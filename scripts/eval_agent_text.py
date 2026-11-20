"""Which parts of readcost's agent feedback matter: docs/prereg/agent-text-factorial.md.

Sixteen variants of the text `readcost check -o agent` prints, a half fraction
of five two-level factors. Each variant goes into the edit test's arm B
message; edits are judged for facts and for readability against the edit
test's arm C. Decoy findings measure deference. The job is
`scripts/agent_text_job.py`; prompts, client and judge prompts come from
`eval_edit_arms`.
"""

from __future__ import annotations

import itertools
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_edit_arms as ea
import eval_edit_localize as el

ROOT = ea.ROOT
SEED = "20261120:agent-text"
DIGEST = "f84d01e995f1d407b08f54c46942661c504a5b5d775825fd5df300f73d3bd6e7"   # src/ and uv.lock of e1871db
EDITORS = ["openai/gpt-oss-120b", "mistralai/Mistral-Small-4-119B-2603"]
JUDGES = ["Qwen/Qwen3.8-27B", "google/gemma-4-31B-it"]
N_MAIN, N_DECOY = 100, 40
CALL_CAP = 44_000
HOURS = 2.0
SMALLEST = 0.03
MIN_PER_LEVEL = 6
FACTORS = ("H", "S", "F", "P", "X")
HEAD_ORDER = ("readcost: {n} hard-to-read construction{s} in {words} words. "
              "Rewrite these sentences where the finding holds; keep the meaning and the facts.")
HEAD_INFORM = "readcost: {n} hard-to-read construction{s} in {words} words."
SCOPE = " Leave the other sentences as they are."
GENERIC_FIX = "Rewrite the sentence so it is easier to read."
POINTER_FILES = (ROOT / "eval" / "edit-arms", ROOT / "eval" / "edit-localize")


def verify(root: Path = ROOT) -> int:
    """0 if src/ and uv.lock are e1871db's (0.4.0), by digest."""
    if ea.tree_digest(root) != DIGEST:
        print("src/ or uv.lock differs from e1871db; the pre-registration needs an amendment", file=sys.stderr)
        return 1
    print("src/ and uv.lock match e1871db")
    return 0


def design() -> list[dict]:
    """The 16 arms: every level of H, S, F and P, with X = -H*S*F*P. R0, today's text, is HsFPX."""
    arms = []
    for h, s, f, p in itertools.product((1, -1), repeat=4):
        arms.append({"H": h, "S": s, "F": f, "P": p, "X": -h * s * f * p})
    for a in arms:
        a["name"] = "".join(k if a[k] > 0 else k.lower() for k in FACTORS)
    return arms


ARMS = design()
R0 = "HsFPX"   # today's text: every "+" level but the scope line, which readcost does not print
DECOY_ARMS = [a for a in ARMS if a["X"] < 0]


# ---- the text ---------------------------------------------------------------

def _line(loc: str, rule: str, detail: str, note: str, fix: str) -> str:
    return f"- {loc} [{rule}] {detail}{note}. Fix: {fix}"


def _note(rule: str) -> str:
    from readcost.report import _precision
    prec = _precision(rule)
    return f" (raters accepted {prec['accepted']} of {prec['labelled']} such findings)" if prec else ""


def feedback(result, arm: dict, decoy: dict | None = None, max_items: int = 8, max_chars: int = 2500) -> str:
    """The arm's text for one Result; ``decoy`` adds one finding line (rule, line, sentence, slot)."""
    from readcost.features import FEATURES, suggestion
    from readcost.report import _worst_first
    items = _worst_first([result])
    lines = []
    for f in items[:max_items]:
        loc = f"line {f.line}" if f.line else (f.label or f.path)
        detail = f.message if arm["X"] > 0 else FEATURES[f.feature].title
        lines.append(_line(loc, f.feature, detail, _note(f.feature) if arm["P"] > 0 else "",
                           f.suggestion if arm["F"] > 0 else GENERIC_FIX))
    total = len(items)
    if decoy is not None:
        rule = decoy["rule"]
        fix = suggestion(rule, decoy["sentence"]) if arm["F"] > 0 else GENERIC_FIX
        lines.insert(min(decoy["slot"], len(lines)),
                     _line(f"line {decoy['line']}", rule, FEATURES[rule].title,
                           _note(rule) if arm["P"] > 0 else "", fix))
        total += 1
    if not total:
        return ""
    head = (HEAD_ORDER if arm["H"] > 0 else HEAD_INFORM).format(n=total, s="s" if total != 1 else "",
                                                                 words=result.words)
    if arm["S"] > 0:
        head += SCOPE
    shown = max_items + (decoy is not None)
    body = [head] + lines[:shown]
    if total > shown:
        body.append(f"- ...and {total - shown} more (run `readcost check` for the full list)")
    text = "\n".join(body)
    if len(text) > max_chars:
        text = text[: max_chars - 3] + "..."
    return text


