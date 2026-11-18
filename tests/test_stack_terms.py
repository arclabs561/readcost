"""Pair counts and the stack-term measurement (scripts/build_open_pairs.py, scripts/eval_stack_terms.py).

The texts are made up; no corpus is read.
"""

import math
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_open_pairs as bop
import eval_stack_terms as est

DOCS = [
    "The call stack grows. A call stack holds frames.",   # "call stack" twice: one document
    "Each thread has a call stack of frames.",
    "The stack. Call the function; a call-stack dump follows.",  # a full stop or a hyphen is not a space
    "Frames hold registers.",
]


@pytest.fixture
def table(tmp_path):
    vocab = ["call", "stack", "frames", "thread", "holds", "function", "dump"]
    keys, counts, uni, docs, positions = bop.count_texts(DOCS, {w: i for i, w in enumerate(vocab)})
    path = tmp_path / "pairs.npz"
    np.savez_compressed(path, keys=keys, counts=counts.astype(np.int32), uni=uni, docs=docs,
                        positions=positions, vocab=np.array(vocab))
    return bop.Pairs(path)


def test_counts_are_documents_not_occurrences(table):
    assert table.docs == 4
    assert table.df("call", "stack") == 2
    assert table.df("stack", "call") == 0      # "stack. Call" has a full stop between
    assert table.df("stack", "holds") == 1
    assert table.df("call", "unknown") == 0


def test_pmi_is_log_ratio_to_chance(table):
    # "call" occurs 5 times and "stack" 5 times in 38 token positions; the pair is in 2 documents.
    assert table.positions == 38
    assert table.pmi("call", "stack") == pytest.approx(math.log2(2 * 38 / (5 * 5)))
    assert table.pmi("stack", "call") is None


def test_merge_sums_equal_keys():
    a = (np.array([1, 5]), np.array([2, 1]))
    b = (np.array([5, 9]), np.array([4, 1]))
    keys, counts = bop.merge([a, b])
    assert keys.tolist() == [1, 5, 9] and counts.tolist() == [2, 5, 1]


def test_export_applies_both_thresholds(table):
    assert "call stack" in table.export(2, 1.0)
    assert "call stack" not in table.export(3, 1.0)
    assert "call stack" not in table.export(2, 5.0)


def test_vocabulary_has_no_function_words():
    words = bop.vocabulary(2000)
    assert "the" not in words and "of" not in words and "time" in words


def test_wilson_interval():
    lo, hi = est.wilson(5, 10)
    assert lo == pytest.approx(0.237, abs=0.002) and hi == pytest.approx(0.763, abs=0.002)
    assert est.wilson(0, 0) == (0.0, 1.0)


def test_occurrences_match_hyphen_or_space():
    doc = "A frame-pointer chain is fragile. Each frame pointer chain ends. Reframe pointer chains."
    assert est.occurrences("frame-pointer chain", doc) == 2
    assert est.occurrences("", doc) == 0


def test_introduced_as_a_term():
    assert est.introduced("write barrier log", "This structure is called the write barrier log.")
    assert est.introduced("write barrier log", "The *write barrier log* records each store.")
    assert est.introduced("write barrier log", "A write barrier log (WBL) records each store.")
    assert not est.introduced("write barrier log", "It appends to the write barrier log when full.")


def test_evidence_brackets_by_the_stronger_pair(table):
    e = est.Evidence("thread call stack", "one thread call stack here", table)
    assert e.words == ["thread", "call", "stack"]
    assert e.df == [0, 2] and e.count == 1
    assert e.bracket("adjacency") == "right"      # "call stack" is attested, "thread call" is not
    assert e.attested(2, 1.0) == [False, True]
    assert e.weakest() == -math.inf


def test_report_counts_dropped_findings(table):
    doc = "The call stack frames are here. The call stack frames again."
    findings = [
        {"split": "bench", "rule": "stacked-nouns", "accepted": False, "excerpt": "call stack frames", "document": doc},
        {"split": "bench", "rule": "stacked-nouns", "accepted": True, "excerpt": "thread dump function",
         "document": "one thread dump function"},
    ]
    text = "\n".join(est.report(findings, table))
    assert "bench: 2 labelled findings, accepted 1 of 2" in text
    assert "| occurs again in the document | 0 of 1 | 1 of 1 | 1 of 1 (100%" in text
    assert "Size of an attested-pair list" in text


def test_auc_is_half_for_equal_values():
    assert est.auc([1.0], [1.0]) == 0.5
    assert est.auc([1.0], [2.0]) == 1.0
    assert est.auc([], [2.0]) is None
