"""Name resolution against the real roster (data/*.csv): surname alias plus court,
district, division, title and date, never surname alone (R8, KTD4)."""

from datetime import date
from pathlib import Path

import pytest

from src import resolve
from src.resolve import Resolver


@pytest.fixture(scope="module")
def resolver():
    return Resolver()


def test_mcconnell_and_orourke_resolve_regardless_of_case(resolver):
    on = date(2025, 10, 16)
    for raw in ("McCONNELL", "MCCONNELL", "McConnell"):
        r = resolver.resolve(raw, "P. J.", "appeal", "4", "One", on)
        assert (r.slug, r.status) == ("judith-mcconnell", "resolved")
    for raw in ("O’ROURKE", "O'ROURKE", "O’Rourke"):
        r = resolver.resolve(raw, "Acting P. J.", "appeal", "4", "One", on)
        assert r.slug == "terry-b-orourke"


def test_compound_surname_is_matched_whole(resolver):
    on = date(2025, 10, 16)
    r = resolver.resolve("BOULWARE EURIE", "J.", "appeal", "3", "", on)
    assert r.slug == "stacy-boulware-eurie"
    # No fallback to the last word of a compound name.
    assert resolver.resolve("EURIE", "J.", "appeal", "3", "", on).slug is None


def test_rodriguez_before_service_start_is_unresolved_not_the_other_rodriguez(resolver):
    # Lisa Rodriguez (4th/1) starts 2027-01-04; Victor A. Rodriguez sits in 1st/3.
    r = resolver.resolve("RODRIGUEZ", "J.", "appeal", "4", "One", date(2025, 6, 1))
    assert r.slug is None
    assert r.status == "no_match"
    assert r.queue
    assert resolver.resolve("RODRÍGUEZ", "J.", "appeal", "1", "Three",
                            date(2025, 6, 1)).slug == "victor-a-rodriguez"


def test_adams_presiding_justice_only_within_presiding_period(resolver):
    # Rashida A. Adams: associate 2023-04-17 to 2026-08-20, presiding from 2026-08-20.
    pj_after = resolver.resolve("ADAMS", "P. J.", "appeal", "2", "Three", date(2026, 9, 1))
    assert pj_after.slug == "rashida-a-adams"
    pj_before = resolver.resolve("ADAMS", "P. J.", "appeal", "2", "Three", date(2025, 1, 1))
    assert pj_before.slug is None and pj_before.queue
    assert resolver.resolve("ADAMS", "J.", "appeal", "2", "Three",
                            date(2025, 1, 1)).slug == "rashida-a-adams"
    # Charles F. Adams (6th District) is never a candidate in the 2nd District.
    assert resolver.resolve("ADAMS", "J.", "appeal", "6", "", date(2026, 9, 1)).slug == (
        "charles-f-adams"
    )


def test_leading_initial_must_match_the_justice_first_name(resolver):
    on = date(2026, 2, 23)
    assert resolver.resolve("M. KIM", "J.", "appeal", "2", "One", on).slug == "michelle-c-kim"
    assert resolver.resolve("D. KIM", "J.", "appeal", "2", "One", on).slug is None


def test_assigned_trial_judge_never_resolves(resolver):
    note = ("Judge of the Alameda Superior Court, assigned by the Chief Justice pursuant "
            "to article VI, section 6 of the California Constitution.")
    r = resolver.resolve("CLAY", "J.", "appeal", "1", "Four", date(2025, 10, 16),
                         assigned=True, assignment_note=note)
    assert (r.slug, r.status, r.queue) == (None, "trial_judge", False)


def test_retired_justice_never_resolves_to_a_same_surname_justice(resolver):
    # B333751: a retired Second District presiding justice named Rubin sits by
    # assignment; ballot justice David M. Rubin (4th/1) must not be matched.
    note = ("Retired Presiding Justice of the Court of Appeal, Second Appellate District, "
            "assigned by the Chief Justice pursuant to article VI, section 6 of the "
            "California Constitution.")
    r = resolver.resolve("RUBIN", "J.", "appeal", "2", "Eight", date(2025, 10, 16),
                         assigned=True, assignment_note=note)
    assert (r.slug, r.status, r.queue) == (None, "retired_justice", False)


