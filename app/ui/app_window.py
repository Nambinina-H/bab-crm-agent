import ctypes
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

from app.core.session import SessionMode
from app.core.logging import log
from app.services.assigned_projects_service import (
    complete_project,
    fetch_assigned_projects,
)
from app.services.register_service import register_employee, set_role
from app.services import autostart_service, storage_service
from app.services.update_service import is_update_ready, restart_for_update
from app.settings.paths import LOGO_PNG
from app.settings.settings import derive_employee_id, save_config
from app.ui.floating_timer import FloatingTimer
from app.ui.notification import NotificationBar
from app.ui.theme import (
    ACCENT,
    ACCENT_HOVER,
    BORDER_SOFT,
    CARD,
    DISABLED,
    EMPLOYEE_ROLES,
    FONT,
    GREEN,
    NAVY,
    ORANGE,
    RED,
    SOFT_BG,
    SOFT_TEXT,
    STATE_COLORS,
    STATUS,
    TEXT,
    TEXT_MUTED,
    VERSIONS,
    VERSION_RE,
    paint_control,
    setup_style,
)
from app.version import __version__


class AppWindow:
    """Fenetre de controle (thread principal) — ORCHESTRATEUR.

    Assemble les pages (Accueil / Profil), le bandeau de notification et le
    timer flottant (composants `ui/`), cable les actions vers le `controller` /
    les services, et tient la boucle de rafraichissement (1 s). Aucune logique
    reseau/DB ici : tout passe par le controller et les services.

    Le chrono est cumulatif par livrable (client + video + version) : total deja
    enregistre + temps en cours.
    """

    _ASSIGNED_REFRESH_MS = 5000  # refresh des projets assignes (ms) : reactif aux
    # changements cote serveur (assignation, terminer/rouvrir) sans trop solliciter.
    _AUTO_UPDATE_IDLE_SEC = 180  # MAJ appliquee seule apres ce temps a l'arret
    # (les postes "juste ouverts" se mettent a jour sans rien faire ; ceux qui
    # travaillent ne sont jamais coupes).

    def __init__(self, controller, worker, cfg, on_close):
        self.controller = controller
        self.worker = worker
        self.cfg = cfg
        self.on_close = on_close
        self.assigned_projects = self._load_assigned_projects()
        self._assigned_by_label = {}
        # Projets assignes recus en arriere-plan (thread reseau) -> appliques
        # par la boucle UI. None = rien en attente.
        self._pending_assigned = None
        self._pending_error = None   # message d'erreur a afficher (thread -> UI)
        self._update_notified = False  # notif "nouvelle version" deja affichee ?
        self._update_idle_since = None  # depuis quand a l'arret avec une MAJ prete
        # Delai d'auto-MAJ a l'arret (override par env pour tester en local).
        self._auto_update_idle_sec = int(
            os.environ.get("AGENT_AUTO_UPDATE_IDLE_SEC") or self._AUTO_UPDATE_IDLE_SEC
        )

        self.root = tk.Tk()
        self.root.title("BABCRM - agent")
        self.root.geometry("380x520")
        self.root.resizable(False, False)  # taille fixe
        self.root.protocol("WM_DELETE_WINDOW", self._handle_close)

        setup_style(self.root)  # theme plat (clam + palette teal/navy)
        self._set_window_icon()
        self._remove_maximize_button()

        # Onglets + fin separateur, puis le corps (les pages) plein cadre.
        self._build_tabs(self.root)
        tk.Frame(self.root, bg=BORDER_SOFT, height=1).pack(fill="x")

        # Corps : les pages vivent ici ; le bandeau de notif s'insere au-dessus.
        self._body = tk.Frame(self.root, bg=CARD)
        self._body.pack(fill="both", expand=True)
        self._notif = NotificationBar(self.root, before=self._body)
        self._build_main_page()
        self._build_settings_page()
        self._build_params_page()
        self._floating = FloatingTimer(self.root, on_restart=self._restart_for_update)

        self._update_who()
        self._refresh()
        # Refresh periodique des projets assignes (create/update/delete refletes).
        self.root.after(self._ASSIGNED_REFRESH_MS, self._tick_assigned_refresh)

        if not self.cfg.get("employee_name"):
            self._show_settings()
        else:
            self._show_main()

    # --- onglets (Accueil / Profil) ---

    def _build_tabs(self, parent):
        bar = tk.Frame(parent, bg=CARD)
        bar.pack(fill="x", padx=18, pady=(12, 0))
        self._tabs = {}
        specs = [("main", "Accueil", self._goto_main),
                 ("settings", "Profil", self._show_settings),
                 ("params", "Paramètres", self._show_params)]
        for key, label, cmd in specs:
            holder = tk.Frame(bar, bg=CARD)
            holder.pack(side="left", padx=(0, 20))
            lbl = tk.Label(holder, text=label, bg=CARD, fg=TEXT_MUTED,
                           font=(FONT, 10, "bold"), cursor="hand2")
            lbl.pack()
            underline = tk.Frame(holder, bg=CARD, height=2)
            underline.pack(fill="x", pady=(5, 0))
            lbl.bind("<Button-1>", lambda _e, c=cmd: c())
            self._tabs[key] = (lbl, underline)

    def _set_active_tab(self, key):
        for k, (lbl, underline) in self._tabs.items():
            on = k == key
            lbl.config(fg=NAVY if on else TEXT_MUTED)
            underline.config(bg=ACCENT if on else CARD)

    def _goto_main(self):
        """Onglet Accueil : exige un nom (comme l'ancien garde de la fleche)."""
        if not self.cfg.get("employee_name"):
            messagebox.showwarning("Nom requis",
                                   "Renseigne ton nom avant de continuer.")
            return
        self._show_main()

    def _restart_for_update(self):
        """Applique la mise a jour (si telechargee) et relance l'agent : ferme
        proprement (hors-ligne + arret des threads) puis un relanceur attend la
        fin du process et redemarre. Marche en prod (swap .exe) comme en dev."""
        try:
            self.on_close()  # hors-ligne + arret des threads
        except Exception:
            pass
        restart_for_update()  # relanceur mutex-safe puis quitte le process

    # --- pages ---

    def _hide_pages(self):
        self.main_frame.pack_forget()
        self.settings_frame.pack_forget()
        self.params_frame.pack_forget()

    def _show_main(self):
        self._hide_pages()
        self._refresh_video_values()
        self._set_active_tab("main")
        self.main_frame.pack(fill="both", expand=True)

    def _show_settings(self):
        self._hide_pages()
        self.settings_name_var.set(self.cfg.get("employee_name", ""))
        self.settings_role_var.set(self.cfg.get("employee_role", ""))
        self._set_active_tab("settings")
        self.settings_frame.pack(fill="both", expand=True)

    def _show_params(self):
        self._hide_pages()
        # Reflete l'etat reel du demarrage automatique (registre).
        self.autostart_var.set(autostart_service.is_enabled())
        self._set_active_tab("params")
        self.params_frame.pack(fill="both", expand=True)

    def _build_main_page(self):
        f = ttk.Frame(self._body)
        self.main_frame = f

        if self._logo_img is not None:
            tk.Label(f, image=self._logo_img, bg=CARD).pack(pady=(14, 4))

        self.who_var = tk.StringVar()
        ttk.Label(f, textvariable=self.who_var, style="Who.TLabel").pack(pady=(2, 0))

        if self.assigned_projects is not None:
            self.client_var = self._field(f, "Client", readonly=True)
            self.video_var = self._field(
                f,
                "Projet",
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
                f, "Projet", combo=True,
                values=storage_service.distinct_videos(),
            )
            self._video_box.bind("<<ComboboxSelected>>", self._on_video_selected)
            self._video_box.bind("<FocusIn>", lambda _e: self._refresh_video_values())

            self.version_var = self._field(f, "Version", combo=True,
                                           values=VERSIONS, readonly=True)
            self.version_var.set("V1")

        for var in (self.client_var, self.video_var, self.version_var):
            var.trace_add("write", self._on_context_change)

        # Le chrono n'est plus dans la fenetre : il vit dans le bandeau flottant
        # (haut a droite de l'ecran). On garde juste l'etat ici.
        self.status_var = tk.StringVar(value="Arrete")
        status_row = tk.Frame(f, bg=CARD)
        status_row.pack(pady=(14, 6))
        self._status_dot = tk.Label(
            status_row, text="●", bg=CARD,
            fg=STATE_COLORS[SessionMode.STOPPED], font=(FONT, 12))
        self._status_dot.pack(side="left", padx=(0, 6))
        self._status_lbl = tk.Label(
            status_row, textvariable=self.status_var, bg=CARD,
            fg=NAVY, font=(FONT, 13, "bold"))
        self._status_lbl.pack(side="left")

        btns = ttk.Frame(f)
        btns.pack(fill="x", padx=14, pady=14)
        btns.columnconfigure((0, 1, 2), weight=1, uniform="ctrl")
        _opts = dict(font=("Segoe UI", 10, "bold"), bd=0, relief="flat",
                     highlightthickness=1, cursor="hand2", pady=7)
        # Icone Pause dessinee (deux barres serrees) ; couleur selon l'etat.
        self._pause_imgs = {
            "white": self._make_pause_icon("#ffffff"),
            "dark": self._make_pause_icon(TEXT),
            "gray": self._make_pause_icon(DISABLED),
        }
        self.play_btn = tk.Button(btns, text="▶ Play", command=self._play, **_opts)
        self.pause_btn = tk.Button(
            btns, text=" Pause", image=self._pause_imgs["dark"],
            compound="left", command=self._pause, **_opts)
        self.stop_btn = tk.Button(btns, text="⏹ Stop", command=self._stop, **_opts)
        self.play_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.pause_btn.grid(row=0, column=1, sticky="ew", padx=4)
        self.stop_btn.grid(row=0, column=2, sticky="ew", padx=(4, 0))

        # Bouton "Terminé" (mode assigne) : a part des controles du chrono, pour
        # marquer le projet livre (il sort alors de la liste).
        if self.assigned_projects is not None:
            self.complete_btn = tk.Button(
                f, text="✓ Marquer ce projet terminé",
                command=self._complete_project,
                bg=SOFT_BG, fg=SOFT_TEXT, activebackground=SOFT_BG,
                activeforeground=SOFT_TEXT, bd=0, relief="flat",
                highlightthickness=1, highlightbackground="#C9E4E6",
                font=("Segoe UI", 9, "bold"), cursor="hand2", pady=6,
            )
            self.complete_btn.pack(fill="x", padx=14, pady=(0, 6))

    def _make_pause_icon(self, color, w=14, h=14, bar=3, gap=2):
        """Petite image : deux barres verticales serrees (icone Pause '||').
        Couleur pleine `color` ; le reste reste transparent (fond du bouton)."""
        img = tk.PhotoImage(master=self.root, width=w, height=h)
        x0 = (w - (bar * 2 + gap)) // 2
        for bx in (x0, x0 + bar + gap):
            img.put(color, to=(bx, 1, bx + bar, h - 1))
        return img

    def _build_settings_page(self):
        f = ttk.Frame(self._body)
        self.settings_frame = f

        ttk.Label(f, text="Profil", style="Title.TLabel").pack(
            anchor="w", padx=16, pady=(18, 18))

        ttk.Label(f, text="Nom", style="Field.TLabel").pack(
            anchor="w", padx=16, pady=(0, 2))
        self.settings_name_var = tk.StringVar(value=self.cfg.get("employee_name", ""))
        entry = ttk.Entry(f, textvariable=self.settings_name_var)
        entry.pack(fill="x", padx=16)
        entry.bind("<Return>", lambda _e: self._save_settings())

        # Role metier : lie au champ role cote plateforme (page Collaborateurs).
        ttk.Label(f, text="Rôle", style="Field.TLabel").pack(
            anchor="w", padx=16, pady=(10, 2))
        self.settings_role_var = tk.StringVar(value=self.cfg.get("employee_role", ""))
        ttk.Combobox(
            f, textvariable=self.settings_role_var,
            values=EMPLOYEE_ROLES, state="readonly",
        ).pack(fill="x", padx=16)

        self._build_save_footer(f, self._save_settings)

    def _build_params_page(self):
        f = ttk.Frame(self._body)
        self.params_frame = f

        ttk.Label(f, text="Paramètres", style="Title.TLabel").pack(
            anchor="w", padx=16, pady=(18, 18))

        self.autostart_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            f, text="Redémarrage automatique",
            variable=self.autostart_var,
        ).pack(anchor="w", padx=16, pady=(0, 2))

        self._build_save_footer(f, self._save_params)

    def _build_save_footer(self, parent, command):
        """Bloc bas commun (bouton Enregistrer + 'Version x.y.z'), ancre en bas
        pour que toutes les pages aient leur Enregistrer au MEME niveau."""
        footer = ttk.Frame(parent)
        footer.pack(side="bottom", fill="x")
        tk.Button(
            footer, text="Enregistrer", command=command,
            bg=ACCENT, fg="#ffffff", activebackground=ACCENT_HOVER,
            activeforeground="#ffffff", bd=0, relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2", pady=7,
        ).pack(fill="x", padx=16)
        ttk.Label(footer, text=f"Version {__version__}",
                  style="Who.TLabel").pack(pady=(8, 12))

    def _save_params(self):
        try:
            autostart_service.set_enabled(self.autostart_var.get())
        except Exception as exc:
            log(f"Reglage demarrage auto echoue: {exc}")
            messagebox.showerror("Erreur", "Impossible d'enregistrer le réglage.")
            return
        messagebox.showinfo("Enregistré", "Réglages enregistrés.")

    # --- construction d'un champ ---

    def _field(self, parent, label, combo=False, values=None, readonly=False):
        ttk.Label(parent, text=label).pack(anchor="w", padx=14, pady=(10, 2))
        var = tk.StringVar()
        state = "readonly" if readonly else "normal"
        if combo:
            widget = ttk.Combobox(parent, textvariable=var,
                                  values=values or [], state=state)
        else:
            widget = ttk.Entry(parent, textvariable=var, state=state)
        widget.pack(fill="x", padx=14)
        if label == "Projet":
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
            # Prefixe le rang de priorite (1., 2., 3...) -> l'ordre se lit
            # directement dans la liste. Les projets non priorises restent nus.
            prio = project.get("priority", 0) or 0
            if prio > 0:
                label = f"{prio}. {label}"
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

    # --- configuration (nom du monteur) ---

    def _update_who(self):
        name = self.cfg.get("employee_name") or "(non configure)"
        self.who_var.set(f"Collaborateur : {name}")

    def _save_settings(self):
        name = self.settings_name_var.get().strip()
        if not name:
            messagebox.showwarning("Nom requis", "Renseigne le nom du collaborateur.")
            return
        role = self.settings_role_var.get().strip()
        save_config({"employee_name": name, "employee_role": role})
        self.cfg["employee_name"] = name
        self.cfg["employee_role"] = role
        # Identite = nom@PC : changer le nom bascule l'agent sur l'identite du
        # nouvel utilisateur (les donnees de l'ancien restent sous son nom).
        self.cfg["employee_id"] = derive_employee_id(name)
        self.controller.update_context(name=name)
        self._announce_employee()  # (re)enregistre l'identite + recupere ses projets
        self.worker.wake()  # cloture le segment courant, repart sous la nouvelle identite
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
            try:
                set_role(self.cfg, self.cfg.get("employee_role") or None)
            except Exception as exc:
                log(f"Role non envoye: {exc}")
            if self.assigned_projects is not None:
                try:
                    self._pending_assigned = fetch_assigned_projects(self.cfg)
                except Exception:
                    pass

        threading.Thread(target=work, daemon=True).start()

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
        temps du segment en cours (s'il porte sur ce meme livrable).

        Cale sur le serveur (source de verite) : on prend le plus eleve entre le
        total serveur et le total local. En ligne, le serveur fait foi (l'agent
        affiche le meme chiffre que le dashboard) ; hors-ligne, le local prend le
        relais (il contient le travail pas encore envoye)."""
        assigned = self._selected_assigned_project()
        client = assigned["client"] if assigned else self.client_var.get().strip()
        video = assigned["video_name"] if assigned else self.video_var.get().strip()
        version = assigned["version"] if assigned else self.version_var.get().strip()
        base = storage_service.accumulated_seconds(client, video, version) if video else 0
        if assigned is not None:
            server_spent = assigned.get("spent_sec")
            if isinstance(server_spent, (int, float)) and server_spent > base:
                base = server_spent

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
                "Renseigne ton nom dans Profil avant de demarrer.",
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
                    "Aucun projet n'est assigne a ce collaborateur.",
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
        if not VERSION_RE.match(version):
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

    def _complete_project(self):
        """Marque le projet selectionne comme termine (cote monteur)."""
        project = self._selected_assigned_project()
        if not project or not project.get("id"):
            messagebox.showwarning(
                "Aucun projet", "Selectionne un projet a marquer termine."
            )
            return
        label = f"{project['video_name']} ({project['version']})"
        if not messagebox.askokcancel(
            "Marquer terminé",
            f"Marquer « {label} » comme terminé ?\n\n"
            "Il sera retire de ta liste.",
        ):
            return
        # Terminer arrete le suivi en cours.
        if self.controller.snapshot()["mode"] != SessionMode.STOPPED:
            self.controller.stop()
            self.worker.wake()
        threading.Thread(
            target=self._complete_bg, args=(project["id"],), daemon=True
        ).start()

    def _complete_bg(self, project_id):
        """Thread reseau : marque termine puis rafraichit la liste (le projet
        disparait). En cas d'echec, l'UI affiche le message a la prochaine boucle."""
        try:
            complete_project(self.cfg, project_id)
            self._pending_assigned = fetch_assigned_projects(self.cfg)
        except Exception as exc:
            log(f"Marquage termine echoue: {exc}")
            self._pending_error = "Impossible de marquer le projet terminé."

    def _handle_close(self):
        if messagebox.askokcancel("Quitter", "Arreter le suivi et quitter ?"):
            self.controller.stop()
            self.on_close()
            self.root.destroy()

    # --- rafraichissement periodique (1 s) ---

    def _refresh(self):
        # Applique une mise a jour des projets assignes recue en arriere-plan.
        if self._pending_assigned is not None:
            projects, self._pending_assigned = self._pending_assigned, None
            self._apply_assigned_refresh(projects)

        # Erreur remontee par un thread (ex. marquage termine) -> popup une fois.
        if self._pending_error is not None:
            msg, self._pending_error = self._pending_error, None
            messagebox.showerror("Erreur", msg)

        update_ready = is_update_ready()
        # Nouvelle version telechargee -> on propose le redemarrage (une fois).
        if update_ready and not self._update_notified:
            self._update_notified = True
            self._notif.show(
                "Une nouvelle version est prête.",
                action_text="Redémarrer",
                action_cb=self._restart_for_update,
            )

        mode = self.controller.snapshot()["mode"]
        seconds = self._displayed_seconds()
        self.status_var.set(STATUS[mode])

        assigned = self._selected_assigned_project()
        estimated = assigned.get("estimated_duration_sec", 0) if assigned else 0
        # Rappel de MAJ dans le timer flottant (toujours visible) : sous le
        # compteur en Play/Pause, a la place du compteur a l'arret.
        self._floating.update(mode, seconds, estimated, update_ready=update_ready)

        running = mode == SessionMode.RUNNING
        paused = mode == SessionMode.PAUSED
        stopped = mode == SessionMode.STOPPED
        self._status_dot.config(fg=STATE_COLORS[mode])
        self._status_lbl.config(fg=STATE_COLORS[mode])
        # Seul le bouton de l'etat courant est rempli (Play vert / Pause orange) ;
        # Stop reste neutre (blanc), comme la maquette.
        paint_control(self.play_btn, GREEN, active=running, enabled=not running)
        paint_control(self.pause_btn, ORANGE, active=paused, enabled=running)
        self.pause_btn.config(image=self._pause_imgs[
            "white" if paused else "dark" if running else "gray"])
        paint_control(self.stop_btn, RED, active=False, enabled=not stopped)

        # Auto-application de la MAJ quand l'agent reste a l'arret un moment :
        # les postes "juste ouverts" se mettent a jour seuls ; ceux qui
        # travaillent (Play/Pause) ne sont jamais coupes (ils ont le rappel).
        if update_ready and stopped:
            if self._update_idle_since is None:
                self._update_idle_since = time.monotonic()
            elif time.monotonic() - self._update_idle_since >= self._auto_update_idle_sec:
                self._restart_for_update()
                return
        else:
            self._update_idle_since = None

        self.root.after(1000, self._refresh)

    def run(self):
        self.root.mainloop()
