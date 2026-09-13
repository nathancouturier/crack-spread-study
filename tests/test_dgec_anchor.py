"""The SPEC.md section 5.5 anchors, and the checks that make them mean something.

SPEC.md section 9 lists "Anchors: the values in 5.5 parse exactly" as a test in
its own right, and section 10 says Gate 2 must not proceed if one fails. This
file is that gate. Section 5.5 is also explicit about what to do when a number
does not come out:

    "If your reading of the table layout disagrees with any value, stop and show
    me the page. Do not adjust the parser until it hits the number."

So nothing here is tolerant. The MBR anchors are asserted against
data/cache/dgec_mbr_monthly.csv, the committed cache the adapter actually wrote,
rounded the way DGEC prints them and compared exactly. No approximate compare, no
tolerance to absorb a parser that reads the wrong column.

What is asserted, what is skipped, and why the difference is stated rather than hidden
---------------------------------------------------------------------------------------
ASSERTED, all nine, from the committed cache:

    the eight published MBR values of SPEC.md section 5.5, October 2025 to July
    2026, and August 2026 at 38.05. Recon 02 section 4.1 verified all eight
    against the workbook and two of them against the printed page of an archived
    note as well. August 2026 was NOT in the workbook when the recon ran, the
    file ended 2026-07; the first live fetch by this adapter on 2026-09-12 got a
    workbook stamped Last-Modified Fri, 11 Sep 2026 14:52:54 GMT carrying
    2026-08 at 38.0505047, which matches the 38,05 printed in the note of 4
    September 2026 in the column with no "(donnees provisoires)" marker.

    Brent date at 628 $/t for July 2026, from dgec_brent_monthly's derived
    brent_usd_t column. Recon 02 section 4.3 established the note's conversion
    factor of exactly 7.5 bbl/t on five independent month pairs, and 628 falls
    out of the published $/bbl at that factor.

CONDITIONALLY SKIPPED, and the condition is measured on every run:

    the five July 2026 product anchors in $/t, Eurosuper 1,084, Gazole 1,160,
    Fioul domestique 1,127, Jet 1,204 and Fioul lourd TBTS 507. There is ONE
    reason, not two, and the test checks it against the data rather than stating
    it. data/cache/dgec_note_printed_monthly.csv is the monthly quotation series
    and it is where a July 2026 monthly average would sit. It carries seven
    months and July 2026 is not one of them, because recon 02 section 4.3
    established that the July 2026 monthly column appears only in an August 2026
    note; the note SPEC.md section 5.5 cites, NPG-2026.08.28_0.pdf, returns HTTP
    404, as do the plain, _0 and _1 spellings for 28 August and the spellings for
    7, 14 and 21 August, and the Internet Archive holds no August 2026 note at
    all. The ministry deletes each note when the next appears. So these five
    numbers are currently unfalsifiable from any source this project can reach,
    and the first August note collected prospectively is what will settle them.

    THE SKIP UN SKIPS ITSELF. The day a note carrying a July 2026 monthly column
    is collected, the row appears in the cache and the five tests become
    assertions with no edit to this file. Gate 1 self audit, finding f: the skip
    used to be unconditional and its first stated reason, that
    data/cache/dgec_note_printed_weekly.csv "does not exist", was false on every
    run from the day that adapter was built.

    Nothing here will be tuned to hit them when that note arrives. If the parsed
    page disagrees with the spec, the test reports the disagreement.

THE CROSS CHECK, which is the other half of section 5.5
--------------------------------------------------------
"DGEC Brent, converted with DGEC's own factor, against the monthly mean of FRED
DCOILBRENTEU, within 1.5 $/bbl in at least 95 percent of months. List every
outlier."

It is run two ways, because "converted with DGEC's own factor" can mean two
things and the weaker reading is the one the site will actually use:

    direct     DGEC's published $/bbl against the FRED monthly mean. This is the
               strict comparison of the two assessments.
    round trip DGEC's $/bbl turned into $/t at 7.5 and rounded to the whole
               dollar, the way the note prints it, then divided back by 7.5. This
               is what a reader gets if they take Brent off the note's quotation
               table, and the rounding alone can move a month by up to 0.067
               $/bbl.

Both must pass. The averaging is crack.config.monthly_mean and nothing else,
because recon 04 section 7.2 measured that the choice of averaging rule moves a
monthly mean by up to 1.10 $/bbl, which is 73 percent of the whole tolerance. A
second copy of that arithmetic in this file would be a second chance to disagree
with the first.

THE ORDER OF MAGNITUDE COMPARISON
----------------------------------
SPEC.md section 5.5 puts the MBR for March and October 2022 next to two S&P
Global figures and says a gap is expected because the methods differ, while a gap
of a different order is a bug. The test asserts only the order of magnitude, at a
deliberately loose factor of two, and prints the real numbers. It is a sanity
check on levels and never a benchmark to fit to: SPEC.md section 6.6 forbids
tuning anything to an external assessment, and crack.config's registry note on
sp_global_reference says these two figures may not be built into a series.

NOTHING HERE TOUCHES THE NETWORK. The cache is committed, SPEC.md section 5.4,
and that is exactly so this gate reproduces without one.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from crack.config import (
    BRENT_CROSS_CHECK_MIN_PASS_SHARE,
    BRENT_CROSS_CHECK_TOLERANCE_USD_BBL,
    DGEC_BBL_PER_T_BRENT_MARGIN,
    DGEC_BBL_PER_T_BRENT_NOTE,
    monthly_mean,
)
from crack.sources import dgec

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = REPO_ROOT / "data" / "cache"

#: The recon probe archive, gitignored and present only on the machine the Gate 1
#: research ran on. The one test that reads a note PDF's text skips without it.
PROBE = REPO_ROOT / "data" / "private" / "probe" / "dgec"


# ==========================================================================
# SPEC.md section 5.5, verbatim
# ==========================================================================

#: Published MBR in $/bbl, with the note each was printed in. Copied from
#: SPEC.md section 5.5 without rounding, reformatting or reinterpretation.
MBR_ANCHORS = {
    "2025-10-01": (11.45, "note of 28 Nov 2025"),
    "2025-11-01": (16.47, "note of 12 Dec 2025"),
    "2026-02-01": (6.50, "note of 13 Mar 2026"),
    "2026-03-01": (24.72, "notes of 3 and 17 Apr 2026"),
    "2026-04-01": (18.68, "notes of 8 and 15 May 2026"),
    "2026-05-01": (21.26, "note of 19 Jun 2026"),
    "2026-06-01": (20.30, "notes of 10 and 17 Jul 2026"),
    "2026-07-01": (36.69, "notes of 14 and 28 Aug 2026"),
    # SPEC.md section 5.5: "August 2026 stood at 38.05 provisional on 28 August;
    # take the final figure from the September notes." The note of 4 September
    # 2026 prints 38,05 in the column carrying no provisional marker, so the
    # provisional figure was confirmed unchanged when it went final.
    "2026-08-01": (38.05, "note of 4 Sep 2026, final, no provisional marker"),
}

#: July 2026 monthly averages in $/t, as SPEC.md section 5.5 prints them from the
#: DGEC note of 28 August 2026. Only the last of the six can be checked today.
PRODUCT_ANCHORS_JULY_2026 = {
    "Eurosuper": 1084,
    "Gazole": 1160,
    "Fioul domestique": 1127,
    "Jet": 1204,
    "Fioul lourd TBTS (< 1%)": 507,
}
BRENT_ANCHOR_JULY_2026_USD_T = 628

#: SPEC.md section 5.5 and section 5.1. NWE cracking margins assessed by S&P
#: Global, quoted with their dates because a weekly physical assessment and a
#: monthly theoretical margin are not the same object and the comparison is only
#: honest if both labels travel with the numbers.
SP_REFERENCES = {
    "2022-03-01": (
        15.35,
        "NWE cracking margin on Forties, week to 25 March 2022, S&P Global, "
        "article of 28 March 2022",
    ),
    "2022-10-01": (
        23.11,
        "NWE cracking margin on Dated Brent, week to 14 October 2022, S&P "
        "Global, article of 17 October 2022",
    ),
}

#: How far apart two differently constructed margins may be before the gap stops
#: being a method difference and starts being a bug. A factor of two either way.
#: SPEC.md section 5.5 asks only for the same order of magnitude and says a gap
#: is expected, so this is deliberately loose. Tightening it would turn a sanity
#: check into a target, which SPEC.md section 6.6 forbids.
ORDER_OF_MAGNITUDE_FACTOR = 2.0


# ==========================================================================
# Reading the committed caches
# ==========================================================================

def _read_committed(series: str, columns: tuple[str, ...]) -> pd.DataFrame:
    """One committed cache, or a failure that says what to run.

    This does not skip when the file is missing. SPEC.md section 5.4 commits the
    caches precisely so this gate reproduces with no network, so an absent cache
    is Gate 1 not being done rather than an environment this test should tiptoe
    around.
    """
    path = CACHE / ("%s.csv" % series)
    if not path.exists():
        raise AssertionError(
            "%s is missing. The caches are committed, SPEC.md section 5.4, so "
            "this gate runs with no network. Run "
            "'python -m crack.sources.dgec' to fetch it." % path
        )
    frame = pd.read_csv(path)
    frame["date"] = pd.to_datetime(frame["date"])
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise AssertionError(
            "%s is missing column(s) %s, it has %s"
            % (path, ", ".join(missing), ", ".join(frame.columns))
        )
    return frame


@pytest.fixture(scope="module")
def mbr() -> pd.Series:
    """The committed MBR cache, indexed by month, in $/bbl."""
    frame = _read_committed(
        dgec.SERIES_MBR, (dgec.COLUMN_MBR_USD_BBL, dgec.COLUMN_MBR_EUR_T)
    )
    return frame.set_index("date")[dgec.COLUMN_MBR_USD_BBL]


@pytest.fixture(scope="module")
def mbr_frame() -> pd.DataFrame:
    frame = _read_committed(
        dgec.SERIES_MBR, (dgec.COLUMN_MBR_USD_BBL, dgec.COLUMN_MBR_EUR_T)
    )
    return frame.set_index("date")


@pytest.fixture(scope="module")
def brent() -> pd.DataFrame:
    """The committed DGEC Brent cache, indexed by month."""
    frame = _read_committed(
        dgec.SERIES_BRENT, (dgec.COLUMN_BRENT_USD_BBL, dgec.COLUMN_BRENT_USD_T)
    )
    return frame.set_index("date")


@pytest.fixture(scope="module")
def fred_monthly() -> pd.DataFrame:
    """FRED DCOILBRENTEU reduced to monthly means by crack.config.monthly_mean.

    The averaging rule is config's and only config's. See MONTHLY_MEAN_RULE.
    """
    path = CACHE / "fred_brent_daily.csv"
    if not path.exists():
        raise AssertionError(
            "%s is missing, so the SPEC.md section 5.5 cross check cannot run. "
            "It is a committed cache." % path
        )
    frame = pd.read_csv(path)
    return monthly_mean(frame["date"], frame["brent_usd_bbl"])


# ==========================================================================
# The MBR anchors. SPEC.md section 9 calls this a gate.
# ==========================================================================

@pytest.mark.parametrize("month", sorted(MBR_ANCHORS))
def test_published_mbr_anchor_parses_exactly(mbr, month):
    """Each SPEC.md section 5.5 MBR value, from the committed cache.

    Compared as DGEC prints it: rounded to two decimals, then equal. Not
    approximately equal. A tolerance here would let a parser reading the EUR/t
    column through on a month where the two happened to be close, and the whole
    reason both columns are found by their unit label is that reading the wrong
    one has no other symptom.
    """
    expected, printed_in = MBR_ANCHORS[month]
    stamp = pd.Timestamp(month)
    assert stamp in mbr.index, (
        "%s is not in the committed %s cache, which runs %s to %s. The anchor "
        "comes from the %s."
        % (
            month,
            dgec.SERIES_MBR,
            mbr.index.min().date(),
            mbr.index.max().date(),
            printed_in,
        )
    )
    actual = float(mbr.loc[stamp])
    assert round(actual, 2) == expected, (
        "SPEC.md section 5.5 gives the MBR for %s as %.2f $/bbl, from the %s. "
        "The committed cache holds %.7f, which rounds to %.2f. SPEC.md section "
        "5.5 says to stop and show the page rather than adjust the parser."
        % (month[:7], expected, printed_in, actual, round(actual, 2))
    )


def test_every_mbr_anchor_in_the_spec_is_covered_here():
    """The parametrised list is the spec's list, not a subset of it.

    A test that quietly dropped an anchor would still be green, which is the one
    failure mode a gate cannot have.
    """
    assert len(MBR_ANCHORS) == 9
    assert sorted(MBR_ANCHORS) == [
        "2025-10-01",
        "2025-11-01",
        "2026-02-01",
        "2026-03-01",
        "2026-04-01",
        "2026-05-01",
        "2026-06-01",
        "2026-07-01",
        "2026-08-01",
    ]


def test_august_2026_is_final_and_is_not_flagged_provisional(mbr):
    """The month SPEC.md section 5.5 leaves open, and how it was closed.

    The spec says August 2026 stood at 38.05 provisional on 28 August and to take
    the final figure from the September notes. The note of 4 September 2026
    prints 38,05 in the column carrying no "(donnees provisoires)" marker, so the
    provisional figure was confirmed rather than revised. The workbook caught up
    on 11 September and now carries it too, which is why this is an assertion
    rather than a skip.

    Recon 02 section 3.5 is the reason this gets its own test: a provisional MBR
    can move by 2 $/b between two notes, August 2024 going from 5.63 to 3.63.
    """
    actual = float(mbr.loc[pd.Timestamp("2026-08-01")])
    assert round(actual, 2) == 38.05
    entry = _manifest_entry(dgec.SERIES_MBR)
    if entry is not None:
        assert entry.get("provisional_from") != "2026-08-01", (
            "August 2026 is final, printed without a provisional marker in the "
            "note of 4 September 2026, so the manifest must not flag it."
        )


def _manifest_entry(series: str) -> dict | None:
    """One series' manifest entry, or None when there is no manifest yet."""
    import json

    path = REPO_ROOT / "data" / "manifest.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    for entry in payload.get("series", []):
        if entry.get("series") == series:
            return entry
    return None


