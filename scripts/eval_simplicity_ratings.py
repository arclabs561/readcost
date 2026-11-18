"""Do readcost findings track human ratings of simplified sentences?

    uv run python scripts/eval_simplicity_ratings.py asset   /tmp/data/asset/repo
    uv run python scripts/eval_simplicity_ratings.py da      /tmp/data/metaeval-simplification/repo
    uv run python scripts/eval_simplicity_ratings.py past    /tmp/data/LENS/repo
    uv run python scripts/eval_simplicity_ratings.py 2022    /tmp/data/LENS/repo
    uv run python scripts/eval_simplicity_ratings.py llm     /tmp/data/human-eval-llm-simplification/repo

Each dataset pairs an original sentence with a simplification and gives
ratings by people. The data stays outside this repository.

    asset  ASSET human ratings (Alva-Manchego et al. 2020, ACL),
           https://github.com/facebookresearch/asset, CC BY-NC 4.0.
           100 system outputs, 15 crowd ratings each of simplicity, fluency
           and meaning on 0 to 100. File human_ratings/human_ratings.csv.
    da     Simplicity-DA (Alva-Manchego, Scarton and Specia 2021,
           Computational Linguistics 47(4)),
           https://github.com/feralvam/metaeval-simplification,
           CC BY-NC-SA 4.0. 600 system outputs, 15 ratings each,
           standardised per rater. File data/simplicity_DA.csv.
    past   SimpEval_past and
    2022   SimpEval_2022 (Maddela, Dou, Heineman and Xu 2023, ACL, "LENS"),
           https://github.com/Yao-Dou/LENS; the repository states no
           licence. 2,400 outputs of 24 systems on Wikipedia sentences with
           five ratings, and 360 outputs (two people, GPT-3.5 zero- and
           few-shot, MUSS, T5) on newer sentences with three. The rating is
           of overall simplification quality, which includes keeping the
           meaning. The control systems "copy" and "scramble_words" are
           dropped.
    llm    Wu and Arase 2026 (ACM TIST 17(4)),
           https://github.com/WuXuanxin/human-eval-llm-simplification; the
           repository states no licence. Likert ratings by three annotators
           of simplifications by GPT-4, Qwen2.5-72B, Llama-3.2-3B and
           Control-T5 on Turk, ASSET and SimPA sentences (the Newsela part
           is withheld).

For each dataset the script prints: findings in originals against
simplifications; Spearman's rho between the mean rating and each measure of
the simplification; the partial rho of findings with length, word length
and word frequency held constant; and, for originals that have a finding,
the rating of simplifications that removed every finding against those that
kept one. Intervals are bootstraps over original sentences, since several
simplifications share one original.

What this can show: whether raters call an output simpler or more fluent
when it has fewer readcost findings than its length and words explain. What
it cannot show: reading time or comprehension, or anything about text that
is not a single rewritten sentence from Wikipedia, news or public
administration.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_signals import (  # noqa: E402
    cluster_bootstrap, coefficient, count_rules, detect_spans, lexical, partial_spearman, spearman)

CONTROL_SYSTEMS = {"copy", "scramble_words"}


def _mean(values) -> float:
    values = [float(v) for v in values if v not in ("", None)]
    return float(np.mean(values)) if values else float("nan")


def load_asset(root: Path) -> list[dict]:
    by: dict[tuple, dict] = {}
    with open(root / "human_ratings" / "human_ratings.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            row = by.setdefault((r["original_sentence_id"], r["simplification"]), {
                "group": r["original_sentence_id"], "original": r["original"],
                "simplified": r["simplification"], "system": "system", "ratings": {}})
            row["ratings"].setdefault(r["aspect"], []).append(float(r["rating"]))
    return [dict(row, simplicity=_mean(row["ratings"].get("simplicity", [])),
                 fluency=_mean(row["ratings"].get("fluency", []))) for row in by.values()]


def load_da(root: Path) -> list[dict]:
    with open(root / "data" / "simplicity_DA.csv", encoding="utf-8-sig", newline="") as f:
        return [{"group": r["sent_id"], "original": r["orig_sent"], "simplified": r["simp_sent"],
                 "system": r["sys_name"], "simplicity": float(r["simplicity_zscore"]),
                 "fluency": float(r["fluency_zscore"])} for r in csv.DictReader(f)]


def load_simpeval(root: Path, name: str) -> list[dict]:
    rows = []
    with open(root / "data" / name, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["system"] in CONTROL_SYSTEMS:
                continue
            z = [v for k, v in r.items() if k.startswith("rating_") and "z" in k]
            text = r.get("processed_generation") or r["generation"]
            rows.append({"group": r["original_id"], "original": r["original"], "simplified": text,
                         "system": r["system"], "simplicity": _mean(z), "fluency": float("nan")})
    return rows


def load_llm(root: Path) -> list[dict]:
    rows = []
    for path in sorted((root / "annotation" / "likert" / "exclude_newsela").glob("likert_*.json")):
        for r in json.loads(path.read_text(encoding="utf-8")):
            notes = r["label_annotations"].values()
            rows.append({"group": f"{r['source_file']}/{r['source_id']}", "original": r["source"],
                         "simplified": r["simple"], "system": r["model"],
                         "simplicity": _mean(a.get("simplicity") for a in notes),
                         "fluency": _mean(a.get("fluency") for a in notes)})
    return rows


LOADERS = {"asset": load_asset, "da": load_da,
           "past": lambda root: load_simpeval(root, "simpeval_past.csv"),
           "2022": lambda root: load_simpeval(root, "simpeval_2022.csv"),
           "llm": load_llm}


def measure(analyzer, zipf: dict, unseen: float, rows: list[dict]) -> list[dict]:
    """Add findings and lexical measures of both sides to each row; drop rows with an empty side."""
    cache: dict[str, tuple] = {}

    def one(text: str) -> tuple:
        if text not in cache:
            rules = count_rules(detect_spans(analyzer, text))
            cache[text] = (sum(rules.values()), rules, *lexical(text, zipf, unseen))
        return cache[text]

    out = []
    for r in rows:
        o, s = one(r["original"]), one(r["simplified"])
        if not o[2] or not s[2]:
            continue
        out.append(dict(r, o_findings=o[0], o_rules=o[1], o_words=o[2],
                        s_findings=s[0], s_rules=s[1], s_words=s[2], s_letters=s[3], s_zipf=s[4]))
    return out


def summarize(rows: list[dict], aspect: str = "simplicity", resamples: int = 2000) -> dict:
    """The statistics printed for one dataset and one rated aspect."""
    rows = [r for r in rows if r[aspect] == r[aspect]]
    groups = np.array([r["group"] for r in rows])
    y = np.array([r[aspect] for r in rows])
    cols = {k: np.array([float(r[k]) for r in rows]) for k in
            ("o_findings", "s_findings", "o_words", "s_words", "s_letters", "s_zipf")}
    delta = cols["s_findings"] - cols["o_findings"]
    controls = np.column_stack([cols["s_words"], cols["s_letters"], cols["s_zipf"]])
    out = {"pairs": len(rows), "originals": len(set(groups)),
           "original_rate": 100 * cols["o_findings"].sum() / cols["o_words"].sum(),
           "simplified_rate": 100 * cols["s_findings"].sum() / cols["s_words"].sum(),
           "fewer": float((delta < 0).mean()), "same": float((delta == 0).mean()),
           "more": float((delta > 0).mean()), "mean_delta": float(delta.mean()),
           "mean_delta_ci": cluster_bootstrap(lambda k: float(delta[k].mean()), groups, resamples),
           "rho": {}}
    for name, x in (("words", cols["s_words"]), ("mean word length", cols["s_letters"]),
                    ("mean word frequency", cols["s_zipf"]), ("findings", cols["s_findings"]),
                    ("findings, change from original", delta)):
        out["rho"][name] = (spearman(x, y), cluster_bootstrap(lambda k: spearman(x[k], y[k]), groups, resamples))
    out["partial"] = (partial_spearman(cols["s_findings"], y, controls),
                      cluster_bootstrap(lambda k: partial_spearman(cols["s_findings"][k], y[k], controls[k]),
                                        groups, resamples))
    had = cols["o_findings"] > 0
    out["had"] = int(had.sum())
    removed = (cols["s_findings"] == 0)[had].astype(float)
    out["removed"] = int(removed.sum())
    if 10 <= removed.sum() <= had.sum() - 10:
        fit = coefficient(y[had], removed, controls[had], groups[had], resamples)
        out["removed_effect"] = (fit["coef"], fit["ci"], fit["standardized"])
    return out


def by_system(rows: list[dict], aspect: str = "simplicity") -> list[tuple[str, int, float, float]]:
    """(system, outputs, findings per 100 words, mean rating), most findings first."""
    out = []
    for system in sorted({r["system"] for r in rows}):
        part = [r for r in rows if r["system"] == system and r[aspect] == r[aspect]]
        if part:
            out.append((system, len(part), 100 * sum(r["s_findings"] for r in part) / sum(r["s_words"] for r in part),
                        float(np.mean([r[aspect] for r in part]))))
    return sorted(out, key=lambda t: -t[2])


def _show(name: str, s: dict) -> None:
    print(f"\n{name}: {s['pairs']} pairs from {s['originals']} originals")
    print(f"  findings per 100 words: original {s['original_rate']:.2f}, simplified {s['simplified_rate']:.2f}; "
          f"per pair {s['mean_delta']:+.3f} (95% CI {s['mean_delta_ci'][0]:+.3f} to {s['mean_delta_ci'][1]:+.3f}); "
          f"fewer {s['fewer']:.0%}, same {s['same']:.0%}, more {s['more']:.0%}")
    for measure_name, (rho, ci) in s["rho"].items():
        print(f"  rho with {measure_name:<31} {rho:+.3f} ({ci[0]:+.3f} to {ci[1]:+.3f})")
    rho, ci = s["partial"]
    print(f"  partial rho, findings (length, word length, frequency held) {rho:+.3f} ({ci[0]:+.3f} to {ci[1]:+.3f})")
    line = f"  originals with a finding: {s['had']} pairs, {s['removed']} simplifications removed every finding"
    if "removed_effect" in s:
        coef, ci, std = s["removed_effect"]
        line += f"; rating {coef:+.3f} ({ci[0]:+.3f} to {ci[1]:+.3f}), {std:+.2f} SD, when removed"
    print(line)


def main(argv: list[str]) -> int:
    from readcost import Analyzer, Config
    from readcost.readtime import _zipf

    if len(argv) != 3 or argv[1] not in LOADERS:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    zipf, unseen = _zipf()
    rows = measure(Analyzer(Config()), zipf, unseen, LOADERS[argv[1]](Path(argv[2])))
    _show(f"{argv[1]} simplicity", summarize(rows, "simplicity"))
    if any(r["fluency"] == r["fluency"] for r in rows):
        _show(f"{argv[1]} fluency", summarize(rows, "fluency"))
    systems = by_system(rows)
    if len(systems) > 1:
        print("\n  system                        outputs  findings/100 words  mean rating")
        for system, n, rate, rating in systems:
            print(f"  {system:<30} {n:>6}  {rate:>10.2f}  {rating:>14.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
