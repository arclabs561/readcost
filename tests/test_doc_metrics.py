"""Document metrics (metrics.py) and the opt-in center-embedding and undefined-acronym rules."""

import pytest

from readcost import Analyzer, Config, metrics
from readcost.features import center_embeddings, new_referents


@pytest.fixture(scope="module")
def plain():
    return Analyzer(Config())


@pytest.fixture(scope="module")
def opt():
    return Analyzer(Config(rules={"center-embedding": "info", "undefined-acronym": "info"}))


def rules(a, text, feature):
    return [f for f in a.check_text(text, "markdown").findings if f.feature == feature]


# Gibson 2000, examples (1b), (1c) and (2).
SINGLE = "The reporter who the senator attacked disliked the editor."
DOUBLE = "The reporter who the senator who John met attacked disliked the editor."
RIGHT = "John met the senator who attacked the reporter who disliked the editor."


# ---------------------------------------------------------------- MTLD

def test_mtld_hand_computed():
    # Forward: a b a -> TTR 2/3 <= .72, one factor; c d e left at TTR 1, adding 0.
    # 6 / 1 = 6. Backward: e d c a b a never reaches .72; the remainder's TTR
    # is 5/6, a partial factor of (1 - 5/6) / (1 - .72) = 0.595; 6 / 0.595 = 10.08.
    # MTLD is the mean of the two directions: 8.04.
    assert metrics.mtld(["a", "b", "a", "c", "d", "e"]) == pytest.approx((6 + 6 / ((1 / 6) / 0.28)) / 2)
    assert metrics.mtld(["a", "b", "a", "c", "d", "e"]) == pytest.approx(8.04, abs=0.01)


def test_mtld_is_undefined_without_repetition():
    assert metrics.mtld(["a", "b", "c"]) is None
    assert metrics.mtld([]) is None


def test_mtld_rises_with_more_varied_words():
    repetitive = ["log", "write", "log", "read"] * 20
    varied = [f"w{i}" for i in range(40)] + ["log", "write"] * 20
    assert metrics.mtld(varied) > metrics.mtld(repetitive)


# ---------------------------------------------------------------- idea density

def test_idea_density_counts_turner_and_greene_propositions(plain):
    # Brown et al. 2008: (HAS, MARE, NOSE), (OLD, MARE), (GRAY, MARE),
    # (LARGE, NOSE), (VERY, (LARGE, NOSE)): five propositions.
    sent = next(plain.nlp("The old gray mare has a very large nose.").sents)
    assert metrics.propositions(sent) == 5


# ---------------------------------------------------------------- center embedding

@pytest.mark.parametrize("text,depth", [(DOUBLE, 2), (SINGLE, 1), (RIGHT, 0)])
def test_center_embedding_depth_follows_gibson(plain, text, depth):
    sent = next(plain.nlp(text).sents)
    assert metrics.embedding_depth(sent) == depth


def test_center_embedded_clause_is_the_inner_verb(plain):
    sent = next(plain.nlp(DOUBLE).sents)
    assert [(t.text, d) for t, d in center_embeddings(sent)] == [("attacked", 1), ("met", 2)]


def test_result_carries_metrics_in_json(plain):
    r = plain.check_text(SINGLE + " " + RIGHT)
    d = r.to_dict()["metrics"]
    assert d["center_embedding_max"] == 1
    assert d["center_embedding_mean"] == 0.5
    assert d["mtld"] is None  # under 50 content words
    assert d["sentence_words_profile"]["low"] == 1.0


def test_sentence_profile_bands_use_the_cut_points(plain):
    long = "The parser " + " ".join(["reads the next file"] * 9) + " and stops."  # 40 words
    r = plain.check_text(SINGLE + " " + long)
    profile = r.metrics["sentence_words_profile"]
    assert profile["very_high"] == pytest.approx(40 / 49, abs=0.001)
    assert profile["low"] == pytest.approx(9 / 49, abs=0.001)


# ---------------------------------------------------------------- DLT referents

def test_new_referents_counts_gibson_examples(plain):
    # Gibson 2000, section 5.3.2: between "reporter" and "disliked" lie two new
    # referents in (1b) (senator, attacked) and four in (1c) (senator, John,
    # met, attacked). A first-person pronoun is not new: (6) has three.
    for text, want in [(SINGLE, 2), (DOUBLE, 4),
                       ("The reporter who the senator who I met attacked disliked the editor.", 3)]:
        doc = plain.nlp(text)
        subj = next(t for t in doc if t.dep_ == "nsubj" and t.head.dep_ == "ROOT")
        assert new_referents(doc, subj.i, subj.head.i) == want