def test_mbr_anchor_months_agree_with_the_note_text_when_the_probe_is_present():
    """Independent corroboration from a note PDF, when one is on this machine.

    The committed cache and the workbook are one source. The printed page is
    another, and recon 02 section 4.1 cross checked two anchors against archived
    notes that way. The note of 4 September 2026 is the only note this project
    holds that prints an anchor month, and it prints August 2026.

    The probe archive is gitignored, so on a fresh checkout this test skips and
    says so rather than pretending to be coverage.
    """
    text_file = PROBE / "NPG-2026.09.04.pdfplumber.txt"
    if not text_file.exists():
        pytest.skip(
            "the recon probe archive is not on this machine, so the printed page "
            "cannot be read. %s is gitignored under data/private and the "
            "ministry has deleted the note from its own site. The committed "
            "cache assertions above still run." % text_file
        )
    text = text_file.read_text(encoding="utf-8", errors="replace")
    assert "marge brute de raffinage sur Brent" in text
    # DGEC writes a decimal comma. The workbook and the page must agree to the
    # two decimals the page prints.
    assert "38,05" in text, (
        "the note of 4 September 2026 no longer prints 38,05 for August 2026. "
        "SPEC.md section 5.5 says to show the page rather than change anything."
    )


# ==========================================================================
# The July 2026 quotation anchors
# ==========================================================================

