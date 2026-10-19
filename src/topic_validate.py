"""Keyword validation for every topic, not just search and seizure (owner request 2026-10-18).

    python -m src.topic_validate sample --topic T --round r1 --seed N
    python -m src.topic_validate score  --topic T --round r1
    python -m src.topic_validate report

Each round draws two samples from opinions in the metrics universe (in the window, not a
superseded duplicate):

- precision: opinions the current rule tags. Share that address the topic = precision.
- probe: untagged opinions containing one of the topic's probe words (near misses). Share
  that address the topic, times the probe pool, estimates what the rule misses.

Labelers get a shuffled packet folder and a blank label file, with the topic's definition.
The key saying which sample each opinion came from is written elsewhere and joined only
when scoring. A round never reuses an opinion labeled in an earlier round for that topic.
"""

from __future__ import annotations

import csv
import json
import random
import re
import sqlite3
import sys
from pathlib import Path

from src import tag

PRECISION_MIN = 0.85
PRECISION_N = 50
PROBE_N = 30


def _universe(conn: sqlite3.Connection, window_start: str) -> str:
    return ("SELECT o.cl_opinion_id FROM opinions o JOIN clusters c USING (cl_cluster_id) "
            f"WHERE o.superseded_by IS NULL AND c.date_filed >= '{window_start}'")


def tagged_ids(conn: sqlite3.Connection, topic: str, window_start: str) -> list[int]:
    return [r[0] for r in conn.execute(
        f"SELECT cl_opinion_id FROM topic_tags WHERE topic = ? AND tagged = 1 "
        f"AND cl_opinion_id IN ({_universe(conn, window_start)}) ORDER BY 1", (topic,))]


def probe_ids(conn: sqlite3.Connection, topic: str, probes: list[str],
              window_start: str) -> list[int]:
    tagged = set(tagged_ids(conn, topic, window_start))
    # Opinions with a keyword hit that the topic's rule does not tag (for a tightened rule,
    # what it drops) are near misses too.
    below_rule = {r[0] for r in conn.execute(
        "SELECT cl_opinion_id FROM topic_tags WHERE topic = ? AND tagged = 0", (topic,))}
    # Probes match at the start of a word, as prefixes ("interrogat" finds "interrogation";
    # "lease" does not find "release", nor "tenant" "lieutenant").
    pattern = re.compile(r"(?<![a-z0-9])(?:" + "|".join(
        re.escape(tag.normalize(p)) for p in sorted(probes, key=len, reverse=True)) + ")")
    out = []
    for oid, text in conn.execute(
            f"SELECT cl_opinion_id, text FROM opinions WHERE cl_opinion_id IN "
            f"({_universe(conn, window_start)}) ORDER BY 1"):
        if oid in tagged:
            continue
        if oid in below_rule or pattern.search(tag.normalize(text or "")):
            out.append(oid)
    return out


def anchor_features(text: str, spec: dict) -> tuple[int, int]:
    """(distinct anchors, total anchor occurrences), matched the way the tagger matches."""
    norm = tag.normalize(text or "")
    prefixes = {tag.normalize(p) for p in spec.get("prefix_terms", [])}
    distinct = total = 0
    for term in spec.get("anchors", []):
        t = tag.normalize(term)
        tail = "" if t in prefixes else r"(?![a-z0-9])"
        n = len(re.findall(rf"(?<![a-z0-9]){re.escape(t)}{tail}", norm))
        distinct += n > 0
        total += n
    return distinct, total


def draw(precision_pool: list[int], probe_pool: list[int], seed: int, exclude: set[int],
         precision_n: int = PRECISION_N, probe_n: int = PROBE_N) -> tuple[list[int], list[int]]:
    rng = random.Random(seed)
    prec_pool = [i for i in precision_pool if i not in exclude]
    prec = rng.sample(prec_pool, min(precision_n, len(prec_pool)))
    probe_pool = [i for i in probe_pool if i not in exclude and i not in set(prec)]
    probe = rng.sample(probe_pool, min(probe_n, len(probe_pool)))
    return sorted(prec), sorted(probe)


