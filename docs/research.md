# Research basis and roadmap

readcost locates sentences whose construction tends to cost readers time. It
does not grade documents, and it cannot see content problems: missing,
ambiguous or wrong information. Developers rate ambiguity, incompleteness and
incorrectness as the worst documentation failures (Uddin and Robillard 2015),
and consistency between comments and code, which includes staleness, is the
most studied comment-quality attribute (Rani et al. 2022). Studies and tools
that compare comments with code changes cover that (Wen et al. 2019;
Panthaplackel et al. 2021).

## What the evidence supports

- The detectors come from Clark, Martin and Mahowald (arXiv 2610.29162). They
  show language models overuse these constructions relative to paraphrases of
  the same content; against human corpora the excess is consistent only for
  inanimate subjects and rare word pairs. That is a claim about rates, not
  about single sentences, and the paper ran no reading study on model text.
- Technical prose is noun-heavy by register. Biber and Gray (2010) argue,
  without measuring it, that compressed noun phrases are efficient for
  expert readers and costly for newcomers. A stacked noun that names a defined term is not the same as one
  coined for a single sentence.
- No single static metric predicts how well people understand code
  (Scalabrino et al. 2017; Peitek et al. 2021); reader experience matters
  most, and combined metrics add a small real signal (Trockman et al. 2018). The same caution applies to a
  prose index. Per-sentence findings are the primary output; the file index is
  for trends and gates.
- Shorter is not the goal. Compressed rewrites can raise reading cost per word
  (Cekini et al., arXiv 2610.23715). Rewrites restore optional words such as
  "that" and keep rationale clauses: rationale is the part of a comment that
  cannot be recovered from the code, and summarization models fail on it
  most (Chen et al. 2021). Done: when a long-dependency or inline-list sentence
  gives a reason, the suggestion says to keep it.
- Two opt-in detectors count constructions that language models overuse:
  nominalizations and present participial clauses (1.5 to 2 and 2 to 5 times
  the human rate in Reinhart et al. 2025, over general genres). Repetition
  of sentence frames is measured across many texts by `readcost corpus`
  (Shaib et al. 2024), not per document.
- Two opt-in rules with weaker evidence. center-embedding flags a clause
  nested two deep inside clauses that continue after it. Gibson (1998, 2000)
  argues from acceptability judgements of constructed sentences that such
  nesting is hard, except when the innermost subject is I or you (readcost
  skips those). Wu et al. (2010) find that a parser's change in embedding
  depth adds to reading time beyond surprisal over all words, though not
  for open-class words, in one constructed corpus. undefined-acronym flags an acronym used before it is
  spelled out; the only evidence is a magazine report of self-rated
  difficulty, whose authors recommend spelling a term out at every use
  (Hales, Williams and Rector 2017). No
  study was found on terminology consistency, and none supports a check for
  ambiguous pronouns: Gordon, Grosz and Gilliom (1993) find that repeating a
  name where a pronoun would do slows reading.
- Document measures (JSON `metrics`) describe rather than judge: MTLD, idea
  density by DEPID (Sirts et al. 2017), center-embedding depth, and a
  sentence-length profile in the manner of Alves et al. (2010).
- Gibson's Dependency Locality Theory measures a gap by the new nouns and
  verbs in it rather than by words. On labelled long-dependency findings it
  separated accepted from rejected findings no better than word distance
  (docs/evaluation.md), so long-dependency still counts words.
- What fills a gap may matter more than its length. Nusbaumer et al. (2026,
  Table 2) held the gap at four words in constructed sentences. Readers took
  22 ms longer at the verb after a prepositional phrase, 49 ms after a subject
  relative and 93 ms after an object relative. `long_dependency_gap =
  "content"` names what fills the gap and lowers a prepositional gap to info.
  It stays opt-in until `scripts/eval_gap_content.py` shows that the raters
  accept prepositional gaps less often than the others.

## Contexts and reference profiles

Text from different places fails differently and is read differently, so
each context gets its own defaults and its own reference profile.

| Context | Detected from | Differences from the README defaults |
| --- | --- | --- |
| readme | Markdown, RST, HTML files | Baseline. Introduction and purpose sections stay strict. |
| doc-comment | Rust `///`, Python docstrings, `/** */` | Tag and parameter lines (`@param`, `Args:`, `# Arguments`) skipped; in Java, `@param` and `@throws` lines are mostly predictable from the code, `@return` lines less so (Louis et al. 2018). |
| inline-comment | `//`, `#` comments with `comments = "all"` | Syntax findings at info level. A comment's effect on comprehension ranges from harmful to helpful by snippet (Abdelsalam et al. 2026), and on small tasks comments made little measurable difference (Nielebock et al. 2019). |
| commit-subject | First line of a commit message | Stacked-noun and hyphen-compound off: subjects are headlines. |
| commit-body | Rest of a commit message | On. Commit-message studies judge whether a message says what changed and why (Tian et al. 2022; Li and Ahmed 2023); readcost checks only how it is written. |
| llm-output | stdin, chat JSON, transcripts | Baseline plus the full detector set. |

A profile records the reference distribution that a context is judged
against: today, how dependency length grows with sentence length; later,
attested word pairs and thresholds.
Profiles are built with `readcost profile build` from a named corpus with its
date and source recorded. Thresholds should come from percentiles of that
corpus (Alves, Ypma and Visser 2010) rather than from the current ten
READMEs by one author.

Short units need absolute counts. One finding in a twelve-word comment gives
a cost index above 80, so below about 40 words the verdict uses the number of
findings, not the density. The 40-word cut is readcost's own choice.

## Terminology

A compound that recurs in the document, appears in a heading, a code span or
a glossary, or is listed in `allow` is treated as a defined term. Its first
unexplained use in a README is still reported. Identifiers and code spans are
opaque heads: `` `parse()` returns `` is not an inanimate subject.

## Rare word pairs

The anchor paper's most consistent signal is the rate of word pairs absent
from a reference corpus. readcost will ship, per context, a compact set of
hashed bigrams seen in its reference corpus, checked in pure Python. An
optional `readcost[lm]` extra adds trigram perplexity from KenLM for offline use;
KenLM is LGPL and builds from source.

## Code complexity

Complexity tools such as lizard measure a different thing and predict
understanding only weakly. readcost may use them for triage: ordering
findings in inline comments so that comments on complex functions come
first, since inline and block comments cluster on longer and more complex code
(Chin and Holmes 2026; the finding excludes docstrings). It
will not fold complexity into the score. Any new index is checked against a
plain baseline, the number of sentences times their mean length, before it
is trusted (Shepperd 1988).

## Gating

CI should gate new and changed text against a stored baseline, as the git and
Claude Code hooks already do for edited lines. A rewrite that lowers the
index while adding words is reported, not rewarded.

## Dependencies

- Core: spaCy, markdown-it-py and mdit-py-plugins (Markdown with line maps).
- `readcost[source]`: the tree-sitter grammars and docstring-parser, with
  the current `ast` and regex path as the fallback.
- `readcost[rst]`: docutils, with the regex fallback kept.
- `readcost[lm]`: KenLM.
- Build-time only: WordNet data (nltk or wn), lemminflect.

## Discourse patterns and redundancy

