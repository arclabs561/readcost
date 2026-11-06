"""Language server: publish readcost findings as editor diagnostics.

``readcost lsp`` speaks the Language Server Protocol over stdin and stdout.
It checks a document when it is opened or saved, and again shortly after the
user stops typing. Analysis runs on one worker thread so that a long document
never stalls the protocol loop, and every document shares one loaded spaCy
model per model name.
"""

from __future__ import annotations

import asyncio
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lsprotocol import types
from pygls.lsp.server import LanguageServer
from pygls.uris import to_fs_path

from . import __version__
from .config import Config, load_config
from .engine import Analyzer, Result
from .extract import detect_format
from .features import Finding

SOURCE = "readcost"
SEVERITY = {
    "info": types.DiagnosticSeverity.Information,
    "warn": types.DiagnosticSeverity.Warning,
    "error": types.DiagnosticSeverity.Error,
}
# Features with a row in the README's "What it flags" table. long-sentence has
# none; test_lsp checks this set against the README.
DOCUMENTED = frozenset({
    "stacked-nouns", "long-dependency", "inanimate-subject", "reduced-object-relative",
    "hyphen-compound", "inline-list", "nominalization", "participial-clause", "undefined-acronym",
})
DOCS_URL = "https://github.com/arclabs561/readcost#what-it-flags"
CHANGE_DELAY = 0.5  # seconds of no typing before a changed document is checked again


def _units(text: str, encoding: str) -> int:
    """Length of ``text`` in the client's position units (UTF-16 unless negotiated)."""
    if encoding == types.PositionEncodingKind.Utf8:
        return len(text.encode("utf-8"))
    if encoding == types.PositionEncodingKind.Utf32:
        return len(text)
    return len(text.encode("utf-16-le")) // 2


def to_diagnostic(f: Finding, lines: list[str],
                  encoding: str = types.PositionEncodingKind.Utf16) -> types.Diagnostic:
    """One finding as a diagnostic: the excerpt's span when it sits on the line, else the whole line."""
    row = min(max(f.line - 1, 0), max(len(lines) - 1, 0))
    text = lines[row] if lines else ""
    start, end = 0, _units(text, encoding)
    col = text.find(f.excerpt) if f.excerpt else -1
    if col >= 0:
        start = _units(text[:col], encoding)
        end = start + _units(f.excerpt, encoding)
    message = f"{f.message}. {f.suggestion}" if f.suggestion else f.message
    return types.Diagnostic(
        range=types.Range(start=types.Position(line=row, character=start),
                          end=types.Position(line=row, character=end)),
        message=message,
        severity=SEVERITY.get(f.severity, types.DiagnosticSeverity.Information),
        code=f.feature,
        code_description=types.CodeDescription(href=DOCS_URL) if f.feature in DOCUMENTED else None,
        source=SOURCE,
    )


def to_diagnostics(result: Result, text: str,
                   encoding: str = types.PositionEncodingKind.Utf16) -> list[types.Diagnostic]:
    lines = text.splitlines()
    return [to_diagnostic(f, lines, encoding) for f in result.findings]


def config_for(path: str) -> tuple[Config, bool]:
    """The config that applies to ``path`` and whether its hooks.paths/exclude select the file.

    Globs are matched against the path relative to the config file's
    directory, as they are for ``readcost check`` run from the repository root.
    """
    cfg = load_config(start=str(Path(path).parent))
    root = Path(cfg.source).resolve().parent if cfg.source else Path(path).resolve().parent
    try:
        rel = os.path.relpath(Path(path).resolve(), root)
    except ValueError:  # different drive on Windows
        rel = Path(path).name
    return cfg, cfg.wants(rel)


