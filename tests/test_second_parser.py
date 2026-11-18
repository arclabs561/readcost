"""scripts/eval_second_parser.py: filters, the two ONNX adapters and the scoring.

Every fixture is made up. The ONNX sessions and tokenizers are stand-ins, so
neither onnxruntime nor a model file is needed.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from readcost import Analyzer, Config

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


@pytest.fixture(scope="module")
def sp():
    spec = importlib.util.spec_from_file_location("eval_second_parser", SCRIPTS / "eval_second_parser.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["eval_second_parser"] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def analyzer():
    return Analyzer(Config())


STACK = "The index shard compaction job reads the manifest before it starts the merge."
RELATIVE = "We adopted the format the reviewers expect in every report."


def finding(sp, rule, words, tokens):
    offsets, at = [], 0
    for w in words:
        offsets.append((at, at + len(w)))
        at += len(w) + 1
    return sp.Finding(rule, offsets[min(tokens)][0], offsets[max(tokens)][1], tuple(words), tuple(offsets),
                      tuple(tokens))


# -------------------------------------------------------------------- findings

def test_doc_findings_gives_each_finding_its_words_and_roles(sp, analyzer):
    from readcost.features import Context

    ctx = Context(analyzer.cfg, analyzer.profile, analyzer.allow, analyzer.enabled)
    stack, = sp.doc_findings(ctx, analyzer.nlp(STACK))
    assert stack.rule == "stacked-nouns" and STACK[stack.start:stack.end] == "index shard compaction job"
    assert [stack.words[k] for k in stack.tokens] == ["index", "shard", "compaction", "job"]
    assert all(STACK[a:b] == w for w, (a, b) in zip(stack.words, stack.offsets))
    relative = [f for f in sp.doc_findings(ctx, analyzer.nlp(RELATIVE)) if f.rule == "reduced-object-relative"]
    assert [relative[0].words[k] for k in relative[0].tokens] == ["format", "reviewers", "expect"]


# --------------------------------------------------------------------- filters

def test_pos_filters_drop_a_stack_with_a_verb_in_it(sp):
    words = ["The", "cache", "eviction", "policy", "scores", "high", "."]
    f = finding(sp, "stacked-nouns", words, [1, 2, 3, 4])
    verb = sp.Parse(["DET", "NOUN", "NOUN", "NOUN", "VERB", "ADJ", "PUNCT"])
    nouns = sp.Parse(["DET", "NOUN", "NOUN", "NOUN", "NOUN", "ADJ", "PUNCT"])
    adjective = sp.Parse(["DET", "ADJ", "NOUN", "NOUN", "NOUN", "ADJ", "PUNCT"])
    assert not sp.keep_pos_verb(f, verb) and not sp.keep_pos(f, verb)
    assert sp.keep_pos_verb(f, nouns) and sp.keep_pos(f, nouns)
    assert sp.keep_pos_verb(f, adjective) and not sp.keep_pos(f, adjective)  # only the strict filter minds


def test_pos_filters_on_a_relative_clause_and_a_long_dependency(sp):
    words = ["the", "format", "the", "reviewers", "expect"]
    f = finding(sp, "reduced-object-relative", words, [1, 3, 4])
    assert sp.keep_pos(f, sp.Parse(["DET", "NOUN", "DET", "NOUN", "VERB"]))
    assert not sp.keep_pos_verb(f, sp.Parse(["DET", "NOUN", "DET", "NOUN", "NOUN"]))
    assert not sp.keep_pos(f, sp.Parse(["DET", "VERB", "DET", "NOUN", "VERB"]))
    dep = finding(sp, "long-dependency", ["index", "x", "serves"], [0, 2])
    assert sp.keep_pos(dep, sp.Parse(["NOUN", "X", "VERB"])) and not sp.keep_pos(dep, sp.Parse(["NOUN", "X", "NOUN"]))
    assert sp.keep_pos_verb(dep, sp.Parse(["NOUN", "X", "NOUN"]))  # the light filter leaves it alone


def test_ud_filter_asks_the_second_tree_for_the_construction(sp):
    words = ["The", "index", "shard", "job", "runs"]
    f = finding(sp, "stacked-nouns", words, [1, 2, 3])
    upos = ["DET", "NOUN", "NOUN", "NOUN", "VERB"]
    compound = sp.Parse(upos, [3, 3, 3, 4, -1], ["det", "compound", "compound", "nsubj", "root"])
    split = sp.Parse(upos, [1, 4, 3, 4, -1], ["det", "nsubj", "compound", "obj", "root"])
    assert sp.keep_ud(f, compound) and not sp.keep_ud(f, split)
    assert sp.keep_ud(f, sp.Parse(upos))  # a tagger with no tree has no say

    words = ["the", "format", "the", "reviewers", "expect"]
    f = finding(sp, "reduced-object-relative", words, [1, 3, 4])
    upos = ["DET", "NOUN", "DET", "NOUN", "VERB"]
    relative = sp.Parse(upos, [1, -1, 3, 4, 1], ["det", "root", "det", "nsubj", "acl:relcl"])
    main = sp.Parse(upos, [1, 4, 3, 4, -1], ["det", "obj", "det", "nsubj", "root"])
    assert sp.keep_ud(f, relative) and not sp.keep_ud(f, main)
    words = ["the", "format", "that", "reviewers", "expect"]
    f = finding(sp, "reduced-object-relative", words, [1, 3, 4])
    with_that = sp.Parse(["DET", "NOUN", "PRON", "NOUN", "VERB"], [1, -1, 4, 4, 1],
                         ["det", "root", "obj", "nsubj", "acl:relcl"])
    assert not sp.keep_ud(f, with_that)


def test_ud_filter_on_a_long_dependency(sp):
    words = ["Index"] + ["x"] * 9 + ["serves"]
    f = finding(sp, "long-dependency", words, [0, 10])
    upos = ["NOUN"] + ["X"] * 9 + ["VERB"]
    far = sp.Parse(upos, [10] + [0] * 9 + [-1], ["nsubj"] + ["dep"] * 9 + ["root"])
    near = sp.Parse(upos, [10] + [0] * 8 + [10, -1], ["nmod"] + ["dep"] * 8 + ["nsubj", "root"])
    assert sp.keep_ud(f, far) and not sp.keep_ud(f, near)


def test_apply_filter_caches_by_words_and_keeps_what_the_tagger_cannot_read(sp):
    calls = []

    class Tagger:
        def tag(self, words):
            calls.append(words)
            return None if words[0] == "long" else sp.Parse(["VERB"] * len(words))

    cached = sp.Cached(Tagger())
    a = finding(sp, "stacked-nouns", ["a", "b", "c"], [0, 1, 2])
    b = finding(sp, "stacked-nouns", ["long", "b", "c"], [0, 1, 2])
    assert sp.apply_filter([a, a, b], cached, sp.keep_pos) == [b]
    assert len(calls) == 2 and cached.calls == 2 and cached.words == 6


def test_agree_needs_the_same_rule_on_overlapping_words(sp):
    words = ["a", "b", "c", "d", "e"]
    mine = [finding(sp, "stacked-nouns", words, [0, 1, 2]), finding(sp, "long-dependency", words, [3, 4])]
    other = [finding(sp, "stacked-nouns", words, [2, 3, 4]), finding(sp, "stacked-nouns", words, [3, 4])]
    assert sp.agree(mine, other) == mine[:1]


# -------------------------------------------------------------------- adapters

class FakeTokenizer:
    """One subword id per letter, plus special tokens at both ends when asked."""

    def token_to_id(self, token):
        return {"[CLS]": 1, "[UNK]": 3}[token]

    def encode(self, text, add_special_tokens=True):
        ids, offsets = [], []
        for k, ch in enumerate(text):
            if ch != " ":
                ids.append(10 + ord(ch) % 50)
                offsets.append((k, k + 1))
        if add_special_tokens:
            ids, offsets = [1, *ids, 2], [(0, 0), *offsets, (0, 0)]
        return SimpleNamespace(ids=ids, offsets=offsets)


class FakeSession:
    def __init__(self, inputs, outputs, run):
        self._inputs = [SimpleNamespace(name=n, type=t, shape=None) for n, t in inputs]
        self._outputs = [SimpleNamespace(name=n, shape=None) for n in outputs]
        self._run = run
        self.feeds = None

    def get_inputs(self):
        return self._inputs

    def get_outputs(self):
        return self._outputs

    def run(self, _names, feeds):
        self.feeds = feeds
        return self._run(feeds)


def test_biaffine_builds_the_word_grid_and_decodes_tags_heads_and_relations(sp, tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({
        "fix_len": 4, "pos_vocab": {"<pad>": 0, "<bos>": 1, "NOUN": 2, "VERB": 3},
        "rel_vocab": {"<pad>": 0, "<bos>": 1, "root": 2, "nsubj": 3}}))

    def run(feeds):
        grid = feeds["subwords"]
        assert grid.shape == (1, 3, 4) and grid.dtype == np.int64
        arc = np.zeros((1, 3, 3), dtype=np.float32)
        arc[0, 1, 1] = 9.0   # "dogs" scores itself highest: not allowed
        arc[0, 1, 2] = 5.0   # then "bark"
        arc[0, 2, 0] = 5.0   # "bark" hangs from the root
        rel = np.zeros((1, 3, 3, 4), dtype=np.float32)
        rel[0, 1, 2, 3] = 1.0
        rel[0, 2, 0, 2] = 1.0
        rel[0, 2, 0, 0] = 7.0   # <pad> never wins
        pos = np.zeros((1, 3, 4), dtype=np.float32)
        pos[0, 1, 2] = 1.0
        pos[0, 2, 3] = 1.0
        pos[0, 2, 0] = 7.0
        return [arc, rel, pos]

    session = FakeSession([("subwords", "tensor(int64)")], ["s_arc", "s_rel", "s_pos"], run)
    model = sp.Biaffine(tmp_path, session=session, tokenizer=FakeTokenizer())
    grid = model.grid(["dogs", "barking"])
    assert grid[0, 0].tolist() == [1, 0, 0, 0]              # the root row holds only [CLS]
    assert (grid[0, 2] != 0).sum() == 4                     # a long word is cut to fix_len
    parse = model.tag(["dogs", "bark"])
    assert parse.upos == ["NOUN", "VERB"] and parse.heads == [1, -1] and parse.deprels == ["nsubj", "root"]


def test_kniv_aligns_words_to_first_subwords_and_reads_the_pos_scores(sp, tmp_path):
    (tmp_path / "onnx").mkdir()
    (tmp_path / "onnx" / "onnx_meta.json").write_text(json.dumps({
        "max_subwords": 12, "labels": {"pos": ["NOUN", "VERB"]}, "graphs": {"plain": {"outputs": ["pos", "arc"]}}}))

    def run(feeds):
        assert set(feeds) == {"input_ids", "attention_mask", "first_subword", "word_mask"}  # only what the graph takes
        assert feeds["word_mask"].dtype == bool
        pos = np.zeros((1, 2, 2), dtype=np.float32)
        pos[0, 0, 0] = pos[0, 1, 1] = 1.0
        return [pos]

    session = FakeSession([("input_ids", "tensor(int64)"), ("attention_mask", "tensor(int64)"),
                           ("first_subword", "tensor(int64)"), ("word_mask", "tensor(bool)")], ["pos"], run)
    model = sp.Kniv(tmp_path, session=session, tokenizer=FakeTokenizer())
    ids, first = model.align(["dogs", "bark"])
    assert len(ids) == 10 and first == [1, 5]               # after the opening special token
    assert model.tag(["dogs", "bark"]).upos == ["NOUN", "VERB"]
    assert model.tag(["a" * 20]) is None                    # over the subword limit: not tagged


# --------------------------------------------------------------------- scoring

CONLLU = """\
# newdoc id = made-up
# text = The index shard compaction job reads the manifest.
1	The	the	DET	DT	_	5	det	_	_
2	index	index	NOUN	NN	_	5	compound	_	_
3	shard	shard	NOUN	NN	_	5	compound	_	_
4	compaction	compaction	NOUN	NN	_	5	compound	_	_
5	job	job	NOUN	NN	_	6	nsubj	_	_
6	reads	read	VERB	VBZ	_	0	root	_	_
7	the	the	DET	DT	_	8	det	_	_
8	manifest	manifest	NOUN	NN	_	6	obj	_	SpaceAfter=No
9	.	.	PUNCT	.	_	6	punct	_	_

