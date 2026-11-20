"""How often a finding an agent hook reported was acted on, per rule, counted locally.

Static-analysis tools count a report as acted on when a later version of the
code no longer has it (Infer at diff time), and treat a report that drew no
action as an "effective false positive" (Google's Tricorder). This module
does the same for the findings the Claude Code and piku hooks report:

- When a hook reports a finding, it is recorded for its session and file:
  its rule and a hash of its flagged words (the sentence when no words were
  kept), lowercased and without punctuation, as ``repeats.finding_id`` knows
  it. Each finding is recorded once per session and file.
- Whenever a hook later sees the whole file again in the same session (Claude
  Code's PostToolUse, piku's PostToolUse), each recorded finding is checked:
  its words no longer appear in the file makes it **resolved**, and words that
  come back after that make it **reintroduced**. The check compares words, not
  findings: it needs no parse, so it costs nothing next to the analysis. A
  rewording that keeps the flagged words counts as not acted on; removing the
  words counts as acted on whether or not the rewrite reads better.
- Per-rule counters (reported, resolved, reintroduced) add up across sessions
  in ``action-stats.json`` next to the repeat state. ``readcost stats`` prints
  them. A finding still present when its session ends was not acted on.

Only counters and hashes are written, never text or paths. Nothing leaves the
machine. ``hooks.track = false`` turns it off; a payload with no session is not
tracked. Any error is logged and the hook carries on.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
import time
from pathlib import Path

from . import _log
from .repeats import (
    MAX_AGE,
    _digest,
    _root,
    _words,
    finding_id,
    session_key,
    state_root,
)

FORMAT = 1
STATS = "action-stats.json"
LOCK = "action-stats.lock"
MAX_PER_FILE = 2000
COUNTERS = ("reported", "resolved", "reintroduced")


def _flagged(f) -> str:
    return _words(f.excerpt) or _words(f.sentence)


def _windows(text: str, sizes: set[int]) -> set[str]:
    """Hashes of every run of n words of the text, for each n in sizes."""
    words = _words(text).split()
    out = set()
    for n in sizes:
        for i in range(max(len(words) - n + 1, 0)):
            out.add(_digest(" ".join(words[i:i + n]), 16))
    return out


def _read_json(path: Path) -> dict | None:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) and data.get("format") == FORMAT else None


def _write_json(d: Path, name: str, data: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, separators=(",", ":"))
        os.replace(tmp, d / name)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class _Locked:
    """An exclusive lock on the counters while they are read and rewritten (POSIX only)."""

    def __init__(self, d: Path):
        self.path = d / LOCK
        self.fd = None

    def __enter__(self):
        try:
            import fcntl
        except ImportError:  # no flock: a lost update costs one count
            return self
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        if self.fd is not None:
            os.close(self.fd)  # closing releases the lock


def _bump(d: Path, changes: dict[str, dict[str, int]]) -> None:
    if not changes:
        return
    with _Locked(d):
        try:
            data = _read_json(d / STATS)
        except (OSError, ValueError):
            data = None
        rules = (data or {}).get("rules")
        rules = rules if isinstance(rules, dict) else {}
        for rule, delta in changes.items():
            row = rules.get(rule) if isinstance(rules.get(rule), dict) else {}
            for k in COUNTERS:
                row[k] = int(row.get(k, 0)) + delta.get(k, 0)
            rules[rule] = row
        _write_json(d, STATS, {"format": FORMAT, "rules": rules, "updated": int(time.time())})


class Ledger:
    """The findings a session's hooks reported for one file, and what became of them."""

    def __init__(self, payload: dict, cfg, path: str, cwd: str | None = None):
        self.key = session_key(payload) if getattr(cfg.hooks, "track", True) else None
        full = os.path.normpath(os.path.join(cwd or os.getcwd(), path))
        self.file = _digest(full, 24)
        self.active = self.key is not None
        self.files: dict[str, dict] = {}
        if self.active:
            try:
                self.files = self._load()
            except Exception as exc:  # fail open: no tracking this time
                _log(f"action state unreadable, ignoring it: {type(exc).__name__}: {exc}")
                self.active = False

    @property
    def _name(self) -> str:
        return f"{self.key}.actions.json"

    def _load(self) -> dict:
        path = state_root() / self._name
        try:
            st = path.lstat()
        except FileNotFoundError:
            return {}
        if not stat.S_ISREG(st.st_mode) or time.time() - st.st_mtime > MAX_AGE:
            return {}
        data = _read_json(path)
        files = (data or {}).get("files")
        if not isinstance(files, dict):
            raise ValueError("not a readcost action state file")
        return {k: v for k, v in files.items() if isinstance(k, str) and isinstance(v, dict)}

    def _commit(self, changes: dict) -> None:
        try:
            d = _root()
            _write_json(d, self._name, {"format": FORMAT, "files": self.files})
            _bump(d, changes)
        except Exception as exc:  # fail open: the counts miss this event, nothing breaks
            _log(f"action state not saved: {type(exc).__name__}: {exc}")

    def observe(self, text: str) -> None:
        """Check every recorded finding of this file against its text as it is now."""
        if not self.active:
            return
        known = self.files.get(self.file)
        if not known:
            return
        present = _windows(text, {int(v.get("n", 0)) for v in known.values() if int(v.get("n", 0)) > 0})
        changes: dict[str, dict[str, int]] = {}
        for entry in known.values():
            here = entry.get("w") in present
            was = entry.get("state") != "resolved"
            if was and not here:
                entry["state"] = "resolved"
                changes.setdefault(entry.get("rule", "?"), {}).setdefault("resolved", 0)
                changes[entry["rule"]]["resolved"] += 1
            elif here and not was:
                entry["state"] = "present"
                changes.setdefault(entry.get("rule", "?"), {}).setdefault("reintroduced", 0)
                changes[entry["rule"]]["reintroduced"] += 1
        if changes:
            self._commit(changes)

    def record(self, findings) -> None:
        """Note the findings a hook has just reported for this file."""
        if not self.active or not findings:
            return
        known = self.files.setdefault(self.file, {})
        changes: dict[str, dict[str, int]] = {}
        for f in findings:
            fid = finding_id(f)
            words = _flagged(f)
            if fid in known or not words:
                continue
            known[fid] = {"rule": f.feature, "n": len(words.split()), "w": _digest(words, 16), "state": "present"}
            changes.setdefault(f.feature, {}).setdefault("reported", 0)
            changes[f.feature]["reported"] += 1
        if len(known) > MAX_PER_FILE:
            for k in list(known)[: len(known) - MAX_PER_FILE]:
                del known[k]
        if changes:
            self._commit(changes)


