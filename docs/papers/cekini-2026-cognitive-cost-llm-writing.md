# The Cognitive Cost of LLM Writing: A Reading-Time Comparison with Human Text

Kamer Cekini, Elisabetta Biondi, Chiara Boldrini, Andrea Passarella, Marco
Conti. 2026. arXiv [2610.23715](https://arxiv.org/abs/2610.23715) (v1, 16
October 2026).

Read: full (10 pages: body, tables I to VIII, conclusion with its
limitation paragraph). Title and authors match. No appendix.

## Claim

A RoBERTa model trained on eye-tracking data predicts that LLM rewrites of
news articles take slightly less time in total but more time per word than
the human originals. The per-word rise goes with longer, rarer words and
higher lexical diversity; contextual predictability (surprisal) moves the
other way.

## Method and data

- Target: for each word occurrence, the mean over participants of the
  summed fixation durations on that word (total reading time). Averaging
  over all participants who read the text implies that a skip counts as 0;
  the paper does not say so in words.
- Training: OneStop (360 native readers, 30 Guardian articles, 162
  paragraphs; split 18/6/6 articles) plus GECO (monolingual English
  readers only) and MECO (L1 English readers only): 78,881 training word
  occurrences. Provo (55 passages, 84 readers, 2,743 words) is an external
  test only.
- Models: ridge, random forest, CatBoost and an MLP on 15 features
  (word length, digit, hyphen, final punctuation, index and relative
  position in the paragraph, Zipf frequency, stopword, the same length,
  frequency and punctuation facts for the previous and next word, and
  GPT-2 surprisal); four transformer encoders fine-tuned per word.
  Selected by text-level MAE (mean absolute error of mean ms per word per
  text) on OneStop validation, 50 Optuna trials each.
- Paired corpus: 500 CCAT50 Reuters articles (10 per author), rewritten by
  GPT-5.6 Terra with one prompt ("Cover the same facts ... in your own
  words"); 496 pairs after four refusals.
- Measures: predicted total and per-word time, word count, mean word
  length, mean wordfreq frequency, mean OPT-125M surprisal, MTLD.
  Two-sided Wilcoxon signed-rank with Bonferroni; Spearman correlations of
  per-pair relative changes.

## Results (numbers that matter)

- Text-level MAE, OneStop validation / test / Provo: RoBERTa-base 15.76 /
  15.00 / 16.09 (chosen); MLP 23.77 / 18.72 / 16.74; ridge 24.63 / 19.29 /
  21.10; random forest 23.60 / 18.96 / 16.47; CatBoost 27.85 / 21.49 /
  22.07. Observed means 192.84 (OneStop test) and 200.16 (Provo) ms/word.
- Rewrites vs originals (mean relative change): total time 117.1 to 115.6 s
  (-1.19%); per word 229.9 to 233.4 ms (+1.57%); words 511 to 496 (-2.66%);
  word length 4.95 to 5.25 (+6.06%); frequency -7.61%; MTLD 103 to 135
  (+31.8%); surprisal -6.51%. All p_adj < .01.
- Change in ms/word correlates with change in word length (rho .588),
  frequency (-.405), MTLD (.292), surprisal (.438). More shortening goes
  with a larger per-word rise (rho -.458).

## What the full text qualifies

- Effects are small: under 2% on either reading-time measure. The model's
  own error (15 ms/word) is several times the per-word difference; the
  authors say the evaluation does not establish small differences between
  individual texts and restrict claims to aggregates.
- One rewriting model, one prompt, news only.
- All reading times are predicted; the authors call for studies with
  people before any claim about effort or comprehension.

## For readcost (used / tested / candidate)

Used: the design of readcost's reading-time model (feature set, target,
text-level MAE, OneStop split, Provo as external test) and of the paired
rewrite test (docs/evaluation.md, "Paired rewrites" and "Reading-time
model"; src/readcost/readtime.py; scripts/reading_time_*.py).

Differences: readcost trains on OneStop only (no GECO or MECO) and leaves
GPT-2 surprisal out of the shipped model after testing it.

Citation accuracy:

- README.md lines 376-379: "a clearer rewrite can still take longer to
  read if it is much longer (Cekini et al. 2026 found exactly that for
  model rewrites)." Mismatch. Cekini's rewrites were shorter and took
  slightly less total time; what they found is that per-word time rose
  while total time fell. They report no case of a longer rewrite taking
  longer.
- docs/research.md lines 25-27: "Compressed rewrites can raise reading cost
  per word": accurate, with the effect size (+1.6%) worth stating.
- docs/evaluation.md line 580-582: "15.0 on OneStop test and 16.1 on Provo
  for their RoBERTa model and about 19 for feature models on OneStop test":
  accurate (feature models 18.7 to 19.3, CatBoost 21.5).
- docs/evaluation.md line 591: Provo 2,743 words, mean 200.16: accurate.
- docs/evaluation.md lines 541-543: longer words "as Cekini et al. found";
  surprisal rose, "the opposite of their result with OPT-125M": accurate.
- docs/evaluation.md lines 617-618: "less in total" does not generalize,
  "more per word" does: a fair reading of their claim.
- scripts/reading_time_prep.py line 15: "counting a skipped word as 0 ms,
  as Cekini et al. 2026 do": implied by their averaging over all readers of
  a text, not stated. Worth softening to "as their averaging implies".
- src/readcost/metrics.py lines 8-10: model rewrites score higher MTLD than
  the originals: accurate (+31.8%).
- README.md and readtime.py: "360 native readers of English newspaper
  paragraphs (OneStop)": accurate.

## Open questions

- Whether GECO and MECO training data, which Cekini added, would close
  part of readcost's gap to their feature models on OneStop test.
- Their RoBERTa's advantage on the external test is small: 16.09 on Provo
  against 16.47 for their random forest and 16.74 for the MLP.
  readcost's tree model reports 10.3 on Provo (docs/evaluation.md), well
  below all of Cekini's numbers; the difference in Provo keying or
  aggregation should be checked before reading it as a better model.
