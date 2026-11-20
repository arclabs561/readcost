## Agent feedback text, stage 2: the search

A copy of `agent-text-search/main-1/search.md` in the private dataset `arclabs561/readcost-labels`, where the replies (which start from the factorial's run `agent-text/main-1`), `search.json`, `run.json` and the model logs are kept. The plan is `docs/prereg/agent-text-search.md`. The job ran from `3acaf21`. `r_star.json` here holds R* as the job's rule chose it.

Calls 63851 in the cache (new this run 23100). Phases: edits done, facts done, read done

| Species | Candidate | Units | Change [95%] | Read vs C [95%] | Utility [95%] | Gain over seed | Chosen |
| --- | --- | --- | --- | --- | --- | --- | --- |
| scope | v0 | 390 | +0.295 [+0.244, +0.346] | +0.578 [+0.537, +0.618] | +0.283 [+0.213, +0.351] |  | yes |
| scope | v1 | 390 | +0.203 [+0.164, +0.241] | +0.485 [+0.442, +0.527] | +0.282 [+0.222, +0.341] | -0.0006 |  |
| scope | v2 | 390 | +0.318 [+0.269, +0.369] | +0.575 [+0.535, +0.615] | +0.257 [+0.194, +0.319] | -0.0256 |  |
| scope | v3 | 390 | +0.297 [+0.249, +0.346] | +0.573 [+0.531, +0.614] | +0.276 [+0.208, +0.342] | -0.0071 |  |
| stacked-nouns | v0 | 194 | +0.273 [+0.201, +0.351] | +0.545 [+0.490, +0.599] | +0.272 [+0.169, +0.370] |  | yes |
| stacked-nouns | v1 | 194 | +0.299 [+0.227, +0.376] | +0.549 [+0.492, +0.606] | +0.250 [+0.149, +0.345] | -0.0219 |  |
| stacked-nouns | v2 | 194 | +0.320 [+0.247, +0.392] | +0.552 [+0.499, +0.606] | +0.232 [+0.137, +0.323] | -0.0399 |  |
| stacked-nouns | v3 | 194 | +0.371 [+0.299, +0.443] | +0.522 [+0.466, +0.577] | +0.151 [+0.053, +0.249] | -0.1211 |  |
| long-dependency | v0 | 60 | +0.217 [+0.100, +0.350] | +0.483 [+0.383, +0.588] | +0.267 [+0.092, +0.438] |  | yes |
| long-dependency | v1 | 60 | +0.150 [+0.067, +0.250] | +0.421 [+0.325, +0.521] | +0.271 [+0.138, +0.408] | 0.0042 |  |
| long-dependency | v2 | 60 | +0.267 [+0.167, +0.383] | +0.367 [+0.267, +0.475] | +0.100 [-0.062, +0.263] | -0.1667 |  |
| long-dependency | v3 | 60 | +0.283 [+0.167, +0.400] | +0.417 [+0.317, +0.521] | +0.133 [-0.021, +0.292] | -0.1333 |  |
| reduced-object-relative | v0 | 120 | +0.367 [+0.267, +0.475] | +0.448 [+0.377, +0.517] | +0.081 [-0.062, +0.215] |  |  |
| reduced-object-relative | v1 | 120 | +0.342 [+0.250, +0.433] | +0.419 [+0.346, +0.496] | +0.077 [-0.050, +0.202] | -0.0042 |  |
| reduced-object-relative | v2 | 120 | +0.350 [+0.258, +0.450] | +0.465 [+0.396, +0.533] | +0.115 [-0.015, +0.237] | 0.0333 | yes |
| reduced-object-relative | v3 | 120 | +0.350 [+0.267, +0.442] | +0.377 [+0.306, +0.452] | +0.027 [-0.090, +0.142] | -0.0542 |  |
| hyphen-compound | v0 | 68 | +0.250 [+0.147, +0.368] | +0.529 [+0.449, +0.610] | +0.279 [+0.136, +0.408] |  |  |
| hyphen-compound | v1 | 68 | +0.382 [+0.265, +0.500] | +0.533 [+0.449, +0.618] | +0.151 [+0.000, +0.301] | -0.1287 |  |
| hyphen-compound | v2 | 68 | +0.324 [+0.191, +0.456] | +0.518 [+0.438, +0.599] | +0.195 [+0.040, +0.346] | -0.0846 |  |
| hyphen-compound | v3 | 68 | +0.176 [+0.088, +0.279] | +0.515 [+0.438, +0.592] | +0.338 [+0.221, +0.452] | 0.0588 | yes |
| inline-list | v0 | 266 | +0.282 [+0.222, +0.342] | +0.704 [+0.664, +0.742] | +0.422 [+0.348, +0.494] |  | yes |
| inline-list | v1 | 266 | +0.353 [+0.293, +0.414] | +0.682 [+0.643, +0.722] | +0.329 [+0.257, +0.401] | -0.093 |  |
| inline-list | v2 | 266 | +0.365 [+0.305, +0.425] | +0.660 [+0.617, +0.702] | +0.295 [+0.216, +0.372] | -0.1269 |  |
| inline-list | v3 | 266 | +0.312 [+0.252, +0.372] | +0.691 [+0.648, +0.732] | +0.379 [+0.302, +0.458] | -0.0432 |  |

R* (the seed, HsFpX, with each species' choice):

- scope line: (none)
- stacked-nouns: Keep at most two nouns together. Unpack the rest with a preposition or a relative clause, if the result reads naturally; leave an established term as it is.
- long-dependency: Put the subject next to its verb. Move long modifiers after the verb or into a second sentence.
- reduced-object-relative: Keep the 'that'. If the clause is long, make it a sentence of its own.
- hyphen-compound: Replace the hyphenated chain with a phrase that says how its words relate.
- inline-list: Use a bulleted list.
