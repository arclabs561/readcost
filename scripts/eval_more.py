"""Run readcost over the corpora added after eval_broad.py and write aggregate comparisons.

    PYTHONPATH=src python3 scripts/eval_more.py REF/broad            # needs scipy

Reads every ``REF/broad/*/manifest.json`` except those evaluated elsewhere
(``--exclude``: by default arxiv, readmes and expert-lay, which
scripts/eval_broad.py covers, and people and ai, which have their own
evaluation), scores each
text once with ``Config()`` defaults, and caches the per-text numbers in
``REF/broad/results-more/texts.jsonl`` by content hash (scoring reuses
scripts/eval_broad.py). Writes ``summary.json`` and ``summary.md`` there,
aggregates only (no text):

- per category and per source: findings per 1,000 words per rule, cost index
  percentiles over texts of 150+ words, median predicted ms per word and words
  per sentence, verdict shares;
- for every category with two or more sources of at least five texts of
  ``--min-words`` or more: medians per source and a Kruskal-Wallis test (a
  Mann-Whitney U test for two sources); Stack Exchange answers are also split
  by vote group (high, low) and by site, man pages by system, and Rust RFCs
  by start year;
- Stack Exchange revision pairs (category ``se-revision-pair``): per measure,
  the median paired difference edited minus original, the share of pairs where
  the edited text is lower and a two-sided Wilcoxon signed-rank test, pooled
  and per site; ``se_pairs.jsonl`` lists each pair's differences (ids and
  numbers only).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from scipy.stats import kruskal, mannwhitneyu

from readcost.config import Config
from readcost.engine import Analyzer
from readcost.features import FEATURES


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


eval_broad = _load("eval_broad")
eval_corpus = eval_broad.eval_corpus
BASE = eval_broad.BASE
EXTRA = ("group", "site", "repo", "number", "start_date", "page_type", "score", "pair_id", "role")
MIN_GROUP = 5


def summarize(rs: list[dict], features: list[str]) -> dict:
    s = eval_corpus.summarize(rs, features)
    long_rs = [r for r in rs if r["words"] >= eval_broad.MIN_WORDS]
    ms = [r["ms_per_word"] for r in long_rs if r["ms_per_word"] is not None]
    wps = [r["words_per_sentence"] for r in long_rs if r["words_per_sentence"]]
    s["ms_per_word_p50"] = round(statistics.median(ms), 1) if ms else None
    s["words_per_sentence_p50"] = round(statistics.median(wps), 1) if wps else None
    return s


def compare(groups: dict[str, list[dict]], measures: list[str]) -> list[dict] | None:
    groups = {g: rs for g, rs in groups.items() if len(rs) >= MIN_GROUP}
    if len(groups) < 2:
        return None
    return eval_broad.group_table(groups, measures, mannwhitneyu if len(groups) == 2 else kruskal)


def rust_era(row: dict) -> str | None:
    """Rust RFCs by start year: 2014-2015, 2016-2018, 2019 on; None for other design docs."""
    year = int((row.get("start_date") or "0")[:4])
    if row["source"] != "rust" or not year:
        return None
    return "2014-2015" if year <= 2015 else "2016-2018" if year <= 2018 else "2019-2026"


def revision_pairs(rows: list[dict], measures: list[str]) -> tuple[list[dict], list[dict]]:
    """Edited minus original per measure, and each pair's differences."""
    as_roles = [r | {"role": "expert" if r["role"] == "original" else "lay"} for r in rows]
    table = [{"measure": t["measure"], "pairs": t["pairs"], "original_median": t["expert_median"],
              "edited_median": t["lay_median"], "median_diff": t["median_diff"], "edited_lower": t["lay_lower"],
              "same": t["same"], "p": t["p"]} for t in eval_broad.pair_table(as_roles, measures)]
    by_pair: dict[str, dict] = defaultdict(dict)
    for r in rows:
        by_pair[r["pair_id"]][r["role"]] = r
    per_pair = []
    for pid, p in sorted(by_pair.items()):
        if "original" in p and "edited" in p:
            d = {"pair_id": pid, "site": p["edited"]["source"], "score": p["edited"].get("score")}
            for m in BASE:
                a, b = eval_broad.value(p["edited"], m), eval_broad.value(p["original"], m)
                d[m] = None if a is None or b is None else round(a - b, 4)
            per_pair.append(d)
    return table, per_pair


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--exclude", default="arxiv,readmes,expert-lay,people,ai")
    ap.add_argument("--min-words", type=int, default=100)
    args = ap.parse_args()
    root: Path = args.root
    out = args.out or root / "results-more"
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    exclude = set(args.exclude.split(","))
    cache_path = out / "texts.jsonl"
    cache = {}
    if cache_path.exists():
        for line in cache_path.read_text().splitlines():
            r = json.loads(line)
            cache[(r["id"], r["sha256"])] = r

    analyzer = Analyzer(config=Config())
    features = [f for f in FEATURES if f in analyzer.enabled]
    measures = list(BASE) + features
    rows: list[dict] = []
    counts: dict[str, dict] = {}
    for mf in sorted(root.glob("*/manifest.json")):
        sub = mf.parent.name
        if sub in exclude:
            continue
        entries = json.loads(mf.read_text())["entries"]
        for i, e in enumerate(entries):
            key = (e["id"], e["sha256"])
            row = cache[key] if key in cache else eval_broad.score(analyzer, root, sub, e)
            rows.append(row | {k: e[k] for k in EXTRA if k in e})
            c = counts.setdefault(f"{e['category']}/{e['source']}", {"texts": 0, "licences": {}})
            c["texts"] += 1
            c["licences"][e["license"]] = c["licences"].get(e["license"], 0) + 1
            if (i + 1) % 100 == 0:
                print(f"{sub}: {i + 1}/{len(entries)}", file=sys.stderr)
        cache_path.write_text("".join(json.dumps(r) + "\n" for r in rows))

    by_cat: dict[str, list[dict]] = defaultdict(list)
    by_src: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
        by_src[f"{r['category']}/{r['source']}"].append(r)
    summary: dict = {"readcost": eval_corpus.code_version(), "settings": "Config() defaults",
                     "min_words_groups": args.min_words, "features": features, "item_counts": counts,
                     "by_category": {k: summarize(v, features) for k, v in sorted(by_cat.items())},
                     "by_source": {k: summarize(v, features) for k, v in sorted(by_src.items())},
                     "groups": {}}

    def long_enough(rs):
        return [r for r in rs if r["words"] >= args.min_words]

    for cat, rs in sorted(by_cat.items()):
        if cat == "se-revision-pair":
            continue
        rs = long_enough(rs)
        splits = {"source": lambda r: r["source"]}
        if cat == "se-answer":
            splits = {"vote group": lambda r: r["group"], "site": lambda r: r["site"]}
        elif cat == "man-page":
            splits |= {"system": lambda r: r["source"].split("/")[0]}
        elif cat == "design-doc":
            splits |= {"Rust RFC start year": rust_era}
        for label, key in splits.items():
            groups: dict[str, list[dict]] = defaultdict(list)
            for r in rs:
                if (k := key(r)) is not None:
                    groups[k].append(r)
            if (tab := compare(dict(sorted(groups.items())), measures)) is not None:
                summary["groups"][f"{cat} by {label}"] = tab

    pair_rows = by_cat.get("se-revision-pair", [])
    if pair_rows:
        table, per_pair = revision_pairs(pair_rows, measures)
        summary["se_revision_pairs"] = table
        summary["se_revision_pairs_by_site"] = {
            s: revision_pairs([r for r in pair_rows if r["source"] == s], list(BASE))[0]
            for s in sorted({r["source"] for r in pair_rows})}
        (out / "se_pairs.jsonl").write_text("".join(json.dumps(d) + "\n" for d in per_pair))

    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")

    md_table = eval_broad.md_table
    md = [(f"readcost {summary['readcost']}; Config() defaults. Percentiles use texts of "
           f"{eval_broad.MIN_WORDS}+ words; group comparisons use texts of {args.min_words}+ words."), ""]
    md += ["## Items", ""]
    md += md_table([{"source": k, "texts": v["texts"],
                     "licences": ", ".join(f"{a} {b}" for a, b in v["licences"].items())}
                    for k, v in sorted(counts.items())], ["source", "texts", "licences"])
    md += ["", "## By category", "", eval_corpus.markdown_table(summary["by_category"], features, "category"), "",
           "## By source", "", eval_corpus.markdown_table(summary["by_source"], features, "source"), ""]
    md += ["Median ms/word and words/sentence (texts of 150+ words):", ""]
    md += md_table([{"group": k, "ms/word": v["ms_per_word_p50"], "words/sentence": v["words_per_sentence_p50"]}
                    for k, v in {**summary["by_category"], **summary["by_source"]}.items()],
                   ["group", "ms/word", "words/sentence"])
    for label, tab in summary["groups"].items():
        cols = ["measure"] + [k for k in tab[0] if k not in ("measure", "p")] + ["p"]
        md += ["", f"## {label} (medians; Mann-Whitney U for two groups, else Kruskal-Wallis)", ""]
        md += md_table(tab, cols)
    pcols = ["measure", "pairs", "original_median", "edited_median", "median_diff", "edited_lower", "same", "p"]
    if "se_revision_pairs" in summary:
        md += ["", "## Stack Exchange revision pairs (edited minus original, Wilcoxon signed-rank)", ""]
        md += md_table(summary["se_revision_pairs"], pcols, ("edited_lower", "same"))
        for site, tab in summary["se_revision_pairs_by_site"].items():
            md += ["", f"### {site}", ""] + md_table(tab, pcols, ("edited_lower", "same"))
    abbrev = eval_corpus.ABBREV
    md += ["", "Rule abbreviations: " + ", ".join(f"{abbrev.get(f, f)} = {f}" for f in features) + "."]
    (out / "summary.md").write_text("\n".join(md) + "\n")
    print(f"{len(rows)} texts -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
