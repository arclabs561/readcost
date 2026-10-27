# A Decade of Code Comment Quality Assessment: A Systematic Literature Review

Pooja Rani, Arianna Blasi, Nataliia Stulova, Sebastiano Panichella,
Alessandra Gorla, Oscar Nierstrasz. 2022. Journal of Systems and Software
(article 111515). https://doi.org/10.1016/j.jss.2022.111515 ;
arXiv 2209.08165.

Read: full (arXiv preprint as submitted to JSS, 34 pages; title and
authors checked). All sections read; the two-column extraction interleaves
columns, and Figures 2 to 8 and Table 3's study list are only partly
legible, so per-attribute counts are not available beyond what the text
states.

## Claim

Research on comment quality from 2011 to 2020 is concentrated on Java,
on a few quality attributes, above all consistency between comments and
code, and on manual or heuristic assessment evaluated mostly by students
or the authors themselves.

## Method and data

- Systematic review: 17,554 papers from 26 software-engineering venues
  (CORE A*/A plus co-located workshops), keyword-filtered to 2,043, then
  manual inclusion by at least two of four evaluators (Cohen's kappa 0.36
  at the candidate stage) to 30; forward and backward snowballing added 17,
  for 47 studies.
- Extracted per study: comment scope, language, quality attributes and
  their definitions, techniques, metrics, contribution type, evaluation.

## Results (numbers that matter)

- 87 percent of studies analyse Java comments; about 15 percent Python, 10
  percent C# or C++; one study covers JavaScript.
- 21 quality attributes in use, 10 of them new relative to Zhi et al.'s
  earlier review. Consistency gets constant attention across the decade;
  completeness, accuracy, content relevance and readability are often
  studied; up-to-dateness has risen in the last three years; conciseness,
  coherence, organization, understandability and spelling/grammar appear in
  at most two studies each.
- Manual assessment is the most common technique; about 25 percent of
  studies use metrics; only 30 percent evaluate with practitioners; about
  half provide data or tools.
- Readability of comments, when measured, is measured with Flesch-Kincaid,
  which the authors criticize because comments mix code and prose.

## What the full text qualifies

- "Consistency" covers several things: comment/code mismatch after
  changes, rename-driven mismatch, and linguistic antipatterns. Staleness
  ("up-to-dateness") is a separate attribute in the paper's catalog,
  though the two overlap and one study measures one through the other.
- The paper lists comment smells (bloated, redundant, inconsistent
  comments) as an open area without settled definitions.
- Venue selection excludes industry tracks and non-SE venues; the authors
  checked that only about 1 percent of relevant ACM and IEEE results were
  missed.

## For readcost (used, with an imprecision)

- Cited in docs/research.md lines 6 to 7: "comment staleness is the most
  studied comment-quality problem (Rani et al. 2022)". The paper's most
  studied attribute is consistency between comments and code, which
  includes but is broader than staleness; up-to-dateness is listed
  separately and is described as rising, not dominant. Suggest: "consistency
  between comments and code, including staleness, is the most studied
  comment-quality attribute".
- The reference entry (research.md line 169) is accurate; the article
  number 111515 could be added.
- Relevant to readcost's design: the attributes closest to what readcost
  measures (conciseness, coherence, natural-language quality,
  spelling/grammar) are the least studied, and the only readability metric
  used on comments is Flesch-Kincaid. That is a gap readcost occupies, and
  it also means there is little prior evidence to lean on for its
  comment contexts.

## Open questions

- No study in the review evaluates sentence-level construction of comments
  against reader performance.
