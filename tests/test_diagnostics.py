"""The full (rustc-style) and concise outputs: where the caret lands and what each line says."""

import subprocess
import sys

from readcost import report
from readcost.engine import Result
from readcost.features import Finding


def run(args, stdin=None, env=None):
    return subprocess.run([sys.executable, "-m", "readcost", *args], input=stdin, check=False,
                          capture_output=True, text=True, env=env)


def finding(excerpt, sentence, line, severity="warn"):
    return Finding(feature="stacked-nouns", severity=severity, message="3 nouns stacked", excerpt=excerpt,
                   sentence=sentence, path="a.md", line=line, suggestion="Unpack it")


def caret(out: str, source_line: str) -> str:
    """The source text above the first caret line, as the caret marks it."""
    lines = out.splitlines()
    i = next(i for i, ln in enumerate(lines) if "^" in ln and ln.lstrip().startswith("|"))
    quoted, marks = lines[i - 1], lines[i]
    start = quoted.index("| ") + 2
    a, b = marks.index("^"), marks.rindex("^") + 1
    assert quoted[start:] == source_line
    return quoted[a:b]


def test_caret_marks_the_excerpt_in_the_source_line():
    src = "# Title\n\nWe rebuild the cache invalidation strategy file nightly.\n"
    f = finding("cache invalidation strategy file", "We rebuild the cache invalidation strategy file nightly.", 3)
    out = report.full([Result(path="a.md", findings=[f], source=src)])
    assert caret(out, "We rebuild the cache invalidation strategy file nightly.") == "cache invalidation strategy file"
    assert " --> a.md:3:16" in out
    assert "= help: Unpack it" in out


def test_caret_spans_markdown_emphasis_between_words():
    src = "We rebuild the **cache invalidation** strategy file nightly.\n"
    f = finding("cache invalidation strategy file", "We rebuild the cache invalidation strategy file nightly.", 1)
    out = report.full([Result(path="a.md", findings=[f], source=src)])
    assert caret(out, src.rstrip()) == "cache invalidation** strategy file"


def test_wrapped_excerpt_gets_a_caret_on_each_line():
    src = "We rebuild the cache invalidation\n  strategy file nightly.\n"
    f = finding("cache invalidation strategy file", "We rebuild the cache invalidation strategy file nightly.", 1)
    lines = report.full([Result(path="a.md", findings=[f], source=src)]).splitlines()
    assert "1 | We rebuild the cache invalidation" in lines
    assert "2 |   strategy file nightly." in lines
    marks = [ln for ln in lines if ln.startswith("  | ") and "^" in ln]
    assert [m.strip(" |").count("^") for m in marks] == [len("cache invalidation"), len("strategy file")]
    assert marks[1].index("^") == lines[lines.index("2 |   strategy file nightly.")].index("strategy")


def test_long_line_is_cropped_with_the_caret_still_under_the_excerpt():
    words = " ".join(f"word{i}" for i in range(40))
    src = f"{words} the cache invalidation strategy file {words}.\n"
    f = finding("cache invalidation strategy file", src.strip(), 1)
    out = report.full([Result(path="a.md", findings=[f], source=src)])
    quoted = next(ln for ln in out.splitlines() if ln.startswith("1 | "))
    assert quoted.startswith("1 | ...") and quoted.endswith("...")
    assert len(quoted) <= len("1 | ") + report._WIDTH + 6
    marks = next(ln for ln in out.splitlines() if "^" in ln)
    assert quoted[marks.index("^"):marks.rindex("^") + 1] == "cache invalidation strategy file"


def test_without_source_the_sentence_is_quoted_and_no_column_is_claimed():
    f = finding("strategy file", "The cache strategy file is stale.", 7)
    out = report.full([Result(path="a.md#3", findings=[f])])
    assert " --> a.md:7\n" in out
    marks = next(ln for ln in out.splitlines() if "^" in ln)
    quoted = next(ln for ln in out.splitlines() if "The cache" in ln)
    assert quoted[marks.index("^"):marks.rindex("^") + 1] == "strategy file"


def test_concise_is_one_grep_line_per_finding_with_a_column():
    src = "x\nWe rebuild the cache invalidation strategy file nightly.\n"
    f = finding("cache invalidation strategy file", src.splitlines()[1], 2)
    out = report.concise([Result(path="a.md", findings=[f], source=src)])
    assert out.splitlines()[0] == "a.md:2:16: warn: [stacked-nouns] 3 nouns stacked"


