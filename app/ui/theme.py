"""Constantes d'interface partagees (libelles, couleurs, polices, formats)."""
import re

from app.core.session import SessionMode

STATUS = {
    SessionMode.STOPPED: "Arrete",
    SessionMode.RUNNING: "En cours",
    SessionMode.PAUSED: "En pause",
}

STATE_COLORS = {
    SessionMode.STOPPED: "#9ca3af",
    SessionMode.RUNNING: "#22c55e",
    SessionMode.PAUSED: "#f59e0b",
}

FLOAT_SIZE = 12  # taille de base du temps dans le bandeau flottant (px)
FLOAT_FONT = ("Segoe UI", FLOAT_SIZE, "bold")
# Battement (zoom/dezoom) du temps quand le projet est depasse : cycle 13-12-13.
PULSE_CYCLE = (FLOAT_SIZE + 1, FLOAT_SIZE, FLOAT_SIZE + 1)
PULSE_HOLD = 6  # frames par palier (80 ms x 6 = ~0,5 s)

VERSIONS = [f"V{i}" for i in range(1, 11)]
VERSION_RE = re.compile(r"^[Vv]\d+$")  # V suivi de chiffres : V1, V2, V12...


def fmt(seconds):
    """Secondes -> 'HH:MM:SS'."""
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"
