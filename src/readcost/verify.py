"""A second parser that checks three rules' findings (opt-in: ``verify_model``).

The default parser, en_core_web_sm, sometimes reads a verb as a noun or
attaches a clause to the wrong word. Three rules then report a construction
that is not there. With ``verify_model`` set, each sentence with a finding of
one of these rules is parsed again by a small dependency parser, and the
finding stays only when that parse agrees:

- stacked-nouns: the second parser tags none of the stacked words as a verb;
- reduced-object-relative: in the second parse the verb heads a relative
  clause (``acl:relcl``) with a subject of its own and no relative pronoun;
- long-dependency: the second parse has a subject or object arc of at least
  nine words over the same stretch.

The parser is ghotriw/deberta-v3-xsmall-biaffine-dep-pos-feats-en-ewt-gum-norm
(MIT): DeBERTa-v3-xsmall with a biaffine head, trained on UD English EWT and
GUM, exported to ONNX. It needs ``onnxruntime`` and ``tokenizers``
(``pip install 'readcost[verify]'``) and about 300 MB of model files, which
``readcost setup --verifier`` downloads at a pinned revision and checks.
docs/evaluation.md ("A second parser as a check") gives the measurements
behind the choice of model and of each rule's test.

Parses are kept in memory by the SHA-256 of the sentence's words, so an
editor or hook that rechecks a file does not parse an unchanged sentence
again.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

REPO = "ghotriw/deberta-v3-xsmall-biaffine-dep-pos-feats-en-ewt-gum-norm"
# The revision and files the second-parser evaluation job downloaded and measured.
REVISION = "47c185bbe563964a82641bd0d4dbe7ad1645db4f"
FILES = {  # file name -> SHA-256
    "config.json": "955d5083925821af62254e574e1f726bdf3d47629eb3169b0d43b4dbe58f6b74",
    "tokenizer.json": "7fb827d15550c884144bec6129b81d7ee7cc42c7181a678aa6b408c04a03d764",
    "model.onnx": "9d1393986208fae03cc4325b02a78a1b12b0e8ccf5b8404e08a6624f427affc2",
}
NAME = "biaffine-xsmall"
VERIFIED_RULES = frozenset({"stacked-nouns", "reduced-object-relative", "long-dependency"})
VERBS = ("VERB", "AUX")
RELATIVE_PRONOUNS = frozenset({"that", "which", "who", "whom"})
CORE = frozenset({"nsubj", "nsubj:pass", "nsubj:outer", "csubj", "csubj:pass", "obj", "iobj"})
NOMINAL = ("NOUN", "PROPN", "PRON")
MIN_WORDS = 9            # features.LONG_DEPENDENCY_CORE_MIN
CACHE_SIZE = 4096        # sentences


@dataclass(frozen=True)
class Parse:
    """The second parser's reading of one sentence. ``heads`` is 0-based, -1 for the root."""
    upos: tuple[str, ...]
    heads: tuple[int, ...]
    deprels: tuple[str, ...]


# --------------------------------------------------------------- the tests

def keep_stack(parse: Parse, stack: list[int]) -> bool:
    """No word of the noun stack is a verb in the second parse."""
    return not any(parse.upos[k] in VERBS for k in stack)


def keep_relative(parse: Parse, words: list[str], verb: int) -> bool:
    """The verb heads a relative clause with its own subject and no relative pronoun."""
    if parse.deprels[verb] != "acl:relcl":
        return False
    kids = [k for k, h in enumerate(parse.heads) if h == verb]
    subject = any(parse.deprels[k] in ("nsubj", "nsubj:pass") and words[k].lower() not in RELATIVE_PRONOUNS
                  for k in kids)
    relativizer = any(k < verb and words[k].lower() in RELATIVE_PRONOUNS for k in kids)
    return subject and not relativizer


