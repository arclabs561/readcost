# Memory access during incremental sentence processing causes reading time latency

Cory Shain, Marten van Schijndel, Richard Futrell, Edward Gibson, William
Schuler. 2016. Proceedings of the Workshop on Computational Linguistics
for Linguistic Complexity (CL4LC), COLING 2016, 49-58. ACL Anthology
[W16-4106](https://aclanthology.org/W16-4106/).

Read: full (10 pages, all sections). Title and authors match.

## Claim

On Natural Stories, a self-paced reading corpus written to be natural but
full of hard constructions, both Dependency Locality Theory integration
cost and left-corner parser memory-access events predict reading times
beyond 5-gram and PCFG surprisal, independently of each other. Earlier
null or negative results on newspaper text (Dundee) may reflect too few
memory-heavy constructions or readers.

## Method and data

- Natural Stories: 10 stories, 181 readers; sentence-initial and final
  words dropped; 768,023 events split into exploratory (255,554) and
  confirmatory (512,469) halves.
- Predictors from hand-corrected trees: 8 DLT variants (DLT-V: verbs cost
  more; DLT-C: a coordinate structure costs as much as its heaviest
  conjunct and dependencies out of it skip earlier conjuncts; DLT-M:
  dependencies to preceding modifiers ignored) and 12 left-corner
  variants, each at the word and three spillover positions (80 tests).
- Mixed models with position, word length, 5-gram and PCFG surprisal,
  rich random effects; Box-Cox transformed times; best predictors
  re-tested on the confirmatory half.

## Results (numbers that matter)

- The strongest effects are on the word after the target (spillover 1).
- Confirmatory: DLT-CM-S1 beta 1.10 ms per SD (t = 6.48), canonical DLT-S1
  0.63 ms per SD (t = 4.50); left-corner no-fork NoF-S1 1.54 ms per SD (t =
  8.15). Both families add to each other.
- 92% of words have DLT-CM cost of 1 or less; the predicted delay is large
  only at the rare extreme values (up to 12).

## What the full text qualifies

- The corpus is built to be hard; on edited newswire the DLT effect was
  weak in earlier work.
- Effects are small per SD; this is a broad-coverage significance result,
  not evidence that a given long dependency costs a reader much time.
- Distance-weighted left-corner predictors did worse than the boolean
  "memory access happened" predictor, so whether access happens may matter
  more than how far back it reaches.

## For readcost (used / tested / candidate)

Not cited. Two candidates for long-dependency, matching failures already
recorded in docs/evaluation.md:

- DLT-M ignores dependencies to preceding modifiers. evaluation.md's
  example "'have' and 'course' are 21 words apart" is exactly an arc from
  a fronted modifier ("Of course"); a DLT-M style exclusion of
  adverbial and fronted-modifier arcs would remove it.
- DLT-C treats a coordinated phrase as one unit as heavy as its heaviest
  conjunct; evaluation.md notes that "a long coordinated object can still
  be reported as a long gap".
- The referent count readcost tested was canonical DLT (linear, all
  nouns and finite verbs, all arcs). This paper's better-fitting variant
  adds both modifications; readcost's comparison of words vs referents
  did not test them.

## Open questions

- Would DLT-CM (with arcs to preceding modifiers dropped and coordination
  collapsed) beat word distance on readcost's labelled long-dependency
  findings, where canonical DLT reached AUC 0.61 against 0.68?
