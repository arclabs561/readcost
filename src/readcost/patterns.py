"""Experimental discourse-level measures. Nothing in readcost imports this module.

It exists to test a question (docs/evaluation.md, "Discourse patterns and
redundancy"): do the patterns that readers of model-written text complain
about track anything readers do, where readcost's sentence constructions do
not? No rule, verdict, metric or command uses it. It is not an AI-text
detector, and a rate from it says nothing about who wrote a text.

The detectors read the parse and closed-class grammar words (``not``,
``but``, ``rather than``, ``it``, forms of ``be``). None uses a list of
content words or stock phrases, so none can be satisfied by swapping a word.

Counted patterns, each with character spans:

- ``contrast``: a negated element followed by its correction. Four shapes:
  ``not-but`` ("not a bug but a feature"), ``comma-not`` ("a feature, not a
  bug"), ``rather-than``, and ``setup-resolution`` ("It isn't a bug. It's a
  feature.", in one sentence or across two). Zamaraeva et al. (2026) count
  the first three with regular expressions; slop-guard's ``contrast_pair``
  and ``setup_resolution`` and vale-ai-tells' ``ContrastiveFormulas`` cover
  the same ground with phrase patterns.
- ``triple``: a comma series of exactly three items ("fast, simple and
  safe"), the "rule of three". ``Report.lists`` counts series of three or
  more, so the share of lists that are triples can be compared.
- ``anticipatory-it``: "It is important to note that ...", "It should be
  noted that ...", "It's worth noting ...": an empty ``it``, a form of
  ``be``, an evaluating adjective or participle, then the clause that holds
  the content. The frame is Biber's extraposed complement clause; it also
  takes in "It is clear that" and "It is possible that".
- ``restatement``: a sentence most of whose content lemmas already occurred
  together in one earlier sentence of the same text.

Document measures:

- ``sentence_cv`` and ``paragraph_cv``: spread of sentence and paragraph
  lengths (standard deviation over mean). Low means uniform.
- ``opener_share``: share of sentences that begin with the most common first
  word.
- ``adjacent_overlap``: mean Jaccard overlap of content lemmas between
  neighbouring sentences (lexical cohesion; Coh-Metrix's argument and stem
  overlap measure the same idea).
- ``given_rate``: share of content words whose lemma the text has used
  before.
- ``closer_given``: the same share for the last sentence alone.
- ``lexical_density``: content words per word.
- ``gzip_ratio``: bytes over gzip-compressed bytes of the first
  ``GZIP_WORDS`` words, lower-cased. Higher means more repetition. Fixed
  length, because the ratio grows with the amount of text.
"""

from __future__ import annotations

import gzip
import statistics
from collections import Counter
from dataclasses import dataclass, field

CONTENT_POS = ("NOUN", "PROPN", "VERB", "ADJ", "ADV")
PATTERNS = ("contrast", "triple", "anticipatory-it", "restatement")
CONTRAST_KINDS = ("not-but", "comma-not", "rather-than", "setup-resolution")

NOT_BUT_WINDOW = 12        # words between the negation and "but"
COMMA_NOT_MAX = 8          # words in the rejected part of "X, not Y"
SERIES_ITEM_MAX = 4        # words in one item of a comma series
FRAME_WINDOW = 9           # tokens in which an anticipatory-it frame must complete
RESTATE_MIN_LEMMAS = 4     # content lemmas a sentence needs before it can restate
RESTATE_SHARE = 0.6        # share of them found in one earlier sentence
GZIP_WORDS = 150
MIN_SENTENCES_CV = 5
MIN_PARAGRAPHS_CV = 3
MIN_PARAGRAPH_WORDS = 20
MIN_SENTENCES_OPENER = 6

FINITE_TAGS = frozenset({"VBZ", "VBP", "VBD", "MD"})
SUBJECT_DEPS = frozenset({"nsubj", "nsubjpass", "expl", "csubj"})
POINTING_SUBJECTS = frozenset({"it", "this", "that", "these", "those", "they", "we"})
CLAUSE_BREAKS = frozenset({",", ";", ":", "—", "–", "--", "-"})
NEGATORS = frozenset({"not", "n't", "n’t"})
FOCUS_ADVERBS = frozenset({"just", "only", "merely", "simply", "really"})


