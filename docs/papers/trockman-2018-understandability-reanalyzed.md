# "Automatically Assessing Code Understandability" Reanalyzed: Combined Metrics Matter

Asher Trockman, Keenen Cates, Mark Mozina, Tuan Nguyen, Christian Kästner,
Bogdan Vasilescu. 2018. MSR 2018. https://doi.org/10.1145/3196398.3196441
(author copy: https://www.cs.cmu.edu/~ckaestne/pdf/msr18underst.pdf)

Read: full (author PDF, 5 pages; title and authors checked). Table 1
(regression coefficients) and Figures 1 to 3 extracted only partly;
coefficients below are those stated in the text.

## Claim

Reanalysing Scalabrino et al.'s data with multivariate models, some code
metrics do correlate with understanding once others are held fixed, and a
combination of metrics has a small amount of predictive power. Programming
experience is the largest single factor.

## Method and data

- Same 324 observations from 46 participants; outcome recoded as
  understood when at least two of three verification questions are right.
  "Professional" means five or more years of programming (13
  participants); "Java professional" five or more years of Java (4).
- Mixed-effects logistic regression with a random intercept per
  participant: one model with variables picked from a principal-component
  analysis, one by forward stepwise selection on AIC (ten variables).
- Prediction: LASSO logistic regression, 5,000 random 75/25 splits.

## Results (numbers that matter)

- PCA-guided model: conditional pseudo-R squared about 20 percent; only
  max line length (odds 0.98 per character) and professional (odds about
  3) are significant.
- Stepwise model: pseudo-R squared 41 percent; professional odds 2.75;
  narrow-meaning identifiers odds 1.8; periods per line odds 0.34; better
  documentation of called methods odds 0.39 and higher textual coherence
  odds 0.027, both in the unexpected direction.
- LASSO: mean AUC 0.64 (2.5 to 97.5 percentile from 0.54); professional
  and textual coherence are selected in over 99 percent of splits.

## What the full text qualifies

- The authors call the predictive power small and the data set the main
  limitation; 121 candidate variables on 324 observations invite spurious
  findings, and stepwise selection biases p values.
- They found some verification questions shallow or ambiguous, which
  limits what any model can predict.
- The pseudo-R squared of 41 percent includes the random participant
  effect; the fixed part alone is not reported in the text.

## For readcost (used, partly accurate)

- Cited in docs/research.md lines 21 to 22: "reader experience matters more
  than any metric (Trockman et al. 2018)". The paper does say experience is
  "the greatest factor" (marked quote) in its models, so the sentence is
  supported. But the paper's thesis runs the other way from the use
  research.md makes of it: its title and conclusion are that combined
  metrics do carry signal beyond experience (AUC 0.64). research.md uses
  it alongside Scalabrino et al. to caution against a prose index. A fair
  summary: "experience matters most; a combination of metrics adds a
  small, real signal (Trockman et al. 2018)". That matches readcost's own
  CEFR-SP result: findings add a small real signal beyond length.
- The reference entry (research.md lines 183 to 184) is accurate.

## Open questions

- No experience variable exists for readcost's readers; readcost's
  reading-time model has the same blind spot (newspaper readers, not
  developers).
