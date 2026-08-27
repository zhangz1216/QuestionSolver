# -*- coding: utf-8 -*-
"""「视界 AI 搜题」统一主题：色板 + 应用图标生成器。

呼应应用图标设计语言：深蓝→紫渐变（#101c4a→#2b3f9e→#7c3aed）+ 四角取景框 + 视界之眼。
所有界面从这里取色，保证整套 UI 风格统一。
"""
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (QColor, QIcon, QLinearGradient, QPainter,
                           QPainterPath, QPixmap, QPen)

# ============ 品牌渐变（图标同款：深蓝 → 靛 → 紫） ============
GRAD_TOP = "#101c4a"      # 渐变起点（深蓝）
GRAD_MID = "#2b3f9e"      # 渐变中段（靛）
GRAD_END = "#7c3aed"      # 渐变终点（紫）

# ============ 强调色（主按钮 / 高亮） ============
PRIMARY   = "#7c3aed"     # 主按钮 / 强调
PRIMARY_H = "#8b5cf6"     # hover
PRIMARY_P = "#6d28d9"     # pressed
ACCENT    = "#a78bfa"     # 亮紫（链接 / 细节强调 / 框选线）

# ============ 背景 ============
WIN_BG    = "#1e1b2e"     # 对话框 / 窗口底色（带紫调深空色）
PANEL_BG  = "#1a1728"     # 主挂件面板（实色）
PANEL_RGBA  = "rgba(26, 23, 40, 244)"    # 主挂件面板
PANEL_RGBA2 = "rgba(26, 23, 40, 242)"    # 结果卡片面板
INPUT_BG  = "#191624"     # 输入框 / 表格 / 预览底
CTRL_BG   = "#2a2540"     # 控件底（普通按钮 / 下拉）
CTRL_HV   = "#3a3455"     # 控件 hover

# ============ 边框 ============
BORDER    = "#3f3a57"
BORDER_HV = "#4a4463"
BORDER_LT = "rgba(255, 255, 255, 30)"

# ============ 文字 ============
TEXT      = "#eceaf4"     # 主文字（亮白微紫）
TEXT_SUB  = "#c9c4dc"     # 次级文字
TEXT_DIM  = "#8a819e"     # 弱化文字 / 提示
TEXT_HINT = "#9f97b5"     # 分组框标题

# ============ 语义 ============
DANGER    = "#ff6b6b"
DANGER_BG = "#3a2230"
OK        = "#9ae6a0"

# ============ 框选（取景框） ============
SELECT_LINE = "#a78bfa"    # 框选线（视界亮紫，呼应取景框）
SELECT_MASK = 55            # 框选遮罩不透明度


def app_icon() -> QIcon:
    """绘制 64×64「视界之眼」应用图标（纯 QPainter，无外部资源）。

    与 exe 图标（icon.ico）同一设计语言，供窗口 / 托盘 / 对话框共同使用。
    """
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    # 圆角渐变背景（深蓝→靛→紫，对角）
    grad = QLinearGradient(0, 0, 64, 64)
    grad.setColorAt(0.0, QColor(GRAD_TOP))
    grad.setColorAt(0.55, QColor(GRAD_MID))
    grad.setColorAt(1.0, QColor(GRAD_END))
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, 64, 64), 14, 14)
    p.fillPath(path, grad)
    # 四角取景框（白，圆头）
    pen = QPen(QColor(255, 255, 255, 235))
    pen.setWidthF(3.2)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    m, L = 8, 14
    p.drawLine(QPointF(m, m + L), QPointF(m, m))
    p.drawLine(QPointF(m, m), QPointF(m + L, m))
    p.drawLine(QPointF(64 - m, m + L), QPointF(64 - m, m))
    p.drawLine(QPointF(64 - m, m), QPointF(64 - m - L, m))
    p.drawLine(QPointF(m, 64 - m - L), QPointF(m, 64 - m))
    p.drawLine(QPointF(m, 64 - m), QPointF(m + L, 64 - m))
    p.drawLine(QPointF(64 - m, 64 - m - L), QPointF(64 - m, 64 - m))
    p.drawLine(QPointF(64 - m, 64 - m), QPointF(64 - m - L, 64 - m))
    # 中央「视界之眼」
    cx, cy = 32.0, 30.0
    for r, a in [(24, 26), (20, 36), (16.5, 50), (13.5, 70)]:
        p.setBrush(QColor(160, 180, 255, a))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), r, r)
    p.setBrush(QColor(255, 255, 255, 245))      # 虹膜
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(cx, cy), 9.8, 9.8)
    p.setBrush(QColor(13, 27, 77, 255))         # 瞳孔
    p.drawEllipse(QPointF(cx, cy), 5.0, 5.0)
    p.setBrush(QColor(255, 255, 255, 235))      # 右上高光
    p.drawEllipse(QPointF(cx + 2.3, cy - 4.2), 2.0, 2.0)
    p.setBrush(QColor(255, 255, 255, 255))
    p.drawEllipse(QPointF(cx + 3.0, cy - 3.4), 0.8, 0.8)
    # 四向星芒
    p.setPen(QPen(QColor(255, 255, 255, 170), 1.6, Qt.SolidLine, Qt.RoundCap))
    for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
        p.drawLine(QPointF(cx + dx * 17, cy + dy * 17),
                   QPointF(cx + dx * 23, cy + dy * 23))
    p.end()
    return QIcon(pm)
