# How to Run Statistics over LLM Judges and Trust the Results: Calibrated Inference for Small-Sample AI Evaluation with evalstats

Ian Arawjo. 2026. arXiv 2609.35815 (v1, 20 Sep 2026).
https://arxiv.org/abs/2609.35815 (code: https://github.com/ianarawjo/evalstats)

Read: main text in full (sections 1 to 10); Appendix B (PPI validation,
bootstrap-adaptive power tuning, judge-bias sweep design) in full;
Appendix A (simulation tables for CI, p-value and FWER methods) and
Appendices C to F (rank-test derivations, efficiency simulations,
end-to-end sweep, full-page plots) skimmed for method and headline
numbers only. Title and author match the arXiv id. The paper states that
its PPI methods were built with help from LLMs and that Appendix C was
drafted by one.

## Claim

Running statistics directly on LLM-judge scores, justified by high
agreement with human raters, inflates false positives, and for several
agreement metrics the risk is worst at "almost perfect" agreement. The
fix is to treat the judge as a noisy predictor, label a random subset by
hand, and correct every estimate with prediction-powered inference (PPI).
For small evaluations (N under 100), the paper recommends specific
interval and test methods from simulation and warns against bootstrap
intervals.

## Method and data

Monte Carlo simulations over binary, continuous [0, 1] and 1-to-5 Likert
data at N = 15 to 100, synthetic and resampled from real benchmark
outputs, scoring coverage, interval score, worst-case coverage, Type I
error and power. PPI-corrected versions of nine tests (t-tests, Welch,
Mann-Whitney U, Wilcoxon, ANOVA, Friedman, Kruskal-Wallis), validated
under a factorial sweep of judge biases (constant and group-specific
shifts, length confounds, noise, scale compression, MNAR labeling); about
3.7 million null trials. A modified PPI++ weight ("bootstrap-adaptive
power tuning") shrinks the plug-in weight toward the share of bootstrap
resamples in which the judge looks informative, with weight
N_lab / (N_lab + 20) on the plug-in, and adds the weight's own variance
to the interval. Real judge data from five corpora (Arena, WMT DA, App
Store, Privacy Judge, ICLR metareviews). Three worked demonstrations.

## Results (numbers that matter)

- Recommended defaults: Wilson interval for a binary mean; Bonett-Price
  for paired binary differences; Šidák simultaneous intervals; Shaffer
  (n < 30) or Romano-Wolf (n >= 30) for family-wise correction.
- Bootstrap intervals (percentile, BCa, studentized and others) were
  overconfident nearly everywhere below N = 100; on paired binary data
  none reached nominal coverage even at N = 100.
- Uncorrected judge scores: for binary data, higher Cohen's kappa lowers
  but does not remove false positives (kappa 0.81 still gave about 37%
  false positives in footnote 7). For Likert data, false-positive risk
  peaks around agreement 0.80 to 0.90.
- Effective sample size from a judge: N_eff = N_lab / (1 - rho^2 (1 -
  N_lab / N)). Gains start around rho^2 = 0.4 (about 1.36x at worst, 1.57x
  on average; kappa about 0.6); below rho^2 = 0.2 (kappa about 0.43) the
  judge is not worth using.
- Floors: no PPI statistics below 15 human labels; aim for 30 per
  condition. Human labels must be drawn at random (MCAR); under MNAR the
  paired tests held up best.
- Demonstration 8.3 (real ELLIPSE essays, six-judge ensemble, quadratic
  weighted kappa 0.66 with two human raters): uncorrected tests found
  p = 1.9e-4 where the human ratings show no difference (p = 0.47); the
  corrected test gave p = 0.31.

## What the full text qualifies

The headline "false positive risk peaks at almost perfect agreement" is
for numeric (continuous and Likert) metrics; for binary kappa the risk
falls as kappa rises but never reaches nominal. The rho^2 >= 0.4 rule is
a rule of thumb from the author's simulation grid, and the gain is
relative to the number of human labels you start with: 30 labels with
rho^2 = 0.4 and 300 judge scores buy only about 17 effective labels more.
Pairwise intervals for between-subjects designs are not validated, PPI
correction in `compare()` needs at least 50 items and one factor, and
there was no user study. The worked demonstrations mix real and
synthetic data; footnotes say which.

## For readcost (candidate; not cited)

This paper is the closest match to readcost's evaluation, which labels
210 findings with model raters only (docs/evaluation.md, "Second rater",
"Ten raters"). Points that bear on the docs:

- docs/evaluation.md lines 463 to 465 read Cohen's kappa near 0.4 between
  Claude and Codex as "moderate agreement". That is the standard Landis
  and Koch band and is accurate as a description. This paper's point is
  that agreement, high or moderate, does not license treating any model
  rater's labels as truth, and that between a model and people (not
  between two models) a kappa below about 0.41 makes the model labels
  useless even with correction. readcost has no model-human agreement at
  all, so the docs' own caveat ("neither rater is ground truth") is the
  right reading, and the Limits section already says so.
- docs/evaluation.md lines 497 to 507 compare majority acceptance across
  rule versions (11.5% of 156, 14.3% of 63, 20.0% of 75) and say the fixes
  "gained 3 points" and the revert "gains 6 more". These are point
  estimates without intervals. Wilson 95% intervals (computed here, not in
  the paper) are 7.4% to 17.5%, 7.7% to 25.0% and 12.5% to 30.4%, which
  overlap heavily. The findings are nested subsets of one 210-finding
  sample, so a paired test would be the right comparison; as written, the
  "points gained" claims are not shown to exceed sampling noise. Mismatch
  in kind: the docs state gains the data cannot distinguish from noise.
- The eight-rater majority drops two raters (Llama 4 Maverick, MiniMax M3)
  after seeing that they are lenient (lines 487 to 489). The paper's
  Step 2 warns that tuning a judge on the data later used for inference
  overfits the judge; choosing which raters count after seeing their
  labels on the same 210 findings is a mild form of that.
- Design to adopt: draw 30 or more findings at random (stratified by rule)
  for a person to label, report the model-majority's rho^2 against them,
  and report precision per rule with a PPI-corrected Wilson-style
  interval. If rho^2 is below 0.2, report the human-only estimate.
- If readcost bootstraps any interval on its small samples (the docs
  report none today), this paper's simulations say not to below N = 100.

## Open questions

- PPI's guarantee assumes good human labels; the paper leaves multi-rater
  disagreement to future work. readcost's construct ("a real reading cost
  an editor would fix") may not reach substantial human-human agreement,
  which the paper's Step 1 sets as a precondition.
- The bootstrap-adaptive weight has no proof; its calibration rests on the
  author's simulations.
