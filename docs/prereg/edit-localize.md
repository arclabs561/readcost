# Pre-registration: do readcost's findings keep an edit's facts, or does pointing at sentences?

Written 20 November 2026 (UTC), before any paragraph below was drawn and
before any model was called for this test. The commit that adds this file is
the registration; its timestamp on GitHub is the record. Nothing in this file
changes after that commit. Any change made later goes in a dated
"Amendments" section at the end, with the reason.

## Why

The pre-registered edit test ([edit-arms.md](edit-arms.md), runs `main-1`
and `main-1b`) found one difference between readcost's feedback (arm B) and
a generic request to make a paragraph easier to read (arm C). The judges
found that B's edits changed the paragraph's facts less often: 47.5% of
edits against 58.1%, a difference of −10.6 points [−19.4, −2.2]. B's edits
read no better than C's (0.542, inconclusive).

That difference has a simpler cause than readcost's rules. B's feedback
points at a few sentences and says "Rewrite these sentences"; C points at
none. Any feedback that names a few sentences may keep an editor away from
the rest of the paragraph, whatever picks those sentences. Earlier tests
in docs/evaluation.md found that no rule's findings beat the longest
sentence when raters see no message. So this test adds arm E. E's
feedback has B's form and points at as many sentences as B's findings do,
but chooses the longest ones and gives a generic fix. If B keeps facts
better than E, the rules add something to pointing. If E keeps facts as
well as B, pointing at sentences explains the effect, and the rules are
not what keeps the facts.

## What was seen before writing this

- docs/prereg/edit-arms.md with all its amendments, and the code that ran it
  (`scripts/eval_edit_arms.py`, `scripts/edit_arms_job.py`).
- The full report of run `main-1b` (`eval/edit-arms/report.md`): every win
  rate, content share, length and findings count, and arm D's results. The
  smallest difference below (5 points) was chosen after seeing that B minus C
  was −10.6 points.
- B's feedback for two of the 60 drawn paragraphs (`d3e2084cc6df` and
  `8b379fcdb94a`), read to see how it locates findings. No edit of them was
  read.
- `eval/edit-arms/walk.jsonl`: which repositories the first draw walked, and
  their outcomes. No repository after the 784th in its order was opened.

## Software

- readcost at commit `a57e19e` (version 0.3.0), default configuration, as
  in the edit test. Its checks decide which paragraphs are eligible, and
  they give B's feedback and the sentences E points at. The job stops if
  `src/` and `uv.lock` are not `a57e19e`'s (`eval_edit_arms.verify`).
- spaCy 3.8 with `en_core_web_sm` 3.8.0, as `uv.lock` pins it.
- The scripts are `scripts/eval_edit_localize.py` and
  `scripts/edit_localize_job.py`, added in the commit after this one. They
  reuse the edit test's prompts, client, judges, counting and bootstrap
  from `scripts/eval_edit_arms.py` unchanged.
