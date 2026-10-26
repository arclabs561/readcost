"""Output formats: text, json, sarif, github, agent."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote

from .engine import Result
from .features import FEATURES

OUTPUTS = ("text", "json", "sarif", "github", "agent")


def render(results: list[Result], fmt: str, **kw) -> str:
    return {"text": text, "json": as_json, "sarif": sarif, "github": github, "agent": agent}[fmt](results, **kw)


def text(results: list[Result], **_) -> str:
    out = []
    for r in results:
        for f in r.findings:
            out.append(f"{f.where()}: {f.severity}: [{f.feature}] {f.message}")
        out.append(
            f"{r.path}: {r.verdict}; {len(r.findings)} findings in {r.sentences} sentences "
            f"({r.words} words); cost index {r.cost_index:.1f} per 1k words"
        )
        out.extend(f"{r.path}: note: {n}" for n in r.notes)
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


def agent(results: list[Result], max_items: int = 8, max_chars: int = 2500, **_) -> str:
    """Short feedback for a model: the worst sentences first, with the fix."""
    order = {"error": 0, "warn": 1, "info": 2}
    items = sorted((f for r in results for f in r.findings), key=lambda f: (order[f.severity], f.path, f.line))
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
    if len(body) <= max_chars:
        return body
    return body[:max_chars] if max_chars <= 3 else body[: max_chars - 3] + "..."
