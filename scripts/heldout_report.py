"""Report for the held-out precision test (docs/prereg/heldout-precision.md).

    uv run python scripts/heldout_report.py [--labels DIR] [--out REPORT.md]

Reads the committed pointers (eval/heldout/sample.jsonl, eval/heldout/counts.json)
and three label files, DIR/rater1.json, DIR/rater2.json and DIR/rater3.json
(default DIR: /home/claude/heldout-batches/labels). A label file is a JSON
list of {"id": <item id>, "label": "c" | "d" | "w", "construction_present":
true | false}; "i" for "id", "present" for "construction_present", the full
words correct / defensible / wrong, and the raters' reply objects
({"labels": [...]}, one or a list of them) are read as well. Writes
markdown with every outcome and decision the pre-registration names. No
item text is read.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RATERS = ("rater1", "rater2", "rater3")
DEFAULT_RULES = ("stacked-nouns", "long-dependency", "inanimate-subject", "reduced-object-relative",
                 "hyphen-compound", "inline-list")
OPT_IN_RULES = ("participial-clause", "nominalization", "center-embedding", "undefined-acronym")
RULES = DEFAULT_RULES + OPT_IN_RULES
VERIFIED_RULES = {"stacked-nouns", "reduced-object-relative", "long-dependency"}  # verify_model checks these

# Rater 1 (Claude) on the 210 in-sample findings, from docs/evaluation.md
# "Precision of the sample": (c or d, present, n).
IN_SAMPLE = {
    "stacked-nouns": (7, 20, 31),
    "long-dependency": (9, 9, 32),
    "inanimate-subject": (7, 10, 32),
    "reduced-object-relative": (1, 18, 32),
    "hyphen-compound": (4, 4, 19),
    "inline-list": (4, 13, 32),
}

OPT_IN_FLOOR = 0.25      # decision 1
PRESENT_FLOOR = 0.5      # decision 2
CANDIDATE_FLOOR = 0.5    # decision 3
MIN_N = 20               # decision 5
KAPPA_GUARD, AGREE_GUARD = 0.20, 0.80  # decision 6
BOOT, BOOT_SEED = 2000, 0
Z = 1.959964


# --- statistics ---

def wilson(k: int, n: int, z: float = Z) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - h) / d), min(1.0, (c + h) / d))


def newcombe(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float, float]:
    """p1 - p2 and its Newcombe hybrid score 95% interval (method 10)."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


def fleiss(table: list[list[int]]) -> float | None:
    """Fleiss' kappa from per-item category counts (every row sums to the same number of raters)."""
    if not table:
        return None
    n = sum(table[0])
    if n < 2:
        return None
    big_n = len(table)
    p_i = [(sum(x * x for x in row) - n) / (n * (n - 1)) for row in table]
    p_bar = sum(p_i) / big_n
    p_j = [sum(row[j] for row in table) / (big_n * n) for j in range(len(table[0]))]
    p_e = sum(p * p for p in p_j)
    if p_e >= 1:
        return None
    return (p_bar - p_e) / (1 - p_e)


def pairwise_agreement(rows: list[list[bool]]) -> float | None:
    pairs = agree = 0
    for row in rows:
        for a in range(len(row)):
            for b in range(a + 1, len(row)):
                pairs += 1
                agree += row[a] == row[b]
    return agree / pairs if pairs else None


# --- labels ---

def _norm_label(v) -> str | None:
    if not isinstance(v, str) or not v:
        return None
    v = v.strip().lower()[:1]
    return v if v in "cdw" else None


def parse_labels(data) -> dict[int, dict]:
    """{id: {"label": c|d|w|None, "present": bool|None}} from any accepted shape."""
    if isinstance(data, dict):
        data = data.get("labels", [])
    entries = []
    for x in data:
        if isinstance(x, dict) and "labels" in x and isinstance(x["labels"], list):
            entries += x["labels"]
        else:
            entries.append(x)
    out = {}
    for e in entries:
        i = e.get("id", e.get("i"))
        if i is None:
            continue
        present = e.get("construction_present", e.get("present"))
        out[int(i)] = {"label": _norm_label(e.get("label")),
                       "present": present if isinstance(present, bool) else None}
    return out


def load_labels(folder: Path) -> dict[str, dict[int, dict]]:
    return {r: parse_labels(json.loads((folder / f"{r}.json").read_text())) for r in RATERS}


