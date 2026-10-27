"""Rebuild src/readcost/data/default_profile.json from a swatch of well-regarded writing.

    python3 scripts/fetch_eval_corpus.py ref/eval     # once; text stays outside the repository
    python3 scripts/build_default_profile.py ref/eval

The swatch is every other text, by id, from each essay, docs and README source
in the evaluation corpus: many writers and documentation sets rather than one
writer. The other half is held out (``held_out_ids``) so the evaluation can
judge the profile on texts it was not built from. The profile keeps only
numbers and source URLs, never text.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

from readcost.engine import Analyzer
from readcost.profile import Profile, build_profile

CATEGORIES = ("essay", "docs", "readme")


def split(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    """(swatch, held out): alternate texts within each source, ordered by id."""
    by_source: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        if e["category"] in CATEGORIES:
            by_source[e["source"]].append(e)
    swatch, held = [], []
    for source in sorted(by_source):
        for k, e in enumerate(sorted(by_source[source], key=lambda e: e["id"])):
            (swatch if k % 2 == 0 else held).append(e)
    return swatch, held


def held_out_ids(manifest: dict) -> set[str]:
    return {e["id"] for e in split(manifest["entries"])[1]}


def main() -> None:
    root = Path(sys.argv[1])
    manifest = json.loads((root / "manifest.json").read_text())
    swatch, _ = split(manifest["entries"])
    placeholder = Profile("placeholder", 0, 0, (0.0, 0.78, 0.42))
    prof = build_profile([str(root / e["path"]) for e in swatch], "swatch",
                         lambda: Analyzer(profile=placeholder))
    prof.sources = sorted(e["url"] for e in swatch)
    sources = sorted({e["source"] for e in swatch})
    prof.note = (f"{len(swatch)} texts from {len(sources)} sources of essays, documentation and READMEs "
                 f"({', '.join(sources)}), fetched for the evaluation corpus. Build a profile from your "
                 "own reference set with `readcost profile build`.")
    out = Path(__file__).resolve().parent.parent / "src/readcost/data/default_profile.json"
    out.write_text(prof.to_json() + "\n")
    print(f"{len(swatch)} texts, {prof.words} words, {prof.sentences} sentences, fit {prof.dep_fit}")


if __name__ == "__main__":
    main()
