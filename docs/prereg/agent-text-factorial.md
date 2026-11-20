# Pre-registration: which parts of readcost's agent feedback matter?

Written 20 November 2026 (UTC), before any model was called for this test.
The commit that adds this file is the registration; its timestamp on GitHub
is the record. Nothing in this file changes after that commit. Any change
made later goes in a dated "Amendments" section at the end, with the reason.

## Why

Two pre-registered tests in docs/evaluation.md looked at how an editor model
uses `readcost check -o agent`. In "Editing with readcost's feedback", edits
made with the feedback changed a paragraph's facts less often than edits made
with a generic instruction. "Pointing at sentences" then found that feedback
in the same form, pointing at the longest sentences, did as well. Naming a
few sentences seems to keep the editor off the rest. Wording the same
findings as questions made facts change more often. So readcost's text may
matter as much as what readcost finds.

This test varies five parts of that text at once, in a fractional factorial
design, and measures what each part does. The task the editor gets stays
fixed. Every part varied is text that readcost itself prints; the words
around it do not change. The result chooses where a later search over the
wording starts (stage 2, which gets a plan of its own). It does not by itself
change readcost.

## What was seen before writing this

- Everything in docs/evaluation.md on `main` at `9029330`, including the full
  reports of the edit test (`eval/edit-arms/report.md`) and of the
  localization control (`eval/edit-localize/report.md`).
- The text of `readcost check -o agent` at `main` and the default rules'
  titles and fixes in `src/readcost/features.py`.
- No edit, judgement or finding of the variants below.

## Software

- readcost at `main` as of this plan: `src/` and `uv.lock` are those of the
  0.4.0 release commit `e1871db`, with `eval_edit_arms.tree_digest()` equal
  to `f84d01e995f1d407b08f54c46942661c504a5b5d775825fd5df300f73d3bd6e7`.
  The job stops if they differ. Default configuration (`Config()`): the rules
  stacked-nouns, long-dependency, reduced-object-relative, hyphen-compound and
  inline-list.
- The scripts are `scripts/eval_agent_text.py` and `scripts/agent_text_job.py`,
  added in the commit after this one. They reuse the edit test's prompts,
  client, judge prompts and counting from `scripts/eval_edit_arms.py`, and
  the sentence list from `scripts/eval_edit_localize.py`.
- Models, revisions, vLLM image and settings as in the edit test. Two editors,
  `openai/gpt-oss-120b` and `mistralai/Mistral-Small-4-119B-2603`. Two judges,
  `Qwen/Qwen3.8-27B` and `google/gemma-4-31B-it`. Olmo 3.1 32B is left out as
  an editor: it went over the word budget most often. GLM-4.7 Flash is left
  out as a judge: in the localization control it listed a lost or changed
  fact in over 99% of edits in every arm.

## Paragraphs

The 200 paragraphs of the localization control (`eval/edit-arms/paragraphs.jsonl`
and `eval/edit-localize/paragraphs.jsonl`), checked with readcost as above.
Their ids are sorted and shuffled with `random.Random("20261120:agent-text")`.
In that order:

- the first 100 with at least one finding form the **main set**;
- the next 40 with at least one finding and at least two checked sentences
  that hold no finding form the **decoy set**.

A checked sentence is one that readcost counts, as defined in the
localization control's plan (`eval_edit_localize.sentences`).

## The task, fixed

The edit test's system message and arm B's user message, unchanged, with the
variant's text as `{feedback}`:

```text
Revise this paragraph to make it easier to read. Keep every fact.
The revision must be at most {budget} words.

A prose checker reported this about the paragraph:
{feedback}

Paragraph:
{text}
```

The anchor for readability is the edit test's arm C: the same message without
the checker's block. Its edits for these paragraphs and editors are already in
the localization control's reply cache and are not asked again.

## The five factors

Each takes one of two levels. The "+" levels together give the text that
`readcost check -o agent` prints at `main` (without the feedback link), and a
test checks that they do.

| Factor | + | − |
| --- | --- | --- |
| H, head | the first line orders: `readcost: {n} hard-to-read construction{s} in {words} words. Rewrite these sentences where the finding holds; keep the meaning and the facts.` | it informs: `readcost: {n} hard-to-read construction{s} in {words} words.` |
| S, scope | ` Leave the other sentences as they are.` is added to the first line | not added |
| F, fix | the rule's fix (`Finding.suggestion`) | `Rewrite the sentence so it is easier to read.` |
| P, precision | `(raters accepted {a} of {m} such findings)` after the detail, where readcost gives one | no note |
| X, detail | the finding's message (`Finding.message`, with its excerpt) | the rule's title (`FEATURES[rule].title`) |

Each finding's line is `- line {line} [{rule}] {detail}{note}. Fix: {fix}`,
in readcost's worst-first order, at most eight, then readcost's "...and N
more" line, cut at 2,500 characters as readcost cuts it.

**The design.** The 16 arms are the half fraction with X = −H·S·F·P, coding
"+" as 1 and "−" as −1. Its resolution is V: no main effect or two-factor
interaction is confounded with another main effect or two-factor interaction.
Today's text (all "+") is one of the 16 arms, called R0.

## Decoys

These measure deference: whether an editor rewrites a sentence because it is
flagged, whatever the flag says. A decoy is one extra finding line for a
checked sentence that holds no finding. It goes only into the 8 arms with
X at "−". In those arms every line shows the rule's title, so a decoy line
looks like the real ones.

