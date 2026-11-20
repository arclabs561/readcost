## Agent feedback text: a fractional factorial over five parts

A copy of `agent-text/main-1/agent-text.md` in the private dataset `arclabs561/readcost-labels`, where the replies (`replies.jsonl`, which start from the localization control's run `edit-localize/main-1`), `run.json` and the model logs are kept. The plan is `docs/prereg/agent-text-factorial.md`. The job ran from `e85494e` for 2,702 seconds. It found all 200 C anchors in the cache before loading a model.

Main set 100 paragraphs, decoy set 40. Units with change 200, with read 200. Missing edits 0. Calls 40751 in the cache (new this run 22550). Phases: edits done, facts done, read done

| Factor | Change (share) [95%] | Matters | Read (vs C) [95%] | Matters | Utility [95%] |
| --- | --- | --- | --- | --- | --- |
| H: head orders (+) or informs (−) | -0.028 [-0.054, -0.002] | no | -0.020 [-0.031, -0.009] | no | +0.008 [-0.021, +0.038] |
| S: scope line | -0.099 [-0.127, -0.072] | yes | -0.085 [-0.103, -0.068] | yes | +0.014 [-0.019, +0.046] |
| F: rule's fix (+) or generic (−) | -0.149 [-0.191, -0.109] | yes | +0.163 [+0.126, +0.199] | yes | +0.312 [+0.254, +0.371] |
| P: precision note | +0.021 [+0.001, +0.041] | no | -0.003 [-0.014, +0.008] | no | -0.024 [-0.045, -0.004] |
| X: finding's message (+) or rule's title (−) | -0.041 [-0.071, -0.012] | yes | -0.023 [-0.038, -0.008] | no | +0.018 [-0.017, +0.053] |

Seed for stage 2: **HsFpX** (R0 is HsFPX). Whole-text search: no. Stage 2 runs: yes.

| Interaction | Change | Read | Utility |
| --- | --- | --- | --- |
| HS | +0.029 [+0.001, +0.056] | +0.009 [-0.003, +0.021] | -0.020 [-0.048, +0.008] |
| HF | +0.016 [-0.010, +0.043] | -0.003 [-0.014, +0.007] | -0.019 [-0.047, +0.007] |
| HP | -0.006 [-0.033, +0.020] | +0.001 [-0.011, +0.012] | +0.007 [-0.021, +0.035] |
| HX | +0.014 [-0.011, +0.039] | -0.003 [-0.013, +0.007] | -0.017 [-0.043, +0.008] |
| SF | -0.007 [-0.033, +0.018] | +0.006 [-0.006, +0.018] | +0.013 [-0.012, +0.039] |
| SP | -0.025 [-0.047, -0.003] | -0.002 [-0.012, +0.007] | +0.023 [-0.001, +0.047] |
| SX | +0.018 [-0.009, +0.044] | -0.004 [-0.015, +0.006] | -0.022 [-0.049, +0.005] |
| FP | +0.005 [-0.017, +0.028] | -0.002 [-0.012, +0.009] | -0.007 [-0.031, +0.018] |
| FX | -0.010 [-0.039, +0.019] | -0.008 [-0.022, +0.005] | +0.002 [-0.027, +0.030] |
| PX | +0.020 [-0.003, +0.044] | -0.000 [-0.012, +0.012] | -0.020 [-0.048, +0.007] |

Deference index (decoy rewritten minus control rewritten): -0.039 [-0.125, +0.042]; decoys rewritten 0.766.

| Factor | Effect on deference |
| --- | --- |
| H | +0.022 [-0.041, +0.081] |
| S | +0.034 [-0.041, +0.113] |
| F | -0.047 [-0.113, +0.016] |
| P | +0.053 [+0.000, +0.106] |

| Arm | Change | Read | Utility | Length |
| --- | --- | --- | --- | --- |
| HSFPx | 0.23 | 0.512 | 0.282 | 1.024 |
| HSFpX | 0.215 | 0.48 | 0.265 | 1.032 |
| HSfPX | 0.375 | 0.318 | -0.058 | 1.009 |
| HSfpx | 0.39 | 0.343 | -0.048 | 1.006 |
| HsFPX (R0) | 0.315 | 0.55 | 0.235 | 1.037 |
| HsFpx | 0.325 | 0.583 | 0.258 | 1.036 |
| HsfPx | 0.46 | 0.42 | -0.04 | 1.0 |
| HsfpX | 0.39 | 0.405 | 0.015 | 1.007 |
| hSFPX | 0.205 | 0.49 | 0.285 | 1.023 |
| hSFpx | 0.245 | 0.53 | 0.285 | 1.022 |
| hSfPx | 0.39 | 0.344 | -0.046 | 1.0 |
| hSfpX | 0.365 | 0.333 | -0.033 | 1.006 |
| hsFPx | 0.41 | 0.609 | 0.199 | 1.019 |
| hsFpX | 0.27 | 0.588 | 0.318 | 1.031 |
| hsfPX | 0.51 | 0.434 | -0.076 | 0.993 |
| hsfpx | 0.525 | 0.441 | -0.084 | 0.995 |

Per editor, main effects (decide nothing):

| Editor | Outcome | H | S | F | P | X |
| --- | --- | --- | --- | --- | --- | --- |
| openai/gpt-oss-120b | change | -0.055 [-0.096, -0.015] | -0.095 [-0.142, -0.048] | -0.065 [-0.114, -0.018] | +0.015 [-0.016, +0.046] | -0.043 [-0.080, -0.005] |
| openai/gpt-oss-120b | read | -0.048 [-0.065, -0.033] | -0.131 [-0.157, -0.107] | +0.170 [+0.124, +0.215] | -0.003 [-0.019, +0.012] | -0.022 [-0.041, -0.003] |
| mistralai/Mistral-Small-4-119B-2603 | change | +0.000 [-0.036, +0.036] | -0.102 [-0.136, -0.070] | -0.233 [-0.289, -0.177] | +0.028 [-0.004, +0.060] | -0.040 [-0.083, +0.003] |
| mistralai/Mistral-Small-4-119B-2603 | read | +0.009 [-0.006, +0.024] | -0.039 [-0.059, -0.020] | +0.157 [+0.115, +0.199] | -0.003 [-0.018, +0.013] | -0.025 [-0.046, -0.004] |
