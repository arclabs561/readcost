"""Run detectors over segments and summarize the result."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from pathlib import Path

from . import lexicon
from .config import Config, load_config, severity_rank
from .extract import Segment, extract
from .features import FEATURES, Context, Finding, detect
from .profile import Profile, load_profile

WEIGHTS = {"info": 0.5, "warn": 1.0, "error": 2.0}


@dataclass
class Result:
    path: str
    words: int = 0
    sentences: int = 0
    findings: list[Finding] = field(default_factory=list)
    mean_dep_z: float = 0.0
    cost_index: float = 0.0       # weighted findings per 1,000 words
    points: float = 0.0           # weighted findings
    verdict: str = "pass"         # pass | advise | block
    notes: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.feature] = out.get(f.feature, 0) + 1
        return out

    def to_dict(self) -> dict:
        return {
            "path": self.path, "words": self.words, "sentences": self.sentences,
            "verdict": self.verdict, "cost_index": round(self.cost_index, 2),
            "points": self.points, "mean_dep_z": round(self.mean_dep_z, 3),
            "counts": self.counts(), "notes": self.notes,
            "findings": [vars(f) for f in self.findings],
        }


def parse_line_ranges(spec: str | None) -> list[tuple[int, int]] | None:
    """'3-9,14,20-22' -> [(3, 9), (14, 14), (20, 22)]."""
    if not spec:
        return None
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        lo, _, hi = part.partition("-")
        out.append((int(lo), int(hi or lo)))
    return out


class Analyzer:
    def __init__(self, config: Config | None = None, profile: Profile | None = None):
        self.cfg = config or load_config()
        self.profile = profile or load_profile(self.cfg.profile)
        self._nlp = None
        enabled = {k for k, f in FEATURES.items() if f.default} | set(self.cfg.enable)
        self.enabled = enabled - set(self.cfg.disable)
        self.allow = {a.lower() for a in lexicon.DEFAULT_ALLOW} | {a.lower() for a in self.cfg.allow}

    @property
    def nlp(self):
        if self._nlp is None:
            import spacy

            try:
                self._nlp = spacy.load(self.cfg.model, disable=["ner"])
            except OSError as exc:
                raise RuntimeError(
                    f"spaCy model {self.cfg.model!r} is not installed; run `readcost setup`") from exc
        return self._nlp

    def sentences(self, seg: Segment):
        doc = self.nlp(seg.text)
        for sent in doc.sents:
            words = [t for t in sent if t.is_alpha]
            if len(words) < 4 or not any(t.pos_ in ("VERB", "AUX") for t in sent):
                continue
            yield sent

    def analyze(self, segments: list[Segment], path: str,
                lines: list[tuple[int, int]] | None = None) -> Result:
        result = Result(path=path)
        ctx = Context(self.cfg, self.profile, self.allow, self.enabled)
        floor = severity_rank(self.cfg.min_severity)
        docs = self.nlp.pipe([s.text for s in segments])
        for seg, doc in zip(segments, docs):
            for sent in doc.sents:
                words = [t for t in sent if t.is_alpha]
                if len(words) < 4 or not any(t.pos_ in ("VERB", "AUX") for t in sent):
                    continue
                line = seg.line_at(sent.start_char)
                # A hard-wrapped sentence spans several lines; keep it when any
                # of them was edited, not only its first.
                last_line = seg.line_at(max(sent.end_char - 1, sent.start_char))
                if lines and not any(lo <= last_line and line <= hi for lo, hi in lines):
                    continue
                result.sentences += 1
                result.words += len(words)
                for feature, sev, msg, toks in detect(sent, ctx):
                    tok_line, excerpt = line, ""
                    if toks:
                        first = min(toks, key=lambda t: t.i)
                        tok_line = seg.line_at(first.idx)
                        excerpt = sent.doc[first.i:max(t.i for t in toks) + 1].text
                    result.findings.append(Finding(
                        feature=feature, severity=sev, message=msg, excerpt=excerpt,
                        sentence=sent.text.strip(), path=path, line=tok_line, label=seg.label,
                        suggestion=FEATURES[feature].fix,
                    ))
        zs = ctx.stats.get("dep_z", [])
        result.mean_dep_z = statistics.mean(zs) if zs else 0.0
        # The verdict uses every finding; min_severity only trims what is shown.
        self._verdict(result)
        result.findings = [f for f in result.findings if severity_rank(f.severity) >= floor]
        if not lexicon.has_wordnet():
            result.notes.append("lexicon data missing: denominal-verb disabled, inanimate-subject reduced")
        return result

    def _verdict(self, result: Result) -> None:
        result.points = sum(WEIGHTS.get(f.severity, 0.5) for f in result.findings)
        result.cost_index = 1000.0 * result.points / result.words if result.words else 0.0
        advise_at = severity_rank(self.cfg.advise_severity)
        if result.points >= self.cfg.block_min_points and result.cost_index >= self.cfg.block_cost_index:
            result.verdict = "block"
        elif (result.cost_index >= self.cfg.advise_cost_index and result.points >= 1) \
                or any(severity_rank(f.severity) >= advise_at for f in result.findings):
            result.verdict = "advise"
        else:
            result.verdict = "pass"

    def check_text(self, text: str, fmt: str | None = "markdown", path: str = "<text>", *,
                   lines=None, field_path=None, last_only=False) -> Result:
        segments = extract(text, path, fmt, field_path=field_path, last_only=last_only,
                           comments=self.cfg.comments)
        return self.analyze(segments, path, lines)

    def check_records(self, text: str, fmt: str, path: str, *, field_path=None) -> list[Result]:
        """One result per message or JSONL record, labeled ``path#label``."""
        segments = extract(text, path, fmt, field_path=field_path, comments=self.cfg.comments)
        groups: dict[str, list[Segment]] = {}
        for seg in segments:
            groups.setdefault(seg.label, []).append(seg)
        results = []
        for label, segs in groups.items():
            result = self.analyze(segs, path)
            result.path = f"{path}#{label}" if label else path
            results.append(result)
        return results

    def check_file(self, path: str, fmt: str | None = None, *, lines=None,
                   field_path=None, last_only=False) -> Result:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
        return self.check_text(text, fmt, path, lines=lines, field_path=field_path, last_only=last_only)


_DEFAULT: Analyzer | None = None


def _default() -> Analyzer:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Analyzer()
    return _DEFAULT


def check_text(text: str, fmt: str = "markdown", **kw) -> Result:
    """Analyze a string. ``fmt`` is any format from ``readcost.extract.FORMATS``."""
    return _default().check_text(text, fmt, **kw)


def check_file(path: str, fmt: str | None = None, **kw) -> Result:
    return _default().check_file(path, fmt, **kw)
