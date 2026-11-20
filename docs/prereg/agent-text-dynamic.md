# Pre-registration: fix texts that use the finding's own words, judged against today's text

Written 20 November 2026 (UTC), before any model was called for this test.
The commit that adds this file is the registration; its timestamp on GitHub
is the record. Nothing in this file changes after that commit. Any change
made later goes in a dated "Amendments" section at the end, with the reason.

## Why

The factorial ([agent-text-factorial.md](agent-text-factorial.md)) found that
the rule's own fix is the largest part of readcost's agent feedback. Against a
generic fix, it cut edits that change content by 14.9 points and raised
readability by 0.163. The search that followed
([agent-text-search.md](agent-text-search.md)) tried rewordings of each
static fix. They differed by less than its measurement could resolve: utility
intervals of about ±0.1 per candidate, gains of 0.02 to 0.06. Its held-out
test decided nothing, because both new judges answered by position.

This test changes three things. It tries fixes that differ in kind rather
than in wording: some quote the finding's own words and name the operation,
others say when to leave the sentence alone. It judges each candidate's edit
directly against today's edit of the same paragraph, scored by the judges'
probabilities rather than by votes. It spends judgements in stages, so units
go to candidates still in contention. Two research briefs, summarized in
this pull request, back each change. It also writes down how to screen a
judge before trusting it, which the held-out test lacked.

## What was seen before writing this

- Everything in docs/evaluation.md on `main` at `3fb3909`, including the
  full reports of the factorial, the search and its held-out test.
- The excerpts and messages that readcost gives for findings of each default
  rule in the 200 paragraphs of the earlier tests. They were read to see which
  words a fix could quote. No edit or judgement was read.
- The two research briefs: on comparing systems with noisy model judges, and
  on evolutionary prompt search.

## Software

readcost at `main`, whose `src/` and `uv.lock` are those of `e1871db` (0.4.0);
the job checks the factorial's digest. The vLLM image, model revisions and
settings are the factorial's. The scripts are `scripts/eval_agent_text_dynamic.py`
and `scripts/agent_text_dynamic_job.py`, in the commit after this one. They
reuse the factorial's task message, fact check and helpers.

Editors: `openai/gpt-oss-120b` and `mistralai/Mistral-Small-4-119B-2603`.
Judges: `Qwen/Qwen3.8-27B` and `google/gemma-4-31B-it`.

## Paragraphs

The 200 paragraphs of the earlier tests (`eval/edit-arms/paragraphs.jsonl`
and `eval/edit-localize/paragraphs.jsonl`). Their ids are sorted and shuffled
with `random.Random("20261120:agent-text-dynamic")`. The first 50 form the
**audit set**: no choice below uses them. The rest form the **training set**.
A paragraph with no finding is left out.

For each species below, its training paragraphs keep the shuffled order. The
first third (rounded up) are its **screen** paragraphs and the rest its
**confirmation** paragraphs. A unit is one paragraph and one editor.

## The seed and the species

**The seed** is today's text, R0: `readcost check -o agent`, the factorial's
arm HsFPX. The stage 2 held-out test kept it
(`eval/agent-text-heldout/decision.json`).

