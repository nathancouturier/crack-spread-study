"""Refinery capacity by country, annual, from the Energy Institute Statistical Review.

    series      ei_refinery_capacity_annual
    cache       data/private/ei_refinery_capacity_annual.csv   NOT data/cache
    unit        thousand barrels daily, capacity at year end
    countries   BE, DE, FR, NL, GB
    source      Energy Institute Statistical Review of World Energy, 2026 edition
    page        https://www.energyinst.org/statistical-review/resources-and-data-downloads

This is the denominator of SPEC.md section 6.1's utilisation. The numerator is
crack.sources.jodi's refinery crude intake. The two work together: recon 03
section 2.3 combined them and got 0.869 in 2015 falling to 0.724 in 2020 and
recovering to 0.831 in 2025, which is the level and the shape a refining analyst
would expect.

THIS CACHE MAY NOT BE COMMITTED, AND THAT IS A GATE 1 DECISION, NOT A BUG
--------------------------------------------------------------------------
The Review says, verbatim:

    Publishers are welcome to quote from this Review provided that they
    attribute the source to Energy Institute Statistical Review of World Energy
    2026. However, for extensive reproduction of tables and/or charts,
    permission must first be obtained from: EI Statistical Review of World
    Energy, 61 New Cavendish Street, London W1G 7AR,
    statisticalreview@energyinst.org

    The redistribution or reproduction of data whose source is S&P Global Energy
    or S&P Global Inc, is strictly prohibited without its prior authorisation.

and the capacity sheet carries its own footnote, on the sheet, below the data:

    Source: Includes data from ICIS and S&P Global Energy

So two separate prohibitions land on the same table. Publishing 61 years for
five countries is extensive reproduction of a table and needs written
permission, and the sheet does not say which rows came from which supplier, so
there is no way to strip the S&P part out and keep the rest. SPEC.md
non negotiable 6 sends anything that cannot be redistributed to data/private/,
which is what committable = False does here, and SPEC.md section 5.4 wants every
cache committed so the site builds with no network. Those two cannot both hold
for this series. The owner chooses at Gate 1 between:

    1. ASK EI. One email to statisticalreview@energyinst.org for permission to
       publish five country rows in a non commercial portfolio repository with
       attribution. Clean, and it takes days.
    2. PUBLISH ONLY THE DERIVED RATIO, utilisation = intake / capacity, keeping
       the capacity itself private.
    3. TAKE SPEC.md SECTION 6.1'S OWN FALLBACK, "If the capacity table is
       unusable, use intake with a trend and closure dummies instead, and say
       so". It was written for a usability failure and it fits a licence failure
       just as well.

This module keeps all three open. It parses and stores the table privately, it
provides utilisation() and capacity_monthly() so option 2 needs no new parsing,
and it touches nothing the fallback in option 3 would use. It does not choose.

ONE THING THE RECON DID NOT SAY, AND IT BEARS ON OPTION 2
-----------------------------------------------------------
Option 2 does not actually withhold the table. utilisation = intake / capacity,
and intake is published in data/cache/jodi_nwe_refinery_intake_monthly.csv under
SPEC.md section 5.4. Anyone who divides the published intake by the published
utilisation recovers EI's capacity exactly, to the last decimal, for every month
the ratio is shown. Rounding the published ratio to three decimals still pins a
capacity of this size to about plus or minus four thousand barrels a day in six
million, which is not meaningful protection either. If option 2 is chosen
because it is thought to satisfy the licence, that
reasoning should be checked with EI rather than assumed, and the honest version
of option 2 publishes the regression outputs and the chart and not a full
precision monthly ratio. Flagged here because the decision is the owner's and
the arithmetic is not obvious from the licence text.

Layout facts that a parser gets wrong once
-------------------------------------------
1. THE HEADER ROW PRINTS 2025 THREE TIMES, in the last capacity column and again
   over a year on year growth rate and a share of world. A parser that took every
   integer header would read a growth rate of minus 0.078 as a capacity of minus
   0.078 thousand barrels a day. The capacity block is bounded by LABEL: the row
   above the header carries "Growth rate per annum" and "Share" over the columns
   that are not capacity, and everything from the first of those markers
   rightwards is dropped. Recon 03 section 2.2.

2. CELLS ARE A MIX OF str AND float. Many of the 1960s and 1970s values arrive as
   strings of digits. Others carry floating point dust, a value that reads as a
   round thousand plus 2e-13, and several recent country years are not round at
   all but carry thirteen decimal places. Nothing is rounded here and no test
   asserts an integer. The values themselves are not quoted in this file: it is
   the file that argues the table may not be republished.

3. THE COUNTRY LABEL IS "United Kingdom", not UK and not GB. The five rows are
   found by their printed labels, and a missing or duplicated label is a stop.

4. THERE IS NO 2026 CAPACITY ANYWHERE IN THE WORKBOOK. The 2026 edition stops at
   2025, while the study's live months are 2026. The manifest carries latest_year
   so the site can say which year the denominator is from rather than implying
   currency, and this module refuses to extend the series by a single year. A
   2026 utilisation computed against a 2025 capacity rests on an assumption that
   no source has published, and SPEC.md section 2 rule 1 means the assumption is
   labelled where it is made, which is in the analysis, not here.

5. THE EDITION IS READ OUT OF THE FILE, not out of the URL. The asset id in the
   download path is edition specific and will move with the 2027 edition, and EI
   revises history between editions on its own admission. The vintage comes from
   the Contents sheet's own "2026 Energy Institute Statistical Review of World
   Energy" string.

ENERGYINST.ORG NOW ANSWERS A BOT CHALLENGE, AND THIS ADAPTER WILL NOT SOLVE IT
-------------------------------------------------------------------------------
Recon 03 fetched the workbook on 2026-09-11 from this machine, HTTP 200,
3,973,716 bytes, off a plain href with no registration and no click through.
Measured again from the same machine on 2026-09-13, with four different header
sets and on the landing page as well as the file:

    HTTP 403, Server: cloudflare, Cf-Mitigated: challenge,
    body "Just a moment...", 5,976 bytes of Cloudflare interstitial

That is an interactive challenge, not a licence refusal and not a rate limit,
and it covers the whole site rather than one file. Working around it is out of
bounds, so this adapter does exactly two things: it parses a copy that is
already stored, and when there is none it raises and tells the operator to
download the file by hand into data/private/ei/. A human downloading a public
workbook from a public page is the normal use of that page. A script defeating a
challenge is not, and a pipeline whose whole job is to tell the truth about its
sources cannot start by lying about being a browser.

The consequence for SPEC.md section 8's weekly refresh job is that this series
cannot be part of it. It is annual, the edition changes once a year, and the
manifest records when the bytes were obtained rather than when this program last
ran, so a stale edition is visible.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from ..config import BOUNDS_INTAKE_KB_D
from ..config import source as registered_source
from .base import PRIVATE, Adapter, SourceError, http_get, utc_now_iso

__all__ = [
    "SERIES",
    "SHEET",
    "CONTENTS_SHEET",
    "COUNTRY_ROWS",
    "COUNTRIES",
    "AGGREGATE",
    "GROWTH_MARKERS",
    "MISSING_TOKENS",
    "UNITS_LABEL",
    "FIRST_YEAR",
    "WORKBOOK_URL",
    "PAGE_URL",
    "column_name",
    "read_edition",
    "parse_capacity",
    "capacity_monthly",
    "utilisation",
    "EiRefineryCapacity",
    "main",
]


SERIES = "ei_refinery_capacity_annual"

#: The sheet, by name. There are 97 sheets in the workbook.
SHEET = "Oil refinery - capacity"

#: Where the edition string is printed.
CONTENTS_SHEET = "Contents"

#: The five countries this study needs, as the SHEET prints them, mapped to the
#: ISO codes crack.sources.jodi uses. THE LABEL IS "United Kingdom" AND THE CODE
#: IS GB: EI spells it out, JODI codes it, and SPEC.md calls it UK in prose.
COUNTRY_ROWS: Mapping[str, str] = {
    "Belgium": "BE",
    "Germany": "DE",
    "France": "FR",
    "Netherlands": "NL",
    "United Kingdom": "GB",
}

#: In the column order the caches use, which is crack.sources.jodi's order so the
#: two files line up column for column when they are read side by side.
COUNTRIES: tuple[str, ...] = ("BE", "DE", "FR", "NL", "GB")

AGGREGATE = "nwe5"

#: The labels printed ABOVE the columns that are not capacity. Everything from
#: the first of these rightwards is dropped, which is how the three columns
#: headed 2025 are told apart without counting to 61.
GROWTH_MARKERS: tuple[str, ...] = ("growth rate per annum", "share")

#: The sheet's own footnotes for a cell with no number in it. Both become NaN.
#: "^ Less than 0.5" is a suppressed small value and not a zero, and turning it
#: into one would invent a capacity of nothing where the source said it did not
#: want to print a figure.
MISSING_TOKENS: frozenset[str] = frozenset(
    # The second token is the black diamond the sheet uses for "less than 0.05 percent",
    # written as an escape so this file stays ASCII.
    {"", "-", "n/a", "na", "^", "\u2666"}
)

#: The units cell that opens the header row, checked before anything is read.
UNITS_LABEL = "thousand barrels daily"

#: The first year the table covers. A workbook that starts later has changed
#: shape and the history would silently shorten.
FIRST_YEAR = 1965

PAGE_URL = "https://www.energyinst.org/statistical-review/resources-and-data-downloads"

WORKBOOK_URL = registered_source(SERIES).machine_url

#: Where the workbook itself is kept, so a rebuild does not fetch 4 MB again and
#: so the parse can be repeated offline. Gitignored with the rest of
#: data/private. NEVER data/cache: the bytes are the Review.
WORKBOOK_DIRNAME = "ei"
WORKBOOK_FILENAME = "EI-Stats-Review-ALL-data.xlsx"

#: 1965 to 2025 is 61 observations. The floor sits under that with room for a
#: restated year, and high enough that a truncated parse cannot replace a good
#: cache.
MIN_OBSERVATIONS = 55

_EDITION = re.compile(r"(?P<year>(19|20)\d{2})\s+Energy Institute Statistical Review")


def column_name(area: str) -> str:
    """The cache column for one country's capacity."""
    return "%s_capacity_kb_d" % area.lower()


