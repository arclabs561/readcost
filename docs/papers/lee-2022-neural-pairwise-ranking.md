# A Neural Pairwise Ranking Model for Readability Assessment

Justin Lee, Sowmya Vajjala. 2022. arXiv
[2203.07450](https://arxiv.org/abs/2203.07450) (v1, 14 March 2022). The
arXiv PDF names no venue; the venue was not checked.

Read: full (body, limitations, ethics; the paper has no appendix). Title
and authors match. Not the same paper as
`lee-2023-pairwise-readability.md` (Bruce W. Lee and Jason Lee).

## Claim

Ranking texts by reading level with a BERT model trained on pairs from
the same article (NPRM) matches classification and regression within a
corpus and transfers better across corpora and, with multilingual BERT,
across languages without target-language training.

## Method and data

- Training on Newsela-En (9,565 texts, 1,911 articles) or OneStopEnglish
  (189 articles x 3 levels); test also on Vikidia En/Fr (new parallel
  dataset of 6,165 articles x 4 versions) and Newsela-Es.
- Pairs only within an article's versions ("slug"), at most 3 levels per
  article. Compared with BERT and embedding-based classifiers, regression
  and SVMRank. Metrics: NDCG, Spearman, Kendall, share of articles ranked
  fully correctly (RA). 5-fold CV.

## Results (numbers that matter)

- OneStop within corpus: NPRM RA 0.979, Spearman 0.981; BERT classifier
  RA 0.825; regBERT 0.905.
- Trained on Newsela, tested on OneStop: NPRM Spearman 0.931, RA 0.878;
  regBERT 0.706 and 0.561.
- Zero-shot Spanish (Newsela-Es): NPRM RA 0.864; French Vikidia RA 0.811.

## What the full text qualifies

- Rankings, not levels; scores are not on any reading-level scale.
- All data are news or encyclopedia text; difficulty labels are editorial
  levels, not reader measurements.

## For readcost (used / tested / candidate)

Not cited. Supports a design choice readcost already makes: comparing two
versions of the same text (`readcost compare`, the paired-rewrite and
OneStop-level evaluations in docs/evaluation.md) is more robust than
absolute thresholds, because relative judgments within the same content
transfer across corpora where absolute scores fail (regBERT's collapse on
OneStop when trained on Newsela). It argues for keeping verdict
thresholds conservative and leaning on paired comparison when judging
rewrites.

## Open questions

None specific.
