"""Findings a hook has already reported in this session, per file.

docs/evaluation.md ("Agents editing in a loop") found that an agent fed the
same findings after every edit either fixes them in one round or gets stuck:
it leaves a finding it judges wrong while the hook keeps repeating it, or it
alternates between two wordings around one. So with ``hooks.repeat = "once"``
an adapter reports a finding once per session and file, blocks or denies on
it at most once, and stays quiet when only old findings remain.

A finding is known by its rule and its flagged words, lowercased and with
punctuation dropped, not by its line: moving or rewording the text around it
keeps it the same finding, and changing the flagged words makes a new one.
The same words flagged by the same rule twice in one file count once.

The session is the harness's ``session_id`` (Claude Code also sends
``transcript_path``; a subagent adds ``agent_id`` and gets its own memory,
since it never saw the parent's feedback). Without a session there is no
memory: the hook reports every time, as with ``hooks.repeat = "always"``,
rather than hide a finding from a session it cannot tell apart.

State is one small JSON file per session under ``$READCOST_HOOK_STATE``, or
``$XDG_CACHE_HOME/readcost/hooks`` (``~/.cache/readcost/hooks``), owner-only.
It holds hashes only, no text or paths. A file untouched for a day is
ignored and deleted. Writes go to a temporary file and are renamed into
place. Any error here is logged and the hook carries on without memory.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
import time
from pathlib import Path

from . import _log

MAX_AGE = 86400            # seconds; older state belongs to a finished session
MAX_PER_FILE = 2000        # finding hashes kept per file, newest last
FORMAT = 1


def state_root() -> Path:
    override = os.environ.get("READCOST_HOOK_STATE")
    if override:
        return Path(override)
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "readcost" / "hooks"


def _digest(text: str, n: int) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()[:n]


def session_key(payload: dict) -> str | None:
    """A file-name-safe key for the session, or None when the payload has none."""
    for field in ("session_id", "transcript_path"):
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            agent = payload.get("agent_id")
            agent = agent if isinstance(agent, str) else ""
            return _digest(f"{field}\0{value}\0{agent}", 32)
    return None


def _words(text: str) -> str:
    return " ".join(re.findall(r"\w+", (text or "").casefold()))


def finding_id(f) -> str:
    """Rule plus normalised flagged words; the sentence stands in when no words were kept."""
    return _digest(f"{f.feature}\0{_words(f.excerpt) or _words(f.sentence)}", 16)


def _root() -> Path:
    d = state_root()
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = d.lstat()
    if not stat.S_ISDIR(st.st_mode) or (hasattr(os, "getuid") and st.st_uid != os.getuid()):
        raise OSError(f"refusing state directory not owned by this user: {d}")
    return d


class Memory:
    """What this session has been told about one file.

    ``active`` is False when ``hooks.repeat = "always"``, when the payload
    names no session, or when the state could not be read; then ``split``
    calls every finding new and ``remember`` does nothing.
    """

    def __init__(self, payload: dict, cfg, path: str, cwd: str | None = None):
        self.key = session_key(payload) if cfg.hooks.repeat == "once" else None
        full = os.path.normpath(os.path.join(cwd or os.getcwd(), path))
        self.file = _digest(full, 24)
        self.files: dict[str, list[str]] = {}
        self.active = self.key is not None
        if self.active:
            try:
                self.files = self._load()
            except Exception as exc:  # fail open: no memory, report as before
                _log(f"repeat state unreadable, ignoring it: {type(exc).__name__}: {exc}")
                self.files = {}

    @property
    def _path(self) -> Path:
        return state_root() / f"{self.key}.json"

    def _load(self) -> dict[str, list[str]]:
        path = self._path
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags)
        except FileNotFoundError:
            return {}
        with os.fdopen(fd, encoding="utf-8") as fh:
            if time.time() - os.fstat(fh.fileno()).st_mtime > MAX_AGE:
                return {}
            data = json.load(fh)
        files = data.get("files") if isinstance(data, dict) and data.get("format") == FORMAT else None
        if not isinstance(files, dict):
            raise ValueError("not a readcost repeat state file")
        return {k: [x for x in v if isinstance(x, str)] for k, v in files.items()
                if isinstance(k, str) and isinstance(v, list)}

    def split(self, findings) -> tuple[list, list]:
        """(findings not reported before, findings reported before), in order."""
        seen = set(self.files.get(self.file, ()))
        new, old = [], []
        for f in findings:
            (old if finding_id(f) in seen else new).append(f)
        return new, old

    def remember(self, findings) -> None:
        if not self.active or not findings:
            return
        known = self.files.get(self.file, [])
        have = set(known)
        for f in findings:
            fid = finding_id(f)
            if fid not in have:
                have.add(fid)
                known.append(fid)
        self.files[self.file] = known[-MAX_PER_FILE:]
        try:
            self._save()
        except Exception as exc:  # fail open: the next run repeats, nothing breaks
            _log(f"repeat state not saved: {type(exc).__name__}: {exc}")

    def _save(self) -> None:
        d = _root()
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"format": FORMAT, "files": self.files}, fh, separators=(",", ":"))
            os.replace(tmp, d / f"{self.key}.json")
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        _prune(d)


# Only files this module and actions.py write: a session key (32 hex digits),
# a session's action ledger (the key plus ".actions") or a temporary file left
# by an interrupted write. Anything else in the directory, which
# READCOST_HOOK_STATE may point anywhere, is never touched; nor are the
# action counters (action-stats.json), which add up across sessions.
_OURS = re.compile(r"(?:[0-9a-f]{32}(?:\.actions)?|\.tmp-[^/]*)\.json")


def _prune(d: Path) -> None:
    cutoff = time.time() - MAX_AGE
    for p in d.iterdir():
        if not _OURS.fullmatch(p.name):
            continue
        try:
            st = p.lstat()
            if stat.S_ISREG(st.st_mode) and st.st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass


def earlier(n: int) -> str:
    """The line that says what was left out, or "" when nothing was."""
    if not n:
        return ""
    return (f"\n({n} finding{'s' if n != 1 else ''} reported earlier in this session "
            f"{'are' if n != 1 else 'is'} not repeated.)")


def repeat_note(n: int) -> str:
    """One advisory line for a block verdict made only of findings already reported."""
    return (f"readcost: the {n} finding{'s' if n != 1 else ''} in this text "
            f"{'were' if n != 1 else 'was'} reported earlier in this session and "
            f"{'are' if n != 1 else 'is'} not blocked again. "
            "Leave the text as it is where a finding does not hold.")
