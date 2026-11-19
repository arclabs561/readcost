# Precision by kind of document: results

Computed by `scripts/kinds_report.py` as `docs/prereg/kinds-precision.md` fixes it. c: at least 7 of the 12 primed raters label the item c; accepted: at least 7 label it c or d; present: at least 7 say the construction is there; unprimed c (c or d): at least 2 of the 3 unprimed raters label it c (c or d). Wilson 95% intervals; differences with Newcombe 95% intervals. Pooled means the ten technical strata (the contrast stratum left out).

## Counts

| Stratum | Findings (deduplicated) | Near misses (deduplicated) | Sampled findings | Sampled near misses | Decoys | Ranked documents | Ranked items |
| --- | --- | --- | --- | --- | --- | --- | --- |
| tutorial | 2536 (2401) | 7761 (6475) | 76 | 16 | 16 | 20 | 50 |
| reference | 3053 (2874) | 9237 (7453) | 78 | 16 | 16 | 20 | 53 |
| explanation | 2944 (2807) | 8620 (6623) | 77 | 16 | 16 | 20 | 52 |
| design | 1651 (1567) | 4795 (3912) | 79 | 16 | 16 | 20 | 52 |
| runbook | 546 (519) | 1639 (1326) | 69 | 16 | 16 | 13 | 32 |
| changelog | 20796 (19642) | 49863 (41206) | 80 | 16 | 16 | 20 | 55 |
| blog | 1004 (935) | 2511 (1999) | 76 | 16 | 16 | 19 | 49 |
| standards | 2498 (2118) | 4287 (3520) | 76 | 16 | 16 | 20 | 53 |
| code-doc | 1159 (1072) | 3393 (2720) | 66 | 12 | 16 | 20 | 50 |
| code-ordinary | 1721 (1512) | 4820 (3824) | 65 | 12 | 16 | 20 | 46 |
| contrast | 499 (479) | 1206 (1026) | 67 | 16 | 16 | 20 | 49 |

Steps before the draw: {"_texts": {"blog: kept": 91, "blog: mostly code": 14, "blog: not English": 1, "blog: under 100 words": 28, "changelog: duplicate text": 5, "changelog: kept": 417, "changelog: mostly code": 6, "changelog: not English": 20, "changelog: under 100 words": 115, "code-doc: duplicate text": 18, "code-doc: kept": 804, "code-doc: not English": 13, "code-doc: too large": 10, "code-doc: under 40 words": 1368, "code-ordinary: check error": 2, "code-ordinary: duplicate text": 24, "code-ordinary: kept": 909, "code-ordinary: not English": 17, "code-ordinary: too large": 12, "code-ordinary: under 40 words": 1249, "contrast: kept": 38, "contrast: under 100 words": 2, "design: kept": 121, "design: mostly code": 32, "design: not English": 12, "design: under 100 words": 13, "explanation: duplicate text": 1, "explanation: kept": 235, "explanation: mostly code": 34, "explanation: not English": 16, "explanation: under 100 words": 56, "reference: check error": 1, "reference: duplicate text": 3, "reference: kept": 235, "reference: mostly code": 78, "reference: not English": 23, "reference: under 100 words": 201, "runbook: kept": 59, "runbook: mostly code": 3, "runbook: not English": 5, "runbook: under 100 words": 21, "standards: kept": 34, "standards: mostly code": 3, "standards: under 100 words": 2, "tutorial: duplicate text": 3, "tutorial: kept": 299, "tutorial: mostly code": 122, "tutorial: not English": 41, "tutorial: under 100 words": 124}, "_texts_by_source": {"blog: named": 52, "blog: walk": 39, "changelog: named": 6, "changelog: walk": 411, "code-doc: walk": 804, "code-ordinary: walk": 909, "contrast: contrast": 38, "design: named": 34, "design: walk": 87, "explanation: named": 52, "explanation: walk": 183, "reference: named": 23, "reference: walk": 212, "runbook: codesearch": 4, "runbook: named": 40, "runbook: walk": 15, "standards: standards": 34, "tutorial: named": 39, "tutorial: walk": 260}, "_jobs": {"walk": {"a: in a development corpus": 19, "a: owner cap": 18, "a: named source": 1, "b: owner cap": 23, "b: in a development corpus": 1, "standards: owner cap": 3}, "picked": {"walk": 1000, "standards": 80, "contrast": 1, "named": 7, "codesearch": 3}}, "_repos": {"walk: ok": 1000, "standards: fetch error": 5, "standards: ok": 75, "named: ok": 7, "contrast: ok": 1, "codesearch: ok": 3}}

## Primary: c share of findings beside near misses

| Stratum | Rule | Findings, c | Near misses, c | Difference |
| --- | --- | --- | --- | --- |
| tutorial | stacked-nouns | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| tutorial | long-dependency | 1/12 (8%; 1% to 35%) | 0/4 (0%; 0% to 49%) | +8 points (-41 to +35) |
| tutorial | reduced-object-relative | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| tutorial | hyphen-compound | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| tutorial | inline-list | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| tutorial | inanimate-subject | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| tutorial | participial-clause | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| tutorial | nominalization | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| tutorial | center-embedding | none | 0/2 (0%; 0% to 66%) | n/a |
| tutorial | undefined-acronym | 0/4 (0%; 0% to 49%) | 0/2 (0%; 0% to 66%) | +0 points (-66 to +49) |
| reference | stacked-nouns | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| reference | long-dependency | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| reference | reduced-object-relative | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| reference | hyphen-compound | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| reference | inline-list | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| reference | inanimate-subject | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| reference | participial-clause | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| reference | nominalization | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| reference | center-embedding | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | -50 points (-91 to +27) |
| reference | undefined-acronym | 0/4 (0%; 0% to 49%) | 0/2 (0%; 0% to 66%) | +0 points (-66 to +49) |
| explanation | stacked-nouns | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| explanation | long-dependency | 2/12 (17%; 5% to 45%) | 0/4 (0%; 0% to 49%) | +17 points (-34 to +45) |
| explanation | reduced-object-relative | 1/12 (8%; 1% to 35%) | no threshold | n/a |
| explanation | hyphen-compound | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| explanation | inline-list | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| explanation | inanimate-subject | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| explanation | participial-clause | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| explanation | nominalization | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| explanation | center-embedding | 1/1 (100%; 21% to 100%) | 0/2 (0%; 0% to 66%) | +100 points (-3 to +100) |
| explanation | undefined-acronym | 0/4 (0%; 0% to 49%) | 0/2 (0%; 0% to 66%) | +0 points (-66 to +49) |
| design | stacked-nouns | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| design | long-dependency | 1/12 (8%; 1% to 35%) | 0/4 (0%; 0% to 49%) | +8 points (-41 to +35) |
| design | reduced-object-relative | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| design | hyphen-compound | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| design | inline-list | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| design | inanimate-subject | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| design | participial-clause | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| design | nominalization | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| design | center-embedding | 0/3 (0%; 0% to 56%) | 0/2 (0%; 0% to 66%) | +0 points (-66 to +56) |
| design | undefined-acronym | 0/4 (0%; 0% to 49%) | 0/2 (0%; 0% to 66%) | +0 points (-66 to +49) |
| runbook | stacked-nouns | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| runbook | long-dependency | 0/11 (0%; 0% to 26%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +26) |
| runbook | reduced-object-relative | 0/8 (0%; 0% to 32%) | no threshold | n/a |
| runbook | hyphen-compound | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| runbook | inline-list | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| runbook | inanimate-subject | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| runbook | participial-clause | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| runbook | nominalization | 0/2 (0%; 0% to 66%) | no threshold | n/a |
| runbook | center-embedding | none | 0/2 (0%; 0% to 66%) | n/a |
| runbook | undefined-acronym | 0/4 (0%; 0% to 49%) | 0/2 (0%; 0% to 66%) | +0 points (-66 to +49) |
| changelog | stacked-nouns | 1/12 (8%; 1% to 35%) | 0/4 (0%; 0% to 49%) | +8 points (-41 to +35) |
| changelog | long-dependency | 1/12 (8%; 1% to 35%) | 0/4 (0%; 0% to 49%) | +8 points (-41 to +35) |
| changelog | reduced-object-relative | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| changelog | hyphen-compound | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| changelog | inline-list | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| changelog | inanimate-subject | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| changelog | participial-clause | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| changelog | nominalization | 1/4 (25%; 5% to 70%) | no threshold | n/a |
| changelog | center-embedding | 2/4 (50%; 15% to 85%) | 0/2 (0%; 0% to 66%) | +50 points (-24 to +85) |
| changelog | undefined-acronym | 0/4 (0%; 0% to 49%) | 0/2 (0%; 0% to 66%) | +0 points (-66 to +49) |
| blog | stacked-nouns | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| blog | long-dependency | 4/12 (33%; 14% to 61%) | 0/4 (0%; 0% to 49%) | +33 points (-19 to +61) |
| blog | reduced-object-relative | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| blog | hyphen-compound | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| blog | inline-list | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| blog | inanimate-subject | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| blog | participial-clause | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| blog | nominalization | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| blog | center-embedding | none | 0/2 (0%; 0% to 66%) | n/a |
| blog | undefined-acronym | 0/4 (0%; 0% to 49%) | 0/2 (0%; 0% to 66%) | +0 points (-66 to +49) |
| standards | stacked-nouns | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| standards | long-dependency | 3/12 (25%; 9% to 53%) | 0/4 (0%; 0% to 49%) | +25 points (-27 to +53) |
| standards | reduced-object-relative | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| standards | hyphen-compound | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| standards | inline-list | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| standards | inanimate-subject | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| standards | participial-clause | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| standards | nominalization | 1/4 (25%; 5% to 70%) | no threshold | n/a |
| standards | center-embedding | none | 0/2 (0%; 0% to 66%) | n/a |
| standards | undefined-acronym | 0/4 (0%; 0% to 49%) | 0/2 (0%; 0% to 66%) | +0 points (-66 to +49) |
| code-doc | stacked-nouns | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| code-doc | long-dependency | 3/12 (25%; 9% to 53%) | 0/4 (0%; 0% to 49%) | +25 points (-27 to +53) |
| code-doc | reduced-object-relative | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| code-doc | hyphen-compound | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| code-doc | inanimate-subject | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| code-doc | participial-clause | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| code-doc | nominalization | 0/3 (0%; 0% to 56%) | no threshold | n/a |
| code-doc | center-embedding | 1/3 (33%; 6% to 79%) | 0/2 (0%; 0% to 66%) | +33 points (-38 to +79) |
| code-doc | undefined-acronym | 0/4 (0%; 0% to 49%) | 0/2 (0%; 0% to 66%) | +0 points (-66 to +49) |
| code-ordinary | stacked-nouns | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| code-ordinary | long-dependency | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| code-ordinary | reduced-object-relative | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| code-ordinary | hyphen-compound | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| code-ordinary | inanimate-subject | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| code-ordinary | participial-clause | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| code-ordinary | nominalization | 0/2 (0%; 0% to 66%) | no threshold | n/a |
| code-ordinary | center-embedding | 0/3 (0%; 0% to 56%) | 0/2 (0%; 0% to 66%) | +0 points (-66 to +56) |
| code-ordinary | undefined-acronym | 0/4 (0%; 0% to 49%) | 0/2 (0%; 0% to 66%) | +0 points (-66 to +49) |
| contrast | stacked-nouns | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| contrast | long-dependency | 2/12 (17%; 5% to 45%) | 0/4 (0%; 0% to 49%) | +17 points (-34 to +45) |
| contrast | reduced-object-relative | 0/12 (0%; 0% to 24%) | no threshold | n/a |
| contrast | hyphen-compound | 0/2 (0%; 0% to 66%) | no threshold | n/a |
| contrast | inline-list | 0/12 (0%; 0% to 24%) | 0/4 (0%; 0% to 49%) | +0 points (-49 to +24) |
| contrast | inanimate-subject | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| contrast | participial-clause | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| contrast | nominalization | 0/4 (0%; 0% to 49%) | no threshold | n/a |
| contrast | center-embedding | 0/1 (0%; 0% to 79%) | 0/2 (0%; 0% to 66%) | +0 points (-66 to +79) |
| contrast | undefined-acronym | 0/4 (0%; 0% to 49%) | 0/2 (0%; 0% to 66%) | +0 points (-66 to +49) |

