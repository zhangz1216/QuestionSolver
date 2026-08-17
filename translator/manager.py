"""协调「框选 -> 截图 -> OCR -> 翻译 -> 原位叠加 -> 卡片」的流程。"""
from PySide6.QtCore import QObject, QThread, Signal, QRect, QBuffer
from PySide6.QtGui import QGuiApplication, QImage

import winsound

from concurrent.futures import ThreadPoolExecutor

from .selector import SelectorOverlay
from .mask import TranslationMask
from . import ocr, translate, config, overlay
from .debuglog import log

MAX_LINES = 25  # 单次翻译最多处理的行数，防止美化字体 OCR 出大量框导致翻译过慢
MAX_WORKERS = 6  # 并行翻译线程数，提升多行翻译速度


def _translate_item(it, target):
    """翻译单行，返回 (box, translated, detected_code)。失败时用原文兜底。"""
    box = it["box"]
    text = it["text"].strip()
    try:
        t, d = translate.translate(text, target=target)
        return box, t, d
    except Exception:  # noqa: BLE001
        return box, text, "auto"


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
    # 显式设置 DPR，让截图显示尺寸与框选逻辑尺寸严格一致
    image.setDevicePixelRatio(screen.devicePixelRatio())
    return image


def crop_precaptured(image: QImage, rect: QRect) -> QImage:
    """从冻结画面中裁剪选中区域。

    冻结画面模式：覆盖层只盖主屏，选中区域 rect 是屏幕逻辑坐标；
    裁剪时换算成物理像素（×DPR）并夹回图片边界，输出保持 DPR。
    """
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


class TranslateWorker(QThread):
    done = Signal(QImage, str, str)   # (原位叠加后的图, 检测语言显示名, 译文文本)
    failed = Signal(str)              # 错误信息

    def __init__(self, image: QImage, target: str):
        super().__init__()
        self._image = image
        self._target = target

    def run(self):
        try:
            png = _qimage_to_png_bytes(self._image)
            items = ocr.recognize_with_boxes(png)
            if not items:
                self.failed.emit("未识别到文字")
                return

            detected_code = "auto"
            lines = []
            translated_texts = []
            # 并行翻译所有行（保持顺序），多行时显著提速
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                results = list(pool.map(
                    lambda it: _translate_item(it, self._target), items[:MAX_LINES]))

            for box, t, d in results:
                lines.append({"box": box, "translated": t})
                translated_texts.append(t)
                if detected_code == "auto":
                    detected_code = d

            composited = overlay.composite_overlay(self._image, lines)
            detected_name = config.DETECTED_NAMES.get(detected_code, detected_code)
            self.done.emit(composited, detected_name, "\n".join(translated_texts))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


def _play_alert():
    """翻译完成提示音。游戏独占音频时 MessageBeep 常被吞，改用原始 Beep 双保险。"""
    if not config.get_alert_enabled():
        return
    try:
        winsound.Beep(1200, 250)
        winsound.Beep(1600, 250)
    except Exception:  # noqa: BLE001
        try:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:  # noqa: BLE001
            pass


class MaskManager(QObject):
    selection_finished = Signal()   # 一次框选流程结束（无论成功/取消）
    game_translated = Signal(str)   # 全屏游戏模式：译文文本
    game_translate_failed = Signal(str)  # 全屏游戏模式：错误信息

    def __init__(self, target_getter):
        super().__init__()
        self._target_getter = target_getter
        self._masks = []
        self._workers = []
        self._selector = None
        self._pre_captured = None  # 冻结画面模式：预先截好的图（游戏画面）

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
        """游戏内框选：先冻结主屏画面（此时游戏还在前台），覆盖层以它为背景。

        独占全屏游戏一弹窗口就会被顶回桌面，若先弹覆盖层再截图，截到的就是桌面；
        必须先截游戏画面 -> 再以它为背景弹覆盖层，框选时看到的才是游戏画面。
        """
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

        mask = TranslationMask(rect, image)
        mask.closed.connect(self._on_mask_closed)
        self._masks.append(mask)
        mask.show()

        target = self._target_getter()
        worker = TranslateWorker(image, target)
        worker.done.connect(lambda img, d, txt, m=mask: self._on_done(m, img, d, txt))
        worker.failed.connect(lambda msg, m=mask: m.set_error(msg))
        worker.finished.connect(lambda: self._drop_worker(worker))
        self._workers.append(worker)
        worker.start()

        self.selection_finished.emit()

    def _on_done(self, mask, image, detected, text):
        if config.get_auto_copy():
            QGuiApplication.clipboard().setText(text)
        mask.set_result(image, detected)

    def _drop_worker(self, worker):
        if worker in self._workers:
            self._workers.remove(worker)

    def _on_mask_closed(self, mask):
        if mask in self._masks:
            self._masks.remove(mask)

    def translate_fullscreen(self):
        """全屏游戏模式：不弹框选覆盖层，直接截主屏翻译，结果走剪贴板 + 通知。

        独占全屏游戏里任何悬浮窗口/覆盖层都会把游戏挤回桌面，所以这里
        全程不创建窗口，只截屏 -> OCR -> 翻译 -> 写剪贴板。
        """
        log("进入游戏模式：开始截主屏")
        screen = QGuiApplication.primaryScreen()
        image = capture_region(screen.geometry())
        target = self._target_getter()
        worker = TranslateWorker(image, target)
        worker.done.connect(self._on_game_done)
        worker.failed.connect(self._on_game_failed)
        worker.finished.connect(lambda w=worker: self._drop_worker(w))
        self._workers.append(worker)
        worker.start()

    def _on_game_done(self, image, detected, text):
        # 游戏里看不到结果卡片，剪贴板是主要输出
        QGuiApplication.clipboard().setText(text)
        log(f"游戏翻译完成({detected}): {text[:60]}")
        _play_alert()
        self.game_translated.emit(text)

    def _on_game_failed(self, msg):
        log(f"游戏翻译失败: {msg}")
        _play_alert()
        self.game_translate_failed.emit(msg)

    def clear_all(self):
        for m in list(self._masks):
            m.close()
        self._masks.clear()
