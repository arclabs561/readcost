"""git hooks: pre-commit (staged prose, changed lines only) and commit-msg."""

from __future__ import annotations

import re
import subprocess
import sys

from .common import analyze, config_for

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.M)


def _git(*args: str) -> str:
    # Decode leniently: one non-UTF-8 staged file must not abort the whole check.
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


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


def _staged_files() -> list[tuple[str, tuple[str, ...]]]:
    """(new path, pathspec) for added, copied, modified and renamed files."""
    fields = _git("diff", "--cached", "--name-status", "--diff-filter=ACMR", "-M", "-z").split("\0")
    out, i = [], 0
    while i < len(fields) and fields[i]:
        status = fields[i]
        if status[:1] in ("R", "C"):
            old, new = fields[i + 1], fields[i + 2]
            out.append((new, (old, new)))
            i += 3
        else:
            out.append((fields[i + 1], (fields[i + 1],)))
            i += 2
    return out


def pre_commit(cfg) -> int:
    if cfg.hooks.mode == "off":
        return 0
    results = []
    for name, paths in _staged_files():
        if not cfg.wants(name):
            continue
        staged = _git("show", f":{name}")
        lines = None
        if cfg.hooks.edited_lines_only:
            # --no-color/--no-ext-diff: user config (color.ui=always, difftastic)
            # would otherwise hide the hunk headers. A rename needs both paths
            # in the pathspec so -M can pair them and report only edited lines.
            diff = _git("diff", "--cached", "-U0", "-M", "--no-color", "--no-ext-diff",
                        "--", *paths)
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
