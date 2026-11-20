"""Report for the breadth precision test (docs/prereg/breadth-precision.md).

    uv run python scripts/breadth_report.py [--labels DIR] [--out REPORT.md]

Reads the committed pointers (eval/breadth/sample.jsonl, eval/breadth/counts.json)
and fifteen label files: DIR/rater1.json to DIR/rater12.json (primed) and
DIR/blind1.json to DIR/blind3.json (unprimed); default DIR:
/home/claude/breadth-batches/labels. A file is a JSON list of {"id": <item id>,
"label": "c" | "d" | "w", "construction_present": true | false} (unprimed files
need no "construction_present"); the shapes scripts/heldout_report.py reads
are read too, including the raters' reply objects. Writes markdown with every
outcome and decision the pre-registration names. No item text is read.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from heldout_report import fleiss, newcombe, parse_labels, wilson

ROOT = Path(__file__).resolve().parent.parent
PRIMED = tuple(f"rater{k}" for k in range(1, 13))
BLIND = ("blind1", "blind2", "blind3")
MODELS = {"Opus 5.5": PRIMED[0:3], "Sonnet 5.5": PRIMED[3:6], "Haiku 5.5": PRIMED[6:9], "Fable 5.2": PRIMED[9:12]}

DEFAULT_RULES = ("stacked-nouns", "long-dependency", "reduced-object-relative", "hyphen-compound", "inline-list")
OPT_IN_RULES = ("inanimate-subject", "participial-clause", "nominalization", "center-embedding",
                "undefined-acronym")
RULES = DEFAULT_RULES + OPT_IN_RULES
THRESHOLD_RULES = ("stacked-nouns", "inline-list", "long-dependency", "center-embedding", "undefined-acronym")
FAMILIES = ("md", "rst", "html", "doc comments", "commit", "pr")
SRC_STRATA = ("src-py", "src-rs", "src-go", "src-js", "src-jvm", "src-c", "src-rb")

PRIMED_MAJORITY = 7       # of 12; six against six is not a majority
BLIND_MAJORITY = 2        # of 3
OFF_FLOOR = 0.25          # decisions 2 and 3
PRESENT_FLOOR = 0.5       # decision 4
CANDIDATE_ACC, CANDIDATE_C = 0.5, 0.10  # decision 5
C_FLOOR = 0.10            # decision 1: both c shares under this -> compare accepted shares
KAPPA_GUARD = 0.20        # decision 7
MIN_FAMILY_N = 10         # decisions 2 and 4
MIN_THRESHOLD_N = 20      # decision 1
MIN_POOLED_N = 40         # decision 3


# --- labels and votes ---

def load_labels(folder: Path, names=PRIMED + BLIND) -> dict[str, dict[int, dict]]:
    out = {}
    for name in names:
        p = folder / f"{name}.json"
        out[name] = parse_labels(json.loads(p.read_text())) if p.exists() else {}
    return out


def votes(items: list[dict], labels: dict[str, dict[int, dict]]) -> list[dict]:
    """Per item, every rater's label and the majorities. A missing label counts as not c, not accepted, not present."""
    out = []
    for it in items:
        lab = [labels.get(r, {}).get(it["i"], {}).get("label") for r in PRIMED]
        pres = [labels.get(r, {}).get(it["i"], {}).get("present") for r in PRIMED]
        blind = [labels.get(r, {}).get(it["i"], {}).get("label") for r in BLIND]
        c = [x == "c" for x in lab]
        acc = [x in ("c", "d") for x in lab]
        prs = [x is True for x in pres]
        bc = [x == "c" for x in blind]
        bacc = [x in ("c", "d") for x in blind]
        out.append(it | {
            "labels": lab, "blind_labels": blind,
            "c": sum(c) >= PRIMED_MAJORITY, "accepted": sum(acc) >= PRIMED_MAJORITY,
            "present": sum(prs) >= PRIMED_MAJORITY,
            "blind_c": sum(bc) >= BLIND_MAJORITY, "blind_accepted": sum(bacc) >= BLIND_MAJORITY,
            "c_votes": c, "acc_votes": acc,
            "model_c": {m: sum(x == "c" for x in lab[PRIMED.index(rs[0]):PRIMED.index(rs[0]) + 3]) >= 2
                        for m, rs in MODELS.items()},
            "model_acc": {m: sum(x in ("c", "d") for x in lab[PRIMED.index(rs[0]):PRIMED.index(rs[0]) + 3]) >= 2
                          for m, rs in MODELS.items()},
            "complete": all(x is not None for x in lab) and all(x is not None for x in pres),
            "blind_complete": all(x is not None for x in blind)})
    return out


