# Rules

This page lists what each rule flags, how findings become a verdict, and
what readcost prints on real READMEs. `readcost explain RULE` prints why a
rule's construction costs the reader, how to fix it, and how model raters
judged its findings in the held-out test across formats.

## Examples

Examples are quoted sentences from the READMEs of other arclabs561
repositories on GitHub. Rules marked
constructed use a sentence written for this table instead, because the
evaluation sample had no clear real case. Each rewrite keeps every fact and
passes. `tests/test_detectors_batch.py` checks that each example still fires
its rule.

| Rule | Example | Rewrite |
| --- | --- | --- |
| stacked-nouns | "For store restart measurement, the example prints first snapshot-query cost with persisted WAND sidecars present versus after deleting those sidecars and forcing source-segment rebuilds." | "To measure a store restart, the example prints the cost of the first snapshot query twice: with the persisted WAND sidecars present, and after deleting them, which forces each segment to be rebuilt from its source." |
| long-dependency | "Comparisons keep the declared artifact-digest relation and packet-shape evidence as separate claims." | "Comparisons keep two claims separate: the relation that the artifact digests declare, and the evidence from packet shapes." |
| inanimate-subject (opt-in) | "It does not decide how text should be split; it records the chosen span." | "The caller decides how to split the text; slabs records the span it chose." |
| reduced-object-relative | "`compressed_postings` compresses an inverted-index posting list with cnk, the storage-shrink use case these ID-set codecs exist for." | "`compressed_postings` uses cnk to compress the posting list of an inverted index. Storing ID sets in less space is what these codecs are for." |
| hyphen-compound | "The missing-pattern check in `gitignore_audit` is a pattern-presence heuristic." | "The missing-pattern check in `gitignore_audit` only looks for whether a pattern is present." |
| inline-list | "`durability` provides filesystem and in-memory directories, atomic writes, WALs, record logs, checkpoint files, CRC validation, and sync helpers." | a bulleted list |
| participial-clause (opt-in) | "The page updates automatically when the file changes on disk, highlighting what changed." | "The page updates automatically when the file changes on disk and highlights what changed." |
| nominalization (opt-in, constructed) | "The tool performs validation of the input." | "The tool validates the input." |
| center-embedding (opt-in, constructed) | "The job that the script that the team maintains starts fails when the disk is full." | "The team maintains a script that starts the job, and the job fails when the disk is full." |
| undefined-acronym (opt-in, constructed) | "Each shard writes its changes to the WAL before it updates the index." | "Each shard writes its changes to the write-ahead log (WAL) before it updates the index." |

