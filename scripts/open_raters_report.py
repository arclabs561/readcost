"""Report for the re-rating with open models (docs/prereg/open-family-raters.md).

    uv run python scripts/open_raters_report.py [--eval DIR] [--out DIR]

Reads, per round, the committed pointers (eval/heldout/sample.jsonl,
eval/breadth/sample.jsonl, eval/kinds/sample.jsonl) and the label files in
eval/<round>/labels/: the Claude panel's rater1.json to rater12.json and
blind1.json to blind3.json, and the open models' files that
scripts/open_raters_job.py writes, open-<family>-primed-s1.json and so on.
No item text is read.

For each panel of the plan (Claude, open, Claude and open, each family,
and the greedy samples) it recomputes each round's pre-registered tables
and decisions with that round's own analysis code, with the panel's raters
and majorities in place of the Claude panel's, and writes them to
OUT/<panel>/round<N>.md. OUT/report.md has the run's coverage, the
agreement tables and the answers to the plan's questions Q1 to Q5. Default
OUT: eval/open-raters.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import breadth_report as br
import heldout_report as hr
import kinds_report as kr
from heldout_report import fleiss, newcombe, parse_labels, wilson

ROOT = Path(__file__).resolve().parent.parent
ROUND_DIRS = {1: "heldout", 2: "breadth", 3: "kinds"}
FAMILIES = ("qwen", "gemma", "glm", "mistral", "olmo")
SAMPLED = ("s1", "s2", "s3")
CLAUDE_MODELS = {"Opus 5.5": ("rater1", "rater2", "rater3"), "Sonnet 5.5": ("rater4", "rater5", "rater6"),
                 "Haiku 5.5": ("rater7", "rater8", "rater9"), "Fable 5.2": ("rater10", "rater11", "rater12")}
CLAUDE_BLIND = ("blind1", "blind2", "blind3")
RULES = br.RULES
COVERAGE_FLOOR = 0.95     # stopping rule 4
KAPPA_FLAG = 0.20
DECOY_FLAG = 0.25
OPT_IN_FLOOR = 0.25       # Q5, #98
BOOT, BOOT_SEED = 2000, 0


@dataclass
class Panel:
    name: str
    primed: tuple[str, ...]
    blind: tuple[str, ...]
    models: dict[str, tuple[str, ...]]

    @property
    def primed_majority(self) -> int:
        return len(self.primed) // 2 + 1

    @property
    def blind_majority(self) -> int:
        return len(self.blind) // 2 + 1


def open_name(family: str, proto: str, sample: str) -> str:
    return f"open-{family}-{proto}-{sample}"


def family_panel(family: str, samples=SAMPLED) -> Panel:
    primed = tuple(open_name(family, "primed", s) for s in samples)
    return Panel(family, primed, tuple(open_name(family, "unprimed", s) for s in samples), {family: primed})


def claude_panel() -> Panel:
    return Panel("claude", tuple(r for rs in CLAUDE_MODELS.values() for r in rs), CLAUDE_BLIND, dict(CLAUDE_MODELS))


def open_panel(families, samples=SAMPLED) -> Panel:
    ps = [family_panel(f, samples) for f in families]
    return Panel("open", tuple(r for p in ps for r in p.primed), tuple(r for p in ps for r in p.blind),
                 {p.name: p.primed for p in ps})


def combined_panel(families, samples=SAMPLED) -> Panel:
    c, o = claude_panel(), open_panel(families, samples)
    return Panel("claude-and-open", c.primed + o.primed, c.blind + o.blind, c.models | o.models)


def greedy_panel(families) -> Panel:
    primed = tuple(open_name(f, "primed", "greedy") for f in families)
    return Panel("open-greedy", primed, tuple(open_name(f, "unprimed", "greedy") for f in families),
                 {f: (r,) for f, r in zip(families, primed)})


# --- votes, for any panel ---

def _maj(flags: list[bool], need: int) -> bool:
    return sum(flags) >= need


def votes(items: list[dict], labels: dict[str, dict[int, dict]], panel: Panel) -> list[dict]:
    """breadth_report.votes for any panel; a missing label counts as not c, not accepted, not present."""
    out = []
    for it in items:
        def get(r, i=it["i"]):
            return labels.get(r, {}).get(i, {})
        lab = [get(r).get("label") for r in panel.primed]
        pres = [get(r).get("present") for r in panel.primed]
        blind = [get(r).get("label") for r in panel.blind]
        c = [x == "c" for x in lab]
        acc = [x in ("c", "d") for x in lab]
        prs = [x is True for x in pres]
        bc = [x == "c" for x in blind]
        bacc = [x in ("c", "d") for x in blind]
        model_c, model_acc = {}, {}
        for m, rs in panel.models.items():
            ml = [get(r).get("label") for r in rs]
            need = len(rs) // 2 + 1
            model_c[m] = sum(x == "c" for x in ml) >= need
            model_acc[m] = sum(x in ("c", "d") for x in ml) >= need
        out.append(it | {
            "labels": lab, "presents": pres, "blind_labels": blind,
            "c": _maj(c, panel.primed_majority), "accepted": _maj(acc, panel.primed_majority),
            "present": _maj(prs, panel.primed_majority),
            "blind_c": _maj(bc, panel.blind_majority), "blind_accepted": _maj(bacc, panel.blind_majority),
            "c_votes": c, "acc_votes": acc, "present_votes": prs, "model_c": model_c, "model_acc": model_acc,
            "complete": all(x is not None for x in lab) and all(x is not None for x in pres),
            "blind_complete": all(x is not None for x in blind)})
    return out


def agreement(vs: list[dict]) -> dict:
    """breadth_report.agreement (and heldout_report's keys) for any number of raters."""
    full = [v for v in vs if v["complete"]]
    n = len(full[0]["labels"]) if full else 0
    three = [[sum(1 for x in v["labels"] if x == c) for c in "cdw"] for v in full]
    cvn = [[sum(v["c_votes"]), n - sum(v["c_votes"])] for v in full]
    acc = [[sum(v["acc_votes"]), n - sum(v["acc_votes"])] for v in full]
    prs = [[sum(v["present_votes"]), n - sum(v["present_votes"])] for v in full]
    bfull = [v for v in vs if v["blind_complete"]]
    bn = len(bfull[0]["blind_labels"]) if bfull else 0
    bc = [[sum(x == "c" for x in v["blind_labels"]), bn - sum(x == "c" for x in v["blind_labels"])] for v in bfull]
    return {"n": len(full), "incomplete": len(vs) - len(full), "kappa3": fleiss(three), "kappa_c": fleiss(cvn),
            "kappa_acc": fleiss(acc), "kappa_present": fleiss(prs), "blind_n": len(bfull),
            "kappa_blind_c": fleiss(bc), "pairwise_acc": hr.pairwise_agreement([v["acc_votes"] for v in full])}


@contextlib.contextmanager
def as_panel(panel: Panel, labels_by_round: dict | None = None):
    """Run the round scripts' analysis with this panel's raters and majorities in place of Claude's."""
    saved = {(br, "PRIMED"): br.PRIMED, (br, "BLIND"): br.BLIND, (br, "MODELS"): br.MODELS,
             (br, "PRIMED_MAJORITY"): br.PRIMED_MAJORITY, (br, "BLIND_MAJORITY"): br.BLIND_MAJORITY,
             (br, "agreement"): br.agreement, (kr, "MODELS"): kr.MODELS, (kr, "PRIMED"): kr.PRIMED,
             (kr, "BLIND"): kr.BLIND, (hr, "RATERS"): hr.RATERS, (hr, "votes"): hr.votes,
             (hr, "agreement"): hr.agreement}
    br.PRIMED, br.BLIND, br.MODELS = panel.primed, panel.blind, panel.models
    br.PRIMED_MAJORITY, br.BLIND_MAJORITY = panel.primed_majority, panel.blind_majority
    br.agreement = agreement
    kr.MODELS, kr.PRIMED, kr.BLIND = panel.models, panel.primed, panel.blind
    hr.RATERS = panel.primed
    hr.votes = lambda sample, labels: votes(sample, labels, panel)
    hr.agreement = agreement
    try:
        yield
    finally:
        for (mod, name), value in saved.items():
            setattr(mod, name, value)


def describe(text: str, panel: Panel) -> str:
    """The round report's wording of the Claude panel's majorities, made true for this panel."""
    p, pm, b, bm = len(panel.primed), panel.primed_majority, len(panel.blind), panel.blind_majority
    for old, new in (("at least 7 of the 12 primed raters", f"at least {pm} of the {p} primed raters"),
                     ("at least 7 ", f"at least {pm} "),
                     ("at least 2 of the 3 unprimed raters", f"at least {bm} of the {b} unprimed raters"),
                     ("over the twelve", f"over the {p} primed raters"),
                     ("majority of its three", "majority of its raters")):
        text = text.replace(old, new)
    return text


# --- loading ---

def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def load_round(eval_dir: Path, rnd: int) -> tuple[list[dict], dict[str, dict[int, dict]], dict | None]:
    d = eval_dir / ROUND_DIRS[rnd]
    sample = read_jsonl(d / "sample.jsonl")
    if rnd == 2:
        sample = kr.round2(sample)  # the one item drawn twice counts once, as part B counts it
    labels = {p.stem: parse_labels(json.loads(p.read_text())) for p in sorted((d / "labels").glob("*.json"))}
    counts = json.loads((d / "counts.json").read_text()) if (d / "counts.json").exists() else None
    return sample, labels, counts


def expected_ids(sample: list[dict], rnd: int, proto: str) -> set[int]:
    """Every item is shown unprimed; every item but round 3's ranked sentences is shown primed."""
    return {x["i"] for x in sample if proto == "unprimed" or x.get("item") != "ranked"}


def coverage(rounds: dict, families) -> dict[str, dict[str, float]]:
    """Per family, round and protocol, the lowest share of expected items its sampled raters labelled."""
    out = {}
    for fam in families:
        out[fam] = {}
        for rnd, (sample, labels, _) in rounds.items():
            for proto in ("primed", "unprimed"):
                want = expected_ids(sample, rnd, proto)
                shares = [len(want & set(labels.get(open_name(fam, proto, s), {}))) / len(want)
                          for s in SAMPLED if want]
                out[fam][f"round{rnd} {proto}"] = min(shares) if shares else None
    return out


# --- statistics for the questions ---

def share(flags: list[bool]) -> dict:
    k, n = sum(flags), len(flags)
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "p": k / n if n else None, "lo": lo, "hi": hi}


