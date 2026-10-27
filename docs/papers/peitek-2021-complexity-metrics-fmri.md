# Program Comprehension and Code Complexity Metrics: An fMRI Study

Norman Peitek, Sven Apel, Chris Parnin, André Brechmann, Janet Siegmund.
2021. ICSE 2021. https://doi.org/10.1109/ICSE43902.2021.00056
(author copy: https://www.tu-chemnitz.de/informatik/ST/publications/papers/ICSE21.pdf)

Read: full (author PDF, 13 pages; title and the first authors checked).
The two-column layout extracted with interleaved columns; all sections
were read in that form. Tables I to III extracted only partly, so
correlations below are those stated in the text plus the legible row of
Table II.

## Claim

Code complexity metrics explain program comprehension only partly. In an
fMRI study, lines of code and Halstead's vocabulary track cognitive load
and attention, Beyer's data-flow metric DepDegree tracks activation most
consistently, and McCabe's cyclomatic complexity tracks nothing measured.
No single metric predicts overall cognitive effort.

## Method and data

- 19 late undergraduate or graduate students (one excluded for head
  movement), intermediate experience (6.8 years programming on average).
- 16 Java snippets (at most 30 lines, solvable within 60 seconds, no
  context, identifiers kept), chosen from a pool of 50 to vary LOC,
  Halstead, McCabe and DepDegree; 37 further metrics from MetricsReloaded
  and SonarQube.
- Task: say what the snippet prints. 3-tesla scanner; brain areas from a
  comprehension vs control contrast; default-mode deactivation as a load
  measure. After the scan, participants sorted snippets into 2 to 4
  complexity piles.
- Kendall's tau between each metric and per-snippet behavior, activation
  and subjective rating.

## Results (numbers that matter)

- Behavior: mean 32 s per task, 72 percent correct. McCabe correlates with
  neither time nor correctness; LOC, Halstead and DepDegree have small
  correlations with time and medium ones with correctness.
- Activation (BA 6, 21, 39, and 44/45, Broca's area): LOC medium with BA
  21, small elsewhere; Halstead and DepDegree medium across BA 6, 21, 39;
  McCabe none.
- Deactivation (default mode network): LOC and Halstead medium,
  DepDegree small, McCabe none.
- Among 37 more metrics, simple ones (number of branches, maximum loop
  depth, number of parameters) beat McCabe; SonarQube's "cognitive
  complexity" reaches only a small correlation.
- Subjective complexity ratings correlate with correctness at tau -0.77
  and with self-reported concentration at -0.69, more strongly than any
  code metric.

## What the full text qualifies

- 16 snippets and 18 usable participants; metric ranges were small (only
  six distinct McCabe values, maximum 8), so null results for McCabe may
  reflect range restriction, as the authors say.
- The four metrics are correlated with each other by construction.
- Task is output prediction for intermediate programmers; other tasks and
  experts may differ.
- The authors note DepDegree ignores the distance of a data dependency and
  suggest adding locality, an idea close to dependency-length measures in
  linguistics.

## For readcost (used, accurately, plus candidates)

- Cited in docs/research.md lines 20 to 21 with Scalabrino et al. 2017:
  "No single static metric predicts how well people understand code".
  Accurate; the paper says no single metric predicts overall cognitive
  effort.
- The reference entry (research.md lines 167 to 168) is accurate; the
  co-authors (Apel, Parnin, Brechmann, Siegmund) could be listed.
- Candidate: the study's own rationale borrows from sentence-processing
  research (filler-gap dependencies, Broca's area), the same literature
  behind readcost's long-dependency and center-embedding rules. Its
  suggestion that dependency distance matters, not just count, matches
  readcost's word-distance choice in research.md lines 48 to 51; it is a
  suggestion, not a tested result.
- Candidate: the strong showing of subjective difficulty ratings supports
  collecting reader ratings in any human evaluation readcost runs.

## Open questions

- Would a distance-weighted DepDegree do better than plain DepDegree? The
  paper proposes it but does not test it.
