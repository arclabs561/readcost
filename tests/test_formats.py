"""Jupyter notebooks, comment syntax for more languages, and code readcost cannot read."""

import json

import pytest

from readcost import Analyzer, Config
from readcost.extract import detect_format, extract

STACK = ("For store restart measurement, the example prints first snapshot query cost "
         "with persisted sidecars present.")


def texts(segments):
    return [s.text for s in segments]


def spans_match(src, segments):
    """Every segment's offsets point at its own words in the file."""
    for s in segments:
        a = s.span(0, len(s.text))
        assert a is not None, s.text
        first_word = s.text.split()[0]
        assert src[a[0]:a[1]].startswith(first_word), (s.text, src[a[0]:a[1]])


# --------------------------------------------------------------- languages

DOC = "Returns the cached value for the given key name here."
PLAIN = "Look up the value in the shared cache before going to disk."

LANGS = {
    "a.php": f"""<?php
/**
 * {DOC}
 */
#[Attribute]
function get($key) {{
    // {PLAIN}
    # {PLAIN}
    /* {PLAIN} */
    return 1;
}}
""",
    "a.lua": f"""--- {DOC}
-- The next line of the same doc comment keeps going on.
local function get(key)
  -- {PLAIN}
  --[[ {PLAIN} ]]
  return key
end
""",
    "a.hs": f"""{{-# LANGUAGE OverloadedStrings #-}}
module A where

-- | {DOC}
-- The next line of the same doc comment keeps going on.
get :: Int -> Int
get x = x
-- {PLAIN}
{{- {PLAIN} -}}
""",
    "a.ex": f'''defmodule A do
  @moduledoc """
  {DOC}

  ## Examples

      iex> A.get(1)
  """

  @doc "{DOC}"
  def get(key) do
    # {PLAIN}
    key
  end
end
''',
    "a.jl": f'''"""
    get(key)

{DOC}
"""
function get(key)
    # {PLAIN}
    #= {PLAIN} =#
    s = """
    An assigned string is not a docstring, even with these words.
    """
    return key
end
''',
    "a.R": f"""#' {DOC}
#' @param key the key
get <- function(key) {{
  # {PLAIN}
  key
}}
""",
    "a.dart": f"""/// {DOC}
int get(int key) {{
  // {PLAIN}
  return key;
}}
""",
    "a.zig": f"""//! {DOC}
/// {DOC}
pub fn get(key: u32) u32 {{
    // {PLAIN}
    return key;
}}
""",
    "a.pl": f"""#!/usr/bin/perl
# {PLAIN}
sub get {{ return 1; }}

=head1 DESCRIPTION

Returns the B<cached> value for C<$key>, as L<the manual|perlpod> says here.

    my $x = get(1);

=begin html

<p>This html paragraph is skipped entirely by the reader.</p>

=end html

=cut
""",
}


@pytest.mark.parametrize("name", sorted(LANGS))
def test_doc_comments_are_read_and_other_comments_only_with_all(name):
    src = LANGS[name]
    assert detect_format(name, src) == "source"
    doc = extract(src, name, comments="doc")
    every = extract(src, name, comments="all")
    assert doc, name
    assert not any(PLAIN in t for t in texts(doc)), texts(doc)
    assert not any(s.kind for s in doc)
    inline = [s for s in every if s.kind == "inline-comment"]
    assert inline and all(PLAIN in s.text for s in inline), texts(every)
    spans_match(src, every)
    # Code, pragmas, attributes, assigned strings and the #! line stay out.
    joined = " ".join(texts(every))
    for code in ("LANGUAGE", "Attribute", "return", "iex>", "assigned string", "usr/bin", "html paragraph"):
        assert code not in joined, (name, code)


def test_haddock_and_ldoc_continuation_lines_join_the_doc_comment():
    for name in ("a.hs", "a.lua"):
        (seg,) = [s for s in extract(LANGS[name], name) if DOC in s.text]
        assert "keeps going on" in seg.text


def test_pod_formatting_codes():
    (seg,) = extract(LANGS["a.pl"], "a.pl")
    assert seg.text.startswith("Returns the cached value for")
    assert "the manual says" in seg.text and "B<" not in seg.text
    assert seg.codes and "$key" in next(iter(seg.codes.values()))
    assert seg.line_at(0) == 7


def test_elixir_heredoc_is_dedented_markdown():
    segs = extract(LANGS["a.ex"], "a.ex")
    assert texts(segs) == [DOC, DOC]  # the heading and the iex> example are not prose
    assert [s.line_at(0) for s in segs] == [3, 10]


