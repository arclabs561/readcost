import asyncio
import re
import sys
from pathlib import Path

import pytest

from readcost.features import Finding

# The language server is an optional extra; skip these tests without pygls.
types = pytest.importorskip("lsprotocol.types")
LanguageClient = pytest.importorskip("pygls.lsp.client").LanguageClient
lsp = pytest.importorskip("readcost.lsp")
DOCS_URL, DOCUMENTED, Checker = lsp.DOCS_URL, lsp.DOCUMENTED, lsp.Checker
config_for, to_diagnostic = lsp.config_for, lsp.to_diagnostic

DENSE = ("We tune the shard compaction retry budget by hand. "
         "It does not own indexing, segment selection, compaction, or reader visibility.\n")
CLEAN = "The index stores one list per term.\n"


def finding(**kw) -> Finding:
    base = {"feature": "stacked-nouns", "severity": "warn", "message": "3 nouns stacked: 'retry budget cost'",
            "excerpt": "retry budget cost", "sentence": "", "path": "a.md", "line": 2,
            "suggestion": "Keep at most two nouns together."}
    return Finding(**(base | kw))


def test_diagnostic_fields_follow_the_finding():
    lines = ["Intro.", "We cut the retry budget cost in half."]
    d = to_diagnostic(finding(), lines)
    assert d.source == "readcost" and d.code == "stacked-nouns"
    assert d.message == "3 nouns stacked: 'retry budget cost'. Keep at most two nouns together."
    assert d.code_description.href == DOCS_URL
    # The excerpt's span on line 2 (0-based line 1), not the whole line.
    assert (d.range.start.line, d.range.start.character) == (1, 11)
    assert (d.range.end.line, d.range.end.character) == (1, 11 + len("retry budget cost"))


@pytest.mark.parametrize("severity,expected", [
    ("info", types.DiagnosticSeverity.Information),
    ("warn", types.DiagnosticSeverity.Warning),
    ("error", types.DiagnosticSeverity.Error),
])
def test_severity_map(severity, expected):
    assert to_diagnostic(finding(severity=severity), ["", "x"]).severity == expected


def test_columns_count_utf16_units():
    # The emoji is one code point but two UTF-16 units; LSP counts UTF-16 by default.
    lines = ["", "\N{GRINNING FACE} retry budget cost"]
    d = to_diagnostic(finding(), lines)
    assert (d.range.start.character, d.range.end.character) == (3, 20)
    d8 = to_diagnostic(finding(), lines, types.PositionEncodingKind.Utf8)
    assert (d8.range.start.character, d8.range.end.character) == (5, 22)


def test_whole_line_without_an_excerpt_and_line_clamped():
    lines = ["First line.", "Second line here."]
    d = to_diagnostic(finding(excerpt="", line=2), lines)
    assert (d.range.start.character, d.range.end.character) == (0, len(lines[1]))
    # Line 0 (record formats) and lines past the end land on a real line.
    assert to_diagnostic(finding(line=0), lines).range.start.line == 0
    assert to_diagnostic(finding(line=99), lines).range.start.line == 1
    assert to_diagnostic(finding(line=1), []).range.start.line == 0


def test_no_message_suffix_and_no_link_for_undocumented_feature():
    d = to_diagnostic(finding(feature="long-sentence", suggestion=""), ["", "x"])
    assert d.message == "3 nouns stacked: 'retry budget cost'" and d.code_description is None


def test_documented_features_match_readme_table():
    readme = (Path(__file__).parents[1] / "README.md").read_text()
    section = readme.split("## What it flags", 1)[1].split("\n## ", 1)[0]
    rows = set(re.findall(r"^\| ([a-z][a-z-]+)(?: \([^)]*\))? \|", section, re.MULTILINE))
    assert rows == DOCUMENTED


def write_repo(root: Path) -> None:
    (root / ".git").mkdir()  # find_config stops at the repository root
    (root / "readcost.toml").write_text('[readcost.hooks]\npaths = ["*.md", "*.py"]\nexclude = ["drafts/*"]\n')
    (root / "docs").mkdir()
    (root / "drafts").mkdir()


