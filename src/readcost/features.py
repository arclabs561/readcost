"""Feature registry and sentence-level detectors.

Each detector looks at one spaCy sentence and returns findings. Five features
come from "Why is AI-generated language so hard to understand?" (arXiv
2610.29162), which links them to human processing difficulty. hyphen-compound
and inline-list are rules derived from where those constructions show up in
technical prose. long-sentence is opt-in and not from the paper.
"""

from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass, field

from . import lexicon
from .extract import CODE


@dataclass(frozen=True)
class Feature:
    id: str
    title: str
    severity: str
    default: bool
    origin: str
    why: str
    fix: str
    bad: str
    good: str


FEATURES: dict[str, Feature] = {f.id: f for f in [
    Feature(
        "stacked-nouns", "Three or more nouns in a row", "warn", True, "paper",
        "Readers must work out how the nouns group before they can read on, "
        "and the grouping is often ambiguous (Squad Helps Dog Bite Victim).",
        "Keep at most two nouns together. Unpack the rest with a preposition "
        "or a relative clause.",
        "forcing source segment rebuilds",
        "forcing each segment to be rebuilt from its source",
    ),
    Feature(
        "long-dependency", "Related words far apart", "warn", True, "paper",
        "A subject far from its verb, or a verb far from its object, has to be held "
        "in working memory. The sentence is scored against a reference profile "
        "at the same sentence length.",
        "Put the subject next to its verb. Move long modifiers after the verb "
        "or into a second sentence.",
        "The index, built once from all documents and rebuilt only on compaction, serves queries.",
        "The index serves queries. It is built once and rebuilt only on compaction.",
    ),
    Feature(
        "inanimate-subject", "Thing doing a person's action", "info", True, "paper",
        "Verbs such as own, decide, promise, claim, hide or swallow normally take "
        "a person as subject. A file or function as the subject forces a "
        "figurative reading.",
        "Make the person the subject, or state the fact directly: what is out "
        "of scope, what is returned, what is not guaranteed.",
        "It does not own indexing or compaction.",
        "Indexing and compaction are left to the caller.",
    ),
    Feature(
        "denominal-verb", "Noun used as a verb", "info", True, "paper",
        "A noun pressed into service as a verb (calendar it, footnote it) "
        "makes the reader re-parse the word. Established verbs are not flagged.",
        "Use an ordinary verb phrase.",
        "Footnote the exception.",
        "Add a footnote about the exception.",
    ),
    Feature(
        "reduced-object-relative", "Object relative clause without 'that'", "info", True, "paper",
        "Object relatives (the house the contractors built) cost more to read "
        "than subject relatives; dropping the optional 'that' removes the cue "
        "that one has started.",
        "Keep the 'that', or turn it into a subject relative or a separate sentence.",
        "the format the reader expects",
        "the format that the reader expects",
    ),
    Feature(
        "hyphen-compound", "Ad hoc hyphenated noun compound", "warn", True, "derived",
        "Coined compounds such as storage-shrink or region-index are rare word "
        "pairs, which the paper links to slower reading. They usually hide a "
        "relationship that a preposition would state.",
        "Write the relationship out.",
        "the storage-shrink use case",
        "the main use: storing ID sets in less space",
    ),
    Feature(
        "inline-list", "Long list inside a sentence", "info", True, "derived",
        "Four or more coordinated items, or items joined by slashes, stretch "
        "the sentence's dependencies and are hard to scan.",
        "Use a bulleted list.",
        "It supports standard/Sugeno/Yager negations, OWA, power means, and uninorms.",
        "It supports:\n- negations (standard, Sugeno, Yager)\n- OWA\n- power means\n- uninorms",
    ),
    Feature(
        "long-sentence", "Long sentence", "info", False, "opt-in",
        "Not from the paper. Long sentences are a rough proxy for the other features.",
        "Split it.",
        "",
        "",
    ),
]}


@dataclass
class Finding:
    feature: str
    severity: str
    message: str
    excerpt: str
    sentence: str
    path: str
    line: int
    label: str = ""
    suggestion: str = ""

    def where(self) -> str:
        loc = self.path + (f"#{self.label}" if self.label else "")
        return f"{loc}:{self.line}" if self.line else loc


@dataclass
class Context:
    cfg: object
    profile: object
    allow: set[str]
    enabled: set[str]
    stats: dict = field(default_factory=dict)


def _norm(text: str) -> str:
    return " ".join(text.lower().replace("-", " ").split())


def _allowed(text: str, allow: set[str]) -> bool:
    """True if the whole phrase is an allowed term."""
    return _norm(text) in {_norm(a) for a in allow}


def _allowed_units(text: str, allow: set[str]) -> int:
    """Words saved by treating allowed terms inside ``text`` as single units."""
    t = f" {_norm(text)} "
    saved = 0
    for a in sorted({_norm(x) for x in allow}, key=len, reverse=True):
        if f" {a} " in t:
            saved += len(a.split()) - 1
            t = t.replace(f" {a} ", " _ ")
    return saved


