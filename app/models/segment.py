def make_segment(employee_id, employee_name, client, app, window_title,
                 project, version, state, start_ts):
    return {
        "employee_id": employee_id,
        "employee_name": employee_name,
        "client": client,
        "app": app,
        "window_title": window_title,
        "project": project,    # = nom de la video
        "version": version,
        "state": state,
        "start_ts": start_ts,
        "clicks": 0,           # clics souris du segment (renseigne a la cloture)
        # Tout changement de contexte (etat, app, fenetre, video, client,
        # version) ouvre un nouveau segment.
        "_key": (state, app, window_title, project, client, version),
    }
