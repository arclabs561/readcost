# Held-out precision: results

Computed by `scripts/heldout_report.py` as `docs/prereg/heldout-precision.md` fixes it.

## S1, READMEs (primary)

320 findings and 80 decoys.

| Rule | n | Accepted (majority c or d) | Over decoys, points | Present (majority) |
| --- | --- | --- | --- | --- |
| stacked-nouns | 40 | 22 of 40 (55%; 40% to 69%) | +55 (+39 to +69) | 29 of 40 (72%; 57% to 84%) |
| long-dependency | 40 | 15 of 40 (38%; 24% to 53%) | +38 (+23 to +53) | 16 of 40 (40%; 26% to 55%) |
| inanimate-subject | 40 | 0 of 40 (0%; 0% to 9%) | +0 (-5 to +9) | 9 of 40 (22%; 12% to 38%) |
| reduced-object-relative | 40 | 8 of 40 (20%; 10% to 35%) | +20 (+9 to +35) | 25 of 40 (62%; 47% to 76%) |
| hyphen-compound | 40 | 14 of 40 (35%; 22% to 50%) | +35 (+21 to +50) | 34 of 40 (85%; 71% to 93%) |
| inline-list | 40 | 8 of 40 (20%; 10% to 35%) | +20 (+9 to +35) | 24 of 40 (60%; 45% to 74%) |
| participial-clause | 20 | 15 of 20 (75%; 53% to 89%) | +75 (+53 to +89) | 19 of 20 (95%; 76% to 99%) |
| nominalization | 20 | 16 of 20 (80%; 58% to 92%) | +80 (+58 to +92) | 20 of 20 (100%; 84% to 100%) |
| center-embedding | 20 | 2 of 20 (10%; 3% to 30%) | +10 (+1 to +30) | 2 of 20 (10%; 3% to 30%) |
| undefined-acronym | 20 | 2 of 20 (10%; 3% to 30%) | +10 (+1 to +30) | 19 of 20 (95%; 76% to 99%) |

Decoy baseline:

| Decoys | Accepted | Present |
| --- | --- | --- |
| all | 0 of 80 (0%; 0% to 5%) | 1 of 80 (1%; 0% to 7%) |
| D-random | 0 of 40 (0%; 0% to 9%) | 1 of 40 (2%; 0% to 13%) |
| D-long | 0 of 40 (0%; 0% to 9%) | 0 of 40 (0%; 0% to 9%) |

Decoys by the rule name they were given (small n; decides nothing): stacked-nouns 0/8, long-dependency 0/8, inanimate-subject 0/8, reduced-object-relative 0/8, hyphen-compound 0/8, inline-list 0/8, participial-clause 0/8, nominalization 0/8, center-embedding 0/8, undefined-acronym 0/8.

Rater counts (c / d / w / missing) and agreement among the three:

| Rule | Rater 1 | Rater 2 | Rater 3 | Fleiss c/d/w | Fleiss accepted | Fleiss present | Pairwise agreement, accepted |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | 0 / 22 / 18 / 0 | 0 / 26 / 14 / 0 | 0 / 16 / 24 / 0 | 0.67 | 0.67 | 0.96 | 83% |
| long-dependency | 3 / 11 / 26 / 0 | 3 / 11 / 26 / 0 | 4 / 13 / 23 / 0 | 0.84 | 0.86 | 0.90 | 93% |
| inanimate-subject | 0 / 2 / 38 / 0 | 0 / 1 / 39 / 0 | 0 / 0 / 40 / 0 | -0.03 | -0.03 | 0.50 | 95% |
| reduced-object-relative | 1 / 3 / 36 / 0 | 0 / 22 / 18 / 0 | 1 / 6 / 33 / 0 | 0.18 | 0.21 | 0.96 | 68% |
| hyphen-compound | 1 / 12 / 27 / 0 | 2 / 27 / 11 / 0 | 1 / 9 / 30 / 0 | 0.29 | 0.32 | 0.94 | 67% |
| inline-list | 0 / 8 / 32 / 0 | 0 / 23 / 17 / 0 | 0 / 5 / 35 / 0 | 0.29 | 0.29 | 0.97 | 70% |
| participial-clause | 0 / 15 / 5 / 0 | 0 / 19 / 1 / 0 | 0 / 5 / 15 / 0 | -0.03 | -0.03 | 1.00 | 53% |
| nominalization | 0 / 15 / 5 / 0 | 2 / 16 / 2 / 0 | 0 / 15 / 5 / 0 | 0.55 | 0.58 | -0.02 | 87% |
| center-embedding | 1 / 2 / 17 / 0 | 1 / 1 / 18 / 0 | 0 / 2 / 18 / 0 | 0.53 | 0.51 | 0.51 | 90% |
| undefined-acronym | 0 / 3 / 17 / 0 | 0 / 3 / 17 / 0 | 0 / 1 / 19 / 0 | 0.51 | 0.51 | 0.07 | 90% |
| all findings | | | | 0.54 | 0.55 | 0.88 | 80% |

