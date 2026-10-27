"""Run readcost over the evaluation corpus and summarize the distributions.

    python3 scripts/eval_corpus.py ref/eval
    python3 scripts/eval_corpus.py CORPUS --sample 200 --seed 1   # findings to label

Reads ``CORPUS/manifest.json`` (written by scripts/fetch_eval_corpus.py) and
writes, under ``CORPUS/results/`` unless ``--out`` says otherwise:

- ``texts.jsonl``: one line per text with words, points, cost index, verdict
  and finding counts.
- ``findings.jsonl``: every finding, with its sentence.
- ``summary.json`` and ``summary.md``: per-category and per-source tables.
- ``sample.jsonl`` with ``--sample``: findings drawn from the essay and docs
  categories, stratified by feature and then source, for hand labeling.

Runs offline once the corpus is fetched. The settings are readcost's
defaults, built explicitly so that no readcost.toml on the way up from the
working directory changes them; source files are read with
``comments = "all"`` so that ``#`` and ``//`` comments count as well as doc
comments. Output order and sampling are deterministic for a given corpus,
code version and seed.
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import readcost
from readcost.config import Config
from readcost.engine import Analyzer
from readcost.features import FEATURES

MIN_WORDS = 150                       # texts shorter than this are left out of cost-index percentiles
LABEL_CATEGORIES = ("essay", "docs")  # where --sample draws from
VERDICTS = ("pass", "advise", "block")


def percentile(values: list[float], q: float) -> float:
    """Linear interpolation between closest ranks (numpy's default)."""
    if not values:
        return float("nan")
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def code_version() -> str:
    """Short SHA of the checkout that the imported readcost package lives in."""
    try:
        root = Path(readcost.__file__).resolve().parent
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                             check=False, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def summarize(rows: list[dict], features: list[str]) -> dict:
    words = sum(r["words"] for r in rows)
    long_rows = [r for r in rows if r["words"] >= MIN_WORDS]
    ci = [r["cost_index"] for r in long_rows]
    verdicts = Counter(r["verdict"] for r in rows)
    counts = Counter()
    for r in rows:
        counts.update(r["counts"])
    return {
        "texts": len(rows),
        "words": words,
        "texts_150": len(long_rows),
        "cost_index_p50": round(percentile(ci, 0.5), 1) if ci else None,
        "cost_index_p90": round(percentile(ci, 0.9), 1) if ci else None,
        "cost_index_max": round(max(ci), 1) if ci else None,
        "verdict_share": {v: round(verdicts[v] / len(rows), 3) if rows else 0.0 for v in VERDICTS},
        "findings": sum(counts.values()),
        "per_1k": {f: round(1000 * counts[f] / words, 2) if words else 0.0 for f in features},
    }


ABBREV = {
    "stacked-nouns": "stack", "long-dependency": "dep", "inanimate-subject": "inan",
    "denominal-verb": "denom", "reduced-object-relative": "rel", "hyphen-compound": "hyph",
    "inline-list": "list", "long-sentence": "long",
}


def markdown_table(groups: dict[str, dict], features: list[str], label: str) -> str:
    head = [label, "texts", "words", "n>=150", "CI p50", "CI p90", "CI max", "pass", "advise", "block"]
    head += [ABBREV.get(f, f) for f in features]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]

    def fmt(x):
        return "-" if x is None else f"{x:g}" if isinstance(x, float) else str(x)

    for name, s in groups.items():
        cells = [name, s["texts"], s["words"], s["texts_150"], s["cost_index_p50"], s["cost_index_p90"],
                 s["cost_index_max"]]
        cells += [f"{100 * s['verdict_share'][v]:.0f}%" for v in VERDICTS]
        cells += [f"{s['per_1k'][f]:.2f}" for f in features]
        lines.append("| " + " | ".join(fmt(c) for c in cells) + " |")
    return "\n".join(lines)