def paired_diff(a: list[bool], b: list[bool], boot: int = BOOT, seed: int = BOOT_SEED):
    """Mean of a minus mean of b on the same items, with a percentile bootstrap 95% interval."""
    n = len(a)
    if not n:
        return None
    d = [int(x) - int(y) for x, y in zip(a, b)]
    est = sum(d) / n
    rng = random.Random(seed)
    stats = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n for _ in range(boot))
    return est, stats[int(0.025 * boot)], stats[int(0.975 * boot) - 1]


def cohen(a: list[bool], b: list[bool]) -> float | None:
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe >= 1 else (po - pe) / (1 - pe)


def above(d) -> bool:
    return d is not None and d[1] > 0


def findings(vs_by_round: dict[int, list[dict]]) -> list[dict]:
    """Findings of rounds 1 to 3, round 3 in the technical kinds only."""
    out = []
    for rnd, vs in vs_by_round.items():
        for v in vs:
            if rnd == 1 and v.get("decoy"):
                continue
            if rnd in (2, 3) and v.get("item") != "finding":
                continue
            if rnd == 3 and v.get("stratum") not in kr.TECHNICAL:
                continue
            out.append(v)
    return out


def random_decoys(vs_by_round: dict[int, list[dict]]) -> list[dict]:
    return [v for rnd, vs in vs_by_round.items() for v in vs
            if (rnd == 1 and v.get("decoy") == "random") or (rnd in (2, 3) and v.get("item") == "decoy")]


