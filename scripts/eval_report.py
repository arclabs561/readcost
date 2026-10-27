"""Regenerate the tables in docs/evaluation.md and show example diagnostics.

    python3 -I scripts/eval_report.py ref/eval RUN [--baseline RUN] [--examples 3] [--check]

RUN is a results directory written by scripts/eval_corpus.py (for example
ref/eval/results-HEAD). The script prints, as Markdown:

- cost-index percentiles and verdicts per category (the "Contexts" table);
- one row per source in the essay and docs categories (the respected-authors
  table), with the share of texts that do not pass;
- for the labelled sample: each rater's share of reported findings labelled
  correct or defensible, the eight-rater and ten-rater majorities, and
  Fleiss' kappa;
- example diagnostics: for each rule, a few findings from the run as readcost
  prints them, with the sentence and the raters' majority where the finding
  was labelled.

Rater labels live in eval/labels/*.json, keyed by a hash of the finding (text
id, rule, sentence), so they contain no source text and match any run that
reports the same finding. Two raters (Llama 4 Maverick, MiniMax M3) accept far
more than the rest; the eight-rater majority leaves them out.

--check turns the respected-authors table into a gate: it exits 1 when more
than 5% of essay and docs texts do not pass, or any one source has more than
25% not passing. Fetched text stays outside the repository (see
scripts/fetch_eval_corpus.py), so this gate runs locally, not in CI.
"""

import argparse
import collections
import hashlib
import json
import random
import statistics
import sys
from pathlib import Path

LABELS = Path(__file__).resolve().parent.parent / "eval" / "labels"
LENIENT = {"meta-llama--llama-4-maverick", "minimax--minimax-m3"}
PROSE = ("essay", "docs")


def key(f: dict) -> str:
    return hashlib.sha256(f"{f['id']}\t{f['feature']}\t{f['sentence']}".encode()).hexdigest()[:16]


def load_run(run: Path) -> tuple[list[dict], list[dict]]:
    texts = [json.loads(x) for x in (run / "texts.jsonl").read_text().splitlines()]
    findings = [json.loads(x) for x in (run / "findings.jsonl").read_text().splitlines()]
    return texts, findings


def load_labels() -> dict[str, dict[str, str]]:
    return {p.stem: {k: v["label"] for k, v in json.loads(p.read_text())["labels"].items()}
            for p in sorted(LABELS.glob("*.json"))}


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def fleiss(rows: list[list[int]]) -> float:
    n, N = sum(rows[0]), len(rows)
    p = [sum(r[j] for r in rows) / (N * n) for j in range(len(rows[0]))]
    P = [(sum(c * c for c in r) - n) / (n * (n - 1)) for r in rows]
    pe = sum(x * x for x in p)
    return (sum(P) / N - pe) / (1 - pe)


