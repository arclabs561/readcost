# Prediction-Powered Inference

Anastasios N. Angelopoulos, Stephen Bates, Clara Fannjiang, Michael I.
Jordan and Tijana Zrnic. 2023. arXiv 2301.09633v4 (9 Nov 2023); the PDF
names no venue. https://arxiv.org/abs/2301.09633

Read: full (arXiv v4 PDF, 40 pages: main text, appendices A to H on
p-values, finite populations, nonasymptotic intervals, proofs, baselines,
underpowered cases and experiment details). Title and authors match the
arXiv id.

## Claim

A small set of gold-standard labels plus a large set of model predictions
can give confidence intervals that are valid whatever the model is, and
narrower than intervals from the gold labels alone when the model is good
enough. Treating predictions as if they were labels ("imputation") gives
intervals that miss the truth.

## Method and data

The estimate from predictions on the unlabeled set is corrected by a
"rectifier": the mean prediction error measured on the labeled set. For a
mean, the estimate is the mean prediction on N unlabeled items minus the
mean of (prediction minus label) on n labeled items, and the interval width
is driven by the variance of the prediction error over n plus the variance
of predictions over N. The same idea extends to quantiles, logistic and
linear regression, any convex loss, and (with data splitting) nonconvex
losses. The paper gives CLT-based and nonasymptotic (betting
supermartingale, Waudby-Smith and Ramdas) versions, a finite-population
version where the n labeled items are a uniform random subset of the N,
and versions under known covariate shift and under label shift. The model
must be independent of the labeled and unlabeled data (trained elsewhere).
Seven applications: AlphaFold and protein disorder, galaxy morphology,
gene expression quantiles, Amazon deforestation, census health insurance,
census income under covariate shift, plankton counts under label shift.

## Results (numbers that matter)

- Labels needed to reject a fixed null (Table 2), prediction-powered vs
  classical: 316 vs 799 (proteins), 189 vs 449 (galaxies), 764 vs 900
  (genes), 21 vs 35 (deforestation), 5569 vs 6653 (insurance), 177 vs 282
  (income).
- The imputed interval failed to cover the true value in every application.
- Appendix G, where it does not help: with a weak predictor (linear model on
  deforestation) it needed 40 labels against 35 classical; with only
  N = 1000 unlabeled items it needed 869 against 652.

## What the full text qualifies

The abstract says more accurate predictions give smaller intervals; the
appendix makes the conditions concrete. Gains need N much larger than n
and a predictor that explains some of the outcome variance. For a binary
outcome with symmetric error rate e, the paper works out that at a base
rate of 0.5 the predictor's error must be below 25% to help, and at a base
rate of 0.1 below about 9.5%. Lower-variance outcomes demand a more
accurate predictor. The CLT intervals are asymptotic; small n calls for the
nonasymptotic versions, which assume bounded outcomes and are wider.

## For readcost (candidate; not cited)

readcost's evaluation (docs/evaluation.md, "Second rater", "Ten raters",
"Limits") estimates the share of findings that are real reading costs from
model raters only, and the Limits section says no person has labelled the
sample. PPI is the standard way to combine a small human-labelled subset
with model labels on many findings and report a valid interval for
precision. Two cautions from the full text apply directly:

- The quantity readcost estimates has a base rate near 0.1 (the
  eight-rater majority accepts 11.5% to 20% of reported findings). By the
  paper's own calculation, a model rater then needs a disagreement rate
  with people below about 10% before PPI beats labelling by people alone.
  The model raters disagree with each other far more than that (Claude and
  Codex agree on 81% of three-way labels), so a single model rater is
  unlikely to tighten the interval; the gain would need the majority or a
  calibrated ensemble to be much closer to people.
- The gain needs N much larger than n. The 210-finding sample is too small
  to be the unlabeled pool; the pool should be all findings in the corpus
  run (thousands), with humans labelling a uniform random subset, which
  the finite-population version covers.

The docs make no claim this paper contradicts. The current precision
figures are imputation in this paper's terms: model labels treated as
truth, with no interval.

## Open questions

- How large is the disagreement between the model-majority label and a
  human label on readcost findings? That number decides whether PPI is
  worth running at all.
- The rater-1 labels also came from the model that helped write the rules;
  PPI assumes the predictor is independent of the labeled data, which an
  LLM rater not trained on these findings satisfies, but rater selection
  after seeing agreement (dropping the two lenient raters) is a choice made
  on the same data.