# --- per-item votes ---

def votes(items: list[dict], labels: dict[str, dict[int, dict]]) -> list[dict]:
    out = []
    for it in items:
        got = [labels[r].get(it["i"], {}) for r in RATERS]
        lab = [g.get("label") for g in got]
        pres = [g.get("present") for g in got]
        acc = [x in ("c", "d") for x in lab]   # a missing label counts as not accepted
        prs = [x is True for x in pres]         # and as not present
        out.append(it | {"labels": lab, "presents": pres, "accepted": sum(acc) >= 2, "present": sum(prs) >= 2,
                         "acc_votes": acc, "present_votes": prs, "complete": all(x is not None for x in lab)
                         and all(x is not None for x in pres)})
    return out


def agreement(vs: list[dict]) -> dict:
    full = [v for v in vs if v["complete"]]
    three = [[sum(1 for x in v["labels"] if x == c) for c in "cdw"] for v in full]
    acc = [[sum(v["acc_votes"]), 3 - sum(v["acc_votes"])] for v in full]
    pres = [[sum(v["present_votes"]), 3 - sum(v["present_votes"])] for v in full]
    return {"n": len(full), "incomplete": len(vs) - len(full), "kappa3": fleiss(three), "kappa_acc": fleiss(acc),
            "kappa_present": fleiss(pres), "pairwise_acc": pairwise_agreement([v["acc_votes"] for v in full])}


def share(vs: list[dict], field: str) -> dict:
    k, n = sum(v[field] for v in vs), len(vs)
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "p": k / n if n else None, "lo": lo, "hi": hi}


def rater_counts(vs: list[dict], rater: int) -> Counter:
    return Counter(v["labels"][rater] or "missing" for v in vs)


def weighted_share(by_rule: dict[str, list[bool]], weights: dict[str, float], boot: int = BOOT,
                   seed: int = BOOT_SEED) -> tuple[float, float, float] | None:
    """Population-weighted accepted share over rules, and a stratified bootstrap 95% interval."""
    rules = [r for r in by_rule if by_rule[r] and weights.get(r)]
    if not rules:
        return None
    total = sum(weights[r] for r in rules)
    w = {r: weights[r] / total for r in rules}
    est = sum(w[r] * sum(by_rule[r]) / len(by_rule[r]) for r in rules)
    rng = random.Random(seed)
    stats = []
    for _ in range(boot):
        s = 0.0
        for r in rules:
            xs = by_rule[r]
            s += w[r] * sum(rng.choice(xs) for _ in xs) / len(xs)
        stats.append(s)
    stats.sort()
    return est, stats[int(0.025 * boot)], stats[int(0.975 * boot) - 1]


# --- the report ---

def pct(x) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def fmt_share(s: dict) -> str:
    return f"{s['k']} of {s['n']} ({pct(s['p'])}; {pct(s['lo'])} to {pct(s['hi'])})" if s["n"] else "none"


