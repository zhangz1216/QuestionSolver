"""设置对话框：双引擎 API Key、模型、默认引擎、历史、提示音等。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QCheckBox, QRadioButton, QPushButton, QGroupBox,
                               QLineEdit, QComboBox, QMessageBox)

from . import config
from .engines import FREE_PROVIDERS, probe_free_engine, EngineError
from .engines.deepseek import verify_key as verify_deepseek_key


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumWidth(460)
        self.setStyleSheet("""
            QDialog { background-color: #23262e; }
            QLabel { color: #c3c6cd; font-size: 12px; }
            QLabel#hint { color: #7d828c; font-size: 11px; }
            QLineEdit, QComboBox { background: #1b1e24; color: #eee;
                                   border: 1px solid #3a3d46; border-radius: 6px;
                                   padding: 5px 8px; font-size: 13px; }
            QCheckBox, QRadioButton { color: #e8e8e8; font-size: 13px; spacing: 8px; }
            QGroupBox { color: #9aa0aa; font-size: 12px; border: 1px solid #3a3d46;
                        border-radius: 8px; margin-top: 10px; padding-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QPushButton { background: #2c2f37; color: #eee; border: 1px solid #444;
                          border-radius: 6px; padding: 7px 20px; font-size: 13px; }
            QPushButton:hover { background: #3a3d46; }
            QPushButton#primary { background: #2f7bff; color: white; border: none; font-weight: bold; }
            QPushButton#primary:hover { background: #3f8aff; }
            QPushButton#probe { background: #7a5af8; color: white; border: none; }
            QPushButton#probe:hover { background: #8a6aff; }
        """)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        # ---------- 引擎 ----------
        engine_box = QGroupBox("搜题引擎")
        engine_lay = QVBoxLayout(engine_box)

        # 默认引擎
        default_row = QHBoxLayout()
        default_row.addWidget(QLabel("默认引擎："))
        self.combo_default = QComboBox()
        self.combo_default.addItem("免费引擎（省钱，简单题）", "free")
        self.combo_default.addItem("DeepSeek（付费，更准）", "deepseek")
        idx = self.combo_default.findData(config.get_default_provider())
        if idx >= 0:
            self.combo_default.setCurrentIndex(idx)
        default_row.addWidget(self.combo_default, 1)
        engine_lay.addLayout(default_row)

        # 免费平台
        free_row = QHBoxLayout()
        free_row.addWidget(QLabel("免费平台："))
        self.combo_free_provider = QComboBox()
        for pid, (name, _u, _m) in FREE_PROVIDERS.items():
            self.combo_free_provider.addItem(name, pid)
        pi = self.combo_free_provider.findData(config.get_free_provider())
        if pi >= 0:
            self.combo_free_provider.setCurrentIndex(pi)
        free_row.addWidget(self.combo_free_provider, 1)
        engine_lay.addLayout(free_row)

        # 免费 key
        free_key_row = QHBoxLayout()
        free_key_row.addWidget(QLabel("免费平台 Key："))
        self.edit_free_key = QLineEdit(config.get_free_key())
        self.edit_free_key.setEchoMode(QLineEdit.Password)
        self.edit_free_key.setPlaceholderText("免费注册：智谱 open.bigmodel.cn 或 硅基流动 cloud.siliconflow.cn")
        free_key_row.addWidget(self.edit_free_key, 1)
        engine_lay.addLayout(free_key_row)

        probe_row = QHBoxLayout()
        self.btn_probe = QPushButton("探测免费引擎可用性")
        self.btn_probe.setObjectName("probe")
        self.btn_probe.setCursor(Qt.PointingHandCursor)
        self.btn_probe.clicked.connect(self._on_probe)
        probe_row.addWidget(self.btn_probe)
        probe_row.addStretch(1)
        engine_lay.addLayout(probe_row)

        # DeepSeek key
        ds_key_row = QHBoxLayout()
        ds_key_row.addWidget(QLabel("DeepSeek Key："))
        self.edit_ds_key = QLineEdit(config.get_deepseek_key())
        self.edit_ds_key.setEchoMode(QLineEdit.Password)
        self.edit_ds_key.setPlaceholderText("platform.deepseek.com 获取")
        ds_key_row.addWidget(self.edit_ds_key, 1)
        engine_lay.addLayout(ds_key_row)

        # DeepSeek 模型
        ds_model_row = QHBoxLayout()
        ds_model_row.addWidget(QLabel("DeepSeek 模型："))
        self.combo_ds_model = QComboBox()
        for label, code in config.DEEPSEEK_MODELS:
            self.combo_ds_model.addItem(label, code)
        mi = self.combo_ds_model.findData(config.get_deepseek_model())
        if mi >= 0:
            self.combo_ds_model.setCurrentIndex(mi)
        ds_model_row.addWidget(self.combo_ds_model, 1)
        engine_lay.addLayout(ds_model_row)

        # DeepSeek Key 验证
        ds_probe_row = QHBoxLayout()
        self.btn_ds_probe = QPushButton("验证 DeepSeek Key")
        self.btn_ds_probe.setObjectName("probe")
        self.btn_ds_probe.setCursor(Qt.PointingHandCursor)
        self.btn_ds_probe.clicked.connect(self._on_probe_ds)
        ds_probe_row.addWidget(self.btn_ds_probe)
        ds_probe_row.addStretch(1)
        engine_lay.addLayout(ds_probe_row)
        lay.addWidget(engine_box)

        # ---------- 行为 ----------
        self.chk_copy = QCheckBox("搜题结果自动复制到剪贴板")
        self.chk_copy.setChecked(config.get_auto_copy())
        lay.addWidget(self.chk_copy)

        self.chk_history = QCheckBox("自动保存搜题记录（历史收藏夹）")
        self.chk_history.setChecked(config.get_save_history())
        lay.addWidget(self.chk_history)

        self.chk_alert = QCheckBox("搜题完成时播放提示音")
        self.chk_alert.setChecked(config.get_alert_enabled())
        lay.addWidget(self.chk_alert)

        box = QGroupBox("全屏应用内按快捷键")
        box_lay = QVBoxLayout(box)
        self.radio_select = QRadioButton("框选搜题（切回桌面显示结果卡片）")
        self.radio_fullscreen = QRadioButton("截全屏搜题（结果进剪贴板，不打断）")
        mode = config.get_game_mode()
        if mode == "fullscreen":
            self.radio_fullscreen.setChecked(True)
        else:
            self.radio_select.setChecked(True)
        box_lay.addWidget(self.radio_select)
        box_lay.addWidget(self.radio_fullscreen)
        lay.addWidget(box)

        hint = QLabel("Key 仅保存在本机。免费平台需注册（免费），DeepSeek 需充值。")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

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

    def _on_probe(self):
        key = self.edit_free_key.text().strip()
        if not key:
            QMessageBox.warning(self, "提示",
                                "请先在「免费平台 Key」填写免费平台的 Key（智谱/硅基流动注册）。\n"
                                "注意：DeepSeek 的 Key 不通用，需在「DeepSeek Key」里填写，"
                                "并点下面的「验证 DeepSeek Key」。")
            return
        self.btn_probe.setEnabled(False)
        self.btn_probe.setText("探测中…")
        try:
            result = probe_free_engine(key)
            provider = result["provider"]
            self.combo_free_provider.setCurrentIndex(
                self.combo_free_provider.findData(provider))
            QMessageBox.information(self, "探测成功",
                                    f"{result['display']} 可用，已自动选中该平台。\n"
                                    f"免费 Key 已保存，搜题时用这个引擎。")
            config.set_free_key(key)
            config.set_free_provider(provider)
        except EngineError as e:
            QMessageBox.warning(self, "探测失败", str(e))
        finally:
            self.btn_probe.setEnabled(True)
            self.btn_probe.setText("探测免费引擎可用性")

    def _on_probe_ds(self):
        """验证 DeepSeek Key：GET /models，不消耗 token。"""
        key = self.edit_ds_key.text().strip()
        if not key:
            QMessageBox.warning(self, "提示",
                                "请先在「DeepSeek Key」填写 platform.deepseek.com 获取的 Key。")
            return
        self.btn_ds_probe.setEnabled(False)
        self.btn_ds_probe.setText("验证中…")
        try:
            models = verify_deepseek_key(key)
            config.set_deepseek_key(key)
            names = "、".join(models[:4]) if models else "（接口未返回模型列表）"
            QMessageBox.information(self, "验证成功",
                                    f"Key 有效！可用模型：{names}\n\n"
                                    f"DeepSeek Key 已保存，搜题时选 DeepSeek 引擎即可使用。")
        except EngineError as e:
            QMessageBox.warning(self, "验证失败", str(e))
        finally:
            self.btn_ds_probe.setEnabled(True)
            self.btn_ds_probe.setText("验证 DeepSeek Key")

    def _save(self):
        config.set_default_provider(self.combo_default.currentData())
        config.set_free_key(self.edit_free_key.text())
        config.set_free_provider(self.combo_free_provider.currentData())
        config.set_deepseek_key(self.edit_ds_key.text())
        config.set_deepseek_model(self.combo_ds_model.currentData())
        config.set_auto_copy(self.chk_copy.isChecked())
        config.set_save_history(self.chk_history.isChecked())
        config.set_alert_enabled(self.chk_alert.isChecked())
        mode = "fullscreen" if self.radio_fullscreen.isChecked() else "select"
        config.set_game_mode(mode)
        self.accept()
