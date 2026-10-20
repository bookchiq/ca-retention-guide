"""Reading-based topic coverage, for topics no keyword rule can count accurately (2026-10-19).

    python -m src.topic_reads prepare --topic T            # first-read batches (pool frozen)
    python -m src.topic_reads second  --topic T --seed N   # blind 15% second read
    python -m src.topic_reads collect --topic T            # merge -> data/topic_reads/T.csv
    python -m src.topic_reads tiebreak --topic T           # batch of disagreements
    python -m src.topic_reads apply                        # decisions -> topic_tags.tagged

The pool for a topic is every opinion in the metrics universe (in the window, not a
superseded duplicate) that has a ballot justice on the panel and contains at least one
of the topic's anchor terms. Each pool opinion is read once against the topic's written
definition. A random 15% is read again by a different session that does not see the
first decision; disagreements go to a third reader, whose decision is final. Agreement
between the first two readers is published, and a topic is shown only at 90% or higher.
Opinions outside the pool count as not addressing the topic (the published undercount).

Near-miss reading (`near_miss_read: true`, 2026-10-19) is for a keyword topic whose
rule is precise but misses many opinions. Its pool is the near-miss pool the keyword
check measured the undercount on: opinions on a ballot panel that the rule does not tag
but that contain a probe term or a below-rule keyword hit. The same read, second read,
and tiebreak apply; opinions read as addressing the topic are added to the keyword tags.
The pool is frozen when the batches are written, because adding tags shrinks it.
"""

from __future__ import annotations

import csv
import json
import random
import sqlite3
import sys
from pathlib import Path

from src import topic_validate as tv

BATCH_SIZE = 80
SECOND_SHARE = 0.15
AGREEMENT_MIN = 0.90
FIELDS = ["cl_opinion_id", "at_issue", "note", "second_at_issue", "second_note",
          "tiebreak_at_issue", "tiebreak_note", "final"]


def pool(conn: sqlite3.Connection, topic: str, window_start: str, ballot: set[str]) -> list[int]:
    seated = {r[0] for r in conn.execute(
        f"SELECT DISTINCT cl_opinion_id FROM panel_seats WHERE slug IN "
        f"({','.join('?' * len(ballot))})", sorted(ballot))}
    rows = conn.execute(
        f"SELECT cl_opinion_id FROM topic_tags WHERE topic = ? AND anchor_hits > 0 "
        f"AND cl_opinion_id IN ({tv._universe(conn, window_start)}) ORDER BY 1", (topic,))
    return [r[0] for r in rows if r[0] in seated]


def near_miss_pool(conn: sqlite3.Connection, topic: str, probes: list[str], window_start: str,
                   ballot: set[str]) -> list[int]:
    seated = {r[0] for r in conn.execute(
        f"SELECT DISTINCT cl_opinion_id FROM panel_seats WHERE slug IN "
        f"({','.join('?' * len(ballot))})", sorted(ballot))}
    return [oid for oid in tv.probe_ids(conn, topic, probes, window_start) if oid in seated]


def batches(ids: list[int], size: int = BATCH_SIZE) -> list[list[int]]:
    return [ids[i:i + size] for i in range(0, len(ids), size)]


def draw_second(ids: list[int], seed: int, share: float = SECOND_SHARE) -> list[int]:
    k = max(1, round(share * len(ids))) if ids else 0
    return sorted(random.Random(seed).sample(ids, k))


def _read_labels(path: Path) -> dict[int, tuple[str, str]]:
    with open(path, newline="") as fh:
        return {int(r["cl_opinion_id"]): ((r.get("at_issue") or "").strip(), r.get("notes", ""))
                for r in csv.DictReader(fh)}


def merge(first: dict[int, tuple[str, str]], second: dict[int, tuple[str, str]],
          tiebreak: dict[int, tuple[str, str]]) -> list[dict]:
    rows = []
    for oid in sorted(first):
        a, note = first[oid]
        if a not in ("0", "1"):
            raise ValueError(f"opinion {oid}: first read missing")
        b, bnote = second.get(oid, ("", ""))
        c, cnote = tiebreak.get(oid, ("", ""))
        final = a if not b or a == b else c
        rows.append({"cl_opinion_id": oid, "at_issue": a, "note": note,
                     "second_at_issue": b, "second_note": bnote,
                     "tiebreak_at_issue": c, "tiebreak_note": cnote, "final": final})
    return rows


def summary(rows: list[dict], pool_size: int) -> dict:
    both = [r for r in rows if r["second_at_issue"]]
    agree = sum(1 for r in both if r["at_issue"] == r["second_at_issue"])
    pending = sum(1 for r in rows if r["final"] not in ("0", "1"))
    return {
        "method": "read", "pool": pool_size, "read": len(rows),
        "second_n": len(both), "agreement": agree / len(both) if both else None,
        "disagreements": len(both) - agree, "unresolved": pending,
        "addresses_topic": sum(1 for r in rows if r["final"] == "1"),
        "agreement_pass": bool(both) and agree / len(both) >= AGREEMENT_MIN and not pending,
    }


def final_decisions(path: Path) -> dict[int, bool]:
    with open(path, newline="") as fh:
        return {int(r["cl_opinion_id"]): r["final"] == "1" for r in csv.DictReader(fh)}


