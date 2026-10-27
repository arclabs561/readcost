# What Makes a Good Commit Message?

Yingchen Tian, Yuxia Zhang, Klaas-Jan Stol, Lin Jiang, Hui Liu. 2022.
ICSE '22. https://doi.org/10.1145/3510003.3510205 ; arXiv 2202.02974.

Read: full (arXiv v1 PDF, 13 pages; title and authors checked). All
sections read. Figure 3 and Tables 3 to 5 extracted only partly; numbers
below come from the text.

## Claim

A good commit message says what changed and why. In five popular Java
projects about 44 percent of messages lack one or both, missing "why" is
about twice as common as missing "what", and a BiLSTM over BERT embeddings
can flag messages that lack either.

## Method and data

- Definition from 46 papers, the top 50 web results for "good commit
  message", and 30 developer responses (about 93 percent said a message
  should give both what and why).
- 1,649 commit messages sampled from Spring Boot, Dubbo, OkHttp, JUnit 4
  and Retrofit (bots removed, English only); 52 non-atomic commits dropped,
  1,597 labeled by two authors as why-and-what, no why, no what, or
  neither. Cohen's kappa 0.91. A linked issue or pull request counts as a
  why; a reason that is common sense (for example "fix typo") is not
  counted as missing.
- Validation survey: 958 contributors invited, 30 valid responses (3.1
  percent), 102 of 120 labels matched the authors'.
- Thematic analysis of 252 good messages into five why categories (18
  subcategories) and four what categories; Mockus and Votta maintenance
  types; classifiers with ten-fold cross-validation.

## Results (numbers that matter)

- Share of good messages per project: about 42 to 82 percent, mean about
  56 percent. "No why" averages 28 percent, "no what" 12 percent,
  "neither" 1 to 8 percent.
- Why is most often an error scenario (19.8 percent of the 252), implied
  improvements (15.5 percent), or out-of-date code (9.5 percent).
- "Missing why" is the most common category for perfective changes (34.2
  percent), where the reason is usually obvious.
- Classifiers: accuracy 84.7 percent (has why), 91.0 percent (has what),
  75.9 percent (good). Precision and recall for missing why 76.5 and 70.9
  percent.

## What the full text qualifies

- "Missing why" is judged leniently: a link to an issue counts as a why,
  and a trivial reason is not required.
- Five Java projects, chosen for having good messages; the authors say the
  44 percent figure is not representative of GitHub.
- The classifiers use random ten-fold splits over messages from the same
  projects and authors.
- The study is about content (whether a reason is given), not about how
  sentences are written.

## For readcost (used, with a caution)

- Cited in docs/research.md line 64 with Li and Ahmed 2023: the
  commit-body context has stacked-noun and hyphen findings "On; a missing
  'why' is the main quality signal". The paper supports "missing why is the
  most common defect" in its sample. It gives no reason to turn on syntax
  rules in commit bodies; the citation explains what matters in a commit
  body, which readcost does not check. research.md lines 3 to 5 say
  readcost cannot see missing information; this row should say the why
  check is out of scope or planned, so readers do not infer readcost
  detects it.
- The reference entry (research.md line 182) is accurate; "Tian et al."
  could carry the arXiv id.
- Candidate: a cheap heuristic for commit bodies, such as reporting a body
  with no causal connective ("because", "so that", "to") as info, would be
  the readcost-shaped version of this finding. It would need its own
  evaluation; this paper's classifier is a BERT model, not a rule.

## Open questions

- How often do commit bodies in readcost's Go commit corpus give a reason?
  The Go project's own conventions may differ from these Java projects.
