"""A harness-neutral protocol, over stdin/stdout or in-process.

Request (stdin JSON): exactly one of ``text`` or ``path``, plus optional
``format``, ``lines`` ("10-24,40"), ``field`` and ``last`` (for transcripts),
and ``config`` (a path).

Response (stdout JSON)::

    {"verdict": "pass|advise|block", "cost_index": 12.5, "words": 240,
     "counts": {"stacked-nouns": 2}, "feedback": "<text for a model>",
     "findings": [{"line": 3, "feature": "...", "severity": "...", ...}]}

Exit status is 0 for any verdict and 2 for a malformed request, so callers
decide what a verdict means.
"""

from __future__ import annotations

import sys

from . import emit, read_payload


def review(text: str | None = None, *, path: str | None = None, fmt: str | None = None,
           lines: str | None = None, field: str | None = None, last: bool = False,
           config: str | None = None) -> dict:
    """In-process form of the protocol for Python harnesses."""
    from ..config import load_config
    from ..engine import Analyzer, parse_line_ranges
    from ..report import agent

    if (text is None) == (path is None):
        raise ValueError("give exactly one of text or path")
    cfg = load_config(config)
    analyzer = Analyzer(cfg)
    ranges = parse_line_ranges(lines)
    if text is not None:
        result = analyzer.check_text(text, fmt or "markdown", "<text>", lines=ranges,
                                     field_path=field, last_only=last)
    else:
        result = analyzer.check_file(path, fmt, lines=ranges, field_path=field, last_only=last)
    out = result.to_dict()
    out["feedback"] = agent([result], max_items=cfg.hooks.max_items, max_chars=cfg.hooks.max_chars)
    return out


def handle(event: str, rest: list[str]) -> int:
    req = read_payload()
    try:
        out = review(req.get("text"), path=req.get("path"), fmt=req.get("format"),
                     lines=req.get("lines"), field=req.get("field"), last=bool(req.get("last")),
                     config=req.get("config"))
    except ValueError as exc:
        print(f"readcost: {exc}", file=sys.stderr)
        return 2
    emit(out)
    return 0
