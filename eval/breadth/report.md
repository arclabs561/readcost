# Breadth precision: results

Computed by `scripts/breadth_report.py` as `docs/prereg/breadth-precision.md` fixes it. c: at least 7 of the 12 primed raters label the item c (an editor would fix it); accepted: at least 7 label it c or d; present: at least 7 say the construction is there; unprimed c: at least 2 of the 3 unprimed raters label it c. Wilson 95% intervals; differences with Newcombe 95% intervals.

## Counts

| Stratum | Findings (deduplicated) | Near misses (deduplicated) | Sampled findings | Sampled near misses | Decoys |
| --- | --- | --- | --- | --- | --- |
| md | 9010 (8361) | 23117 (18813) | 120 | 32 | 4 |
| rst | 241 (214) | 673 (565) | 77 | 32 | 4 |
| html | 94 (92) | 234 (201) | 37 | 12 | 2 |
| src-py | 668 (615) | 1804 (1464) | 26 | 8 | 1 |
| src-rs | 333 (319) | 937 (802) | 28 | 8 | 1 |
| src-go | 276 (249) | 762 (617) | 26 | 8 | 1 |
| src-js | 864 (737) | 2165 (1756) | 28 | 8 | 1 |
| src-jvm | 1130 (898) | 2657 (2113) | 28 | 8 | 1 |
| src-c | 1306 (967) | 2921 (2176) | 28 | 8 | 1 |
| src-rb | 781 (703) | 2090 (1684) | 29 | 8 | 1 |
| commit | 7089 (6298) | 16569 (12202) | 114 | 32 | 4 |
| pr | 9997 (8965) | 24985 (18896) | 114 | 32 | 4 |

Steps before the draw: {"_texts": {"commit: duplicate text": 111, "commit: kept": 5850, "commit: not English": 3, "html: duplicate text": 1, "html: kept": 16, "html: not English": 3, "html: under 100 words": 59, "md: kept": 707, "md: mostly code": 188, "md: not English": 11, "md: under 100 words": 91, "pr: duplicate text": 31, "pr: kept": 2109, "pr: not English": 20, "pr: under 100 words": 1346, "rst: kept": 41, "rst: under 100 words": 27, "src-c: duplicate text": 2, "src-c: kept": 283, "src-c: not English": 2, "src-c: too large": 4, "src-c: under 40 words": 182, "src-go: kept": 104, "src-go: under 40 words": 80, "src-js: duplicate text": 9, "src-js: kept": 234, "src-js: too large": 21, "src-js: under 40 words": 465, "src-jvm: kept": 357, "src-jvm: not English": 3, "src-jvm: too large": 3, "src-jvm: under 40 words": 349, "src-py: duplicate text": 9, "src-py: kept": 212, "src-py: too large": 4, "src-py: under 40 words": 403, "src-rb: duplicate text": 3, "src-rb: kept": 314, "src-rb: not English": 1, "src-rb: too large": 4, "src-rb: under 40 words": 609, "src-rs: duplicate text": 1, "src-rs: kept": 87, "src-rs: under 40 words": 122}, "_walk": {"owner cap": 16, "picked": 720}, "_repos": {"README under 100 words": 81, "kept": 608, "no README": 5, "README not English": 26}}

## Primary: c share of findings beside near misses

