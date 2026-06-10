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
    if os.path.getsize(staged) < _MIN_EXE_SIZE:
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

        _, _, staged = _paths()
        tmp = staged + ".part"
        with requests.get(
            asset["browser_download_url"], stream=True, timeout=180
        ) as dl:
            dl.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in dl.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
        os.replace(tmp, staged)  # rename atomique une fois le fichier complet
        log(f"Mise a jour {remote} telechargee (appliquee au prochain demarrage).")
    except Exception as exc:
        log(f"Verification de mise a jour: {exc}")


def start_background_checker(interval_hours=6):
    """Verifie maintenant puis toutes les `interval_hours` (thread daemon)."""
    if not _is_frozen():
        return

    def loop():
        while True:
            check_and_download()
            time.sleep(interval_hours * 3600)

    threading.Thread(target=loop, daemon=True).start()


def _safe_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass
