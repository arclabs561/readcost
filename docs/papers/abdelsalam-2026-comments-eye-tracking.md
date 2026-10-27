# The effect of comments on program comprehension: an eye-tracking study

Youssef Abdelsalam, Norman Peitek, Annabelle Bergum, Sven Apel. 2026.
Empirical Software Engineering 31, article 94.
https://doi.org/10.1007/s10664-025-10721-2

Read: full text (publisher PDF from link.springer.com, 65 pages; title and
authors checked), all sections from introduction to conclusion and the
declarations. Several results tables (10, 11, 13 to 16, 19, 20, 23) and
figures are images in the PDF and did not extract; the per-snippet numbers
below come from the running text and the tables that did extract (12 is
partly described in text; 17, 18, 21, 22, 24 extracted).

## Claim

Whether inline comments help depends on the code they annotate. Across 12
snippets the composite score moved from 30 percent worse to 34 percent
better with comments. Comments draw about a quarter of fixations, make local
reading more top-to-bottom, and are read mostly after the code
("code-first"). Participants rated comments as helpful even on snippets
where comments did not improve performance or perceived difficulty.

## Method and data

- 20 computer science students at Saarland University (18 men, 2 women,
  mean age 25.8), convenience sample.
- 12 Java snippets of 16 to 24 lines (algorithm tasks such as peak element,
  longest common subsequence, sieve), taken from Nielebock et al. and Peitek
  et al. and adapted: Javadoc removed, identifiers obfuscated. Task: write
  the program's output.
- Comments written by the first author and reviewed by two colleagues,
  placed to the right of the code, on nearly every line (5 to 10 per
  snippet). The authors say this density departs from practice.
- Each participant saw each snippet once, in one condition (comments
  present or missing), so the design is partially crossed. Tobii EyeX at
  60 Hz; velocity-threshold fixation detection; lines as areas of interest.
- Outcome: a composite of correctness and per-snippet normalized time,
  weighted equally. Wilcoxon tests on aggregates, per-snippet linear mixed
  models with a participant random intercept, Benjamini-Hochberg correction;
  a light thematic analysis of a post-questionnaire.

## Results (numbers that matter)

- Performance: snippet 1 correctness fell from 70 to 30 percent with
  comments and time rose from 191 to 272 s (score -30 percent); snippet 9
  correctness rose from 60 to 100 percent and time fell from 339 to 189 s
  (+34 percent). Five snippets positive, four negative, three neutral or
  mixed. With about 10 participants per snippet and condition, each
  correctness rate rests on roughly ten answers.
- Attention: with comments, 92 of 397 area fixations (23 percent) were on
  comments. Total fixations rose for snippets 1 to 4 (more text on screen)
  and fell for snippets 8 to 10.
- Local linearity (Table 17, corrected p): vertical-later fixations 14.3 to
  12.1 percent (p 0.018), regressions 28.7 to 25.7 percent (p 0.004),
  within-line forward saccades 16.6 to 22.8 percent (p 0.003), within-line
  regressions 14.8 to 16.1 percent (p 0.018). Global order alignment: no
  significant change (Table 18).
- Code-to-comment saccades outnumber comment-to-code (7.8 vs 6.4 per
  snippet, p 0.007); the global code-first and comment-first alignments do
  not differ.
- Self-report: in Table 24, perceived difficulty changed significantly for
  two snippets: snippet 9 fell (3.1 to 1.4) and snippet 5 rose (3.9 to 4.2),
  both p < 0.001; the text discusses only snippet 9. Comment contribution
  was rated 2.8 to 3.9 of 5 on every snippet.
- Themes: comments help when they summarize or give intent; comments that
  "merely restate easy to understand lines were not helpful" (participant
  quote reported by the authors); some readers skip comments when the code
  is clear.

## What the full text qualifies

- The abstract's "30% decrease to 34% increase" is a range over 12 snippets
  with about ten observations per cell; the paper does not separate comment
  quality from snippet difficulty, so the variation is not attributed to any
  property of the comments.
- The comments were dense, line-by-line, and written by one author for
  algorithm puzzles with obfuscated names. That is closer to a teaching
  setting than to comments in production code.
- The study varies whether comments exist, not how they are written. It
  says nothing about sentence construction, length or wording inside a
  comment.
- The ethics note says the study was a student thesis project and did not
  need committee approval.

## For readcost (used)

- Cited in docs/research.md line 62: the inline-comment context reports
  syntax findings at info level because "comment value depends on context
  (Abdelsalam et al. 2026; Nielebock et al. 2019)". The paper does support
  "comment value depends on context": the effect of comments ranges from
  harmful to helpful by snippet. It does not bear on the severity of prose
  findings inside comments; that step is readcost's own design judgment.
  Two findings fit the choice, though neither tests it: readers skip
  comments when code is clear, and comments that restate code were judged
  unhelpful. Suggest wording such as "comments are read selectively and
  their value varies by code (Abdelsalam et al. 2026)".
- The reference entry (research.md lines 135 to 136) is accurate: authors,
  title, journal and volume match; article number 94 could be added.
- Candidate: the "restating comments are not helpful" theme supports
  roadmap item 7 (obvious-comment check), as weak qualitative evidence.

## Open questions

- Would sparse, idiomatic comments in real code show the same spread?
- None of the measures isolate comment wording, so readcost's question
  (does a comment's sentence construction slow its reader) remains open.
