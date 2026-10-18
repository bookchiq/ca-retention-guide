"""Opinion parsing against real opinion texts (tests/fixtures/opinions/).

Each fixture is a public-domain opinion as stored in data/cases.sqlite, with our
metadata (cluster docket number, filing date, CourtListener status) above "----".
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src import db, parse

FIXTURES = Path(__file__).parent / "fixtures" / "opinions"


def load(name: str) -> tuple[dict, str]:
    raw = (FIXTURES / f"{name}.txt").read_text()
    head, _, text = raw.partition("\n----\n")
    meta = dict(line.split(": ", 1) for line in head.splitlines())
    return meta, text


def run(name: str, text: str | None = None) -> parse.ParseResult:
    meta, body = load(name)
    return parse.parse_opinion(
        body if text is None else text,
        court="cal" if meta["docket"].startswith("S") else "calctapp",
        docket_number=meta["docket"],
        date_filed=meta["date"],
        precedential_status=meta["status"],
    )


def seats(result: parse.ParseResult) -> list[tuple[str, str | None, str]]:
    return [(s.surname, s.slug, s.role) for s in result.seats]


# --- Court of Appeal signatures -------------------------------------------------


def test_author_then_we_concur_gives_three_member_panel():
    r = run("D_11171775")  # RUBIN, J. / WE CONCUR: IRION, Acting P. J. / DATO, J.
    assert (r.author_raw, r.author_slug, r.per_curiam) == ("RUBIN, J.", "david-m-rubin", False)
    assert seats(r) == [
        ("RUBIN", "david-m-rubin", "author"),
        ("IRION", "joan-k-irion", "joined"),
        ("DATO", "william-s-dato", "joined"),
    ]
    assert [s.title for s in r.seats] == ["J.", "Acting P. J.", "J."]
    assert (r.district, r.division, r.parse_status) == ("4", "One", "ok")


def test_mixed_case_and_curly_apostrophe_resolve_to_non_ballot_slugs():
    assert ("McCONNELL", "judith-mcconnell", "joined") in seats(run("D_11171767"))
    assert ("O'ROURKE", "terry-b-orourke", "joined") in seats(run("D_11171770"))


def test_compound_surname_signature():
    r = run("C_11171777")
    assert (r.author_raw, r.author_slug) == ("BOULWARE EURIE, J.", "stacy-boulware-eurie")
    assert (r.district, r.division) == ("3", None)


def test_title_case_signatures_with_signature_rules():
    r = run("A_11171838")  # Miller, J. / Stewart, P. J. / Richman, J.
    assert seats(r) == [
        ("Miller", "marla-j-miller", "author"),
        ("Stewart", "therese-m-stewart", "joined"),
        ("Richman", "james-a-richman", "joined"),
    ]


def test_name_and_title_on_separate_lines():
    r = run("E_6333314")  # RAPHAEL / J.  We concur: RAMIREZ / P. J.  MENETREZ / J.
    assert seats(r) == [
        ("RAPHAEL", "michael-j-raphael", "author"),
        ("RAMIREZ", "manuel-a-ramirez", "joined"),
        ("MENETREZ", "frank-j-menetrez", "joined"),
    ]
    assert r.seats[1].title == "P. J."


def test_split_lines_with_mixed_case_name_and_acting_title():
    r = run("E_11171655")  # RAPHAEL / J.  We concur: McKINSTER / Acting P. J.  FIELDS / J.
    assert seats(r) == [
        ("RAPHAEL", "michael-j-raphael", "author"),
        ("McKINSTER", "art-w-mckinster", "joined"),
        ("FIELDS", "richard-t-fields", "joined"),
    ]


def test_signature_with_first_initial():
    r = run("B_11264490")  # BENDIX, Acting P. J.          M. KIM, J.
    assert ("M. KIM", "michelle-c-kim", "joined") in seats(r)


def test_we_concur_with_a_period():
    r = run("A_11225082")  # SIMONS, J. / We concur. / JACKSON, P. J. / CHOU, J.
    assert [(x.surname, x.role) for x in r.seats] == [
        ("SIMONS", "author"), ("JACKSON", "joined"), ("CHOU", "joined"),
    ]
    assert r.author_slug == "mark-simons"


def test_signature_with_space_before_comma():
    r = run("C_9326020")  # "KRAUSE                 , J."
    assert seats(r) == [
        ("KRAUSE", "peter-a-krause", "author"),
        ("ROBIE", "ronald-b-robie", "joined"),
        ("BOULWARE EURIE", "stacy-boulware-eurie", "joined"),
    ]


def test_acting_comma_title_and_assigned_trial_judge_on_same_line():
    r = run("B_4880872")  # STRATTON, Acting, P. J. / WILEY, J.     OHTA, J.*
    assert [(x.surname, x.title, x.role) for x in r.seats] == [
        ("STRATTON", "Acting P. J.", "author"),
        ("WILEY", "J.", "joined"),
        ("OHTA", "J.", "joined"),
    ]
    assert r.seats[2].resolution == "trial_judge"


def test_parenthesized_initial_distinguishes_same_surname():
    r = run("B_11392803")  # KIM (D.), J. in 2nd District Division Five
    assert r.seats[0].surname == "D. KIM"
    assert r.author_slug == "dorothy-c-kim"


def test_per_curiam_star_after_colon_and_before_comma():
    r = run("G_4590573")  # THE COURT:*  / * Before, O'Leary, P.J., Ikola, J., and Thompson, J.
    assert r.per_curiam is True
    assert seats(r) == [
        ("O'Leary", "kathleen-e-oleary", "joined"),
        ("Ikola", "raymond-j-ikola", "joined"),
        ("Thompson", "david-a-thompson", "joined"),
    ]


def test_symbol_font_asterisk_marks_an_assigned_author():
    r = run("A_6344493")  # "EAST, J.\uf02a" -- Judge of the San Francisco Superior Court
    author = r.seats[0]
    assert (author.surname, author.assigned, author.resolution) == ("EAST", True, "trial_judge")
    [sep] = r.separate_opinions  # DISSENTING OPINION OF BANKE, J.
    assert (sep.type, sep.slug) == ("dissent", "kathleen-m-banke")


def test_title_without_final_period():
    r = run("A_11221363")  # "PETROU, J"
    assert r.author_slug == "ioana-petrou"


def test_footnote_between_author_and_we_concur():
    r = run("A_9349311")  # GOLDMAN, J. / "7 People v. Marsden ..." / 24 / WE CONCUR:
    assert [(x.surname, x.role) for x in r.seats] == [
        ("GOLDMAN", "author"), ("STREETER", "joined"), ("BROWN", "joined"),
    ]


def test_space_before_star_and_semicolon_marker():
    r = run("A_9969508")  # "HITE, J. *" -- Judge of the Superior Court ... San Francisco
    assert (r.seats[0].surname, r.seats[0].resolution) == ("HITE", "trial_judge")
    r = run("B_9365330")  # LUI, P. J. / We concur;
    assert [x.surname for x in r.seats] == ["LUI", "ASHMANN-GERST", "CHAVEZ"]


def test_dagger_footnote_marks_assigned_trial_judge_not_the_later_ballot_justice():
    # GUERRA, J.† in 2025 is a Fresno trial judge; ballot justice Amy K. Guerra
    # joined the Fifth District only in 2026.
    r = run("F_11211533")
    author = r.seats[0]
    assert (author.surname, author.assigned, author.slug, author.resolution) == (
        "GUERRA", True, None, "trial_judge",
    )


def test_signature_without_comma():
    r = run("F_6316780")  # "DE SANTOS J." / FRANSON, ACTING P. J. / PEÑA, J.
    assert seats(r) == [
        ("DE SANTOS", "thomas-desantos", "author"),
        ("FRANSON", "donald-r-franson-jr", "joined"),
        ("PEÑA", "rosendo-pena-jr", "joined"),
    ]
    assert r.seats[1].title == "Acting P. J."


def test_title_above_name_signature_shape():
    r = run("B_4652857")  # "_____, J." then "HOFFSTADT" on the next line
    assert ("HOFFSTADT", "brian-m-hoffstadt", "joined") in seats(r)


def test_assigned_trial_judge_is_an_assigned_seat_with_no_slug():
    r = run("A_11171776")  # CLAY, J.* -- Judge of the Alameda Superior Court
    author = r.seats[0]
    assert (author.surname, author.role, author.assigned, author.slug) == (
        "CLAY", "author", True, None,
    )
    assert "Alameda Superior Court" in author.assignment_note
    assert author.resolution == "trial_judge"
    assert r.author_slug is None
    assert r.parse_status == "ok"  # a trial judge is identified, not unresolved


def test_two_joiners_on_one_line_and_retired_justice_collision():
    r = run("B_11171774")  # VIRAMONTES, J.      RUBIN, J.*  (retired 2nd District PJ)
    assert seats(r) == [
        ("STRATTON", "maria-e-stratton", "author"),
        ("VIRAMONTES", "victor-g-viramontes", "joined"),
        ("RUBIN", None, "joined"),
    ]
    rubin = r.seats[2]
    assert rubin.assigned and rubin.resolution == "retired_justice"
    assert "Retired Presiding Justice" in rubin.assignment_note


def test_the_court_is_per_curiam_with_panel_from_footnote():
    r = run("F_11171780")  # THE COURT* / * Before Levy, Acting P. J., Detjen, J. and Peña, J.
    assert r.per_curiam is True
    assert r.author_raw is None and r.author_slug is None
    assert seats(r) == [
        ("Levy", "bert-levy", "joined"),
        ("Detjen", "jennifer-rs-detjen", "joined"),
        ("Peña", "rosendo-pena-jr", "joined"),
    ]
    assert r.parse_status == "ok"


def test_per_curiam_panel_listed_at_the_end():
    r = run("B_4651666")  # THE COURT: ... ASHMANN-GERST, Acting P. J., CHAVEZ, J., HOFFSTADT, J.
    assert r.per_curiam is True
    assert seats(r) == [
        ("ASHMANN-GERST", "judith-ashmann-gerst", "joined"),
        ("CHAVEZ", "victoria-m-chavez", "joined"),
        ("HOFFSTADT", "brian-m-hoffstadt", "joined"),
    ]


def test_asterisk_operator_marks_an_assigned_author():
    r = run("C_9410897")  # "HORST, J. \u2217" -- Judge of the Placer County Superior Court
    assert (r.seats[0].surname, r.seats[0].resolution) == ("HORST", "trial_judge")
    assert r.per_curiam is False


def test_order_modifying_per_curiam_does_not_override_signed_opinion():
    r = run("A_11171846")  # THE COURT* order on top, opinion signed by TUCHER below
    assert r.per_curiam is False
    assert r.author_slug == "alison-m-tucher"


def test_supreme_court_statement_appended_to_court_of_appeal_opinion_is_ignored():
    r = run("H_11171800")  # Evans, J., dissenting statement upon denial of review
    assert r.author_slug == "mary-j-greenwood"
    assert r.has_dissent is False
    assert r.separate_opinions == []


# --- Separate opinions ----------------------------------------------------------


def test_dissent_heading_with_name_attributes_to_that_justice():
    r = run("D_4639750")  # O'Rourke, J., dissenting.
    assert r.has_dissent is True
    [sep] = r.separate_opinions
    assert (sep.type, sep.partial, sep.slug) == ("dissent", False, "terry-b-orourke")
    # The dissenter sat on the panel even though not listed under "I CONCUR".
    assert ("O'ROURKE", "terry-b-orourke", "joined") in seats(r)
    assert len(r.seats) == 3


def test_concurring_and_dissenting_is_a_partial_dissent():
    r = run("C_9918859")  # MESIWALA, J., Concurring and Dissenting.
    [sep] = r.separate_opinions
    assert (sep.type, sep.partial, sep.slug) == ("dissent", True, "shama-mesiwala")
    assert r.has_dissent is True and r.has_concurrence is False


def test_concurring_and_dissenting_fourth_district():
    r = run("G_4677448")  # ARONSON, J., Concurring and Dissenting.
    [sep] = r.separate_opinions
    assert (sep.type, sep.partial, sep.slug) == ("dissent", True, "richard-m-aronson")


def test_respectfully_dissent_near_a_signature_is_attributed_to_the_signer():
    r = run("B_4670203")  # "TANGEMAN, J.:" then "I respectfully dissent." ... TANGEMAN, J.
    [sep] = r.separate_opinions
    assert (sep.type, sep.slug) == ("dissent", "martin-j-tangeman")
    r = run("H_11050682")  # Lie, J., Dissenting: ... I respectfully dissent.
    [sep] = r.separate_opinions
    assert (sep.type, sep.slug) == ("dissent", "cynthia-c-lie")


def test_split_signature_dissent_and_assigned_trial_judge_dissent():
    r = run("E_4641269")  # MENETREZ, J., Dissenting.
    [sep] = r.separate_opinions
    assert sep.slug == "frank-j-menetrez"
    r = run("G_11312363")  # BANCROFT, J., pro tem., Dissenting. -- Orange County judge
    [sep] = r.separate_opinions
    assert (sep.type, sep.author_raw, sep.slug) == ("dissent", "BANCROFT, J.*", None)
    bancroft = [s for s in r.seats if s.surname == "BANCROFT"]
    assert bancroft and bancroft[0].assigned and bancroft[0].resolution == "trial_judge"


def test_concurring_in_part_and_dissenting_in_part_is_a_partial_dissent():
    r = run("D_11236280")  # CASTILLO, J., Concurring in part and dissenting in part.
    [sep] = r.separate_opinions
    assert (sep.type, sep.partial, sep.slug) == ("dissent", True, "jose-s-castillo")
    assert ("CASTILLO", "jose-s-castillo", "joined") in seats(r)
    r = run("B_11213456")  # HOFFSTADT, P. J., Concurring in part ... / "____, P. J." HOFFSTADT
    [sep] = r.separate_opinions
    assert (sep.type, sep.partial, sep.slug) == ("dissent", True, "brian-m-hoffstadt")


def test_abbreviated_acting_presiding_title_in_concurrence_heading():
    r = run("B_11331873")  # YEGAN, A.P.J., concurring:
    [sep] = r.separate_opinions
    assert (sep.type, sep.slug) == ("concurrence", "kenneth-r-yegan")


def test_joint_concurrence_gives_one_separate_opinion_per_signer():
    r = run("B_5175669")  # STRATTON, J., and WILEY, J., Concurring.
    assert [(x.type, x.surname) for x in r.separate_opinions] == [
        ("concurrence", "STRATTON"), ("concurrence", "WILEY"),
    ]
    assert r.has_concurrence is True


def test_concur_in_the_result_marker_and_following_dissent():
    r = run("C_5135324")  # HULL / I concur in the result: / MAURO / DUARTE, J., Dissenting.
    assert [(x.surname, x.role) for x in r.seats] == [
        ("HULL", "author"), ("MAURO", "joined"), ("DUARTE", "joined"),
    ]
    [sep] = r.separate_opinions
    assert (sep.type, sep.slug) == ("dissent", "elena-j-duarte")


def test_concurring_in_the_result_is_a_concurrence():
    r = run("D_9957665")  # O'ROURKE, J., Concurring in the result. ... O'ROURKE, Acting P. J.
    [sep] = r.separate_opinions
    assert (sep.type, sep.partial, sep.slug) == ("concurrence", False, "terry-b-orourke")


def test_lowercase_acting_title_and_concurring_colon():
    r = run("B_6342053")  # YEGAN, acting P. J. / I concur: PERREN / TANGEMAN, J., Concurring:
    assert r.author_slug == "kenneth-r-yegan" and r.seats[0].title == "Acting P. J."
    [sep] = r.separate_opinions
    assert (sep.type, sep.slug) == ("concurrence", "martin-j-tangeman")


# --- Supreme Court --------------------------------------------------------------


def test_supreme_court_authored_statement_gives_author_and_concurring_justices():
    r = run("S_4638160")
    assert (r.author_raw, r.author_slug) == ("Justice Corrigan", "carol-a-corrigan")
    assert [s.surname for s in r.seats] == [
        "Corrigan", "Cantil-Sakauye", "Liu", "Cuéllar", "Kruger", "Groban", "Gilbert",
    ]
    gilbert = r.seats[-1]
    assert gilbert.assigned and gilbert.slug == "arthur-gilbert"
    assert r.seats[1].title == "C. J."
    assert (r.district, r.division, r.published) == (None, None, True)


def test_supreme_court_filed_separate_opinion():
    r = run("S_4494581")  # Justice Cuéllar filed a concurring opinion.
    [sep] = r.separate_opinions
    assert (sep.type, sep.author_raw) == ("concurrence", "Justice Cuéllar")
    assert r.has_concurrence is True and r.has_dissent is False


def test_dash_led_separate_opinion_is_detected():
    # "POLLAK, P.J. — I concur in the disposition of this appeal, but ..." then signed.
    r = run("A_8210908")
    assert [(s.type, s.surname) for s in r.separate_opinions] == [("concurrence", "POLLAK")]
    assert "POLLAK" in [s.surname for s in r.seats]


def test_supreme_court_joiner_of_separate_opinion_is_on_the_panel():
    # "Justice Cuéllar filed a concurring and dissenting opinion, in which Justice Groban
    # concurred." Groban is not in the majority's "in which ... concurred" list.
    r = run("S_4433270")
    assert "Groban" in [s.surname for s in r.seats]
    assert sorted((s.author_raw, s.type, s.partial) for s in r.separate_opinions) == [
        ("Justice Cuéllar", "dissent", True), ("Justice Liu", "dissent", True)]


def test_supreme_court_separate_opinion_joiner_without_comma():
    # "Justice Liu filed a concurring opinion in which Justice Kruger concurred."
    r = run("S_5175655")
    assert [(s.type, s.author_raw) for s in r.separate_opinions] == [("concurrence", "Justice Liu")]
    assert "Kruger" in [s.surname for s in r.seats]


def test_supreme_court_opinion_concurring_in_the_judgment():
    r = run("S_4519783")  # "Justice Cuéllar filed an opinion concurring in the judgment."
    [sep] = r.separate_opinions
    assert (sep.type, sep.author_raw) == ("concurrence", "Justice Cuéllar")
    assert "Cuéllar" in [s.surname for s in r.seats]


def test_former_supreme_court_justices_resolve_within_their_service():
    r = run("S_4638160")  # filed 2020-11-30
    assert (r.seats[1].slug, r.seats[3].slug) == (
        "tani-cantil-sakauye", "mariano-florentino-cuellar",
    )
    assert r.parse_status == "ok"


def test_unresolvable_names_are_kept_and_marked_unresolved():
    # Cantil-Sakauye (left 2023-01-02) and Cuéllar (left 2021-10-31) have aliases,
    # but no service period covers a later filing date, so they cannot be placed.
    meta, body = load("S_4638160")
    r = parse.parse_opinion(
        body, court="cal", docket_number=meta["docket"], date_filed="2023-06-01",
        precedential_status=meta["status"],
    )
    cs = r.seats[1]
    assert cs.slug is None and cs.resolution == "no_match"
    assert r.parse_status == "unresolved"
    assert [s.surname for s in r.unresolved] == ["Cantil-Sakauye", "Cuéllar"]


# --- Caption, publication, disposition ------------------------------------------


def test_caption_division_wins_over_docket_prefix_and_disagreement_is_logged():
    meta, text = load("E_6333314")
    relabeled = text.replace("DIVISION TWO", "DIVISION ONE", 1)
    r = run("E_6333314", relabeled)
    assert (r.district, r.division) == ("4", "One")
    assert ("prefix_caption_mismatch", "E prefix 4/Two, caption 4/One") in r.notes


def test_partial_publication():
    r = run("F_4654417")  # CERTIFIED FOR PARTIAL PUBLICATION*
    assert (r.published, r.partial_publication) == (True, True)
    [sep] = r.separate_opinions  # POOCHIGIAN, Acting P.J., Dissenting.
    assert (sep.type, sep.partial, sep.slug) == ("dissent", False, "charles-s-poochigian")


def test_publication_status_from_header_and_cross_check():
    assert run("A_11171828").published is True
    assert run("D_11171767").published is False
    meta, text = load("D_11171767")
    r = parse.parse_opinion(text, court="calctapp", docket_number=meta["docket"],
                            date_filed=meta["date"], precedential_status="Published")
    assert ("publication_status_mismatch", "text unpublished, CourtListener Published") in r.notes


def test_consolidated_dockets_in_caption():
    r = run("A_11171828")  # case history below cites other A-numbers; only the caption counts
    assert r.docket_number_text == "A171807, A172215"
    r = run("A_4557316")  # two stacked captions, A156234 and A156238
    assert r.docket_number_text == "A156234, A156238"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("A_11171832", "affirmed"),
        ("A_11171776", "affirmed"),  # "Our original opinion ... is vacated" is not the disposition
        ("D_11171767", "dismissed"),
        ("D_11171775", "reversed"),
        ("B_11171774", "reversed"),
        ("F_6333312", "reversed_in_part"),  # remanded; "In all other respects ... affirmed"
        ("E_11171655", "writ_denied"),
        ("S_4635400", "affirmed"),
    ],
)
def test_disposition_class(name, expected):
    r = run(name)
    assert r.disposition_class == expected
    assert r.disposition_text


# --- Duplicates and remands -----------------------------------------------------


def _item(name: str) -> parse.DedupeItem:
    meta, text = load(name)
    r = run(name)
    return parse.DedupeItem(int(meta["cl_opinion_id"]), meta["date"], r.disposition_class, text)


def test_modified_opinion_supersedes_the_earlier_text():
    # E076253: filed 5/6/21, then E076253M "modified ... denying rehearing" 5/10/21.
    earlier, later = _item("E_4684756"), _item("E_4685458")
    assert parse.find_superseded([later, earlier]) == {earlier.opinion_id: later.opinion_id}


def test_opinion_after_supreme_court_transfer_is_a_separate_decision():
    # B333875 (9/16/24, affirmed) and B333875A (2/23/26, on transfer, vacated and remanded).
    assert parse.find_superseded([_item("B_10585515"), _item("B_11264490")]) == {}


def test_consolidated_case_filed_under_both_dockets_counts_once():
    meta, text = load("A_11171828")
    first = parse.DedupeItem(1, meta["date"], "affirmed", text)
    second = parse.DedupeItem(2, meta["date"], "affirmed", text)
    assert parse.find_superseded([first, second]) == {1: 2}
    assert parse.docket_keys("A171807", "A171807, A172215") == {"A171807", "A172215"}


# --- Every fixture --------------------------------------------------------------


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.txt")), ids=lambda p: p.stem)
def test_every_fixture_has_author_or_per_curiam_and_a_district(path):
    r = run(path.stem)
    assert r.parse_status in ("ok", "unresolved")
    assert r.per_curiam or r.author_raw
    assert r.seats
    if not path.stem.startswith("S_"):
        assert r.district in ("1", "2", "3", "4", "5", "6")


# --- Database CLI ---------------------------------------------------------------


def _seed(conn, names: list[str]) -> None:
    for name in names:
        meta, text = load(name)
        court = "cal" if meta["docket"].startswith("S") else "calctapp"
        conn.execute(
            "INSERT INTO clusters (cl_cluster_id, court, docket_number, date_filed, "
            "precedential_status, source) VALUES (?, ?, ?, ?, ?, 'test')",
            (int(meta["cluster"]), court, meta["docket"], meta["date"], meta["status"]),
        )
        db.insert_opinion(conn, int(meta["cl_opinion_id"]), int(meta["cluster"]),
                          meta["type"], text, "plain_text", "test")
    conn.commit()


def test_parse_database_is_idempotent_and_queues_unresolved(tmp_path):
    conn = db.connect(tmp_path / "cases.sqlite")
    _seed(conn, ["D_11171775", "S_4638160", "E_4684756", "E_4685458", "D_4639750"])
    # Move S_4638160 past Cantil-Sakauye's and Cuéllar's service so two seats queue.
    conn.execute("UPDATE clusters SET date_filed = '2023-06-01' WHERE cl_cluster_id = 4834381")
    conn.commit()
    queue = tmp_path / "unresolved.csv"
    log = tmp_path / "parse_log.csv"
    for _ in range(2):
        stats = parse.parse_database(conn, unresolved_path=queue, log_path=log)
    assert stats.parsed == 5
    unparsed = conn.execute("SELECT count(*) FROM opinions WHERE parse_status IS NULL")
    assert unparsed.fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM panel_seats WHERE cl_opinion_id = 11171775").fetchone()[0] == 3
    assert [tuple(x) for x in conn.execute(
        "SELECT type, author_slug FROM separate_opinions WHERE cl_opinion_id = 4639750"
    )] == [("dissent", "terry-b-orourke")]
    row = conn.execute(
        "SELECT author_slug, has_dissent, district, division FROM opinions "
        "WHERE cl_opinion_id = 4639750").fetchone()
    assert tuple(row) == ("judith-mcconnell", 1, "4", "One")
    assert conn.execute(
        "SELECT superseded_by FROM opinions WHERE cl_opinion_id = 4684756").fetchone()[0] == 4685458
    with open(queue, newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert [(r["cl_opinion_id"], r["seat_raw"], r["reason"]) for r in rows] == [
        ("4638160", "Chief Justice Cantil-Sakauye", "no_match"),
        ("4638160", "Justice Cuéllar", "no_match"),
    ]
