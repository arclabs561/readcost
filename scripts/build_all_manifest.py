"""Write one manifest line per text for every evaluation corpus, so rules and speed can run over all of them.

    PYTHONPATH=src python3 scripts/build_all_manifest.py REF       # writes REF/broad/ALL.jsonl

Reads ``REF/eval/manifest.json`` (the corpus of scripts/fetch_eval_corpus.py)
and every ``REF/broad/*/manifest.json``, and writes ``REF/broad/ALL.jsonl``
with, per text: ``path`` (absolute), ``format``, ``category``, ``source``,
``licence``, ``corpus`` (``eval`` or the broad subdirectory), ``id``,
``tokens`` (whitespace-separated tokens in the file) and ``words``, the word
count readcost reported when the text was scored (read from
``REF/eval/results/texts.jsonl`` and every ``REF/broad/results*/texts.jsonl``;
null if it has not been). Prints the totals.
Only paths and counts are written; no text.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cached_words(*paths: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    for p in paths:
        if p.exists():
            for line in p.read_text().splitlines():
                r = json.loads(line)
                out[r["id"]] = r["words"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ref", type=Path)
    args = ap.parse_args()
    ref: Path = args.ref
    broad = ref / "broad"
    words = cached_words(ref / "eval" / "results" / "texts.jsonl", *sorted(broad.glob("results*/texts.jsonl")))
    manifests = [("eval", ref / "eval" / "manifest.json")]
    manifests += [(mf.parent.name, mf) for mf in sorted(broad.glob("*/manifest.json"))]
    lines, missing = [], 0
    totals = {"texts": 0, "tokens": 0, "words": 0}
    for corpus, mf in manifests:
        for e in json.loads(mf.read_text())["entries"]:
            path = mf.parent / e["path"]
            if not path.exists():
                missing += 1
                continue
            tokens = len(path.read_text(encoding="utf-8", errors="replace").split())
            w = words.get(e["id"])
            lines.append({"path": str(path), "format": e.get("format", "text"), "category": e["category"],
                          "source": e["source"], "licence": e.get("license"), "corpus": corpus, "id": e["id"],
                          "tokens": tokens, "words": w})
            totals["texts"] += 1
            totals["tokens"] += tokens
            totals["words"] += w or 0
    out = broad / "ALL.jsonl"
    out.write_text("".join(json.dumps(x) + "\n" for x in lines))
    out.chmod(0o600)
    unscored = sum(x["words"] is None for x in lines)
    print(f"{out}: {totals['texts']} texts, {totals['tokens']:,} tokens, {totals['words']:,} readcost words "
          f"({unscored} texts not scored, {missing} manifest paths missing)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
