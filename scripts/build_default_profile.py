"""Rebuild src/readcost/data/default_profile.json from BurntSushi READMEs.

    git clone --depth 1 https://github.com/BurntSushi/<repo> ref/<repo>   # for each repo below
    python3 scripts/build_default_profile.py ref
"""

import sys
from pathlib import Path

from readcost.engine import Analyzer
from readcost.profile import Profile, build_profile

REPOS = ["aho-corasick", "bstr", "byteorder", "fst", "jiff", "memchr", "regex",
         "ripgrep", "rust-csv", "same-file", "termcolor", "walkdir"]

root = Path(sys.argv[1])
paths = [str(root / r / "README.md") for r in REPOS]
placeholder = Profile("placeholder", 0, 0, (0.0, 0.78, 0.42))
prof = build_profile(paths, "readme-burntsushi", lambda: Analyzer(profile=placeholder))
prof.sources = [f"github.com/BurntSushi/{r}/README.md" for r in REPOS]
prof.note = ("Twelve READMEs from github.com/BurntSushi, shallow clones of 2026-10-26. "
             "One writer; build a profile from your own reference set with `readcost profile build`.")
out = Path(__file__).resolve().parent.parent / "src/readcost/data/default_profile.json"
out.write_text(prof.to_json() + "\n")
print(prof.to_json())