**Species "note".** One candidate: R0 without the precision note (the
factorial's HsFpX level of P). The factorial found the note slightly lowered
utility (−0.024 [−0.045, −0.004]), below its smallest difference. This
species tests that on its own.

**One species per default rule.** Each has two candidates. A candidate
replaces that rule's fix in every finding of that rule and leaves every other
part of R0 as it is. readcost's reminder to keep a "because" clause, for
long-dependency and inline-list, is added to every candidate as it is today.

The quoted words `{q}` come from the finding. For stacked-nouns and
reduced-object-relative they are the words quoted in the message. For
hyphen-compound and inline-list they are the excerpt. For long-dependency,
`{a}` and `{b}` are the two words the message names. A quote of more than
eight words is not used, and the candidate falls back to its form without a
quote, shown in brackets.

| Rule | c1: name the words and the operation | c2: say when to leave it |
| --- | --- | --- |
| stacked-nouns | Unpack '{q}': say how its nouns relate, with a preposition or a verb. [Unpack the run of nouns: say how they relate, with a preposition or a verb.] | Leave '{q}' if readers know it as one term; otherwise say how its nouns relate. [Leave the nouns together if readers know them as one term; otherwise say how they relate.] |
| long-dependency | Bring '{a}' and '{b}' together: move what comes between them to the end of the sentence, or into a sentence of its own. | Leave it if '{a}' and '{b}' are easy to connect; otherwise split the sentence so that each part says one thing. |
| reduced-object-relative | Add 'that' to the clause in '{q}'. [Add 'that' to start the clause.] | Leave '{q}' if the clause is short; otherwise add 'that' or make the clause a sentence of its own. [Leave the clause if it is short; otherwise add 'that' or make it a sentence of its own.] |
| hyphen-compound | Write '{q}' out as a phrase that says how its parts relate. [Write the hyphenated words out as a phrase that says how they relate.] | Keep '{q}' if it is an established term; otherwise write it out. [Keep the hyphenated words if they are an established term; otherwise write them out.] |
| inline-list | Put the {n} items in a bulleted list, after a sentence that introduces them. | Leave the list in the sentence if the items are short; otherwise use a bulleted list. |

`{n}` is the number of items in inline-list's message. A rule's candidates
are judged only on paragraphs where readcost's feedback shows that rule. The
note species is judged on every paragraph.

## Judgements

**Facts (every edit).** Each judge runs the factorial's fact check once,
comparing the edit with the original. An edit **changes content** when at
least one judge lists a lost or changed fact.

**Readability (cascade).** For a unit, compare the candidate's edit with the
seed's edit of the same paragraph and editor. If exactly one of the two
changes content, the unit's score is decided by facts. If both do, it is 0.
If neither does, each judge compares the two edits in both orders. The
prompt is the edit test's pairwise prompt, ending instead with `Answer "1",
"2" or "tie".` and with the reply schema `{"easier": "1" | "2" | "tie"}`.
The request asks vLLM for the log probabilities of the answer token. The
three options are renormalized, and P(candidate) is taken as P(its version)
+ 0.5·P(tie), averaged over the two orders and the two judges. Where vLLM
returns no log probabilities for a unit's answers, that unit's readability
comes from the votes instead (win 1, tie or split 0.5, loss 0, averaged over
judges), and the report gives how many units this applies to.

**Pointwise readability (secondary).** For each edit that enters a
readability comparison, each judge scores how easy it is to read, 1 to 7, on
its own.

## Outcomes

For each unit, the **paired score** Δ of candidate against seed:

- +1 if the seed's edit changes content and the candidate's does not, −1 if
  the reverse;
- 0 if both change content;
- 2·P(candidate) − 1 if neither does.

Δ lies between −1 and +1; 0 means no difference. A candidate's gain is the
mean Δ over its units, with a 95% percentile bootstrap interval over
paragraphs (both editors' units resampled together), 10,000 resamples,
seed 0.

Secondary:

- Δ with win, tie and loss in place of probabilities (1, 0.5 and 0, as in
  the factorial);
- the pointwise difference (candidate minus seed, over 6) on units where
  neither changes content;
- the share of edits that change content, per arm;
- whether readcost still flags the rule's finding after the edit (rerun on
  the edit), per arm;
- length, the median of words over the original's;
- the per-unit standard deviation of Δ, from the screen, and the smallest
  gain the confirmation could detect;
- all of the above per editor and per judge.

## Successive halving and the choice

For each species, separately:

1. **Screen.** Every candidate is judged on the screen units. A candidate
   whose gain has an upper bound under 0 is dropped. If two remain, the
   paired difference c1 − c2 over the screen units is computed. If its
   interval excludes 0, only the better one goes on; otherwise both do.
2. **Confirmation.** The candidates that go on are judged on the
   confirmation units and on the audit set.
3. **Choice.** The winner is the candidate with the higher confirmation gain,
   provided its lower bound is over 0. Otherwise the seed stays for that
   species.

**Reported gains.** The confirmation gain is shrunk toward 0 as
g·max(0, 1 − se²/g²), where se is the bootstrap standard error. The
screen chose among candidates, which inflates a raw gain. The audit-set gain
is reported unshrunk; nothing was chosen on it.

No readcost text changes because of this test. A winner goes to a held-out
confirmation in a later plan, with fresh paragraphs and screened judges.

## Smallest gain the budget can detect

No smallest difference is set as a decision threshold; the choice rule needs
only a lower bound over 0. A per-unit standard deviation of about 0.55 for Δ
is assumed, with 80% power at α = 0.05. Under that assumption, the
confirmation sets detect a gain of about:

| Species | Confirmation units (about) | Detectable gain |
| --- | --- | --- |
| note | 194 | 0.11 |
| inline-list | 134 | 0.13 |
| stacked-nouns | 98 | 0.16 |
| reduced-object-relative | 60 | 0.20 |
| hyphen-compound | 34 | 0.26 |
| long-dependency | 30 | 0.28 |

A gain of 0.1 is, for example, 10 points fewer edits that change content at
equal readability. hyphen-compound and long-dependency are too rare in these
paragraphs to show anything but a large effect, and the report says so. The
screen measures the standard deviation, and the report gives the detectable
gains it implies.

## Judge screening

Before a judge is trusted, it runs a **calibration** on 40 paragraphs of the
factorial's main set, the first 40 in the shuffled order above that are not
in the audit set:

1. **Parsing.** At least 90% of its calibration replies parse.
2. **Position.** On the R0 edit against the C edit, in both orders, at most
   70% of its outcomes are splits (the same position chosen in both orders).
3. **Position on identical texts.** Shown the original against itself, in
   both orders, its non-tie answers pick Version 1 between 25% and 75% of the
   time.
4. **Facts.** Of the C edits it checks, the share it calls content-changing is
   at least 5 points above the share of R0 edits it calls so. Earlier tests
   put the gap at about 14 points.
5. **Null check.** It lists a lost or changed fact for the original compared
   with itself in at most 10% of paragraphs.

In this test, Qwen and Gemma run the calibration first, and the report gives
their results. They decide nothing here: the search uses these two judges in
any case, and the earlier tests already relied on them. In any later
held-out confirmation, a judge that fails any of the five is excluded before
it judges, and the next judge on that plan's list takes its place. By the
earlier figures, the held-out judges of stage 2 would have failed check 2.

## Calls and caps

| Calls | About |
| --- | --- |
| Edits, new (R0's edits of the factorial's 100 paragraphs and the note candidate's edits of every paragraph are cached) | 1,600 |
| Fact checks, new | 3,200 |
| Calibration, both judges | 560 |
| Pairwise, screen, confirmation and audit | 2,950 |
| Pointwise | 2,300 |

One Hugging Face Job on one H200, timeout **1.5 hours ($7.50)**. The job starts
from the search's replies (`agent-text-search/main-1/replies.jsonl`). It stops
before loading a model if fewer than 95% of the edits expected in the cache
are found: R0's on the factorial's main set and the note candidate's on
every paragraph with a finding.
It also stops before a call that would take the cache past **80,000**
replies. Its own clock stops new calls 15 minutes before the timeout.

**Order.** One model is loaded at a time:

1. each editor: every edit;
2. each judge: the calibration, then every fact check;
3. each judge: the screen's comparisons and pointwise scores;
4. each judge: the confirmation's and the audit set's comparisons and
   pointwise scores, for the candidates still in.

That is eight model loads, about 32 minutes. The estimate is 55 to 70 minutes
in all. Calls within a phase are shuffled with
`random.Random("20261120:agent-text-dynamic:calls:<phase>")`. If the job
stops before step 4 is complete for both judges, the report gives what was
done, and no choice is made. If it stops with an error before any judge is
called, one more job may run after the fix, within 2 GPU hours for both.

**Outputs.** Every reply (with its log probabilities), `run.json`, the model
logs and the report go to the private dataset `arclabs561/readcost-labels`
under `agent-text-dynamic/<run id>/`. The upload stops if the dataset is not
private. The paragraphs are not uploaded.

The editors and judges are models; no person reads an edit.

## Amendments
