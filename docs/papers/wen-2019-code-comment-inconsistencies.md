# A Large-Scale Empirical Study on Code-Comment Inconsistencies

Fengcai Wen, Csaba Nagy, Gabriele Bavota, Michele Lanza. 2019. ICPC 2019,
pp. 53 to 64. https://doi.org/10.1109/ICPC.2019.00019
(author preprint: https://csnagy.github.io/research/pdfs/2019/Wen2019-preprint.pdf)

Read: full (author preprint, 12 pages; title and authors checked). All
sections read; Figures 1 to 3 (bar charts, heatmap, taxonomy tree) did not
extract, so per-category values come from the text.

## Claim

Code and comments mostly do not change together. Across the history of
1,500 Java projects, 13 to 20 percent of code changes come with a change to
the method's or class's comments, and some change types (array, lambda,
loop, literal, call and rename changes) rarely do. A manual taxonomy of 362
comment-fixing commits shows what kinds of stale comments developers fix.

## Method and data

- 1,500 most-starred Java projects with at least 500 commits and 10 stars
  (November 2018); 3,323,198 commits; GumTreeDiff AST operations (1.3
  billion, 476 GB database, released).
- RQ1: for each of 18 categories of code change made in isolation in a
  method, the share followed by a change to that method's comments (MCC)
  or to its class Javadoc (CCC); Fisher's exact tests with Holm
  correction and odds ratios.
- RQ2: 3,641 commits whose messages match (update or outdate) and comment;
  500 sampled, each labeled by two of three authors, a third resolving
  disagreements (51 percent of commits needed one); 138 false positives.

## Results (numbers that matter)

- Co-change rate: 7 percent of changes for method comments, 13 percent for
  class comments, so 13 to 20 percent overall.
- Constructor changes: CCC 0.83 vs MCC 0.06; signature changes: CCC 0.68
  vs MCC 0.04; variable declarations: MCC 0.69 vs CCC 0.19.
- Taxonomy of the 362 commits: application logic 136 (comment described
  logic wrongly 35, new logic 25, more detail 53), code design or quality
  80 (technical-debt comments 54, after refactoring 14),
  formatting/readability 63 (better wording 31, typos 9), maintenance 17,
  copyright 10, others 56. 25 of 69 change types relate to
  inconsistencies.

## What the full text qualifies

- The authors say the 80 percent of changes without a comment update are
  not all inconsistencies; many changes need no comment change.
- MCC and CCC cannot see deletions or edits of comments that do not exist,
  and GumTree sometimes reports a type change as delete plus insert.
- The RQ2 sample comes from a keyword filter, so the taxonomy covers fixes
  developers labeled as comment updates, not stale comments in general.
- Java only.

## For readcost (used, accurately)

- Cited in docs/research.md lines 7 to 8 with Panthaplackel et al. 2021 for
  "tools that compare comments with code changes cover" staleness. This
  paper is an empirical study, not a tool; it motivates such tools and
  reports where staleness arises. The sentence groups it with a tool;
  "studies and tools (Wen et al. 2019; Panthaplackel et al. 2021)" would be
  more exact.
- The reference entry (research.md lines 186 to 187) is accurate.
- Relevant to readcost's scope: about a sixth of the comment-fixing
  commits (63 of 362) were wording, readability or typo fixes, so
  developers do revise how comments are written, not only what they say.
  That is weak support for running prose checks on comments at all.
- Candidate: rename and literal changes rarely update comments, and the
  paper's examples are comments that still name an old identifier or
  literal. That is the same cheap diff check suggested in the
  Panthaplackel et al. note.

## Open questions

- Do Python and Rust projects, where docstrings are the main form of
  documentation, show similar co-change rates?
