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

THE ONE EXPECTED CHANGE, AND HOW IT IS RENEWED WITHOUT DEFEATING THE PIN

    python tests/cache_digests.py --renew --allow dgec_note_

The weekly refresh job collects a DGEC note, and a note legitimately changes the
note caches every week. A job that failed on that would fail every week and be
ignored inside a month; a job that ran --write would renew every pin in the file
with nobody seeing what moved. --renew does neither: it renews only the caches
whose name starts with an allowed prefix, REFUSES and writes nothing if anything
else moved, and prints the old and new sha256, the old and new row count and the
last value of every column that changed, which the job puts in the commit
message. See renew().

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


def _anchor_text(anchor: dict | None, key: str) -> str:
    value = (anchor or {}).get(key)
    return " ".join(str(x) for x in value) if value else "none"


def _record_lines(relative: str, before: dict | None, after: dict) -> list[str]:
    """One readable before and after for a renewed entry."""
    out = [
        "  %s%s" % (relative, "" if before else "  (new cache)"),
        "      sha256  %s  ->  %s"
        % ((before or {}).get("sha256", "not recorded")[:16], after["sha256"][:16]),
        "      rows    %s  ->  %d" % ((before or {}).get("rows", "none"), after["rows"]),
    ]
    for column, anchor in after.get("anchors", {}).items():
        was = ((before or {}).get("anchors") or {}).get(column)
        if (
            _anchor_text(was, "first") == _anchor_text(anchor, "first")
            and _anchor_text(was, "last") == _anchor_text(anchor, "last")
            and (was or {}).get("observations") == anchor.get("observations")
        ):
            continue
        out.append(
            "      %s: first %s -> %s, last %s -> %s, %s -> %s observations"
            % (
                column,
                _anchor_text(was, "first"),
                _anchor_text(anchor, "first"),
                _anchor_text(was, "last"),
                _anchor_text(anchor, "last"),
                (was or {}).get("observations", "none"),
                anchor.get("observations"),
            )
        )
    return out


def renew(allow: list[str]) -> tuple[int, list[str]]:
    """Rewrite the digests of the caches an allowed change may touch, and no others.

    THIS IS THE ANSWER TO A REAL DILEMMA AND IT IS NOT A LOOSENING OF THE PIN.
    The weekly refresh job of SPEC.md section 8 collects a DGEC note, and a note
    legitimately changes the note caches every single week. A job that failed on
    that would fail every week and be ignored inside a month, which is the same
    as having no job. A job that ran --write would renew every pin in the file
    without anybody seeing what moved, which is the same as having no pin.

    So the renewal is SCOPED and ITEMISED. Only a cache whose name starts with
    one of the allowed prefixes may have its digest renewed; a change to any
    other cache is refused, nothing is written, and the caller is expected to
    stop and open an issue rather than commit. What is renewed comes back as
    readable lines, old and new sha256, old and new row count, and the last
    value of every column that moved, so the commit that carries the renewal
    says in words what changed.

    Returns (exit code, report lines).
    """
    payload = build()
    committed = load() if DIGEST_FILE.exists() else {"files": {}}
    lines: list[str] = []
    changed = [
        relative
        for relative, record in payload["files"].items()
        if committed["files"].get(relative, {}).get("sha256") != record["sha256"]
    ]
    removed = sorted(set(committed["files"]) - set(payload["files"]))

    def allowed(relative: str) -> bool:
        stem = Path(relative).stem
        return any(stem.startswith(prefix) for prefix in allow)

    refused = sorted(r for r in changed + removed if not allowed(r))
    if refused:
        lines.append(
            "REFUSED. %d cache(s) changed that the allowed change cannot touch, "
            "so nothing was renewed and nothing should be committed:" % len(refused)
        )
        lines.extend("  %s" % r for r in refused)
        lines.append("")
        lines.append(
            "Allowed prefixes were: %s. Find out which source served what and "
            "why before anything else." % ", ".join(allow)
        )
        return 1, lines

    if not changed and not removed:
        lines.append("no committed cache changed, so no digest was renewed")
        return 0, lines

    for relative in sorted(changed):
        lines.extend(
            _record_lines(
                relative,
                committed["files"].get(relative),
                payload["files"][relative],
            )
        )
    for relative in removed:
        lines.append("  %s removed" % relative)
    write()
    lines.insert(0, "renewed %d digest(s) in %s:" % (len(changed) + len(removed), DIGEST_FILE.name))
    return 0, lines


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--renew" in args:
        allow = [args[i + 1] for i, a in enumerate(args) if a == "--allow" and i + 1 < len(args)]
        if not allow:
            print("--renew needs at least one --allow <series name prefix>")
            return 2
        code, lines = renew(allow)
        for line in lines:
            print(line)
        return code
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
