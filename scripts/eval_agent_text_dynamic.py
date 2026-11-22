"""Fix texts that use the finding's own words: docs/prereg/agent-text-dynamic.md.

Each candidate changes one default rule's fix (or drops the precision note) and is judged
against today's text (R0) on the same paragraph and editor: facts first, then the judges'
probabilities that one edit reads better, with successive halving over screen and
confirmation units and an audit set nothing is chosen on. The job is
`scripts/agent_text_dynamic_job.py`.
"""

from __future__ import annotations

import json
import math
import random
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_agent_text as at
import eval_edit_arms as ea

ROOT = ea.ROOT
SEED = "20261120:agent-text-dynamic"
EDITORS = list(at.EDITORS)
JUDGES = list(at.JUDGES)
AUDIT_N = 50
CALIB_N = 40
CALL_CAP = 80_000
HOURS = 1.5
MAX_QUOTE_WORDS = 8
RULES = ("stacked-nouns", "long-dependency", "reduced-object-relative", "hyphen-compound", "inline-list")
SPECIES = ("note", *RULES)
NOTE_OFF = {"H": 1, "S": -1, "F": 1, "P": -1, "X": 1}   # R0 without the precision note (HsFpX)

# c1 names the words and the operation; c2 says when to leave the sentence alone. The second
# string of each pair is the form without a quote, for a finding whose quote is missing or long.
CANDIDATES = {
    "stacked-nouns": {
        "c1": ("Unpack '{q}': say how its nouns relate, with a preposition or a verb.",
               "Unpack the run of nouns: say how they relate, with a preposition or a verb."),
        "c2": ("Leave '{q}' if readers know it as one term; otherwise say how its nouns relate.",
               "Leave the nouns together if readers know them as one term; otherwise say how they relate.")},
    "long-dependency": {
        "c1": (("Bring '{a}' and '{b}' together: move what comes between them to the end of the sentence, "
               "or into a sentence of its own."), None),
        "c2": (("Leave it if '{a}' and '{b}' are easy to connect; otherwise split the sentence so that each "
               "part says one thing."), None)},
    "reduced-object-relative": {
        "c1": ("Add 'that' to the clause in '{q}'.", "Add 'that' to start the clause."),
        "c2": ("Leave '{q}' if the clause is short; otherwise add 'that' or make the clause a sentence of its own.",
               "Leave the clause if it is short; otherwise add 'that' or make it a sentence of its own.")},
    "hyphen-compound": {
        "c1": ("Write '{q}' out as a phrase that says how its parts relate.",
               "Write the hyphenated words out as a phrase that says how they relate."),
        "c2": ("Keep '{q}' if it is an established term; otherwise write it out.",
               "Keep the hyphenated words if they are an established term; otherwise write them out.")},
    "inline-list": {
        "c1": ("Put the {n} items in a bulleted list, after a sentence that introduces them.", None),
        "c2": ("Leave the list in the sentence if the items are short; otherwise use a bulleted list.", None)},
}

PAIRWISE_SHORT = ea.PAIRWISE.rsplit("\n\n", 1)[0] + '\n\nAnswer "1", "2" or "tie".'
SHORT_SCHEMA = {"type": "object", "properties": {"easier": {"type": "string", "enum": ["1", "2", "tie"]}},
                "required": ["easier"], "additionalProperties": False}
POINTWISE = """Here is one paragraph from the documentation of a software project. The intended reader is a developer who is new to the project and reads its documentation to learn what it does and how to use it.

How easy is it for that reader to read and understand? Judge only how easy it is to read.

Paragraph:
{text}

Answer with a score from 1 (very hard to read) to 7 (very easy to read)."""
POINT_SCHEMA = {"type": "object", "properties": {"score": {"type": "integer", "minimum": 1, "maximum": 7}},
                "required": ["score"], "additionalProperties": False}


# ---- the text --------------------------------------------------------------------

def _quote(text: str | None) -> str | None:
    return text if text and len(text.split()) <= MAX_QUOTE_WORDS else None


