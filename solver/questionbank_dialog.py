"""题库管理窗口：导入（PDF/Word/TXT/图片）、删除、查看、指定参考。"""
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QFileDialog, QMessageBox, QTextBrowser,
                               QHeaderView, QAbstractItemView)

from . import questionbank as qb
from . import config
from . import theme


class QuestionBankDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(theme.app_icon())
        self.setWindowTitle("题库管理")
        self.setMinimumSize(680, 420)
        self.resize(720, 460)
        self.setStyleSheet("""
            QDialog { background-color: #1e1b2e; }
            QLabel { color: #c9c4dc; font-size: 12px; }
            QTableWidget { background: #191624; color: #e8e8e8; border: 1px solid #3f3a57;
                           border-radius: 8px; gridline-color: #2a2540; font-size: 12px; }
            QHeaderView::section { background: #2a2540; color: #c9c4dc; border: none;
                                   padding: 6px; font-size: 12px; }
            QPushButton { background: #2a2540; color: #eee; border: 1px solid #4a4463;
                          border-radius: 6px; padding: 7px 16px; font-size: 13px; }
            QPushButton:hover { background: #3f3a57; }
            QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #101c4a, stop:0.5 #2b3f9e, stop:1 #7c3aed); color: white; border: none; font-weight: bold; }
            QPushButton#primary:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #1e2b6e, stop:0.5 #3452c8, stop:1 #8b5cf6); }
            QPushButton#danger { color: #ff6b6b; }
            QPushButton#danger:hover { background: #3a2230; }
            QTextBrowser { background: #191624; color: #e8e8e8; border: 1px solid #3f3a57;
                           border-radius: 8px; padding: 8px; font-size: 13px; }
        """)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("导入的资料会先转成文字，搜题时自动检索最相关的部分（纯本地，不花钱）")
        title.setWordWrap(True)
        head.addWidget(title, 1)
        lay.addLayout(head)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["名称", "类型", "字数", "导入时间"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        lay.addWidget(self.table, 1)

        btns = QHBoxLayout()
        btn_import = QPushButton("＋ 导入文件…")
        btn_import.setObjectName("primary")
        btn_import.setCursor(Qt.PointingHandCursor)
        btn_import.clicked.connect(self._import_files)
        btn_view = QPushButton("查看内容")
        btn_view.setCursor(Qt.PointingHandCursor)
        btn_view.clicked.connect(self._view_content)
        btn_refer = QPushButton("设为参考资料")
        btn_refer.setCursor(Qt.PointingHandCursor)
        btn_refer.setToolTip("搜题时只参考这一份（否则自动检索全部题库）")
        btn_refer.clicked.connect(self._set_reference)
        btn_clear_ref = QPushButton("清除指定（恢复自动检索全部）")
        btn_clear_ref.setCursor(Qt.PointingHandCursor)
        btn_clear_ref.clicked.connect(self._clear_reference)
        btn_delete = QPushButton("删除选中")
        btn_delete.setObjectName("danger")
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.clicked.connect(self._delete_selected)
        btns.addWidget(btn_import)
        btns.addWidget(btn_view)
        btns.addWidget(btn_refer)
        btns.addWidget(btn_clear_ref)
        btns.addStretch(1)
        btns.addWidget(btn_delete)
        lay.addLayout(btns)

        self._ref_label = QLabel("")
        self._ref_label.setWordWrap(True)
        lay.addWidget(self._ref_label)

        close_btn = QPushButton("关闭")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn, 0, Qt.AlignRight)

    # ---------- 数据 ----------
    def _refresh(self):
        self._items = qb.list_bank()
        self.table.setRowCount(len(self._items))
        for row, it in enumerate(self._items):
            self.table.setItem(row, 0, QTableWidgetItem(it["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(qb.KINDS.get(it["kind"], it["kind"])))
            self.table.setItem(row, 2, QTableWidgetItem(str(it["char_count"])))
            self.table.setItem(row, 3, QTableWidgetItem(
                time.strftime("%Y-%m-%d %H:%M", time.localtime(it["imported_at"]))))
        ref_id = config.get_reference_id()
        if ref_id > 0:
            name = next((it["name"] for it in self._items if it["id"] == ref_id), "")
            self._ref_label.setText(f"📌 当前指定参考：{name}（搜题只看这一份）")
        else:
            self._ref_label.setText("当前：自动检索全部题库")
        self._ref_label.setStyleSheet(
            "color: #9ae6a0; font-size: 12px;" if ref_id > 0 else "color: #8a819e; font-size: 12px;")

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._items):
            return None
        return self._items[row]["id"]

    # ---------- 动作 ----------
    def _import_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择要导入的资料",
            "", "支持的格式 (*.txt *.md *.pdf *.docx *.png *.jpg *.jpeg *.bmp *.webp);;所有文件 (*.*)")
        if not files:
            return
        ok, fail = 0, []
        for f in files:
            try:
                qb.import_file(f)
                ok += 1
            except Exception as e:  # noqa: BLE001
                fail.append(f"{f.split('/')[-1]}: {e}")
        if ok:
            self._refresh()
        msg = f"成功导入 {ok} 个文件"
        if fail:
            msg += "\n失败：" + "\n".join(fail)
        QMessageBox.information(self, "导入结果", msg)

    def _view_content(self):
        bank_id = self._selected_id()
        if bank_id is None:
            QMessageBox.information(self, "提示", "请先在列表中选择一份资料")
            return
        text = qb.get_bank_text(bank_id)
        dlg = QDialog(self)
        dlg.setWindowIcon(theme.app_icon())
        dlg.setWindowTitle("资料内容")
        dlg.resize(640, 520)
        dlg.setStyleSheet("QDialog { background-color: #1e1b2e; }")
        lay = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setPlainText(text[:8000] + ("\n\n…（内容过长已截断）" if len(text) > 8000 else ""))
        lay.addWidget(browser)
        dlg.exec()

    def _set_reference(self):
        bank_id = self._selected_id()
        if bank_id is None:
            QMessageBox.information(self, "提示", "请先在列表中选择一份资料")
            return
        config.set_reference_id(bank_id)
        self._refresh()
        QMessageBox.information(self, "已设置",
                                "已指定参考这份资料。搜题时勾选「参考我的题库」即只看这份。")

    def _clear_reference(self):
        config.set_reference_id(0)
        self._refresh()

    def _delete_selected(self):
        bank_id = self._selected_id()
        if bank_id is None:
            QMessageBox.information(self, "提示", "请先在列表中选择一份资料")
            return
        if QMessageBox.question(self, "确认删除",
                                "确定删除这份资料吗？（不影响原文件）") != QMessageBox.Yes:
            return
        qb.delete_bank(bank_id)
        if config.get_reference_id() == bank_id:
            config.set_reference_id(0)
        self._refresh()
