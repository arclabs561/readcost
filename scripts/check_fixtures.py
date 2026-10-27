"""Check that no test fixture copies text from the third-party evaluation corpora.

    python3 scripts/check_fixtures.py REF [REF ...]

Every string of eight or more words in tests/*.py is searched, whitespace
collapsed, in the Markdown, reStructuredText, HTML and text files under each
REF directory (the corpora that scripts/fetch_*.py download, kept outside the
repository). Exits 1 and prints each match. Test sentences should be written
for the test, or come from text whose owner allows it (this repository, the
author's own repositories); evaluation data stays outside the repository and
is fetched by scripts.
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_strings() -> list[tuple[str, str]]:
    out = []
    for path in sorted((ROOT / "tests").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = " ".join(node.value.split())
                if len(text.split()) >= 8:
                    out.append((path.name, text))
    return out


def corpus(roots: list[Path]) -> str:
    parts = []
    for root in roots:
        for p in root.rglob("*"):
            if (p.is_file() and p.suffix in (".md", ".rst", ".txt", ".html")
                    and "results" not in p.parts and p.stat().st_size < 3_000_000):
                parts.append(" ".join(p.read_text(errors="ignore").split()))
    return "\n".join(parts)


def main() -> int:
    blob = corpus([Path(a) for a in sys.argv[1:]])
    if not blob:
        print("no corpus files found under", " ".join(sys.argv[1:]), file=sys.stderr)
        return 2
    hits = [(name, text) for name, text in test_strings() if text[:60] in blob]
    for name, text in hits:
        print(f"{name}: copied from a corpus: {text[:100]}")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
