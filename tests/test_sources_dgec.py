"""Tests for the DGEC workbook adapters. SPEC.md section 9, parser coverage.

NOTHING HERE TOUCHES THE NETWORK. Every parser runs against a committed fixture
under tests/fixtures, and the two adapters run with their fetch functions
replaced, inside the sandbox fixture from conftest.py so no test can write into
the real data directories.

The anchors themselves are a separate file, tests/test_dgec_anchor.py, because
SPEC.md section 10 makes them a gate on their own and a gate should not be able
to go green because some unrelated parser test was skipped.

The fixtures, and which are captures and which are constructed
---------------------------------------------------------------
A capture is a verbatim slice of what the ministry actually served during the
Gate 1 recon on 2026-09-11. A constructed fixture is written to cover a case that
could not be captured, and it says so. The difference matters: a passing test on
a constructed fixture proves the parser handles what this file imagines, and only
a capture proves it handles what the source sends.

    dgec_landing.html               CAPTURE of the anchor elements. Every <a>
                                    pointing at an xlsx or a pdf, lifted verbatim
                                    from the captured landing page with its href
                                    and its visible label intact, wrapped in a
                                    minimal document. It carries the real
                                    disagreement recon 02 section 1.2 found: the
                                    Brent href ends _0.xlsx while its label does
                                    not, and the MBR label ends _1.xlsx while its
                                    href does not. The _1 URL the label claims
                                    returns HTTP 404. ONE character was changed:
                                    the separator the page prints between file
                                    type and file size is an en dash and is
                                    written as a comma, because SPEC.md section
                                    0.1 forbids en dashes anywhere in this
                                    repository. No assertion reads it, and the
                                    substitution is recorded inside the fixture
                                    as well as here.

    dgec_landing_renamed.html       CONSTRUCTED. The same anchors with the two
                                    workbooks renamed, which is what a page looks
                                    like after the ministry retitles a file. The
                                    adapter must fail loudly and name what it did
                                    find, never fall back to a remembered URL.

    dgec_brent_history.xlsx         CAPTURE, re cut. The real title row, the real
                                    header row, eleven real monthly rows
                                    including every month the anchors need, the
                                    blank spacer, the real MOYENNES ANNUELLES
                                    heading, the eleven real annual rows keyed by
                                    a text year, and the real source line. The
                                    cells are DGEC's, the row selection is ours.

    dgec_mbr_history.xlsx           CAPTURE, re cut the same way, ten monthly
                                    rows, both value columns.

    dgec_mbr_annual_heading_lost.xlsx
                                    CONSTRUCTED. The same file with the MOYENNES
                                    ANNUELLES heading cleared, so the text years
                                    fall inside the monthly block. This is the
                                    SPEC.md section 13 failure the parser exists
                                    to make loud.

    dgec_mbr_columns_swapped.xlsx   CONSTRUCTED. The $/b and EUR/t columns moved,
                                    header cells and values together, which is
                                    what a real column reordering looks like. A
                                    parser reading by position returns euros per
                                    tonne where dollars per barrel were asked
                                    for, a factor of about seven, with no other
                                    symptom.
"""

from __future__ import annotations

import datetime as dt
import io
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

from crack.config import DGEC_BBL_PER_T_BRENT_NOTE, SOURCES
from crack.sources import base, dgec
from crack.sources.base import SourceError

FIXTURES = Path(__file__).resolve().parent / "fixtures"

#: A date well after the last month in every fixture, so provisional_month gives
#: the same answer in 2027 as it does today.
AFTER_THE_FIXTURES = dt.date(2026, 11, 15)


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def shrink_floors(adapter, rows: int):
    """Lower an adapter's size floors so a handful of fixture rows can pass.

    The production floors are 130 rows, because a truncated workbook is the
    failure they exist to catch, and the fixtures are ten. Both floors come down
    together and explicitly: dropping min_observations to zero would turn off the
    guard that stops an all NaN column replacing a good cache.
    """
    adapter.min_rows = int(rows)
    adapter.min_observations = {col: int(rows) for col in adapter.min_observations}
    return adapter


def build_workbook(sheet: str, rows) -> bytes:
    """A small xlsx in memory, for the cases no fixture file is worth keeping."""
    book = openpyxl.Workbook()
    book.active.title = sheet
    for row in rows:
        book.active.append(list(row))
    buffer = io.BytesIO()
    book.save(buffer)
    book.close()
    return buffer.getvalue()