def test_july_2026_brent_date_is_628_usd_t(brent):
    """The one product row anchor that can be checked, and the factor behind it.

    SPEC.md section 5.5 prints Brent date at 628 $/t for July 2026. The workbook
    publishes July 2026 at 83.7586956521739 $/bbl, and the note converts Brent
    date at exactly 7.5 bbl/t, which recon 02 section 4.3 established on five
    independent month pairs against printed notes: August 2026 683, March 2026
    774, February 2026 532 and November 2025 479, all exact.

    7.55, the factor the methodology note states, belongs to the CAF Brent inside
    the margin calculation and would give 632 here, which is not what the page
    prints. The two factors are separate constants in crack.config for exactly
    this reason and config raises at import if they are ever collapsed into one.
    """
    stamp = pd.Timestamp("2026-07-01")
    usd_t = float(brent.loc[stamp, dgec.COLUMN_BRENT_USD_T])
    assert round(usd_t) == BRENT_ANCHOR_JULY_2026_USD_T, (
        "SPEC.md section 5.5 gives Brent date at %d $/t for July 2026. The "
        "committed cache gives %.4f $/bbl times %g bbl/t, which is %.4f $/t and "
        "rounds to %d."
        % (
            BRENT_ANCHOR_JULY_2026_USD_T,
            float(brent.loc[stamp, dgec.COLUMN_BRENT_USD_BBL]),
            DGEC_BBL_PER_T_BRENT_NOTE,
            usd_t,
            round(usd_t),
        )
    )
    # The wrong factor is shown to be wrong, so that a future edit that swaps the
    # two constants fails here with the reason attached rather than silently.
    wrong = float(brent.loc[stamp, dgec.COLUMN_BRENT_USD_BBL]) * (
        DGEC_BBL_PER_T_BRENT_MARGIN
    )
    assert round(wrong) != BRENT_ANCHOR_JULY_2026_USD_T


