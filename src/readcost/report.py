"""Output formats: full, concise, json, sarif, github, agent, pr-comment."""

from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

from .engine import Result
from .features import FEATURES

OUTPUTS = ("full", "concise", "json", "sarif", "github", "agent", "pr-comment")
REPO_URL = "https://github.com/arclabs561/readcost"
RULES_URL = REPO_URL + "#what-it-flags"
FEEDBACK_URL = REPO_URL + "/issues/new?template=false-positive.yml"
FEEDBACK_LINE = f"readcost: a finding is wrong? Report it at {FEEDBACK_URL}"
# The action finds its own PR comment by this first line.
COMMENT_MARKER = "<!-- readcost -->"


def render(results: list[Result], fmt: str, **kw) -> str:
    return {"full": full, "concise": concise, "json": as_json, "sarif": sarif, "github": github, "agent": agent,
            "pr-comment": pr_comment}[fmt](results, **kw)


# Markdown that can sit between two words of an excerpt in the source.
_SEP = r"(?:\s|[*_~`\[\]]|\]\([^)\s]*\))+"
_WIDTH = 100
# Rules whose excerpt runs from one related word to the other.
_ENDPOINTS = {"long-dependency", "inanimate-subject"}
_CODES = {"error": "1;31", "warn": "1;33", "info": "1;36", "gutter": "1;34", "bold": "1",
          "block": "1;31", "advise": "1;33", "pass": "1;32"}


def use_color(stream, mode: str = "auto") -> bool:
    """Colour for ``stream``: NO_COLOR and FORCE_COLOR win, then whether it is a terminal."""
    if mode != "auto":
        return mode == "always"
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR") or os.environ.get("CLICOLOR_FORCE"):
        return True
    return bool(getattr(stream, "isatty", lambda: False)()) and os.environ.get("TERM") != "dumb"


def _paint(on: bool):
    if not on:
        return lambda s, _k: s
    return lambda s, k: f"\x1b[{_CODES[k]}m{s}\x1b[0m"


def _span(f, source_lines: list[str]) -> list[tuple[int, int, int]]:
    """Where ``f.excerpt`` sits in the source: (line, start, end) per line, columns from 0.

    Empty when the excerpt is not found near ``f.line``, e.g. for text taken
    from JSON, where the source line holds escaped text.
    """
    words = f.excerpt.split()
    if not words or not 0 < f.line <= len(source_lines):
        return []
    pat = re.compile(_SEP.join(re.escape(w) for w in words))
    for first in (f.line, max(f.line - 2, 1)):
        window = "\n".join(source_lines[first - 1:first + 5])
        m = pat.search(window)
        if m:
            break
    else:
        return []
    out, pos = [], m.start()
    line_no = first + window.count("\n", 0, pos)
    line_start = window.rfind("\n", 0, pos) + 1
    while True:
        line_end = window.find("\n", line_start)
        line_end = len(window) if line_end == -1 else line_end
        out.append((line_no, pos - line_start, min(m.end(), line_end) - line_start))
        if m.end() <= line_end:
            return out
        line_start, line_no = line_end + 1, line_no + 1
        nxt = window.find("\n", line_start)
        line = window[line_start:] if nxt == -1 else window[line_start:nxt]
        pos = line_start + len(line) - len(line.lstrip())


def _crop(text: str, start: int, end: int) -> tuple[str, int, int]:
    """At most _WIDTH characters of ``text`` around [start, end), with the span shifted to match."""
    text = text.replace("\t", " ").rstrip()
    if len(text) <= _WIDTH:
        return text, start, end
    lo = max(0, min(start - 20, len(text) - _WIDTH))
    hi = min(len(text), max(lo + _WIDTH, end))
    head, tail = ("..." if lo else ""), ("..." if hi < len(text) else "")
    shift = len(head) - lo
    return head + text[lo:hi] + tail, start + shift, end + shift


def _snippet(f, source_lines: list[str], paint) -> tuple[list[str], int | None, int]:
    """Gutter lines quoting the source (or the sentence) with a caret under the excerpt, the column, the gutter width."""
    sev = f.severity if f.severity in _CODES else "info"
    span = _span(f, source_lines)
    if span:
        width = len(str(span[-1][0]))
        bar = paint(" " * width + " |", "gutter")
        out = [bar]
        for i, (line_no, a, b) in enumerate(span):
            text, a, b = _crop(source_lines[line_no - 1], a, b)
            out.append(paint(f"{line_no:>{width}} |", "gutter") + f" {text}")
            marks = "^" * max(b - a, 1)
            if f.feature in _ENDPOINTS:
                # The two related words get carets; the words between them a dashed line.
                piece = text[a:b]
                head, tail = re.match(r"[\w'`]*", piece), re.search(r"[\w'`]*$", piece)
                first = len(head.group()) if i == 0 else 0
                last = len(tail.group()) if i == len(span) - 1 else 0
                marks = "^" * first + "-" * max(len(piece) - first - last, 0) + "^" * last
                marks = marks[:len(piece)] or "^"
            out.append(bar + " " + " " * a + paint(marks, sev))
        return out, span[0][1] + 1, width
    width = len(str(f.line or 0))
    bar = paint(" " * width + " |", "gutter")
    a = f.sentence.find(f.excerpt) if f.excerpt else -1
    text, a, b = _crop(" ".join(f.sentence.split()), max(a, 0), max(a, 0) + len(f.excerpt))
    out = [bar, bar + f" {text}"]
    if f.excerpt and a >= 0:
        out.append(bar + " " + " " * a + paint("^" * max(b - a, 1), sev))
    return out, None, width


