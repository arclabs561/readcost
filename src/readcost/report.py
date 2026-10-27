"""Output formats: full, concise, json, sarif, github, agent, pr-comment."""

from __future__ import annotations

import html
import json
import os
import re
import textwrap
from functools import lru_cache
from importlib import resources
from pathlib import Path
from urllib.parse import quote

from .engine import Result
from .features import FEATURES

OUTPUTS = ("full", "concise", "json", "sarif", "github", "agent", "pr-comment")
REPO_URL = "https://github.com/arclabs561/readcost"
RULES_URL = REPO_URL + "#what-it-flags"
# The template chooser, which lists the false-positive form; short enough for a terminal line.
FEEDBACK_URL = REPO_URL + "/issues/new/choose"
FEEDBACK_LINE = f"readcost: a finding is wrong? Report it at {FEEDBACK_URL}"
# The action finds its own PR comment by this first line.
COMMENT_MARKER = "<!-- readcost -->"


def render(results: list[Result], fmt: str, **kw) -> str:
    return {"full": full, "concise": concise, "json": as_json, "sarif": sarif, "github": github, "agent": agent,
            "pr-comment": pr_comment}[fmt](results, **kw)


# Markdown that can sit between two words of an excerpt in the source.
_SEP = r"(?:\s|[*_~`\[\]]|\]\([^)\s]*\))+"
_WIDTH = 76  # with the gutter, quoted lines stay near 80 columns
# Rules whose excerpt runs from one related word to the other.
_ENDPOINTS = {"long-dependency", "inanimate-subject"}
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
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


def _crop(text: str, start: int, end: int, width: int = _WIDTH) -> tuple[str, int, int]:
    """At most ``width`` characters of ``text`` around [start, end), with the span shifted to match."""
    text = text.replace("\t", " ").rstrip()
    if len(text) <= width:
        return text, start, end
    budget = width - 6  # room for "..." at both ends
    lo = max(0, min(start - 20, len(text) - budget))
    hi = min(len(text), lo + budget)
    if end > hi:  # keep the whole excerpt when it fits
        hi = min(len(text), end)
        lo = max(0, min(start, hi - budget))
        hi = min(hi, lo + budget)  # a longer excerpt is cut at the right
    head, tail = ("..." if lo else ""), ("..." if hi < len(text) else "")
    shift = len(head) - lo
    return head + text[lo:hi] + tail, start + shift, min(end, hi) + shift


def _snippet(f, source_lines: list[str], paint) -> tuple[list[str], int | None, int]:
    """Gutter lines quoting the source (or the sentence) with a caret under the excerpt, the column, the gutter width."""
    sev = f.severity if f.severity in _CODES else "info"
    span = _span(f, source_lines)
    if span:
        width = len(str(span[-1][0]))
        bar = paint(" " * width + " |", "gutter")
        out = [bar]
        for i, (line_no, a, b) in enumerate(span):
            text, a, b = _crop(source_lines[line_no - 1], a, b, _WIDTH + 1 - width)
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


def _summary_lines(r: Result) -> list[str]:
    """The file summary for full output: counts, then reading time, each short enough for a terminal."""
    def n(k: int, word: str) -> str:
        return f"{k} {word}" + ("" if k == 1 else "s")
    out = [(f"{n(len(r.findings), 'finding')} in {n(r.sentences, 'sentence')} ({n(r.words, 'word')}), "
            f"cost index {r.cost_index:.1f} per 1,000 words")]
    if r.reading_seconds is not None:
        out.append(f"predicted reading time {r.reading_seconds:.0f} s, {r.reading_ms_per_word:.0f} ms per word")
    if r.baselined:
        out.append(f"{r.baselined} more in baseline")
    return out


def _summary(r: Result) -> str:
    def n(k: int, word: str) -> str:
        return f"{k} {word}" + ("" if k == 1 else "s")
    return (f"{n(len(r.findings), 'finding')} in {n(r.sentences, 'sentence')} ({n(r.words, 'word')}); "
            f"cost index {r.cost_index:.1f} per 1k words"
            + (f"; predicted reading time {r.reading_seconds:.0f} s ({r.reading_ms_per_word:.0f} ms per word)"
               if r.reading_seconds is not None else "")
            + (f"; {r.baselined} more in baseline" if r.baselined else ""))


def _headline(message: str) -> str:
    """The message without the quoted excerpt the carets already mark, or the z-score."""
    message = re.sub(r"^'[^']*': ", "", message)
    message = re.sub(r": '[^']*'$", "", message)
    return re.sub(r" \(z = [^)]*\)", "", message)


