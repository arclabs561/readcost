# readcost with Vale

Vale and readcost check different things, so a docs repository can run both.

| | Vale | readcost |
| --- | --- | --- |
| What it checks | Your style guide: terms, phrases, capitalization, house rules | Sentence constructions tied to slower reading, and predicted reading time |
| How | Rules you write or install (Google, Microsoft, Red Hat and other packages): patterns, word lists, part-of-speech sequences | A dependency parse of each sentence (spaCy) and a model fitted to eye-tracking data |
| Rules it cannot express | | House style and terminology |

Vale has no parse of which word depends on which, so it cannot measure how far
a subject is from its verb or find an object relative without "that".
readcost does not know your terminology or your style guide. Vale can call an
external NLP server (`NLPEndpoint` in `.vale.ini`), but only for sentence
splitting and part-of-speech tags, not for rules, so readcost runs beside Vale
rather than inside it.

## In CI

One workflow, two steps. Vale's official action posts its findings through
reviewdog; readcost's action annotates the lines it flags and can post one
summary comment.

```yaml
name: prose
on: pull_request

permissions:
  contents: read
  pull-requests: write   # readcost's comment: "true"

jobs:
  prose:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
        with:
          fetch-depth: 0
      - uses: vale-cli/vale-action@518a9136acc6e6668ce7c00d367051e0941e87ff # v3.0.0
        with:
          files: docs
      - uses: arclabs561/readcost@main   # pin a commit SHA in real use
        with:
          paths: README.md docs
          comment: "true"
```

A minimal `.vale.ini` for the Google developer documentation style:

```ini
StylesPath = .github/styles
MinAlertLevel = suggestion
Packages = Google

[*.md]
BasedOnStyles = Vale, Google
```

readcost can also write SARIF (`readcost check -o sarif`) for GitHub code
scanning, and it has a language server for editors (`readcost lsp`).

## Where they overlap

Vale's Readability package computes grade-level formulas for a whole
document; readcost points at sentences instead. If a Vale package and readcost
both report the same sentence and the duplicate is noise, turn one rule off:
`rule = "ignore"` under `[readcost.rules]`, or the rule's level in Vale.

None of the snippets above have been run in a live repository yet; the action
inputs come from `vale-cli/vale-action`'s `action.yml` at v3.0.0 and readcost's
own `action.yml`.
