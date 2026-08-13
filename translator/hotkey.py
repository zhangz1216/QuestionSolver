"""全局快捷键 Ctrl+Shift+T（Win32 RegisterHotKey + Qt native event filter）。"""
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter

WM_HOTKEY = 0x0312
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
VK_T = 0x54

HOTKEY_ID = 0xC0DE


class _HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, hotkey):
        super().__init__()
        self._hotkey = hotkey

    def nativeEventFilter(self, eventType, message):
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
            self._hotkey._trigger()
            return True, 0
        return False, 0


class GlobalHotkey:
    """全局快捷键。用法：
        hk = GlobalHotkey(callback)
        hk.register()
        QApplication.instance().installNativeEventFilter(hk.filter)
    """

    def __init__(self, callback, modifiers=MOD_CONTROL | MOD_SHIFT, vk=VK_T):
        self._callback = callback
        self._modifiers = modifiers
        self._vk = vk
        self._registered = False
        self.filter = _HotkeyFilter(self)

    def register(self):
        user32 = ctypes.windll.user32
        ok = user32.RegisterHotKey(None, HOTKEY_ID, self._modifiers, self._vk)
        if not ok:
            raise RuntimeError("注册全局快捷键失败（Ctrl+Shift+T 可能被其他程序占用）")
        self._registered = True

    def unregister(self):
        if self._registered:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
            self._registered = False

    def _trigger(self):
        try:
            self._callback()
        except Exception:  # noqa: BLE001
            pass
