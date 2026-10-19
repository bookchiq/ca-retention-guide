"""Opinion text selection shared by the bulk loader and the API fetcher."""

from __future__ import annotations

import hashlib
import html
import re

# Preference order. FLP recommends html_with_citations; plain_text is the
# court-file extraction and is usually cleanest for California opinions.
TEXT_FIELDS = (
    "plain_text",
    "html_with_citations",
    "html",
    "html_lawbox",
    "html_columbia",
    "html_anon_2020",
    "xml_harvard",
)

_BLOCK_TAGS = re.compile(r"</?(p|div|br|h[1-6]|li|tr|blockquote|pre)\b[^>]*>", re.I)
_TAGS = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"[ \t ]+")
_BLANK_LINES = re.compile(r"\n\s*\n\s*\n+")


def html_to_text(markup: str) -> str:
    text = _BLOCK_TAGS.sub("\n", markup)
    text = _TAGS.sub("", text)
    text = html.unescape(text)
    text = _SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return _BLANK_LINES.sub("\n\n", text).strip()


def choose_text(row: dict) -> tuple[str, str | None]:
    """Return (text, field_used) from the first non-empty text field."""
    for field in TEXT_FIELDS:
        value = row.get(field)
        if value and str(value).strip():
            value = str(value)
            return (value.strip() if field == "plain_text" else html_to_text(value)), field
    return "", None


def text_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()
