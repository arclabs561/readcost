"""The dataset matrix (scripts/dataset_matrix*.py): loaders, derived labels, features and statistics.

Every fixture is made up; no third-party data is read.
"""

import importlib.util
import json
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


dm = _mod("dataset_matrix")
rep = _mod("dataset_matrix_report")


# ------------------------------------------------------------------ helpers

def test_every_dataset_has_a_loader_and_a_valid_spec():
    for name, spec in dm.DATASETS.items():
        assert callable(dm.LOADERS[name])
        assert spec["family"] in ("rated", "reading", "revision")
        if spec["kind"] == "text":
            assert spec["primary"] in spec["direction"]
            assert spec["direction"][spec["primary"]] in (-1, 1)
            assert all(v in (-1, 0, 1) for v in spec["direction"].values())
        else:
            assert spec["target"] and spec["other"]


def test_detokenize_and_strip_code():
    assert dm.detokenize("a process ( for example , by resonance ) , which isn 't") == \
        "a process (for example, by resonance), which isn't"
    md = "Use `run()` here.\n\n```python\nx = 1\n```\nThen stop."
    assert "x = 1" not in dm.strip_code(md) and "run()" not in dm.strip_code(md)
    assert "Then stop." in dm.strip_code(md)


def test_complaint_shares_and_helpfulness_from_feedback():
    fb = ["The response is mostly helpful. It is a little verbose.",
          "The response is partially helpful. The explanation is confusing and repetitive.",
          "The response is perfectly helpful."]
    assert dm._share(fb, dm.VERBOSE) == pytest.approx(1 / 3)
    assert dm._share(fb, dm.CLARITY) == pytest.approx(1 / 3)
    assert dm._share(fb, dm.REPETITION) == pytest.approx(1 / 3)
    assert dm._helpful(fb) == pytest.approx((3 + 2 + 4) / 3)
    assert dm._share([], dm.VERBOSE) != dm._share([], dm.VERBOSE)  # NaN when there is no feedback
    assert dm.EDIT_TARGET.search("Made the answer more concise and removed redundant lines")
    assert not dm.EDIT_TARGET.search("Fixed the date and added a citation")


def test_scarecrow_coverage_averages_marked_characters_over_annotators():
    text = "a" * 100
    responses = [[["Redundant", "x", 1, 0, 50, []]], [["Technical_Jargon", "x", 1, 0, 10, []]], []]
    shares, spans = dm.scarecrow_coverage(text, responses)
    assert shares["redundant"] == pytest.approx(0.5 / 3)
    assert shares["jargon"] == pytest.approx(0.1 / 3)
    assert shares["readability"] == pytest.approx((0.5 + 0.1) / 3)
    assert shares["grammar"] == 0
    assert len(spans) == 2


def test_sample_groups_keeps_groups_whole():
    rows = [{"group": g, "i": i} for i, g in enumerate("aabbccddee")]
    kept = dm._sample_groups(rows, 5)
    groups = {r["group"] for r in kept}
    assert all(sum(r["group"] == g for r in kept) == 2 for g in groups)
    assert dm._sample_groups(rows, None) == rows


# ------------------------------------------------------------------ loaders

def test_arxivedits_loader(tmp_path):
    d = tmp_path / "data" / "edits"
    d.mkdir(parents=True)
    (d / "train.json").write_text(json.dumps({"0": {
        "sentence-1": "We use a very long method , which works .", "sentence-2": "We use a short method .",
        "edits-combination-0": {"0": {"intention": "Lang-improve-readability-Simplify"}},
        "edits-combination-1": {}, "arxiv-id": "1234.5678"}}))
    rows = dm.load_arxivedits(tmp_path)
    assert rows[0]["target"] and rows[0]["before"] == "We use a very long method, which works."
    assert rows[0]["group"] == "1234.5678"