# --------------------------------------------------------------------------
# Reading the workbook
# --------------------------------------------------------------------------

def _open(workbook):
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover, an environment problem
        raise SourceError(
            "ei: openpyxl is not installed and the Statistical Review is an xlsx"
        ) from exc
    handle = io.BytesIO(bytes(workbook)) if isinstance(workbook, (bytes, bytearray)) else workbook
    try:
        return openpyxl.load_workbook(handle, data_only=True, read_only=True)
    except Exception as exc:  # noqa: BLE001, openpyxl raises several types
        raise SourceError(
            "ei: could not open the Statistical Review workbook, %s: %s"
            % (type(exc).__name__, exc)
        ) from exc


def _rows(book, sheet: str) -> list[tuple]:
    if sheet not in book.sheetnames:
        raise SourceError(
            "ei: the workbook has no sheet named %r. It carries %d sheets and the "
            "capacity table is the one SPEC.md section 5.1 asks for, so a renamed "
            "sheet is a stop rather than a search" % (sheet, len(book.sheetnames))
        )
    return list(book[sheet].iter_rows(values_only=True))


def read_edition(workbook) -> str:
    """The edition string, read out of the Contents sheet. Never out of the URL.

    Returns something like "2026 Energy Institute Statistical Review of World
    Energy". The asset id in the download URL is edition specific and will change
    with the next edition, and EI revises history between editions, so the
    vintage has to come from inside the file.
    """
    book = _open(workbook)
    for row in _rows(book, CONTENTS_SHEET):
        for cell in row:
            if isinstance(cell, str) and _EDITION.search(cell):
                return " ".join(cell.split())
    raise SourceError(
        "ei: the Contents sheet does not print an edition line matching %r, so "
        "there is nothing to record as the vintage and a revision between "
        "editions would be invisible" % _EDITION.pattern
    )


