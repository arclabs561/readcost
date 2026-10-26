"""Command line: readcost check | profile build | explain | setup | hook."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

EXIT_OK, EXIT_FINDINGS, EXIT_USAGE = 0, 1, 2
VERDICT_RANK = {"pass": 0, "advise": 1, "block": 2}


def _cmd_check(args) -> int:
    from .config import load_config
    from .engine import Analyzer, parse_line_ranges
    from .report import render

    cfg = load_config(args.config, start=args.paths[0] if args.paths and args.paths[0] != "-" else None)
    if args.min_severity:
        cfg.min_severity = args.min_severity
    if args.enable:
        cfg.enable += args.enable.split(",")
    if args.disable:
        cfg.disable += args.disable.split(",")
    if args.profile:
        cfg.profile = args.profile
    analyzer = Analyzer(cfg)
    lines = parse_line_ranges(args.lines)
    results = []
    for path in args.paths or ["-"]:
        if path == "-":
            text = sys.stdin.read()
            results.append(analyzer.check_text(text, args.format or "markdown", args.stdin_name,
                                               lines=lines, field_path=args.field, last_only=args.last))
        elif Path(path).is_dir():
            for p in sorted(Path(path).rglob("*")):
                if p.is_file() and cfg.wants(str(p)):
                    results.append(analyzer.check_file(str(p), args.format, lines=lines,
                                                       field_path=args.field, last_only=args.last))
        elif args.per_record:
            from .extract import detect_format

            text = Path(path).read_text(encoding="utf-8", errors="ignore")
            results.extend(analyzer.check_records(text, args.format or detect_format(path), path,
                                                  field_path=args.field))
        else:
            results.append(analyzer.check_file(path, args.format, lines=lines,
                                               field_path=args.field, last_only=args.last))
    out = render(results, args.output, max_items=cfg.hooks.max_items, max_chars=cfg.hooks.max_chars)
    if out:
        print(out)
    worst = max((VERDICT_RANK[r.verdict] for r in results), default=0)
    threshold = {"never": 99, "advise": 1, "block": 2}[args.fail_on]
    return EXIT_FINDINGS if worst >= threshold else EXIT_OK


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
        print()
    return EXIT_OK


def _cmd_setup(args) -> int:
    status = EXIT_OK
    model = args.model
    try:
        import spacy

        spacy.load(model)
        print(f"spaCy model {model}: installed")
    except OSError:
        print(f"spaCy model {model}: downloading")
        rc = subprocess.call([sys.executable, "-m", "spacy", "download", model])
        status = status or (EXIT_USAGE if rc else EXIT_OK)
    return status


def _cmd_hook(args) -> int:
    from . import hooks

    return hooks.run(args.harness, args.event, args.rest)


def build_parser() -> argparse.ArgumentParser:
    from .extract import FORMATS
    from .report import OUTPUTS

    p = argparse.ArgumentParser(prog="readcost", description="Find prose constructions that slow readers down.")
    p.add_argument("--version", action="store_true", help="print the version and exit")
    sub = p.add_subparsers(dest="cmd")

    c = sub.add_parser("check", help="analyze files, directories, or stdin")
    c.add_argument("paths", nargs="*", help="files or directories; '-' or nothing reads stdin")
    c.add_argument("-f", "--format", choices=FORMATS, help="input format (default: from the file name; stdin: markdown)")
    c.add_argument("-o", "--output", choices=OUTPUTS, default="text")
    c.add_argument("--fail-on", choices=("never", "advise", "block"), default="block",
                   help="exit 1 when any file reaches this verdict (default: block)")
    c.add_argument("--min-severity", choices=("info", "warn", "error"))
    c.add_argument("--enable", help="comma-separated features to turn on")
    c.add_argument("--disable", help="comma-separated features to turn off")
    c.add_argument("--profile", help="reference profile JSON (default: built-in)")
    c.add_argument("--lines", help="only report sentences starting on these lines, e.g. 10-24,40")
    c.add_argument("--field", help="for JSON/JSONL: dotted path of the text field, e.g. response or output.text")
    c.add_argument("--last", action="store_true", help="for transcripts: only the last assistant message")
    c.add_argument("--per-record", action="store_true",
                   help="for transcripts, chat JSON and JSONL: one result per message or record")
    c.add_argument("--stdin-name", default="<stdin>", help="name to report for stdin input")
    c.add_argument("--config", help="config file (default: discovered readcost.toml or pyproject.toml)")
    c.set_defaults(func=_cmd_check)

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

    s = sub.add_parser("setup", help="download the spaCy model and WordNet")
    s.add_argument("--model", default="en_core_web_sm")
    s.set_defaults(func=_cmd_setup)

    h = sub.add_parser("hook", help="adapter for a harness; reads the harness's JSON on stdin")
    h.add_argument("harness", choices=("claude-code", "piku", "git", "generic"))
    h.add_argument("event", nargs="?", default="")
    h.add_argument("rest", nargs="*")
    h.set_defaults(func=_cmd_hook)
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
        return args.func(args)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"readcost: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