For each paragraph of the decoy set, `random.Random(f"20261120:agent-text:decoy:{id}")`
picks, in this order:

1. the decoy sentence and a control sentence, two different checked
   sentences that hold no finding;
2. the decoy's rule, from the five default rules;
3. where its line goes among the finding lines.

The decoy's line follows the arm's levels of F and P for its rule. The head's
count includes it.

**Deference index.** For each edit of a decoy-set paragraph: the decoy
sentence counts as rewritten when its text, after collapsing whitespace, no
longer appears in the edit. The control sentence counts the same way. The
index is the share of edits that rewrote the decoy minus the share that
rewrote the control, with a paragraph bootstrap interval. Decoy-set edits are
not judged.

## Judgements

For each edit of the main set:

- **Facts.** Each judge runs the edit test's fact check once, comparing the
  edit with the original. The edit **changes content** when at least one of
  the two judges lists a lost or changed fact. With GLM left out, this is
  what the localization control's rule (two of three judges) came to.
- **Readability.** Each judge compares the edit with the C edit of the same
  paragraph and editor, in both orders, with the edit test's pairwise prompt.
  The edit test's scoring applies: 1 for a win in both orders, 0 for a loss
  in both, 0.5 otherwise. A unit's score is the mean over the judges that
  judged it in both orders.

A missing reply is asked for once more at the end of its phase. A unit is one
paragraph and one editor: 200 units, each seen in all 16 arms.

## Outcomes

For each unit and arm: **change** (0 or 1), **read** (0 to 1, against C) and
**utility** = read − change.

**Primary.** The main effect of each factor on change and on read. For each
unit, it is the mean over the 8 arms at "+" minus the mean over the 8 arms
at "−". Then it is averaged over units, with a 95% percentile bootstrap
interval over paragraphs (both editors' units resampled together), 10,000
resamples, seed 0. A unit counts for a factor when at least 6 of its 8 arms
at each level have the outcome.

Secondary, deciding nothing unless stated below:

- each factor's main effect on utility (decides the seed for stage 2);
- the ten two-factor interactions on change, read and utility, each as a
  contrast with the same bootstrap;
- each arm's mean change, read and utility, and R0's;
- the deference index over all 8 decoy arms, with an interval, and the main
  effects of H, S, F and P on it (those 8 arms are a half fraction of the four
  factors, resolution IV);
- the same per editor and per judge;
- length (median words over the original's, per arm) and readcost's findings
  after each edit (mean per arm).

## Smallest difference that counts

3 points of change, 0.03 of read, 0.03 of utility. A main effect of that size
is a third of the gap between B and C in the localization control (13.7
points). For a main effect, each side averages 8 arms over 200 units. The 95%
interval of a main effect is expected to have a half-width of 1.5 to 3 points.

## Decision rules

- A factor **matters** for an outcome when its main effect's interval
  excludes 0 and the estimate is at least the smallest difference in size.
- **Seed for stage 2.** Each factor takes the level with the higher utility
  main effect when that effect's interval excludes 0, and otherwise keeps
  R0's level.
- **Whole-text search.** Stage 2 searches the text as a whole, not part by
  part, when any two-factor interaction on utility is larger in size than the
  largest main effect on utility, and its interval excludes 0.
- **Stage 2 runs** when at least one factor matters for change or for read.
  Otherwise the report says that within these five parts the wording made no
  difference of the smallest size, and stage 2 does not run.
- No readcost text changes because of this test alone. A change ships only
  after stage 2's held-out test, or a later pre-registered test, supports it.

The judges are models; no person reads the edits. The 200 paragraphs were
used in the earlier tests, so this test is not held-out data. That is why it
chooses a seed and ships nothing.

## Calls and caps

| Calls | Count |
| --- | --- |
| Edits, main set: 16 arms × 100 paragraphs × 2 editors | 3,200 |
| Edits, decoy set: 8 arms × 40 paragraphs × 2 editors | 640 |
| Fact checks: 3,200 edits × 2 judges | 6,400 |
| Readability against C: 3,200 edits × 2 judges × 2 orders | 12,800 |
| In all | 23,040 |

The job starts from the localization control's 18,201 cached replies
(`edit-localize/main-1/replies.jsonl`) and stops before a call that would take
the cache past **44,000**. It is one Hugging Face Job on one H200 with a
timeout of **2 hours ($10)**. The job's own clock stops new calls 15 minutes
before the timeout. If it stops with an error before any judge has been
called, one more job may run after the fix, within 2.5 hours for both. The
estimate is 1 to 1.3 hours.

**Order.** One model is loaded at a time: each editor for all its edits; then
each judge for the fact checks, then the readability judgements. Calls within
a phase are shuffled with `random.Random("20261120:agent-text:calls:<phase>")`.
If a judge's phases do not finish, the report gives what was done, and no
rule above is applied.

**Outputs.** Every reply, `run.json`, the model logs and the report go to the
private dataset `arclabs561/readcost-labels` under `agent-text/<run id>/`.
The upload stops if the dataset is not private. The paragraphs are not
uploaded.

## What the report contains

- The counts of the main and decoy sets.
- Calls made, calls served from the cache, and GPU time.
- Every outcome above, whatever the result; each decision and its outcome.
- Anything else under the heading "Exploratory, not pre-registered".

readcost's rules, defaults and output do not change in this pull request.

## Amendments
