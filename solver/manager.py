"""协调「框选 -> 截图 -> OCR -> 组装题目 -> 双引擎搜题 -> 结果卡片」的流程。"""
from PySide6.QtCore import QObject, QThread, Signal, QRect, QBuffer
from PySide6.QtGui import QGuiApplication, QImage

import winsound

from .selector import SelectorOverlay
from .resultcard import ResultCard
from . import ocr, config, engines
from .debuglog import log


def _qimage_to_png_bytes(image: QImage) -> bytes:
    buf = QBuffer()
    buf.open(QBuffer.WriteOnly)
    image.save(buf, "PNG")
    return bytes(buf.data())


def capture_region(rect: QRect) -> QImage:
    """按屏幕逻辑坐标截取区域，跨屏自动定位到所在屏幕。"""
    screens = QGuiApplication.screens()
    screen = None
    for s in screens:
        if s.geometry().contains(rect.topLeft()):
            screen = s
            break
    if screen is None:
        screen = QGuiApplication.primaryScreen()
    g = screen.geometry()
    local = rect.translated(-g.x(), -g.y())
    pixmap = screen.grabWindow(0, local.x(), local.y(),
                               max(1, rect.width()), max(1, rect.height()))
    image = pixmap.toImage()
    image.setDevicePixelRatio(screen.devicePixelRatio())
    return image


def crop_precaptured(image: QImage, rect: QRect) -> QImage:
    """从冻结画面中裁剪选中区域（游戏内框选场景）。"""
    g = QGuiApplication.primaryScreen().geometry()
    local = rect.translated(-g.x(), -g.y())
    dpr = image.devicePixelRatio()
    phys = QRect(int(local.x() * dpr), int(local.y() * dpr),
                 int(local.width() * dpr), int(local.height() * dpr))
    phys = phys.intersected(QRect(0, 0, image.width(), image.height()))
    if phys.width() < 4 or phys.height() < 4:
        raise ValueError("框选区域过小")
    crop = image.copy(phys)
    crop.setDevicePixelRatio(dpr)
    return crop


class SolveWorker(QThread):
    """后台搜题线程：OCR -> 组装题目 -> 引擎解答。"""

    done = Signal(str, str, str, str, float)
    # (题目文本, 答案 markdown, 引擎显示名, 模型名, 耗时秒)
    failed = Signal(str)

    def __init__(self, image: QImage, *, provider: str, deep: bool = False,
                 question_override: str = "", use_questionbank: bool = False):
        super().__init__()
        self._image = image
        self._provider = provider          # "free" / "deepseek"
        self._deep = deep                  # True -> 深度重搜（DEEP_MODEL）
        self._question_override = question_override
        self._use_questionbank = use_questionbank

    def run(self):
        try:
            # 1. OCR（或直接用用户改过的题目）
            question = self._question_override
            if not question:
                png = _qimage_to_png_bytes(self._image)
                question = ocr.recognize(png).strip()
                if not question:
                    self.failed.emit("未识别到题目文字，请重试或框选更大范围")
                    return

            # 2. 参考题库：检索最相关的资料块（纯本地）
            context_chunks = None
            if self._use_questionbank:
                from . import questionbank as qb
                ref_id = config.get_reference_id()
                bank_ids = [ref_id] if ref_id > 0 else None
                hits = qb.retrieve(question, bank_ids=bank_ids, top_k=3)
                if hits:
                    context_chunks = [f"[{h['source_name']}]\n{h['text']}" for h in hits]
                    log(f"题库检索到 {len(hits)} 段参考：{[h['source_name'] for h in hits]}")

            # 3. 组装引擎参数（读最新配置）
            if self._provider == "deepseek":
                api_key = config.get_deepseek_key()
                # 深度重搜用 DEEP_MODEL（官方 V4 系列），不能用已下线的 deepseek-reasoner
                model = engines.DEEP_MODEL if self._deep else config.get_deepseek_model()
                result = engines.solve(question, provider="deepseek", api_key=api_key,
                                       model=model, context_chunks=context_chunks)
            else:
                api_key = config.get_free_key()
                result = engines.solve(question, provider="free", api_key=api_key,
                                       free_provider=config.get_free_provider(),
                                       model=config.get_free_model(),
                                       context_chunks=context_chunks)
            self.done.emit(question, result.text, result.engine_name, result.model, result.elapsed)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


def _play_alert():
    """搜题完成提示音。"""
    if not config.get_alert_enabled():
        return
    try:
        winsound.Beep(1200, 200)
    except Exception:  # noqa: BLE001
        try:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:  # noqa: BLE001
            pass


