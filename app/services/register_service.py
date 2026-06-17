import requests


def register_employee(cfg):
    """Annonce le monteur a la plateforme (employee_id + nom) pour qu'il soit
    visible et assignable, sans attendre d'activite. Best-effort : l'appelant
    capture les erreurs reseau. Renvoie la reponse (dont le `role` courant)."""
    resp = requests.post(
        cfg["server_url"].rstrip("/") + "/api/register",
        json={
            "employee_id": cfg["employee_id"],
            "employee_name": cfg.get("employee_name", ""),
            # Ancien identifiant machine : migration unique cote serveur
            # (rename -> nom@PC). Sans effet une fois la migration faite.
            "previous_id": cfg.get("machine_id"),
        },
        headers={"X-API-Key": cfg["api_key"]},
        timeout=8,
    )
    resp.raise_for_status()
    try:
        return resp.json()
    except ValueError:
        return {}


def set_role(cfg, role):
    """Definit le role metier du collaborateur (depuis l'ecran Parametres).
    Meme champ que la page Collaborateurs. `role` vide/None = aucun role."""
    resp = requests.post(
        cfg["server_url"].rstrip("/") + "/api/agent/role",
        json={"employee_id": cfg["employee_id"], "role": role or None},
        headers={"X-API-Key": cfg["api_key"]},
        timeout=8,
    )
    resp.raise_for_status()
