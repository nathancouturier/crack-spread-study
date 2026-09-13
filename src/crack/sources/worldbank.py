"""European natural gas, monthly, $/MMBtu, from the World Bank pink sheet.

    series      worldbank_gas_europe_monthly
    cache       data/cache/worldbank_gas_europe_monthly.csv
    columns     date, gas_usd_mmbtu
    unit        US dollars per MMBtu
    source      World Bank Commodity Price Data (The Pink Sheet), monthly
    page        https://www.worldbank.org/en/research/commodity-markets

This is the PRIMARY monthly gas series, not the fallback SPEC.md section 5.1
assumed
----------------------------------------------------------------------------
The spec lists Yahoo TTF=F as the gas source and the pink sheet as something to
extend it with if the history is short. Recon 04 section 4 established that the
direction of that fix is backwards, on four counts that are facts about the
sources and not preferences:

  * it is ALREADY IN $/MMBtu. SPEC.md section 4.4 needs gas_usd_mmbtu. This
    series is published in that unit, so the analysis reads it rather than
    computing it, with no FX and no conversion factor and therefore no place to
    be wrong.
  * it IS TTF from April 2015, by the publisher's own definition. See the
    Description sheet quotation below. Not a proxy for TTF. TTF.
  * it has NO GAPS. 800 monthly observations, 1960M01 to 2026M08, every one of
    them a number, recon 04 section 4.4.
  * it is CC BY 4.0. Yahoo's TTF=F carries no redistribution grant at all, which
    is why crack.sources.yahoo writes into data/private and this one does not.

Recon 04 section 4.5 tied the two together numerically. Over the 106 months where
both exist, the monthly mean of TTF=F converted with DEXUSEU and MMBTU_PER_MWH
reproduces this series to a median absolute difference of 0.02 percent and a
worst case of 1.99 percent. That is a confirmation of SPEC.md section 4.4's unit
chain by construction, and it is also the honest size of the uncertainty in
going back the other way.

The URL rots, so it is discovered every time
---------------------------------------------
The workbook sits under a thedocs.worldbank.org path whose document id segment
changes. Recon 04 section 4.1 found three forms of it in the wild:

    .../74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx
    .../18675f1d1639c7a34d463f59263ba0a2-0050012025/related/...
    .../5d903e848db1d1b83e0ec8f744e55570-0350012021/related/...

and the old stable pubdocs.worldbank.org URL now returns HTTP 404. So there is no
URL to hardcode. discover_workbook_url() reads the landing page and takes the
href whose filename is CMO-Historical-Data-Monthly.xlsx, and it RAISES when it
cannot find one. It does not fall back to a remembered URL, because a remembered
URL that still resolves would be the worst outcome available: an old edition,
fetched successfully, with a stale vintage nobody noticed.

The file layout, and why every part of it is matched by label
--------------------------------------------------------------
Sheet "Monthly Prices", zero indexed: rows 0 to 3 are titles, of which row 3 is
"Updated on September 02, 2026" and becomes the manifest vintage; row 4 carries
the series names; row 5 carries the units; data starts at row 6 with column A
holding a period written as 2026M08.

The Europe gas series was in column I when recon 04 read it. That is not used.
The column is found by matching row 4's text against "Natural gas, Europe" and
the unit cell underneath it is then checked to still read ($/mmbtu). The pink
sheet has added and removed series before, the September 2026 revision notes
record exactly that, and a column index would survive such a change while
quietly pointing at LNG Japan.

A missing value in this file is the token ".." as the file's own note block
describes it, which reaches a reader as a single U+2026 horizontal ellipsis.
Other columns carry it; the Europe gas column carried none on 2026-09-11. It is
mapped to NaN. Anything else that is not a number raises.

Two things carried into the manifest rather than left in prose
---------------------------------------------------------------
1. A STRUCTURAL BREAK AT 2015-04. The series description is verbatim:

       Natural Gas (Europe), from April 2015, Netherlands Title Transfer Facility
       (TTF); April 2010 to March 2015, average import border price and a spot
       price component, including UK; during June 2000 - March 2010 prices
       excludes UK.

   So there are two definition changes inside one published series, at 2000-06
   and at 2010-04, and the one that matters is 2015-04. This is the World Bank's
   own splice inside its own series and the adapter cannot undo it. It is written
   into the manifest as structural_breaks and SPEC.md section 4.3 requires it
   marked on every chart that spans it. The level moved from 8.27 to 6.77, a fall
   of 18.1 percent, across that one month, and recon 04 section 5.3 found no free
   overlap series that would let anyone decompose how much of that was the
   definition and how much was the market. The page says so rather than picking a
   number.

2. RECON 04 OPEN QUESTION 3, THE LEADING ASTERISK. The Description sheet prints
   the Europe gas description in a row whose first cell is "*", and the same
   sheet's own footnote says "* denotes forecast series". That reading does not
   obviously apply to a historical monthly file, and no sentence in the workbook
   settles it. The question travels in the manifest as open_question rather than
   being resolved by guessing, and it belongs in docs/open-questions.md.

Attribution, which is a condition of the licence and not a courtesy: World Bank
Commodity Price Data (The Pink Sheet), CC BY 4.0. The series itself credits
Bloomberg Finance L.P. and World Gas Intelligence, so do not strip that and do
not present the numbers as this study's own assessment.
"""

