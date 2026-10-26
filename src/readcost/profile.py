"""Reference profiles: what normal prose looks like for comparison.

A profile stores per-feature rates per 1,000 words and a fit of mean
dependency length against log(sentence length). Dependency-length findings are
scored against the fit, so the profile decides what counts as "far apart".
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import asdict, dataclass, field
from importlib import resources
from pathlib import Path


@dataclass
class Profile:
    name: str
    words: int
    sentences: int
    dep_fit: tuple[float, float, float]  # a, b, residual sd
    rates: dict[str, float] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    note: str = ""

    def to_json(self) -> str:
        d = asdict(self)
        d["dep_fit"] = list(self.dep_fit)
        return json.dumps(d, indent=1)

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        d = dict(d)
        d["dep_fit"] = tuple(d["dep_fit"])
        return cls(**d)


def load_profile(spec: str = "default") -> Profile:
    if spec in ("default", ""):
        data = resources.files("readcost").joinpath("data/default_profile.json").read_text()
        return Profile.from_dict(json.loads(data))
    return Profile.from_dict(json.loads(Path(spec).read_text()))


def fit_dependency(points: list[tuple[int, float]]) -> tuple[float, float, float]:
    pts = [(math.log(n), d) for n, d in points if n >= 4]
    if len(pts) < 10:
        raise ValueError("need at least 10 sentences of 4+ tokens to fit a profile")
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    spread = sum((x - mx) ** 2 for x in xs)
    if spread == 0:
        raise ValueError("every sentence has the same length; the profile needs varied sentences")
    b = sum((x - mx) * (y - my) for x, y in pts) / spread
    a = my - b * mx
    sd = statistics.pstdev([y - (a + b * x) for x, y in pts])
    return a, b, sd


def build_profile(paths: list[str], name: str, analyzer_factory, fmt: str | None = None) -> Profile:
    """Measure reference documents. ``analyzer_factory`` returns an Analyzer."""
    from .extract import extract

    analyzer = analyzer_factory()
    points: list[tuple[int, float]] = []
    counts: dict[str, int] = {}
    words = sentences = 0
    for p in paths:
        text = Path(p).read_text(encoding="utf-8", errors="ignore")
        for seg in extract(text, p, fmt):
            for sent in analyzer.sentences(seg):
                content = [t for t in sent if not t.is_punct and not t.is_space]
                arcs = [abs(t.i - t.head.i) for t in content if t.head is not t and not t.head.is_punct]
                if arcs:
                    points.append((len(content), statistics.mean(arcs)))
    fit = fit_dependency(points)
    profile = Profile(name, 0, 0, fit, {}, [str(p) for p in paths])
    # Second pass for feature rates, now that the dependency fit exists.
    analyzer.profile = profile
    for p in paths:
        result = analyzer.check_file(p, fmt)
        words += result.words
        sentences += result.sentences
        for f in result.findings:
            counts[f.feature] = counts.get(f.feature, 0) + 1
    profile.words, profile.sentences = words, sentences
    profile.rates = {k: round(1000.0 * v / words, 3) for k, v in sorted(counts.items())} if words else {}
    return profile