"""


def test_counts_score_a_finding_against_both_references(sp, analyzer, tmp_path):
    from readcost.features import Context

    path = tmp_path / "made-up.conllu"
    path.write_text(CONLLU)
    sentence, = sp.load_group([path])
    assert sentence["words"] == 8 and sentence["cluster"] == "made-up.conllu:made-up"
    refs = sp.references(analyzer, sentence["tokens"])
    ctx = Context(analyzer.cfg, analyzer.profile, analyzer.allow, analyzer.enabled)
    mine = sp.doc_findings(ctx, analyzer.nlp(sentence["text"]))
    row = sp.counts(mine, refs)["stacked-nouns"]
    assert row.tolist() == [1, 1, 1, 1, 1, 1, 1]
    assert sp.counts([], refs)["stacked-nouns"].tolist() == [0, 0, 1, 0, 0, 1, 0]


def test_summarize_gives_paired_differences_under_the_same_resamples(sp):
    # Ten documents; the filter drops the one wrong finding in each of the first five.
    base = np.array([[2, 1, 1, 1, 1, 1, 1]] * 5 + [[1, 1, 1, 1, 1, 1, 1]] * 5)
    kept = base.copy()
    kept[:5, sp.FINDINGS] = 1
    out = sp.summarize({"sm": base, "filter": kept}, "sm", resamples=300)
    assert out["sm"]["precision"] == pytest.approx(10 / 15) and out["filter"]["precision"] == 1.0
    assert out["filter"]["precision_diff"] == pytest.approx(1 / 3)
    lo, hi = out["filter"]["precision_diff_ci"]
    assert 0 < lo <= 1 / 3 <= hi < 1          # paired: the gain is never negative
    assert out["filter"]["recall_diff"] == 0 and out["filter"]["recall_diff_ci"] == (0.0, 0.0)
    assert sp.by_cluster(np.ones((4, 7), dtype=np.int64), ["a", "b", "a", "a"])[:, 0].tolist() == [3, 1]


def test_run_group_and_report_without_a_second_model(sp, analyzer, tmp_path):
    path = tmp_path / "made-up.conllu"
    path.write_text(CONLLU)

    class Verbs:
        def tag(self, words):
            return sp.Parse(["VERB"] * len(words))

    group = sp.run_group("made up", sp.load_group([path]), {"sm": analyzer}, {"fake": sp.Cached(Verbs())},
                         resamples=50, examples=2)
    rows = group["rules"]["stacked-nouns"]
    assert rows["sm"]["findings"] == 1 and rows["sm + fake pos"]["findings"] == 0
    assert group["sentences_read_by_second_model"]["sm + fake pos"] == 1
    assert group["examples"]["sm + fake pos"][0] == {"rule": "stacked-nouns", "words": "index shard compaction job",
                                                     "gold_has_it": True}
    text = sp.report_group(group)
    assert "| sm + fake pos | 0 | 1 (1) |" in text and "no treebank here marks" in text
