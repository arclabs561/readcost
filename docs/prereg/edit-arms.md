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

19 November 2026, before any model was called:

1. The job runs only when started by hand or on the branch
   `exp/edit-arms`, and on other pull requests writes one line saying so.
   A pull request can read only its own cache and the base branch's, so a
   run there would pay again for replies that are already cached here.
2. Two calls whose model, system message and prompt are the same get one
   reply, from the cache. This happens when two edits are the same text,
   for example when two editors leave a paragraph unchanged. The judgement
   then counts for each unit that needs it, so the plan's 4,680 calls is an
   upper bound.
3. `rater_ensemble.ask` also records the token counts OpenRouter reports.
   The request it sends is as described above.
4. The shell that runs the draw can search GitHub but cannot read
   repositories through its API, so the first attempt at the draw found
   every repository unavailable and read no file. The draw instead clones
   each repository's default branch without file contents
   (`git clone --bare --depth 1 --filter=blob:none`). This gives the head
   commit and the list of files, and the files are read from
   `raw.githubusercontent.com` at that commit. The 1 MB limit applies to
   the file as read (its text encoded as UTF-8), since the clone has no
   sizes. The README is the file
   GitHub would show: the first match in the root, then in `.github/`,
   then in `docs/`, taking names (compared without case) in the order
   `README.md`, `README.markdown`, `README.mdx`, `README.rst`,
   `README.txt`, `README`. Forks and archived repositories are known from
   the search results.
5. Drop reason 2 could not act. The draw read `origin/main` as last
   fetched, before the held-out precision study merged its
   `eval/heldout/candidates.jsonl`, and the study's branch had no such
   file. Checked afterwards against that file as merged: none of the 5,367
   candidates is in it.
6. The draw walked 784 repositories: 60 paragraphs drawn, 694 with no
   eligible paragraph, 27 with no README, 3 that could not be cloned.

19 November 2026 (UTC), after pull request #102 was opened and before any
model was called:

