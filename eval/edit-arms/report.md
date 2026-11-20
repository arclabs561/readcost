## Edit arms: readcost feedback (B) against a generic instruction (C) and the original (A)

A copy of `edit-arms/main-1b/edit-arms.md` in the private dataset `arclabs561/readcost-labels`, where the replies (`replies.jsonl`), `run.json` and the model logs of runs `main-1` and `main-1b` are kept. `main-1` stopped after B against C at the original phases' call cap; `main-1b` resumed it from `main-1`'s replies under the cap the plan's amendment of 19 November raised, written after B against C was seen. B against C is `main-1`'s, unchanged.

Calls 8661 (new this run 2387, served from cache 6263), on GPUs billed by time (see run.json); call caps 7500 for the original phases and 9160 for the whole run. Phases: edits done, editsD done, BC done, facts done, BA done, CA done, DB done, factsD done, DC done, DA done

| Pair | Win rate of first [95%] | Label | Win | Tie | Split | Loss | Missing |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B against C | 0.542 [0.482, 0.601] | inconclusive | 151 | 1 | 279 | 106 | 3 |
| B against A | 0.866 [0.827, 0.901] | better | 400 | 5 | 125 | 7 | 3 |
| C against A | 0.823 [0.784, 0.861] | better | 354 | 0 | 176 | 7 | 3 |

| Claim | Holds |
| --- | --- |
| readcost feedback beats a generic instruction | no |
| readcost adds nothing over a generic instruction | no |
| an edit with readcost feedback beats the original | no |
| an edit with a generic instruction beats the original | no |

Content (an edit changes content when 2 of 3 judges list a lost or changed fact):

| Arm | Edits checked | Share changing content [95%] | Lost | Added | Changed |
| --- | --- | --- | --- | --- | --- |
| B | 179 | 0.475 [0.402, 0.544] | 1.928 | 1.957 | 1.871 |
| C | 179 | 0.581 [0.508, 0.650] | 2.403 | 2.293 | 2.655 |
| D | 179 | 0.559 [0.486, 0.631] | 2.261 | 2.169 | 2.223 |

B minus C, share changing content: -0.106 [-0.194, -0.022]. Missing edits: 2.

| Version | n | Words over original, median | Over budget | Findings, median | mean | none |
| --- | --- | --- | --- | --- | --- | --- |
| A | 60 | 1.0 | 0 | 2.0 | 2.65 | 0.0 |
| B openai/gpt-oss-120b | 60 | 1.054 | 0 | 1.0 | 1.38 | 0.333 |
| B mistralai/Mistral-Small-4-119B-2603 | 60 | 1.01 | 1 | 1.5 | 1.93 | 0.133 |
| B allenai/Olmo-3.1-32B-Instruct | 59 | 1.064 | 9 | 2 | 2.27 | 0.153 |
| C openai/gpt-oss-120b | 60 | 1.01 | 1 | 2.0 | 2.08 | 0.083 |
| C mistralai/Mistral-Small-4-119B-2603 | 60 | 0.93 | 2 | 2.0 | 2.17 | 0.133 |
| C allenai/Olmo-3.1-32B-Instruct | 59 | 1.013 | 8 | 2 | 2.2 | 0.119 |
| D openai/gpt-oss-120b | 60 | 1.043 | 1 | 1.0 | 1.68 | 0.167 |
| D mistralai/Mistral-Small-4-119B-2603 | 60 | 0.995 | 0 | 2.0 | 2.03 | 0.133 |
| D allenai/Olmo-3.1-32B-Instruct | 59 | 1.03 | 7 | 2 | 2.19 | 0.136 |

B was told to address readcost's findings, so fewer findings after B is not evidence that B reads better.

Per editor and per judge (decide nothing):

| Who | B against C | B against A | C against A |
| --- | --- | --- | --- |
| openai/gpt-oss-120b | 0.553 [0.478, 0.628] | 0.869 [0.822, 0.914] | 0.792 [0.739, 0.844] |
| mistralai/Mistral-Small-4-119B-2603 | 0.519 [0.433, 0.606] | 0.903 [0.856, 0.944] | 0.858 [0.808, 0.906] |
| allenai/Olmo-3.1-32B-Instruct | 0.554 [0.489, 0.621] | 0.825 [0.777, 0.870] | 0.819 [0.768, 0.864] |
| Qwen/Qwen3.8-27B | 0.578 [0.517, 0.640] | 0.855 [0.807, 0.897] | 0.791 [0.742, 0.839] |
| google/gemma-4-31B-it | 0.550 [0.480, 0.619] | 0.933 [0.899, 0.963] | 0.905 [0.867, 0.939] |
| zai-org/GLM-4.7-Flash | 0.497 [0.438, 0.556] | 0.810 [0.760, 0.858] | 0.774 [0.725, 0.822] |

