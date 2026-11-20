# Pre-registration: a search over readcost's fix texts and scope line, with a held-out test

Written 20 November 2026 (UTC), before any model was called for this test and
before the held-out paragraphs were drawn. The commit that adds this file is
the registration; its timestamp on GitHub is the record. Nothing in this file
changes after that commit. Any change made later goes in a dated
"Amendments" section at the end, with the reason.

## Why

<!-- readcost: ignore stacked-nouns -->
The factorial in [agent-text-factorial.md](agent-text-factorial.md) found
that the rule's own fix was the largest part of readcost's agent feedback.
Compared with a generic fix, it cut edits that change content by 14.9 points
and raised readability against the edit test's arm C by 0.163. A scope line
cut content changes by 9.9 points but lowered readability by 0.085. The
precision note lowered utility slightly. By that plan's rules, stage 2 starts
from HsFpX: today's text without the precision note. It searches part by
part.

This plan is stage 2, in two parts. The **search** tries a few rewordings of
each default rule's fix and of the scope line, on the paragraphs the earlier
tests used, and picks one text, R\*. The **held-out test** then compares R\*
with today's text on new paragraphs, with an editor and two judges that the
search did not use. Only the held-out test can change readcost.

## What was seen before writing this

- Everything in docs/evaluation.md on `main` at `ca85e2e`, including the
  factorial's full report (`eval/agent-text/report.md`): its per-factor,
  per-arm and per-editor figures. No single edit or judgement of the
  factorial was read.
- The default rules' fixes, titles and examples in `src/readcost/features.py`.
- How often each rule appears in readcost's feedback for the 200 paragraphs:
  stacked-nouns in 97, inline-list in 133, reduced-object-relative in 60,
  long-dependency in 30 and hyphen-compound in 34. Five paragraphs have no
  finding.
- The Hugging Face Hub pages of the two held-out judges named below, for
  their size, licence and how they are served.

## Software

As in the factorial: readcost at `main`, whose `src/` and `uv.lock` are those
of `e1871db` (the job checks the same digest), and the same vLLM image and
settings. The scripts are `scripts/eval_agent_text.py`, extended, and
`scripts/agent_text_search_job.py`, in the commit after this one.

## Part 1: the search

**Paragraphs, editors, judges.** The factorial's 200 paragraphs (all that
have a finding), its two editors (gpt-oss-120b and Mistral Small 4) and its
two judges (Qwen3.8 27B and Gemma 4 31B), at the same revisions. The task
message, the fact check, the readability judgement against C and the scores
are the factorial's. Utility is read minus change.

**The seed** is HsFpX: the first line orders a rewrite, no scope line, the
rule's own fix, no precision note, and the finding's message.

**Species.** Each candidate changes one part of the seed and keeps the rest.

*Fix species*, one per default rule. A candidate replaces that rule's fix
everywhere the rule appears. Where readcost adds to the fix today (for
long-dependency and inline-list, the reminder to keep a "because" clause), it
adds the same to every candidate. Each rule has the seed's fix, called v0,
and three candidates:

| Rule | Candidate | Fix |
| --- | --- | --- |
| stacked-nouns | v1 | Unpack the run of nouns with a preposition or a verb: 'the cache eviction policy threshold' becomes 'the threshold at which the cache evicts'. Leave an established term as it is. |
| stacked-nouns | v2 | Keep at most two nouns together; say how the others relate with 'of', 'for' or a verb. Leave an established term as it is. |
| stacked-nouns | v3 | Keep at most two nouns together. |
| long-dependency | v1 | Put the subject next to its verb: move the long phrase between them to the end of the sentence, or into a sentence of its own. |
| long-dependency | v2 | Bring the two words together. Move what separates them after the verb, or split the sentence, and keep every fact in one of the two. |
| long-dependency | v3 | Put the subject next to its verb. |
| reduced-object-relative | v1 | Add the 'that' back: 'the file the tool writes' becomes 'the file that the tool writes'. |
| reduced-object-relative | v2 | Keep the 'that'. If the clause is long, make it a sentence of its own. |
| reduced-object-relative | v3 | Add 'that' at the start of the clause. |
| hyphen-compound | v1 | Write the relationship out: 'a user-config-driven step' becomes 'a step driven by the user's config'. |
| hyphen-compound | v2 | Say how the hyphenated words relate, with a preposition or a verb; keep an established hyphenated term. |
| hyphen-compound | v3 | Replace the hyphenated chain with a phrase that says how its words relate. |
| inline-list | v1 | Use a bulleted list, one item per line, after a sentence that says what the items are. |
| inline-list | v2 | If there are more than three items or they are long, use a bulleted list; otherwise keep them in the sentence. |
| inline-list | v3 | Use a bulleted list, and keep every item. |

*Scope species.* A candidate adds one sentence to the first line:

