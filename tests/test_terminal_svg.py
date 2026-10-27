"""The README's terminal image matches what readcost prints today."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _script():
    spec = importlib.util.spec_from_file_location("terminal_svg", ROOT / "scripts" / "terminal_svg.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_spans_follow_readcost_colour_codes():
    t = _script()
    assert t.spans("\x1b[1;33mwarn\x1b[0m plain \x1b[1mbold\x1b[0m") == [
        ("warn", t.COLORS["33"], True), (" plain ", None, False), ("bold", None, True)]


def test_committed_image_is_current():
    # Rerun scripts/terminal_svg.py when output formatting or the rules change.
    assert _script().main(["--check"]) == 0
