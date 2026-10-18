"""U3: bulk snapshot filtering, resume, and coverage report."""

import bz2
import csv
from pathlib import Path

from src import bulk, coverage, db

FIXTURES = Path(__file__).parent / "fixtures" / "bulk"


def write_pg_csv(path, header, rows):
    """Write rows the way PostgreSQL exports them: all quoted, backslash escapes."""
    with bz2.open(path, "wt", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, dialect=bulk.PostgresCSV, quoting=csv.QUOTE_ALL)
        writer.writerow(header)
        writer.writerows(rows)


def test_real_cluster_rows_parse_with_escaped_quotes():
    rows = list(bulk.read_rows(FIXTURES / "clusters_head.csv.bz2"))
    assert len(rows) == 5
    assert all(row["id"].isdigit() and row["docket_id"].isdigit() for row in rows)
    text = " ".join(" ".join(r.values()) for r in rows)
    assert '\\"' not in text


def test_real_opinion_rows_keep_multiline_text_with_escaped_quotes():
    rows = list(bulk.read_rows(FIXTURES / "opinions_head.csv.bz2"))
    assert len(rows) == 3
    assert all(row["cluster_id"].isdigit() for row in rows)
    harvard = rows[0]["xml_harvard"]
    assert '<opinion type="majority">' in harvard
    assert "\n" in harvard


DOCKET_HEADER = ["id", "court_id", "docket_number", "case_name"]
CLUSTER_HEADER = ["id", "docket_id", "date_filed", "case_name", "precedential_status", "slug"]
OPINION_HEADER = ["id", "cluster_id", "type", "plain_text", "html_with_citations"]


def build_snapshot(tmp_path):
    write_pg_csv(tmp_path / "dockets.csv.bz2", DOCKET_HEADER, [
        ["1", "calctapp", "D081234", "People v. A"],
        ["2", "cal", "S270000", "People v. B"],
        ["3", "cand", "3:20-cv-1", "Fed v. C"],
        ["4", "calctapp", "G060000", "People v. D"],
    ])
    write_pg_csv(tmp_path / "clusters.csv.bz2", CLUSTER_HEADER, [
        ["10", "1", "2021-03-01", "People v. A", "Unpublished", "people-v-a"],
        ["20", "2", "2019-12-31", "People v. B", "Published", "people-v-b"],
        ["30", "3", "2021-01-01", "Fed v. C", "Published", "fed-v-c"],
        ["40", "4", "2019-12-31", "People v. D", "Published", "people-v-d"],
    ])
    long_text = 'THE PEOPLE,\nPlaintiff and Respondent,\nv.\n"QUOTED" DEFENDANT.\n'
    write_pg_csv(tmp_path / "opinions.csv.bz2", OPINION_HEADER, [
        ["100", "10", "010combined", long_text, ""],
        ["200", "20", "020lead", "Supreme opinion text", ""],
        ["300", "30", "010combined", "federal text", ""],
        ["400", "40", "010combined", "too early", ""],
        ["101", "10", "040dissent", "", "<p>I respectfully dissent.</p>"],
    ])


def load_all(conn, tmp_path):
    starts = {"calctapp": "2020-01-01", "cal": "2019-01-01"}
    bulk.load_dockets(conn, tmp_path / "dockets.csv.bz2", {"calctapp", "cal"})
    bulk.load_clusters(conn, tmp_path / "clusters.csv.bz2", starts, "bulk-test")
    return bulk.load_opinions(conn, tmp_path / "opinions.csv.bz2", "bulk-test")


def test_filter_chain_keeps_only_california_courts_in_window(tmp_path):
    build_snapshot(tmp_path)
    conn = db.connect(":memory:")
    added = load_all(conn, tmp_path)
    assert added == 3
    clusters = {r[0] for r in conn.execute("SELECT cl_cluster_id FROM clusters")}
    assert clusters == {10, 20}  # cand dropped; 2019-12-31 kept for cal, dropped for calctapp
    ops = {r[0]: r for r in conn.execute("SELECT cl_opinion_id, text, docket_number FROM "
                                         "opinions JOIN clusters USING (cl_cluster_id)")}
    assert set(ops) == {100, 101, 200}
    assert '"QUOTED" DEFENDANT.' in ops[100]["text"]
    assert ops[100]["docket_number"] == "D081234"


