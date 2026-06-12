import ctypes
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

from app.core.session import SessionMode
from app.core.logging import log
from app.services.assigned_projects_service import fetch_assigned_projects
from app.services.register_service import register_employee
from app.services import storage_service
from app.services.update_service import apply_pending_update, is_update_ready
from app.settings.paths import LOGO_PNG
from app.settings.settings import save_config
from app.version import __version__


def _fmt(seconds):
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


_STATUS = {
    SessionMode.STOPPED: "Arrete",
    SessionMode.RUNNING: "En cours",
    SessionMode.PAUSED: "En pause",
}

_STATE_COLORS = {
    SessionMode.STOPPED: "#9ca3af",
    SessionMode.RUNNING: "#22c55e",
    SessionMode.PAUSED: "#f59e0b",
}

_FLOAT_SIZE = 12  # taille de base du temps dans le bandeau flottant (px)
_FLOAT_FONT = ("Segoe UI", _FLOAT_SIZE, "bold")
# Battement (zoom/dezoom) du temps quand le projet est depasse : cycle 13-12-13.
_PULSE_CYCLE = (_FLOAT_SIZE + 1, _FLOAT_SIZE, _FLOAT_SIZE + 1)
_PULSE_HOLD = 6  # frames par palier (80 ms x 6 = ~0,5 s)

_VERSIONS = [f"V{i}" for i in range(1, 11)]
_VERSION_RE = re.compile(r"^[Vv]\d+$")  # V suivi de chiffres : V1, V2, V12...


