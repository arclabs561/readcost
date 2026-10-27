# Alienating the Audience: How Abbreviations Hamper Scientific Communication

Andrew H. Hales, Kipling D. Williams, Joel Rector. 2017. APS Observer 30(2),
31 January 2017.
[psychologicalscience.org/observer/alienating-the-audience-how-abbreviations-hamper-scientific-communication](https://www.psychologicalscience.org/observer/alienating-the-audience-how-abbreviations-hamper-scientific-communication)

Read: full (the Observer article, a magazine opinion piece of about 1,500
words; title and authors match). No peer-reviewed report of the experiment
it describes was found (web search for the CrossFit study and the
authors' names); the Observer piece is the only primary source.

## Claim

Abbreviations are mostly unnecessary, cost readers effort, and can make
outsiders feel excluded. Writers overestimate how familiar readers are with
them (the curse of knowledge). The authors recommend spelling
abbreviations out on every use by default.

## Method and data

One experiment, described in a paragraph: 98 college students read one of
three versions of a CrossFit recruitment message: all abbreviations spelled
out on every mention (control); abbreviations explained at first mention
only; abbreviations never explained. Measures were self-reports of basic
needs (belonging, self-esteem, control, meaningful existence), interest in
joining, and how difficult the passage was to read.

## Results (numbers that matter)

None reported: no means, test statistics or effect sizes. The article
says that as the passage became less clear, participants reported more
threat to basic needs, more reading difficulty and less interest in
joining.

## What the full text qualifies

- The evidence is a self-report trend over three conditions in one
  unpublished experiment, reported without statistics. No reading times,
  no comprehension measure.
- The pairwise comparison readcost quotes (never expanded vs expanded once)
  is not reported separately; only the ordered trend is.
- The authors treat "explained at first mention" as still less clear than
  spelling out every time, and recommend the latter, while allowing
  abbreviations that a given audience processes fluently.

## For readcost (used / tested / candidate)

Used: the opt-in undefined-acronym rule (features.py lines 153-162;
docs/research.md lines 40-41; README.md lines 185-187).

Citation accuracy:

- docs/research.md line 41, "the only evidence is self-reported
  difficulty": accurate, and features.py's "there is no reading-time
  evidence" is accurate.
- features.py lines 156-158, "Readers rated passages harder to read when
  abbreviations were never expanded than when each was expanded once":
  overstated. The article reports an ordered trend across three
  conditions with no statistics; it does not report that pairwise
  difference. It also does not support expand-once as the fix: its
  recommendation is to spell out on every use.
- README.md line 186, "which readers report as harder to read": accurate
  in kind, with the caveats above.
- The citation in docs/research.md references (APS Observer 30(2)) is
  correct; the user's guess that a PNAS or Psychological Science primary
  study exists is not supported by anything found.

## Open questions

- The evidence base for undefined-acronym is one magazine paragraph. If
  the rule stays, its explanation should say so rather than describe a
  specific contrast.
