"""Banned-word lint for guide pages (R19, KTD11).

Whole-word, case-insensitive matching over prose the project wrote. Italic
segments (case names are rendered in italics) are skipped. Text quoted from an
opinion is linted like everything else unless it is listed in
data/lint_exceptions.yaml; every exception is logged in DECISIONS.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

BANNED = [
    "pro-police", "anti-police", "soft on crime", "tough on crime", "activist", "liberal",
    "conservative", "radical", "lenient", "rubber-stamp", "heroic", "outrageous",
]
_PATTERNS = [(term, re.compile(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", re.I))
             for term in BANNED]
_ITALIC = re.compile(r"(?<!\*)\*(?!\*)[^*\n]+\*(?!\*)")

EXCEPTIONS_FILE = Path(__file__).resolve().parents[1] / "data" / "lint_exceptions.yaml"


def load_exceptions(path: Path = EXCEPTIONS_FILE) -> list[dict]:
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text()) or []


def check_text(name: str, text: str, exceptions: list[dict]) -> list[tuple[str, int, str]]:
    allowed = [e["phrase"] for e in exceptions if e.get("file") in (name, "*")]
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        line = _ITALIC.sub(" ", line)
        for phrase in allowed:
            line = re.sub(re.escape(phrase), " ", line, flags=re.I)
        for term, pattern in _PATTERNS:
            if pattern.search(line):
                hits.append((name, lineno, term))
    return hits


def check_files(paths: list[Path], root: Path) -> list[tuple[str, int, str]]:
    exceptions = load_exceptions()
    hits = []
    for path in sorted(paths):
        hits += check_text(str(path.relative_to(root)), path.read_text(), exceptions)
    return hits