def _to_float(value, *, where: str) -> float:
    """One capacity cell. A footnote token becomes NaN, anything odd raises."""
    if value is None:
        return float("nan")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip()
    if text.lower() in MISSING_TOKENS:
        return float("nan")
    # Many 1960s and 1970s cells arrive as strings of digits.
    cleaned = text.replace(",", "").replace("\u00a0", "")  # a thousands comma, a non breaking space
    try:
        return float(cleaned)
    except ValueError as exc:
        raise SourceError(
            "ei %s: cannot read %r as a capacity. The sheet's own footnotes for a "
            "cell with no number are %s, and a token outside that list is added "
            "deliberately rather than allowed to become a number"
            % (where, value, ", ".join(sorted(t for t in MISSING_TOKENS if t)))
        ) from exc


def parse_capacity(workbook) -> pd.DataFrame:
    """Read the five country rows of the capacity sheet, by label.

    Args:
        workbook: bytes, a path, or anything openpyxl will open.

    Returns:
        One row per year, ascending, with columns

            date                    31 December of the year. The sheet's own
                                    footnote says "Atmospheric distillation
                                    capacity at YEAR END on a calendar-day
                                    basis", so the observation belongs at the end
                                    of its year and not at the start. Anything
                                    that interpolates it monthly has to know that.
            be_capacity_kb_d ...    one per country, thousand barrels daily
            nwe5_capacity_kb_d      the five country sum, NaN unless all five
                                    printed a number

    Raises:
        SourceError: on a missing sheet, a header row that cannot be found, a
            units cell that no longer says thousand barrels daily, a country
            label that has gone or appears twice, a year that repeats inside the
            capacity block, or a first year later than 1965.
    """
    book = _open(workbook)
    rows = _rows(book, SHEET)

    header_index = None
    for index, row in enumerate(rows):
        first = row[0] if row else None
        if isinstance(first, str) and first.strip().lower().startswith(UNITS_LABEL):
            header_index = index
            break
    if header_index is None:
        raise SourceError(
            "ei: no header row on sheet %r opening with %r. The years are read "
            "from that row, so there is nothing to read them from"
            % (SHEET, UNITS_LABEL)
        )

    header = rows[header_index]
    above = rows[header_index - 1] if header_index else ()

    # Where the capacity block ends. The marker row is the authority, not a
    # column count: "Growth rate per annum" sits over the year on year change
    # and "Share" over the share of world, and both of those columns are headed
    # with a year that is already in the block.
    stop = len(header)
    for position, cell in enumerate(above):
        if isinstance(cell, str) and cell.strip().lower() in GROWTH_MARKERS:
            stop = min(stop, position)
    if stop <= 1:
        raise SourceError(
            "ei: the row above the header marks column %d as %r, which would "
            "leave no capacity columns at all" % (stop, above[stop] if above else None)
        )

    years: dict[int, int] = {}
    for position in range(1, stop):
        cell = header[position]
        if isinstance(cell, bool) or not isinstance(cell, (int, float)):
            continue
        year = int(cell)
        if float(cell) != year:
            continue
        if year in years:
            raise SourceError(
                "ei: year %d is headed twice inside the capacity block, at "
                "columns %d and %d. The block is bounded by the %s marker above "
                "the header, so a repeat inside it means the layout moved"
                % (year, years[year], position, " or ".join(GROWTH_MARKERS))
            )
        years[year] = position
    if not years:
        raise SourceError("ei: the header row carries no year columns at all")
    first_year = min(years)
    if first_year > FIRST_YEAR:
        raise SourceError(
            "ei: the capacity table now starts at %d, not %d. The history would "
            "silently shorten" % (first_year, FIRST_YEAR)
        )

    found: dict[str, int] = {}
    for index, row in enumerate(rows[header_index + 1 :], start=header_index + 1):
        label = row[0]
        if not isinstance(label, str):
            continue
        label = label.strip()
        if label not in COUNTRY_ROWS:
            continue
        if label in found:
            raise SourceError(
                "ei: the sheet prints %r twice, at rows %d and %d. Which one is "
                "the country is a guess" % (label, found[label], index)
            )
        found[label] = index
    missing = [label for label in COUNTRY_ROWS if label not in found]
    if missing:
        raise SourceError(
            "ei: the capacity sheet has no row labelled %s. SPEC.md section 5.1 "
            "asks Gate 1 to confirm the table covers all five countries, and it "
            "no longer does" % ", ".join(repr(m) for m in missing)
        )

    ordered = sorted(years)
    frame = pd.DataFrame(
        {"date": [pd.Timestamp(year=year, month=12, day=31) for year in ordered]}
    )
    for label, code in COUNTRY_ROWS.items():
        row = rows[found[label]]
        values = []
        for year in ordered:
            position = years[year]
            cell = row[position] if position < len(row) else None
            values.append(_to_float(cell, where="%s %d" % (label, year)))
        frame[column_name(code)] = values

    columns = [column_name(code) for code in COUNTRIES]
    # NaN unless all five printed a number. A four country denominator would
    # inflate utilisation by up to a fifth with nothing on the page to show it.
    frame[column_name(AGGREGATE)] = frame[columns].sum(axis=1, skipna=False)
    return frame


