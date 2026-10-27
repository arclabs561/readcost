# Evaluation on well-regarded writing

This report runs readcost over about 817,000 words of technical writing that
people widely cite as clear, then reads a sample of its findings to see where
the rules fail. Text that is already good should get few findings, so nearly
every finding here is a candidate false positive. The report measures how the
rules fail on such text. It does not measure how often they are right on model
output, which is what the paper studied.

Every table can be regenerated from the fetched corpus with
`python3 -I scripts/eval_report.py ref/eval ref/eval/results-RUN`, which
also prints example diagnostics per rule; rater labels are in
`eval/labels/`, keyed by a hash of each finding, with no source text.
`--check` makes the respected-authors table a local regression gate.

Measured 2026-10-26. Distributions are for readcost `20199a9` (main after
PR 7). The hand-labeled sample was drawn from `a4c609a` (main before PRs 5 to
7); each sampled finding is also marked as still reported or not on
`20199a9`.

## Method

1. `scripts/fetch_eval_corpus.py` downloads the corpus to a local directory
   and writes `manifest.json`: URL, author, license, fetch time, SHA-256 and,
   for GitHub files, the commit SHA. Web pages are reduced to Markdown with
   trafilatura. Hacker News and Stack Overflow items are pinned by ID. The
   text stays local and is never committed.
2. `scripts/eval_corpus.py` runs readcost with its default settings over every
   manifest entry, offline. Source files use `comments = "all"`. It writes
   per-text results, every finding, and per-category and per-source tables
   (median, 90th percentile and maximum of the cost index over texts of 150
   words or more, verdict
   shares, findings per 1,000 words for each feature). With `--sample N` it
   draws findings from the essay and docs categories, spread evenly over
   features and then over sources. The seed fixes the draw.
3. One rater labeled 210 sampled findings (seed 1), reading each in its
   sentence and, where needed, in the source:
   - correct: a real reading cost that an editor would fix;
   - defensible: arguable either way;
   - wrong: a misparse, idiom, term of art, quotation, code-like text or
     intentional style.

   A second label records whether the construction that the rule names is
   really there, apart from whether it costs the reader.
4. Each proposed rule change was coded as a filter over the findings: the
   sentence is reparsed with the same spaCy model and the finding is dropped
   if the filter matches. The counts below are findings that the filter would
   drop in the essay and docs categories on `20199a9`, and how the dropped
   findings in the labeled sample split by label.

The rater is Claude, an automated model. These labels are one rater's
judgment, not ground truth; no second rater has checked them. The labels and
the filter script are kept with the corpus, outside the repository.

To reproduce:

```sh
python3 scripts/fetch_reference_corpora.py ref   # READMEs and Go commit messages (needs gh)
uv run scripts/fetch_eval_corpus.py ref/eval
python3 scripts/eval_corpus.py ref/eval --sample 210 --seed 1
```

## Corpus

| Category | Sources | Texts | Words |
| --- | --- | --- | --- |
| essay | Paul Graham, Julia Evans, Dan Luu, Simon Willison, Russ Cox, Raymond Chen, Hillel Wayne, Joel Spolsky, Martin Fowler, Andrew Gallant, Dan Abramov, Brendan Gregg, Eli Bendersky | 118 | 391,411 |
| docs | Go blog, Effective Go, Rust book, Python tutorial, Django docs, SQLite docs, GOV.UK publishing guidance, Stripe docs | 83 | 179,649 |
| discussion | Hacker News top comments on 60 best stories; 100 highest-voted Stack Overflow answers | 218 | 40,011 |
| code | CPython 3.15 standard library (24 modules), Rust `core` and `std` (6 files) | 30 | 104,679 |
| readme | 42 READMEs of popular projects (earlier fetch) | 42 | 37,165 |
| commit | 1,000 Go commit messages (earlier fetch) | 1,000 | 64,125 |

Words are the words readcost analyzed, after code, tables and headings are
removed. Each essayist contributes 3 to 14 posts. Recent posts were taken from
each author's feed; older ones are well-known essays. Licenses range from
public domain (SQLite) and open licenses (Go blog CC BY 4.0, Rust book MIT or
Apache-2.0, Stack Overflow CC BY-SA 4.0, GOV.UK OGL v3) to all rights reserved
for most essays. That is why the text stays local. This document quotes
single sentences with attribution.

Not fetched: the GOV.UK page of writing guidelines, from which the extractor
got under 100 words. Paul Graham's pages need trafilatura's default mode rather than its
precision mode, which drops their table layout.

## Distributions

Cost index is weighted findings per 1,000 words. Feature columns are findings
per 1,000 words: stack (stacked-nouns), dep (long-dependency), inan
(inanimate-subject), denom (denominal-verb), rel (reduced-object-relative),
hyph (hyphen-compound), list (inline-list).

| Category | CI p50 | CI p90 | CI max | advise | block | stack | dep | inan | denom | rel | hyph | list |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| essay | 7.0 | 11.9 | 17.4 | 5% | 0% | 2.23 | 0.72 | 1.11 | 1.08 | 4.20 | 0.04 | 2.11 |
| docs | 6.2 | 10.4 | 20.8 | 7% | 0% | 3.27 | 0.56 | 0.67 | 0.68 | 2.34 | 0.02 | 1.70 |
| discussion | 5.0 | 13.3 | 20.0 | 9% | 0% | 2.17 | 0.62 | 0.57 | 0.77 | 3.67 | 0.02 | 1.97 |
| code | 6.4 | 8.6 | 13.8 | 7% | 0% | 1.65 | 1.71 | 0.88 | 0.63 | 1.09 | 0.01 | 1.56 |
| readme | 8.6 | 15.7 | 27.6 | 19% | 0% | 6.22 | 0.57 | 0.38 | 0.65 | 1.10 | 0.19 | 3.69 |
| commit | 11.4 | 28.2 | 110.7 | 21% | 4% | 9.19 | 1.82 | 1.48 | 0.56 | 1.15 | 0.12 | 5.55 |

Selected sources (cost index over texts of 150+ words):

| Source | Texts | Words | CI p50 | CI p90 | advise |
| --- | --- | --- | --- | --- | --- |
| essay/andrew-gallant | 8 | 76,579 | 5.3 | 6.4 | 0% |
| essay/paul-graham | 14 | 56,854 | 6.5 | 8.9 | 0% |
| essay/dan-luu | 9 | 100,550 | 8.6 | 10.1 | 11% |
| essay/brendan-gregg | 7 | 11,657 | 12.2 | 14.5 | 14% |
| docs/rust-book | 16 | 34,886 | 5.9 | 6.9 | 0% |
| docs/python-tutorial | 11 | 21,968 | 4.6 | 9.4 | 0% |
| docs/sqlite-docs | 10 | 35,144 | 7.8 | 14.4 | 30% |
| docs/stripe-docs | 10 | 15,361 | 8.2 | 16.2 | 10% |
| code/rust-std | 6 | 61,479 | 4.3 | 5.7 | 0% |

What stands out:

- The advise threshold of 15 sits above the 90th percentile of essays (11.9)
  and docs (10.4). This matches the README's claim that writing as clear as
  the BurntSushi READMEs passes. 95% of essays and 93% of docs pass.
- Reduced object relatives are the most frequent finding in essays (4.2 per
  1,000 words; Paul Graham 8.0 on `a4c609a`). Stacked nouns lead in commits
  (9.2), READMEs (6.2), and the SQLite and Stripe docs (about 6).
- Commit messages are the only category with block verdicts (4%). Stacked
  nouns drive them: 42 of the 44 blocked messages have 40 or more words,
  and both the subject ("net/http: rewrite the transport connection pool")
  and the dense body add stacks.
- Some essays and docs get "advise" with a cost index well under 15, because
  one finding of severity error is enough. All 9 such texts on `20199a9` were
  tipped by a five-noun stack, and several of those stacks are misparses that
  run across a verb or a dash ("Go language specification defines slices").
- PRs 5 to 7 cut findings on this corpus from 10,485 to 9,087 (13%), mostly
  long-dependency (down 38%) and reduced-object-relative (down 27%).

## Precision of the sample

Precision is the share of sampled findings labeled correct; "c+d" adds
defensible ones. "Present" is the share where the named construction is
really there in the finding. "Kept" counts the sampled findings that
`20199a9` still reports, with their labels.

| Feature | n | correct | defensible | wrong | precision | c+d | present | kept on 20199a9 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stacked-nouns | 31 | 1 | 6 | 24 | 3% | 23% | 65% | 26 (1 c, 5 d, 20 w) |
| long-dependency | 32 | 0 | 9 | 23 | 0% | 28% | 28% | 14 (0 c, 5 d, 9 w) |
| inanimate-subject | 32 | 1 | 6 | 25 | 3% | 22% | 31% | 27 (1 c, 4 d, 22 w) |
| denominal-verb | 32 | 0 | 1 | 31 | 0% | 3% | 3% | 29 (0 c, 1 d, 28 w) |
| reduced-object-relative | 32 | 0 | 1 | 31 | 0% | 3% | 56% | 20 (0 c, 1 d, 19 w) |
| hyphen-compound | 19 | 1 | 3 | 15 | 5% | 21% | 21% | 17 (1 c, 2 d, 14 w) |
| inline-list | 32 | 0 | 4 | 28 | 0% | 12% | 41% | 23 (0 c, 3 d, 20 w) |
| all | 210 | 3 | 30 | 177 | 1% | 16% | 36% | 156 (3 c, 21 d, 132 w) |

Hyphen-compound fired only 19 times in the essay and docs categories, so its
row is the whole population, not a sample. On `20199a9`, 3 of the 156 kept
findings are correct (2%) and 24 are correct or defensible (15%).

Read the precision column against the selection: these writers are chosen
for clarity, so a low rate is expected. The "present" column says more. Where
it is high (stacked-nouns, reduced-object-relative) the parser finds the
construction and the rule's claim about cost is what fails. Where it is low
(denominal-verb, long-dependency, inanimate-subject) the rule fires on
something other than what it names.

The three correct findings:

