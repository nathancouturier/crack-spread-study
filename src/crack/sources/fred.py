"""Brent and EUR/USD, daily, from FRED's keyless fredgraph.csv endpoint.

    series      fred_brent_daily          fred_eurusd_daily
    cache       data/cache/...csv         data/cache/...csv
    columns     date, brent_usd_bbl       date, eurusd
    unit        USD per barrel            US dollars per one euro
    id          DCOILBRENTEU              DEXUSEU
    url         https://fred.stlouisfed.org/graph/fredgraph.csv?id=<id>
    page        https://fred.stlouisfed.org/series/<id>

Brent is the crude leg of every crack in SPEC.md section 4.2 and the cross check
subject of SPEC.md section 5.5. EUR/USD is the FX leg of the gas chain in
SPEC.md section 4.4. They come from the same endpoint and they are still two
adapters, because they are two series with two calendars and a manifest entry
each.

Five traps, all measured, all encoded below
--------------------------------------------
1. THE HEADER IS "observation_date", NOT "DATE". SPEC.md section 5.1 was written
   against an older FRED download. Recon 04 sections 1.3 and 2.2 read the
   current files: the first column is headed observation_date and the second
   carries the series id verbatim. Both spellings are accepted here and the
   value column is found by matching the id, never by position, because a file
   whose columns move is exactly the failure position based parsing cannot see.

2. A MISSING OBSERVATION IS AN EMPTY FIELD, NOT A DOT. Recon 04 section 1.3
   verified it with od -c on 2025-12-25: the line is

       2025-12-25,

   with a trailing comma and nothing after it. The historical "." convention
   still appears in FRED vintage files and elsewhere on the site, so both are
   accepted and both become NaN. A zero here would be a fabricated Brent print
   on a day nobody published one, which SPEC.md section 2 rule 1 forbids
   outright. The whole DCOILBRENTEU download carries 283 such rows.

3. A BROWSER USER AGENT GETS THE CONNECTION RESET. Recon 04 section 1.2 measured
   the same URL five ways in one minute: curl's own token, a named project token
   and python-requests all returned HTTP 200 in under a second, "Mozilla/5.0"
   got curl error 56 with zero bytes, and a full Chrome string timed out after
   40 seconds. The sibling repository measured the same thing independently on
   2026-08-31 for SOFR. crack.sources.base.http_get already picks the project
   token for this host, so this module sets no User-Agent of its own and must
   not start.

4. THE TWO SERIES FOLLOW DIFFERENT HOLIDAY CALENDARS. Brent blanks on UK and
   European bank holidays, about 8 or 9 a year. EUR/USD blanks on the US federal
   calendar, about 11 or 12 a year. Recon 04 section 2.5 joined the two on date
   over the whole shared span: 172 business days carry a Brent price and no FX
   rate, and 94 carry an FX rate and no Brent price, out of 7,220 joined rows.
   calendar_disagreement() below measures it from whatever the files currently
   say, so the number in the manifest is the one that was true on the day of the
   fetch. Anything that needs both legs joins them on the date and writes NaN
   where either is missing. It never zips them by position and never carries one
   forward to meet the other.

5. EUR/USD LAGS BY UP TO A WEEK. The underlying H.10 release goes out on Monday
   afternoons covering the previous business week, so the FX series can be five
   business days behind Brent, recon 04 section 2.6. That is not a gap and not a
   failure. It is why SPEC.md section 7.2's "Now" view reads the monthly gas
   price in $/MMBtu straight from the World Bank pink sheet, which needs no FX
   at all.

The licence question this adapter does not settle
--------------------------------------------------
FRED tags both series "public domain: citation requested", which is its most
permissive tier, and the underlying publishers are two US federal agencies. The
same legal page also prohibits "data mining, mirroring, robots, scraping, or
similar data-gathering or extraction methods except as expressly allowed by the
terms of use applicable to the FRED API". A scheduled job that downloads
fredgraph.csv and commits it into a public repository is, read strictly, both a
robot and a mirror. Recon 04 section 1.8 records the clause verbatim and does not
resolve it, and neither does this module.

SPEC.md section 5.1 names FRED, so FRED is built. Two things follow:

  * the concern travels with the data. crack.config's _FRED_NOTE carries it into
    the manifest licence_note of both series, so it is printed on the provenance
    panel rather than filed in a document nobody opens. docs/open-questions.md
    carries the clause in full.
  * the escape route is built and tested. crack.sources.eia fetches the same
    Brent numbers from EIA directly, where the reuse grant is explicit and there
    is no mirroring clause. Recon 04 section 1.7 joined the two on date and found
    a maximum absolute difference of 0.0 across all 9,973 shared dates. If the
    owner decides the FRED clause bites, the switch is a one line change of which
    series the analysis reads, not a rewrite.
"""

