"""U7: topic tagging rules."""

from src import db, tag

TOPICS = tag.load_keywords()


def hits(text, topic="search_seizure"):
    return tag.score(text, tag.compile_topics(TOPICS))[topic]


def test_single_anchor_tags():
    h = hits("Defendant filed a motion to suppress the evidence.")
    assert h.anchor_hits == 1 and h.tagged and h.queue_match


def test_two_broad_terms_do_not_tag_three_do():
    two = hits("There was probable cause for the detention.")
    assert not two.tagged and two.queue_match
    three = hits("There was probable cause for the detention and consent to search.")
    assert three.tagged


def test_repeated_broad_term_counts_once():
    h = hits("detention detention detention")
    assert h.broad_hits == 1 and not h.tagged


def test_section_symbol_and_word_match_alike():
    assert hits("under Penal Code § 1538.5, subdivision (m)").anchor_hits == 1
    assert hits("under Penal Code section 1538.5").anchor_hits == 1
    assert hits("under §1538.5").anchor_hits == 1


def test_whole_word_only():
    assert hits("Leonard testified.").broad_hits == 0
    assert hits("The Leon good faith rule applies.").broad_hits == 1


def test_one_broad_term_matches_queue_but_not_tag():
    h = hits("The officer had reasonable suspicion.")
    assert h.queue_match and not h.tagged


def test_prefix_term_matches_word_stem():
    h = hits("The agreement was procedurally unconscionable.", "arbitration")
    assert h.tagged


def test_rerun_after_keyword_change_replaces_rows():
    conn = db.connect(":memory:")
    conn.execute(
        "INSERT INTO opinions (cl_opinion_id, cl_cluster_id, text, source) "
        "VALUES (1, 1, 'motion to suppress', 't')"
    )
    tag.tag_all(conn, TOPICS)
    tag.tag_all(conn, TOPICS)
    rows = conn.execute(
        "SELECT COUNT(*) FROM topic_tags WHERE cl_opinion_id = 1 AND topic = 'search_seizure'"
    ).fetchone()[0]
    assert rows == 1
    narrowed = {k: dict(v) for k, v in TOPICS.items()}
    narrowed["search_seizure"]["anchors"] = ["fourth amendment"]
    tag.tag_all(conn, narrowed)
    row = conn.execute(
        "SELECT tagged FROM topic_tags WHERE cl_opinion_id = 1 AND topic = 'search_seizure'"
    ).fetchone()
    assert row is None  # no hits under the narrowed keywords -> no row
