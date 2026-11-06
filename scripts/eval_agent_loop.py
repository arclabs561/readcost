"""What happens when an agent edits text with readcost's feedback, round after round.

    uv run --group eval scripts/eval_agent_loop.py select REF OUT   # paragraphs to edit
    EVAL_OPENROUTER_API_KEY=... uv run --group eval scripts/eval_agent_loop.py run OUT
    uv run --group eval scripts/eval_agent_loop.py report OUT

A single check says what is wrong with a text once. An agent in a loop
(check, rewrite, check again) can do other things: converge, trade one
finding for another, oscillate, lengthen the text to dilute the rate, or
drift from the original facts. This runs that loop for each paragraph, model
and feedback style, for up to ROUNDS rounds or until readcost passes the
paragraph with no findings, records every round, and at the end asks a
separate judge model which facts the final text lost or added.

Feedback styles: "holds" is `-o agent` as it is now (rewrite where the
finding holds, with each rule's measured precision); "plain" is the older
wording (rewrite these sentences, no precision). Text stays under OUT, which
is outside the repository.
"""

import argparse
import hashlib
import json
import random
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from readcost import Analyzer, Config, report

ROUNDS = 6
MODELS = ["anthropic/claude-opus-5.5", "openai/gpt-6.1-terra-pro", "google/gemini-4-argon",
          "deepseek/deepseek-v4.1-flash", "mistralai/mistral-large-4-0"]
JUDGE = "moonshotai/kimi-k3.1-pro"
STYLES = ("holds", "plain")
REWRITE = """You are editing one paragraph of technical or expository writing.
A prose checker reported the problems below. Revise the paragraph to address
them. Keep every fact, number, name and claim; do not add new ones. Return the
whole revised paragraph.

Paragraph:
{text}

Checker feedback:
{feedback}"""
JUDGE_PROMPT = """Compare an original paragraph with a revision. List the
factual content (claims, numbers, names, conditions, causal links) that the
revision LOST or ADDED or CHANGED in meaning. Ignore wording, order and style.

Original:
{a}

Revision:
{b}"""
TEXT_SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"],
               "additionalProperties": False}
JUDGE_SCHEMA = {"type": "object", "properties": {
    "lost": {"type": "array", "items": {"type": "string"}},
    "added": {"type": "array", "items": {"type": "string"}},
    "changed": {"type": "array", "items": {"type": "string"}}},
    "required": ["lost", "added", "changed"], "additionalProperties": False}


def feedback(result, style: str) -> str:
    text = report.agent([result], feedback_link=False)
    if style == "plain":
        text = text.replace("Rewrite these sentences where the finding holds", "Rewrite these sentences")
        text = re.sub(r" \(raters accepted \d+ of \d+ such findings\)", "", text)
    return text


def measure(analyzer, text: str) -> dict:
    r = analyzer.check_text(text, "markdown", "p.md")
    return {"words": r.words, "verdict": r.verdict, "cost_index": round(r.cost_index, 2),
            "reading_seconds": r.reading_seconds, "ms_per_word": r.reading_ms_per_word,
            "findings": sorted((f.feature, f.excerpt) for f in r.findings), "result": r}


def loop(analyzer, text: str, rewrite, style: str, rounds: int = ROUNDS) -> list[dict]:
    """Round 0 is the original; each later round is one rewrite. Stops when a round has no findings."""
    out = []
    for k in range(rounds + 1):
        m = measure(analyzer, text)
        out.append({"round": k, "text": text, **{x: y for x, y in m.items() if x != "result"}})
        if not m["findings"] or k == rounds:
            break
        new = rewrite(text, feedback(m["result"], style))
        if not new or not new.strip():
            out[-1]["error"] = "empty rewrite"
            break
        text = new.strip()
    return out


def churn(rounds: list[dict]) -> dict:
    """Findings fixed, introduced, and come back after leaving, across a loop's rounds."""
    seen_gone: set = set()
    fixed = introduced = returned = 0
    for prev, cur in zip(rounds, rounds[1:]):
        a, b = set(map(tuple, prev["findings"])), set(map(tuple, cur["findings"]))
        fixed += len(a - b)
        introduced += len(b - a)
        returned += len(b & seen_gone)
        seen_gone |= a - b
    return {"fixed": fixed, "introduced": introduced, "returned": returned}


