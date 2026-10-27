"""Fetch Python Enhancement Proposals as an evaluation category of specifications and design documents.

    git clone --depth 1 https://github.com/python/peps REF/peps/repo
    python3 -I scripts/fetch_peps.py REF/peps/repo REF/peps
    python3 scripts/eval_corpus.py REF/peps

Takes every PEP in the python/peps repository whose status is Final, Active
or Accepted and whose Copyright section places it in the public domain or
under CC0-1.0 (most PEPs say "placed in the public domain or under the
CC0-1.0-Universal license, whichever is more permissive"). Writes each PEP,
without its RFC 822 header, to REF/peps/<type>/pep-NNNN.rst and writes
REF/peps/manifest.json in the schema of scripts/fetch_eval_corpus.py:
category "pep", source the PEP type (standards-track, informational,
process), the URL on peps.python.org and the repository commit. The text
stays under REF, outside the repository.
"""

import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

STATUSES = {"Final", "Active", "Accepted"}


def main(repo: Path, ref: Path) -> None:
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True,
                            text=True, timeout=30).stdout.strip()
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entries, skipped = [], []
    for p in sorted((repo / "peps").glob("pep-*.rst")):
        text = p.read_text(encoding="utf-8")
        head, _, body = text.partition("\n\n")
        fields = dict(re.findall(r"^([A-Za-z-]+):\s*(.*)$", head, re.MULTILINE))
        num = int(fields.get("PEP", "0"))
        copyright_ = body[body.rfind("Copyright\n=========") :]
        if fields.get("Status", "").strip() not in STATUSES:
            continue
        if not re.search(r"public\s+domain|CC0", copyright_):
            skipped.append(num)
            continue
        kind = fields.get("Type", "").strip().lower().replace(" ", "-")
        rel = f"{kind}/pep-{num:04d}.rst"
        out = ref / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body)
        entries.append({"id": f"pep/{kind}/{num:04d}", "category": "pep", "source": kind,
                        "author": fields.get("Author", "").split("<")[0].strip(),
                        "url": f"https://peps.python.org/pep-{num:04d}/", "path": rel, "format": "rst",
                        "license": "public domain or CC0-1.0 (the PEP's Copyright section)",
                        "fetched_at": now, "via": f"github.com/python/peps@{commit}",
                        "sha256": hashlib.sha256(body.encode()).hexdigest(), "bytes": len(body.encode())})
    (ref / "manifest.json").write_text(json.dumps(
        {"description": "Final, Active and Accepted PEPs; see scripts/fetch_peps.py",
         "generated_at": now, "commit": commit, "entries": entries,
         "failures": [{"pep": n, "reason": "Copyright section is not public domain or CC0"} for n in skipped]},
        indent=1) + "\n")
    print(len(entries), "PEPs;", len(skipped), "skipped for licence")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
