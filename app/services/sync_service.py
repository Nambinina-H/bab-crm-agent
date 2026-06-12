import threading

import requests

from app.core.logging import log
from app.services.config_service import pull_remote_config
from app.services.register_service import register_employee
from app.services.storage_service import fetch_unsynced, mark_synced, open_connection
from app.utils.time_utils import now_utc_iso


class Syncer(threading.Thread):
    def __init__(self, cfg):
        super().__init__(daemon=True)
        self.cfg = cfg
        self._stop = threading.Event()

    def run(self):
        conn = open_connection()
        while not self._stop.is_set():
            # 0. S'annonce a la plateforme des qu'un nom est configure (visible
            #    et assignable sans attendre d'activite). Idempotent.
            if self.cfg.get("employee_name"):
                try:
                    register_employee(self.cfg)
                except Exception as exc:
                    log(f"Enregistrement non envoye: {exc}")
            # 1. Recupere la config centrale (a chaud). Echec = on garde l'actuelle.
            try:
                pull_remote_config(self.cfg)
            except Exception as exc:
                log(f"Config non recuperee (config locale conservee): {exc}")
            # 2. Envoie les segments en attente.
            try:
                self.sync_once(conn)
            except Exception as exc:
                log(f"Erreur de synchro: {exc}")
            self._stop.wait(self.cfg["sync_interval_sec"])

    def sync_once(self, conn):
        rows = fetch_unsynced(conn, self.cfg["sync_batch_size"])
        if not rows:
            return

        events = [{
            "client_id": r[0],
            "employee_id": r[1], "employee_name": r[2], "client": r[3],
            "app": r[4], "window_title": r[5], "project": r[6], "version": r[7],
            "state": r[8], "start_ts": r[9], "end_ts": r[10],
            "duration_sec": r[11],
        } for r in rows]

        resp = requests.post(
            self.cfg["server_url"].rstrip("/") + "/api/events",
            # client_sent_at : heure UTC de l'agent a l'envoi -> le serveur
            # recale les horodatages si l'horloge du poste est decalee.
            json={"events": events, "client_sent_at": now_utc_iso()},
            headers={"X-API-Key": self.cfg["api_key"]},
            timeout=15,
        )
        resp.raise_for_status()

        ids = [r[0] for r in rows]
        mark_synced(conn, ids)
        log(f"Synchronise {len(ids)} segment(s).")

    def stop(self):
        self._stop.set()
