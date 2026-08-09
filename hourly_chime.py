"""Compatibility entry point for the original project commands.

The daemon loop has intentionally been removed. launchd now invokes the short-lived
``chimectl run`` jobs.
"""

from __future__ import annotations

import sys
from pathlib import Path


# The repository keeps this legacy script for people who still run
# ``python hourly_chime.py``.  Expose the src-layout package path as well so
# local development commands such as ``python -m hourly_chime.cli`` are not
# shadowed by this compatibility file.
if __name__ != "__main__":
    __path__ = [str(Path(__file__).resolve().parent / "src" / "hourly_chime")]


def _bootstrap_source_tree() -> None:
    source = Path(__file__).resolve().parent / "src"
    if source.is_dir():
        sys.path.insert(0, str(source))


def main() -> int:
    _bootstrap_source_tree()
    from hourly_chime.cli import main as cli_main

    if "--test" in sys.argv:
        return cli_main(["test", "full"])
    if "--test-music" in sys.argv:
        return cli_main(["test", "music"])
    return cli_main(["run", "play", "--allow-late"])


if __name__ == "__main__":
    raise SystemExit(main())
