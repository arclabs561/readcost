# Pre-registration: does repetition predict reader outcomes outside model chat text?

Written 18 November 2026, before any of the data below was analysed. The
commit that adds this file is the registration; its timestamp on GitHub is
the record. Nothing in this file changes after that commit. Any change made
later goes in a dated "Amendments" section at the end, with the reason.

## Why

Across fourteen datasets with human signals
([evaluation.md](../evaluation.md#many-datasets-with-human-signals)),
readcost's construction findings did not track ratings or reading time.
Repetition did: texts that reuse their own words, or restate an earlier
sentence, got lower coherence ratings and more complaints in five rating
sets (partial r +0.09 to +0.29 toward worse). That result came from 767
uncorrected intervals, every rated text was written by a model, and none
was technical documentation. Repetition also showed nothing in reading
times (OneStop, Provo). This test asks whether the rating result holds on
new data: technical text and text written by people, with the analysis
fixed in advance.

## What was seen before writing this

- The fourteen datasets of pull request 88 and the discourse sets of pull
  request 83, with their results. None of them is used below, except a
  held-out domain of HelpSteer3.
- For the datasets below: their cards, READMEs and file listings, to learn
  splits, column names, licences and file sizes. The Hugging Face dataset
  viewer showed two rows of the HelpSteer3 `preference` validation split
  (both in the code domain) while the schema was checked. No measure was
  computed on any row of any dataset below.

## Hypothesis

Among texts that answer the same prompt or question, a text that repeats
itself more gets a worse judgement from people than its length and words
predict. "Worse" means lower rated coherence or cohesion, less preferred,
or a lower vote score.

The direction is predicted: positive partial r, signed toward the worse
outcome. There is a known reason it could fail on human text. Cohesive,
explicit text helps readers who know little and can hurt those who know a
lot (research.md, "Discourse patterns and redundancy"), and reuse of words
is a large part of what cohesion indices count.

## Measures

Two measures, both computed by code that was already on `main` at commit
`fd778fdd89572e33705b67b5db7fea645183f45c` and unchanged since the
discovery run (pull request 88 measured with the same files):

| Name | Definition | Code |
| --- | --- | --- |
| M1, primary: share of content words already used | content-word tokens (NOUN, PROPN, VERB, ADJ, ADV, not stop words) whose lemma occurred earlier in the text, over all content-word tokens | `readcost.patterns._document_measures`, key `given_rate`, reached through `scripts/dataset_matrix.py:pattern_measures` |
| M2, secondary: restatements per 100 words | sentences with 4 or more content lemmas, 60% of which occurred together in one earlier sentence, per 100 words of checked sentences | `readcost.patterns._restatements`, counted by `pattern_measures` as `restatement` |

Both are computed by `scripts/dataset_matrix.py:features`, which also
gives the controls. The job that runs this test checks the SHA-256 of
these files and stops if any differs:

| File | SHA-256 at `fd778fd` |
| --- | --- |
| `src/readcost/patterns.py` | `f8fe7ef76b93b447760c6c563e907e9a84cbc0c9f65093c9ad72a4a9ace4728a` |
| `scripts/dataset_matrix.py` | `744b1b39efce6213ec0c14f3caed013579803778bbcefb36a4654eba0ff9625b` |
| `scripts/human_signals.py` | `eae332b59c09677d9ea12c0c762259e8416b0f763287705e9363c235663a8e03` |
| `src/readcost/readtime.py` | `d8484e6fc9564cf27a5ac4c24ffebf89d5166e3cc371b568b8255ff7cc7e8a3a` |

The parser is spaCy 3.8 with `en_core_web_sm` 3.8.0, as `uv.lock` pins it.

## Datasets, splits and outcomes

Four datasets, none used in the discovery. Text formats follow
`dataset_matrix.py`: markdown answers are checked as markdown, and code
blocks and inline code are removed before the measures are computed.

| | Dataset | Who wrote the text | Split and sample | Group | Outcome, signed toward worse |
| --- | --- | --- | --- | --- | --- |
| D1 | HelpSteer (v1), `nvidia/HelpSteer`, CC BY 4.0 | models | train and validation; responses whose text is identical to a HelpSteer2 response are dropped; whole prompts sampled with seed 0 up to 12,000 responses | prompt | coherence, 0 to 4, negated |
| D2 | HelpSteer3, `nvidia/HelpSteer3` config `preference`, code domain only, CC BY 4.0 | models, technical answers about code | train and validation, rows with `domain == "code"`; pairs whose two responses are identical are dropped; up to 6,000 pairs sampled with seed 0 | the pair | the response's own preference: `overall_preference` for response 2 and its negation for response 1 (-3 to 3), negated so that less preferred is worse |
| D3 | Stack Exchange answers, `HuggingFaceH4/stack-exchange-preferences`, CC BY-SA 4.0 | people, technical answers | the first shard (`train-00000-of-…parquet`) of each of four sites: softwareengineering.stackexchange.com, unix.stackexchange.com, serverfault.com, superuser.com; per site, up to 1,000 questions sampled with seed 0 from those with two or more eligible answers | the question | `pm_score` (log2 of 1 plus upvotes, rounded, plus 1 if accepted; -1 if net votes are negative), negated |
| D4 | ELLIPSE, `scrosseye/ELLIPSE-Corpus` at commit `710963bbf1acf23a28e40643d9f937d06f047dd4`, CC BY 4.0 (README) | people: English learners in grades 8 to 12 | `ELLIPSE_Final_github_train.csv`, every row; the password-protected test file is not used | the prompt | cohesion, the mean of two trained raters, negated |

HelpSteer3's pull request 88 run used only the General and STEM domains of
the `feedback` and `edit` configs, so the code domain is held out. D3's
answers are HTML: `<pre>`, `<code>` and `<blockquote>` elements are
removed with their content (code, and text quoted from others), other tags
are dropped, entities are unescaped, and paragraph breaks are kept at block
elements. The result is checked as plain text.

Eligibility, applied in this order:

1. A text needs at least 50 words, counted as whitespace-separated tokens
   of the prose that the measures see (after the code and quote removal
   above). In D2 both responses of a pair must qualify; in D3 only eligible
   answers count toward "two or more".
2. Sampling as in the table, on the texts that passed step 1.
3. After the features are computed, a text is dropped from a test if that
   test's measure is undefined, and a group is dropped from a test if fewer
   than two of its texts remain.

None of the four datasets ships surprisal, so surprisal is not a control.
Computing it with a language model was considered and left out: a repeated
word is more predictable, so surprisal would partly absorb the measure
being tested rather than hold a confound constant.

## Controls and model

The controls are those of the discovery: log of word count, mean word
length in letters and mean Zipf frequency of the words, from
`human_signals.lexical`.

For each dataset and measure:

1. Remove group means from the signed outcome y, the measure x and the
   three controls (texts are compared only with texts in the same group).
2. Regress y and x each on an intercept and the three controls by least
   squares, keep the residuals, and scale each to unit standard deviation.
3. The effect is the slope of residual y on residual x, which equals the
   partial Pearson r of x with y given the controls and the groups. This
   is the statistic that `dataset_matrix_report.association` reported in
   the discovery.
4. Standard error: cluster-robust (CR1) by group, SE² = G/(G-1) ·
   Σ_g (Σ_i x_i e_i)² / (Σ_i x_i²)², with e the residuals of step 3 and G
   the number of groups.
5. One-sided p = P(T ≥ r/SE), T Student's t with G-1 degrees of freedom.
6. A 95% percentile bootstrap interval over groups (2,000 resamples, seed 0)
   is reported beside it, as in the discovery, but decides nothing.

## Tests and correction

Eight tests: M1 and M2 on each of D1 to D4. Holm's step-down correction is
applied across all eight one-sided p-values at a family-wise level of 0.05.
A test that cannot be run (data unavailable, fewer than 30 texts) is
reported as not run, keeps its place in the family with p = 1, and does not
pass.

## Smallest effect that counts

Partial r = +0.05. It is about half the smallest effect of either measure
in the discovery sets (+0.10, restatement and HelpSteer3 complaints), and
explains 0.25% of the variance left after the controls. A smaller effect
would not justify a measure that readcost reports.

## Decision rules

Each test gets one of three labels:

- **pass**: Holm-adjusted one-sided p < 0.05 and r ≥ +0.05;
- **below the smallest effect**: the one-sided 95% upper bound,
  r + 1.645 · SE, is under +0.05 (this includes any effect in the opposite
  direction);
- **inconclusive**: neither.

An effect in the opposite direction whose two-sided 95% interval excludes
zero is reported as such, in words, whatever its label.

Conclusions, each decided by the primary measure M1:

| Claim | Holds if | Otherwise |
| --- | --- | --- |
| The discovery replicates on new model text | M1 passes in D1 | the result does not replicate on held-out data of the kind it came from |
| Repetition predicts reader judgements of technical text | M1 passes in D2 and in D3 | not supported for technical text |
| Repetition predicts reader judgements of human-written text | M1 passes in D3 and in D4 | not supported for human-written text |

M2 is reported in the same family and can support or qualify a claim in
words; it cannot make a claim hold when M1 does not pass.

What counts as failure: the hypothesis fails for a kind of text when M1
does not pass in both of its datasets. If M1 is below the smallest effect
in a dataset, the report says that the effect is absent there, not only
unproven. If both the technical and the human-written claims fail, the
report says plainly that repetition was not shown to predict reader
outcomes outside model chat text, and docs/research.md gets no proposal for
a document-level repetition measure.

## What the report contains

- Every one of the eight tests: n, groups, r, SE, the bootstrap interval,
  raw and Holm-adjusted p, and its label, whatever the result.
- The three claims and whether each holds.
- Anything else under the heading "Exploratory, not pre-registered", for
  example other repetition measures (overlap of neighbouring sentences,
  gzip ratio, MTLD), other outcomes in the same datasets, per-site results
  in D3, and readcost's weighted findings.

The job is `repetition-prereg` in `.github/workflows/eval.yml`, added in
the commit after this one. readcost's rules and defaults do not change.