def slots(f) -> dict:
    """The words a candidate may quote, from the finding's message or excerpt."""
    if f.feature in ("stacked-nouns", "reduced-object-relative"):
        m = re.search(r"'(.+)'", f.message)
        return {"q": _quote(m.group(1) if m else None)}
    if f.feature == "hyphen-compound":
        return {"q": _quote(f.excerpt)}
    if f.feature == "long-dependency":
        m = re.search(r"'(.+?)' and '(.+?)' are", f.message)
        return {"a": m.group(1), "b": m.group(2)} if m else {}
    if f.feature == "inline-list":
        m = re.match(r"(\d+) items", f.message)
        return {"n": m.group(1)} if m else {}
    return {}


def candidate_fix(f, cand: str) -> str:
    """The candidate's fix for one finding, with readcost's reminder to keep a reason."""
    quoted, plain = CANDIDATES[f.feature][cand]
    s = slots(f)
    names = set(re.findall(r"\{(\w+)\}", quoted))
    if all(s.get(k) for k in names):
        base = quoted.format(**s)
    else:
        base = plain if plain else None
    if base is None:
        return f.suggestion
    return at.fix_for(f.feature, f.sentence, base)


def render(result, species: str = "seed", cand: str = "v0", max_items: int = 8, max_chars: int = 2500) -> str:
    """R0 (`readcost check -o agent`), or R0 with one species' candidate."""
    from readcost.report import _worst_first
    items = _worst_first([result])
    if not items:
        return ""
    precision = species != "note"
    total = len(items)
    head = at.HEAD_ORDER.format(n=total, s="s" if total != 1 else "", words=result.words)
    lines = [head]
    for f in items[:max_items]:
        loc = f"line {f.line}" if f.line else (f.label or f.path)
        fix = candidate_fix(f, cand) if species == f.feature else f.suggestion
        lines.append(at._line(loc, f.feature, f.message, at._note(f.feature) if precision else "", fix))
    if total > max_items:
        lines.append(f"- ...and {total - max_items} more (run `readcost check` for the full list)")
    body = "\n".join(lines)
    return body[: max_chars - 3] + "..." if len(body) > max_chars else body


def cands(species: str) -> tuple[str, ...]:
    return ("c1",) if species == "note" else ("c1", "c2")


# ---- paragraphs and the plan -------------------------------------------------------

def split(paras: list[dict]) -> tuple[list[str], list[str]]:
    """(audit ids, training ids), in the plan's shuffled order."""
    order = sorted(p["id"] for p in paras)
    random.Random(SEED).shuffle(order)
    return order[:AUDIT_N], order[AUDIT_N:]


def plan(analyzer, ref: Path) -> dict:
    from readcost.report import _worst_first
    paras = at.texts(ref)
    by = {p["id"]: p for p in paras}
    audit, train = split(paras)
    prompts, rules_of = {}, {}
    for pid in audit + train:
        result = ea.check(analyzer, by[pid]["text"])
        shown = {f.feature for f in _worst_first([result])[:8]}
        if not shown:
            continue
        rules_of[pid] = shown
        text = by[pid]["text"]
        prompts[(pid, "seed", "v0")] = at.prompt(text, render(result))
        for sp in SPECIES:
            if sp != "note" and sp not in shown:
                continue
            for c in cands(sp):
                prompts[(pid, sp, c)] = at.prompt(text, render(result, sp, c))
    groups = {}
    for sp in SPECIES:
        mine = [pid for pid in train if pid in rules_of and (sp == "note" or sp in rules_of[pid])]
        k = math.ceil(len(mine) / 3)
        groups[sp] = {"screen": mine[:k], "confirm": mine[k:],
                      "audit": [pid for pid in audit if pid in rules_of and (sp == "note" or sp in rules_of[pid])]}
    main = {p["id"] for p in at.choose(analyzer, paras)[0]}
    calib = [pid for pid in train if pid in main][:CALIB_N]
    return {"prompts": prompts, "groups": groups, "texts": {p["id"]: p["text"] for p in paras},
            "rules": rules_of, "calib": calib, "audit": audit, "train": train, "main": sorted(main)}


# ---- asking with log probabilities --------------------------------------------------

