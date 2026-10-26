import json

from readcost.extract import CODE, detect_format, extract


def test_markdown_drops_code_tables_headings_and_keeps_lines():
    md = "\n".join([
        "# Title",                       # 1
        "",                              # 2
        "The index stores postings for every term in the corpus.",  # 3
        "",                              # 4
        "```rust",                       # 5
        "let x = index.search(query);",  # 6
        "```",                           # 7
        "",                              # 8
        "| a | b |",                     # 9
        "|---|---|",                     # 10: a pipe line alone is a paragraph, not a table
        "- Call `search` with a query",  # 11
        "  and read the [docs](https://example.com) first.",  # 12
    ])
    segs = extract(md, "README.md")
    texts = [s.text for s in segs]
    assert texts[0] == "The index stores postings for every term in the corpus."
    assert segs[0].line_at(0) == 3
    assert texts[1] == f"Call {CODE} with a query and read the docs first."
    assert segs[1].line_at(texts[1].index("read")) == 12
    assert not any("let x" in t or "| a" in t for t in texts)


def test_markdown_suppression_comments():
    md = "Normal prose sentence here to keep.\n\n<!-- readcost: ignore -->\nThis paragraph is ignored entirely by the tool.\n\n" \
         "<!-- readcost: off -->\nOff paragraph one is skipped here.\n<!-- readcost: on -->\n\nBack on with this final sentence."
    texts = [s.text for s in extract(md, "x.md")]
    assert texts == ["Normal prose sentence here to keep.", "Back on with this final sentence."]


def test_front_matter_and_setext_heading_skipped():
    md = "---\ntitle: x\n---\nHeading text\n============\n\nBody sentence with enough words."
    assert [s.text for s in extract(md, "x.md")] == ["Body sentence with enough words."]


def test_rst_skips_directives_and_literal_blocks():
    rst = "Title\n=====\n\nThe parser reads the file once::\n\n    code here\n\n.. note::\n\n   directive body\n\nFinal sentence of prose here."
    texts = [s.text for s in extract(rst, "doc.rst")]
    assert texts[0].startswith("The parser reads the file once")
    assert "code here" not in " ".join(texts) and "directive body" not in " ".join(texts)
    assert texts[-1] == "Final sentence of prose here."


def test_html_skips_pre_and_headings():
    html = "<h1>Title</h1>\n<p>The cache keeps <code>N</code> entries per host.</p>\n<pre>code block</pre>\n<p>Second paragraph of plain prose.</p>"
    texts = [s.text for s in extract(html, "page.html")]
    assert texts == [f"The cache keeps {CODE} entries per host.", "Second paragraph of plain prose."]


def test_rust_doc_comments_only_by_default():
    src = "/// Returns the number of documents in the index.\n/// It never blocks.\nfn len() {}\n// internal note about the loop counter here\n"
    segs = extract(src, "lib.rs")
    assert [s.text for s in segs] == ["Returns the number of documents in the index. It never blocks."]
    assert segs[0].line_at(0) == 1
    all_segs = extract(src, "lib.rs", comments="all")
    assert any("internal note" in s.text for s in all_segs)


def test_python_docstrings():
    src = 'def f():\n    """Compute the score for one document and return it."""\n    return 1\n'
    segs = extract(src, "m.py")
    assert segs[0].text == "Compute the score for one document and return it."
    assert segs[0].line_at(0) == 2


def test_commit_message_drops_comments_and_trailers():
    msg = "Fix the reader so it stops at EOF\n\nThe reader looped when the file ended early.\n\nSigned-off-by: A <a@b>\n# Please enter the commit message\n"
    texts = [s.text for s in extract(msg, "COMMIT_EDITMSG")]
    assert texts == ["Fix the reader so it stops at EOF", "The reader looped when the file ended early."]


def test_transcript_jsonl_assistant_text_only():
    lines = [
        {"type": "user", "message": {"role": "user", "content": "Explain the cache to me please."}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "The cache keeps one entry per URL for a day."},
            {"type": "tool_use", "name": "Read", "input": {}}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "Entries expire after the TTL you set."}]}},
    ]
    text = "\n".join(json.dumps(l) for l in lines)
    segs = extract(text, "t.jsonl")
    assert [s.text for s in segs] == ["The cache keeps one entry per URL for a day.", "Entries expire after the TTL you set."]
    assert segs[0].label == "line2"
    last = extract(text, "t.jsonl", last_only=True)
    assert [s.text for s in last] == ["Entries expire after the TTL you set."]


def test_messages_json_and_field_path():
    msgs = {"messages": [{"role": "user", "content": "hi there friend"},
                         {"role": "assistant", "content": "The answer is in the second table below."}]}
    assert [s.text for s in extract(json.dumps(msgs), "m.json")] == ["The answer is in the second table below."]
    rec = "\n".join(json.dumps({"id": i, "response": f"Response number {i} has four words."}) for i in range(2))
    segs = extract(rec, "out.jsonl", field_path="response")
    assert len(segs) == 2 and segs[1].text == "Response number 1 has four words."


def test_detect_format():
    assert detect_format("README.md") == "markdown"
    assert detect_format(".git/COMMIT_EDITMSG") == "commit"
    assert detect_format("a/b.rs") == "source"
    assert detect_format("x.jsonl") == "transcript"
    assert detect_format("notes") == "text"
