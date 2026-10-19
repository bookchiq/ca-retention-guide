"""Review queue, draft case records, verification, second check, promotion (U9).

    python -m src.review queue --set sd17 --tier 1      # build the KTD7 superset queue
    python -m src.review new --justice SLUG --topic T   # scaffold draft stubs to fill in
    python -m src.review verify --justice SLUG --topic T --by SESSION [--ids 1,2 | --all]
    python -m src.review sample --justice SLUG --seed N # draw the KTD8 second-check sample
    python -m src.review check --justice SLUG --id N --pass|--fail --by SESSION [--note TEXT]
    python -m src.review finish-check --justice SLUG
    python -m src.review promote --justice SLUG --topic T
    python -m src.review status

Drafts live in data/drafts/ (gitignored). `promote` is the only writer of the
tracked data/case_notes.jsonl (KTD2), and only for a justice-topic whose whole
queue is decided, verified, and covered by a passed second check (KTD6, KTD8).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

LISTING_RULES = {"L1", "L2", "L3", "L4", "SC"}
ROLES_FOR_RULE = {
    "L1": {"dissent", "concurrence", "concur_dissent"},
    "L2": {"author"},
    "L3": {"author"},
    "SC": {"author"},
    "L4": {"joined_majority_over_dissent", "author"},
}
EXCLUSION_REASONS = {
    "topic_not_at_issue", "topic_issue_affirmed", "dissent_on_other_issue", "duplicate",
    "no_rule_applies",  # at issue, but the justice's role meets no rule (e.g. joined a dissent)
}
POSTURES = {
    "defendant_appeal", "people_appeal", "writ_by_defendant", "writ_by_people", "civil_appeal",
    "other",
}
SECOND_CHECK_DONE = {"passed", "not_sampled"}
SUMMARY_MAX_WORDS = 50
SAMPLE_SHARE = 0.15
OPINION_URL = re.compile(r"^https://www\.courtlistener\.com/opinion/\d+/")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VOTE = re.compile(r"^\d+-\d+$")

# SPEC §9.1 reading order for the San Diego set.
SD_ORDER = [("supreme", None), ("appeal", "One"), ("appeal", "Three"), ("appeal", "Two")]


class PromotionRefused(RuntimeError):
    pass


@dataclass
class Workspace:
    drafts: Path
    queue: Path
    case_notes: Path

    @property
    def checks(self) -> Path:
        return self.queue.parent / "second_check"


# ---------------------------------------------------------------- queue (KTD7)

def build_queue(
    conn: sqlite3.Connection, slug: str, topic: str, start: str, court: str
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT o.cl_opinion_id, o.author_slug, o.published, o.disposition_class,
               o.has_dissent, c.case_name, c.docket_number, c.date_filed, c.absolute_url
        FROM opinions o
        JOIN clusters c USING (cl_cluster_id)
        JOIN topic_tags t ON t.cl_opinion_id = o.cl_opinion_id
             AND t.topic = ? AND t.queue_match = 1
        WHERE c.court = ? AND c.date_filed >= ? AND o.superseded_by IS NULL
        ORDER BY c.date_filed DESC, o.cl_opinion_id DESC
        """,
        (topic, court, start),
    ).fetchall()
    queue = []
    for r in rows:
        oid = r["cl_opinion_id"]
        separate = {
            s["type"] for s in conn.execute(
                "SELECT type FROM separate_opinions WHERE cl_opinion_id = ? AND author_slug = ?",
                (oid, slug),
            )
        }
        on_panel = conn.execute(
            "SELECT 1 FROM panel_seats WHERE cl_opinion_id = ? AND slug = ? "
            "AND role IN ('author', 'joined')",
            (oid, slug),
        ).fetchone()
        authored = r["author_slug"] == slug
        rules = []
        if separate:
            rules.append("L1")
        if court == "cal":
            if authored:
                rules.append("SC")
        else:
            if authored and r["published"]:
                rules.append("L2")
            if authored and (r["disposition_class"] or "other") != "affirmed":
                rules.append("L3")
        dissented = separate & {"dissent", "concur_dissent"}
        if r["has_dissent"] and on_panel and not dissented:
            rules.append("L4")
        if rules:
            queue.append({
                "cl_opinion_id": oid,
                "justice_slug": slug,
                "topic": topic,
                "candidate_rules": rules,
                "case_name": r["case_name"],
                "citation_or_docket": r["docket_number"],
                "date_filed": r["date_filed"],
                "published": bool(r["published"]),
                "opinion_url": f"https://www.courtlistener.com{r['absolute_url']}",
            })
    return queue


