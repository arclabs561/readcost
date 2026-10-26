"""Helpers shared by the harness adapters."""

from __future__ import annotations

import os
from pathlib import Path

from ..config import Config, load_config


def config_for(cwd: str | None) -> Config:
    return load_config(start=cwd or os.getcwd())


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


def analyze(cfg: Config, *, path: str, text: str | None = None, fmt: str | None = None,
            lines: list[tuple[int, int]] | None = None):
    from ..engine import Analyzer

    analyzer = Analyzer(cfg)
    if text is None:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
    return analyzer.check_text(text, fmt, path, lines=lines)


def feedback(cfg: Config, result) -> str:
    from ..report import agent

    return agent([result], max_items=cfg.hooks.max_items, max_chars=cfg.hooks.max_chars)


def summary_line(result) -> str:
    counts = result.counts()
    parts = ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
    return (f"readcost: {len(result.findings)} hard-to-read constructions in "
            f"{result.words} words ({parts}); verdict {result.verdict}")
