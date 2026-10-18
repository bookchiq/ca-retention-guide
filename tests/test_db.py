import sqlite3

from src import db


def test_connect_adds_columns_missing_from_an_older_database(tmp_path):
    path = tmp_path / "old.sqlite"
    old = sqlite3.connect(path)
    old.execute(
        "CREATE TABLE opinions (cl_opinion_id INTEGER PRIMARY KEY, cl_cluster_id INTEGER, "
        "text_hash TEXT)"
    )
    old.execute(
        "CREATE TABLE panel_seats (cl_opinion_id INTEGER, seat_raw TEXT, slug TEXT, role TEXT)"
    )
    old.commit()
    old.close()
    conn = db.connect(path)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(opinions)")}
    assert {"disposition_class", "docket_number_text"} <= cols
    seat_cols = {r[1] for r in conn.execute("PRAGMA table_info(panel_seats)")}
    assert {"title", "assignment_note"} <= seat_cols
