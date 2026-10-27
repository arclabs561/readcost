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
one rule the majority disagreed with gains 6 more. The scripts are
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
  result with OPT-125M. The rise holds in all 13 sources, docs included, so
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
the trees' importance. Surprisal adds nothing on OneStop and makes Provo
worse, so readcost ships the lexical model, which needs neither torch nor a
language model.

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

## Contexts

The verdict thresholds (advise at 15, block at 30) were set on ten READMEs.
Following Alves et al. 2010, a threshold should sit at a high percentile of
good writing of the same kind. Cost index per text on the corpus (texts of
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
on a short file takes 0.74 s (median of 5; most of it loading spaCy), which
is what a hook pays per edit; a loaded Analyzer checks about 5,100 words per
second.

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
All five current models write answers that take longer per word to read than
the human answer to the same question (83 to 98% of questions), and longer in
total, because they are 1.5 to 4 times as long. readcost's construction counts
do not separate them: cost index and findings per 1,000 words are lower than
the human answers' or not different. The Wikipedia passages are dense; one in
five does not pass. The 2022 ChatGPT answers read faster per word than the
human ones, so the per-word cost is a property of current models, not of model
text as such.

## Not yet evaluated

The corpus above covers edited essays and documentation, READMEs, Hacker News
and Stack Overflow discussion, code comments from two standard libraries, Go
commit messages, model rewrites of human paragraphs, and two reading-time and
two difficulty datasets. Not covered:

- Agent replies and Claude Code transcripts (chat answers to questions are
  above).
- Human judgment: every label here comes from model raters, which agree only
  modestly (Fleiss' kappa 0.23 over ten, 0.40 over eight). No study has
  checked that readers understand a rewrite faster or better.
- Issue threads (pull request descriptions and review comments are above).
- API references, docstrings at scale, man pages, CLI help and error messages.
- Changelogs, release notes, design documents, ADRs and specifications.
- Commit messages outside the Go project's conventions.
- Writing by non-native English writers. Limits warns against treating
  findings as markers of authorship, but the rates in such writing are not
  measured.
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
