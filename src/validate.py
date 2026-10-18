"""Parsing validation gate (U6, KTD10) and tag validation scoring (U7).

    python -m src.validate sample --seed N        # draw the parse sample, export packets
    python -m src.validate score                  # score labels -> report + status.json
    python -m src.validate tag-sample --seed N    # precision + recall samples for search_seizure
    python -m src.validate tag-score              # score tag labels -> report_tags.md

Labels come from a session that never sees parser output: packets contain the
opinion text only. The owner audits 20 labels; an `owner_ruling` of "parser"
on a disagreement means the parser was right and the label was wrong.
"""

from __future__ import annotations

import csv
import json
import math
import random
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

THRESHOLDS = {"author": 0.98, "panel": 0.97, "separate": 0.95}
GATED_STRATA = {"4": 60, "supreme": 30}
OTHER_DISTRICT_MIN = 15
TOTAL_MIN = 200
SEPARATE_MIN = 20
TAG_PRECISION_MIN = 0.85
LABEL_FIELDS = ["cl_opinion_id", "author", "panel", "separate", "per_curiam", "notes",
                "owner_ruling"]


def norm_name(name: str | None) -> str:
    if not name:
        return ""
    name = name.split(",")[0]
    name = unicodedata.normalize("NFKD", name)
    name = "".join(ch for ch in name if not unicodedata.combining(ch))
    name = re.sub(r"[^A-Za-z ]", " ", name).upper()
    # Compare surnames only: drop titles and initials, ignore spacing
    # ("Chief Justice Cantil-Sakauye" = "CANTIL-SAKAUYE", "D KIM" = "KIM (D.)").
    tokens = [t for t in name.split() if len(t) > 1 and t not in _TITLE_WORDS]
    return "".join(tokens)


_TITLE_WORDS = {"CHIEF", "JUSTICE", "PRESIDING", "ACTING", "ASSOCIATE", "JUDGE"}


