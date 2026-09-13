"""Europe Brent spot, daily, straight from EIA. The redistributable cross check.

    series      eia_brent_daily
    cache       data/cache/eia_brent_daily.csv
    columns     date, brent_usd_bbl
    unit        USD per barrel
    source      US Energy Information Administration, series RBRTE
    url         https://www.eia.gov/dnav/pet/hist_xls/RBRTEd.xls
    page        https://www.eia.gov/dnav/pet/hist/RBRTEd.htm

Why this exists when crack.sources.fred already fetches Brent
--------------------------------------------------------------
FRED's DCOILBRENTEU is not FRED's series. It is this series, published by EIA
and redistributed by FRED. Recon 04 section 1.7 fetched both, joined them on the
date and measured a maximum absolute difference of 0.0 across all 9,973 shared
dates. They are the same numbers.

What differs is the licence. EIA's reuse statement is the only unambiguous grant
in this project, verbatim from https://www.eia.gov/about/copyrights_reuse.php:

    U.S. government publications are in the public domain and are not subject to
    copyright protection. You may use and/or distribute any of our data, files,
    databases, reports, graphs, charts, and other information products ...

FRED's legal page, on the other hand, prohibits "data mining, mirroring, robots,
scraping, or similar data-gathering or extraction methods except as expressly
allowed by the terms of use applicable to the FRED API", and a scheduled job that
commits fredgraph.csv into a public repository is arguably a mirror. Recon 04
section 1.8 records the tension and does not resolve it.

SPEC.md section 5.1 names FRED, so FRED stays the series the analysis reads. This
adapter exists so that the decision is reversible at the cost of one line rather
than a rewrite, and so that the Gate 1 report can show the two sources agreeing
rather than assert it. crack.sources.fred's module docstring says the same thing
from the other side.

Two differences in the file, and only two
------------------------------------------
1. IT IS A LEGACY .xls. Not .xlsx. openpyxl cannot open it and says so unhelpfully,
   so this module uses xlrd, which since version 2.0 reads .xls and nothing else.
   The dates are Excel serials and are converted with the workbook's own datemode
   rather than an assumed 1900 epoch.

2. EIA OMITS A HOLIDAY, FRED BLANKS IT. FRED emits one row for every business day
   and leaves the value empty on a holiday. EIA simply has no row for that day.
   So the two files carry the same 9,973 observations and a different number of
   lines, and comparing their row counts would be comparing two different things.
   The manifest's observations field is the comparable one, which is why base.py
   keeps it apart from file_rows.

NEVER PROBE eia.gov WITH HEAD. It answers HTTP 503 to a HEAD and HTTP 200 to a
GET of the same URL, recon 03 section 4 item 12. base.http_head refuses the host
outright rather than let the mistake be made twice. This module uses http_get and
reads what it needs off the real response.
"""

from __future__ import annotations

import pandas as pd

from ..config import source as registered_source
from .base import (
    Adapter,
    SourceError,
    SPEC_BOUNDS,
    http_get,
)

__all__ = [
    "SERIES",
    "COLUMN",
    "SOURCE_KEY",
    "XLS_URL",
    "PAGE_URL",
    "SHEET",
    "parse_xls",
    "fetch_xls",
    "compare_with",
    "EiaBrent",
    "SEED_SERIES",
    "SEED_FILENAME",
    "SEED_FIGURES",
    "seed_path",
    "load_refinery_fuel_seed",
    "gas_intensity_from_seed",
    "record_refinery_fuel_seed",
    "main",
]


#: Manifest and cache name, a key of crack.config.SOURCES.
SERIES = "eia_brent_daily"

#: Value column. The same name crack.sources.fred writes, on purpose: the two
#: files hold the same quantity and a cross check should not have to rename it.
COLUMN = "brent_usd_bbl"

