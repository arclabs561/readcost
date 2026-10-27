# Challenging stereotypes about academic writing: Complexity, elaboration, explicitness

Douglas Biber, Bethany Gray. 2010. Journal of English for Academic
Purposes 9(1), 2-20. DOI
[10.1016/j.jeap.2010.01.001](https://doi.org/10.1016/j.jeap.2010.01.001);
author copy at jan.ucc.nau.edu/~biber.

Read: full (author PDF of the published article, 19 pages, sections 1 to
6; reference list not read). Title and authors match. Figures are bar and
line charts without printed values.

## Claim

Academic writing is not elaborated with dependent clauses, as teachers
assume; conversation has about twice as many dependent clauses. Academic
prose is "compressed": its complexity is phrasal modification inside noun
phrases (attributive adjectives, noun premodifiers, prepositional-phrase
postmodifiers, appositives). That compression leaves the relation between
head and modifier unstated, so academic prose is less explicit than
clausal alternatives. The style grew in the 20th century, while linking
adverbials declined and colons rose.

## Method and data

Corpus counts per 1,000 words: about 3 million words of research articles
(science/medicine, education, psychology, history; 1965, 1985, 2005), the
T2K-SWAL university corpus (textbooks, syllabi, spoken registers), 4.2
million words of American conversation from the Longman corpus, and the
ARCHER and Coruña corpora for history. Longman Grammar tagger plus hand
coding for prepositional phrase function and appositives on a subsample.

## Results (numbers that matter)

- Dependent clauses about twice as frequent in conversation as in
  academic writing; relative clauses (especially non-finite) are the
  exception, more frequent in writing.
- Noun premodifiers in academic prose rose from rare in the 18th and 19th
  centuries to about 80 per 1,000 words by 2005 (figure 5, read from the
  plot).
- Worked examples of ambiguous compression: "pressure hose" vs "pressure
  ratio"; three different relations expressed by "for" in one sentence.

## What the full text qualifies

- The paper measures frequencies, not reading. "Efficient for expert
  readers, difficult for novices" is the authors' argument from the
  examples, offered as a motivation and a teaching implication; there is
  no reader experiment, timing or comprehension measure.
- The authors are descriptive, not prescriptive: their conclusion is that
  students must learn to read and write this style, and that how to
  balance clarity and economy needs research.

## For readcost (used / tested / candidate)

Used: stacked-nouns and hyphen-compound reasoning, first-use-only
reporting (src/readcost/engine.py lines 92-97), docs/research.md lines
16-19.

Citation accuracy:

- docs/research.md lines 16-18, "Compressed noun phrases are efficient
  for expert readers and costly for newcomers (Biber and Gray 2010)":
  accurate as a report of the paper's argument, but it reads as a finding.
  The paper presents it as interpretation; nothing was measured on readers.
- engine.py lines 95-96, "Biber and Gray 2010 show such noun phrases are
  efficient for expert readers and costly for newcomers, but do not study
  repeated use": "show" overstates in the same way; "argue" would be
  accurate. The second half is accurate.
- The paper supports the docs' point that technical prose is noun-heavy by
  register, and its "pressure hose / pressure ratio" contrast is a direct
  source for the stacked-nouns rationale (unstated relation between
  nouns).

## Open questions

- The decline of linking adverbials is a measurable register trend that
  readcost does not track; none of the evidence here ties it to reading
  cost either.
