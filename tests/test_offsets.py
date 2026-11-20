"""Character offsets: every extractor maps segment text back to the file.

The first half checks the extractors alone on generated documents, so it
needs no parser. The second half checks findings end to end.
"""

import html
import json
import random
import re

import pytest

from readcost.engine import Analyzer, LineIndex
from readcost.extract import CODE, _align, extract
from readcost.report import render


# ----------------------------------------------------------- extractor properties

def check_segments(src: str, path: str, fmt: str | None = None, *, complete: bool = True) -> list:
    """Assert that each segment's map points at its own characters in ``src``."""
    segs = extract(src, path, fmt)
    for seg in segs:
        assert len(seg.starts) == len(seg.ends) == len(seg.text), (path, seg.text)
        last = 0
        for i, ch in enumerate(seg.text):
            a, b = seg.starts[i], seg.ends[i]
            if a < 0:
                assert b < 0
                assert ch == " " or not complete, (path, seg.text, i, ch)
                continue
            assert 0 <= a < b <= len(src), (path, seg.text, i)
            assert a >= last, f"offsets go backwards at {i} in {seg.text!r}"
            last = a
            piece = src[a:b]
            in_code = any(k <= i < k + len(CODE) for k in seg.codes)
            if in_code:
                k = max(k for k in seg.codes if k <= i)
                core = seg.codes[k].strip("`$ ")
                assert core[:3] in html.unescape(piece) or piece in seg.codes[k], (path, seg.codes[k], piece)
            else:
                assert piece == ch or piece == "\\" + ch or ch in html.unescape(piece), (path, seg.text, i, piece)
    return segs


WORDS = ("the index stores postings for every term naïve café users read Zoë's 日本語 notes when "
         "a shard is rebuilt from its source and nobody waits long").split()
INLINE = [
    lambda w: f"*{w}*", lambda w: f"**{w}**", lambda w: f"_{w}_", lambda w: f"~~{w}~~",
    lambda w: f"`{w}()`", lambda w: f"``a `{w}` b``", lambda w: f"[{w}](https://example.com/{w})",
    lambda w: f"[{w} docs](<https://example.com/a b> \"the {w} title\")", lambda w: f"[{w}][ref]",
    lambda w: f"![{w} picture](img/{w}.png)", lambda w: f"<https://example.com/{w}>",
    lambda w: f"{w} &amp; {w}", lambda w: f"{w}&nbsp;&mdash; {w}", lambda w: f"\\*{w}\\*",
    lambda w: f"<b>{w}</b>", lambda w: f"{w}[^1]", lambda w: f"{w}^[a note on {w} here]", lambda w: f"https://example.com/{w}.",
    lambda w: f"src/{w}.py", lambda w: f"#12 and {w}", lambda w: f"***{w}***", lambda w: f"$x_{w}$",
    lambda w: f"[**{w}** and `{w}`](https://example.com/q?{w}=1)", lambda w: f"({w})", lambda w: f"“{w}”",
]


def paragraph(rng: random.Random, inline=INLINE, width: int = 60) -> list[str]:
    """A paragraph of 12 to 40 words with markup, hard-wrapped; as lines."""
    words = []
    for _ in range(rng.randint(12, 40)):
        w = rng.choice(WORDS)
        words.append(rng.choice(inline)(w) if rng.random() < 0.3 else w)
    lines, line = [], ""
    for w in words:
        if line and len(line) + len(w) > width:
            lines.append(line + rng.choice(["", "", "  ", "\\"]))
            line = w
        else:
            line = f"{line} {w}".strip()
    return lines + [line + "."]


def markdown_doc(rng: random.Random) -> str:
    blocks = []
    for _ in range(rng.randint(2, 6)):
        lines = paragraph(rng)
        kind = rng.choice(["plain", "quote", "list", "nested", "numbered", "lazy"])
        if kind == "quote":
            lines = ["> " + l for l in lines]
        elif kind == "lazy":
            lines = ["> " + lines[0]] + lines[1:]
        elif kind == "list":
            lines = ["- " + lines[0]] + ["  " + l for l in lines[1:]]
        elif kind == "numbered":
            lines = ["1. " + lines[0]] + ["   " + l for l in lines[1:]]
        elif kind == "nested":
            lines = ["- outer item with four words", "", "  > " + lines[0]] + ["  > " + l for l in lines[1:]]
        blocks.append("\n".join(lines))
        if rng.random() < 0.3:
            blocks.append(rng.choice(["## A heading", "```\ncode here\n```", "| a | b |\n|---|---|\n| c | d |",
                                      "<!-- a comment -->", "<details><summary>More</summary>\n"
                                      "<p>Text inside an HTML block with &amp; and <code>x</code> in it.</p>\n</details>"]))
    return "\n\n".join(blocks) + "\n\n[ref]: https://example.com/ref\n[^1]: A footnote with enough words in it.\n"


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_markdown_maps_every_character(seed, newline):
    src = markdown_doc(random.Random(seed)).replace("\n", newline)
    assert check_segments(src, "doc.md")


