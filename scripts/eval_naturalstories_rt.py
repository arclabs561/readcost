"""Do readcost findings predict self-paced reading time in Natural Stories?

    git clone --depth 1 https://github.com/languageMIT/naturalstories /tmp/data/naturalstories/repo
    uv run --group eval python scripts/eval_naturalstories_rt.py /tmp/data/naturalstories/repo

Data: the Natural Stories corpus (Futrell et al. 2021, Language Resources
and Evaluation 55), https://github.com/languageMIT/naturalstories, licence
CC BY-NC-SA 4.0. Ten stories of about 1,000 words, edited to contain rare
constructions, read word by word by 181 people on Mechanical Turk. The data
stays outside this repository. Files read:

    naturalstories_RTS/all_stories.tok     word, zone (position), item (story)
    naturalstories_RTS/processed_RTs.tsv   one row per reader and word; the
                                           corpus authors already dropped
                                           times under 100 ms or over 3,000 ms
                                           and readers with under five of six
                                           questions right
    probs/all_stories_gpt3.csv             GPT-3 (davinci) log probabilities

The repository's update of 12 May 2025 moved every reading time by one word
to correct a misalignment, so results from earlier copies do not compare.

Three analyses, each asking whether findings predict reading time beyond
word length, word frequency (readcost's Zipf table), GPT-3 surprisal and
position:

1. Sentences. Mean reading time per word of a sentence against its length,
   mean word length, mean frequency, mean surprisal, place in the story and
   the story, plus one findings term. Interval: bootstrap over sentences.
2. Words, by item. Mean log reading time of each word against its own and
   the previous word's length, frequency and surprisal, its position, and
   whether it lies inside a finding's span. Interval: bootstrap over
   sentences, since the words of one finding share a sentence.
3. Words, by reader. The same regression fitted to each reader's own log
   times; the coefficient is averaged over readers. Interval: bootstrap
   over readers.

A finding's span runs from its first token to its last; for long-dependency
that is the dependent, the gap and the head. Each sentence is checked alone,
so a compound is counted at every use.

What this can show: whether words and sentences that readcost flags are
read more slowly by these readers than their length, frequency and
predictability explain. What it cannot show: anything about comprehension
or rereading (self-paced reading has no regressions), about technical prose,
or about a rewrite. Rules that fire a handful of times get intervals too
wide to read.
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_signals import RULES, cluster_bootstrap, coefficient, detect_spans, ols  # noqa: E402

STRIP = ".,;:!?\"'()[]{}-"


def read_stories(root: Path) -> dict[int, list[str]]:
    """Story number -> its words in order, from all_stories.tok."""
    stories: dict[int, list[tuple[int, str]]] = {}
    with open(root / "naturalstories_RTS" / "all_stories.tok", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            stories.setdefault(int(row["item"]), []).append((int(row["zone"]), row["word"]))
    return {k: [w for _, w in sorted(v)] for k, v in stories.items()}


def read_surprisal(root: Path, stories: dict[int, list[str]]) -> dict[int, list[float]]:
    """Story number -> GPT-3 surprisal in bits of each word (NaN for the first word).

    The file has one row per subword token; a word's surprisal is the sum
    over its tokens. A story whose word count does not match is left out.
    """
    tokens: dict[int, list[tuple[str, str]]] = {}
    with open(root / "probs" / "all_stories_gpt3.csv", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            tokens.setdefault(int(row["story"]) + 1, []).append((row["token"], row["logprob"]))
    out = {}
    for story, toks in tokens.items():
        words: list[float] = []
        for k, (tok, lp) in enumerate(toks):
            value = -float(lp) / math.log(2) if lp else float("nan")
            if k == 0 or tok.startswith(" "):
                words.append(value)
            else:
                words[-1] += value
        if story in stories and len(words) == len(stories[story]):
            out[story] = words
    return out


def read_times(root: Path) -> list[tuple[str, int, int, float]]:
    """(reader, story, zone, RT in ms) for every kept observation."""
    out = []
    with open(root / "naturalstories_RTS" / "processed_RTs.tsv", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            out.append((row["WorkerId"], int(row["item"]), int(row["zone"]), float(row["RT"])))
    return out


def word_table(analyzer, zipf: dict, unseen: float, stories: dict[int, list[str]],
               surprisal: dict[int, list[float]]) -> list[dict]:
    """One row per word: story, zone, sentence, lexical measures and the rules whose span covers it."""
    rows = []
    for story in sorted(stories):
        words = stories[story]
        starts, pos = [], 0
        for w in words:
            starts.append(pos)
            pos += len(w) + 1
        sentences = detect_spans(analyzer, " ".join(words))
        k = 0
        for s_index, sent in enumerate(sentences):
            in_sentence = 0
            while k < len(words) and starts[k] < sent["end"]:
                lo, hi = starts[k], starts[k] + len(words[k])
                bare = words[k].strip(STRIP).lower()
                rows.append({
                    "story": story, "zone": k + 1, "sentence": (story, s_index), "position": in_sentence,
                    "letters": len(bare), "zipf": zipf.get(bare, unseen),
                    "surprisal": surprisal[story][k] if story in surprisal else float("nan"),
                    "checked": sent["checked"],
                    "rules": sorted({r for r, _, a, b in sent["findings"] if lo < b and hi > a}),
                    "sentence_rules": sorted({r for r, *_ in sent["findings"]}),
                    "final": False,
                })
                in_sentence += 1
                k += 1
            if in_sentence:
                rows[-1]["final"] = True
    return rows


def _controls(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """Word-level control matrix and the mask of rows that have every control.

    Columns: letters, frequency, surprisal, the same three for the previous
    word of the story (spillover), log position in the story, position in
    the sentence, sentence-final, and a dummy for each story but the first.
    """
    n = len(rows)
    base = np.array([[r["letters"], r["zipf"], r["surprisal"]] for r in rows], dtype=float)
    prev = np.full_like(base, np.nan)
    for k in range(1, n):
        if rows[k]["story"] == rows[k - 1]["story"]:
            prev[k] = base[k - 1]
    place = np.array([[math.log(r["zone"]), r["position"], float(r["final"])] for r in rows])
    stories = sorted({r["story"] for r in rows})
    dummies = np.array([[float(r["story"] == s) for s in stories[1:]] for r in rows]).reshape(n, -1)
    X = np.column_stack([base, prev, place, dummies])
    return X, ~np.isnan(X).any(axis=1)


def sentence_table(rows: list[dict], mean_rt: dict[tuple[int, int], float]) -> list[dict]:
    """One row per sentence with a reading time: ms per word, the controls and findings per rule."""
    by: dict[tuple, list[dict]] = {}
    for r in rows:
        by.setdefault(r["sentence"], []).append(r)
    out = []
    for key in sorted(by):
        ws = [w for w in by[key] if (w["story"], w["zone"]) in mean_rt and w["surprisal"] == w["surprisal"]]
        if len(ws) < 2:
            continue
        out.append({
            "sentence": key, "story": key[0], "index": key[1], "words": len(by[key]),
            "ms": float(np.mean([mean_rt[(w["story"], w["zone"])] for w in ws])),
            "letters": float(np.mean([w["letters"] for w in ws])),
            "zipf": float(np.mean([w["zipf"] for w in ws])),
            "surprisal": float(np.mean([w["surprisal"] for w in ws])),
            "rules": by[key][0]["sentence_rules"], "checked": by[key][0]["checked"],
        })
    return out


def sentence_fit(sents: list[dict], flag, resamples: int = 2000) -> dict:
    """Coefficient (ms per word) of ``flag(sentence)`` beyond the sentence-level controls."""
    stories = sorted({s["story"] for s in sents})
    controls = np.array([[math.log(s["words"]), s["letters"], s["zipf"], s["surprisal"], math.log(s["index"] + 1)]
                         + [float(s["story"] == k) for k in stories[1:]] for s in sents])
    y = np.array([s["ms"] for s in sents])
    target = np.array([float(flag(s)) for s in sents])
    r = coefficient(y, target, controls, np.arange(len(sents)), resamples)
    r["flagged"] = int((target > 0).sum())
    return r


def item_fit(rows: list[dict], log_rt: dict[tuple[int, int], float], inside, resamples: int = 1000) -> dict:
    """Coefficient (log ms) of ``inside(word)`` on each word's mean log RT; bootstrap over sentences."""
    X, ok = _controls(rows)
    have = np.array([(r["story"], r["zone"]) in log_rt for r in rows])
    keep = ok & have
    y = np.array([log_rt.get((r["story"], r["zone"]), np.nan) for r in rows])[keep]
    target = np.array([float(inside(r)) for r in rows])[keep]
    groups = np.array([f"{r['sentence'][0]}/{r['sentence'][1]}" for r in rows])[keep]
    r = coefficient(y, target, X[keep], groups, resamples)
    r["flagged"] = int(target.sum())
    return r


