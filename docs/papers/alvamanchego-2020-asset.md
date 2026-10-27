# ASSET: A Dataset for Tuning and Evaluation of Sentence Simplification Models with Multiple Rewriting Transformations

Fernando Alva-Manchego, Louis Martin, Antoine Bordes, Carolina Scarton,
Benoît Sagot, Lucia Specia. 2020. ACL 2020, 4668-4679. ACL Anthology
[2020.acl-main.424](https://aclanthology.org/2020.acl-main.424).

Read: full (body and reference list; the paper has no appendix). Title and
authors match.

## Claim

ASSET gives ten crowd-written simplifications for each of TurkCorpus's
2,359 English Wikipedia sentences, made with several kinds of rewriting
(lexical paraphrase, splitting, deletion, reordering). Judges find them
simpler and more fluent than TurkCorpus and HSplit references, and BLEU
and SARI correlate poorly with human simplicity judgments when several
transformations are used.

## Method and data

- Amazon Mechanical Turk workers from the US, UK or Canada with >= 95%
  approval and > 1,000 HITs, who passed a qualification test (42 of 100
  passed). Instructions showed examples of each transformation and left
  the choice to the worker.
- 23,590 simplifications (2,000 validation, 359 test originals).
- Features from tseval: splits, compression, Levenshtein, added, deleted
  and reordered words, lexical complexity (log word rank), dependency
  depth ratio.
- Preference judgments on the 359 test sentences; 15 ratings each of 100
  system outputs for fluency, meaning and simplicity.

## Results (numbers that matter)

- Test set: 20.2% of ASSET simplifications split the sentence, 31.2% are
  compressed below 75% of the characters, 0.4% are unchanged (TurkCorpus
  16.3%). Mean 19.04 tokens per reference.
- Most simplifications in all three datasets keep the original
  dependency depth.
- Preferred as simpler than TurkCorpus 41.2% vs 20.1% (38.7% similar);
  than HSplit 59.0% vs 14.8%. TurkCorpus is preferred for meaning.
- Simplicity ratings correlate with none of the surface features
  significantly (table 6); meaning ratings fall with more edits.

## What the full text qualifies

- Individual simplifications are not rated; that a given pair is simpler
  is assumed, not checked. Raters judged simplicity on a sample.
- Deletion is allowed, so a simplification can be shorter because it
  carries less information.

## For readcost (used / tested / candidate)

Tested: docs/evaluation.md "Human simplifications" and "Model signals"
(scripts/eval_simplifications.py).

Citation accuracy: docs/evaluation.md lines 970-972 ("2,359 Wikipedia
sentences, each simplified by ten crowd workers, who could paraphrase,
delete and split", CC BY-NC 4.0) is accurate; the paper itself states
only "CC-BY-NC" without a version (not checked against the repository).

Fit: because ASSET workers could delete content, the result that the
cost index does not change per original sentence (p = 0.87) and that
long dependencies are removed 84% of the time is a statement about
rewrites that may also drop information. The paper's table 6 is a useful
prior: no surface feature, dependency depth included, tracked rated
simplicity on system outputs.

## Open questions

- The ASSET test-set preference judgments (359 originals) could serve as
  a small human check of whether readcost's findings fall in the
  simplification judges preferred.