@dataclass
class Hit:
    pattern: str
    kind: str
    start: int   # character offsets in the paragraph's text
    end: int
    paragraph: int


@dataclass
class Report:
    words: int = 0
    sentences: int = 0
    paragraphs: int = 0
    hits: list[Hit] = field(default_factory=list)
    lists: int = 0            # comma series of three or more items
    measures: dict = field(default_factory=dict)

    def count(self, pattern: str, kind: str | None = None) -> int:
        return sum(1 for h in self.hits if h.pattern == pattern and (kind is None or h.kind == kind))

    def per_1000(self, pattern: str, kind: str | None = None) -> float:
        return 1000.0 * self.count(pattern, kind) / self.words if self.words else 0.0

    def to_dict(self) -> dict:
        out = {"words": self.words, "sentences": self.sentences, "paragraphs": self.paragraphs}
        for p in PATTERNS:
            out[p] = self.count(p)
        for k in CONTRAST_KINDS:
            out[f"contrast/{k}"] = self.count("contrast", k)
        out["lists"] = self.lists
        out.update(self.measures)
        return out


# ----------------------------------------------------------------- helpers

def _words(sent) -> list:
    return [t for t in sent if t.is_alpha]


def _lemmas(sent) -> set[str]:
    return {t.lemma_.lower() for t in sent if t.is_alpha and t.pos_ in CONTENT_POS and not t.is_stop}


def _span(tokens) -> tuple[int, int]:
    return min(t.idx for t in tokens), max(t.idx + len(t.text) for t in tokens)


def _is_negator(t) -> bool:
    return t.lower_ in NEGATORS


def _starts_clause(tokens) -> bool:
    """True if a subject and a finite verb open these tokens: a new clause, not a corrected phrase."""
    head = tokens[:5]
    return any(t.dep_ in SUBJECT_DEPS for t in head) and any(t.tag_ in FINITE_TAGS for t in head)


def _cv(values: list[int]) -> float | None:
    mean = statistics.mean(values) if values else 0
    return round(statistics.pstdev(values) / mean, 3) if mean else None


# --------------------------------------------------------------- contrast

def _not_but(sent) -> list[list]:
    """"not X but Y" where Y is a phrase, not a clause of its own."""
    toks = [t for t in sent if not t.is_space]
    out = []
    for i, t in enumerate(toks):
        if not _is_negator(t):
            continue
        for j in range(i + 2, min(i + 2 + NOT_BUT_WINDOW, len(toks))):
            if toks[j].lower_ != "but":
                continue
            rest = toks[j + 1:]
            if rest and rest[0].lower_ == "also":
                rest = rest[1:]
            emphatic = toks[i + 1].lower_ in FOCUS_ADVERBS      # "not only X but (also) Y"
            if rest and (emphatic or not _starts_clause(rest)):
                out.append(toks[i:j + 2])
            break
    return out


def _comma_not(sent) -> list[list]:
    """"X, not Y": a negated phrase after a comma or dash, with no verb of its own."""
    toks = [t for t in sent if not t.is_space]
    out = []
    for i in range(1, len(toks) - 1):
        if toks[i].lower_ != "not" or toks[i - 1].text not in CLAUSE_BREAKS:
            continue
        tail = []
        for t in toks[i + 1:]:
            if t.is_punct:
                break
            tail.append(t)
        if tail and tail[0].lower_ in FOCUS_ADVERBS:
            continue   # "not only ..., but": counted by _not_but when it completes
        if (0 < len(tail) <= COMMA_NOT_MAX and not any(t.tag_ in FINITE_TAGS for t in tail)
                and any(t.pos_ in CONTENT_POS and not t.is_stop for t in tail)):
            out.append([toks[i - 1], toks[i], *tail])
    return out


def _rather_than(sent) -> list[list]:
    toks = [t for t in sent if not t.is_space]
    return [[a, b] for a, b in zip(toks, toks[1:]) if a.lower_ == "rather" and b.lower_ == "than"]


