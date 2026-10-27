# PPI++: Efficient Prediction-Powered Inference

Anastasios N. Angelopoulos, John C. Duchi and Tijana Zrnic. 2023 (v2 26
Mar 2024). arXiv 2311.01453. https://arxiv.org/abs/2311.01453

Read: full (arXiv v2 PDF, 29 pages: main text, proofs in Appendix A,
one-step experiments in B, odds-ratio intervals in C). Title and authors
match the arXiv id.

## Claim

Prediction-powered inference (PPI) has two problems: for many estimands
its confidence sets need a grid search that is intractable beyond two or
three dimensions, and with poor predictions its intervals can be wider
than intervals from the labeled data alone. PPI++ fixes both: it puts
error bars around a point estimate computed by convex optimization, and it
weights the predictions by a tuning parameter chosen from the data so the
result is, asymptotically, never worse than classical inference.

## Method and data

The rectified loss is the labeled loss plus lambda times (prediction loss
on N unlabeled items minus prediction loss on the n labeled items).
lambda = 0 is classical inference, lambda = 1 is original PPI. The paper
proves asymptotic normality of the minimizer for "smooth enough" convex
losses, gives the variance-minimizing lambda and a plug-in estimate of it,
and shows the PPI++ sets are asymptotically equivalent to (a sharper
version of) the original test-inversion sets. For a mean, the optimal
lambda is Cov(Y, f) / ((1 + n/N) Var(f)). A one-step Newton variant
allows lambda outside [0, 1], including negative lambda for
anti-correlated predictions. Experiments: simulations of mean, linear
and logistic regression with prediction noise varied (N = 10,000, 100
trials, alpha = 0.1); the five real datasets from the PPI paper
(deforestation, galaxies, AlphaFold odds ratio, census linear and logistic
regression).

## Results (numbers that matter)

- In simulations, tuned PPI matched PPI when predictions were accurate,
  matched classical inference when they were noisy, and beat both in
  between; coverage held near nominal throughout (figures, no tables).
- On deforestation (1,596 items), with large n and therefore small N,
  classical beat plain PPI and tuned PPI beat both.
- On galaxies and census data, tuned PPI and PPI were indistinguishable
  because the predictions were already accurate.
- The grid-based original PPI for logistic regression gave wider sets and
  often infinite sets as dimension grew (Figure 9).

## What the full text qualifies

"Always improve on classical intervals" in the abstract is an asymptotic
statement about the variance of the estimator with the optimal lambda; the
plug-in lambda is consistent, but in finite samples the paper shows this
only by simulation. The guarantees are CLT-based, so very small labeled
sets are outside what is proved. Results are mostly figures; there are no
tables of widths.

## For readcost (candidate; not cited)

If readcost ever adds human labels to its finding-precision estimate
(docs/evaluation.md, "Limits": no person has labelled the sample), PPI++
is the version to use rather than plain PPI: the model raters' agreement
with people is unknown, and power tuning falls back to the human-only
estimate when model labels carry little information, instead of widening
the interval. For a proportion (share of findings that are real reading
costs) the estimator reduces to the human mean plus lambda times the
difference between the model-label mean on all findings and on the
human-labelled ones, with the formula for lambda given above. That is
simple enough to compute in `scripts/rater_ensemble.py` without the
ppi-py package. The docs make no claim this paper bears on.

## Open questions

- With n of a few dozen human labels, the CLT intervals may undercover;
  the paper does not test n that small.
- Which model label to use as the predictor: one rater, the eight-rater
  majority, or the fraction of raters accepting a finding? A graded
  fraction may correlate better with human labels than a majority vote.
