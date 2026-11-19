# Pre-registration: does readcost's feedback make an agent's edit easier to read?

Written 19 November 2026 (UTC), before any paragraph below was drawn and
before any model was called. The commit that adds this file is the
registration; its timestamp on GitHub is the record. Nothing in this file
changes after that commit. Any change made later goes in a dated
"Amendments" section at the end, with the reason.

## Why

readcost's main use is feedback for agents that write documentation: an
agent checks a paragraph, reads `readcost check -o agent`, and edits.
"Agents editing in a loop" in [evaluation.md](../evaluation.md#agents-editing-in-a-loop)
measured what such edits do to readcost's own findings, to length and to
facts. It did not measure whether the edited text is easier to read, and
it had no control arm. An agent told only "make this clearer" may do as
well. This test compares three versions of each paragraph: the original,
an edit guided by readcost's feedback, and an edit guided by a generic
instruction of the same kind. Model judges compare the versions blind.

## What was seen before writing this

- The results of "Agents editing in a loop" and the prompts in
  `scripts/eval_agent_loop.py` and `scripts/rater_ensemble.py`.
- `docs/prereg/heldout-precision.md` on branch `exp/heldout-precision`
  (commit `10f9e21`), for the repositories it uses.
- The `total_count` that GitHub's repository search returned on
  19 November 2026, about 03:20 UTC, for the query below on each creation
  day from 2 to 17 November 2026. It was 173 to 492 per day, 5,366 in all,
  so no day reaches the search's limit of 1,000. No repository name,
  README or finding from it was read.
- The OpenRouter model pages of the six models below, for their prices.

## Software

- readcost at commit `a57e19e` (version 0.3.0), default configuration
  (`Config()`, no repository config read). Its default rules are
  stacked-nouns, long-dependency, inanimate-subject,
  reduced-object-relative, hyphen-compound and inline-list. The script
  stops if `git diff a57e19e -- src uv.lock` is not empty, since the
  feedback in arm B and the findings counts depend on it.
- spaCy 3.8 with `en_core_web_sm` 3.8.0, as `uv.lock` pins it.
- The model client is `ask` in `scripts/rater_ensemble.py`: OpenRouter's
  chat completions endpoint, temperature 0, a strict JSON schema for the
  reply, one retry on failure. The commit after this one adds an optional
  system message to it; nothing else about it changes.

## Paragraphs

### Population

Repositories from GitHub's repository search, run once on 19 November
2026 (UTC), one query per creation day from 2 to 17 November 2026:

```text
created:DAY stars:10..49 fork:false archived:false
```

sorted by stars, descending, 100 per page, every page. Every repository
returned, with its star count and creation time, goes into
`eval/edit-arms/candidates.jsonl`, committed.

The star band keeps this sample apart from the held-out precision study,
which draws repositories created on the same days with 50 stars or more.

A repository is dropped, and the reason recorded, when:

1. its owner is `arclabs561`, or its `owner/repo` appears in any file under
   `scripts/`, `eval/` or `docs/` at `a57e19e` (the evaluation corpora and
   the rulebench);
2. it appears in `eval/heldout/candidates.jsonl` on `origin/main` or
   `origin/exp/heldout-precision` at the time of the draw (if that file
   exists then);
3. it is a fork or archived;
4. it has no README, or its README is over 1 MB.

Reasons 1 to 3 are checked for every candidate, reason 4 only for the
repositories that the draw walks.

### Files

For each repository, at the head commit of its default branch at the time
of the draw:

- the README that `repos/{repo}/readme` returns;
- up to two Markdown files (`.md`, `.markdown`, `.mdx`) whose path,
  compared without case, starts with `docs/`, `doc/`, `design/`, `rfcs/`
  or `adr/`, or contains `/adr/` or `/design/`, and whose file name does
  not start with README, CHANGELOG, LICENSE, CONTRIBUTING, CODE_OF_CONDUCT
  or SECURITY. They are chosen with `random.Random(f"20261119:edit-arms:{repo}")`
  from the sorted list of such paths, and each must be under 1 MB.

### Eligible paragraphs

A file is decoded as UTF-8 (invalid bytes replaced). A paragraph is a run
of non-blank lines between blank lines, outside fenced code blocks (lines
starting with three backticks or three tildes, after up to three spaces)
and outside HTML comments. It is eligible when:

1. its first line, after up to three spaces, starts with none of `#`, `>`,
   `|`, `-`, `*`, `+`, `<`, `!`, `[`, `=`, or a number followed by `.` or `)`;
2. no line is indented by four or more spaces or a tab, and no line starts
   with `|`;
3. it has 120 to 260 words, counted as whitespace-separated tokens;
4. readcost's language check (`readcost.lang.other_language`) does not name
   another language for it;
5. readcost, checking it alone as Markdown with the default configuration,
   reports two or more findings.

### Draw

1. Sort the kept repositories by `owner/repo` and shuffle them with
   `random.Random("20261119:edit-arms")`.
2. Walk them in that order. For each, list the eligible paragraphs in its
   files, sorted by path and offset, and drop any whose text has the same
   SHA-256 as a paragraph already drawn. If any remain, draw one with
   `random.Random(f"20261119:edit-arms:{repo}:pick")`.
3. Stop at 60 paragraphs. At most one comes from each repository.

The repository holds pointers only, in `eval/edit-arms/paragraphs.jsonl`:
repository, commit, path, character offsets of the paragraph in the
decoded file, the paragraph's SHA-256, its word count and its findings
count. The text belongs to the repositories' authors. The evaluation job
fetches each file at its commit when it runs, cuts the paragraph out, and
stops if the SHA-256 differs. A paragraph that can no longer be fetched is
reported as missing and left out.

## Arms

| Arm | Text |
| --- | --- |
| A | the original paragraph |
| B | one edit, given readcost's feedback |
| C | one edit, given the generic instruction alone |

One round per arm, no loop. B and C use the same editor model, the same
system message, temperature 0, and the same instruction and length budget.
The only difference between their prompts is the block of readcost
feedback. The word budget is ⌈1.2 × the original's words⌉; an edit over
it is kept and counted.

System message, for every edit:

```text
You edit technical documentation. You will get one paragraph from the README or the documentation of a software project. Return the whole revised paragraph. Keep its Markdown, such as links and inline code.
```

Arm C, user message:

```text
Revise this paragraph to make it easier to read. Keep every fact.
The revision must be at most {budget} words.

Paragraph:
{text}
```

Arm B, user message:

```text
Revise this paragraph to make it easier to read. Keep every fact.
The revision must be at most {budget} words.

A prose checker reported this about the paragraph:
{feedback}

Paragraph:
{text}
```

`{feedback}` is `readcost.report.agent([result], feedback_link=False)` for
the paragraph checked alone as Markdown: the text of `readcost check -o agent`.
`ask` appends `Return only the JSON object, no prose.` to every user
message, and the reply schema is `{"text": string}`.

Editor models, one from each of three families:

| Family | OpenRouter id |
| --- | --- |
| Anthropic | `anthropic/claude-opus-5.5` |
| Google | `google/gemini-4-argon` |
| Mistral | `mistralai/mistral-large-4-0` |

An edit that comes back empty or unparseable is asked for once more at the
end. If it is still missing, every comparison that needs it is left out,
and the report gives the count.

## Judges

Three judge models, from three families that edit nothing:

| Family | OpenRouter id |
| --- | --- |
| Moonshot AI | `moonshotai/kimi-k3.1-pro` |
| DeepSeek | `deepseek/deepseek-v4.1-flash` |
| xAI | `x-ai/grok-4.7` |

So every judge comes from a family other than the editor of the pair it
judges. Every judge does every judgement below.

### Which version is easier to read

For each paragraph and editor there are three pairs: B against A, C
against A and B against C. Each judge sees each pair twice, once in each
order, in separate calls. The order of all judge calls is shuffled with
`random.Random("20261119:edit-arms:calls")`. A judge sees only the two
texts, labelled Version 1 and Version 2. It is not told which is the
original, that an edit was made, or that a checker was used.

```text
Here are two versions of one paragraph from the documentation of a software project. The intended reader is a developer who is new to the project and reads its documentation to learn what it does and how to use it.

Which version is easier for that reader to read and understand? Judge only how easy each is to read. Assume both say the same thing; a separate check compares their content. Answer "tie" only if neither is easier to read.

Version 1:
{first}

Version 2:
{second}

Give your reason in one or two sentences, then your answer: "1", "2" or "tie".
```

Reply schema: `{"reason": string, "easier": "1" | "2" | "tie"}`.

### Facts

Each edit (arms B and C, every editor) is compared with A once by each
judge, with `JUDGE_PROMPT` and `JUDGE_SCHEMA` from `scripts/eval_agent_loop.py`
at `a57e19e`, unchanged: the original as `{a}`, the edit as `{b}`. The
reply lists facts lost, added and changed in meaning.

A missing or unparseable judgement is asked for once more at the end; if
it is still missing, that judge's judgement is left out, and the report
gives the count.

## Counting

For one pair X against Y, one judge and one paragraph and editor:

- X **wins** if the judge picks X in both orders, and **loses** if it picks
  Y in both orders.
- Every other outcome is a **tie**: tie in both orders, tie in one, or a
  different version in each order (a **split**, which shows position bias).
  Splits are also counted on their own.
- Score: 1 for a win, 0.5 for a tie, 0 for a loss.

A unit is one paragraph and one editor (60 × 3 = 180 units). A unit's score
for X against Y is the mean of the scores of the judges that judged it in
both orders. The **win rate** of X against Y is the mean unit score over
units. Its 95% interval is a percentile bootstrap over paragraphs (all
three editors' units of a paragraph are resampled together), 10,000
resamples, seed 0.

An edit **changes content** when at least two of the three judges list at
least one fact lost or changed. Added facts are reported apart and do not
count toward this.

## Outcomes

Primary: the win rate of B against C, with its interval.

Secondary, each with a paragraph bootstrap interval as above:

- the win rates of B against A and of C against A;
- the share of B edits and of C edits that change content, and their
  difference (B minus C, paired by unit);
- the mean number of facts lost, added and changed per edit, per arm;
- length: the median of words in the edit over words in A, per arm and
  editor, and the count of edits over budget;
- readcost's default-rule findings in each version: the median and mean
  count per arm, and the share of edits with none. B was given readcost's
  findings and told to address them, so fewer findings after B shows that
  the editor followed the feedback. It is not evidence that B reads
  better; only the judges speak to that.

Reported for each editor and each judge, deciding nothing: the three win
rates, the win, tie, loss and split counts, and the content measures.
Agreement between judges: for each pair of judges, the share of units
where both gave the same outcome (win, tie or loss).

## Smallest difference that counts

A win rate of 0.55. At 0.55, B wins the comparison in ten more of every
hundred judgements than C does, with ties split. A smaller difference would
not justify telling agents to run readcost rather than ask for clarity in
plain words.

With 60 paragraphs, three editors and three judges, the 95% interval is
expected to have a half-width of 0.05 to 0.09, depending on how much the
editors and judges agree. A true win rate near 0.55 may well end
inconclusive; that is the price of the cost cap below.

## Decision rules

For each comparison of X against Y:

- **X better**: lower 95% bound over 0.50 and win rate at least 0.55;
- **no meaningful advantage for X**: upper 95% bound under 0.55;
- **inconclusive**: neither.

If the upper bound is under 0.50, the report says in words that Y did
better.

Claims:

| Claim | Holds if | Otherwise |
| --- | --- | --- |
| readcost's feedback makes an agent's edit easier to read than a generic instruction | B against C is "B better", and the upper 95% bound of the difference in content-changing edits (B minus C) is under +0.10 | not shown |
| readcost adds nothing for agents over a generic instruction | B against C is "no meaningful advantage for B" (C at least as good as B, within the smallest difference) | not shown |
| An edit with readcost's feedback is easier to read than the original | B against A is "B better", and the upper 95% bound of the share of B edits that change content is under 0.10 | not shown |
| An edit with a generic instruction is easier to read than the original | C against A is "C better", with the same bound for C edits | not shown |

When B against C is "B better" but the content bound fails, the report says
that B's edits read easier but changed facts more often, and the first
claim does not hold. The first two claims cannot both hold; when neither
does, the result is inconclusive and the report says so.

If the second claim holds, the report says plainly that readcost's feedback
was not shown to help an agent edit beyond a plain request for clarity, and
docs/agents.md gets a proposal to say so.

The judges are models. Model judges may prefer edited, model-written text
over the original whatever its quality, so the comparisons against A can
favour both edits. B against C compares two edits by the same editor, so
that bias should mostly cancel there; it is the primary outcome for that
reason. No person reads the texts, so "easier to read" means easier
according to three model judges.

## Cost cap

Prices on OpenRouter on 19 November 2026, in dollars per million input and
output tokens: Claude Opus 5.5 4 and 20, Gemini 4 Argon 2 and 10 (a 50%
discount on 4 and 20), Mistral Large 4 0.70 and 2.10, Kimi K3.1 Pro 0.24
and 8.40, DeepSeek V4.1 Flash 0.051 and 0.567, Grok 4.7 2 and 6.

Planned calls: 360 edits (60 × 3 editors × 2 arms), 3,240 readability
judgements (180 units × 3 pairs × 2 orders × 3 judges) and 1,080 fact
checks (360 edits × 3 judges), 4,680 in all.

The run stops before a call that would take it past either cap:

- **$60** in all, summed from the cost OpenRouter reports for each reply
  (a reply that reports no cost counts as $0.05);
- **5,200 calls**.

Replies are cached by a hash of model, system message and prompt, with
their cost, and the caps count every cached reply. A later run reuses the
cache and does not pay twice, so the caps hold across runs that share the
cache.

Calls go in this order, so that a stop at the cap loses the least
important work: all edits; B against C; the fact checks; B against A;
C against A. If the run stops before B against C is complete, no claim is
decided, and the report gives what was done.

## What the report contains

- Counts at each step of the draw: candidates, each drop reason,
  repositories walked, paragraphs drawn, missing at run time.
- Calls made, calls served from the cache, the cost, and the model id
  OpenRouter served for each requested model.
- Every outcome above, whatever the result; each claim and whether it
  holds.
- Anything else under the heading "Exploratory, not pre-registered".

The script is `scripts/eval_edit_arms.py`, added in the commit after this
one, and the job is `edit-arms` in `.github/workflows/eval.yml`, added in
the commit after that. It runs when the repository secret
`OPENROUTER_API_KEY` is set and writes one line to the run summary saying
that it skipped when it is not. readcost's rules and defaults do not
change.

## Amendments

None yet.