def test_rerun_of_completed_load_writes_nothing(tmp_path):
    build_snapshot(tmp_path)
    conn = db.connect(":memory:")
    load_all(conn, tmp_path)
    assert load_all(conn, tmp_path) == 0
    assert conn.execute("SELECT COUNT(*) FROM opinions").fetchone()[0] == 3


def test_interrupted_opinions_pass_resumes_without_duplicates(tmp_path):
    build_snapshot(tmp_path)
    conn = db.connect(":memory:")
    starts = {"calctapp": "2020-01-01", "cal": "2019-01-01"}
    bulk.load_dockets(conn, tmp_path / "dockets.csv.bz2", {"calctapp", "cal"})
    bulk.load_clusters(conn, tmp_path / "clusters.csv.bz2", starts, "bulk-test")
    # Simulate a crash after the first two rows were committed.
    db.insert_opinion(conn, 100, 10, "010combined",
                      'THE PEOPLE,\nPlaintiff and Respondent,\nv.\n"QUOTED" DEFENDANT.',
                      "plain_text", "bulk-test")
    db.insert_opinion(conn, 200, 20, "020lead", "Supreme opinion text", "plain_text", "bulk-test")
    conn.execute("INSERT INTO bulk_checkpoints VALUES ('opinions:opinions.csv.bz2', 2, 0)")
    conn.commit()
    added = bulk.load_opinions(conn, tmp_path / "opinions.csv.bz2", "bulk-test")
    assert added == 1
    assert conn.execute("SELECT COUNT(*) FROM opinions").fetchone()[0] == 3


def test_coverage_report_flags_thin_year_and_projects_workload(tmp_path):
    conn = db.connect(":memory:")
    rows = [(i, "calctapp", "D0", "2021-05-01", "Unpublished") for i in range(1, 701)]
    rows += [(i, "calctapp", "D0", "2023-05-01", "Unpublished") for i in range(701, 7801)]
    conn.executemany(
        "INSERT INTO clusters (cl_cluster_id, court, docket_number, date_filed, "
        "precedential_status, source) VALUES (?, ?, ?, ?, ?, 'test')", rows,
    )
    conn.executemany(
        "INSERT INTO opinions (cl_opinion_id, cl_cluster_id, text, source) VALUES (?, ?, ?, 't')",
        [(i, i, "motion to suppress" if i % 100 == 0 else "other") for i in range(1, 7801)],
    )
    report = coverage.build_report(conn, expected_per_year=7000, window_options=["2020-01-01",
                                                                                 "2023-01-01"])
    assert "| 2021 |" in report
    assert "LOW" in report.split("| 2021 |")[1].splitlines()[0]
    assert "LOW" not in report.split("| 2023 |")[1].splitlines()[0]
    assert "2020-01-01" in report and "2023-01-01" in report


def test_latest_year_is_marked_partial_not_low(tmp_path):
    conn = db.connect(":memory:")
    conn.executemany(
        "INSERT INTO clusters (cl_cluster_id, court, docket_number, date_filed, "
        "precedential_status, source) VALUES (?, 'calctapp', 'D0', ?, 'Published', 't')",
        [(1, "2025-06-01"), (2, "2026-10-14")],
    )
    report = coverage.build_report(conn, expected_per_year=7000, window_options=["2020-01-01"])
    row_2026 = report.split("| 2026 |")[1].splitlines()[0]
    assert "partial year through 2026-10-14" in row_2026 and "LOW" not in row_2026
    assert "LOW" in report.split("| 2025 |")[1].splitlines()[0]