def write_round(conn: sqlite3.Connection, packet_dir: Path, key_path: Path, prec: list[int],
                probe: list[int], seed: int, meta: dict) -> list[int]:
    """Blind packets + blank label file (shuffled), and a separate key."""
    order = prec + probe
    random.Random(seed + 1).shuffle(order)
    (packet_dir / "packets").mkdir(parents=True, exist_ok=True)
    for oid in order:
        text = conn.execute("SELECT text FROM opinions WHERE cl_opinion_id = ?",
                            (oid,)).fetchone()[0]
        (packet_dir / "packets" / f"{oid}.txt").write_text(f"cl_opinion_id: {oid}\n----\n{text}")
    with open(packet_dir / "labels_raw.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["cl_opinion_id", "at_issue", "notes"])
        w.writerows([[oid, "", ""] for oid in order])
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(json.dumps({
        **meta, "seed": seed,
        "sample": {str(i): "precision" for i in prec} | {str(i): "probe" for i in probe},
    }, indent=2, sort_keys=True) + "\n")
    return order


def score_round(labels: list[dict], key: dict, features: dict[int, tuple[int, int]]) -> dict:
    rows = []
    for r in labels:
        value = (r.get("at_issue") or "").strip()
        if value not in ("0", "1"):
            raise ValueError(f"opinion {r['cl_opinion_id']}: at_issue must be 0 or 1")
        oid = int(r["cl_opinion_id"])
        distinct, total = features.get(oid, (0, 0))
        rows.append({"cl_opinion_id": oid, "sample": key["sample"][str(oid)],
                     "at_issue": int(value), "anchors_distinct": distinct,
                     "anchor_occurrences": total, "notes": r.get("notes", "")})
    prec = [r["at_issue"] for r in rows if r["sample"] == "precision"]
    probe = [r["at_issue"] for r in rows if r["sample"] == "probe"]
    precision = sum(prec) / len(prec) if prec else None
    probe_rate = sum(probe) / len(probe) if probe else 0.0
    est_missed = round(probe_rate * key["probe_pool"])
    est_found = round((precision or 0) * key["tagged"])
    return {
        "rows": sorted(rows, key=lambda r: r["cl_opinion_id"]),
        "summary": {
            "round": key["round"], "rule": key["rule"], "tagged": key["tagged"],
            "precision": precision, "precision_n": len(prec),
            "precision_pass": precision is not None and precision >= PRECISION_MIN,
            "probe_pool": key["probe_pool"], "probe_n": len(probe), "probe_hits": sum(probe),
            "est_missed": est_missed,
            "undercount_share": (est_missed / (est_found + est_missed)
                                 if est_found + est_missed else None),
        },
    }


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def undercount_text(s: dict) -> str:
    """A near-miss sample with no hits bounds the undercount; it does not prove it is zero."""
    if s.get("probe_n") and not s.get("probe_hits"):
        return "none found in sample"
    return _pct(s.get("undercount_share"))


def report_markdown(status: dict, topics: dict, titles: dict) -> str:
    lines = [
        "# Topic keyword validation",
        "",
        "For each topic, a random sample of the opinions its keyword rule tags was labeled by "
        "sessions that saw only the opinion text and the topic's definition, in shuffled order, "
        "mixed with near-miss opinions the rule does not tag. Precision is the share of tagged "
        f"opinions that address the topic; a topic is shown on the pages only at "
        f"{PRECISION_MIN:.0%} or higher on a sample not used to choose its rule. The undercount "
        "estimate scales the near-miss hits to the whole near-miss pool.",
        "",
        "| Topic | Round | Rule | Tagged | Precision | Near-miss hits | Est. undercount | "
        "Shown |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for topic in sorted(status, key=lambda t: titles.get(t, t)):
        rounds = status[topic]["rounds"]
        shown = "yes" if topics.get(topic, {}).get("validated") else "no"
        for i, s in enumerate(rounds):
            lines.append(
                f"| {titles.get(topic, topic)} | {s['round']} | {s['rule']} | {s['tagged']} | "
                f"{_pct(s['precision'])} (N = {s['precision_n']}) | "
                f"{s['probe_hits']} of {s['probe_n']} | {undercount_text(s)} | "
                f"{shown if i == len(rounds) - 1 else '—'} |")
    lines += ["", "Per-opinion labels: `labels_topic_<topic>_<round>.csv` in this folder."]
    return "\n".join(lines) + "\n"


def rule_text(spec: dict) -> str:
    rule = spec.get("tag_rule")
    if not rule:
        return "any anchor"
    parts = [f"≥{rule['min_distinct_anchors']} distinct anchors"]
    if rule.get("min_core_hits"):
        parts.append(f"≥{rule['min_core_hits']} core-term uses")
    if rule.get("min_anchor_occurrences"):
        parts.append(f"≥{rule['min_anchor_occurrences']} anchor uses")
    return ", ".join(parts)


def main(argv: list[str] | None = None) -> int:
    import argparse

    from src import config, db, render

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--topic", required=True)
    s.add_argument("--round", required=True)
    s.add_argument("--seed", type=int, required=True)
    sc = sub.add_parser("score")
    sc.add_argument("--topic", required=True)
    sc.add_argument("--round", required=True)
    sub.add_parser("report")
    args = parser.parse_args(argv)

    settings = config.load()
    window = settings.raw["window"]["start"]
    topics = tag.load_keywords()
    vdir = settings.path("validation")
    labeling = settings.path("review") / "labeling" / "topics"
    keys = settings.path("review") / "labeling" / "topic_keys"
    status_path = vdir / "topic_status.json"
    status = json.loads(status_path.read_text()) if status_path.exists() else {}

    if args.cmd in ("sample", "score"):
        conn = db.connect(settings.path("database"))
        spec = topics[args.topic]
        folder = labeling / args.topic / args.round
        key_path = keys / f"{args.topic}_{args.round}.json"
    if args.cmd == "sample":
        seen: set[int] = set()
        for old in vdir.glob(f"labels_topic_{args.topic}_*.csv"):
            with open(old, newline="") as fh:
                seen |= {int(r["cl_opinion_id"]) for r in csv.DictReader(fh)}
        tagged = tagged_ids(conn, args.topic, window)
        probes = probe_ids(conn, args.topic, spec.get("probe", []), window)
        prec, probe = draw(tagged, probes, args.seed, seen)
        write_round(conn, folder, key_path, prec, probe, args.seed, {
            "topic": args.topic, "round": args.round, "rule": rule_text(spec),
            "tagged": len(tagged), "probe_pool": len(probes)})
        print(f"{args.topic} {args.round}: tagged {len(tagged)}, probe pool {len(probes)}; "
              f"drew {len(prec)} + {len(probe)} -> {folder}")
    elif args.cmd == "score":
        key = json.loads(key_path.read_text())
        with open(folder / "labels_raw.csv", newline="") as fh:
            labels = list(csv.DictReader(fh))
        feats = {}
        for r in labels:
            text = conn.execute("SELECT text FROM opinions WHERE cl_opinion_id = ?",
                                (int(r["cl_opinion_id"]),)).fetchone()[0]
            feats[int(r["cl_opinion_id"])] = anchor_features(text, spec)
        result = score_round(labels, key, feats)
        out = vdir / f"labels_topic_{args.topic}_{args.round}.csv"
        with open(out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(result["rows"][0]), lineterminator="\n")
            w.writeheader()
            w.writerows(result["rows"])
        entry = status.setdefault(args.topic, {"rounds": []})
        entry["rounds"] = [r for r in entry["rounds"] if r["round"] != args.round]
        entry["rounds"].append(result["summary"])
        entry["rounds"].sort(key=lambda r: r["round"])
        status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
        print(json.dumps(result["summary"], indent=2))
    if args.cmd in ("score", "report"):
        (vdir / "report_topics.md").write_text(
            report_markdown(status, topics, render.TOPIC_TITLES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