def share(vs: list[dict], field: str) -> dict:
    k, n = sum(bool(v[field]) for v in vs), len(vs)
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "p": k / n if n else None, "lo": lo, "hi": hi}


def diff(a: dict, b: dict) -> tuple[float, float, float] | None:
    if not a["n"] or not b["n"]:
        return None
    return newcombe(a["k"], a["n"], b["k"], b["n"])


def agreement(vs: list[dict]) -> dict:
    full = [v for v in vs if v["complete"]]
    n = len(PRIMED)
    three = [[sum(1 for x in v["labels"] if x == c) for c in "cdw"] for v in full]
    cvn = [[sum(v["c_votes"]), n - sum(v["c_votes"])] for v in full]
    acc = [[sum(v["acc_votes"]), n - sum(v["acc_votes"])] for v in full]
    bfull = [v for v in vs if v["blind_complete"]]
    bc = [[sum(x == "c" for x in v["blind_labels"]), 3 - sum(x == "c" for x in v["blind_labels"])] for v in bfull]
    return {"n": len(full), "incomplete": len(vs) - len(full), "kappa3": fleiss(three), "kappa_c": fleiss(cvn),
            "kappa_acc": fleiss(acc), "blind_n": len(bfull), "kappa_blind_c": fleiss(bc)}


# --- analysis ---

def cell(vs: list[dict]) -> dict:
    return {f: share(vs, f) for f in ("c", "accepted", "present", "blind_c", "blind_accepted")}


def analyse(sample: list[dict] | None = None, labels: dict | None = None,
            vs: list[dict] | None = None) -> dict:
    vs = vs if vs is not None else votes(sample, labels)
    find = [v for v in vs if v["item"] == "finding"]
    near = [v for v in vs if v["item"] == "near"]
    decoy = [v for v in vs if v["item"] == "decoy"]
    res: dict = {"families": {}, "strata": {}, "pooled": {}, "models": {}, "decoys": {}, "decisions": []}
    for fam in FAMILIES:
        ff = [v for v in find if v["family"] == fam]
        rules = {}
        for rule in RULES:
            fv = [v for v in ff if v["rule"] == rule]
            nv = [v for v in near if v["family"] == fam and v["rule"] == rule]
            f, n = cell(fv), cell(nv)
            rules[rule] = {"findings": f, "near": n if rule in THRESHOLD_RULES else None,
                           "c_diff": diff(f["c"], n["c"]) if rule in THRESHOLD_RULES else None,
                           "acc_diff": diff(f["accepted"], n["accepted"]) if rule in THRESHOLD_RULES else None}
        res["families"][fam] = {"rules": rules, "agreement": agreement(ff), "n": len(ff),
                                "near_n": sum(1 for v in near if v["family"] == fam)}
        res["decoys"][fam] = cell([v for v in decoy if v["family"] == fam])
    res["decoys"]["all"] = cell(decoy)
    for st in SRC_STRATA:
        res["strata"][st] = {rule: {"findings": cell([v for v in find if v["stratum"] == st and v["rule"] == rule]),
                                    "near": cell([v for v in near if v["stratum"] == st and v["rule"] == rule])}
                             for rule in RULES}
    for rule in RULES:
        fv = [v for v in find if v["rule"] == rule]
        nv = [v for v in near if v["rule"] == rule]
        f, n = cell(fv), cell(nv)
        res["pooled"][rule] = {"findings": f, "near": n, "c_diff": diff(f["c"], n["c"]),
                               "acc_diff": diff(f["accepted"], n["accepted"]),
                               "blind_over_decoys": diff(f["blind_c"], res["decoys"]["all"]["blind_c"])}
        res["models"][rule] = {m: {"c": share([{"x": v["model_c"][m]} for v in fv], "x"),
                                   "accepted": share([{"x": v["model_acc"][m]} for v in fv], "x")} for m in MODELS}
    res["agreement_all"] = agreement(find)
    res["decisions"] = decide(res)
    return res


