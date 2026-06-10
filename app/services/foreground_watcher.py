import ctypes
import ctypes.wintypes as wintypes
import sys
import threading

from app.core.logging import log

EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000
WM_QUIT = 0x0012

if sys.platform == "win32":
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32
    # Signature du callback du hook (WinEventProc).
    _WinEventProc = ctypes.WINFUNCTYPE(
        None,
        wintypes.HANDLE,  # hWinEventHook
        wintypes.DWORD,   # event
        wintypes.HWND,    # hwnd
        wintypes.LONG,    # idObject
        wintypes.LONG,    # idChild
        wintypes.DWORD,   # dwEventThread
        wintypes.DWORD,   # dwmsEventTime
    )
    # Types explicites : evite la troncature du handle sur 64 bits.
    _user32.SetWinEventHook.restype = wintypes.HANDLE
    _user32.SetWinEventHook.argtypes = [
        wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, _WinEventProc,
        wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
    ]
    _user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
    _user32.GetMessageW.argtypes = [
        ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT,
    ]
    _user32.GetMessageW.restype = ctypes.c_int  # peut renvoyer -1
else:
    _user32 = None


class ForegroundWatcher(threading.Thread):
    """Détecte les changements de fenêtre au premier plan via un hook Windows
    (EVENT_SYSTEM_FOREGROUND) et appelle `on_change` en <100 ms.

    Évènementiel : Windows nous réveille seulement au changement (aucun polling).
    No-op hors Windows ou si le hook est indisponible (repli sur l'échantillonnage).
    """

    def __init__(self, on_change):
        super().__init__(daemon=True)
        self.on_change = on_change
        self._thread_id = None
        self._hook = None
        self._proc = None  # garde une reference (sinon le callback est collecte par le GC)

    def run(self):
        if not _user32:
            return
        self._thread_id = _kernel32.GetCurrentThreadId()

        def _callback(_hook, _event, _hwnd, _obj, _child, _thread, _ts):
            try:
                self.on_change()
            except Exception:
                pass  # ne jamais perturber la boucle de messages

        self._proc = _WinEventProc(_callback)
        self._hook = _user32.SetWinEventHook(
            EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND,
            None, self._proc, 0, 0, WINEVENT_OUTOFCONTEXT,
        )
        if not self._hook:
            log("Hook premier-plan indisponible (echantillonnage standard utilise).")
            return

        # Boucle de messages : indispensable pour recevoir les evenements du hook.
        msg = wintypes.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))
        _user32.UnhookWinEvent(self._hook)

    def stop(self):
        # Reveille GetMessageW pour sortir proprement de la boucle.
        if _user32 and self._thread_id:
            _user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
