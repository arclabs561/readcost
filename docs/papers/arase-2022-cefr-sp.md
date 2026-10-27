# CEFR-Based Sentence Difficulty Annotation and Assessment

Yuki Arase, Satoru Uchida, Tomoyuki Kajiwara. 2022. EMNLP 2022; arXiv
[2210.11766](https://arxiv.org/abs/2210.11766) (v1).

Read: full (body, limitations, ethics statement, appendices A to D).
Title and authors match.

## Claim

CEFR-SP: about 17k English sentences labelled with CEFR levels (A1 to
C2) by English-education professionals, and a prototype-based BERT
classifier that copes with the scarcity of A1 and C2 sentences (macro-F1
84.5%).

## Method and data

- Sentences of 5 to 30 words from Newsela-Auto, Wiki-Auto and SCoRE
  (written for learners). Only stand-alone sentences: first sentence of a
  paragraph, no named entities (dates, numbers, common countries and
  names allowed), no quotations or brackets; Wikipedia first paragraphs
  excluded.
- Two annotators chosen from eight by agreement with a senior expert
  (Pearson 0.75 and 0.73 on 100 trial sentences). Guideline: a sentence is
  level X if a learner at X can readily understand it; dictionary lookup
  allowed, but word level alone must not decide.
- Of 20k sentences, the two gave the same level to 37.6% and adjacent
  levels to 50.8%; sentences whose labels differ by more than one level
  were dropped, leaving 17,676 sentences with 27,841 labels. Both labels
  count as correct.

## Results (numbers that matter)

- Mean length by level: A1 7.7, A2 10.9, B1 15.2, B2 18.0, C1 19.0, C2
  19.2 words. Length separates A from B but hardly B1 to C2; lexical level
  of content words rises with sentence level throughout.
- Newsela grade levels scatter across CEFR levels; Brunato et al.'s
  crowd complexity ratings behave differently from CEFR-SP.
- Classifier: macro-F1 84.5%, quadratic weighted kappa 0.628; BERT
  baseline 82.5% with loss weighting; bag-of-words SVM 41 to 52%.

## What the full text qualifies

- The scale is learner proficiency (who can understand the sentence), not
  native-reader reading time.
- The selection removes the sentences technical prose is full of: named
  entities, brackets, quotations, context-dependent sentences.
- Agreement is modest at the exact level (37.6%); the corpus keeps only
  sentences within one level.

## For readcost (used / tested / candidate)

Tested: docs/evaluation.md "Sentence difficulty rated by people" and
"Model signals"; scripts/eval_sentence_ratings.py.

Citation accuracy: docs/evaluation.md lines 898-902 ("two
English-education professionals each placed at a CEFR level from A1 to
C2 ... Wiki-Auto, CC BY-SA 3.0 ... SCoRE, CC BY-NC-SA 4.0; the Newsela part
needs a separate licence") is accurate. readcost's "the two raters agree
at rho 0.72" is its own computation on the released labels, not a number
from the paper; worth saying so, since the paper's agreement figures are
37.6% exact and 88.4% within one level before filtering. Because pairs
more than one level apart were removed, any agreement computed on the
release is inflated by construction.

Implication for the readcost result: sentences with named entities,
acronyms and brackets were excluded, so the near-zero firing rates of
undefined-acronym and similar rules on CEFR-SP say nothing about technical
text. The finding that length stops separating levels above B1 matches
readcost's use of within-length-bin correlations.

## Open questions

None beyond the selection bias above.
