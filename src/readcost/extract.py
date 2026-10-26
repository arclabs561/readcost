"""Turn documents into prose segments with source line numbers.

Every extractor yields ``Segment`` objects. A segment is one paragraph or
list item of prose, with code, tables, headings, link targets and markup
removed, plus anchors that map character offsets back to source lines so a
finding can point at ``file:line``.
"""

from __future__ import annotations

import ast
import bisect
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Iterator

from markdown_it import MarkdownIt
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.front_matter import front_matter_plugin

CODE = "Xcode"  # stands in for inline code; parsed as a proper noun

FORMATS = (
    "markdown", "text", "rst", "html", "source", "commit",
    "transcript", "messages", "jsonl",
)


@dataclass
class Segment:
    text: str
    path: str
    anchors: list[tuple[int, int]] = field(default_factory=list)  # (offset, line)
    label: str = ""  # e.g. "assistant[3]" for a message inside a transcript

    def line_at(self, offset: int) -> int:
        if not self.anchors:
            return 0
        offsets = [a[0] for a in self.anchors]
        i = bisect.bisect_right(offsets, offset) - 1
        return self.anchors[max(i, 0)][1]


# --------------------------------------------------------------- markdown

def _parser(front_matter: bool) -> MarkdownIt:
    md = MarkdownIt("commonmark").enable(["table", "strikethrough"])
    if front_matter:
        md.use(front_matter_plugin)
    # No spaces just inside the dollars and no digit after the closing one,
    # so "$5 and $10" stays text.
    return (md.use(footnote_plugin).use(deflist_plugin)
            .use(dollarmath_plugin, allow_space=False, allow_digits=False, double_inline=True))


_MD = _parser(front_matter=True)
_MD_PLAIN = _parser(front_matter=False)  # for a leading "---" that is not YAML

# A URL ends before trailing sentence punctuation or a closing bracket.
URL = re.compile(r"\b(?:https?|ftp)://[^\s<>\"'`]*[^\s<>\"'`.,;:!?)\]}](?P<close>\))?")
PATH_CANDIDATE = re.compile(r"(?<![\w/.~-])(?:(?:~|\.\.?)?/[\w.-]+(?:/[\w.-]+)*|[\w.-]+(?:/[\w.-]+)+)/?")
EXTENSION = re.compile(r"\.[A-Za-z][A-Za-z0-9]{0,7}$")
YAML_KEY = re.compile(r"^[^\s:#-][^:]*:(\s|$)")
YAML_LINE = re.compile(r"^(\s.*|#.*|-(\s.*)?|\.\.\.|[^\s:#-][^:]*:(\s.*)?)$")
IGNORE_NEXT = re.compile(r"readcost:\s*ignore", re.I)
OFF = re.compile(r"readcost:\s*off", re.I)
ON = re.compile(r"readcost:\s*on", re.I)


def _path(m: re.Match) -> str:
    """Replace a file path with CODE; leave word lists such as and/or or a/b/c."""
    whole = m.group()
    body = whole.rstrip(".")
    if body.startswith(("~/", "./", "../", "/")) or body.endswith("/") or EXTENSION.search(body):
        return CODE + whole[len(body):]
    return whole


def _url(m: re.Match) -> str:
    """Replace a URL with CODE; a closing paren belongs to it only if it opened one."""
    url, close = m.group(), m.group("close") or ""
    if close and url.count("(") >= url.count(")"):
        return CODE
    return CODE + close


def _plain(text: str) -> str:
    return PATH_CANDIDATE.sub(_path, URL.sub(_url, text))


def _is_yaml(body: str) -> bool:
    lines = [l for l in body.splitlines() if l.strip()]
    return bool(lines) and bool(YAML_KEY.match(lines[0])) and all(YAML_LINE.match(l) for l in lines)


