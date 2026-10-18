"""U4: fetching the post-snapshot gap through the API into SQLite."""

from src import db, fetch, textutil
from tests.test_cl_api import FakeClock, FakeResponse, FakeSession, make_settings


def run_api_fetch(tmp_path, responses, conn=None):
    conn = conn or db.connect(":memory:")
    clock = FakeClock()
    client = fetch.cl_api.Client(
        make_settings(tmp_path, interval=0), conn, session=FakeSession(responses),
        now=clock.time, sleep=clock.sleep,
    )
    fetch.fetch_api_gap(client, conn, court="calctapp", since="2026-10-01")
    return conn


CLUSTERS = {
    "results": [
        {
            "id": 501,
            "docket_id": 9001,
            "case_name": "People v. Doe",
            "date_filed": "2026-10-05",
            "precedential_status": "Unpublished",
            "absolute_url": "/opinion/501/people-v-doe/",
        }
    ],
    "next": None,
}
OPINIONS = {
    "results": [
        {
            "id": 7001,
            "cluster_id": 501,
            "type": "010combined",
            "plain_text": "",
            "html_with_citations": "<p>THE PEOPLE,</p><p>Plaintiff &amp; Respondent.</p>",
        }
    ],
    "next": None,
}


def test_api_gap_stores_clusters_and_opinions(tmp_path):
    conn = run_api_fetch(tmp_path, [FakeResponse(200, CLUSTERS), FakeResponse(200, OPINIONS)])
    cluster = conn.execute("SELECT * FROM clusters WHERE cl_cluster_id = 501").fetchone()
    assert cluster["court"] == "calctapp"
    assert cluster["source"] == "api"
    assert cluster["case_name"] == "People v. Doe"
    op = conn.execute("SELECT * FROM opinions WHERE cl_opinion_id = 7001").fetchone()
    assert op["text"] == "THE PEOPLE,\n\nPlaintiff & Respondent."
    assert op["text_field_used"] == "html_with_citations"
    assert op["source"] == "api"


def test_api_opinion_matching_bulk_hash_is_not_duplicated(tmp_path):
    conn = db.connect(":memory:")
    text = "THE PEOPLE,\nPlaintiff & Respondent."
    conn.execute(
        "INSERT INTO opinions (cl_opinion_id, cl_cluster_id, text, text_hash, source) "
        "VALUES (?, ?, ?, ?, ?)",
        (6000, 400, text, textutil.text_hash(text), "bulk-2026-09-30"),
    )
    run_api_fetch(tmp_path, [FakeResponse(200, CLUSTERS), FakeResponse(200, OPINIONS)], conn)
    count = conn.execute("SELECT COUNT(*) FROM opinions").fetchone()[0]
    assert count == 1


def test_choose_text_prefers_plain_text():
    text, field = textutil.choose_text({"plain_text": " A ", "html_with_citations": "<p>B</p>"})
    assert (text, field) == ("A", "plain_text")
