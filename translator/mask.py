"""翻译卡片窗口：上半显示框选截图，下半显示译文，半透明，可拖拽，右上角 ✕ 关闭。"""
from PySide6.QtCore import Qt, QRect, Signal, QEvent
from PySide6.QtGui import QFont, QPixmap, QImage
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel)

MIN_W = 260


class TranslationMask(QWidget):
    closed = Signal(object)  # 发送自身，供管理器从列表移除

    def __init__(self, rect: QRect, image: QImage, font_size: int = 13):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setGeometry(rect)
        self._image = image
        self._drag_offset = None
        self._build_ui(font_size)
        self._install_drag()
        self.set_loading()

    def _build_ui(self, font_size: int):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._panel = QWidget(self)
        self._panel.setObjectName("panel")
        self._panel.setStyleSheet("""
            #panel { background-color: rgba(30, 32, 40, 188);
                     border: 1px solid rgba(255, 255, 255, 28);
                     border-radius: 10px; }
            QLabel#src { color: #a7abb8; font-size: 11px; }
            QLabel#shot { background-color: rgba(255, 255, 255, 8);
                          border: 1px solid rgba(255, 255, 255, 22);
                          border-radius: 6px; }
            QLabel#dst { color: #ffffff; }
            QPushButton#close_btn { background: transparent; border: none;
                                     color: #c7c9d1; font-size: 15px; }
            QPushButton#close_btn:hover { color: #ff5b5b; }
        """)
        outer.addWidget(self._panel)

        lay = QVBoxLayout(self._panel)
        lay.setContentsMargins(10, 7, 10, 10)
        lay.setSpacing(7)

        # 顶部：检测语言 + 关闭按钮
        top = QHBoxLayout()
        top.setSpacing(6)
        self._src_label = QLabel("")
        self._src_label.setObjectName("src")
        self._src_label.setWordWrap(True)
        btn = QPushButton("✕")
        btn.setObjectName("close_btn")
        btn.setFixedSize(22, 22)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip("关闭（拖拽卡片可移动）")
        btn.clicked.connect(self._on_close)
        top.addWidget(self._src_label, 1)
        top.addWidget(btn, 0, Qt.AlignTop)
        lay.addLayout(top)

        # 框选截图
        self._shot_label = QLabel()
        self._shot_label.setObjectName("shot")
        self._shot_label.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._shot_label)

        # 译文
        self._dst_label = QLabel("")
        self._dst_label.setObjectName("dst")
        self._dst_label.setWordWrap(True)
        f = QFont()
        f.setPointSize(font_size)
        self._dst_label.setFont(f)
        lay.addWidget(self._dst_label)

    def set_loading(self):
        self._src_label.setText("")
        self._dst_label.setText("识别中…")
        self._show_shot()
        self._adjust_size()

    def set_text(self, translated: str, detected: str):
        self._src_label.setText(f"检测到：{detected}" if detected else "")
        self._dst_label.setText(translated)
        self._adjust_size()

    def _show_shot(self):
        if self._image is None or self._image.isNull():
            self._shot_label.hide()
            return
        # 原生尺寸显示，不缩放（保留截图原比例与原大小）
        pm = QPixmap.fromImage(self._image)
        self._shot_label.setPixmap(pm)
        self._shot_label.show()

    def _adjust_size(self):
        # 卡片宽度跟随截图原生宽度，译文按此宽度换行
        shot_w = self._shot_label.sizeHint().width()
        if shot_w > 0:
            self._dst_label.setMaximumWidth(max(shot_w, MIN_W))
        hint = self._panel.sizeHint()
        w = max(self.width(), MIN_W, hint.width())
        h = max(self.height(), hint.height())
        self.resize(w, h)

    # ---------- 拖拽移动 ----------
    def _install_drag(self):
        for w in (self, self._panel, self._src_label, self._shot_label, self._dst_label):
            w.installEventFilter(self)

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            return False
        if t == QEvent.MouseMove and self._drag_offset is not None and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            return True
        if t == QEvent.MouseButtonRelease:
            self._drag_offset = None
            return False
        return super().eventFilter(obj, event)

    def _on_close(self):
        self.closed.emit(self)
        self.close()
