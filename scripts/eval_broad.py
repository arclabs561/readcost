"""Run readcost over the broader corpora and write aggregate comparisons.

    python3 scripts/fetch_arxiv.py REF/broad/arxiv
    PYTHONPATH=src python3 scripts/fetch_github_readmes.py REF/broad/readmes
    python3 scripts/fetch_expert_lay.py REF/broad/expert-lay
    python3 scripts/eval_broad.py REF/broad

Reads every ``REF/broad/*/manifest.json`` and scores each text once with
readcost's default settings (``Config()``), caching the per-text numbers in
``REF/broad/results/texts.jsonl`` by content hash. Writes, under
``REF/broad/results/``, ``summary.json`` and ``summary.md`` with aggregates
only (no text):

- per category and per source: findings per 1,000 words per rule, cost index
  percentiles, median predicted ms per word, verdict shares (as in
  scripts/eval_corpus.py);
- expert and lay pairs (categories ``summary-pair`` and ``wiki-pair``): for
  each measure, the median paired difference lay minus expert, the share of
  pairs where the lay text is lower, and a two-sided Wilcoxon signed-rank test
  with each pair as one unit; words per sentence and mean word length are
  reported alongside, since length and vocabulary are confounds;
- GOV.UK guides against detailed guides (unpaired): medians and a two-sided
  Mann-Whitney U test;
- READMEs: Spearman correlation of each measure with stars (the same as with
  log stars, since Spearman uses ranks), and a Kruskal-Wallis test across
  languages with per-language medians;
- arXiv: Kruskal-Wallis across fields for abstracts and introductions, and a
  paired Wilcoxon test of introduction minus abstract over papers with both.

Per-text measures are computed per text; texts under 150 words are left out
of every comparison except the pair tests, where both sides passed the
fetcher's length floor. Needs scipy.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from scipy.stats import kruskal, mannwhitneyu, spearmanr, wilcoxon

from readcost.config import Config
from readcost.engine import Analyzer
from readcost.extract import CODE, extract
from readcost.features import FEATURES

_spec = importlib.util.spec_from_file_location("eval_corpus", Path(__file__).with_name("eval_corpus.py"))
eval_corpus = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eval_corpus)

MIN_WORDS = 150
PAIR_CATEGORIES = ("summary-pair", "wiki-pair")
BASE = ("findings_per_1k", "cost_index", "ms_per_word", "words_per_sentence", "mean_word_length", "words")


def mean_word_length(text: str, fmt: str, path: str) -> float | None:
    """Mean letters per word over the prose readcost reads (code stand-ins left out)."""
    ws = [w for seg in extract(text, path, fmt) for w in re.findall(r"[A-Za-z]+", seg.text) if w != CODE]
    return sum(map(len, ws)) / len(ws) if ws else None


def score(analyzer: Analyzer, root: Path, sub: str, e: dict) -> dict:
    path = root / sub / e["path"]
    text = path.read_text(encoding="utf-8", errors="replace")
    r = analyzer.check_text(text, e["format"], str(path))
    counts = r.counts()
    row = {k: e[k] for k in ("id", "category", "source", "sha256") if k in e}
    row |= {k: e[k] for k in ("pair_id", "role", "stars", "language", "tier", "paper") if k in e}
    row |= {"words": r.words, "sentences": r.sentences, "points": r.points, "verdict": r.verdict,
            "cost_index": round(r.cost_index, 3), "ms_per_word": r.reading_ms_per_word,
            "findings_per_1k": 1000 * len(r.findings) / r.words if r.words else None,
            "words_per_sentence": r.words / r.sentences if r.sentences else None,
            "mean_word_length": mean_word_length(text, e["format"], str(path)), "counts": counts}
    return row


def value(row: dict, measure: str) -> float | None:
    if measure in FEATURES:
        return 1000 * row["counts"].get(measure, 0) / row["words"] if row["words"] else None
    return row.get(measure)


def fmt(x, digits: int = 3) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    if isinstance(x, float):
        return f"{x:.{digits}g}"
    return str(x)


def pvalue(test, *a) -> float | None:
    try:
        return float(test(*a).pvalue)
    except ValueError:
        return None


def pair_table(rows: list[dict], measures: list[str]) -> list[dict]:
    """Lay minus expert per measure, one unit per pair."""
    by_pair: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        by_pair[r["pair_id"]][r["role"]] = r
    pairs = [(p["expert"], p["lay"]) for p in by_pair.values() if "expert" in p and "lay" in p]
    out = []
    for m in measures:
        d = [(value(lay, m), value(exp, m)) for exp, lay in pairs]
        d = [(a, b) for a, b in d if a is not None and b is not None]
        diffs = [a - b for a, b in d]
        out.append({"measure": m, "pairs": len(d),
                    "expert_median": statistics.median(b for _, b in d) if d else None,
                    "lay_median": statistics.median(a for a, _ in d) if d else None,
                    "median_diff": statistics.median(diffs) if d else None,
                    "lay_lower": sum(x < 0 for x in diffs) / len(d) if d else None,
                    "same": sum(x == 0 for x in diffs) / len(d) if d else None,
                    "p": pvalue(wilcoxon, [x for x in diffs if x]) if any(diffs) else None})
    return out


def group_table(groups: dict[str, list[dict]], measures: list[str], test) -> list[dict]:
    out = []
    for m in measures:
        vals = {g: [v for r in rs if (v := value(r, m)) is not None] for g, rs in groups.items()}
        vals = {g: v for g, v in vals.items() if v}
        row = {"measure": m, **{g: statistics.median(v) for g, v in vals.items()}}
        row["p"] = pvalue(test, *vals.values()) if len(vals) >= 2 else None
        out.append(row)
    return out


def md_table(rows: list[dict], cols: list[str], pct: tuple[str, ...] = ()) -> list[str]:
    lines = ["| " + " | ".join(cols) + " |", "|" + " --- |" * len(cols)]
    for r in rows:
        cells = [f"{100 * r[c]:.0f}%" if c in pct and r.get(c) is not None else fmt(r.get(c)) for c in cols]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    root: Path = args.root
    out = args.out or root / "results"
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    cache_path = out / "texts.jsonl"
    cache = {}
    if cache_path.exists():
        for line in cache_path.read_text().splitlines():
            r = json.loads(line)
            cache[(r["id"], r["sha256"])] = r

    analyzer = Analyzer(config=Config())
    features = [f for f in FEATURES if f in analyzer.enabled]
    rows: list[dict] = []
    counts: dict[str, dict] = {}
    located: dict[str, tuple[str, dict]] = {}
    for mf in sorted(root.glob("*/manifest.json")):
        sub = mf.parent.name
        entries = json.loads(mf.read_text())["entries"]
        for i, e in enumerate(entries):
            key = (e["id"], e["sha256"])
            located[e["id"]] = (sub, e)
            rows.append(cache[key] if key in cache else score(analyzer, root, sub, e))
            c = counts.setdefault(f"{e['category']}/{e['source']}", {"texts": 0, "licences": {}})
            c["texts"] += 1
            c["licences"][e["license"]] = c["licences"].get(e["license"], 0) + 1
            if (i + 1) % 100 == 0:
                print(f"{sub}: {i + 1}/{len(entries)}", file=sys.stderr)
    cache_path.write_text("".join(json.dumps(r) + "\n" for r in rows))

    long_rows = [r for r in rows if r["words"] >= MIN_WORDS]
    by_cat: dict[str, list[dict]] = defaultdict(list)
    by_src: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
        by_src[f"{r['category']}/{r['source']}"].append(r)

    def summarize(rs: list[dict]) -> dict:
        s = eval_corpus.summarize(rs, features)
        ms = [r["ms_per_word"] for r in rs if r["words"] >= MIN_WORDS and r["ms_per_word"] is not None]
        wps = [r["words_per_sentence"] for r in rs if r["words"] >= MIN_WORDS and r["words_per_sentence"]]
        s["ms_per_word_p50"] = round(statistics.median(ms), 1) if ms else None
        s["words_per_sentence_p50"] = round(statistics.median(wps), 1) if wps else None
        return s

    measures = list(BASE) + features
    summary: dict = {
        "readcost": eval_corpus.code_version(), "settings": "Config() defaults",
        "min_words": MIN_WORDS, "features": features, "item_counts": counts,
        "by_category": {k: summarize(v) for k, v in sorted(by_cat.items())},
        "by_source": {k: summarize(v) for k, v in sorted(by_src.items())},
        "pairs": {}, "pairs_by_source": {},
    }
    for cat in PAIR_CATEGORIES:
        rs = by_cat.get(cat, [])
        if rs:
            summary["pairs"][cat] = pair_table(rs, measures)
            for src in sorted({r["source"] for r in rs}):
                summary["pairs_by_source"][f"{cat}/{src}"] = pair_table(
                    [r for r in rs if r["source"] == src], list(BASE))

    # English Wikipedia articles run about eight times as long as their Simple
    # counterparts. As a length control, score each English article cut, at a
    # paragraph end, to the Simple article's word count.
    wiki = by_cat.get("wiki-pair", [])
    if wiki:
        lay_words = {r["pair_id"]: r["words"] for r in wiki if r["role"] == "lay"}
        matched = [r for r in wiki if r["role"] == "lay"]
        for r in wiki:
            if r["role"] != "expert" or r["pair_id"] not in lay_words:
                continue
            sub, e = located[r["id"]]
            text = (root / sub / e["path"]).read_text(encoding="utf-8")
            paras, n = [], 0
            for para in text.split("\n\n"):
                if n >= lay_words[r["pair_id"]]:
                    break
                paras.append(para)
                n += len(para.split())
            res = analyzer.check_text("\n\n".join(paras) + "\n", "text", e["path"])
            matched.append({**r, "words": res.words, "sentences": res.sentences,
                            "cost_index": res.cost_index, "ms_per_word": res.reading_ms_per_word,
                            "findings_per_1k": 1000 * len(res.findings) / res.words if res.words else None,
                            "words_per_sentence": res.words / res.sentences if res.sentences else None,
                            "mean_word_length": mean_word_length("\n\n".join(paras), "text", e["path"]),
                            "counts": res.counts()})
        summary["pairs"]["wiki-pair, English cut to the Simple length"] = pair_table(matched, measures)

    gov = [r for r in long_rows if r["category"] == "govuk"]
    if gov:
        summary["govuk"] = group_table({s: [r for r in gov if r["source"] == s] for s in ("guide", "detailed_guide")},
                                       measures, mannwhitneyu)

    readmes = [r for r in long_rows if r["category"] == "readme"]
    if readmes:
        corr = []
        for m in measures:
            pts = [(r["stars"], v) for r in readmes if (v := value(r, m)) is not None]
            rho = spearmanr([a for a, _ in pts], [b for _, b in pts])
            corr.append({"measure": m, "n": len(pts), "rho": float(rho.statistic), "p": float(rho.pvalue)})
        summary["readme_stars"] = corr
        langs = sorted({r["language"] for r in readmes})
        summary["readme_language"] = group_table({lg: [r for r in readmes if r["language"] == lg] for lg in langs},
                                                 measures, kruskal)
        tiers = ("5-50", "50-500", "500-5000", "5000+")
        summary["readme_tier"] = group_table({t: [r for r in readmes if r["tier"] == t] for t in tiers},
                                             measures, kruskal)

    arx = [r for r in long_rows if r["category"].startswith("arxiv")]
    if arx:
        for cat in ("arxiv-abstract", "arxiv-intro"):
            rs = [r for r in rows if r["category"] == cat and r["words"] >= (50 if cat == "arxiv-abstract" else MIN_WORDS)]
            fields = sorted({r["source"] for r in rs})
            summary[f"{cat}_field"] = group_table({f: [r for r in rs if r["source"] == f] for f in fields},
                                                  measures, kruskal)
        both: dict[str, dict] = defaultdict(dict)
        for r in rows:
            if r["category"] in ("arxiv-abstract", "arxiv-intro"):
                both[r["paper"]]["lay" if r["category"] == "arxiv-intro" else "expert"] = r | {"pair_id": r["paper"]}
        paired = [x for p in both.values() if len(p) == 2 for x in (p["expert"] | {"role": "expert"},
                                                                    p["lay"] | {"role": "lay"})]
        summary["arxiv_intro_minus_abstract"] = pair_table(paired, measures)

    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")

    abbrev = eval_corpus.ABBREV
    md = [(f"readcost {summary['readcost']}; Config() defaults. Texts under {MIN_WORDS} words are left out of "
           "percentiles and group comparisons."), ""]
    md += ["## Items", ""]
    md += md_table([{"source": k, "texts": v["texts"], "licences": ", ".join(f"{a} {b}" for a, b in v["licences"].items())}
                    for k, v in sorted(counts.items())], ["source", "texts", "licences"])
    md += ["", "## By category", "", eval_corpus.markdown_table(summary["by_category"], features, "category"), "",
           "## By source", "", eval_corpus.markdown_table(summary["by_source"], features, "source"), ""]
    md += ["Median ms/word and words/sentence (texts of 150+ words):", ""]
    md += md_table([{"group": k, "ms/word": v["ms_per_word_p50"], "words/sentence": v["words_per_sentence_p50"]}
                    for k, v in {**summary["by_category"], **summary["by_source"]}.items()],
                   ["group", "ms/word", "words/sentence"])
    pcols = ["measure", "pairs", "expert_median", "lay_median", "median_diff", "lay_lower", "same", "p"]
    for cat, tab in summary["pairs"].items():
        md += ["", f"## Pairs: {cat} (lay minus expert)", ""] + md_table(tab, pcols, ("lay_lower", "same"))
    for key, tab in summary["pairs_by_source"].items():
        md += ["", f"### {key}", ""] + md_table(tab, pcols, ("lay_lower", "same"))
    if "arxiv_intro_minus_abstract" in summary:
        md += ["", "## arXiv: introduction (\"lay\" column) minus abstract (\"expert\" column), per paper", ""]
        md += md_table(summary["arxiv_intro_minus_abstract"], pcols, ("lay_lower", "same"))
    for key, label in (("govuk", "GOV.UK guide vs detailed_guide (medians, Mann-Whitney U)"),
                       ("readme_language", "READMEs by language (medians, Kruskal-Wallis)"),
                       ("readme_tier", "READMEs by star tier (medians, Kruskal-Wallis)"),
                       ("arxiv-abstract_field", "arXiv abstracts by field (medians, Kruskal-Wallis)"),
                       ("arxiv-intro_field", "arXiv introductions by field (medians, Kruskal-Wallis)")):
        if key in summary:
            cols = ["measure"] + [k for k in summary[key][0] if k not in ("measure", "p")] + ["p"]
            md += ["", f"## {label}", ""] + md_table(summary[key], cols)
    if "readme_stars" in summary:
        md += ["", "## READMEs: Spearman correlation with stars", ""]
        md += md_table(summary["readme_stars"], ["measure", "n", "rho", "p"])
    md += ["", "Rule abbreviations: " + ", ".join(f"{abbrev.get(f, f)} = {f}" for f in features) + "."]
    (out / "summary.md").write_text("\n".join(md) + "\n")
    print(f"{len(rows)} texts -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
