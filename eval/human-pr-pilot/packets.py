"""Build local editor and reviewer packets. Requires two commits and their parents."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = {item["case"]: item for item in json.loads((HERE / "cases.json").read_text())}
# A digit identifies the editor. Reviewers see only an ordinal for each task.
EDITORS = {"1": [("A", False), ("B", True)], "2": [("A", True), ("B", False)]}
REVIEWERS = [("A1", "B1"), ("A2", "B2"), ("B2", "A2"), ("B1", "A1")]
INSTRUCTION = "Revise this pull request description to make it easier to read. Keep every fact."


def frozen_diff(case):
    data = subprocess.check_output([
        "git", "diff", "--no-color", "--no-ext-diff", "--no-textconv", "--no-renames",
        "--full-index", "--diff-algorithm=myers", "--no-indent-heuristic", "--unified=3",
        "--src-prefix=a/", "--dst-prefix=b/", case["base"], case["head"], "--",
    ], cwd=HERE)
    if hashlib.sha256(data).hexdigest() != case["diff_sha256"]:
        raise SystemExit(f"Diff for {case['case']} differs from the frozen copy.")
    return data


def editor_packets(root, diffs):
    for editor, schedule in EDITORS.items():
        directory = root / "editors" / editor
        directory.mkdir(parents=True)
        for index, (label, questions) in enumerate(schedule, start=1):
            case = CASES[label]
            stem = f"{index:02}-{label}"
            prompt = INSTRUCTION + "\n\n" + case["source"]
            if questions:
                prompt += "\n\n" + case["feedback"]
            (directory / f"{stem}.txt").write_text(prompt + "\n", encoding="utf-8")
            (directory / f"{stem}.diff").write_bytes(diffs[label])
            (directory / f"{label}.edit.txt").touch()


def reviewer_packets(root, diffs):
    edits = {}
    for editor, schedule in EDITORS.items():
        for label, _ in schedule:
            path = root / "editors" / editor / f"{label}.edit.txt"
            value = path.read_text(encoding="utf-8").strip()
            if not value:
                raise SystemExit(f"Missing completed edit in {path}.")
            edits[label + editor] = value

    for index, schedule in enumerate(REVIEWERS, start=1):
        directory = root / "reviewers" / f"R{index}"
        directory.mkdir(parents=True)
        for task, token in enumerate(schedule, start=1):
            label = token[0]
            question = CASES[label]["question"]
            page = f"Question\n{question}\n\nPull request description\n{edits[token]}\n"
            (directory / f"{task:02}.txt").write_text(page, encoding="utf-8")
            (directory / f"{task:02}.diff").write_bytes(diffs[label])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("editors", "reviewers"))
    parser.add_argument("directory", type=Path, help="private pilot directory outside the repository")
    args = parser.parse_args()
    if (args.directory / args.stage).exists():
        parser.error(f"{args.stage} packets already exist")
    patches = {label: frozen_diff(case) for label, case in CASES.items()}
    if args.stage == "editors":
        editor_packets(args.directory, patches)
    else:
        reviewer_packets(args.directory, patches)
