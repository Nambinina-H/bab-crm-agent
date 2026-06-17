"""Verrou mono-instance : empeche deux agents de tourner en meme temps sur le
meme poste/session.

Deux instances simultanees capturent la meme activite chacune de leur cote :
on obtient des segments en doublon decales de quelques microsecondes (la
deduplication serveur, basee sur un horodatage identique, ne les voit pas) ->
le temps affiche cote plateforme est gonfle.

Implementation : mutex nomme Windows (CreateMutexW). Le mutex est libere
automatiquement par Windows a la fin du process (meme en cas de crash) : pas de
verrou fantome. Volontairement par SESSION utilisateur ("Local\\") : deux
comptes Windows distincts = deux collaborateurs distincts (employee_id =
user@host) -> suivi separe legitime.
"""

import ctypes
import sys
from ctypes import wintypes

from app.core.logging import log

_MUTEX_NAME = "Local\\BABCRM_Agent_SingleInstance"
_ERROR_ALREADY_EXISTS = 183

# Conserve le handle pour toute la duree de vie du process : tant qu'il existe,
# le mutex reste tenu. Windows le libere a la sortie du process.
_lock_handle = None


def acquire_single_instance_lock():
    """Pose le verrou mono-instance.

    Retourne True si on est la seule instance (on continue), None si une autre
    instance tourne deja (il faut quitter). En cas de souci technique, on
    n'empeche jamais le demarrage (retourne True).
    """
    global _lock_handle
    if sys.platform != "win32":
        return True  # agent concu pour Windows : pas de verrou ailleurs
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = [
            wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR,
        ]
        handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
        err = ctypes.get_last_error()
    except Exception as exc:
        log(f"Verrou mono-instance indisponible (demarrage autorise): {exc}")
        return True
    if not handle:
        return True  # echec de creation : ne pas bloquer le demarrage
    if err == _ERROR_ALREADY_EXISTS:
        # CreateMutexW renvoie un handle vers le mutex existant meme dans ce cas :
        # on le ferme, sinon ce process maintiendrait le mutex en vie.
        kernel32.CloseHandle(handle)
        return None  # une autre instance detient deja le mutex
    _lock_handle = handle
    return True


def notify_already_running():
    """Signale brievement qu'un agent est deja ouvert (boite Windows native)."""
    log("Une autre instance de l'agent est deja en cours : demarrage annule.")
    if sys.platform != "win32":
        return
    try:
        # MB_ICONINFORMATION (0x40) | MB_SETFOREGROUND (0x10000)
        ctypes.windll.user32.MessageBoxW(
            0,
            "BABCRM - agent est déjà ouvert.\n\n"
            "Une seule fenêtre peut être ouverte à la fois.",
            "BABCRM - agent",
            0x40 | 0x00010000,
        )
    except Exception:
        pass