"""Config validation, profile loading, CLI flag handling and output escaping."""

import dataclasses
import json
import math
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from readcost.config import Config, HookConfig, load_config
from readcost.engine import Analyzer, Result
from readcost.features import Finding
from readcost.profile import Profile, build_profile, load_profile
from readcost.report import agent, github, sarif

ROOT = Path(__file__).resolve().parents[1]
DENSE = ("It does not own indexing, segment selection, compaction, or reader visibility. "
         "The example prints the first snapshot-search cost with persisted region-index sidecars "
         "present versus after deleting those sidecars and forcing source-segment rebuilds.\n")
PLAIN = "The index stores one list per term.\n"


def run(args, stdin=None, cwd=None):
    return subprocess.run([sys.executable, "-m", "readcost", *args], input=stdin,
                          capture_output=True, text=True, cwd=cwd)


def write_cfg(tmp_path, body, name="readcost.toml"):
    p = tmp_path / name
    p.write_text(body)
    return p


def finding(path="a.md", line=3, severity="error", message="5 nouns in a row", feature="stacked-nouns"):
    return Finding(feature=feature, severity=severity, message=message, excerpt="x", sentence="x",
                   path=path, line=line, suggestion="Unpack it")


# --- config validation -------------------------------------------------------

@pytest.mark.parametrize("body, key", [
    ('[readcost.hooks]\nexclude = "CHANGELOG*"\n', "hooks.exclude"),
    ('[readcost.hooks]\npaths = "*.md"\n', "hooks.paths"),
    ('[readcost]\nallow = "foo"\n', "allow"),
    ('[readcost]\nenable = "long-sentence"\n', "enable"),
    ('[readcost.hooks]\nmode = "Block"\n', "hooks.mode"),
    ('[readcost.hooks]\nstop = "yes"\n', "hooks.stop"),
    ('[readcost.hooks]\ndisplay = "on"\n', "hooks.display"),
    ('[readcost]\nmin_severity = "warning"\n', "min_severity"),
    ('[readcost]\nadvise_severity = "Error"\n', "advise_severity"),
    ('[readcost]\ncomments = "some"\n', "comments"),
    ('[readcost]\nblock_cost_index = "high"\n', "block_cost_index"),
    ('[readcost.hooks]\nedited_lines_only = "yes"\n', "hooks.edited_lines_only"),
    ('[readcost]\ndisable = ["no-such-feature"]\n', "disable"),
    ('[readcost]\nhooks = "advise"\n', "hooks"),
])
def test_invalid_config_value_names_file_and_key(tmp_path, body, key):
    p = write_cfg(tmp_path, body)
    with pytest.raises(ValueError) as exc:
        load_config(str(p))
    assert str(p) in str(exc.value) and key in str(exc.value)


def test_invalid_config_exits_2_with_message(tmp_path):
    write_cfg(tmp_path, '[readcost.hooks]\nmode = "Block"\n')
    proc = run(["check", "-"], PLAIN, tmp_path)
    assert proc.returncode == 2 and "hooks.mode" in proc.stderr and "readcost.toml" in proc.stderr


def test_toml_syntax_error_names_file(tmp_path):
    p = write_cfg(tmp_path, "[readcost\nmodel = 1\n")
    with pytest.raises(ValueError) as exc:
        load_config(str(p))
    assert str(p) in str(exc.value)


def test_unknown_key_warns_with_name(tmp_path, capsys):
    p = write_cfg(tmp_path, '[readcost.hook]\nmode = "block"\n[readcost]\nmodle = "x"\n')
    load_config(str(p))
    err = capsys.readouterr().err
    assert "hook" in err and "modle" in err and str(p) in err


def test_top_level_keys_merge_with_readcost_table(tmp_path):
    p = write_cfg(tmp_path, 'allow = ["foo bar"]\n[readcost]\nmodel = "en_core_web_md"\n')
    cfg = load_config(str(p))
    assert cfg.allow == ["foo bar"] and cfg.model == "en_core_web_md"


def test_key_both_top_level_and_in_table_is_error(tmp_path):
    p = write_cfg(tmp_path, 'model = "a"\n[readcost]\nmodel = "b"\n')
    with pytest.raises(ValueError, match="model"):
        load_config(str(p))


