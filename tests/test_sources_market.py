"""Tests for the market data adapters: fred, eia, worldbank and yahoo.

NOTHING HERE TOUCHES THE NETWORK. Every parser is exercised against a committed
fixture under tests/fixtures, and every adapter is exercised with its fetch
function replaced, inside the sandbox fixture from conftest.py so no test can
write into the real data directories.

The fixtures, and which of them are captures and which are constructed
----------------------------------------------------------------------
A capture is a verbatim slice of a file a source actually served during the Gate
1 recon on 2026-09-11 or 2026-09-12. A constructed fixture is written here to
cover a case that could not be captured, and it says so. The difference matters:
a test that passes against a constructed fixture proves the parser handles what
this file imagines, and only a capture proves it handles what the source sends.

    fred_brent_sample.csv           CAPTURE. Rows 2025-12-19 to 2026-07-10 of
                                    fredgraph.csv?id=DCOILBRENTEU, header
                                    included, byte for byte. Carries three
                                    blank days: 2025-12-25, 2025-12-26 and
                                    2026-01-01.

    fred_eurusd_sample.csv          CAPTURE. The same date window of
                                    fredgraph.csv?id=DEXUSEU. Carries blanks on
                                    2025-12-25, 2026-01-01, 2026-06-19 and
                                    2026-07-03, which is a DIFFERENT set from
                                    Brent's, and that is the point of the pair.

    fred_brent_dot_convention.csv   CONSTRUCTED. Seven of the captured rows with
                                    the blank written as "." instead. SPEC.md
                                    section 5.1 describes the dot convention and
                                    the current endpoint does not use it, so a
                                    real dot row could not be captured from this
                                    source at all. The parser accepts both.

    fred_brent_bad_header.csv       CONSTRUCTED. The captured rows under a value
                                    column headed BRENT_EUROPE instead of
                                    DCOILBRENTEU, which is what a position based
                                    parser would sail straight past.

    worldbank_cmo_landing.html      CAPTURE of the anchor elements. Every <a>
                                    element pointing at an xlsx or a pdf, lifted
                                    verbatim from the captured landing page and
                                    wrapped in a minimal document. The markup of
                                    the links is the source's, the page around
                                    them is not.

    worldbank_cmo_landing_rotted.html
                                    CONSTRUCTED. The same anchors with the
                                    monthly workbook link replaced by the legacy
                                    pubdocs.worldbank.org URL recon 04 section
                                    4.1 found returning HTTP 404. This is what a
                                    rotted page looks like and the adapter must
                                    fail loudly on it.

    worldbank_monthly_prices.xlsx   CAPTURE, re cut. Rows 1 to 6 of the real
                                    'Monthly Prices' sheet, columns A to K, plus
                                    eleven real data rows: the first two months
                                    of the file, the six months either side of
                                    the April 2015 definition change, and the
                                    last three. The cells are the workbook's own,
                                    the row selection is this file's.

    yahoo_ttf_history.csv           CAPTURE. Sessions 2026-08-20 to 2026-09-11
                                    of the yfinance history frame for TTF=F,
                                    saved with its tz aware Date column intact.

    yahoo_ttf_chart.json            CAPTURE, taken 2026-09-12 from
                                    query1.finance.yahoo.com/v8/finance/chart/
                                    TTF=F?period1=1786665600&period2=1789171200
                                    &interval=1d. Twenty sessions, 2026-08-14 to
                                    2026-09-11.

The EIA workbook has no committed fixture and its parser test skips
--------------------------------------------------------------------
RBRTEd.xls is a legacy .xls. Writing one needs xlwt, which is not installed and
is not worth a dependency for a fixture, and the real file is half a megabyte.
So test_eia_parses_the_probe_workbook reads the recon probe copy when it is
there and SKIPS when it is not. On a fresh checkout that test does not run. It is
recorded here rather than dressed up as coverage.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import openpyxl
import pandas as pd
import pytest

from crack.sources import base, eia, fred, worldbank, yahoo
from crack.sources.base import SourceError

FIXTURES = Path(__file__).resolve().parent / "fixtures"

#: The recon probe archive. Gitignored, present only on the machine the Gate 1
#: research ran on. Tests that need it skip when it is absent.
PROBE = Path(__file__).resolve().parents[1] / "data" / "private" / "probe"

#: A moment after the last session in every fixture, on the exchange clock.
#: Passed anywhere the wall clock would otherwise be read, so these tests give
#: the same answer in 2027.
AFTER_THE_FIXTURES = dt.datetime(
    2026, 9, 12, 12, 0, tzinfo=ZoneInfo("America/New_York")
)


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def shrink_floors(adapter, rows: int, observations: int | None = None):
    """Lower an adapter's size floors so a handful of fixture rows can pass.

    The production floors are thousands of rows, because a truncated response is
    the failure they exist to catch. A fixture is twenty sessions. Both floors
    have to come down together and they have to come down explicitly: dropping
    min_observations to zero would turn off the guard that stops an all NaN
    column replacing a good cache, in every test that runs an adapter.
    """
    adapter.min_rows = int(rows)
    floor = int(rows if observations is None else observations)
    adapter.min_observations = {col: floor for col in adapter.min_observations}
    return adapter


# ==========================================================================
# FRED, the CSV parser
# ==========================================================================

def test_fred_reads_the_observation_date_header_not_DATE():
    # SPEC.md section 5.1 was written when the first column was headed DATE.
    # Recon 04 section 1.3 read the current file: it is observation_date. Both
    # are accepted, and the value column is matched against the series id.
    frame = fred.parse_csv(
        fixture_bytes("fred_brent_sample.csv"),
        series_id="DCOILBRENTEU",
        column="brent_usd_bbl",
    )
    assert list(frame.columns) == ["date", "brent_usd_bbl"]
    assert fixture_text("fred_brent_sample.csv").splitlines()[0] == (
        "observation_date,DCOILBRENTEU"
    )
    assert frame["date"].iloc[0] == pd.Timestamp("2025-12-19")
    assert frame["date"].iloc[-1] == pd.Timestamp("2026-07-10")


def test_fred_accepts_the_older_DATE_spelling():
    text = "DATE,DCOILBRENTEU\n2026-01-02,61.98\n2026-01-05,63.00\n"
    frame = fred.parse_csv(text, series_id="DCOILBRENTEU", column="brent_usd_bbl")
    assert len(frame) == 2
    assert frame["brent_usd_bbl"].tolist() == [61.98, 63.00]


def test_fred_empty_field_becomes_nan_and_never_zero():
    # The failure this test exists for: a blank coerced to 0.0 would be a Brent
    # print of zero dollars on Christmas Day, which SPEC.md section 2 rule 1
    # forbids outright, and it would pass every bounds check that ignores NaN.
    frame = fred.parse_csv(
        fixture_bytes("fred_brent_sample.csv"),
        series_id="DCOILBRENTEU",
        column="brent_usd_bbl",
    )
    indexed = frame.set_index("date")["brent_usd_bbl"]
    blanks = [
        "2025-12-25",  # Christmas Day
        "2025-12-26",  # Boxing Day, a UK bank holiday and not a US one
        "2026-01-01",
        "2026-04-03",  # Good Friday
        "2026-04-06",  # Easter Monday
        "2026-05-04",  # early May bank holiday
        "2026-05-25",  # spring bank holiday
    ]
    for blank in blanks:
        assert math.isnan(indexed.loc[pd.Timestamp(blank)]), blank
    # The row is kept, so the hole is visible in the file rather than invisible
    # in a shorter frame.
    assert pd.Timestamp("2025-12-25") in indexed.index
    assert not (indexed == 0).any()
    assert int(indexed.notna().sum()) == len(frame) - len(blanks)


def test_fred_dot_convention_becomes_nan_too():
    frame = fred.parse_csv(
        fixture_bytes("fred_brent_dot_convention.csv"),
        series_id="DCOILBRENTEU",
        column="brent_usd_bbl",
    )
    indexed = frame.set_index("date")["brent_usd_bbl"]
    assert math.isnan(indexed.loc[pd.Timestamp("2025-12-25")])
    assert math.isnan(indexed.loc[pd.Timestamp("2025-12-26")])
    assert indexed.loc[pd.Timestamp("2025-12-29")] == 63.10


def test_fred_refuses_a_header_that_does_not_name_the_series():
    with pytest.raises(SourceError) as caught:
        fred.parse_csv(
            fixture_bytes("fred_brent_bad_header.csv"),
            series_id="DCOILBRENTEU",
            column="brent_usd_bbl",
        )
    message = str(caught.value)
    assert "DCOILBRENTEU" in message
    # The message names what it actually saw, so the log alone diagnoses it.
    assert "BRENT_EUROPE" in message


def test_fred_refuses_html_and_refuses_an_empty_body():
    with pytest.raises(SourceError, match="HTML"):
        fred.parse_csv(
            "<!doctype html><html><body>error</body></html>",
            series_id="DCOILBRENTEU",
            column="brent_usd_bbl",
        )
    with pytest.raises(SourceError, match="empty"):
        fred.parse_csv("   ", series_id="DCOILBRENTEU", column="brent_usd_bbl")


def test_fred_refuses_a_duplicate_date_and_an_unreadable_value():
    with pytest.raises(SourceError, match="duplicate"):
        fred.parse_csv(
            "observation_date,DEXUSEU\n2026-01-02,1.17\n2026-01-02,1.18\n",
            series_id="DEXUSEU",
            column="eurusd",
        )
    with pytest.raises(SourceError, match="cannot read"):
        fred.parse_csv(
            "observation_date,DEXUSEU\n2026-01-02,1 174\n",
            series_id="DEXUSEU",
            column="eurusd",
        )


def test_fred_sends_the_project_token_to_fred_and_the_browser_string_elsewhere():
    # Trap 3. Recon 04 section 1.2 measured a connection reset from a browser
    # user agent on this host. The choice lives in base.http_get, and this test
    # asserts it without a network call so a future edit cannot quietly undo it.
    assert base.user_agent_for(fred.csv_url("DCOILBRENTEU")) == base.PROJECT_USER_AGENT
    assert base.user_agent_for(fred.csv_url("DEXUSEU")) == base.PROJECT_USER_AGENT
    assert base.user_agent_for(yahoo.CHART_URL) == base.USER_AGENT


# ==========================================================================
# FRED, the two calendars
# ==========================================================================

@pytest.fixture(scope="module")
def fred_pair() -> tuple[pd.DataFrame, pd.DataFrame]:
    brent = fred.parse_csv(
        fixture_bytes("fred_brent_sample.csv"),
        series_id="DCOILBRENTEU",
        column="brent_usd_bbl",
    )
    eurusd = fred.parse_csv(
        fixture_bytes("fred_eurusd_sample.csv"),
        series_id="DEXUSEU",
        column="eurusd",
    )
    return brent, eurusd


def test_the_two_fred_series_keep_different_holiday_calendars(fred_pair):
    # This is the trap that would otherwise turn up as a wrong gas cost on a
    # random Friday. Brent blanks on UK and European bank holidays, EUR/USD on
    # the US federal calendar, and about one business day in twenty carries one
    # leg and not the other.
    brent, eurusd = fred_pair
    counts = fred.calendar_disagreement(brent, eurusd)

    assert counts["joined"] == len(brent) == len(eurusd)
    assert counts["brent_only"] > 0, "the fixture window must contain a US holiday"
    assert counts["eurusd_only"] > 0, "and a UK holiday"
    assert (
        counts["both"] + counts["brent_only"] + counts["eurusd_only"] + counts["neither"]
        == counts["joined"]
    )

    b = brent.set_index("date")["brent_usd_bbl"]
    e = eurusd.set_index("date")["eurusd"]

    # 2026-06-19 is Juneteenth. The Fed is shut, Brent trades.
    assert not math.isnan(b.loc[pd.Timestamp("2026-06-19")])
    assert math.isnan(e.loc[pd.Timestamp("2026-06-19")])

    # 2025-12-26 is Boxing Day. Brent does not print, the Fed does.
    assert math.isnan(b.loc[pd.Timestamp("2025-12-26")])
    assert not math.isnan(e.loc[pd.Timestamp("2025-12-26")])

    # 2025-12-25 is a holiday in both calendars, so neither prints.
    assert math.isnan(b.loc[pd.Timestamp("2025-12-25")])
    assert math.isnan(e.loc[pd.Timestamp("2025-12-25")])


def test_the_pair_is_joined_on_the_date_and_never_zipped_by_position(fred_pair):
    # Both files carry a row for every business day in this window, so a naive
    # zip happens to line up here. Drop one row from the middle of the FX file
    # and a positional pairing silently shifts every later Brent price onto the
    # wrong FX rate. The join notices; a zip cannot.
    brent, eurusd = fred_pair
    thinned = eurusd.drop(index=eurusd.index[5]).reset_index(drop=True)

    counts = fred.calendar_disagreement(brent, thinned)
    assert counts["joined"] == len(brent) - 1

    merged = brent.merge(thinned, on="date", how="inner")
    assert len(merged) == len(thinned)
    for _, row in merged.iterrows():
        matching = thinned.loc[thinned["date"] == row["date"], "eurusd"]
        assert len(matching) == 1
        left, right = row["eurusd"], matching.iloc[0]
        assert (pd.isna(left) and pd.isna(right)) or left == right


# ==========================================================================
# FRED, the adapter end to end
# ==========================================================================

def _install_fred_fixture(monkeypatch) -> None:
    """Make fred.fetch_series read the fixtures instead of the network."""

    def fake(series_id: str, *, column: str, delay: float = 1.0) -> pd.DataFrame:
        name = {
            "DCOILBRENTEU": "fred_brent_sample.csv",
            "DEXUSEU": "fred_eurusd_sample.csv",
        }[series_id]
        return fred.parse_csv(
            fixture_bytes(name), series_id=series_id, column=column
        )

    monkeypatch.setattr(fred, "fetch_series", fake)


def test_fred_brent_adapter_writes_a_cache_and_a_manifest_entry(sandbox, monkeypatch):
    _install_fred_fixture(monkeypatch)
    # The fixture starts in 2025, so the real start guard would reject it. The
    # guard itself is tested separately, below.
    monkeypatch.setattr(fred.FredBrent, "series_start", "2025-01-01")

    adapter = shrink_floors(fred.FredBrent(delay=0.0), 100, 90)
    entry = adapter.run()

    assert entry["status"] == "ok"
    assert entry["series"] == "fred_brent_daily"
    assert entry["frequency"] == "daily"
    assert entry["method"] == "published"
    assert entry["committable"] is True
    assert entry["file"] == "data/cache/fred_brent_daily.csv"
    assert entry["unit"] == "USD per barrel"
    # rows counts the observations, file_rows counts the lines, and the seven
    # UK and European bank holidays in this window are the difference.
    assert entry["file_rows"] == entry["rows"] + 7
    assert entry["first_date"] == "2025-12-19"
    assert entry["last_date"] == "2026-07-10"
    assert entry["licence_note"].startswith("FRED tags both series")
    # The mirroring concern travels with the data rather than only in a document.
    assert "mirroring" in entry["licence_note"]

    written = base.read_cache("fred_brent_daily")
    assert len(written) == entry["file_rows"]
    blank = written.set_index("date").loc[pd.Timestamp("2025-12-25"), "brent_usd_bbl"]
    assert math.isnan(blank)
    # The cache writes a missing observation as an empty field, not as a zero.
    raw = (sandbox / "cache" / "fred_brent_daily.csv").read_text(encoding="utf-8")
    assert "2025-12-25,\n" in raw


def test_fred_adapters_agree_with_the_registry(sandbox, monkeypatch):
    # base.Adapter refuses an adapter that disagrees with crack.config.SOURCES
    # about frequency, method or committable, because the registry is what the
    # provenance panel prints. Assert the two really are registered, so that
    # check is doing something.
    for adapter, name in (
        (fred.FredBrent(), "fred_brent_daily"),
        (fred.FredEurUsd(), "fred_eurusd_daily"),
    ):
        registered = base.SOURCES[name]
        assert adapter.frequency == registered.frequency
        assert adapter.method == registered.method
        assert adapter.committable == registered.committable
        assert adapter.url == registered.machine_url
        assert adapter.page_url == registered.page_url


def test_fred_eurusd_adapter_records_the_us_calendar_blanks(sandbox, monkeypatch):
    _install_fred_fixture(monkeypatch)
    monkeypatch.setattr(fred.FredEurUsd, "series_start", "2025-01-01")

    adapter = shrink_floors(fred.FredEurUsd(delay=0.0), 100, 90)
    entry = adapter.run()

    assert entry["status"] == "ok"
    assert entry["file"] == "data/cache/fred_eurusd_daily.csv"
    # Seven blanks in this window, the same count as Brent and a different set:
    # both files blank 25 December, 1 January and 25 May, and after that they
    # part company entirely. Juneteenth is a gap here and not in Brent, and
    # Boxing Day is a gap in Brent and not here.
    assert entry["file_rows"] == entry["rows"] + 7
    assert "2026-06-19" in entry["gaps"]
    assert "2026-01-19" in entry["gaps"]
    assert "2025-12-26" not in entry["gaps"]
    assert "2026-04-03" not in entry["gaps"]


def test_a_download_starting_before_the_series_start_is_refused(sandbox, monkeypatch):
    _install_fred_fixture(monkeypatch)
    adapter = shrink_floors(fred.FredBrent(delay=0.0), 100, 90)
    # The real guard, unpatched: the fixture starts 2025-12-19 and the class
    # says the series starts 1987-05-20, so this passes. Move the guard forward
    # instead, which is the same test from the other side.
    monkeypatch.setattr(fred.FredBrent, "series_start", "2026-01-01")
    with pytest.raises(SourceError, match="source change"):
        adapter.run()

    entry = next(
        e for e in base.manifest_read()["series"] if e["series"] == "fred_brent_daily"
    )
    assert entry["status"] == "failed"
    assert "source change" in entry["note"]


def test_a_failed_fetch_keeps_the_cache_that_is_already_there(sandbox, monkeypatch):
    _install_fred_fixture(monkeypatch)
    monkeypatch.setattr(fred.FredBrent, "series_start", "2025-01-01")

    good = shrink_floors(fred.FredBrent(delay=0.0), 100, 90)
    good.run()
    before = (sandbox / "cache" / "fred_brent_daily.csv").read_bytes()

    def explode(series_id: str, *, column: str, delay: float = 1.0):
        raise SourceError("fred %s: the source is down" % series_id)

    monkeypatch.setattr(fred, "fetch_series", explode)
    with pytest.raises(SourceError, match="the source is down"):
        shrink_floors(fred.FredBrent(delay=0.0), 100, 90).run()

    assert (sandbox / "cache" / "fred_brent_daily.csv").read_bytes() == before
    entry = next(
        e for e in base.manifest_read()["series"] if e["series"] == "fred_brent_daily"
    )
    assert entry["status"] == "failed"
    assert "previous cache kept unchanged" in entry["note"]
    # The failed entry still describes the file that is on disk, so the
    # provenance panel does not go blank when a source has a bad day.
    assert entry["rows"] > 0


# ==========================================================================
# EIA, the cross check on Brent
# ==========================================================================

def test_eia_and_fred_brent_are_compared_on_the_date_not_the_row():
    # EIA omits a holiday, FRED blanks it, so the two files have the same
    # observations and a different number of lines. compare_with joins on the
    # date, which is the only comparison that means anything.
    fred_frame = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2026-01-01", "2026-01-02", "2026-01-05", "2026-01-06"]
            ),
            "brent_usd_bbl": [float("nan"), 61.98, 63.00, 62.10],
        }
    )
    eia_frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"]),
            "brent_usd_bbl": [61.98, 63.00, 62.10],
        }
    )
    result = eia.compare_with(eia_frame, fred_frame)
    assert result["shared"] == 3
    assert result["max_abs_diff"] == 0.0
    assert result["eia_only"] == 0
    assert result["other_only"] == 0

    disagreeing = eia_frame.copy()
    disagreeing.loc[1, "brent_usd_bbl"] = 64.00
    result = eia.compare_with(disagreeing, fred_frame)
    assert result["max_abs_diff"] == pytest.approx(1.0)
    assert result["worst_date"] == "2026-01-05"


@pytest.mark.skipif(
    not (PROBE / "fred" / "EIA_RBRTEd.xls").exists(),
    reason=(
        "the recon probe archive is gitignored. RBRTEd.xls is a legacy .xls and "
        "writing a miniature one needs xlwt, which is not installed, so this "
        "parser has no committed fixture"
    ),
)
def test_eia_parses_the_probe_workbook():
    frame = eia.parse_xls(PROBE / "fred" / "EIA_RBRTEd.xls")
    assert list(frame.columns) == ["date", "brent_usd_bbl"]
    assert frame["date"].iloc[0] == pd.Timestamp("1987-05-20")
    assert frame["brent_usd_bbl"].iloc[0] == pytest.approx(18.63)
    # EIA omits a day it did not publish, so every row carries a price.
    assert int(frame["brent_usd_bbl"].notna().sum()) == len(frame)
    assert frame["date"].is_monotonic_increasing


def test_eia_refuses_a_workbook_that_is_not_this_series():
    with pytest.raises(SourceError, match="did not open as an xls"):
        eia.parse_xls(b"<html>not a workbook at all</html>")


# ==========================================================================
# World Bank, finding the file
# ==========================================================================

def test_the_pink_sheet_url_is_discovered_from_the_landing_page():
    url = worldbank.discover_workbook_url(fixture_text("worldbank_cmo_landing.html"))
    assert url.endswith("/CMO-Historical-Data-Monthly.xlsx")
    # The document id segment is the part that rots. It is read, never built.
    assert "thedocs.worldbank.org" in url
    assert "74e8be41ceb20fa0da750cda2f6b9e4e-0050012026" in url


def test_the_annual_workbook_on_the_same_page_is_not_mistaken_for_the_monthly_one():
    url = worldbank.discover_workbook_url(fixture_text("worldbank_cmo_landing.html"))
    assert "Annual" not in url


def test_a_rotted_pink_sheet_page_fails_loudly_and_does_not_guess():
    # The one behaviour that must never appear here is a fallback to a
    # remembered URL. An old edition that still resolves would be fetched
    # successfully, cached, and stamped with a vintage nobody read.
    with pytest.raises(SourceError) as caught:
        worldbank.discover_workbook_url(
            fixture_text("worldbank_cmo_landing_rotted.html")
        )
    message = str(caught.value)
    assert "CMO-Historical-Data-Monthly.xlsx" in message
    assert "no URL to fall back to" in message
    # It says how many links it did see, so the next reader knows whether the
    # page failed to load or simply changed.
    assert "link(s) in total" in message


def test_a_relative_href_is_resolved_against_the_landing_page():
    html = '<html><body><a href="/en/doc/x/CMO-Historical-Data-Monthly.xlsx">m</a></body></html>'
    url = worldbank.discover_workbook_url(html)
    assert url == "https://www.worldbank.org/en/doc/x/CMO-Historical-Data-Monthly.xlsx"


def test_two_different_monthly_links_are_refused_rather_than_picked_between():
    html = (
        "<html><body>"
        '<a href="https://a.example/CMO-Historical-Data-Monthly.xlsx">one</a>'
        '<a href="https://b.example/CMO-Historical-Data-Monthly.xlsx">two</a>'
        "</body></html>"
    )
    with pytest.raises(SourceError, match="Picking one would be a guess"):
        worldbank.discover_workbook_url(html)


# ==========================================================================
# World Bank, the workbook parser
# ==========================================================================

@pytest.fixture(scope="module")
def pink_sheet() -> pd.DataFrame:
    return worldbank.parse_workbook(FIXTURES / "worldbank_monthly_prices.xlsx")


def test_the_pink_sheet_row_is_found_by_label_and_not_by_position(pink_sheet):
    # Column I today. The pink sheet has added and removed series before, and a
    # column index would survive such a change while quietly pointing at LNG
    # Japan, which is also quoted in $/mmbtu and would pass every bounds check.
    frame = pink_sheet
    assert list(frame.columns) == ["date", "gas_usd_mmbtu"]
    indexed = frame.set_index("date")["gas_usd_mmbtu"]
    assert indexed.loc[pd.Timestamp("2026-08-01")] == pytest.approx(21.11)
    assert indexed.loc[pd.Timestamp("2015-03-01")] == pytest.approx(8.27)
    assert indexed.loc[pd.Timestamp("2015-04-01")] == pytest.approx(6.77)

    # The neighbouring column is a different series with the same unit. If the
    # parser were reading by position it would be reading this instead.
    lng = worldbank.parse_workbook(
        FIXTURES / "worldbank_monthly_prices.xlsx",
        label="Liquefied natural gas, Japan",
    )
    assert not lng["gas_usd_mmbtu"].equals(frame["gas_usd_mmbtu"])


def test_a_period_label_becomes_the_first_day_of_that_month(pink_sheet):
    assert pink_sheet["date"].iloc[0] == pd.Timestamp("1960-01-01")
    assert pink_sheet["date"].is_monotonic_increasing
    assert all(d.day == 1 for d in pink_sheet["date"])


def test_the_vintage_is_read_off_the_sheet(pink_sheet):
    assert pink_sheet.attrs["vintage"] == "Updated on September 02, 2026"


def test_a_missing_label_is_a_stop_and_not_a_fallback():
    with pytest.raises(SourceError, match="no column headed"):
        worldbank.parse_workbook(
            FIXTURES / "worldbank_monthly_prices.xlsx",
            label="Natural gas, Neverland",
        )


def _workbook(rows: list[list]) -> bytes:
    """A miniature Monthly Prices sheet, in memory. CONSTRUCTED, for one case."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = worldbank.SHEET
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def test_a_unit_that_changed_under_the_label_is_refused():
    # SPEC.md section 4.4 reads this column straight into gas_usd_mmbtu. A series
    # that quietly moved to $/mt would be wrong by a factor nobody would see, so
    # the unit cell is checked and not assumed.
    payload = _workbook(
        [
            ["World Bank Commodity Price Data (The Pink Sheet)"],
            ["monthly prices in nominal US dollars, 1960 to present"],
            ["(monthly series are available only in nominal terms)"],
            ["Updated on September 02, 2026"],
            [None, "Natural gas, Europe"],
            [None, "($/mt)"],
            ["2026M08", 21.11],
        ]
    )
    with pytest.raises(SourceError, match="unit cell"):
        worldbank.parse_workbook(payload)