def _ci(s: dict) -> str:
    return f"{pct(s['p'])}, {pct(s['lo'])} to {pct(s['hi'])}"


def decide(res: dict) -> list[tuple[str, str, str, str]]:
    """(rule, family or "all", decision, reason) under the registered rules 1 to 7."""
    out = []
    # 1. thresholds, pooled
    for rule in THRESHOLD_RULES:
        p = res["pooled"][rule]
        f, n = p["findings"], p["near"]
        if f["c"]["n"] < MIN_THRESHOLD_N or n["c"]["n"] < MIN_THRESHOLD_N:
            out.append((rule, "all", "threshold: too few to decide", f"{f['c']['n']} findings, {n['c']['n']} near misses"))
            continue
        field, d = "c", p["c_diff"]
        if f["c"]["p"] < C_FLOOR and n["c"]["p"] < C_FLOOR:  # point estimates (amendment of 19 November)
            field, d = "accepted", p["acc_diff"]
        why = (f"{field}: findings {_ci(f[field])}, near misses {_ci(n[field])}, difference "
               f"{pts(d)}" + ("; too little c to compare, so accepted shares are used" if field == "accepted" else ""))
        if d[1] > 0:
            out.append((rule, "all", "the threshold earns its place", why))
        elif d[2] < 0:
            out.append((rule, "all", "near misses judged worse than findings: test a lower threshold", why))
        else:
            out.append((rule, "all", "threshold not supported by these labels", why))
    guarded = {fam for fam, r in res["families"].items()
               if r["agreement"]["kappa_acc"] is not None and r["agreement"]["kappa_acc"] < KAPPA_GUARD}
    for fam in sorted(guarded):
        out.append(("all rules", fam, "no proposal under rules 2, 4 and 5",
                    f"Fleiss' kappa for accepted {res['families'][fam]['agreement']['kappa_acc']:.2f}"))
    md = res["families"]["md"]["rules"]
    for fam in FAMILIES:
        for rule in RULES:
            f = res["families"][fam]["rules"][rule]["findings"]
            acc, c, prs = f["accepted"], f["c"], f["present"]
            # 2. off in one format
            if fam != "md" and acc["n"] >= MIN_FAMILY_N \
                    and fam not in guarded and acc["hi"] < OFF_FLOOR:
                ref = md[rule]["findings"]["accepted"]
                d = diff(acc, ref) if ref["n"] >= MIN_FAMILY_N else None
                why = f"accepted {_ci(acc)}; against md {pts(d)}"
                if d is not None and d[2] < 0:
                    out.append((rule, fam, f"proposed off for {fam}", why))
                else:
                    out.append((rule, fam, "low here but not distinguishable from Markdown", why))
            # 4. detection
            if prs["n"] >= MIN_FAMILY_N and fam not in guarded and prs["hi"] < PRESENT_FLOOR:
                out.append((rule, fam, "detection problem in this format", f"present {_ci(prs)}"))
            # 5. candidate default
            if rule in OPT_IN_RULES and acc["n"] and fam not in guarded \
                    and acc["lo"] > CANDIDATE_ACC and c["lo"] > CANDIDATE_C:
                out.append((rule, fam, f"candidate default for {fam}", f"accepted {_ci(acc)}; c {_ci(c)}"))
    # 3. opt-in everywhere
    for rule in DEFAULT_RULES:
        acc = res["pooled"][rule]["findings"]["accepted"]
        if acc["n"] >= MIN_POOLED_N and acc["hi"] < OFF_FLOOR:
            out.append((rule, "all", "proposed for opt-in everywhere", f"accepted {_ci(acc)}"))
    # 6. chance placement without priming
    for rule in RULES:
        d = res["pooled"][rule]["blind_over_decoys"]
        if d is None:
            continue
        if d[1] <= 0:
            f = res["pooled"][rule]["findings"]["blind_c"]
            out.append((rule, "all", "no better than chance placement without priming",
                        f"unprimed c {_ci(f)}; over random decoys {pts(d)}"))
    return out