class AppWindow:
    """Fenetre de controle (thread principal). Deux pages (Accueil / Parametres)
    commutables via la barre de menu. Le worker de capture tourne dans un thread
    de fond.

    Le chrono est **cumulatif par livrable** (client + video + version) : il
    affiche le total deja enregistre + le temps en cours. Selectionner une video
    existante pre-remplit le client et restaure son cumul.
    """

    _ASSIGNED_REFRESH_MS = 20000  # refresh des projets assignes (ms)

    def __init__(self, controller, worker, cfg, on_close):
        self.controller = controller
        self.worker = worker
        self.cfg = cfg
        self.on_close = on_close
        self.assigned_projects = self._load_assigned_projects()
        self._assigned_by_label = {}
        self._overrun = False      # temps prevu depasse -> pulsation
        self._pulse_phase = 0
        # Projets assignes recus en arriere-plan (thread reseau) -> appliques
        # par la boucle UI. None = rien en attente.
        self._pending_assigned = None
        self._update_notified = False  # notif "nouvelle version" deja affichee ?

        self.root = tk.Tk()
        self.root.title("BABCRM - agent")
        self.root.geometry("380x500")
        self.root.resizable(False, False)  # taille fixe
        self.root.protocol("WM_DELETE_WINDOW", self._handle_close)

        self._set_window_icon()
        self._remove_maximize_button()
        self._build_menu()
        self._build_notification()  # barre de notif (en haut, masquee par defaut)
        # Corps : les pages vivent ici, sous la barre de notification.
        self._body = ttk.Frame(self.root)
        self._body.pack(fill="both", expand=True)
        self._build_main_page()
        self._build_settings_page()
        self._build_floating_timer()

        self._update_who()
        self._refresh()
        self._pulse()
        # Refresh periodique des projets assignes (create/update/delete refletes).
        self.root.after(self._ASSIGNED_REFRESH_MS, self._tick_assigned_refresh)

        if not self.cfg.get("employee_name"):
            self._show_settings()
        else:
            self._show_main()

    # --- barre de menu ---

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        menubar.add_command(label="Accueil", command=self._show_main)
        menubar.add_command(label="Paramètres", command=self._show_settings)
        self.root.config(menu=menubar)

    # --- bandeau de notification (reutilisable) ---

    def _build_notification(self):
        """Bandeau bleu en haut de la fenetre : message + action + fermeture.
        Masque par defaut ; affiche via _show_notification()."""
        self._notif_action_cb = None
        bar = tk.Frame(self.root, bg="#1d4ed8")
        self._notif_bar = bar
        self._notif_label = tk.Label(
            bar, bg="#1d4ed8", fg="white", font=("Segoe UI", 9),
            wraplength=230, justify="left", anchor="w",
        )
        self._notif_label.pack(side="left", padx=(10, 6), pady=6)
        tk.Button(
            bar, text="✕", bd=0, relief="flat", bg="#1d4ed8", fg="white",
            activebackground="#1d4ed8", activeforeground="white",
            cursor="hand2", command=self._hide_notification,
        ).pack(side="right", padx=(0, 8))
        self._notif_btn = tk.Button(
            bar, text="", bd=0, relief="flat", bg="white", fg="#1d4ed8",
            activebackground="#e5e7eb", font=("Segoe UI", 9, "bold"),
            cursor="hand2", padx=8, command=self._on_notif_action,
        )  # affiche seulement s'il y a une action

    def _on_notif_action(self):
        if self._notif_action_cb:
            self._notif_action_cb()

    def _show_notification(self, message, action_text=None, action_cb=None):
        self._notif_label.config(text=message)
        self._notif_action_cb = action_cb
        if action_text and action_cb:
            self._notif_btn.config(text=action_text)
            self._notif_btn.pack(side="right", padx=(0, 4), pady=4)
        else:
            self._notif_btn.pack_forget()
        self._notif_bar.pack(side="top", fill="x", before=self._body)

    def _hide_notification(self):
        self._notif_bar.pack_forget()

    def _restart_for_update(self):
        """Applique la mise a jour deja telechargee : ferme proprement puis un
        script remplace l'.exe et relance l'agent (config conservee)."""
        try:
            self.on_close()  # hors-ligne + arret des threads
        except Exception:
            pass
        apply_pending_update()  # ecrit le script de swap puis quitte le process

    # --- pages ---

    def _show_main(self):
        self.settings_frame.pack_forget()
        self._refresh_video_values()
        self.main_frame.pack(fill="both", expand=True)

    def _show_settings(self):
        self.main_frame.pack_forget()
        self.settings_name_var.set(self.cfg.get("employee_name", ""))
        self.settings_frame.pack(fill="both", expand=True)

    def _build_main_page(self):
        f = ttk.Frame(self._body)
        self.main_frame = f

        if self._logo_img is not None:
            tk.Label(f, image=self._logo_img).pack(pady=(10, 0))

        self.who_var = tk.StringVar()
        ttk.Label(f, textvariable=self.who_var).pack(pady=(6, 0))

        if self.assigned_projects is not None:
            self.client_var = self._field(f, "Client", readonly=True)
            self.video_var = self._field(
                f,
                "Nom de la video",
                combo=True,
                values=self._assigned_video_values(),
                readonly=True,
            )
            self._video_box.bind("<<ComboboxSelected>>", self._on_assigned_video_selected)
            self.version_var = self._field(f, "Version", readonly=True)
            if self.assigned_projects:
                first_label = next(iter(self._assigned_by_label))
                self.video_var.set(first_label)
                self._apply_assigned_project(self._assigned_by_label[first_label])
        else:
            self.client_var = self._field(f, "Client")
            self.video_var = self._field(
                f, "Nom de la video", combo=True,
                values=storage_service.distinct_videos(),
            )
            self._video_box.bind("<<ComboboxSelected>>", self._on_video_selected)
            self._video_box.bind("<FocusIn>", lambda _e: self._refresh_video_values())

            self.version_var = self._field(f, "Version", combo=True,
                                           values=_VERSIONS, readonly=True)
            self.version_var.set("V1")

        for var in (self.client_var, self.video_var, self.version_var):
            var.trace_add("write", self._on_context_change)

        # Le chrono n'est plus dans la fenetre : il vit dans le bandeau flottant
        # (haut a droite de l'ecran). On garde juste l'etat ici.
        self.status_var = tk.StringVar(value="Arrete")
        ttk.Label(f, textvariable=self.status_var,
                  font=("Segoe UI", 15, "bold")).pack(pady=(14, 6))

        btns = ttk.Frame(f)
        btns.pack(pady=14)
        self.play_btn = ttk.Button(btns, text="▶ Play", command=self._play)
        self.pause_btn = ttk.Button(btns, text="⏸ Pause", command=self._pause)
        self.stop_btn = ttk.Button(btns, text="⏹ Stop", command=self._stop)
        self.play_btn.grid(row=0, column=0, padx=4)
        self.pause_btn.grid(row=0, column=1, padx=4)
        self.stop_btn.grid(row=0, column=2, padx=4)

    def _build_settings_page(self):
        f = ttk.Frame(self._body)
        self.settings_frame = f

        ttk.Button(f, text="←", width=3, command=self._leave_settings).pack(
            anchor="w", padx=12, pady=(12, 0))
        ttk.Label(f, text="Paramètres", font=("Segoe UI", 15, "bold")).pack(
            pady=(12, 16))

        ttk.Label(f, text="Nom du monteur").pack(anchor="w", padx=16, pady=(0, 2))
        self.settings_name_var = tk.StringVar(value=self.cfg.get("employee_name", ""))
        entry = ttk.Entry(f, textvariable=self.settings_name_var)
        entry.pack(fill="x", padx=16)
        entry.bind("<Return>", lambda _e: self._save_settings())

        ttk.Button(f, text="Enregistrer", command=self._save_settings).pack(pady=18)

        ttk.Label(f, text=f"Version {__version__}").pack(side="bottom", pady=10)

    # --- construction d'un champ ---

    def _field(self, parent, label, combo=False, values=None, readonly=False):
        ttk.Label(parent, text=label).pack(anchor="w", padx=14, pady=(10, 2))
        var = tk.StringVar()
        if combo:
            state = "readonly" if readonly else "normal"
            widget = ttk.Combobox(parent, textvariable=var,
                                  values=values or [], state=state)
        else:
            state = "readonly" if readonly else "normal"
            widget = ttk.Entry(parent, textvariable=var, state=state)
        widget.pack(fill="x", padx=14)
        if label == "Nom de la video":
            self._video_box = widget
        return var

    # --- projets assignes ---

    def _load_assigned_projects(self):
        try:
            return fetch_assigned_projects(self.cfg)
        except Exception as exc:
            log(f"Projets assignes non recuperes (mode local conserve): {exc}")
            return None

    def _assigned_video_values(self):
        self._assigned_by_label = {}
        counts = {}
        for project in self.assigned_projects or []:
            video_name = project["video_name"]
            counts[video_name] = counts.get(video_name, 0) + 1

        for project in self.assigned_projects or []:
            video_name = project["video_name"]
            if counts[video_name] == 1:
                label = video_name
            else:
                label = f"{video_name} - {project['version']} ({project['client']})"
            self._assigned_by_label[label] = project
        return list(self._assigned_by_label)

    def _apply_assigned_project(self, project):
        self.client_var.set(project["client"])
        self.version_var.set(project["version"])
        self.controller.update_context(
            client=project["client"],
            project=project["video_name"],
            version=project["version"],
        )
        self.worker.wake()

    def _on_assigned_video_selected(self, _event=None):
        project = self._assigned_by_label.get(self.video_var.get())
        if project:
            self._apply_assigned_project(project)

    def _selected_assigned_project(self):
        if self.assigned_projects is None:
            return None
        return self._assigned_by_label.get(self.video_var.get())

    # --- refresh periodique des projets assignes (auto) ---

    def _tick_assigned_refresh(self):
        """Planifie une recuperation reseau en arriere-plan, puis se replanifie.
        Inactif en mode local (serveur injoignable au demarrage)."""
        if self.assigned_projects is not None:
            threading.Thread(target=self._fetch_assigned_bg, daemon=True).start()
        self.root.after(self._ASSIGNED_REFRESH_MS, self._tick_assigned_refresh)

    def _fetch_assigned_bg(self):
        """Thread reseau : depose le resultat ; la boucle UI l'applique. En cas
        d'echec on ne touche a rien (on garde la liste actuelle)."""
        try:
            self._pending_assigned = fetch_assigned_projects(self.cfg)
        except Exception:
            pass

    def _apply_assigned_refresh(self, projects):
        """Applique (sur le thread UI) une nouvelle liste de projets assignes :
        ajout/maj/suppression refletes, sans perturber une session en cours."""
        if self.assigned_projects is None or projects is None:
            return
        current = self.video_var.get()
        self.assigned_projects = projects
        values = self._assigned_video_values()  # reconstruit _assigned_by_label
        self._video_box["values"] = values
        running = self.controller.snapshot()["mode"] != SessionMode.STOPPED

        if current in self._assigned_by_label:
            # Selection toujours valide : le temps prevu eventuellement modifie
            # est repris automatiquement (via _selected_assigned_project). A
            # l'arret, on re-applique au cas ou client/version auraient change.
            if not running:
                self._apply_assigned_project(self._assigned_by_label[current])
            return

        # Selection disparue (projet supprime/renomme).
        if running:
            return  # ne pas perturber la session en cours
        if values:
            self.video_var.set(values[0])
            self._apply_assigned_project(self._assigned_by_label[values[0]])
        else:
            self.video_var.set("")
            self.client_var.set("")
            self.version_var.set("")

    # --- fenetre : icone + suppression bouton Agrandir ---

    def _set_window_icon(self):
        self._logo_img = None
        try:
            self._icon_img = tk.PhotoImage(file=LOGO_PNG)
            self.root.iconphoto(True, self._icon_img)
            self._logo_img = self._icon_img.subsample(4, 4)  # logo large ~128x70 px
        except Exception:
            pass

    def _remove_maximize_button(self):
        """Retire le bouton Agrandir de la barre de titre (Windows uniquement)."""
        if sys.platform != "win32":
            return
        try:
            GWL_STYLE = -16
            WS_MAXIMIZEBOX = 0x00010000
            # SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED
            SWP = 0x0001 | 0x0002 | 0x0004 | 0x0020
            self.root.update_idletasks()
            user32 = ctypes.windll.user32
            hwnd = user32.GetParent(self.root.winfo_id())
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            user32.SetWindowLongW(hwnd, GWL_STYLE, style & ~WS_MAXIMIZEBOX)
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP)
        except Exception:
            pass

    # --- timer flottant (overlay verrouille, haut a droite de l'ecran) ---

    def _build_floating_timer(self):
        """Petit bandeau chrono toujours au-dessus, ancre en haut a droite de
        l'ecran. Verrouille : pas de deplacement ni de fermeture ; visible
        jusqu'a la fermeture de l'application (detruit avec la fenetre)."""
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)        # pas de barre de titre
        win.attributes("-topmost", True)  # au-dessus de tout
        try:
            win.attributes("-alpha", 0.95)
        except Exception:
            pass

        bg = "#111827"
        frame = tk.Frame(win, bg=bg, padx=12, pady=7, highlightthickness=1,
                         highlightbackground="#374151")
        frame.pack()
        self._float_dot = tk.Label(frame, text="●", fg="#9ca3af", bg=bg,
                                   font=("Segoe UI", 11))
        self._float_dot.pack(side="left", padx=(0, 6))
        self._float_status = tk.Label(frame, text="Arrete", fg="#e5e7eb", bg=bg,
                                      font=("Segoe UI", 9))
        self._float_status.pack(side="left", padx=(0, 8))
        self._float_time = tk.Label(frame, text="00:00:00", fg="#ffffff", bg=bg,
                                    font=_FLOAT_FONT)
        self._float_time.pack(side="left")

        # Position fixe : coin haut droit de l'ecran (verrouille).
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        win.geometry(f"+{sw - win.winfo_width() - 16}+16")
        self.floating = win

    def _anchor_floating(self):
        """Re-cale le bandeau sur le bord droit de l'ecran (sa largeur change
        selon le texte : 'Restant ...' / 'Depasse ...' / chrono)."""
        self.floating.update_idletasks()
        sw = self.floating.winfo_screenwidth()
        self.floating.geometry(f"+{sw - self.floating.winfo_width() - 16}+16")

    def _update_floating(self, mode, seconds):
        """Affiche le temps RESTANT du projet (vert/orange, rouge si depasse) ;
        a defaut d'estimation, affiche le chrono ecoule. Couleurs claires
        adaptees au fond sombre du bandeau."""
        self._float_dot.config(fg=_STATE_COLORS[mode])
        self._float_status.config(text=_STATUS[mode])

        assigned = self._selected_assigned_project()
        estimated = assigned.get("estimated_duration_sec", 0) if assigned else 0
        if estimated and estimated > 0:
            remaining = estimated - seconds
            if remaining < 0:
                self._overrun = True  # seul le temps pulse (zoom/dezoom)
                self._float_time.config(text=f"Dépassé {_fmt(-remaining)}",
                                        fg="#f87171")
            else:
                self._overrun = False
                color = "#fbbf24" if remaining <= 600 else "#4ade80"  # orange/vert
                self._float_time.config(text=f"Restant {_fmt(remaining)}",
                                        fg=color, font=_FLOAT_FONT)
        else:
            self._overrun = False
            self._float_time.config(text=_fmt(seconds), fg="#ffffff",
                                    font=_FLOAT_FONT)
        self._anchor_floating()

    # --- configuration (nom du monteur) ---

    def _update_who(self):
        name = self.cfg.get("employee_name") or "(non configure)"
        self.who_var.set(f"Monteur : {name}")

    def _save_settings(self):
        name = self.settings_name_var.get().strip()
        if not name:
            messagebox.showwarning("Nom requis", "Renseigne le nom du monteur.")
            return
        save_config({"employee_name": name})
        self.cfg["employee_name"] = name
        self.controller.update_context(name=name)
        self._announce_employee()  # visible/assignable de suite sur la plateforme
        self._update_who()
        self._show_main()

    def _announce_employee(self):
        """Annonce le monteur tout de suite (thread reseau), puis recupere ses
        projets assignes -> visible et assignable sans attendre d'activite."""
        def work():
            try:
                register_employee(self.cfg)
            except Exception as exc:
                log(f"Enregistrement non envoye: {exc}")
            if self.assigned_projects is not None:
                try:
                    self._pending_assigned = fetch_assigned_projects(self.cfg)
                except Exception:
                    pass

        threading.Thread(target=work, daemon=True).start()

    def _leave_settings(self):
        if not self.cfg.get("employee_name"):
            messagebox.showwarning("Nom requis",
                                   "Renseigne ton nom avant de continuer.")
            return
        self._show_main()

    # --- selection / contexte ---

    def _refresh_video_values(self):
        if self.assigned_projects is not None:
            return
        self._video_box["values"] = storage_service.distinct_videos()

    def _on_video_selected(self, _event=None):
        if self.assigned_projects is not None:
            return
        # Selectionner une video existante pre-remplit son client.
        client = storage_service.client_for_video(self.video_var.get().strip())
        if client:
            self.client_var.set(client)

    def _on_context_change(self, *_):
        # En mode assigne, video_var contient le LABEL affiche (qui peut differer
        # du nom reel quand un meme nom a plusieurs versions) : on pousse les
        # vraies valeurs du projet, sinon le live du chrono ne correspond jamais.
        assigned = self._selected_assigned_project()
        if assigned is not None:
            client = assigned["client"]
            project = assigned["video_name"]
            version = assigned["version"]
        else:
            client = self.client_var.get()
            project = self.video_var.get()
            version = self.version_var.get()
        self.controller.update_context(
            client=client, project=project, version=version
        )
        self.worker.wake()  # cloture/ouvre le segment sur le nouveau livrable

    def _displayed_seconds(self):
        """Chrono cumulatif du livrable selectionne : total enregistre + le
        temps du segment en cours (s'il porte sur ce meme livrable)."""
        assigned = self._selected_assigned_project()
        client = assigned["client"] if assigned else self.client_var.get().strip()
        video = assigned["video_name"] if assigned else self.video_var.get().strip()
        version = assigned["version"] if assigned else self.version_var.get().strip()
        base = storage_service.accumulated_seconds(client, video, version) if video else 0

        live = 0
        if self.controller.snapshot()["mode"] == SessionMode.RUNNING:
            cur = self.worker.live_snapshot()
            if (cur and not cur["paused"] and cur["client"] == client
                    and cur["video"] == video and cur["version"] == version):
                live = time.monotonic() - cur["started"]
        return base + live

    # --- actions ---

    def _play(self):
        if not self.cfg.get("employee_name"):
            messagebox.showwarning(
                "Configuration requise",
                "Renseigne ton nom dans Paramètres avant de demarrer.",
            )
            self._show_settings()
            return
        client = self.client_var.get().strip()
        video = self.video_var.get().strip()
        version = self.version_var.get().strip()
        if not client or not video:
            if self.assigned_projects == []:
                messagebox.showwarning(
                    "Aucun projet assigne",
                    "Aucun projet n'est assigne a ce monteur.",
                )
                return
            messagebox.showwarning(
                "Champs requis",
                "Selectionne un projet avant de demarrer.",
            )
            return
        if self.assigned_projects is not None:
            project = self._selected_assigned_project()
            if not project:
                messagebox.showwarning(
                    "Projet requis",
                    "Selectionne un projet assigne avant de demarrer.",
                )
                return
            self._apply_assigned_project(project)
        if not _VERSION_RE.match(version):
            messagebox.showwarning(
                "Version invalide",
                "La version doit etre au format V1, V2, V3... (ex. V2).",
            )
            return
        self.version_var.set(version.upper())  # normalise : v2 -> V2
        self.controller.play()
        self.worker.wake()

    def _pause(self):
        self.controller.pause()
        self.worker.wake()

    def _stop(self):
        self.controller.stop()
        self.worker.wake()
        self._refresh_video_values()

    def _handle_close(self):
        if messagebox.askokcancel("Quitter", "Arreter le suivi et quitter ?"):
            self.controller.stop()
            self.on_close()
            self.root.destroy()

    # --- battement (zoom/dezoom) du temps quand depasse ---

    def _pulse(self):
        """Battement zoom/dezoom (13-12-13) du temps du bandeau quand depasse."""
        if self._overrun:
            step = (self._pulse_phase // _PULSE_HOLD) % len(_PULSE_CYCLE)
            self._float_time.config(font=("Segoe UI", _PULSE_CYCLE[step], "bold"))
            self._pulse_phase += 1
        else:
            self._pulse_phase = 0
        self.root.after(80, self._pulse)

    # --- rafraichissement periodique (1 s) ---

    def _refresh(self):
        # Applique une mise a jour des projets assignes recue en arriere-plan.
        if self._pending_assigned is not None:
            projects, self._pending_assigned = self._pending_assigned, None
            self._apply_assigned_refresh(projects)

        # Nouvelle version telechargee -> on propose le redemarrage (une fois).
        if not self._update_notified and is_update_ready():
            self._update_notified = True
            self._show_notification(
                "Une nouvelle version est prête.",
                action_text="Redémarrer",
                action_cb=self._restart_for_update,
            )

        mode = self.controller.snapshot()["mode"]
        seconds = self._displayed_seconds()
        self.status_var.set(_STATUS[mode])
        self._update_floating(mode, seconds)

        running = mode == SessionMode.RUNNING
        stopped = mode == SessionMode.STOPPED
        self.play_btn.state(["disabled"] if running else ["!disabled"])
        self.pause_btn.state(["!disabled"] if running else ["disabled"])
        self.stop_btn.state(["disabled"] if stopped else ["!disabled"])

        self.root.after(1000, self._refresh)

    def run(self):
        self.root.mainloop()
