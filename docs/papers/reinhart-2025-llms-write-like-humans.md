# Do LLMs write like humans? Variation in grammatical and rhetorical styles

Alex Reinhart, Ben Markey, Michael Laudenbach, Kachatad Pantusen, Ronald
Yurko, Gordon Weinberg, David West Brown. 2025. PNAS 122(8), e2422455122.
DOI [10.1073/pnas.2422455122](https://doi.org/10.1073/pnas.2422455122);
open access via PMC11874169 (CC BY-NC-ND 4.0).

Read: full (main text from the PMC full-text XML, and the 22-page SI
appendix from the PMC supplementary files: methods, feature definitions in
table S4, rates in table S5, effect sizes in table S6). Title and authors
match.

## Claim

Instruction-tuned models (GPT-4o, GPT-4o Mini, Llama 3 8B/70B Instruct)
write in a noun-heavy, informationally dense style that differs from human
writing in the same context, even when asked to continue a human text in
its own style. Base Llama 3 models are close to human rates, so the shift
is attributed to instruction tuning.

## Method and data

- Two parallel corpora. HAP-E: 12,000 texts from six text types
  (academic, news, fiction, podcast transcripts, blogs, TV and movie
  scripts); CAP: 1,500 texts from each of COCA's eight registers. Each text
  gives two 500-word chunks; each model continues chunk 1 for about 500
  words, compared with the human chunk 2. After dropping refusals and
  short outputs: 8,290 HAP-E and 9,615 CAP texts.
- Features: Biber's 66 features tagged with pseudobibeR on a spaCy parse,
  per 1,000 tokens. Paired Wilcoxon with Bonferroni; paired Cohen's d.
- Random forests (seven-class and pairwise) and lasso classifiers; M4
  arXiv abstracts (GPT-3.5) as an out-of-genre check.

## Results (numbers that matter)

- Present participial clauses (Biber: adverbial clauses headed by a
  present participle, "Stuffing his mouth with cookies, Joe ran out"):
  human 1.7 per 1,000 tokens; GPT-4o Mini 481%, GPT-4o 527%, Llama 8B
  Instruct 224%, 70B Instruct 261%; base models 94% and 102%. Paired d 1.37
  and 1.38 for the GPT models, 0.44 and 0.56 for Llama Instruct.
- Nominalizations (nouns ending in -tion, -ment and similar): human 14.6
  per 1,000; 209%, 214%, 145%, 151%; base 88% and 91%. d 1.18 and 1.23 for
  GPT, 0.49 and 0.59 for Llama Instruct.
- "That" clauses as subject (relative clauses in subject position) 2.6
  times, phrasal coordination 1.9 times for GPT-4o; GPT-4o uses agentless
  passives at about half the human rate.
- "That" deletion: small negative effect sizes for the instruction-tuned
  models (d -0.10 to -0.16), so they omit "that" slightly less than humans.
- Seven-way classifier 66% accurate (chance 14%); pairwise human vs one
  LLM 93 to 98%. Base-model detectors fall to chance on M4.

## What the full text qualifies

- The results are rates pooled over all text types, from paired
  continuations of the same human text. Neither the paper nor the SI
  reports feature rates per genre; the genres are there to make the corpus
  diverse.
- No claim about reading time, comprehension or difficulty. "Informationally
  dense" is a register description from corpus linguistics.
- 2024 models only (GPT-4o family, Llama 3).
- Nominalization in Biber's tagset is a suffix count. Any noun ending in
  -tion counts, with or without a light verb.

## For readcost (used / tested / candidate)

Used: the evidence for the opt-in nominalization and participial-clause
rules, and for the advice that rates should be compared within genre.
Tested: the paired rewrite test (docs/evaluation.md lines 537-540) counted
these constructions; nominalizations were found in no paragraph.

Citation accuracy:

- docs/research.md lines 30-33 and src/readcost/features.py lines 114-117
  and 124-127 ("1.5 to 2" and "2 to 5 times the human rate",
  "instruction-tuned models"): accurate (1.45 to 2.14 and 2.2 to 5.3).
- README.md lines 339-341: "Reinhart et al. 2025 compare model and human
  text within each genre for that reason." Mismatch in detail: they
  compare paired continuations of the same human text and report rates
  pooled across genres; there is no per-genre comparison. Their discussion
  does say models fail to follow genre conventions, so the advice to
  compare like with like stands, but the attribution should change.
- README.md line 183 groups participial-clause and nominalization under
  "language models use more often than people": accurate for these models.
- Scope gap, not a misquote: readcost's nominalization rule fires only
  after a light verb or on two -tion nouns joined by "of", far narrower than
  Biber's suffix count. That is why the paired test found none; readcost
  cannot claim to measure the rate Reinhart measured.
- No source here supports a reading-cost claim for either construction;
  features.py's "leaves the reader to work out its subject" is readcost's
  own reasoning.

## Open questions

- "That" deletion is slightly rarer in these models than in humans, while
  Clark et al. find reduced object relatives over-used by 2026 models.
  Different constructions and model generations; worth not merging.
