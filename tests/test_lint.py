"""U11: banned-word lint over prose the project wrote (KTD11)."""

from src import lint


def test_banned_word_in_prose_is_flagged_with_line():
    hits = lint.check_text("guide/justices/x.md", "Line one.\nThe ruling was lenient.\n", [])
    assert hits == [("guide/justices/x.md", 2, "lenient")]


def test_phrase_and_hyphenated_terms_flagged():
    text = "A rubber-stamp ruling. Critics say soft on crime."
    words = {h[2] for h in lint.check_text("p.md", text, [])}
    assert words == {"rubber-stamp", "soft on crime"}


def test_whole_words_only():
    assert lint.check_text("p.md", "Liberalization and conservatively drafted.", []) == []


def test_italic_case_name_is_skipped():
    assert lint.check_text("p.md", "*People v. Liberal* (2024)", []) == []


def test_quoted_opinion_text_is_skipped_only_when_excepted():
    text = 'The court said "the conservative reading controls."'
    assert lint.check_text("p.md", text, []) != []
    exceptions = [{"file": "p.md", "phrase": "the conservative reading controls"}]
    assert lint.check_text("p.md", text, exceptions) == []


def test_case_insensitive():
    assert lint.check_text("p.md", "ACTIVIST judges", []) == [("p.md", 1, "activist")]