# ---------------------------------------------------------------- opt-in rules

def test_new_rules_are_off_by_default(plain):
    assert rules(plain, DOUBLE, "center-embedding") == []
    assert rules(plain, "Every write goes to the WAL before the table changes.", "undefined-acronym") == []


def test_double_center_embedding_is_flagged(opt):
    fs = rules(opt, DOUBLE, "center-embedding")
    assert len(fs) == 1
    assert fs[0].severity == "info"
    assert fs[0].excerpt == "who the senator who John met attacked"


def test_double_embedding_with_an_indexical_innermost_subject_is_not_flagged(opt):
    # Gibson 1998, after Bever 1974: "I" or "you" adds no new referent, and
    # such sentences are processable. The parse still nests "met" two deep.
    from readcost.features import center_embeddings

    text = DOUBLE.replace("who John met", "who I met")
    assert max(d for _, d in center_embeddings(next(opt.nlp(text).sents))) == 2
    assert rules(opt, text, "center-embedding") == []


@pytest.mark.parametrize("text", [SINGLE, RIGHT])
def test_single_or_right_branching_clauses_are_not_flagged(opt, text):
    assert rules(opt, text, "center-embedding") == []


def test_acronym_never_spelled_out(opt):
    fs = rules(opt, "Every write goes to the WAL before the table changes.", "undefined-acronym")
    assert [f.message for f in fs] == ["'WAL' is used without being spelled out"]


def test_acronym_spelled_out_later(opt):
    text = ("Every write goes to the WAL before the table changes.\n\n"
            "The write-ahead log (WAL) is compacted by a background job.")
    assert [f.message for f in rules(opt, text, "undefined-acronym")] == ["'WAL' is used before it is spelled out"]


@pytest.mark.parametrize("text", [
    "Every write goes to the write-ahead log (WAL) first. The WAL is compacted by a background job.",
    "Every write goes to the WAL (write-ahead log) first. The WAL is compacted by a background job.",
    "The server returns JSON from the API to every caller that asks.",
    "## WAL\n\nEvery write goes to the write-ahead log (WAL) before the table changes.",
])
def test_spelled_out_or_common_acronyms_are_not_flagged(opt, text):
    assert rules(opt, text, "undefined-acronym") == []


def test_acronym_in_allow_list_is_not_flagged():
    a = Analyzer(Config(rules={"undefined-acronym": "info"}, allow=["WAL"]))
    assert rules(a, "Every write goes to the WAL before the table changes.", "undefined-acronym") == []


def test_acronym_reported_once(opt):
    text = "Every write goes to the WAL first. Then the WAL is flushed to the disk by the job."
    assert len(rules(opt, text, "undefined-acronym")) == 1


@pytest.mark.parametrize("text", [
    # Shaped like corpus sentences labelled not center-embedded: only a
    # connective of the outer clause precedes the nested clause.
    "But if what we measure is latency on our own servers, we have enough data.",
    "Whereas when the failures you have to debug are rare, they look like noise.",
])
def test_clause_after_a_connective_is_not_center_embedded(opt, text):
    assert rules(opt, text, "center-embedding") == []


def test_frequent_abbreviations_and_capitalised_words_are_known(opt):
    assert rules(opt, "The CEO approved the plan after the board meeting ended.", "undefined-acronym") == []
    assert rules(opt, "Then the job runs an UPDATE statement to modify the database.", "undefined-acronym") == []


@pytest.mark.parametrize("text", [
    # The two shapes found in database documentation: "X or ACR" and a quoted
    # expansion followed by the acronym in parentheses.
    "Each shard keeps a write-ahead log or WAL file next to its data.",
    'Since version 2, a "Write-Ahead Log" setting (called "WAL" below) is available.',
])
def test_spelled_out_next_to_the_acronym_counts_as_a_definition(opt, text):
    assert rules(opt, text, "undefined-acronym") == []


def test_referent_measure_is_opt_in_and_changes_the_message():
    text = ("The index, which is built once from every document in the corpus at startup and then "
            "rebuilt only when the compactor runs, serves all queries.")
    default = rules(Analyzer(Config()), text, "long-dependency")
    assert default and "new nouns or verbs" not in default[0].message
    dlt = rules(Analyzer(Config(long_dependency_referents=5)), text, "long-dependency")
    assert [f.message.split(", with ")[1].split(" new")[0] for f in dlt] == ["6"]