def test_scarecrow_loader(tmp_path):
    (tmp_path / "data").mkdir()
    gen = "The cat sat. The cat sat again."
    with open(tmp_path / "data" / "grouped_data.csv", "w", encoding="utf-8") as f:
        f.write("id,gid,prompt,generation,model,p,temperature,frequency_penalty,responses\n")
        f.write(f'0,1,A prompt.,{gen},gpt3,1,1,0,"[[[\'Redundant\', \'repeats\', 1, 13, 31, []]], []]"\n')
    rows = dm.load_scarecrow(tmp_path)
    assert rows[0]["_annotators"] == 2
    assert rows[0]["outcomes"]["redundant"] == pytest.approx((31 - 13) / len(gen) / 2)


def test_reading_time_loader_groups_onestop_levels(tmp_path):
    p = tmp_path / "texts.jsonl"
    p.write_text("\n".join(json.dumps(t) for t in [
        {"corpus": "onestop", "id": "1/2/Adv/3", "words": ["A", "b"], "rt": [100, 300]},
        {"corpus": "onestop", "id": "1/2/Ele/3", "words": ["A"], "rt": [150]},
        {"corpus": "provo", "id": "7", "words": ["C"], "rt": [10]}]))
    rows = dm.load_onestop(p)
    assert [r["outcomes"]["ms_per_word"] for r in rows] == [200, 150]
    assert rows[0]["group"] == rows[1]["group"] == "1/2/3"
    assert len(dm.load_provo(p)) == 1


# ----------------------------------------------------------------- features

def test_features_counts_rules_and_controls():
    text = "The index shard compaction job reads the manifest before it starts the merge."
    f = dm.features(text, "text")
    assert f["counts"]["stacked-nouns"] >= 1
    assert f["rates"]["stacked-nouns"] == pytest.approx(100 * f["counts"]["stacked-nouns"] / f["checked_words"])
    assert f["points_per100"] > 0 and f["words"] == 13
    assert set(dm.OPT_IN) <= set(f["counts"])
    rec = dm._text_record("summeval", dm.DATASETS["summeval"],
                          {"id": "x", "group": "g", "text": text, "pointer": {}, "outcomes": {"coherence": 3.0}})
    assert "text" not in rec and rec["sha256"] == dm.sha(text)


# --------------------------------------------------------------- statistics

def test_demean_only_with_repeated_groups():
    x = np.array([1.0, 3.0, 5.0])
    assert np.allclose(rep.demean(x, np.array(["a", "b", "c"])), x)
    assert np.allclose(rep.demean(x, np.array(["a", "a", "b"])), [-1, 1, 0])


def test_association_finds_a_planted_effect_and_not_a_length_one():
    rng = np.random.default_rng(1)
    n = 400
    C = rng.normal(size=(n, 3))
    x = (rng.random(n) < 0.3).astype(float)
    y_effect = 0.8 * x + C[:, 0] + rng.normal(size=n)
    y_length = C[:, 0] + rng.normal(size=n)
    x_len = (C[:, 0] + rng.normal(size=n) > 0.5).astype(float)  # tied to length only
    g = np.arange(n).astype(str)
    a = rep.association(y_effect, x, C, g, 200)
    assert a["r"] > 0.2 and a["ci"][0] > 0
    b = rep.association(y_length, x_len, C, g, 200)
    assert b["ci"][0] < 0 < b["ci"][1]


def _rec(dataset, y, rate, words=100, group=None, i=0):
    rates = {k: 0.0 for k in rep.DEFAULT_RULES + rep.OPT_IN_RULES}
    rates["stacked-nouns"] = rate
    return {"dataset": dataset, "kind": "text", "id": str(i), "group": group or str(i), "words": words,
            "checked_words": words, "mean_word_len": 4.5, "mean_zipf": 5.0, "points_per100": rate,
            "counts": {k: int(v > 0) for k, v in rates.items()}, "rates": rates,
            "metrics": {k: 1.0 for k in rep.METRICS}, "outcomes": {"cefr": y}}


