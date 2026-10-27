"""Render readcost's coloured terminal output for a constructed example as an SVG for the README.

    python3 scripts/terminal_svg.py            # rewrites docs/images/check.svg
    python3 scripts/terminal_svg.py --check    # exits 1 when the file is stale

GitHub cannot show terminal colours in Markdown, so the README shows this
image. The example text is written for it; tests/test_terminal_svg.py fails
when the committed image no longer matches what readcost prints.
"""

import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images" / "check.svg"
EXAMPLE = ("The shard compaction retry budget is the setting the operator changes most.\n"
           "It sets the limit the scheduler uses for every retry.\n")

# readcost's SGR codes (report._CODES) as colours for a dark background.
COLORS = {"31": "#ff7b72", "32": "#7ee787", "33": "#e3b341", "34": "#79c0ff", "36": "#56d4dd"}
FG, BG = "#e6edf3", "#0d1117"
CHAR_W, LINE_H, PAD = 8.6, 19, 14  # glyph widths vary by font; the width keeps 3 spare columns


def terminal_output() -> str:
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "notes.md").write_text(EXAMPLE)
        proc = subprocess.run([sys.executable, "-m", "readcost", "check", "notes.md", "--color", "always"],
                              cwd=d, capture_output=True, text=True, check=False)
    return "$ readcost check notes.md\n" + proc.stdout.rstrip("\n")


def spans(line: str) -> list[tuple[str, str | None, bool]]:
    """(text, colour, bold) runs of one line of SGR-coloured text."""
    out, color, bold = [], None, False
    for part in re.split(r"(\x1b\[[0-9;]*m)", line):
        m = re.fullmatch(r"\x1b\[([0-9;]*)m", part)
        if not m:
            if part:
                out.append((part, color, bold))
            continue
        for code in (m.group(1) or "0").split(";"):
            if code == "0":
                color, bold = None, False
            elif code == "1":
                bold = True
            elif code in COLORS:
                color = COLORS[code]
    return out


def svg(text: str) -> str:
    lines = text.split("\n")
    width = max(len(re.sub(r"\x1b\[[0-9;]*m", "", ln)) for ln in lines)
    w, h = round((width + 3) * CHAR_W + 2 * PAD), len(lines) * LINE_H + 2 * PAD
    rows = []
    for i, line in enumerate(lines):
        tspans = ""
        for t, c, b in spans(line):
            attrs = (f' fill="{c}"' if c else "") + (' font-weight="bold"' if b else "")
            tspans += f"<tspan{attrs}>{html.escape(t)}</tspan>"
        rows.append(f'<text x="{PAD}" y="{PAD + (i + 1) * LINE_H - 5}" xml:space="preserve">{tspans}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="readcost check output">\n'
            f'<rect width="100%" height="100%" rx="6" fill="{BG}"/>\n'
            f'<g font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="14" fill="{FG}">\n'
            + "\n".join(rows) + "\n</g>\n</svg>\n")


def main(argv: list[str]) -> int:
    new = svg(terminal_output())
    if "--check" in argv:
        if not OUT.exists() or OUT.read_text() != new:
            print(f"{OUT.relative_to(ROOT)} is stale; run scripts/terminal_svg.py", file=sys.stderr)
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(new)
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
