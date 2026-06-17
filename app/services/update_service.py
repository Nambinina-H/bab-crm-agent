"""Mise a jour automatique de l'agent.

Principe (comme une appli mobile) :
- L'agent embarque une version (`app.version.__version__`).
- En arriere-plan, il interroge la derniere Release du depot GitHub public.
- Si une version plus recente existe, il telecharge le nouvel .exe a cote de
  l'actuel (`update.exe`), SANS interrompre la session.
- Au prochain demarrage, `apply_pending_update()` installe ce fichier : un petit
  script attend la fermeture de l'agent, remplace l'.exe puis relance.

La config (`config.json`, `.env`) vit a cote de l'.exe et n'est jamais touchee.
Tout est sans effet hors .exe (developpement) ou si le serveur GitHub est
injoignable (best-effort, silencieux).
"""

import os
import subprocess
import sys
import threading
import time

import requests

from app.core.logging import log
from app.settings.paths import BASE_DIR
from app.version import __version__

# Depot public ou sont publiees les Releases (le .exe en asset).
GITHUB_REPO = "Nambinina-H/bab-crm-agent"
_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_STAGED_NAME = "update.exe"  # nouvel .exe telecharge, en attente d'installation
_MIN_EXE_SIZE = 1_000_000    # garde-fou : un .exe valable fait plusieurs Mo


def _is_frozen():
    """Vrai uniquement pour l'.exe packagee (pas en developpement source)."""
    return getattr(sys, "frozen", False)


def _version_tuple(value):
    """'v1.2.3' / '1.2' -> (1, 2, 3) pour une comparaison numerique robuste."""
    parts = []
    for chunk in str(value).lstrip("vV").split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def _paths():
    exe = sys.executable                       # l'.exe de l'agent en cours
    folder = os.path.dirname(exe)
    return exe, folder, os.path.join(folder, _STAGED_NAME)


