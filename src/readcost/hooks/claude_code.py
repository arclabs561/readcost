"""Claude Code hooks: PostToolUse, PreToolUse, Stop, MessageDisplay.

Contract (code.claude.com/docs/en/hooks, read 2026-10-26):

- PostToolUse stdin has ``tool_name``, ``tool_input`` (Write: file_path,
  content; Edit: file_path, old_string, new_string, replace_all) and
  ``tool_response``. ``hookSpecificOutput.additionalContext`` is added next to
  the tool result; top-level ``decision: "block"`` adds ``reason`` there too.
- PreToolUse answers with ``hookSpecificOutput.permissionDecision`` ("deny")
  and ``permissionDecisionReason``, which Claude sees.
- Stop stdin has ``stop_hook_active`` and ``last_assistant_message``.
  ``decision: "block"`` with ``reason`` makes Claude continue; ``systemMessage``
  shows a warning to the user without continuing.
- MessageDisplay stdin has ``message_id``, ``index``, ``final`` and ``delta``;
  ``displayContent`` replaces the delta on screen only.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path

from . import _log, emit, read_payload
from .common import analyze, config_for, feedback, lines_of, relpath, summary_line

FILE_TOOLS = {"Write", "Edit", "MultiEdit"}


def handle(event: str, rest: list[str]) -> int:
    event = event.lower().replace("_", "-")
    payload = read_payload()
    cwd = payload.get("cwd") or os.getcwd()
    cfg = config_for(cwd)
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
    tool = payload.get("tool_name")
    ti = payload.get("tool_input") or {}
    if tool == "Write":
        return None
    news = [ti.get("new_string", "")] if tool == "Edit" else [e.get("new_string", "") for e in ti.get("edits", [])]
    ranges: list[tuple[int, int]] = []
    for new in news:
        found = lines_of(text, new)
        if found and not ti.get("replace_all"):
            found = found[:1]
        ranges.extend(found)
    # new_string not verbatim on disk (another hook reflowed it, quotes changed):
    # judge the whole file rather than silently checking nothing.
    return ranges or None


def post_tool_use(payload: dict, cfg, cwd: str) -> int:
    if cfg.hooks.mode == "off" or payload.get("tool_name") not in FILE_TOOLS:
        return 0
    path = (payload.get("tool_input") or {}).get("file_path", "")
    rel = relpath(path, cwd)
    if not path or not cfg.wants(rel) or not Path(path).is_file():
        return 0
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    lines = _edited_ranges(payload, text) if cfg.hooks.edited_lines_only else None
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
    if payload["tool_name"] == "Write":
        text = ti.get("content", "")
    elif payload["tool_name"] == "Edit":
        text = ti.get("new_string", "")
    else:
        text = "\n\n".join(e.get("new_string", "") for e in ti.get("edits", []))
    result = analyze(cfg, path=rel, text=text)
    if result.verdict != "block":
        return 0
    emit({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": feedback(cfg, result) + "\nRewrite the text and try the edit again.",
    }})
    return 0


def stop(payload: dict, cfg) -> int:
    mode = cfg.hooks.stop
    text = payload.get("last_assistant_message") or ""
    if mode == "off" or not text.strip():
        return 0
    if mode == "revise" and payload.get("stop_hook_active"):
        return 0  # one revision round per turn at most
    result = analyze(cfg, path="<answer>", text=text, fmt="markdown")
    if mode == "report" and result.verdict != "pass":
        emit({"systemMessage": summary_line(result)})
    elif mode == "revise" and result.verdict == "block":
        emit({"decision": "block", "reason": feedback(cfg, result).replace(
            "Rewrite these sentences", "Restate your previous answer more plainly; rewrite these sentences")})
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


def message_display(payload: dict, cfg) -> int:
    """Append a one-line note under an assistant message the user reads. Display only."""
    if cfg.hooks.display == "off":
        return 0
    mid = re.sub(r"[^\w-]", "", str(payload.get("message_id", "")))[:64] or \
        hashlib.sha1(str(payload.get("session_id", "")).encode()).hexdigest()[:16]
    state = _state_dir() / f"{mid}.md"
    delta = payload.get("delta") or ""
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(state, flags, 0o600), "a", encoding="utf-8") as fh:
        fh.write(delta)
    if not payload.get("final"):
        return 0
    text = state.read_text(encoding="utf-8")
    try:
        state.unlink()
    except OSError:
        pass
    result = analyze(cfg, path="<answer>", text=text, fmt="markdown")
    if result.verdict == "pass":
        return 0
    sep = "" if delta.endswith("\n") or not delta else "\n"
    emit({"displayContent": f"{delta}{sep}\n_{summary_line(result)}_\n"})
    return 0
