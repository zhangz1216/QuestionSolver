"""OCR 引擎封装（RapidOCR，离线内嵌，无需联网）。"""
from rapidocr_onnxruntime import RapidOCR

_engine = None


def _get_engine() -> RapidOCR:
    global _engine
    if _engine is None:
        _engine = RapidOCR()
    return _engine


def recognize(image) -> str:
    """识别图片中的文字，按「上->下、左->右」的阅读顺序拼好返回。

    image 支持：文件路径 / PNG 等图片字节 / numpy 数组（BGR）。
    """
    engine = _get_engine()
    result, _ = engine(image)
    if not result:
        return ""
    # result 每项为 [box(4 点), text, score]
    lines = sorted(result, key=lambda r: (round(r[0][0][1]), round(r[0][0][0])))
    return "\n".join(str(r[1]) for r in lines)
