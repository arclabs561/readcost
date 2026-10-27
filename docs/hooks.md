# Hooks

readcost runs inside four kinds of harness: Claude Code, piku, git, and CI.
A fifth, harness-neutral protocol covers anything else. Each adapter reads the
harness's own JSON from stdin and answers in the harness's own format. This
page describes what each one sees, what it sends back, and the rules that they
all follow.

The Claude Code contract was read from code.claude.com/docs/en/hooks on
2026-10-26. The piku contract was read from `crates/piku-runtime/src/hooks.rs`
on the same day.

## Shared rules

**Advisory by default.** With no configuration, these hooks are active and
only advise: Claude Code's PostToolUse adds text next to the tool result,
piku's PreToolUse allows the write and adds context, piku's PostToolUse
appends to a log, and git pre-commit and commit-msg print findings without
failing. The Stop and MessageDisplay hooks and Claude Code's PreToolUse do
nothing until configured. Nothing is denied or blocked until
`hooks.mode = "block"`, and then only on a "block" verdict.
`hooks.mode = "off"` turns every hook off, including Stop, MessageDisplay and
the piku log.

**Verdicts.** Each finding has a weight: info 0.5, warn 1, error 2. The cost
index is the weighted count per 1,000 words.

| Verdict | Rule (defaults) | BurntSushi READMEs (10 with 150+ words) | arclabs561 READMEs (58 with 150+ words; measured with 0.1.0) |
| --- | --- | --- | --- |
| pass | cost index below 15 | 10 | 18 |
| advise | cost index 15 or more, or any error | 0 | 37 |
| block | cost index 30 or more, and at least 3 weighted findings | 0 | 3 |

Those BurntSushi READMEs have a median cost index of 7.3 and a maximum of 12.5,
so the advise line sits just above the most demanding prose in the reference
set. Change the lines with `advise_cost_index`, `block_cost_index` and
`block_min_points`.

**Only the lines that changed.** On an edit, readcost judges sentences that
overlap the edited lines, so a hook does not repeat complaints about text
nobody touched. A Write over an existing file counts as an edit of the lines
it changes. Set `hooks.edited_lines_only = false` to judge the whole file.

**Baseline.** When the config sets `baseline` (a file from `readcost
baseline`), every hook drops the findings that file records before it
computes a verdict, so old prose neither blocks nor adds feedback. See
"Adopting readcost in an existing repo" in the README.

**Fail open.** Bad input, a missing spaCy model, or any exception ends the
hook with exit 0 and no output. The error goes to stderr and, if
`READCOST_HOOK_LOG` names a file, to that file. A broken checker should never
stop an agent.

**Cost.** For a file the configuration does not cover, the hook exits in about
0.1 s without loading spaCy. For a covered file it takes about 1.2 s, almost
all of it loading the spaCy model, plus about 0.1 s per 1,000 words. WordNet
lookups are precomputed into the package, so they cost nothing at run time.

**Bounded loops.** The Stop hook asks Claude to revise at most once per turn: it
does nothing when `stop_hook_active` is true. Claude Code also overrides a Stop
hook after eight consecutive continuations.

**Short feedback.** A model gets at most 8 findings and 2,500 characters, worst
first, each with its fix (`hooks.max_items`, `hooks.max_chars`). Claude Code
caps `additionalContext` at 10,000 characters.

**Local only.** No hook uses the network. The MessageDisplay hook keeps the
message that it is assembling in `$CLAUDE_PLUGIN_DATA/readcost-display/` (or
under `$XDG_STATE_HOME` or `~/.local/state`, owner-only) and deletes it after
the final batch. State left by an interrupted message is deleted after a day. The piku
PostToolUse hook appends to `.piku/readcost.jsonl` in the project.

## Event map

| Harness | Event | readcost reads | readcost returns | Active when |
| --- | --- | --- | --- | --- |
| Claude Code | PostToolUse on Write, Edit | the file on disk; the edited lines | `hookSpecificOutput.additionalContext`; in block mode, `decision: "block"` with `reason` | `hooks.mode` is advise (default) or block |
| Claude Code | PreToolUse on Write, Edit | the lines `content` changes, or `new_string` | `permissionDecision: "deny"` with the findings as the reason | `hooks.mode = "block"` |
| Claude Code | Stop | `last_assistant_message` | report: `systemMessage` to the user; revise: `decision: "block"` once | `hooks.stop` is report or revise, and `hooks.mode` is not off |
| Claude Code | MessageDisplay | each `delta`, joined in `index` order per `message_id` | `displayContent`: the final delta plus a one-line note | `hooks.display = "note"`, `hooks.mode` not off, and the hook registered by hand (see Setup) |
| piku | PreToolUse on write_file, edit_file | the lines `content` changes, or `new_string` | `permissionDecision: "allow"` with `additionalContext`; in block mode, `"deny"` | `hooks.mode` is advise or block |
| piku | PostToolUse on write_file, edit_file | the file on disk | a line in `.piku/readcost.jsonl` (piku ignores stdout) | `hooks.mode` is advise or block |
| git | pre-commit | staged content of changed lines; with file arguments, whole files that have nothing staged | report on stderr; exit 1 on block in block mode | `hooks.mode` is advise or block |
| git | commit-msg | the message file | the same | `hooks.mode` is advise or block |
| GitHub Actions | `action.yml` | the paths you give | annotations; exit 1 at `fail-on` | always |
| any | `readcost hook generic` | `{"text"}` or `{"path"}` | verdict, counts, findings, feedback | always |
| Python | `readcost.hooks.generic.review()` | a string or path | the same, as a dict | always |

