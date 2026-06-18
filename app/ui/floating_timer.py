"""Bandeau flottant verrouille en haut a droite de l'ecran.

Affiche le temps RESTANT du projet (vert/orange, rouge si depasse) ; a defaut
d'estimation, affiche le chrono ecoule. Toujours au-dessus des autres fenetres.

Quand une mise a jour est prete, il montre un rappel **toujours visible** :
- en Play/Pause : le compteur reste, le rappel s'affiche dessous ;
- a l'arret : le rappel remplace le compteur.
Cliquer le rappel redemarre l'app (callback `on_restart`).

Composant pilote par l'exterieur : update(mode, seconds, estimated, update_ready)
a chaque rafraichissement ; il gere lui-meme son ancrage.
"""
import tkinter as tk

from app.core.session import SessionMode
from app.ui.theme import (
    FLOAT_FONT,
    NAVY,
    STATE_COLORS,
    STATUS,
    fmt,
)

_BG = NAVY             # navy de la palette
_BORDER = "#1B3A52"    # bordure navy plus claire
_NUDGE_FG = "#fbbf24"  # ambre : attire l'oeil sans alarmer


class FloatingTimer:
    def __init__(self, root, on_restart=None):
        self._on_restart = on_restart
        self._layout = "normal"  # "normal" | "under" | "replace"

        win = tk.Toplevel(root)
        win.overrideredirect(True)        # pas de barre de titre
        win.attributes("-topmost", True)  # au-dessus de tout
        try:
            win.attributes("-alpha", 0.95)
        except Exception:
            pass

        outer = tk.Frame(win, bg=_BG, padx=12, pady=7, highlightthickness=1,
                         highlightbackground=_BORDER)
        outer.pack()
        row = tk.Frame(outer, bg=_BG)
        row.pack(fill="x")
        self._dot = tk.Label(row, text="●", fg="#9ca3af", bg=_BG,
                             font=("Segoe UI", 11))
        self._dot.pack(side="left", padx=(0, 6))
        self._status = tk.Label(row, text="Arrete", fg="#e5e7eb", bg=_BG,
                                font=("Segoe UI", 9))
        self._status.pack(side="left", padx=(0, 8))
        self._time = tk.Label(row, text="00:00:00", fg="#ffffff", bg=_BG,
                              font=FLOAT_FONT)
        self._time.pack(side="left")
        # Rappel de mise a jour (cache par defaut), cliquable pour redemarrer.
        self._nudge = tk.Label(outer, text="", fg=_NUDGE_FG, bg=_BG,
                               font=("Segoe UI", 9, "bold"), cursor="hand2")
        self._nudge.bind("<Button-1>", lambda _e: self._restart())

        self._win = win
        self._row = row
        self._anchor()

    def _restart(self):
        if self._on_restart:
            self._on_restart()

    def _anchor(self):
        """Re-cale le bandeau sur le bord droit de l'ecran (sa largeur/hauteur
        change selon le texte : compteur / rappel)."""
        self._win.update_idletasks()
        sw = self._win.winfo_screenwidth()
        self._win.geometry(f"+{sw - self._win.winfo_width() - 16}+16")

    def update(self, mode, seconds, estimated, update_ready=False):
        """Met a jour l'affichage. `estimated` : temps prevu du projet (s) ou 0.
        `update_ready` : une mise a jour est telechargee et attend un redemarrage.
        """
        self._dot.config(fg=STATE_COLORS[mode])
        self._status.config(text=STATUS[mode])

        if estimated and estimated > 0:
            remaining = estimated - seconds
            if remaining < 0:
                self._time.config(text=f"Dépassé {fmt(-remaining)}",
                                  fg="#f87171", font=FLOAT_FONT)
            else:
                color = "#fbbf24" if remaining <= 600 else "#4ade80"  # orange/vert
                self._time.config(text=f"Restant {fmt(remaining)}",
                                  fg=color, font=FLOAT_FONT)
        else:
            self._time.config(text=fmt(seconds), fg="#ffffff", font=FLOAT_FONT)

        # Disposition : normal / rappel dessous (play-pause) / rappel a la place
        # (arret). On ne re-agence que si l'etat change (pas de scintillement).
        if update_ready:
            desired = "replace" if mode == SessionMode.STOPPED else "under"
        else:
            desired = "normal"
        if desired != self._layout:
            self._layout = desired
            self._relayout(desired)
        if update_ready:
            self._nudge.config(
                text="Mise à jour prête - cliquez pour redémarrer"
                if desired == "replace"
                else "Mise à jour prête - redémarrer"
            )

        self._anchor()

    def _relayout(self, desired):
        self._nudge.pack_forget()
        self._time.pack_forget()
        if desired == "normal":
            self._time.pack(side="left")
        elif desired == "under":
            self._time.pack(side="left")
            self._nudge.pack(side="top", pady=(5, 0))
        elif desired == "replace":
            self._nudge.pack(side="top", pady=(2, 0))