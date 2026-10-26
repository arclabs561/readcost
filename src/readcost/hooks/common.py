"""Helpers shared by the harness adapters."""

from __future__ import annotations

import difflib
import os
import re
from pathlib import Path

from ..config import Config, find_config, load_config


def config_for(cwd: str | None, path: str | None = None) -> Config:
    """Config for an edited file: look up from its directory first, then from cwd."""
    cwd = cwd or os.getcwd()
    if path and not os.environ.get("READCOST_CONFIG"):
        full = Path(cwd, path).resolve()
        if find_config(full) is not None:
            return load_config(start=str(full if full.is_dir() else full.parent))
    return load_config(start=cwd)


def relpath(path: str, cwd: str | None) -> str:
    try:
        return os.path.relpath(path, cwd) if cwd and os.path.isabs(path) else path
    except ValueError:  # different drive on Windows
        return path


def lines_of(text: str, needle: str) -> list[tuple[int, int]]:
    """Line ranges (1-based, inclusive) where ``needle`` occurs in ``text``."""
    if not needle:
        return []
    out = []
    start = 0
    span = needle.count("\n")
    while True:
        i = text.find(needle, start)
        if i < 0:
            break
        first = text.count("\n", 0, i) + 1
        out.append((first, first + span))
        start = i + max(len(needle), 1)
    return out


def changed_lines(old: str, new: str) -> list[tuple[int, int]]:
    """Line ranges (1-based, inclusive) of ``new`` that differ from ``old``.

    A pure deletion marks the line after the cut, where two sentences may now
    run together. Empty when the texts have the same lines.
    """
    a, b = old.splitlines(), new.splitlines()
    out = []
    for tag, _, _, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("replace", "insert"):
            out.append((j1 + 1, j2))
        elif tag == "delete" and b:
            line = min(j1 + 1, len(b))
            out.append((line, line))
    return out


# One Analyzer (one spaCy load) per config, so a pre-commit run over many files
# loads the model once.
_cached: tuple[Config, object] | None = None


def analyze(cfg: Config, *, path: str, text: str | None = None, fmt: str | None = None,
            lines: list[tuple[int, int]] | None = None):
    global _cached
    from .. import engine

    if _cached is None or _cached[0] is not cfg:
        _cached = (cfg, engine.Analyzer(cfg))
    analyzer = _cached[1]
    if text is None:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
    return analyzer.check_text(text, fmt, path, lines=lines)


def feedback(cfg: Config, result, *, where: str = "", head: str = "", suffix: str = "") -> str:
    """Findings for a model, within ``hooks.max_chars`` including ``suffix``.

    ``where`` qualifies line numbers ("of the new text") when they are not file
    lines; ``head`` replaces the opening instruction. Truncation runs last.
    """
    from ..report import agent

    body = agent([result], max_items=cfg.hooks.max_items, max_chars=1 << 30)
    if head:
        body = body.replace("Rewrite these sentences", head, 1)
    if where:
        body = re.sub(r"^- line (\d+) \[", rf"- line \1 {where} [", body, flags=re.MULTILINE)
    room = cfg.hooks.max_chars - len(suffix)
    if len(body) > room:
        body = body[: max(room - 3, 0)] + "..."
    return body + suffix


def summary_line(result) -> str:
    counts = result.counts()
    parts = ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
    return (f"readcost: {len(result.findings)} hard-to-read constructions in "
            f"{result.words} words ({parts}); verdict {result.verdict}")
