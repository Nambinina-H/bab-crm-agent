import getpass
import json
import os
import socket

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.logging import log
from app.settings.paths import CONFIG_PATH, ENV_PATH

# L'identite affichee (nom) est saisie dans l'UI ; seule la cle technique stable
# (employee_id, basee sur la machine) vit dans la config.
DEFAULT_CONFIG = {
    "server_url": "http://localhost:8000",
    "api_key": "CHANGE_ME",
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