- Models, revisions, vLLM image, serving arguments and thinking settings
  are those of the edit test as its amendment of 19 November ("judges
  shared with the open-raters plan") fixed them, Mistral Small 4 included,
  since it served in `main-1`:

| Role | Model | Revision |
| --- | --- | --- |
| Editor | `openai/gpt-oss-120b` | `b5c939de8f754692c1647ca79fbf85e8c1e70f8a` |
| Editor | `mistralai/Mistral-Small-4-119B-2603` | `a11f36bebf709121056b1dbcc943d1c6afbe494d` |
| Editor | `allenai/Olmo-3.1-32B-Instruct` | `ac0587e4a7744a551c059d8cd17ba220bc940dae` |
| Judge | `Qwen/Qwen3.8-27B` | `37561816e66b5b9153b1b64c10968c18c1e6f4a0` |
| Judge | `google/gemma-4-31B-it` | `842da3794eaa0b77d5f08bae87a17459d91ff475` |
| Judge | `zai-org/GLM-4.7-Flash` | `7dd20894a642a0aa287e9827cb1a1f7f91386b67` |

## Paragraphs

200 paragraphs: the edit test's 60 and 140 new ones.

The new ones continue the edit test's draw. Its candidates
(`eval/edit-arms/candidates.jsonl`) and its rules stay: the drop reasons,
the files read from each repository, the eligible paragraphs, at most one
paragraph from each repository, and the pick within a repository with
`random.Random(f"20261119:edit-arms:{repo}:pick")`.

1. The script rebuilds the draw's order: the candidates kept by that draw's
   drop reasons, sorted by `owner/repo`, shuffled with
   `random.Random("20261119:edit-arms")`. It stops if the first 784
   repositories in that order are not those of `eval/edit-arms/walk.jsonl`,
   in the same order.
2. It walks on from the 785th, with one more drop reason: a repository named
   in any file under `scripts/`, `eval/` or `docs/` at this plan's commit
   (the corpora of the tests run since `a57e19e`). Such a repository is
   recorded as dropped and not opened.
3. A paragraph whose SHA-256 equals that of one already drawn, in either
   draw, is not eligible.
4. It stops at 140 new paragraphs, or when the order runs out.

Pointers go to `eval/edit-localize/paragraphs.jsonl` (the new 140, in the
edit test's format) and the walk to `eval/edit-localize/walk.jsonl`. The
job fetches each paragraph at its commit and stops using it if its SHA-256
differs, as in the edit test. A paragraph that can no longer be fetched is
reported as missing and left out.

## Arms

| Arm | Text | Paragraphs |
| --- | --- | --- |
| A | the original | all 200 |
| B | one edit, given readcost's feedback | all 200; the edit test's 60 are reused |
| C | one edit, given the generic instruction alone | all 200; the edit test's 60 are reused |
| E | one edit, given feedback that points at the longest sentences | all 200 |

B and C are built exactly as in the edit test: its system message, its two
user messages, temperature 0, the word budget and the reply schema. For the
edit test's 60 paragraphs, B's and C's edits are the replies of `main-1b`,
read from its reply cache; no editor is asked for them again. E's user
message is B's, with E's feedback in place of `{feedback}`. Arm D is not
part of this test.

### E's feedback

E's feedback is built from the same readcost `Result` as B's (the
paragraph checked alone as Markdown, `Config()`, readcost at `a57e19e`).

1. **How many sentences.** B's feedback lists the findings that
   `report.agent` shows: the first eight in its worst-first order. *k* is
   the number of distinct sentences that hold them, a sentence known by the
   finding's `sentence_start` and `sentence_end`. A finding whose sentence
   offsets are missing counts as its own sentence.
2. **Which sentences.** The candidates are the sentences that readcost
   checks and counts in `Result.words`. These are the sentences of each
   extracted segment that have at least four alphabetic tokens and a verb
   or auxiliary, or that `misparsed_verb` accepts. A sentence's length is
   its number of alphabetic tokens. E points at the *k* longest; a tie goes
   to the sentence that comes first. If fewer than *k* sentences qualify, E
   points at all of them.
3. **The text.** B's first line, word for word, with *k* as the count and
   the paragraph's `Result.words` as the words. Then one line per sentence,
   longest first:

```text
readcost: {k} hard-to-read construction{s} in {words} words. Rewrite these sentences where the finding holds; keep the meaning and the facts.
- line {line} [long-sentence] {n} words in one sentence. Fix: Split it into shorter sentences, if the result reads naturally.
```

`{line}` is the line of the paragraph where the sentence starts, counted
as B counts it. `{n}` is the sentence's length. `{s}` is "s" unless *k* is
1. When *k* is 0, E's feedback is empty, as B's is.

So E differs from B in what the lines say and in which sentences they name.
It also lists *k* lines where B may list more, when two findings share a
sentence. E names each sentence by line only, with no excerpt, and gives
no rater precision. Its form, its head, the number of sentences named and
the order to rewrite them are B's.

## Judges

The edit test's fact check: each edit (B, C and E) compared with A once by
each judge, with `JUDGE_PROMPT` and `JUDGE_SCHEMA` from
`scripts/eval_agent_loop.py` at `a57e19e`. For the edit test's 60
paragraphs, the fact checks of B and C are `main-1b`'s replies, read from
its cache.

The edit test's pairwise readability judgement, for E against B only:
each judge, both orders, separate calls, the edit test's prompt and reply
schema.

A missing or unparseable reply is asked for once more at the end of its
phase; if it is still missing, that judgement is left out, and the report
gives the count.

## Counting

As in the edit test. A unit is one paragraph and one editor: 600 units. An
edit **changes content** when at least two of the three judges list at least
one fact lost or changed (`eval_edit_arms.changes_content`). A paired
difference of shares, X minus Y, is taken over the units where both edits
exist. Its 95% interval is a percentile bootstrap over paragraphs, with all
three editors' units of a paragraph resampled together, 10,000 resamples,
seed 0. Win rates, wins, ties, splits and losses are counted as in the edit
test.

## Outcomes

**Primary:** the share of edits that change content, B minus E, paired by
unit, over all 200 paragraphs, with its interval.

Secondary, each with an interval as above:

- B minus C, over the 140 new paragraphs only. This repeats the edit test's
  −10.6 on paragraphs it did not see; it also gets the same figure over all
  200 paragraphs.
- E minus C, over all 200 paragraphs.
- The share of edits that change content, per arm; the mean facts lost,
  added and changed per edit, per arm.
- E against B, win rate, labelled as in the edit test (smallest difference
  0.55).
- Scope. For each edit, the share of the original's checked sentences that
  appear unchanged in the edit, compared after collapsing runs of
  whitespace. It is given separately for the sentences that the arm's feedback
  pointed at and for the rest. C points at none, so all of C's sentences
  count as the rest. A sentence counts as pointed at by B when it holds one
  of the findings B's feedback lists.
- Overlap. The share of E's sentences that B's feedback also points at,
  over all paragraphs. Also B minus E for the paragraphs where E points at
  exactly B's sentences, and for the rest, without decision.
- Length (words in the edit over words in A, the median per arm and editor)
  and readcost's default-rule findings after each edit, as in the edit test.
- Each of the above per editor and per judge, deciding nothing.

## Smallest difference that counts

5 points of the share of edits that change content: about half of the edit
test's −10.6. If readcost's rules account for less than that, most of the
effect comes from pointing at sentences.

With 200 paragraphs and three editors, the 95% interval of B minus E is
expected to have a half-width of about 4.5 to 5.5 points. That expectation
scales the edit test's interval for B minus C (half-width 8.6 points on 60
paragraphs) to 200. B and E both point at sentences, so their edits may be
more alike than B's and C's, which would narrow it.

## Decision rules

| Claim | Holds if |
| --- | --- |
| readcost's findings keep facts better than pointing at the longest sentences | B minus E has an upper 95% bound under 0 and an estimate of −0.05 or less |
| Pointing at the longest sentences keeps facts as well as readcost's findings | B minus E has a lower 95% bound over −0.05 |

The two cannot both hold. When neither does, the report says the test is
inconclusive. If the upper bound is under 0 and the estimate is between
−0.05 and 0, the report says that B kept facts better by less than the
smallest difference. If the lower bound is over 0, it says that E kept facts
better than B.

What follows, for readcost:

- If the first claim holds, docs/agents.md says that readcost's feedback
  kept an editor's facts better than feedback pointing at the longest
  sentences, with the figures.
- If the second claim holds, the report says plainly that the fact-keeping
  effect was not shown to need readcost's rules. A separate pull request then
  proposes what to change. Such changes could be a long-sentence pointer
  in `-o agent`, or fewer rules on by default. This test does not decide
  them.
- B minus C on the new paragraphs is read alone. If its upper bound is under
  0, the edit test's finding repeats on new paragraphs. If its interval
  contains 0, it does not repeat, and the report says so whatever the primary
  outcome.

The judges are models, and the fact check is one prompt. "Changes content"
means that two of three model judges listed a lost or changed fact. No person
reads the edits.

## Calls and caps

| Calls | Count |
| --- | --- |
| E edits, 200 paragraphs × 3 editors | 600 |
| B and C edits, 140 new paragraphs × 3 editors × 2 | 840 |
| Fact checks of E, 600 edits × 3 judges | 1,800 |
| Fact checks of B and C on the new paragraphs, 840 edits × 3 judges | 2,520 |
| E against B, 600 units × 2 orders × 3 judges | 3,600 |
| In all | 9,360 |

The job starts with `main-1b`'s 8,661 replies as its cache. Two calls whose
model, system message and prompt are the same get one reply, so 9,360 is an
upper bound on new calls. The run stops before a call that would take the
cache past **19,000 replies**.

One Hugging Face Job on one H200, at $5 an hour, with a timeout of
**2.5 hours ($12.50)**. The job's clock stops new calls 15 minutes before
the timeout, writes the report from what is done, and uploads it. If the job
stops with an error before any judge has been called, after the fix one more
job may run under the same timeout. Together the two may bill at most
**3 GPU hours ($15)**. No other job runs for this test without an
amendment. The estimate is 1 to 1.6 hours: six model loads, the 1,440
edits and 7,920 short judgements.

**Order.** One model is loaded at a time:

1. each editor in turn: E's edits for all 200 paragraphs, then B's and C's
   for the new 140;
2. each judge in turn: the fact checks of E, then of B and C on the new
   paragraphs (the primary outcome), then E against B.

Calls within a phase are shuffled with `random.Random("20261120:edit-localize:calls:<phase>")`.
If the job stops before every judge has finished its fact checks, the
primary outcome is computed from the judges that finished, the report says
so, and no claim is decided.

**Outputs.** As in the edit test: every reply, `run.json`, the model logs and
the report go to the private dataset `arclabs561/readcost-labels`, under
`edit-localize/<run id>/`. The upload stops if that dataset is not private.
The paragraphs are not uploaded.

## What the report contains

- Counts at each step of the continued draw.
- Calls made, calls served from the cache, and GPU time.
- Every outcome above, whatever the result, and each claim and whether it
  holds.
- Anything else under the heading "Exploratory, not pre-registered".

readcost's rules and defaults do not change in this pull request.

## Amendments

### 20 November 2026, before the draw: the draw's own files

The new drop reason (step 2 of the draw) names every file under `eval/`.
That includes `eval/edit-arms/candidates.jsonl`, which lists every
candidate, so as written it would drop every repository. It now leaves out
the files under `eval/edit-arms/`: the draw's own candidates, walk and
pointers. The files of every other test still count. No repository past the
784th had been opened when this was written, and no model had been called.