def _pool(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT o.cl_opinion_id AS id, c.court, o.district, o.published, o.per_curiam, "
        "o.partial_publication AS partial, "
        "(COALESCE(o.has_dissent, 0) OR COALESCE(o.has_concurrence, 0)) AS separate "
        "FROM opinions o JOIN clusters c USING (cl_cluster_id) "
        "WHERE o.parse_status = 'ok' AND o.superseded_by IS NULL ORDER BY o.cl_opinion_id"
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["stratum"] = "supreme" if r["court"] == "cal" else str(r["district"])
        out.append(d)
    return out


def draw_parse_sample(conn: sqlite3.Connection, seed: int) -> list[int]:
    rng = random.Random(seed)
    pool = _pool(conn)
    picked: dict[int, dict] = {}

    def take(candidates: list[dict], k: int) -> None:
        candidates = [c for c in candidates if c["id"] not in picked]
        for c in rng.sample(candidates, min(k, len(candidates))):
            picked[c["id"]] = c

    by_stratum = defaultdict(list)
    for r in pool:
        by_stratum[r["stratum"]].append(r)
    for stratum, k in GATED_STRATA.items():
        take(by_stratum[stratum], k)
    for stratum in sorted(by_stratum):
        if stratum not in GATED_STRATA:
            take(by_stratum[stratum], OTHER_DISTRICT_MIN)
    have_sep = sum(1 for c in picked.values() if c["separate"])
    take([r for r in pool if r["separate"]], max(0, SEPARATE_MIN - have_sep))
    for flag, k in (("per_curiam", 5), ("partial", 3)):
        if sum(1 for c in picked.values() if c[flag]) < k:
            take([r for r in pool if r[flag]], k)
    for status in (0, 1):
        if not any((c["published"] or 0) == status for c in picked.values()):
            take([r for r in pool if (r["published"] or 0) == status], 1)
    take(pool, max(0, TOTAL_MIN - len(picked)))
    return sorted(picked)


def export_packets(conn: sqlite3.Connection, ids: list[int], out_dir: Path) -> None:
    """Text-only labeling packets: nothing the parser produced."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for oid in ids:
        text = conn.execute(
            "SELECT text FROM opinions WHERE cl_opinion_id = ?", (oid,)).fetchone()[0]
        (out_dir / f"{oid}.txt").write_text(f"cl_opinion_id: {oid}\n----\n{text}")


def write_label_template(ids: list[int], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=LABEL_FIELDS, lineterminator="\n")
        w.writeheader()
        for oid in ids:
            w.writerow({"cl_opinion_id": oid})


def _parser_view(conn: sqlite3.Connection, oid: int) -> dict:
    o = conn.execute(
        "SELECT o.author_raw, o.per_curiam, o.district, c.court FROM opinions o "
        "JOIN clusters c USING (cl_cluster_id) WHERE o.cl_opinion_id = ?", (oid,)).fetchone()
    panel = {norm_name(r[0]) for r in conn.execute(
        "SELECT seat_raw FROM panel_seats WHERE cl_opinion_id = ?", (oid,))}
    separate = {(r[0], norm_name(r[1])) for r in conn.execute(
        "SELECT type, author_raw FROM separate_opinions WHERE cl_opinion_id = ?", (oid,))}
    return {
        "author": "" if o["per_curiam"] else norm_name(o["author_raw"]),
        "panel": panel,
        "separate": separate,
        "stratum": "supreme" if o["court"] == "cal" else str(o["district"]),
    }


def _label_view(row: dict) -> dict:
    per_curiam = str(row.get("per_curiam") or "0").strip() in ("1", "true", "yes")
    separate = set()
    for item in filter(None, (row.get("separate") or "").split(";")):
        kind, _, who = item.partition(":")
        separate.add((kind.strip(), norm_name(who)))
    return {
        "author": "" if per_curiam else norm_name(row.get("author")),
        "panel": {norm_name(n) for n in (row.get("panel") or "").split(";") if n.strip()},
        "separate": separate,
    }


def _allowed(n: int, threshold: float) -> int:
    return math.floor(round(n * (1 - threshold), 9))


def _summarize(tallies: dict[str, list[bool]]) -> dict:
    out = {}
    for field, threshold in THRESHOLDS.items():
        results = tallies.get(field, [])
        n, errors = len(results), sum(1 for ok in results if not ok)
        allowed = _allowed(n, threshold)
        out[field] = {"n": n, "errors": errors, "allowed": allowed,
                      "rate": (n - errors) / n if n else None, "pass": n > 0 and errors <= allowed}
    return out


def score(conn: sqlite3.Connection, labels_path: Path) -> dict:
    pooled: dict[str, list[bool]] = defaultdict(list)
    per_stratum: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    with open(labels_path, newline="") as fh:
        for row in csv.DictReader(fh):
            if not row.get("author") and not row.get("panel") and not row.get("per_curiam"):
                continue  # not labeled yet
            oid = int(row["cl_opinion_id"])
            parser, label = _parser_view(conn, oid), _label_view(row)
            parser_wins = (row.get("owner_ruling") or "").strip().lower() == "parser"
            for field in THRESHOLDS:
                ok = parser_wins or parser[field] == label[field]
                pooled[field].append(ok)
                per_stratum[parser["stratum"]][field].append(ok)
    pooled_summary = _summarize(pooled)
    pooled_pass = all(f["pass"] for f in pooled_summary.values())
    strata = {s: _summarize(t) for s, t in per_stratum.items()}
    districts = {}
    for stratum, summary in strata.items():
        own = all(f["pass"] for f in summary.values())
        gated = stratum in GATED_STRATA and summary["author"]["n"] >= GATED_STRATA[stratum]
        districts[stratum] = pooled_pass and (own if gated else True)
    return {"pooled": pooled_summary, "strata": strata,
            "status": {"pooled": pooled_pass, "districts": districts}}


def report_markdown(result: dict) -> str:
    lines = ["# Parsing validation report", "",
             "Thresholds (SPEC §7.3.8): author ≥ 98%, panel membership ≥ 97%, "
             "separate-opinion detection ≥ 95%. The pooled sample must pass; the 4th "
             "District (≥ 60 labeled) and the Supreme Court (≥ 30) are also gated on their "
             "own strata, stated as allowed error counts.", "",
             "| Stratum | Field | N | Errors | Allowed | Accuracy | Pass |",
             "|---|---|---|---|---|---|---|"]
    rows = [("pooled", result["pooled"])] + sorted(result["strata"].items())
    for stratum, summary in rows:
        for field, s in summary.items():
            acc = "" if s["rate"] is None else f"{100 * s['rate']:.1f}%"
            lines.append(f"| {stratum} | {field} | {s['n']} | {s['errors']} | {s['allowed']} "
                         f"| {acc} | {'yes' if s['pass'] else 'no'} |")
    lines += ["", "District status: " + ", ".join(
        f"{d}: {'pass' if ok else 'FAIL'}" for d, ok in sorted(result["status"]["districts"]
                                                              .items()))]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- tags (U7)

def draw_tag_samples(conn: sqlite3.Connection, seed: int, topic: str = "search_seizure",
                     precision_n: int = 50, recall_n: int = 60) -> tuple[list[int], list[int]]:
    rng = random.Random(seed)
    tagged = [r[0] for r in conn.execute(
        "SELECT cl_opinion_id FROM topic_tags WHERE topic = ? AND tagged = 1 ORDER BY 1",
        (topic,))]
    untagged = [r[0] for r in conn.execute(
        "SELECT o.cl_opinion_id FROM opinions o JOIN clusters c USING (cl_cluster_id) "
        "WHERE (c.court = 'cal' OR o.district = '4') AND c.case_name LIKE 'People v.%' "
        "AND o.cl_opinion_id NOT IN (SELECT cl_opinion_id FROM topic_tags WHERE topic = ? "
        "AND tagged = 1) ORDER BY 1", (topic,))]
    return (sorted(rng.sample(tagged, min(precision_n, len(tagged)))),
            sorted(rng.sample(untagged, min(recall_n, len(untagged)))))


def score_tags(path: Path) -> dict:
    precision, recall = [], []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("at_issue", "").strip() == "":
                continue
            value = row["at_issue"].strip() == "1"
            (precision if row["sample"] == "precision" else recall).append(value)
    p = sum(precision) / len(precision) if precision else None
    return {
        "precision": p,
        "precision_n": len(precision),
        "precision_pass": p is not None and p >= TAG_PRECISION_MIN,
        "missed_in_untagged": sum(recall),
        "recall_sample_n": len(recall),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    from src import config, db

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("sample", "tag-sample"):
        sub.add_parser(name).add_argument("--seed", type=int, required=True)
    sub.add_parser("score")
    sub.add_parser("tag-score")
    args = parser.parse_args(argv)

    settings = config.load()
    conn = db.connect(settings.path("database"))
    vdir = settings.path("validation")
    packets = settings.path("review") / "labeling"
    if args.cmd == "sample":
        ids = draw_parse_sample(conn, args.seed)
        export_packets(conn, ids, packets / "parse")
        (vdir / "sample_parse.csv").parent.mkdir(parents=True, exist_ok=True)
        (vdir / "sample_parse.csv").write_text(
            f"# seed {args.seed}\ncl_opinion_id\n" + "".join(f"{i}\n" for i in ids))
        labels = vdir / "labels_parse.csv"
        if not labels.exists():
            write_label_template(ids, labels)
        print(f"{len(ids)} opinions; packets in {packets / 'parse'}")
    elif args.cmd == "score":
        result = score(conn, vdir / "labels_parse.csv")
        (vdir / "report_parse.md").write_text(report_markdown(result))
        (vdir / "status.json").write_text(json.dumps(result["status"], indent=2,
                                                      sort_keys=True) + "\n")
        print(json.dumps(result["status"], indent=2))
    elif args.cmd == "tag-sample":
        prec, rec = draw_tag_samples(conn, args.seed)
        export_packets(conn, prec + rec, packets / "tags")
        with open(vdir / "labels_tags.csv", "w", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["cl_opinion_id", "sample", "at_issue", "notes"])
            w.writerows([[i, "precision", "", ""] for i in prec] +
                        [[i, "recall", "", ""] for i in rec])
        print(f"precision sample {len(prec)}, recall sample {len(rec)}")
    elif args.cmd == "tag-score":
        result = score_tags(vdir / "labels_tags.csv")
        p = result["precision"]
        (vdir / "report_tags.md").write_text(
            "# Tag validation: search_seizure\n\n"
            "Precision: share of tagged opinions that address a search or seizure claim on "
            "the merits or rule it forfeited (KTD9).\n\n"
            f"- Precision: {'n/a' if p is None else f'{100 * p:.1f}%'} "
            f"(N = {result['precision_n']}; target ≥ 85%: "
            f"{'pass' if result['precision_pass'] else 'FAIL'})\n"
            f"- Recall check: {result['missed_in_untagged']} of {result['recall_sample_n']} "
            "untagged 4th District and Supreme Court criminal opinions had a search or "
            "seizure issue the tag missed.\n")
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
