"""readcost: find sentence constructions in prose that language models overuse.

Python API::

    from readcost import Analyzer, check_text

    result = check_text(open("README.md").read(), fmt="markdown")
    for f in result.findings:
        print(f.line, f.feature, f.message)
"""

__version__ = "0.4.0"

from .config import Config, load_config  # noqa: E402
from .engine import Analyzer, Result, check_file, check_text  # noqa: E402
from .features import FEATURES, Finding  # noqa: E402

__all__ = [
    "Analyzer", "Config", "FEATURES", "Finding", "Result",
    "check_file", "check_text", "load_config", "__version__",
]