## Secondary, per stratum

### tutorial

76 findings, 16 near misses; random decoys: unprimed c 0/16 (0%; 0% to 19%), unprimed c or d 3/16 (19%; 7% to 43%).

| Rule | Item | Accepted | Present | Unprimed c | Unprimed c or d | Unprimed c over decoys | Unprimed c or d over decoys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | findings | 5/12 (42%; 19% to 68%) | 9/12 (75%; 47% to 91%) | 0/12 (0%; 0% to 24%) | 3/12 (25%; 9% to 53%) | +0 points (-19 to +24) | +6 points (-23 to +37) |
| stacked-nouns | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | - | - |
| long-dependency | findings | 4/12 (33%; 14% to 61%) | 4/12 (33%; 14% to 61%) | 0/12 (0%; 0% to 24%) | 4/12 (33%; 14% to 61%) | +0 points (-19 to +24) | +15 points (-17 to +45) |
| long-dependency | near misses | 3/4 (75%; 30% to 95%) | 3/4 (75%; 30% to 95%) | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | - | - |
| reduced-object-relative | findings | 3/12 (25%; 9% to 53%) | 5/12 (42%; 19% to 68%) | 1/12 (8%; 1% to 35%) | 4/12 (33%; 14% to 61%) | +8 points (-12 to +35) | +15 points (-17 to +45) |
| hyphen-compound | findings | 5/12 (42%; 19% to 68%) | 9/12 (75%; 47% to 91%) | 0/12 (0%; 0% to 24%) | 1/12 (8%; 1% to 35%) | +0 points (-19 to +24) | -10 points (-36 to +19) |
| inline-list | findings | 1/12 (8%; 1% to 35%) | 8/12 (67%; 39% to 86%) | 0/12 (0%; 0% to 24%) | 4/12 (33%; 14% to 61%) | +0 points (-19 to +24) | +15 points (-17 to +45) |
| inline-list | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | - | - |
| inanimate-subject | findings | 0/4 (0%; 0% to 49%) | 3/4 (75%; 30% to 95%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | +0 points (-19 to +49) | +6 points (-25 to +53) |
| participial-clause | findings | 1/4 (25%; 5% to 70%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | +0 points (-19 to +49) | -19 points (-43 to +32) |
| nominalization | findings | 3/4 (75%; 30% to 95%) | 3/4 (75%; 30% to 95%) | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | +0 points (-19 to +49) | +31 points (-11 to +68) |
| center-embedding | near misses | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | - | - |
| undefined-acronym | findings | 2/4 (50%; 15% to 85%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | +0 points (-19 to +49) | +6 points (-25 to +53) |
| undefined-acronym | near misses | 1/2 (50%; 9% to 91%) | 2/2 (100%; 34% to 100%) | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | - | - |

Fleiss' kappa over the twelve (76 complete findings, 0 incomplete): c/d/w 0.30, c against not 0.24, accepted against not 0.35; unprimed c against not 0.31 (76 complete).

### reference

78 findings, 16 near misses; random decoys: unprimed c 0/16 (0%; 0% to 19%), unprimed c or d 1/16 (6%; 1% to 28%).

| Rule | Item | Accepted | Present | Unprimed c | Unprimed c or d | Unprimed c over decoys | Unprimed c or d over decoys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | findings | 4/12 (33%; 14% to 61%) | 10/12 (83%; 55% to 95%) | 0/12 (0%; 0% to 24%) | 1/12 (8%; 1% to 35%) | +0 points (-19 to +24) | +2 points (-21 to +30) |
| stacked-nouns | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | - | - |
| long-dependency | findings | 5/12 (42%; 19% to 68%) | 7/12 (58%; 32% to 81%) | 0/12 (0%; 0% to 24%) | 2/12 (17%; 5% to 45%) | +0 points (-19 to +24) | +10 points (-15 to +39) |
| long-dependency | near misses | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | - | - |
| reduced-object-relative | findings | 5/12 (42%; 19% to 68%) | 7/12 (58%; 32% to 81%) | 0/12 (0%; 0% to 24%) | 4/12 (33%; 14% to 61%) | +0 points (-19 to +24) | +27 points (-2 to +55) |
| hyphen-compound | findings | 5/12 (42%; 19% to 68%) | 11/12 (92%; 65% to 99%) | 0/12 (0%; 0% to 24%) | 1/12 (8%; 1% to 35%) | +0 points (-19 to +24) | +2 points (-21 to +30) |
| inline-list | findings | 1/12 (8%; 1% to 35%) | 7/12 (58%; 32% to 81%) | 0/12 (0%; 0% to 24%) | 3/12 (25%; 9% to 53%) | +0 points (-19 to +24) | +19 points (-9 to +47) |
| inline-list | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | - | - |
| inanimate-subject | findings | 1/4 (25%; 5% to 70%) | 2/4 (50%; 15% to 85%) | 0/4 (0%; 0% to 49%) | 3/4 (75%; 30% to 95%) | +0 points (-19 to +49) | +69 points (+19 to +90) |
| participial-clause | findings | 2/4 (50%; 15% to 85%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | +0 points (-19 to +49) | +44 points (+2 to +79) |
| nominalization | findings | 4/4 (100%; 51% to 100%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | +0 points (-19 to +49) | +19 points (-11 to +64) |
| center-embedding | findings | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | +50 points (+5 to +91) | +44 points (-2 to +85) |
| center-embedding | near misses | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | - | - |
| undefined-acronym | findings | 2/4 (50%; 15% to 85%) | 3/4 (75%; 30% to 95%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | +0 points (-19 to +49) | +19 points (-11 to +64) |
| undefined-acronym | near misses | 1/2 (50%; 9% to 91%) | 2/2 (100%; 34% to 100%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | - | - |

Fleiss' kappa over the twelve (78 complete findings, 0 incomplete): c/d/w 0.35, c against not 0.20, accepted against not 0.38; unprimed c against not 0.35 (78 complete).

### explanation

77 findings, 16 near misses; random decoys: unprimed c 0/16 (0%; 0% to 19%), unprimed c or d 1/16 (6%; 1% to 28%).

| Rule | Item | Accepted | Present | Unprimed c | Unprimed c or d | Unprimed c over decoys | Unprimed c or d over decoys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | findings | 5/12 (42%; 19% to 68%) | 9/12 (75%; 47% to 91%) | 0/12 (0%; 0% to 24%) | 3/12 (25%; 9% to 53%) | +0 points (-19 to +24) | +19 points (-9 to +47) |
| stacked-nouns | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | - | - |
| long-dependency | findings | 5/12 (42%; 19% to 68%) | 5/12 (42%; 19% to 68%) | 1/12 (8%; 1% to 35%) | 5/12 (42%; 19% to 68%) | +8 points (-12 to +35) | +35 points (+4 to +62) |
| long-dependency | near misses | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 2/4 (50%; 15% to 85%) | 3/4 (75%; 30% to 95%) | - | - |
| reduced-object-relative | findings | 8/12 (67%; 39% to 86%) | 10/12 (83%; 55% to 95%) | 3/12 (25%; 9% to 53%) | 6/12 (50%; 25% to 75%) | +25 points (-0 to +53) | +44 points (+11 to +69) |
| hyphen-compound | findings | 5/12 (42%; 19% to 68%) | 9/12 (75%; 47% to 91%) | 0/12 (0%; 0% to 24%) | 2/12 (17%; 5% to 45%) | +0 points (-19 to +24) | +10 points (-15 to +39) |
| inline-list | findings | 5/12 (42%; 19% to 68%) | 11/12 (92%; 65% to 99%) | 0/12 (0%; 0% to 24%) | 2/12 (17%; 5% to 45%) | +0 points (-19 to +24) | +10 points (-15 to +39) |
| inline-list | near misses | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | - | - |
| inanimate-subject | findings | 1/4 (25%; 5% to 70%) | 3/4 (75%; 30% to 95%) | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | +25 points (-3 to +70) | +19 points (-11 to +64) |
| participial-clause | findings | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | +25 points (-3 to +70) | +19 points (-11 to +64) |
| nominalization | findings | 4/4 (100%; 51% to 100%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | +0 points (-19 to +49) | -6 points (-28 to +43) |
| center-embedding | findings | 1/1 (100%; 21% to 100%) | 1/1 (100%; 21% to 100%) | 1/1 (100%; 21% to 100%) | 1/1 (100%; 21% to 100%) | +100 points (+18 to +100) | +94 points (+11 to +99) |
| center-embedding | near misses | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | - | - |
| undefined-acronym | findings | 1/4 (25%; 5% to 70%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | +0 points (-19 to +49) | +19 points (-11 to +64) |
| undefined-acronym | near misses | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | - | - |

Fleiss' kappa over the twelve (77 complete findings, 0 incomplete): c/d/w 0.38, c against not 0.54, accepted against not 0.41; unprimed c against not 0.40 (77 complete).

### design

79 findings, 16 near misses; random decoys: unprimed c 1/16 (6%; 1% to 28%), unprimed c or d 2/16 (12%; 3% to 36%).

| Rule | Item | Accepted | Present | Unprimed c | Unprimed c or d | Unprimed c over decoys | Unprimed c or d over decoys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | findings | 4/12 (33%; 14% to 61%) | 10/12 (83%; 55% to 95%) | 1/12 (8%; 1% to 35%) | 4/12 (33%; 14% to 61%) | +2 points (-21 to +30) | +21 points (-10 to +50) |
| stacked-nouns | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | - | - |
| long-dependency | findings | 5/12 (42%; 19% to 68%) | 6/12 (50%; 25% to 75%) | 0/12 (0%; 0% to 24%) | 2/12 (17%; 5% to 45%) | -6 points (-28 to +19) | +4 points (-22 to +34) |
| long-dependency | near misses | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | - | - |
| reduced-object-relative | findings | 6/12 (50%; 25% to 75%) | 7/12 (58%; 32% to 81%) | 1/12 (8%; 1% to 35%) | 8/12 (67%; 39% to 86%) | +2 points (-21 to +30) | +54 points (+18 to +76) |
| hyphen-compound | findings | 8/12 (67%; 39% to 86%) | 11/12 (92%; 65% to 99%) | 0/12 (0%; 0% to 24%) | 2/12 (17%; 5% to 45%) | -6 points (-28 to +19) | +4 points (-22 to +34) |
| inline-list | findings | 4/12 (33%; 14% to 61%) | 9/12 (75%; 47% to 91%) | 0/12 (0%; 0% to 24%) | 2/12 (17%; 5% to 45%) | -6 points (-28 to +19) | +4 points (-22 to +34) |
| inline-list | near misses | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | - | - |
| inanimate-subject | findings | 1/4 (25%; 5% to 70%) | 3/4 (75%; 30% to 95%) | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | -6 points (-28 to +43) | +38 points (-5 to +74) |
| participial-clause | findings | 1/4 (25%; 5% to 70%) | 3/4 (75%; 30% to 95%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | -6 points (-28 to +43) | +12 points (-19 to +58) |
| nominalization | findings | 4/4 (100%; 51% to 100%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | -6 points (-28 to +43) | +38 points (-5 to +74) |
| center-embedding | findings | 3/3 (100%; 44% to 100%) | 3/3 (100%; 44% to 100%) | 0/3 (0%; 0% to 56%) | 3/3 (100%; 44% to 100%) | -6 points (-28 to +50) | +88 points (+27 to +97) |
| center-embedding | near misses | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | - | - |
| undefined-acronym | findings | 2/4 (50%; 15% to 85%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | -6 points (-28 to +43) | +38 points (-5 to +74) |
| undefined-acronym | near misses | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | - | - |

Fleiss' kappa over the twelve (79 complete findings, 0 incomplete): c/d/w 0.35, c against not 0.20, accepted against not 0.41; unprimed c against not 0.30 (79 complete).

### runbook

69 findings, 16 near misses; random decoys: unprimed c 0/16 (0%; 0% to 19%), unprimed c or d 2/16 (12%; 3% to 36%).

| Rule | Item | Accepted | Present | Unprimed c | Unprimed c or d | Unprimed c over decoys | Unprimed c or d over decoys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | findings | 3/12 (25%; 9% to 53%) | 9/12 (75%; 47% to 91%) | 0/12 (0%; 0% to 24%) | 4/12 (33%; 14% to 61%) | +0 points (-19 to +24) | +21 points (-10 to +50) |
| stacked-nouns | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | - | - |
| long-dependency | findings | 5/11 (45%; 21% to 72%) | 7/11 (64%; 35% to 85%) | 0/11 (0%; 0% to 26%) | 1/11 (9%; 2% to 38%) | +0 points (-19 to +26) | -3 points (-28 to +27) |
| long-dependency | near misses | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | - | - |
| reduced-object-relative | findings | 3/8 (38%; 14% to 69%) | 4/8 (50%; 22% to 78%) | 0/8 (0%; 0% to 32%) | 2/8 (25%; 7% to 59%) | +0 points (-19 to +32) | +12 points (-17 to +48) |
| hyphen-compound | findings | 2/12 (17%; 5% to 45%) | 8/12 (67%; 39% to 86%) | 0/12 (0%; 0% to 24%) | 3/12 (25%; 9% to 53%) | +0 points (-19 to +24) | +12 points (-16 to +42) |
| inline-list | findings | 4/12 (33%; 14% to 61%) | 10/12 (83%; 55% to 95%) | 0/12 (0%; 0% to 24%) | 1/12 (8%; 1% to 35%) | +0 points (-19 to +24) | -4 points (-29 to +24) |
| inline-list | near misses | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | - | - |
| inanimate-subject | findings | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | +0 points (-19 to +49) | +12 points (-19 to +58) |
| participial-clause | findings | 0/4 (0%; 0% to 49%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | +0 points (-19 to +49) | -12 points (-36 to +37) |
| nominalization | findings | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | +50 points (+5 to +91) | +38 points (-9 to +79) |
| center-embedding | near misses | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | - | - |
| undefined-acronym | findings | 1/4 (25%; 5% to 70%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | +0 points (-19 to +49) | -12 points (-36 to +37) |
| undefined-acronym | near misses | 1/2 (50%; 9% to 91%) | 2/2 (100%; 34% to 100%) | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | - | - |

Fleiss' kappa over the twelve (69 complete findings, 0 incomplete): c/d/w 0.38, c against not 0.23, accepted against not 0.44; unprimed c against not 0.49 (69 complete).

### changelog

80 findings, 16 near misses; random decoys: unprimed c 0/16 (0%; 0% to 19%), unprimed c or d 1/16 (6%; 1% to 28%).

| Rule | Item | Accepted | Present | Unprimed c | Unprimed c or d | Unprimed c over decoys | Unprimed c or d over decoys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | findings | 4/12 (33%; 14% to 61%) | 8/12 (67%; 39% to 86%) | 0/12 (0%; 0% to 24%) | 1/12 (8%; 1% to 35%) | +0 points (-19 to +24) | +2 points (-21 to +30) |
| stacked-nouns | near misses | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | - | - |
| long-dependency | findings | 5/12 (42%; 19% to 68%) | 6/12 (50%; 25% to 75%) | 2/12 (17%; 5% to 45%) | 7/12 (58%; 32% to 81%) | +17 points (-6 to +45) | +52 points (+18 to +75) |
| long-dependency | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | - | - |
| reduced-object-relative | findings | 4/12 (33%; 14% to 61%) | 6/12 (50%; 25% to 75%) | 4/12 (33%; 14% to 61%) | 7/12 (58%; 32% to 81%) | +33 points (+6 to +61) | +52 points (+18 to +75) |
| hyphen-compound | findings | 1/12 (8%; 1% to 35%) | 7/12 (58%; 32% to 81%) | 0/12 (0%; 0% to 24%) | 1/12 (8%; 1% to 35%) | +0 points (-19 to +24) | +2 points (-21 to +30) |
| inline-list | findings | 1/12 (8%; 1% to 35%) | 9/12 (75%; 47% to 91%) | 1/12 (8%; 1% to 35%) | 3/12 (25%; 9% to 53%) | +8 points (-12 to +35) | +19 points (-9 to +47) |
| inline-list | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | - | - |
| inanimate-subject | findings | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | +0 points (-19 to +49) | -6 points (-28 to +43) |
| participial-clause | findings | 1/4 (25%; 5% to 70%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | +0 points (-19 to +49) | +19 points (-11 to +64) |
| nominalization | findings | 4/4 (100%; 51% to 100%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 3/4 (75%; 30% to 95%) | +0 points (-19 to +49) | +69 points (+19 to +90) |
| center-embedding | findings | 3/4 (75%; 30% to 95%) | 4/4 (100%; 51% to 100%) | 3/4 (75%; 30% to 95%) | 3/4 (75%; 30% to 95%) | +75 points (+26 to +95) | +69 points (+19 to +90) |
| center-embedding | near misses | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | - | - |
| undefined-acronym | findings | 1/4 (25%; 5% to 70%) | 3/4 (75%; 30% to 95%) | 1/4 (25%; 5% to 70%) | 3/4 (75%; 30% to 95%) | +25 points (-3 to +70) | +69 points (+19 to +90) |
| undefined-acronym | near misses | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | - | - |

Fleiss' kappa over the twelve (80 complete findings, 0 incomplete): c/d/w 0.38, c against not 0.49, accepted against not 0.43; unprimed c against not 0.55 (80 complete).

### blog

76 findings, 16 near misses; random decoys: unprimed c 0/16 (0%; 0% to 19%), unprimed c or d 1/16 (6%; 1% to 28%).

| Rule | Item | Accepted | Present | Unprimed c | Unprimed c or d | Unprimed c over decoys | Unprimed c or d over decoys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | findings | 0/12 (0%; 0% to 24%) | 7/12 (58%; 32% to 81%) | 0/12 (0%; 0% to 24%) | 1/12 (8%; 1% to 35%) | +0 points (-19 to +24) | +2 points (-21 to +30) |
| stacked-nouns | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | - | - |
| long-dependency | findings | 7/12 (58%; 32% to 81%) | 9/12 (75%; 47% to 91%) | 1/12 (8%; 1% to 35%) | 5/12 (42%; 19% to 68%) | +8 points (-12 to +35) | +35 points (+4 to +62) |
| long-dependency | near misses | 3/4 (75%; 30% to 95%) | 3/4 (75%; 30% to 95%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | - | - |
| reduced-object-relative | findings | 1/12 (8%; 1% to 35%) | 6/12 (50%; 25% to 75%) | 0/12 (0%; 0% to 24%) | 3/12 (25%; 9% to 53%) | +0 points (-19 to +24) | +19 points (-9 to +47) |
| hyphen-compound | findings | 1/12 (8%; 1% to 35%) | 4/12 (33%; 14% to 61%) | 0/12 (0%; 0% to 24%) | 3/12 (25%; 9% to 53%) | +0 points (-19 to +24) | +19 points (-9 to +47) |
| inline-list | findings | 2/12 (17%; 5% to 45%) | 6/12 (50%; 25% to 75%) | 0/12 (0%; 0% to 24%) | 3/12 (25%; 9% to 53%) | +0 points (-19 to +24) | +19 points (-9 to +47) |
| inline-list | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | - | - |
| inanimate-subject | findings | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | +0 points (-19 to +49) | -6 points (-28 to +43) |
| participial-clause | findings | 2/4 (50%; 15% to 85%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | +0 points (-19 to +49) | -6 points (-28 to +43) |
| nominalization | findings | 3/4 (75%; 30% to 95%) | 3/4 (75%; 30% to 95%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | +0 points (-19 to +49) | +19 points (-11 to +64) |
| center-embedding | near misses | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | - | - |
| undefined-acronym | findings | 1/4 (25%; 5% to 70%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | +0 points (-19 to +49) | +44 points (+2 to +79) |
| undefined-acronym | near misses | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | - | - |

Fleiss' kappa over the twelve (76 complete findings, 0 incomplete): c/d/w 0.45, c against not 0.63, accepted against not 0.49; unprimed c against not 0.14 (76 complete).

### standards

76 findings, 16 near misses; random decoys: unprimed c 0/16 (0%; 0% to 19%), unprimed c or d 2/16 (12%; 3% to 36%).

| Rule | Item | Accepted | Present | Unprimed c | Unprimed c or d | Unprimed c over decoys | Unprimed c or d over decoys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | findings | 4/12 (33%; 14% to 61%) | 11/12 (92%; 65% to 99%) | 0/12 (0%; 0% to 24%) | 6/12 (50%; 25% to 75%) | +0 points (-19 to +24) | +38 points (+3 to +64) |
| stacked-nouns | near misses | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | - | - |
| long-dependency | findings | 7/12 (58%; 32% to 81%) | 8/12 (67%; 39% to 86%) | 1/12 (8%; 1% to 35%) | 7/12 (58%; 32% to 81%) | +8 points (-12 to +35) | +46 points (+10 to +70) |
| long-dependency | near misses | 1/4 (25%; 5% to 70%) | 2/4 (50%; 15% to 85%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | - | - |
| reduced-object-relative | findings | 1/12 (8%; 1% to 35%) | 4/12 (33%; 14% to 61%) | 1/12 (8%; 1% to 35%) | 1/12 (8%; 1% to 35%) | +8 points (-12 to +35) | -4 points (-29 to +24) |
| hyphen-compound | findings | 1/12 (8%; 1% to 35%) | 4/12 (33%; 14% to 61%) | 0/12 (0%; 0% to 24%) | 2/12 (17%; 5% to 45%) | +0 points (-19 to +24) | +4 points (-22 to +34) |
| inline-list | findings | 1/12 (8%; 1% to 35%) | 3/12 (25%; 9% to 53%) | 0/12 (0%; 0% to 24%) | 6/12 (50%; 25% to 75%) | +0 points (-19 to +24) | +38 points (+3 to +64) |
| inline-list | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 2/4 (50%; 15% to 85%) | - | - |
| inanimate-subject | findings | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | +0 points (-19 to +49) | +38 points (-5 to +74) |
| participial-clause | findings | 3/4 (75%; 30% to 95%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | +0 points (-19 to +49) | +12 points (-19 to +58) |
| nominalization | findings | 3/4 (75%; 30% to 95%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | +0 points (-19 to +49) | +38 points (-5 to +74) |
| center-embedding | near misses | 1/2 (50%; 9% to 91%) | 1/2 (50%; 9% to 91%) | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | - | - |
| undefined-acronym | findings | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | +0 points (-19 to +49) | -12 points (-36 to +37) |
| undefined-acronym | near misses | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | - | - |

Fleiss' kappa over the twelve (76 complete findings, 0 incomplete): c/d/w 0.44, c against not 0.58, accepted against not 0.51; unprimed c against not 0.37 (76 complete).

### code-doc

66 findings, 12 near misses; random decoys: unprimed c 0/16 (0%; 0% to 19%), unprimed c or d 1/16 (6%; 1% to 28%).

| Rule | Item | Accepted | Present | Unprimed c | Unprimed c or d | Unprimed c over decoys | Unprimed c or d over decoys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | findings | 3/12 (25%; 9% to 53%) | 6/12 (50%; 25% to 75%) | 0/12 (0%; 0% to 24%) | 2/12 (17%; 5% to 45%) | +0 points (-19 to +24) | +10 points (-15 to +39) |
| stacked-nouns | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | - | - |
| long-dependency | findings | 9/12 (75%; 47% to 91%) | 9/12 (75%; 47% to 91%) | 1/12 (8%; 1% to 35%) | 7/12 (58%; 32% to 81%) | +8 points (-12 to +35) | +52 points (+18 to +75) |
| long-dependency | near misses | 1/4 (25%; 5% to 70%) | 2/4 (50%; 15% to 85%) | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | - | - |
| reduced-object-relative | findings | 4/12 (33%; 14% to 61%) | 8/12 (67%; 39% to 86%) | 1/12 (8%; 1% to 35%) | 5/12 (42%; 19% to 68%) | +8 points (-12 to +35) | +35 points (+4 to +62) |
| hyphen-compound | findings | 4/12 (33%; 14% to 61%) | 9/12 (75%; 47% to 91%) | 1/12 (8%; 1% to 35%) | 5/12 (42%; 19% to 68%) | +8 points (-12 to +35) | +35 points (+4 to +62) |
| inanimate-subject | findings | 0/4 (0%; 0% to 49%) | 3/4 (75%; 30% to 95%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | +0 points (-19 to +49) | +19 points (-11 to +64) |
| participial-clause | findings | 1/4 (25%; 5% to 70%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | +0 points (-19 to +49) | +19 points (-11 to +64) |
| nominalization | findings | 2/3 (67%; 21% to 94%) | 3/3 (100%; 44% to 100%) | 0/3 (0%; 0% to 56%) | 2/3 (67%; 21% to 94%) | +0 points (-19 to +56) | +60 points (+9 to +88) |
| center-embedding | findings | 1/3 (33%; 6% to 79%) | 1/3 (33%; 6% to 79%) | 1/3 (33%; 6% to 79%) | 3/3 (100%; 44% to 100%) | +33 points (-0 to +79) | +94 points (+33 to +99) |
| center-embedding | near misses | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | - | - |
| undefined-acronym | findings | 2/4 (50%; 15% to 85%) | 3/4 (75%; 30% to 95%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | +0 points (-19 to +49) | -6 points (-28 to +43) |
| undefined-acronym | near misses | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | - | - |

Fleiss' kappa over the twelve (66 complete findings, 0 incomplete): c/d/w 0.41, c against not 0.53, accepted against not 0.46; unprimed c against not 0.18 (66 complete).

### code-ordinary

65 findings, 12 near misses; random decoys: unprimed c 0/16 (0%; 0% to 19%), unprimed c or d 2/16 (12%; 3% to 36%).

| Rule | Item | Accepted | Present | Unprimed c | Unprimed c or d | Unprimed c over decoys | Unprimed c or d over decoys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | findings | 2/12 (17%; 5% to 45%) | 6/12 (50%; 25% to 75%) | 1/12 (8%; 1% to 35%) | 5/12 (42%; 19% to 68%) | +8 points (-12 to +35) | +29 points (-3 to +57) |
| stacked-nouns | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | - | - |
| long-dependency | findings | 1/12 (8%; 1% to 35%) | 1/12 (8%; 1% to 35%) | 1/12 (8%; 1% to 35%) | 4/12 (33%; 14% to 61%) | +8 points (-12 to +35) | +21 points (-10 to +50) |
| long-dependency | near misses | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 1/4 (25%; 5% to 70%) | 3/4 (75%; 30% to 95%) | - | - |
| reduced-object-relative | findings | 5/12 (42%; 19% to 68%) | 8/12 (67%; 39% to 86%) | 0/12 (0%; 0% to 24%) | 5/12 (42%; 19% to 68%) | +0 points (-19 to +24) | +29 points (-3 to +57) |
| hyphen-compound | findings | 3/12 (25%; 9% to 53%) | 9/12 (75%; 47% to 91%) | 0/12 (0%; 0% to 24%) | 1/12 (8%; 1% to 35%) | +0 points (-19 to +24) | -4 points (-29 to +24) |
| inanimate-subject | findings | 0/4 (0%; 0% to 49%) | 3/4 (75%; 30% to 95%) | 1/4 (25%; 5% to 70%) | 3/4 (75%; 30% to 95%) | +25 points (-3 to +70) | +62 points (+12 to +85) |
| participial-clause | findings | 2/4 (50%; 15% to 85%) | 3/4 (75%; 30% to 95%) | 0/4 (0%; 0% to 49%) | 3/4 (75%; 30% to 95%) | +0 points (-19 to +49) | +62 points (+12 to +85) |
| nominalization | findings | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | +0 points (-19 to +66) | +38 points (-9 to +79) |
| center-embedding | findings | 2/3 (67%; 21% to 94%) | 2/3 (67%; 21% to 94%) | 1/3 (33%; 6% to 79%) | 2/3 (67%; 21% to 94%) | +33 points (-0 to +79) | +54 points (+3 to +83) |
| center-embedding | near misses | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | - | - |
| undefined-acronym | findings | 0/4 (0%; 0% to 49%) | 3/4 (75%; 30% to 95%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | +0 points (-19 to +49) | +12 points (-19 to +58) |
| undefined-acronym | near misses | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | - | - |

Fleiss' kappa over the twelve (65 complete findings, 0 incomplete): c/d/w 0.29, c against not 0.21, accepted against not 0.29; unprimed c against not 0.46 (65 complete).

### contrast

67 findings, 16 near misses; random decoys: unprimed c 0/16 (0%; 0% to 19%), unprimed c or d 3/16 (19%; 7% to 43%).

| Rule | Item | Accepted | Present | Unprimed c | Unprimed c or d | Unprimed c over decoys | Unprimed c or d over decoys |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | findings | 1/12 (8%; 1% to 35%) | 11/12 (92%; 65% to 99%) | 0/12 (0%; 0% to 24%) | 1/12 (8%; 1% to 35%) | +0 points (-19 to +24) | -10 points (-36 to +19) |
| stacked-nouns | near misses | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | - | - |
| long-dependency | findings | 10/12 (83%; 55% to 95%) | 10/12 (83%; 55% to 95%) | 0/12 (0%; 0% to 24%) | 4/12 (33%; 14% to 61%) | +0 points (-19 to +24) | +15 points (-17 to +45) |
| long-dependency | near misses | 2/4 (50%; 15% to 85%) | 3/4 (75%; 30% to 95%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | - | - |
| reduced-object-relative | findings | 2/12 (17%; 5% to 45%) | 8/12 (67%; 39% to 86%) | 0/12 (0%; 0% to 24%) | 4/12 (33%; 14% to 61%) | +0 points (-19 to +24) | +15 points (-17 to +45) |
| hyphen-compound | findings | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | +0 points (-19 to +66) | -19 points (-43 to +48) |
| inline-list | findings | 3/12 (25%; 9% to 53%) | 9/12 (75%; 47% to 91%) | 0/12 (0%; 0% to 24%) | 3/12 (25%; 9% to 53%) | +0 points (-19 to +24) | +6 points (-23 to +37) |
| inline-list | near misses | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | - | - |
| inanimate-subject | findings | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | +0 points (-19 to +49) | +6 points (-25 to +53) |
| participial-clause | findings | 0/4 (0%; 0% to 49%) | 2/4 (50%; 15% to 85%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | +0 points (-19 to +49) | -19 points (-43 to +32) |
| nominalization | findings | 2/4 (50%; 15% to 85%) | 3/4 (75%; 30% to 95%) | 0/4 (0%; 0% to 49%) | 1/4 (25%; 5% to 70%) | +0 points (-19 to +49) | +6 points (-25 to +53) |
| center-embedding | findings | 1/1 (100%; 21% to 100%) | 1/1 (100%; 21% to 100%) | 0/1 (0%; 0% to 79%) | 0/1 (0%; 0% to 79%) | +0 points (-19 to +79) | -19 points (-43 to +62) |
| center-embedding | near misses | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | 1/2 (50%; 9% to 91%) | - | - |
| undefined-acronym | findings | 2/4 (50%; 15% to 85%) | 4/4 (100%; 51% to 100%) | 0/4 (0%; 0% to 49%) | 0/4 (0%; 0% to 49%) | +0 points (-19 to +49) | -19 points (-43 to +32) |
| undefined-acronym | near misses | 0/2 (0%; 0% to 66%) | 2/2 (100%; 34% to 100%) | 0/2 (0%; 0% to 66%) | 0/2 (0%; 0% to 66%) | - | - |

Fleiss' kappa over the twelve (67 complete findings, 0 incomplete): c/d/w 0.44, c against not 0.53, accepted against not 0.47; unprimed c against not -0.02 (67 complete).

## Random decoys

| Stratum | c | Accepted | Present | Unprimed c | Unprimed c or d |
| --- | --- | --- | --- | --- | --- |
| tutorial | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 3/16 (19%; 7% to 43%) |
| reference | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 1/16 (6%; 1% to 28%) |
| explanation | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 1/16 (6%; 1% to 28%) | 0/16 (0%; 0% to 19%) | 1/16 (6%; 1% to 28%) |
| design | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 1/16 (6%; 1% to 28%) | 2/16 (12%; 3% to 36%) |
| runbook | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 2/16 (12%; 3% to 36%) |
| changelog | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 1/16 (6%; 1% to 28%) |
| blog | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 1/16 (6%; 1% to 28%) |
| standards | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 1/16 (6%; 1% to 28%) | 0/16 (0%; 0% to 19%) | 2/16 (12%; 3% to 36%) |
| code-doc | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 1/16 (6%; 1% to 28%) |
| code-ordinary | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 1/16 (6%; 1% to 28%) | 0/16 (0%; 0% to 19%) | 2/16 (12%; 3% to 36%) |
| contrast | 0/16 (0%; 0% to 19%) | 0/16 (0%; 0% to 19%) | 1/16 (6%; 1% to 28%) | 0/16 (0%; 0% to 19%) | 3/16 (19%; 7% to 43%) |
| technical | 0/160 (0%; 0% to 2%) | 0/160 (0%; 0% to 2%) | 3/160 (2%; 1% to 5%) | 1/160 (1%; 0% to 3%) | 16/160 (10%; 6% to 16%) |

## Pooled over the technical strata

| Rule | Findings, c | Near, c | c difference | Findings, accepted | Near, accepted | Accepted difference | Unprimed c over decoys | Unprimed c or d over decoys |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | 1/120 (1%; 0% to 5%) | 0/40 (0%; 0% to 9%) | +1 points (-8 to +5) | 34/120 (28%; 21% to 37%) | 0/40 (0%; 0% to 9%) | +28 points (+17 to +37) | +1 points (-2 to +5) | +15 points (+6 to +24) |
| long-dependency | 15/119 (13%; 8% to 20%) | 0/40 (0%; 0% to 9%) | +13 points (+3 to +20) | 53/119 (45%; 36% to 53%) | 12/40 (30%; 18% to 45%) | +15 points (-3 to +29) | +5 points (+1 to +11) | +27 points (+17 to +37) |
| reduced-object-relative | 1/116 (1%; 0% to 5%) | - | - | 40/116 (34%; 26% to 44%) | - | - | +9 points (+4 to +16) | +29 points (+19 to +39) |
| hyphen-compound | 0/120 (0%; 0% to 3%) | - | - | 35/120 (29%; 22% to 38%) | - | - | +0 points (-3 to +4) | +7 points (-1 to +16) |
| inline-list | 0/96 (0%; 0% to 4%) | 0/32 (0%; 0% to 11%) | +0 points (-11 to +4) | 19/96 (20%; 13% to 29%) | 2/32 (6%; 2% to 20%) | +14 points (-2 to +24) | +0 points (-3 to +5) | +15 points (+6 to +25) |
| inanimate-subject | 0/40 (0%; 0% to 9%) | - | - | 4/40 (10%; 4% to 23%) | - | - | +4 points (-0 to +16) | +25 points (+11 to +41) |
| participial-clause | 0/40 (0%; 0% to 9%) | - | - | 13/40 (32%; 20% to 48%) | - | - | +2 points (-2 to +12) | +15 points (+3 to +31) |
| nominalization | 2/35 (6%; 2% to 19%) | - | - | 28/35 (80%; 64% to 90%) | - | - | +2 points (-1 to +14) | +33 points (+17 to +50) |
| center-embedding | 4/16 (25%; 10% to 49%) | 1/20 (5%; 1% to 24%) | +20 points (-4 to +45) | 11/16 (69%; 44% to 86%) | 4/20 (20%; 8% to 42%) | +49 points (+16 to +70) | +43 points (+22 to +66) | +71 points (+46 to +84) |
| undefined-acronym | 0/40 (0%; 0% to 9%) | 0/20 (0%; 0% to 16%) | +0 points (-16 to +9) | 12/40 (30%; 18% to 45%) | 3/20 (15%; 5% to 36%) | +15 points (-9 to +33) | +2 points (-2 to +12) | +18 points (+5 to +33) |

## Per model (majority of its three), findings pooled

| Rule | Opus 5.5 c | Opus 5.5 accepted | Sonnet 5.5 c | Sonnet 5.5 accepted | Haiku 5.5 c | Haiku 5.5 accepted | Fable 5.2 c | Fable 5.2 accepted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | 3/120 (2%; 1% to 7%) | 29/120 (24%; 17% to 33%) | 1/120 (1%; 0% to 5%) | 46/120 (38%; 30% to 47%) | 0/120 (0%; 0% to 3%) | 13/120 (11%; 6% to 18%) | 7/120 (6%; 3% to 12%) | 63/120 (52%; 44% to 61%) |
| long-dependency | 17/119 (14%; 9% to 22%) | 50/119 (42%; 34% to 51%) | 26/119 (22%; 15% to 30%) | 87/119 (73%; 65% to 80%) | 10/119 (8%; 5% to 15%) | 64/119 (54%; 45% to 62%) | 17/119 (14%; 9% to 22%) | 56/119 (47%; 38% to 56%) |
| reduced-object-relative | 4/116 (3%; 1% to 9%) | 25/116 (22%; 15% to 30%) | 1/116 (1%; 0% to 5%) | 42/116 (36%; 28% to 45%) | 1/116 (1%; 0% to 5%) | 28/116 (24%; 17% to 33%) | 8/116 (7%; 4% to 13%) | 64/116 (55%; 46% to 64%) |
| hyphen-compound | 0/120 (0%; 0% to 3%) | 31/120 (26%; 19% to 34%) | 0/120 (0%; 0% to 3%) | 44/120 (37%; 29% to 46%) | 0/120 (0%; 0% to 3%) | 4/120 (3%; 1% to 8%) | 0/120 (0%; 0% to 3%) | 72/120 (60%; 51% to 68%) |
| inline-list | 0/96 (0%; 0% to 4%) | 19/96 (20%; 13% to 29%) | 0/96 (0%; 0% to 4%) | 25/96 (26%; 18% to 36%) | 0/96 (0%; 0% to 4%) | 17/96 (18%; 11% to 27%) | 3/96 (3%; 1% to 9%) | 59/96 (61%; 51% to 71%) |
| inanimate-subject | 0/40 (0%; 0% to 9%) | 4/40 (10%; 4% to 23%) | 0/40 (0%; 0% to 9%) | 5/40 (12%; 5% to 26%) | 0/40 (0%; 0% to 9%) | 3/40 (8%; 3% to 20%) | 0/40 (0%; 0% to 9%) | 10/40 (25%; 14% to 40%) |
| participial-clause | 0/40 (0%; 0% to 9%) | 18/40 (45%; 31% to 60%) | 0/40 (0%; 0% to 9%) | 14/40 (35%; 22% to 50%) | 0/40 (0%; 0% to 9%) | 3/40 (8%; 3% to 20%) | 1/40 (2%; 0% to 13%) | 35/40 (88%; 74% to 95%) |
| nominalization | 5/35 (14%; 6% to 29%) | 26/35 (74%; 58% to 86%) | 1/35 (3%; 1% to 15%) | 31/35 (89%; 74% to 95%) | 0/35 (0%; 0% to 10%) | 26/35 (74%; 58% to 86%) | 8/35 (23%; 12% to 39%) | 29/35 (83%; 67% to 92%) |
| center-embedding | 7/16 (44%; 23% to 67%) | 12/16 (75%; 51% to 90%) | 8/16 (50%; 28% to 72%) | 14/16 (88%; 64% to 97%) | 4/16 (25%; 10% to 49%) | 12/16 (75%; 51% to 90%) | 4/16 (25%; 10% to 49%) | 6/16 (38%; 18% to 61%) |
| undefined-acronym | 0/40 (0%; 0% to 9%) | 12/40 (30%; 18% to 45%) | 0/40 (0%; 0% to 9%) | 12/40 (30%; 18% to 45%) | 0/40 (0%; 0% to 9%) | 9/40 (22%; 12% to 38%) | 1/40 (2%; 0% to 13%) | 19/40 (48%; 33% to 63%) |

## Ranked sentences (unprimed raters only)

192 documents, pooled over the technical strata. Unprimed c or d:

| Ranking | Unprimed c or d |
| --- | --- |
| composite | 92/192 (48%; 41% to 55%) |
| longest | 104/192 (54%; 47% to 61%) |
| random | 25/192 (13%; 9% to 19%) |

Composite minus longest: -6 points (-16 to +4). Composite minus random: +35 points (+26 to +43).

Exploratory, paired by document: against longest, 192 documents, composite alone accepted in 14, longest alone in 26; against random, 192 documents, composite alone accepted in 74, random alone in 7.

| Stratum | Documents | Composite | Longest | Random |
| --- | --- | --- | --- | --- |
| tutorial | 20 | 10/20 (50%; 30% to 70%) | 11/20 (55%; 34% to 74%) | 4/20 (20%; 8% to 42%) |
| reference | 20 | 7/20 (35%; 18% to 57%) | 9/20 (45%; 26% to 66%) | 1/20 (5%; 1% to 24%) |
| explanation | 20 | 9/20 (45%; 26% to 66%) | 9/20 (45%; 26% to 66%) | 2/20 (10%; 3% to 30%) |
| design | 20 | 9/20 (45%; 26% to 66%) | 14/20 (70%; 48% to 85%) | 1/20 (5%; 1% to 24%) |
| runbook | 13 | 6/13 (46%; 23% to 71%) | 4/13 (31%; 13% to 58%) | 1/13 (8%; 1% to 33%) |
| changelog | 20 | 17/20 (85%; 64% to 95%) | 18/20 (90%; 70% to 97%) | 3/20 (15%; 5% to 36%) |
| blog | 19 | 7/19 (37%; 19% to 59%) | 9/19 (47%; 27% to 68%) | 4/19 (21%; 9% to 43%) |
| standards | 20 | 12/20 (60%; 39% to 78%) | 14/20 (70%; 48% to 85%) | 4/20 (20%; 8% to 42%) |
| code-doc | 20 | 5/20 (25%; 11% to 47%) | 7/20 (35%; 18% to 57%) | 1/20 (5%; 1% to 24%) |
| code-ordinary | 20 | 10/20 (50%; 30% to 70%) | 9/20 (45%; 26% to 66%) | 4/20 (20%; 8% to 42%) |
| contrast | 20 | 10/20 (50%; 30% to 70%) | 14/20 (70%; 48% to 85%) | 2/20 (10%; 3% to 30%) |

## Defaults across rounds (part B)

(i): findings' accepted share minus near misses', rounds 2 and 3. (ii): findings' unprimed c-or-d share minus the random decoys', rounds 1 to 3.

| Rule | Findings accepted | Near accepted | (i) | Findings unprimed c or d | Decoys unprimed c or d | (ii) | Decision | Differs in round |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | 70/220 (32%; 26% to 38%) | 0/90 (0%; 0% to 4%) | +32 points (+25 to +38) | 49/260 (19%; 15% to 24%) | 20/225 (9%; 6% to 13%) | +10 points (+4 to +16) | stays default | - |
| long-dependency | 81/210 (39%; 32% to 45%) | 27/86 (31%; 23% to 42%) | +7 points (-5 to +18) | 95/250 (38%; 32% to 44%) | 20/225 (9%; 6% to 13%) | +29 points (+22 to +36) | stays default | - |
| reduced-object-relative | 83/201 (41%; 35% to 48%) | none | n/a | 91/241 (38%; 32% to 44%) | 20/225 (9%; 6% to 13%) | +29 points (+21 to +36) | stays default | - |
| hyphen-compound | 77/207 (37%; 31% to 44%) | none | n/a | 45/247 (18%; 14% to 24%) | 20/225 (9%; 6% to 13%) | +9 points (+3 to +15) | stays default | 2, 3 |
| inline-list | 40/196 (20%; 15% to 27%) | 8/82 (10%; 5% to 18%) | +11 points (+1 to +18) | 55/236 (23%; 18% to 29%) | 20/225 (9%; 6% to 13%) | +14 points (+8 to +21) | stays default | 2 |
| inanimate-subject | 4/82 (5%; 2% to 12%) | none | n/a | 31/122 (25%; 19% to 34%) | 20/225 (9%; 6% to 13%) | +17 points (+8 to +25) | proposed default | 2 |
| participial-clause | 29/90 (32%; 23% to 42%) | none | n/a | 22/110 (20%; 14% to 28%) | 20/225 (9%; 6% to 13%) | +11 points (+3 to +20) | proposed default | 1, 2 |
| nominalization | 41/54 (76%; 63% to 85%) | none | n/a | 26/74 (35%; 25% to 46%) | 20/225 (9%; 6% to 13%) | +26 points (+15 to +38) | proposed default | 2 |
| center-embedding | 24/46 (52%; 38% to 66%) | 6/45 (13%; 6% to 26%) | +39 points (+20 to +54) | 42/66 (64%; 52% to 74%) | 20/225 (9%; 6% to 13%) | +55 points (+42 to +66) | proposed default | 1 |
| undefined-acronym | 16/90 (18%; 11% to 27%) | 5/45 (11%; 5% to 23%) | +7 points (-7 to +18) | 27/110 (25%; 17% to 33%) | 20/225 (9%; 6% to 13%) | +16 points (+7 to +25) | stays opt-in | - |

Per round:

| Rule | Round | (i) | (ii) |
| --- | --- | --- | --- |
| stacked-nouns | 1 | n/a | +12 points (+1 to +26) |
| stacked-nouns | 2 | +36 points (+25 to +46) | -2 points (-21 to +11) |
| stacked-nouns | 3 | +28 points (+17 to +37) | +15 points (+6 to +24) |
| long-dependency | 1 | n/a | +38 points (+22 to +53) |
| long-dependency | 2 | -2 points (-19 to +14) | +24 points (+3 to +38) |
| long-dependency | 3 | +15 points (-3 to +29) | +27 points (+17 to +37) |
| reduced-object-relative | 1 | n/a | +20 points (+7 to +35) |
| reduced-object-relative | 2 | n/a | +29 points (+7 to +43) |
| reduced-object-relative | 3 | n/a | +29 points (+19 to +39) |
| hyphen-compound | 1 | n/a | +20 points (+7 to +35) |
| hyphen-compound | 2 | n/a | +2 points (-17 to +16) |
| hyphen-compound | 3 | n/a | +7 points (-1 to +16) |
| inline-list | 1 | n/a | +15 points (+3 to +29) |
| inline-list | 2 | +9 points (-5 to +20) | +9 points (-11 to +22) |
| inline-list | 3 | +14 points (-2 to +24) | +15 points (+6 to +25) |
| inanimate-subject | 1 | n/a | +20 points (+7 to +35) |
| inanimate-subject | 2 | n/a | +5 points (-16 to +23) |
| inanimate-subject | 3 | n/a | +25 points (+11 to +41) |
| participial-clause | 1 | n/a | +0 points (-9 to +16) |
| participial-clause | 2 | n/a | +8 points (-13 to +24) |
| participial-clause | 3 | n/a | +15 points (+3 to +31) |
| nominalization | 1 | n/a | +15 points (+2 to +36) |
| nominalization | 2 | n/a | +26 points (-0 to +50) |
| nominalization | 3 | n/a | +33 points (+17 to +50) |
| center-embedding | 1 | n/a | +40 points (+20 to +61) |
| center-embedding | 2 | +35 points (+12 to +54) | +54 points (+28 to +70) |
| center-embedding | 3 | +49 points (+16 to +70) | +71 points (+46 to +84) |
| undefined-acronym | 1 | n/a | +20 points (+5 to +42) |
| undefined-acronym | 2 | +0 points (-18 to +12) | +8 points (-13 to +24) |
| undefined-acronym | 3 | +15 points (-9 to +33) | +18 points (+5 to +33) |

## Decisions

- stacked-nouns (technical): the threshold earns its place. accepted: findings 28%, 21% to 37%, near misses 0%, 0% to 9%, difference +28 points (+17 to +37); too little c to compare, so accepted shares are used.
- inline-list (technical): threshold not supported by these labels. accepted: findings 20%, 13% to 29%, near misses 6%, 2% to 20%, difference +14 points (-2 to +24); too little c to compare, so accepted shares are used.
- long-dependency (technical): the threshold earns its place. c: findings 13%, 8% to 20%, near misses 0%, 0% to 9%, difference +13 points (+3 to +20).
- center-embedding (technical): threshold: too few to decide. 16 findings, 20 near misses.
- undefined-acronym (technical): threshold not supported by these labels. accepted: findings 30%, 18% to 45%, near misses 15%, 5% to 36%, difference +15 points (-9 to +33); too little c to compare, so accepted shares are used.
- stacked-nouns (tutorial): no better than chance placement in this kind. unprimed c or d 25%, 9% to 53%; over decoys +6 points (-23 to +37).
- long-dependency (tutorial): no better than chance placement in this kind. unprimed c or d 33%, 14% to 61%; over decoys +15 points (-17 to +45).
- reduced-object-relative (tutorial): no better than chance placement in this kind. unprimed c or d 33%, 14% to 61%; over decoys +15 points (-17 to +45).
- hyphen-compound (tutorial): no better than chance placement in this kind. unprimed c or d 8%, 1% to 35%; over decoys -10 points (-36 to +19).
- inline-list (tutorial): no better than chance placement in this kind. unprimed c or d 33%, 14% to 61%; over decoys +15 points (-17 to +45).
- stacked-nouns (reference): no better than chance placement in this kind. unprimed c or d 8%, 1% to 35%; over decoys +2 points (-21 to +30).
- long-dependency (reference): no better than chance placement in this kind. unprimed c or d 17%, 5% to 45%; over decoys +10 points (-15 to +39).
- reduced-object-relative (reference): no better than chance placement in this kind. unprimed c or d 33%, 14% to 61%; over decoys +27 points (-2 to +55).
- hyphen-compound (reference): no better than chance placement in this kind. unprimed c or d 8%, 1% to 35%; over decoys +2 points (-21 to +30).
- inline-list (reference): no better than chance placement in this kind. unprimed c or d 25%, 9% to 53%; over decoys +19 points (-9 to +47).
- stacked-nouns (explanation): no better than chance placement in this kind. unprimed c or d 25%, 9% to 53%; over decoys +19 points (-9 to +47).
- hyphen-compound (explanation): no better than chance placement in this kind. unprimed c or d 17%, 5% to 45%; over decoys +10 points (-15 to +39).
- inline-list (explanation): no better than chance placement in this kind. unprimed c or d 17%, 5% to 45%; over decoys +10 points (-15 to +39).
- stacked-nouns (design): no better than chance placement in this kind. unprimed c or d 33%, 14% to 61%; over decoys +21 points (-10 to +50).
- long-dependency (design): no better than chance placement in this kind. unprimed c or d 17%, 5% to 45%; over decoys +4 points (-22 to +34).
- hyphen-compound (design): no better than chance placement in this kind. unprimed c or d 17%, 5% to 45%; over decoys +4 points (-22 to +34).
- inline-list (design): no better than chance placement in this kind. unprimed c or d 17%, 5% to 45%; over decoys +4 points (-22 to +34).
- stacked-nouns (runbook): no better than chance placement in this kind. unprimed c or d 33%, 14% to 61%; over decoys +21 points (-10 to +50).
- long-dependency (runbook): no better than chance placement in this kind. unprimed c or d 9%, 2% to 38%; over decoys -3 points (-28 to +27).
- hyphen-compound (runbook): no better than chance placement in this kind. unprimed c or d 25%, 9% to 53%; over decoys +12 points (-16 to +42).
- inline-list (runbook): no better than chance placement in this kind. unprimed c or d 8%, 1% to 35%; over decoys -4 points (-29 to +24).
- stacked-nouns (changelog): no better than chance placement in this kind. unprimed c or d 8%, 1% to 35%; over decoys +2 points (-21 to +30).
- hyphen-compound (changelog): no better than chance placement in this kind. unprimed c or d 8%, 1% to 35%; over decoys +2 points (-21 to +30).
- inline-list (changelog): no better than chance placement in this kind. unprimed c or d 25%, 9% to 53%; over decoys +19 points (-9 to +47).
- stacked-nouns (blog): proposed off for blog. accepted 0%, 0% to 24%; against the rest -35 points (-45 to -9).
- stacked-nouns (blog): no better than chance placement in this kind. unprimed c or d 8%, 1% to 35%; over decoys +2 points (-21 to +30).
- reduced-object-relative (blog): no better than chance placement in this kind. unprimed c or d 25%, 9% to 53%; over decoys +19 points (-9 to +47).
- hyphen-compound (blog): no better than chance placement in this kind. unprimed c or d 25%, 9% to 53%; over decoys +19 points (-9 to +47).
- inline-list (blog): no better than chance placement in this kind. unprimed c or d 25%, 9% to 53%; over decoys +19 points (-9 to +47).
- reduced-object-relative (standards): no better than chance placement in this kind. unprimed c or d 8%, 1% to 35%; over decoys -4 points (-29 to +24).
- hyphen-compound (standards): no better than chance placement in this kind. unprimed c or d 17%, 5% to 45%; over decoys +4 points (-22 to +34).
- stacked-nouns (code-doc): no better than chance placement in this kind. unprimed c or d 17%, 5% to 45%; over decoys +10 points (-15 to +39).
- stacked-nouns (code-ordinary): no better than chance placement in this kind. unprimed c or d 42%, 19% to 68%; over decoys +29 points (-3 to +57).
- long-dependency (code-ordinary): no better than chance placement in this kind. unprimed c or d 33%, 14% to 61%; over decoys +21 points (-10 to +50).
- long-dependency (code-ordinary): detection problem in this kind. present 8%, 1% to 35%.
- reduced-object-relative (code-ordinary): no better than chance placement in this kind. unprimed c or d 42%, 19% to 68%; over decoys +29 points (-3 to +57).
- hyphen-compound (code-ordinary): no better than chance placement in this kind. unprimed c or d 8%, 1% to 35%; over decoys -4 points (-29 to +24).
- hyphen-compound (technical): no better than chance placement without priming. unprimed c over decoys +0 points (-3 to +4); unprimed c or d +7 points (-1 to +16).
- ranking (technical): the composite does not beat sentence length. composite minus longest -6 points (-16 to +4); composite minus random +35 points (+26 to +43).
- stacked-nouns (rounds 1 to 3): stays default.
- long-dependency (rounds 1 to 3): stays default.
- reduced-object-relative (rounds 1 to 3): stays default.
- hyphen-compound (rounds 1 to 3): stays default.
- inline-list (rounds 1 to 3): stays default.
- inanimate-subject (rounds 1 to 3): proposed default.
- participial-clause (rounds 1 to 3): proposed default.
- nominalization (rounds 1 to 3): proposed default.
- center-embedding (rounds 1 to 3): proposed default.
- undefined-acronym (rounds 1 to 3): stays opt-in.
