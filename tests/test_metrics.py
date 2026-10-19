"""U8: per-justice metrics with pooled division baselines (KTD5)."""

import pytest

from src import db, metrics
from src.justices import PartialDate, ServicePeriod


def period(slug, start, end=None, district="4", division="One", court="appeal"):
    return ServicePeriod(
        slug=slug, court=court, district=district, division=division, title="J.",
        start=PartialDate.parse(start), end=PartialDate.parse(end) if end else None,
        source_url="https://example.org",
    )


def add(conn, oid, *, author, joined=(), published=0, date="2023-03-01", district="4",
        division="One", court="calctapp", per_curiam=0, dissent_by=None, concur_by=None,
        topics=()):
    conn.execute(
        "INSERT INTO clusters (cl_cluster_id, court, date_filed, source) "
        "VALUES (?, ?, ?, 't')", (oid, court, date))
    conn.execute(
        "INSERT INTO opinions (cl_opinion_id, cl_cluster_id, source, district, division, "
        "published, per_curiam, author_slug, has_dissent, parse_status) "
        "VALUES (?, ?, 't', ?, ?, ?, ?, ?, ?, 'ok')",
        (oid, oid, district, division, published, per_curiam, author,
         int(dissent_by is not None)))
    seats = ([] if author is None else [(author, "author")]) + [(j, "joined") for j in joined]
    for slug, role in seats:
        conn.execute("INSERT INTO panel_seats (cl_opinion_id, seat_raw, slug, role) "
                     "VALUES (?, ?, ?, ?)", (oid, slug, slug, role))
    if dissent_by:
        conn.execute("INSERT INTO separate_opinions (cl_opinion_id, type, partial, author_slug) "
                     "VALUES (?, 'dissent', 0, ?)", (oid, dissent_by))
        conn.execute("INSERT INTO panel_seats (cl_opinion_id, seat_raw, slug, role) "
                     "VALUES (?, ?, ?, 'joined')", (oid, dissent_by, dissent_by))
    if concur_by:
        conn.execute("INSERT INTO separate_opinions (cl_opinion_id, type, partial, author_slug) "
                     "VALUES (?, 'concurrence', 0, ?)", (oid, concur_by))
    for t in topics:
        conn.execute("INSERT INTO topic_tags VALUES (?, ?, 1, 0, 1, 1)", (oid, t))


@pytest.fixture
def conn():
    return db.connect(":memory:")


def get(rows, slug, metric, topic=""):
    for r in rows:
        if r["slug"] == slug and r["metric"] == metric and r["topic"] == topic:
            return r
    raise KeyError((slug, metric, topic))


def compute(conn, periods, limited=()):
    return metrics.compute(conn, periods, window_start="2020-01-01", window_end="2026-10-27",
                           limited=set(limited), validated_districts={"4", "supreme"})


def test_publication_rate_and_pooled_baseline(conn):
    for i in range(1, 5):
        add(conn, i, author="dato", joined=("do", "kelety"), published=int(i == 1))
    for i in range(5, 11):
        add(conn, i, author="do", joined=("dato", "kelety"), published=int(i <= 7))
    rows = compute(conn, [period("dato", "2017-02"), period("do", "2021-01-14"),
                          period("kelety", "2023-01-01")])
    r = get(rows, "dato", "publication_rate")
    assert r["value"] == pytest.approx(0.25)
    assert r["baseline"] == pytest.approx(4 / 10)
    assert r["baseline_n"] == 10


def test_division_change_is_time_sliced(conn):
    add(conn, 1, author="x", division="One", date="2021-06-01", published=1)
    add(conn, 2, author="y", division="Three", date="2021-06-01", published=0)
    add(conn, 3, author="mover", division="One", date="2021-03-01", published=1)
    add(conn, 4, author="mover", division="Three", date="2023-03-01", published=0)
    add(conn, 5, author="y", division="Three", date="2023-06-01", published=1)
    periods = [
        period("mover", "2020-01-01", "2022-01-01", division="One"),
        period("mover", "2022-01-01", division="Three"),
        period("x", "2015-01-01"), period("y", "2015-01-01", division="Three"),
    ]
    r = get(compute(conn, periods), "mover", "publication_rate")
    # Division One in 2020-2021 (ops 1, 3) plus Division Three from 2022 (ops 4, 5);
    # op 2 (Division Three, 2021) is outside both slices. Published: 1, 3, 5.
    assert r["baseline_n"] == 4
    assert r["baseline"] == pytest.approx(3 / 4)
    assert r["value"] == pytest.approx(1 / 2)


