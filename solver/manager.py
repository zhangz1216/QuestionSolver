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

    chunk = Signal(str)  # 流式输出的增量文本（deepseek）
    done = Signal(str, str, str, str, float, str)
    # (题目文本, 答案 markdown, 引擎显示名, 模型名, 耗时秒, 记录类型 kind)
    # kind: 'ocr'=OCR 识别搜题 / 'vision'=看图直搜 / ''=未标记
    failed = Signal(str)

    def __init__(self, image: QImage, *, provider: str, model: str = "",
                 question_override: str = "", use_questionbank: bool = False,
                 vision_direct: bool = False, images: list | None = None,
                 prompt_extra: str = ""):
        super().__init__()
        self._image = image
        self._provider = provider          # "free" / "deepseek"
        self._model = model                # 指定模型（如用户选模型重搜）；空=用当前配置
        self._question_override = question_override
        self._use_questionbank = use_questionbank
        self._vision_direct = vision_direct  # 看图直搜：把原图直接发给视觉模型
        self._images = images or [image]     # 多图列表（添加框选图后多张）
        self._prompt_extra = prompt_extra    # 视觉搜题的用户附加说明（改题/条件）

    def run(self):
        try:
            # 1a. 看图直搜：跳过 OCR，把原图直接发给 DeepSeek 视觉模型
            if self._vision_direct:
                api_key = config.get_deepseek_key()
                model = self._model or config.get_deepseek_model() or engines.DEFAULT_VISION_MODEL
                pngs = [_qimage_to_png_bytes(i) for i in self._images]
                result = engines.solve_vision_stream(
                    pngs, api_key=api_key, model=model,
                    on_token=self.chunk.emit, prompt_extra=self._prompt_extra)
                # 看图搜题没有文本题目：question 传空，避免占位符污染「加条件重搜」
                self.done.emit("", result.text, result.engine_name,
                               result.model, result.elapsed, "vision")
                return

            # 1b. 常规：识别题目（OCR 为主；空/低置信度时用 DeepSeek 视觉模型兜底）
            question = self._question_override
            if not question:
                png = _qimage_to_png_bytes(self._image)
                question = self._recognize(png)
                if not question:
                    self.failed.emit("未能识别到题目文字，请重试或框选更大范围")
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
                # 指定模型优先；未指定用设置里的默认模型
                model = self._model or config.get_deepseek_model()
                # 流式：边生成边通过 chunk 信号上屏，首字 1 秒内可见
                result = engines.solve_stream(question, provider="deepseek",
                                              api_key=api_key, model=model,
                                              context_chunks=context_chunks,
                                              on_token=self.chunk.emit)
            else:
                api_key = config.get_free_key()
                result = engines.solve(question, provider="free", api_key=api_key,
                                       free_provider=config.get_free_provider(),
                                       model=config.get_free_model(),
                                       context_chunks=context_chunks)
            self.done.emit(question, result.text, result.engine_name, result.model, result.elapsed, "ocr")
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))

    def _recognize(self, png):
        """识别题目：本地 OCR 优先（免费快）；空/低置信度时用 DeepSeek 视觉模型兜底。

        返回 (识别文本) 或空字符串。
        """
        # --- OCR 优先 ---
        try:
            text, avg_score, lines = ocr.recognize_scored(png)
        except Exception as e:  # noqa: BLE001
            log(f"OCR 识别异常: {e}")
            text, avg_score, lines = "", 0.0, 0
        # OCR 可信：非空 + 平均置信度达标 + 有内容行
        if text and avg_score >= 0.55 and lines >= 1:
            return text

        log(f"OCR 不可信(score={avg_score:.2f}, lines={lines})，尝试 DeepSeek 视觉识别兜底")
        # --- 视觉兜底（DeepSeek vision） ---
        try:
            api_key = config.get_deepseek_key()
        except Exception as e:  # noqa: BLE001
            log(f"读取 DeepSeek key 失败: {e}")
            api_key = ""
        if api_key:
            try:
                vis_text = engines.vision_recognize(png, api_key=api_key,
                                                    model=config.get_deepseek_model())
                if vis_text:
                    log(f"视觉识别兜底成功（{len(vis_text)}字）")
                    return vis_text
            except Exception as e:  # noqa: BLE001
                log(f"视觉识别兜底失败: {e}")
        # 兜底失败：回退 OCR 结果（即使效果一般）
        return text


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
        self._add_image_target = None  # 「添加框选图」的目标卡片（None=普通框选建新卡）

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
        self._add_image_target = None
        self._cleanup_selector()
        self.selection_finished.emit()

    def _on_region(self, rect: QRect):
        self._cleanup_selector()
        if self._pre_captured is not None:
            image = crop_precaptured(self._pre_captured, rect)
            self._pre_captured = None
        else:
            image = capture_region(rect)

        # 加图模式：把这次框选追加到目标卡片（题目太长分多张截图）
        if self._add_image_target is not None:
            card = self._add_image_target
            self._add_image_target = None
            card.add_image(image)
            self.selection_finished.emit()
            return

        card = ResultCard(rect, image)
        card.resolve_requested.connect(self._on_resolve_requested)
        card.vision_solve_requested.connect(self._on_vision_requested)
        card.add_image_requested.connect(self._on_add_image_requested)
        self._cards.append(card)
        card.destroyed.connect(lambda obj=None, c=card: self._on_card_closed(c))
        card.show()

        self._start_worker(image, card)
        self.selection_finished.emit()

    def _start_worker(self, image, card, question_override="", model=""):
        params = self._params_getter()
        provider = params.get("provider", "free")
        # 指定模型重搜固定走 DeepSeek
        if model:
            provider = "deepseek"
        card.set_solving("DeepSeek" if provider == "deepseek" else "免费引擎")
        worker = SolveWorker(image, provider=provider, model=model,
                             question_override=question_override,
                             use_questionbank=params.get("use_questionbank", False))
        worker.chunk.connect(lambda d, c=card: c.append_answer(d))
        worker.done.connect(lambda q, a, en, m, el, k, c=card: self._on_done(c, q, a, en, m, el, k))
        worker.failed.connect(lambda msg, c=card: self._on_card_failed(c, msg))
        worker.finished.connect(lambda w=worker: self._drop_worker(w))
        self._workers.append(worker)
        worker.start()

    def _on_resolve_requested(self, question, model):
        """结果卡片请求重搜：找到对应卡片并重跑。model 非空=用指定 DeepSeek 模型。"""
        card = self.sender()
        if card is None:
            return
        image = card._image
        # 修改/加条件重搜：直接用新题目文本，跳过 OCR（provider/状态由 _start_worker 设置）
        self._start_worker(image, card, question_override=question, model=model)

    def _on_vision_requested(self, images, model, prompt_extra=""):
        """卡片请求「看图直搜/看图+条件重搜」：把原图直接发给 DeepSeek 视觉模型。"""
        card = self.sender()
        if card is None:
            return
        model = model or config.get_deepseek_model() or engines.DEFAULT_VISION_MODEL
        label = "DeepSeek " + (" · 看图直搜" if not prompt_extra else " · 看图+条件")
        card.set_solving(f"{model}{label}")
        worker = SolveWorker(card._image, provider="deepseek", model=model,
                             vision_direct=True, images=images,
                             prompt_extra=prompt_extra)
        worker.chunk.connect(lambda d, c=card: c.append_answer(d))
        worker.done.connect(lambda q, a, en, m, el, k, c=card: self._on_done(c, q, a, en, m, el, k))
        worker.failed.connect(lambda msg, c=card: self._on_card_failed(c, msg))
        worker.finished.connect(lambda w=worker: self._drop_worker(w))
        self._workers.append(worker)
        worker.start()

    def _on_add_image_requested(self):
        """卡片请求「添加框选图」：进入框选，把新截图追加到该卡片。"""
        card = self.sender()
        if card is None or self._selector is not None:
            return
        self._add_image_target = card
        self._selector = SelectorOverlay(self._pre_captured)
        self._selector.region_selected.connect(self._on_region)
        self._selector.cancelled.connect(self._on_cancel)
        self._selector.show()
        self._selector.activateWindow()

    def _on_done(self, card, question, answer, engine_name, model, elapsed, kind=""):
        if config.get_auto_copy():
            QGuiApplication.clipboard().setText(answer)
        if config.get_save_history():
            try:
                from . import history
                history.add_record(question or "（看图搜题）", answer, engine_name, model,
                                   card._image, kind=kind)
            except Exception as e:  # noqa: BLE001
                log(f"历史保存失败: {e}")
        card.set_result(question, answer, engine_name, model)
        log(f"搜题完成({engine_name}/{model}, {elapsed:.1f}s): {question[:40]}")
        _play_alert()

    def _on_card_failed(self, card, msg):
        """卡片搜题失败：记日志（失败无痕=无法排查）+ 卡片显示错误。"""
        log(f"搜题失败: {msg}")
        card.set_error(msg)

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

    def _on_game_done(self, question, answer, engine_name, model, elapsed, kind=""):
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