RST_INLINE = [lambda w: f"*{w}*", lambda w: f"``{w}()``", lambda w: f":func:`{w}`", lambda w: f":py:class:`~pkg.{w}`",
              lambda w: f"`{w} page <https://example.com/{w}>`_", lambda w: f"**{w}**"]
PLAIN_INLINE = [lambda w: f"*{w}*", lambda w: f"`{w}()`", lambda w: f"[{w}](https://example.com/{w})",
                lambda w: f"**{w}**"]


def clean(lines: list[str]) -> list[str]:
    """Without the trailing spaces and backslashes that mark a Markdown hard break."""
    return [l.rstrip(" \\") for l in lines]


@pytest.mark.parametrize("seed", range(15))
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_rst_maps_every_character(seed, newline):
    rng = random.Random(seed)
    parts = ["Title\n=====", ""]
    for _ in range(3):
        parts += clean(paragraph(rng, RST_INLINE)) + ["", ".. note::", "   skipped directive text here", ""]
    parts += ["An example follows::", "", "    literal block", "", "After the block comes one more sentence."]
    assert check_segments("\n".join(parts).replace("\n", newline), "doc.rst")


@pytest.mark.parametrize("seed", range(15))
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_html_maps_every_character(seed, newline):
    rng = random.Random(seed)
    inline = [lambda w: f"<em>{w}</em>", lambda w: f"<code>{w}()</code>", lambda w: f"{w} &amp; {w}",
              lambda w: f'<a href="https://example.com/{w}">{w}</a>', lambda w: f"{w}&nbsp;&#8212; {w}",
              lambda w: f"<code>a &lt; {w}</code>"]
    body = ["<html><head><title>T</title><style>p { color: red }</style></head><body>", "<h1>Heading</h1>"]
    for _ in range(3):
        body += ["<p>"] + ["  " + l for l in clean(paragraph(rng, inline))] + ["</p>", "<pre>code</pre>"]
    body += ["<ul><li>One item with enough words in it.</li></ul>", "</body></html>"]
    assert check_segments("\n".join(body).replace("\n", newline), "page.html")


def comment_doc(rng: random.Random, style: str) -> tuple[str, str]:
    paras = [clean(paragraph(rng, PLAIN_INLINE)) for _ in range(2)]
    if style == "python":
        doc = paras[0] + [""] + ["    " + l for l in paras[1]]
        src = ['"""' + doc[0]] + doc[1:] + ['"""', "import os", "", "", "def f():",
               '    """' + paras[1][0]] + ["    " + l for l in paras[1][1:]] + ['    """', "    return os"]
        return "\n".join(src) + "\n", "mod.py"
    if style == "rust":
        src = ["//! " + l for l in paras[0]] + ["", "/// " + paras[1][0]] + ["///" + (" " + l if l else "")
                                                                             for l in paras[1][1:]]
        return "\n".join(src + ["fn f() {}"]) + "\n", "lib.rs"
    if style == "c":
        src = ["/**"] + [" * " + l for l in paras[0]] + [" */", "int f(void);"] + ["  // " + l for l in paras[1]]
        return "\n".join(src) + "\n", "f.c"
    return "\n".join(["key = 1"] + ["# " + l for l in paras[0]] + ["other = 2"]) + "\n", "conf.toml"