| Family | Rule | Findings, c | Near misses, c | Difference |
| --- | --- | --- | --- | --- |
| md | stacked-nouns | 0/16 (0%; 0% to 19%) | 0/8 (0%; 0% to 32%) | +0 points (-32 to +19) |
| md | long-dependency | 0/16 (0%; 0% to 19%) | 0/8 (0%; 0% to 32%) | +0 points (-32 to +19) |
| md | reduced-object-relative | 0/16 (0%; 0% to 19%) | no threshold | n/a |
| md | hyphen-compound | 0/16 (0%; 0% to 19%) | no threshold | n/a |
| md | inline-list | 0/16 (0%; 0% to 19%) | 0/8 (0%; 0% to 32%) | +0 points (-32 to +19) |
| md | inanimate-subject | 0/8 (0%; 0% to 32%) | no threshold | n/a |
| md | participial-clause | 0/8 (0%; 0% to 32%) | no threshold | n/a |
| md | nominalization | 1/8 (12%; 2% to 47%) | no threshold | n/a |
| md | center-embedding | 1/8 (12%; 2% to 47%) | 0/4 (0%; 0% to 49%) | +12 points (-38 to +47) |
| md | undefined-acronym | 0/8 (0%; 0% to 32%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +32) |
| rst | stacked-nouns | 0/16 (0%; 0% to 19%) | 0/8 (0%; 0% to 32%) | +0 points (-32 to +19) |
| rst | long-dependency | 0/12 (0%; 0% to 24%) | 0/8 (0%; 0% to 32%) | +0 points (-32 to +24) |
| rst | reduced-object-relative | 0/6 (0%; 0% to 39%) | no threshold | n/a |
| rst | hyphen-compound | 0/8 (0%; 0% to 32%) | no threshold | n/a |
| rst | inline-list | 1/16 (6%; 1% to 28%) | 0/8 (0%; 0% to 32%) | +6 points (-27 to +28) |
| rst | inanimate-subject | 0/2 (0%; 0% to 66%) | no threshold | n/a |
| rst | participial-clause | 0/8 (0%; 0% to 32%) | no threshold | n/a |
| rst | nominalization | 0/1 (0%; 0% to 79%) | no threshold | n/a |
| rst | center-embedding | none | 0/4 (0%; 0% to 49%) | n/a |
| rst | undefined-acronym | 0/8 (0%; 0% to 32%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +32) |
| html | stacked-nouns | 0/8 (0%; 0% to 32%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +32) |
| html | long-dependency | 2/3 (67%; 21% to 94%) | none | n/a |
| html | reduced-object-relative | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| html | hyphen-compound | 0/3 (0%; 0% to 56%) | no threshold | n/a |
| html | inline-list | 1/8 (12%; 2% to 47%) | 0/4 (0%; 0% to 49%) | +12 points (-38 to +47) |
| html | inanimate-subject | 0/2 (0%; 0% to 66%) | no threshold | n/a |
| html | participial-clause | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| html | nominalization | 0/1 (0%; 0% to 79%) | no threshold | n/a |
| html | center-embedding | none | 0/2 (0%; 0% to 66%) | n/a |
| html | undefined-acronym | 0/4 (0%; 0% to 49%) | 0/2 (0%; 0% to 66%) | +0 points (-66 to +49) |
| doc comments | stacked-nouns | 0/28 (0%; 0% to 12%) | 0/14 (0%; 0% to 22%) | +0 points (-22 to +12) |
| doc comments | long-dependency | 2/28 (7%; 2% to 23%) | 0/14 (0%; 0% to 22%) | +7 points (-15 to +23) |
| doc comments | reduced-object-relative | 3/27 (11%; 4% to 28%) | no threshold | n/a |
| doc comments | hyphen-compound | 0/28 (0%; 0% to 12%) | no threshold | n/a |
| doc comments | inline-list | 0/28 (0%; 0% to 12%) | 0/14 (0%; 0% to 22%) | +0 points (-22 to +12) |
| doc comments | inanimate-subject | 0/14 (0%; 0% to 22%) | no threshold | n/a |
| doc comments | participial-clause | 0/14 (0%; 0% to 22%) | no threshold | n/a |
| doc comments | nominalization | 1/5 (20%; 4% to 62%) | no threshold | n/a |
| doc comments | center-embedding | 1/6 (17%; 3% to 56%) | 0/7 (0%; 0% to 35%) | +17 points (-21 to +56) |
| doc comments | undefined-acronym | 0/14 (0%; 0% to 22%) | 0/7 (0%; 0% to 35%) | +0 points (-35 to +22) |
| commit | stacked-nouns | 0/16 (0%; 0% to 19%) | 0/8 (0%; 0% to 32%) | +0 points (-32 to +19) |
| commit | long-dependency | 1/16 (6%; 1% to 28%) | 0/8 (0%; 0% to 32%) | +6 points (-27 to +28) |
| commit | reduced-object-relative | 1/16 (6%; 1% to 28%) | no threshold | n/a |
| commit | hyphen-compound | 0/16 (0%; 0% to 19%) | no threshold | n/a |
| commit | inline-list | 3/16 (19%; 7% to 43%) | 1/8 (12%; 2% to 47%) | +6 points (-30 to +33) |
| commit | inanimate-subject | 0/8 (0%; 0% to 32%) | no threshold | n/a |
| commit | participial-clause | 0/8 (0%; 0% to 32%) | no threshold | n/a |
| commit | nominalization | 0/2 (0%; 0% to 66%) | no threshold | n/a |
| commit | center-embedding | 1/8 (12%; 2% to 47%) | 0/4 (0%; 0% to 49%) | +12 points (-38 to +47) |
| commit | undefined-acronym | 0/8 (0%; 0% to 32%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +32) |
| pr | stacked-nouns | 0/16 (0%; 0% to 19%) | 0/8 (0%; 0% to 32%) | +0 points (-32 to +19) |
| pr | long-dependency | 0/16 (0%; 0% to 19%) | 0/8 (0%; 0% to 32%) | +0 points (-32 to +19) |
| pr | reduced-object-relative | 0/16 (0%; 0% to 19%) | no threshold | n/a |
| pr | hyphen-compound | 0/16 (0%; 0% to 19%) | no threshold | n/a |
| pr | inline-list | 0/16 (0%; 0% to 19%) | 0/8 (0%; 0% to 32%) | +0 points (-32 to +19) |
| pr | inanimate-subject | 0/8 (0%; 0% to 32%) | no threshold | n/a |
| pr | participial-clause | 0/8 (0%; 0% to 32%) | no threshold | n/a |
| pr | nominalization | 0/2 (0%; 0% to 66%) | no threshold | n/a |
| pr | center-embedding | 1/8 (12%; 2% to 47%) | 0/4 (0%; 0% to 49%) | +12 points (-38 to +47) |
| pr | undefined-acronym | 0/8 (0%; 0% to 32%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +32) |

## Secondary, per family

### md

120 findings, 32 near misses.

