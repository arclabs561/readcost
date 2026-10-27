# Large-scale evidence for logarithmic effects of word predictability on reading time

Cory Shain, Clara Meister, Tiago Pimentel, Ryan Cotterell, Roger P. Levy.
2024. PNAS 121(10), e2307876121. DOI
[10.1073/pnas.2307876121](https://doi.org/10.1073/pnas.2307876121); open
access (CC BY 4.0), PMC10927576.

Read: full main text (PMC full-text XML: introduction, results,
discussion, materials and methods). The 15-section SI appendix was not
read (results by dataset, control predictors, CDRNN details). Title and
authors match.

## Claim

Across six English reading datasets and five language models, reading
times are linear in surprisal (logarithmic in predictability), not linear
in probability and not reliably super-logarithmic. GPT-2 small fits
reading times better than n-gram, PCFG, GPT-J and GPT-3, and at least as
well as human cloze norms on Provo.

## Method and data

- Brown SPR, Dundee ET, GECO ET (14 English monolinguals), Natural Stories
  SPR and Maze, Provo ET; over 2.2 million data points. Splits by
  (sentence + participant) mod 4 into 50/25/25.
- Measures: scan path, first pass and go-past durations; self-paced and
  Maze reaction times.
- Continuous-time deconvolutional regressive neural networks (CDRNN),
  ex-Gaussian response, ensembles of 10, paired permutation tests on
  held-out likelihood; models constrained to probability or surprisal^k
  (k = 1/2 to 2) vs unconstrained.

## Results (numbers that matter)

- Linear-in-probability models underperform all surprisal models;
  surprisal^1 is the best constrained model; the unconstrained model does
  not beat it.
- Natural Stories SPR and the larger LMs lean super-logarithmic, which
  the authors attribute to that dataset and possible training-data
  contamination of GPT-3.
- On Provo, GPT-2 surprisal numerically beats cloze surprisal in every
  comparison, significantly for first pass and go-past.

## What the full text qualifies

- The authors stress that surprisal is not the only determinant;
  frequency, priming, dependency locality and garden paths have
  independent effects.
- Near-equivalence across sub- to super-logarithmic forms means a weak UID
  pressure cannot be ruled out.

## For readcost (used / tested / candidate)

Not cited. Bearing on the reading-time model and "Model signals":

- If readcost adds surprisal it should be a linear term in surprisal from
  a small model (GPT-2 small sized); readcost's SmolLM2-135M is that size.
  readcost's finding that surprisal hurt Provo is at odds with this paper
  finding GPT-2 surprisal strongly predictive on Provo; see the Tsipidi
  2026 note for candidate causes.
- Against using surprisal variance (UID) as a cost signal; consistent
  with Smith and Levy 2013.
- Dependency locality is named as a surprisal-independent cost, which
  supports keeping long-dependency separate from any surprisal feature.

## Open questions

None beyond those above.