def test_per_curiam_counts_panel_seats_not_authorship(conn):
    add(conn, 1, author=None, joined=("dato", "do", "kelety"), per_curiam=1)
    rows = compute(conn, [period(s, "2020-01-01") for s in ("dato", "do", "kelety")])
    assert get(rows, "dato", "panels")["value"] == 1
    assert get(rows, "dato", "authored_total")["value"] == 0


def test_assigned_trial_judge_counts_in_baseline_denominator(conn):
    add(conn, 1, author="dato", joined=("do",))
    conn.execute("INSERT INTO panel_seats (cl_opinion_id, seat_raw, slug, role, assigned) "
                 "VALUES (1, 'CLAY', NULL, 'joined', 1)")
    add(conn, 2, author="do", joined=("dato",), dissent_by="kelety")
    rows = compute(conn, [period(s, "2020-01-01") for s in ("dato", "do", "kelety")])
    r = get(rows, "kelety", "dissents_per_100_panels")
    # 1 dissent across 6 panel seats in the division (3 per opinion, incl. assigned judge)
    assert r["baseline"] == pytest.approx(100 * 1 / 6)


def test_window_starts_at_justice_start(conn):
    add(conn, 1, author="kelety", date="2021-01-01", published=1)
    add(conn, 2, author="dato", date="2023-06-01", published=0)
    add(conn, 3, author="dato", date="2023-07-01", published=1)
    rows = compute(conn, [period("kelety", "2023-04-07"), period("dato", "2017-02")])
    r = get(rows, "kelety", "publication_rate")
    assert r["baseline_n"] == 2  # only opinions filed after 2023-04-07
    assert r["window_start"] == "2023-04-07"


def test_supreme_court_has_no_publication_rate(conn):
    add(conn, 1, author="joshua-groban", joined=("kelli-m-evans",), court="cal",
        district=None, division=None, published=1)
    periods = [period("joshua-groban", "2019-01-03", court="supreme", district=None,
                      division=None),
               period("kelli-m-evans", "2023-01-02", court="supreme", district=None,
                      division=None)]
    rows = compute(conn, periods)
    assert all(r["metric"] != "publication_rate" for r in rows if r["slug"] == "joshua-groban")
    assert get(rows, "joshua-groban", "authored_total")["value"] == 1


def test_limited_record_justice_gets_counts_but_no_rates(conn):
    add(conn, 1, author="newbie", published=1, date="2026-06-01")
    rows = compute(conn, [period("newbie", "2026-05-22")], limited={"newbie"})
    assert get(rows, "newbie", "authored_total")["value"] == 1
    r = get(rows, "newbie", "publication_rate")
    assert r["value"] is None and "limited" in r["note"]


def test_topic_counts_and_contested_votes(conn):
    add(conn, 1, author="dato", joined=("do",), topics=("search_seizure",), dissent_by="kelety")
    add(conn, 2, author="do", joined=("dato", "kelety"), topics=("search_seizure",))
    rows = compute(conn, [period(s, "2020-01-01") for s in ("dato", "do", "kelety")])
    assert get(rows, "dato", "topic_authored", "search_seizure")["value"] == 1
    assert get(rows, "dato", "topic_panels", "search_seizure")["value"] == 2
    assert get(rows, "dato", "contested_majority", "search_seizure")["value"] == 1
    assert get(rows, "kelety", "contested_dissent", "search_seizure")["value"] == 1


def test_unvalidated_district_is_skipped(conn):
    add(conn, 1, author="h1", district="6", division=None)
    rows = metrics.compute(conn, [period("h1", "2020-01-01", district="6", division=None)],
                           window_start="2020-01-01", window_end="2026-10-27", limited=set(),
                           validated_districts={"4"})
    assert all(r["slug"] != "h1" for r in rows)