from __future__ import annotations

import io
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

import pandas as pd

from ..config import BOUNDS_GAS_USD_MMBTU
from ..config import source as registered_source
from .base import Adapter, SourceError, http_get

__all__ = [
    "SERIES",
    "COLUMN",
    "LANDING_PAGE",
    "WORKBOOK_FILENAME",
    "SHEET",
    "SERIES_LABEL",
    "EXPECTED_UNIT",
    "MISSING_TOKENS",
    "DEFINITION_BREAKS",
    "SERIES_DESCRIPTION",
    "OPEN_QUESTION",
    "discover_workbook_url",
    "parse_workbook",
    "read_vintage",
    "fetch_monthly",
    "WorldBankGasEurope",
    "main",
]


#: Manifest and cache name, a key of crack.config.SOURCES.
SERIES = "worldbank_gas_europe_monthly"

#: Value column. The unit is in the name because SPEC.md section 4.4 reads this
#: column straight into gas_usd_mmbtu and a renamed column would hide a unit
#: change.
COLUMN = "gas_usd_mmbtu"

#: The page the workbook link is discovered on. This one is stable, the file URL
#: is not.
LANDING_PAGE = "https://www.worldbank.org/en/research/commodity-markets"

#: The filename to look for on that page. Matched on the filename, not on the
#: full URL, because the directory above it is exactly the part that rots.
WORKBOOK_FILENAME = "CMO-Historical-Data-Monthly.xlsx"

#: The sheet the monthly numbers are on. The workbook also carries "Mismatch
#: Details", "Monthly Indices", "Description" and "Index Weights".
SHEET = "Monthly Prices"

#: Row 4 of SHEET, zero indexed, carries the series names. Verbatim.
SERIES_LABEL = "Natural gas, Europe"

#: Row 5 of SHEET carries the units. The cell under SERIES_LABEL must still read
#: this, or the series changed unit and nothing downstream would notice.
EXPECTED_UNIT = "($/mmbtu)"

#: Zero indexed rows in SHEET. Searched for by content, these are the starting
#: point and the sanity check, not an assumption. See find_header_rows().
NAME_ROW = 4
UNIT_ROW = 5
FIRST_DATA_ROW = 6

#: What the file writes where it has no observation. The workbook's own note
#: block calls it "..", and openpyxl hands it back as one U+2026 horizontal
#: ellipsis. Both spellings are accepted and both become NaN, never zero.
MISSING_TOKENS = frozenset({"", "..", "...", chr(0x2026), "n/a", "na", "nan"})

#: The two definition changes inside this one published series, from the
#: Description sheet, and what each side of the 2015-04 one has to be called.
#: SPEC.md section 4.3 requires the break marked on every chart that spans it.
DEFINITION_BREAKS = (
    {
        "date": "2000-06-01",
        "note": (
            "From June 2000 the series is an average import border price plus a "
            "spot price component, excluding the UK. What it was before June "
            "2000 is not stated in the workbook."
        ),
    },
    {
        "date": "2010-04-01",
        "note": (
            "From April 2010 the same construction includes the UK."
        ),
    },
    {
        "date": "2015-04-01",
        "note": (
            "From April 2015 the series is the Netherlands Title Transfer "
            "Facility, TTF, by the publisher's own definition. Before it, the "
            "series is an average import border price plus a spot component "
            "including the UK and must be labelled that way, never as TTF. The "
            "level fell from 8.27 to 6.77 $/MMBtu across this one month, 18.1 "
            "percent. No free overlap series exists that would separate the "
            "definition change from the market move, recon 04 section 5.3, so "
            "the split is not asserted."
        ),
    },
)

