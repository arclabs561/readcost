# StyleDistance: Stronger Content-Independent Style Embeddings with Synthetic Parallel Examples

Justin Qiu, Zachary Horvitz, Jiacheng Zhu, Ajay Patel, Marianna Apidianaki,
Kathleen McKeown, Chris Callison-Burch. 2024 (arXiv v2 February 2025).
arXiv [2410.12757](https://arxiv.org/abs/2410.12757). The PDF names no venue.

Read: full (arXiv v2, 22 pages: body, limitations, appendices A to I,
including the per-feature Table 11). Title and authors match the arXiv ID.
Tables were checked against a layout-preserving extraction.

## Claim

Style embeddings trained on authorship triplets (same author = same style)
leak content. Training instead on LLM-generated near-paraphrase pairs that
differ in one style feature gives embeddings that are more independent of
content and do better on style benchmarks and downstream tasks.

## Method and data

- SynthSTEL: GPT-4 writes 100 positive/negative paraphrase pairs for each of
  40 style features in 7 groups. Topics come from random C4 sentences, and
  the prompt varies sentence length, point of view, tense and sentence type
  (AttrPrompt). Features include active voice, nominalizations, long words,
  complex sentence structure, function words, formal tone, contractions,
  fluency and emoji. Split 90/10.
- Data check: 10 graduate-student annotators per item judged the feature
  present or absent correctly 92% of the time; Krippendorff's alpha 0.55.
  Content similarity within pairs was 0.88 (natural baseline 0.50).
- Triplets (about 320K): anchor and positive share the feature on different
  topics; the negative is the paraphrase without the feature, half the time
  of the anchor itself. RoBERTa-base with LoRA, triplet loss, margin 0.1.
  StyleDistance mixes 50% synthetic with 50% of the Wegmann et al. 2022
  Reddit triplets; StyleDistance-Synth uses only synthetic data.
- Evaluation: STEL and STEL-or-Content (five features: formality,
  complexity, number substitution, contractions, emoji), synthetic STEL
  instances for all 40 features, PAN 2011 to 2015 authorship verification,
  and the style-transfer discrimination set from Patel et al. 2022.

## Results (numbers that matter)

- STEL-or-Content average accuracy (Table 3): roberta-base 0.05, LUAR 0.03,
  LISA 0.03, Wegmann et al. 0.22, StyleDistance 0.29, StyleDistance-Synth
  0.31. STEL average: roberta-base 0.90 (untuned), StyleDistance 0.87.
- The "complex" (simple vs complex sentence) feature stays hard for every
  model: STEL-or-Content 0.25 to 0.27 at best.
- Ablation (Table 4): with the benchmark's features removed from training,
  Synth keeps 65% of its STEL-or-Content score; with 15 related features
  removed, 50%.
- On synthetic probes (Table 11), the Wegmann et al. embedding scores 0.07
  STEL-or-Content on nominalizations, 0.16 on complex sentence structure and
  0.07 on active voice. StyleDistance scores near 1.0, but it was trained on
  the same generator's train split.
- Authorship verification ROC-AUC average: LISA 0.57, Wegmann 0.56,
  StyleDistance 0.64. Style-transfer discrimination accuracy: humans 0.37,
  LUAR 0.38, StyleDistance 0.46.

## What the full text qualifies

- The best content-independence score on natural data is still 0.29 to
  0.31: on most STEL-or-Content items, every model prefers the paraphrase
  with the same content over the text in the same style.
- The near-perfect per-feature scores come from the same LLM's own test
  split, so they measure fit to GPT-4's idea of each feature rather than to
  natural text.
- Features are sentence-level only; the authors list multi-sentence style as
  future work. Some features (sarcasm, articles) cannot be fully removed from
  the negative example, so pairs differ in degree.
- The authors observe repetitive patterns and possible biases in the
  synthetic data. The style-transfer gains in Appendix I are within a few
  points of the baseline ("performs comparably").

## For readcost (candidate, not cited)

readcost's docs do not cite this paper. Style embeddings measure how a text
is written, not what it costs a reader, so this is not a candidate rule.
Two possible uses:

- Paired rewrites (docs/evaluation.md, "Paired rewrites"): the report
  concludes that model rewrites shift word choice rather than the
  constructions readcost counts. A content-independent style distance
  between each original and its rewrite would measure that shift directly
  and would let the report check whether style distance tracks the
  predicted ms-per-word rise. The 0.29 STEL-or-Content ceiling means
  content similarity would still leak into the distance.
- The probes show that general style embeddings barely represent
  nominalization, active voice or sentence complexity, which are close to
  readcost's own detectors. That supports keeping those detectors as
  explicit parse rules rather than replacing them with an embedding.

No readcost claim conflicts with the paper.

## Open questions

- Does style distance from a human original correlate with the reading-time
  model's per-word increase across the ten rewriters?
- Would the synthetic probe method (pairs that differ in one feature) give
  readcost a cheap controlled test set for each detector?