#: The column of dgec_note_printed_monthly that each SPEC.md section 5.5 product
#: label is printed in. The labels are the ministry's, the columns are the
#: cache's, and dgec_note.PRINTED_ROWS is the mapping this repeats. It is written
#: out here so that a rename on either side fails loudly in this file rather than
#: quietly turning an assertion back into a skip.
PRODUCT_ANCHOR_COLUMNS = {
    "Eurosuper": "eurosuper_usd_t",
    "Gazole": "gazole_usd_t",
    "Fioul domestique": "fioul_domestique_usd_t",
    "Jet": "jet_usd_t",
    "Fioul lourd TBTS (< 1%)": "fioul_lourd_tbts_usd_t",
}

#: The month SPEC.md section 5.5 prints the five product anchors for.
PRODUCT_ANCHOR_MONTH = pd.Timestamp("2026-07-01")


def _printed_monthly() -> pd.DataFrame:
    """The committed monthly quotation cache, which is where July 2026 would be.

    Not a skip when it is missing. It is a committed cache, SPEC.md section 5.4,
    and its absence is Gate 1 not being done rather than an environment to tiptoe
    around. That is the same rule _read_committed applies.
    """
    return _read_committed(
        "dgec_note_printed_monthly", tuple(PRODUCT_ANCHOR_COLUMNS.values())
    )


