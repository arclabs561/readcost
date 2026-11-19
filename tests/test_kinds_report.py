"""The report by kind of document (scripts/kinds_report.py), on made-up items and labels."""

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


kr = _mod("kinds_report")
br = kr.br


def _item(i, rule="stacked-nouns", item="finding", stratum="tutorial", **kw):
    return {"i": i, "rule": rule, "item": item, "stratum": stratum, "family": stratum, "doc": f"d{i}"} | kw


def _labels(assign, blind=None, present=True):
    out = {r: {} for r in br.PRIMED + br.BLIND}
    for i, labs in assign.items():
        for r, lab in zip(br.PRIMED, labs):
            out[r][i] = {"label": lab, "present": present}
    for i, labs in (blind or {}).items():
        for r, lab in zip(br.BLIND, labs):
            out[r][i] = {"label": lab, "present": None}
    return out


def _build(groups):
    """groups: (count, item kwargs, 12 primed labels or None, 3 unprimed labels)."""
    items, prim, blind, i = [], {}, {}, 100000
    for n, kw, p, b in groups:
        for _ in range(n):
            items.append(_item(i, **kw))
            if p:
                prim[i] = p
            blind[i] = b
            i += 1
    return items, _labels(prim, blind)


C12, D12, W12 = ["c"] * 12, ["d"] * 12, ["w"] * 12


def test_threshold_and_chance_pooled():
    items, labels = _build([
        (30, {"rule": "stacked-nouns"}, ["c"] * 8 + ["w"] * 4, ["c", "c", "w"]),
        (30, {"rule": "stacked-nouns", "item": "near"}, W12, ["w"] * 3),
        (20, {"rule": "long-dependency", "item": "decoy"}, W12, ["w"] * 3),
    ])
    res = kr.analyse(items, labels)
    dec = {(r, s, w) for r, s, w, _ in res["decisions"]}
    assert ("stacked-nouns", "technical", "the threshold earns its place") in dec
    assert not any(r == "stacked-nouns" and "chance placement without priming" in w for r, _, w in dec)
    assert res["pooled"]["stacked-nouns"]["blind_c_over_decoys"][1] > 0


def test_off_for_a_kind_needs_the_rest_higher():
    items, labels = _build([
        (12, {"rule": "inline-list", "stratum": "changelog"}, W12, ["w"] * 3),
        (12, {"rule": "inline-list", "stratum": "tutorial"}, D12, ["d"] * 3),
        (12, {"rule": "inline-list", "stratum": "code-doc"}, W12, ["w"] * 3),
        (12, {"rule": "inline-list", "stratum": "code-ordinary"}, W12, ["w"] * 3),
    ])
    res = kr.analyse(items, labels)
    dec = {(r, s, w) for r, s, w, _ in res["decisions"]}
    assert ("inline-list", "changelog", "proposed off for changelog") in dec
    assert ("inline-list", "code-doc", "low here but not distinguishable from the rest") in dec
    assert ("inline-list", "changelog", "detection problem in this kind") not in dec  # present is true
    assert ("inline-list", "changelog", "no better than chance placement in this kind") in dec


def test_candidate_default_and_kappa_guard():
    items, labels = _build([
        (12, {"rule": "center-embedding", "stratum": "design"}, C12, ["c"] * 3),
        (16, {"rule": "stacked-nouns", "item": "decoy", "stratum": "design"}, W12, ["w"] * 3),
    ])
    res = kr.analyse(items, labels)
    assert ("center-embedding", "design", "candidate default for design") in \
        {(r, s, w) for r, s, w, _ in res["decisions"]}
    # split raters: kappa under the guard, no per-kind proposals
    mixed = {i: (["c", "w"] * 6 if i % 2 else ["w", "c"] * 6) for i in range(100000, 100012)}
    labels2 = _labels(mixed, {i: ["c"] * 3 for i in range(100000, 100028)})
    res2 = kr.analyse(items, labels2)
    dec2 = [(r, s, w) for r, s, w, _ in res2["decisions"]]
    assert ("all rules", "design", "no proposal under rules 2, 4 and 5") in dec2
    assert not any(w.startswith("candidate default") for _, _, w in dec2)


def test_contrast_makes_no_proposal_and_is_not_pooled():
    items, labels = _build([(12, {"rule": "inline-list", "stratum": "contrast"}, W12, ["w"] * 3)])
    res = kr.analyse(items, labels)
    assert not any(s == "contrast" for _, s, _, _ in res["decisions"])
    assert res["pooled"]["inline-list"]["findings"]["c"]["n"] == 0
    assert res["strata"]["contrast"]["rules"]["inline-list"]["findings"]["c"]["n"] == 12


def _ranked(i, doc, ranks, ok, stratum="tutorial"):
    return {"i": i, "rule": "", "item": "ranked", "stratum": stratum, "family": stratum, "doc": doc, "ranks": ranks}, ok


