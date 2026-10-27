# Deep Learning to Detect Redundant Method Comments

Annie Louis, Santanu Kumar Dash, Earl T. Barr, Charles Sutton. 2018.
arXiv preprint (cs.SE). https://arxiv.org/abs/1806.04616 (v1).

Read: full (arXiv v1 PDF, 12 pages, title and authors checked; all
sections, tables 1 to 7, and the conclusion). The preprint is a blind
submission draft; some page layout text is out of order in the PDF but no
section is missing.

## Claim

A comment sentence that a model can predict from the method's code adds
little information. The authors call this "comment entailment" and score it
by the perplexity of the comment sentence under a sequence-to-sequence model
conditioned on the method. Low perplexity marks a candidate redundant
sentence. They are explicit that entailed is not the same as bad: a good
summary comment is entailed, and an unrelated comment is not entailed but is
bad.

## Method and data

- Corpus: the GitHub Java Corpus (14,785 projects); method-level comments
  immediately before a method, over 3M method/comment pairs, split into
  sentences with CoreNLP. Javadoc fields such as `@param` plus their text
  count as one sentence.
- Models: an LSTM language model over comments alone, and three LSTM
  seq2seq models that see the method compressed to 50 tokens (signature
  only; first and last 25 tokens; signature plus salient identifiers).
- Human check: 500 method/comment-sentence pairs from 45 projects sampled
  across popularity tiers, methods of at most 100 tokens; five M.Sc.
  students with at least two years of industry experience chose among
  entails, partly entails, does not entail, cannot decide, unrelated. One
  annotator was dropped for disagreeing with the rest.
- Javadoc analysis: mean perplexity per Javadoc tag over 73,430 sentences
  from the 45 projects.

## Results (numbers that matter)

- Test perplexity: comment-only LM 9.87; seq2seq with signature 8.26,
  begin-end 5.31, identifiers 6.00. Code roughly halves the perplexity of
  comments, so comments are partly predictable from code.
- Human agreement: pairwise Cohen's kappa 0.10 to 0.29 for the four kept
  annotators; all four agreed on 95 of 500, a majority existed on 292.
  Most confusion was between entails and partly entails, and the annotators
  split into two pairs with different defaults for ambiguous cases.
- On the 292 majority items, median perplexity rises from entails (2.30)
  to partly entailed (7.35) to not entailed (13.35); means are dominated by
  outliers (not entailed: mean 115.7, sd 266.7). No correlation
  coefficient, AUC or significance test is reported.
- Pascarella and Bacchelli categories (1,352 sentences): notice-usage has
  the lowest mean perplexity (14.2), then purpose-summary (19.3),
  purpose-rationale (20.9), purpose-expand (35.2). Standard deviations
  (about 25 to 33) exceed the gaps between means.
- Javadoc (Table 7): non-Javadoc sentences average 15.58. `@since` 1.44,
  `@throws` 2.50, `@inherit` 3.53, `@see` 6.13, `@deprecated` 6.41,
  `@param` 6.49, `@link` 9.56, `@code` 10.01, `@return` 13.28,
  `@linkplain` 15.91. Of 190 annotated pairs that at least one annotator
  marked as Javadoc, 180 were judged entailed or partly entailed.

## What the full text qualifies

- The abstract says Javadoc tags are "at least two times more predictable";
  in Table 7 that holds for `@param` and `@throws` and some rarer tags, not
  for `@return` (13.28 against 15.58, about 15 percent lower) or
  `@linkplain` (higher than non-Javadoc).
- The abstract claims "good agreement with human judgements". The evidence
  is a monotone ordering of medians on the 58 percent of items with a
  majority, with pairwise kappa of 0.10 to 0.29 among humans. That is weak
  support, and the paper itself says the Javadoc result needs "more
  extensive studies" (marked paraphrase of its own hedge).
- Perplexity is averaged per token, so it measures predictability from
  surface tokens. The paper's own error cases show it misses negation ("not
  primary keys, they are indexes") and conventions humans infer (`i` is an
  index).
- Everything is Java method comments; nothing covers Python docstrings,
  Rust `///` sections, inline comments or prose quality. The study is about
  information content, not reading cost.

## For readcost (used)

- Used in docs/research.md line 61: the doc-comment context skips tag and
  parameter lines (`@param`, `Args:`, `# Arguments`) because "they are
  mostly predictable from the code (Louis et al. 2018)". This is a fair
  gloss for `@param`, `@throws`, `@since`, `@see` and `@deprecated` in Java,
  with three qualifications the docs omit:
  - `@return` lines are only slightly more predictable than ordinary
    comment sentences (13.28 vs 15.58), so the paper does not support
    skipping return lines on predictability grounds.
  - The evidence is Java Javadoc only; extending it to Python `Args:` and
    Rust `# Arguments` sections is an inference.
  - Predictable means low in information, not low in reading cost. The
    skip is better justified as "these lines are formulaic and their
    content is checked against the signature" than by reading cost.
- The reference entry (research.md lines 161 to 162) has the right authors,
  title and arXiv id.
- Candidate: roadmap item 7 (research.md lines 129 to 131) plans an
  obvious-comment check from identifier overlap (Steidl et al. 2013). This
  paper is the stronger prior art for a predictability-based version; its
  finding that rationale and "expand" comments are the least predictable
  matches readcost's rule of keeping rationale clauses. Any such check
  should report, not judge, given the human kappa above.

## Open questions

- Would the Javadoc gap hold for Python docstring sections and Rust doc
  sections, where `Args:` text often adds units, ranges and side effects?
- A modern code LM would likely lower all perplexities; whether the tag
  ordering survives is untested.
