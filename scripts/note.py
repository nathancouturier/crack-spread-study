"""Collect this week's DGEC note, then rebuild the weekly series. What `make note` runs.

    python scripts/note.py                 collect the note online now, rebuild the weekly layer
    python scripts/note.py --diagnostics   print the per note decode diagnostics, build nothing

Any other argument is passed to crack.sources.dgec_note unchanged. With no
argument this is `python -m crack.sources.dgec_note --collect`, which only works
where the package is importable: pytest puts src on the path through
tests/conftest.py, and nothing does on a fresh clone with nothing installed, so
that command failed there with "No module named crack". This file only puts src
on the path, the way scripts/export.py and scripts/refresh.py do, so the target
runs from a clean clone with no install, in any shell.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from crack.sources import dgec_note  # noqa: E402

if __name__ == "__main__":
    arguments = sys.argv[1:] or ["--collect"]
    sys.exit(dgec_note.main(arguments))
