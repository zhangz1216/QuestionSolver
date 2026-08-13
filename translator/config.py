"""配置与语言定义。"""
from PySide6.QtCore import QSettings

# 目标语言：显示名 -> Google 翻译语言代码
TARGET_LANGUAGES = [
    ("中文（简体）", "zh-CN"),
    ("中文（繁体）", "zh-TW"),
    ("英语", "en"),
    ("日语", "ja"),
    ("韩语", "ko"),
    ("俄语", "ru"),
    ("法语", "fr"),
    ("德语", "de"),
    ("西班牙语", "es"),
    ("葡萄牙语", "pt"),
    ("意大利语", "it"),
    ("阿拉伯语", "ar"),
    ("越南语", "vi"),
    ("泰语", "th"),
]

# 检测语言代码 -> 显示名（用于展示「检测到：英语」）
DETECTED_NAMES = {
    "en": "英语", "ja": "日语", "ko": "韩语", "ru": "俄语",
    "fr": "法语", "de": "德语", "es": "西班牙语", "pt": "葡萄牙语",
    "it": "意大利语", "ar": "阿拉伯语", "vi": "越南语", "th": "泰语",
    "zh-CN": "中文", "zh-TW": "中文（繁体）", "zh": "中文",
}

DEFAULT_TARGET = "zh-CN"

_settings = QSettings("ScreenTranslator", "ScreenTranslator")


def get_target() -> str:
    return str(_settings.value("target_lang", DEFAULT_TARGET))


def set_target(code: str):
    _settings.setValue("target_lang", code)


def get_auto_copy() -> bool:
    return bool(_settings.value("auto_copy", True, type=bool))


def set_auto_copy(v: bool):
    _settings.setValue("auto_copy", v)


def get_font_size() -> int:
    return int(_settings.value("font_size", 13))


def set_font_size(v: int):
    _settings.setValue("font_size", v)
