"""Harness adapters.

Each adapter reads the harness's JSON from stdin, decides whether the event
concerns prose it should check, and answers in the harness's own format.

Policy shared by every adapter (see docs/hooks.md):

- Fail open. Any error, missing model, or unparseable input exits 0 with no
  output, so a broken linter never blocks an agent. Errors go to stderr and,
  if ``READCOST_HOOK_LOG`` is set, to that file. The generic adapter is the
  exception: its caller asked for a verdict, so it exits 3 with ``{"error"}``.
- Cheap when irrelevant. Path filtering happens before spaCy is imported.
- Advisory by default. ``hooks.mode = "block"`` is needed before an adapter
  denies or blocks anything, and only a "block" verdict does so.
- Bounded loops. Stop-time revision runs at most once per turn.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback


def _log(msg: str) -> None:
    print(f"readcost hook: {msg}", file=sys.stderr)
    path = os.environ.get("READCOST_HOOK_LOG")
    if path:
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")
        except OSError:
            pass


def read_payload() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    data = json.loads(raw)
    return data if isinstance(data, dict) else {"value": data}


def emit(obj: dict | None) -> None:
    if obj:
        sys.stdout.write(json.dumps(obj))
        sys.stdout.flush()


def run(harness: str, event: str, rest: list[str]) -> int:
    try:
        if harness == "claude-code":
            from .claude_code import handle
        elif harness == "piku":
            from .piku import handle
        elif harness == "git":
            from .git import handle
        else:
            from .generic import handle
        return handle(event, rest)
    except SystemExit:
        raise
    except Exception as exc:  # fail open
        _log(f"{harness} {event}: {type(exc).__name__}: {exc}")
        if os.environ.get("READCOST_HOOK_DEBUG"):
            traceback.print_exc()
        if harness == "generic":
            emit({"error": f"{type(exc).__name__}: {exc}"})
            return 3
        return 0
