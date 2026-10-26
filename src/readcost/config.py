"""Configuration: defaults, TOML loading, and discovery.

Lookup order: an explicit path, then ``$READCOST_CONFIG``, then the first of
``readcost.toml``, ``.readcost.toml`` or ``pyproject.toml`` (``[tool.readcost]``)
found walking up from the start directory.
"""

from __future__ import annotations

import fnmatch
import math
import os
import sys
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

SEVERITIES = ("info", "warn", "error")


def severity_rank(s: str) -> int:
    """Rank of a severity; "off" ranks above every severity, so nothing reaches it."""
    if s == "off":
        return len(SEVERITIES)
    return SEVERITIES.index(s) if s in SEVERITIES else 0


# Allowed values for string settings that are enums.
CHOICES = {
    "mode": ("off", "advise", "block"),
    "stop": ("off", "report", "revise"),
    "display": ("off", "note"),
    "min_severity": SEVERITIES,
    "advise_severity": (*SEVERITIES, "off"),
    "comments": ("doc", "all"),
}
FEATURE_LISTS = ("enable", "disable")


@dataclass
class HookConfig:
    mode: str = "advise"            # off | advise | block
    stop: str = "off"               # off | report | revise
    display: str = "off"            # off | note  (Claude Code MessageDisplay)
    paths: list[str] = field(default_factory=lambda: [
        "*.md", "*.markdown", "*.mdx", "*.rst", "*.txt", "COMMIT_EDITMSG"])
    exclude: list[str] = field(default_factory=lambda: [
        "CHANGELOG*", "*/node_modules/*", "*/target/*", "*/.git/*", "*/vendor/*",
        "*/.venv/*", "*/venv/*", "*/.tox/*"])
    max_items: int = 8
    max_chars: int = 2500
    edited_lines_only: bool = True
    timeout_seconds: float = 8.0


@dataclass
class Config:
    model: str = "en_core_web_sm"
    profile: str = "default"        # "default" or a path to a profile JSON
    enable: list[str] = field(default_factory=list)   # adds opt-in features
    disable: list[str] = field(default_factory=list)
    min_severity: str = "info"      # findings below this are dropped
    advise_severity: str = "error"  # any finding this severe makes the verdict at least "advise"
    advise_cost_index: float = 15.0 # weighted findings per 1,000 words
    allow: list[str] = field(default_factory=list)
    comments: str = "doc"           # source files: "doc" or "all"
    stacked_nouns_min: int = 3
    long_dependency_z: float = 2.5
    long_dependency_min_tokens: int = 10
    inline_list_min_items: int = 4
    long_sentence_words: int = 32
    block_cost_index: float = 30.0  # weighted findings per 1,000 words
    block_min_points: float = 3.0   # and at least this many weighted findings
    # Below this many words a per-1,000 density is too noisy (one finding in a
    # 20-word comment scores 50), so short texts are judged by weighted points:
    # advise at short_advise_points, block at block_min_points.
    short_text_words: int = 40
    short_advise_points: float = 2.0
    # Commit messages are terser than prose: in 1,000 Go commit messages of
    # 40+ words the 99th percentile cost index is 49, against 8 to 16 for
    # essays, docs, READMEs and discussion (docs/evaluation.md, "Contexts").
    commit_advise_cost_index: float = 50.0
    commit_block_cost_index: float = 100.0
    hooks: HookConfig = field(default_factory=HookConfig)
    source: str = ""                # where the config came from

    def wants(self, path: str) -> bool:
        if self.excluded(path):
            return False
        return any(fnmatch.fnmatch(c, g) for c in _candidates(path) for g in self.hooks.paths)

    def excluded(self, path: str) -> bool:
        return any(fnmatch.fnmatch(c, g) for c in _candidates(path) for g in self.hooks.exclude)


