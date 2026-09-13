"""Value level assertions on every committed cache, so a silent edit cannot pass.

SPEC.md section 5.4 commits the caches so the site builds and the results
reproduce with no network. That makes the committed bytes the product, and it
makes a silent edit to one of them the worst failure this repository can have,
because nothing downstream would know.

WHAT THE GATE COULD NOT SEE BEFORE THIS FILE
----------------------------------------------
Gate 1 self audit, finding d.1. The audit put 99.99 into one cell of
data/cache/dgec_mbr_monthly.csv, a 172 percent error on a figure SPEC.md section
5.5 prints, and ran the whole gate:

    python scripts/refresh.py --offline    19 of 19 series ok, exit 0
    node tools/validate-data.mjs           15 of 15 checks passed, exit 0
    python -m pytest tests                 2 FAILED

Two of the four steps were blind, and pytest only caught it because the MBR is
one of exactly two series that had value level assertions, the other being the
Brent $/t conversion. The audit's own words: "A one digit change in, say,
opec_rotterdam_products_monthly would survive all four gate steps."

WHAT THIS FILE ASSERTS, IN THREE LAYERS
-----------------------------------------
1. THE ANCHORS THE SPEC SUPPLIES, read from data/seed/anchors.json rather than
   retyped here. The nine published MBR values of SPEC.md section 5.5 and the
   July 2026 Brent date figure, each against the committed cache it is a claim
   about. tests/test_dgec_anchor.py asserts the same nine against literals
   copied from the spec, and tests/test_events_anchors.py asserts that the two
   copies agree, so all three have to be changed together to move a number.

2. THE FIRST AND LAST PUBLISHED VALUE OF EVERY VALUE COLUMN OF EVERY COMMITTED
   CACHE, from tests/cache_digests.json. This is the readable layer: when it
   fires it names a file, a column, a date and two numbers.

3. A SHA256 OF EVERY COMMITTED CACHE, from the same file. This is the complete
   layer: write_cache is deterministic, so any edit anywhere in any committed
   cache changes it, including one inside its bounds, in the middle of the file,
   in a column nothing else reads.

Layer 3 alone would catch everything layer 2 catches. Layer 2 exists because a
gate that fails with two hex strings teaches nobody anything, and the first
thing a reader needs to know is whether a price moved or a file was rewritten.

A FAILURE HERE IS NOT A REASON TO REGENERATE THE DIGEST. It is a reason to find
out what changed and why. Once the data is right:

    python tests/cache_digests.py --write

and the diff is what gets reviewed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import cache_digests
from crack.sources import events_anchors as ea

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = REPO_ROOT / "data" / "cache"


@pytest.fixture(scope="module")
def committed():
    """The committed digest file."""
    return cache_digests.load()


@pytest.fixture(scope="module")
def measured():
    """The same measurement, taken from the caches on disk now."""
    return cache_digests.build()


# ==========================================================================
# Layer 1: the anchors SPEC.md section 5.5 supplies, read from the seed
# ==========================================================================

def test_every_spec_mbr_anchor_reproduces_from_the_committed_cache():
    """The nine published MBR values, re measured against the cache.

    Read out of data/seed/anchors.json rather than retyped, which is the whole
    reason that file holds them as data. The same function the refresh script
    uses is the one called here, so the manifest's claim and this assertion
    cannot drift: if this passes and the manifest says something else, the
    manifest is wrong about a check it ran, which is the failure
    crack.sources.events_anchors.measure_mbr_reproduction exists to prevent.
    """
    payload = ea.load_anchors()
    measurement = ea.measure_mbr_reproduction(payload["_mbr"])
    assert measurement["failures"] == [], (
        "an MBR anchor printed by DGEC does not reproduce from %s: %s. SPEC.md "
        "section 5.5 says to stop and show the page rather than adjust anything."
        % (measurement["cache"], "; ".join(measurement["failures"]))
    )
    assert measurement["reproduced"] == measurement["checked"] == 9


def test_the_july_2026_brent_anchor_reproduces_from_the_committed_cache():
    """SPEC.md section 5.5's sixth quotation anchor, from the seed's own figure.

    628 $/t, from the published $/bbl at DGEC's own 7.5 bbl/t. The factor comes
    out of the seed file too, so a change to either has to be made in the file a
    reader checks.
    """
    payload = ea.load_anchors()
    anchor = payload["anchors"]["brent_july_2026_usd_t"]
    factor = float(anchor["conversion_factor_bbl_per_t"])

    values = {}
    path = CACHE / "dgec_brent_monthly.csv"
    with open(path, "r", encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split(",")
        date_at = header.index("date")
        bbl_at = header.index("brent_usd_bbl")
        for line in handle:
            cells = line.rstrip("\n").split(",")
            if cells[bbl_at].strip():
                values[cells[date_at]] = float(cells[bbl_at])

    usd_bbl = values["2026-07-01"]
    assert round(usd_bbl * factor) == anchor["printed_value"], (
        "SPEC.md section 5.5 prints Brent date at %s $/t for July 2026. %s holds "
        "%r $/bbl, which is %.4f $/t at %g bbl/t."
        % (anchor["printed_value"], path.name, usd_bbl, usd_bbl * factor, factor)
    )


def test_the_five_unverifiable_product_anchors_are_still_unverifiable():
    """The seed and the monthly cache have to agree about what is missing.

    data/seed/anchors.json marks the five July 2026 product anchors unverified.
    tests/test_dgec_anchor.py skips them only while
    data/cache/dgec_note_printed_monthly.csv carries no July 2026 row. Those two
    statements are about the same fact and this is where they are compared, so
    the day the fact changes exactly one of them cannot quietly stay behind.
    """
    payload = ea.load_anchors()
    products = payload["anchors"]["july_2026_products_usd_t"]["values"]
    unverified = [item for item in products if item.get("status") != "verified"]

    header, rows = cache_digests._read_rows(CACHE / "dgec_note_printed_monthly.csv")
    date_at = header.index("date")
    months = {row[date_at][:7] for row in rows}

    if "2026-07" in months:
        assert unverified == [], (
            "data/cache/dgec_note_printed_monthly.csv now carries a July 2026 "
            "row, so the five product anchors in data/seed/anchors.json are no "
            "longer unverifiable and their status and status_note must be "
            "updated from the note that carries them."
        )
    else:
        assert len(unverified) == 5
        assert len(products) == 5


# ==========================================================================
# Layer 2: the first and last published value of every value column
# ==========================================================================

def _cases():
    """One case per (file, column) pair in the committed digest.

    Collected at import time so each column is its own test id and a failure
    names the column in the report rather than inside a loop.
    """
    if not cache_digests.DIGEST_FILE.exists():
        return [("<no committed digest>", "<none>")]
    payload = json.loads(cache_digests.DIGEST_FILE.read_text(encoding="utf-8"))
    return [
        (relative, column)
        for relative, record in sorted(payload["files"].items())
        for column in sorted(record.get("anchors", {}))
    ]


@pytest.mark.parametrize("relative,column", _cases())
def test_the_ends_of_every_value_column_are_what_was_committed(
    relative, column, committed, measured
):
    """Value level assertions on every committed cache, not only on two of them.

    The first and last published value of every value column, with its date.
    This is the layer that makes a one digit edit fail with a sentence a person
    can act on.
    """
    if relative == "<no committed digest>":
        pytest.fail(
            "%s is missing, so nothing in this file is asserting anything. "
            "Regenerate it with python tests/cache_digests.py --write"
            % cache_digests.DIGEST_FILE
        )
    assert relative in measured["files"], (
        "%s is in the committed digest and not on disk. A committed cache was "
        "deleted, SPEC.md section 5.4 commits them" % relative
    )
    expected = committed["files"][relative]["anchors"][column]
    actual = measured["files"][relative]["anchors"].get(column)
    assert actual is not None, (
        "%s no longer carries a value column named %r, or that column now holds "
        "text. It used to hold %d published values, %s to %s"
        % (
            relative,
            column,
            expected["observations"],
            expected["first"][0],
            expected["last"][0],
        )
    )
    assert actual["first"] == expected["first"], (
        "%s %s: the FIRST published value is now %s on %s and the committed "
        "digest says %s on %s. Find out what the source served and why before "
        "regenerating the digest."
        % (
            relative,
            column,
            actual["first"][1],
            actual["first"][0],
            expected["first"][1],
            expected["first"][0],
        )
    )
    assert actual["last"] == expected["last"], (
        "%s %s: the LAST published value is now %s on %s and the committed "
        "digest says %s on %s."
        % (
            relative,
            column,
            actual["last"][1],
            actual["last"][0],
            expected["last"][1],
            expected["last"][0],
        )
    )
    assert actual["observations"] == expected["observations"], (
        "%s %s now carries %d published value(s) and the committed digest says "
        "%d."
        % (relative, column, actual["observations"], expected["observations"])
    )


# ==========================================================================
# Layer 3: the bytes
# ==========================================================================

def test_the_digest_covers_every_committed_cache_and_no_others(committed):
    """A digest that quietly stopped covering a file would still be green.

    That is the one failure mode a tripwire cannot have, so the set of files is
    asserted rather than iterated over.
    """
    assert sorted(committed["files"]) == cache_digests.committed_caches(), (
        "the committed digest covers %s and data/cache holds %s"
        % (sorted(committed["files"]), cache_digests.committed_caches())
    )
    assert len(committed["files"]) >= 13


@pytest.mark.parametrize("relative", cache_digests.committed_caches())
def test_every_committed_cache_matches_its_committed_digest(
    relative, committed, measured
):
    """The sha256 of the exact bytes on disk.

    This is what makes a one digit edit anywhere in any committed cache fail
    `make gate`, including inside its declared bounds, in the middle of a file,
    in a column no other test reads. write_cache is deterministic: utf-8, LF, no
    index, plain decimal floats, so a clean rebuild of unchanged data reproduces
    these bytes exactly.

    IF THIS FAILS, DO NOT REGENERATE THE DIGEST FIRST. Find out which source
    served what and why. Then python tests/cache_digests.py --write, and read
    the diff.
    """
    assert relative in committed["files"], (
        "%s is a committed cache with no entry in %s. Regenerate the digest with "
        "python tests/cache_digests.py --write and read the diff"
        % (relative, cache_digests.DIGEST_FILE)
    )
    want = committed["files"][relative]
    got = measured["files"][relative]
    assert got["rows"] == want["rows"], (
        "%s now has %d row(s) and the committed digest says %d"
        % (relative, got["rows"], want["rows"])
    )
    assert got["columns"] == want["columns"], (
        "%s now has columns %s and the committed digest says %s"
        % (relative, got["columns"], want["columns"])
    )
    assert got["sha256"] == want["sha256"], (
        "%s has the right shape and different bytes: %d bytes against %d "
        "committed, sha256 %s against %s. A value changed inside its bounds. "
        "Find out what the source served before touching the digest."
        % (relative, got["bytes"], want["bytes"], got["sha256"], want["sha256"])
    )


def test_a_one_digit_edit_is_detected(tmp_path):
    """The tripwire is tested, not assumed.

    A gate step nobody has watched fail is a gate step nobody knows works. This
    copies a committed cache, changes one digit of one value in the middle of
    it, and asserts that both layers notice: the sha256 and the per column
    anchors when the edited cell happens to be an end.
    """
    relative = "data/cache/dgec_mbr_monthly.csv"
    original = (REPO_ROOT / relative).read_text(encoding="utf-8")
    before = cache_digests.digest_one(relative)

    lines = original.split("\n")
    header = lines[0].split(",")
    value_at = header.index("mbr_usd_bbl")
    middle = len(lines) // 2
    cells = lines[middle].split(",")
    digits = cells[value_at]
    # One digit, in place, so the value stays a plausible margin well inside
    # BOUNDS_MARGIN_USD_BBL and the row count and column list do not move.
    cells[value_at] = digits[:-1] + ("8" if digits[-1] != "8" else "7")
    lines[middle] = ",".join(cells)

    edited = tmp_path / "dgec_mbr_monthly.csv"
    edited.write_text("\n".join(lines), encoding="utf-8", newline="")

    import hashlib

    after = hashlib.sha256(edited.read_bytes()).hexdigest()
    assert after != before["sha256"], (
        "a one digit change to a value in the middle of a committed cache did "
        "not change its sha256, so this whole file is asserting nothing"
    )
    # And the file on disk is untouched by this test.
    assert (REPO_ROOT / relative).read_text(encoding="utf-8") == original