def _inline_pieces(inline, line_no) -> list[tuple[str, int]]:
    """Prose pieces of one paragraph, each paired with its source line.

    The paragraph starts on ``inline.map[0]``; each soft or hard break moves
    to the next line. Code spans, math and raw HTML can also hold newlines.
    """
    first = inline.map[0]
    raw = inline.content  # the paragraph's source lines, container markers removed
    starts = [0] + [i + 1 for i, c in enumerate(raw) if c == "\n"]
    k, cursor, in_autolink = first, 0, False
    pieces: list[tuple[str, int]] = []
    for child in inline.children or []:
        kind = child.type
        if in_autolink:
            in_autolink = kind != "link_close"
        elif kind == "text":
            pieces.append((_plain(child.content), line_no(k)))
        elif kind in ("softbreak", "hardbreak"):
            k += 1
            pieces.append((" ", line_no(k)))
        elif kind == "code_inline":
            pieces.append((CODE, line_no(k)))
            # markdown-it folds newlines in a code span into spaces; count
            # them in the raw source instead.
            cursor = max(cursor, starts[min(k - first, len(starts) - 1)])
            opened = raw.find(child.markup, cursor)
            closed = raw.find(child.markup, opened + len(child.markup)) if opened >= 0 else -1
            if closed >= 0:
                k += raw.count("\n", opened, closed)
                cursor = closed + len(child.markup)
        elif kind in ("math_inline", "math_inline_double"):
            pieces.append((CODE, line_no(k)))
            k += child.content.count("\n")
        elif kind == "link_open" and child.markup == "autolink":
            pieces.append((CODE, line_no(k)))
            in_autolink = True
        elif kind == "image":
            k += sum(c.type in ("softbreak", "hardbreak") for c in child.children or [])
        elif kind == "html_inline":
            k += child.content.count("\n")
        # Emphasis, strikethrough, link markers and footnote references add no words.
    return pieces


def _segment(pieces: list[tuple[str, int]], path: str, label: str) -> Segment | None:
    chars: list[str] = []
    anchors: list[tuple[int, int]] = []
    for piece, line in pieces:
        for ch in piece:
            if ch.isspace():
                if chars and chars[-1] != " ":
                    chars.append(" ")
                continue
            if not anchors or anchors[-1][1] != line:
                anchors.append((len(chars), line))
            chars.append(ch)
    text = "".join(chars).rstrip()
    if len(text.split()) < 4:
        return None
    return Segment(text, path, anchors, label)


def _markdown(src: str, path: str, label: str, line_no) -> list[Segment]:
    tokens = _MD.parse(src)
    if tokens and tokens[0].type == "front_matter" and not _is_yaml(tokens[0].content):
        tokens = _MD_PLAIN.parse(src)
    segments: list[Segment] = []
    disabled = False
    ignore_level: int | None = None  # a readcost: ignore waits at this nesting level
    skip_level: int | None = None  # inside the block that ignore applies to
    for i, tok in enumerate(tokens):
        if skip_level is not None:
            if tok.level == skip_level and tok.nesting == -1:
                skip_level = None
            continue
        if tok.type == "html_block" and tok.content.lstrip().startswith("<!--"):
            # Comments, directives included, do not use up a pending ignore.
            if OFF.search(tok.content):
                disabled = True
            elif ON.search(tok.content):
                disabled = False
            elif IGNORE_NEXT.search(tok.content):
                ignore_level = tok.level
            continue
        if ignore_level is not None:
            if tok.level < ignore_level:
                ignore_level = None  # the container ended; nothing followed
            elif tok.level == ignore_level:
                ignore_level = None
                if tok.nesting == 1:
                    skip_level = tok.level
                continue
        if disabled or tok.type != "inline" or i == 0 or tokens[i - 1].type != "paragraph_open":
            continue  # headings, table cells and definition terms are not prose
        seg = _segment(_inline_pieces(tok, line_no), path, label)
        if seg:
            segments.append(seg)
    return segments


def markdown_lines(lines: Iterable[tuple[str, int]], path: str, label: str = "") -> list[Segment]:
    """Prose segments from (text, line number) pairs that together form Markdown."""
    lines = list(lines)
    numbers = [n for _, n in lines] or [0]
    src = "\n".join(t for t, _ in lines)
    return _markdown(src, path, label, lambda k: numbers[min(k, len(numbers) - 1)])


