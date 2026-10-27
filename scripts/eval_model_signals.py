# /// script
# requires-python = ">=3.11"
# dependencies = ["readcost", "torch", "transformers", "scipy", "numpy"]
# ///
"""Model-based uncertainty and difficulty signals, tested against human judgments.

    uv run --with-editable . scripts/eval_model_signals.py cefr REF/datasets/cefr-sp
    uv run --with-editable . scripts/eval_model_signals.py asset REF/datasets/asset
    uv run --with-editable . scripts/eval_model_signals.py answers REF/datasets/hc3

Per text it computes, from two small causal language models of different
families (HuggingFaceTB/SmolLM2-135M and gpt2): mean and maximum surprisal
in bits per token, the standard deviation of surprisal (uniform information
density says even is easier), and mean predictive entropy (the model's
uncertainty about the next token). It also runs a readability regressor
(agentlans/deberta-v3-xsmall-readability, grade level; trained on FineWeb-Edu,
TinyStories, Wikipedia and arXiv paragraphs) and, outside CEFR-SP, a sentence
CEFR classifier (AbdullahBarayan/ModernBERT-base-doc_sent_en-Cefr; expected
level and the entropy of its class distribution). The CEFR classifier's
training data is not documented and may include CEFR-SP, so it is not scored
there. readcost's predicted ms per word is included as the baseline.

- ``cefr``: Spearman rho with the two teachers' mean CEFR level on the
  Wiki-Auto sentences of CEFR-SP, the partial rho controlling for length,
  and the mean rho within length bins (scripts/eval_sentence_ratings.py).
- ``asset``: 600 ASSET original sentences (seed 1) against their first human
  simplification: share of pairs where each signal goes down, and Wilcoxon p.
- ``answers``: scripts/native_answers.py answers; each model's answers
  against the human answer to the same question.

Data stays outside the repository; only aggregates are printed.
"""

import json
import math
import random
import re
import statistics
import sys
from pathlib import Path

import numpy as np
import torch
from scipy.stats import spearmanr, wilcoxon
from transformers import AutoModelForCausalLM, AutoModelForSequenceClassification, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_sentence_ratings import load, partial, within_bins  # noqa: E402

from readcost import readtime  # noqa: E402

DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
LMS = ("HuggingFaceTB/SmolLM2-135M", "gpt2")
READABILITY = "agentlans/deberta-v3-xsmall-readability"
CEFR = "AbdullahBarayan/ModernBERT-base-doc_sent_en-Cefr"
LN2 = math.log(2)


def lm_signals(name: str, texts: list[str]) -> list[dict]:
    tok = AutoTokenizer.from_pretrained(name)
    model = AutoModelForCausalLM.from_pretrained(name).to(DEVICE).eval()
    out = []
    for text in texts:
        ids = tok(tok.bos_token + text if tok.bos_token else text, return_tensors="pt",
                  truncation=True, max_length=512).input_ids.to(DEVICE)
        with torch.no_grad():
            logp = torch.log_softmax(model(ids).logits[0, :-1].float(), -1)
        target = ids[0, 1:]
        s = (-logp[torch.arange(len(target)), target] / LN2).cpu().numpy()
        ent = (-(logp.exp() * logp).sum(-1) / LN2).cpu().numpy()
        out.append({"surprisal": float(s.mean()), "max_surprisal": float(s.max()),
                    "surprisal_sd": float(s.std()), "entropy": float(ent.mean())})
    return out


def regressor(texts: list[str]) -> list[float]:
    tok = AutoTokenizer.from_pretrained(READABILITY)
    model = AutoModelForSequenceClassification.from_pretrained(READABILITY).to(DEVICE).eval()
    out = []
    for text in texts:
        with torch.no_grad():
            out.append(float(model(**tok(text, return_tensors="pt", truncation=True).to(DEVICE)).logits.squeeze()))
    return out


def cefr_classifier(texts: list[str]) -> list[dict]:
    tok = AutoTokenizer.from_pretrained(CEFR)
    model = AutoModelForSequenceClassification.from_pretrained(CEFR).to(DEVICE).eval()
    out = []
    for text in texts:
        with torch.no_grad():
            p = torch.softmax(model(**tok(text, return_tensors="pt", truncation=True).to(DEVICE)).logits[0], -1)
        p = p.float().cpu().numpy()
        out.append({"cefr_expected": float((p * np.arange(1, len(p) + 1)).sum()),
                    "cefr_entropy": float(-(p * np.log2(np.clip(p, 1e-12, 1))).sum())})
    return out


