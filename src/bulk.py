"""Stream-filter CourtListener's bulk CSV snapshot into SQLite (U3).

The files are PostgreSQL CSV exports: every value quoted, embedded quotes
escaped with a backslash (\\") rather than doubled, multi-line text fields.
Filter order: dockets by court -> clusters by docket and date -> one pass over
the opinions file keeping rows whose cluster is in the set.

Each stage is checkpointed in `bulk_checkpoints`; a finished stage is skipped
on rerun, and an interrupted opinions pass resumes after the last committed
row count.
"""

from __future__ import annotations

import bz2
import csv
import io
import logging
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from src import db, textutil

log = logging.getLogger(__name__)

csv.field_size_limit(sys.maxsize)


class PostgresCSV(csv.Dialect):
    delimiter = ","
    quotechar = '"'
    escapechar = "\\"
    doublequote = False
    skipinitialspace = False
    lineterminator = "\n"
    quoting = csv.QUOTE_MINIMAL
    strict = False


BATCH = 2000


@contextmanager
def open_text(path: Path) -> Iterator[io.TextIOBase]:
    """Open a .csv.bz2 (parallel pbzip2 when installed) or plain .csv as text."""
    path = Path(path)
    if path.suffix != ".bz2":
        with open(path, encoding="utf-8", newline="") as fh:
            yield fh
        return
    pbzip2 = shutil.which("pbzip2")
    if pbzip2:
        # stderr discarded: closing early (fixtures, interrupts) makes pbzip2 report a
        # broken pipe. Full files are size-checked by scripts/download_bulk.sh.
        proc = subprocess.Popen(
            [pbzip2, "-dc", str(path)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        try:
            yield io.TextIOWrapper(proc.stdout, encoding="utf-8", errors="replace", newline="")
        finally:
            proc.stdout.close()
            proc.terminate()
            proc.wait()
    else:
        with bz2.open(path, "rt", encoding="utf-8", errors="replace", newline="") as fh:
            yield fh


def read_rows(path: Path) -> Iterator[dict[str, str]]:
    with open_text(path) as fh:
        reader = csv.reader(fh, dialect=PostgresCSV)
        header = next(reader)
        for row in reader:
            if len(row) != len(header):
                log.warning("Skipping malformed row with %d columns in %s", len(row), path)
                continue
            yield dict(zip(header, row, strict=True))


def _stage_done(conn: sqlite3.Connection, stage: str) -> tuple[bool, int]:
    row = conn.execute(
        "SELECT rows_done, done FROM bulk_checkpoints WHERE stage = ?", (stage,)
    ).fetchone()
    return (bool(row["done"]), row["rows_done"]) if row else (False, 0)


def _checkpoint(conn: sqlite3.Connection, stage: str, rows: int, done: bool) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO bulk_checkpoints (stage, rows_done, done) VALUES (?, ?, ?)",
        (stage, rows, int(done)),
    )
    conn.commit()


def load_dockets(conn: sqlite3.Connection, path: Path, courts: set[str]) -> int:
    stage = f"dockets:{Path(path).name}"
    done, _ = _stage_done(conn, stage)
    if done:
        return 0
    kept = 0
    for row in read_rows(path):
        if row["court_id"] in courts:
            conn.execute(
                "INSERT OR REPLACE INTO bulk_dockets (docket_id, court, docket_number, case_name) "
                "VALUES (?, ?, ?, ?)",
                (int(row["id"]), row["court_id"], row["docket_number"], row["case_name"]),
            )
            kept += 1
            if kept % BATCH == 0:
                conn.commit()  # short transactions so the API fetcher can write too
    _checkpoint(conn, stage, kept, True)
    return kept


def load_clusters(
    conn: sqlite3.Connection, path: Path, start_dates: dict[str, str], source: str
) -> int:
    """Keep clusters on kept dockets filed on or after the court's start date."""
    stage = f"clusters:{Path(path).name}"
    done, _ = _stage_done(conn, stage)
    if done:
        return 0
    dockets = {
        r["docket_id"]: (r["court"], r["docket_number"])
        for r in conn.execute("SELECT docket_id, court, docket_number FROM bulk_dockets")
    }
    kept = 0
    for row in read_rows(path):
        docket = dockets.get(int(row["docket_id"]))
        if not docket:
            continue
        court, docket_number = docket
        if row["date_filed"] < start_dates[court]:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO clusters (cl_cluster_id, docket_id, court, case_name, "
            "docket_number, date_filed, precedential_status, absolute_url, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (int(row["id"]), int(row["docket_id"]), court, row["case_name"], docket_number,
             row["date_filed"], row["precedential_status"],
             f"/opinion/{row['id']}/{row['slug']}/", source),
        )
        kept += 1
        if kept % BATCH == 0:
            conn.commit()
    _checkpoint(conn, stage, kept, True)
    return kept


def load_opinions(conn: sqlite3.Connection, path: Path, source: str) -> int:
    """One pass over the opinions file, keeping rows whose cluster was kept."""
    stage = f"opinions:{Path(path).name}"
    done, resume_after = _stage_done(conn, stage)
    if done:
        return 0
    clusters = {r[0] for r in conn.execute("SELECT cl_cluster_id FROM clusters")}
    added = 0
    seen = 0
    for row in read_rows(path):
        seen += 1
        if seen <= resume_after:
            continue
        if int(row["cluster_id"]) in clusters:
            text, field = textutil.choose_text(row)
            added += db.insert_opinion(
                conn, int(row["id"]), int(row["cluster_id"]), row["type"], text, field, source
            )
        # Checkpoint (and commit) often enough that other writers are never
        # blocked for long; resume skips `seen` rows, so this must stay in step
        # with the inserts it covers.
        if seen % BATCH == 0:
            _checkpoint(conn, stage, seen, False)
        if seen % 500_000 == 0:
            log.info("opinions: %d rows scanned, %d added", seen, added)
    _checkpoint(conn, stage, seen, True)
    return added
