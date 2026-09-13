"""NWE physical oil: refinery intake, refinery output by product, crude imports.

    series      jodi_nwe_refinery_intake_monthly
                jodi_nwe_refinery_output_monthly
                jodi_nwe_crude_imports_monthly
    caches      data/cache/<series>.csv
    unit        thousand barrels per day, JODI's KBD
    countries   BE, DE, FR, NL, GB
    source      JODI-Oil World Database, International Energy Forum
    page        https://www.jodidata.org/oil/database/data-downloads.aspx

This is the layer that turns a margin into crude demand. SPEC.md section 6.1
regresses NWE refinery utilisation on the margin after gas, and the numerator of
that utilisation is the crude intake below. SPEC.md section 4.3 layer 4 wants
observed NWE yields from the output table. SPEC.md section 6.1 also asks for
crude imports next to intake as the physical footprint of the same demand.

Seven facts about this source that the spec does not carry
----------------------------------------------------------
Each one was measured by recon 03, each one would otherwise be found the hard
way, and each one is enforced somewhere below rather than left in prose.

1. IT IS NOT ONE CSV. SPEC.md section 5.1 says "JODI-Oil World Database, free
   CSV" as though one file were on offer. There is no world_primary.csv. There
   are 50 annual files, 25 primary and 25 secondary, 933 MB in total for one
   full refresh. So this module never downloads the database. It downloads one
   year at a time, keeps the five countries and the handful of flows and
   products this study needs, writes that few thousand row extract to
   data/private/jodi_raw/ and throws the rest away. Recon 03 section 1.2.

2. THE CURRENT YEAR IS NOT NAMED LIKE THE OTHERS. Closed years are 2025.csv.
   The year in progress is primaryyear2026.csv and secondaryyear2026.csv. An
   adapter that built URLs from a pattern would silently lose the newest year
   every January, which is the one year anybody is looking at. So the hrefs are
   read off the downloads page and never constructed. discover_annual_files()
   raises rather than guessing.

3. THE UK IS GB. SPEC.md writes "BE, DE, FR, NL, UK" in four places. The
   database has 118 REF_AREA values, GB is one of them and UK is not, so
   hardcoding UK returns an empty series rather than an error. COUNTRIES below
   carries GB and the country label carries the note.

4. THE LAG IS 2.4 TO 2.9 MONTHS, NOT 2. Data ran to 2026-06 when the files were
   last written on 2026-08-20, and the next update is the 22nd of the following
   month, so the gap widens to almost three months just before each release.
   SPEC.md section 13 says "about two months" and SPEC.md section 7.2 already
   requires the runs data date shown separately from the margin data date. The
   manifest carries the measured lag so the site can print it rather than assume
   it.

5. THREE SERIES START IN 2009-01, NOT 2002-01. TOTCRUDE, JETKERO and NAPHTHA
   begin when JODI extended the questionnaire. Everything else runs from
   2002-01. The min_observations floors below differ between the two groups for
   exactly that reason, and the manifest says which is which.

6. TOTPRODS EXCLUDES JETKERO. JODI's own definition of total oil products is
   "Sum of categories (5) to (12) excluding (9)", and category 9 is kerosene
   type jet fuel, which is already inside KEROSENE. Summing the product columns
   in this cache WITH jetkero double counts jet. Sum with kerosene instead.
   Recon 03 checked the arithmetic: for the five countries in 2026-06 the sum
   of lpg, naphtha, gasoline, kerosene, gasdies, resfuel and ononspec is 5,867.4
   kb/d against a printed TOTPRODS of 5,867.0.

7. JODI REVISES HISTORY. The 2002 file was rewritten in October 2025. SPEC.md
   section 13 warns about it. The raw store records a sha256 and the server's
   Last-Modified per year so a revision is visible rather than silent.

THE MODELLING CHOICE THIS MODULE REFUSES TO MAKE FOR YOU
---------------------------------------------------------
SPEC.md section 4.3 layer 4 says "Compute NWE yields from JODI refinery output
by product over refinery intake". Done literally, on the five country sums in
KBD, that ratio is not 1:

    month     refinobs/crudeoil   refgrout/totprods   ratio
    2019-06             5,276.7             6,103.0   1.1566
    2022-10             4,995.8             5,761.0   1.1532
    2025-06             5,111.3             5,789.0   1.1326
    2026-06             5,147.1             5,867.0   1.1399

The numerator is GROSS output, including refinery fuel, from ALL refinery feed,
which is crude plus NGL plus other feedstocks plus backflows. The denominator is
crude alone. Using those ratios as yield[p] in contribution[p] = yield[p] *
crack[p] would inflate the decomposed margin by about 15 percent.

Swap the denominator to REFINOBS/TOTCRUDE, total refinery feed, and the same
computation gives 1.0338, 1.0132, 1.0314 and 1.0241. That is volume gain, which
is physically right. The cost is that TOTCRUDE only starts in 2009-01, so seven
years of history lose their yield vector.

This module therefore publishes BOTH denominators, side by side, in the intake
cache: nwe5_refinobs_crudeoil_kbd and nwe5_refinobs_totcrude_kbd. It computes no
yield and picks no denominator. That is a real modelling choice, SPEC.md has not
made it, and making it quietly inside a data adapter would hide it from the
Method view where it belongs. Recon 03 section 1.8. The analysis gate decides,
in the open, and says which it chose on the page.

Column names are JODI's own codes, on purpose
----------------------------------------------
A column is named {country}_{flow}_{product}_kbd with JODI's codes lowercased,
for example be_refinobs_crudeoil_kbd or nwe5_refgrout_gasdies_kbd. It is uglier
than "belgium_crude_runs" and it is traceable: every part of the name is a token
this module verified against JODI's published item names document before it
parsed a single row. The human readable names live in PRODUCT_NAMES and
FLOW_NAMES and travel into the manifest.

nwe5_ is the sum of the five countries, and it is NaN unless all five reported.
A four country sum presented as five would be a quiet 15 percent hole in crude
demand on the one chart the whole study builds toward.

Licence
-------
JODI publishes no data licence. Its terms of use are website terms: "The
Intellectual Property rights in the JODI Website, and in the material published
on it, are protected by Intellectual Property laws and treaties around the world.
All such rights are reserved." The downloads page says the data can be downloaded
for free, which is a statement about access and not about republication. Recon 03
section 1.9 reads this as: committing a small derived extract with attribution is
normal practice, it is not covered by a grant, and it is materially weaker than
FRED or EIA. So the parsed extract is committed with attribution, the raw annual
files are never mirrored, and JODIinfo@ief.org should be asked before Gate 5.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import urljoin

import numpy as np
import pandas as pd

from ..config import BOUNDS_INTAKE_KB_D
from ..config import source as registered_source
from .base import PRIVATE, Adapter, SourceError, http_get, http_head, utc_now_iso

__all__ = [
    "SERIES_INTAKE",
    "SERIES_OUTPUT",
    "SERIES_IMPORTS",
    "COUNTRIES",
    "COUNTRY_NAMES",
    "UNIT",
    "DOWNLOADS_PAGE",
    "ITEM_NAMES_URL",
    "CSV_HEADER",
    "MISSING_TOKENS",
    "PRODUCT_NAMES",
    "FLOW_NAMES",
    "UNIT_NAMES",
    "ASSESSMENT_CODES",
    "WANTED",
    "LATE_START_KEYS",
    "LATE_START",
    "EARLY_START",
    "discover_annual_files",
    "verify_item_names",
    "filter_annual_csv",
    "JodiRawStore",
    "pivot",
    "column_name",
    "JodiSeries",
    "JodiRefineryIntake",
    "JodiRefineryOutput",
    "JodiCrudeImports",
    "ADAPTERS",
    "main",
]


# --------------------------------------------------------------------------
# What we ask for
# --------------------------------------------------------------------------

#: Manifest and cache names. Three caches rather than one, because the cache
#: format is one row per date and a single tidy table of five countries times
#: eight measures would repeat every date forty times, which validate_frame
#: refuses outright and rightly so.
SERIES_INTAKE = "jodi_nwe_refinery_intake_monthly"
SERIES_OUTPUT = "jodi_nwe_refinery_output_monthly"
SERIES_IMPORTS = "jodi_nwe_crude_imports_monthly"

#: THE UK IS GB. SPEC.md section 5.1 writes UK, JODI publishes GB, and UK is not
#: one of the 118 REF_AREA values in the database, so the spec's spelling returns
#: nothing at all rather than failing. Recon 03 section 1.7.
COUNTRIES: tuple[str, ...] = ("BE", "DE", "FR", "NL", "GB")

COUNTRY_NAMES: Mapping[str, str] = {
    "BE": "Belgium",
    "DE": "Germany",
    "FR": "France",
    "NL": "Netherlands",
    "GB": "United Kingdom, which JODI codes GB and SPEC.md section 5.1 calls UK",
}

#: The aggregate column prefix. Five countries, summed, and NaN unless all five
#: reported that month.
AGGREGATE = "nwe5"

#: The only unit this study reads. JODI publishes the same observation five
#: times, once per unit, and KBD is the one that is directly comparable across
#: months of unequal length and directly comparable with Energy Institute
#: capacity, which is also thousand barrels daily.
UNIT = "KBD"

DOWNLOADS_PAGE = "https://www.jodidata.org/oil/database/data-downloads.aspx"

#: JODI's own published guide to the codes. SPEC.md section 5.1 says to resolve
#: product and flow codes from it and never to hardcode them, so this module
#: fetches it and checks every code it is about to use against the printed long
#: name before it parses anything. See verify_item_names.
ITEM_NAMES_URL = (
    "https://www.jodidata.org/_resources/files/downloads/oil-data/"
    "jodi-oil-wdb-item-names-ver2017.pdf"
)

#: The manual, quoted in DEFINITIONS below. Not fetched, cited.
MANUAL_URL = (
    "https://www.jodidata.org/_resources/files/downloads/manuals/"
    "jodi-oil-2nd-manual.pdf"
)

#: The header line, identical in all 50 files. Checked on every file, by label,
#: and a file whose columns moved is a stop rather than a silent reindex.
CSV_HEADER: tuple[str, ...] = (
    "REF_AREA",
    "TIME_PERIOD",
    "ENERGY_PRODUCT",
    "FLOW_BREAKDOWN",
    "UNIT_MEASURE",
    "OBS_VALUE",
    "ASSESSMENT_CODE",
)

#: What OBS_VALUE says when there is no observation. Four tokens, counted by
#: recon 03 section 1.4 across 955,500 NWE rows: N/A 179,760, x 38,220, minus
#: 16,800, two dots 10,500. NOT VERIFIED, and the recon says so plainly: neither
#: the manual nor the item names guide defines them separately from one another,
#: so all four are treated as missing and none of them is interpreted. None
#: appears in any series this study reads, so this is robustness and not a live
#: problem. Anything else that will not parse as a number raises rather than
#: becoming a zero, SPEC.md section 2 rule 1.
MISSING_TOKENS: frozenset[str] = frozenset({"", "-", "..", "...", "x", "X", "N/A", "n/a", "NA", "na"})

#: Products, as JODI's item names guide prints them. The code is the key, the
#: long name is what the guide prints beside it, and verify_item_names checks
#: that the guide still prints that pairing before any file is parsed.
PRODUCT_NAMES: Mapping[str, str] = {
    "CRUDEOIL": "Crude oil",
    "TOTCRUDE": "Total",
    "GASOLINE": "Motor and aviation gasoline",
    "NAPHTHA": "Naphtha",
    "KEROSENE": "Kerosenes",
    "JETKERO": "of which: kerosene type jet fuel",
    "GASDIES": "Gas/diesel oil",
    "RESFUEL": "Fuel oil",
    "TOTPRODS": "Total oil products",
}

#: Flows, same guide, same rule.
FLOW_NAMES: Mapping[str, str] = {
    "REFINOBS": "Refinery intake",
    "REFGROUT": "Refinery output",
    "TOTIMPSB": "Imports",
}

#: Units, same guide. Printed the other way round there, code first.
UNIT_NAMES: Mapping[str, str] = {
    "KBD": "Thousand Barrels per day (kb/d)",
}

#: The assessment codes, verbatim from the item names guide. SPEC.md section 5.1
#: requires codes 1, 2 and 3 carried into the manifest; 4 is carried too because
#: the guide defines it even though recon 03 counted zero rows of it in all 50
#: files, and a code that appears for the first time must not arrive as an
#: unknown integer.
ASSESSMENT_CODES: Mapping[str, str] = {
    "1": "Results of the assessment show reasonable levels of comparability",
    "2": "Consult metadata/Use with caution",
    "3": "Data has not been assessed",
    "4": "Data under verification",
}

#: Definitions quoted from the JODI-Oil manual, chapter 2.3, page 20. The manual
#: prints "Refinery" with an fi ligature the PDF text layer cannot map, which is
#: why recon 03 quotes it as "Re?inery"; the words are as printed.
DEFINITIONS: Mapping[str, str] = {
    "REFINOBS": "Refinery intake : Observed refinery throughputs.",
    "REFGROUT": "Refinery output : Gross output (including refinery fuel).",
    "TOTIMPSB": (
        "Imports/Exports : Goods having physically crossed the international "
        "boundaries, excluding transit trade, international marine and aviation "
        "bunkers."
    ),
    "TOTPRODS": "Total oil products : Sum of categories (5) to (12) excluding (9).",
}

#: table -> the (flow, product) pairs this study keeps. Everything else in the
#: 933 MB is discarded before it reaches disk.
#:
#: Two intakes on purpose, see the module docstring: REFINOBS over CRUDEOIL is
#: crude only and runs from 2002, REFINOBS over TOTCRUDE is total refinery feed
#: and runs from 2009. Both are published and neither is chosen here.
WANTED: Mapping[str, tuple[tuple[str, str], ...]] = {
    "primary": (
        ("REFINOBS", "CRUDEOIL"),
        ("REFINOBS", "TOTCRUDE"),
        ("TOTIMPSB", "CRUDEOIL"),
    ),
    "secondary": (
        ("REFGROUT", "GASOLINE"),
        ("REFGROUT", "GASDIES"),
        ("REFGROUT", "JETKERO"),
        ("REFGROUT", "KEROSENE"),
        ("REFGROUT", "RESFUEL"),
        ("REFGROUT", "NAPHTHA"),
        ("REFGROUT", "TOTPRODS"),
    ),
}

#: The three (flow, product) pairs JODI only began collecting in 2009-01, when
#: it extended the questionnaire. Recon 03 section 1.7 measured 210 months for
#: these and 294 for everything else, in all five countries, with no gaps in
#: either group. Their observation floors differ for that reason and for no
#: other, and a run that found them starting later than 2009-01 has lost history.
LATE_START_KEYS: frozenset[tuple[str, str]] = frozenset(
    {("REFINOBS", "TOTCRUDE"), ("REFGROUT", "JETKERO"), ("REFGROUT", "NAPHTHA")}
)
LATE_START = "2009-01"
EARLY_START = "2002-01"

#: The first year of the database. A downloads page offering fewer years than
#: this has changed shape and the history would silently shorten.
FIRST_YEAR = 2002

#: JODI publishes on the dates in its own update calendar, "at noon London time",
#: around the 20th of each month. The 2026 schedule, quoted from
#: https://www.jodidata.org/_resources/files/downloads/jodi-update-schedule-2026.pdf
#: runs 21 Jan, 19 Feb, 18 Mar, 21 Apr, 20 May, 22 Jun, 21 Jul, 20 Aug, 22 Sep,
#: 21 Oct, 19 Nov, 21 Dec, with supplementary updates whenever the IEF receives
#: further submissions. Recorded so the refresh job can be scheduled against the
#: source rather than against a guess.
UPDATE_CALENDAR_URL = (
    "https://www.jodidata.org/_resources/files/downloads/"
    "jodi-update-schedule-2026.pdf"
)

#: Where the filtered per year extracts live. NOT data/cache: these are an
#: intermediate, they are a subset of JODI's own files rather than a derived
#: series, and mirroring JODI's files is exactly what recon 03 section 1.9 says
#: not to do. Gitignored with the rest of data/private.
RAW_DIRNAME = "jodi_raw"

#: Observation floors. 294 months from 2002-01 and 210 from 2009-01 when recon
#: 03 counted them, in every one of the five countries. The floors sit about 5
#: percent under, which is low enough not to trip on a revision and high enough
#: that a truncated download cannot replace a good cache.
MIN_OBSERVATIONS_EARLY = 280
MIN_OBSERVATIONS_LATE = 200
MIN_ROWS = 280


_PERIOD = re.compile(r"^(\d{4})-(\d{2})$")

#: The three spellings an annual file on this machine can carry. primary_2002 is
#: how recon 03 saved its downloads, 2002 is how the site names a closed year,
#: and primaryyear2026 is how it names the year in progress. A bare year gives no
#: table, so adopt_local takes the table from the directory the file sits in and
#: skips the file when that directory does not name one, rather than guessing:
#: reading a secondary file as primary would file gasoline rows under crude.
_LOCAL_ANNUAL_NAME = re.compile(
    r"^(?:(?P<table>primary|secondary)[_-]?(?:year)?)?(?P<year>\d{4})$",
    re.IGNORECASE,
)


def _int_or_none(text) -> int | None:
    """An HTTP header as an int, or None when it is absent or not a number."""
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


for _name in (SERIES_INTAKE, SERIES_OUTPUT, SERIES_IMPORTS):
    _registered = registered_source(_name)
    if _registered.machine_url is not None:
        raise RuntimeError(
            "crack.config.SOURCES gives %s a machine_url. The current year's "
            "file is named primaryyear2026.csv rather than 2026.csv, so the "
            "URLs are discovered from the downloads page and never constructed"
            % _name
        )


# --------------------------------------------------------------------------
# Finding the files
# --------------------------------------------------------------------------

class _LinkCollector(HTMLParser):
    """Collect every href on a page, in document order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.hrefs.append(value.strip())


