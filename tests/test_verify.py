"""readcost.verify: the second-parser check behind verify_model. Made-up sentences and a fake model."""

import json

import pytest

from readcost import Analyzer, Config, verify
from readcost.config import load_config

STACK = "The index shard compaction job reads the manifest before it starts the merge."
RELATIVE = "We adopted the format the reviewers expect in every report."


def parse(upos, heads=None, deprels=None):
    n = len(upos)
    return verify.Parse(tuple(upos), tuple(heads or [-1] * n), tuple(deprels or ["dep"] * n))


def test_a_stack_survives_unless_a_word_of_it_is_a_verb():
    nouns = parse(["DET", "NOUN", "NOUN", "NOUN", "VERB"])
    assert verify.keep("stacked-nouns", nouns, [], [1, 2, 3])
    assert not verify.keep("stacked-nouns", nouns, [], [1, 2, 3, 4])
    assert verify.keep("stacked-nouns", parse(["DET", "ADJ", "NOUN", "NOUN"]), [], [1, 2, 3])  # an adjective is not a veto


def test_a_reduced_relative_needs_a_relative_clause_with_its_own_subject():
    words = ["the", "format", "the", "reviewers", "expect"]
    upos = ["DET", "NOUN", "DET", "NOUN", "VERB"]
    relative = parse(upos, [1, -1, 3, 4, 1], ["det", "root", "det", "nsubj", "acl:relcl"])
    main_clause = parse(upos, [1, 4, 3, 4, -1], ["det", "obj", "det", "nsubj", "root"])
    assert verify.keep("reduced-object-relative", relative, words, [1, 3, 4])
    assert not verify.keep("reduced-object-relative", main_clause, words, [1, 3, 4])
    words = ["the", "format", "that", "reviewers", "expect"]
    with_that = parse(["DET", "NOUN", "PRON", "NOUN", "VERB"], [1, -1, 4, 4, 1],
                      ["det", "root", "obj", "nsubj", "acl:relcl"])
    assert not verify.keep("reduced-object-relative", with_that, words, [1, 3, 4])


def test_a_long_dependency_needs_a_long_core_arc_over_the_same_words():
    upos = ["NOUN"] + ["X"] * 9 + ["VERB"]
    far = parse(upos, [10] + [0] * 9 + [-1], ["nsubj"] + ["dep"] * 9 + ["root"])
    near = parse(upos, [10] + [0] * 8 + [10, -1], ["nmod"] + ["dep"] * 8 + ["nsubj", "root"])
    assert verify.keep("long-dependency", far, [], [0, 10])
    assert not verify.keep("long-dependency", near, [], [0, 10])
    assert not verify.keep("long-dependency", far, [], [11, 12])  # an arc elsewhere does not count


def test_a_copular_subject_is_measured_to_the_copula():
    # "Index [8 words] is a file": UD hangs the subject on "file"; readcost measures it to "is".
    upos = ["NOUN"] + ["X"] * 8 + ["AUX", "DET", "NOUN"]
    heads = [11] + [0] * 8 + [11, 11, -1]
    deprels = ["nsubj"] + ["dep"] * 8 + ["cop", "det", "root"]
    arcs = verify.core_arcs(parse(upos, heads, deprels))
    assert (9, 0, 9) in arcs and (2, 9, 11) in arcs


def test_other_rules_and_unreadable_sentences_keep_their_findings():
    assert verify.keep("inline-list", parse(["VERB"]), ["x"], [0])
    assert verify.keep("stacked-nouns", None, ["x"], [0])
    assert verify.keep("stacked-nouns", parse(["VERB"]), ["x"], [])


class FakeModel:
    """Tags every word of the stack sentence a noun except "reads"; counts its calls."""

    def __init__(self, verb_in_stack=False):
        self.calls = 0
        self.verb_in_stack = verb_in_stack

    def parse(self, words):
        self.calls += 1
        upos = ["VERB" if w in ("reads", "starts", "adopted", "expect") else "NOUN" for w in words]
        if self.verb_in_stack and "compaction" in words:
            upos[words.index("compaction")] = "VERB"
        return parse(upos)