def extract_markdown(text: str, path: str, label: str = "") -> list[Segment]:
    return _markdown(text, path, label, lambda k: k + 1)


# --------------------------------------------------------------- plain text

def extract_text(text: str, path: str, label: str = "") -> list[Segment]:
    segments, parts = [], []

    def flush() -> None:
        if parts:
            body, anchors = "", []
            for piece, lineno in parts:
                if body:
                    body += " "
                anchors.append((len(body), lineno))
                body += piece
            if len(body.split()) >= 4:
                segments.append(Segment(body, path, anchors, label))
            parts.clear()

    for i, line in enumerate(text.splitlines()):
        if line.strip():
            parts.append((line.strip(), i + 1))
        else:
            flush()
    flush()
    return segments


# --------------------------------------------------------------- reStructuredText

RST_DIRECTIVE = re.compile(r"^\s*\.\.\s")
RST_UNDERLINE = re.compile(r"^\s*([=\-~^\"'`#*+:.])\1{2,}\s*$")
RST_TABLE = re.compile(r"^\s*(\+[-=+]+\+|=+(\s+=+)+)\s*$")
RST_ROLE = re.compile(r":[\w:-]+:`([^`]*)`")
RST_LINK = re.compile(r"`([^`<]+?)\s*<[^>]+>`_+")


def extract_rst(text: str, path: str, label: str = "") -> list[Segment]:
    out: list[tuple[str, int]] = []
    lines = text.splitlines()
    skip_indent: int | None = None
    for i, line in enumerate(lines):
        indent = len(line) - len(line.lstrip())
        if skip_indent is not None:
            if line.strip() and indent <= skip_indent:
                skip_indent = None
            else:
                continue
        if RST_DIRECTIVE.match(line):
            skip_indent = indent
            out.append(("", i + 1))
            continue
        if RST_UNDERLINE.match(line) or RST_TABLE.match(line):
            if out and out[-1][0].strip():
                out[-1] = ("", out[-1][1])  # previous line was a title
            out.append(("", i + 1))
            continue
        body = RST_ROLE.sub(lambda m: CODE, line)
        body = RST_LINK.sub(r"\1", body)
        body = re.sub(r"``[^`]+``", CODE, body)
        if body.rstrip().endswith("::"):
            body = body.rstrip()[:-1]
            skip_indent = indent
        out.append((body, i + 1))
    return markdown_lines(out, path, label)


# --------------------------------------------------------------- HTML

class _HTMLProse(HTMLParser):
    BLOCK = {"p", "li", "div", "section", "article", "blockquote", "td", "dd", "dt", "br", "tr"}
    SKIP = {"script", "style", "pre", "nav", "header", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "table", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[tuple[str, int]] = []
        self.skip = 0
        self.in_code = 0
        self.buffer: list[str] = []
        self.start_line = 1

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(self.buffer)).strip()
        if text:
            self.lines.append((text, self.start_line))
        self.lines.append(("", self.start_line))
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "code":
            self.in_code += 1
            if not self.skip:
                self.buffer.append(f" {CODE} ")
        elif tag in self.BLOCK:
            self._flush()
            self.start_line = self.getpos()[0]

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag == "code":
            self.in_code = max(0, self.in_code - 1)
        elif tag in self.BLOCK:
            self._flush()

    def handle_data(self, data):
        if self.skip or self.in_code:
            return
        if not "".join(self.buffer).strip():
            self.start_line = self.getpos()[0]
        self.buffer.append(data)


def extract_html(text: str, path: str, label: str = "") -> list[Segment]:
    parser = _HTMLProse()
    parser.feed(text)
    parser._flush()
    return markdown_lines(parser.lines, path, label)


# --------------------------------------------------------------- source comments