from __future__ import annotations

import csv
import io

import pandas as pd

# Imported under a different name because Adapter already owns an attribute
# called "source", the human readable publisher string, and the two would
# shadow each other inside a class body.
from ..config import BOUNDS_EURUSD
from ..config import source as registered_source
from .base import (
    Adapter,
    SourceError,
    SPEC_BOUNDS,
    http_get,
)

__all__ = [
    "BRENT_ID",
    "EURUSD_ID",
    "BRENT_SERIES",
    "EURUSD_SERIES",
    "BRENT_COLUMN",
    "EURUSD_COLUMN",
    "MISSING_TOKENS",
    "csv_url",
    "series_page",
    "parse_csv",
    "parse_value",
    "fetch_series",
    "calendar_disagreement",
    "FredDaily",
    "FredBrent",
    "FredEurUsd",
    "main",
]


# --------------------------------------------------------------------------
# Where the data is
# --------------------------------------------------------------------------

#: FRED's identifier for Europe Brent spot, the EIA series.
BRENT_ID = "DCOILBRENTEU"

#: FRED's identifier for US dollars to one euro, the Federal Reserve H.10 series.
EURUSD_ID = "DEXUSEU"

#: Manifest and cache names. They are keys of crack.config.SOURCES and the
#: registry is checked against them at import time, below.
BRENT_SERIES = "fred_brent_daily"
EURUSD_SERIES = "fred_eurusd_daily"

#: Value column names in the cache files. The unit is in the name on purpose:
#: SPEC.md section 4.4's gas chain and section 4.2's cracks both go wrong
#: silently if a column turns out to hold the other unit.
BRENT_COLUMN = "brent_usd_bbl"
EURUSD_COLUMN = "eurusd"

#: Cells that mean "FRED published no observation on this date". The empty field
#: is the current convention, recon 04 section 1.3. The dot is the historical one
#: and still appears in FRED vintage files. Never a zero, see trap 2 above.
MISSING_TOKENS = frozenset({"", ".", "na", "n/a", "nan"})

#: A byte order mark, written with chr() so this file stays pure ASCII. FRED does
#: not send one today, recon 04 section 1.3 checked, but a CSV that grows one is
#: a silly way to lose a fetch.
BOM = chr(0xFEFF)

#: Brent has 10,256 rows and 9,973 published prices as of 2026-09-11, recon 04
#: section 1.4. The floors sit about 2 percent under that: low enough that a
#: normal week of growth never trips them, high enough that a truncated response
#: or a column that stops printing prices cannot be written over a good cache.
BRENT_MIN_ROWS = 10_000
BRENT_MIN_PUBLISHED = 9_700

#: EUR/USD has 7,220 rows and 6,941 published rates, recon 04 section 2.3.
EURUSD_MIN_ROWS = 7_000
EURUSD_MIN_PUBLISHED = 6_700

#: The first date each series can start on. A download that begins earlier is a
#: source change worth stopping on, not a longer history: FRED's Brent begins
#: with EIA's own 1987-05-20 and the euro did not exist before 1999-01-04.
BRENT_START = "1987-05-20"
EURUSD_START = "1999-01-04"


def csv_url(series_id: str) -> str:
    """The keyless download URL for one FRED series id."""
    return "https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s" % series_id


def series_page(series_id: str) -> str:
    """The human readable page for one FRED series id, for provenance."""
    return "https://fred.stlouisfed.org/series/%s" % series_id


# The registry is what the provenance panel and docs/sources.md are generated
# from. If the URL in this module and the URL in the registry ever drift apart,
# the site links one file and the pipeline fetches another, so they are checked
# here rather than left to agree by luck.
for _series, _id in ((BRENT_SERIES, BRENT_ID), (EURUSD_SERIES, EURUSD_ID)):
    _registered = registered_source(_series)
    if _registered.machine_url != csv_url(_id):
        raise RuntimeError(
            "crack.sources.fred builds %s for %s but crack.config.SOURCES "
            "registers %s. One of the two is wrong and the site would link a "
            "different file from the one the pipeline reads"
            % (csv_url(_id), _series, _registered.machine_url)
        )
    if _registered.page_url != series_page(_id):
        raise RuntimeError(
            "crack.sources.fred builds the page %s for %s but "
            "crack.config.SOURCES registers %s"
            % (series_page(_id), _series, _registered.page_url)
        )