def test_the_missing_value_token_becomes_nan_and_never_zero():
    # The file's own note block calls it "..", and openpyxl hands it back as one
    # U+2026 horizontal ellipsis. A zero here would be free European gas.
    payload = _workbook(
        [
            ["World Bank Commodity Price Data (The Pink Sheet)"],
            ["monthly prices in nominal US dollars, 1960 to present"],
            ["(monthly series are available only in nominal terms)"],
            ["Updated on September 02, 2026"],
            [None, "Natural gas, Europe"],
            [None, "($/mmbtu)"],
            ["2026M06", 15.17],
            ["2026M07", chr(0x2026)],
            ["2026M08", 21.11],
        ]
    )
    frame = worldbank.parse_workbook(payload)
    indexed = frame.set_index("date")["gas_usd_mmbtu"]
    assert math.isnan(indexed.loc[pd.Timestamp("2026-07-01")])
    assert not (indexed.fillna(-1) == 0).any()
    # The row survives, so the hole is visible rather than absent.
    assert len(frame) == 3


def test_an_unreadable_price_raises_rather_than_being_coerced():
    payload = _workbook(
        [
            ["World Bank Commodity Price Data (The Pink Sheet)"],
            [None],
            [None],
            ["Updated on September 02, 2026"],
            [None, "Natural gas, Europe"],
            [None, "($/mmbtu)"],
            ["2026M08", "twenty one"],
        ]
    )
    with pytest.raises(SourceError, match="cannot read"):
        worldbank.parse_workbook(payload)


