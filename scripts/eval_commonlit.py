"""Correlate readcost measures with teacher-judged ease (CommonLit CLEAR BT_easiness).

    for s in train validation test; do curl -L -o ref/commonlit/$s.parquet \
      "https://huggingface.co/datasets/casey-martin/CommonLit-Ease-of-Readability/resolve/refs%2Fconvert%2Fparquet/default/$s/0000.parquet"; done
    python3 -I scripts/eval_commonlit.py ref/commonlit

The CLEAR corpus (Crossley et al. 2022, Behavior Research Methods) has 4,724
excerpts for school reading with an ease score fitted from teachers' pairwise judgments (Bradley-Terry),
and classic formula scores for comparison. Licences are per excerpt (the
License column); the data stays local. Needs pyarrow and scipy.
"""
import re
import statistics
import sys
from pathlib import Path

import pyarrow.parquet as pq
from scipy.stats import spearmanr

from readcost import Analyzer, Config

rows = []
for p in sorted(Path(sys.argv[1]).glob("*.parquet")):
    rows += pq.read_table(p).to_pylist()
a = Analyzer(Config())
a_all = Analyzer(Config(enable=["long-sentence", "nominalization", "participial-clause"]))
meas = {k: [] for k in ("cost_index", "cost_index_all_rules", "findings_per_1k", "reading_ms_per_word",
                        "word_len", "words_per_sentence")}
ease = []
for r in rows:
    text = r["Excerpt"]
    res = a.check_text(text, "text")
    res2 = a_all.check_text(text, "text")
    ws = re.findall(r"[A-Za-z]+", text)
    if res.reading_ms_per_word is None or not ws:
        continue
    ease.append(r["BT_easiness"])
    meas["cost_index"].append(res.cost_index)
    meas["cost_index_all_rules"].append(res2.cost_index)
    meas["findings_per_1k"].append(1000 * len(res.findings) / max(res.words, 1))
    meas["reading_ms_per_word"].append(res.reading_ms_per_word)
    meas["word_len"].append(statistics.mean(len(w) for w in ws))
    meas["words_per_sentence"].append(len(ws) / max(r["Sentence Count"], 1))
formulas = {"Flesch-Reading-Ease": "Flesch Reading Ease", "Flesch-Kincaid-Grade-Level": "Flesch-Kincaid grade",
            "New Dale-Chall Readability Formula": "Dale-Chall", "CAREC": "CAREC"}
kept = [r for r in rows if r["Excerpt"] and re.findall(r"[A-Za-z]+", r["Excerpt"])]
print(f"{len(ease)} excerpts; correlation with BT_easiness (higher = easier, so a cost should be negative)\n")
print("| Measure | Spearman rho |")
print("| --- | --- |")
for k, v in meas.items():
    print(f"| readcost {k} | {spearmanr(v, ease).statistic:+.3f} |")
for col, name in formulas.items():
    vals = [r[col] for r in kept][:len(ease)]
    print(f"| {name} (from the dataset) | {spearmanr(vals, ease).statistic:+.3f} |")
