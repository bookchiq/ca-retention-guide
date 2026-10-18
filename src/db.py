"""SQLite storage for opinions, parse results, tags, and fetch state (KTD3).

The database lives at data/cases.sqlite (gitignored) and is never published.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

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
    slug              TEXT,
    role              TEXT NOT NULL,          -- author | joined | separate | assigned
    assigned          INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (cl_opinion_id, seat_raw, role)
);

CREATE TABLE IF NOT EXISTS separate_opinions (
    cl_opinion_id     INTEGER NOT NULL,
    type              TEXT NOT NULL,          -- dissent | concurrence | concur_dissent
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

CREATE TABLE IF NOT EXISTS bulk_checkpoints (
    stage             TEXT PRIMARY KEY,
    rows_done         INTEGER NOT NULL,
    done              INTEGER NOT NULL DEFAULT 0
);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    path = Path(path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    return conn
