"""U9: review queue, draft records, verification, second-check sampling, and
promotion into the tracked case_notes.jsonl."""

import json

import pytest

from src import db, guard, review

TOPICS = {"search_seizure": {
    "issue_types": ["warrant_sufficiency", "detention_or_stop", "other"],
    "outcomes": ["evidence_suppressed_or_search_held_unlawful", "search_upheld", "mixed",
                 "not_reached"],
}}


def add_opinion(conn, oid, *, author="dato", joined=("kelety", "do"), published=0,
                disposition="affirmed", dissent_by=None, queue=1, court="calctapp",
                date="2024-05-01", sep_type="dissent"):
    conn.execute(
        "INSERT INTO clusters (cl_cluster_id, court, case_name, docket_number, date_filed, "
        "precedential_status, absolute_url, source) VALUES (?, ?, ?, ?, ?, ?, ?, 'test')",
        (oid, court, f"People v. Case{oid}", f"D0{oid}", date,
         "Published" if published else "Unpublished", f"/opinion/{oid}/people-v-case{oid}/"),
    )
    conn.execute(
        "INSERT INTO opinions (cl_opinion_id, cl_cluster_id, text, source, published, "
        "disposition_class, author_slug, has_dissent, parse_status) "
        "VALUES (?, ?, 'x', 'test', ?, ?, ?, ?, 'ok')",
        (oid, oid, published, disposition, author, int(dissent_by is not None)),
    )
    conn.execute("INSERT INTO panel_seats (cl_opinion_id, seat_raw, slug, role) "
                 "VALUES (?, ?, ?, 'author')", (oid, author.upper(), author))
    for j in joined:
        conn.execute("INSERT INTO panel_seats (cl_opinion_id, seat_raw, slug, role) "
                     "VALUES (?, ?, ?, 'joined')", (oid, j.upper(), j))
    if dissent_by:
        conn.execute("INSERT INTO separate_opinions (cl_opinion_id, type, partial, author_slug) "
                     "VALUES (?, ?, 0, ?)", (oid, sep_type, dissent_by))
    if queue:
        conn.execute("INSERT INTO topic_tags VALUES (?, 'search_seizure', 1, 0, 1, 1)", (oid,))


@pytest.fixture
def conn():
    return db.connect(":memory:")


def queue_ids(conn, slug="dato", court="calctapp"):
    return [e["cl_opinion_id"] for e in
            review.build_queue(conn, slug, "search_seizure", "2020-01-01", court)]


def test_queue_includes_published_and_nonaffirmance_authored_but_not_pure_affirmance(conn):
    add_opinion(conn, 1, published=1, disposition="affirmed")
    add_opinion(conn, 2, published=0, disposition="reversed")
    add_opinion(conn, 3, published=0, disposition="affirmed")
    assert queue_ids(conn) == [2, 1]  # newest first by date then id; same date -> id desc


def test_joined_over_dissent_is_l4_candidate(conn):
    add_opinion(conn, 4, author="kelety", joined=("dato", "do"), dissent_by="do")
    entry = review.build_queue(conn, "dato", "search_seizure", "2020-01-01", "calctapp")[0]
    assert entry["cl_opinion_id"] == 4
    assert "L4" in entry["candidate_rules"]


def test_authored_unpublished_affirmance_over_dissent_is_l4_candidate(conn):
    add_opinion(conn, 8, author="dato", published=0, disposition="affirmed", dissent_by="do")
    entry = review.build_queue(conn, "dato", "search_seizure", "2020-01-01", "calctapp")[0]
    assert entry["candidate_rules"] == ["L4"]


def test_own_dissent_is_l1_not_l4(conn):
    add_opinion(conn, 5, author="kelety", joined=("do", "dato"), dissent_by="dato")
    entry = review.build_queue(conn, "dato", "search_seizure", "2020-01-01", "calctapp")[0]
    assert entry["candidate_rules"] == ["L1"]


def test_untagged_opinion_never_queued(conn):
    add_opinion(conn, 6, published=1, queue=0)
    assert queue_ids(conn) == []


def test_supreme_court_queues_every_authored_matching_opinion(conn):
    add_opinion(conn, 7, author="joshua-groban", joined=("kelli-m-evans",), court="cal",
                published=1, disposition="affirmed")
    entry = review.build_queue(conn, "joshua-groban", "search_seizure", "2020-01-01", "cal")[0]
    assert "SC" in entry["candidate_rules"]


def listed(**overrides):
    rec = {
        "cl_opinion_id": 1, "case_name": "People v. Case1", "citation_or_docket": "D01",
        "date_filed": "2024-05-01", "published": False, "justice_slug": "dato",
        "listing_decision": "listed", "exclusion_reason": None,
        "role": "author", "listing_rule": "L3", "topic": "search_seizure",
        "issue_type": "detention_or_stop", "posture": "defendant_appeal",
        "trial_court_ruling": "Denied the motion to suppress.",
        "result_on_issue": "Held the detention unlawful.",
        "outcome": "evidence_suppressed_or_search_held_unlawful", "vote": "3-0",
        "summary": "Wrote the opinion holding the detention unlawful; reversed.",
        "opinion_url": "https://www.courtlistener.com/opinion/1/people-v-case1/",
        "verified": False, "verified_by": "", "verified_date": "", "verification_notes": "",
        "second_check": "pending",
    }
    rec.update(overrides)
    return rec


