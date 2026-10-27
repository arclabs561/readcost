# CARE: Confounder-Aware Aggregation for Reliable LLM Evaluation

Jitian Zhao, Changho Shin, Tzu-Heng Huang, Satya Sai Srinath Namburi GNVV
and Frederic Sala (University of Wisconsin-Madison). 2026. ICML 2026
(PMLR 306, per the PDF footer). arXiv 2603.00039 (read v2, 8 Sep 2026).
https://arxiv.org/abs/2603.00039

Read: main text in full (sections 1 to 7, Tables 1 to 4, Figures 2 to
4); appendix sections on datasets (E.1), the quality-factor ablation
(E.8) and the synthetic confounding experiments (E.9) read; the proofs and
derivations (Appendices C and D), extended related work (B) and the
remaining experiment details skimmed or not read. Title and authors match
the arXiv id.

## Claim

LLM judges in an ensemble make correlated errors because shared hidden
factors (verbosity, style, training artifacts) push all of them the same
way. Majority vote and averaging assume independent judges and so can
amplify those errors. CARE models judge scores as driven by one latent
quality factor plus latent confounders, separates them without
ground-truth labels, and aggregates by the quality factor alone.

## Method and data

From the judges' score matrix, CARE estimates the precision matrix and
splits it into a sparse part (direct judge-to-judge dependence) and a
low-rank part (shared latent factors). CARE-SVD (continuous scores,
jointly Gaussian) takes the leading eigenvector of the low-rank part as
the quality direction. CARE-Tensor (discrete or preference data, binary
quality and binary confounder) uses the sparse graph to split judges into
three conditionally independent groups and recovers the latent states by
decomposing a third-order moment tensor. Choosing which latent factor is
"quality" needs a symmetry-breaking rule: by default, the factor with the
largest shared variance; alternatives are a small human-rated anchor set
or a balanced-loading rule. Theory: identifiability and finite-sample
recovery under stated conditions. Experiments: 11 to 20 open LLM judges
(0.6B to 14B parameters) on 12 public benchmarks (scoring: ASSET,
FeedbackQA, Review-5K, Summarize, UltraFeedback, Yelp; classification and
preference: Chatbot Arena, CivilComments, PKU-Better, PKU-Safer, SHP,
Summarize), mostly 5,000 sampled items each; baselines majority vote,
averaging, weak-supervision models, Dawid-Skene, GLAD and MACE.

## Results (numbers that matter)

- Scoring tasks (MAE): CARE-SVD lowest on all six, up to 26.8% lower than
  majority vote (UltraFeedback); on average 17.4% better than averaging
  and 12.8% better than majority vote.
- Classification and preference (accuracy, read from the extracted
  Table 2): best on 5 of 6. Chatbot Arena 0.580 against 0.551 for the
  best baseline, near chance for a pairwise task; CivilComments 0.778
  against 0.739; Summarize 0.814 against 0.718. On PKU-Safer MACE (0.735)
  beat both CARE variants (0.690, 0.731).
- The inferred confounders correlate with response length (Spearman about
  0.49 on Review-5K) and with SMOG readability (about -0.38), that is,
  judges respond to surface features of the text.
- Robustness: under injected "beauty" (emoji, formatting) and "authority"
  (fake citation) edits, CARE-SVD changed its aggregate least (MAE 0.375
  and 0.233). Against adversarial tokens such as "Solution" or ":",
  CARE-Tensor cut false-positive rates from about 0.44 to 0.67 (majority
  vote) to 0.00 to 0.50.

## What the full text qualifies

Identifying the quality factor rests on the assumption that quality is
the strongest shared variation across judges; Appendix E.8 supports it on
the six scoring datasets only by comparing factors in hindsight on the
test set. When a confounder dominates the pairwise structure, CARE-SVD
falls to chance (synthetic regime E.9b) and only the tensor version
survives. Results are reported as means with standard deviations over
runs of the same data, not across datasets, and the judges are small open
models, not frontier models. Several baseline-to-CARE gaps on the
classification tasks are a few points.

## For readcost (candidate; not cited)

Two links to readcost:

- Rater aggregation (docs/evaluation.md, "Ten raters"). The ten-rater
  table shows the largest shared difference among readcost's raters is
  leniency: Llama 4 Maverick and MiniMax M3 accept far more findings than
  the rest. That is exactly the kind of shared factor CARE's default rule
  would mistake for quality if it were the dominant direction. The docs
  handle it by dropping the two raters after seeing their labels; CARE
  would instead model it, but only with thousands of items, not 210, and
  it still needs human anchors to know which factor is quality. Neither
  route replaces a human-labelled subset. No doc claim contradicted.
- Judges and readability. CARE finds LLM judges' errors track length and
  SMOG grade. readcost's model raters judge whether a sentence costs
  readers time; if their labels are driven by the same surface cues
  (longer sentences, longer words look "costly"), rater acceptance would
  partly measure sentence length rather than the construction a rule
  names. docs/evaluation.md already records a second label for whether
  the construction is present, which helps separate the two; correlating
  rater acceptance with sentence length on the 210 findings would test
  this directly.

## Open questions

- Is rater leniency the leading factor in readcost's 210 x 10 label
  matrix, and does acceptance correlate with sentence length after
  controlling for rule? Both are cheap to compute from existing labels.
