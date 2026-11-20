"""Turn documents into prose segments with source line numbers.

Every extractor yields ``Segment`` objects. A segment is one paragraph or
list item of prose, with code, tables, headings, link targets and markup
removed, plus anchors that map character offsets back to source lines so a
finding can point at ``file:line``.
"""

from __future__ import annotations

import ast
import bisect
import html
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Iterator

from markdown_it import MarkdownIt
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.front_matter import front_matter_plugin

CODE = "Xcode"  # stands in for inline code; parsed as a proper noun

FORMATS = (
    "markdown", "text", "rst", "html", "source", "notebook", "commit",
    "transcript", "messages", "jsonl",
)
# detect_format also returns "code": a file that looks like code readcost
# has no comment syntax for. extract reads nothing from it and adds a note.


@dataclass
class Segment:
    text: str
    path: str
    anchors: list[tuple[int, int]] = field(default_factory=list)  # (offset, line)
    label: str = ""  # e.g. "assistant[3]" for a message inside a transcript
    codes: dict[int, str] = field(default_factory=dict)  # CODE offset -> original text
    in_list: bool = False  # a Markdown list item, not running prose
    skip: frozenset[str] = frozenset()  # rules a readcost directive turned off here
    # "inline-comment" for a comment that only ``comments = "all"`` reads;
    # its findings are reported at info unless a config sets the rule's level.
    kind: str = ""
    # For each character of ``text``, where it starts and ends in the source
    # file, in characters; -1 where that is not known (a space that stands
    # for a line break, text taken out of a JSON string). All five
    # characters of a CODE placeholder map to the whole code span. Empty
    # when the extractor has no offsets at all.
    starts: list[int] = field(default_factory=list, repr=False)
    ends: list[int] = field(default_factory=list, repr=False)

    def line_at(self, offset: int) -> int:
        if not self.anchors:
            return 0
        offsets = [a[0] for a in self.anchors]
        i = bisect.bisect_right(offsets, offset) - 1
        return self.anchors[max(i, 0)][1]

    def span(self, a: int, b: int) -> tuple[int, int] | None:
        """Source offsets (start, end) of ``text[a:b]``, or None when either end is unknown."""
        if not self.starts or not 0 <= a < b <= len(self.starts):
            return None
        start, end = self.starts[a], self.ends[b - 1]
        return (start, end) if 0 <= start < end else None


Span = tuple[int, int]  # (start, end) in the source file; (-1, -1) when unknown
UNKNOWN: Span = (-1, -1)
NEWLINE = re.compile(r"\r\n?|\n")  # the line breaks markdown-it, the LSP and readcost's columns use
ENTITY = re.compile(r"&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});?")


def line_starts(text: str, keepends_split: bool = False) -> list[int]:
    """Offset of each line's first character.

    Lines end at ``\\n``, ``\\r\\n`` or ``\\r``. With ``keepends_split`` they
    end wherever ``str.splitlines`` ends them, which the line-based
    extractors use.
    """
    if keepends_split:
        out, pos = [], 0
        for line in text.splitlines(keepends=True):
            out.append(pos)
            pos += len(line)
        return out or [0]
    return [0] + [m.end() for m in NEWLINE.finditer(text)]


def _align(text: str, raw: str, cursor: int) -> tuple[list[int], list[int], int]:
    """Where each character of ``text`` sits in ``raw``, at or after ``cursor``.

    ``text`` is ``raw`` with backslash escapes and character references
    decoded, as a Markdown or HTML parser returns it. Returns the start and
    end offset of each character (-1 for one that cannot be found) and the
    offset after the last one.
    """
    starts, ends = [-1] * len(text), [-1] * len(text)
    i, n = 0, len(raw)
    while i < len(text):
        c = text[i]
        if cursor < n and raw[cursor] == "&":
            m = ENTITY.match(raw, cursor)
            decoded = html.unescape(m.group()) if m else ""
            if m and decoded != m.group() and text.startswith(decoded, i):
                for k in range(i, i + len(decoded)):
                    starts[k], ends[k] = m.start(), m.end()
                cursor, i = m.end(), i + len(decoded)
                continue
        if cursor < n and raw[cursor] == c:
            starts[i], ends[i] = cursor, cursor + 1
            cursor, i = cursor + 1, i + 1
            continue
        if cursor + 1 < n and raw[cursor] == "\\" and raw[cursor + 1] == c:
            starts[i], ends[i] = cursor, cursor + 2
            cursor, i = cursor + 2, i + 1
            continue
        if c.isspace() and cursor < n and raw[cursor].isspace():
            cursor, i = cursor + 1, i + 1  # a line break the parser turned into a space
            continue
        # Markup the caller did not step over. Look for the next few characters;
        # a single character only close by, where it cannot be far wrong.
        for size, reach in ((8, n), (3, n), (1, cursor + 4)):
            chunk = text[i:i + size]
            found = raw.find(chunk, cursor, min(n, reach + len(chunk)))
            if found >= 0:
                cursor = found
                break
        else:
            i += 1
    return starts, ends, cursor


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
# Issue and pull request references: rust-lang/rust#123, #123, gh-123, GH-123.
ISSUE_REF = re.compile(r"(?<![\w/#&-])(?:[\w.-]+/[\w.-]+#\d+|#\d+|[Gg][Hh]-\d+)\b")
YAML_KEY = re.compile(r"^[^\s:#-][^:]*:(\s|$)")
YAML_LINE = re.compile(r"^(\s.*|#.*|-(\s.*)?|\.\.\.|[^\s:#-][^:]*:(\s.*)?)$")
IGNORE_NEXT = re.compile(r"readcost:\s*ignore", re.I)
DIRECTIVE = re.compile(r"readcost:\s*(?:ignore|off|on)\b(.*?)(?:-->|$)", re.I | re.S)
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


SENTINEL = re.compile(r"\x00(\d+)\x00")


def _plain(text: str) -> list[tuple[str, str | None]]:
    """Split text into prose and CODE pieces; a CODE piece carries the original."""
    originals: list[str] = []

    def keep(sub):
        def repl(m: re.Match) -> str:
            out = sub(m)
            if not out.startswith(CODE):
                return out  # a word list such as and/or stays prose
            # Whatever follows CODE (a closing paren, a full stop) stays prose.
            originals.append(m.group()[:len(m.group()) - (len(out) - len(CODE))])
            return f"\x00{len(originals) - 1}\x00" + out[len(CODE):]
        return repl

    marked = URL.sub(keep(_url), text.replace("\x00", ""))
    marked = PATH_CANDIDATE.sub(keep(_path), ISSUE_REF.sub(keep(lambda m: CODE), marked))
    pieces: list[tuple[str, str | None]] = []
    last = 0
    for m in SENTINEL.finditer(marked):
        if m.start() > last:
            pieces.append((marked[last:m.start()], None))
        pieces.append((CODE, originals[int(m.group(1))]))
        last = m.end()
    if last < len(marked):
        pieces.append((marked[last:], None))
    return pieces


def _is_yaml(body: str) -> bool:
    lines = [l for l in body.splitlines() if l.strip()]
    return bool(lines) and bool(YAML_KEY.match(lines[0])) and all(YAML_LINE.match(l) for l in lines)


