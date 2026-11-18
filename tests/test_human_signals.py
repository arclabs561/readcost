"""The evaluations against human data (scripts/eval_*): loaders, gold constructions and statistics.

Every fixture is made up; no third-party data is read.
"""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from readcost import Analyzer, Config

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _mod(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def analyzer():
    return Analyzer(Config())


STACK = "The index shard compaction job reads the manifest before it starts the merge."
RELATIVE = "The auditors praised the format the reviewers from the regional office expect in every report."
PLAIN = "The cat sat on the mat while the dog slept."


# ------------------------------------------------------------ human_signals

def test_detect_spans_agrees_with_check_text_and_locates_each_finding(analyzer):
    hs = _mod("human_signals")
    text = f"{STACK} {RELATIVE} {PLAIN}"
    sentences = hs.detect_spans(analyzer, text)
    assert len(sentences) == 3 and all(s["checked"] for s in sentences)
    found = sorted(rule for s in sentences for rule, *_ in s["findings"])
    assert found == sorted(f.feature for f in analyzer.check_text(text, "text").findings)
    rule, _sev, first, last = sentences[0]["findings"][0]
    assert rule == "stacked-nouns" and text[first:last] == "index shard compaction job"
    assert not sentences[2]["findings"]
    assert hs.count_rules(sentences)["stacked-nouns"] == 1


def test_detect_spans_marks_a_fragment_as_not_checked(analyzer):
    hs = _mod("human_signals")
    assert [s["checked"] for s in hs.detect_spans(analyzer, "Release notes. " + PLAIN)] == [False, True]


def test_lexical_counts_words_letters_and_frequency():
    hs = _mod("human_signals")
    words, letters, freq = hs.lexical("The cat, the dog.", {"the": 7.0, "cat": 5.0}, 2.0)
    assert words == 4 and letters == 3.0 and freq == (7 + 5 + 7 + 2) / 4


def test_ranks_share_ties_and_spearman_ignores_scale():
    hs = _mod("human_signals")
    assert list(hs.ranks([10, 20, 20, 5])) == [2.0, 3.5, 3.5, 1.0]
    assert hs.spearman([1, 2, 3, 4], [1, 10, 100, 1000]) == pytest.approx(1.0)


def test_partial_spearman_removes_what_the_control_explains():
    hs = _mod("human_signals")
    rng = np.random.default_rng(0)
    z = rng.normal(size=400)
    x, y = z + 0.3 * rng.normal(size=400), z + 0.3 * rng.normal(size=400)
    assert hs.spearman(x, y) > 0.8
    assert abs(hs.partial_spearman(x, y, z)) < 0.15


def test_cluster_bootstrap_is_wider_when_rows_of_a_group_move_together():
    hs = _mod("human_signals")
    rng = np.random.default_rng(1)
    group_means = rng.normal(size=20)
    values = np.repeat(group_means, 30)
    groups = np.repeat(np.arange(20), 30)
    lo, hi = hs.cluster_bootstrap(lambda k: float(values[k].mean()), groups, 500)
    lo_rows, hi_rows = hs.cluster_bootstrap(lambda k: float(values[k].mean()), np.arange(600), 500)
    assert hi - lo > 3 * (hi_rows - lo_rows)


def test_coefficient_recovers_a_planted_effect_and_reports_none_for_noise():
    hs = _mod("human_signals")
    rng = np.random.default_rng(2)
    n = 300
    control, target = rng.normal(size=n), (rng.random(n) < 0.3).astype(float)
    y = 5 * control + 2 * target + rng.normal(size=n)
    r = hs.coefficient(y, target, control, np.arange(n), 300)
    assert 1.5 < r["coef"] < 2.5 and r["ci"][0] > 0 and r["r2_with"] > r["r2_controls"]
    null = hs.coefficient(5 * control + rng.normal(size=n), target, control, np.arange(n), 300)
    assert null["ci"][0] < 0 < null["ci"][1]


# ----------------------------------------------------------- Natural Stories

def _story_root(tmp_path):
    rts = tmp_path / "naturalstories_RTS"
    probs = tmp_path / "probs"
    rts.mkdir()
    probs.mkdir()
    words = (STACK + " " + PLAIN).split()
    (rts / "all_stories.tok").write_text(
        "word\tzone\titem\n" + "".join(f"{w}\t{k + 1}\t1\n" for k, w in enumerate(words)), encoding="utf-8")
    (rts / "processed_RTs.tsv").write_text(
        "WorkerId\tWorkTimeInSeconds\tcorrect\titem\tzone\tRT\tword\n"
        + "".join(f"r{r}\t1\t6\t1\t{k + 1}\t{300 + 10 * r + k}\t{w}\n" for r in (1, 2) for k, w in enumerate(words)),
        encoding="utf-8")
    lines = ["token,logprob,offset,model,time,id,story", "The,,0,m,0,x,0"]
    for w in words[1:]:
        lines += [f" {w[:2]},-1.0,0,m,0,x,0", f"{w[2:]},-2.0,0,m,0,x,0"] if len(w) > 2 else [f" {w},-1.0,0,m,0,x,0"]
    (probs / "all_stories_gpt3.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tmp_path, words


def test_natural_stories_readers_and_surprisal_summed_over_subword_tokens(tmp_path):
    ns = _mod("eval_naturalstories_rt")
    root, words = _story_root(tmp_path)
    stories = ns.read_stories(root)
    assert stories == {1: words}
    bits = ns.read_surprisal(root, stories)[1]
    assert bits[0] != bits[0]                              # the first word has no probability
    assert bits[1] == pytest.approx(3 / np.log(2))         # "index" = " in" + "dex"
    assert bits[words.index("it")] == pytest.approx(1 / np.log(2))
    times = ns.read_times(root)
    assert len(times) == 2 * len(words) and times[0] == ("r1", 1, 1, 310.0)


def test_natural_stories_word_table_marks_the_words_inside_a_finding(tmp_path, analyzer):
    ns = _mod("eval_naturalstories_rt")
    root, words = _story_root(tmp_path)
    stories = ns.read_stories(root)
    rows = ns.word_table(analyzer, {"the": 7.0}, 2.0, stories, ns.read_surprisal(root, stories))
    assert [r["zone"] for r in rows] == list(range(1, len(words) + 1))
    inside = [words[r["zone"] - 1] for r in rows if "stacked-nouns" in r["rules"]]
    assert inside == ["index", "shard", "compaction", "job"]
    assert {r["sentence"][1] for r in rows} == {0, 1}
    assert all("stacked-nouns" in r["sentence_rules"] for r in rows if r["sentence"][1] == 0)
    assert not any(r["sentence_rules"] for r in rows if r["sentence"][1] == 1)
    assert [r["final"] for r in rows].count(True) == 2 and rows[0]["zipf"] == 7.0


def _synthetic_words(n=600, sentences=60, seed=3):
    rng = np.random.default_rng(seed)
    rows = []
    for k in range(n):
        s = k * sentences // n
        flagged = s % 4 == 0 and (k % 10) < 4
        rows.append({"story": 1 + s % 2, "zone": k + 1, "sentence": (1 + s % 2, s), "position": k % 10,
                     "letters": int(rng.integers(1, 10)), "zipf": float(rng.uniform(2, 7)),
                     "surprisal": float(rng.uniform(1, 15)), "checked": True,
                     "rules": ["long-dependency"] if flagged else [],
                     "sentence_rules": ["long-dependency"] if s % 4 == 0 else [], "final": k % 10 == 9})
    return rows, rng


def test_item_and_reader_fits_recover_a_planted_slowdown_inside_spans():
    ns = _mod("eval_naturalstories_rt")
    rows, rng = _synthetic_words()
    slow = 0.10
    times = []
    for reader in range(12):
        for r in rows:
            mu = 5.7 + 0.02 * r["letters"] + 0.01 * r["surprisal"] + slow * bool(r["rules"]) + 0.05 * reader
            times.append((f"r{reader}", r["story"], r["zone"], float(np.exp(mu + rng.normal(scale=0.05)))))
    by = {}
    for _, story, zone, rt in times:
        by.setdefault((story, zone), []).append(np.log(rt))
    log_rt = {k: float(np.mean(v)) for k, v in by.items()}
    item = ns.item_fit(rows, log_rt, lambda r: bool(r["rules"]), resamples=200)
    assert item["flagged"] > 30 and 0.07 < item["coef"] < 0.13 and item["ci"][0] > 0
    reader = ns.reader_fit(rows, times, lambda r: bool(r["rules"]), resamples=200)
    assert reader["readers"] == 12 and 0.07 < reader["coef"] < 0.13 and reader["ci"][0] > 0


def test_sentence_fit_finds_no_effect_when_flagged_sentences_are_only_longer():
    ns = _mod("eval_naturalstories_rt")
    rng = np.random.default_rng(4)
    sents = []
    for k in range(200):
        words = int(rng.integers(5, 40))
        sents.append({"sentence": (1 + k % 2, k), "story": 1 + k % 2, "index": k // 2, "words": words,
                      "ms": 300 + 20 * np.log(words) + rng.normal(scale=5), "letters": 4.0 + rng.normal(scale=0.3),
                      "zipf": 5.0 + rng.normal(scale=0.3), "surprisal": 7.0 + rng.normal(scale=1.0),
                      "rules": ["inline-list"] if words > 25 else [], "checked": True})
    r = ns.sentence_fit(sents, lambda s: bool(s["rules"]), resamples=300)
    assert r["flagged"] > 20 and r["ci"][0] < 0 < r["ci"][1]


# ------------------------------------------------------------ gold treebank

def _token(i, form, lemma, upos, xpos, head, deprel, misc="_", feats="_"):
    return "\t".join([str(i), form, lemma, upos, xpos, feats, str(head), deprel, "_", misc])


CONLLU = "\n".join([
    "# newdoc id = GUM_academic_made_up",
    "# sent_id = 1",
    "# text = The index shard compaction job reads the team's manifest.",
    _token(1, "The", "the", "DET", "DT", 5, "det"),
    _token(2, "index", "index", "NOUN", "NN", 5, "compound"),
    _token(3, "shard", "shard", "NOUN", "NN", 4, "compound"),
    _token(4, "compaction", "compaction", "NOUN", "NN", 5, "compound"),
    _token(5, "job", "job", "NOUN", "NN", 6, "nsubj"),
    _token(6, "reads", "read", "VERB", "VBZ", 0, "root"),
    _token(7, "the", "the", "DET", "DT", 8, "det"),
    "8-9\tteam's\t_\t_\t_\t_\t_\t_\t_\t_",
    _token(8, "team", "team", "NOUN", "NN", 10, "nmod:poss"),
    _token(9, "'s", "'s", "PART", "POS", 8, "case"),
    _token(10, "manifest", "manifest", "NOUN", "NN", 6, "obj", "SpaceAfter=No"),
    "10.1\tcopy\tcopy\tVERB\tVB\t_\t_\t_\t6:conj\tCopyOf=6",
    _token(11, ".", ".", "PUNCT", ".", 6, "punct"),
    "",
    "# newdoc id = GUM_fiction_made_up",
    "# sent_id = 2",
    "# text = The auditors praised the format the reviewers expect.",
    _token(1, "The", "the", "DET", "DT", 2, "det"),
    _token(2, "auditors", "auditor", "NOUN", "NNS", 3, "nsubj"),
    _token(3, "praised", "praise", "VERB", "VBD", 0, "root"),
    _token(4, "the", "the", "DET", "DT", 5, "det"),
    _token(5, "format", "format", "NOUN", "NN", 3, "obj"),
    _token(6, "the", "the", "DET", "DT", 7, "det"),
    _token(7, "reviewers", "reviewer", "NOUN", "NNS", 8, "nsubj"),
    _token(8, "expect", "expect", "VERB", "VBP", 5, "acl:relcl", "Cxn=rc-red-obj|SpaceAfter=No"),
    _token(9, ".", ".", "PUNCT", ".", 3, "punct"),
    "",
]) + "\n"


@pytest.fixture()
def treebank(tmp_path):
    tb = _mod("eval_gold_treebank")
    path = tmp_path / "made_up.conllu"
    path.write_text(CONLLU, encoding="utf-8")
    return tb, list(tb.read_conllu(path))


def test_conllu_reader_rebuilds_text_and_offsets_through_multiword_tokens(treebank):
    tb, sentences = treebank
    (meta, first), (_, second) = sentences
    assert meta["doc"] == "GUM_academic_made_up" and len(first) == 11
    text = tb.text_of(first)
    assert text == "The index shard compaction job reads the team's manifest."
    assert all(text[t["start"]:t["end"]] == t["form"] for t in first)
    assert first[5]["head"] == -1 and first[4]["head"] == 5
    assert second[7]["cxn"] == ["rc-red-obj"]


def test_gold_stack_is_three_or_more_nouns_in_one_compound_and_names_are_not_targets(treebank):
    tb, sentences = treebank
    tokens = sentences[0][1]
    (stack,) = tb.gold_stacks(tokens)
    assert tb.text_of(tokens)[stack["start"]:stack["end"]] == "index shard compaction job" and stack["target"]
    assert tb.gold_stacks(sentences[1][1]) == []
    for i in (1, 2):
        tokens[i]["form"] = tokens[i]["form"].capitalize()
    assert tb.gold_stacks(tokens)[0]["target"] is False


def test_gold_reduced_relative_comes_from_the_annotation_and_pronoun_subjects_are_not_targets(treebank):
    tb, sentences = treebank
    tokens = sentences[1][1]
    (rel,) = tb.gold_reduced_relatives(tokens)
    assert rel["object"] and rel["target"]
    assert tb.text_of(tokens)[rel["start"]:rel["end"]] == "format the reviewers expect"
    assert tb.gold_relative_verbs(tokens) == [rel["verb"]]
    tokens[6]["upos"] = "PRON"
    assert tb.gold_reduced_relatives(tokens)[0]["target"] is False
    tokens[7]["cxn"] = ["rc-red-obl-pstrand"]
    assert tb.gold_reduced_relatives(tokens)[0]["object"] is False


def _copular(gap):
    """'The file <gap words> is a manifest .' in UD: the predicate noun heads the clause."""
    forms = ["The", "file", *gap, "is", "a", "manifest", "."]
    n = len(forms)
    pred = n - 2
    toks = []
    for k, form in enumerate(forms):
        t = {"form": form, "lemma": form.lower(), "upos": "X", "xpos": "X", "feats": "", "head": pred,
             "deprel": "dep", "cxn": [], "space": True}
        toks.append(t)
    toks[0].update(upos="DET", xpos="DT", head=1, deprel="det")
    toks[1].update(upos="NOUN", xpos="NN", head=pred, deprel="nsubj")
    for k in range(2, 2 + len(gap)):
        toks[k].update(upos="ADV", xpos="RB", head=1, deprel="advmod")
    toks[n - 4].update(upos="AUX", xpos="VBZ", head=pred, deprel="cop")
    toks[n - 3].update(upos="DET", xpos="DT", head=pred, deprel="det")
    toks[pred].update(upos="NOUN", xpos="NN", head=-1, deprel="root")
    toks[n - 1].update(upos="PUNCT", xpos=".", head=pred, deprel="punct")
    pos = 0
    for t in toks:
        t["start"], t["end"] = pos, pos + len(t["form"])
        pos = t["end"] + 1
    return toks


def test_core_arcs_measure_a_copular_subject_to_the_copula_not_the_predicate():
    tb = _mod("eval_gold_treebank")
    toks = _copular(["really"] * 9)
    arcs = {(toks[d]["form"], toks[h]["form"]): dist for dist, d, h in tb.core_arcs(toks)}
    assert arcs == {("file", "is"): 10, ("manifest", "is"): 2}
    (long,) = tb.gold_long_dependencies(toks)
    assert long["distance"] == 10 and tb.gold_long_dependencies(toks, 15) == []
    assert tb.long_dependency_applies(toks) and not tb.long_dependency_applies(_copular([]))


def test_conversion_puts_the_copula_and_the_preposition_on_top():
    tb = _mod("eval_gold_treebank")
    toks = _copular(["really"])
    heads, deps = tb.to_readcost_scheme(toks)
    cop = next(k for k, t in enumerate(toks) if t["form"] == "is")
    assert heads[cop] == -1 and deps[cop] == "ROOT"
    assert heads[1] == cop and deps[1] == "nsubj"
    assert heads[len(toks) - 2] == cop and deps[len(toks) - 2] == "attr"
    # "reads from disk": disk <-obl- reads, from <-case- disk
    pp = [{"form": f, "lemma": f, "upos": u, "xpos": x, "feats": "", "head": h, "deprel": d, "cxn": [], "space": True}
          for f, u, x, h, d in (("It", "PRON", "PRP", 1, "nsubj:pass"), ("reads", "VERB", "VBZ", -1, "root"),
                                ("from", "ADP", "IN", 3, "case"), ("disk", "NOUN", "NN", 1, "obl"))]
    heads, deps = tb.to_readcost_scheme(pp)
    assert heads == [1, -1, 1, 2] and deps == ["nsubjpass", "ROOT", "prep", "pobj"]


def test_tally_counts_overlap_both_ways_and_wilson_brackets_the_share():
    tb = _mod("eval_gold_treebank")
    t = tb.Tally()
    t.add([(0, 5), (20, 30)], [(3, 8), (40, 50)])
    assert (t.right, t.findings, t.found, t.references) == (1, 2, 1, 2)
    t.add([(0, 5)], [], correct=[(4, 6)])
    assert t.precision == pytest.approx(2 / 3) and t.recall == 0.5
    lo, hi = tb.wilson(8, 10)
    assert 0.45 < lo < 0.8 < hi < 0.97 and tb.wilson(0, 0)[0] != tb.wilson(0, 0)[0]


def test_score_matches_parser_findings_to_gold_and_to_the_rules_on_the_gold_tree(treebank, analyzer, capsys):
    tb, sentences = treebank
    result = tb.score(analyzer, sentences)
    t = result["tallies"]
    assert result["sentences"] == 2 and result["has_cxn"]
    stack = t["stack/gold"]
    assert (stack.right, stack.findings, stack.found, stack.references) == (1, 1, 1, 1)
    assert t["stack/tree"].precision == 1.0 and t["stack/tree"].recall == 1.0
    rel = t["relative/object"]
    assert (rel.right, rel.findings, rel.found, rel.references) == (1, 1, 1, 1)
    assert t["relative/tree"].recall == 1.0
    assert t["dependency/gold"].findings == 0
    tb.report(result)
    out = capsys.readouterr().out
    assert "precision 1/1 = 100%" in out and "reduced object relatives" in out


def test_gold_tree_findings_run_the_detectors_without_the_parser(treebank, analyzer):
    tb, sentences = treebank
    tokens = sentences[0][1]
    found = tb.gold_tree_findings(analyzer, tokens)
    assert [(rule, tb.text_of(tokens)[a:b]) for rule, a, b in found] == [("stacked-nouns", "index shard compaction job")]


# ----------------------------------------------------- simplification ratings

def test_asset_loader_averages_raters_per_aspect(tmp_path):
    sr = _mod("eval_simplicity_ratings")
    (tmp_path / "human_ratings").mkdir()
    (tmp_path / "human_ratings" / "human_ratings.csv").write_text(
        "original,simplification,original_sentence_id,aspect,worker_id,rating\n"
        'A long one.,"Short, one.",7,simplicity,1,60\nA long one.,"Short, one.",7,simplicity,2,80\n'
        'A long one.,"Short, one.",7,fluency,1,90\n', encoding="utf-8")
    (row,) = sr.load_asset(tmp_path)
    assert row["group"] == "7" and row["simplified"] == "Short, one."
    assert row["simplicity"] == 70.0 and row["fluency"] == 90.0


def test_simpeval_loader_drops_control_systems_and_averages_z_scores(tmp_path):
    sr = _mod("eval_simplicity_ratings")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "simpeval_2022.csv").write_text(
        "original_id,original,generation,system,rating_1,rating_2,rating_1_zscore,rating_2_zscore\n"
        "3,Orig.,Simple.,Human 1 Writing,90,70,1.0,0.5\n3,Orig.,Orig.,copy,10,10,-1,-1\n", encoding="utf-8")
    (row,) = sr.load_simpeval(tmp_path, "simpeval_2022.csv")
    assert row["system"] == "Human 1 Writing" and row["simplicity"] == 0.75 and row["fluency"] != row["fluency"]


def test_llm_and_da_loaders_read_their_formats(tmp_path):
    sr = _mod("eval_simplicity_ratings")
    likert = tmp_path / "annotation" / "likert" / "exclude_newsela"
    likert.mkdir(parents=True)
    (likert / "likert_gpt.json").write_text(json.dumps([{
        "id": 1, "source_file": "turk", "source_id": 9, "model": "gpt", "source": "Orig.", "simple": "Simple.",
        "label_annotations": {"annotator_1": {"fluency": 3, "meaning preservation": 3, "simplicity": 2},
                              "annotator_2": {"fluency": 3, "meaning preservation": 2, "simplicity": 3}}}]),
        encoding="utf-8")
    (row,) = sr.load_llm(tmp_path)
    assert row["group"] == "turk/9" and row["system"] == "gpt" and row["simplicity"] == 2.5 and row["fluency"] == 3.0
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "simplicity_DA.csv").write_text(
        "sent_id,sys_name,orig_sent,simp_sent,sys_type,fluency,fluency_zscore,meaning,meaning_zscore,"
        "simplicity,simplicity_zscore\n1,ACCESS,Orig.,Simple.,x,70,0.2,70,0.1,60,-0.4\n", encoding="utf-8")
    (row,) = sr.load_da(tmp_path)
    assert row["simplicity"] == -0.4 and row["fluency"] == 0.2 and row["system"] == "ACCESS"


