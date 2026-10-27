"""Blind comparison of two versions of one rule, rated by the model ensemble.

    python3 scripts/blind_rule_compare.py sample ref/eval OLD_RUN NEW_RUN RULE OUT_CORPUS [--n 30]
    EVAL_OPENROUTER_API_KEY=... python3 -I scripts/rater_ensemble.py rate OUT_CORPUS OUT_CORPUS/labels
    python3 scripts/blind_rule_compare.py summary OUT_CORPUS

``sample`` draws n findings of RULE from the essay and docs categories of each
run (results directories from scripts/eval_corpus.py), shuffles them together
with a fixed seed, and writes OUT_CORPUS/results/sample.jsonl, the file
rater_ensemble.py rates. The raters see the rule, message, excerpt and
sentence, not which run a finding came from. ``summary`` counts, per run, the
findings a majority of the strict raters (not the two lenient ones) labelled
correct or defensible.
"""

import argparse
import glob
import json
import random
from pathlib import Path

LENIENT = {"meta-llama__llama-4-maverick", "minimax__minimax-m3"}


def sample(corpus: Path, old: Path, new: Path, rule: str, out: Path, n: int, seed: int) -> None:
    def findings(run: Path) -> list[dict]:
        rows = [json.loads(x) for x in (run / "findings.jsonl").read_text().splitlines()]
        return [f for f in rows if f["feature"] == rule and f["category"] in ("essay", "docs")]

    rng = random.Random(seed)
    pick = ([dict(f, arm="old") for f in rng.sample(findings(old), n)]
            + [dict(f, arm="new") for f in rng.sample(findings(new), n)])
    rng.shuffle(pick)
    (out / "results").mkdir(parents=True, exist_ok=True)
    (out / "labels").mkdir(exist_ok=True)
    (out / "results/sample.jsonl").write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in pick))
    print(len(pick), "findings ->", out / "results/sample.jsonl")


def summary(out: Path) -> None:
    rows = [json.loads(x) for x in (out / "results/sample.jsonl").read_text().splitlines()]
    labels = {Path(p).stem.removeprefix("labels-"): json.loads(Path(p).read_text())
              for p in glob.glob(str(out / "labels/labels-*.json"))}
    strict = sorted(m for m in labels if m not in LENIENT)
    print(f"{len(strict)} strict raters: {', '.join(strict)}")
    for arm in ("old", "new"):
        items = [str(i) for i, r in enumerate(rows) if r["arm"] == arm and all(str(i) in labels[m] for m in strict)]
        votes = [sum(labels[m][i]["label"] in "cd" for m in strict) for i in items]
        accepted = sum(v > len(strict) / 2 for v in votes)
        singles = [sum(labels[m][i]["label"] in "cd" for i in items) for m in strict]
        print(f"{arm}: {len(items)} findings rated by all; majority accepted {accepted}; "
              f"single raters {min(singles)} to {max(singles)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("task", choices=("sample", "summary"))
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    if a.task == "sample":
        corpus, old, new, rule, out = a.paths
        sample(Path(corpus), Path(old), Path(new), rule, Path(out), a.n, a.seed)
    else:
        summary(Path(a.paths[0]))