def test_valid_listed_record_passes():
    assert review.validate_record(listed(), TOPICS) == []


def test_excluded_without_reason_fails():
    errors = review.validate_record(
        listed(listing_decision="excluded", exclusion_reason=None), TOPICS)
    assert any("exclusion_reason" in e for e in errors)


def test_not_reached_is_not_an_exclusion_reason():
    errors = review.validate_record(
        listed(listing_decision="excluded", exclusion_reason="not_reached"), TOPICS)
    assert any("exclusion_reason" in e for e in errors)


def test_summary_over_50_words_fails():
    errors = review.validate_record(listed(summary=" ".join(["word"] * 51)), TOPICS)
    assert any("50 words" in e for e in errors)


def test_value_laden_outcome_fails():
    errors = review.validate_record(listed(outcome="won"), TOPICS)
    assert any("outcome" in e for e in errors)


def test_role_inconsistent_with_rule_fails():
    errors = review.validate_record(listed(listing_rule="L1", role="author"), TOPICS)
    assert any("role" in e for e in errors)


def test_sample_size_is_fifteen_percent_with_minimum_one():
    assert review.sample_size(4) == 1
    assert review.sample_size(20) == 3
    assert review.sample_size(0) == 0


@pytest.fixture
def workspace(tmp_path):
    ws = review.Workspace(tmp_path / "drafts", tmp_path / "queue", tmp_path / "case_notes.jsonl")
    ws.drafts.mkdir()
    ws.queue.mkdir()
    return ws


def write_queue(ws, slug, topic, ids):
    path = ws.queue / f"{slug}__{topic}.jsonl"
    path.write_text("".join(json.dumps({"cl_opinion_id": i}) + "\n" for i in ids))


def write_drafts(ws, slug, topic, records):
    path = ws.drafts / slug / f"{topic}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records))


def test_promote_refuses_when_a_queued_case_is_undecided(workspace):
    write_queue(workspace, "dato", "search_seizure", [1, 2])
    write_drafts(workspace, "dato", "search_seizure",
                 [listed(verified=True, second_check="passed")])
    with pytest.raises(review.PromotionRefused, match="2"):
        review.promote(workspace, "dato", "search_seizure", TOPICS)


def test_promote_refuses_when_a_sampled_record_failed(workspace):
    write_queue(workspace, "dato", "search_seizure", [1])
    write_drafts(workspace, "dato", "search_seizure",
                 [listed(verified=True, second_check="failed")])
    with pytest.raises(review.PromotionRefused, match="second check"):
        review.promote(workspace, "dato", "search_seizure", TOPICS)


def test_topic_with_no_drawn_records_promotes_after_justice_check_passes(workspace):
    write_queue(workspace, "dato", "search_seizure", [1, 2])
    write_drafts(workspace, "dato", "search_seizure", [
        listed(verified=True, second_check="passed"),
        listed(cl_opinion_id=2, verified=True, second_check="not_sampled",
               listing_decision="excluded", exclusion_reason="topic_not_at_issue",
               opinion_url="https://www.courtlistener.com/opinion/2/x/"),
    ])
    review.promote(workspace, "dato", "search_seizure", TOPICS)
    lines = workspace.case_notes.read_text().splitlines()
    assert len(lines) == 2  # excluded records are promoted too


def test_promote_is_deterministic_and_guard_clean(workspace):
    write_queue(workspace, "dato", "search_seizure", [1])
    write_drafts(workspace, "dato", "search_seizure",
                 [listed(verified=True, second_check="passed")])
    review.promote(workspace, "dato", "search_seizure", TOPICS)
    first = workspace.case_notes.read_bytes()
    review.promote(workspace, "dato", "search_seizure", TOPICS)
    assert workspace.case_notes.read_bytes() == first
    problems = guard.check_tree(
        ["data/case_notes.jsonl"], lambda p: first, token=None)
    assert problems == []


def test_promote_records_reviewed_manifest_even_for_empty_queue(workspace):
    write_queue(workspace, "dato", "search_seizure", [])
    write_drafts(workspace, "dato", "search_seizure", [])
    assert review.promote(workspace, "dato", "search_seizure", TOPICS) == 0
    manifest = review.load_reviewed(workspace)
    assert manifest[("dato", "search_seizure")] == {
        "justice_slug": "dato", "topic": "search_seizure", "queued": 0, "listed": 0,
        "excluded": 0}


def test_mark_sample_sets_drawn_pending_and_finish_sets_not_sampled(workspace):
    recs = [listed(cl_opinion_id=i, verified=True, second_check=None) for i in range(1, 8)]
    write_drafts(workspace, "dato", "search_seizure", recs)
    drawn = review.draw_sample(workspace, "dato", seed=7)
    assert len(drawn) == review.sample_size(7)
    for oid in drawn:
        review.record_check(workspace, "dato", oid, passed=True, note="ok", by="s2")
    review.finish_check(workspace, "dato")
    states = {r["cl_opinion_id"]: r["second_check"]
              for r in review.load_drafts(workspace, "dato")}
    assert {states[i] for i in drawn} == {"passed"}
    assert {s for i, s in states.items() if i not in drawn} == {"not_sampled"}
