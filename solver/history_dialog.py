"""历史收藏夹窗口：浏览搜题记录、查看详情、删除。"""
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QMessageBox, QTextBrowser, QSplitter,
                               QHeaderView, QAbstractItemView, QScrollArea)

from . import history


class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("历史收藏夹")
        self.setMinimumSize(820, 520)
        self.resize(900, 560)
        self.setStyleSheet("""
            QDialog { background-color: #23262e; }
            QLabel { color: #c3c6cd; font-size: 12px; }
            QTableWidget { background: #1b1e24; color: #e8e8e8; border: 1px solid #3a3d46;
                           border-radius: 8px; gridline-color: #2c2f37; font-size: 12px; }
            QHeaderView::section { background: #2c2f37; color: #c3c6cd; border: none;
                                   padding: 6px; font-size: 12px; }
            QTextBrowser { background: #1b1e24; color: #e8e8e8; border: 1px solid #3a3d46;
                           border-radius: 8px; padding: 8px; font-size: 13px; }
            QPushButton { background: #2c2f37; color: #eee; border: 1px solid #444;
                          border-radius: 6px; padding: 7px 16px; font-size: 13px; }
            QPushButton:hover { background: #3a3d46; }
            QPushButton#danger { color: #ff6b6b; }
            QPushButton#danger:hover { background: #3a2026; }
            QScrollArea { background: #1b1e24; border: 1px solid #3a3d46; border-radius: 8px; }
        """)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        splitter = QSplitter(Qt.Horizontal, self)
        lay.addWidget(splitter, 1)

        # 左：记录列表
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        head = QLabel("搜题记录（点击查看详情）")
        left_lay.addWidget(head)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["题目", "引擎", "时间", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.currentCellChanged.connect(self._on_select_row)
        self.table.doubleClicked.connect(self._on_select_row)
        left_lay.addWidget(self.table, 1)
        splitter.addWidget(left)

        # 右：详情
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(8, 0, 0, 0)
        right_lay.addWidget(QLabel("详情（文字可选中复制）"))
        self._shot_label = QLabel()
        self._shot_label.setAlignment(Qt.AlignCenter)
        self._shot_label.setVisible(False)
        right_lay.addWidget(self._shot_label)
        self._browser = QTextBrowser()
        self._browser.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        right_lay.addWidget(self._browser, 1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        btns = QHBoxLayout()
        btn_copy = QPushButton("复制当前答案")
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.clicked.connect(self._copy_current)
        btn_del = QPushButton("删除选中")
        btn_del.setObjectName("danger")
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.clicked.connect(self._delete_selected)
        btn_clear = QPushButton("清空全部")
        btn_clear.setObjectName("danger")
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.clicked.connect(self._clear_all)
        btns.addWidget(btn_copy)
        btns.addWidget(btn_del)
        btns.addWidget(btn_clear)
        btns.addStretch(1)
        btn_close = QPushButton("关闭")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        btns.addWidget(btn_close)
        lay.addLayout(btns)

    # ---------- 数据 ----------
    def _refresh(self):
        self._records = history.list_records()
        self.table.setRowCount(len(self._records))
        for row, r in enumerate(self._records):
            q = " ".join(r["question"].split())
            self.table.setItem(row, 0, QTableWidgetItem(q[:60] + ("…" if len(q) > 60 else "")))
            self.table.setItem(row, 1, QTableWidgetItem(f"{r['engine']}·{r['model']}"))
            self.table.setItem(row, 2, QTableWidgetItem(
                time.strftime("%m-%d %H:%M", time.localtime(r["created_at"]))))
            self.table.setItem(row, 3, QTableWidgetItem(""))
        self._browser.clear()
        self._shot_label.clear()
        self._shot_label.setVisible(False)

    def _current(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._records):
            return None
        return self._records[row]

    def _on_select_row(self, *_args):
        r = self._current()
        if r is None:
            return
        if r["image_path"]:
            pm = QPixmap(r["image_path"])
            if not pm.isNull():
                scaled = pm.scaled(300, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._shot_label.setPixmap(scaled)
                self._shot_label.setVisible(True)
        else:
            self._shot_label.clear()
            self._shot_label.setVisible(False)
        self._browser.setMarkdown(
            f"**题目：**\n{r['question']}\n\n---\n\n**解答（{r['engine']}·{r['model']}）：**\n{r['answer']}")

    def _copy_current(self):
        from PySide6.QtGui import QGuiApplication
        r = self._current()
        if r is None:
            return
        QGuiApplication.clipboard().setText(r["answer"])
        QMessageBox.information(self, "已复制", "答案已复制到剪贴板")

    def _delete_selected(self):
        r = self._current()
        if r is None:
            QMessageBox.information(self, "提示", "请先在列表中选择一条记录")
            return
        history.delete_record(r["id"])
        self._refresh()

    def _clear_all(self):
        if not self._records:
            return
        if QMessageBox.question(self, "确认清空",
                                "确定清空全部搜题记录吗？") != QMessageBox.Yes:
            return
        history.clear_all()
        self._refresh()
