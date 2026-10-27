# A critique of cyclomatic complexity as a software metric

Martin Shepperd. 1988. Software Engineering Journal 3(2), March 1988.
https://doi.org/10.1049/sej.1988.0003

Read: full text (7 pages; title, author and journal header checked). The
copy read is a scan hosted on a University of Denver course page
(cs.du.edu), not by the author or publisher; the publisher version is
paywalled. Table 1 (summary of empirical studies) extracted as a jumble of
coefficients and could not be matched to studies row by row.

## Claim

McCabe's cyclomatic complexity rests on weak theory and weak evidence. For
a large class of software it is little more than a proxy for lines of
code, and lines of code often predict as well or better. New metrics
should be validated against lines of code as a baseline.

## Method and data

A critical review, no new data: McCabe's definitions and counting rules,
theoretical objections, and a table of about 17 prior empirical studies
correlating v(G) with errors, development time, maintenance or recall.

## Results (numbers that matter)

- Theory: the metric ignores ELSE branches and nesting, is insensitive to
  long linear code, can rise when code is restructured in accepted ways,
  and rises as a program is split into more modules (v(P') = v(P) + i).
- Evidence: correlations are erratic; the clearest result across studies
  is the strong association between v(G) and LOC; LOC outperforms v(G) in
  over a third of the studies considered. Basili and Perricone found error
  density falling as v(G) rises.
- Method: many validations use Pearson correlation on skewed error counts,
  inflating coefficients, and rely on correlation without an explicit
  model to refute.

## What the full text qualifies

- The LOC-as-baseline idea is attributed to an earlier reference (Ref. 55),
  which Shepperd endorses; it is not his own new proposal.
- He allows that v(G) may track testing effort for decision-bound code and
  that the metric's validity depends on what it is meant to capture
  (testing paths vs comprehension).
- The review predates any study with comprehension measured directly in
  readers; its comprehension points are argument, not data.

## For readcost (used, accurately)

- Cited in docs/research.md lines 100 to 102: "Any new index is checked
  against a plain baseline, the number of sentences times their mean
  length, before it is trusted (Shepperd 1988)." This is a fair transfer:
  Shepperd's baseline is lines of code; readcost's analogue is word count.
  readcost's own results follow the pattern he describes (length carries
  much of the signal in the CEFR-SP and CLEAR tests in docs/evaluation.md).
- The reference entry (research.md lines 176 to 177) lacks volume and pages;
  3(2), 30 to 36 per the publisher listing (one secondary citation gives
  pages 317 to 324; not resolved here).
- The point about skewed data and Pearson correlation applies to
  readcost's evaluation, which already uses Spearman and Wilcoxon tests.

## Open questions

- None beyond the baseline rule; the paper's value for readcost is
  methodological.
