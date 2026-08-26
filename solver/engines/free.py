"""免费引擎：国内免费大模型 API（省钱默认档）。

候选平台（均需注册免费 key，OpenAI 兼容接口）：
- 智谱 GLM-4-Flash：https://open.bigmodel.cn，模型 glm-4-flash（免费）
- 硅基流动 SiliconFlow：https://cloud.siliconflow.cn，模型 Qwen/Qwen2.5-7B-Instruct（免费）

开发时用 probe_free_engine() 实测哪家通、稳，就把哪家设为默认。
"""
import json
import time
import urllib.request
import urllib.error

from .prompt import SYSTEM_PROMPT, build_user_prompt
from .deepseek import EngineError

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 免费平台注册表：provider -> (显示名, 接口地址, 默认模型)
FREE_PROVIDERS = {
    "zhipu": ("智谱 GLM-4-Flash", "https://open.bigmodel.cn/api/paas/v4/chat/completions", "glm-4-flash"),
    "siliconflow": ("硅基流动", "https://api.siliconflow.cn/v1/chat/completions", "Qwen/Qwen2.5-7B-Instruct"),
}


def _post(url, payload, api_key, timeout=45):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", _UA)
    req.add_header("Authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def solve(question: str, api_key: str, provider: str = "zhipu",
          model: str = "", context_chunks=None, timeout: int = 60):
    """调用免费引擎解答题目，返回 (markdown 文本, 耗时)。"""
    if not api_key:
        raise EngineError("未配置免费平台 API Key，请到设置里填写（免费注册）")
    if provider not in FREE_PROVIDERS:
        raise EngineError(f"未知的免费平台：{provider}")
    display, url, default_model = FREE_PROVIDERS[provider]
    model = model or default_model
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(question, context_chunks)},
    ]
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "temperature": 0.3,
    }
    t0 = time.time()
    try:
        data = _post(url, payload, api_key, timeout=timeout)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:200]
        except Exception:  # noqa: BLE001
            pass
        raise EngineError(f"{display}：HTTP {e.code}（{detail}）") from e
    except urllib.error.URLError as e:
        raise EngineError(f"{display}：网络连接失败（{e.reason}）") from e
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise EngineError(f"{display}：返回格式异常（{str(data)[:150]}）") from e
    return content, time.time() - t0


def probe_free_engine(api_key: str) -> dict:
    """逐个实测免费平台，返回 {'provider': ..., 'display': ..., 'model': ...}。

    测一道简单题，哪个平台能稳定返回就选哪个。全部失败则抛 EngineError。
    """
    test_question = "1+1等于几？只回答数字。"
    failures = []
    for provider, (display, _url, default_model) in FREE_PROVIDERS.items():
        try:
            content, _el = solve(test_question, api_key, provider=provider,
                                 model=default_model, timeout=20)
            if content and content.strip():
                return {"provider": provider, "display": display, "model": default_model}
            failures.append(f"{display}：返回为空")
        except Exception as e:  # noqa: BLE001
            failures.append(f"{display}：{e}")
    raise EngineError("；".join(failures) or "所有免费平台都不可用")
