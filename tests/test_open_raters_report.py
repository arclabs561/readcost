"""The open-raters report on made-up samples and labels."""

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("open_raters_report", SCRIPTS / "open_raters_report.py")
rep = importlib.util.module_from_spec(spec)
sys.modules["open_raters_report"] = rep
spec.loader.exec_module(rep)

FAMILIES = ("qwen", "gemma", "glm", "mistral")
N = 12  # items per cell


def make_samples():
    """Center-embedding findings that every rater accepts, near misses, decoys and long sentences they reject."""
    ids = iter(range(100000, 999999))
    r1 = []
    for stratum in ("S1", "S2"):
        for rule in ("center-embedding", "inanimate-subject", "stacked-nouns"):
            r1 += [{"i": next(ids), "stratum": stratum, "decoy": "", "rule": rule} for _ in range(N)]
        for kind in ("random", "long"):
            r1 += [{"i": next(ids), "stratum": stratum, "decoy": kind, "rule": "stacked-nouns"} for _ in range(N)]
    r2 = []
    for rule in ("center-embedding", "inanimate-subject", "stacked-nouns"):
        r2 += [{"i": next(ids), "stratum": "md", "family": "md", "item": "finding", "rule": rule} for _ in range(N)]
    for rule in ("center-embedding", "stacked-nouns"):
        r2 += [{"i": next(ids), "stratum": "md", "family": "md", "item": "near", "rule": rule} for _ in range(N)]
    r2 += [{"i": next(ids), "stratum": "md", "family": "md", "item": "decoy", "rule": "stacked-nouns"}
           for _ in range(N)]
    r3 = []
    for rule in ("center-embedding", "inanimate-subject", "stacked-nouns"):
        r3 += [{"i": next(ids), "stratum": "tutorial", "item": "finding", "rule": rule, "ranks": []} for _ in range(N)]
    for rule in ("center-embedding", "stacked-nouns"):
        r3 += [{"i": next(ids), "stratum": "tutorial", "item": "near", "rule": rule, "ranks": []} for _ in range(N)]
    r3 += [{"i": next(ids), "stratum": "tutorial", "item": "decoy", "rule": "stacked-nouns", "ranks": []}
           for _ in range(N)]
    for d in range(N):
        for rank in ("composite", "longest", "random"):
            r3.append({"i": next(ids), "stratum": "tutorial", "item": "ranked", "rule": "", "ranks": [rank],
                       "doc": f"doc{d}"})
    return {1: r1, 2: r2, 3: r3}


def label_for(x: dict, proto: str, who: str) -> dict:
    """c for center-embedding findings; inanimate-subject is a problem unprimed but rejected primed; rest w."""
    finding = not x.get("decoy") and x.get("item", "finding") == "finding"
    if finding and x["rule"] == "center-embedding":
        lab = "c"
    elif finding and x["rule"] == "inanimate-subject":
        lab = "d" if proto == "unprimed" else "w"
    elif finding and x["rule"] == "stacked-nouns" and proto == "primed":
        lab = "d"  # accepted only when primed: a priming effect
    else:
        lab = "w"
    if who == "lenient" and x.get("item") == "ranked" and "longest" in x.get("ranks", []):
        lab = "c"
    out = {"id": x["i"], "label": lab, "cause": ""}
    if proto == "primed":
        out["construction_present"] = lab != "w"
    return out