def apply_pending_update():
    """A appeler tout au debut du demarrage : installe une MAJ deja telechargee.

    S'il existe un `update.exe` valable, lance un script qui attend la fermeture
    de l'agent, remplace l'.exe et relance ; puis quitte immediatement.
    """
    if not _is_frozen():
        return
    exe, folder, staged = _paths()
    if not os.path.exists(staged):
        return
    if os.path.getsize(staged) < _MIN_EXE_SIZE or not _is_valid_exe(staged):
        _safe_remove(staged)  # telechargement partiel/corrompu : on jette
        return

    exe_name = os.path.basename(exe)
    bat = os.path.join(folder, "_apply_update.bat")
    try:
        with open(bat, "w", encoding="utf-8") as f:
            f.write(
                "@echo off\r\n"
                ":wait\r\n"
                f'tasklist /FI "IMAGENAME eq {exe_name}" | find /I "{exe_name}" '
                ">nul && (ping 127.0.0.1 -n 2 >nul & goto wait)\r\n"
                f'move /Y "{_STAGED_NAME}" "{exe_name}" >nul\r\n'
                f'start "" "{exe_name}"\r\n'
                'del "%~f0"\r\n'  # le script se supprime
            )
        log("Mise a jour : installation + redemarrage...")
        subprocess.Popen(
            ["cmd", "/c", bat], cwd=folder,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
    except Exception as exc:
        log(f"Application MAJ impossible: {exc}")
        return
    os._exit(0)  # libere l'.exe : le script peut le remplacer puis relancer


def is_update_ready() -> bool:
    """Vrai si une nouvelle version a ete telechargee et attend l'installation
    (au prochain redemarrage). Sert a notifier l'utilisateur dans l'UI.

    `AGENT_FAKE_UPDATE=1` force le vrai en developpement : permet de tester le
    bandeau + le rappel du timer flottant sans build."""
    if os.environ.get("AGENT_FAKE_UPDATE"):
        return True
    if not _is_frozen():
        return False
    _, _, staged = _paths()
    return os.path.exists(staged) and os.path.getsize(staged) >= _MIN_EXE_SIZE


def restart_for_update():
    """Relance l'agent en appliquant la MAJ telechargee si presente.

    Robuste et compatible avec le verrou mono-instance : un petit relanceur
    attend la **fin du process courant** (par PID) avant de redemarrer, sinon la
    nouvelle instance se heurterait au verrou. Marche aussi en developpement
    (relance `python -m app.main`) pour pouvoir tester le redemarrage.
    """
    pid = os.getpid()
    exe, _folder, staged = _paths()
    has_update = (
        _is_frozen()
        and os.path.exists(staged)
        and os.path.getsize(staged) >= _MIN_EXE_SIZE
        and _is_valid_exe(staged)
    )
    try:
        if _is_frozen():
            exe_name = os.path.basename(exe)
            swap = (
                f'move /Y "{_STAGED_NAME}" "{exe_name}" >nul\r\n' if has_update else ""
            )
            launch = f'start "" "{exe_name}"\r\n'
        else:
            swap = ""  # dev : rien a remplacer, on relance juste le module
            launch = f'start "" "{sys.executable}" -m app.main\r\n'
        bat = os.path.join(BASE_DIR, "_restart_agent.bat")
        with open(bat, "w", encoding="utf-8") as f:
            f.write(
                "@echo off\r\n"
                ":wait\r\n"
                f'tasklist /FI "PID eq {pid}" | find "{pid}" >nul '
                "&& (ping 127.0.0.1 -n 2 >nul & goto wait)\r\n"
                + swap
                + launch
                + 'del "%~f0"\r\n'  # le script se supprime
            )
        log("Redemarrage de l'agent (application de la mise a jour)...")
        subprocess.Popen(
            ["cmd", "/c", bat], cwd=BASE_DIR, creationflags=0x08000000
        )
    except Exception as exc:
        log(f"Redemarrage impossible: {exc}")
        return
    os._exit(0)  # libere le verrou : le relanceur attend cette sortie puis relance


def check_and_download():
    """Best-effort : telecharge la derniere version si plus recente. Le swap se
    fera au prochain demarrage (apply_pending_update). Sans effet en dev."""
    if not _is_frozen():
        return
    try:
        resp = requests.get(
            _API_LATEST,
            headers={"Accept": "application/vnd.github+json"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        remote = data.get("tag_name", "")
        if _version_tuple(remote) <= _version_tuple(__version__):
            return  # deja a jour

        asset = next(
            (a for a in data.get("assets", [])
             if str(a.get("name", "")).lower().endswith(".exe")),
            None,
        )
        if not asset:
            return
        expected_size = asset.get("size") or 0  # taille exacte annoncee par GitHub

        _, _, staged = _paths()
        tmp = staged + ".part"
        try:
            with requests.get(
                asset["browser_download_url"], stream=True, timeout=180
            ) as dl:
                dl.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in dl.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)

            # Integrite : on n'installe JAMAIS un telechargement incomplet/corrompu
            # (sinon l'.exe ne demarre pas : "Failed to load Python DLL").
            actual = os.path.getsize(tmp)
            if expected_size and actual != expected_size:
                log(f"MAJ {remote} ignoree : telechargement incomplet "
                    f"({actual}/{expected_size} octets).")
                return
            if actual < _MIN_EXE_SIZE or not _is_valid_exe(tmp):
                log(f"MAJ {remote} ignoree : fichier invalide.")
                return

            os.replace(tmp, staged)  # rename atomique : le fichier est complet & valide
            log(f"Mise a jour {remote} verifiee et telechargee "
                f"(appliquee au prochain demarrage).")
        finally:
            _safe_remove(tmp)  # supprime un .part restant (echec/incomplet)
    except Exception as exc:
        log(f"Verification de mise a jour: {exc}")


def start_background_checker(interval_minutes=30):
    """Verifie maintenant puis toutes les `interval_minutes` (thread daemon)."""
    if not _is_frozen():
        return

    def loop():
        while True:
            check_and_download()
            time.sleep(max(5, interval_minutes) * 60)

    threading.Thread(target=loop, daemon=True).start()


def _is_valid_exe(path):
    """Vrai si le fichier est bien un executable Windows (entete 'MZ')."""
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"MZ"
    except OSError:
        return False


def _safe_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass
