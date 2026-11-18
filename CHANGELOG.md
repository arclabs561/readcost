# Changelog

All notable changes to readcost are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com), and versions follow semantic
versioning; before 1.0, a minor version can change output formats and
configuration.

## [Unreleased]

### Added

- `verify_model` (opt-in): a small ONNX dependency parser
  (`readcost setup --verifier`, extra `verify`) checks stacked-nouns,
  reduced-object-relative and long-dependency findings, with parses cached
  by sentence hash. Off by default. `scripts/eval_second_parser.py` and the
  `second-parser` eval job measure it, en_core_web_trf and two other checks
  against UD gold parses; results in docs/evaluation.md.
- Every finding has `start` and `end`, character offsets of the flagged
  words in the source file, with `sentence_start` and `sentence_end`.
  Markdown, reStructuredText, HTML, source comments, commit messages and
  plain text all map back to the file, through code spans, links, character
  references, CRLF line ends and wrapped sentences. Text taken from JSON has
  no offsets. JSON output adds the four fields and keeps `column`,
  `end_line` and `end_column`, which now come from the offsets. SARIF
  regions gain `startColumn`, `endLine`, `endColumn`, `charOffset` and
  `charLength`. Language server diagnostics cover the exact words, over
  several lines when the sentence is wrapped.
- `readcost label export`, `import`, `agreement` and `convert`, and the
  `readcost.labels` module: a JSON Lines format for labels on findings (one
  line per rater per finding, keyed by document, version, offsets and rule),
  a blind sheet for people to fill in, Fleiss' kappa with category
  frequencies, Cohen's kappa per pair, and majority votes. docs/labels.md
  describes it.
- `long_dependency_gap = "content"` (opt-in): long-dependency says what fills
  the gap (an object relative clause, another clause, only prepositional
  phrases, or no clause) and reports a gap of prepositional phrases at info.
  The default, `"words"`, is unchanged. `scripts/eval_gap_content.py` splits
  the labelled findings by gap class.
- Evaluations against existing human data, with no new labels:
  `scripts/eval_naturalstories_rt.py` (self-paced reading times),
  `scripts/eval_gold_treebank.py` (UD English EWT and GUM gold parses),
  `scripts/eval_simplicity_ratings.py` (five sets of rated simplifications)
  and `scripts/eval_rated_sentences.py` (PLABA-EVAL). Results, including
  the nulls, are in docs/evaluation.md.
- `scripts/eval_stack_terms.py` and `scripts/build_open_pairs.py` test
  whether counts of word pairs, counts of the whole phrase, bracketing or
  the document tell an established term from a coined noun stack; the eval
  workflow's `stack-terms` job runs them. On the labelled findings nothing
  separated the two, so no rule changed. docs/research.md says what the
  human-label study should measure.

- `readcost style FILES --against NAME` compares rule rates, sentence length and
  predicted reading time with a reference; built-in references for the Rust
  book, Go, Python, Django, SQLite and Stripe docs, GOV.UK guidance, READMEs and
  essays. Profiles now record predicted ms per word and words per sentence.
- `readcost corpus` measures repetition across many texts: syntactic templates,
  CR-POS and repeated sentence openers (Shaib et al. 2024).
- Text that is clearly not English gets a note instead of findings and a
  reading time, which would be meaningless (`language_check`).
- Rule levels as in ty: `[readcost.rules]` sets each rule to `error`, `warn`,
  `info` or `ignore` (`all` for every rule), `[[readcost.overrides]]` sets them
  per path, and `--error`, `--warn`, `--info` and `--ignore` set them from the
  command line.
- `[readcost.src]` with `include`, `exclude`, `extend_exclude` and
  `respect_ignore_files`, and the flags `--exclude`, `--force-exclude`,
  `--no-respect-ignore-files` and `--exit-zero`.
- `readcost compare OLD NEW`: predicted reading time in total and per word,
  findings by rule, the verdicts, and the findings only in the rewrite;
  `--fail-on slower` or `worse` for CI checks on rewrites.
- `readcost check --hotspots N` lists the sentences predicted to cost the
  most reading time beyond their length (experimental); the JSON output has
  `hotspots` for every file.

- JSON output has a `metrics` object per file: lexical diversity (MTLD),
  idea density (DEPID), mean and maximum center-embedding depth, and the share
  of words in four sentence-length bands. It never changes the verdict.
- Opt-in rules center-embedding (a clause nested two deep inside clauses that
  continue after it) and undefined-acronym (an acronym used before it is
  spelled out), both at info severity.
