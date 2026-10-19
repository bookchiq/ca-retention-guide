"""Resolve a signature (surname as printed plus title) to a justice slug (R8, KTD4).

A signature resolves only when exactly one roster justice (ballot or non-ballot)
has a matching surname alias AND a service period on the same court, district and
division, with a matching title, that may cover the filing date. Never surname
alone, and never a best guess:

- No candidate or more than one candidate: unresolved, and queued for review.
- An assigned judge (starred signature) resolves only through the assignment
  footnote: a sitting Court of Appeal justice is matched against the court,
  district and division the footnote names. Assigned trial judges and retired
  justices never resolve to any slug, and are not queued (nothing to look up).
- An assigned judge with no readable footnote is queued.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src import justices

ORDINAL_DISTRICTS = {
    "FIRST": "1", "SECOND": "2", "THIRD": "3", "FOURTH": "4", "FIFTH": "5", "SIXTH": "6",
}
DIVISION_WORDS = {
    "ONE": "One", "TWO": "Two", "THREE": "Three", "FOUR": "Four",
    "FIVE": "Five", "SIX": "Six", "SEVEN": "Seven", "EIGHT": "Eight",
}

_APPELLATE_NOTE = re.compile(
    r"(?:\b(?P<title>Administrative Presiding|Presiding|Associate)\s+)?Justice\s+of\s+the\s+"
    r"Court\s+of\s+Appeal,?\s+(?P<district>First|Second|Third|Fourth|Fifth|Sixth)\s+"
    r"Appell(?:ate|ant)\s+"
    r"District(?:,?\s+Division\s+(?P<division>One|Two|Three|Four|Five|Six|Seven|Eight))?",
    re.I,
)
_RETIRED = re.compile(r"\bretired[^.]*justice\b", re.I)  # also "RetiredAssociate Justice"
_TRIAL_JUDGE = re.compile(r"\bsuperior\s+court\b|\bsup(?:er)?\.?\s*ct\b", re.I)


def name_key(name: str) -> str:
    """Comparison key: accents folded, apostrophes/spaces/hyphens dropped, uppercase."""
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return re.sub(r"[^A-Z]", "", folded.upper())


def title_matches(signature_title: str, period_title: str) -> bool:
    """`P. J.` needs a presiding period, `C. J.` a chief justice period; `J.` and
    `Acting P. J.` are signed by associate justices."""
    sig = signature_title.replace(" ", "").upper()
    period = period_title.lower()
    if sig == "P.J.":
        return "presiding" in period
    if sig == "C.J.":
        return period == "chief justice"
    return period == "associate justice"


@dataclass(frozen=True)
class Resolution:
    slug: str | None
    # resolved | no_match | ambiguous | assigned_unknown | trial_judge | retired_justice
    status: str
    candidates: tuple[str, ...] = ()

    @property
    def queue(self) -> bool:
        """True when a person must look at this signature (data/review/unresolved.csv)."""
        return self.status in ("no_match", "ambiguous", "assigned_unknown")


@dataclass(frozen=True)
class Assignment:
    kind: str  # appellate_justice | trial_judge | retired_justice | unknown
    district: str = ""
    division: str = ""
    title: str = ""


def classify_assignment(note: str | None) -> Assignment:
    if not note:
        return Assignment("unknown")
    text = re.sub(r"\s+", " ", note)
    if _RETIRED.search(text):
        return Assignment("retired_justice")
    m = _APPELLATE_NOTE.search(text)
    if m:
        title = "P. J." if "presiding" in (m.group("title") or "").lower() else "J."
        division = DIVISION_WORDS[m.group("division").upper()] if m.group("division") else ""
        return Assignment(
            "appellate_justice", ORDINAL_DISTRICTS[m.group("district").upper()], division, title,
        )
    if _TRIAL_JUDGE.search(text):
        return Assignment("trial_judge")
    return Assignment("unknown")


class Resolver:
    def __init__(self, data_dir: Path | None = None):
        self._by_key: dict[str, set[str]] = {}
        for row in justices.load_aliases(data_dir):
            self._by_key.setdefault(name_key(row["alias_surname_signature"]), set()).add(
                row["slug"]
            )
        self._periods = justices.load_service_periods(data_dir)

    def candidates(
        self, surname: str, title: str, court: str, district: str, division: str, on: date,
    ) -> tuple[str, ...]:
        # "M. KIM": the initial must match the first letter of the justice's slug.
        initial = re.match(r"([A-Z])\.\s+(.+)", surname.strip())
        if initial:
            surname = initial.group(2)
        named = {
            slug for slug in self._by_key.get(name_key(surname), set())
            if not initial or slug.startswith(initial.group(1).lower())
        }
        hits = {
            p.slug
            for p in self._periods
            if p.slug in named
            and p.court == court
            and (p.district or "") == (district or "")
            and (p.division or "") == (division or "")
            and title_matches(title, p.title)
            and p.may_cover(on)
        }
        return tuple(sorted(hits))

    def resolve(
        self,
        surname: str,
        title: str,
        court: str,
        district: str | None,
        division: str | None,
        on: date,
        assigned: bool = False,
        assignment_note: str | None = None,
    ) -> Resolution:
        if assigned:
            a = classify_assignment(assignment_note)
            if a.kind in ("trial_judge", "retired_justice"):
                return Resolution(None, a.kind)
            if a.kind != "appellate_justice":
                return Resolution(None, "assigned_unknown")
            court, district, division, title = "appeal", a.district, a.division, a.title
        found = self.candidates(surname, title, court, district or "", division or "", on)
        if len(found) == 1:
            return Resolution(found[0], "resolved", found)
        return Resolution(None, "ambiguous" if found else "no_match", found)
