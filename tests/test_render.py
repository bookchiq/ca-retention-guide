"""U11: guide rendering — gating states, listings, determinism, lint, exports."""

import csv

import pytest

from src import render

TOPICS = {
    "search_seizure": {"tier": 1, "validated": True},
    "interrogation": {"tier": 2, "validated": False},
    "arbitration": {"tier": 3, "validated": False},
}


def justice(slug, court="appeal", district="4", division="One", sd="true", **kw):
    base = {
        "slug": slug, "full_name_ballot": slug.upper(), "display_name": slug.title(),
        "court": court, "district": district, "division": division, "title": "Associate Justice",
        "sd_ballot": sd, "appellate_start_date": "2020-01-01", "appointing_governor": "Newsom",
        "prior_career": "prosecutor;trial_judge", "prior_retention": "2022:61.5",
        "cjp_public_discipline": "none_found", "cjp_search_date": "2026-10-17",
        "limited_record": "false", "bio_url": "https://appellate.courts.ca.gov/x",
        "ballot_question": f"Shall {slug} be elected to the office for the term provided by law?",
        "appellate_start_source_url": "https://appellate.courts.ca.gov/x",
        "appointing_governor_source_url": "https://www.gov.ca.gov/x",
        "prior_career_source_url": "https://appellate.courts.ca.gov/x",
        "prior_retention_source_url": "https://www.sos.ca.gov/x",
        "cjp_source_url": "https://cjp.ca.gov/x",
    }
    base.update(kw)
    return base


def metric_rows(slug, *, rate=0.25, base=0.3):
    rows = [
        {"slug": slug, "metric": "authored_total", "topic": "", "value": "40"},
        {"slug": slug, "metric": "panels", "topic": "", "value": "120"},
        {"slug": slug, "metric": "publication_rate", "topic": "", "value": str(rate),
         "baseline": str(base), "baseline_n": "900", "n": "40"},
        {"slug": slug, "metric": "dissents", "topic": "", "value": "2"},
        {"slug": slug, "metric": "dissents_per_100_panels", "topic": "", "value": "1.6667",
         "baseline": "1.2", "baseline_n": "2700", "n": "120"},
        {"slug": slug, "metric": "concurrences", "topic": "", "value": "1"},
        {"slug": slug, "metric": "concurrences_per_100_panels", "topic": "", "value": "0.8333",
         "baseline": "0.5", "baseline_n": "2700", "n": "120"},
    ]
    for topic in TOPICS:
        for m, v in (("topic_authored", "3"), ("topic_panels", "9"), ("contested_majority", "1"),
                     ("contested_dissent", "0")):
            rows.append({"slug": slug, "metric": m, "topic": topic, "value": v})
    for r in rows:
        r.setdefault("baseline", "")
        r.setdefault("baseline_n", "")
        r.setdefault("n", "")
        r.setdefault("window_start", "2020-01-01")
        r.setdefault("note", "")
    return rows


def note(slug, oid, date, summary="Wrote the opinion holding the search lawful; affirmed."):
    return {
        "cl_opinion_id": oid, "case_name": f"People v. Case{oid}", "citation_or_docket": f"D0{oid}",
        "date_filed": date, "published": False, "justice_slug": slug, "topic": "search_seizure",
        "listing_decision": "listed", "role": "author", "listing_rule": "L3",
        "summary": summary, "vote": "3-0",
        "opinion_url": f"https://www.courtlistener.com/opinion/{oid}/x/",
        "verified": True, "second_check": "passed",
    }


def make_inputs(**overrides):
    inputs = render.Inputs(
        justices=[justice("dato"), justice("other", district="1", sd="false")],
        metrics=metric_rows("dato") + metric_rows("other"),
        case_notes=[], reviewed={}, topics=TOPICS, validated={"4", "1", "supreme"},
        sc_dissents=None, window_start="2020-01-01", window_end="2026-10-27",
        updated="2026-10-27", bulk_snapshot="2026-09-30", tier2_enabled=False,
        correction_contact=None, validation_summary="(validation)", tag_summary="(tags)",
    )
    for k, v in overrides.items():
        setattr(inputs, k, v)
    return inputs


def page(out, slug):
    return (out / "justices" / f"{slug}.md").read_text()


