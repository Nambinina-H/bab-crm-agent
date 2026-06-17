import requests


def fetch_assigned_projects(cfg):
    """Projets assignes au poste courant, selon l'employee_id technique."""
    resp = requests.get(
        cfg["server_url"].rstrip("/") + "/api/assigned-projects",
        params={"employee_id": cfg["employee_id"]},
        headers={"X-API-Key": cfg["api_key"]},
        timeout=8,
    )
    resp.raise_for_status()

    projects = []
    for item in resp.json().get("projects", []):
        client = str(item.get("client") or "").strip()
        video_name = str(item.get("video_name") or "").strip()
        version = str(item.get("version") or "").strip()
        if client and video_name and version:
            projects.append({
                "id": item.get("id"),
                "client": client,
                "video_name": video_name,
                "version": version,
                "estimated_duration_sec": item.get("estimated_duration_sec") or 0,
                # Priorite definie par le manager (1 = plus prioritaire ; 0 = non
                # priorise). La liste arrive deja triee par priorite.
                "priority": item.get("priority") or 0,
                # Temps actif cote serveur (= ce qu'affiche le dashboard). Sert a
                # caler le compteur de l'agent sur le serveur.
                "spent_sec": item.get("spent_sec") or 0,
            })
    return projects


def complete_project(cfg, project_id):
    """Marque un projet assigne comme termine (cote monteur)."""
    resp = requests.post(
        cfg["server_url"].rstrip("/") + "/api/agent/project-complete",
        json={"employee_id": cfg["employee_id"], "project_id": project_id},
        headers={"X-API-Key": cfg["api_key"]},
        timeout=8,
    )
    resp.raise_for_status()