def stats() -> dict:
    """{rule: {reported, resolved, reintroduced, acted, ignored, action_rate}} from the local counters."""
    try:
        data = _read_json(state_root() / STATS)
    except (OSError, ValueError):
        data = None
    rules = (data or {}).get("rules") if data else None
    out = {}
    for rule, row in sorted((rules or {}).items()):
        if not isinstance(row, dict):
            continue
        reported = int(row.get("reported", 0))
        acted = max(int(row.get("resolved", 0)) - int(row.get("reintroduced", 0)), 0)
        out[rule] = {"reported": reported, "resolved": int(row.get("resolved", 0)),
                     "reintroduced": int(row.get("reintroduced", 0)), "acted": acted,
                     "ignored": max(reported - acted, 0),
                     "action_rate": round(acted / reported, 3) if reported else None}
    return out


def reset() -> bool:
    """Delete the counters (not the session state). True when there was something to delete."""
    path = state_root() / STATS
    try:
        if stat.S_ISREG(path.lstat().st_mode):
            path.unlink()
            return True
    except FileNotFoundError:
        pass
    return False


def render(rows: dict) -> str:
    if not rows:
        return ("readcost: no hook findings tracked yet. The Claude Code and piku hooks count, per rule, "
                "how many findings they reported and how many the agent's later edits removed.\n")
    width = max(len(r) for r in rows)
    lines = [f"{'rule':<{width}}  reported  acted  ignored  reintroduced  action rate"]
    for rule, r in rows.items():
        rate = "-" if r["action_rate"] is None else f"{100 * r['action_rate']:.0f}%"
        lines.append(f"{rule:<{width}}  {r['reported']:>8}  {r['acted']:>5}  {r['ignored']:>7}  "
                     f"{r['reintroduced']:>12}  {rate:>11}")
    total = sum(r["reported"] for r in rows.values())
    acted = sum(r["acted"] for r in rows.values())
    lines.append(f"\n{acted} of {total} findings acted on: their flagged words were gone from the file at a "
                 "later hook check in the same session. A finding still in the file was not acted on; "
                 "a low rate marks a rule worth turning down for this project.")
    return "\n".join(lines) + "\n"