LANG_BY_EXT = {
    ".rs": "rust", ".py": "python", ".pyi": "python", ".go": "c", ".js": "c",
    ".mjs": "c", ".cjs": "c", ".ts": "c", ".tsx": "c", ".jsx": "c", ".c": "c",
    ".h": "c", ".cc": "c", ".cpp": "c", ".hpp": "c", ".java": "c", ".kt": "c",
    ".swift": "c", ".scala": "c", ".cs": "c", ".sh": "hash", ".bash": "hash",
    ".rb": "hash", ".toml": "hash", ".yaml": "hash", ".yml": "hash",
}
CODEISH = re.compile(r"[;{}]\s*$|^\s*(let|fn|def|return|import|use|if|for|while|pub|var|const)\b|=>|::|\(\)\s*$")


def _comment_blocks(lines: list[str], prefixes: tuple[str, ...]) -> Iterator[list[tuple[str, int]]]:
    block: list[tuple[str, int]] = []
    for i, line in enumerate(lines):
        s = line.strip()
        prefix = next((p for p in prefixes if s.startswith(p)), None)
        if prefix is not None:
            body = s[len(prefix):]
            body = body[1:] if body.startswith(" ") else body
            block.append((body, i + 1))
        elif block:
            yield block
            block = []
    if block:
        yield block


def _block_comments(text: str) -> Iterator[list[tuple[str, int]]]:
    for m in re.finditer(r"/\*\*?(.*?)\*/", text, re.S):
        start_line = text.count("\n", 0, m.start()) + 1
        out = []
        for k, line in enumerate(m.group(1).splitlines()):
            out.append((re.sub(r"^\s*\*\s?", "", line), start_line + k))
        yield out


def extract_source(text: str, path: str, label: str = "", comments: str = "doc") -> list[Segment]:
    """Prose from comments. ``comments`` is "doc" (doc comments only) or "all"."""
    lang = LANG_BY_EXT.get(Path(path).suffix.lower(), "c")
    lines = text.splitlines()
    # Doc comments are Markdown: code in them sits in fences, which
    # markdown_lines skips. Plain comments often hold commented-out code, so
    # only they get the line-level CODEISH filter.
    blocks: list[list[tuple[str, int]]] = []
    plain: list[list[tuple[str, int]]] = []
    if lang == "python":
        try:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    body = getattr(node, "body", [])
                    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                            and isinstance(body[0].value.value, str):
                        first = body[0].lineno
                        doc = body[0].value.value.splitlines()
                        # Remove the docstring's own indent only, so an
                        # indented code block inside it stays code.
                        margin = min((len(l) - len(l.lstrip()) for l in doc[1:] if l.strip()),
                                     default=0)
                        margin = min(margin, body[0].col_offset)
                        doc = [l.strip() if k == 0 else l[margin:].rstrip() for k, l in enumerate(doc)]
                        blocks.append([(l, first + k) for k, l in enumerate(doc)])
        except SyntaxError:
            pass
        if comments == "all":
            plain.extend(_comment_blocks(lines, ("#",)))
    elif lang == "rust":
        blocks.extend(_comment_blocks(lines, ("///", "//!")))
        if comments == "all":
            plain.extend(_comment_blocks(lines, ("//",)))
    elif lang == "hash":
        plain.extend(_comment_blocks(lines, ("#",)))
    else:
        blocks.extend(_block_comments(text))
        plain.extend(_comment_blocks(lines, ("///", "//")))
    segments: list[Segment] = []
    for block in blocks:
        segments.extend(markdown_lines(block, path, label))
    for block in plain:
        prose = [(b, n) for b, n in block if not CODEISH.search(b) and not b.strip().startswith("#!")]
        segments.extend(markdown_lines(prose, path, label))
    return segments


# --------------------------------------------------------------- commit messages

def extract_commit(text: str, path: str, label: str = "") -> list[Segment]:
    kept = []
    for i, line in enumerate(text.splitlines()):
        if line.startswith("# ------------------------ >8"):
            break
        if line.startswith("#"):
            continue
        if re.match(r"^[\w-]+:\s", line) and i > 0:  # trailers: Signed-off-by:, Co-Authored-By:
            continue
        kept.append((line, i + 1))
    return markdown_lines(kept, path, label)