def test_the_worldbank_adapter_carries_the_2015_break_into_the_manifest(
    sandbox, monkeypatch
):
    def fake(*, delay: float = 1.0):
        frame = worldbank.parse_workbook(FIXTURES / "worldbank_monthly_prices.xlsx")
        return frame, "https://thedocs.worldbank.org/en/doc/fixture/related/CMO-Historical-Data-Monthly.xlsx"

    monkeypatch.setattr(worldbank, "fetch_monthly", fake)
    adapter = shrink_floors(worldbank.WorldBankGasEurope(delay=0.0), 10, 10)
    entry = adapter.run()

    assert entry["status"] == "ok"
    assert entry["file"] == "data/cache/worldbank_gas_europe_monthly.csv"
    assert entry["frequency"] == "monthly"
    assert entry["unit"] == "USD per MMBtu"
    assert entry["vintage"] == "Updated on September 02, 2026"
    assert entry["url"].endswith("CMO-Historical-Data-Monthly.xlsx")

    breaks = {b["date"] for b in entry["structural_breaks"]}
    assert "2015-04-01" in breaks
    ttf_break = next(
        b for b in entry["structural_breaks"] if b["date"] == "2015-04-01"
    )
    assert "Title Transfer Facility" in ttf_break["note"]
    # Recon 04 open question 3 travels with the data instead of only living in
    # docs/open-questions.md.
    assert "forecast series" in entry["open_question"]
    assert "from April 2015" in entry["series_description"]