#: annual-csv/<table>/<anything><year>.csv , where <table> is primary or
#: secondary. It matches both spellings the site uses, 2025.csv and
#: primaryyear2026.csv, and it takes the YEAR OUT OF THE FILENAME rather than
#: assuming a position, so when 2026 closes and is renamed to 2026.csv nothing
#: here has to change.
_ANNUAL_HREF = re.compile(
    r"/annual-csv/(?P<table>primary|secondary)/(?P<stem>[A-Za-z]*)(?P<year>\d{4})\.csv$",
    re.IGNORECASE,
)


def discover_annual_files(
    html, *, base_url: str = DOWNLOADS_PAGE
) -> dict[tuple[str, int], str]:
    """Read the annual CSV links off the downloads page. No network.

    Args:
        html: the downloads page body, text or bytes.
        base_url: what a relative href resolves against.

    Returns:
        {(table, year): absolute url}, table being "primary" or "secondary".

    Raises:
        SourceError: when the page carries no annual links, when the two tables
            disagree about which years exist, when a year is missing from the
            span, or when one (table, year) is offered at two different URLs.

    Why this is not a URL pattern. Closed years are served as 2025.csv and the
    year in progress as primaryyear2026.csv. A constructed URL would therefore
    fetch every year except the newest one, and would do it successfully, so the
    failure would show up as a series that quietly stopped in December. Recon 03
    section 4 item 3.
    """
    if isinstance(html, (bytes, bytearray)):
        html = html.decode("utf-8", errors="replace")

    parser = _LinkCollector()
    parser.feed(html)

    found: dict[tuple[str, int], str] = {}
    for href in parser.hrefs:
        path = href.split("?", 1)[0].split("#", 1)[0]
        match = _ANNUAL_HREF.search(path)
        if not match:
            continue
        table = match.group("table").lower()
        year = int(match.group("year"))
        absolute = urljoin(base_url, href)
        key = (table, year)
        if key in found and found[key] != absolute:
            raise SourceError(
                "jodi: the downloads page offers %s %d at two different URLs, %s "
                "and %s. Picking one would be a guess about which is current"
                % (table, year, found[key], absolute)
            )
        found[key] = absolute

    if not found:
        raise SourceError(
            "jodi: no annual CSV links on %s. The page carried %d link(s). The "
            "database is 50 annual files under .../annual-csv/primary/ and "
            ".../annual-csv/secondary/ and there is no single world CSV to fall "
            "back on, so this is a stop. Open the page and find where the annual "
            "files moved to" % (base_url, len(parser.hrefs))
        )

    for table in ("primary", "secondary"):
        years = sorted(y for t, y in found if t == table)
        if not years:
            raise SourceError(
                "jodi: the downloads page offers no %s annual files at all, only "
                "%s" % (table, sorted({t for t, _ in found}))
            )
        if years[0] != FIRST_YEAR:
            raise SourceError(
                "jodi: the %s table now starts at %d, not %d. The history would "
                "silently shorten" % (table, years[0], FIRST_YEAR)
            )
        missing = [y for y in range(years[0], years[-1] + 1) if y not in years]
        if missing:
            raise SourceError(
                "jodi: the %s table is missing year(s) %s between %d and %d"
                % (table, ", ".join(str(y) for y in missing), years[0], years[-1])
            )

    primary_years = {y for t, y in found if t == "primary"}
    secondary_years = {y for t, y in found if t == "secondary"}
    if primary_years != secondary_years:
        raise SourceError(
            "jodi: the primary and secondary tables offer different years, "
            "primary only %s, secondary only %s"
            % (
                sorted(primary_years - secondary_years),
                sorted(secondary_years - primary_years),
            )
        )
    return found


