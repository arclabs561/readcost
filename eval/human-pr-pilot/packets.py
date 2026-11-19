"""Build local editor and reviewer packets. Requires the frozen commits and their parents."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = {item["case"]: item for item in json.loads((HERE / "cases.json").read_text())}
# In adjacent pairs (A/B through K/L), the two editors receive opposite arms.
# Each tuple lists one editor's tasks in order and the cases that get feedback.
EDITORS = {
    "1": ("AB DC EF HG IJ LK".split(), "BDFHJL"),
    "2": ("KL JI GH FE CD BA".split(), "ACEGIK"),
}
# Each token is case + editor. Reviewers receive only task numbers.
REVIEWERS = [
    "A1 B1 C2 D2 E1 F1 G2 H2 I1 J1 K2 L2".split(),
    "A2 B2 C1 D1 E2 F2 G1 H1 I2 J2 K1 L1".split(),
    "L2 K2 J1 I1 H2 G2 F1 E1 D2 C2 B1 A1".split(),
    "L1 K1 J2 I2 H1 G1 F2 E2 D1 C1 B2 A2".split(),
]
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
    for editor, (pairs, guided) in EDITORS.items():
        directory = root / "editors" / editor
        directory.mkdir(parents=True)
        for index, label in enumerate("".join(pairs), start=1):
            case = CASES[label]
            stem = f"{index:02}-{label}"
            prompt = INSTRUCTION + "\n\n" + case["source"]
            if label in guided:
                prompt += "\n\n" + case["feedback"]
            (directory / f"{stem}.txt").write_text(prompt + "\n", encoding="utf-8")
            (directory / f"{stem}.diff").write_bytes(diffs[label])
            (directory / f"{label}.edit.txt").touch()


def reviewer_packets(root, diffs):
    edits = {}
    for editor, (pairs, _) in EDITORS.items():
        for label in "".join(pairs):
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
