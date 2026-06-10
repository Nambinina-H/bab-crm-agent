import threading
import time
from enum import Enum


class SessionMode(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


class SessionController:
    """Machine a etats de la session de suivi, partagee entre l'UI (thread
    principal) et le worker de capture (thread de fond). Toutes les operations
    sont protegees par un verrou.

    Contexte saisi dans l'UI : nom (employe), client, projet (= nom de la video)
    et version. Le minuteur expose le temps ecoule depuis le premier Play,
    pauses deduites (il n'avance que pendant RUNNING, remis a zero au Stop).
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._mode = SessionMode.STOPPED
        self._name = ""
        self._client = ""
        self._project = ""   # = nom de la video
        self._version = ""
        self._worked = 0.0
        self._running_since = None

    # --- transitions ---

    def play(self):
        with self._lock:
            if self._mode == SessionMode.STOPPED:
                self._worked = 0.0
            if self._mode != SessionMode.RUNNING:
                self._running_since = time.monotonic()
            self._mode = SessionMode.RUNNING

    def pause(self):
        with self._lock:
            if self._mode == SessionMode.STOPPED:
                return
            self._accumulate_locked()
            self._mode = SessionMode.PAUSED

    def stop(self):
        with self._lock:
            self._accumulate_locked()
            self._mode = SessionMode.STOPPED
            self._worked = 0.0

    def update_context(self, name=None, client=None, project=None, version=None):
        with self._lock:
            if name is not None:
                self._name = name.strip()
            if client is not None:
                self._client = client.strip()
            if project is not None:
                self._project = project.strip()
            if version is not None:
                self._version = version.strip()

    def _accumulate_locked(self):
        if self._running_since is not None:
            self._worked += time.monotonic() - self._running_since
            self._running_since = None

    # --- lecture ---

    def snapshot(self):
        with self._lock:
            return {
                "mode": self._mode,
                "name": self._name,
                "client": self._client,
                "project": self._project,
                "version": self._version,
            }

    def worked_seconds(self):
        with self._lock:
            worked = self._worked
            if self._running_since is not None:
                worked += time.monotonic() - self._running_since
            return worked
