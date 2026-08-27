"""搜题结果展示：小卡片 ↔ 完整面板（同一窗口双形态）+ 加条件重搜 + 选模型重搜。

- 小卡片：置顶悬浮，截图缩略图 + 答案摘要 + 操作按钮，可拖拽
- 完整面板：同一窗口展开（左右分栏：左大图、右全文），右上角 □/▣ 切换
- 加条件重搜：OCR 不准或需求变化时，改题目 / 附加要求（如「改用 Python 写」）
- 修改模型重搜：弹窗选择 DeepSeek 模型后用该模型重新搜题
"""
from PySide6.QtCore import Qt, QRect, QRectF, QSize, Signal, QEvent, QTimer
from PySide6.QtGui import (QPixmap, QImage, QPainter, QPen, QIcon, QColor)
from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QTextBrowser, QPlainTextEdit,
                               QComboBox, QSplitter, QScrollArea)

MIN_W = 260
MAX_PREVIEW_CHARS = 500  # 小卡片答案摘要字数
STREAM_RENDER_MS = 120   # 流式输出渲染节流（毫秒）


def _win_icon(kind: str, color: str) -> QIcon:
    """自绘 Windows 风格窗口按钮图标（最大化=单框；还原=两框对角重叠）。

    字体字符做不出一模一样的还原符号，用 QPainter 描边画，和 Windows
    标题栏最大化/还原按钮的图案一致。
    """
    pm = QPixmap(16, 16)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.4)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    if kind == "max":
        # 最大化：单个方框
        p.drawRect(QRectF(2.0, 2.0, 12.0, 12.0))
    else:
        # 还原：两个同尺寸方框，左下框 + 右上框对角重叠（同 Windows 还原图标）
        p.drawRect(QRectF(2.0, 6.5, 9.5, 9.5))   # 左下框（下层）
        p.drawRect(QRectF(6.5, 2.0, 9.5, 9.5))   # 右上框（上层）
    p.end()
    return QIcon(pm)


# ---------------------------------------------------------------- 加条件重搜
class EditQuestionDialog(QDialog):
    """调整题目文本 + 附加搜题要求（如「改用 Python 实现」）。"""

    def __init__(self, question: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("调整题目 / 添加要求后重搜")
        self.setMinimumSize(540, 400)
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
        lay.setSpacing(8)

        # 置顶：卡片本身是 WindowStaysOnTopHint 窗口，对话框必须显式置顶，
        # 否则会被卡片压到下面（模态下看不见=卡死）
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        lay.addWidget(QLabel("① 题目文本（OCR 识别可能有错，可直接修改）："))
        self._edit = QPlainTextEdit(question)
        self._edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        lay.addWidget(self._edit, 3)

        lay.addWidget(QLabel("② 附加要求（可选，AI 会按新要求做题。例：老师要求用 Python，不要用 Java）："))
        self._cond_edit = QPlainTextEdit()
        self._cond_edit.setPlaceholderText("例：这道题老师要求用 Python 写，请按 Python 给出代码和步骤")
        self._cond_edit.setFixedHeight(64)
        lay.addWidget(self._cond_edit)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_go = QPushButton("按新条件重搜")
        btn_go.setObjectName("primary")
        btn_go.clicked.connect(self.accept)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_go)
        lay.addLayout(btns)
        self._edit.setFocus()

    def question_text(self) -> str:
        return self._edit.toPlainText().strip()

    def condition_text(self) -> str:
        return self._cond_edit.toPlainText().strip()


