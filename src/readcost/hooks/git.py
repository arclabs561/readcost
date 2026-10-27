"""git hooks: pre-commit (staged prose, changed lines only) and commit-msg.

pre-commit with no file arguments (a plain git hook) judges the changed lines
of every staged file. With file arguments (the pre-commit framework) it judges
the changed lines of each named file that has staged changes, and the whole
working-tree file otherwise, which is what ``pre-commit run --all-files`` and
pre-commit.ci need: they pass every file and stage nothing.
"""

from __future__ import annotations

import re
import subprocess
import sys

from .common import analyze, config_for

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


def _git(*args: str) -> str:
    # Decode leniently: one non-UTF-8 staged file must not abort the whole check.
    # --literal-pathspecs: a file named "[WIP] plan.md" must not match "W plan.md".
    return subprocess.run(["git", "--literal-pathspecs", *args], check=True, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def handle(event: str, rest: list[str]) -> int:
    cfg = config_for(None)
    if event == "commit-msg":
        return commit_msg(rest[0] if rest else ".git/COMMIT_EDITMSG", cfg)
    if event in ("pre-commit", ""):
        return pre_commit(cfg, rest)
    print(f"readcost: unknown git event {event!r}", file=sys.stderr)
    return 0


def _report(results, cfg) -> int:
    from ..report import full, use_color

    shown = [r for r in results if r.verdict != "pass"]
    if shown:
        print(full(shown, color=use_color(sys.stderr)), file=sys.stderr)
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


def pre_commit(cfg, files: list[str] | None = None) -> int:
    if cfg.hooks.mode == "off":
        return 0
    staged = dict(_staged_files())
    results = []
    for name in files or list(staged):
        if not cfg.wants(name):
            continue
        if name in staged:
            result = _check_staged(cfg, name, staged[name])
        else:
            with open(name, encoding="utf-8", errors="replace") as fh:
                result = analyze(cfg, path=name, text=fh.read())
        if result is not None:
            results.append(result)
    return _report(results, cfg)


def _check_staged(cfg, name: str, paths: tuple[str, ...]):
    """The staged content of ``name``, judged on its changed lines; None if none changed."""
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
            return None
    return analyze(cfg, path=name, text=staged, lines=lines)


def commit_msg(path: str, cfg) -> int:
    if cfg.hooks.mode == "off":
        return 0
    with open(path, encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
    return _report([analyze(cfg, path=path, text=text, fmt="commit")], cfg)
