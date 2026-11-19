"""Report for the precision test by kind of document (docs/prereg/kinds-precision.md).

    uv run python scripts/kinds_report.py [--labels DIR] [--out REPORT.md]

Reads the committed pointers (eval/kinds/sample.jsonl, eval/kinds/counts.json)
and fifteen label files: DIR/rater1.json to DIR/rater12.json (primed) and
DIR/blind1.json to DIR/blind3.json (unprimed); default DIR:
/home/claude/kinds-batches/labels. The label shapes are those
scripts/breadth_report.py reads. For part B ("Defaults across rounds") it also
reads round 1 (eval/heldout/sample.jsonl, eval/heldout/labels/) and round 2
(eval/breadth/sample.jsonl without the second row of id 768685,
eval/breadth/labels/). Writes markdown with every outcome and decision the
pre-registration names. No item text is read.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import breadth_report as br
from heldout_report import newcombe

ROOT = Path(__file__).resolve().parent.parent
PRIMED, BLIND, MODELS = br.PRIMED, br.BLIND, br.MODELS
DEFAULT_RULES, OPT_IN_RULES, RULES, THRESHOLD_RULES = br.DEFAULT_RULES, br.OPT_IN_RULES, br.RULES, br.THRESHOLD_RULES

DOC_STRATA = ("tutorial", "reference", "explanation", "design", "runbook", "changelog", "blog", "standards")
CODE_STRATA = ("code-doc", "code-ordinary")
STRATA = (*DOC_STRATA, *CODE_STRATA, "contrast")
TECHNICAL = (*DOC_STRATA, *CODE_STRATA)
RANKS = ("composite", "longest", "random")
DUPLICATE_R2 = 768685

OFF_FLOOR, PRESENT_FLOOR = 0.25, 0.5
CANDIDATE_ACC, CANDIDATE_C = 0.5, 0.10
C_FLOOR, KAPPA_GUARD = 0.10, 0.20
MIN_N, MIN_THRESHOLD_N = 10, 20

share, diff, cell, fmt, pts, pct, fk = br.share, br.diff, br.cell, br.fmt, br.pts, br.pct, br.fk


def _ci(s: dict) -> str:
    return f"{pct(s['p'])}, {pct(s['lo'])} to {pct(s['hi'])}"


def lower_above_zero(d) -> bool:
    return d is not None and d[1] > 0


# --- round 3 ---

def rule_cells(find: list[dict], near: list[dict], decoys: list[dict]) -> dict:
    out = {}
    dc = cell(decoys)
    for rule in RULES:
        f = cell([v for v in find if v["rule"] == rule])
        n = cell([v for v in near if v["rule"] == rule])
        thr = rule in THRESHOLD_RULES
        out[rule] = {"findings": f, "near": n if thr else None,
                     "c_diff": diff(f["c"], n["c"]) if thr else None,
                     "acc_diff": diff(f["accepted"], n["accepted"]) if thr else None,
                     "blind_c_over_decoys": diff(f["blind_c"], dc["blind_c"]),
                     "blind_acc_over_decoys": diff(f["blind_accepted"], dc["blind_accepted"])}
    return out


def ranked(vs: list[dict]) -> dict:
    rk = [v for v in vs if v["item"] == "ranked"]
    cells = {r: share([v for v in rk if r in v.get("ranks", [])], "blind_accepted") for r in RANKS}
    # paired, exploratory: per document, composite against longest and against random
    by_doc: dict[str, dict[str, bool]] = {}
    for v in rk:
        for r in v.get("ranks", []):
            by_doc.setdefault(v["doc"], {})[r] = bool(v["blind_accepted"])
    paired = {}
    for other in ("longest", "random"):
        pairs = [(d["composite"], d[other]) for d in by_doc.values() if "composite" in d and other in d]
        paired[other] = {"n": len(pairs), "composite_only": sum(a and not b for a, b in pairs),
                         "other_only": sum(b and not a for a, b in pairs)}
    return {"cells": cells, "minus_longest": diff(cells["composite"], cells["longest"]),
            "minus_random": diff(cells["composite"], cells["random"]), "paired": paired, "docs": len(by_doc)}


def analyse(sample: list[dict] | None = None, labels: dict | None = None, vs: list[dict] | None = None) -> dict:
    vs = vs if vs is not None else br.votes(sample, labels)
    kinds = {k: [v for v in vs if v["item"] == k] for k in ("finding", "near", "decoy", "ranked")}
    find, near, decoy = kinds["finding"], kinds["near"], kinds["decoy"]
    res: dict = {"strata": {}, "decoys": {}, "pooled": {}, "models": {}, "ranked": {}}
    for st in STRATA:
        ff = [v for v in find if v["stratum"] == st]
        dd = [v for v in decoy if v["stratum"] == st]
        res["strata"][st] = {"rules": rule_cells(ff, [v for v in near if v["stratum"] == st], dd),
                             "agreement": br.agreement(ff), "n": len(ff),
                             "near_n": sum(1 for v in near if v["stratum"] == st)}
        res["decoys"][st] = cell(dd)
    tf = [v for v in find if v["stratum"] in TECHNICAL]
    tn = [v for v in near if v["stratum"] in TECHNICAL]
    td = [v for v in decoy if v["stratum"] in TECHNICAL]
    res["decoys"]["technical"] = cell(td)
    res["pooled"] = rule_cells(tf, tn, td)
    for rule in RULES:
        fv = [v for v in tf if v["rule"] == rule]
        res["models"][rule] = {m: {"c": share([{"x": v["model_c"][m]} for v in fv], "x"),
                                   "accepted": share([{"x": v["model_acc"][m]} for v in fv], "x")} for m in MODELS}
    tech_ranked = [v for v in kinds["ranked"] if v["stratum"] in TECHNICAL]
    res["ranked"]["technical"] = ranked(tech_ranked)
    for st in STRATA:
        res["ranked"][st] = ranked([v for v in kinds["ranked"] if v["stratum"] == st])
    # the rest of a stratum's family, for decision 2
    res["rest"] = {}
    for st in TECHNICAL:
        others = [s for s in (DOC_STRATA if st in DOC_STRATA else CODE_STRATA) if s != st]
        res["rest"][st] = {rule: cell([v for v in find if v["stratum"] in others and v["rule"] == rule])
                           for rule in RULES}
    res["agreement_all"] = br.agreement(tf)
    res["decisions"] = decide(res)
    return res


def decide(res: dict) -> list[tuple[str, str, str, str]]:
    """(rule, stratum or "technical", decision, reason) under the registered rules 1 to 8."""
    out = []
    # 1. thresholds, pooled over the technical strata
    for rule in THRESHOLD_RULES:
        p = res["pooled"][rule]
        f, n = p["findings"], p["near"]
        if f["c"]["n"] < MIN_THRESHOLD_N or n["c"]["n"] < MIN_THRESHOLD_N:
            out.append((rule, "technical", "threshold: too few to decide",
                        f"{f['c']['n']} findings, {n['c']['n']} near misses"))
            continue
        field, d = "c", p["c_diff"]
        if f["c"]["p"] < C_FLOOR and n["c"]["p"] < C_FLOOR:
            field, d = "accepted", p["acc_diff"]
        why = (f"{field}: findings {_ci(f[field])}, near misses {_ci(n[field])}, difference {pts(d)}"
               + ("; too little c to compare, so accepted shares are used" if field == "accepted" else ""))
        if d[1] > 0:
            out.append((rule, "technical", "the threshold earns its place", why))
        elif d[2] < 0:
            out.append((rule, "technical", "near misses judged worse than findings: test a lower threshold", why))
        else:
            out.append((rule, "technical", "threshold not supported by these labels", why))
    guarded = {st for st in TECHNICAL if res["strata"][st]["agreement"]["kappa_acc"] is not None
               and res["strata"][st]["agreement"]["kappa_acc"] < KAPPA_GUARD}
    for st in sorted(guarded):
        out.append(("all rules", st, "no proposal under rules 2, 4 and 5",
                    f"Fleiss' kappa for accepted {res['strata'][st]['agreement']['kappa_acc']:.2f}"))
    for st in TECHNICAL:
        for rule in RULES:
            r = res["strata"][st]["rules"][rule]
            f = r["findings"]
            acc, c, prs = f["accepted"], f["c"], f["present"]
            if acc["n"] < MIN_N:
                continue
            # 2. off for a kind
            if st not in guarded and acc["hi"] < OFF_FLOOR:
                ref = res["rest"][st][rule]["accepted"]
                d = diff(acc, ref) if ref["n"] >= MIN_N else None
                why = f"accepted {_ci(acc)}; against the rest {pts(d)}"
                if d is not None and d[2] < 0:
                    out.append((rule, st, f"proposed off for {st}", why))
                else:
                    out.append((rule, st, "low here but not distinguishable from the rest", why))
            # 3. chance placement in a kind
            d = r["blind_acc_over_decoys"]
            if not lower_above_zero(d):
                out.append((rule, st, "no better than chance placement in this kind",
                            f"unprimed c or d {_ci(f['blind_accepted'])}; over decoys {pts(d)}"))
            # 4. detection
            if st not in guarded and prs["hi"] < PRESENT_FLOOR:
                out.append((rule, st, "detection problem in this kind", f"present {_ci(prs)}"))
            # 5. candidate default
            if rule in OPT_IN_RULES and st not in guarded and acc["lo"] > CANDIDATE_ACC and c["lo"] > CANDIDATE_C \
                    and lower_above_zero(d):
                out.append((rule, st, f"candidate default for {st}",
                            f"accepted {_ci(acc)}; c {_ci(c)}; unprimed c or d over decoys {pts(d)}"))
    # 6. chance placement, pooled
    for rule in RULES:
        p = res["pooled"][rule]
        if not p["findings"]["c"]["n"]:
            continue
        if not lower_above_zero(p["blind_c_over_decoys"]) and not lower_above_zero(p["blind_acc_over_decoys"]):
            out.append((rule, "technical", "no better than chance placement without priming",
                        f"unprimed c over decoys {pts(p['blind_c_over_decoys'])}; unprimed c or d "
                        f"{pts(p['blind_acc_over_decoys'])}"))
    # 8. ranking
    rk = res["ranked"]["technical"]
    ml, mr = rk["minus_longest"], rk["minus_random"]
    why = f"composite minus longest {pts(ml)}; composite minus random {pts(mr)}"
    if lower_above_zero(ml):
        out.append(("ranking", "technical", "the composite is worth shipping as a ranking", why))
    elif ml is not None and ml[0] > 0 and lower_above_zero(mr):
        out.append(("ranking", "technical", "looser result only: the composite beats random, and longest "
                    "by point estimate", why))
    else:
        out.append(("ranking", "technical", "the composite does not beat sentence length", why))
    return out


# --- part B: defaults across rounds ---

def round1(sample: list[dict]) -> list[dict]:
    """Round 1's S1 findings and D-random decoys, in the item shape of rounds 2 and 3."""
    out = []
    for x in sample:
        if x.get("stratum") != "S1":
            continue
        kind = {"": "finding", "random": "decoy"}.get(x.get("decoy", ""))
        if kind:
            out.append(x | {"item": kind, "round": 1})
    return out