# ==========================================================================
# normalise, the one piece of text handling everything else rests on
# ==========================================================================

def test_normalise_folds_accents_the_euro_sign_and_odd_spaces():
    assert dgec.normalise("COURS MOYENS MENSUELS DU BRENT DATÉ EN $/BARIL") == (
        dgec.BRENT_TITLE_CELL
    )
    assert dgec.normalise("en €/t") == dgec.UNIT_EUR_T
    assert dgec.normalise("en $/b") == dgec.UNIT_USD_BBL
    # The narrow no break space the notes use as a thousands separator, and the
    # no break space French typography puts before a colon.
    assert dgec.normalise("1 349") == "1 349"
    assert dgec.normalise("Source : Reuters / DGEC") == "source : reuters / dgec"
    assert dgec.normalise(None) == ""


def test_normalise_is_not_a_fuzzy_match():
    # The difference that told recon 02 section 3.3 the weekly note had changed
    # layout was exactly this one: "Moyenne hebdomadaire" against "Moyennes
    # hebdomadaires". A normalisation that swallowed it would have hidden a
    # column count change.
    assert dgec.normalise("Moyenne mensuelle") != dgec.MONTHLY_BLOCK_LABEL
    assert dgec.normalise("Moyennes mensuelles") == dgec.MONTHLY_BLOCK_LABEL
    # The currency sign is rewritten, never dropped, so a euro unit cannot match
    # a dollar one.
    assert dgec.normalise("en €/t") != dgec.normalise("en $/t")


# ==========================================================================
# Link discovery. The href is authoritative and the label is not.
# ==========================================================================

def test_discovery_finds_both_workbooks_on_the_captured_page():
    html = fixture_bytes("dgec_landing.html")
    brent = dgec.discover_workbook_url(html, dgec.BRENT_DOCUMENT_TITLE)
    mbr = dgec.discover_workbook_url(html, dgec.MBR_DOCUMENT_TITLE)
    assert brent.endswith("%29_0.xlsx")
    assert mbr.endswith("%29.xlsx")
    assert brent != mbr
    assert brent.startswith("https://www.ecologie.gouv.fr/sites/default/files/")


def test_discovery_follows_the_href_and_ignores_the_visible_label():
    """The failure recon 02 section 1.2 measured, in both directions.

    On the captured page the MBR link's visible label ends _1.xlsx while its href
    carries no suffix, and the _1 URL returns HTTP 404. The Brent link is the
    other way round. A discovery keyed on the label would fetch a 404 for one and
    the wrong spelling for the other.
    """
    html = fixture_bytes("dgec_landing.html").decode("utf-8")
    assert "moyennes mensuelles)_1.xlsx" in html  # the label, as served
    mbr = dgec.discover_workbook_url(html, dgec.MBR_DOCUMENT_TITLE)
    assert "_1.xlsx" not in mbr
    assert "%28moyennes%20mensuelles%29.xlsx" in mbr


def test_discovery_tolerates_a_suffix_that_moves():
    """The Drupal counter is assigned at upload time and has changed three times.

    Wayback holds these files under _0, _1 and no suffix at all over two years,
    recon 02 section 1.5, so the title has to match with the counter stripped.
    """
    base_href = (
        "/sites/default/files/documents/Historique%20du%20cours%20du%20Brent"
        "%20depuis%202015%20%28moyennes%20mensuelles%29"
    )
    for suffix in ("", "_0", "_1", "_17"):
        html = '<a href="%s%s.xlsx">whatever</a>' % (base_href, suffix)
        url = dgec.discover_workbook_url(html, dgec.BRENT_DOCUMENT_TITLE)
        assert url.endswith("%s%s.xlsx" % (base_href, suffix))


def test_discovery_raises_when_the_file_is_renamed_and_says_what_it_saw():
    with pytest.raises(SourceError) as caught:
        dgec.discover_workbook_url(
            fixture_bytes("dgec_landing_renamed.html"), dgec.MBR_DOCUMENT_TITLE
        )
    message = str(caught.value)
    # It names what it did find, so the log alone diagnoses it.
    assert "marge brute mensuelle" in message
    assert "cours du brent mensuel" in message
    assert "404" in message


