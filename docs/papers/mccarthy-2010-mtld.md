# MTLD, vocd-D, and HD-D: A validation study of sophisticated approaches to lexical diversity assessment

Philip M. McCarthy, Scott Jarvis. 2010. Behavior Research Methods 42(2),
381-392. DOI [10.3758/BRM.42.2.381](https://doi.org/10.3758/BRM.42.2.381).

Read: abstract only (paywall: Springer serves a purchase page for the PDF
that Semantic Scholar lists as "bronze" open access; no author copy found;
the academia.edu copy needs a login). Two details below are second-hand:
the .720 threshold and the corpus size come from academia.edu's
machine-generated summary of the paper and are marked as such.

## Claim (abstract)

MTLD, the mean length of word strings that keep a criterion level of
lexical variation, performs well on convergent, divergent, internal and
incremental validity and is the only index tested that does not vary with
text length. HD-D is a viable alternative to vocd-D. MTLD, vocd-D (or
HD-D) and Maas capture distinct information; the authors advise using
several rather than any single index.

## Method and data

Abstract: comparison of MTLD with vocd-D, TTR, Maas, Yule's K and HD-D on
two corpora. Second-hand (academia.edu summary): 1,584 text units across
16 registers; the criterion type-token ratio is .720.

## Results (numbers that matter)

Not available from the abstract.

## What the full text would qualify

Not read: the exact factor rule (whether a factor closes at TTR < .72 or
<= .72), the treatment of the final partial factor, whether the measure is
computed on all tokens or content words, and the minimum text length the
authors recommend.

## For readcost (used / tested / candidate)

Used: `mtld` in the JSON metrics (src/readcost/metrics.py lines 6-10, 27,
55-79; README.md line 411; docs/research.md line 46).

Citation accuracy (limited by the read depth):

- "Lexical diversity of content words (MTLD; McCarthy and Jarvis 2010)":
  MTLD as published is, to the best of the abstract's description, a
  measure over a text's words; restricting it to content words is
  readcost's choice and should be said as such. Not verifiable further
  without the full text.
- MTLD_THRESHOLD = 0.72: consistent with the second-hand .720.
- Forward and backward passes averaged, partial last factor: matches the
  standard description of MTLD but could not be checked against the paper.
- The 50-word floor is attributed to Zenker and Kyle (2021) via Shatz,
  not to this paper: correctly attributed.
- metrics.py's "higher is not better in technical prose" is readcost's own
  claim; the abstract makes no claim about quality.

## Open questions

- Get the full text to check the factor rule and whether content-word
  MTLD has been validated.
