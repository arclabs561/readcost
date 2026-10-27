# Prompt-based Learning for Text Readability Assessment

Bruce W. Lee, Jason Hyung-Jong Lee. 2023 (arXiv v2 June 2024). arXiv
[2302.13139](https://arxiv.org/abs/2302.13139). The PDF names no venue.

Read: full (short paper: body, limitations, appendices A and B). Title and
authors match the ID; the topic, pairwise readability ranking with T5 and
BART, matches the request.

## Claim

A seq2seq model (T5 or BART) can be fine-tuned to say which of two texts is
harder. Training on pairs from parallel simplification corpora teaches a
notion of relative difficulty that transfers to other corpora, and lets
corpora with different level schemes be trained together.

## Method and data

- Pairs: for parallel corpora, every ordered pair of versions of the same
  article ("slug"); for distinct corpora, every pair of texts at different
  levels.
- Training data: Newsela (2,154 slugs, 4 or 5 versions, 43,316 pairs) and
  OneStopEnglish (189 slugs, 3 versions, 1,134 pairs), each split 6:2:2 at
  random over pairs. Test-only: Common Core exemplar stories (69 texts, 6
  levels) and Cambridge exams (331 texts, A2 to C2).
- Nine prompt formats (question, statement, follow-up; "more difficult",
  "easier", "harder"). T5-base and BART-base, 512 tokens for both texts
  together, so at most about 256 tokens per text; most OneStopEnglish texts
  were truncated.
- Baseline: Flesch-Kincaid grade, comparing the two texts' grades.

## Results (numbers that matter)

- Prompt format matters for T5 on OneStopEnglish: validation accuracy 0.52
  to 0.83 across formats. BART reaches 0.94 to 0.99.
- Table 3, pairwise accuracy (OneStopEnglish, Newsela, Common Core,
  Cambridge): Flesch-Kincaid 0.978, 0.986, 0.798, 0.808. BART trained on
  Newsela 0.987, 0.993, 0.793, 0.883. Best joint model BART on both 0.983,
  0.996, 0.790, 0.865.
- Accuracy falls when the two texts' levels are close (the authors report
  this qualitatively; no numbers per level gap).

## What the full text qualifies

- The plain Flesch-Kincaid baseline is within about one point of the best
  models on both parallel corpora and beats every model on Common Core.
  The authors call formulas "surprisingly strong baselines" for pairwise
  comparison.
- The split is random over pairs, not over articles, so pairs from the same
  article appear in training and test. The authors do not discuss this.
- The "0.208" increase in the text is the T5 gain from 0.784 to 0.992, not
  an accuracy.
- The limitations section concedes that a pairwise answer alone (quote:
  "knowing which is easier out of texts has little use as a real-world
  system") and that long texts need a sliding window.

## For readcost (candidate evidence; not cited)

readcost's docs do not cite this paper. It bears directly on "Text
difficulty benchmarks" in docs/evaluation.md, which uses the same
pairwise design on OneStopEnglish: for each article, is the advanced
version higher than the elementary one?

- readcost reports words per sentence higher in the advanced version in 99%
  of articles and its cost index in 61%. This paper's Flesch-Kincaid
  baseline orders OneStopEnglish pairs correctly 97.8% of the time, so a
  length-based formula nearly saturates this test. Corpora with parallel
  levels show that a signal tracks the editors' rewrite. They cannot show
  that it tracks reading cost beyond length. readcost's text already makes
  this point. The paper adds a published number for the formula baseline
  that readcost could print beside its own rows.
- Common Core and Cambridge, where formulas reach only 0.80 and 0.81, are
  harder pairwise tests than OneStopEnglish if readcost wants one that
  length does not saturate.

No readcost claim conflicts with the paper.

## Open questions

- How do readcost's predicted ms per word and cost index do on the Common
  Core and Cambridge pairwise tests, against the 0.80 formula baseline?