def _setup(sent):
    """The negator of "It isn't X" or "This is not about X", if the sentence has one; else None."""
    for t in sent:
        if not _is_negator(t):
            continue
        head = t.head
        subjects = [c for c in head.children if c.dep_ in SUBJECT_DEPS]
        if subjects and subjects[0].lower_ in POINTING_SUBJECTS and subjects[0].i < t.i:
            return t
    return None


def _resolution(tokens) -> list | None:
    """"It's Y", "That is Y" at the start of these tokens."""
    toks = [t for t in tokens if not t.is_space and not t.is_punct][:3]
    if len(toks) >= 2 and toks[0].lower_ in POINTING_SUBJECTS and toks[1].lemma_ == "be":
        if not any(_is_negator(t) for t in toks):
            return toks[:2]
    return None


def _setup_resolution(sents) -> list[list]:
    out = []
    for k, sent in enumerate(sents):
        neg = _setup(sent)
        if neg is None:
            continue
        after = [t for t in sent if t.i > neg.i]
        found = None
        for i, t in enumerate(after):
            if t.text in CLAUSE_BREAKS:
                found = _resolution(after[i + 1:])
                if found:
                    break
        if not found and k + 1 < len(sents):
            found = _resolution(list(sents[k + 1]))
        if found:
            out.append([neg, *found])
    return out


# ------------------------------------------------------- other counted patterns

def _series(sent) -> list[tuple[int, list]]:
    """Comma series that end in "and" or "or": (number of items, tokens from the first item to the last).

    Read from the surface, because the small parser often splits one list
    into several coordinations. An item is at most ``SERIES_ITEM_MAX`` words
    and ends in a word of the same part of speech as the other items' last
    words: "fast, simple and safe", "read, parse, and store the rows".
    """
    toks = [t for t in sent if not t.is_space]
    out = []
    for j, cc in enumerate(toks):
        if cc.lower_ not in ("and", "or") or j < 3 or j + 1 >= len(toks):
            continue
        end = j - 1 if toks[j - 1].text == "," else j     # the serial comma is optional
        ends = []                                            # index of each earlier item's last word
        k = end
        while k > 0:
            item = []
            while k > 0 and not toks[k - 1].is_punct and len(item) <= SERIES_ITEM_MAX:
                k -= 1
                item.append(toks[k])
            if not item or len(item) > SERIES_ITEM_MAX and ends:
                break
            ends.append(k + len(item) - 1)
            if k == 0 or toks[k - 1].text != ",":
                break
            k -= 1
        if len(ends) < 2:
            continue
        pos = toks[ends[0]].pos_
        tail = next((t for t in toks[j + 1:j + 1 + SERIES_ITEM_MAX] if t.pos_ == pos), None)
        if tail is None:
            continue
        n = 1
        for e in ends:
            if toks[e].pos_ != pos:
                break
            n += 1
        if n >= 3:
            first = ends[n - 2]
            out.append((n, toks[first:toks.index(tail) + 1]))
    return out


def _anticipatory_it(sent) -> list | None:
    """"It is ADJ (to VERB) that ..." or "It is worth VERBing ..." at the start of a sentence."""
    toks = [t for t in sent if not t.is_space and not t.is_punct][:FRAME_WINDOW]
    if len(toks) < 4 or toks[0].lower_ != "it":
        return None
    be = next((i for i, t in enumerate(toks[1:4], 1) if t.lemma_ == "be"), None)
    if be is None:
        return None
    judge = next((i for i in range(be + 1, min(be + 4, len(toks)))
                  if toks[i].pos_ == "ADJ" or toks[i].tag_ == "VBN" or toks[i].lower_ == "worth"), None)
    if judge is None:
        return None
    for i in range(judge + 1, len(toks)):
        t = toks[i]
        if t.lower_ == "that" and t.dep_ in ("mark", "nsubj", "dobj", "det"):
            return toks[:i + 1] if t.dep_ == "mark" else None
        if toks[judge].lower_ == "worth" and t.tag_ == "VBG":
            return toks[:i + 1]
        if t.tag_ in FINITE_TAGS:
            return None
    return None


