"""Command line: readcost check | profile build | explain | setup | hook."""

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

    ids = [i.strip() for i in value.split(",") if i.strip()]
    bad = unknown_features(ids)
    if bad:
        from .features import FEATURES

        raise ValueError(f"{flag}: unknown feature {', '.join(map(repr, bad))}; known: {', '.join(FEATURES)}")
    return ids


def _walk(root: Path) -> list[Path]:
    """Files under ``root``: what git tracks or would track, else non-hidden files."""
    proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others",
                           "--exclude-standard"], capture_output=True)
    if proc.returncode == 0:
        names = [n for n in proc.stdout.decode("utf-8", "replace").split("\0") if n]
        return sorted(p for p in (root / n for n in names) if p.is_file())
    return sorted(p for p in root.rglob("*")
                  if p.is_file() and not any(part.startswith(".") for part in p.relative_to(root).parts))


def _cmd_check(args) -> int:
    from .config import load_config
    from .engine import Analyzer, parse_line_ranges
    from .extract import detect_format
    from .report import render

    if args.per_record and (args.last or args.lines):
        raise ValueError("--per-record cannot be combined with --last or --lines")
    lines = parse_line_ranges(_line_spec(args.lines))
    cfg = load_config(args.config, start=args.paths[0] if args.paths and args.paths[0] != "-" else None)
    if args.min_severity:
        cfg.min_severity = args.min_severity
    if args.enable:
        cfg.enable += _feature_ids(args.enable, "--enable")
    if args.disable:
        cfg.disable += _feature_ids(args.disable, "--disable")
    if args.profile:
        cfg.profile = args.profile
    analyzer = Analyzer(cfg)

    def check(text: str, path: str, name: str) -> list:
        fmt = args.format or ("markdown" if path == "-" else detect_format(path))
        if args.per_record:
            out = analyzer.check_records(text, fmt, name, field_path=args.field)
        else:
            out = [analyzer.check_text(text, fmt, name, lines=lines, field_path=args.field,
                                       last_only=args.last)]
        if fmt in RECORD_FORMATS and not any(r.words for r in out):
            what = "records with that --field" if args.field else "assistant messages"
            print(f"readcost: warning: {name}: no prose found in {what} (format {fmt}); "
                  "is --format right?", file=sys.stderr)
        return out

    results, failed = [], False
    for path in args.paths or ["-"]:
        if path == "-":
            results.extend(check(sys.stdin.read(), "-", args.stdin_name))
            continue
        if Path(path).is_dir():
            # --per-record also takes JSONL, which hooks.paths leaves out.
            files = [p for p in _walk(Path(path))
                     if cfg.wants(str(p)) or (args.per_record and p.suffix == ".jsonl"
                                              and not cfg.excluded(str(p)))]
            if not files:
                print(f"readcost: {path}: no files matched hooks.paths", file=sys.stderr)
        else:
            files = [Path(path)]
        for p in files:
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
                results.extend(check(text, str(p), str(p)))
            except (OSError, ValueError) as exc:
                failed = True
                detail = exc.strerror if isinstance(exc, OSError) and exc.strerror else exc
                print(f"readcost: {p}: {detail}", file=sys.stderr)
    out = render(results, args.output, max_items=cfg.hooks.max_items, max_chars=cfg.hooks.max_chars)
    if out:
        print(out)
    if failed:
        return EXIT_USAGE
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
    c.add_argument("--lines", help="only report sentences touching these lines, e.g. 10-24,40")
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

    s = sub.add_parser("setup", help="download the spaCy model if it is missing")
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