#: The series description, verbatim from the Description sheet, doubled
#: attribution and all. Quoted rather than paraphrased because the April 2015
#: clause is the single most load bearing sentence in the gas layer.
SERIES_DESCRIPTION = (
    "Natural Gas (Europe), from April 2015, Netherlands Title Transfer Facility "
    "(TTF); April 2010 to March 2015, average import border price and a spot "
    "price component, including UK; during June 2000 - March 2010 prices "
    "excludes UK. Bloomberg Finance L.P. Finance L.P.; World Gas Intelligence; "
    "World Bank."
)

#: Recon 04 open question 3, carried in the manifest so it reaches the provenance
#: panel rather than only docs/open-questions.md.
OPEN_QUESTION = (
    "The Description sheet prints this series' description in a row whose first "
    "cell is '*', and row 107 of that sheet says '* denotes forecast series'. "
    "Nothing in the workbook says whether that marks a series the World Bank "
    "publishes forecasts for in the Commodity Markets Outlook, which is the "
    "reading that makes sense for a historical monthly file, or something about "
    "the history itself. Recon 04 open question 3. Unresolved, and not resolved "
    "by guessing."
)

#: 800 monthly observations 1960M01 to 2026M08 when recon 04 read the file. The
#: floors sit under that with room for the file to be re cut, and high enough
#: that a truncated workbook cannot replace a good cache.
MIN_ROWS = 700
MIN_PUBLISHED = 700

#: The first period the file carries. A workbook starting later has been re cut
#: and is worth stopping on rather than silently shortening the history.
SERIES_START = "1960-01-01"


_registered = registered_source(SERIES)
if _registered.page_url != LANDING_PAGE:
    raise RuntimeError(
        "crack.sources.worldbank discovers the workbook from %s but "
        "crack.config.SOURCES registers the page %s"
        % (LANDING_PAGE, _registered.page_url)
    )


# --------------------------------------------------------------------------
# Finding the file
# --------------------------------------------------------------------------