def apply(conn: sqlite3.Connection, topics: dict, reads_dir: Path) -> dict[str, int]:
    """Set topic_tags.tagged from read decisions: replace the keyword tags of a
    `method: read` topic; add to the keyword tags of a `near_miss_read` topic."""
    done = {}
    for topic, spec in topics.items():
        near_miss = bool(spec.get("near_miss_read")) and spec.get("method") != "read"
        if spec.get("method") != "read" and not near_miss:
            continue
        path = reads_dir / f"{topic}.csv"
        if not path.exists():
            continue
        yes = {oid for oid, v in final_decisions(path).items() if v}
        if near_miss:
            # A probe-only near miss has no keyword hit, so the tagger wrote no row for it.
            conn.executemany(
                "INSERT OR IGNORE INTO topic_tags (cl_opinion_id, topic, anchor_hits, "
                "broad_hits, tagged, queue_match) VALUES (?, ?, 0, 0, 1, 0)",
                [(oid, topic) for oid in sorted(yes)])
        else:
            conn.execute("UPDATE topic_tags SET tagged = 0 WHERE topic = ?", (topic,))
        conn.executemany("UPDATE topic_tags SET tagged = 1 WHERE topic = ? AND cl_opinion_id = ?",
                         [(topic, oid) for oid in sorted(yes)])
        done[topic] = len(yes)
    conn.commit()
    return done


def main(argv: list[str] | None = None) -> int:
    import argparse

    from src import config, db, justices, tag

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("prepare", "second", "collect", "tiebreak"):
        p = sub.add_parser(name)
        p.add_argument("--topic", required=True)
        if name == "second":
            p.add_argument("--seed", type=int, required=True)
    sub.add_parser("apply")
    args = parser.parse_args(argv)

    settings = config.load()
    conn = db.connect(settings.path("database"))
    topics = tag.load_keywords()
    work = settings.path("review") / "reading_topics"
    reads_dir = settings.repo_root / "data" / "topic_reads"
    status_path = settings.path("validation") / "topic_status.json"

    if args.cmd == "apply":
        print(apply(conn, topics, reads_dir))
        return 0

    topic = args.topic
    tdir = work / topic
    spec = topics[topic]
    ballot = {j["slug"] for j in justices.load_justices()}
    window_start = settings.raw["window"]["start"]
    near_miss = bool(spec.get("near_miss_read")) and spec.get("method") != "read"
    if args.cmd == "prepare":
        if near_miss and (reads_dir / f"{topic}.csv").exists():
            print(f"refused: {topic} already has read decisions, which change its near-miss "
                  f"pool; move data/topic_reads/{topic}.csv aside and re-run tagging first")
            return 1
        ids = (near_miss_pool(conn, topic, spec["probe"], window_start, ballot) if near_miss
               else pool(conn, topic, window_start, ballot))
    else:
        # Later steps use the frozen pool: every opinion in the first-read batches.
        ids = sorted({oid for f in tdir.glob("first_*/labels_raw.csv")
                      for oid in _read_labels(f)})
    if args.cmd == "prepare":
        for n, chunk in enumerate(batches(ids), 1):
            order = list(chunk)
            random.Random(n).shuffle(order)
            tv.write_round(conn, tdir / f"first_{n:02d}",
                           work / "keys" / f"{topic}_first_{n:02d}.json", order, [], n,
                           {"topic": topic, "round": "first", "rule": "read",
                            "tagged": len(ids), "probe_pool": 0})
        print(f"{topic}: pool {len(ids)} -> {len(batches(ids))} first-read batches in {tdir}")
    elif args.cmd == "second":
        picked = draw_second(ids, args.seed)
        tv.write_round(conn, tdir / "second", work / "keys" / f"{topic}_second.json", picked, [],
                       args.seed, {"topic": topic, "round": "second", "rule": "read",
                                   "tagged": len(ids), "probe_pool": 0})
        print(f"{topic}: second read of {len(picked)} -> {tdir / 'second'}")
    elif args.cmd in ("collect", "tiebreak"):
        first: dict[int, tuple[str, str]] = {}
        for f in sorted(tdir.glob("first_*/labels_raw.csv")):
            first.update(_read_labels(f))
        second = (_read_labels(tdir / "second" / "labels_raw.csv")
                  if (tdir / "second" / "labels_raw.csv").exists() else {})
        tie = (_read_labels(tdir / "tiebreak" / "labels_raw.csv")
               if (tdir / "tiebreak" / "labels_raw.csv").exists() else {})
        rows = merge(first, {k: v for k, v in second.items() if v[0] in ("0", "1")},
                     {k: v for k, v in tie.items() if v[0] in ("0", "1")})
        if args.cmd == "tiebreak":
            todo = [int(r["cl_opinion_id"]) for r in rows
                    if r["second_at_issue"] and r["at_issue"] != r["second_at_issue"]]
            tv.write_round(conn, tdir / "tiebreak", work / "keys" / f"{topic}_tiebreak.json",
                           todo, [], 7, {"topic": topic, "round": "tiebreak", "rule": "read",
                                         "tagged": len(ids), "probe_pool": 0})
            print(f"{topic}: {len(todo)} disagreements -> {tdir / 'tiebreak'}")
            return 0
        reads_dir.mkdir(parents=True, exist_ok=True)
        with open(reads_dir / f"{topic}.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        s = summary(rows, len(ids))
        status = json.loads(status_path.read_text()) if status_path.exists() else {}
        if near_miss:
            s["method"] = "near_miss_read"
        status.setdefault(topic, {"rounds": []})["near_miss" if near_miss else "read"] = s
        status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
        print(json.dumps(s, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
