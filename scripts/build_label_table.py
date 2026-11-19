"""Build eval/labels/labels.jsonl, every label the evaluations collected, from the rater manifest.

    python3 -I scripts/build_label_table.py           # write eval/labels/labels.jsonl
    python3 -I scripts/build_label_table.py --check   # exit 1 if the file is stale or a label file is unlisted

eval/labels/raters.json lists one entry per rater file: its round, rater id, model, family, protocol
(primed or unprimed), rubric, how it was run and notes. This script reads each listed file, joins each
label to its item's rule, stratum, kind and item type from the round's sample.jsonl, and writes one row
per (round, item, rater). Rows follow the manifest's order of raters, then item id, so a rater added at
the end of the manifest adds rows at the end of the file. The table holds ids, labels and the raters'
short causes, no source text. See eval/labels/README.md.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = Path("eval/labels/raters.json")
TABLE = Path("eval/labels/labels.jsonl")
FIELDS = ("round", "item", "rater", "model", "family", "protocol", "label", "construction_present", "cause",
          "rule", "stratum", "kind", "item_type", "decoy")
RATER_FIELDS = ("round", "rater", "file", "model", "family", "protocol")
LABELS = {"c", "d", "w"}
ITEM_TYPES = {"finding", "near", "decoy", "ranked"}


class TableError(Exception):
    pass


def item_key(item: str):
    return (0, int(item), "") if item.isdigit() else (1, 0, item)


def read_labels(path: Path) -> list[dict]:
    """A rater file as a list of {item, label, present, cause}, in file order.

    Two shapes are read: a JSON list of {"id", "label", "construction_present", "cause"} (the rounds in
    eval/<round>/labels/), and {"rater": ..., "labels": {key: {"label", "present", "cause"}}} (the
    in-sample files in eval/labels/). "i" is read for "id" and "present" for "construction_present".
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("labels"), dict):
        entries = [{"id": k, **v} for k, v in data["labels"].items()]
    elif isinstance(data, dict) and isinstance(data.get("labels"), list):
        entries = data["labels"]
    elif isinstance(data, list):
        entries = data
    else:
        raise TableError(f"{path}: not a label file")
    out = []
    for e in entries:
        item = e.get("id", e.get("i"))
        if item is None:
            raise TableError(f"{path}: an entry has no id")
        label = e.get("label")
        if label not in LABELS:
            raise TableError(f"{path}: item {item}: label {label!r} is not c, d or w")
        present = e.get("construction_present", e.get("present"))
        if present is not None and not isinstance(present, bool):
            raise TableError(f"{path}: item {item}: present {present!r} is not true, false or absent")
        cause = e.get("cause")
        out.append({"item": str(item), "label": label, "present": present,
                    "cause": cause if isinstance(cause, str) else None})
    return out


def read_sample(path: Path) -> dict[str, dict]:
    items: dict[str, dict] = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        decoy = row.get("decoy")
        item_type = row.get("item") or ("decoy" if decoy else "finding")
        if item_type not in ITEM_TYPES:
            raise TableError(f"{path}:{n}: item type {item_type!r}")
        info = {"rule": row.get("rule") or None, "stratum": row.get("stratum") or None,
                "kind": row.get("kind") or None, "item_type": item_type, "decoy": decoy or None}
        key = str(row["i"])
        if key in items and items[key] != info:
            raise TableError(f"{path}:{n}: item {key} appears twice with different rule, stratum or type")
        items.setdefault(key, info)
    return items


def label_files(root: Path) -> list[Path]:
    """Every rater file under eval/: eval/labels/*.json and eval/<round>/labels/*.json."""
    found = set((root / "eval" / "labels").glob("*.json")) | set((root / "eval").glob("*/labels/*.json"))
    found.discard(root / MANIFEST)
    return sorted(found)


def build(root: Path = ROOT) -> list[dict]:
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    rounds = {r["round"]: r for r in manifest["rounds"]}
    seen_raters: set[tuple[str, str]] = set()
    listed: set[Path] = set()
    for r in manifest["raters"]:
        missing = [f for f in RATER_FIELDS if not r.get(f)]
        if missing:
            raise TableError(f"manifest entry {r.get('round')}/{r.get('rater')}: missing {', '.join(missing)}")
        if r["round"] not in rounds:
            raise TableError(f"manifest entry {r['round']}/{r['rater']}: round not in the manifest's rounds")
        if r["protocol"] not in ("primed", "unprimed"):
            raise TableError(f"manifest entry {r['round']}/{r['rater']}: protocol {r['protocol']!r}")
        if (r["round"], r["rater"]) in seen_raters:
            raise TableError(f"manifest lists {r['round']}/{r['rater']} twice")
        seen_raters.add((r["round"], r["rater"]))
        listed.add(root / r["file"])
    unlisted = [p.relative_to(root).as_posix() for p in label_files(root) if p not in listed]
    if unlisted:
        raise TableError("label files not in eval/labels/raters.json: " + ", ".join(unlisted))

    samples = {name: read_sample(root / r["sample"]) if r.get("sample") else None for name, r in rounds.items()}
    rows = []
    for r in manifest["raters"]:
        path = root / r["file"]
        if not path.is_file():
            raise TableError(f"manifest entry {r['round']}/{r['rater']}: {r['file']} does not exist")
        sample = samples[r["round"]]
        by_item: dict[str, dict] = {}
        for e in read_labels(path):
            first = by_item.get(e["item"])
            if first is None:
                by_item[e["item"]] = e
            elif (first["label"], first["present"]) != (e["label"], e["present"]):
                raise TableError(f"{r['file']}: item {e['item']} labelled twice, differently")
        for item in sorted(by_item, key=item_key):
            e = by_item[item]
            if sample is None:
                info = {"rule": None, "stratum": None, "kind": None, "item_type": "finding", "decoy": None}
            elif item in sample:
                info = sample[item]
            else:
                raise TableError(f"{r['file']}: item {item} is not in {rounds[r['round']]['sample']}")
            rows.append({"round": r["round"], "item": item, "rater": r["rater"], "model": r["model"],
                         "family": r["family"], "protocol": r["protocol"], "label": e["label"],
                         "construction_present": e["present"], "cause": e["cause"], **info})
    return rows


def render(rows: list[dict]) -> str:
    return "".join(json.dumps({k: row[k] for k in FIELDS}, ensure_ascii=False, separators=(",", ":")) + "\n"
                   for row in rows)


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="fail if labels.jsonl is stale; write nothing")
    args = ap.parse_args(argv)
    try:
        text = render(build(root))
    except TableError as e:
        print(f"build_label_table: {e}", file=sys.stderr)
        return 1
    out = root / TABLE
    if args.check:
        if not out.is_file() or out.read_text(encoding="utf-8") != text:
            print(f"build_label_table: {TABLE} is stale; run python3 -I scripts/build_label_table.py",
                  file=sys.stderr)
            return 1
        return 0
    out.write_text(text, encoding="utf-8")
    print(f"wrote {TABLE}: {text.count(chr(10))} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
