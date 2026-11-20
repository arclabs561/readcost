# Pre-registration: re-rating rounds 1 to 3 with open models from other families

Written 19 November 2026 (UTC), before any model below was called on any
item. The commit that adds this file is the registration; its timestamp on
GitHub is the record. Nothing in this file changes after that commit. Any
change made later goes in a dated "Amendments" section at the end, with the
reason.

## Why

Every label in the three held-out precision rounds came from Claude models:
fifteen raters per item, twelve primed (three each of Opus 5.5, Sonnet 5.5,
Haiku 5.5 and Fable 5.2) and three unprimed (one each of Opus, Sonnet and
Haiku). The plans are [heldout-precision.md](heldout-precision.md),
[breadth-precision.md](breadth-precision.md) and
[kinds-precision.md](kinds-precision.md); the results are in
[evaluation.md](../evaluation.md), "Held-out precision, pre-registered",
"Held-out precision: a wider panel and unprimed raters", "Precision across
formats" and "Precision by kind of document". Several of readcost's
decisions rest on them: inanimate-subject became opt-in (#98) and
center-embedding became a default rule (#107).

The four Claude models share training data and methods, so their agreement
may be a property of the family and not of the sentences. This test labels
every item of the three rounds again with open-weight models from four other
families, under the same rubrics, and asks which results survive.

No person labels anything here either.

## What was seen before writing this

- The three plans, their amendments, their reports (`eval/heldout/`,
  `eval/breadth/report.md`, `eval/kinds/report.md`) and the summaries in
  evaluation.md, which give the Claude panel's results per rule.
- The six rubrics and the item files of the label store
  (`round{1,2,3}.jsonl.gz`, built by `scripts/rebuild_items.py` on branch
  `eval/rebuild-items`): their fields, row counts and the length of their
  text fields. No item was read and none was shown to any model.
- The model cards, chat templates, generation configs, file lists and Hub
  metadata of the models below and of those rejected, read on the Hugging
  Face Hub on 19 November 2026.

## Models

One instruction model from each of four families, none from Anthropic. Each
fits on one H200 (141 GB) with room for the cache: weights of 63 GB or
less, in the precision the publisher ships. None is gated; each licence
allows this use.

| Family | Repository | Revision (commit) | Parameters | Weights as run | Licence |
| --- | --- | --- | --- | --- | --- |
| Qwen (Alibaba) | `Qwen/Qwen3.8-27B` | `37561816e66b5b9153b1b64c10968c18c1e6f4a0` | 27.8B dense | bf16, 55.6 GB | Apache-2.0 |
| Gemma (Google) | `google/gemma-4-31B-it` | `842da3794eaa0b77d5f08bae87a17459d91ff475` | 31.3B dense | bf16, 62.6 GB | Apache-2.0 |
| GLM (Z.ai) | `zai-org/GLM-4.7-Flash` | `7dd20894a642a0aa287e9827cb1a1f7f91386b67` | 31.2B MoE, about 3B active | bf16, 62.4 GB | MIT |
| Mistral | `mistralai/Ministral-3-14B-Instruct-2512` | `29439f81c2be264d8d393273f99e7db9c0961120` | 13.9B dense | fp8 as released, 15.7 GB | Apache-2.0 |

The family keys used in file names are `qwen`, `gemma`, `glm` and
`mistral`.

The substitute, used only under "Stopping and substitution" below, is
`allenai/Olmo-3.1-32B-Instruct` at `ac0587e4a7744a551c059d8cd17ba220bc940dae`
(Ai2, 32.2B dense, bf16, 64.5 GB, Apache-2.0, family key `olmo`).

Rejected, with the reason:

- Larger models from the same families do not fit on one H200 with a cache:
  `mistralai/Mistral-Small-4-119B-2603` (121 GB in fp8; its card serves it
  on two GPUs), `zai-org/GLM-5.3-Flash` (321B),
  `Qwen/Qwen3.8-Flash-Next` (180B, and its licence is "other").
- `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-FP8`: 128 GB, and its card
  gives two H100s as the minimum.
- `deepseek-ai/DeepSeek-V4.1-Flash-1017`: 763B.
- Llama 4: gated, and Scout is 109B.
- `openai/gpt-oss-120b`: released in August 2025, shipped only in MXFP4,
  and it answers only after a reasoning channel.
- Granite 4.1 and Phi-4: smaller and older than the models kept.

Ministral 3 14B is the weakest of the four by its card's benchmarks. It is
kept anyway. Mistral Small 4 is stronger but does not fit, and Mistral
Small 3.2 is older (June 2025).

Thinking is off for every model: `enable_thinking=False` in the chat
template for Qwen and GLM, and Gemma's template leaves it off unless asked.
Ministral 3 Instruct has no thinking mode. The Claude raters wrote labels
directly, and a reasoning trace would multiply the cost.

## Software

- vLLM 0.34.0 (released 16 November 2026), in the image
  `vllm/vllm-openai:v0.34.0`, offline `LLM` class. The job records the
  version it ran, the GPU, and the torch and CUDA versions.
- Each model is loaded with `revision` set to the commit above,
  `max_model_len=8192`, `gpu_memory_utilization=0.90`,
  `enable_prefix_caching=True`, `generation_config="vllm"` (so the
  sampling defaults in each repository's `generation_config.json` are not
  applied), images off (`limit_mm_per_prompt={"image": 0}` where the model
  takes images), and seed 0. Ministral is loaded with `tokenizer_mode`,
  `config_format` and `load_format` set to `"mistral"`, as its card says.
- The job script is `scripts/open_raters_job.py` and the report script is
  `scripts/open_raters_report.py`, both added in the pull request that adds
  this plan, in a commit after this one.

## Items

All items of the three rounds, as the label store holds them:

| Round | Folder | Items | Shown primed | Shown unprimed |
| --- | --- | --- | --- | --- |
| 1 | `eval/heldout/` | 597 | 597 | 597 |
| 2 | `eval/breadth/` | 875 | 875 | 875 |
| 3 | `eval/kinds/` | 1,694 | 1,153 | 1,694 |

Round 3's 541 ranked sentences are shown unprimed only, as before. The job
records the SHA-256 of each item file after decompression, and of each
rubric. An item whose text cannot be rebuilt is left out and listed; it is
not replaced.

## Protocol

### One request per item

Each item is rated in its own request, independently of every other item.
The Claude raters saw batches of about 25 shuffled items; here the batch is
one item, so there is no order to shuffle and no item can influence
another. This is the one intended difference from the Claude protocol.

Each request is a chat of two messages:

1. system: the round's rubric, verbatim, the file `RUBRIC.txt` for primed
   items and `RUBRIC_BLIND.txt` for unprimed items;
2. user: a batch file of one item, written as the Claude raters' batch
   files were written: `json.dumps([item], ensure_ascii=False, indent=1)`.

The item has the fields the round's batch files had, in their order:

| Round | Primed | Unprimed |
| --- | --- | --- |
| 1 | `i`, `rule`, `message`, `excerpt`, `sentence`, `before`, `after` | `i`, `excerpt`, `sentence`, `before`, `after` |
| 2 and 3 | `i`, `kind`, `rule`, `message`, `excerpt`, `sentence`, `before`, `after` | `i`, `kind`, `excerpt`, `sentence`, `before`, `after` |

`excerpt` is `primed_excerpt` in primed items and `blind_excerpt` in
unprimed items. An unprimed item never has `rule` or `message`.

### The reply

The reply is constrained with vLLM structured outputs to a JSON schema of
the rubric's own reply format for a batch of one:

```text
{"labels": [{"i": <the item's id>, "label": "c" | "d" | "w", "present": true | false, "cause": "<string>"}]}
```

The array has exactly one entry, `i` is fixed to the item's id, no other
property is allowed, and the unprimed schema has no `present`. The rubric
asks for a cause under 8 words; the schema does not enforce that, and
`max_tokens` is 160. A reply that does not parse, or that ends at the token
limit, is a parse failure: it is retried once with the sample's seed plus
1,000, and if it fails again the item has no label from that rater. As in
every report so far, a missing label counts as not accepted, not c and not
present.

### Samples

Per model and item, four samples:

- three at temperature 0.7, top-p 1, no top-k, with seeds 1, 2 and 3 (the
  same seed for every item), which make three raters per family, as the
  Claude panel had three per model;
- one greedy sample (temperature 0), reported separately; it decides
  nothing.

The Claude raters' sampling settings were not recorded, so 0.7 is a choice,
not a match.

### Rater files

For each round, model and sample, one label file in the schema of
`eval/<round>/labels/`: a JSON list of `{"id", "label",
"construction_present", "cause"}` (unprimed files have no
`construction_present`). The files are named
`open-<family>-primed-s1.json` to `-s3.json`,
`open-<family>-primed-greedy.json`, and the same with `unprimed`. Each
model's raw replies, token counts and finish reasons go beside them, and
a run log records per model the requested and resolved revision, the vLLM
version, load and generation times, prompt, cached and output tokens, and
parse failures. Everything is uploaded to the private dataset
`arclabs561/readcost-labels` under `runs/<run-id>/`; the label files and
the run log are then committed under `eval/`.

### Batching and caching

All requests of one model go to vLLM in one call. They are sorted by
rubric and then by item, so the four samples of an item are adjacent. Prefix
caching then computes each rubric once per model and each item's prompt
once for its four samples. The models run one after another, each in its
own process, so that GPU memory is freed between them.

## Cost

### Estimate

A rubric is 3.3 to 3.6 thousand characters primed and 1.4 to 1.8 thousand
unprimed; an item as a batch file averages 800 characters (at most 2,069).
At about 4 characters a token, a primed prompt is about 1,100 tokens and an
unprimed one about 650; a reply is about 45 tokens.

Per model there are 2,625 primed and 3,166 unprimed items, 5,791 prompts,
and 23,164 requests with the four samples. With prefix caching that is
about 1.4 million prompt tokens to compute and 1.0 million tokens to
generate.

On one H200 a 30B dense model in bf16 with a few hundred requests in flight
should generate 2,000 to 4,000 tokens a second, and the MoE and 14B models
more. That is 4 to 9 minutes of generation per model, plus 5 to 10 minutes
to download and load it: 10 to 20 minutes per model and 40 to 80 minutes
for the four, or $3.50 to $7 at $5 an hour. These numbers are a guess; the
pilot measures them.

### Pilot

Before the full run, one job on `h200` runs each model on a pilot of 50
items: the first 50 of all items of the three rounds, ordered by
`random.Random("open-raters-pilot")` after sorting by round and id, each
shown primed where its round shows it primed and unprimed, with all four
samples. The pilot measures per model the load time, requests and output
tokens per second, and the parse rate. Its labels are kept in its own run
folder and are not used in any outcome; the full run labels the pilot items
again.

### Stopping and substitution

The cap for this re-rating, pilot included, is $30 of GPU time.

1. A model is replaced by the substitute (OLMo 3.1 32B Instruct) if it
   fails to load in the pilot, or if its parse rate in the pilot is under
   98% after retries. The substitute then runs its own pilot. A second failure leaves
   that family out and the panel is three families; that is reported.
2. From the pilot, the full run's cost is projected as the sum over models
   of (load time + 23,164 requests / measured requests per second) at $5 an
   hour, times 1.25. If it exceeds what remains of the $30, the greedy
   sample is dropped; if it still exceeds it, the third sampled rater is
   dropped (two per family: a family's majority is then 2 of 2, and the
   open panel's 5 of 8); if it still exceeds it, round 3's ranked
   sentences are dropped. Nothing else is cut.
3. The full run's job has a timeout of 3 hours ($15). It uploads each
   model's files as soon as that model finishes, so a timeout loses only
   the model in progress, which is then run alone in a second job if the
   cap allows.
4. A family whose parse rate in the full run is under 95% in any round is
   reported but left out of the open panel.

## Panels

| Panel | Primed raters | Majority, primed | Unprimed raters | Majority, unprimed |
| --- | --- | --- | --- | --- |
| Claude (as before) | 12 | 7 | 3 | 2 |
| Open | 12 (3 per family) | 7 | 12 | 7 |
| Claude and open | 24 | 13 | 15 | 8 |
| One family | 3 | 2 | 3 | 2 |
| Open, greedy (separate) | 4 | 3 | 4 | 3 |

A majority is more than half; six of twelve is not one. If a family is left
out, the open panel has nine raters and its majority is 5.

## Outcomes

For each panel above and each round, `scripts/open_raters_report.py`
recomputes the round's pre-registered tables and decisions with the
round's own analysis code, with the panel's raters and majorities in place
of the Claude panel's:

- round 1: the S1 and S2 tables of `scripts/heldout_report.py`, with the
  decoy kinds, and the decisions of its plan;
- round 2: the tables and decisions of `scripts/breadth_report.py`;
- round 3: the tables and decisions of `scripts/kinds_report.py`, the
  ranking test (part A) and the defaults across rounds (part B).

Agreement, per round and pooled, on findings:

- Fleiss' kappa (accepted against not, and over c, d and w) within each
  family's three raters, within the open panel, and over the Claude
  twelve with each family's three;
- Cohen's kappa between the Claude panel's majority and each family's
  majority, and between the Claude panel's majority and the open panel's,
  for accepted (primed) and for c-or-d (unprimed).

## Questions and decision rules

Each question is answered with the open panel alone, because the question
is whether a result depends on Claude. The combined panel and each family
are reported beside it and decide nothing. Intervals are 95%: Wilson for a
share, Newcombe's hybrid score interval for a difference between
independent shares, and a paired bootstrap over items (2,000 resamples,
seed 0, percentile) for a difference measured on the same items. "Beats"
means the lower bound of the difference is above zero.

### Q1. Does the priming effect replicate outside Claude?

For each rule, over the findings of rounds 1 to 3 (round 3: technical
kinds), the share the primed majority accepts minus the share the unprimed
majority labels c or d, with the paired bootstrap interval. The Claude
panel's difference is computed the same way.

- The effect replicates for a rule if the open panel's difference is above
  zero (lower bound above zero).
- It replicates outside Claude if it does so pooled over all rules and for
  at least half of the rules for which the Claude panel's difference is
  above zero.
- It does not replicate if the pooled difference's interval contains zero
  or lies below it.
- Anything between is reported as partial, with the rules named.

### Q2. Is center-embedding still the only rule that beats the longest sentence unprimed?

Primary: round 3, technical kinds. For each rule, the share of its findings
the unprimed majority labels c or d minus that share for the sentences
ranked "longest", Newcombe interval. Secondary, decides nothing: round 1,
findings against the D-long decoys, S1 and S2 together.

- Yes, if center-embedding beats the longest sentence and no other rule
  does.
- If another rule also beats it, that rule is named as a candidate for the
  same test that #107 passed, and nothing changes until a later plan tests
  it.
- If center-embedding does not beat it, see Q5.

### Q3. Do inanimate-subject, participial-clause and nominalization still fail the stricter test?

The stricter test is the one the departure recorded in evaluation.md used
in round 3: the findings beat the longest sentence unprimed, as in Q2.
Each of the three still fails it if the lower bound is at or below zero. A
rule that passes it is proposed again for the decision of the plan's part B,
which then needs both of part B's criteria from the open panel too.

### Q4. Does the composite ranking still not beat the longest sentence?

Round 3's ranking test (part A of kinds-precision.md) with the open
unprimed panel: the composite's pick minus the longest sentence, Newcombe
interval, technical kinds. It still does not beat it if the lower bound is
at or below zero. If it beats it, the composite is proposed as a ranking
again, and a new plan decides.

### Q5. What would reverse #107 or #98?

#107 (center-embedding on by default) rests on three results: its findings
beat its near misses (primed accepted, rounds 2 and 3), beat random decoys
unprimed (rounds 1 to 3), and beat the longest sentence unprimed (round
3). With the open panel:

- if it fails at least two of the three, turning it off by default is
  proposed;
- if it fails exactly one, the disagreement is recorded and the default
  stays.

#98 (inanimate-subject opt-in) rests on its findings being accepted by
almost no primed rater (0 of 40 on READMEs, upper bound 9%). With the open
panel, pooled over rounds 1 to 3:

- if the primed majority accepts its findings with a lower bound above 25%,
  and its findings also beat the longest sentence unprimed (Q3), turning it
  back on is proposed;
- if only the first holds, the open models accept it where Claude did not;
  that is recorded and it stays opt-in, because acceptance under priming is
  the measure that Q1 calls into question.

Any proposal goes to a separate pull request with the evidence. This plan
changes no default.

### Families against Claude

Not a decision: for each family, the share of findings per rule its
majority accepts beside the Claude panel's, and Cohen's kappa against the
Claude majority. A family whose kappa against Claude is below 0.20 on
findings, pooled, is named; so is any family whose primed majority accepts
more than 25% of random decoys, which would mean it accepts whatever it is
shown.

## What this cannot show

- These are still models. Agreement between Claude and other families
  shows that a result does not depend on one family; it does not show that
  readers pay a cost.
- The open models are smaller than Opus and Sonnet. A disagreement may come
  from a weaker rater and not from a family's bias; the per-family tables
  and the kappas help tell these apart, but cannot settle it.
- One item per request differs from batches of 25. If the open panel
  differs from Claude, part of the difference may be the batch size.
- Structured outputs guarantee the format, and may also change which label
  a model picks.

## What the report contains

`eval/open-raters/report.md`: the run's models, revisions, vLLM version,
token counts and cost; parse failures per model and round; for each round
and panel the tables named under "Outcomes"; the agreement tables; the
answers to Q1 to Q5 with their numbers; and the greedy panel's main table,
marked as deciding nothing.

## Amendments

### 19 November 2026, while writing the job script, before any model call

- Images are turned off with vLLM's `language_model_only=True` and not
  with `limit_mm_per_prompt={"image": 0}`. vLLM documents the option as
  the same as a limit of 0 for every modality, so it also covers Qwen's
  video input.
- Round 2 holds one item twice (id 768685). It counts once in every
  panel's round 2 tables, as part B of kinds-precision.md counts it.
- The GPU job does not rebuild the item texts. Rebuilding runs readcost
  at three commits over hundreds of repositories. On the GPU, that time is
  billed at the GPU's rate. The items are put in the private dataset at
  `items/` first, by `scripts/rebuild_items.py` in a CPU job or from the
  label store, and the GPU job reads them from there. The job records
  their SHA-256, so the two sources can be compared.