def select(ref: Path, out: Path, n: int, seed: int) -> None:
    analyzer = Analyzer(Config())
    manifest = json.loads((ref / "manifest.json").read_text())
    pool = []
    for e in manifest["entries"]:
        path = ref / e["path"] if "path" in e else None
        if path is None or not path.exists() or e.get("category") == "code":
            continue
        for para in path.read_text(encoding="utf-8", errors="ignore").split("\n\n"):
            para = " ".join(para.split())
            words = len(para.split())
            if 60 <= words <= 200 and not para.startswith(("#", "|", "```", "-", "*", ">")):
                pool.append((e["category"], e.get("source", ""), para))
    random.Random(seed).shuffle(pool)
    picked, per_cat = [], {}
    for cat, src, para in pool:
        if per_cat.get(cat, 0) >= n // 4 + 1 or len(picked) >= n:
            continue
        if len(analyzer.check_text(para, "markdown").findings) >= 2:
            picked.append({"id": hashlib.sha256(para.encode()).hexdigest()[:12], "category": cat,
                           "source": src, "text": para})
            per_cat[cat] = per_cat.get(cat, 0) + 1
    out.mkdir(parents=True, exist_ok=True)
    (out / "paragraphs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in picked))
    print(f"{len(picked)} paragraphs with 2+ findings: {per_cat}")


def run(out: Path, models: list[str], styles: list[str], rounds: int, workers: int = 1) -> None:
    import threading
    from concurrent.futures import ThreadPoolExecutor

    import rater_ensemble

    lock = threading.Lock()  # one spaCy pipeline and one output file shared by the threads

    class Locked:
        def __init__(self, inner):
            self.inner = inner

        def check_text(self, *a, **k):
            with lock:
                return self.inner.check_text(*a, **k)

    analyzer = Locked(Analyzer(Config()))
    paras = [json.loads(x) for x in (out / "paragraphs.jsonl").read_text().splitlines()]
    done_path = out / "loops.jsonl"
    done = {(d["id"], d["model"], d["style"]) for d in map(json.loads, done_path.read_text().splitlines())} \
        if done_path.exists() else set()
    for model in models:
        def rewrite(text, fb, model=model):
            data, _meta = rater_ensemble.ask(model, REWRITE.format(text=text, feedback=fb), TEXT_SCHEMA)
            return (data or {}).get("text", "")
        def one(p, style, model=model, rewrite=rewrite):
            trace = loop(analyzer, p["text"], rewrite, style, rounds)
            verdict, _ = rater_ensemble.ask(JUDGE, JUDGE_PROMPT.format(a=p["text"], b=trace[-1]["text"]),
                                            JUDGE_SCHEMA)
            row = {"id": p["id"], "category": p["category"], "model": model, "style": style,
                   "rounds": trace, "churn": churn(trace), "judge": verdict}
            with lock:
                with done_path.open("a") as f:
                    f.write(json.dumps(row) + "\n")
                print(model, style, p["id"], len(trace) - 1, "rounds", row["churn"], flush=True)

        todo = [(p, style) for style in styles for p in paras if (p["id"], model, style) not in done]
        with ThreadPoolExecutor(max(1, workers)) as pool:
            list(pool.map(lambda job: one(*job), todo))


def summarize(rows: list[dict]) -> list[dict]:
    out = []
    for (model, style) in sorted({(r["model"], r["style"]) for r in rows}):
        rs = [r for r in rows if r["model"] == model and r["style"] == style]
        first, last = [r["rounds"][0] for r in rs], [r["rounds"][-1] for r in rs]
        converged = [r for r in rs if not r["rounds"][-1]["findings"]]

        def ratio(key):
            vals = [b[key] / a[key] for a, b in zip(first, last) if a.get(key) and b.get(key) is not None]
            return round(statistics.median(vals), 3) if vals else None
        judged = [r["judge"] for r in rs if r.get("judge")]
        out.append({
            "model": model, "style": style, "loops": len(rs),
            "converged": len(converged),
            "median_rounds_to_converge": statistics.median([len(r["rounds"]) - 1 for r in converged]) if converged else None,
            "findings_first_median": statistics.median(len(a["findings"]) for a in first),
            "findings_last_median": statistics.median(len(b["findings"]) for b in last),
            "words_ratio_median": ratio("words"),
            "reading_seconds_ratio_median": ratio("reading_seconds"),
            "ms_per_word_ratio_median": ratio("ms_per_word"),
            "introduced_per_loop": round(statistics.mean(r["churn"]["introduced"] for r in rs), 2),
            "returned_per_loop": round(statistics.mean(r["churn"]["returned"] for r in rs), 2),
            "loops_losing_facts": sum(bool(j["lost"] or j["changed"]) for j in judged),
            "loops_adding_facts": sum(bool(j["added"]) for j in judged),
            "judged": len(judged),
        })
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select"); s.add_argument("ref", type=Path); s.add_argument("out", type=Path)
    s.add_argument("--n", type=int, default=40); s.add_argument("--seed", type=int, default=1)
    r = sub.add_parser("run"); r.add_argument("out", type=Path)
    r.add_argument("--models", default=",".join(MODELS)); r.add_argument("--styles", default=",".join(STYLES))
    r.add_argument("--rounds", type=int, default=ROUNDS)
    r.add_argument("--workers", type=int, default=1, help="paragraphs edited at once")
    p = sub.add_parser("report"); p.add_argument("out", type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "select":
        select(a.ref, a.out, a.n, a.seed)
    elif a.cmd == "run":
        run(a.out, a.models.split(","), a.styles.split(","), a.rounds, a.workers)
    else:
        rows = [json.loads(x) for x in (a.out / "loops.jsonl").read_text().splitlines()]
        print(json.dumps(summarize(rows), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
