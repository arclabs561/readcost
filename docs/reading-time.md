# Predicted reading time

Each whole-document check also reports a predicted reading time, for example
`predicted reading time 211 s (222 ms per word)`, and the JSON output has
`reading_seconds` and `reading_ms_per_word`. A small tree model predicts how
long readers look at each word from its length, its frequency and its
neighbours. It was fitted to eye-tracking data from 360 native English readers
of newspaper paragraphs (OneStop) and takes about 15 ms for 1,000 words.

On held-out paragraphs its error is about 19 ms per word against a mean of
about 200 (OneStop), and 10 ms on a separate corpus (Provo). Always predicting
the average would score 22 and 17, so treat it as a document-level estimate,
useful for comparing two versions of the same text, not as a judgement of one
sentence. When ten models from different labs each rewrote the same 53
paragraphs, every one raised the predicted time per word (by 2 to 19 ms);
readcost's findings did not tell the rewrites apart. The number does not
affect the verdict. Code spans are left out. See
[evaluation](evaluation.md#reading-time-model) for how it was built and
tested.

## Comparing two versions

To judge a rewrite, compare it with the original. `readcost compare` reports
both the time per word and the total: a rewrite can read slower per word yet
faster in total, or the reverse when it is much longer. Cekini et al. 2026
found model rewrites took 1.6% longer per word but 1.2% less in total, being
shorter. For the sentence in the README's example and the rewrite it adopted
(`tests/test_compare.py` checks that this output is current):

```text
$ readcost compare cmp-old.md cmp-new.md
                              old        new  change
words                          26         48  +22
sentences                       1          2  +1
predicted reading time      7.2 s     10.5 s  +3.2 s (+45%)
ms per word                   301        218  -83
findings                        2          0  -2
weighted findings               2          0  -2
verdict                    advise       pass

by rule: hyphen-compound 1 -> 0, stacked-nouns 1 -> 0
```

`--fail-on slower` exits 1 when the rewrite is predicted to take longer in
total, and `--fail-on worse` also when it has more weighted findings, which
suits a check on model rewrites. `-o json` gives both results in full. The
old text can come from git: `readcost compare HEAD:README.md README.md`.

## Hotspots

`readcost check --hotspots 3` also lists each file's three sentences predicted
to cost the most reading time beyond their length, with their slowest words.
This is experimental: the model was tested on whole texts, not single
sentences.