def prompt(text: str, fb: str) -> str:
    return ea.ARM_B.format(budget=ea.budget(text), feedback=fb, text=text)


def anchor_prompt(text: str) -> str:
    return ea.edit_prompt("C", text)


# ---- paragraphs and decoys ---------------------------------------------------

def choose(analyzer, paras: list[dict]) -> tuple[list[dict], list[dict]]:
    """The main set and the decoy set, by the plan's order and rules."""
    by = {p["id"]: p for p in paras}
    order = sorted(by)
    random.Random(SEED).shuffle(order)
    main, decoys = [], []
    for pid in order:
        p = by[pid]
        result = ea.check(analyzer, p["text"])
        if not result.findings:
            continue
        if len(main) < N_MAIN:
            main.append(p)
            continue
        if len(decoys) >= N_DECOY:
            break
        free = unflagged(analyzer, p["text"], result)
        if len(free) >= 2:
            decoys.append(p)
    return main, decoys


def unflagged(analyzer, text: str, result) -> list[dict]:
    """Checked sentences that hold no finding and whose text appears once in the paragraph, in text order.

    A sentence repeated word for word could not be told apart in the edit.
    """
    held = {(f.sentence_start, f.sentence_end) for f in result.findings}
    sents = el.sentences(analyzer, text)
    return [s for s in sents if s["span"] and tuple(s["span"]) not in held
            and el.norm(text).count(el.norm(s["text"])) == 1]


def decoy_for(analyzer, p: dict) -> dict:
    from readcost.features import FEATURES
    result = ea.check(analyzer, p["text"])
    free = unflagged(analyzer, p["text"], result)
    rng = random.Random(f"{SEED}:decoy:{p['id']}")
    d, c = rng.sample(free, 2)
    rules = sorted(k for k, f in FEATURES.items() if f.default)
    rule = rng.choice(rules)
    slot = rng.randrange(min(len(result.findings), 8) + 1)
    return {"rule": rule, "line": d["line"], "sentence": d["text"], "control": c["text"], "slot": slot}


def rewrote(sentence: str, edit: str) -> bool:
    return el.norm(sentence) not in el.norm(edit)


# ---- the run -------------------------------------------------------------------

def texts(ref: Path) -> list[dict]:
    return [json.loads(x) for x in (ref / "texts.jsonl").read_text().splitlines()]


def plan(analyzer, ref: Path) -> dict:
    """Every edit prompt of the test, by (set, pid, arm name), and what the analysis needs."""
    main, decoys = choose(analyzer, texts(ref))
    prompts, info = {}, {"main": [p["id"] for p in main], "decoy": [p["id"] for p in decoys], "decoys": {}}
    for p in main:
        result = ea.check(analyzer, p["text"])
        for a in ARMS:
            prompts[("main", p["id"], a["name"])] = prompt(p["text"], feedback(result, a))
    for p in decoys:
        result = ea.check(analyzer, p["text"])
        d = decoy_for(analyzer, p)
        info["decoys"][p["id"]] = d
        for a in DECOY_ARMS:
            prompts[("decoy", p["id"], a["name"])] = prompt(p["text"], feedback(result, a, d))
    info["texts"] = {p["id"]: p["text"] for p in main + decoys}
    return {"prompts": prompts, **info}