def q1(vs_by_round) -> dict:
    f = findings(vs_by_round)
    per = {rule: paired_diff([v["accepted"] for v in f if v["rule"] == rule],
                             [v["blind_accepted"] for v in f if v["rule"] == rule]) for rule in RULES}
    return {"pooled": paired_diff([v["accepted"] for v in f], [v["blind_accepted"] for v in f]), "rules": per}


def q1_verdict(open_q1: dict, claude_q1: dict) -> tuple[str, list[str]]:
    claude_rules = [r for r, d in claude_q1["rules"].items() if above(d)]
    open_rules = [r for r in claude_rules if above(open_q1["rules"].get(r))]
    pooled = open_q1["pooled"]
    if above(pooled) and claude_rules and len(open_rules) * 2 >= len(claude_rules):
        return "replicates", open_rules
    if pooled is None or pooled[1] <= 0 <= pooled[2] or pooled[2] < 0:
        return "does not replicate", open_rules
    return "partial", open_rules


def longest_test(v3: list[dict], v1: list[dict]) -> dict:
    """Q2 and Q3: unprimed c-or-d share of each rule's findings minus that of the longest sentences."""
    tech = [v for v in v3 if v.get("stratum") in kr.TECHNICAL]
    longest = share([v["blind_accepted"] for v in tech if v.get("item") == "ranked" and "longest" in v.get("ranks", [])])
    long1 = share([v["blind_accepted"] for v in v1 if v.get("decoy") == "long"])
    out = {"longest": longest, "long_decoys_r1": long1, "rules": {}}
    for rule in RULES:
        f3 = share([v["blind_accepted"] for v in tech if v.get("item") == "finding" and v["rule"] == rule])
        f1 = share([v["blind_accepted"] for v in v1 if not v.get("decoy") and v["rule"] == rule])
        out["rules"][rule] = {
            "r3": f3, "r3_diff": newcombe(f3["k"], f3["n"], longest["k"], longest["n"]) if f3["n"] and longest["n"]
            else None,
            "r1": f1, "r1_diff": newcombe(f1["k"], f1["n"], long1["k"], long1["n"]) if f1["n"] and long1["n"] else None}
    return out