# ---------------------------------------------------------------- drafts

def _draft_path(ws: Workspace, slug: str, topic: str) -> Path:
    return ws.drafts / slug / f"{topic}.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n"
                            for r in records))


def load_drafts(ws: Workspace, slug: str) -> list[dict]:
    records = []
    for path in sorted((ws.drafts / slug).glob("*.jsonl")):
        for rec in _read_jsonl(path):
            rec.setdefault("topic", path.stem)
            records.append(rec)
    return records


def save_drafts(ws: Workspace, slug: str, records: list[dict]) -> None:
    by_topic: dict[str, list[dict]] = {}
    for rec in records:
        by_topic.setdefault(rec["topic"], []).append(rec)
    for topic, recs in by_topic.items():
        _write_jsonl(_draft_path(ws, slug, topic), recs)


def scaffold(ws: Workspace, slug: str, topic: str) -> int:
    """Add a stub draft for every queued case that has no draft yet."""
    queue = _read_jsonl(ws.queue / f"{slug}__{topic}.jsonl")
    drafts = _read_jsonl(_draft_path(ws, slug, topic))
    have = {d["cl_opinion_id"] for d in drafts}
    added = 0
    for q in queue:
        if q["cl_opinion_id"] in have:
            continue
        drafts.append({
            **{k: q.get(k) for k in ("cl_opinion_id", "case_name", "citation_or_docket",
                                     "date_filed", "published", "justice_slug", "topic",
                                     "opinion_url", "candidate_rules")},
            "listing_decision": None, "exclusion_reason": None, "role": None,
            "listing_rule": None, "issue_type": None, "posture": None,
            "trial_court_ruling": "", "result_on_issue": "", "outcome": None, "vote": None,
            "summary": "", "verified": False, "verified_by": "", "verified_date": "",
            "verification_notes": "", "second_check": None,
        })
        added += 1
    _write_jsonl(_draft_path(ws, slug, topic), drafts)
    return added


# ---------------------------------------------------------------- validation

