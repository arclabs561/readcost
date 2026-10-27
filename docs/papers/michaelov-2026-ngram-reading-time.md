# N-gram-like Language Models Predict Naturalistic Reading Time Best

James A. Michaelov, Roger P. Levy. 2026. arXiv
[2603.09872](https://arxiv.org/abs/2603.09872) (v2, 18 August 2026);
CogSci 2026 per the acknowledgments.

Read: full (body, table 1, figure captions; no appendix). Title and
authors match. Figures are plots; numbers come from the text and table 1.

## Claim

Reading time on natural text tracks low-order n-gram statistics. Language
models whose surprisal correlates most with unigram, bigram and trigram
surprisal also correlate most with reading time, which would explain why
bigger and better-trained models fit reading times worse.

## Method and data

- N-gram surprisal (n = 1 to 5) from infini-gram counts with Stupid
  Backoff over six corpora (OpenWebText 10B to OLMo-Mix 4.6T tokens).
- Provo (word means over readers; first-pass skips and sentence-initial
  and sentence-final words excluded: 2,449 words) and GECO (43,251 words);
  first fixation, first pass, go-past, total duration.
- Pythia (14M to 12B, with training checkpoints), Open GPT-2 small and
  medium (4 seeds), Gemstone (22 models). Pearson correlations, and
  correlations between those correlations.

## Results (numbers that matter)

- Provo: unigram and bigram surprisal correlate most with reading time;
  each order above 2 correlates less, and less again from larger corpora.
  For first fixation, bigram is clearly best.
- Across models and checkpoints, the correlation of a model's surprisal
  with reading time tracks its correlation with bigram or trigram
  surprisal: r between the two correlations 0.92 to 0.99 for bigram and
  trigram in most cells of table 1.
- In Provo, 82.5% of words are fixated once in the first pass and 82.5%
  are not refixated later.

## What the full text qualifies

- Correlational, simple Pearson correlations without other predictors
  (no length or frequency controls in the main analyses).
- Sentence-boundary words and skipped words excluded, unlike readcost's
  target, which counts skips as 0 ms.

## For readcost (used / tested / candidate)

Not cited. Two connections:

- Reading-time model: readcost uses unigram frequency of the word and its
  neighbours and found LM surprisal unhelpful. This paper says bigram
  surprisal does about as well as unigram and better for early measures,
  and that larger models fit worse. A bigram probability feature (word
  given previous word) from readcost's FineWeb-Edu counts is the cheapest
  next feature to test, needs no torch, and matches the project's plan for
  attested word-pair sets (docs/research.md "Rare word pairs").
- It also explains why a strong LM's surprisal can hurt: small or n-gram
  statistics are closer to readers.

## Open questions

- Does a smoothed bigram feature improve readcost's OneStop and Provo
  error, where SmolLM2 surprisal did not?
