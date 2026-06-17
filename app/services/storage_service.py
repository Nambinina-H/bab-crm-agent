import sqlite3

from app.settings.paths import DB_PATH

_NON_PAUSED = ("active", "idle")


def open_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    conn = open_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS segments (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id   TEXT,
            employee_name TEXT,
            client        TEXT,
            app           TEXT,
            window_title  TEXT,
            project       TEXT,
            version       TEXT,
            state         TEXT,
            start_ts      TEXT,
            end_ts        TEXT,
            duration_sec  INTEGER,
            clicks        INTEGER DEFAULT 0,
            synced        INTEGER DEFAULT 0
        )
    """)
    _ensure_columns(conn)
    conn.commit()
    return conn


def _ensure_columns(conn):
    """Ajoute les colonnes manquantes sur une base existante (migration douce)."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(segments)")}
    for col in ("client", "version"):
        if col not in existing:
            conn.execute(f"ALTER TABLE segments ADD COLUMN {col} TEXT")
    if "clicks" not in existing:
        conn.execute("ALTER TABLE segments ADD COLUMN clicks INTEGER DEFAULT 0")


def store_segment(conn, seg):
    conn.execute("""
        INSERT INTO segments
        (employee_id, employee_name, client, app, window_title, project,
         version, state, start_ts, end_ts, duration_sec, clicks, synced)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)
    """, (
        seg["employee_id"], seg["employee_name"], seg["client"], seg["app"],
        seg["window_title"], seg["project"], seg["version"], seg["state"],
        seg["start_ts"], seg["end_ts"], seg["duration_sec"],
        seg.get("clicks", 0)
    ))
    conn.commit()


def fetch_unsynced(conn, limit):
    return conn.execute("""
        SELECT id, employee_id, employee_name, client, app, window_title,
               project, version, state, start_ts, end_ts, duration_sec, clicks
        FROM segments WHERE synced = 0
        ORDER BY id LIMIT ?
    """, (limit,)).fetchall()


def mark_synced(conn, ids):
    if not ids:
        return
    conn.executemany("UPDATE segments SET synced = 1 WHERE id = ?",
                     [(i,) for i in ids])
    conn.commit()


def purge_synced(conn):
    """Supprime du buffer local les segments DEJA envoyes au serveur (synced=1).
    Les segments en attente (synced=0) sont conserves -> aucune perte. Sert au
    reset unique apres la v1.0.7 : l'agent repart du serveur (source de verite)."""
    conn.execute("DELETE FROM segments WHERE synced = 1")
    conn.commit()


# --- Lecture pour l'UI (reprise d'un livrable) -------------------------------
# Ces fonctions ouvrent leur propre connexion (appelees depuis le thread UI).

def distinct_videos():
    """Noms de videos deja saisis, plus recents en tete (pour la liste)."""
    conn = open_connection()
    try:
        rows = conn.execute("""
            SELECT project, MAX(id) AS m FROM segments
            WHERE project IS NOT NULL AND project <> ''
            GROUP BY project ORDER BY m DESC
        """).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def client_for_video(video):
    """Dernier client associe a cette video (pour pre-remplir le champ Client)."""
    if not video:
        return ""
    conn = open_connection()
    try:
        row = conn.execute("""
            SELECT client FROM segments
            WHERE project = ? AND client IS NOT NULL AND client <> ''
            ORDER BY id DESC LIMIT 1
        """, (video,)).fetchone()
        return row[0] if row else ""
    finally:
        conn.close()


def accumulated_seconds(client, video, version):
    """Temps cumule (hors pause) deja enregistre pour ce livrable."""
    if not video:
        return 0
    conn = open_connection()
    try:
        placeholders = ",".join("?" * len(_NON_PAUSED))
        row = conn.execute(f"""
            SELECT COALESCE(SUM(duration_sec), 0) FROM segments
            WHERE client = ? AND project = ? AND version = ?
              AND state IN ({placeholders})
        """, (client, video, version, *_NON_PAUSED)).fetchone()
        return row[0] or 0
    finally:
        conn.close()