| Rule | Kind | Accepted | Present | Unprimed c | Unprimed c or d |
| --- | --- | --- | --- | --- | --- |
| stacked-nouns | findings | 5/16 (31%; 14% to 56%) | 15/16 (94%; 72% to 99%) | 0/16 (0%; 0% to 19%) | 1/16 (6%; 1% to 28%) |
| stacked-nouns | near misses | 0/8 (0%; 0% to 32%) | 1/8 (12%; 2% to 47%) | 0/8 (0%; 0% to 32%) | 3/8 (38%; 14% to 69%) |
| long-dependency | findings | 5/16 (31%; 14% to 56%) | 7/16 (44%; 23% to 67%) | 0/16 (0%; 0% to 19%) | 7/16 (44%; 23% to 67%) |
| long-dependency | near misses | 3/8 (38%; 14% to 69%) | 4/8 (50%; 22% to 78%) | 0/8 (0%; 0% to 32%) | 2/8 (25%; 7% to 59%) |
| reduced-object-relative | findings | 8/16 (50%; 28% to 72%) | 11/16 (69%; 44% to 86%) | 2/16 (12%; 3% to 36%) | 9/16 (56%; 33% to 77%) |
| hyphen-compound | findings | 7/16 (44%; 23% to 67%) | 9/16 (56%; 33% to 77%) | 0/16 (0%; 0% to 19%) | 2/16 (12%; 3% to 36%) |
| inline-list | findings | 5/16 (31%; 14% to 56%) | 13/16 (81%; 57% to 93%) | 1/16 (6%; 1% to 28%) | 4/16 (25%; 10% to 49%) |
| inline-list | near misses | 1/8 (12%; 2% to 47%) | 1/8 (12%; 2% to 47%) | 1/8 (12%; 2% to 47%) | 2/8 (25%; 7% to 59%) |
| inanimate-subject | findings | 0/8 (0%; 0% to 32%) | 6/8 (75%; 41% to 93%) | 2/8 (25%; 7% to 59%) | 2/8 (25%; 7% to 59%) |
| participial-clause | findings | 5/8 (62%; 31% to 86%) | 7/8 (88%; 53% to 98%) | 0/8 (0%; 0% to 32%) | 4/8 (50%; 22% to 78%) |
| nominalization | findings | 7/8 (88%; 53% to 98%) | 7/8 (88%; 53% to 98%) | 0/8 (0%; 0% to 32%) | 5/8 (62%; 31% to 86%) |
| center-embedding | findings | 3/8 (38%; 14% to 69%) | 3/8 (38%; 14% to 69%) | 1/8 (12%; 2% to 47%) | 5/8 (62%; 31% to 86%) |
| center-embedding | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) |
| undefined-acronym | findings | 0/8 (0%; 0% to 32%) | 7/8 (88%; 53% to 98%) | 0/8 (0%; 0% to 32%) | 1/8 (12%; 2% to 47%) |
| undefined-acronym | near misses | 1/4 (25%; 5% to 70%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) |

Fleiss' kappa over the twelve (120 complete findings, 0 incomplete): c/d/w 0.39, c against not 0.33, accepted against not 0.46; unprimed c against not 0.29 (120 complete).

### rst

77 findings, 32 near misses.

| Rule | Kind | Accepted | Present | Unprimed c | Unprimed c or d |
| --- | --- | --- | --- | --- | --- |
| stacked-nouns | findings | 4/16 (25%; 10% to 49%) | 14/16 (88%; 64% to 97%) | 0/16 (0%; 0% to 19%) | 2/16 (12%; 3% to 36%) |
| stacked-nouns | near misses | 0/8 (0%; 0% to 32%) | 0/8 (0%; 0% to 32%) | 0/8 (0%; 0% to 32%) | 1/8 (12%; 2% to 47%) |
| long-dependency | findings | 1/12 (8%; 1% to 35%) | 1/12 (8%; 1% to 35%) | 0/12 (0%; 0% to 24%) | 3/12 (25%; 9% to 53%) |
| long-dependency | near misses | 5/8 (62%; 31% to 86%) | 5/8 (62%; 31% to 86%) | 0/8 (0%; 0% to 32%) | 3/8 (38%; 14% to 69%) |
| reduced-object-relative | findings | 0/6 (0%; 0% to 39%) | 2/6 (33%; 10% to 70%) | 0/6 (0%; 0% to 39%) | 2/6 (33%; 10% to 70%) |
| hyphen-compound | findings | 0/8 (0%; 0% to 32%) | 6/8 (75%; 41% to 93%) | 0/8 (0%; 0% to 32%) | 2/8 (25%; 7% to 59%) |
| inline-list | findings | 2/16 (12%; 3% to 36%) | 11/16 (69%; 44% to 86%) | 1/16 (6%; 1% to 28%) | 3/16 (19%; 7% to 43%) |
| inline-list | near misses | 1/8 (12%; 2% to 47%) | 2/8 (25%; 7% to 59%) | 0/8 (0%; 0% to 32%) | 1/8 (12%; 2% to 47%) |
| inanimate-subject | findings | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) |
| participial-clause | findings | 4/8 (50%; 22% to 78%) | 7/8 (88%; 53% to 98%) | 0/8 (0%; 0% to 32%) | 2/8 (25%; 7% to 59%) |
| nominalization | findings | 1/1 (100%; 21% to 100%) | 1/1 (100%; 21% to 100%) | 0/1 (0%; 0% to 79%) | 0/1 (0%; 0% to 79%) |
| center-embedding | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) |
| undefined-acronym | findings | 1/8 (12%; 2% to 47%) | 7/8 (88%; 53% to 98%) | 0/8 (0%; 0% to 32%) | 1/8 (12%; 2% to 47%) |
| undefined-acronym | near misses | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) |

Fleiss' kappa over the twelve (77 complete findings, 0 incomplete): c/d/w 0.25, c against not 0.33, accepted against not 0.29; unprimed c against not 0.24 (77 complete).

### html

37 findings, 12 near misses.