def write_eval(root: Path, drop_family: str | None = None) -> Path:
    samples = make_samples()
    for rnd, rows in samples.items():
        d = root / rep.ROUND_DIRS[rnd]
        (d / "labels").mkdir(parents=True)
        (d / "sample.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        if rnd == 1:
            (d / "counts.json").write_text(json.dumps({"deduped": {"S1": {"center-embedding": 5, "stacked-nouns": 5,
                                                                          "inanimate-subject": 5}}}))
        primed_rows = [r for r in rows if r.get("item") != "ranked"]
        names = [*(f"rater{k}" for k in range(1, 13)), *(f"blind{k}" for k in range(1, 4))]
        for fam in FAMILIES:
            names += [rep.open_name(fam, p, s) for p in ("primed", "unprimed") for s in (*rep.SAMPLED, "greedy")]
        for name in names:
            proto = "unprimed" if "blind" in name or "unprimed" in name else "primed"
            use = rows if proto == "unprimed" else primed_rows
            if drop_family and name.startswith(f"open-{drop_family}-") and rnd == 3:
                use = use[: len(use) // 2]
            (d / "labels" / f"{name}.json").write_text(json.dumps([label_for(x, proto, "") for x in use]))
    return root


def test_panels_and_majorities():
    c, o = rep.claude_panel(), rep.open_panel(FAMILIES)
    assert (len(c.primed), c.primed_majority, len(c.blind), c.blind_majority) == (12, 7, 3, 2)
    assert (len(o.primed), o.primed_majority, len(o.blind), o.blind_majority) == (12, 7, 12, 7)
    both = rep.combined_panel(FAMILIES)
    assert (both.primed_majority, both.blind_majority) == (13, 8)
    assert rep.family_panel("qwen").primed_majority == 2
    assert rep.greedy_panel(FAMILIES).primed_majority == 3
    assert rep.open_panel(FAMILIES[:3]).primed_majority == 5


def test_votes_count_missing_labels_against():
    p = rep.family_panel("qwen")
    labels = {p.primed[0]: {1: {"label": "c", "present": True}}, p.primed[1]: {1: {"label": "d", "present": True}}}
    v = rep.votes([{"i": 1}], labels, p)[0]
    assert v["accepted"] and not v["c"] and v["present"] and not v["complete"]
    labels.pop(p.primed[1])
    assert not rep.votes([{"i": 1}], labels, p)[0]["accepted"]


def test_as_panel_restores_the_round_scripts():
    before = (rep.br.PRIMED, rep.br.PRIMED_MAJORITY, rep.hr.RATERS, rep.kr.MODELS, rep.br.agreement)
    with rep.as_panel(rep.open_panel(FAMILIES)):
        assert rep.br.PRIMED_MAJORITY == 7 and rep.br.BLIND_MAJORITY == 7
        assert rep.hr.RATERS[0] == "open-qwen-primed-s1"
    assert (rep.br.PRIMED, rep.br.PRIMED_MAJORITY, rep.hr.RATERS, rep.kr.MODELS, rep.br.agreement) == before


def test_describe_rewrites_the_majorities():
    text = "c: at least 7 of the 12 primed raters label it; accepted: at least 7 label it; at least 2 of the 3 " \
           "unprimed raters; Fleiss' kappa over the twelve"
    out = rep.describe(text, rep.combined_panel(FAMILIES))
    assert "at least 13 of the 24 primed raters" in out and "at least 13 label" in out
    assert "at least 8 of the 15 unprimed raters" in out and "over the 24 primed raters" in out


def test_statistics():
    assert rep.cohen([True, False, True, False], [True, False, True, False]) == 1.0
    assert rep.cohen([], []) is None
    est, lo, hi = rep.paired_diff([True] * 20, [False] * 20)
    assert est == lo == hi == 1.0
    est, lo, hi = rep.paired_diff([True, False] * 10, [False, True] * 10)
    assert est == 0 and lo < 0 < hi


def test_q1_verdict():
    up, flat, down = (0.3, 0.1, 0.5), (0.0, -0.1, 0.1), (-0.3, -0.5, -0.1)
    claude = {"pooled": up, "rules": {"a": up, "b": up, "c": flat}}
    assert rep.q1_verdict({"pooled": up, "rules": {"a": up, "b": flat, "c": up}}, claude) == ("replicates", ["a"])
    assert rep.q1_verdict({"pooled": up, "rules": {"a": flat, "b": flat, "c": up}}, claude) == ("partial", [])
    assert rep.q1_verdict({"pooled": flat, "rules": {"a": up, "b": up}}, claude)[0] == "does not replicate"
    assert rep.q1_verdict({"pooled": down, "rules": {}}, claude)[0] == "does not replicate"


def test_report_answers_the_questions(tmp_path):
    root = write_eval(tmp_path / "eval")
    got = rep.build(root)
    meta, qa = got["meta"], got["meta"]["answers"]
    assert meta["families"] == list(FAMILIES) and not meta["excluded"]
    # Q1: stacked-nouns accepted only primed; inanimate-subject the other way
    assert rep.above(qa["q1_open"]["rules"]["stacked-nouns"])
    assert qa["q1_open"]["rules"]["inanimate-subject"][2] < 0
    # pooled, the two cancel out: stacked-nouns +100 points, inanimate-subject -100, center-embedding 0
    assert qa["q1"][0] == "does not replicate" and qa["q1"][1] == ["stacked-nouns"]
    # Q2 and Q3: nobody calls the longest sentences a problem, so both rules that are problems unprimed beat them
    assert qa["q2"]["answer"] == "no: others beat it too"
    assert qa["q2"]["beats"] == ["center-embedding", "inanimate-subject"]
    assert qa["q3"]["inanimate-subject"] == "passes"  # a problem unprimed in every finding: it passes here
    assert qa["q3"]["nominalization"] == "still fails"
    assert qa["q4"]["answer"] == "still does not beat it"
    assert qa["q5_107"]["answer"] == "stands"
    assert qa["q5_98"]["answer"] == "stands"  # never accepted primed
    # the Claude panel and the open panel gave the same labels here
    pooled = next(r for r in meta["agreement"] if r["scope"] == "pooled" and r["family"] == "open")
    assert pooled["cohen_primed"] == 1.0
    text = rep.render_report(meta)
    assert "## Q1." in text and "## Q5." in text
    for name in ("claude", "open", "claude-and-open", "qwen", "open-greedy"):
        assert set(got["panels"][name]["texts"]) == {1, 2, 3}
    assert "at least 13 of the 24 primed raters" in got["panels"]["claude-and-open"]["texts"][2]


def test_a_family_with_low_coverage_is_left_out(tmp_path):
    got = rep.build(write_eval(tmp_path / "eval", drop_family="mistral"))
    assert got["meta"]["excluded"] == ["mistral"]
    assert got["meta"]["families"] == ["qwen", "gemma", "glm"]
    assert "mistral" in got["panels"]  # still reported alone
    assert got["meta"]["coverage"]["mistral"]["round3 primed"] < rep.COVERAGE_FLOOR


def test_main_writes_the_report_and_panel_files(tmp_path, capsys):
    root = write_eval(tmp_path / "eval")
    out = tmp_path / "out"
    rep.main(["--eval", str(root), "--out", str(out)])
    assert (out / "report.md").exists() and (out / "open" / "round3.md").exists()
    assert "# Re-rating with open models" in capsys.readouterr().out
