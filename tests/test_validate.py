"""U6: parsing validation gate (KTD10) and U7 tag validation scoring."""

import csv

import pytest

from src import db, validate


def add(conn, oid, district, *, division=None, court="calctapp", published=0,
        has_dissent=0, author="DATO", panel=("DATO", "DO", "KELETY"), per_curiam=0):
    conn.execute("INSERT INTO clusters (cl_cluster_id, court, date_filed, docket_number, source) "
                 "VALUES (?, ?, '2023-01-01', ?, 't')", (oid, court, f"X{oid}"))
    conn.execute(
        "INSERT INTO opinions (cl_opinion_id, cl_cluster_id, text, source, district, division, "
        "published, has_dissent, author_raw, per_curiam, parse_status) "
        "VALUES (?, ?, ?, 't', ?, ?, ?, ?, ?, ?, 'ok')",
        (oid, oid, f"Opinion text {oid}", district, division, published, has_dissent,
         None if per_curiam else author, per_curiam))
    for i, name in enumerate(panel):
        role = "author" if (i == 0 and not per_curiam) else "joined"
        conn.execute("INSERT INTO panel_seats (cl_opinion_id, seat_raw, role) VALUES (?, ?, ?)",
                     (oid, name, role))


@pytest.fixture
def populated():
    conn = db.connect(":memory:")
    oid = 1
    for district, count in (("1", 80), ("2", 80), ("3", 40), ("4", 150), ("5", 40), ("6", 40)):
        for k in range(count):
            add(conn, oid, district, division="One" if district in "124" else None,
                published=int(k % 5 == 0), has_dissent=int(k % 9 == 0))
            oid += 1
    for k in range(60):
        add(conn, oid, None, court="cal", published=1, has_dissent=int(k % 4 == 0))
        oid += 1
    return conn


def test_sample_is_seeded_and_meets_strata(populated):
    a = validate.draw_parse_sample(populated, seed=11)
    b = validate.draw_parse_sample(populated, seed=11)
    assert a == b
    rows = {r[0]: r for r in populated.execute(
        "SELECT o.cl_opinion_id, o.district, c.court, o.published, o.has_dissent "
        "FROM opinions o JOIN clusters c USING (cl_cluster_id)")}
    picked = [rows[i] for i in a]
    assert len(picked) >= 200
    assert sum(1 for r in picked if r[1] == "4") >= 60
    assert sum(1 for r in picked if r[2] == "cal") >= 30
    assert sum(1 for r in picked if r[4]) >= 20
    for district in ("1", "2", "3", "5", "6"):
        assert any(r[1] == district for r in picked)
    assert {0, 1} <= {r[3] for r in picked}


def test_packets_contain_no_parser_fields(populated, tmp_path):
    ids = validate.draw_parse_sample(populated, seed=3)[:3]
    validate.export_packets(populated, ids, tmp_path)
    text = (tmp_path / f"{ids[0]}.txt").read_text()
    assert "Opinion text" in text
    for leaked in ("DATO", "author_raw", "parse_status", "has_dissent"):
        assert leaked not in text


def write_labels(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=validate.LABEL_FIELDS)
        w.writeheader()
        w.writerows(rows)


def label(oid, author="DATO", panel="DATO;DO;KELETY", separate="", per_curiam="0"):
    return {"cl_opinion_id": oid, "author": author, "panel": panel, "separate": separate,
            "per_curiam": per_curiam, "notes": "", "owner_ruling": ""}


def test_pooled_gate_passes_with_three_errors_in_210(tmp_path):
    conn = db.connect(":memory:")
    for i in range(1, 211):
        district = "4" if i <= 60 else ("supreme" if i <= 90 else "1")
        add(conn, i, None if district == "supreme" else district,
            court="cal" if district == "supreme" else "calctapp")
    labels = [label(i) for i in range(1, 211)]
    for i in (100, 150, 200):  # three author errors, all outside the 4th District
        labels[i - 1]["author"] = "SOMEONE"
    path = tmp_path / "labels.csv"
    write_labels(path, labels)
    result = validate.score(conn, path)
    assert result["pooled"]["author"]["rate"] == pytest.approx(207 / 210)
    assert result["status"]["pooled"] is True
    assert result["status"]["districts"]["4"] is True


def test_fourth_district_stratum_fails_on_its_own(tmp_path):
    conn = db.connect(":memory:")
    for i in range(1, 211):
        district = "4" if i <= 60 else "1"
        add(conn, i, district)
    labels = [label(i) for i in range(1, 211)]
    for i in (1, 2):  # 2 author errors in 60 > floor(60 * 0.02) = 1 allowed
        labels[i - 1]["author"] = "SOMEONE"
    path = tmp_path / "labels.csv"
    write_labels(path, labels)
    result = validate.score(conn, path)
    assert result["status"]["pooled"] is True
    assert result["status"]["districts"]["4"] is False
    assert result["status"]["districts"]["1"] is True


def test_owner_ruling_for_parser_overrides_label(tmp_path):
    conn = db.connect(":memory:")
    add(conn, 1, "1")
    path = tmp_path / "labels.csv"
    row = label(1, author="WRONG")
    row["owner_ruling"] = "parser"
    write_labels(path, [row])
    assert validate.score(conn, path)["pooled"]["author"]["errors"] == 0


def test_names_compare_ignoring_case_accents_and_apostrophes():
    assert validate.norm_name("O’Rourke") == validate.norm_name("O'ROURKE")
    assert validate.norm_name("Rodríguez") == validate.norm_name("RODRIGUEZ")


def test_tag_precision_and_recall_scoring(tmp_path):
    path = tmp_path / "tags.csv"
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["cl_opinion_id", "sample", "at_issue", "notes"])
        w.writeheader()
        for i in range(50):
            w.writerow({"cl_opinion_id": i, "sample": "precision",
                        "at_issue": "1" if i < 45 else "0", "notes": ""})
        for i in range(50, 90):
            w.writerow({"cl_opinion_id": i, "sample": "recall",
                        "at_issue": "1" if i < 52 else "0", "notes": ""})
    result = validate.score_tags(path)
    assert result["precision"] == pytest.approx(45 / 50)
    assert result["precision_pass"] is True
    assert result["missed_in_untagged"] == 2
    assert result["recall_sample_n"] == 40
