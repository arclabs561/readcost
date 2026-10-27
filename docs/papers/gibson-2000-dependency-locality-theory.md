# The Dependency Locality Theory: A Distance-Based Theory of Linguistic Complexity

Edward Gibson. 2000. In A. Marantz, Y. Miyashita and W. O'Neil (eds.),
Image, Language, Brain, MIT Press, 95-126. Author copy at
tedlab.mit.edu (Gibson_2000_DLT.pdf).

Read: full (scanned chapter, 32 pages). The text layer is OCR and is
scrambled on several pages (99, 102-104, 116-119); those pages were read as
page images. Title and author match.

## Claim

Sentence comprehension spends resources on storage (one memory unit per
syntactic head still required) and on integration, whose cost depends on
the distance between a word and the head it attaches to. The DLT explains
nesting complexity, the object vs subject relative contrast, the pronoun
effect in doubly nested relatives, the RC/CC asymmetry, Japanese nesting
and some ambiguity preferences.

## Method and data

Theory chapter with worked examples. Evidence: Warren and Gibson (1999)
rating questionnaire (1 to 5 scale) on doubly nested relatives with a
pronoun, a name or a description as innermost subject; Gibson and Ko
(1998) self-paced reading of subject and object relatives (32 participants,
16 items); Babyonyshev and Gibson (1999) Japanese ratings; Gibson, Grodner
and Tunstall (1997) self-paced reading of the MV/RR ambiguity inside a
relative clause (60 participants).

## Results (numbers that matter)

- Section 5.3.1: 1 energy unit for each new discourse referent between
  the two words (head noun of a new NP, head verb of a new event), plus 1
  if the word itself heads a new referent. This is a stated simplification
  of an accessibility scale (pronouns, focused entities, names,
  descriptions, new indefinites); it separates only new from old.
- The chapter says the cost rises with the first few intervening referents
  and then levels off toward a maximum, and that one long integration is
  never as costly as several shorter ones at the same word.
- Doubly nested "The reporter who the senator who John met attacked
  disliked the editor": 7 units at "attacked"; with "I" for "John", 5.
  Pronoun versions are rated significantly easier.
- DLT integration cost against residual reading times by region: r = 0.79
  (object relatives), 0.77 (subject relatives), 0.77 combined (r squared
  0.59, p < 0.005), over six regions, reading times corrected for word
  length.
- Nesting is defined as A inside B with material of B on both sides.

## What the full text qualifies

- The chapter does not use nesting depth as its measure. Depth two is hard
  in the examples because several long integrations land on the same verbs;
  with a pronoun as the innermost subject the same depth is easy ("A book
  that some Italian that I have never heard of wrote will be published").
- The evidence for doubly nested difficulty is ratings and intuition; the
  reading-time evidence is for single relative clauses.
- The referent count is a first approximation. Adjectives, prepositions
  and old referents probably add some cost too.

## For readcost (used / tested / candidate)

Used: center-embedding rule and metrics (features.py line 147, 635;
metrics.py line 15), the opt-in referent measure for long-dependency
(features.py lines 557-575, config.py line 112), docs/research.md lines
36-39 and 48-51, README.md lines 184-185 and 413.

Citation accuracy:

- docs/research.md lines 37-39, "Gibson (2000) shows that readers lose
  track at that depth in constructed sentences"; features.py line 147 and
  635, "one nested clause is ordinary; two is where readers lose track";
  README.md line 185, "which readers fail to follow". Partly accurate. The
  chapter shows that doubly nested object relatives with new referents are
  rated very hard, and that the same depth with a pronoun innermost subject
  is easy. The claim needs that condition; as written it attributes a depth
  threshold the DLT rejects.
- docs/research.md lines 48-49, "measures a gap by the new nouns and verbs
  in it": accurate as a summary of the simplified cost.
- features.py lines 560-566: section 5.3.1 is the right section.
  "Pronouns refer to entities already in the discourse and do not count"
  goes beyond the chapter for third-person pronouns, which count as new
  when they have no antecedent in Gibson 1998, but matches its treatment of
  "I" and "you". "Gibson's simplification treats every noun phrase as new"
  is not quite what the chapter says: it treats every new referent as new
  and every old one as free; names and descriptions count as new in its
  examples.
- The readcost referent rule is linear and per arc; the chapter says
  neither is right in general (saturation, several integrations at one
  word).

## Open questions

- A center-embedding rule that exempts innermost pronoun subjects would
  follow the chapter's own counterexamples.
- Counting several long integrations at the same word, rather than the
  longest arc, is the DLT's actual difficulty measure (see the Gibson 1998
  note).
