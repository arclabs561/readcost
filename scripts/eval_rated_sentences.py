"""Do readcost findings track how easy readers found each sentence of a technical abstract?

    git clone --depth 1 https://github.com/SDS-NLP/PLABA-EVAL /tmp/data/PLABA-EVAL/repo
    uv run python scripts/eval_rated_sentences.py /tmp/data/PLABA-EVAL/repo

Data: PLABA-EVAL (Bian, Yoon and Komachi, "PLABA-EVAL: A Multi-Dimensional,
In-Context Sentence Readability Dataset for Medical Text"),
https://github.com/SDS-NLP/PLABA-EVAL, CC BY 4.0. 39 biomedical abstracts
and their expert plain-language versions, 609 sentences. Three lay readers
per document version rated every sentence, with the whole document in
view, for processing ease and perceived understanding (1 to 5, 5 easiest).
The data stays outside this repository. Files read: dataset/sentences.csv
and dataset/annotations.csv.

Each sentence is checked alone. The script prints, for each rating,
Spearman's rho with sentence length, word length, word frequency and
findings; the partial rho of findings with the three lexical measures held
constant; and the difference in rating between flagged and unflagged
sentences from a regression with the same controls and the document
version. Intervals are bootstraps over abstracts, since the sentences of
one abstract, in both versions, share topic and readers.

What this can show: whether lay readers rate a flagged sentence of
technical prose as harder than its length and vocabulary explain. This is
the only dataset here with expert technical text. What it cannot show:
reading time, measured comprehension per sentence, or the view of an
expert reader; the ratings are self-reports by three people per sentence.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_signals import (  # noqa: E402
    RULES, cluster_bootstrap, coefficient, count_rules, detect_spans, lexical, partial_spearman, spearman)

ASPECTS = ("processing_ease", "perceived_understanding")


def load(root: Path) -> list[dict]:
    """One row per rated sentence: text, abstract, version and the mean of its ratings."""
    with open(root / "dataset" / "sentences.csv", encoding="utf-8", newline="") as f:
        sentences = {r["sentence_uid"]: r for r in csv.DictReader(f)}
    ratings: dict[str, dict[str, list[float]]] = {}
    with open(root / "dataset" / "annotations.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["sentence_uid"] not in sentences or r["included_in_paper_sentence_analysis"] != "True":
                continue
            for aspect in ASPECTS:
                if r[aspect]:
                    ratings.setdefault(r["sentence_uid"], {}).setdefault(aspect, []).append(float(r[aspect]))
    rows = []
    for uid, by in sorted(ratings.items()):
        s = sentences[uid]
        if all(len(by.get(a, [])) >= 2 for a in ASPECTS):
            rows.append({"uid": uid, "text": s["sentence_text"], "group": s["doc_pair_id"],
                         "simplified": s["variant"] == "simp",
                         **{a: float(np.mean(by[a])) for a in ASPECTS}})
    return rows


def measure(analyzer, zipf: dict, unseen: float, rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        rules = count_rules(detect_spans(analyzer, r["text"]))
        words, letters, freq = lexical(r["text"], zipf, unseen)
        if words:
            out.append(dict(r, rules=rules, findings=sum(rules.values()), words=words, letters=letters, zipf=freq))
    return out


def summarize(rows: list[dict], aspect: str, resamples: int = 2000) -> dict:
    groups = np.array([r["group"] for r in rows])
    y = np.array([r[aspect] for r in rows])
    words, letters, freq = (np.array([float(r[k]) for r in rows]) for k in ("words", "letters", "zipf"))
    flagged = np.array([float(r["findings"] > 0) for r in rows])
    lexical_controls = np.column_stack([words, letters, freq])
    controls = np.column_stack([lexical_controls, [float(r["simplified"]) for r in rows]])
    out = {"sentences": len(rows), "abstracts": len(set(groups)), "flagged": int(flagged.sum()), "rho": {}}
    for name, x in (("words", words), ("mean word length", letters), ("mean word frequency", freq),
                    ("any finding", flagged)):
        out["rho"][name] = (spearman(x, y), cluster_bootstrap(lambda k: spearman(x[k], y[k]), groups, resamples))
    out["partial"] = (partial_spearman(flagged, y, lexical_controls),
                      cluster_bootstrap(lambda k: partial_spearman(flagged[k], y[k], lexical_controls[k]),
                                        groups, resamples))
    out["effect"] = coefficient(y, flagged, controls, groups, resamples)
    out["rules"] = {}
    for rule in RULES:
        has = np.array([float(r["rules"].get(rule, 0) > 0) for r in rows])
        if has.sum() >= 10:
            out["rules"][rule] = (int(has.sum()), coefficient(y, has, controls, groups, resamples))
    return out


def main(argv: list[str]) -> int:
    from readcost import Analyzer, Config
    from readcost.readtime import _zipf

    if len(argv) != 2:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    zipf, unseen = _zipf()
    rows = measure(Analyzer(Config()), zipf, unseen, load(Path(argv[1])))
    for label, part in (("original", [r for r in rows if not r["simplified"]]),
                        ("plain-language", [r for r in rows if r["simplified"]])):
        n_words = sum(r["words"] for r in part)
        print(f"{label}: {len(part)} sentences, {n_words} words, "
              f"{100 * sum(r['findings'] for r in part) / n_words:.2f} findings per 100 words, "
              f"{np.mean([r['findings'] > 0 for r in part]):.0%} of sentences flagged, "
              + ", ".join(f"mean {a.replace('_', ' ')} {np.mean([r[a] for r in part]):.2f}" for a in ASPECTS))
    for aspect in ASPECTS:
        s = summarize(rows, aspect)
        print(f"\n{aspect.replace('_', ' ')}: {s['sentences']} sentences from {s['abstracts']} abstracts, "
              f"{s['flagged']} flagged")
        for name, (rho, ci) in s["rho"].items():
            print(f"  rho with {name:<20} {rho:+.3f} ({ci[0]:+.3f} to {ci[1]:+.3f})")
        rho, ci = s["partial"]
        print(f"  partial rho, any finding (length, word length, frequency held) {rho:+.3f} ({ci[0]:+.3f} to {ci[1]:+.3f})")
        e = s["effect"]
        print(f"  flagged against unflagged, controls and version held: {e['coef']:+.2f} points "
              f"({e['ci'][0]:+.2f} to {e['ci'][1]:+.2f}), {e['standardized']:+.2f} SD; "
              f"R2 {e['r2_controls']:.3f} to {e['r2_with']:.3f}")
        for rule, (n, e) in s["rules"].items():
            print(f"    {rule:<24} {n:>3} sentences  {e['coef']:+.2f} ({e['ci'][0]:+.2f} to {e['ci'][1]:+.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
