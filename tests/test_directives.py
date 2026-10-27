"""readcost directives in Markdown comments that name rules turn off only those rules."""

from readcost.config import Config
from readcost.engine import Analyzer

# A stacked noun phrase and an inanimate subject in one sentence.
D = "We tune the shard compaction retry budget by hand, and it does not own indexing or compaction."


def found(text: str) -> list[tuple[int, str]]:
    return sorted((f.line, f.feature) for f in Analyzer(Config()).check_text(text, "markdown").findings)


def test_ignore_with_a_rule_drops_only_that_rule_in_the_next_block():
    assert found(f"<!-- readcost: ignore stacked-nouns -->\n{D}\n\n{D}\n") == [
        (2, "inanimate-subject"), (4, "inanimate-subject"), (4, "stacked-nouns")]


def test_ignore_without_rules_still_skips_the_block():
    assert found(f"<!-- readcost: ignore -->\n{D}\n") == []


def test_off_and_on_with_a_rule_bound_a_region():
    text = f"<!-- readcost: off stacked-nouns -->\n\n{D}\n\n<!-- readcost: on stacked-nouns -->\n\n{D}\n"
    assert found(text) == [(3, "inanimate-subject"), (7, "inanimate-subject"), (7, "stacked-nouns")]


def test_ignore_before_a_code_block_does_not_reach_the_paragraph_after_it():
    assert (6, "stacked-nouns") in found(f"<!-- readcost: ignore stacked-nouns -->\n```\ncode\n```\n\n{D}\n")


def test_ignore_before_a_list_covers_every_item():
    assert found(f"<!-- readcost: ignore stacked-nouns -->\n- {D}\n- {D}\n\n{D}\n") == [
        (2, "inanimate-subject"), (3, "inanimate-subject"), (5, "inanimate-subject"), (5, "stacked-nouns")]


def test_misspelled_rule_is_reported_in_a_note():
    r = Analyzer(Config()).check_text(f"<!-- readcost: ignore stacked-noun -->\n{D}\n", "markdown")
    assert {f.feature for f in r.findings} == {"inanimate-subject", "stacked-nouns"}
    assert r.notes == ["unknown rule in a readcost directive: stacked-noun; `readcost explain` lists the rules"]