def _summary(r: Result) -> str:
    def n(k: int, word: str) -> str:
        return f"{k} {word}" + ("" if k == 1 else "s")
    return (f"{n(len(r.findings), 'finding')} in {n(r.sentences, 'sentence')} ({n(r.words, 'word')}); "
            f"cost index {r.cost_index:.1f} per 1k words"
            + (f"; predicted reading time {r.reading_seconds:.0f} s ({r.reading_ms_per_word:.0f} ms per word)"
               if r.reading_seconds is not None else "")
            + (f"; {r.baselined} more in baseline" if r.baselined else ""))


def full(results: list[Result], feedback_link: bool = False, color: bool = False, **_) -> str:
    """One block per finding in the style of rustc: header, location, quoted line, caret, help."""
    paint = _paint(color)
    out: list[str] = []
    rules: list[str] = []
    for r in results:
        source_lines = r.source.splitlines()
        for f in r.findings:
            sev = f.severity if f.severity in _CODES else "info"
            snippet, col, pad = _snippet(f, source_lines, paint)
            help_text = f.suggestion or (FEATURES[f.feature].fix if f.feature in FEATURES else "")
            out.append(paint(f"{f.severity}[{f.feature}]", sev) + paint(f": {f.message}", "bold"))
            out.append(" " * pad + paint("-->", "gutter") + f" {f.where()}" + (f":{col}" if col else ""))
            out.extend(snippet)
            if help_text:
                out.append(" " * (pad + 1) + paint("=", "gutter") + paint(" help:", "bold") + f" {help_text}")
            out.append("")
            if f.feature not in rules:
                rules.append(f.feature)
        if r.findings or r.baselined or r.verdict != "pass" or len(results) == 1:
            out.append(f"{r.path}: " + paint(r.verdict, r.verdict) + f"; {_summary(r)}")
        out.extend(f"{r.path}: note: {n}" for n in r.notes)
    if len(results) > 1:
        verdicts = {v: sum(r.verdict == v for r in results) for v in ("block", "advise", "pass")}
        counts = ", ".join(paint(f"{n} {v}", v) for v, n in verdicts.items() if n)
        found = sum(len(r.findings) for r in results)
        out.append(paint("readcost", "bold") + f": {len(results)} files checked: {counts}; {found} findings")
    if rules:
        out.append(f"For why a rule matters, with an example rewrite, run `readcost explain {rules[0]}`"
                   + (f" (rules here: {', '.join(rules)})." if len(rules) > 1 else "."))
        if feedback_link:
            out.append(FEEDBACK_LINE)
    return "\n".join(out)


def concise(results: list[Result], feedback_link: bool = False, **_) -> str:
    """One line per finding, ``path:line:col: severity: [rule] message``, for editors and grep."""
    out = []
    for r in results:
        source_lines = r.source.splitlines()
        for f in r.findings:
            span = _span(f, source_lines)
            where = f.where() + (f":{span[0][1] + 1}" if span else "")
            out.append(f"{where}: {f.severity}: [{f.feature}] {f.message}")
        out.append(f"{r.path}: {r.verdict}; {_summary(r)}")
        out.extend(f"{r.path}: note: {n}" for n in r.notes)
    if feedback_link and any(r.findings for r in results):
        out.append(FEEDBACK_LINE)
    return "\n".join(out)


def as_json(results: list[Result], **_) -> str:
    return json.dumps([r.to_dict() for r in results], indent=1)


def _gh_data(s: str) -> str:
    # Same escaping as actions/toolkit's escapeData.
    return s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _gh_property(s: str) -> str:
    # actions/toolkit's escapeProperty: data escaping plus the property separators.
    return _gh_data(s).replace(":", "%3A").replace(",", "%2C")


def github(results: list[Result], **_) -> str:
    level = {"info": "notice", "warn": "warning", "error": "error"}
    lines = []
    for r in results:
        for f in r.findings:
            props = (f"file={_gh_property(f.path)},line={max(f.line, 1)},"
                     f"title={_gh_property(f'readcost {f.feature}')}")
            lines.append(f"::{level[f.severity]} {props}::{_gh_data(f'{f.message}. {f.suggestion}')}")
    return "\n".join(lines)


def _artifact_location(path: str) -> dict:
    """A SARIF artifactLocation: a valid URI reference, relative to %SRCROOT% when relative."""
    if path.startswith("<") and path.endswith(">"):  # <stdin>, <text>: not a file
        return {"uri": quote(path, safe="")}
    if Path(path).is_absolute():
        return {"uri": Path(path).as_uri()}
    return {"uri": quote(path.replace(os.sep, "/").removeprefix("./")), "uriBaseId": "%SRCROOT%"}


