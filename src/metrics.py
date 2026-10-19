"""Per-justice metrics with district/division baselines (U8, KTD5).

    python -m src.metrics          # writes guide/data/metrics.csv

Baseline = pooled rate over every opinion decided by the division the justice
sat in, during the dates they sat there, clipped to their window (district for
the 3rd, 5th, and 6th Districts; whole court for the Supreme Court). The
justice's own opinions are included and the baseline N is reported.
Per curiam opinions count as a panel seat for each identified member, are not
authored, and are excluded from publication rates. Rates are suppressed for
limited-record justices. Justices in districts that have not passed the
parsing validation gate (R9) are skipped.
"""

from __future__ import annotations

import csv
import sqlite3
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from src.justices import ServicePeriod

FIELDS = ["slug", "metric", "topic", "value", "baseline", "baseline_n", "n",
          "window_start", "window_end", "note"]
DISSENT_TYPES = ("dissent", "concur_dissent")
LIMITED_NOTE = "limited appellate record: too few opinions to assess"


def _court(period: ServicePeriod) -> str:
    return "cal" if period.court == "supreme" else "calctapp"


def _district_key(period: ServicePeriod) -> str:
    return "supreme" if period.court == "supreme" else str(period.district)


def _slice_ids(conn, period: ServicePeriod, lo: str, hi: str) -> set[int]:
    sql = ("SELECT o.cl_opinion_id FROM opinions o JOIN clusters c USING (cl_cluster_id) "
           "WHERE c.court = ? AND c.date_filed >= ? AND c.date_filed < ? "
           "AND o.superseded_by IS NULL AND o.parse_status = 'ok'")
    params: list = [_court(period), lo, hi]
    if period.court != "supreme":
        sql += " AND o.district = ?"
        params.append(str(period.district))
        if period.division:
            sql += " AND o.division = ?"
            params.append(period.division)
    return {r[0] for r in conn.execute(sql, params)}


def _justice_ids(conn, slug: str, lo: str, hi: str) -> set[int]:
    return {r[0] for r in conn.execute(
        "SELECT o.cl_opinion_id FROM opinions o JOIN clusters c USING (cl_cluster_id) "
        "WHERE c.date_filed >= ? AND c.date_filed < ? AND o.superseded_by IS NULL "
        "AND o.parse_status = 'ok' AND (o.cl_opinion_id IN "
        "(SELECT cl_opinion_id FROM panel_seats WHERE slug = ?) OR o.cl_opinion_id IN "
        "(SELECT cl_opinion_id FROM separate_opinions WHERE author_slug = ?))",
        (lo, hi, slug, slug))}


def _in(ids: set[int]) -> str:
    return ",".join(str(i) for i in sorted(ids)) or "NULL"


def _rate(num: int, den: int, scale: float = 1.0) -> float | None:
    return scale * num / den if den else None


