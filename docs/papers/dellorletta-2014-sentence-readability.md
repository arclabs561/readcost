# Assessing the Readability of Sentences: Which Corpora and Features?

Felice Dell'Orletta, Martijn Wieling, Giulia Venturi, Andrea Cimino,
Simonetta Montemagni. 2014. Proceedings of the Ninth Workshop on
Innovative Use of NLP for Building Educational Applications (BEA),
163-173. ACL Anthology [W14-1820](https://aclanthology.org/W14-1820/).

Read: full (11 pages, all sections, tables 1 to 4, figure captions).
Title and authors match.

## Claim

Sentence readability (easy vs difficult, Italian, for readers with low
literacy or mild cognitive impairment) needs more features than document
readability (about 30 vs 14), mostly syntactic and local. Hand-filtering
which sentences of a complex corpus are actually difficult helps only
modestly over treating the whole corpus as difficult.

## Method and data

- Easy: Due Parole (newspaper written by simplification experts). Hard:
  La Repubblica, with 1,745 sentences hand-selected as difficult by two
  annotators (precision of agreement 0.88 on a 107-sentence trial).
- 87 features: length, word length, basic-vocabulary lexicon, TTR, POS and
  verb-mood distributions, dependency types, parse depth, subordination
  chains, arity, pre-/post-verbal subject and object, average and maximum
  dependency length (in words). Maximum entropy with grafting feature
  selection; held-out test of 870 sentences.

## Results (numbers that matter)

- Sentences: 65.6% accuracy with sentence and word length alone (gold
  training data), 79.9% with 30 features, 83.7% with all 66 selected.
  Documents: 80% with the two length features, 96.6% with 30.
- Local syntactic features (verb arity, pre-verbal subject, post-verbal
  object, embedded complement chains) matter for sentences; average
  dependency length is a middle-ranked feature for both; maximum
  dependency length ranks higher for documents (rank 6) than sentences
  (rank 18).
- Mean max dependency length: 10.98 words in difficult sentences vs 7.67
  in easy ones; parse depth 6.83 vs 5.2.

## What the full text qualifies

Italian; binary labels; the "difficult" sentences are newspaper sentences
chosen by computational linguists, not measured on readers.

## For readcost (used / tested / candidate)

Not cited. Consistent with readcost's evaluation that single rules fire
too rarely to rank sentences (docs/evaluation.md "Sentence difficulty
rated by people"): sentence difficulty here needed some 30 mostly
syntactic features, and length alone left accuracy at 65%. Maximum
dependency length is more useful aggregated over a document than per
sentence, which fits readcost reporting long-dependency as a per-sentence
flag but treating the file index as a trend measure.

## Open questions

None specific.