# ---------------------------------------------------------------- 选模型重搜
class ModelSelectDialog(QDialog):
    """选择模型重新搜题。"""

    def __init__(self, current_model: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择模型重新搜题")
        self.setMinimumWidth(440)
        self.setStyleSheet("""
            QDialog { background-color: #23262e; }
            QLabel { color: #c3c6cd; font-size: 12px; }
            QComboBox { background: #1b1e24; color: #eee; border: 1px solid #3a3d46;
                        border-radius: 6px; padding: 6px 10px; font-size: 13px; }
            QComboBox QAbstractItemView { background: #1b1e24; color: #eee;
                                          selection-background-color: #2f7bff; }
            QPushButton { background: #2c2f37; color: #eee; border: 1px solid #444;
                          border-radius: 6px; padding: 7px 20px; font-size: 13px; }
            QPushButton:hover { background: #3a3d46; }
            QPushButton#primary { background: #2f7bff; color: white; border: none; font-weight: bold; }
            QPushButton#primary:hover { background: #3f8aff; }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        # 置顶：卡片本身是 WindowStaysOnTopHint 窗口，对话框必须显式置顶，
        # 否则会被卡片压到下面（模态下看不见=卡死）
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        lay.addWidget(QLabel("选择模型后用该模型重新搜这道题："))

        from . import config
        self._combo = QComboBox()
        for display, m in config.DEEPSEEK_MODELS:
            self._combo.addItem(display, m)
        idx = self._combo.findData(current_model)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)
        lay.addWidget(self._combo)

        tip = QLabel("flash 快且便宜（日常）；pro 更强更准（难题）；"
                     "vision 适合直接看图片（本工具走 OCR 文字，一般用不到）")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #7f8593; font-size: 11px;")
        lay.addWidget(tip)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_go = QPushButton("用此模型重搜")
        btn_go.setObjectName("primary")
        btn_go.clicked.connect(self.accept)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_go)
        lay.addLayout(btns)

    def selected_model(self) -> str:
        return self._combo.currentData()


# ---------------------------------------------------------------- 结果卡片
class ResultCard(QWidget):
    """搜题结果卡片：小卡片 ↔ 完整面板同一窗口双形态，可拖动。

    右上角 □ 展开 / ▣ 收起（同 Windows 最大化按钮位置），展开态左右分栏：
    左=大截图（可滚动），右=完整答案（可选中复制）+ 操作按钮。
    """

    # 重搜请求信号： (题目文本, 模型名)；模型名为空=按当前默认引擎
    resolve_requested = Signal(str, str)
    # 看图直搜信号： (QImage, 视觉模型名) —— 把原图直接发给视觉模型解题，跳过 OCR
    vision_solve_requested = Signal(object, str)

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
        self._expanded = False
        # 流式输出状态（边生成边显示）
        self._streaming = False
        self._pending = ""
        self._last_flushed = ""
        self._flush_queued = False
        # 窗口按钮图标（Windows 风格，normal/hover 两色 × 最大化/还原）
        self._hovered = False
        self._icon_max = _win_icon("max", "#d8dce2")
        self._icon_max_light = _win_icon("max", "#ffffff")
        self._icon_restore = _win_icon("restore", "#d8dce2")
        self._icon_restore_light = _win_icon("restore", "#ffffff")
        self._build_ui()
        self._install_drag()
        self._update_expand_icon()

    def _update_expand_icon(self):
        """按当前形态 + hover 状态切换右上角按钮图标（Windows 同款）。"""
        if self._expanded:
            self.btn_expand.setIcon(self._icon_restore_light if self._hovered else self._icon_restore)
        else:
            self.btn_expand.setIcon(self._icon_max_light if self._hovered else self._icon_max)

    # ---------- 构建 ----------
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
            QTextBrowser#full { background: #1b1e24; color: #eee; border: 1px solid #3a3d46;
                                border-radius: 8px; padding: 10px; font-size: 14px; }
            QScrollArea#shot_scroll { background: #1b1e24; border: 1px solid #3a3d46;
                                      border-radius: 8px; }
            QPushButton#tool { background: #2c2f37; color: #ddd; border: 1px solid #41454f;
                               border-radius: 6px; padding: 4px 10px; font-size: 12px; }
            QPushButton#tool:hover { background: #3a3d46; }
            QPushButton#deep { background: #7a5af8; color: white; border: none;
                               border-radius: 6px; padding: 4px 10px; font-size: 12px; }
            QPushButton#deep:hover { background: #8a6aff; }
            QPushButton#close_btn { background: transparent; border: none; color: #c7c9d1;
                                    font-size: 15px; }
            QPushButton#close_btn:hover { color: #ff5b5b; }
        """)
        outer.addWidget(self._panel)
        lay = QVBoxLayout(self._panel)
        lay.setContentsMargins(10, 6, 10, 10)
        lay.setSpacing(6)

        # ---- 顶栏：meta + 展开/收起 + 关闭（右上角，类 Windows） ----
        top = QHBoxLayout()
        self._meta_label = QLabel("")
        self._meta_label.setObjectName("meta")
        self._meta_label.setWordWrap(True)
        self.btn_expand = QPushButton()
        self.btn_expand.setObjectName("close_btn")
        self.btn_expand.setFixedSize(24, 24)
        self.btn_expand.setIconSize(QSize(16, 16))
        self.btn_expand.setCursor(Qt.PointingHandCursor)
        self.btn_expand.setAttribute(Qt.WA_Hover, True)  # 保证 HoverEnter/Leave 事件
        self.btn_expand.setToolTip("展开完整面板")
        self.btn_expand.clicked.connect(self._toggle_panel)
        btn_close = QPushButton("✕")
        btn_close.setObjectName("close_btn")
        btn_close.setFixedSize(24, 24)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setToolTip("关闭（拖拽卡片可移动）")
        btn_close.clicked.connect(self.close)
        top.addWidget(self._meta_label, 1)
        top.addWidget(self.btn_expand, 0, Qt.AlignTop)
        top.addWidget(btn_close, 0, Qt.AlignTop)
        lay.addLayout(top)

        self._all_buttons = []       # 受「搜题中禁用」控制的按钮
        self._always_buttons = []    # 任何时候可用的按钮

        # ---- 紧凑容器（小卡片形态） ----
        self._compact = QWidget()
        cl = QVBoxLayout(self._compact)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(6)

        self._shot_label = QLabel()
        self._shot_label.setAlignment(Qt.AlignCenter)
        if self._image and not self._image.isNull():
            pm = QPixmap.fromImage(self._image).scaled(
                360, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._shot_label.setPixmap(pm)
        cl.addWidget(self._shot_label)

        self._status_label = QLabel("识别中…")
        self._status_label.setObjectName("status")
        self._status_label.setWordWrap(True)
        cl.addWidget(self._status_label)

        self._browser = QTextBrowser()
        self._browser.setObjectName("preview")
        self._browser.setMaximumHeight(160)
        self._browser.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self._browser.hide()
        cl.addWidget(self._browser)

        cl.addLayout(self._make_btns_row())
        lay.addWidget(self._compact)

        # ---- 展开容器（完整面板形态：左右分栏） ----
        self._expanded_w = QWidget()
        self._expanded_w.hide()
        el = QVBoxLayout(self._expanded_w)
        el.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal, self._expanded_w)
        # 左：大截图（可滚动）
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("shot_scroll")
        scroll.setWidgetResizable(True)
        self._big_shot = QLabel()
        self._big_shot.setAlignment(Qt.AlignCenter)
        if self._image and not self._image.isNull():
            pm = QPixmap.fromImage(self._image).scaled(
                560, 520, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._big_shot.setPixmap(pm)
        scroll.setWidget(self._big_shot)
        ll.addWidget(scroll, 1)
        splitter.addWidget(left)

        # 右：状态 + 完整答案 + 按钮
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 0, 0, 0)
        rl.setSpacing(6)
        self._exp_status = QLabel("")
        self._exp_status.setObjectName("status")
        self._exp_status.setWordWrap(True)
        rl.addWidget(self._exp_status)
        self._exp_browser = QTextBrowser()
        self._exp_browser.setObjectName("full")
        self._exp_browser.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        rl.addWidget(self._exp_browser, 1)
        rl.addLayout(self._make_btns_row())
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        el.addWidget(splitter, 1)
        lay.addWidget(self._expanded_w, 1)

        self._set_buttons_enabled(False)

    def _make_btns_row(self):
        """构建一行操作按钮，登记到统一启用/禁用管理。"""
        row = QHBoxLayout()
        row.setSpacing(6)

        btn_cond = QPushButton("加条件重搜")
        btn_cond.setObjectName("tool")
        btn_cond.setCursor(Qt.PointingHandCursor)
        btn_cond.setToolTip("改题目 / 给 AI 附加要求（如：改用 Python 写）后重新搜题")
        btn_cond.clicked.connect(self._ask_condition)
        row.addWidget(btn_cond)
        self._always_buttons.append(btn_cond)

        btn_model = QPushButton("修改模型重搜")
        btn_model.setObjectName("deep")
        btn_model.setCursor(Qt.PointingHandCursor)
        btn_model.setToolTip("选择 DeepSeek 模型（flash/pro/vision）后重新搜题")
        btn_model.clicked.connect(self._choose_model)
        row.addWidget(btn_model)
        self._all_buttons.append(btn_model)

        btn_vision = QPushButton("看图直搜")
        btn_vision.setObjectName("deep")
        btn_vision.setCursor(Qt.PointingHandCursor)
        btn_vision.setToolTip("把截图原图直接发给 DeepSeek 视觉模型解题，跳过 OCR（左题设/右代码也能看准）")
        btn_vision.clicked.connect(self._vision_search)
        row.addWidget(btn_vision)
        self._always_buttons.append(btn_vision)
        return row

    def _set_buttons_enabled(self, enabled: bool):
        for b in self._all_buttons:
            b.setEnabled(enabled)
        for b in self._always_buttons:
            b.setEnabled(True)

    def _resize_to_fit(self):
        if self._expanded:
            return  # 展开态尺寸由 _toggle_panel 管理
        self.adjustSize()
        hint = self.sizeHint()
        self.resize(max(MIN_W, hint.width()),
                    min(560, hint.height()))

    # ---------- 状态更新（由 manager 调用） ----------
    def set_solving(self, provider_name: str):
        msg = f"搜题中（{provider_name}）…"
        self._status_label.setText(msg)
        self._exp_status.setText(msg)
        self._meta_label.setText("")
        # 新一次搜题：重置流式状态，清掉旧内容
        self._streaming = False
        self._pending = ""
        self._last_flushed = ""
        self._flush_queued = False
        self._browser.setMarkdown("")
        self._exp_browser.setMarkdown("")
        self._browser.hide()
        self._resize_to_fit()

    def set_result(self, question: str, answer: str, engine_name: str, model: str):
        self._question = question
        self._answer = answer
        self._engine_name = engine_name
        self._model = model
        # 停止流式渲染
        self._streaming = False
        self._pending = ""
        self._last_flushed = ""
        self._flush_queued = False
        self._meta_label.setText(f"{engine_name} · {model}")
        self._status_label.setText("题目：")
        self._exp_status.setText("题目：")
        self._browser.setMarkdown(self._preview_text())
        self._browser.show()
        self._exp_browser.setMarkdown(answer)
        self._set_buttons_enabled(True)
        self._resize_to_fit()

    # ---------- 流式输出（边生成边显示，体感提速） ----------
    def append_answer(self, delta: str):
        """AI 流式输出的增量文本；节流合并渲染，避免每个 token 全量重绘。"""
        if not delta:
            return
        if not self._streaming:
            self._streaming = True
            self._pending = ""
            self._last_flushed = ""
            self._status_label.setText("AI 生成中…")
            self._exp_status.setText("AI 生成中…")
        self._pending += delta
        if not self._flush_queued:
            self._flush_queued = True
            QTimer.singleShot(STREAM_RENDER_MS, self._flush_stream)

    def _flush_stream(self):
        """节流渲染：把累积的流式文本刷到两个浏览器。"""
        self._flush_queued = False
        if not self._streaming or self._pending == self._last_flushed:
            return
        self._last_flushed = self._pending
        self._browser.setMarkdown(self._pending)
        self._exp_browser.setMarkdown(self._pending)
        for b in (self._browser, self._exp_browser):
            sb = b.verticalScrollBar()
            sb.setValue(sb.maximum())

    def set_error(self, msg: str):
        self._meta_label.setText("")
        self._status_label.setText(f"⚠ {msg}")
        self._exp_status.setText(f"⚠ {msg}")
        self._resize_to_fit()

    def _preview_text(self) -> str:
        """小卡片摘要：答案超过 500 字时截断并提示。"""
        if not self._answer:
            return ""
        if len(self._answer) > MAX_PREVIEW_CHARS:
            return self._answer[:MAX_PREVIEW_CHARS] + "\n\n…（点右上角 □ 看完整内容）"
        return self._answer

    # ---------- 动作 ----------
    def _ask_condition(self):
        """改题目 / 附加要求（如「改用 Python 写」）后重搜。"""
        dlg = EditQuestionDialog(self._question or "（未识别到题目文字，可直接输入）",
                                 parent=self)
        if dlg.exec() == QDialog.Accepted:
            q = dlg.question_text()
            cond = dlg.condition_text()
            if cond:
                q = f"{q}\n\n（附加要求：{cond}）" if q else f"（附加要求：{cond}）"
            if q:
                self._request_resolve(q, "")

    def _choose_model(self):
        """弹窗选择模型，用所选模型重搜。"""
        from . import config
        dlg = ModelSelectDialog(current_model=self._model or config.get_deepseek_model(),
                                parent=self)
        if dlg.exec() == QDialog.Accepted:
            model = dlg.selected_model()
            if model:
                self._request_resolve(self._question or "（未识别到题目文字）", model)

    def _request_resolve(self, question: str, model: str = ""):
        """向 manager 请求重搜。model 非空时用该 DeepSeek 模型。"""
        self.resolve_requested.emit(question, model)

    def _vision_search(self):
        """「看图直搜」：把原图直接发给 DeepSeek 视觉模型解题，跳过 OCR。

        看图必须用视觉模型：若当前设置的模型不含 vision，强制用视觉默认模型。
        """
        from . import engines, config
        model = config.get_deepseek_model() or ""
        if "vision" not in model and "vis" not in model:
            model = engines.DEFAULT_VISION_MODEL
        self.vision_solve_requested.emit(self._image, model)

    # ---------- 形态切换 ----------
    def _toggle_panel(self):
        """同一窗口在「小卡片 / 完整面板」两种形态间切换（无模态、可拖动）。"""
        self._expanded = not self._expanded
        if self._expanded:
            self._compact.hide()
            self._expanded_w.show()
            self.btn_expand.setToolTip("收起为小卡片")
            if self._image and not self._image.isNull():
                pm = QPixmap.fromImage(self._image).scaled(
                    560, 520, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._big_shot.setPixmap(pm)
            if self._answer:
                self._exp_browser.setMarkdown(self._answer)
            self.resize(960, 620)
            self._clamp_to_screen()
        else:
            self._expanded_w.hide()
            self._compact.show()
            self.btn_expand.setToolTip("展开完整面板")
            if self._answer:
                self._browser.setMarkdown(self._preview_text())
            self._resize_to_fit()
        self._update_expand_icon()

    def _clamp_to_screen(self):
        """展开后若超出屏幕工作区，夹回可见范围。"""
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().availableGeometry()
        geo = self.geometry()
        x = min(max(geo.x(), screen.left()), screen.right() - geo.width() + 1)
        y = min(max(geo.y(), screen.top()), screen.bottom() - geo.height() + 1)
        self.move(x, y)

    # ---------- 拖拽 ----------
    def _install_drag(self):
        for w in (self, self._panel, self._meta_label, self._shot_label,
                  self._status_label, self._big_shot, self._exp_status,
                  self.btn_expand):
            w.installEventFilter(self)

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.HoverEnter:
            self._hovered = True
            self._update_expand_icon()
            return False
        if t == QEvent.HoverLeave:
            self._hovered = False
            self._update_expand_icon()
            return False
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