def round2(sample: list[dict]) -> list[dict]:
    out, seen = [], set()
    for x in sample:
        if x["i"] == DUPLICATE_R2 and x["i"] in seen:
            continue
        seen.add(x["i"])
        out.append(x | {"round": 2})
    return out


def defaults(r1: list[dict], r2: list[dict], r3: list[dict]) -> dict:
    """Votes of each round in; per rule, tests (i) and (ii) pooled and per round, and the decision."""
    r3 = [v for v in r3 if v["stratum"] in TECHNICAL]
    rounds = {1: r1, 2: r2, 3: r3}
    out = {}
    for rule in RULES:
        def tests(vs_by_round: dict[int, list[dict]]) -> dict:
            allv = [v for vs in vs_by_round.values() for v in vs]
            f = [v for v in allv if v["item"] == "finding" and v["rule"] == rule]
            f23 = [v for v in f if v["round"] in (2, 3)]
            n23 = [v for v in allv if v["item"] == "near" and v["rule"] == rule and v["round"] in (2, 3)]
            d = [v for v in allv if v["item"] == "decoy"]
            fa, na = share(f23, "accepted"), share(n23, "accepted")
            fb, db = share(f, "blind_accepted"), share(d, "blind_accepted")
            return {"findings_accepted": fa, "near_accepted": na, "findings_blind": fb, "decoys_blind": db,
                    "i": diff(fa, na) if rule in THRESHOLD_RULES else None, "ii": diff(fb, db)}

        pooled = tests(rounds)
        per = {k: tests({k: vs}) for k, vs in rounds.items() if any(v["rule"] == rule and v["item"] == "finding"
                                                                     for v in vs)}
        out[rule] = {"pooled": pooled, "per_round": per, "decision": decision_b(rule, pooled),
                     "differs": sorted(k for k, t in per.items() if decision_b(rule, t) != decision_b(rule, pooled)
                                       and (t["i"] is not None or t["ii"] is not None))}
    return out


