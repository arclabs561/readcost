# Memory interference during language processing

Peter C. Gordon, Randall Hendrick, Marcus Johnson. 2001. Journal of
Experimental Psychology: Learning, Memory, and Cognition 27(6), 1411-1423.
DOI [10.1037/0278-7393.27.6.1411](https://doi.org/10.1037/0278-7393.27.6.1411).
PubMed 11713876.

Read: abstract only (paywall: APA; Semantic Scholar lists no open copy and
no author copy was found). Second-hand: the authors' own summary of this
study in Gordon, Hendrick, Johnson and Lee 2006 (JEP:LMC 32(6), PMC1766329,
introduction and experiment 2 rationale), labelled as such below.

## Claim (abstract)

In self-paced reading, the usual extra cost of object-extracted over
subject-extracted relative clauses and clefts depends strongly on the mix
of noun-phrase types (descriptions, indexical pronouns, names): two NPs of
the same type give a larger difference than two of different types. The
authors attribute this to similarity-based interference in working memory.

## Method and data (abstract)

Self-paced reading and comprehension accuracy, college students; relative
clauses and clefts; NP types crossed. Item counts, experiment count and
effect sizes are not in the abstract.

## Results (second-hand, Gordon et al. 2006)

- Object extractions had more comprehension errors and longer reading
  times than subject extractions.
- Performance was worse when the two critical NPs were matched in type
  (two descriptions, "barber ... lawyer", or two names, "John ... Bill")
  than unmatched (one name, one description), and the object-subject
  difference was larger with matched NPs.
- Gordon et al. 2006 add, from eye tracking, that the accessibility
  usually associated with NP types (pronoun, name, description) "does not
  have a strong effect"; similarity is what matters (2006 abstract).

## What the full text would qualify

Not read. Unknown from the abstract: the indexical-pronoun conditions'
exact numbers, whether pronoun-pronoun pairs were tested, and effect
sizes.

## For readcost (used / tested / candidate)

Used: docs/evaluation.md lines 179-182 and features.py lines 753-757
(reduced-object-relative skips relatives whose subject is a pronoun).

Citation accuracy:

- docs/evaluation.md lines 179-182: "the reading cost of object relatives
  depends on the mix of types of noun phrase: a description head with a
  pronoun subject costs far less than two descriptions." Consistent with
  the abstract; "far less" cannot be checked without the full text.
- features.py lines 755-756: "a pronoun subject makes an object relative
  easy to read". Imprecise. The finding is about mismatch between the head
  and the relative-clause subject, not about pronouns as such; the 2006
  follow-up says NP accessibility has no strong effect. A pronoun head
  with a pronoun subject ("someone I trust", "all you need" are handled by
  the light-head list) would be a matched pair, which the theory predicts
  is harder, not easier. In technical prose the head is almost always a
  description, so the rule's behaviour is probably right for the wrong
  stated reason.

## Open questions

- Obtain the full text (library access or the authors) to check the
  pronoun conditions before the code comment is rewritten.
