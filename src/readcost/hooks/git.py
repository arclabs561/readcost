"""git hooks: pre-commit (staged prose, changed lines only) and commit-msg."""

from __future__ import annotations

import re
import subprocess
import sys

from .common import analyze, config_for

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.M)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def handle(event: str, rest: list[str]) -> int:
    cfg = config_for(None)
    if event == "commit-msg":
        return commit_msg(rest[0] if rest else ".git/COMMIT_EDITMSG", cfg)
    if event in ("pre-commit", ""):
        return pre_commit(cfg)
    print(f"readcost: unknown git event {event!r}", file=sys.stderr)
    return 0


def _report(results, cfg) -> int:
    from ..report import text

    shown = [r for r in results if r.verdict != "pass"]
    if shown:
        print(text(shown), file=sys.stderr)
    blocked = any(r.verdict == "block" for r in results)
    if blocked and cfg.hooks.mode == "block":
        print("readcost: commit blocked; rewrite the flagged sentences or commit with --no-verify",
              file=sys.stderr)
        return 1
    return 0


def pre_commit(cfg) -> int:
    if cfg.hooks.mode == "off":
        return 0
    names = _git("diff", "--cached", "--name-only", "--diff-filter=ACM", "-z").split("\0")
    results = []
    for name in filter(None, names):
        if not cfg.wants(name):
            continue
        staged = _git("show", f":{name}")
        lines = None
        if cfg.hooks.edited_lines_only:
            diff = _git("diff", "--cached", "-U0", "--", name)
            lines = [(int(s), int(s) + max(int(c or 1), 1) - 1) for s, c in HUNK.findall(diff) if c != "0"]
            if not lines:
                continue
        results.append(analyze(cfg, path=name, text=staged, lines=lines))
    return _report(results, cfg)


def commit_msg(path: str, cfg) -> int:
    if cfg.hooks.mode == "off":
        return 0
    with open(path, encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
    return _report([analyze(cfg, path=path, text=text, fmt="commit")], cfg)
