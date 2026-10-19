"""U2: ballot and justice data checks (R1, R2, R3, KTD4)."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import pytest

from src import justices as j

DATA = Path(__file__).resolve().parents[1] / "data"
RUN_DATE = date(2026, 10, 17)

PRIOR_CAREER_CATEGORIES = {
    "prosecutor",
    "public_defender",
    "private_criminal_defense",
    "civil_plaintiff",
    "civil_defense",
    "government_counsel",
    "appellate_court_staff",
    "trial_judge",
    "academia",
    "policy_or_political_staff",
    "other",
}

# Background field -> the column holding its source URL(s).
FIELD_SOURCES = {
    "full_name_ballot": "ballot_source_url",
    "ballot_question": "ballot_source_url",
    "title": "ballot_source_url",
    "appellate_start_date": "appellate_start_source_url",
    "appellate_start_basis": "appellate_start_source_url",
    "appointing_governor": "appointing_governor_source_url",
    "prior_career": "prior_career_source_url",
    "prior_career_detail": "prior_career_source_url",
    "prior_retention": "prior_retention_source_url",
    "prior_retention_years_checked": "prior_retention_source_url",
    "cjp_public_discipline": "cjp_source_url",
    "cjp_search_date": "cjp_source_url",
}

OFFICIAL_HOSTS = {
    "elections.cdn.sos.ca.gov",
    "appellate.courts.ca.gov",
    "supreme.courts.ca.gov",
    "newsroom.courts.ca.gov",
    "courts.ca.gov",
    "www.courts.ca.gov",
    "www.gov.ca.gov",
    "www.archive.gov.ca.gov",
    "cjp.ca.gov",
}


def read(name):
    with open(DATA / name, newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def justices():
    return read("justices.csv")


@pytest.fixture(scope="module")
def others():
    return read("other_justices.csv")


@pytest.fixture(scope="module")
def periods():
    return read("service_periods.csv")


@pytest.fixture(scope="module")
def aliases():
    return read("aliases.csv")


def urls(cell):
    return [u for u in cell.split(";") if u]


def test_exactly_64_ballot_justices_2_supreme_62_appeal_17_sd(justices):
    assert len(justices) == 64
    courts = Counter(r["court"] for r in justices)
    assert courts == {"supreme": 2, "appeal": 62}
    sd = [r for r in justices if r["sd_ballot"] == "true"]
    assert len(sd) == 17
    # San Diego ballots carry the Supreme Court and the whole Fourth District.
    assert all(r["court"] == "supreme" or r["district"] == "4" for r in sd)
    assert {r["sd_ballot"] for r in justices} <= {"true", "false"}


def test_slugs_unique_and_names_in_ballot_question(justices):
    slugs = [r["slug"] for r in justices]
    assert len(slugs) == len(set(slugs))
    for r in justices:
        q = r["ballot_question"]
        assert q.startswith("Shall ")
        assert q.endswith("be elected to the office for the term provided by law?")
        assert r["full_name_ballot"] in q
        assert r["full_name_ballot"] == r["full_name_ballot"].upper()


def test_every_nonblank_background_field_has_source(justices):
    for r in justices:
        for field, src in FIELD_SOURCES.items():
            if r[field].strip():
                assert r[src].strip(), f"{r['slug']}: {field} set but {src} blank"


def test_source_urls_are_official(justices, others, periods):
    cells = []
    for r in justices:
        cells += [r[c] for c in r if c.endswith("_url")]
    cells += [r["source_url"] for r in others] + [r["source_url"] for r in periods]
    for cell in cells:
        for u in urls(cell):
            parsed = urlparse(u)
            assert parsed.scheme == "https", u
            assert parsed.hostname in OFFICIAL_HOSTS, u


def test_prior_career_values_from_category_list(justices):
    for r in justices:
        values = [v for v in r["prior_career"].split(";") if v]
        assert set(values) <= PRIOR_CAREER_CATEGORIES, r["slug"]


def test_cjp_fields_consistent(justices):
    for r in justices:
        if r["cjp_public_discipline"]:
            assert r["cjp_search_date"], r["slug"]
            date.fromisoformat(r["cjp_search_date"])


def test_partial_dates_parse(justices, periods):
    for r in justices:
        if r["appellate_start_date"]:
            j.PartialDate.parse(r["appellate_start_date"])
    for p in periods:
        j.PartialDate.parse(p["start"])
        if p["end"]:
            j.PartialDate.parse(p["end"])


def test_every_alias_and_period_slug_in_exactly_one_roster(justices, others, aliases, periods):
    ballot = {r["slug"] for r in justices}
    other = {r["slug"] for r in others}
    assert not ballot & other
    assert all(r["ballot"] == "false" for r in others)
    for row in aliases + periods:
        assert (row["slug"] in ballot) != (row["slug"] in other), row["slug"]


def test_every_ballot_justice_has_a_service_period(justices, periods):
    with_periods = {p["slug"] for p in periods}
    assert {r["slug"] for r in justices} <= with_periods


def test_service_periods_do_not_overlap(periods):
    by_slug = defaultdict(list)
    for p in periods:
        by_slug[p["slug"]].append(j.ServicePeriod.from_row(p))
    for slug, ps in by_slug.items():
        assert not j.overlapping(ps), slug


def test_overlap_detection_catches_overlap():
    a = j.ServicePeriod("x", "appeal", "4", "One", "Associate Justice",
                        j.PartialDate.parse("2020-01-01"), j.PartialDate.parse("2023-01-01"), "")
    b = j.ServicePeriod("x", "appeal", "4", "Two", "Associate Justice",
                        j.PartialDate.parse("2022-06-01"), None, "")
    assert j.overlapping([a, b])


def test_limited_record_examples():
    records = j.compute_limited_records(RUN_DATE, data_dir=DATA)
    assert records["lisa-rodriguez"] is True  # confirmed Aug 20, 2026
    assert records["rashida-a-adams"] is False  # on the court since 2023; PJ period is new
    assert records["juliet-o-macaulay"] is True
    assert records["joshua-groban"] is False


def test_limited_record_column_matches_computation(justices):
    records = j.compute_limited_records(RUN_DATE, data_dir=DATA)
    for r in justices:
        assert r["limited_record"] == ("true" if records[r["slug"]] else "false"), r["slug"]


def test_limited_record_boundary_and_ambiguity():
    assert j.limited_record(j.PartialDate.parse("2025-10-18"), RUN_DATE) is True
    assert j.limited_record(j.PartialDate.parse("2025-10-17"), RUN_DATE) is False
    assert j.limited_record(j.PartialDate.parse("2018"), RUN_DATE) is False
    with pytest.raises(j.AmbiguousDate):
        j.limited_record(j.PartialDate.parse("2025-10"), RUN_DATE)


@pytest.mark.parametrize(
    "surname,court,district,division,expected",
    [
        ("RODRIGUEZ", "appeal", "1", "Three", "victor-a-rodriguez"),
        ("RODRIGUEZ", "appeal", "4", "One", "lisa-rodriguez"),
        ("ADAMS", "appeal", "2", "Three", "rashida-a-adams"),
        ("ADAMS", "appeal", "6", "", "charles-f-adams"),
        ("WILSON", "appeal", "1", "One", "monique-langhorne-wilson"),
        ("WILSON", "appeal", "6", "", "charles-e-wilson-ii"),
    ],
)
def test_collision_pairs_resolve_by_district(surname, court, district, division, expected):
    # 2027-02-01 so that Lisa Rodriguez's seat (term begins 2027-01-04) is in service.
    on = date(2027, 2, 1)
    found = j.candidate_slugs(surname, court, district, division, on, data_dir=DATA)
    assert found == [expected]


def test_known_collisions_recorded(aliases):
    by_alias = defaultdict(set)
    for a in aliases:
        by_alias[a["alias_surname_signature"].upper()].add(a["slug"])
    assert {"victor-a-rodriguez", "lisa-rodriguez"} <= by_alias["RODRIGUEZ"]
    assert {"rashida-a-adams", "charles-f-adams"} <= by_alias["ADAMS"]
    assert {"monique-langhorne-wilson", "charles-e-wilson-ii"} <= by_alias["WILSON"]