def fmt_k(x) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def analyse(sample: list[dict], counts: dict, labels: dict[str, dict[int, dict]]) -> dict:
    vs = votes(sample, labels)
    res: dict = {"strata": {}, "decisions": [], "labels": {}}
    for stratum in ("S1", "S2"):
        st_items = [v for v in vs if v["stratum"] == stratum]
        real = [v for v in st_items if not v["decoy"]]
        decoys = [v for v in st_items if v["decoy"]]
        dec_acc = share(decoys, "accepted")
        rules = {}
        for rule in RULES:
            rv = [v for v in real if v["rule"] == rule]
            acc, prs = share(rv, "accepted"), share(rv, "present")
            diff = newcombe(acc["k"], acc["n"], dec_acc["k"], dec_acc["n"]) if acc["n"] and dec_acc["n"] else None
            rules[rule] = {"accepted": acc, "present": prs, "over_decoys": diff, "agreement": agreement(rv),
                           "raters": [rater_counts(rv, j) for j in range(len(RATERS))]}
        deco = {"all": dec_acc, "all_present": share(decoys, "present"),
                "kind": {k: share([v for v in decoys if v["decoy"] == k], "accepted") for k in ("random", "long")},
                "kind_present": {k: share([v for v in decoys if v["decoy"] == k], "present")
                                 for k in ("random", "long")},
                "name": {r: share([v for v in decoys if v["rule"] == r], "accepted") for r in RULES}}
        weights = counts.get("deduped", {}).get(stratum, {})
        pooled = weighted_share({r: [v["accepted"] for v in real if v["rule"] == r] for r in DEFAULT_RULES},
                                {r: weights.get(r, 0) for r in DEFAULT_RULES})
        res["strata"][stratum] = {"rules": rules, "decoys": deco, "agreement": agreement(real),
                                  "decoy_agreement": agreement(decoys), "pooled_default": pooled,
                                  "n_real": len(real), "n_decoys": len(decoys)}
    # comparison with rater 1 in-sample, S1
    comp = {}
    s1 = [v for v in vs if v["stratum"] == "S1" and not v["decoy"]]
    for rule, (k_in, _, n_in) in IN_SAMPLE.items():
        rv = [v for v in s1 if v["rule"] == rule]
        if not rv:
            continue
        per = []
        for j in range(len(RATERS)):
            k = sum(1 for v in rv if v["labels"][j] in ("c", "d"))
            per.append((k, len(rv)) + newcombe(k, len(rv), k_in, n_in))
        lows, highs = [p[3] for p in per], [p[4] for p in per]
        verdict = "higher" if all(x > 0 for x in lows) else "lower" if all(x < 0 for x in highs) else "no clear difference"
        comp[rule] = {"in_sample": (k_in, n_in), "raters": per, "verdict": verdict}
    res["comparison"] = comp
    # decisions, S1
    s1r = res["strata"]["S1"]
    guard = s1r["agreement"]
    withheld = (guard["kappa_acc"] is not None and guard["kappa_acc"] < KAPPA_GUARD
                and guard["pairwise_acc"] is not None and guard["pairwise_acc"] < AGREE_GUARD)
    res["withheld"] = withheld
    s2r = res["strata"]["S2"]["rules"]
    for rule in RULES:
        r = s1r["rules"][rule]
        acc, prs, diff = r["accepted"], r["present"], r["over_decoys"]
        if acc["n"] < MIN_N:
            res["decisions"].append((rule, "too few findings to decide", f"n = {acc['n']}"))
            continue
        if rule in DEFAULT_RULES and acc["hi"] < OPT_IN_FLOOR:
            note = ""
            s2 = s2r[rule]["accepted"]
            if s2["n"] and s2["lo"] > OPT_IN_FLOOR:
                note = "; S2 points the other way, so the proposal may hold for READMEs only"
            res["decisions"].append((rule, "proposed for opt-in", f"accepted upper bound {pct(acc['hi'])}{note}"))
        if prs["hi"] < PRESENT_FLOOR:
            what = ("run the verify_model leg on this sample first" if rule in VERIFIED_RULES
                    else "look at the detector")
            note = ""
            s2 = s2r[rule]["present"]
            if s2["n"] and s2["lo"] > PRESENT_FLOOR:
                note = "; S2 points the other way, so this may hold for READMEs only"
            res["decisions"].append((rule, "detection problem, not a cost problem",
                                     f"present upper bound {pct(prs['hi'])}: {what}{note}"))
        if rule in OPT_IN_RULES and acc["lo"] > CANDIDATE_FLOOR:
            res["decisions"].append((rule, "candidate for more testing as a default",
                                     f"accepted lower bound {pct(acc['lo'])}"))
        if diff is not None and diff[1] <= 0:
            res["decisions"].append((rule, "not distinguishable from chance placement",
                                     (f"accepted share over decoys {100 * diff[0]:+.0f} points "
                                     f"({100 * diff[1]:+.0f} to {100 * diff[2]:+.0f})")))
    return res


