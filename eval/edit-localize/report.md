## Edit localization: readcost's findings (B) against pointing at the longest sentences (E)

A copy of `edit-localize/main-1/edit-localize.md` in the private dataset `arclabs561/readcost-labels`, where the replies (`replies.jsonl`, which start from the edit test's run `main-1b`), `run.json` and the model logs are kept. The plan is `docs/prereg/edit-localize.md`. The job ran from `892e51b` (branch `run/edit-localize`: this branch with `src/` at `a57e19e`) for 2,466 seconds. Before any model was loaded it found 358 of the edit test's 360 B and C edits in the cache; the other two were missing in `main-1b` too.

Continued draw: walked 1977 more repositories (no eligible paragraph: 1743, drawn: 140, no README: 86, repository unavailable: 8); missing at run time 0.

Paragraphs 200 (140 new). Calls 18201 in the cache (new this run 9540, served from cache 7). Phases: edits done, facts done, EB done

| Paired difference, share of edits changing content (points) | Estimate [95%] |
| --- | --- |
| **B minus E, all paragraphs (primary)** | +3.9 [-0.5, +8.4] |
| B minus C, new paragraphs | -15.1 [-20.4, -9.8] |
| B minus C, all paragraphs | -13.7 [-18.3, -9.3] |
| E minus C, all paragraphs | -17.6 [-22.2, -12.9] |
| B minus E, paragraphs where E points at B's sentences | -3.4 [-12.3, +5.6] |
| B minus E, the other paragraphs | +6.2 [+1.3, +11.3] |

| Claim | Holds |
| --- | --- |
| readcost's findings keep facts better than pointing at the longest sentences | no |
| Pointing at the longest sentences keeps facts as well as readcost's findings | yes |

B minus C on the new paragraphs repeats the edit test's finding (upper bound under 0).

| Arm | Edits checked | Share changing content [95%] | Lost | Added | Changed |
| --- | --- | --- | --- | --- | --- |
| B | 597 | 0.491 [0.453, 0.529] | 1.89 | 1.971 | 1.93 |
| C | 598 | 0.629 [0.588, 0.668] | 2.572 | 2.248 | 2.725 |
| E | 599 | 0.454 [0.413, 0.495] | 1.944 | 1.636 | 2.025 |

| Pair | Win rate of E [95%] | Label | Counts | Missing |
| --- | --- | --- | --- | --- |
| E against B | 0.431 [0.402, 0.459] | no meaningful advantage | loss 550, split 936, tie 3, win 302 | 9 |

The upper bound is under 0.50, so B did better: its win rate against E is 0.569 [0.541, 0.598].

Overlap: 0.581 of E's sentences are among B's; E points at exactly B's sentences in 49 paragraphs; sentences named per paragraph, mean 2.27. Missing edits: B 2, C 1, E 1.

| Arm | Sentences pointed at, unchanged [95%] | Other sentences, unchanged [95%] |
| --- | --- | --- |
| B | 0.042 [0.030, 0.055] | 0.183 [0.159, 0.207] |
| C | — | 0.031 [0.023, 0.039] |
| E | 0.027 [0.019, 0.036] | 0.161 [0.141, 0.183] |

| Version | n | Words over original, median | Over budget | Findings, median | mean | none |
| --- | --- | --- | --- | --- | --- | --- |
| A | 200 | 1.0 | 0 | 2.0 | 2.77 | 0.0 |
| B openai/gpt-oss-120b | 200 | 1.054 | 6 | 1.0 | 1.22 | 0.345 |
| B mistralai/Mistral-Small-4-119B-2603 | 200 | 1.018 | 4 | 1.0 | 1.66 | 0.185 |
| B allenai/Olmo-3.1-32B-Instruct | 197 | 1.065 | 23 | 2 | 2.14 | 0.122 |
| C openai/gpt-oss-120b | 200 | 1.007 | 4 | 2.0 | 1.88 | 0.13 |
| C mistralai/Mistral-Small-4-119B-2603 | 200 | 0.92 | 3 | 2.0 | 1.99 | 0.17 |
| C allenai/Olmo-3.1-32B-Instruct | 198 | 1.01 | 15 | 2.0 | 2.25 | 0.106 |
| E openai/gpt-oss-120b | 200 | 1.023 | 4 | 2.0 | 1.97 | 0.12 |
| E mistralai/Mistral-Small-4-119B-2603 | 200 | 1.0 | 4 | 2.0 | 2.06 | 0.17 |
| E allenai/Olmo-3.1-32B-Instruct | 199 | 1.055 | 18 | 2 | 2.18 | 0.141 |

Per editor and per judge (decide nothing):

| Who | B minus E (points) | E against B | Share changing, B | C | E |
| --- | --- | --- | --- | --- | --- |
| openai/gpt-oss-120b | +8.5 [+1.0, +16.0] | 0.369 [0.327, 0.412] | 0.310 [0.245, 0.375] | 0.400 [0.330, 0.465] | 0.225 [0.170, 0.285] |
| mistralai/Mistral-Small-4-119B-2603 | +1.0 [-7.5, +9.0] | 0.531 [0.487, 0.574] | 0.380 [0.310, 0.450] | 0.685 [0.620, 0.750] | 0.370 [0.305, 0.440] |
| allenai/Olmo-3.1-32B-Instruct | +2.0 [-4.6, +9.1] | 0.392 [0.357, 0.426] | 0.787 [0.731, 0.843] | 0.803 [0.747, 0.859] | 0.769 [0.709, 0.829] |
| Qwen/Qwen3.8-27B | +4.7 [+0.5, +8.8] | 0.441 [0.411, 0.469] | 0.482 [0.446, 0.520] | 0.655 [0.614, 0.695] | 0.437 [0.397, 0.478] |
| google/gemma-4-31B-it | +3.2 [-0.8, +7.2] | 0.431 [0.397, 0.466] | 0.268 [0.231, 0.306] | 0.299 [0.261, 0.337] | 0.237 [0.203, 0.272] |
| zai-org/GLM-4.7-Flash | +0.0 [-0.7, +0.7] | 0.420 [0.389, 0.452] | 0.995 [0.988, 1.000] | 1.000 [1.000, 1.000] | 0.995 [0.988, 1.000] |