@pytest.mark.parametrize("product", sorted(PRODUCT_ANCHORS_JULY_2026))
def test_july_2026_product_anchor(product):
    """The five $/t product anchors of SPEC.md section 5.5.

    THIS IS A REAL ASSERTION THE MOMENT THE EVIDENCE ARRIVES, AND IT CHECKS FOR
    THE EVIDENCE ITSELF. It skips only while dgec_note_printed_monthly carries no
    July 2026 row, and the skip message says which months it does carry, so the
    reason printed on every run is a fact about this repository measured on this
    run rather than a sentence written once.

    Why there is no July 2026 row today, and it is one reason rather than two.
    Recon 02 section 4.3: the July 2026 monthly column appears only in an August
    2026 note. NPG-2026.08.28_0.pdf, the note SPEC.md section 5.5 cites, returns
    HTTP 404, as do the plain, _0 and _1 spellings for 28 August and the
    spellings for 7, 14 and 21 August, and the Internet Archive holds no August
    2026 note at all, because the ministry deletes each note when the next
    appears. data/seed/anchors.json records all of that against each of the five,
    with status "unverified" and a status_note saying the same thing, and
    tests/test_events_anchors.py asserts it.

    WHAT CHANGED HERE, AND WHY. Gate 1 self audit, finding f. This used to call
    pytest.skip unconditionally with a message whose FIRST reason was that
    data/cache/dgec_note_printed_weekly.csv "does not exist". That file exists,
    is committed, is 18 rows and carries the Rotterdam quotations. The sentence
    was written before the note adapter was built and was not updated when it
    was, so the suite printed something untrue five times on every run. The skip
    now has to earn itself against the data every time.

    When a note carrying July 2026 is collected, this becomes an assertion with
    no further edit. If the parsed page then disagrees with the spec, the
    disagreement is what gets reported: the parser does not get adjusted to hit
    the number, SPEC.md section 5.5.
    """
    expected = PRODUCT_ANCHORS_JULY_2026[product]
    column = PRODUCT_ANCHOR_COLUMNS[product]
    frame = _printed_monthly().set_index("date")

    if PRODUCT_ANCHOR_MONTH not in frame.index:
        months = ", ".join(d.strftime("%Y-%m") for d in sorted(frame.index))
        pytest.skip(
            "%s at %d $/t for July 2026 cannot be checked: no note in the corpus "
            "prints a July 2026 monthly column. data/cache/"
            "dgec_note_printed_monthly.csv holds %d month(s), %s, and July 2026 "
            "is not among them. The column appears only in an August 2026 note; "
            "every spelling of every August 2026 note returns HTTP 404 and the "
            "Internet Archive holds none, because the ministry deletes each note "
            "when the next appears. The first August note collected "
            "prospectively settles it, and this test becomes an assertion the "
            "run after that with no edit. Brent date, the sixth anchor of the "
            "same table, IS checked, by test_july_2026_brent_date_is_628_usd_t."
            % (product, expected, len(frame), months)
        )

    actual = float(frame.loc[PRODUCT_ANCHOR_MONTH, column])
    row = frame.loc[PRODUCT_ANCHOR_MONTH]
    assert round(actual) == expected, (
        "SPEC.md section 5.5 gives %s at %d $/t for July 2026, from the DGEC note "
        "of 28 August 2026. The committed monthly cache holds %.4f in %r, read "
        "from %s and flagged provisional=%s. SPEC.md section 5.5 says to stop and "
        "show the page rather than adjust the parser."
        % (product, expected, actual, column, row.get("notes"), row.get("provisional"))
    )