Turn any opt-in rule on with a level, such as `--info nominalization` or
`nominalization = "info"` under `[readcost.rules]`. `long-sentence` is also
available but off by default. denominal-verb and repeated-frame were removed
in 0.3 ([evaluation](evaluation.md#opt-in-rules-on-every-corpus-provisional)).

## Notes on each rule

The first four rules come from "Why is AI-generated language so hard to
understand?" ([arXiv 2610.29162](https://arxiv.org/abs/2610.29162)). The
paper finds that recent language models use these constructions more often
than paraphrases of the same content do. Against human corpora, the
difference is consistent only for inanimate subjects. Earlier studies, mostly
of constructed sentences, tie each construction to harder reading, some with
reading times and some with brain responses. `hyphen-compound` and
`inline-list` are derived from where those constructions show up in technical writing.

### stacked-nouns

Three or more nouns in a row. A hyphenated word counts as one noun, so
`storage-shrink job` is a hyphen compound, not three stacked nouns. By
default a stack of five or more nouns is an error; shorter stacks are
warnings.

### long-dependency

A subject far from its verb, or a verb far from its object, judged against
the reference profile at the same sentence length (see [Verdicts](#verdicts)).
When the sentence gives a reason (because, since, so that, otherwise), the
suggestion says to keep that reason when splitting the sentence.
`long_dependency_gap = "content"` reports a gap filled only by prepositional
phrases at info ([configuration](configuration.md)).

### inanimate-subject

A thing doing a person's action: a verb that normally takes a person as
subject, such as own or decide, with a file or a function as its subject. It uses word lists derived from
WordNet, so treat its findings as prompts to reread, not verdicts. An
identifier as a subject (`` `parse()` returns ``) is not reported.

It is opt-in after 0.3.0. On READMEs the rules had not been tuned on, three
blind model raters accepted none of 40 of its findings, and judged the
construction present in 9
([evaluation](evaluation.md#held-out-precision-pre-registered)). The
paper finds this construction more often in model text than in human
corpora; the detector, not that result, is what failed. Turn it on
with `inanimate-subject = "info"` under `[readcost.rules]`.

### reduced-object-relative

An object relative clause without "that" (the format the reader expects).
Object relatives cost more to read than subject relatives, and dropping the
optional "that" removes the cue that one has started.

### hyphen-compound

An ad hoc hyphenated noun compound, such as storage-shrink or region-index.
Such compounds are rare word pairs, which the paper links to slower reading.
Pairs found in 5 or more documents of a 2019 FineWeb-Edu crawl are skipped
(ODC-By; see `src/readcost/data/FINEWEB_NOTICE`).

### inline-list

Four or more coordinated items in one sentence, or items joined by slashes.
As with long-dependency, a sentence that gives a reason gets a suggestion to
keep the reason when splitting it.

It is off in doc comments and docstrings. In the test across formats, model
raters accepted 1 of 28 of its findings there, against 5 of 16 in Markdown
([evaluation](evaluation.md#precision-across-formats-pre-registered)). A
level for it in `[readcost.rules]` or an override turns it back on.

### participial-clause

Opt-in. A present participle clause set off by a comma (", making X faster").
It leaves the reader to work out its subject and how it relates to the main
clause. Language models use it more often than people (Reinhart et al. 2025).

### nominalization

Opt-in. An action written as a noun (performs validation of). It is flagged
only after a light verb such as perform, or when two such nouns with "of"
share a sentence. Language models use it more often than people
(Reinhart et al. 2025).

### center-embedding

Opt-in. A clause nested two deep inside clauses that continue after it, which
people judge hard in constructed sentences unless the innermost subject is I,
you or we (Gibson 1998, 2000).

### undefined-acronym

Opt-in. An acronym used before it is spelled out, which readers rated as
harder to read in one small report (Hales, Williams and Rector 2017). Common
acronyms such as API and JSON are skipped.

### What every rule skips

Technical writing repeats compressed terms on purpose, so a stacked or
hyphenated compound is reported once per document, at its first use. Code
spans, URLs and file paths count as single words.

## Verdicts

Each finding counts 0.5 (info), 1 (warn) or 2 (error). The cost index is that
count per 1,000 words. A file passes below 15, gets "advise" at 15 or more, and
gets "block" at 30 or more with at least 3 weighted findings. One error finding
also makes a file "advise" whatever its rate; by default only a stack of five
or more nouns is an error, and `advise_severity` changes the level. Of 110 essays,
documentation pages and READMEs by well-regarded writers (150 words or more,
held out from the reference profile), 107 pass and 3 get "advise"; the median
cost index is 3.2 (measured 2026-10-26).

Commit messages (`--format commit`, the `commit-msg` hook) are judged against
their own thresholds, 50 and 100, because they are terser than prose: in 1,000
Go commit messages the 99th percentile cost index is 49, against 8 to 16 for
essays, docs, READMEs and discussion. Benchmark tables, shell commands and the
`pkg/path:` scope prefix of the subject line are not read as prose.

A rate is noisy for a short text: one finding in a 20-word comment is 50 per
1,000 words. Below 40 words, readcost counts weighted findings instead: 2 or
more gets "advise" and 3 or more gets "block".

Dependency length is judged against a reference profile: how far apart
related words usually are, by sentence length, in a swatch of essays,
documentation and READMEs by well-regarded writers (126 texts from 22 sources,
listed in `src/readcost/data/default_profile.json`). To compare against
writing that you prefer, build your own:

```sh
readcost profile build path/to/good/*.md -o myprofile.json --name mine
readcost check --profile myprofile.json README.md
```

## Real output

Checked with the default settings on the READMEs of other arclabs561
repositories; `scripts/readme_gallery.py` regenerates this from pinned commits.

```text
warn[stacked-nouns]: three or more nouns in a row
  --> cnk/README.md:61:48
   |
61 | ...presses an inverted-index posting list with cnk, the storage-shrink u...
   |                        ^^^^^^^^^^^^^^^^^^ 3 nouns stacked
   |
   = why: Readers must work out how the nouns group before they can read on, and
          the grouping is often ambiguous (Squad Helps Dog Bite Victim).
   = help: Keep at most two nouns together. Unpack the rest with a preposition
           or a relative clause, if the result reads naturally; leave an
           established term as it is.
   = example: 'forcing source segment rebuilds' -> 'forcing each segment to be
              rebuilt from its source'

warn[hyphen-compound]: ad hoc hyphenated noun compound
  --> cnk/README.md:61:81
   |
61 | ... list with cnk, the storage-shrink use case these ID-set codecs exist...
   |                        ^^^^^^^^^^^^^^^^^^^^^^^ coined compound modifier
   |
   = why: Coined compounds such as storage-shrink or region-index are rare word
          pairs, which the paper links to slower reading.
   = help: Write the relationship out.
   = example: 'the storage-shrink use case' -> 'the main use: storing ID sets in
              less space'

info[reduced-object-relative]: object relative clause without 'that'
  --> cnk/README.md:61:100
   |
61 | ... with cnk, the storage-shrink use case these ID-set codecs exist for.
   |                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
   |                                      object relative without 'that'
   |
   = why: Object relatives (the house the contractors built) cost more to read
          than subject relatives; dropping the optional 'that' removes the cue
          that one has started.
   = help: Keep the 'that', or turn it into a subject relative or a separate
           sentence.
   = example: 'the format the reader expects' -> 'the format that the reader
              expects'

info[inanimate-subject]: thing doing a person's action
 --> lexir/README.md:7:60
  |
7 | ...ranks caller-provided token streams. Its in-memory index owns postings
  |                                                       ^^^^^-^^^^
  |                                    a person's verb with a non-person subject
  |
  = why: Verbs such as own, decide, promise, claim, hide or swallow normally
         take a person as subject.
  = help: Make the person the subject, or state the fact directly: what is out
          of scope, what is returned, what is not guaranteed.
  = example: 'It does not own indexing or compaction.' -> 'Indexing and
             compaction are left to the caller.'

info[inline-list]: long list inside a sentence
 --> durability/README.md:8:68
  |
8 | ...y` provides filesystem and in-memory directories, atomic writes, WALs,
  |                                                             ^^^^^^^^^^^^^
9 | record logs, checkpoint files, CRC validation, and sync helpers.
  | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  | 6 items listed in one sentence
  |
  = why: Four or more coordinated items, or items joined by slashes, stretch the
         sentence's dependencies and are hard to scan.
  = help: Use a bulleted list.
  = example: 'It supports standard/Sugeno/Yager negations, OWA, power means, and
             uninorms.' -> a bulleted list
```

## Other tools

| Tool | Checks | How |
| --- | --- | --- |
| readcost | Sentence constructions that models overuse; reading time | A dependency parse of each sentence; a model fitted to eye-tracking data |
| Vale | Your style guide: terms, phrases, capitalization | Rules you write: patterns, word lists, part-of-speech sequences |
| proselint | Usage advice gathered from authors and editors | Built-in checks |
| write-good | Passive voice, weasel words, wordy phrases | Word patterns |
| LanguageTool | Grammar, spelling, punctuation | Grammar rules and models |
| Readability formulas (Flesch-Kincaid) | A grade for a whole text | Word and sentence length |

Vale's part-of-speech rules can match a run of nouns, but Vale, proselint and
write-good do not parse which word depends on which. So they cannot measure
the distance from a subject to its verb or find an object relative without
"that". readcost works next to Vale rather than instead of it;
[vale.md](vale.md) has a CI recipe that runs both. A readability formula
tracks how hard a whole text is better than readcost's cost index does (see
[evaluation](evaluation.md)); readcost's job is to say which sentence to
change.

readcost does not check grammar or spelling, and it does not enforce a style
guide. Whether a text is correct, complete or clear in meaning is out of its
scope, although developers rate ambiguity, incompleteness and incorrectness
as the worst documentation failures. It does not tell who wrote a text.

## Reporting a false positive

readcost is advisory, and many findings are wrong (see [Limits](#limits)).
When one is, open an issue with the
[false positive form](https://github.com/arclabs561/readcost/issues/new?template=false-positive.yml).
The form asks for the rule, the message, the sentence, where the sentence
was, and why the finding is wrong. When there are findings, text and agent
output end with a line that links to the issue chooser, which lists the form.
`feedback_link = false` in `readcost.toml` turns that line off. The hooks
never add it, since a model cannot act on it.

## Limits

The README lists the main limits. This is the full list.

- readcost is not an AI-text detector. Construction rates and reading-time
  estimates must not be used to judge who wrote a text: the same patterns
  appear in human writing, and treating them as markers penalizes non-native
  English writers in particular.
- English only. readcost skips text that is clearly in another language,
  judged from its script and its function words, and gives a note instead of
  findings or a reading time; `language_check = false` turns that off. On 2,132 English
  texts in the evaluation corpora the check skipped none.
- The default spaCy model misparses some sentences. A sentence parsed with no
  verb is skipped, unless it ends with a full stop and a plural noun inside a
  noun run looks like the verb ("the job reruns merge planning"); then only
  `stacked-nouns` and `hyphen-compound` run on it. A misparse can produce a false
  finding. Set `model = "en_core_web_trf"` for better parses at 30 or more
  times the cost, or `verify_model` ([configuration](configuration.md)) to
  have a second parser check three rules' findings.
- inanimate-subject uses word lists derived from WordNet. Treat its findings
  as prompts to reread, not verdicts.
- Precision is low on well-edited prose. Ten model raters from different labs
  labelled 210 findings sampled from essays and documentation by well-regarded
  writers. Of the 64 that the current rules still report, a majority of eight
  raters judged 15 (23%) correct or defensible (single raters: 16 to 48%; two
  lenient raters: 75 to 77%). Agreement between raters is modest (Fleiss' kappa 0.40
  over the eight). The rules were revised after the first rater's labels on
  this sample were read, and the two lenient raters were set aside after
  theirs were seen, so 23% is an in-sample estimate. In a pre-registered test
  on new READMEs, three blind model raters accepted 30% (23 to 38%), nearly
  all of it as "defensible", and none of inanimate-subject's findings
  ([evaluation](evaluation.md#held-out-precision-pre-registered)).
  `readcost explain RULE`
  shows the count for each rule. See [evaluation](evaluation.md).
- Every label behind these numbers comes from a model rater. No person has
  labelled a finding, and agreement among model raters is not a measured
  cost to readers.
- Most studies that tie these constructions to harder reading used
  constructed sentences, one at a time. Whether fewer findings in ordinary prose
  goes with faster reading has not been shown. On Natural Stories
  self-paced reading, flagged sentences were not read more slowly once
  length, frequency and surprisal were in the model, and words inside a
  finding were read about 1% more slowly, an effect that did not hold
  across sentences. Human ratings of simplified sentences and of sentences
  in biomedical abstracts did not track findings either
  ([evaluation](evaluation.md#human-reading-times-gold-parses-and-human-ratings)).
  On OneStop's 162 pairs of original and simplified paragraphs, the change
  in findings did not predict the change in observed reading time once word
  length and frequency were in the model (+1.3 ms per word per finding point
  per 100 words, 95% CI -7.1 to +9.5; [evaluation](evaluation.md#paired-paragraphs-findings-against-observed-reading-time)).
- In seven rating sets of 52,000 texts, weighted findings did not track
  readers' ratings once length and word frequency were held (partial
  correlations -0.01 to +0.08). In GECO, a novel read by 14 people, sentences
  with findings were read slightly more slowly per word (r = +0.05, 95% CI
  +0.02 to +0.09), with surprisal not held. OneStop showed nothing, and Provo
  had too few flagged passages to test
  ([evaluation](evaluation.md#many-datasets-with-human-signals)).
- Against hand-corrected parses of web and mixed-genre text, 81 to 84% of
  stacked-nouns findings, 60% of reduced-object-relative findings and 61 to
  67% of long-dependency findings name a construction that is there. The
  rest are the parser's errors.
- No suggested rewrite has been tested on readers. In one study, splitting
  ordinary noun phrases made sentences look easier and understood slightly
  worse on average (Leroy et al. 2016); it did not test technical stacks.
  Keep a rewrite only if it reads naturally.
- The paper's findings are about how often text uses these constructions,
  not about any single sentence, and it ran no reading study on model text.
- The paper also measures rare word pairs. readcost uses word-pair counts only
  to skip hyphenated pairs in common use; it does not flag rare pairs in
  general yet.
- The default profile is edited English technical and essay prose. A cost
  index for chat answers is not comparable to one for READMEs.
