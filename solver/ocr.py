"""OCR 引擎封装（RapidOCR，离线内嵌，无需联网）。"""
from rapidocr_onnxruntime import RapidOCR

_engine = None


def _get_engine() -> RapidOCR:
    global _engine
    if _engine is None:
        _engine = RapidOCR()
    return _engine


def _rows_from_result(result):
    """RapidOCR result -> 每行 {text, cx, cy, x0, x1, y0, y1}，按检测顺序。

    RapidOCR 每项：[(4点box), 文本, 置信度]。box 坐标为原图像素坐标。
    """
    rows = []
    for r in result:
        box = r[0]
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        rows.append({
            "text": str(r[1]),
            "score": float(r[2]),
            "box_pts": box,           # 原始 4 点，供原位叠加还原坐标
            "cx": sum(xs) / 4.0,
            "cy": sum(ys) / 4.0,
            "x0": min(xs), "x1": max(xs),
            "y0": min(ys), "y1": max(ys),
        })
    return rows


def _detect_columns(rows, img_w):
    """按每行的 x 中心聚类，检测左右分栏（如「题目要求 | 初始代码」并排）。

    ArkTS 题目常左右两栏：左=题设、右=初始代码。RapidOCR 默认按行高排序，
    会把左右同一水平线上的行交错合并成一段。这里依据相邻行 cx 间隙切栏：
    cx 间隔 > 阈值（图片宽的一定比例）说明进入了新的一栏。
    """
    if len(rows) <= 1:
        return [rows] if rows else []
    threshold = max(50, img_w * 0.08)
    sr = sorted(rows, key=lambda r: r["cx"])
    cols = [[sr[0]]]
    prev = sr[0]["cx"]
    for r in sr[1:]:
        if r["cx"] - prev > threshold:
            cols.append([])
        cols[-1].append(r)
        prev = r["cx"]
    cols = [c for c in cols if c]
    # 防过度切分：很宽的单栏（如长代码）易被切成多块，回退单栏
    if len(cols) > 3:
        return [rows]
    return cols


def _sort_in_col(col):
    """栏内阅读顺序：上->下，同高度左->右。"""
    return sorted(col, key=lambda r: (round(r["cy"]), round(r["cx"])))


def recognize(image) -> str:
    """识别图片中的文字，按「先分栏（左->右）、栏内再 上->下」阅读顺序拼好返回。

    多栏布局（题目要求 | 初始代码）会分别识别成独立段落，避免左右交错合并。
    """
    engine = _get_engine()
    result, _ = engine(image)
    if not result:
        return ""
    rows = _rows_from_result(result)
    img_w = max(r["x1"] for r in rows) or 1
    cols = _detect_columns(rows, img_w)
    if len(cols) <= 1:
        # 单栏：整段按 上->下 排
        cols = [_sort_in_col(rows)]
    return "\n\n".join("\n".join(r["text"] for r in _sort_in_col(c))
                       for c in cols)


def recognize_scored(image):
    """识别并附带质量指标，用于「OCR 是否可信」的判断。

    返回 (text, avg_score, line_count)：
    - text：分栏重排后的识别文本
    - avg_score：RapidOCR 平均置信度（0~1）
    - line_count：识别到的文本行数
    """
    engine = _get_engine()
    result, _ = engine(image)
    if not result:
        return "", 0.0, 0
    rows = _rows_from_result(result)
    img_w = max(r["x1"] for r in rows) or 1
    cols = _detect_columns(rows, img_w)
    if len(cols) <= 1:
        cols = [_sort_in_col(rows)]
    text = "\n\n".join("\n".join(r["text"] for r in _sort_in_col(c))
                       for c in cols)
    avg_score = sum(r["score"] for r in rows) / len(rows)
    return text, avg_score, len(rows)


def recognize_with_boxes(image):
    """识别并返回每行文字的包围盒与文本（用于原位叠加译文）。

    返回 list[dict]，每项 {'box': [(x,y),...4点], 'text': str, 'score': float}。
    坐标为输入图像的像素坐标（物理像素），按阅读顺序排序。
    """
    engine = _get_engine()
    result, _ = engine(image)
    if not result:
        return []
    rows = _rows_from_result(result)
    img_w = max(r["x1"] for r in rows) or 1
    cols = _detect_columns(rows, img_w)
    if len(cols) <= 1:
        cols = [rows]
    ordered = [r for c in cols for r in _sort_in_col(c)]
    return [
        {"box": [tuple(int(v) for v in p) for p in r["box_pts"]],
         "text": r["text"],
         "score": r["score"]}
        for r in ordered
    ]