7. **Arm D: B's prompt, with the feedback worded as questions.**

   *Why.* Two held-out precision tests in docs/evaluation.md on `main`
   ("Held-out precision: a wider panel and unprimed raters" and "Precision
   across formats") found that model raters accept far more findings when
   they are shown readcost's rule and message than when they see the same
   sentence alone. An editor model may defer to the feedback in the same way.
   B's feedback reads as orders ("Rewrite these sentences where the finding
   holds", "Fix: …"), so it may prompt edits that a finding does not justify.
   Pull request #102 words `-o agent` as questions and gives held-out
   precision figures in place of in-sample ones. Arm D tests that wording on
   the same paragraphs, in the same run, before it ships.

   *The arm.* D uses B's system message and B's user message. Only
   `{feedback}` differs: it is the feedback as #102 words it. That text is
   built from the same `Result` as B's feedback (readcost at `a57e19e`,
   the paragraph checked alone as Markdown, `Config()`). So D names exactly
   the same findings as B, in the same order, with the same messages and
   fixes. A function in `scripts/eval_edit_arms.py` builds it. Its strings
   are copied from `src/readcost/report.py` on branch `feat/agent-questions`
   at commit `6769c81d10e7e25612a7d6404e199ada0e4fb6ba`: `AGENT_HEAD`,
   `_measured_note` and the per-finding line "… Is it hard to follow here?
   <note> If it is, <fix>". The figures in the note come from that commit's
   `src/readcost/data/rule_precision.json` (held-out, 12 raters). It is
   copied unchanged to `eval/edit-arms/rule_precision.json`, and the script
   stops if the copy's SHA-256 differs. readcost stays pinned at `a57e19e`,
   and the verify step does not change.

   D differs from B in two ways at once: the wording, and held-out figures
   in place of in-sample ones. So D against B tests #102's feedback as a
   whole, not its wording alone. #102's other changes are not part of D.
   For example, it turns inanimate-subject off by default, but D's findings
   are those at `a57e19e`.

   *Comparisons.* D against B, D against C and D against A. Each judge sees
   each pair in both orders, in separate calls, with the same prompt as the
   other pairs. Counting, the paragraph bootstrap and the labels ("better",
   "no meaningful advantage", "inconclusive") are as for the other pairs.
   Each of D's edits gets the fact check from all three judges. Length and
   readcost's findings are counted for D as for B and C. Three paired
   differences, D minus B, are also reported, each with a paragraph
   bootstrap interval as above: the share of edits that change content,
   facts lost per edit (the mean over judges), and length change, which is
   the absolute value of an edit's words over A's words minus 1.

   *What stays.* The primary outcome is still B against C. Its decision
   rules and the four claims above do not change. D's comparisons are
   secondary.

   *How D is read.*

   | Reading | Holds if |
   | --- | --- |
   | The question wording should ship | D against B has a lower 95% bound over 0.45, so B has no meaningful advantage over D. In addition, D loses fewer facts than B or changes length less (the upper 95% bound of that D minus B difference is under 0). Finally, D does not lose more facts than B (the lower bound for facts lost is not over 0). |
   | The question wording should not ship | D against B has an upper 95% bound under 0.50 and a win rate of at most 0.45, so B reads better. Or D loses more facts than B: the lower 95% bound of D minus B, facts lost per edit, is over 0. |
   | Neither | The report says the run does not speak for or against the wording. |

   Both readings cannot hold together. D against C and D against A are
   read like B against C and B against A. "An edit with feedback as
   questions beats a generic instruction" holds if D against C is "D
   better" and the upper 95% bound of D minus C, the share of edits that
   change content, is under +0.10. "An edit with feedback as questions
   beats the original" holds if D against A is "D better" and the upper
   95% bound of the share of D's edits that change content is under 0.10.

   *Calls and cost.* D adds 180 edits (60 paragraphs and 3 editors), 3,240
   readability judgements (180 units, 3 pairs, 2 orders, 3 judges) and 540
   fact checks (180 edits, 3 judges). That is 3,960 calls, and 8,640 in all
   with the original 4,680. The original estimate of $6 to $57 assumed
   prompt and reply sizes from the drawn paragraphs, and from 0 to about
   2,000 reasoning tokens in each reply from every model but Mistral Large.
   The same assumptions give $4 to $46 for D. Most of it is the judges'
   reasoning on the 3,240 judgements. D's feedback is longer than B's
   (1,007 characters on average over the 60 paragraphs, against 648),
   which adds under $0.10.

   *Caps.* The caps rise by D's planned calls and D's high estimate, to
   **$106** and **9,160 calls** for the whole run, counted as before over
   every reply in the cache. The original five phases keep the old caps:
   the run stops before a call in them that would take it past $60 or
   5,200 calls. Only D's phases may go past those, up to $106 and 9,160
   calls. If an original phase stops at its cap, D's phases do not run.

   *Order.* The original five phases run first, in the order above. D's
   phases follow, in this order:

   1. D's edits;
   2. D against B;
   3. D's fact checks;
   4. D against C;
   5. D against A.

   B against C is the second phase of the run, so it completes under
   the old cap, as before; at the high estimate the first two phases cost
   about $20. D's judge calls are shuffled within each phase with seeds of
   the same form, `20261119:edit-arms:calls:` followed by DB, DC, DA or
   facts-D. An edit or judgement that is missing is asked for once more at
   the end of its phase, as for the others.

   *Report.* It adds:

   - a table for D's three comparisons;
   - D's rows in the tables of content, length and findings;
   - the three differences of D minus B;
   - each reading of D, and whether it holds.

   *What was seen before writing this.* To size D's feedback, the 60
   paragraphs were fetched at their commits, and B's and D's feedback were
   computed for each; no model was called. One paragraph's feedback was
   read in full: `d3e2084cc6df`, which is about one third Chinese
   characters. readcost's language check did not name another language for
   it, so it stays in the draw, as the rules above say.