# ==========================================================================
# Yahoo TTF
# ==========================================================================

@pytest.fixture(scope="module")
def ttf_history() -> pd.DataFrame:
    """The captured yfinance history frame, as yfinance hands it over."""
    raw = pd.read_csv(FIXTURES / "yahoo_ttf_history.csv")
    return yahoo.frame_from_yfinance(raw.set_index("Date"))


def test_an_empty_yfinance_frame_raises_and_is_never_cached(sandbox, monkeypatch):
    # SPEC.md section 13 by name. The failure this prevents is a zero row cache
    # replacing 2,235 real sessions, which every downstream chart would render
    # as a blank panel with no error anywhere.
    with pytest.raises(yahoo.EmptyChartError, match="empty frame"):
        yahoo.frame_from_yfinance(pd.DataFrame())

    def always_empty(*args, **kwargs):
        raise yahoo.EmptyChartError("yfinance returned an empty frame for TTF=F")

    monkeypatch.setattr(yahoo, "fetch_via_yfinance", always_empty)
    monkeypatch.setattr(yahoo, "fetch_via_chart_json", always_empty)

    adapter = shrink_floors(
        yahoo.TtfFrontMonth(delay=0.0, pause=0.0, now=AFTER_THE_FIXTURES), 10, 10
    )
    with pytest.raises(yahoo.EmptyChartError):
        adapter.run()

    assert not (sandbox / "private" / "ttf_daily.csv").exists()
    entry = next(
        e for e in base.manifest_read()["series"] if e["series"] == "ttf_daily"
    )
    assert entry["status"] == "failed"
    assert entry["rows"] == 0
    assert "empty frame" in entry["note"]


