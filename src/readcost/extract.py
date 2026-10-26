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

FENCE = re.compile(r"^\s*(```|~~~)")
TABLE = re.compile(r"^\s*\|")
HEADING = re.compile(r"^\s*#{1,6}(\s|$)")
SETEXT = re.compile(r"^\s*(=+|-+)\s*$")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
REF_LINK = re.compile(r"\[([^\]]*)\]\[[^\]]*\]")
REF_DEF = re.compile(r"^\s*\[[^\]]+\]:\s*\S+")
HTML_TAG = re.compile(r"<[^>]+>")
URL = re.compile(r"https?://\S+")
INLINE_CODE = re.compile(r"`+[^`]+`+")
EMPHASIS = re.compile(r"(\*\*|__|\*|_)(?=\S)(.+?)(?<=\S)\1")
FOOTNOTE = re.compile(r"\[\^[^\]]+\]")
MATH = re.compile(r"\$[^$\n]+\$")
IGNORE_NEXT = re.compile(r"readcost:\s*ignore", re.I)
OFF = re.compile(r"readcost:\s*off", re.I)
ON = re.compile(r"readcost:\s*on", re.I)


def clean_inline(line: str) -> str:
    line = IMAGE.sub("", line)
    line = LINK.sub(r"\1", line)
    line = REF_LINK.sub(r"\1", line)
    line = FOOTNOTE.sub("", line)
    line = HTML_TAG.sub("", line)
    line = URL.sub("", line)
    line = INLINE_CODE.sub(CODE, line)
    line = MATH.sub(CODE, line)
    line = EMPHASIS.sub(r"\2", line)
    return line.strip()


def markdown_lines(lines: Iterable[tuple[str, int]], path: str, label: str = "") -> list[Segment]:
    """Group (text, line number) pairs of markdown into prose segments."""
    segments: list[Segment] = []
    parts: list[tuple[str, int]] = []
    in_fence = False
    in_html_comment = False
    disabled = False
    skip_next = False
    prev_blank = True

    def flush() -> None:
        nonlocal skip_next
        if parts:
            if skip_next:
                skip_next = False
            else:
                text, anchors = "", []
                for piece, lineno in parts:
                    if text:
                        text += " "
                    anchors.append((len(text), lineno))
                    text += piece
                if len(text.split()) >= 4:
                    segments.append(Segment(text, path, anchors, label))
            parts.clear()

    lines = list(lines)
    # YAML front matter at the very top.
    if lines and lines[0][0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j][0].strip() in ("---", "..."):
                lines = lines[j + 1:]
                break

    for idx, (raw, lineno) in enumerate(lines):
        stripped = raw.strip()
        if in_html_comment:
            if "-->" in raw:
                in_html_comment = False
            continue
        if stripped.startswith("<!--"):
            if OFF.search(stripped):
                disabled = True
            elif ON.search(stripped):
                disabled = False
            elif IGNORE_NEXT.search(stripped):
                flush()
                skip_next = True
            if "-->" not in stripped:
                in_html_comment = True
            continue
        if FENCE.match(raw):
            in_fence = not in_fence
            flush()
            prev_blank = False
            continue
        if in_fence or disabled:
            continue
        if not stripped:
            flush()
            prev_blank = True
            continue
        nxt = lines[idx + 1][0] if idx + 1 < len(lines) else ""
        if TABLE.match(raw) or HEADING.match(raw) or REF_DEF.match(raw) or SETEXT.match(raw):
            flush()
            prev_blank = False
            continue
        if parts and SETEXT.match(nxt) and not LIST_ITEM.match(raw):
            # Setext heading: this line is a heading, drop it.
            parts.clear()
            continue
        if raw.startswith(("    ", "\t")) and prev_blank and not parts and not LIST_ITEM.match(raw):
            continue  # indented code block
        if stripped.startswith("<") and stripped.endswith(">") and HTML_TAG.fullmatch(stripped):
            continue
        if LIST_ITEM.match(stripped):
            flush()
            stripped = LIST_ITEM.sub("", stripped)
        if stripped.startswith(">"):
            stripped = stripped.lstrip("> ").strip()
        cleaned = clean_inline(stripped)
        if cleaned:
            parts.append((cleaned, lineno))
        prev_blank = False
    flush()
    return segments


def extract_markdown(text: str, path: str, label: str = "") -> list[Segment]:
    return markdown_lines(((l, i + 1) for i, l in enumerate(text.splitlines())), path, label)


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
                        blocks.append([(l.strip(), first + k) for k, l in enumerate(doc)])
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