def render(res: dict) -> str:
    out = ["# Held-out precision: results", "",
           "Computed by `scripts/heldout_report.py` as `docs/prereg/heldout-precision.md` fixes it.", ""]
    for stratum, title in (("S1", "S1, READMEs (primary)"), ("S2", "S2, docs files (secondary; decides nothing)")):
        st = res["strata"][stratum]
        d = st["decoys"]
        out += [f"## {title}", "",
                f"{st['n_real']} findings and {st['n_decoys']} decoys.", "",
                "| Rule | n | Accepted (majority c or d) | Over decoys, points | Present (majority) |",
                "| --- | --- | --- | --- | --- |"]
        for rule in RULES:
            r = st["rules"][rule]
            diff = r["over_decoys"]
            dtxt = "n/a" if diff is None else f"{100 * diff[0]:+.0f} ({100 * diff[1]:+.0f} to {100 * diff[2]:+.0f})"
            out.append(f"| {rule} | {r['accepted']['n']} | {fmt_share(r['accepted'])} | {dtxt} | "
                       f"{fmt_share(r['present'])} |")
        out += ["", "Decoy baseline:", "",
                "| Decoys | Accepted | Present |", "| --- | --- | --- |",
                f"| all | {fmt_share(d['all'])} | {fmt_share(d['all_present'])} |"]
        for k in ("random", "long"):
            out.append(f"| D-{k} | {fmt_share(d['kind'][k])} | {fmt_share(d['kind_present'][k])} |")
        out += ["", "Decoys by the rule name they were given (small n; decides nothing): "
                + ", ".join(f"{r} {d['name'][r]['k']}/{d['name'][r]['n']}" for r in RULES) + ".", ""]
        out += ["Rater counts (c / d / w / missing) and agreement among the three:", "",
                ("| Rule | Rater 1 | Rater 2 | Rater 3 | Fleiss c/d/w | Fleiss accepted | Fleiss present | "
                "Pairwise agreement, accepted |"),
                "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for rule in RULES:
            r = st["rules"][rule]
            if not r["accepted"]["n"]:
                continue
            cells = [" / ".join(str(c[x]) for x in ("c", "d", "w", "missing")) for c in r["raters"]]
            a = r["agreement"]
            out.append(f"| {rule} | {' | '.join(cells)} | {fmt_k(a['kappa3'])} | {fmt_k(a['kappa_acc'])} | "
                       f"{fmt_k(a['kappa_present'])} | {pct(a['pairwise_acc'])} |")
        a = st["agreement"]
        out += [(f"| all findings | | | | {fmt_k(a['kappa3'])} | {fmt_k(a['kappa_acc'])} | "
                f"{fmt_k(a['kappa_present'])} | {pct(a['pairwise_acc'])} |"), ""]
        if a["incomplete"]:
            out += [f"{a['incomplete']} findings lack a label from some rater and are left out of the kappas.", ""]
        p = st["pooled_default"]
        if p:
            out += [(f"Default rules together, weighted by each rule's share of the stratum's findings: "
                    f"{pct(p[0])} accepted (bootstrap 95%: {pct(p[1])} to {pct(p[2])})."), ""]
    out += ["## Against rater 1 in-sample (S1, default rules)", "",
            ("Each held-out rater's own c-or-d share against rater 1's on the 210 in-sample findings, "
            "with Newcombe 95% intervals for the difference."), "",
            "| Rule | In-sample | Rater 1 | Rater 2 | Rater 3 | Reading |", "| --- | --- | --- | --- | --- | --- |"]
    for rule, c in res["comparison"].items():
        k_in, n_in = c["in_sample"]
        cells = [f"{k}/{n}, {100 * dd:+.0f} ({100 * lo:+.0f} to {100 * hi:+.0f})" for k, n, dd, lo, hi in c["raters"]]
        out.append(f"| {rule} | {k_in}/{n_in} | {' | '.join(cells)} | {c['verdict']} |")
    out += ["", "## Decisions (S1)", ""]
    if res["withheld"]:
        out += [("The raters do not agree enough to act on (Fleiss' kappa for accepted under 0.20 and pairwise "
                "agreement under 80%), so no proposal is made. The labels each rule would have received:"), ""]
    if res["decisions"]:
        out += [f"- {rule}: {what} ({why})" for rule, what, why in res["decisions"]]
    else:
        out.append("No rule meets a decision rule.")
    return "\n".join(out) + "\n"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--labels", type=Path, default=Path("/home/claude/heldout-batches/labels"))
    ap.add_argument("--sample", type=Path, default=ROOT / "eval/heldout/sample.jsonl")
    ap.add_argument("--counts", type=Path, default=ROOT / "eval/heldout/counts.json")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    sample = [json.loads(x) for x in args.sample.read_text().splitlines()]
    counts = json.loads(args.counts.read_text())
    text = render(analyse(sample, counts, load_labels(args.labels)))
    if args.out:
        args.out.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