# --------------------------------------------------------------------------
# Derived, for whichever Gate 1 option the owner takes
# --------------------------------------------------------------------------

def capacity_monthly(
    capacity: pd.DataFrame, *, column: str | None = None, how: str = "step"
) -> pd.DataFrame:
    """Spread the annual capacity onto months, without extending it by a year.

    SPEC.md section 6.1 says "Energy Institute, interpolated monthly, closures as
    steps", which names two different things, so both are offered and the caller
    says which it took:

        how="step"    each month carries the capacity of the year end it falls
                      in, so a closure lands as a step. This is the literal
                      reading of the sheet, whose figure is a year end stock.
        how="linear"  straight line between consecutive year ends, so a closure
                      is spread across the year it happened in. Smoother, and
                      wrong about the month a refinery shut.

    NOTHING IS EXTENDED PAST THE LAST YEAR THE SOURCE PUBLISHED. The 2026 edition
    stops at 2025 and the study's live months are 2026, so the months after the
    last year end come back NaN rather than carrying 2025 forward. Holding the
    last value is a defensible modelling assumption and it is not a published
    figure, so it belongs in the analysis where it can be labelled, not in a
    function that looks like it read something.

    Returns a frame of date and the chosen column, spanning the months from the
    first published year end to the last. Months outside that span are absent
    rather than carried, which is what utilisation() turns into NaN.
    """
    if how not in ("step", "linear"):
        raise ValueError("ei: how must be 'step' or 'linear', got %r" % (how,))
    name = column or column_name(AGGREGATE)
    if name not in capacity.columns:
        raise SourceError("ei: no column %r in the capacity frame" % name)

    dates = pd.to_datetime(capacity["date"])
    span = pd.date_range(
        dates.min().to_period("M").to_timestamp(),
        dates.max().to_period("M").to_timestamp(),
        freq="MS",
    )
    annual = pd.Series(capacity[name].to_numpy(), index=dates.dt.to_period("M"))

    out = pd.DataFrame({"date": span})
    if how == "step":
        by_year = {period.year: value for period, value in annual.items()}
        out[name] = [float(by_year.get(when.year, np.nan)) for when in span]
    else:
        joined = pd.Series(np.nan, index=span.to_period("M"))
        for period, value in annual.items():
            joined.loc[period] = value
        out[name] = joined.interpolate(method="linear", limit_area="inside").to_numpy()
    return out


