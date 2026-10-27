# Complexity Metrics in an Incremental Right-corner Parser

Stephen Wu, Asaf Bachrach, Carlos Cardenas, William Schuler. 2010. ACL
2010, 1189-1198. ACL Anthology [P10-1121](https://aclanthology.org/P10-1121).

Read: full (10 pages: model, evaluation, results, discussion). Title and
authors match.

## Claim

A right-corner hierarchical HMM parser with a bounded store (4 levels)
yields surprisal and entropy reduction that predict self-paced reading
times, and a new metric, embedding difference (the change in the parser's
probability-weighted average store depth from one word to the next),
predicts reading time independently of surprisal.

## Method and data

- Parser trained on WSJ sections 02-21; beam over hypotheses; store depth
  counts center-embedded constituents of any category in right-corner form,
  not just clauses.
- Reading times: 23 native speakers, self-paced word by word, four
  narratives written to be syntactically complex but natural (Bachrach et
  al. 2009); RTs outside 150-1500 ms and line-initial and line-final words
  dropped: 2,926 of 3,540 words.
- Linear mixed-effects model with random intercepts for subject, word and
  sentence; predictors word order, reciprocal length, unigram frequency,
  bigram probability, embedding difference, entropy reduction, surprisal.
  Significance by |t| > 2 and likelihood-ratio tests.

## Results (numbers that matter)

- Surprisal: t = 11.4 (all words), 6.3 (open class), 9.3 (closed class).
- Embedding difference: t = 2.87 (all), 0.54 (open class, LR test p =
  0.60), 3.08 (closed class).
- Entropy reduction: t = 4.05 (all), 0.06 (open), 4.86 (closed).
- Embedding difference correlates with surprisal (r = 0.36 in table 3),
  yet keeps an independent effect on all words and closed-class words.

## What the full text qualifies

- The depth measure is the parser's expected store depth, a probabilistic
  quantity over hypotheses, not a count of nested finite clauses.
- The effect is absent for open-class words.
- One small corpus of constructed, deliberately complex narratives; random
  intercepts only.

## For readcost (used / tested / candidate)

Used: cited in docs/research.md lines 38-39 as support for
center-embedding: "Wu et al. (2010) find that embedding depth adds to
reading time beyond surprisal."

Citation accuracy: partly accurate. The paper finds that a change in a
parser's probabilistic embedding depth adds to reading time beyond
surprisal, on all words and on closed-class words, not on open-class
words, in one constructed corpus. readcost's center-embedding rule counts
finite clauses nested two deep, which is a different quantity; this paper
does not show that clause nesting depth two costs reading time. The
citation should say "a parser's embedding-depth change" and note the
open-class null.

## Open questions

- A per-word depth change computed from readcost's parse would be closer
  to Wu's measure than a sentence-level depth threshold, and could be
  tested on OneStop or Provo as a reading-time feature.