def answers(open_vs: dict, claude_vs: dict, open_part_b: dict, open_rank: dict) -> dict:
    qa = {"q1_open": q1(open_vs), "q1_claude": q1(claude_vs)}
    qa["q1"] = q1_verdict(qa["q1_open"], qa["q1_claude"])
    lt = longest_test(open_vs[3], open_vs[1])
    qa["longest"] = lt
    beats = sorted(r for r, x in lt["rules"].items() if above(x["r3_diff"]))
    qa["q2"] = {"beats": beats,
                "answer": "yes" if beats == ["center-embedding"] else
                ("no: center-embedding does not beat it" if "center-embedding" not in beats else
                 "no: others beat it too")}
    qa["q3"] = {r: "still fails" if not above(lt["rules"][r]["r3_diff"]) else "passes"
                for r in ("inanimate-subject", "participial-clause", "nominalization")}
    ml = open_rank["minus_longest"]
    qa["q4"] = {"minus_longest": ml, "answer": "still does not beat it" if not above(ml) else "beats it"}
    ce = open_part_b["center-embedding"]["pooled"]
    fails = [name for name, d in (("over near misses", ce["i"]), ("over random decoys, unprimed", ce["ii"]),
                                  ("over the longest sentence, unprimed", lt["rules"]["center-embedding"]["r3_diff"]))
             if not above(d)]
    qa["q5_107"] = {"fails": fails, "answer": "propose turning it off by default" if len(fails) >= 2 else
                    ("disagreement recorded; the default stays" if len(fails) == 1 else "stands")}
    inan = share([v["accepted"] for v in findings(open_vs) if v["rule"] == "inanimate-subject"])
    passes = qa["q3"]["inanimate-subject"] == "passes"
    accepted = inan["n"] > 0 and inan["lo"] > OPT_IN_FLOOR
    qa["q5_98"] = {"accepted": inan, "beats_longest": passes,
                   "answer": "propose turning it back on" if accepted and passes else
                   ("open models accept it; recorded, it stays opt-in" if accepted else "stands")}
    return qa