19 November 2026 (UTC), before any model was called:

8. Pull request #102 was merged into `main` at 14:34 UTC as `5631de4`,
   four minutes before amendment 7 was committed. Amendment 7 was written
   as if it were still open. On `main` at `5631de4`, the wording of
   `-o agent` is the same as at `6769c81`, and `rule_precision.json` has
   the same SHA-256 as the copy in `eval/edit-arms/`. So D's feedback is
   what readcost on `main` prints for `a57e19e`'s findings, and B's is what
   it printed before. Amendment 7's readings apply unchanged, read as
   follows. "The question wording should ship" means it should stay on
   `main`. "It should not ship" means `main` should go back to B's wording,
   or try another one, and docs/agents.md should say why.

### 19 November 2026, before any model call: where the key lives

The key is an environment secret, in the GitHub environment `openrouter`,
not a repository secret, and the job asks for that environment. The owner
sets a required reviewer on it, so each run waits for approval before it
gets the key. The job runs only by hand or for this branch of this
repository; a fork's branch of the same name does not qualify. Nothing about
the arms, models, prompts, outcomes or caps changes.

### 19 November 2026, before any model call: open-weight models on Hugging Face Jobs

The owner approved this change before any model was called. No reply,
edit or judgement exists.

*Why.* The run will not use OpenRouter. GitHub Models, the other way to
call models without a key, was retired on 30 July 2026. The models below
have open weights. They run with vLLM inside Hugging Face Jobs, one H200
GPU per job, billed by the minute at $5 an hour, from the owner's
account. Weights pinned to a revision give the same model on every run,
and none of the six families is Anthropic.

*What stays.* The 60 paragraphs and the four arms. The system message, the
three prompts, temperature 0 and the reply schemas. The pairwise judgements
in both orders, the fact check, the counting and the bootstrap. The primary
outcome (B against C), the secondary comparisons of D, the decision rules,
the claims and amendment 7's readings. The call caps (5,200 for the
original phases, 9,160 in all) also stay.

**Editors.** Three instruction models from three families:

| Family | Repository | Revision | Licence |
| --- | --- | --- | --- |
| Qwen (Alibaba) | `Qwen/Qwen3.8-27B` | `37561816e66b5b9153b1b64c10968c18c1e6f4a0` | Apache-2.0 |
| Gemma (Google) | `google/gemma-4-31B-it` | `842da3794eaa0b77d5f08bae87a17459d91ff475` | Apache-2.0 |
| Mistral | `mistralai/Mistral-Small-4-119B-2603` | `a11f36bebf709121056b1dbcc943d1c6afbe494d` | Apache-2.0 |

**Judges.** Three more, from three other families:

| Family | Repository | Revision | Licence |
| --- | --- | --- | --- |
| OpenAI | `openai/gpt-oss-120b` | `b5c939de8f754692c1647ca79fbf85e8c1e70f8a` | Apache-2.0 |
| GLM (Zhipu AI) | `zai-org/GLM-4.7-Flash` | `7dd20894a642a0aa287e9827cb1a1f7f91386b67` | MIT |
| OLMo (Ai2) | `allenai/Olmo-3.1-32B-Instruct` | `ac0587e4a7744a551c059d8cd17ba220bc940dae` | Apache-2.0 |

No judge shares a family with an editor, as before. The repositories,
revisions, licences and gating were read from the Hugging Face Hub on
19 November 2026; none is gated. Each fits one H200 (141 GB). The weights
take 56 to 64 GB for all models but two: gpt-oss-120b, about 65 GB in
MXFP4, and Mistral Small 4, about 121 GB in FP8, which leaves the least
room. If Mistral Small 4 cannot be served on one H200 in the pilot below,
`mistralai/Ministral-3-14B-Instruct-2512` at revision
`29439f81c2be264d8d393273f99e7db9c0961120` (Apache-2.0) replaces it, and
the report says so. Any other model that fails in the pilot stops the plan
until a further amendment.

