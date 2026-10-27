# Learning Universal Authorship Representations

Rafael A. Rivera-Soto, Olivia Elizabeth Miano, Juanita Ordonez, Barry Y.
Chen, Aleem Khan, Marcus Bishop, Nicholas Andrews. 2021. EMNLP 2021, pages
913 to 919. ACL Anthology
[2021.emnlp-main.70](https://aclanthology.org/2021.emnlp-main.70).

Read: full (7-page short paper, all sections and Tables 1 to 3). Title,
authors and venue match the Anthology ID (PDF metadata and footer). The
model is known elsewhere as LUAR; the paper itself does not use that name.

## Claim

Neural authorship representations trained in one domain do not in general
transfer to others. Reddit-trained models transfer best, which the authors
attribute to more training authors and more topic diversity per author.

## Method and data

- Model: SBERT encodes w excerpts of 32 subword tokens (w drawn from 1 to
  16 at training time), then self-attention across excerpts, max pooling
  and a linear projection to 512 dimensions. Supervised contrastive loss
  (temperature 0.01) over collections by the same author.
- Domains: Amazon reviews (100K training authors with at least 100 reviews,
  35K for evaluation); fanfiction.net stories from PAN 2020 (16,456
  evaluation authors with exactly two stories); Reddit comments (1M training
  authors with at least 100 comments; evaluation set from Andrews and
  Bishop 2019, later in time than training).
- Metrics: recall at 8 and mean reciprocal rank when ranking targets for
  each query. Baselines: a convolutional version of the model and TF-IDF
  over words.
- Experiments: zero-shot transfer across domains, number of training
  authors, multi-domain training, and random subword masking (p 0.05 to
  0.60) on Amazon.

## Results (numbers that matter)

- Table 1 (R@8, proposed model; rows evaluation, columns training): trained
  on Reddit, 65.6 on Reddit, 68.9 on Amazon, 41.6 on fanfiction. Trained on
  Amazon, 23.7 on Reddit and 82.5 on Amazon. Trained on fanfiction, 12.1 on
  Reddit and 50.9 on fanfiction.
- A Reddit model trained on only 100K authors scores 36.7 on fanfiction,
  close to the Amazon model's 36.35; adding Amazon authors with fewer
  reviews gains about 1%.
- Adding Reddit to training improves every evaluation (best Amazon 84.8,
  best fanfiction 57.5); adding fanfiction always hurts transfer.
- Random masking helps transfer from Amazon a little (Reddit R@8 up 2.6
  points) and costs in-domain performance.

## What the full text qualifies

- The topic-diversity explanation is inferred from the gap between the
  neural models and TF-IDF, which the authors treat as a proxy for a topic
  model; there is no direct measure of topic.
- The authors conclude that neural authorship models do not learn
  universal authorship features and that training data must be controlled
  to get the invariances wanted. They leave separating content from style
  to future work.
- Later work (Qiu et al. 2024, StyleDistance) finds that this kind of model
  scores 0.03 on STEL-or-Content, that is, it follows content over style.

## For readcost (not applicable)

readcost's docs do not cite this paper. readcost's README says it does not
tell who wrote a text, and LUAR is an authorship model that also encodes
content, so it is a poor measure of whether a rewrite changed style. If
readcost ever needs a style distance for the paired-rewrite tests in
docs/evaluation.md, a content-independent model (StyleDistance) fits
better.

## Open questions

None for readcost.
