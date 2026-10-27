# Same Author or Just Same Topic? Towards Content-Independent Style Representations

Anna Wegmann, Marijn Schraagen, Dong Nguyen. 2022. 7th Workshop on
Representation Learning for NLP (RepL4NLP), ACL (venue as cited by later
work; the arXiv PDF names none). arXiv
[2204.04907](https://arxiv.org/abs/2204.04907).

Read: full (arXiv v1: body, limitations, ethics, appendices A to F).
Title and authors match the arXiv ID. Some appendix tables extracted as
scrambled number columns; the main tables (2, 3) and all prose were read.

## Claim

Style embeddings trained on authorship verification (same author = same
style) also learn topic. Choosing the different-author example from the
same Reddit conversation, and training with a triplet (anchor, same author,
different author), gives embeddings that prefer style over content more
than domain-level or no content control does.

## Method and data

- Reddit 2018 sample from 100 subreddits via ConvoKit: 210K training
  triplets per condition, 45K dev and 45K test, split by author 70/15/15.
- Two setups: AV (pairs, contrastive loss) and CAV (triplets, triplet loss).
  Three content-control levels for the different-author utterance: same
  conversation, same subreddit, or random.
- Siamese BERT and RoBERTa models via Sentence-Transformers, margin 0.5,
  three seeds; 5 of 18 models failed to learn and were retrained.
- Evaluation: AV AUC and CAV accuracy; STEL (formal/informal,
  complex/simple, contractions, number substitution); and a new task,
  STEL-or-Content, in which the wrong answer is a paraphrase of the anchor
  in a different style.
- Agglomerative clustering (7 clusters) of 14,756 test utterances to see
  what the embedding groups together.

## Results (numbers that matter)

- AV/CAV (Table 2): every model does best on the content-control level it
  was trained with. The conversation test set is the hardest (AUC about
  0.69 against 0.77 to 0.79 on the random test set).
- STEL (Table 3): untuned RoBERTa scores 0.80 overall; every fine-tuned
  model scores lower (0.71 to 0.73). The complex/simple dimension drops from
  0.73 to 0.46 to 0.69.
- STEL-or-Content: untuned RoBERTa 0.05; CAV with conversation control
  0.42, the best; all are below the 0.5 random baseline.
- Error analysis: 50 of 55 complex/simple STEL items that fine-tuned
  models got wrong, and 29 of 41 they newly got right, contain ambiguities
  such as typos, changed content or unnatural wording.
- Clusters separate mostly on surface marks: missing final punctuation
  (97% in one cluster vs 37% elsewhere), lowercase "i", curly vs straight
  apostrophes (90% vs 0%), line breaks. 46.2% of same-author pairs share a
  cluster against 20.1% by chance.

## What the full text qualifies

- The abstract's "better at representing style independent from content"
  is relative: the best model still picks the same-content paraphrase on
  most STEL-or-Content items, and fine-tuning lowered plain STEL accuracy.
- The features the authors could verify by hand are typographic (apostrophe
  type, casing, punctuation), not syntax. They note that more complex
  features may be present but were not shown.
- The complex/simple STEL data is noisy enough that model scores on it are
  hard to read.
- Same-conversation control cannot transfer to non-conversation corpora,
  and content still helps authorship within a conversation ("my wife" vs
  "my husband").

## For readcost (not applicable now; background for any style signal)

readcost's docs do not cite this paper. It is about authorship style on
Reddit, not reading cost. Its relevance is a warning for any future
"style" signal in readcost's evaluation:

- An embedding trained on authorship mostly encodes punctuation, casing and
  apostrophes. If readcost ever compares model and human text by style
  embedding (for example in "Model answers written from scratch" or "Paired
  rewrites" in docs/evaluation.md), differences may come from typography
  and Markdown habits rather than sentence construction.
- The complex/simple dimension, the one closest to readcost's concern, is
  the one that fine-tuned style models handle worst and the one with the
  noisiest benchmark items.

No readcost claim conflicts with the paper.

## Open questions

- None specific to readcost beyond the StyleDistance note
  (qiu-2024-styledistance.md), which supersedes this model.
