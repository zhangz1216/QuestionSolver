"""协调「框选 -> 截图 -> OCR -> 翻译 -> 遮罩」的流程。"""
from PySide6.QtCore import QObject, QThread, Signal, QRect, QBuffer
from PySide6.QtGui import QGuiApplication, QImage

from .selector import SelectorOverlay
from .mask import TranslationMask
from . import ocr, translate, config


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
    # 显式设置 DPR，让截图显示尺寸与框选逻辑尺寸严格一致（150% 缩放下不放大/缩小）
    image.setDevicePixelRatio(screen.devicePixelRatio())
    return image


class TranslateWorker(QThread):
    done = Signal(str, str)    # (译文, 检测语言显示名)
    failed = Signal(str)       # 错误信息

    def __init__(self, image: QImage, target: str):
        super().__init__()
        self._image = image
        self._target = target

    def run(self):
        try:
            png = _qimage_to_png_bytes(self._image)
            text = ocr.recognize(png)
            if not text or not text.strip():
                self.failed.emit("未识别到文字")
                return
            translated, detected_code = translate.translate(
                text.strip(), target=self._target)
            detected_name = config.DETECTED_NAMES.get(detected_code, detected_code)
            self.done.emit(translated, detected_name)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class MaskManager(QObject):
    selection_finished = Signal()  # 一次框选流程结束（无论成功/取消）

    def __init__(self, target_getter):
        super().__init__()
        self._target_getter = target_getter
        self._masks = []
        self._workers = []
        self._selector = None

    def start_selection(self):
        if self._selector is not None:
            return
        self._selector = SelectorOverlay()
        self._selector.region_selected.connect(self._on_region)
        self._selector.cancelled.connect(self._on_cancel)
        self._selector.show()
        self._selector.activateWindow()

    def _cleanup_selector(self):
        if self._selector is not None:
            self._selector.deleteLater()
            self._selector = None

    def _on_cancel(self):
        self._cleanup_selector()
        self.selection_finished.emit()

    def _on_region(self, rect: QRect):
        self._cleanup_selector()
        image = capture_region(rect)

        mask = TranslationMask(rect, image, config.get_font_size())
        mask.closed.connect(self._on_mask_closed)
        self._masks.append(mask)
        mask.show()

        target = self._target_getter()
        worker = TranslateWorker(image, target)
        worker.done.connect(lambda t, d, m=mask: self._on_done(m, t, d))
        worker.failed.connect(lambda msg, m=mask: m.set_text(f"⚠ {msg}", ""))
        worker.finished.connect(lambda: self._drop_worker(worker))
        self._workers.append(worker)
        worker.start()

        self.selection_finished.emit()

    def _on_done(self, mask, translated: str, detected: str):
        if config.get_auto_copy():
            QGuiApplication.clipboard().setText(translated)
        mask.set_text(translated, detected)

    def _drop_worker(self, worker):
        if worker in self._workers:
            self._workers.remove(worker)

    def _on_mask_closed(self, mask):
        if mask in self._masks:
            self._masks.remove(mask)

    def clear_all(self):
        for m in list(self._masks):
            m.close()
        self._masks.clear()