def compute(
    conn: sqlite3.Connection,
    periods: list[ServicePeriod],
    window_start: str,
    window_end: str,
    limited: set[str],
    validated_districts: set[str],
) -> list[dict]:
    by_slug: dict[str, list[ServicePeriod]] = defaultdict(list)
    for p in periods:
        by_slug[p.slug].append(p)
    topics = [r[0] for r in conn.execute("SELECT DISTINCT topic FROM topic_tags ORDER BY 1")]
    end_exclusive = (date.fromisoformat(window_end) + timedelta(days=1)).isoformat()
    rows: list[dict] = []

    for slug, ps in sorted(by_slug.items()):
        if not any(_district_key(p) in validated_districts for p in ps):
            continue
        supreme = all(p.court == "supreme" for p in ps)
        start = max(window_start, min(p.start.lower.isoformat() for p in ps))
        baseline: set[int] = set()
        for p in ps:
            lo = max(start, p.start.lower.isoformat())
            hi = min(end_exclusive, p.end.lower.isoformat() if p.end else end_exclusive)
            if lo < hi:
                baseline |= _slice_ids(conn, p, lo, hi)
        mine = _justice_ids(conn, slug, start, end_exclusive)
        is_limited = slug in limited

        def row(metric, value, base=None, base_n=None, n=None, topic="", note="",
                _slug=slug, _start=start, _limited=is_limited):
            if _limited and metric.endswith(("_rate", "_per_100_panels")):
                value, base, note = None, None, LIMITED_NOTE
            rows.append({"slug": _slug, "metric": metric, "topic": topic, "value": value,
                         "baseline": base, "baseline_n": base_n, "n": n,
                         "window_start": _start, "window_end": window_end, "note": note})

        def q(sql, params=()):
            return conn.execute(sql, params).fetchone()[0]

        m, b = _in(mine), _in(baseline)
        authored = q(f"SELECT COUNT(*) FROM opinions WHERE cl_opinion_id IN ({m}) "
                     "AND author_slug = ? AND per_curiam IS NOT 1", (slug,))
        authored_pub = q(f"SELECT COUNT(*) FROM opinions WHERE cl_opinion_id IN ({m}) "
                         "AND author_slug = ? AND per_curiam IS NOT 1 AND published = 1", (slug,))
        panels = len(mine)
        row("authored_total", authored)
        row("panels", panels)
        if not supreme:
            row("authored_published", authored_pub)
            row("authored_unpublished", authored - authored_pub)
            base_auth = q(f"SELECT COUNT(*) FROM opinions WHERE cl_opinion_id IN ({b}) "
                          "AND author_slug IS NOT NULL AND per_curiam IS NOT 1")
            base_pub = q(f"SELECT COUNT(*) FROM opinions WHERE cl_opinion_id IN ({b}) "
                         "AND author_slug IS NOT NULL AND per_curiam IS NOT 1 AND published = 1")
            row("publication_rate", _rate(authored_pub, authored), _rate(base_pub, base_auth),
                base_auth, authored)

        base_seats = q(f"SELECT COUNT(*) FROM (SELECT DISTINCT cl_opinion_id, seat_raw FROM "
                       f"panel_seats WHERE cl_opinion_id IN ({b}))")
        for label, types in (("dissents", DISSENT_TYPES), ("concurrences", ("concurrence",))):
            marks = ",".join("?" * len(types))
            mine_n = q(f"SELECT COUNT(*) FROM separate_opinions WHERE cl_opinion_id IN ({m}) "
                       f"AND author_slug = ? AND type IN ({marks})", (slug, *types))
            base_n = q(f"SELECT COUNT(*) FROM separate_opinions WHERE cl_opinion_id IN ({b}) "
                       f"AND type IN ({marks})", types)
            row(label, mine_n)
            row(f"{label}_per_100_panels", _rate(mine_n, panels, 100),
                _rate(base_n, base_seats, 100), base_seats, panels)

        for topic in topics:
            tagged = {r[0] for r in conn.execute(
                f"SELECT cl_opinion_id FROM topic_tags WHERE topic = ? AND tagged = 1 "
                f"AND cl_opinion_id IN ({m})", (topic,))}
            t = _in(tagged)
            row("topic_authored", q(f"SELECT COUNT(*) FROM opinions WHERE cl_opinion_id IN "
                                    f"({t}) AND author_slug = ?", (slug,)), topic=topic)
            row("topic_panels", len(tagged), topic=topic)
            dissented = {r[0] for r in conn.execute(
                f"SELECT cl_opinion_id FROM separate_opinions WHERE cl_opinion_id IN ({t}) "
                "AND author_slug = ? AND type IN ('dissent', 'concur_dissent')", (slug,))}
            split = {r[0] for r in conn.execute(
                f"SELECT cl_opinion_id FROM opinions WHERE cl_opinion_id IN ({t}) "
                "AND has_dissent = 1")}
            row("contested_majority", len(split - dissented), topic=topic,
                note="topic-tagged opinions with any dissent, justice in the majority")
            row("contested_dissent", len(dissented), topic=topic,
                note="topic-tagged opinions where the justice dissented")
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: ("" if r[k] is None else
                                 (f"{r[k]:.4f}" if isinstance(r[k], float) else r[k]))
                             for k in FIELDS})


def main() -> int:
    import json

    from src import config, db, justices

    settings = config.load()
    conn = db.connect(settings.path("database"))
    status_file = settings.path("validation") / "status.json"
    if not status_file.exists():
        print("No validation status yet (data/validation/status.json). Run the parsing "
              "validation gate (U6) first; metrics are not computed before it passes.")
        return 1
    status = json.loads(status_file.read_text())
    validated = {d for d, ok in status.get("districts", {}).items() if ok}
    run_date = settings.raw["render"].get("snapshot_date") or date.today().isoformat()
    limited = {s for s, v in justices.compute_limited_records(
        date.fromisoformat(run_date)).items() if v}
    ballot = {j["slug"] for j in justices.load_justices()}
    periods = [p for p in justices.load_service_periods() if p.slug in ballot]
    rows = compute(conn, periods, settings.raw["window"]["start"], run_date, limited, validated)
    out = settings.path("guide") / "data" / "metrics.csv"
    write_csv(rows, out)
    print(f"wrote {len(rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
