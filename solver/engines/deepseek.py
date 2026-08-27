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


def _http_to_engine_error(e):
    """把 urllib 的 HTTPError/URLError 转成用户可读的 EngineError。"""
    if isinstance(e, urllib.error.HTTPError):
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
        return EngineError(f"DeepSeek：{code_msg}（{detail}）")
    return EngineError(f"DeepSeek：网络连接失败（{e.reason}），请检查网络")


def _post(url, payload, api_key, timeout=60):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", _UA)
    req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        raise _http_to_engine_error(e) from e


def _validate_key(api_key: str) -> str:
    """校验 DeepSeek API Key 格式。

    防止非 ASCII 内容（如误粘贴的中文）混入 Authorization 头：
    http.client 对 str 类型的 header 用 latin-1 编码，含中文会抛
    UnicodeEncodeError 且 UI 上表现为「按钮没反应」。这里提前拦截，
    给出用户可读的错误。
    """
    key = (api_key or "").strip()
    if not key:
        raise EngineError("未填写 DeepSeek API Key，请到 platform.deepseek.com 获取（sk- 开头）")
    if not key.isascii():
        raise EngineError(
            "DeepSeek Key 格式不正确：包含中文或非英文字符。"
            "请检查是否误粘贴了别的内容，应形如 sk-xxxxxxxx")
    if not key.startswith("sk-"):
        raise EngineError(
            "DeepSeek Key 格式不正确：应以 sk- 开头。"
            "请到 platform.deepseek.com 复制完整 Key")
    return key


def verify_key(api_key: str, timeout: int = 20) -> list:
    """验证 DeepSeek Key 是否有效（GET /models，不消耗 token）。

    返回可用模型 id 列表；无效或网络错误抛 EngineError。
    """
    api_key = _validate_key(api_key)
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
          context_chunks=None, timeout: int = 90, max_tokens: int = 900):
    """调用 DeepSeek 解答题目，返回 markdown 文本。

    max_tokens 限制输出长度：防止简单题也生成超长答案拖慢速度。
    """
    if not api_key:
        raise EngineError("未配置 DeepSeek API Key，请到设置里填写")
    api_key = _validate_key(api_key)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(question, context_chunks)},
    ]
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "stream": False,
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }
    t0 = time.time()
    data = _post(BASE_URL, payload, api_key, timeout=timeout)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise EngineError(f"DeepSeek：返回格式异常（{str(data)[:150]}）") from e
    elapsed = time.time() - t0
    return content, elapsed


def solve_stream(question: str, api_key: str, model: str = DEFAULT_MODEL,
                 context_chunks=None, timeout: int = 90, max_tokens: int = 900,
                 on_token=None):
    """流式调用 DeepSeek：边接收边回调 on_token(增量文本)，返回 (完整文本, 耗时秒)。

    体感提速的关键：首字 1 秒内到达，用户不用干等完整答案生成。
    """
    if not api_key:
        raise EngineError("未配置 DeepSeek API Key，请到设置里填写")
    api_key = _validate_key(api_key)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(question, context_chunks)},
    ]
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "stream": True,
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", _UA)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Accept", "text/event-stream")
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        raise _http_to_engine_error(e) from e
    parts = []
    try:
        while True:
            line = resp.readline()
            if not line:
                break
            line = line.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            try:
                delta = obj["choices"][0]["delta"].get("content") or ""
            except (KeyError, IndexError, TypeError):
                delta = ""
            if delta:
                parts.append(delta)
                if on_token:
                    on_token(delta)
    except Exception as e:  # noqa: BLE001
        raise EngineError(f"DeepSeek：流式响应中断（{e}）") from e
    finally:
        try:
            resp.close()
        except Exception:  # noqa: BLE001
            pass
    text = "".join(parts)
    if not text:
        raise EngineError("DeepSeek：返回内容为空，请重试")
    return text, time.time() - t0
