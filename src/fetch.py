"""Load opinions into data/cases.sqlite.

    python -m src.fetch bulk            # 2026-09-30 bulk snapshot (U3)
    python -m src.fetch api --since 2026-10-01   # post-snapshot gap via the API (U4)
    python -m src.fetch coverage        # write data/validation/coverage.md (U3)

Both loaders are idempotent and resumable.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from urllib.parse import urlencode

from src import cl_api, config, db, textutil

log = logging.getLogger(__name__)

CLUSTER_FIELDS = "id,docket_id,case_name,date_filed,precedential_status,absolute_url"
OPINION_FIELDS = "id,cluster_id,type," + ",".join(textutil.TEXT_FIELDS)


def insert_opinion(
    conn: sqlite3.Connection, opinion_id: int, cluster_id: int, opinion_type: str | None,
    text: str, field: str | None, source: str,
) -> bool:
    """Insert one opinion unless it or identical text is already stored."""
    digest = textutil.text_hash(text) if text else None
    if conn.execute("SELECT 1 FROM opinions WHERE cl_opinion_id = ?", (opinion_id,)).fetchone():
        return False
    if digest and conn.execute(
        "SELECT 1 FROM opinions WHERE text_hash = ?", (digest,)
    ).fetchone():
        return False
    conn.execute(
        "INSERT INTO opinions (cl_opinion_id, cl_cluster_id, opinion_type, text, "
        "text_field_used, text_hash, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (opinion_id, cluster_id, opinion_type, text, field, digest, source),
    )
    return True


def fetch_api_gap(client: cl_api.Client, conn: sqlite3.Connection, court: str, since: str) -> int:
    """Fetch clusters and opinions filed on or after `since` for one court."""
    cluster_url = client.base + "clusters/?" + urlencode(
        {"docket__court": court, "date_filed__gte": since, "order_by": "id",
         "fields": CLUSTER_FIELDS}
    )
    for c in client.paginate(f"clusters:{court}:{since}", cluster_url):
        conn.execute(
            "INSERT OR IGNORE INTO clusters (cl_cluster_id, docket_id, court, case_name, "
            "date_filed, precedential_status, absolute_url, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'api')",
            (c["id"], c.get("docket_id"), court, c.get("case_name"), c.get("date_filed"),
             c.get("precedential_status"), c.get("absolute_url")),
        )
    conn.commit()

    opinion_url = client.base + "opinions/?" + urlencode(
        {"cluster__docket__court": court, "cluster__date_filed__gte": since, "order_by": "id",
         "fields": OPINION_FIELDS}
    )
    added = 0
    for o in client.paginate(f"opinions:{court}:{since}", opinion_url):
        text, field = textutil.choose_text(o)
        added += insert_opinion(conn, o["id"], o["cluster_id"], o.get("type"), text, field, "api")
    conn.commit()
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load opinions into SQLite.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    api = sub.add_parser("api", help="fetch the post-snapshot gap through the API")
    api.add_argument("--since", default="2026-10-01")
    api.add_argument("--court", action="append", help="court id; repeatable")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = config.load()
    conn = db.connect(settings.path("database"))

    if args.cmd == "api":
        client = cl_api.Client(settings, conn)
        courts = args.court or settings.raw["bulk"]["courts"]
        try:
            for court in courts:
                n = fetch_api_gap(client, conn, court, args.since)
                log.info("%s: %d new opinions since %s", court, n, args.since)
        except cl_api.StopRun as exc:
            log.error("Stopped: %s", exc)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
