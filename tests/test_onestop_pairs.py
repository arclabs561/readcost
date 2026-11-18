"""scripts/eval_onestop_pairs.py: pairing and the paired regression, on made-up data."""

import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def _mod():
    spec = importlib.util.spec_from_file_location("eval_onestop_pairs", ROOT / "scripts" / "eval_onestop_pairs.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _text(ident, corpus="onestop"):
    return {"corpus": corpus, "id": ident, "words": ["a"], "rt": [1.0]}


def test_pairs_match_levels_of_the_same_paragraph_and_skip_the_rest():
    m = _mod()
    texts = [_text("1/2/Adv/3"), _text("1/2/Ele/3"), _text("1/2/Adv/4"), _text("7", corpus="provo")]
    got = m.pairs(texts)
    assert [(a["id"], e["id"]) for a, e in got] == [("1/2/Adv/3", "1/2/Ele/3")]


def test_fit_recovers_an_effect_of_findings_beyond_the_controls():
    rng = np.random.default_rng(1)
    n = 160
    d_len, d_zipf, d_points = rng.normal(size=n), rng.normal(size=n), rng.normal(size=n)
    d_rt = 10 * d_len - 6 * d_zipf + 3 * d_points + rng.normal(scale=1.0, size=n)
    r = _mod().fit(d_rt, d_points, d_len, d_zipf, resamples=300)
    assert r["pairs"] == n and 2.5 < r["coef"] < 3.5
    assert r["ci"][0] > 0 and r["r2_with_findings"] > r["r2_controls"]


def test_fit_reports_no_effect_when_findings_only_track_word_length():
    rng = np.random.default_rng(2)
    n = 160
    d_len, d_zipf = rng.normal(size=n), rng.normal(size=n)
    d_points = d_len + rng.normal(scale=0.5, size=n)  # correlated with length, no effect of its own
    d_rt = 10 * d_len - 6 * d_zipf + rng.normal(scale=1.0, size=n)
    r = _mod().fit(d_rt, d_points, d_len, d_zipf, resamples=300)
    assert r["ci"][0] < 0 < r["ci"][1]
    assert r["coef_alone"] > 2  # alone it looks predictive; the controls remove that
