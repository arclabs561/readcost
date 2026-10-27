# Deep Just-In-Time Inconsistency Detection Between Comments and Source Code

Sheena Panthaplackel, Junyi Jessy Li, Milos Gligoric, Raymond J. Mooney.
2021. AAAI 2021. arXiv 2010.01625 (v2, 16 pages with appendices).

Read: full main text (arXiv v2; title and authors checked) and the
appendices on per-comment-type results, implicit edit encodings and the
combined detect-and-update system; Tables 1 to 3 checked in a
layout-preserving extraction. The re-implementation details of the Liu et
al. baseline (Appendix B) and hyperparameter lists were skimmed.

## Claim

Detecting a stale comment at the moment its method changes ("just in
time") works much better than judging a comment against the current code
alone ("post hoc"). A model that attends from the comment to an explicit
representation of the code edit reaches F1 about 0.83 to 0.87 on a cleaned
test sample, beating post hoc models and rule and feature baselines.

## Method and data

- 40,688 examples from 1,518 Java projects, from consecutive commits that
  changed a method: the comment changed too (positive, assumed to have gone
  stale) or did not (negative). Three comment types: `@return`, `@param`
  and the summary sentence of Javadoc. Negatives downsampled to balance;
  projects disjoint across splits.
- Labels are noisy by construction (a reworded comment counts as stale; a
  developer who forgot to update counts as consistent). A cleaned test
  sample of 300 examples (50 positive and 50 negative per type) was
  curated by hand.
- Models: BiGRU comment encoder with self-attention, code encoded as a
  token edit sequence or an AST edit graph (GGNN), cross-attention; with
  and without linguistic and lexical features. Baselines include a lexical
  rule (comment shares a token with deleted code), Corazza et al.'s SVM,
  CodeBERT bag of words, and Liu et al.'s random forest.

## Results (numbers that matter)

- Cleaned test sample, F1: lexical rule 74.7; Liu et al. 75.8; CodeBERT
  over the edit 72.3; post hoc models 63 to 65; just-in-time models 81.4 to
  83.1; with features 86.4 to 87.1. On the full (noisy) test set the best
  F1 is about 80.
- Per type (with features, cleaned sample): `@param` F1 about 92 to 94;
  `@return` about 79; summary 86 to 90, but only 68 to 71 on the full test
  set.
- For `@param`, a format rule from Khamis et al. (the comment starts with
  the parameter name) is already very strong.
- Detection matters for automatic updating: a system that never updates
  scores 50 percent exact match on the balanced sample and beats an
  always-update model on several metrics.

## What the full text qualifies

- The positive label is "the developer changed the comment", not "the
  comment was wrong"; the cleaned 300-example sample is the only check
  against that noise.
- Balanced classes after downsampling; real stale comments are a small
  share of code changes, so precision in practice would be lower.
- Java Javadoc only.
- The authors warn that relying on the tool could make developers trust
  comments the tool missed.

## For readcost (used, accurately)

- Cited in docs/research.md lines 7 to 8 with Wen et al. 2019 as a tool
  that "compares comments with code changes" and covers staleness, which
  readcost does not. That description is accurate.
- The reference entry (research.md lines 165 to 166) is accurate.
- Candidate: the git and Claude Code hooks already see diffs. The
  one-line lexical rule (a doc comment still names an identifier the diff
  deleted) reached F1 74.7 here and needs no model. As an opt-in info
  finding it would be the cheapest step toward the content problems
  research.md says readcost cannot see; it would need its own precision
  check on readcost's corpora.

## Open questions

- How does the lexical rule do on Python and Rust, where docstrings name
  parameters in prose rather than tags?
