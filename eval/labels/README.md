# Labels

Every label that readcost's evaluations have collected, in one file:
`labels.jsonl`, one row per round, item and rater. It holds item ids,
labels and the raters' short causes. It holds no source text.

- `raters.json` is the manifest: one entry per rater file, with its round,
  model, family, protocol, rubric, shuffle seed, how it was run, date and
  notes. Its `rounds` list points to each round's sample, plan and raw
  replies.
- `labels.jsonl` is built from the manifest and the rater files by
  `scripts/build_label_table.py`. Do not edit it by hand.
- The other `*.json` files here are the in-sample labels of 210 findings
  (round `insample`, ten raters), keyed by a hash of the finding.

## Rounds

| Round | Folder | Items | Raters |
| --- | --- | --- | --- |
| `insample` | `eval/labels/` | 210 | 10, one per model family; primed |
| `round1` | `eval/heldout/` | 597 | 12 primed, 3 unprimed |
| `round2` | `eval/breadth/` | 875 | 12 primed, 3 unprimed |
| `round3` | `eval/kinds/` | 1,694 | 12 primed, 3 unprimed |

A primed rater saw readcost's rule name and message; an unprimed rater saw
only the sentence and the marked words. In rounds 1 to 3 every rater is a
Claude model; `raw/` in each round's folder holds each rater's reply to each
batch, as written.

## Fields

| Field | Meaning |
| --- | --- |
| `round` | round name, as in `raters.json` |
| `item` | the item's id in its round, as a string: the six-digit `i` of the round's `sample.jsonl`, or the in-sample hash |
| `rater` | the rater file's name without `.json` |
| `model`, `family`, `protocol` | from the manifest; `protocol` is `primed` or `unprimed` |
| `label` | `c` (correct), `d` (defensible) or `w` (wrong) |
| `construction_present` | `true` or `false` when the rater was asked; else `null` |
| `cause` | the rater's few words on why, or `null` |
| `rule`, `stratum`, `kind` | from the round's `sample.jsonl`; `null` where the round has none |
| `item_type` | `finding`, `near` (near miss), `decoy` or `ranked` |
| `decoy` | round 1 only: `random` or `long` for a decoy |

Rows follow the manifest's order of raters, then item id. A rater file that
lists an item twice gives one row, from the first copy; two copies with
different labels are an error.

## Adding a rater

1. Write `eval/<round>/labels/<rater>.json`: a JSON list of
   `{"id": ..., "label": "c" | "d" | "w", "construction_present": true | false, "cause": "..."}`
   (`construction_present` and `cause` may be left out). Keep the replies
   per batch in `eval/<round>/raw/<rater>-batch-NN.json`.
2. Add an entry for it at the end of `raters.json`. Do not edit or reorder
   the entries already there, so that the new rows go at the end of
   `labels.jsonl`.
3. Run `python3 -I scripts/build_label_table.py` and commit both files.

`python3 -I scripts/build_label_table.py --check` and
`tests/test_label_table.py` fail when `labels.jsonl` is out of date, and
when a label file under `eval/` is missing from the manifest. A new round
also needs an entry in `rounds`.

## Item texts

The sentences are third-party text and stay out of this repository. They
are in the private Hugging Face dataset `arclabs561/readcost-labels`, and
can be rebuilt from the pointers in each round's `sample.jsonl`
(repository, commit, path, blob and offsets) with
`scripts/rebuild_items.py`. The in-sample items can be rebuilt only from
the fetched evaluation corpus; see [docs/labels.md](../../docs/labels.md).