#: EIA's own key for the series, printed in cell B2 of the data sheet. Checked
#: on every fetch, because the URL is the only other thing identifying the file
#: and a silently reused URL is how you end up charting WTI.
SOURCE_KEY = "RBRTE"

XLS_URL = "https://www.eia.gov/dnav/pet/hist_xls/RBRTEd.xls"
PAGE_URL = "https://www.eia.gov/dnav/pet/hist/RBRTEd.htm"

#: The sheet the numbers are on. The other sheet, "Contents", is a link page.
SHEET = "Data 1"

#: Row index, zero based, of the header inside SHEET, and of the first data row.
#: Recon 04 section 1.7 read the layout: row 0 is a back link, row 1 is the
#: source key, row 2 is the header, data starts at row 3. The header row is still
#: matched by its text below rather than trusted by its position.
HEADER_ROW = 2
FIRST_DATA_ROW = 3

#: 9,973 published prices as of 2026-09-11. The floors sit about 2 percent under.
MIN_ROWS = 9_700
MIN_PUBLISHED = 9_700

#: EIA's own series starts here and nothing exists before it.
SERIES_START = "1987-05-20"


_registered = registered_source(SERIES)
if _registered.machine_url != XLS_URL or _registered.page_url != PAGE_URL:
    raise RuntimeError(
        "crack.sources.eia builds %s and %s but crack.config.SOURCES registers "
        "%s and %s. The site would link a different file from the one the "
        "pipeline reads"
        % (XLS_URL, PAGE_URL, _registered.machine_url, _registered.page_url)
    )


# --------------------------------------------------------------------------
# Parsing, no network
# --------------------------------------------------------------------------

