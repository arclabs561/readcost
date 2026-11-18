"""Can word-pair counts or the document tell an established term from a coined noun stack?

    python3 scripts/eval_stack_terms.py --bench BENCH_DIR [--corpus ref/eval] [--pairs open_pairs.npz]

stacked-nouns and hyphen-compound report "goroutine call stack" and "pull
request description" as readily as a stack the writer coined. This script
takes the findings that have labels and asks which evidence separates the
accepted ones from the rejected ones:

- the pair lists readcost ships (hyphenated pairs from FineWeb-Edu, WordNet's
  two-word entries);
- counts of adjacent open pairs ("call stack") from scripts/build_open_pairs.py,
  as document frequency and as pointwise mutual information (``--pairs``);
- bracketing a three-noun stack by which pair is stronger, under the
  adjacency model (A B against B C) and the dependency model (A B against
  A C; Lauer 1995);
- the document: the stack occurs again in it, or is introduced as a term.

Labelled findings come from two places. ``--bench`` is the directory written
by scripts/fetch_rulebench.py: a finding on an expected-fire item counts as
accepted, one on a trap as rejected. ``--corpus`` is the evaluation corpus
from scripts/fetch_eval_corpus.py: a finding whose hash is in eval/labels/
counts as accepted when most of the eight strict raters labelled it correct
or defensible. Every other finding of the two rules in the corpus's essays
and documentation is used only to say how many findings an exemption would
remove.

For each candidate exemption the script prints how many accepted and how
many rejected findings it would drop and the precision before and after,
with 95% Wilson intervals. It gates nothing.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
RULES = ("stacked-nouns", "hyphen-compound")
WORD = re.compile(r"[a-z]+")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for k successes in n trials, as fractions."""
    if not n:
        return (0.0, 1.0)
    p = k / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (centre - half) / (1 + z * z / n)), min(1.0, (centre + half) / (1 + z * z / n)))


def share(k: int, n: int) -> str:
    if not n:
        return "none"
    lo, hi = wilson(k, n)
    return f"{k} of {n} ({100 * k / n:.0f}%, {100 * lo:.0f} to {100 * hi:.0f})"


def stack_words(excerpt: str) -> list[str]:
    """The words of a finding's excerpt, lower case, a hyphenated pair as two words."""
    return WORD.findall(excerpt.lower())


def occurrences(excerpt: str, document: str) -> int:
    """Times the excerpt's words occur in the document as a phrase, hyphen or space between them."""
    words = stack_words(excerpt)
    if not words:
        return 0
    return len(re.findall(r"(?<![a-z])" + r"[\s-]+".join(words) + r"(?![a-z])", document.lower()))


def introduced(excerpt: str, document: str) -> bool:
    """True when the document presents the phrase as a term: defined, named, quoted or emphasised."""
    words = stack_words(excerpt)
    if not words:
        return False
    phrase = r"[\s-]+".join(words)
    patterns = (
        phrase + r"\s+(?:is|are|means|refers to)\s+(?:an?|the)\b",   # "A B C is a ..."
        r"(?:called|termed|named|known as)\s+(?:an?\s+|the\s+)?[\"'*_`“]?" + phrase,
        r"[\"*_`“]" + phrase + r"[\"*_`”]",                # quoted or emphasised
        phrase + r"\s+\([A-Za-z]{2,}\)",                              # "A B C (ABC)"
        r"^#+ .*" + phrase,                                           # in a heading
    )
    text = document.lower()
    return any(re.search(p, text, re.MULTILINE) for p in patterns)


class Evidence:
    """What is known about one finding's stack, computed once."""

    def __init__(self, excerpt: str, document: str, pairs=None):
        from readcost.lexicon import is_established_pair, is_lexicalized

        self.words = stack_words(excerpt)
        self.adjacent = list(zip(self.words, self.words[1:]))
        self.shipped = [is_established_pair(a, b) or is_lexicalized(a, b) for a, b in self.adjacent]
        self.count = occurrences(excerpt, document)
        self.introduced = introduced(excerpt, document)
        self.df = [pairs.df(a, b) for a, b in self.adjacent] if pairs else []
        self.pmi = [pairs.pmi(a, b) for a, b in self.adjacent] if pairs else []
        # The dependency model's pair for a three-word stack: does A modify C?
        self.skip = pairs.pmi(self.words[0], self.words[2]) if pairs and len(self.words) == 3 else None

    def attested(self, min_docs: int, min_pmi: float) -> list[bool]:
        return [n >= min_docs and p is not None and p >= min_pmi for n, p in zip(self.df, self.pmi)]

    def weakest(self) -> float:
        """PMI of the weakest adjacent pair; minus infinity when one is unattested."""
        return min((p if p is not None else -math.inf for p in self.pmi), default=-math.inf)

    def bracket(self, model: str) -> str:
        """left, right or unknown for a three-word stack under the adjacency or dependency model."""
        if len(self.words) != 3 or not self.pmi:
            return "n/a"
        first = self.pmi[0] if self.pmi[0] is not None else -math.inf
        other = self.pmi[1] if model == "adjacency" else self.skip
        other = other if other is not None else -math.inf
        if first == other:
            return "unknown"
        return "left" if first > other else "right"


