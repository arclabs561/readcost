# Evaluating Text Generation Quality Using Spectral Distances of Surprisal

Zhichen Liu, Yongyuan Li, Yang Xu, Yu Wang, Yingfang Yuan, Zuhao Yang.
2025. Findings of EMNLP 2025, pages 2444 to 2463. ACL Anthology
[2025.findings-emnlp.132](https://aclanthology.org/2025.findings-emnlp.132).

Read: full (body, limitations, appendices A and B; the per-evaluator
Table 8 and the MT-Bench Table 9 were read as extracted numbers and labels,
and Figure 6's bar chart only through its printed r and p values). Title,
authors and venue match the Anthology ID. The paper calls the method FACE-2.

## Claim

Comparing the frequency spectrum of a text's per-token surprisal with that
of human text ranks larger generators above smaller ones more often than
raw surprisal, MAUVE, BERTScore and other metrics, and agrees better with
human preferences.

## Method and data

- Per text: token surprisal from an evaluator model, z-scored within the
  text, discrete Fourier transform, magnitude spectrum. Distance between
  the model-text and human-text spectra by spectral overlap, correlation,
  earth mover's distance, KL or JS.
- Generation: first 64 tokens of human texts as prompts (Wikipedia, BBC
  News, WritingPrompts, PubMedQA, LIMA in English; three Chinese sets),
  up to 1,024 generated tokens; about 5,000 texts per set. Generators:
  Qwen-2, Yi-1.5, Llama-3, Gemma-2 at two or three sizes. Evaluators:
  Pythia 410M and 1.4B, Llama-3 8B and 70B, Qwen-2 0.5B to 72B.
- Test 1: share of generator family by task cells in which the metric
  orders large over medium over small (chance 1/6).
- Test 2: MT-Bench human pairwise judgments of five chat models, with
  GPT-4's answers standing in for human text, compared by Bradley-Terry
  scores and Pearson correlation.

## Results (numbers that matter)

- Valid-cell ratio, English, mean over four evaluators (Table 1): FACE-1
  0.356, FACE-2 EMD 0.388 to 0.400, raw surprisal 0.363 with SD 0.143.
  Best single evaluator (Table 2): FACE-2 EMD 0.60, BERTScore 0.45, Zipf
  0.35, MAUVE 0.20, Self-BLEU 0.15, BARTScore 0.00.
- Raw surprisal's score depends on the evaluator: with small Qwen-2
  evaluators its valid ratio on Chinese is 0; with Qwen-2 72B it is 1.0.
  The authors read this as surprisal favouring generators of the
  evaluator's own size.
- z-scoring the surprisal before the transform mostly helps; using the full
  complex magnitude instead of the real part helps less than expected.
- MT-Bench: correlations with human Bradley-Terry scores over five models
  range from about -0.71 to 0.82; the highest has p = 0.09. No correlation
  is significant.

## What the full text qualifies

- "Agreement with human preferences" rests on five systems, with GPT-4
  answers as the reference, and no significant correlation. The authors
  trace the largest disagreement to Claude-v1's chat preambles, which
  people ignored and the metrics did not.
- The ground truth for test 1 is the assumption that a larger model in a
  family writes better text; no reader judged these generations.
- The authors say they do not know which visible features of a text
  (sentence structure, word choice) the spectrum reflects.
- Nothing in the paper measures reading time or comprehension.

## For readcost (candidate; not cited)

readcost's docs do not cite this paper. Two points bear on
docs/evaluation.md:

- "Paired rewrites" reports that mean surprisal from SmolLM2-135M rose in
  model rewrites, the opposite of Cekini et al.'s result with OPT-125M, and
  rules out memorization of famous essays. This paper's evaluator effect
  offers another explanation the report does not consider. Raw surprisal
  depends on how well the scoring model matches the generator. A 135M
  scorer reading text from much larger models may score that text as more
  surprising for reasons unrelated to readers. The report's own limit ("one
  scoring model for surprisal") is the right caveat; this paper says the
  effect can be large, enough to flip a ranking.
- "Model signals" finds that the spread of surprisal (its standard
  deviation, the uniform information density idea) tracks teacher
  difficulty ratings a little and mean surprisal does not. FACE-2's
  normalized spectrum is a richer version of that dynamic signal and would
  be cheap to add to `scripts/eval_model_signals.py`. Its validation is
  weak, though, so it is a signal to test, not one to adopt.

No mismatch with readcost's docs.

## Open questions

- Does readcost's paired-rewrite surprisal rise survive a larger scoring
  model, or z-scored surprisal?
- Does the spectral distance from human originals track the reading-time
  model's per-word rise across the ten rewriters?