def test_cross_court_assignment_resolves_only_through_assignment_language(resolver):
    note = ("Presiding Justice of the Court of Appeal, Second Appellate District, "
            "Division Six, assigned by the Chief Justice pursuant to article VI, "
            "section 6 of the California Constitution.")
    on = date(2020, 11, 30)
    r = resolver.resolve("GILBERT", "J.", "supreme", "", "", on,
                         assigned=True, assignment_note=note)
    assert r.slug == "arthur-gilbert"
    # Without the assignment footnote, Gilbert is not a Supreme Court justice.
    assert resolver.resolve("GILBERT", "J.", "supreme", "", "", on).slug is None


def test_assigned_without_a_footnote_is_queued(resolver):
    r = resolver.resolve("DATO", "J.", "appeal", "4", "One", date(2025, 1, 1),
                         assigned=True, assignment_note=None)
    assert (r.slug, r.status, r.queue) == (None, "assigned_unknown", True)


def test_two_roster_matches_are_ambiguous_and_queued(tmp_path: Path):
    data = Path(resolve.__file__).resolve().parents[1] / "data"
    for name in ("justices.csv", "other_justices.csv"):
        (tmp_path / name).write_text((data / name).read_text())
    (tmp_path / "aliases.csv").write_text(
        "slug,alias_surname_signature,notes\n"
        "michelle-c-kim,KIM,surname\n"
        "dorothy-c-kim,KIM,surname\n"
    )
    (tmp_path / "service_periods.csv").write_text(
        "slug,court,district,division,title,start,end,source_url\n"
        "michelle-c-kim,appeal,2,One,Associate Justice,2024,,x\n"
        "dorothy-c-kim,appeal,2,One,Associate Justice,2018,,x\n"
    )
    r = Resolver(tmp_path).resolve("KIM", "J.", "appeal", "2", "One", date(2025, 3, 1))
    assert r.slug is None
    assert r.status == "ambiguous"
    assert r.candidates == ("dorothy-c-kim", "michelle-c-kim")
    assert r.queue


@pytest.mark.parametrize(
    ("note", "kind"),
    [
        # Real footnote texts from opinions in data/cases.sqlite.
        ("Judge of the Orange Super. Ct., assigned by the Chief Justice pursuant to article "
         "VI, section 6 of the California Constitution.", "trial_judge"),
        ("(Judge of the Santa Barbara Sup. Ct assigned by the Chief Justice pursuant to art. "
         "VI, \u00a7 6 of the Cal. Const.)", "trial_judge"),
        ("RetiredAssociate Justice of the Court of Appeal, Fourth Appellate District, Division "
         "One, assigned by the Chief Justice pursuant to article VI, section 6 of the "
         "California Constitution.", "retired_justice"),
        ("Assigned by the Chief Justice pursuant to article VI, section 6 of the California "
         "Constitution.", "unknown"),
    ],
)
def test_assignment_footnote_kinds(note, kind):
    assert resolve.classify_assignment(note).kind == kind


def test_assignment_footnote_without_associate_and_with_appellant_typo(resolver):
    on = date(2025, 6, 2)
    note = ("Justice of the Court of Appeal, Second Appellate District, Division Eight, "
            "assigned by the Chief Justice pursuant to article VI, section 6 of the "
            "California Constitution.")
    a = resolve.classify_assignment(note)
    assert (a.kind, a.district, a.division, a.title) == ("appellate_justice", "2", "Eight", "J.")
    note = ("Associate Justice of the Court of Appeal, Second Appellant District, Division "
            "Five, assigned by the Chief Justice pursuant to article VI, section 6 of the "
            "California Constitution.")
    r = resolver.resolve("BAKER", "J.", "appeal", "2", "One", on, True, note)
    assert r.slug == "lamar-w-baker"
