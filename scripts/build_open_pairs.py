# /// script
# dependencies = ["pyarrow>=15", "numpy>=1.26"]
# ///
"""Count adjacent word pairs ("call stack", "pull request") in FineWeb-Edu shards.

    uv run scripts/build_open_pairs.py SHARD.parquet [...] --out ref/pairs/open_pairs.npz
    uv run scripts/build_open_pairs.py --export ref/pairs/open_pairs.npz \
        --min-docs 20 --min-pmi 6 --to src/readcost/data/open_pairs.txt.gz

For every pair of words written next to each other with a space between
them, the first form counts the documents that contain it. Both words must
be in readcost's word list (data/word_freq.txt.gz) and neither may be a
function word, so "of the" is not counted and "call stack" is. The counts
are document frequencies, as in scripts/build_word_pairs.py, so that one
page repeating a phrase counts once. The file also holds how often each
word occurs and the number of token positions T, which is what pointwise
mutual information needs:

    pmi(a, b) = log2( df(a b) * T / (count(a) * count(b)) )

The pair's document count stands in for its frequency, so the measure is
a little low for a phrase that pages repeat.

``--phrases FILE`` also counts the documents that contain each longer
phrase listed in FILE, one per line ("time zone database"). A table of
every three-word sequence would be far larger than the pair table, so only
the phrases asked for are counted; scripts/eval_stack_terms.py --list-stacks
writes the ones its measurement needs. The last word matches with or
without a plural "s", and a hyphen between two words counts as a space.

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


def singular(word: str) -> str:
    """The word without a plural "s"; crude, and applied to both sides of a comparison."""
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def phrase_index(phrases: list[str]) -> dict[str, list[tuple[int, list[str], str]]]:
    """First word -> (position in ``phrases``, the words between, last word in the singular)."""
    index: dict[str, list[tuple[int, list[str], str]]] = {}
    for k, phrase in enumerate(phrases):
        words = phrase.split()
        if len(words) >= 3:
            index.setdefault(words[0], []).append((k, words[1:-1], singular(words[-1])))
    return index


def phrases_in(tokens: list[str], index: dict) -> set[int]:
    """Positions of the indexed phrases that occur in a token list."""
    found: set[int] = set()
    for i, tok in enumerate(tokens):
        for k, middle, last in index.get(tok, ()):
            end = i + 1 + len(middle)
            if end < len(tokens) and tokens[i + 1:end] == middle and singular(tokens[end]) == last:
                found.add(k)
    return found


def count_texts(texts, ids: dict[str, int], phrases: list[str] | None = None):
    """(pair keys, pair document counts, word counts, documents, token positions, phrase document counts)."""
    size = len(ids)
    index = phrase_index(phrases or [])
    phrase_df = np.zeros(len(phrases or []), dtype=np.int64)
    uni = np.zeros(size, dtype=np.int64)
    positions = 0
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
        tokens = TOKEN.findall(text.lower())
        if index:
            # A hyphen counts as a space here: "frame-pointer chain" is the phrase "frame pointer chain".
            phrase_df[list(phrases_in([t for t in tokens if t != "-"], index))] += 1
        seq = np.fromiter((ids.get(w, -1) for w in tokens), dtype=np.int64)
        positions += len(seq)
        if len(seq) < 2:
            continue
        uni += np.bincount(seq[seq >= 0], minlength=size)
        both = (seq[:-1] >= 0) & (seq[1:] >= 0)
        pending.append(np.unique(seq[:-1][both] * size + seq[1:][both]))
        if docs % 20000 == 0:
            flush()
    flush()
    keys, counts = merge(parts) if parts else (np.zeros(0, np.int64), np.zeros(0, np.int64))
    return keys, counts, uni, docs, positions, phrase_df


def _count_group(job: tuple[str, int, int, str, list[str]]) -> str:
    """Count one row group of a shard; the result goes to a file, since it is large."""
    import pyarrow.parquet as pq

    path, group, limit, tmp, phrases = job
    ids = {w: i for i, w in enumerate(vocabulary(limit))}
    texts = pq.ParquetFile(path).read_row_group(group, columns=["text"]).column(0).to_pylist()
    keys, counts, uni, docs, positions, phrase_df = count_texts(texts, ids, phrases)
    out = Path(tmp) / f"{Path(path).stem}-{group}.npz"
    np.savez(out, keys=keys, counts=counts, uni=uni, docs=docs, positions=positions, phrase_df=phrase_df)
    return str(out)


def build(shards: list[str], out: Path, limit: int, keep: int, workers: int, phrases: list[str]) -> None:
    import pyarrow.parquet as pq

    jobs = []
    with tempfile.TemporaryDirectory() as tmp:
        for shard in shards:
            jobs += [(shard, g, limit, tmp, phrases) for g in range(pq.ParquetFile(shard).metadata.num_row_groups)]
        uni = np.zeros(limit, dtype=np.int64)
        phrase_df = np.zeros(len(phrases), dtype=np.int64)
        docs = positions = 0
        table = (np.zeros(0, np.int64), np.zeros(0, np.int64))
        waiting: list[tuple[np.ndarray, np.ndarray]] = []
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for n, path in enumerate(ex.map(_count_group, jobs), 1):
                part = np.load(path)
                waiting.append((part["keys"], part["counts"]))
                uni[:len(part["uni"])] += part["uni"]
                docs += int(part["docs"])
                positions += int(part["positions"])
                phrase_df += part["phrase_df"]
                Path(path).unlink()
                # Merging sorts the whole table, so do it in large steps.
                if sum(len(k) for k, _ in waiting) >= 40_000_000 or n == len(jobs):
                    table = merge([table, *waiting])
                    waiting.clear()
                    print(f"{n}/{len(jobs)} row groups, {docs} documents, {len(table[0])} pairs", file=sys.stderr)
    keys, counts = table
    kept = counts >= keep
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, keys=keys[kept], counts=counts[kept].astype(np.int32), uni=uni,
                        docs=docs, positions=positions, vocab=np.array(vocabulary(limit)),
                        phrases=np.array(phrases, dtype=str), phrase_df=phrase_df)
    print(f"{docs} documents, {len(keys)} pairs, {int(kept.sum())} in {keep}+ documents -> {out}")


class Pairs:
    """Lookup over a table written by build(): document counts and PMI of "a b"."""

    def __init__(self, path: Path | str):
        data = np.load(path)
        self.keys, self.counts, self.uni = data["keys"], data["counts"], data["uni"]
        self.docs, self.positions = int(data["docs"]), int(data["positions"])
        self.vocab = [str(w) for w in data["vocab"]]
        self.ids = {w: i for i, w in enumerate(self.vocab)}
        self.phrases = ({str(p): int(n) for p, n in zip(data["phrases"], data["phrase_df"])}
                        if "phrases" in data else {})

    def phrase_df(self, words: list[str]) -> int | None:
        """Documents that contain the whole phrase; None when it was not among the phrases counted."""
        return self.phrases.get(" ".join(words))

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
        return float(np.log2(n * self.positions / (int(self.uni[self.ids[a]]) * int(self.uni[self.ids[b]]))))

    def select(self, min_docs: int, min_pmi: float) -> np.ndarray:
        """Indices of the pairs in at least ``min_docs`` documents with PMI of at least ``min_pmi``."""
        size = len(self.vocab)
        a, b = self.keys // size, self.keys % size
        with np.errstate(divide="ignore"):
            pmi = np.log2(self.counts.astype(np.float64) * self.positions
                          / (self.uni[a].astype(np.float64) * self.uni[b]))
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
    ap.add_argument("--phrases", type=Path, help="longer phrases to count, one per line")
    ap.add_argument("--export", type=Path, help="a table from an earlier run to write a pair list from")
    ap.add_argument("--min-docs", type=int, default=20)
    ap.add_argument("--min-pmi", type=float, default=6.0)
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
    phrases = sorted(set(args.phrases.read_text().split("\n")) - {""}) if args.phrases else []
    build(args.shards, args.out, args.vocab, args.keep, args.workers, phrases)
    return 0


if __name__ == "__main__":
    sys.exit(main())
