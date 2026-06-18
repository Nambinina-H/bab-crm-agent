"""Constantes d'interface partagees (libelles, couleurs, polices, formats)."""
import re
import tkinter as tk
from tkinter import ttk

from app.core.session import SessionMode

# --- Palette UI (teal + navy), style plat, sans coins arrondis ---------------
FONT = "Segoe UI"
ACCENT = "#0E8088"        # teal (boutons d'action)
ACCENT_HOVER = "#0F676E"
NAVY = "#0E2638"          # texte fort / bandeaux sombres
TEXT = "#39434D"          # texte courant
TEXT_MUTED = "#6C7884"    # texte secondaire
BORDER = "#DBE1E7"        # bordure
BORDER_SOFT = "#E6EAEF"
INSET = "#F1F4F7"         # fond des champs en lecture seule
CARD = "#FFFFFF"          # fond de la fenetre / contenu
GREEN = "#1F9D63"         # Play actif
ORANGE = "#E08A00"        # Pause actif
RED = "#D92D20"           # Stop actif
DISABLED = "#C2CAD3"      # texte d'un bouton inactif
SOFT_BG = "#E7F3F4"       # bouton "terminer" (teal clair)
SOFT_TEXT = "#0F676E"

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

VERSIONS = [f"V{i}" for i in range(1, 11)]
VERSION_RE = re.compile(r"^[Vv]\d+$")  # V suivi de chiffres : V1, V2, V12...

# Roles metiers proposes dans l'agent (memes valeurs que la page Collaborateurs).
EMPLOYEE_ROLES = [
    "Monteur",
    "Manager",
    "Admin",
    "Générateur d'images",
    "Scénariste",
    "Informaticien",
    "IA",
    "Stagiaire",
]


def fmt(seconds):
    """Secondes -> 'HH:MM:SS'."""
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def setup_style(root):
    """Applique le theme plat (clam + palette) a toute la fenetre. A appeler une
    fois, juste apres la creation de la racine, avant de construire les widgets.
    Ne touche qu'a l'apparence : aucun comportement modifie."""
    root.configure(bg=CARD)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")  # seul theme ttk qui respecte fond/bordure a plat
    except tk.TclError:
        pass

    base = (FONT, 10)
    style.configure(
        ".", background=CARD, foreground=TEXT, font=base, fieldbackground=CARD,
        bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD, troughcolor=INSET,
        focuscolor=CARD,
    )
    style.configure("TFrame", background=CARD)
    style.configure("TLabel", background=CARD, foreground=TEXT, font=base)
    # Libelle de champ : petit, gris.
    style.configure("Field.TLabel", foreground=TEXT_MUTED, font=(FONT, 9, "bold"))
    style.configure("Who.TLabel", foreground=TEXT_MUTED, font=(FONT, 9))
    style.configure("Status.TLabel", foreground=NAVY, font=(FONT, 13, "bold"))
    style.configure("Title.TLabel", foreground=NAVY, font=(FONT, 16, "bold"))

    # Champs texte (Entry) : blanc, gris en lecture seule.
    style.configure("TEntry", fieldbackground=CARD, foreground=TEXT,
                    bordercolor=BORDER, insertcolor=TEXT, padding=6)
    style.map(
        "TEntry",
        fieldbackground=[("readonly", INSET), ("disabled", INSET)],
        foreground=[("disabled", TEXT_MUTED)],
        bordercolor=[("focus", ACCENT)],
    )
    # Listes deroulantes : champ blanc (interactif) meme en readonly.
    style.configure("TCombobox", fieldbackground=CARD, background=CARD,
                    foreground=TEXT, bordercolor=BORDER, arrowcolor=TEXT_MUTED,
                    padding=6)
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", CARD), ("disabled", INSET)],
        foreground=[("disabled", TEXT_MUTED)],
        bordercolor=[("focus", ACCENT)],
        arrowcolor=[("disabled", BORDER)],
    )
    # Popup de la liste deroulante (Listbox sous-jacente).
    root.option_add("*TCombobox*Listbox.background", CARD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.font", f"{{{FONT}}} 10")

    # Bouton ttk neutre (ex. fleche retour) : plat.
    style.configure("TButton", background=CARD, foreground=TEXT,
                    bordercolor=BORDER, relief="flat", padding=6)
    style.map("TButton", background=[("active", INSET)],
              bordercolor=[("focus", ACCENT)])

    # Case a cocher (page Parametres) : fond blanc, coche teal.
    style.configure("TCheckbutton", background=CARD, foreground=TEXT,
                    focuscolor=CARD)
    style.map("TCheckbutton",
              background=[("active", CARD)],
              indicatorcolor=[("selected", ACCENT)])


def paint_control(btn, fill, *, active, enabled):
    """Peint un bouton de controle (tk.Button) : rempli de `fill` s'il represente
    l'etat courant, blanc sinon, grise si desactive. Bloque le clic via l'etat
    mais garde notre couleur (disabledforeground)."""
    if active:
        bg, fg = fill, "#ffffff"
    elif enabled:
        bg, fg = CARD, TEXT
    else:
        bg, fg = CARD, DISABLED
    btn.config(
        bg=bg, fg=fg, activebackground=bg, activeforeground=fg,
        disabledforeground=fg, highlightbackground=BORDER if not active else fill,
        state=("normal" if enabled else "disabled"),
    )
