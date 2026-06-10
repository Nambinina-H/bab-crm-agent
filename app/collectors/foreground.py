import ctypes
import ctypes.wintypes as wintypes
import sys

import psutil

user32 = ctypes.windll.user32 if sys.platform == "win32" else None


def get_foreground_app():
    """Return (process_name, window_title) for the foreground window."""
    if not user32:
        return ("(inconnu)", "")

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ("(aucune)", "")

    length = user32.GetWindowTextLengthW(hwnd)
    buff = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buff, length + 1)
    title = buff.value or ""

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    proc_name = "(inconnu)"
    try:
        proc_name = psutil.Process(pid.value).name()
    except Exception:
        pass

    return (proc_name, title)
