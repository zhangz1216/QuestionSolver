"""协调「框选 -> 截图 -> OCR -> 翻译 -> 原位叠加 -> 卡片」的流程。"""
from PySide6.QtCore import QObject, QThread, Signal, QRect, QBuffer
from PySide6.QtGui import QGuiApplication, QImage

from concurrent.futures import ThreadPoolExecutor

from .selector import SelectorOverlay
from .mask import TranslationMask
from . import ocr, translate, config, overlay

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

    def clear_all(self):
        for m in list(self._masks):
            m.close()
        self._masks.clear()