def test_discovery_refuses_two_candidates_rather_than_picking_one():
    html = (
        '<a href="/a/Historique%20du%20cours%20du%20Brent%20depuis%202015'
        '%20%28moyennes%20mensuelles%29.xlsx">one</a>'
        '<a href="/b/Historique%20du%20cours%20du%20Brent%20depuis%202015'
        '%20%28moyennes%20mensuelles%29_2.xlsx">two</a>'
    )
    with pytest.raises(SourceError, match="Picking one would be a guess"):
        dgec.discover_workbook_url(html, dgec.BRENT_DOCUMENT_TITLE)


def test_discovery_does_not_match_a_pdf_under_the_same_title():
    html = (
        '<a href="/x/Historique%20du%20cours%20du%20Brent%20depuis%202015'
        '%20%28moyennes%20mensuelles%29.pdf">a pdf</a>'
    )
    with pytest.raises(SourceError, match="no .xlsx link"):
        dgec.discover_workbook_url(html, dgec.BRENT_DOCUMENT_TITLE)


# ==========================================================================
# The parsers
# ==========================================================================

def test_brent_workbook_parses_to_the_cache_layout():
    frame = dgec.parse_brent_workbook(FIXTURES / "dgec_brent_history.xlsx")
    assert list(frame.columns) == [
        "date",
        dgec.COLUMN_BRENT_USD_BBL,
        dgec.COLUMN_BRENT_USD_T,
    ]
    assert frame["date"].iloc[0] == pd.Timestamp("2015-01-01")
    assert frame["date"].iloc[-1] == pd.Timestamp("2026-08-01")
    # Full float precision, not the rounded figure the note prints.
    assert frame[dgec.COLUMN_BRENT_USD_BBL].iloc[0] == 47.7080952380952
    assert frame[dgec.COLUMN_BRENT_USD_BBL].iloc[-1] == 91.076


def test_mbr_workbook_parses_both_units():
    frame = dgec.parse_mbr_workbook(FIXTURES / "dgec_mbr_history.xlsx")
    assert list(frame.columns) == [
        "date",
        dgec.COLUMN_MBR_USD_BBL,
        dgec.COLUMN_MBR_EUR_T,
    ]
    indexed = frame.set_index("date")
    assert indexed[dgec.COLUMN_MBR_USD_BBL].loc[pd.Timestamp("2015-01-01")] == 6.987702
    assert indexed[dgec.COLUMN_MBR_EUR_T].loc[pd.Timestamp("2015-01-01")] == 45.2530904


def test_the_annual_averages_block_never_reaches_the_monthly_series():
    """The trap recon 02 sections 1.3 and 1.4 documented.

    The annual rows are keyed by a year written as text. '2015' coerced by a
    pandas default becomes 2015-01-01 and collides with the real January 2015
    row, so the series would silently gain eleven annual averages.
    """
    frame = dgec.parse_brent_workbook(FIXTURES / "dgec_brent_history.xlsx")
    # Eleven monthly rows in the fixture, eleven annual rows below them.
    assert len(frame) == 11
    assert not frame["date"].duplicated().any()
    assert (frame["date"].dt.day == 1).all()
    # The annual average for 2015 is 52.354, and it must not be anywhere here.
    assert not (frame[dgec.COLUMN_BRENT_USD_BBL].round(3) == 52.354).any()


def test_losing_the_annual_heading_stops_the_parse_rather_than_coercing():
    """SPEC.md section 13: a layout change must break loudly.

    With the heading gone the text years land inside the monthly block. The
    parser must name the offending cell, not skip it: a parser that silently
    drops rows it does not understand cannot tell a layout change from an empty
    file.
    """
    with pytest.raises(SourceError) as caught:
        dgec.parse_mbr_workbook(FIXTURES / "dgec_mbr_annual_heading_lost.xlsx")
    message = str(caught.value)
    assert "'2015'" in message
    assert "not a date" in message
    assert "ANNUAL" in message


