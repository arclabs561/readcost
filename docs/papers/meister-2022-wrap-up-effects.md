# Analyzing Wrap-Up Effects through an Information-Theoretic Lens

Clara Meister, Tiago Pimentel, Thomas Hikaru Clark, Ryan Cotterell, Roger
Levy. 2022. ACL 2022 (short paper); arXiv
[2203.17213](https://arxiv.org/abs/2203.17213) (v2, January 2024).

Read: full (body, ethics, appendix A preprocessing, appendix B figure
captions). Title and authors match. Results are given in plots; the text
gives directions, not numbers.

## Claim

Reading times on sentence- and clause-final words (wrap-up effects) are
predicted by the information content of the preceding sentence (summed
surprisal, or surprisal raised to a power k), beyond the usual per-word
predictors, while the same quantities add little for sentence-medial
words. Wrap-up time is therefore not a constant end-of-sentence cost.

## Method and data

- Natural Stories, Brown, UCL self-paced reading; Provo, Dundee, UCL eye
  tracking (total fixation time; regression time in the appendix).
- Clause-final words: all words ending in punctuation.
- Baseline: surprisal, unigram log-frequency, length and their
  interaction for the current and previous word (two back for self-paced).
  Added predictor INF(k) = sum of s(w)^k over the preceding sentence
  (k = 0 is length). Delta log-likelihood on held-out folds.

## Results (numbers that matter)

- Residuals of a model fit on sentence-medial words are skewed and
  off-centre for clause-final words (figure 1).
- For clause-final words, INF(k) with k > 0 improves fit more than
  length alone (k = 0), and k > 1 usually more than k = 1 (often within
  standard error). Effects are stronger for eye tracking than self-paced
  reading and stronger still for regression time. Sentence-medial words
  gain little.
- Smaller corpora (UCL, Provo) give noisy or null gains.

## What the full text qualifies

Correlational; the authors make no causal claim. Clause ends are
approximated by punctuation.

## For readcost (used / tested / candidate)

Not cited. Candidate for the reading-time model (src/readcost/readtime.py).
readcost's features mark closing punctuation on the word and its
neighbours, which can only add a fixed wrap-up cost. This paper says the
cost at a clause end grows with how much information the clause carried,
and that even length (k = 0) helps. A cheap test: add, for words ending in
punctuation, the number of words (or summed log-frequency) since the last
clause boundary, and check OneStop and Provo error. That would also give
the model a sentence-length effect the current word-local features lack,
relevant to the hotspots feature and to long-dependency-heavy sentences.

## Open questions

- Whether a length-only INF(0) feature captures most of the gain for
  readcost, given that surprisal added nothing to its trees.
