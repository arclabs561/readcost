# ScanDL: A Diffusion Model for Generating Synthetic Scanpaths on Texts

Lena S. Bolliger, David R. Reich, Patrick Haller, Deborah N. Jakobi, Paul
Prasse, Lena A. Jäger. 2023. arXiv
[2310.15587](https://arxiv.org/abs/2310.15587) (v1). The PDF names no
venue.

Read: full (body, limitations, ethics, appendices A to G including the
psycholinguistic model specification and Table 7 effect sizes; the
diffusion-bound derivation in G was skimmed). Title and authors match the
ID.

## Claim

A discrete diffusion model that embeds the sentence (frozen BERT) and the
fixation sequence jointly generates scanpaths closer to human ones than
E-Z Reader, SWIFT and Eyettention, closer even than one human reader's
scanpath is to another's, and reproduces the direction of word length,
frequency and surprisal effects on reading measures.

## Method and data

- Input: the sentence's subword tokens and the scanpath as word indices,
  concatenated; only the scanpath part is noised and denoised (2,000 steps,
  12-block transformer, about 130M parameters).
- Data: CELER L1 (69 native readers, English sentences) for 5-fold
  within-corpus tests (new sentence, new reader, both); ZuCo natural
  reading (12 readers) for a cross-corpus test.
- Metric: normalized Levenshtein distance (NLD) between predicted and human
  scanpaths, against a human-to-human baseline.
- Psycholinguistic check: Bayesian GLMs of skipping, first-pass
  regression, first-pass and total fixation counts on word length,
  frequency (wordfreq) and GPT-2 XL surprisal, fitted separately to human
  and generated scanpaths.

## Results (numbers that matter)

- NLD, new reader and new sentence (Table 1): ScanDL 0.515, Eyettention
  0.578, SWIFT 0.607, E-Z Reader 0.622, uniform 0.782; human-to-human
  0.538. Cross-corpus on ZuCo: ScanDL 0.647, human 0.646.
- Ablation: without the sentence condition NLD rises to 0.667; without the
  BERT and position embeddings, 0.968.
- Effect signs for ScanDL scanpaths match the human signs on all four
  measures; for example frequency on skipping: human 0.07, ScanDL 0.21,
  Eyettention -0.03.
- All models do worse on long scanpaths with many regressions.

## What the full text qualifies

- Beating the human baseline means the model produces an average reader;
  the authors say it cannot predict individual readers.
- Effect magnitudes are not close to human: in Table 7 ScanDL's frequency
  effects on skipping and on total fixations are about two to three times
  the human estimates. The text's claim that magnitudes are "most similar"
  holds only relative to the other models.
- ScanDL predicts fixation positions only, not durations; the authors list
  this as a main limitation. NLD itself ignores durations.
- Inference takes about 2 seconds per sentence on a GPU.
- Data are single sentences from natural reading by native speakers.

## For readcost (not applicable now)

readcost's docs do not cite this paper. Like Eyettention
(deng-2023-eyettention.md), ScanDL predicts where readers look and not for
how long, so it cannot replace readcost's per-word reading-time model
(docs/evaluation.md, "Reading-time model"), and its GPU cost rules it out as
a runtime dependency. Its psycholinguistic check uses GPT-2 XL surprisal as
a predictor alongside length and frequency. That is a reminder that
readcost's finding, that surprisal from SmolLM2-135M adds nothing on
OneStop, was tested with a small scoring model. The paper does not test
surprisal's added value, so it does not contradict that finding.

No mismatch with readcost's docs.

## Open questions

None specific to readcost.