def utilisation(
    intake: pd.DataFrame,
    capacity: pd.DataFrame,
    *,
    intake_column: str = "nwe5_refinobs_crudeoil_kbd",
    capacity_column: str | None = None,
    how: str = "step",
) -> pd.DataFrame:
    """Refinery crude intake over capacity, monthly. The SPEC.md 6.1 denominator.

    This is option 2 of the three in the module docstring, prepared and not
    taken. Read the warning there before publishing the output: the intake is
    committed in data/cache, so a published full precision ratio hands back EI's
    capacity by division.

    A month with no published capacity, which is every month after the last year
    the Review covers, comes back NaN. SPEC.md section 2 rule 1.
    """
    name = capacity_column or column_name(AGGREGATE)
    monthly = capacity_monthly(capacity, column=name, how=how)
    if intake_column not in intake.columns:
        raise SourceError("ei: no column %r in the intake frame" % intake_column)

    left = intake[["date", intake_column]].copy()
    left["date"] = pd.to_datetime(left["date"]).dt.to_period("M").dt.to_timestamp()
    monthly = monthly.copy()
    monthly["date"] = pd.to_datetime(monthly["date"]).dt.to_period("M").dt.to_timestamp()

    merged = left.merge(monthly, on="date", how="left")
    merged["utilisation"] = merged[intake_column] / merged[name]
    merged["capacity_is_published"] = merged[name].notna()
    return merged[
        ["date", intake_column, name, "utilisation", "capacity_is_published"]
    ]


# --------------------------------------------------------------------------
# The adapter
# --------------------------------------------------------------------------

