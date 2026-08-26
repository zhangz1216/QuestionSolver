"""搜题结果展示：小卡片 + 放大面板 + 修改题目重搜对话框。

- 小卡片：置顶悬浮，截图缩略图 + 答案摘要 + 操作按钮，可拖拽
- 放大面板：左侧大截图、右侧完整答案（QTextBrowser 可部分选中复制）
- 修改重搜：OCR 识别不准时，编辑题目文本重新搜
"""
from PySide6.QtCore import Qt, QRect, Signal, QEvent
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QTextBrowser, QPlainTextEdit)

MIN_W = 260
MAX_PREVIEW_CHARS = 500  # 小卡片答案摘要字数


# ---------------------------------------------------------------- 修改重搜
class EditQuestionDialog(QDialog):
    """显示 OCR 识别出的题目文本，允许修改后重新搜题。"""

    def __init__(self, question: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("修改题目后重新搜题")
        self.setMinimumSize(480, 320)
        self.setStyleSheet("""
            QDialog { background-color: #23262e; }
            QLabel { color: #c3c6cd; font-size: 12px; }
            QPlainTextEdit { background: #1b1e24; color: #eee; border: 1px solid #3a3d46;
                             border-radius: 8px; padding: 8px; font-size: 13px; }
            QPushButton { background: #2c2f37; color: #eee; border: 1px solid #444;
                          border-radius: 6px; padding: 7px 20px; font-size: 13px; }
            QPushButton:hover { background: #3a3d46; }
            QPushButton#primary { background: #2f7bff; color: white; border: none; font-weight: bold; }
            QPushButton#primary:hover { background: #3f8aff; }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        tip = QLabel("OCR 识别的题目可能有错（尤其公式），可直接修改：")
        lay.addWidget(tip)
        self._edit = QPlainTextEdit(question)
        self._edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        lay.addWidget(self._edit, 1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_go = QPushButton("重新搜题")
        btn_go.setObjectName("primary")
        btn_go.clicked.connect(self.accept)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_go)
        lay.addLayout(btns)
        self._edit.setFocus()

    def question_text(self) -> str:
        return self._edit.toPlainText().strip()


# ---------------------------------------------------------------- 小卡片
class ResultCard(QWidget):
    """搜题结果卡片：截图 + 答案 + 操作按钮，支持「小卡片 / 完整面板」双形态切换。

    展开形态与卡片是同一个无边框窗口（可拖动），不再弹模态面板，
    避免第二个窗口遮挡、锁死交互的问题。
    """

    # 重搜请求信号（交给 manager 处理，避免卡片里直接起线程）
    resolve_requested = Signal(str, bool)   # (题目文本, 是否用 DeepSeek 深度重搜)

    def __init__(self, rect: QRect, image: QImage):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setGeometry(rect)
        self._image = image
        self._question = ""
        self._answer = ""
        self._engine_name = ""
        self._model = ""
        self._drag_offset = None
        self._expanded = False          # False=小卡片 / True=完整面板（同一窗口）
        self._build_ui()
        self._install_drag()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._panel = QWidget(self)
        self._panel.setObjectName("panel")
        self._panel.setStyleSheet("""
            #panel { background-color: rgba(30, 32, 40, 240);
                     border: 1px solid rgba(255, 255, 255, 28);
                     border-radius: 10px; }
            QLabel#meta { color: #8f93a0; font-size: 11px; }
            QTextBrowser#preview { background: transparent; border: none; color: #e8e8e8;
                                   font-size: 13px; }
            QLabel#status { color: #c3c6cf; font-size: 12px; }
            QPushButton#tool { background: #2c2f37; color: #ddd; border: 1px solid #41454f;
                               border-radius: 6px; padding: 4px 10px; font-size: 12px; }
            QPushButton#tool:hover { background: #3a3d46; }
            QPushButton#deep { background: #7a5af8; color: white; border: none;
                               border-radius: 6px; padding: 4px 10px; font-size: 12px; }
            QPushButton#deep:hover { background: #8a6aff; }
            QPushButton#close_btn { background: transparent; border: none; color: #c7c9d1; font-size: 15px; }
            QPushButton#close_btn:hover { color: #ff5b5b; }
        """)
        outer.addWidget(self._panel)
        lay = QVBoxLayout(self._panel)
        lay.setContentsMargins(10, 6, 10, 10)
        lay.setSpacing(6)

        # 顶部：状态 + 关闭
        top = QHBoxLayout()
        self._meta_label = QLabel("")
        self._meta_label.setObjectName("meta")
        self._meta_label.setWordWrap(True)
        btn_close = QPushButton("✕")
        btn_close.setObjectName("close_btn")
        btn_close.setFixedSize(22, 22)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setToolTip("关闭（拖拽卡片可移动）")
        btn_close.clicked.connect(self.close)
        top.addWidget(self._meta_label, 1)
        top.addWidget(btn_close, 0, Qt.AlignTop)
        lay.addLayout(top)

        # 截图缩略图
        self._shot_label = QLabel()
        self._shot_label.setAlignment(Qt.AlignCenter)
        if self._image and not self._image.isNull():
            pm = QPixmap.fromImage(self._image).scaled(
                360, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._shot_label.setPixmap(pm)
        lay.addWidget(self._shot_label)

        # 状态 / 题目识别预览
        self._status_label = QLabel("识别中…")
        self._status_label.setObjectName("status")
        self._status_label.setWordWrap(True)
        lay.addWidget(self._status_label)

        # 答案预览（可选中复制）
        self._browser = QTextBrowser()
        self._browser.setObjectName("preview")
        self._browser.setMaximumHeight(160)
        self._browser.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self._browser.hide()
        lay.addWidget(self._browser)

        # 按钮行
        btns = QHBoxLayout()
        btns.setSpacing(6)
        self.btn_enlarge = QPushButton("放大")
        self.btn_enlarge.setObjectName("tool")
        self.btn_enlarge.setCursor(Qt.PointingHandCursor)
        self.btn_enlarge.setToolTip("展开完整面板（同一窗口切换形态，可部分选中复制）")
        self.btn_enlarge.clicked.connect(self._toggle_panel)
        self.btn_copy = QPushButton("复制")
        self.btn_copy.setObjectName("tool")
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.clicked.connect(self._copy_all)
        self.btn_fix = QPushButton("识别不准？改题重搜")
        self.btn_fix.setObjectName("tool")
        self.btn_fix.setCursor(Qt.PointingHandCursor)
        self.btn_fix.setToolTip("OCR 可能识别错（尤其公式），修改题目文本后重新搜题")
        self.btn_fix.clicked.connect(self._ask_edit)
        self.btn_deep = QPushButton("DeepSeek 深度重搜")
        self.btn_deep.setObjectName("deep")
        self.btn_deep.setCursor(Qt.PointingHandCursor)
        self.btn_deep.setToolTip("用 DeepSeek（付费）重新搜这道题，更准")
        self.btn_deep.clicked.connect(lambda: self._request_resolve(deep=True))
        for b in (self.btn_enlarge, self.btn_copy, self.btn_fix, self.btn_deep):
            btns.addWidget(b)
        lay.addLayout(btns)
        self._set_buttons_enabled(False)

    def _set_buttons_enabled(self, enabled: bool):
        for b in (self.btn_enlarge, self.btn_copy, self.btn_deep):
            b.setEnabled(enabled)
        self.btn_fix.setEnabled(True)  # 修改重搜任何时候都可用

    def _resize_to_fit(self):
        if self._expanded:
            return  # 展开态尺寸由 _toggle_panel 管理，防止被内容变化缩回小卡片
        self.adjustSize()
        hint = self.sizeHint()
        self.resize(max(MIN_W, hint.width()),
                    min(560, hint.height()))

    # ---------- 状态更新（由 manager 调用） ----------
    def set_solving(self, provider_name: str):
        self._status_label.setText(f"搜题中（{provider_name}）…")
        self._meta_label.setText("")
        self._resize_to_fit()

    def set_result(self, question: str, answer: str, engine_name: str, model: str):
        self._question = question
        self._answer = answer
        self._engine_name = engine_name
        self._model = model
        self._meta_label.setText(f"{engine_name} · {model} · 已复制到剪贴板" if False else f"{engine_name} · {model}")
        self._status_label.setText("题目：")
        self._browser.setMarkdown(self._answer if self._expanded else self._preview_text())
        self._browser.show()
        self._set_buttons_enabled(True)
        self._resize_to_fit()

    def _preview_text(self) -> str:
        """小卡片摘要：答案超过 500 字时截断并提示。"""
        if not self._answer:
            return ""
        if len(self._answer) > MAX_PREVIEW_CHARS:
            return self._answer[:MAX_PREVIEW_CHARS] + "\n\n…（点「放大」看完整内容）"
        return self._answer

    def set_error(self, msg: str):
        self._meta_label.setText("")
        self._status_label.setText(f"⚠ {msg}")
        self._resize_to_fit()

    # ---------- 动作 ----------
    def _copy_all(self):
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(self._answer or self._question)

    def _toggle_panel(self):
        """同一窗口在「小卡片 / 完整面板」两种形态间切换（无模态、可拖动）。"""
        self._expanded = not self._expanded
        if self._expanded:
            # ---- 展开为完整面板 ----
            self.btn_enlarge.setText("收起")
            self.btn_enlarge.setToolTip("收起为小卡片")
            if self._image and not self._image.isNull():
                pm = QPixmap.fromImage(self._image).scaled(
                    560, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._shot_label.setPixmap(pm)
            self._browser.setMaximumHeight(16777215)  # 不限高，显示全文
            if self._answer:
                self._browser.setMarkdown(self._answer)
            self.resize(920, 620)
            self._clamp_to_screen()
        else:
            # ---- 收起为小卡片 ----
            self.btn_enlarge.setText("放大")
            self.btn_enlarge.setToolTip("展开完整面板（同一窗口切换形态，可部分选中复制）")
            if self._image and not self._image.isNull():
                pm = QPixmap.fromImage(self._image).scaled(
                    360, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._shot_label.setPixmap(pm)
            self._browser.setMaximumHeight(160)
            if self._answer:
                self._browser.setMarkdown(self._preview_text())
            self._resize_to_fit()

    def _clamp_to_screen(self):
        """展开后若超出屏幕工作区，夹回可见范围。"""
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().availableGeometry()
        geo = self.geometry()
        x = min(max(geo.x(), screen.left()), screen.right() - geo.width() + 1)
        y = min(max(geo.y(), screen.top()), screen.bottom() - geo.height() + 1)
        self.move(x, y)

    def _ask_edit(self):
        dlg = EditQuestionDialog(self._question or "（未识别到题目文字，可直接输入）")
        if dlg.exec() == QDialog.Accepted:
            new_text = dlg.question_text()
            if new_text:
                self._request_resolve(deep=False, question_override=new_text)

    def _request_resolve(self, deep: bool, question_override: str = ""):
        """向 manager 请求重搜。deep=True 时走 DeepSeek。"""
        self.resolve_requested.emit(question_override or self._question, deep)

    # ---------- 拖拽 ----------
    def _install_drag(self):
        for w in (self, self._panel, self._meta_label, self._shot_label, self._status_label):
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
