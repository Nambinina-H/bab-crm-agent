"""Bandeau flottant verrouille en haut a droite de l'ecran.

Affiche le temps RESTANT du projet (vert/orange, rouge si depasse) ; a defaut
d'estimation, affiche le chrono ecoule. Toujours au-dessus des autres fenetres,
sans deplacement ni fermeture, jusqu'a la fermeture de l'application.

Composant pilote par l'exterieur : update(mode, seconds, estimated) a chaque
rafraichissement ; il gere lui-meme son ancrage.
"""
import tkinter as tk

from app.ui.theme import (
    FLOAT_FONT,
    STATE_COLORS,
    STATUS,
    fmt,
)

_BG = "#111827"


class FloatingTimer:
    def __init__(self, root):
        win = tk.Toplevel(root)
        win.overrideredirect(True)        # pas de barre de titre
        win.attributes("-topmost", True)  # au-dessus de tout
        try:
            win.attributes("-alpha", 0.95)
        except Exception:
            pass

        frame = tk.Frame(win, bg=_BG, padx=12, pady=7, highlightthickness=1,
                         highlightbackground="#374151")
        frame.pack()
        self._dot = tk.Label(frame, text="●", fg="#9ca3af", bg=_BG,
                             font=("Segoe UI", 11))
        self._dot.pack(side="left", padx=(0, 6))
        self._status = tk.Label(frame, text="Arrete", fg="#e5e7eb", bg=_BG,
                                font=("Segoe UI", 9))
        self._status.pack(side="left", padx=(0, 8))
        self._time = tk.Label(frame, text="00:00:00", fg="#ffffff", bg=_BG,
                              font=FLOAT_FONT)
        self._time.pack(side="left")

        self._win = win
        self._anchor()

    def _anchor(self):
        """Re-cale le bandeau sur le bord droit de l'ecran (sa largeur change
        selon le texte : 'Restant ...' / 'Depasse ...' / chrono)."""
        self._win.update_idletasks()
        sw = self._win.winfo_screenwidth()
        self._win.geometry(f"+{sw - self._win.winfo_width() - 16}+16")

    def update(self, mode, seconds, estimated):
        """Met a jour l'affichage. `estimated` : temps prevu du projet (s) ou 0."""
        self._dot.config(fg=STATE_COLORS[mode])
        self._status.config(text=STATUS[mode])

        if estimated and estimated > 0:
            remaining = estimated - seconds
            if remaining < 0:
                # Temps depasse : simplement en rouge (sans clignotement).
                self._time.config(text=f"Dépassé {fmt(-remaining)}",
                                  fg="#f87171", font=FLOAT_FONT)
            else:
                color = "#fbbf24" if remaining <= 600 else "#4ade80"  # orange/vert
                self._time.config(text=f"Restant {fmt(remaining)}",
                                  fg=color, font=FLOAT_FONT)
        else:
            self._time.config(text=fmt(seconds), fg="#ffffff", font=FLOAT_FONT)
        self._anchor()
