"""Are model answers more templated than human answers? `readcost corpus` on HC3 answers.

    python3 scripts/eval_corpus_mode.py REF/datasets/hc3

Reads answers.jsonl from scripts/native_answers.py. For each source (the
human answers, the 2022 ChatGPT answers and each current model) it runs the
corpus measures over that source's answers, each cut to its first 120 words
of prose so that every source contributes about the same amount of text
(CR-POS grows with length), and prints one row per source.
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
    print("| Source | Texts | Words | CR-POS | Texts with a template | Tokens in templates | Top opener |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for src, rows in by.items():
        texts = [(f"{r['qid']}.md", " ".join(prose(r["text"]).split()[:WORDS])) for r in rows]
        rep = analyze(analyzer, texts)
        opener = rep.top_openers[0]["opener"] if rep.top_openers else "-"
        print(f"| {src} | {rep.texts} | {rep.words:,} | {rep.cr_pos:.2f} | {rep.template_rate:.0%} | "
              f"{rep.templates_per_token:.1%} | {opener} |")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
