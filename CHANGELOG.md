# Changelog

All notable changes to readcost are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com), and versions follow semantic
versioning; before 1.0, a minor version can change output formats and
configuration.

## [Unreleased]

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
