"""Measure readcost's speed: cold start of the CLI and steady-state throughput.

    python3 -I scripts/bench_speed.py [FILES...] [--repeat 5]

Cold start is what a hook pays on every edit: a new `readcost check` process
on a short Markdown file, timed end to end. Throughput is words per second for
an Analyzer that is already loaded, over the given files (default: this
repository's README and docs). Reports the median of --repeat runs and the
spread, since a single timing on a laptop is noise.
"""

import argparse
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def cold_start(repeat: int) -> list[float]:
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "note.md"
        f.write_text("The index stores one list of documents for each term. You can search it from several threads.\n")
        times = []
        for _ in range(repeat):
            t = time.perf_counter()
            subprocess.run([sys.executable, "-m", "readcost", "check", str(f)], capture_output=True, check=False)
            times.append(time.perf_counter() - t)
    return times


def throughput(files: list[Path], repeat: int) -> tuple[int, list[float]]:
    from readcost import Analyzer, Config

    a = Analyzer(Config())
    texts = [(p.read_text(encoding="utf-8", errors="ignore"), str(p)) for p in files]
    a.check_text(texts[0][0], None, texts[0][1])  # load the model before timing
    words, times = 0, []
    for _ in range(repeat):
        t = time.perf_counter()
        words = sum(a.check_text(text, None, path).words for text, path in texts)
        times.append(time.perf_counter() - t)
    return words, times


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--repeat", type=int, default=5)
    args = ap.parse_args()
    files = args.files or [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
    cold = cold_start(args.repeat)
    words, times = throughput(files, args.repeat)
    rate = [words / t for t in times]
    print(f"cold start, short file: median {statistics.median(cold):.2f} s "
          f"(min {min(cold):.2f}, max {max(cold):.2f}, n={args.repeat})")
    print(f"throughput, loaded: median {statistics.median(rate):,.0f} words/s over {words:,} words "
          f"(min {min(rate):,.0f}, max {max(rate):,.0f}, n={args.repeat})")


if __name__ == "__main__":
    main()
