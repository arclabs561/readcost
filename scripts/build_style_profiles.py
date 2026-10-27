"""Build the reference profiles in src/readcost/data/profiles from the evaluation corpus.

    python3 scripts/fetch_eval_corpus.py ref/eval     # once; text stays outside the repository
    python3 scripts/build_style_profiles.py ref/eval

One profile per documentation set or genre, so `readcost style` can compare a
document with a style a reader knows. Each profile keeps only numbers (rule
rates per 1,000 words, the dependency-length fit, predicted ms per word,
words per sentence) and the source URLs, never text. Rebuild after a rule
changes, since the rates depend on readcost's version.
"""

import json
import sys
from pathlib import Path

from readcost import __version__
from readcost.engine import Analyzer
from readcost.profile import Profile, build_profile

OUT = Path(__file__).resolve().parent.parent / "src/readcost/data/profiles"
# profile name -> (corpus sources, description)
PROFILES = {
    "rust-book": (["rust-book"], "The Rust Programming Language (the Rust book)"),
    "go-docs": (["effective-go", "go-blog"], "Effective Go and the Go blog"),
    "python-docs": (["python-tutorial"], "the Python tutorial"),
    "django-docs": (["django-docs"], "the Django documentation"),
    "sqlite-docs": (["sqlite-docs"], "the SQLite documentation"),
    "stripe-docs": (["stripe-docs"], "the Stripe documentation"),
    "govuk": (["govuk-guidance"], "GOV.UK guidance for writing to GOV.UK standards"),
    "readmes": (["github-readmes"], "READMEs of widely used open-source projects"),
    "essays": (["andrew-gallant", "brendan-gregg", "dan-abramov", "dan-luu", "eli-bendersky", "hillel-wayne",
                "joel-spolsky", "julia-evans", "martin-fowler", "paul-graham", "raymond-chen", "russ-cox",
                "simon-willison"], "essays by thirteen well-regarded technical writers"),
}


def main(root: Path) -> None:
    manifest = json.loads((root / "manifest.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    placeholder = Profile("placeholder", 0, 0, (0.0, 0.78, 0.42))
    for name, (sources, what) in PROFILES.items():
        entries = [e for e in manifest["entries"] if e["source"] in sources]
        if not entries:
            print(f"{name}: no texts for {sources}", file=sys.stderr)
            continue
        prof = build_profile([str(root / e["path"]) for e in entries], name, lambda: Analyzer(profile=placeholder))
        prof.sources = sorted(e["url"] for e in entries)
        prof.note = (f"{len(entries)} texts from {what}, fetched for readcost's evaluation corpus; "
                     f"rates measured with readcost {__version__}.")
        (OUT / f"{name}.json").write_text(prof.to_json() + "\n")
        print(f"{name}: {len(entries)} texts, {prof.words} words, {prof.reading_ms_per_word} ms per word")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