def parse_xls(payload) -> pd.DataFrame:
    """Parse the RBRTEd.xls workbook into the cache layout. No network.

    Args:
        payload: the response body as bytes, or a path to a saved copy.

    Returns:
        A frame with date and brent_usd_bbl, ascending by date. EIA emits no row
        for a day it published nothing, so every row here carries a price and the
        gap list is a list of weekdays with no row.

    Raises:
        SourceError: if xlrd is missing, if the workbook will not open, if the
            data sheet is absent, if the source key is not RBRTE, if the header
            does not name a date column and a dollars per barrel column, or if a
            cell is neither a number nor empty. Nothing is repaired quietly.
    """
    try:
        import xlrd
    except ImportError as exc:  # pragma: no cover, an environment problem
        raise SourceError(
            "eia %s: xlrd is not installed. RBRTEd.xls is a legacy .xls and "
            "openpyxl cannot read it" % SERIES
        ) from exc

    try:
        if isinstance(payload, (bytes, bytearray)):
            book = xlrd.open_workbook(file_contents=bytes(payload))
        else:
            book = xlrd.open_workbook(str(payload))
    except Exception as exc:  # noqa: BLE001, xlrd raises several unrelated types
        raise SourceError(
            "eia %s: the download did not open as an xls workbook, %s: %s. That "
            "is usually an HTML error page served with the wrong name"
            % (SERIES, type(exc).__name__, exc)
        ) from exc

    if SHEET not in book.sheet_names():
        raise SourceError(
            "eia %s: the workbook has no %r sheet, sheets were %s"
            % (SERIES, SHEET, ", ".join(book.sheet_names()))
        )
    sheet = book.sheet_by_name(SHEET)

    if sheet.nrows <= FIRST_DATA_ROW:
        raise SourceError(
            "eia %s: the %r sheet has %d row(s), too few to hold a series"
            % (SERIES, SHEET, sheet.nrows)
        )

    # The identity check. B2 carries EIA's own key for the series and a file
    # fetched from the wrong path would carry a different one.
    key = str(sheet.cell_value(1, 1)).strip()
    if key != SOURCE_KEY:
        raise SourceError(
            "eia %s: the workbook declares source key %r, expected %r. This is "
            "not the Europe Brent spot file" % (SERIES, key, SOURCE_KEY)
        )

    header = [str(sheet.cell_value(HEADER_ROW, c)).strip() for c in range(sheet.ncols)]
    lowered = [h.lower() for h in header]
    date_index = next((i for i, h in enumerate(lowered) if h == "date"), None)
    if date_index is None:
        raise SourceError(
            "eia %s: no column headed 'Date' on row %d, headers were %s"
            % (SERIES, HEADER_ROW + 1, ", ".join(repr(h) for h in header))
        )
    value_index = next(
        (
            i
            for i, h in enumerate(lowered)
            if i != date_index and "brent" in h and "dollars per barrel" in h
        ),
        None,
    )
    if value_index is None:
        raise SourceError(
            "eia %s: no column headed with Brent and 'Dollars per Barrel', "
            "headers were %s. The unit is part of the match on purpose, a "
            "column that quietly changed unit must not be read as this one"
            % (SERIES, ", ".join(repr(h) for h in header))
        )

    dates: list[pd.Timestamp] = []
    values: list[float] = []
    for row in range(FIRST_DATA_ROW, sheet.nrows):
        raw_date = sheet.cell_value(row, date_index)
        raw_value = sheet.cell_value(row, value_index)
        if raw_date == "" and raw_value == "":
            continue
        try:
            stamp = pd.Timestamp(
                xlrd.xldate.xldate_as_datetime(float(raw_date), book.datemode)
            ).normalize()
        except Exception as exc:  # noqa: BLE001, xlrd raises its own types here
            raise SourceError(
                "eia %s: row %d has %r in the date column, which is not an Excel "
                "date serial" % (SERIES, row + 1, raw_date)
            ) from exc
        if raw_value == "":
            # EIA omits a day it did not publish rather than blanking it, so an
            # empty cell here would be new behaviour. It becomes NaN, never zero,
            # and the row is kept so the change is visible in the file.
            values.append(float("nan"))
        else:
            try:
                values.append(float(raw_value))
            except (TypeError, ValueError) as exc:
                raise SourceError(
                    "eia %s: row %d has %r in the price column, which is not a "
                    "number" % (SERIES, row + 1, raw_value)
                ) from exc
        dates.append(stamp)

    if not dates:
        raise SourceError("eia %s: the data sheet carried no rows" % SERIES)

    frame = pd.DataFrame({"date": dates, COLUMN: values})
    duplicates = frame.loc[frame["date"].duplicated(), "date"]
    if len(duplicates):
        raise SourceError(
            "eia %s: duplicate date(s) in the workbook, first is %s"
            % (SERIES, duplicates.iloc[0].strftime("%Y-%m-%d"))
        )
    return frame.sort_values("date", kind="mergesort").reset_index(drop=True)


def compare_with(eia: pd.DataFrame, other: pd.DataFrame) -> dict:
    """Join this series against another Brent frame on the date and measure.

    Both frames must carry a date column and a brent_usd_bbl column. The join is
    on the date and nothing else, because the two files do not have the same
    number of lines: FRED blanks a holiday and EIA omits it.

    Returns:
        shared          dates where both carry a price
        max_abs_diff    the largest absolute difference, NaN when nothing is
                        shared
        worst_date      where that difference is, or None
        eia_only        dates only EIA carries a price for
        other_only      dates only the other file carries a price for
    """
    left = eia.loc[:, ["date", COLUMN]].rename(columns={COLUMN: "eia"}).copy()
    right = other.loc[:, ["date", COLUMN]].rename(columns={COLUMN: "other"}).copy()
    left["date"] = pd.to_datetime(left["date"], errors="coerce")
    right["date"] = pd.to_datetime(right["date"], errors="coerce")

    merged = left.merge(right, on="date", how="outer")
    both = merged["eia"].notna() & merged["other"].notna()
    shared = merged.loc[both].copy()
    if shared.empty:
        return {
            "shared": 0,
            "max_abs_diff": float("nan"),
            "worst_date": None,
            "eia_only": int((merged["eia"].notna() & merged["other"].isna()).sum()),
            "other_only": int((merged["eia"].isna() & merged["other"].notna()).sum()),
        }
    shared["diff"] = (shared["eia"] - shared["other"]).abs()
    worst = shared.loc[shared["diff"].idxmax()]
    return {
        "shared": int(len(shared)),
        "max_abs_diff": float(shared["diff"].max()),
        "worst_date": worst["date"].strftime("%Y-%m-%d"),
        "eia_only": int((merged["eia"].notna() & merged["other"].isna()).sum()),
        "other_only": int((merged["eia"].isna() & merged["other"].notna()).sum()),
    }


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

