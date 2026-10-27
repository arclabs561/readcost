# readcost

readcost finds the sentences in your docs, or in a model's answer, whose
construction slows readers down: three or more nouns in a row, a subject far
from its verb, a thing doing a person's action, and a few more. For each one it
quotes the line, marks the words, and says how to rewrite it.

For example, this sentence from a README:

```text
For store restart measurement, the example prints first snapshot-query cost
with persisted WAND sidecars present versus after deleting those sidecars and
forcing source-segment rebuilds.
```

```text
warn[stacked-nouns]: three or more nouns in a row
 --> notes.md:1:5
  |
1 | For store restart measurement, the example prints first snapshot-query cost
  |     ^^^^^^^^^^^^^^^^^^^^^^^^^ 3 nouns stacked
  |
  = why: Readers must work out how the nouns group before they can read on, and
         the grouping is often ambiguous (Squad Helps Dog Bite Victim).
  = help: Keep at most two nouns together. Unpack the rest with a preposition or
          a relative clause.
  = example: 'forcing source segment rebuilds' -> 'forcing each segment to be
             rebuilt from its source'

warn[hyphen-compound]: ad hoc hyphenated noun compound
 --> notes.md:3:9
  |
3 | forcing source-segment rebuilds.
  |         ^^^^^^^^^^^^^^^^^^^^^^^ coined compound modifier
  |
  = why: Coined compounds such as storage-shrink or region-index are rare word
         pairs, which the paper links to slower reading.
  = help: Write the relationship out.
  = example: 'the storage-shrink use case' -> 'the main use: storing ID sets in
             less space'

notes.md: advise
  2 findings in 1 sentence (26 words), cost index 76.9 per 1,000 words
  predicted reading time 7 s, 301 ms per word

More on a rule: readcost explain stacked-nouns
Wrong finding? https://github.com/arclabs561/readcost/issues/new/choose
```

The rewrite that README adopted keeps every fact and passes:

```text
To measure a store restart, the example reopens a checkpointed store and
prints the duration of its first snapshot query. It does this twice: once
with the persisted WAND sidecars present, and once after deleting those
sidecars, which forces each segment to be rebuilt from its source vectors.
```

```sh
uvx readcost check README.md
```

The constructions come from "Why is AI-generated language so hard to
understand?" ([arXiv 2610.29162](https://arxiv.org/abs/2610.29162)), which finds
that recent language models use them more than people do; earlier reading
studies tie each of them to slower reading.

## Scope

readcost is for English technical prose: READMEs, documentation, commit
messages, doc comments, and text a model writes before you or your users read
it. It reports:

- sentences built in a way that costs readers time, with the words marked and
  a suggested rewrite;
- a verdict per file (pass, advise, block) for CI and hooks;
- a predicted reading time per file, from a model fitted to eye-tracking data.

It does not check grammar, spelling or terminology, enforce a style guide,
judge whether text is correct, complete or up to date (which developers rate as
the worst documentation failures), or tell who wrote a text.

## How it differs

| Tool | Checks | How |
| --- | --- | --- |
| readcost | Sentence constructions tied to slower reading; reading time | A dependency parse of each sentence; a model fitted to eye-tracking data |
| Vale | Your style guide: terms, phrases, capitalization | Rules you write: patterns, word lists, part-of-speech sequences |
| proselint | Usage advice gathered from authors and editors | Built-in checks |
| write-good | Passive voice, weasel words, wordy phrases | Word patterns |
| LanguageTool | Grammar, spelling, punctuation | Grammar rules and models |
| Readability formulas (Flesch-Kincaid) | A grade for a whole text | Word and sentence length |