Default rules together, weighted by each rule's share of the stratum's findings: 30% accepted (bootstrap 95%: 23% to 38%).

## S2, docs files (secondary; decides nothing)

157 findings and 40 decoys.

| Rule | n | Accepted (majority c or d) | Over decoys, points | Present (majority) |
| --- | --- | --- | --- | --- |
| stacked-nouns | 20 | 14 of 20 (70%; 48% to 85%) | +70 (+46 to +85) | 18 of 20 (90%; 70% to 97%) |
| long-dependency | 20 | 6 of 20 (30%; 15% to 52%) | +30 (+12 to +52) | 6 of 20 (30%; 15% to 52%) |
| inanimate-subject | 20 | 1 of 20 (5%; 1% to 24%) | +5 (-5 to +24) | 9 of 20 (45%; 26% to 66%) |
| reduced-object-relative | 20 | 11 of 20 (55%; 34% to 74%) | +55 (+32 to +74) | 14 of 20 (70%; 48% to 85%) |
| hyphen-compound | 20 | 13 of 20 (65%; 43% to 82%) | +65 (+42 to +82) | 18 of 20 (90%; 70% to 97%) |
| inline-list | 20 | 9 of 20 (45%; 26% to 66%) | +45 (+24 to +66) | 14 of 20 (70%; 48% to 85%) |
| participial-clause | 10 | 6 of 10 (60%; 31% to 83%) | +60 (+30 to +83) | 10 of 10 (100%; 72% to 100%) |
| nominalization | 7 | 1 of 7 (14%; 3% to 51%) | +14 (-0 to +51) | 4 of 7 (57%; 25% to 84%) |
| center-embedding | 10 | 8 of 10 (80%; 49% to 94%) | +80 (+48 to +94) | 8 of 10 (80%; 49% to 94%) |
| undefined-acronym | 10 | 1 of 10 (10%; 2% to 40%) | +10 (-2 to +40) | 9 of 10 (90%; 60% to 98%) |

Decoy baseline:

| Decoys | Accepted | Present |
| --- | --- | --- |
| all | 0 of 40 (0%; 0% to 9%) | 1 of 40 (2%; 0% to 13%) |
| D-random | 0 of 20 (0%; 0% to 16%) | 1 of 20 (5%; 1% to 24%) |
| D-long | 0 of 20 (0%; 0% to 16%) | 0 of 20 (0%; 0% to 16%) |

Decoys by the rule name they were given (small n; decides nothing): stacked-nouns 0/4, long-dependency 0/4, inanimate-subject 0/4, reduced-object-relative 0/4, hyphen-compound 0/4, inline-list 0/4, participial-clause 0/4, nominalization 0/4, center-embedding 0/4, undefined-acronym 0/4.

Rater counts (c / d / w / missing) and agreement among the three:

