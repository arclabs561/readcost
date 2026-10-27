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
# Rule levels, as in ty: a level turns a rule on at that severity; "ignore" turns it off.
LEVELS = (*SEVERITIES, "ignore")
# Keys that still load but have a newer spelling; removed at 1.0.
DEPRECATED = {"enable": "[readcost.rules] RULE = \"info\", \"warn\" or \"error\"", "disable": "[readcost.rules] RULE = \"ignore\"",
              "hooks.paths": "[readcost.src] include", "hooks.exclude": "[readcost.src] exclude"}
# Tuning thresholds that were config keys until 0.3 and are now fixed in
# features.py and engine.py. Setting one warns and is ignored.
RETIRED_KEYS = frozenset({
    "stacked_nouns_min", "long_dependency_z", "long_dependency_min_tokens", "long_dependency_core_min",
    "long_dependency_core_always", "inline_list_min_items", "long_sentence_words", "block_min_points",
    "short_text_words", "short_advise_points", "commit_advise_cost_index", "commit_block_cost_index",
    "long_dependency_referents"})


@dataclass
class HookConfig:
    mode: str = "advise"            # off | advise | block
    stop: str = "off"               # off | report | revise
    display: str = "off"            # off | note  (Claude Code MessageDisplay)
    max_items: int = 8
    max_chars: int = 2500
    edited_lines_only: bool = True
    timeout_seconds: float = 8.0


@dataclass
class SrcConfig:
    """Which files `readcost check DIR`, the hooks and the language server read."""
    include: list[str] = field(default_factory=lambda: [
        "*.md", "*.markdown", "*.mdx", "*.rst", "*.txt", "COMMIT_EDITMSG"])
    exclude: list[str] = field(default_factory=lambda: [
        "CHANGELOG*", "*/node_modules/*", "*/target/*", "*/.git/*", "*/vendor/*",
        "*/.venv/*", "*/venv/*", "*/.tox/*"])
    extend_exclude: list[str] = field(default_factory=list)  # added to exclude, keeping its defaults
    respect_ignore_files: bool = True  # skip what .gitignore and other git ignore files exclude


@dataclass
class Config:
    model: str = "en_core_web_sm"
    profile: str = "default"        # "default" or a path to a profile JSON
    baseline: str = ""              # a file from `readcost baseline`; findings in it do not count
    enable: list[str] = field(default_factory=list)   # adds opt-in features
    disable: list[str] = field(default_factory=list)
    min_severity: str = "info"      # findings below this are dropped
    advise_severity: str = "error"  # any finding this severe makes the verdict at least "advise"
    advise_cost_index: float = 15.0 # weighted findings per 1,000 words
    allow: list[str] = field(default_factory=list)
    comments: str = "doc"           # source files: "doc" or "all"
    block_cost_index: float = 30.0  # weighted findings per 1,000 words
    # Text and agent output end with a link for reporting a wrong finding.
    feedback_link: bool = True
    # Skip text that is clearly not English (readcost/lang.py) with a note.
    language_check: bool = True
    # Per-rule level: "error", "warn", "info" or "ignore"; "all" sets every rule.
    rules: dict[str, str] = field(default_factory=dict)
    # [[readcost.overrides]]: {"include": [globs], "exclude": [globs], "rules": {...}}, in order.
    overrides: list[dict] = field(default_factory=list)
    src: SrcConfig = field(default_factory=SrcConfig)
    hooks: HookConfig = field(default_factory=HookConfig)
    source: str = ""                # where the config came from
    cli_rules: dict[str, str] = field(default_factory=dict, repr=False)  # --error/--warn/--info/--ignore

    def wants(self, path: str) -> bool:
        if self.excluded(path):
            return False
        return any(fnmatch.fnmatch(c, g) for c in _candidates(path) for g in self.src.include)

    def excluded(self, path: str) -> bool:
        globs = [*self.src.exclude, *self.src.extend_exclude]
        return any(fnmatch.fnmatch(c, g) for c in _candidates(path) for g in globs)

    def rule_levels(self, path: str | None = None) -> dict[str, str]:
        """The level each rule has for ``path``: a severity, "ignore", or "default".

        "default" means on, at the detector's own severity. Later sources win:
        each rule's default, enable/disable, [readcost.rules], every override
        whose globs match ``path``, then the command line.
        """
        from .features import FEATURES

        levels = {k: "default" if f.default else "ignore" for k, f in FEATURES.items()}
        levels.update({k: "default" for k in self.enable if k in levels})
        levels.update({k: "ignore" for k in self.disable if k in levels})

        def apply(rules: dict[str, str]) -> None:
            if "all" in rules:
                levels.update(dict.fromkeys(levels, rules["all"]))
            levels.update({k: v for k, v in rules.items() if k in levels})

        apply(self.rules)
        for o in self.overrides:
            if path is None:
                continue
            hit = any(fnmatch.fnmatch(c, g) for c in _candidates(path) for g in o.get("include", ["*"]))
            miss = any(fnmatch.fnmatch(c, g) for c in _candidates(path) for g in o.get("exclude", []))
            if hit and not miss:
                apply(o.get("rules", {}))
        apply(self.cli_rules)
        return levels


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


