import json
import subprocess
import sys

DENSE = ("It does not own indexing, segment selection, compaction, or reader visibility. "
         "The example prints the first snapshot-search cost with persisted region-index sidecars "
         "present versus after deleting those sidecars and forcing source-segment rebuilds. "
         "We tune the shard compaction retry budget by hand.\n")


def run(args, stdin=None, cwd=None):
    return subprocess.run([sys.executable, "-m", "readcost", *args], input=stdin,
                          capture_output=True, text=True, cwd=cwd)


def test_exit_codes(tmp_path):
    assert run(["check", "-"], DENSE, tmp_path).returncode == 1
    assert run(["check", "--fail-on", "never", "-"], DENSE, tmp_path).returncode == 0
    assert run(["check", "-"], "The index stores one list per term.\n", tmp_path).returncode == 0
    assert run(["check", str(tmp_path / "missing.md")], cwd=tmp_path).returncode == 2


def test_json_and_sarif_outputs_parse(tmp_path):
    data = json.loads(run(["check", "-o", "json", "--fail-on", "never", "-"], DENSE, tmp_path).stdout)
    assert data[0]["verdict"] == "block" and data[0]["counts"]["stacked-nouns"] >= 1
    sarif = json.loads(run(["check", "-o", "sarif", "--fail-on", "never", "-"], DENSE, tmp_path).stdout)
    assert sarif["version"] == "2.1.0" and sarif["runs"][0]["results"]


def test_github_annotations(tmp_path):
    out = run(["check", "-o", "github", "--fail-on", "never", "--stdin-name", "README.md", "-"], DENSE, tmp_path).stdout
    assert out.startswith("::") and "file=README.md" in out


def test_explain_and_version():
    assert "stacked-nouns" in run(["explain"]).stdout
    assert run(["explain", "nope"]).returncode == 2
    assert run(["--version"]).stdout.strip()


def test_profile_build(tmp_path):
    doc = tmp_path / "ref.md"
    doc.write_text("\n\n".join(f"The parser reads line {i} and writes " + "one more record " * (i % 4) + "to the output file." for i in range(15)))
    out = tmp_path / "p.json"
    assert run(["profile", "build", str(doc), "-o", str(out)], cwd=tmp_path).returncode == 0
    prof = json.loads(out.read_text())
    assert prof["sentences"] == 15 and len(prof["dep_fit"]) == 3


def test_per_record(tmp_path):
    f = tmp_path / "evals.jsonl"
    f.write_text(json.dumps({"response": DENSE}) + "\n" + json.dumps({"response": "The index stores one list per term."}) + "\n")
    data = json.loads(run(["check", "--format", "jsonl", "--field", "response", "--per-record", "-o", "json",
                           "--fail-on", "never", str(f)], cwd=tmp_path).stdout)
    assert [d["verdict"] for d in data] == ["block", "pass"]
    assert data[0]["path"].endswith("#line1")


def test_lsp_without_pygls_says_how_to_install():
    # A None entry in sys.modules makes `import pygls` raise ImportError, as when it is not installed.
    code = "import sys; sys.modules['pygls'] = None; from readcost.cli import main; sys.exit(main(['lsp']))"
    proc = subprocess.run([sys.executable, "-c", code], check=False, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert proc.returncode == 2
    assert proc.stderr.count("\n") == 1 and "pip install 'readcost[lsp]'" in proc.stderr


def test_readme_links_work_on_pypi():
    # PyPI renders README.md without the repository, so relative links break there.
    import re
    from pathlib import Path

    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text()
    relative = re.findall(r"\]\((?!https?:|#)([^)]+)\)", readme)
    assert relative == []