## Which mode to use

- **An agent writes docs for you.** Use the default: PostToolUse in advise
  mode. Claude reads the findings next to the tool result and usually fixes
  the sentences in its next edit.
- **A repository with a style bar.** Add `hooks.mode = "block"`. PreToolUse
  then denies writes whose new text would be blocked, and Claude retries with
  the reason in hand. Expect some retries; raise `block_cost_index` if they
  are too frequent.
- **Long answers in chat.** `hooks.stop = "report"` shows you a warning line
  and lets the turn end. `"revise"` asks Claude once to restate the answer,
  which costs a second message.
- **A quiet signal for yourself.** `hooks.display = "note"` adds a line under
  the answer on your screen. Claude never sees it and the transcript keeps the
  original text.

## Setup

### Claude Code

As a plugin: install `integrations/claude-code-plugin/`. In settings: merge
`integrations/claude-code/settings.json` into `.claude/settings.json`
(project) or `~/.claude/settings.json` (user). Both register PostToolUse,
PreToolUse and Stop. PostToolUse advises by default; the other two do nothing
until `readcost.toml` turns them on.

Neither registers MessageDisplay, because Claude Code would start it for
every streamed batch of every answer. To use `hooks.display = "note"`, add it
to your settings:

```json
"MessageDisplay": [
  { "hooks": [ { "type": "command", "command": "readcost hook claude-code message-display", "timeout": 10 } ] }
]
```

Either way `readcost` must be on the PATH that Claude Code runs hooks with.
Matchers filter by tool name only; readcost filters paths itself using
`hooks.paths` and `hooks.exclude`.

### piku

Copy `integrations/piku/hooks.json` to `.piku/hooks.json` (project; piku asks
you to trust it) or to `piku/hooks.json` in your config directory (global).
piku waits 10 s for a hook by default; the example allows 15 s for the first
model load.

### git

With the pre-commit framework, add this repository with hook ids `readcost` and
`readcost-commit-msg`; `.pre-commit-hooks.yaml` installs the spaCy model as an
additional dependency. `pre-commit install` installs only the pre-commit
stage, so install both:

```sh
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

or set `default_install_hook_types: [pre-commit, commit-msg]` in
`.pre-commit-config.yaml`. In a commit, the `readcost` hook judges the changed
lines of staged files. `pre-commit run --all-files` and pre-commit.ci stage
nothing, so there it judges each file whole. Without the framework, copy
`integrations/git/pre-commit` and `integrations/git/commit-msg` into
`.git/hooks/`.

### CI

```yaml
- uses: actions/checkout@v4
- uses: <owner>/readcost@v0.1.0
  with:
    paths: README.md docs
    fail-on: block
```

For code scanning, run `readcost check . -o sarif --fail-on never > readcost.sarif`
and upload the file with `github/codeql-action/upload-sarif`.

### Anything else

Send one JSON object on stdin to `readcost hook generic`:

```json
{"text": "...", "format": "markdown", "lines": "10-24"}
```

The reply is one JSON object. Exit status is 0 for every verdict, so the
caller decides what a verdict means. A malformed request exits 2 and an
environment error (a missing spaCy model, an unreadable file or config) exits
3; both reply `{"error": "..."}`.

```json
{"verdict": "advise", "cost_index": 21.4, "words": 233, "points": 5.0,
 "counts": {"stacked-nouns": 3, "inline-list": 2},
 "feedback": "readcost: 5 hard-to-read constructions in 233 words. ...",
 "findings": [{"feature": "stacked-nouns", "severity": "warn", "line": 3, "...": "..."}]}
```

In Python, `readcost.hooks.generic.review(text)` returns the same dict without
a subprocess. `examples/revise_loop.py` shows a draft, check, revise-once loop.

## Changes piku would need to review final answers

piku can advise on text before it is written, but not on a final answer. Two
gaps cause this:

1. **The Stop input has no assistant text.** `run_stop` (hooks.rs, around line
   445) sends `iterations`, `stop_reason`, token counts and `duration_ms`. Add
   `last_assistant_message`, the final assistant text of the turn, as Claude
   Code does.
2. **Stop and PostToolUse ignore hook output.** Both are fire-and-forget; only
   errors are logged. Two additions would match Claude Code:
   - Stop honors `{"decision": "block", "reason": "..."}` by continuing the
     turn and passing the reason to the model. It sends
     `stop_hook_active: true` in the next Stop input and caps consecutive
     continuations.
   - PostToolUse honors `hookSpecificOutput.additionalContext` by appending it
     to the tool result that the model sees.

With the second change, readcost could judge the file after the edit, with its
surrounding text, rather than the `new_string` alone. The readcost side needs
no change beyond pointing the piku adapter at the new fields.

## Limits

- English only. The default model, `en_core_web_sm`, misparses some sentences;
  a sentence parsed with no verb is skipped. `model = "en_core_web_trf"` parses
  better and is several times slower.
- inanimate-subject and denominal-verb are heuristics based on word lists. Treat them as
  prompts to reread the sentence.
- The reference profile is one writer's READMEs. A cost index from chat answers
  or papers is not comparable to one from READMEs; build a profile from text you
  consider readable with `readcost profile build`.
- After a Write, Claude Code's PostToolUse finds the changed lines by diffing
  against `tool_response.originalFile`. That field appears in session
  transcripts but not in the hooks documentation; without it, readcost judges
  the whole file.
- On an Edit, readcost locates the edited lines by searching for `new_string`.
  If that text also appears earlier in the file, it checks the earlier copy.
