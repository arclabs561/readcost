# Quantifying and Correcting Measurement Error in LLM-Generated Classifications: A Beta-Binomial Latent Class Model for Correlated Repeated Judgments

Yichi Zhang and Ignacio Martinez (Google). arXiv 2510.23874 (v1 2025;
read v5, 30 Sep 2026). https://arxiv.org/abs/2510.23874 (data and code:
https://github.com/google-research/ljer)

Read: sections 1 to 6 in full, with all main-text tables; Appendix C.2
(semi-supervised model against PPI) in full; the proofs (Appendix A) and
the remaining appendix detail (B, C.1) not read. Title and authors match
the arXiv id.

## Claim

Asking one LLM the same classification question several times and
aggregating assumes the answers are independent given the true label. They
are not: answers to the same item are strongly correlated, so ten answers
carry the information of one to two. A latent class model that assumes
independence (binomial likelihood, in the Dawid and Skene tradition) gives
intervals that are far too narrow and error rates that are too low. A
beta-binomial version with one correlation parameter fixes most of this.

## Method and data

250 items from VerifyBench and VerifyBench-Hard (does a candidate answer
match the reference answer; human labels by two annotators plus an
adjudicator). Seven open-weight judges from 1B to 32B parameters, three
prompt conditions, ten samples per item at temperature 0.7: 52,500
judgments. Error rates are false acceptance and false rejection; the
"acceptance gap" J (sensitivity + specificity - 1, Youden's J) must be
positive for the unsupervised model to be identified. Bayesian fits in
Stan; a semi-supervised version uses a labeled subset; simulations with
known parameters compare binomial and beta-binomial likelihoods, majority
vote and a single sample, and (Appendix C.2) PPI.

## Results (numbers that matter)

- Intraclass correlation of repeated answers: 0.50 to 0.93 on the balanced
  split; ten answers are worth 1.07 to 1.81 independent ones; the median
  standard error from treating them as independent is about 2.7 times too
  small. More samples barely help: the effective number is capped at
  1/rho (1.04 to 3.13 across settings).
- Binomial model: 95% intervals for the false acceptance rate covered the
  human-label value in 0 of 42 settings; it underestimated the total error
  rate in 42 of 42 (median shortfall 0.31). Beta-binomial: coverage 0.905
  for prevalence and false acceptance on the balanced split.
- Recovery tracks J (Spearman 0.96 with AUC). Below J of about 0.2 the
  posterior barely separates classes (mean AUC 0.48); J <= 0 reverses the
  ranking.
- Labeling 10% of items cut prevalence error four- to sevenfold but did
  not improve classification of individual items.
- Simulation (Table 8): at correlation 0.9, majority vote over ten samples
  has the same prevalence bias and nearly the same accuracy as one sample;
  its Wald interval covered the truth in about 20% of replicates.
- Appendix C.2: with 50 labels out of 500 items, PPI and the
  semi-supervised model were both unbiased with 94 to 95% coverage; when J
  was 0.2, the labeled items alone did nearly as well.

## What the full text qualifies

One benchmark family, one task type, open-weight models only, one
sampling setting; the authors say the correlation values are descriptive
of this setting. The labeled-subset experiment drew labels stratified on
the true state, which the authors note overstates the value of small
labeled sets. Human labels are treated as truth although some were hard
to adjudicate. The paper studies repeated samples of one model, not
different models.

## For readcost (candidate; not cited)

readcost aggregates ten different model families, one label each, by
majority (docs/evaluation.md, "Ten raters"), not repeated samples of one
model. The paper's mechanism still applies by analogy: majority vote gains
over a single rater only to the extent that raters' errors are
independent, and model raters trained on overlapping data are likely to
share errors (for example, all reading a well-known term of art the same
way). Fleiss' kappa of 0.40 over eight raters says nothing about whether
their errors are correlated given the true label, which is what limits
the majority's accuracy. Two concrete uses:

- Report the majority's accuracy against a human-labelled random subset
  as sensitivity and specificity, and so the acceptance gap J. If J is
  small, the model majority cannot say which individual findings are real,
  even though it can still help estimate the overall share with labels
  (PPI) or a latent class model.
- The docs use the majority to decide individual rule changes, for example
  reverting the short-items rule because the majority accepted 10 of 32
  inline-list findings (docs/evaluation.md lines 492 to 497). This paper's
  results say item-level decisions are where model labels are least
  trustworthy, and labels do not fix that. That change rests on a
  per-item judgment no human has checked.

No doc claim is contradicted outright; the docs already call no rater
ground truth.

## Open questions

- Are readcost's model raters' errors correlated given a human label? A
  random subset labelled by a person, plus the raters' labels, would
  measure it (the design-effect calculation in Section 4.2 needs only the
  labels grouped by true state).
