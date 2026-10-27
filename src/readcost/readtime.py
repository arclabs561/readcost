"""Predicted reading time from eye-tracking data.

A gradient-boosted tree model predicts the mean total reading time (dwell
time, ms) of each word from its length, its frequency, its position, and the
same facts about its neighbours, following the feature model of Cekini et
al. 2026. It was trained on OneStop Eye Movements (ordinary reading, 360
native readers of English newspaper paragraphs) and tested on held-out
OneStop articles and on the Provo Corpus; scripts/build_reading_time.py
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
        base.append([len(re.sub(r"[^A-Za-z0-9]", "", w)), float(any(ch.isdigit() for ch in w)),
                     float("-" in w), float(bool(re.search(r"[.,;:!?)\"']$", w))), k, k / max(n - 1, 1),
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
    for t in spec["trees"]:
        node = np.zeros(len(X), dtype=np.int64)
        while True:
            leaf = t["left"][node] == -1
            if leaf.all():
                break
            go_left = X[rows, np.where(leaf, 0, t["feature"][node])] <= t["threshold"][node]
            node = np.where(leaf, node, np.where(go_left, t["left"][node], t["right"][node]))
        out += spec["learning_rate"] * t["value"][node]
    return out


def paragraph_words(text: str) -> list[str]:
    """Whitespace words, as eye-tracking interest areas are; code spans are left out."""
    return [w for w in text.split() if CODE not in w]


def estimate(paragraphs: list[str]) -> tuple[int, float]:
    """(words, predicted total ms) over paragraphs, each read from its own start."""
    words, total = 0, 0.0
    for p in paragraphs:
        ws = paragraph_words(p)
        if ws:
            words += len(ws)
            total += float(predict(features(ws)).sum())
    return words, total