def test_the_columns_are_found_by_unit_label_and_not_by_position():
    """The SPEC.md section 13 failure made real on the MBR sheet.

    $/b and EUR/t are adjacent, they differ by a factor of about seven, and
    reading the wrong one has no other symptom. In the swapped fixture the header
    cells and the values move together, which is what a real column reordering
    looks like, and the parser must return exactly the same frame.
    """
    straight = dgec.parse_mbr_workbook(FIXTURES / "dgec_mbr_history.xlsx")
    swapped = dgec.parse_mbr_workbook(FIXTURES / "dgec_mbr_columns_swapped.xlsx")
    pd.testing.assert_frame_equal(straight, swapped)
    # And the values really are far apart, so the test is not vacuous.
    assert (
        straight[dgec.COLUMN_MBR_EUR_T] / straight[dgec.COLUMN_MBR_USD_BBL]
    ).min() > 5


def test_a_missing_unit_label_stops_the_parse():
    payload = build_workbook(
        dgec.MBR_SHEET,
        [
            [None, "MARGE BRUTE DE RAFFINAGE SUR BRENT"],
            ["Moyennes mensuelles", "en $/b", "en c€/l"],
            [dt.datetime(2015, 1, 1), 6.987702, 4.1],
            ["MOYENNES ANNUELLES", None, None],
        ],
    )
    with pytest.raises(SourceError) as caught:
        dgec.parse_mbr_workbook(payload)
    message = str(caught.value)
    assert dgec.UNIT_EUR_T in message
    assert "never by position" in message


def test_the_wrong_table_under_the_right_filename_is_refused():
    payload = build_workbook(
        dgec.BRENT_SHEET,
        [
            [None, "PRIX HTT ET TTC DEPUIS JANVIER 2020"],
            ["Moyennes mensuelles", "en $/b"],
            [dt.datetime(2015, 1, 1), 47.7],
        ],
    )
    with pytest.raises(SourceError, match="no cell in the first rows"):
        dgec.parse_brent_workbook(payload)


def test_the_wrong_sheet_name_is_refused_and_the_sheets_are_listed():
    payload = build_workbook("Feuil1", [[None, "MARGE BRUTE DE RAFFINAGE SUR BRENT"]])
    with pytest.raises(SourceError) as caught:
        dgec.parse_mbr_workbook(payload)
    assert "Feuil1" in str(caught.value)


def test_an_html_error_page_served_as_an_xlsx_is_refused():
    with pytest.raises(SourceError, match="did not open as an xlsx"):
        dgec.parse_brent_workbook(b"<!doctype html><html><body>404</body></html>")


def test_a_re_cut_workbook_that_starts_later_is_refused():
    payload = build_workbook(
        dgec.BRENT_SHEET,
        [
            [None, "COURS MOYENS MENSUELS DU BRENT DATÉ EN $/BARIL"],
            ["Moyennes mensuelles", "en $/b"],
            [dt.datetime(2020, 1, 1), 63.6],
            [dt.datetime(2020, 2, 1), 55.7],
            ["MOYENNES ANNUELLES", None],
        ],
    )
    with pytest.raises(SourceError, match="re cut"):
        dgec.parse_brent_workbook(payload)


def test_an_empty_cell_becomes_nan_and_never_zero():
    """SPEC.md non negotiable 1. A margin of zero dollars is a real statement."""
    payload = build_workbook(
        dgec.MBR_SHEET,
        [
            [None, "MARGE BRUTE DE RAFFINAGE SUR BRENT"],
            ["Moyennes mensuelles", "en $/b", "en €/t"],
            [dt.datetime(2015, 1, 1), 6.987702, 45.2530904],
            [dt.datetime(2015, 2, 1), None, None],
            ["MOYENNES ANNUELLES", None, None],
        ],
    )
    frame = dgec.parse_mbr_workbook(payload)
    assert len(frame) == 2
    assert pd.isna(frame[dgec.COLUMN_MBR_USD_BBL].iloc[1])
    assert not (frame[dgec.COLUMN_MBR_USD_BBL].fillna(-1) == 0).any()


