"""视界 AI 搜题 - 程序入口。"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from solver.widget import SolverWidget


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("视界 AI 搜题")
    app.setApplicationDisplayName("视界 AI 搜题")
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Microsoft YaHei UI", 10))

    widget = SolverWidget()
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