def _plain_spans(text: str) -> list[tuple[str, str | None, int, int]]:
    """``_plain`` pieces with the range of ``text`` each one came from."""
    out, pos = [], 0
    for piece, original in _plain(text):
        size = len(piece if original is None else original)
        out.append((piece, original, pos, pos + size))
        pos += size
    if pos != len(text):  # a NUL was dropped; the ranges would be off
        return [(piece, original, -1, -1) for piece, original, _, _ in out]
    return out


def _content_at(content: str, first: int, src_lines: list[str], at):
    """A function from an offset in a block's content to that character's span in the file.

    markdown-it gives a block's content with container markers ("> ", list
    indents) removed, so each content line is the tail of a source line.
    ``at(k, col)`` is the file span of column ``col`` of source line ``k``.
    """
    starts = [0] + [i + 1 for i, c in enumerate(content) if c == "\n"]
    shifts: list[int | None] = []
    for j, line in enumerate(content.split("\n")):
        src = src_lines[first + j] if first + j < len(src_lines) else ""
        body = line.rstrip()
        col = len(src.rstrip()) - len(body)
        if col < 0 or src[col:col + len(body)] != body:
            found = src.find(line.strip()) if line.strip() else -1
            col = found - (len(line) - len(line.lstrip())) if found >= 0 else None
        shifts.append(col)

    def span(offset: int) -> Span:
        if offset < 0:
            return UNKNOWN
        j = bisect.bisect_right(starts, offset) - 1
        if shifts[j] is None:
            return UNKNOWN
        return at(first + j, offset - starts[j] + shifts[j])

    def spans(a: int, b: int) -> Span:
        """The file span of content[a:b]."""
        lo, hi = span(a), span(b - 1)
        return (lo[0], hi[1]) if lo[0] >= 0 and hi[1] >= 0 else UNKNOWN

    return spans


def _link_tail(raw: str, i: int, href: str = "") -> int:
    """The offset after a link's closing bracket and its destination or reference."""
    if not raw.startswith("]", i):
        return i
    i += 1
    if raw.startswith("(", i):
        depth, j, quote = 0, i, ""
        while j < len(raw):
            ch = raw[j]
            if ch == "\\":
                j += 2
                continue
            if quote:
                quote = "" if ch == quote else quote
            elif ch in "\"'" and raw[j - 1].isspace():
                quote = ch  # a title
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    dest = raw[i + 1:j].strip().lstrip("<")
                    # "[ref](not a destination)": the parentheses are prose.
                    same = not href or not dest or dest[0].lower() == href[0].lower() or dest[0] in "%&\\"
                    return j + 1 if same else i
            j += 1
        return i
    if raw.startswith("[", i):
        j = raw.find("]", i)
        return j + 1 if j >= 0 else i
    return i


def _image_end(raw: str, cursor: int) -> int:
    """The offset after the image that starts at or after ``cursor``."""
    j = raw.find("![", cursor)
    if j < 0:
        return cursor
    depth, k = 0, j + 1
    while k < len(raw):
        if raw[k] == "\\":
            k += 2
            continue
        if raw[k] == "[":
            depth += 1
        elif raw[k] == "]":
            depth -= 1
            if depth == 0:
                return _link_tail(raw, k)
        k += 1
    return cursor


BREAK = re.compile(r"[ \t]*\\?\n[ \t]*")
Piece = tuple[str, int, "str | None", "list[Span]"]  # text, line, original of a CODE piece, span per character


def _inline_pieces(inline, line_no, spans=None) -> list[Piece]:
    """Prose pieces of one paragraph, each paired with its source line and offsets.

    The paragraph starts on ``inline.map[0]``; each soft or hard break moves
    to the next line. Code spans, math and raw HTML can also hold newlines.
    ``spans(a, b)`` gives the file span of ``inline.content[a:b]``; ``cur``
    walks the content in step with the tokens so each piece can be found.
    """
    first = inline.map[0]
    raw = inline.content  # the paragraph's source lines, container markers removed
    starts = [0] + [i + 1 for i, c in enumerate(raw) if c == "\n"]
    k, cursor, in_autolink = first, 0, False
    cur = 0
    hrefs: list[str] = []
    pieces: list[Piece] = []

    def where(a: int, b: int) -> Span:
        return spans(a, b) if spans and 0 <= a < b else UNKNOWN

    def code(text_line: int, original: str | None, a: int, b: int) -> None:
        pieces.append((CODE, text_line, original, [where(a, b)] * len(CODE)))

    for child in inline.children or []:
        kind = child.type
        if in_autolink:
            in_autolink = kind != "link_close"
        elif kind == "text":
            st, en, cur = _align(child.content, raw, cur)
            for text, orig, a, b in _plain_spans(child.content):
                if a < 0:
                    pieces.append((text, line_no(k), orig, [UNKNOWN] * len(text)))
                elif orig is None:
                    pieces.append((text, line_no(k), None,
                                   [where(st[i], en[i]) for i in range(a, b)]))
                else:
                    code(line_no(k), orig, st[a], en[b - 1])
        elif kind in ("softbreak", "hardbreak"):
            k += 1
            pieces.append((" ", line_no(k), None, [UNKNOWN]))
            m = BREAK.match(raw, cur)
            cur = m.end() if m else cur
        elif kind == "code_inline":
            # markdown-it folds newlines in a code span into spaces; count
            # them in the raw source instead.
            cursor = max(cursor, cur, starts[min(k - first, len(starts) - 1)])
            fence = re.compile(r"(?<!`)" + re.escape(child.markup) + r"(?!`)")
            m = fence.search(raw, cursor)
            opened = m.start() if m else -1
            m = fence.search(raw, opened + len(child.markup)) if opened >= 0 else None
            closed = m.start() if m else -1
            code(line_no(k), f"{child.markup}{child.content}{child.markup}",
                 opened, closed + len(child.markup) if closed >= 0 else -1)
            if closed >= 0:
                k += raw.count("\n", opened, closed)
                cursor = cur = closed + len(child.markup)
        elif kind in ("math_inline", "math_inline_double"):
            whole = f"{child.markup}{child.content}{child.markup}"
            found = raw.find(whole, cur)
            code(line_no(k), whole, found, found + len(whole))
            cur = found + len(whole) if found >= 0 else cur
            k += child.content.count("\n")
        elif kind == "link_open" and child.markup == "autolink":
            found = raw.find("<", cur)
            end = raw.find(">", found) + 1 if found >= 0 else 0
            code(line_no(k), str(child.attrs.get("href", "")) or None, found if end else -1, end)
            cur = end or cur
            in_autolink = True
        elif kind == "link_open":
            hrefs.append(str(child.attrs.get("href", "")))
            cur += raw.startswith("[", cur)
        elif kind == "link_close":
            cur = _link_tail(raw, cur, hrefs.pop() if hrefs else "")
        elif kind == "image":
            k += sum(c.type in ("softbreak", "hardbreak") for c in child.children or [])
            cur = _image_end(raw, cur)
        elif kind == "html_inline":
            k += child.content.count("\n")
            found = raw.find(child.content, cur)
            cur = found + len(child.content) if found >= 0 else cur
        elif kind == "footnote_ref" and "label" not in (child.meta or {}):
            # An inline footnote, "^[text]": its text is read as its own paragraph.
            found = raw.find("^[", cur)
            cur = _bracket_end(raw, found + 1) if found >= 0 else cur
        elif kind == "footnote_ref":
            found = raw.find("[^", cur)
            end = raw.find("]", found) + 1 if found >= 0 else 0
            cur = end or cur
        elif child.markup and raw.startswith(child.markup, cur):
            cur += len(child.markup)  # emphasis and strikethrough markers add no words
    return pieces


