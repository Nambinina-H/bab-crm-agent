import sys

from app.core.logging import log
from app.core.session import SessionController
from app.services.capture_service import CaptureWorker
from app.services.foreground_watcher import ForegroundWatcher
from app.services.heartbeat_service import HeartbeatSender
from app.services.storage_service import init_db
from app.services.sync_service import Syncer
from app.services.update_service import apply_pending_update, start_background_checker
from app.settings.settings import load_config
from app.ui.app_window import AppWindow


def main():
    # Tout au debut : si une mise a jour a ete telechargee, on l'installe puis
    # l'agent se relance automatiquement (sans toucher a la config).
    apply_pending_update()

    if sys.platform != "win32":
        log("ATTENTION : agent concu pour Windows. "
            "Les mesures d'activite sont limitees sur un autre OS.")

    cfg = load_config()
    init_db().close()  # cree la table avant de demarrer les threads

    controller = SessionController()
    # Nom configure (ecran Configuration) : injecte des le demarrage.
    controller.update_context(name=cfg.get("employee_name", ""))

    syncer = Syncer(cfg)
    syncer.start()

    heartbeat = HeartbeatSender(cfg, controller)
    # Le worker declenche le heartbeat des qu'une activite change (temps reel).
    worker = CaptureWorker(cfg, controller, on_change=heartbeat.trigger)
    worker.start()
    heartbeat.start()

    # Changement de fenetre au premier plan -> re-echantillonne tout de suite
    # (<100 ms) ; le worker cascade ensuite vers le heartbeat.
    watcher = ForegroundWatcher(on_change=worker.wake)
    watcher.start()

    # Verifie les mises a jour en arriere-plan (sans interrompre la session).
    start_background_checker()

    log(f"Agent pret (machine {cfg['employee_id']}). Serveur: {cfg['server_url']}")

    def on_close():
        log("Arret demande.")
        heartbeat.send_offline()  # passe hors-ligne tout de suite cote dashboard
        watcher.stop()
        worker.stop()
        syncer.stop()
        heartbeat.stop()

    AppWindow(controller, worker, cfg, on_close).run()
    log("Agent arrete.")


if __name__ == "__main__":
    main()
