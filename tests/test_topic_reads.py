"""Reading-based topic coverage: pools, second-read draw, merging, agreement, applying."""

import csv

import pytest

from src import db
from src import topic_reads as tr


def seed(conn, oid, slug, anchors=1, date="2023-01-01"):
    conn.execute("INSERT INTO clusters (cl_cluster_id, court, date_filed, docket_number, source) "
                 "VALUES (?, 'calctapp', ?, 'X', 't')", (oid, date))
    conn.execute("INSERT INTO opinions (cl_opinion_id, cl_cluster_id, text, source) "
                 "VALUES (?, ?, 'text', 't')", (oid, oid))
    conn.execute("INSERT INTO panel_seats (cl_opinion_id, seat_raw, role, slug) "
                 "VALUES (?, 'X', 'author', ?)", (oid, slug))
    conn.execute("INSERT INTO topic_tags (cl_opinion_id, topic, anchor_hits, broad_hits, tagged, "
                 "queue_match) VALUES (?, 'emp', ?, 0, ?, 1)", (oid, anchors, int(anchors > 0)))


def test_pool_needs_an_anchor_a_ballot_justice_and_the_window():
    conn = db.connect(":memory:")
    seed(conn, 1, "dato")
    seed(conn, 2, "not-on-ballot")
    seed(conn, 3, "dato", anchors=0)
    seed(conn, 4, "dato", date="2019-06-01")
    assert tr.pool(conn, "emp", "2020-01-01", {"dato"}) == [1]


def test_second_read_draws_fifteen_percent_minimum_one():
    assert len(tr.draw_second(list(range(100)), seed=1)) == 15
    assert len(tr.draw_second([5], seed=1)) == 1
    assert tr.draw_second([], seed=1) == []


def test_merge_uses_tiebreak_only_for_disagreements():
    first = {1: ("1", "a"), 2: ("0", "b"), 3: ("1", "c")}
    second = {2: ("0", "b2"), 3: ("0", "c2")}
    tie = {3: ("0", "c3")}
    rows = {r["cl_opinion_id"]: r for r in tr.merge(first, second, tie)}
    assert rows[1]["final"] == "1" and rows[2]["final"] == "0" and rows[3]["final"] == "0"
    s = tr.summary(list(rows.values()), pool_size=3)
    assert s["agreement"] == 0.5 and s["disagreements"] == 1 and s["unresolved"] == 0
    assert not s["agreement_pass"]


def test_unresolved_disagreement_blocks_the_topic():
    rows = tr.merge({1: ("1", "")}, {1: ("0", "")}, {})
    assert rows[0]["final"] == ""
    assert tr.summary(rows, 1)["unresolved"] == 1


def test_merge_rejects_missing_first_reads():
    with pytest.raises(ValueError, match="opinion 9"):
        tr.merge({9: ("", "")}, {}, {})


def test_apply_overrides_tags_for_read_topics_only(tmp_path):
    conn = db.connect(":memory:")
    seed(conn, 1, "dato")
    seed(conn, 2, "dato")
    with open(tmp_path / "emp.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=tr.FIELDS)
        w.writeheader()
        w.writerow(dict.fromkeys(tr.FIELDS, "") | {"cl_opinion_id": 1, "final": "0"})
        w.writerow(dict.fromkeys(tr.FIELDS, "") | {"cl_opinion_id": 2, "final": "1"})
    assert tr.apply(conn, {"emp": {"method": "keywords"}}, tmp_path) == {}
    assert tr.apply(conn, {"emp": {"method": "read"}}, tmp_path) == {"emp": 1}
    tagged = dict(conn.execute("SELECT cl_opinion_id, tagged FROM topic_tags").fetchall())
    assert tagged == {1: 0, 2: 1}
