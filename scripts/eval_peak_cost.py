"""Does the peak of a sentence's predicted word cost say more than its mean?

    uv run --group eval scripts/eval_peak_cost.py CEFR_SP_DIR ASSET_DIR

Gibson (1998) argued that a sentence's difficulty is set by its hardest
point, not its average; Meister et al. (2021) found super-linear costs beat
linear ones for acceptability. readcost's predicted reading time is mostly
word length and frequency, so a peak can just be the longest or rarest word.
This tests each shape measure of the per-word predicted times against the
CEFR-SP teacher ratings with a Spearman partial correlation that holds
sentence length, mean predicted ms per word, the longest word and the rarest
word fixed (ranks residualised on all four), and checks on ASSET whether
people simplifying a sentence lower the peak, per original sentence.

Data as in scripts/eval_sentence_ratings.py and
scripts/eval_simplifications.py; it stays outside the repository.
"""

import statistics
import sys
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, spearmanr, wilcoxon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_sentence_ratings import load

from readcost import readtime


def shape(text: str) -> dict | None:
    words = readtime.paragraph_words(text)
    if len(words) < 4:
        return None
    ms = np.clip(readtime.predict(readtime.features(words)), 1.0, None)  # a few trees predict below 0
    zipf, floor = readtime._zipf()
    clean = [w.strip(".,;:!?()\"'").lower() for w in words]
    top = sorted(ms, reverse=True)
    return {
        "words": len(words),
        "mean ms": float(ms.mean()),
        "longest word": max(len(w) for w in clean),
        "rarest word": -min(zipf.get(w, floor) for w in clean if w) if any(clean) else 0.0,
        "3 longest words": float(np.mean(sorted((len(w) for w in clean), reverse=True)[:3])),
        "3 rarest words": -float(np.mean(sorted(zipf.get(w, floor) for w in clean if w)[:3])) if any(clean) else 0.0,
        "max ms": float(top[0]),
        "top-3 mean ms": float(np.mean(top[:3])),
        "90th percentile ms": float(np.percentile(ms, 90)),
        "sd ms": float(ms.std()),
        "sum ms^1.25 / words": float((ms ** 1.25).sum() / len(words)),
    }


CONTROLS = ["words", "mean ms", "longest word", "rarest word"]
# The strongest rival: a top-3 peak is just several long or rare words.
CONTROLS_3 = ["words", "mean ms", "3 longest words", "3 rarest words"]
SHAPES = ["max ms", "top-3 mean ms", "90th percentile ms", "sd ms", "sum ms^1.25 / words"]


def partial(x, y, zs) -> float:
    """Spearman partial correlation of x and y given every column of zs."""
    Z = np.column_stack([np.ones(len(x))] + [rankdata(z) for z in zs])

    def resid(a):
        a = rankdata(a)
        beta, *_ = np.linalg.lstsq(Z, a, rcond=None)
        return a - Z @ beta
    return float(np.corrcoef(resid(x), resid(y))[0, 1])


def ratings(ref: Path) -> None:
    for name, pattern in (("Wiki-Auto", "CEFR-SP_Wikiauto_*.txt"), ("SCoRE", "CEFR-SP_SCoRE_*.txt")):
        rows = [(s, (a + b) / 2) for p in sorted(ref.glob(pattern)) for s, a, b in load(p)]
        data = [(shape(s), r) for s, r in rows]
        data = [(m, r) for m, r in data if m]
        y = [r for _, r in data]
        col = {k: [m[k] for m, _ in data] for k in data[0][0]}
        print(f"\n{name}: {len(data)} sentences\n")
        print("| Measure | rho | partial rho, length held | partial rho, four controls held | partial rho, top-3 word controls held |")
        print("| --- | --- | --- | --- | --- |")
        for k in ["mean ms", *SHAPES]:
            rho = spearmanr(col[k], y).statistic
            p1 = partial(col[k], y, [col["words"]])
            p4 = partial(col[k], y, [col[c] for c in CONTROLS]) if k != "mean ms" else float("nan")
            p3 = partial(col[k], y, [col[c] for c in CONTROLS_3]) if k != "mean ms" else float("nan")
            print(f"| {k} | {rho:+.3f} | {p1:+.3f} | {p4:+.3f} | {p3:+.3f} |")


def simplifications(ref: Path) -> None:
    by_orig = []
    for split in ("test", "valid"):
        origs = (ref / f"asset.{split}.orig").read_text(encoding="utf-8").splitlines()
        simps = [(ref / f"asset.{split}.simp.{k}").read_text(encoding="utf-8").splitlines() for k in range(10)]
        for i, o in enumerate(origs):
            mo = shape(o)
            if mo is None:
                continue
            ms = [shape(s[i]) for s in simps if i < len(s) and s[i].strip()]
            ms = [m for m in ms if m]
            if ms:
                by_orig.append((mo, ms))
    print(f"\nASSET: {len(by_orig)} original sentences, {sum(len(m) for _, m in by_orig)} simplifications\n")
    print("| Measure | Simplification lower (share of pairs) | Mean change per original | p (per original) |")
    print("| --- | --- | --- | --- |")
    for k in ["mean ms", "longest word", *SHAPES]:
        pairs = [(o[k], s[k]) for o, ss in by_orig for s in ss]
        lower = sum(s < o for o, s in pairs) / len(pairs)
        per = [statistics.mean(s[k] - o[k] for s in ss) for o, ss in by_orig]
        p = wilcoxon([d for d in per if d]).pvalue
        print(f"| {k} | {lower:.0%} | {statistics.mean(per):+.2f} | {p:.2g} |")


if __name__ == "__main__":
    ratings(Path(sys.argv[1]))
    simplifications(Path(sys.argv[2]))
