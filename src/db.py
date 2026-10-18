"""SQLite storage for opinions, parse results, tags, and fetch state (KTD3).

The database lives at data/cases.sqlite (gitignored) and is never published.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src import textutil

SCHEMA = """
CREATE TABLE IF NOT EXISTS clusters (
    cl_cluster_id     INTEGER PRIMARY KEY,
    docket_id         INTEGER,
    court             TEXT,
    case_name         TEXT,
    docket_number     TEXT,
    date_filed        TEXT,
    precedential_status TEXT,
    absolute_url      TEXT,
    source            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS clusters_court_date ON clusters(court, date_filed);

CREATE TABLE IF NOT EXISTS opinions (
    cl_opinion_id     INTEGER PRIMARY KEY,
    cl_cluster_id     INTEGER NOT NULL,
    opinion_type      TEXT,
    text              TEXT,
    text_field_used   TEXT,
    text_hash         TEXT,
    source            TEXT NOT NULL,
    -- parse results (U5); NULL until parsed
    district          TEXT,
    division          TEXT,
    published         INTEGER,
    partial_publication INTEGER,
    disposition_text  TEXT,
    disposition_class TEXT,   -- affirmed | affirmed_as_modified | reversed | reversed_in_part |
                              -- vacated | dismissed | writ_granted | writ_denied | other
    docket_number_text TEXT,  -- docket number parsed from the caption
    author_slug       TEXT,
    author_raw        TEXT,
    per_curiam        INTEGER,
    has_dissent       INTEGER,
    has_concurrence   INTEGER,
    parse_status      TEXT,
    superseded_by     INTEGER
);
CREATE INDEX IF NOT EXISTS opinions_cluster ON opinions(cl_cluster_id);
CREATE INDEX IF NOT EXISTS opinions_hash ON opinions(text_hash);

CREATE TABLE IF NOT EXISTS panel_seats (
    cl_opinion_id     INTEGER NOT NULL,
    seat_raw          TEXT NOT NULL,
    slug              TEXT,                   -- NULL when unresolved or an assigned trial judge
    role              TEXT NOT NULL,          -- author | joined (per curiam panels: joined)
    title             TEXT,                   -- J. | P. J. | Acting P. J. | C. J.
    assigned          INTEGER NOT NULL DEFAULT 0,
    assignment_note   TEXT,                   -- footnote text for an assigned judge
    PRIMARY KEY (cl_opinion_id, seat_raw, role)
);

CREATE TABLE IF NOT EXISTS separate_opinions (
    cl_opinion_id     INTEGER NOT NULL,
    type              TEXT NOT NULL,          -- dissent | concurrence; a concurring-and-
                                              -- dissenting opinion is dissent with partial=1
    partial           INTEGER NOT NULL DEFAULT 0,
    author_slug       TEXT,
    author_raw        TEXT
);

CREATE TABLE IF NOT EXISTS topic_tags (
    cl_opinion_id     INTEGER NOT NULL,
    topic             TEXT NOT NULL,
    anchor_hits       INTEGER NOT NULL,
    broad_hits        INTEGER NOT NULL,
    tagged            INTEGER NOT NULL,
    queue_match       INTEGER NOT NULL,
    PRIMARY KEY (cl_opinion_id, topic)
);

CREATE TABLE IF NOT EXISTS http_cache (
    url               TEXT PRIMARY KEY,
    status            INTEGER NOT NULL,
    body              TEXT NOT NULL,
    fetched_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_cursors (
    job               TEXT PRIMARY KEY,
    next_url          TEXT,
    done              INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bulk_dockets (
    docket_id         INTEGER PRIMARY KEY,
    court             TEXT NOT NULL,
    docket_number     TEXT,
    case_name         TEXT
);

CREATE TABLE IF NOT EXISTS bulk_checkpoints (
    stage             TEXT PRIMARY KEY,
    rows_done         INTEGER NOT NULL,
    done              INTEGER NOT NULL DEFAULT 0
);
"""


def insert_opinion(
    conn: sqlite3.Connection, opinion_id: int, cluster_id: int, opinion_type: str | None,
    text: str, field: str | None, source: str,
) -> bool:
    """Insert one opinion unless it, or identical text, is already stored."""
    digest = textutil.text_hash(text) if text else None
    if conn.execute("SELECT 1 FROM opinions WHERE cl_opinion_id = ?", (opinion_id,)).fetchone():
        return False
    if digest and conn.execute("SELECT 1 FROM opinions WHERE text_hash = ?", (digest,)).fetchone():
        return False
    conn.execute(
        "INSERT INTO opinions (cl_opinion_id, cl_cluster_id, opinion_type, text, "
        "text_field_used, text_hash, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (opinion_id, cluster_id, opinion_type, text, field, digest, source),
    )
    return True


def connect(path: Path | str) -> sqlite3.Connection:
    path = Path(path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    _add_missing_columns(conn)
    return conn


# Columns added after a database may already exist: (table, column, type).
ADDED_COLUMNS = [
    ("opinions", "disposition_class", "TEXT"),
    ("opinions", "docket_number_text", "TEXT"),
    ("panel_seats", "title", "TEXT"),
    ("panel_seats", "assignment_note", "TEXT"),
]


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    for table, column, kind in ADDED_COLUMNS:
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
    conn.commit()
