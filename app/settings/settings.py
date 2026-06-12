import getpass
import json
import os
import socket

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.logging import log
from app.settings.paths import CONFIG_PATH, ENV_PATH

# Config injectee au BUILD par la CI (app/_build_config.py, jamais committe) :
# l'.exe publie marche sans .env. Absent en dev/local -> placeholders ci-dessous.
# Un .env reste prioritaire au runtime (voir load_config) pour les tests.
try:
    from app import _build_config as _bc

    _BUILD_SERVER_URL = getattr(_bc, "SERVER_URL", "") or ""
    _BUILD_API_KEY = getattr(_bc, "API_KEY", "") or ""
except Exception:
    _BUILD_SERVER_URL = ""
    _BUILD_API_KEY = ""

# L'identite affichee (nom) est saisie dans l'UI ; seule la cle technique stable
# (employee_id, basee sur la machine) vit dans la config.
DEFAULT_CONFIG = {
    "server_url": _BUILD_SERVER_URL or "http://localhost:8000",
    "api_key": _BUILD_API_KEY or "CHANGE_ME",
    "employee_id": f"{getpass.getuser()}@{socket.gethostname()}",
    "employee_name": "",  # saisi via l'ecran Configuration de l'app
    "sample_interval_sec": 5,
    "idle_threshold_sec": 120,
    "sync_interval_sec": 60,
    "sync_batch_size": 500,
}

# Cles ecrites dans config.json (les secrets api_key/server_url restent dans
# .env ; employee_id est derive de la machine au runtime).
_PERSISTED_KEYS = (
    "employee_name", "sample_interval_sec", "idle_threshold_sec",
    "sync_interval_sec", "sync_batch_size",
)


class Secrets(BaseSettings):
    """Secrets de connexion, lus depuis agent/.env (ou variables d'env).

    Variables reconnues : AGENT_API_KEY, AGENT_SERVER_URL.
    Priorite : variable d'environnement > agent/.env > rien.
    """

    api_key: str | None = None
    server_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        env_prefix="AGENT_",
        extra="ignore",
    )


def load_config():
    cfg = dict(DEFAULT_CONFIG)

    # 1. config.json : reglages (intervalles, seuils).
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as exc:
            log(f"Config illisible, valeurs par defaut utilisees: {exc}")
    else:
        try:
            defaults = {k: DEFAULT_CONFIG[k] for k in _PERSISTED_KEYS}
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(defaults, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # 2. Secrets depuis .env : prioritaires sur config.json.
    secrets = Secrets()
    if secrets.api_key:
        cfg["api_key"] = secrets.api_key
    if secrets.server_url:
        cfg["server_url"] = secrets.server_url

    return cfg


def save_config(updates):
    """Persiste des reglages dans config.json (fusion avec l'existant).

    Sert a memoriser le nom du monteur saisi dans l'ecran Configuration. Ne
    touche pas aux secrets (qui vivent dans .env), seulement aux cles fournies.
    """
    data = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data.update(updates)
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        log(f"Ecriture config impossible: {exc}")
