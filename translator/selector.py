"""全屏框选覆盖层：左键拖拽画框选择翻译区域。"""
from PySide6.QtCore import Qt, QRect, QSize, Signal
from PySide6.QtGui import QColor, QPainter, QGuiApplication
from PySide6.QtWidgets import QWidget, QRubberBand


class SelectorOverlay(QWidget):
    region_selected = Signal(QRect)   # 屏幕逻辑坐标下的选中区域
    cancelled = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        vg = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(vg)
        self._origin_local = None
        self._origin_global = None
        self._rubber = QRubberBand(QRubberBand.Rectangle, self)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 55))
        p.setPen(QColor(255, 255, 255, 220))
        f = p.font()
        f.setPointSize(14)
        p.setFont(f)
        p.drawText(self.rect().adjusted(30, 24, -30, -24),
                   Qt.AlignTop | Qt.AlignHCenter,
                   "按住鼠标左键拖拽框选要翻译的区域\n右键或 Esc 取消")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._origin_local = e.position().toPoint()
            self._origin_global = e.globalPosition().toPoint()
            self._rubber.setGeometry(QRect(self._origin_local, QSize()))
            self._rubber.show()
        elif e.button() == Qt.RightButton:
            self._cancel()

    def mouseMoveEvent(self, e):
        if self._origin_local is not None and (e.buttons() & Qt.LeftButton):
            rect = QRect(self._origin_local, e.position().toPoint()).normalized()
            self._rubber.setGeometry(rect)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._origin_local is not None:
            self._rubber.hide()
            rect = QRect(self._origin_global, e.globalPosition().toPoint()).normalized()
            self._origin_local = None
            self._origin_global = None
            self.close()
            if rect.width() >= 5 and rect.height() >= 5:
                self.region_selected.emit(rect)
            else:
                self.cancelled.emit()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._cancel()

    def _cancel(self):
        self._origin_local = None
        self._origin_global = None
        self.close()
        self.cancelled.emit()
