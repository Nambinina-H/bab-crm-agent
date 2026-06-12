"""Bandeau de notification reutilisable (haut de la fenetre).

Message + bouton d'action optionnel + fermeture. Masque par defaut ; on
l'affiche via show(...) et on le cache via hide(). Utilise par exemple pour
proposer le redemarrage quand une nouvelle version est telechargee.
"""
import tkinter as tk

_BG = "#1d4ed8"


class NotificationBar:
    def __init__(self, root, before):
        """`root` : fenetre parente. `before` : widget au-dessus duquel le
        bandeau s'insere (pour rester en haut, sous la barre de menu)."""
        self._before = before
        self._action_cb = None

        bar = tk.Frame(root, bg=_BG)
        self._bar = bar
        self._label = tk.Label(
            bar, bg=_BG, fg="white", font=("Segoe UI", 9),
            wraplength=230, justify="left", anchor="w",
        )
        self._label.pack(side="left", padx=(10, 6), pady=6)
        tk.Button(
            bar, text="✕", bd=0, relief="flat", bg=_BG, fg="white",
            activebackground=_BG, activeforeground="white",
            cursor="hand2", command=self.hide,
        ).pack(side="right", padx=(0, 8))
        self._btn = tk.Button(
            bar, text="", bd=0, relief="flat", bg="white", fg=_BG,
            activebackground="#e5e7eb", font=("Segoe UI", 9, "bold"),
            cursor="hand2", padx=8, command=self._on_action,
        )  # affiche seulement s'il y a une action

    def _on_action(self):
        if self._action_cb:
            self._action_cb()

    def show(self, message, action_text=None, action_cb=None):
        self._label.config(text=message)
        self._action_cb = action_cb
        if action_text and action_cb:
            self._btn.config(text=action_text)
            self._btn.pack(side="right", padx=(0, 4), pady=4)
        else:
            self._btn.pack_forget()
        self._bar.pack(side="top", fill="x", before=self._before)

    def hide(self):
        self._bar.pack_forget()
