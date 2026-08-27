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


def _sort_in_col(col):
    """阅读顺序：上->下，同高度左->右。"""
    return sorted(col, key=lambda r: (round(r["cy"]), round(r["cx"])))


def recognize(image) -> str:
    """识别图片中的文字，按「上->下、同行左->右」阅读顺序拼好返回。

    注：不再做左右分栏识别——需要准确读版面（如左右两栏的题）时，
    用「看图直搜」把原图直接交给视觉模型，效果更好。
    """
    engine = _get_engine()
    result, _ = engine(image)
    if not result:
        return ""
    rows = _sort_in_col(_rows_from_result(result))
    return "\n".join(r["text"] for r in rows)


def recognize_scored(image):
    """识别并附带质量指标，用于「OCR 是否可信」的判断。

    返回 (text, avg_score, line_count)：
    - text：按阅读顺序拼接的识别文本
    - avg_score：RapidOCR 平均置信度（0~1）
    - line_count：识别到的文本行数
    """
    engine = _get_engine()
    result, _ = engine(image)
    if not result:
        return "", 0.0, 0
    rows = _sort_in_col(_rows_from_result(result))
    text = "\n".join(r["text"] for r in rows)
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
    ordered = _sort_in_col(_rows_from_result(result))
    return [
        {"box": [tuple(int(v) for v in p) for p in r["box_pts"]],
         "text": r["text"],
         "score": r["score"]}
        for r in ordered
    ]
