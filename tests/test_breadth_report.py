"""The breadth precision report (scripts/breadth_report.py), on made-up items and labels."""

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _mod(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


br = _mod("breadth_report")


def _item(i, rule="stacked-nouns", item="finding", family="md", stratum=None):
    return {"i": i, "rule": rule, "item": item, "family": family, "stratum": stratum or family}


def _labels(assign: dict[int, list[str]], blind: dict[int, list[str]] | None = None, present=True):
    """assign: id -> 12 primed labels; blind: id -> 3 unprimed labels."""
    out = {r: {} for r in br.PRIMED + br.BLIND}
    for i, labs in assign.items():
        for r, lab in zip(br.PRIMED, labs):
            if lab is not None:
                out[r][i] = {"label": lab, "present": present}
    for i, labs in (blind or {}).items():
        for r, lab in zip(br.BLIND, labs):
            out[r][i] = {"label": lab, "present": None}
    return out


def test_majorities_ties_and_missing_labels():
    items = [_item(1), _item(2), _item(3), _item(4)]
    labels = _labels({1: ["c"] * 7 + ["w"] * 5,
                      2: ["c"] * 6 + ["w"] * 6,            # a tie is not a majority
                      3: ["c"] * 6 + [None] * 6,           # missing labels count against
                      4: ["d"] * 4 + ["c"] * 3 + ["w"] * 5},
                     {1: ["c", "c", "w"], 2: ["c", "w", "w"], 4: ["d", "d", "w"]})
    vs = {v["i"]: v for v in br.votes(items, labels)}
    assert vs[1]["c"] and vs[1]["accepted"] and vs[1]["present"] and vs[1]["blind_c"]
    assert not vs[2]["c"] and not vs[2]["accepted"] and not vs[2]["blind_c"]
    assert not vs[3]["c"] and not vs[3]["complete"]
    assert not vs[4]["c"] and vs[4]["accepted"] and vs[4]["blind_accepted"] and not vs[4]["blind_c"]
    assert vs[1]["model_c"] == {"Opus 5.5": True, "Sonnet 5.5": True, "Haiku 5.5": False, "Fable 5.2": False}


def test_parse_labels_accepts_reply_objects(tmp_path):
    (tmp_path / "rater1.json").write_text(json.dumps([{"labels": [{"i": 5, "label": "c", "present": True}]}]))
    (tmp_path / "blind1.json").write_text(json.dumps({"labels": [{"i": 5, "label": "w"}]}))
    labels = br.load_labels(tmp_path)
    assert labels["rater1"][5] == {"label": "c", "present": True}
    assert labels["blind1"][5]["label"] == "w" and labels["rater2"] == {}


def _world(n_find, find_labels, n_near, near_labels, family="md", rule="stacked-nouns", start=0,
           blind_find=("w", "w", "w"), blind_near=("w", "w", "w")):
    items, assign, blind = [], {}, {}
    for k in range(n_find):
        i = start + k
        items.append(_item(i, rule, "finding", family, "src-go" if family == "doc comments" else None))
        assign[i], blind[i] = list(find_labels), list(blind_find)
    for k in range(n_near):
        i = start + 10000 + k
        items.append(_item(i, rule, "near", family))
        assign[i], blind[i] = list(near_labels), list(blind_near)
    return items, assign, blind


def _run(*worlds, decoys=0, decoy_blind=("w", "w", "w"), present=True):
    items, assign, blind = [], {}, {}
    for w in worlds:
        items += w[0]
        assign |= w[1]
        blind |= w[2]
    for k in range(decoys):
        i = 90000 + k
        items.append(_item(i, "inline-list", "decoy", "md"))
        assign[i], blind[i] = ["w"] * 12, list(decoy_blind)
    vs = br.votes(items, _labels(assign, blind, present))
    # vary one label per item so that Fleiss' kappa is defined and high enough
    return br.analyse(vs=vs)


def _decisions(res, what):
    return [(r, f) for r, f, d, _ in res["decisions"] if d.startswith(what)]


def test_threshold_earns_its_place_when_findings_beat_near_misses():
    res = _run(_world(25, ["c"] * 10 + ["w"] * 2, 25, ["w"] * 12))
    assert ("stacked-nouns", "all") in _decisions(res, "the threshold earns its place")
    p = res["pooled"]["stacked-nouns"]
    assert p["findings"]["c"]["k"] == 25 and p["near"]["c"]["k"] == 0


def test_threshold_not_supported_and_floor_fallback():
    # Neither has any c: the comparison falls back to accepted shares, which are equal.
    res = _run(_world(25, ["d"] * 8 + ["w"] * 4, 25, ["d"] * 8 + ["w"] * 4))
    dec = [d for d in res["decisions"] if d[0] == "stacked-nouns" and d[1] == "all"]
    assert dec and dec[0][2] == "threshold not supported by these labels" and "accepted" in dec[0][3]
    res = _run(_world(25, ["w"] * 12, 25, ["c"] * 12))
    assert _decisions(res, "near misses judged worse")
    res = _run(_world(5, ["c"] * 12, 5, ["w"] * 12))
    assert _decisions(res, "threshold: too few")


def test_off_in_one_format_needs_markdown_to_be_higher():
    md = _world(20, ["d"] * 8 + ["w"] * 4, 0, [], family="md", rule="hyphen-compound")
    commit = _world(20, ["w"] * 12, 0, [], family="commit", rule="hyphen-compound", start=1000)
    res = _run(md, commit)
    assert ("hyphen-compound", "commit") in _decisions(res, "proposed off for commit")
    md_low = _world(20, ["w"] * 12, 0, [], family="md", rule="hyphen-compound")
    res = _run(md_low, commit)
    assert ("hyphen-compound", "commit") in _decisions(res, "low here but not distinguishable")
    assert ("hyphen-compound", "all") in _decisions(res, "proposed for opt-in everywhere")


def test_detection_candidate_and_chance_rules():
    res = _run(_world(12, ["w"] * 12, 0, [], family="pr", rule="inline-list"), present=False)
    assert ("inline-list", "pr") in _decisions(res, "detection problem")
    res = _run(_world(12, ["c"] * 12, 0, [], family="rst", rule="nominalization",
                      blind_find=("c", "c", "w")), decoys=12)
    assert ("nominalization", "rst") in _decisions(res, "candidate default for rst")
    assert ("nominalization", "all") not in _decisions(res, "no better than chance")
    res = _run(_world(12, ["c"] * 12, 0, [], family="rst", rule="nominalization"), decoys=12)
    assert ("nominalization", "all") in _decisions(res, "no better than chance")


def test_kappa_guard_withholds_format_proposals():
    # Raters split down the middle on every finding: kappa for accepted is negative.
    w = _world(20, ["d"] * 6 + ["w"] * 6, 0, [], family="commit", rule="inline-list")
    res = _run(w, present=False)
    assert ("all rules", "commit") in _decisions(res, "no proposal")
    assert not _decisions(res, "detection problem")


def test_render_and_main(tmp_path):
    items, assign, blind = _world(25, ["c"] * 10 + ["w"] * 2, 25, ["w"] * 12, family="doc comments")
    items = [it | {"stratum": "src-go"} for it in items]
    labels = _labels(assign, blind)
    folder = tmp_path / "labels"
    folder.mkdir()
    for r, got in labels.items():
        rows = [{"id": i, "label": x["label"]} | ({"construction_present": x["present"]} if x["present"] is not None
                                                  else {}) for i, x in got.items()]
        (folder / f"{r}.json").write_text(json.dumps(rows))
    sample = tmp_path / "sample.jsonl"
    sample.write_text("".join(json.dumps(x) + "\n" for x in items))
    counts = tmp_path / "counts.json"
    counts.write_text(json.dumps({"md": {"findings": {"stacked-nouns": 3}, "deduped": {"stacked-nouns": 2},
                                         "near": {}, "near_deduped": {}, "sampled": {"stacked-nouns": 2},
                                         "sampled_near": {}, "decoys": 1}, "_repos": {"kept": 3}}))
    out = tmp_path / "report.md"
    br.main(["--labels", str(folder), "--sample", str(sample), "--counts", str(counts), "--out", str(out)])
    text = out.read_text()
    assert "## Primary" in text and "| doc comments | stacked-nouns | 25/25" in text
    assert "| src-go | stacked-nouns |" in text
    assert "the threshold earns its place" in text