def contexts(texts: list[dict]) -> list[str]:
    out = ["| Category | Texts (40+ words) | p50 | p90 | p95 | p99 | Not passing |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    by = collections.defaultdict(list)
    for t in texts:
        by[t["category"]].append(t)
    for c, ts in sorted(by.items()):
        ci = [t["cost_index"] for t in ts if t["words"] >= 40]
        bad = sum(t["verdict"] != "pass" for t in ts)
        out.append(f"| {c} | {len(ci)} | {pct(ci, .5):.1f} | {pct(ci, .9):.1f} | {pct(ci, .95):.1f} | "
                   f"{pct(ci, .99):.1f} | {bad}/{len(ts)} ({100 * bad / len(ts):.1f}%) |")
    return out


def authors(texts: list[dict]) -> tuple[list[str], list[str]]:
    out = ["| Source | Category | Texts | Words | Findings per 1k | Median cost index | Max | Not passing |",
           "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    by = collections.defaultdict(list)
    for t in texts:
        if t["category"] in PROSE:
            by[(t["category"], t["source"])].append(t)
    failures = []
    total = bad_total = 0
    for (c, s), ts in sorted(by.items()):
        words = sum(t["words"] for t in ts)
        points = sum(t["points"] for t in ts)
        bad = sum(t["verdict"] != "pass" for t in ts)
        total += len(ts)
        bad_total += bad
        out.append(f"| {s} | {c} | {len(ts)} | {words} | {1000 * points / max(words, 1):.1f} | "
                   f"{statistics.median(t['cost_index'] for t in ts):.1f} | {max(t['cost_index'] for t in ts):.1f} | {bad} |")
        if bad > 0.25 * len(ts):
            failures.append(f"{s}: {bad} of {len(ts)} texts do not pass")
    if bad_total > 0.05 * total:
        failures.append(f"essay and docs: {bad_total} of {total} texts do not pass")
    return out, failures


def precision(findings: list[dict], labels: dict[str, dict[str, str]], name: str) -> list[str]:
    reported = {key(f) for f in findings}
    raters = sorted(labels)
    sample = sorted(set.intersection(*(set(v) for v in labels.values())))
    kept = [k for k in sample if k in reported]

    def majority(group: list[str], k: str) -> bool:
        return sum(labels[r][k] in "cd" for r in group) > len(group) / 2

    eight = [r for r in raters if r not in LENIENT]
    rows = [f"Run `{name}`: {len(kept)} of the {len(sample)} labelled findings are still reported.", "",
            "| Rater | Correct or defensible, of those reported |", "| --- | --- |"]
    for r in raters:
        ok = sum(labels[r][k] in "cd" for k in kept)
        rows.append(f"| {r}{' (lenient)' if r in LENIENT else ''} | {ok} ({100 * ok / max(len(kept), 1):.1f}%) |")
    for label, group in (("eight-rater majority", eight), ("ten-rater majority", raters)):
        ok = sum(majority(group, k) for k in kept)
        rows.append(f"| {label} | {ok} ({100 * ok / max(len(kept), 1):.1f}%) |")
    table = [[sum(labels[r][k] == c for r in raters) for c in "cdw"] for k in sample]
    table8 = [[sum(labels[r][k] == c for r in eight) for c in "cdw"] for k in sample]
    rows += ["", f"Fleiss' kappa (correct / defensible / wrong): {fleiss(table):.2f} over ten raters, "
                 f"{fleiss(table8):.2f} over eight."]
    return rows


def rule_precision(findings: list[dict], labels: dict[str, dict[str, str]], name: str) -> dict:
    """Per rule: labelled findings this run still reports, and how many the eight-rater majority accepts."""
    feature = {key(f): f["feature"] for f in findings}
    sample = set.intersection(*(set(v) for v in labels.values()))
    eight = [r for r in sorted(labels) if r not in LENIENT]
    rules: dict[str, dict[str, int]] = {}
    for k in sorted(sample & set(feature)):
        row = rules.setdefault(feature[k], {"labelled": 0, "accepted": 0})
        row["labelled"] += 1
        row["accepted"] += sum(labels[r][k] in "cd" for r in eight) > len(eight) / 2
    return {"run": name, "raters": len(eight),
            "method": "findings sampled from essays and documentation by well-regarded writers; "
                      "accepted means a majority of the raters labelled it correct or defensible",
            "rules": rules}


def examples(findings: list[dict], labels: dict[str, dict[str, str]], n: int) -> list[str]:
    eight = [r for r in labels if r not in LENIENT]
    rng = random.Random(1)
    by = collections.defaultdict(list)
    for f in findings:
        if f["category"] in PROSE:
            by[f["feature"]].append(f)
    out = []
    for feature in sorted(by):
        fs = by[feature]
        labelled = [f for f in fs if all(key(f) in labels[r] for r in eight)]
        pick = rng.sample(labelled, min(n, len(labelled)))
        pick += rng.sample([f for f in fs if f not in pick], min(n - len(pick), len(fs) - len(pick)))
        out += [f"### {feature} ({len(fs)} findings in essays and docs)", ""]
        for f in pick:
            verdict = ""
            if all(key(f) in labels[r] for r in eight):
                ok = sum(labels[r][key(f)] in "cd" for r in eight)
                verdict = f"  raters: {ok} of {len(eight)} call it correct or defensible"
            sentence = f["sentence"] if len(f["sentence"]) <= 220 else f["sentence"][:217] + "..."
            out += ["```text", f"{f['source']}:{f['line']}: {f['severity']}: [{feature}] {f['message']}",
                    f"  > {sentence}"] + ([verdict] if verdict else []) + ["```", ""]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus", type=Path)
    ap.add_argument("run", type=Path)
    ap.add_argument("--baseline", type=Path, help="an earlier run to compare precision against")
    ap.add_argument("--examples", type=int, default=3, help="example diagnostics per rule")
    ap.add_argument("--check", action="store_true", help="exit 1 if well-regarded writing is flagged")
    ap.add_argument("--rule-precision", type=Path, help="also write per-rule precision as JSON to this file")
    args = ap.parse_args()
    texts, findings = load_run(args.run)
    labels = load_labels()
    table, failures = authors(texts)
    out = ["## Contexts", ""] + contexts(texts) + ["", "## Respected authors", ""] + table + [""]
    out += ["## Precision on the labelled sample", ""]
    if args.baseline:
        out += precision(load_run(args.baseline)[1], labels, args.baseline.name) + [""]
    out += precision(findings, labels, args.run.name) + [""]
    if args.examples:
        out += ["## Example diagnostics", ""] + examples(findings, labels, args.examples)
    print("\n".join(out))
    if args.rule_precision:
        args.rule_precision.write_text(json.dumps(rule_precision(findings, labels, args.run.name), indent=1) + "\n")
    if args.check and failures:
        print("\n".join(f"check failed: {x}" for x in failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
