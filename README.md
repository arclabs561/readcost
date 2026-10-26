# readcost

readcost points at sentences that are likely to slow a reader down: three or
more nouns in a row, related words far apart, things doing a person's action,
and four other constructions. The list comes from "Why is AI-generated
language so hard to understand?" ([arXiv 2610.29162](https://arxiv.org/abs/2610.29162)),
which links these constructions to measured reading difficulty and finds that
recent language models use them more than people do.

It is for two jobs: checking documentation you write, and checking text a
model writes before you or your users read it. It reads Markdown,
reStructuredText, HTML, plain text, doc comments in source files, commit
messages, and model output as raw text, chat JSON, or Claude Code transcripts.
It runs as a command, a Python library, or a hook in Claude Code, piku, git and
GitHub Actions.

It is not a grammar or style checker. Vale and proselint enforce style rules
and word lists; readcost parses each sentence and looks at its structure. It is
also not a readability formula: it says which sentence to change and how, not
a grade level.

Status: experimental, version 0.1.0.

## Install

```sh
pip install git+https://github.com/arclabs561/readcost   # or: pip install -e . from a checkout
readcost setup              # downloads the spaCy English model (about 13 MB)
```

Python 3.11 or later. The only dependency is spaCy. readcost is not on PyPI yet.

## Use

```sh
readcost check README.md docs/
readcost check --lines 40-80 README.md      # only sentences starting on these lines
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

A finding looks like this:

```text
README.md:117: warn: [stacked-nouns] 3 nouns stacked: 'source-segment rebuilds'
README.md: advise; 6 findings in 41 sentences (612 words); cost index 18.0 per 1k words
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
| long-dependency | The index, built once from all documents and rebuilt only on compaction, serves queries. | The index serves queries. It is built once and rebuilt only on compaction. |
| inanimate-subject | It does not own indexing or compaction. | Indexing and compaction are left to the caller. |
| denominal-verb | Footnote the exception. | Add a footnote about the exception. |
| reduced-object-relative | the format the reader expects | the format that the reader expects |
| hyphen-compound | the storage-shrink use case | the main use: storing ID sets in less space |
| inline-list | supports standard/Sugeno/Yager negations, OWA, power means, and uninorms | a bulleted list |

The first five come from the paper. The last two are rules derived from where
those constructions show up in technical writing. `long-sentence` is
available but off by default. `readcost explain` prints why each one costs the
reader and how to fix it.

## Verdicts

Each finding counts 0.5 (info), 1 (warn) or 2 (error). The cost index is that
count per 1,000 words. A file passes below 15, gets "advise" at 15 or more, and
gets "block" at 30 or more with at least 3 weighted findings. The ten BurntSushi
READMEs of 150 words or more score at most 12.5 (median 7.3, measured
2026-10-26), so the defaults treat that level of writing as the bar.

Dependency length is judged against a reference profile built from those
READMEs. To compare against writing you prefer, build your own:

```sh
readcost profile build path/to/good/*.md -o myprofile.json --name mine
readcost check --profile myprofile.json README.md
```

## Configuration

Put a `readcost.toml` at the repository root, or a `[tool.readcost]` table in
`pyproject.toml`. `readcost.toml.example` lists every key. The useful ones:

- `allow`: phrases never flagged, such as product names or terms of art.
- `disable` and `enable`: turn features off or on.
- `hooks.mode`: `off`, `advise` or `block`.

To skip text, put `<!-- readcost: ignore -->` before a paragraph, or wrap a
section in `<!-- readcost: off -->` and `<!-- readcost: on -->`.

## Hooks

`docs/hooks.md` describes each adapter, what it sends back, and the rules they
share: advisory by default, only edited lines, fail open, at most one revision
per turn. In short:

- Claude Code: `integrations/claude-code-plugin/`, or the settings snippet in
  `integrations/claude-code/`.
- piku: `integrations/piku/hooks.json`.
- git: `.pre-commit-hooks.yaml`, or the scripts in `integrations/git/`.
- GitHub Actions: `action.yml`.
- Anything else: `readcost hook generic` reads JSON on stdin and writes JSON.

## Limits

- English only.
- The default spaCy model misparses some sentences. A sentence parsed with no
  verb is skipped, and a misparse can produce a false finding. Set
  `model = "en_core_web_trf"` for better parses at several times the cost.
- inanimate-subject and denominal-verb use word lists derived from WordNet.
  Treat their findings as prompts to reread, not verdicts.
- The paper also measures rare word pairs. readcost does not, because that
  needs a large reference corpus.
- The default profile is one writer's READMEs. A cost index for chat answers
  is not comparable to one for READMEs.

## Development

```sh
pip install -e '.[test]' && python3 -m pytest
python3 scripts/build_lexicon.py               # needs nltk and its WordNet data
python3 scripts/build_default_profile.py ref/  # needs the BurntSushi clones
```

## License

MIT or Apache-2.0, at your option. `src/readcost/data/lexicon.json.gz` is
derived from Princeton WordNet 3.0; its license is in
`src/readcost/data/WORDNET_LICENSE`.
