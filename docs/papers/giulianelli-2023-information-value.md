# Information Value: Measuring Utterance Predictability as Distance from Plausible Alternatives

Mario Giulianelli, Sarenne Wallbridge, Raquel Fernández. 2023. EMNLP 2023;
arXiv [2310.13676](https://arxiv.org/abs/2310.13676) (v1).

Read: full body, limitations and ethics; appendices E, F (tables 5 and 6)
and G read; appendices A to D (fine-tuning, surprisal aggregates,
robustness plots) partly lost in text extraction and read only through
their figure captions. Title and authors match.

## Claim

Information value, the distance between an utterance and a set of
alternatives sampled from a language model in the same context, predicts
acceptability in dialogue better than aggregated surprisal and adds to
surprisal for predicting sentence reading times. Lexical and syntactic
(POS n-gram) distances drive reading times; semantic distance drives
dialogue acceptability.

## Method and data

- Alternatives: 10 to 100 samples per context from GPT-2, GPT-Neo, OPT
  (DialoGPT for dialogue), 11 sampling strategies; 1.3M generations
  released.
- Distances: lexical (distinct n-gram fraction), syntactic (distinct POS
  n-gram fraction), semantic (sentence-embedding cosine or Euclidean);
  summarized by mean or min.
- Data: Switchboard and DailyDialog in-context acceptability, CLASP
  (Wikipedia round-trip translations); Provo (136 sentences, total dwell
  time summed per sentence) and Brown self-paced reading.
- Spearman correlations with length-normalized reading time; mixed models
  of total sentence time with number of fixated words as control.

## Results (numbers that matter)

- Provo: syntactic information value rho 0.421 with length-normalized
  reading time, against 0.495 for the best surprisal aggregate (variance).
  Brown: lexical 0.223 vs surprisal mean 0.220.
- Provo mixed models (Delta LogLik): surprisal alone 59.0 (superlinear,
  k = 0.5); syntactic information value 34.4; joint 93.1, a 58% gain from
  adding information value, mostly from the syntactic level.
- Out-of-context information value predicts reading times at least as
  well as in context: unusual POS sequences slow reading regardless of
  context. For Provo, surprisal computed in an incongruent context
  predicted better than in the true context.

## What the full text qualifies

- Small reading-time samples (136 Provo sentences); correlations are at
  the sentence level.
- Costly: many full samples per context.

## For readcost (used / tested / candidate)

Not cited. Candidate for readcost's reading-time model and rules:

- The syntactic result says that how far a sentence's POS n-grams are
  from typical ones predicts reading time beyond surprisal, and that
  context matters little. readcost already tags POS for `corpus` and
  repeated-frame. A context-free version (rarity of a sentence's POS
  trigrams against a reference corpus, the POS analogue of the planned
  rare-word-pair sets) is cheap and needs no language model. It would be
  the syntactic counterpart to Clark et al.'s unattested word pairs.

## Open questions

- Does POS-trigram rarity against a reference profile add to readcost's
  lexical model at the sentence level on Provo or OneStop?
