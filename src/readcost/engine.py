"""Run detectors over segments and summarize the result."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from pathlib import Path

from . import lexicon, metrics, readtime
from .baseline import load_baseline
from .config import SEVERITIES, Config, load_config, severity_rank
from .extract import Segment, detect_format, extract
from .features import (
    FEATURES,
    Context,
    Finding,
    detect,
    repeated_frames,
    show,
    suggestion,
    undefined_acronyms,
)
from .lang import other_language
from .profile import Profile, load_profile

WEIGHTS = {"info": 0.5, "warn": 1.0, "error": 2.0}
# Verdict thresholds that were config keys until 0.3. Below SHORT_TEXT_WORDS
# a per-1,000 density is too noisy (one finding in a 20-word comment scores
# 50), so short texts are judged by weighted points. Commit messages are
# terser than prose: in 1,000 Go commit messages of 40+ words the 99th
# percentile cost index is 49, against 8 to 16 for essays, docs, READMEs and
# discussion (docs/evaluation.md, "Contexts").
SHORT_TEXT_WORDS = 40
SHORT_ADVISE_POINTS = 2.0
BLOCK_MIN_POINTS = 3.0            # a block needs at least this many weighted findings
COMMIT_ADVISE_COST_INDEX = 50.0
COMMIT_BLOCK_COST_INDEX = 100.0


@dataclass
class Result:
    path: str
    words: int = 0
    sentences: int = 0
    findings: list[Finding] = field(default_factory=list)
    mean_dep_z: float | None = None  # None when long-dependency is off
    cost_index: float = 0.0       # weighted findings per 1,000 words
    points: float = 0.0           # weighted findings
    verdict: str = "pass"         # pass | advise | block
    baselined: int = 0            # findings dropped because the baseline already had them
    notes: list[str] = field(default_factory=list)
    # Predicted reading time from eye-tracking data (readtime.py); None when
    # only some lines were checked or the model data is missing.
    reading_ms_per_word: float | None = None
    reading_seconds: float | None = None
    # Sentences predicted to cost the most reading time beyond their length,
    # worst first (see Analyzer._hotspots). Experimental: the model was
    # validated on whole texts, not single sentences.
    hotspots: list[dict] = field(default_factory=list)
    # Document measures (metrics.py); JSON output only, never the verdict.
    metrics: dict = field(default_factory=dict)
    # The checked text, so reports can quote the source line; not in to_dict.
    source: str = field(default="", repr=False)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.feature] = out.get(f.feature, 0) + 1
        return out

    def to_dict(self) -> dict:
        return {
            "path": self.path, "words": self.words, "sentences": self.sentences,
            "verdict": self.verdict, "baselined": self.baselined, "cost_index": round(self.cost_index, 2),
            "points": self.points, "mean_dep_z": None if self.mean_dep_z is None else round(self.mean_dep_z, 3),
            "counts": self.counts(), "notes": self.notes,
            "reading_ms_per_word": None if self.reading_ms_per_word is None else round(self.reading_ms_per_word, 1),
            "reading_seconds": None if self.reading_seconds is None else round(self.reading_seconds, 1),
            "hotspots": self.hotspots,
            "metrics": self.metrics,
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


TERM_FEATURES = ("stacked-nouns", "hyphen-compound")


def _first_use_only(findings: list[Finding]) -> list[Finding]:
    """Keep a compound's first use; later uses are a term the reader has met.

    Technical prose repeats compressed terms on purpose, so the cost is taken
    to fall on the first, unexplained use. This is a design choice: Biber and
    Gray 2010 argue, without measuring it, that such noun phrases are
    efficient for expert readers and costly for newcomers, and do not study
    repeated use.
    """
    seen: set[tuple[str, str]] = set()
    out = []
    for f in findings:
        if f.feature in TERM_FEATURES:
            key = (f.feature, " ".join(f.excerpt.lower().replace("-", " ").split()))
            if key in seen:
                continue
            seen.add(key)
        out.append(f)
    return out


class Analyzer:
    def __init__(self, config: Config | None = None, profile: Profile | None = None):
        self.cfg = config or load_config()
        self.profile = profile or load_profile(self.cfg.profile)
        self._nlp = None
        # Rules on for a file with no path-specific override; analyze() resolves per path.
        self.enabled = {k for k, v in self.cfg.rule_levels().items() if v != "ignore"}
        self.allow = {a.lower() for a in lexicon.DEFAULT_ALLOW} | {a.lower() for a in self.cfg.allow}
        self.baseline = load_baseline(self.cfg.baseline) if self.cfg.baseline else None

    @property
    def nlp(self):
        if self._nlp is None:
            from . import modelstore

            try:
                # The default model is fetched into a cache on first use.
                self._nlp = modelstore.load(self.cfg.model, disable=["ner"])
            except (OSError, ValueError) as exc:
                raise RuntimeError(
                    f"spaCy model {self.cfg.model!r} is not available ({exc}); run `readcost setup`") from exc
        return self._nlp

    def sentences(self, seg: Segment):
        doc = self.nlp(seg.text)
        for sent in doc.sents:
            words = [t for t in sent if t.is_alpha]
            if len(words) < 4 or not any(t.pos_ in ("VERB", "AUX") for t in sent):
                continue
            yield sent

    def analyze(self, segments: list[Segment], path: str,
                lines: list[tuple[int, int]] | None = None, *, context: str = "prose",
                budget=None) -> Result:
        """``budget``: baselined keys left for this file, shared when one file yields several results."""
        result = Result(path=path)
        if self.cfg.language_check:
            lang = other_language(" ".join(seg.text for seg in segments))
            if lang:
                # The rules, parser and reading-time model are English only; their
                # output on other languages would look confident and mean nothing.
                result.notes.append(f"text looks like {lang}, not English; readcost checks English only, "
                                    "so it reports no findings or reading time here")
                return result
        levels = self.cfg.rule_levels(path)
        enabled = {k for k, v in levels.items() if v != "ignore"}
        forced = {k: v for k, v in levels.items() if v in SEVERITIES}  # a level set in config or flags
        ctx = Context(self.cfg, self.profile, self.allow, enabled)
        floor = severity_rank(self.cfg.min_severity)
        docs = self.nlp.pipe([s.text for s in segments])
        framed: list[tuple[Segment, object]] = []  # prose sentences for repeated-frame
        spans: list[tuple] = []  # (segment, start, end, line, text) of each checked sentence
        parsed: list[tuple[Segment, object]] = []  # every parsed segment, for document-level rules
        checked: list = []                          # every sentence checked, for metrics
        for seg_index, (seg, doc) in enumerate(zip(segments, docs)):
            ctx.codes = seg.codes
            parsed.append((seg, doc))
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
                checked.append(sent)
                if not seg.in_list:
                    framed.append((seg, sent))
                text = show(ctx, sent.doc, sent.start, sent.end - 1)
                spans.append((seg_index, sent.start_char, sent.end_char, line, text))
                for feature, sev, msg, toks in detect(sent, ctx):
                    if feature in seg.skip:
                        continue
                    result.findings.append(self._finding(ctx, seg, sent, text, path, line,
                                                         feature, sev, msg, toks))
        if "repeated-frame" in enabled:
            for seg, sent, msg, toks in repeated_frames(framed):
                if "repeated-frame" in seg.skip:
                    continue
                ctx.codes = seg.codes
                text = show(ctx, sent.doc, sent.start, sent.end - 1)
                result.findings.append(self._finding(ctx, seg, sent, text, path, seg.line_at(sent.start_char),
                                                     "repeated-frame", "info", msg, toks))
        if "undefined-acronym" in enabled:
            keys = {(id(s.doc), s.start) for s in checked}
            for seg, sent, msg, toks in undefined_acronyms(parsed, keys, self.allow):
                if "undefined-acronym" in seg.skip:
                    continue
                ctx.codes = seg.codes
                text = show(ctx, sent.doc, sent.start, sent.end - 1)
                result.findings.append(self._finding(ctx, seg, sent, text, path, seg.line_at(sent.start_char),
                                                     "undefined-acronym", "info", msg, toks))
        result.findings = _first_use_only(result.findings)
        for f in result.findings:
            # A level set in [readcost.rules], an override or a flag replaces the detector's own.
            if f.feature in forced:
                f.severity = forced[f.feature]
        result.metrics = metrics.compute(checked)
        if self.baseline is not None:
            # Before the verdict, so that only new findings decide it.
            if budget is None:
                budget = self.baseline.budget(path)
            result.findings, result.baselined = self.baseline.suppress(result.findings, budget)
        zs = ctx.stats.get("dep_z", [])
        result.mean_dep_z = statistics.mean(zs) if zs else None
        # The verdict uses every finding; min_severity only trims what is shown.
        self._verdict(result, context)
        result.findings = [f for f in result.findings if severity_rank(f.severity) >= floor]
        unknown = sorted(set().union(*(seg.skip for seg in segments)) - set(FEATURES))
        if unknown:
            result.notes.append(f"unknown rule in a readcost directive: {', '.join(unknown)}; "
                                "`readcost explain` lists the rules")
        if not lexicon.has_wordnet():
            result.notes.append("lexicon data missing: denominal-verb disabled, inanimate-subject reduced")
        if lines is None and readtime.available():
            times = [readtime.word_times(seg.text) for seg in segments]
            words = sum(len(t) for t in times)
            ms = sum(w[3] for t in times for w in t)
            if words:
                result.reading_ms_per_word, result.reading_seconds = ms / words, ms / 1000
                result.hotspots = self._hotspots(segments, times, spans, ms / words)
        return result

    @staticmethod
    def _hotspots(segments, times, spans, mean_ms: float, keep: int = 5) -> list[dict]:
        """Sentences whose predicted reading time most exceeds their word count at the document's mean rate."""
        out = []
        for seg_index, start, end, line, text in spans:
            words = [w for w in times[seg_index] if start <= w[0] < end]
            if len(words) < 8:
                continue  # a few slow words in a short sentence are noise, not a hotspot
            ms = sum(w[3] for w in words)
            excess = ms - mean_ms * len(words)
            if excess <= 0:
                continue
            slow = sorted(words, key=lambda w: -w[3])[:3]
            out.append({"line": line, "sentence": text,
                        "words": len(words), "ms": round(ms), "excess_ms": round(excess),
                        "ms_per_word": round(ms / len(words)),
                        "slow_words": [{"word": w[2], "ms": round(w[3])} for w in slow]})
        return sorted(out, key=lambda h: -h["excess_ms"])[:keep]

    @staticmethod
    def _finding(ctx, seg, sent, text, path, line, feature, sev, msg, toks) -> Finding:
        excerpt = ""
        if toks:
            first = min(toks, key=lambda t: t.i)
            line = seg.line_at(first.idx)
            excerpt = show(ctx, sent.doc, first.i, max(t.i for t in toks))
        return Finding(feature=feature, severity=sev, message=msg, excerpt=excerpt, sentence=text,
                       path=path, line=line, label=seg.label, suggestion=suggestion(feature, text))

    def _verdict(self, result: Result, context: str = "prose") -> None:
        result.points = sum(WEIGHTS.get(f.severity, 0.5) for f in result.findings)
        result.cost_index = 1000.0 * result.points / result.words if result.words else 0.0
        advise_at = severity_rank(self.cfg.advise_severity)
        severe = any(severity_rank(f.severity) >= advise_at for f in result.findings)
        if result.words < SHORT_TEXT_WORDS:
            if result.points >= BLOCK_MIN_POINTS:
                result.verdict = "block"
            elif result.points >= SHORT_ADVISE_POINTS or severe:
                result.verdict = "advise"
            else:
                result.verdict = "pass"
            return
        advise_ci, block_ci = self.cfg.advise_cost_index, self.cfg.block_cost_index
        if context == "commit":
            advise_ci, block_ci = COMMIT_ADVISE_COST_INDEX, COMMIT_BLOCK_COST_INDEX
        if result.points >= BLOCK_MIN_POINTS and result.cost_index >= block_ci:
            result.verdict = "block"
        elif (result.cost_index >= advise_ci and result.points >= 1) \
                or any(severity_rank(f.severity) >= advise_at for f in result.findings):
            result.verdict = "advise"
        else:
            result.verdict = "pass"

    def check_text(self, text: str, fmt: str | None = "markdown", path: str = "<text>", *,
                   lines=None, field_path=None, last_only=False) -> Result:
        segments = extract(text, path, fmt, field_path=field_path, last_only=last_only,
                           comments=self.cfg.comments)
        context = "commit" if (fmt or detect_format(path, text)) == "commit" else "prose"
        result = self.analyze(segments, path, lines, context=context)
        result.source = text
        return result

    def check_records(self, text: str, fmt: str, path: str, *, field_path=None) -> list[Result]:
        """One result per message or JSONL record, labeled ``path#label``."""
        segments = extract(text, path, fmt, field_path=field_path, comments=self.cfg.comments)
        groups: dict[str, list[Segment]] = {}
        for seg in segments:
            groups.setdefault(seg.label, []).append(seg)
        results = []
        budget = self.baseline.budget(path) if self.baseline else None
        for label, segs in groups.items():
            result = self.analyze(segs, path, budget=budget)
            result.path = f"{path}#{label}" if label else path
            result.source = text
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
