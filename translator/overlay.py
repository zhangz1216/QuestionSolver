"""把译文原位叠加回截图：擦除原文、原位重绘译文（类似拍照翻译）。

保证不变量：文本框（擦除矩形 + 译文）绝不超出截图边界。
- 填充矩形外扩后夹取回图片边界内。
- 文字用 TextWrapAnywhere 在任意字符处换行，横向绝不溢出。
- 夹取后按实际可用尺寸重新缩小字号，纵向也放得下。
- 整体按 SCALE 放大，译文有更多空间。
"""
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QFontMetrics

# 整体放大倍率
SCALE = 1.4


def _sample_bg(image: QImage, rect: QRect, dist: int = 3) -> QColor:
    """在文本框外侧 dist 像素处采样一圈背景色，取每通道中位数。"""
    W, H = image.width(), image.height()
    rs, gs, bs = [], [], []

    def _push(x, y):
        if 0 <= x < W and 0 <= y < H:
            c = image.pixelColor(x, y)
            rs.append(c.red())
            gs.append(c.green())
            bs.append(c.blue())

    for x in range(rect.left(), rect.right() + 1):
        _push(x, rect.top() - dist)
        _push(x, rect.bottom() + dist)
    for y in range(rect.top(), rect.bottom() + 1):
        _push(rect.left() - dist, y)
        _push(rect.right() + dist, y)

    if not rs:
        return QColor(255, 255, 255)
    rs.sort()
    gs.sort()
    bs.sort()
    mid = len(rs) // 2
    return QColor(rs[mid], gs[mid], bs[mid])


def _measure_wrapped(fm: QFontMetrics, width: int, text: str):
    """返回文本在指定宽度内换行后的 (最大行宽, 总高度)。"""
    br = fm.boundingRect(QRect(0, 0, width, 100000), Qt.TextWrapAnywhere, text)
    return br.width(), br.height()


def composite_overlay(image: QImage, lines) -> QImage:
    """把译文原位叠加到截图，返回新图（不改动原图，整体按 SCALE 放大）。

    lines: [{'box': [(x,y),...4点], 'translated': str}]
    """
    img = image.convertToFormat(QImage.Format_ARGB32)
    img.setDevicePixelRatio(image.devicePixelRatio())

    rects, texts = [], []
    for ln in lines:
        box = ln["box"]
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        r = QRect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        if r.width() >= 4 and r.height() >= 4:
            rects.append(r)
            texts.append(ln["translated"])
    if not rects:
        return img

    hs = sorted(r.height() for r in rects)
    median_h = hs[len(hs) // 2]
    base_size = max(9.0, median_h * 0.5)
    h_pad = max(6, int(median_h * 0.20))
    v_pad = max(6, int(median_h * 0.20))

    img_bounds = QRect(0, 0, img.width(), img.height())

    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)

    planned = []
    for rect, text in zip(rects, texts):
        draw_w = rect.width() + 2 * h_pad
        size = base_size
        font = QFont()
        font.setPointSizeF(size)
        fm = QFontMetrics(font)
        _, needed_h = _measure_wrapped(fm, draw_w, text)

        target_h = max(rect.height(), needed_h) + 2 * v_pad
        fill_rect = QRect(rect.left() - h_pad, rect.top() - v_pad, draw_w, target_h)
        fill_rect = fill_rect.intersected(img_bounds)  # 绝不超出图片边界
        if fill_rect.width() < 4 or fill_rect.height() < 4:
            continue

        # 夹取后框变小，重新缩小字号直到文字放得下
        while size > 6.0:
            font.setPointSizeF(size)
            fm = QFontMetrics(font)
            w2, h2 = _measure_wrapped(fm, fill_rect.width(), text)
            if w2 <= fill_rect.width() and h2 <= fill_rect.height():
                break
            size -= 0.5

        bg = _sample_bg(img, fill_rect, dist=max(3, h_pad // 2))
        lum = (bg.red() * 299 + bg.green() * 587 + bg.blue() * 114) // 1000
        pen = QColor(24, 24, 24) if lum > 128 else QColor(240, 240, 240)
        planned.append((fill_rect, text, font, bg, pen))

    for fill_rect, _, _, bg, _ in planned:
        p.fillRect(fill_rect, bg)

    for fill_rect, text, font, _, pen in planned:
        p.setFont(font)
        p.setPen(pen)
        p.drawText(fill_rect, Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWrapAnywhere, text)

    p.end()

    if abs(SCALE - 1.0) > 0.01:
        new_w = max(1, int(img.width() * SCALE))
        new_h = max(1, int(img.height() * SCALE))
        img = img.scaled(new_w, new_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        img.setDevicePixelRatio(image.devicePixelRatio())
    return img
