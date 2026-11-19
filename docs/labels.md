# Labels on findings

A label is one rater's judgment of one finding. This page describes the file
that holds labels, the commands that produce it, and what the older label
files can and cannot give.

The study this is for is in [research.md](research.md), "What has not been
shown": 100 to 150 findings, three or more people, and the alternative
annotator test of Calderon, Reichart and Dror 2025 to say whether model
raters can stand in for them. No person has labelled a finding yet. This
page is the tooling, not a result.

## Offsets

Every finding has `start` and `end`: character offsets into the file, with
the end exclusive, so `text[start:end]` is the flagged words as the file
spells them.

- A character is a Unicode code point of the file decoded as UTF-8. A byte
  order mark counts as one character, and `\r\n` as two.
- `line`, `column`, `end_line` and `end_column` say the same span in lines
  and 1-based columns. Lines end at `\n`, `\r\n` or `\r`.
- `sentence_start` and `sentence_end` are the offsets of the sentence that
  holds the words.
- Markup inside the span is part of it: `the *big* index` and
  `[index team](https://example.com)` are kept whole. A span that starts or
  ends at inline code covers the backticks. In reStructuredText it covers
  the role (``:func:`name` ``) and in HTML the `<code>` tags. A character
  reference such as `&amp;` counts from `&` to `;`.
- A finding with no words of its own (long-sentence) has the sentence's
  span.

Offsets are `null` in two cases. Text taken from a JSON file (`transcript`,
`messages`, `jsonl`) is an escaped string there, so its offsets would not be
offsets into the file. A line of a Python docstring that the source spells
with an escape (`\t`, `\\`) cannot be matched to the source. A finding
without offsets still has its line.

## The file

A labels file is JSON Lines: one label per line, one line per rater per
finding.

```json
{"doc": "docs/guide.md", "doc_version": "sha256:72e8…", "start": 6970, "end": 6995, "rule": "stacked-nouns", "label": "wrong", "present": true, "cause": "an established term", "rater": "ana", "rater_kind": "human", "prompt_version": "rubric-1", "date": "2026-11-18", "text": "transport connection pool"}
```

| Field | Meaning |
| --- | --- |
| `doc` | The document: a path or a URL. |
| `doc_version` | Which text the offsets count into: `sha256:` and the hash of the file's bytes, or `git:` and a commit. |
| `start`, `end` | Character offsets of the flagged words, as above. |
| `rule` | The rule that made the finding. |
| `label` | `correct`, `defensible` or `wrong`. |
| `present` | Whether the construction is there at all, apart from its cost: `true`, `false` or `null`. |
| `cause` | A few words on why. |
| `rater` | A person's handle or a model id. |
| `rater_kind` | `human` or `model`. |
| `prompt_version` | The instructions the rater had. `rubric-1` is the rubric below. |
| `date` | ISO date of the label. |
| `text` | Optional: the document's text from `start` to `end`, so the offsets can be checked. |
| `finding` | Only in converted older files: the hash that named the finding there. |

`readcost.labels` reads and writes the file (`read`, `write`, `loads`,
`dumps`), refuses a line with an unknown field or a bad value, and checks
labels against a document (`check_offsets`). It needs no parser.

The format is plain on purpose. It does not use the types of an annotation
library, so any tool that reads JSON Lines can read it.

## Labelling by hand

```sh
readcost label export docs/ README.md -n 150 -o sheet.csv
```

This checks the files, samples up to 150 findings and writes two files.

- `sheet.csv` is for the raters. Each row has an `item` id, the rule, the
  rule's definition, the sentence as the source has it with `[[` and `]]`
  around the flagged words, those words alone, and three empty columns:
  `label`, `present` and `cause`. Rows are shuffled, and the sheet does not
  say which document a sentence is from, what readcost's message was, or
  what any other rater said.
- `sheet.key.jsonl` says where each item is: document, version, offsets and
  rule. Keep it and do not hand it out.

The sample takes the same number of findings from each rule as far as the
rules allow, so a rare rule is not crowded out. `--seed` fixes the sample
and the order. Findings below the configured severity are included, and a
baseline is ignored. A sheet named `.jsonl` holds one JSON object per row.