def exemptions(with_pairs: bool) -> dict:
    """Name -> predicate over Evidence: True when the exemption would drop the finding."""
    out = {
        "shipped lists: every adjacent pair": lambda e: bool(e.shipped) and all(e.shipped),
        "shipped lists: some adjacent pair": lambda e: any(e.shipped),
        "occurs again in the document": lambda e: e.count >= 2,
        "occurs 3+ times in the document": lambda e: e.count >= 3,
        "introduced as a term in the document": lambda e: e.introduced,
    }
    if with_pairs:
        for docs, pmi in ((5, 0.0), (20, 0.0), (20, 3.0), (20, 6.0), (20, 9.0), (100, 6.0)):
            name = f"open pairs in {docs}+ documents, PMI {pmi:g}+"
            out[f"{name}: every adjacent pair"] = (
                lambda e, d=docs, p=pmi: bool(e.adjacent) and all(e.attested(d, p)))
            out[f"{name}: some adjacent pair"] = lambda e, d=docs, p=pmi: any(e.attested(d, p))
        out["open pairs in 20+ documents, PMI 6+: every pair, or it occurs again"] = (
            lambda e: (bool(e.adjacent) and all(e.attested(20, 6.0))) or e.count >= 2)
    return out


def auc(pos: list[float], neg: list[float]) -> float | None:
    """Chance that a rejected finding's value exceeds an accepted one's (ties count half)."""
    if not pos or not neg:
        return None
    wins = sum((n > p) + 0.5 * (n == p) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def bench_findings(bench: Path, analyzer) -> list[dict]:
    items = [json.loads(x) for x in (bench / "rulebench.jsonl").read_text().splitlines() if x.strip()]
    documents = {}
    path = bench / "documents.jsonl"
    if path.exists():
        for line in path.read_text().splitlines():
            row = json.loads(line)
            documents[row["source"]] = "\n".join(row["sentences"])
    out = []
    for it in items:
        if it["rule"] not in RULES:
            continue
        for f in analyzer.check_text(it["text"], "markdown").findings:
            if f.feature == it["rule"]:
                out.append({"split": "bench", "rule": f.feature, "accepted": it["expected"] == "fire",
                            "excerpt": f.excerpt, "document": documents.get(it["source"], it["text"])})
    return out


def corpus_findings(corpus: Path, analyzer) -> list[dict]:
    from eval_report import LENIENT, key, load_labels

    labels = load_labels()
    strict = [r for r in sorted(labels) if r not in LENIENT]
    manifest = json.loads((corpus / "manifest.json").read_text())
    out = []
    for e in manifest["entries"]:
        if e["category"] not in ("essay", "docs") or e["format"] == "source":
            continue
        text = (corpus / e["path"]).read_text(encoding="utf-8", errors="replace")
        for f in analyzer.check_text(text, e["format"], str(corpus / e["path"])).findings:
            if f.feature not in RULES:
                continue
            k = key({"id": e["id"], "feature": f.feature, "sentence": f.sentence})
            row = {"split": "corpus", "rule": f.feature, "accepted": None, "excerpt": f.excerpt, "document": text}
            if all(k in labels[r] for r in strict):
                row["split"] = "sample"
                row["accepted"] = sum(labels[r][k] in "cd" for r in strict) > len(strict) / 2
            out.append(row)
    return out


def report(findings: list[dict], pairs) -> list[str]:
    for f in findings:
        f["evidence"] = Evidence(f["excerpt"], f["document"], pairs)
    tests = exemptions(pairs is not None)
    out = ["## Noun stacks: established term or coined?", ""]
    for rule in RULES:
        of_rule = [f for f in findings if f["rule"] == rule]
        out += [f"### {rule}", ""]
        splits = [("bench", [f for f in of_rule if f["split"] == "bench"]),
                  ("sample", [f for f in of_rule if f["split"] == "sample"])]
        splits.append(("bench and sample", splits[0][1] + splits[1][1]))
        for name, rows in splits:
            good = sum(f["accepted"] for f in rows)
            out += [f"{name}: {len(rows)} labelled findings, accepted {share(good, len(rows))}.", ""]
            if not rows:
                continue
            out += ["| Exemption | Accepted dropped | Rejected dropped | Precision after |", "| --- | --- | --- | --- |"]
            for label, test in tests.items():
                hit = [f for f in rows if test(f["evidence"])]
                lost = sum(f["accepted"] for f in hit)
                kept = len(rows) - len(hit)
                out.append(f"| {label} | {lost} of {good} | {len(hit) - lost} of {len(rows) - good} | "
                           f"{share(good - lost, kept)} |")
            out.append("")
            if pairs is not None:
                pos = [f["evidence"].weakest() for f in rows if f["accepted"]]
                neg = [f["evidence"].weakest() for f in rows if not f["accepted"]]
                a = auc(pos, neg)
                if a is not None:
                    out += [(f"Weakest adjacent pair's PMI, rejected against accepted: AUC {a:.2f} "
                             f"({len(neg)} rejected, {len(pos)} accepted; 0.50 is chance)."), ""]
                for model in ("adjacency", "dependency"):
                    table = Counter((f["evidence"].bracket(model), f["accepted"]) for f in rows)
                    cells = [f"{side} {table[(side, True)]} accepted, {table[(side, False)]} rejected"
                             for side in ("left", "right", "unknown") if table[(side, True)] + table[(side, False)]]
                    if cells:
                        out += [f"Three-word stacks bracketed by the {model} model: " + "; ".join(cells) + ".", ""]
        rest = [f for f in of_rule if f["split"] != "bench"]
        if rest:
            out += [(f"All {len(rest)} findings in the corpus's essays and documentation, labelled or not: "
                     "share each exemption removes."), "", "| Exemption | Removed |", "| --- | --- |"]
            out += [f"| {label} | {share(sum(test(f['evidence']) for f in rest), len(rest))} |"
                    for label, test in tests.items()]
            out.append("")
    out += ["### Labelled findings", "",
            "| Rule | Split | Label | Stack | Times in document | Introduced | Shipped | Documents per pair | PMI per pair |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for f in findings:
        if f["accepted"] is None:
            continue
        e = f["evidence"]
        pmi = " ".join("none" if p is None else f"{p:.1f}" for p in e.pmi)
        out.append(f"| {f['rule']} | {f['split']} | {'accepted' if f['accepted'] else 'rejected'} | "
                   f"{' '.join(e.words)} | {e.count} | {'yes' if e.introduced else 'no'} | "
                   f"{' '.join('yes' if s else 'no' for s in e.shipped)} | {' '.join(map(str, e.df))} | {pmi} |")
    out.append("")
    if pairs is not None:
        out += ["### Size of an attested-pair list", "",
                f"{pairs.docs} documents, {pairs.positions} token positions, {len(pairs.vocab)} words, {len(pairs.keys)} pairs kept.", "",
                "| Documents | PMI | Pairs | As 5-byte hashes | Bloom filter, 1% false positives |",
                "| --- | --- | --- | --- | --- |"]
        for docs in (5, 20, 100):
            for pmi in (0.0, 3.0, 6.0, 9.0):
                n = len(pairs.select(docs, pmi))
                out.append(f"| {docs}+ | {pmi:g}+ | {n:,} | {5 * n / 1e6:.1f} MB | {9.6 * n / 8e6:.1f} MB |")
        out.append("")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bench", type=Path, help="directory written by scripts/fetch_rulebench.py")
    ap.add_argument("--corpus", type=Path, help="directory written by scripts/fetch_eval_corpus.py")
    ap.add_argument("--pairs", type=Path, help="table written by scripts/build_open_pairs.py")
    args = ap.parse_args()
    if not args.bench and not args.corpus:
        ap.error("give --bench, --corpus or both")
    from readcost import Analyzer, Config

    analyzer = Analyzer(Config())
    pairs = None
    if args.pairs:
        from build_open_pairs import Pairs

        pairs = Pairs(args.pairs)
    findings = bench_findings(args.bench, analyzer) if args.bench else []
    if args.corpus:
        findings += corpus_findings(args.corpus, analyzer)
    print("\n".join(report(findings, pairs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
