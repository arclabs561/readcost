"""Pull request text from a GitHub event file, checked like a Markdown file.

The title is checked as plain text and the description as Markdown, so code,
HTML comments (a pull request template's instructions) and link targets are
not read as prose. Findings are located by the text they came from and the
line within it, since neither is a file.

The event file is untrusted input from whoever opened the pull request: it is
read here as JSON and only ever analysed, never passed to a shell.
"""

from __future__ import annotations

import json
from pathlib import Path

TITLE = "pull request title"
BODY = "pull request description"
PATHS = frozenset((TITLE, BODY))

# Below this many words of prose (title and description together, outside
# code and comments) the text is not checked: "Fixes #12" has nothing to say
# about reading cost, and a verdict on a dozen words swings on one finding.
# Chosen, not measured.
MIN_WORDS = 30


def read_event(path: str | Path) -> dict | None:
    """The ``pull_request`` object of a GitHub event file, or None.

    pull_request and pull_request_target events carry one; push, issues and
    the other events do not.
    """
    event = json.loads(Path(path).read_text(encoding="utf-8"))
    pr = event.get("pull_request") if isinstance(event, dict) else None
    return pr if isinstance(pr, dict) else None


def check_pull_request(analyzer, pr: dict) -> list:
    """Results for the title (plain text) and the description (Markdown)."""
    title = pr.get("title") or ""
    body = pr.get("body") or ""
    return [analyzer.check_text(title, "text", TITLE),
            analyzer.check_text(body, "markdown", BODY)]


def where(path: str, line: int) -> str:
    """A finding's place: "pull request description, line 3", or ``path:line`` for a file.

    The title is one line, so it gets no line number.
    """
    if path in PATHS:
        return f"{path}, line {line}" if line and path != TITLE else path
    return f"{path}:{line}" if line else path
