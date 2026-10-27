# Probing for Reading Times

Eleftheria Tsipidi, Samuel Kiegeland, Francesco Ignazio Re, Tianyang Xu,
Mario Giulianelli, Karolina Stańczak, Ryan Cotterell. 2026. arXiv
[2604.18712](https://arxiv.org/abs/2604.18712) (v1, 20 April 2026).

Read: full (body, limitations, appendices on data, combined predictors,
monolingual models, qualitative example, permutation and mixed-model
results). Title and authors match. Appendix tables are numeric dumps; only
the headline cells were checked.

## Claim

Regularized linear probes on a language model's hidden states predict
early eye-tracking measures (first fixation, gaze duration) better than
surprisal, with early layers best; for total reading time, scalar
surprisal is as good or better than whole representations. Which
predictor wins depends on language and measure.

## Method and data

- Provo (84 English readers, 55 passages) and MECO English, Greek, Hebrew,
  Russian, Turkish; reading times averaged over participants per word
  (the preprocessed MECO folder is named "merged_data_no_zero").
- Predictors: mGPT (1.3B, 24 layers) surprisal, every layer's
  mean-pooled word representation, information value, logit-lens
  surprisal; GPT-2 and a Turkish model in the appendix. OLS, ridge or
  LASSO chosen per setting; 10-fold CV, reported as Delta MSE against a
  baseline of standard psycholinguistic predictors; permutation control;
  mixed models with random intercepts on 25 principal components.

## Results (numbers that matter)

- Provo total reading time, Delta MSE (negative is better than
  baseline): surprisal -290.6, best representation layer -198.1, best
  logit lens -298.9 (layer 24). Gaze duration: surprisal -40.0, layer-2
  representation -57.2.
- Combining representations with surprisal improves on representations
  but never significantly on the scalar alone.
- Mixed models give the same picture with fewer significant effects.

## What the full text qualifies

- Up to 1.3B parameters; mean pooling of subword states; scale-dependent
  MSE, so magnitudes are not comparable across measures.

## For readcost (used / tested / candidate)

Not cited. Two points bear on docs/evaluation.md "Reading-time model":

- readcost predicts total reading time, the measure where this paper finds
  surprisal clearly helps on Provo (Delta MSE -291 against its baseline).
  readcost found that adding SmolLM2-135M surprisal made Provo error worse
  (10.3 to 15.8 ms/word). The disagreement is worth checking before the
  conclusion "surprisal adds nothing" is relied on: differences in
  word-to-token alignment, the error metric (readcost scores per-text mean
  ms/word, which averages away word-level gains) or overfitting of the
  trees to OneStop are candidate causes.
- Hidden-state probes are not a fit for readcost's no-torch shipping
  model; the paper's own result says they buy least for total reading time.

## Open questions

- Would a per-word error metric, rather than per-text mean, show the
  surprisal gain readcost's text-level metric hides?