def _segment(pieces: list[Piece], path: str, label: str) -> Segment | None:
    chars: list[str] = []
    anchors: list[tuple[int, int]] = []
    codes: dict[int, str] = {}
    spans: list[Span] = []
    for piece, line, original, where in pieces:
        if original is not None:
            codes[len(chars)] = original
        for ch, span in zip(piece, where):
            if ch.isspace():
                if chars and chars[-1] != " ":
                    chars.append(" ")
                    spans.append(UNKNOWN)
                continue
            if not anchors or anchors[-1][1] != line:
                anchors.append((len(chars), line))
            chars.append(ch)
            spans.append(span)
    text = "".join(chars).rstrip()
    if len(text.split()) < 4:
        return None
    spans = spans[:len(text)]
    return Segment(text, path, anchors, label, codes,
                   starts=[s for s, _ in spans], ends=[e for _, e in spans])


def _bracket_end(raw: str, i: int) -> int:
    """The offset after the "]" that closes the "[" at ``raw[i]``, nested brackets and escapes included."""
    depth, j = 0, i
    while j < len(raw):
        if raw[j] == "\\":
            j += 2
            continue
        depth += {"[": 1, "]": -1}.get(raw[j], 0)
        j += 1
        if depth == 0:
            return j
    return i


def _fill_maps(tokens) -> None:
    """Give each token that has no line map the lines its text came from.

    The footnote plugin builds the paragraph of an inline footnote
    ("^[text]") at the end of the token stream with no map. That
    paragraph takes the line of its "^[" in the paragraph that holds it;
    any other token without a map takes the map of the nearest enclosing
    token that has one, or else of the token before it.
    """
    holder: dict[int, Any] = {}  # inline footnote id -> the inline token that holds it
    searched: dict[int, int] = {}  # id(inline token) -> where the next "^[" search starts
    open_maps: list = []
    last, note = None, None
    for tok in tokens:
        if tok.type == "footnote_open":
            note = tok.meta.get("id")
        elif tok.type == "footnote_close":
            note = None
        if tok.map is None and tok.nesting != -1:
            parent = holder.get(note) if tok.type == "inline" else None
            found = -1
            if parent is not None:
                found = parent.content.find(f"^[{tok.content}]", searched.get(id(parent), 0))
            if found >= 0:
                searched[id(parent)] = found + 2
                line = parent.map[0] + parent.content.count("\n", 0, found)
                tok.map = [line, line + 1 + tok.content.count("\n")]
            else:
                inner = next((m for m in reversed(open_maps) if m is not None), None)
                tok.map = list(inner or last or [0, 1])
        if tok.nesting == 1:
            open_maps.append(tok.map)
        elif tok.nesting == -1 and open_maps:
            open_maps.pop()
        if tok.map is not None:
            last = tok.map
        if tok.type == "inline":
            for child in tok.children or []:
                if child.type == "footnote_ref" and "label" not in (child.meta or {}):
                    holder.setdefault(child.meta.get("id"), tok)


def _link_row(tok) -> bool:
    """True when an inline token is only links joined by separators such as | or ·."""
    depth, links = 0, 0
    for c in tok.children or []:
        if c.type == "link_open":
            depth, links = depth + 1, links + 1
        elif c.type == "link_close":
            depth -= 1
        elif depth == 0 and c.type in ("text", "softbreak") and c.content.strip(" |·•/-–\n"):
            return False
        elif depth == 0 and c.type not in ("text", "softbreak"):
            return False
    return links >= 2


def _markdown(src: str, path: str, label: str, line_no, at=None) -> list[Segment]:
    """``at(k, col)`` is the file span of column ``col`` of line ``k`` of ``src``; None for no offsets."""
    src_lines = NEWLINE.split(src) if at else []
    tokens = _MD.parse(src)
    if tokens and tokens[0].type == "front_matter" and not _is_yaml(tokens[0].content):
        tokens = _MD_PLAIN.parse(src)
    _fill_maps(tokens)
    segments: list[Segment] = []
    disabled = False
    ignore_level: int | None = None  # a readcost: ignore waits at this nesting level
    skip_level: int | None = None  # inside the block that ignore applies to
    # "readcost: ignore RULE ..." and "readcost: off RULE ...": only those rules.
    ignore_rules: frozenset[str] = frozenset()
    rule_skip: frozenset[str] = frozenset()  # for the block an ignore RULE applies to
    rule_level: int | None = None
    rule_token: int | None = None  # or, for a block that is one token, its index
    off_rules: frozenset[str] = frozenset()
    items = 0  # open list items
    for i, tok in enumerate(tokens):
        if rule_token is not None and i > rule_token:
            rule_skip, rule_token = frozenset(), None
        if tok.type in ("list_item_open", "list_item_close"):
            items += tok.nesting
        if skip_level is not None:
            if tok.level == skip_level and tok.nesting == -1:
                skip_level = None
            continue
        if tok.type == "html_block" and tok.content.lstrip().startswith("<!--"):
            # Comments, directives included, do not use up a pending ignore.
            m = DIRECTIVE.search(tok.content)
            rules = frozenset(re.findall(r"[a-z][a-z-]*[a-z]", m.group(1))) if m else frozenset()
            if OFF.search(tok.content):
                if rules:
                    off_rules |= rules
                else:
                    disabled = True
            elif ON.search(tok.content):
                if rules:
                    off_rules -= rules
                else:
                    disabled, off_rules = False, frozenset()
            elif IGNORE_NEXT.search(tok.content):
                ignore_level, ignore_rules = tok.level, rules
            continue
        if ignore_level is not None:
            if tok.level < ignore_level:
                ignore_level = None  # the container ended; nothing followed
            elif tok.level == ignore_level:
                ignore_level = None
                if ignore_rules:
                    # Read the block, but drop these rules' findings in it.
                    rule_skip = ignore_rules
                    if tok.nesting == 1:
                        rule_level = tok.level
                    else:
                        rule_token = i
                else:
                    if tok.nesting == 1:
                        skip_level = tok.level
                    continue
        if rule_level is not None and tok.level == rule_level and tok.nesting == -1:
            rule_skip, rule_level = frozenset(), None
        if tok.type == "html_block" and not disabled:
            # Prose inside HTML in Markdown (<p>...</p>, <details>) is still prose.
            base = tok.map[0] if tok.map else 0
            parser = _HTMLProse()
            parser.read(tok.content, _content_at(tok.content, base, src_lines, at) if at else None)
            for seg in markdown_lines([(t, line_no(base + n - 1), m if at else None)
                                       for t, n, m in parser.lines], path, label):
                seg.in_list = items > 0
                seg.skip = seg.skip | rule_skip | off_rules
                segments.append(seg)
            continue
        if disabled or tok.type != "inline" or i == 0 or tokens[i - 1].type != "paragraph_open":
            continue  # headings, table cells and definition terms are not prose
        if _link_row(tok):
            continue  # "[Guide](a) | [API docs](b) | [Changelog](c)": navigation, not prose
        spans = _content_at(tok.content, tok.map[0], src_lines, at) if at else None
        seg = _segment(_inline_pieces(tok, line_no, spans), path, label)
        if seg:
            seg.in_list = items > 0
            seg.skip = rule_skip | off_rules
            segments.append(seg)
    return segments


