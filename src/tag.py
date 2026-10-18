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

    @property
    def tagged(self) -> bool:
        return self.anchor_hits > 0 or self.broad_hits >= TAG_BROAD_MIN

    @property
    def queue_match(self) -> bool:
        return self.anchor_hits > 0 or self.broad_hits >= QUEUE_BROAD_MIN


@dataclass
class Compiled:
    pattern: re.Pattern
    # normalized term -> list of (topic, "anchor" | "broad")
    owners: dict[str, list[tuple[str, str]]]
    topics: list[str]


def load_keywords(path: Path = KEYWORDS) -> dict:
    return yaml.safe_load(Path(path).read_text())


def compile_topics(topics: dict) -> Compiled:
    owners: dict[str, list[tuple[str, str]]] = {}
    prefixes: set[str] = set()
    for topic, spec in topics.items():
        prefixes |= {normalize(p) for p in spec.get("prefix_terms", [])}
        for key, kind in (("anchors", "anchor"), ("broad", "broad")):
            for term in spec.get(key, []):
                owners.setdefault(normalize(term), []).append((topic, kind))
    parts = []
    for term in sorted(owners, key=len, reverse=True):
        tail = "" if term in prefixes else r"(?![a-z0-9])"
        parts.append(r"(?<![a-z0-9])" + re.escape(term) + tail)
    return Compiled(re.compile("|".join(parts)), owners, list(topics))


def score(text: str, compiled: Compiled) -> dict[str, Hits]:
    found: dict[str, dict[str, set[str]]] = {
        t: {"anchor": set(), "broad": set()} for t in compiled.topics
    }
    for match in compiled.pattern.finditer(normalize(text or "")):
        term = match.group(0)
        for topic, kind in compiled.owners.get(term, []):
            found[topic][kind].add(term)
    return {
        t: Hits(anchor_hits=len(k["anchor"]), broad_hits=len(k["broad"]))
        for t, k in found.items()
    }


def tag_all(conn: sqlite3.Connection, topics: dict) -> int:
    compiled = compile_topics(topics)
    conn.execute("DELETE FROM topic_tags")
    count = 0
    cursor = conn.execute("SELECT cl_opinion_id, text FROM opinions")
    batch = []
    for opinion_id, text in cursor.fetchall():
        for topic, h in score(text, compiled).items():
            if h.anchor_hits or h.broad_hits:
                batch.append((opinion_id, topic, h.anchor_hits, h.broad_hits, int(h.tagged),
                              int(h.queue_match)))
        count += 1
    conn.executemany(
        "INSERT INTO topic_tags (cl_opinion_id, topic, anchor_hits, broad_hits, tagged, "
        "queue_match) VALUES (?, ?, ?, ?, ?, ?)",
        batch,
    )
    conn.commit()
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
