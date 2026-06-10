import threading
import time
from datetime import datetime

from app.collectors.foreground import get_foreground_app
from app.collectors.idle import get_idle_seconds
from app.core.session import SessionMode
from app.models.segment import make_segment
from app.services.storage_service import init_db, store_segment
from app.utils.time_utils import now_utc_iso


class CaptureWorker(threading.Thread):
    """Thread de fond qui echantillonne l'activite selon l'etat de la session.

    - RUNNING : capture app/titre + etat actif/inactif (souris/clavier).
    - PAUSED  : enregistre des segments `paused` (la pause est comptabilisee).
    - STOPPED : ne mesure rien (cloture le segment en cours s'il existe).

    Expose `live_snapshot()` : le livrable du segment en cours + depuis quand,
    pour que l'UI affiche un chrono cumulatif qui ticke.
    """

    def __init__(self, cfg, controller, on_change=None):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.controller = controller
        self._on_change = on_change  # appele quand l'activite change (heartbeat)
        self._stop = threading.Event()
        self._wake = threading.Event()  # reveil immediat sur transition
        self._current = None
        self._live_lock = threading.Lock()
        self._live = None  # {client, video, version, started, paused}

    def run(self):
        conn = init_db()
        try:
            while not self._stop.is_set():
                self._tick(conn)
                self._wake.wait(self.cfg["sample_interval_sec"])
                self._wake.clear()
        finally:
            if self._current is not None:
                self._finalize(conn, self._current, now_utc_iso())
                self._current = None
            self._set_live(None)

    def _tick(self, conn):
        snap = self.controller.snapshot()
        mode = snap["mode"]
        ts = now_utc_iso()

        if mode == SessionMode.STOPPED:
            if self._current is not None:
                self._finalize(conn, self._current, ts)
                self._current = None
                self._notify()  # transition -> stop : presence a rafraichir
            self._set_live(None)
            return

        project = snap["project"]
        client = snap["client"]
        version = snap["version"]
        if mode == SessionMode.RUNNING:
            idle = get_idle_seconds()
            state = "idle" if idle >= self.cfg["idle_threshold_sec"] else "active"
            app, title = get_foreground_app()
        else:  # PAUSED
            state, app, title = "paused", None, ""

        key = (state, app, title, project, client, version)
        if self._current is None or key != self._current["_key"]:
            if self._current is not None:
                self._finalize(conn, self._current, ts)
            self._current = make_segment(
                self.cfg["employee_id"], snap["name"], client, app, title,
                project, version, state, ts,
            )
            self._set_live({
                "client": client, "video": project, "version": version,
                "started": time.monotonic(), "paused": state == "paused",
            })
            self._notify()  # nouvel etat (app/titre/etat) -> presence a pousser

    def _finalize(self, conn, seg, end_ts):
        seg["end_ts"] = end_ts
        start = datetime.fromisoformat(seg["start_ts"])
        end = datetime.fromisoformat(end_ts)
        seg["duration_sec"] = max(0, int((end - start).total_seconds()))
        if seg["duration_sec"] > 0:
            store_segment(conn, seg)

    def _notify(self):
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                pass  # le heartbeat ne doit jamais perturber la capture

    def _set_live(self, value):
        with self._live_lock:
            self._live = value

    def live_snapshot(self):
        with self._live_lock:
            return dict(self._live) if self._live else None

    def wake(self):
        """Force un echantillon immediat (a appeler apres Play/Pause/Stop ou un
        changement de contexte) pour cloturer/ouvrir le segment sans attendre."""
        self._wake.set()

    def stop(self):
        self._stop.set()
        self._wake.set()