def test_colour_only_when_asked_and_no_color_wins(monkeypatch):
    f = finding("cache file", "The cache file is stale.", 1)
    r = Result(path="a.md", findings=[f], source="The cache file is stale.\n")
    assert "\x1b[" not in report.full([r])
    assert "\x1b[1;33mwarn[stacked-nouns]" in report.full([r], color=True)

    class Tty:
        def isatty(self):
            return True
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
    monkeypatch.setenv("TERM", "xterm")
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert report.use_color(Tty())
    assert not report.use_color(object())
    monkeypatch.setenv("NO_COLOR", "1")
    assert not report.use_color(Tty())
    assert report.use_color(Tty(), "always") and not report.use_color(Tty(), "never")


def test_cli_default_is_full_and_points_at_explain():
    text = "We tune the shard compaction retry budget by hand.\n"
    out = run(["check", "--fail-on", "never", "-"], stdin=text).stdout
    assert out.startswith("warn[stacked-nouns]: three or more nouns in a row\n --> <stdin>:1:19\n")
    assert "^^^^^^^^^^^^^^^^^^^^^^^ 3 nouns stacked\n" in out  # the specific finding sits at the carets
    assert "1 | We tune the shard compaction retry budget by hand." in out
    assert "\nMore on a rule: readcost explain stacked-nouns\n" in out
    assert "\x1b[" not in out  # a pipe is not a terminal
    concise = run(["check", "--fail-on", "never", "-o", "concise", "-"], stdin=text).stdout
    assert concise.startswith("<stdin>:1:")


def test_two_word_rules_mark_both_words_and_dash_the_gap():
    src = "The index, built once from every document, serves queries.\n"
    f = Finding(feature="long-dependency", severity="warn", message="'index' and 'serves' are 7 words apart",
                excerpt="index, built once from every document, serves", sentence=src.strip(), path="a.md", line=1)
    out = report.full([Result(path="a.md", findings=[f], source=src)])
    marks = next(ln for ln in out.splitlines() if "^" in ln)[4:]
    assert marks.strip() == "^^^^^" + "-" * len(", built once from every document, ") + "^^^^^^"


def test_readme_example_output_is_what_readcost_prints():
    # The README's "For example" block is the first output most readers see; keep it current.
    import re
    from pathlib import Path

    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text()
    m = re.search(r"For example, this sentence from a README:\n\n```text\n(.*?)```\n\n```text\n(.*?)```", readme, re.DOTALL)
    assert m, "README example blocks not found"
    out = run(["check", "--fail-on", "never", "--stdin-name", "notes.md", "-"], stdin=m.group(1)).stdout
    assert out == m.group(2)


def test_colour_changes_no_column(tmp_path):
    # Escape codes have no width; padding measured on coloured text misaligns the arrows.
    import re

    src = "x\nWe rebuild the cache invalidation strategy file nightly.\n"
    f = finding("cache invalidation strategy file", src.splitlines()[1], 2)
    r = Result(path="a.md", findings=[f], source=src)
    coloured = re.sub(r"\x1b\[[0-9;]*m", "", report.full([r], color=True))
    assert coloured == report.full([r])


def test_full_output_fits_80_columns():
    # A README code block or a narrow terminal shows 80 columns without scrolling.
    text = ("For store restart measurement, the example prints first snapshot-query cost\n"
            "with persisted WAND sidecars present versus after deleting those sidecars and\n"
            "forcing source-segment rebuilds. It does not own indexing, segment selection,\n"
            "compaction, or reader visibility.\n")
    out = run(["check", "--fail-on", "never", "--stdin-name", "notes.md", "-"], stdin=text).stdout
    assert out.count("-->") >= 3
    assert max(len(line) for line in out.splitlines()) <= 80


def test_why_and_example_once_per_rule_help_every_time():
    src = "We tune the shard compaction retry budget.\nWe skip the cache invalidation strategy file.\n"
    fs = [finding("shard compaction retry budget", src.splitlines()[0], 1),
          finding("cache invalidation strategy file", src.splitlines()[1], 2)]
    out = report.full([Result(path="a.md", findings=fs, source=src)])
    assert out.count("= why:") == 1 and out.count("= example:") == 1
    assert out.count("= help: Unpack it") == 2
    assert out.count("warn[stacked-nouns]: three or more nouns in a row\n") == 2
    assert out.count("^ 3 nouns stacked") == 2  # the label, not the headline, carries the specifics
