"""The localization control for the edit test: docs/prereg/edit-localize.md.

Arm E points at as many sentences as readcost's findings (arm B), chosen by
length, in B's form. This module continues the edit test's draw, builds E's
feedback, runs the phases with one model loaded at a time (through
`scripts/edit_localize_job.py`), and writes the report. Prompts, the client,
the judges, counting and the bootstrap are `eval_edit_arms`'s, unchanged.

    python scripts/eval_edit_localize.py draw      # the 140 new paragraphs (readcost at a57e19e)
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_edit_arms as ea

ROOT = ea.ROOT
PLAN_COMMIT = "39969c8"           # the registration; the new drop reason reads its scripts/, eval/, docs/
N_NEW = 140
OLD_WALKED = 784
SEED = "20261120:edit-localize"
CALL_CAP = 19_000
HOURS = 2.5
SMALLEST_DIFF = 0.05
POINTERS = ROOT / "eval" / "edit-localize"
OLD_POINTERS = ROOT / "eval" / "edit-arms"
E_LINE = "- line {line} [long-sentence] {n} words in one sentence. Fix: Split it into shorter sentences, if the result reads naturally."


# ---- the continued draw ----------------------------------------------------

def tree_text(rev: str, skip: tuple[str, ...] = ()) -> str:
    """Text of every file under scripts/, eval/ and docs/ at ``rev``, lowercased, but those under ``skip``."""
    names = subprocess.run(["git", "ls-tree", "-r", "--name-only", rev, "scripts", "eval", "docs"],
                           cwd=ROOT, check=True, capture_output=True, text=True).stdout.split("\n")
    names = [n for n in names if n and not n.startswith(skip)]
    blob = subprocess.run(["git", "cat-file", "--batch"], cwd=ROOT, check=True, capture_output=True,
                          input="".join(f"{rev}:{n}\n" for n in names).encode()).stdout
    return blob.decode("utf-8", "replace").lower()


def first_order(rows: list[dict]) -> list[str]:
    """The edit test's walk order: its drop reasons (reason 2 could not act, amendment 5), sorted, shuffled."""
    corpus = ea.exclusion_patterns()
    kept = sorted(r["repo"] for r in rows if ea.drop_reason({"full_name": r["repo"], **r}, corpus, "") is None)
    random.Random(ea.SEED).shuffle(kept)
    return kept


def walk_on(order: list[str], files_for, analyzer, seen: set[str], newer: str, n: int = N_NEW,
            workers: int = 16, start: int = OLD_WALKED) -> tuple[list[dict], list[dict]]:
    """The edit test's walk, from the 785th repository, with the plan's extra drop reason.

    ``files_for`` runs ahead in a pool; repositories are still taken in order, and one fetched
    beyond the stop is neither recorded nor used.
    """
    rest = order[start:]
    picked, log = [], []
    with ThreadPoolExecutor(workers) as pool:
        todo = [r for r in rest]
        futures = {}
        i = 0

        def ahead(upto):
            for r in todo[i:upto]:
                if r not in futures and not ea.named_in(r, newer):
                    futures[r] = pool.submit(files_for, r)
        while i < len(todo) and len(picked) < n:
            ahead(i + workers * 2)
            repo = todo[i]
            i += 1
            if ea.named_in(repo, newer):
                log.append({"repo": repo, "outcome": "named in a later evaluation"})
                continue
            got = futures.pop(repo).result()
            if len(log) % 100 == 0:
                print(f"walked {len(log)}, drawn {len(picked)}", file=sys.stderr, flush=True)
            if isinstance(got, str):
                log.append({"repo": repo, "outcome": got})
                continue
            commit, files = got
            cands = []
            for path, text in files:
                cands += [c for c in ea.eligible(text, path, analyzer) if c["sha256"] not in seen]
            cands.sort(key=lambda c: (c["path"], c["start"]))
            if not cands:
                log.append({"repo": repo, "outcome": "no eligible paragraph"})
                continue
            c = random.Random(f"{ea.SEED}:{repo}:pick").choice(cands)
            seen.add(c["sha256"])
            picked.append({"id": c["sha256"][:12], "repo": repo, "commit": commit, **c})
            log.append({"repo": repo, "outcome": "drawn", "eligible": len(cands)})
        for f in futures.values():
            f.cancel()
    return picked, log


