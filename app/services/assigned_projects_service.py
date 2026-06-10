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
                "client": client,
                "video_name": video_name,
                "version": version,
                "estimated_duration_sec": item.get("estimated_duration_sec") or 0,
            })
    return projects