# --------------------------------------------------------------------------
# Resolving the codes from JODI's own document
# --------------------------------------------------------------------------

def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def verify_item_names(text: str) -> dict[str, str]:
    """Check every code this module uses against JODI's published guide.

    SPEC.md section 5.1: "Resolve product and flow codes from JODI's published
    short names list, never hardcode them." The codes are written down in
    PRODUCT_NAMES, FLOW_NAMES, UNIT_NAMES and ASSESSMENT_CODES because a program
    has to name something, and this function is what makes them resolved rather
    than remembered: it reads the guide and refuses to go on if the guide no
    longer prints that pairing.

    Args:
        text: the extracted text of jodi-oil-wdb-item-names-ver2017.pdf.

    Returns:
        {code: the long name as the guide prints it}, for every code checked.

    Raises:
        SourceError: naming the first code whose printed name has changed or
            gone. A renamed code is not something to recover from. It means the
            column this study calls gasoil is no longer necessarily gas/diesel
            oil, and nothing downstream would ever notice.

    How the guide is laid out. Products and flows are printed as two side by
    side tables, so one line can read "Production INDPROD Refinery output
    REFGROUT" and the name of a code is the text immediately to its left. Units
    and assessment codes are printed the other way round, code first, name after.
    Both shapes are handled explicitly and neither is guessed at.
    """
    if isinstance(text, (bytes, bytearray)):
        text = text.decode("utf-8", errors="replace")
    lines = [line for line in text.splitlines() if line.strip()]

    resolved: dict[str, str] = {}
    problems: list[str] = []

    def name_before(code: str) -> str | None:
        """The words printed immediately left of a code token, or None."""
        pattern = re.compile(r"(?<![A-Z0-9])" + re.escape(code) + r"(?![A-Z0-9])")
        for line in lines:
            match = pattern.search(line)
            if match:
                return line[: match.start()].strip()
        return None

    def name_after(code: str) -> str | None:
        """The words printed immediately right of a code at the line start."""
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(code + " "):
                return stripped[len(code) :].strip()
        return None

    for group, mapping in (("product", PRODUCT_NAMES), ("flow", FLOW_NAMES)):
        for code, expected in mapping.items():
            printed = name_before(code)
            if printed is None:
                problems.append("%s code %s does not appear in the guide" % (group, code))
                continue
            if not _normalise(printed).endswith(_normalise(expected)):
                problems.append(
                    "%s code %s is printed against %r, this module expects %r"
                    % (group, code, printed, expected)
                )
                continue
            resolved[code] = expected

    for code, expected in UNIT_NAMES.items():
        printed = name_after(code)
        if printed is None:
            problems.append("unit code %s does not appear in the guide" % code)
        elif _normalise(printed) != _normalise(expected):
            problems.append(
                "unit code %s is printed against %r, this module expects %r"
                % (code, printed, expected)
            )
        else:
            resolved[code] = expected

    for code, expected in ASSESSMENT_CODES.items():
        printed = name_after(code)
        if printed is None:
            problems.append("assessment code %s does not appear in the guide" % code)
        elif _normalise(printed) != _normalise(expected):
            problems.append(
                "assessment code %s is printed against %r, this module expects %r"
                % (code, printed, expected)
            )
        else:
            resolved[code] = expected

    if problems:
        raise SourceError(
            "jodi: the published item names guide no longer agrees with this "
            "module about %d code(s): %s. Source %s. A renamed code is a stop, "
            "not something to work around: it means a column this study labels "
            "gasoil may no longer be gas/diesel oil and nothing downstream would "
            "notice" % (len(problems), "; ".join(problems), ITEM_NAMES_URL)
        )
    return resolved