def validate_record(rec: dict, topics: dict) -> list[str]:
    errors = []
    oid = rec.get("cl_opinion_id")
    if not isinstance(oid, int):
        errors.append("cl_opinion_id must be an integer")
    if not OPINION_URL.match(str(rec.get("opinion_url") or "")):
        errors.append("opinion_url must be a CourtListener opinion link")
    decision = rec.get("listing_decision")
    if decision == "excluded":
        if rec.get("exclusion_reason") not in EXCLUSION_REASONS:
            errors.append(f"exclusion_reason must be one of {sorted(EXCLUSION_REASONS)}")
        return errors
    if decision != "listed":
        return errors + ["listing_decision must be 'listed' or 'excluded'"]

    rule = rec.get("listing_rule")
    if rule not in LISTING_RULES:
        errors.append(f"listing_rule must be one of {sorted(LISTING_RULES)}")
    elif rec.get("role") not in ROLES_FOR_RULE[rule]:
        errors.append(f"role {rec.get('role')!r} is inconsistent with listing_rule {rule}")
    topic = rec.get("topic")
    spec = topics.get(topic)
    if spec is None:
        errors.append(f"unknown topic {topic!r}")
    else:
        if spec.get("issue_types") and rec.get("issue_type") not in spec["issue_types"]:
            errors.append(f"issue_type must be one of {spec['issue_types']}")
        if spec.get("outcomes") and rec.get("outcome") not in spec["outcomes"]:
            errors.append(f"outcome must be one of {spec['outcomes']}")
    if rec.get("posture") not in POSTURES:
        errors.append(f"posture must be one of {sorted(POSTURES)}")
    if not VOTE.match(str(rec.get("vote") or "")):
        errors.append("vote must look like 3-0 or 2-1")
    if not DATE.match(str(rec.get("date_filed") or "")):
        errors.append("date_filed must be YYYY-MM-DD")
    if not isinstance(rec.get("published"), bool):
        errors.append("published must be true or false")
    words = len(str(rec.get("summary") or "").split())
    if words == 0:
        errors.append("summary is empty")
    elif words > SUMMARY_MAX_WORDS:
        errors.append(f"summary has {words} words; the limit is {SUMMARY_MAX_WORDS} words")
    for field in ("case_name", "citation_or_docket", "result_on_issue"):
        if not rec.get(field):
            errors.append(f"{field} is required")
    return errors


def verify(ws: Workspace, slug: str, topic: str, topics: dict, by: str,
           ids: set[int] | None, today: str) -> tuple[list[int], dict[int, list[str]]]:
    """Validate decided drafts and stamp the requested ones as verified."""
    drafts = _read_jsonl(_draft_path(ws, slug, topic))
    stamped, problems = [], {}
    for rec in drafts:
        if rec.get("listing_decision") is None:
            continue
        errors = validate_record(rec, topics)
        if errors:
            problems[rec["cl_opinion_id"]] = errors
            continue
        if ids is None or rec["cl_opinion_id"] in ids:
            rec.update(verified=True, verified_by=by, verified_date=today)
            stamped.append(rec["cl_opinion_id"])
    _write_jsonl(_draft_path(ws, slug, topic), drafts)
    return stamped, problems


# ---------------------------------------------------------------- second check (KTD8)

def sample_size(decided: int) -> int:
    return 0 if decided == 0 else max(1, math.ceil(SAMPLE_SHARE * decided))


def draw_sample(ws: Workspace, slug: str, seed: int) -> list[int]:
    records = load_drafts(ws, slug)
    decided = sorted(r["cl_opinion_id"] for r in records if r.get("listing_decision"))
    drawn = sorted(random.Random(seed).sample(decided, sample_size(len(decided))))
    for rec in records:
        if rec["cl_opinion_id"] in drawn:
            rec["second_check"] = "pending"
    save_drafts(ws, slug, records)
    ws.checks.mkdir(parents=True, exist_ok=True)
    lines = [f"# Second check: {slug}", "", f"Seed: {seed}. Drawn {len(drawn)} of "
             f"{len(decided)} decided records (listed and excluded).", ""]
    for rec in records:
        if rec["cl_opinion_id"] in drawn:
            lines.append(f"- [ ] {rec['cl_opinion_id']} {rec.get('case_name')} "
                         f"({rec.get('listing_decision')}) {rec.get('opinion_url')}")
    (ws.checks / f"{slug}.md").write_text("\n".join(lines) + "\n")
    return drawn


def record_check(ws: Workspace, slug: str, opinion_id: int, passed: bool, note: str,
                 by: str, today: str | None = None) -> None:
    records = load_drafts(ws, slug)
    for rec in records:
        if rec["cl_opinion_id"] == opinion_id:
            if rec.get("second_check") != "pending":
                raise ValueError(f"{opinion_id} was not drawn for the second check")
            rec.update(second_check="passed" if passed else "failed",
                       second_check_note=note, second_check_by=by,
                       second_check_date=today or date.today().isoformat())
            save_drafts(ws, slug, records)
            return
    raise KeyError(opinion_id)