def reader_fit(rows: list[dict], times: list[tuple[str, int, int, float]], inside,
               resamples: int = 2000, seed: int = 0) -> dict:
    """Mean over readers of the coefficient (log ms) of ``inside(word)``; bootstrap over readers."""
    X, ok = _controls(rows)
    index = {(r["story"], r["zone"]): k for k, r in enumerate(rows)}
    target = np.array([float(inside(r)) for r in rows])
    by_reader: dict[str, tuple[list[int], list[float]]] = {}
    for reader, story, zone, rt in times:
        k = index.get((story, zone))
        if k is not None and ok[k]:
            ks, ys = by_reader.setdefault(reader, ([], []))
            ks.append(k)
            ys.append(math.log(rt))
    coefs = []
    for ks, ys in by_reader.values():
        ks = np.array(ks)
        if target[ks].sum() < 2 or len(ks) < 200:
            continue
        beta, _ = ols(np.column_stack([X[ks], target[ks]]), np.array(ys))
        coefs.append(beta[-1])
    coefs = np.array(coefs)
    if not len(coefs):
        return {"readers": 0, "coef": float("nan"), "ci": (float("nan"), float("nan"))}
    lo, hi = cluster_bootstrap(lambda k: float(coefs[k].mean()), np.arange(len(coefs)), resamples, seed)
    return {"readers": len(coefs), "coef": float(coefs.mean()), "ci": (lo, hi)}


