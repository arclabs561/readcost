# Deriving Metric Thresholds from Benchmark Data

Tiago L. Alves, Christiaan Ypma, Joost Visser. 2010. ICSM 2010 (26th IEEE
International Conference on Software Maintenance). DOI
10.1109/ICSM.2010.5609747. Author copy from the University of Minho
web archive (AlvesYpmaVisserICSM2010.pdf).

Read: full (10 pages, sections I to IX). Title and authors match. Figures
are quantile plots; values come from the text and tables.

## Claim

Metric thresholds should come from the distribution of a benchmark of
systems, not expert opinion: weight each unit by its size, normalize so
every system counts equally, pool, and take the metric values that cover
70%, 80% and 90% of all code. These give "quality profiles" (share of code
in low, moderate, high, very-high risk) that differ between systems.

## Method and data

- Six steps: per unit (method) metric and weight (LOC); weight as a share
  of its system's LOC; per-system weighted histogram; average over
  systems; quantile function; thresholds at chosen percentages.
- Benchmark: 100 Java and C# systems (proprietary and open source, 3K to
  800K LOC, 12M LOC total), outlier systems removed after expert review;
  generated and test code excluded.

## Results (numbers that matter)

- McCabe thresholds 6, 8, 14 at 70/80/90% (the motivating example in
  section III says 15). Unit size 30/44/74 LOC; unit interfacing 2/3/4 at
  80/90/95%; fan-in 10/22/56; methods per file 29/42/73.
- Applied back, the median system has about 70% of its code in low risk
  and about 10% in each other band.
- Weighting by LOC moves the metric's variation from the last third of
  methods to the last 80% of code; McCabe and LOC correlate (Spearman
  0.779), which the authors accept by design.

## What the full text qualifies

- The benchmark is meant to be representative of systems in general, not
  a set of good systems; the 90% threshold marks the worst 10% of code
  by volume relative to that benchmark.
- Thresholds are relative to the tool and scoping used; the same tool must
  be used for calibration and analysis.
- No link to external quality (defects, maintenance effort) is tested in
  this paper; that is named future work.

## For readcost (used / tested / candidate)

Used: `sentence_words_profile` (metrics.py lines 17-18, 44-52;
scripts/metric_cut_points.py; README.md line 414) and the threshold
method in docs/research.md lines 70-73 and docs/evaluation.md lines
626-643.

Citation accuracy:

- metrics.py and metric_cut_points.py: sentence as unit, words as weight,
  each document weighted equally, cut points at the 70th, 80th and 90th
  percentiles, and the 70/10/10/10 check: a faithful transfer of the
  method.
- docs/evaluation.md lines 627-628, "Following Alves et al. 2010, a
  threshold should sit at a high percentile of good writing of the same
  kind": partly accurate. Alves calibrates on a representative benchmark,
  not on good examples, and sets thresholds at 70/80/90% of weighted
  volume to rank units within systems. readcost then compares the verdict
  thresholds with p90/p95/p99 of a per-text index over curated,
  well-edited texts, which is a different use: a per-document index, not
  unit-level risk bands, and a curated rather than representative corpus.
  The method supports building the profile; it does not specifically
  support putting a block threshold at the 99th percentile of good text.
- docs/research.md lines 72-73, "Thresholds should come from percentiles
  of that corpus (Alves, Ypma and Visser 2010)": accurate in spirit.

## Open questions

- Alves's method applied literally to readcost would weight sentences by
  words and report the share of a document's words in sentences with
  findings, per risk band, rather than one index per text.