def finish_check(ws: Workspace, slug: str) -> None:
    records = load_drafts(ws, slug)
    states = [r.get("second_check") for r in records if r.get("listing_decision")]
    if "pending" in states:
        raise PromotionRefused("second check still has pending records")
    if "failed" in states:
        raise PromotionRefused(
            "second check failed: re-verify every record for this justice, log the error "
            "type in DECISIONS.md, then draw a new sample")
    for rec in records:
        if rec.get("listing_decision") and rec.get("second_check") is None:
            rec["second_check"] = "not_sampled"
    save_drafts(ws, slug, records)


# ---------------------------------------------------------------- promotion

def promote(ws: Workspace, slug: str, topic: str, topics: dict) -> int:
    queue_ids = [q["cl_opinion_id"] for q in _read_jsonl(ws.queue / f"{slug}__{topic}.jsonl")]
    drafts = {r["cl_opinion_id"]: r for r in _read_jsonl(_draft_path(ws, slug, topic))}
    undecided = [i for i in queue_ids if not drafts.get(i, {}).get("listing_decision")]
    if undecided:
        raise PromotionRefused(f"undecided queued cases: {undecided}")
    for oid in queue_ids:
        rec = drafts[oid]
        errors = validate_record(rec, topics)
        if errors:
            raise PromotionRefused(f"{oid} fails validation: {errors}")
        if rec.get("verified") is not True:
            raise PromotionRefused(f"{oid} is not verified")
    states = {r.get("second_check") for r in load_drafts(ws, slug) if r.get("listing_decision")}
    if "failed" in states:
        raise PromotionRefused("a second check failed for this justice")
    if not states <= SECOND_CHECK_DONE:
        raise PromotionRefused("the second check for this justice is not complete")

    existing = [r for r in _read_jsonl(ws.case_notes)
                if not (r.get("justice_slug") == slug and r.get("topic") == topic)]
    promoted = [{k: v for k, v in drafts[i].items() if k != "candidate_rules"}
                for i in queue_ids]
    merged = sorted(existing + promoted, key=lambda r: (
        r.get("justice_slug", ""), r.get("topic", ""), _desc(r.get("date_filed", "")),
        r["cl_opinion_id"]))
    _write_jsonl(ws.case_notes, merged)

    # The manifest is how render tells "reviewed, nothing listed" from "not yet reviewed".
    reviewed = load_reviewed(ws)
    reviewed[(slug, topic)] = {
        "justice_slug": slug, "topic": topic, "queued": len(queue_ids),
        "listed": sum(1 for r in promoted if r.get("listing_decision") == "listed"),
        "excluded": sum(1 for r in promoted if r.get("listing_decision") == "excluded"),
    }
    _write_jsonl(_reviewed_path(ws), [reviewed[k] for k in sorted(reviewed)])
    return len(promoted)


def _reviewed_path(ws: Workspace) -> Path:
    return ws.case_notes.parent / "reviewed.jsonl"


def load_reviewed(ws: Workspace) -> dict[tuple[str, str], dict]:
    return {(r["justice_slug"], r["topic"]): r for r in _read_jsonl(_reviewed_path(ws))}


def _desc(value: str) -> str:
    return "".join(chr(0x10FFFF - ord(ch)) for ch in value)


# ---------------------------------------------------------------- CLI

def _start_date(raw: str, window_start: str) -> str:
    parts = (raw or "").split("-")
    padded = "-".join(parts + ["01"] * (3 - len(parts))) if raw else window_start
    return max(padded, window_start)


