# Large-scale evidence of dependency length minimization in 37 languages

Richard Futrell, Kyle Mahowald, Edward Gibson. 2015. PNAS 112(33),
10336-10341. DOI
[10.1073/pnas.1502134112](https://doi.org/10.1073/pnas.1502134112);
PMC4547262.

Read: full main text from the PMC HTML (significance, abstract, results,
further baselines, discussion, materials and methods). Figures and the
regression equation are images and were not readable; their content is
described in the captions and text. Table S1 (corpus details) not read.
Title and authors match.

## Claim

In hand-parsed corpora of 37 languages, total dependency length grows more
slowly with sentence length than in random reorderings of the same trees,
including conservative baselines with fixed word order per relation type.
The authors read this as a universal pressure to keep related words close.

## Method and data

- HamleDT 2.0, Google Universal Treebank 2.0, Universal Dependencies 1.0,
  plus the Chinese Dependency Treebank. Mostly written prose (news, novels,
  blogs); Latin and Ancient Greek include poetry; Japanese is spoken dialogue.
- Trees normalized so prepositions head their objects and complementizers
  head their verbs; Stanford-style conjunctions. Content-head versions gave
  the same pattern.
- Arc length: words between head and dependent, counting the dependent (so
  adjacent words have length 1). Punctuation and root arcs excluded.
- Baselines (100 per sentence): free random projective order; fixed order
  per relation type; consistent head direction; fixed head position; and an
  optimal projective order.
- Mixed-effects regression of total sentence dependency length on squared
  sentence length (sentences under 100 words), with random effects by
  sentence; likelihood ratio test on the observed-vs-random slope term.

## Results (numbers that matter)

- Every language is below the free-order baseline (P < 0.0001 each). Against
  the fixed-order baseline all are significant at P < 0.0001 except Telugu
  (P = 0.15, a small corpus without long sentences).
- Sentence length 12 is the shortest length with a significant effect in all
  languages.
- Squared sentence length fit total dependency length better than plain
  length for 33 of 37 languages (AIC and BIC).
- Observed lengths sit between random and optimal; head-final languages
  (Japanese, Korean, Turkish) minimize much less than Italian, Indonesian or
  Irish.

## What the full text qualifies

- The study is about production and grammar (corpus word order), not reading
  difficulty; processing cost is the motivation, cited from other work.
- The authors do not separate grammar from speaker choice.
- They argue that length summaries not conditioned on sentence length are
  inaccurate because they mix dependencies of different lengths.
- Effect size varies a lot by language; morphology (case marking) may make
  long dependencies easier.

## For readcost (used / tested / candidate)

Not cited in readcost's docs. Clark et al. 2026 cite it for speakers
avoiding long dependencies, which the paper supports as a corpus tendency.

- Supports judging dependency length against sentence length rather than
  as a raw mean (README.md 301-304, docs/research.md 67-69,
  src/readcost/profile.py 1-5).
- readcost's arc length (token-position difference excluding punctuation,
  features.py 521-523) matches the paper's definition.
- Functional form differs: readcost fits mean dependency length against
  log(sentence length) (profile.py 76-77); the paper finds total length
  grows with squared length, which implies a mean that grows roughly
  linearly. A log fit may under-predict long sentences and flag them too
  often. Candidate: compare linear-in-n and log fits on the default profile
  corpus by held-out residuals.
- Absolute lengths depend on the annotation scheme (the paper normalized
  its treebanks), so readcost's numbers are comparable only to a profile
  built with the same spaCy model, not to the paper's figures.

## Open questions

- Does the length effect in readcost's own profile corpus look more like
  log or linear in sentence length?