def test_lodo_fits_on_the_others_and_tests_on_the_left_out(monkeypatch):
    rng = np.random.default_rng(2)
    specs = {}
    data = {}
    for d in ("a", "b", "c"):
        specs[d] = {"family": "rated", "primary": "cefr", "direction": {"cefr": 1}}
        rows = []
        for i in range(200):
            rate = float(rng.random() < 0.3) * rng.uniform(1, 3)
            rows.append(_rec(d, rate + rng.normal(), rate, words=int(rng.integers(10, 50)), i=i))
        data[d] = rows
    monkeypatch.setattr(rep, "DATASETS", specs)
    lines = rep.lodo(data, "rated", 100)
    assert len(lines) == 5
    fitted = [float(line.split("|")[3]) for line in lines[2:]]
    assert all(r > 0.3 for r in fitted)


def test_revision_table_compares_target_with_other_edits(monkeypatch):
    rows = []
    for i in range(80):
        target = i % 2 == 0
        before = {"words": 20, "checked_words": 20, "points_per100": 5.0,
                  "counts": {"stacked-nouns": 1}}
        removed = target or i % 8 == 1
        after = {"words": 19, "checked_words": 19, "points_per100": 0.0 if removed else 5.0,
                 "counts": {"stacked-nouns": 0 if removed else 1}}
        rows.append({"dataset": "x", "group": str(i), "target": target, "edit_size": 0.2, "intents": [],
                     "before": before, "after": after})
    monkeypatch.setitem(rep.DATASETS, "x", {"signal": "s", "source": "s", "licence": "l", "target": "t",
                                            "other": "o", "family": "revision"})
    lines, table = rep.revision_dataset("x", rows, 100)
    row = [t for t in table if t["measure"] == "stacked-nouns"][0]
    assert row["raw_r"] == pytest.approx(1.0 - 10 / 40)
    assert row["lo"] > 0


def test_derive_writes_no_text_and_a_manifest(tmp_path):
    rec = _rec("readmepp", 3.0, 0.0)
    rec["sha256"] = "0" * 64
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "readmepp.jsonl").write_text(json.dumps(rec) + "\n")
    rep.derive(tmp_path / "in", tmp_path / "out")
    manifest = json.loads((tmp_path / "out" / "MANIFEST.json").read_text())
    assert manifest["files"][0]["records"] == 1 and manifest["files"][0]["licence"]
    assert "text" not in json.loads((tmp_path / "out" / "readmepp.jsonl").read_text())
    assert (tmp_path / "out" / "README.md").exists()


def test_prep_geco_matches_columns_exactly(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ALL"
    ws.append(["WORD_ID", "SENTENCE_ID", "WORD"])
    for wid, sid, w in [("1-1-1", "1-1", "It"), ("1-1-2", "1-1", "rained."), ("1-2-1", "1-2", "Yes.")]:
        ws.append([wid, sid, w])
    wb.save(tmp_path / "EnglishMaterial.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "DATA"
    # WORD_ID_WITHIN_TRIAL comes first and contains "WORD_ID": the match must be exact.
    ws.append(["PP_NR", "PART", "TRIAL", "WORD_ID_WITHIN_TRIAL", "WORD_ID", "WORD_TOTAL_READING_TIME"])
    for pp in ("a", "b"):
        ws.append([pp, 1, 4, 1, "1-1-1", 200 if pp == "a" else 100])
        ws.append([pp, 1, 4, 2, "1-1-2", "."])
        ws.append([pp, 1, 5, 1, "1-2-1", 300])
    wb.save(tmp_path / "MonolingualReadingData.xlsx")
    out = dm.prep_geco(tmp_path)
    rows = dm.load_geco(out)
    assert [r["text"] for r in rows] == ["It rained.", "Yes."]
    assert rows[0]["outcomes"]["ms_per_word"] == pytest.approx((150 + 0) / 2)
    assert [r["group"] for r in rows] == ["1-4", "1-5"]