def test_existing_languages_keep_their_rules():
    # Swift, Kotlin and Scala were already read as C-family code.
    for name in ("a.swift", "a.kt", "a.scala"):
        assert detect_format(name) == "source"
    src = f"// {PLAIN}\nlet x = 1\n"
    (seg,) = extract(src, "a.swift")
    assert seg.kind == ""  # read by default, as before, so not lowered


def test_shebang_line_is_not_a_comment():
    src = f"#!/bin/bash\n# {PLAIN}\necho hi\n"
    assert texts(extract(src, "run.sh")) == [PLAIN]


# --------------------------------------------------------------- unknown code

def test_unknown_code_extension_is_not_read_as_prose():
    notes = []
    assert detect_format("a.lisp") == "code"
    assert extract("(defun f () \"the user session token cache\")\n", "a.lisp", notes=notes) == []
    assert notes and "nothing was checked" in notes[0]
    # --format text still reads it.
    assert extract("one two three four five words here", "a.lisp", "text")


def test_scripts_without_an_extension_are_recognised_by_their_shebang():
    py = f'#!/usr/bin/env python3\n"""{DOC}"""\nx = 1\n'
    assert detect_format("tool", py) == "source"
    assert texts(extract(py, "tool")) == [DOC]
    assert detect_format("tool", "#!/usr/bin/env tclsh\nputs hi\n") == "code"


def test_prose_files_stay_text():
    prose = "These are plain notes about the release that we wrote by hand.\n"
    assert detect_format("notes", prose) == "text"
    assert detect_format("notes.txt", "#!/not/a/script\n" + prose) == "text"
    assert detect_format("NOTES.text", prose) == "text"
    assert detect_format("Dockerfile", "FROM alpine\n") == "source"


# --------------------------------------------------------------- notebooks

def notebook(cells, language="python", **dump):
    nb = {"cells": cells, "metadata": {"kernelspec": {"language": language, "name": "k"}},
          "nbformat": 4, "nbformat_minor": 5}
    return json.dumps(nb, indent=1, **dump) + "\n"


def md(*lines):
    return {"cell_type": "markdown", "metadata": {}, "source": list(lines)}


def code(*lines, outputs=()):
    return {"cell_type": "code", "metadata": {}, "execution_count": 1,
            "outputs": list(outputs), "source": list(lines)}


def file_position(src, needle):
    """1-based (line, column) of ``needle`` in the file."""
    i = src.index(needle)
    return src.count("\n", 0, i) + 1, i - src.rfind("\n", 0, i)


@pytest.mark.parametrize("ascii_only", [True, False])
def test_notebook_findings_point_into_the_ipynb_file(ascii_only):
    src = notebook([
        md("# Title\n", "\n", 'A "quoted" café line with\ttabs here.\n'),
        md("Intro.\n", "\n", STACK + "\n"),
    ], ensure_ascii=ascii_only)
    assert detect_format("nb.ipynb") == "notebook"
    r = Analyzer(Config()).check_text(src, None, "nb.ipynb")
    (f,) = [f for f in r.findings if f.feature == "stacked-nouns" and "store" in f.excerpt]
    assert (f.line, f.column) == file_position(src, "store restart")
    assert src[f.start:f.end] == f.excerpt
    segs = extract(src, "nb.ipynb")
    assert segs[0].text.startswith('A "quoted" café line')
    spans_match(src, segs)
    # An escaped character maps to its whole escape.
    seg = segs[0]
    k = seg.text.index('"')
    assert src[seg.starts[k]:seg.ends[k]] == '\\"'


def test_notebook_source_as_one_string_and_lines_after_it():
    cell = {"cell_type": "markdown", "metadata": {}, "source": "Intro line.\n\n" + STACK}
    src = notebook([cell])
    (seg,) = [s for s in extract(src, "nb.ipynb") if "store" in s.text]
    assert seg.line_at(0) == file_position(src, "Intro line")[0]  # one JSON line holds the cell
    a = seg.span(0, len(seg.text))
    assert src[a[0]:a[1]].startswith("For store")


def test_notebook_code_cells_need_comments_all_and_outputs_are_skipped():
    out = {"output_type": "stream", "name": "stdout",
           "text": ["The output stream buffer flush handler runs here now.\n"]}
    src = notebook([md(STACK + "\n"), code(f"# {PLAIN}\n", "x = 1\n", outputs=[out]),
                    {"cell_type": "raw", "metadata": {}, "source": [DOC]}])
    assert texts(extract(src, "nb.ipynb")) == [STACK]
    every = extract(src, "nb.ipynb", comments="all")
    assert texts(every) == [STACK, PLAIN]
    assert every[1].kind == "inline-comment"
    assert every[1].line_at(0) == file_position(src, PLAIN)[0]
    spans_match(src, every)


