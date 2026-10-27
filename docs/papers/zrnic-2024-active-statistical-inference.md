# Active Statistical Inference

Tijana Zrnic and Emmanuel J. Candès. arXiv 2403.03208 (v1 2024; read v3,
7 Apr 2026). https://arxiv.org/abs/2403.03208

Read: full (v3 PDF, 25 pages: main text, proofs in Appendix A, experiment
details in B, non-asymptotic extension in C; the last half page of C was
skimmed). Title and authors match the arXiv id.

## Claim

When labels are expensive and a model can predict them, choose which items
to label by the model's uncertainty, label those, and use the model's
prediction elsewhere. With inverse-probability weighting the resulting
intervals are valid for any model and narrower than intervals from uniform
sampling, with or without predictions.

## Method and data

Each unlabeled item i is labeled with probability pi(X_i), scaled so the
expected number of labels meets a budget. The mean estimate averages
f(X_i) + (Y_i - f(X_i)) * xi_i / pi(X_i), where xi_i marks a collected
label: the augmented inverse-propensity-weighted (AIPW) estimator with
propensities chosen from model uncertainty. Uniform pi gives back PPI. The
variance-minimizing rule samples in proportion to the expected size of the
model's error at X; for a binary classifier the paper uses
2 * min(p, 1 - p). To avoid near-zero probabilities that blow up the
variance, the rule is mixed with uniform sampling (tau = 0.5 by default).
Batch and sequential versions (the sequential one fine-tunes the model as
labels arrive) extend to convex M-estimation, with CLT intervals and, for
means, non-asymptotic betting intervals. Experiments: Pew post-election
survey (approval, binary), census age-income regression, AlphaFold odds
ratio; alpha = 0.1, 1,000 batch trials.

## Results (numbers that matter)

- Pew survey: all methods covered; active sampling narrowed intervals by
  at least about 10% over uniform PPI, saving about 25% of the label
  budget over uniform PPI and over 70% (Trump) to 85% (Biden) over
  classical sampling.
- Census regression: about 80% saved over classical and over 60% over
  uniform.
- AlphaFold: over 75% over classical, 20 to 25% over uniform.
- With a model trained on only 10 examples and no fine-tuning, active
  sampling can be worse than uniform PPI; sequential fine-tuning fixed
  this and saved 30 to 45%.

## What the full text qualifies

The budget savings are read off interval widths interpolated on a grid of
budgets, from figures; there are no tables. Validity is asymptotic (CLT)
except for the mean, where a betting construction works if outcomes are
bounded and sampling probabilities are bounded below. A badly calibrated
uncertainty score can make active sampling worse than uniform, which is
why the uniform mixing step exists. The "over 80%" headline is against
classical inference; the gain over PPI with the same model is 10 to 60%.

## For readcost (candidate; not cited)

readcost already has an uncertainty score for each finding: how many of
the ten model raters accept it (docs/evaluation.md, "Ten raters"). If a
person labels findings, this paper says which ones: sample findings where
the raters split with higher probability, findings all raters reject with
lower but nonzero probability, and weight by the inverse probability.
That would estimate the share of findings that are real reading costs
with a valid interval from fewer human labels than a uniform sample.
Caution: the gain relies on rater disagreement tracking human error; if
the raters agree on a wrong label (a shared bias across model families),
those items get few human labels and the variance rises, though the
estimate stays unbiased because every item keeps a nonzero sampling
probability. The docs make no claim this paper bears on.

## Open questions

- Does disagreement among the ten model raters predict where a human
  disagrees with the majority? Without that, uniform sampling plus PPI++
  is the safer design.