def test_render_is_byte_identical_on_rerun(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    render.render(make_inputs(), a)
    render.render(make_inputs(), b)
    files_a = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    assert files_a == sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
    for rel in files_a:
        assert (a / rel).read_bytes() == (b / rel).read_bytes()


def test_unreviewed_topic_shows_counts_and_no_list(tmp_path):
    render.render(make_inputs(case_notes=[note("dato", 1, "2024-01-01")]), tmp_path)
    text = page(tmp_path, "dato")
    assert "not yet reviewed" in text
    assert "People v. Case1" not in text  # promoted notes alone don't mark it reviewed


def test_reviewed_topic_shows_25_newest_and_links_csv(tmp_path):
    notes = [note("dato", i, f"2024-01-{i:02d}") for i in range(1, 31)]
    reviewed = {("dato", "search_seizure"): {"queued": 30, "listed": 30, "excluded": 0}}
    render.render(make_inputs(case_notes=notes, reviewed=reviewed), tmp_path)
    text = page(tmp_path, "dato")
    assert "People v. Case30" in text and "People v. Case6*" in text
    assert "People v. Case5*" not in text
    assert "data/case_notes/dato.csv" in text
    with open(tmp_path / "data" / "case_notes" / "dato.csv") as fh:
        assert len(list(csv.DictReader(fh))) == 30


def test_reviewed_with_nothing_listed(tmp_path):
    reviewed = {("dato", "search_seizure"): {"queued": 4, "listed": 0, "excluded": 4}}
    render.render(make_inputs(reviewed=reviewed), tmp_path)
    assert "none. No case in the window met the listing rules" in page(tmp_path, "dato")


def test_limited_record_page_has_background_only(tmp_path):
    inputs = make_inputs(justices=[justice("newbie", limited_record="true")],
                         metrics=metric_rows("newbie"))
    render.render(inputs, tmp_path)
    text = page(tmp_path, "newbie")
    assert "Limited appellate record" in text
    assert "Record at a glance" not in text


def test_unvalidated_district_shows_metrics_not_available(tmp_path):
    render.render(make_inputs(validated={"supreme"}), tmp_path)
    assert "Metrics not available" in page(tmp_path, "dato")


def test_every_rate_has_a_baseline_cell(tmp_path):
    render.render(make_inputs(), tmp_path)
    for line in page(tmp_path, "dato").splitlines():
        if line.startswith("| Share") or "per 100 panels" in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            assert len(cells) == 3 and cells[2] not in ("", "—")


def test_banned_word_fails_render_naming_file(tmp_path):
    notes = [note("dato", 1, "2024-01-01", summary="Wrote a lenient opinion; reversed.")]
    reviewed = {("dato", "search_seizure"): {"queued": 1, "listed": 1, "excluded": 0}}
    with pytest.raises(render.LintFailure, match="justices/dato.md"):
        render.render(make_inputs(case_notes=notes, reviewed=reviewed), tmp_path)


def test_index_follows_ballot_order_not_metrics(tmp_path):
    js = [justice("zeta"), justice("alpha")]
    metrics = metric_rows("zeta", rate=0.01) + metric_rows("alpha", rate=0.99)
    render.render(make_inputs(justices=js, metrics=metrics), tmp_path)
    index = (tmp_path / "index.md").read_text()
    assert index.index("Zeta") < index.index("Alpha")


def test_unvalidated_topics_hidden_from_pages_but_kept_in_data(tmp_path):
    render.render(make_inputs(), tmp_path)
    text = page(tmp_path, "dato")
    assert "### Search and seizure" in text
    assert "Interrogation" not in text and "Arbitration" not in text
    assert "2 other topics are not shown yet" in text
    with open(tmp_path / "data" / "metrics.csv") as fh:
        rows = [r for r in csv.DictReader(fh) if r["slug"] == "dato"]
    notes = {r["topic"]: r["note"] for r in rows if r["topic"]}
    assert notes["interrogation"] == "unvalidated keywords"
    assert notes["search_seizure"] == ""


def test_supreme_court_page_quotes_denial_dissents_with_attribution(tmp_path):
    sc = {"source": {"title": "T", "author": "David S. Ettinger", "publication": "At the Lectern",
                     "date": "2025-09-15", "url": "https://www.horvitzlevy.com/x/"},
          "term": "2024–25",
          "justices": {"kelli-m-evans": {"dissenting_votes": 63, "criminal": 63, "civil": 0}}}
    js = [justice("kelli-m-evans", court="supreme", district="", division=""), justice("dato")]
    inputs = make_inputs(justices=js, metrics=metric_rows("kelli-m-evans") + metric_rows("dato"),
                         sc_dissents=sc)
    render.render(inputs, tmp_path)
    assert "https://www.horvitzlevy.com/x/" in page(tmp_path, "kelli-m-evans")
    assert "63 dissenting votes" in page(tmp_path, "kelli-m-evans")
    assert "Dissents from denial of review" not in page(tmp_path, "dato")


def test_headings_always_start_their_own_line(tmp_path):
    render.render(make_inputs(), tmp_path)
    for line in page(tmp_path, "dato").splitlines():
        assert "#" not in line or line.startswith("#") or "](" in line, line


def test_multiple_source_urls_render_as_separate_links(tmp_path):
    js = [justice("dato", prior_retention_source_url="https://a.example/1;https://a.example/2")]
    render.render(make_inputs(justices=js, metrics=metric_rows("dato")), tmp_path)
    text = page(tmp_path, "dato")
    assert "](https://a.example/1)" in text and "](https://a.example/2)" in text
    assert ";https" not in text


def test_listing_display_drops_courtlistener_suffixes(tmp_path):
    n = note("dato", 1, "2024-01-01")
    n.update(case_name="People v. Lewis CA4/1", citation_or_docket="D080606M")
    reviewed = {("dato", "search_seizure"): {"queued": 1, "listed": 1, "excluded": 0}}
    render.render(make_inputs(case_notes=[n], reviewed=reviewed), tmp_path)
    text = page(tmp_path, "dato")
    assert "*People v. Lewis* (D080606," in text
    assert "CA4/1" not in text and "D080606M" not in text


def test_credit_and_contact_appear_on_every_page(tmp_path):
    render.render(make_inputs(credit="An experiment by Test Author",
                              correction_contact="Open an issue."), tmp_path)
    for rel in ("index.md", "methodology.md", "justices/dato.md"):
        assert "An experiment by Test Author" in (tmp_path / rel).read_text(), rel
    assert "Open an issue." in (tmp_path / "index.md").read_text()
    assert render.PLACEHOLDER not in (tmp_path / "methodology.md").read_text()


def test_methodology_reports_review_counts_from_records(tmp_path):
    listed = note("dato", 1, "2024-01-01")
    excluded = dict(note("dato", 2, "2024-02-01"), listing_decision="excluded",
                    exclusion_reason="topic_not_at_issue", second_check="not_sampled")
    other = dict(note("other", 3, "2024-03-01"), listing_decision="excluded",
                 exclusion_reason="topic_not_at_issue", second_check="failed")
    render.render(make_inputs(case_notes=[listed, excluded, other]), tmp_path)
    text = (tmp_path / "methodology.md").read_text()
    assert "3 records for 2 justices" in text
    assert "1 cases are listed and 2 were excluded" in text
    assert "| `topic_not_at_issue` | 2 |" in text
    assert "re-read 2 records; 1 had a substantive error" in text


def test_site_config_and_reviewer_notes_are_exported(tmp_path):
    n = dict(note("dato", 1, "2024-01-01"), verification_notes="Checked caption.",
             second_check_note="Re-read in full.")
    render.render(make_inputs(case_notes=[n]), tmp_path)
    assert "jekyll-relative-links" in (tmp_path / "_config.yml").read_text()
    with open(tmp_path / "data" / "case_notes.csv") as fh:
        row = next(csv.DictReader(fh))
    assert row["verification_notes"] == "Checked caption."
    assert row["second_check_note"] == "Re-read in full."


def test_other_appellate_service_row_only_when_present(tmp_path):
    js = [justice("dato", other_appellate_service="Pro tem assignment, 2025",
                  other_appellate_service_source_url="https://a.example/bio"),
          justice("other", district="1", sd="false")]
    render.render(make_inputs(justices=js), tmp_path)
    assert ("| Earlier appellate service | Pro tem assignment, 2025 ([source]"
            "(https://a.example/bio)) |") in page(tmp_path, "dato")
    assert "Earlier appellate service" not in page(tmp_path, "other")


def test_methodology_lists_each_topic_with_its_latest_validation(tmp_path):
    topics = {k: dict(v, definition=f"Decides {k}.") for k, v in TOPICS.items()}
    status = {"interrogation": {"rounds": [
        {"round": "r1", "precision": 0.6, "precision_n": 50, "undercount_share": 0.1},
        {"round": "r2", "precision": 0.9, "precision_n": 50, "undercount_share": 0.25}]}}
    render.render(make_inputs(topics=topics, topic_validation=status), tmp_path)
    text = (tmp_path / "methodology.md").read_text()
    assert "| Interrogation | Decides interrogation. | 90% (N = 50) | 25% | no |" in text
    assert "| Arbitration | Decides arbitration. | not yet checked | — | no |" in text
    assert "| Search and seizure | Decides search_seizure. |" in text


def test_unset_correction_contact_leaves_visible_placeholder(tmp_path):
    render.render(make_inputs(), tmp_path)
    assert render.PLACEHOLDER in (tmp_path / "methodology.md").read_text()