| Rule | Kind | Accepted | Present | Unprimed c | Unprimed c or d |
| --- | --- | --- | --- | --- | --- |
| stacked-nouns | findings | 1/8 (12%; 2% to 47%) | 4/8 (50%; 22% to 78%) | 1/8 (12%; 2% to 47%) | 2/8 (25%; 7% to 59%) |
| stacked-nouns | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) |
| long-dependency | findings | 2/3 (67%; 21% to 94%) | 2/3 (67%; 21% to 94%) | 3/3 (100%; 44% to 100%) | 3/3 (100%; 44% to 100%) |
| reduced-object-relative | findings | 1/4 (25%; 5% to 70%) | 2/4 (50%; 15% to 85%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) |
| hyphen-compound | findings | 0/3 (0%; 0% to 56%) | 2/3 (67%; 21% to 94%) | 0/3 (0%; 0% to 56%) | 0/3 (0%; 0% to 56%) |
| inline-list | findings | 1/8 (12%; 2% to 47%) | 7/8 (88%; 53% to 98%) | 1/8 (12%; 2% to 47%) | 2/8 (25%; 7% to 59%) |
| inline-list | near misses | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) |
| inanimate-subject | findings | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) |
| participial-clause | findings | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) |
| nominalization | findings | 0/1 (0%; 0% to 79%) | 1/1 (100%; 21% to 100%) | 0/1 (0%; 0% to 79%) | 0/1 (0%; 0% to 79%) |
| center-embedding | near misses | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) |
| undefined-acronym | findings | 0/4 (0%; 0% to 49%) | 3/4 (75%; 30% to 95%) | 1/4 (25%; 5% to 70%) | 2/4 (50%; 15% to 85%) |
| undefined-acronym | near misses | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) |

Fleiss' kappa over the twelve (37 complete findings, 0 incomplete): c/d/w 0.36, c against not 0.74, accepted against not 0.36; unprimed c against not 0.56 (37 complete).

### doc comments

192 findings, 56 near misses.

| Rule | Kind | Accepted | Present | Unprimed c | Unprimed c or d |
| --- | --- | --- | --- | --- | --- |
| stacked-nouns | findings | 9/28 (32%; 18% to 51%) | 21/28 (75%; 57% to 87%) | 2/28 (7%; 2% to 23%) | 6/28 (21%; 10% to 40%) |
| stacked-nouns | near misses | 0/14 (0%; 0% to 22%) | 0/14 (0%; 0% to 22%) | 0/14 (0%; 0% to 22%) | 2/14 (14%; 4% to 40%) |
| long-dependency | findings | 6/28 (21%; 10% to 40%) | 6/28 (21%; 10% to 40%) | 3/28 (11%; 4% to 27%) | 9/28 (32%; 18% to 51%) |
| long-dependency | near misses | 5/14 (36%; 16% to 61%) | 5/14 (36%; 16% to 61%) | 0/14 (0%; 0% to 22%) | 5/14 (36%; 16% to 61%) |
| reduced-object-relative | findings | 16/27 (59%; 41% to 75%) | 20/27 (74%; 55% to 87%) | 3/27 (11%; 4% to 28%) | 9/27 (33%; 19% to 52%) |
| hyphen-compound | findings | 14/28 (50%; 33% to 67%) | 24/28 (86%; 69% to 94%) | 1/28 (4%; 1% to 18%) | 3/28 (11%; 4% to 27%) |
| inline-list | findings | 1/28 (4%; 1% to 18%) | 9/28 (32%; 18% to 51%) | 3/28 (11%; 4% to 27%) | 6/28 (21%; 10% to 40%) |
| inline-list | near misses | 1/14 (7%; 1% to 31%) | 1/14 (7%; 1% to 31%) | 1/14 (7%; 1% to 31%) | 3/14 (21%; 8% to 48%) |
| inanimate-subject | findings | 0/14 (0%; 0% to 22%) | 6/14 (43%; 21% to 67%) | 0/14 (0%; 0% to 22%) | 1/14 (7%; 1% to 31%) |
| participial-clause | findings | 2/14 (14%; 4% to 40%) | 12/14 (86%; 60% to 96%) | 0/14 (0%; 0% to 22%) | 1/14 (7%; 1% to 31%) |
| nominalization | findings | 3/5 (60%; 23% to 88%) | 3/5 (60%; 23% to 88%) | 1/5 (20%; 4% to 62%) | 2/5 (40%; 12% to 77%) |
| center-embedding | findings | 3/6 (50%; 19% to 81%) | 3/6 (50%; 19% to 81%) | 3/6 (50%; 19% to 81%) | 5/6 (83%; 44% to 97%) |
| center-embedding | near misses | 0/7 (0%; 0% to 35%) | 0/7 (0%; 0% to 35%) | 1/7 (14%; 3% to 51%) | 4/7 (57%; 25% to 84%) |
| undefined-acronym | findings | 1/14 (7%; 1% to 31%) | 13/14 (93%; 69% to 99%) | 1/14 (7%; 1% to 31%) | 3/14 (21%; 8% to 48%) |
| undefined-acronym | near misses | 0/7 (0%; 0% to 35%) | 4/7 (57%; 25% to 84%) | 0/7 (0%; 0% to 35%) | 1/7 (14%; 3% to 51%) |

Fleiss' kappa over the twelve (192 complete findings, 0 incomplete): c/d/w 0.41, c against not 0.59, accepted against not 0.43; unprimed c against not 0.53 (192 complete).

### commit

114 findings, 32 near misses.

