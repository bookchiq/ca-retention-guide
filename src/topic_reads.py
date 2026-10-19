"""Reading-based topic coverage, for topics no keyword rule can count accurately (2026-10-19).

    python -m src.topic_reads prepare --topic T            # first-read batches
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
    """Set topic_tags.tagged from read decisions for every `method: read` topic."""
    done = {}
    for topic, spec in topics.items():
        if spec.get("method") != "read":
            continue
        path = reads_dir / f"{topic}.csv"
        if not path.exists():
            continue
        yes = {oid for oid, v in final_decisions(path).items() if v}
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
    ballot = {j["slug"] for j in justices.load_justices()}
    ids = pool(conn, topic, settings.raw["window"]["start"], ballot)
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
        status.setdefault(topic, {"rounds": []})["read"] = s
        status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
        print(json.dumps(s, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
