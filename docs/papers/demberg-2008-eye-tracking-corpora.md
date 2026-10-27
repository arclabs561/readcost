# Data from eye-tracking corpora as evidence for theories of syntactic processing complexity

Vera Demberg, Frank Keller. 2008. Cognition 109(2), 193-210. DOI
[10.1016/j.cognition.2008.07.008](https://doi.org/10.1016/j.cognition.2008.07.008);
author copy at homepages.inf.ed.ac.uk/keller (cognition08a.pdf, 32-page
manuscript).

Read: full (author manuscript: three experiments, tables 1 to 7, general
discussion; the preprocessing appendix referenced in the text was not in
the extracted text). Title and authors match.

## Claim

On the Dundee eye-tracking corpus (newspaper text, 10 readers), DLT
integration cost does not predict reading times for words in general; it
does for nouns and (with part-of-speech controls) verbs. Unlexicalized
(part-of-speech) surprisal predicts reading times for all words and is
uncorrelated with integration cost, so both mechanisms are needed.

## Method and data

- Dundee English: 20 Independent articles, 51,502 tokens; words at line
  ends, before punctuation and in unfixated runs excluded; 200,684 first
  pass and 240,157 total-time data points.
- Integration cost from Minipar parses: nouns and verbs as referents,
  identity or log cost; checked against a hand-annotated text (83% of
  values correct, r = 0.70).
- Surprisal from Roark's parser, lexicalized and unlexicalized (trained on
  POS sequences); controls: length, frequency, forward and backward
  transitional probability, position, previous-word fixation, launch
  distance, landing position. Hierarchical mixed models, AIC selection.

## Results (numbers that matter)

- All words: integration cost coefficient negative (first pass -2.28 ms
  main effects; -5.37 log cost in the full model).
- Nouns with non-zero cost: log integration cost +5.86 ms (p < .05); the
  effect disappears when compound-initial nouns (cost 0 by DLT) are
  included, so the authors conclude the first noun of a compound should
  carry cost.
- Verbs: positive only with verb part of speech controlled; nominal
  dependents raise times at the verb unless an auxiliary came first.
- Words DLT gives zero cost (adjectives, prepositions, expletives) are read
  slower than the low-level model predicts.
- Unlexicalized surprisal +1.03 ms per bit (first pass), significant in all
  measures; lexicalized surprisal adds nothing over forward transitional
  probability. Integration cost correlates with no other predictor (|r| <=
  0.26).

## What the full text qualifies

- Automatic parses (Minipar), 10 readers; edited newspaper text has few
  costly dependencies (the point Shain et al. 2016 later make).
- The authors note DLT's predictions depend on the grammar formalism.

## For readcost (used / tested / candidate)

Not cited. Bearing on long-dependency and the referent measure:

- features.py lines 563-565 follow Gibson in not counting nouns that only
  modify another noun as referents. This paper's evidence is that treating
  the first noun of a compound as free is wrong in reading data; the cost
  should spread over the compound. For readcost that argues for counting
  compound modifiers, or counting the whole compound once, in
  `new_referents`.
- DLT's zero cost for adjectives and prepositions misses real reading
  cost; Gibson 1998's extended version (predicates count) points the same
  way.
- Unlexicalized POS surprisal predicts reading time beyond frequency,
  supporting a POS n-gram rarity feature (see the Giulianelli 2023 note).
- On natural edited text, locality effects are weak; readcost's own
  finding that referent counts did not beat word distance fits that.

## Open questions

- Does counting compound modifiers change the AUC of the referent measure
  on readcost's labelled findings?