| Rule | Kind | Accepted | Present | Unprimed c | Unprimed c or d |
| --- | --- | --- | --- | --- | --- |
| stacked-nouns | findings | 7/16 (44%; 23% to 67%) | 13/16 (81%; 57% to 93%) | 1/16 (6%; 1% to 28%) | 2/16 (12%; 3% to 36%) |
| stacked-nouns | near misses | 0/8 (0%; 0% to 32%) | 1/8 (12%; 2% to 47%) | 0/8 (0%; 0% to 32%) | 1/8 (12%; 2% to 47%) |
| long-dependency | findings | 7/16 (44%; 23% to 67%) | 7/16 (44%; 23% to 67%) | 0/16 (0%; 0% to 19%) | 8/16 (50%; 28% to 72%) |
| long-dependency | near misses | 1/8 (12%; 2% to 47%) | 1/8 (12%; 2% to 47%) | 2/8 (25%; 7% to 59%) | 4/8 (50%; 22% to 78%) |
| reduced-object-relative | findings | 14/16 (88%; 64% to 97%) | 15/16 (94%; 72% to 99%) | 0/16 (0%; 0% to 19%) | 9/16 (56%; 33% to 77%) |
| hyphen-compound | findings | 10/16 (62%; 39% to 82%) | 11/16 (69%; 44% to 86%) | 1/16 (6%; 1% to 28%) | 6/16 (38%; 18% to 61%) |
| inline-list | findings | 6/16 (38%; 18% to 61%) | 9/16 (56%; 33% to 77%) | 0/16 (0%; 0% to 19%) | 4/16 (25%; 10% to 49%) |
| inline-list | near misses | 1/8 (12%; 2% to 47%) | 1/8 (12%; 2% to 47%) | 1/8 (12%; 2% to 47%) | 4/8 (50%; 22% to 78%) |
| inanimate-subject | findings | 0/8 (0%; 0% to 32%) | 4/8 (50%; 22% to 78%) | 1/8 (12%; 2% to 47%) | 4/8 (50%; 22% to 78%) |
| participial-clause | findings | 2/8 (25%; 7% to 59%) | 6/8 (75%; 41% to 93%) | 0/8 (0%; 0% to 32%) | 3/8 (38%; 14% to 69%) |
| nominalization | findings | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) |
| center-embedding | findings | 3/8 (38%; 14% to 69%) | 4/8 (50%; 22% to 78%) | 3/8 (38%; 14% to 69%) | 6/8 (75%; 41% to 93%) |
| center-embedding | near misses | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 3/4 (75%; 30% to 95%) |
| undefined-acronym | findings | 1/8 (12%; 2% to 47%) | 8/8 (100%; 68% to 100%) | 1/8 (12%; 2% to 47%) | 3/8 (38%; 14% to 69%) |
| undefined-acronym | near misses | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) |

Fleiss' kappa over the twelve (114 complete findings, 0 incomplete): c/d/w 0.38, c against not 0.45, accepted against not 0.43; unprimed c against not 0.40 (114 complete).

### pr

114 findings, 32 near misses.

| Rule | Kind | Accepted | Present | Unprimed c | Unprimed c or d |
| --- | --- | --- | --- | --- | --- |
| stacked-nouns | findings | 10/16 (62%; 39% to 82%) | 15/16 (94%; 72% to 99%) | 0/16 (0%; 0% to 19%) | 1/16 (6%; 1% to 28%) |
| stacked-nouns | near misses | 0/8 (0%; 0% to 32%) | 0/8 (0%; 0% to 32%) | 0/8 (0%; 0% to 32%) | 1/8 (12%; 2% to 47%) |
| long-dependency | findings | 7/16 (44%; 23% to 67%) | 8/16 (50%; 28% to 72%) | 2/16 (12%; 3% to 36%) | 6/16 (38%; 18% to 61%) |
| long-dependency | near misses | 1/8 (12%; 2% to 47%) | 3/8 (38%; 14% to 69%) | 0/8 (0%; 0% to 32%) | 1/8 (12%; 2% to 47%) |
| reduced-object-relative | findings | 4/16 (25%; 10% to 49%) | 7/16 (44%; 23% to 67%) | 1/16 (6%; 1% to 28%) | 8/16 (50%; 28% to 72%) |
| hyphen-compound | findings | 11/16 (69%; 44% to 86%) | 13/16 (81%; 57% to 93%) | 0/16 (0%; 0% to 19%) | 3/16 (19%; 7% to 43%) |
| inline-list | findings | 6/16 (38%; 18% to 61%) | 11/16 (69%; 44% to 86%) | 2/16 (12%; 3% to 36%) | 6/16 (38%; 18% to 61%) |
| inline-list | near misses | 2/8 (25%; 7% to 59%) | 2/8 (25%; 7% to 59%) | 0/8 (0%; 0% to 32%) | 2/8 (25%; 7% to 59%) |
| inanimate-subject | findings | 0/8 (0%; 0% to 32%) | 2/8 (25%; 7% to 59%) | 1/8 (12%; 2% to 47%) | 2/8 (25%; 7% to 59%) |
| participial-clause | findings | 3/8 (38%; 14% to 69%) | 7/8 (88%; 53% to 98%) | 0/8 (0%; 0% to 32%) | 2/8 (25%; 7% to 59%) |
| nominalization | findings | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) |
| center-embedding | findings | 4/8 (50%; 22% to 78%) | 5/8 (62%; 31% to 86%) | 1/8 (12%; 2% to 47%) | 5/8 (62%; 31% to 86%) |
| center-embedding | near misses | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 0/4 (0%; 0% to 49%) | 3/4 (75%; 30% to 95%) |
| undefined-acronym | findings | 1/8 (12%; 2% to 47%) | 7/8 (88%; 53% to 98%) | 1/8 (12%; 2% to 47%) | 2/8 (25%; 7% to 59%) |
| undefined-acronym | near misses | 1/4 (25%; 5% to 70%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) |

