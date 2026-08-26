"""配置：双引擎（免费/DeepSeek）、模型、历史等。"""
from PySide6.QtCore import QSettings

_settings = QSettings("QuestionSolver", "QuestionSolver")

# 默认引擎：'free'=免费引擎（默认，省钱）/ 'deepseek'=DeepSeek（付费）
DEFAULT_PROVIDER = "free"

# DeepSeek 模型（2026-08 官方 V4 系列；按量付费，flash 最便宜）
DEEPSEEK_MODELS = [
    ("deepseek-v4-flash（快，日常够用，最便宜）", "deepseek-v4-flash"),
    ("deepseek-v4-pro（更强，难题深度思考）", "deepseek-v4-pro"),
    ("deepseek-v4-flash-vision-exp（视觉实验版）", "deepseek-v4-flash-vision-exp"),
]

# 免费平台（显示名 -> provider 标识）
FREE_PROVIDER_NAMES = {
    "zhipu": "智谱 GLM-4-Flash（免费）",
    "siliconflow": "硅基流动（免费）",
}


def get_deepseek_key() -> str:
    return str(_settings.value("deepseek_key", ""))


def set_deepseek_key(v: str):
    _settings.setValue("deepseek_key", v.strip())


def get_deepseek_model() -> str:
    return str(_settings.value("deepseek_model", "deepseek-chat"))


def set_deepseek_model(v: str):
    _settings.setValue("deepseek_model", v)


def get_free_key() -> str:
    return str(_settings.value("free_key", ""))


def set_free_key(v: str):
    _settings.setValue("free_key", v.strip())


def get_free_provider() -> str:
    return str(_settings.value("free_provider", "zhipu"))


def set_free_provider(v: str):
    _settings.setValue("free_provider", v)


def get_free_model() -> str:
    return str(_settings.value("free_model", ""))


def set_free_model(v: str):
    _settings.setValue("free_model", v)


def get_default_provider() -> str:
    """默认引擎：'free'（省钱）或 'deepseek'。"""
    return str(_settings.value("default_provider", DEFAULT_PROVIDER))


def set_default_provider(v: str):
    _settings.setValue("default_provider", v)


def get_auto_copy() -> bool:
    return bool(_settings.value("auto_copy", True, type=bool))


def set_auto_copy(v: bool):
    _settings.setValue("auto_copy", v)


def get_save_history() -> bool:
    """是否自动保存搜题记录到历史收藏夹。"""
    return bool(_settings.value("save_history", True, type=bool))


def set_save_history(v: bool):
    _settings.setValue("save_history", v)


def get_alert_enabled() -> bool:
    return bool(_settings.value("alert_enabled", True, type=bool))


def set_alert_enabled(v: bool):
    _settings.setValue("alert_enabled", v)


def get_game_mode() -> str:
    """全屏应用内按快捷键的行为：'select'=框选搜题（切回桌面显示结果，默认）；
    'fullscreen'=截全屏搜题（结果进剪贴板+通知，不打断）。"""
    return str(_settings.value("game_mode", "select"))


def set_game_mode(mode: str):
    _settings.setValue("game_mode", mode)


def get_reference_id() -> int:
    """手动指定的参考资料 id；0 表示自动检索全部题库。"""
    return int(_settings.value("reference_id", 0))


def set_reference_id(v: int):
    _settings.setValue("reference_id", int(v))
