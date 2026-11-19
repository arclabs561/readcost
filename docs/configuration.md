# Configuration and output

## Commands

```sh
readcost check README.md docs/
readcost check ~/src                          # a whole tree: git-aware, skips node_modules and the like, parallel
readcost check --lines 40-80 README.md      # only sentences touching these lines; 40- runs to the end
some-model-cli "explain X" | readcost check -        # model output on stdin
readcost check --format transcript --last session.jsonl
readcost check --format jsonl --field response --per-record evals.jsonl
readcost check src/lib.rs                     # doc comments; --format source
readcost explain stacked-nouns
readcost compare HEAD:README.md README.md     # see reading-time.md
readcost style README.md --against go-docs    # see style.md
readcost baseline README.md docs              # see below
```

## Configuration

Put a `readcost.toml` at the repository root, or a `[tool.readcost]` table in
`pyproject.toml`. `readcost.toml.example` lists every key with its default. The
useful ones:

- `allow`: phrases never flagged, such as product names or terms of art.
- `[readcost.rules]`: a level per rule, as in ty. `"error"`, `"warn"` or
  `"info"` turns a rule on at that severity (opt-in rules too); `"ignore"`
  turns it off; `all` sets every rule. An unlisted rule keeps its default.
- `[[readcost.overrides]]`: rule levels for files matching `include` globs
  and not `exclude` globs, applied in order after `[readcost.rules]`.
- `[readcost.src]`: `include` and `exclude` globs choose the files that
  `readcost check DIR`, the hooks and the language server read;
  `extend_exclude` adds to the default excludes; `respect_ignore_files`
  (default on) skips what `.gitignore` excludes.
- `advise_severity`: the verdict is at least `advise` when any finding reaches
  this severity; `off` turns that rule off.
- `profile`: a relative path is read from the config file's directory.
- `hooks.mode`: `off`, `advise` or `block`.
- `hooks.repeat`: `"once"` (the default) makes the Claude Code and piku hooks
  report a finding once per session and file, and block or deny on it once;
  `"always"` reports every finding after every edit. See
  [hooks](hooks.md#shared-rules).
- `feedback_link`: `false` drops the line that text and agent output end
  with, which points to the false-positive form.
- `language_check`: `false` checks text that looks like another language
  instead of skipping it with a note.
- `model`: the spaCy model; `"en_core_web_trf"` parses better at 30 or more
  times the cost.
- `long_dependency_gap`: `"words"` (the default) judges a long-dependency
  gap by its length. `"content"` adds what fills the gap to the message and
  reports a gap of only prepositional phrases at info. In a controlled study,
  readers spent far less time on such a gap than on a relative clause of the
  same length (Nusbaumer et al. 2026). The setting has not been checked
  against labelled findings yet. A level set under `[readcost.rules]` still
  wins.
- `verify_model` (opt-in): a second parser checks stacked-nouns,
  reduced-object-relative and long-dependency findings, and a finding stays
  only when the second parser finds the same construction. Install it with `pip install 'readcost[verify]'`
  and `readcost setup --verifier` (about 400 MB with onnxruntime), then set
  `verify_model = "biaffine"`, or a directory with the model. Against
  hand-corrected parses of text that the parser was not trained on, it raised
  long-dependency precision from 68% to 99% and kept nearly all of the
  recall; noun stacks gained 4 points. It makes a check 1.3 to 1.5 times
  slower. See [evaluation](evaluation.md#a-second-parser-as-a-check).

```toml
[readcost.rules]
stacked-nouns = "error"
hyphen-compound = "ignore"
nominalization = "info"

[[readcost.overrides]]
include = ["CHANGELOG.md", "docs/adr/*"]
rules = { inline-list = "ignore" }

[readcost.src]
extend_exclude = ["docs/generated/*"]
```

The same choices are flags: `--error`, `--warn`, `--info` and `--ignore` take
a rule name (repeat them, or `all`), `--exclude GLOB` adds an exclude,
`--force-exclude` applies the excludes to files named on the command line,
`--no-respect-ignore-files` reads ignored files too, and `--exit-zero` never
fails on findings. Flags win over the config file. The older `enable`,
`disable`, `hooks.paths` and `hooks.exclude` keys still work and print a
warning naming the newer key; they will be removed at version 1.0.

readcost warns about unknown keys and stops with exit code 2 on a value of the
wrong type or outside its choices, naming the file and the key.

## Skipping text

To skip text, put `<!-- readcost: ignore -->` before a paragraph, or wrap a
section in `<!-- readcost: off -->` and `<!-- readcost: on -->`. Name rules to
turn off only those: `<!-- readcost: ignore stacked-nouns -->` keeps every
other rule on for the next block, and `<!-- readcost: off inline-list -->`
lasts until `<!-- readcost: on inline-list -->` or a bare `readcost: on`. A
misspelled rule name is reported in the file's notes.

## Adopting readcost in an existing repo

Old docs can fail the check before anyone edits them. Record their findings
once, commit the file, and point the config at it:

```sh
readcost baseline README.md docs      # writes .readcost-baseline.json
echo 'baseline = ".readcost-baseline.json"' >> readcost.toml
```

From then on `readcost check` and the hooks report only findings that are not
in the baseline, and the verdict and exit status count only those. The text
summary says how many findings the baseline hid, and the JSON output has a
`baselined` count per file. `readcost check --baseline FILE` does the same
without the config key.

A finding is matched by its file, its feature and a hash of its sentence, not
by line number, so edits elsewhere in a file do not make old findings new.
A sentence that is reworded but still flagged counts as new, and so does a
second copy of a baselined sentence. The file holds hashes only, sorted one
entry per line, with paths relative to its own directory, so keep it at the
repository root. Run `readcost baseline` again after a cleanup to shrink it.

## Output

The default output, in the style of the Rust compiler, names the rule, quotes
the line with carets under the words and a label saying what is wrong, and
gives the fix. The first finding of each rule also says why it costs the reader
and shows an example rewrite. Lines stay within 80 columns.
Colour is on in a terminal unless `NO_COLOR` is set (`--color` overrides);
the README's terminal image is generated by `scripts/terminal_svg.py`.

- `-o concise` prints one `path:line:col` line per finding, for editors and
  grep.
- `-o json`, `-o sarif` and `-o github` are for tools; JSON and SARIF give
  each finding's exact character offsets in the file.
- `-o agent` is short feedback written for a model
  ([agents](agents.md)).
- `-o pr-comment` is the Markdown summary that the GitHub Action posts on a
  pull request ([hooks](hooks.md#ci)).

The exit status is 1 when a file reaches the `--fail-on` verdict (default
`block`), 2 on an error, and 0 otherwise.

From Python:

```python
from readcost import check_text

result = check_text(answer, fmt="markdown")
if result.verdict != "pass":
    for f in result.findings:
        print(f.line, f.feature, f.message, f.suggestion)
```