def test_ranking_decision_and_shared_items():
    rows = []
    i = 200000
    for k in range(60):  # composite (also longest in a third of documents) accepted, random not
        if k % 3 == 0:
            rows.append(_ranked(i, f"d{k}", ["composite", "longest"], True)); i += 1
        else:
            rows.append(_ranked(i, f"d{k}", ["composite"], True)); i += 1
            rows.append(_ranked(i, f"d{k}", ["longest"], False)); i += 1
        rows.append(_ranked(i, f"d{k}", ["random"], False)); i += 1
    items = [r for r, _ in rows]
    labels = _labels({}, {r["i"]: (["d"] * 3 if ok else ["w"] * 3) for r, ok in rows})
    res = kr.analyse(items, labels)
    rk = res["ranked"]["technical"]
    assert rk["cells"]["composite"]["n"] == rk["cells"]["longest"]["n"] == rk["cells"]["random"]["n"] == 60
    assert rk["cells"]["longest"]["k"] == 20 and rk["cells"]["composite"]["k"] == 60
    assert rk["paired"]["longest"] == {"n": 60, "composite_only": 40, "other_only": 0}
    assert ("ranking", "technical", "the composite is worth shipping as a ranking") in \
        {(r, s, w) for r, s, w, _ in res["decisions"]}
    # no ranked items: the composite does not beat length
    res0 = kr.analyse([], _labels({}))
    assert res0["decisions"][-1][2] == "the composite does not beat sentence length"


def test_rounds_one_and_two_shapes():
    r1 = [{"i": 1, "stratum": "S1", "decoy": "", "rule": "stacked-nouns"},
          {"i": 2, "stratum": "S1", "decoy": "random", "rule": "inline-list"},
          {"i": 3, "stratum": "S1", "decoy": "long", "rule": "inline-list"},
          {"i": 4, "stratum": "S2", "decoy": "", "rule": "stacked-nouns"}]
    got = kr.round1(r1)
    assert [(x["i"], x["item"]) for x in got] == [(1, "finding"), (2, "decoy")]
    r2 = [{"i": 768685, "item": "finding"}, {"i": 768685, "item": "finding"}, {"i": 5, "item": "near"}]
    assert [x["i"] for x in kr.round2(r2)] == [768685, 5]


def test_defaults_across_rounds():
    def votes(items, labels):
        return br.votes(items, labels)

    # round 2: stacked-nouns findings accepted, near misses not; hyphen-compound neither beats anything
    i2, l2 = _build([
        (30, {"rule": "stacked-nouns", "stratum": "md"}, D12, ["w"] * 3),
        (30, {"rule": "stacked-nouns", "item": "near", "stratum": "md"}, W12, ["w"] * 3),
        (30, {"rule": "hyphen-compound", "stratum": "md"}, D12, ["w"] * 3),
        (30, {"rule": "center-embedding", "stratum": "md"}, D12, ["d"] * 3),
        (30, {"rule": "center-embedding", "item": "near", "stratum": "md"}, W12, ["w"] * 3),
        (30, {"rule": "nominalization", "stratum": "md"}, D12, ["d"] * 3),
        (30, {"rule": "inline-list", "item": "decoy", "stratum": "md"}, W12, ["w"] * 3),
    ])
    v2 = [v | {"round": 2} for v in votes(i2, l2)]
    i1 = [{"i": 900000, "stratum": "S1", "decoy": "", "rule": "hyphen-compound"}]
    v1 = br.votes(kr.round1(i1), _labels({900000: D12}, {900000: ["w"] * 3}))
    v1 = [v | {"round": 1} for v in v1]
    b = kr.defaults(v1, v2, [])
    assert b["stacked-nouns"]["decision"] == "stays default"            # (i)
    assert b["hyphen-compound"]["decision"] == "proposed opt-in"        # no threshold, (ii) fails
    assert b["center-embedding"]["decision"] == "proposed default"      # (i) and (ii)
    assert b["nominalization"]["decision"] == "proposed default"        # no threshold: (ii) alone
    assert b["undefined-acronym"]["decision"] == "stays opt-in"
    assert set(b["hyphen-compound"]["per_round"]) == {1, 2}


def test_render_and_main(tmp_path):
    items, labels = _build([
        (12, {"rule": "stacked-nouns", "stratum": "tutorial"}, D12, ["d", "w", "w"]),
        (4, {"rule": "stacked-nouns", "item": "near", "stratum": "tutorial"}, W12, ["w"] * 3),
        (16, {"rule": "inline-list", "item": "decoy", "stratum": "tutorial"}, W12, ["w"] * 3),
    ])
    items.append({"i": 300000, "rule": "", "item": "ranked", "stratum": "tutorial", "doc": "x",
                  "ranks": ["composite", "longest", "random"]})
    sample = tmp_path / "sample.jsonl"
    sample.write_text("".join(json.dumps(x) + "\n" for x in items))
    lab = tmp_path / "labels"
    lab.mkdir()
    for r in br.PRIMED + br.BLIND:
        rows = [{"id": i, "label": v["label"], "construction_present": v["present"]} for i, v in labels[r].items()]
        (lab / f"{r}.json").write_text(json.dumps(rows))
    r1 = tmp_path / "r1"
    r2 = tmp_path / "r2"
    for d, rows in ((r1, [{"i": 1, "stratum": "S1", "decoy": "", "rule": "stacked-nouns"}]),
                    (r2, [{"i": 2, "stratum": "md", "family": "md", "item": "finding", "rule": "stacked-nouns"}])):
        (d / "labels").mkdir(parents=True)
        (d / "sample.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
        for r in br.PRIMED + br.BLIND:
            (d / "labels" / f"{r}.json").write_text("[]")
    out = tmp_path / "report.md"
    kr.main(["--labels", str(lab), "--sample", str(sample), "--counts", str(tmp_path / "none.json"),
             "--round1", str(r1), "--round2", str(r2), "--out", str(out)])
    text = out.read_text()
    for head in ("## Primary", "## Random decoys", "## Ranked sentences", "## Defaults across rounds", "## Decisions"):
        assert head in text