| Rule | Rater 1 | Rater 2 | Rater 3 | Fleiss c/d/w | Fleiss accepted | Fleiss present | Pairwise agreement, accepted |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | 3 / 10 / 7 / 0 | 2 / 14 / 4 / 0 | 1 / 10 / 9 / 0 | 0.52 | 0.55 | 0.71 | 80% |
| long-dependency | 3 / 4 / 13 / 0 | 3 / 3 / 14 / 0 | 4 / 2 / 14 / 0 | 0.72 | 0.92 | 0.92 | 97% |
| inanimate-subject | 0 / 1 / 19 / 0 | 0 / 4 / 16 / 0 | 0 / 1 / 19 / 0 | 0.07 | 0.07 | 0.52 | 83% |
| reduced-object-relative | 1 / 9 / 10 / 0 | 3 / 10 / 7 / 0 | 6 / 4 / 10 / 0 | 0.52 | 0.73 | 1.00 | 87% |
| hyphen-compound | 0 / 13 / 7 / 0 | 0 / 16 / 4 / 0 | 0 / 10 / 10 / 0 | 0.56 | 0.56 | 1.00 | 80% |
| inline-list | 0 / 9 / 11 / 0 | 0 / 14 / 6 / 0 | 0 / 5 / 15 / 0 | 0.40 | 0.40 | 0.92 | 70% |
| participial-clause | 1 / 5 / 4 / 0 | 1 / 9 / 0 / 0 | 1 / 2 / 7 / 0 | 0.18 | -0.00 | n/a | 53% |
| nominalization | 0 / 2 / 5 / 0 | 0 / 3 / 4 / 0 | 0 / 1 / 6 / 0 | 0.30 | 0.30 | 0.81 | 71% |
| center-embedding | 6 / 2 / 2 / 0 | 5 / 2 / 3 / 0 | 6 / 2 / 2 / 0 | 0.60 | 0.81 | 0.81 | 93% |
| undefined-acronym | 0 / 1 / 9 / 0 | 0 / 2 / 8 / 0 | 0 / 0 / 10 / 0 | 0.26 | 0.26 | 1.00 | 87% |
| all findings | | | | 0.58 | 0.62 | 0.87 | 81% |

Default rules together, weighted by each rule's share of the stratum's findings: 49% accepted (bootstrap 95%: 39% to 59%).

## Against rater 1 in-sample (S1, default rules)

Each held-out rater's own c-or-d share against rater 1's on the 210 in-sample findings, with Newcombe 95% intervals for the difference.

| Rule | In-sample | Rater 1 | Rater 2 | Rater 3 | Reading |
| --- | --- | --- | --- | --- | --- |
| stacked-nouns | 7/31 | 22/40, +32 (+9 to +51) | 26/40, +42 (+19 to +59) | 16/40, +17 (-5 to +36) | no clear difference |
| long-dependency | 9/32 | 14/40, +7 (-15 to +27) | 14/40, +7 (-15 to +27) | 17/40, +14 (-8 to +34) | no clear difference |
| inanimate-subject | 7/32 | 2/40, -17 (-34 to -1) | 1/40, -19 (-36 to -4) | 0/40, -22 (-39 to -8) | lower |
| reduced-object-relative | 1/32 | 4/40, +7 (-7 to +20) | 22/40, +52 (+32 to +66) | 7/40, +14 (-1 to +29) | no clear difference |
| hyphen-compound | 4/19 | 13/40, +11 (-14 to +31) | 29/40, +51 (+24 to +68) | 10/40, +4 (-21 to +24) | no clear difference |
| inline-list | 4/32 | 8/40, +8 (-11 to +24) | 23/40, +45 (+23 to +61) | 5/40, +0 (-17 to +16) | no clear difference |

## Decisions (S1)

- inanimate-subject: proposed for opt-in (accepted upper bound 9%)
- inanimate-subject: detection problem, not a cost problem (present upper bound 38%: look at the detector)
- inanimate-subject: not distinguishable from chance placement (accepted share over decoys +0 points (-5 to +9))
- participial-clause: candidate for more testing as a default (accepted lower bound 53%)
- nominalization: candidate for more testing as a default (accepted lower bound 58%)
- center-embedding: detection problem, not a cost problem (present upper bound 30%: look at the detector)