def _restatements(sents) -> list[int]:
    """Indexes of sentences whose content lemmas mostly occurred together in one earlier sentence."""
    seen: list[set[str]] = []
    out = []
    for k, sent in enumerate(sents):
        lemmas = _lemmas(sent)
        if len(lemmas) >= RESTATE_MIN_LEMMAS and any(
                len(lemmas & earlier) >= RESTATE_SHARE * len(lemmas) for earlier in seen):
            out.append(k)
        seen.append(lemmas)
    return out


# ------------------------------------------------------------------ report

def measure(nlp, paragraphs: list[str]) -> Report:
    """Patterns and document measures for one text, given as its paragraphs of plain prose."""
    report = Report()
    docs = list(nlp.pipe([p for p in paragraphs if p.strip()]))
    all_sents: list[tuple[int, object]] = []
    for p, doc in enumerate(docs):
        sents = [s for s in doc.sents if len(_words(s)) >= 3]
        all_sents.extend((p, s) for s in sents)
        for sent in sents:
            for kind, finder in (("not-but", _not_but), ("comma-not", _comma_not), ("rather-than", _rather_than)):
                for toks in finder(sent):
                    report.hits.append(Hit("contrast", kind, *_span(toks), p))
            for n, toks in _series(sent):
                report.lists += 1
                if n == 3:
                    report.hits.append(Hit("triple", "", *_span(toks), p))
            frame = _anticipatory_it(sent)
            if frame:
                report.hits.append(Hit("anticipatory-it", "", *_span(frame), p))
        for toks in _setup_resolution(sents):
            report.hits.append(Hit("contrast", "setup-resolution", *_span(toks), p))
    sents = [s for _, s in all_sents]
    for k in _restatements(sents):
        report.hits.append(Hit("restatement", "", sents[k].start_char, sents[k].end_char, all_sents[k][0]))
    report.sentences = len(sents)
    report.paragraphs = len(docs)
    report.words = sum(len(_words(s)) for s in sents)
    report.measures = _document_measures(docs, sents)
    return report


def _document_measures(docs, sents) -> dict:
    lengths = [len(_words(s)) for s in sents]
    para_lengths = [n for n in (sum(1 for t in d if t.is_alpha) for d in docs) if n >= MIN_PARAGRAPH_WORDS]
    words = [t for s in sents for t in s if t.is_alpha]
    content = [t for t in words if t.pos_ in CONTENT_POS and not t.is_stop]
    lemma_sets = [_lemmas(s) for s in sents]
    overlaps = [len(a & b) / len(a | b) for a, b in zip(lemma_sets, lemma_sets[1:]) if a | b]
    seen: set[str] = set()
    given = 0
    last_given = None
    for k, s in enumerate(sents):
        own = [t.lemma_.lower() for t in s if t.is_alpha and t.pos_ in CONTENT_POS and not t.is_stop]
        hits = sum(1 for w in own if w in seen)
        given += hits
        if k == len(sents) - 1 and own and k >= MIN_SENTENCES_CV - 1:
            last_given = round(hits / len(own), 3)
        seen.update(own)
    openers = Counter(w[0].lower_ for w in (_words(s) for s in sents) if w)
    window = " ".join(t.lower_ for t in words[:GZIP_WORDS]).encode()
    return {
        "sentence_cv": _cv(lengths) if len(lengths) >= MIN_SENTENCES_CV else None,
        "paragraph_cv": _cv(para_lengths) if len(para_lengths) >= MIN_PARAGRAPHS_CV else None,
        "opener_share": (round(openers.most_common(1)[0][1] / len(sents), 3)
                         if len(sents) >= MIN_SENTENCES_OPENER else None),
        "adjacent_overlap": round(statistics.mean(overlaps), 3) if overlaps else None,
        "given_rate": round(given / len(content), 3) if content else None,
        "closer_given": last_given,
        "lexical_density": round(len(content) / len(words), 3) if words else None,
        "gzip_ratio": (round(len(window) / len(gzip.compress(window, 9, mtime=0)), 3)
                       if len(words) >= GZIP_WORDS else None),
    }
