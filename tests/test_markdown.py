"""Markdown extraction: which text counts as prose and which line it came from.

Each test pins one requirement of the markdown-it-py extractor; several pin
defects found in the regex extractor it replaced.
"""

import json

from readcost.config import Config
from readcost.engine import Analyzer
from readcost.extract import CODE, extract, extract_source


def texts(md):
    return [s.text for s in extract(md, "x.md")]


def joined(md):
    return " ".join(texts(md))


# --------------------------------------------------------------- blocks

def test_list_item_continuation_paragraph_is_prose():
    md = "- The first item explains the cache.\n\n    The continuation paragraph explains eviction too.\n"
    assert texts(md) == ["The first item explains the cache.",
                         "The continuation paragraph explains eviction too."]


def test_blockquote_markers_are_removed():
    md = "> The quoted line has several words.\n> > The nested quote has more words.\n"
    # A nested quote starts a new block (CommonMark), so it is its own segment.
    assert texts(md) == ["The quoted line has several words.", "The nested quote has more words."]


def test_code_and_headings_inside_blockquotes_are_skipped():
    md = "> # Heading inside the quote here\n>\n> ```\n> let value = compute(input);\n> ```\n>\n> Quoted prose stays in the output.\n"
    assert texts(md) == ["Quoted prose stays in the output."]


def test_table_cells_and_headings_are_not_prose():
    md = "## A heading with four words\n\n| Column one here | Column two here |\n|---|---|\n| cell text with words | more cell words here |\n\nThe paragraph after the table stays.\n"
    assert texts(md) == ["The paragraph after the table stays."]


def test_pipe_table_without_leading_pipe_is_not_prose():
    md = "Name of thing | What the thing does\n--- | ---\nreader one | reads every file twice\n\nThe paragraph after the table stays.\n"
    assert texts(md) == ["The paragraph after the table stays."]


def test_fenced_and_indented_code_are_skipped():
    md = ("Intro paragraph has four words.\n\n~~~\ntilde fenced code is skipped here\n~~~\n\n"
          "    indented code block is skipped too\n\nClosing paragraph has four words.\n")
    assert texts(md) == ["Intro paragraph has four words.", "Closing paragraph has four words."]


def test_html_pre_script_and_comment_blocks_are_skipped():
    md = ("<pre>\nfirst line of preformatted text here\n\nsecond line after a blank line\n</pre>\n\n"
          "<script>\nvar words = 'script body is not prose at all';\n\nvar more = 1;\n</script>\n\n"
          "<!--\nA comment that spans lines is not prose.\n\nNor is its second paragraph here.\n-->\n\n"
          "Only this paragraph is prose here.\n")
    assert texts(md) == ["Only this paragraph is prose here."]


def test_thematic_breaks_at_file_start_are_not_front_matter():
    md = "---\n\nThe intro paragraph sits between two rules.\n\n---\n\nThe second paragraph follows the rule.\n"
    assert texts(md) == ["The intro paragraph sits between two rules.",
                         "The second paragraph follows the rule."]


def test_real_front_matter_is_skipped():
    md = "---\ntitle: Guide\ntags:\n  - docs\n---\n\nThe body sentence has enough words.\n"
    segs = extract(md, "x.md")
    assert [s.text for s in segs] == ["The body sentence has enough words."]
    assert segs[0].line_at(0) == 7


def test_definition_bodies_are_prose_and_terms_are_not():
    md = "Cache entry\n: One stored response keyed by its request URL.\n"
    assert texts(md) == ["One stored response keyed by its request URL."]


def test_footnote_markers_drop_and_footnote_bodies_are_prose():
    md = "The index stores postings for each term.[^1]\n\n[^1]: Postings are lists of document ids.\n"
    assert texts(md) == ["The index stores postings for each term.",
                         "Postings are lists of document ids."]


# --------------------------------------------------------------- inline

def test_code_span_is_one_placeholder_word():
    assert texts("Run `make test. now` before you push the branch.\n") == \
        [f"Run {CODE} before you push the branch."]


def test_url_is_one_placeholder_and_keeps_sentence_punctuation():
    assert texts("Read the guide at https://example.com/docs/guide. Then rebuild the index.\n") == \
        [f"Read the guide at {CODE}. Then rebuild the index."]


def test_url_inside_parentheses_keeps_the_closing_paren():
    assert texts("The service (see https://example.com/a_b) answers every request.\n") == \
        [f"The service (see {CODE}) answers every request."]


def test_autolink_is_one_placeholder():
    assert texts("Report problems at <https://example.com/issues> when they happen.\n") == \
        [f"Report problems at {CODE} when they happen."]


def test_file_path_is_one_placeholder():
    assert texts("Edit src/readcost/extract.py to change how prose is found.\n") == \
        [f"Edit {CODE} to change how prose is found."]


def test_slash_between_words_is_not_a_path():
    assert texts("The reader handles input/output errors on every call.\n") == \
        ["The reader handles input/output errors on every call."]


def test_inline_math_is_one_placeholder():
    assert texts("The cost grows as $n^2$ when the input doubles.\n") == \
        [f"The cost grows as {CODE} when the input doubles."]


def test_dollar_amounts_are_not_math():
    assert texts("The plan costs $5 and $10 per month for each seat.\n") == \
        ["The plan costs $5 and $10 per month for each seat."]


def test_link_text_kept_and_target_dropped_across_lines():
    md = "Read [the full\nguide](https://example.com/guide) before you start.\n"
    assert texts(md) == ["Read the full guide before you start."]