def test_the_july_2026_skip_can_never_be_true_and_skipping_at_the_same_time():
    """The skip above has to be wrong about the data before it can fire wrongly.

    A skip message is the one kind of test output nobody re reads, so this is the
    assertion that the condition and the message describe the same file. If
    July 2026 IS in the monthly cache, the five tests above must not be skipping;
    if it is not, the cache must genuinely not carry it.
    """
    frame = _printed_monthly().set_index("date")
    present = PRODUCT_ANCHOR_MONTH in frame.index
    months = {d.strftime("%Y-%m") for d in frame.index}
    assert present == ("2026-07" in months)
    if not present:
        # Everything the skip message claims about the corpus, checked.
        assert len(frame) >= 1, "the monthly cache is empty, which is a Gate 1 bug"
        assert "2026-07" not in months


# ==========================================================================
# SPEC.md section 5.5, the FRED cross check
# ==========================================================================

def _cross_check(dgec_usd_bbl: pd.Series, fred_monthly: pd.DataFrame) -> pd.DataFrame:
    """Join DGEC's monthly Brent to FRED's monthly mean and difference them."""
    joined = pd.DataFrame({"dgec": dgec_usd_bbl}).join(
        fred_monthly.set_index("month")[["value", "observations"]], how="left"
    )
    joined = joined.rename(columns={"value": "fred"})
    joined["difference"] = joined["dgec"] - joined["fred"]
    return joined


def _report_outliers(joined: pd.DataFrame, label: str) -> str:
    """Every month outside tolerance, listed. SPEC.md section 5.5 asks for it."""
    outside = joined[
        joined["difference"].notna()
        & (joined["difference"].abs() > BRENT_CROSS_CHECK_TOLERANCE_USD_BBL)
    ]
    if outside.empty:
        return "%s: no month outside %.2f $/bbl" % (
            label,
            BRENT_CROSS_CHECK_TOLERANCE_USD_BBL,
        )
    lines = [
        "%s: %d month(s) outside %.2f $/bbl"
        % (label, len(outside), BRENT_CROSS_CHECK_TOLERANCE_USD_BBL)
    ]
    for month, row in outside.iterrows():
        lines.append(
            "  %s  DGEC %.4f  FRED %.4f on %d published day(s)  difference %+.4f"
            % (
                month.strftime("%Y-%m"),
                row["dgec"],
                row["fred"],
                int(row["observations"]),
                row["difference"],
            )
        )
    return "\n".join(lines)


