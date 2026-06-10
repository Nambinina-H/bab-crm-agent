import threading

import requests

from app.collectors.foreground import get_foreground_app
from app.collectors.idle import get_idle_seconds
from app.core.logging import log
from app.core.session import SessionMode


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
        self._offline_sent = False

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
            if self._offline_sent:
                return  # deja signale hors-ligne, on n'inonde pas le serveur
            self._post({
                "employee_id": self.cfg["employee_id"],
                "employee_name": snap["name"],
                "state": "offline",
            })
            self._offline_sent = True
            return

        self._offline_sent = False
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
            self._offline_sent = True
        except Exception as exc:
            log(f"Offline non envoye: {exc}")

    def _post(self, payload):
        requests.post(
            self.cfg["server_url"].rstrip("/") + "/api/heartbeat",
            json=payload,
            headers={"X-API-Key": self.cfg["api_key"]},
            timeout=8,
        )

    def stop(self):
        self._stop.set()
        self._wake.set()
