"""Tests for the JODI physical adapter, the layer that turns a margin into crude demand.

NOTHING HERE TOUCHES THE NETWORK. Every parser runs against a committed fixture
under tests/fixtures, every adapter runs inside the sandbox fixture from
conftest.py with its raw store rooted in tmp_path, and every JodiRawStore in this
file is built with policy "none" so that a mistake fails as an error rather than
as 933 MB of traffic.

The fixtures, and which are captures and which are constructed
---------------------------------------------------------------
A capture is a verbatim slice of what jodidata.org actually served, taken during
the Gate 1 recon on 2026-09-11 and re verified against the server on 2026-09-13.
A constructed fixture is written here for a case that could not be captured, and
each one says so in its own header. The difference matters: a test that passes
against a constructed fixture proves the parser handles what this file imagines,
and only a capture proves it handles what the source sends.

    jodi_downloads_page.html        CAPTURE of the anchor elements. All 50
                                    annual CSV <a> elements, byte for byte, from
                                    data-downloads.aspx. The document around them
                                    is this file's: the real page is 31,660 bytes
                                    of navigation and Beyond 20/20 links that no
                                    parser here reads. It carries the thing the
                                    whole discovery step exists for, the year in
                                    progress served as primaryyear2026.csv while
                                    every closed year is served as 2025.csv.

    jodi_downloads_page_year_missing.html
                                    CONSTRUCTED. The capture with the primary
                                    2013 link deleted. A hole in the middle of
                                    the span would silently shorten the history.

    jodi_downloads_page_tables_disagree.html
                                    CONSTRUCTED. The capture with the secondary
                                    2026 link deleted, so the primary table
                                    offers a year the secondary table does not.
                                    Output over intake would then be computed
                                    from a numerator and a denominator of
                                    different lengths.

    jodi_primary_2026_sample.csv    CAPTURE, re cut. Fifty rows of
                                    annual-csv/primary/primaryyear2026.csv, the
                                    file's own header and lines, for 2026-05 and
                                    2026-06. Thirty of them are what this study
                                    keeps, five countries times three flow and
                                    product pairs times two months. The other
                                    twenty are there to be thrown away and each
                                    kind is a real shape from the file: the same
                                    observation in CONVBBL, KBBL, KL and KTONS,
                                    NWE rows for flows this study does not read
                                    carrying the missing tokens x and minus, and
                                    rows for AE, a country this study does not
                                    read. The row selection is this file's, every
                                    row is JODI's.

    jodi_secondary_2026_sample.csv  CAPTURE, re cut, the same way. Fifty five
                                    rows of secondaryyear2026.csv for 2026-06, of
                                    which thirty five are the five countries
                                    times the seven products.

    jodi_item_names.txt             CAPTURE. The text layer of JODI's published
                                    item names guide, extracted with pdfplumber
                                    exactly as the module extracts it at run
                                    time, with a provenance header added as the
                                    first eight lines.

    jodi_item_names_renamed.txt     CONSTRUCTED. The same with one long name
                                    changed, which is what a renamed code looks
                                    like.

Two things are constructed in code rather than captured, and both say why at the
point they are built: a full length extract covering 2002-01 to 2026-06, because
the adapters declare observation floors of 280 and 200 months and no honest
fixture of a few rows can reach them, and a truncated one, because a history that
silently shortens is the failure the start date check exists to catch.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from crack.sources import jodi
from crack.sources.base import SourceError

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


# --------------------------------------------------------------------------
# Discovery: the hrefs are read, never constructed
# --------------------------------------------------------------------------

def test_discovery_finds_all_fifty_annual_files():
    found = jodi.discover_annual_files(fixture_text("jodi_downloads_page.html"))
    assert len(found) == 50
    assert sorted({table for table, _ in found}) == ["primary", "secondary"]
    years = sorted({year for _, year in found})
    assert years[0] == 2002
    assert years == list(range(years[0], years[-1] + 1))


def test_discovery_reads_the_current_year_under_its_own_name():
    """The year in progress is primaryyear2026.csv, not 2026.csv.

    This is the single most valuable assertion in the file. A URL built from a
    pattern would fetch 2002 to 2025 successfully and lose the newest year, so
    the failure would appear months later as a physical series that stopped in
    December for no reason.
    """
    found = jodi.discover_annual_files(fixture_text("jodi_downloads_page.html"))
    current = max(year for _, year in found)
    assert found[("primary", current)].endswith("/primary/primaryyear2026.csv")
    assert found[("secondary", current)].endswith("/secondary/secondaryyear2026.csv")
    assert found[("primary", current - 1)].endswith("/primary/2025.csv")
    assert found[("secondary", current - 1)].endswith("/secondary/2025.csv")


def test_discovery_returns_absolute_urls_from_relative_hrefs():
    found = jodi.discover_annual_files(fixture_text("jodi_downloads_page.html"))
    for url in found.values():
        assert url.startswith("https://www.jodidata.org/_resources/files/downloads/")


def test_discovery_accepts_bytes_as_well_as_text():
    found = jodi.discover_annual_files(fixture_bytes("jodi_downloads_page.html"))
    assert len(found) == 50


def test_discovery_stops_when_a_year_is_missing_from_the_span():
    with pytest.raises(SourceError, match="missing year"):
        jodi.discover_annual_files(fixture_text("jodi_downloads_page_year_missing.html"))


def test_discovery_stops_when_the_two_tables_offer_different_years():
    with pytest.raises(SourceError, match="different years"):
        jodi.discover_annual_files(
            fixture_text("jodi_downloads_page_tables_disagree.html")
        )


def test_discovery_stops_on_a_page_with_no_annual_links():
    with pytest.raises(SourceError, match="no annual CSV links"):
        jodi.discover_annual_files("<html><body><a href='/about'>About</a></body></html>")


def test_discovery_stops_when_the_history_would_shorten():
    """A page that no longer offers 2002 has moved its start date."""
    page = fixture_text("jodi_downloads_page.html")
    kept = "\n".join(line for line in page.splitlines() if "/2002.csv" not in line)
    with pytest.raises(SourceError, match="now starts at 2003"):
        jodi.discover_annual_files(kept)


# --------------------------------------------------------------------------
# The codes come from JODI's own guide, SPEC.md section 5.1
# --------------------------------------------------------------------------

def test_every_code_this_module_uses_resolves_from_the_published_guide():
    resolved = jodi.verify_item_names(fixture_text("jodi_item_names.txt"))
    for code, name in jodi.PRODUCT_NAMES.items():
        assert resolved[code] == name
    for code, name in jodi.FLOW_NAMES.items():
        assert resolved[code] == name
    assert resolved["KBD"] == jodi.UNIT_NAMES["KBD"]
    for code, meaning in jodi.ASSESSMENT_CODES.items():
        assert resolved[code] == meaning


def test_a_renamed_code_is_a_stop_and_not_a_warning():
    with pytest.raises(SourceError, match="GASDIES"):
        jodi.verify_item_names(fixture_text("jodi_item_names_renamed.txt"))


def test_the_guide_still_prints_refinery_intake_as_the_observed_throughput():
    """REFINOBS is the observed intake, which is the series SPEC.md 6.1 wants.

    The manual defines a separate calculated intake used as an accuracy check.
    The two are different numbers and only one of them is in the database.
    """
    assert jodi.DEFINITIONS["REFINOBS"].startswith("Refinery intake : Observed")
    assert "Gross output (including refinery fuel)" in jodi.DEFINITIONS["REFGROUT"]


# --------------------------------------------------------------------------
# Filtering one annual file
# --------------------------------------------------------------------------

def test_filter_keeps_only_the_five_countries_the_wanted_pairs_and_kbd():
    rows = jodi.filter_annual_csv(
        fixture_bytes("jodi_primary_2026_sample.csv"), table="primary", year=2026
    )
    assert len(rows) == 30
    assert {row[0] for row in rows} == set(jodi.COUNTRIES)
    assert {row[4] for row in rows} == {"KBD"}
    assert {(row[3], row[2]) for row in rows} == set(jodi.WANTED["primary"])
    assert {row[1] for row in rows} == {"2026-05", "2026-06"}


def test_filter_discards_the_other_units_of_the_same_observation():
    """JODI prints one observation five times, once per unit.

    Keeping more than one unit would put the same barrels into the cache twice
    under two names, and the KBBL and KTONS rows in the fixture are the real
    lines that sit beside the KBD one.
    """
    text = fixture_text("jodi_primary_2026_sample.csv")
    assert "BE,2026-05,CRUDEOIL,REFINOBS,KTONS,2634.0000,1" in text
    rows = jodi.filter_annual_csv(text, table="primary", year=2026)
    assert all(row[4] == "KBD" for row in rows)


def test_filter_keeps_the_secondary_products(tmp_path):
    rows = jodi.filter_annual_csv(
        fixture_bytes("jodi_secondary_2026_sample.csv"), table="secondary", year=2026
    )
    assert len(rows) == 35
    assert {row[2] for row in rows} == {
        "GASOLINE",
        "GASDIES",
        "JETKERO",
        "KEROSENE",
        "RESFUEL",
        "NAPHTHA",
        "TOTPRODS",
    }


def test_filter_does_not_parse_obs_value():
    """The source's own tokens survive into the extract.

    A token this module has never seen must be visible in data/private rather
    than already collapsed into a NaN by the time anyone looks.
    """
    text = fixture_text("jodi_primary_2026_sample.csv")
    lines = [line for line in text.splitlines() if line.startswith("BE,2026-05,CRUDEOIL,OSOURCES")]
    assert lines and lines[0].endswith(",-,3")


def test_filter_stops_on_a_changed_header():
    text = fixture_text("jodi_primary_2026_sample.csv")
    moved = text.replace(
        "REF_AREA,TIME_PERIOD,ENERGY_PRODUCT,FLOW_BREAKDOWN",
        "REF_AREA,TIME_PERIOD,FLOW_BREAKDOWN,ENERGY_PRODUCT",
        1,
    )
    with pytest.raises(SourceError, match="header"):
        jodi.filter_annual_csv(moved, table="primary", year=2026)


def test_filter_stops_when_the_page_and_the_file_disagree_about_the_year():
    with pytest.raises(SourceError, match="carries a row dated"):
        jodi.filter_annual_csv(
            fixture_text("jodi_primary_2026_sample.csv"), table="primary", year=2025
        )


def test_filter_stops_on_a_time_period_that_is_not_year_month():
    text = fixture_text("jodi_primary_2026_sample.csv").replace("2026-06", "2026-Q2")
    with pytest.raises(SourceError, match="TIME_PERIOD"):
        jodi.filter_annual_csv(text, table="primary", year=2026)


def test_filter_stops_when_the_countries_have_gone():
    text = fixture_text("jodi_primary_2026_sample.csv")
    without = "\n".join(
        line
        for line in text.splitlines()
        if not any(line.startswith(code + ",") for code in jodi.COUNTRIES)
    )
    with pytest.raises(SourceError, match="yielded no rows"):
        jodi.filter_annual_csv(without + "\n", table="primary", year=2026)


def test_filter_refuses_an_unknown_table():
    with pytest.raises(SourceError, match="unknown table"):
        jodi.filter_annual_csv("REF_AREA\n", table="tertiary", year=2026)


# --------------------------------------------------------------------------
# Missing tokens
# --------------------------------------------------------------------------

@pytest.mark.parametrize("token", ["-", "..", "x", "N/A", ""])
def test_every_declared_missing_token_becomes_nan(token):
    value = jodi._parse_value(token, where="test")
    assert value != value


def test_an_undeclared_token_raises_rather_than_becoming_a_number():
    """SPEC.md section 2 rule 1. A fifth token is added deliberately or not at all.

    Recon 03 could not find a JODI document defining x, minus, two dots and N/A
    apart from one another, so the module treats all four as missing and refuses
    to guess at a fifth.
    """
    with pytest.raises(SourceError, match="cannot read OBS_VALUE"):
        jodi._parse_value("c", where="test")


# --------------------------------------------------------------------------
# Column naming
# --------------------------------------------------------------------------

def test_column_names_are_jodis_own_codes():
    assert jodi.column_name("BE", "REFINOBS", "CRUDEOIL") == "be_refinobs_crudeoil_kbd"
    assert jodi.column_name("nwe5", "REFGROUT", "GASDIES") == "nwe5_refgrout_gasdies_kbd"


def test_the_uk_is_gb():
    """SPEC.md writes UK in four places and UK is not in the database.

    JODI carries 118 REF_AREA values, GB is one of them and UK is not, so the
    spec's spelling returns an empty series rather than an error.
    """
    assert "GB" in jodi.COUNTRIES
    assert "UK" not in jodi.COUNTRIES
    assert "UK" in jodi.COUNTRY_NAMES["GB"]


# --------------------------------------------------------------------------
# The raw store
# --------------------------------------------------------------------------

def build_store(tmp_path: Path, *, item_names: str = "jodi_item_names.txt") -> jodi.JodiRawStore:
    store = jodi.JodiRawStore(root=tmp_path / "jodi_raw", policy="none")
    store.root.mkdir(parents=True, exist_ok=True)
    store.item_names_path.write_text(fixture_text(item_names), encoding="utf-8")
    return store


def write_extract(store: jodi.JodiRawStore, table: str, year: int, rows) -> None:
    store._write_extract(table, year, rows)


def test_adopt_local_filters_files_already_on_this_machine(tmp_path):
    """933 MB downloaded once is not downloaded again to produce the same extract."""
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "primary_2026.csv").write_bytes(fixture_bytes("jodi_primary_2026_sample.csv"))
    (incoming / "secondary_2026.csv").write_bytes(
        fixture_bytes("jodi_secondary_2026_sample.csv")
    )
    (incoming / "nwe_extract.csv").write_text("not an annual file\n", encoding="utf-8")

    store = build_store(tmp_path)
    report = store.adopt_local(incoming)

    assert sorted(report["adopted"]) == ["primary/2026", "secondary/2026"]
    assert report["skipped"] == ["nwe_extract.csv"]
    assert store.extract_path("primary", 2026).exists()

    record = store.read_index()["files"]["primary/2026"]
    assert record["origin"] == "adopted"
    assert record["rows_kept"] == 30
    assert record["sha256"]
    # An adopted file is undated on purpose. Nothing has asked the server what
    # it is serving, so nothing may claim a release date.
    assert record["last_modified"] is None
    assert record["url"] is None


def test_adopt_local_takes_the_table_from_the_directory_for_a_bare_year(tmp_path):
    incoming = tmp_path / "incoming" / "secondary"
    incoming.mkdir(parents=True)
    (incoming / "2026.csv").write_bytes(fixture_bytes("jodi_secondary_2026_sample.csv"))
    store = build_store(tmp_path)
    report = store.adopt_local(incoming)
    assert report["adopted"] == ["secondary/2026"]


def test_adopt_local_stops_on_a_directory_with_nothing_in_it(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    store = build_store(tmp_path)
    with pytest.raises(SourceError, match="no annual file"):
        store.adopt_local(empty)


def test_the_store_refuses_an_unknown_policy():
    with pytest.raises(ValueError, match="unknown fetch policy"):
        jodi.JodiRawStore(policy="sometimes")


def test_the_store_will_not_invent_a_series_from_an_empty_directory(tmp_path):
    store = build_store(tmp_path)
    with pytest.raises(SourceError, match="Nothing has been fetched"):
        store.load()


def test_the_store_refuses_to_load_without_the_item_names_guide(tmp_path):
    store = jodi.JodiRawStore(root=tmp_path / "jodi_raw", policy="none")
    store.root.mkdir(parents=True, exist_ok=True)
    write_extract(
        store,
        "primary",
        2026,
        jodi.filter_annual_csv(
            fixture_bytes("jodi_primary_2026_sample.csv"), table="primary", year=2026
        ),
    )
    with pytest.raises(SourceError, match="resolved from JODI"):
        store.load()


def test_the_store_loads_the_extracts_as_a_tidy_frame(tmp_path):
    store = build_store(tmp_path)
    write_extract(
        store,
        "primary",
        2026,
        jodi.filter_annual_csv(
            fixture_bytes("jodi_primary_2026_sample.csv"), table="primary", year=2026
        ),
    )
    write_extract(
        store,
        "secondary",
        2026,
        jodi.filter_annual_csv(
            fixture_bytes("jodi_secondary_2026_sample.csv"), table="secondary", year=2026
        ),
    )
    tidy = store.load()
    assert list(tidy.columns) == [
        "date",
        "ref_area",
        "flow",
        "product",
        "value",
        "code",
        "table",
    ]
    assert len(tidy) == 65
    row = tidy[
        (tidy["ref_area"] == "FR")
        & (tidy["flow"] == "REFINOBS")
        & (tidy["product"] == "CRUDEOIL")
        & (tidy["date"] == pd.Timestamp("2026-06-01"))
    ]
    # The value recon 03 quoted out of the file, carried through unchanged.
    assert float(row["value"].iloc[0]) == pytest.approx(817.3673)
    assert row["code"].iloc[0] == "1"


def test_the_store_refuses_two_files_carrying_the_same_month(tmp_path):
    store = build_store(tmp_path)
    rows = jodi.filter_annual_csv(
        fixture_bytes("jodi_primary_2026_sample.csv"), table="primary", year=2026
    )
    write_extract(store, "primary", 2026, rows)
    # The same rows filed under a second table name, which is what a renamed
    # download or a half finished refresh would leave behind.
    write_extract(store, "primarycopy", 2026, rows)
    with pytest.raises(SourceError, match="duplicate observation"):
        store.load()


def test_an_assessment_code_outside_jodis_published_list_is_a_stop(tmp_path):
    store = build_store(tmp_path)
    rows = jodi.filter_annual_csv(
        fixture_bytes("jodi_primary_2026_sample.csv"), table="primary", year=2026
    )
    rows[0][6] = "7"
    write_extract(store, "primary", 2026, rows)
    with pytest.raises(SourceError, match="assessment code"):
        store.load()


# --------------------------------------------------------------------------
# Pivoting
# --------------------------------------------------------------------------

def tidy_frame(records) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": pd.Timestamp(date),
                "ref_area": area,
                "flow": flow,
                "product": product,
                "value": value,
                "code": code,
                "table": "primary",
            }
            for date, area, flow, product, value, code in records
        ]
    )


def test_the_five_country_sum_is_nan_unless_all_five_reported():
    """A four country sum printed as five is a hole of up to a fifth of NWE demand."""
    records = [
        ("2026-01-01", area, "REFINOBS", "CRUDEOIL", 100.0, "1")
        for area in jodi.COUNTRIES
    ]
    records += [
        ("2026-02-01", area, "REFINOBS", "CRUDEOIL", 100.0, "1")
        for area in jodi.COUNTRIES[:4]
    ]
    frame, _ = jodi.pivot(tidy_frame(records), [("REFINOBS", "CRUDEOIL")])
    total = frame["nwe5_refinobs_crudeoil_kbd"]
    assert total.iloc[0] == pytest.approx(500.0)
    assert np.isnan(total.iloc[1])
    assert frame["cells"].tolist() == [5, 4]


def test_a_month_nobody_reported_is_present_as_nan_rather_than_absent():
    """SPEC.md section 2 rule 1. A hole that is simply missing from the file is invisible."""
    records = [
        ("2026-01-01", area, "REFINOBS", "CRUDEOIL", 100.0, "1")
        for area in jodi.COUNTRIES
    ] + [
        ("2026-03-01", area, "REFINOBS", "CRUDEOIL", 110.0, "1")
        for area in jodi.COUNTRIES
    ]
    frame, _ = jodi.pivot(tidy_frame(records), [("REFINOBS", "CRUDEOIL")])
    assert frame["date"].tolist() == [
        pd.Timestamp("2026-01-01"),
        pd.Timestamp("2026-02-01"),
        pd.Timestamp("2026-03-01"),
    ]
    assert np.isnan(frame["nwe5_refinobs_crudeoil_kbd"].iloc[1])
    assert frame["cells"].iloc[1] == 0


def test_a_missing_token_does_not_become_a_cell():
    records = [
        ("2026-01-01", area, "REFINOBS", "CRUDEOIL", float("nan"), "3")
        for area in jodi.COUNTRIES
    ]
    frame, flagged = jodi.pivot(tidy_frame(records), [("REFINOBS", "CRUDEOIL")])
    assert frame["cells"].iloc[0] == 0
    assert flagged == []
    assert np.isnan(frame["be_refinobs_crudeoil_kbd"].iloc[0])


def test_the_assessment_codes_are_counted_apart_and_flagged_cell_by_cell():
    """Code 2 and code 3 are categories, not two points on a scale.

    Code 3 sits on whole lines for their whole lives and code 2 lands on recent
    cells, so one column holding both would hide the second behind the first.
    """
    records = [
        ("2026-01-01", "BE", "REFINOBS", "CRUDEOIL", 100.0, "1"),
        ("2026-01-01", "DE", "REFINOBS", "CRUDEOIL", 200.0, "2"),
        ("2026-01-01", "FR", "REFINOBS", "CRUDEOIL", 300.0, "3"),
        ("2026-01-01", "NL", "REFINOBS", "CRUDEOIL", 400.0, "1"),
        ("2026-01-01", "GB", "REFINOBS", "CRUDEOIL", 500.0, "1"),
    ]
    frame, flagged = jodi.pivot(tidy_frame(records), [("REFINOBS", "CRUDEOIL")])
    assert frame["cells_code_2"].iloc[0] == 1
    assert frame["cells_code_3"].iloc[0] == 1
    assert frame["cells_code_4"].iloc[0] == 0
    assert {cell["ref_area"] for cell in flagged} == {"DE", "FR"}
    assert flagged[0]["meaning"] == jodi.ASSESSMENT_CODES[flagged[0]["code"]]


def test_pivot_stops_when_the_extracts_carry_none_of_the_wanted_pairs():
    records = [("2026-01-01", "BE", "REFINOBS", "CRUDEOIL", 100.0, "1")]
    with pytest.raises(SourceError, match="carry none of"):
        jodi.pivot(tidy_frame(records), [("REFGROUT", "GASDIES")])


def test_provisional_runs_back_from_the_last_month_and_only_on_code_2():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=4, freq="MS"),
            "cells_code_2": [1, 0, 1, 1],
        }
    )
    assert jodi._provisional_from(frame) == "2026-03-01"
    frame["cells_code_2"] = [1, 1, 1, 0]
    assert jodi._provisional_from(frame) is None


# --------------------------------------------------------------------------
# The adapters, end to end, in the sandbox
# --------------------------------------------------------------------------

#: A constructed full length extract. THE VALUES ARE MADE UP AND THE SHAPE IS
#: NOT: the adapters declare observation floors of 280 and 200 months because
#: recon 03 counted 294 and 210, and no honest fixture of a few captured rows
#: can reach them. So the months, the country set, the two start dates and the
#: assessment codes are the real ones and the numbers are a ramp. Nothing here
#: asserts on a value, only on shape, coverage and bookkeeping. The captured
#: fixtures above are what test the parsing of real bytes.
def constructed_rows(table: str, *, first: str = "2002-01", last: str = "2026-06"):
    months = pd.period_range(first, last, freq="M")
    rows = []
    for pair_index, (flow, product) in enumerate(jodi.WANTED[table]):
        late = (flow, product) in jodi.LATE_START_KEYS
        for month in months:
            if late and str(month) < jodi.LATE_START:
                continue
            for area_index, area in enumerate(jodi.COUNTRIES):
                value = 500.0 + 10 * area_index + pair_index
                code = "2" if str(month) == last else "1"
                rows.append(
                    [
                        area,
                        str(month),
                        product,
                        flow,
                        "KBD",
                        "%.4f" % value,
                        code,
                    ]
                )
    return rows


def loaded_store(tmp_path: Path, **kwargs) -> jodi.JodiRawStore:
    store = build_store(tmp_path)
    for table in ("primary", "secondary"):
        write_extract(store, table, 2026, constructed_rows(table, **kwargs))
    return store


def test_the_three_adapters_write_their_caches_and_their_manifest(sandbox, tmp_path):
    store = loaded_store(tmp_path)
    entries = {}
    for factory in jodi.ADAPTERS:
        entries[factory.name] = factory(store).run()

    assert set(entries) == {
        jodi.SERIES_INTAKE,
        jodi.SERIES_OUTPUT,
        jodi.SERIES_IMPORTS,
    }
    for name, entry in entries.items():
        assert entry["status"] == "ok"
        assert entry["frequency"] == "monthly"
        assert entry["gaps"] == []
        assert entry["first_date"] == "2002-01-01"
        assert entry["last_date"] == "2026-06-01"
        assert entry["rows"] == 294
        assert entry["file"] == "data/cache/%s.csv" % name
        assert (sandbox / "cache" / ("%s.csv" % name)).exists()

    manifest = json.loads((sandbox / "manifest.json").read_text(encoding="utf-8"))
    assert {e["series"] for e in manifest["series"]} == set(entries)


def test_the_manifest_carries_the_assessment_codes_spec_5_1_asks_for(sandbox, tmp_path):
    store = loaded_store(tmp_path)
    entry = jodi.JodiRefineryIntake(store).run()
    codes = entry["assessment_codes"]
    assert codes["definitions"] == dict(jodi.ASSESSMENT_CODES)
    assert codes["source"] == jodi.ITEM_NAMES_URL
    assert set(codes["counts"]) == {"1", "2", "3", "4"}
    assert codes["counts"]["4"] == 0
    # Every constructed cell in the last month carries code 2, five countries
    # times the two intake pairs.
    assert codes["counts"]["2"] == 10
    assert all(cell["code"] in ("2", "4") for cell in codes["flagged_cells"])
    assert "REFINOBS/CRUDEOIL" in codes["by_key"]


def test_the_last_month_is_flagged_provisional(sandbox, tmp_path):
    entry = jodi.JodiRefineryIntake(loaded_store(tmp_path)).run()
    assert entry["provisional_from"] == "2026-06-01"


def test_total_refinery_feed_starts_in_2009_and_crude_intake_in_2002(sandbox, tmp_path):
    jodi.JodiRefineryIntake(loaded_store(tmp_path)).run()
    frame = pd.read_csv(sandbox / "cache" / ("%s.csv" % jodi.SERIES_INTAKE))
    crude = frame.loc[frame["nwe5_refinobs_crudeoil_kbd"].notna(), "date"]
    feed = frame.loc[frame["nwe5_refinobs_totcrude_kbd"].notna(), "date"]
    assert crude.min() == "2002-01-01"
    assert feed.min() == "2009-01-01"


def test_both_denominators_are_published_and_neither_is_chosen(sandbox, tmp_path):
    """SPEC.md section 4.3 layer 4 has not made this choice, so the adapter does not.

    Refinery output over crude only intake is 1.13 to 1.16 and over total
    refinery feed it is 1.01 to 1.03. Publishing one would decide the
    decomposition inside a data adapter, out of sight of the Method view.
    """
    jodi.JodiRefineryIntake(loaded_store(tmp_path)).run()
    frame = pd.read_csv(sandbox / "cache" / ("%s.csv" % jodi.SERIES_INTAKE))
    assert "nwe5_refinobs_crudeoil_kbd" in frame.columns
    assert "nwe5_refinobs_totcrude_kbd" in frame.columns
    assert not any(column.endswith("_yield") for column in frame.columns)


def test_jet_is_published_beside_kerosene_so_a_sum_can_avoid_double_counting(
    sandbox, tmp_path
):
    jodi.JodiRefineryOutput(loaded_store(tmp_path)).run()
    frame = pd.read_csv(sandbox / "cache" / ("%s.csv" % jodi.SERIES_OUTPUT))
    assert "nwe5_refgrout_jetkero_kbd" in frame.columns
    assert "nwe5_refgrout_kerosene_kbd" in frame.columns
    entry = json.loads((sandbox / "manifest.json").read_text(encoding="utf-8"))
    note = next(
        e["note"] for e in entry["series"] if e["series"] == jodi.SERIES_OUTPUT
    )
    assert "double counts jet" in note


def test_a_history_that_has_silently_shortened_is_refused(sandbox, tmp_path):
    """Losing years quietly is how a study claims a sample it does not have."""
    store = loaded_store(tmp_path, first="2010-01")
    with pytest.raises(SourceError, match="The history has shortened"):
        jodi.JodiRefineryIntake(store).run()


def test_a_failed_run_keeps_the_previous_cache_and_records_the_failure(sandbox, tmp_path):
    good = loaded_store(tmp_path)
    jodi.JodiRefineryIntake(good).run()
    before = (sandbox / "cache" / ("%s.csv" % jodi.SERIES_INTAKE)).read_bytes()

    broken = loaded_store(tmp_path / "second", first="2010-01")
    with pytest.raises(SourceError):
        jodi.JodiRefineryIntake(broken).run()

    assert (sandbox / "cache" / ("%s.csv" % jodi.SERIES_INTAKE)).read_bytes() == before
    manifest = json.loads((sandbox / "manifest.json").read_text(encoding="utf-8"))
    entry = next(e for e in manifest["series"] if e["series"] == jodi.SERIES_INTAKE)
    assert entry["status"] == "failed"
    assert "previous cache kept unchanged" in entry["note"]


def test_the_caches_are_committable_and_carry_the_licence_position(sandbox, tmp_path):
    """JODI grants nothing explicitly, so the manifest says so in words."""
    entry = jodi.JodiCrudeImports(loaded_store(tmp_path)).run()
    assert entry["committable"] is True
    assert "no explicit permission to redistribute" in entry["licence_note"]
    assert entry["file"].startswith("data/cache/")


def test_the_store_is_refreshed_once_for_the_three_adapters(sandbox, tmp_path, monkeypatch):
    """Three adapters, one pass over the source. Three passes would be 2.8 GB."""
    store = loaded_store(tmp_path)
    calls = {"n": 0}
    real = store.refresh

    def counted(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(store, "refresh", counted)
    for factory in jodi.ADAPTERS:
        factory(store).run()
    assert calls["n"] == 3
    # Called three times, but the work happened once: the second and third see
    # the memo. Under the offline policy there is nothing else to observe, so
    # this asserts on the memo itself.
    assert store._report is not None
