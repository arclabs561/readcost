# Why My Code Summarization Model Does Not Work: Code Comment Improvement with Category Prediction

Qiuyuan Chen, Xin Xia, Han Hu, David Lo, Shanping Li. 2021 (accepted
version dated November 2020). ACM Transactions on Software Engineering and
Methodology 30(2). https://doi.org/10.1145/3434280
(author copy: https://xin-xia.github.io/publication/tosem206.pdf)

Read: full (author PDF, 30 pages; title and authors checked). All sections
read, with Tables 6, 9, 10 and 13 checked in a layout-preserving
extraction.

## Claim

Method comments serve different intents, and code-summarization models do
well on some intents and badly on others. Every model does worst on "why"
comments (design rationale), because the reason for code is usually not in
the code. Picking a summarizer per predicted comment category improves
ROUGE-L by 8.6 percent relative and BLEU-4 by 16.3 percent relative.

## Method and data

- Java method/comment pairs from Hu et al.'s DeepCom dataset (9,714
  projects); 445,812 pairs for training and two 20,000-pair sets for
  validation and testing, split by project. External test set of 20,000
  pairs from 1,500 other projects.
- The 20,000 validation pairs were labeled by three coders (two authors
  and a graduate student, two to three years of Java) into Zhai et al.'s
  six categories: what, why, how-to-use, how-it-is-done, property, others.
  Open coding with discussion rounds and majority vote; Fleiss' kappa 0.79
  on the final round.
- Six summarizers (CodeNN, Code2Seq, DeepCom, NNGen, Transformer, BiLSTM)
  trained on the same data and scored per category with BLEU and ROUGE; a
  random-forest category classifier (weighted F1 about 0.77 in 10-fold
  cross-validation) picks a summarizer for each test method.

## Results (numbers that matter)

- Category shares (Table 9): how-to-use 50.95 percent, what 20.53, how it
  is done 14.14, why 12.47 (2,493 pairs), property 1.45, others 0.46.
- Before discussion the coders disagreed widely: one coder put 5,964 pairs
  in how-it-is-done where the others put about 2,000 (Table 6).
- Per category (Table 10), DeepCom ROUGE-L is 36.6 on what and 27.5 on
  why; NNGen, a retrieval method, is best on why at 29.7. Every learned
  model scores lowest or near lowest on why.
- Composite on the test set: ROUGE-L 34.98 vs 32.22 for the best single
  model; BLEU-4 19.94 vs 17.14.

## What the full text qualifies

- "Why" comments are 12.5 percent of method comments, ahead of property
  and others; the paper does not call them rare.
- The paper measures how well models reproduce reference comments, not
  how useful any comment is to a reader. Its own discussion says BLEU and
  ROUGE ignore usefulness to developers.
- Kappa 0.79 is computed after rounds of discussion and relabeling, so it
  measures consensus after negotiation, not independent agreement.
- Method-level Java comments only, median length 10 words.

## For readcost (used, with a mismatch)

- Cited in docs/research.md lines 25 to 28: rewrites keep "rationale
  clauses, which are rare and valuable in comments (Chen et al., TOSEM)".
  - "Rare": not what the paper reports. Why comments are about one in
    eight method comments.
  - "Valuable": the paper does not measure value. It shows that rationale
    is the content models cannot infer from code, which is a reason to
    protect it, but that is an inference.
  - A supported gloss: "rationale is the part of a comment that cannot be
    recovered from the code; summarization models fail on it most (Chen et
    al. 2021)."
- The reference entry (research.md lines 145 to 146) lacks a year and
  volume; TOSEM 30(2), 2021, can be added.
- The keep-the-reason rule for long-dependency and inline-list suggestions
  is consistent with the paper's finding; the paper does not test any
  rewrite.

## Open questions

- Would the category shares hold for Python docstrings or Rust doc
  comments, which tend to be longer than a one-line Javadoc summary?
