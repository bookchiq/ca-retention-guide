"""Parse opinion text into court, publication, disposition, author, panel and
separate opinions (R7, SPEC §7.3), resolving names with src.resolve (R8).

Patterns were drafted from real opinions in tests/fixtures/opinions/. Anything the
parser cannot place is recorded, never guessed:

- parse_status on every opinion row: ok | unresolved | no_signature |
  per_curiam_no_panel | no_district | no_cluster | no_text
- unresolved and ambiguous signatures go to data/review/unresolved.csv
- caption/docket and publication disagreements go to data/review/parse_log.csv

CLI: python -m src.parse [--limit N] [--only-unparsed]
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from rapidfuzz import fuzz

from src import config, db
from src.resolve import DIVISION_WORDS, ORDINAL_DISTRICTS, Resolver, name_key

# Docket prefix -> (district, division). SPEC §7.3.1.
PREFIXES = {
    "A": ("1", None), "B": ("2", None), "C": ("3", None), "D": ("4", "One"),
    "E": ("4", "Two"), "G": ("4", "Three"), "F": ("5", None), "H": ("6", None),
}

# --- signature tokens -------------------------------------------------------------

_WORD = r"(?!(?i:acting)\b)[A-ZÀ-Þ][A-Za-zÀ-ÿ'\-]*"
# Initials distinguish same-surname justices: "M. KIM, J." and "KIM (D.), J.".
_NAME = rf"(?:[A-Z]\. )?{_WORD}(?: {_WORD}){{0,3}}(?: \([A-Z]\.\))?"
# Final period sometimes missing ("PETROU, J"); comma sometimes missing ("DE SANTOS J.").
_TITLE = (
    r"(?:(?:(?i:acting),?\s+)?(?:P\.\s*J|C\.\s*J)\.?|A\.\s*P\.\s*J\.?|J\.?)(?![A-Za-z])"
)
_STAR = r"(?:\s?(?P<star>[*\u2020]+))?"  # assigned-judge footnote marker: * or dagger
SIG_RE = re.compile(rf"(?P<name>{_NAME})(?:\s*,\s*|\s+)(?P<title>{_TITLE}){_STAR}")
_NAME_ONLY = re.compile(rf"(?P<name>{_NAME}){_STAR}")
_TITLE_ONLY = re.compile(rf",?\s*(?P<title>{_TITLE}){_STAR}")
_MARKER = re.compile(
    r"(?:WE|We|I)\s+(?:CONCUR|Concur|concur)(?i:\s+in\s+the\s+(?:result|judgment))?\s*[:.;]?"
)
_THE_COURT = re.compile(r"THE COURT\s*(?P<star>\*+)?\s*[:.]?\s*(?P<star2>\*+)?")
_NOISE = re.compile(
    r"\d+\.?|NOT TO BE PUBLISHED.*|CERTIFIED FOR .*PUBLICATION\*?|-?o+O+o+-?", re.I
)

_TITLES = {
    "J.": "J.", "P.J.": "P. J.", "C.J.": "C. J.",
    "ACTINGP.J.": "Acting P. J.", "ACTINGC.J.": "Acting C. J.", "A.P.J.": "Acting P. J.",
}


def norm_title(raw: str) -> str:
    compact = re.sub(r"[\s,]+", "", raw).upper()
    return _TITLES[compact if compact.endswith(".") else compact + "."]


def make_sig(name: str, title: str, stars: str | None, line: int) -> Sig:
    paren = re.fullmatch(r"(.+?) \(([A-Z])\.\)", name)
    surname = f"{paren.group(2)}. {paren.group(1)}" if paren else name
    return Sig(surname, norm_title(title), stars or "", line)


@dataclass
class Sig:
    surname: str
    title: str
    stars: str = ""
    line: int = 0

    @property
    def raw(self) -> str:
        return f"{self.surname}, {self.title}{self.stars}"


def clean_line(line: str) -> str:
    line = re.sub(r"_+", " ", line)
    line = re.sub(r"/s/|\\s\\", " ", line, flags=re.I)
    return line.strip().strip(",").strip()


def sig_line(text: str, line: int = 0) -> list[Sig] | None:
    """Signatures when the whole line is one or more signature tokens, else None."""
    if re.search(r"\b(?:opinion|dissent\w*|concurr\w*)\b", text, re.I):
        return None  # "DISSENTING OPINION OF BANKE, J." is a heading
    matches = list(SIG_RE.finditer(text))
    if not matches or SIG_RE.sub("", text).strip(" ,;\t"):
        return None
    return [make_sig(m.group("name"), m.group("title"), m.group("star"), line) for m in matches]


@dataclass
class Token:
    kind: str  # sig | marker | court | other
    start: int
    end: int
    text: str
    sigs: list[Sig] = field(default_factory=list)


def tokenize(lines: list[str]) -> list[Token]:
    """Non-blank, non-noise lines as tokens. Name and title split over two lines
    (either order) are joined into one signature token."""
    cleaned = [clean_line(x) for x in lines]
    keep = [i for i, c in enumerate(cleaned) if c and not _NOISE.fullmatch(c)]
    tokens: list[Token] = []
    k = 0
    while k < len(keep):
        i = keep[k]
        c = cleaned[i]
        nxt = keep[k + 1] if k + 1 < len(keep) and keep[k + 1] - i <= 8 else None
        sigs = sig_line(c, i)
        if sigs:
            tokens.append(Token("sig", i, i, c, sigs))
        elif _MARKER.fullmatch(c):
            tokens.append(Token("marker", i, i, c))
        elif _THE_COURT.fullmatch(c):
            tokens.append(Token("court", i, i, c))
        elif nxt is not None and (pair := _split_sig(c, cleaned[nxt], i)):
            tokens.append(Token("sig", i, nxt, f"{c} {cleaned[nxt]}", [pair]))
            k += 1
        else:
            tokens.append(Token("other", i, i, c))
        k += 1
    return tokens


def _split_sig(first: str, second: str, line: int) -> Sig | None:
    for name_part, title_part in ((first, second), (second, first)):
        n = _NAME_ONLY.fullmatch(name_part)
        t = _TITLE_ONLY.fullmatch(title_part)
        # A bare name line must be in capitals (McKINSTER allowed), not prose.
        if n and t and sum(c.islower() for c in n.group("name")) <= 2:
            stars = (n.group("star") or "") + (t.group("star") or "")
            return make_sig(n.group("name"), t.group("title"), stars, line)
    return None


# --- result types -----------------------------------------------------------------


@dataclass
class Seat:
    raw: str
    surname: str
    title: str
    role: str  # author | joined
    assigned: bool = False
    assignment_note: str | None = None
    slug: str | None = None
    resolution: str | None = None
    candidates: tuple[str, ...] = ()
    line: int = 0

    @property
    def queue(self) -> bool:
        return self.resolution in ("no_match", "ambiguous", "assigned_unknown")


@dataclass
class SeparateOpinion:
    type: str  # dissent | concurrence
    partial: bool
    author_raw: str | None
    surname: str | None = None
    title: str | None = None
    stars: str = ""
    slug: str | None = None
    line: int = 0


@dataclass
class ParseResult:
    district: str | None = None
    division: str | None = None
    published: bool | None = None
    partial_publication: bool = False
    disposition_text: str | None = None
    disposition_class: str | None = None
    docket_number_text: str | None = None
    author_raw: str | None = None
    author_slug: str | None = None
    per_curiam: bool = False
    has_dissent: bool = False
    has_concurrence: bool = False
    parse_status: str = "ok"
    seats: list[Seat] = field(default_factory=list)
    separate_opinions: list[SeparateOpinion] = field(default_factory=list)
    notes: list[tuple[str, str]] = field(default_factory=list)

    @property
    def unresolved(self) -> list[Seat]:
        return [s for s in self.seats if s.queue]


# --- caption, docket, publication -------------------------------------------------

_DISTRICT_RE = re.compile(r"\b(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH)\s+APPELLATE\s+DISTRICT", re.I)
_DIVISION_RE = re.compile(r"\bDIVISION\s+(ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT)\b", re.I)


def caption(lines: list[str]) -> tuple[str | None, str | None]:
    head = lines[:120]
    for i, line in enumerate(head):
        m = _DISTRICT_RE.search(line)
        if m:
            district = ORDINAL_DISTRICTS[m.group(1).upper()]
            for later in head[i : i + 6]:
                d = _DIVISION_RE.search(later)
                if d:
                    return district, DIVISION_WORDS[d.group(1).upper()]
            return district, None
    return None, None


def caption_dockets(lines: list[str], cluster_docket: str | None) -> list[str]:
    prefix = (cluster_docket or "?")[0]
    if not prefix.isalpha():
        return []
    found: list[str] = []
    for width in (6, 5):
        pattern = re.compile(rf"\b{re.escape(prefix)}\d{{{width}}}\b")
        first = None
        for i, line in enumerate(lines[:80]):
            if first is not None and (
                i > first + 12 or re.match(r"\s*(?:APPEALS? from|ORIGINAL PROCEEDING)", line, re.I)
            ):
                break  # consolidated numbers sit in the caption block
            if re.search(r"Super\.|Ct\.\s*No|Case No", line):
                continue
            for m in pattern.findall(line):
                first = i if first is None else first
                if m not in found:
                    found.append(m)
        if found:
            break
    return found


def docket_keys(cluster_docket: str | None, docket_number_text: str | None) -> set[str]:
    """Base docket numbers an opinion belongs to (suffixes like M/N/A dropped)."""
    text = f"{cluster_docket or ''} {docket_number_text or ''}"
    return set(re.findall(r"\b[A-HJS]\d{5,6}", text))


def publication(lines: list[str]) -> tuple[bool | None, bool]:
    stripped = [x.strip() for x in lines]
    if any(re.match(r"CERTIFIED FOR PARTIAL PUBLICATION", x) for x in stripped):
        return True, True
    if any(re.match(r"CERTIFIED FOR PUBLICATION", x) or re.search(r"Certified for Pub", x)
           for x in stripped):
        return True, False
    if any(re.match(r"NOT TO BE PUBLISHED", x, re.I) for x in stripped):
        return False, False
    return None, False


# --- disposition ------------------------------------------------------------------

_DISPO_HEAD = re.compile(
    r"(?:[IVX]+\.?\s*)?(?:DISPOSITION|Disposition|CONCLUSION(?: AND DISPOSITION)?|Conclusion)"
)
_DISPO_VERB = re.compile(
    r"\b(affirm|affirmed|reverse|reversed|vacated?|dismissed|remanded|granted|denied)\b", re.I
)


def disposition(lines: list[str], end: int) -> str | None:
    body = lines[:end]
    heads = [i for i, x in enumerate(body) if _DISPO_HEAD.fullmatch(x.strip())]
    if heads:
        out: list[str] = []
        blanks = 0
        for x in body[heads[-1] + 1 :]:
            t = x.strip()
            if not t:
                blanks += 1
                if out and blanks >= 2:
                    break
                continue
            blanks = 0
            if _NOISE.fullmatch(clean_line(t)) or sig_line(clean_line(t)):
                if out:
                    break
                continue
            out.append(t)
        text = re.sub(r"\s+", " ", " ".join(out)).strip()
        if text:
            return text[:1000]
    tail = re.sub(r"\s+", " ", " ".join(body[-60:]))
    sentences = [s for s in re.split(r"(?<=[.])\s+", tail) if _DISPO_VERB.search(s)]
    return " ".join(sentences[-3:])[:1000] or None


def classify_disposition(text: str | None) -> str:
    if not text:
        return "other"
    s = re.sub(r"\s+", " ", text.lower())
    sentences = [
        x for x in re.split(r"(?<=[.;])\s+", s)
        if not re.search(r"\bopinion\b[^.]*\bvacated\b|rehearing|\bcosts?\b|remittitur|publish", x)
    ]
    s = " ".join(sentences)
    aff = re.search(r"\baffirm(?:ed|s)?\b", s)
    rev = re.search(r"\brevers(?:e|ed|es)\b", s)
    vac = re.search(r"\bvacated?\b", s)
    if re.search(r"\b(?:petition|writ)\b[^.]*\b(?:is|are)\s+granted\b|\blet\s+a\b[^.]*\bwrit\b", s):
        return "writ_granted"
    if not (aff or rev) and re.search(
        r"\b(?:petitions?|writs?)\b[^.]*\b(?:is|are)\s+(?:both\s+)?denied\b", s
    ):
        return "writ_denied"
    if re.search(r"\b(?:affirmed|reversed) in part\b", s):
        return "reversed_in_part"
    if aff and re.search(r"\bas (?:so )?modified\b|\b(?:is|are) (?:hereby )?modified\b", s):
        return "affirmed_as_modified"
    if aff and (rev or vac or re.search(r"\bin all other respects\b|\botherwise affirmed\b", s)):
        return "reversed_in_part"
    if rev:
        return "reversed"
    if vac:
        return "vacated"
    if re.search(r"\b(?:appeals?|petitions?)\s+(?:is|are)\s+dismissed\b|\bdismiss the appeal\b", s):
        return "dismissed"
    if aff:
        return "affirmed"
    return "other"


# --- footnotes --------------------------------------------------------------------


def footnote(lines: list[str], stars: str, after: int) -> str | None:
    """Text of the footnote marked with exactly `stars`, searching forward from
    `after` first and then from the top."""
    pattern = re.compile(rf"\s*{re.escape(stars)}(?![*\u2020])\s*(.*)")
    for start, stop in ((after + 1, len(lines)), (0, after + 1)):
        for i in range(start, stop):
            m = pattern.fullmatch(lines[i])
            if not m or m.group(1).startswith(("*", "\u2020")):
                continue
            parts = [m.group(1).strip()] if m.group(1).strip() else []
            j = i + 1
            while j < len(lines) and len(parts) < 6:
                joined = " ".join(parts)
                if len(joined) > 15 and joined.endswith("."):
                    break
                t = lines[j].strip()
                j += 1
                if not t:
                    continue
                if re.fullmatch(r"\d+\.?", t) or t.startswith("*"):
                    break
                parts.append(t)
            text = re.sub(r"\s+", " ", " ".join(parts)).strip()
            if text:
                return text
    return None


# --- separate opinions (Court of Appeal) ------------------------------------------

_KIND = (
    r"concurring\s+in\s+part\s+and\s+dissenting\s+in\s+part|concurring\s+and\s+dissenting"
    r"|concurring\s+in\s+the\s+(?:result|judgment)|dissenting|concurring"
)
_HEAD_KIND = re.compile(rf"[\s,.:—–-]*\b(?P<kind>{_KIND})\s*[.:]?\s*$", re.I)
_PRO_TEM = re.compile(r",?\s*pro\s+tem\.?\s*$", re.I)


def heading_signers(text: str) -> tuple[list[Sig], str | None] | None:
    """Signers and kind of a separate-opinion heading such as "ELIA, J., Dissenting",
    "STRATTON, J., and WILEY, J., Concurring." or "TANGEMAN, J.:" (kind None)."""
    m = _HEAD_KIND.search(text)
    if m:
        prefix, kind = text[: m.start()], re.sub(r"\s+", " ", m.group("kind").lower())
    elif text.rstrip().endswith(":"):
        prefix, kind = text.rstrip()[:-1], None
    else:
        return None
    prefix = _PRO_TEM.sub("", prefix)
    sigs = sig_line(re.sub(r",?\s+and\s+", "  ", prefix))
    if not sigs or (kind is None and len(sigs) != 1):
        return None
    return sigs, kind

_HEAD_GENERIC = re.compile(
    r"(?P<kind>CONCURRING AND DISSENTING|DISSENTING|CONCURRING)(?: OPINION)?"
    r"(?:\s+(?:of|by)\s+.*)?\.?",
    re.I,
)
_RESPECTFULLY = re.compile(r"\bI (?:respectfully )?dissent\b")
# "POLLAK, P.J. — I concur in the disposition ..." / "SMITH, J. -- I respectfully dissent."
_DASH_LEAD = re.compile(
    r"^\s*(?P<sig>[^—–]+?,\s*(?:Acting\s+)?(?:P\.\s*J\.|J\.))\s*(?:—|–|--)\s*(?P<rest>I\b.*)$"
)
_KINDS = {
    "concurring in part and dissenting in part": ("dissent", True),
    "concurring and dissenting": ("dissent", True),
    "concurring in the result": ("concurrence", False),
    "concurring in the judgment": ("concurrence", False),
    "dissenting": ("dissent", False),
    "concurring": ("concurrence", False),
}


def separate_opinions(tokens: list[Token]) -> list[SeparateOpinion]:
    out: list[SeparateOpinion] = []
    current: SeparateOpinion | None = None
    pending_kind_line = False  # "TANGEMAN, J.:" waiting for "I respectfully dissent"
    for tok in tokens:
        if tok.kind == "sig":
            if current is not None and len(tok.sigs) == 1:
                sig = tok.sigs[0]
                if current.surname is None or name_key(current.surname) == name_key(sig.surname):
                    current.surname, current.title, current.author_raw = (
                        sig.surname, sig.title, sig.raw,
                    )
                    current.stars = sig.stars
                    current.line = sig.line
                current = None
                pending_kind_line = False
            continue
        if tok.kind != "other":
            continue
        lead = _DASH_LEAD.match(tok.text)
        if lead and (lead_sigs := sig_line(lead.group("sig"))) and len(lead_sigs) == 1:
            rest = lead.group("rest")[:120].lower()
            if "concur" in rest and "dissent" in rest:
                typ, partial = "dissent", True
            elif "dissent" in rest:
                typ, partial = "dissent", False
            else:
                typ, partial = "concurrence", False
            sig = lead_sigs[0]
            current = SeparateOpinion(typ, partial, sig.raw, sig.surname, sig.title, sig.stars,
                                      line=tok.start)
            out.append(current)
            pending_kind_line = False
            continue
        named = heading_signers(tok.text)
        if named:
            signers, kind = named
            typ, partial = _KINDS.get(kind or "", ("dissent", False))
            for sig in signers:
                current = SeparateOpinion(typ, partial, sig.raw, sig.surname, sig.title,
                                          sig.stars, line=tok.start)
                out.append(current)
            pending_kind_line = kind is None
            continue
        if pending_kind_line and current is not None:
            if re.search(r"\bI concur\b", tok.text) and not _RESPECTFULLY.search(tok.text):
                current.type = "concurrence"
            pending_kind_line = False
            continue
        if current is not None:
            continue
        generic = _HEAD_GENERIC.fullmatch(tok.text)
        if generic:
            typ, partial = _KINDS[generic.group("kind").lower()]
            current = SeparateOpinion(typ, partial, None, line=tok.start)
            out.append(current)
        elif _RESPECTFULLY.search(tok.text):
            current = SeparateOpinion("dissent", False, None, line=tok.start)
            out.append(current)
    return out


# --- Supreme Court statement ------------------------------------------------------

_SC_AUTHOR = re.compile(
    r"(?P<who>(?:Chief\s+)?Justice\s+[^,]+?)\s+authored\s+the\s+(?:majority\s+)?opinion\s+of\s+"
    r"the\s+Court,?\s+in\s+which\s+(?P<joined>.+?)\s+concurred\."
)
_SC_SEPARATE = re.compile(
    r"(?P<who>(?:Chief\s+)?Justice\s+\S+?)\s+filed\s+(?:an?\s+"
    r"(?P<kind>concurring and dissenting|dissenting|concurring)\s+opinion"
    r"|an\s+opinion\s+(?P<kind2>concurring\s+in\s+the\s+(?:judgment|result)"
    r"|concurring and dissenting|dissenting))"
    r"(?:,?\s+in\s+which\s+(?P<joined>[^.]+?)\s+concurred)?"
)


def _sc_person(token: str, default_chief: bool = False) -> Sig | None:
    token = token.strip()
    chief = default_chief
    m = re.match(r"(?:(Chief)\s+)?Justices?\s+(.*)", token)
    if m:
        chief = bool(m.group(1))
        token = m.group(2)
    m = re.fullmatch(r"([A-ZÀ-Þ][\w'’\-]+(?: [A-Z][\w'\-]+)?)(\**)", token)
    if not m:
        return None
    return Sig(m.group(1), "C. J." if chief else "J.", m.group(2))


def supreme_statement(text: str) -> tuple[Sig, list[Sig], list[tuple[Sig, str]]] | None:
    flat = re.sub(r"\s+", " ", text[:8000])
    m = _SC_AUTHOR.search(flat)
    if not m:
        return None
    author = _sc_person(m.group("who"))
    if author is None:
        return None
    joined = []
    for part in re.split(r",\s*and\s+|,\s*|\s+and\s+", m.group("joined")):
        p = _sc_person(part)
        if p:
            joined.append(p)
    separates = []
    seated = {author.surname} | {j.surname for j in joined}
    for s in _SC_SEPARATE.finditer(flat):
        p = _sc_person(s.group("who"))
        if not p:
            continue
        kind = s.group("kind") or re.sub(r"\s+", " ", s.group("kind2"))
        separates.append((p, kind))
        # Separate-opinion authors and their joiners sat on the case too.
        others = [p] + [q for part in re.split(r",\s*and\s+|,\s*|\s+and\s+",
                                               s.group("joined") or "")
                        if (q := _sc_person(part))]
        for q in others:
            if q.surname not in seated:
                joined.append(q)
                seated.add(q.surname)
    return author, joined, separates


def _sc_raw(sig: Sig) -> str:
    return ("Chief Justice " if sig.title == "C. J." else "Justice ") + sig.surname + sig.stars


# --- main entry -------------------------------------------------------------------


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    # \uf02a (Symbol font) and \u2217 (asterisk operator) mark assigned judges too.
    pairs = (("\u2019", "'"), ("\u2018", "'"), ("\u00a0", " "), ("\r", ""),
             ("\uf02a", "*"), ("\u2217", "*"))
    for a, b in pairs:
        text = text.replace(a, b)
    return text


def _truncate(lines: list[str], court: str) -> list[str]:
    for i, line in enumerate(lines):
        t = line.strip()
        if court == "cal" and t.startswith("See next page for addresses"):
            return lines[:i]
        if court != "cal" and re.fullmatch(r"IN THE SUPREME COURT OF CALIFORNIA", t):
            return lines[:i]
    return lines


_RESOLVER: Resolver | None = None


def default_resolver() -> Resolver:
    global _RESOLVER
    if _RESOLVER is None:
        _RESOLVER = Resolver()
    return _RESOLVER


def parse_opinion(
    text: str | None,
    court: str,
    docket_number: str | None,
    date_filed: str | date,
    precedential_status: str | None = None,
    resolver: Resolver | None = None,
) -> ParseResult:
    r = ParseResult()
    if not text or not text.strip():
        r.parse_status = "no_text"
        return r
    resolver = resolver or default_resolver()
    on = date_filed if isinstance(date_filed, date) else date.fromisoformat(date_filed[:10])
    lines = _truncate(normalize(text).splitlines(), court)
    supreme = court == "cal"

    # Court, district, division.
    if not supreme:
        prefix = (docket_number or " ")[0].upper()
        p_district, p_division = PREFIXES.get(prefix, (None, None))
        c_district, c_division = caption(lines)
        r.district = p_district or c_district
        r.division = c_division or p_division
        if p_district and c_district and (p_district, p_division) != (c_district, c_division) and (
            p_district != c_district or (p_division and c_division)
        ):
            r.notes.append((
                "prefix_caption_mismatch",
                f"{prefix} prefix {p_district}/{p_division or '-'}, "
                f"caption {c_district}/{c_division or '-'}",
            ))
    dockets = caption_dockets(lines, docket_number)
    r.docket_number_text = ", ".join(dockets) or None

    # Publication.
    text_pub, partial = publication(lines)
    if supreme:
        text_pub, partial = True, False
    cl_pub = {"Published": True, "Unpublished": False}.get(precedential_status or "")
    if text_pub is not None and cl_pub is not None and text_pub != cl_pub:
        word = "published" if text_pub else "unpublished"
        r.notes.append((
            "publication_status_mismatch", f"text {word}, CourtListener {precedential_status}",
        ))
    r.published = text_pub if text_pub is not None else cl_pub
    r.partial_publication = partial

    tokens = tokenize(lines)
    sc = supreme_statement("\n".join(lines)) if supreme else None
    author: Sig | None = None
    joiners: list[Sig] = []
    block_end = None
    seps: list[SeparateOpinion] = []

    if sc:
        author, joiners, sc_seps = sc
        header_line = next((i for i, x in enumerate(lines) if "authored the" in x), 0)
        for s in [author, *joiners]:
            s.line = header_line
        for sig, kind in sc_seps:
            typ, part = _KINDS[kind]
            seps.append(SeparateOpinion(typ, part, _sc_raw(sig), sig.surname, sig.title,
                                        sig.stars, line=header_line))
    block = _majority_block(tokens)
    if block:
        a_k, k, end_k = block
        if not sc:
            author = tokens[a_k].sigs[-1]
            joiners = [s for t in tokens[k + 1 : end_k + 1] for s in t.sigs]
        block_end = end_k
    if not sc and block_end is not None:
        seps = separate_opinions(tokens[block_end + 1 :])

    def raw_of(sig: Sig) -> str:
        return _sc_raw(sig) if sc else sig.raw

    seat_list: list[Seat] = []
    if author is not None:
        seat_list.append(_seat(author, "author", raw_of(author)))
        seat_list += [_seat(s, "joined", raw_of(s)) for s in joiners]
    else:
        court_tok = next((t for t in tokens if t.kind == "court"), None)
        if court_tok is not None:
            r.per_curiam = True
            m_court = _THE_COURT.fullmatch(court_tok.text)
            stars = m_court.group("star") or m_court.group("star2") or ""
            note = footnote(lines, stars, court_tok.start) if stars else None
            if note and re.search(r"\bBefore\b|participated", note):
                listed = re.sub(r"^\s*Before,?\s+", "", note)
                for m in SIG_RE.finditer(listed):
                    sig = make_sig(m.group("name"), m.group("title"), "", court_tok.start)
                    seat_list.append(_seat(sig, "joined"))
            if not seat_list:
                # Some per curiam opinions list the panel on the last signature line(s).
                after = [t for t in tokens if t.start > court_tok.start]
                run_sigs: list[Sig] = []
                current_run: list[Sig] = []
                for t in after:
                    current_run = current_run + t.sigs if t.kind == "sig" else []
                    if len(current_run) >= 2:
                        run_sigs = current_run
                if len(run_sigs) >= 2:
                    seat_list += [_seat(sig, "joined") for sig in run_sigs]
    for sep in seps:
        if sep.surname and not any(name_key(s.surname) == name_key(sep.surname) for s in seat_list):
            sig = Sig(sep.surname, sep.title or "J.", sep.stars, sep.line)
            seat_list.append(_seat(sig, "joined", sep.author_raw))

    # Assignment footnotes and resolution.
    seen: set[tuple[str, str]] = set()
    for seat in seat_list:
        if (seat.raw, seat.role) in seen:
            continue
        seen.add((seat.raw, seat.role))
        stars = re.search(r"[*\u2020]+$", seat.raw)
        if stars:
            seat.assigned = True
            seat.assignment_note = footnote(lines, stars.group(0), seat.line)
        res = resolver.resolve(
            seat.surname, seat.title, "supreme" if supreme else "appeal",
            r.district or "", r.division or "", on, seat.assigned, seat.assignment_note,
        )
        seat.slug, seat.resolution, seat.candidates = res.slug, res.status, res.candidates
        r.seats.append(seat)

    by_key = {name_key(s.surname): s for s in r.seats}
    for sep in seps:
        match = by_key.get(name_key(sep.surname)) if sep.surname else None
        sep.slug = match.slug if match else None
    r.separate_opinions = seps
    r.has_dissent = any(s.type == "dissent" for s in seps)
    r.has_concurrence = any(s.type == "concurrence" for s in seps)

    if author is not None:
        a = r.seats[0]
        r.author_raw, r.author_slug = a.raw, a.slug

    # Disposition: text before the majority signature (or the whole opinion).
    end_line = len(lines)
    if block:
        end_line = tokens[block[0]].start
    r.disposition_text = disposition(lines, end_line)
    r.disposition_class = classify_disposition(r.disposition_text)

    if not supreme and r.district is None:
        r.parse_status = "no_district"
    elif author is None and not r.per_curiam:
        r.parse_status = "no_signature"
    elif r.per_curiam and not r.seats:
        r.parse_status = "per_curiam_no_panel"
    elif r.unresolved or any(s.author_raw is None for s in seps):
        r.parse_status = "unresolved"
    else:
        r.parse_status = "ok"
    return r


def _seat(sig: Sig, role: str, raw: str | None = None) -> Seat:
    return Seat(raw or sig.raw, sig.surname, sig.title, role, line=sig.line)


def _majority_block(tokens: list[Token]) -> tuple[int, int, int] | None:
    """(author index, marker index, last joiner index) for the first "We concur" /
    "I concur" that follows a signature."""
    for k, tok in enumerate(tokens):
        if tok.kind != "marker":
            continue
        # A page-bottom footnote ("7 People v. Marsden ...") may sit between the
        # author's signature and "WE CONCUR".
        j = k - 1
        while j >= 0 and k - j <= 4 and tokens[j].kind == "other" and tokens[j].text[:1].isdigit():
            j -= 1
        if j >= 0 and tokens[j].kind == "sig":
            end = k
            while end + 1 < len(tokens) and tokens[end + 1].kind == "sig":
                end += 1
            return j, k, end
    return None


# --- duplicates -------------------------------------------------------------------

_TRANSFER = re.compile(
    r"transfer(?:red)?\s+from\s+the\s+Supreme\s+Court|\bon\s+transfer\b|following\s+transfer"
    r"|transferred\s+(?:the|this)\s+(?:matter|case|cause)\s+(?:back\s+)?to\s+(?:us|this\s+court)"
    r"|remanded\s+(?:the|this)\s+(?:matter|case)\s+to\s+(?:us|this\s+court)",
    re.I,
)
SIMILARITY = 90


@dataclass
class DedupeItem:
    opinion_id: int
    date_filed: str
    disposition_class: str | None
    text: str


def _norm_for_similarity(text: str) -> str:
    return re.sub(r"\s+", " ", normalize(text)).lower()


def find_superseded(items: list[DedupeItem]) -> dict[int, int]:
    """Map each superseded opinion id to the id of the latest version of the same
    decision. Same decision = near-identical text and the same disposition class,
    unless the later one follows a Supreme Court transfer and the earlier does not."""
    ordered = sorted(items, key=lambda x: (x.date_filed, x.opinion_id))
    decisions: list[list[DedupeItem]] = []
    for item in ordered:
        home = None
        for members in decisions:
            latest = members[-1]
            if latest.disposition_class != item.disposition_class:
                continue
            if _TRANSFER.search(item.text[:3000]) and not _TRANSFER.search(latest.text[:3000]):
                continue
            score = fuzz.token_set_ratio(
                _norm_for_similarity(latest.text), _norm_for_similarity(item.text)
            )
            if score >= SIMILARITY:
                home = members
                break
        if home is None:
            decisions.append([item])
        else:
            home.append(item)
    out = {}
    for members in decisions:
        for m in members[:-1]:
            out[m.opinion_id] = members[-1].opinion_id
    return out


# --- database CLI -----------------------------------------------------------------

QUEUE_FIELDS = [
    "cl_opinion_id", "seat_raw", "role", "reason", "candidates", "court", "district",
    "division", "date_filed", "docket_number", "assignment_note",
]
LOG_FIELDS = ["cl_opinion_id", "kind", "detail"]


@dataclass
class Stats:
    parsed: int = 0
    status: Counter = field(default_factory=Counter)
    by_district: dict = field(default_factory=lambda: defaultdict(Counter))
    unresolved_shapes: Counter = field(default_factory=Counter)
    superseded: int = 0


def _merge_csv(path: Path, fields: list[str], replaced_ids: set[int], rows: list[dict]) -> None:
    kept: list[dict] = []
    if path.exists():
        with open(path, newline="") as fh:
            kept = [r for r in csv.DictReader(fh) if int(r["cl_opinion_id"]) not in replaced_ids]
    allrows = kept + rows
    allrows.sort(key=lambda r: (int(r["cl_opinion_id"]), *(str(r.get(f, "")) for f in fields[1:3])))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(allrows)


def _write(conn: sqlite3.Connection, oid: int, r: ParseResult) -> None:
    def b(v):
        return None if v is None else int(bool(v))

    conn.execute(
        "UPDATE opinions SET district=?, division=?, published=?, partial_publication=?, "
        "disposition_text=?, disposition_class=?, docket_number_text=?, author_slug=?, "
        "author_raw=?, per_curiam=?, has_dissent=?, has_concurrence=?, parse_status=? "
        "WHERE cl_opinion_id=?",
        (r.district, r.division, b(r.published), b(r.partial_publication), r.disposition_text,
         r.disposition_class, r.docket_number_text, r.author_slug, r.author_raw, b(r.per_curiam),
         b(r.has_dissent), b(r.has_concurrence), r.parse_status, oid),
    )
    conn.execute("DELETE FROM panel_seats WHERE cl_opinion_id = ?", (oid,))
    conn.execute("DELETE FROM separate_opinions WHERE cl_opinion_id = ?", (oid,))
    for s in r.seats:
        conn.execute(
            "INSERT OR IGNORE INTO panel_seats (cl_opinion_id, seat_raw, slug, role, title, "
            "assigned, assignment_note) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (oid, s.raw, s.slug, s.role, s.title, int(s.assigned), s.assignment_note),
        )
    for s in r.separate_opinions:
        conn.execute(
            "INSERT INTO separate_opinions (cl_opinion_id, type, partial, author_slug, author_raw) "
            "VALUES (?, ?, ?, ?, ?)",
            (oid, s.type, int(s.partial), s.slug, s.author_raw),
        )


def _district_key(court: str | None, district: str | None) -> str:
    return "S" if court == "cal" else (district or "?")


def parse_database(
    conn: sqlite3.Connection,
    limit: int | None = None,
    only_unparsed: bool = False,
    unresolved_path: Path | None = None,
    log_path: Path | None = None,
    resolver: Resolver | None = None,
    batch: int = 200,
) -> Stats:
    stats = Stats()
    where = "WHERE o.parse_status IS NULL" if only_unparsed else ""
    sql = f"SELECT o.cl_opinion_id FROM opinions o {where} ORDER BY o.cl_opinion_id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    ids = [row[0] for row in conn.execute(sql)]
    queue_rows: list[dict] = []
    log_rows: list[dict] = []
    for start in range(0, len(ids), batch):
        chunk = ids[start : start + batch]
        marks = ",".join("?" * len(chunk))
        rows = conn.execute(
            "SELECT o.cl_opinion_id, o.text, c.court, c.docket_number, c.date_filed, "
            "c.precedential_status FROM opinions o LEFT JOIN clusters c USING (cl_cluster_id) "
            f"WHERE o.cl_opinion_id IN ({marks})",
            chunk,
        ).fetchall()
        for oid, text, court, docket, filed, status in rows:
            if court is None or filed is None:
                r = ParseResult(parse_status="no_cluster")
            else:
                r = parse_opinion(text, court, docket, filed, status, resolver)
            _write(conn, oid, r)
            stats.parsed += 1
            stats.status[r.parse_status] += 1
            dkey = _district_key(court, r.district)
            d = stats.by_district[dkey]
            d["opinions"] += 1
            d[f"status:{r.parse_status}"] += 1
            if r.per_curiam:
                d["author:per_curiam"] += 1
            elif r.author_slug:
                d["author:resolved"] += 1
            elif r.seats and r.seats[0].resolution in ("trial_judge", "retired_justice"):
                d["author:assigned_judge"] += 1
            elif r.author_raw:
                d["author:unresolved"] += 1
            else:
                d["author:none"] += 1
            for kind, detail in r.notes:
                log_rows.append({"cl_opinion_id": oid, "kind": kind, "detail": detail})
            for s in r.unresolved:
                queue_rows.append({
                    "cl_opinion_id": oid, "seat_raw": s.raw, "role": s.role,
                    "reason": s.resolution, "candidates": ";".join(s.candidates),
                    "court": court, "district": r.district or "", "division": r.division or "",
                    "date_filed": filed, "docket_number": docket,
                    "assignment_note": s.assignment_note or "",
                })
                stats.unresolved_shapes[(dkey, s.raw, s.resolution)] += 1
            for sep in r.separate_opinions:
                if sep.author_raw is None:
                    queue_rows.append({
                        "cl_opinion_id": oid, "seat_raw": f"({sep.type} opinion, no signature)",
                        "role": "separate", "reason": "no_signature", "candidates": "",
                        "court": court, "district": r.district or "",
                        "division": r.division or "", "date_filed": filed,
                        "docket_number": docket, "assignment_note": "",
                    })
                    stats.unresolved_shapes[(dkey, "(separate, no signature)", "no_signature")] += 1
            if r.parse_status == "no_signature":
                stats.unresolved_shapes[(dkey, "(no author signature)", "no_signature")] += 1
        conn.commit()
    stats.superseded = mark_superseded(conn, set(ids))
    conn.commit()
    if unresolved_path is not None:
        _merge_csv(unresolved_path, QUEUE_FIELDS, set(ids), queue_rows)
    if log_path is not None:
        _merge_csv(log_path, LOG_FIELDS, set(ids), log_rows)
    return stats


def mark_superseded(conn: sqlite3.Connection, touched: set[int]) -> int:
    """Recompute superseded_by for every docket group that contains a touched opinion."""
    rows = conn.execute(
        "SELECT o.cl_opinion_id, c.docket_number, o.docket_number_text, c.date_filed, "
        "o.disposition_class FROM opinions o JOIN clusters c USING (cl_cluster_id) "
        "WHERE o.parse_status IS NOT NULL"
    ).fetchall()
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    keys_of: dict[int, set[str]] = {}
    for oid, docket, dtext, _filed, _dc in rows:
        keys = docket_keys(docket, dtext) or {f"#{oid}"}
        keys_of[oid] = keys
        first, *rest = sorted(keys)
        for k in rest:
            parent[find(k)] = find(first)
    groups: dict[str, list] = defaultdict(list)
    for row in rows:
        groups[find(sorted(keys_of[row[0]])[0])].append(row)
    count = 0
    for members in groups.values():
        member_ids = [m[0] for m in members]
        if len(members) < 2 or not touched.intersection(member_ids):
            if len(members) == 1 and members[0][0] in touched:
                conn.execute("UPDATE opinions SET superseded_by = NULL WHERE cl_opinion_id = ?",
                             (members[0][0],))
            continue
        texts = dict(conn.execute(
            f"SELECT cl_opinion_id, text FROM opinions WHERE cl_opinion_id IN "
            f"({','.join('?' * len(member_ids))})", member_ids,
        ).fetchall())
        items = [DedupeItem(m[0], m[3] or "", m[4], texts.get(m[0]) or "") for m in members]
        sup = find_superseded(items)
        for oid in member_ids:
            conn.execute("UPDATE opinions SET superseded_by = ? WHERE cl_opinion_id = ?",
                         (sup.get(oid), oid))
        count += len(sup)
    return count


def report(stats: Stats, top: int = 15) -> str:
    out = [f"Parsed {stats.parsed} opinions; superseded duplicates: {stats.superseded}", "",
           "parse_status: " + ", ".join(f"{k}={v}" for k, v in stats.status.most_common()), "",
           "By district (S = Supreme Court):"]
    for key in sorted(stats.by_district):
        d = stats.by_district[key]
        n = d["opinions"]
        parts = [f"{k}={v} ({100 * v / n:.1f}%)" for k, v in sorted(d.items()) if k != "opinions"]
        out.append(f"  {key}: n={n}; " + "; ".join(parts))
    out += ["", f"Top {top} unresolved signature shapes (district, seat, reason):"]
    for (dkey, raw, reason), n in stats.unresolved_shapes.most_common(top):
        out.append(f"  {n:4d}  {dkey}  {raw}  [{reason}]")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--only-unparsed", action="store_true")
    args = ap.parse_args(argv)
    settings = config.load()
    conn = db.connect(settings.path("database"))
    review = settings.path("review")
    stats = parse_database(
        conn, limit=args.limit, only_unparsed=args.only_unparsed,
        unresolved_path=review / "unresolved.csv", log_path=review / "parse_log.csv",
    )
    print(report(stats))


if __name__ == "__main__":
    main()
