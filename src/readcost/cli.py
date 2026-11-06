"""Command line: the subcommands that build_parser lists, and main."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

EXIT_OK, EXIT_FINDINGS, EXIT_USAGE = 0, 1, 2
EXIT_BROKEN_PIPE = 141  # 128 + SIGPIPE, what a shell reports for a reader that went away
VERDICT_RANK = {"pass": 0, "advise": 1, "block": 2}
RECORD_FORMATS = ("transcript", "messages", "jsonl")
LAST_LINE = 10**9  # stands in for "end of file" in an open range such as 40-


def _line_spec(spec: str | None) -> str | None:
    """Validate --lines and close open ranges: "40-" -> to the end, "-5" -> 1-5."""
    if spec is None:
        return None
    parts = []
    for part in spec.split(","):
        part = part.strip()
        m = re.fullmatch(r"(\d*)(-?)(\d*)", part)
        if not part or not m or not (m[1] or m[3]) or (not m[2] and not m[1]):
            raise ValueError(f"--lines: {part!r} is not a line or range; use e.g. 10-24,40 or 40-")
        lo = int(m[1]) if m[1] else 1
        hi = int(m[3]) if m[3] else (LAST_LINE if m[2] else lo)
        if lo < 1 or hi < lo:
            raise ValueError(f"--lines: {part!r} is not a valid range; lines start at 1 and a range "
                             "runs low to high")
        parts.append(f"{lo}-{hi}")
    return ",".join(parts)


def _feature_ids(value: str, flag: str) -> list[str]:
    from .config import unknown_features

    from .config import drop_retired

    ids = drop_retired([i.strip() for i in value.split(",") if i.strip()], flag)
    bad = unknown_features(ids)
    if bad:
        from .features import FEATURES

        raise ValueError(f"{flag}: unknown feature {', '.join(map(repr, bad))}; known: {', '.join(FEATURES)}")
    return ids


def _git_files(root: Path) -> list[Path] | None:
    """What git tracks or would track under ``root``, or None outside a work tree.

    Untracked nested repositories come back from git as directory entries
    ("sub/"); their own files are listed with their own ignore rules.
    """
    proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others",
                           "--exclude-standard"], capture_output=True)
    if proc.returncode != 0:
        return None
    out = []
    for name in proc.stdout.decode("utf-8", "replace").split("\0"):
        if not name:
            continue
        p = root / name
        if name.endswith("/") and (p / ".git").exists():
            out.extend(_git_files(p) or [])
        elif p.is_file():
            out.append(p)
    return out


def _walk(root: Path, respect_ignore_files: bool = True, prune=lambda path: False) -> list[Path]:
    """Files under ``root``, for checking a whole tree quickly.

    Inside a git work tree, what git tracks or would track. Elsewhere, a walk
    that never descends into hidden directories or ones ``prune`` matches
    (node_modules, target, .venv from [readcost.src] exclude), and that lists
    each git repository it meets by its own ignore files.
    """
    if respect_ignore_files:
        files = _git_files(root)
        if files is not None:
            return sorted(files)
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        if respect_ignore_files and here != root and (here / ".git").exists():
            out.extend(_git_files(here) or [])
            dirnames[:] = []
            continue
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and not prune(str(here / d) + "/"))
        out.extend(here / f for f in filenames if not f.startswith("."))
    return sorted(out)


def _load_config(args):
    from .config import load_config

    cfg = load_config(args.config, start=args.paths[0] if args.paths and args.paths[0] != "-" else None)
    if args.enable:
        cfg.enable += _feature_ids(args.enable, "--enable")
    if args.disable:
        cfg.disable += _feature_ids(args.disable, "--disable")
    if args.profile:
        cfg.profile = args.profile
    for level in ("error", "warn", "info", "ignore"):
        for value in getattr(args, level):
            for rule in (r.strip() for r in value.split(",") if r.strip()):
                if rule != "all":
                    _feature_ids(rule, f"--{level}")
                cfg.cli_rules[rule] = level
    cfg.src.extend_exclude += args.exclude
    if args.respect_ignore_files is not None:
        cfg.src.respect_ignore_files = args.respect_ignore_files
    return cfg


def _cmd_check(args) -> int:
    from .engine import Analyzer
    from .report import render, use_color

    cfg = _load_config(args)
    if args.min_severity:
        cfg.min_severity = args.min_severity
    if args.baseline:
        cfg.baseline = args.baseline
    results, failed = _collect(args, cfg, Analyzer(cfg))
    color = use_color(sys.stdout, args.color)
    out = render(results, args.output, max_items=cfg.hooks.max_items, max_chars=cfg.hooks.max_chars,
                 feedback_link=cfg.feedback_link, color=color)
    if out:
        print(out)
    if args.hotspots and args.output in ("full", "concise"):
        from .report import hotspots

        spots = hotspots(results, args.hotspots, color)
        if spots:
            print("\n" + spots)
    if failed:
        return EXIT_USAGE
    worst = max((VERDICT_RANK[r.verdict] for r in results), default=0)
    threshold = {"never": 99, "advise": 1, "block": 2}["never" if args.exit_zero else args.fail_on]
    return EXIT_FINDINGS if worst >= threshold else EXIT_OK


def _read_rev_or_file(path: str) -> str:
    """A file's text, or for REV:PATH that isn't a file (HEAD:README.md), the file at a git revision."""
    if Path(path).exists() or ":" not in path:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    proc = subprocess.run(["git", "show", path], capture_output=True, check=False)
    if proc.returncode != 0:
        print(f"readcost: cannot read {path}: {proc.stderr.decode(errors='ignore').strip()}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)
    return proc.stdout.decode("utf-8", errors="ignore")


def _cmd_compare(args) -> int:
    from .config import load_config
    from .engine import Analyzer
    from .extract import detect_format
    from .report import compare, use_color

    cfg = load_config(args.config, start=args.new if args.new != "-" else None)
    analyzer = Analyzer(cfg)
    results = []
    for path in (args.old, args.new):
        text = sys.stdin.read() if path == "-" else _read_rev_or_file(path)
        fmt = args.format or ("markdown" if path == "-" else detect_format(path.split(":", 1)[-1]))
        results.append(analyzer.check_text(text, fmt, path))
    old, new = results
    if args.output == "json":
        import json

        print(json.dumps({"old": old.to_dict(), "new": new.to_dict()}, indent=1))
    else:
        print(compare(old, new, use_color(sys.stdout, args.color)))
    slower = (old.reading_seconds is not None and new.reading_seconds is not None
              and new.reading_seconds > old.reading_seconds)
    worse = slower or new.points > old.points
    return EXIT_FINDINGS if {"never": False, "slower": slower, "worse": worse}[args.fail_on] else EXIT_OK


def _cmd_style(args) -> int:
    from .engine import Analyzer
    from .profile import builtin_profiles, load_profile

    if args.list:
        for name in builtin_profiles():
            prof = load_profile(name)
            print(f"{name:12} {prof.words:>7,} words  {prof.note.split(';')[0]}")
        return EXIT_OK
    ref = load_profile(args.against)
    cfg = _load_config(args)
    # Measure against the reference's own dependency fit, as its rates were.
    results, failed = _collect(args, cfg, Analyzer(cfg, profile=ref))
    if failed or not results:
        return EXIT_USAGE
    words = sum(r.words for r in results)
    sentences = sum(r.sentences for r in results)
    if not words:
        print("readcost: no prose found", file=sys.stderr)
        return EXIT_USAGE
    counts: dict[str, int] = {}
    for r in results:
        for k, n in r.counts().items():
            counts[k] = counts.get(k, 0) + n
    timed = [r for r in results if r.reading_seconds is not None and r.reading_ms_per_word]
    ms = sum(1000 * r.reading_seconds for r in timed)
    ws = sum(1000 * r.reading_seconds / r.reading_ms_per_word for r in timed)
    rows = [("words per sentence", words / max(sentences, 1), ref.words_per_sentence, None),
            ("predicted ms per word", ms / ws if ws else None, ref.reading_ms_per_word, None)]
    rules = sorted(set(counts) | set(ref.rates))
    rows += [(f"{k} per 1k words", 1000 * counts.get(k, 0) / words, ref.rates.get(k, 0.0), counts.get(k, 0))
             for k in rules]
    if args.output == "json":
        import json

        print(json.dumps({
            "files": len(results), "words": words, "against": args.against, "reference": ref.note.split(";")[0],
            "rows": [{"measure": label, "rule": label.removesuffix(" per 1k words") if n is not None else None,
                      "yours": None if mine is None else round(mine, 3),
                      "reference": None if theirs is None else round(theirs, 3), "count": n,
                      "ratio": round(mine / theirs, 3) if mine is not None and theirs else None}
                     for label, mine, theirs, n in rows],
        }, indent=1))
        return EXIT_OK
    print(f"{len(results)} file(s), {words:,} words, against {args.against}: {ref.note.split(';')[0]}")
    print()
    width = max(len(r[0]) for r in rows)
    print(f"{'':<{width}}  {'yours':>8}  {args.against[:12]:>12}  ratio")
    for label, mine, theirs, n in rows:
        if mine is None or theirs is None:
            print(f"{label:<{width}}  {'-' if mine is None else f'{mine:.1f}':>8}  "
                  f"{'-' if theirs is None else f'{theirs:.1f}':>12}")
            continue
        ratio = mine / theirs if theirs else None
        note = "  much higher" if n is not None and n >= 3 and (ratio is None or ratio >= 2) else ""
        print(f"{label:<{width}}  {mine:>8.2f}  {theirs:>12.2f}  {'-' if ratio is None else f'{ratio:.1f}x'}{note}")
    return EXIT_OK


def _cmd_corpus(args) -> int:
    from .config import load_config
    from .corpus import analyze, split_records
    from .engine import Analyzer

    cfg = load_config(args.config, start=args.paths[0] if args.paths and args.paths[0] != "-" else None)
    texts: list[tuple[str, str]] = []
    for path in args.paths or ["-"]:
        if path == "-":
            raw = [("-", sys.stdin.read())]
        elif Path(path).is_dir():
            raw = [(str(p), p.read_text(encoding="utf-8", errors="ignore"))
                   for p in _walk(Path(path), cfg.src.respect_ignore_files, cfg.excluded) if cfg.wants(str(p))]
        else:
            raw = [(path, Path(path).read_text(encoding="utf-8", errors="ignore"))]
        for name, text in raw:
            texts += [(f"{name}#{i}", t) for i, t in enumerate(split_records(text), 1)] if args.split \
                else [(name, text)]
    if len(texts) < 2:
        print("readcost: corpus needs two or more texts (use --split for one file of many)", file=sys.stderr)
        return EXIT_USAGE
    rep = analyze(Analyzer(cfg), texts, top=args.top)
    if args.output == "json":
        import dataclasses
        import json

        print(json.dumps(dataclasses.asdict(rep), indent=1))
        return EXIT_OK
    print(f"{rep.texts} texts, {rep.words:,} words")
    print(f"CR-POS (repetitiveness of syntax)   {rep.cr_pos:.2f}")
    print(f"texts with a frequent template      {rep.template_rate:.0%}")
    print(f"template 6-grams per token          {rep.templates_per_token:.3f}")
    if rep.top_templates:
        print("\nmost frequent 6-tag templates:")
        for t in rep.top_templates:
            print(f"  {t['count']:>4} times in {t['texts']:>3} texts  {t['tags']:<28}  e.g. {t['example']}")
    if rep.top_openers:
        print("\nmost frequent sentence openers:")
        for o in rep.top_openers:
            print(f"  {o['count']:>4} ({o['share']:.0%})  {o['opener']}")
    return EXIT_OK


def _cmd_baseline(args) -> int:
    from .baseline import dump_baseline
    from .engine import Analyzer

    cfg = _load_config(args)
    # Record every finding: the verdict counts findings below min_severity too,
    # and an existing baseline must not hide what the new one should hold.
    cfg.min_severity, cfg.baseline = "info", ""
    results, failed = _collect(args, cfg, Analyzer(cfg))
    if failed:
        return EXIT_USAGE  # a partial baseline would make the unread files' findings new
    findings = [f for r in results for f in r.findings]
    Path(args.output).write_text(dump_baseline(findings, args.output))
    files = len({f.path for f in findings})
    print(f"wrote {args.output}: {len(findings)} findings in {files} file{'s' if files != 1 else ''}")
    return EXIT_OK


def _check_one(analyzer, opts: tuple, text: str, path: str, name: str) -> list:
    """Results for one input; ``opts`` is (format, per_record, field, last, lines)."""
    from .extract import detect_format

    fmt_opt, per_record, field_path, last, lines = opts
    fmt = fmt_opt or ("markdown" if path == "-" else detect_format(path))
    if per_record:
        out = analyzer.check_records(text, fmt, name, field_path=field_path)
    else:
        out = [analyzer.check_text(text, fmt, name, lines=lines, field_path=field_path, last_only=last)]
    if fmt in RECORD_FORMATS and not any(r.words for r in out):
        what = "records with that --field" if field_path else "assistant messages"
        print(f"readcost: warning: {name}: no prose found in {what} (format {fmt}); "
              "is --format right?", file=sys.stderr)
    return out


def _read_and_check(analyzer, opts: tuple, p: Path) -> tuple[list, str | None]:
    """(results, None), or ([], the reason) when the file cannot be read or parsed."""
    try:
        return _check_one(analyzer, opts, p.read_text(encoding="utf-8", errors="ignore"), str(p), str(p)), None
    except (OSError, ValueError) as exc:
        return [], str(exc.strerror if isinstance(exc, OSError) and exc.strerror else exc)


# A process pool pays a model load per worker (about two seconds), so it is
# used only for this many files or more.
PARALLEL_MIN_FILES = 16
_WORKER: tuple | None = None


def _init_worker(cfg, profile, opts) -> None:
    from .engine import Analyzer

    global _WORKER
    _WORKER = (Analyzer(cfg, profile), opts)


def _work(p: Path) -> tuple[list, str | None]:
    analyzer, opts = _WORKER
    return _read_and_check(analyzer, opts, p)


def _jobs(requested: int, files: int) -> int:
    if files < PARALLEL_MIN_FILES:
        return 1
    if requested > 0:
        return requested
    return max(1, min(os.cpu_count() or 1, 8, files // PARALLEL_MIN_FILES))


def _collect(args, cfg, analyzer) -> tuple[list, bool]:
    """Check every path in ``args.paths``; also say whether some file could not be read."""
    from .engine import parse_line_ranges

    if args.per_record and (args.last or args.lines):
        raise ValueError("--per-record cannot be combined with --last or --lines")
    opts = (args.format, args.per_record, args.field, args.last, parse_line_ranges(_line_spec(args.lines)))

    # Every input in order: stdin text, or a file. Files from all paths are
    # checked together, so many file arguments use the pool as a directory does.
    inputs: list = []
    for path in args.paths or ["-"]:
        if path == "-":
            inputs.append(("-", sys.stdin.read()))
            continue
        if Path(path).is_dir():
            # --per-record also takes JSONL, which [readcost.src] include leaves out.
            files = [p for p in _walk(Path(path), cfg.src.respect_ignore_files, cfg.excluded)
                     if cfg.wants(str(p)) or (args.per_record and p.suffix == ".jsonl"
                                              and not cfg.excluded(str(p)))]
            if not files:
                print(f"readcost: {path}: no files matched [readcost.src] include", file=sys.stderr)
            inputs.extend(files)
        elif not (args.force_exclude and cfg.excluded(path)):
            inputs.append(Path(path))
    files = [x for x in inputs if isinstance(x, Path)]
    jobs = _jobs(getattr(args, "jobs", 1), len(files))
    if jobs > 1:
        from concurrent.futures import ProcessPoolExecutor

        with ProcessPoolExecutor(jobs, initializer=_init_worker,
                                 initargs=(analyzer.cfg, analyzer.profile, opts)) as pool:
            checked = iter(pool.map(_work, files, chunksize=4))
    else:
        checked = (_read_and_check(analyzer, opts, p) for p in files)
    results, failed = [], False
    for x in inputs:
        if not isinstance(x, Path):
            results.extend(_check_one(analyzer, opts, x[1], "-", args.stdin_name))
            continue
        out, error = next(checked)
        if error is not None:
            failed = True
            print(f"readcost: {x}: {error}", file=sys.stderr)
        results.extend(out)
    return results, failed


def _cmd_profile(args) -> int:
    from .config import load_config
    from .engine import Analyzer
    from .profile import Profile, build_profile

    cfg = load_config(args.config)
    placeholder = Profile("placeholder", 0, 0, (0.0, 0.78, 0.42))
    prof = build_profile(args.paths, args.name, lambda: Analyzer(cfg, placeholder), args.format)
    Path(args.output).write_text(prof.to_json() + "\n")
    print(f"wrote {args.output}: {prof.words} words, {prof.sentences} sentences")
    return EXIT_OK


def _measured(rule: str) -> str:
    """How often model raters accepted this rule's findings in the evaluation (docs/evaluation.md)."""
    from .report import _precision, rule_precision

    data = rule_precision()
    if not data:
        return "no evaluation data in this install"
    row = _precision(rule)
    if row is None:
        return "too few labelled findings to measure (see docs/evaluation.md)"
    return (f"{row['accepted']} of {row['labelled']} labelled findings judged correct or defensible "
            f"by a majority of {data['raters']} model raters, on essays and docs by well-regarded writers")


