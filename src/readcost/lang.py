"""Tell English apart from other languages, so readcost does not judge text it cannot read.

readcost's rules, parser and reading-time model are English only. For other
languages they still produce findings and a reading time, both meaningless.
``other_language`` names the language of a text that is clearly not English,
from two signals that need no model: the share of letters in Latin script,
and which language's function words (spaCy's stop-word lists) the words
match best. Short texts are assumed to be English.
"""

from __future__ import annotations

import importlib
import re
from functools import lru_cache

# Languages with stop-word lists in spaCy that need no model download.
CANDIDATES = ("de", "es", "fr", "nl", "it", "pt", "sv", "da", "nb", "pl", "tr", "id")
MIN_WORDS = 20


@lru_cache(maxsize=None)
def _stop_words(lang: str) -> frozenset[str]:
    return frozenset(importlib.import_module(f"spacy.lang.{lang}.stop_words").STOP_WORDS)


def other_language(text: str) -> str | None:
    """A language code when ``text`` is clearly not English, else None."""
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 40 and sum(c.isascii() or "À" <= c <= "ɏ" for c in letters) / len(letters) < 0.5:
        return "a non-Latin script"
    words = re.findall(r"[^\W\d_]+", text.lower())
    if len(words) < MIN_WORDS:
        return None

    def share(lang: str) -> float:
        stop = _stop_words(lang)
        return sum(w in stop for w in words) / len(words)

    english = share("en")
    best = max(CANDIDATES, key=share)
    # English prose is about 40% function words; a terse commit subject still
    # has some. Another language must clearly lead before English is ruled out.
    return best if share(best) >= 0.25 and share(best) > 2 * english else None
