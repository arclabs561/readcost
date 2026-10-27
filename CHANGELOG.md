# Changelog

All notable changes to readcost are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com), and versions follow semantic
versioning; before 1.0, a minor version can change output formats and
configuration.

## [Unreleased]

### Added

- `readcost style FILES --against NAME` compares rule rates, sentence length and
  predicted reading time with a reference; built-in references for the Rust
  book, Go, Python, Django, SQLite and Stripe docs, GOV.UK guidance, READMEs and
  essays. Profiles now record predicted ms per word and words per sentence.
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

### Deprecated

- `enable`, `disable`, `hooks.paths` and `hooks.exclude` still work, with a
  warning naming the newer key; they will be removed at 1.0.

### Changed

- long-dependency reports a subject, object or attribute far from its verb
  (9+ words in a sentence whose dependencies are long overall, or 15+ words
  anywhere), not the longest arc of any kind. In a blind comparison six model
  raters accepted 14 of 30 new findings and 0 of 30 old ones. New config keys
  `long_dependency_core_min` and `long_dependency_core_always`.

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
