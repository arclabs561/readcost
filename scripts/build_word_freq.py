# /// script
# dependencies = ["pyarrow>=15"]
# ///
"""Count lowercase word tokens in FineWeb-Edu parquet shards.

    uv run scripts/build_word_freq.py OUT.tsv SHARD.parquet [SHARD.parquet ...]

Writes "#tokens<TAB>N" then "word<TAB>count" for words seen 20+ times to
OUT.tsv, and the same compressed to src/readcost/data/word_freq.txt.gz. The
shipped file counts shards 0 and 1 of FineWeb-Edu CC-MAIN-2019-04
(1,198,367,072 tokens); see data/FINEWEB_NOTICE.
"""
import collections
import gzip
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pyarrow.parquet as pq

WORD = re.compile(r"[a-z]+(?:'[a-z]+)?")


def count(path: str) -> collections.Counter:
    c: collections.Counter = collections.Counter()
    for batch in pq.ParquetFile(path).iter_batches(batch_size=2048, columns=["text"]):
        for text in batch.column(0).to_pylist():
            c.update(WORD.findall(text.lower()))
    return c


def main(out: str, shards: list[str]) -> None:
    total: collections.Counter = collections.Counter()
    with ProcessPoolExecutor(max_workers=len(shards)) as ex:
        for c in ex.map(count, shards):
            total.update(c)
    n = sum(total.values())
    with open(out, "w") as fh:
        fh.write(f"#tokens\t{n}\n")
        for w, k in total.most_common():
            if k < 20:
                break
            fh.write(f"{w}\t{k}\n")
    data = Path(__file__).resolve().parent.parent / "src/readcost/data/word_freq.txt.gz"
    data.write_bytes(gzip.compress(Path(out).read_bytes(), mtime=0))
    print(n, "tokens,", sum(1 for k in total.values() if k >= 20), "words with 20+")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
