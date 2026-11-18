"""Precompute the WordNet lookups readcost needs into src/readcost/data/lexicon.json.gz.

Loading WordNet through nltk takes about 3.5 s, which is too slow for a hook,
so the lookups are computed once here and shipped as sets of words.

    pip install nltk && python3 -c "import nltk; nltk.download('wordnet')"
    python3 scripts/build_lexicon.py
"""

import gzip
import json
from pathlib import Path

from nltk.corpus import wordnet as wn

ROOTS = {wn.synset(s) for s in ("person.n.01", "organism.n.01", "social_group.n.01", "organization.n.01")}
ANIMATE_LEXNAMES = {"verb.emotion", "verb.consumption", "verb.body", "verb.cognition"}


animate_nouns, animate_verbs, lexicalized = set(), set(), set()
for lemma in wn.all_lemma_names("n"):
    if "_" in lemma or "-" in lemma:
        parts = lemma.replace("-", "_").split("_")
        if len(parts) == 2 and all(p.isalpha() for p in parts):
            lexicalized.add(" ".join(parts).lower())
        continue
    if not lemma.isalpha():
        continue
    for s in wn.synsets(lemma, "n")[:3]:
        if (set(s.closure(lambda x: x.hypernyms())) | {s}) & ROOTS:
            animate_nouns.add(lemma)
            break
for lemma in wn.all_lemma_names("v"):
    if "_" in lemma or "-" in lemma:
        parts = lemma.replace("-", "_").split("_")
        if len(parts) == 2 and all(p.isalpha() for p in parts):
            lexicalized.add(" ".join(parts).lower())
        continue
    verbs = wn.synsets(lemma, "v")
    if verbs and verbs[0].lexname() in ANIMATE_LEXNAMES:
        animate_verbs.add(lemma)

# Nominalizations: a -tion/-ment/-ance noun with a related verb, or a
# -ness/-ity noun with a related adjective, whose spelling starts like it
# (validation/validate, completeness/complete). Stored as "noun base".
VERB_SUFFIXES = ("tion", "sion", "ment", "ance", "ence")
ADJ_SUFFIXES = ("ness", "ity")
nominalizations = set()
for lemma in wn.all_lemma_names("n"):
    if not lemma.isalpha() or not lemma.endswith(VERB_SUFFIXES + ADJ_SUFFIXES):
        continue
    want = ("v",) if lemma.endswith(VERB_SUFFIXES) else ("a", "s")
    bases = sorted({r.name() for s in wn.synsets(lemma, "n") for l in s.lemmas() if l.name() == lemma
                    for r in l.derivationally_related_forms() if r.synset().pos() in want})
    for base in bases:
        if base != lemma and base.isalpha() and lemma.startswith(base[:max(3, len(base) - 2)]):
            nominalizations.add(f"{lemma} {base}")
            break

data = {
    "source": "Princeton WordNet 3.0 via nltk; see data/WORDNET_LICENSE",
    "animate_nouns": sorted(animate_nouns),
    "animate_verbs": sorted(animate_verbs),
    "lexicalized_pairs": sorted(lexicalized),
    "nominalizations": sorted(nominalizations),
}
out = Path(__file__).resolve().parent.parent / "src/readcost/data/lexicon.json.gz"
with gzip.open(out, "wt", encoding="utf-8") as fh:
    json.dump(data, fh, separators=(",", ":"))
print({k: len(v) for k, v in data.items() if isinstance(v, list)}, out.stat().st_size, "bytes")
