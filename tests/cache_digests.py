"""The committed digest of every committed cache, and how to regenerate it.

WHY THIS EXISTS
---------------
Gate 1 self audit, finding d.1 and point 10 item 7. The audit set one cell of
data/cache/dgec_mbr_monthly.csv to 99.99, a 172 percent error on a published
anchor and comfortably inside its declared bounds, and watched two of the four
gate steps pass:

    python scripts/refresh.py --offline    19 of 19 series ok, exit 0
    node tools/validate-data.mjs           15 of 15 checks passed, exit 0
    python -m pytest tests                 2 FAILED

Only pytest caught it, and only because the MBR happens to be the one series
with value level assertions. The audit's own conclusion was that "a one digit
change in, say, opec_rotterdam_products_monthly would survive all four gate
steps", and it was right: bounds are units checks, gap counts are shape checks,
and neither can see a plausible wrong number.

This module closes that. It records, for every committed cache:

    sha256      of the exact bytes on disk. write_cache is deterministic, so a
                clean rebuild reproduces the same bytes and any edit at all,
                one digit included, changes this.
    bytes, rows, columns
                so that a failure says what kind of change happened rather than
                only that the hash moved.
    anchors     the FIRST and LAST published value of every value column, with
                its date. These are the readable half: when a cache changes, the
                test that fires names a product, a date and two numbers instead
                of two hex strings.

WHAT A FAILURE MEANS, AND WHAT TO DO
-------------------------------------
A digest failure is not a reason to regenerate the digest. It means a committed
cache changed, and the first question is always which source served what and
why. Only once the data is right:

    python tests/cache_digests.py --write

and the diff it produces is the thing to read before committing. That diff is
the point: a deliberate data change shows up as a reviewable change to a
committed file, and an accidental one cannot hide.

WHAT THIS DOES NOT COVER
-------------------------
The two private caches, data/private/ttf_daily.csv and
data/private/ei_refinery_capacity_annual.csv. They are not in the repository,
SPEC.md section 2 rule 6, so a digest of them would fail on every clean checkout
and would be worthless. Their bounds and their manifest entries are the checks
they get, plus the --strict-private offline run on the owner's machine.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = REPO_ROOT / "data" / "cache"
DIGEST_FILE = Path(__file__).resolve().parent / "cache_digests.json"

#: Columns that are provenance rather than measurement and carry no anchor. They
#: are still inside the sha256, so a change to one is still caught; they just do
#: not produce a readable "first and last value" pair.
_NOT_MEASUREMENTS = ("date",)


def committed_caches() -> list[str]:
    """Every committed cache, as repository relative posix paths, sorted."""
    return sorted(
        "data/cache/%s" % path.name for path in CACHE.glob("*.csv") if path.is_file()
    )


def _read_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    """The header and the data rows of one cache, split on commas.

    Deliberately not pandas. This file is a tripwire on the bytes, and a reader
    that normalises, coerces or reindexes is a reader that can absorb the very
    change this is here to catch. No committed cache quotes a field: the one
    field that could need it, revision_history, is written without commas for
    exactly this reason, and _digest asserts it.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return [], []
    return lines[0].split(","), [line.split(",") for line in lines[1:]]


def _is_number(cell: str) -> bool:
    try:
        float(cell)
    except ValueError:
        return False
    return True


def anchors_for(path: Path) -> dict[str, Any]:
    """The first and last published value of every value column, with its date.

    A value column is one whose non blank cells are all numbers. A column of
    True/False, of note file names or of a text label has no first and last
    VALUE, so it gets none, and the sha256 is what guards it.
    """
    header, rows = _read_rows(path)
    if "date" not in header:
        return {}
    date_at = header.index("date")
    out: dict[str, Any] = {}
    for index, column in enumerate(header):
        if column in _NOT_MEASUREMENTS:
            continue
        published = []
        numeric = True
        for row in rows:
            if index >= len(row):
                continue
            cell = row[index].strip()
            if not cell:
                continue
            if not _is_number(cell):
                numeric = False
                break
            published.append((row[date_at].strip(), cell))
        if not numeric or not published:
            continue
        out[column] = {
            "observations": len(published),
            "first": list(published[0]),
            "last": list(published[-1]),
        }
    return out


def digest_one(relative: str) -> dict[str, Any]:
    """The committed record for one cache."""
    path = REPO_ROOT / relative
    raw = path.read_bytes()
    header, rows = _read_rows(path)
    if b'"' in raw:
        raise AssertionError(
            "%s contains a quoted CSV field. Every committed cache in this "
            "project is written without one, and this reader splits on commas, "
            "so a quoted field would be read wrong here and nowhere else. Write "
            "the field without commas, the way revision_history does." % relative
        )
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "rows": len(rows),
        "columns": header,
        "anchors": anchors_for(path),
    }


def build() -> dict[str, Any]:
    """The whole digest file, measured from the caches on disk right now."""
    return {
        "note": (
            "A committed digest of every committed cache. A failure here means a "
            "cache changed: find out which source served what and why BEFORE "
            "regenerating this file. Regenerate with "
            "python tests/cache_digests.py --write and read the diff. See the "
            "module docstring of tests/cache_digests.py."
        ),
        "files": {relative: digest_one(relative) for relative in committed_caches()},
    }


def load() -> dict[str, Any]:
    """The committed digest file.

    Raises:
        AssertionError: when it is absent, because an absent tripwire reads
            exactly like a passing one.
    """
    if not DIGEST_FILE.exists():
        raise AssertionError(
            "%s is missing. It is committed, and without it a silent edit to any "
            "cache passes the whole gate. Regenerate it with "
            "python tests/cache_digests.py --write, and read the diff before "
            "committing it." % DIGEST_FILE
        )
    return json.loads(DIGEST_FILE.read_text(encoding="utf-8"))


def write() -> Path:
    """Rewrite the digest file from the caches on disk. Returns the path."""
    payload = build()
    DIGEST_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return DIGEST_FILE


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--write" in args:
        path = write()
        payload = load()
        print("wrote %s" % path)
        for relative, record in payload["files"].items():
            print(
                "  %-46s %s  %d rows  %d columns"
                % (relative, record["sha256"][:16], record["rows"], len(record["columns"]))
            )
        print("")
        print("Read the diff before committing it. A digest change is a data change.")
        return 0
    payload = build()
    committed = load() if DIGEST_FILE.exists() else {"files": {}}
    changed = [
        relative
        for relative, record in payload["files"].items()
        if committed["files"].get(relative, {}).get("sha256") != record["sha256"]
    ]
    for relative, record in payload["files"].items():
        mark = "CHANGED" if relative in changed else "ok"
        print("%-46s %-8s %s" % (relative, mark, record["sha256"][:16]))
    if changed:
        print("")
        print("%d cache(s) differ from the committed digest." % len(changed))
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
