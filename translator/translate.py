"""Google 翻译在国内不可达，改用三路免费回退（均无需 Key、国内可达、自动识别语言）：
有道 demo -> 腾讯 transmart -> MyMemory。"""
import json
import time
import urllib.request
import urllib.parse


class TranslateError(Exception):
    pass


_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _http_json(url, payload_bytes, headers, timeout):
    req = urllib.request.Request(url, data=payload_bytes, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def _youdao(text, target):
    """有道 demo 接口，返回 (译文, 源语言代码)。"""
    data = {
        "q": text,
        "from": "auto",
        "to": target,
    }
    payload = urllib.parse.urlencode(data).encode("utf-8")
    headers = {"User-Agent": _UA, "Content-Type": "application/x-www-form-urlencoded"}
    j = _http_json("https://aidemo.youdao.com/trans", payload, headers, 12)
    if j.get("errorCode") not in ("0", 0, None):
        raise TranslateError(f"有道返回错误：{j.get('errorCode')}")
    translation = j.get("translation")
    if not translation:
        raise TranslateError("有道返回空结果")
    text_out = translation[0] if isinstance(translation, list) else str(translation)
    # l 形如 "en2zh-CHS"，取源语言
    src = "auto"
    l = j.get("l") or ""
    if "2" in l:
        src = l.split("2")[0]
    return text_out, src


def _tencent(text, target):
    """腾讯交互翻译（transmart），返回 (译文, 源语言代码)。"""
    body = {
        "header": {"fn": "auto_translation",
                   "client_key": "browser-chrome-110.0.0.0-104.0.5112.81-"},
        "type": "plain",
        "model_category": "normal",
        "source": {"lang": "auto", "text_list": [text]},
        "target": {"lang": target},
    }
    payload = json.dumps(body).encode("utf-8")
    headers = {"User-Agent": _UA, "Content-Type": "application/json"}
    j = _http_json("https://transmart.qq.com/api/imt", payload, headers, 12)
    hdr = j.get("header", {})
    if hdr.get("ret_code") != "succ":
        raise TranslateError(f"腾讯返回错误：{hdr.get('ret_code')}")
    arr = j.get("auto_translation") or []
    if not arr:
        raise TranslateError("腾讯返回空结果")
    return arr[0], j.get("src_lang", "auto")


def _mymemory(text, target):
    """MyMemory 免费接口，返回 (译文, 源语言代码)。"""
    params = urllib.parse.urlencode({"q": text, "langpair": f"autodetect|{target}"})
    url = f"https://api.mymemory.translated.net/get?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=12) as resp:
        j = json.loads(resp.read().decode("utf-8"))
    resp_data = j.get("responseData", {})
    if int(j.get("responseStatus", 0)) != 200 or not resp_data.get("translatedText"):
        raise TranslateError("MyMemory 返回错误")
    return resp_data["translatedText"], resp_data.get("detectedLanguage", "auto")


_BACKENDS = (_youdao, _tencent, _mymemory)


def translate(text: str, target: str = "zh-CN", source: str = "auto",
              timeout: int = 12):
    """翻译文本，返回 (译文, 源语言代码)。自动在多个免费后端间回退。

    target 使用 Google 风格代码（zh-CN 等），内部自动转换为各后端格式。
    """
    # 后端语言代码映射
    target = _normalize_target(target)
    last_err = None
    for backend in _BACKENDS:
        try:
            return backend(text, target)
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.3)
    raise TranslateError(f"翻译失败：{last_err}")


def _normalize_target(code: str) -> str:
    """把目标语言代码转成各后端可接受的形式。"""
    # 有道/腾讯用 zh-CHS / zh，Google 风格用 zh-CN
    if code in ("zh-CN", "zh"):
        return "zh-CHS"
    if code == "zh-TW":
        return "zh-CHT"
    return code
