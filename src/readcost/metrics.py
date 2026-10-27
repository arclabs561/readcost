"""Document-level measures reported beside the findings.

None of these changes a finding or the verdict; they appear in JSON output
(``Result.metrics``) so a reader or a script can compare documents.

- ``mtld``: lexical diversity of content words, McCarthy and Jarvis's
  Measure of Textual Lexical Diversity (2010). Higher means more varied
  vocabulary. In technical prose repeated terms help the reader, so higher
  is not better; model rewrites score higher than the human originals
  (Cekini et al. 2026; SlopBench).
- ``idea_density``: propositions per word, counted from the dependency
  parse in the way of DEPID (Sirts, Piguet and Johnson 2017), the
  dependency-based successor of CPIDR (Brown et al. 2008).
- ``center_embedding_mean`` and ``center_embedding_max``: how deeply finite
  clauses nest inside a clause that continues after them (Gibson 2000;
  Karlsson 2007).
- ``sentence_words_profile``: the share of words in sentences of each length
  band, the "quality profile" of Alves, Ypma and Visser (2010).
"""

from __future__ import annotations

import statistics

from .features import center_embeddings

MTLD_THRESHOLD = 0.72      # McCarthy and Jarvis 2010
# The final, partial factor weighs more the shorter the text; 100 words was
# the usual floor, and Zenker and Kyle (2021, as reported by Shatz et al.)
# found MTLD fairly stable down to 50.
MTLD_MIN_WORDS = 50
CONTENT_POS = ("NOUN", "PROPN", "VERB", "ADJ", "ADV")

# DEPID's proposition relations (Sirts et al. 2017, table 2), in the names
# spaCy's English models use: Stanford "vmod" is "acl" and "tmod" is
# "npadvmod" here.
PROPOSITION_DEPS = frozenset({
    "advcl", "advmod", "amod", "appos", "cc", "csubj", "csubjpass", "det", "neg", "npadvmod",
    "nsubj", "nsubjpass", "nummod", "poss", "predet", "preconj", "prep", "quantmod", "acl",
})
PLAIN_DETERMINERS = frozenset({"a", "an", "the"})   # DEPID: not propositions
EMPTY_SUBJECTS = frozenset({"it", "this"})          # DEPID: not propositions

# Sentence-length bands in words, from the evaluation corpus's essays and
# docs (201 texts, 571,078 words) by the method of Alves et al. 2010: each
# document's words are weighted equally, then the 70th, 80th and 90th
# percentiles of words by the length of their sentence. Recompute with
# scripts/metric_cut_points.py when the corpus or the sentence splitter changes.
# Applied back to the corpus, the median document has 74%, 8%, 9% and 6% of
# its words in the four bands (Alves et al. expect about 70/10/10/10).
SENTENCE_WORD_CUTS = (27, 31, 38)  # a sentence of 28 to 31 words is "moderate"
BANDS = ("low", "moderate", "high", "very_high")


def _ttr_factors(words: list[str], threshold: float) -> float:
    factors, types, count = 0.0, set(), 0
    for w in words:
        count += 1
        types.add(w)
        if len(types) / count <= threshold:
            factors += 1
            types, count = set(), 0
    if count:
        # The unfinished last stretch counts as the fraction of a factor it
        # has covered: a TTR of .90 is 36% of the way from 1.00 to .72.
        factors += (1 - len(types) / count) / (1 - threshold)
    return factors


def mtld(words: list[str], threshold: float = MTLD_THRESHOLD) -> float | None:
    """Mean length of the word runs that keep the type-token ratio above ``threshold``.

    Computed forwards and backwards and averaged. None when the text never
    repeats a word, so no factor forms.
    """
    if not words:
        return None
    forward = _ttr_factors(words, threshold)
    backward = _ttr_factors(words[::-1], threshold)
    if not forward or not backward:
        return None
    return (len(words) / forward + len(words) / backward) / 2


def propositions(sent) -> int:
    n = 0
    for t in sent:
        if t.dep_ not in PROPOSITION_DEPS:
            continue
        if t.dep_ == "det" and t.lower_ in PLAIN_DETERMINERS:
            continue
        if t.dep_ in ("nsubj", "nsubjpass") and t.lower_ in EMPTY_SUBJECTS:
            continue
        n += 1
    return n


def embedding_depth(sent) -> int:
    return max((d for _, d in center_embeddings(sent)), default=0)


def _words(sent) -> list:
    return [t for t in sent if t.is_alpha]


def compute(sents) -> dict:
    """Document measures over the checked sentences (spaCy spans)."""
    sents = list(sents)
    if not sents:
        return {}
    content = [t.lower_ for s in sents for t in s if t.is_alpha and t.pos_ in CONTENT_POS]
    tokens = sum(1 for s in sents for t in s if not t.is_punct and not t.is_space)
    depths = [embedding_depth(s) for s in sents]
    lengths = [len(_words(s)) for s in sents]
    total = sum(lengths)
    profile = dict.fromkeys(BANDS, 0.0)
    if total:
        for n in lengths:
            band = sum(n > cut for cut in SENTENCE_WORD_CUTS)
            profile[BANDS[band]] += n / total
    return {
        "content_words": len(content),
        "mtld": None if len(content) < MTLD_MIN_WORDS else _round(mtld(content)),
        "idea_density": _round(sum(propositions(s) for s in sents) / tokens, 3) if tokens else None,
        "center_embedding_mean": _round(statistics.mean(depths), 3),
        "center_embedding_max": max(depths),
        "sentence_word_cuts": list(SENTENCE_WORD_CUTS),
        "sentence_words_profile": {k: round(v, 3) for k, v in profile.items()},
    }


def _round(x: float | None, k: int = 1) -> float | None:
    return None if x is None else round(x, k)
