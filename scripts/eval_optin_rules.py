"""Should the opt-in rules stay? Precision and rate of each, on every corpus.

    readcost check ... -o json --info <every opt-in rule>  > CHECK.json   # over ALL.jsonl's paths
    uv run --group eval scripts/eval_optin_rules.py sample ALL.jsonl CHECK.json OUT
    EVAL_OPENROUTER_API_KEY=... uv run --group eval scripts/eval_optin_rules.py label OUT
    uv run --group eval scripts/eval_optin_rules.py summary OUT

Earlier samples were too small to judge the opt-in rules ("no hits in the
sample"). This takes every finding of each opt-in rule over the combined
corpus (scripts/build_all_manifest.py), samples up to N per rule spread
across categories in turn, and has the six strict raters label each item
blind with scripts/label_rulebench.py: the rule's definition and the
sentence, nothing else. The summary gives, per rule, findings per 1,000
words, the share of sampled findings a majority accepts with a Wilson 95%
interval, and that share by category. The sample, with its sentences, stays
under OUT, outside the repository.
"""

import collections
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import label_rulebench

OPT_IN = ["denominal-verb", "nominalization", "repeated-frame", "long-sentence", "center-embedding",
          "participial-clause", "undefined-acronym"]
PROMPT = label_rulebench.PROMPT.split("Rules:")[0] + """Rules:
- denominal-verb: a noun used as a verb where a plain verb exists ("bucket the requests" for "group").
- nominalization: an action turned into a noun with a light verb ("performs validation of" for "validates").
- repeated-frame: several sentences in a row built on the same opening frame ("This change ... This change ...").
- long-sentence: a sentence of more than 32 words.
- center-embedding: a clause nested inside a clause that is itself inside the middle of another clause.
- participial-clause: a present participle clause tacked onto a sentence ("..., highlighting what changed").
- undefined-acronym: an acronym used before, or without, being spelled out in the document.

Return JSON matching the schema: one entry per item, with its "i" unchanged."""


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def sample(manifest: Path, check: Path, out: Path, n: int, seed: int) -> None:
    cats = {}
    for line in manifest.read_text().splitlines():
        row = json.loads(line)
        cats[row["path"]] = row.get("category", "?")
    results = json.loads(check.read_text())
    words = collections.Counter()
    found = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in results:
        cat = cats.get(r["path"], "?")
        words[cat] += r["words"]
        for f in r["findings"]:
            if f["feature"] in OPT_IN:
                found[f["feature"]][cat].append({"rule": f["feature"], "text": f["sentence"], "category": cat,
                                                 "excerpt": f["excerpt"], "path": r["path"]})
    rng = random.Random(seed)
    items = []
    for rule in OPT_IN:
        pools = {c: rng.sample(v, len(v)) for c, v in found[rule].items()}
        picked = []
        while len(picked) < n and any(pools.values()):
            for c in sorted(pools):  # one per category in turn, so no category dominates
                if pools[c] and len(picked) < n:
                    picked.append(pools[c].pop())
        items += picked
    out.mkdir(parents=True, exist_ok=True)
    rng.shuffle(items)  # raters see rules mixed, not in blocks
    (out / "items.jsonl").write_text("".join(json.dumps(x) + "\n" for x in items))
    counts = {rule: sum(len(v) for v in found[rule].values()) for rule in OPT_IN}
    (out / "counts.json").write_text(json.dumps({"words": sum(words.values()), "findings": counts,
                                                 "by_category": {r: {c: len(v) for c, v in found[r].items()}
                                                                 for r in OPT_IN}}, indent=1))
    print(f"{len(items)} items; findings per rule: {counts}")


def summary(out: Path) -> list[dict]:
    items = [json.loads(x) for x in (out / "items.jsonl").read_text().splitlines()]
    counts = json.loads((out / "counts.json").read_text())
    labels = {p.stem: json.loads(p.read_text()) for p in out.glob("labels-*.json")}
    rows = []
    for rule in OPT_IN:
        idx = [i for i, it in enumerate(items) if it["rule"] == rule]
        majority, by_cat = [], collections.defaultdict(list)
        for i in idx:
            votes = [labels[m][str(i)]["flag"] for m in labels if str(i) in labels[m]]
            if len(votes) < len(labels) or not votes:
                continue
            yes = sum(v == "yes" for v in votes) > len(votes) / 2
            majority.append(yes)
            by_cat[items[i]["category"]].append(yes)
        k, n = sum(majority), len(majority)
        lo, hi = wilson(k, n)
        rows.append({"rule": rule, "findings": counts["findings"][rule],
                     "per_1k_words": round(1000 * counts["findings"][rule] / counts["words"], 3),
                     "labelled": n, "accepted": k, "share": round(k / n, 3) if n else None,
                     "wilson_95": [round(lo, 3), round(hi, 3)],
                     "by_category": {c: f"{sum(v)}/{len(v)}" for c, v in sorted(by_cat.items())}})
    return rows


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "sample":
        sample(Path(argv[1]), Path(argv[2]), Path(argv[3]), int(argv[4]) if len(argv) > 4 else 40, 1)
    elif cmd == "label":
        label_rulebench.label(Path(argv[1]) / "items.jsonl", Path(argv[1]), PROMPT)
    else:
        print(json.dumps(summary(Path(argv[1])), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
