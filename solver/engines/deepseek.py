"""DeepSeek 官方 API 客户端（付费引擎）。

OpenAI 兼容接口：POST https://api.deepseek.com/chat/completions
模型：deepseek-chat（快，日常）/ deepseek-reasoner（深度思考，难题更准）
"""
import time
import urllib.request
import urllib.error
import json

from .prompt import SYSTEM_PROMPT, build_user_prompt

BASE_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"
DEEP_MODEL = "deepseek-v4-pro"

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")


class EngineError(Exception):
    """带用户可读信息的引擎错误。"""


def _post(url, payload, api_key, timeout=60):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", _UA)
    req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # 把 HTTP 错误码转成用户可读的中文信息
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:200]
        except Exception:  # noqa: BLE001
            pass
        code_msg = {
            401: "API Key 无效或已过期，请检查设置里的 Key",
            402: "账户余额不足，请到 DeepSeek 平台充值",
            403: "无权限访问，请检查 Key",
            429: "请求太频繁被限流，稍等几秒再试",
        }.get(e.code, f"服务返回 HTTP {e.code}")
        raise EngineError(f"DeepSeek：{code_msg}（{detail}）") from e
    except urllib.error.URLError as e:
        raise EngineError(f"DeepSeek：网络连接失败（{e.reason}），请检查网络") from e


def verify_key(api_key: str, timeout: int = 20) -> list:
    """验证 DeepSeek Key 是否有效（GET /models，不消耗 token）。

    返回可用模型 id 列表；无效或网络错误抛 EngineError。
    """
    if not api_key:
        raise EngineError("未填写 DeepSeek API Key")
    req = urllib.request.Request("https://api.deepseek.com/models", method="GET")
    req.add_header("User-Agent", _UA)
    req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:200]
        except Exception:  # noqa: BLE001
            pass
        code_msg = {
            401: "API Key 无效或已过期，请检查设置里的 Key",
            402: "账户余额不足，请到 DeepSeek 平台充值",
            403: "无权限访问，请检查 Key",
            429: "请求太频繁被限流，稍等几秒再试",
        }.get(e.code, f"服务返回 HTTP {e.code}")
        raise EngineError(f"DeepSeek：{code_msg}（{detail}）") from e
    except urllib.error.URLError as e:
        raise EngineError(f"DeepSeek：网络连接失败（{e.reason}），请检查网络") from e


def solve(question: str, api_key: str, model: str = DEFAULT_MODEL,
          context_chunks=None, timeout: int = 90):
    """调用 DeepSeek 解答题目，返回 markdown 文本。

    model 为 "deepseek-reasoner" 时走深度思考（更准但慢）。
    """
    if not api_key:
        raise EngineError("未配置 DeepSeek API Key，请到设置里填写")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(question, context_chunks)},
    ]
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "stream": False,
        "temperature": 0.3,
    }
    t0 = time.time()
    data = _post(BASE_URL, payload, api_key, timeout=timeout)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise EngineError(f"DeepSeek：返回格式异常（{str(data)[:150]}）") from e
    elapsed = time.time() - t0
    return content, elapsed