def test_a_french_decimal_comma_is_read_and_a_word_is_not():
    payload = build_workbook(
        dgec.MBR_SHEET,
        [
            [None, "MARGE BRUTE DE RAFFINAGE SUR BRENT"],
            ["Moyennes mensuelles", "en $/b", "en €/t"],
            [dt.datetime(2015, 1, 1), "6,987702", "45,2530904"],
            ["MOYENNES ANNUELLES", None, None],
        ],
    )
    frame = dgec.parse_mbr_workbook(payload)
    assert frame[dgec.COLUMN_MBR_USD_BBL].iloc[0] == 6.987702

    broken = build_workbook(
        dgec.MBR_SHEET,
        [
            [None, "MARGE BRUTE DE RAFFINAGE SUR BRENT"],
            ["Moyennes mensuelles", "en $/b", "en €/t"],
            [dt.datetime(2015, 1, 1), "non disponible", 45.25],
            ["MOYENNES ANNUELLES", None, None],
        ],
    )
    with pytest.raises(SourceError, match="cannot read"):
        dgec.parse_mbr_workbook(broken)


def test_a_mid_month_date_is_refused():
    payload = build_workbook(
        dgec.BRENT_SHEET,
        [
            [None, "COURS MOYENS MENSUELS DU BRENT DATÉ EN $/BARIL"],
            ["Moyennes mensuelles", "en $/b"],
            [dt.datetime(2015, 1, 15), 47.7],
            ["MOYENNES ANNUELLES", None],
        ],
    )
    with pytest.raises(SourceError, match="not the first of a month"):
        dgec.parse_brent_workbook(payload)


def test_the_header_units_actually_present_are_recorded():
    """So that a c EUR/l column appearing one day is visible in the manifest.

    SPEC.md section 5.1 expects three units and this workbook carries two,
    recon 02 section 1.4. UNITS_NOT_IN_FILE says so in words; this is the part a
    reader can check.
    """
    frame = dgec.parse_mbr_workbook(FIXTURES / "dgec_mbr_history.xlsx")
    assert frame.attrs["header_units"] == [dgec.UNIT_USD_BBL, dgec.UNIT_EUR_T]
    assert "en c eur/l" not in frame.attrs["header_units"]


# ==========================================================================
# The derived $/t column, and the two factors that must never be swapped
# ==========================================================================

def test_the_usd_t_column_uses_the_note_factor_and_reproduces_the_printed_page():
    """Recon 02 section 4.3 measured 7.5 bbl/t on five printed month pairs.

    Every one of them is in this fixture, so the check is against the ministry's
    own printed figures and not against arithmetic this project invented.
    """
    frame = dgec.parse_brent_workbook(FIXTURES / "dgec_brent_history.xlsx")
    indexed = frame.set_index("date")[dgec.COLUMN_BRENT_USD_T].round()
    printed = {
        "2026-08-01": 683,  # NPG-2026.09.04, column aout-26
        "2026-03-01": 774,  # NPG-2026.04.17, column mars-26
        "2026-02-01": 532,  # NPG-2026.03.20 and NPG-2026.03.27
        "2025-11-01": 479,  # NPG-2025.12.19, column nov.-25
        "2026-07-01": 628,  # SPEC.md section 5.5
    }
    for month, expected in printed.items():
        assert indexed.loc[pd.Timestamp(month)] == expected, month


def test_the_two_dgec_factors_are_still_different():
    """crack.config raises at import if they are collapsed. Asserted here too.

    Using 7.55 where 7.5 belongs is a 0.67 percent error on the crude leg, about
    0.56 $/bbl at a Brent of 84, and it would be silent.
    """
    from crack.config import DGEC_BBL_PER_T_BRENT_MARGIN

    assert DGEC_BBL_PER_T_BRENT_NOTE == 7.5
    assert DGEC_BBL_PER_T_BRENT_MARGIN == 7.55


# ==========================================================================
# Provisional
# ==========================================================================

def test_a_complete_last_month_is_not_flagged_provisional():
    """The workbooks publish complete months, so the usual answer is None.

    Flagging a final figure provisional is its own kind of lie: the site prints
    the flag, and a permanent flag would train a reader to ignore it.
    """
    assert dgec.provisional_month("2026-08-01", dt.date(2026, 9, 12)) is None
    assert dgec.provisional_month("2026-07-01", dt.date(2026, 9, 12)) is None


def test_the_month_the_fetch_happens_in_is_flagged_provisional():
    """The one circumstance where the workbook could carry an incomplete month.

    Recon 02 section 3.5 measured a 2 $/b revision on a provisional August 2024
    between two notes, so the flag has to exist even though these files have not
    yet used it.
    """
    assert dgec.provisional_month("2026-09-01", dt.date(2026, 9, 12)) == "2026-09-01"
    assert dgec.provisional_month("2026-12-01", dt.date(2026, 12, 1)) == "2026-12-01"


