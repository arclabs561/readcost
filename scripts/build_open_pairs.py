# /// script
# dependencies = ["pyarrow>=15", "numpy>=1.26"]
# ///
"""Count adjacent word pairs ("call stack", "pull request") in FineWeb-Edu shards.

    uv run scripts/build_open_pairs.py SHARD.parquet [...] --out ref/pairs/open_pairs.npz
    uv run scripts/build_open_pairs.py --export ref/pairs/open_pairs.npz \
        --min-docs 20 --min-pmi 3 --to src/readcost/data/open_pairs.txt.gz

For every pair of words written next to each other with a space between
them, the first form counts the documents that contain it. Both words must
be in readcost's word list (data/word_freq.txt.gz) and neither may be a
function word, so "of the" is not counted and "call stack" is. The counts
are document frequencies, as in scripts/build_word_pairs.py, so that one
page repeating a phrase counts once. The file also holds each word's own
document frequency and the number of documents, which is what pointwise
mutual information needs:

    pmi(a, b) = log2( df(a b) * N / (df(a) * df(b)) )

Pairs seen in fewer than --keep documents (default 3) are dropped from the
output; a pair that rare is treated as unattested anyway. Only counts are
kept, no text. FineWeb-Edu is released under ODC-By 1.0; see
src/readcost/data/FINEWEB_NOTICE.

The second form writes the pairs that pass both thresholds as a sorted,
gzipped list of "a b" lines, the file readcost reads for
``stacked_nouns_terms = "attested"``.
"""
import argparse
import gzip
import re
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FREQ = ROOT / "src/readcost/data/word_freq.txt.gz"
# A word, or one character that is not part of a word. The second kind is
# kept so that "stack. Call" and "call-stack" do not count as adjacent words.
TOKEN = re.compile(r"[a-z]+|[^a-z\s]")
# Function words and the commonest verbs: a pair with one of these is not a compound.
STOP = frozenset("""
a about above after again against all also am an and any are as at be because been before being below between both
but by can could did do does doing down during each either else even ever every few for from further had has have having
he her here hers him his how however i if in into is it its just may me might more most much must my neither no nor not
now of off on once only or other our ours out over own per same shall she should so some such than that the their theirs
them then there these they this those though through to too under until up upon us very was we were what when where
which while who whom whose why will with within without would yet you your yours one two three many said says get got
make made use used using see seen like new well way
""".split())


def vocabulary(limit: int) -> list[str]:
    """The ``limit`` most frequent words of readcost's word list that can be half of a compound."""
    words = []
    with gzip.open(FREQ, "rt", encoding="utf-8") as lines:
        for line in lines:
            w = line.split("\t")[0]
            if w.isascii() and w.isalpha() and w.islower() and len(w) > 1 and w not in STOP:
                words.append(w)
                if len(words) == limit:
                    break
    return words


def merge(parts: list[tuple[np.ndarray, np.ndarray]]) -> tuple[np.ndarray, np.ndarray]:
    """Sum the counts of equal keys over several (keys, counts) tables."""
    keys = np.concatenate([p[0] for p in parts])
    counts = np.concatenate([p[1] for p in parts])
    if not len(keys):
        return keys.astype(np.int64), counts.astype(np.int64)
    order = np.argsort(keys, kind="stable")
    keys, counts = keys[order], counts[order]
    start = np.flatnonzero(np.r_[True, keys[1:] != keys[:-1]])
    return keys[start], np.add.reduceat(counts, start)


def count_texts(texts, ids: dict[str, int]) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """(pair keys, pair document counts, word document counts, documents) for an iterable of texts."""
    size = len(ids)
    uni = np.zeros(size, dtype=np.int64)
    parts: list[tuple[np.ndarray, np.ndarray]] = []
    pending: list[np.ndarray] = []
    docs = 0

    def flush() -> None:
        if pending:
            keys, counts = np.unique(np.concatenate(pending), return_counts=True)
            parts.append((keys, counts.astype(np.int64)))
            pending.clear()

    for text in texts:
        docs += 1
        seq = np.fromiter((ids.get(w, -1) for w in TOKEN.findall(text.lower())), dtype=np.int64)
        if len(seq) < 2:
            continue
        uni[np.unique(seq[seq >= 0])] += 1
        both = (seq[:-1] >= 0) & (seq[1:] >= 0)
        pending.append(np.unique(seq[:-1][both] * size + seq[1:][both]))
        if docs % 20000 == 0:
            flush()
    flush()
    keys, counts = merge(parts) if parts else (np.zeros(0, np.int64), np.zeros(0, np.int64))
    return keys, counts, uni, docs


def _count_group(job: tuple[str, int, int, str]) -> str:
    """Count one row group of a shard; the result goes to a file, since it is large."""
    import pyarrow.parquet as pq

    path, group, limit, tmp = job
    ids = {w: i for i, w in enumerate(vocabulary(limit))}
    texts = pq.ParquetFile(path).read_row_group(group, columns=["text"]).column(0).to_pylist()
    keys, counts, uni, docs = count_texts(texts, ids)
    out = Path(tmp) / f"{Path(path).stem}-{group}.npz"
    np.savez(out, keys=keys, counts=counts, uni=uni, docs=docs)
    return str(out)


