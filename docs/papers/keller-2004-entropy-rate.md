# The Entropy Rate Principle as a Predictor of Processing Effort: An Evaluation against Eye-tracking Data

Frank Keller. 2004. Proceedings of EMNLP 2004, 317-324 (Barcelona). ACL
Anthology [W04-3241](https://aclanthology.org/W04-3241/). The request
called it ACL; the anthology entry gives EMNLP 2004.

Read: full (8 pages, both experiments, tables 1 to 5). Title and author
match.

## Claim

Genzel and Charniak's entropy rate effect (out-of-context per-word
entropy rises with sentence position) holds for individual sentences but
is much weaker than reported and largely confounded with sentence length.
Sentence entropy correlates with reading time, and reading time per word
does not change with sentence position in context, as the entropy rate
principle predicts.

## Method and data

- Experiment 1: WSJ, n-gram models (n = 1 to 5), correlation of per-word
  entropy and length with sentence position, binned and raw, with
  partial correlations.
- Experiment 2: n-grams trained on BNC broadsheet text (6.7M words); Embra
  eye-tracking corpus (10 articles, 2,262 words, 125 sentences, 23
  readers); total sentence reading time per word, with word length,
  frequency and subjects partialled out (Lorch and Myers method).

## Results (numbers that matter)

- Raw-data correlation of entropy with position at most r = 0.083;
  binning inflates it to 0.65. Sentence length correlates with position
  more strongly than entropy in every setting.
- Embra: reading time per word correlates with sentence entropy r = 0.155
  to 0.165 (bigram to 5-gram, p < .01); with sentence position r = -0.027,
  not significant.

## What the full text qualifies

- Small eye-tracking corpus (125 sentences); in Embra, longer sentences
  come later, unlike BNC and WSJ.
- Correlations, not a predictive model.

## For readcost (used / tested / candidate)

Not cited. Two points of contact:

- A small n-gram entropy correlates with per-word reading time beyond word
  length and frequency, at the sentence level, which supports readcost's
  plan for word-pair statistics (docs/research.md "Rare word pairs") as a
  reading-cost signal, not only a model-text signal.
- Methodological: binning by position inflated correlations eightfold.
  readcost's "mean rho within length bins" in docs/evaluation.md is a
  different operation (correlation inside each bin, then averaged), which
  avoids that inflation; worth keeping it that way.

## Open questions

None specific.