# --- rendering ---

def pct(x) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def pts(d) -> str:
    return "n/a" if d is None else f"{100 * d[0]:+.0f} points ({100 * d[1]:+.0f} to {100 * d[2]:+.0f})"


def fmt(s: dict | None) -> str:
    if not s or not s["n"]:
        return "none"
    return f"{s['k']}/{s['n']} ({pct(s['p'])}; {pct(s['lo'])} to {pct(s['hi'])})"


def fk(x) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def render(res: dict, counts: dict | None = None) -> str:
    intro = ("Computed by `scripts/breadth_report.py` as `docs/prereg/breadth-precision.md` fixes it. "
             "c: at least 7 of the 12 primed raters label the item c (an editor would fix it); accepted: at least 7 "
             "label it c or d; present: at least 7 say the construction is there; unprimed c: at least 2 of the "
             "3 unprimed raters label it c. Wilson 95% intervals; differences with Newcombe 95% intervals.")
    out = ["# Breadth precision: results", "", intro, ""]
    if counts:
        head = ("| Stratum | Findings (deduplicated) | Near misses (deduplicated) | Sampled findings | "
                "Sampled near misses | Decoys |")
        out += ["## Counts", "", head, "| --- | --- | --- | --- | --- | --- |"]
        for st, c in counts.items():
            if st.startswith("_"):
                continue
            out.append(f"| {st} | {sum(c['findings'].values())} ({sum(c['deduped'].values())}) | "
                       f"{sum(c['near'].values())} ({sum(c['near_deduped'].values())}) | "
                       f"{sum(c['sampled'].values())} | {sum(c['sampled_near'].values())} | {c['decoys']} |")
        out += ["", "Steps before the draw: " + json.dumps({k: v for k, v in counts.items() if k.startswith("_")
                                                             and k != "_items"}), ""]
    out += ["## Primary: c share of findings beside near misses", "",
            "| Family | Rule | Findings, c | Near misses, c | Difference |", "| --- | --- | --- | --- | --- |"]
    for fam in FAMILIES:
        for rule in RULES:
            r = res["families"][fam]["rules"][rule]
            if not r["findings"]["c"]["n"] and not (r["near"] and r["near"]["c"]["n"]):
                continue
            out.append(f"| {fam} | {rule} | {fmt(r['findings']['c'])} | "
                       f"{fmt(r['near']['c']) if r['near'] else 'no threshold'} | {pts(r['c_diff'])} |")
    out += ["", "## Secondary, per family", ""]
    for fam in FAMILIES:
        fr = res["families"][fam]
        out += [f"### {fam}", "", f"{fr['n']} findings, {fr['near_n']} near misses.", "",
                "| Rule | Kind | Accepted | Present | Unprimed c | Unprimed c or d |", "| --- | --- | --- | --- | --- | --- |"]
        for rule in RULES:
            r = fr["rules"][rule]
            for kind, s in (("findings", r["findings"]), ("near misses", r["near"])):
                if s and s["c"]["n"]:
                    out.append(f"| {rule} | {kind} | {fmt(s['accepted'])} | {fmt(s['present'])} | "
                               f"{fmt(s['blind_c'])} | {fmt(s['blind_accepted'])} |")
        a = fr["agreement"]
        line = (f"Fleiss' kappa over the twelve ({a['n']} complete findings, {a['incomplete']} incomplete): "
                f"c/d/w {fk(a['kappa3'])}, c against not {fk(a['kappa_c'])}, accepted against not "
                f"{fk(a['kappa_acc'])}; unprimed c against not {fk(a['kappa_blind_c'])} ({a['blind_n']} complete).")
        out += ["", line, ""]
    out += ["## Random decoys", "", "| Family | c | Accepted | Present | Unprimed c |", "| --- | --- | --- | --- | --- |"]
    for fam in (*FAMILIES, "all"):
        d = res["decoys"][fam]
        out.append(f"| {fam} | {fmt(d['c'])} | {fmt(d['accepted'])} | {fmt(d['present'])} | {fmt(d['blind_c'])} |")
    head = ("| Rule | Findings, c | Near, c | c difference | Findings, accepted | Near, accepted | "
            "Accepted difference | Unprimed c over decoys |")
    out += ["", "## Pooled over families", "", head, "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for rule in RULES:
        p = res["pooled"][rule]
        thr = rule in THRESHOLD_RULES
        out.append(f"| {rule} | {fmt(p['findings']['c'])} | {fmt(p['near']['c']) if thr else '-'} | "
                   f"{pts(p['c_diff']) if thr else '-'} | {fmt(p['findings']['accepted'])} | "
                   f"{fmt(p['near']['accepted']) if thr else '-'} | {pts(p['acc_diff']) if thr else '-'} | "
                   f"{pts(p['blind_over_decoys'])} |")
    out += ["", "## Per model (majority of its three), findings pooled over families", "",
            "| Rule | " + " | ".join(f"{m} c | {m} accepted" for m in MODELS) + " |",
            "| --- |" + " --- | --- |" * len(MODELS)]
    for rule in RULES:
        m = res["models"][rule]
        if not m[next(iter(MODELS))]["c"]["n"]:
            continue
        out.append(f"| {rule} | " + " | ".join(f"{fmt(m[x]['c'])} | {fmt(m[x]['accepted'])}" for x in MODELS) + " |")
    out += ["", "## Doc comments by language (small n; decides nothing)", "",
            "| Stratum | Rule | Findings, c | Findings, accepted | Present | Near, c |", "| --- | --- | --- | --- | --- | --- |"]
    for st in SRC_STRATA:
        for rule in RULES:
            r = res["strata"][st][rule]
            if r["findings"]["c"]["n"]:
                out.append(f"| {st} | {rule} | {fmt(r['findings']['c'])} | {fmt(r['findings']['accepted'])} | "
                           f"{fmt(r['findings']['present'])} | {fmt(r['near']['c'])} |")
    out += ["", "## Decisions", ""]
    out += [f"- {rule} ({fam}): {what}. {why}." for rule, fam, what, why in res["decisions"]] or ["None."]
    return "\n".join(out) + "\n"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--labels", type=Path, default=Path("/home/claude/breadth-batches/labels"))
    ap.add_argument("--sample", type=Path, default=ROOT / "eval/breadth/sample.jsonl")
    ap.add_argument("--counts", type=Path, default=ROOT / "eval/breadth/counts.json")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    sample = [json.loads(x) for x in args.sample.read_text().splitlines()]
    counts = json.loads(args.counts.read_text()) if args.counts.exists() else None
    labels = load_labels(args.labels)
    missing = [r for r in PRIMED + BLIND if not labels[r]]
    if missing:
        print(f"no labels for {', '.join(missing)}; their items count as unlabelled", file=sys.stderr)
    text = render(analyse(sample, labels), counts)
    if args.out:
        args.out.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