Fleiss' kappa over the twelve (114 complete findings, 0 incomplete): c/d/w 0.42, c against not 0.24, accepted against not 0.45; unprimed c against not 0.48 (114 complete).

## Random decoys

| Family | c | Accepted | Present | Unprimed c |
| --- | --- | --- | --- | --- |
| md | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) |
| rst | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) |
| html | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) |
| doc comments | 0/7 (0%; 0% to 35%) | 0/7 (0%; 0% to 35%) | 0/7 (0%; 0% to 35%) | 0/7 (0%; 0% to 35%) |
| commit | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) |
| pr | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) |
| all | 0/25 (0%; 0% to 13%) | 0/25 (0%; 0% to 13%) | 0/25 (0%; 0% to 13%) | 0/25 (0%; 0% to 13%) |

## Pooled over families

| Rule | Findings, c | Near, c | c difference | Findings, accepted | Near, accepted | Accepted difference | Unprimed c over decoys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | 0/100 (0%; 0% to 4%) | 0/50 (0%; 0% to 7%) | +0 points (-7 to +4) | 36/100 (36%; 27% to 46%) | 0/50 (0%; 0% to 7%) | +36 points (+25 to +46) | +4 points (-10 to +10) |
| long-dependency | 5/91 (5%; 2% to 12%) | 0/46 (0%; 0% to 8%) | +5 points (-3 to +12) | 28/91 (31%; 22% to 41%) | 15/46 (33%; 21% to 47%) | -2 points (-19 to +14) | +9 points (-5 to +16) |
| reduced-object-relative | 4/85 (5%; 2% to 11%) | - | - | 43/85 (51%; 40% to 61%) | - | - | +7 points (-7 to +15) |
| hyphen-compound | 0/87 (0%; 0% to 4%) | - | - | 42/87 (48%; 38% to 59%) | - | - | +2 points (-11 to +8) |
| inline-list | 5/100 (5%; 2% to 11%) | 1/50 (2%; 0% to 10%) | +3 points (-6 to +9) | 21/100 (21%; 14% to 30%) | 6/50 (12%; 6% to 24%) | +9 points (-5 to +20) | +8 points (-6 to +15) |
| inanimate-subject | 0/42 (0%; 0% to 8%) | - | - | 0/42 (0%; 0% to 8%) | - | - | +10 points (-5 to +22) |
| participial-clause | 0/50 (0%; 0% to 7%) | - | - | 16/50 (32%; 21% to 46%) | - | - | +0 points (-13 to +7) |
| nominalization | 2/19 (11%; 3% to 31%) | - | - | 13/19 (68%; 46% to 85%) | - | - | +5 points (-9 to +25) |
| center-embedding | 4/30 (13%; 5% to 30%) | 0/25 (0%; 0% to 13%) | +13 points (-2 to +30) | 13/30 (43%; 27% to 61%) | 2/25 (8%; 2% to 25%) | +35 points (+12 to +54) | +27 points (+8 to +44) |
| undefined-acronym | 0/50 (0%; 0% to 7%) | 0/25 (0%; 0% to 13%) | +0 points (-13 to +7) | 4/50 (8%; 3% to 19%) | 2/25 (8%; 2% to 25%) | +0 points (-18 to +12) | +8 points (-6 to +19) |

## Per model (majority of its three), findings pooled over families

| Rule | Opus 5.5 c | Opus 5.5 accepted | Sonnet 5.5 c | Sonnet 5.5 accepted | Haiku 5.5 c | Haiku 5.5 accepted | Fable 5.2 c | Fable 5.2 accepted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | 0/100 (0%; 0% to 4%) | 22/100 (22%; 15% to 31%) | 1/100 (1%; 0% to 5%) | 66/100 (66%; 56% to 75%) | 0/100 (0%; 0% to 4%) | 12/100 (12%; 7% to 20%) | 2/100 (2%; 1% to 7%) | 67/100 (67%; 57% to 75%) |
| long-dependency | 7/91 (8%; 4% to 15%) | 30/91 (33%; 24% to 43%) | 10/91 (11%; 6% to 19%) | 42/91 (46%; 36% to 56%) | 3/91 (3%; 1% to 9%) | 28/91 (31%; 22% to 41%) | 5/91 (5%; 2% to 12%) | 27/91 (30%; 21% to 40%) |
| reduced-object-relative | 4/85 (5%; 2% to 11%) | 16/85 (19%; 12% to 28%) | 4/85 (5%; 2% to 11%) | 56/85 (66%; 55% to 75%) | 5/85 (6%; 3% to 13%) | 30/85 (35%; 26% to 46%) | 10/85 (12%; 7% to 20%) | 57/85 (67%; 57% to 76%) |
| hyphen-compound | 0/87 (0%; 0% to 4%) | 28/87 (32%; 23% to 43%) | 0/87 (0%; 0% to 4%) | 59/87 (68%; 57% to 77%) | 0/87 (0%; 0% to 4%) | 30/87 (34%; 25% to 45%) | 0/87 (0%; 0% to 4%) | 61/87 (70%; 60% to 79%) |
| inline-list | 5/100 (5%; 2% to 11%) | 19/100 (19%; 13% to 28%) | 5/100 (5%; 2% to 11%) | 22/100 (22%; 15% to 31%) | 5/100 (5%; 2% to 11%) | 24/100 (24%; 17% to 33%) | 7/100 (7%; 3% to 14%) | 56/100 (56%; 46% to 65%) |
| inanimate-subject | 0/42 (0%; 0% to 8%) | 6/42 (14%; 7% to 28%) | 0/42 (0%; 0% to 8%) | 7/42 (17%; 8% to 31%) | 0/42 (0%; 0% to 8%) | 1/42 (2%; 0% to 12%) | 0/42 (0%; 0% to 8%) | 2/42 (5%; 1% to 16%) |
| participial-clause | 1/50 (2%; 0% to 10%) | 17/50 (34%; 22% to 48%) | 0/50 (0%; 0% to 7%) | 18/50 (36%; 24% to 50%) | 0/50 (0%; 0% to 7%) | 1/50 (2%; 0% to 10%) | 4/50 (8%; 3% to 19%) | 38/50 (76%; 63% to 86%) |
| nominalization | 4/19 (21%; 9% to 43%) | 13/19 (68%; 46% to 85%) | 1/19 (5%; 1% to 25%) | 13/19 (68%; 46% to 85%) | 0/19 (0%; 0% to 17%) | 15/19 (79%; 57% to 91%) | 7/19 (37%; 19% to 59%) | 13/19 (68%; 46% to 85%) |
| center-embedding | 6/30 (20%; 10% to 37%) | 10/30 (33%; 19% to 51%) | 8/30 (27%; 14% to 44%) | 22/30 (73%; 56% to 86%) | 4/30 (13%; 5% to 30%) | 18/30 (60%; 42% to 75%) | 5/30 (17%; 7% to 34%) | 9/30 (30%; 17% to 48%) |
| undefined-acronym | 0/50 (0%; 0% to 7%) | 5/50 (10%; 4% to 21%) | 0/50 (0%; 0% to 7%) | 6/50 (12%; 6% to 24%) | 0/50 (0%; 0% to 7%) | 9/50 (18%; 10% to 31%) | 2/50 (4%; 1% to 13%) | 6/50 (12%; 6% to 24%) |

