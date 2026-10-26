# readcost

readcost points at sentences that are likely to slow a reader down: three or
more nouns in a row, related words far apart, things doing a person's action,
and four other constructions. The list comes from "Why is AI-generated
language so hard to understand?" ([arXiv 2610.29162](https://arxiv.org/abs/2610.29162)).
The paper finds that recent language models use these constructions more than
people do; earlier reading studies tie each of them to slower reading.

It is for two jobs: checking documentation that you write, and checking text a
model writes before you or your users read it. It reads Markdown,
reStructuredText, HTML, plain text, doc comments in source files, commit
messages, and model output as raw text, chat JSON, or Claude Code transcripts.
It runs as a command, a Python library, or a hook in Claude Code, piku, git and
GitHub Actions.

It is not a grammar or style checker. Vale and proselint enforce style rules
and word lists; readcost parses each sentence and looks at its structure. It is
also not a readability formula: it says which sentence to change and how, not
a grade level. It cannot tell whether text is complete, correct or up to date,
which developers rate as the worst documentation failures.

Status: experimental, version 0.1.0. [docs/research.md](docs/research.md) has
the evidence behind each choice and the roadmap.

## Install

```sh
pip install git+https://github.com/arclabs561/readcost   # or: pip install -e . from a checkout
readcost setup              # downloads the spaCy English model (about 13 MB)
```

Python 3.11 or later. The dependencies are spaCy and markdown-it-py. readcost is
not on PyPI yet.

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

Output is plain text by default. `-o json`, `-o sarif` and `-o github` are for
tools, and `-o agent` is short feedback written for a model. The exit status is
1 when a file reaches the `--fail-on` verdict (default `block`), 2 on an error,
and 0 otherwise.

For example, this sentence from a README:

```text
For store restart measurement, the example prints first snapshot-query cost
with persisted WAND sidecars present versus after deleting those sidecars and
forcing source-segment rebuilds.
```

```text
notes.md:1: warn: [stacked-nouns] 3 nouns stacked: 'store restart measurement'
notes.md:1: warn: [stacked-nouns] 3 nouns stacked: 'source-segment rebuilds'
notes.md: advise; 2 findings in 1 sentences (26 words); cost index 76.9 per 1k words
```

The rewrite that README adopted keeps every fact and passes:

```text
To measure a store restart, the example reopens a checkpointed store and
prints the duration of its first snapshot query. It does this twice: once
with the persisted WAND sidecars present, and once after deleting those
sidecars, which forces each segment to be rebuilt from its source vectors.
```

From Python:

```python
from readcost import check_text

result = check_text(answer, fmt="markdown")
if result.verdict != "pass":
    for f in result.findings:
        print(f.line, f.feature, f.message, f.suggestion)
```

## What it flags

| Feature | Example | Rewrite |
| --- | --- | --- |
| stacked-nouns | forcing source segment rebuilds | forcing each segment to be rebuilt from its source |
| long-dependency | The index, which is built once from every document in the corpus at startup and then rebuilt only when the compactor runs, serves all queries. | The index serves all queries. It is built once at startup and rebuilt only when the compactor runs. |
| inanimate-subject | It does not own indexing or compaction. | Indexing and compaction are left to the caller. |
| denominal-verb (opt-in) | The script will bucket the requests by hour. | The script will group the requests by hour. |
| reduced-object-relative | the format the reader expects | the format that the reader expects |
| hyphen-compound | the storage-shrink job | the job that shrinks storage |
| inline-list | supports standard/Sugeno/Yager negations, OWA, power means, and uninorms | a bulleted list |
| nominalization (opt-in) | The tool performs validation of the input. | The tool validates the input. |
| participial-clause (opt-in) | The parser caches every token, making lookups faster. | The parser caches every token, so lookups are faster. |
| repeated-frame (opt-in) | This change reduces the latency of the cache. This change improves the speed of the parser. This change lowers the cost of the build. | This change makes the cache faster, the parser quicker and the build cheaper. |

The first five come from the paper; denominal-verb is opt-in because on
well-edited prose nearly all its hits were settled verbs. The next two are
rules derived from where those constructions show up in technical writing. A
hyphenated word counts as one noun, so "storage-shrink job" is a hyphen
compound, not three stacked nouns. The other opt-in three are constructions
that language models use more often than people (Reinhart et al. 2025; Shaib
et al. 2024). Turn any opt-in rule on with `--enable`. `long-sentence` is also
available but off by default. `readcost explain` prints why each one costs the
reader and how to fix it. When a long-dependency or inline-list
sentence gives a reason (because, since, so that, otherwise), the suggestion
says to keep that reason when splitting the sentence.

Technical writing repeats compressed terms on purpose, so a stacked or
hyphenated compound is reported once per document, at its first use. An
identifier as a subject (`` `parse()` returns ``) is not reported as an
inanimate subject. Code spans, URLs and file paths count as single words.