- Removed rules: denominal-verb, whose findings raters rejected almost
  entirely in two separate samples (1 of 32 correct or defensible in the
  210-finding sample, 3 of 40 in the opt-in sample), and repeated-frame, which marks
  model text, makes no claim about reading cost, and is covered across texts
  by `readcost corpus`. A config or flag that names one warns and is ignored;
  a readcost directive that names one is ignored without a note.
- `scripts/eval_corpus.py --info RULES` turns on opt-in rules for a corpus run.

- JSON findings carry `column`, `end_line` and `end_column`, and `precision`
  (how many labelled findings of that rule raters accepted); `-o agent` shows
  the same share and asks the model to rewrite only where a finding holds.
- `readcost compare` reads the old text from git as `REV:PATH`
  (`readcost compare HEAD:README.md README.md`).
- docs/agents.md: using readcost from a coding agent, with an AGENTS.md
  snippet.

- `readcost check DIR` crawls large trees: inside a repository it lists what
  git tracks or would track (nested repositories by their own ignore files);
  elsewhere it never descends into hidden directories or ones `[readcost.src]
  exclude` matches. From 16 files it checks in parallel processes (`-j N`).
  With the reading-time and allowed-term speedups, the 235-file evaluation
  corpus takes 14 s instead of 112 s, with identical output.

### Deprecated

- `enable`, `disable`, `hooks.paths` and `hooks.exclude` still work, with a
  warning naming the newer key; they will be removed at 1.0.

### Changed

- long-dependency reports a subject, object or attribute far from its verb
  (9+ words in a sentence whose dependencies are long overall, or 15+ words
  anywhere), not the longest arc of any kind. In a blind comparison six model
  raters accepted 14 of 30 new findings and 0 of 30 old ones.
- Rule and verdict thresholds are no longer config keys: `stacked_nouns_min`,
  `long_dependency_z`, `long_dependency_min_tokens`, `inline_list_min_items`,
  `long_sentence_words`, `block_min_points`, `short_text_words`,
  `short_advise_points`, `commit_advise_cost_index` and
  `commit_block_cost_index` now warn and are ignored. They were set from the
  evaluation corpus; change a rule's level instead. `advise_cost_index`,
  `block_cost_index` and `advise_severity` stay.
- The stacked-nouns advice is conditional: unpack only if the result reads
  naturally, and leave an established term alone. README "Limits" says that
  all labels come from model raters, that the supporting studies used
  constructed sentences, and that no rewrite has been tested on readers.
- docs/agents.md keeps `readcost compare` as information; `--fail-on worse`
  is for rewrites that should not grow, and predicted reading time is not a
  target. `scripts/eval_onestop_pairs.py` tests whether fewer findings go
  with faster reading on OneStop's paired paragraphs; the `eval` workflow
  runs it, and it finds no effect (docs/evaluation.md).

### Fixed

- A finding in a Python docstring after a line that ends in a backslash was
  reported one line too high.
- A finding's line is now counted with the line ends editors use (`\n`,
  `\r\n`, `\r`). In source comments, commit messages and plain text a form
  feed or a Unicode line separator used to count as a line end.
- stacked-nouns no longer counts a verb the tagger read as a plural noun
  after another plural ("merge-commit subjects scores high") when a real verb
  sits above it.
- Predicted reading time no longer falls the longer a paragraph runs past the
  longest training paragraph (165 words): one long paragraph read 17% faster
  than the same text split into paragraphs, now 4%. Reference profiles are
  rebuilt.
- numpy is a declared dependency (readtime imports it). `uv sync` sets up
  development with a lock file, and `uv run --group eval` runs the evaluation
  scripts; scripts whose inline metadata names readcost now use the checkout
  instead of the PyPI release.