Vale's part-of-speech rules can match a run of nouns, but Vale, proselint and
write-good do not parse which word depends on which, so they cannot measure the
distance from a subject to its verb or find an object relative without "that". readcost works next to
Vale rather than instead of it; [docs/vale.md](https://github.com/arclabs561/readcost/blob/main/docs/vale.md)
has a CI recipe that runs both. A readability formula tracks how hard a whole
text is better than readcost's cost index does (see
[docs/evaluation.md](https://github.com/arclabs561/readcost/blob/main/docs/evaluation.md));
readcost's job is to say which sentence to change.

Status: experimental; before 1.0, output and configuration can change between
minor versions.
[docs/research.md](https://github.com/arclabs561/readcost/blob/main/docs/research.md)
has the evidence behind each choice and the roadmap.

## Install

```sh
uvx readcost check README.md    # run without installing
pip install readcost            # or install it
```

Python 3.11 or later. The dependencies are spaCy and markdown-it-py. On first
use readcost downloads spaCy's English model (about 13 MB, checksum verified)
into `~/.cache/readcost`; no pip is needed, so it also works under `uvx`.
`readcost setup` does the download ahead of time. Set `READCOST_NO_DOWNLOAD=1`
to forbid it, for example on an offline machine with the model installed as a
package.

## Use

```sh
readcost check README.md docs/
readcost check --lines 40-80 README.md      # only sentences touching these lines; 40- runs to the end
some-model-cli "explain X" | readcost check -        # model output on stdin
readcost check --format transcript --last session.jsonl
readcost check --format jsonl --field response --per-record evals.jsonl
readcost check src/lib.rs                     # doc comments; --format source
readcost explain stacked-nouns
```

![readcost check output in a terminal, with the rule names and carets in colour](https://raw.githubusercontent.com/arclabs561/readcost/main/docs/images/check.svg)

The default output, in the style of the Rust compiler, names the rule, quotes
the line with carets under the words and a label saying what is wrong, and
gives the fix. The first finding of each rule also says why it costs the reader
and shows an example rewrite. Lines stay within 80 columns.
Colour is on in a terminal unless `NO_COLOR` is set (`--color` overrides);
the image above is generated by `scripts/terminal_svg.py`.
`-o concise` prints one `path:line:col` line per finding, for editors and grep.
`-o json`, `-o sarif` and `-o github` are for tools, `-o agent` is short
feedback written for a model, and `-o pr-comment` is the Markdown summary that
the GitHub Action posts on a pull request. The exit status is
1 when a file reaches the `--fail-on` verdict (default `block`), 2 on an error,
and 0 otherwise.

From Python:

```python
from readcost import check_text

result = check_text(answer, fmt="markdown")
if result.verdict != "pass":
    for f in result.findings:
        print(f.line, f.feature, f.message, f.suggestion)
```

## What it flags

Each example below is a real sentence from a public README, except where the
last column says otherwise; each rewrite keeps every fact and passes.

| Feature | Example | Rewrite | Source |
| --- | --- | --- | --- |
| stacked-nouns | For store restart measurement, the example prints first snapshot-query cost with persisted WAND sidecars present versus after deleting those sidecars and forcing source-segment rebuilds. | To measure a store restart, the example prints the cost of the first snapshot query twice: with the persisted WAND sidecars present, and after deleting them, which forces each segment to be rebuilt from its source. | a README this rewrite was adopted in |
| long-dependency | Comparisons keep the declared artifact-digest relation and packet-shape evidence as separate claims. | Comparisons keep two claims separate: the relation that the artifact digests declare, and the evidence from packet shapes. | [linktop](https://github.com/arclabs561/linktop) |
| inanimate-subject | It does not decide how text should be split; it records the chosen span. | The caller decides how to split the text; slabs records the span it chose. | [slabs](https://github.com/arclabs561/slabs) |
| reduced-object-relative | `compressed_postings` compresses an inverted-index posting list with cnk, the storage-shrink use case these ID-set codecs exist for. | `compressed_postings` uses cnk to compress the posting list of an inverted index. Storing ID sets in less space is what these codecs are for. | [cnk](https://github.com/arclabs561/cnk) |
| hyphen-compound | The missing-pattern check in `gitignore_audit` is a pattern-presence heuristic. | The missing-pattern check in `gitignore_audit` only looks for whether a pattern is present. | [devguard](https://github.com/arclabs561/devguard) |
| inline-list | `durability` provides filesystem and in-memory directories, atomic writes, WALs, record logs, checkpoint files, CRC validation, and sync helpers. | a bulleted list | [durability](https://github.com/arclabs561/durability) |
| participial-clause (opt-in) | The page updates automatically when the file changes on disk, highlighting what changed. | The page updates automatically when the file changes on disk and highlights what changed. | [mdpreview](https://github.com/arclabs561/mdpreview) |
| denominal-verb (opt-in) | The script will bucket the requests by hour. | The script will group the requests by hour. | constructed: every hit in the sample was wrong |
| nominalization (opt-in) | The tool performs validation of the input. | The tool validates the input. | constructed: no hit in the sample |
| repeated-frame (opt-in) | This change reduces the latency of the cache. This change improves the speed of the parser. This change lowers the cost of the build. | This change makes the cache faster, the parser quicker and the build cheaper. | constructed: no hit in the sample |
| center-embedding (opt-in) | The job that the script that the team maintains starts fails when the disk is full. | The team maintains a script that starts the job, and the job fails when the disk is full. | constructed: the sample has no double embedding |
| undefined-acronym (opt-in) | Each shard writes its changes to the WAL before it updates the index. | Each shard writes its changes to the write-ahead log (WAL) before it updates the index. | constructed |

The first five come from the paper; denominal-verb is opt-in because on
well-edited prose nearly all its hits were settled verbs. The next two are
rules derived from where those constructions show up in technical writing. A
hyphenated word counts as one noun, so "storage-shrink job" is a hyphen
compound, not three stacked nouns. Participial-clause, nominalization and
repeated-frame are constructions that language models use more often than
people (Reinhart et al. 2025; Shaib et al. 2024). Center-embedding flags a
clause nested two deep inside clauses that continue after it, which readers
fail to follow (Gibson 2000); undefined-acronym flags an acronym used before
it is spelled out, which readers report as harder to read (Hales, Williams and
Rector 2017), skipping common ones such as API and JSON. Turn any opt-in rule on
with a level, such as `--info nominalization` or `nominalization = "info"`
under `[readcost.rules]`. `long-sentence` is also
available but off by default. `readcost explain` prints why each one costs the
reader and how to fix it. When a long-dependency or inline-list
sentence gives a reason (because, since, so that, otherwise), the suggestion
says to keep that reason when splitting the sentence.

Technical writing repeats compressed terms on purpose, so a stacked or
hyphenated compound is reported once per document, at its first use. An
identifier as a subject (`` `parse()` returns ``) is not reported as an
inanimate subject. Code spans, URLs and file paths count as single words.

<details>
<summary>More real output, from READMEs in the author's public repositories</summary>

Checked with the default settings; `scripts/readme_gallery.py` regenerates
this from pinned commits.

```text
warn[stacked-nouns]: three or more nouns in a row
  --> cnk/README.md:61:48
   |
61 | ...presses an inverted-index posting list with cnk, the storage-shrink u...
   |                        ^^^^^^^^^^^^^^^^^^ 3 nouns stacked
   |
   = why: Readers must work out how the nouns group before they can read on, and
          the grouping is often ambiguous (Squad Helps Dog Bite Victim).
   = help: Keep at most two nouns together. Unpack the rest with a preposition
           or a relative clause.
   = example: 'forcing source segment rebuilds' -> 'forcing each segment to be
              rebuilt from its source'

warn[hyphen-compound]: ad hoc hyphenated noun compound
  --> cnk/README.md:61:81
   |
61 | ... list with cnk, the storage-shrink use case these ID-set codecs exist...
   |                        ^^^^^^^^^^^^^^^^^^^^^^^ coined compound modifier
   |
   = why: Coined compounds such as storage-shrink or region-index are rare word
          pairs, which the paper links to slower reading.
   = help: Write the relationship out.
   = example: 'the storage-shrink use case' -> 'the main use: storing ID sets in
              less space'

info[reduced-object-relative]: object relative clause without 'that'
  --> cnk/README.md:61:100
   |
61 | ... with cnk, the storage-shrink use case these ID-set codecs exist for.
   |                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
   |                                      object relative without 'that'
   |
   = why: Object relatives (the house the contractors built) cost more to read
          than subject relatives; dropping the optional 'that' removes the cue
          that one has started.
   = help: Keep the 'that', or turn it into a subject relative or a separate
           sentence.
   = example: 'the format the reader expects' -> 'the format that the reader
              expects'

info[inanimate-subject]: thing doing a person's action
 --> lexir/README.md:7:60
  |
7 | ...ranks caller-provided token streams. Its in-memory index owns postings
  |                                                       ^^^^^-^^^^
  |                                    a person's verb with a non-person subject
  |
  = why: Verbs such as own, decide, promise, claim, hide or swallow normally
         take a person as subject.
  = help: Make the person the subject, or state the fact directly: what is out
          of scope, what is returned, what is not guaranteed.
  = example: 'It does not own indexing or compaction.' -> 'Indexing and
             compaction are left to the caller.'

info[inline-list]: long list inside a sentence
 --> durability/README.md:8:68
  |
8 | ...y` provides filesystem and in-memory directories, atomic writes, WALs,
  |                                                             ^^^^^^^^^^^^^
9 | record logs, checkpoint files, CRC validation, and sync helpers.
  | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  | 6 items listed in one sentence
  |
  = why: Four or more coordinated items, or items joined by slashes, stretch the
         sentence's dependencies and are hard to scan.
  = help: Use a bulleted list.
  = example: 'It supports standard/Sugeno/Yager negations, OWA, power means, and
             uninorms.' -> a bulleted list
```

</details>

Not every finding is right: see [Limits](#limits) and
[Reporting a false positive](#reporting-a-false-positive).

## Verdicts

Each finding counts 0.5 (info), 1 (warn) or 2 (error). The cost index is that
count per 1,000 words. A file passes below 15, gets "advise" at 15 or more, and
gets "block" at 30 or more with at least 3 weighted findings. Of 110 essays,
documentation pages and READMEs by well-regarded writers (150 words or more,
held out from the reference profile), 107 pass and 3 get "advise"; the median
cost index is 3.2 (measured 2026-10-26).

Commit messages (`--format commit`, the commit-msg hook) are judged against
their own thresholds, 50 and 100, because they are terser than prose: in 1,000
Go commit messages the 99th percentile cost index is 49, against 8 to 16 for
essays, docs, READMEs and discussion. Benchmark tables, shell commands and the
`pkg/path:` scope prefix of the subject line are not read as prose.

A rate is noisy for a short text: one finding in a 20-word comment is 50 per
1,000 words. Below 40 words, readcost counts weighted findings instead: 2 or
more gets "advise" and 3 or more gets "block".

Dependency length is judged against a reference profile: how far apart
related words usually are, by sentence length, in a swatch of essays,
documentation and READMEs by well-regarded writers (126 texts from 22 sources,
listed in `src/readcost/data/default_profile.json`). To compare against
writing that you prefer, build your own:

```sh
readcost profile build path/to/good/*.md -o myprofile.json --name mine
readcost check --profile myprofile.json README.md
```

### Comparing with a style you know

`readcost style` compares a document set with a reference: words per
sentence, predicted reading time, and each rule's rate per 1,000 words, and
marks a rule at least twice as frequent as in the reference (with three or
more findings). Built-in references, measured on readcost's evaluation corpus
(numbers only): `rust-book`, `go-docs`, `python-docs`, `django-docs`,
`sqlite-docs`, `stripe-docs`, `govuk`, `readmes` and `essays`; `readcost
style --list` describes them, and `--against` also takes a profile file from
`readcost profile build`. For an earlier version of this README against the Go docs:

```text
$ readcost style README.md --against go-docs
1 file(s), 2,301 words, against go-docs: 19 texts from Effective Go and the Go blog, fetched for readcost's evaluation corpus

                                         yours       go-docs  ratio
words per sentence                       17.70         17.50  1.0x
predicted ms per word                   213.54        200.70  1.1x
hyphen-compound per 1k words              0.87          0.05  17.7x
inanimate-subject per 1k words            0.00          0.30  0.0x
inline-list per 1k words                  2.17          0.82  2.7x  much higher
long-dependency per 1k words              0.43          0.35  1.3x
reduced-object-relative per 1k words      0.00          0.35  0.0x
stacked-nouns per 1k words                0.43          1.53  0.3x
```

A rate far above the reference is a prompt to look at those sentences, not a
verdict. These rates differ by genre (Reinhart et al. 2025 compare model and
human text within each genre for that reason), so compare with a reference of
the same kind of text.

### Repetition across texts

`readcost corpus` looks across many texts at once (commit messages, PR
descriptions, a model's answers) for syntactic templates and repeated
sentence openers, with Shaib et al.'s (2024) measures: CR-POS, the share of
texts with one of the 100 most frequent part-of-speech 6-grams, and those
6-grams per token. Point it at files or directories (one text each), or at
one file of many texts separated by `---` lines with `--split`. Formulaic
text such as merge-commit subjects scores high legitimately, and the
measures depend on how much text there is (on essays, CR-POS rises from 4.0
to 4.6 between 5 and 40 texts while templates per token falls), so compare
corpora of similar size and kind.

## Predicted reading time

Each whole-document check also reports a predicted reading time, for example
`predicted reading time 211 s (222 ms per word)`, and the JSON output has
`reading_seconds` and `reading_ms_per_word`. A small tree model predicts how
long readers look at each word from its length, its frequency and its
neighbours. It was fitted to eye-tracking data from 360 native English readers
of newspaper paragraphs (OneStop) and takes about 15 ms for 1,000 words.

On held-out paragraphs its error is about 19 ms per word against a mean of
about 200 (OneStop), and 10 ms on a separate corpus (Provo). Always predicting
the average would score 22 and 17, so treat it as a document-level estimate,
useful for comparing two versions of the same text, not as a judgement of one
sentence. When ten models from different labs each rewrote the same 53
paragraphs, every one raised the predicted time per word (by 2 to 19 ms);
readcost's findings did not tell the rewrites apart. The number does not
affect the verdict. Code spans are left out. See
[docs/evaluation.md](https://github.com/arclabs561/readcost/blob/main/docs/evaluation.md)
for how it was built and tested.

To judge a rewrite, compare it with the original. `readcost compare` reports
both the time per word and the total, because a clearer rewrite can still take
longer to read if it is much longer (Cekini et al. 2026 found exactly that for
model rewrites). For the README sentence above and the rewrite it adopted:

```text
$ readcost compare cmp-old.md cmp-new.md
                              old        new  change
words                          26         48  +22
sentences                       1          2  +1
predicted reading time      7.2 s     10.5 s  +3.2 s (+45%)
ms per word                   301        218  -83
findings                        2          0  -2
weighted findings               2          0  -2
verdict                    advise       pass

by rule: hyphen-compound 1 -> 0, stacked-nouns 1 -> 0
```

`--fail-on slower` exits 1 when the rewrite is predicted to take longer in
total, and `--fail-on worse` also when it has more weighted findings, which
suits a check on model rewrites. `-o json` gives both results in full.

`readcost check --hotspots 3` also lists each file's three sentences predicted
to cost the most reading time beyond their length, with their slowest words.
This is experimental: the model was tested on whole texts, not single
sentences.

## Document measures

The JSON output has a `metrics` object per file. None of it changes a finding
or the verdict.

| Key | What it measures | Essays, median | Docs, median |
| --- | --- | --- | --- |
| `mtld` | Lexical diversity of content words (MTLD; McCarthy and Jarvis 2010); none under 50 content words | 149 | 54 |
| `idea_density` | Propositions per word, counted from the parse (DEPID; Sirts et al. 2017) | 0.43 | 0.41 |
| `center_embedding_mean`, `center_embedding_max` | How deeply clauses nest inside clauses that continue after them (Gibson 2000) | 0.07, 1 | 0.04, 1 |
| `sentence_words_profile` | Share of words in sentences of up to 27, 28 to 31, 32 to 38, and more than 38 words (Alves et al. 2010) | 73%, 8%, 10%, 7% | 74%, 9%, 8%, 5% |

Medians are over the evaluation corpus (118 essays and 83 documentation
pages). Documentation repeats its terms, so its lexical diversity is far
lower; higher is not better in technical prose. The sentence-length bands
split the corpus's words at 70%, 80% and 90%, counting each document equally.

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
- `feedback_link`: `false` drops the line that text and agent output end
  with, which points to the false-positive form.

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
second copy of a baselined sentence. The file holds hashes only, sorted one entry per
line, and paths relative to its own directory, so keep it at the repository
root. Run `readcost baseline` again after a cleanup to shrink it.

## Hooks

`docs/hooks.md` describes each adapter, what it sends back, and the rules that
they share: advisory by default, only edited lines, fail open, at most one revision
per turn. In short:

- Claude Code: `integrations/claude-code-plugin/`, or the settings snippet in
  `integrations/claude-code/`.
- piku: `integrations/piku/hooks.json`.
- git: `.pre-commit-hooks.yaml`, or the scripts in `integrations/git/`.
- GitHub Actions: `action.yml`; see the next section.
- Anything else: `readcost hook generic` reads JSON on stdin and writes JSON.

## GitHub Action

The action annotates the lines it flags. On a pull request it checks only the
Markdown, reStructuredText and text files that the pull request adds or
changes; set `changed-only: "false"` to check every file under `paths`. With
`comment: "true"` it also posts one summary comment on the pull request and
edits that comment on later runs, so the thread gets one comment, not one
per push. The comment counts the verdicts, lists the worst findings in a
table, and gives the predicted reading time.

```yaml
name: readcost
on: pull_request

permissions:
  contents: read
  pull-requests: write   # only needed for comment: "true"

jobs:
  prose:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
        with:
          fetch-depth: 0   # lets the action diff against the merge base
      - uses: arclabs561/readcost@main   # pin a commit SHA in real use
        with:
          paths: README.md docs
          fail-on: block
          comment: "true"
```

Inputs:

- `paths`: files or directories, separated by spaces or newlines (default `.`).
- `fail-on`: `never`, `advise` or `block` (default `block`).
- `comment`: `"true"` to post the summary comment (default `"false"`).
- `changed-only`: on a pull request, check only changed files (default `"true"`).

Without `fetch-depth: 0` the action fetches the base commit itself and
compares it with the checked-out commit; that list can include files that
changed on the base branch after the pull request was opened. A pull request
from a fork gets a read-only token, so the comment fails with a warning and the
annotations still appear.

## Reporting a false positive

readcost is advisory, and many findings are wrong (see Limits). When one is,
open an issue with the
[false positive form](https://github.com/arclabs561/readcost/issues/new?template=false-positive.yml):
it asks for the rule, the message, the sentence, where the sentence was, and
why the finding is wrong. Text and agent output end with a line that links to
the form when there are findings; `feedback_link = false` in `readcost.toml`
turns that line off. The hooks never add it, since a model cannot act on it.

## Editors

`readcost lsp` is a language server, so findings show up as diagnostics in
VS Code, Neovim, Helix and other editors with a generic LSP client. Install it
with `pip install 'readcost[lsp]'`.
[docs/editors.md](https://github.com/arclabs561/readcost/blob/main/docs/editors.md) has the
setup for each editor.

## Limits

- readcost is not an AI-text detector. Construction rates and reading-time
  estimates must not be used to judge who wrote a text: the same patterns
  appear in human writing, and treating them as markers penalizes non-native
  English writers in particular.
- English only. Text that is clearly in another language (judged from its
  script and its function words) gets a note instead of findings or a
  reading time; `language_check = false` turns that off. On 2,132 English
  texts in the evaluation corpora the check skipped none.
- The default spaCy model misparses some sentences. A sentence parsed with no
  verb is skipped, and a misparse can produce a false finding. Set
  `model = "en_core_web_trf"` for better parses at several times the cost.
- inanimate-subject and denominal-verb use word lists derived from WordNet.
  Treat their findings as prompts to reread, not verdicts.
- Precision is low on well-edited prose. Ten model raters from different labs
  labelled 210 findings sampled from essays and documentation by well-regarded
  writers. Of the 64 that the current rules still report, a majority of eight
  raters judged 15 (23%) correct or defensible (single raters: 16 to 48%; two
  lenient raters: 75 to 77%). Agreement between raters is modest (Fleiss' kappa 0.40
  over the eight). `readcost explain RULE` shows the count for each rule. See
  [docs/evaluation.md](https://github.com/arclabs561/readcost/blob/main/docs/evaluation.md).
- hyphen-compound skips pairs found in 5+ documents of a 2019 FineWeb-Edu
  crawl (ODC-By; see `src/readcost/data/FINEWEB_NOTICE`).
- The paper's findings are about how often text uses these constructions,
  not about any single sentence, and it ran no reading study on model text.
- The paper also measures rare word pairs. readcost uses word-pair counts only
  to skip hyphenated pairs in common use; it does not flag rare pairs in
  general yet.
- The default profile is edited English technical and essay prose. A cost
  index for chat answers is not comparable to one for READMEs.

## Development

```sh
uv sync && uv run pytest                       # or: pip install -e '.[test]' && python3 -m pytest
uv run readcost check . --fail-on block        # CI runs readcost on its own repo
uv run --group eval scripts/eval_simplifications.py REF   # scripts without inline metadata
uv run scripts/fetch_eval_corpus.py ref/eval   # scripts with inline metadata bring their own
uv run --group eval scripts/build_lexicon.py   # also needs nltk's WordNet data
uv run scripts/build_default_profile.py ref/eval   # after fetch_eval_corpus.py
```

Scripts with inline metadata that import readcost install this checkout, not
the release on PyPI.

## License

MIT or Apache-2.0, at your option. `src/readcost/data/lexicon.json.gz` is
derived from Princeton WordNet 3.0; its license is in
`src/readcost/data/WORDNET_LICENSE`.
