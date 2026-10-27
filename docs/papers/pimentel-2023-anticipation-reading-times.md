# On the Effect of Anticipation on Reading Times

Tiago Pimentel, Clara Meister, Ethan G. Wilcox, Roger P. Levy, Ryan
Cotterell. 2023. TACL; arXiv [2211.14301](https://arxiv.org/abs/2211.14301)
(v2, 14 July 2023).

Read: full (body, limitations, appendices A to C). Title and authors
match.

## Claim

Reading is partly anticipatory: a word's contextual entropy (the expected
surprisal before the word is seen) predicts its reading time, sometimes
better than its surprisal. A Rényi entropy with alpha = 1/2 (roughly, how
many continuations are plausible) works best. Much of the effect in eye
tracking comes through word skipping.

## Method and data

- Brown and Natural Stories (self-paced), Provo and Dundee (eye tracking,
  progressive gaze duration; skipped words as 0 ms in the main runs,
  removed in later runs). Times averaged over readers per word.
- GPT-2 small surprisal; entropy over the first subword (a lower bound on
  word entropy). Baseline: length and unigram frequency for the word and
  three previous words, plus surprisal terms. Linear regression, 10-fold
  CV, Delta log-likelihood, paired permutation tests.

## Results (numbers that matter)

- Adding Shannon entropy improves fit in three of four datasets (not
  Provo); replacing surprisal by entropy is as good except in Provo.
  Rényi alpha = 1/2 replacing surprisal improves fit in Natural Stories
  (+1.30, in units of 0.01 nats) and Dundee (+0.32), and is worse in Provo (-3.25).
- Spillover is carried by previous words' surprisal, not their entropy.
- Skipping: in Dundee, entropy predicts whether a word is skipped better
  than surprisal, and surprisal adds nothing once entropy is in. With
  skipped words removed, entropy is no better than surprisal.
- Successor entropy matters only in Natural Stories.

## What the full text qualifies

- Provo behaves differently from the other three corpora throughout; the
  authors cannot explain it.
- Entropy from a small LM over subwords; noise in surprisal estimates
  could favour entropy, which the authors argue is not the main cause.

## For readcost (used / tested / candidate)

Not cited. Relevant to the reading-time model and to docs/evaluation.md
"Model signals":

- readcost's target counts skipped words as 0 ms. This paper shows that
  under that target, skipping is predicted by anticipation (entropy) more
  than by surprisal. readcost's lexical features capture part of
  skipping through length and frequency (short, frequent words are
  skipped); an explicit skip-probability feature or entropy would be the
  principled addition. Provo, readcost's external test, is the corpus
  where entropy helped least.
- In "Model signals", entropy fell in human simplifications and was
  negatively related to CEFR-SP difficulty; this paper gives a reading of
  that: lower entropy means more predictable continuations, more skipping
  and shorter times, consistent with simpler text.

## Open questions

- Is a per-word skip-rate model (logistic, from length and frequency)
  plus a fixation-duration model better than one regression on times that
  mix zeros and fixations? The paper's split between skipped-included and
  skipped-removed results suggests the two parts behave differently.
