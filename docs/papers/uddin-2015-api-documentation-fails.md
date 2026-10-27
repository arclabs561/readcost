# How API Documentation Fails

Gias Uddin, Martin P. Robillard. 2015. IEEE Software 32(4), 68 to 75.
https://doi.org/10.1109/MS.2014.80
(author copy: https://www.cs.mcgill.ca/~martin/papers/ieeesw2015.pdf)

Read: full (author manuscript from the McGill page, 9 pages; title and
authors checked). The copy is a pre-final manuscript: it still contains an
authors' editing note inside the text. Table 2's counts (examples and
developers per problem) and Figure 2's chart did not extract, so the
per-problem frequencies come from the text only.

## Claim

From two surveys of IBM developers, ten kinds of API documentation
failure fall into content problems (incompleteness, ambiguity, unexplained
examples, obsoleteness, inconsistency, incorrectness) and presentation
problems (bloat, fragmentation, excessive structural information, tangled
information). Content problems matter most: ambiguity, incompleteness and
incorrectness are the most severe and most in need of fixing.

## Method and data

- Exploratory survey: 698 IBM Canada employees invited, 69 responded; 179
  examples of good and bad documentation; the 89 bad examples were
  card-sorted into 10 problem types (79 usable examples).
- Validation survey: 1,064 IBM developers and architects in Canada and
  Britain invited, 254 responded (23.8 percent). For each problem:
  frequency in the last three months, severity, and priority under a
  fixed budget.

## Results (numbers that matter)

- Ambiguity: 42 frequently, 68 occasionally, 38 once or twice, 10 never,
  96 no opinion; 26.5 percent "frequently" after excluding no opinion.
  Ranked top priority by 54 respondents (51.9 percent of those ranking
  it).
- Six problems were called blockers at least once: incompleteness,
  ambiguity, obsoleteness, incorrectness, inconsistency, unexplained
  examples. Incorrectness is rarely seen but rated severe.
- No respondent chose tangled information or excessive structural
  information as a top problem.
- No significant difference between the less and more experienced halves.

## What the full text qualifies

- The paper counts ambiguity as a content problem: the text covers a topic
  but leaves out a clarifying detail so that several readings are
  possible. It is defined as a kind of incompleteness, not as unclear
  sentence construction.
- Bloat (verbose text) is the presentation problem closest to what a prose
  checker could see; it ranked below the content problems.
- One company, self-report, API reference documentation only.

## For readcost (used, with a gloss to fix)

- docs/research.md lines 3 to 6: readcost "cannot see content problems:
  missing, wrong or stale information. Developers rate those as the worst
  documentation failures (Uddin and Robillard 2015)". The paper's three
  worst are ambiguity, incompleteness and incorrectness. "Stale"
  (obsoleteness) is one of the six content problems but not in that top
  three, and the list in research.md omits ambiguity, the top-priority
  problem. A closer gloss: "missing, ambiguous or wrong information".
- README.md lines 79 to 81 repeat the claim ("correct, complete or up to date
  (which developers rate as the worst documentation failures)"); the same
  correction applies: the paper ranks ambiguity and incompleteness
  highest, then incorrectness, not staleness.
- The reference entry (research.md line 185) is accurate.
- The paper supports readcost's honesty about scope: what readers most
  want fixed is beyond a construction checker. Bloat is the one problem in
  the list that readcost's measures (length, density) touch.

## Open questions

- Ambiguity is defined by missing detail; some reported cases (the ASM
  `getItem` example) are a sentence that admits two readings. Whether a
  syntactic check can catch any of them is untested.
