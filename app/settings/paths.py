import os
import sys

if getattr(sys, "frozen", False):
    # Lance depuis un .exe PyInstaller : les fichiers (config, .env, base) sont
    # a cote de l'executable. Les assets embarques sont, eux, extraits dans
    # le dossier temporaire _MEIPASS.
    BASE_DIR = os.path.dirname(sys.executable)
    ASSETS_DIR = os.path.join(getattr(sys, "_MEIPASS", BASE_DIR), "assets")
else:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
ENV_PATH = os.path.join(BASE_DIR, ".env")
DB_PATH = os.path.join(BASE_DIR, "local_buffer.db")
LOG_PATH = os.path.join(BASE_DIR, "agent.log")
HISTORY_PATH = os.path.join(BASE_DIR, "projects_history.json")
LOGO_PNG = os.path.join(ASSETS_DIR, "logo.png")
