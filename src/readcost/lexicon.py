"""Word lists and precomputed WordNet lookups used by the detectors.

The WordNet-derived sets live in data/lexicon.json.gz (built by
scripts/build_lexicon.py; WordNet's license is in data/WORDNET_LICENSE), so
nothing loads WordNet at run time. If the file is missing, denominal-verb is
disabled and inanimate-subject uses only the explicit lists.
"""

from __future__ import annotations

import gzip
import json
from functools import lru_cache
from importlib import resources

_LEX: dict | None = None


def _lex() -> dict:
    global _LEX
    if _LEX is None:
        try:
            raw = resources.files("readcost").joinpath("data/lexicon.json.gz").read_bytes()
            data = json.loads(gzip.decompress(raw))
            _LEX = {k: set(v) for k, v in data.items() if isinstance(v, list)}
        except (OSError, ValueError, EOFError):  # EOFError: a truncated gzip
            _LEX = {}
    return _LEX


def has_wordnet() -> bool:
    """True when the precomputed WordNet sets are available."""
    return bool(_lex())


INANIMATE_PRONOUNS = {"it", "this", "that", "which", "these", "those"}

# Verbs whose subject is normally a person or animal (selectional restriction).
ANIMATE_VERBS = {
    "admit", "agree", "argue", "beg", "believe", "bite", "bleed", "bless",
    "care", "chase", "cheat", "chew", "choose_to", "claim", "complain", "cry",
    "decide", "die", "digest", "dislike", "doubt", "eat", "enjoy", "examine",
    "explore", "fear", "fight", "forbid", "forget", "forgive", "guess", "hate",
    "hide", "hope", "hunt", "hurt", "insist", "kill", "know", "lie_to",
    "love", "notice", "own", "pretend", "promise", "punish", "punt", "refuse",
    "remember", "review", "rot", "scream", "shrug", "sleep", "smell", "starve",
    "steal", "suffer", "swallow", "think", "tolerate", "trust", "understand",
    "wake", "want", "wish", "worry", "yell",
}

# Routine metonymy in technical prose ("the index uses", "the test feeds",
# "the model learns"). Never flagged.
TECHNICAL_VERBS = {
    "accept", "analyze", "apply", "approximate", "assume", "calculate",
    "check", "choose", "classify", "compare", "compute", "consider", "consume",
    "define", "derive", "detect", "determine", "distinguish", "drink", "emit",
    "estimate", "evaluate", "exercise", "exhaust", "expect", "feed", "find",
    "flush", "focus", "identify", "infer", "learn", "lie", "match", "mean",
    "measure", "model", "need", "override", "predict", "prove", "rank", "read",
    "recognize", "reject", "relate", "require", "respect", "score", "see",
    "select", "skip", "solve", "spend", "test", "track", "train", "upgrade",
    "use", "validate", "verify", "view", "waste",
}

# Verbs WordNet lists mostly as nouns that are ordinary verbs in software prose.
CONVENTIONAL_VERBS = {
    "access", "account", "panic", "author", "back", "base", "batch", "benchmark",
    "bit", "bound", "build", "byte", "cache", "call", "change", "check",
    "chunk", "cluster", "compile", "condition", "contact", "copy", "cost",
    "count", "default", "design", "disk", "document", "end", "export",
    "feature", "file", "filter", "fix", "flag", "focus", "format", "gate",
    "grade", "group", "handle", "hash", "head", "help", "import", "index",
    "input", "install", "kernel", "key", "label", "limit", "link", "list",
    "load", "lock", "log", "map", "mark", "match", "measure", "model", "name",
    "need", "order", "output", "package", "page", "pair", "parse", "patch",
    "pin", "pipe", "plan", "point", "pool", "power", "process", "query",
    "range", "rank", "re", "record", "release", "report", "result", "return",
    "run", "sample", "scope", "score", "search", "seed", "segment", "set",
    "share", "ship", "shell", "side", "sort", "source", "split", "start",
    "step", "store", "stream", "structure", "sum", "support", "tag", "target",
    "test", "time", "token", "touch", "trace", "track", "type", "update",
    "upgrade", "use", "value", "view", "weight", "work", "wrap", "zero",
}

