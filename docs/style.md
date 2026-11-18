# Style profiles, repetition and document measures

None of these change a finding or the verdict.

## Comparing with a style you know

`readcost style` compares a document set with a reference: words per
sentence, predicted reading time, and each rule's rate per 1,000 words. It
marks a rule at least twice as frequent as in the reference (with three or
more findings). Built-in references, measured on readcost's evaluation corpus
(numbers only): `rust-book`, `go-docs`, `python-docs`, `django-docs`,
`sqlite-docs`, `stripe-docs`, `govuk`, `readmes` and `essays`. `readcost
style --list` describes them, and `--against` also takes a profile file from
`readcost profile build`. For an earlier version of the README against the Go
docs:

```text
$ readcost style README.md --against go-docs
1 file(s), 2,301 words, against go-docs: 19 texts from Effective Go and the Go blog, fetched for readcost's evaluation corpus

                                         yours       go-docs  ratio
words per sentence                       17.70         17.50  1.0x
predicted ms per word                   213.54        200.70  1.1x
hyphen-compound per 1k words              0.87          0.05  17.7x
inanimate-subject per 1k words            0.00          0.30  0.0x
inline-list per 1k words                  2.17          0.82  2.7x  much higher
long-dependency per 1k words              0.43          0.35  1.3x
reduced-object-relative per 1k words      0.00          0.35  0.0x
stacked-nouns per 1k words                0.43          1.53  0.3x
```

A rate far above the reference is a prompt to look at those sentences, not a
verdict. These rates differ by kind of text, as the built-in profiles show,
so compare with a reference of the same kind of text.

## Repetition across texts

`readcost corpus` looks across many texts at once (commit messages, PR
descriptions, a model's answers) for syntactic templates and repeated
sentence openers. It uses Shaib et al.'s (2024) measures: CR-POS, the share of
texts with one of the 100 most frequent part-of-speech 6-grams, and those
6-grams per token. Point it at files or directories (one text each), or at
one file of many texts separated by `---` lines with `--split`. Formulaic
text, such as the subject lines of merge commits, scores high for a good
reason. The measures also depend on how much text there is: on essays, CR-POS
rises from 4.0 to 4.6 between 5 and 40 texts while templates per token falls.
Compare corpora of similar size and kind. See
[evaluation](evaluation.md#repetition-across-texts).

## Document measures

The JSON output has a `metrics` object per file.

| Key | What it measures | Essays, median | Docs, median |
| --- | --- | --- | --- |
| `mtld` | Lexical diversity of content words (MTLD; McCarthy and Jarvis 2010); none under 50 content words | 149 | 54 |
| `idea_density` | Propositions per word, counted from the parse (DEPID; Sirts et al. 2017) | 0.43 | 0.41 |
| `center_embedding_mean`, `center_embedding_max` | How deeply clauses nest inside clauses that continue after them (Gibson 2000) | 0.07, 1 | 0.04, 1 |
| `sentence_words_profile` | Share of words in sentences of up to 27, 28 to 31, 32 to 38, and more than 38 words (Alves et al. 2010) | 73%, 8%, 10%, 7% | 74%, 9%, 8%, 5% |

Medians are over the evaluation corpus (118 essays and 83 documentation
pages). Documentation repeats its terms, so its lexical diversity is far
lower; higher is not better in technical prose. The sentence-length bands
split the corpus's words at 70%, 80% and 90%, counting each document equally.
