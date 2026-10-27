# Automatic Measurement of Propositional Idea Density from Part-of-Speech Tagging

Cati Brown, Tony Snodgrass, Susan J. Kemper, Ruth Herman, Michael A.
Covington. 2008. Behavior Research Methods 40(2), 540-545. DOI
[10.3758/BRM.40.2.540](https://doi.org/10.3758/BRM.40.2.540); NIH author
manuscript PMC2423207.

Read: full (PMC author manuscript: introduction, implementation, usage,
algorithm, validation, applications). Title and authors match.

## Claim

CPIDR 3 counts propositions (in the sense of Kintsch 1974 and Turner and
Greene 1977) from part-of-speech tags plus 37 adjustment rules and agrees
with the consensus of two human raters (r = 0.97 over 80 speech samples)
better than five raters agree with each other (r = 0.82 over 10).

## Method and data

- MontyLingua tagger, Penn tags. Initially every conjunction, numeral,
  determiner, preposition, adjective, adverb, possessive, verb, relative or
  interrogative is a proposition; rules then merge verb groups ("may have
  been singing" is one), drop a/an/the, drop modals unless negated, count
  a copula only before a noun phrase.
- Validation: Turner and Greene's 69 examples (matched except a few
  stated cases); 80 transcripts of spoken recollections of 9/11.

## Results (numbers that matter)

r = 0.97 against the two-rater consensus, with CPIDR counts about 5%
higher; human raters agreed at r > 0.81.

## What the full text qualifies

- Validation is on speech, not written text.
- Readability is listed as a potential application, citing Kintsch and
  Keenan (1973); the paper itself tests nothing about reading.
- Results depend on the exact CPIDR version; the authors ask users to cite
  it.

## For readcost (used / tested / candidate)

Used only as background: metrics.py line 13 calls DEPID "the
dependency-based successor of CPIDR (Brown et al. 2008)", and
docs/research.md lists it in the references. Accurate: Sirts et al. 2017
build DEPID as an alternative to CPIDR and compare against it.

## Open questions

None for readcost.
