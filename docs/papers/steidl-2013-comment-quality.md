# Quality Analysis of Source Code Comments

Daniela Steidl, Benjamin Hummel, Elmar Juergens. 2013. ICPC 2013,
pp. 83 to 92. https://doi.org/10.1109/ICPC.2013.6613836
(publisher-of-record copy hosted by the authors' company:
https://teamscale.com/hubfs/26978363/Publications/2013-quality-analysis-of-source-code-comments.pdf)

Read: full (10-page PDF; title and authors checked). All sections read.
Tables I, III and V and Figures 8 to 10 extracted only partly, so some
per-project numbers come from the text.

## Claim

Comment ratio is a poor documentation metric because many comments
(copyright, commented-out code) do not help understanding. Classifying
comments into seven types with a decision tree makes a quality model
possible, and two simple metrics find defects: a member comment whose
words overlap heavily with the method name is trivial, and inline comments
of two words or fewer are usually removable.

## Method and data

- Seven categories: copyright, header, member, inline, section, code
  (commented out), task. J48 decision tree on simple features (keywords,
  braces, distance to next declaration, word count, special-character
  share, code-snippet regexes). 830 hand-tagged Java comments from twelve
  projects (389 from jMol) and about 500 C++ comments; five-fold
  cross-validation.
- Coherence coefficient (c_coeff) for member comments: share of comment
  words within Levenshtein distance 1 of a word in the camelCase-split
  method name. Thresholds from preliminary manual checks: 0 means
  unrelated, above 0.5 means trivial.
- Length indicator for inline comments: at most 2 words or at least 30
  words.
- Survey: 16 developers (all with 5 or more years of programming) judged
  30 member comments (10 per c_coeff band) and 30 inline comments (10 per
  length band). Case study on five open-source projects.

## Results (numbers that matter)

- Classification: weighted precision and recall 96 percent (Java), 95
  percent (C++); commented-out code is the weakest class.
- c_coeff above 0.5: 9 of 10 comments judged trivial, agreement above 80
  percent. c_coeff = 0: 8 of 10 judged to need more information or a
  better method name.
- Inline comments of at most 2 words: 7 of 10 to be removed (deleted or
  replaced by extracting a method); 8 of 10 hold only local information.
  At least 30 words: 10 of 10 kept, all judged to hold global information.
- Case study: copyright is 18 to 49 percent of comment characters; ConQAT
  has 1,774 trivial member comments (9 percent), attributed to a
  missing-comment compiler warning; in jMol 44 percent of inline comments
  are two words or fewer.

## What the full text qualifies

- Thresholds come from "preliminary experiments with manual evaluation",
  then are validated on 10 comments per band with 16 people, mostly from
  the authors' own institutions and company.
- The 30-word result is not advice to write long comments; the authors say
  inline comments generally should not be that long.
- The comment-type model's impacts were defined by the authors' own
  reading of the training data.
- Java and C++ only.

## For readcost (candidate, with a mismatch)

- docs/research.md lines 128 to 130 (roadmap item 7) describe an
  obvious-comment check as "comment words repeating the next line's
  identifiers; Steidl, Hummel and Juergens 2013". The paper's metric is
  different: it compares a member (doc) comment with the method name, not
  an inline comment with the next line of code. For inline comments the
  paper's signal is length (two words or fewer), not identifier overlap.
  Either the roadmap should describe the c_coeff method as published
  (doc comment vs function name), or cite this paper only as the source
  for comparing comment words with identifiers and say the next-line
  variant is new.
- The reference entry (research.md lines 180 to 181) is accurate.
- The c_coeff check is cheap and fits readcost's doc-comment context: split
  the function name, compare it with the summary sentence, report above
  0.5 as info. Louis et al. 2018 is the model-based alternative.
- The ConQAT case (trivial comments written to silence a missing-comment
  warning) is a caution for any CI gate that rewards comment presence.

## Open questions

- The thresholds were never validated beyond 10 comments per band; a
  readcost version would need its own labeled sample.
