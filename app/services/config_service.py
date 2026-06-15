import threading

import requests

from app.core.logging import log
from app.services import update_service
from app.settings.settings import save_config

# Bornes defensives : l'agent revalide meme si le serveur valide deja, pour ne
# jamais appliquer une valeur aberrante (ex. intervalle 0 -> boucle folle).
_BOUNDS = {
    "sample_interval_sec": (1, 3600),
    "idle_threshold_sec": (5, 86400),
    "sync_interval_sec": (5, 3600),
    "sync_batch_size": (1, 5000),
}

# Dernier "top de mise a jour" vu (None = pas encore lu, sert de reference).
_last_update_signal = None


def _clamp(key, value):
    lo, hi = _BOUNDS[key]
    return max(lo, min(hi, int(value)))


def pull_remote_config(cfg):
    """Recupere la config centrale et l'applique a chaud sur `cfg` (en place).

    - Valide/borne chaque valeur recue.
    - Persiste les valeurs appliquees dans config.json (cache pour l'offline).
    - Leve si le serveur est injoignable (l'appelant doit ignorer l'exception :
      on garde alors la derniere config connue).
    """
    url = cfg["server_url"].rstrip("/") + "/api/agent-config"
    resp = requests.get(url, headers={"X-API-Key": cfg["api_key"]}, timeout=15)
    resp.raise_for_status()
    remote = resp.json()

    applied = {}
    for key in _BOUNDS:
        if key not in remote:
            continue
        try:
            value = _clamp(key, remote[key])
        except (TypeError, ValueError):
            continue
        if cfg.get(key) != value:
            cfg[key] = value          # appliquee a chaud (relue a chaque boucle)
            applied[key] = value

    if applied:
        save_config(applied)          # cache local pour le prochain demarrage
        log(f"Config mise a jour depuis le serveur: {applied}")

    # Top de mise a jour manuel (bouton du dashboard) : si le compteur augmente,
    # on telecharge tout de suite (sans attendre le check periodique de 30 min).
    # La notif "Redemarrer" s'affichera ensuite, une fois l'.exe telecharge.
    global _last_update_signal
    signal = remote.get("update_signal")
    if isinstance(signal, int):
        if _last_update_signal is None:
            _last_update_signal = signal   # 1re lecture : reference, pas de MAJ
        elif signal > _last_update_signal:
            _last_update_signal = signal
            log("Top de mise a jour recu : telechargement immediat.")
            threading.Thread(
                target=update_service.check_and_download, daemon=True
            ).start()

    return applied
