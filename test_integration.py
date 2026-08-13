"""集成测试：验证「遮罩 + 后台线程 + OCR + 翻译」整条链路（用已知文字测试图）。"""
import sys
sys.path.insert(0, ".")
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage
from PySide6.QtCore import QTimer, QRect

from translator.mask import TranslationMask
from translator.manager import TranslateWorker

app = QApplication(sys.argv)

img = QImage("test_image.png")  # 内容为 "Save your work now"

mask = TranslationMask(QRect(200, 200, 420, 130), img, font_size=13)
mask.show()


def on_done(translated, detected):
    print(f"[完成] 检测语言={detected} 译文={translated}")
    mask.set_text(translated, detected)


def on_failed(msg):
    print(f"[失败] {msg}")
    mask.set_text(f"⚠ {msg}", "")


worker = TranslateWorker(img, "zh-CN")
worker.done.connect(on_done)
worker.failed.connect(on_failed)
worker.finished.connect(app.quit)
worker.start()

QTimer.singleShot(20000, app.quit)  # 20s 兜底
sys.exit(app.exec())
