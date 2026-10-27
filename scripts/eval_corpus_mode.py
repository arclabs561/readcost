"""Are model answers more templated than human answers? `readcost corpus` on HC3 answers.

    python3 scripts/eval_corpus_mode.py REF/datasets/hc3
    python3 scripts/eval_corpus_mode.py --size REF/eval

Reads answers.jsonl from scripts/native_answers.py. For each source (the
human answers, the 2022 ChatGPT answers and each current model) it runs the
corpus measures over that source's answers, each cut to its first 120 words
of prose so that every source contributes about the same amount of text
(both measures depend on the amount of text), and prints one row per source.
``--size`` runs the measures on the first 5, 10, 20 and 40 essays of the
evaluation corpus, each cut to 300 words, to show how they move with corpus
size.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

from readcost import Analyzer, Config
from readcost.corpus import analyze
from readcost.extract import CODE, extract

WORDS = 120


def prose(markdown: str) -> str:
    return "\n\n".join(" ".join(w for w in seg.text.split() if CODE not in w)
                       for seg in extract(markdown, "answer.md", "markdown"))


def main(ref: Path) -> None:
    by = defaultdict(list)
    for a in map(json.loads, (ref / "answers.jsonl").read_text().splitlines()):
        if a["text"]:
            by[a["source"]].append(a)
    analyzer = Analyzer(Config())
    print("| Source | Texts | Words | CR-POS | Texts with a template | Templates per token | Top opener |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for src, rows in by.items():
        texts = [(f"{r['qid']}.md", " ".join(prose(r["text"]).split()[:WORDS])) for r in rows]
        rep = analyze(analyzer, texts)
        opener = rep.top_openers[0]["opener"] if rep.top_openers else "-"
        print(f"| {src} | {rep.texts} | {rep.words:,} | {rep.cr_pos:.2f} | {rep.template_rate:.0%} | "
              f"{rep.templates_per_token:.3f} | {opener} |")


def size(ref: Path) -> None:
    manifest = json.loads((ref / "manifest.json").read_text())
    essays = [e for e in manifest["entries"] if e["category"] == "essay"][:40]
    texts = [(e["path"], " ".join((ref / e["path"]).read_text(errors="ignore").split()[:300])) for e in essays]
    analyzer = Analyzer(Config())
    print("| Essays | Words | CR-POS | Templates per token |")
    print("| --- | --- | --- | --- |")
    for k in (5, 10, 20, 40):
        rep = analyze(analyzer, texts[:k])
        print(f"| {k} | {rep.words:,} | {rep.cr_pos:.2f} | {rep.templates_per_token:.3f} |")


if __name__ == "__main__":
    if sys.argv[1] == "--size":
        size(Path(sys.argv[2]))
    else:
        main(Path(sys.argv[1]))
