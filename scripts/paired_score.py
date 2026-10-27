# /// script
# requires-python = ">=3.11"
# dependencies = ["readcost", "torch", "transformers", "scipy"]
# [tool.uv.sources]
# readcost = { path = "..", editable = true }  # this checkout, not the PyPI release
# ///
"""Score the paired rewrite experiment (docs/evaluation.md, "Paired rewrites").

    uv run scripts/paired_score.py ref/eval/analysis/paired

Needs the spaCy model (readcost setup) and downloads HuggingFaceTB/SmolLM2-135M.
"""
import json
import math
import re
import statistics
import sys
from pathlib import Path

import torch
from scipy.stats import wilcoxon
from transformers import AutoModelForCausalLM, AutoTokenizer

from readcost import Analyzer, Config, lexicon

OPT_IN = ["nominalization", "participial-clause", "repeated-frame", "denominal-verb"]
analyzer = Analyzer(Config(enable=OPT_IN))
tok = AutoTokenizer.from_pretrained("HuggingFaceTB/SmolLM2-135M")
lm = AutoModelForCausalLM.from_pretrained("HuggingFaceTB/SmolLM2-135M").eval()
PAIR = re.compile(r"(?<![\w-])([a-z]{2,})-([a-z]{2,})(?![\w-])")


def surprisal(text: str) -> float:
    """Mean surprisal in bits per token (the first token has no context and is skipped)."""
    ids = tok(text, return_tensors="pt").input_ids[:, :1024]
    with torch.no_grad():
        logits = lm(ids).logits[0, :-1]
    lp = torch.log_softmax(logits, -1).gather(1, ids[0, 1:, None])[:, 0]
    return float(-lp.mean() / math.log(2))


def measures(text: str) -> dict:
    r = analyzer.check_text(text, "markdown")
    words = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text)
    k = 1000 / max(r.words, 1)
    coined = [f"{a}-{b}" for a, b in PAIR.findall(text.lower())
              if not lexicon.is_established_pair(a, b) and not lexicon.is_lexicalized(a, b)]
    out = {"words": len(words), "cost_index": r.cost_index, "points": r.points,
           "word_len": statistics.mean(len(w) for w in words), "surprisal": surprisal(text),
           "coined_pairs_per_1k": 1000 * len(coined) / max(len(words), 1),
           "reading_ms_per_word": r.reading_ms_per_word, "reading_seconds": r.reading_seconds}
    counts = r.counts()
    for f in ["stacked-nouns", "long-dependency", "inanimate-subject", "reduced-object-relative",
              "hyphen-compound", "inline-list", *OPT_IN]:
        out[f] = counts.get(f, 0) * k
    return out


def main(d: Path) -> None:
    rows = []
    for path in sorted(d.glob("pairs-*.jsonl")):
        for line in path.read_text().splitlines():
            p = json.loads(line)
            rows.append({"model": p["model"], "source": p["source"], "i": p["i"],
                         "orig": measures(p["text"]), "rw": measures(p["rewrite"])})
    (d / "scores.json").write_text(json.dumps(rows, indent=1))
    # A paragraph readcost extracts nothing from (an HTML block in Markdown) has
    # no reading time and a cost index of 0; leave its pair out of every test.
    skipped = [r for r in rows if r["orig"]["reading_seconds"] is None or r["rw"]["reading_seconds"] is None]
    rows = [r for r in rows if r not in skipped]
    print(f"{len(skipped)} pairs left out: no prose extracted", file=sys.stderr)
    keys = list(rows[0]["orig"])
    lines = ["| measure | model | n | original median | rewrite median | median diff | rewrite higher | p |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for key in keys:
        for model in sorted({r["model"] for r in rows}):
            o = [r["orig"][key] for r in rows if r["model"] == model]
            w = [r["rw"][key] for r in rows if r["model"] == model]
            diff = [b - a for a, b in zip(o, w)]
            nz = [x for x in diff if x != 0]
            p = wilcoxon(nz).pvalue if len(nz) >= 6 else float("nan")
            higher = sum(x > 0 for x in diff) / len(diff)
            lines.append(f"| {key} | {model} | {len(o)} | {statistics.median(o):.3g} | {statistics.median(w):.3g} "
                         f"| {statistics.median(diff):+.3g} | {higher:.0%} | {p:.3g} |")
    (d / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
