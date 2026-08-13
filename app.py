"""悬屏翻译 - 程序入口。"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from translator.widget import TranslatorWidget


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("悬屏翻译")
    app.setApplicationDisplayName("悬屏翻译")
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Microsoft YaHei UI", 10))

    widget = TranslatorWidget()
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