<!-- readcost: off -->
- "the database file format version numbers" ([SQLite](https://sqlite.org/wal.html))
- "User research by GDS noticed users use and understand the word 'page'" ([GOV.UK](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/style-guides/a-to-z-style-guide/))
- "a subsecond-offset heatmap of profile samples" ([Brendan Gregg](https://www.brendangregg.com/blog/2025-05-01/doom-gpu-flame-graphs.html))
<!-- readcost: on -->

## Where the rules break down

Causes of the 207 wrong or defensible findings, grouped. Counts are from the
sample.

### Reduced object relative: idiomatic pronoun subjects (17), wh-relatives (8), temporal heads (2)

Most hits are short relatives with a pronoun subject. Gordon, Hendrick and
Johnson (2001) found that the reading cost of object relatives depends on the
mix of types of noun phrase: a description head with a pronoun subject costs
far less than two descriptions. Editors do not add "that" to these.

<!-- readcost: off -->
- "If the code is written by someone I trust, ..." ([Andrew Gallant](https://burntsushi.net/foss/))
- "a standard ... is all you need" ([Django docs](https://github.com/django/django/blob/5c13b5a19864807cae7266339554c14e151e5961/docs/topics/db/models.txt))
<!-- readcost: on -->

Most of the rest have "where" or "whose", which `a4c609a` did not
recognize. PR 7 fixed 7 of these 8. Two more are temporal nouns that head an
adverbial ("each time it is evaluated", [Effective Go](https://github.com/golang/website/blob/52d470bcf26e41fd5a38199c5463268fb61b67ae/_content/doc/effective_go.html)).
A reduced passive also reads as an object relative: on `a4c609a`, readcost
flags "the commit SHA resolved at fetch time" in this repository's own
`scripts/fetch_eval_corpus.py`.

### Denominal verb: settled verbs (15), phrasal verbs (10), idioms, misparses and participles (6)

The WordNet test marks a verb as denominal when its noun senses outnumber its
verb senses. That catches "figure" (87 of 543 hits in essays and docs),
"reference", "scale", "exit" and "host", which every reader knows as verbs.
Phrasal verbs are worse: the particle that marks "figure out" as a verb is
taken as evidence of a verb use.

<!-- readcost: off -->
- "information than you can figure out from the screen" ([Joel Spolsky](https://www.joelonsoftware.com/2000/10/02/painless-functional-specifications-part-1-why-bother/))
- "doing something that really doesn't scale" ([Paul Graham](https://paulgraham.com/ds.html))
- "Use numbered steps instead of bullet points" ([GOV.UK](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/style-guides/a-to-z-style-guide/))
<!-- readcost: on -->

The only real denominal verb in the sample is intentional wit: "you can't
credential your way into it" ([Martin Fowler](https://martinfowler.com/articles/practitioner-voice.html)).
In READMEs the same rule fires on plural nouns in fragments, as in
"Threading and synchronization primitives". It also fires on "alias", "fork",
"bundle" and "version".

### Inline list: three-item and comma-count overcounts (17), short items (7), quoted or code items (4)

The comma fallback counts every comma in a long sentence that ends in "and"
or "or". Lists of one-word items read fine in prose, and so do rhetorical
triads.

<!-- readcost: off -->
- "Microsoft, Apple, Yahoo, Google, and Facebook all began this way." ([Paul Graham](https://paulgraham.com/startupideas.html))
- "guidelines for naming packages, types, functions, and variables" ([Go blog](https://github.com/golang/website/blob/52d470bcf26e41fd5a38199c5463268fb61b67ae/_content/blog/package-names.md))
- "The gods Hadad and El and Rašap and Rākib-El and Šamaš supported me." (a quoted inscription, [Hillel Wayne](https://www.hillelwayne.com/post/tale-of-daniel/))
<!-- readcost: on -->

### Inanimate subject: verbs that take things as subjects (10), copular "feel" (5), terms of art (3)

The animate-verb list from WordNet includes verbs that ordinary English uses
with inanimate subjects: suffer from, rely on, respond, link, perturb,
overwhelm. "Feel" as a linking verb ("it feels like") has no agent at all.
"Panic" and "die" are terms of art for programs.

<!-- readcost: off -->
- "If a line feels too long, wrap it" ([Effective Go](https://github.com/golang/website/blob/52d470bcf26e41fd5a38199c5463268fb61b67ae/_content/doc/effective_go.html))
- "Systems under load can respond with exponential latency" ([Brendan Gregg](https://www.brendangregg.com/blog/2025-08-04/when-to-hire-a-computer-performance-engineering-team-2025-part1.html))
- "will cause the program to panic" ([Rust book](https://github.com/rust-lang/book/blob/1500248d8f230566e4ec9f27fcbb8fe9e2898ab1/src/ch08-01-vectors.md))
<!-- readcost: on -->

Defensible ones are conventional personification that technical readers
expect: "the database layer knows nothing about data display" ([Django docs](https://github.com/django/django/blob/5c13b5a19864807cae7266339554c14e151e5961/docs/misc/design-philosophies.txt)).

### Stacked nouns: names and established terms (13), parser errors (9), headlines (2)

A name or acronym in front of a term of two nouns reads as one unit: "Go
programming language", "HTTP status codes", "Monte Carlo methods". Hyphenated
modifiers ("compile-time restriction", "client-side apps") are split into
nouns by the tokenizer, and adjectives and verbs get tagged as nouns ("custom
data type", "bisect hash patterns default to"). The allow list misses
plurals: "error message" is allowed but "validation error messages" is
flagged.

<!-- readcost: off -->
- "Because of the compile-time restriction, ..." ([Effective Go](https://github.com/golang/website/blob/52d470bcf26e41fd5a38199c5463268fb61b67ae/_content/doc/effective_go.html))
- "Instead, bisect hash patterns default to a 'quiet' mode" ([Russ Cox](https://research.swtch.com/bisect))
- "Bonus bonus chatter: ..." (a recurring section label, [Raymond Chen](https://devblogs.microsoft.com/oldnewthing/20261012-00/?p=112767))
<!-- readcost: on -->

### Long dependency: fronted adverbials (10), coordinated clauses (5), misparses and fragments (8)

The longest arc is often from a sentence-initial connective ("However", "In
other words", "For example") to the main verb, or between two coordinated
clauses. Neither has to be held in memory. PR 7, with arcs between words
only and a refitted profile, removed 18 of the 32 sampled findings. The
defensible ones are real interruptions that the writer chose, such as an
aside in dashes between subject and verb.

<!-- readcost: off -->
- "However, for ListView, the automatically generated context variable is ..." ([Django docs](https://github.com/django/django/blob/5c13b5a19864807cae7266339554c14e151e5961/docs/intro/tutorial04.txt))
- "You do tend to get a certain bulk discount if you buy the economy-size pain, but you can't evade the fundamental conservation law." ([Paul Graham](https://paulgraham.com/wealth.html))
- Defensible: "the thing it's made of, accumulated consequence-bearing experience stated plainly, has to be earned" (dashes replaced with commas; [Martin Fowler](https://martinfowler.com/articles/practitioner-voice.html))
<!-- readcost: on -->

### Hyphen compound: established compounds (7), names and defined terms (6), misparses (2)

Some compounds are established but missing from WordNet: "set-top boxes",
"quad-core processor", "message-digest algorithm". A compound in quotes is
being named or defined, as in "the 'bisect-reduce' algorithm" ([Russ
Cox](https://research.swtch.com/bisect)). The first-use rule then misses its
next use, because the key keeps the closing quote. The rule also fires on
names of repositories and tools ("clang-format/clangd") and on the suffix
"-ish".

### Extraction

The essay corpus has extraction artifacts of its own. trafilatura drops
blockquote markers, so quoted material (the C89 standard in a Russ Cox post)
counts as the author's prose. Some sites separate paragraphs with single
newlines, which the fetcher splits with a heuristic.

## Proposed rule changes

Ranked by findings dropped in the essay and docs categories on `20199a9`
(about 571,000 words). "Sample" gives the labels of the dropped sampled
findings that `20199a9` still reports. No filter dropped any of the three
correct findings. Each was coded and run except where marked untested.

1. Reduced object relative: skip the clause when its subject is a pronoun.
   Drops 1,684 of 2,065 (82%). Sample: 15 wrong, 1 defensible, 0 correct.
   Fixes "someone I trust" (Gallant), "the people I call Architecture
   Astronauts" ([Joel Spolsky](https://www.joelonsoftware.com/2001/04/21/dont-let-architecture-astronauts-scare-you/)),
   "the dataset we've used" ([Andrew Gallant](https://burntsushi.net/csv/)).
   It also drops one defensible finding from Fowler, "the thing no one had
   time to notice". Clauses with a full noun phrase as subject, such as "the
   format the reader expects", are still reported.
2. Inline list: require four conjuncts from the parser, drop the fallback
   that counts commas, and skip lists whose items average under three words.
   Together with item 11, drops 1,035 of 1,131 (92%). Sample: 20 wrong, 3
   defensible. Fixes Graham's list of companies, the Go blog's "packages, types,
   functions, and variables", and Stripe's "fulfilling orders, granting
   account access, or modifying records" ([Stripe](https://docs.stripe.com/webhooks.md)).
   Wrongly lets through Effective Go's seven-item list of key types, which
   would read better as a bulleted list.
3. Stacked nouns: do not count a leading name or acronym. Drops 362
   of 1,461 (25%). Sample: 5 wrong. Fixes "Go programming language" ([Go
   blog](https://github.com/golang/website/blob/52d470bcf26e41fd5a38199c5463268fb61b67ae/_content/blog/errors-are-values.md)),
   "Bluesky client app" ([Dan Abramov](https://overreacted.io/open-social/)),
   "HTTP status codes" (Django docs). Wrongly lets through "SEO spam clone"
   ([Dan Luu](https://danluu.com/diseconomies-scale/)), which is a real stack.
4. Reduced object relative: skip clauses on light or temporal heads (time,
   way, reason, all). Drops 364 (18%), mostly the same findings as item 1. Fixes
   "the first time you write code like that" ([Russ Cox](https://research.swtch.com/nih)),
   "the way you'd ask the question" ([Dan Luu](https://danluu.com/ai-coding/)), "is all you need" (Django
   docs, Rust book).
5. Denominal verb: treat a verb as settled when it is tagged as a verb in
   three or more texts of a held-out corpus, and skip verbs with a
   particle. The coded version used the readme, commit, code and
   discussion categories as the held-out corpus. Drops 304 of 543 (56%).
   Sample: 18 wrong. Among them are "figure out" (Spolsky, Fowler, Rust
   book), "doesn't scale" (Graham) and "goroutines to exit" ([Go
   blog](https://github.com/golang/website/blob/52d470bcf26e41fd5a38199c5463268fb61b67ae/_content/blog/context.md)).
   Keeps "credential your way into it". A held-out list built from a larger
   corpus would do better than this small one.
6. Long dependency: leave out arcs from fronted adverbials and
   connectives, and arcs between coordinated clauses, before computing z.
   Drops 252 of 384 (66%). Sample: 6 wrong, 4 defensible. It drops the
   Django "However" sentence above, Gallant's "In other words, ..." ([Andrew
   Gallant](https://burntsushi.net/regex-internals/)) and Graham's two
   coordinated clauses. The profile must be refitted with the same arcs.
   Risk: on `a4c609a` the coordination filter also dropped a 49-word SQLite
   sentence whose subject waits behind two parentheticals ([SQLite](https://sqlite.org/wal.html)).
7. Inanimate subject: remove verbs that take inanimate subjects in
   ordinary English (rely, respond, suffer, link, catch, resolve, remind,
   surprise, overwhelm, perturb, react, behave) and terms of art (panic,
   die, crash). Drops 114 (21%). Sample: 11 wrong. It drops Gregg's
   "respond", the Rust book's "panic" and Gallant's "doesn't suffer from that
   weakness".
8. Inanimate subject: skip linking verbs (feel, seem, look, sound,
   appear). Drops 67 (12%). Sample: 4 wrong. It drops the Effective Go line
   above, "how magical it feels" ([Russ Cox](https://research.swtch.com/bisect))
   and "Wouldn't it feel satisfying?" (Fowler).
9. Stacked nouns: count a hyphenated word as one unit, and leave coined ones
   to hyphen-compound. Drops 130 (9%). Sample: 2 wrong. Fixes
   "compile-time restriction" (Effective Go), "client-side apps" (Abramov),
   "world-class team" (Dan Luu). Coinages such as "caller-side bug" and
   "meat-proxy development" would then be judged by hyphen-compound.
10. Stacked nouns: a stack of severity error must not cross a dash or end in
    a word that can be a verb, and one such finding should not make a long
    text "advise". Untested at the level of findings; it changes the verdict
    of 9 texts. Examples are "Go language specification defines slices" (Go
    blog) and a Django stack that runs across a dash.
11. Inline list: skip lists whose items are code spans or quoted terms.
    Drops 14 on top of item 2. Fixes "four columns 'a', 'b', 'c', and 'd'"
    (SQLite docs) and the Gallant "yes"/"no" quotes ([Andrew
    Gallant](https://burntsushi.net/transducers/)).
12. Hyphen compound: skip compounds in quotes or next to a slash, an
    expansion in parentheses after an acronym, and "-ish"; strip quotes from
    the first-use key. Drops 5 of 18. Fixes "'bisect-reduce' algorithm"
    (Russ Cox), "CSBI (context-situation-behaviour-impact)" (Fowler),
    "clang-format/clangd" (Dan Luu), "standard-ish" (Abramov).
13. Match terms in the allow list by lemma, so that plurals match. Drops 4. Fixes "validation
    error messages" (GOV.UK), "API rate limits" (Stripe), "niche use cases"
    (Abramov).
14. Treat text in quotation marks as opaque, as code spans already are.
    Untested on the corpus. Quoted lists, quoted terms and quoted titles
    account for several wrong findings above; this document gets most of its
    own findings from the sentences it quotes.

One tested idea failed. Treating a hyphen pair as established when it occurs
in two or more other sources of this corpus dropped nothing: the corpus is too
small for "set-top" or "quad-core" to recur. An established-compound list
needs a much larger reference corpus.

Items 1, 2, 5 and 7 change what the README says about those features, and
item 6 needs the reference profile refitted. Each change needs a regression
test built from the sentences quoted here, and from the paper's examples
that the rule should still report.

## After the first fixes

The next change applied proposals 1 to 5 (in part), 7, 8, 9, 11 and 13 as
code rather than filters:

- reduced-object-relative skips pronoun subjects and light heads;
- inline-list counts parser conjuncts or verbless comma chunks only, and
  skips lists that are mostly code (a rule skipping lists of short items
  was reverted after the ten-rater check below);
- stacked-nouns skips a leading name or acronym and counts a hyphenated word
  as one unit;
- inanimate-subject skips linking verbs and verbs that take things as
  subjects;
- denominal-verb skips phrasal verbs and is now opt-in.

Rerunning the whole corpus with the same labels (essay and docs only):

| | Before | After |
| --- | --- | --- |
| Findings in essay and docs | 6,156 | 2,234 |
| Labeled correct still reported | 3 of 3 | 3 of 3 |
| Labeled defensible still reported | 21 of 30 | 18 of 30 |
| Labeled wrong still reported | 132 of 177 | 46 of 177 |
| Correct or defensible, of those reported | 15% | 31% |

"Before" is `20199a9`. The remaining wrong findings are mostly stacked nouns
(13), hyphen compounds (14) and long dependencies (9). Counting a hyphenated
word as one unit moved established terms such as "product-market fit" and
"name-value pairs" from stacked-nouns to hyphen-compound (18 to 74 findings);
telling them from coinages needs word-pair frequencies, which readcost does
not have yet. Proposals 6, 10, 12 and 14 are not applied.

## Word pairs

The next change gave hyphen-compound a list of hyphenated pairs in common
use: those found in five or more of 1,598,350 FineWeb-Edu documents from a
2019 crawl (`scripts/build_word_pairs.py`, 105,277 pairs, 0.4 MB). In that
crawl, 17 coinages taken from model-written READMEs and from this corpus
("storage-shrink", "region-index", "capability-tractability") occur in no
document, while established compounds mostly occur in ten or more
("product-market" 11, "write-ahead" 10, "trade-off" 1,958). On the corpus,
hyphen-compound findings in essays and docs fall from 74 to 50, and no
finding labelled correct or defensible is lost. Most of the remaining 50 are
coinages ("quality-velocity trade-off space") or tool and repository names
("oss-fuzz", "git-rev-list").

## Second rater

A second rater from a different model family, Codex (`gpt-6.1-sol`, run
headless by `scripts/second_rater.py`), labelled the same 210 findings with
the same rubric, without seeing the first labels.

| | Agreement | Cohen's kappa |
| --- | --- | --- |
| correct / defensible / wrong | 81% | 0.41 |
| correct or defensible / wrong | 83% | 0.46 |
| construction present | 81% | 0.61 |

The second rater labelled 5 correct, 41 defensible and 164 wrong (first
rater: 3, 30, 177), so the main result holds: few findings on this text are
real costs. The raters differ on how much the fixes helped. Of the findings
each version still reports:

| | Reported | Rater 1 correct or defensible | Rater 2 correct or defensible | Both raters |
| --- | --- | --- | --- | --- |
| `20199a9` | 156 | 15% | 22% | 16 |
| precision fixes | 67 | 31% | 25% | 13 |
| plus word pairs | 63 | 33% | 25% | 13 |

The second rater called most of the dropped reduced-object-relative and
inline-list findings defensible, with reasons such as "clear object relative;
'that' is optional" and "five names remain easy to scan", which describe no
reading cost. Three findings both raters accepted were dropped: two real
lists of short items and an opt-in denominal verb. Kappa near 0.4 is moderate
agreement; neither rater is ground truth.


## Ten raters

Two raters from two labs are a narrow base, so eight more model families
labelled the same 210 findings blind, through OpenRouter with the same rubric:
Kimi K3.1 Pro, Gemini 4 Argon, DeepSeek V4.1 Flash, Grok 4.7, Mistral Large 4,
GLM 5.3 FlashX, Llama 4 Maverick and MiniMax M3 (Qwen was not reachable).

| Rater | Correct | Defensible | Wrong | Kappa with the majority of the others |
| --- | --- | --- | --- | --- |
| Claude (rater 1) | 3 | 30 | 177 | 0.43 |
| Codex gpt-6.1-sol | 5 | 41 | 164 | 0.54 |
| DeepSeek V4.1 Flash | 4 | 37 | 169 | 0.50 |
| Gemini 4 Argon | 7 | 30 | 173 | 0.44 |
| GLM 5.3 FlashX | 5 | 49 | 156 | 0.52 |
| Grok 4.7 | 3 | 23 | 184 | 0.56 |
| Kimi K3.1 Pro | 3 | 10 | 197 | 0.44 |
| Mistral Large 4 | 5 | 21 | 184 | 0.36 |
| Llama 4 Maverick | 36 | 94 | 80 | 0.13 |
| MiniMax M3 | 19 | 86 | 105 | 0.10 |

Fleiss' kappa over all ten is 0.23; Llama 4 Maverick and MiniMax M3 accept
far more than the rest and agree with them little, and without those two it is
0.40. The eight-rater majority calls 2 findings correct and 24 defensible: the
low base rate holds across model families.

The majority also changes a conclusion. It accepts inline-list findings more
than any other (10 of 32; 1 to 5 of 32 for the other rules), including lists
of short items such as "Microsoft, Apple, Yahoo, Google, and Facebook", which
rater 1 had labelled wrong and the precision fixes had dropped. The
short-items rule is reverted; the rules that skip clauses joined by commas and
lists of code stay. Share of reported sample findings the eight-rater majority
accepts:

| Version | Reported | Majority correct or defensible |
| --- | --- | --- |
| `20199a9`, before the fixes | 156 | 18 (11.5%) |
| precision fixes, word pairs, contexts (`30631c7`) | 63 | 9 (14.3%) |
| short-items rule reverted | 75 | 15 (20.0%) |

The fixes judged by one rater gained 3 points by the majority; reverting the
one rule the majority disagreed with gains 6 more. Both gains are small
against the sampling error (Wilson 95% intervals 7.4 to 17.5%, 7.7 to 25.0%
and 12.5 to 30.4%), and the two lenient raters were set aside after their
labels were seen. The scripts are
`scripts/second_rater.py` and `scripts/rater_ensemble.py`.

## Paired rewrites

Does readcost score model text as costlier than human text with the same
content? Following Cekini et al. 2026, 53 human paragraphs (120 to 260 words,
13 sources, essays and docs) were each rewritten by two models with the
instruction to keep the same facts and audience in their own words: Codex
`gpt-6.1-sol` and Claude `claude-sonnet-5-5`, both run headless with the
user's global instruction files kept out (`scripts/paired_rewrite.py`). The
hypotheses were written down before any rewrite was scored. Paired two-sided
Wilcoxon tests, rewrite minus original (`scripts/paired_score.py`):

| Measure | Model | Original median | Rewrite median | Rewrite higher | p |
| --- | --- | --- | --- | --- | --- |
| words | Codex | 134 | 120 | 8% | <0.001 |
| words | Claude | 134 | 119 | 4% | <0.001 |
| cost index | Codex | 3.6 | 2.9 | 40% | 0.75 |
| cost index | Claude | 3.6 | 3.5 | 36% | 0.99 |
| mean word length | Codex | 4.62 | 5.23 | 100% | <0.001 |
| mean word length | Claude | 4.62 | 4.79 | 64% | <0.001 |
| surprisal, bits per token (SmolLM2-135M) | Codex | 4.56 | 5.22 | 92% | <0.001 |
| surprisal, bits per token (SmolLM2-135M) | Claude | 4.56 | 4.94 | 87% | <0.001 |

- H1 failed. readcost's cost index does not tell the rewrites from the
  originals. (Three pairs are HTML paragraphs that readcost extracts nothing
  from; leaving them out, p = 0.46 and 0.99 on 50 pairs, the same result.) Pooled over all 53 paragraphs the weighted findings per 1,000
  words are 4.4 for the originals and 4.2 (Codex) and 4.4 (Claude) for the
  rewrites.
- H2 was not detected. Nominalizations were found in no paragraph on either
  side. Participial clauses rose from 6 to 13 (Codex) and 8 (Claude) in total,
  the direction Reinhart et al. 2025 report, but at these counts the test is
  not significant (p = 0.08 and 0.31).
- H3 was half confirmed. Rewrites use longer words, as Cekini et al. found,
  and in every pair for Codex. Surprisal went up, the opposite of their
  result with OPT-125M; both were scored with one small model, and such
  comparisons can reverse with the scorer's size (Liu et al. 2025). The rise
  holds in all 13 sources, docs included, so
  memorization of famous essays by the scoring model does not explain it,
  though the largest rise is for Paul Graham's essays (+0.86 bits).
- H4 was not detected: coined hyphen pairs are rare on both sides.

The rewrites shift word choice (longer, less predictable words) rather than
the syntactic constructions readcost counts. The detectors work as a
checklist of constructions to reread; on this evidence they are not a
measure of whether text was written by a model. Limits: one prompt, 53 short
paragraphs from well-edited sources, and one scoring model for surprisal.

## Reading-time model

The paired test above shows that the detectors do not measure what changes
when a model rewrites a text. readcost now also predicts reading time from
eye-tracking data, following the feature model of Cekini et al. 2026: per
word, its length, digits, hyphen, closing punctuation, position, frequency
(from 1.2 billion FineWeb-Edu tokens), stopword status, and the length,
frequency and closing punctuation of the words before and after it. The
target is a word's mean total reading time across readers, counting a skipped
word as 0 ms.

Fitting data is OneStop Eye Movements, ordinary reading: 324 paragraphs and
35,188 word occurrences, split by article 60/20/20 into training, validation
and test. The Provo Corpus (55 passages, 84 readers) is an external test that
was not used for fitting. Error is the mean absolute difference between
predicted and observed mean reading time per word of each text, in ms/word,
as in the paper (`scripts/reading_time_train.py`):

| Model | OneStop validation | OneStop test | Provo |
| --- | --- | --- | --- |
| always the training mean | 27.1 | 22.3 | 16.9 |
| word length only (ridge) | 23.7 | 20.8 | 12.2 |
| all features (ridge) | 23.4 | 19.7 | 11.5 |
| gradient-boosted trees (shipped) | 22.7 | 19.2 | 10.3 |
| trees plus SmolLM2-135M surprisal | 22.7 | 19.2 | 15.8 |

Observed means are 198 to 205 ms/word. Cekini et al. report 15.0 on OneStop
test and 16.1 on Provo for their RoBERTa model and about 19 for feature
models on OneStop test. Word length (0.59) and frequency (0.22) carry most of
the trees' importance.

Surprisal studies usually report word-level fit, which tells a different
story from the text-level error above:

| Model | OneStop test, word r | OneStop test, word RMSE | Provo, word r | Provo, word RMSE | Provo, mean signed error |
| --- | --- | --- | --- | --- | --- |
| trees (shipped) | 0.776 | 77.2 | 0.823 | 62.7 | +4.8 |
| trees plus surprisal | 0.786 | 75.6 | 0.831 | 65.0 | +15.0 |

Surprisal improves word-level correlation everywhere, as Shain et al. 2024,
Pimentel et al. 2023 and Tsipidi et al. 2026 find on Provo. What it costs is
calibration across corpora: Provo's short passages give the language model
little context, so their mean surprisal is 6.89 bits per word against 5.50 on
OneStop, and a model fitted on OneStop predicts every Provo passage about 15
ms per word too slow. Studies that fit their regressions within each corpus
never see that shift. readcost applies one model to texts of every length
and kind, so it ships the lexical model, which also needs neither torch nor a
language model. A surprisal feature normalised per text, or computed with a
fixed amount of context, would be the version to test next.

Correction: an earlier version of this table reported 9.6 ms/word on Provo.
Provo rows were keyed by `Word_Number`, which is missing for each passage's
first word and runs one ahead of the interest area in places, so some words
were paired with a neighbour's reading time. Keyed by interest area, Provo
has 2,743 words with a mean of 200.2 ms (Cekini et al. report 2,743 and
200.16), and the shipped model's error is 10.3. The model itself and the
paired results below are unchanged; Provo is used only for testing.

Applied to the paired rewrites (the `reading_ms_per_word`, `reading_seconds`
and `cost_index` rows of `scripts/paired_score.py`), with eight more
rewriters from the OpenRouter ensemble (`scripts/rater_ensemble.py rewrite`,
same prompt). Medians, rewrite minus original; all 53 pairs are scored now
that HTML paragraphs are extracted, and MiniMax M3 returned 37 rewrites:

| Rewriter | Pairs | ms/word | Higher | p | Total s | Higher | p | Cost index p |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Codex `gpt-6.1-sol` | 53 | +19.2 | 98% | <0.001 | -1.1 | 32% | 0.003 | 0.78 |
| Gemini 4 Argon | 53 | +17.0 | 94% | <0.001 | +1.3 | 64% | 0.004 | 0.45 |
| Mistral Large 4 | 53 | +17.0 | 94% | <0.001 | +0.4 | 58% | 0.61 | 0.12 |
| Llama 4 Maverick | 53 | +16.7 | 92% | <0.001 | -8.7 | 0% | <0.001 | 0.98 |
| MiniMax M3 | 37 | +8.6 | 84% | <0.001 | -0.2 | 49% | 0.91 | 0.61 |
| Kimi K3.1 Pro | 53 | +6.8 | 89% | <0.001 | -0.5 | 36% | 0.008 | 0.32 |
| DeepSeek V4.1 Flash | 53 | +5.3 | 72% | <0.001 | -0.7 | 28% | <0.001 | 0.57 |
| Claude `claude-sonnet-5-5` | 53 | +4.4 | 75% | <0.001 | -2.2 | 4% | <0.001 | 0.60 |
| GLM 5.3 FlashX | 53 | +2.7 | 68% | 0.002 | -0.1 | 47% | 0.34 | 0.90 |
| Grok 4.7 | 53 | +2.4 | 75% | <0.001 | -1.2 | 21% | <0.001 | 0.05 |

Every rewriter raises predicted reading time per word, from +2 ms (Grok,
GLM) to +19 ms (Codex), against originals near 194 ms; every one also uses
longer words. The total depends on how much a model shortens: six lower it,
Gemini raises it and three show no clear change, so Cekini et al.'s "less in
total" does not generalize while "more per word" does. readcost's cost index
separates none of the ten (Grok's p = 0.05 is in the direction of fewer
findings in the rewrite). The model is trained on newspaper paragraphs read
by native speakers; technical prose, code-heavy text and non-native readers
are outside its data.

Paragraph layout also lies partly outside it. Training paragraphs have 50 to
165 words. Past 165 words the trees kept lowering the time per word with
position, so 30 essays set as one paragraph each were predicted to read 17%
faster (median) than the same essays in their paragraphs. A longer paragraph's
positions are now scaled into 165 words, which leaves the held-out error
unchanged (OneStop 19.2 ms, Provo 10.3 ms, since no test paragraph is longer)
and brings the gap to 4%. Splitting every sentence into its own paragraph
still predicts 9% slower. Those paragraphs fall inside the training range,
and paragraph starts may really cost readers time. Read short paragraphs as
the start of a 50-word one instead and that figure barely moves, while
Provo's error rises to 10.4 ms, so short paragraphs keep their positions.

## Contexts

The verdict thresholds (advise at 15, block at 30) were set on ten READMEs.
Adapting Alves et al. 2010, who set code-metric thresholds at the 70th, 80th
and 90th percentiles of a benchmark weighted by code volume, a threshold
should sit at a high percentile of good writing of the same kind. Cost index per text on the corpus (texts of
40+ words, after the fixes above):

| Context | Texts | p90 | p95 | p99 |
| --- | --- | --- | --- | --- |
| essays | 118 | 5.4 | 7.0 | 8.4 |
| docs | 81 | 6.2 | 7.8 | 11.4 |
| READMEs | 41 | 13.0 | 14.0 | 16.1 |
| discussion (HN, Stack Overflow) | 174 | 8.3 | 11.7 | 14.5 |
| code comments (CPython, Rust std) | 30 | 6.7 | 8.7 | 9.9 |
| Go commit messages | 549 | 23.9 | 32.5 | 48.9 |

The prose thresholds already sit near the 99th percentile of every prose
context, so they stay. Commit messages are terser and get their own:
advise at 50 and block at 100, keeping the prose ratio of two. Thirty code
files are too few to justify a separate threshold for comments.

Most commit-message noise came from extraction, not prose: benchstat tables,
shell commands and the `pkg/path:` scope prefix were read as sentences, and
package paths such as `cmd/compile/internal/ssa` as slash lists. The commit
extractor now drops lines that are not sentences and strips the scope, and
a slash group of three or more lowercase identifiers counts as a path (so
"read/write/execute" is no longer flagged either). On the 1,000 Go commit
messages, the share not passing fell from 16.4% to 12.9% with the extraction
fixes and to 1.6% with the commit thresholds; of the 16 left, 6 are short
messages, 6 exceed the rate and 4 hold an error-level noun stack.

## Example diagnostics

Real output on the corpus at `8ccf0ac`, with how many of the eight raters
call each finding correct or defensible (`scripts/eval_report.py`):

```text
brendan-gregg:11: info: [inline-list] 5 items listed in one sentence
  > The main ROIs are infrastructure cost savings, latency reductions, improved scalability and reliability, and faster engineering.
  raters: 7 of 8 call it correct or defensible
```

```text
joel-spolsky:34: info: [inanimate-subject] 'code ... smells': a person's verb with a non-person subject
  > That code smells a little bit dirty.
  raters: 0 of 8 call it correct or defensible
```

```text
dan-luu:36: warn: [long-dependency] 'have' and 'course' are 21 words apart (z = 3.2)
  > Of course, since the issue is not the number of clicks it takes and there's some underlying emotional motivation, other people have different reasons.
  raters: 2 of 8 call it correct or defensible
```

The first is the kind of finding the rules are for. The second is a fixed
idiom. The third measures an arc from the fronted "Of course" (proposal 6,
not applied) rather than any subject held apart from its verb.

All ten raters score the current rules higher than those before the fixes:
the share of reported sample findings each calls correct or defensible rose
for every rater (Claude 15% to 31%, Codex 22% to 31%, DeepSeek 22% to 32%,
Gemini 20% to 28%, Mistral 14% to 23%, Kimi 8% to 13%, Grok 14% to 25%, GLM
30% to 41%, and the two lenient raters 63% to 71% and 53% to 71%).

## Text difficulty benchmarks

Two public datasets test whether readcost tracks how hard a text is, as
opposed to whether its findings are real reading costs.

OneStopEnglish (Vajjala and Lucic 2018) has 189 news articles, each written
at elementary, intermediate and advanced level. Paired across the three
versions (`scripts/eval_onestop_levels.py`, readcost `ca847be`):

| Measure | Elementary | Intermediate | Advanced | Advanced higher | p |
| --- | --- | --- | --- | --- | --- |
| words per sentence | 16.6 | 19.6 | 22.0 | 99% | <0.001 |
| mean word length | 4.47 | 4.67 | 4.68 | 96% | <0.001 |
| predicted ms per word | 170 | 173 | 173 | 74% | <0.001 |
| readcost cost index | 2.99 | 3.49 | 3.66 | 61% | <0.001 |

The CLEAR corpus (Crossley et al. 2022) has 4,724 school reading excerpts
with an ease score fitted from teachers' pairwise judgments. Spearman
correlation with that ease (`scripts/eval_commonlit.py`; a cost should be
negative):

| Measure | rho |
| --- | --- |
| readcost cost index, default rules | -0.06 |
| readcost cost index, with long-sentence, nominalization and participial-clause | -0.25 |
| readcost predicted ms per word | -0.37 |
| words per sentence | -0.41 |
| mean word length | -0.43 |
| Flesch-Kincaid grade | -0.55 |
| Dale-Chall | -0.60 |

readcost's default cost index barely tracks judged difficulty: the
constructions it counts are not what makes school texts easy or hard, and
sentence length, which separates the OneStopEnglish levels best, is behind an
opt-in rule. Formulas built from word familiarity and sentence length track
teachers' judgments far better. That is not the same as tracking
comprehension: Guo et al. 2025 found formulas rated GPT-4 summaries easier
while readers understood the human ones better. readcost reports what to
reread and a reading-time estimate; it should not be read as a difficulty
grade.

## Speed

`scripts/bench_speed.py` on an Apple M3 Max: a new `readcost check` process
on a short file takes about 1.1 to 1.4 s (most of it loading spaCy and the
word-frequency table), which is what a hook pays per edit. A loaded Analyzer
checks 8,100 words per second (median of 5), against 3,400 for the code
before the reading-time model walked all its trees at once, measured at the
same time; an earlier, quieter run of the old code gave 5,100.

On many files, `readcost check` runs a process per core. The combined
evaluation corpus (10,953 texts, 5.66 million words) takes 157 s with 8
processes, about 36,000 words per second, and 231 s with every opt-in rule
on as well.

## Reference profile

long-dependency scores a sentence against a reference profile: the usual
distance between related words at each sentence length. The first default
profile came from twelve READMEs by one writer. It is now built by
`scripts/build_default_profile.py` from every other text of each essay, docs
and README source in this corpus (126 texts, 22 sources, 341k words); the other
half is held out. The two fits are close ((0.429, 0.629, 0.405) before,
(0.446, 0.633, 0.409) after), so the change is mostly in how much evidence
stands behind the profile. `scripts/compare_profile.py` compares the runs
before and after:

| Texts | Run | Texts (40+ words) | Pass | Cost index p50 / p95 | long-dependency per 1k words |
| --- | --- | --- | --- | --- | --- |
| code | before | 30 | 97% | 4.1 / 9.7 | 1.80 |
| code | after | 30 | 97% | 4.0 / 9.7 | 1.64 |
| commit | before | 549 | 98% | 5.0 / 32.4 | 1.69 |
| commit | after | 549 | 98% | 4.3 / 32.4 | 1.55 |
| discussion | before | 174 | 98% | 0.0 / 12.8 | 0.64 |
| discussion | after | 174 | 98% | 0.0 / 12.8 | 0.51 |
| held-out docs | before | 38 | 97% | 2.7 / 6.2 | 0.54 |
| held-out docs | after | 38 | 97% | 2.7 / 6.2 | 0.51 |
| held-out essay | before | 56 | 98% | 3.3 / 7.2 | 0.69 |
| held-out essay | after | 56 | 98% | 3.3 / 7.2 | 0.65 |
| held-out readme | before | 20 | 90% | 5.7 / 19.2 | 0.68 |
| held-out readme | after | 20 | 90% | 5.7 / 19.2 | 0.62 |

Verdicts do not move; long-dependency findings drop by 5 to 20% per category.
Of the 210 labelled findings, 74 are still reported instead of 75; the one
dropped was judged wrong by the majority, so the eight-rater majority's share
correct or defensible goes from 20.0% to 20.3%.

## Pull requests and review comments

`scripts/fetch_github_prose.py` takes 20 merged pull request descriptions (40 or
more words) and 20 review comments by people (25 or more words) from each of
python/cpython, rust-lang/rust, django/django, kubernetes/kubernetes,
astral-sh/ruff and facebook/react: 240 texts, kept outside the repository.
`scripts/eval_corpus.py` runs on them unchanged.

| Category | Texts | Median words | Pass | Advise | Block | Cost index p50 / p90 |
| --- | --- | --- | --- | --- | --- | --- |
| PR descriptions | 120 | 108 | 104 | 16 | 0 | 3.1 / 12.2 |
| Review comments | 120 | 39 | 114 | 5 | 1 | 7.1 / 10.6 |

The first run found one false-positive source that the other categories never
show: cross-repository references such as `rust-lang/rust#161362` were read as
the coined compound "rust-lang", which put 3% of descriptions at "block". Issue
references now count as single words, like URLs, and hyphen-compound findings
in descriptions fell from 2.11 to 0.72 per 1,000 words. What remains is mostly
stacked nouns in terse rollup titles ("overflow safety docs"). Most review
comments are under 40 words, so they are judged by weighted counts, not the
cost index.

## Model answers written from scratch

The paired rewrites above test a model restating a human paragraph. This tests
what a user of a chat product reads: the model's own answer to a question.
`scripts/native_answers.py` takes 55 questions from HC3 (Hello-SimpleAI/HC3,
CC BY-SA 4.0; 30 from wiki_csai, whose human answers are Wikipedia passages on
computer science and AI, and 25 from open_qa), each with a human answer and a
ChatGPT answer from late 2022, and asks five current models each question
unchanged, at default settings, through OpenRouter (275 calls, $1.70). Each
cell gives the median, then in brackets the share of questions where that
source's answer is above the human answer and a Wilcoxon signed-rank p-value.

54 questions with a human answer of 40+ words

| Source | Answers | words median (above human) | cost_index median (above human) | findings_per_1k median (above human) | ms_per_word median (above human) | seconds median (above human) | Not passing |
| --- | --- | --- | --- | --- | --- | --- | --- |
| human | 54 | 133 | 6.12 | 9.76 | 209 | 28 | 20% |
| chatgpt-2022 | 55 | 168 (52%, p 0.42) | 4.07 (31%, p 0.0035) | 8 (33%, p 0.12) | 202 (33%, p 0.0025) | 34 (46%, p 0.96) | 2% |
| google/gemini-4-argon | 53 | 506 (98%, p 2.7e-10) | 3.14 (34%, p 0.0003) | 5.41 (34%, p 0.00088) | 223 (83%, p 3.2e-05) | 120 (98%, p 2.5e-10) | 0% |
| deepseek/deepseek-v4.1-flash | 51 | 246 (71%, p 1.4e-05) | 7.63 (45%, p 0.77) | 12.3 (55%, p 0.096) | 260 (98%, p 5.5e-10) | 69.3 (90%, p 6.2e-09) | 12% |
| x-ai/grok-4.7 | 51 | 204 (63%, p 0.035) | 7.61 (51%, p 0.97) | 13.8 (55%, p 0.12) | 239 (92%, p 9.1e-09) | 53.9 (73%, p 0.0001) | 12% |
| moonshotai/kimi-k3.1-pro | 50 | 210 (70%, p 0.0024) | 5.08 (30%, p 0.037) | 8.54 (38%, p 0.5) | 248 (92%, p 3e-13) | 50.9 (78%, p 6e-07) | 8% |
| mistralai/mistral-large-4-0 | 54 | 316 (91%, p 2.2e-09) | 4.42 (40%, p 0.016) | 7.37 (40%, p 0.045) | 256 (94%, p 3.8e-10) | 92 (96%, p 3.2e-10) | 4% |

The finding from the paired rewrites holds for answers written from scratch.
Four of the five current models write answers that take longer per word to
read than the human answer to the same question, and all five take longer in
total, because they are 1.5 to 4 times as long. The per-word figure depends on
how the estimate treats paragraphs (see "Model signals" below): read paragraph
by paragraph, as `readcost check` does, all five are slower in 83 to 98% of
questions; read sentence by sentence (each answer's prose without Markdown,
split at sentence ends, as `scripts/eval_model_signals.py` does), which does
not depend on how a text is split into paragraphs, DeepSeek, Kimi, Grok and
Mistral are slower in 74 to 94% and Gemini in 51%, about even with the human
answers (no significance test was run). Gemini's answers
have the most short paragraphs (median 21). readcost's construction counts
do not separate them: cost index and findings per 1,000 words are lower than
the human answers' or not different. The Wikipedia passages are dense; one in
five does not pass. The 2022 ChatGPT answers read faster per word than the
human ones, so the per-word cost is a property of current models, not of model
text as such.
## Long dependency: subject and object gaps

On the labelled sample the eight-rater majority accepted none of 13
long-dependency findings. Most reported a fronted connective ("Of course",
"Therefore", "Likewise") or an arc between two clauses as the long dependency,
and the raters said so ("adverb and verb, not dependency"). The rule now keeps
its trigger, the sentence's mean dependency length against the profile, but
reports only a subject, object or attribute arc: 9 or more words when the
trigger fires, or 15 or more at any z, which catches "The index, which ...
runs, serves all queries" (21 words) whose overall z is 2.48.

`scripts/blind_rule_compare.py` drew 30 findings of each version from the
essays and docs, shuffled them together, and the six strict OpenRouter raters
labelled them without knowing which version produced which:

| Version | Majority of six accepts | Single raters |
| --- | --- | --- |
| Longest arc of any kind (before) | 0 of 30 | 0 to 3 |
| Subject, object or attribute gap (after) | 14 of 30 | 15 to 17 |

Volume falls only from 365 to 320 findings in the essays and docs, so the gain
is in which words are reported. On the original labelled sample, 64 findings
are still reported instead of 74, and the eight-rater majority's share goes
from 20.3% to 23.4%. Misparses remain: a misattached appositive or a long
coordinated object can still be reported as a long gap.

## Repetition across texts

`readcost corpus` measures repetition across many texts with Shaib et al.'s
(2024) measures: a template is one of the corpus's 100 most frequent
part-of-speech 6-grams, and CR-POS is the gzip compression ratio of all the
tags in a row. `scripts/eval_corpus_mode.py` runs it on each source's answers
to the 55 HC3 questions, each answer cut to its first 120 words of prose so
that every source contributes about the same amount of text:

| Source | Texts | Words | CR-POS | Texts with a template | Templates per token | Top opener |
| --- | --- | --- | --- | --- | --- | --- |
| human | 55 | 5,932 | 4.78 | 98% | 0.050 | it is |
| chatgpt-2022 | 55 | 6,113 | 5.14 | 95% | 0.078 | it is |
| google/gemini-4-argon | 55 | 6,305 | 4.62 | 89% | 0.051 | here is |
| deepseek/deepseek-v4.1-flash | 55 | 5,883 | 4.58 | 87% | 0.056 | it is |
| x-ai/grok-4.7 | 55 | 5,812 | 4.60 | 85% | 0.047 | it is |
| moonshotai/kimi-k3.1-pro | 55 | 5,695 | 4.54 | 80% | 0.054 | for example |
| mistralai/mistral-large-4-0 | 55 | 6,257 | 4.61 | 93% | 0.043 | here is |

On these answers the current models are not more templated than the human
answers: their CR-POS is slightly lower and their templates per token about
the same. The 2022 ChatGPT answers are the most repetitive. The share
of texts with a template is near its ceiling for every source at this corpus
size, so it separates nothing here. Openers show habits ("here is" leads two
models' answers). Shaib et al. found much larger gaps in summarization (on
movie-review summaries, 95% of model outputs against 46% of human references
contained a template, partly an effect of length); open questions answered at length may leave models less
room to repeat a frame.

Both measures depend on corpus size. On essays cut to 300 words each, the size
check in the same script gives:

| Essays | Words | CR-POS | Templates per token |
| --- | --- | --- | --- |
| 5 | 1,457 | 4.02 | 0.088 |
| 10 | 2,910 | 4.28 | 0.064 |
| 20 | 4,398 | 4.41 | 0.045 |
| 40 | 8,850 | 4.56 | 0.030 |

## Sentence difficulty rated by people

The first human ratings tested are CEFR-SP (Arase, Uchida and Kajiwara
2022): English sentences that two English-education professionals each placed at a CEFR
level from A1 to C2 (scored 1 to 6). Its public part has 7,406 Wikipedia
sentences (Wiki-Auto, CC BY-SA 3.0) and 2,540 sentences written for learners
(SCoRE, CC BY-NC-SA 4.0); the Newsela part needs a separate licence. The data
planned first, Brunato et al. 2018, is behind a request form, and its English
sentences come from the Wall Street Journal treebank under an LDC licence, so
it was not used.

`scripts/eval_sentence_ratings.py` checks each sentence alone and correlates
each measure with the mean rating (Spearman's rho). "Partial" holds sentence
length constant; "within bins" is the mean rho inside six length bins
(readcost `f3871bb`). Wikipedia sentences, median 14 words; on the released
ratings the two raters agree at rho 0.72 by our computation (the paper
reports 37.6% exact agreement and 88.4% within one level):

| Measure | Sentences with it | rho | Partial, length held | Within length bins |
| --- | --- | --- | --- | --- |
| words | all | +0.40 | - | +0.12 |
| mean word length | all | +0.39 | +0.45 | +0.43 |
| predicted ms per word | all | +0.09 | +0.39 | +0.38 |
| any readcost finding | 5% | +0.08 | +0.04 | +0.02 |
| stacked-nouns | 3% | +0.05 | +0.03 | +0.03 |
| inline-list | 1% | +0.05 | +0.03 | +0.01 |
| inanimate-subject | 1% | +0.03 | +0.01 | -0.00 |

The other three rules fire on under 1% of these sentences. A flagged
sentence is rated 0.13 points harder than unflagged sentences of the same
length (387 matched, Wilcoxon p = 0.01, on a scale of 1 to 6). On the
learners' sentences (median 8 words) only 1% are flagged and the
same-length difference, +0.08, is not significant (29 matched, p = 0.47).

The rules add a small, real signal beyond length on Wikipedia text, but they
fire too rarely in single sentences to rank sentences by difficulty. The
reading-time estimate adds far more beyond length (partial rho 0.39); most
of that comes from word length, which it uses as a feature. This is the same
picture as the CLEAR result above: readcost's rules are a list of
constructions to reread, not a difficulty score.

## Non-native writers

Does readcost flag learners of English more than native writers? W&I+LOCNESS
(BEA-2019 shared task) has 3,215 essays of 40 or more words submitted to
Cambridge Write & Improve, each given a CEFR level, and 50 essays by native
English students from LOCNESS. Both licences allow non-commercial research
only, so the text stays local and only counts are reported.
`scripts/eval_learner_essays.py` checks every essay, then again after
applying the annotators' corrections. Findings per 1,000 words, readcost
`f3871bb`:

| Group | Essays | Words | Not passing | All rules | stack | dep | inan | rel | hyph | list |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A (beginner) | 1,347 | 173,231 | 1% | 3.12 | 0.61 | 0.30 | 0.53 | 0.29 | 0.02 | 1.39 |
| B (intermediate) | 1,099 | 228,759 | 1% | 2.92 | 0.61 | 0.35 | 0.45 | 0.20 | 0.01 | 1.29 |
| C (advanced) | 769 | 198,856 | 1% | 3.05 | 0.74 | 0.38 | 0.57 | 0.25 | 0.02 | 1.10 |
| native (LOCNESS) | 50 | 20,461 | 0% | 4.74 | 0.83 | 0.93 | 0.73 | 0.44 | 0.10 | 1.71 |
| A, corrected | 1,348 | 172,941 | 1% | 2.31 | 0.39 | 0.19 | 0.36 | 0.14 | 0.02 | 1.21 |
| C, corrected | 769 | 199,080 | 1% | 2.90 | 0.62 | 0.38 | 0.56 | 0.21 | 0.02 | 1.11 |

Learners are flagged less than native students, at each of the levels A, B
and C and for every rule; native essays have two to three times the
long-dependency rate. readcost's
rules count constructions that fluent writers build, so they are not biased
against non-native writing on this data. Errors do add findings: corrections
cut beginners' rate by a quarter (A, 3.12 to 2.31; A1, 3.75 to 2.20), mostly stacked nouns,
inanimate subjects and object relatives, where a misspelling or missing word
misleads the parser. Advanced learners' rates barely move (C, 3.05 to 2.90).
Limits: 50 native essays, all by students, and essays are short (130 words on
average at level A, 260 at C, 410 for native), so the cost index is 0 for
most learner essays.

## Human simplifications

ASSET (Alva-Manchego et al. 2020, CC BY-NC 4.0) has 2,359 Wikipedia
sentences, each simplified by ten crowd workers, who could paraphrase,
delete and split. This is the human counterpart to the model rewrites above.
`scripts/eval_simplifications.py` compares 23,280 pairs. The shares count
pairs; the two-sided Wilcoxon test runs on each of the 2,336 original
sentences' mean difference, since its ten simplifications are not independent
(an earlier version tested all pairs and overstated the significance):

| Measure | Original median | Simplification median | Lower | Same | Higher | p |
| --- | --- | --- | --- | --- | --- | --- |
| words | 17 | 15 | 64% | 16% | 19% | <0.001 |
| findings | 0 | 0 | 5% | 93% | 2% | <0.001 |
| cost index | 0 | 0 | 6% | 89% | 5% | 0.87 |
| predicted ms per word | 241 | 239 | 56% | 1% | 43% | <0.001 |

| Rule | Per 1k words, original | Per 1k words, simplified | Present in original: removed | Absent in original: added |
| --- | --- | --- | --- | --- |
| long-dependency | 0.55 | 0.23 | 84% of 239 | 0.2% |
| reduced-object-relative | 0.12 | 0.10 | 86% of 50 | 0.1% |
| inanimate-subject | 0.29 | 0.36 | 65% of 127 | 0.4% |
| stacked-nouns | 2.00 | 1.79 | 44% of 830 | 0.8% |
| inline-list | 2.84 | 2.39 | 37% of 1,234 | 0.6% |
| hyphen-compound | 0.07 | 0.08 | 20% of 30 | 0.0% |
| all | 5.87 | 4.95 | 43% of 2,420 | 2.0% |

People asked to simplify remove long dependencies and object relatives
almost every time they occur, and the rate of findings per word falls by 16%.
They keep most noun stacks and lists, many of which are names and
established terms in Wikipedia text, and they add inanimate subjects slightly
more than they remove them. Predicted reading time per word barely moves,
because simplifications keep the rare content words. Findings fall, but so
does length, and the cost index (points per 1,000 words) shows no reliable
change per original sentence (p = 0.87), as with the model rewrites.

## Python Enhancement Proposals

Specifications and design documents: `scripts/fetch_peps.py` takes the 401
PEPs whose status is Final, Active or Accepted and whose text is in the
public domain or under CC0 (22 more were skipped for licence), from
python/peps at `362ca9d`. Both runs below are readcost `f3871bb`:

| Category | Texts | Words | Pass | CI p50 / p90 | stack | dep | inan | rel | hyph | list |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| essays | 118 | 391,429 | 98% | 2.5 / 6.4 | 1.44 | 0.59 | 0.71 | 0.40 | 0.08 | 1.11 |
| docs | 83 | 179,649 | 96% | 2.8 / 6.6 | 2.06 | 0.51 | 0.50 | 0.37 | 0.09 | 0.77 |
| PEPs, standards track | 301 | 677,538 | 98% | 3.8 / 7.5 | 2.69 | 0.63 | 0.56 | 0.27 | 0.14 | 1.00 |
| PEPs, informational | 65 | 90,441 | 89% | 4.5 / 13.0 | 2.68 | 0.46 | 0.64 | 0.23 | 0.11 | 1.18 |
| PEPs, process | 35 | 62,239 | 100% | 4.1 / 7.1 | 2.22 | 0.82 | 0.42 | 0.19 | 0.22 | 1.35 |

PEPs pass at the rate of essays and docs; stacked nouns and hyphen compounds
run higher.
The informational PEPs that do not pass are short release schedules and
election notices (100 to 300 words), where two stacks are enough to reach
"advise". Several of those stacks are false positives of one kind: a number
joined to a unit by a hyphen ("17-month development period", "two-week
nomination period") is split, and the unit is counted as a noun.

## Per-rule benchmark

`eval/rulebench/rulebench.jsonl` lists 116 real sentences, 18 to 21 per
default rule, each labelled with whether the rule should fire. Expected-fire
items are constructions an editor would change; expected-no-fire items are
traps, most of them sentences some version of readcost has reported. The
repository keeps references only: the source URL (PEPs at a pinned commit,
SQLite docs, the Go blog and Effective Go, the Rust book, Django docs, GOV.UK
guidance, two essays), its licence, the label and the SHA-256 of the sentence;
the only text kept is readcost's own rule examples. `scripts/fetch_rulebench.py`
downloads the sources and rebuilds the sentences by hash (all 116 rebuild);
three items from an earlier draft could not be rebuilt and were dropped.

Labels: 48 come from the majority of the strict model raters in the sections
above, judging readcost's findings. The other 68 were first labelled by one
maintainer, then all 116 were labelled blind by the six strict OpenRouter
raters (`scripts/label_rulebench.py`), who saw only the rule's definition and
the sentence. Counting a 3 to 3 split as a tie: of the 48 rater labels the
blind majority agreed with 43, tied on 3 and disagreed with 2 (kept, with
the votes recorded); of the 68 maintainer labels it agreed with 58, tied on 3,
overturned 6 (which now carry the blind majority's label) and missed one rater
on 1. Each item records its blind votes.

`scripts/rulebench.py --bench` scores the current rules:

| Rule | Items | Fire / no-fire | TP | FN | TN | FP | Precision | Recall | Silent on traps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hyphen-compound | 18 | 5 / 13 | 4 | 1 | 3 | 10 | 29% | 80% | 23% |
| inanimate-subject | 20 | 6 / 14 | 6 | 0 | 5 | 9 | 40% | 100% | 36% |
| inline-list | 18 | 10 / 8 | 10 | 0 | 2 | 6 | 62% | 100% | 25% |
| long-dependency | 20 | 10 / 10 | 9 | 1 | 4 | 6 | 60% | 90% | 40% |
| reduced-object-relative | 21 | 10 / 11 | 9 | 1 | 6 | 5 | 64% | 90% | 55% |
| stacked-nouns | 19 | 8 / 11 | 8 | 0 | 2 | 9 | 47% | 100% | 18% |

These numbers describe the bench, not the rules' precision on real text: the
traps were picked from reported findings, so the bench is built to be hard on
precision. Use it to compare two versions of a rule.

## Model signals

`scripts/eval_model_signals.py` computes signals from models that readcost
does not use: surprisal (mean, maximum and standard deviation, in bits per
token) and predictive entropy from two small language models of different
families (SmolLM2-135M and GPT-2), a readability regressor
(agentlans/deberta-v3-xsmall-readability, trained on FineWeb-Edu, TinyStories,
Wikipedia and arXiv paragraphs), and a sentence CEFR classifier
(AbdullahBarayan/ModernBERT-base-doc_sent_en-Cefr). The classifier's training
data is not documented and may include CEFR-SP, so it is left out of that test.
readcost's predicted ms per word is computed sentence by sentence.

On the 7,453 Wiki-Auto sentences rated by teachers (CEFR-SP; length alone has
rho +0.36):

| Signal | rho | partial rho (length held) | mean rho within length bins |
| --- | --- | --- | --- |
| length in words | +0.36 | | |
| SmolLM2-135M surprisal | +0.00 | +0.09 | +0.07 (5 bins) |
| SmolLM2-135M max_surprisal | +0.15 | +0.10 | +0.08 (5 bins) |
| SmolLM2-135M surprisal_sd | +0.13 | +0.17 | +0.15 (5 bins) |
| SmolLM2-135M entropy | -0.12 | -0.00 | -0.05 (5 bins) |
| gpt2 surprisal | -0.02 | +0.07 | +0.08 (5 bins) |
| gpt2 max_surprisal | +0.25 | +0.20 | +0.19 (5 bins) |
| gpt2 surprisal_sd | +0.24 | +0.25 | +0.24 (5 bins) |
| gpt2 entropy | -0.21 | -0.11 | -0.09 (5 bins) |
| readability grade | +0.58 | +0.48 | +0.47 (5 bins) |
| readcost ms per word | +0.08 | +0.33 | +0.32 (5 bins) |

The readability regressor tracks the teachers far better than anything readcost
computes: partial rho +0.48, against +0.33 for readcost's predicted ms per word
in this run. The sentence-ratings section above is a separate run
(`scripts/eval_sentence_ratings.py`): it checks each sentence with readcost,
keeps the 7,406 with three or more words, and uses readcost's word count as
the length; it gives +0.39 for ms per word and +0.04 for readcost's findings.
This script keeps all 7,453 sentences and counts whitespace words, which is why
the two figures for ms per word differ. Among the language-model signals, how uneven the
surprisal is (its standard deviation, one way to measure uniform information
density, and a weak one by Meister et al. 2021's comparison) and the most
surprising token track difficulty a little; mean surprisal and
entropy do not.

On 600 ASSET pairs, each original against its first human simplification:

| Signal | Original median | Simplification median | Lower in the simplification | p |
| --- | --- | --- | --- | --- |
| SmolLM2-135M surprisal | 5.07 | 5.38 | 34% | 6.8e-24 |
| SmolLM2-135M max_surprisal | 15.9 | 15.5 | 42% | 0.36 |
| SmolLM2-135M surprisal_sd | 4.39 | 4.4 | 48% | 0.49 |
| SmolLM2-135M entropy | 5.2 | 5.52 | 26% | 1.7e-38 |
| gpt2 surprisal | 5.8 | 6.17 | 33% | 1.2e-26 |
| gpt2 max_surprisal | 15.9 | 15.9 | 42% | 0.57 |
| gpt2 surprisal_sd | 4.46 | 4.48 | 48% | 0.18 |
| gpt2 entropy | 6.05 | 6.26 | 28% | 2.7e-32 |
| readability grade | 11.7 | 8.51 | 91% | 3.2e-88 |
| cefr_expected | 3.86 | 3 | 79% | 1.5e-48 |
| cefr_entropy | 0.0171 | 0.0267 | 48% | 0.31 |
| readcost ms per word | 243 | 239 | 56% | 0.015 |

People's simplifications lower the readability grade in 91% of pairs and the
CEFR level in 79%, but raise mean surprisal and entropy: plainer wording is not
more predictable per token to these models.

On the model and human answers to the same HC3 questions (each answer's prose,
without Markdown), for selected signals:

| Source | SmolLM2-135M surprisal | SmolLM2-135M max_surprisal | SmolLM2-135M surprisal_sd | SmolLM2-135M entropy | gpt2 surprisal | gpt2 max_surprisal | gpt2 surprisal_sd | gpt2 entropy | readability grade | cefr_expected | cefr_entropy | readcost ms per word |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| human | 3.82 | 18.5 | 3.7 | 3.85 | 4.57 | 18.2 | 4.08 | 4.74 | 16.3 | 5 | 0.00735 | 226 |
| chatgpt-2022 | 2.19 (0%) | 14 (16%) | 2.52 (0%) | 2.94 (5%) | 3.07 (0%) | 18.1 (44%) | 3.18 (0%) | 4.25 (9%) | 13.8 (25%) | 4.01 (7%) | 0.0271 (65%) | 214 (31%) |
| google/gemini-4-argon | 3.31 (17%) | 18.6 (47%) | 3.54 (30%) | 3.44 (13%) | 4.2 (17%) | 22.3 (85%) | 3.92 (34%) | 4.59 (26%) | 10.7 (4%) | 4.9 (9%) | 0.0102 (62%) | 228 (51%) |
| deepseek/deepseek-v4.1-flash | 3.66 (44%) | 18 (46%) | 3.74 (46%) | 3.76 (44%) | 4.68 (56%) | 22.3 (85%) | 4.24 (69%) | 4.86 (56%) | 12.5 (10%) | 5 (17%) | 0.054 (60%) | 259 (94%) |
| x-ai/grok-4.7 | 4.15 (75%) | 17.8 (45%) | 3.87 (61%) | 4 (69%) | 5.08 (90%) | 23.1 (90%) | 4.39 (80%) | 5.03 (65%) | 13.9 (24%) | 5 (24%) | 0.02 (49%) | 240 (75%) |
| moonshotai/kimi-k3.1-pro | 3.74 (51%) | 17.6 (41%) | 3.69 (35%) | 3.76 (43%) | 4.7 (65%) | 23.3 (92%) | 4.25 (65%) | 4.86 (55%) | 13.6 (20%) | 4.99 (14%) | 0.0111 (59%) | 246 (84%) |
| mistralai/mistral-large-4-0 | 3.76 (50%) | 18.6 (52%) | 3.76 (54%) | 3.8 (50%) | 4.59 (63%) | 21.4 (85%) | 4.1 (59%) | 4.87 (63%) | 15.8 (56%) | 5 (31%) | 0.0198 (59%) | 243 (74%) |

The signals disagree. The readability regressor and the CEFR classifier rate
most model answers easier than the human answers (dense Wikipedia passages),
while readcost's predicted time per word is higher for four of the five
models. A text can look easier to a classifier and still take longer to read;
which one matches readers needs a study with people.

## Long dependency: words or new referents

Gibson's Dependency Locality Theory (2000) measures the cost of a gap by the
new discourse referents inside it (head nouns and tensed verbs), not by
words. `features.new_referents` counts them for the reported arc. Over the
20,789 sentences long-dependency examines in the essays and docs, the two
measures correlate at r = 0.87.

On findings the raters had already labelled (both earlier samples, reparsed;
80 of 92 matched), 31 were subject or object arcs and the strict majority
accepted 14. As a score for telling accepted from rejected findings, the
number of words between the two words reaches an AUC of 0.68 and the referent
count 0.61. Every accepted finding had 15 or more words in its gap. All 49 other arcs were rejected.

A referent rule tuned to fire about as often (5 or more referents at any z,
or 2 or more when the sentence's z is 2.5 or more: 308 findings against 320)
shares 231 findings with the current rule. `scripts/blind_rule_compare.py`'s
format took 30 findings only the current rule reports and 30 only the
referent rule reports, shuffled; the six strict raters labelled them blind:

| Findings only one rule reports | Majority of six accepts | Single raters |
| --- | --- | --- |
| Words (current rule) | 17 of 30 | 14 to 19 |
| New referents | 10 of 30 | 7 to 15 |

Word distance stays the default, and the referent measure was removed in
0.3 rather than kept as an option.

## Center embedding and undefined acronyms (opt-in)

With both rules enabled, the essays and docs give:

| Rule | Findings | Per 1,000 words | Essays | Docs |
| --- | --- | --- | --- | --- |
| center-embedding | 14 | 0.02 | 0.04 | 0.00 |
| undefined-acronym | 476 | 0.83 | 0.93 | 0.63 |

center-embedding counts a finite clause as nested when it interrupts a
subject and its verb, or a verb and its object, of the clause around it;
counting any clause with words of its parent on both sides flagged fronted
"when" and "if" clauses after a connective, and gave 106 findings. Six of
118 essays and none of the 83 docs reach depth two. undefined-acronym skips
a fixed list of common abbreviations and any whose lowercase form has a Zipf
frequency of 3.8 or more (CEO, TV, and capitalised words such as UPDATE),
and treats words just before an acronym that start with its letters as its
expansion ("write-ahead log or WAL mode"). Without these it gave 776
findings; the frequency cut removed 288 and the expansion check 12. Most
remaining hits are names that a specialist reader knows (AWS, POSIX, GNU) or
SQL keywords below the cut (PRAGMA, ROLLBACK).

The six strict raters labelled all 14 center-embedding findings and 30 random
undefined-acronym findings, shuffled together, with the rule definitions
added to the rater prompt:

| Rule | Majority of six accepts | Single raters |
| --- | --- | --- |
| center-embedding | 5 of 14 | 1 to 11 |
| undefined-acronym | 7 of 30 | 5 to 9 |

For center-embedding the raters' commonest objection was that the clause is
not center-embedded (a single relative clause, or right-branching); the
majority judged the construction present in 8 of 14. For undefined-acronym
they called most hits common acronyms, terms of art or SQL keywords; the
raters see one sentence, not the document, so they cannot check whether the
acronym was spelled out elsewhere. Both rules stay off by default.

center-embedding also misses doubly embedded clauses that the small parser
attaches elsewhere: of four constructed double embeddings, it reported one.

## Peaks and spread of word cost

Gibson (1998) argued that a sentence is as hard as its hardest point, not its
average, and Meister et al. (2021) found super-linear costs fit acceptability
better than linear ones. `scripts/eval_peak_cost.py` takes each sentence's
predicted ms per word and tests its peak (maximum, mean of the top three,
90th percentile), its spread (standard deviation) and a super-linear sum
(ms to the 1.25 per word) against the CEFR-SP teacher ratings, with Spearman
partial correlations. Predicted time is mostly word length and frequency, so
a peak may only be the longest or rarest words; the last column holds those
fixed:

| Measure | Wiki-Auto, length held | Wiki-Auto, + mean ms, longest and rarest word | Wiki-Auto, + mean ms, 3 longest and 3 rarest words | SCoRE, length held | SCoRE, + mean ms, longest and rarest word | SCoRE, + mean ms, 3 longest and 3 rarest words |
| --- | --- | --- | --- | --- | --- | --- |
| mean ms per word | +0.33 | | | +0.43 | | |
| maximum | +0.32 | +0.08 | +0.07 | +0.40 | +0.05 | +0.02 |
| mean of top three | +0.35 | +0.09 | +0.06 | +0.45 | +0.10 | +0.02 |
| 90th percentile | +0.32 | +0.06 | +0.01 | +0.42 | +0.07 | +0.01 |
| standard deviation | +0.34 | +0.12 | +0.08 | +0.30 | +0.05 | +0.01 |
| ms^1.25 per word | +0.34 | +0.08 | +0.06 | +0.44 | +0.05 | +0.02 |

With the three longest and three rarest words fixed, the peaks add nothing on
SCoRE's learner sentences and at most 0.08 on Wikipedia. What carries the
signal is word length: the mean length of a sentence's three longest words
has a partial rho of +0.39 (Wiki-Auto) and +0.25 (SCoRE) beyond sentence
length and mean predicted time, more than any peak of the predicted times.
The three rarest words point the other way on Wikipedia (-0.14), where rare
words are mostly names, and the same way on SCoRE (+0.18). On ASSET, people
simplifying a sentence lower the top-three mean in 66% of pairs, against 57%
for the mean (both p < 0.001 per original sentence).

So the teachers' ratings track long words more than the reading-time model
does; a peak measure would mostly re-add that. Nothing here changes the
rules or the verdict. Within-sentence surprisal spread from a language model
(partial rho +0.25, "Model signals") remains the strongest model-based
signal of this kind.

## Broader corpora

Three new samples test readcost outside the essays, docs and PEPs above:
arXiv abstracts and introductions, GitHub READMEs stratified by language and
stars, and texts written for experts alongside texts on the same subject
written for lay readers. All runs are readcost `9655bea` with `Config()`
defaults, fetched on 2026-10-27. The text stays under `REF/broad`; only these
aggregates leave it.

```sh
REF=/Volumes/Rebuildable/readcost-ref
uv run scripts/fetch_arxiv.py $REF/broad/arxiv               # --date 2026-10-20 --per-set 50 --intros 150
uv run scripts/fetch_github_readmes.py $REF/broad/readmes     # --per-cell 12 --windows 2 --seed 1
uv run scripts/fetch_expert_lay.py $REF/broad/expert-lay      # --summaries 150 --wiki 150 --govuk 100 --seed 1
uv run --group eval scripts/eval_broad.py $REF/broad
```

### Items and licences

| Corpus | Items | Licence | Skipped |
| --- | --- | --- | --- |
| arXiv abstracts, 8 sets | 385 (50 per set; q-fin 35 after 10 days) | CC BY 362, CC0 12, CC BY-SA 11 | every paper under arXiv's non-exclusive licence or a CC NC/ND licence |
| arXiv introductions (section S1) | 152 (19 per set) | CC BY 143, CC0 6, CC BY-SA 3 | 40 papers: no HTML version, or S1 not titled Introduction |
| GitHub READMEs, 8 languages x 4 star tiers | 361 (12 per cell; Haskell 500..5000 has 3, Haskell >5000 has 4, JavaScript 5..50 has 8, Go 5..50 has 10) | MIT 168, Apache-2.0 97, GPL-3.0 34, BSD-3-Clause 23, GPL-2.0 13, MPL-2.0 8, AGPL-3.0 8, other 10 | 263 repositories with no licence GitHub recognizes, 155 READMEs under 100 words of prose, 4 not English, 2 without a README |
| PLOS (Comp Biol, Genetics, Pathogens, NTD) and eLife: abstract vs author summary or digest | 150 pairs (30 per journal) | CC BY 141, CC0 9 (pairs) | 167 articles without a lay summary, 12 without either, 2 with a side under 80 words; none failed the licence check |
| English vs Simple English Wikipedia | 150 pairs (CS 48, maths 47, physics 41, biology 14) | CC BY-SA 4.0 | 149 Simple articles under 150 words, 8 with no English link, 4 English articles short |
| GOV.UK `guide` and `detailed_guide` | 100 + 100 (unpaired) | OGL v3.0 | 7 pages under 150 words, 2 not English |

All items used have reuse rights; nothing was kept on the strength of a local
analysis exception. Group comparisons leave out texts under 150 words, which
drops most arXiv abstracts from the pooled percentiles (280 of 385 remain);
the per-field abstract tables use a 50-word floor, and the pair tests use
every pair.

### Pooled distributions

| Category | Texts | Words | CI p50 / p90 | Pass | ms/word p50 | Words/sentence p50 | stack | dep | inan | rel | hyph | list |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| arXiv abstracts | 385 | 70,227 | 10.0 / 22.3 | 68% | 242 | 24.5 | 5.95 | 0.93 | 0.83 | 0.10 | 2.72 | 2.01 |
| arXiv introductions | 152 | 144,183 | 8.1 / 15.4 | 88% | 237 | 22.3 | 4.24 | 0.94 | 1.03 | 0.30 | 1.60 | 2.20 |
| PLOS/eLife abstracts and summaries | 300 | 61,648 | 6.1 / 19.9 | 78% | 229 | 23.1 | 5.79 | 1.56 | 0.57 | 0.08 | 0.39 | 1.44 |
| English and Simple Wikipedia | 300 | 493,404 | 4.4 / 9.5 | 95% | 212 | 19.3 | 2.82 | 0.93 | 0.48 | 0.20 | 0.12 | 2.29 |
| READMEs | 361 | 233,113 | 5.0 / 11.8 | 94% | 240 | 13.5 | 3.41 | 0.31 | 0.32 | 0.24 | 0.39 | 2.66 |
| GOV.UK guides | 200 | 240,093 | 3.1 / 7.9 | 97% | 222 | 14.4 | 2.15 | 0.43 | 0.22 | 0.29 | 0.02 | 1.32 |

arXiv abstracts are the densest text readcost has been run on: a third get
"advise" or "block", against 2 to 4% of the essays and docs. Stacked nouns
(5.95 per 1,000 words) and hyphen compounds (2.72) drive it.

### Expert and lay texts

Each pair is one unit; the Wilcoxon signed-rank test is two-sided on the
paired differences. "Lay lower" is the share of pairs where the lay text has
the lower value.

| Pairs | Measure | Expert median | Lay median | Median diff | Lay lower | p |
| --- | --- | --- | --- | --- | --- | --- |
| PLOS/eLife, 150 | findings per 1k words | 10.1 | 6.0 | -1.9 | 54% | 0.0004 |
| | cost index | 9.4 | 5.5 | -1.7 | 55% | 0.0002 |
| | ms per word | 241 | 223 | -14.5 | 81% | <0.001 |
| | words per sentence | 23.0 | 23.0 | +0.2 | 48% | 0.76 |
| | mean word length | 5.68 | 5.52 | -0.12 | 69% | <0.001 |
| | words | 216 | 181 | -46 | 73% | 0.005 |
| Wikipedia, 150 | findings per 1k words | 6.7 | 4.1 | -2.6 | 72% | <0.001 |
| | cost index | 5.1 | 2.5 | -2.5 | 71% | <0.001 |
| | ms per word | 218 | 201 | -13.8 | 75% | <0.001 |
| | words per sentence | 21.5 | 16.2 | -4.9 | 85% | <0.001 |
| | mean word length | 4.97 | 4.82 | -0.23 | 74% | <0.001 |
| | words | 2,390 | 288 | -1,950 | 98% | <0.001 |
| Wikipedia, English cut to Simple length | findings per 1k words | 6.8 | 4.1 | -2.4 | 65% | <0.001 |
| | cost index | 4.9 | 2.5 | -1.9 | 65% | <0.001 |
| | ms per word | 212 | 201 | -9.4 | 69% | <0.001 |

| GOV.UK (Mann-Whitney U) | guide, 100 | detailed_guide, 100 | p |
| --- | --- | --- | --- |
| findings per 1k words | 3.0 | 5.3 | <0.001 |
| cost index | 2.6 | 4.1 | <0.001 |
| ms per word | 219 | 224 | 0.005 |
| words per sentence | 13.8 | 15.5 | <0.001 |
| mean word length | 4.47 | 4.93 | <0.001 |

In all three sources the text written for lay readers scores lower on
findings, cost index and predicted reading time. The PLOS and eLife pairs are
the cleanest test of the confound: summaries and abstracts have the same
median sentence length (23 words, p = 0.76), yet the summaries have fewer
findings, almost all from stacked nouns (5.2 to 2.9 per 1,000 words, p <
0.001). Mean word length does fall with them (5.68 to 5.52), so part of the
drop may track vocabulary rather than structure. In Wikipedia, sentence length
falls with everything else, and the per-rule drops (long dependency in 77% of
pairs, stacked nouns in 69%) cannot be separated from it here. Cutting each
English article to its Simple counterpart's length shrinks the effect but
keeps it (cost index 4.9 against 2.5).

By source the effect is uneven. eLife digests (written by eLife's editorial staff) and PLOS
Computational Biology summaries are clearly lower (cost index -8.2 and -4.3
per pair, p < 0.005); PLOS Genetics marginally (-1.4, p = 0.02); PLOS
Pathogens (-0.1, p = 0.70) and PLOS NTD (+0.4, p = 0.49) show no difference
in findings, although predicted reading time still falls (p < 0.03). PLOS
author summaries are written by the paper's authors, which may explain why
some stay close to the abstract; this was not checked.

### READMEs

306 READMEs of 150 or more prose words. Spearman correlation with stars:
findings per 1k words rho = 0.08 (p = 0.15), cost index 0.05 (p = 0.34),
predicted ms per word 0.22 (p < 0.001), mean word length 0.18 (p = 0.002),
inline lists 0.17 (p = 0.003). Popular projects' READMEs are no less
readable by readcost's rules; they are longer, use longer words and more
inline lists. By language (Kruskal-Wallis p < 0.001), median cost index runs
from 2.9 (Python) and 4.1 (Haskell) to 6.4 (C++) and 7.9 (Java), mostly from
stacked nouns and inline lists; sentence length does not differ (p = 0.10).

### arXiv

Fields differ (Kruskal-Wallis p < 0.01 for findings and cost index, in both
abstracts and introductions). Median cost index in abstracts runs from 6.8
(math) and 7.5 (econ) to 14.9 (eess); introductions keep the same order (5.6
math, 11.4 eess). Within a paper, the introduction is not lighter than the
abstract: cost index differs by +0.1 per paper (p = 0.20), findings per 1k
words by +1.1 (p = 0.63), on 152 papers. The introduction has shorter words
(-0.14 letters) and sentences (-1.9 words) and 5 ms per word less predicted
reading time, and it trades stacked nouns and hyphen compounds for long
dependencies, inanimate subjects and object relatives, which barely occur in
abstracts.

### Surprises and limits

- Introductions are not lighter than abstracts by findings, though they are
  four to five times longer and less compressed by every other measure. The
  pooled rates (5.95 against 4.24 stacked nouns per 1,000 words) suggest a
  difference that the per-paper test does not find; abstracts of 150 to 250
  words make per-text rates noisy.
- Stars do not predict findings. Whatever makes a README popular, readcost's
  rules do not see it, and higher-star READMEs score slightly worse on
  predicted reading time.
- Two of four PLOS journals show no expert-lay difference in findings.
- arXiv math introductions have 16.4 words per sentence against 21 to 25
  elsewhere: display equations and `[MATH]` tokens likely split sentences.
  `[MATH]` also counts as a four-letter word in mean word length.
- Simple Wikipedia articles of 150+ words are a selected subset (149 of 311
  tried were shorter); English articles were cut by paragraph, so the
  length-matched English side still runs longer (386 against 288 words).
- The arXiv harvest is by OAI datestamp (2026-10-11 to 2026-10-20), which
  includes revised older papers; introductions come only from papers first
  submitted in 2024 or later with an HTML version. READMEs come from random
  creation-date windows and random result pages, two windows per cell, so
  Haskell's higher tiers are thin (3 and 4 READMEs).
- GOV.UK guides are not paired by topic: the comparison is between two
  publishing formats, not two treatments of one subject.

## More corpora: technical and non-technical

Thirteen new categories, 2,322 texts and 2.4 million readcost words, test
readcost on Stack Exchange answers and their edits, design documents, MDN, man
pages, release notes, and fiction and essays, news, law and regulation, health
pages for lay readers, social-science abstracts and Wikipedia Featured
Articles. All runs are readcost `6be1918` with `Config()` defaults, fetched on
2026-10-27. The text stays under `REF/broad`; only these aggregates leave it.

```sh
REF=/Volumes/Rebuildable/readcost-ref
uv run scripts/fetch_stackexchange.py $REF/broad/stackexchange    # --per-group 25 --pairs-per-site 25
uv run scripts/fetch_design_docs.py $REF/broad/design-docs        # --rust 150 --keps 150 --seed 1
uv run scripts/fetch_mdn.py $REF/broad/mdn                        # --per-group 100 --seed 1
uv run scripts/fetch_man_pages.py $REF/broad/man-pages            # --per-section 34 --seed 1
uv run scripts/fetch_release_notes.py $REF/broad/release-notes    # --per-repo 5
uv run scripts/fetch_domains.py $REF/broad/literature --parts literature
uv run scripts/fetch_domains.py $REF/broad/news --parts news
uv run scripts/fetch_domains.py $REF/broad/law --parts federal-register,uk-notes,courts
uv run scripts/fetch_domains.py $REF/broad/health --parts medlineplus
uv run scripts/fetch_domains.py $REF/broad/openalex --parts openalex
uv run scripts/fetch_domains.py $REF/broad/wiki-featured --parts featured
uv run --group eval scripts/eval_more.py $REF/broad      # -> $REF/broad/results-more/
uv run scripts/build_all_manifest.py $REF                # -> $REF/broad/ALL.jsonl
```

Each fetch log is `$REF/broad/<dir>.log`. Full tables, every rule and every
group comparison: `results-more/summary.md` and `summary.json`; per-pair
Stack Exchange differences: `results-more/se_pairs.jsonl`.

### Items and licences

| Corpus | Items | Licence | Skipped |
| --- | --- | --- | --- |
| Stack Exchange answers: unix, softwareengineering, cs, math; top-scored and score 0 or 1 | 197 (25 per cell; unix low 22) | CC BY-SA 3.0 77, 2.5 70, 4.0 50 (per answer) | 227 under 80 words of prose; 41 API requests of the 300 a day |
| Stack Exchange revision pairs, first vs last revision | 100 pairs (25 per site) | CC BY-SA, version per revision | 92 with a side under 80 words, 4 with unchanged prose |
| Go proposals (`design/*.md`) | 113 of 116 | BSD-3-Clause | 3 stubs under 150 words |
| Rust RFCs, evenly spaced by number | 148 of 150 (start years 2014 to 2026) | Apache-2.0 or MIT | 2 under 150 words |
| Kubernetes KEP READMEs, random | 150 | Apache-2.0 | none |
| MDN pages by `page-type` | 100 guides + 100 reference | CC BY-SA 2.5 | 115 under 150 words, 8 landing or listing pages, 5 guides past the quota |
| OpenBSD man pages, sections 1 to 3 | 102 (34 per section) | BSD-3 63, ISC 17, BSD-2 16, BSD-4 3, public domain 3 | 85 DESCRIPTIONs under 150 words, 5 unclassified licences |
| Linux man-pages 6.20, sections 1 to 3 | 80 (12, 34, 34; section 1 has only 40 pages) | per file SPDX: Linux-man-pages-copyleft 48, GPL-2.0+ 19, GPL-1.0+ 5, other 8 | 111 under 150 words, 3 unclassified |
| GitHub release notes, 30 repositories | 142 (121 curated, 21 auto-generated) | repository SPDX: MIT 78, Apache-2.0 40, BSD-3 15, Unlicense 5, AGPL-3.0 4 | 9 first-choice repositories replaced (bodies only links, or no SPDX licence) |
| Project Gutenberg passages, 400 to 800 words | 90 novel + 60 essay, from 75 books | Public domain (US) | none |
| Wikinews articles, 2005 to 2024 | 120 | CC BY 4.0 (site's current statement) | 32 under 150 words |
| Federal Register rules and notices, 2001 to 2025 | 120 | US government work, public domain | 8 under 150 words |
| UK explanatory notes, acts of 2000 to 2025 | 120 | OGL v3.0 | 132 acts without notes |
| Court lead opinions (COLD Cases, CourtListener and CAP data) | 120 | CC0 | 171 rows without one lead opinion or under 150 words |
| MedlinePlus health topic summaries | 120 | Public domain (US NLM) | 58 under 150 words |
| OpenAlex abstracts: sociology, history, economics, psychology | 120 (30 each) | CC BY, checked per work | 30 under 100 words |
| Wikipedia Featured Articles: history, arts, biography | 120 (40 each) | CC BY-SA 4.0 | none |

Not fetched:

- IETF RFCs. rfc-editor.org, www.ietf.org and the datatracker document pages
  all answer the project User-Agent with a Cloudflare 403. Only the
  datatracker metadata API answers, and it has abstracts, not text. No
  fetcher was written.
- CourtListener's own API returns 401 without a token. Court opinions came
  from COLD Cases, a CC0 dataset built from CourtListener and the Caselaw
  Access Project, read through the Hugging Face datasets server.
- USPTO patents: the sources need an API key.
- Cochrane plain-language summaries: the licence is doubtful, so they were
  not fetched. Policy and NGO reports: skipped as instructed.

### Pooled distributions

Cost index percentiles over texts of 150+ words; findings per 1,000 words.

| Category | Texts | Words | CI p50 / p90 | Pass | ms/word p50 | Words/sentence p50 | stack | dep | inan | rel | hyph | list |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| release notes | 142 | 48,704 | 10.4 / 22.7 | 75% | 284 | 11.7 | 7.47 | 0.41 | 0.70 | 0.14 | 1.15 | 1.60 |
| man pages (DESCRIPTION) | 182 | 103,519 | 6.5 / 13.8 | 88% | 230 | 16.2 | 4.56 | 0.88 | 0.78 | 0.25 | 0.31 | 2.02 |
| social-science abstracts | 120 | 24,032 | 6.4 / 16.4 | 85% | 216 | 23.1 | 4.33 | 1.25 | 1.96 | 0.17 | 0.08 | 2.87 |
| health pages for lay readers | 120 | 50,062 | 5.8 / 10.9 | 98% | 209 | 12.3 | 3.54 | 0.20 | 0.56 | 0.10 | 0.00 | 3.72 |
| regulation | 240 | 362,311 | 4.9 / 10.1 | 92% | 221 | 24.4 | 2.48 | 1.39 | 0.29 | 0.25 | 0.02 | 2.11 |
| design docs | 411 | 939,322 | 4.4 / 8.3 | 96% | 219 | 17.5 | 3.05 | 0.53 | 0.62 | 0.32 | 0.47 | 0.86 |
| court opinions | 120 | 134,425 | 4.1 / 8.0 | 98% | 206 | 28.1 | 1.11 | 1.53 | 0.71 | 0.25 | 0.04 | 1.99 |
| MDN | 200 | 181,392 | 4.0 / 10.1 | 97% | 210 | 18.0 | 2.77 | 0.29 | 0.35 | 0.38 | 0.50 | 1.69 |
| Wikipedia Featured Articles | 120 | 236,640 | 3.0 / 5.4 | 98% | 210 | 22.7 | 1.09 | 0.75 | 0.54 | 0.21 | 0.09 | 1.69 |
| news (Wikinews) | 120 | 45,981 | 2.9 / 9.2 | 98% | 209 | 20.3 | 1.74 | 0.70 | 0.89 | 0.20 | 0.17 | 1.02 |
| Stack Exchange answers | 197 | 73,398 | 2.6 / 8.3 | 96% | 203 | 18.5 | 1.20 | 0.83 | 0.59 | 0.37 | 0.05 | 1.32 |
| Stack Exchange revisions (both sides) | 200 | 110,313 | 2.1 / 5.5 | 100% | 202 | 17.4 | 1.17 | 0.63 | 0.53 | 0.45 | 0.04 | 1.11 |
| literature (Gutenberg) | 150 | 69,758 | 2.4 / 5.9 | 100% | 195 | 20.5 | 0.10 | 0.80 | 1.09 | 0.23 | 0.09 | 2.14 |

Release notes are the densest category so far, ahead of arXiv abstracts (CI
p50 10.0): a quarter get "advise" or "block", almost all from stacked nouns
(7.5 per 1,000 words) in short changelog items such as component and feature
names. Nineteenth-century fiction and essays sit at the bottom, with almost no
stacked nouns (0.10). Long dependencies are highest in court opinions (1.53)
and regulation (1.39), which also have the longest sentences.

### Stack Exchange: edited against original

100 pairs, one unit each; edited minus original; two-sided Wilcoxon on the
paired differences. "Edited lower" is the share of pairs where the edited
text has the lower value.

| Measure | Original median | Edited median | Median diff | Edited lower | Same | p |
| --- | --- | --- | --- | --- | --- | --- |
| findings per 1k words | 2.45 | 2.65 | 0 | 33% | 38% | 0.90 |
| cost index | 1.38 | 1.89 | 0 | 34% | 37% | 0.72 |
| ms per word | 203 | 204 | -0.2 | 52% | 1% | 0.36 |
| words per sentence | 16.6 | 17.3 | +0.3 | 28% | 8% | <0.001 |
| words | 259 | 388 | +64 | 7% | 8% | <0.001 |

Edits do not change readcost's scores: findings, cost index and predicted
reading time are flat, overall and on each site (cost index p from 0.20 to
0.93). What edits do is add text: the edited answer is longer in 85 of 100
pairs (median +64 words; unix +127, softwareengineering +91, cs +37, math
+15), and sentences get slightly longer (+0.3 words, p < 0.001; significant
on softwareengineering alone, p = 0.005).

### Group comparisons

Medians of texts with 100+ words; Mann-Whitney U for two groups, otherwise
Kruskal-Wallis.

| Comparison | Cost index | Findings per 1k | Words/sentence | p (CI) |
| --- | --- | --- | --- | --- |
| Stack Exchange answers, high vs low score | 2.55 vs 0 | 3.85 vs 0 | 17.9 vs 18.5 | 0.01 |
| Design docs: Go, Kubernetes, Rust | 4.8, 5.7, 2.7 | 5.8, 6.7, 3.6 | 18.8, 16.1, 17.7 | <0.001 |
| Rust RFCs by start year: 2014-15, 2016-18, 2019-26 | 2.4, 2.0, 3.8 | 3.5, 2.8, 4.8 | 17.1, 17.6, 18.1 | <0.001 |
| MDN guide vs reference | 4.1 vs 4.1 | 5.2 vs 5.4 | 18.2 vs 17.3 | 0.93 |
| Man pages, Linux vs OpenBSD | 7.3 vs 5.7 | 8.3 vs 7.1 | 16.7 vs 15.6 | 0.14 |
| Release notes, auto-generated vs curated | 11.8 vs 10.1 | 13.2 vs 10.7 | 10.8 vs 11.8 | 0.53 |
| Regulation, Federal Register vs UK explanatory notes | 6.4 vs 3.8 | 8.5 vs 5.0 | 23.4 vs 25.3 | <0.001 |
| Literature, essay vs novel | 3.6 vs 1.9 | 5.9 vs 2.5 | 26.9 vs 17.5 | <0.001 |
| Social-science abstracts: economics, history, psychology, sociology | 10.9, 2.9, 5.6, 10.6 | 13.1, 5.3, 7.7, 13.8 | 24.7, 26.1, 21.3, 23.0 | <0.001 |
| Featured Articles: arts, biography, history | 3.4, 2.6, 2.8 | 4.9, 3.9, 3.7 | 22.7, 22.6, 23.3 | 0.13 |

MDN guides and reference pages score the same on findings, but guides have
shorter words (4.56 against 4.86 letters) and 12 ms less predicted time per
word (p < 0.001). Economics and sociology abstracts score like arXiv
abstracts (stacked nouns 6.0 and 4.5 per 1,000 words at the median); history
abstracts have none at the median.

### Combined manifest

`$REF/broad/ALL.jsonl` lists every text in every corpus: 10,953 texts, 3.6 MB,
one line each with `path` (absolute), `format`, `category`, `source`,
`licence`, `corpus`, `id`, `tokens` and `words`. Total: 5,688,012 readcost
words (6,940,563 whitespace tokens). It includes the original eval corpus
(1,491 texts, 817k words), the first broad samples (arXiv, READMEs,
expert-lay: 1,698 texts), the corpora above (2,322 texts), and the
`people` and `ai` corpora described next (5,442 texts,
1.25 million words). `words` comes from each corpus's own scoring cache, so
the eval corpus's counts are from the readcost version that scored it.

### Surprises and limits

- Edits to Stack Exchange answers add text without changing readcost's
  scores. Revision 1 is often a short first answer, so a pair is closer to
  "first draft against grown answer" than to "same answer copy-edited".
- High-scored answers have more findings than low-scored ones (cost index
  2.55 against 0), but low-scored answers are short (median 139 words against
  349), and a short text often has no finding at all. Length, not quality,
  probably drives this; the comparison is not length-matched.
- Auto-generated release notes do not score worse than curated ones (p =
  0.53); both are dense lists of names. Only 21 auto-generated releases
  survived the 50-word floor, since link-only lines are removed.
- MDN guides and reference pages do not differ in findings, despite
  different audiences. Eight of the 100 reference pages came from guide
  paths (the `page-type` decides, not the path); learning-area assessments count as
  guides.
- Newer Rust RFCs (2019 on) score higher than earlier ones (cost index 3.8
  against 2.0 to 2.4); the number spacing gives 2014 and 2015 57 of the 148
  RFCs.
- Man page DESCRIPTION sections are terse: 65 of 99 sampled Linux section 3
  pages were under 150 words. Option tags (`-f`) stay in the text as words.
- MedlinePlus summaries are stored as HTML and read with readcost's HTML
  reader; their high inline-list rate (3.72) comes from bulleted symptom
  lists.
- The cs site's answers have a median cost index of 0: with `[MATH]` tokens
  and short sentences, few rules fire.
- Wikinews now states CC BY 4.0; older articles were contributed under 2.5.
  Gutenberg selection uses the catalog file (gutendex returned 503) and
  authors who died by 1945.

## Project communities and AI-written text

`scripts/fetch_people_text.py`, `scripts/fetch_ai_text.py` and
`scripts/eval_people_ai.py` (readcost `6be1918`, `Config()` defaults, fetched
2026-10-27) compare 5,271 texts in three ways. None of this text has a reuse
licence beyond the host's terms, so it is analysed locally and only
aggregates are reported; per-person figures are not published.

| Corpus | Texts | Matched against |
| --- | --- | --- |
| Issue and PR bodies, review and thread comments by 24 developers whose writing is widely respected | 658 | the same kinds of text from 32 random repositories with 200 to 5,000 stars (277) |
| Forum posts (Rust users and internals, discuss.python.org) and project wikis | 425 | community posts in the same forums |
| Agent-written PRs from AIDev v3 (Codex, Devin, Copilot, Cursor, Claude Code) | 400 | a human PR in the same repository |
| Agent PRs found live on GitHub in 2026 | 109 | the latest human PR in the same repository |
| Machine text from RAID, MAGE and M4 | 1,644 | the human text it was generated from, or one of the same domain |

Words per sentence (wps) and mean word length (mwl) are shown with each
result because both drive readcost's rules.

- Issue and PR bodies by the respected developers get fewer findings than the
  community baseline: a median of 1.35 against 8.84 per 1,000 words (321
  against 138 texts, p = 0.0002), and 219 against 240 predicted ms per word.
  Sentence length is the same (16.2 wps); their words are shorter (mwl 4.55
  against 4.72). Pooled per person or repository the gap holds (5.3 against
  8.4 findings per 1,000 words, p = 0.006). Review comments, thread comments
  and forum posts show no difference in findings. The spread among the
  respected developers is wide: from about 1 to about 25 findings per 1,000
  words.
- Agent-written PRs cost more than human PRs in the same repository: findings
  per 1,000 words 7.0 against 0 (medians, 333 pairs, p = 2e-6) and 275
  against 252 ms per word. They are longer (98 against 60 words), use shorter
  sentences (11.3 against 13.0 wps) and much longer words (mwl 5.52 against
  4.82), and have 3.0 more stacked nouns per 1,000 words. Every agent reads
  slower per word than its human pairs, from +7 ms (not significant) to +42
  ms. The live 2026 sample (93 pairs) shows no difference except shorter
  sentences.
- Machine text from the detection benchmarks reads as cheaper than its human
  source, the opposite of agent PRs: RAID 202 against 205 ms per word (268
  pairs), M4 206 against 213 with fewer findings but shorter texts (695
  pairs). MAGE shows no pooled difference, and its generators split both
  ways at 25 pairs each: OPT-13B and GPT-NeoX read slower than their human
  text, the generators MAGE labels only "13B" and "65B" faster.

The two AI results point different ways because the texts are different:
agent PRs describe code changes in identifiers and compressed noun phrases,
while the benchmark generations are essays, news and reviews written to
imitate their human source. Limits: matching is by repository, source or
domain, not by length; about 700 comparisons were run without correction, so
p above 0.001 is suggestive; the respected side is what search returned for
each handle, the community side the latest activity in random repositories;
the RAID sample covers three domains and six models.

## Agents editing in a loop

One check says what is wrong once. An agent that edits, checks and edits
again can do other things: converge, swap one finding for another, cycle,
lengthen the text to dilute the rate, or drift from the facts.
`scripts/eval_agent_loop.py` runs that loop on 40 paragraphs of real
writing with two or more findings each (commits, docs, essays, discussion,
READMEs), for up to six rounds or until readcost finds nothing. Each model
gets each paragraph twice: with `-o agent` as it is now ("rewrite these
sentences where the finding holds", with each rule's measured precision),
and with the older plain wording ("rewrite these sentences", no
precision). A separate judge (Kimi K3.1 Pro) then lists facts the final
text lost, added or changed against the original. Changes are medians of
final over original; six loops ended on an empty reply and count as not
converged.

| Model | Feedback | Converged | Median rounds | Words | Total reading time | Time per word | New findings per loop | Returning per loop | Facts lost or changed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Opus 5.5 | holds | 26/40 | 2 | +3.4% | +2.3% | -1.5% | 0.40 | 0 | 4/40 |
| Claude Opus 5.5 | plain | 37/40 | 1 | +3.3% | +1.9% | -2.2% | 0.12 | 0 | 2/40 |
| Gemini 4 Argon | holds | 37/40 | 1 | +3.3% | +2.3% | -2.1% | 0.25 | 0 | 3/40 |
| Gemini 4 Argon | plain | 40/40 | 1 | +2.9% | +2.2% | -1.4% | 0.40 | 0 | 4/40 |
| DeepSeek V4.1 Flash | holds | 38/40 | 1 | +1.3% | +1.6% | -1.8% | 0.23 | 0 | 4/40 |
| DeepSeek V4.1 Flash | plain | 38/40 | 1 | +0.0% | +1.0% | -1.6% | 0.10 | 0 | 2/40 |
| Mistral Large 4 | holds | 39/40 | 1 | +0.5% | +0.9% | -1.0% | 0.30 | 0.10 | 4/40 |
| Mistral Large 4 | plain | 39/40 | 1 | +1.1% | +1.2% | -1.1% | 0.25 | 0.05 | 4/40 |

Most loops end after one rewrite. The text grows a little, so the total
predicted reading time rises 1 to 2% even as the time per word falls;
rewrites introduce 0.1 to 0.4 new findings per loop on average, and old
findings rarely come back. The judge finds a lost or changed fact in 5 to 10% of loops,
about as often with either wording. The hedged wording changes behaviour
mainly for Claude Opus 5.5, which leaves findings it judges wrong: it stops
short of zero findings in 14 of 40 loops instead of 3, without losing more
facts.

The loops that never end are of two kinds. A fixed point: the model judges
the findings do not hold and returns the paragraph unchanged, round after
round (three Gemini loops on inline lists). A two-cycle: the model
alternates between two wordings around a finding it cannot fix, here a
hyphenated CSS class name written without backticks, which readcost reads
as a coined compound (114 and 118 words, six rounds). An agent or hook that
loops on readcost's feedback should stop when the text stops changing or
when the same findings come back, and treat what remains as findings to
judge, not to chase.

Each loop was judged once by one model; the fact counts are small and only
indicative. The paragraphs had two or more findings to start with, so
these loops are short; a longer document could take more rounds.

## Not yet evaluated

The corpus above covers edited essays and documentation, READMEs, Hacker News
and Stack Overflow discussion, code comments from two standard libraries, Go
commit messages, model rewrites of human paragraphs, two reading-time and
two difficulty datasets, sentence ratings by teachers, learner essays, human
simplifications and PEPs. Not covered:

- Agent replies and Claude Code transcripts (chat answers to questions are
  above).
- Human labels of findings: every finding label here comes from model raters,
  which agree only modestly (Fleiss' kappa 0.23 over ten, 0.40 over eight).
  The human data above rates sentences or rewrites them, not readcost's
  findings. No study has checked that readers understand a rewrite faster or
  better.
- Issue threads (pull request descriptions and review comments are above).
- API references, docstrings at scale, man pages, CLI help and error messages.
- Changelogs, release notes, ADRs, and design documents other than PEPs.
- Commit messages outside the Go project's conventions.
- Professional writing by non-native writers: the learner essays above are
  short student essays.
- Reading time on technical prose: the model was fitted and tested on
  newspaper, popular-science and fiction passages.

## Limits

- Every rater is a model. Ten raters from different labs agree only modestly
  (Fleiss' kappa 0.23 over ten, 0.40 over the eight that are not lenient; see
  Ten raters); no person has labelled the sample.
- The sample is 210 findings from the essay and docs categories; commit,
  README, code and discussion findings were not labeled.
- The corpus is curated for quality. It cannot show how well the rules
  separate model text from human text.
- Filters reparse each sentence alone, which can differ slightly from the
  parse inside the document.
- Recent posts (2026) are included; their authors may have used writing
  tools.
- Each count is from one run of a deterministic pipeline; there is no
  variance to report, but a different sample seed would give different
  labeled examples.

## References

- Gordon, Hendrick and Johnson 2001. Memory interference during language
  processing. Journal of Experimental Psychology: Learning, Memory, and
  Cognition 27(6), doi 10.1037/0278-7393.27.6.1411.
- Liu, Li, Xu, Wang, Yuan and Yang 2025. Evaluating text generation quality
  using spectral distances of surprisal. Findings of EMNLP 2025.
- Meister, Pimentel, Haller, Jäger, Cotterell and Levy 2021. Revisiting the
  uniform information density hypothesis. EMNLP; arXiv 2109.11635.

Notes on these and the other papers cited here are in
[docs/papers](papers/).