def answer_probs(content: list[dict] | None) -> dict | None:
    """{"1", "2", "tie": probability} for the "easier" value, from a reply's token log probabilities."""
    if not content:
        return None
    text = ""
    for tok in content:
        here = tok.get("token", "")
        open_quote = re.search(r'"easier"\s*:\s*"$', text)
        # A token that holds the opening quote and the answer together, as '"2'.
        before_quote = (re.search(r'"easier"\s*:\s*$', text) and here.lstrip().startswith('"')
                        and here.strip().lstrip('"') != "")
        if open_quote or before_quote:
            probs = {"1": 0.0, "2": 0.0, "tie": 0.0}
            for alt in tok.get("top_logprobs") or [{"token": here, "logprob": tok.get("logprob", 0.0)}]:
                t = alt.get("token", "").strip().lstrip('"')
                key = "1" if t.startswith("1") else "2" if t.startswith("2") else "tie" if t.startswith("t") else None
                if key:
                    probs[key] += math.exp(alt.get("logprob", -math.inf))
            total = sum(probs.values())
            return {k: v / total for k, v in probs.items()} if total > 0 else None
        text += here
    return None


def logprob_ask(base_url: str, extras: dict | None = None, max_tokens: int = ea.MAX_TOKENS, timeout: int = 900,
                urlopen=urllib.request.urlopen, retry_wait: float = 5.0):
    """`eval_edit_arms.openai_ask` with token log probabilities, kept in the reply's meta as ``probs``."""
    extras = extras or {}
    url = base_url.rstrip("/") + "/chat/completions"

    def ask(model: str, prompt: str, schema: dict, system: str | None = None) -> tuple[dict | None, dict]:
        body = {"model": model, "messages": ea.messages_for(prompt, system), "temperature": 0,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": "out", "strict": True, "schema": schema}},
                **extras.get(model, {})}
        if "easier" in schema.get("properties", {}):
            body.update({"logprobs": True, "top_logprobs": 5})
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        meta: dict = {"requested": model}
        rev = ea.OPEN_MODELS.get(model, {}).get("revision")
        if rev:
            meta["revision"] = rev
        for attempt in range(2):
            try:
                with urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read())
                break
            except urllib.error.HTTPError as exc:
                meta["error"] = f"HTTP {exc.code}"
            except (OSError, json.JSONDecodeError) as exc:
                meta["error"] = str(exc)[:300]
            if attempt == 1:
                return None, meta
            time.sleep(retry_wait)
        meta.pop("error", None)
        meta["served"] = data.get("model")
        choice = (data.get("choices") or [{}])[0]
        meta["finish"] = choice.get("finish_reason")
        probs = answer_probs((choice.get("logprobs") or {}).get("content"))
        if probs is not None:
            meta["probs"] = probs
        parsed, err = ea.parse_reply(choice.get("message", {}).get("content") or "")
        if err:
            meta["error"] = err
        return parsed, meta
    return ask


def short_prompt(first: str, second: str) -> str:
    return PAIRWISE_SHORT.format(first=first, second=second)


def short_reply(client, judge: str, first: str, second: str) -> tuple[str | None, dict | None]:
    """(answer, probabilities) of one short pairwise judgement, from the cache."""
    row = client.ok.get(client.key(judge, None, short_prompt(first, second)))
    if not row:
        return None, None
    ans = str((row["data"] or {}).get("easier", "")).strip().lower()
    return (ans if ans in ("1", "2", "tie") else None), (row.get("meta") or {}).get("probs")


def point_score(client, judge: str, text: str) -> int | None:
    data = client.get(judge, None, POINTWISE.format(text=text))
    v = (data or {}).get("score")
    return v if isinstance(v, int) and 1 <= v <= 7 else None


# ---- scoring a unit -----------------------------------------------------------------

def changed(client, judges, original: str, edit: str | None) -> bool | None:
    if edit is None:
        return None
    got = [c for c in (at.facts_of(client, j, original, edit) for j in judges) if c]
    return any(c["lost"] or c["changed"] for c in got) if got else None


def p_candidate(client, judges, cand: str, seed: str) -> tuple[float | None, float | None]:
    """(probability, win-tie-loss score) that the candidate's edit reads better, over orders and judges."""
    ps, wtl = [], []
    for j in judges:
        a1, p1 = short_reply(client, j, cand, seed)
        a2, p2 = short_reply(client, j, seed, cand)
        if p1 and p2:
            ps.append(((p1["1"] + 0.5 * p1["tie"]) + (p2["2"] + 0.5 * p2["tie"])) / 2)
        if a1 and a2:
            first = {"1": "X", "2": "S", "tie": "tie"}[a1]
            second = {"1": "S", "2": "X", "tie": "tie"}[a2]
            wtl.append(ea.SCORE[ea.outcome(first, second, "X", "S")])
    return (statistics.mean(ps) if ps else None), (statistics.mean(wtl) if wtl else None)


