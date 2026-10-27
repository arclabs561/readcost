# Dependence-Aware Label Aggregation for LLM-as-a-Judge via Ising Models

Krishnakumar Balasubramanian, Aleksandr Podkopaev and Shiva Prasad
Kasiviswanathan (UC Davis; Amazon Web Services). 2026. arXiv 2601.22336
(v1, 29 Jan 2026). https://arxiv.org/abs/2601.22336

Read: main text in full (sections 1 to 5, Table 1, Figure 3) and Appendix
A (related work) and the opening of Appendix D (the EM procedure); the
proofs (Appendix E), the worked three-judge example (B), the factor-model
material (C), the simulations (F) and the prompts (G) were not read. Title
and authors match the arXiv id.

## Claim

Majority vote, weighted majority vote and Dawid-Skene all assume judges
are independent given the true label. LLM judges are not: they share
training data, architectures, prompts and failure modes. Modelling the
votes as an Ising model (pairwise couplings between judges, possibly
different for each class) gives a better aggregator, and the paper proves
that independence-based aggregators can stay strictly worse than the
Bayes rule however many judges are added.

## Method and data

Votes of K judges on binary items are modelled as a pairwise Markov random
field given the label. With couplings shared across classes, the Bayes
rule is still a weighted vote, but with weights corrected for correlation;
with class-dependent couplings, it is quadratic in the votes. Theorems 1
and 2 construct Curie-Weiss examples where each judge is individually
better than chance yet the independence-based rule keeps a constant error
rate as K grows, because correlated "wrong-mode" agreement looks like
strong evidence. Parameters are fitted by unsupervised (generalized) EM;
no gold labels are used for fitting. Experiments: six judges (Claude
Sonnet 4.5, Claude Haiku 4.5, gpt-oss-120b, Llama 4 Maverick, Llama 4
Scout, DeepSeek-R1, temperature 0) on WikiQA relevance (about 3,000
items), Jigsaw toxicity (4,000) and a CNN/DailyMail summary-consistency
set (1,100); 20 trials, accuracy against human labels.

## Results (numbers that matter)

Table 1, all six judges, largest training pool (accuracy):

| Task | Class-dependent Ising | Class-independent Ising | Weighted majority | Majority |
| --- | --- | --- | --- | --- |
| Relevance | 0.90 | 0.88 | 0.82 | 0.80 |
| Toxicity | 0.79 | 0.77 | 0.72 | 0.69 |
| Summarization | 0.68 | 0.64 | 0.61 | 0.60 |

The Ising aggregators beat weighted majority once the number of items
and judges passed a modest threshold (Figure 3); with few items the
class-dependent model, which has more parameters, is not reliably better.

## What the full text qualifies

The theory concerns the population Bayes rule under the true model; the
authors say the fitted EM procedure is not covered by the theory. The
separation theorems use stylized Curie-Weiss models chosen to make
independence fail. The real-data gains need hundreds to thousands of
items; Figure 3 starts at a few hundred training items, and fewer items
favour the simpler models. Accuracy is the only reported metric; no
calibration numbers are given in the main text despite the abstract's
emphasis on miscalibrated posteriors.

## For readcost (candidate; not cited)

docs/evaluation.md ("Ten raters") aggregates ten model raters by
majority, excluding two lenient ones, and lines 492 to 507 use the
majority's per-item verdicts to revert a rule. This paper names the
assumption behind that: majority vote is right only if raters err
independently given the truth. The readcost raters include Llama 4
Maverick, also used here; model families trained on overlapping web text
are the case the paper describes. Implications:

- The majority's agreement among raters is not evidence of correctness
  when errors are shared; eight raters agreeing a term of art is fine can
  be one shared failure counted eight times.
- An Ising or Dawid-Skene fit is not practical on 210 findings with ten
  raters (a class-dependent Ising model has 2 x (10 + 45) parameters),
  and fitting it without any human labels leaves the label direction and
  error rates unchecked. The paper's own practical advice is the cheap
  part: check residual correlation between raters after accounting for
  the label, which needs some human labels.
- The docs do not claim the majority is correct; they call no rater
  ground truth (Limits). No mismatch, but the rule revert in lines 492 to
  497 treats the majority as if its item-level votes were independent
  evidence.

## Open questions

- How strongly are readcost's model raters coupled? Pairwise agreement
  between raters, computed separately on findings a person labels correct
  and on findings a person labels wrong, would show it.
