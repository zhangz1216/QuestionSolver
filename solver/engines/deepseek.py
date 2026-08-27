"""DeepSeek 官方 API 客户端（付费引擎）。

OpenAI 兼容接口：POST https://api.deepseek.com/chat/completions
模型：deepseek-chat（快，日常）/ deepseek-reasoner（深度思考，难题更准）
"""
import time
import base64
import urllib.request
import urllib.error
import json

from .prompt import SYSTEM_PROMPT, build_user_prompt

BASE_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"
DEEP_MODEL = "deepseek-v4-pro"
DEFAULT_VISION_MODEL = "deepseek-v4-flash-vision-exp"

# 视觉识别提示词：把截图里的「题目要求 | 初始代码」按语义分开摘录，供 OCR 兜底
VISION_RECOGNIZE_PROMPT = (
    "你是编程题识别助手。识别这张截图里的题目内容，完整、原样地摘录，"
    "严格按以下两段输出：\n\n"
    "【题目要求】\n（把题干要求逐句原样抄录，保留原有的分点、编号、代码块）\n\n"
    "【初始代码】\n（把提供的初始代码原样摘录，保持缩进与结构；若没有则写“无”）\n\n"
    "注意：\n"
    "- 截图可能左右两栏（左=题目要求、右=初始代码）或上下排列，请按语义区分，不要混在一起。\n"
    "- 代码里的符号（@Entry、@Component、大括号、箭头函数、泛型等）要原样保留，不要省略或简化。\n"
    "- 只输出【题目要求】和【初始代码】两段，不要添加解释、解答或多余内容。"
)

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


def vision_recognize(image_bytes: bytes, api_key: str,
                     model: str = DEFAULT_VISION_MODEL, timeout: int = 60) -> str:
    """用 DeepSeek 视觉模型识别题目截图，返回结构化文本（题设/代码分开）。

    用途：OCR 识别不可信（空/低置信度/多栏杂乱）时兜底——让模型直接看图，
    理解「题目要求 | 初始代码」的左右分栏后按语义摘录，比纯 OCR 更准。

    返回 (识别文本, 耗时秒)。
    """
    if not api_key:
        raise EngineError("未配置 DeepSeek API Key，无法使用视觉识别兜底")
    api_key = _validate_key(api_key)
    b64 = base64.b64encode(image_bytes).decode("ascii")
    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": VISION_RECOGNIZE_PROMPT},
            {"type": "image_url",
             "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]},
    ]
    payload = {
        "model": model or DEFAULT_VISION_MODEL,
        "messages": messages,
        "stream": False,
        "temperature": 0.1,
        "max_tokens": 1200,
        # 关闭思考：识别是确定性任务，不需要思考过程，直出更快更稳
        "thinking": {"type": "disabled"},
    }
    t0 = time.time()
    data = _post(BASE_URL, payload, api_key, timeout=timeout)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise EngineError(f"DeepSeek：视觉识别返回格式异常（{str(data)[:150]}）") from e
    if not content:
        raise EngineError("DeepSeek：视觉识别返回内容为空，请重试")
    return content.strip()


def _extract_delta(obj):
    """从流式 chunk JSON 提取 (content文本, reasoning文本, finish_reason)。

    兼容两种响应形态：
    - delta.content 为 str（普通模型）
    - delta.content 为 list（视觉模型：[{type, text}]）
    - 思考型模型先输出 delta.reasoning_content（思考过程）
    """
    try:
        choice = obj["choices"][0]
    except (KeyError, IndexError, TypeError):
        return "", "", None
    delta = choice.get("delta") or {}
    c = delta.get("content") or ""
    if isinstance(c, list):
        c = "".join(str(x.get("text", "")) for x in c if isinstance(x, dict))
    r = delta.get("reasoning_content") or ""
    return c, r, choice.get("finish_reason")


