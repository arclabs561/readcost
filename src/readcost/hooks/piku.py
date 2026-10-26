"""piku hooks (crates/piku-runtime/src/hooks.rs, read 2026-10-26).

piku's contract today:

- PreToolUse stdin: ``hook_event_name``, ``tool_name``, ``tool_input``,
  ``session_id``, ``cwd``. The file tools are ``write_file`` (path, content) and
  ``edit_file`` (path, old_string, new_string, replace_all). Output JSON
  ``hookSpecificOutput.permissionDecision`` "allow" or "deny", with
  ``permissionDecisionReason`` and ``additionalContext``. Exit 2 also denies.
- PostToolUse and Stop are fire-and-forget: piku ignores their stdout. They can
  log, not advise. Stop carries no assistant text.

So readcost advises in piku at PreToolUse time, on the text about to be
written, and can log at PostToolUse. docs/hooks.md proposes the two piku
changes that would allow review of final answers.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from . import _log, emit, read_payload
from .common import analyze, config_for, feedback, relpath

FILE_TOOLS = {"write_file", "edit_file"}


def handle(event: str, rest: list[str]) -> int:
    event = event.lower().replace("_", "-")
    payload = read_payload()
    cwd = payload.get("cwd") or os.getcwd()
    cfg = config_for(cwd)
    if event in ("pre-tool-use", "pretooluse"):
        return pre_tool_use(payload, cfg, cwd)
    if event in ("post-tool-use", "posttooluse"):
        return post_tool_use(payload, cfg, cwd)
    _log(f"piku: unsupported event {event!r}")
    return 0


def _target(payload: dict, cwd: str) -> tuple[str, str] | None:
    if payload.get("tool_name") not in FILE_TOOLS:
        return None
    ti = payload.get("tool_input") or {}
    path = ti.get("path", "")
    if not path:
        return None
    text = ti.get("content", "") if payload["tool_name"] == "write_file" else ti.get("new_string", "")
    return relpath(os.path.join(cwd, path) if not os.path.isabs(path) else path, cwd), text


def pre_tool_use(payload: dict, cfg, cwd: str) -> int:
    if cfg.hooks.mode == "off":
        return 0
    target = _target(payload, cwd)
    if not target or not cfg.wants(target[0]) or not target[1].strip():
        return 0
    rel, text = target
    result = analyze(cfg, path=rel, text=text)
    if result.verdict == "pass":
        return 0
    message = feedback(cfg, result)
    if result.verdict == "block" and cfg.hooks.mode == "block":
        emit({"hookSpecificOutput": {
            "permissionDecision": "deny",
            "permissionDecisionReason": message + "\nRewrite the text and try again.",
        }})
    else:
        emit({"hookSpecificOutput": {"permissionDecision": "allow", "additionalContext": message}})
    return 0


def post_tool_use(payload: dict, cfg, cwd: str) -> int:
    """Append findings for the written file to .piku/readcost.jsonl (piku ignores stdout here)."""
    target = _target(payload, cwd)
    if not target or not cfg.wants(target[0]):
        return 0
    if (payload.get("tool_response") or {}).get("is_error"):
        return 0
    full = Path(cwd) / target[0]
    if not full.is_file():
        return 0
    result = analyze(cfg, path=target[0])
    log = Path(cwd) / ".piku" / "readcost.jsonl"
    log.parent.mkdir(exist_ok=True)
    with open(log, "a", encoding="utf-8") as fh:
        record = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "session_id": payload.get("session_id"),
                  **{k: v for k, v in result.to_dict().items() if k != "findings"},
                  "findings": [{"line": f.line, "feature": f.feature, "message": f.message}
                               for f in result.findings]}
        fh.write(json.dumps(record) + "\n")
    return 0
