"""搜题引擎统一入口。

双引擎路由：
- provider="free"（默认）→ 免费引擎，0 成本，简单题用
- provider="deepseek" → DeepSeek 官方 API（付费），带题库学习/深度重搜时用
"""
from dataclasses import dataclass

from .deepseek import solve as _ds_solve, solve_stream as _ds_solve_stream
from .deepseek import solve_vision_stream as _ds_solve_vision_stream
from .deepseek import vision_recognize as _ds_vision_recognize
from .deepseek import EngineError, DEFAULT_MODEL, DEEP_MODEL, DEFAULT_VISION_MODEL
from .free import solve as _free_solve, probe_free_engine, FREE_PROVIDERS

ENGINE_DISPLAY = {
    "free": "免费引擎",
    "deepseek": "DeepSeek",
}


@dataclass
class SolveResult:
    text: str          # 解答文本（markdown）
    provider: str      # "free" / "deepseek"
    engine_name: str   # 显示名
    model: str         # 模型名
    elapsed: float     # 耗时秒


def solve(question: str, *, provider: str, api_key: str,
          model: str = "", free_provider: str = "zhipu",
          context_chunks=None, timeout: int = 90) -> SolveResult:
    """解答题目。

    provider="deepseek" 时：model 是 DeepSeek 模型名（deepseek-chat / deepseek-reasoner）
    provider="free" 时：free_provider 是免费平台（zhipu / siliconflow），model 是该平台模型名
    """
    if provider == "deepseek":
        text, elapsed = _ds_solve(question, api_key, model=model or DEFAULT_MODEL,
                                  context_chunks=context_chunks, timeout=timeout)
        return SolveResult(text, "deepseek", "DeepSeek", model or DEFAULT_MODEL, elapsed)
    text, elapsed = _free_solve(question, api_key, provider=free_provider, model=model,
                                context_chunks=context_chunks, timeout=timeout)
    return SolveResult(text, "free", "免费引擎", model or "自动", elapsed)


def solve_stream(question: str, *, provider: str, api_key: str, model: str = "",
                 on_token=None, free_provider: str = "zhipu",
                 context_chunks=None, timeout: int = 90) -> SolveResult:
    """流式解答题目：边生成边回调 on_token(增量)。

    目前仅 deepseek 支持流式；free 引擎回退到非流式一次性返回。
    """
    if provider == "deepseek":
        text, elapsed = _ds_solve_stream(question, api_key, model=model or DEFAULT_MODEL,
                                         context_chunks=context_chunks, timeout=timeout,
                                         on_token=on_token)
        return SolveResult(text, "deepseek", "DeepSeek", model or DEFAULT_MODEL, elapsed)
    return solve(question, provider=provider, api_key=api_key, model=model,
                 free_provider=free_provider, context_chunks=context_chunks,
                 timeout=timeout)


def vision_recognize(image_bytes: bytes, *, api_key: str, model: str = "",
                     timeout: int = 60) -> str:
    """用 DeepSeek 视觉模型识别题目截图（OCR 兜底），返回结构化文本。"""
    return _ds_vision_recognize(image_bytes, api_key,
                                model=model or DEFAULT_VISION_MODEL, timeout=timeout)


def solve_vision_stream(images, *, api_key: str, model: str = "",
                        on_token=None, timeout: int = 90,
                        max_tokens: int = 2000, prompt_extra: str = "") -> SolveResult:
    """把题目截图（一张或多张）直接发给 DeepSeek 视觉模型解题（流式）。

    images 可传单张 bytes 或 list[bytes]；prompt_extra 为用户附加说明（改题/条件）。
    """
    text, elapsed = _ds_solve_vision_stream(
        images, api_key, model=model or DEFAULT_VISION_MODEL,
        on_token=on_token, timeout=timeout, max_tokens=max_tokens,
        prompt_extra=prompt_extra)
    return SolveResult(text, "deepseek", "DeepSeek", model or DEFAULT_VISION_MODEL, elapsed)


__all__ = ["solve", "SolveResult", "EngineError", "probe_free_engine",
           "FREE_PROVIDERS", "DEFAULT_MODEL", "DEEP_MODEL", "DEFAULT_VISION_MODEL",
           "vision_recognize", "solve_vision_stream", "ENGINE_DISPLAY"]