class Checker:
    """Analyzers keyed by their settings; spaCy models shared by model name."""

    def __init__(self) -> None:
        self._analyzers: dict[str, Analyzer] = {}
        self._models: dict[str, object] = {}

    def analyzer(self, cfg: Config) -> Analyzer:
        key = repr(cfg)
        found = self._analyzers.get(key)
        if found is None:
            found = Analyzer(cfg)
            if cfg.model not in self._models:
                self._models[cfg.model] = found.nlp
            found._nlp = self._models[cfg.model]
            self._analyzers[key] = found
        return found

    def check(self, path: str, text: str) -> Result | None:
        """Findings for ``text`` saved at ``path``, or None when the config leaves the file out."""
        cfg, wanted = config_for(path)
        if not wanted:
            return None
        return self.analyzer(cfg).check_text(text, detect_format(path, text), path)


class ReadcostServer(LanguageServer):
    def __init__(self) -> None:
        super().__init__("readcost", __version__)
        self.checker = Checker()
        # One worker: spaCy pipelines are not documented as thread-safe, and
        # serial checks keep memory flat.
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="readcost")
        self.pending: dict[str, asyncio.Task] = {}
        self.reported: set[str] = set()

    def schedule(self, uri: str, delay: float = 0.0) -> None:
        """Check ``uri`` after ``delay`` seconds, replacing any check still waiting."""
        old = self.pending.pop(uri, None)
        if old is not None:
            old.cancel()
        self.pending[uri] = asyncio.get_running_loop().create_task(self._check(uri, delay))

    async def _check(self, uri: str, delay: float) -> None:
        if delay:
            await asyncio.sleep(delay)
        path = to_fs_path(uri) if uri.startswith("file:") else None
        if path is None:
            return  # untitled buffers have no path, so no config or format
        doc = self.workspace.get_text_document(uri)
        text, version = doc.source, doc.version
        try:
            result = await asyncio.get_running_loop().run_in_executor(
                self.worker, self.checker.check, path, text)
        except (OSError, ValueError, RuntimeError) as exc:
            self._report(f"readcost: {exc}")
            return
        if self.pending.get(uri) is asyncio.current_task():
            del self.pending[uri]
        encoding = str(self.workspace.position_encoding or types.PositionEncodingKind.Utf16)
        diagnostics = to_diagnostics(result, text, encoding) if result else []
        self.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(uri=uri, version=version, diagnostics=diagnostics))

    def _report(self, message: str) -> None:
        """Show an error once (a missing spaCy model would otherwise repeat on every keystroke)."""
        self.window_log_message(types.LogMessageParams(type=types.MessageType.Error, message=message))
        if message not in self.reported:
            self.reported.add(message)
            self.window_show_message(types.ShowMessageParams(type=types.MessageType.Error, message=message))


def build_server() -> ReadcostServer:
    server = ReadcostServer()

    @server.feature(types.TEXT_DOCUMENT_DID_OPEN)
    async def did_open(ls: ReadcostServer, params: types.DidOpenTextDocumentParams) -> None:
        ls.schedule(params.text_document.uri)

    @server.feature(types.TEXT_DOCUMENT_DID_SAVE)
    async def did_save(ls: ReadcostServer, params: types.DidSaveTextDocumentParams) -> None:
        ls.schedule(params.text_document.uri)

    @server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
    async def did_change(ls: ReadcostServer, params: types.DidChangeTextDocumentParams) -> None:
        ls.schedule(params.text_document.uri, CHANGE_DELAY)

    @server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
    async def did_close(ls: ReadcostServer, params: types.DidCloseTextDocumentParams) -> None:
        uri = params.text_document.uri
        task = ls.pending.pop(uri, None)
        if task is not None:
            task.cancel()
        ls.text_document_publish_diagnostics(types.PublishDiagnosticsParams(uri=uri, diagnostics=[]))

    return server


def main() -> int:
    server = build_server()
    # pygls closes its output stream on `exit`; hand it a duplicate so the
    # interpreter's own stdout stays open for the CLI's final flush.
    with os.fdopen(os.dup(sys.stdout.fileno()), "wb") as out:
        server.start_io(sys.stdin.buffer, out)
    # As the protocol asks: 0 after a shutdown request, 1 when the client exits without one.
    return 0 if server.protocol._shutdown else 1
