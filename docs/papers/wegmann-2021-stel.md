# Does It Capture STEL? A Modular, Similarity-based Linguistic Style Evaluation Framework

Anna Wegmann, Dong Nguyen. 2021. EMNLP 2021 (per the acknowledgements and
the later papers that cite it). arXiv
[2109.04817](https://arxiv.org/abs/2109.04817).

Read: full (arXiv v1: body, limitations, ethics, appendix on annotation
setup, screening questions and annotation analysis). Title and authors
match the arXiv ID. Tables 2 and 3 were read from a layout-preserving
extraction.

## Claim

A style measure can be tested without training data by asking it to match
two paraphrase pairs that differ along the same style dimension. Off the
shelf, BERT-based embeddings do this better than character n-grams,
punctuation, word length or LIWC.

## Method and data

- Task (quadruple setup): anchors A1, A2 are paraphrases split along one
  style; sentences S1, S2 are another such pair. Order S1, S2 to match the
  anchors. Any model that returns a similarity between two sentences can be
  scored.
- Components: formal/informal from GYAFC (Yahoo Answers, Entertainment and
  Music); simple/complex from Xu et al. 2016 (Wikipedia sentences and one of
  their 8 crowd simplifications, dropping pairs within 3 characters of edit
  distance); contractions (100 Wikipedia sentences, contraction added);
  number substitution (100 Reddit sentences, hand-translated).
- Ambiguity filter: 5 native-English Prolific workers per candidate (839
  workers, screening questions). Kept only items a majority ordered
  correctly: 815 formal, 815 complex, plus 100 and 100 characteristic
  items, 1,830 in total.
- 18 methods scored: BERT, RoBERTa, SBERT, USE, BERT NSP head, char
  3-grams, word length, punctuation, LIWC variants, deepstyle, POS tags,
  share of capitals, edit distance.

## Results (numbers that matter)

- Crowd agreement on the generated items (Table 2, quadruple, all
  candidates): formal/informal Fleiss' kappa 0.48, majority correct 90%;
  simple/complex kappa 0.17, majority correct 68%. The triple setup was
  worse (simple/complex kappa 0.19, 51% on the sample).
- STEL accuracy, filtered items (Table 3): BERT cased 0.77 overall (formal
  0.82, complex 0.68); RoBERTa 0.61; SBERT paraphrase 0.68; deepstyle 0.66.
  Simple measures sit near 0.5: char 3-grams 0.55, punctuation 0.56, LIWC
  0.50 to 0.55, POS tags 0.52.
- Word length is the one simple measure better on simple/complex (0.59)
  than on formal/informal (0.53).
- Every method scores lowest on simple/complex.

## What the full text qualifies

- The benchmark keeps only items people agreed on, so scores describe the
  clear cases. On the unfiltered simple/complex items the same methods
  score equal or lower.
- The authors give an example where moving a time phrase to the front is
  labelled "simpler" by the source data but could be read either way. They
  conclude that low agreement mostly signals ambiguous items, not bad
  annotators.
- Table 2 lists n = 918 for simple/complex and 1,195 for formal/informal,
  while the text says 918 formal and 1,195 complex candidates were
  generated; one of the two is swapped. This does not change the kappas.
- STEL does not test whether a model prefers style over content; that task
  (STEL-or-Content) came in Wegmann et al. 2022.

## For readcost (candidate evidence for an evaluation caveat; not cited)

readcost's docs do not cite this paper. It bears on two evaluations in
docs/evaluation.md:

- "Human simplifications" uses ASSET, whose 2,359 originals are Wikipedia
  sentences from the same TurkCorpus line (Xu et al. 2016) that STEL's
  simple/complex data comes from. STEL found that native speakers order an
  original against a crowd simplification correctly only 68% of the time,
  with kappa 0.17. So "the simplification is simpler" is not a safe label
  for every pair. readcost's per-pair tests (signal lower in the
  simplification in X% of pairs) carry that label noise. They do not
  account for it.
- The finding that word length is the one surface feature that tracks
  simple/complex agrees with readcost's own results: word length carries
  most of the reading-time model and the CEFR-SP partial correlation
  ("Reading-time model", "Sentence difficulty rated by people").

No mismatch: the paper is not cited.

## Open questions

- Should the ASSET test keep only pairs where a readability signal and a
  human judgment agree, or report how many pairs a rater would call
  ambiguous?