Give each rater a copy of the sheet and these instructions (`rubric-1`, the
words the model raters had in `scripts/second_rater.py`):

> Each row is a finding from a prose linter: it says that a sentence contains
> a construction that may slow readers down. Judge each finding on its own,
> as an experienced technical editor would.
>
> **label**
> - `correct`: the construction is really there and it is a real reading
>   cost an editor would fix.
> - `defensible`: the construction is there and an editor might reasonably
>   flag it, but fixing it is optional or the author's choice is fine.
> - `wrong`: the construction is not really there (misparse, wrong
>   definition), or it is there but costs the reader nothing (a fixed
>   phrase, a term of art, an idiom, an ordinary verb).
>
> **present**: `yes` if the construction the rule names is actually in the
> sentence, judged by the rule's definition and apart from whether it costs
> the reader; else `no`.
>
> **cause**: a few words on why.

A label may be written as its first letter. Then read each filled sheet
back:

```sh
readcost label import ana.csv --rater ana --key sheet.key.jsonl -o labels.jsonl
readcost label import bo.csv  --rater bo  --key sheet.key.jsonl -o labels.jsonl
readcost label import cy.csv  --rater cy  --key sheet.key.jsonl -o labels.jsonl
readcost label agreement labels.jsonl
```

`import` appends to the labels file. It reports and skips a row with no
label or a value it cannot read, so a half-filled sheet can be read. A
sheet that a model filled is read with `--kind model`.

`agreement` prints, for the items every rater labelled:

- Fleiss' kappa, with the observed agreement, the chance agreement and the
  share of each label. Chance agreement comes from those shares. With most
  labels `wrong`, a chance level fixed at one half would overstate kappa.
- Cohen's kappa for each pair of raters.
- the majority vote: the label that more than half of the raters gave.

It prints the same three for `correct` or `defensible` against `wrong`, and
for `present`. `--kind human` or `--kind model` keeps one kind of rater, and
`-o json` gives the numbers to a script.

Not built: the alternative annotator test itself. It needs the people's
labels first.

## Other labelling tools

Read on 18 November 2026; nothing here was run.

- **CSV** opens in any spreadsheet, which is enough for 150 rows and three
  columns. It is the default.
- **JSON Lines** is the same rows for a script or a model rater.
- **Label Studio** imports tasks as JSON with a `data` object and
  `predictions` whose spans are `start`, `end`, `text` and `labels` over
  plain text (its guide to importing pre-annotated data). The key file
  has those fields, so an exporter would be short. Reading its export back
  and a labelling configuration for the three questions would have to be
  tested against a running server. That is not cheap, so it is not built.
- **factgenie** collects error spans in model outputs from crowd workers and
  model judges through its own web server, and expects its own dataset and
  campaign folders. It lets raters mark spans. This study gives them a span
  to judge, so the fit is poor.

## Older label files

`eval/labels/*.json`, apart from the manifest `raters.json`, hold ten
model raters' labels of 210 findings. Each label is keyed by the first 16
hex digits of a hash of the text id, the rule and the sentence.

`eval/labels/labels.jsonl` collects these and the labels of the three
held-out rounds in one table, one row per round, item and rater; its
README says how it is built and how to add a rater.

```sh
readcost label convert $(ls eval/labels/*.json | grep -v raters.json) -o model-labels.jsonl
readcost label agreement model-labels.jsonl
```

What converts: the label, `present`, `cause`, the rater (the file's name),
`rater_kind` `model`, and `rubric-1`. The old key is kept as `finding`, so
labels of the same finding still meet and agreement can be computed. The
converted files give Fleiss' kappa 0.23 for all ten raters and 0.40 without
the two lenient ones, the numbers in [evaluation.md](evaluation.md).

What does not convert from the repository alone: the document, the rule and
the offsets. The key is a hash, and the sampled findings are in the fetched
evaluation corpus, not here. With that corpus,
`--sample ref/eval/results/sample.jsonl` fills in the document id and the
rule. Offsets are in neither file. Recovering them means checking the
fetched text again and matching findings by rule and sentence. That can
only find the findings the current rules still report, and it has not been
done. The dates are not in the files either; `--date` sets one.
