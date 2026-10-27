"""Correlate readcost's per-sentence findings with human sentence-difficulty ratings.

    D=/Volumes/Rebuildable/readcost-ref/datasets/cefr-sp
    for f in SCoRE/CEFR-SP_SCoRE_{train,dev,test}.txt Wiki-Auto/CEFR-SP_Wikiauto_{train,dev,test}.txt; do
      curl -sfL --max-time 60 -o $D/$(basename $f) \
        https://raw.githubusercontent.com/yukiar/CEFR-SP/main/CEFR-SP/$f; done
    python3 -I scripts/eval_sentence_ratings.py $D

Data: CEFR-SP (Arase, Uchida and Kajiwara 2022, "CEFR-Based Sentence
Difficulty Annotation and Assessment", EMNLP; https://github.com/yukiar/CEFR-SP).
Two English-education professionals each gave every sentence a CEFR level,
A1 to C2 (1 to 6). The public part has two sources: Wiki-Auto sentences
(Wikipedia, CC BY-SA 3.0) and SCoRE sentences (example sentences written for
learners, CC BY-NC-SA 4.0). The Newsela part needs a Newsela licence and is
not used. The data stays outside the repository.

Brunato et al. 2018 ("Is this Sentence Difficult? Do you Agree?", EMNLP),
the dataset first planned for this test, is behind a request form and its
English sentences come from the Penn Treebank's Wall Street Journal section
(LDC licence), so it is not used.

Each sentence is checked alone with readcost's default rules. For each
measure the script prints Spearman's rho with the mean of the two ratings,
the partial rho controlling for sentence length (Spearman ranks, residuals of
a linear fit on the length rank), and the mean rho within length bins. The
agreement between the two annotators is printed as a ceiling. Needs scipy.
"""

import re
import statistics
import sys
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, spearmanr, wilcoxon

from readcost import Analyzer, Config

BINS = [(1, 10), (11, 15), (16, 20), (21, 25), (26, 30), (31, 200)]


def detok(s: str) -> str:
    """Undo the PTB-style spacing of the dataset ("June 4 , 1830 .")."""
    s = re.sub(r" ([.,;:!?%)\]}])", r"\1", s)
    s = re.sub(r"([(\[{$]) ", r"\1", s)
    s = re.sub(r" (n't|'s|'re|'ve|'ll|'d|'m)\b", r"\1", s)
    s = re.sub(r'" (.*?) "', r'"\1"', s)
    return s.replace("`` ", '"').replace(" ''", '"')


def load(path: Path) -> list[tuple[str, float, float]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
            rows.append((detok(parts[0]), float(parts[1]), float(parts[2])))
    return rows


def partial(x, y, z) -> float:
    """Spearman partial correlation of x and y given z."""
    rx, ry, rz = (rankdata(v) for v in (x, y, z))  # ties share the mean rank

    def resid(a):
        b = np.polyfit(rz, a, 1)
        return a - np.polyval(b, rz)
    return float(np.corrcoef(resid(rx), resid(ry))[0, 1])


def within_bins(x, y, length) -> tuple[float, int]:
    rhos = []
    for lo, hi in BINS:
        idx = [i for i, n in enumerate(length) if lo <= n <= hi]
        xs = [x[i] for i in idx]
        if len(idx) >= 30 and len(set(xs)) > 1:
            rhos.append(spearmanr(xs, [y[i] for i in idx]).statistic)
    return (statistics.mean(rhos) if rhos else float("nan")), len(rhos)


def main(ref: Path) -> None:
    a = Analyzer(Config())
    rules = [f for f in a.enabled if f != "long-sentence"]
    for name, pattern in (("Wiki-Auto", "CEFR-SP_Wikiauto_*.txt"), ("SCoRE", "CEFR-SP_SCoRE_*.txt")):
        rows = [r for p in sorted(ref.glob(pattern)) for r in load(p)]
        m = {k: [] for k in ["words", "mean word length", "any finding", "findings", "weighted points",
                             "predicted ms per word", *rules]}
        rating, ra, rb = [], [], []
        for text, x, y in rows:
            r = a.check_text(text, "text")
            ws = re.findall(r"[A-Za-z]+", text)
            if r.words < 3 or r.reading_ms_per_word is None or not ws:
                continue
            rating.append((x + y) / 2)
            ra.append(x)
            rb.append(y)
            counts = r.counts()
            m["words"].append(r.words)
            m["mean word length"].append(statistics.mean(len(w) for w in ws))
            m["any finding"].append(int(bool(r.findings)))
            m["findings"].append(len(r.findings))
            m["weighted points"].append(r.points)
            m["predicted ms per word"].append(r.reading_ms_per_word)
            for f in rules:
                m[f].append(counts.get(f, 0))
        length = m["words"]
        print(f"\n### {name}: {len(rating)} sentences, median {statistics.median(length):g} words, "
              f"mean rating {statistics.mean(rating):.2f}")
        print(f"\nAnnotator A vs B: rho {spearmanr(ra, rb).statistic:+.3f}\n")
        print("| Measure | Sentences with it | rho | partial rho, length held | mean rho within length bins |")
        print("| --- | --- | --- | --- | --- |")
        for k, v in m.items():
            share = sum(1 for t in v if t) / len(v)
            if len(set(v)) < 2:
                continue
            rho = spearmanr(v, rating).statistic
            pr = partial(v, rating, length) if k != "words" else float("nan")
            wb, nb = within_bins(v, rating, length)
            cells = [f"{share:.0%}" if k in rules or k in ("any finding", "findings", "weighted points") else "all",
                     f"{rho:+.3f}", "-" if k == "words" else f"{pr:+.3f}", f"{wb:+.3f} ({nb} bins)"]
            print(f"| {k} | " + " | ".join(cells) + " |")
        # Length-matched contrast: each flagged sentence against unflagged ones of the same word count.
        clean: dict[int, list[float]] = {}
        for n, hit, y in zip(length, m["any finding"], rating):
            if not hit:
                clean.setdefault(n, []).append(y)
        diffs = [y - statistics.mean(clean[n]) for n, hit, y in zip(length, m["any finding"], rating)
                 if hit and len(clean.get(n, [])) >= 5]
        if diffs:
            print(f"\nFlagged sentences vs unflagged sentences of the same length: {len(diffs)} matched, "
                  f"mean rating difference {statistics.mean(diffs):+.3f} "
                  f"(sd {statistics.stdev(diffs):.2f}; scale 1 to 6; Wilcoxon p {wilcoxon(diffs).pvalue:.2g})")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