People who find model-written text tiring rarely name the constructions
readcost flags. They name contrast framing ("it's not X, it's Y"), padding
and restatement, lists of three, signposting, summary closers and uniform
sentences and paragraphs. This section records what was read about those
patterns; the measurements are in
[evaluation.md](evaluation.md#discourse-patterns-and-redundancy).

Open rule sets, read at the commits named:

| Rule set | Licence | What its structural rules are | Evidence it cites |
| --- | --- | --- | --- |
| slop-guard (eric-tramel/slop-guard, `7ef2113`) | MIT | 24 rules. Regular expressions for "X, not Y", "not only X but Y" and a negated clause followed by "it's" (contrast-pair, setup-resolution); "A, B, and C"; sentence-length spread under 0.3 over five sentences; paragraph balance; repeated 4- to 8-word phrases; share of sentences with a copula; a closing sentence that matches two of eight stock openings | thresholds fitted to public-domain newspapers; no reader data |
| vale-ai-tells (tbhb/vale-ai-tells, `51f646e`, v1.37.0) | MIT | 137 rule files, nearly all lists of phrases. A separate experimental style scripts sentence-length spread under 0.30, paragraph-length spread under 0.25, one first word opening over 30% of sentences, paragraph pairs with word overlap over 60%, and the share of lists with three items | style guides, blog posts, Reinhart et al. 2025 and Kobak et al. 2025; the README says a model wrote most rule definitions; no reader data |
| SlopBench (hgaddipati1118/slop-index, `4eb24d9`) | MIT | length against the length the task asked for, repeated openers across samples, paragraph-length spread against a human corpus, fixed constructions | its crowd vote, a detector and lexical diversity each failed to confirm the ranking (Roongta et al. 2026) |
| slop-forensics, humanizer | MIT | word and phrase lists; an agent skill built on Wikipedia's "Signs of AI writing" | none |

The rule sets agree on what to count and none shows that a reader pays for
it. The thresholds are set by eye or against human text, which makes each
rule a marker of model text by construction.

Studies, with how each was read:

- Contrast framing has one study with readers. "Rather than" occurs 0.13
  times per 1,000 words in ACL 2019 papers and 0.99 in arXiv NLP papers of
  2026; "X, not Y" rose from 0.05 to 0.20. Two reviewers labelled uses blind:
  almost none of the 2019 uses annoyed either, and about half of the 2026
  papers hold a use that annoys a given reviewer. The two seldom agreed on
  which uses. The outcome is annoyance, not reading time or comprehension,
  and the uses that annoyed reject a position nobody holds, which no
  pattern-matcher can see (Zamaraeva et al. 2026; results and method
  sections read).
- Padding is what annotators agree on, weakly. Three copy editors marked
  spans in 213 news articles and 123 answers. Verbosity was the one code
  that predicted every annotator's "slop" label, but agreement on that label
  was poor (Cohen's kappa -0.15 to 0.29), and compression ratio and
  templates per token did not predict it. A model of every automatic
  measure reached an area under the precision-recall curve of 0.52 against a base rate of 0.25
  (Shaib et al. 2025; sections 4 to 6 read). The repository that should hold
  the annotations says "Coming soon" (cshaib/slop, `62c6e0a`).
- Raters reward length. Among answers to the same prompt in PRISM, a longer
  answer was rated higher (1.84 points per standard deviation of length);
  24% of participants asked for longer answers and 7% for shorter (Chen,
  Zheng and Zhu 2026; results read). YapBench measures excess length on
  prompts with a short right answer and cites, without testing, that it
  costs the reader (Borisov et al. 2026).
- Markers of model text are not what readers react to. Features that
  separate model-written comments from human ones did not predict which
  human comments were accused of being model-written, in 421 accused
  comments against 2,048 matched controls (Miklian and Katsos 2026; the
  matched-control section read).
- Redundancy is not a cost for every reader. Cohesive, explicit text helps
  readers who know little about the topic and can hurt those who know a lot
  (the redundancy and expertise-reversal effects; Yeung, Jin and Sweller
  1998; Rey and Buchwald 2011; abstracts only). A measure of repetition
  cannot say which reader a text is for.
- Uniform sentence length, lower in model news text than in human
  (Muñoz-Ortiz, Gómez-Rodríguez and Vilares 2024; abstract only), and
  compression ratio (Hadad et al. 2026; abstract only) are measured as
  differences between sources, with no reader outcome.
- Reading time on model text has been predicted (Cekini et al. 2026, above)
  and measured once, in EMTeC: 107 people's eye movements on texts by three
  models (Bolliger et al. 2025). No study relates any of these patterns to
  it; the evaluation here does.

- Measured since: repetition goes with worse ratings in every large rating
  set of model text that was tried. The share of content words already
  used, restatements and the overlap of neighbouring sentences go with lower
  coherence ratings in HelpSteer2, SummEval and OpenAI's CNN/DM summaries
  (partial r +0.09 to +0.29 toward worse) and with more of HelpSteer3's
  annotators complaining about repetition (+0.17), with length and word
  frequency held. Contrast framing and lists of three track nothing there
  (evaluation.md, "Many datasets with human signals"). This is preference,
  not reading time: in OneStop and Provo the same measures show nothing.

Not read: work on entity-grid coherence in model text, and the uniform
information density literature beyond what
[evaluation.md](evaluation.md#model-signals) already tests.

## What has not been shown

- One rule has support beyond surprisal, and one has indirect support. In
  constructed sentences read word by word, a four-word gap between subject
  and verb cost about 93 ms at the verb when an object relative filled it
  and 22 ms when a prepositional phrase did (means; medians 45 and 13 ms;
  Nusbaumer et al. 2026). Object relatives also cause more regressions than
  surprisal predicts (Timkey et al. 2026). Both studies kept the
  relativizer, so neither tests the reduced form that
  reduced-object-relative flags. `long_dependency_gap = "content"` uses the
  first result.
- On OneStop, changes in embedding depth, integration cost and idea density
  were not significantly correlated, in most evaluations, with how much
  easier simplified sentences and paragraphs were to read; changes in word
  length, frequency and surprisal were (Gruteke Klein et al. 2026, Figure
  1). The simplifications were mostly paraphrase, so syntax may have changed
  too little to show an effect.
  readcost's rules have not had that test; `scripts/eval_onestop_pairs.py`
  runs it.
- Splitting two- to four-word noun phrases in health sentences made them
  look slightly easier and raised cloze errors from 8.5% to 10.9% (Leroy,
  Kauchak and Hogue 2016). Splits that readers judged more natural did
  better (r = .43 over 21 prepositions). Technical terms were excluded, so
  the study does not cover coined stacks. The stacked-nouns advice is
  conditional for that reason.
- Across 20 datasets, model judges agreed with people less on the datasets
  of model-written text than on those of human-written text (Bavaresco et
  al. 2025); the two sets differ in task, so this is not a matched
  comparison. The alternative annotator test (Calderon, Reichart and Dror
  2025) says how to check model raters against three or more people on 100
  to 150 items (50 to 100 only if the people are experts), using the version
  for skewed labels and reporting agreement among the people. readcost has
  not run it. `readcost label export` writes the sheet for the people and
  `readcost label agreement` reports their agreement
  ([labels.md](labels.md)).
- Nothing readcost computes today tells an established term from a coined
  noun stack. The test used 27 labelled stacked-nouns findings and 25
  hyphen-compound findings. Counts of adjacent word pairs from web text,
  bracketing by pair strength and recurrence in the document all failed to
  separate accepted from rejected findings. Counts of the whole stack as a
  phrase dropped three rejected findings and no accepted one, which is too
  few to act on (docs/evaluation.md, "Noun stacks"). Earlier work explains
  part of this. Pair counts were built to bracket a compound, not to say
  whether it is a term: Lauer 1995 got 77.5% of 244 three-noun compounds
  right with the dependency model and 68.9% with the adjacency model, and
  Nakov and Hearst 2005 reached 89.3% by adding surface cues from the web.
  Term extraction scores the whole candidate instead: C-value is the
  candidate's frequency, lowered when it mostly occurs inside longer
  candidates and weighted by its length (Frantzi, Ananiadou and Mima
  2000). Trained extractors are still imprecise: the best English system at
  TermEval 2020 had 35% precision and 71% recall (Rigouts Terryn et al.
  2020). Farahmand, Smith and Nivre 2015 had experts mark 1,048 two-noun
  compounds as conventionalized or not, the closest existing labels to
  "established"; there is no such set for longer stacks.

- Findings do not track what raters think of a text. In seven rating sets
  of 52,000 texts (HelpSteer2, HelpSteer3, SummEval, two of OpenAI's
  summary sets, ReadMe++, Scarecrow), the default rules' weighted findings
  have partial correlations of -0.01 to +0.08 with the primary outcome once
  length and word frequency are held, and only Scarecrow's interval clears
  zero, barely. A score fitted on some of these sets does worse on the one
  left out than the untuned count. The one reading-time set with a positive
  result is GECO, a novel read by 14 people: +0.05 (+0.02 to +0.09), with
  surprisal not held. People revising for clarity or concision rewrite
  flagged sentences more often than other revisers (+10 points in
  HelpSteer3-Edit, +26 for long-dependency in ParaRev), but leave as many
  findings per 100 words as before. So the evidence supports saying that
  readcost flags sentences that writers revising for clarity tend to
  rewrite, and that may read slightly slower. It does not support saying
  that a finding costs a reader time or that a document with more findings
  is rated worse. The README's opening sentence ("whose construction slows
  readers down") says more than this; restating it is a separate change.
- undefined-acronym is the one opt-in rule with consistent outside support,
  and it is support from ratings only: Scarecrow's annotators marked more of
  a paragraph as technical jargon when it had one (+0.22), and ReadMe++
  sentences with one were rated a higher CEFR level (+0.12). OneStop
  paragraphs with one were read faster, on 28 paragraphs.

## Roadmap

0. Human labels on 100 to 150 findings, with the alternative annotator test;
   the OneStop paired test. Both come before more precision work, because
   every current number rests on model raters.

1. Markdown extraction on markdown-it-py; line numbers from its block map.
2. Contexts with per-context defaults; tag-line skipping; absolute counts for
   short units.
3. Terminology as defined units; code spans as opaque heads.
4. Per-context reference profiles and percentile thresholds from named
   corpora; a regression set of labeled findings with a second rater.
5. Attested word-pair sets; optional KenLM extra.
6. A baseline file for CI gating, and a check that rewrites do not add words.
7. Optional obvious-comment check (a doc comment that only restates its
   function's name, or an inline comment of two words or fewer; Steidl,
   Hummel and Juergens 2013) and complexity-ordered triage.

### Terms in the human-label study

Item 0 should settle whether a term exemption for stacked-nouns and
hyphen-compound is worth having. The model labels cannot: they cover 27
and 25 findings, of which 10 and 6 were accepted.

- Sample by evidence, not at random. Run `scripts/eval_stack_terms.py` over
  the study's texts and draw stacked-nouns findings from three groups: the
  whole stack is attested (five or more documents of a reference corpus),
  only its pairs are attested, and neither. About one finding in ten has an
  attested stack, so a random sample of 150 would hold about 15. Draw 40
  from each group. For hyphen-compound, draw 30 whose hyphenated pair is
  attested as an open pair and 30 whose pair is not. Weight the groups back
  to their shares when reporting overall precision.
- Count in technical text as well as FineWeb-Edu: READMEs, documentation
  and Stack Overflow answers, where `call stack` and `pull request` are
  common. The web shard held none of the Go and CPython terms in the bench.
  `scripts/build_open_pairs.py --phrases` counts whole stacks. A general
  list of three-word terms needs a tagger run over the corpus, or C-value
  over its noun phrases.
- Ask each rater two questions per finding: would an editor change this,
  and would a reader of this document already know the phrase as a term.
  The second question separates "the exemption is wrong" from "the stack is
  a term and still worth unpacking". Raters accepted `core team member`,
  which is the second kind.
- Record whether the stack occurs again in the document and whether the
  document introduces it, so that the document's own evidence gets the same
  test.
- Decide beforehand. The exemption becomes an opt-in setting if people
  accept at most 1 of 40 attested stacks (a 95% upper bound under 15%) and
  clearly more of the unattested ones. It becomes the default only if that
  holds on texts from a second project and it removes at least a tenth of
  the stacked-nouns findings there. An exemption that removes 6% of
  findings cannot change the rule's precision much.

A larger list can ship. FineWeb-Edu is under ODC-By 1.0, which asks for
attribution only, and readcost already carries its notice. Pairs in 20 or
more documents with PMI 6 or more fit in 0.2 MB as a Bloom filter.
Wiktionary's category of English multiword terms has about 228,000 entries
and Wikipedia has millions of titles. Both are under CC BY-SA, whose
share-alike term may reach a list made from them, so check before shipping
either in a package under MIT or Apache-2.0. The licence of the two wikis
is stated from memory; the other facts here were read at the source.

## References

Reading notes on each paper, with how much of it was read, are in
[docs/papers](papers/).

- Abdelsalam, Peitek, Bergum and Apel 2026. The effect of comments on program
  comprehension: an eye-tracking study. Empirical Software Engineering 31.
- Alves, Ypma and Visser 2010. Deriving metric thresholds from benchmark data.
  ICSM.
- Brown, Snodgrass, Kemper, Herman and Covington 2008. Automatic measurement
  of propositional idea density from part-of-speech tagging. Behavior
  Research Methods 40(2).
- Biber and Gray 2010. Challenging stereotypes about academic writing.
  Journal of English for Academic Purposes 9(1).
- Bolliger, Haller, Cretton, Reich, Kew and Jäger 2025. EMTeC: a corpus of
  eye movements on machine-generated texts. Behavior Research Methods 57.
- Borisov, Gröger, Mikhael and Schreiber 2026. Do chatbot LLMs talk too
  much? The YapBench benchmark. arXiv 2601.00624.
- Cekini et al. 2026. The cognitive cost of LLM writing. arXiv 2610.23715.
- Chen, Xia, Hu, Lo and Li 2021. Why my code summarization model does not
  work. TOSEM 30(2), doi 10.1145/3434280.
- Chin and Holmes 2026. Put the "code" back in "code comprehension study".
  ICPC.
- Clark, Martin and Mahowald 2026. Why is AI-generated language so hard to
  understand? arXiv 2610.29162.
- Gibson 1998. Linguistic complexity: locality of syntactic dependencies.
  Cognition 68(1).
- Gibson 2000. The dependency locality theory: a distance-based theory of
  linguistic complexity. In Image, Language, Brain, MIT Press.
- Gordon, Grosz and Gilliom 1993. Pronouns, names, and the centering of
  attention in discourse. Cognitive Science 17.
- Hales, Williams and Rector 2017. Alienating the audience: how abbreviations
  hamper scientific communication. APS Observer 30(2).
- Karlsson 2007. Constraints on multiple center-embedding of clauses.
  Journal of Linguistics 43(2), doi 10.1017/S0022226707004616.
- Li and Ahmed 2023. Commit message matters. ICSE.
- McCarthy and Jarvis 2010. MTLD, vocd-D, and HD-D: a validation study of
  sophisticated approaches to lexical diversity assessment. Behavior Research
  Methods 42(2).
- Louis, Dash, Barr and Sutton 2018. Deep learning to detect redundant method
  comments. arXiv 1806.04616.
- Nielebock et al. 2019. Commenting source code: is it worth it for small
  programming tasks? Empirical Software Engineering 24.
- Nusbaumer, de-Dios-Flores, Bel, Pallier, Wisniewski and Crabbé 2026.
  StructuralCost: a controlled reading time dataset for modeling human
  sentence processing difficulty. arXiv 2610.08208.
- Panthaplackel, Li, Gligoric and Mooney 2021. Deep just-in-time
  inconsistency detection between comments and source code. AAAI.
- Peitek et al. 2021. Program comprehension and code complexity metrics: an
  fMRI study. ICSE.
- Rani et al. 2022. A decade of code comment quality assessment. JSS.
- Reinhart et al. 2025. Do LLMs write like humans? Variation in grammatical
  and rhetorical styles. PNAS 122(8), e2422455122.
- Scalabrino et al. 2017. Automatically assessing code understandability: how
  far are we? ASE.
- Shaib et al. 2024. Detection and measurement of syntactic templates in
  generated text. EMNLP; arXiv 2407.00211.
- Shepperd 1988. A critique of cyclomatic complexity as a software metric.
  Software Engineering Journal.
- Sirts, Piguet and Johnson 2017. Idea density for predicting Alzheimer's
  disease from transcribed speech. CoNLL; arXiv 1706.04473.
- Steidl, Hummel and Juergens 2013. Quality analysis of source code comments.
  ICPC.
- Tian et al. 2022. What makes a good commit message? ICSE.
- Trockman et al. 2018. "Automatically assessing code understandability"
  reanalyzed. MSR.
- Uddin and Robillard 2015. How API documentation fails. IEEE Software 32(4).
- Wen, Nagy, Bavota and Lanza 2019. A large-scale empirical study on
  code-comment inconsistencies. ICPC.
- Wu, Bachrach, Cardenas and Schuler 2010. Complexity metrics in an
  incremental right-corner parser. ACL.
- Bavaresco et al. 2025. LLMs instead of human judges? A large scale
  empirical study across 20 NLP evaluation tasks. arXiv 2406.18403.
- Calderon, Reichart and Dror 2025. The alternative annotator test for
  LLM-as-a-judge. arXiv 2501.10970.
- Gruteke Klein, Frenkel, Shubi and Berzak 2026. Eye tracking based cognitive
  evaluation of automatic readability assessment methods. arXiv 2502.11150.
- Leroy, Kauchak and Hogue 2016. Effects on text simplification: evaluation
  of splitting up noun phrases. Journal of Health Communication 21(Suppl),
  doi 10.1080/10810730.2015.1131775.
- Nusbaumer et al. 2026. StructuralCost: a controlled reading time dataset
  for modeling human sentence processing difficulty. arXiv 2610.08208.
- Timkey et al. 2026. Eye movements reveal a dissociation between prediction
  and structural processing difficulty in language comprehension. PNAS,
  doi 10.1073/pnas.2532230123.
- Chakrabarty, Laban and Wu 2025. Can AI writing be salvaged? Mitigating
  idiosyncrasies and improving human-AI alignment in the writing process
  through edits. arXiv 2409.14509. The LAMP corpus.
- Chen, Zheng and Zhu 2026. Abstract priorities, concrete rewards: how
  stated preferences relate to what people reward in AI responses. arXiv
  2610.30763.
- Farahmand, Smith and Nivre 2015. A multiword expression data set:
  annotating non-compositionality and conventionalization for English noun
  compounds. Workshop on Multiword Expressions, NAACL.
- Frantzi, Ananiadou and Mima 2000. Automatic recognition of multi-word
  terms: the C-value/NC-value method. International Journal on Digital
  Libraries 3(2).
- Hadad, Loru, Nudo, Di Marco, Cinelli and Quattrociocchi 2026. The
  statistical signature of LLMs. arXiv 2602.18152.
- Kobak et al. 2025. Delving into ChatGPT usage in academic writing through
  excess vocabulary. arXiv 2406.07016.
- Lauer 1995. Corpus statistics meet the noun compound: some empirical
  results. ACL. arXiv cmp-lg/9504033.
- Miklian and Katsos 2026. "That's AI slop, you bot!" Studying accusations,
  evidence, and credibility in online discourse towards LLM-generated
  comments. arXiv 2606.12073.
- Muñoz-Ortiz, Gómez-Rodríguez and Vilares 2024. Contrasting linguistic
  patterns in human and LLM-generated news text. arXiv 2308.09067.
- Nakov and Hearst 2005. Search engine statistics beyond the n-gram:
  application to noun compound bracketing. CoNLL.
- Rey and Buchwald 2011. The expertise reversal effect: cognitive load and
  motivational explanations (PubMed 21443379).
- Rigouts Terryn, Hoste, Drouin and Lefever 2020. TermEval 2020: shared
  task on automatic term extraction using the ACTER dataset. Computerm
  workshop, LREC.
- Roongta, Gaddipati and Huynh 2026. SlopBench: how well can we rank
  language models by slop? arXiv 2609.33905.
- Shaib, Chakrabarty, Garcia-Olano and Wallace 2025. Measuring AI "slop" in
  text. arXiv 2509.19163.
- Yeung, Jin and Sweller 1998. Cognitive load and learner expertise:
  split-attention and redundancy effects in reading with explanatory notes
  (PubMed 9514686).
- Zamaraeva, Gude, Santos-Ríos and Gómez-Rodríguez 2026. I would rather quit
  NLP than read another paper like this: the rise of antithesis in NLP
  papers. arXiv 2610.10092.