def agreement_tables(claude_vs: dict, fam_vs: dict[str, dict], open_vs: dict) -> list[dict]:
    """Per family and round (and pooled): Fleiss within the family, over Claude's twelve with it, and Cohen."""
    rows = []
    for fam, fvs in [*fam_vs.items(), ("open", open_vs)]:
        for scope in (1, 2, 3, "pooled"):
            rnds = (1, 2, 3) if scope == "pooled" else (scope,)
            cf = findings({r: claude_vs[r] for r in rnds})
            ff = findings({r: fvs[r] for r in rnds})
            both = [[c, f] for c, f in zip(cf, ff) if c["complete"] and f["complete"]]
            n_all = len(both[0][0]["labels"]) + len(both[0][1]["labels"]) if both else 0
            joint = [[sum(c["acc_votes"]) + sum(f["acc_votes"]), n_all - sum(c["acc_votes"]) - sum(f["acc_votes"])]
                     for c, f in both]
            fa = agreement(ff)
            rows.append({"family": fam, "scope": scope, "n": len(ff), "kappa_acc": fa["kappa_acc"],
                         "kappa3": fa["kappa3"], "kappa_with_claude": fleiss(joint),
                         "cohen_primed": cohen([v["accepted"] for v in cf], [v["accepted"] for v in ff]),
                         "cohen_unprimed": cohen([v["blind_accepted"] for v in cf], [v["blind_accepted"] for v in ff])})
    return rows


# --- rendering ---

def pct(x) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def fs(s: dict) -> str:
    return f"{s['k']} of {s['n']} ({pct(s['p'])}; {pct(s['lo'])} to {pct(s['hi'])})" if s["n"] else "none"


def pts(d) -> str:
    return "n/a" if d is None else f"{100 * d[0]:+.0f} points ({100 * d[1]:+.0f} to {100 * d[2]:+.0f})"


def fk(x) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def render_round1(res: dict, vs: list[dict], panel: Panel) -> str:
    out = [f"# Round 1 (held-out READMEs and docs files), panel {panel.name}", "",
           (f"Majorities: {panel.primed_majority} of {len(panel.primed)} primed raters, {panel.blind_majority} of "
            f"{len(panel.blind)} unprimed. Computed with `scripts/heldout_report.py`'s analysis."), ""]
    for stratum in ("S1", "S2"):
        st = res["strata"][stratum]
        sv = [v for v in vs if v["stratum"] == stratum]
        out += [f"## {stratum}", "", "| Rule | Accepted | Over decoys | Present | c | Unprimed c or d |",
                "| --- | --- | --- | --- | --- | --- |"]
        for rule in RULES:
            r = st["rules"].get(rule)
            if not r or not r["accepted"]["n"]:
                continue
            rv = [v for v in sv if not v["decoy"] and v["rule"] == rule]
            out.append(f"| {rule} | {fs(r['accepted'])} | {pts(r['over_decoys'])} | {fs(r['present'])} | "
                       f"{fs(share([v['c'] for v in rv]))} | {fs(share([v['blind_accepted'] for v in rv]))} |")
        for kind in ("random", "long"):
            dv = [v for v in sv if v["decoy"] == kind]
            out.append(f"| decoys, {kind} | {fs(st['decoys']['kind'][kind])} | | "
                       f"{fs(st['decoys']['kind_present'][kind])} | {fs(share([v['c'] for v in dv]))} | "
                       f"{fs(share([v['blind_accepted'] for v in dv]))} |")
        a = st["agreement"]
        out += ["", f"Fleiss' kappa, accepted: {fk(a['kappa_acc'])}; c/d/w: {fk(a['kappa3'])} ({a['n']} complete "
                f"findings).", ""]
    out += ["## Decisions (S1)", ""]
    if res["withheld"]:
        out.append("Agreement is under the plan's guard, so these are not acted on.")
    out += [f"- {rule}: {what} ({why})" for rule, what, why in res["decisions"]] or ["None."]
    return "\n".join(out) + "\n"


