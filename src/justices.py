"""Justice roster, service periods, aliases, and the limited-record rule.

Data lives in data/justices.csv (the 64 ballot justices), data/other_justices.csv
(non-ballot justices), data/service_periods.csv (one row per seat or title held) and
data/aliases.csv (surname signature forms).

Dates in the data may be partial ("2018", "2018-07" or "2018-07-26") because some
official sources give only a year or a month. Partial dates are kept as ranges and
never rounded to a guessed day. Service periods are half-open: [start, end).
"""

from __future__ import annotations

import calendar
import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class AmbiguousDate(ValueError):
    """A partial date is too coarse to decide a rule; find a more precise source."""


@dataclass(frozen=True)
class PartialDate:
    text: str
    lower: date
    upper: date

    @classmethod
    def parse(cls, text: str) -> PartialDate:
        parts = text.strip().split("-")
        if len(parts) == 3:
            d = date.fromisoformat(text.strip())
            return cls(text, d, d)
        if len(parts) == 2:
            y, m = int(parts[0]), int(parts[1])
            last = calendar.monthrange(y, m)[1]
            return cls(text, date(y, m, 1), date(y, m, last))
        if len(parts) == 1 and len(parts[0]) == 4:
            y = int(parts[0])
            return cls(text, date(y, 1, 1), date(y, 12, 31))
        raise ValueError(f"not a date: {text!r}")


@dataclass(frozen=True)
class ServicePeriod:
    slug: str
    court: str
    district: str
    division: str
    title: str
    start: PartialDate
    end: PartialDate | None
    source_url: str

    @classmethod
    def from_row(cls, row: dict) -> ServicePeriod:
        return cls(
            slug=row["slug"],
            court=row["court"],
            district=row["district"],
            division=row["division"],
            title=row["title"],
            start=PartialDate.parse(row["start"]),
            end=PartialDate.parse(row["end"]) if row["end"].strip() else None,
            source_url=row["source_url"],
        )

    def may_cover(self, on: date) -> bool:
        """True if `on` could fall inside the period, given partial-date uncertainty."""
        if on < self.start.lower:
            return False
        return self.end is None or on <= self.end.upper


def _read(name: str, data_dir: Path | None) -> list[dict]:
    with open((data_dir or DATA_DIR) / name, newline="") as fh:
        return list(csv.DictReader(fh))


def load_justices(data_dir: Path | None = None) -> list[dict]:
    return _read("justices.csv", data_dir)


def load_other_justices(data_dir: Path | None = None) -> list[dict]:
    return _read("other_justices.csv", data_dir)


def load_aliases(data_dir: Path | None = None) -> list[dict]:
    return _read("aliases.csv", data_dir)


def load_service_periods(data_dir: Path | None = None) -> list[ServicePeriod]:
    return [ServicePeriod.from_row(r) for r in _read("service_periods.csv", data_dir)]


def overlapping(periods: list[ServicePeriod]) -> bool:
    """True if any two periods of one justice overlap (half-open, by lower bounds)."""
    ordered = sorted(periods, key=lambda p: p.start.lower)
    for prev, nxt in zip(ordered, ordered[1:], strict=False):
        if prev.end is None or nxt.start.lower < prev.end.lower:
            return True
    return False


def _one_year_after(d: date) -> date:
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # Feb 29
        return d.replace(year=d.year + 1, day=28)


def limited_record(first_start: PartialDate, run_date: date) -> bool:
    """Less than 12 months of appellate service on `run_date` (R2).

    Raises AmbiguousDate when the partial start date straddles the 12-month line.
    """
    early = _one_year_after(first_start.lower) > run_date
    late = _one_year_after(first_start.upper) > run_date
    if early != late:
        raise AmbiguousDate(f"start {first_start.text!r} is too coarse for run date {run_date}")
    return early


def compute_limited_records(run_date: date, data_dir: Path | None = None) -> dict[str, bool]:
    """limited_record for every ballot justice, from their earliest appellate start."""
    by_slug: dict[str, list[ServicePeriod]] = {}
    for p in load_service_periods(data_dir):
        by_slug.setdefault(p.slug, []).append(p)
    out = {}
    for row in load_justices(data_dir):
        periods = by_slug.get(row["slug"])
        if not periods:
            raise ValueError(f"{row['slug']}: no service periods")
        first = min(periods, key=lambda p: p.start.lower).start
        out[row["slug"]] = limited_record(first, run_date)
    return out


def candidate_slugs(
    surname: str,
    court: str,
    district: str,
    division: str,
    on: date,
    data_dir: Path | None = None,
) -> list[str]:
    """Slugs whose alias matches `surname` and who may have sat in that seat on `on`.

    Never matches on surname alone: court, district, division and date must fit a
    recorded service period. Cross-division assignments are not covered here.
    """
    key = surname.strip().upper()
    named = {
        a["slug"]
        for a in load_aliases(data_dir)
        if a["alias_surname_signature"].upper() == key
    }
    hits = {
        p.slug
        for p in load_service_periods(data_dir)
        if p.slug in named
        and p.court == court
        and p.district == district
        and p.division == division
        and p.may_cover(on)
    }
    return sorted(hits)
