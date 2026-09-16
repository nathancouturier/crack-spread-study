"""Write the site facing JSON artifacts. What `make build` and `make build-check` run.

    python scripts/export.py            write data/*.json from the committed caches
    python scripts/export.py --check    write nothing, exit 1 if a committed artifact is stale
    python scripts/export.py --out DIR  write somewhere else

It never fetches. SPEC.md section 5.4: `make build` never fetches. Everything is
in src/crack/export.py; this file only puts src on the path.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from crack import export  # noqa: E402

if __name__ == "__main__":
    sys.exit(export.main())
