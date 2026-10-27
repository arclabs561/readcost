"""Repetition across many texts: syntactic templates and repeated openers.

A within-document check cannot see that a model, a bot or one author writes
every commit message or answer in the same mould. Following Shaib et al.
(2024), a template is one of the corpus's most frequent part-of-speech
6-grams; the measures are the share of texts that contain one, templates per
token, and CR-POS, the gzip compression ratio of all part-of-speech tags in a
row (higher is more repetitive). Formulaic genres score high legitimately,
and CR-POS grows with the amount of text, so compare corpora of similar size
and genre.
"""

from __future__ import annotations

import gzip
import re
from collections import Counter
from dataclasses import dataclass, field

N = 6          # tags in a template, as in Shaib et al.'s main results
TOP = 100      # templates are the corpus's TOP most frequent n-grams


@dataclass
class CorpusReport:
    texts: int
    words: int
    cr_pos: float
    template_rate: float           # share of texts with at least one template
    templates_per_token: float
    top_templates: list[dict] = field(default_factory=list)   # tags, count, texts, example
    top_openers: list[dict] = field(default_factory=list)     # opener, count, share of sentences


def _tags_and_sentences(analyzer, texts: list[tuple[str, str]]):
    from .extract import detect_format, extract

    for name, text in texts:
        tags, sents = [], []
        for seg in extract(text, name, detect_format(name, text) if name != "-" else "markdown"):
            for sent in analyzer.nlp(seg.text).sents:
                toks = [t for t in sent if not t.is_space]
                if len(toks) < 3:
                    continue
                tags.extend(t.tag_ for t in toks)
                sents.append(toks)
        yield name, tags, sents


def analyze(analyzer, texts: list[tuple[str, str]], top: int = 5) -> CorpusReport:
    """``texts``: (name, text) pairs, one per document (a commit message, an answer, a file)."""
    docs = list(_tags_and_sentences(analyzer, texts))
    grams: Counter = Counter()
    per_doc: list[Counter] = []
    examples: dict[tuple, str] = {}
    openers: Counter = Counter()
    n_sents = 0
    for _, tags, sents in docs:
        c = Counter(tuple(tags[i:i + N]) for i in range(len(tags) - N + 1))
        grams.update(c)
        per_doc.append(c)
        for toks in sents:
            n_sents += 1
            words = [t.lower_ for t in toks if t.is_alpha][:2]
            if len(words) == 2:
                openers[" ".join(words)] += 1
            for i in range(len(toks) - N + 1):
                examples.setdefault(tuple(t.tag_ for t in toks[i:i + N]), " ".join(t.text for t in toks[i:i + N]))
    templates = {g for g, _ in grams.most_common(TOP)}
    all_tags = " ".join(t for _, tags, _ in docs for t in tags).encode()
    tokens = sum(len(tags) for _, tags, _ in docs)
    words = sum(1 for _, _, sents in docs for toks in sents for t in toks if t.is_alpha)
    with_template = sum(1 for c in per_doc if templates & set(c))
    in_template = sum(n for c in per_doc for g, n in c.items() if g in templates)
    top_t = [{"tags": " ".join(g), "count": n, "texts": sum(1 for c in per_doc if g in c),
              "example": examples.get(g, "")} for g, n in grams.most_common(top)]
    top_o = [{"opener": o, "count": n, "share": n / n_sents} for o, n in openers.most_common(top) if n > 1]
    return CorpusReport(
        texts=len(docs), words=words,
        cr_pos=len(all_tags) / len(gzip.compress(all_tags)) if all_tags else 0.0,
        template_rate=with_template / len(docs) if docs else 0.0,
        templates_per_token=in_template / tokens if tokens else 0.0,
        top_templates=top_t, top_openers=top_o)


def split_records(text: str) -> list[str]:
    """Split one file of many short texts, separated by lines of three or more dashes or equals signs."""
    return [p.strip() for p in re.split(r"(?m)^\s*(?:-{3,}|={3,})\s*$", text) if p.strip()]