## Doc comments by language (small n; decides nothing)

| Stratum | Rule | Findings, c | Findings, accepted | Present | Near, c |
| --- | --- | --- | --- | --- | --- |
| src-py | stacked-nouns | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | 2/4 (50%; 15% to 85%) | 0/2 (0%; 0% to 66%) |
| src-py | long-dependency | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 0/2 (0%; 0% to 66%) |
| src-py | reduced-object-relative | 1/4 (25%; 5% to 70%) | 3/4 (75%; 30% to 95%) | 3/4 (75%; 30% to 95%) | none |
| src-py | hyphen-compound | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | 4/4 (100%; 51% to 100%) | none |
| src-py | inline-list | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 4/4 (100%; 51% to 100%) | 0/2 (0%; 0% to 66%) |
| src-py | inanimate-subject | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | none |
| src-py | participial-clause | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | none |
| src-py | undefined-acronym | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | 0/1 (0%; 0% to 79%) |
| src-rs | stacked-nouns | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 4/4 (100%; 51% to 100%) | 0/2 (0%; 0% to 66%) |
| src-rs | long-dependency | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/2 (0%; 0% to 66%) |
| src-rs | reduced-object-relative | 1/4 (25%; 5% to 70%) | 2/4 (50%; 15% to 85%) | 3/4 (75%; 30% to 95%) | none |
| src-rs | hyphen-compound | 0/4 (0%; 0% to 49%) | 4/4 (100%; 51% to 100%) | 4/4 (100%; 51% to 100%) | none |
| src-rs | inline-list | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 0/2 (0%; 0% to 66%) |
| src-rs | inanimate-subject | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | none |
| src-rs | participial-clause | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | 2/2 (100%; 34% to 100%) | none |
| src-rs | nominalization | 0/1 (0%; 0% to 79%) | 0/1 (0%; 0% to 79%) | 0/1 (0%; 0% to 79%) | none |
| src-rs | center-embedding | 0/1 (0%; 0% to 79%) | 1/1 (100%; 21% to 100%) | 1/1 (100%; 21% to 100%) | 0/1 (0%; 0% to 79%) |
| src-rs | undefined-acronym | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | 0/1 (0%; 0% to 79%) |
| src-go | stacked-nouns | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | 0/2 (0%; 0% to 66%) |
| src-go | long-dependency | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 0/2 (0%; 0% to 66%) |
| src-go | reduced-object-relative | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | 2/4 (50%; 15% to 85%) | none |
| src-go | hyphen-compound | 0/4 (0%; 0% to 49%) | 3/4 (75%; 30% to 95%) | 3/4 (75%; 30% to 95%) | none |
| src-go | inline-list | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/2 (0%; 0% to 66%) |
| src-go | inanimate-subject | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | none |
| src-go | participial-clause | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | none |
| src-go | undefined-acronym | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | 2/2 (100%; 34% to 100%) | 0/1 (0%; 0% to 79%) |
| src-js | stacked-nouns | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 3/4 (75%; 30% to 95%) | 0/2 (0%; 0% to 66%) |
| src-js | long-dependency | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/2 (0%; 0% to 66%) |
| src-js | reduced-object-relative | 0/3 (0%; 0% to 56%) | 2/3 (67%; 21% to 94%) | 2/3 (67%; 21% to 94%) | none |
| src-js | hyphen-compound | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | none |
| src-js | inline-list | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 2/4 (50%; 15% to 85%) | 0/2 (0%; 0% to 66%) |
| src-js | inanimate-subject | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | none |
| src-js | participial-clause | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | none |
| src-js | center-embedding | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | 0/1 (0%; 0% to 79%) |
| src-js | undefined-acronym | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | 0/1 (0%; 0% to 79%) |
| src-jvm | stacked-nouns | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | 3/4 (75%; 30% to 95%) | 0/2 (0%; 0% to 66%) |
| src-jvm | long-dependency | 1/4 (25%; 5% to 70%) | 2/4 (50%; 15% to 85%) | 2/4 (50%; 15% to 85%) | 0/2 (0%; 0% to 66%) |
| src-jvm | reduced-object-relative | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | 3/4 (75%; 30% to 95%) | none |
| src-jvm | hyphen-compound | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 4/4 (100%; 51% to 100%) | none |
| src-jvm | inline-list | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/2 (0%; 0% to 66%) |
| src-jvm | inanimate-subject | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | none |
| src-jvm | participial-clause | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | none |
| src-jvm | nominalization | 0/1 (0%; 0% to 79%) | 1/1 (100%; 21% to 100%) | 1/1 (100%; 21% to 100%) | none |
| src-jvm | center-embedding | 0/1 (0%; 0% to 79%) | 0/1 (0%; 0% to 79%) | 0/1 (0%; 0% to 79%) | 0/1 (0%; 0% to 79%) |
| src-jvm | undefined-acronym | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | 0/1 (0%; 0% to 79%) |
| src-c | stacked-nouns | 0/4 (0%; 0% to 49%) | 3/4 (75%; 30% to 95%) | 3/4 (75%; 30% to 95%) | 0/2 (0%; 0% to 66%) |
| src-c | long-dependency | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 0/2 (0%; 0% to 66%) |
| src-c | reduced-object-relative | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | 3/4 (75%; 30% to 95%) | none |
| src-c | hyphen-compound | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | 4/4 (100%; 51% to 100%) | none |
| src-c | inline-list | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/2 (0%; 0% to 66%) |
| src-c | inanimate-subject | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | none |
| src-c | participial-clause | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | 2/2 (100%; 34% to 100%) | none |
| src-c | nominalization | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | none |
| src-c | undefined-acronym | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | 0/1 (0%; 0% to 79%) |
| src-rb | stacked-nouns | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 4/4 (100%; 51% to 100%) | 0/2 (0%; 0% to 66%) |
| src-rb | long-dependency | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 0/2 (0%; 0% to 66%) |
| src-rb | reduced-object-relative | 1/4 (25%; 5% to 70%) | 3/4 (75%; 30% to 95%) | 4/4 (100%; 51% to 100%) | none |
| src-rb | hyphen-compound | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | 4/4 (100%; 51% to 100%) | none |
| src-rb | inline-list | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | 0/2 (0%; 0% to 66%) |
| src-rb | inanimate-subject | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | none |
| src-rb | participial-clause | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | none |
| src-rb | nominalization | 0/1 (0%; 0% to 79%) | 1/1 (100%; 21% to 100%) | 1/1 (100%; 21% to 100%) | none |
| src-rb | center-embedding | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | 0/1 (0%; 0% to 79%) |
| src-rb | undefined-acronym | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | 0/1 (0%; 0% to 79%) |

