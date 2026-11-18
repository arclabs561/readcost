"""long_dependency_gap = "content": long-dependency says what fills the gap and lowers a prepositional one to info."""

import subprocess
import sys
from pathlib import Path

import pytest

from readcost import Analyzer, Config
from readcost.config import load_config

PREPOSITIONAL = ("The configuration file for the service in the default directory on most Linux systems "
                 "under the home folder of the user is read at startup.")
OBJECT_RELATIVE = ("The report that the auditors from the regional office wrote during the long review "
                   "last spring was published in full.")
SUBJECT_RELATIVE = ("The report that described the outages in the regional office during the long review "
                    "last spring was published in full.")
LIST = ("Taking an order from table A, then an order from table B, then one from A again, and then one "
        "from B again would be a much slower process.")


@pytest.fixture(scope="module")
def words():
    return Analyzer(Config())


@pytest.fixture(scope="module")
def content():
    return Analyzer(Config(long_dependency_gap="content"))


def dep(a, text):
    return [(f.severity, f.message) for f in a.check_text(text, "markdown").findings
            if f.feature == "long-dependency"]


def test_default_is_words_and_leaves_findings_unchanged(words):
    assert Config().long_dependency_gap == "words"
    for text in (PREPOSITIONAL, OBJECT_RELATIVE, SUBJECT_RELATIVE, LIST):
        found = dep(words, text)
        assert found and all(sev == "warn" and "between" not in msg for sev, msg in found)


@pytest.mark.parametrize("text, severity, note", [
    (PREPOSITIONAL, "info", "only prepositional phrases in between"),
    (OBJECT_RELATIVE, "warn", "an object relative clause in between"),
    (SUBJECT_RELATIVE, "warn", "a clause in between"),
    # A list of objects is not a prepositional gap: raters accepted this one.
    (LIST, "warn", "no clause in between"),
])
def test_content_names_the_gap_and_lowers_only_prepositional_gaps(content, text, severity, note):
    [(sev, msg)] = dep(content, text)
    assert sev == severity and msg.endswith("; " + note)


def test_content_reports_the_same_arcs_as_words(words, content):
    for text in (PREPOSITIONAL, OBJECT_RELATIVE, SUBJECT_RELATIVE, LIST):
        before = [m for _, m in dep(words, text)]
        after = [m.rsplit("; ", 1)[0] for _, m in dep(content, text)]
        assert before == after


def test_a_rule_level_still_wins():
    a = Analyzer(Config(long_dependency_gap="content", rules={"long-dependency": "warn"}))
    assert [sev for sev, _ in dep(a, PREPOSITIONAL)] == ["warn"]


def test_lowering_a_gap_lowers_the_points(words, content):
    assert content.check_text(PREPOSITIONAL, "markdown").points < words.check_text(PREPOSITIONAL, "markdown").points


def test_config_key_loads_and_rejects_other_values(tmp_path):
    p = tmp_path / "readcost.toml"
    p.write_text('long_dependency_gap = "content"\n')
    assert load_config(str(p)).long_dependency_gap == "content"
    p.write_text('long_dependency_gap = "referents"\n')
    with pytest.raises(ValueError, match="must be one of words, content"):
        load_config(str(p))


def test_evaluation_script_documents_its_use():
    out = subprocess.run([sys.executable, "scripts/eval_gap_content.py"], capture_output=True, text=True,
                         cwd=Path(__file__).resolve().parent.parent)
    assert out.returncode == 2 and "eval_gap_content.py" in out.stderr