# --------------------------------------------------------------------------
# Parsing, no network
# --------------------------------------------------------------------------

def _match_header(headers, series_id: str) -> tuple[int, int]:
    """Find the date column and the value column by header text.

    Args:
        headers: the header cells in the order the file prints them.
        series_id: the FRED id, which is also the value column's header.

    Returns:
        (date column index, value column index).

    Raises:
        SourceError: naming the headers that were actually seen. FRED renamed
            the first column from DATE to observation_date at some point before
            2026 and SPEC.md section 5.1 still describes the old name, which is
            the reason this is matched rather than assumed.
    """
    cleaned = [h.strip().strip('"').lower() for h in headers]

    date_index = next(
        (i for i, h in enumerate(cleaned) if h in ("observation_date", "date")), None
    )
    if date_index is None:
        date_index = next((i for i, h in enumerate(cleaned) if "date" in h), None)
    if date_index is None:
        raise SourceError(
            "fred %s: no date column in the header, headers were %s"
            % (series_id, ", ".join(repr(h) for h in headers) or "none at all")
        )

    wanted = series_id.lower()
    hits = [i for i, h in enumerate(cleaned) if h == wanted and i != date_index]
    if not hits:
        hits = [i for i, h in enumerate(cleaned) if wanted in h and i != date_index]
    if not hits:
        raise SourceError(
            "fred %s: no column headed %r, headers were %s"
            % (series_id, series_id, ", ".join(repr(h) for h in headers))
        )
    if len(hits) > 1:
        raise SourceError(
            "fred %s: %d columns match %r, %s. Picking one would be a guess"
            % (series_id, len(hits), series_id, ", ".join(repr(headers[i]) for i in hits))
        )
    return date_index, hits[0]


def parse_value(text: str, *, series_id: str, where: str = "") -> float:
    """Parse one FRED value cell.

    An empty field and a "." both mean the series has no observation for that
    date, and both become NaN. Anything else that is not a number raises rather
    than being coerced, because a coerced zero is an invented price.

    No thousands separator is accepted. FRED writes plain decimals, so a comma in
    a value field means the format changed, and that is worth failing on.
    """
    raw = (text or "").strip().strip('"')
    if raw.lower() in MISSING_TOKENS:
        return float("nan")
    try:
        return float(raw)
    except ValueError as exc:
        raise SourceError(
            "fred %s %s: cannot read %r as a number"
            % (series_id, where or "value cell", text)
        ) from exc


def parse_csv(text, *, series_id: str, column: str) -> pd.DataFrame:
    """Parse a fredgraph.csv download into the cache layout. No network.

    Args:
        text: the response body, decoded or raw bytes.
        series_id: the FRED id, used to find the value column and to write
            error messages a reader can act on.
        column: what to call the value column in the cache, for example
            brent_usd_bbl.

    Returns:
        A frame with columns date and the given column name, ascending by date.
        A date FRED publishes nothing for keeps NaN and keeps its row, which is
        what makes a hole visible to the manifest rather than invisible in a
        shorter file.

    Raises:
        SourceError: on an empty body, an HTML error page, a header that cannot
            be matched, a row of the wrong width, an unparseable date, an
            unparseable value or a duplicate date. Nothing is repaired quietly.
    """
    if isinstance(text, (bytes, bytearray)):
        text = text.decode("utf-8", errors="replace")
    body = text.lstrip(BOM)
    if not body.strip():
        raise SourceError("fred %s: the download was empty" % series_id)

    opening = body[:400].lower()
    if "<html" in opening or "<!doctype" in opening:
        raise SourceError(
            "fred %s: the endpoint returned HTML, not CSV. That is an error page "
            "or an interstitial rather than the series" % series_id
        )

    reader = csv.reader(io.StringIO(body))
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise SourceError("fred %s: the download had no header row" % series_id) from exc

    date_index, value_index = _match_header(headers, series_id)
    width = len(headers)

    dates: list[pd.Timestamp] = []
    values: list[float] = []
    for number, row in enumerate(reader, start=2):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) != width:
            raise SourceError(
                "fred %s: line %d has %d field(s) but the header has %d, row was %s"
                % (series_id, number, len(row), width, row)
            )
        where = "line %d" % number
        raw_date = row[date_index].strip().strip('"')
        stamp = pd.to_datetime(raw_date, format="%Y-%m-%d", errors="coerce")
        if pd.isna(stamp):
            raise SourceError(
                "fred %s %s: cannot read %r as a yyyy-mm-dd date"
                % (series_id, where, raw_date)
            )
        dates.append(stamp)
        values.append(parse_value(row[value_index], series_id=series_id, where=where))

    if not dates:
        raise SourceError("fred %s: the download had a header but no rows" % series_id)

    frame = pd.DataFrame({"date": dates, column: values})
    duplicates = frame.loc[frame["date"].duplicated(), "date"]
    if len(duplicates):
        raise SourceError(
            "fred %s: duplicate date(s) in the download, first is %s"
            % (series_id, duplicates.iloc[0].strftime("%Y-%m-%d"))
        )
    return frame.sort_values("date", kind="mergesort").reset_index(drop=True)


