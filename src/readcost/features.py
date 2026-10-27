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
from typing import TYPE_CHECKING

from . import lexicon
from .extract import CODE

if TYPE_CHECKING:
    from .config import Config
    from .profile import Profile


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
        "denominal-verb", "Noun used as a verb", "info", False, "paper",
        "A noun pressed into service as a verb (calendar it, footnote it) "
        "makes the reader re-parse the word. Off by default: on well-edited "
        "prose almost every hit was a settled verb (scale, host, fork), because "
        "the lexicon cannot tell a new coinage from an old one (docs/evaluation.md).",
        "Use an ordinary verb phrase.",
        "The script will bucket the requests by hour.",
        "The script will group the requests by hour.",
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
    Feature(
        "nominalization", "Action written as a noun", "info", False, "opt-in",
        "A verb or adjective turned into a noun (validation, completeness) hides who "
        "does what. Instruction-tuned models use these at 1.5 to 2 times the human "
        "rate (Reinhart et al. 2025). Flagged only after a light verb (perform, "
        "provide, make) or when two such nouns with 'of' share a sentence.",
        "Use the verb: 'validates the input', not 'performs validation of the input'.",
        "The tool performs validation of the input.",
        "The tool validates the input.",
    ),
    Feature(
        "participial-clause", "Clause hung on an -ing verb", "info", False, "opt-in",
        "A present participle clause set off by a comma (', making X faster'; "
        "'Building on this, ...') leaves the reader to work out its subject and "
        "how it relates to the main clause. Language models use them several "
        "times as often as people (Reinhart et al. 2025).",
        "Say the relation: 'so', 'because', 'which', or a second sentence.",
        "The parser caches every token, making lookups faster.",
        "The parser caches every token, so lookups are faster.",
    ),
    Feature(
        "repeated-frame", "Same sentence frame repeated", "info", False, "opt-in",
        "Three or more sentences in one document share a run of six or more "
        "part-of-speech tags. Repeated syntactic templates mark model output "
        "(Shaib et al. 2024 measure them across many texts, not within one, and "
        "make no claim about reading cost). Formulaic text such as changelogs "
        "repeats on purpose; list items, headings and tables are skipped.",
        "Vary the sentences, or turn the parallel statements into a list.",
        "This change reduces latency. This change improves speed. This change lowers cost.",
        "This change reduces latency, improves speed and lowers cost.",
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
    cfg: Config
    profile: Profile
    allow: set[str]
    enabled: set[str]
    stats: dict = field(default_factory=dict)
    codes: dict[int, str] = field(default_factory=dict)  # CODE offset in the doc -> original


def show(ctx: Context | None, doc, lo: int, hi: int) -> str:
    """Text of tokens lo..hi (inclusive) with code placeholders restored."""
    codes = ctx.codes if ctx else {}
    parts = [codes.get(t.idx, t.text) + t.whitespace_ if t.text == CODE else t.text_with_ws
             for t in doc[lo:hi + 1]]
    return "".join(parts).strip()


def _w(ctx: Context, t) -> str:
    return show(ctx, t.doc, t.i, t.i)


def _norm(text: str) -> str:
    return " ".join(text.lower().replace("-", " ").split())


def _allowed(text: str, allow: set[str]) -> bool:
    """True if the whole phrase is an allowed term."""
    return _norm(text) in {_norm(a) for a in allow}


def _excerpt(doc, tokens, ctx: Context | None = None) -> str:
    return show(ctx, doc, min(t.i for t in tokens), max(t.i for t in tokens))


def _merge(spans: list[set[int]]) -> list[set[int]]:
    """Union overlapping spans, so "tree-sitter" allowed and hyphenated is one unit."""
    out: list[set[int]] = []
    for span in spans:
        for other in [o for o in out if o & span]:
            out.remove(other)
            span = span | other
        out.append(span)
    return out


def _looks_like_package(doc, span: set[int]) -> bool:
    """"markdown-it-py", "utf8-ranges": a part of two letters or with a digit."""
    parts = [doc[i] for i in sorted(span) if doc[i].text != "-"]
    return any(len(p.text) <= 2 or any(c.isdigit() for c in p.text) for p in parts)


def _hyphen_spans(sent) -> list[set[int]]:
    """Token indices of each hyphen-joined word ("region-shard-segment", "tree-sitter")."""
    spans: list[set[int]] = []
    toks = list(sent)
    for k in range(1, len(toks) - 1):
        a, hy, b = toks[k - 1], toks[k], toks[k + 1]
        if hy.text != "-" or hy.whitespace_ or a.whitespace_:
            continue
        if spans and a.i in spans[-1]:
            spans[-1] |= {hy.i, b.i}
        else:
            spans.append({a.i, hy.i, b.i})
    return spans


# A clause opened by one of these after a noun is an embedded question, not a
# relative clause: "prints how long the search takes".
QUESTION_WORDS = {"how", "what", "whether", "if"}
# "why", "where", "when" open relative clauses only after these nouns.
WH_RELATIVE_HEADS = {"reason", "place", "time", "day", "year", "case", "moment", "point",
                     "situation", "period", "way", "location", "spot", "area", "stage", "step"}


def _opens_with_wh(clause) -> bool:
    """True if the clause starts with a wh-word: it is not a reduced relative."""
    first = clause.left_edge
    return first.i < clause.i and (first.tag_ in ("WRB", "WP", "WP$", "WDT")
                                   or first.lower_ in QUESTION_WORDS)


def _embedded_question(clause, noun) -> bool:
    first = clause.left_edge
    if first.i >= clause.i:
        return False
    if first.lower_ in QUESTION_WORDS:
        return True
    return first.lower_ in ("why", "where", "when") and noun.lemma_.lower() not in WH_RELATIVE_HEADS


def _mostly_upper(sent) -> bool:
    words = [t for t in sent if t.is_alpha and len(t.text) > 1]
    return bool(words) and sum(t.is_upper for t in words) >= 0.7 * len(words)


# --------------------------------------------------------------- detectors

def _allowed_spans(sent, allow: set[str]) -> list[set[int]]:
    """Token indices of each allowed term found in the sentence, hyphens included."""
    words = [t for t in sent if t.text != "-"]
    spans = []
    for phrase in {_norm(a) for a in allow}:
        parts = phrase.split()
        n = len(parts)
        for k in range(len(words) - n + 1):
            if [w.lower_ for w in words[k:k + n]] == parts:
                spans.append(set(range(words[k].i, words[k + n - 1].i + 1)))
    return spans


def _noun_stack(token) -> list:
    # Iterative: a very long run of nouns would overflow Python's recursion limit.
    out, todo = [], [token]
    while todo:
        t = todo.pop()
        out.append(t)
        todo.extend(c for c in t.children
                    if c.dep_ == "compound" and c.pos_ in ("NOUN", "PROPN") and c.text != CODE)
    return out


def stacked_nouns(sent, ctx: Context, taken: set[int],
                  spans: list[set[int]] | None = None) -> list[tuple[str, str, list]]:
    # An allowed term ("write-ahead log") and a hyphenated word ("reader-patience",
    # "markdown-it-py") each count as one unit; a coined hyphen pair in front
    # of a noun is hyphen-compound's to report.
    spans = _merge((spans or []) + _hyphen_spans(sent))
    out = []
    minimum = ctx.cfg.stacked_nouns_min
    caps = _mostly_upper(sent)
    for t in sent:
        if t.pos_ not in ("NOUN", "PROPN") or t.dep_ == "compound" or t.text == CODE:
            continue
        stack = _noun_stack(t)
        if t.tag_ == "NNS" and any(_embedded_question(c, t) for c in t.children
                                   if c.dep_ in ("relcl", "ccomp", "acl")):
            # "prints how long the search takes": the head is the verb.
            stack = [x for x in stack if x.i != t.i]
        if not stack:
            continue
        if not any(a.pos_ in ("VERB", "AUX") for a in t.ancestors):
            # With no verb above it, a plural inside the stack is usually the
            # misparsed main verb ("specification defines slices", "keys
            # default to"); compound modifiers are rarely plural. Keep only
            # the words before it, the verb's subject.
            verb = next((x for x in sorted(stack, key=lambda x: x.i) if x.i != t.i and x.tag_ == "NNS"), None)
            if verb is not None:
                stack = [x for x in stack if x.i < verb.i]
                if not stack:
                    continue
        first = min(stack, key=lambda x: x.i)
        if first.i == sent.start and first.tag_ in ("NN", "VB") and sent.root.i in {x.i for x in stack}:
            # "Flag prose constructions that ...": with no main verb parsed,
            # the first word is an imperative verb.
            stack = [x for x in stack if x.i != first.i]
        if len(stack) < minimum:
            continue
        if any(x.lower_ in ("et", "al", "al.") for x in stack) or \
                any(c.lower_ in ("et", "al", "al.") for x in stack for c in x.children):
            continue  # a citation such as "Chen et al"
        capitals = sum(1 for x in stack if x.text[:1].isupper() and x.i != sent.start)
        if capitals >= 2 and not caps:
            continue  # a proper name such as "Apple M3 Max"
        excerpt = _excerpt(sent.doc, stack, ctx)
        ids = {x.i for x in stack}
        # A leading name or acronym classifies the rest ("Go programming
        # language", "SQLite database file"); count the units after it.
        for x in sorted(stack, key=lambda x: x.i):
            is_name = x.pos_ == "PROPN" or (x.is_upper and len(x.text) > 1) or x.text == CODE
            if caps or not is_name or (x.i == sent.start and not x.is_upper) or len(ids) == 1:
                break
            ids.discard(x.i)
        touched = [s for s in spans if s & ids]
        units = len(ids - set().union(*touched)) + len(touched)
        if units < minimum:
            continue
        taken.update(x.i for x in stack)
        sev = "error" if units >= minimum + 2 else "warn"
        out.append((sev, f"{units} nouns stacked: '{excerpt}'", stack))
    return out


def hyphen_compounds(sent, ctx: Context, taken: set[int],
                     allowed: set[int] = frozenset()) -> list[tuple[str, str, list]]:
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
        if any(a.i in span and _looks_like_package(sent.doc, span) for span in _hyphen_spans(sent)):
            continue  # "py-spy", "markdown-it-py": a package name
        # Noun-noun only: "caller-owned", "user-defined" are ordinary English.
        if a.pos_ not in ("NOUN", "PROPN") or b.pos_ not in ("NOUN", "PROPN"):
            continue
        if b.lower_ in lexicon.HYPHEN_SECONDS or (a.text[:1].isupper() and b.text[:1].isupper()):
            continue  # "X-based", "build-time"; names such as Elias-Fano
        if lexicon.is_lexicalized(a.lower_, b.lower_) or lexicon.is_established_pair(a.lower_, b.lower_):
            continue  # "trade-off", "key-value", "product-market": in common use
        head = b.head
        if not (head.pos_ in ("NOUN", "PROPN") and head.i > b.i and b.dep_ in ("compound", "amod", "nmod")):
            continue
        while head.dep_ == "compound" and head.head.pos_ in ("NOUN", "PROPN") and head.head.i > head.i:
            head = head.head
        if head.i in taken and head.i not in allowed:
            # Already reported. A head inside an allowed term ("storage-shrink
            # use case") is still a coined modifier on that term.
            continue
        excerpt = show(ctx, sent.doc, a.i, head.i)
        if _allowed(excerpt, ctx.allow) or _allowed(f"{a.text}-{b.text}", ctx.allow):
            continue
        taken.update((a.i, b.i, head.i))
        out.append(("warn", f"coined compound modifier: '{excerpt}'", [a, b, head]))
    return out


SLASH_LIST = re.compile(r"(?<![\w./])([A-Za-z][\w-]*)(?:/[A-Za-z][\w-]*){2,}(?![\w/.])")
# "cmd/compile/internal/ssa", "x/net/http2": a package path, not a list.
PATH_LIKE = re.compile(r"[a-z][a-z0-9_.-]*(?:/[a-z0-9_.-]+){2,}|[a-z0-9_.-]*[0-9_][a-z0-9_.-]*(?:/[a-z0-9_.-]+)+")
SLASH_OK = {"and/or", "input/output", "i/o", "read/write", "tcp/ip", "km/h", "on/off", "yes/no"}


def _code_items(items) -> bool:
    """True when half or more of the items are code."""
    own = []
    for t in items:
        others = {x.i for o in items if o is not t for x in o.subtree}
        own.append([x for x in t.subtree if x.i not in others and not x.is_punct and x.dep_ != "cc"])
    return sum(1 for words in own if any(x.text == CODE for x in words)) >= len(items) / 2


# A chunk with a subject or a modal is a clause, not a list item.
CLAUSE_DEPS = {"nsubj", "nsubjpass", "csubj", "expl"}


def _comma_items(sent) -> list[list]:
    """The verbless comma-separated chunks that end in an "and"/"or" item.

    Returns the items after the first one; the first item shares its chunk
    with the verb that introduces the list ("It supports A, B, and C").
    """
    chunks, cur = [], []
    for t in sent:
        if t.text == ",":
            chunks.append(cur)
            cur = []
        elif not (t.is_punct and t.i == sent.end - 1):
            cur.append(t)
    chunks.append(cur)
    last = next((k for k in range(len(chunks) - 1, 0, -1)
                 if chunks[k] and chunks[k][0].lower_ in ("and", "or")), None)
    if last is None:
        return []
    items = []
    for k in range(last, 0, -1):
        words = [t for t in chunks[k] if t.lower_ not in ("and", "or") or t.i != chunks[k][0].i]
        if not words or any(t.dep_ in CLAUSE_DEPS or t.tag_ == "MD" for t in words):
            break
        items.insert(0, words)
    return items


def _code_chunks(chunks) -> bool:
    return sum(1 for c in chunks if any(t.text == CODE for t in c)) >= len(chunks) / 2


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
    # The small parser often splits one long list into groups, so comma-separated
    # chunks count too, but only verbless ones: counting every comma flagged
    # clauses and asides as lists. A list of code names reads like a list
    # already. Lists of short items are still reported: most raters in the
    # ten-model evaluation call them defensible (docs/evaluation.md).
    chunks = _comma_items(sent)
    if len(best) >= minimum and not _code_items(best):
        out.append(("info", f"{len(best)} items listed in one sentence", best))
        return out  # slash-joined items in the same sentence are part of that list
    if len(chunks) + 1 >= minimum and not _code_chunks(chunks):
        out.append(("info", f"{len(chunks) + 1} items listed in one sentence",
                    [t for c in chunks for t in c]))
        return out
    for m in SLASH_LIST.finditer(sent.text):
        if m.group(0).lower() in SLASH_OK or PATH_LIKE.fullmatch(m.group(0)):
            continue
        out.append(("info", f"slash-joined items: '{m.group(0)}'", []))
    return out


def dependency_arcs(sent) -> list[tuple[int, object, object]]:
    """(distance, dependent, head) for each arc between words.

    Distance counts words only, so the hyphens in "region-shard-segment"
    do not lengthen an arc. The root has no arc. The reference profile must
    be fitted with the same arcs.
    """
    pos = {t.i: k for k, t in enumerate(t for t in sent if not t.is_punct and not t.is_space)}
    return [(abs(pos[t.i] - pos[t.head.i]), t, t.head) for t in sent
            if t.i in pos and t.head.i != t.i and t.head.i in pos]


def dependency_z(sent, profile) -> tuple[float, int, tuple]:
    n = sum(1 for t in sent if not t.is_punct and not t.is_space)
    arcs = dependency_arcs(sent)
    if not arcs or n < 4:
        return 0.0, n, ()
    mean = statistics.mean(d for d, _, _ in arcs)
    a, b, sd = profile.dep_fit
    z = (mean - (a + b * math.log(n))) / sd if sd else 0.0
    return z, n, max(arcs, key=lambda x: x[0])


def long_dependency(sent, ctx: Context, has_list: bool) -> list[tuple[str, str, list]]:
    z, n, longest = dependency_z(sent, ctx.profile)
    ctx.stats.setdefault("dep_z", []).append(z)
    if has_list or n < ctx.cfg.long_dependency_min_tokens or z < ctx.cfg.long_dependency_z or not longest:
        return []
    dist, dep, head = longest
    return [("warn", f"'{_w(ctx, head)}' and '{_w(ctx, dep)}' are {dist} words apart (z = {z:.1f})", [dep, head])]


def inanimate_subjects(sent, ctx: Context) -> list[tuple[str, str, list]]:
    out = []
    for t in sent:
        if t.pos_ != "VERB":
            continue
        subjects = [c for c in t.children if c.dep_ == "nsubj"]
        if not subjects or not lexicon.is_animate_verb(t.lemma_.lower()):
            continue
        s = subjects[0]
        if s.lower_ in ("that", "which") and t.dep_ == "relcl":
            # "the engineer that owns": the relative pronoun stands for its antecedent.
            ante = t.head
            animate = lexicon.noun_animacy(ante.lemma_.lower()) if ante.pos_ == "NOUN" else None
        elif s.text == CODE or any(c.text == CODE for c in s.children):
            # An identifier as subject ("`parse()` returns") is the normal
            # register of technical docs, where readers anchor on names.
            animate = None
        elif s.pos_ == "PRON" and s.lower_ in lexicon.INANIMATE_PRONOUNS:
            animate = False
        elif s.pos_ == "NOUN":
            animate = lexicon.noun_animacy(s.lemma_.lower())
        else:
            animate = None  # names and personal pronouns
        if animate is False:
            out.append(("info", f"'{_w(ctx, s)} ... {t.text}': a person's verb with a non-person subject", [s, t]))
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
        nxt = sent.doc[t.i + 1] if t.i + 1 < len(sent.doc) else None
        if any(c.dep_ == "prt" for c in t.children) or (nxt is not None and nxt.dep_ == "prt"):
            continue  # phrasal verbs: "figure out", "wind up", "light up"
        if lexicon.is_denominal_candidate(t.lemma_.lower()):
            out.append(("info", f"'{t.text}' is mainly a noun used here as a verb", [t]))
    return out


LIGHT_RELATIVE_HEADS = {"time", "way", "all", "reason", "day", "moment", "place"}


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
        if _opens_with_wh(t):
            continue  # "prints how long the search takes", "the reason why it exists"
        rel = _relativizer(t)
        subj = [c for c in t.children if c.dep_ in ("nsubj", "nsubjpass") and (rel is None or c.i != rel.i)]
        if not subj or rel is not None or subj[0].i <= t.head.i:
            continue
        if t.head.dep_ == "ROOT":
            # "The help output begins with": with the noun as the root, the
            # "relative clause" is the main clause the parser missed.
            continue
        if subj[0].pos_ == "PRON" or t.head.lemma_.lower() in LIGHT_RELATIVE_HEADS:
            # "someone I trust", "all you need", "the first time we met": a
            # pronoun subject makes an object relative easy to read (Gordon,
            # Hendrick and Johnson 2001), and these heads are fixed phrases.
            continue
        out.append(("info", f"'{_w(ctx, t.head)} {_w(ctx, subj[0])} {t.text}': object relative without 'that'",
                    [t.head, subj[0], t]))
    return out


def long_sentence(sent, ctx: Context) -> list[tuple[str, str, list]]:
    words = sum(1 for t in sent if t.is_alpha)
    if words > ctx.cfg.long_sentence_words:
        return [("info", f"{words} words in one sentence", [])]
    return []


def nominalizations(sent, ctx: Context) -> list[tuple[str, str, list]]:
    """Action nouns after a light verb, or two action nouns with 'of' in one sentence."""
    out = []
    with_of = []
    for t in sent:
        if t.pos_ != "NOUN" or t.text == CODE:
            continue
        base = lexicon.nominalization_base(t.lemma_.lower())
        if not base:
            continue
        if not any(c.dep_ == "prep" and c.lower_ == "of" for c in t.children):
            continue  # "performs validation of the input": the action and its object
        verb = t.head
        # "a fast implementation of", "implementations of": a thing, not an action.
        thing = t.tag_ == "NNS" or any(c.dep_ == "amod" or c.lower_ in ("a", "an") for c in t.children)
        if thing:
            continue
        if t.dep_ in ("dobj", "obj") and verb.pos_ == "VERB" and verb.lemma_.lower() in lexicon.LIGHT_VERBS:
            out.append(("info", f"'{verb.text} {t.text} of': the verb '{base}' would do", [verb, t]))
        else:
            with_of.append((t, base))
    if len(with_of) >= 2 and not out:
        words = ", ".join(f"'{t.text} of' ({b})" for t, b in with_of)
        out.append(("info", f"{len(with_of)} actions written as nouns: {words}", [with_of[0][0]]))
    return out


SUBORDINATORS = {"when", "while", "if", "after", "before", "without", "by", "once", "until", "whether"}


def participial_clauses(sent, ctx: Context) -> list[tuple[str, str, list]]:
    """An -ing clause set off by a comma: ", making X faster" or "Building on X, ..."."""
    out = []
    for t in sent:
        if t.tag_ != "VBG" or t.dep_ != "advcl" or t.head.pos_ not in ("VERB", "AUX"):
            continue
        if any(c.dep_ in ("mark", "aux", "auxpass", "nsubj") for c in t.children):
            continue  # "while parsing", "is running", an absolute clause with its own subject
        k = t.i - 1
        while k > sent.start and sent.doc[k].lower_ in (",", "for", "example", "instance", "e.g.", "i.e."):
            k -= 1
        if t.conjuncts or (k >= sent.start and sent.doc[k].lower_ in SUBORDINATORS):
            continue  # "trimming and splitting" as objects; "when, for example, searching"
        before = sent.doc[t.i - 1] if t.i > sent.start else None
        parallel = any(x.tag_ == "VBG" for x in sent.doc[t.head.i + 1:t.i])  # "for following X, controlling Y"
        if t.i > t.head.i and before is not None and before.text == "," and not parallel:
            out.append(("info", f"', {t.text} ...' leaves its link to '{t.head.text}' unstated", [t]))
        elif t.i == sent.start and t.head.i > t.i and \
                any(x.text == "," for x in sent.doc[t.right_edge.i + 1:t.head.i + 1]):
            out.append(("info", f"'{t.text} ...,' leaves its link to '{t.head.text}' unstated", [t]))
    return out


# Calibrated on 12 BurntSushi READMEs and this repo's docs (10k words): with
# 7 tags and sentences ending in ":" left out, no frame repeats three times.
FRAME_N = 7      # fine-grained tags in a frame; shorter runs are common in all prose
FRAME_MIN = 3    # sentences that must share it


def repeated_frames(sents) -> list[tuple[object, object, str, list]]:
    """Sentences sharing a run of FRAME_N fine-grained POS tags, FRAME_MIN or more times.

    A within-document check, not Shaib et al.'s corpus-level template rate.

    ``sents`` is a list of (segment, sentence). Returns one finding per group
    of sentences, at the group's first sentence: (segment, sentence, message, tokens).
    """
    where: dict[tuple, dict[int, int]] = {}  # frame -> sentence number -> first token index
    for k, (_, sent) in enumerate(sents):
        if sent.text.rstrip().endswith(":"):
            continue  # lead-ins to code or lists are formulaic on purpose
        toks = [t for t in sent if not t.is_punct and not t.is_space]
        for j in range(len(toks) - FRAME_N + 1):
            where.setdefault(tuple(t.tag_ for t in toks[j:j + FRAME_N]), {}).setdefault(k, j)
    groups: dict[frozenset, tuple] = {}
    for frame, hits in where.items():
        if len(hits) >= FRAME_MIN:
            groups.setdefault(frozenset(hits), frame)
    out = []
    reported: set[int] = set()
    for members, frame in sorted(groups.items(), key=lambda g: (-len(g[0]), min(g[0]))):
        if members <= reported:
            continue  # a sub-run of a frame already reported for these sentences
        reported |= members
        k = min(members)
        seg, sent = sents[k]
        toks = [t for t in sent if not t.is_punct and not t.is_space]
        j = where[frame][k]
        out.append((seg, sent, f"{len(members)} sentences share the frame '{' '.join(frame)}'",
                    toks[j:j + FRAME_N]))
    return out


RATIONALE = re.compile(r"\b(because|so that|otherwise|since)\b", re.IGNORECASE)


def suggestion(feature: str, sentence: str) -> str:
    """The feature's fix, plus a reminder to keep the reason when splitting."""
    fix = FEATURES[feature].fix
    m = RATIONALE.search(sentence) if feature in ("long-dependency", "inline-list") else None
    if not m:
        return fix
    return (f"{fix} Split the sentence and keep the reason: the '{m.group(1).lower()}' "
            "clause can be a sentence of its own.")


def detect(sent, ctx: Context) -> list[tuple[str, str, str, list]]:
    """Run enabled detectors on one sentence: (feature, severity, message, tokens)."""
    results: list[tuple[str, str, str, list]] = []
    taken: set[int] = set()
    on = ctx.enabled

    def add(feature, items):
        for sev, msg, toks in items:
            results.append((feature, sev, msg, toks))

    # Tokens of allow-listed terms are taken before any detector runs, so no
    # detector reports part of "write-ahead log" or "key-value store".
    spans = _allowed_spans(sent, ctx.allow)
    taken.update(i for span in spans for i in span)
    if "stacked-nouns" in on:
        add("stacked-nouns", stacked_nouns(sent, ctx, taken, spans))
    if "hyphen-compound" in on:
        add("hyphen-compound", hyphen_compounds(sent, ctx, taken, {i for span in spans for i in span}))
    # List detection always runs: it decides whether long-dependency applies,
    # so turning inline-list off must not change long-dependency.
    lists = inline_lists(sent, ctx)
    if "inline-list" in on:
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
    if "nominalization" in on:
        add("nominalization", nominalizations(sent, ctx))
    if "participial-clause" in on:
        add("participial-clause", participial_clauses(sent, ctx))
    return results