def edit_text(client, model: str, prompt_text: str) -> str | None:
    data = client.get(model, ea.SYSTEM, prompt_text)
    t = (data or {}).get("text")
    return t.strip() if isinstance(t, str) and t.strip() else None


def anchor(client, ed: str, text: str) -> str | None:
    return edit_text(client, ed, anchor_prompt(text))


def facts_of(client, judge: str, original: str, edit: str | None) -> dict | None:
    if edit is None:
        return None
    data = client.get(judge, None, ea.fact_prompt(original, edit))
    if not data or not all(isinstance(data.get(k), list) for k in ("lost", "added", "changed")):
        return None
    return data


def pick(client, judge: str, first: str, second: str) -> str | None:
    """'1', '2' or 'tie'."""
    return ea.parse_easier(client.get(judge, None, ea.pair_prompt(first, second)))


def run(ref: Path, client, analyzer, editors=EDITORS, judges=JUDGES, workers: int = 8, call_editors=None,
        call_judges=None, phases=None) -> dict:
    """edits (main and decoy sets), facts, read. Returns which phases finished."""
    pl = plan(analyzer, ref)
    ask_e = editors if call_editors is None else call_editors
    ask_j = judges if call_judges is None else call_judges
    tx = pl["texts"]
    status = {}

    def edits():
        jobs = [(ed, k) for k in pl["prompts"] for ed in ask_e]
        random.Random(f"{SEED}:calls:edits").shuffle(jobs)

        def one(job):
            ed, k = job
            client(ed, ea.SYSTEM, pl["prompts"][k], ea.TEXT_SCHEMA)
        ok = ea._pool(jobs, one, workers)
        return ok and ea._pool([j for j in jobs if edit_text(client, j[0], pl["prompts"][j[1]]) is None], one, workers)

    main_keys = [k for k in pl["prompts"] if k[0] == "main"]

    def facts():
        jobs = [(ed, k, j) for k in main_keys for ed in editors for j in ask_j]
        random.Random(f"{SEED}:calls:facts").shuffle(jobs)

        def one(job):
            ed, k, j = job
            e = edit_text(client, ed, pl["prompts"][k])
            if e is not None:
                client(j, None, ea.fact_prompt(tx[k[1]], e), ea.fact_schema())
        ok = ea._pool(jobs, one, workers)
        again = [jb for jb in jobs if (e := edit_text(client, jb[0], pl["prompts"][jb[1]])) is not None
                 and facts_of(client, jb[2], tx[jb[1][1]], e) is None]
        return ok and ea._pool(again, one, workers)

    def read():
        jobs = [(ed, k, j, o) for k in main_keys for ed in editors for j in ask_j for o in (0, 1)]
        random.Random(f"{SEED}:calls:read").shuffle(jobs)

        def pair(job):
            ed, k, _j, o = job
            e, c = edit_text(client, ed, pl["prompts"][k]), anchor(client, ed, tx[k[1]])
            if e is None or c is None:
                return None
            return (e, c) if o == 0 else (c, e)

        def one(job):
            got = pair(job)
            if got:
                client(job[2], None, ea.pair_prompt(*got), ea.PAIRWISE_SCHEMA)
        ok = ea._pool(jobs, one, workers)
        again = [jb for jb in jobs if (got := pair(jb)) and pick(client, jb[2], *got) is None]
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

def collect(ref: Path, client, analyzer, editors=EDITORS, judges=JUDGES) -> dict:
    pl = plan(analyzer, ref)
    tx = pl["texts"]
    change, read, edits = {}, {}, {}
    for (kind, pid, arm), pr in pl["prompts"].items():
        for ed in editors:
            e = edit_text(client, ed, pr)
            edits[(kind, pid, arm, ed)] = e
            if kind != "main" or e is None:
                continue
            checks = [facts_of(client, j, tx[pid], e) for j in judges]
            got = [c for c in checks if c]
            if got:
                change[(pid, ed, arm)] = float(any(c["lost"] or c["changed"] for c in got))
            c = anchor(client, ed, tx[pid])
            scores = []
            for j in judges:
                if c is None:
                    break
                p0, p1 = pick(client, j, e, c), pick(client, j, c, e)
                first = {"1": "X", "2": "C", "tie": "tie"}.get(p0) if p0 else None
                second = {"1": "C", "2": "X", "tie": "tie"}.get(p1) if p1 else None
                o = ea.outcome(first, second, "X", "C")
                if o is not None:
                    scores.append(ea.SCORE[o])
            if scores:
                read[(pid, ed, arm)] = sum(scores) / len(scores)
    return {"plan": pl, "change": change, "read": read, "edits": edits}