def _note(pad: int, label: str, text: str, paint) -> list[str]:
    """``= label: text`` under the gutter, wrapped to about 80 columns with a hanging indent."""
    lead = " " * (pad + 1) + "= " + label + ": "
    lines = textwrap.wrap(text, width=80, initial_indent=" " * len(lead), subsequent_indent=" " * len(lead))
    if not lines:
        return []
    first = " " * (pad + 1) + paint("=", "gutter") + " " + paint(label + ":", "bold") + " " + lines[0].lstrip()
    return [first] + lines[1:]


def _label(snippet: list[str], label: str, painted: str) -> None:
    """Put ``label`` after the last row of carets, as rustc does, or under it when that row is full."""
    rows = [k for k, line in enumerate(snippet) if "^" in _ANSI.sub("", line)]
    if not rows:
        return
    k = rows[-1]
    plain = _ANSI.sub("", snippet[k])
    if len(plain) + 1 + len(label) <= 80:
        snippet[k] += " " + painted
    else:
        bar = snippet[k][: snippet[k].index("|") + 1]
        start = len(plain) - len(plain.lstrip(" |")) if plain.strip(" |") else 0
        start = min(start, max(80 - len(label), 0))
        snippet.insert(k + 1, bar + " " * (start - plain.index("|") - 1) + painted)


def _first_sentence(text: str) -> str:
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    return m.group(1) if m else text


def full(results: list[Result], feedback_link: bool = False, color: bool = False, **_) -> str:
    """One block per finding in the style of rustc: headline, location, quoted line, carets, help.

    The first finding of each rule also says why the rule matters and shows
    an example rewrite; later ones give only the fix.
    """
    paint = _paint(color)
    out: list[str] = []
    rules: list[str] = []
    for r in results:
        source_lines = r.source.splitlines()
        for f in r.findings:
            sev = f.severity if f.severity in _CODES else "info"
            snippet, col, pad = _snippet(f, source_lines, paint)
            rule = FEATURES.get(f.feature)
            help_text = f.suggestion or (rule.fix if rule else "")
            title = (rule.title[:1].lower() + rule.title[1:]) if rule else _headline(f.message)
            out.append(paint(f"{f.severity}[{f.feature}]", sev) + paint(f": {title}", "bold"))
            if rule:
                _label(snippet, _headline(f.message), paint(_headline(f.message), sev))
            out.append(" " * pad + paint("-->", "gutter") + f" {f.where()}" + (f":{col}" if col else ""))
            out.extend(snippet)
            out.append(" " * (pad + 1) + paint("|", "gutter"))
            if rule and f.feature not in rules:
                out.extend(_note(pad, "why", _first_sentence(rule.why), paint))
            out.extend(_note(pad, "help", help_text, paint))
            if rule and rule.bad and f.feature not in rules:
                good = "a bulleted list" if "\n" in rule.good else f"'{rule.good}'"
                out.extend(_note(pad, "example", f"'{rule.bad}' -> {good}", paint))
            out.append("")
            if f.feature not in rules:
                rules.append(f.feature)
        if r.findings or r.baselined or r.verdict != "pass" or len(results) == 1:
            out.append(f"{r.path}: " + paint(r.verdict, r.verdict))
            out.extend("  " + line for line in _summary_lines(r))
        out.extend(f"{r.path}: note: {n}" for n in r.notes)
    if len(results) > 1:
        verdicts = {v: sum(r.verdict == v for r in results) for v in ("block", "advise", "pass")}
        counts = ", ".join(paint(f"{n} {v}", v) for v, n in verdicts.items() if n)
        found = sum(len(r.findings) for r in results)
        out.append(paint("readcost", "bold") + f": {len(results)} files checked: {counts}; {found} findings")
    if rules:
        out.append("")
        out.append(f"More on a rule: readcost explain {rules[0]}")
        if feedback_link:
            out.append(f"Wrong finding? {FEEDBACK_URL}")
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


@lru_cache(maxsize=1)
def rule_precision() -> dict:
    """data/rule_precision.json: per rule, how many labelled findings model raters accepted."""
    try:
        return json.loads(resources.files("readcost").joinpath("data/rule_precision.json").read_text())
    except (OSError, ValueError):
        return {}


def _precision(rule: str) -> dict | None:
    """{accepted, labelled} for a rule with at least 5 labelled findings, else None."""
    row = rule_precision().get("rules", {}).get(rule)
    return {"accepted": row["accepted"], "labelled": row["labelled"]} if row and row["labelled"] >= 5 else None


