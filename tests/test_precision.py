"""False positives from docs/evaluation.md, and the true findings that must survive the fixes."""

import pytest

from readcost import Analyzer, Config


@pytest.fixture(scope="module")
def analyzer():
    return Analyzer(Config())


def feats(a, text):
    return [f.feature for f in a.check_text(text, "markdown").findings]


@pytest.mark.parametrize("text", [
    "If we're serializing an object we've already seen before, we can just outline it as a separate row.",
    "It is a list of everyone I trust with the keys to the server.",
    "That is all you need to start a new project.",
    "The first time we met, the build took an hour.",
])
def test_object_relative_with_pronoun_subject_or_light_head_is_not_reported(analyzer, text):
    assert "reduced-object-relative" not in feats(analyzer, text)


def test_object_relative_with_full_noun_subject_is_reported(analyzer):
    assert "reduced-object-relative" in feats(analyzer, "The format the reader expects is not the one we write.")


@pytest.mark.parametrize("text", [
    "In my small project it feels like I just have five main files to worry about.",
    "If a line feels too long, wrap it and indent with an extra tab.",
    "An unrecoverable error causes the program to panic and the process dies.",
])
def test_thing_subject_verbs_are_not_inanimate_subjects(analyzer, text):
    assert "inanimate-subject" not in feats(analyzer, text)


def test_true_inanimate_subject_is_still_reported(analyzer):
    assert "inanimate-subject" in feats(analyzer, "The configuration file does not own the cache directory.")


@pytest.mark.parametrize("text", [
    "The Go programming language has a short and readable specification.",
    "The SQLite database file is a single ordinary disk file.",
])
def test_leading_name_does_not_count_as_a_stacked_noun(analyzer, text):
    assert "stacked-nouns" not in feats(analyzer, text)


def test_long_stack_after_a_name_is_still_reported(analyzer):
    # The one labeled-correct stacked-nouns finding in the evaluation sample.
    text = ("To prevent older versions from trying to recover the database, the database "
            "file format version numbers are set to 2.")
    assert "stacked-nouns" in feats(analyzer, text)


def test_phrasal_verb_is_not_a_denominal_verb():
    a = Analyzer(Config(enable=["denominal-verb"]))
    assert "denominal-verb" not in feats(a, "You can always figure out more from the screen than from the manual.")
    assert "denominal-verb" in feats(a, "The script will bucket the requests by hour.")


def test_denominal_verb_is_off_by_default(analyzer):
    assert "denominal-verb" not in feats(analyzer, "The script will bucket the requests by hour.")


@pytest.mark.parametrize("text", [
    "Effective Go provides guidelines for naming packages, types, functions, and variables.",
    "But it's still a challenge for models, because drawing pelicans is difficult, drawing "
    "bicycles is difficult, and pelicans can't ride bicycles in the first place.",
])
def test_short_items_and_clauses_are_not_inline_lists(analyzer, text):
    assert "inline-list" not in feats(analyzer, text)


def test_list_the_parser_splits_is_still_counted(analyzer):
    # en_core_web_sm attaches these items to different heads; the verbless
    # comma chunks still count them.
    text = ("The release adds a parser for the old format, a cache for remote lookups, "
            "a retry policy for failed uploads, and a flag to disable telemetry.")
    assert "inline-list" in feats(analyzer, text)


def test_slash_list_is_reported_beside_a_short_comma_list(analyzer):
    fs = [f for f in Analyzer(Config()).check_text(
        "It supports standard/Sugeno/Yager negations, OWA, power means, and uninorms.", "markdown").findings
        if f.feature == "inline-list"]
    assert len(fs) == 1 and "slash" in fs[0].message