def draw(out: Path = POINTERS) -> None:
    from readcost import Analyzer, Config
    if ea.verify() != 0:
        raise SystemExit(1)
    rows = [json.loads(x) for x in (OLD_POINTERS / "candidates.jsonl").read_text().splitlines()]
    order = first_order(rows)
    old = [json.loads(x)["repo"] for x in (OLD_POINTERS / "walk.jsonl").read_text().splitlines()]
    if order[:OLD_WALKED] != old:
        raise SystemExit("the rebuilt order does not match eval/edit-arms/walk.jsonl; not drawn")
    seen = {json.loads(x)["sha256"] for x in (OLD_POINTERS / "paragraphs.jsonl").read_text().splitlines()}
    newer = tree_text(PLAN_COMMIT, skip=("eval/edit-arms/",))
    picked, log = walk_on(order, ea.github_files, Analyzer(Config()), seen, newer)
    out.mkdir(parents=True, exist_ok=True)
    (out / "paragraphs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in picked))
    (out / "walk.jsonl").write_text("".join(json.dumps(x) + "\n" for x in log))
    print(json.dumps({"order": len(order), "walked before": OLD_WALKED, "walked": len(log),
                      "left": len(order) - OLD_WALKED - len(log),
                      "outcomes": dict(Counter(x["outcome"] for x in log)), "drawn": len(picked)}, indent=1))


# ---- arm E's feedback -------------------------------------------------------

def sentences(analyzer, text: str) -> list[dict]:
    """The sentences readcost checks and counts in `Result.words`, with source offsets, line and length.

    The same test as `Analyzer.analyze`: four or more alphabetic tokens and a verb or auxiliary,
    or a verb the parser read as a noun (`misparsed_verb`).
    """
    from readcost.engine import misparsed_verb
    from readcost.extract import extract
    segs = extract(text, "p.md", "markdown", comments=analyzer.cfg.comments)
    out = []
    for seg, doc in zip(segs, analyzer.nlp.pipe([s.text for s in segs])):
        for sent in doc.sents:
            n = sum(t.is_alpha for t in sent)
            if n < 4:
                continue
            if not any(t.pos_ in ("VERB", "AUX") for t in sent) and not misparsed_verb(sent):
                continue
            span = seg.span(sent.start_char, sent.end_char)
            out.append({"span": span, "line": seg.line_at(sent.start_char), "n": n,
                        "text": text[span[0]:span[1]] if span else sent.text})
    return out


def b_spans(result) -> list:
    """The sentences that hold the findings B's feedback lists (the first eight, worst first)."""
    from readcost.report import _worst_first
    keys = []
    for i, f in enumerate(_worst_first([result])[:8]):
        k = (f.sentence_start, f.sentence_end) if None not in (f.sentence_start, f.sentence_end) else ("f", i)
        if k not in keys:
            keys.append(k)
    return keys


def e_feedback(analyzer, text: str) -> dict:
    """B's feedback, E's feedback and the sentences each points at, from one readcost Result."""
    from readcost import report
    result = ea.check(analyzer, text)
    b = b_spans(result)
    sents = sentences(analyzer, text)
    k = len(b)
    longest = sorted(range(len(sents)), key=lambda i: (-sents[i]["n"], i))[:k]
    chosen = [sents[i] for i in longest]
    if chosen:
        head = (f"readcost: {len(chosen)} hard-to-read construction{'s' if len(chosen) != 1 else ''} "
                f"in {result.words} words. Rewrite these sentences where the finding holds; keep the meaning "
                "and the facts.")
        fb_e = "\n".join([head] + [E_LINE.format(line=s["line"], n=s["n"]) for s in chosen])
    else:
        fb_e = ""
    return {"B": report.agent([result], feedback_link=False), "E": fb_e,
            "b_spans": [tuple(x) for x in b], "e_spans": [tuple(s["span"]) for s in chosen if s["span"]],
            "sentences": sents}


def all_feedback(analyzer, paras: list[dict]) -> dict:
    return {p["id"]: e_feedback(analyzer, p["text"]) for p in paras}


def prompt(arm: str, text: str, fb: dict) -> str:
    if arm == "E":
        return ea.ARM_B.format(budget=ea.budget(text), feedback=fb["E"], text=text)
    return ea.edit_prompt(arm, text, fb.get("B", "") if arm == "B" else "")


def edit_of(client, p: dict, ed: str, arm: str, fb: dict) -> str | None:
    data = client.get(ed, ea.SYSTEM, prompt(arm, p["text"], fb[p["id"]]))
    text = (data or {}).get("text")
    return text.strip() if isinstance(text, str) and text.strip() else None


ARMS = ("B", "C", "E")


def arms_for(p: dict) -> tuple[str, ...]:
    """The edit arms this test asks for: E everywhere, B and C on the new paragraphs only."""
    return ARMS if p.get("new") else ("E",)


def texts_of(client, p: dict, ed: str, fb: dict) -> dict:
    return {"A": p["text"], **{arm: edit_of(client, p, ed, arm, fb) for arm in ARMS}}


def fact_of(client, p: dict, edit: str | None, judge: str) -> dict | None:
    if edit is None:
        return None
    data = client.get(judge, None, ea.fact_prompt(p["text"], edit))
    if not data or not all(isinstance(data.get(k), list) for k in ("lost", "added", "changed")):
        return None
    return data


def pick_of(client, call: dict, t: dict) -> str | None:
    a, b = (t[s] for s in ea.shown(call))
    if a is None or b is None:
        return None
    return ea.chosen_arm(call, ea.parse_easier(client.get(call["judge"], None, ea.pair_prompt(a, b))))


# ---- the run -----------------------------------------------------------------

def load(ref: Path) -> list[dict]:
    return [json.loads(x) for x in (ref / "texts.jsonl").read_text().splitlines()]


def run(ref: Path, client, analyzer, editors, judges, workers: int = 8, call_editors=None, call_judges=None,
        phases=None) -> dict:
    """The plan's three phases: edits, facts (the primary outcome), E against B. Returns which finished."""
    paras = load(ref)
    fb = all_feedback(analyzer, paras)
    ask_editors = editors if call_editors is None else call_editors
    ask_judges = judges if call_judges is None else call_judges
    status = {}

    def edits():
        jobs = [(p, ed, arm) for p in paras for ed in ask_editors for arm in arms_for(p)]
        random.Random(f"{SEED}:calls:edits").shuffle(jobs)

        def one(job):
            p, ed, arm = job
            client(ed, ea.SYSTEM, prompt(arm, p["text"], fb[p["id"]]), ea.TEXT_SCHEMA)
        ok = ea._pool(jobs, one, workers)
        return ok and ea._pool([j for j in jobs if edit_of(client, *j, fb) is None], one, workers)

    def facts():
        jobs = [(p, ed, arm, j) for p in paras for ed in editors for arm in arms_for(p) for j in ask_judges]
        random.Random(f"{SEED}:calls:facts").shuffle(jobs)

        def one(job):
            p, ed, arm, j = job
            e = edit_of(client, p, ed, arm, fb)
            if e is not None:
                client(j, None, ea.fact_prompt(p["text"], e), ea.fact_schema())
        ok = ea._pool(jobs, one, workers)
        again = [jb for jb in jobs if (e := edit_of(client, *jb[:3], fb)) is not None
                 and fact_of(client, jb[0], e, jb[3]) is None]
        return ok and ea._pool(again, one, workers)

    def eb():
        by = {p["id"]: p for p in paras}
        calls = ea.judge_calls([(p["id"], ed) for p in paras for ed in editors], [("E", "B")], ask_judges,
                               f"{SEED}:calls:EB")

        def one(c):
            t = texts_of(client, by[c["id"]], c["editor"], fb)
            a, b = (t[s] for s in ea.shown(c))
            if a is not None and b is not None:
                client(c["judge"], None, ea.pair_prompt(a, b), ea.PAIRWISE_SCHEMA)
        ok = ea._pool(calls, one, workers)

        def missing(c):
            t = texts_of(client, by[c["id"]], c["editor"], fb)
            return all(t[s] is not None for s in ea.shown(c)) and pick_of(client, c, t) is None
        return ok and ea._pool([c for c in calls if missing(c)], one, workers)

    for name, phase in (("edits", edits), ("facts", facts), ("EB", eb)):
        if phases is not None and name not in phases:
            continue
        status[name] = bool(phase())
        print(name, "done" if status[name] else "stopped", f"{client.calls} calls", flush=True)
        if not status[name]:
            break
    return status


# ---- analysis ----------------------------------------------------------------

def norm(s: str) -> str:
    return " ".join(s.split())


def scope(fb: dict, arm: str, edit: str) -> dict:
    """Shares of the original's checked sentences left unchanged in the edit: pointed at, and the rest."""
    pointed = set(fb["b_spans"] if arm == "B" else fb["e_spans"] if arm == "E" else [])
    body = norm(edit)
    out = {"pointed": [], "rest": []}
    for s in fb["sentences"]:
        key = "pointed" if s["span"] and tuple(s["span"]) in pointed else "rest"
        out[key].append(norm(s["text"]) in body)
    return {k: sum(v) / len(v) for k, v in out.items() if v}


def collect(ref: Path, client, analyzer, editors, judges) -> dict:
    paras = load(ref)
    fb = all_feedback(analyzer, paras)
    edits = {(p["id"], ed): texts_of(client, p, ed, fb) for p in paras for ed in editors}
    by = {p["id"]: p for p in paras}
    facts = {(pid, ed, arm, j): fact_of(client, by[pid], t[arm], j)
             for (pid, ed), t in edits.items() for arm in ARMS for j in judges}
    picks = {}
    for (pid, ed), t in edits.items():
        for j in judges:
            for o in (0, 1):
                c = {"id": pid, "editor": ed, "pair": "EB", "judge": j, "order": o}
                picks[(pid, ed, j, o)] = pick_of(client, c, t)
    return {"paras": paras, "fb": fb, "edits": edits, "facts": facts, "picks": picks}


def claims(b_minus_e) -> dict:
    if b_minus_e is None:
        return {"findings keep facts better": False, "pointing keeps facts as well": False}
    m, lo, hi = b_minus_e
    return {"findings keep facts better": hi < 0 and m <= -SMALLEST_DIFF,
            "pointing keeps facts as well": lo > -SMALLEST_DIFF}


def analyse(data: dict, analyzer, editors, judges, judges_done=None) -> dict:
    """Every outcome of the plan. ``judges_done``: the judges whose fact checks finished (default all)."""
    edits, facts, picks, fb = data["edits"], data["facts"], data["picks"], data["fb"]
    new = {p["id"] for p in data["paras"] if p.get("new")}
    fj = list(judges if judges_done is None else judges_done)
    res: dict = {"paragraphs": len(data["paras"]), "new": len(new), "fact_judges": fj, "all_judges": list(judges)}
    change = {a: {} for a in ARMS}
    counts = {a: Counter() for a in ARMS}
    checked = Counter()
    for (pid, ed), t in edits.items():
        for a in ARMS:
            if t[a] is None:
                continue
            checks = [facts[(pid, ed, a, j)] for j in fj]
            got = [c for c in checks if c]
            if not got:
                continue
            change[a][(pid, ed)] = float(ea.changes_content(checks))
            checked[a] += 1
            for c in got:
                for k in ("lost", "added", "changed"):
                    counts[a][k] += len(c[k]) / len(got)

    def paired(x, y, keep=lambda k: True):
        both = {k: x[k] - y[k] for k in x if k in y and keep(k)}
        return ea.cluster_boot(both) if both else None
    is_new = lambda k: k[0] in new
    res["content"] = {a: {"share": ea.cluster_boot(change[a]), "checked": checked[a],
                          **{k: round(counts[a][k] / checked[a], 3) if checked[a] else None
                             for k in ("lost", "added", "changed")}} for a in ARMS}
    res["B_minus_E"] = paired(change["B"], change["E"])
    res["B_minus_C_new"] = paired(change["B"], change["C"], is_new)
    res["B_minus_C_all"] = paired(change["B"], change["C"])
    res["E_minus_C"] = paired(change["E"], change["C"])
    full = {pid for pid, f in fb.items() if f["e_spans"] and set(f["e_spans"]) == set(f["b_spans"])}
    res["B_minus_E_same_sentences"] = paired(change["B"], change["E"], lambda k: k[0] in full)
    res["B_minus_E_other_sentences"] = paired(change["B"], change["E"], lambda k: k[0] not in full)
    shared = sum(len(set(f["e_spans"]) & set(f["b_spans"])) for f in fb.values())
    res["overlap"] = {"share_of_E_in_B": round(shared / max(1, sum(len(f["e_spans"]) for f in fb.values())), 3),
                      "paragraphs_same_sentences": len(full),
                      "mean_k": round(statistics.mean(len(f["b_spans"]) for f in fb.values()), 2) if fb else None}
    res["claims"] = claims(res["B_minus_E"]) if len(fj) == len(judges) else None
    # E against B, readability.
    oc = {(pid, ed, j): ea.outcome(picks[(pid, ed, j, 0)], picks[(pid, ed, j, 1)], "E", "B")
          for (pid, ed) in edits for j in judges}
    est = ea.cluster_boot(ea.unit_scores(oc))
    res["EB"] = {"estimate": est, "label": ea.label(est), "counts": dict(Counter(o for o in oc.values() if o)),
                 "missing": sum(o is None for o in oc.values())}
    # Scope, length, findings.
    sc = {a: {"pointed": {}, "rest": {}} for a in ARMS}
    for (pid, ed), t in edits.items():
        for a in ARMS:
            if t[a] is not None:
                for k, v in scope(fb[pid], a, t[a]).items():
                    sc[a][k][(pid, ed)] = v
    res["scope"] = {a: {k: ea.cluster_boot(v) for k, v in sc[a].items() if v} for a in ARMS}
    length, finds = {}, {}
    for a in ("A",) + ARMS:
        for ed in editors:
            rows = [(t["A"], t[a]) for (pid, e), t in edits.items() if e == ed and t[a] is not None]
            if not rows:
                continue
            name = "A" if a == "A" else f"{a} {ed}"
            length[name] = {"n": len(rows), "median_ratio": round(statistics.median(
                len(b.split()) / len(x.split()) for x, b in rows), 3),
                "over_budget": sum(len(b.split()) > ea.budget(x) for x, b in rows)}
            nf = [len(analyzer.check_text(b, "markdown", "p.md").findings) for _x, b in rows]
            finds[name] = {"median": statistics.median(nf), "mean": round(statistics.mean(nf), 2),
                           "none": round(sum(f == 0 for f in nf) / len(nf), 3)}
            if a == "A":
                break
    res["length"], res["findings"] = length, finds
    res["missing_edits"] = {a: sum(t[a] is None for (pid, _e), t in edits.items()
                                   if a == "E" or pid in new) for a in ARMS}
    # Per editor and per judge, deciding nothing.
    res["per_editor"] = {ed: {"B_minus_E": paired(change["B"], change["E"], lambda k, ed=ed: k[1] == ed),
                              "EB": ea.cluster_boot(ea.unit_scores({k: v for k, v in oc.items() if k[1] == ed})),
                              **{a: ea.cluster_boot({k: v for k, v in change[a].items() if k[1] == ed})
                                 for a in ARMS}} for ed in editors}
    per_judge = {}
    for j in judges:
        ch = {a: {(pid, ed): float(bool(c and (c["lost"] or c["changed"])))
                  for (pid, ed, aa, jj), c in facts.items() if aa == a and jj == j and c} for a in ARMS}
        per_judge[j] = {"B_minus_E": paired(ch["B"], ch["E"]),
                        "EB": ea.cluster_boot(ea.unit_scores({k: v for k, v in oc.items() if k[2] == j})),
                        **{a: ea.cluster_boot(ch[a]) for a in ARMS}}
    res["per_judge"] = per_judge
    return res


def fmt(est, pct: bool = False) -> str:
    if est is None:
        return "—"
    if pct:
        return "{:+.1f} [{:+.1f}, {:+.1f}]".format(*(100 * x for x in est))
    return "{:.3f} [{:.3f}, {:.3f}]".format(*est)


def render(res: dict, status: dict, calls: dict, draw: str = "") -> str:
    yn = {True: "yes", False: "no", None: "not decided"}
    lines = ["## Edit localization: readcost's findings (B) against pointing at the longest sentences (E)", ""]
    if draw:
        lines += [draw, ""]
    lines += [f"Paragraphs {res['paragraphs']} ({res['new']} new). Calls {calls.get('calls')} in the cache "
              f"(new this run {calls.get('new')}, served from cache {calls.get('cached')}). Phases: "
              + ", ".join(f"{k} {'done' if v else 'stopped'}" for k, v in status.items()), ""]
    if len(res["fact_judges"]) != len(res["all_judges"]):
        lines += [f"Fact checks finished for {', '.join(res['fact_judges'])} only; no claim is decided.", ""]
    lines += ["| Paired difference, share of edits changing content (points) | Estimate [95%] |", "| --- | --- |",
              f"| **B minus E, all paragraphs (primary)** | {fmt(res['B_minus_E'], True)} |",
              f"| B minus C, new paragraphs | {fmt(res['B_minus_C_new'], True)} |",
              f"| B minus C, all paragraphs | {fmt(res['B_minus_C_all'], True)} |",
              f"| E minus C, all paragraphs | {fmt(res['E_minus_C'], True)} |",
              f"| B minus E, paragraphs where E points at B's sentences | {fmt(res['B_minus_E_same_sentences'], True)} |",
              f"| B minus E, the other paragraphs | {fmt(res['B_minus_E_other_sentences'], True)} |", ""]
    cl = res["claims"]
    lines += ["| Claim | Holds |", "| --- | --- |",
              ("| readcost's findings keep facts better than pointing at the longest sentences | "
               f"{yn[cl['findings keep facts better'] if cl else None]} |"),
              ("| Pointing at the longest sentences keeps facts as well as readcost's findings | "
               f"{yn[cl['pointing keeps facts as well'] if cl else None]} |"), ""]
    rep = res["B_minus_C_new"]
    if rep is not None:
        lines += ["B minus C on the new paragraphs " + ("repeats the edit test's finding (upper bound under 0)."
                                                         if rep[2] < 0 else
                                                         "does not repeat the edit test's finding." if rep[1] <= 0 <= rep[2]
                                                         else "has C keeping facts better."), ""]
    lines += ["| Arm | Edits checked | Share changing content [95%] | Lost | Added | Changed |",
              "| --- | --- | --- | --- | --- | --- |"]
    for a in ARMS:
        c = res["content"][a]
        lines.append(f"| {a} | {c['checked']} | {fmt(c['share'])} | {c['lost']} | {c['added']} | {c['changed']} |")
    eb = res["EB"]
    lines += ["", "| Pair | Win rate of E [95%] | Label | Counts | Missing |", "| --- | --- | --- | --- | --- |",
              f"| E against B | {fmt(eb['estimate'])} | {eb['label']} | "
              + ", ".join(f"{k} {v}" for k, v in sorted(eb["counts"].items())) + f" | {eb['missing']} |", ""]
    ov = res["overlap"]
    lines += [f"Overlap: {ov['share_of_E_in_B']:.3f} of E's sentences are among B's; E points at exactly B's "
              f"sentences in {ov['paragraphs_same_sentences']} paragraphs; sentences named per paragraph, mean "
              f"{ov['mean_k']}. Missing edits: " + ", ".join(f"{a} {n}" for a, n in res["missing_edits"].items()) + ".",
              "", "| Arm | Sentences pointed at, unchanged [95%] | Other sentences, unchanged [95%] |",
              "| --- | --- | --- |"]
    for a in ARMS:
        s = res["scope"][a]
        lines.append(f"| {a} | {fmt(s.get('pointed'))} | {fmt(s.get('rest'))} |")
    lines += ["", "| Version | n | Words over original, median | Over budget | Findings, median | mean | none |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for name, ln in res["length"].items():
        f = res["findings"][name]
        lines.append(f"| {name} | {ln['n']} | {ln['median_ratio']} | {ln['over_budget']} | {f['median']} | "
                     f"{f['mean']} | {f['none']} |")
    lines += ["", "Per editor and per judge (decide nothing):", "",
              "| Who | B minus E (points) | E against B | Share changing, B | C | E |", "| --- | --- | --- | --- | --- | --- |"]
    for who, r in {**res["per_editor"], **res["per_judge"]}.items():
        lines.append(f"| {who} | {fmt(r['B_minus_E'], True)} | {fmt(r['EB'])} | {fmt(r['B'])} | {fmt(r['C'])} | "
                     f"{fmt(r['E'])} |")
    return "\n".join(lines) + "\n"


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
