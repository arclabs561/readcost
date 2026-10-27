"""Do human simplifications lower readcost's measures? Original sentences against ASSET rewrites.

    D=/Volumes/Rebuildable/readcost-ref/datasets/asset
    for s in test valid; do for f in orig simp.0 simp.1 simp.2 simp.3 simp.4 simp.5 simp.6 simp.7 simp.8 simp.9; do
      curl -sfL --max-time 60 -o $D/asset.$s.$f \
        https://raw.githubusercontent.com/facebookresearch/asset/main/dataset/asset.$s.$f; done; done
    python3 -I scripts/eval_simplifications.py $D

Data: ASSET (Alva-Manchego et al. 2020, "ASSET: A Dataset for Tuning and
Evaluation of Sentence Simplification Models with Multiple Rewriting
Transformations", ACL; https://github.com/facebookresearch/asset, CC BY-NC
4.0). 2,359 English Wikipedia sentences, each simplified by ten crowd workers
who could paraphrase, delete and split sentences. The data stays outside the
repository.

People rewrote these sentences, as models did in the paired rewrites of
docs/evaluation.md. For every pair of an original and a simplification it
compares four measures: findings, weighted points, cost index (weighted
points per 1,000 words) and predicted ms per word. It prints the share of pairs where the measure went
down, stayed, or went up, with a two-sided Wilcoxon signed-rank test on each
original sentence's mean difference (its ten simplifications are not
independent). It then takes the pairs whose original has a finding and counts,
per rule, how often the simplification no longer has it, and how often a
simplification of a sentence without the finding adds one. Needs scipy.
"""

import statistics
import sys
from collections import Counter
from pathlib import Path

from scipy.stats import wilcoxon

from readcost import Analyzer, Config


def main(ref: Path) -> None:
    a = Analyzer(Config())
    rules = [f for f in a.enabled if f != "long-sentence"]

    def measure(text: str) -> dict | None:
        r = a.check_text(text, "text")
        if not r.words or r.reading_ms_per_word is None:
            return None
        return {"words": r.words, "findings": len(r.findings), "points": r.points,
                "cost_index": 1000 * r.points / r.words, "ms_per_word": r.reading_ms_per_word,
                "counts": r.counts()}

    pairs = []
    for split in ("test", "valid"):
        origs = (ref / f"asset.{split}.orig").read_text(encoding="utf-8").splitlines()
        simps = [(ref / f"asset.{split}.simp.{k}").read_text(encoding="utf-8").splitlines() for k in range(10)]
        for i, o in enumerate(origs):
            mo = measure(o)
            if mo is None:
                continue
            for s in simps:
                ms = measure(s[i]) if i < len(s) and s[i].strip() else None
                if ms is not None:
                    pairs.append((mo, ms))
    by_orig: dict[int, list] = {}
    for o, s in pairs:
        by_orig.setdefault(id(o), []).append((o, s))
    n_orig = len(by_orig)
    print(f"{n_orig} original sentences, {len(pairs)} pairs\n")
    print("| Measure | Original median | Simplification median | Lower | Same | Higher | p |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for k in ("words", "findings", "points", "cost_index", "ms_per_word"):
        d = [s[k] - o[k] for o, s in pairs]
        lo, same, hi = (sum(x < 0 for x in d), sum(x == 0 for x in d), sum(x > 0 for x in d))
        # The ten simplifications of one sentence are not independent: test the
        # mean difference per original sentence.
        per_orig = [statistics.mean(s[k] - o[k] for o, s in ps) for ps in by_orig.values()]
        p = wilcoxon([x for x in per_orig if x]).pvalue
        print(f"| {k} | {statistics.median(o[k] for o, _ in pairs):.3g} | "
              f"{statistics.median(s[k] for _, s in pairs):.3g} | {lo / len(d):.0%} | {same / len(d):.0%} | "
              f"{hi / len(d):.0%} | {p:.2g} |")
    ow = sum(o["words"] for o, _ in pairs)
    sw = sum(s["words"] for _, s in pairs)
    oc, sc = Counter(), Counter()
    for o, s in pairs:
        oc.update(o["counts"])
        sc.update(s["counts"])
    print("\n| Rule | Per 1k words, original | Per 1k words, simplification | Original has it: simplification "
          "drops it | Original lacks it: simplification adds it |")
    print("| --- | --- | --- | --- | --- |")
    for f in [*rules, "all"]:
        def has(m, f=f):
            return bool(m["findings"]) if f == "all" else m["counts"].get(f, 0) > 0
        with_ = [(o, s) for o, s in pairs if has(o)]
        without = [(o, s) for o, s in pairs if not has(o)]
        drop = sum(not has(s) for _, s in with_)
        add = sum(has(s) for _, s in without)
        po = sum(oc.values()) if f == "all" else oc[f]
        ps = sum(sc.values()) if f == "all" else sc[f]
        print(f"| {f} | {1000 * po / ow:.2f} | {1000 * ps / sw:.2f} | "
              f"{drop} of {len(with_)} ({drop / max(len(with_), 1):.0%}) | "
              f"{add} of {len(without)} ({add / max(len(without), 1):.1%}) |")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