# --------------------------------------------------------------- LLM output

def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for block in content:
            if isinstance(block, str):
                out.append(block)
            elif isinstance(block, dict) and block.get("type") in ("text", "output_text") and isinstance(block.get("text"), str):
                out.append(block["text"])
        return "\n\n".join(out)
    return ""


def _get_path(obj, dotted: str):
    for key in dotted.split("."):
        if isinstance(obj, dict):
            obj = obj.get(key)
        elif isinstance(obj, list) and key.isdigit() and int(key) < len(obj):
            obj = obj[int(key)]
        else:
            return None
    return obj


def assistant_messages(text: str, fmt: str, field_path: str | None = None) -> list[tuple[str, str]]:
    """Return (label, text) for each assistant message, or each record's field."""
    out: list[tuple[str, str]] = []
    if fmt in ("transcript", "jsonl"):
        for n, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if field_path:
                value = _get_path(obj, field_path)
                if isinstance(value, (str, list)):
                    out.append((f"line{n}", _content_text(value)))
                continue
            # Claude Code transcript lines: {"type": "assistant", "message": {...}}
            msg = obj.get("message") if isinstance(obj.get("message"), dict) else obj
            role = msg.get("role") or obj.get("type")
            if role == "assistant":
                body = _content_text(msg.get("content"))
                if body.strip():
                    out.append((f"line{n}", body))
        return out
    data = json.loads(text)
    if field_path:
        items = data if isinstance(data, list) else [data]
        for k, item in enumerate(items):
            value = _get_path(item, field_path)
            if isinstance(value, (str, list)):
                out.append((f"item{k}", _content_text(value)))
        return out
    messages = []
    if isinstance(data, dict):
        if "messages" in data:
            messages = data["messages"]
        elif "choices" in data:  # OpenAI chat completion
            messages = [c.get("message", {}) for c in data["choices"]]
        elif data.get("role") == "assistant" or "content" in data:  # Anthropic message
            messages = [data]
    elif isinstance(data, list):
        messages = data
    for k, msg in enumerate(messages):
        if isinstance(msg, dict) and msg.get("role", "assistant") == "assistant":
            body = _content_text(msg.get("content"))
            if body.strip():
                out.append((f"assistant[{k}]", body))
    return out


# --------------------------------------------------------------- dispatch

def detect_format(path: str, text: str | None = None) -> str:
    name = Path(path).name
    suffix = Path(path).suffix.lower()
    if path == "-":
        return "markdown"
    if name in ("COMMIT_EDITMSG", "MERGE_MSG", "TAG_EDITMSG") or suffix == ".gitmessage":
        return "commit"
    if suffix in (".md", ".markdown", ".mdx", ".mdown"):
        return "markdown"
    if suffix == ".rst":
        return "rst"
    if suffix in (".html", ".htm", ".xhtml"):
        return "html"
    if suffix == ".jsonl":
        return "transcript"
    if suffix == ".json":
        return "messages"
    if suffix in LANG_BY_EXT:
        return "source"  # config files too: only their # comments are prose
    return "text"


def extract(text: str, path: str, fmt: str | None = None, *, field_path: str | None = None,
            last_only: bool = False, comments: str = "doc") -> list[Segment]:
    fmt = fmt or detect_format(path, text)
    if fmt == "markdown":
        return extract_markdown(text, path)
    if fmt == "text":
        return extract_text(text, path)
    if fmt == "rst":
        return extract_rst(text, path)
    if fmt == "html":
        return extract_html(text, path)
    if fmt == "source":
        return extract_source(text, path, comments=comments)
    if fmt == "commit":
        return extract_commit(text, path)
    if fmt in ("transcript", "jsonl", "messages"):
        msgs = assistant_messages(text, fmt, field_path)
        if last_only and msgs:
            msgs = msgs[-1:]
        segments: list[Segment] = []
        for label, body in msgs:
            segments.extend(extract_markdown(body, path, label))
        return segments
    raise ValueError(f"unknown format {fmt!r}; choose one of {', '.join(FORMATS)}")