def test_notebook_kernel_language_picks_the_comment_syntax():
    src = notebook([code(f"#' {DOC}\n", f"# {PLAIN}\n", "f <- function(x) x\n")], language="R")
    segs = extract(src, "nb.ipynb", comments="all")
    assert [(s.text, s.kind) for s in segs] == [(DOC, ""), (PLAIN, "inline-comment")]
    nb = json.loads(src)
    del nb["metadata"]["kernelspec"]
    nb["metadata"]["language_info"] = {"name": "julia"}
    segs = extract(json.dumps(nb, indent=1), "nb.ipynb", comments="all")
    # Julia has no #' doc comments: both lines are one plain comment.
    assert [(s.text, s.kind) for s in segs] == [(f"' {DOC} {PLAIN}", "inline-comment")]


def test_notebook_with_an_unknown_kernel_language_skips_code_cells_with_a_note():
    notes = []
    src = notebook([md(STACK + "\n"), code(f"; {PLAIN}\n")], language="scheme")
    assert texts(extract(src, "nb.ipynb", comments="all", notes=notes)) == [STACK]
    assert notes == ["code cells not read: readcost has no comment syntax for the notebook's language 'scheme'"]


def test_nbformat_3_worksheets():
    nb = {"worksheets": [{"cells": [{"cell_type": "markdown", "source": [STACK]},
                                    {"cell_type": "code", "input": [f"# {PLAIN}\n"], "language": "python"}]}],
          "metadata": {"language": "python"}, "nbformat": 3}
    assert texts(extract(json.dumps(nb, indent=1), "nb.ipynb", comments="all")) == [STACK, PLAIN]


@pytest.mark.parametrize("bad", ['{"cells": [', "", "[1, 2]", '{"cells": 3}', '{"a": 1} x'])
def test_malformed_notebook_gives_a_note_not_a_crash(bad):
    r = Analyzer(Config()).check_text(bad, None, "nb.ipynb")
    assert r.words == 0 and not r.findings
    assert any("nothing was checked" in n for n in r.notes), r.notes


def test_notebook_through_the_command_line(tmp_path):
    from cliproc import run_cli

    p = tmp_path / "nb.ipynb"
    p.write_text(notebook([md("Intro.\n", "\n", STACK + "\n")]))
    out = run_cli(["check", "-o", "concise", str(p)], cwd=tmp_path)
    line, col = file_position(p.read_text(), "store restart")
    assert f"nb.ipynb:{line}:{col}: warn: [stacked-nouns]" in out.stdout


# --------------------------------------------------------------- inline comment severity

COMMENTED = """def build(items):
    # Initialize the result accumulator list before the main processing loop runs.
    return []
"""


def test_inline_comment_findings_are_info():
    r = Analyzer(Config(comments="all")).check_text(COMMENTED, None, "build.py")
    found = [f for f in r.findings if f.feature == "stacked-nouns"]
    assert found and all(f.severity == "info" for f in found)


def test_a_rule_level_set_in_config_still_wins_in_inline_comments():
    cfg = Config(comments="all", rules={"stacked-nouns": "warn"})
    r = Analyzer(cfg).check_text(COMMENTED, None, "build.py")
    found = [f for f in r.findings if f.feature == "stacked-nouns"]
    assert found and all(f.severity == "warn" for f in found)


def test_doc_comments_keep_their_severity():
    src = f'def build():\n    """{STACK}"""\n'
    r = Analyzer(Config(comments="all")).check_text(src, None, "build.py")
    assert any(f.feature == "stacked-nouns" and f.severity == "warn" for f in r.findings)


def test_notebook_positions_in_lsp_and_sarif():
    from readcost.lsp import to_diagnostics
    from readcost.report import sarif

    src = notebook([md("Intro é.\n", "\n", STACK + "\n")])
    r = Analyzer(Config()).check_text(src, None, "nb.ipynb")
    line, col = file_position(src, "store restart")
    (d,) = [d for d in to_diagnostics(r, src) if "store" in d.message]
    assert (d.range.start.line, d.range.start.character) == (line - 1, col - 1)
    regions = [res["locations"][0]["physicalLocation"]["region"]
               for res in json.loads(sarif([r]))["runs"][0]["results"]]
    assert any(reg["startLine"] == line and reg.get("startColumn") == col for reg in regions), regions