class _LinkCollector(HTMLParser):
    """Collect every href on a page, in document order.

    A regex over the raw HTML would do for this one page today. A parser is used
    because the landing page is a rendered marketing page whose markup changes
    with every redesign, and a parser fails on a page shape it does not
    understand rather than matching something that merely looks like a link.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.hrefs.append(value.strip())


def discover_workbook_url(html, *, base_url: str = LANDING_PAGE) -> str:
    """Find the monthly workbook's URL on the landing page. No network.

    Args:
        html: the landing page body, text or bytes.
        base_url: what to resolve a relative href against.

    Returns:
        The absolute URL of CMO-Historical-Data-Monthly.xlsx.

    Raises:
        SourceError: when the page carries no such link, or carries more than
            one that disagree. Both are loud on purpose. The document id segment
            in the path rots, the legacy pubdocs URL already 404s, and the one
            thing this adapter must never do is fall back to a URL it remembers:
            an old edition that still resolves would be fetched successfully,
            cached, and stamped with a vintage nobody read.
    """
    if isinstance(html, (bytes, bytearray)):
        html = html.decode("utf-8", errors="replace")

    parser = _LinkCollector()
    parser.feed(html)
    wanted = WORKBOOK_FILENAME.lower()

    hits: list[str] = []
    for href in parser.hrefs:
        # Match on the filename at the end of the path, ignoring any query.
        path = href.split("?", 1)[0].split("#", 1)[0]
        if path.lower().rsplit("/", 1)[-1] == wanted:
            absolute = urljoin(base_url, href)
            if absolute not in hits:
                hits.append(absolute)

    if not hits:
        raise SourceError(
            "worldbank %s: no link to %s on %s. The document id segment of the "
            "file path changes and the legacy pubdocs.worldbank.org URL is "
            "already HTTP 404, so there is no URL to fall back to and guessing "
            "one would risk fetching an old edition successfully. Open the page "
            "and find where the monthly historical workbook moved to. The page "
            "carried %d link(s) in total."
            % (SERIES, WORKBOOK_FILENAME, base_url, len(parser.hrefs))
        )
    if len(hits) > 1:
        raise SourceError(
            "worldbank %s: %d different links to %s on %s, %s. Picking one would "
            "be a guess about which edition is current"
            % (SERIES, len(hits), WORKBOOK_FILENAME, base_url, ", ".join(hits))
        )
    return hits[0]


# --------------------------------------------------------------------------
# Parsing, no network
# --------------------------------------------------------------------------

_PERIOD = re.compile(r"^\s*(\d{4})M(\d{1,2})\s*$", re.IGNORECASE)


def _period_to_timestamp(text: str) -> pd.Timestamp | None:
    """Turn a pink sheet period label such as 2026M08 into a month start.

    Returns None for anything that is not a period label, which is how the
    trailing note rows at the bottom of a sheet are told apart from data.
    """
    match = _PERIOD.match(str(text))
    if not match:
        return None
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        return None
    return pd.Timestamp(year=year, month=month, day=1)


def _cell_text(value) -> str:
    return "" if value is None else str(value).strip()


def _parse_number(raw, *, where: str) -> float:
    """One price cell. The missing token becomes NaN, anything odd raises."""
    if raw is None:
        return float("nan")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    text = str(raw).strip()
    if text.lower() in MISSING_TOKENS:
        return float("nan")
    # Strip a thousands separator only where it is unambiguous, then fail rather
    # than coerce. A cell this parser cannot read is a format change, and a
    # format change written into the cache as a zero is an invented gas price.
    cleaned = text.replace(",", "")
    try:
        return float(cleaned)
    except ValueError as exc:
        raise SourceError(
            "worldbank %s %s: cannot read %r as a price. If the file has started "
            "writing a new token for a missing month, add it to MISSING_TOKENS "
            "deliberately rather than letting it become a number"
            % (SERIES, where, raw)
        ) from exc


def _open_sheet(payload):
    """Open the workbook and return the Monthly Prices worksheet.

    Args:
        payload: the response body as bytes, or a path to a saved copy.
    """
    try:
        import openpyxl
    except ImportError as exc:  # pragma: no cover, an environment problem
        raise SourceError(
            "worldbank %s: openpyxl is not installed and the pink sheet is an "
            "xlsx" % SERIES
        ) from exc

    try:
        handle = (
            io.BytesIO(bytes(payload))
            if isinstance(payload, (bytes, bytearray))
            else str(payload)
        )
        book = openpyxl.load_workbook(handle, read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001, openpyxl raises several types
        raise SourceError(
            "worldbank %s: the download did not open as an xlsx workbook, %s: "
            "%s. That is usually an HTML error page served under the file's name"
            % (SERIES, type(exc).__name__, exc)
        ) from exc

    if SHEET not in book.sheetnames:
        raise SourceError(
            "worldbank %s: the workbook has no %r sheet, sheets were %s"
            % (SERIES, SHEET, ", ".join(book.sheetnames))
        )
    return book, book[SHEET]


def _find_series_column(rows: list[list], label: str) -> tuple[int, int]:
    """Find the column holding one named series, by label and not by position.

    Args:
        rows: the sheet as a list of row lists, zero indexed.
        label: the series name as row NAME_ROW prints it.

    Returns:
        (name row index, column index), both zero based.

    Raises:
        SourceError: when the label is absent, when it appears more than once,
            or when the unit cell under it is not EXPECTED_UNIT. Each of the
            three is a different way the file could change under this parser and
            each would otherwise produce a plausible looking wrong series.
    """
    wanted = label.strip().lower()

    found: list[tuple[int, int]] = []
    # The name row is searched for rather than assumed, over the first dozen
    # rows, because the title block above it has gained and lost lines before.
    for row_index in range(0, min(12, len(rows))):
        for col_index, cell in enumerate(rows[row_index]):
            if _cell_text(cell).lower() == wanted:
                found.append((row_index, col_index))

    if not found:
        header = ", ".join(
            repr(_cell_text(c)) for c in (rows[NAME_ROW] if len(rows) > NAME_ROW else [])
        )
        raise SourceError(
            "worldbank %s: no column headed %r in the first 12 rows of %r. Row "
            "%d read: %s. The pink sheet adds and removes series, so this is "
            "matched by label and never by position, and a missing label is a "
            "stop rather than a fallback"
            % (SERIES, label, SHEET, NAME_ROW + 1, header or "nothing")
        )
    if len(found) > 1:
        raise SourceError(
            "worldbank %s: %d cells read %r, at %s. Picking one would be a guess"
            % (
                SERIES,
                len(found),
                label,
                ", ".join("row %d column %d" % (r + 1, c + 1) for r, c in found),
            )
        )

    name_row, column = found[0]
    unit_row = name_row + 1
    unit = _cell_text(rows[unit_row][column]).lower() if unit_row < len(rows) else ""
    if unit != EXPECTED_UNIT:
        raise SourceError(
            "worldbank %s: the unit cell under %r reads %r, expected %r. The "
            "unit is checked because SPEC.md section 4.4 reads this column "
            "straight into gas_usd_mmbtu, so a series that changed unit would "
            "be wrong by a factor nobody would see"
            % (SERIES, label, unit or "nothing", EXPECTED_UNIT)
        )
    return name_row, column


def read_vintage(rows: list[list]) -> str | None:
    """The 'Updated on ...' line from the sheet's title block, or None.

    Recon 04 section 4.6: cell A4 reads "Updated on September 02, 2026" and the
    file is republished on or about the 2nd of each month. It goes into the
    manifest vintage, because a revision note is the only warning this source
    gives and a vintage is the only way to notice one landed.
    """
    for row in rows[: min(12, len(rows))]:
        for cell in row:
            text = _cell_text(cell)
            if text.lower().startswith("updated on"):
                return text
    return None


def parse_workbook(payload, *, label: str = SERIES_LABEL) -> pd.DataFrame:
    """Parse the pink sheet monthly workbook into the cache layout. No network.

    Args:
        payload: the response body as bytes, or a path to a saved copy.
        label: the series name to extract, as row 5 of the sheet prints it.

    Returns:
        A frame with date, the month's first day, and gas_usd_mmbtu. Ascending
        by date, one row per period the file carries, NaN where the file carries
        its missing token.

    Raises:
        SourceError: on anything that is not this workbook. See
            _find_series_column for the three ways the sheet can change.
    """
    book, sheet = _open_sheet(payload)
    try:
        rows = [list(row) for row in sheet.iter_rows(values_only=True)]
    finally:
        book.close()

    if len(rows) <= FIRST_DATA_ROW:
        raise SourceError(
            "worldbank %s: sheet %r has %d row(s), too few to hold a monthly "
            "series" % (SERIES, SHEET, len(rows))
        )

    name_row, column = _find_series_column(rows, label)
    first_data_row = name_row + 2

    dates: list[pd.Timestamp] = []
    values: list[float] = []
    for index in range(first_data_row, len(rows)):
        row = rows[index]
        if not row:
            continue
        period = _period_to_timestamp(_cell_text(row[0]))
        if period is None:
            # A row whose first cell is not a period label is a note or a blank
            # at the foot of the sheet, not data. Skipping it is safe because the
            # data block is contiguous and every data row is keyed by a period.
            continue
        raw = row[column] if column < len(row) else None
        values.append(_parse_number(raw, where="period %s" % _cell_text(row[0])))
        dates.append(period)

    if not dates:
        raise SourceError(
            "worldbank %s: sheet %r carried no row whose first cell looks like a "
            "period such as 2026M08" % (SERIES, SHEET)
        )

    frame = pd.DataFrame({"date": dates, COLUMN: values})
    duplicates = frame.loc[frame["date"].duplicated(), "date"]
    if len(duplicates):
        raise SourceError(
            "worldbank %s: duplicate period(s), first is %s"
            % (SERIES, duplicates.iloc[0].strftime("%Y-%m"))
        )
    frame = frame.sort_values("date", kind="mergesort").reset_index(drop=True)
    frame.attrs["vintage"] = read_vintage(rows)
    return frame


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

def fetch_monthly(*, delay: float = 1.0) -> tuple[pd.DataFrame, str]:
    """Discover the workbook, fetch it and parse it. Two network calls.

    One request for the landing page and one for the file, which is what SPEC.md
    section 5.4's "one request per file" asks for. The discovered URL travels
    back with the frame so the manifest records the URL that was actually used
    rather than the one this module hoped for.
    """
    page = http_get(LANDING_PAGE, delay=delay, retries=3, timeout=45)
    url = discover_workbook_url(page.content, base_url=LANDING_PAGE)

    workbook = http_get(
        url,
        headers={
            "Accept": (
                "application/vnd.openxmlformats-officedocument.spreadsheetml."
                "sheet,*/*;q=0.8"
            )
        },
        delay=delay,
        retries=3,
        timeout=90,
    )
    body = workbook.content
    if not body:
        raise SourceError("worldbank %s: the workbook download was empty" % SERIES)
    return parse_workbook(body), url


# --------------------------------------------------------------------------
# The adapter
# --------------------------------------------------------------------------

class WorldBankGasEurope(Adapter):
    """The pink sheet's Natural gas, Europe series, monthly, in $/MMBtu."""

    name = SERIES
    source = "World Bank Commodity Price Data (The Pink Sheet)"
    #: Filled in by fetch() with the URL that was actually discovered. The class
    #: attribute is the landing page so that a failed run still records something
    #: a human can open.
    url = LANDING_PAGE
    page_url = LANDING_PAGE
    unit = "USD per MMBtu"
    frequency = "monthly"
    method = "published"
    committable = True
    licence_note = _registered.licence_note
    required_cols = ("date", COLUMN)
    bounds = {COLUMN: BOUNDS_GAS_USD_MMBTU}
    date_col = "date"
    min_rows = MIN_ROWS
    min_observations = {COLUMN: MIN_PUBLISHED}
    observation_column = COLUMN

    def __init__(self, *, delay: float = 1.0):
        """
        Args:
            delay: polite pause before each of the two requests, seconds.
        """
        self.delay = float(delay)
        #: the URL discovered on the landing page, set by fetch()
        self.discovered_url: str | None = None

    def fetch(self) -> pd.DataFrame:
        frame, url = fetch_monthly(delay=self.delay)
        self.discovered_url = url
        self.url = url
        self.vintage = frame.attrs.get("vintage")

        first = frame["date"].min()
        if first > pd.Timestamp(SERIES_START):
            raise SourceError(
                "worldbank %s: the workbook starts %s, later than the documented "
                "start of %s. The file has been re cut and the history would "
                "silently shorten"
                % (SERIES, first.strftime("%Y-%m"), SERIES_START[:7])
            )

        published = int(frame[COLUMN].notna().sum())
        self.note = (
            "Natural gas, Europe, monthly, US dollars per MMBtu, read straight "
            "from the pink sheet's 'Monthly Prices' sheet by matching the row 5 "
            "label %r and checking the unit cell under it still reads %r. %d of "
            "%d periods carry a value. THIS IS THE PRIMARY MONTHLY GAS SERIES, "
            "not a fallback: it is already in the unit SPEC.md section 4.4 needs, "
            "so gas_usd_mmbtu is read and never computed, with no FX and no "
            "conversion factor. From April 2015 it IS TTF by the publisher's own "
            "definition, and before that it is an average import border price "
            "plus a spot component which must never be labelled TTF. Three "
            "definition changes are carried in structural_breaks and SPEC.md "
            "section 4.3 requires the 2015-04 one marked on every chart that "
            "spans it. The workbook URL was discovered from the landing page "
            "because the document id segment of the path rots, recon 04 section "
            "4.1: this run used %s. Attribution is a licence condition, CC BY "
            "4.0, and the series itself credits Bloomberg Finance L.P. and World "
            "Gas Intelligence."
            % (SERIES_LABEL, EXPECTED_UNIT, published, len(frame), url)
        )
        return frame

    def _entry(self, *, status: str, frame, note: str) -> dict:
        """The base entry plus the three source specific facts.

        base.manifest_upsert carries extra keys through, which is what makes it
        possible to declare a structural break where the data is rather than in
        a document the provenance panel does not read.
        """
        entry = super()._entry(status=status, frame=frame, note=note)
        entry["structural_breaks"] = [dict(b) for b in DEFINITION_BREAKS]
        entry["series_description"] = SERIES_DESCRIPTION
        entry["open_question"] = OPEN_QUESTION
        if self.discovered_url:
            entry["discovered_url"] = self.discovered_url
        return entry


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> int:
    """Run the adapter and print an ASCII report. Returns an exit code."""
    adapter = WorldBankGasEurope()
    try:
        entry = adapter.run()
    except Exception as exc:  # noqa: BLE001, the CLI reports and exits non zero
        print("%s FAILED: %s: %s" % (SERIES, type(exc).__name__, exc))
        return 1
    print(
        "%-30s rows=%-5d %s to %s gaps=%d status=%s vintage=%s"
        % (
            entry["series"],
            entry["rows"],
            entry["first_date"],
            entry["last_date"],
            len(entry["gaps"]),
            entry["status"],
            entry["vintage"],
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
