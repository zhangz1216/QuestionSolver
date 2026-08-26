"""检测前台窗口是否全屏游戏（用于避免悬浮覆盖层把独占全屏游戏挤回桌面）。"""
import ctypes
from ctypes import wintypes

# 窗口样式常量
GWL_STYLE = -16
WS_CAPTION = 0x00C00000  # WS_BORDER | WS_DLGFRAME（有标题栏/边框）


def is_fullscreen_foreground() -> bool:
    """判断当前前台窗口是否「全屏且无边框」（覆盖主屏）。

    全屏独占游戏（exclusive fullscreen）及无边框窗口全屏（borderless）
    都满足此条件。此时不应显示任何悬浮窗口/覆盖层，否则会把游戏挤回桌面。
    """
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False

        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False

        w = rect.right - rect.left
        h = rect.bottom - rect.top
        sw = user32.GetSystemMetrics(0)  # SM_CXSCREEN 主屏宽
        sh = user32.GetSystemMetrics(1)  # SM_CYSCREEN 主屏高
        if w < sw or h < sh:
            return False

        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        if style & WS_CAPTION:
            return False

        return True
    except Exception:  # noqa: BLE001
        return False