# ==========================================================================
# The adapters end to end, with the network replaced
# ==========================================================================

def _run(adapter_class, monkeypatch, fetch_name, fixture, url, rows):
    """Run one adapter with its fetch function replaced by a fixture."""
    adapter = adapter_class(today=AFTER_THE_FIXTURES)
    parse = {
        "fetch_brent": dgec.parse_brent_workbook,
        "fetch_mbr": dgec.parse_mbr_workbook,
    }[fetch_name]

    def fake(*, delay=1.0):
        return parse(FIXTURES / fixture), url, "Mon, 07 Sep 2026 08:10:35 GMT"

    monkeypatch.setattr(dgec, fetch_name, fake)
    return shrink_floors(adapter, rows).run()


BRENT_URL = (
    "https://www.ecologie.gouv.fr/sites/default/files/documents/"
    "Historique%20du%20cours%20du%20Brent%20depuis%202015%20"
    "%28moyennes%20mensuelles%29_0.xlsx"
)
MBR_URL = (
    "https://www.ecologie.gouv.fr/sites/default/files/documents/"
    "Historique%20de%20la%20marge%20brute%20de%20raffinage%20sur%20Brent%20"
    "depuis%202015%20%28moyennes%20mensuelles%29.xlsx"
)


def test_brent_adapter_writes_a_cache_and_a_manifest_entry(sandbox, monkeypatch):
    entry = _run(dgec.DgecBrentMonthly, monkeypatch, "fetch_brent",
                 "dgec_brent_history.xlsx", BRENT_URL, 11)
    assert entry["status"] == "ok"
    assert entry["rows"] == 11
    assert entry["first_date"] == "2015-01-01"
    assert entry["last_date"] == "2026-08-01"
    assert entry["frequency"] == "monthly"
    assert entry["method"] == "published"
    assert entry["committable"] is True
    assert entry["file"] == "data/cache/dgec_brent_monthly.csv"
    # The URL recorded is the one actually used, not the landing page.
    assert entry["url"] == BRENT_URL
    assert entry["discovered_url"] == BRENT_URL
    assert entry["page_url"] == dgec.LANDING_PAGE
    assert entry["vintage"].startswith("Historique du cours du Brent")
    assert "last month 2026-08" in entry["vintage"]
    assert "Last-Modified" in entry["vintage"]
    assert entry["provisional_from"] is None
    # The derived column declares itself where the data is, not only in prose.
    derived = entry["derived_columns"][0]
    assert derived["column"] == dgec.COLUMN_BRENT_USD_T
    assert derived["factor_bbl_per_t"] == DGEC_BBL_PER_T_BRENT_NOTE

    written = base.read_cache(dgec.SERIES_BRENT, directory="cache")
    assert list(written.columns) == [
        "date",
        dgec.COLUMN_BRENT_USD_BBL,
        dgec.COLUMN_BRENT_USD_T,
    ]
    assert len(written) == 11


def test_mbr_adapter_carries_the_facts_the_provenance_panel_needs(sandbox, monkeypatch):
    entry = _run(dgec.DgecMbrMonthly, monkeypatch, "fetch_mbr",
                 "dgec_mbr_history.xlsx", MBR_URL, 10)
    assert entry["status"] == "ok"
    assert entry["rows"] == 10
    assert entry["unit"] == "USD per barrel and EUR per tonne"
    assert entry["licence"] == "Licence Ouverte 2.0 (Etalab)"
    assert "DGEC" in entry["attribution"]
    # SPEC.md section 4.3 wants the method change marked. The honest answer is
    # that there is no break inside the published window, and it is carried where
    # the data is rather than asserted in prose somewhere else.
    assert entry["method_change"]["break_inside_the_published_window"] is False
    assert entry["method_change"]["detailed_method_in_force_from"] == "2016-01-01"
    # The two facts that would otherwise surprise a reader of this series.
    assert "note" in entry["note_leads_file"].lower()
    assert "centimes per litre" in entry["units_not_in_file"]
    assert "0.50 $/bbl" in entry["replication_note"]
    assert entry["header_units"] == [dgec.UNIT_USD_BBL, dgec.UNIT_EUR_T]