def _candidates(path: str) -> tuple[str, str, str]:
    p = path.replace(os.sep, "/").removeprefix("./")
    # A leading "/" lets "*/node_modules/*" match a top-level node_modules too.
    return (p, "/" + p.lstrip("/"), Path(p).name)


def _check(name: str, default, value):
    """Return an error message when ``value`` cannot stand in for ``default``."""
    if isinstance(default, bool):
        ok, want = isinstance(value, bool), "true or false"
    elif isinstance(default, int):
        ok, want = isinstance(value, int) and not isinstance(value, bool), "an integer"
    elif isinstance(default, float):
        ok = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        want = "a number"
    elif isinstance(default, list):
        ok = isinstance(value, list) and all(isinstance(v, str) for v in value)
        want = "a list of strings, e.g. [\"a\", \"b\"]"
    else:
        ok, want = isinstance(value, str), "a string"
    if not ok:
        return f"must be {want}, not {value!r}"
    if name in CHOICES and value not in CHOICES[name]:
        return f"must be one of {', '.join(CHOICES[name])}, not {value!r}"
    if name in FEATURE_LISTS:
        bad = unknown_features(value)
        if bad:
            return f"unknown feature {', '.join(map(repr, bad))}"
    return None


def unknown_features(ids: list[str]) -> list[str]:
    from .features import FEATURES

    return [i for i in ids if i not in FEATURES]


def _apply(obj, data: dict, source: str, prefix: str = "") -> None:
    known = {f.name for f in fields(obj)} - {"source"}
    for key, value in data.items():
        name = key.replace("-", "_")
        if name not in known:
            print(f"readcost: warning: {source}: unknown key {prefix + key!r} ignored", file=sys.stderr)
            continue
        current = getattr(obj, name)
        if isinstance(current, HookConfig):
            if not isinstance(value, dict):
                raise ValueError(f"{source}: {prefix + key} must be a table, not {value!r}")
            _apply(current, value, source, f"{prefix}{key}.")
            continue
        error = _check(name, current, value)
        if error:
            raise ValueError(f"{source}: {prefix + key} {error}")
        setattr(obj, name, float(value) if isinstance(current, float) else value)


def find_config(start: Path) -> Path | None:
    start = start if start.is_dir() else start.parent
    for directory in [start, *start.parents]:
        for name in ("readcost.toml", ".readcost.toml"):
            if (directory / name).is_file():
                return directory / name
        pyproject = directory / "pyproject.toml"
        if pyproject.is_file():
            try:
                if "readcost" in tomllib.loads(pyproject.read_text()).get("tool", {}):
                    return pyproject
            except (tomllib.TOMLDecodeError, OSError):
                pass
        if (directory / ".git").exists():
            break
    return None


def load_config(path: str | None = None, start: str | None = None) -> Config:
    cfg = Config()
    candidate = Path(path) if path else None
    if candidate is None and os.environ.get("READCOST_CONFIG"):
        candidate = Path(os.environ["READCOST_CONFIG"])
    if candidate is None:
        candidate = find_config(Path(start or os.getcwd()).resolve())
    if candidate is None:
        return cfg
    try:
        data = tomllib.loads(candidate.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{candidate}: invalid TOML: {exc}") from exc
    if candidate.name == "pyproject.toml":
        data = data.get("tool", {}).get("readcost", {})
    elif isinstance(data.get("readcost"), dict):
        # readcost.toml may use a [readcost] table, top-level keys, or both.
        table = data.pop("readcost")
        both = sorted(set(data) & set(table))
        if both:
            raise ValueError(f"{candidate}: {', '.join(both)} set both at top level and in [readcost]")
        data |= table
    _apply(cfg, data, str(candidate))
    cfg.source = str(candidate)
    # A relative profile path means relative to the config file, not the cwd.
    if cfg.profile not in ("default", "") and not Path(cfg.profile).is_absolute():
        cfg.profile = str(candidate.resolve().parent / cfg.profile)
    return cfg