| Candidate | Added |
| --- | --- |
| v0 | nothing (the seed) |
| v1 | ` Leave the other sentences as they are.` (the factorial's S) |
| v2 | ` Change other sentences only where they need it.` |
| v3 | ` Keep the other sentences unless a change helps the reader.` |

The candidates were written from the factorial's figures alone. A rule's
candidates are judged only on paragraphs where that rule appears in the
feedback. The scope candidates are judged on all 195 paragraphs with a
finding. The seed is the same text in every species, so it is judged once on
each paragraph and editor. Its factorial edits are reused where the factorial
asked for them.

**Choice.** For each species, the candidate with the highest mean utility
over its units wins. The seed stays unless the winner's mean utility is at
least **0.02** above the seed's on the same units. R\* is the seed with
every species' choice. The search reports each candidate's mean change, read
and utility, with paragraph bootstrap intervals, but chooses only by the rule
above. That rule takes the best of several noisy candidates, so R\*'s
advantage on these paragraphs will overstate its true advantage. The
held-out test is there for that.

**Calls.** About 3,500 new units at 7 calls each (1 edit, 2 fact checks, 4
readability judgements): about 24,500 calls. One job on one H200, timeout
**1.75 hours ($8.75)**, starting from the factorial's replies. It stops before
loading a model if fewer than 95% of the C anchors are in the cache, and
before a call that would take the cache past **70,000** replies. One editor
then one judge at a time; edits, then fact checks, then readability, shuffled
within a phase with `random.Random("20261120:agent-text-search:calls:<phase>")`.

If R\* is the seed itself, the report says so, and part 2 compares the seed
(HsFpX) with today's text (HsFPX). The only difference is the precision note.

## Part 2: the held-out test

**Paragraphs.** 100 new paragraphs, drawn after the search's report is
written. The draw continues the edit test's walk in the same way as the
localization control (its candidates, order, drop reasons, files and pick),
from the repository after the last one that test walked. It uses readcost at
`main` as above for eligibility, with the edit test's rule of two or more
findings. One more drop reason: a repository named in any file under
`scripts/`, `eval/` or `docs/` at the commit of this plan, except the files
under `eval/edit-arms/` and `eval/edit-localize/` (those list the draw's own
candidates and walk).

**Arms.** R0, today's text (`readcost check -o agent`, HsFPX); R\*; and C,
the edit test's generic instruction with no checker block.

**Editors.** gpt-oss-120b and Mistral Small 4, which the search used, and
Olmo 3.1 32B, which it did not. They are at the revisions of the edit test.

**Judges.** Two families that no earlier test used, as editor, judge or rater:

| Family | Repository | Licence |
| --- | --- | --- |
| NVIDIA | `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16` | OpenMDW 1.1 |
| Microsoft | `microsoft/phi-4` | MIT |

They are pinned to the revision the Hub serves when the held-out job starts,
which the job records. Thinking is off where the model allows it. If a judge
cannot be served on one H200, or more than 10% of its replies in the first
200 calls do not parse, `ibm-granite/granite-3.3-8b-instruct` (Apache-2.0)
takes its place, and the report says so.

**Judgements.** For each unit (paragraph and editor):

- each judge's fact check of R0's, R\*'s and C's edits, as in the factorial.
  An edit changes content when at least one judge lists a lost or changed
  fact;
- each judge's readability judgement, both orders, for R\* against R0, R\*
  against C, and R0 against C.

**Outcomes.** Primary, two parts, each paired by unit, with a paragraph
bootstrap 95% interval:

1. R\* against R0, readability win rate;
2. R\* minus R0, the share of edits that change content.

Secondary: R0 against C and R\* against C, in readability win rate and in
the share changing content; per editor (Olmo apart), per judge.

**Decision.** R\* replaces today's text in readcost when both hold:

- R\* against R0 has a win rate whose lower 95% bound is over 0.50, or a win
  rate of at least 0.47 when R\* minus R0 in content changes has an upper
  bound under 0;
- R\* minus R0 in content changes has an upper bound under +0.03.

Otherwise today's text stays, and the report says which part failed. When R\*
replaces it, a pull request changes the rules' fixes, the scope line or the
precision note in `src/readcost/` to R\*'s, with a changelog entry citing this
test. readcost's tests then check the new text.

**Calls and caps.** 900 edits (100 paragraphs, 3 editors, 3 arms); 1,800 fact
checks; 3,600 readability judgements. About 6,300 calls, one job on one H200,
timeout **1.25 hours ($6.25)**. If either job stops with an error before any
judge is called, one more job may run after the fix. All jobs of this plan
together bill at most **4 GPU hours ($20)**.

**Outputs.** Every reply, `run.json`, the model logs and the reports go to the
private dataset `arclabs561/readcost-labels` under `agent-text-search/<run id>/`
and `agent-text-heldout/<run id>/`. The upload stops if the dataset is not
private. The paragraphs are not uploaded.

The judges and editors are models; no person reads an edit. "Easier to read"
means easier according to two model judges from families that took no part
in the search.

## Amendments

### 20 November 2026, before any model call: a readcost directive

readcost's own check of this file read "A scope line cut content changes" as
five stacked nouns: its parser took "cut" for a noun. That error made the
file fail the repository's documentation check. A
`<!-- readcost: ignore stacked-nouns -->` comment now comes before the
paragraph under "Why". No word of the plan changed.
