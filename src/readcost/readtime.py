"""Predicted reading time from eye-tracking data.

A gradient-boosted tree model predicts the mean total reading time (dwell
time, ms) of each word from its length, its frequency, its position, and the
same facts about its neighbours, following the feature model of Cekini et
al. 2026. It was trained on OneStop Eye Movements (ordinary reading, 360
native readers of English newspaper paragraphs) and tested on held-out
OneStop articles and on the Provo Corpus; scripts/reading_time_train.py
builds it and docs/evaluation.md reports its error. Word frequencies come
from FineWeb-Edu. Attribution for all three is in data/READING_TIME_NOTICE.

The estimate is for a document, not a sentence: the model's error is about
19 ms per word on a held-out paragraph, against a mean of about 200.
"""

from __future__ import annotations

import gzip
import json
import math
import re
from functools import lru_cache
from importlib import resources

import numpy as np

from .extract import CODE

# Neighbour values at a paragraph edge: no word before, a sentence end after.
_EDGE_PREV = [0, 0, 0, 0, 0, 0, 7.0, 1]
_EDGE_NEXT = [0, 0, 0, 1, 0, 0, 7.0, 1]
# The longest training paragraph. Past it the trees extrapolate a reading
# time that keeps falling with position, so a text set as one long paragraph
# read 17% faster than the same text in its paragraphs; a longer paragraph's
# positions are scaled into this length instead (docs/evaluation.md).
_MAX_PARAGRAPH = 165


@lru_cache(maxsize=1)
def _zipf() -> tuple[dict[str, float], float]:
    raw = resources.files("readcost").joinpath("data/word_freq.txt.gz").read_bytes()
    lines = gzip.decompress(raw).decode().splitlines()
    total = int(lines[0].split("\t")[1])
    table = {}
    for line in lines[1:]:
        w, k = line.split("\t")
        table[w] = math.log10(int(k) / total * 1e9)
    return table, math.log10(10 / total * 1e9)  # unseen words: below the 20-count cut-off


@lru_cache(maxsize=1)
def _model() -> dict:
    raw = resources.files("readcost").joinpath("data/reading_time_model.json.gz").read_bytes()
    spec = json.loads(gzip.decompress(raw))
    spec["trees"] = [{k: np.asarray(v) for k, v in t.items()} for t in spec["trees"]]
    # All trees padded into (trees, nodes) arrays, so predict walks every tree
    # at once, one level per step, instead of looping over 300 trees.
    width = max(len(t["left"]) for t in spec["trees"])

    def pad(key, fill, dtype):
        out = np.full((len(spec["trees"]), width), fill, dtype=dtype)
        for i, t in enumerate(spec["trees"]):
            out[i, :len(t[key])] = t[key]
        return out
    spec["stacked"] = {"left": pad("left", -1, np.int64), "right": pad("right", -1, np.int64),
                       "feature": pad("feature", 0, np.int64), "threshold": pad("threshold", 0.0, np.float64),
                       "value": pad("value", 0.0, np.float64)}
    return spec


@lru_cache(maxsize=1)
def _stop_words() -> frozenset[str]:
    from spacy.lang.en.stop_words import STOP_WORDS

    return frozenset(STOP_WORDS)


def available() -> bool:
    try:
        _model()
        _zipf()
    except (OSError, ValueError, EOFError):
        return False
    return True


def features(words: list[str]) -> np.ndarray:
    """One row per word, in the order the model was trained with."""
    zipf, floor = _zipf()
    stop = _stop_words()
    n = len(words)
    base = []
    for k, w in enumerate(words):
        c = re.sub(r"[^a-z']", "", w.lower())
        rel = k / max(n - 1, 1)
        index = round(rel * (_MAX_PARAGRAPH - 1)) if n > _MAX_PARAGRAPH else k
        base.append([len(re.sub(r"[^A-Za-z0-9]", "", w)), float(any(ch.isdigit() for ch in w)),
                     float("-" in w), float(bool(re.search(r"[.,;:!?)\"']$", w))), index, rel,
                     zipf.get(c, floor) if c else floor, float(c in stop)])
    rows = []
    for k in range(n):
        prev = base[k - 1] if k else _EDGE_PREV
        nxt = base[k + 1] if k + 1 < n else _EDGE_NEXT
        rows.append(base[k] + [prev[0], nxt[0], prev[6], nxt[6], prev[3], nxt[3]])
    return np.array(rows, dtype=np.float64).reshape(n, 14)


def predict(X: np.ndarray) -> np.ndarray:
    """Predicted ms per word for each row of ``features``."""
    spec = _model()
    out = np.full(len(X), spec["init"])
    if not len(X):
        return out
    rows = np.arange(len(X))
    # scikit-learn compares float32 features with float64 thresholds; do the
    # same, or a value on a split goes down the other branch.
    X = np.asarray(X, dtype=np.float32).astype(np.float64)
    st = spec["stacked"]
    trees = np.arange(st["left"].shape[0])[None, :]
    node = np.zeros((len(X), st["left"].shape[0]), dtype=np.int64)  # (rows, trees)
    while True:
        left = st["left"][trees, node]
        leaf = left == -1
        if leaf.all():
            break
        x = X[rows[:, None], st["feature"][trees, node]]
        go_left = x <= st["threshold"][trees, node]
        node = np.where(leaf, node, np.where(go_left, left, st["right"][trees, node]))
    # Summed tree by tree, in the order scikit-learn adds them.
    for value in (spec["learning_rate"] * st["value"][trees, node]).T:
        out += value
    return out


def paragraph_words(text: str) -> list[str]:
    """Whitespace words, as eye-tracking interest areas are; code spans are left out."""
    return [w for w in text.split() if CODE not in w]


def word_times(text: str) -> list[tuple[int, int, str, float]]:
    """(start, end, word, predicted ms) for each word of one paragraph, read from its start.

    The words are those of ``paragraph_words``, so the times add up to what
    ``estimate`` predicts for the paragraph.
    """
    spans = [(m.start(), m.end(), m.group()) for m in re.finditer(r"\S+", text) if CODE not in m.group()]
    if not spans:
        return []
    ms = predict(features([w for _, _, w in spans]))
    return [(a, b, w, float(t)) for (a, b, w), t in zip(spans, ms)]


def word_times_many(texts: list[str]) -> list[list[tuple[int, int, str, float]]]:
    """``word_times`` for each paragraph, with one model call for all of them."""
    spans = [[(m.start(), m.end(), m.group()) for m in re.finditer(r"\S+", t) if CODE not in m.group()]
             for t in texts]
    blocks = [features([w for _, _, w in sp]) for sp in spans if sp]
    if not blocks:
        return [[] for _ in texts]
    ms = iter(predict(np.vstack(blocks)))
    return [[(a, b, w, float(next(ms))) for a, b, w in sp] for sp in spans]


def estimate(paragraphs: list[str]) -> tuple[int, float]:
    """(words, predicted total ms) over paragraphs, each read from its own start."""
    words, total = 0, 0.0
    for p in paragraphs:
        ws = paragraph_words(p)
        if ws:
            words += len(ws)
            total += float(predict(features(ws)).sum())
    return words, total