- A sentence whose verb the parser read as a noun ("The index shard
  compaction job reruns merge planning every hour.") was skipped as having
  no verb, so the densest noun stacks went unreported. When such a sentence
  ends with a full stop, and a plural noun inside a noun run comes after a
  determiner and before an object or adverb, stacked-nouns and
  hyphen-compound now run on it; the other rules still skip it. A plural
  head followed by its object is read as the verb ("one correlation
  parameter fixes most of this"), which also drops two old false positives
  in this repository's docs.
- The generic hook and `readcost.hooks.generic.review()` read `lines` as the
  CLI does: `40-` runs to the end, `-5` is lines 1 to 5, and a malformed or
  reversed range is an error (exit 2) instead of a Python error or no lines.
- inanimate-subject no longer reports "blow up", "pick up" or "wake up" with
  a thing as subject ("large inputs blow up the memory use").
- stacked-nouns no longer counts the first half of a suspended hyphen
  ("four- to sevenfold") as a noun.
- long-dependency prints `(z = ...)` only when z triggered the finding; a gap
  of 15+ words reported at a low z no longer shows a z that argues against it.
- stacked-nouns no longer reports a person's name at the start of a
  sentence ("Guido van Rossum wrote ...").
- A file that is not valid UTF-8 gets a note, and its undecodable bytes
  become U+FFFD instead of being dropped ("Café" in Latin-1 read as "Caf").

## [0.2.0] - 2026-10-26

First release on PyPI (`pip install readcost`, or `uvx readcost`).

### Added

- Default output quotes each flagged line with carets under the words, in the
  style of the Rust compiler: the rule as a headline, the specific finding as a
  label at the carets, the fix, and once per rule why it costs the reader and
  an example rewrite, all within 80 columns. Colour on a terminal (`--color`,
  `NO_COLOR`). `-o concise` prints one `path:line:col` line per finding
  ([#24](https://github.com/arclabs561/readcost/pull/24),
  [#29](https://github.com/arclabs561/readcost/pull/29)).
- `readcost explain` shows how often model raters accepted each rule's findings
  on well-regarded writing ([#34](https://github.com/arclabs561/readcost/pull/34)).
- `readcost: ignore`, `off` and `on` comments in Markdown can name rules,
  turning off only those; an unknown rule name is reported in the notes
  ([#27](https://github.com/arclabs561/readcost/pull/27)).
- `readcost lsp`, a language server for editors, as the optional extra
  `readcost[lsp]` ([#23](https://github.com/arclabs561/readcost/pull/23)).
- `readcost baseline` and `check --baseline` record today's findings so that
  only new ones count when adopting readcost in an existing repository
  ([#22](https://github.com/arclabs561/readcost/pull/22)).
- The GitHub Action can post one pull request comment (`comment: true`) and
  checks only changed files by default; `-o pr-comment` renders that comment.
  A false-positive issue form and a link to it after findings
  ([#21](https://github.com/arclabs561/readcost/pull/21)).
- The spaCy model is downloaded on first use, checksum verified, into
  `~/.cache/readcost`, so readcost runs under `uvx` with no setup step
  ([#19](https://github.com/arclabs561/readcost/pull/19)).
- Predicted reading time per file, from a model trained on eye-tracking data
  ([#12](https://github.com/arclabs561/readcost/pull/12)).
- Separate thresholds for commit messages
  ([#13](https://github.com/arclabs561/readcost/pull/13)).
- Opt-in rules: nominalization, participial-clause, repeated-frame
  ([#7](https://github.com/arclabs561/readcost/pull/7)).

### Changed

- The default reference profile is built from 126 essays, documentation pages
  and READMEs from 22 sources instead of one writer's twelve READMEs.
- `-o text` is now `-o concise`, and the default output is the new quoted
  form ([#24](https://github.com/arclabs561/readcost/pull/24)).
- denominal-verb is off by default: on edited prose almost every hit was a
  settled verb.
- Hyphenated compounds that are common word pairs in a large web corpus are
  no longer flagged ([#10](https://github.com/arclabs561/readcost/pull/10)).

### Fixed

- A number joined to its unit ("17-month", "one-hop", "64-bit") is a modifier,
  not a noun in a stack.
- inanimate-subject no longer flags groups of people ("a majority of eight
  raters judged"): a quantity noun takes the animacy of what it counts.
- Issue and pull request references (`owner/repo#123`, `#123`, `gh-123`) count
  as single words, like URLs, so they are no longer read as coined compounds.
- Fewer false positives: a misparsed verb inside a noun stack ("specification
  defines slices"), a main clause read as an object relative ("The help output
  begins with:"), and a row of links read as prose
  ([#28](https://github.com/arclabs561/readcost/pull/28)).
- Precision fixes for pronoun subjects, light relative heads, names before
  noun stacks and package paths in slash lists
  ([#9](https://github.com/arclabs561/readcost/pull/9)).
- HTML blocks inside Markdown are read as prose with correct line numbers
  ([#14](https://github.com/arclabs561/readcost/pull/14)).

## [0.1.0]

Not published. The first tagged state of the repository.

[Unreleased]: https://github.com/arclabs561/readcost/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/arclabs561/readcost/releases/tag/v0.2.0