def test_verifier_caches_by_the_words_and_counts_what_it_drops():
    v = verify.Verifier(FakeModel(verb_in_stack=True), size=2)
    words = ["The", "index", "shard", "compaction", "job"]
    assert not v.keep("stacked-nouns", words, [1, 2, 3, 4])
    assert not v.keep("stacked-nouns", words, [1, 2, 3, 4])
    assert v.model.calls == 1 and v.dropped == 2
    v.parse(["a"]), v.parse(["b"])  # the cache holds two sentences
    v.parse(words)
    assert v.model.calls == 4
    assert v.parse(["w"] * (verify.Verifier.MAX_WORDS + 1)) is None


@pytest.fixture
def with_fake(monkeypatch):
    def use(model):
        monkeypatch.setattr(verify, "load", lambda setting: verify.Verifier(model))
    return use


def test_the_setting_drops_a_finding_the_second_parser_rejects(with_fake):
    plain = Analyzer(Config()).check_text(STACK, "text")
    assert [f.feature for f in plain.findings] == ["stacked-nouns"]
    with_fake(FakeModel(verb_in_stack=False))
    assert [f.feature for f in Analyzer(Config(verify_model="fake")).check_text(STACK, "text").findings] == \
        ["stacked-nouns"]
    with_fake(FakeModel(verb_in_stack=True))
    assert Analyzer(Config(verify_model="fake")).check_text(STACK, "text").findings == []


def test_the_setting_leaves_sentences_without_those_findings_unparsed(with_fake):
    model = FakeModel()
    with_fake(model)
    Analyzer(Config(verify_model="fake")).check_text("The cat sat on the mat while the dog slept.", "text")
    assert model.calls == 0


def test_the_setting_is_off_by_default_and_read_from_toml(tmp_path):
    assert Config().verify_model == "" and Analyzer(Config()).verifier is None
    (tmp_path / "readcost.toml").write_text('[readcost]\nverify_model = "biaffine"\n')
    assert load_config(tmp_path / "readcost.toml").verify_model == "biaffine"


def test_a_missing_model_says_how_to_get_it(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    with pytest.raises(OSError, match="readcost setup --verifier"):
        verify.resolve("biaffine")
    with pytest.raises(OSError, match="no model.onnx"):
        verify.resolve(str(tmp_path))
    with pytest.raises(RuntimeError, match="verify_model"):
        Analyzer(Config(verify_model=str(tmp_path))).check_text(STACK, "text")


def test_biaffine_reads_the_graph_outputs(tmp_path):
    import numpy as np

    (tmp_path / "config.json").write_text(json.dumps({
        "fix_len": 3, "pos_vocab": {"<pad>": 0, "<bos>": 1, "NOUN": 2, "VERB": 3},
        "rel_vocab": {"<pad>": 0, "<bos>": 1, "root": 2, "nsubj": 3}}))

    class Tok:
        def token_to_id(self, t):
            return {"[CLS]": 1, "[UNK]": 3}[t]

        def encode(self, w, add_special_tokens=False):
            return type("E", (), {"ids": [10 + len(w)] * len(w)})()

    class Session:
        def get_inputs(self):
            return [type("I", (), {"name": "subwords"})()]

        def get_outputs(self):
            return [type("O", (), {"name": n})() for n in ("s_arc", "s_rel", "s_pos", "s_feats")]

        def run(self, _names, feeds):
            assert feeds["subwords"].shape == (1, 3, 3)
            arc = np.zeros((1, 3, 3), dtype=np.float32)
            arc[0, 1, 2], arc[0, 2, 0] = 5, 5
            rel = np.zeros((1, 3, 3, 4), dtype=np.float32)
            rel[0, 1, 2, 3] = rel[0, 2, 0, 2] = 1
            pos = np.zeros((1, 3, 4), dtype=np.float32)
            pos[0, 1, 2] = pos[0, 2, 3] = 1
            return [arc, rel, pos, None]

    model = verify.Biaffine(tmp_path, session=Session(), tokenizer=Tok())
    assert model.grid(["a", "long"])[0].tolist() == [[1, 0, 0], [11, 0, 0], [14, 14, 14]]
    assert model.parse(["dogs", "bark"]) == verify.Parse(("NOUN", "VERB"), (1, -1), ("nsubj", "root"))


def test_fetch_refuses_without_a_pinned_revision(monkeypatch):
    monkeypatch.setattr(verify, "REVISION", "")
    with pytest.raises(OSError, match="no pinned"):
        verify.fetch()
