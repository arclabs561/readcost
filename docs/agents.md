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

`-o agent` names each finding's line and rule, asks whether the sentence is
hard to follow there, and says what to do if it is. Where the evaluation
measured it, it adds how the raters judged that rule's findings ("Raters
said an editor would fix 0 of 100 such findings, and called 36 more
optional."). The output is worded as questions on purpose: shown readcost's
message, model raters agreed with it far more often than when they saw the
same sentence without it (docs/evaluation.md, "a wider panel"), and an agent
told to rewrite will rewrite. Its first line asks the model to change a
sentence only if it reads badly, and to leave the rest.

In `-o json` each finding has `start` and `end`, character offsets into the
file with the end exclusive, so a tool can replace exactly the flagged
words: `text[start:end]`. `line`, `column`, `end_line` and `end_column` say
the same span in 1-based lines and columns (the end column is exclusive),
and `sentence_start` and `sentence_end` are the offsets of the sentence.
The offsets are `null` for text read from JSON; the columns are then found
by searching for the excerpt, and are `null` when it is not found.
[labels.md](labels.md) says how characters are counted. `precision` is
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

`--fail-on worse` is strict: a rewrite that adds any words usually takes
longer in total, so the check rejects it. In the measured loops
(docs/evaluation.md, "Agents editing in a loop") it would have rejected at
least half of the final rewrites. Use it where a rewrite should not grow.
Elsewhere, read the comparison and judge. Predicted reading time is a rough
estimate, not a target: do not rewrite to lower it.

## When to stop

Most findings go after one rewrite. Stop when the text stops changing or the
same findings come back after a rewrite: what remains is a finding the
model has judged wrong, or one it cannot fix (docs/evaluation.md, "Agents
editing in a loop"). Two rounds are enough.

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
finding holds and the rewrite reads naturally; keep every fact. Then run
`readcost compare HEAD:<file> <file>` and reread both versions: if the
rewrite is much longer or says less, keep the original. Stop after two
rounds, or as soon as the same findings come back. Do not rewrite to lower
the predicted reading time.
Leave code spans, identifiers and quoted text as they are.
```

## Limits

The precision shares come from findings labelled on essays and documentation
by well-regarded writers, not from your repository. Predicted reading time is
fitted to native readers of newspaper paragraphs; see
[evaluation](evaluation.md) for what it does and does not predict.