def as_json(results: list[Result], **_) -> str:
    out = []
    for r in results:
        d = r.to_dict()
        lines = r.source.splitlines()
        for fd, f in zip(d["findings"], r.findings):
            # 1-based columns of the excerpt, so a tool can edit exactly those words;
            # null when the excerpt cannot be found in the source.
            span = _span(f, lines)
            fd["column"] = span[0][1] + 1 if span else None
            fd["end_line"] = span[-1][0] if span else None
            fd["end_column"] = span[-1][2] + 1 if span else None
            fd["precision"] = _precision(f.feature)
        out.append(d)
    return json.dumps(out, indent=1)


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
            f"in {words} words. Rewrite these sentences where the finding holds; keep the meaning and the facts.")
    lines = [head]
    for f in items[:max_items]:
        if several:
            loc = f"{f.path}:{f.line}" if f.line else f.path + (f"#{f.label}" if f.label else "")
        else:
            loc = f"line {f.line}" if f.line else (f.label or f.path)
        prec = _precision(f.feature)
        # A low share tells the model the finding may be wrong and is worth judging, not obeying.
        note = f" (raters accepted {prec['accepted']} of {prec['labelled']} such findings)" if prec else ""
        lines.append(f"- {loc} [{f.feature}] {f.message}{note}. Fix: {f.suggestion}")
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


def hotspots(results: list[Result], n: int, color: bool = False) -> str:
    """The n sentences per file predicted to cost the most reading time beyond their length."""
    paint = _paint(color)
    out = []
    for r in results:
        if not r.hotspots[:n]:
            continue
        out.append(paint(f"{r.path}: slowest sentences", "bold")
                   + " (predicted reading time beyond their length; experimental)")
        for h in r.hotspots[:n]:
            slow = ", ".join(w["word"].strip(".,;:()\"'") for w in h["slow_words"])
            out.append(f"  {r.path}:{h['line']}  +{h['excess_ms'] / 1000:.1f} s  {h['ms_per_word']} ms per word"
                       f"  slowest words: {slow}")
            text = h["sentence"]
            out.append("    " + (text if len(text) <= 76 else text[:73] + "..."))
    return "\n".join(out)


def compare(old: Result, new: Result, color: bool = False) -> str:
    """A rewrite against its original: reading time, findings by rule, and findings only in the rewrite."""
    from .baseline import sentence_hash

    paint = _paint(color)

    def secs(r: Result) -> str:
        return "-" if r.reading_seconds is None else f"{r.reading_seconds:.1f} s"

    rows = [("", "old", "new", "change"),
            ("words", str(old.words), str(new.words), f"{new.words - old.words:+d}"),
            ("sentences", str(old.sentences), str(new.sentences), f"{new.sentences - old.sentences:+d}")]
    if old.reading_seconds is not None and new.reading_seconds is not None:
        d = new.reading_seconds - old.reading_seconds
        pct = f" ({100 * d / old.reading_seconds:+.0f}%)" if old.reading_seconds else ""
        rows.append(("predicted reading time", secs(old), secs(new), f"{d:+.1f} s{pct}"))
        rows.append(("ms per word", f"{old.reading_ms_per_word:.0f}", f"{new.reading_ms_per_word:.0f}",
                     f"{new.reading_ms_per_word - old.reading_ms_per_word:+.0f}"))
    rows += [("findings", str(len(old.findings)), str(len(new.findings)),
              f"{len(new.findings) - len(old.findings):+d}"),
             ("weighted findings", f"{old.points:g}", f"{new.points:g}", f"{new.points - old.points:+g}"),
             ("verdict", old.verdict, new.verdict, "")]
    width = max(len(r[0]) for r in rows)
    out = [f"{a:<{width}}  {b:>9}  {c:>9}  {d}".rstrip() for a, b, c, d in rows]
    oc, nc = old.counts(), new.counts()
    changed = [f"{k} {oc.get(k, 0)} -> {nc.get(k, 0)}" for k in sorted(set(oc) | set(nc)) if oc.get(k) != nc.get(k)]
    if changed:
        out += ["", "by rule: " + ", ".join(changed)]
    seen = {(f.feature, sentence_hash(f.sentence)) for f in old.findings}
    fresh = [f for f in new.findings if (f.feature, sentence_hash(f.sentence)) not in seen]
    if fresh:
        new_only = Result(path=new.path, findings=fresh, source=new.source, words=new.words,
                          sentences=new.sentences, verdict=new.verdict)
        blocks = full([new_only], color=color).split("\n\n")
        out += ["", paint(f"Only in {new.path}:", "bold"), ""]
        out += ["\n\n".join(b for b in blocks if b.lstrip().startswith(("error[", "warn[", "info[")))]
    return "\n".join(out)
