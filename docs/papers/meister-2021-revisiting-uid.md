# Revisiting the Uniform Information Density Hypothesis

Clara Meister, Tiago Pimentel, Patrick Haller, Lena Jäger, Ryan Cotterell,
Roger Levy. 2021. EMNLP 2021, 963-980; arXiv
[2109.11635](https://arxiv.org/abs/2109.11635) (v1).

Read: full (body, appendix A proof, appendix B data and evaluation,
appendix C figure and table captions). Title and authors match. Appendix C
figures are plots; their content is known from captions only.

## Claim

At the sentence level, reading time and acceptability are better
predicted by a sum of surprisals raised to a power slightly above 1 than
by plain summed surprisal: evidence for uniform information density
(UID) in comprehension, clear for acceptability and only suggestive for
reading time. Among measures of non-uniformity, super-linear surprisal
and variance around the language-wide mean surprisal work best; local or
sentence-level variance, the maximum surprisal and entropy measures work
worse.

## Method and data

- Reading times summed per sentence: Natural Stories and Brown
  (self-paced), Provo and Dundee (eye tracking, total dwell time incl.
  rereading); acceptability: CoLA and BNC. GECO Dutch in the appendix.
- Surprisal from GPT-2, Transformer-XL, BERT (pseudo) and a 5-gram model.
- Mixed-effects regression with word count and fixated-word count as
  controls; Delta log-likelihood on held-out folds (10-fold).

## Results (numbers that matter)

- Reading time: the best k is slightly above 1, but k = 1 stays within the
  standard error; paired tests never reject linearity. Acceptability: k >
  1 is reliably better (p < .001 except the n-gram model).
- Table 1 (GPT-2, 10^-2 nats): on Provo, super-linear k = 1.5 gives 3.25,
  sentence variance 2.59, local variance 2.15, max 1.17; on Dundee, k =
  1.25 gives 4.93, language variance 2.37, sentence variance 2.01, local
  1.93, max 1.74. Entropy measures near 0.
- Word-level: variance around a mean computed over the sentence,
  document or language predicts reading time better than a mean over the
  previous 1 to 4 words.

## What the full text qualifies

- The reading-time evidence for UID is weak; the linear surprisal account
  is not ruled out.
- Sentence-level measures sum word times, so they include sentence length
  effects the controls only partly remove.

## For readcost (used / tested / candidate)

Not cited. Relevant to docs/evaluation.md lines 1101-1104, which calls
the standard deviation of surprisal within a sentence "the uniform
information density idea" and finds it tracks CEFR-SP difficulty a
little. Per this paper, within-sentence variance is one of the weaker UID
operationalizations; super-linear summed surprisal and variance around a
language-wide mean predict reading times and acceptability better. If
readcost adds a surprisal-uniformity signal, these two are the candidates
to test first, not sentence SD.

Also relevant to readcost's reading-time model: Provo total dwell time is
the same measure readcost uses.

## Open questions

- Whether summed surprisal^k with k around 1.25 adds anything over
  readcost's lexical model on OneStop at the paragraph level (readcost
  found plain surprisal added nothing).
