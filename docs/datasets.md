# Datasets with human signals about prose

These datasets record what people did with English prose: they rated it,
edited it, marked problems in it or read it. Each entry says which
question about readcost it can answer. No person has labelled
a readcost finding, so every dataset here answers a narrower question;
[evaluation.md](evaluation.md) reports what the ones marked "run" show.

Compiled 18 November 2026. "Checked" says how each entry was confirmed:

- **card**: the Hugging Face card or file listing, read for this list;
- **repo**: the repository's README, LICENSE or files;
- **paper**: the paper's text;
- **earlier**: an earlier section of evaluation.md;
- **memory**: not rechecked, a lead only.

 "Human label" says whether people
produced the outcome, and how that was checked; sets whose labels came from
a model are listed at the end and not used.

Status: **run** means `scripts/dataset_matrix.py` reads it and the
`matrix` job in the eval workflow runs it; **used before** means an earlier
evaluation used it; **#83** means that pull request 83, an experiment on discourse
patterns, uses it; **#92** means the pre-registered repetition test
([prereg/repetition.md](prereg/repetition.md)) uses it.

## Ratings, preferences and complaints

| Dataset | Human signal | Size | Licence | Host | Human label | readcost question | Checked | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [HelpSteer2](https://huggingface.co/datasets/nvidia/HelpSteer2) | 0 to 4 for helpfulness, correctness, coherence, complexity, verbosity | 21,362 responses | CC BY 4.0 | Hugging Face | yes: card says "five human-annotated attributes", made with Scale AI | do findings go with lower coherence or more verbosity among answers to the same prompt? | card | run |
| [HelpSteer](https://huggingface.co/datasets/nvidia/HelpSteer) | the same five attributes | about 37,000 (memory) | CC BY 4.0 | Hugging Face | yes (card) | as HelpSteer2; the card recommends v2 | card | #92: pre-registered repetition test |
| [HelpSteer3-Feedback](https://huggingface.co/datasets/nvidia/HelpSteer3) | three annotators each write a paragraph about a response | about 40,800 rows, two responses each | CC BY 4.0 | Hugging Face | yes (card); the complaint labels are matched here from the paragraphs | do annotators complain about length, clarity or repetition more often when findings are present? | card | run (derived labels) |
| [HelpSteer3-Preference](https://huggingface.co/datasets/nvidia/HelpSteer3) | -3 to 3 preference between two responses, with a 1 to 2 sentence reason per annotator | 40,476 pairs | CC BY 4.0 | Hugging Face | yes (card) | is the answer with fewer findings preferred? | card | #92: code domain only, pre-registered repetition test |
| [summarize from feedback, axis](https://huggingface.co/datasets/openai/summarize_from_feedback) | 1 to 7 for overall, accuracy, coverage, coherence | 14,900 ratings of TL;DR and CNN/DM summaries | OpenAI's modified MIT (covers the feedback data) | Hugging Face, Azure | yes: the repository calls it "our human feedback dataset" | do findings go with lower coherence among summaries of one post? | repo, card | run |
| summarize from feedback, comparisons | which of two summaries is better | 179,000 | as above | as above | yes (repo) | as above, pairwise | card | not run |
| [SummEval](https://huggingface.co/datasets/mteb/summeval) | mean of three experts' 1 to 5 ratings of coherence, consistency, fluency, relevance | 1,600 summaries of 100 articles | MIT | Hugging Face, [GitHub](https://github.com/Yale-LILY/SummEval) | yes (card tag `annotations_creators:human-annotated`; paper) | do findings go with lower coherence or fluency? | card, repo | run |
| [Stanford SHP](https://huggingface.co/datasets/stanfordnlp/SHP) | which of two Reddit comments got more votes, written later | 385,000 pairs | none on the card | Hugging Face | yes, collective votes; they judge content as much as prose | is the comment with fewer findings preferred? | card | not run |
| [Arena human preference 55k](https://huggingface.co/datasets/lmarena-ai/arena-human-preference-55k) | a user's vote between two answers | 55,000 | Apache-2.0 | Hugging Face | yes (votes) | as above | #83 | #83 |
| [Arena human preference 140k](https://huggingface.co/datasets/lmarena-ai/arena-human-preference-140k) | as above, newer models | 140,000 | CC BY 4.0 | Hugging Face | yes (card: "user votes") | as above | card | not run |
| [MT-Bench human judgments](https://huggingface.co/datasets/lmsys/mt_bench_human_judgments) | expert pairwise preferences | 3,300 | CC BY 4.0 | Hugging Face | yes: card says mostly graduate students | as above | card | not run |
| [WebGPT comparisons](https://huggingface.co/datasets/openai/webgpt_comparisons) | which of two answers is better | about 20,000 (memory) | not on the card | Hugging Face | yes (paper, memory) | as above | card | not run |
| [HH-RLHF](https://huggingface.co/datasets/Anthropic/hh-rlhf) | which of two replies is more helpful or less harmful | about 160,000 (memory) | MIT | Hugging Face | yes (card) | little: dialogue, and harmlessness | card | not run |
| [HANNA](https://github.com/dig-team/hanna-benchmark-asg) | three raters, six criteria including coherence and complexity | 1,056 stories | MIT | GitHub | yes (paper, memory) | do findings go with lower rated coherence of stories? | repo | not run |
| [LitBench](https://huggingface.co/datasets/SAA-Lab/LitBench-Test) | upvotes between two Reddit stories | 2,381 pairs, as comment ids only | none on the card | Hugging Face | yes (votes) | needs the texts fetched from Reddit | card | not run |
| [LAMP](https://github.com/salesforce/creativity_eval) | writers edit model paragraphs and label each edit (for example "Unnecessary Exposition") | 1,282 paragraphs | BSD-3-Clause | GitHub | yes (#83) | are findings edited more? | #83 | #83 |
| [ELLIPSE](https://github.com/scrosseye/ELLIPSE-Corpus) | two trained raters score each essay 1 to 5 for overall proficiency and six analytic traits, including cohesion | 3,911 essays in the public train file, 44 prompts (measured) | CC BY 4.0 (README) | GitHub | yes (paper) | does repetition go with lower rated cohesion in text people wrote? | repo | #92 |
| [PLABA-EVAL](https://github.com/SDS-NLP/PLABA-EVAL) | lay readers rate each sentence for ease | 609 sentences | CC BY 4.0 | GitHub | yes | as below | earlier | used before |
| ASSET, Simplicity-DA, SimpEval, Wu and Arase | ratings of simplifications | 100 to 6,163 | various | GitHub | yes | as below | earlier | used before |

## Revisions labelled with intent

| Dataset | Human signal | Size | Licence | Host | Human label | readcost question | Checked | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [IteraTeR, human, sentences](https://huggingface.co/datasets/wanyu/IteraTeR_human_sent) | intent of each revision: clarity, fluency, coherence, style, meaning-changed | about 4,000 pairs | Apache-2.0 | Hugging Face | yes (card tag `annotations_creators:crowdsourced`); the larger IteraTeR_full is labelled by a model and not used | do clarity and fluency edits remove findings more often than other edits? | card | run |
| [IteraTeR, human, documents](https://huggingface.co/datasets/wanyu/IteraTeR_human_doc) | the same intents on whole documents | under 1,000 | Apache-2.0 | Hugging Face | yes (card) | as above, per document | card | not run |
| [arXivEdits](https://github.com/chaojiang06/arXivEdits) | intent of each edit between two arXiv versions: readability, style, accuracy, grammar, content, format | 1,000 sentence pairs | none stated; per-paper arXiv licences listed | GitHub | yes (paper) | do readability edits remove findings more often? | repo | run |
| [ParaRev](https://huggingface.co/datasets/taln-ls2n/pararev) | two annotators label each revised paragraph: rewriting, concision, development, content | 641 annotated of 48,203 | CC BY-NC-SA 4.0 | Hugging Face | yes for the 641 (card; paper reports alpha 0.50 strict, 0.69 merged) | do concision revisions remove findings more often? | card, paper | run |
| [HelpSteer3-Edit](https://huggingface.co/datasets/nvidia/HelpSteer3) | an annotator edits a model response from others' feedback and summarises the change | 14,461 | CC BY 4.0 | Hugging Face | yes (card); the intent is matched here from the summary | do edits made for concision or clarity remove findings? | card | run (derived labels) |
| [Re3-Sci](https://github.com/UKPLab/re3) | three annotators label sentence edits as grammar, clarity, claim or fact | 314 document pairs, 11,648 edits | code Apache-2.0; data on TUdatalib, licence not checked | TUdatalib | yes (paper: alpha 0.78) | as IteraTeR, on scientific papers with reviews | paper, repo | not run: download host not tried |
| [CASIMIR](https://aclanthology.org/2024.lrec-main.257/) | revisions of 15,646 OpenReview papers | large | not checked | not checked | no: intents "automatically extracted" (abstract) | none | paper | excluded |
| [CoEdIT](https://huggingface.co/datasets/grammarly/coedit) | instruction and edited text | about 82,000 (memory) | Apache-2.0 | Hugging Face | the task tags come from the source datasets, not from judgments | none beyond IteraTeR, one of its sources | card | not run |
| [SALSA](https://github.com/davidheineman/salsa) | spans of each edit in simplifications, rated for efficacy and severity | about 19,000 edits (memory) | Apache-2.0 | GitHub | yes (paper, memory) | are deletions of findings rated as good edits? | repo | not run |
| [Med-EASi](https://huggingface.co/datasets/cbasu/Med-EASi) | expert and simple medical text with edit types | 1,979 pairs | MIT (repository) | Hugging Face | yes (card: crowdsourced) | which edit types remove findings in medical text | card, repo | not run |
| [ScholaWrite](https://github.com/minnesotanlp/scholawrite) | keystrokes of LaTeX writing with intention labels | 893 MB repository | MIT | GitHub | yes (memory) | revision intent at keystroke level | repo | not run |
| [WikiAtomicEdits](https://github.com/google-research-datasets/wiki-atomic-edits) | single insertions and deletions | 43 million (memory) | no licence file | GitHub | no intent labels | none | repo | not run |
| wikiHowToImprove (Anthonio et al. 2020) | revisions of how-to instructions | 2.7 million (memory) | not checked | the guessed repository does not exist | no intent labels (memory) | instructional prose before and after | repo | not found |
| ArgRewrite v2 | revision purposes in student essays | small (memory) | request form (memory) | University of Pittsburgh | yes (memory) | as IteraTeR, on essays | memory | not obtained |

## Readability and difficulty ratings

| Dataset | Human signal | Size | Licence | Host | Human label | readcost question | Checked | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [ReadMe++](https://github.com/tareknaous/readme) | CEFR level 1 to 6 per sentence, rated in its paragraph | 2,822 English sentences in 20 domains (measured) | README: personal, research and non-commercial use | GitHub | yes (paper) | do flagged sentences get higher levels than their length predicts, outside Wikipedia? | repo | run |
| CLEAR corpus | teachers' pairwise ease, fitted as Bradley-Terry | 4,724 excerpts | per excerpt | Hugging Face | yes | text-level difficulty | earlier | used before |
| CEFR-SP | CEFR level per sentence, two teachers | 9,946 public sentences | CC BY-SA 3.0, CC BY-NC-SA 4.0 | GitHub | yes | as ReadMe++ | earlier | used before |
| OneStopEnglish levels | three written levels per article | 189 articles | CC BY-SA 4.0 | GitHub | levels written by teachers | which measures separate levels | earlier | used before |
| [CompLex](https://github.com/MMU-TDMLab/CompLex) | complexity of a word in context | about 10,000 (memory) | CC BY 4.0 | GitHub | yes | none: no rule is about single words | earlier | not run |
| SR-Crowd | lexical, grammatical and overall difficulty per sentence | 1,000 sentences | paper CC BY 4.0 | not released | yes | grammatical difficulty apart from lexical | earlier | not available |
| Brunato et al. 2018 | 20 ratings per sentence | 1,200 WSJ sentences | request; LDC text | italianlp.it | yes | as ReadMe++ | earlier | not available |
| UniversalCEFR | CEFR labels gathered from many sets | 505,807 texts | mixed | Hugging Face | mixed provenance (memory) | as ReadMe++ | memory | not run |
| WeeBit, Newsela | grade levels | thousands | not open; Newsela licence | by request | levels by editors | level separation | memory | not available |

## Reading behaviour

| Dataset | Human signal | Size | Licence | Host | Human label | readcost question | Checked | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [GECO](https://expsy.ugent.be/downloads/geco/) | eye movements on a whole novel | 14 English monolinguals, about 5,000 sentences | free with citation | ugent.be | yes | are flagged sentences read more slowly per word than their length predicts? | page (file links) | run |
| OneStop Eye Movements | eye movements, two levels per paragraph | 360 readers | CC BY 4.0 | OSF | yes | as GECO, on news | earlier | used before; run again here |
| Provo | eye movements and cloze | 55 passages, 84 readers | CC BY 4.0 | OSF | yes | as GECO | earlier | used before; run again here |
| Natural Stories | self-paced reading | 10 stories, 180 readers | CC BY-NC-SA 4.0 | GitHub | yes | words inside findings | earlier | used before |
| EMTeC | eye movements on model text | 107 readers | not checked | OSF | yes | as GECO, on model text | #83 | #83 |
| MECO, English L1 | eye movements on 12 expository texts | about 46 readers (memory) | CC BY 4.0 (memory) | OSF | yes | as GECO, on expository text | memory | not run |
| ZuCo 1.0 and 2.0 | eye tracking and EEG | 1,107 and 739 sentences | CC BY 4.0 (1.0) | OSF | yes | as GECO | earlier | not run: large MATLAB files |
| [CELER](https://github.com/berzak/celer) | eye movements on newswire | 365 readers | CC BY 4.0 repository; texts need LDC | GitHub | yes | as GECO | repo | needs a licence |
| SAP benchmark | self-paced reading of constructed sentences | 2,000 readers | MIT repository; data on Google Drive | GitHub | yes | the cost of reduced relatives, for severities | repo | not run |
| UCL corpus; Dundee | eye tracking and self-paced reading | 361 sentences; 10 readers | supplement; not public | Springer; by request | yes | as GECO | earlier | not run |

## Annotated problems in model-written text

| Dataset | Human signal | Size | Licence | Host | Human label | readcost question | Checked | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [Scarecrow](https://github.com/yao-dou/scarecrow) | ten crowd annotators mark spans of ten error types, including Redundant, Technical Jargon, Incoherent, Grammar and Usage | 1,308 paragraphs (987 GPT-3), 41,862 spans (measured) | none stated | GitHub | yes (paper) | are words inside findings marked as jargon, redundant or incoherent more often? | repo | run |
| [Measuring AI "slop"](https://arxiv.org/abs/2509.19163) (Shaib et al.) | copy editors mark spans of density, verbosity, repetition, coherence and more | 213 articles and 123 passages | MIT repository | [GitHub](https://github.com/cshaib/slop) | yes (paper) | the closest match to the annoyances readers report | repo: README says "Coming soon!" | not released |
| LAMP | see above | | | | | | | #83 |

## Developer and documentation text

| Dataset | Human signal | Size | Licence | Host | Human label | readcost question | Checked | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [Comments on Comments](https://doi.org/10.5281/zenodo.5886145) (Rao et al. 2022) | review comments about code comments, with the change before and after | 65,000 cases; 240 labelled by hand | not checked | Zenodo | the 65,000 come from keyword filters (paper: precision 0.67); the 240 are human | do reviewers ask to clarify comments that have findings? | paper | not run |
| [github-codereview](https://huggingface.co/datasets/ronantakizawa/github-codereview) | inline review comments and the code after the fix | 167,000 | permissive source repositories (card) | Hugging Face | yes: bot reviewers removed (card) | little: code, not prose | search result | not run |
| [crc-py-dataset](https://github.com/busraicoz/crc-py-dataset) | review comments with categories including documentation | 16,711 | not checked | GitHub | no: categories from an SVM classifier (README) | none | search result | excluded |
| [Stack Exchange preferences](https://huggingface.co/datasets/HuggingFaceH4/stack-exchange-preferences) | answers to one question with their vote score (log2 of 1 plus upvotes, plus 1 if accepted) | 10.8 million questions over 300 sites | CC BY-SA 4.0 | Hugging Face | yes, collective votes; they judge content as much as prose | does repetition go with lower scores among answers people wrote to one technical question? | card | #92: first shard of four technical sites |
| Stack Exchange edits | a post before and after an edit | readcost's own sample | CC BY-SA | Stack Exchange API | yes (edits) | do edits remove findings? | earlier | used before |

## Technical text for word-pair counts

`scripts/eval_stack_terms.py` asks whether counts of word pairs tell an
established term from a coined noun stack, and needs counts from
technical writing. Only counts are kept.

| Corpus | Contents | Licence | Host | Checked | Status |
| --- | --- | --- | --- | --- | --- |
| [Common Pile Stack Exchange, filtered](https://huggingface.co/datasets/common-pile/stackexchange_filtered) | questions, answers and comments from Stack Exchange to December 2024, as plain text | CC BY-SA, per document in `metadata.license` | Hugging Face | card | run: one parquet shard, `stack-terms-tech` job |
| [Common Pile GitHub Archive, filtered](https://huggingface.co/datasets/common-pile/github_archive_filtered) | issue and pull request threads of repositories under open licences | each repository's licence, per document | Hugging Face | card | run: one parquet shard |
| The Stack v2, Markdown | READMEs and docs from GitHub | per file; gated | Hugging Face | memory | not run: needs accepting terms |

## Excluded because a model made the labels

| Dataset | How checked |
| --- | --- |
| [UltraFeedback](https://huggingface.co/datasets/openbmb/UltraFeedback) | card: "We then ask GPT-4 to annotate the collected samples" |
| [Nectar](https://huggingface.co/datasets/berkeley-nest/Nectar) | card: "7-wise ranking labeled by GPT-4" |
| IteraTeR_full; CASIMIR intents | IteraTeR paper (memory); CASIMIR abstract |
| crc-py-dataset | README: SVM classifier |

## Not about prose

FRANK (factuality spans, MIT) and RoSE (content units, BSD-3-Clause) rate
what a summary says, not how it reads. They would test nothing readcost
claims.
