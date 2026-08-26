"""搜题引擎统一入口。

双引擎路由：
- provider="free"（默认）→ 免费引擎，0 成本，简单题用
- provider="deepseek" → DeepSeek 官方 API（付费），带题库学习/深度重搜时用
"""
from dataclasses import dataclass

from .deepseek import solve as _ds_solve, EngineError, DEFAULT_MODEL, DEEP_MODEL
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


__all__ = ["solve", "SolveResult", "EngineError", "probe_free_engine",
           "FREE_PROVIDERS", "DEFAULT_MODEL", "DEEP_MODEL", "ENGINE_DISPLAY"]
