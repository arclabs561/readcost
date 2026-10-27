# Surprise! Uniform Information Density Isn't the Whole Story: Predicting Surprisal Contours in Long-form Discourse

Eleftheria Tsipidi, Franz Nowak, Ryan Cotterell, Ethan Wilcox, Mario
Giulianelli, Alex Warstadt. 2024. EMNLP 2024, pages 18820 to 18836. ACL
Anthology [2024.emnlp-main.1047](https://aclanthology.org/2024.emnlp-main.1047).

Read: full (body, future work, limitations, appendices B to E on variables,
transition predictors and dependent-variable definitions). Results are
reported in bar charts (Figures 4 to 7); this note gives their
significance tests, not read-off magnitudes. Title, authors and venue match
the Anthology ID.

## Claim

Surprisal across a document is not flat around a constant rate, and part
of its rise and fall is predictable from where a token sits in the
document's discourse structure (the "Structured Context Hypothesis").
Rhetorical Structure Theory trees predict it better than paragraph and
sentence boundaries.

## Method and data

- Texts: 347 Wall Street Journal documents from the English RST Discourse
  Treebank (train split) and 256 Spanish specialist documents from the
  Spanish RST Treebank.
- Surprisal per token from Yarn-Llama-2-7B-64K (English, full document as
  context) and a Spanish Mistral 7B.
- Dependent variables: document-conditioned surprisal; its rolling mean
  over 3, 5 or 7 tokens; and the difference between document-conditioned
  and sentence- or clause-conditioned surprisal (a pointwise mutual
  information).
- Baseline predictors: token length in characters and the previous token's
  surprisal. Added predictor groups, from RST trees or from paragraphs and
  sentences: relative position in the unit, distance to the nearest
  boundary, position of the unit within its parent, and parser
  push/pop counts.
- Bayesian linear regression, 5-fold cross-validation; gain = drop in
  held-out MSE over the baseline; paired permutation tests.

## Results (numbers that matter)

- Every structural predictor group lowers held-out error over the baseline
  (p < 0.001), in both languages.
- English: relative position within a discourse unit is the best RST
  group; Spanish: position of the unit within its parent is best for
  document surprisal.
- A monotonic relative-position effect fits better than distance to the
  nearest boundary.
- RST predictors beat paragraph-and-sentence predictors for document
  surprisal (p < 0.001); paragraph-and-sentence predictors are better for
  surprisal measured within the sentence.

## What the full text qualifies

- The authors state that structure accounts for "only a small portion" of
  the deviations from a constant rate (their phrase), visible in Figure 1.
- The dependent variable is a language model's surprisal, not reading time
  or any reader measure. Explanations such as keeping interest or easing
  comprehension with repetition are listed as future hypotheses, untested.
- Linear models only; units are model tokens; two languages, one news
  genre in English.
- The paper argues that UID is underspecified: it does not say which
  surprisal rates count as uniform or within which context.

## For readcost (candidate background; not cited)

readcost's docs do not cite this paper. It bears on "Model signals" in
docs/evaluation.md (around line 1100), which says that the standard
deviation of surprisal, labelled "the uniform information density idea",
tracks teachers' sentence difficulty ratings a little:

- The label is fair as shorthand, but this paper shows that surprisal
  spread within a document partly reflects discourse position (where a
  token falls in its paragraph or rhetorical unit), not only how hard the
  wording is. readcost's CEFR-SP test scores single sentences, so this
  confound does not affect it. Applied to whole documents, for example in
  the paired-rewrite or model-answer comparisons, surprisal spread would
  mix structure with difficulty. Comparing two texts with different
  paragraphing would need that controlled.
- The paper gives no evidence that uneven or even surprisal changes reading
  cost, so it supports neither direction for a readcost rule.

No mismatch with readcost's docs.

## Open questions

- If readcost adds a surprisal-spread signal at document level, should it
  first regress out position within the sentence and paragraph?