def test_measure_counts_findings_on_both_sides(analyzer):
    sr = _mod("eval_simplicity_ratings")
    rows = [{"group": "1", "original": STACK, "simplified": PLAIN, "system": "s", "simplicity": 1.0,
             "fluency": 1.0},
            {"group": "2", "original": PLAIN, "simplified": "", "system": "s", "simplicity": 1.0, "fluency": 1.0}]
    (row,) = sr.measure(analyzer, {}, 3.0, rows)
    assert row["o_findings"] == 1 and row["o_rules"] == {"stacked-nouns": 1} and row["s_findings"] == 0
    assert row["s_words"] == 10 and row["s_zipf"] == 3.0


def _rated_pairs(effect, n=400, seed=5):
    rng = np.random.default_rng(seed)
    rows = []
    for k in range(n):
        o_findings = int(rng.random() < 0.5)
        s_findings = int(o_findings and rng.random() < 0.5)
        words = int(rng.integers(8, 30))
        rows.append({"group": str(k // 4), "system": "a" if k % 2 else "b", "o_findings": o_findings,
                     "s_findings": s_findings, "o_words": words + 5, "s_words": words,
                     "s_letters": 4.5 + rng.normal(scale=0.3), "s_zipf": 5 + rng.normal(scale=0.3),
                     "simplicity": -0.02 * words - effect * s_findings + rng.normal(scale=0.3),
                     "fluency": float("nan")})
    return rows


def test_summarize_finds_a_planted_link_between_findings_and_ratings():
    sr = _mod("eval_simplicity_ratings")
    s = sr.summarize(_rated_pairs(effect=0.6), resamples=200)
    assert s["pairs"] == 400 and s["originals"] == 100 and s["mean_delta"] < 0 and s["mean_delta_ci"][1] < 0
    assert s["partial"][0] < -0.3 and s["partial"][1][1] < 0
    coef, ci, _std = s["removed_effect"]
    assert 0.4 < coef < 0.8 and ci[0] > 0


def test_summarize_reports_a_null_and_by_system_ranks_by_rate():
    sr = _mod("eval_simplicity_ratings")
    rows = _rated_pairs(effect=0.0)
    s = sr.summarize(rows, resamples=200)
    assert s["partial"][1][0] < 0 < s["partial"][1][1]
    assert s["removed_effect"][1][0] < 0 < s["removed_effect"][1][1]
    systems = sr.by_system(rows)
    assert {name for name, *_ in systems} == {"a", "b"} and systems[0][2] >= systems[1][2]


# ------------------------------------------------------------ rated sentences

def test_rated_sentence_loader_averages_readers_and_skips_unlinked_rows(tmp_path):
    rs = _mod("eval_rated_sentences")
    (tmp_path / "dataset").mkdir()
    (tmp_path / "dataset" / "sentences.csv").write_text(
        "sentence_uid,doc_pair_id,variant,sentence_text\nt1__s1,1,orig,An original sentence.\n"
        "t1_simp__s1,1,simp,A plain one.\n", encoding="utf-8")
    (tmp_path / "dataset" / "annotations.csv").write_text(
        "sentence_uid,processing_ease,perceived_understanding,included_in_paper_sentence_analysis\n"
        "t1__s1,2,3,True\nt1__s1,4,3,True\nt1_simp__s1,5,5,True\nt1_simp__s1,5,4,True\n"
        "t1_simp__s1,1,1,False\n,3,3,True\n", encoding="utf-8")
    rows = rs.load(tmp_path)
    assert [(r["uid"], r["simplified"], r["processing_ease"], r["perceived_understanding"]) for r in rows] == [
        ("t1__s1", False, 3.0, 3.0), ("t1_simp__s1", True, 5.0, 4.5)]


def test_rated_sentence_summary_separates_length_from_findings(analyzer):
    rs = _mod("eval_rated_sentences")
    measured = rs.measure(analyzer, {}, 3.0, [
        {"uid": "a", "text": STACK, "group": "1", "simplified": False, "processing_ease": 2.0,
         "perceived_understanding": 2.0}])
    assert measured[0]["findings"] == 1 and measured[0]["words"] == 13
    rng = np.random.default_rng(6)
    rows = []
    for k in range(300):
        words = int(rng.integers(5, 40))
        flagged = words > 22 and rng.random() < 0.6
        rows.append({"group": str(k // 10), "simplified": bool(k % 2), "words": words,
                     "letters": 5 + rng.normal(scale=0.4), "zipf": 5 + rng.normal(scale=0.4),
                     "findings": int(flagged), "rules": {"stacked-nouns": 1} if flagged else {},
                     "processing_ease": 5 - 0.06 * words + rng.normal(scale=0.3),
                     "perceived_understanding": 4.0})
    s = rs.summarize(rows, "processing_ease", resamples=200)
    assert s["rho"]["any finding"][0] < -0.2            # flagged sentences are rated harder ...
    assert s["effect"]["ci"][0] < 0 < s["effect"]["ci"][1]   # ... but only because they are longer
    assert s["rules"]["stacked-nouns"][0] == s["flagged"]