## Decisions

- stacked-nouns (all): the threshold earns its place. accepted: findings 36%, 27% to 46%, near misses 0%, 0% to 7%, difference +36 points (+25 to +46); too little c to compare, so accepted shares are used.
- inline-list (all): threshold not supported by these labels. accepted: findings 21%, 14% to 30%, near misses 12%, 6% to 24%, difference +9 points (-5 to +20); too little c to compare, so accepted shares are used.
- long-dependency (all): threshold not supported by these labels. accepted: findings 31%, 22% to 41%, near misses 33%, 21% to 47%, difference -2 points (-19 to +14); too little c to compare, so accepted shares are used.
- center-embedding (all): threshold not supported by these labels. c: findings 13%, 5% to 30%, near misses 0%, 0% to 13%, difference +13 points (-2 to +30).
- undefined-acronym (all): threshold not supported by these labels. accepted: findings 8%, 3% to 19%, near misses 8%, 2% to 25%, difference +0 points (-18 to +12); too little c to compare, so accepted shares are used.
- long-dependency (rst): detection problem in this format. present 8%, 1% to 35%.
- long-dependency (doc comments): detection problem in this format. present 21%, 10% to 40%.
- inline-list (doc comments): proposed off for doc comments. accepted 4%, 1% to 18%; against md -28 points (-52 to -6).
- inanimate-subject (doc comments): low here but not distinguishable from Markdown. accepted 0%, 0% to 22%; against md n/a.
- stacked-nouns (all): no better than chance placement without priming. unprimed c 4%, 2% to 10%; over random decoys +4 points (-10 to +10).
- long-dependency (all): no better than chance placement without priming. unprimed c 9%, 5% to 16%; over random decoys +9 points (-5 to +16).
- reduced-object-relative (all): no better than chance placement without priming. unprimed c 7%, 3% to 15%; over random decoys +7 points (-7 to +15).
- hyphen-compound (all): no better than chance placement without priming. unprimed c 2%, 1% to 8%; over random decoys +2 points (-11 to +8).
- inline-list (all): no better than chance placement without priming. unprimed c 8%, 4% to 15%; over random decoys +8 points (-6 to +15).
- inanimate-subject (all): no better than chance placement without priming. unprimed c 10%, 4% to 22%; over random decoys +10 points (-5 to +22).
- participial-clause (all): no better than chance placement without priming. unprimed c 0%, 0% to 7%; over random decoys +0 points (-13 to +7).
- nominalization (all): no better than chance placement without priming. unprimed c 5%, 1% to 25%; over random decoys +5 points (-9 to +25).
- undefined-acronym (all): no better than chance placement without priming. unprimed c 8%, 3% to 19%; over random decoys +8 points (-6 to +19).