def _cmd_explain(args) -> int:
    from .features import FEATURES

    ids = [args.feature] if args.feature else list(FEATURES)
    for fid in ids:
        f = FEATURES.get(fid)
        if f is None:
            print(f"unknown feature {fid!r}; known: {', '.join(FEATURES)}", file=sys.stderr)
            return EXIT_USAGE
        state = "on" if f.default else "off (enable with --enable)"
        print(f"{f.id}: {f.title}  [{f.severity}, {state}, {f.origin}]")
        print(f"  Why: {f.why}")
        print(f"  Fix: {f.fix}")
        if f.bad:
            print(f"  Before: {f.bad}")
            print(f"  After:  {f.good}")
        print(f"  Measured: {_measured(f.id)}")
        print()
    return EXIT_OK


def _cmd_setup(args) -> int:
    from . import modelstore

    model = args.model
    try:
        import spacy

        spacy.load(model)
        print(f"spaCy model {model}: installed")
        return EXIT_OK
    except OSError:
        pass
    if model == modelstore.MODEL:
        # No pip needed, so this also works under uvx.
        path = modelstore.cached_path() or modelstore.fetch()
        print(f"spaCy model {model}: {path}")
        return EXIT_OK
    print(f"spaCy model {model}: downloading")
    return EXIT_USAGE if subprocess.call([sys.executable, "-m", "spacy", "download", model]) else EXIT_OK


