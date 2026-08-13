"""验证屏幕区域截图 + OCR 链路（拖拽后实际走的就是这个）。"""
import sys
sys.path.insert(0, ".")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRect
from translator.manager import capture_region, _qimage_to_png_bytes
from translator import ocr

app = QApplication(sys.argv)
rect = QRect(100, 100, 900, 320)
img = capture_region(rect)
print(f"截图尺寸: {img.width()}x{img.height()}, 是否为空: {img.isNull()}")
png = _qimage_to_png_bytes(img)
print(f"PNG 字节数: {len(png)}")
text = ocr.recognize(png)
print(f"OCR 结果: {text[:120]!r}")