A pre-registration on branch `exp/open-family-raters` will re-rate the
precision rounds with four open families. It was not pushed when this
was written, so its families could not be read. The judges above are
chosen for it to reuse: three families, none of them an editor's here. If
that plan, once pushed and before any job here starts, names other
families, a dated amendment may replace judges with them, keeping the rule
that no judge shares a family with an editor.

**Serving.** vLLM 0.34.0, the image
`vllm/vllm-openai:v0.34.0@sha256:20fdb089454afbb324efa4110a2c025ff7b27cc1a086e07aa580b18df8ad1ce1`,
OpenAI-compatible chat completions on the job's own machine. Each request
keeps the system message, prompt, temperature 0 and strict JSON schema
that the client sent to OpenRouter, with at most 2,048 tokens in the
reply. Thinking is off where a model can turn it off: `reasoning_effort`
"none", and `enable_thinking` false for Qwen, Gemma and GLM. gpt-oss-120b
cannot turn it off and runs at `reasoning_effort` "low". OLMo 3.1 Instruct
has no thinking mode. The original plan expected up to 2,000 reasoning
tokens from most models, so these judges reason less before answering.
Batched GPU inference at temperature 0 is close to repeatable but not
exact, so a rerun may differ in a few replies.

**Order.** The job loads one model at a time, runs that model's calls, and
stops it before loading the next:

1. each editor in turn: its edits for arms B and C, then for arm D, all
   60 paragraphs;
2. each judge in turn: B against C;
3. each judge in turn: the fact checks of B and C, B against A, C against
   A, D against B, D's fact checks, D against C, D against A.

D's edits move forward into the first pass, because each editor is loaded
once. Each judge is loaded twice, so that B against C is complete for all
three judges before any other comparison starts. Within a pass, calls are
shuffled with the seeds above, and a missing reply is asked for once more
before the model stops.

**GPU-hour caps.** The dollar caps no longer apply. A job on a GPU is
billed for its time, not for tokens. The test may use at most **6 GPU hours ($30)** in all, as
Hugging Face bills them:

- a **pilot** on the first 5 paragraphs of `eval/edit-arms/paragraphs.jsonl`,
  with a job timeout of **1.5 hours ($7.50)**. It loads every model once
  and runs all its phases in one pass. It checks that each model loads and
  returns parseable replies, and how long the steps take. Its report gives
  counts, failures and timings only, not win rates, and its replies are not
  reused;
- the **full run**, from an empty reply cache, with a job timeout of
  **4 hours ($20)**.

That is 5.5 hours ($27.50). The job's own clock stops new calls 15 minutes
before its timeout, writes the report from what is done, and uploads it.
No other job runs for this test without a further amendment. If the full
run stops before B against C is complete for every judge, no claim is
decided, as before.

The estimate for the full run is 1.0 to 1.7 GPU hours ($5 to $8.50). Most
of it is starting models: pulling the image, downloading about 430 GB of
weights, loading and compiling nine times. The 8,640 planned calls are
short: 540 edits and 8,100 judgements and fact checks, under a million
generated tokens in all, about 15 to 30 minutes on one H200. The pilot is
estimated at 0.6 to 1.1 hours.

**Outputs.** The job uploads its outputs to the private dataset
`arclabs561/readcost-labels` under `edit-arms/<run id>/`, after each model
and at the end. They are every reply with the model and revision that gave
it, the phase status, a run log with timings per model, vLLM's log for each
model, and the report. The upload
stops if that dataset is not private. The paragraphs themselves are not
uploaded; the job fetches them from GitHub at their commits, as before.
The job checks that readcost's `src/` and `uv.lock` are those of `a57e19e`
by a SHA-256 over their files, since the job has the source without git
history.

