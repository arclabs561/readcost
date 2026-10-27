# Pronouns, Names, and the Centering of Attention in Discourse

Peter C. Gordon, Barbara J. Grosz, Laura A. Gilliom. 1993. Cognitive Science
17(3), 311-347. DOI
[10.1207/s15516709cog1703_1](https://doi.org/10.1207/s15516709cog1703_1).

Read: full (37-page PDF of the Wiley version, from a researcher.life
full-text mirror; the Wiley footer in the file marks it as downloaded from
onlinelibrary.wiley.com). Title and authors match. OCR has character
errors but every section, table and figure caption is readable. Figures
are plots without numbers; values come from the text and tables.

## Claim

Five self-paced reading experiments test centering theory. Each utterance
has one backward-looking center, which is its grammatical subject when
possible; referring to it with a repeated name instead of a pronoun slows
reading (the "repeated-name penalty"). Surface-initial position does not
make an entity the backward-looking center but does raise its prominence
as a candidate for the next sentence.

## Method and data

- Short constructed passages (3 to 5 sentences) about two people; a
  true/false comprehension question after each. Harvard students: 12 (exp.
  1), 16 and 18 (2A, 2B), 16 (3), 24 (4), 24 (5). 24 or 40 items, with
  fillers. Exp. 1 shows phrases of 2 to 6 words; later experiments one
  sentence at a time.
- Exp. 1 used two same-gender names ("Bruno ... Tommy"), so its pronouns
  were ambiguous by gender; experiments 2 to 5 used different genders.

## Results (numbers that matter)

- Exp. 1: passage reading time 7,581 ms (pronouns for both), 7,624
  (pronoun subject, repeated object name), 8,460 (repeated names for
  both). The subject repeated as a name costs time; repeating the object's
  name does not. Comprehension accuracy did not differ (94 to 95%).
- Exp. 2A, 2B: no penalty for a repeated name in a fronted non-subject
  phrase ("In Lisa's opinion"). Post hoc, sentences were read faster the
  more directly their subject had been mentioned in the previous sentence.
- Exp. 3: penalty for the subject only, not for the fronted entity.
- Exp. 4: penalty 183 ms when the subject continues the previous
  subject; 42 ms, not significant, after a shift to the other entity.
- Exp. 5: penalty also for an entity that was surface-initial (but not
  subject) in the previous sentence.

## What the full text qualifies

- The penalty is specific: it applies to the grammatical subject that
  continues the previous sentence's most prominent entity. Repeating a
  name in object position or after a topic shift cost nothing measurable.
- Comprehension accuracy never changed; the effect is on time only.
- Narrative passages about people with names, small samples. Nothing
  about technical terms, code identifiers or inanimate referents.

## For readcost (used / tested / candidate)

Used: docs/research.md lines 42-44 as the reason readcost has no
ambiguous-pronoun check.

Citation accuracy: "repeating a name where a pronoun would do slows
reading" is accurate as a summary, if narrower than stated: only in
subject position, continuing the previous sentence's subject. Using it
against an ambiguous-pronoun rule is a fair inference, not a finding: the
paper does not test pronoun ambiguity directly, though exp. 1's
same-gender pronouns showed no cost.

Candidate: none for technical prose. Repeating a defined term is
deliberate in documentation (readcost's first-use rule relies on it), and
the paper says nothing about terms or inanimate referents.

## Open questions

- Whether the penalty holds for technical nouns repeated as subjects
  ("The index ... The index ...") is untested here.