def decision_b(rule: str, t: dict) -> str:
    i_ok, ii_ok = lower_above_zero(t["i"]), lower_above_zero(t["ii"])
    if rule in DEFAULT_RULES:
        return "stays default" if (i_ok or ii_ok) else "proposed opt-in"
    ok = ii_ok and (i_ok if rule in THRESHOLD_RULES else True)
    return "proposed default" if ok else "stays opt-in"


# --- rendering ---

def render(res: dict, counts: dict | None = None, part_b: dict | None = None) -> str:
    intro = ("Computed by `scripts/kinds_report.py` as `docs/prereg/kinds-precision.md` fixes it. c: at least 7 of "
             "the 12 primed raters label the item c; accepted: at least 7 label it c or d; present: at least 7 say the "
             "construction is there; unprimed c (c or d): at least 2 of the 3 unprimed raters label it c (c or d). "
             "Wilson 95% intervals; differences with Newcombe 95% intervals. Pooled means the ten technical strata "
             "(the contrast stratum left out).")
    out = ["# Precision by kind of document: results", "", intro, ""]
    if counts:
        out += ["## Counts", "", "| Stratum | Findings (deduplicated) | Near misses (deduplicated) | Sampled findings | "
                "Sampled near misses | Decoys | Ranked documents | Ranked items |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for st in STRATA:
            c = counts.get(st)
            if not c:
                continue
            out.append(f"| {st} | {sum(c['findings'].values())} ({sum(c['deduped'].values())}) | "
                       f"{sum(c['near'].values())} ({sum(c['near_deduped'].values())}) | "
                       f"{sum(c['sampled'].values())} | {sum(c['sampled_near'].values())} | {c['decoys']} | "
                       f"{c.get('ranked_docs', 0)} | {c.get('ranked', 0)} |")
        out += ["", "Steps before the draw: " + json.dumps({k: v for k, v in counts.items()
                                                            if k.startswith("_") and k != "_items"}), ""]
    out += ["## Primary: c share of findings beside near misses", "",
            "| Stratum | Rule | Findings, c | Near misses, c | Difference |", "| --- | --- | --- | --- | --- |"]
    for st in STRATA:
        for rule in RULES:
            r = res["strata"][st]["rules"][rule]
            if not r["findings"]["c"]["n"] and not (r["near"] and r["near"]["c"]["n"]):
                continue
            out.append(f"| {st} | {rule} | {fmt(r['findings']['c'])} | "
                       f"{fmt(r['near']['c']) if r['near'] else 'no threshold'} | {pts(r['c_diff'])} |")
    out += ["", "## Secondary, per stratum", ""]
    for st in STRATA:
        sr = res["strata"][st]
        out += [f"### {st}", "", f"{sr['n']} findings, {sr['near_n']} near misses; random decoys: unprimed c "
                f"{fmt(res['decoys'][st]['blind_c'])}, unprimed c or d {fmt(res['decoys'][st]['blind_accepted'])}.", "",
                "| Rule | Item | Accepted | Present | Unprimed c | Unprimed c or d | Unprimed c over decoys | "
                "Unprimed c or d over decoys |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for rule in RULES:
            r = sr["rules"][rule]
            for kind, s in (("findings", r["findings"]), ("near misses", r["near"])):
                if s and s["c"]["n"]:
                    extra = (f"{pts(r['blind_c_over_decoys'])} | {pts(r['blind_acc_over_decoys'])}"
                             if kind == "findings" else "- | -")
                    out.append(f"| {rule} | {kind} | {fmt(s['accepted'])} | {fmt(s['present'])} | "
                               f"{fmt(s['blind_c'])} | {fmt(s['blind_accepted'])} | {extra} |")
        a = sr["agreement"]
        out += ["", f"Fleiss' kappa over the twelve ({a['n']} complete findings, {a['incomplete']} incomplete): "
                f"c/d/w {fk(a['kappa3'])}, c against not {fk(a['kappa_c'])}, accepted against not "
                f"{fk(a['kappa_acc'])}; unprimed c against not {fk(a['kappa_blind_c'])} ({a['blind_n']} complete).", ""]
    out += ["## Random decoys", "", "| Stratum | c | Accepted | Present | Unprimed c | Unprimed c or d |",
            "| --- | --- | --- | --- | --- | --- |"]
    for st in (*STRATA, "technical"):
        d = res["decoys"][st]
        out.append(f"| {st} | {fmt(d['c'])} | {fmt(d['accepted'])} | {fmt(d['present'])} | {fmt(d['blind_c'])} | "
                   f"{fmt(d['blind_accepted'])} |")
    out += ["", "## Pooled over the technical strata", "",
            "| Rule | Findings, c | Near, c | c difference | Findings, accepted | Near, accepted | "
            "Accepted difference | Unprimed c over decoys | Unprimed c or d over decoys |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for rule in RULES:
        p = res["pooled"][rule]
        thr = rule in THRESHOLD_RULES
        out.append(f"| {rule} | {fmt(p['findings']['c'])} | {fmt(p['near']['c']) if thr else '-'} | "
                   f"{pts(p['c_diff']) if thr else '-'} | {fmt(p['findings']['accepted'])} | "
                   f"{fmt(p['near']['accepted']) if thr else '-'} | {pts(p['acc_diff']) if thr else '-'} | "
                   f"{pts(p['blind_c_over_decoys'])} | {pts(p['blind_acc_over_decoys'])} |")
    out += ["", "## Per model (majority of its three), findings pooled", "",
            "| Rule | " + " | ".join(f"{m} c | {m} accepted" for m in MODELS) + " |",
            "| --- |" + " --- | --- |" * len(MODELS)]
    for rule in RULES:
        m = res["models"][rule]
        if m[next(iter(MODELS))]["c"]["n"]:
            out.append(f"| {rule} | " + " | ".join(f"{fmt(m[x]['c'])} | {fmt(m[x]['accepted'])}" for x in MODELS) + " |")
    rk = res["ranked"]["technical"]
    out += ["", "## Ranked sentences (unprimed raters only)", "",
            f"{rk['docs']} documents, pooled over the technical strata. Unprimed c or d:", "",
            "| Ranking | Unprimed c or d |", "| --- | --- |"]
    out += [f"| {r} | {fmt(rk['cells'][r])} |" for r in RANKS]
    out += ["", f"Composite minus longest: {pts(rk['minus_longest'])}. Composite minus random: "
            f"{pts(rk['minus_random'])}.", "",
            "Exploratory, paired by document: " + "; ".join(
                f"against {k}, {v['n']} documents, composite alone accepted in {v['composite_only']}, {k} alone in "
                f"{v['other_only']}" for k, v in rk["paired"].items()) + ".", "",
            "| Stratum | Documents | Composite | Longest | Random |", "| --- | --- | --- | --- | --- |"]
    for st in STRATA:
        r = res["ranked"][st]
        if r["docs"]:
            out.append(f"| {st} | {r['docs']} | " + " | ".join(fmt(r["cells"][x]) for x in RANKS) + " |")
    if part_b:
        out += ["", "## Defaults across rounds (part B)", "",
                "(i): findings' accepted share minus near misses', rounds 2 and 3. (ii): findings' unprimed c-or-d "
                "share minus the random decoys', rounds 1 to 3.", "",
                "| Rule | Findings accepted | Near accepted | (i) | Findings unprimed c or d | Decoys unprimed c or d | "
                "(ii) | Decision | Differs in round |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for rule in RULES:
            b = part_b[rule]
            p = b["pooled"]
            out.append(f"| {rule} | {fmt(p['findings_accepted'])} | {fmt(p['near_accepted'])} | {pts(p['i'])} | "
                       f"{fmt(p['findings_blind'])} | {fmt(p['decoys_blind'])} | {pts(p['ii'])} | {b['decision']} | "
                       f"{', '.join(map(str, b['differs'])) or '-'} |")
        out += ["", "Per round:", "", "| Rule | Round | (i) | (ii) |", "| --- | --- | --- | --- |"]
        for rule in RULES:
            for k, t in part_b[rule]["per_round"].items():
                out.append(f"| {rule} | {k} | {pts(t['i'])} | {pts(t['ii'])} |")
    out += ["", "## Decisions", ""]
    out += [f"- {rule} ({st}): {what}. {why}." for rule, st, what, why in res["decisions"]] or ["None."]
    if part_b:
        out += [f"- {rule} (rounds 1 to 3): {b['decision']}." for rule, b in part_b.items()]
    return "\n".join(out) + "\n"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--labels", type=Path, default=Path("/home/claude/kinds-batches/labels"))
    ap.add_argument("--sample", type=Path, default=ROOT / "eval/kinds/sample.jsonl")
    ap.add_argument("--counts", type=Path, default=ROOT / "eval/kinds/counts.json")
    ap.add_argument("--round1", type=Path, default=ROOT / "eval/heldout")
    ap.add_argument("--round2", type=Path, default=ROOT / "eval/breadth")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    sample = read_jsonl(args.sample)
    counts = json.loads(args.counts.read_text()) if args.counts.exists() else None
    labels = br.load_labels(args.labels)
    missing = [r for r in PRIMED + BLIND if not labels[r]]
    if missing:
        print(f"no labels for {', '.join(missing)}; their items count as unlabelled", file=sys.stderr)
    v3 = br.votes(sample, labels)
    res = analyse(vs=v3)
    part_b = None
    if (args.round1 / "sample.jsonl").exists() and (args.round2 / "sample.jsonl").exists():
        v1 = br.votes(round1(read_jsonl(args.round1 / "sample.jsonl")), br.load_labels(args.round1 / "labels"))
        v2 = br.votes(round2(read_jsonl(args.round2 / "sample.jsonl")), br.load_labels(args.round2 / "labels"))
        part_b = defaults(v1, v2, [v | {"round": 3} for v in v3])
    text = render(res, counts, part_b)
    if args.out:
        args.out.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
