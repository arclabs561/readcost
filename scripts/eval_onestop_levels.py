"""Does readcost rank OneStopEnglish reading levels? Paired across the three versions of each article.

    curl -L -o ref/onestop.parquet \
      "https://huggingface.co/datasets/iastate/onestop_english/resolve/refs%2Fconvert%2Fparquet/default/train/0000.parquet"
    python3 -I scripts/eval_onestop_levels.py ref/onestop.parquet

OneStopEnglish (Vajjala and Lucic 2018; CC BY-SA 4.0) has 189 news articles,
each written at elementary, intermediate and advanced level. The dataset has
no article id, so versions are paired by vocabulary overlap (Jaccard 0.3 or
more across all three). A measure of difficulty should rise from elementary
to advanced. Needs pyarrow and scipy.
"""
import re
import statistics
import sys

import pyarrow.parquet as pq
from scipy.stats import wilcoxon

from readcost import Analyzer, Config

rows = pq.read_table(sys.argv[1]).to_pylist()
by = {0: [], 1: [], 2: []}
for r in rows:
    by[int(r["label"])].append(r["text"])


def words(t):
    return set(re.findall(r"[a-z]+", t.lower()))


# Pair each elementary text with the most similar intermediate and advanced text.
ws = {k: [words(t) for t in v] for k, v in by.items()}
triples = []
for i, w0 in enumerate(ws[0]):
    def best(level, w0=w0):
        sims = [len(w0 & w) / len(w0 | w) for w in ws[level]]
        j = max(range(len(sims)), key=sims.__getitem__)
        return j, sims[j]
    j1, s1 = best(1)
    j2, s2 = best(2)
    triples.append((i, j1, j2, min(s1, s2)))
ok = [t for t in triples if t[3] >= 0.3]
print(f"{len(ok)} of {len(triples)} articles matched across all three levels (Jaccard >= 0.3)", file=sys.stderr)

a = Analyzer(Config())


def measure(text):
    r = a.check_text(text, "text")
    ws_ = re.findall(r"[A-Za-z]+", text)
    sents = max(r.sentences, 1)
    return {"words": len(ws_), "word_len": statistics.mean(len(w) for w in ws_),
            "words_per_sentence": r.words / sents, "cost_index": r.cost_index,
            "findings_per_1k": 1000 * len(r.findings) / max(r.words, 1),
            "reading_ms_per_word": r.reading_ms_per_word, "reading_seconds": r.reading_seconds}


m = {lvl: {} for lvl in (0, 1, 2)}
for i, j1, j2, _ in ok:
    m[0][i] = measure(by[0][i])
    m[1][i] = measure(by[1][j1])
    m[2][i] = measure(by[2][j2])
keys = list(next(iter(m[0].values())))
print("| Measure | Elementary | Intermediate | Advanced | Adv > Ele | p (Adv vs Ele) | Ele < Int < Adv |")
print("| --- | --- | --- | --- | --- | --- | --- |")
for k in keys:
    e = [m[0][i][k] for i in m[0]]
    n = [m[1][i][k] for i in m[0]]
    v = [m[2][i][k] for i in m[0]]
    diff = [y - x for x, y in zip(e, v)]
    higher = sum(d > 0 for d in diff) / len(diff)
    p = wilcoxon([d for d in diff if d != 0]).pvalue if sum(d != 0 for d in diff) > 5 else float("nan")
    ordered = sum(x < y < z for x, y, z in zip(e, n, v)) / len(e)
    print(f"| {k} | {statistics.median(e):.3g} | {statistics.median(n):.3g} | {statistics.median(v):.3g} | "
          f"{higher:.0%} | {p:.2g} | {ordered:.0%} |")