def unit(client, pl: dict, pid: str, ed: str, sp: str, c: str, judges=JUDGES) -> dict | None:
    """The unit's paired score Δ and its parts; None when an edit or a judgement is missing."""
    original = pl["texts"][pid]
    s_edit = at.edit_text(client, ed, pl["prompts"][(pid, "seed", "v0")])
    c_edit = at.edit_text(client, ed, pl["prompts"][(pid, sp, c)])
    cs, cc = changed(client, judges, original, s_edit), changed(client, judges, original, c_edit)
    if cs is None or cc is None:
        return None
    out = {"seed_changes": cs, "cand_changes": cc}
    if cs != cc:
        out.update(delta=1.0 if cs else -1.0, delta_wtl=1.0 if cs else -1.0, judged=False)
        return out
    if cs and cc:
        out.update(delta=0.0, delta_wtl=0.0, judged=False)
        return out
    p, w = p_candidate(client, judges, c_edit, s_edit)
    if p is None and w is None:
        return None
    # Where vLLM returned no log probabilities for the answer, the votes stand in (the plan's rule).
    out.update(delta=2 * p - 1 if p is not None else 2 * w - 1,
               delta_wtl=(2 * w - 1) if w is not None else None, judged=True, p=p, from_votes=p is None)
    sc = [point_score(client, j, c_edit) for j in judges]
    ss = [point_score(client, j, s_edit) for j in judges]
    pairs = [(a, b) for a, b in zip(sc, ss) if a is not None and b is not None]
    if pairs:
        out["point"] = statistics.mean((a - b) / 6 for a, b in pairs)
    return out


def needs_reading(client, pl, pid, ed, sp, c, judges=JUDGES) -> tuple[str, str] | None:
    """The two edits to compare, when facts leave the unit to readability."""
    original = pl["texts"][pid]
    s_edit = at.edit_text(client, ed, pl["prompts"][(pid, "seed", "v0")])
    c_edit = at.edit_text(client, ed, pl["prompts"][(pid, sp, c)])
    cs, cc = changed(client, judges, original, s_edit), changed(client, judges, original, c_edit)
    if cs is None or cc is None or cs or cc:
        return None
    return c_edit, s_edit


# ---- statistics -----------------------------------------------------------------------

def gain(values: dict):
    return ea.cluster_boot(values) if values else None


def se_of(est) -> float | None:
    return None if est is None else (est[2] - est[1]) / (2 * 1.96)


def shrink(est) -> float | None:
    if est is None:
        return None
    g, se = est[0], se_of(est)
    return 0.0 if g == 0 else g * max(0.0, 1 - (se * se) / (g * g))


def deltas(client, pl, sp, c, pids, editors=EDITORS, judges=JUDGES, key="delta") -> dict:
    out = {}
    for pid in pids:
        for ed in editors:
            u = unit(client, pl, pid, ed, sp, c, judges)
            if u is not None and u.get(key) is not None:
                out[(pid, ed)] = u[key]
    return out


def survivors(client, pl, sp, editors=EDITORS, judges=JUDGES) -> dict:
    """The screen: who goes on to confirmation, and why."""
    pids = pl["groups"][sp]["screen"]
    est = {c: gain(deltas(client, pl, sp, c, pids, editors, judges)) for c in cands(sp)}
    alive = [c for c in cands(sp) if est[c] is not None and est[c][2] >= 0]
    diff = None
    if len(alive) == 2:
        d1, d2 = (deltas(client, pl, sp, c, pids, editors, judges) for c in alive)
        both = {k: d1[k] - d2[k] for k in d1 if k in d2}
        diff = gain(both)
        if diff is not None and (diff[1] > 0 or diff[2] < 0):
            alive = [alive[0] if diff[0] > 0 else alive[1]]
    return {"screen": est, "c1_minus_c2": diff, "go_on": alive}


def choose(client, pl, sp, go_on, editors=EDITORS, judges=JUDGES) -> dict:
    conf = {c: gain(deltas(client, pl, sp, c, pl["groups"][sp]["confirm"], editors, judges)) for c in go_on}
    audit = {c: gain(deltas(client, pl, sp, c, pl["groups"][sp]["audit"], editors, judges)) for c in go_on}
    ok = [c for c in go_on if conf[c] is not None and conf[c][1] > 0]
    winner = max(ok, key=lambda c: conf[c][0]) if ok else None
    return {"confirm": conf, "audit": audit, "shrunk": {c: shrink(conf[c]) for c in go_on}, "winner": winner}


