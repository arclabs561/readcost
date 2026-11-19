"""The panel report on made-up labels."""

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("heldout_panel_report", SCRIPTS / "heldout_panel_report.py")
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)


def test_majority_counts_missing_labels_against():
    assert panel.majority(["c", "d", None], {"c", "d"})
    assert not panel.majority(["c", None, None], {"c", "d"})
    assert not panel.majority(["c"] * 6 + ["w"] * 6, {"c", "d"})  # six of twelve is not a majority
    assert panel.majority(["c"] * 7 + ["w"] * 5, {"c"})


def write(folder: Path, name: str, rows):
    (folder / f"{name}.json").write_text(json.dumps(rows))


def test_report_on_made_up_labels(tmp_path):
    sample = [{"i": 1, "stratum": "S1", "decoy": "", "rule": "stacked-nouns"},
              {"i": 2, "stratum": "S1", "decoy": "", "rule": "stacked-nouns"},
              {"i": 3, "stratum": "S1", "decoy": "random", "rule": "inline-list"}]
    for n, r in enumerate(panel.PRIMED):
        # item 1: everyone says c; item 2: Opus raters say d, others w; item 3: all w
        write(tmp_path, r, [{"id": 1, "label": "c", "construction_present": True},
                            {"id": 2, "label": "d" if n < 3 else "w", "construction_present": True},
                            {"id": 3, "label": "w", "construction_present": False}])
    for r in panel.UNPRIMED:
        write(tmp_path, r, [{"id": 1, "label": "d"}, {"id": 2, "label": "w"}, {"id": 3, "label": "w"}])
    res = panel.analyse(sample, panel.load(tmp_path, panel.PRIMED), panel.load(tmp_path, panel.UNPRIMED))
    row = res["strata"]["S1"]["rows"]["stacked-nouns"]
    assert (row["acc12"]["k"], row["acc12"]["n"]) == (1, 2)
    assert row["c12"]["k"] == 1
    assert row["models"]["Opus 5.5"]["k"] == 2 and row["models"]["Haiku 5.5"]["k"] == 1
    assert row["u_acc"]["k"] == 1 and row["u_c"]["k"] == 0
    assert res["strata"]["S1"]["rows"]["all decoys"]["acc12"]["k"] == 0
    text = panel.render(res)
    assert "| stacked-nouns | 1/2 (50%;" in text and "## S2" in text
