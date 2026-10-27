# Commit Message Matters: Investigating Impact and Evolution of Commit Message Quality

Jiawei Li, Iftekhar Ahmed. 2023. ICSE 2023 (45th International Conference
on Software Engineering). https://doi.org/10.1109/ICSE48619.2023.00076
(author copy: https://stairs.ics.uci.edu/papers/2023/Commit_Messages.pdf)

Read: full (author PDF from the STAIRS lab page, 12 pages; title and
authors checked). All sections read. Tables II to VII and Figures 3 to 5
extracted poorly; values below come from the text.

## Claim

Tian et al.'s labels count a linked issue or pull request as a "why"; about
15 percent of those links do not supply one. With relabeled data, a
classifier finds that the what/why quality of earlier commit messages is
associated with whether a later commit introduces a defect, more strongly
than message length is, and that message quality in 32 Apache Java
projects declines over time while developers believe theirs improves.

## Method and data

- Relabeled the 611 messages with links from Tian et al.'s 1,597 (two
  authors, Cohen's kappa 0.95): 89 (14.6 percent) had been wrongly marked
  as having a why. Most common link problem: the linked page repeats the
  message (59 cases).
- Classifier: link titles substituted into messages, BERT embeddings,
  ensemble of BiLSTM, BiGRU and others by majority vote; ten-fold
  cross-validation; up to 12 points better F1 on why than Tian et al.'s
  model.
- Defect analysis: SZZ on 238k commits from 17 of the 32 projects (the
  tool did not finish on the rest in two months); refactoring and bot
  commits removed, leaving 91,926. For each commit, the share of the
  previous N commits (N from 5 to 1,000) whose messages have what, why or
  both; Welch's t-test and Cohen's d between defect-introducing and other
  commits; Poisson regressions with one predictor each.
- Evolution: weekly share of good messages over 246,735 commits, first 415
  weeks, Spearman correlation with week number.
- 13 interviews and a survey of 2,657 contributors (93 responses, 3.5
  percent).

## Results (numbers that matter)

- Earlier-message quality differs significantly between defect-introducing
  and other commits at every window size; the file-level effect sizes are
  described as small.
- Each single-predictor Poisson model has McFadden adjusted R squared below
  0.002. The comparison with message length rests on regression
  coefficients and t-tests over window sizes.
- Spearman correlation of weekly quality with time: what -0.80, why -0.43,
  good -0.80. The weekly share of messages with a why stays around 0.95.
- 61.9 percent of survey respondents say they write the why more over
  time.

## What the full text qualifies

- The defect association is statistically significant but explains almost
  none of the variance (R squared below 0.002), and the design is
  observational: earlier messages in a window, not the message of the
  defect-introducing commit itself.
- Only 17 of 32 projects enter the defect analysis; all are Apache Java
  projects with contribution guidelines.
- Why information remains present in about 95 percent of weekly messages
  in these projects, so the decline is mainly in what.
- Like Tian et al., the study is about content, not sentence construction.

## For readcost (used, with a caution)

- Cited in docs/research.md line 64 with Tian et al. 2022 for the
  commit-body context: "a missing 'why' is the main quality signal". This
  paper slightly undercuts that phrasing. In its data the decline is
  steeper for what than for why, and why stays present in about 95 percent
  of weekly messages. Its contribution is that a link alone is not a why.
  Suggest citing Tian et al. for "missing why is the most common gap" and
  this paper for "a link does not supply the reason".
- As with Tian et al., the finding concerns content readcost does not
  check; it does not justify the syntax rules that run on commit bodies.
- The reference entry (research.md line 157) is accurate but shortened;
  the full title is "Commit Message Matters: Investigating Impact and
  Evolution of Commit Message Quality".

## Open questions

- Does the steep decline in what hold for projects that use squash merges,
  where the pull request title becomes the subject line?
