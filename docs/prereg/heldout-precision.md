# Pre-registration: how often are readcost's findings real, on text no rule was tuned on?

Written 19 November 2026 (UTC), before any finding from the sample below
was computed or read. The commit that adds this file is the registration;
its timestamp on GitHub is the record. Nothing in this file changes after
that commit. Any change made later goes in a dated "Amendments" section at
the end, with the reason.

## Why

The precision figures in [evaluation.md](../evaluation.md#precision-of-the-sample)
come from 210 findings on essays and documentation, drawn at `a4c609a` and
labelled by one rater (Claude), then by a second ("Second rater") and by
ten ("Ten raters"). The rules were then revised with those labels in view,
and the share that a majority accepts among the findings still reported
(23% in README "Limits") was measured on the same 210. That makes it an
in-sample estimate: the revisions were chosen to remove findings that the
raters had rejected, so the share is biased upward by an unknown amount.

This test measures the same quantity on text that no rule change could have
been fitted to, with the sample, the raters and the decisions fixed in
advance. No person labels anything; every label comes from a model.

## What was seen before writing this

- The 210-finding sample's results as reported in evaluation.md, the label
  files in `eval/labels/` and the rubric in `scripts/second_rater.py`.
- For the population below: the `total_count` that GitHub's repository
  search returned for the query with star floors of 5, 10, 20 and 50
  (16,215, 9,409, 6,167 and 3,638 on 19 November 2026, 03:05 UTC). No
  repository name, README or finding from it was read.

## Rules and settings

- readcost at `origin/main` commit `a57e19e` (version 0.3.0). The script
  that draws the sample stops if `git diff a57e19e -- src uv.lock` is not
  empty, and records the SHA-256 of `src/readcost/features.py`.
- spaCy 3.8 with `en_core_web_sm` 3.8.0, as `uv.lock` pins it.
- Default configuration (`readcost.toml.example`), with no repository
  config read, plus four opt-in rules turned on at level `info`:
  participial-clause, nominalization, center-embedding and
  undefined-acronym. long-sentence is left off: the rubric does not define
  it, and raters agree that a sentence over 32 words is long
  (evaluation.md, "Opt-in rules on every corpus": 38 of 40), so labelling
  it again would measure nothing.
- `verify_model` is off. The biaffine second parser cannot be downloaded in
  the shell that runs the draw (it reaches only GitHub and package
  registries). A later amendment can add a CI job
  that runs with `verify_model = "biaffine"` on the same files and the
  same sampled findings; it would report which sampled findings that setting keeps,
  without new labels.

The default rules are stacked-nouns, long-dependency, inanimate-subject,
reduced-object-relative, hyphen-compound and inline-list.

## Population

Strata, in order of priority:

- **S1, primary: READMEs.** The README that GitHub's `repos/{repo}/readme`
  endpoint returns, at the default branch's head commit at the time of the
  draw.
- **S2, secondary: documentation files from the same repositories.** From
  the repositories whose README passed every filter, the Markdown files
  (`.md`, `.markdown`, `.mdx`) at the same commit whose path, compared
  without case, starts with `docs/`, `doc/`, `design/`, `rfcs/` or `adr/`,
  or contains `/adr/` or `/design/`, and whose file name does not start
  with README, CHANGELOG, LICENSE, CONTRIBUTING, CODE_OF_CONDUCT or
  SECURITY. Up to two such files per repository, chosen with
  `random.Random(f"20261119:{repo}")` from the sorted list of paths.

The repositories come from GitHub's repository search, run once on
19 November 2026 (UTC), one query per creation day from 2 to 17 November
2026:

```text
created:DAY stars:>=50 fork:false archived:false
```

sorted by stars, descending, 100 per page, every page. A day whose
`total_count` is over 1,000 (the search's limit) is split into
`stars:50..99`, `stars:100..499` and `stars:>=500`. Every repository
returned, with its star count and creation time at the draw, goes into
`eval/heldout/candidates.jsonl`, committed, so the population can be
rebuilt without searching again.

The star floor is 50 because the draw needs enough text for the rare
opt-in rules (center-embedding fired about once in 100,000 words on the
combined corpus), and 3,638 repositories at 50 stars give an estimated
1.5 to 3 million words of README prose. A lower floor adds repositories
that few people have read; a higher one leaves too few.

A repository or file is dropped, and the reason recorded, when:

1. its owner is `arclabs561`, or its `owner/repo` appears in any file
   under `scripts/`, `eval/` or `docs/` at `a57e19e` (the evaluation
   corpora and the rulebench). Every development corpus was fetched
   before 2 November 2026 or drew repositories created before 2026, so this
   should drop nothing; it is checked anyway;
2. it is a fork or archived (the search excludes both; the repository
   record is checked again);
3. the README endpoint returns no file, or the file is over 1 MB;
4. readcost reports that the text is not English (its `language_check`
   note);
5. readcost counts fewer than 300 words in it (words it analyses, after
   code blocks, tables, HTML and headings are removed);
6. more than half of its non-blank lines are inside fenced code blocks;
7. it is byte-identical to a file already kept (same blob SHA), in which
   case the first one in sorted `owner/repo` order is kept.

The rule changes on `main` went on until 18 November 2026, after some of
these repositories were created. That does not matter for this test: what
makes the sample held out is that no one working on readcost had read
these texts, because none of them is in a development corpus.

## The sample

1. Run readcost over every kept file of both strata. Record, for each file,
   the repository, the commit SHA, the path and the blob SHA.
2. Number every finding by its key: the first 16 hex digits of the SHA-256
   of `repo|commit|path|rule|start|end`. Sort by key.
3. Within each stratum, drop a finding whose rule and sentence text equal
   those of a finding earlier in key order (template READMEs repeat
   sentences).
4. For each stratum and rule, shuffle that rule's findings with
   `random.Random(f"20261119:{stratum}:{rule}")` and take them in that
   order, skipping a finding when its repository already has two in the
   sample for that rule and stratum, until the quota is met or the
   findings run out:

   | | Each default rule | Each opt-in rule |
   | --- | --- | --- |
   | S1, READMEs | 40 | 20 |
   | S2, docs | 20 | 10 |

   The planned total is 480 findings (320 in S1, 160 in S2). A rule with
   fewer findings than its quota contributes all that pass the cap, and the
   report gives its n.

## Decoys

Model raters may call a fair share of any sentence "defensible", so an
accepted share means little alone. The sample therefore also holds decoys:
sentences with no finding, given a made-up finding. They come from the same
kept files and are drawn after the findings, with the same seed scheme.

A sentence is eligible as a decoy when readcost checks it (at least four
alphabetic words and a verb or auxiliary, as `Analyzer.sentences` decides)
and no finding of any enabled rule falls in it. Within each stratum, a
sentence whose text equals an earlier eligible sentence's, in key order, is
dropped. Two kinds, with their own pools:

- **D-random**: any eligible sentence.
- **D-long**: in each file, the eligible sentence with the most words (the
  first one on a tie).

For each stratum and kind, shuffle the pool with
`random.Random(f"20261119:{stratum}:decoy-{kind}")` and take sentences in
that order, at most one per repository for each kind, up to the quota:

| | D-random | D-long |
| --- | --- | --- |
| S1, READMEs | 40 | 40 |
| S2, docs | 20 | 20 |

That is 120 decoys among 600 items, 20%.

Each decoy gets a rule name and a span. The rule names of a stratum's
decoys are the ten rules repeated in order until there is one name per
decoy, shuffled with `random.Random(f"20261119:{stratum}:decoy-rules")`, so
every rule name is used about equally often. The span, chosen with
`random.Random(f"20261119:span:{key}")`: a length L drawn from 2, 3 and 4,
then a run of L consecutive alphabetic tokens whose first and last tokens
are content words (noun, proper noun, verb, adjective or adverb), drawn
uniformly from the runs of that length in the sentence. If there is no such
run, L is lowered by one; a sentence with no run of two is skipped, and the
next one in shuffled order is taken. The message is the rule's own message
template, filled from the span (for example `'A' and 'B' are N words
apart`, with A and B the first and last words of the span and N their
distance in words), so that a decoy has the same fields and format as a
real finding.

Decoys are not real findings and are left out of every outcome below
except the decoy baseline.

The text stays under `ref/heldout/`, outside the repository (it belongs to
the repositories' authors). The repository holds pointers only, in
`eval/heldout/sample.jsonl`: repository, commit, path, blob SHA, rule,
stratum, key, whether the item is a decoy and of which kind, and character
offsets of the finding (or decoy span) and its sentence.

## Raters

Three independent instances of Claude. Each labels every one of the 600
items (480 findings and 120 decoys, mixed, with nothing to tell them apart
but their content) and sees, for each:

- the rule name, readcost's message, the flagged words (excerpt), the
  sentence, and up to 240 characters of the source on each side of the
  sentence;
- nothing else: not the repository, not the other raters' labels, not the
  in-sample labels, and not this file.

Raters are not told that some items are decoys.

The prompt is `RUBRIC` from `scripts/second_rater.py` at `a57e19e`,
verbatim, followed by two definitions it lacks, taken verbatim from the
`PROMPT` in `scripts/eval_optin_rules.py`:

```text
- nominalization: an action turned into a noun with a light verb ("performs validation of" for "validates").
- participial-clause: a present participle clause tacked onto a sentence ("..., highlighting what changed").
```

and the reply format. Each rater labels each finding `c` (correct), `d`
(defensible) or `w` (wrong) and says whether the construction is present.
Items go to raters in batches of about 40, in an order shuffled with a
different fixed seed per rater (1, 2 and 3). A rater that leaves an item
unlabelled gets it once more in a final batch; an item still missing a
label is reported as such and counts as not accepted, and not present, for
that rater.

All three raters come from one model family, the same family as rater 1
of the in-sample set. That makes the comparison between this sample and
rater 1's in-sample labels like for like in the rater. It also means the
three can share a bias, and a majority of three does not remove it. Their
agreement measures consistency, not correctness. The ten-rater majority of
the in-sample set cannot be reproduced here: the other families were
reached through OpenRouter, and no key is available.

The comparison is not like for like in two other ways, stated now so that a
difference is not read as the effect of the rule changes alone. Rater 1
labelled the in-sample findings by hand, reading the source where needed,
not through this prompt; and the in-sample findings came from essays and
documentation by well-regarded writers, not from new READMEs, so a
difference mixes the rule changes, the kind of text and the rater setup.

## Outcomes

The primary outcome, for each rule in S1:

- **Accepted share over decoys**: the rule's accepted share (below) minus
  the accepted share of all S1 decoys together, with a Newcombe hybrid
  score 95% interval for the difference of two independent proportions. A
  rule whose interval does not lie wholly above zero is reported as not
  distinguishable from chance placement: raters accepted its findings no
  more often than a made-up finding on a sentence without one.

The decoy baseline itself: the accepted and present shares of the S1
decoys, of the S2 decoys, of each kind (D-random, D-long) and of the decoys
given each rule name, each with a Wilson 95% interval. The per-name decoy
counts are small (about 8 in S1) and decide nothing.

For each stratum and rule:

- **Accepted share**: the share of findings that at least two of the three
  raters label `c` or `d`, with a Wilson 95% interval.
- **Present share**: the share that at least two of the three say has the
  construction, with a Wilson 95% interval.
- Each rater's counts of `c`, `d` and `w`.
- Fleiss' kappa over the three raters, for the three-way label, for
  accepted against wrong, and for present; and the mean pairwise
  agreement on accepted against wrong.

Across rules:

- The same kappas over all findings of each stratum.
- The S1 accepted share for the default rules as a whole, weighting each
  rule's accepted share by that rule's share of all default-rule findings
  in S1 (after step 3 of the sample), with a 95% percentile interval from
  2,000 bootstrap resamples within rules (seed 0). This is the held-out
  counterpart of the 23% in README "Limits", which came from a different
  majority and a different kind of text.

Comparison with the in-sample labels, S1 only, for the six default rules:
each held-out rater's own `c` or `d` share against rater 1's on the 210
findings, as evaluation.md's precision table reports it:

| Rule | Rater 1, in-sample, c or d | Present |
| --- | --- | --- |
| stacked-nouns | 7 of 31 | 20 of 31 (65%) |
| long-dependency | 9 of 32 | 9 of 32 (28%) |
| inanimate-subject | 7 of 32 | 10 of 32 (31%) |
| reduced-object-relative | 1 of 32 | 18 of 32 (56%) |
| hyphen-compound | 4 of 19 | 4 of 19 (21%) |
| inline-list | 4 of 32 | 13 of 32 (41%) |

The present counts are the table's percentages times n, rounded. The
difference of two proportions gets a Newcombe hybrid score 95% interval.
The report calls a rule's held-out share higher or lower than in-sample
only when all three raters' intervals exclude zero in the same direction.
Nothing is decided by this comparison.

## Decision rules

Fixed now, applied to S1. Each is a proposal for a later pull request; this
test changes no rule, level or default.

1. **Proposed for opt-in**: a default rule whose accepted share has an
   upper 95% bound under 0.25. With n = 40 that means 4 or fewer accepted.
   The floor: 0.25 is about the share that the in-sample majority gave the
   default rules after the revisions (23%). A rule that is clearly below
   it on held-out text, where the label includes "defensible", is worse
   than the figure readcost now quotes for its rules. A rule whose readers
   dismiss more than three findings in four is teaching them to ignore the
   tool.
2. **Detection problem, not a cost problem**: any rule whose present share
   has an upper 95% bound under 0.5 (with n = 40, 13 or fewer present).
   When fewer than half of a rule's findings hold the construction it
   names, the error is in finding the construction, and the claim about
   reading cost has not been tested. For stacked-nouns,
   reduced-object-relative and long-dependency the proposal is to run the
   `verify_model` leg on this sample first; for the others, to look at the
   detector.
3. **Candidate for more testing as a default**: an opt-in rule whose
   accepted share has a lower 95% bound over 0.5. Precision alone does not
   show a reading cost, so this names a candidate and proposes nothing
   else.
4. **Not distinguishable from chance placement**: any rule whose accepted
   share over decoys has a 95% interval that does not lie wholly above
   zero. The report states this label for each rule that gets it, beside
   any proposal from rules 1 to 3, and says that the rule's acceptance by
   these raters does not show that it finds anything that a random span
   would not.
5. A rule with fewer than 20 sampled findings in S1 gets no decision; the
   report gives its numbers as they are.
6. If, over all S1 findings, Fleiss' kappa for accepted against wrong is
   under 0.20 and the mean pairwise agreement is under 0.80, the raters do
   not agree enough to act on, and the report makes no proposal.

S2 is reported with the same outcomes, its accepted share over decoys
taken against the S2 decoys, and decides nothing. Where S2 points
the other way from an S1 decision (for example, an S1 upper bound under
0.25 and an S2 lower bound over 0.25), the report says that the proposal
may hold for READMEs only.

## What the report contains

- Counts at each step: candidates, each drop reason, files kept, findings
  per rule before and after the de-duplication, sampled findings per
  rule, and decoy pools and draws.
- Every outcome above, for every rule and stratum, whatever the result.
- Each decision, and which rules it names.
- Anything else under the heading "Exploratory, not pre-registered", such
  as rates per 1,000 words, the causes raters gave, or results by star
  count.

The scripts are `scripts/heldout_precision.py` (draw and batches) and
`scripts/heldout_report.py` (report), added in the commits after this one.

## Amendments

### 19 November 2026, before the search was run

Details that `scripts/heldout_precision.py` fixes and the text above
leaves open, written before any search, fetch or check was run:

- The head commit of each repository's default branch comes from
  GitHub's GraphQL API; the README comes from `repos/{repo}/readme` at
  that commit.
- A finding that readcost cannot map to source offsets is not sampled.
- D-random is drawn before D-long, and a sentence drawn as D-random is
  not drawn again as D-long. A decoy whose span cannot be mapped to
  source offsets is skipped, like a sentence with no run.
- An inline-list decoy's message says "4 items listed in one sentence",
  the rule's smallest count, whatever the span's length.
- The 240 characters of context on each side are cut back to whole
  words, with runs of white space collapsed to one space.
- A rater sees each item as the fields `i`, `rule`, `message`,
  `excerpt`, `sentence`, `before` and `after`. The ids are six-digit
  numbers drawn with `random.Random("20261119:ids")` over the items in
  key order, so they carry no information about rule or decoy status.

### 19 November 2026, after a failed first fetch

GitHub's GraphQL API is not reachable from this shell, so the first fetch
got nothing: every repository failed at the head-commit step, before any
README was read. That attempt was discarded. The head commit now comes
from the REST endpoint `repos/{repo}/commits/{branch}`, with the default
branch that the search returned, and the fork and archived flags come from
the search results only. A repository whose commit or README request fails
for another reason (an empty repository, for example) is dropped as a
fetch error.

### 19 November 2026, after a second failed fetch

The REST API also refuses per-repository requests from this shell; only
the search and git itself reach these repositories. The second fetch read
no README either, and was discarded. The fetch now makes a shallow clone
of each repository's default branch without file contents (`git clone
--depth 1 --filter=blob:none --no-checkout`), takes the head commit from
it, lists the tree, and reads only the files it needs. Three consequences:

- The README is no longer the one that `repos/{repo}/readme` returns but
  an approximation from the tree: the first of the root, `.github/` and
  `docs/` that holds a file named README or README.ext (any case), and
  there the first by extension in the order `.md`, `.markdown`, `.mdx`,
  `.rst`, `.txt`, none, then by name.
- Docs files are chosen for every repository at fetch time, by the same
  seeded rule; S2 still checks only those of repositories whose README
  was kept.
- Symbolic links are not followed.