def test_advise_severity_off_disables_the_rule(tmp_path):
    cfg = load_config(str(write_cfg(tmp_path, '[readcost]\nadvise_severity = "off"\n')))
    result = Result(path="a.md", words=1000, findings=[finding()])
    Analyzer(cfg)._verdict(result)
    assert result.verdict == "pass"
    result = Result(path="a.md", words=1000, findings=[finding()])
    Analyzer(Config())._verdict(result)
    assert result.verdict == "advise"


def test_example_lists_every_key_with_default_values():
    example = ROOT / "readcost.toml.example"
    table = tomllib.loads(example.read_text())["readcost"]
    top = {f.name for f in dataclasses.fields(Config)} - {"source"}
    assert set(table) == top
    assert set(table["hooks"]) == {f.name for f in dataclasses.fields(HookConfig)}
    loaded = load_config(str(example))
    assert dataclasses.replace(loaded, source="") == Config()


# --- profiles ----------------------------------------------------------------

def default_profile_dict():
    return json.loads(load_profile("default").to_json())


def test_relative_profile_resolves_against_config_dir(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / ".git").mkdir()
    (repo / "prof.json").write_text(json.dumps(default_profile_dict()))
    write_cfg(repo, '[readcost]\nprofile = "prof.json"\n')
    monkeypatch.chdir(repo / "docs")
    cfg = load_config(start=str(repo / "docs"))
    assert load_profile(cfg.profile).name == default_profile_dict()["name"]


def test_profile_with_extra_keys_loads(tmp_path):
    d = default_profile_dict() | {"future_field": 1}
    p = tmp_path / "p.json"
    p.write_text(json.dumps(d))
    assert load_profile(str(p)).dep_fit == tuple(d["dep_fit"])


def test_profile_missing_dep_fit_names_file(tmp_path):
    d = default_profile_dict()
    del d["dep_fit"]
    p = tmp_path / "p.json"
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError) as exc:
        load_profile(str(p))
    assert str(p) in str(exc.value) and "dep_fit" in str(exc.value)


@pytest.mark.parametrize("fit", [[1.0, 0.5, 0.0], [1.0, 0.5, "NaN"], [1.0, 0.5], [1.0, "x", 0.4]])
def test_degenerate_dep_fit_rejected(tmp_path, fit):
    p = tmp_path / "p.json"
    text = json.dumps(default_profile_dict() | {"dep_fit": fit}).replace('"NaN"', "NaN")
    p.write_text(text)
    with pytest.raises(ValueError, match="dep_fit"):
        load_profile(str(p))


def test_build_profile_reads_comments_setting(tmp_path):
    src = tmp_path / "mod.py"
    src.write_text("\n\n".join(
        f"# The parser reads line {i} and writes " + "one more record " * (i % 4)
        + f"to the output file.\nx{i} = {i}" for i in range(15)) + "\n")
    cfg = Config(comments="all")
    placeholder = Profile("placeholder", 0, 0, (0.0, 0.78, 0.42))
    prof = build_profile([str(src)], "c", lambda: Analyzer(cfg, placeholder))
    assert prof.sentences == 15 and math.isfinite(prof.dep_fit[2])


# --- CLI ---------------------------------------------------------------------

def test_lines_open_ranges(tmp_path):
    doc = tmp_path / "a.md"
    doc.write_text("\n".join(["Plain line."] * 10) + "\n\n" + DENSE)
    data = json.loads(run(["check", "-o", "json", "--fail-on", "never", "--lines", "11-", str(doc)],
                          cwd=tmp_path).stdout)
    assert data[0]["findings"]
    data = json.loads(run(["check", "-o", "json", "--fail-on", "never", "--lines", "-5", str(doc)],
                          cwd=tmp_path).stdout)
    assert not data[0]["findings"]


@pytest.mark.parametrize("spec", ["9-3", "abc", "1-2-3", "0-4"])
def test_bad_line_ranges_rejected(tmp_path, spec):
    proc = run(["check", "--lines", spec, "-"], PLAIN, tmp_path)
    assert proc.returncode == 2 and "--lines" in proc.stderr and "Traceback" not in proc.stderr


@pytest.mark.parametrize("flag", [["--last"], ["--lines", "1-3"]])
def test_per_record_rejects_last_and_lines(tmp_path, flag):
    f = tmp_path / "e.jsonl"
    f.write_text(json.dumps({"response": PLAIN}) + "\n")
    proc = run(["check", "--per-record", *flag, "--field", "response", str(f)], cwd=tmp_path)
    assert proc.returncode == 2 and "--per-record" in proc.stderr