def _extract_pdf_text(payload: bytes) -> str:
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover, an environment problem
        raise SourceError(
            "jodi: pdfplumber is not installed and JODI's item names guide is a "
            "PDF. SPEC.md section 5.1 requires the codes resolved from it"
        ) from exc
    try:
        with pdfplumber.open(io.BytesIO(payload)) as book:
            return "\n".join((page.extract_text() or "") for page in book.pages)
    except Exception as exc:  # noqa: BLE001, pdfplumber raises several types
        raise SourceError(
            "jodi: could not read the item names guide as a PDF, %s: %s"
            % (type(exc).__name__, exc)
        ) from exc


# --------------------------------------------------------------------------
# Filtering one annual file
# --------------------------------------------------------------------------

def filter_annual_csv(payload, *, table: str, year: int) -> list[list[str]]:
    """Keep the five countries and the wanted flows and products. Discard the rest.

    Args:
        payload: one annual file, bytes or text. The caller holds it for as long
            as this call takes and then lets it go. A primary file is 11 MB and
            a secondary file is 26 MB, so one at a time is a few tens of
            megabytes of memory and nothing lands on disk.
        table: "primary" or "secondary", which decides what WANTED asks for.
        year: the year the file is supposed to cover, checked against its rows.

    Returns:
        The kept rows, verbatim, as lists of strings in CSV_HEADER order.
        OBS_VALUE is NOT parsed here: the file's own missing tokens survive into
        the extract so that a token this module has never seen is visible in
        data/private rather than already collapsed into a NaN.

    Raises:
        SourceError: on a header that is not CSV_HEADER, on a row whose
            TIME_PERIOD is not yyyy-mm, on a row dated outside the file's year,
            or when the file yields no rows at all for the five countries.
    """
    if table not in WANTED:
        raise SourceError("jodi: unknown table %r, expected one of %s" % (table, sorted(WANTED)))

    if isinstance(payload, (bytes, bytearray)):
        text = bytes(payload).decode("utf-8-sig", errors="strict")
    else:
        text = str(payload)

    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        header = next(reader)
    except StopIteration:
        raise SourceError("jodi: %s %d is empty" % (table, year)) from None

    header = [cell.strip() for cell in header]
    if tuple(header) != CSV_HEADER:
        raise SourceError(
            "jodi: %s %d has header %s, expected %s. Every field below is read "
            "by label from this header, so a changed layout is a stop rather "
            "than a reindex" % (table, year, header, list(CSV_HEADER))
        )
    index = {name: position for position, name in enumerate(header)}
    wanted = set(WANTED[table])
    countries = set(COUNTRIES)

    kept: list[list[str]] = []
    for row in reader:
        if len(row) != len(CSV_HEADER):
            if not any(cell.strip() for cell in row):
                continue
            raise SourceError(
                "jodi: %s %d has a row with %d field(s), expected %d: %s"
                % (table, year, len(row), len(CSV_HEADER), row)
            )
        if row[index["REF_AREA"]] not in countries:
            continue
        if row[index["UNIT_MEASURE"]] != UNIT:
            continue
        key = (row[index["FLOW_BREAKDOWN"]], row[index["ENERGY_PRODUCT"]])
        if key not in wanted:
            continue
        period = row[index["TIME_PERIOD"]].strip()
        match = _PERIOD.match(period)
        if not match:
            raise SourceError(
                "jodi: %s %d has TIME_PERIOD %r, expected yyyy-mm as the item "
                "names guide states" % (table, year, period)
            )
        if int(match.group(1)) != year:
            raise SourceError(
                "jodi: the file served as %s %d carries a row dated %s. The year "
                "comes from the filename on the downloads page, so this means "
                "the page and the file disagree" % (table, year, period)
            )
        kept.append([row[index[name]] for name in CSV_HEADER])

    if not kept:
        raise SourceError(
            "jodi: %s %d yielded no rows for %s at unit %s. Either the country "
            "codes changed or the file is not the one it claims to be"
            % (table, year, ", ".join(COUNTRIES), UNIT)
        )
    return kept


# --------------------------------------------------------------------------
# The raw store
# --------------------------------------------------------------------------

