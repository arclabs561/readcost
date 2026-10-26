# /// script
# dependencies = ["pyarrow>=15"]
# ///
"""Build src/readcost/data/hyphen_pairs.txt.gz from FineWeb-Edu parquet shards.

    uv run scripts/build_word_pairs.py SHARD.parquet [SHARD.parquet ...] [--min-docs 5]

The shipped file was built from shards 0 and 1 of the CC-MAIN-2019-04 crawl
(1,598,350 documents), downloaded from
huggingface.co/datasets/HuggingFaceFW/fineweb-edu/tree/main/data/CC-MAIN-2019-04.
A 2019 crawl predates widespread model-written web text, so the counts
describe human usage. A pair used in at least --min-docs documents is
treated as an established compound ("key-value", "set-top"); coinages such
as "storage-shrink" appear in none. Only the pair list is kept, no text.
FineWeb-Edu is released under ODC-By 1.0; see data/FINEWEB_NOTICE.
"""
import argparse
import collections
import gzip
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pyarrow.parquet as pq

# A word, a hyphen, a word; not part of a longer hyphen chain on either side.
PAIR = re.compile(r"(?<![\w-])([a-z]{2,})-([a-z]{2,})(?![\w-])")
OUT = Path(__file__).resolve().parent.parent / "src/readcost/data/hyphen_pairs.txt.gz"


def count(path: str) -> tuple[collections.Counter, int]:
    """Documents containing each pair, and the number of documents."""
    df: collections.Counter = collections.Counter()
    docs = 0
    for batch in pq.ParquetFile(path).iter_batches(batch_size=4096, columns=["text"]):
        for text in batch.column(0).to_pylist():
            docs += 1
            df.update({f"{a}-{b}" for a, b in PAIR.findall(text.lower())})
    return df, docs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("shards", nargs="+")
    ap.add_argument("--min-docs", type=int, default=5)
    args = ap.parse_args()
    total: collections.Counter = collections.Counter()
    ndocs = 0
    with ProcessPoolExecutor(max_workers=len(args.shards)) as ex:
        for df, docs in ex.map(count, args.shards):
            total.update(df)
            ndocs += docs
    pairs = sorted(p for p, n in total.items() if n >= args.min_docs)
    OUT.write_bytes(gzip.compress(("\n".join(pairs) + "\n").encode(), mtime=0))
    print(f"{ndocs} documents, {len(pairs)} pairs in {args.min_docs}+ documents -> {OUT}")


if __name__ == "__main__":
    main()
