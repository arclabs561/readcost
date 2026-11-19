# Re-rating with open models: results

Computed by `scripts/open_raters_report.py` as `docs/prereg/open-family-raters.md` fixes it. The questions are answered with the open panel alone; the other panels are in the folders beside this file and decide nothing.

Run `full-20261119` on Hugging Face Jobs (one H200, vLLM 0.34.0). The label files and the per-panel round reports are in the private dataset `arclabs561/readcost-labels`, under `runs/full-20261119/` and `reports/full-20261119/`; this file is a copy of `reports/full-20261119/report.md`.

Open panel: qwen, gemma, glm, mistral.

## Coverage

Lowest share of expected items each family's sampled raters labelled. Round 1 is 98% because 12 of its 597 items could not be rebuilt (their repositories are gone).

| Family | round1 primed | round1 unprimed | round2 primed | round2 unprimed | round3 primed | round3 unprimed |
| --- | --- | --- | --- | --- | --- | --- |
| qwen | 98% | 98% | 100% | 100% | 100% | 100% |
| gemma | 98% | 98% | 100% | 100% | 100% | 100% |
| glm | 98% | 98% | 100% | 100% | 100% | 100% |
| mistral | 98% | 98% | 100% | 100% | 100% | 100% |

## Q1. Priming: primed accepted minus unprimed c or d, findings of rounds 1 to 3

| Rule | Open | Claude |
| --- | --- | --- |
| stacked-nouns | +15 points (+8 to +23) | +19 points (+12 to +25) |
| long-dependency | -4 points (-11 to +4) | -2 points (-10 to +6) |
| reduced-object-relative | -29 points (-37 to -21) | +2 points (-5 to +10) |
| hyphen-compound | +13 points (+5 to +20) | +26 points (+19 to +34) |
| inline-list | +25 points (+16 to +33) | -2 points (-8 to +4) |
| inanimate-subject | -39 points (-49 to -31) | -25 points (-33 to -18) |
| participial-clause | +68 points (+57 to +77) | +27 points (+17 to +37) |
| nominalization | +44 points (+31 to +58) | +38 points (+25 to +52) |
| center-embedding | -66 points (-76 to -55) | -22 points (-36 to -11) |
| undefined-acronym | +27 points (+16 to +38) | -6 points (-16 to +4) |
| all rules | +5 points (+2 to +8) | +7 points (+4 to +9) |

