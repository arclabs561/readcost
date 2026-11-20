## Agent feedback text, stage 2: the held-out test

A copy of `agent-text-heldout/main-1/heldout.md` in the private dataset `arclabs561/readcost-labels`, where the replies, `heldout.json`, `run.json` and the model logs are kept. The plan is `docs/prereg/agent-text-search.md`, part 2. The job ran from `d1cb611`. The judges were pinned at Nemotron 3.5 Lightning `a9904d24bcc1d289a1950fa9d2b978c47cf903b9` and Phi-4 `2db69c1c3e91a05d2c64a3185acfbaf36f744e25`; neither needed the fallback.

Held-out draw: walked 1317 more repositories (no eligible paragraph: 1146, drawn: 100, no README: 65, repository unavailable: 6).

Paragraphs 100. Judges: nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16, microsoft/phi-4. Calls 6632 in the cache (new this run 6632). Missing edits 1. Phases: edits done, facts done, read done

| Pair | Win rate of the first [95%] | Counts | Missing |
| --- | --- | --- | --- |
| R* against R0 | 0.493 [0.483, 0.502] | loss 17, split 564, tie 10, win 9 | 0 |
| R* against C | 0.489 [0.478, 0.499] | loss 21, split 569, win 8 | 2 |
| R0 against C | 0.496 [0.485, 0.507] | loss 16, split 571, win 11 | 2 |

| Share of edits changing content | Estimate [95%] |
| --- | --- |
| RS | 0.963 [0.942, 0.983] |
| R0 | 0.967 [0.943, 0.987] |
| C | 0.956 [0.930, 0.980] |
| R* minus R0 (points) | -0.3 [-3.0, +2.3] |
| R0 minus C (points) | +1.0 [-1.7, +4.0] |
| R* minus C (points) | +0.7 [-2.0, +3.4] |

| Part of the decision | Holds |
| --- | --- |
| R* reads at least as well | no |
| R* does not change content more | yes |
| **R* replaces today's text** | **no** |

Per editor and judge (decide nothing):

| Who | R* against R0 | R* against C | R0 against C | R* minus R0, content (points) |
| --- | --- | --- | --- | --- |
| openai/gpt-oss-120b | 0.497 [0.485, 0.510] | 0.495 [0.477, 0.512] | 0.505 [0.490, 0.522] | +0.0 [-5.1, +5.1] |
| mistralai/Mistral-Small-4-119B-2603 | 0.490 [0.472, 0.505] | 0.475 [0.458, 0.492] | 0.485 [0.465, 0.502] | +0.0 [-6.1, +6.1] |
| allenai/Olmo-3.1-32B-Instruct | 0.492 [0.480, 0.502] | 0.497 [0.485, 0.508] | 0.497 [0.485, 0.510] | -1.0 [-3.0, +0.0] |
| nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16 | 0.492 [0.475, 0.507] | 0.483 [0.466, 0.500] | 0.492 [0.473, 0.508] |  |
| microsoft/phi-4 | 0.495 [0.485, 0.503] | 0.495 [0.487, 0.502] | 0.500 [0.492, 0.510] |  |

Median words over the original: RS 1.055, R0 1.051, C 0.994.

R*: scope line none; fixes:
- stacked-nouns: Keep at most two nouns together. Unpack the rest with a preposition or a relative clause, if the result reads naturally; leave an established term as it is.
- long-dependency: Put the subject next to its verb. Move long modifiers after the verb or into a second sentence.
- reduced-object-relative: Keep the 'that'. If the clause is long, make it a sentence of its own.
- hyphen-compound: Replace the hyphenated chain with a phrase that says how its words relate.
- inline-list: Use a bulleted list.