def _check_rules(rules, where: str) -> dict[str, str]:
    """Validate a rules table: rule names (or "all") to a level."""
    from .features import FEATURES

    if not isinstance(rules, dict):
        raise ValueError(f"{where} must be a table of rule = level, not {rules!r}")
    for k, v in rules.items():
        if k != "all" and k not in FEATURES:
            raise ValueError(f"{where}: unknown rule {k!r}; `readcost explain` lists the rules")
        if v not in LEVELS:
            raise ValueError(f"{where}.{k} must be one of {', '.join(LEVELS)}, not {v!r}")
    return dict(rules)


def _check_overrides(value, source: str) -> list[dict]:
    if not isinstance(value, list) or not all(isinstance(o, dict) for o in value):
        raise ValueError(f"{source}: overrides must be [[readcost.overrides]] tables")
    out = []
    for n, o in enumerate(value, 1):
        where = f"{source}: overrides #{n}"
        unknown = set(o) - {"include", "exclude", "rules"}
        if unknown:
            raise ValueError(f"{where}: unknown key {', '.join(map(repr, sorted(unknown)))}")
        for g in ("include", "exclude"):
            if g in o and not (isinstance(o[g], list) and all(isinstance(x, str) for x in o[g])):
                raise ValueError(f"{where}: {g} must be a list of globs")
        out.append({"include": o.get("include", ["*"]), "exclude": o.get("exclude", []),
                    "rules": _check_rules(o.get("rules", {}), f"{where} rules")})
    return out


def _deprecated(source: str, key: str) -> None:
    print(f"readcost: warning: {source}: {key} is deprecated; use {DEPRECATED[key]}", file=sys.stderr)


def _apply(obj, data: dict, source: str, prefix: str = "") -> None:
    known = {f.name for f in fields(obj)} - {"source", "cli_rules"}
    for key, value in data.items():
        name = key.replace("-", "_")
        if not prefix and name in RETIRED_KEYS:
            print(f"readcost: warning: {source}: {key} is no longer configurable and is ignored; "
                  "change a rule's level under [readcost.rules] instead", file=sys.stderr)
            continue
        if name not in known:
            print(f"readcost: warning: {source}: unknown key {prefix + key!r} ignored", file=sys.stderr)
            continue
        current = getattr(obj, name)
        if isinstance(current, (HookConfig, SrcConfig)):
            if not isinstance(value, dict):
                raise ValueError(f"{source}: {prefix + key} must be a table, not {value!r}")
            if isinstance(current, HookConfig):
                # hooks.paths and hooks.exclude moved to [readcost.src].
                value = dict(value)
                for old, new in (("paths", "include"), ("exclude", "exclude")):
                    if old in value:
                        _deprecated(source, f"hooks.{old}")
                        moved = value.pop(old)
                        error = _check(new, getattr(obj.src, new), moved)
                        if error:  # name the key the user wrote
                            raise ValueError(f"{source}: {prefix}{key}.{old} {error}")
                        setattr(obj.src, new, moved)
            _apply(current, value, source, f"{prefix}{key}.")
            continue
        if name == "rules":
            obj.rules = _check_rules(value, f"{source}: {prefix}rules")
            continue
        if name == "overrides":
            obj.overrides = _check_overrides(value, source)
            continue
        if name in FEATURE_LISTS and not prefix:
            _deprecated(source, name)
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
    # A relative profile or baseline path means relative to the config file, not the cwd.
    if cfg.profile not in ("default", "") and not Path(cfg.profile).is_absolute():
        cfg.profile = str(candidate.resolve().parent / cfg.profile)
    if cfg.baseline and not Path(cfg.baseline).is_absolute():
        cfg.baseline = str(candidate.resolve().parent / cfg.baseline)
    return cfg
