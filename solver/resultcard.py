"""搜题结果展示：小卡片 + 放大面板 + 修改题目重搜对话框。

- 小卡片：置顶悬浮，截图缩略图 + 答案摘要 + 操作按钮，可拖拽
- 放大面板：左侧大截图、右侧完整答案（QTextBrowser 可部分选中复制）
- 修改重搜：OCR 识别不准时，编辑题目文本重新搜
"""
from PySide6.QtCore import Qt, QRect, Signal, QEvent
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QTextBrowser, QPlainTextEdit,
                               QSplitter, QScrollArea)

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


# ---------------------------------------------------------------- 放大面板
class ResultPanel(QDialog):
    """放大完整面板：左侧原截图、右侧完整答案（可选中复制）。"""

    def __init__(self, image: QImage, question: str, answer: str,
                 engine_name: str, model: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("搜题结果")
        self.setMinimumSize(860, 560)
        self.resize(960, 620)
        self.setStyleSheet("""
            QDialog { background-color: #23262e; }
            QLabel { color: #c3c6cd; font-size: 12px; }
            QTextBrowser { background: #1b1e24; color: #eee; border: 1px solid #3a3d46;
                           border-radius: 8px; padding: 10px; font-size: 14px; }
            QPushButton { background: #2c2f37; color: #eee; border: 1px solid #444;
                          border-radius: 6px; padding: 7px 16px; font-size: 13px; }
            QPushButton:hover { background: #3a3d46; }
        """)
        self._image = image
        self._question = question
        self._answer = answer

        splitter = QSplitter(Qt.Horizontal, self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addWidget(splitter, 1)

        # 左：截图（可滚动）
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        head = QLabel(f"题目截图（{engine_name} · {model}）")
        left_lay.addWidget(head)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: #1b1e24; border: 1px solid #3a3d46; border-radius: 8px; }")
        shot = QLabel()
        shot.setAlignment(Qt.AlignCenter)
        pm = QPixmap.fromImage(self._image) if self._image and not self._image.isNull() else QPixmap()
        if not pm.isNull():
            scaled = pm.scaled(520, 520, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            shot.setPixmap(scaled)
        scroll.setWidget(shot)
        left_lay.addWidget(scroll, 1)
        splitter.addWidget(left)

        # 右：答案（可选中复制）
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(8, 0, 0, 0)
        self._browser = QTextBrowser()
        self._browser.setMarkdown(self._answer)
        self._browser.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        right_lay.addWidget(self._browser, 1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btn_copy = QPushButton("复制全部")
        btn_copy.clicked.connect(self._copy_all)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        btns.addWidget(btn_copy)
        btns.addWidget(btn_close)
        right_lay.addLayout(btns)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

    def _copy_all(self):
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(self._answer)


# ---------------------------------------------------------------- 小卡片
class ResultCard(QWidget):
    """搜题结果小卡片：截图缩略图 + 答案摘要 + 操作按钮。"""

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
        self.btn_enlarge.setToolTip("打开完整面板（可部分选中复制）")
        self.btn_enlarge.clicked.connect(self._open_panel)
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
        self._browser.setMarkdown(answer[:MAX_PREVIEW_CHARS] +
                                  ("\n\n…（更多见「放大」）" if len(answer) > MAX_PREVIEW_CHARS else ""))
        self._browser.show()
        self._set_buttons_enabled(True)
        self._resize_to_fit()

    def set_error(self, msg: str):
        self._meta_label.setText("")
        self._status_label.setText(f"⚠ {msg}")
        self._resize_to_fit()

    # ---------- 动作 ----------
    def _copy_all(self):
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(self._answer or self._question)

    def _open_panel(self):
        dlg = ResultPanel(self._image, self._question, self._answer,
                          self._engine_name, self._model)
        dlg.exec()

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
