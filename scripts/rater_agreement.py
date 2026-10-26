"""Agreement and majority-vote precision across all raters of the 210-finding sample.

    python3 -I scripts/rater_agreement.py ref/eval
"""
import collections
import glob
import json
import runpy
import sys
from pathlib import Path


def fleiss(table: list[list[int]]) -> float:
    """Fleiss' kappa; table[i][j] = raters putting item i in category j."""
    n = sum(table[0])
    N = len(table)
    p_j = [sum(row[j] for row in table) / (N * n) for j in range(len(table[0]))]
    P_i = [(sum(c * c for c in row) - n) / (n * (n - 1)) for row in table]
    P_bar, P_e = sum(P_i) / N, sum(p * p for p in p_j)
    return (P_bar - P_e) / (1 - P_e)


def cohen(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def main(corpus: Path) -> None:
    an = corpus / "analysis"
    raters = {"claude-opus (rater 1)": {i: v[0] for i, v in runpy.run_path(str(an / "labels.py"))["L"].items()}}
    raters["codex gpt-6.1-sol"] = {int(k): v["label"] for k, v in json.loads((an / "rater2-codex/labels2.json").read_text()).items()}
    for p in sorted(glob.glob(str(an / "ensemble-rate/labels-*.json"))):
        name = Path(p).stem.removeprefix("labels-").replace("__", "/")
        raters[name] = {int(k): v["label"] for k, v in json.loads(Path(p).read_text()).items()}
    items = sorted(set.intersection(*(set(r) for r in raters.values())))
    names = list(raters)
    cats = ["c", "d", "w"]
    table = [[sum(raters[r][i] == c for r in names) for c in cats] for i in items]
    ok_table = [[sum(raters[r][i] in "cd" for r in names), sum(raters[r][i] == "w" for r in names)] for i in items]
    out = {"items": len(items), "raters": len(names), "fleiss_cdw": round(fleiss(table), 3),
           "fleiss_ok_vs_wrong": round(fleiss(ok_table), 3), "per_rater": {}}
    majority = {}
    for i in items:
        votes = collections.Counter(raters[r][i] for r in names)
        ok = votes["c"] + votes["d"]
        majority[i] = "c" if votes["c"] > len(names) / 2 else ("ok" if ok > len(names) / 2 else "w")
    for r in names:
        others = [x for x in names if x != r]
        maj = []
        for i in items:
            ok = sum(raters[x][i] in "cd" for x in others)
            maj.append("ok" if ok > len(others) / 2 else "w")
        mine = ["ok" if raters[r][i] in "cd" else "w" for i in items]
        counts = collections.Counter(raters[r][i] for i in items)
        out["per_rater"][r] = {"c": counts["c"], "d": counts["d"], "w": counts["w"],
                               "kappa_vs_majority_of_others": round(cohen(mine, maj), 3)}
    out["majority"] = dict(collections.Counter(majority.values()))
    sample = [json.loads(x) for x in (corpus / "results/sample.jsonl").read_text().splitlines()]
    for run in ("results-main", "results-prec", "results-wp", "results-ctx"):
        f = corpus / run / "findings.jsonl"
        if not f.exists():
            continue
        keys = {(x["id"], x["feature"], x["sentence"]) for x in map(json.loads, f.read_text().splitlines())}
        kept = [i for i in items if (sample[i]["id"], sample[i]["feature"], sample[i]["sentence"]) in keys]
        ok = sum(majority[i] in ("c", "ok") for i in kept)
        out[f"kept_{run}"] = {"reported": len(kept), "majority_ok": ok, "share": round(ok / len(kept), 3)}
    by_feature = collections.defaultdict(lambda: [0, 0])
    for i in items:
        by_feature[sample[i]["feature"]][0] += 1
        by_feature[sample[i]["feature"]][1] += majority[i] in ("c", "ok")
    out["majority_ok_by_feature"] = {k: f"{v[1]}/{v[0]}" for k, v in sorted(by_feature.items())}
    (an / "ensemble-agreement.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
