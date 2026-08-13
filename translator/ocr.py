"""OCR 引擎封装（RapidOCR，离线内嵌，无需联网）。"""
from rapidocr_onnxruntime import RapidOCR

_engine = None


def _get_engine() -> RapidOCR:
    global _engine
    if _engine is None:
        _engine = RapidOCR()
    return _engine


def recognize(image) -> str:
    """识别图片中的文字，按「上->下、左->右」的阅读顺序拼好返回。"""
    engine = _get_engine()
    result, _ = engine(image)
    if not result:
        return ""
    lines = sorted(result, key=lambda r: (round(r[0][0][1]), round(r[0][0][0])))
    return "\n".join(str(r[1]) for r in lines)


def recognize_with_boxes(image):
    """识别并返回每行文字的包围盒与文本（用于原位叠加译文）。

    返回 list[dict]，每项 {'box': [(x,y),...4点], 'text': str, 'score': float}。
    坐标为输入图像的像素坐标（物理像素），按阅读顺序排序。
    """
    engine = _get_engine()
    result, _ = engine(image)
    if not result:
        return []
    lines = sorted(result, key=lambda r: (round(r[0][0][1]), round(r[0][0][0])))
    out = []
    for r in lines:
        box = r[0]  # 4 点 [[x,y],[x,y],[x,y],[x,y]]
        out.append({
            "box": [tuple(int(v) for v in p) for p in box],
            "text": str(r[1]),
            "score": float(r[2]),
        })
    return out