def build(shards: list[str], out: Path, limit: int, keep: int, workers: int) -> None:
    import pyarrow.parquet as pq

    jobs = []
    with tempfile.TemporaryDirectory() as tmp:
        for shard in shards:
            jobs += [(shard, g, limit, tmp) for g in range(pq.ParquetFile(shard).metadata.num_row_groups)]
        uni = np.zeros(limit, dtype=np.int64)
        docs = 0
        table = (np.zeros(0, np.int64), np.zeros(0, np.int64))
        waiting: list[tuple[np.ndarray, np.ndarray]] = []
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for n, path in enumerate(ex.map(_count_group, jobs), 1):
                part = np.load(path)
                waiting.append((part["keys"], part["counts"]))
                uni[:len(part["uni"])] += part["uni"]
                docs += int(part["docs"])
                Path(path).unlink()
                # Merging sorts the whole table, so do it in large steps.
                if sum(len(k) for k, _ in waiting) >= 40_000_000 or n == len(jobs):
                    table = merge([table, *waiting])
                    waiting.clear()
                    print(f"{n}/{len(jobs)} row groups, {docs} documents, {len(table[0])} pairs", file=sys.stderr)
    keys, counts = table
    kept = counts >= keep
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, keys=keys[kept], counts=counts[kept].astype(np.int32), uni=uni.astype(np.int32),
                        docs=docs, vocab=np.array(vocabulary(limit)))
    print(f"{docs} documents, {len(keys)} pairs, {int(kept.sum())} in {keep}+ documents -> {out}")


class Pairs:
    """Lookup over a table written by build(): document counts and PMI of "a b"."""

    def __init__(self, path: Path | str):
        data = np.load(path)
        self.keys, self.counts, self.uni = data["keys"], data["counts"], data["uni"]
        self.docs = int(data["docs"])
        self.vocab = [str(w) for w in data["vocab"]]
        self.ids = {w: i for i, w in enumerate(self.vocab)}

    def df(self, a: str, b: str) -> int:
        """Documents that contain "a b"; 0 when either word is outside the vocabulary or the pair is rare."""
        i, j = self.ids.get(a), self.ids.get(b)
        if i is None or j is None:
            return 0
        key = i * len(self.vocab) + j
        k = int(np.searchsorted(self.keys, key))
        return int(self.counts[k]) if k < len(self.keys) and self.keys[k] == key else 0

    def pmi(self, a: str, b: str) -> float | None:
        """log2 of how much more often "a b" occurs than chance; None when it is not attested."""
        n = self.df(a, b)
        if not n:
            return None
        return float(np.log2(n * self.docs / (int(self.uni[self.ids[a]]) * int(self.uni[self.ids[b]]))))

    def select(self, min_docs: int, min_pmi: float) -> np.ndarray:
        """Indices of the pairs in at least ``min_docs`` documents with PMI of at least ``min_pmi``."""
        size = len(self.vocab)
        a, b = self.keys // size, self.keys % size
        with np.errstate(divide="ignore"):
            pmi = np.log2(self.counts.astype(np.float64) * self.docs / (self.uni[a].astype(np.float64) * self.uni[b]))
        return np.flatnonzero((self.counts >= min_docs) & (pmi >= min_pmi))

    def export(self, min_docs: int, min_pmi: float) -> list[str]:
        size = len(self.vocab)
        return sorted(f"{self.vocab[k // size]} {self.vocab[k % size]}" for k in self.keys[self.select(min_docs, min_pmi)])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shards", nargs="*")
    ap.add_argument("--out", type=Path, default=Path("ref/pairs/open_pairs.npz"))
    ap.add_argument("--vocab", type=int, default=100_000, help="most frequent words to count pairs of")
    ap.add_argument("--keep", type=int, default=3, help="drop pairs in fewer documents than this")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--export", type=Path, help="a table from an earlier run to write a pair list from")
    ap.add_argument("--min-docs", type=int, default=20)
    ap.add_argument("--min-pmi", type=float, default=3.0)
    ap.add_argument("--to", type=Path, default=ROOT / "src/readcost/data/open_pairs.txt.gz")
    args = ap.parse_args()
    if args.export:
        pairs = Pairs(args.export).export(args.min_docs, args.min_pmi)
        args.to.write_bytes(gzip.compress(("\n".join(pairs) + "\n").encode(), mtime=0))
        print(f"{len(pairs)} pairs in {args.min_docs}+ documents with PMI {args.min_pmi}+ -> {args.to} "
              f"({args.to.stat().st_size} bytes)")
        return 0
    if not args.shards:
        ap.error("give at least one parquet shard, or --export")
    build(args.shards, args.out, args.vocab, args.keep, args.workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