def test_config_found_from_document_path_and_globs_applied(tmp_path, monkeypatch):
    monkeypatch.delenv("READCOST_CONFIG", raising=False)
    monkeypatch.chdir(Path(__file__).parent)  # cwd elsewhere: lookup must start at the document
    write_repo(tmp_path)
    cfg, wanted = config_for(str(tmp_path / "docs" / "guide.md"))
    assert wanted and cfg.source == str(tmp_path / "readcost.toml")
    assert config_for(str(tmp_path / "src.py"))[1]
    assert not config_for(str(tmp_path / "notes.txt"))[1]          # not in hooks.paths
    assert not config_for(str(tmp_path / "drafts" / "idea.md"))[1]  # hooks.exclude


def test_checker_formats_by_extension_and_skips_unselected(tmp_path, monkeypatch):
    monkeypatch.delenv("READCOST_CONFIG", raising=False)
    write_repo(tmp_path)
    checker = Checker()
    md = checker.check(str(tmp_path / "docs" / "a.md"), DENSE)
    assert md is not None and {f.feature for f in md.findings} >= {"stacked-nouns"}
    # In a .py file the same prose is a string literal, which source format leaves
    # out; read as Markdown it would be a paragraph with findings.
    py = checker.check(str(tmp_path / "a.py"), f"x = {DENSE.strip()!r}\n")
    assert py is not None and py.findings == []
    assert checker.check(str(tmp_path / "drafts" / "a.md"), DENSE) is None


def test_checker_shares_one_model_across_configs(tmp_path, monkeypatch):
    monkeypatch.delenv("READCOST_CONFIG", raising=False)
    a, b = tmp_path / "a", tmp_path / "b"
    for root, extra in ((a, ""), (b, 'enable = ["nominalization"]\n')):
        root.mkdir()
        (root / ".git").mkdir()
        (root / "readcost.toml").write_text(extra)
    checker = Checker()
    checker.check(str(a / "x.md"), CLEAN)
    checker.check(str(b / "x.md"), CLEAN)
    first, second = checker._analyzers.values()
    assert first is not second and first.nlp is second.nlp


def test_server_publishes_diagnostics_over_stdio(tmp_path):
    """Start `readcost lsp`, open a document, and read back its diagnostics."""
    write_repo(tmp_path)
    doc = tmp_path / "docs" / "notes.md"
    doc.write_text(DENSE)
    uri = doc.as_uri()

    async def run() -> list[types.PublishDiagnosticsParams]:
        client = LanguageClient("test", "0")
        received: asyncio.Queue = asyncio.Queue()

        @client.feature(types.TEXT_DOCUMENT_PUBLISH_DIAGNOSTICS)
        def on_diagnostics(params: types.PublishDiagnosticsParams) -> None:
            received.put_nowait(params)

        await client.start_io(sys.executable, "-m", "readcost", "lsp", cwd=str(tmp_path))
        try:
            await client.initialize_async(types.InitializeParams(
                capabilities=types.ClientCapabilities(), root_uri=tmp_path.as_uri()))
            client.initialized(types.InitializedParams())
            client.text_document_did_open(types.DidOpenTextDocumentParams(
                text_document=types.TextDocumentItem(uri=uri, language_id="markdown", version=1, text=DENSE)))
            opened = await asyncio.wait_for(received.get(), 60)
            client.text_document_did_change(types.DidChangeTextDocumentParams(
                text_document=types.VersionedTextDocumentIdentifier(uri=uri, version=2),
                content_changes=[types.TextDocumentContentChangeWholeDocument(text=CLEAN)]))
            changed = await asyncio.wait_for(received.get(), 60)
            await client.shutdown_async(None)
            client.exit(None)
        finally:
            # On a failed assertion the server never got `exit`; stop() would wait on it forever.
            if client._server is not None and client._server.returncode is None and not client.stopped:
                await asyncio.sleep(1)
                if client._server.returncode is None:
                    client._server.kill()
            await client.stop()
        return [opened, changed]

    opened, changed = asyncio.run(run())
    assert opened.uri == uri and opened.version == 1
    assert "stacked-nouns" in {d.code for d in opened.diagnostics}
    assert all(d.source == "readcost" for d in opened.diagnostics)
    assert changed.version == 2 and list(changed.diagnostics) == []