def core_arcs(parse: Parse) -> list[tuple[int, int, int]]:
    """(distance in words, first, last) of the subject and object arcs, punctuation not counted.

    UD attaches the subject of a copular clause to the predicate ("the index
    is a file": index <- file); readcost's rules measure it to the copula, so
    both the subject and the predicate noun are measured to the copula here.
    """
    order = {k: n for n, k in enumerate(k for k, p in enumerate(parse.upos) if p != "PUNCT")}
    copula: dict[int, int] = {}
    for k, (h, rel) in enumerate(zip(parse.heads, parse.deprels)):
        if rel == "cop" and h >= 0:
            copula.setdefault(h, k)
    out = []
    for k, (h, rel) in enumerate(zip(parse.heads, parse.deprels)):
        if k not in order:
            continue
        if rel in CORE and h >= 0:
            h = copula.get(h, h)
            if h in order:
                out.append((abs(order[k] - order[h]), min(k, h), max(k, h)))
        if k in copula and parse.upos[k] in NOMINAL and copula[k] in order:
            c = copula[k]
            out.append((abs(order[k] - order[c]), min(k, c), max(k, c)))
    return out


def keep_dependency(parse: Parse, first: int, last: int) -> bool:
    """The second parse has a subject or object arc of nine or more words overlapping first..last."""
    return any(dist >= MIN_WORDS and lo <= last and first <= hi for dist, lo, hi in core_arcs(parse))


def keep(rule: str, parse: Parse | None, words: list[str], tokens: list[int]) -> bool:
    """Whether a finding survives the second parse.

    ``tokens`` index ``words``: the stacked nouns; the head, subject and verb
    of a relative clause; the two ends of a long dependency. A sentence the
    parser could not read keeps its findings, and so does any other rule.
    """
    if parse is None or rule not in VERIFIED_RULES or not tokens:
        return True
    if rule == "stacked-nouns":
        return keep_stack(parse, tokens)
    if rule == "reduced-object-relative":
        return keep_relative(parse, words, tokens[-1])
    return keep_dependency(parse, min(tokens), max(tokens))


# ------------------------------------------------------------------ the model

class Biaffine:
    """The biaffine parser's ONNX graph.

    Input: one int64 grid [1, words + 1, fix_len]. Each word is tokenized
    alone with the encoder's tokenizer and cut or padded with 0 to
    ``fix_len`` subwords; row 0 stands for the root and holds only [CLS].
    Outputs: arc scores [dependent, head] with column 0 the root, relation
    scores [dependent, head, label] and part-of-speech scores. Each word
    takes its best-scoring head, with no tree constraint: the tests above
    read single arcs.
    """

    def __init__(self, directory: Path, session=None, tokenizer=None):
        directory = Path(directory)
        cfg = json.loads((directory / "config.json").read_text(encoding="utf-8"))
        self.fix_len = int(cfg["fix_len"])
        self.pos = {v: k for k, v in cfg["pos_vocab"].items()}
        self.rel = {v: k for k, v in cfg["rel_vocab"].items()}
        self.first_label = 2  # 0 and 1 are <pad> and <bos>
        if tokenizer is None:
            from tokenizers import Tokenizer

            tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
            tokenizer.no_padding()
            tokenizer.no_truncation()
        self.tokenizer = tokenizer
        self.cls = tokenizer.token_to_id("[CLS]")
        self.unk = tokenizer.token_to_id("[UNK]")
        if session is None:
            import onnxruntime as ort

            options = ort.SessionOptions()
            options.log_severity_level = 3
            session = ort.InferenceSession(str(directory / "model.onnx"), options,
                                           providers=["CPUExecutionProvider"])
        self.session = session
        self.input = session.get_inputs()[0].name
        names = [o.name for o in session.get_outputs()]
        self.order = [names.index(n) if n in names else k for k, n in enumerate(("s_arc", "s_rel", "s_pos"))]

    def grid(self, words: list[str]):
        import numpy as np

        rows = [[self.cls]]
        for w in words:
            ids = self.tokenizer.encode(w, add_special_tokens=False).ids[:self.fix_len]
            rows.append(ids or [self.unk])
        out = np.zeros((1, len(rows), self.fix_len), dtype=np.int64)
        for k, ids in enumerate(rows):
            out[0, k, :len(ids)] = ids
        return out

    def parse(self, words: list[str]) -> Parse:
        import numpy as np

        outputs = self.session.run(None, {self.input: self.grid(words)})
        arc, rel, pos = (np.asarray(outputs[k], dtype=np.float32)[0] for k in self.order)
        lo = self.first_label
        upos = tuple(self.pos[int(k) + lo] for k in pos[1:, lo:].argmax(-1))
        arc = arc[1:].copy()
        arc[np.arange(len(words)), np.arange(1, len(words) + 1)] = -np.inf  # no word heads itself
        head_col = arc.argmax(-1)
        deprels = tuple(self.rel[int(rel[d + 1, h, lo:].argmax()) + lo] for d, h in enumerate(head_col))
        return Parse(upos, tuple(int(h) - 1 for h in head_col), deprels)


