# Frequency Explains the Inverse Correlation of Large Language Models' Size, Training Data Amount, and Surprisal's Fit to Reading Times

Byung-Doh Oh, Shisen Yue, William Schuler. 2024. EACL 2024; arXiv
[2402.02255](https://arxiv.org/abs/2402.02255) (v1).

Read: full body, limitations and ethics (20-page PDF). Appendices A to C
are model hyperparameter tables and per-variant versions of figures 4 and
5; their captions were read, the plots were not. Title and authors match.

## Claim

Larger and longer-trained language models fit reading times worse mainly
because they predict rare words too well: the loss of fit is concentrated
in the least frequent fifth of words, where they assign much lower
surprisal than smaller models and the regression underpredicts reading
time.

## Method and data

- Natural Stories, Dundee, GECO and Provo (exploratory halves; edge,
  unfixated and long-saccade words excluded); log reading times
  (self-paced, go-past).
- GPT-2, GPT-Neo, OPT and Pythia families. Baseline predictors: length,
  position, unigram surprisal from 33B Pile tokens, plus saccade length
  and previous-word fixation for eye tracking; no spillover terms.
- MSE by unigram-frequency quintile; Pythia checkpoints from step 0 to
  143,000; context truncation to 49, 24 or 9 tokens as attribution.

## Results (numbers that matter)

- On all four corpora the slope of MSE against log perplexity is
  steepest in the rarest quintile (permutation test p < .05), and MSE is
  highest there.
- Training: surprisal for rare words keeps falling after step 1,000 (about
  2B tokens); fit to reading times peaks then degrades, faster for larger
  models.
- Larger models predict rare words better even with only 9 tokens of
  context, so both longer effective context and stronger local
  associations contribute.

## What the full text qualifies

- Linear effects assumed; no spillover predictors; English only.
- The authors leave open whether this means a separate frequency effect
  in reading or frequency effects washed out of LM surprisal.

## For readcost (used / tested / candidate)

Not cited. Supports readcost's shipped design: a model built on word
frequency (FineWeb-Edu counts) and length captures most of what LM
surprisal adds for naturalistic reading, and large LMs would make it
worse on exactly the rare words that technical prose is full of
(identifiers, product names). It also suggests why readcost's rewrite
results diverge between per-word time (frequency-driven) and LM surprisal.

## Open questions

None specific.
