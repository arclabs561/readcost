"""Rehearse the complete packet handoff with distinct placeholders for the 24 edits."""
import hashlib
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packets import CASES, HERE, INSTRUCTION

check = TestCase()


def rehearse(root):
    def run(stage, *, success=True):
        result = subprocess.run(
            [sys.executable, str(HERE / "packets.py"), stage, str(root)],
            capture_output=True, text=True,
        )
        check.assertEqual(result.returncode == 0, success, result.stderr)

    run("editors")
    run("reviewers", success=False)
    check.assertFalse((root / "reviewers").exists())
    check.assertEqual(len(CASES), 12)
    variants = {}
    for directory in sorted((root / "editors").iterdir()):
        arms = []
        labels = set()
        for patch in sorted(directory.glob("*.diff")):
            label = patch.stem.split("-")[1]
            case = CASES[label]
            labels.add(label)
            original = INSTRUCTION + "\n\n" + case["source"]
            prompt = patch.with_suffix(".txt").read_text()
            guided = prompt == original + "\n\n" + case["feedback"] + "\n"
            if not guided:
                check.assertEqual(prompt, original + "\n")
            arms.append(guided)
            check.assertEqual(hashlib.sha256(patch.read_bytes()).hexdigest(), case["diff_sha256"])
            edit = directory / f"{label}.edit.txt"
            check.assertEqual(edit.read_text(), "")
            placeholder = f"rehearsal edit {len(variants) + 1}"
            edit.write_text(placeholder)
            variants[placeholder] = (label, guided, directory.name)
        check.assertEqual(labels, set(CASES))
        check.assertEqual(arms.count(True), 6)
        check.assertTrue(all(arms[i] != arms[i + 1] for i in range(0, 12, 2)))

    check.assertEqual(len(variants), 24)
    run("reviewers")
    run("reviewers", success=False)
    uses = defaultdict(list)
    by_ordinal = Counter()
    case_arms = Counter()
    for directory in sorted((root / "reviewers").iterdir()):
        labels, arms, editors = [], [], []
        check.assertEqual(len(list(directory.iterdir())), 24)
        for i in range(12):
            page = directory / f"{i + 1:02}.txt"
            body = page.read_text()
            edit = body.splitlines()[-1]
            label, guided, editor = variants[edit]
            case = CASES[label]
            check.assertEqual(body, f"Question\n{case['question']}\n\nPull request description\n{edit}\n")
            check.assertEqual(hashlib.sha256(page.with_suffix(".diff").read_bytes()).hexdigest(),
                              case["diff_sha256"])
            labels.append(label)
            arms.append(guided)
            editors.append(editor)
            uses[edit].append(i)
            by_ordinal[i] += guided
            case_arms[label, guided] += 1
        check.assertCountEqual(labels, CASES.keys())
        check.assertCountEqual(arms, [True] * 6 + [False] * 6)
        check.assertCountEqual(editors, ["1"] * 6 + ["2"] * 6)
        check.assertTrue(all(arms[i] != arms[i + 1] for i in range(0, 12, 2)))

    check.assertEqual(set(uses), set(variants))
    check.assertEqual(by_ordinal, Counter({i: 2 for i in range(12)}))
    check.assertEqual(case_arms, Counter({(c, arm): 2 for c in CASES for arm in (False, True)}))
    for positions in uses.values():
        check.assertCountEqual([i % 2 for i in positions], [0, 1])
        check.assertCountEqual([i // 6 for i in positions], [0, 1])


if __name__ == "__main__":
    with TemporaryDirectory() as tmp:
        rehearse(Path(tmp))
    print("Verified 24 editor tasks, 48 blinded reviewer tasks and 12 frozen diffs.")
