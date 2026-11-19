"""Write src/readcost/data/rule_precision.json from the test across formats.

The figures readcost prints beside a finding come from the pre-registered
test in docs/evaluation.md, "Precision across formats": per rule, of the
findings drawn, how many at least 7 of 12 model raters called correct (an
editor would fix it) and how many they accepted (correct or defensible).
Labels are eval/breadth/labels/rater1..12.json; the sample is
eval/breadth/sample.jsonl, where one finding appears twice and counts once.

Usage: uv run python scripts/build_rule_precision.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src/readcost/data/rule_precision.json"
RATERS = [f"rater{n}" for n in range(1, 13)]


def labels(folder: Path) -> dict[str, dict[int, str]]:
    out = {}
    for r in RATERS:
        rows = json.loads((folder / f"{r}.json").read_text())
        out[r] = {int(x.get("id", x.get("i"))): (x.get("label") or "")[:1].lower() for x in rows}
    return out


def build(sample: list[dict], lab: dict[str, dict[int, str]]) -> dict:
    seen, rules = set(), {}
    for it in sample:
        if it["item"] != "finding" or it["i"] in seen:
            continue
        seen.add(it["i"])
        votes = [lab[r].get(it["i"], "") for r in RATERS]
        row = rules.setdefault(it["rule"], {"labelled": 0, "correct": 0, "accepted": 0})
        row["labelled"] += 1
        row["correct"] += sum(v == "c" for v in votes) * 2 > len(RATERS)
        row["accepted"] += sum(v in ("c", "d") for v in votes) * 2 > len(RATERS)
    return {
        "run": "breadth-precision",
        "raters": len(RATERS),
        "method": ("findings drawn from Markdown, reStructuredText and HTML docs, doc comments, commit "
                   "messages and pull request descriptions of repositories no rule was tuned on; correct "
                   "means at least 7 of 12 model raters said an editor would fix it, accepted means at "
                   "least 7 said correct or defensible (docs/evaluation.md, Precision across formats)"),
        "rules": dict(sorted(rules.items())),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="fail if the file differs from what would be written")
    args = ap.parse_args(argv)
    sample = [json.loads(x) for x in (ROOT / "eval/breadth/sample.jsonl").read_text().splitlines()]
    text = json.dumps(build(sample, labels(ROOT / "eval/breadth/labels")), indent=1) + "\n"
    if args.check:
        if OUT.read_text() != text:
            print(f"{OUT.relative_to(ROOT)} is out of date; run scripts/build_rule_precision.py", file=sys.stderr)
            return 1
        return 0
    OUT.write_text(text)
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