class SolverManager(QObject):
    selection_finished = Signal()          # 一次框选流程结束（无论成功/取消）
    game_solved = Signal(str)              # 全屏模式：解答文本
    game_solve_failed = Signal(str)        # 全屏模式：错误信息

    def __init__(self, params_getter):
        """params_getter() -> dict：{'provider': 'free'|'deepseek',
        'deep': bool, 'use_questionbank': bool, 'questionbank_name': str|None}"""
        super().__init__()
        self._params_getter = params_getter
        self._cards = []
        self._workers = []
        self._selector = None
        self._pre_captured = None

    # ---------- 框选 ----------
    def start_selection(self, pre_captured=None):
        if self._selector is not None:
            return
        self._pre_captured = pre_captured
        self._selector = SelectorOverlay(pre_captured)
        self._selector.region_selected.connect(self._on_region)
        self._selector.cancelled.connect(self._on_cancel)
        self._selector.show()
        self._selector.activateWindow()

    def start_game_selection(self):
        screen = QGuiApplication.primaryScreen()
        pre = capture_region(screen.geometry())
        self.start_selection(pre_captured=pre)

    def _cleanup_selector(self):
        if self._selector is not None:
            self._selector.deleteLater()
            self._selector = None

    def _on_cancel(self):
        self._pre_captured = None
        self._cleanup_selector()
        self.selection_finished.emit()

    def _on_region(self, rect: QRect):
        self._cleanup_selector()
        if self._pre_captured is not None:
            image = crop_precaptured(self._pre_captured, rect)
            self._pre_captured = None
        else:
            image = capture_region(rect)

        card = ResultCard(rect, image)
        card.resolve_requested.connect(self._on_resolve_requested)
        self._cards.append(card)
        card.destroyed.connect(lambda obj=None, c=card: self._on_card_closed(c))
        card.show()

        self._start_worker(image, card)
        self.selection_finished.emit()

    def _start_worker(self, image, card, question_override="", deep=False):
        params = self._params_getter()
        provider = params.get("provider", "free")
        # 深度重搜固定走 DeepSeek
        if deep:
            provider = "deepseek"
        card.set_solving("DeepSeek" if provider == "deepseek" else "免费引擎")
        worker = SolveWorker(image, provider=provider, deep=deep,
                             question_override=question_override,
                             use_questionbank=params.get("use_questionbank", False))
        worker.done.connect(lambda q, a, en, m, el, c=card: self._on_done(c, q, a, en, m, el))
        worker.failed.connect(lambda msg, c=card: c.set_error(msg))
        worker.finished.connect(lambda w=worker: self._drop_worker(w))
        self._workers.append(worker)
        worker.start()

    def _on_resolve_requested(self, question, deep):
        """结果卡片请求重搜：找到对应卡片并重跑。"""
        card = self.sender()
        if card is None:
            return
        image = card._image
        # 修改重搜：直接用新题目文本，跳过 OCR
        card.set_solving("DeepSeek" if deep else "免费引擎")
        self._start_worker(image, card, question_override=question, deep=deep)

    def _on_done(self, card, question, answer, engine_name, model, elapsed):
        if config.get_auto_copy():
            QGuiApplication.clipboard().setText(answer)
        if config.get_save_history():
            try:
                from . import history
                history.add_record(question, answer, engine_name, model, card._image)
            except Exception as e:  # noqa: BLE001
                log(f"历史保存失败: {e}")
        card.set_result(question, answer, engine_name, model)
        log(f"搜题完成({engine_name}/{model}, {elapsed:.1f}s): {question[:40]}")
        _play_alert()

    def _drop_worker(self, worker):
        if worker in self._workers:
            self._workers.remove(worker)

    def _on_card_closed(self, card):
        if card in self._cards:
            self._cards.remove(card)

    # ---------- 全屏模式（截全屏搜题，结果进剪贴板） ----------
    def solve_fullscreen(self):
        log("进入全屏模式：开始截主屏")
        screen = QGuiApplication.primaryScreen()
        image = capture_region(screen.geometry())
        worker = SolveWorker(image, provider="deepseek")
        worker.done.connect(self._on_game_done)
        worker.failed.connect(self._on_game_failed)
        worker.finished.connect(lambda w=worker: self._drop_worker(w))
        self._workers.append(worker)
        worker.start()

    def _on_game_done(self, question, answer, engine_name, model, elapsed):
        QGuiApplication.clipboard().setText(answer)
        log(f"全屏搜题完成({engine_name}/{model}): {answer[:60]}")
        _play_alert()
        self.game_solved.emit(answer)

    def _on_game_failed(self, msg):
        log(f"全屏搜题失败: {msg}")
        _play_alert()
        self.game_solve_failed.emit(msg)

    def clear_all(self):
        for c in list(self._cards):
            c.close()
        self._cards.clear()