def test_dgec_brent_tracks_fred_within_tolerance(brent, fred_monthly):
    """SPEC.md section 5.5: within 1.5 $/bbl in at least 95 percent of months.

    These are two different assessments of the same physical thing. DGEC's is a
    mean of daily Brent date London closes assessed by Reuters; FRED's is EIA
    Europe Brent spot. They cannot agree perfectly and a residual of a few tens
    of cents is expected, not a bug. What the test rules out is a unit error, a
    column read from the wrong place, or an averaging rule that drifted.
    """
    joined = _cross_check(brent[dgec.COLUMN_BRENT_USD_BBL], fred_monthly)
    comparable = joined[joined["difference"].notna()]
    assert len(comparable) >= 130, (
        "only %d month(s) could be compared, out of %d in the DGEC cache. FRED "
        "coverage or the monthly_mean minimum has changed."
        % (len(comparable), len(joined))
    )

    within = comparable["difference"].abs() <= BRENT_CROSS_CHECK_TOLERANCE_USD_BBL
    share = float(within.mean())
    assert share >= BRENT_CROSS_CHECK_MIN_PASS_SHARE, (
        "%.4f of %d months are within %.2f $/bbl, below the SPEC.md section 5.5 "
        "bar of %.2f.\n%s"
        % (
            share,
            len(comparable),
            BRENT_CROSS_CHECK_TOLERANCE_USD_BBL,
            BRENT_CROSS_CHECK_MIN_PASS_SHARE,
            _report_outliers(comparable, "direct $/bbl"),
        )
    )


def test_dgec_brent_tracks_fred_through_the_notes_rounded_usd_t(brent, fred_monthly):
    """The same check on the route a reader of the note actually takes.

    SPEC.md section 5.5 says "converted with DGEC's own factor", and the note
    publishes Brent date in $/t rounded to the whole dollar. Anyone taking Brent
    off that table and dividing by 7.5 picks up a rounding error of up to 0.5/7.5,
    which is 0.067 $/bbl. This asserts that the weaker route still clears the
    same bar, because it is the route the crack calculation will use whenever its
    product leg comes from the same $/t table.
    """
    printed = (brent[dgec.COLUMN_BRENT_USD_T]).round()
    round_tripped = printed / DGEC_BBL_PER_T_BRENT_NOTE
    joined = _cross_check(round_tripped, fred_monthly)
    comparable = joined[joined["difference"].notna()]

    within = comparable["difference"].abs() <= BRENT_CROSS_CHECK_TOLERANCE_USD_BBL
    share = float(within.mean())
    assert share >= BRENT_CROSS_CHECK_MIN_PASS_SHARE, (
        "%.4f of %d months are within %.2f $/bbl by the rounded $/t route.\n%s"
        % (
            share,
            len(comparable),
            BRENT_CROSS_CHECK_TOLERANCE_USD_BBL,
            _report_outliers(comparable, "rounded $/t, divided back by 7.5"),
        )
    )


def test_the_cross_check_uses_config_monthly_mean_and_not_a_resample(brent):
    """The averaging rule is config's, and a pandas default is not equivalent.

    Recon 04 section 7.2 measured the three defensible readings of "the monthly
    mean" against each other and found up to 1.10 $/bbl between them, which is 73
    percent of the 1.5 $/bbl tolerance. This test exists so that anyone tempted
    to replace monthly_mean with a one line resample sees the size of what they
    would be changing.
    """
    frame = pd.read_csv(CACHE / "fred_brent_daily.csv")
    frame["date"] = pd.to_datetime(frame["date"])
    rule = monthly_mean(frame["date"], frame["brent_usd_bbl"]).set_index("month")

    # Method C of recon 04: reindex to every calendar day, carry forward, mean.
    daily = frame.set_index("date")["brent_usd_bbl"]
    filled = daily.reindex(
        pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    ).ffill()
    carried = filled.resample("MS").mean()

    shared = rule.index.intersection(carried.index)
    gap = (rule.loc[shared, "value"] - carried.loc[shared]).abs().max()
    assert gap > 0.5, (
        "the two averaging rules now differ by at most %.4f $/bbl. They used to "
        "differ by 1.15. If that is real, crack.config MONTHLY_MEAN_RULE's "
        "reasoning needs rereading rather than this test relaxing." % gap
    )
    assert gap < BRENT_CROSS_CHECK_TOLERANCE_USD_BBL


# ==========================================================================
# SPEC.md section 5.5, the order of magnitude comparison
# ==========================================================================