def test_yfinance_is_retried_before_the_chart_endpoint_is_used(sandbox, monkeypatch):
    calls = {"n": 0}

    def flaky(*, attempts: int = 3, pause: float = 0.0):
        calls["n"] += 1
        raise yahoo.EmptyChartError("empty again")

    def json_path(*, delay: float = 0.0):
        return yahoo.parse_chart_json(fixture_bytes("yahoo_ttf_chart.json"))

    monkeypatch.setattr(yahoo, "fetch_via_yfinance", flaky)
    monkeypatch.setattr(yahoo, "fetch_via_chart_json", json_path)

    adapter = shrink_floors(
        yahoo.TtfFrontMonth(delay=0.0, pause=0.0, now=AFTER_THE_FIXTURES), 10, 10
    )
    entry = adapter.run()
    assert calls["n"] == 1
    assert entry["status"] == "ok"
    assert entry["fetch_path"] == "chart json"
    assert "yfinance path not used because" in entry["note"]


def test_the_ttf_cache_is_written_to_data_private_and_marked_not_committable(
    sandbox, monkeypatch
):
    # SPEC.md section 2 rule 6. Yahoo grants no redistribution right, recon 04
    # section 3.9, so these bytes must not be able to reach a public repository.
    def from_fixture(*, attempts: int = 3, pause: float = 0.0):
        raw = pd.read_csv(FIXTURES / "yahoo_ttf_history.csv")
        return yahoo.frame_from_yfinance(raw.set_index("Date"))

    monkeypatch.setattr(yahoo, "fetch_via_yfinance", from_fixture)
    adapter = shrink_floors(
        yahoo.TtfFrontMonth(delay=0.0, pause=0.0, now=AFTER_THE_FIXTURES), 10, 10
    )
    entry = adapter.run()

    assert adapter.directory() == "private"
    assert entry["committable"] is False
    assert entry["file"] == "data/private/ttf_daily.csv"
    assert (sandbox / "private" / "ttf_daily.csv").exists()
    assert not (sandbox / "cache" / "ttf_daily.csv").exists()
    assert "NOT COMMITTED" in entry["note"]
    assert "not" in entry["licence_note"].lower()


