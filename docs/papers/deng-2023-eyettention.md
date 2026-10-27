# Eyettention: An Attention-based Dual-Sequence Model for Predicting Human Scanpaths during Reading

Shuwen Deng, David R. Reich, Paul Prasse, Patrick Haller, Tobias Scheffer,
Lena A. Jäger. 2023. Proceedings of the ACM on Human-Computer Interaction
(ETRA 2023), per the preprint's footnote. arXiv
[2304.10784](https://arxiv.org/abs/2304.10784).

Read: full (arXiv v2, 24 pages: body, discussion, appendices A.1 to A.5
including the MultiMatch table and the asymmetric-window ablation). Title
and authors match the ID.

## Claim

A model that encodes the sentence (BERT embeddings through BiLSTMs) and the
fixations so far (LSTM), and links them with cross-attention restricted to
a window around the current fixation, predicts the next fixation location
better than E-Z Reader, SWIFT and earlier machine-learning models, for new
readers, new sentences and both.

## Method and data

- Output: a distribution over saccade lengths in words, forward or back,
  plus end of scanpath. Inputs per fixation: the fixated word, fixation
  duration and landing position. At generation time, duration and landing
  position are set to 0; the model predicts where readers look, not for
  how long.
- Data: Beijing Sentence Corpus (Chinese, 150 sentences, 60 readers); CELER
  L1 (English, 5,456 sentences, 69 native readers); ZuCo and ZuCo 2.0
  natural reading (English, 700 and 349 sentences, 12 and 18 readers).
  Hyperparameters tuned by training on CELER and validating on ZuCo 2.0,
  which was then set aside.
- Splits: new sentence, new reader, new reader and new sentence (5-fold);
  cross-corpus CELER to ZuCo with optional fine-tuning.
- Metrics: negative log-likelihood per fixation; normalized Levenshtein
  distance between generated and human scanpaths, with a human-to-human
  baseline.

## Results (numbers that matter)

- New reader and new sentence, CELER L1: NLL 2.297 against 2.381 for the
  best earlier model (Nilsson and Nivre 2011) and 5.49 for uniform; NLD
  0.568 against 0.595, with human-to-human 0.542. BSC: NLL 1.84 against
  2.093.
- A reader embedding improves NLL by about 4%.
- Cross-corpus: trained on CELER, tested on ZuCo, NLL 3.060; trained on
  ZuCo, 2.653; CELER then fine-tuned on ZuCo, 2.613. A few hundred
  fine-tuning items give most of the gain.
- Ablation, English: dropping word length worsens NLL (2.277 to 2.375);
  dropping the sentence encoder worsens it most (2.607); fixation duration
  and landing position add nothing for English.
- All models predict short forward saccades (1 to 3 words) best; the
  remaining weakness is long regressions and long forward saccades.
- On MultiMatch shape and length, even the uniform baseline scores 0.93 to
  0.99, so those measures barely separate models.

## What the full text qualifies

- The gains over the previous best are about 4% NLL on English; the model
  stays short of human-to-human similarity on every split.
- The data are single sentences shown alone, mostly 11 to 20 words, not
  paragraphs or documents.
- The authors put MultiMatch in the appendix because prior work showed
  wrong models can outscore the ground truth on it.

## For readcost (not applicable now; possible later)

readcost's docs do not cite this paper. readcost's reading-time model
(docs/evaluation.md, "Reading-time model") predicts each word's mean total
reading time from lexical features. Eyettention predicts fixation
locations and drops durations at generation time, so it cannot replace
that model or give a reading time. Two points:

- Its ablation agrees with readcost's feature importance: word length is
  the input feature that matters for English.
- Regressions are the eye-movement behaviour most tied to the
  constructions readcost flags (long dependencies, garden paths), and they
  are what this model predicts worst. A scanpath model is not yet a
  reliable way to check whether a flagged sentence causes rereading.

No mismatch with readcost's docs.

## Open questions

- Would a scanpath model trained on paragraph data (for example OneStop,
  which readcost already uses) predict more regressions on sentences
  readcost flags than on the same sentences rewritten?
