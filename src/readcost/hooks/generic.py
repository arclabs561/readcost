"""A harness-neutral protocol, over stdin/stdout or in-process.

Request (stdin JSON): exactly one of ``text`` or ``path``, plus optional
``format``, ``lines`` ("10-24,40"), ``field`` and ``last`` (for transcripts),
and ``config`` (a path).

Response (stdout JSON)::

    {"verdict": "pass|advise|block", "cost_index": 12.5, "words": 240,
     "counts": {"stacked-nouns": 2}, "feedback": "<text for a model>",
     "findings": [{"line": 3, "feature": "...", "severity": "...", ...}]}

Exit status is 0 for any verdict, so callers decide what a verdict means. A
malformed request exits 2 and an environment error (missing spaCy model,
unreadable file or config) exits 3; both print ``{"error": "..."}``.
"""

from __future__ import annotations

import json
import sys

from . import emit


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


def _fail(code: int, message: str) -> int:
    print(f"readcost: {message}", file=sys.stderr)
    emit({"error": message})
    return code


def handle(event: str, rest: list[str]) -> int:
    from ..engine import parse_line_ranges

    try:
        req = json.loads(sys.stdin.read() or "{}")
        if not isinstance(req, dict):
            raise ValueError("the request must be a JSON object")
        if (req.get("text") is None) == (req.get("path") is None):
            raise ValueError("give exactly one of text or path")
        parse_line_ranges(req.get("lines"))
    except (ValueError, TypeError, AttributeError) as exc:  # bad JSON or field types
        return _fail(2, str(exc))
    try:
        out = review(req.get("text"), path=req.get("path"), fmt=req.get("format"),
                     lines=req.get("lines"), field=req.get("field"), last=bool(req.get("last")),
                     config=req.get("config"))
    except Exception as exc:  # environment, not the request: model, file, config
        return _fail(3, f"{type(exc).__name__}: {exc}")
    emit(out)
    return 0