def test_the_tz_aware_date_becomes_the_exchange_session_date(ttf_history):
    # Recon 04 section 3.10: Yahoo stamps the bar in New York time, so the saved
    # frame carries a -04:00 offset that becomes -05:00 in winter. Parsed as UTC
    # dates, every session would sit on the wrong calendar day.
    frame = yahoo.normalise(ttf_history, now=AFTER_THE_FIXTURES)
    assert frame["date"].iloc[0] == pd.Timestamp("2026-08-20")
    assert frame["date"].iloc[-1] == pd.Timestamp("2026-09-11")
    assert all(d.weekday() < 5 for d in frame["date"])
    assert frame["date"].dt.tz is None


def test_a_bar_for_a_session_that_has_not_settled_is_dropped(ttf_history):
    # A live bar is a snapshot, not a settlement, and writing it puts a number in
    # the file that the next run quietly changes. The fixture itself is the
    # evidence: it was captured intraday on 2026-09-11 with a close of 81.50,
    # and the chart capture taken the next day settles that session at 79.52.
    during = dt.datetime(2026, 9, 11, 11, 0, tzinfo=ZoneInfo("America/New_York"))
    frame = yahoo.normalise(ttf_history, now=during)
    assert frame["date"].max() == pd.Timestamp("2026-09-10")

    kept = yahoo.normalise(ttf_history, now=during, drop_unsettled=False)
    assert kept["date"].max() == pd.Timestamp("2026-09-11")