Judge agreement (same outcome on a unit): Qwen/Qwen3.8-27B / google/gemma-4-31B-it 0.801; Qwen/Qwen3.8-27B / zai-org/GLM-4.7-Flash 0.734; google/gemma-4-31B-it / zai-org/GLM-4.7-Flash 0.7

### Arm D: readcost feedback worded as questions (secondary)

D has B's prompt and B's findings, with the feedback worded as in pull request #102 and its held-out rule precision. B against C above stays the primary outcome.

| Pair | Win rate of D [95%] | Label | Win | Tie | Split | Loss | Missing |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D against B | 0.494 [0.453, 0.536] | no meaningful advantage | 94 | 10 | 333 | 100 | 3 |
| D against C | 0.506 [0.455, 0.555] | inconclusive | 126 | 1 | 290 | 120 | 3 |
| D against A | 0.852 [0.813, 0.889] | better | 385 | 3 | 142 | 7 | 3 |

| D minus B, paired by unit | Estimate [95%] |
| --- | --- |
| Share of edits changing content | 0.084 [0.011, 0.156] |
| Facts lost per edit | 0.332 [0.047, 0.617] |
| Length change, abs(words over A - 1) | -0.005 [-0.013, 0.003] |

D minus C, share changing content: -0.022 [-0.106, 0.062]. Missing D edits: 1.

| Reading of D | Holds |
| --- | --- |
| the question wording should ship | no |
| the question wording should not ship | yes |
| an edit with feedback as questions beats a generic instruction | no |
| an edit with feedback as questions beats the original | no |

| Who | D against B | D against C | D against A |
| --- | --- | --- | --- |
| openai/gpt-oss-120b | 0.567 [0.503, 0.631] | 0.586 [0.517, 0.653] | 0.853 [0.800, 0.903] |
| mistralai/Mistral-Small-4-119B-2603 | 0.489 [0.425, 0.550] | 0.478 [0.389, 0.564] | 0.875 [0.828, 0.919] |
| allenai/Olmo-3.1-32B-Instruct | 0.427 [0.370, 0.483] | 0.452 [0.390, 0.514] | 0.828 [0.780, 0.873] |
| Qwen/Qwen3.8-27B | 0.492 [0.447, 0.536] | 0.542 [0.492, 0.589] | 0.841 [0.797, 0.883] |
| google/gemma-4-31B-it | 0.475 [0.424, 0.528] | 0.506 [0.442, 0.567] | 0.916 [0.879, 0.950] |
| zai-org/GLM-4.7-Flash | 0.517 [0.469, 0.564] | 0.469 [0.416, 0.525] | 0.799 [0.747, 0.847] |

Judge agreement on D's pairs: Qwen/Qwen3.8-27B / google/gemma-4-31B-it 0.786; Qwen/Qwen3.8-27B / zai-org/GLM-4.7-Flash 0.698; google/gemma-4-31B-it / zai-org/GLM-4.7-Flash 0.709

Models served: Qwen/Qwen3.8-27B: {'Qwen/Qwen3.8-27B': 2683}; allenai/Olmo-3.1-32B-Instruct: {'allenai/Olmo-3.1-32B-Instruct': 177}; google/gemma-4-31B-it: {'google/gemma-4-31B-it': 2685}; mistralai/Mistral-Small-4-119B-2603: {'mistralai/Mistral-Small-4-119B-2603': 180}; openai/gpt-oss-120b: {'openai/gpt-oss-120b': 180}; zai-org/GLM-4.7-Flash: {'zai-org/GLM-4.7-Flash': 2659}

Draw: candidates 5367; walked 784 (drawn: 60, no README: 27, no eligible paragraph: 694, repository unavailable: 3); paragraphs fetched 60; missing at run time 0.
