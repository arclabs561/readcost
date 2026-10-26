import pytest

from readcost import Analyzer, Config


@pytest.fixture(scope="module")
def analyzer():
    return Analyzer(Config())


def feats(analyzer, text, **kw):
    return [f.feature for f in analyzer.check_text(text, "markdown", **kw).findings]


def test_paper_example_sentence(analyzer):
    # The paper's opening example: an object relative, an inanimate subject of
    # "eat", and a noun stack.
    # With "you" as the relative clause's subject the object relative is easy
    # (Gordon, Hendrick and Johnson 2001), so it is not reported; with a full
    # noun phrase it is.
    s = ("Your instinct is right; the convoluted sentence you are currently reading "
         "is quietly eating its own reader-patience budget.")
    found = feats(analyzer, s)
    assert "hyphen-compound" in found
    assert "inanimate-subject" in found
    assert "reduced-object-relative" not in found
    assert "reduced-object-relative" in feats(
        analyzer, "The convoluted sentence the reviewer is currently reading is quietly eating its budget.")


def test_plain_sentence_is_clean(analyzer):
    r = analyzer.check_text("The index stores one list of documents for each term. "
                            "You can search it from several threads.", "markdown")
    assert r.findings == [] and r.verdict == "pass"


def test_stacked_nouns_and_rewrite(analyzer):
    assert "stacked-nouns" in feats(analyzer, "Each restart triggers source segment rebuilds in the store.")
    assert "stacked-nouns" not in feats(analyzer, "Each restart triggers a rebuild of every segment from its source.")


def test_names_and_allowlist_are_not_stacks(analyzer):
    assert "stacked-nouns" not in feats(analyzer, "We ran the benchmark on an Apple M3 Max laptop yesterday.")
    assert "stacked-nouns" not in feats(analyzer, "The store appends each record to a write-ahead log first.")


def test_hyphen_compound(analyzer):
    # A hyphen pair is one unit, so a coined pair before a noun is
    # hyphen-compound's, even when the noun is an allowed term ("use case").
    found = feats(analyzer, "This crate exists for the storage-shrink use case in search engines.")
    assert "hyphen-compound" in found and "stacked-nouns" not in found
    assert "hyphen-compound" not in feats(analyzer, "The caller-owned buffer is reused between calls to the parser.")


def test_inline_list(analyzer):
    # Short items and clauses joined by commas are not inline lists.
    assert "inline-list" not in feats(analyzer, "It supports negations, implications, OWA, power means, and uninorms.")
    assert "inline-list" not in feats(analyzer, "They hired people from Microsoft, Apple, Yahoo, Google, and Facebook.")
    assert "inline-list" not in feats(
        analyzer, "When the cache is cold, the first request is slow, the second is faster, and the third is instant.")
    assert "inline-list" in feats(analyzer, "It supports negations from three families, implications defined by residuation, ordered weighted averages, and uninorms with any neutral element.")
    assert "inline-list" in feats(analyzer, "It supports standard/Sugeno/Yager negations for every operator.")
    assert "inline-list" not in feats(analyzer, "It reads input/output streams and writes files.")


def test_inanimate_subject_does_not_own(analyzer):
    assert "inanimate-subject" in feats(analyzer, "It does not own indexing or compaction in any form.")
    assert "inanimate-subject" not in feats(analyzer, "The index uses one file per segment on disk.")


def test_line_filter(analyzer):
    text = "Plain first sentence with nothing odd in it.\n\nEach restart triggers source segment rebuilds in the store."
    assert analyzer.check_text(text, "markdown", lines=[(1, 1)]).findings == []
    assert analyzer.check_text(text, "markdown", lines=[(3, 3)]).findings


def test_disable_feature():
    a = Analyzer(Config(disable=["stacked-nouns"]))
    assert "stacked-nouns" not in feats(a, "Each restart triggers source segment rebuilds in the store.")


def test_verdict_thresholds(analyzer):
    dense = ("It does not own indexing, segment selection, compaction, or reader visibility. "
             "The example prints the first snapshot-search cost with persisted region-index sidecars "
             "present versus after deleting those sidecars and forcing source-segment rebuilds. "
             "We tune the shard compaction retry budget by hand.")
    assert analyzer.check_text(dense, "markdown").verdict == "block"
