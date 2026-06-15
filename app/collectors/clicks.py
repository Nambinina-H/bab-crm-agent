"""Compteur de clics souris (pour l'APM = clics / minute).

On echantillonne l'etat des boutons souris via `GetAsyncKeyState` (un simple
sondage de l'etat materiel), volontairement PAS un hook bas niveau
(`SetWindowsHookEx`) : pas d'injection, pas de DLL globale -> profil bien moins
susceptible d'etre signale par un antivirus. On NE lit jamais le clavier : on
compte uniquement les clics, sans aucun contenu de frappe.

Le compteur tourne dans son propre thread ; `read_and_reset()` renvoie le
nombre de clics depuis le dernier appel (et remet a zero). Tout est encapsule :
hors Windows ou en cas d'erreur, il reste a 0 et ne perturbe jamais l'agent.
"""
import ctypes
import sys
import threading

# Codes virtuels des boutons souris (jamais de touche clavier ici).
_VK_BUTTONS = (0x01, 0x02, 0x04)  # gauche, droit, milieu
_DOWN = 0x8000                    # bit "enfonce" renvoye par GetAsyncKeyState
_POLL_SEC = 0.04                  # 25 Hz : capte les clics sans charger le CPU

_user32 = ctypes.windll.user32 if sys.platform == "win32" else None
if _user32 is not None:
    # SHORT en retour : sans restype explicite, ctypes lit un c_int et le bit
    # "enfonce" peut etre fausse par les octets de poids fort du registre.
    _user32.GetAsyncKeyState.restype = ctypes.c_short
    _user32.GetAsyncKeyState.argtypes = [ctypes.c_int]


class ClickCounter:
    def __init__(self):
        self._count = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if _user32 is None or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        get_state = _user32.GetAsyncKeyState
        prev = [False, False, False]
        while not self._stop.is_set():
            try:
                clicks = 0
                for i, vk in enumerate(_VK_BUTTONS):
                    down = bool(get_state(vk) & _DOWN)
                    if down and not prev[i]:  # front montant = un clic
                        clicks += 1
                    prev[i] = down
                if clicks:
                    with self._lock:
                        self._count += clicks
            except Exception:
                pass  # un clic perdu ne doit jamais arreter le sondage
            self._stop.wait(_POLL_SEC)

    def read_and_reset(self):
        """Clics depuis le dernier appel ; remet le compteur a zero."""
        with self._lock:
            n = self._count
            self._count = 0
            return n

    def stop(self):
        self._stop.set()