def markdown_lines(lines: Iterable[tuple], path: str, label: str = "") -> list[Segment]:
    """Prose segments from lines that together form Markdown.

    Each line is (text, line number) or (text, line number, map). The map
    says where the line's characters are in the file: an offset when the
    text is a verbatim run of the file starting there, a list with one span
    per character when it was rewritten, None when unknown.
    """
    lines = [(*line, None)[:3] for line in lines]
    numbers = [n for _, n, _ in lines] or [0]
    src = "\n".join(t for t, _, _ in lines)

    def at(k: int, col: int) -> Span:
        if k >= len(lines):
            return UNKNOWN
        where = lines[k][2]
        if where is None:
            return UNKNOWN
        if isinstance(where, int):
            return (where + col, where + col + 1)
        return where[col] if col < len(where) else UNKNOWN

    return _markdown(src, path, label, lambda k: numbers[min(k, len(numbers) - 1)], at)


def extract_markdown(text: str, path: str, label: str = "") -> list[Segment]:
    # A byte order mark is not Markdown. Left in, "\ufeff# Title" is a
    # paragraph instead of a heading and front matter is not recognised. Parse
    # without it; ``bom`` keeps the spans pointing into ``text`` as given.
    bom = 1 if text.startswith("\ufeff") else 0
    body = text[bom:]
    first = line_starts(body)

    def at(k: int, col: int) -> Span:
        return (first[k] + col + bom, first[k] + col + 1 + bom) if k < len(first) else UNKNOWN

    return _markdown(body, path, label, lambda k: k + 1, at)


# --------------------------------------------------------------- plain text

def extract_text(text: str, path: str, label: str = "") -> list[Segment]:
    segments, parts = [], []
    first = line_starts(text, keepends_split=True)

    def flush() -> None:
        if parts:
            body, anchors, starts = "", [], []
            for piece, lineno, base in parts:
                if body:
                    body += " "
                    starts.append(-1)
                anchors.append((len(body), lineno))
                body += piece
                starts.extend(range(base, base + len(piece)))
            if len(body.split()) >= 4:
                segments.append(Segment(body, path, anchors, label, starts=starts,
                                        ends=[s + 1 if s >= 0 else -1 for s in starts]))
            parts.clear()

    for i, line in enumerate(text.splitlines()):
        if line.strip():
            parts.append((line.strip(), i + 1, first[i] + len(line) - len(line.lstrip())))
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
    out: list[tuple] = []
    lines = text.splitlines()
    first = line_starts(text, keepends_split=True)
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
        # Roles become Markdown code spans, so findings can show the original;
        # ``literal`` already is one.
        where = [(first[i] + c, first[i] + c + 1) for c in range(len(line))]
        body, where = _sub_spans(RST_ROLE, line, where, lambda m: (_code_span(m.group(1)), None))
        body, where = _sub_spans(RST_LINK, body, where, lambda m: (m.group(1), 1))
        if body.rstrip().endswith("::"):
            body = body.rstrip()[:-1]
            skip_indent = indent
        out.append((body, i + 1, where[:len(body)]))
    return markdown_lines(out, path, label)


def _sub_spans(pattern: re.Pattern, text: str, where: list[Span], repl) -> tuple[str, list[Span]]:
    """``pattern.sub`` that also carries each character's file span.

    ``repl(match)`` returns (replacement, group). With a group number the
    replacement is that group's text and keeps its spans; with None every
    character of the replacement maps to the whole match.
    """
    out, spans, last = [], [], 0
    for m in pattern.finditer(text):
        new, group = repl(m)
        out.append(text[last:m.start()])
        spans.extend(where[last:m.start()])
        out.append(new)
        if group is None:
            spans.extend([(where[m.start()][0], where[m.end() - 1][1])] * len(new))
        else:
            spans.extend(where[m.start(group):m.end(group)])
        last = m.end()
    out.append(text[last:])
    spans.extend(where[last:])
    return "".join(out), spans