def effect(values: dict, sign, editors=EDITORS, need: int = MIN_PER_LEVEL):
    """Mean over units of (mean over arms with sign +1) minus (mean over arms with sign -1), bootstrapped."""
    by: dict = {}
    for (pid, ed, arm), v in values.items():
        by.setdefault((pid, ed), {})[arm] = v
    diffs = {}
    for unit, arms in by.items():
        plus = [v for a, v in arms.items() if sign(a) > 0]
        minus = [v for a, v in arms.items() if sign(a) < 0]
        if len(plus) >= need and len(minus) >= need:
            diffs[unit] = statistics.mean(plus) - statistics.mean(minus)
    return ea.cluster_boot(diffs) if diffs else None


LEVELS = {a["name"]: a for a in ARMS}


def matters(est) -> bool:
    return est is not None and (est[1] > 0 or est[2] < 0) and abs(est[0]) >= SMALLEST


def analyse(data: dict, editors=EDITORS, judges=JUDGES) -> dict:
    change, read = data["change"], data["read"]
    util = {k: read[k] - change[k] for k in read if k in change}
    out: dict = {"main_set": len(data["plan"]["main"]), "decoy_set": len(data["plan"]["decoy"])}
    eff = {}
    for name, vals in (("change", change), ("read", read), ("utility", util)):
        eff[name] = {f: effect(vals, lambda a, f=f: LEVELS[a][f]) for f in FACTORS}
        eff[name + "_x"] = {f"{f}{g}": effect(vals, lambda a, f=f, g=g: LEVELS[a][f] * LEVELS[a][g])
                            for f, g in itertools.combinations(FACTORS, 2)}
    out["effects"] = eff
    out["matters"] = {o: {f: matters(eff[o][f]) for f in FACTORS} for o in ("change", "read")}
    seed = {}
    for f in FACTORS:
        e = eff["utility"][f]
        seed[f] = (1 if e[0] > 0 else -1) if (e and (e[1] > 0 or e[2] < 0)) else LEVELS[R0][f]
    out["seed"] = "".join(f if seed[f] > 0 else f.lower() for f in FACTORS)
    biggest_main = max((abs(e[0]) for e in eff["utility"].values() if e), default=0)
    out["whole_text"] = any(e and abs(e[0]) > biggest_main and (e[1] > 0 or e[2] < 0)
                            for e in eff["utility_x"].values())
    out["stage_2"] = any(out["matters"]["change"].values()) or any(out["matters"]["read"].values())
    out["arms"] = {}
    for a in ARMS:
        n = a["name"]
        row = {}
        for k, vals in (("change", change), ("read", read), ("utility", util)):
            got = [v for (_pid, _ed, arm), v in vals.items() if arm == n]
            row[k] = round(statistics.mean(got), 3) if got else None
        out["arms"][n] = row
    # Deference: decoy rewritten minus control rewritten, per decoy edit.
    pl, edits = data["plan"], data["edits"]
    dif = {}
    for (kind, pid, arm, ed), e in edits.items():
        if kind == "decoy" and e is not None:
            d = pl["decoys"][pid]
            dif[(pid, ed, arm)] = float(rewrote(d["sentence"], e)) - float(rewrote(d["control"], e))
    out["deference"] = {"index": ea.cluster_boot(dif) if dif else None,
                        "decoy_rewritten": round(statistics.mean(
                            float(rewrote(pl["decoys"][k[1]]["sentence"], e)) for k, e in edits.items()
                            if k[0] == "decoy" and e), 3) if dif else None,
                        **{f: effect(dif, lambda a, f=f: LEVELS[a][f], need=3) for f in ("H", "S", "F", "P")}}
    out["per_editor"] = {ed: {o: {f: effect({k: v for k, v in vals.items() if k[1] == ed},
                                            lambda a, f=f: LEVELS[a][f]) for f in FACTORS}
                              for o, vals in (("change", change), ("read", read))} for ed in editors}
    # Length and findings after the edit, per arm (main set).
    length = {}
    for a in ARMS:
        rows = [(data["plan"]["texts"][pid], e) for (kind, pid, arm, ed), e in edits.items()
                if kind == "main" and arm == a["name"] and e]
        if rows:
            length[a["name"]] = round(statistics.median(len(e.split()) / len(t.split()) for t, e in rows), 3)
    out["length"] = length
    out["missing_edits"] = sum(e is None for e in edits.values())
    out["units"] = {"change": len({k[:2] for k in change}), "read": len({k[:2] for k in read})}
    return out


