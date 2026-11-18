"""The pre-registered repetition test (scripts/eval_repetition_prereg.py).

Every fixture is made up; no third-party data is read.
"""

import csv
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _mod(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


pr = _mod("eval_repetition_prereg")

PROSE = ("The cache keeps each block for a minute. When the minute ends, the block is written back "
         "to disk and its slot is freed. Readers that arrive after that point load the block again, "
         "which costs one more read but keeps memory bounded. Writers never wait for readers, because "
         "each write goes to a fresh slot and the old block stays readable until the swap. ")


def test_measurement_code_matches_the_preregistration():
    assert pr.verify() == []


def test_verify_reports_a_changed_file(tmp_path):
    for rel in pr.MEASUREMENT_SHA256:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("changed\n")
    assert len(pr.verify(tmp_path)) == len(pr.MEASUREMENT_SHA256)


def test_eight_tests_two_measures_four_datasets():
    assert set(pr.MEASURES) == {"M1", "M2"}
    assert set(pr.DATASETS) == {"D1", "D2", "D3", "D4"}
    assert pr.MEASURES["M1"][0] == "given_rate" and pr.MEASURES["M2"][0] == "restatement"
    assert all(spec["sign"] == -1 for spec in pr.DATASETS.values())


def test_html_prose_drops_code_and_quotes_and_keeps_paragraphs():
    html = ("<p>Use <code>ls -l</code> to list files &amp; folders.</p>"
            "<pre><code>ls -l /tmp\n</code></pre>"
            "<blockquote><p>Someone else wrote this.</p></blockquote>"
            "<ul><li>First point</li><li>Second<br>point</li></ul>")
    out = pr.html_prose(html)
    assert out.split("\n\n") == ["Use to list files & folders.", "First point", "Second", "point"]
    assert "ls -l" not in out and "Someone" not in out


def test_prose_words_ignores_markdown_code():
    assert pr.prose_words("one two\n\n```\nthree four five\n```\n`six` seven", "markdown") == 3
    assert pr.prose_words("one two `three`", "text") == 3


def test_holm_matches_hand_computation():
    adj = pr.holm([0.01, 0.04, 0.03, 0.005])
    # sorted: 0.005*4=0.02, 0.01*3=0.03, 0.03*2=0.06, 0.04*1=0.04 -> running max 0.06
    assert adj == pytest.approx([0.03, 0.06, 0.06, 0.02])
    assert pr.holm([1.0, 0.9]) == [1.0, 1.0]


def test_cluster_se_with_singleton_clusters_is_hc1():
    rng = np.random.default_rng(1)
    x = rng.normal(size=40)
    y = 0.3 * x + rng.normal(size=40)
    beta = float(x @ y / (x @ x))
    e = y - beta * x
    want = math.sqrt(40 / 39 * float(((x * e) ** 2).sum())) / float(x @ x)
    assert pr.cluster_se(y, x, beta, np.arange(40).astype(str)) == pytest.approx(want)


def test_prepare_drops_singleton_groups_and_demeans():
    y = np.array([1.0, 3.0, 5.0, 7.0, 9.0])
    x = np.array([0.0, 2.0, 1.0, 1.0, 4.0])
    C = np.ones((5, 3))
    g = np.array(["a", "a", "b", "b", "c"])
    yd, xd, Cd, groups = pr._prepare(y, x, C, g)
    assert list(groups) == ["a", "a", "b", "b"]
    assert list(yd) == [-1.0, 1.0, -1.0, 1.0]
    assert list(xd) == [-1.0, 1.0, 0.0, 0.0]


def _planted(effect, n_groups=400, per=3, seed=0):
    rng = np.random.default_rng(seed)
    g = np.repeat(np.arange(n_groups), per).astype(str)
    length = rng.normal(5, 0.5, len(g))
    C = np.column_stack([length, rng.normal(4.5, 0.3, len(g)), rng.normal(5, 0.2, len(g))])
    x = 0.5 * length + rng.normal(size=len(g))
    y = effect * x + 2.0 * length + np.repeat(rng.normal(size=n_groups), per) + rng.normal(size=len(g))
    return y, x, C, g


def test_planted_effect_passes_and_length_alone_does_not():
    pytest.importorskip("scipy")
    res = pr.test(*_planted(0.4), resamples=200)
    assert res["ran"] and res["r"] > 0.2 and res["p"] < 1e-6
    lo, hi = res["ci"]
    assert lo < res["r"] < hi
    assert pr.label(res, pr.holm([res["p"]] * 8)[0]) == "pass"
    null = pr.test(*_planted(0.0), resamples=0)
    assert abs(null["r"]) < 0.1
    assert pr.label(null, 1.0) in ("below the smallest effect", "inconclusive")


def test_labels():
    base = {"ran": True, "r": 0.10, "se": 0.01}
    assert pr.label(base, 0.001) == "pass"
    assert pr.label({**base, "r": 0.03}, 0.001) == "below the smallest effect"   # significant but too small
    assert pr.label({**base, "r": -0.05}, 1.0) == "below the smallest effect"
    assert pr.label({**base, "r": 0.06, "se": 0.05}, 0.2) == "inconclusive"
    assert pr.label({"ran": False}, 1.0) == "not run"


def test_claims_need_m1_to_pass_in_every_dataset_of_the_claim():
    tests = [{"dataset": d, "measure": m, "label": "pass" if (d, m) in {("D1", "M1"), ("D2", "M1"), ("D3", "M2")}
              else "inconclusive"} for d in pr.DATASETS for m in pr.MEASURES]
    got = {text: holds for text, holds, _ in pr.claims(tests)}
    assert got == {"The discovery replicates on new model text": True,
                   "Repetition predicts reader judgements of technical text": False,
                   "Repetition predicts reader judgements of human-written text": False}


def test_missing_dataset_is_not_run_and_keeps_its_place_in_the_family():
    tests = pr.preregistered({}, resamples=0)
    assert len(tests) == 8
    assert all(t["label"] == "not run" and t["p_holm"] == 1.0 for t in tests)


def test_ellipse_loader(tmp_path):
    d = tmp_path / "ellipse"
    d.mkdir()
    with open(d / "ELLIPSE_Final_github_train.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["text_id_kaggle", "full_text", "prompt"] + list(pr.ELLIPSE_SCORES))
        w.writerow(["a1", PROSE * 2, "Phones at school", 3, 3.5, 3, 3, 3, 3, 3])
        w.writerow(["a2", "Too short.", "Phones at school", 3, 3, 3, 3, 3, 3, 3])
        w.writerow(["a3", PROSE, "Summer projects", 2.5, 2, 3, 3, 3, 3, 3])
    items = pr.load_ellipse(tmp_path)
    assert [i["id"] for i in items] == ["a1", "a3"]
    assert items[0]["group"] == "Phones at school" and items[0]["outcomes"]["cohesion"] == 3.5


def _parquet(path, rows):
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path)


def test_helpsteer3_code_loader_keeps_code_pairs_and_splits_preference(tmp_path):
    rows = [{"domain": "code", "response1": PROSE, "response2": PROSE + "Also.", "overall_preference": -2},
            {"domain": "general", "response1": PROSE, "response2": PROSE + "No.", "overall_preference": 1},
            {"domain": "code", "response1": PROSE, "response2": PROSE, "overall_preference": 0},
            {"domain": "code", "response1": "```\ncode only\n```", "response2": PROSE, "overall_preference": 3}]
    _parquet(tmp_path / "helpsteer3" / "train.parquet", rows)
    _parquet(tmp_path / "helpsteer3" / "validation.parquet", rows[:1])
    items = pr.load_helpsteer3_code(tmp_path)
    assert [i["id"] for i in items] == ["train:0:1", "train:0:2", "validation:0:1", "validation:0:2"]
    assert [i["outcomes"]["preference"] for i in items] == [2.0, -2.0, 2.0, -2.0]


def test_helpsteer_loader_drops_helpsteer2_duplicates_and_short_answers(tmp_path):
    hs = [{"prompt": "p1", "response": PROSE, "helpfulness": 3, "correctness": 3, "coherence": 4,
           "complexity": 1, "verbosity": 2},
          {"prompt": "p1", "response": PROSE + "Different.", "helpfulness": 2, "correctness": 3, "coherence": 3,
           "complexity": 1, "verbosity": 2},
          {"prompt": "p2", "response": "Short.", "helpfulness": 2, "correctness": 3, "coherence": 3,
           "complexity": 1, "verbosity": 2}]
    _parquet(tmp_path / "helpsteer" / "train.parquet", hs)
    _parquet(tmp_path / "helpsteer" / "validation.parquet", [dict(hs[0], prompt="p3")])
    _parquet(tmp_path / "helpsteer2" / "train.parquet", [{"response": PROSE}])
    _parquet(tmp_path / "helpsteer2" / "validation.parquet", [{"response": "unrelated"}])
    items = pr.load_helpsteer(tmp_path)
    assert [i["id"] for i in items] == ["train:1"]


def test_stackexchange_loader_needs_two_eligible_answers(tmp_path):
    def ans(i, text, score, sel=False):
        return {"answer_id": i, "author": "x", "author_id": 1, "author_profile": "", "pm_score": score,
                "selected": sel, "text": text}
    long = f"<p>{PROSE}</p><pre><code>rm -rf /\n</code></pre>"
    rows = [{"qid": 1, "question": "q", "date": "2020", "metadata": [],
             "answers": [ans(10, long, 3, True), ans(11, long + "<p>More.</p>", 1)]},
            {"qid": 2, "question": "q", "date": "2020", "metadata": [],
             "answers": [ans(20, long, 2), ans(21, "<p>Short.</p>", 0)]}]
    for site in pr.SE_SITES:
        _parquet(tmp_path / "stackexchange" / f"{site}.parquet", rows)
    items = pr.load_stackexchange(tmp_path)
    assert len(items) == 2 * len(pr.SE_SITES)
    first = items[0]
    assert first["group"].endswith(":1") and first["outcomes"] == {"pm_score": 3.0, "accepted": 1.0}
    assert "rm -rf" not in first["text"]


def test_report_runs_on_records_and_lists_every_test(tmp_path):
    pytest.importorskip("scipy")
    y, x, C, g = _planted(0.3, n_groups=60)
    with open(tmp_path / "ellipse.jsonl", "w") as f:
        for k in range(len(y)):
            f.write(json.dumps({"dataset": "ellipse", "group": g[k], "words": int(math.exp(C[k, 0] / 2) + 50),
                                "mean_word_len": C[k, 1], "mean_zipf": C[k, 2],
                                "outcomes": {"cohesion": -y[k], "overall": -y[k]},
                                "patterns": {"given_rate": x[k], "restatement": 0.0},
                                "metrics": {"mtld": 50.0}, "points_per100": 0.0}) + "\n")
    records = pr.load_records(tmp_path)
    tests = pr.preregistered(records, resamples=50)
    out = pr.render(records, tests, 50)
    assert len(re.findall(r"^\| D[1-4]M[12] \|", out, re.M)) == 8
    assert "Exploratory, not pre-registered" in out
    d4m1 = [t for t in tests if t["dataset"] == "D4" and t["measure"] == "M1"][0]
    assert d4m1["ran"] and d4m1["r"] > 0