def _excerpt(doc, tokens) -> str:
    lo = min(t.i for t in tokens)
    hi = max(t.i for t in tokens)
    return doc[lo:hi + 1].text


# --------------------------------------------------------------- detectors

def _noun_stack(token) -> list:
    out = [token]
    for child in token.children:
        if child.dep_ == "compound" and child.pos_ in ("NOUN", "PROPN") and child.text != CODE:
            out.extend(_noun_stack(child))
    return out


def stacked_nouns(sent, ctx: Context, taken: set[int]) -> list[tuple[str, str, list]]:
    out = []
    minimum = ctx.cfg.stacked_nouns_min
    for t in sent:
        if t.pos_ not in ("NOUN", "PROPN") or t.dep_ == "compound" or t.text == CODE:
            continue
        stack = _noun_stack(t)
        if len(stack) < minimum:
            continue
        capitals = sum(1 for x in stack if x.text[:1].isupper() and x.i != sent.start)
        if capitals >= 2:
            continue  # a proper name such as "Apple M3 Max"
        excerpt = _excerpt(sent.doc, stack)
        if len(stack) - _allowed_units(excerpt, ctx.allow) < minimum:
            continue  # e.g. "write-ahead log" counts as one unit
        taken.update(x.i for x in stack)
        sev = "error" if len(stack) >= minimum + 2 else "warn"
        out.append((sev, f"{len(stack)} nouns stacked: '{excerpt}'", stack))
    return out


def hyphen_compounds(sent, ctx: Context, taken: set[int]) -> list[tuple[str, str, list]]:
    out = []
    toks = list(sent)
    for k in range(1, len(toks) - 1):
        hy = toks[k]
        if hy.text != "-" or hy.whitespace_ or toks[k - 1].whitespace_:
            continue
        a, b = toks[k - 1], toks[k + 1]
        if a.i in taken or b.i in taken or CODE in (a.text, b.text):
            continue
        if a.lower_ in lexicon.HYPHEN_PREFIXES or not a.is_alpha or not b.is_alpha:
            continue
        # Noun-noun only: "caller-owned", "user-defined" are ordinary English.
        if a.pos_ not in ("NOUN", "PROPN") or b.pos_ not in ("NOUN", "PROPN"):
            continue
        if b.lower_ in lexicon.HYPHEN_SECONDS or (a.text[:1].isupper() and b.text[:1].isupper()):
            continue  # "X-based", "build-time"; names such as Elias-Fano
        if lexicon.is_lexicalized(a.lower_, b.lower_):
            continue  # "trade-off", "data-processing"
        head = b.head
        if not (head.pos_ in ("NOUN", "PROPN") and head.i > b.i and b.dep_ in ("compound", "amod", "nmod")):
            continue
        while head.dep_ == "compound" and head.head.pos_ in ("NOUN", "PROPN") and head.head.i > head.i:
            head = head.head
        excerpt = sent.doc[a.i:head.i + 1].text
        if _allowed(excerpt, ctx.allow) or _allowed(f"{a.text}-{b.text}", ctx.allow):
            continue
        out.append(("warn", f"coined compound modifier: '{excerpt}'", [a, b, head]))
    return out


SLASH_LIST = re.compile(r"(?<![\w./])([A-Za-z][\w-]*)(?:/[A-Za-z][\w-]*){2,}(?![\w/.])")
SLASH_OK = {"and/or", "input/output", "i/o", "read/write", "tcp/ip", "km/h", "on/off", "yes/no"}


def inline_lists(sent, ctx: Context) -> list[tuple[str, str, list]]:
    out = []
    minimum = ctx.cfg.inline_list_min_items
    seen = set()
    best: list = []
    for t in sent:
        if t.dep_ == "conj" or t.i in seen:
            continue
        items = [t, *t.conjuncts]
        seen.update(x.i for x in items)
        if len(items) > len(best):
            best = items
    # The parser often splits one long list into two groups; count commas too.
    text = sent.text
    last = text.rfind(",")
    comma_items = text.count(",") + 1 if last > 0 and re.search(r"\b(and|or)\b", text[last:]) else 0
    n = max(len(best), comma_items)
    if n >= minimum:
        out.append(("info", f"{n} items listed in one sentence", best if len(best) >= 2 else []))
    for m in SLASH_LIST.finditer(sent.text):
        if m.group(0).lower() in SLASH_OK:
            continue
        out.append(("info", f"slash-joined items: '{m.group(0)}'", []))
    return out


def dependency_z(sent, profile) -> tuple[float, int, tuple]:
    content = [t for t in sent if not t.is_punct and not t.is_space]
    arcs = [(abs(t.i - t.head.i), t) for t in content if t.head is not t and not t.head.is_punct]
    if not arcs or len(content) < 4:
        return 0.0, len(content), ()
    mean = statistics.mean(a for a, _ in arcs)
    a, b, sd = profile.dep_fit
    z = (mean - (a + b * math.log(len(content)))) / sd if sd else 0.0
    longest = max(arcs, key=lambda x: x[0])
    return z, len(content), (longest[0], longest[1], longest[1].head)