def _pct(x: float) -> str:
    return f"{100 * (math.exp(x) - 1):+.1f}%"


def main(argv: list[str]) -> int:
    from readcost import Analyzer, Config
    from readcost.readtime import _zipf

    if len(argv) != 2:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    root = Path(argv[1])
    stories = read_stories(root)
    surprisal = read_surprisal(root, stories)
    times = read_times(root)
    zipf, unseen = _zipf()
    rows = word_table(Analyzer(Config()), zipf, unseen, stories, surprisal)

    sums: dict[tuple[int, int], list[float]] = {}
    for _, story, zone, rt in times:
        sums.setdefault((story, zone), []).append(rt)
    mean_rt = {k: float(np.mean(v)) for k, v in sums.items()}
    log_rt = {k: float(np.mean(np.log(v))) for k, v in sums.items()}

    sents = sentence_table(rows, mean_rt)
    readers = len({t[0] for t in times})
    print(f"{len(stories)} stories, {len(rows)} words, {len(sents)} sentences with times, "
          f"{len(times)} reading times from {readers} readers; surprisal for {len(surprisal)} stories")
    n_checked = sum(1 for s in sents if s["checked"])
    flagged = sum(1 for s in sents if s["rules"])
    print(f"readcost checked {n_checked} sentences and flagged {flagged} ({flagged / len(sents):.0%})")
    ms = np.array([s["ms"] for s in sents])
    print(f"sentence reading time: mean {ms.mean():.0f} ms per word, SD {ms.std():.0f}")

    base = sentence_fit(sents, lambda s: 0.0, resamples=1)
    print(f"\n1. sentences: controls alone explain R2 {base['r2_controls']:.3f} of ms per word")
    print("   term                      flagged   ms/word      95% CI             in SD    R2 gain")
    terms = [("any finding", lambda s: bool(s["rules"])),
             ("number of rules firing", lambda s: len(s["rules"]))]
    terms += [(rule, lambda s, rule=rule: rule in s["rules"]) for rule in RULES]
    for name, flag in terms:
        r = sentence_fit(sents, flag)
        if r["flagged"] < 5:
            print(f"   {name:<25} {r['flagged']:>5}     too few to fit")
            continue
        print(f"   {name:<25} {r['flagged']:>5}   {r['coef']:+7.1f}   {r['ci'][0]:+7.1f} to {r['ci'][1]:+6.1f}   "
              f"{r['standardized']:+.2f}   {r['r2_with'] - r['r2_controls']:+.4f}")

    X, ok = _controls(rows)
    have = np.array([(r["story"], r["zone"]) in log_rt for r in rows])
    y = np.array([log_rt.get((r["story"], r["zone"]), np.nan) for r in rows])
    beta, r2 = ols(X[ok & have], y[ok & have])
    print(f"\n   word-level controls: R2 {r2:.3f}; per letter {_pct(beta[1])}, per Zipf unit {_pct(beta[2])}, "
          f"per bit of surprisal {_pct(beta[3])}")

    print("\n2 and 3. words inside a finding's span, log reading time")
    print("   span                       words   by item   95% CI               by reader  95% CI            readers")
    spans = [("any finding", lambda r: bool(r["rules"])),
             ("any word of a flagged sentence", lambda r: bool(r["sentence_rules"]))]
    spans += [(rule, lambda r, rule=rule: rule in r["rules"]) for rule in RULES]
    for name, inside in spans:
        a = item_fit(rows, log_rt, inside)
        if a["flagged"] < 10:
            print(f"   {name:<30} {a['flagged']:>4}   too few to fit")
            continue
        b = reader_fit(rows, times, inside)
        print(f"   {name:<30} {a['flagged']:>4}   {_pct(a['coef']):>7}   {_pct(a['ci'][0])} to {_pct(a['ci'][1]):<8}   "
              f"{_pct(b['coef']):>7}   {_pct(b['ci'][0])} to {_pct(b['ci'][1]):<8} {b['readers']:>4}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