def test_a_failed_fetch_keeps_the_previous_cache_and_marks_the_series_failed(
    sandbox, monkeypatch
):
    """SPEC.md section 5.4. The whole point of the Adapter contract."""
    _run(dgec.DgecMbrMonthly, monkeypatch, "fetch_mbr",
         "dgec_mbr_history.xlsx", MBR_URL, 10)
    good = base.read_cache(dgec.SERIES_MBR, directory="cache")
    assert len(good) == 10

    def explode(*, delay=1.0):
        raise SourceError("the ministry served an HTML error page")

    monkeypatch.setattr(dgec, "fetch_mbr", explode)
    adapter = shrink_floors(dgec.DgecMbrMonthly(today=AFTER_THE_FIXTURES), 10)
    with pytest.raises(SourceError):
        adapter.run()

    kept = base.read_cache(dgec.SERIES_MBR, directory="cache")
    pd.testing.assert_frame_equal(good, kept)

    recorded = [
        e
        for e in base.manifest_read()["series"]
        if e["series"] == dgec.SERIES_MBR
    ][0]
    assert recorded["status"] == "failed"
    assert "HTML error page" in recorded["note"]
    # The manifest still describes the cache that is on disk, not an empty one.
    assert recorded["rows"] == 10


def test_a_shrunken_workbook_cannot_replace_a_good_cache(sandbox, monkeypatch):
    _run(dgec.DgecBrentMonthly, monkeypatch, "fetch_brent",
         "dgec_brent_history.xlsx", BRENT_URL, 11)

    truncated = dgec.parse_brent_workbook(FIXTURES / "dgec_brent_history.xlsx").head(4)

    def fake(*, delay=1.0):
        return truncated, BRENT_URL, ""

    monkeypatch.setattr(dgec, "fetch_brent", fake)
    adapter = shrink_floors(dgec.DgecBrentMonthly(today=AFTER_THE_FIXTURES), 4)
    with pytest.raises(SourceError, match="row count shrank"):
        adapter.run()
    assert len(base.read_cache(dgec.SERIES_BRENT, directory="cache")) == 11


# ==========================================================================
# The registry, which the Adapter base class also cross checks
# ==========================================================================

@pytest.mark.parametrize("series", [dgec.SERIES_BRENT, dgec.SERIES_MBR])
def test_the_adapter_and_the_registry_agree(series):
    registered = SOURCES[series]
    adapter = {
        dgec.SERIES_BRENT: dgec.DgecBrentMonthly,
        dgec.SERIES_MBR: dgec.DgecMbrMonthly,
    }[series]
    assert adapter.frequency == registered.frequency
    assert adapter.method == registered.method
    assert adapter.committable == registered.committable
    assert adapter.page_url == registered.page_url
    # machine_url is None on purpose: the URL has to be discovered every time.
    assert registered.machine_url is None
    # Both registry notes say to read the href off the landing page, which is
    # what this module does and what the label cannot be trusted for.
    assert "href" in registered.url_note


def test_the_landing_page_cache_is_used_once_and_can_be_cleared(monkeypatch):
    """Both series live on one page, so one run asks for it once.

    SPEC.md section 5.4 asks for a polite delay and one request per file. Two
    adapters refetching the same HTML in the same run would be rude for no gain,
    and the memo is short enough that it cannot hide an edition change.
    """
    calls = []

    class _Response:
        content = b"<html></html>"

    def fake_get(url, **kwargs):
        calls.append(url)
        return _Response()

    monkeypatch.setattr(dgec, "http_get", fake_get)
    dgec.clear_landing_cache()
    try:
        first = dgec.fetch_landing_page(delay=0)
        second = dgec.fetch_landing_page(delay=0)
        assert first == second == b"<html></html>"
        assert calls == [dgec.LANDING_PAGE]
        dgec.clear_landing_cache()
        dgec.fetch_landing_page(delay=0)
        assert len(calls) == 2
    finally:
        dgec.clear_landing_cache()


def test_an_empty_landing_page_is_a_failure(monkeypatch):
    class _Empty:
        content = b""

    monkeypatch.setattr(dgec, "http_get", lambda url, **kwargs: _Empty())
    dgec.clear_landing_cache()
    try:
        with pytest.raises(SourceError, match="came back empty"):
            dgec.fetch_landing_page(delay=0)
    finally:
        dgec.clear_landing_cache()
