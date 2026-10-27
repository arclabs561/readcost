# Pushing on Text Readability Assessment: A Transformer Meets Handcrafted Linguistic Features

Bruce W. Lee, Yoo Sung Jang, Jason Hyung-Jong Lee. 2021 (arXiv v2 June
2024). arXiv [2109.12258](https://arxiv.org/abs/2109.12258). The arXiv PDF
names no venue; the authors' later paper (arXiv 2302.13139) cites it as
EMNLP 2021, pages 10669 to 10686.

Read: full (arXiv v2: body, limitations discussion, appendices A to H
including feature definitions, preprocessing, hyperparameters and feature
sets; the 255-feature tables were skimmed, not checked row by row). Title
and authors match the ID; the PDF header lists Jang before Bruce Lee,
while the arXiv listing and the request give Lee, Jang and Lee.

## Claim

Feeding a transformer's class probabilities, together with 255 handcrafted
linguistic features, into a classical classifier (random forest, XGBoost)
beats either alone on readability classification. Three new
"advanced semantic" features from LDA topic distributions add
information beyond the existing features.

## Method and data

- Datasets: WeeBit (5 levels, downsampled to 625 per class), OneStopEnglish
  (3 levels, 189 articles each rewritten at every level), Cambridge (5 exam
  levels, 60 per class).
- Features (LingFeat toolkit): LDA topic features (richness, clarity,
  noise, topic count) from models trained on Wikipedia, WeeBit and
  OneStopEnglish; entity density and entity grid; phrase counts and parse
  tree shape; POS counts; type-token ratios and MTLD; age of acquisition;
  SubtlexUS word frequency; shallow counts; five formulas. Feature
  extraction drops stopwords, words under 3 characters and special
  characters.
- Models: BERT, RoBERTa, BART, XLNet (base, 512 tokens, 3 epochs); SVM,
  random forest, XGBoost, logistic regression. Hybrid = neural soft labels
  plus a feature set, classified by a non-neural model. Stratified 5-fold
  (80/10/10), metrics averaged.

## Results (numbers that matter)

- Transformers alone (Table 2), accuracy: WeeBit 0.88 to 0.90;
  OneStopEnglish BERT 0.80, RoBERTa 0.965, BART 0.968; Cambridge 0.57 to
  0.68.
- Feature models alone (Table 3): WeeBit 0.62 to 0.68, OneStopEnglish 0.71
  to 0.78, Cambridge 0.63 to 0.69.
- Hybrids (Table 5): RoBERTa-RF-T1 0.990 on OneStopEnglish (BERT-GB-T1
  0.982, up 0.181 on BERT alone); 0.902 to 0.905 on WeeBit, a gain of
  0.002 to 0.016 over the transformer; Cambridge gains about 0.08 to 0.11.
- Single feature subgroups: word familiarity (SubtlexUS) and age of
  acquisition are in the top seven on all three corpora; traditional
  formulas lead on OneStopEnglish and Cambridge with logistic regression.
- With 750 WeeBit training passages, BERT-GB-T1 reaches 0.858.

## What the full text qualifies

- The 99% headline comes from one parallel corpus; on the larger WeeBit
  set the hybrid adds under 2 points, and BART gains almost nothing.
- The authors ran no cross-corpus evaluation and say so, noting that
  domain overfitting is a common problem in readability assessment.
- Not discussed in the paper (my inference from the method): OneStopEnglish
  has three versions of each article, and a stratified k-fold over texts can
  place versions of the same article in training and test folds. The
  OneStopEnglish topic features are also trained on OneStopEnglish. Either
  could inflate the 0.99 figure.
- Labels are publisher or exam levels, not measured reading behaviour.

## For readcost (candidate; not cited)

readcost's docs do not cite this paper. It bears on "Text difficulty
benchmarks" in docs/evaluation.md, which uses OneStopEnglish paired across
levels:

- readcost's own result, that sentence length and word length separate the
  OneStopEnglish levels best, agrees with this paper's finding that
  word-familiarity, age-of-acquisition and formula features are the most
  useful single subgroups.
- The paper's level classification accuracy is not a target for readcost,
  which reports constructions and reading time rather than a grade. If
  readcost ever trains anything on OneStopEnglish (the reading-time model
  is trained on OneStop Eye Movements paragraphs, split by article), it
  should keep the split by article; this paper's random fold split is the
  pattern to avoid.
- LingFeat's 255 features are a ready source if readcost wants a stronger
  feature baseline than words per sentence and mean word length.

No readcost claim conflicts with the paper.

## Open questions

- Does the 0.99 hold with folds split by article?
