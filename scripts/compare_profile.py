"""Compare two evaluation runs on the texts the default profile was not built from.

    python3 scripts/compare_profile.py ref/eval RUN_BEFORE RUN_AFTER

RUN_* are results directories from scripts/eval_corpus.py. For the held-out
half of the essay, docs and README sources (scripts/build_default_profile.py),
prints per category the share of texts that pass, the median and 95th
percentile cost index, and the long-dependency findings per 1,000 words; then
the same for every category, where no text was used to build the profile.
"""

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_default_profile import held_out_ids


def load(run: Path) -> dict[str, dict]:
    return {t["id"]: t for t in map(json.loads, (run / "texts.jsonl").read_text().splitlines())}


def row(texts: list[dict]) -> str:
    texts = [t for t in texts if t["words"] >= 40]
    if not texts:
        return "| - | - | - | - |"
    ci = sorted(t["cost_index"] for t in texts)
    words = sum(t["words"] for t in texts)
    dep = sum(t.get("counts", {}).get("long-dependency", 0) for t in texts)
    passing = sum(t["verdict"] == "pass" for t in texts) / len(texts)
    p95 = ci[min(len(ci) - 1, round(0.95 * (len(ci) - 1)))]
    return f"| {len(texts)} | {passing:.0%} | {statistics.median(ci):.1f} / {p95:.1f} | {1000 * dep / words:.2f} |"


def main() -> None:
    root, before, after = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    manifest = json.loads((root / "manifest.json").read_text())
    held = held_out_ids(manifest)
    category = {e["id"]: e["category"] for e in manifest["entries"]}
    runs = {"before": load(before), "after": load(after)}
    print("| Texts | Run | Texts (40+ words) | Pass | Cost index p50 / p95 | long-dependency per 1k words |")
    print("| --- | --- | --- | --- | --- | --- |")
    groups: dict[str, list[str]] = defaultdict(list)
    for tid, cat in category.items():
        if tid in held:
            groups[f"held-out {cat}"].append(tid)
        elif cat not in ("essay", "docs", "readme"):
            groups[cat].append(tid)
    for name in sorted(groups):
        for label, run in runs.items():
            print(f"| {name} | {label} {row([run[t] for t in groups[name] if t in run])}")


if __name__ == "__main__":
    main()
