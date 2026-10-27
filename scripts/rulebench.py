"""Score readcost's default rules on the curated per-rule benchmark in eval/rulebench/.

    python3 scripts/rulebench.py                # per-rule table
    python3 scripts/rulebench.py --misses       # also list every item the rule gets wrong
    python3 scripts/rulebench.py --json         # machine-readable scores

eval/rulebench/rulebench.jsonl holds references to real sentences, one JSON
object per line; scripts/fetch_rulebench.py downloads the sources and writes
the same items with their text to a directory outside the repository, which
this script reads (``--bench``):

- ``rule``: the rule the item tests;
- ``sha256``: of the sentence with whitespace collapsed; ``text`` is stored
  only for this repository's own sentences and added by the fetch script;
- ``expected``: ``fire`` when the rule should report the sentence and the
  finding would help an editor, ``no-fire`` when it should stay silent (a
  false-positive trap, often a sentence an earlier version reported);
- ``source`` and ``licence``: where the sentence comes from (PEPs, SQLite
  docs, the Go blog, the Rust book, Django docs, GOV.UK guidance, a few
  essays); the text itself is not kept in the repository;
- ``labelled_by``: ``raters`` when the label is the majority of the strict
  model raters in docs/evaluation.md (``votes`` gives the count),
  ``self`` when one maintainer labelled it, with the reasoning in ``reason``.

Each item is checked alone with readcost's default settings. For each rule
the script counts true positives (expected fire, fires), false negatives,
true negatives (expected no-fire, silent) and false positives, and prints
precision, recall, and the share of traps it stays silent on. A rule firing
on a sentence for some other rule's item counts only toward that item's
rule. The numbers describe the current code against this bench; they are
not a quality gate yet.
"""

import argparse
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "eval" / "rulebench" / "rulebench.jsonl"


def load(path: Path) -> list[dict]:
    items = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    for i, it in enumerate(items):
        missing = {"rule", "text", "expected", "source", "licence", "reason", "labelled_by"} - it.keys()
        if missing or it["expected"] not in ("fire", "no-fire"):
            raise ValueError(f"item {i + 1}: missing {sorted(missing)} or bad expected {it.get('expected')!r}")
    return items


def score(items: list[dict]) -> dict[str, dict]:
    from readcost import Analyzer, Config

    a = Analyzer(Config())
    out: dict[str, dict] = {}
    for it in items:
        fired = it["rule"] in {f.feature for f in a.check_text(it["text"], "markdown").findings}
        s = out.setdefault(it["rule"], {"tp": 0, "fn": 0, "tn": 0, "fp": 0, "misses": []})
        if it["expected"] == "fire":
            s["tp" if fired else "fn"] += 1
        else:
            s["fp" if fired else "tn"] += 1
        if fired != (it["expected"] == "fire"):
            s["misses"].append(it)
    for s in out.values():
        s["precision"] = s["tp"] / (s["tp"] + s["fp"]) if s["tp"] + s["fp"] else None
        s["recall"] = s["tp"] / (s["tp"] + s["fn"]) if s["tp"] + s["fn"] else None
        s["silent_on_traps"] = s["tn"] / (s["tn"] + s["fp"]) if s["tn"] + s["fp"] else None
    return out


def table(scores: dict[str, dict]) -> str:
    def pct(x):
        return "-" if x is None else f"{x:.0%}"

    lines = ["| Rule | Items | Fire / no-fire | TP | FN | TN | FP | Precision | Recall | Silent on traps |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for rule, s in sorted(scores.items()):
        n_fire, n_quiet = s["tp"] + s["fn"], s["tn"] + s["fp"]
        lines.append(f"| {rule} | {n_fire + n_quiet} | {n_fire} / {n_quiet} | {s['tp']} | {s['fn']} | {s['tn']} | "
                     f"{s['fp']} | {pct(s['precision'])} | {pct(s['recall'])} | {pct(s['silent_on_traps'])} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bench", type=Path, required=True,
                    help="rulebench.jsonl written by scripts/fetch_rulebench.py (with the sentences)")
    ap.add_argument("--misses", action="store_true", help="list the items each rule gets wrong")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    scores = score(load(args.bench))
    if args.json:
        print(json.dumps({r: {k: v for k, v in s.items() if k != "misses"} for r, s in scores.items()}, indent=1))
        return 0
    print(table(scores))
    if args.misses:
        for rule, s in sorted(scores.items()):
            for it in s["misses"]:
                want = "should fire" if it["expected"] == "fire" else "should not fire"
                print(f"\n{rule}: {want} ({it['labelled_by']}): {it['text']}\n  reason: {it['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