def test_per_record_on_directory_includes_jsonl(tmp_path):
    d = tmp_path / "evals"
    d.mkdir()
    (d / "e.jsonl").write_text(json.dumps({"response": DENSE}) + "\n" + json.dumps({"response": PLAIN}) + "\n")
    data = json.loads(run(["check", "--per-record", "--field", "response", "-o", "json",
                           "--fail-on", "never", str(d)], cwd=tmp_path).stdout)
    assert [r["path"].rsplit("#", 1)[-1] for r in data] == ["line1", "line2"]


def test_transcript_format_on_markdown_warns(tmp_path):
    doc = tmp_path / "a.md"
    doc.write_text(DENSE)
    proc = run(["check", "-f", "transcript", "--fail-on", "never", str(doc)], cwd=tmp_path)
    assert "no" in proc.stderr and "a.md" in proc.stderr and "transcript" in proc.stderr


def test_disable_list_strips_whitespace(tmp_path):
    out = run(["check", "-o", "json", "--fail-on", "never", "--disable", "stacked-nouns, hyphen-compound",
               "-"], DENSE, tmp_path).stdout
    counts = json.loads(out)[0]["counts"]
    assert "hyphen-compound" not in counts and "stacked-nouns" not in counts


def test_enable_unknown_feature_is_usage_error(tmp_path):
    proc = run(["check", "--enable", "long-sentence, nope", "-"], PLAIN, tmp_path)
    assert proc.returncode == 2 and "nope" in proc.stderr


def test_bad_file_reports_path_and_run_continues(tmp_path):
    good = tmp_path / "good.md"
    good.write_text(PLAIN)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    proc = run(["check", str(tmp_path / "missing.md"), str(bad), str(good)], cwd=tmp_path)
    assert proc.returncode == 2
    assert "missing.md" in proc.stderr and "bad.json" in proc.stderr
    assert "good.md: pass" in proc.stdout


def test_directory_with_no_matching_files_says_so(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    (d / "data.csv").write_text("a,b\n")
    proc = run(["check", str(d)], cwd=tmp_path)
    assert "no files matched" in proc.stderr and str(d) in proc.stderr


def test_broken_pipe_exits_quietly(tmp_path):
    p = subprocess.Popen([sys.executable, "-m", "readcost", "explain"], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, cwd=tmp_path)
    p.stdout.close()
    err = p.stderr.read().decode()
    p.wait()
    assert err == "" and p.returncode != 2


# --- outputs -----------------------------------------------------------------

def test_github_escapes_properties_and_data():
    r = Result(path="a,b:c.md", findings=[finding(path="a,b:c.md", message="50% of it\rnow\nhere")])
    line = github([r])
    head, _, data = line.partition("::")[2].partition("::")
    assert "file=a%2Cb%3Ac.md," in head
    assert data.startswith("50%25 of it%0Dnow%0Ahere")
    assert "\r" not in line and "\n" not in line


def test_sarif_uris_are_encoded(tmp_path):
    abs_path = str(tmp_path / "x y.md")
    results = [Result(path=p, findings=[finding(path=p)]) for p in ("my docs/a%b.md", "<stdin>", abs_path)]
    locs = [r["locations"][0]["physicalLocation"]["artifactLocation"]
            for r in json.loads(sarif(results))["runs"][0]["results"]]
    assert locs[0] == {"uri": "my%20docs/a%25b.md", "uriBaseId": "%SRCROOT%"}
    assert "<" not in locs[1]["uri"] and "uriBaseId" not in locs[1]
    assert locs[2]["uri"].startswith("file://") and " " not in locs[2]["uri"]


def test_agent_limits_and_file_names():
    results = [Result(path=p, words=50, findings=[finding(path=p), finding(path=p, line=7)])
               for p in ("a.md", "b.md")]
    assert len(agent(results, max_chars=2)) <= 2
    assert len(agent(results, max_chars=10)) <= 10
    out = agent(results, max_items=-1)
    assert "...and 4 more" in out and "- " not in out.split("\n", 1)[0]
    out = agent(results)
    assert "a.md:3" in out and "b.md:7" in out
    single = agent(results[:1])
    assert "line 3" in single
