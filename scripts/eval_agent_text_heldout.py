"""Stage 2, part 2, the held-out test (docs/prereg/agent-text-search.md): R* against today's text.

    python scripts/eval_agent_text_heldout.py draw     # 100 new paragraphs, readcost at main

The job is `scripts/agent_text_heldout_job.py`. Prompts, fact check, pairwise judgement and
scores are the factorial's (`eval_agent_text`), which are the edit test's.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_agent_text as at
import eval_edit_arms as ea
import eval_edit_localize as el

ROOT = ea.ROOT
SEED = "20261120:agent-text-heldout"
PLAN_COMMIT = "0ba6d34"
WALKED_BEFORE = el.OLD_WALKED + 1977     # the edit test's 784 and the localization control's 1,977
N = 100
POINTERS = ROOT / "eval" / "agent-text-heldout"
R_STAR = ROOT / "eval" / "agent-text-search" / "r_star.json"
EDITORS = ["openai/gpt-oss-120b", "mistralai/Mistral-Small-4-119B-2603", "allenai/Olmo-3.1-32B-Instruct"]
JUDGES = ["nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16", "microsoft/phi-4"]
FALLBACK = "ibm-granite/granite-3.3-8b-instruct"
NEW_MODELS = {
    "nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16": {
        "family": "NVIDIA", "licence": "OpenMDW-1.1",
        "extra": {"chat_template_kwargs": {"enable_thinking": False}},
        "engine": {"mamba_ssm_cache_dtype": "float16"}},
    "microsoft/phi-4": {"family": "Microsoft", "licence": "MIT", "extra": {}, "engine": {}},
    FALLBACK: {"family": "IBM", "licence": "Apache-2.0", "extra": {}, "engine": {}},
}
ARMS = ("RS", "R0", "C")
PAIRS = (("RS", "R0"), ("RS", "C"), ("R0", "C"))
CALL_CAP = 80_000
HOURS = 1.25
MAX_FAILED = 0.10        # share of a judge's first 200 replies that may fail to parse before the fallback
FIRST = 200


# ---- the draw ----------------------------------------------------------------

def draw(out: Path = POINTERS) -> None:
    from readcost import Analyzer, Config
    if at.verify() != 0:
        raise SystemExit(1)
    rows = [json.loads(x) for x in (el.OLD_POINTERS / "candidates.jsonl").read_text().splitlines()]
    order = el.first_order(rows)
    walked = ([json.loads(x)["repo"] for x in (el.OLD_POINTERS / "walk.jsonl").read_text().splitlines()]
              + [json.loads(x)["repo"] for x in (el.POINTERS / "walk.jsonl").read_text().splitlines()])
    if order[:WALKED_BEFORE] != walked:
        raise SystemExit("the rebuilt order does not match the two earlier walks; not drawn")
    seen = {json.loads(x)["sha256"] for ptr in at.POINTER_FILES
            for x in (ptr / "paragraphs.jsonl").read_text().splitlines()}
    newer = el.tree_text(PLAN_COMMIT, skip=("eval/edit-arms/", "eval/edit-localize/"))
    picked, log = el.walk_on(order, ea.github_files, Analyzer(Config()), seen, newer, n=N, start=WALKED_BEFORE)
    out.mkdir(parents=True, exist_ok=True)
    (out / "paragraphs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in picked))
    (out / "walk.jsonl").write_text("".join(json.dumps(x) + "\n" for x in log))
    print(json.dumps({"walked before": WALKED_BEFORE, "walked": len(log),
                      "outcomes": dict(Counter(x["outcome"] for x in log)), "drawn": len(picked)}, indent=1))


# ---- the arms ------------------------------------------------------------------

def load_r_star(path: Path = R_STAR) -> dict:
    return json.loads(path.read_text())


def prompts_for(analyzer, p: dict, rs: dict) -> dict:
    """{arm: edit prompt}: R0 is `readcost check -o agent` (HsFPX); RS is R*; C has no checker block."""
    result = ea.check(analyzer, p["text"])
    r0 = at.feedback(result, at.LEVELS[at.R0])
    rs_text = at.text_of(result, rs["fixes"], rs["scope"], precision=rs["precision"])
    return {"R0": at.prompt(p["text"], r0), "RS": at.prompt(p["text"], rs_text), "C": at.anchor_prompt(p["text"])}


def plan(analyzer, ref: Path, rs: dict) -> dict:
    paras = at.texts(ref)
    return {"paras": paras, "texts": {p["id"]: p["text"] for p in paras},
            "prompts": {p["id"]: prompts_for(analyzer, p, rs) for p in paras}}


def run(ref: Path, client, analyzer, rs: dict, editors=EDITORS, judges=JUDGES, workers: int = 8,
        call_editors=None, call_judges=None, phases=None) -> dict:
    pl = plan(analyzer, ref, rs)
    ask_e = editors if call_editors is None else call_editors
    ask_j = judges if call_judges is None else call_judges
    tx, pr = pl["texts"], pl["prompts"]
    status = {}

    def edit(ed, pid, arm):
        return at.edit_text(client, ed, pr[pid][arm])

    def edits():
        jobs = [(ed, pid, arm) for pid in pr for ed in ask_e for arm in ARMS]
        random.Random(f"{SEED}:calls:edits").shuffle(jobs)

        def one(job):
            ed, pid, arm = job
            client(ed, ea.SYSTEM, pr[pid][arm], ea.TEXT_SCHEMA)
        ok = ea._pool(jobs, one, workers)
        return ok and ea._pool([j for j in jobs if edit(*j) is None], one, workers)

    def facts():
        jobs = [(ed, pid, arm, j) for pid in pr for ed in editors for arm in ARMS for j in ask_j]
        random.Random(f"{SEED}:calls:facts").shuffle(jobs)

        def one(job):
            ed, pid, arm, j = job
            e = edit(ed, pid, arm)
            if e is not None:
                client(j, None, ea.fact_prompt(tx[pid], e), ea.fact_schema())
        ok = ea._pool(jobs, one, workers)
        again = [jb for jb in jobs if (e := edit(*jb[:3])) is not None
                 and at.facts_of(client, jb[3], tx[jb[1]], e) is None]
        return ok and ea._pool(again, one, workers)

    def read():
        jobs = [(ed, pid, x, y, j, o) for pid in pr for ed in editors for x, y in PAIRS for j in ask_j
                for o in (0, 1)]
        random.Random(f"{SEED}:calls:read").shuffle(jobs)

        def pair(job):
            ed, pid, x, y, _j, o = job
            a, b = edit(ed, pid, x), edit(ed, pid, y)
            if a is None or b is None:
                return None
            return (a, b) if o == 0 else (b, a)

        def one(job):
            got = pair(job)
            if got:
                client(job[4], None, ea.pair_prompt(*got), ea.PAIRWISE_SCHEMA)
        ok = ea._pool(jobs, one, workers)
        again = [jb for jb in jobs if (got := pair(jb)) and at.pick(client, jb[4], *got) is None]
        return ok and ea._pool(again, one, workers)

    for name, phase in (("edits", edits), ("facts", facts), ("read", read)):
        if phases is not None and name not in phases:
            continue
        status[name] = bool(phase())
        print(name, "done" if status[name] else "stopped", f"{client.calls} calls", flush=True)
        if not status[name]:
            break
    return status


# ---- analysis ------------------------------------------------------------------

def analyse(ref: Path, client, analyzer, rs: dict, editors=EDITORS, judges=JUDGES) -> dict:
    pl = plan(analyzer, ref, rs)
    tx, pr = pl["texts"], pl["prompts"]
    edits = {(pid, ed, arm): at.edit_text(client, ed, pr[pid][arm]) for pid in pr for ed in editors for arm in ARMS}
    change = {arm: {} for arm in ARMS}
    for (pid, ed, arm), e in edits.items():
        got = [c for c in (at.facts_of(client, j, tx[pid], e) for j in judges) if c] if e else []
        if got:
            change[arm][(pid, ed)] = float(any(c["lost"] or c["changed"] for c in got))
    pairs = {}
    for x, y in PAIRS:
        oc = {}
        for pid in pr:
            for ed in editors:
                a, b = edits[(pid, ed, x)], edits[(pid, ed, y)]
                for j in judges:
                    if a is None or b is None:
                        oc[(pid, ed, j)] = None
                        continue
                    p0, p1 = at.pick(client, j, a, b), at.pick(client, j, b, a)
                    first = {"1": x, "2": y, "tie": "tie"}.get(p0) if p0 else None
                    second = {"1": y, "2": x, "tie": "tie"}.get(p1) if p1 else None
                    oc[(pid, ed, j)] = ea.outcome(first, second, x, y)
        est = ea.cluster_boot(ea.unit_scores(oc))
        per = {who: ea.cluster_boot(ea.unit_scores({k: v for k, v in oc.items() if who in (k[1], k[2])}))
               for who in editors + judges}
        pairs[x + y] = {"estimate": est, "counts": dict(Counter(o for o in oc.values() if o)),
                        "missing": sum(o is None for o in oc.values()), "per": per}

    def paired(a, b, keep=lambda k: True):
        both = {k: a[k] - b[k] for k in a if k in b and keep(k)}
        return ea.cluster_boot(both) if both else None
    res = {"paragraphs": len(pr), "judges": list(judges), "pairs": pairs,
           "share": {arm: ea.cluster_boot(change[arm]) if change[arm] else None for arm in ARMS},
           "RS_minus_R0": paired(change["RS"], change["R0"]),
           "R0_minus_C": paired(change["R0"], change["C"]), "RS_minus_C": paired(change["RS"], change["C"]),
           "RS_minus_R0_per": {ed: paired(change["RS"], change["R0"], lambda k, ed=ed: k[1] == ed)
                               for ed in editors},
           "missing_edits": sum(e is None for e in edits.values())}
    res["decision"] = decide(pairs["RSR0"]["estimate"], res["RS_minus_R0"])
    res["length"] = {arm: round(statistics.median(len(e.split()) / len(tx[pid].split())
                                                  for (pid, _ed, a), e in edits.items() if a == arm and e), 3)
                     for arm in ARMS}
    return res


def decide(win, diff) -> dict:
    """The plan's rule: R* replaces today's text when both parts hold."""
    if win is None or diff is None:
        return {"reads": False, "content": False, "replace": False}
    reads = win[1] > 0.5 or (win[0] >= 0.47 and diff[2] < 0)
    content = diff[2] < 0.03
    return {"reads": reads, "content": content, "replace": reads and content}


def fmt(est, pct: bool = False) -> str:
    if est is None:
        return "—"
    if pct:
        return "{:+.1f} [{:+.1f}, {:+.1f}]".format(*(100 * x for x in est))
    return "{:.3f} [{:.3f}, {:.3f}]".format(*est)


def render(res: dict, status: dict, calls: dict, rs: dict, draw_line: str = "") -> str:
    yn = {True: "yes", False: "no"}
    names = {"RSR0": "R* against R0", "RSC": "R* against C", "R0C": "R0 against C"}
    out = ["## Agent feedback text, stage 2: the held-out test", ""]
    if draw_line:
        out += [draw_line, ""]
    out += [f"Paragraphs {res['paragraphs']}. Judges: {', '.join(res['judges'])}. Calls {calls.get('calls')} in the "
            f"cache (new this run {calls.get('new')}). Missing edits {res['missing_edits']}. Phases: "
            + ", ".join(f"{k} {'done' if v else 'stopped'}" for k, v in status.items()), "",
            "| Pair | Win rate of the first [95%] | Counts | Missing |", "| --- | --- | --- | --- |"]
    for k, r in res["pairs"].items():
        out.append(f"| {names[k]} | {fmt(r['estimate'])} | "
                   + ", ".join(f"{a} {b}" for a, b in sorted(r["counts"].items())) + f" | {r['missing']} |")
    out += ["", "| Share of edits changing content | Estimate [95%] |", "| --- | --- |"]
    out += [f"| {a} | {fmt(res['share'][a])} |" for a in ARMS]
    out += [f"| R* minus R0 (points) | {fmt(res['RS_minus_R0'], True)} |",
            f"| R0 minus C (points) | {fmt(res['R0_minus_C'], True)} |",
            f"| R* minus C (points) | {fmt(res['RS_minus_C'], True)} |", ""]
    d = res["decision"]
    out += ["| Part of the decision | Holds |", "| --- | --- |", f"| R* reads at least as well | {yn[d['reads']]} |",
            f"| R* does not change content more | {yn[d['content']]} |", f"| **R* replaces today's text** | **{yn[d['replace']]}** |", "", "Per editor and judge (decide nothing):", "",
            "| Who | R* against R0 | R* against C | R0 against C | R* minus R0, content (points) |",
            "| --- | --- | --- | --- | --- |"]
    for who in list(res["RS_minus_R0_per"]) + res["judges"]:
        out.append(f"| {who} | " + " | ".join(fmt(res["pairs"][k]["per"].get(who)) for k in ("RSR0", "RSC", "R0C"))
                   + f" | {fmt(res['RS_minus_R0_per'].get(who), True) if who in res['RS_minus_R0_per'] else ''} |")
    out += ["", "Median words over the original: " + ", ".join(f"{a} {v}" for a, v in res["length"].items()) + ".",
            "", "R*: scope line " + (repr(rs["scope"].strip()) if rs["scope"] else "none") + "; fixes:"]
    out += [f"- {r}: {fx}" for r, fx in rs["fixes"].items()]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("draw")
    a = ap.parse_args(argv)
    if a.cmd == "draw":
        draw()
    return 0


if __name__ == "__main__":
    sys.exit(main())
