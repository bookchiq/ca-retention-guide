"""Coverage report for the owner's window decision (R6): opinion counts per year
by court and publication status, plus a projected Tier 1 reading workload for
each window option."""

from __future__ import annotations

import sqlite3
from collections import defaultdict

# Tier 1 search_seizure anchors from SPEC §7.4. Used only for the workload
# projection; tagging itself reads data/keywords.yaml (U7).
SEARCH_SEIZURE_ANCHORS = (
    "fourth amendment", "motion to suppress", "section 1538.5", "§ 1538.5",
    "search warrant", "warrantless", "exclusionary rule", "calecpa",
    "electronic communications privacy act", "section 1546",
)
SAN_DIEGO_PREFIXES = ("D", "E", "G")  # 4th District divisions One, Two, Three
LOW_SHARE = 0.8


def _status_bucket(status: str | None) -> str:
    if status == "Published":
        return "published"
    if status == "Unpublished":
        return "unpublished"
    return "other"


def build_report(
    conn: sqlite3.Connection, expected_per_year: int, window_options: list[str]
) -> str:
    counts: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"published": 0, "unpublished": 0, "other": 0}
    )
    for row in conn.execute(
        "SELECT substr(date_filed, 1, 4) AS year, court, precedential_status, COUNT(*) AS n "
        "FROM clusters GROUP BY year, court, precedential_status"
    ):
        counts[(row["year"], row["court"])][_status_bucket(row["precedential_status"])] += row["n"]

    lines = [
        "# Coverage report",
        "",
        "Opinion clusters per year in `data/cases.sqlite`, by court and publication status. "
        f"A Court of Appeal year below {int(LOW_SHARE * 100)}% of the expected "
        f"~{expected_per_year:,} opinions is flagged LOW.",
        "",
        "| Year | Court | Published | Unpublished | Other | Total | Flag |",
        "|---|---|---|---|---|---|---|",
    ]
    for (year, court), c in sorted(counts.items()):
        total = sum(c.values())
        flag = ""
        if court == "calctapp" and total < LOW_SHARE * expected_per_year:
            flag = "LOW"
        lines.append(
            f"| {year} | {court} | {c['published']} | {c['unpublished']} | {c['other']} "
            f"| {total} | {flag} |"
        )

    anchor_sql = " OR ".join("lower(o.text) LIKE ?" for _ in SEARCH_SEIZURE_ANCHORS)
    params = [f"%{a}%" for a in SEARCH_SEIZURE_ANCHORS]
    prefix_sql = " OR ".join("c.docket_number LIKE ?" for _ in SAN_DIEGO_PREFIXES)
    prefix_params = [f"{p}%" for p in SAN_DIEGO_PREFIXES]

    lines += [
        "",
        "## Projected Tier 1 reading workload",
        "",
        "Opinions with at least one `search_seizure` anchor term, in the courts the San Diego "
        "set sits on. This is an upper bound on what the reading queue draws from: the queue "
        "only includes cases a given justice wrote, joined over a dissent, or that were "
        "reversed or published.",
        "",
        "| Window starts | 4th District opinions with an anchor | Supreme Court opinions "
        "with an anchor |",
        "|---|---|---|",
    ]
    for start in window_options:
        fourth = conn.execute(
            f"SELECT COUNT(*) FROM opinions o JOIN clusters c USING (cl_cluster_id) "
            f"WHERE c.court = 'calctapp' AND c.date_filed >= ? AND ({prefix_sql}) "
            f"AND ({anchor_sql})",
            [start, *prefix_params, *params],
        ).fetchone()[0]
        supreme = conn.execute(
            f"SELECT COUNT(*) FROM opinions o JOIN clusters c USING (cl_cluster_id) "
            f"WHERE c.court = 'cal' AND c.date_filed >= ? AND ({anchor_sql})",
            [start, *params],
        ).fetchone()[0]
        lines.append(f"| {start} | {fourth} | {supreme} |")
    return "\n".join(lines) + "\n"