def solve(question: str, api_key: str, model: str = DEFAULT_MODEL,
          context_chunks=None, timeout: int = 90, max_tokens: int = 1800):
    """调用 DeepSeek 解答题目，返回 markdown 文本。

    max_tokens 限制输出长度：防止简单题也生成超长答案拖慢速度。
    """
    if not api_key:
        raise EngineError("未配置 DeepSeek API Key，请到设置里填写")
    api_key = _validate_key(api_key)
    # 思考型模型（pro/reasoner）先输出 reasoning_content 再输出正文，
    # 预算太小会被思考过程吃光导致正文为空 → 单独给大预算
    if "pro" in (model or "") or "reasoner" in (model or ""):
        max_tokens = max(max_tokens, 4000)
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
        # 关闭思考：v4 系列默认先输出 reasoning_content，复杂题思考会吃光
        # max_tokens 预算导致正文为空（表现为「返回内容为空」）。关闭后正文直出，
        # 更快更稳；pro 关闭思考后仍是更强的模型。
        "thinking": {"type": "disabled"},
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
                 context_chunks=None, timeout: int = 90, max_tokens: int = 1800,
                 on_token=None):
    """流式调用 DeepSeek：边接收边回调 on_token(增量文本)，返回 (完整文本, 耗时秒)。

    体感提速的关键：首字 1 秒内到达，用户不用干等完整答案生成。
    """
    if not api_key:
        raise EngineError("未配置 DeepSeek API Key，请到设置里填写")
    api_key = _validate_key(api_key)
    # 思考型模型（pro/reasoner）先输出 reasoning_content 再输出正文，
    # 预算太小会被思考过程吃光导致正文为空 → 单独给大预算
    if "pro" in (model or "") or "reasoner" in (model or ""):
        max_tokens = max(max_tokens, 4000)
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
        # 关闭思考：v4 系列默认先输出 reasoning_content，复杂题思考会吃光
        # max_tokens 预算导致正文为空（表现为「返回内容为空」）。关闭后正文直出，
        # 更快更稳；pro 关闭思考后仍是更强的模型。
        "thinking": {"type": "disabled"},
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
    reasoning = []
    finish_reason = None
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
            c, r, fr = _extract_delta(obj)
            if fr:
                finish_reason = fr
            if c:
                parts.append(c)
                if on_token:
                    on_token(c)
            elif r:
                reasoning.append(r)
    except Exception as e:  # noqa: BLE001
        raise EngineError(f"DeepSeek：流式响应中断（{e}）") from e
    finally:
        try:
            resp.close()
        except Exception:  # noqa: BLE001
            pass
    text = "".join(parts)
    if not text:
        if reasoning:
            raise EngineError(
                "DeepSeek：模型思考过程过长，还没输出正文就结束了。"
                "建议点「修改模型重搜」改选 flash，或稍后重试")
        if finish_reason == "length":
            raise EngineError(
                "DeepSeek：答案生成被截断（内容超长），请重试或换用 pro 模型")
        raise EngineError("DeepSeek：返回内容为空，请重试")
    return text, time.time() - t0


# 看图直搜：让视觉模型直接理解截图（含左右分栏题设/代码）并解题，
# 跳过低质量的 OCR 转文字。用户点「看图直搜」时走这里。
VISION_SOLVE_PROMPT = (
    "请看这张题目截图，直接解题。截图可能左右两栏（左=题目要求、右=初始代码）"
    "或上下排列，请先完整读清题设与代码再作答。\n"
    "务必：① 按题目要求完整解答；② 若需要补全/编写代码，在答案里给出完整可运行的"
    "ArkTS 代码并保留正确缩进；③ 用 markdown 把代码块、步骤、知识点讲清楚。"
)


def solve_vision_stream(image_bytes: bytes, api_key: str,
                        model: str = DEFAULT_VISION_MODEL, timeout: int = 90,
                        max_tokens: int = 2000, on_token=None):
    """把题目截图直接发给 DeepSeek 视觉模型解题（流式），返回 (完整文本, 耗时秒)。

    跳过 OCR 转文字环节：视觉模型能直接理解版面（题目要求 | 初始代码 分栏），
    用于「看图直搜」。要求 model 是视觉模型（deepseek-v4-flash-vision-exp）。
    """
    if not api_key:
        raise EngineError("未配置 DeepSeek API Key，无法看图搜题，请到设置里填写")
    api_key = _validate_key(api_key)
    b64 = base64.b64encode(image_bytes).decode("ascii")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": VISION_SOLVE_PROMPT},
            {"type": "image_url",
             "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]},
    ]
    payload = {
        "model": model or DEFAULT_VISION_MODEL,
        "messages": messages,
        "stream": True,
        "temperature": 0.3,
        "max_tokens": max_tokens,
        "thinking": {"type": "disabled"},
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
            c, _r, _fr = _extract_delta(obj)
            if c:
                parts.append(c)
                if on_token:
                    on_token(c)
    except Exception as e:  # noqa: BLE001
        raise EngineError(f"DeepSeek：看图搜题流式响应中断（{e}）") from e
    finally:
        try:
            resp.close()
        except Exception:  # noqa: BLE001
            pass
    text = "".join(parts)
    if not text:
        raise EngineError("DeepSeek：看图搜题返回内容为空，请重试")
    return text, time.time() - t0
