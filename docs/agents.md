# readcost for coding agents

A coding agent that edits prose (READMEs, docs, commit messages, its own
answers) can run readcost the way it runs a test: check, rewrite, check that
the rewrite did not make things worse. [docs/hooks.md](hooks.md) covers the
automatic route, hooks that feed findings back to the model; this page
covers the agent calling readcost itself.

## Check

```sh
readcost check README.md -o agent          # short, worst sentences first, with the fix
readcost check README.md -o json           # every finding, with exact location
```

`-o agent` names each finding's line and rule, says what to do, and, where
the evaluation measured it, how often raters accepted that rule's findings
("raters accepted 3 of 19 such findings"). A low share means the finding is
often wrong: judge it before rewriting.

In `-o json` each finding has `line`, `column`, `end_line` and `end_column`
(1-based; the end column is exclusive), so a tool can select exactly the
words in `excerpt`; they are `null` when the excerpt is not found in the
source (text read from JSON, for example). `precision` is
`{"accepted": N, "labelled": M}` from the same evaluation, or `null` when too
few findings were labelled. `suggestion` is the fix in words.

## Rewrite, then compare

A rewrite can remove findings and still read slower, usually by getting much
longer. `readcost compare` checks both:

```sh
readcost compare HEAD:README.md README.md --fail-on worse
```

The old text can be a file, `REV:PATH` from git, or `-` for stdin. The exit
status is 1 when the rewrite is predicted to take longer to read in total or
has more weighted findings (`--fail-on slower` checks time only), 2 when an
input cannot be read, and 0 otherwise.

## Match a house style

`readcost style docs/ --against go-docs -o json` compares a draft's rule
rates, words per sentence and predicted ms per word with a reference
profile (`readcost style --list`). Each row has `measure`, `rule` (null for
the two rows that are not rules), `yours`, `reference`, `count` and
`ratio`; a rule far above the reference (ratio 2 or more) is where a
rewrite toward that style should start.

## AGENTS.md snippet

Paste into a repository's AGENTS.md or CLAUDE.md:

```markdown
## Prose

After editing a README, a file under docs/ or a commit message, run
`readcost check <file> -o agent`. Rewrite a flagged sentence only where the
finding holds; keep every fact. Then run
`readcost compare HEAD:<file> <file> --fail-on worse`; if it fails, the
rewrite reads slower than the original, so shorten it or keep the original.
Leave code spans, identifiers and quoted text as they are.
```

## Limits

The precision shares come from findings labelled on essays and documentation
by well-regarded writers, not from your repository. Predicted reading time is
fitted to native readers of newspaper paragraphs; see
[evaluation](evaluation.md) for what it does and does not predict.