class Verifier:
    """A parser with an in-memory cache keyed by the SHA-256 of the sentence's words."""

    MAX_WORDS = 200  # longer "sentences" are usually tables or code; leave their findings alone

    def __init__(self, model, size: int = CACHE_SIZE):
        self.model = model
        self.cache: OrderedDict[str, Parse | None] = OrderedDict()
        self.size = size
        self.parsed = 0
        self.dropped = 0

    def parse(self, words: list[str]) -> Parse | None:
        key = hashlib.sha256("\x1f".join(words).encode()).hexdigest()
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        parse = self.model.parse(words) if 0 < len(words) <= self.MAX_WORDS else None
        self.parsed += 1
        self.cache[key] = parse
        if len(self.cache) > self.size:
            self.cache.popitem(last=False)
        return parse

    def keep(self, rule: str, words: list[str], tokens: list[int]) -> bool:
        if rule not in VERIFIED_RULES or not tokens:
            return True
        kept = keep(rule, self.parse(words), words, tokens)
        self.dropped += not kept
        return kept

    def filter(self, sent, found: list[tuple]) -> list[tuple]:
        """The detector results of one spaCy sentence, (feature, severity, message, tokens), that survive."""
        if not any(f[0] in VERIFIED_RULES and f[3] for f in found):
            return found
        kept_tokens = [t for t in sent if not t.is_space]
        index = {t.i: k for k, t in enumerate(kept_tokens)}
        words = [t.text for t in kept_tokens]
        out = []
        for f in found:
            feature, toks = f[0], f[3]
            roles = [index[t.i] for t in toks if t.i in index] if toks else []
            if feature == "stacked-nouns":
                roles.sort()
            if self.keep(feature, words, roles):
                out.append(f)
        return out


# ------------------------------------------------------------ files and setup

def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "readcost" / "models" / f"{NAME}-{REVISION[:12] or 'unpinned'}"


def resolve(setting: str) -> Path:
    """The model directory a ``verify_model`` value names: "biaffine" for the downloaded copy, or a path."""
    if setting == "biaffine":
        path = cache_dir()
        if not all((path / name).is_file() for name in ("model.onnx", "config.json", "tokenizer.json")):
            raise OSError(f"the verifier model is not downloaded; run `readcost setup --verifier` ({path})")
        return path
    path = Path(setting).expanduser()
    if not (path / "model.onnx").is_file():
        raise OSError(f"verify_model {setting!r}: no model.onnx in that directory")
    return path


def fetch(timeout: float = 300.0) -> Path:
    """Download the pinned model files into the cache and check each SHA-256."""
    if not REVISION or not FILES:
        raise OSError("this readcost has no pinned verifier model; set verify_model to a directory instead")
    if os.environ.get("READCOST_NO_DOWNLOAD"):
        raise OSError("READCOST_NO_DOWNLOAD is set; download the verifier model where downloads are allowed")
    final = cache_dir()
    final.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=final.parent, prefix=".partial-"))
    print(f"readcost: downloading the verifier model {REPO} (about 300 MB, once) to {final}", file=sys.stderr)
    try:
        for name, digest in FILES.items():
            url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{name}"
            target = staging / name
            h = hashlib.sha256()
            with urllib.request.urlopen(url, timeout=timeout) as resp, open(target, "wb") as out:
                while chunk := resp.read(1 << 20):
                    h.update(chunk)
                    out.write(chunk)
            if h.hexdigest() != digest:
                raise ValueError(f"{name} has SHA-256 {h.hexdigest()}, expected {digest}")
        if final.exists():
            shutil.rmtree(final)
        staging.rename(final)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return final


def load(setting: str) -> Verifier:
    try:
        import onnxruntime  # noqa: F401
        import tokenizers  # noqa: F401
    except ImportError as exc:
        raise OSError("verify_model needs onnxruntime and tokenizers: pip install 'readcost[verify]'") from exc
    return Verifier(Biaffine(resolve(setting)))