def test_images_and_emphasis_markup_are_removed():
    md = "The ![diagram](d.png) cache keeps **hot** entries in _memory_ now.\n"
    assert texts(md) == ["The cache keeps hot entries in memory now."]


# --------------------------------------------------------------- line numbers

def test_line_numbers_inside_a_multi_line_paragraph():
    md = "# Title\n\n- The first line of the item\n  continues on the second line\n  and ends on the third line.\n"
    seg = extract(md, "x.md")[0]
    assert seg.line_at(0) == 3
    assert seg.line_at(seg.text.index("second")) == 4
    assert seg.line_at(seg.text.index("third")) == 5


def test_line_numbers_after_hard_breaks_and_wrapped_code_spans():
    md = "The first line ends hard\\\nthen `a wrapped\ncode span` sits here\nand the last line follows.\n"
    seg = extract(md, "x.md")[0]
    assert seg.line_at(seg.text.index("then")) == 2
    assert seg.line_at(seg.text.index("sits")) == 3
    assert seg.line_at(seg.text.index("last")) == 4


def test_line_numbers_after_a_pre_block_with_blank_lines():
    md = "<pre>\none\n\ntwo\n</pre>\n\nThe paragraph after the block starts\non line seven and ends on line eight.\n"
    seg = extract(md, "x.md")[0]
    assert seg.line_at(0) == 7
    assert seg.line_at(seg.text.index("eight")) == 8


def test_finding_line_inside_a_quoted_wrapped_paragraph():
    md = ("Intro paragraph that is plain enough.\n\n"
          "> The example prints the first query time with\n"
          "> persisted region-index sidecars present versus after deleting\n"
          "> those sidecars and forcing source-segment rebuilds.\n")
    found = Analyzer(Config()).check_text(md, "markdown").findings
    stacked = [f for f in found if f.feature in ("stacked-nouns", "hyphen-compound")]
    assert stacked and all(f.line in (4, 5) for f in stacked), [(f.line, f.excerpt) for f in stacked]


# --------------------------------------------------------------- directives

def test_directive_inside_a_fence_is_code_not_a_directive():
    md = "```markdown\n<!-- readcost: off -->\n```\n\nThis prose after the fence stays checked.\n"
    assert texts(md) == ["This prose after the fence stays checked."]


def test_directive_inside_an_indented_code_block_is_ignored():
    md = "Intro paragraph has four words.\n\n    <!-- readcost: off -->\n\nThis prose after the code stays checked.\n"
    assert texts(md) == ["Intro paragraph has four words.", "This prose after the code stays checked."]


def test_ignore_before_a_heading_is_spent_on_the_heading():
    md = "<!-- readcost: ignore -->\n# A heading here\n\nThis paragraph after the heading stays.\n"
    assert texts(md) == ["This paragraph after the heading stays."]


def test_ignore_before_a_fence_is_spent_on_the_fence():
    md = "<!-- readcost: ignore -->\n```\ncode\n```\n\nThis paragraph after the fence stays.\n"
    assert texts(md) == ["This paragraph after the fence stays."]


def test_ignore_before_a_table_is_spent_on_the_table():
    md = "<!-- readcost: ignore -->\n| a | b |\n|---|---|\n| c | d |\n\nThis paragraph after the table stays.\n"
    assert texts(md) == ["This paragraph after the table stays."]


def test_ignore_before_a_list_skips_the_whole_list():
    md = ("<!-- readcost: ignore -->\n- The first item has four words.\n- The second item has four words.\n\n"
          "This paragraph after the list stays.\n")
    assert texts(md) == ["This paragraph after the list stays."]


def test_off_and_on_still_work():
    md = ("Kept paragraph before the switch.\n\n<!-- readcost: off -->\n\nSkipped paragraph while it is off.\n\n"
          "- skipped list item while off\n\n<!-- readcost: on -->\n\nKept paragraph after the switch.\n")
    assert texts(md) == ["Kept paragraph before the switch.", "Kept paragraph after the switch."]


# --------------------------------------------------------------- embedded markdown

def test_doc_comment_markdown_uses_the_same_rules():
    src = ("/// Opens the index at the given path.\n"
           "///\n"
           "/// ```\n"
           "/// let index = Index::open(\"x\");\n"
           "/// ```\n"
           "///\n"
           "/// See https://docs.rs/index. Then call search.\n"
           "fn open() {}\n")
    segs = extract_source(src, "lib.rs")
    assert [s.text for s in segs] == ["Opens the index at the given path.",
                                      f"See {CODE}. Then call search."]
    assert segs[1].line_at(0) == 7


def test_chat_message_markdown_uses_the_same_rules():
    body = "Run `make` first.\n\n```\nmake test\n```\n\nThe build writes to ./target/debug/app for you."
    line = json.dumps({"type": "assistant", "message": {"role": "assistant", "content": body}})
    assert [s.text for s in extract(line, "t.jsonl")] == [f"The build writes to {CODE} for you."]


def test_indented_code_in_a_python_docstring_is_skipped():
    src = ('def build():\n    """Rebuild the profile from the reference files.\n\n'
           '        python3 scripts/build.py ref --out data/profile.json\n    """\n')
    segs = extract_source(src, "build.py")
    assert [s.text for s in segs] == ["Rebuild the profile from the reference files."]
    assert segs[0].line_at(0) == 2


def test_url_keeps_its_own_balanced_paren():
    assert texts("See https://en.wikipedia.org/wiki/Foo_(bar) for the details.\n") == \
        [f"See {CODE} for the details."]


def test_home_and_relative_paths_are_placeholders():
    assert texts("Copy ~/x and ../up/dir before you run the build.\n") == \
        [f"Copy {CODE} and {CODE} before you run the build."]