def fmt(est, scale: float = 1.0) -> str:
    if est is None:
        return "—"
    return "{:+.3f} [{:+.3f}, {:+.3f}]".format(*(scale * x for x in est))


NAMES = {"H": "head orders (+) or informs (−)", "S": "scope line", "F": "rule's fix (+) or generic (−)",
         "P": "precision note", "X": "finding's message (+) or rule's title (−)"}


def render(res: dict, status: dict, calls: dict) -> str:
    yn = {True: "yes", False: "no"}
    e = res["effects"]
    out = ["## Agent feedback text: a fractional factorial over five parts", "",
           f"Main set {res['main_set']} paragraphs, decoy set {res['decoy_set']}. Units with change {res['units']['change']}, "
           f"with read {res['units']['read']}. Missing edits {res['missing_edits']}. Calls {calls.get('calls')} in the cache "
           f"(new this run {calls.get('new')}). Phases: " + ", ".join(f"{k} {'done' if v else 'stopped'}"
                                                                   for k, v in status.items()), "",
           "| Factor | Change (share) [95%] | Matters | Read (vs C) [95%] | Matters | Utility [95%] |",
           "| --- | --- | --- | --- | --- | --- |"]
    for f in FACTORS:
        out.append(f"| {f}: {NAMES[f]} | {fmt(e['change'][f])} | {yn[res['matters']['change'][f]]} | "
                   f"{fmt(e['read'][f])} | {yn[res['matters']['read'][f]]} | {fmt(e['utility'][f])} |")
    out += ["", (f"Seed for stage 2: **{res['seed']}** (R0 is {R0}). Whole-text search: {yn[res['whole_text']]}. "
                 f"Stage 2 runs: {yn[res['stage_2']]}."), "",
            "| Interaction | Change | Read | Utility |", "| --- | --- | --- | --- |"]
    for k in e["change_x"]:
        out.append(f"| {k} | {fmt(e['change_x'][k])} | {fmt(e['read_x'][k])} | {fmt(e['utility_x'][k])} |")
    d = res["deference"]
    out += ["", (f"Deference index (decoy rewritten minus control rewritten): {fmt(d['index'])}; decoys rewritten "
                 f"{d['decoy_rewritten']}."), "", "| Factor | Effect on deference |", "| --- | --- |"]
    out += [f"| {f} | {fmt(d[f])} |" for f in ("H", "S", "F", "P")]
    out += ["", "| Arm | Change | Read | Utility | Length |", "| --- | --- | --- | --- | --- |"]
    for n, r in res["arms"].items():
        out.append(f"| {n}{' (R0)' if n == R0 else ''} | {r['change']} | {r['read']} | {r['utility']} | "
                   f"{res['length'].get(n)} |")
    out += ["", "Per editor, main effects (decide nothing):", "", "| Editor | Outcome | " + " | ".join(FACTORS) + " |",
            "| --- | --- | " + " | ".join("---" for _ in FACTORS) + " |"]
    for ed, r in res["per_editor"].items():
        for o in ("change", "read"):
            out.append(f"| {ed} | {o} | " + " | ".join(fmt(r[o][f]) for f in FACTORS) + " |")
    return "\n".join(out) + "\n"



# ---- stage 2, part 1: the search (docs/prereg/agent-text-search.md) ------------

