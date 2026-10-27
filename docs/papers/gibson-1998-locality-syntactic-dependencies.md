# Linguistic complexity: locality of syntactic dependencies

Edward Gibson. 1998. Cognition 68(1), 1-76. DOI
[10.1016/S0010-0277(98)00034-1](https://doi.org/10.1016/S0010-0277(98)00034-1);
author copy at tedlab.mit.edu.

Read: full (author PDF of the published article, 76 pages, sections 1 to
7; reference list skimmed). Title and author match.

## Claim

The Syntactic Prediction Locality Theory (SPLT): sentence processing costs
(1) memory for each syntactic head still required to finish the sentence,
growing with the number of new discourse referents processed since it was
predicted, and (2) integration cost for attaching a word to its head,
growing with the new discourse referents in between. Together they explain
object vs subject relatives, nesting overload, heaviness, cross-serial vs
nested dependencies and several ambiguity preferences. Section 6 sketches
the variant later called the Dependency Locality Theory, where only
integration cost grows with distance.

## Method and data

Theory paper. Predictions are worked word by word and compared with
self-paced reading (King and Just 1991; Gibson and Ko, 32 items), rating
questionnaires (Gibson and Thomas 1997; Gibson and Warren 1998; Babyonyshev
and Gibson 1997) and published studies in English, Japanese, Dutch,
German and Finnish.

## Results (numbers that matter)

- Distance is counted in new discourse referents: the head noun of a new
  NP and a tensed verb (an event). First- and second-person pronouns are
  already in the discourse and cost nothing; a third-person pronoun with
  no antecedent is as costly as a name (Gibson and Warren ratings).
- Untensed embedded verbs cost less than tensed ones (Gibson and Thomas
  ratings, "neglecting" vs "were neglecting").
- Section 2.6.4 suggests predicates (adjectives, contentful prepositions)
  may also add cost; the evidence is from attachment ambiguities only.
- Section 2.6.7: memory and integration cost are not linear. The cost of
  one prediction stops growing after two or three intervening referents;
  Gibson proposes a sigmoid, M(n) = 1/(1 + e^(-n+2)).
- Overload generalization (section 3.5): a sentence is unacceptable when
  some parse state holds at least two long unresolved predictions (each
  spanning three or more new referents) besides the top-level verb; one
  long prediction alone is tolerated.
- Intuitive complexity follows the maximum cost at any point in the
  sentence, not the average; adding right-branching clauses does not
  change it.
- For the SC/RC vs RC/SC contrast a word-count or morpheme-count distance
  gives the same predictions as referent counts.
- Heaviness: integration crossing four referents (I(4)) at "about" in
  "talked to the visitor who ... about the problem" vs I(0) and I(1) when
  the heavy phrase comes last.

## What the full text qualifies

- The linear cost I(n) = n is a stated simplification used only for the
  worked examples.
- Doubly nested relatives are not uniformly unreadable: with an indexical
  pronoun as the innermost subject they are processable (Bever 1974, "The
  reporter everyone I met trusts said ...").
- Many contrasts rest on ratings and intuition rather than reading times.
- The concluding section names grammar and style checking as a possible
  application.

## For readcost (used / tested / candidate)

Not cited in readcost's docs; Gibson 2000 is. This is the fuller source.

Candidate changes:

- long-dependency measures one arc. Gibson's overload criterion is two or
  more long dependencies open at the same time, and per-arc cost that
  saturates after about three referents. A rule that counts simultaneous
  long open dependencies (or the maximum summed cost at one word) is
  closer to the theory than the longest single arc.
- The referent count readcost tried (docs/evaluation.md "Long dependency:
  words or new referents") was linear and per arc; neither the saturation
  nor tensed vs untensed verbs nor the pronoun distinction beyond
  "pronouns do not count" was tested.
- Heaviness: the theory predicts the cost of a long phrase placed before a
  short one ("gave [long NP] to her"); readcost's suggestion "move long
  modifiers after the verb" matches.

## Open questions

- Whether "two long open dependencies at one word" separates the raters'
  accepted and rejected long-dependency findings better than word
  distance (AUC 0.68).