# ---- calibration ------------------------------------------------------------------------

def calibration(client, pl, judge: str, editors=EDITORS) -> dict:
    """The plan's five checks for one judge."""
    tx = pl["texts"]
    replies, splits, outcomes, ident, ident_one, fc, fr, null = 0, 0, 0, 0, 0, [], [], []
    parsed = 0
    for pid in pl["calib"]:
        a = tx[pid]
        for ed in editors:
            r0 = at.edit_text(client, ed, pl["prompts"][(pid, "seed", "v0")])
            c = at.anchor(client, ed, a)
            if r0 is None or c is None:
                continue
            x1, _ = short_reply(client, judge, r0, c)
            x2, _ = short_reply(client, judge, c, r0)
            replies += 2
            parsed += (x1 is not None) + (x2 is not None)
            if x1 and x2:
                first = {"1": "R", "2": "C", "tie": "tie"}[x1]
                second = {"1": "C", "2": "R", "tie": "tie"}[x2]
                outcomes += 1
                splits += ea.outcome(first, second, "R", "C") == "split"
            for edit, sink in ((r0, fr), (c, fc)):
                got = at.facts_of(client, judge, a, edit)
                replies += 1
                parsed += got is not None
                if got:
                    sink.append(bool(got["lost"] or got["changed"]))
        x, _ = short_reply(client, judge, a, a)
        replies += 1
        parsed += x is not None
        if x in ("1", "2"):
            ident += 1
            ident_one += x == "1"
        got = at.facts_of(client, judge, a, a)
        replies += 1
        parsed += got is not None
        if got:
            null.append(bool(got["lost"] or got["changed"]))
    res = {"parsed": parsed / replies if replies else None,
           "split_rate": splits / outcomes if outcomes else None,
           "identical_first": ident_one / ident if ident else None,
           "facts_gap": (statistics.mean(fc) - statistics.mean(fr)) if fc and fr else None,
           "null_rate": statistics.mean(null) if null else None}
    res["passes"] = {
        "parsing": res["parsed"] is not None and res["parsed"] >= 0.90,
        "position": res["split_rate"] is not None and res["split_rate"] <= 0.70,
        "identical": res["identical_first"] is None or 0.25 <= res["identical_first"] <= 0.75,
        "facts": res["facts_gap"] is not None and res["facts_gap"] >= 0.05,
        "null": res["null_rate"] is not None and res["null_rate"] <= 0.10}
    res["pass"] = all(res["passes"].values())
    return res


# ---- the run ---------------------------------------------------------------------------