def render_report(meta: dict) -> str:
    qa = meta["answers"]
    out = ["# Re-rating with open models: results", "",
           "Computed by `scripts/open_raters_report.py` as `docs/prereg/open-family-raters.md` fixes it. The "
           "questions are answered with the open panel alone; the other panels are in the folders beside this "
           "file and decide nothing.", "",
           f"Open panel: {', '.join(meta['families'])}" + (f"; left out: {meta['excluded']}" if meta["excluded"]
                                                             else "") + ".", "",
           "## Coverage", "", "Lowest share of expected items each family's sampled raters labelled.", "",
           "| Family | " + " | ".join(meta["coverage_keys"]) + " |", "| --- |" + " --- |" * len(meta["coverage_keys"])]
    for fam, cov in meta["coverage"].items():
        out.append(f"| {fam} | " + " | ".join(pct(cov.get(k)) for k in meta["coverage_keys"]) + " |")
    out += ["", "## Q1. Priming: primed accepted minus unprimed c or d, findings of rounds 1 to 3", "",
            "| Rule | Open | Claude |", "| --- | --- | --- |"]
    for rule in RULES:
        out.append(f"| {rule} | {pts(qa['q1_open']['rules'][rule])} | {pts(qa['q1_claude']['rules'][rule])} |")
    out.append(f"| all rules | {pts(qa['q1_open']['pooled'])} | {pts(qa['q1_claude']['pooled'])} |")
    verdict, rules = qa["q1"]
    out += ["", f"Answer: {verdict} (rules where it replicates among those where Claude's does: "
            f"{', '.join(rules) or 'none'}).", "",
            "## Q2 and Q3. Unprimed findings against the longest sentence", "",
            f"Round 3, technical kinds: the longest sentences are a problem (c or d) to the open panel in "
            f"{fs(qa['longest']['longest'])}. Round 1's long decoys: {fs(qa['longest']['long_decoys_r1'])}.", "",
            "| Rule | Round 3 findings | Minus longest | Round 1 findings | Minus long decoys (secondary) |",
            "| --- | --- | --- | --- | --- |"]
    for rule, x in qa["longest"]["rules"].items():
        out.append(f"| {rule} | {fs(x['r3'])} | {pts(x['r3_diff'])} | {fs(x['r1'])} | {pts(x['r1_diff'])} |")
    out += ["", f"Q2: {qa['q2']['answer']} (rules that beat it: {', '.join(qa['q2']['beats']) or 'none'}).",
            "Q3: " + "; ".join(f"{r} {a}" for r, a in qa["q3"].items()) + ".", "",
            "## Q4. Ranking", "", f"Composite minus longest: {pts(qa['q4']['minus_longest'])}. The composite "
            f"{qa['q4']['answer']}.", "", "## Q5. #107 and #98", "",
            f"#107 (center-embedding default): fails {', '.join(qa['q5_107']['fails']) or 'none'}; "
            f"{qa['q5_107']['answer']}.", "",
            f"#98 (inanimate-subject opt-in): accepted primed in {fs(qa['q5_98']['accepted'])}; beats the longest "
            f"sentence: {'yes' if qa['q5_98']['beats_longest'] else 'no'}; {qa['q5_98']['answer']}.", "",
            "## Agreement on findings", "",
            "| Family | Round | n | Fleiss accepted, within | Fleiss c/d/w, within | Fleiss accepted, with Claude's 12 "
            "| Cohen vs Claude, primed | Cohen vs Claude, unprimed |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in meta["agreement"]:
        out.append(f"| {r['family']} | {r['scope']} | {r['n']} | {fk(r['kappa_acc'])} | {fk(r['kappa3'])} | "
                   f"{fk(r['kappa_with_claude'])} | {fk(r['cohen_primed'])} | {fk(r['cohen_unprimed'])} |")
    out += ["", "## Families against Claude", "",
            "| Rule | Claude | " + " | ".join(meta["families"]) + " |", "| --- | --- |" + " --- |" * len(meta["families"])]
    for rule in RULES:
        out.append(f"| {rule} | {pct(meta['by_family']['claude'][rule]['p'])} | " +
                   " | ".join(pct(meta["by_family"][f][rule]["p"]) for f in meta["families"]) + " |")
    out += ["", "Shares of findings (rounds 1 to 3) each panel's majority accepts, primed. Random decoys accepted: "
            + ", ".join(f"{k} {fs(v)}" for k, v in meta["decoys"].items()) + "."]
    if meta["flags"]:
        out += ["", "Named under the plan: " + "; ".join(meta["flags"]) + "."]
    return "\n".join(out) + "\n"


# --- main ---

def analyse_panel(panel: Panel, rounds: dict) -> dict:
    """Votes per round, and each round's own analysis and text, for one panel."""
    vs = {rnd: votes(s, labels, panel) for rnd, (s, labels, _) in rounds.items()}
    texts, extra = {}, {}
    with as_panel(panel):
        s1, labels1, counts1 = rounds[1]
        res1 = hr.analyse(s1, counts1 or {}, labels1)
        texts[1] = render_round1(res1, vs[1], panel)
        res2 = br.analyse(vs=vs[2])
        texts[2] = describe(br.render(res2, rounds[2][2]), panel)
        res3 = kr.analyse(vs=vs[3])
        part_b = kr.defaults(votes(kr.round1(s1), labels1, panel), [v | {"round": 2} for v in vs[2]],
                             [v | {"round": 3} for v in vs[3]])
        texts[3] = describe(kr.render(res3, rounds[3][2], part_b), panel)
        extra = {"part_b": part_b, "ranked": res3["ranked"]["technical"]}
    return {"votes": vs, "texts": texts, **extra}


def build(eval_dir: Path, families=None) -> dict:
    rounds = {rnd: load_round(eval_dir, rnd) for rnd in ROUND_DIRS}
    present = set().union(*(set(labels) for _, labels, _ in rounds.values()))
    fams = [f for f in (families or FAMILIES) if any(open_name(f, "primed", s) in present for s in SAMPLED)]
    cov = coverage(rounds, fams)
    excluded = [f for f in fams if any(v is not None and v < COVERAGE_FLOOR for v in cov[f].values())]
    kept = [f for f in fams if f not in excluded]
    panels = [claude_panel(), open_panel(kept), combined_panel(kept), *(family_panel(f) for f in fams),
              greedy_panel(kept)]
    done = {p.name: analyse_panel(p, rounds) for p in panels}
    open_vs, claude_vs = done["open"]["votes"], done["claude"]["votes"]
    qa = answers(open_vs, claude_vs, done["open"]["part_b"], done["open"]["ranked"])
    by_family = {}
    for name in ["claude", *fams]:
        f = findings(done[name]["votes"])
        by_family[name] = {rule: share([v["accepted"] for v in f if v["rule"] == rule]) for rule in RULES}
    decoys = {name: share([v["accepted"] for v in random_decoys(done[name]["votes"])]) for name in ["claude", *fams]}
    agree = agreement_tables(claude_vs, {f: done[f]["votes"] for f in fams}, open_vs)
    flags = []
    for row in agree:
        if row["scope"] == "pooled" and row["family"] != "open" and row["cohen_primed"] is not None \
                and row["cohen_primed"] < KAPPA_FLAG:
            flags.append(f"{row['family']}: Cohen's kappa against Claude {row['cohen_primed']:.2f}")
    for f in fams:
        if decoys[f]["n"] and decoys[f]["p"] > DECOY_FLAG:
            flags.append(f"{f}: accepts {pct(decoys[f]['p'])} of random decoys")
    keys = [f"round{r} {p}" for r in ROUND_DIRS for p in ("primed", "unprimed")]
    meta = {"families": kept, "excluded": excluded, "coverage": cov, "coverage_keys": keys, "answers": qa,
            "agreement": agree, "by_family": by_family, "decoys": decoys, "flags": flags}
    return {"meta": meta, "panels": done}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--eval", type=Path, default=ROOT / "eval")
    ap.add_argument("--out", type=Path, default=ROOT / "eval/open-raters")
    ap.add_argument("--families", help="comma-separated; default: every family with label files")
    args = ap.parse_args(argv)
    got = build(args.eval, args.families.split(",") if args.families else None)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, res in got["panels"].items():
        (args.out / name).mkdir(exist_ok=True)
        for rnd, text in res["texts"].items():
            (args.out / name / f"round{rnd}.md").write_text(text)
    text = render_report(got["meta"])
    (args.out / "report.md").write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
