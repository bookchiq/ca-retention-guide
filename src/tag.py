"""Topic tagging (U7): a first-pass keyword filter, not a classification.

    python -m src.tag      # (re)tag every opinion; replaces earlier rows

Rules (KTD7, KTD9):
- tagged:      any anchor term, or at least 3 distinct broader terms
- queue_match: any anchor term, or at least 1 broader term (looser, so that
               tightening anchors for precision never shrinks the reading queue)
"""

from __future__ import annotations

import logging
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

KEYWORDS = Path(__file__).resolve().parents[1] / "data" / "keywords.yaml"
TAG_BROAD_MIN = 3
QUEUE_BROAD_MIN = 1

_SECTION = re.compile(r"§+\s*")
_SPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    text = _SECTION.sub("section ", text.lower())
    return _SPACE.sub(" ", text)


@dataclass
class Hits:
    anchor_hits: int
    broad_hits: int
    core_hits: int = 0
    rule: dict | None = None
    anchor_occurrences: int = 0

    @property
    def tagged(self) -> bool:
        if self.rule:
            # A validated topic's own rule (KTD9): the topic is litigated, not just mentioned.
            return (self.anchor_hits >= self.rule.get("min_distinct_anchors", 1)
                    and self.core_hits >= self.rule.get("min_core_hits", 0)
                    and self.anchor_occurrences >= self.rule.get("min_anchor_occurrences", 0))
        return self.anchor_hits > 0 or self.broad_hits >= TAG_BROAD_MIN

    @property
    def queue_match(self) -> bool:
        return self.anchor_hits > 0 or self.broad_hits >= QUEUE_BROAD_MIN


@dataclass
class Compiled:
    pattern: re.Pattern
    # normalized term -> list of (topic, "anchor" | "broad" | "core")
    owners: dict[str, list[tuple[str, str]]]
    topics: list[str]
    rules: dict[str, dict]


def load_keywords(path: Path = KEYWORDS) -> dict:
    return yaml.safe_load(Path(path).read_text())


def compile_topics(topics: dict) -> Compiled:
    owners: dict[str, list[tuple[str, str]]] = {}
    prefixes: set[str] = set()
    for topic, spec in topics.items():
        prefixes |= {normalize(p) for p in spec.get("prefix_terms", [])}
        rule = spec.get("tag_rule") or {}
        for key, kind in (("anchors", "anchor"), ("broad", "broad")):
            for term in spec.get(key, []):
                owners.setdefault(normalize(term), []).append((topic, kind))
        for term in rule.get("core_terms", []):
            owners.setdefault(normalize(term), []).append((topic, "core"))
    ordered = sorted(owners, key=len, reverse=True)
    whole = "|".join(re.escape(t) for t in ordered if t not in prefixes)
    stems = "|".join(re.escape(t) for t in ordered if t in prefixes)
    # One shared left boundary instead of one per alternative: far fewer checks per
    # position on long opinion texts.
    body = rf"(?:{whole})(?![a-z0-9])" + (f"|(?:{stems})" if stems else "")
    rules = {t: s["tag_rule"] for t, s in topics.items() if s.get("tag_rule")}
    return Compiled(re.compile(rf"(?<![a-z0-9])(?:{body})"), owners, list(topics), rules)


def score(text: str, compiled: Compiled) -> dict[str, Hits]:
    found: dict[str, dict[str, set[str]]] = {
        t: {"anchor": set(), "broad": set()} for t in compiled.topics
    }
    core = dict.fromkeys(compiled.topics, 0)
    anchor_uses = dict.fromkeys(compiled.topics, 0)
    for match in compiled.pattern.finditer(normalize(text or "")):
        term = match.group(0)
        for topic, kind in compiled.owners.get(term, []):
            if kind == "core":
                core[topic] += 1  # occurrences, not distinct terms
            else:
                found[topic][kind].add(term)
                if kind == "anchor":
                    anchor_uses[topic] += 1
    return {
        t: Hits(anchor_hits=len(k["anchor"]), broad_hits=len(k["broad"]), core_hits=core[t],
                rule=compiled.rules.get(t), anchor_occurrences=anchor_uses[t])
        for t, k in found.items()
    }


def tag_all(conn: sqlite3.Connection, topics: dict) -> int:
    compiled = compile_topics(topics)
    count = 0
    batch = []
    # Score everything before writing, so the write lock is held only briefly and
    # other jobs (parsing, fetching) can write to the database meanwhile.
    for opinion_id, text in conn.execute("SELECT cl_opinion_id, text FROM opinions"):
        for topic, h in score(text, compiled).items():
            if h.anchor_hits or h.broad_hits:
                batch.append((opinion_id, topic, h.anchor_hits, h.broad_hits, int(h.tagged),
                              int(h.queue_match)))
        count += 1
    conn.execute("DELETE FROM topic_tags")
    conn.executemany(
        "INSERT INTO topic_tags (cl_opinion_id, topic, anchor_hits, broad_hits, tagged, "
        "queue_match) VALUES (?, ?, ?, ?, ?, ?)",
        batch,
    )
    conn.commit()
    # Topics covered by reading each opinion take their tags from the read decisions,
    # not from keyword counts (src/topic_reads.py).
    from src import topic_reads
    topic_reads.apply(conn, topics, KEYWORDS.parent / "topic_reads")
    return count


def main() -> int:
    from src import config, db

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = config.load()
    conn = db.connect(settings.path("database"))
    n = tag_all(conn, load_keywords())
    log.info("tagged %d opinions", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
