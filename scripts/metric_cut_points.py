"""Derive the sentence-length bands in metrics.py from the evaluation corpus.

    python3 scripts/metric_cut_points.py ref/eval [--category essay,docs]

Follows Alves, Ypma and Visser (2010): every word is weighted by the length
(in words) of the sentence it sits in; each document's words add up to one,
so a long document does not set the bands; the cut points are the sentence
lengths below which 70%, 80% and 90% of the pooled weight falls. Prints the
cut points and, as Alves et al. check, the median share of each document's
words that falls in each band when the cut points are applied back.
"""

import argparse
import json
import statistics
from pathlib import Path

from readcost import metrics
from readcost.config import Config
from readcost.engine import Analyzer


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--category", default="essay,docs")
    args = ap.parse_args()
    wanted = set(args.category.split(","))
    entries = [e for e in json.loads((args.corpus / "manifest.json").read_text())["entries"]
               if e["category"] in wanted]
    lengths: list[list[int]] = []
    real = metrics.compute

    def capture(sents):
        sents = list(sents)
        lengths.append([sum(1 for t in s if t.is_alpha) for s in sents])
        return real(sents)

    metrics.compute = capture
    an = Analyzer(config=Config())
    for e in entries:
        path = Path(e["path"]) if Path(e["path"]).is_absolute() else args.corpus / e["path"]
        an.check_text(path.read_text(encoding="utf-8", errors="replace"), e["format"], str(path))
    docs = [d for d in lengths if sum(d)]
    weight: dict[int, float] = {}
    for d in docs:
        total = sum(d)
        for n in d:
            weight[n] = weight.get(n, 0.0) + n / total / len(docs)
    cuts, acc, qs = [], 0.0, [0.7, 0.8, 0.9]
    for n in sorted(weight):
        acc += weight[n]
        while qs and acc >= qs[0]:
            cuts.append(n)
            qs.pop(0)
    print(f"{len(docs)} documents, {sum(map(sum, docs))} words; cut points (words per sentence): {cuts}")
    bands = [[0.0] * 4 for _ in docs]
    for k, d in enumerate(docs):
        total = sum(d)
        for n in d:
            bands[k][sum(n > c for c in cuts)] += n / total
    print("median share of a document's words per band:",
          [round(statistics.median(b[j] for b in bands), 3) for j in range(4)])


if __name__ == "__main__":
    main()
