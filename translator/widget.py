"""悬浮挂件：置顶、可拖拽、含「框选翻译」按钮与语言设置。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon, QAction, QGuiApplication
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QComboBox, QCheckBox, QMenu,
                               QSystemTrayIcon, QApplication)

from . import config
from .manager import MaskManager


class TranslatorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag_offset = None
        self._was_visible = True
        self.manager = MaskManager(self._current_target)
        self.manager.selection_finished.connect(self._restore_widget)
        self._build_ui()
        self._build_tray()
        self._move_to_corner()
        self._setup_hotkey()

    # ---------- 目标语言 ----------
    def _current_target(self) -> str:
        return self.combo_target.currentData()

    # ---------- UI ----------
    def _build_ui(self):
        self.setObjectName("root")
        self.setStyleSheet("""
            #root { background: transparent; }
            #panel { background-color: rgba(35, 38, 46, 242); border-radius: 12px;
                    border: 1px solid rgba(255,255,255,22); }
            QLabel#title { color: #fff; font-size: 13px; font-weight: bold; }
            QLabel#lbl { color: #c3c6cd; font-size: 12px; }
            QPushButton#select { background-color: #2f7bff; color: white; border: none;
                                 border-radius: 8px; padding: 10px 16px; font-size: 14px;
                                 font-weight: bold; }
            QPushButton#select:hover { background-color: #3f8aff; }
            QPushButton#select:pressed { background-color: #2566d6; }
            QPushButton#close { background: transparent; color: #9aa; border: none; font-size: 14px; }
            QPushButton#close:hover { color: #fff; }
            QComboBox { background: #2c2f37; color: #eee; border: 1px solid #444;
                        border-radius: 6px; padding: 3px 6px; }
            QComboBox QAbstractItemView { background: #2c2f37; color: #eee;
                                          selection-background-color: #2f7bff; }
            QCheckBox { color: #b5b8bf; font-size: 11px; }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._panel = QWidget(self)
        self._panel.setObjectName("panel")
        outer.addWidget(self._panel)

        lay = QVBoxLayout(self._panel)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(8)

        # 标题行
        top = QHBoxLayout()
        title = QLabel("悬屏翻译")
        title.setObjectName("title")
        close = QPushButton("✕")
        close.setObjectName("close")
        close.setFixedSize(20, 20)
        close.setCursor(Qt.PointingHandCursor)
        close.setToolTip("最小化到托盘")
        close.clicked.connect(self.hide)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(close)
        lay.addLayout(top)

        # 框选按钮
        self.btn_select = QPushButton("框选翻译")
        self.btn_select.setObjectName("select")
        self.btn_select.setCursor(Qt.PointingHandCursor)
        self.btn_select.clicked.connect(self._on_select)
        lay.addWidget(self.btn_select)

        # 语言行
        lang_row = QHBoxLayout()
        lang_row.setSpacing(6)
        lbl = QLabel("翻译成：")
        lbl.setObjectName("lbl")
        self.combo_target = QComboBox()
        for label, code in config.TARGET_LANGUAGES:
            self.combo_target.addItem(label, code)
        idx = self.combo_target.findData(config.get_target())
        if idx >= 0:
            self.combo_target.setCurrentIndex(idx)
        self.combo_target.currentIndexChanged.connect(
            lambda: config.set_target(self._current_target()))
        lang_row.addWidget(lbl)
        lang_row.addWidget(self.combo_target, 1)
        lay.addLayout(lang_row)

        # 自动复制
        self.chk_copy = QCheckBox("翻译结果自动复制到剪贴板")
        self.chk_copy.setChecked(config.get_auto_copy())
        self.chk_copy.toggled.connect(config.set_auto_copy)
        lay.addWidget(self.chk_copy)

        hint = QLabel("快捷键：Ctrl+Shift+T")
        hint.setObjectName("lbl")
        hint.setAlignment(Qt.AlignCenter)
        lay.addWidget(hint)

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self._make_icon())
        self.tray.setToolTip("悬屏翻译")
        menu = QMenu()
        act_show = QAction("显示挂件", self)
        act_show.triggered.connect(self._show_widget)
        act_select = QAction("框选翻译", self)
        act_select.triggered.connect(self._on_select)
        act_clear = QAction("清除所有遮罩", self)
        act_clear.triggered.connect(self.manager.clear_all)
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(self._quit)
        for a in (act_show, act_select, act_clear):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _make_icon(self) -> QIcon:
        pm = QPixmap(64, 64)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#2f7bff"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(4, 4, 56, 56, 14, 14)
        p.setPen(QColor("white"))
        f = QFont()
        f.setPointSize(26)
        f.setBold(True)
        p.setFont(f)
        p.drawText(pm.rect(), Qt.AlignCenter, "译")
        p.end()
        return QIcon(pm)

    def _move_to_corner(self):
        screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        self.adjustSize()
        x = geo.right() - self.width() - 20
        y = geo.top() + 20
        self.move(x, y)

    # ---------- 行为 ----------
    def _on_select(self):
        self._was_visible = self.isVisible()
        self.hide()
        self.manager.start_selection()

    def _restore_widget(self):
        if self._was_visible and not self.isVisible():
            self.show()
            self.raise_()

    def _setup_hotkey(self):
        self._hotkey = None
        try:
            from .hotkey import GlobalHotkey
            self._hotkey = GlobalHotkey(self._on_select)
            self._hotkey.register()
            QApplication.instance().installNativeEventFilter(self._hotkey.filter)
        except Exception as e:  # noqa: BLE001
            print(f"[提示] 全局快捷键注册失败：{e}")

    def _show_widget(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._show_widget()

    def _quit(self):
        self.tray.hide()
        QApplication.quit()

    # ---------- 拖拽 ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None and (e.buttons() & Qt.LeftButton):
            self.move(e.globalPosition().toPoint() - self._drag_offset)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_offset = None
