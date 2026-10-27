# Detection and Measurement of Syntactic Templates in Generated Text

Chantal Shaib, Yanai Elazar, Junyi Jessy Li, Byron C. Wallace. 2024. EMNLP
2024; arXiv [2407.00211](https://arxiv.org/abs/2407.00211) (v2, 6 October
2024).

Read: full (arXiv v2, 16 pages: body, limitations, appendices A to E with
tables 5 to 13). Title and authors match. Tables were read from a
layout-preserving extraction.

## Claim

Syntactic templates (frequent part-of-speech n-grams) are more common in
model outputs than in human references for summarization, are mostly
learned in pre-training (75% of OLMo's templates appear in Dolma, against
34% of non-template sequences), and survive fine-tuning and RLHF.

## Method and data

- A template is a POS n-gram (n = 4 to 8) among the top 100 most frequent
  in a corpus (one model's outputs on one task). spaCy tagger, Penn tags,
  `diversity` package.
- Measures: CR-POS (gzip compression ratio of the concatenated POS
  sequence; higher means more repetitive), template rate (share of texts
  with at least one template) and templates per token.
- Models: OLMo-7B Instruct, Mistral-7B, Alpaca 7B and 13B, Llama-2 7B to
  70B chat, Llama-3-70B Instruct, GPT-4o. Tasks: open generation,
  Cosmopedia prompts, summarization of Rotten Tomatoes, CNN/DM, Cochrane,
  BooookScore. 500 samples, greedy decoding, prompt "Write a short summary".

## Results (numbers that matter)

- Rotten Tomatoes (n = 6): human references 46.4% with a template, 0.040
  per token (references average 25 words); models 89 to 99.6%, 0.041 to
  0.151 per token (outputs 93 to 204 words).
- CNN/DM: references 36.0% (0.013); models 83 to 97% (0.024 to 0.042).
- Cochrane: references 83.3% (0.049); models 67 to 99.7%; Cochrane reviews
  are formulaic by design, so humans are high too.
- The text says 38% for humans on Rotten Tomatoes; that figure averages
  references (46.4%) with input documents (29.3%).
- Larger models do not have fewer templates; templates per token rise
  with size in Llama.
- POS ("style") memorization finds 6.4% of sampled training sequences vs
  5.3% for exact match.

## What the full text qualifies

- Every measure is over a corpus of outputs, not within one text.
- No claim about readers or reading time; the paper says it makes no claim
  that templates detect model text.
- Template rate depends on text length; templates per token is the
  length-normalized measure, and on Rotten Tomatoes most models are close
  to the reference on it (0.041 to 0.070) except the Llama models.

## For readcost (used / tested / candidate)

Used: `readcost corpus` (src/readcost/corpus.py: N = 6, TOP = 100,
CR-POS, template rate, templates per token) and the opt-in
repeated-frame rule. Tested: docs/evaluation.md "Repetition across texts".

Citation accuracy:

- docs/research.md lines 33-35 and features.py lines 135-138 ("count
  templates across many outputs of one model, not within one document ...
  no claim about reading time"): accurate.
- docs/evaluation.md lines 881-883 ("95% of model outputs against 46% of
  human references ... partly an effect of length"): accurate to table 3
  and the paper's own length caveat.
- corpus.py line 20 ("N = 6, as in Shaib et al.'s main results"): accurate.
- README.md line 183 cites Shaib for repeated-frame as a construction
  models use more than people. Accurate only at corpus level; the
  within-document rule is readcost's own extension, which features.py
  already says.

## Open questions

- readcost's own HC3 test found current models no more templated than
  human answers; Shaib's gap was largest for short human references in
  summarization. A length-matched comparison would separate the two.
