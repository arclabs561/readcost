# Why Does Surprisal From Larger Transformer-Based Language Models Provide a Poorer Fit to Human Reading Times?

Byung-Doh Oh, William Schuler. 2023. TACL 11; arXiv
[2212.12131](https://arxiv.org/abs/2212.12131) (v1).

Read: full (body and discussion; no appendix). Title and authors match.
Figures are plots; the text states the directions.

## Claim

Within GPT-2, GPT-Neo and OPT, larger models with lower perplexity give
surprisal that fits self-paced reading (Natural Stories) and go-past eye
durations (Dundee) worse, with a log-linear relation between perplexity
and fit. The loss comes mostly from larger models assigning low surprisal
to nouns, adjectives and especially named entities, so the regression
underpredicts reading times there.

## Method and data

- Natural Stories (181 readers, 770,102 observations after filtering) and
  Dundee (10 readers, 195,507), split into exploratory and held-out halves;
  sentence-initial and final words excluded; log reading times.
- 17 models from 124M to 66B parameters. Mixed-effects models with word
  length, position, and (eye tracking) saccade length and previous-word
  fixation as baseline; Delta log-likelihood.
- Residual analysis by part of speech, named entity, DLT cost (nouns and
  finite verbs as referents), left-corner center-embedding.

## Results (numbers that matter)

- The smallest variant of each family fits best; larger fits strictly
  worse; regression slopes of fit on log perplexity significant in 5 of 6
  family-by-corpus cases.
- Named entities are the top subset driving the trend in all
  combinations; nouns and adjectives get average surprisal more than 2
  bits lower from the largest than the smallest models.
- Also identified: words with DLT cost of 3 or more (underpredicted in
  Natural Stories with OPT) and ends of center-embedded constituents of 4
  or more words.

## What the full text qualifies

Reading times are log-transformed, sentence edges dropped; the analysis
is of fit, not of prediction error in milliseconds.

## For readcost (used / tested / candidate)

Not cited. Bearing:

- Supports readcost's choice of a small model (SmolLM2-135M) when it tests
  surprisal, and supports not shipping a large one.
- Long-dependency: words that close dependencies with DLT cost 3 or more
  and ends of long center-embedded constituents are where surprisal
  underpredicts reading times. That is independent evidence that a
  locality feature adds information beyond surprisal at the closing word,
  which is where readcost's long-dependency rule points.
- Named entities: readers slow on them more than LMs predict; readcost's
  lexical model uses frequency, which already treats rare names as slow.

## Open questions

None specific.