def _cmd_hook(args) -> int:
    from . import hooks

    return hooks.run(args.harness, args.event, args.rest)


def _cmd_lsp(args) -> int:
    try:
        from . import lsp
    except ImportError as exc:
        if (exc.name or "").split(".")[0] not in ("pygls", "lsprotocol"):
            raise
        print("readcost: the language server needs pygls; run pip install 'readcost[lsp]'", file=sys.stderr)
        return EXIT_USAGE
    return lsp.main()


def build_parser() -> argparse.ArgumentParser:
    from .extract import FORMATS
    from .report import OUTPUTS

    p = argparse.ArgumentParser(prog="readcost", description="Find prose constructions that slow readers down.")
    p.add_argument("--version", action="store_true", help="print the version and exit")
    sub = p.add_subparsers(dest="cmd")

    def inputs(c):
        """Arguments that choose and read the input, shared by check and baseline."""
        c.add_argument("paths", nargs="*", help="files or directories; '-' or nothing reads stdin")
        c.add_argument("-f", "--format", choices=FORMATS,
                       help="input format (default: from the file name; stdin: markdown)")
        for level in ("error", "warn", "info", "ignore"):
            what = "turn off" if level == "ignore" else f"turn on at severity {level}"
            c.add_argument(f"--{level}", action="append", default=[], metavar="RULE",
                           help=f"{what} (repeatable or comma-separated; 'all' for every rule)")
        c.add_argument("--enable", help="comma-separated rules to turn on (older spelling of --warn etc.)")
        c.add_argument("--disable", help="comma-separated rules to turn off (older spelling of --ignore)")
        c.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                       help="also skip files matching this glob, after [readcost.src] exclude (repeatable)")
        c.add_argument("--force-exclude", action="store_true",
                       help="apply the excludes to files named on the command line too")
        c.add_argument("--respect-ignore-files", action=argparse.BooleanOptionalAction, default=None,
                       help="skip files that .gitignore excludes when walking a directory (default: on)")
        c.add_argument("--profile", help="reference profile JSON (default: built-in)")
        c.add_argument("--field", help="for JSON/JSONL: dotted path of the text field, e.g. response or output.text")
        c.add_argument("--per-record", action="store_true",
                       help="for transcripts, chat JSON and JSONL: one result per message or record")
        c.add_argument("--stdin-name", default="<stdin>", help="name to report for stdin input")
        c.add_argument("--config", help="config file (default: discovered readcost.toml or pyproject.toml)")

    c = sub.add_parser("check", help="analyze files, directories, or stdin")
    inputs(c)
    c.add_argument("-o", "--output", choices=OUTPUTS, default="full",
                   help="full: quoted line and fix per finding; concise: one line per finding")
    c.add_argument("--color", choices=("auto", "always", "never"), default="auto",
                   help="colour the full output (auto: on a terminal, unless NO_COLOR is set)")
    c.add_argument("--fail-on", choices=("never", "advise", "block"), default="block",
                   help="exit 1 when any file reaches this verdict (default: block)")
    c.add_argument("--exit-zero", action="store_true", help="always exit 0 on findings (same as --fail-on never)")
    c.add_argument("-j", "--jobs", type=int, default=0, metavar="N",
                   help=f"check files in N processes (default: automatic, from {PARALLEL_MIN_FILES} files up)")
    c.add_argument("--hotspots", type=int, default=0, metavar="N",
                   help="also list each file's N sentences predicted to cost the most reading time (experimental)")
    c.add_argument("--min-severity", choices=("info", "warn", "error"))
    c.add_argument("--lines", help="only report sentences touching these lines, e.g. 10-24,40")
    c.add_argument("--last", action="store_true", help="for transcripts: only the last assistant message")
    c.add_argument("--baseline", help="baseline JSON from `readcost baseline`; only findings not in it count")
    c.set_defaults(func=_cmd_check)

    st = sub.add_parser("style", help="compare rule rates, sentence length and reading time with a reference style")
    inputs(st)
    st.add_argument("--against", default="default",
                    help="a built-in profile (see --list), 'default', or a profile JSON file")
    st.add_argument("--list", action="store_true", help="list the built-in reference profiles")
    st.add_argument("-o", "--output", choices=("text", "json"), default="text",
                    help="json: the same rows for tools and agents")
    st.set_defaults(func=_cmd_style, lines=None, last=False)

    co = sub.add_parser("corpus", help="repetition across many texts: syntactic templates and openers")
    co.add_argument("paths", nargs="*", help="files or directories, one text each; '-' reads stdin")
    co.add_argument("--split", action="store_true",
                    help="treat each file as many texts separated by lines of --- or ===")
    co.add_argument("--top", type=int, default=5, help="templates and openers to list")
    co.add_argument("-o", "--output", choices=("text", "json"), default="text")
    co.add_argument("--config", help="config file (default: discovered)")
    co.set_defaults(func=_cmd_corpus)

    cm = sub.add_parser("compare", help="compare a rewrite with its original: reading time and findings")
    cm.add_argument("old", help="the original: a file, REV:PATH from git (HEAD:README.md), or '-' for stdin")
    cm.add_argument("new", help="the rewrite")
    cm.add_argument("-f", "--format", choices=FORMATS, help="input format (default: from the file name)")
    cm.add_argument("-o", "--output", choices=("full", "json"), default="full")
    cm.add_argument("--color", choices=("auto", "always", "never"), default="auto")
    cm.add_argument("--config", help="config file (default: discovered from the rewrite's directory)")
    cm.add_argument("--fail-on", choices=("never", "slower", "worse"), default="never",
                    help="exit 1 if the rewrite is predicted to read slower, or (worse) slower or with more "
                         "weighted findings")
    cm.set_defaults(func=_cmd_compare)

    bl = sub.add_parser("baseline", help="record current findings so that later checks report only new ones")
    inputs(bl)
    bl.add_argument("-o", "--output", default=".readcost-baseline.json",
                    help="file to write; finding paths are stored relative to its directory "
                         "(default: .readcost-baseline.json)")
    bl.set_defaults(func=_cmd_baseline, lines=None, last=False)

    pr = sub.add_parser("profile", help="build a reference profile from documents you consider readable")
    prsub = pr.add_subparsers(dest="profile_cmd", required=True)
    b = prsub.add_parser("build")
    b.add_argument("paths", nargs="+")
    b.add_argument("-o", "--output", required=True)
    b.add_argument("--name", default="custom")
    b.add_argument("-f", "--format", choices=FORMATS)
    b.add_argument("--config")
    b.set_defaults(func=_cmd_profile)

    e = sub.add_parser("explain", help="describe features and how to fix them")
    e.add_argument("feature", nargs="?")
    e.set_defaults(func=_cmd_explain)

    s = sub.add_parser("setup", help="download the spaCy model if it is missing")
    s.add_argument("--model", default="en_core_web_sm")
    s.set_defaults(func=_cmd_setup)

    h = sub.add_parser("hook", help="adapter for a harness; reads the harness's JSON on stdin")
    h.add_argument("harness", choices=("claude-code", "piku", "git", "generic"))
    h.add_argument("event", nargs="?", default="")
    h.add_argument("rest", nargs="*")
    h.set_defaults(func=_cmd_hook)

    ls = sub.add_parser("lsp", help="run a language server on stdin and stdout for editors")
    ls.set_defaults(func=_cmd_lsp)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        from . import __version__

        print(__version__)
        return EXIT_OK
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USAGE
    try:
        code = args.func(args)
        sys.stdout.flush()
        return code
    except BrokenPipeError:
        # The reader (e.g. `| head`) left. Point stdout at devnull so the
        # interpreter's final flush does not print a second error.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return EXIT_BROKEN_PIPE
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"readcost: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except Exception as exc:  # noqa: BLE001 - exit 1 means "findings"; a crash must not
        print(f"readcost: internal error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