Answer: replicates (rules where it replicates among those where Claude's does: stacked-nouns, hyphen-compound, participial-clause, nominalization).

## Q2 and Q3. Unprimed findings against the longest sentence

Round 3, technical kinds: the longest sentences are a problem (c or d) to the open panel in 126 of 192 (66%; 59% to 72%). Round 1's long decoys: 17 of 60 (28%; 19% to 41%).

| Rule | Round 3 findings | Minus longest | Round 1 findings | Minus long decoys (secondary) |
| --- | --- | --- | --- | --- |
| stacked-nouns | 41 of 120 (34%; 26% to 43%) | -31 points (-42 to -20) | 15 of 60 (25%; 16% to 37%) | -3 points (-19 to +12) |
| long-dependency | 69 of 119 (58%; 49% to 66%) | -8 points (-19 to +3) | 38 of 60 (63%; 51% to 74%) | +35 points (+17 to +50) |
| reduced-object-relative | 77 of 116 (66%; 57% to 74%) | +1 points (-10 to +11) | 45 of 60 (75%; 63% to 84%) | +47 points (+29 to +60) |
| hyphen-compound | 31 of 120 (26%; 19% to 34%) | -40 points (-49 to -29) | 17 of 60 (28%; 19% to 41%) | +0 points (-16 to +16) |
| inline-list | 41 of 96 (43%; 33% to 53%) | -23 points (-34 to -11) | 20 of 60 (33%; 23% to 46%) | +5 points (-11 to +21) |
| inanimate-subject | 16 of 40 (40%; 26% to 55%) | -26 points (-41 to -9) | 31 of 60 (52%; 39% to 64%) | +23 points (+6 to +39) |
| participial-clause | 9 of 40 (22%; 12% to 38%) | -43 points (-55 to -27) | 5 of 30 (17%; 7% to 34%) | -12 points (-27 to +8) |
| nominalization | 18 of 35 (51%; 36% to 67%) | -14 points (-31 to +3) | 6 of 27 (22%; 11% to 41%) | -6 points (-23 to +15) |
| center-embedding | 13 of 16 (81%; 57% to 93%) | +16 points (-9 to +30) | 23 of 30 (77%; 59% to 88%) | +48 points (+27 to +63) |
| undefined-acronym | 8 of 40 (20%; 10% to 35%) | -46 points (-57 to -29) | 5 of 30 (17%; 7% to 34%) | -12 points (-27 to +8) |

Q2: no: center-embedding does not beat it (rules that beat it: none).
Q3: inanimate-subject still fails; participial-clause still fails; nominalization still fails.

## Q4. Ranking

Composite minus longest: +1 points (-9 to +10). The composite still does not beat it.

## Q5. #107 and #98

#107 (center-embedding default): fails over near misses, over the longest sentence, unprimed; propose turning it off by default.

#98 (inanimate-subject opt-in): accepted primed in 7 of 142 (5%; 2% to 10%); beats the longest sentence: no; stands.

## Agreement on findings

| Family | Round | n | Fleiss accepted, within | Fleiss c/d/w, within | Fleiss accepted, with Claude's 12 | Cohen vs Claude, primed | Cohen vs Claude, unprimed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| qwen | 1 | 477 | 0.43 | 0.38 | 0.46 | 0.44 | 0.48 |
| qwen | 2 | 654 | 0.38 | 0.35 | 0.37 | 0.32 | 0.44 |
| qwen | 3 | 742 | 0.41 | 0.36 | 0.40 | 0.41 | 0.52 |
| qwen | pooled | 1873 | 0.41 | 0.36 | 0.41 | 0.39 | 0.49 |
| gemma | 1 | 477 | 0.96 | 0.90 | 0.53 | 0.63 | 0.49 |
| gemma | 2 | 654 | 0.93 | 0.87 | 0.43 | 0.45 | 0.46 |
| gemma | 3 | 742 | 0.91 | 0.87 | 0.46 | 0.60 | 0.45 |
| gemma | pooled | 1873 | 0.93 | 0.88 | 0.47 | 0.56 | 0.46 |
| glm | 1 | 477 | 0.16 | 0.11 | 0.35 | 0.13 | 0.26 |
| glm | 2 | 654 | 0.20 | 0.15 | 0.26 | 0.01 | 0.14 |
| glm | 3 | 742 | 0.18 | 0.14 | 0.29 | 0.08 | 0.18 |
| glm | pooled | 1873 | 0.19 | 0.14 | 0.30 | 0.06 | 0.18 |
| mistral | 1 | 477 | 0.45 | 0.30 | 0.41 | 0.24 | 0.16 |
| mistral | 2 | 654 | 0.40 | 0.29 | 0.32 | 0.08 | 0.05 |
| mistral | 3 | 742 | 0.38 | 0.29 | 0.33 | 0.17 | 0.09 |
| mistral | pooled | 1873 | 0.41 | 0.30 | 0.35 | 0.15 | 0.09 |
| open | 1 | 477 | 0.27 | 0.19 | 0.34 | 0.57 | 0.51 |
| open | 2 | 654 | 0.24 | 0.19 | 0.26 | 0.32 | 0.46 |
| open | 3 | 742 | 0.24 | 0.18 | 0.29 | 0.47 | 0.45 |
| open | pooled | 1873 | 0.25 | 0.18 | 0.29 | 0.44 | 0.47 |

## Families against Claude

| Rule | Claude | qwen | gemma | glm | mistral |
| --- | --- | --- | --- | --- | --- |
| stacked-nouns | 38% | 40% | 43% | 72% | 70% |
| long-dependency | 38% | 67% | 33% | 80% | 65% |
| reduced-object-relative | 44% | 43% | 49% | 68% | 18% |
| hyphen-compound | 45% | 29% | 35% | 56% | 59% |
| inline-list | 23% | 60% | 45% | 90% | 70% |
| inanimate-subject | 4% | 17% | 9% | 59% | 7% |
| participial-clause | 48% | 71% | 81% | 83% | 59% |
| nominalization | 75% | 79% | 80% | 88% | 99% |
| center-embedding | 45% | 32% | 7% | 32% | 11% |
| undefined-acronym | 18% | 32% | 40% | 38% | 79% |

Shares of findings (rounds 1 to 3) each panel's majority accepts, primed. Random decoys accepted: claude 1 of 261 (0%; 0% to 2%), qwen 5 of 261 (2%; 1% to 4%), gemma 2 of 261 (1%; 0% to 3%), glm 120 of 261 (46%; 40% to 52%), mistral 29 of 261 (11%; 8% to 16%).

Named under the plan: glm: Cohen's kappa against Claude 0.06; mistral: Cohen's kappa against Claude 0.15; glm: accepts 46% of random decoys.
