"""Configuration: defaults, TOML loading, and discovery.

Lookup order: an explicit path, then ``$READCOST_CONFIG``, then the first of
``readcost.toml``, ``.readcost.toml`` or ``pyproject.toml`` (``[tool.readcost]``)
found walking up from the start directory.
"""

from __future__ import annotations

import fnmatch
import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

SEVERITIES = ("info", "warn", "error")


def severity_rank(s: str) -> int:
    return SEVERITIES.index(s) if s in SEVERITIES else 0


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
    hooks: HookConfig = field(default_factory=HookConfig)
    source: str = ""                # where the config came from

    def wants(self, path: str) -> bool:
        p = path.replace(os.sep, "/").removeprefix("./")
        # A leading "/" lets "*/node_modules/*" match a top-level node_modules too.
        candidates = (p, "/" + p.lstrip("/"), Path(p).name)
        if any(fnmatch.fnmatch(c, g) for c in candidates for g in self.hooks.exclude):
            return False
        return any(fnmatch.fnmatch(c, g) for c in candidates for g in self.hooks.paths)


def _apply(obj, data: dict) -> None:
    known = {f.name: f for f in fields(obj)}
    for key, value in data.items():
        key = key.replace("-", "_")
        if key == "hooks" and isinstance(value, dict) and hasattr(obj, "hooks"):
            _apply(obj.hooks, value)
        elif key in known:
            setattr(obj, key, value)


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
    data = tomllib.loads(candidate.read_text())
    if candidate.name == "pyproject.toml":
        data = data.get("tool", {}).get("readcost", {})
    else:
        data = data.get("readcost", data)
    _apply(cfg, data)
    cfg.source = str(candidate)
    return cfg
