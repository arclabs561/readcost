"""Shared helpers for the evaluations against human data.

Used by eval_naturalstories_rt.py, eval_gold_treebank.py,
eval_simplicity_ratings.py and eval_rated_sentences.py. It holds no data and
reads none: the statistics (least squares, cluster bootstrap, partial rank
correlation) and one function that runs readcost's detectors on a text and
keeps the character span of each finding, which `Analyzer.check_text` does
not return.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

RULES = ("stacked-nouns", "long-dependency", "inanimate-subject",
         "reduced-object-relative", "hyphen-compound", "inline-list")


# ----------------------------------------------------------------- readcost

def detect_spans(analyzer, text: str) -> list[dict]:
    """Sentences of ``text`` as readcost splits them, each with its findings and their spans.

    Returns one dict per sentence: ``start`` and ``end`` (character offsets),
    ``checked`` (False for a sentence readcost skips: under four words, or no
    verb), and ``findings``, a list of (rule, severity, first, last) where
    first and last are the character offsets that the finding's tokens cover.
    A rule's tokens are its two ends for long-dependency (the dependent and
    its head), so the span includes the words between them.

    This follows the sentence loop of `Analyzer.analyze` but skips the
    document-level steps: a compound is reported at every use, not only its
    first, and no baseline or severity override applies.
    """
    from readcost.features import NOUN_RUN_RULES, Context, detect, misparsed_verb

    ctx = Context(analyzer.cfg, analyzer.profile, analyzer.allow, analyzer.enabled)
    out = []
    doc = analyzer.nlp(text)
    for sent in doc.sents:
        row = {"start": sent.start_char, "end": sent.end_char, "checked": False, "findings": []}
        out.append(row)
        if len([t for t in sent if t.is_alpha]) < 4:
            continue
        rules = None
        if not any(t.pos_ in ("VERB", "AUX") for t in sent):
            if not misparsed_verb(sent):
                continue
            rules = NOUN_RUN_RULES
        row["checked"] = True
        for rule, severity, _msg, toks in detect(sent, ctx, rules):
            toks = toks or list(sent)  # a slash list is found in the text, with no tokens
            first = min(t.idx for t in toks)
            last = max(t.idx + len(t.text) for t in toks)
            row["findings"].append((rule, severity, first, last))
    return out


def count_rules(sentences: list[dict]) -> dict[str, int]:
    """Findings per rule over the output of `detect_spans`."""
    counts: dict[str, int] = {}
    for s in sentences:
        for rule, *_ in s["findings"]:
            counts[rule] = counts.get(rule, 0) + 1
    return counts


def lexical(text: str, zipf: dict, unseen: float) -> tuple[int, float, float]:
    """Words, mean letters per word and mean Zipf frequency of a text."""
    words = [w.strip(".,;:!?\"'()[]{}-").lower() for w in text.split()]
    words = [w for w in words if w]
    if not words:
        return 0, 0.0, unseen
    return (len(words), float(np.mean([len(w) for w in words])),
            float(np.mean([zipf.get(w, unseen) for w in words])))


# --------------------------------------------------------------- statistics

def ols(X, y) -> tuple[np.ndarray, float]:
    """Least-squares coefficients (intercept first) and R squared."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    X1 = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    resid = y - X1 @ beta
    total = float(((y - y.mean()) ** 2).sum())
    return beta, (1.0 - float((resid ** 2).sum()) / total if total else 0.0)


def ranks(x) -> np.ndarray:
    """Average ranks, ties shared."""
    x = np.asarray(x, dtype=float)
    order = np.argsort(x, kind="mergesort")
    out = np.empty(len(x))
    out[order] = np.arange(1, len(x) + 1)
    values, inverse = np.unique(x, return_inverse=True)
    sums = np.bincount(inverse, weights=out)
    counts = np.bincount(inverse)
    return (sums / counts)[inverse]


def pearson(x, y) -> float:
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if len(x) < 3 or x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def spearman(x, y) -> float:
    return pearson(ranks(x), ranks(y))


def partial_spearman(x, y, controls) -> float:
    """Spearman's rho between x and y with the controls held constant.

    Every variable is ranked; x and y are each regressed on the ranked
    controls, and the residuals are correlated.
    """
    controls = np.asarray(controls, dtype=float)
    if controls.ndim == 1:
        controls = controls[:, None]
    Z = np.column_stack([ranks(controls[:, k]) for k in range(controls.shape[1])])
    rx, ry = ranks(x), ranks(y)
    Z1 = np.column_stack([np.ones(len(rx)), Z])
    ex = rx - Z1 @ np.linalg.lstsq(Z1, rx, rcond=None)[0]
    ey = ry - Z1 @ np.linalg.lstsq(Z1, ry, rcond=None)[0]
    # A fully explained rank vector can leave floating-point noise after the
    # projection. Correlating that noise would turn an undefined result into
    # a coefficient, even 1.0 when the two rank vectors are identical.
    tol = np.finfo(float).eps * max(Z1.shape)
    if (np.linalg.norm(ex) <= tol * np.linalg.norm(rx)
            or np.linalg.norm(ey) <= tol * np.linalg.norm(ry)):
        return float("nan")
    return pearson(ex, ey)


def cluster_bootstrap(stat, groups, resamples: int = 2000, seed: int = 0) -> tuple[float, float]:
    """Percentile 95% interval of ``stat(index_array)``, resampling whole groups.

    ``groups`` gives each row's cluster (an original sentence, a reader, a
    document). Rows of a drawn cluster stay together, so the interval allows
    for rows of one cluster resembling each other. Resamples where the
    statistic is undefined (NaN) are dropped.
    """
    groups = np.asarray(groups)
    labels, inverse = np.unique(groups, return_inverse=True)
    members = [np.flatnonzero(inverse == k) for k in range(len(labels))]
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(resamples):
        drawn = rng.integers(0, len(members), len(members))
        value = stat(np.concatenate([members[k] for k in drawn]))
        if value == value:
            values.append(value)
    if not values:
        return float("nan"), float("nan")
    lo, hi = np.percentile(values, [2.5, 97.5])
    return float(lo), float(hi)


def coefficient(y, target, controls, groups, resamples: int = 2000, seed: int = 0) -> dict:
    """Coefficient of ``target`` in y ~ controls + target, with a cluster bootstrap interval.

    Also returns R squared without and with the target and the coefficient
    in units of y's standard deviation.
    """
    y = np.asarray(y, dtype=float)
    target = np.asarray(target, dtype=float)
    controls = np.asarray(controls, dtype=float)
    if controls.ndim == 1:
        controls = controls[:, None]
    full = np.column_stack([controls, target])
    _, r2_base = ols(controls, y)
    beta, r2_full = ols(full, y)
    lo, hi = cluster_bootstrap(lambda k: ols(full[k], y[k])[0][-1] if target[k].std() > 0 else float("nan"),
                               groups, resamples, seed)
    sd = float(y.std())
    return {"n": len(y), "coef": float(beta[-1]), "ci": (lo, hi), "r2_controls": r2_base,
            "r2_with": r2_full, "standardized": float(beta[-1]) / sd if sd else float("nan")}
