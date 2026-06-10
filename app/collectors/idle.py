import ctypes
import ctypes.wintypes as wintypes
import sys

user32 = ctypes.windll.user32 if sys.platform == "win32" else None
kernel32 = ctypes.windll.kernel32 if sys.platform == "win32" else None


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def get_idle_seconds() -> float:
    """Seconds since last keyboard or mouse input."""
    if not user32 or not kernel32:
        return 0
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0
    millis = kernel32.GetTickCount() - info.dwTime
    return millis / 1000.0
