import requests


def register_employee(cfg):
    """Annonce le monteur a la plateforme (employee_id + nom) pour qu'il soit
    visible et assignable, sans attendre d'activite. Best-effort : l'appelant
    capture les erreurs reseau."""
    resp = requests.post(
        cfg["server_url"].rstrip("/") + "/api/register",
        json={
            "employee_id": cfg["employee_id"],
            "employee_name": cfg.get("employee_name", ""),
        },
        headers={"X-API-Key": cfg["api_key"]},
        timeout=8,
    )
    resp.raise_for_status()
