# Why is AI-generated language so hard to understand?

Thomas Hikaru Clark, Matias B. Martin, Kyle Mahowald. 2026. arXiv
[2610.29162](https://arxiv.org/abs/2610.29162) (v1, 21 October 2026).

Read: full (arXiv v1, 23 pages: body, limitations, appendix A on data
collection, B on features and statistics, C on the RL experiment, tables 1
to 5, figures 1 to 10). Title and authors match. Figure panels are plots;
values below come from the text and the figure captions.

## Claim

Recent post-trained models use constructions that psycholinguistics ties
to processing difficulty more often than round-trip paraphrases of the same
content, and for some constructions more often than genre-matched human
text. The authors propose that pressure for information density during
post-training (verifiable rewards, length limits) causes this, and show a
proof of concept: a length penalty during RL makes a small model prefer the
shorter member of syntactic alternations, including ones never trained.

## Method and data

- 14 models: Claude Sonnet 5, Opus 5, Opus 5.5, Fable 5; GPT-5.6 Luna,
  Terra, Sol; GLM-5; Kimi K2.5; Llama 3.1 8B base and Instruct; Olmo 3 7B
  base, Instruct and Think. All run under one agent harness (Pi), medium
  reasoning, provider defaults.
- Three settings: chat (10 topics, 12 turns, simulated user; 120
  conversations, 1,428 replies), coding (5 public Python repos, frontier
  models only; 45 sessions), essays (7 PERSUADE 2.0 prompts, 10 essays per
  model, 980 total; 2,934 student essays scored 5 or 6 as the human
  reference).
- Human baselines: OpenSubtitles (chat), StackExchange (coding), PERSUADE
  students (essays), plus Wikipedia; about 500,000 words each.
- Features from spaCy `en_core_web_trf`: object relatives with and without
  a relativizer, stacked nouns (three or more nouns in a modifier
  relation), dependency length, denominal verbs, inanimate subjects with
  animate verbs, unattested bigrams per 1,000 pairs and trigram perplexity
  (KenLM, modified Kneser-Ney). Denominal-verb and inanimate-subject
  candidates come from the parse and are then accepted by an external
  classifier at p > 0.5; denominal candidates are verbs whose lemma is used
  mostly as a noun in the setting's human corpus.
- Dependency length is directly standardized: five sentence-length bins
  (1-5 to 21-30 words), sentences over 30 words dropped, bin weights from
  Wikipedia's arc distribution.
- Round trip: each sentence English to Japanese to English with NLLB-200
  3.3B; checked with a Russian pivot and with TranslateGemma.
- Statistics: two-sided paired jackknife t-tests over conversations,
  not corrected for multiple comparisons; 95% bootstrap intervals.
- Experiment 2: Qwen2.5-1.5B-Instruct, GRPO, task is turning JSON event
  descriptions into one sentence; reward is correctness times format minus
  lambda times length; 24 runs crossing lambda and KL beta.

## Results (numbers that matter)

- Against the round trip, almost all frontier and near-frontier models
  have more unattested bigrams and higher n-gram perplexity in all three
  settings; effects are absent or small for Llama and Olmo base and grow
  from Olmo base to Instruct to Think.
- The same pattern "largely" holds for denominal verbs, inanimate subjects
  and reduced object relatives; object relatives with a relativizer are
  under-used, which the authors read as skipping optional words.
- Stacked nouns and dependency length follow the pattern in chat and
  coding; in essays dependency length is unchanged or longer after the
  round trip and stacked nouns change significantly for only two models.
- Against student essays (figure 3b), the consistent excess is inanimate
  subjects and low-frequency n-grams. Denominal verbs and inanimate
  subjects were not scored on the chat and coding human corpora at all.
- Claude Opus 5.5 is lower than Opus 5 on 19 of 21 difficulty-linked
  comparisons (non-overlapping intervals in eight).
- Experiment 2: for any lambda > 0 without KL, all seeds converge to the
  short variant (over 98% for both trained "that" alternations); with KL
  the shift is gradual. Near transfer to untrained "that" alternations
  holds; of four far-transfer alternations only the genitive shifts, and
  only without KL.

## What the full text qualifies

- No reading-time, comprehension or rating study of model text. The
  difficulty link for each construction is cited from prior work, and the
  kind of evidence differs: surprisal and dependency length have
  reading-time evidence; denominal verbs and inanimate subjects are
  supported by ERP and reanalysis studies (P600, part-of-speech conversion)
  and by animacy as a parsing cue, not by reading times on such sentences.
- Object relatives: the authors themselves note that animacy and frequency
  reduce the object-relative cost (Mak et al. 2006; Reali and Christiansen
  2007), which is the qualification readcost's pronoun-subject exception
  relies on.
- The comparison to humans is genre-approximate (subtitles for chat), and
  for chat and coding the human corpus is also the n-gram reference.
- Limitations: few seeds and topics, English only, proxies for
  post-training.

## For readcost (used / tested / candidate)

Used: the source of the five "paper" rules (stacked-nouns,
long-dependency, inanimate-subject, denominal-verb,
reduced-object-relative) and of the rare-word-pair plan.

Citation accuracy:

- docs/research.md lines 12-15: "overuse these constructions relative to
  paraphrases of the same content and to human corpora ... ran no reading
  study on model text." Accurate on the paraphrase comparison and on the
  absence of a reading study. "To human corpora" is too broad: against
  humans the paper finds a consistent excess only for inanimate subjects
  and rare n-grams, mixed results for the rest, and it never compared
  denominal verbs or inanimate subjects with the chat and coding human
  corpora.
- README.md lines 63-66: "finds that recent language models use them more
  than people do; earlier reading studies tie each of them to slower
  reading." The first half needs the same qualification. The second half
  overstates the prior evidence: for denominal verbs and inanimate
  subjects the cited evidence is ERP and reanalysis work, not reading
  times.
- src/readcost/features.py (hyphen-compound, "rare word pairs, which the
  paper links to slower reading"): fair; the paper ties low-probability
  words to reading time via Levy 2008 and Smith and Levy 2013.
- docs/research.md line 88, "the anchor paper's most consistent signal is
  the rate of word pairs absent from a reference corpus": accurate.

Differences in method worth knowing: Clark uses the transformer parser and
an external classifier to accept denominal-verb and inanimate-subject
candidates; readcost uses a small parser and WordNet sense counts, which
evaluation.md shows fire on settled verbs. Clark drops sentences over 30
words from dependency length; readcost scores every sentence against a
length profile.

## Open questions

- Does the classifier gate Clark used for denominal verbs explain why its
  rule works there and readcost's does not?
- The paper's own Opus 5 to 5.5 drop says the rates move between model
  versions; a reference profile per model version may be needed.