SEARCH_SEED = "20261120:agent-text-search"
SEARCH_CALL_CAP = 70_000
SEARCH_HOURS = 1.75
SEED_ARM = "HsFpX"
MARGIN = 0.02
FIX_CANDIDATES = {
    "stacked-nouns": [
        ("Unpack the run of nouns with a preposition or a verb: 'the cache eviction policy threshold' becomes "
        "'the threshold at which the cache evicts'. Leave an established term as it is."),
        ("Keep at most two nouns together; say how the others relate with 'of', 'for' or a verb. Leave an "
        "established term as it is."),
        "Keep at most two nouns together."],
    "long-dependency": [
        ("Put the subject next to its verb: move the long phrase between them to the end of the sentence, or "
        "into a sentence of its own."),
        ("Bring the two words together. Move what separates them after the verb, or split the sentence, and keep "
        "every fact in one of the two."),
        "Put the subject next to its verb."],
    "reduced-object-relative": [
        "Add the 'that' back: 'the file the tool writes' becomes 'the file that the tool writes'.",
        "Keep the 'that'. If the clause is long, make it a sentence of its own.",
        "Add 'that' at the start of the clause."],
    "hyphen-compound": [
        "Write the relationship out: 'a user-config-driven step' becomes 'a step driven by the user's config'.",
        "Say how the hyphenated words relate, with a preposition or a verb; keep an established hyphenated term.",
        "Replace the hyphenated chain with a phrase that says how its words relate."],
    "inline-list": [
        "Use a bulleted list, one item per line, after a sentence that says what the items are.",
        ("If there are more than three items or they are long, use a bulleted list; otherwise keep them in the "
        "sentence."),
        "Use a bulleted list, and keep every item."],
}
SCOPE_CANDIDATES = ["", " Leave the other sentences as they are.", " Change other sentences only where they need it.",
                    " Keep the other sentences unless a change helps the reader."]


def base_fixes() -> dict:
    from readcost.features import FEATURES
    return {r: FEATURES[r].fix for r in FIX_CANDIDATES}


def fix_for(rule: str, sentence: str, base: str) -> str:
    """readcost's `suggestion` with another base fix: the same reminder to keep a reason."""
    from readcost.features import RATIONALE
    m = RATIONALE.search(sentence) if rule in ("long-dependency", "inline-list") else None
    if not m:
        return base
    return (f"{base} Split the sentence and keep the reason: the '{m.group(1).lower()}' "
            "clause can be a sentence of its own.")


def text_of(result, fixes: dict, scope: str, precision: bool = False, max_items: int = 8,
            max_chars: int = 2500) -> str:
    """The seed's form (head orders, the finding's message), with these fixes, scope line and note."""
    from readcost.report import _worst_first
    items = _worst_first([result])
    if not items:
        return ""
    total = len(items)
    head = HEAD_ORDER.format(n=total, s="s" if total != 1 else "", words=result.words) + scope
    lines = [head]
    for f in items[:max_items]:
        loc = f"line {f.line}" if f.line else (f.label or f.path)
        base = fixes.get(f.feature)
        fix = fix_for(f.feature, f.sentence, base) if base is not None else f.suggestion
        lines.append(_line(loc, f.feature, f.message, _note(f.feature) if precision else "", fix))
    if total > max_items:
        lines.append(f"- ...and {total - max_items} more (run `readcost check` for the full list)")
    body = "\n".join(lines)
    return body[: max_chars - 3] + "..." if len(body) > max_chars else body


def species() -> list[tuple[str, str]]:
    """(species, candidate) pairs; v0 of every species is the seed."""
    out = [("seed", "v0")]
    for r in FIX_CANDIDATES:
        out += [(r, f"v{i}") for i in range(1, 4)]
    out += [("scope", f"v{i}") for i in range(1, 4)]
    return out


def candidate_text(result, sp: str, cand: str) -> str:
    fixes = base_fixes()
    scope = ""
    if sp in FIX_CANDIDATES and cand != "v0":
        fixes[sp] = FIX_CANDIDATES[sp][int(cand[1]) - 1]
    if sp == "scope" and cand != "v0":
        scope = SCOPE_CANDIDATES[int(cand[1])]
    return text_of(result, fixes, scope)


