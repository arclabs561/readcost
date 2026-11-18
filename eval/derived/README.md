---
license: other
language:
- en
pretty_name: readcost features against human signals
---

# readcost features against human signals

One record per text (or per revision pair) from existing datasets in
which people rated, edited, annotated or read English prose. Each record
holds the measures readcost computes for the text and the human outcome
that the source dataset gives. No text is included: each record points to
the row it came from and carries the SHA-256 of the text, so the text can
be recovered from the source and checked.

The `matrix` and `matrix-report` jobs in readcost's
`.github/workflows/eval.yml` build it; the `readcost-derived` artifact of
a run holds the files below. docs/datasets.md in the readcost repository
lists every source with its licence, and docs/evaluation.md reports what
the records show.

## Files

- `NAME.jsonl`: one dataset's records.
- `MANIFEST.json`: for each file, the record count, the file's SHA-256, the
  source and its licence, and whether any outcome is a derived label.
- `PART.SHA256SUMS`: the SHA-256 of each downloaded source file, so a
  reader can tell whether the source has changed since the run.

## Fields of a text record

| Field | Meaning |
| --- | --- |
| `dataset`, `id`, `group` | source, row identifier, and the group whose texts answer one prompt, summarise one article or share a paragraph |
| `pointer` | where the text is in the source: file and row, or the source's own identifiers |
| `sha256` | SHA-256 of the text as readcost read it (UTF-8) |
| `outcomes` | the human outcome or outcomes; `DATASETS` in scripts/dataset_matrix.py says which way is worse for the reader |
| `counts`, `rates` | findings per readcost rule, as a count and per 100 checked words; default and opt-in rules |
| `points_per100` | weighted findings of the default rules per 100 checked words (info 0.5, warn 1, error 2) |
| `metrics` | MTLD, idea density, mean and maximum embedding depth, mean dependency z, predicted reading time per word |
| `words`, `checked_words`, `sentences`, `words_per_sentence`, `mean_word_len`, `mean_zipf` | length and lexical controls; Zipf values from readcost's word list |
| `words_table` | Scarecrow only: per word, the rules whose span covers it, its length and Zipf value, and the share of annotators who marked it, by category |

A revision record has `intents`, `target` (the edit has the intent the
analysis compares: clarity or fluency, readability, concision), `edit_size`
(share of words changed), `sha256_before`, `sha256_after`, and `before` and
`after` objects with the fields above.

## Derived labels

Two outcomes were computed by readcost's scripts from human-written text,
not shipped by the source: in `helpsteer3_feedback`, the share of an
answer's three feedback paragraphs that complain about length, clarity or
repetition (word lists in scripts/dataset_matrix.py); in `helpsteer3_edit`,
whether the editor's change summary mentions concision or clarity. Treat
them as noisy.

## Licences and publication

The records are numbers computed from the sources plus pointers, but some
sources restrict use. Before publishing, check each source in the manifest:

| May be published with attribution | Check first |
| --- | --- |
| helpsteer2, helpsteer3_feedback, helpsteer3_edit, onestop, provo (CC BY 4.0); summeval (MIT); tldr_axis, cnndm_axis (OpenAI's modified MIT); iterater (Apache-2.0) | readmepp (research and non-commercial use only); pararev (CC BY-NC-SA 4.0); geco (free for research with citation); scarecrow, arxivedits (no licence stated) |

## Upload (maintainer)

Nothing uploads automatically. To publish the first column only:

```sh
gh run download RUN_ID -n readcost-derived -D derived
cd derived && sha256sum -c <(python3 -c 'import json; [print(f["sha256"]+"  "+f["file"]) for f in json.load(open("MANIFEST.json"))["files"]]')
hf upload OWNER/readcost-human-signals . . --repo-type dataset \
  --include "README.md" "MANIFEST.json" "helpsteer*.jsonl" "summeval.jsonl" "*_axis.jsonl" \
  "iterater.jsonl" "onestop.jsonl" "provo.jsonl"
```

## Limits

- readcost's rules fire on a minority of texts in most sets, so most
  records carry zero findings.
- Rates depend on readcost's version and the spaCy model; the manifest
  names the generator, and the run's commit names the version.
- Sampling: large sets are cut to a fixed number of texts, keeping groups
  whole, with seed 0.