def test_the_chart_json_capture_parses_into_the_same_shape():
    frame = yahoo.parse_chart_json(fixture_bytes("yahoo_ttf_chart.json"))
    assert list(frame.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert len(frame) == 20
    assert frame["date"].iloc[0] == pd.Timestamp("2026-08-14")
    assert frame["date"].iloc[-1] == pd.Timestamp("2026-09-11")
    # 2026-09-07 was Labor Day. Yahoo emits no bar for it.
    assert pd.Timestamp("2026-09-07") not in set(frame["date"])
    assert frame["close"].iloc[-1] == pytest.approx(79.519997, rel=1e-6)


def test_the_range_max_trap_is_refused():
    # CONSTRUCTED. Recon 04 section 3.8 measured range=max returning 465 weekly
    # bars while still being asked for interval=1d. A file of weekly bars written
    # into a daily cache would thin nine years of data and nothing in the
    # response says it happened, so the granularity is checked.
    payload = json.loads(fixture_text("yahoo_ttf_chart.json"))
    payload["chart"]["result"][0]["meta"]["dataGranularity"] = "1wk"
    with pytest.raises(SourceError, match="range=max"):
        yahoo.parse_chart_json(payload)


def test_a_chart_error_document_and_an_empty_result_are_told_apart():
    with pytest.raises(SourceError, match="chart endpoint returned"):
        yahoo.parse_chart_json({"chart": {"error": {"code": "Not Found"}, "result": None}})
    with pytest.raises(yahoo.EmptyChartError):
        yahoo.parse_chart_json({"chart": {"error": None, "result": []}})


def test_roll_jumps_are_reported_and_nothing_is_adjusted(ttf_history):
    # The rolls are unadjusted and undocumented, and this is the only honest
    # thing to do with them: list the candidates, say what is circumstantial
    # about each, and leave every price exactly as Yahoo served it.
    frame = yahoo.normalise(ttf_history, now=AFTER_THE_FIXTURES)
    before = frame["close"].tolist()

    candidates = yahoo.roll_jump_candidates(frame, threshold_percent=3.0)
    assert candidates, "the captured window contains moves above 3 percent"
    for entry in candidates:
        assert set(entry) == {
            "date",
            "previous_date",
            "close",
            "previous_close",
            "percent",
            "sessions_to_month_end",
        }
        assert abs(entry["percent"]) >= 3.0
        assert entry["previous_date"] < entry["date"]

    # The observed roll of 2026-08-28 is inside this window. It is recorded as a
    # fact with a method next to it, not inferred from the jump.
    assert yahoo.OBSERVED_ROLL["date"] == "2026-08-28"
    assert "TTFV26" in yahoo.OBSERVED_ROLL["into"]

    assert frame["close"].tolist() == before


def test_the_early_flat_bars_are_counted_rather_than_hidden():
    # Recon 04 section 3.3: the first four and a half months repeat the
    # settlement into all four OHLC fields and carry no volume. Usable as a
    # price, useless as a liquidity signal, and the difference belongs in the
    # manifest.
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2017-10-23", "2017-10-24", "2018-02-27", "2018-03-14"]
            ),
            "open": [18.09, 17.96, 20.0, 20.0],
            "high": [18.09, 17.96, 20.0, 21.0],
            "low": [18.09, 17.96, 20.0, 19.5],
            "close": [18.09, 17.96, 20.0, 20.5],
            "volume": [0, 0, 5, 12],
        }
    )
    shape = yahoo.flat_bar_count(frame)
    assert shape["flat_bars"] == 3
    assert shape["zero_volume_bars"] == 2
    assert shape["first_non_flat_bar"] == "2018-03-14"
    assert shape["first_bar_with_volume"] == "2018-02-27"


def test_a_duplicate_session_and_a_missing_column_are_both_refused(ttf_history):
    doubled = pd.concat([ttf_history, ttf_history.tail(1)], ignore_index=True)
    with pytest.raises(SourceError, match="duplicate session"):
        yahoo.normalise(doubled, now=AFTER_THE_FIXTURES)

    with pytest.raises(SourceError, match="missing column"):
        yahoo.normalise(ttf_history.drop(columns=["volume"]), now=AFTER_THE_FIXTURES)
