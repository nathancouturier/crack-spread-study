"""Tests for the OPEC MOMR Rotterdam product price parser. SPEC.md section 9.

NOTHING HERE TOUCHES THE NETWORK AND NOTHING HERE OPENS A PDF. Every parser test
runs against a committed text fixture under tests/fixtures, and the one adapter
test runs with its index and its readings replaced, inside the sandbox fixture
from conftest.py so no test can write into the real data directories.

The fixtures, and which are captures and which are constructed
---------------------------------------------------------------
A capture is a verbatim slice of a real issue. A constructed fixture is written
to cover a case that could not be captured and says so in its own header. The
difference matters: a passing test on a constructed fixture proves the parser
handles what this file imagines, and only a capture proves it handles what OPEC
actually prints.

    opec_momr_2001_01_table.txt   CAPTURE. Layout era one. "Table 2 / Refined
                                  product prices / US $/b", three months, three
                                  Rotterdam rows, gasoil at 0.2 percent sulphur,
                                  gasoline as bare "unleaded", no naphtha, no
                                  jet, no 1.0 percent fuel oil, a BLANK LINE
                                  between the block header and its first row and
                                  a block header of just "Rotterdam".
    opec_momr_2003_06_table.txt   CAPTURE. Era two, the same layout under a
                                  title with no table number.
    opec_momr_2006_06_table.txt   CAPTURE. Era three. "Table 2:", seven Rotterdam
                                  rows, gasoil at 50 ppm, TWO premium gasoline
                                  rows, and a jet price printed as a bare "87"
                                  with no decimals.
    opec_momr_2011_01_table.txt   CAPTURE. Era four. "Table 6.1:", gasoil at
                                  10 ppm, still two gasoline rows.
    opec_momr_2015_06_table.txt   CAPTURE. "Table 6.2:", one gasoline row at
                                  unleaded 98, still three months per issue.
    opec_momr_2019_06_table.txt   CAPTURE. Era five. "Table 6 - 4:", TWO months
                                  per issue plus an annual average column and a
                                  year to date column.
    opec_momr_2022_10_table.txt   CAPTURE. The crisis month the spec names, and
                                  the only issue in the sample that spells its
                                  year to date column "2022-to-date".
    opec_momr_2024_09_table.txt   CAPTURE. The issue recon 05 section 1.3 quotes
                                  verbatim, and the one whose block header
                                  capitalises FOB.
    opec_momr_2026_03_table.txt   CAPTURE. The most recent archived issue.

Five more captures, each kept because a whole run of issues failed on it the
first time the parser met the real archive rather than the eleven issues recon 05
had opened:

    opec_momr_2001_03_table.txt   CAPTURE, extracted at a five point line
                                  tolerance. At the default tolerance this page
                                  splits every product label away from its own
                                  numbers, which is what read_issue_pdf's second
                                  attempt exists for.
    opec_momr_2002_01_table.txt   CAPTURE. Two things at once: the header dates
                                  its third column "Dec,01" with a comma for a
                                  full stop, and the gasoline row carries the
                                  old layout's revision flag, "23.50R".
    opec_momr_2005_02_table.txt   CAPTURE. The header dates only its LAST column,
                                  "Nov    Dec   Jan 05", and the block carries a
                                  "Regular gasoline (unleaded)" row this study
                                  does not keep, and "unleaded 95" is the only
                                  premium gasoline row.
    opec_momr_2008_02_table.txt   CAPTURE. The specifications are footnoted with
                                  an asterisk, "(50 ppm*)".
    opec_momr_2009_07_table.txt   CAPTURE, and a failing one. The gasoline label
                                  is clipped by its own column width and prints
                                  as "Premium gasoline (unleaded 10". The parser
                                  must refuse the issue rather than read the 10
                                  as a price.

    opec_momr_label_missing_table.txt
                                  CONSTRUCTED. The 2024-09 table with the
                                  Rotterdam gasoil row relabelled to a
                                  specification the report has never printed.
                                  The parser must refuse the whole issue rather
                                  than return a number it cannot identify.

Every captured fixture carries one substitution, recorded in its own header: an
en dash used as a minus sign is written as an ASCII hyphen, because SPEC.md
section 0.1 forbids an en dash anywhere in this repository. No digit is touched.
The real document's dash family is covered by test_to_float_reads_every_dash,
which does not need a fixture.

The values asserted below were read off the documents by hand in recon 05
sections 1.3 and 1.4 before this parser existed. That is the point of them: they
are not what the parser produced, recorded afterwards.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from crack.config import BOUNDS_PRODUCT_USD_BBL, SOURCES
from crack.sources import base, opec_momr
from crack.sources.base import SourceError
from crack.sources.opec_momr import (
    COLUMNS_BY_SLOT,
    PRODUCT_LABELS,
    SERIES,
    SPECIFICATION_BREAKS,
    IssueReading,
    OpecRotterdamProductsMonthly,
    build_frame,
    issue_month_of_filename,
    label_key,
    locate_table_page,
    page_is_table,
    parse_cdx,
    parse_header_columns,
    parse_table_page,
    specification_timeline,
    split_label_and_numbers,
    to_float,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture_text(issue: str) -> str:
    return (FIXTURES / ("opec_momr_%s_table.txt" % issue.replace("-", "_"))).read_text(
        encoding="utf-8"
    )


def read(issue: str) -> object:
    return parse_table_page(fixture_text(issue), issue=issue)


def month(text: str) -> pd.Timestamp:
    return pd.Period(text, freq="M").to_timestamp()


# --------------------------------------------------------------------------
# The five layout eras, read out of a real page each
# --------------------------------------------------------------------------

#: issue -> month -> slot -> price, exactly as recon 05 sections 1.3 and 1.4
#: transcribed them from the documents.
ERA_VALUES = {
    "2001-01": {
        "2000-10": {"gasoline": 35.31, "gasoil": 40.06, "fuel_oil_35pct": 23.82},
        "2000-11": {"gasoline": 33.46, "gasoil": 40.68, "fuel_oil_35pct": 22.18},
        "2000-12": {"gasoline": 28.05, "gasoil": 34.25, "fuel_oil_35pct": 18.31},
    },
    "2001-03": {
        # December 2000 is also in the January 2001 issue above, at the same
        # three values. That is the overlap doing its job on a page this parser
        # can only read at the wider line tolerance.
        "2000-12": {"gasoline": 28.05, "gasoil": 34.25, "fuel_oil_35pct": 18.31},
        "2001-01": {"gasoline": 29.85, "gasoil": 30.15, "fuel_oil_35pct": 15.48},
        "2001-02": {"gasoline": 32.49, "gasoil": 30.88, "fuel_oil_35pct": 18.21},
    },
    "2002-01": {
        # The gasoline figure is printed "23.50R", revised since the last issue.
        "2001-10": {"gasoline": 23.50, "gasoil": 27.41, "fuel_oil_35pct": 16.07},
        "2001-11": {"gasoline": 20.20, "gasoil": 23.03, "fuel_oil_35pct": 14.67},
        "2001-12": {"gasoline": 19.30, "gasoil": 21.35, "fuel_oil_35pct": 14.95},
    },
    "2005-02": {
        # Only the last column is dated. November and December take their year
        # from January 2005 and from being consecutive.
        "2004-11": {
            "naphtha": 56.49,
            "gasoline": 50.62,
            "gasoline_95": 50.62,
            "jet": 60.31,
            "gasoil": 56.89,
            "fuel_oil_1pct": 25.23,
            "fuel_oil_35pct": 21.49,
        },
        "2005-01": {
            "naphtha": 51.32,
            "gasoline": 47.84,
            "gasoline_95": 47.84,
            "jet": 55.05,
            "gasoil": 51.92,
            "fuel_oil_1pct": 26.68,
            "fuel_oil_35pct": 23.54,
        },
    },
    "2008-02": {
        "2007-11": {
            "naphtha": 108.46,
            "gasoline": 109.03,
            "gasoline_95": 97.05,
            "jet": 115.45,
            "gasoil": 118.34,
            "fuel_oil_1pct": 72.16,
            "fuel_oil_35pct": 70.61,
        },
        "2008-01": {
            "gasoline": 95.82,
            "gasoline_95": 94.13,
            "gasoil": 108.70,
        },
    },
    "2003-06": {
        "2003-03": {"gasoline": 36.06, "gasoil": 39.61, "fuel_oil_35pct": 21.91},
        "2003-04": {"gasoline": 34.38, "gasoil": 29.59, "fuel_oil_35pct": 18.61},
        "2003-05": {"gasoline": 32.06, "gasoil": 29.00, "fuel_oil_35pct": 20.29},
    },
    "2006-06": {
        "2006-03": {
            "naphtha": 69.12,
            "gasoline": 76.53,
            "gasoline_95": 68.23,
            "jet": 76.52,
            "gasoil": 77.42,
            "fuel_oil_1pct": 45.37,
            "fuel_oil_35pct": 44.02,
        },
        "2006-04": {
            "naphtha": 77.49,
            "gasoline": 90.97,
            "gasoline_95": 81.15,
            "jet": 84.70,
            "gasoil": 84.69,
            "fuel_oil_1pct": 47.77,
            "fuel_oil_35pct": 47.67,
        },
        "2006-05": {
            "naphtha": 78.73,
            "gasoline": 93.84,
            "gasoline_95": 83.69,
            # Printed as a bare "87" with no decimals, which is a real value and
            # not a missing one.
            "jet": 87.0,
            "gasoil": 86.03,
            "fuel_oil_1pct": 47.14,
            "fuel_oil_35pct": 48.13,
        },
    },
    "2011-01": {
        "2010-10": {
            "naphtha": 83.47,
            "gasoline": 96.08,
            "gasoline_95": 93.41,
            "jet": 96.35,
            "gasoil": 96.88,
            "fuel_oil_1pct": 73.78,
            "fuel_oil_35pct": 71.94,
        },
        "2010-12": {
            "naphtha": 93.15,
            "gasoline": 103.44,
            "gasoline_95": 100.57,
            "jet": 105.26,
            "gasoil": 104.15,
            "fuel_oil_1pct": 76.54,
            "fuel_oil_35pct": 76.19,
        },
    },
    "2015-06": {
        "2015-05": {
            "naphtha": 60.76,
            "gasoline": 87.70,
            "jet": 78.67,
            "gasoil": 79.16,
            "fuel_oil_1pct": 52.57,
            "fuel_oil_35pct": 53.41,
        },
    },
    "2019-06": {
        "2019-04": {
            "naphtha": 62.12,
            "gasoline": 92.99,
            "jet": 83.87,
            "gasoil": 84.47,
            "fuel_oil_1pct": 64.94,
            "fuel_oil_35pct": 61.99,
        },
        "2019-05": {
            "naphtha": 60.11,
            "gasoline": 90.26,
            "jet": 84.35,
            "gasoil": 84.87,
            "fuel_oil_1pct": 61.69,
            "fuel_oil_35pct": 58.79,
        },
    },
    "2022-10": {
        "2022-08": {
            "naphtha": 72.98,
            "gasoline": 137.45,
            "jet": 143.04,
            "gasoil": 143.00,
            "fuel_oil_1pct": 90.31,
            "fuel_oil_35pct": 78.87,
        },
        "2022-09": {
            "naphtha": 69.03,
            "gasoline": 124.73,
            "jet": 135.02,
            "gasoil": 139.42,
            "fuel_oil_1pct": 82.58,
            "fuel_oil_35pct": 66.29,
        },
    },
    "2024-09": {
        "2024-07": {
            "naphtha": 75.92,
            "gasoline": 107.60,
            "jet": 103.78,
            "gasoil": 103.06,
            "fuel_oil_1pct": 76.11,
            "fuel_oil_35pct": 77.04,
        },
        "2024-08": {
            "naphtha": 72.69,
            "gasoline": 100.50,
            "jet": 96.18,
            "gasoil": 95.52,
            "fuel_oil_1pct": 72.14,
            "fuel_oil_35pct": 70.60,
        },
    },
    "2026-03": {
        "2026-01": {
            "naphtha": 57.62,
            "gasoline": 80.23,
            "jet": 92.21,
            "gasoil": 88.17,
            "fuel_oil_1pct": 56.36,
            "fuel_oil_35pct": 56.83,
        },
        "2026-02": {
            "naphtha": 62.18,
            "gasoline": 87.66,
            "jet": 98.21,
            "gasoil": 94.62,
            "fuel_oil_1pct": 60.32,
            "fuel_oil_35pct": 62.88,
        },
    },
}


@pytest.mark.parametrize("issue", sorted(ERA_VALUES))
def test_each_era_parses_the_values_read_by_hand(issue):
    reading = read(issue)
    assert reading.ok, reading.error
    for stamp, expected in ERA_VALUES[issue].items():
        got = reading.values[month(stamp)]
        for slot, value in expected.items():
            assert got[slot] == pytest.approx(value, abs=1e-9), (
                "%s %s %s" % (issue, stamp, slot)
            )


@pytest.mark.parametrize("issue", sorted(ERA_VALUES))
def test_no_era_yields_a_label_this_parser_cannot_name(issue):
    """A label in the Rotterdam block that PRODUCT_LABELS does not know.

    None of the nine captures carries one. This is the test that goes red the
    first time OPEC renames a row, which is the moment somebody has to decide
    what the new row is rather than let it vanish.
    """
    assert read(issue).unknown_labels == []


@pytest.mark.parametrize("issue", sorted(ERA_VALUES))
def test_every_price_is_inside_the_declared_bounds(issue):
    low, high = BOUNDS_PRODUCT_USD_BBL
    for prices in read(issue).values.values():
        for slot, value in prices.items():
            assert low <= value <= high, "%s %s %g" % (issue, slot, value)


def test_the_early_era_has_no_naphtha_no_jet_and_no_one_percent_fuel_oil():
    """2001 really does print three Rotterdam rows, and that is a fact not a bug.

    A parser that invented the missing three, or that failed because they were
    absent, would be wrong in opposite directions. SPEC.md section 2 rule 1: a
    missing observation is missing.
    """
    reading = read("2001-01")
    assert reading.ok
    present = set(reading.values[month("2000-10")])
    assert present == {"gasoline", "gasoil", "fuel_oil_35pct"}


# --------------------------------------------------------------------------
# The two specification breaks
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "issue, gasoil_spec, gasoline_spec, gasoline_95_spec",
    [
        ("2001-01", "0.2% S", "unleaded", None),
        ("2001-03", "0.2% S", "unleaded", None),
        ("2002-01", "0.2% S", "unleaded", None),
        ("2003-06", "0.2% S", "unleaded", None),
        # August 2004 to May 2005: "unleaded 95" is the only premium gasoline row
        # printed, so it is both the leading grade and the 95 line.
        ("2005-02", "0.2% S", "unleaded 95", "unleaded 95"),
        ("2006-06", "50 ppm", "unleaded 50 ppm", "unleaded 95"),
        # The specifications are footnoted with an asterisk in 2008. Same row,
        # same product, and the asterisk is not a different grade.
        ("2008-02", "50 ppm", "unleaded 50 ppm", "unleaded 95"),
        ("2011-01", "10 ppm", "unleaded 10 ppm", "unleaded 95"),
        ("2015-06", "10 ppm", "unleaded 98", None),
        ("2019-06", "10 ppm", "unleaded 98", None),
        ("2022-10", "10 ppm", "unleaded 98", None),
        ("2024-09", "10 ppm", "unleaded 98", None),
        ("2026-03", "10 ppm", "unleaded 98", None),
    ],
)
def test_the_specification_is_read_off_the_row_and_travels_with_it(
    issue, gasoil_spec, gasoline_spec, gasoline_95_spec
):
    """The two breaks SPEC.md section 4.2 requires to be marked.

    Gasoil runs 0.2 percent sulphur, 50 ppm, 10 ppm. Gasoline runs unleaded, then
    a sulphur graded and an octane graded row together, then 98. The parser must
    report the label the issue actually printed, because that is what tells a
    chart where to draw the break.
    """
    reading = read(issue)
    assert reading.ok, reading.error
    assert reading.specs["gasoil"] == gasoil_spec
    assert reading.specs["gasoline"] == gasoline_spec
    assert reading.specs.get("gasoline_95") == gasoline_95_spec


def test_the_95_row_keeps_its_column_when_the_source_moves_it():
    """The one place reading gasoline by printed position would go wrong.

    "unleaded 95" is the ONLY premium gasoline row from August 2004 to May 2005,
    and the SECOND row from June 2005, under a sulphur graded row. A parser that
    assigned by position would silently move the 95 line out of its column in
    June 2005 and nothing downstream would notice.
    """
    only_row = read("2005-02")
    november = only_row.values[month("2004-11")]
    assert november["gasoline"] == november["gasoline_95"] == pytest.approx(50.62)
    assert only_row.specs["gasoline"] == "unleaded 95"

    two_rows = read("2008-02")
    november_2007 = two_rows.values[month("2007-11")]
    assert november_2007["gasoline_95"] == pytest.approx(97.05)
    assert november_2007["gasoline"] == pytest.approx(109.03)
    assert two_rows.specs["gasoline"] == "unleaded 50 ppm"


def test_a_second_gasoline_row_that_is_not_the_95_row_fails():
    text = fixture_text("2008-02").replace(
        "Premium gasoline (unleaded 95) 97.05  94.05  94.13   0.08",
        "Premium gasoline (unleaded 98) 97.05  94.05  94.13   0.08",
    )
    reading = parse_table_page(text, issue="2008-02")
    assert not reading.ok
    assert "neither is 'unleaded 95'" in reading.error


def test_the_regular_grade_is_recorded_as_not_carried_rather_than_dropped():
    """A row this study knows about and decides against is not an unknown row.

    The distinction is the point: an unknown label means nobody has looked at it
    and is a reason to go and read the document, and this means somebody did.
    """
    reading = read("2005-02")
    assert reading.ok
    assert reading.ignored_labels == ["Regular gasoline (unleaded)"]
    assert reading.unknown_labels == []
    assert "regulargasoline(unleaded)" in opec_momr.IGNORED_LABELS
    assert len(opec_momr.IGNORED_LABELS["regulargasoline(unleaded)"]) > 60


def test_the_revision_flag_on_a_figure_is_read_and_not_fatal():
    """The old layout footnotes "R Revised since last issue" against the figure.

    "23.50R" is a price, and a parser that refused it would read the row as a two
    number row and fail an issue that is perfectly readable. The flag itself is
    dropped, because the revision is what the overlap rule sees: the same month
    printed again by a later issue.
    """
    assert "23.50R" in fixture_text("2002-01")
    reading = read("2002-01")
    assert reading.ok, reading.error
    assert reading.values[month("2001-10")]["gasoline"] == pytest.approx(23.50)


def test_the_wider_line_tolerance_capture_reads_the_same_december_as_its_neighbour():
    """Two issues, one of them only readable at the wider tolerance, agree.

    December 2000 is printed by the January 2001 issue and again by the March
    2001 issue. The two agree to the cent, which is the cheapest possible check
    that the second attempt in read_issue_pdf is reading the right rows and not
    merely reading something.
    """
    january = read("2001-01").values[month("2000-12")]
    march = read("2001-03").values[month("2000-12")]
    assert january == march


def test_a_clipped_label_fails_rather_than_reading_its_own_specification_as_a_price():
    """July 2009 prints "Premium gasoline (unleaded 10" and loses " ppm)".

    Half a specification identifies nothing, and the 10 that is left would be
    read as a price by a parser that only counted numbers. The issue is refused,
    and its three months are covered by the issues either side of it.
    """
    reading = read("2009-07")
    assert not reading.ok
    assert "unclosed bracket" in reading.error
    assert reading.values == {}


def test_the_two_middle_era_gasoline_rows_are_both_kept_and_not_merged():
    reading = read("2011-01")
    assert reading.specs["gasoline"] == "unleaded 10 ppm"
    assert reading.specs["gasoline_95"] == "unleaded 95"
    october = reading.values[month("2010-10")]
    assert october["gasoline"] == pytest.approx(96.08)
    assert october["gasoline_95"] == pytest.approx(93.41)
    assert october["gasoline"] != october["gasoline_95"]


def test_specification_breaks_are_declared_where_the_manifest_can_read_them():
    """SPEC.md section 4.2 wants the breaks marked, not mentioned.

    They exist twice on purpose: as a per row column in the cache, which is what
    a chart draws from, and as this structure, which is what the provenance panel
    prints. The two must name the same columns.
    """
    columns = {break_["column"] for break_ in SPECIFICATION_BREAKS}
    assert columns == {"gasoil_usd_bbl", "premium_gasoline_usd_bbl"}
    for break_ in SPECIFICATION_BREAKS:
        assert break_["spec_column"] in opec_momr.CACHE_COLUMNS
        assert break_["column"] in opec_momr.CACHE_COLUMNS
        assert break_["what"] and break_["source"]


# --------------------------------------------------------------------------
# The column header
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "issue, months, annual_years",
    [
        ("2001-01", ["2000-10", "2000-11", "2000-12"], []),
        ("2006-06", ["2006-03", "2006-04", "2006-05"], []),
        ("2019-06", ["2019-04", "2019-05"], [2018]),
        ("2022-10", ["2022-08", "2022-09"], [2021]),
        ("2026-03", ["2026-01", "2026-02"], [2025]),
    ],
)
def test_the_months_and_the_annual_column_are_told_apart(issue, months, annual_years):
    """Only the FIRST annual column is an annual average.

    The modern layout prints the previous year's complete average and then the
    current year to date, and only the 2022 issue spells the second one
    "2022-to-date". Reading a running mean of an unfinished year as an annual
    average would be a wrong number with no symptom, so every year column after
    the first is dropped.
    """
    reading = read(issue)
    assert sorted(m.strftime("%Y-%m") for m in reading.values) == months
    assert sorted(reading.annual) == annual_years


def test_the_change_column_is_never_mistaken_for_a_month():
    columns = parse_header_columns("Jul 24 Aug 24 Aug/Jul  2023      2024", "2024-09")
    assert [c.kind for c in columns] == ["month", "month", "change", "year", "year"]
    assert [c.month.strftime("%Y-%m") for c in columns[:2]] == ["2024-07", "2024-08"]
    assert columns[3].year == 2023 and columns[3].to_date is False
    assert columns[4].year == 2024 and columns[4].to_date is True


@pytest.mark.parametrize(
    "header, issue, months",
    [
        # The January 2002 issue's comma for a full stop.
        ("Oct.01 Nov.01 Dec,01 Dec./Nov.", "2002-01",
         ["2001-10", "2001-11", "2001-12"]),
        # The 2005 hyphen.
        ("Apr-05 May-05 Jun-05 Jun/May", "2005-07",
         ["2005-04", "2005-05", "2005-06"]),
        # Months spelled out, and a space after the separator.
        ("Aug. 08 Sept. 08 Oct. 08 Oct./Sept.", "2008-11",
         ["2008-08", "2008-09", "2008-10"]),
        # Only the last column dated, the 2005 layout.
        ("Nov    Dec   Jan 05 Jan/Dec", "2005-02",
         ["2004-11", "2004-12", "2005-01"]),
        ("Dec   Jan 05 Feb 05 Feb/Jan", "2005-03",
         ["2004-12", "2005-01", "2005-02"]),
    ],
)
def test_every_header_spelling_the_archive_actually_prints(header, issue, months):
    """Counted across the 303 archived issues, not imagined.

    Each of these failed a run of real issues before it was handled, and each is
    a way of writing the same thing rather than a different table.
    """
    columns = parse_header_columns(header, issue)
    dated = [c.month.strftime("%Y-%m") for c in columns if c.kind == "month"]
    assert dated == months


def test_a_header_with_no_year_anywhere_is_refused():
    """One dated column is the minimum. Below that the months cannot be placed.

    Taking the year from the issue instead would be a guess about the lag, and
    the lag is the thing the year is used to check.
    """
    with pytest.raises(SourceError) as caught:
        parse_header_columns("Nov    Dec   Jan Jan/Dec", "2005-02")
    assert "carries a year" in str(caught.value)


def test_a_header_whose_undated_months_are_not_consecutive_is_refused():
    with pytest.raises(SourceError) as caught:
        parse_header_columns("Sep    Dec   Jan 05 Jan/Dec", "2005-02")
    assert "consecutive months" in str(caught.value)


def test_the_issue_month_is_read_off_the_page_when_the_page_prints_it():
    """The archive holds one issue filed a month early.

    momr-april-2001.pdf is the May 2001 issue: every page says May 2001 and the
    price table prints February, March and April 2001. Trusting the filename
    dates it a month early and breaks the lag check on a readable issue.
    """
    assert opec_momr.printed_issue_month(
        "60                     OPEC Monthly Oil Market Report - March 2026"
    ) == "2026-03"
    assert opec_momr.printed_issue_month("MOMR January 2001") == "2001-01"
    # A month named in the narrative, on a line that does not name the report,
    # is not the issue date.
    assert opec_momr.printed_issue_month("demand rose through March 2002") is None
    assert opec_momr.printed_issue_month("") is None


def test_a_two_digit_year_is_expanded_against_the_issue_not_a_pivot():
    columns = parse_header_columns("Oct.00 Nov.00 Dec.00 Dec./Nov.", "2001-01")
    assert [c.month.strftime("%Y-%m") for c in columns[:3]] == [
        "2000-10",
        "2000-11",
        "2000-12",
    ]


def test_a_header_whose_months_do_not_belong_to_the_issue_is_refused():
    with pytest.raises(SourceError) as caught:
        parse_header_columns("Jul 24 Aug 24 Aug/Jul 2023 2024", "2026-03")
    assert "before the issue" in str(caught.value)


def test_a_header_with_non_consecutive_months_is_refused():
    with pytest.raises(SourceError) as caught:
        parse_header_columns("Jan 26 Mar 26 Mar/Jan 2025 2026", "2026-04")
    assert "not" in str(caught.value) and "consecutive" in str(caught.value)


def test_a_header_with_the_change_column_in_front_is_refused():
    with pytest.raises(SourceError) as caught:
        parse_header_columns("Aug/Jul Jul 24 Aug 24 2023 2024", "2024-09")
    assert "months first" in str(caught.value)


# --------------------------------------------------------------------------
# The negative cases. A parser that cannot read a label must not guess.
# --------------------------------------------------------------------------

def test_an_unknown_gasoil_label_fails_the_issue_and_writes_nothing():
    """SPEC.md section 13, the whole reason this parser reads labels.

    The fixture is the real 2024-09 table with the gasoil row relabelled to
    "(7 ppm)", a specification the report has never printed. A parser reading by
    position hands back a 7 ppm gasoil under the 10 ppm column and nothing
    downstream notices. This one refuses the issue, keeps no value from it, and
    names the label it could not place.
    """
    reading = parse_table_page(
        fixture_text("label_missing"), issue="2024-09", page=67
    )
    assert not reading.ok
    assert "gasoil" in reading.error
    assert "Gasoil/Diesel (7 ppm)" in reading.error
    assert reading.values == {}
    assert "Gasoil/Diesel (7 ppm)" in reading.unknown_labels


def test_a_failed_issue_contributes_nothing_to_the_series():
    """The failure has to cost the issue, and nothing else.

    build_frame is what enforces it: a reading with .error set never reaches the
    cache, whatever values it happens to be carrying.
    """
    good = read("2024-09")
    bad = parse_table_page(fixture_text("label_missing"), issue="2024-09")
    frame = build_frame([good, bad])
    assert len(frame) == 2
    assert frame["gasoil_usd_bbl"].tolist() == pytest.approx([103.06, 95.52])


def test_an_extra_number_in_a_row_fails_the_issue():
    """A column that appeared. The row and the header must agree on the count."""
    broken = fixture_text("2024-09").replace(
        "Gasoil/Diesel     (10 ppm)    103.06 95.52  -7.54   111.19   105.80",
        "Gasoil/Diesel     (10 ppm)    103.06 95.52  -7.54   111.19   105.80  99.99",
    )
    reading = parse_table_page(broken, issue="2024-09")
    assert not reading.ok
    assert "6 number" in reading.error and "5 column" in reading.error
    assert reading.values == {}


def test_a_page_with_no_rotterdam_block_fails_rather_than_reading_another_hub():
    """The US Gulf block sits directly above Rotterdam and carries the same rows.

    Removing the Rotterdam header must not let the parser walk into the block
    above or below it.
    """
    text = fixture_text("2024-09").replace("Rotterdam (Barges FOB)", "Amsterdam bargES")
    reading = parse_table_page(text, issue="2024-09")
    assert not reading.ok
    assert "rotterdam" in reading.error


def test_a_page_without_the_table_title_fails():
    text = fixture_text("2024-09").replace("Refined product prices", "Crude oil prices")
    reading = parse_table_page(text, issue="2024-09")
    assert not reading.ok
    assert "refined product prices" in reading.error


def test_a_second_row_claiming_one_slot_fails_rather_than_picking_one():
    text = fixture_text("2024-09").replace(
        "        Naphtha                        75.92 72.69  -3.23    71.06    74.19",
        "        Naphtha                        75.92 72.69  -3.23    71.06    74.19\n"
        "        Naphtha*                       11.11 22.22  -3.23    71.06    74.19",
    )
    reading = parse_table_page(text, issue="2024-09")
    assert not reading.ok
    assert "naphtha" in reading.error


def test_three_gasoline_rows_fail_rather_than_being_ranked():
    text = fixture_text("2024-09").replace(
        "        Premium gasoline  (unleaded 98) 107.60 100.50 -7.10 125.96   114.68",
        "        Premium gasoline  (unleaded 98) 107.60 100.50 -7.10 125.96   114.68\n"
        "        Premium gasoline  (unleaded 95) 100.00 99.00  -7.10 125.96   114.68\n"
        "        Premium gasoline  (unleaded 10 ppm) 101.0 98.0 -7.10 125.96  114.68",
    )
    reading = parse_table_page(text, issue="2024-09")
    assert not reading.ok
    assert "3 premium gasoline rows" in reading.error


# --------------------------------------------------------------------------
# The small pieces
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "line, label, numbers",
    [
        (
            "Premium gasoline  (unleaded 98) 107.60 100.50 -7.10 125.96 114.68",
            "Premium gasoline (unleaded 98)",
            ["107.60", "100.50", "-7.10", "125.96", "114.68"],
        ),
        (
            "Gasoil      (0.2%S)  40.06 40.68 34.25    -6.43",
            "Gasoil (0.2%S)",
            ["40.06", "40.68", "34.25", "-6.43"],
        ),
        (
            "Fuel oil          (380 cst 3.5% S) 56.32 65.65 9.33   64.21   60.99",
            "Fuel oil (380 cst 3.5% S)",
            ["56.32", "65.65", "9.33", "64.21", "60.99"],
        ),
        ("Jet/Kerosene                76.52  84.70     87  2.30", "Jet/Kerosene",
         ["76.52", "84.70", "87", "2.30"]),
        ("Rotterdam (Barges FOB)", "Rotterdam (Barges FOB)", []),
    ],
)
def test_the_label_keeps_its_specification_and_the_numbers_are_taken_off_the_end(
    line, label, numbers
):
    """The 98 in "(unleaded 98)" must stay in the label.

    Scanning forward and stopping at the first digit would cut it off and prepend
    it to the values, which is a wrong price with no symptom. Scanning backward,
    the closing parenthesis is what stops the scan.
    """
    got_label, got_numbers = split_label_and_numbers(line)
    assert got_label == label
    assert got_numbers == numbers


def test_to_float_reads_every_dash_this_source_uses():
    """The 2001 and 2003 issues write their minus sign as an en dash.

    One of them extracts as a character that is neither ASCII nor a recognised
    dash. The change column is not used by this adapter, but a token it could not
    classify as a number would throw the column count off and fail an issue that
    is perfectly readable, so the whole family is read as a minus.
    """
    for code in (0x002D, 0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015, 0x2212, 0xFFFD):
        assert to_float(chr(code) + "5.41") == pytest.approx(-5.41)
    assert to_float("+1.68") == pytest.approx(1.68)
    assert to_float("87") == pytest.approx(87.0)


def test_label_key_folds_whitespace_and_case_and_nothing_else():
    assert label_key("Gasoil      (0.2%S)") == "gasoil(0.2%s)"
    assert label_key("Gasoil/Diesel  (10 ppm)") == "gasoil/diesel(10ppm)"
    # The specification is never dropped, because dropping it would put a 50 ppm
    # gasoil into a 10 ppm column.
    assert label_key("Gasoil/Diesel (50 ppm)") != label_key("Gasoil/Diesel (10 ppm)")


def test_every_product_label_maps_to_a_real_slot():
    for key, (slot, spec) in PRODUCT_LABELS.items():
        assert key == label_key(key), "PRODUCT_LABELS key %r is not folded" % key
        assert slot in COLUMNS_BY_SLOT or slot == "gasoline"
        assert spec


def test_page_is_table_needs_both_marks():
    assert page_is_table(fixture_text("2024-09"))
    assert not page_is_table("Rotterdam (Barges FOB)\nGasoil/Diesel (10 ppm) 1 2 3")
    assert not page_is_table("Table 6 - 4: Refined product prices, US$/b\nUS Gulf")
    assert not page_is_table("")


def test_the_page_search_starts_where_the_table_usually_is_and_spirals_out():
    """Ninety six pages must not mean ninety six text extractions.

    The table sits at about 70 percent of the way through every modern issue, so
    the search starts there. The counter below is what proves it does not simply
    read the document from page one.
    """
    pages = ["nothing here"] * 100
    pages[68] = fixture_text("2024-09")
    asked: list[int] = []

    def plain(index: int) -> str:
        asked.append(index)
        return pages[index]

    assert locate_table_page(len(pages), plain) == 68
    assert len(asked) <= 6
    assert asked[0] == 69


def test_the_page_search_fails_loudly_when_no_page_carries_the_table():
    with pytest.raises(SourceError) as caught:
        locate_table_page(5, lambda index: "nothing here")
    assert "none of the 5 pages" in str(caught.value)


# --------------------------------------------------------------------------
# The archive index
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.opec.org/assets/assetdb/momr-march-2026.pdf", "2026-03"),
        ("https://www.opec.org/assets/assetdb/momr-april-2004-1.pdf", "2004-04"),
        # The archive's own misspelling. Recon 05 section 1.2: without this the
        # index reports a hole in January 2008 that does not exist.
        ("https://www.opec.org/assets/assetdb/momr-janaury-2008.pdf", "2008-01"),
        ("https://www.opec.org/x/MOMR%20August%202015.pdf", "2015-08"),
        ("https://www.opec.org/x/OPEC%20MOMR%20August%202017.pdf", "2017-08"),
        ("https://www.opec.org/x/OPEC_MOMR_November-2012.pdf", "2012-11"),
        ("https://www.opec.org/x/momr-december-2026.pdf", "2026-12"),
        ("https://www.opec.org/x/annual-report-2020.pdf", None),
        ("https://www.opec.org/x/momr-cover.pdf", None),
    ],
)
def test_the_issue_month_is_read_off_every_filename_shape_the_archive_holds(
    url, expected
):
    assert issue_month_of_filename(url) == expected


def test_parse_cdx_prefers_the_canonical_url_and_counts_the_candidates():
    """Several captures of several URL shapes exist per issue.

    The choice is stated rather than left to the order the archive returned:
    the canonical /assets/assetdb/ shape first, then the largest capture, then
    the most recent.
    """
    text = "\n".join(
        [
            "20200101000000 https://www.opec.org/x/MOMR%20March%202026.pdf 200 application/pdf 900",
            "20250513133129 https://www.opec.org/assets/assetdb/momr-march-2026.pdf 200 application/pdf 100",
            "20190101000000 https://www.opec.org/x/momr-nothing.pdf 200 application/pdf 10",
            "20240101000000 https://www.opec.org/assets/assetdb/momr-janaury-2008.pdf 200 application/pdf 50",
        ]
    )
    index = parse_cdx(text)
    assert sorted(index) == ["2008-01", "2026-03"]
    assert index["2026-03"]["original"].endswith("momr-march-2026.pdf")
    assert index["2026-03"]["timestamp"] == "20250513133129"
    assert index["2026-03"]["candidates"] == 2
    assert index["2008-01"]["candidates"] == 1


def test_parse_cdx_ignores_lines_it_cannot_read():
    assert parse_cdx("") == {}
    assert parse_cdx("rubbish\nnot a timestamp https://x/momr-may-2020.pdf 200") == {}


# --------------------------------------------------------------------------
# The overlap rule
# --------------------------------------------------------------------------

def reading_for(issue: str, values: dict, specs: dict | None = None) -> IssueReading:
    return IssueReading(
        issue=issue,
        page=1,
        values={month(m): dict(v) for m, v in values.items()},
        specs=dict(specs or {"gasoil": "10 ppm", "gasoline": "unleaded 98"}),
    )


def test_the_latest_issue_wins_and_the_disagreement_is_kept_not_averaged():
    """THE OVERLAP RULE, which is the one judgement call in this adapter.

    Two issues print July. The later one is the revision, so its figure is the
    one cached, and the gap between them travels in the cache rather than being
    smoothed into a mean neither issue ever printed.
    """
    early = reading_for(
        "2024-08", {"2024-06": {"gasoil": 90.0, "gasoline": 80.0},
                    "2024-07": {"gasoil": 103.00, "gasoline": 107.00}}
    )
    late = reading_for(
        "2024-09", {"2024-07": {"gasoil": 103.06, "gasoline": 107.60},
                    "2024-08": {"gasoil": 95.52, "gasoline": 100.50}}
    )
    frame = build_frame([early, late]).set_index("date")

    july = frame.loc[month("2024-07")]
    assert july["gasoil_usd_bbl"] == pytest.approx(103.06)
    assert july["n_issues"] == 2
    assert july["source_issue"] == "2024-09"
    assert july["issues"] == "2024-08;2024-09"
    # The largest gap on any product: gasoline moved 0.60, gasoil 0.06.
    assert july["max_disagreement_usd_bbl"] == pytest.approx(0.60)

    june = frame.loc[month("2024-06")]
    assert june["n_issues"] == 1
    assert june["issues"] == "2024-08"
    assert np.isnan(june["max_disagreement_usd_bbl"])


def test_a_month_no_issue_reported_stays_in_the_frame_as_a_hole():
    """SPEC.md section 2 rule 1. A hole must be visible, not absent.

    A shorter frame hides a missing month. A row of NaN with n_issues of zero
    puts it in front of the manifest and the provenance panel.
    """
    first = reading_for("2024-02", {"2023-12": {"gasoil": 90.0, "gasoline": 80.0}})
    last = reading_for("2024-05", {"2024-03": {"gasoil": 95.0, "gasoline": 85.0}})
    frame = build_frame([first, last]).set_index("date")
    assert len(frame) == 4
    hole = frame.loc[month("2024-01")]
    assert hole["n_issues"] == 0
    assert hole["issues"] == ""
    assert hole["source_issue"] == ""
    assert np.isnan(hole["gasoil_usd_bbl"])


def test_build_frame_refuses_to_write_anything_when_no_issue_parsed():
    bad = IssueReading(issue="2024-09", error="nothing readable")
    with pytest.raises(SourceError) as caught:
        build_frame([bad])
    assert "no issue yielded a single month" in str(caught.value)


def test_the_specification_timeline_is_measured_from_the_data():
    frame = build_frame(
        [
            reading_for("2006-06", {"2006-05": {"gasoil": 86.03, "gasoline": 93.84}},
                        specs={"gasoil": "50 ppm", "gasoline": "unleaded 50 ppm"}),
            reading_for("2006-07", {"2006-06": {"gasoil": 87.0, "gasoline": 94.0}},
                        specs={"gasoil": "10 ppm", "gasoline": "unleaded 98"}),
        ]
    )
    timeline = specification_timeline(frame)
    gasoil = [row for row in timeline if row["product"] == "gasoil"]
    assert [row["specification"] for row in gasoil] == ["50 ppm", "10 ppm"]
    assert gasoil[1]["first_month"] == "2006-06"


def test_the_cache_columns_are_the_ones_the_adapter_declares():
    frame = build_frame([read("2024-09")])
    assert list(frame.columns) == list(opec_momr.CACHE_COLUMNS)
    for column in COLUMNS_BY_SLOT.values():
        assert column in frame.columns


# --------------------------------------------------------------------------
# The adapter
# --------------------------------------------------------------------------

def test_the_adapter_and_the_registry_agree():
    registered = SOURCES[SERIES]
    adapter = OpecRotterdamProductsMonthly()
    assert adapter.frequency == registered.frequency == "monthly"
    assert adapter.method == registered.method == "parsed"
    assert adapter.committable is registered.committable is True
    assert adapter.cache_file() == "data/cache/%s.csv" % SERIES
    # Every bounded column has an observation floor, which is what stops an all
    # NaN column replacing a good cache. base.Adapter refuses the class outright
    # without it, so this only has to say the floors are the right ones.
    assert set(adapter.bounds) == set(adapter.min_observations)
    assert set(adapter.bounds) == set(COLUMNS_BY_SLOT.values())


def test_the_pdfs_are_cached_outside_the_committed_tree():
    """The licence permits the information and forbids the report.

    So the parsed values are committed and the documents are not. data/private is
    gitignored, and this is the assertion that says the adapter puts them there.
    """
    assert opec_momr.PDF_DIR.parent == base.PRIVATE or base.PRIVATE in opec_momr.PDF_DIR.parents
    assert "private" in str(opec_momr.PDF_DIR).replace("\\", "/")


def test_the_adapter_writes_the_cache_the_manifest_and_the_breaks(sandbox, monkeypatch):
    """One end to end run with the network replaced. SPEC.md section 5.3.

    The floors come down to the size of the three fake issues, both of them
    together, because dropping min_observations to zero would turn off the guard
    that stops an all NaN column replacing a good cache.
    """
    # The second issue is the October 2024 one this project has not downloaded,
    # written by hand: it repeats August exactly as September printed it EXCEPT
    # for a 0.02 revision on gasoil, and adds September. All seven products are
    # present, because a fake issue carrying only the two required ones would
    # force the floors below down to zero on the other five and turn off the very
    # guard this test is supposed to leave switched on.
    august_as_revised = {
        "naphtha": 72.69,
        "gasoline": 100.50,
        "gasoline_95": 99.00,
        "jet": 96.18,
        "gasoil": 95.50,
        "fuel_oil_1pct": 72.14,
        "fuel_oil_35pct": 70.60,
    }
    september = {slot: value - 4.0 for slot, value in august_as_revised.items()}
    readings = [
        read("2024-09"),
        reading_for("2024-10", {"2024-08": august_as_revised, "2024-09": september}),
    ]
    monkeypatch.setattr(
        opec_momr, "fetch_issue_index", lambda **kw: {"2024-09": {}, "2024-10": {}}
    )
    monkeypatch.setattr(
        opec_momr, "collect_readings", lambda index, **kw: (readings, ["2026-04"])
    )

    adapter = OpecRotterdamProductsMonthly(download=False)
    adapter.min_rows = 3
    adapter.min_observations = {column: 2 for column in adapter.min_observations}
    entry = adapter.run()

    assert entry["status"] == "ok"
    assert entry["rows"] == 3
    assert entry["first_date"] == "2024-07-01"
    assert entry["last_date"] == "2024-09-01"
    assert entry["frequency"] == "monthly"
    assert entry["method"] == "parsed"
    assert entry["gaps"] == []
    assert entry["issues_indexed"] == 2
    assert entry["issues_parsed"] == 2
    assert entry["issues_not_downloaded"] == ["2026-04"]
    assert "Argus" in entry["attribution"]
    assert entry["specification_breaks"] == [dict(b) for b in SPECIFICATION_BREAKS]
    assert "latest issue" in entry["overlap_rule"].lower()
    assert "manual" in entry["unarchived_issues"].lower()

    written = base.read_cache(SERIES)
    assert list(written.columns) == list(opec_momr.CACHE_COLUMNS)
    august = written.set_index("date").loc[pd.Timestamp("2024-08-01")]
    # The later issue printed 95.50 where the earlier printed 95.52, and the
    # later one wins.
    assert august["gasoil_usd_bbl"] == pytest.approx(95.50)
    assert august["n_issues"] == 2
    assert august["max_disagreement_usd_bbl"] == pytest.approx(0.02, abs=1e-9)


def test_a_failing_fetch_keeps_the_previous_cache_and_marks_the_series_failed(
    sandbox, monkeypatch
):
    """SPEC.md section 5.4. A bad run must never cost a good cache."""
    good = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-07-01", "2024-08-01"]),
            **{column: [1.0, 2.0] for column in COLUMNS_BY_SLOT.values()},
        }
    )
    base.write_cache(SERIES, good)

    def explode(**kwargs):
        raise SourceError("the archive said no")

    monkeypatch.setattr(opec_momr, "fetch_issue_index", explode)
    adapter = OpecRotterdamProductsMonthly(download=False)
    with pytest.raises(SourceError):
        adapter.run()

    kept = base.read_cache(SERIES)
    assert len(kept) == 2
    entry = next(
        e for e in base.manifest_read()["series"] if e["series"] == SERIES
    )
    assert entry["status"] == "failed"
    assert "the archive said no" in entry["note"]


# --------------------------------------------------------------------------
# Gate 1 audit: a revision and a respecification, kept apart
# --------------------------------------------------------------------------
#
# THE FINDING THESE TESTS LOCK DOWN. The first build of this adapter carried one
# column, max_disagreement_usd_bbl, for every gap between two issues on one
# month, and 27 of 305 months carried a non zero value, the worst 21.28 $/bbl.
# The Gate 1 audit re-read the Rotterdam block of every issue involved by WORD
# COORDINATES, clustering pdfplumber's words by their vertical centre and giving
# each number to the label whose row it physically shares, rather than by
# pdfplumber's assembled text lines. The geometric reading agreed with the
# parser on every one of the 27 months and on the undisputed months read beside
# them, so none of it was an extraction artifact and none of it was fixed by
# touching the extraction.
#
# What was wrong was the measurement. Most of those 27 months were the Rotterdam
# row SET changing, so one slot held two different products either side, and the
# parser reported that as the source disagreeing with itself. Separating the two
# leaves the months where two issues really do print different numbers under the
# same row label, and February and March 2012 are the largest of them.

def test_a_respecification_is_not_a_disagreement_may_and_june_2005():
    """Two real issues, one month, and the row set changes between them.

    The May 2005 issue prints "Gasoil (0.2% S)" and one premium gasoline row.
    The June 2005 issue prints "Gasoil/Diesel (50 ppm)" and two. March 2005
    gasoil is 64.60 in the first and 69.30 in the second, and that 4.70 is two
    products, not one product revised. The proof it is not a revision is in the
    same block: the "unleaded 95" row is 56.03 in BOTH issues, unchanged.
    """
    may = read("2005-05")
    june = read("2005-06")
    assert may.ok and june.ok
    march = month("2005-03")

    assert may.specs["gasoil"] == "0.2% S"
    assert june.specs["gasoil"] == "50 ppm"
    assert may.values[march]["gasoil"] == pytest.approx(64.60)
    assert june.values[march]["gasoil"] == pytest.approx(69.30)

    # The one row whose label did not change did not move at all.
    assert may.specs["gasoline"] == "unleaded 95"
    assert june.specs["gasoline_95"] == "unleaded 95"
    assert may.values[march]["gasoline"] == pytest.approx(56.03)
    assert june.values[march]["gasoline_95"] == pytest.approx(56.03)

    frame = build_frame([may, june]).set_index("date")
    row = frame.loc[march]
    assert row["n_issues"] == 2
    # Gasoline moves 56.03 to 62.03 and gasoil 64.60 to 69.30, so the widest
    # respecification gap on the month is the gasoline row's 6.00.
    assert row["max_respec_gap_usd_bbl"] == pytest.approx(6.00)
    assert "gasoil:0.2% S|50 ppm" in row["respecified"]
    assert "gasoline:unleaded 50 ppm|unleaded 95" in row["respecified"]
    # The naphtha, jet and fuel oil rows kept their labels and their numbers, so
    # the like for like disagreement is zero and it is reported as zero.
    assert row["max_disagreement_usd_bbl"] == pytest.approx(0.0)
    # The latest issue still wins, and the specification travels with the value.
    assert row["gasoil_usd_bbl"] == pytest.approx(69.30)
    assert row["gasoil_spec"] == "50 ppm"
    assert row["source_issue"] == "2005-06"


def test_february_2012_is_a_real_disagreement_under_one_unchanged_label():
    """The largest gap in the sample, and it survives every explanation.

    Both issues print the same three Rotterdam row labels. Naphtha, jet and both
    fuel oils agree to 0.27 $/bbl, which is an ordinary revision. The premium
    gasoline 10 ppm row moves 13.53 and the gasoil row 8.80, on labels that did
    not change. The word coordinate re-read says both pages were read exactly as
    printed. So OPEC restated two rows of one block and this study cannot say
    which vintage is right: it keeps the later one, per the overlap rule, and
    puts the size of the disagreement on the record.
    """
    april = read("2012-04")
    may = read("2012-05")
    assert april.ok and may.ok
    feb, mar = month("2012-02"), month("2012-03")

    # The labels are identical, which is what makes this a disagreement.
    for reading in (april, may):
        assert reading.specs["gasoline"] == "unleaded 10 ppm"
        assert reading.specs["gasoline_95"] == "unleaded 95"
        assert reading.specs["gasoil"] == "10 ppm"

    assert april.values[feb]["gasoline"] == pytest.approx(129.29)
    assert may.values[feb]["gasoline"] == pytest.approx(115.76)
    assert april.values[feb]["gasoil"] == pytest.approx(142.59)
    assert may.values[feb]["gasoil"] == pytest.approx(133.79)
    # and the rows that were only revised, for contrast
    assert april.values[feb]["naphtha"] == pytest.approx(113.65)
    assert may.values[feb]["naphtha"] == pytest.approx(113.70)
    assert april.values[feb]["jet"] == pytest.approx(134.66)
    assert may.values[feb]["jet"] == pytest.approx(134.39)

    frame = build_frame([april, may]).set_index("date")
    row = frame.loc[feb]
    assert row["n_issues"] == 2
    assert row["respecified"] == ""
    assert np.isnan(row["max_respec_gap_usd_bbl"])
    assert row["max_disagreement_usd_bbl"] == pytest.approx(13.53)
    # The later issue wins, unchanged by any of this.
    assert row["gasoil_usd_bbl"] == pytest.approx(133.79)
    assert row["premium_gasoline_usd_bbl"] == pytest.approx(115.76)
    assert row["source_issue"] == "2012-05"

    assert frame.loc[mar]["max_disagreement_usd_bbl"] == pytest.approx(21.28)


def test_the_2012_gasoline_rows_are_not_a_column_misalignment():
    """The first explanation tried, and ruled out on the documents.

    A column misalignment would show in the header. Both issues date their three
    columns correctly and consecutively, and the parser reads those dates off the
    header line rather than off the column order.
    """
    april = read("2012-04")
    may = read("2012-05")
    assert sorted(april.values) == [
        month("2012-01"), month("2012-02"), month("2012-03")
    ]
    assert sorted(may.values) == [
        month("2012-02"), month("2012-03"), month("2012-04")
    ]
    # The two issues overlap on February and March and agree on the months
    # themselves, so the disagreement is inside a column and not between columns.
    assert april.values[month("2012-03")]["naphtha"] == pytest.approx(118.32)
    assert may.values[month("2012-03")]["naphtha"] == pytest.approx(118.19)


def test_a_disagreement_is_measured_only_between_issues_that_agree_on_the_row():
    """The rule itself, on constructed readings so the arithmetic is visible.

    Three issues print one month. Two of them call the gasoil row 10 ppm and
    differ by 0.06, which is a revision. The third calls it 50 ppm and sits
    9.00 below, which is a different product. The revision is 0.06 and the
    respecification is 9.06, and neither is allowed to stand in for the other.
    """
    old = reading_for(
        "2024-07", {"2024-07": {"gasoil": 94.00}}, specs={"gasoil": "50 ppm"}
    )
    mid = reading_for(
        "2024-08", {"2024-07": {"gasoil": 103.00}}, specs={"gasoil": "10 ppm"}
    )
    new = reading_for(
        "2024-09", {"2024-07": {"gasoil": 103.06}}, specs={"gasoil": "10 ppm"}
    )
    row = build_frame([old, mid, new]).set_index("date").loc[month("2024-07")]
    assert row["n_issues"] == 3
    assert row["max_disagreement_usd_bbl"] == pytest.approx(0.06)
    assert row["max_respec_gap_usd_bbl"] == pytest.approx(9.06)
    assert row["respecified"] == "gasoil:10 ppm|50 ppm"
    assert row["gasoil_usd_bbl"] == pytest.approx(103.06)


def test_two_issues_that_share_no_specification_report_no_cross_check():
    """Not agreement, and not zero. No measurement, recorded as none.

    A zero in max_disagreement_usd_bbl would say two issues printed the same
    number. When the only slot they share was specified differently they printed
    no comparable number at all, and saying zero would be a claim the documents
    do not support.
    """
    old = reading_for(
        "2024-08", {"2024-07": {"gasoil": 94.00}}, specs={"gasoil": "50 ppm"}
    )
    new = reading_for(
        "2024-09", {"2024-07": {"gasoil": 103.06}}, specs={"gasoil": "10 ppm"}
    )
    row = build_frame([old, new]).set_index("date").loc[month("2024-07")]
    assert row["n_issues"] == 2
    assert np.isnan(row["max_disagreement_usd_bbl"])
    assert row["max_respec_gap_usd_bbl"] == pytest.approx(9.06)


def test_the_new_columns_reach_the_cache_layout():
    """They are worthless if they do not reach the cache and therefore the site."""
    assert opec_momr.COLUMN_RESPEC_GAP in opec_momr.CACHE_COLUMNS
    assert opec_momr.COLUMN_RESPECIFIED in opec_momr.CACHE_COLUMNS
    frame = build_frame([reading_for("2024-09", {"2024-08": {"gasoil": 95.52}})])
    assert list(frame.columns) == list(opec_momr.CACHE_COLUMNS)
