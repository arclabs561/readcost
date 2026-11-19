# Pre-registration: precision on every kind of text readcost reads

Written 19 November 2026 (UTC), before any text from the sample below was
fetched or read. The commit that adds this file is the registration; its
timestamp on GitHub is the record. Nothing in this file changes after that
commit. Any change made later goes in a dated "Amendments" section at the
end, with the reason.

## Why

The first held-out test ([heldout-precision.md](heldout-precision.md),
"Held-out precision, pre-registered" in
[evaluation.md](../evaluation.md#held-out-precision-pre-registered))
sampled Markdown READMEs and docs files of repositories created after
1 November 2026. Four weaknesses limit what it shows:

- It covers one kind of text, while readcost also reads reStructuredText,
  HTML, doc comments and docstrings in source files, commit messages and
  pull request descriptions (README "Use"; `src/readcost/extract.py`).
- The population was odd: many READMEs were templates or written by
  models, and 748 of 3,437 were byte-identical to another.
- The decoys (random spans with made-up messages) were all rejected, so
  they set no useful baseline.
- Raters saw readcost's rule name and message, so they judged readcost's
  claim, and "accepted" (correct or defensible) was almost always
  "defensible".

This round samples established repositories, one stratum per format. In
place of random decoys it uses near misses: constructions that readcost
does not report at its default settings but would report one step past a
threshold. If raters accept near misses as often as findings, the
threshold adds nothing. It uses the twelve-rater panel and the unprimed
protocol of the amendment to the first test (pull request #99), and its
primary outcome is the share that an editor would fix ("c").

No person labels anything; every label comes from a model.

## What was seen before writing this

- The first test's pre-registration, report (`eval/heldout/report.md`) and
  its summary in evaluation.md. On READMEs, raters accepted 20 to 55% of
  each default rule's findings, and each rater called about 2% of
  default-rule findings "c". inanimate-subject was made opt-in after it
  (#98).
- The amendment of pull request #99 (branch `exp/heldout-panel`) and its
  unprimed rubric; `docs/prereg/edit-arms.md` on branch `exp/edit-arms`,
  for the repositories it uses.
- Three checks of what this shell can reach, whose replies were not read
  beyond the fields named: `search/issues` with `is:pr` returns a `body`
  field for a public repository outside this project (its length only was
  printed); per-repository REST endpoints (`repos/{owner}/{repo}/...`) and
  GraphQL refuse public repositories outside this project; and
  `git clone --bare --filter=blob:none --shallow-since=2026-11-01` works
  (tried on this repository).
- The `total_count` that GitHub's repository search returned at about
  11:30 UTC for the query below, per language and for the star bands
  200..999, 1000..4999 and 5000..20000, for example Python 5,026, 2,244
  and 697, Swift 359, 189 and 63. No repository name or text was read.
- Hugging Face's dataset search for agent transcripts (see "Formats left
  out").

## Software

- readcost at `origin/main` commit `fa4a42c` (0.3.0 with inanimate-subject
  opt-in). The script that draws the sample stops if `git diff fa4a42c --
  src uv.lock` is not empty, and records the SHA-256 of
  `src/readcost/features.py`.
- spaCy 3.8 with `en_core_web_sm` 3.8.0, as `uv.lock` pins it.
- Default configuration (`Config()`, no repository config read), with the
  five opt-in rules on at level `info`: inanimate-subject,
  participial-clause, nominalization, center-embedding and
  undefined-acronym. `comments = "doc"`, the default. long-sentence stays
  off, as in the first test. `verify_model` is off.

The default rules are stacked-nouns, long-dependency,
reduced-object-relative, hyphen-compound and inline-list.

## Population

### Repositories

GitHub's repository search, run once on 19 November 2026 (UTC), for each
of twelve languages (Python, Rust, Go, JavaScript, TypeScript, Java,
Kotlin, C#, Swift, C, C++, Ruby):

```text
language:"LANG" stars:200..20000 pushed:>=2026-11-01 created:<2026-01-01 fork:false archived:false
```

sorted by stars, descending, 100 per page, every page. A query whose
`total_count` is over 1,000 (the search's limit) has its star range split
at the integer midpoint, and each half is searched the same way, again
split if it is over 1,000. Every repository returned goes into
`eval/breadth/candidates.tsv`, committed, with its language, star count
and creation date.

The bounds: 200 stars and an age of at least ten and a half months make a
repository that people use and that is unlikely to be a template; 20,000
stars keeps out the largest projects, whose clones are slow and whose
docs some development corpora drew on; a push since 1 November means that
commits and pull requests from after that date exist.

A repository is dropped, and the reason recorded, when:

1. its owner is `arclabs561`, or its `owner/repo` appears in any file
   under `scripts/`, `eval/` or `docs/` at `fa4a42c` (the evaluation
   corpora, the rulebench, the first test's candidates), or in
   `eval/edit-arms/candidates.jsonl` on branch `exp/edit-arms`;
2. it is a fork or archived (by the search record);
3. its owner already has two repositories in the walk below.

Some development corpora (the broad README sample of
`scripts/fetch_github_readmes.py`) drew repositories by search and keep
their lists outside this repository, so rule 1 cannot see them. An overlap
is possible; it is not checked.

### The walk

For each language, sort its kept candidates by `owner/repo` and shuffle
them with `random.Random("20261119b:walk:LANG")`. Take the first 60 in
that order: 720 repositories. For each, at the head of its default branch
at the time of the fetch, make one clone:

```text
git clone --bare --filter=blob:none --shallow-since=2026-11-01 --single-branch --branch BRANCH URL
```

and, if that fails because no commit is that recent, the same with
`--depth 1` in place of `--shallow-since`. A repository whose clone fails
is dropped as a fetch error. Symbolic links are not followed. A repository
is then dropped when it has no README (as the first test's amendment finds
it), its README is over 1 MB, readcost reports that the README is not
English, or readcost counts fewer than 100 words in it. Every stratum
takes text only from the repositories kept.

## Strata

One stratum per format. For each repository, the files of each stratum
are chosen with `random.Random(f"20261119b:{stratum}:{repo}")` from the
sorted list of eligible paths. Paths under `node_modules/`, `vendor/`,
`third_party/`, `dist/` or `build/` are never eligible.

| Stratum | Text | Files per repository |
| --- | --- | --- |
| md | the README if it is Markdown, and Markdown files (`.md`, `.markdown`, `.mdx`) chosen as in the first test (under `docs/`, `doc/`, `design/`, `rfcs/`, `adr/`) | README and up to 2 |
| rst | the README if it is `.rst`, and `.rst` files under `docs/`, `doc/` or `documentation/` | README and up to 2 |
| html | `.html` and `.htm` files under `docs/`, `doc/`, `documentation/`, `site/` or `website/`, except those whose first 4 KB name a generator (`<meta name="generator"`, "Generated by") | up to 2 |
| src-py | docstrings in `.py`, `.pyi` | up to 3 |
| src-rs | `///` and `//!` comments in `.rs` | up to 3 |
| src-go | comments in `.go` | up to 3 |
| src-js | comments in `.js`, `.mjs`, `.cjs`, `.jsx`, `.ts`, `.tsx` | up to 3 |
| src-jvm | comments in `.java`, `.kt`, `.scala`, `.swift`, `.cs` | up to 3 |
| src-c | comments in `.c`, `.h`, `.cc`, `.cpp`, `.hpp` | up to 3 |
| src-rb | `#` comments in `.rb`, `.sh`, `.bash` | up to 3 |
| commit | commit messages on the default branch, author date on or after 1 November 2026 00:00 UTC | up to 30 |
| pr | pull request descriptions (the body, read as Markdown), created on or after 1 November 2026 | up to 20 |

The file names README, CHANGELOG, HISTORY, NEWS, LICENSE, AUTHORS,
CONTRIBUTING, CODE_OF_CONDUCT and SECURITY (any case, any extension) are
not eligible in md, rst or html except as the README itself. A source file
is not eligible when a path component is `test`, `tests`, `__tests__`,
`spec`, `testdata`, `fixtures`, `generated` or `gen`, or its name ends in
`.min.js`, `_pb2.py`, `.pb.go` or contains `.generated.` or `_generated.`.

Commits come from `git log --no-merges` of the clone. A commit is not
eligible when its author name or email contains `[bot]`, `dependabot`,
`renovate` or `github-actions`. Up to 30 are chosen with the seed above
from those sorted by SHA. Each message is checked as a commit message
(readcost's `commit` format).

Pull requests come from GitHub's issue search, one query per kept
repository:

```text
repo:OWNER/REPO is:pr created:>=2026-11-01
```

sorted by creation, newest first, one page of 100. A pull request is not
eligible when its body is empty or its author's type is `Bot` or login
ends in `[bot]`. Up to 20 are chosen with the seed above from those sorted
by number. Pointers record the number and the SHA-256 of the body.

Docs and doc comments are taken as they stand at the fetched head commit.
A push since 1 November may have gone to another branch, so that commit
can be older, and the text in it may be older still. Commits and pull requests were written after
1 November, so after almost every rule change on `main`.

A text is dropped, and the reason recorded, when it is over 1 MB (source
files: over 200 KB), when readcost reports that it is not English, when
readcost counts fewer words in it than the stratum's floor (100 for md,
rst, html and pr; 40 for source files; none for commits), when more than
half of the non-blank lines of a Markdown file are in fenced code blocks,
or when it is byte-identical to a text already kept in the stratum (by
SHA-256, the first in sorted `repo`, `path` order kept).

## Findings, near misses and decoys

### Findings

As in the first test: run readcost on every kept text; key each finding by
the first 16 hex digits of the SHA-256 of `repo|commit|path|rule|start|end`
(for a pull request, `path` is `pr/NUMBER`; for a commit message,
`commit/SHA`); within each stratum drop a finding whose rule and sentence
equal an earlier one's in key order; then for each stratum and rule
shuffle with `random.Random(f"20261119b:{stratum}:{rule}")` and take in
that order, at most two per repository, up to the quota. A finding that
readcost cannot map to source offsets is not sampled.

### Near misses

Five rules have a numeric threshold. One step past it:

| Rule | Default | One step looser |
| --- | --- | --- |
| stacked-nouns | 3 nouns (`STACKED_NOUNS_MIN`) | 2 |
| inline-list | 4 items (`INLINE_LIST_MIN_ITEMS`) | 3 |
| long-dependency | a gap of 9 words at z ≥ 2.5, or 15 at any z | 7 at z ≥ 2.0, or 13 at any z |
| center-embedding | depth 2 (`CENTER_EMBEDDING_DEPTH`) | depth 1 |
| undefined-acronym | known when Zipf frequency ≥ 3.8 (`KNOWN_ZIPF`) | ≥ 4.3 |

For long-dependency a step is two words of gap and 0.5 of z, since one
word would give too few cases to sample. The thresholds are module
constants, not configuration keys, so the looser runs set them in
`readcost.features` for the duration of one run.

For each of the five rules, readcost is run again on every kept text with
that rule's thresholds alone loosened (the other rules at default, so that
one rule's change cannot move another's findings). A near miss is a
finding of the loosened run, of that rule, whose sentence holds no
default finding of the same rule. Its message is the one readcost writes
in the looser run, so it has the rule's real format ("2 nouns stacked:
'build cache'", "3 items listed in one sentence"). Near misses are keyed,
de-duplicated against each other and against the stratum's findings of
the same rule (by sentence), and drawn as findings are, with the seed
`f"20261119b:{stratum}:near-{rule}"`.

The other five rules have no numeric threshold and get no near misses.

### Random decoys

A small floor of the first test's D-random decoys, built by its code
(`decoy_span`, `decoy_message`): eligible sentences with no finding of any
rule in either the default or the looser runs, a random span of two to
four content words, a rule name from the ten in rotation (shuffled with
`f"20261119b:{stratum}:decoy-rules"`), drawn with
`f"20261119b:{stratum}:decoy-random"`, at most one per repository.

### Quotas

Per stratum, the most items of each kind:

| Stratum | Each default rule | Each opt-in rule | Near misses, each default rule with a threshold | Near misses, each opt-in rule with a threshold | Random decoys |
| --- | --- | --- | --- | --- | --- |
| md, rst, commit, pr | 16 | 8 | 8 | 4 | 4 |
| html | 8 | 4 | 4 | 2 | 2 |
| each src stratum (7) | 4 | 2 | 2 | 1 | 1 |

At most 975 items: 750 findings, 200 near misses, 25 random decoys. A
rule with fewer eligible findings than its quota contributes all that pass
the cap, and the report gives its n. Rare rules will fall short in short
texts (center-embedding was about one finding per 100,000 words in the
first test); that is expected and stated, not repaired.

For the outcomes and decisions, the seven src strata are pooled into one
family, **doc comments** (at most 28 findings per default rule). The six
families are md, rst, html, doc comments, commit and pr.

Third-party text stays under `ref/breadth/`, outside the repository. The
repository holds pointers only, in `eval/breadth/sample.jsonl`:
repository, commit, path (or `pr/NUMBER` with the body's SHA-256, or
`commit/SHA`), blob SHA, stratum, kind of item, rule and offsets.

## Raters

The panel of #99's amendment: twelve primed raters, each a fresh,
independent Claude agent (raters 1 to 3 Claude Opus 5.5, 4 to 6 Claude
Sonnet 5.5, 7 to 9 Claude Haiku 5.5, 10 to 12 Claude Fable 5.2), and three
unprimed raters (blind 1 to 3: Opus, Sonnet, Haiku). These are four models
of one family, not independent families.

- Primed raters get the first test's rubric (`RUBRIC.txt`) and see, per
  item: `i`, `kind`, `rule`, `message`, `excerpt`, `sentence`, `before`
  and `after`. They label `c`, `d` or `w` and say whether the construction
  is present.
- Unprimed raters get the unprimed rubric (`RUBRIC_BLIND.txt` of #99) and
  see `i`, `kind`, `excerpt`, `sentence`, `before` and `after`, without
  rule or message. They label `c`, `d` or `w`.
- `kind` names the text type ("Markdown documentation", "Rust doc
  comment", "commit message", "pull request description" and so on). The
  two rubrics are changed only to name the text type: one line saying what
  `kind` means, and the list of fields.
- Nothing tells an item's kind of sample (finding, near miss, decoy) apart
  but its content. Raters are not told that near misses or decoys exist.
- Ids are six-digit numbers drawn with `random.Random("20261119b:ids")`
  over the items in key order. Each rater gets every item, in batches of
  about 40, in an order shuffled with its own seed: rater k with 5000 + k,
  blind k with 6000 + k. An item a rater leaves unlabelled counts as not
  "c", not accepted and not present for that rater.

## Outcomes

Majorities: an item is "c" when at least 7 of the 12 primed raters label
it `c` (six against six is not "c"); "accepted" when at least 7 label it
`c` or `d`; "present" when at least 7 say the construction is present;
"unprimed c" when at least 2 of the 3 unprimed raters label it `c`.

**Primary**, for each rule and family: the share of findings that are
"c", with a Wilson 95% interval, beside the share of the rule's near
misses that are "c" in the same family (rules with a threshold), with the
difference (findings minus near misses) and its Newcombe hybrid score 95%
interval.

**Secondary**, for each rule and family, the same for findings and near
misses: the accepted share, the present share and the unprimed c share.
Also the random decoys' c, accepted, present and unprimed c shares per
family and pooled. For the doc-comment family, every outcome also per src
stratum (small n; decides nothing). Per model (majority of its three) the
c and accepted shares of each rule, pooled over families.

**Pooled over families**, for each threshold rule: the findings' and near
misses' c and accepted shares and their difference, with intervals.

Agreement: Fleiss' kappa over the twelve primed raters, per family, for
the three-way label, for "c" against not, and for accepted against not;
and over the three unprimed raters for "c" against not.

## Decision rules

Fixed now. Each is a proposal for a later pull request; this test changes
no rule, level or default. A per-format proposal would be a per-format
level (for example a built-in override that turns a rule off for commit
messages or doc comments).

1. **The threshold earns its place**, for each threshold rule, pooled
   over families (at least 20 findings and 20 near misses): the
   difference of c shares (findings minus near misses) has a 95% interval
   wholly above zero. If it lies wholly below zero, the near misses are
   judged worse than the findings and the report proposes testing a lower
   threshold. Otherwise the threshold is "not supported by these labels".
   If the c shares of findings and near misses both have upper bounds
   under 0.10, there is too little "c" to compare: the same test is made
   on accepted shares and the report says so.
2. **Off in one format**: a rule R in a family F other than md (at least
   10 findings of R in F) is proposed off for F when its accepted share in
   F has an upper 95% bound under 0.25 and the difference of accepted
   shares (F minus md) has an interval wholly below zero. If only the
   first holds, the report says R is low in F but not distinguishable
   from Markdown, and it counts toward rule 3, not this rule.
3. **Opt-in everywhere**: a default rule whose accepted share pooled over
   all families (at least 40 findings) has an upper 95% bound under 0.25
   (the first test's decision 1).
4. **Detection problem in a format**: a rule whose present share in a
   family has an upper 95% bound under 0.5 (at least 10 findings).
5. **Candidate default in a format**: an opt-in rule whose accepted share
   in a family has a lower 95% bound over 0.5 and whose c share there has
   a lower bound over 0.10.
6. **No better than chance placement without priming**: a rule whose
   unprimed c share, pooled over families, does not exceed the pooled
   random decoys' unprimed c share by a difference whose 95% interval lies
   wholly above zero. The report states this beside any other proposal.
7. **Guards**: a family whose Fleiss' kappa for accepted against not,
   over all its findings and the twelve primed raters, is under 0.20 makes
   no proposal under rules 2, 4 and 5. A rule or family below its minimum
   n gets its numbers and no decision.

## Formats left out

- **Agent session transcripts** (`--format transcript`). Licensed public
  sets of agent trajectories exist on Hugging Face (for example
  `nebius/SWE-agent-trajectories`, CC BY 4.0), but they are loops of
  agent tools from 2024 and 2025, written before the rules, and Hugging
  Face is blocked in the shell that builds the rater batches. Left out; a
  later round could fetch one in CI.
- **Plain text** files (`.txt`) and configuration comments (`.toml`,
  `.yaml`): readcost reads them, but they are not a documentation format
  that users point it at; left out to keep the strata few.

## What the report contains

- Counts at each step: candidates per language, each drop reason,
  repositories walked and kept, texts kept per stratum, findings and near
  misses per rule before and after de-duplication, and items drawn.
- Every outcome above, whatever the result, and each decision with the
  rules it names.
- Anything else under "Exploratory, not pre-registered", such as rates
  per 1,000 words per format, the causes raters gave, and a comparison of
  md with the first test's READMEs.

The scripts are `scripts/breadth_precision.py` (draw and batches, reusing
`scripts/heldout_precision.py`) and `scripts/breadth_report.py` (report),
added in the commits after this one.

## Amendments