*What this costs in validity.* The editors are open models of 27B to
119B parameters, weaker writers than the Claude, Gemini and Mistral Large
models planned, and none is from Anthropic, whose models many agents that
would read readcost's feedback use. A result about these editors may not
hold for stronger ones: feedback may help a weaker editor more, or
mislead it more. The judges are weaker too, and reason less or not at all
before they answer. Weaker judges make noisier and more position-biased
choices, so expect more ties and splits and wider intervals than the
0.05 to 0.09 half-width estimated above. They may also lean more toward
longer or more model-like text. B against C still compares two edits by
the same editor, so that lean should still mostly cancel there.

*What it gains.* No key to hold or approve. Six families, independent of
each other and of Anthropic. Weights pinned by revision, so anyone with a
GPU can rerun the same models with the same prompts. And decoding that
the job controls, with no provider routing between requests.

The GitHub Actions job `edit-arms` stays in `.github/workflows/eval.yml` as
a fallback for the OpenRouter models above. It now runs only when started
by hand, and only after the `openrouter` environment approves it. This plan
does not use it; using it would need a further amendment.

### 19 November 2026, before any model call: judges shared with the open-raters plan

The plan on branch `exp/open-family-raters` (pull request #110) was pushed
after the amendment above, and before any job here. It rates with Qwen
3.8 27B, Gemma 4 31B, GLM-4.7-Flash and Ministral 3 14B, with OLMo 3.1 32B
as its substitute, at the revisions above. As that amendment allows, the
judges here become three of its four families, at the same repositories
and revisions. So the same three families judge here and rate there, on
purpose, and a family's leanings can be compared across the two tests.
No judge may share a family with an editor, so the editors move to three
families that do not judge:

| Role | Family | Repository | Revision | Licence |
| --- | --- | --- | --- | --- |
| Editor | OpenAI | `openai/gpt-oss-120b` | `b5c939de8f754692c1647ca79fbf85e8c1e70f8a` | Apache-2.0 |
| Editor | Mistral | `mistralai/Mistral-Small-4-119B-2603` | `a11f36bebf709121056b1dbcc943d1c6afbe494d` | Apache-2.0 |
| Editor | OLMo (Ai2) | `allenai/Olmo-3.1-32B-Instruct` | `ac0587e4a7744a551c059d8cd17ba220bc940dae` | Apache-2.0 |
| Judge | Qwen (Alibaba) | `Qwen/Qwen3.8-27B` | `37561816e66b5b9153b1b64c10968c18c1e6f4a0` | Apache-2.0 |
| Judge | Gemma (Google) | `google/gemma-4-31B-it` | `842da3794eaa0b77d5f08bae87a17459d91ff475` | Apache-2.0 |
| Judge | GLM (Zhipu AI) | `zai-org/GLM-4.7-Flash` | `7dd20894a642a0aa287e9827cb1a1f7f91386b67` | MIT |

These tables replace the two above. The open-raters plan does not use
the editors' families as raters, except Mistral, whose smaller model it
rates with. Everything else in the amendment above stands: serving,
thinking settings, order, caps, outputs, and the fallback to
`mistralai/Ministral-3-14B-Instruct-2512` if Mistral Small 4 cannot be
served on one H200.

Two of the open-raters plan's reasons not to rate with a model bear on the
editors here. It rejects gpt-oss-120b because it answers only after a
reasoning channel. Agents often reason briefly before they edit, so here
gpt-oss-120b edits at `reasoning_effort` "low". It also
finds that Mistral Small 4 (121 GB in FP8) does not fit one H200 with a
cache, since its card serves it on two GPUs. That card serves 262,144
tokens of context; this run needs 8,192, and the model's attention stores
a small cache per token. Whether it fits is what the pilot finds out, and
the fallback above covers the case where it does not.

What this changes in validity: the editors are now gpt-oss-120b (August
2025), Mistral Small 4 and OLMo 3.1 32B. They are probably weaker writers
than Qwen and Gemma, and OLMo probably the weakest of the six; no
benchmark of editing prose was checked. The judges are now the three
newest models. That should make the judgements less noisy, and it narrows
further what the result can say about strong editors. The primary
comparison, B against C, still holds the editor fixed within each pair.

### 20 November 2026, after the primary result of run main-1 was seen: resuming main-1

This amendment is written after the report of run `main-1` was read,
primary outcome included. It changes one cap, so that the phases
planned above can finish, and nothing else.

*What main-1 found.* The job started at 22:21 UTC on 19 November from
`d613308`. B against C, over all three judges, was **0.542 [0.482,
0.601]**: 151 wins, 1 tie, 279 splits, 106 losses, 3 missing;
inconclusive. So neither of the first two claims holds, and the fact
checks cannot change that: the first claim needs "B better" before its
content bound is read. The report also gave B against A, C against A
and D's comparisons from Qwen and Gemma alone. Those were seen too.

*Why it stopped.* Not time and not money. It ran 2,306 seconds of its
4 hours, and the owner reports about $3.30 of its $20. It stopped at
the call cap of the original phases, 5,200, which counts every reply in
the cache, D's included (amendment 7). The amendment of 19 November
kept that cap and moved D's phases into the same pass as the original
ones. In the third pass, each judge runs its original phases and then
its D phases before the next judge starts. So when GLM-4.7-Flash, the
last judge, began its fact checks, the cache already held 6,274
replies. About 2,690 of them came from D's edits and from Qwen's and
Gemma's D phases. The first call over the cap stopped the phase, and
GLM made no call in that pass. Without D's replies the original phases
would have needed about 4,660 calls, under the cap. Calls asked again
played almost no part: there were 6 in the whole run, 3 by OLMo and 3
by Qwen, and GLM-4.7-Flash answered all 358 of its calls the first
time. The stop followed the rules as written; the mistake was in the
plan, which did not check how the old cap and the new order interact.

*What changes, for one resumed run only.*

- The call cap of the original phases rises from 5,200 to **7,500**,
  counted as before over every reply in the cache. GLM's three original
  phases need 1,074 calls (358 fact checks, 358 for B against A, 358
  for C against A), so the cache reaches 7,348. The other 152 are room
  for calls asked again.
- The cap for the whole run stays at 9,160. GLM's D phases need 1,253
  more calls, 8,601 in all.
- The resumed job has a timeout of **1.5 hours** ($7.50 at $5 an hour).
  With the pilot (at most 1.5 hours) and main-1 (under 0.7 hours
  billed), the test stays under its 6 GPU hours.

The amendment of 19 November allows no other job without a further
amendment. This is that amendment, for one job, with the run id
`main-1b`.

*How it resumes.* The job starts with main-1's replies as its cache
(`edit-arms/main-1/replies.jsonl` in the dataset). Where main-1 finished
a phase for a model, the job asks that model nothing in that phase. A
model left with nothing to ask is not loaded. So no edit and no B
against C judgement is asked again. That includes three OLMo edits (B,
C and D of one paragraph) and two of Qwen's later calls, which failed
twice in main-1. They stay missing: the rule above, to ask once more at
the end of the phase, has already been applied to them. Only
GLM-4.7-Flash loads, for its fact checks, B against A, C against A, D
against B, D's fact checks, D against C and D against A. Its revision,
prompts, settings, phase order and seeds are those of main-1. The
outputs go to `edit-arms/main-1b/` and hold every reply of both runs.

*What stays.* Everything else. The primary outcome stays as main-1
measured it. The resumed run asks no B against C call, and its report
computes B against C from the same replies with the same code, so it
should give the same numbers. If it does not, main-1's numbers stand and
the report says why they differ. The secondary results this run
completes are reported with a note that they were completed after the
primary result was seen. That covers:

- GLM's judgements and fact checks;
- the content measures, which need two of three judges;
- B against A and C against A over all three judges;
- all of arm D's comparisons and readings.