def fetch_xls(*, delay: float = 1.0) -> pd.DataFrame:
    """Fetch and parse RBRTEd.xls. Network call.

    http_get, never http_head. See the module docstring.
    """
    response = http_get(
        XLS_URL,
        headers={"Accept": "application/vnd.ms-excel,*/*;q=0.8"},
        delay=delay,
        retries=3,
        timeout=60,
    )
    body = response.content
    if not body:
        raise SourceError("eia %s: the download was empty" % SERIES)
    return parse_xls(body)


# --------------------------------------------------------------------------
# The refinery fuel seed, SPEC.md sections 5.1 and 8
# --------------------------------------------------------------------------
#
# FOUR NUMBERS, TYPED ONCE, EACH WITH ITS TABLE. SPEC.md section 5.1 asks for a
# "Seed JSON with source URLs" here rather than an adapter, and recon 03 section
# 3.1 established why that is right rather than lazy: tables 10a and 10b of the
# Refinery Capacity Report exist ONLY as a PDF. The workbook that accompanies
# the report, refcap24.xlsx, carries exactly one sheet and it is the per
# refinery capacity file. There is nothing to parse.
#
# What is NOT typed is the intensity itself. SPEC.md section 4.4 says "Gas
# intensity is derived, not typed", so gas_intensity_from_seed recomputes it
# from the four figures every time it is asked, and tests/test_seeds.py asserts
# that the result reproduces crack.config.GAS_INTENSITY_MMBTU_PER_BBL. If
# somebody edits the constant without editing the seed, or edits the seed
# without editing the constant, that test fails, which is the whole point of
# SPEC.md section 9's intensity row.

SEED_SERIES = "eia_refinery_fuel_2023"

SEED_FILENAME = "%s.json" % SEED_SERIES

#: The keys the derivation needs, and what each one is. A seed missing one of
#: these cannot produce an intensity, and a seed that carries a figure with no
#: source_url cannot be checked by a reader, which SPEC.md section 5.1 requires
#: of every entry.
SEED_FIGURES = (
    "refinery_fuel_gas_mmcf",
    "hydrogen_feedstock_gas_mmcf",
    "gas_heat_content_btu_per_cf",
    "crude_inputs_thousand_bbl",
)


def seed_path(root=None):
    """Path of the committed seed file."""
    from pathlib import Path

    from .base import SEED

    return (Path(root) if root is not None else SEED) / SEED_FILENAME


