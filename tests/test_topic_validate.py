"""Keyword validation for every topic: sampling, blinding, features, scoring."""

import csv
import json

import pytest

from src import db
from src import topic_validate as tv


def test_draw_excludes_earlier_rounds_and_never_overlaps():
    prec, probe = tv.draw(list(range(100)), list(range(50, 200)), seed=3, exclude={1, 2, 3},
                          precision_n=50, probe_n=30)
    assert len(prec) == 50 and len(probe) == 30
    assert not {1, 2, 3} & set(prec) and not set(prec) & set(probe)


def test_draw_takes_what_exists_when_pool_is_small():
    prec, probe = tv.draw([1, 2], [], seed=1, exclude=set())
    assert prec == [1, 2] and probe == []


def test_anchor_features_count_distinct_and_occurrences_with_prefixes():
    spec = {"anchors": ["arbitration agreement", "unconscionab"], "prefix_terms": ["unconscionab"]}
    text = ("The Arbitration Agreement was unconscionable. Unconscionability... "
            "arbitration agreements")
    # "arbitration agreements" is not a whole-word match; the stem matches both forms.
    assert tv.anchor_features(text, spec) == (2, 3)


def test_probes_match_word_starts_only():
    conn = db.connect(":memory:")
    texts = {1: "The tenant appealed.", 2: "Lieutenant Smith testified.",
             3: "We release the funds.", 4: "The lease was void.", 5: "Interrogations began."}
    for oid, text in texts.items():
        conn.execute("INSERT INTO clusters (cl_cluster_id, court, date_filed, docket_number, "
                     "source) VALUES (?, 'calctapp', '2023-01-01', 'X', 't')", (oid,))
        conn.execute("INSERT INTO opinions (cl_opinion_id, cl_cluster_id, text, source) "
                     "VALUES (?, ?, ?, 't')", (oid, oid, text))
    assert tv.probe_ids(conn, "t", ["tenant", "lease", "interrogat"], "2020-01-01") == [1, 4, 5]
    # A keyword hit below a tightened rule counts as a near miss; a tagged opinion never does.
    conn.execute("INSERT INTO topic_tags (cl_opinion_id, topic, anchor_hits, broad_hits, tagged, "
                 "queue_match) VALUES (2, 't', 1, 0, 0, 1), (1, 't', 3, 0, 1, 1)")
    assert tv.probe_ids(conn, "t", ["tenant", "lease", "interrogat"], "2020-01-01") == [2, 4, 5]


def test_write_round_keeps_the_key_out_of_the_labeler_folder(tmp_path):
    conn = db.connect(":memory:")
    for oid in (1, 2, 3):
        conn.execute("INSERT INTO clusters (cl_cluster_id, court, date_filed, docket_number, "
                     "source) VALUES (?, 'calctapp', '2023-01-01', 'X', 't')", (oid,))
        conn.execute("INSERT INTO opinions (cl_opinion_id, cl_cluster_id, text, source) "
                     "VALUES (?, ?, ?, 't')", (oid, oid, f"text {oid}"))
    folder, key = tmp_path / "labeler", tmp_path / "keys" / "k.json"
    tv.write_round(conn, folder, key, [1, 2], [3], seed=5,
                   meta={"topic": "t", "round": "r1", "rule": "any anchor", "tagged": 2,
                         "probe_pool": 1})
    with open(folder / "labels_raw.csv") as fh:
        rows = list(csv.DictReader(fh))
    assert sorted(int(r["cl_opinion_id"]) for r in rows) == [1, 2, 3]
    assert set(rows[0]) == {"cl_opinion_id", "at_issue", "notes"}
    assert not list(folder.rglob("*.json"))
    assert json.loads(key.read_text())["sample"] == {"1": "precision", "2": "precision",
                                                    "3": "probe"}


def test_score_round_precision_and_undercount():
    key = {"round": "r1", "rule": "any anchor", "tagged": 100, "probe_pool": 200,
           "sample": {"1": "precision", "2": "precision", "3": "probe", "4": "probe"}}
    labels = [{"cl_opinion_id": "1", "at_issue": "1"}, {"cl_opinion_id": "2", "at_issue": "0"},
              {"cl_opinion_id": "3", "at_issue": "1"}, {"cl_opinion_id": "4", "at_issue": "0"}]
    s = tv.score_round(labels, key, {})["summary"]
    assert s["precision"] == 0.5 and not s["precision_pass"]
    assert s["est_missed"] == 100            # half of a 200-opinion near-miss pool
    assert s["undercount_share"] == 100 / (50 + 100)


def test_score_round_rejects_blank_labels():
    key = {"round": "r1", "rule": "x", "tagged": 1, "probe_pool": 0, "sample": {"1": "precision"}}
    with pytest.raises(ValueError, match="opinion 1"):
        tv.score_round([{"cl_opinion_id": "1", "at_issue": ""}], key, {})