class JodiRawStore:
    """The filtered per year extracts, and the record of where each came from.

    One full refresh of the world database is 933 MB across 50 files. A weekly
    job that re fetched all of it would be slow, and it would be discourteous to
    a small organisation's web server, which recon 03 section 4 item 2 says in
    as many words. So this store keeps what was already filtered and fetches
    only what the policy asks for:

        policy "none"      touch nothing. Rebuild the caches from the extracts
                           already on disk. This is what make data-offline wants.
        policy "missing"   fetch the downloads page, then fetch only the years
                           with no extract on disk. The default.
        policy "recent"    missing, plus the newest RECENT_YEARS years, because
                           the current year gains a month every release and the
                           one before it still gets revised. This is what the
                           weekly job wants.
        policy "verify"    fetch the downloads page, then ask the server for the
                           size and Last-Modified of each of the 50 files with a
                           HEAD, and fetch only the ones whose size differs from
                           the bytes this store was built from, or that have no
                           extract at all. 51 small requests instead of 933 MB,
                           and unlike "recent" it notices a revision to a CLOSED
                           year, which is the revision SPEC.md section 13 warns
                           about and which recon 03 measured on the 2002 file.
                           jodidata.org answers HEAD correctly, measured here on
                           2026-09-13: primary/2002.csv returned 200 with
                           Content-Length 11,469,196 and Last-Modified Tue, 21
                           Oct 2025 17:48:00 GMT, both matching what recon 03
                           recorded from a GET. It is NOT one of the hosts in
                           base.HEAD_IS_BROKEN_ON.
        policy "all"       fetch all 50 files. 933 MB. Use it when JODI has
                           revised deep history, and not otherwise.

    adopt_local() sits beside the policies and takes no policy of its own: it
    filters annual files that are already on this machine, so a copy downloaded
    once does not have to be downloaded again to produce byte identical
    extracts.

    Every fetch records the URL, the moment of the fetch, the server's
    Last-Modified, the byte count and a sha256 of the raw file, so a revision to
    a closed year is visible as a changed digest rather than as a series that
    moved for no reason. SPEC.md section 13 warns that JODI revises history and
    recon 03 measured it: the 2002 file was rewritten on 2025-10-21.
    """

    #: How many of the newest years the "recent" policy re fetches.
    RECENT_YEARS = 2

    POLICIES = ("none", "missing", "recent", "verify", "all")

    def __init__(
        self,
        *,
        root: Path | None = None,
        policy: str = "missing",
        delay: float = 1.2,
    ) -> None:
        """
        Args:
            root: the directory holding the extracts. Defaults to
                data/private/jodi_raw, looked up at call time so the test
                sandbox can move it.
            policy: one of POLICIES.
            delay: polite pause before every request, seconds. Recon 03 fetched
                these files about 1.2 seconds apart and that is what is kept.
        """
        if policy not in self.POLICIES:
            raise ValueError(
                "jodi: unknown fetch policy %r, expected one of %s"
                % (policy, ", ".join(self.POLICIES))
            )
        self._root = root
        self.policy = policy
        self.delay = float(delay)
        self._loaded: pd.DataFrame | None = None
        self._index: dict | None = None
        self._report: dict | None = None

    # -- paths -------------------------------------------------------------

    @property
    def root(self) -> Path:
        if self._root is not None:
            return Path(self._root)
        return PRIVATE / RAW_DIRNAME

    def extract_path(self, table: str, year: int) -> Path:
        return self.root / ("%s_%d.csv" % (table, year))

    @property
    def index_path(self) -> Path:
        return self.root / "index.json"

    @property
    def item_names_path(self) -> Path:
        return self.root / "item_names.txt"

    # -- the index ---------------------------------------------------------

    def read_index(self) -> dict:
        if self._index is not None:
            return self._index
        if self.index_path.exists():
            with open(self.index_path, "r", encoding="utf-8") as handle:
                self._index = json.load(handle)
        else:
            self._index = {"files": {}}
        self._index.setdefault("files", {})
        return self._index

    def write_index(self) -> None:
        index = self.read_index()
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(index, handle, indent=2, sort_keys=True)
            handle.write("\n")

    # -- fetching ----------------------------------------------------------

    def _record(self, table: str, year: int, record: Mapping) -> None:
        index = self.read_index()
        index["files"]["%s/%d" % (table, year)] = dict(record)

    def _write_extract(self, table: str, year: int, rows: Sequence[Sequence[str]]) -> None:
        """Write one filtered year to disk, atomically, header first."""
        path = self.extract_path(table, year)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(CSV_HEADER)
            writer.writerows(rows)
        tmp.replace(path)

    def fetch_one(self, table: str, year: int, url: str) -> int:
        """Fetch one annual file, filter it, write the extract. Returns rows kept."""
        response = http_get(
            url,
            headers={"Accept": "text/csv,application/octet-stream,*/*;q=0.8"},
            delay=self.delay,
            retries=3,
            timeout=180,
        )
        body = response.content
        if not body:
            raise SourceError("jodi: %s %d downloaded as zero bytes from %s" % (table, year, url))
        rows = filter_annual_csv(body, table=table, year=year)
        self._write_extract(table, year, rows)

        self._record(
            table,
            year,
            {
                "url": url,
                "fetched_at": utc_now_iso(),
                "last_modified": response.headers.get("Last-Modified"),
                "content_length": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "rows_kept": len(rows),
                "origin": "fetched",
            },
        )
        return len(rows)

    def adopt_local(self, directory: Path | str) -> dict:
        """Filter annual files that are already on this machine. No network.

        WHY THIS EXISTS AND WHAT IT REFUSES TO CLAIM. One full refresh is 933 MB
        across 50 requests against a small organisation's web server, and recon
        03 downloaded all 50 files on 2026-09-11, before this module existed.
        Fetching them a second time to produce byte identical extracts would be
        discourteous, which is recon 03 section 4 item 2's own complaint about
        the weekly job. So a copy already on disk is filtered in place.

        What an adopted record does NOT say is that the bytes are current. It
        carries origin "adopted", the path it came from, the sha256 and the byte
        count of what was actually read, and NO last_modified, so _vintage
        reports the release date as not recorded until refresh() has run under
        the "verify" policy and asked the server. Adopting and then verifying
        costs 51 HEAD requests; adopting alone is honest but undated.

        Args:
            directory: holds the annual files under any of the three spellings
                this project has seen, primary_2002.csv as recon 03 saved them,
                2002.csv as the site serves closed years, and
                primaryyear2026.csv as the site serves the year in progress.
                Files whose name matches none of those are ignored, because the
                same directory also holds the manual, the item names guide and
                the recon's own 50 MB five country extract, and none of those is
                an annual file.

        Returns:
            {"adopted": [...], "skipped": [...], "directory": str}

        Raises:
            SourceError: when the directory holds no annual file at all, or when
                one of them does not parse. A directory that was pointed at by
                hand and yields nothing is a mistake worth stopping for.
        """
        source_dir = Path(directory)
        if not source_dir.is_dir():
            raise SourceError("jodi: %s is not a directory" % source_dir)

        report: dict = {"directory": str(source_dir), "adopted": [], "skipped": []}
        for path in sorted(source_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() != ".csv":
                continue
            match = _LOCAL_ANNUAL_NAME.match(path.stem)
            if not match:
                report["skipped"].append(path.name)
                continue
            table = (match.group("table") or "").lower()
            year = int(match.group("year"))
            if not table:
                # A bare 2002.csv gives no table, so the directory it sits in
                # has to. Guessing would put secondary rows in the primary
                # extract and the whole study would read gasoline as crude.
                parent = path.parent.name.lower()
                if parent not in WANTED:
                    report["skipped"].append(path.name)
                    continue
                table = parent
            body = path.read_bytes()
            rows = filter_annual_csv(body, table=table, year=year)
            self._write_extract(table, year, rows)
            self._record(
                table,
                year,
                {
                    "url": None,
                    "adopted_at": utc_now_iso(),
                    "adopted_from": str(path),
                    "last_modified": None,
                    "content_length": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "rows_kept": len(rows),
                    "origin": "adopted",
                },
            )
            report["adopted"].append("%s/%d" % (table, year))

        if not report["adopted"]:
            raise SourceError(
                "jodi: %s holds no annual file this module recognises. Expected "
                "names like primary_2002.csv, 2002.csv beside a primary or "
                "secondary directory, or primaryyear2026.csv. It held %d other "
                "csv file(s)" % (source_dir, len(report["skipped"]))
            )
        self.write_index()
        return report

    def _verify_one(self, table: str, year: int, url: str, record: Mapping) -> tuple[bool, dict]:
        """Ask the server what it is serving now. Returns (needs a fetch, served).

        A HEAD, not a GET, so checking all 50 files costs kilobytes. The decision
        is made on Content-Length rather than on Last-Modified, because a
        rewritten file that happens to keep its length is the case that matters
        and JODI rewrites closed years in place: recon 03 found the 2002 file
        touched on 2025-10-21. Where the served length differs from the bytes
        this store was built from, the file is fetched in full and the extract
        rebuilt. Where the store has no record of a length at all, which is what
        a very old index looks like, the file is fetched rather than trusted.
        """
        head = http_head(url, delay=self.delay)
        served = {
            "last_modified": head.headers.get("Last-Modified"),
            "content_length": _int_or_none(head.headers.get("Content-Length")),
            "verified_at": utc_now_iso(),
            "url": url,
        }
        if not self.extract_path(table, year).exists():
            return True, served
        known = record.get("content_length")
        if known is None or served["content_length"] is None:
            return True, served
        return int(known) != int(served["content_length"]), served

    def refresh(self, *, force: bool = False) -> dict:
        """Bring the store up to date under the policy. Returns a small report.

        ONCE PER PROCESS, not once per adapter. The three JODI adapters share one
        store precisely so that one pass over the source feeds all three, and
        each of them calls this from its own fetch(). Without the memo below,
        building the three caches would walk the downloads page and all 50 files
        three times over, which is the discourtesy this class exists to avoid.
        Pass force=True to make it look again in the same process.
        """
        if self._report is not None and not force:
            return dict(self._report, reused_report=True)

        report: dict = {
            "policy": self.policy,
            "fetched": [],
            "reused": [],
            "verified": [],
            "page_url": DOWNLOADS_PAGE,
            "discovered": 0,
        }
        if self.policy == "none":
            report["note"] = "offline, nothing was fetched"
            self._report = report
            return report

        page = http_get(DOWNLOADS_PAGE, delay=self.delay, retries=3, timeout=60)
        files = discover_annual_files(page.content, base_url=DOWNLOADS_PAGE)
        report["discovered"] = len(files)

        years = sorted({year for _, year in files})
        recent = set(years[-self.RECENT_YEARS :])

        # The codes are resolved from JODI's own guide before a single annual
        # file is parsed, SPEC.md section 5.1.
        self.refresh_item_names()

        index = self.read_index()
        for (table, year) in sorted(files):
            url = files[(table, year)]
            path = self.extract_path(table, year)
            key = "%s/%d" % (table, year)
            record = index["files"].get(key, {})
            served: dict | None = None
            if self.policy == "verify":
                need, served = self._verify_one(table, year, url, record)
            else:
                need = (
                    self.policy == "all"
                    or not path.exists()
                    or (self.policy == "recent" and year in recent)
                )
            if need:
                self.fetch_one(table, year, url)
                report["fetched"].append(key)
                continue
            if served is not None:
                # The bytes on disk are the bytes the server is serving, so the
                # extract keeps its provenance and gains the release date.
                merged = dict(record)
                merged.update(served)
                merged["origin"] = "%s, verified against the server" % record.get(
                    "origin", "unknown"
                )
                self._record(table, year, merged)
                report["verified"].append(key)
            else:
                report["reused"].append(key)

        self.write_index()
        self._report = report
        return report

    def refresh_item_names(self) -> dict[str, str]:
        """Fetch JODI's item names guide if it is not cached, then verify the codes."""
        if not self.item_names_path.exists():
            response = http_get(
                ITEM_NAMES_URL,
                headers={"Accept": "application/pdf,*/*;q=0.8"},
                delay=self.delay,
                retries=3,
                timeout=90,
            )
            text = _extract_pdf_text(response.content)
            self.root.mkdir(parents=True, exist_ok=True)
            with open(self.item_names_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
        return self.verify_codes()

    def verify_codes(self) -> dict[str, str]:
        """Check the cached item names guide against this module's codes."""
        if not self.item_names_path.exists():
            raise SourceError(
                "jodi: %s is not on disk, so the product and flow codes have not "
                "been resolved from JODI's own published guide. SPEC.md section "
                "5.1 requires it. Run with a policy other than 'none' once, or "
                "put the extracted text of %s there"
                % (self.item_names_path, ITEM_NAMES_URL)
            )
        text = self.item_names_path.read_text(encoding="utf-8")
        return verify_item_names(text)

    # -- reading -----------------------------------------------------------

    def load(self) -> pd.DataFrame:
        """Every extract on disk, as one tidy frame. Memoised per instance.

        Returns:
            Columns date, ref_area, flow, product, value, code, table. One row
            per observation JODI printed, value NaN where the file carried one
            of MISSING_TOKENS.
        """
        if self._loaded is not None:
            return self._loaded

        self.verify_codes()

        paths = sorted(self.root.glob("*_[0-9][0-9][0-9][0-9].csv"))
        if not paths:
            raise SourceError(
                "jodi: no extracts in %s. Nothing has been fetched yet, and this "
                "module will not invent a physical series" % self.root
            )

        rows: list[tuple] = []
        for path in paths:
            table, _, year_text = path.stem.rpartition("_")
            year = int(year_text)
            with open(path, "r", encoding="utf-8", newline="") as handle:
                reader = csv.reader(handle)
                header = next(reader)
                if tuple(header) != CSV_HEADER:
                    raise SourceError(
                        "jodi: extract %s has header %s, expected %s"
                        % (path, header, list(CSV_HEADER))
                    )
                for row in reader:
                    period = row[1]
                    match = _PERIOD.match(period)
                    if not match:
                        raise SourceError(
                            "jodi: extract %s carries TIME_PERIOD %r" % (path, period)
                        )
                    rows.append(
                        (
                            pd.Timestamp(year=int(match.group(1)), month=int(match.group(2)), day=1),
                            row[0],
                            row[3],
                            row[2],
                            _parse_value(row[5], where="%s %s" % (path.name, period)),
                            row[6].strip(),
                            table,
                        )
                    )

        frame = pd.DataFrame(
            rows,
            columns=["date", "ref_area", "flow", "product", "value", "code", "table"],
        )
        duplicated = frame.duplicated(["date", "ref_area", "flow", "product"], keep=False)
        if duplicated.any():
            first = frame[duplicated].iloc[0]
            raise SourceError(
                "jodi: %d duplicate observation(s) across the extracts, the first "
                "being %s %s %s %s. Two annual files cannot both carry the same "
                "month" % (int(duplicated.sum()), first["ref_area"], first["date"].date(), first["flow"], first["product"])
            )
        unknown = sorted(set(frame["code"]) - set(ASSESSMENT_CODES))
        if unknown:
            raise SourceError(
                "jodi: assessment code(s) %s appear in the data and are not in "
                "JODI's published list %s. SPEC.md section 5.1 requires the codes "
                "carried, and carrying one this module cannot describe would be "
                "carrying a number rather than a meaning"
                % (", ".join(unknown), ", ".join(sorted(ASSESSMENT_CODES)))
            )
        self._loaded = frame.sort_values(
            ["date", "ref_area", "flow", "product"], kind="mergesort"
        ).reset_index(drop=True)
        return self._loaded


def _parse_value(raw: str, *, where: str) -> float:
    """One OBS_VALUE cell. A declared missing token becomes NaN, anything odd raises."""
    text = str(raw).strip()
    if text in MISSING_TOKENS:
        return float("nan")
    try:
        return float(text)
    except ValueError as exc:
        raise SourceError(
            "jodi %s: cannot read OBS_VALUE %r as a number. JODI's four known "
            "missing tokens are %s and none of them is defined anywhere in its "
            "manual, so a fifth token must be added to MISSING_TOKENS "
            "deliberately rather than allowed to become a number"
            % (where, raw, ", ".join(sorted(t for t in MISSING_TOKENS if t)))
        ) from exc


# --------------------------------------------------------------------------
# Pivoting
# --------------------------------------------------------------------------

def column_name(area: str, flow: str, product: str) -> str:
    """The cache column for one country, flow and product.

    JODI's own codes, lowercased, in the order country, flow, product, with the
    unit last: be_refinobs_crudeoil_kbd. Nothing in the name is this project's
    invention, which is the point: a reader can take any part of it back to the
    item names guide.
    """
    return "%s_%s_%s_%s" % (area.lower(), flow.lower(), product.lower(), UNIT.lower())


def pivot(
    tidy: pd.DataFrame, keys: Sequence[tuple[str, str]]
) -> tuple[pd.DataFrame, list[dict]]:
    """Turn the tidy extract into one row per month, one column per series.

    Args:
        tidy: the frame JodiRawStore.load returns.
        keys: the (flow, product) pairs this cache carries, in column order.

    Returns:
        (frame, flagged) where frame has

            date                  first of the month, every month between the
                                  first and the last, none skipped
            <cc>_<flow>_<prod>_kbd   one per country per key
            nwe5_<flow>_<prod>_kbd   the five country sum, NaN unless all five
                                  reported
            cells                 how many country level cells the row carries
            cells_code_2          how many of them JODI flags "consult
                                  metadata, use with caution"
            cells_code_3          how many of them JODI has not assessed
            cells_code_4          how many of them JODI has under verification

        and flagged is the list of every cell whose code is not 1, each a dict
        of date, ref_area, flow, product, code and meaning, for the manifest.

    The counts are kept apart by code rather than collapsed into one "not code
    1" column because the codes are categories and not a scale. Code 3 is a
    standing property of a whole line, REFINOBS/TOTCRUDE carries it in every
    month of its life, while code 2 lands on individual recent cells and behaves
    like a provisional flag. One column holding both would make the second
    invisible behind the first.

    Why every month appears even when it is empty. A month JODI covered and
    published nothing for is a hole, and a hole that is simply absent from the
    file is invisible. SPEC.md section 2 rule 1 wants it as NaN, on the record.
    """
    wanted = list(keys)
    if len(tidy):
        pairs = pd.Series(list(zip(tidy["flow"], tidy["product"])), index=tidy.index)
        subset = tidy[pairs.isin(set(wanted))]
    else:
        subset = tidy

    if subset.empty:
        raise SourceError(
            "jodi: the extracts carry none of %s"
            % ", ".join("%s/%s" % pair for pair in wanted)
        )

    span = pd.date_range(subset["date"].min(), subset["date"].max(), freq="MS")
    out = pd.DataFrame({"date": span})

    lookup = {
        (row.date, row.ref_area, row.flow, row.product): (row.value, row.code)
        for row in subset.itertuples(index=False)
    }

    flagged: list[dict] = []
    cells = np.zeros(len(span), dtype="int64")
    by_code = {
        code: np.zeros(len(span), dtype="int64")
        for code in ASSESSMENT_CODES
        if code != "1"
    }

    for flow, product in wanted:
        columns = []
        for area in COUNTRIES:
            values = np.full(len(span), np.nan)
            for position, when in enumerate(span):
                hit = lookup.get((when, area, flow, product))
                if hit is None:
                    continue
                value, code = hit
                if value != value:  # NaN, the source printed a missing token
                    continue
                values[position] = value
                cells[position] += 1
                if code != "1":
                    by_code[code][position] += 1
                    flagged.append(
                        {
                            "date": when.strftime("%Y-%m-%d"),
                            "ref_area": area,
                            "flow": flow,
                            "product": product,
                            "code": code,
                            "meaning": ASSESSMENT_CODES[code],
                        }
                    )
            name = column_name(area, flow, product)
            out[name] = values
            columns.append(name)

        # NaN unless all five reported. A four country sum printed as five would
        # be a hole of up to a fifth of NWE crude demand on the one chart the
        # study is built around, and nothing on the page would show it.
        out[column_name(AGGREGATE, flow, product)] = out[columns].sum(
            axis=1, skipna=False
        )

    out["cells"] = cells
    for code in sorted(by_code):
        out["cells_code_%s" % code] = by_code[code]
    return out, flagged


def _provisional_from(frame: pd.DataFrame) -> str | None:
    """The start of the trailing run of months carrying a code 2 cell.

    CODE 2 ONLY, and the reason is measured. Recon 03 section 1.6 found that in
    the series this study reads every code 2 cell is dated in the newest month,
    so code 2 behaves like a provisional flag on data that has just arrived.
    Code 3 does not: it is a standing property of whole lines, and
    REFINOBS/TOTCRUDE carries it in every month of its life, so a rule that
    counted code 3 would declare the entire total refinery feed series
    provisional from its first month and hide the thing worth seeing.

    JODI does not use the word provisional and this function does not claim it
    does. What it reports is the first month of the unbroken run of "consult
    metadata, use with caution" months at the end of the series, which is the
    nearest thing this source publishes to SPEC.md section 2 rule 5's flag.

    Returns None when the last month carries no code 2 cell at all.
    """
    if frame.empty or "cells_code_2" not in frame.columns:
        return None
    flagged = frame["cells_code_2"].to_numpy()
    if flagged[-1] == 0:
        return None
    start = len(flagged) - 1
    while start > 0 and flagged[start - 1] > 0:
        start -= 1
    return pd.Timestamp(frame["date"].iloc[start]).strftime("%Y-%m-%d")


# --------------------------------------------------------------------------
# The adapters
# --------------------------------------------------------------------------

class JodiSeries(Adapter):
    """Shared behaviour of the three JODI caches.

    A subclass names its keys and its series. The store is passed in so that one
    refresh feeds all three adapters: three independent runs would mean three
    downloads of the same 933 MB, which is the discourtesy recon 03 section 4
    item 2 asks this project not to commit.
    """

    source = "JODI-Oil World Database, International Energy Forum"
    url = DOWNLOADS_PAGE
    page_url = DOWNLOADS_PAGE
    unit = "thousand barrels per day"
    frequency = "monthly"
    method = "published"
    committable = True
    date_col = "date"
    min_rows = MIN_ROWS

    #: (flow, product) pairs, in column order. Set by the subclass.
    keys: tuple[tuple[str, str], ...] = ()

    def __init__(self, store: JodiRawStore | None = None) -> None:
        self.store = store if store is not None else JodiRawStore()
        self.flagged: list[dict] = []
        self.store_report: dict | None = None
        self.licence_note = registered_source(self.name).licence_note

    # -- declarations that depend on the keys -------------------------------

    def value_columns(self) -> list[str]:
        names: list[str] = []
        for flow, product in self.keys:
            for area in COUNTRIES:
                names.append(column_name(area, flow, product))
            names.append(column_name(AGGREGATE, flow, product))
        return names

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.keys:
            return
        columns: list[str] = []
        floors: dict[str, int] = {}
        for flow, product in cls.keys:
            floor = (
                MIN_OBSERVATIONS_LATE
                if (flow, product) in LATE_START_KEYS
                else MIN_OBSERVATIONS_EARLY
            )
            for area in list(COUNTRIES) + [AGGREGATE]:
                name = column_name(area, flow, product)
                columns.append(name)
                floors[name] = floor
        cls.required_cols = tuple(["date"] + columns)
        cls.bounds = {name: BOUNDS_INTAKE_KB_D for name in columns}
        cls.min_observations = dict(floors)

    # -- fetch --------------------------------------------------------------

    def fetch(self) -> pd.DataFrame:
        if self.store_report is None:
            self.store_report = self.store.refresh()
        tidy = self.store.load()
        frame, flagged = pivot(tidy, self.keys)
        self.flagged = flagged
        self.provisional_from = _provisional_from(frame)
        self.vintage = self._vintage()
        self.note = self._note(frame)
        self._check_starts(frame)
        return frame

    def _vintage(self) -> str:
        """The newest Last-Modified the store recorded, as the release date."""
        stamps = [
            record.get("last_modified")
            for record in self.store.read_index()["files"].values()
            if record.get("last_modified")
        ]
        if not stamps:
            return "JODI-Oil World Database, release date not recorded"
        newest = max(stamps, key=_http_date_sort_key)
        return "JODI-Oil World Database, annual CSV files last written %s" % newest

    def _check_starts(self, frame: pd.DataFrame) -> None:
        """Refuse a frame whose history has silently shortened.

        Recon 03 section 1.7 measured the two start dates in all five countries,
        2002-01 for everything and 2009-01 for total refinery feed, jet and
        naphtha. A run that finds a later start has lost years, and losing years
        quietly is how a study ends up claiming a sample it does not have.
        """
        for flow, product in self.keys:
            expected = LATE_START if (flow, product) in LATE_START_KEYS else EARLY_START
            name = column_name(AGGREGATE, flow, product)
            present = frame.loc[frame[name].notna(), "date"]
            if present.empty:
                raise SourceError(
                    "jodi %s: column %s carries no observation at all" % (self.name, name)
                )
            first = present.min().strftime("%Y-%m")
            if first > expected:
                raise SourceError(
                    "jodi %s: %s starts %s, later than the documented %s. Recon "
                    "03 section 1.7 counted %d months in every one of the five "
                    "countries. The history has shortened"
                    % (self.name, name, first, expected, 294 if expected == EARLY_START else 210)
                )

    def _note(self, frame: pd.DataFrame) -> str:
        raise NotImplementedError

    # -- manifest -----------------------------------------------------------

    def _entry(self, *, status: str, frame, note: str) -> dict:
        entry = super()._entry(status=status, frame=frame, note=note)

        counts: dict[str, int] = {code: 0 for code in ASSESSMENT_CODES}
        for cell in self.flagged:
            counts[cell["code"]] = counts.get(cell["code"], 0) + 1
        if frame is not None and "cells" in getattr(frame, "columns", []):
            counts["1"] = int(frame["cells"].sum()) - sum(
                v for k, v in counts.items() if k != "1"
            )

        # Per line, because the picture is per line: code 3 covers whole series
        # for their whole lives while code 2 lands on a handful of recent cells.
        # An aggregate count would hide both facts behind one number.
        by_key: dict[str, dict] = {}
        for flow, product in self.keys:
            label = "%s/%s" % (flow, product)
            hits = [
                cell
                for cell in self.flagged
                if cell["flow"] == flow and cell["product"] == product
            ]
            per_code: dict[str, dict] = {}
            for code in sorted({cell["code"] for cell in hits}):
                dates = sorted(cell["date"] for cell in hits if cell["code"] == code)
                per_code[code] = {
                    "cells": len(dates),
                    "first_date": dates[0],
                    "last_date": dates[-1],
                    "meaning": ASSESSMENT_CODES[code],
                }
            by_key[label] = per_code

        entry["assessment_codes"] = {
            "definitions": dict(ASSESSMENT_CODES),
            "source": ITEM_NAMES_URL,
            "counts": counts,
            "by_key": by_key,
            # Code 2 and code 4 are listed cell by cell because there are few of
            # them and because they are the ones a reader would want to look up.
            # Code 3 is summarised in by_key: listing it cell by cell would put
            # thousands of entries in the manifest to say one sentence, which is
            # that JODI has never assessed that line.
            "flagged_cells": [
                cell for cell in self.flagged if cell["code"] in ("2", "4")
            ],
            "note": (
                "SPEC.md section 5.1 requires JODI's assessment code carried into "
                "the manifest. Every cell of this cache carries one, and the "
                "counts above are over the country level cells only, the nwe5 "
                "columns being this study's sums rather than JODI observations. "
                "THE CODES ARE CATEGORIES AND NOT A SCALE: 3 means the data has "
                "not been assessed, which is not worse than 2, and 3 attaches to "
                "whole lines rather than to recent cells. Code 4 is defined by "
                "JODI and appears nowhere in the 50 files, so it is listed here "
                "and expected to stay at zero rather than arrive one day as an "
                "integer nothing can describe."
            ),
        }
        entry["countries"] = dict(COUNTRY_NAMES)
        entry["flow_definitions"] = {
            code: DEFINITIONS[code] for code in sorted({f for f, _ in self.keys}) if code in DEFINITIONS
        }
        entry["product_names"] = {
            code: PRODUCT_NAMES[code] for code in sorted({p for _, p in self.keys})
        }
        entry["lag_note"] = (
            "JODI publishes around the 20th of each month, on the dates in its own "
            "update calendar, %s. Recon 03 section 1.7 measured the lag at 2 "
            "months and 11 days on 2026-09-11, widening to 2 months and 22 days "
            "the day before a release. SPEC.md section 13 says about two months, "
            "which understates it, and SPEC.md section 7.2 already requires the "
            "runs data date shown separately from the margin data date."
            % UPDATE_CALENDAR_URL
        )
        entry["coverage_note"] = (
            "Everything in this cache runs from %s except total refinery feed, "
            "jet and naphtha, which JODI only began collecting in %s. A study "
            "window advertised as starting in 2002 therefore has no jet line and "
            "no total feed for its first seven years." % (EARLY_START, LATE_START)
        )
        entry["aggregate_rule"] = (
            "nwe5 is the sum of %s and is NaN unless all five reported that "
            "month. A four country sum presented as five would understate NWE "
            "crude demand by up to a fifth with nothing on the page to show it."
            % ", ".join(COUNTRIES)
        )
        entry["revision_note"] = (
            "JODI revises history. Recon 03 found the 2002 file rewritten on "
            "2025-10-21. data/private/jodi_raw/index.json records a sha256 and "
            "the server's Last-Modified for every annual file, so a revision to a "
            "closed year is visible rather than silent."
        )
        if self.store_report is not None:
            entry["fetch_report"] = dict(self.store_report)
        return entry


class JodiRefineryIntake(JodiSeries):
    """Refinery crude intake and total refinery feed, five countries, monthly.

    SPEC.md section 6.1's numerator. Both denominators for SPEC.md section 4.3
    layer 4 are here, side by side, and neither is chosen. See the module
    docstring: refgrout/totprods over refinobs/crudeoil is 1.13 to 1.16, and
    over refinobs/totcrude it is 1.01 to 1.03 but starts in 2009.
    """

    name = SERIES_INTAKE
    keys = (("REFINOBS", "CRUDEOIL"), ("REFINOBS", "TOTCRUDE"))
    observation_column = column_name(AGGREGATE, "REFINOBS", "CRUDEOIL")

    def _note(self, frame: pd.DataFrame) -> str:
        crude = column_name(AGGREGATE, "REFINOBS", "CRUDEOIL")
        feed = column_name(AGGREGATE, "REFINOBS", "TOTCRUDE")
        return (
            "Refinery intake, JODI flow REFINOBS, '%s', for %s, in thousand "
            "barrels per day. TWO DENOMINATORS ARE PUBLISHED HERE AND NEITHER IS "
            "CHOSEN. %s is crude oil only and runs from %s. %s is total refinery "
            "feed, crude plus NGL plus other feedstocks, and runs from %s. "
            "Refinery output over the first is 1.13 to 1.16 because gross output "
            "includes refinery fuel and comes from all feed; over the second it "
            "is 1.01 to 1.03, which is volume gain and is physically right. "
            "Recon 03 section 1.8. SPEC.md section 4.3 layer 4 has not made this "
            "choice, so the analysis gate makes it in the open and the Method "
            "view states it. ONE FACT THAT BEARS ON THAT CHOICE AND IS NOT IN "
            "RECON 03: JODI carries assessment code 3, 'Data has not been "
            "assessed', on every total refinery feed cell in all five countries "
            "for the whole life of the series, while crude only intake is code 1 "
            "almost everywhere. The physically better denominator is the one "
            "JODI has never checked. Both are published here with their codes so "
            "the choice can be made on the evidence. Latest month %s, %d of %d "
            "months carry all five countries on the crude series."
            % (
                DEFINITIONS["REFINOBS"],
                ", ".join(COUNTRIES),
                crude,
                EARLY_START,
                feed,
                LATE_START,
                pd.Timestamp(frame["date"].iloc[-1]).strftime("%Y-%m"),
                int(frame[crude].notna().sum()),
                len(frame),
            )
        )


class JodiRefineryOutput(JodiSeries):
    """Refinery output by product, five countries, monthly.

    SPEC.md section 4.3 layer 4's numerator. TOTPRODS EXCLUDES JETKERO, because
    jet sits inside KEROSENE, so a sum of these columns that includes jetkero
    double counts it. Sum with kerosene.
    """

    name = SERIES_OUTPUT
    keys = (
        ("REFGROUT", "GASOLINE"),
        ("REFGROUT", "GASDIES"),
        ("REFGROUT", "JETKERO"),
        ("REFGROUT", "KEROSENE"),
        ("REFGROUT", "RESFUEL"),
        ("REFGROUT", "NAPHTHA"),
        ("REFGROUT", "TOTPRODS"),
    )
    observation_column = column_name(AGGREGATE, "REFGROUT", "TOTPRODS")

    def _note(self, frame: pd.DataFrame) -> str:
        return (
            "Refinery output by product, JODI flow REFGROUT, '%s', for %s, in "
            "thousand barrels per day. IT IS GROSS OUTPUT, INCLUDING REFINERY "
            "FUEL, FROM ALL REFINERY FEED, so it is not on the same base as "
            "crude intake and the ratio of the two is about 1.14, not 1. "
            "'%s', so category 9, kerosene type jet fuel, is already inside "
            "kerosenes and a sum of these columns that includes jetkero double "
            "counts jet. Sum with kerosene instead: recon 03 checked the "
            "arithmetic and got 5,867.4 against a printed 5,867.0 for 2026-06. "
            "Jet and naphtha start %s, everything else %s. Latest month %s."
            % (
                DEFINITIONS["REFGROUT"],
                ", ".join(COUNTRIES),
                DEFINITIONS["TOTPRODS"],
                LATE_START,
                EARLY_START,
                pd.Timestamp(frame["date"].iloc[-1]).strftime("%Y-%m"),
            )
        )


class JodiCrudeImports(JodiSeries):
    """Crude imports, five countries, monthly.

    SPEC.md section 6.1: shown next to intake as the physical footprint of the
    same demand, with no separate model.
    """

    name = SERIES_IMPORTS
    keys = (("TOTIMPSB", "CRUDEOIL"),)
    observation_column = column_name(AGGREGATE, "TOTIMPSB", "CRUDEOIL")

    def _note(self, frame: pd.DataFrame) -> str:
        total = column_name(AGGREGATE, "TOTIMPSB", "CRUDEOIL")
        return (
            "Crude oil imports, JODI flow TOTIMPSB, '%s', for %s, in thousand "
            "barrels per day, from %s. SPEC.md section 6.1 shows this next to "
            "intake as the physical footprint of the same crude demand and fits "
            "no separate model to it. Imports and intake differ by stock change, "
            "domestic production, backflows and direct use, so they are not two "
            "measurements of one quantity. Latest month %s, %d of %d months carry "
            "all five countries."
            % (
                DEFINITIONS["TOTIMPSB"],
                ", ".join(COUNTRIES),
                EARLY_START,
                pd.Timestamp(frame["date"].iloc[-1]).strftime("%Y-%m"),
                int(frame[total].notna().sum()),
                len(frame),
            )
        )


ADAPTERS = (JodiRefineryIntake, JodiRefineryOutput, JodiCrudeImports)


def _http_date_sort_key(stamp: str):
    for pattern in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S GMT"):
        try:
            return datetime.strptime(stamp, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.min.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    """Refresh the store once and run all three adapters against it."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--policy",
        default="missing",
        choices=list(JodiRawStore.POLICIES),
        help=(
            "none: no network at all. missing: fetch only the years with no "
            "extract on disk, the default. recent: missing plus the two newest "
            "years. verify: ask the server for every file's size with a HEAD and "
            "fetch only the ones that moved, 51 small requests, which is what the "
            "weekly job wants. all: all 50 files, 933 MB"
        ),
    )
    parser.add_argument(
        "--adopt",
        metavar="DIR",
        default=None,
        help=(
            "filter annual files already on this machine out of DIR before "
            "applying the policy, so a copy downloaded once is not downloaded "
            "again. Pair it with --policy verify to date the result against the "
            "server"
        ),
    )
    parser.add_argument("--delay", type=float, default=1.2)
    args = parser.parse_args(list(argv) if argv is not None else None)

    store = JodiRawStore(policy=args.policy, delay=args.delay)
    if args.adopt:
        adopted = store.adopt_local(args.adopt)
        print(
            "adopted %d annual file(s) from %s, skipped %d other file(s)"
            % (len(adopted["adopted"]), adopted["directory"], len(adopted["skipped"]))
        )
    failures = 0
    for factory in ADAPTERS:
        adapter = factory(store)
        try:
            entry = adapter.run()
        except Exception as exc:  # noqa: BLE001, the CLI reports and exits non zero
            print("%s FAILED: %s: %s" % (factory.name, type(exc).__name__, exc))
            failures += 1
            continue
        print(
            "%-36s rows=%-5d %s to %s gaps=%d codes %s status=%s"
            % (
                entry["series"],
                entry["rows"],
                entry["first_date"],
                entry["last_date"],
                len(entry["gaps"]),
                entry["assessment_codes"]["counts"],
                entry["status"],
            )
        )
    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
