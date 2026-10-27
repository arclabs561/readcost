# The effect of word predictability on reading time is logarithmic

Nathaniel J. Smith, Roger Levy. 2013. Cognition 128(3), 302-319. DOI
[10.1016/j.cognition.2013.02.013](https://doi.org/10.1016/j.cognition.2013.02.013);
NIH author manuscript PMC3709001.

Read: full (PMC author manuscript: body, discussion, appendices A to C).
The equations and figures are images in the HTML and were not readable;
their content is described in the text. The supplementary PDF was not
read. Title and authors match.

## Claim

Reading time grows linearly with surprisal (the log of a word's
probability in context) over at least six orders of magnitude of
probability, in both eye tracking and self-paced reading; there is no
super-logarithmic component. The authors derive the logarithm from a
model in which processing is highly incremental below the word level.

## Method and data

- Dundee first-pass gaze durations (10 readers, 166,522 points after
  exclusions) and Brown-corpus self-paced reading (35 readers, 51,552).
- Probabilities: modified Kneser-Ney trigram on the BNC with a bigram
  cache.
- Penalized cubic splines (mgcv) of log probability for the current word
  and previous words (2 for eye tracking, 4 for self-paced), with controls
  for position, a length-by-log-frequency surface and participant.
  Excluded: line-initial and final words, words next to punctuation, words
  with numerals.

## Results (numbers that matter)

- The summed slowdown is a straight line in log probability; a quadratic
  term is null (eye tracking beta -0.05, 95% CI -0.45 to 0.37; self-paced
  0.04, CI -0.90 to 1.07).
- Time course: in eye tracking the effect is on the word and the next one;
  in self-paced reading it starts on the next word and lasts three words.
  Totals are about the same.
- Nine of ten Dundee readers show the linear-in-log effect individually.
- With crossed item and subject random effects (appendix B), the effect of
  the previous word's log probability stays significant in both datasets
  (Dundee one-back |t| = 5.59).

## What the full text qualifies

- Trigram-plus-cache model; long-range context only partly represented.
- Item random effects were handled in an appendix rather than the main
  analysis.

## For readcost (used / tested / candidate)

Not cited directly in readcost's docs; cited inside Clark et al. and
Cekini et al. as the reading-time basis for surprisal.

- Any probability feature readcost adds should enter as a log (surprisal
  or log frequency), as the Zipf frequency feature already does.
- Spillover: the previous word's predictability affects the current
  word's time; readcost's neighbour features use length and frequency of
  the previous word, consistent with this. A bigram log-probability of the
  previous word would be the direct analogue.
- Against UID-based reasoning: no super-logarithmic cost was found, so
  "uneven surprisal" (docs/evaluation.md lines 1101-1104) has no support
  here as a reading-time cost; Meister et al. 2021 later found at most a
  slight super-linearity.

## Open questions

None specific.
