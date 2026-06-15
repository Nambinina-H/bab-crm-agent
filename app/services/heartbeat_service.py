import threading

import requests

from app.collectors.foreground import get_foreground_app
from app.collectors.idle import get_idle_seconds
from app.core.logging import log
from app.core.session import SessionMode
from app.version import __version__


class HeartbeatSender(threading.Thread):
    """Présence temps réel : envoie l'état courant *sur changement* (via
    `trigger()`, appelé par le worker quand l'app/l'état change) et, à défaut,
    toutes les ~12 s en filet de sécurité (liveness).

    Indépendant du worker/syncer : n'enregistre rien en local, ne transporte
    qu'un petit état volatile. Silencieux si le serveur est injoignable.
    """

    KEEPALIVE = 12  # secondes : renvoi de sécurité si rien ne change

    def __init__(self, cfg, controller):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.controller = controller
        self._stop = threading.Event()
        self._wake = threading.Event()

    def run(self):
        while not self._stop.is_set():
            try:
                self._send_once()
            except Exception as exc:
                log(f"Heartbeat non envoye: {exc}")
            self._wake.wait(self.KEEPALIVE)
            self._wake.clear()

    def trigger(self):
        """Force un envoi immédiat (changement d'app/d'état détecté par le worker)."""
        self._wake.set()

    def _send_once(self):
        snap = self.controller.snapshot()
        mode = snap["mode"]

        if mode == SessionMode.STOPPED:
            # Agent ouvert mais pas en suivi : on reste EN LIGNE (connecté), sans
            # activite (on vide app/projet pour ne pas afficher quelque chose de
            # perime). Le hors-ligne n'est envoye qu'a la fermeture (send_offline).
            self._post({
                "employee_id": self.cfg["employee_id"],
                "employee_name": snap["name"],
                "state": "online",
                "app": None,
                "window_title": "",
                "client": "",
                "project": "",
                "version": "",
            })
            return

        if mode == SessionMode.PAUSED:
            state, app, title = "paused", None, ""
        else:
            idle = get_idle_seconds()
            state = "idle" if idle >= self.cfg["idle_threshold_sec"] else "active"
            app, title = get_foreground_app()

        self._post({
            "employee_id": self.cfg["employee_id"],
            "employee_name": snap["name"],
            "client": snap["client"],
            "project": snap["project"],
            "version": snap["version"],
            "app": app,
            "window_title": title,
            "state": state,
        })

    def send_offline(self):
        """Signale explicitement le passage hors-ligne (fermeture de l'agent)."""
        try:
            self._post({
                "employee_id": self.cfg["employee_id"],
                "employee_name": self.controller.snapshot()["name"],
                "state": "offline",
            })
        except Exception as exc:
            log(f"Offline non envoye: {exc}")

    def _post(self, payload):
        # On joint la version de l'agent a chaque heartbeat : le dashboard peut
        # ainsi afficher la version installee sur chaque poste.
        requests.post(
            self.cfg["server_url"].rstrip("/") + "/api/heartbeat",
            json={**payload, "agent_version": __version__},
            headers={"X-API-Key": self.cfg["api_key"]},
            timeout=8,
        )

    def stop(self):
        self._stop.set()
        self._wake.set()