## Verdicts

Each finding counts 0.5 (info), 1 (warn) or 2 (error). The cost index is that
count per 1,000 words. A file passes below 15, gets "advise" at 15 or more, and
gets "block" at 30 or more with at least 3 weighted findings. The ten BurntSushi
READMEs of 150 words or more score at most 12.5 (median 7.3, measured
2026-10-26), so the defaults treat that level of writing as the bar.

Commit messages (`--format commit`, the commit-msg hook) are judged against
their own thresholds, 50 and 100, because they are terser than prose: in 1,000
Go commit messages the 99th percentile cost index is 49, against 8 to 16 for
essays, docs, READMEs and discussion. Benchmark tables, shell commands and the
`pkg/path:` scope prefix of the subject line are not read as prose.

A rate is noisy for a short text: one finding in a 20-word comment is 50 per
1,000 words. Below 40 words, readcost counts weighted findings instead: 2 or
more gets "advise" and 3 or more gets "block".

Dependency length is judged against a reference profile built from those
READMEs. To compare against writing that you prefer, build your own:

```sh
readcost profile build path/to/good/*.md -o myprofile.json --name mine
readcost check --profile myprofile.json README.md
```

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
readcost's findings did not tell the rewrites apart. The number does not affect the verdict. Code spans are left out. See
[docs/evaluation.md](docs/evaluation.md) for how it was built and tested.

## Configuration

Put a `readcost.toml` at the repository root, or a `[tool.readcost]` table in
`pyproject.toml`. `readcost.toml.example` lists every key with its default. The
useful ones:

- `allow`: phrases never flagged, such as product names or terms of art.
- `disable` and `enable`: turn features off or on.
- `advise_severity`: the verdict is at least `advise` when any finding reaches
  this severity; `off` turns that rule off.
- `profile`: a relative path is read from the config file's directory.
- `hooks.mode`: `off`, `advise` or `block`.

readcost warns about unknown keys and stops with exit code 2 on a value of the
wrong type or outside its choices, naming the file and the key.

To skip text, put `<!-- readcost: ignore -->` before a paragraph, or wrap a
section in `<!-- readcost: off -->` and `<!-- readcost: on -->`.

## Hooks

`docs/hooks.md` describes each adapter, what it sends back, and the rules that
they share: advisory by default, only edited lines, fail open, at most one revision
per turn. In short:

- Claude Code: `integrations/claude-code-plugin/`, or the settings snippet in
  `integrations/claude-code/`.
- piku: `integrations/piku/hooks.json`.
- git: `.pre-commit-hooks.yaml`, or the scripts in `integrations/git/`.
- GitHub Actions: `action.yml`.
- Anything else: `readcost hook generic` reads JSON on stdin and writes JSON.

## Limits

- readcost is not an AI-text detector. Construction rates and reading-time
  estimates must not be used to judge who wrote a text: the same patterns
  appear in human writing, and treating them as markers penalizes non-native
  English writers in particular.
- English only.
- The default spaCy model misparses some sentences. A sentence parsed with no
  verb is skipped, and a misparse can produce a false finding. Set
  `model = "en_core_web_trf"` for better parses at several times the cost.
- inanimate-subject and denominal-verb use word lists derived from WordNet.
  Treat their findings as prompts to reread, not verdicts.
- Precision is low on well-edited prose. On 210 findings sampled from essays
  and documentation by well-regarded writers, two automated raters from
  different model families (agreement kappa 0.41) found 1 to 3% correct and
  16 to 22% correct or defensible. After the fixes that evaluation prompted,
  25 to 33% of the findings still reported are correct or defensible, at
  about 40% of the earlier volume. See [docs/evaluation.md](docs/evaluation.md).
- hyphen-compound skips pairs found in 5+ documents of a 2019 FineWeb-Edu
  crawl (ODC-By; see `src/readcost/data/FINEWEB_NOTICE`).
- The paper's findings are about how often text uses these constructions,
  not about any single sentence, and it ran no reading study on model text.
- The paper also measures rare word pairs. readcost does not yet; the roadmap
  in docs/research.md describes how it will.
- The default profile is one writer's READMEs. A cost index for chat answers
  is not comparable to one for READMEs.

## Development

```sh
pip install -e '.[test]' && python3 -m pytest
readcost check . --fail-on block               # CI runs readcost on its own repo
python3 scripts/build_lexicon.py               # needs nltk and its WordNet data
python3 scripts/build_default_profile.py ref/  # needs the BurntSushi clones
```

## License

MIT or Apache-2.0, at your option. `src/readcost/data/lexicon.json.gz` is
derived from Princeton WordNet 3.0; its license is in
`src/readcost/data/WORDNET_LICENSE`.