@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize("style", ["python", "rust", "c", "hash"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_source_comments_map_every_character(seed, style, newline):
    src, path = comment_doc(random.Random(seed), style)
    assert check_segments(src.replace("\n", newline), path)


@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_commit_and_text_map_every_character(seed, newline):
    rng = random.Random(seed)
    body = clean(paragraph(rng, PLAIN_INLINE))
    msg = "\n".join(["net/http: fix the naïve retry loop for every café user", ""] + body
                    + ["", "Signed-off-by: A Person <a@example.com>", "# a comment line"]).replace("\n", newline)
    segs = check_segments(msg, "COMMIT_EDITMSG")
    assert segs and msg[segs[0].starts[0]:].startswith("fix the")
    plain = "\n".join(clean(paragraph(rng, [str])) + ["", "  indented second paragraph of plain text here."])
    assert check_segments(plain.replace("\n", newline), "notes.txt")


def test_align_follows_escapes_and_character_references():
    raw = r"a \* b &amp; c &#x263A; d"
    text = "a * b & c ☺ d"
    starts, ends, cursor = _align(text, raw, 0)
    assert cursor == len(raw)
    assert [raw[a:b] for a, b in zip(starts, ends)] == \
        ["a", " ", r"\*", " ", "b", " ", "&amp;", " ", "c", " ", "&#x263A;", " ", "d"]


def test_python_docstring_with_an_escape_gets_no_offset_for_that_line():
    src = '"""First line of the module docstring here.\n\nA tab\\tseparates these two words here.\n"""\n'
    segs = check_segments(src, "m.py", complete=False)
    assert [s.span(0, 5) is not None for s in segs] == [True, False]


def test_docstring_after_a_line_continuation_keeps_its_place():
    src = '"""Usage of this script from a shell.\n\n    run --flag \\\n        value\n\nThe result goes to standard output.\n"""\n'
    segs = check_segments(src, "m.py")
    last = segs[-1]
    assert last.line_at(0) == 6
    assert src[last.starts[0]:last.ends[len(last.text) - 1]] == "The result goes to standard output."


def test_transcript_segments_have_no_offsets():
    line = json.dumps({"type": "assistant", "message": {"role": "assistant", "content": "The index stores every term."}})
    seg, = extract(line, "t.jsonl")
    assert seg.starts == [] and seg.span(0, 3) is None


def test_transcript_segments_carry_the_record_line():
    """Lines counted inside a message are not file lines; the record's line is."""
    records = [
        {"type": "user", "message": {"role": "user", "content": "Explain the cache."}},
        {"type": "assistant", "message": {"role": "assistant", "content": (
            "The cache keeps one entry per URL.\n\nEntries expire after the TTL you set.\n\n"
            "A purge removes them at once.")}},
        {"type": "user", "message": {"role": "user", "content": "And the index?"}},
        {"type": "assistant", "message": {"role": "assistant", "content": "The index stores every term."}},
    ]
    text = "\n".join(json.dumps(r) for r in records)
    segs = extract(text, "t.jsonl")
    assert [s.label for s in segs] == ["line2", "line2", "line2", "line4"]
    assert [s.line_at(0) for s in segs] == [2, 2, 2, 4]
    assert [s.line_at(len(s.text) - 1) for s in segs] == [2, 2, 2, 4]


def test_reference_followed_by_parentheses_is_not_a_destination():
    src = "See the [guide] (not a link) before the index stores a term.\n\n[guide]: https://example.com\n"
    seg, = check_segments(src, "a.md")
    a = seg.text.index("(not")
    assert src[seg.starts[a]:seg.ends[a + 3]] == "(not"


# ----------------------------------------------------------- findings end to end

@pytest.fixture(scope="module")
def analyzer():
    return Analyzer()


def words(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text)


def in_order(needles: list[str], hay: list[str]) -> bool:
    it = iter(hay)
    return all(w in it for w in needles)


def check_findings(analyzer, src: str, path: str, fmt: str | None = None, expect: int = 1) -> list:
    result = analyzer.check_text(src, fmt, path)
    assert len(result.findings) >= expect, [f.feature for f in result.findings]
    index = LineIndex(src)
    for f in result.findings:
        assert f.start is not None, (path, f.feature, f.excerpt)
        flagged = src[f.start:f.end]
        assert in_order(words(f.excerpt), words(flagged)), (f.excerpt, flagged)
        assert flagged == flagged.strip()
        assert f.sentence_start <= f.start < f.end <= f.sentence_end
        assert in_order(words(f.sentence), words(src[f.sentence_start:f.sentence_end]))
        assert (f.line, f.column) == index.position(f.start)
        assert (f.end_line, f.end_column) == index.position(f.end)
        assert index.line(f.line)[f.column - 1] == src[f.start]
    return result.findings


STACK = "source segment rebuilds"
SENTENCE = "Every write ends up forcing source segment rebuilds, which nobody in the team wanted."


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
@pytest.mark.parametrize("path, template", [
    ("a.md", "# Zoë's café ☕\n\nNaïve intro — 日本語 text first.\n\n{}\n"),
    ("a.md", "> A quote first.\n>\n> {}\n"),
    ("a.md", "1. One short item here.\n2. {}\n"),
    ("a.rst", "Title ☕\n=======\n\nSee :func:`naïve` first.\n\n{}\n"),
    ("a.html", "<html><body><h1>Café</h1>\n<p>Zoë &amp; co.</p>\n<p>{}</p></body></html>\n"),
    ("a.py", '"""Zoë\'s module.\n\n{}\n"""\n'),
    ("a.rs", "// é\n/// {}\nfn f() {{}}\n"),
    ("a.c", "/* é */\n/**\n * {}\n */\nint f(void);\n"),
    ("a.toml", "name = \"é\"\n# {}\nkey = 1\n"),
    ("COMMIT_EDITMSG", "core: fix the café retry loop\n\n{}\n"),
    ("a.txt", "Zoë's notes ☕\n\n{}\n"),
])
def test_exact_span_in_every_format(analyzer, path, template, newline):
    src = template.format(SENTENCE).replace("\n", newline)
    stack, = [f for f in check_findings(analyzer, src, path) if f.excerpt == STACK]
    assert src[stack.start:stack.end] == STACK
    assert src[stack.sentence_start:stack.sentence_end] == SENTENCE


@pytest.mark.parametrize("path, wrapped", [
    ("a.md", "Every write ends up forcing *source*\n**segment** rebuilds, which nobody in the team wanted.\n"),
    ("a.md", "> Every write ends up forcing source\n> segment rebuilds, which nobody in the team wanted.\n"),
    ("a.md", "- Every write ends up forcing source\n  segment rebuilds, which nobody in the team wanted.\n"),
    ("a.rs", "/// Every write ends up forcing source\n/// segment rebuilds, which nobody in the team wanted.\nfn f() {}\n"),
    ("a.py", '"""Module.\n\nEvery write ends up forcing source\nsegment rebuilds, which nobody in the team wanted.\n"""\n'),
    ("a.html", "<p>Every write ends up forcing source\n   <em>segment</em> rebuilds, which nobody in the team wanted.</p>\n"),
    ("a.txt", "Every write ends up forcing source\n  segment rebuilds, which nobody in the team wanted.\n"),
])
def test_wrapped_sentence_spans_two_lines(analyzer, path, wrapped):
    stack, = [f for f in check_findings(analyzer, wrapped, path) if f.feature == "stacked-nouns"]
    flagged = wrapped[stack.start:stack.end]
    assert flagged.startswith("source") and flagged.endswith("rebuilds") and "\n" in flagged
    assert stack.end_line == stack.line + 1


def test_span_covers_a_code_span_and_a_link(analyzer):
    src = ("The `Index` type, which the [storage team](https://example.com/the-team) wrote for the `v2` "
           "format last year after a long argument, serves queries.\n")
    dep, = [f for f in check_findings(analyzer, src, "a.md") if f.feature == "long-dependency"]
    assert src[dep.start:dep.end].startswith("type, which the [storage team](https://example.com/the-team)")
    assert "`v2`" in src[dep.start:dep.end]


TAIL = ", which the storage team wrote for the second format last year after a long argument, serves"


@pytest.mark.parametrize("path, code", [("a.md", "`Index`"), ("a.rst", ":class:`Index`"),
                                        ("a.html", "<code>Index</code>")])
def test_span_starting_at_code_covers_its_markup(analyzer, path, code):
    src = f"Today {code}{TAIL} queries."
    src = f"<p>{src}</p>" if path.endswith("html") else src + "\n"
    dep = next(f for f in check_findings(analyzer, src, path) if f.feature == "long-dependency")
    assert dep.excerpt.startswith("`Index`")
    assert src[dep.start:dep.end] == code + TAIL


def test_messages_have_no_offsets_and_json_says_null(analyzer):
    src = json.dumps({"role": "assistant", "content": SENTENCE})
    result = analyzer.check_text(src, "messages", "m.json")
    assert result.findings and all(f.start is None and f.end is None for f in result.findings)
    out = json.loads(render([result], "json"))[0]["findings"][0]
    assert out["start"] is None and out["end"] is None and "column" in out


def test_json_output_keeps_old_fields_and_adds_offsets(analyzer):
    src = "Intro.\n\n" + SENTENCE + "\n"
    result = analyzer.check_text(src, "markdown", "a.md")
    out = [f for f in json.loads(render([result], "json"))[0]["findings"] if f["feature"] == "stacked-nouns"][0]
    for key in ("feature", "severity", "message", "excerpt", "sentence", "path", "line", "label", "suggestion",
                "column", "end_line", "end_column", "precision"):
        assert key in out
    assert src[out["start"]:out["end"]] == STACK
    assert (out["line"], out["column"], out["end_line"], out["end_column"]) == (3, 29, 3, 29 + len(STACK))
    assert src[out["sentence_start"]:out["sentence_end"]] == SENTENCE


def test_sarif_region_is_exact_and_skips_the_byte_order_mark(analyzer):
    src = "﻿Zoë says " + SENTENCE[0].lower() + SENTENCE[1:] + "\n"
    result = analyzer.check_text(src, "markdown", "a.md")
    run = json.loads(render([result], "sarif"))["runs"][0]
    assert run["columnKind"] == "unicodeCodePoints"
    region = next(r for r in run["results"] if r["ruleId"] == "stacked-nouns")["locations"][0]["physicalLocation"]["region"]
    plain = src[1:]
    assert plain[region["charOffset"]:region["charOffset"] + region["charLength"]] == STACK
    assert plain.splitlines()[0][region["startColumn"] - 1:region["endColumn"] - 1] == STACK
    assert region["startLine"] == region["endLine"] == 1


def test_sarif_omits_char_offset_for_repaired_text(analyzer, tmp_path):
    p = tmp_path / "latin.md"
    p.write_bytes(("Caf\xe9 notes. " + SENTENCE + "\n").encode("latin-1"))
    result = analyzer.check_file(str(p))
    region = json.loads(render([result], "sarif"))["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"]
    assert "startColumn" in region and "charOffset" not in region


def test_sarif_without_offsets_is_the_line_alone(analyzer):
    result = analyzer.check_text(json.dumps({"role": "assistant", "content": SENTENCE}), "messages", "m.json")
    region = json.loads(render([result], "sarif"))["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"]
    assert region == {"startLine": 1}


def test_lsp_range_is_exact_across_lines_and_in_utf16(analyzer):
    pytest.importorskip("pygls")
    from lsprotocol import types

    from readcost.lsp import to_diagnostics

    src = "𝒳 café: every write ends up forcing source\r\nsegment rebuilds, which nobody in the team wanted.\r\n"
    result = analyzer.check_text(src, "markdown", "a.md")
    stack, = [d for d in to_diagnostics(result, src) if d.code == "stacked-nouns"]
    lines = src.split("\r\n")
    col16 = len(lines[0][:lines[0].index("source")].encode("utf-16-le")) // 2
    assert (stack.range.start.line, stack.range.start.character) == (0, col16)
    assert (stack.range.end.line, stack.range.end.character) == (1, len("segment rebuilds"))
    utf8, = [d for d in to_diagnostics(result, src, types.PositionEncodingKind.Utf8) if d.code == "stacked-nouns"]
    assert utf8.range.start.character == len(lines[0][:lines[0].index("source")].encode())


def test_full_and_concise_report_use_the_offsets(analyzer):
    src = "x\n\n> Every write ends up forcing source\n> segment rebuilds, which nobody in the team wanted.\n"
    result = analyzer.check_text(src, "markdown", "a.md")
    assert "a.md:3:31: warn: [stacked-nouns]" in render([result], "concise")
    full = render([result], "full")
    assert "3 | > Every write ends up forcing source" in full and "4 | > segment rebuilds" in full


def test_transcript_finding_is_reported_on_its_own_record(analyzer, tmp_path):
    """The same words in an earlier record must not be quoted in place of the finding."""
    phrase = "the storage engine page cache"
    records = [
        {"type": "summary", "summary": "s"},
        {"type": "system", "content": "x"},
        {"type": "user", "message": {"role": "user", "content": f"Tell me about {phrase} please."}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": (
            "Sure, here is an overview of the system.\n\n"
            f"The writes touch {phrase} first, and the readers come later.")}]}},
    ]
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    result = analyzer.check_file(str(path))
    stacked = [f for f in result.findings if "storage engine page cache" in f.excerpt]
    assert stacked, [f.excerpt for f in result.findings]
    assert {f.line for f in result.findings} == {4}
    shown = render([result], "full", color=False) if "color" in render.__code__.co_varnames else render([result], "full")
    assert "Tell me about" not in shown
    assert json.loads(render([result], "json"))

