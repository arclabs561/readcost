# Put The "Code" Back In "Code Comprehension Study"

Kyle D. Chin, Reid Holmes. 2026. ICPC '26 (34th International Conference on
Program Comprehension). https://doi.org/10.1145/3794763.3794806
(author preprint: https://www.cs.ubc.ca/~rtholmes/papers/icpc_2026_chin.pdf,
CC BY-NC-ND 4.0)

Read: full (author PDF, 13 pages; title and authors checked). All sections
read. Figures 1 to 3 and Table 2 are images or scattered numbers in the
extraction; the values below come from the text.

## Claim

Controlled code-comprehension studies disagree because they use small,
synthetic, length-controlled samples. In 604k methods from mature
open-source projects, method length (lines of code) correlates strongly
with the usual comprehension metrics, metrics vary widely even among
methods of similar length, and methods with inline or block comments are
longer and more complex than methods without. The authors propose comment
presence as a comprehension signal.

## Method and data

- Ten top-starred, actively developed GitHub projects per language in
  TypeScript, Python, Java, C++ and Rust (the text says 49 projects);
  methods extracted with a custom parser; methods of 3 or fewer lines and
  the top 1 percent by length per project dropped.
- Metrics from prior studies: Length, Identifiers, Characters, McCabe,
  FanOut, Halstead volume, token entropy; CommentPresence as none, one or
  several inline or block comments. Consecutive comment lines count as one
  comment. Docstrings are not counted as comments.
- No human subjects. The premise that the code was comprehended rests on
  code review and active maintenance, checked from contribution guidelines
  and GitHub Archive activity counts.
- A 500-comment sample was checked by two authors: 12 (2.4 percent) were
  junk such as TODOs or commented-out code.

## Results (numbers that matter)

- Length correlates with Characters (r squared 0.91), Identifiers (0.86),
  Halstead (0.83), FanOut (0.72), McCabe (0.71) and entropy (0.58).
- Within length bands, metrics still vary widely; with the 16-snippet
  samples typical of prior studies, the standard error of mean characters
  per Java method would be 43 (small methods) to 134 (all methods).
- Per-line averages discriminate little across bands (tensorflow average
  identifiers per line 2.6, 2.8, 2.9 for small, medium and large methods).
- Comments: in vscode the median Length/Identifiers/Halstead is 8/15/94
  without comments, 13/27/212 with one, and 23/53/480 with several. Cliff's
  delta median 0.36 (none vs one) and 0.45 (one vs several). With length
  held fixed, commented methods are still more complex, with small to
  medium deltas, largest in Python.
- Docstrings: methods with only a docstring have about the same length as
  uncommented ones (Java 9.9 vs 9.5 lines; Rust 13.1 vs 14.1).

## What the full text qualifies

- "Comment presence serves as a useful comprehension metric" is an
  inference. Nothing in the study measures comprehension; it shows that
  comments co-occur with long and complex code.
- The finding covers inline and block comments only. Docstrings were
  excluded on purpose, and docstring-only methods look like uncommented
  ones.
- The text reports r squared and calls it a correlation coefficient; the
  ANOVA p values are reported as 0.00.
- The paper is about code metrics; it does not study comment text, comment
  length or density.

## For readcost (used, with two mismatches)

- docs/research.md lines 75 to 77 cite this paper for "below about 40 words
  the verdict uses the number of findings, not the density". The paper
  does not support that. It says nothing about prose, short units, density
  of findings or a 40-word threshold. Its nearest point is that per-line
  averages lose meaning across very different lengths and that small
  samples have large standard errors. That is a loose analogy at best; the
  40-word rule needs its own justification (for example, the arithmetic in
  the same sentence: one finding in twelve words gives an index above 80).
- docs/research.md lines 97 to 99 cite it for ordering findings "in doc
  comments" so that comments on complex functions come first, "since
  comments cluster on longer and more complex code". The paper's finding is
  for inline and block comments, and it reports that methods with only a
  docstring are no longer than uncommented ones. For doc comments
  (readcost's `///`, docstrings, `/** */`) the paper gives no support for
  complexity ordering. The triage idea could still apply to the
  inline-comment context.
- The reference entry (research.md lines 147 to 148) is accurate.
- Candidate: the length-confounding result supports research.md's plan to
  check any new index against a plain length baseline (lines 100 to 102).

## Open questions

- Do docstrings on complex functions carry more prose problems, or only
  more words? This paper does not test it.
