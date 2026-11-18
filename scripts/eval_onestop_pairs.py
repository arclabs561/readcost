"""Do fewer findings go with faster reading? OneStop paragraphs, original against simplified.

    uv run scripts/reading_time_prep.py ROOT        # writes ROOT/texts.jsonl
    uv run python scripts/eval_onestop_pairs.py ROOT/texts.jsonl

OneStop Eye Movements has each paragraph in an advanced and an elementary
version, read by different people. For each pair this takes the difference
(advanced minus elementary) in observed reading time per word, in weighted
findings per 100 words, in mean word length and in mean word frequency. It
then asks whether the difference in findings predicts the difference in
reading time once length and frequency are in the model.

The reading times are the readers' own, not readcost's predictions, and no
rule was tuned on this corpus. Gruteke Klein et al. 2026 ran the same kind
of test for other syntactic measures and found that only word length,
frequency and surprisal predicted the benefit of simplification; this
script leaves surprisal out, so a positive result here is an upper bound.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

HARD, EASY = "adv", "ele"


def pairs(texts: list[dict]) -> list[tuple[dict, dict]]:
    """(advanced, elementary) versions of the same OneStop paragraph."""
    by_key: dict[tuple, dict[str, dict]] = {}
    for t in texts:
        if t.get("corpus") != "onestop":
            continue
        batch, article, level, paragraph = t["id"].split("/")
        by_key.setdefault((batch, article, paragraph), {})[level.lower()[:3]] = t
    return [(v[HARD], v[EASY]) for _, v in sorted(by_key.items()) if HARD in v and EASY in v]


def measures(analyzer, zipf, unseen: float, t: dict) -> tuple[float, float, float, float, dict]:
    """Observed ms per word, weighted findings per 100 words, mean word length,
    mean Zipf frequency, and findings per 100 words for each rule."""
    words = [w for w in t["words"] if w]
    result = analyzer.check_text(" ".join(words), "text")
    bare = [w.strip(".,;:!?\"'()[]").lower() for w in words]
    bare = [w for w in bare if w]
    per_rule: dict[str, float] = {}
    for f in result.findings:
        per_rule[f.feature] = per_rule.get(f.feature, 0.0) + 100.0 / max(result.words, 1)
    return (float(np.mean(t["rt"])), 100.0 * result.points / max(result.words, 1),
            float(np.mean([len(w) for w in bare])), float(np.mean([zipf.get(w, unseen) for w in bare])), per_rule)


def _ols(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    X1 = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    resid = y - X1 @ beta
    total = float(((y - y.mean()) ** 2).sum())
    return beta, 1.0 - float((resid ** 2).sum()) / total if total else 0.0


def fit(d_rt, d_points, d_len, d_zipf, resamples: int = 2000, seed: int = 0) -> dict:
    """Coefficient of the findings difference, with and without the lexical controls.

    The interval is a percentile bootstrap over pairs.
    """
    d_rt, d_points, d_len, d_zipf = (np.asarray(a, dtype=float) for a in (d_rt, d_points, d_len, d_zipf))
    controls = np.column_stack([d_len, d_zipf])
    full = np.column_stack([controls, d_points])
    _, r2_base = _ols(controls, d_rt)
    beta, r2_full = _ols(full, d_rt)
    alone, r2_alone = _ols(d_points[:, None], d_rt)
    rng = np.random.default_rng(seed)
    n = len(d_rt)
    boots = []
    for _ in range(resamples):
        k = rng.integers(0, n, n)
        boots.append(_ols(full[k], d_rt[k])[0][-1])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"pairs": n, "coef": float(beta[-1]), "ci": (float(lo), float(hi)),
            "r2_controls": r2_base, "r2_with_findings": r2_full,
            "coef_alone": float(alone[-1]), "r2_alone": r2_alone,
            "fewer_findings_in_simplified": float(np.mean(d_points > 0)),
            "faster_in_simplified": float(np.mean(d_rt > 0))}


def main(argv: list[str]) -> int:
    from readcost import Analyzer, Config
    from readcost.readtime import _zipf

    texts = [json.loads(line) for line in Path(argv[1]).read_text().splitlines() if line.strip()]
    analyzer = Analyzer(Config())
    zipf, unseen = _zipf()
    rows = [(measures(analyzer, zipf, unseen, a), measures(analyzer, zipf, unseen, e)) for a, e in pairs(texts)]
    if len(rows) < 20:
        print(f"only {len(rows)} pairs; need the OneStop texts from reading_time_prep.py", file=sys.stderr)
        return 2
    d = np.array([[a[k] - e[k] for k in range(4)] for a, e in rows])
    r = fit(d[:, 0], d[:, 1], d[:, 2], d[:, 3])
    print(f"{r['pairs']} paragraph pairs (advanced minus elementary)")
    print(f"simplified version read faster per word in {r['faster_in_simplified']:.0%} of pairs, "
          f"has fewer weighted findings in {r['fewer_findings_in_simplified']:.0%}")
    print(f"findings alone: {r['coef_alone']:+.2f} ms/word per finding point per 100 words (R2 {r['r2_alone']:.3f})")
    print(f"with word length and frequency: {r['coef']:+.2f} ms/word "
          f"(95% CI {r['ci'][0]:+.2f} to {r['ci'][1]:+.2f}); "
          f"R2 {r['r2_controls']:.3f} without findings, {r['r2_with_findings']:.3f} with")
    print("each rule alone, with the same controls (ms/word per finding per 100 words):")
    for rule in sorted({k for a, e in rows for k in (*a[4], *e[4])}):
        d_rule = np.array([a[4].get(rule, 0.0) - e[4].get(rule, 0.0) for a, e in rows])
        if np.count_nonzero(d_rule) < 10:
            print(f"  {rule}: differs in {np.count_nonzero(d_rule)} pairs; too few to fit")
            continue
        rr = fit(d[:, 0], d_rule, d[:, 2], d[:, 3])
        print(f"  {rule}: {rr['coef']:+.2f} (95% CI {rr['ci'][0]:+.2f} to {rr['ci'][1]:+.2f}); "
              f"differs in {np.count_nonzero(d_rule)} pairs")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
