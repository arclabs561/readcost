"""Print the README's "Real findings" block from public READMEs at pinned commits.

    python scripts/readme_gallery.py

Each entry names a sentence that a rule flags in a public repository, so the
README shows real output on real prose. Commits are pinned so the output does
not move when those READMEs change. Paste the output into README.md.
"""

from __future__ import annotations

import urllib.request

from readcost import report
from readcost.config import Config
from readcost.engine import Analyzer, Result

# (repository under github.com/arclabs561, commit, line, rules shown)
ENTRIES = [
    ("cnk", "e62ce5f08c3fd6f9999b49fdf929ee236aef5454", 61,
     ("stacked-nouns", "hyphen-compound", "reduced-object-relative")),
    ("lexir", "fe578e4061f95447f8dc125a3133ed920de72eb7", 7, ("inanimate-subject",)),
    ("durability", "f213db600007709928db3d9aafba8e6c19a7fdfe", 8, ("inline-list",)),
]


def fetch(repo: str, sha: str) -> str:
    url = f"https://raw.githubusercontent.com/arclabs561/{repo}/{sha}/README.md"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode()


def main() -> None:
    analyzer = Analyzer(Config())
    sources: dict[tuple[str, str], Result] = {}
    blocks: list[str] = []
    for repo, sha, line, rules in ENTRIES:
        if (repo, sha) not in sources:
            sources[repo, sha] = analyzer.check_text(fetch(repo, sha), "markdown", f"{repo}/README.md")
        full = sources[repo, sha]
        found = [f for f in full.findings if f.line == line and f.feature in rules]
        if {f.feature for f in found} != set(rules):
            raise SystemExit(f"{repo}:{line}: expected {rules}, got {[f.feature for f in found]}")
        # One block per finding: what full output prints before its summary lines.
        blocks += [report.full([Result(path=full.path, findings=[f], source=full.source)]).split("\n\n")[0]
                   for f in found]
    print("\n\n".join(blocks))


if __name__ == "__main__":
    main()