def run(ref: Path, client, analyzer, editors=EDITORS, judges=JUDGES, workers: int = 8, call_editors=None,
        call_judges=None, phases=None) -> dict:
    """Phases edits, calib, facts, screen, confirm. Returns which finished."""
    pl = plan(analyzer, ref)
    tx, pr = pl["texts"], pl["prompts"]
    ask_e = editors if call_editors is None else call_editors
    ask_j = judges if call_judges is None else call_judges
    status = {}

    def shuffled(jobs, tag):
        random.Random(f"{SEED}:calls:{tag}").shuffle(jobs)
        return jobs

    def pool(jobs, one, again):
        ok = ea._pool(jobs, one, workers)
        return ok and ea._pool([j for j in jobs if again(j)], one, workers)

    def edits():
        jobs = shuffled([(ed, k) for k in sorted(pr) for ed in ask_e], "edits")
        return pool(jobs, lambda j: client(j[0], ea.SYSTEM, pr[j[1]], ea.TEXT_SCHEMA),
                    lambda j: at.edit_text(client, j[0], pr[j[1]]) is None)

    def calib():
        jobs = []
        for pid in pl["calib"]:
            a = tx[pid]
            for j in ask_j:
                jobs += [("short", j, a, a), ("fact", j, a, a)]
                for ed in editors:
                    r0, c = at.edit_text(client, ed, pr[(pid, "seed", "v0")]), at.anchor(client, ed, a)
                    if r0 is None or c is None:
                        continue
                    jobs += [("short", j, r0, c), ("short", j, c, r0), ("fact", j, a, r0), ("fact", j, a, c)]
        jobs = shuffled(jobs, "calib")

        def one(job):
            kind, j, x, y = job
            if kind == "short":
                client(j, None, short_prompt(x, y), SHORT_SCHEMA)
            else:
                client(j, None, ea.fact_prompt(x, y), ea.fact_schema())

        def again(job):
            kind, j, x, y = job
            return (short_reply(client, j, x, y)[0] is None) if kind == "short" else at.facts_of(client, j, x, y) is None
        return pool(jobs, one, again)

    def facts():
        jobs = []
        for (pid, _sp, _c), p in pr.items():
            for ed in editors:
                e = at.edit_text(client, ed, p)
                if e is not None:
                    jobs += [(j, pid, e) for j in ask_j]
        jobs = shuffled(sorted(set(jobs)), "facts")
        return pool(jobs, lambda jb: client(jb[0], None, ea.fact_prompt(tx[jb[1]], jb[2]), ea.fact_schema()),
                    lambda jb: at.facts_of(client, jb[0], tx[jb[1]], jb[2]) is None)

    def reading(which):
        jobs = []
        for sp in SPECIES:
            if which == "screen":
                pairs = [(pid, c) for pid in pl["groups"][sp]["screen"] for c in cands(sp)]
            else:
                go_on = survivors(client, pl, sp, editors, judges)["go_on"]
                pids = pl["groups"][sp]["confirm"] + pl["groups"][sp]["audit"]
                pairs = [(pid, c) for pid in pids for c in go_on]
            for pid, c in pairs:
                for ed in editors:
                    got = needs_reading(client, pl, pid, ed, sp, c, judges)
                    if got:
                        ce, se = got
                        for j in ask_j:
                            jobs += [("short", j, ce, se), ("short", j, se, ce), ("point", j, ce, None),
                                     ("point", j, se, None)]
        jobs = shuffled(sorted(set(jobs), key=repr), which)

        def one(job):
            kind, j, x, y = job
            if kind == "short":
                client(j, None, short_prompt(x, y), SHORT_SCHEMA)
            else:
                client(j, None, POINTWISE.format(text=x), POINT_SCHEMA)

        def again(job):
            kind, j, x, y = job
            return short_reply(client, j, x, y)[0] is None if kind == "short" else point_score(client, j, x) is None
        return pool(jobs, one, again)

    steps = (("edits", edits), ("calib", calib), ("facts", facts), ("screen", lambda: reading("screen")),
             ("confirm", lambda: reading("confirm")))
    for name, phase in steps:
        if phases is not None and name not in phases:
            continue
        status[name] = bool(phase())
        print(name, "done" if status[name] else "stopped", f"{client.calls} calls", flush=True)
        if not status[name]:
            break
    return status


# ---- analysis and report ------------------------------------------------------------------

def analyse(client, analyzer, pl: dict, editors=EDITORS, judges=JUDGES) -> dict:
    res: dict = {"species": {}, "calibration": {j: calibration(client, pl, j, editors) for j in judges},
                 "paragraphs": {"audit": len(pl["audit"]), "train": len(pl["train"]), "with_findings": len(pl["rules"])}}
    allv = []
    for sp in SPECIES:
        sv = survivors(client, pl, sp, editors, judges)
        ch = choose(client, pl, sp, sv["go_on"], editors, judges)
        grp = pl["groups"][sp]
        row = {"units": {k: len(v) * len(editors) for k, v in grp.items()}, **sv, **ch}
        # Secondary outcomes, over the confirmation units.
        row["wtl"] = {c: gain(deltas(client, pl, sp, c, grp["confirm"], editors, judges, "delta_wtl"))
                      for c in sv["go_on"]}
        row["point"] = {c: gain(deltas(client, pl, sp, c, grp["confirm"], editors, judges, "point"))
                        for c in sv["go_on"]}
        row["per_editor"] = {ed: {c: gain(deltas(client, pl, sp, c, grp["confirm"], [ed], judges))
                                  for c in sv["go_on"]} for ed in editors}
        shares = {}
        for c in ("v0",) + cands(sp):
            key_sp = "seed" if c == "v0" else sp
            flags, cleared, ratio = [], [], []
            for pid in grp["screen"] + grp["confirm"] + grp["audit"]:
                for ed in editors:
                    e = at.edit_text(client, ed, pl["prompts"][(pid, key_sp, c)])
                    ch_ = changed(client, judges, pl["texts"][pid], e)
                    if ch_ is not None:
                        flags.append(ch_)
                    if e is not None:
                        ratio.append(len(e.split()) / len(pl["texts"][pid].split()))
                        if sp != "note":
                            cleared.append(all(f.feature != sp for f in ea.check(analyzer, e).findings))
            shares[c] = {"changes": round(statistics.mean(flags), 3) if flags else None,
                         "rule_cleared": round(statistics.mean(cleared), 3) if cleared else None,
                         "length": round(statistics.median(ratio), 3) if ratio else None}
        row["arms"] = shares
        for c in cands(sp):
            allv += list(deltas(client, pl, sp, c, grp["screen"], editors, judges).values())
        res["species"][sp] = row
    judged, voted = 0, 0
    for (pid, sp, c) in pl["prompts"]:
        if sp == "seed":
            continue
        for ed in editors:
            u = unit(client, pl, pid, ed, sp, c, judges)
            if u and u.get("judged"):
                judged += 1
                voted += bool(u.get("from_votes"))
    res["from_votes"] = {"units": voted, "of_judged": judged}
    res["delta_sd"] = round(statistics.pstdev(allv), 3) if len(allv) > 1 else None
    if res["delta_sd"]:
        res["detectable"] = {sp: round(2.8 * res["delta_sd"] / math.sqrt(max(1, r["units"]["confirm"])), 3)
                             for sp, r in res["species"].items()}
    return res