# Common hyphenated or multi-word technical terms that are not ad hoc stacks.
DEFAULT_ALLOW = {
    "write-ahead log", "command-line interface", "command line interface",
    "open-source", "pull request", "end-to-end", "copy-on-write",
    "least-recently-used", "time-to-live", "key-value store", "key value store",
    "real-time", "built-in", "read-only", "read-write", "first-class",
    "out-of-the-box", "state-of-the-art", "zero-copy", "lock-free",
    "thread-safe", "type-safe", "memory-safe", "cross-platform",
    "high-level", "low-level", "user space", "kernel space", "test suite",
    "unit test", "integration test", "error message", "use case",
    "rate limit", "hash map", "hash table", "search engine", "file system",
    "machine learning", "nearest neighbor", "nearest-neighbor",
    "dependency graph", "language model", "data set", "code base",
    # Tool and package names spelled with hyphens.
    "tree-sitter", "markdown-it", "pre-commit",
}

# Hyphen prefixes that make ordinary words, not noun-noun coinages.
HYPHEN_PREFIXES = {
    "anti", "auto", "bi", "co", "counter", "cross", "de", "dual", "ex",
    "extra", "half", "hyper", "inter", "intra", "macro", "meta", "micro",
    "mid", "mini", "multi", "non", "off", "on", "out", "over", "post", "pre",
    "pro", "pseudo", "quasi", "re", "self", "semi", "single", "sub", "super",
    "trans", "tri", "ultra", "un", "under", "well", "zero", "one", "two",
    "three", "four", "n", "k", "x", "e", "top", "low", "high", "full",
}


# Second halves of hyphenated words that form ordinary adjectives.
HYPHEN_SECONDS = {
    "based", "style", "level", "scale", "time", "side", "wide", "specific",
    "oriented", "driven", "aware", "free", "safe", "friendly", "like", "sized",
    "shaped", "bound", "first", "only", "heavy", "light", "intensive", "ready",
    "grade", "class", "order", "way", "case", "sensitive", "insensitive",
}


ANIMATE_NOUNS_EXTRA = {
    "user", "caller", "maintainer", "developer", "contributor", "reader",
    "reviewer", "team", "people", "operator", "author", "writer", "owner",
}


@lru_cache(maxsize=4096)
def is_lexicalized(a: str, b: str) -> bool:
    """True if WordNet knows "a-b" or "a b" as one word."""
    return f"{a} {b}" in _lex().get("lexicalized_pairs", ())


def is_denominal_candidate(lemma: str) -> bool:
    if lemma in CONVENTIONAL_VERBS or not lemma.isalpha() or len(lemma) < 3:
        return False
    return lemma in _lex().get("denominal_candidates", ())


@lru_cache(maxsize=4096)
def noun_animacy(lemma: str) -> bool | None:
    """True for people, organisms and groups; False otherwise; None without data."""
    if lemma in ANIMATE_NOUNS_EXTRA:
        return True
    nouns = _lex().get("animate_nouns")
    if nouns is None:
        return None  # no data: neither person nor thing
    return lemma in nouns


# Verbs that take a thing as subject in ordinary prose: linking verbs ("if a
# line feels too long") and terms of art ("the program panics", "the process
# dies"). Found as false positives in docs/evaluation.md.
THING_SUBJECT_VERBS = {
    "feel", "seem", "look", "sound", "appear",
    "panic", "die", "respond", "behave", "rely", "suffer", "link", "catch",
    "resolve", "remind", "surprise", "overwhelm", "perturb", "react", "crash",
}


@lru_cache(maxsize=4096)
def is_animate_verb(lemma: str) -> bool:
    if lemma in TECHNICAL_VERBS or lemma in THING_SUBJECT_VERBS:
        return False
    if lemma in ANIMATE_VERBS:
        return True
    return lemma in _lex().get("animate_verbs", ())


# Verbs that carry little meaning of their own and take an action noun as
# object: "performs validation" for "validates".
LIGHT_VERBS = {
    "perform", "make", "do", "carry", "conduct", "provide", "give", "undergo",
    "achieve", "effect", "facilitate", "enable", "allow", "undertake",
}

# Nouns WordNet relates to a verb or adjective that are not used as actions.
NOT_NOMINALIZATIONS = {
    "community", "position", "station", "statement", "government", "argument",
    "environment", "document", "element", "department", "sentence", "instance",
    "experience", "audience", "evidence", "reference", "difference", "license",
    "requirement", "dependency", "entity", "identity", "quality", "quantity",
    "property", "city", "university", "authority", "majority", "minority",
    "priority", "facility", "utility", "capacity", "function", "question",
    "section", "option", "condition", "version", "session", "permission",
    "business", "witness",
}


@lru_cache(maxsize=1)
def _nominalizations() -> dict[str, str]:
    return dict(p.split(" ", 1) for p in _lex().get("nominalizations", ()))


def nominalization_base(lemma: str) -> str | None:
    """The verb or adjective behind an action noun: validation -> validate."""
    if lemma in NOT_NOMINALIZATIONS:
        return None
    return _nominalizations().get(lemma)
