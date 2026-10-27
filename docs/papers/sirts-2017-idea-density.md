# Idea density for predicting Alzheimer's disease from transcribed speech

Kairit Sirts, Olivier Piguet, Mark Johnson. 2017. CoNLL 2017; arXiv
[1706.04473](https://arxiv.org/abs/1706.04473) (v1).

Read: full (11 pages: body, tables 1 to 8, discussion, conclusion).
Title and authors match.

## Claim

Propositional idea density (propositions per word) can be computed from a
dependency parse by counting arcs of certain relations (DEPID); this
matches manual counts better than the part-of-speech tool CPIDR. A variant
that skips repeated propositions (DEPID-R) separates Alzheimer's patients
from controls on free autobiographical speech.

## Method and data

- DEPID: sum of arcs whose relation is in table 2 (advcl, advmod, amod,
  appos, cc, csubj, csubjpass, det except a/an/the, neg, npadvmod, nsubj
  except "it" and "this", nsubjpass, nummod, poss, predet, preconj, prep,
  quantmod, tmod, vmod), divided by tokens. Stanford dependencies.
- DEPID-R counts each lexicalized (relation, dependent lemma, head lemma)
  once per narrative.
- Validation: 276 example sentences from Turner and Greene (1977) and
  Chand et al. (2010) with manual counts.
- Data: DementiaBank Cookie Theft descriptions (169 AD, 98 control
  subjects) and AMI autobiographical interviews (20 and 20). Logistic and
  elastic-net classifiers, 10-fold CV by subject, 100 repeats.

## Results (numbers that matter)

- Spearman with manual counts: DEPID 0.839, CPIDR 0.795 (DEPID vs CPIDR
  0.864).
- On 20 hand-annotated interviews both tools overestimate density, CPIDR
  more (it does not split contractions and counts progressive auxiliaries).
- DementiaBank: CPIDR and DEPID give patients higher density than
  controls, the opposite of the literature, until conjunctions, I/you
  subject sentences and vague sentences are removed (DEPID-R-ADD).
- AMI: DEPID-R separates groups (0.334 vs 0.366); classification F-score
  77.6 (PID) vs 72.3 (semantic idea density).
- Densities: DEPID 0.36 to 0.47 on these speech corpora.

## What the full text qualifies

- Purpose is clinical screening of speech, not readability. The paper
  makes no claim that higher or lower density makes text harder to read.
- Manual and automatic counts disagree in level even where they correlate;
  the absolute value depends on tokenization and parser.
- The rule set was designed for Stanford dependencies; spaCy's labels
  differ.

## For readcost (used / tested / candidate)

Used: `idea_density` in the JSON metrics (src/readcost/metrics.py lines
11-13, 34-42; README.md line 412; docs/research.md lines 45-46).

Citation accuracy: metrics.py's relation list matches table 2, with
spaCy's `acl` for `vmod` and `npadvmod` for `tmod`; it keeps `cc`, the
determiner and subject exceptions. Accurate. "Propositions per word,
counted from the parse": accurate. readcost uses plain DEPID, not
DEPID-R; that is a choice, not an error. spaCy `acl` also covers
infinitival and participial modifiers beyond Stanford `vmod`, a small
difference.

Nothing in the paper supports using idea density as a reading-cost
signal, and readcost does not: the metric changes no finding. That is the
right reading.

## Open questions

- None for readcost beyond whether to report DEPID-R for long documents,
  where repeated propositions inflate the count.
