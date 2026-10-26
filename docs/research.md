# Research basis and roadmap

readcost locates sentences whose construction tends to cost readers time. It
does not grade documents, and it cannot see content problems: missing,
wrong or stale information. Developers rate those as the worst documentation
failures (Uddin and Robillard 2015), and comment staleness is the most studied
comment-quality problem (Rani et al. 2022). Tools that compare comments with
code changes cover that (Wen et al. 2019; Panthaplackel et al. 2021).

## What the evidence supports

- The detectors come from Clark, Martin and Mahowald (arXiv 2610.29162). They
  show language models overuse these constructions relative to paraphrases of
  the same content and to human corpora. That is a claim about rates, not
  about single sentences, and the paper ran no reading study on model text.
- Technical prose is noun-heavy by register. Compressed noun phrases are
  efficient for expert readers and costly for newcomers (Biber and Gray
  2010). A stacked noun that names a defined term is not the same as one
  coined for a single sentence.
- No single static metric predicts how well people understand code
  (Scalabrino et al. 2017; Peitek et al. 2021), and reader experience matters
  more than any metric (Trockman et al. 2018). The same caution applies to a
  prose index. Per-sentence findings are the primary output; the file index is
  for trends and gates.
- Shorter is not the goal. Compressed rewrites can raise reading cost per word
  (Cekini et al., arXiv 2610.23715). Rewrites restore optional words such as
  "that" and keep rationale clauses, which are rare and valuable in comments
  (Chen et al., TOSEM). Done: when a long-dependency or inline-list sentence
  gives a reason, the suggestion says to keep it.
- Three opt-in detectors count constructions that language models overuse:
  nominalizations and present participial clauses (1.5 to 2 and 2 to 5 times
  the human rate in Reinhart et al. 2025, over general genres), and sentence
  frames repeated within one document. Shaib et al. 2024 count templates
  across many outputs of one model, not within one document, and they make
  no claim about reading time; repeated-frame is a style signal only.

## Contexts and reference profiles

Text from different places fails differently and is read differently, so
each context gets its own defaults and its own reference profile.

| Context | Detected from | Differences from the README defaults |
| --- | --- | --- |
| readme | Markdown, RST, HTML files | Baseline. Introduction and purpose sections stay strict. |
| doc-comment | Rust `///`, Python docstrings, `/** */` | Tag and parameter lines (`@param`, `Args:`, `# Arguments`) skipped; they are mostly predictable from the code (Louis et al. 2018). |
| inline-comment | `//`, `#` comments with `comments = "all"` | Syntax findings at info level; comment value depends on context (Abdelsalam et al. 2026; Nielebock et al. 2019). |
| commit-subject | First line of a commit message | Stacked-noun and hyphen-compound off: subjects are headlines. |
| commit-body | Rest of a commit message | On; a missing "why" is the main quality signal (Tian et al. 2022; Li and Ahmed 2023). |
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
findings, not the density (Chin and Holmes 2026).

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
findings in doc comments so that comments on complex functions come first, since
comments cluster on longer and more complex code (Chin and Holmes 2026). It
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

## Roadmap

1. Markdown extraction on markdown-it-py; line numbers from its block map.
2. Contexts with per-context defaults; tag-line skipping; absolute counts for
   short units.
3. Terminology as defined units; code spans as opaque heads.
4. Per-context reference profiles and percentile thresholds from named
   corpora; a regression set of labeled findings with a second rater.
5. Attested word-pair sets; optional KenLM extra.
6. A baseline file for CI gating, and a check that rewrites do not add words.
7. Optional obvious-comment check (comment words repeating the next line's
   identifiers; Steidl, Hummel and Juergens 2013) and complexity-ordered
   triage.

## References

- Abdelsalam, Peitek, Bergum and Apel 2026. The effect of comments on program
  comprehension: an eye-tracking study. Empirical Software Engineering 31.
- Alves, Ypma and Visser 2010. Deriving metric thresholds from benchmark data.
  ICSM.
- Biber and Gray 2010. Challenging stereotypes about academic writing.
  Journal of English for Academic Purposes 9(1).
- Cekini et al. 2026. The cognitive cost of LLM writing. arXiv 2610.23715.
- Chen, Xia, Hu, Lo and Li. Why my code summarization model does not work.
  TOSEM, doi 10.1145/3434280.
- Chin and Holmes 2026. Put the "code" back in "code comprehension study".
  ICPC.
- Clark, Martin and Mahowald 2026. Why is AI-generated language so hard to
  understand? arXiv 2610.29162.
- Li and Ahmed 2023. Commit message matters. ICSE.
- Louis, Dash, Barr and Sutton 2018. Deep learning to detect redundant method
  comments. arXiv 1806.04616.
- Nielebock et al. 2019. Commenting source code: is it worth it for small
  programming tasks? Empirical Software Engineering 24.
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
- Steidl, Hummel and Juergens 2013. Quality analysis of source code comments.
  ICPC.
- Tian et al. 2022. What makes a good commit message? ICSE.
- Trockman et al. 2018. "Automatically assessing code understandability"
  reanalyzed. MSR.
- Uddin and Robillard 2015. How API documentation fails. IEEE Software 32(4).
- Wen, Nagy, Bavota and Lanza 2019. A large-scale empirical study on
  code-comment inconsistencies. ICPC.
