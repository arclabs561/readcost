"""Baselines: record today's findings so that only new ones count.

A finding's key is its path relative to the baseline file, its feature, and a
hash of its sentence with whitespace collapsed. It has no line number, so a
finding stays old when lines above it change or its sentence is reflowed. Keys
are counted: a file that had two identical findings and now has three has one
new finding. The file holds hashes only, so it can be committed.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from .features import Finding

VERSION = 1
Key = tuple[str, str]  # (feature, sentence hash) within one path


def key_path(path: str, root: Path) -> str:
    """``path`` relative to ``root`` with forward slashes; pseudo-paths such as <stdin> as given."""
    if path.startswith("<") and path.endswith(">"):
        return path
    return Path(os.path.relpath(Path(path).resolve(), root.resolve())).as_posix()


def sentence_hash(sentence: str) -> str:
    # 16 hex digits: collisions within one file and feature are not a concern.
    return hashlib.sha256(" ".join(sentence.split()).encode()).hexdigest()[:16]


def finding_key(f: Finding, root: Path) -> tuple[str, str, str]:
    return key_path(f.path, root), f.feature, sentence_hash(f.sentence)


class Baseline:
    def __init__(self, counts: dict[str, dict[Key, int]], root: Path):
        self.counts = counts
        self.root = root

    def budget(self, path: str) -> Counter:
        """A fresh count of the baselined keys for ``path``, to spend on one check."""
        return Counter(self.counts.get(key_path(path, self.root), {}))

    def suppress(self, findings: list[Finding], budget: Counter) -> tuple[list[Finding], int]:
        """Drop each finding that the budget still covers; return the rest and how many were dropped."""
        kept, dropped = [], 0
        for f in findings:
            k = finding_key(f, self.root)[1:]
            if budget[k] > 0:
                budget[k] -= 1
                dropped += 1
            else:
                kept.append(f)
        return kept, dropped


def load_baseline(path: str) -> Baseline:
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or data.get("version") != VERSION:
        raise ValueError(f"{path}: not a readcost baseline of version {VERSION}; "
                         "rewrite it with `readcost baseline`")
    counts: dict[str, dict[Key, int]] = {}
    for e in data.get("findings", []):
        counts.setdefault(e["path"], {})[(e["feature"], e["sentence_hash"])] = int(e["count"])
    return Baseline(counts, Path(path).resolve().parent)


def dump_baseline(findings: list[Finding], path: str) -> str:
    """The baseline file for ``findings``: sorted, one entry per line, so diffs stay small."""
    root = Path(path).resolve().parent
    counts = Counter(finding_key(f, root) for f in findings)
    entries = [json.dumps({"path": p, "feature": feat, "sentence_hash": h, "count": n})
               for (p, feat, h), n in sorted(counts.items())]
    body = ",\n".join(entries) + "\n" if entries else ""
    return f'{{\n"version": {VERSION},\n"findings": [\n{body}]}}\n'