def long_dependency(sent, ctx: Context, has_list: bool) -> list[tuple[str, str, list]]:
    z, n, longest = dependency_z(sent, ctx.profile)
    ctx.stats.setdefault("dep_z", []).append(z)
    if has_list or n < ctx.cfg.long_dependency_min_tokens or z < ctx.cfg.long_dependency_z or not longest:
        return []
    dist, dep, head = longest
    return [("warn", f"'{head.text}' and '{dep.text}' are {dist} words apart (z = {z:.1f})", [dep, head])]


def inanimate_subjects(sent, ctx: Context) -> list[tuple[str, str, list]]:
    out = []
    for t in sent:
        if t.pos_ != "VERB":
            continue
        subjects = [c for c in t.children if c.dep_ == "nsubj"]
        if not subjects or not lexicon.is_animate_verb(t.lemma_.lower()):
            continue
        s = subjects[0]
        if s.text == CODE or (s.pos_ == "PRON" and s.lower_ in lexicon.INANIMATE_PRONOUNS):
            animate = False
        elif s.pos_ == "NOUN":
            animate = lexicon.noun_animacy(s.lemma_.lower())
        else:
            animate = None  # names and personal pronouns
        if animate is False:
            out.append(("info", f"'{s.text} ... {t.text}': a person's verb with a non-person subject", [s, t]))
    return out


def denominal_verbs(sent, ctx: Context) -> list[tuple[str, str, list]]:
    if not lexicon.has_wordnet():
        return []
    out = []
    for t in sent:
        if t.pos_ != "VERB" or not t.tag_.startswith("VB") or t.dep_ in ("amod", "compound"):
            continue
        if t.text[:1].isupper() or not any(c.dep_ in ("dobj", "obj", "nsubj", "prt") for c in t.children):
            continue
        inflected = t.tag_ in ("VBD", "VBG", "VBN") or (t.tag_ == "VBZ" and t.text.lower().endswith("es"))
        if not inflected and not any(c.dep_ in ("aux", "auxpass") for c in t.children) and t.i != sent.start:
            continue  # bare base-form "verbs" here are usually mis-tagged nouns
        if lexicon.is_denominal_candidate(t.lemma_.lower()):
            out.append(("info", f"'{t.text}' is mainly a noun used here as a verb", [t]))
    return out


def _relativizer(verb):
    for t in verb.subtree:
        if t.lower_ in ("that", "which", "who", "whom") and t.i < verb.i and t.tag_ in ("WDT", "WP", "IN", "DT"):
            return t
    return None


def reduced_object_relatives(sent, ctx: Context) -> list[tuple[str, str, list]]:
    out = []
    for t in sent:
        if t.dep_ != "relcl" or t.pos_ not in ("VERB", "AUX"):
            continue
        rel = _relativizer(t)
        subj = [c for c in t.children if c.dep_ in ("nsubj", "nsubjpass") and c is not rel]
        if subj and rel is None and subj[0].i > t.head.i:
            out.append(("info", f"'{t.head.text} {subj[0].text} {t.text}': object relative without 'that'",
                        [t.head, subj[0], t]))
    return out


def long_sentence(sent, ctx: Context) -> list[tuple[str, str, list]]:
    words = sum(1 for t in sent if t.is_alpha)
    if words > ctx.cfg.long_sentence_words:
        return [("info", f"{words} words in one sentence", [])]
    return []


def detect(sent, ctx: Context) -> list[tuple[str, str, str, list]]:
    """Run enabled detectors on one sentence: (feature, severity, message, tokens)."""
    results: list[tuple[str, str, str, list]] = []
    taken: set[int] = set()
    on = ctx.enabled

    def add(feature, items):
        for sev, msg, toks in items:
            results.append((feature, sev, msg, toks))

    if "stacked-nouns" in on:
        add("stacked-nouns", stacked_nouns(sent, ctx, taken))
    if "hyphen-compound" in on:
        add("hyphen-compound", hyphen_compounds(sent, ctx, taken))
    lists = inline_lists(sent, ctx) if "inline-list" in on else []
    add("inline-list", lists)
    if "long-dependency" in on:
        coordinated = any(len(t.conjuncts) >= 2 for t in sent)
        add("long-dependency", long_dependency(sent, ctx, has_list=bool(lists) or coordinated or ":" in sent.text))
    if "inanimate-subject" in on:
        add("inanimate-subject", inanimate_subjects(sent, ctx))
    if "denominal-verb" in on:
        add("denominal-verb", denominal_verbs(sent, ctx))
    if "reduced-object-relative" in on:
        add("reduced-object-relative", reduced_object_relatives(sent, ctx))
    if "long-sentence" in on:
        add("long-sentence", long_sentence(sent, ctx))
    return results