def load_refinery_fuel_seed(root=None) -> dict:
    """Read and check data/seed/eia_refinery_fuel_2023.json.

    Raises:
        SourceError: when the file is absent, when a figure the derivation needs
            is missing, when a figure carries no value, or when a figure carries
            no source_url. The last of those is not pedantry: a seeded number
            with no citation is exactly the "plausible fabrication" SPEC.md
            non negotiable 8 is about, and it would be indistinguishable from a
            real one a year from now.
    """
    import json

    path = seed_path(root)
    if not path.exists():
        raise SourceError(
            "eia: %s is not on disk. SPEC.md section 5.1 seeds the gas intensity "
            "inputs by hand because tables 10a and 10b exist only as a PDF, and "
            "crack.config.GAS_INTENSITY_MMBTU_PER_BBL is derived from them" % path
        )
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    figures = {entry.get("key"): entry for entry in payload.get("figures", [])}
    problems = []
    for key in SEED_FIGURES:
        figure = figures.get(key)
        if figure is None:
            problems.append("no figure %r" % key)
            continue
        if not isinstance(figure.get("value"), (int, float)):
            problems.append("figure %r carries no numeric value" % key)
        if not figure.get("source_url"):
            problems.append("figure %r carries no source_url" % key)
        if not figure.get("unit"):
            problems.append("figure %r carries no unit" % key)
    if problems:
        raise SourceError(
            "eia: %s is not usable: %s. Every seeded number states where it came "
            "from, or a reader cannot tell it from an invention"
            % (path, "; ".join(problems))
        )
    payload["_figures"] = figures
    return payload


def gas_intensity_from_seed(seed: dict) -> float:
    """MMBtu of purchased natural gas per barrel of crude input. SPEC.md 4.4.

    Derived here from the seed's own figures, at full precision, in the order
    SPEC.md section 4.4 sets out:

        (fuel gas + hydrogen feedstock) MMcf
          x 1e6 cubic feet per MMcf
          x heat content, Btu per cubic foot
          / 1e6 Btu per MMBtu
          / (crude inputs, thousand barrels x 1e3)

    The hydrogen feedstock gas is INCLUDED, because a European refiner buys that
    gas too. Excluding it gives 0.1815 instead of 0.2122, a 15 percent difference,
    and the seed carries that as a labelled sensitivity.
    """
    figures = seed.get("_figures") or {entry["key"]: entry for entry in seed["figures"]}
    fuel = float(figures["refinery_fuel_gas_mmcf"]["value"])
    hydrogen = float(figures["hydrogen_feedstock_gas_mmcf"]["value"])
    heat = float(figures["gas_heat_content_btu_per_cf"]["value"])
    crude = float(figures["crude_inputs_thousand_bbl"]["value"])
    if crude <= 0:
        raise SourceError("eia: the seed's crude input denominator is %r" % crude)
    mmbtu = (fuel + hydrogen) * 1e6 * heat / 1e6
    return mmbtu / (crude * 1e3)


def record_refinery_fuel_seed(root=None) -> dict:
    """Put the seed into data/manifest.json. Returns the entry.

    It is a manifest entry rather than an Adapter run because an Adapter writes
    a CSV and this is JSON, and because nothing fetched it. It therefore carries
    machine_fetched false and a checked_at rather than a fetched_at, which is
    the rule crack.sources.base.manifest_upsert enforces: a file nothing fetched
    has no fetch time.
    """
    from .base import manifest_upsert, utc_now_iso

    seed = load_refinery_fuel_seed(root)
    intensity = gas_intensity_from_seed(seed)
    figures = seed["_figures"]

    entry = {
        "series": SEED_SERIES,
        "source": seed.get("publisher", "US Energy Information Administration"),
        "url": None,
        "page_url": figures["refinery_fuel_gas_mmcf"].get("page_url"),
        "machine_fetched": False,
        "fetched_at": None,
        "checked_at": utc_now_iso(),
        "rows": len(SEED_FIGURES),
        "observations": len(SEED_FIGURES),
        "file_rows": len(seed.get("figures", [])),
        "first_date": "2023-01-01",
        "last_date": "2023-12-31",
        "frequency": "annual",
        "gaps": [],
        "provisional_from": None,
        "vintage": seed["_figures"]["refinery_fuel_gas_mmcf"].get("publication"),
        "method": "seed",
        "committable": True,
        "licence_note": seed.get("licence_note", ""),
        "status": "ok",
        "file": "data/seed/%s" % SEED_FILENAME,
        "unit": "million cubic feet, Btu per cubic foot, thousand barrels",
        "observation_column": None,
        "figures": {
            key: {
                "value": figures[key]["value"],
                "unit": figures[key]["unit"],
                "label_as_printed": figures[key].get("label_as_printed"),
                "source_url": figures[key]["source_url"],
            }
            for key in SEED_FIGURES
        },
        "derived_gas_intensity_mmbtu_per_bbl": intensity,
        "note": (
            "Four figures for the United States in 2023, typed by hand from the "
            "tables named against each one, because tables 10a and 10b of the EIA "
            "Refinery Capacity Report exist only as a PDF: the workbook that "
            "accompanies the report carries the per refinery capacity sheet and "
            "nothing else. The gas intensity is DERIVED from them, never typed, "
            "and comes to %.6f MMBtu per barrel against the SPEC.md section 4.4 "
            "band of 0.12 to 0.30. It is a US figure and therefore an upper end "
            "default for Europe, where refiners burn proportionally more of their "
            "own still gas. %s"
            % (intensity, seed.get("acknowledgment", ""))
        ),
    }
    manifest_upsert(entry)
    return entry