def search_plan(analyzer, ref: Path) -> dict:
    """Every edit prompt of the search, keyed (pid, species, candidate), and each species' paragraphs."""
    from readcost.report import _worst_first
    paras = texts(ref)
    prompts, units = {}, {}
    for p in paras:
        result = ea.check(analyzer, p["text"])
        shown = {f.feature for f in _worst_first([result])[:8]}
        if not shown:
            continue
        for sp, cand in species():
            if sp in FIX_CANDIDATES and sp not in shown:
                continue
            prompts[(p["id"], sp, cand)] = prompt(p["text"], candidate_text(result, sp, cand))
            units.setdefault(sp, set()).add(p["id"])
    return {"prompts": prompts, "units": units, "texts": {p["id"]: p["text"] for p in paras}}


def run_search(ref: Path, client, analyzer, editors=EDITORS, judges=JUDGES, workers: int = 8,
               call_editors=None, call_judges=None, phases=None) -> dict:
    pl = search_plan(analyzer, ref)
    unique = sorted(set(pl["prompts"].values()))
    by_prompt = {}
    for (pid, _sp, _c), pr in pl["prompts"].items():
        by_prompt.setdefault(pr, pid)
    ask_e = editors if call_editors is None else call_editors
    ask_j = judges if call_judges is None else call_judges
    tx = pl["texts"]
    status = {}

    def edits():
        jobs = [(ed, pr) for pr in unique for ed in ask_e]
        random.Random(f"{SEARCH_SEED}:calls:edits").shuffle(jobs)

        def one(job):
            client(job[0], ea.SYSTEM, job[1], ea.TEXT_SCHEMA)
        ok = ea._pool(jobs, one, workers)
        return ok and ea._pool([j for j in jobs if edit_text(client, *j) is None], one, workers)

    def facts():
        jobs = [(ed, pr, j) for pr in unique for ed in editors for j in ask_j]
        random.Random(f"{SEARCH_SEED}:calls:facts").shuffle(jobs)

        def one(job):
            ed, pr, j = job
            e = edit_text(client, ed, pr)
            if e is not None:
                client(j, None, ea.fact_prompt(tx[by_prompt[pr]], e), ea.fact_schema())
        ok = ea._pool(jobs, one, workers)
        again = [jb for jb in jobs if (e := edit_text(client, jb[0], jb[1])) is not None
                 and facts_of(client, jb[2], tx[by_prompt[jb[1]]], e) is None]
        return ok and ea._pool(again, one, workers)

    def read():
        jobs = [(ed, pr, j, o) for pr in unique for ed in editors for j in ask_j for o in (0, 1)]
        random.Random(f"{SEARCH_SEED}:calls:read").shuffle(jobs)

        def pair(job):
            ed, pr, _j, o = job
            e, c = edit_text(client, ed, pr), anchor(client, ed, tx[by_prompt[pr]])
            if e is None or c is None:
                return None
            return (e, c) if o == 0 else (c, e)

        def one(job):
            got = pair(job)
            if got:
                client(job[2], None, ea.pair_prompt(*got), ea.PAIRWISE_SCHEMA)
        ok = ea._pool(jobs, one, workers)
        again = [jb for jb in jobs if (got := pair(jb)) and pick(client, jb[2], *got) is None]
        return ok and ea._pool(again, one, workers)

    for name, phase in (("edits", edits), ("facts", facts), ("read", read)):
        if phases is not None and name not in phases:
            continue
        status[name] = bool(phase())
        print(name, "done" if status[name] else "stopped", f"{client.calls} calls", flush=True)
        if not status[name]:
            break
    return status