def _code_span(text: str) -> str:
    """Markdown code span for text; CODE when there is nothing to show."""
    if not text.strip():
        return CODE
    fence = "`" * (max((len(r) for r in re.findall(r"`+", text)), default=0) + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


# --------------------------------------------------------------- HTML

class _HTMLProse(HTMLParser):
    BLOCK = {"p", "li", "div", "section", "article", "blockquote", "td", "dd", "dt", "br", "tr"}
    SKIP = {"script", "style", "pre", "nav", "header", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "table", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[tuple[str, int, list[Span] | None]] = []
        self.skip = 0
        self.in_code = 0
        self.code: list[str] = []
        self.code_start = -1
        self.buffer: list[tuple[str, list[Span]]] = []
        self.start_line = 1
        self.src = ""
        self.first: list[int] = [0]
        self.spans = None

    def read(self, text: str, spans=None) -> None:
        """Parse ``text``; ``spans(a, b)`` is the file span of ``text[a:b]`` (default: the same offsets)."""
        self.src = text
        self.first = [0] + [i + 1 for i, c in enumerate(text) if c == "\n"]  # as HTMLParser counts lines
        self.spans = spans or (lambda a, b: (a, b))
        self.feed(text)
        self._flush()

    def _offset(self) -> int:
        line, col = self.getpos()
        return self.first[min(line - 1, len(self.first) - 1)] + col

    def _flush(self) -> None:
        chars: list[str] = []
        where: list[Span] = []
        for text, spans in self.buffer:
            for ch, span in zip(text, spans):
                if ch.isspace():
                    if chars and chars[-1] != " ":
                        chars.append(" ")
                        where.append(UNKNOWN)
                    continue
                chars.append(ch)
                where.append(span)
        text = "".join(chars).rstrip()
        if text:
            self.lines.append((text, self.start_line, where[:len(text)]))
        self.lines.append(("", self.start_line, None))
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "code":
            self.in_code += 1
            if self.in_code == 1:
                self.code = []
                self.code_start = self._offset()
        elif tag in self.BLOCK:
            self._flush()
            self.start_line = self.getpos()[0]

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag == "code":
            self.in_code = max(0, self.in_code - 1)
            if not self.in_code and not self.skip:
                code = re.sub(r"\s+", " ", "".join(self.code)).strip()
                end = self.src.find(">", self._offset()) + 1
                span = self.spans(self.code_start, end) if 0 <= self.code_start < end else UNKNOWN
                shown = _code_span(code)
                self.buffer.append((f" {shown} ", [UNKNOWN] + [span] * len(shown) + [UNKNOWN]))
        elif tag in self.BLOCK:
            self._flush()

    def handle_data(self, data):
        if self.skip:
            return
        if self.in_code:
            self.code.append(data)
            return
        if not "".join(t for t, _ in self.buffer).strip():
            self.start_line = self.getpos()[0]
        starts, ends, _ = _align(data, self.src, self._offset())
        self.buffer.append((data, [self.spans(a, b) if a >= 0 else UNKNOWN for a, b in zip(starts, ends)]))


def extract_html(text: str, path: str, label: str = "") -> list[Segment]:
    parser = _HTMLProse()
    parser.read(text)
    return markdown_lines(parser.lines, path, label)


# --------------------------------------------------------------- source comments

LANG_BY_EXT = {
    ".rs": "rust", ".py": "python", ".pyi": "python", ".go": "c", ".js": "c",
    ".mjs": "c", ".cjs": "c", ".ts": "c", ".tsx": "c", ".jsx": "c", ".c": "c",
    ".h": "c", ".cc": "c", ".cpp": "c", ".hpp": "c", ".java": "c", ".kt": "c",
    ".swift": "c", ".scala": "c", ".cs": "c", ".sh": "hash", ".bash": "hash",
    ".rb": "hash", ".toml": "hash", ".yaml": "hash", ".yml": "hash",
    ".cxx": "c", ".hxx": "c", ".hh": "c", ".kts": "c", ".groovy": "c", ".gradle": "c",
    ".proto": "c", ".cu": "c", ".cuh": "c",
    ".zsh": "hash", ".ksh": "hash", ".fish": "hash",
    ".php": "php", ".lua": "lua", ".hs": "haskell", ".ex": "elixir", ".exs": "elixir",
    ".jl": "julia", ".r": "r", ".dart": "dart", ".zig": "zig",
    ".pl": "perl", ".pm": "perl", ".pod": "perl",
}
# Files known by name, whose # comments are their only prose.
LANG_BY_NAME = {name: "hash" for name in (
    "Makefile", "GNUmakefile", "Dockerfile", "Containerfile", "Gemfile", "Rakefile")}
# The interpreter on a #! line, for a script with no extension.
LANG_BY_INTERPRETER = {
    "python": "python", "sh": "hash", "bash": "hash", "zsh": "hash", "dash": "hash",
    "ksh": "hash", "fish": "hash", "ruby": "hash", "node": "c", "deno": "c", "bun": "c",
    "perl": "perl", "php": "php", "lua": "lua", "luajit": "lua", "rscript": "r",
    "julia": "julia", "elixir": "elixir", "runghc": "haskell", "runhaskell": "haskell",
}
# Code that readcost has no comment syntax for. Read as prose, its code would
# be checked as sentences, so it is not read at all.
CODE_EXTS = frozenset("""
    .m .mm .ml .mli .fs .fsi .fsx .erl .hrl .clj .cljs .cljc .el .lisp .scm .rkt
    .elm .purs .nim .cr .d .v .sv .svh .vhd .vhdl .adb .ads .pas .f .f90 .f95
    .cob .cbl .asm .s .tcl .awk .sol .glsl .hlsl .wgsl .metal .ps1 .psm1 .bat .cmd
    .sql .tf .hcl .cmake .vue .svelte .css .scss .sass .less .vim .nix .gleam .odin
    .hx .vala .pyx .pxd .coffee .lean .agda .idr .wat .ll
""".split())
CODEISH = re.compile(r"[;{}]\s*$|^\s*(let|fn|def|return|import|use|if|for|while|pub|var|const)\b|=>|::|\(\)\s*$")


@dataclass(frozen=True)
class CommentSyntax:
    """Comment syntax of one language.

    Doc comments are always read, as Markdown. The other comments are read
    only with ``comments = "all"``. Each block entry is a regular expression
    with a ``body`` group.
    """
    doc_lines: tuple[str, ...] = ()
    lines: tuple[str, ...] = ()
    doc_blocks: tuple[str, ...] = ()
    blocks: tuple[str, ...] = ()
    not_comment: tuple[str, ...] = ()  # line starts that are code, such as PHP's #[ attributes
    continues: str = ""  # a comment line after a doc line continues it (Haddock, LDoc)
    strings: str = ""    # doc strings with their own reader: "elixir", "julia" or "pod"


C_DOC_BLOCK = r"/\*\*(?![*/])(?P<body>.*?)\*/"
C_BLOCK = r"/\*(?!\*)(?P<body>.*?)\*/"
COMMENT_SYNTAX: dict[str, CommentSyntax] = {
    # PHPDoc /** */; // and # comments; #[...] is an attribute.
    "php": CommentSyntax(lines=("//", "#"), doc_blocks=(C_DOC_BLOCK,), blocks=(C_BLOCK,),
                         not_comment=("#[",)),
    # LDoc and EmmyLua: a comment that starts with --- is a doc comment.
    "lua": CommentSyntax(doc_lines=("---",), lines=("--",), continues="--",
                         blocks=(r"--\[(?P<eq>=*)\[(?P<body>.*?)\](?P=eq)\]",)),
    # Haddock: -- | and -- ^ start a doc comment, {-| -} is one; {-# #-} is a pragma.
    "haskell": CommentSyntax(doc_lines=("-- |", "-- ^"), lines=("--",), continues="--",
                             doc_blocks=(r"\{-[|^](?P<body>.*?)-\}",),
                             blocks=(r"\{-(?![#|^])(?P<body>.*?)-\}",)),
    # @moduledoc, @doc and @typedoc strings.
    "elixir": CommentSyntax(lines=("#",), strings="elixir"),
    # Triple-quoted docstrings before a definition; #= =# block comments.
    "julia": CommentSyntax(lines=("#",), blocks=(r"#=(?P<body>.*?)=#",), not_comment=("#=",),
                           strings="julia"),
    # roxygen2: #' lines.
    "r": CommentSyntax(doc_lines=("#'",), lines=("#",)),
    "dart": CommentSyntax(doc_lines=("///",), lines=("//",), doc_blocks=(C_DOC_BLOCK,),
                          blocks=(C_BLOCK,)),
    # Zig has line comments only: /// and //! are doc comments.
    "zig": CommentSyntax(doc_lines=("///", "//!"), lines=("//",)),
    # POD between =head1 (or any command) and =cut.
    "perl": CommentSyntax(lines=("#",), strings="pod"),
}


def _comment_blocks(lines: list[str], prefixes: tuple[str, ...],
                    first: list[int] | None = None) -> Iterator[list[tuple]]:
    """Runs of comment lines as (body, line number, offset of the body in the file)."""
    block: list[tuple] = []
    for i, line in enumerate(lines):
        s = line.strip()
        prefix = next((p for p in prefixes if s.startswith(p)), None)
        if prefix is not None:
            body = s[len(prefix):]
            body = body[1:] if body.startswith(" ") else body
            col = len(line) - len(line.lstrip()) + len(s) - len(body)
            block.append((body, i + 1, first[i] + col if first else None))
        elif block:
            yield block
            block = []
    if block:
        yield block


def _block_comments(text: str) -> Iterator[list[tuple[str, int]]]:
    for m in re.finditer(r"/\*\*?(.*?)\*/", text, re.S):
        start_line = text.count("\n", 0, m.start()) + 1
        out, pos = [], m.start(1)
        for k, whole in enumerate(m.group(1).splitlines(keepends=True)):
            line = whole.rstrip("\r\n")
            body = re.sub(r"^\s*\*\s?", "", line)
            out.append((body, start_line + k, pos + len(line) - len(body)))
            pos += len(whole)
        yield out


def _docstring_lines(doc: list[str], start: int, lines: list[str], first: list[int]) -> list[tuple]:
    """(text, line number, offset in the file) for each line of a docstring that starts on line ``start``.

    The text comes from the evaluated string, so a backslash at the end of a
    source line joins two lines of it; the lines after are then looked for a
    little further down. A line the source spells differently (an escape)
    gets no offset.
    """
    out, shift = [], 0
    for k, body in enumerate(doc):
        n, offset = start + k + shift, None
        for extra in range(4 if body.strip() else 0):
            if n + extra > len(lines):
                break
            col = lines[n + extra - 1].find(body)
            if col >= 0:
                shift, n = shift + extra, n + extra
                offset = first[n - 1] + col
                break
        out.append((body, n, offset))
    return out


def _line_no(first: list[int], offset: int) -> int:
    """1-based line of ``offset``; ``first`` is ``line_starts(text, keepends_split=True)``."""
    return bisect.bisect_right(first, offset)


def _body_lines(text: str, start: int, end: int, first: list[int], strip) -> list[tuple]:
    """(text, line number, offset) for each line of ``text[start:end]``; ``strip(line)`` is how much to cut."""
    out, pos = [], start
    for whole in text[start:end].splitlines(keepends=True):
        line = whole.rstrip("\r\n")
        cut = strip(line)
        out.append((line[cut:], _line_no(first, pos), pos + cut))
        pos += len(whole)
    return out


def _covered(first: list[int], start: int, end: int) -> range:
    """0-based indexes of the lines that ``text[start:end]`` touches."""
    return range(_line_no(first, start) - 1, _line_no(first, max(end - 1, start)))


def _regex_blocks(text: str, pattern: str, first: list[int], covered: set[int]) -> list[list[tuple]]:
    star = pattern.startswith("/")  # a leading * on each line of a C-style block is decoration
    out = []
    for m in re.finditer(pattern, text, re.S):
        if _line_no(first, m.start()) - 1 in covered:
            continue  # inside a block found already, such as a doc block
        covered.update(_covered(first, m.start(), m.end()))
        out.append(_body_lines(text, m.start("body"), m.end("body"), first,
                               (lambda l: len(l) - len(re.sub(r"^\s*\*\s?", "", l))) if star else (lambda l: 0)))
    return out


ELIXIR_HEREDOC = re.compile(
    r'^[ \t]*@(?:moduledoc|doc|typedoc)[ \t]+(?:~[sS])?(?P<q>"""|\'\'\')[ \t]*\r?\n'
    r"(?P<body>.*?)^(?P<indent>[ \t]*)(?P=q)", re.S | re.M)
ELIXIR_DOC_LINE = re.compile(r'^[ \t]*@(?:moduledoc|doc|typedoc)[ \t]+(?:~[sS])?"(?P<body>[^"\\\n]*)"', re.M)
JULIA_DOCSTRING = re.compile(
    r'^[ \t]*(?:@doc[ \t]+(?:raw)?)?"""[ \t]*\r?\n(?P<body>.*?)^(?P<indent>[ \t]*)"""[ \t]*$', re.S | re.M)
POD_BLOCK = re.compile(r"^=[a-zA-Z]\w*.*?(?:^=cut\b[^\n]*|\Z)", re.S | re.M)
POD_DOUBLE_CODE = re.compile(r"C<{2,}\s+(.+?)\s+>{2,}")
POD_CODE = re.compile(r"C<([^<>]*)>")
POD_LINK = re.compile(r"L<(?:([^|<>]*)\|)?([^<>]*)>")
POD_TEXT = re.compile(r"[BIFS]<([^<>]*)>")
POD_DROP = re.compile(r"[XZ]<[^<>]*>")
POD_ESCAPE = re.compile(r"E<(\w+)>")
POD_ESCAPES = {"lt": "<", "gt": ">", "verbar": "|", "sol": "/"}


def _dedent(indent: int):
    return lambda line: min(indent, len(line) - len(line.lstrip(" \t")))


def _string_docs(text: str, kind: str, first: list[int], covered: set[int]) -> list[list[tuple]]:
    """Doc strings that are not comments: Elixir @doc, Julia docstrings, Perl POD."""
    out: list[list[tuple]] = []
    if kind == "elixir":
        for m in ELIXIR_HEREDOC.finditer(text):
            covered.update(_covered(first, m.start(), m.end()))
            out.append(_body_lines(text, m.start("body"), m.end("body"), first, _dedent(len(m.group("indent")))))
        for m in ELIXIR_DOC_LINE.finditer(text):
            if _line_no(first, m.start()) - 1 not in covered:
                out.append([(m.group("body"), _line_no(first, m.start()), m.start("body"))])
    elif kind == "julia":
        for m in JULIA_DOCSTRING.finditer(text):
            covered.update(_covered(first, m.start(), m.end()))
            body = text[m.start("body"):m.end("body")]
            # Julia removes the indent the lines and the closing quotes share.
            indents = [len(l) - len(l.lstrip(" \t")) for l in body.splitlines() if l.strip()]
            margin = min([len(m.group("indent")), *indents])
            out.append(_body_lines(text, m.start("body"), m.end("body"), first, _dedent(margin)))
    elif kind == "pod":
        for m in POD_BLOCK.finditer(text):
            covered.update(_covered(first, m.start(), m.end()))
            out.append(_pod_lines(text, m.start(), m.end(), first))
    return out


def _pod_lines(text: str, start: int, end: int, first: list[int]) -> list[tuple]:
    """Prose lines of a POD block: commands, verbatim paragraphs and =begin blocks become breaks."""
    out: list[tuple] = []
    skip_until = ""  # "=end" inside =begin, or "" (a blank line) after =for
    verbatim = False
    for body, n, offset in _body_lines(text, start, end, first, lambda l: 0):
        if skip_until:
            if (body.startswith(skip_until) if skip_until != "blank" else not body.strip()):
                skip_until = ""
            out.append(("", n))
            continue
        if body.startswith("="):
            skip_until = "=end" if body.startswith("=begin") else "blank" if body.startswith("=for") else ""
            out.append(("", n))
            continue
        if not body.strip():
            verbatim = False
        elif body[0] in " \t" or verbatim:
            verbatim = True  # a verbatim paragraph: code
            out.append(("", n))
            continue
        where = [(offset + c, offset + c + 1) for c in range(len(body))]
        body, where = _sub_spans(POD_DOUBLE_CODE, body, where, lambda m: (_code_span(m.group(1)), None))
        for _ in range(3):  # B<C<x>>: innermost first
            body, where = _sub_spans(POD_CODE, body, where, lambda m: (_code_span(m.group(1)), None))
            body, where = _sub_spans(POD_LINK, body, where,
                                     lambda m: (m.group(1), 1) if m.group(1) else (_code_span(m.group(2)), None))
            body, where = _sub_spans(POD_TEXT, body, where, lambda m: (m.group(1), 1))
            body, where = _sub_spans(POD_DROP, body, where, lambda m: ("", None))
            body, where = _sub_spans(POD_ESCAPE, body, where, lambda m: (POD_ESCAPES.get(m.group(1), ""), None))
        out.append((body, n, where[:len(body)]))
    return out


def _syntax_comments(text: str, lines: list[str], first: list[int], syn: CommentSyntax,
                     comments: str) -> tuple[list[list[tuple]], list[list[tuple]]]:
    """(doc comment blocks, other comment blocks) for a language in COMMENT_SYNTAX."""
    covered: set[int] = set()
    docs = _string_docs(text, syn.strings, first, covered)
    for pattern in syn.doc_blocks:
        docs.extend(_regex_blocks(text, pattern, first, covered))
    plain: list[list[tuple]] = []
    for pattern in syn.blocks:
        found = _regex_blocks(text, pattern, first, covered)
        if comments == "all":
            plain.extend(found)
    block: list[tuple] = []
    kind = ""
    for i, line in enumerate(lines):
        s = line.strip()
        prefix, now = None, ""
        if i not in covered and not (syn.not_comment and s.startswith(syn.not_comment)):
            prefix = next((p for p in syn.doc_lines if s.startswith(p)), None)
            now = "doc" if prefix else ""
            if prefix is None and kind == "doc" and syn.continues and s.startswith(syn.continues):
                prefix, now = syn.continues, "doc"
            if prefix is None:
                prefix = next((p for p in syn.lines if s.startswith(p)), None)
                now = "plain" if prefix else ""
        if block and (now != kind or prefix is None):
            (docs if kind == "doc" else plain).append(block)
            block = []
        kind = now
        if prefix is None or (now == "plain" and comments != "all"):
            continue
        body = s[len(prefix):]
        body = body[1:] if body.startswith(" ") else body
        col = len(line) - len(line.lstrip()) + len(s) - len(body)
        block.append((body, i + 1, first[i] + col))
    if block:
        (docs if kind == "doc" else plain).append(block)
    docs.sort(key=lambda b: b[0][1] if b else 0)
    plain.sort(key=lambda b: b[0][1] if b else 0)
    return docs, plain


def _shebang_lang(text: str | None) -> str | None:
    """The language a script's #! line names, or None."""
    if not text or not text.startswith("#!"):
        return None
    words = text[2:].split("\n", 1)[0].split()
    if words and words[0].endswith("/env"):
        words = [w for w in words[1:] if not w.startswith("-") and "=" not in w]
    if not words:
        return None
    name = re.match(r"[a-z]*", words[0].rsplit("/", 1)[-1].lower()).group()
    return LANG_BY_INTERPRETER.get(name)


def source_language(path: str, text: str | None = None) -> str:
    """The comment syntax to read ``path`` with: from its extension, its name or its #! line."""
    p = Path(path)
    return (LANG_BY_EXT.get(p.suffix.lower()) or LANG_BY_NAME.get(p.name)
            or _shebang_lang(text) or "c")


def extract_source(text: str, path: str, label: str = "", comments: str = "doc") -> list[Segment]:
    """Prose from comments. ``comments`` is "doc" (doc comments only) or "all"."""
    return _source_segments(text, path, label, comments, source_language(path, text))


def _source_segments(text: str, path: str, label: str, comments: str, lang: str) -> list[Segment]:
    lines = text.splitlines()
    if text.startswith("#!"):
        lines[0] = ""  # the interpreter line is not a comment
    first = line_starts(text, keepends_split=True)
    # Doc comments are Markdown: code in them sits in fences, which
    # markdown_lines skips. Plain comments often hold commented-out code, so
    # only they get the line-level CODEISH filter.
    blocks: list[list[tuple]] = []
    plain: list[list[tuple]] = []   # read in either mode
    extra: list[list[tuple]] = []   # read only with comments = "all"
    if lang in COMMENT_SYNTAX:
        blocks, extra = _syntax_comments(text, lines, first, COMMENT_SYNTAX[lang], comments)
    elif lang == "python":
        try:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    body = getattr(node, "body", [])
                    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                            and isinstance(body[0].value.value, str):
                        start = body[0].lineno
                        doc = body[0].value.value.splitlines()
                        # Remove the docstring's own indent only, so an
                        # indented code block inside it stays code.
                        margin = min((len(l) - len(l.lstrip()) for l in doc[1:] if l.strip()),
                                     default=0)
                        margin = min(margin, body[0].col_offset)
                        doc = [l.strip() if k == 0 else l[margin:].rstrip() for k, l in enumerate(doc)]
                        blocks.append(_docstring_lines(doc, start, lines, first))
        except SyntaxError:
            pass
        if comments == "all":
            extra.extend(_comment_blocks(lines, ("#",), first))
    elif lang == "rust":
        blocks.extend(_comment_blocks(lines, ("///", "//!"), first))
        if comments == "all":
            extra.extend(_comment_blocks(lines, ("//",), first))
    elif lang == "hash":
        plain.extend(_comment_blocks(lines, ("#",), first))
    else:
        blocks.extend(_block_comments(text))
        plain.extend(_comment_blocks(lines, ("///", "//"), first))
    segments: list[Segment] = []
    for block in blocks:
        segments.extend(markdown_lines(block, path, label))
    for group, kind in ((plain, ""), (extra, "inline-comment")):
        for block in group:
            prose = [line for line in block if not CODEISH.search(line[0])]
            for seg in markdown_lines(prose, path, label):
                seg.kind = kind
                segments.append(seg)
    return segments


# --------------------------------------------------------------- Jupyter notebooks

class _Str(str):
    """A JSON string that remembers the offset of its opening quote."""
    at = -1


_WS = re.compile(r"[ \t\n\r]*")
_SCALAR = json.JSONDecoder()


def _json_at(text: str, i: int):
    """Parse the JSON value at ``text[i]``; strings come back as ``_Str``. Returns (value, end)."""
    if text.startswith('"', i):
        value, end = json.decoder.scanstring(text, i + 1)
        out = _Str(value)
        out.at = i
        return out, end
    if text.startswith("{", i) or text.startswith("[", i):
        is_obj = text[i] == "{"
        close = "}" if is_obj else "]"
        items: dict | list = {} if is_obj else []
        i = _WS.match(text, i + 1).end()
        if text.startswith(close, i):
            return items, i + 1
        while True:
            if is_obj:
                if not text.startswith('"', i):
                    raise ValueError(f"expected a key at offset {i}")
                key, i = json.decoder.scanstring(text, i + 1)
                i = _WS.match(text, i).end()
                if not text.startswith(":", i):
                    raise ValueError(f"expected ':' at offset {i}")
                i = _WS.match(text, i + 1).end()
            value, i = _json_at(text, i)
            if is_obj:
                items[key] = value
            else:
                items.append(value)
            i = _WS.match(text, i).end()
            if text.startswith(",", i):
                i = _WS.match(text, i + 1).end()
            elif text.startswith(close, i):
                return items, i + 1
            else:
                raise ValueError(f"expected ',' or {close!r} at offset {i}")
    return _SCALAR.raw_decode(text, i)  # a number, true, false or null


def _json_positions(text: str):
    start = _WS.match(text, 1 if text.startswith("﻿") else 0).end()
    value, end = _json_at(text, start)
    if _WS.match(text, end).end() != len(text):
        raise ValueError(f"extra data at offset {end}")
    return value


def _string_spans(raw: str, at: int) -> list[Span]:
    """The file span of each character of the JSON string literal whose opening quote is at ``at``."""
    spans, i, n = [], at + 1, len(raw)
    while i < n and raw[i] != '"':
        if raw[i] != "\\":
            spans.append((i, i + 1))
            i += 1
        elif raw.startswith("u", i + 1):
            j = i + 6
            if 0xD800 <= int(raw[i + 2:i + 6], 16) <= 0xDBFF and raw.startswith("\\u", j) \
                    and 0xDC00 <= int(raw[j + 2:j + 6], 16) <= 0xDFFF:
                j += 6  # a surrogate pair is one character
            spans.append((i, j))
            i = j
        else:
            spans.append((i, i + 2))
            i += 2
    return spans


def _cell_text(raw: str, source) -> tuple[str, list[Span]]:
    """A cell's source, a string or a list of strings, and the file span of each character."""
    parts = source if isinstance(source, list) else [source]
    body, spans = [], []
    for s in parts:
        if not isinstance(s, str):
            continue
        where = _string_spans(raw, s.at) if isinstance(s, _Str) and s.at >= 0 else []
        body.append(str(s))
        spans.extend(where if len(where) == len(s) else [UNKNOWN] * len(s))
    return "".join(body), spans


def _remap(segments: list[Segment], cell_starts: list[int], spans: list[Span],
           file_starts: list[int]) -> None:
    """Move segments read from a cell's text to offsets and lines in the notebook file."""
    def file_line(line: int) -> int:
        k = min(max(line - 1, 0), len(cell_starts) - 1)
        for p in range(cell_starts[k], len(spans)):
            if spans[p][0] >= 0:
                return bisect.bisect_right(file_starts, spans[p][0])
        return 0

    for seg in segments:
        seg.anchors = [(offset, file_line(line)) for offset, line in seg.anchors]
        starts, ends = [], []
        for a, b in zip(seg.starts, seg.ends):
            if 0 <= a < b <= len(spans) and spans[a][0] >= 0 and spans[b - 1][1] >= 0:
                starts.append(spans[a][0])
                ends.append(spans[b - 1][1])
            else:
                starts.append(-1)
                ends.append(-1)
        seg.starts, seg.ends = starts, ends


# Kernel language (metadata.kernelspec.language or language_info.name) to comment syntax.
NOTEBOOK_LANGS = {
    "python": "python", "ipython": "python", "r": "r", "julia": "julia", "rust": "rust",
    "scala": "c", "java": "c", "kotlin": "c", "c": "c", "c++": "c", "cpp": "c", "go": "c",
    "javascript": "c", "typescript": "c", "csharp": "c", "c#": "c", "swift": "c",
    "bash": "hash", "sh": "hash", "shell": "hash", "ruby": "hash", "perl": "perl",
    "php": "php", "lua": "lua", "haskell": "haskell", "elixir": "elixir", "dart": "dart",
    "zig": "zig",
}


def extract_notebook(text: str, path: str, label: str = "", comments: str = "doc",
                     notes: list[str] | None = None) -> list[Segment]:
    """Prose from a Jupyter notebook's Markdown cells, and with ``comments = "all"``
    from the comments in its code cells. Offsets and lines point into the .ipynb file."""
    notes = notes if notes is not None else []
    try:
        nb = _json_positions(text)
    except (ValueError, IndexError, RecursionError) as exc:
        notes.append(f"not a readable Jupyter notebook ({exc}); nothing was checked")
        return []
    cells = nb.get("cells") if isinstance(nb, dict) else None
    worksheets = nb.get("worksheets") if isinstance(nb, dict) else None
    legacy = cells is None and isinstance(worksheets, list)
    if legacy:
        cells = [cell for ws in worksheets if isinstance(ws, dict) and isinstance(ws.get("cells"), list)
                 for cell in ws["cells"]]
    if not isinstance(cells, list):
        notes.append("not a Jupyter notebook: no list of cells; nothing was checked")
        return []
    meta = nb.get("metadata") if isinstance(nb.get("metadata"), dict) else {}
    kernel_language = _get_path(meta, "kernelspec.language") or _get_path(meta, "language_info.name") \
        or meta.get("language") or ""
    file_starts = line_starts(text)
    segments: list[Segment] = []
    unread_languages: set[str] = set()
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        kind = cell.get("cell_type")
        if kind == "markdown":
            body, spans = _cell_text(text, cell.get("source"))
            segs, cell_starts = extract_markdown(body, path, label), line_starts(body)
        elif kind == "code" and comments == "all":
            name = cell.get("language", kernel_language) if legacy else kernel_language
            name = name.strip().lower() if isinstance(name, str) else ""
            lang = NOTEBOOK_LANGS.get(name) or NOTEBOOK_LANGS.get(re.sub(r"[\d.]+$", "", name))
            if lang is None:
                unread_languages.add(name)
                continue
            body, spans = _cell_text(text, cell.get("source", cell.get("input")))
            segs = _source_segments(body, path, label, "all", lang)
            cell_starts = line_starts(body, keepends_split=True)
        else:
            continue  # raw cells, and outputs, are not prose
        _remap(segs, cell_starts, spans, file_starts)
        segments.extend(segs)
    for name in sorted(unread_languages):
        source = "cell" if legacy else "notebook"
        notes.append(f"code cells not read: readcost has no comment syntax for the {source}'s "
                     f"language {name or '(none given)'!r}")
    return segments


# --------------------------------------------------------------- commit messages

# "net/http: fix ...", "cmd/compile, runtime: ...": a scope prefix, not prose.
COMMIT_SCOPE = re.compile(r"^[\w./+,{} -]*[\w}]: (?=\S)")
SHELL_START = re.compile(r"^\s*(\$ |cd |git |go |make |sed |rf |cat |echo |\./)")


def _commit_prose(line: str) -> bool:
    """False for benchmark tables, command lines and other lines that are not sentences."""
    s = line.strip()
    if not s:
        return True
    if SHELL_START.match(line) or "±" in s or re.search(r"\S {2,}\S.* {2,}\S", s):
        return False  # a shell command, or columns of a table such as benchstat output
    letters = sum(ch.isalpha() for ch in s)
    return letters >= 0.6 * len(s.replace(" ", ""))


def extract_commit(text: str, path: str, label: str = "") -> list[Segment]:
    kept = []
    first = line_starts(text, keepends_split=True)
    for i, line in enumerate(text.splitlines()):
        base = first[i]
        if line.startswith("# ------------------------ >8"):
            break
        if line.startswith("#"):
            continue
        if re.match(r"^[\w-]+:\s", line) and i > 0:  # trailers: Signed-off-by:, Co-Authored-By:
            continue
        if i == 0:
            scope = COMMIT_SCOPE.match(line)
            if scope and " " not in scope.group(0).rstrip(": ").replace(", ", ","):
                line, base = line[scope.end():], base + scope.end()
        elif not _commit_prose(line):
            line = ""
        kept.append((line, i + 1, base))
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
    if suffix == ".ipynb":
        return "notebook"
    if suffix in LANG_BY_EXT or name in LANG_BY_NAME:
        return "source"  # config files too: only their # comments are prose
    if suffix in CODE_EXTS:
        return "code"
    if text and text.startswith("#!") and suffix not in (".txt", ".text"):
        return "source" if _shebang_lang(text) else "code"  # a script without an extension
    return "text"


def extract(text: str, path: str, fmt: str | None = None, *, field_path: str | None = None,
            last_only: bool = False, comments: str = "doc",
            notes: list[str] | None = None) -> list[Segment]:
    """Prose segments of ``text``. Notes for the reader, such as why nothing was read, go in ``notes``."""
    fmt = fmt or detect_format(path, text)
    notes = notes if notes is not None else []
    if fmt == "code":
        notes.append("this looks like code in a language readcost has no comment syntax for, "
                     "so nothing was checked; --format text reads it as prose")
        return []
    if fmt == "notebook":
        return extract_notebook(text, path, comments=comments, notes=notes)
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
            for seg in extract_markdown(body, path, label):
                # The offsets are into the message, which the file holds as an
                # escaped JSON string, so they say nothing about the file.
                seg.starts, seg.ends = [], []
                segments.append(seg)
        return segments
    raise ValueError(f"unknown format {fmt!r}; choose one of {', '.join(FORMATS)}")