# --------------------------------------------------------------------------
# The adapter
# --------------------------------------------------------------------------

class EiaBrent(Adapter):
    """EIA Europe Brent spot, one row per date EIA publishes a price."""

    name = SERIES
    source = "US Energy Information Administration, series RBRTE"
    url = XLS_URL
    page_url = PAGE_URL
    unit = "USD per barrel"
    frequency = "daily"
    method = "published"
    committable = True
    licence_note = _registered.licence_note
    required_cols = ("date", COLUMN)
    bounds = {COLUMN: SPEC_BOUNDS["brent_usd_bbl"]}
    date_col = "date"
    min_rows = MIN_ROWS
    min_observations = {COLUMN: MIN_PUBLISHED}
    observation_column = COLUMN

    def __init__(self, *, delay: float = 1.0):
        """
        Args:
            delay: polite pause before the request, seconds.
        """
        self.delay = float(delay)

    def fetch(self) -> pd.DataFrame:
        frame = fetch_xls(delay=self.delay)

        first = frame["date"].min()
        if first < pd.Timestamp(SERIES_START):
            raise SourceError(
                "eia %s: the workbook starts %s, earlier than the documented "
                "series start of %s. That is a source change, not a longer "
                "history" % (SERIES, first.strftime("%Y-%m-%d"), SERIES_START)
            )

        published = int(frame[COLUMN].notna().sum())
        self.note = (
            "Europe Brent spot price FOB, daily, US dollars per barrel, EIA "
            "series RBRTE, read from the published RBRTEd.xls workbook. %d of %d "
            "rows carry a price. EIA omits a day it did not publish rather than "
            "emitting a blank row, so the weekdays in the gap list are holidays "
            "on a UK and European calendar and not lost data. This is the same "
            "series FRED redistributes as DCOILBRENTEU, and recon 04 section 1.7 "
            "measured a maximum absolute difference of 0.0 between the two across "
            "all 9,973 shared dates. It is fetched as the redistributable cross "
            "check on fred_brent_daily, SPEC.md section 5.1 names FRED as the "
            "source the analysis reads, and this one carries EIA's explicit "
            "public domain grant. Acknowledge EIA with the publication date."
            % (published, len(frame))
        )
        return frame


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> int:
    """Run the adapter and print an ASCII report. Returns an exit code."""
    adapter = EiaBrent()
    try:
        entry = adapter.run()
    except Exception as exc:  # noqa: BLE001, the CLI reports and exits non zero
        print("%s FAILED: %s: %s" % (SERIES, type(exc).__name__, exc))
        return 1
    print(
        "%-20s rows=%-6d file_rows=%-6d %s to %s gaps=%d status=%s"
        % (
            entry["series"],
            entry["rows"],
            entry["file_rows"],
            entry["first_date"],
            entry["last_date"],
            len(entry["gaps"]),
            entry["status"],
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
