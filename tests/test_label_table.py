"""eval/labels/labels.jsonl against its builder, and the builder on made-up files."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("build_label_table", SCRIPTS / "build_label_table.py")
table = importlib.util.module_from_spec(spec)
spec.loader.exec_module(table)


def test_committed_table_is_current():
    # Fails when a label file or the manifest changed and labels.jsonl was not rebuilt, or when a
    # label file under eval/ is missing from eval/labels/raters.json.
    rows = table.build(ROOT)
    assert (ROOT / table.TABLE).read_text(encoding="utf-8") == table.render(rows), (
        "eval/labels/labels.jsonl is stale: run python3 -I scripts/build_label_table.py")


def test_every_label_file_is_in_the_manifest():
    manifest = json.loads((ROOT / table.MANIFEST).read_text(encoding="utf-8"))
    listed = {ROOT / r["file"] for r in manifest["raters"]}
    assert set(table.label_files(ROOT)) == listed


def make_repo(tmp_path: Path, raters: list[dict]) -> Path:
    (tmp_path / "eval" / "labels").mkdir(parents=True)
    (tmp_path / "eval" / "r1" / "labels").mkdir(parents=True)
    sample = [{"i": 200, "rule": "stacked-nouns", "stratum": "md", "kind": "Markdown", "item": "finding"},
              {"i": 30, "rule": "inline-list", "stratum": "md", "kind": "Markdown", "item": "near"},
              {"i": 30, "rule": "inline-list", "stratum": "md", "kind": "Markdown", "item": "near"},
              {"i": 4, "rule": "long-dependency", "stratum": "S1", "decoy": "long"}]
    (tmp_path / "eval" / "r1" / "sample.jsonl").write_text("".join(json.dumps(s) + "\n" for s in sample))
    (tmp_path / "eval" / "r1" / "labels" / "a.json").write_text(json.dumps([
        {"id": 200, "label": "c", "construction_present": True, "cause": "made up"},
        {"id": 30, "label": "w", "construction_present": False, "cause": "first"},
        {"id": 30, "label": "w", "construction_present": False, "cause": "second"},
        {"id": 4, "label": "d", "construction_present": True}]))
    (tmp_path / "eval" / "r1" / "labels" / "b.json").write_text(json.dumps([
        {"id": 4, "label": "w", "cause": "plain"}, {"id": 200, "label": "d", "cause": ""}]))
    (tmp_path / "eval" / "labels" / "old.json").write_text(json.dumps(
        {"rater": "x", "labels": {"ffff000011112222": {"label": "w", "present": False, "cause": "idiom"}}}))
    manifest = {"rounds": [{"round": "r1", "dir": "eval/r1", "sample": "eval/r1/sample.jsonl"},
                           {"round": "old", "dir": "eval/labels", "sample": None}],
                "raters": raters}
    (tmp_path / "eval" / "labels" / "raters.json").write_text(json.dumps(manifest))
    return tmp_path


RATERS = [
    {"round": "old", "rater": "old", "file": "eval/labels/old.json", "model": "M0", "family": "F",
     "protocol": "primed"},
    {"round": "r1", "rater": "a", "file": "eval/r1/labels/a.json", "model": "M1", "family": "F",
     "protocol": "primed"},
    {"round": "r1", "rater": "b", "file": "eval/r1/labels/b.json", "model": "M2", "family": "G",
     "protocol": "unprimed"},
]


def test_rows_joined_ordered_and_deduplicated(tmp_path):
    rows = table.build(make_repo(tmp_path, RATERS))
    assert [(r["rater"], r["item"]) for r in rows] == [
        ("old", "ffff000011112222"), ("a", "4"), ("a", "30"), ("a", "200"), ("b", "4"), ("b", "200")]
    a30 = rows[2]
    assert (a30["cause"], a30["item_type"], a30["rule"]) == ("first", "near", "inline-list")
    b4 = rows[4]
    assert (b4["item_type"], b4["decoy"], b4["construction_present"], b4["protocol"]) == (
        "decoy", "long", None, "unprimed")
    assert rows[0]["rule"] is None and rows[0]["item_type"] == "finding"
    lines = table.render(rows).splitlines()
    assert list(json.loads(lines[0])) == list(table.FIELDS)


def test_check_mode(tmp_path):
    root = make_repo(tmp_path, RATERS)
    assert table.main(["--check"], root=root) == 1  # not built yet
    assert table.main([], root=root) == 0
    assert table.main(["--check"], root=root) == 0
    (root / "eval" / "r1" / "labels" / "b.json").write_text(json.dumps([{"id": 4, "label": "c"}]))
    assert table.main(["--check"], root=root) == 1


def test_unlisted_label_file_fails(tmp_path):
    root = make_repo(tmp_path, RATERS[:2])
    with pytest.raises(table.TableError, match="eval/r1/labels/b.json"):
        table.build(root)


def test_conflicting_duplicate_and_unknown_item_fail(tmp_path):
    root = make_repo(tmp_path, RATERS)
    path = root / "eval" / "r1" / "labels" / "b.json"
    path.write_text(json.dumps([{"id": 4, "label": "w"}, {"id": 4, "label": "c"}]))
    with pytest.raises(table.TableError, match="labelled twice"):
        table.build(root)
    path.write_text(json.dumps([{"id": 999, "label": "w"}]))
    with pytest.raises(table.TableError, match="not in"):
        table.build(root)
    path.write_text(json.dumps([{"id": 4, "label": "x"}]))
    with pytest.raises(table.TableError, match="not c, d or w"):
        table.build(root)
