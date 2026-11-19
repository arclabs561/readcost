"""The held-out precision report (scripts/heldout_report.py), on made-up labels."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _mod(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


hr = _mod("heldout_report")


def test_wilson_matches_known_values():
    lo, hi = hr.wilson(4, 40)
    assert lo == pytest.approx(0.0396, abs=1e-3) and hi == pytest.approx(0.2313, abs=1e-3)
    assert hr.wilson(0, 0) == (0.0, 1.0)
    assert hr.wilson(0, 10)[0] == 0.0 and hr.wilson(10, 10)[1] == pytest.approx(1.0)


def test_newcombe_against_newcombe_1998():
    # Newcombe (1998), Table II example (h): 56/70 against 48/80 gives 0.2000, 0.0524 to 0.3339.
    d, lo, hi = hr.newcombe(56, 70, 48, 80)
    assert d == pytest.approx(0.2)
    assert lo == pytest.approx(0.0524, abs=5e-4) and hi == pytest.approx(0.3339, abs=5e-4)


def test_fleiss_kappa():
    # Fleiss (1971) style check: perfect agreement is 1, a constant category is undefined.
    assert hr.fleiss([[3, 0], [0, 3], [3, 0]]) == pytest.approx(1.0)
    assert hr.fleiss([[3, 0], [3, 0]]) is None
    # Wikipedia's worked example (14 raters, 10 items, 5 categories): kappa 0.210.
    table = [[0, 0, 0, 0, 14], [0, 2, 6, 4, 2], [0, 0, 3, 5, 6], [0, 3, 9, 2, 0], [2, 2, 8, 1, 1],
             [7, 7, 0, 0, 0], [3, 2, 6, 3, 0], [2, 5, 3, 2, 2], [6, 5, 2, 1, 0], [0, 2, 2, 3, 7]]
    assert hr.fleiss(table) == pytest.approx(0.210, abs=1e-3)


def test_pairwise_agreement():
    assert hr.pairwise_agreement([[True, True, False]]) == pytest.approx(1 / 3)
    assert hr.pairwise_agreement([]) is None


def test_parse_labels_accepts_every_shape():
    canonical = [{"id": 1, "label": "c", "construction_present": True}]
    reply = {"labels": [{"i": 2, "label": "defensible", "present": False, "cause": "x"}]}
    assert hr.parse_labels(canonical) == {1: {"label": "c", "present": True}}
    assert hr.parse_labels(reply) == {2: {"label": "d", "present": False}}
    both = hr.parse_labels([reply, {"labels": [{"i": "3", "label": "W", "present": "yes"}]}])
    assert both == {2: {"label": "d", "present": False}, 3: {"label": "w", "present": None}}
    assert hr.parse_labels([{"id": 4, "label": "maybe"}]) == {4: {"label": None, "present": None}}


def _sample():
    """Made-up pointers: for each rule 40 S1 findings and 10 S2 findings, plus 80 S1 and 20 S2 decoys."""
    items, i = [], 1000
    for stratum, n in (("S1", 40), ("S2", 10)):
        for rule in hr.RULES:
            for _ in range(n):
                items.append({"i": i, "stratum": stratum, "rule": rule, "decoy": ""})
                i += 1
        for k in range({"S1": 80, "S2": 20}[stratum]):
            items.append({"i": i, "stratum": stratum, "rule": hr.RULES[k % 10],
                          "decoy": "random" if k % 2 else "long"})
            i += 1
    return items


def _labels(sample, accept_share):
    """Three raters who agree; accept_share(item) -> True if all three accept it."""
    out = {r: [] for r in hr.RATERS}
    for it in sample:
        acc = accept_share(it)
        for r in hr.RATERS:
            out[r].append({"id": it["i"], "label": "d" if acc else "w", "construction_present": acc})
    return {r: hr.parse_labels(v) for r, v in out.items()}


def _accept(it):
    """inline-list: 30 of 40 accepted; stacked-nouns 2 of 40; decoys 8 of 80; others 12 of 40."""
    j = it["i"] % 40
    if it["decoy"]:
        return it["i"] % 10 == 0
    if it["rule"] == "inline-list":
        return j < 30
    if it["rule"] == "stacked-nouns":
        return j < 2
    return j < 12


COUNTS = {"deduped": {"S1": {r: 100 for r in hr.RULES}, "S2": {r: 10 for r in hr.RULES}}}


def test_analyse_decisions_on_made_up_labels():
    sample = _sample()  # S1 ids start at 1000, 40 per rule, so i % 40 runs 0..39 within a rule
    res = hr.analyse(sample, COUNTS, _labels(sample, _accept))
    s1 = res["strata"]["S1"]
    sn = s1["rules"]["stacked-nouns"]
    assert sn["accepted"]["n"] == 40
    assert s1["decoys"]["all"]["n"] == 80
    decisions = {(r, what) for r, what, _ in res["decisions"]}
    k_sn = sn["accepted"]["k"]
    assert k_sn == 2
    assert ("stacked-nouns", "proposed for opt-in") in decisions
    assert ("stacked-nouns", "detection problem, not a cost problem") in decisions
    assert ("stacked-nouns", "not distinguishable from chance placement") in decisions
    il = s1["rules"]["inline-list"]
    assert il["over_decoys"][1] > 0
    assert ("inline-list", "not distinguishable from chance placement") not in decisions
    assert not res["withheld"]  # the raters agree perfectly
    assert s1["agreement"]["kappa_acc"] == pytest.approx(1.0)
    est, lo, hi = s1["pooled_default"]
    assert lo <= est <= hi
    text = hr.render(res)
    assert "## Decisions (S1)" in text and "inline-list" in text
    assert set(res["comparison"]) == set(hr.IN_SAMPLE)


def test_missing_labels_count_as_not_accepted_and_guard_withholds():
    sample = [{"i": k, "stratum": "S1", "rule": "inline-list", "decoy": ""} for k in range(30)]
    sample += [{"i": 100 + k, "stratum": "S1", "rule": "inline-list", "decoy": "random"} for k in range(10)]
    labels = {r: {} for r in hr.RATERS}
    # rater-by-rater disagreement that is no better than chance
    pattern = [("c", "w", "w"), ("w", "c", "w"), ("w", "w", "c"), ("c", "c", "w"), ("w", "c", "c"), ("c", "w", "c")]
    for it in sample:
        for j, r in enumerate(hr.RATERS):
            labels[r][it["i"]] = {"label": pattern[it["i"] % 6][j], "present": True}
    del labels["rater3"][0]
    res = hr.analyse(sample, {"deduped": {"S1": {"inline-list": 30}}}, labels)
    v = hr.votes(sample[:1], labels)[0]
    assert v["labels"][2] is None and not v["complete"]
    a = res["strata"]["S1"]["agreement"]
    assert a["incomplete"] == 1
    assert a["kappa_acc"] < 0.2 and a["pairwise_acc"] < 0.8
    assert res["withheld"]
    assert "do not agree enough" in hr.render(res)


def test_main_writes_markdown(tmp_path, capsys):
    sample = _sample()
    labels = _labels(sample, _accept)
    (tmp_path / "labels").mkdir()
    for r in hr.RATERS:
        rows = [{"id": i, "label": v["label"], "construction_present": v["present"]} for i, v in labels[r].items()]
        (tmp_path / "labels" / f"{r}.json").write_text(json.dumps(rows))
    (tmp_path / "sample.jsonl").write_text("".join(json.dumps(x) + "\n" for x in sample))
    (tmp_path / "counts.json").write_text(json.dumps(COUNTS))
    out = tmp_path / "report.md"
    hr.main(["--labels", str(tmp_path / "labels"), "--sample", str(tmp_path / "sample.jsonl"),
             "--counts", str(tmp_path / "counts.json"), "--out", str(out)])
    assert out.read_text().startswith("# Held-out precision: results")
    assert capsys.readouterr().out == out.read_text()