def stratified_sample(findings: list[dict], n: int, seed: int) -> list[dict]:
    """Spread ``n`` draws evenly over features, then over sources within one.

    Each feature gets ``n / features`` draws (more for others when one runs
    short); within a feature, sources are visited round-robin so that one
    prolific source does not fill the quota.
    """
    rng = random.Random(seed)
    by_feature: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for f in findings:
        by_feature[f["feature"]][f["source"]].append(f)
    for sources in by_feature.values():
        for items in sources.values():
            rng.shuffle(items)
    feats = sorted(by_feature)
    avail = {f: sum(len(v) for v in by_feature[f].values()) for f in feats}
    quota = {f: 0 for f in feats}
    left = n
    while left > 0 and any(quota[f] < avail[f] for f in feats):
        for f in feats:
            if left and quota[f] < avail[f]:
                quota[f] += 1
                left -= 1
    out = []
    for f in feats:
        queues = {s: list(v) for s, v in sorted(by_feature[f].items())}
        picked = 0
        while picked < quota[f]:
            for s in list(queues):
                if picked >= quota[f]:
                    break
                if queues[s]:
                    out.append(queues[s].pop())
                    picked += 1
                else:
                    del queues[s]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--sample", type=int, default=0, help="findings to draw for labeling")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--category", default="", help="comma-separated categories to run (default all)")
    ap.add_argument("--code-label", help="readcost version to record when it is not a git checkout")
    ap.add_argument("--enable", default="", help="comma-separated opt-in rules to turn on")
    args = ap.parse_args()
    corpus: Path = args.corpus
    out = args.out or corpus / "results"
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((corpus / "manifest.json").read_text())
    wanted = {c for c in args.category.split(",") if c}
    entries = [e for e in manifest["entries"] if not wanted or e["category"] in wanted]

    enable = [f for f in args.enable.split(",") if f]
    prose = Analyzer(config=Config(enable=list(enable)))
    code = Analyzer(config=Config(comments="all", enable=list(enable)))
    code._nlp = prose.nlp  # share the loaded model
    features = [f for f in FEATURES if f in prose.enabled]

    rows: list[dict] = []
    findings: list[dict] = []
    for i, e in enumerate(entries):
        path = Path(e["path"]) if Path(e["path"]).is_absolute() else corpus / e["path"]
        text = path.read_text(encoding="utf-8", errors="replace")
        analyzer = code if e["format"] == "source" else prose
        # The file name decides the source language, so pass the real path.
        r = analyzer.check_text(text, e["format"], str(path))
        row = {"id": e["id"], "category": e["category"], "source": e["source"], "url": e["url"],
               "words": r.words, "sentences": r.sentences, "points": r.points,
               "cost_index": round(r.cost_index, 2), "verdict": r.verdict, "counts": r.counts(),
               "metrics": r.metrics}
        rows.append(row)
        for f in r.findings:
            findings.append({"id": e["id"], "category": e["category"], "source": e["source"], "url": e["url"],
                             "line": f.line, "feature": f.feature, "severity": f.severity,
                             "message": f.message, "excerpt": f.excerpt, "sentence": f.sentence})
        if (i + 1) % 100 == 0:
            print(f"{i + 1}/{len(entries)}", file=sys.stderr)

    by_cat: dict[str, list[dict]] = defaultdict(list)
    by_src: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
        by_src[f"{r['category']}/{r['source']}"].append(r)
    summary = {
        "readcost": args.code_label or code_version(),
        "settings": "Config() defaults" + (f" plus {', '.join(enable)}" if enable else "")
                    + "; source files with comments='all'",
        "min_words_for_percentiles": MIN_WORDS,
        "features": features,
        "all": summarize(rows, features),
        "by_category": {k: summarize(v, features) for k, v in sorted(by_cat.items())},
        "by_source": {k: summarize(v, features) for k, v in sorted(by_src.items())},
    }
    (out / "texts.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    (out / "findings.jsonl").write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in findings))
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    legend = ("Columns: CI is the cost index (weighted findings per 1,000 words) over texts of "
              f"{MIN_WORDS}+ words; verdict shares are over all texts; feature columns are findings "
              "per 1,000 words (" + ", ".join(f"{ABBREV.get(f, f)} = {f}" for f in features) + ").")
    md = [f"readcost {summary['readcost']}; {summary['settings']}.", "", legend, "",
          "## By category", "", markdown_table(summary["by_category"] | {"all": summary["all"]}, features, "category"),
          "", "## By source", "", markdown_table(summary["by_source"], features, "source"), ""]
    (out / "summary.md").write_text("\n".join(md))
    if args.sample:
        pool = [f for f in findings if f["category"] in LABEL_CATEGORIES and not f["source"].startswith(
            ("cpython", "rust-std"))]
        sample = stratified_sample(pool, args.sample, args.seed)
        (out / "sample.jsonl").write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in sample))
        print(f"sampled {len(sample)} findings -> {out / 'sample.jsonl'}", file=sys.stderr)
    print(f"{len(rows)} texts, {summary['all']['words']} words, {len(findings)} findings -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