def sarif(results: list[Result], **_) -> str:
    from . import __version__

    level = {"info": "note", "warn": "warning", "error": "error"}
    rules = [{
        "id": f.id,
        "name": f.title,
        "shortDescription": {"text": f.title},
        "fullDescription": {"text": f.why},
        "help": {"text": f.fix},
        "helpUri": RULES_URL,
        "defaultConfiguration": {"level": level[f.severity]},
    } for f in FEATURES.values()]
    runs_results = []
    for r in results:
        for f in r.findings:
            runs_results.append({
                "ruleId": f.feature,
                "level": level[f.severity],
                "message": {"text": f"{f.message}. {f.suggestion}"},
                "locations": [{"physicalLocation": {
                    "artifactLocation": _artifact_location(f.path),
                    "region": {"startLine": max(f.line, 1)},
                }}],
            })
    doc = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "readcost", "version": __version__,
                                "informationUri": "https://arxiv.org/abs/2610.29162", "rules": rules}},
            "results": runs_results,
        }],
    }
    return json.dumps(doc, indent=1)


_ORDER = {"error": 0, "warn": 1, "info": 2}


def _worst_first(results: list[Result]) -> list:
    return sorted((f for r in results for f in r.findings), key=lambda f: (_ORDER[f.severity], f.path, f.line))


def agent(results: list[Result], max_items: int = 8, max_chars: int = 2500, feedback_link: bool = False,
          **_) -> str:
    """Short feedback for a model: the worst sentences first, with the fix.

    ``feedback_link`` adds FEEDBACK_LINE within ``max_chars``; the hooks leave
    it off, since a model cannot file an issue.
    """
    items = _worst_first(results)
    if not items:
        return ""
    max_items, max_chars = max(max_items, 0), max(max_chars, 0)
    several = len({f.path for f in items}) > 1
    total = len(items)
    words = sum(r.words for r in results)
    head = (f"readcost: {total} hard-to-read construction{'s' if total != 1 else ''} "
            f"in {words} words. Rewrite these sentences; keep the meaning and the facts.")
    lines = [head]
    for f in items[:max_items]:
        if several:
            loc = f"{f.path}:{f.line}" if f.line else f.path + (f"#{f.label}" if f.label else "")
        else:
            loc = f"line {f.line}" if f.line else (f.label or f.path)
        lines.append(f"- {loc} [{f.feature}] {f.message}. Fix: {f.suggestion}")
    if total > max_items:
        lines.append(f"- ...and {total - max_items} more (run `readcost check` for the full list)")
    body = "\n".join(lines)
    suffix = "\n" + FEEDBACK_LINE
    if feedback_link and max_chars > len(suffix) + 3:
        max_chars -= len(suffix)
    else:
        suffix = ""
    if len(body) > max_chars:
        body = body[:max_chars] if max_chars <= 3 else body[: max_chars - 3] + "..."
    return body + suffix


def _cell(s: str) -> str:
    """Text safe in a Markdown table cell: no HTML, no line breaks, no @mentions."""
    s = html.escape(" ".join(s.split()), quote=False)
    return s.replace("|", "\\|").replace("@", "&#64;")


def pr_comment(results: list[Result], max_items: int = 8, **_) -> str:
    """Markdown for one pull request comment that the action creates, then edits."""
    lines = [COMMENT_MARKER, "### readcost", ""]
    if not results:
        lines.append("No Markdown, reStructuredText or text files to check.")
    else:
        verdicts = {v: sum(r.verdict == v for r in results) for v in ("block", "advise", "pass")}
        counts = ", ".join(f"{n} {v}" for v, n in verdicts.items() if n)
        files = f"{len(results)} file{'s' if len(results) != 1 else ''}"
        items = _worst_first(results)
        lines.append(f"{files} checked: {counts}. {len(items) or 'No'} finding{'s' if len(items) != 1 else ''}.")
        timed = [r for r in results if r.reading_seconds is not None]
        if timed:
            words = sum(r.words for r in timed)
            seconds = sum(r.reading_seconds for r in timed)
            per_word = f" ({1000 * seconds / words:.0f} ms per word)" if words else ""
            lines.append(f"Predicted reading time: {seconds:.0f} s for {words} words{per_word}.")
        if items:
            shown = items[: max(max_items, 0)]
            lines += ["", "| Where | Rule | Message |", "| --- | --- | --- |"]
            for f in shown:
                where = f"{f.path}:{f.line}" if f.line else f.path
                lines.append(f"| {_cell(where)} | {_cell(f.feature)} | {_cell(f.message)} |")
            if len(items) > len(shown):
                lines += ["", f"...and {len(items) - len(shown)} more; the job's annotations list them all."]
    lines += ["", f"readcost is advisory and can be wrong. [Report a false positive]({FEEDBACK_URL})."]
    return "\n".join(lines) + "\n"
