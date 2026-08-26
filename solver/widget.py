"""悬浮挂件：置顶、可拖拽、含「框选搜题」按钮与引擎选择。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon, QAction, QGuiApplication
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QComboBox, QCheckBox, QMenu,
                               QSystemTrayIcon, QApplication)

from . import config
from .debuglog import log
from .fullscreen import is_fullscreen_foreground
from .manager import SolverManager
from .settings import SettingsDialog


class SolverWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag_offset = None
        self._was_visible = True
        self.manager = SolverManager(self._current_params)
        self.manager.selection_finished.connect(self._restore_widget)
        self.manager.game_solved.connect(self._on_game_solved)
        self.manager.game_solve_failed.connect(self._on_game_solve_failed)
        self._build_ui()
        self._build_tray()
        self._move_to_corner()
        self._setup_hotkey()

    # ---------- 搜题参数（供 manager 每次框选时读取） ----------
    def _current_params(self) -> dict:
        return {
            "provider": self.combo_engine.currentData(),
            "deep": False,
            "use_questionbank": self.chk_bank.isChecked(),
            "questionbank_name": None,
        }

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
        title = QLabel("悬屏搜题")
        title.setObjectName("title")
        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("close")
        settings_btn.setFixedSize(20, 20)
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.setToolTip("设置（API Key、模型等）")
        settings_btn.clicked.connect(self._open_settings)
        close = QPushButton("✕")
        close.setObjectName("close")
        close.setFixedSize(20, 20)
        close.setCursor(Qt.PointingHandCursor)
        close.setToolTip("最小化到托盘")
        close.clicked.connect(self.hide)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(settings_btn)
        top.addWidget(close)
        lay.addLayout(top)

        # 框选按钮
        self.btn_select = QPushButton("框选搜题")
        self.btn_select.setObjectName("select")
        self.btn_select.setCursor(Qt.PointingHandCursor)
        self.btn_select.clicked.connect(self._on_select)
        lay.addWidget(self.btn_select)

        # 引擎行
        engine_row = QHBoxLayout()
        engine_row.setSpacing(6)
        lbl = QLabel("引擎：")
        lbl.setObjectName("lbl")
        self.combo_engine = QComboBox()
        self.combo_engine.addItem("免费引擎（省钱，简单题）", "free")
        self.combo_engine.addItem("DeepSeek（付费，更准）", "deepseek")
        idx = self.combo_engine.findData(config.get_default_provider())
        if idx >= 0:
            self.combo_engine.setCurrentIndex(idx)
        self.combo_engine.currentIndexChanged.connect(
            lambda: config.set_default_provider(self.combo_engine.currentData()))
        engine_row.addWidget(lbl)
        engine_row.addWidget(self.combo_engine, 1)
        lay.addLayout(engine_row)

        # 参考题库
        self.chk_bank = QCheckBox("参考我的题库（自动用 DeepSeek 深度搜索）")
        self.chk_bank.setChecked(False)
        lay.addWidget(self.chk_bank)

        # 自动复制
        self.chk_copy = QCheckBox("搜题结果自动复制到剪贴板")
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
        self.tray.setToolTip("悬屏搜题")
        menu = QMenu()
        act_show = QAction("显示挂件", self)
        act_show.triggered.connect(self._show_widget)
        act_select = QAction("框选搜题", self)
        act_select.triggered.connect(self._on_select)
        act_clear = QAction("清除所有结果卡片", self)
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
        p.drawText(pm.rect(), Qt.AlignCenter, "题")
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
        fs = is_fullscreen_foreground()
        log(f"热键触发: is_fullscreen={fs}")
        if fs and config.get_game_mode() == "fullscreen":
            self.manager.solve_fullscreen()
            return
        self._was_visible = self.isVisible()
        self.hide()
        if fs:
            self.manager.start_game_selection()
        else:
            self.manager.start_selection()

    def _restore_widget(self):
        if self._was_visible and not self.isVisible():
            self.show()
            self.raise_()

    def _on_game_solved(self, text):
        preview = " ".join(text.split())[:80]
        self.tray.showMessage("搜题完成（已复制）", preview,
                              QSystemTrayIcon.Information, 4000)

    def _on_game_solve_failed(self, msg):
        self.tray.showMessage("搜题失败", msg, QSystemTrayIcon.Warning, 3000)

    def _setup_hotkey(self):
        self._hotkey = None
        try:
            from .hotkey import GlobalHotkey
            self._hotkey = GlobalHotkey(self._on_select)
            self._hotkey.register()
            QApplication.instance().installNativeEventFilter(self._hotkey.filter)
        except Exception as e:  # noqa: BLE001
            print(f"[提示] 全局快捷键注册失败：{e}")

    def _open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()

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
