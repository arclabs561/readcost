"""Claude Code hooks: PostToolUse, PreToolUse, Stop, MessageDisplay.

Contract (code.claude.com/docs/en/hooks, read 2026-10-26):

- PostToolUse stdin has ``tool_name``, ``tool_input`` (Write: file_path,
  content; Edit: file_path, old_string, new_string, replace_all) and
  ``tool_response``. For a Write over an existing file, ``tool_response``
  carries ``originalFile`` (seen in session transcripts, not in the hooks doc);
  readcost diffs against it and judges the whole file when it is absent.
  ``hookSpecificOutput.additionalContext`` is added next to the tool result;
  top-level ``decision: "block"`` adds ``reason`` there too.
- PreToolUse answers with ``hookSpecificOutput.permissionDecision`` ("deny")
  and ``permissionDecisionReason``, which Claude sees.
- Stop stdin has ``stop_hook_active`` and ``last_assistant_message``.
  ``decision: "block"`` with ``reason`` makes Claude continue; ``systemMessage``
  shows a warning to the user without continuing.
- MessageDisplay stdin has ``message_id``, ``index``, ``final`` and ``delta``;
  ``displayContent`` replaces the delta on screen only.

MultiEdit was removed from Claude Code in v2.0.0; it is ignored here.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from pathlib import Path

from . import _log, emit, read_payload
from .common import (
    analyze,
    changed_lines,
    config_for,
    feedback,
    lines_of,
    relpath,
    summary_line,
)

FILE_TOOLS = {"Write", "Edit"}
STALE_SECONDS = 86400  # MessageDisplay state older than a day belongs to an interrupted message


def handle(event: str, rest: list[str]) -> int:
    event = event.lower().replace("_", "-")
    payload = read_payload()
    cwd = payload.get("cwd") or os.getcwd()
    cfg = config_for(cwd, (payload.get("tool_input") or {}).get("file_path") or None)
    if event in ("post-tool-use", "posttooluse"):
        return post_tool_use(payload, cfg, cwd)
    if event in ("pre-tool-use", "pretooluse"):
        return pre_tool_use(payload, cfg, cwd)
    if event in ("stop", "subagent-stop", "subagentstop"):
        return stop(payload, cfg)
    if event in ("message-display", "messagedisplay"):
        return message_display(payload, cfg)
    _log(f"claude-code: unknown event {event!r}")
    return 0


def _edited_ranges(payload: dict, text: str) -> list[tuple[int, int]] | None:
    """Lines to judge after the edit: [] for nothing changed, None for the whole file."""
    ti = payload.get("tool_input") or {}
    if payload.get("tool_name") == "Write":
        original = (payload.get("tool_response") or {}).get("originalFile")
        return changed_lines(original, text) if isinstance(original, str) else None
    found = lines_of(text, ti.get("new_string", ""))
    if found and not ti.get("replace_all"):
        found = found[:1]
    # new_string not verbatim on disk (another hook reflowed it, quotes changed):
    # judge the whole file rather than silently checking nothing.
    return found or None


def post_tool_use(payload: dict, cfg, cwd: str) -> int:
    if cfg.hooks.mode == "off" or payload.get("tool_name") not in FILE_TOOLS:
        return 0
    path = (payload.get("tool_input") or {}).get("file_path", "")
    rel = relpath(path, cwd)
    if not path or not cfg.wants(rel) or not Path(path).is_file():
        return 0
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    lines = _edited_ranges(payload, text) if cfg.hooks.edited_lines_only else None
    if lines == []:
        return 0  # the Write left every line as it was
    result = analyze(cfg, path=rel, text=text, lines=lines)
    if result.verdict == "pass":
        return 0
    message = feedback(cfg, result)
    out: dict = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message}}
    if result.verdict == "block" and cfg.hooks.mode == "block":
        out = {"decision": "block", "reason": message}
    emit(out)
    return 0


def pre_tool_use(payload: dict, cfg, cwd: str) -> int:
    """Deny a Write or Edit whose new prose would be blocked. Only in block mode."""
    if cfg.hooks.mode != "block" or payload.get("tool_name") not in FILE_TOOLS:
        return 0
    ti = payload.get("tool_input") or {}
    rel = relpath(ti.get("file_path", ""), cwd)
    if not rel or not cfg.wants(rel):
        return 0
    lines, where = None, ""
    if payload["tool_name"] == "Write":
        text = ti.get("content", "")
        on_disk = Path(cwd, ti.get("file_path", ""))
        if cfg.hooks.edited_lines_only and on_disk.is_file():
            # Judge only what this Write changes, not old prose nobody touched.
            lines = changed_lines(on_disk.read_text(encoding="utf-8", errors="ignore"), text)
            if not lines:
                return 0
    else:
        text, where = ti.get("new_string", ""), "of the new text"
    result = analyze(cfg, path=rel, text=text, lines=lines)
    if result.verdict != "block":
        return 0
    emit({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": feedback(cfg, result, where=where,
                                             suffix="\nRewrite the text and try the edit again."),
    }})
    return 0


def stop(payload: dict, cfg) -> int:
    mode = cfg.hooks.stop
    text = payload.get("last_assistant_message") or ""
    if mode == "off" or cfg.hooks.mode == "off" or not text.strip():
        return 0
    if mode == "revise" and payload.get("stop_hook_active"):
        return 0  # one revision round per turn at most
    result = analyze(cfg, path="<answer>", text=text, fmt="markdown")
    if mode == "report" and result.verdict != "pass":
        emit({"systemMessage": summary_line(result)})
    elif mode == "revise" and result.verdict == "block":
        emit({"decision": "block", "reason": feedback(
            cfg, result, head="Restate your previous answer more plainly; rewrite these sentences")})
    return 0


def _state_dir() -> Path:
    # Message text lands here, so keep it in the user's own state directory,
    # owner-only, never in a shared, predictable /tmp path.
    base = os.environ.get("CLAUDE_PLUGIN_DATA") or os.environ.get("XDG_STATE_HOME") \
        or os.path.join(os.path.expanduser("~"), ".local", "state")
    d = Path(base) / "readcost-display"
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = d.lstat()
    if not stat.S_ISDIR(st.st_mode) or (hasattr(os, "getuid") and st.st_uid != os.getuid()):
        raise OSError(f"refusing state directory not owned by this user: {d}")
    os.chmod(d, 0o700)
    return d


def _message_key(payload: dict) -> str:
    # message_id when Claude Code sends it, else the turn, else the session; a
    # hash keeps any value safe as a file name.
    for field in ("message_id", "turn_id", "session_id"):
        if payload.get(field):
            return hashlib.sha1(f"{field}:{payload[field]}".encode()).hexdigest()[:24]
    return "unkeyed"


def _prune(d: Path, keep: Path) -> None:
    cutoff = time.time() - STALE_SECONDS
    for p in d.iterdir():
        try:
            if p != keep and p.lstat().st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass


def message_display(payload: dict, cfg) -> int:
    """Append a one-line note under an assistant message the user reads. Display only."""
    if cfg.hooks.display == "off" or cfg.hooks.mode == "off":
        return 0
    d = _state_dir()
    state = d / f"{_message_key(payload)}.jsonl"
    _prune(d, state)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        with os.fdopen(os.open(state, flags), encoding="utf-8") as fh:
            batches = {int(r["index"]): r["delta"] for r in map(json.loads, fh) if "index" in r}
    except FileNotFoundError:
        batches = {}
    delta = payload.get("delta") or ""
    index = payload.get("index")
    index = index if isinstance(index, int) else max(batches, default=-1) + 1
    if index == 0 and 0 in batches:
        batches = {}  # a second index 0 under this key starts a new message
    batches[index] = delta
    if payload.get("final"):
        try:
            state.unlink()
        except OSError:
            pass
        text = "".join(batches[i] for i in sorted(batches))
    else:
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(state, flags, 0o600), "w", encoding="utf-8") as fh:
            fh.writelines(json.dumps({"index": i, "delta": t}) + "\n" for i, t in sorted(batches.items()))
        return 0
    result = analyze(cfg, path="<answer>", text=text, fmt="markdown")
    if result.verdict == "pass":
        return 0
    sep = "" if delta.endswith("\n") or not delta else "\n"
    emit({"displayContent": f"{delta}{sep}\n_{summary_line(result)}_\n"})
    return 0