class EiRefineryCapacity(Adapter):
    """The capacity table, parsed into data/private. Never into data/cache.

    The workbook itself is kept beside the parsed cache so a rebuild needs no
    network, with a sha256 and the fetch time in its own small index, because EI
    revises history between editions without versioning the URL.
    """

    name = SERIES
    source = "Energy Institute Statistical Review of World Energy"
    url = WORKBOOK_URL
    page_url = PAGE_URL
    unit = "thousand barrels daily, capacity at year end"
    frequency = "annual"
    method = "published"
    #: SPEC.md non negotiable 6. See the module docstring for the two clauses.
    committable = False
    date_col = "date"
    min_rows = MIN_OBSERVATIONS
    observation_column = column_name(AGGREGATE)
    required_cols = tuple(
        ["date"] + [column_name(code) for code in COUNTRIES] + [column_name(AGGREGATE)]
    )
    bounds = {
        column_name(code): BOUNDS_INTAKE_KB_D for code in list(COUNTRIES) + [AGGREGATE]
    }
    min_observations = {
        column_name(code): MIN_OBSERVATIONS for code in list(COUNTRIES) + [AGGREGATE]
    }

    def __init__(self, *, refetch: bool = False, delay: float = 1.0, root: Path | None = None) -> None:
        """
        Args:
            refetch: fetch the workbook even when a copy is already stored.
                The default reuses the stored copy, because the file is 4 MB, it
                changes once a year, and a weekly job that pulled it every time
                would be discourteous for nothing.
            delay: polite pause before the request.
            root: where the workbook is stored. Defaults to data/private/ei.
        """
        self.refetch = bool(refetch)
        self.delay = float(delay)
        self._root = root
        self.licence_note = registered_source(SERIES).licence_note
        self.latest_year: int | None = None
        self.fetched = False

    # -- the stored workbook ------------------------------------------------

    @property
    def root(self) -> Path:
        return Path(self._root) if self._root is not None else PRIVATE / WORKBOOK_DIRNAME

    @property
    def workbook_path(self) -> Path:
        return self.root / WORKBOOK_FILENAME

    @property
    def index_path(self) -> Path:
        return self.root / "index.json"

    def adopt_workbook(self, path: Path | str, *, obtained_at: str, note: str) -> dict:
        """Take a copy of the workbook that was obtained outside this program.

        energyinst.org is behind a Cloudflare challenge as of 2026-09-13, so the
        only lawful way to get the file today is for a person to download it from
        the page the way a person does. This records that honestly: where the
        bytes came from, when they were obtained, in whose words, and a sha256 of
        exactly what was stored. It never claims this adapter fetched them.

        Args:
            path: the local copy.
            obtained_at: when it was obtained, ISO. NOT when this ran.
            note: how it was obtained, in a sentence a reader can check.
        """
        source = Path(path)
        body = source.read_bytes()
        if not body.startswith(b"PK"):
            raise SourceError(
                "ei: %s is not a zip container, so it is not an xlsx. A Cloudflare "
                "interstitial saved under an xlsx name looks exactly like this"
                % source
            )
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.workbook_path.with_name(self.workbook_path.name + ".tmp")
        tmp.write_bytes(body)
        tmp.replace(self.workbook_path)
        record = {
            "url": self.url,
            "page_url": PAGE_URL,
            "obtained_at": obtained_at,
            "obtained_from": str(source),
            "origin": "adopted",
            "content_length": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "note": note,
        }
        self._write_index(record)
        return record

    def _write_index(self, record: Mapping) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(dict(record), handle, indent=2, sort_keys=True)
            handle.write("\n")

    def read_index(self) -> dict:
        if not self.index_path.exists():
            return {}
        with open(self.index_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def load_workbook_bytes(self) -> bytes:
        """The workbook, from disk when it is there and from EI when it is not."""
        if self.workbook_path.exists() and not self.refetch:
            return self.workbook_path.read_bytes()

        try:
            response = http_get(
                self.url,
                headers={
                    "Accept": (
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet,*/*;q=0.8"
                    )
                },
                delay=self.delay,
                retries=3,
                timeout=180,
            )
        except SourceError as exc:
            raise SourceError(
                "ei: could not fetch the Statistical Review workbook, %s. "
                "energyinst.org answered HTTP 403 with Server: cloudflare and "
                "Cf-Mitigated: challenge to every request from this machine on "
                "2026-09-13, on the landing page as well as the file, after "
                "serving both to the same machine on 2026-09-11. That is an "
                "interactive bot challenge and this adapter will not try to "
                "defeat it. Download %s by hand from %s, which is a plain link "
                "with no registration, put it at %s, and run again. Then "
                "EiRefineryCapacity.adopt_workbook records where it came from."
                % (exc, WORKBOOK_FILENAME, PAGE_URL, self.workbook_path)
            ) from exc
        body = response.content
        if not body:
            raise SourceError("ei: the workbook downloaded as zero bytes from %s" % self.url)
        if not body.startswith(b"PK"):
            raise SourceError(
                "ei: %s did not serve a zip container, so it is not an xlsx. The "
                "first bytes were %r. The asset id in that path is edition "
                "specific, so check the landing page %s"
                % (self.url, body[:16], PAGE_URL)
            )

        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.workbook_path.with_name(self.workbook_path.name + ".tmp")
        tmp.write_bytes(body)
        tmp.replace(self.workbook_path)
        self.fetched = True

        self._write_index(
            {
                "url": self.url,
                "page_url": PAGE_URL,
                "obtained_at": utc_now_iso(),
                "obtained_from": self.url,
                "origin": "fetched",
                "last_modified": response.headers.get("Last-Modified"),
                "content_length": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "note": (
                    "The Energy Institute Statistical Review workbook. It is kept "
                    "here and never in data/cache: the Review forbids extensive "
                    "reproduction of its tables without written permission and the "
                    "capacity sheet carries S&P Global sourced data whose "
                    "redistribution is strictly prohibited."
                ),
            }
        )
        return body

    # -- fetch --------------------------------------------------------------

    def fetch(self) -> pd.DataFrame:
        body = self.load_workbook_bytes()
        frame = parse_capacity(body)
        self.vintage = read_edition(body)
        self.latest_year = int(pd.Timestamp(frame["date"].iloc[-1]).year)
        self.note = self._note(frame)
        return frame

    def _note(self, frame: pd.DataFrame) -> str:
        total = column_name(AGGREGATE)
        latest = frame[total].iloc[-1]
        return (
            "Atmospheric distillation capacity at year end on a calendar-day "
            "basis, thousand barrels daily, for %s, read from the sheet '%s' by "
            "row label and by the year printed above each column. THE LATEST YEAR "
            "IS %d AND THERE IS NO 2026 CAPACITY ANYWHERE IN THIS WORKBOOK, while "
            "the study's live months are 2026, so any 2026 utilisation rests on "
            "an assumption no source has published and must be labelled where it "
            "is made. The five country total for %d is %s kb/d. THIS CACHE IS NOT "
            "COMMITTABLE: the Review permits quotation with attribution but "
            "requires written permission for extensive reproduction of tables, "
            "and the capacity sheet is footnoted 'Source: Includes data from ICIS "
            "and S&P Global Energy' while the Review states that redistribution "
            "of S&P sourced data is strictly prohibited. The footnote does not "
            "say which rows came from which supplier, so the S&P part cannot be "
            "stripped out. See the module docstring for the three options open at "
            "Gate 1 and for the reason publishing only the ratio does not by "
            "itself withhold the table."
            % (
                ", ".join(COUNTRIES),
                SHEET,
                self.latest_year,
                self.latest_year,
                ("%.1f" % latest) if pd.notna(latest) else "not published",
            )
        )

    # -- manifest -----------------------------------------------------------

    def _entry(self, *, status: str, frame, note: str) -> dict:
        entry = super()._entry(status=status, frame=frame, note=note)

        # fetched_at MEANS WHEN THE BYTES WERE OBTAINED, NOT WHEN THIS RAN. The
        # base class stamps the moment of the run, which is right for an adapter
        # that fetches every time and wrong for this one: it parses a stored
        # workbook, and since 2026-09-13 it cannot do anything else, because the
        # site answers a Cloudflare challenge. A run that touched no network must
        # not print a fresh fetch time onto the provenance panel. checked_at is
        # what this run did.
        stored = self.read_index()
        entry["fetched_at"] = stored.get("obtained_at") or stored.get("fetched_at")
        entry["checked_at"] = utc_now_iso()
        entry["workbook"] = {
            key: stored.get(key)
            for key in ("origin", "obtained_at", "obtained_from", "sha256", "content_length")
        }
        entry["live_fetch"] = (
            "BLOCKED. energyinst.org answered HTTP 403 with Server: cloudflare "
            "and Cf-Mitigated: challenge to every request from this machine on "
            "2026-09-13, on https://www.energyinst.org/statistical-review/"
            "resources-and-data-downloads as well as on the workbook itself, "
            "after serving both to the same machine on 2026-09-11. It is an "
            "interactive bot challenge and this project does not defeat those. "
            "The workbook is downloaded by hand and adopted, and this series is "
            "therefore not part of the weekly refresh job."
        )
        entry["latest_year"] = self.latest_year
        entry["sheet"] = SHEET
        entry["countries"] = dict(COUNTRY_ROWS)
        entry["sheet_source_footnote"] = (
            "Source: Includes data from ICIS and S&P Global Energy"
        )
        entry["prohibition"] = (
            "REPRODUCTION OF THIS TABLE IS NOT PERMITTED. The Energy Institute "
            "Statistical Review 2026 says: 'Publishers are welcome to quote from "
            "this Review provided that they attribute the source to Energy "
            "Institute Statistical Review of World Energy 2026. However, for "
            "extensive reproduction of tables and/or charts, permission must "
            "first be obtained from: EI Statistical Review of World Energy, 61 "
            "New Cavendish Street, London W1G 7AR, "
            "statisticalreview@energyinst.org'. It also says: 'The redistribution "
            "or reproduction of data whose source is S&P Global Energy or S&P "
            "Global Inc, is strictly prohibited without its prior authorisation.' "
            "The capacity sheet itself is footnoted 'Source: Includes data from "
            "ICIS and S&P Global Energy' and does not say which rows came from "
            "which supplier, so the S&P sourced part cannot be separated out. "
            "This cache therefore lives in data/private/, is gitignored, and is "
            "never deployed."
        )
        entry["gate_1_decision"] = {
            "question": (
                "SPEC.md section 5.4 requires every cache committed so the site "
                "builds with no network, and SPEC.md non negotiable 6 requires "
                "anything that cannot be redistributed to stay in data/private/. "
                "Both cannot hold for this series. The owner chooses."
            ),
            "options": [
                "Ask EI for written permission to publish five country rows, "
                "statisticalreview@energyinst.org.",
                "Publish only the derived utilisation ratio and keep the "
                "capacity private. NOTE that the intake is itself committed, so "
                "a full precision published ratio hands the capacity back by "
                "division. See the module docstring.",
                "Take SPEC.md section 6.1's own fallback and model intake with a "
                "trend and closure dummies instead, saying so on the page.",
            ],
            "chosen": None,
        }
        entry["currency_note"] = (
            "The latest published year is %s. There is no 2026 capacity in this "
            "workbook and none anywhere else in the Review, so the manifest says "
            "which year the denominator is from rather than implying it is "
            "current. crack.sources.ei.capacity_monthly returns NaN past the last "
            "published year end rather than carrying it forward."
            % (self.latest_year,)
        )
        entry["revision_note"] = (
            "EI states that 'Each year revisions are made to historical data when "
            "updated or where more reliable data sources have become available'. "
            "The download URL carries an edition specific asset id and is not "
            "versioned, so the vintage above is read from the workbook's own "
            "Contents sheet and data/private/ei/index.json records a sha256 of "
            "the bytes that were parsed."
        )
        entry["workbook_fetched_this_run"] = self.fetched
        return entry


def main(argv: Sequence[str] | None = None) -> int:
    """Parse the capacity table into data/private and record it in the manifest."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--refetch",
        action="store_true",
        help="download the workbook again even if a copy is already stored",
    )
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args(list(argv) if argv is not None else None)

    adapter = EiRefineryCapacity(refetch=args.refetch, delay=args.delay)
    try:
        entry = adapter.run()
    except Exception as exc:  # noqa: BLE001, the CLI reports and exits non zero
        print("%s FAILED: %s: %s" % (SERIES, type(exc).__name__, exc))
        return 1
    print(
        "%-32s rows=%-4d %s to %s status=%s committable=%s\n  file    %s\n  vintage %s"
        % (
            entry["series"],
            entry["rows"],
            entry["first_date"],
            entry["last_date"],
            entry["status"],
            entry["committable"],
            entry["file"],
            entry["vintage"],
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
