# Commenting source code: is it worth it for small programming tasks?

Sebastian Nielebock, Dariusz Krolikowski, Jacob Krüger, Thomas Leich,
Frank Ortmeier. 2019 (online 2018). Empirical Software Engineering 24(3),
1418 to 1457. https://doi.org/10.1007/s10664-018-9664-z

Read: full (accepted-manuscript preprint from a co-author's page,
jacobkrueger.github.io, 42 pages; title and authors checked; the publisher
version is paywalled). Sections 1 to 6 and the threats section read in
full. Figures 1 to 5 and Tables 5 to 8 extracted as scattered numbers, so
per-task values are taken from the text. Appendix A (translated task code)
was skimmed, not read line by line.

## Claim

For small Java tasks (under 30 source lines), whether code carries no
comments, line-level implementation comments, or Javadoc documentation
comments makes almost no measurable difference to correctness or time,
especially for professionals. Participants nonetheless believe comments
save time.

## Method and data

- Online survey (LimeSurvey), June to July 2016, in German; tasks and
  comments were written in German and translated for the paper.
- 416 started; 277 kept (227 professionals, 50 novices by a self-assessed
  experience score); 1,619 of 1,940 task answers kept after removing
  interrupted or implausibly fast or slow answers; only 66 participants
  have every task.
- Nine tasks of 7 to 27 lines, three each of using code, fixing a bug and
  extending code; two from Apache Commons Lang. Identifiers anonymized
  (`Class1`, `foo`). Three groups rotate comment type over tasks (Latin
  square). Comments written by the authors, designed not to restate syntax.
- Correctness by Fisher's exact test with Bonferroni post hoc; time for
  correct answers by Kruskal-Wallis and Dunn tests; a Likert self-report;
  free-text answers from 86 participants.

## Results (numbers that matter)

- Correctness: no significant effect of comment type for novices; for
  professionals one of nine tasks (task 2) differs, and there
  implementation comments did worse than no comments. The authors trace
  this to a comment naming concepts (prefix, suffix) that did not match the
  anonymized variables.
- Time: one significant difference in 18 comparisons (task 8, novices
  slower with Javadoc that used an `@see` reference to `StringBuilder`).
- Professionals beat novices with documentation comments on 3 of 9 tasks.
- Self-report: most participants rated comments as neutral or slightly
  time-saving. The text gives the counts saying comments moderately or
  highly reduce time as "14 to 11" for novices and "132 to 37" for
  professionals; the figure did not extract, and the text does not say
  whether the pairs are implementation versus documentation comments, so
  the split is unclear. Either way it runs against the measurements.
- Free text: several professionals distrust comments and rely on
  identifiers, tests and the debugger; others say comments are needed for
  interfaces or longer code.

## What the full text qualifies

- The null result is for small, algorithmic, anonymized snippets; the
  authors say comments may matter for larger or more complex code and
  that identifier anonymization pushed readers toward comments.
- Comment content and length were not varied; a table of comment lines
  versus correctness and time is discussed only qualitatively because nine
  tasks give no power.
- Many statistical tests on small novice cells; the two significant
  differences could be chance, as the authors acknowledge.
- Unsupervised online setting; interruptions handled by trimming.

## For readcost (used)

- Cited in docs/research.md line 62 with Abdelsalam et al. 2026 for "comment
  value depends on context" in the inline-comment context. Partly
  accurate. The paper's main finding is that comment type barely matters
  on small tasks, which supports lowering the stakes of findings in short
  comments. The "depends on context" reading comes mostly from the
  participants' free text and the authors' discussion, not from measured
  effects. A closer gloss: "for small tasks, comments had almost no
  measured effect on correctness or time (Nielebock et al. 2019)".
- The reference entry (research.md lines 163 to 164) has the right title,
  journal and volume; the year 2019 matches the volume (online first
  2018, which Abdelsalam et al. cite as 2018).
- Task 2 is a direct example of a content failure: a comment that names the
  wrong concept hurt professionals. That is the class of problem
  research.md lines 3 to 8 say readcost cannot see.

## Open questions

- No study here or in Abdelsalam et al. varies how a comment is written
  while holding its content fixed, which is what readcost would need.
