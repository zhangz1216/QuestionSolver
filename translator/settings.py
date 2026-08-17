"""设置对话框：提示音开关、游戏内快捷键行为、自动复制等。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QCheckBox, QRadioButton, QPushButton, QGroupBox)

from . import config


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumWidth(380)
        self.setStyleSheet("""
            QDialog { background-color: #23262e; }
            QLabel { color: #c3c6cd; font-size: 12px; }
            QCheckBox { color: #e8e8e8; font-size: 13px; spacing: 8px; }
            QRadioButton { color: #e8e8e8; font-size: 13px; spacing: 8px; }
            QGroupBox { color: #9aa0aa; font-size: 12px; border: 1px solid #3a3d46;
                        border-radius: 8px; margin-top: 10px; padding-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QPushButton { background: #2c2f37; color: #eee; border: 1px solid #444;
                          border-radius: 6px; padding: 7px 20px; font-size: 13px; }
            QPushButton:hover { background: #3a3d46; }
            QPushButton#primary { background: #2f7bff; color: white; border: none; font-weight: bold; }
            QPushButton#primary:hover { background: #3f8aff; }
        """)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        # 提示音开关
        self.chk_alert = QCheckBox("翻译完成时播放提示音")
        self.chk_alert.setChecked(config.get_alert_enabled())
        lay.addWidget(self.chk_alert)

        # 游戏内快捷键行为
        box = QGroupBox("游戏内按快捷键")
        box_lay = QVBoxLayout(box)
        self.radio_select = QRadioButton("框选翻译（切回桌面显示截图+译文）")
        self.radio_fullscreen = QRadioButton("截全屏翻译（结果进剪贴板，不打断游戏）")
        mode = config.get_game_mode()
        if mode == "fullscreen":
            self.radio_fullscreen.setChecked(True)
        else:
            self.radio_select.setChecked(True)
        box_lay.addWidget(self.radio_select)
        box_lay.addWidget(self.radio_fullscreen)
        lay.addWidget(box)

        # 自动复制
        self.chk_copy = QCheckBox("翻译结果自动复制到剪贴板")
        self.chk_copy.setChecked(config.get_auto_copy())
        lay.addWidget(self.chk_copy)

        hint = QLabel("提示：游戏内选择「框选翻译」时，画面会切回桌面完成框选并显示结果。")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        # 按钮
        btns = QHBoxLayout()
        btns.addStretch(1)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("保存")
        btn_save.setObjectName("primary")
        btn_save.clicked.connect(self._save)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        lay.addLayout(btns)

    def _save(self):
        config.set_alert_enabled(self.chk_alert.isChecked())
        mode = "fullscreen" if self.radio_fullscreen.isChecked() else "select"
        config.set_game_mode(mode)
        config.set_auto_copy(self.chk_copy.isChecked())
        self.accept()