def signals(texts: list[str], with_cefr: bool) -> list[dict]:
    rows = [{} for _ in texts]
    for name in LMS:
        short = name.split("/")[-1]
        for r, s in zip(rows, lm_signals(name, texts)):
            r.update({f"{short} {k}": v for k, v in s.items()})
    for r, g in zip(rows, regressor(texts)):
        r["readability grade"] = g
    if with_cefr:
        for r, c in zip(rows, cefr_classifier(texts)):
            r.update(c)
    for r, text in zip(rows, texts):
        # Each sentence read from its own start: the model's word-position
        # feature makes per-paragraph estimates depend on how a text is split
        # into paragraphs (model answers have many short ones).
        sents = [x for x in re.split(r"(?<=[.!?])\s+", text) if x.split()]
        words, ms = readtime.estimate(sents)
        r["readcost ms per word"] = ms / words if words else float("nan")
    return rows


def cefr(ref: Path) -> None:
    rows = [r for f in sorted(ref.glob("CEFR-SP_Wikiauto_*.txt")) for r in load(f)]
    texts = [t for t, _, _ in rows]
    level = [(a + b) / 2 for _, a, b in rows]
    length = [len(t.split()) for t in texts]
    sig = signals(texts, with_cefr=False)
    print(f"{len(texts)} Wiki-Auto sentences; rho with the teachers' mean CEFR level\n")
    print("| Signal | rho | partial rho (length held) | mean rho within length bins |")
    print("| --- | --- | --- | --- |")
    print(f"| length in words | {spearmanr(length, level).statistic:+.2f} | | |")
    for k in sig[0]:
        x = [s[k] for s in sig]
        within, bins = within_bins(x, level, length)
        print(f"| {k} | {spearmanr(x, level).statistic:+.2f} | {partial(x, level, length):+.2f} | "
              f"{within:+.2f} ({bins} bins) |")


def asset(ref: Path) -> None:
    origs = (ref / "asset.test.orig").read_text().splitlines() + (ref / "asset.valid.orig").read_text().splitlines()
    simps = (ref / "asset.test.simp.0").read_text().splitlines() + (ref / "asset.valid.simp.0").read_text().splitlines()
    pairs = [(o, s) for o, s in zip(origs, simps) if o.strip() and s.strip() and o.strip() != s.strip()]
    pairs = random.Random(1).sample(pairs, min(600, len(pairs)))
    so = signals([o for o, _ in pairs], with_cefr=True)
    ss = signals([s for _, s in pairs], with_cefr=True)
    print(f"{len(pairs)} ASSET pairs (original against its first human simplification)\n")
    print("| Signal | Original median | Simplification median | Lower in the simplification | p |")
    print("| --- | --- | --- | --- | --- |")
    for k in so[0]:
        d = [b[k] - a[k] for a, b in zip(so, ss)]
        nz = [x for x in d if x]
        print(f"| {k} | {statistics.median(a[k] for a in so):.3g} | {statistics.median(b[k] for b in ss):.3g} | "
              f"{sum(x < 0 for x in d) / len(d):.0%} | {wilcoxon(nz).pvalue:.2g} |")


def prose(markdown: str) -> str:
    """The prose of a Markdown answer, as readcost reads it: no markup, code spans left out."""
    from readcost.extract import CODE, extract

    return "\n".join(" ".join(w for w in seg.text.split() if CODE not in w)
                     for seg in extract(markdown, "answer.md", "markdown"))


def answers(ref: Path) -> None:
    # Model answers use Markdown (headings, bold, lists); human answers are
    # plain. Score the prose of both, or the markup moves every signal.
    rows = [a for a in map(json.loads, (ref / "answers.jsonl").read_text().splitlines()) if a["text"]]
    rows = [a | {"text": prose(a["text"])} for a in rows]
    rows = [a for a in rows if len(a["text"].split()) >= 40]
    sig = signals([a["text"] for a in rows], with_cefr=True)
    by: dict[str, dict[str, dict]] = {}
    for a, s in zip(rows, sig):
        by.setdefault(a["source"], {})[a["qid"]] = s
    human = by["human"]
    keys = list(sig[0])
    print("Median per source; in brackets the share of questions where the answer is above the human one\n")
    print("| Source | " + " | ".join(keys) + " |")
    print("| --- | " + " | ".join("---" for _ in keys) + " |")
    for src, qs in by.items():
        cells = []
        for k in keys:
            med = statistics.median(v[k] for v in qs.values())
            if src == "human":
                cells.append(f"{med:.3g}")
            else:
                pairs = [(qs[q][k], human[q][k]) for q in qs if q in human]
                cells.append(f"{med:.3g} ({sum(a > b for a, b in pairs) / len(pairs):.0%})")
        print(f"| {src} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    {"cefr": cefr, "asset": asset, "answers": answers}[sys.argv[1]](Path(sys.argv[2]))