def calendar_disagreement(
    brent: pd.DataFrame, eurusd: pd.DataFrame
) -> dict[str, int]:
    """Count the days where one FRED series prints and the other does not.

    Trap 4 in the module docstring, measured from the files in hand rather than
    quoted from the recon report, so the number that reaches the manifest is the
    one that was true on the day of the fetch.

    Args:
        brent: a frame with date and BRENT_COLUMN.
        eurusd: a frame with date and EURUSD_COLUMN.

    Returns:
        joined        dates present as a row in both files
        both          dates where both carry a value
        brent_only    dates where Brent carries a value and EUR/USD does not
        eurusd_only   dates where EUR/USD carries a value and Brent does not
        neither       dates where both files have a row and neither has a value

    The join is on the date and only on the date. Zipping the two by position
    would silently pair a Brent price with the wrong day's FX rate, which is the
    error this function exists to make visible.
    """
    left = brent.loc[:, ["date", BRENT_COLUMN]].copy()
    right = eurusd.loc[:, ["date", EURUSD_COLUMN]].copy()
    left["date"] = pd.to_datetime(left["date"], errors="coerce")
    right["date"] = pd.to_datetime(right["date"], errors="coerce")

    merged = left.merge(right, on="date", how="inner")
    has_brent = merged[BRENT_COLUMN].notna()
    has_fx = merged[EURUSD_COLUMN].notna()
    return {
        "joined": int(len(merged)),
        "both": int((has_brent & has_fx).sum()),
        "brent_only": int((has_brent & ~has_fx).sum()),
        "eurusd_only": int((~has_brent & has_fx).sum()),
        "neither": int((~has_brent & ~has_fx).sum()),
    }


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

def fetch_series(series_id: str, *, column: str, delay: float = 1.0) -> pd.DataFrame:
    """Fetch and parse one FRED series. Network call.

    No User-Agent is passed. base.http_get picks the project token for this
    host, and overriding it with the project browser string is what gets the
    connection reset. See trap 3 in the module docstring.
    """
    response = http_get(
        csv_url(series_id),
        headers={"Accept": "text/csv,*/*;q=0.8"},
        delay=delay,
        retries=3,
        timeout=45,
    )
    return parse_csv(response.content, series_id=series_id, column=column)


# --------------------------------------------------------------------------
# The adapters
# --------------------------------------------------------------------------

class FredDaily(Adapter):
    """Shared behaviour of the two FRED daily series.

    Everything that differs between Brent and EUR/USD is a class attribute, so
    the fetch, the start date guard and the note are written once. This is not
    an abstraction for its own sake: the two series really are the same file
    shape from the same endpoint, and writing the parser twice would be two
    chances to accept a "." as a zero in one of them.
    """

    #: the FRED id, which is also the value column's header in the download
    series_id: str = ""
    #: the earliest date the series can legitimately start on
    series_start: str = ""
    #: one human sentence for the manifest note, describing what the series is
    description: str = ""

    frequency = "daily"
    method = "published"
    committable = True
    date_col = "date"

    def __init__(self, *, delay: float = 1.0):
        """
        Args:
            delay: polite pause before each request, seconds. SPEC.md section
                5.4 asks for one and the default is a real second.
        """
        self.delay = float(delay)
        #: how many rows carry a value, set by fetch()
        self.published: int = 0
        #: how many rows are blank in the source, set by fetch()
        self.blank: int = 0

    def value_column(self) -> str:
        """The one value column this adapter writes."""
        return self.observation_column

    def fetch(self) -> pd.DataFrame:
        frame = fetch_series(
            self.series_id, column=self.value_column(), delay=self.delay
        )

        first = frame["date"].min()
        if first < pd.Timestamp(self.series_start):
            raise SourceError(
                "fred %s: the download starts %s, earlier than the documented "
                "series start of %s. That is a source change, not a longer "
                "history, and it is not written over the cache"
                % (self.series_id, first.strftime("%Y-%m-%d"), self.series_start)
            )

        column = self.value_column()
        self.published = int(frame[column].notna().sum())
        self.blank = len(frame) - self.published
        self.note = (
            "%s %d of %d rows carry a value and %d are blank in the source, all "
            "of them holidays on this series' own calendar. A blank is NaN in "
            "the cache, never a zero, and it counts as a gap exactly as a "
            "missing row would. rows and observations count the published "
            "values, file_rows counts the lines. Fetched from the keyless "
            "fredgraph.csv endpoint with the project token user agent, which is "
            "required: a browser user agent gets the connection reset from this "
            "machine, recon 04 section 1.2. FRED publishes this series on behalf "
            "of another agency, so cite both, and see docs/open-questions.md for "
            "the mirroring clause that a committed cache sits awkwardly against."
            % (self.description, self.published, len(frame), self.blank)
        )
        return frame