def main(argv: list[str] | None = None) -> int:
    from src import config, db, justices, tag

    parser = argparse.ArgumentParser(description="Review queue and promotion")
    sub = parser.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("queue")
    q.add_argument("--set", default="sd17")
    q.add_argument("--tier", type=int, default=1)
    for name in ("new", "promote"):
        p = sub.add_parser(name)
        p.add_argument("--justice", required=True)
        p.add_argument("--topic", default="search_seizure")
    v = sub.add_parser("verify")
    v.add_argument("--justice", required=True)
    v.add_argument("--topic", default="search_seizure")
    v.add_argument("--by", required=True)
    v.add_argument("--ids")
    v.add_argument("--all", action="store_true")
    s = sub.add_parser("sample")
    s.add_argument("--justice", required=True)
    s.add_argument("--seed", type=int, required=True)
    c = sub.add_parser("check")
    c.add_argument("--justice", required=True)
    c.add_argument("--id", type=int, required=True)
    c.add_argument("--by", required=True)
    c.add_argument("--note", default="")
    g = c.add_mutually_exclusive_group(required=True)
    g.add_argument("--pass", dest="passed", action="store_true")
    g.add_argument("--fail", dest="passed", action="store_false")
    f = sub.add_parser("finish-check")
    f.add_argument("--justice", required=True)
    sub.add_parser("status")
    args = parser.parse_args(argv)

    settings = config.load()
    ws = Workspace(settings.path("drafts"), settings.path("review") / "queue",
                   settings.path("case_notes"))
    topics = tag.load_keywords()
    today = date.today().isoformat()

    if args.cmd == "queue":
        conn = db.connect(settings.path("database"))
        roster = [j for j in justices.load_justices() if str(j.get("sd_ballot")).lower()
                  in ("true", "1")] if args.set == "sd17" else justices.load_justices()
        wanted = [t for t, spec in topics.items() if spec.get("tier") == args.tier]
        ws.queue.mkdir(parents=True, exist_ok=True)
        for j in roster:
            court = "cal" if j["court"] == "supreme" else "calctapp"
            start = _start_date(j.get("appellate_start_date", ""), settings.raw["window"]["start"])
            for topic in wanted:
                entries = build_queue(conn, j["slug"], topic, start, court)
                _write_jsonl(ws.queue / f"{j['slug']}__{topic}.jsonl", entries)
                print(f"{j['slug']:<24} {topic:<16} {len(entries):>4} queued")
    elif args.cmd == "new":
        print(f"added {scaffold(ws, args.justice, args.topic)} draft stubs")
    elif args.cmd == "verify":
        ids = None if args.all else {int(i) for i in (args.ids or "").split(",") if i}
        if ids is not None and not ids:
            parser.error("pass --ids or --all")
        stamped, problems = verify(ws, args.justice, args.topic, topics, args.by, ids, today)
        print(f"verified: {stamped}")
        for oid, errs in problems.items():
            print(f"  {oid}: {'; '.join(errs)}")
        return 1 if problems else 0
    elif args.cmd == "sample":
        print(f"drawn: {draw_sample(ws, args.justice, args.seed)}")
    elif args.cmd == "check":
        record_check(ws, args.justice, args.id, args.passed, args.note, args.by, today)
    elif args.cmd == "finish-check":
        finish_check(ws, args.justice)
    elif args.cmd == "promote":
        try:
            print(f"promoted {promote(ws, args.justice, args.topic, topics)} records")
        except PromotionRefused as exc:
            print(f"refused: {exc}")
            return 1
    elif args.cmd == "status":
        for path in sorted(ws.queue.glob("*.jsonl")):
            slug, topic = path.stem.split("__")
            queued = len(_read_jsonl(path))
            drafts = _read_jsonl(_draft_path(ws, slug, topic))
            decided = sum(1 for d in drafts if d.get("listing_decision"))
            verified = sum(1 for d in drafts if d.get("verified"))
            promoted = sum(1 for r in _read_jsonl(ws.case_notes)
                           if r.get("justice_slug") == slug and r.get("topic") == topic)
            print(f"{slug:<24} {topic:<16} queued {queued:>4}  decided {decided:>4}  "
                  f"verified {verified:>4}  promoted {promoted:>4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
