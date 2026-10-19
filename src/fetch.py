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

from src import bulk, cl_api, config, coverage, db, textutil

log = logging.getLogger(__name__)

CLUSTER_FIELDS = "id,docket_id,case_name,date_filed,precedential_status,absolute_url"
OPINION_FIELDS = "id,cluster_id,type," + ",".join(textutil.TEXT_FIELDS)


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
        added += db.insert_opinion(
            conn, o["id"], o["cluster_id"], o.get("type"), text, field, "api"
        )
    conn.commit()
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load opinions into SQLite.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    api = sub.add_parser("api", help="fetch the post-snapshot gap through the API")
    api.add_argument("--since", default="2026-10-01")
    api.add_argument("--court", action="append", help="court id; repeatable")
    blk = sub.add_parser("bulk", help="filter the bulk snapshot into SQLite")
    blk.add_argument(
        "--stages", default="dockets,clusters,opinions", help="comma list of stages to run"
    )
    sub.add_parser("coverage", help="write data/validation/coverage.md")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = config.load()
    conn = db.connect(settings.path("database"))

    if args.cmd == "bulk":
        snap = settings.raw["bulk"]["snapshot"]
        folder = settings.path("bulk")
        source = f"bulk-{snap}"
        stages = set(args.stages.split(","))
        starts = {
            "calctapp": settings.raw["window"]["start"],
            "cal": settings.raw["window"]["supreme_court_start"],
        }
        if "dockets" in stages:
            n = bulk.load_dockets(conn, folder / f"dockets-{snap}.csv.bz2",
                                  set(settings.raw["bulk"]["courts"]))
            log.info("dockets kept: %d", n)
        if "clusters" in stages:
            n = bulk.load_clusters(conn, folder / f"opinion-clusters-{snap}.csv.bz2", starts,
                                   source)
            log.info("clusters kept: %d", n)
        if "opinions" in stages:
            n = bulk.load_opinions(conn, folder / f"opinions-{snap}.csv.bz2", source)
            log.info("opinions added: %d", n)

    if args.cmd == "coverage":
        report = coverage.build_report(
            conn, expected_per_year=7000,
            window_options=[settings.raw["window"]["start"], "2023-01-01"],
        )
        out = settings.path("validation") / "coverage.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report)
        log.info("wrote %s", out)

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
