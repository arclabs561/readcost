"""action.yml: expressions reach scripts only through env, and actions are pinned.

A line scanner instead of a YAML parser keeps the test free of a new
dependency; it relies on the file's block style (``run: |``, indented keys).
"""

import re
from pathlib import Path

ACTION = Path(__file__).resolve().parents[1] / "action.yml"


def indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def parent_key(lines: list[str], i: int) -> str:
    """The key of the nearest less-indented line above line ``i``."""
    level = indent(lines[i])
    for j in range(i - 1, -1, -1):
        if lines[j].strip() and indent(lines[j]) < level:
            return lines[j].strip().lstrip("- ").split(":", 1)[0]
    return ""


def run_blocks(lines: list[str]) -> list[list[str]]:
    blocks = []
    for i, line in enumerate(lines):
        if re.match(r"\s*(- )?run: \|", line):
            level, body = indent(line), []
            for nxt in lines[i + 1:]:
                if nxt.strip() and indent(nxt) <= level:
                    break
                body.append(nxt)
            blocks.append(body)
        elif re.match(r"\s*(- )?run: \S", line):
            blocks.append([line])
    return blocks


def test_inputs_reach_steps_only_through_env():
    lines = ACTION.read_text().splitlines()
    uses = [i for i, ln in enumerate(lines) if "${{ inputs." in ln]
    assert uses, "the scanner found no inputs; has action.yml changed shape?"
    for i in uses:
        assert parent_key(lines, i) == "env", f"action.yml:{i + 1}: {lines[i].strip()}"


def test_run_scripts_contain_no_expressions():
    blocks = run_blocks(ACTION.read_text().splitlines())
    assert len(blocks) >= 2, "the scanner found too few run blocks; has action.yml changed shape?"
    for body in blocks:
        assert not any("${{" in ln for ln in body), "\n".join(body)


def test_actions_are_pinned_by_sha():
    for line in ACTION.read_text().splitlines():
        m = re.match(r"\s*(- )?uses: (\S+)", line)
        if m:
            assert re.search(r"@[0-9a-f]{40}$", m[2]), line


def test_comment_inputs_exist_and_marker_matches_report():
    from readcost.report import COMMENT_MARKER

    text = ACTION.read_text()
    assert f'startswith("{COMMENT_MARKER}")' in text
    assert re.search(r'^  comment:\n(    .*\n)*?    default: "false"$', text, re.MULTILINE)
    assert re.search(r'^  changed-only:\n(    .*\n)*?    default: "true"$', text, re.MULTILINE)