def score(client, ed: str, pr: str, original: str, judges=JUDGES) -> tuple[float | None, float | None]:
    """(change, read) of one edit, as the factorial scores them."""
    e = edit_text(client, ed, pr)
    if e is None:
        return None, None
    got = [c for c in (facts_of(client, j, original, e) for j in judges) if c]
    change = float(any(c["lost"] or c["changed"] for c in got)) if got else None
    c = anchor(client, ed, original)
    scores = []
    for j in judges:
        if c is None:
            break
        p0, p1 = pick(client, j, e, c), pick(client, j, c, e)
        first = {"1": "X", "2": "C", "tie": "tie"}.get(p0) if p0 else None
        second = {"1": "C", "2": "X", "tie": "tie"}.get(p1) if p1 else None
        o = ea.outcome(first, second, "X", "C")
        if o is not None:
            scores.append(ea.SCORE[o])
    return change, (sum(scores) / len(scores) if scores else None)


def analyse_search(pl: dict, client, editors=EDITORS, judges=JUDGES) -> dict:
    tx = pl["texts"]
    cache: dict = {}
    res: dict = {"species": {}, "choice": {}}
    for sp in ["scope", *FIX_CANDIDATES]:
        pids = pl["units"].get(sp, set())
        rows = {}
        for cand in ("v0", "v1", "v2", "v3"):
            key_sp = "seed" if cand == "v0" else sp
            vals = {"change": {}, "read": {}, "utility": {}}
            for pid in pids:
                pr = pl["prompts"].get((pid, key_sp, cand))
                if pr is None:
                    continue
                for ed in editors:
                    if (ed, pr) not in cache:
                        cache[(ed, pr)] = score(client, ed, pr, tx[pid], judges)
                    ch, rd = cache[(ed, pr)]
                    if ch is not None:
                        vals["change"][(pid, ed)] = ch
                    if rd is not None:
                        vals["read"][(pid, ed)] = rd
                    if ch is not None and rd is not None:
                        vals["utility"][(pid, ed)] = rd - ch
            rows[cand] = {k: ea.cluster_boot(v) if v else None for k, v in vals.items()}
            rows[cand]["units"] = len(vals["utility"])
            rows[cand]["_u"] = vals["utility"]
        seed_u = rows["v0"]["_u"]
        best, best_gain = "v0", 0.0
        for cand in ("v1", "v2", "v3"):
            u = rows[cand]["_u"]
            both = [k for k in u if k in seed_u]
            if not both:
                continue
            gain = statistics.mean(u[k] for k in both) - statistics.mean(seed_u[k] for k in both)
            rows[cand]["gain_over_seed"] = round(gain, 4)
            if gain >= MARGIN and gain > best_gain:
                best, best_gain = cand, gain
        for r in rows.values():
            r.pop("_u")
        res["species"][sp] = rows
        res["choice"][sp] = best
    return res


def r_star(choice: dict) -> dict:
    """R*'s fixes and scope line from the search's choices."""
    fixes = base_fixes()
    for r in FIX_CANDIDATES:
        if choice.get(r, "v0") != "v0":
            fixes[r] = FIX_CANDIDATES[r][int(choice[r][1]) - 1]
    scope = SCOPE_CANDIDATES[int(choice.get("scope", "v0")[1])]
    return {"fixes": fixes, "scope": scope, "precision": False}


def render_search(res: dict, status: dict, calls: dict) -> str:
    out = ["## Agent feedback text, stage 2: the search", "",
           f"Calls {calls.get('calls')} in the cache (new this run {calls.get('new')}). Phases: "
           + ", ".join(f"{k} {'done' if v else 'stopped'}" for k, v in status.items()), "",
           "| Species | Candidate | Units | Change [95%] | Read vs C [95%] | Utility [95%] | Gain over seed | Chosen |",
           "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for sp, rows in res["species"].items():
        for cand, r in rows.items():
            out.append(f"| {sp} | {cand} | {r['units']} | {fmt(r['change'])} | {fmt(r['read'])} | "
                       f"{fmt(r['utility'])} | {r.get('gain_over_seed', '')} | "
                       f"{'yes' if res['choice'][sp] == cand else ''} |")
    rs = r_star(res["choice"])
    out += ["", "R* (the seed, HsFpX, with each species' choice):", "",
            f"- scope line: {rs['scope'].strip() or '(none)'}"]
    out += [f"- {r}: {rs['fixes'][r]}" for r in FIX_CANDIDATES]
    return "\n".join(out) + "\n"