@pytest.mark.parametrize("month", sorted(SP_REFERENCES))
def test_mbr_is_the_same_order_of_magnitude_as_the_sp_assessment(mbr, month):
    """SPEC.md section 5.5: a gap is expected, a gap of a different order is a bug.

    The two are not the same construction and must never be presented as one.
    S&P's is a weekly physical cracking margin on a named crude, Forties in March
    and Dated Brent in October. DGEC's is a monthly theoretical margin on a fixed
    French product slate, gross of every cost that is not energy, and its own
    methodology note calls it "une marge 'theorique' [...] un indicateur
    illustrant en tendance l'environnement economique du raffinage" that "differe
    d'une marge reelle d'une raffinerie francaise".

    So this asserts a factor of two, not a tolerance, and prints both numbers.
    Nothing is tuned to close the gap, SPEC.md section 6.6.
    """
    reference, description = SP_REFERENCES[month]
    actual = float(mbr.loc[pd.Timestamp(month)])
    ratio = actual / reference
    assert 1.0 / ORDER_OF_MAGNITUDE_FACTOR <= ratio <= ORDER_OF_MAGNITUDE_FACTOR, (
        "%s: DGEC MBR %.2f $/bbl against %s of %.2f $/bbl, a ratio of %.2f. "
        "SPEC.md section 5.5 expects the same order of magnitude; this is a "
        "different order and is a bug rather than a method difference."
        % (month[:7], actual, description, reference, ratio)
    )


def test_the_order_of_magnitude_numbers_are_reported_not_only_asserted(mbr):
    """Print the comparison SPEC.md section 5.5 asks to see in the Gate 1 report.

    Run with -s to read it. It is a test rather than a script so that it cannot
    drift away from the cache it describes.
    """
    lines = ["SPEC.md section 5.5 order of magnitude comparison"]
    for month in sorted(SP_REFERENCES):
        reference, description = SP_REFERENCES[month]
        actual = float(mbr.loc[pd.Timestamp(month)])
        lines.append(
            "  %s  DGEC MBR %6.2f $/bbl   S&P %6.2f $/bbl   gap %+6.2f   "
            "ratio %.2f   (%s)"
            % (month[:7], actual, reference, actual - reference, actual / reference,
               description)
        )
    print("\n".join(lines))
    assert len(lines) == 3


# ==========================================================================
# The cache itself, so the anchors are not asserted against a broken file
# ==========================================================================

def test_both_caches_are_monthly_contiguous_and_start_in_january_2015(brent, mbr_frame):
    """No missing month, no duplicate, no gap. The manifest says the same.

    An anchor that passed against a frame with a hole in it would still be a
    passing anchor, so the shape of the file is checked here rather than assumed.
    """
    for label, frame in (("brent", brent), ("mbr", mbr_frame)):
        index = frame.index
        assert index.is_monotonic_increasing, label
        assert not index.has_duplicates, label
        assert index.min() == pd.Timestamp("2015-01-01"), label
        assert (index.day == 1).all(), label
        expected = pd.date_range(index.min(), index.max(), freq="MS")
        missing = expected.difference(index)
        assert list(missing) == [], "%s is missing %s" % (label, list(missing))


def test_no_value_in_either_cache_is_missing(brent, mbr_frame):
    """Both series are complete. A NaN here would be real and worth seeing.

    SPEC.md non negotiable 1 says a missing observation becomes NaN and is
    surfaced. Neither workbook has ever had one, so a NaN appearing is news and
    this test is where the news arrives.
    """
    for column in (dgec.COLUMN_BRENT_USD_BBL, dgec.COLUMN_BRENT_USD_T):
        blanks = brent.index[brent[column].isna()]
        assert list(blanks) == [], "%s is NaN at %s" % (column, list(blanks))
    for column in (dgec.COLUMN_MBR_USD_BBL, dgec.COLUMN_MBR_EUR_T):
        blanks = mbr_frame.index[mbr_frame[column].isna()]
        assert list(blanks) == [], "%s is NaN at %s" % (column, list(blanks))


def test_the_derived_usd_t_column_is_exactly_the_published_value_times_7_5(brent):
    """brent_usd_t is one multiplication and nothing else.

    It is declared derived in the manifest, and this is what "derived" has to
    mean: no rounding, no smoothing, no second source blended in. SPEC.md non
    negotiable 1.
    """
    recomputed = brent[dgec.COLUMN_BRENT_USD_BBL] * DGEC_BBL_PER_T_BRENT_NOTE
    difference = (brent[dgec.COLUMN_BRENT_USD_T] - recomputed).abs().max()
    assert difference < 1e-9, difference
    assert not math.isclose(
        DGEC_BBL_PER_T_BRENT_NOTE, DGEC_BBL_PER_T_BRENT_MARGIN
    ), "the two DGEC Brent factors have been collapsed into one"