def fmt(est) -> str:
    return "—" if est is None else "{:+.3f} [{:+.3f}, {:+.3f}]".format(*est)


def report(res: dict, status: dict, calls: dict) -> str:
    yn = {True: "yes", False: "no", None: "—"}
    out = ["## Agent feedback text, stage 3: fixes that use the finding's words", "",
           f"Paragraphs: audit {res['paragraphs']['audit']}, training {res['paragraphs']['train']}, with a finding "
           f"{res['paragraphs']['with_findings']}. Calls {calls.get('calls')} in the cache (new this run "
           f"{calls.get('new')}). Phases: " + ", ".join(f"{k} {'done' if v else 'stopped'}" for k, v in status.items())
           + f". Units scored from votes for lack of log probabilities: {res.get('from_votes', {}).get('units')} of "
           f"{res.get('from_votes', {}).get('of_judged')} judged.",
           "", "| Judge | Parsed | Split rate | Identical, picks 1 | Facts gap (C − R0) | Null rate | Passes |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    for j, c in res["calibration"].items():
        out.append(f"| {j} | {c['parsed']} | {c['split_rate']} | {c['identical_first']} | {c['facts_gap']} | "
                   f"{c['null_rate']} | {yn[c['pass']]} |")
    out += ["", f"Per-unit standard deviation of Δ on the screen: {res.get('delta_sd')}.", "",
            "| Species | Candidate | Screen gain | Goes on | Confirmation gain | Shrunk | Audit gain | Chosen |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for sp, r in res["species"].items():
        for c in cands(sp):
            go = c in r["go_on"]
            out.append(f"| {sp} | {c} | {fmt(r['screen'].get(c))} | {yn[go]} | {fmt(r['confirm'].get(c))} | "
                       f"{'' if r['shrunk'].get(c) is None else round(r['shrunk'][c], 3)} | {fmt(r['audit'].get(c))} | "
                       f"{'yes' if r['winner'] == c else ''} |")
    out += ["", "| Species | Arm | Changes content | Rule cleared | Length |", "| --- | --- | --- | --- | --- |"]
    for sp, r in res["species"].items():
        for c, a in r["arms"].items():
            out.append(f"| {sp} | {'seed' if c == 'v0' else c} | {a['changes']} | {a['rule_cleared']} | {a['length']} |")
    if res.get("detectable"):
        out += ["", "Detectable gain on the confirmation units (80% power): "
                + ", ".join(f"{sp} {v}" for sp, v in res["detectable"].items()) + "."]
    winners = {sp: r["winner"] for sp, r in res["species"].items() if r["winner"]}
    out += ["", "Winners: " + (", ".join(f"{sp} {c}" for sp, c in winners.items()) or "none; today's text stays")
            + ". Nothing in readcost changes without a held-out confirmation."]
    return "\n".join(out) + "\n"
