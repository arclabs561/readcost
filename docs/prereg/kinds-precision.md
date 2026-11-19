# Pre-registration: precision by kind of document, and in ordinary code comments

Written 19 November 2026 (UTC), before any text from the sample below was
fetched or read. The commit that adds this file is the registration; its
timestamp on GitHub is the record. Nothing in this file changes after that
commit. Any change made later goes in a dated "Amendments" section at the
end, with the reason.

## Why

The second held-out test ([breadth-precision.md](breadth-precision.md),
"Precision across formats" in
[evaluation.md](../evaluation.md#precision-across-formats-pre-registered))
found that model raters call almost no finding of a default rule a cost an
editor would fix (0 to 6% "c"), that readcost's message drives most of the
acceptance, that stacked-nouns' threshold earns its place and
long-dependency's does not, and that center-embedding is the one rule above
chance placement without priming. Three weaknesses limit it:

- It had 25 random decoys. Their unprimed "c" share has an upper bound of
  13%, wider than most rules' shares, so the test against chance placement
  could not tell rules apart.
- Its strata were file formats. A changelog, a tutorial and a design
  document are all Markdown, and a rule can suit one and not another.
- Its code strata held doc comments only. In C-family languages readcost
  reads every comment under the default `comments = "doc"` (see "Code
  strata"), so ordinary comments were in the sample unlabelled as such, and
  in Python and Rust they were not in it at all.

This round samples by kind of document, adds ordinary code comments as a
stratum of their own, and draws at least 15 random decoys per stratum. It
also tests a ranking of sentences for rereading (part A of "Ranked
sentences") and fixes, before any data, the rule that decides which rules
stay on by default across all three rounds ("Defaults across rounds").

No person labels anything; every label comes from a model.

## What was seen before writing this

- Both earlier plans, their amendments, their reports (`eval/heldout/`,
  `eval/breadth/report.md`) and their summaries in evaluation.md; the
  rubrics in `/home/claude/breadth-batches/`.
- The `total_count` that GitHub's search returned at about 14:00 UTC for
  the queries below, and nothing else from them: 1,357 for population (a),
  11,443 for population (b), 710 for `draft-ietf in:name fork:false
  archived:false` (90 of them pushed since 1 November), and 168,960 for the
  code search `filename:runbook extension:md`. No repository name, path or
  text was read.
- The search records (licence, stars, last push, fork and archived flags)
  of `github/site-policy` and of the named sources below, and whether
  `owner/repo` is in the exclusion set of drop rule 1. Their file lists and
  text were not read.
- `reports/readcost-formats.md` (outside the repository), section "Kinds of
  document", which names public sources per kind. Of those, `django/django`,
  `golang/proposal`, `golang/website`, `rust-lang/rfcs`,
  `kubernetes/enhancements`, `python/peps`, `python/cpython`,
  `rust-lang/rust`, `mdn/content` and `dotnet/csharplang` are in the
  exclusion set (named in a development corpus) and are not used;
  `gitlab-com/runbooks` is on gitlab.com, which this shell cannot reach
  (`git ls-remote` gets 403).

## Software

- readcost at `origin/main` commit `663e0cc` (0.3.0, inanimate-subject
  opt-in, inline-list off in source files by `CONTEXT_DEFAULTS`). The script
  that draws the sample stops if `git diff 663e0cc -- src uv.lock` is not
  empty, and records the SHA-256 of `src/readcost/features.py`.
- spaCy 3.8 with `en_core_web_sm` 3.8.0, as `uv.lock` pins it.
- Default configuration (`Config()`, no repository config read), with the
  five opt-in rules on at level `info`: inanimate-subject,
  participial-clause, nominalization, center-embedding and
  undefined-acronym. long-sentence stays off. `verify_model` is off.
  `comments` is `"doc"` except in the ordinary-comment stratum, where it is
  `"all"`.

The default rules are stacked-nouns, long-dependency,
reduced-object-relative, hyphen-compound and inline-list. Since #101,
inline-list is off in source files, so the two code strata have no
inline-list findings and no inline-list near misses; that is the shipped
behaviour and it is not changed for this test.

## Population

### Repositories

GitHub's repository search, run once on 19 November 2026 (UTC):

```text
(a) stars:20001..1000000 pushed:>=2026-11-01 created:<2026-01-01 fork:false archived:false
(b) stars:200..20000 pushed:>=2026-11-01 created:<2026-01-01 fork:false archived:false
    -language:Python -language:Rust -language:Go -language:JavaScript -language:TypeScript
    -language:Java -language:Kotlin -language:C# -language:Swift -language:C -language:C++
    -language:Ruby
```

(b) is one query, written on three lines here. Both are sorted by stars,
descending, 100 per page, every page; a query whose `total_count` is over
1,000 has its star range split at the integer midpoint, again and again, as
in round 2. Round 2 searched the twelve languages that (b) leaves out at
200 to 20,000 stars and excluded more than 20,000, so (a) and (b) are
disjoint from its population by construction. Every repository returned
goes into `eval/kinds/candidates.tsv`, committed, with its population,
language, stars and creation date.

A repository is dropped, and the reason recorded, when:

1. its owner is `arclabs561`, or its `owner/repo` appears in any file
   under `scripts/`, `eval/` or `docs/` at `663e0cc` (this covers round 1's
   `eval/heldout/candidates.jsonl`, round 2's `eval/breadth/candidates.tsv`,
   the rulebench and the corpora of `docs/datasets.md`), or in
   `eval/edit-arms/candidates.jsonl` on branch `exp/edit-arms`;
2. it is a fork or archived (by the search record);
3. its owner already has two repositories in the walk.

### The walk

Sort each population's kept candidates by `owner/repo`, shuffle with
`random.Random("20261119c:walk:a")` (and `:b`), and take the first 400 of
(a) and then the first 600 of (b), the owner cap counting across both:
1,000 repositories. Each gets one clone of its default branch at the head
at the time of the fetch:

```text
git clone --bare --filter=blob:none --depth 1 --single-branch --branch BRANCH URL
```

A repository whose clone fails or takes over 10 minutes is dropped as a
fetch error. Symbolic links are not followed. Text is taken as it stands at
that commit, which is recorded; no date filter applies to it.

### Named sources

Some kinds have well-known public sources. These are added beside the walk,
each at its head commit, cloned as above, and left out of the walk (drop
reason "named source"). The licence is the one in the repository's search
record; a source without a licence there is not used.

| Source | Licence | Files and kind |
| --- | --- | --- |
| `github/docs` | CC-BY-4.0 | Markdown under `content/`, kind by the kind rule below |
| `kubernetes/website` | CC-BY-4.0 | Markdown under `content/en/`, kind by the kind rule below (its `blog/` gives blog posts, `docs/tutorials`, `docs/tasks`, `docs/concepts` and `docs/reference` the Diátaxis kinds) |
| `rust-lang/blog.rust-lang.org` | Apache-2.0 | every Markdown file: blog |
| `swiftlang/swift-evolution` | Apache-2.0 | Markdown under `proposals/`: design |
| `Kotlin/KEEP` | Apache-2.0 | Markdown under `proposals/`: design |
| `openshift/runbooks` | Apache-2.0 | every Markdown file: runbook |
| `prometheus-operator/runbooks` | Apache-2.0 | Markdown under `content/`: runbook |

The documentation exclusions below (README and the like, `.github/`) apply
to them too. A named source gives up to 30 files per stratum, chosen with
the stratum's seed. So that one large source cannot fill a stratum, a
named source gives at most 4 items of each rule and kind of item per
stratum, at most 2 of them from one directory (the file's parent), and at
most 4 random decoys per stratum, one per file.

### Runbooks found by code search

Runbooks and postmortems are rare in open source repositories, so their
stratum also takes files found by GitHub's code search, run once, each
query sorted by best match, 100 per page, up to 10 pages:

```text
filename:runbook extension:md      path:runbooks extension:md
filename:postmortem extension:md   path:postmortems extension:md
filename:post-mortem extension:md  filename:incident extension:md
```

A result is kept when its repository is a kept candidate of (a) or (b)
(after drop rules 1 and 2; the owner cap does not apply) and the kind rule
below assigns its path to the runbook stratum. Each such repository not
already in the walk is cloned as above, and only its runbook stratum is
read. The code search's ranking and index are not documented; this part
of the stratum is a convenience sample of the candidate repositories, and
the report gives its count apart.

### Standards text

No mirror of published RFCs was checked. In its place: Internet-Drafts
from repositories found by the repository search `draft-ietf in:name
fork:false archived:false created:<2026-01-01`, sorted by stars, every
page. A `draft-ietf-` name marks a draft adopted by an IETF working group.
Drop rule 1 applies, and an owner cap of five. Shuffle with
`random.Random("20261119c:walk:standards")` and take the first 80; clone as
above. Eligible files: Markdown files (`.md`) whose name starts with
`draft-`, outside the skipped directories; one per repository, chosen with
the seed of its stratum. These drafts are written in kramdown-rfc
Markdown, for publication as RFCs.

### Non-technical contrast

One source: `github/site-policy` (CC0-1.0), GitHub's terms, privacy
statements and other site policies, at its head commit, cloned as above.
Eligible files: Markdown files outside `.github/` whose name is not README,
CONTRIBUTING, LICENSE or CODE_OF_CONDUCT; up to 40, chosen with the seed of
its stratum. It is legal and policy prose written by a software company,
not prose from another field; it shows whether rates differ in text that is
not technical, and decides nothing.

## Strata

### Kind of document

A documentation file is a file with extension `.md`, `.markdown`, `.mdx` or
`.rst`, not under `node_modules/`, `vendor/`, `third_party/`, `dist/`,
`build/` or `.github/`, whose name does not start with README, LICENSE,
CONTRIBUTING, CODE_OF_CONDUCT, SECURITY or AUTHORS (any case). Its kind is
assigned from its path alone, lowercased, before readcost runs on it:

1. Each directory component, outermost first, is compared with the
   directory names below; the first that matches gives the kind.
2. If none matches, the file name without its extension (the stem) is
   compared with the stem patterns, in the order of the table.
3. If neither matches, the file is in no stratum.

| Stratum | Directory names (whole component) | Stem starts with |
| --- | --- | --- |
| changelog | `changelog`, `changelogs`, `changelog.d`, `changes`, `release-notes`, `release_notes`, `releasenotes`, `releases`, `whatsnew`, `whats-new`, `news` | `changelog`, `changes`, `history`, `news`, `release-notes`, `release_notes`, `releasenotes`, `releases`, `whatsnew`, `whats-new` |
| runbook | `runbook`, `runbooks`, `postmortem`, `postmortems`, `post-mortems`, `incidents`, `incident`, `oncall`, `on-call` | `runbook`, `postmortem`, `post-mortem`, `post_mortem`, `incident`, `oncall`, `on-call` |
| design | `rfc`, `rfcs`, `adr`, `adrs`, `decisions`, `decision-records`, `design`, `designs`, `design-docs`, `design_docs`, `proposal`, `proposals`, `keps`, `enhancements`, `architecture-decisions`, `architecture-decision-records` | `adr-`, `adr_`, `rfc-`, `rfc_`, `kep-`, `design-doc`, `design_doc`, or `adr`, `rfc` or `kep` followed by a digit |
| blog | `blog`, `blogs`, `posts`, `_posts` | none |
| tutorial | `tutorial`, `tutorials`, `how-to`, `howto`, `how-tos`, `how_to`, `tasks`, `getting-started`, `getting_started`, `get-started`, `quickstart`, `quick-start`, `walkthrough`, `walkthroughs`, `cookbook`, `recipes`, `guide`, `guides`, `user-guide`, `learn` | `tutorial`, `how-to`, `howto`, `how_to`, `getting-started`, `getting_started`, `gettingstarted`, `get-started`, `quickstart`, `quick-start`, `quick_start`, `walkthrough`, `cookbook`, `install`, `guide`, and any stem ending in `-guide` or `_guide` |
| reference | `reference`, `references`, `api`, `apis`, `api-reference`, `api-docs`, `man`, `man1` to `man9`, `manpages`, `man-pages`, `cli`, `commands`, `configuration`, `options`, `settings` | `reference`, `api`, `cli-reference`, `commands`, `configuration`, `options`, `settings`, `glossary`, and a stem ending in `.1` to `.9` (a man page) |
| explanation | `concepts`, `concept`, `explanation`, `explanations`, `background`, `architecture`, `internals`, `overview`, `theory`, `how-it-works`, `under-the-hood` | `concept`, `explanation`, `background`, `architecture`, `internals`, `overview`, `how-it-works`, `under-the-hood`, `theory` |

The kind rule applies to the walked repositories, to `github/docs` and
`kubernetes/website` (on the path below `content/` and `content/en/`), and
to the files of the code search. The other named sources, the standards
stratum and the contrast stratum take the kind their own rules above
give.

For each repository and stratum, the eligible paths are sorted, shuffled
with `random.Random(f"20261119c:{stratum}:{repo}")` and taken in that
order: up to 2 files per documentation stratum. A file is read only when it
is taken.

### Code strata

Source files are files with an extension readcost reads as source, except
`.toml`, `.yaml` and `.yml`: `.py`, `.pyi`, `.rs`, `.go`, `.js`, `.mjs`,
`.cjs`, `.jsx`, `.ts`, `.tsx`, `.java`, `.kt`, `.scala`, `.swift`, `.cs`,
`.c`, `.h`, `.cc`, `.cpp`, `.hpp`, `.rb`, `.sh`, `.bash`. Round 2's
exclusions apply: no path component `test`, `tests`, `__tests__`, `spec`,
`testdata`, `fixtures`, `generated` or `gen`, none of the skipped
directories, and no name ending in `.min.js`, `_pb2.py`, `.pb.go` or
containing `.generated.` or `_generated.`. Each code stratum takes up to 3
files per walked repository, chosen as above with its own seed.

`src/readcost/extract.py` decides which comments are prose. With the
default `comments = "doc"` it reads docstrings in Python, `///` and `//!` in
Rust, and in every C-family language and in Ruby and shell scripts every
comment (`//`, `/* */`, `#`); `"all"` adds `#` comments in Python and `//`
in Rust. So the setting separates doc comments from others only in Python
and Rust. This test classifies each sentence by the comment it starts in,
from the source text alone:

- **doc**: a Python docstring; Rust `///`, `//!`, `/**` or `/*!`; in a
  C-family language, a `/** */` block (not `/**/`) or a `///` line; in Go,
  also a run of `//` lines directly followed (no blank line) by a line
  whose text starts with `func`, `type`, `var`, `const`, `package` or an
  upper-case identifier (Go's convention for doc comments); in Ruby, a run
  of `#` lines directly followed by a line starting with `def`, `class`,
  `module`, `attr_reader`, `attr_writer` or `attr_accessor`.
- **ordinary**: every other comment: Python and shell `#`, `//` and
  `/* */` elsewhere, Ruby `#` elsewhere.

Stratum **code-doc** runs readcost with `comments = "doc"` and keeps the
findings, near misses and sentences classified doc. Stratum
**code-ordinary** runs it with `comments = "all"` and keeps those
classified ordinary. The kind shown to raters names the language: "doc
comment in Go source", "Python docstring", "ordinary comment in Rust source
(not a doc comment)".

### What a text must pass

A text is dropped, and the reason recorded, when it is over 1 MB (source
files: 200 KB), when readcost reports that it is not English, when readcost
counts fewer than 100 words in it (40 for source files, counted over the
whole run before the classification above), when more than half of the
non-blank lines of a Markdown file are in fenced code blocks, or when it is
byte-identical to a text already kept in the stratum (SHA-256, first in
sorted `repo`, `path` order kept). A changelog is cut to its first
100,000 bytes, at the end of a line, before any check: most changelogs put
the newest entries first, and the longest would otherwise dominate.

## Items

Findings, near misses and random decoys are made as in round 2
(`scripts/breadth_precision.py`): the same keys, the same looser thresholds
(stacked-nouns 2, inline-list 3, long-dependency 7 at z ≥ 2.0 or 13 at any
z, center-embedding depth 1, undefined-acronym Zipf 4.3), the same decoy
spans and messages (`decoy_span`, `decoy_message` of round 1), and the same
de-duplication by rule and sentence within a stratum, in key order. All
seeds start with `20261119c` in place of `20261119b`.

### No item twice

Round 2 drew one finding twice: readcost reported it twice at the same
offsets, so the two copies had one key. This round, before any quota is
filled:

- every item is keyed as in round 2, and the draw rejects an item whose key
  is already in the sample;
- every sentence is compared in a normalized form (lower case, every run of
  characters that are not letters or digits made one space, stripped).
  Within a stratum, findings, near misses and decoys are de-duplicated by
  rule and normalized sentence; across the whole sample, strata in the
  order of the quota table, an item whose rule and normalized sentence equal
  an item already drawn is rejected and the next in shuffled order is
  taken. A decoy is rejected when its normalized sentence equals any item's
  already drawn.

### Quotas

Per stratum, at most two items per repository for each rule and kind of
item, and at most one random decoy per repository; named sources have the
caps of "Named sources", and the contrast stratum (one repository) has them
per file:

| | Each default rule | Each opt-in rule | Near misses, stacked-nouns, long-dependency, inline-list | Near misses, center-embedding, undefined-acronym | Random decoys |
| --- | --- | --- | --- | --- | --- |
| each stratum | 12 | 4 | 4 each | 2 each | 16 |

The strata, in the order the draw takes them: tutorial, reference,
explanation, design, runbook, changelog, blog, standards, code-doc,
code-ordinary, contrast. At most 112 items per documentation stratum and
96 per code stratum (no inline-list): at most 1,200 items for the primed
raters. A rule with fewer eligible items than its quota contributes all
that pass the caps, and the report gives its n. Rare kinds (runbook, blog,
standards) and rare rules will fall short; that is expected and stated,
not repaired.

The random decoys bound chance placement per stratum and pooled. With 16
decoys and none labelled, the Wilson 95% upper bound is 19%; with 2 of 16,
the interval is 4 to 36%, 33 points wide. Pooled over ten strata (160
decoys, the contrast stratum left out), a share near 5% has an interval
about 7 points wide (3 to 10%), near 10% about 9 points, against round 2's
25 decoys (upper bound 13% at zero).

### Ranked sentences (part A)

For each stratum, the documents (texts) that gave at least one item above
are sorted by key of their first item, shuffled with
`random.Random(f"20261119c:{stratum}:ranked-docs")`, and taken in that
order, one per repository (contrast: any), up to 20 documents with at least
5 eligible sentences. An eligible sentence is one readcost checks (at
least four alphabetic words and a verb or auxiliary, as
`Analyzer.sentences` decides), in the stratum's comment class for code
strata. From each document, three items:

1. **longest**: the sentence with the most alphabetic words;
2. **composite**: the sentence with the highest score
   `z(words) + z(arc) + z(depth) + F`, where z is the z-score within the
   document's eligible sentences (population standard deviation; z is 0
   when it is 0), words is the count of alphabetic tokens, arc is the
   longest dependency arc (over tokens whose head is another token of the
   sentence, the number of alphabetic tokens from the dependent to its
   head, counting the head), depth is `readcost.metrics.embedding_depth` of
   the sentence as readcost's own parse gives it, and F is the number of
   default-rule findings (default run) whose span starts in the sentence.
   The composite is fixed here and is not tuned;
3. **random**: one eligible sentence, chosen with
   `random.Random(f"20261119c:ranked:{key}")`, where key is the document's
   key.

Ties go to the sentence that comes first. If two of the three are the same
sentence, it is one item, counted in each. The excerpt is the whole
sentence. Ranked items go to the unprimed raters only, mixed with their
other items; the primed raters never see them. At most 660 ranked items.

## Raters

The panel of rounds 1 and 2: twelve primed raters, each a fresh,
independent Claude agent (raters 1 to 3 Claude Opus 5.5, 4 to 6 Claude
Sonnet 5.5, 7 to 9 Claude Haiku 5.5, 10 to 12 Claude Fable 5.2), and three
unprimed raters (blind 1 to 3: Opus, Sonnet, Haiku). Four models of one
family.

- Primed raters get round 2's `RUBRIC.txt` and see `i`, `kind`, `rule`,
  `message`, `excerpt`, `sentence`, `before` and `after`. They label `c`,
  `d` or `w` and say whether the construction is present.
- Unprimed raters get round 2's `RUBRIC_BLIND.txt` and see `i`, `kind`,
  `excerpt`, `sentence`, `before` and `after`, without rule or message.
- `kind` now names the kind of document ("tutorial or how-to guide",
  "changelog or release notes", "doc comment in Go source"). The rubrics
  change only to say so: the line that says what `kind` means, and, in the
  unprimed rubric, the clause that lists where sentences come from.
- Nothing tells finding, near miss, decoy and ranked item apart but their
  content; raters are not told that near misses, decoys or ranked items
  exist. A ranked item's excerpt is a whole sentence, which a rater may
  notice.
- Ids are six-digit numbers drawn with `random.Random("20261119c:ids")`
  over all items in key order. Each rater gets every item meant for it, in
  batches of about 40, shuffled with its own seed: rater k with 7000 + k,
  blind k with 8000 + k. An unlabelled item counts as not "c", not accepted
  and not present for that rater.

## Outcomes

Majorities as in round 2: "c" when at least 7 of the 12 primed raters label
it `c`; "accepted" when at least 7 label it `c` or `d`; "present" when at
least 7 say the construction is present; "unprimed c" when at least 2 of
the 3 unprimed raters label it `c`; "unprimed c or d" when at least 2
label it `c` or `d`.

**Primary**, for each rule and stratum: the share of findings that are
"c", with a Wilson 95% interval, beside its near misses' "c" share in the
same stratum (threshold rules), with the difference and its Newcombe 95%
interval.

**Secondary**, for each rule and stratum, findings and near misses: the
accepted, present, unprimed c and unprimed c-or-d shares; and against the
stratum's random decoys, the differences of unprimed c and of unprimed c or
d (findings minus decoys), with Newcombe intervals. The random decoys' own
shares per stratum and pooled over the ten technical strata. Per model
(majority of its three), the c and accepted shares of each rule, pooled.
Fleiss' kappa over the twelve per stratum (three-way, c against not,
accepted against not) and over the three unprimed (c against not).

**Pooled over the ten technical strata**, for each threshold rule: the
findings' and near misses' c and accepted shares and their differences;
for each rule, unprimed c and unprimed c or d over the pooled decoys.

**Ranked sentences**: the unprimed c-or-d share of composite, longest and
random items, pooled over the ten technical strata, with Wilson intervals;
composite minus longest and composite minus random, with Newcombe
intervals. The three come from the same documents, so these intervals,
which treat them as independent, are wider than paired ones when the
outcomes correlate; a paired comparison is reported as exploratory.

## Decision rules

Fixed now. Each is a proposal for a later pull request; this test changes
no rule, level or default.

How a per-kind proposal would ship: `CONTEXT_DEFAULTS` in
`src/readcost/config.py` is keyed by context, and the engine picks the
context from the format (`prose`, `commit`, `source`). Every kind of
document here is `prose`, so a per-kind default would need a new built-in
layer keyed by path globs, built from the kind rule above, sitting where
`CONTEXT_DEFAULTS` sits (under every user setting). The two code strata are
both `source`; a default for ordinary comments only would need the
extractor to mark each segment doc or ordinary and a new context for the
latter.

1. **The threshold earns its place**, for each threshold rule, pooled over
   the ten technical strata (at least 20 findings and 20 near misses): the
   difference of c shares has a 95% interval wholly above zero. Wholly
   below zero: the report proposes testing a lower threshold. Otherwise:
   "not supported by these labels". When the point estimates of both c
   shares are under 0.10, the test uses accepted shares and says so (round
   2's amendment).
2. **Off for a kind**: a rule R in a technical stratum K (at least 10
   findings of R in K) is proposed off for K when its accepted share in K
   has an upper 95% bound under 0.25 and the difference of accepted shares
   (K minus the other documentation strata pooled; for a code stratum, K
   minus the other code stratum) has an interval wholly below zero. If only
   the first holds, the report says R is low in K but not distinguishable
   from the rest.
3. **No better than chance placement in a kind**: a rule whose unprimed
   c-or-d share in K (at least 10 findings) does not exceed K's random
   decoys' by a difference with a lower 95% bound above zero. Stated beside
   any proposal; with 16 decoys it is weak and decides nothing alone.
4. **Detection problem in a kind**: present share with an upper 95% bound
   under 0.5 (at least 10 findings).
5. **Candidate default in a kind**: an opt-in rule whose accepted share in
   K has a lower 95% bound over 0.5, whose c share there has a lower bound
   over 0.10, and whose unprimed c-or-d share exceeds K's random decoys'
   with a lower bound above zero.
6. **No better than chance placement, pooled**: for each rule, unprimed c
   and unprimed c or d, pooled over the ten technical strata, against the
   pooled random decoys; the rule is so labelled when neither difference
   has a lower 95% bound above zero.
7. **Guards**: a stratum whose Fleiss' kappa for accepted against not,
   over all its findings and the twelve primed raters, is under 0.20 makes
   no proposal under rules 2, 4 and 5. A rule or stratum below its minimum
   n gets its numbers and no decision. The contrast stratum makes no
   proposal.
8. **Ranking (part A)**: the composite is worth shipping as a ranking of
   sentences to reread only if composite minus longest has a lower 95%
   bound above zero. A looser result, stated as looser: a point estimate
   of composite minus longest above zero together with composite minus
   random with a lower bound above zero. Otherwise the composite does not
   beat sentence length.

### Defaults across rounds (part B)

Pooling rounds 1, 2 and 3, for each of the ten rules:

- round 1: S1 (READMEs) findings and S1 D-random decoys, from
  `eval/heldout/sample.jsonl` and `eval/heldout/labels/` (it has no near
  misses);
- round 2: every family, from `eval/breadth/sample.jsonl` (the second row
  of id 768685 dropped, as its amendment says) and `eval/breadth/labels/`;
- round 3: the ten technical strata.

The majorities are those above (7 of 12 primed, 2 of 3 unprimed). The
tests:

- (i) findings' accepted share minus near misses' accepted share, rounds 2
  and 3, with a Newcombe 95% interval (threshold rules only);
- (ii) findings' unprimed c-or-d share minus the random decoys' unprimed
  c-or-d share, all three rounds, with a Newcombe 95% interval.

A default rule stays on by default only if (i) or (ii) has a lower bound
above zero; otherwise it is proposed opt-in. An opt-in rule is proposed
default only if (ii) has a lower bound above zero and, where it has a
threshold, (i) does too. Pooling mixes kinds of text and rounds with
different populations; the per-round shares are reported beside the pooled
ones, and a rule whose decision differs between the pooled and any single
round's figures is reported as such.

## What the report contains

- Counts at each step: candidates per population, each drop reason,
  repositories walked, cloned and kept, files per stratum and drop reason,
  runbook files from the walk and from code search, findings and near
  misses per rule before and after de-duplication, items rejected as
  duplicates, items drawn, ranked documents.
- Every outcome above, whatever the result, and each decision with the
  rules it names, including part B's table.
- Anything else under "Exploratory, not pre-registered".

The scripts are `scripts/kinds_precision.py` (draw and batches, reusing
`scripts/breadth_precision.py` and `scripts/heldout_precision.py`) and
`scripts/kinds_report.py` (report), added in the commits after this one.
Third-party text stays under `ref/kinds/`; the repository holds pointers
only, in `eval/kinds/sample.jsonl`.

## Amendments

### 19 November 2026, after the searches and before any fetch

Written after the searches ran and before any repository was cloned or
any text read. Counts from the searches, and details that
`scripts/kinds_precision.py` fixes and the text above leaves open.

- The searches returned 1,357 repositories for (a) and 11,446 for (b)
  (12,803 candidates), 624 for the drafts query and the records of the
  eight named sources and `github/site-policy`. The six code searches
  each returned their limit of 1,000 results (4,803 distinct files); only
  12 files in 3 repositories that are kept candidates and not walked pass
  the kind rule, so the runbook stratum rests on the walk and the two
  named runbook sources.
- The drafts query is run as registered, without a star range: its count
  is under the search's limit, so no split is needed.
- The walk drops 19 repositories of (a) and 1 of (b) as named in a
  development corpus, 41 for the owner cap, and `github/docs` from (a) as
  a named source; the drafts walk drops 3 for its owner cap.
- Code search results in walked repositories are not used: the walk reads
  their runbook files by the kind rule already.
- The chosen blobs of a clone are fetched in one batch (`git fetch origin
  OID...` in the blobless clone) and read with `git cat-file`; the bytes
  are the same as one fetch per blob.
- A changelog is cut when it is stored, so pointers' offsets refer to the
  cut text; its record says whether it was cut.
- In a Python file, a sentence whose line starts with `#` outside a
  docstring is ordinary; every other sentence readcost reads there is in a
  docstring.
- Under `comments = "all"`, readcost reads a Rust `///` line a second time
  as a `//` comment. Such a sentence is classified doc by its own line, so
  it never enters code-ordinary; in the ranked sentences of a document a
  sentence at the same offsets counts once.
- Documents for ranked sentences are sorted by the smallest key of the
  items they gave, then shuffled.
- Ids are drawn over all items, ranked ones included. Primed batches hold
  findings, near misses and random decoys; unprimed batches hold those and
  the ranked items.