class FredBrent(FredDaily):
    """Europe Brent spot, daily, $/bbl. The crude leg of every crack."""

    name = BRENT_SERIES
    series_id = BRENT_ID
    series_start = BRENT_START
    source = "US Energy Information Administration, retrieved from FRED"
    url = csv_url(BRENT_ID)
    page_url = series_page(BRENT_ID)
    unit = "USD per barrel"
    description = (
        "Europe Brent spot price FOB, daily, US dollars per barrel, published by "
        "the US Energy Information Administration as series RBRTE and "
        "redistributed by FRED as DCOILBRENTEU."
    )
    required_cols = ("date", BRENT_COLUMN)
    bounds = {BRENT_COLUMN: SPEC_BOUNDS["brent_usd_bbl"]}
    min_rows = BRENT_MIN_ROWS
    min_observations = {BRENT_COLUMN: BRENT_MIN_PUBLISHED}
    observation_column = BRENT_COLUMN


class FredEurUsd(FredDaily):
    """US dollars to one euro, daily. The FX leg of the gas chain."""

    name = EURUSD_SERIES
    series_id = EURUSD_ID
    series_start = EURUSD_START
    source = (
        "Board of Governors of the Federal Reserve System, retrieved from FRED"
    )
    url = csv_url(EURUSD_ID)
    page_url = series_page(EURUSD_ID)
    unit = "US dollars per one euro"
    description = (
        "Noon buying rates in New York City for cable transfers, US dollars to "
        "one euro, daily, from the Federal Reserve Board H.10 release. The "
        "orientation is dollars per euro, which is what SPEC.md section 4.4's "
        "chain ttf_eur_mwh * eurusd / MMBTU_PER_MWH needs, so nothing is "
        "inverted anywhere. H.10 goes out on Monday afternoons covering the "
        "previous week, so this series can sit five business days behind Brent."
    )
    required_cols = ("date", EURUSD_COLUMN)
    #: The euro has traded between about 0.82 and 1.60 since 1999, so this band
    #: is a units and inversion check: a file of 0.86 dollars per euro would be
    #: euros per dollar and would land outside it.
    bounds = {EURUSD_COLUMN: BOUNDS_EURUSD}
    min_rows = EURUSD_MIN_ROWS
    min_observations = {EURUSD_COLUMN: EURUSD_MIN_PUBLISHED}
    observation_column = EURUSD_COLUMN


# The licence sentence a reader sees on the provenance panel is the registry's,
# not a paraphrase written here. Assigning it after the class body rather than
# inside it keeps the class readable and keeps one copy of the words.
FredBrent.licence_note = registered_source(BRENT_SERIES).licence_note
FredEurUsd.licence_note = registered_source(EURUSD_SERIES).licence_note


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> int:
    """Run both adapters and print an ASCII report. Returns an exit code.

    Print policy is ASCII only: the Windows console is cp1252 and one accented
    character raises UnicodeEncodeError halfway through a report, which is a
    miserable way to lose a fetch.
    """
    code = 0
    for adapter in (FredBrent(), FredEurUsd()):
        try:
            entry = adapter.run()
        except Exception as exc:  # noqa: BLE001, the CLI reports and exits non zero
            print("%s FAILED: %s: %s" % (adapter.name, type(exc).__name__, exc))
            code = 1
            continue
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
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
