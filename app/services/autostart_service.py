"""Demarrage automatique de l'agent a l'ouverture de session Windows.

Utilise la cle de registre HKCU\\...\\Run (par utilisateur, sans droits admin).
A l'ouverture de session, Windows relance l'agent tout seul -> utile apres une
coupure de courant ou un redemarrage. Reglable par l'utilisateur (case a cocher).
"""
import os
import sys

from app.core.logging import log
from app.settings.paths import BASE_DIR

try:
    import winreg  # Windows uniquement
except ImportError:  # autre OS (dev) : fonctions inertes
    winreg = None

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "BABCRM Agent"


def is_supported():
    return winreg is not None and sys.platform == "win32"


def _launch_command():
    """Commande lancee au demarrage : l'.exe en prod ; le module en dev."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    # Dev : relance `python -m app.main` depuis le dossier de l'agent (pythonw
    # si dispo pour eviter une console). Best-effort (le vrai cas est l'.exe).
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    py = pyw if os.path.exists(pyw) else exe
    return f'cmd /c "cd /d "{BASE_DIR}" && "{py}" -m app.main"'


def is_enabled():
    """Vrai si le demarrage automatique est actif (valeur presente en registre)."""
    if not is_supported():
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        log(f"Lecture demarrage auto impossible: {exc}")
        return False


def enable():
    if not is_supported():
        return
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, _launch_command())


def disable():
    if not is_supported():
        return
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
    except FileNotFoundError:
        pass  # deja absent


def set_enabled(on):
    """Active ou desactive le demarrage automatique."""
    enable() if on else disable()