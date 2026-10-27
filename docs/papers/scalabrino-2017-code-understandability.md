# Automatically Assessing Code Understandability: How Far Are We?

Simone Scalabrino, Gabriele Bavota, Christopher Vendome, Mario
Linares-Vásquez, Denys Poshyvanyk, Rocco Oliveto. 2017. ASE 2017.
https://doi.org/10.1109/ASE.2017.8115654
(author copy: https://www.cs.wm.edu/~dposhyvanyk/pubs/ASE'17-Readability.pdf)

Read: full (author PDF, 11 pages; title and authors checked). All sections
read. Table I (metric list) and Figure 2 (correlation heat map) extracted
only partly; correlations below are those named in the text.

## Claim

None of 121 metrics (code, documentation and developer metrics, including
readability models and cyclomatic complexity) correlates more than weakly
with how well people understood 50 Java methods. The authors call it a
negative result.

## Method and data

- 50 Java and Android methods of 30 to 70 effective lines, five from each
  of ten systems, chosen to spread over the metric space.
- 46 participants (about 70 percent bachelor's students, five professional
  developers) each tried to understand eight methods, with web search and
  navigation allowed; 324 evaluations (about 6.5 per method).
- Outcomes: perceived understanding (button), time to "I understood",
  actual understanding (three verification questions), and a combination
  of correctness and time.
- 121 metrics, cut to 74 after removing pairs with Kendall's tau of 0.7 or
  more; Kendall's tau with each outcome. Documentation metrics include the
  Flesch reading ease of comments and of Javadoc.

## Results (numbers that matter)

- 50 of 74 metrics show no correlation (|tau| below 0.1) with any outcome;
  the rest are weak. Strongest: max line length with perceived
  understanding (tau about -0.17); DFT of conditionals with the timed
  outcome (about -0.18); average textual coherence with actual
  understanding (about -0.16, in the unexpected direction).
- Experience: years of programming correlate weakly and positively with
  time taken (about 0.15 to 0.16).
- A snippet everyone understood scored 0.14 on the authors' own earlier
  readability model.

## What the full text qualifies

- Lines of code varied only from 30 to 70, so length effects were limited
  by design; the authors note this.
- About 6.5 evaluations per method, mostly students, so per-method
  outcomes are noisy; no power analysis.
- Experience is not reported as a strong predictor here; it is one weak
  correlate among several. Trockman et al. 2018 reanalyse these data and
  find combined metrics do better.

## For readcost (used, accurately)

- Cited in docs/research.md lines 20 to 21 with Peitek et al. 2021: "No
  single static metric predicts how well people understand code". Accurate
  for this paper.
- Relevant detail the docs could use: comment readability measured by
  Flesch reading ease was among the metrics with no useful correlation.
  That is direct evidence that a prose-readability score of comments did
  not track how well the code was understood, which supports readcost's
  choice to report sentences rather than score files.
- The reference entry (research.md lines 172 to 173) is accurate.

## Open questions

- None of the metrics measured comment construction; whether specific
  constructions in comments slow understanding remains untested.
