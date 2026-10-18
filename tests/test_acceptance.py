"""U12: acceptance checks over the rendered guide, and the owner's sample."""

import json

from src import acceptance, render


def write_guide(tmp_path, page_text, methodology="Corrections: corrections@example.org\n"):
    guide = tmp_path / "guide"
    (guide / "justices").mkdir(parents=True)
    (guide / "justices" / "a.md").write_text(page_text)
    (guide / "methodology.md").write_text(methodology)
    (guide / "index.md").write_text("# Index\n")
    return guide


GOOD_PAGE = "## Limitations\n\ntext\n\nData window: 2020-01-01 through 2026-10-27. " \
            "Last updated: 2026-10-27.\n"


def test_page_missing_limitations_note_fails_naming_page(tmp_path):
    guide = write_guide(tmp_path, "Data window: x. Last updated: y.\n")
    failures = acceptance.check_pages(guide)
    assert any("justices/a.md" in f and "Limitations" in f for f in failures)


def test_good_page_passes(tmp_path):
    assert acceptance.check_pages(write_guide(tmp_path, GOOD_PAGE)) == []


def test_unfilled_placeholder_fails(tmp_path):
    guide = write_guide(tmp_path, GOOD_PAGE, methodology=f"Corrections: {render.PLACEHOLDER}\n")
    assert any("placeholder" in f for f in acceptance.check_pages(guide))


def test_draft_date_fails(tmp_path):
    page = GOOD_PAGE.replace("Last updated: 2026-10-27", "Last updated: draft (no release "
                                                          "date set)")
    assert any("release date" in f for f in acceptance.check_pages(write_guide(tmp_path, page)))


def test_owner_sample_draws_only_promoted_listed_records_and_is_seeded(tmp_path):
    notes = tmp_path / "case_notes.jsonl"
    records = [{"cl_opinion_id": i, "listing_decision": "listed" if i % 3 else "excluded",
                "justice_slug": "a", "topic": "search_seizure"} for i in range(1, 40)]
    notes.write_text("".join(json.dumps(r) + "\n" for r in records))
    a = acceptance.owner_sample(notes, seed=5)
    assert a == acceptance.owner_sample(notes, seed=5)
    assert len(a) == 10
    assert all(r["listing_decision"] == "listed" for r in a)
