"""The OPEC Monthly Oil Market Report Rotterdam barge product prices.

    series      opec_rotterdam_products_monthly
    cache       data/cache/opec_rotterdam_products_monthly.csv
    columns     date, naphtha_usd_bbl, premium_gasoline_usd_bbl,
                premium_gasoline_95_usd_bbl, jet_usd_bbl, gasoil_usd_bbl,
                fuel_oil_1pct_usd_bbl, fuel_oil_35pct_usd_bbl,
                gasoline_spec, gasoil_spec,
                n_issues, max_disagreement_usd_bbl, max_respec_gap_usd_bbl,
                respecified, source_issue, issues
    unit        US dollars per barrel
    source      OPEC Monthly Oil Market Report, table "Refined product prices,
                US$/b", block "Rotterdam (Barges FOB)". Assessments credited to
                Argus.
    page        https://www.opec.org/monthly-oil-market-report.html

This is the headline crack source, the one the study is named after. It is the
only free, citable, monthly Rotterdam barge product price series this project
found, it is quoted in DOLLARS PER BARREL so the crack is a subtraction with no
tonne to barrel conversion argument in it, and it runs from October 2000, which
means the sample covers 2008, 2015, 2020, 2022, 2023 and 2026 rather than only
the last two. Recon 05 part one and part three set all of that out.

WHERE THE ISSUES COME FROM, AND WHY NOT FROM OPEC
-------------------------------------------------
opec.org answers HTTP 403 with a Cloudflare managed challenge to every scripted
request from this machine, on every path recon 05 section 1.1 tried, including
the PDF delivery endpoint. Nothing here talks to opec.org. The issues come from
the Internet Archive, whose CDX index is queried live and never hardcoded:

    http://web.archive.org/cdx/search/cdx?url=opec.org*
      &filter=original:.*[Mm][Oo][Mm][Rr].*\\.pdf
      &filter=mimetype:application/pdf&filter=statuscode:200

and each issue is then retrieved through the id_ form of the Wayback replay URL,
which returns the raw PDF with no rewriting and no banner:

    https://web.archive.org/web/<timestamp>id_/<original url>

The index is discovered rather than constructed for three reasons that all come
out of the CDX listing itself. The timestamp differs per issue and cannot be
guessed. The filename has at least five shapes over twenty five years,
momr-march-2026.pdf, momr-april-2004-1.pdf, MOMR%20August%202015.pdf,
OPEC%20MOMR%20August%202017.pdf and OPEC_MOMR_November-2012.pdf. And January
2008 is filed under the misspelling momr-janaury-2008.pdf, so a constructed URL
would report a hole that does not exist.

Six issues, April to September 2026, are not in the archive and could not be
fetched, so the series ends where the archive ends. That is recorded in the
manifest as unarchived_issues and in the note, because a hole that is reported is
a fact and a hole that is filled is a fabrication, SPEC.md section 2 rule 1.

PARSE BY LABEL, ACROSS FIVE LAYOUT ERAS
----------------------------------------
Recon 05 section 1.4 opened eleven issues spanning five eras and read the table
out of every one. The block header, the product row labels and the month column
headers all move, so nothing here is read by position:

    the page          is found by its own title line, "Refined product prices",
                      together with a line that starts with "Rotterdam". The page
                      NUMBER moves from 10 of 25 in 2001 to 70 of 96 in 2026, so
                      the search starts at 70 percent of the way through the
                      document and spirals outward instead of opening every page.
    the block         is the line whose text starts with "Rotterdam", case
                      insensitively, because the wording changes from
                      "Rotterdam" to "Rotterdam (Barges FoB):" to
                      "Rotterdam (Barges FOB)" between eras. It ends at the next
                      block header or at the table note.
    the columns       are read off the header line, which carries two or three
                      month tokens, then one change token, then zero or two year
                      tokens. Every product row must then carry exactly that many
                      numbers, which is the check that catches a column appearing
                      or disappearing.
    the product rows  are split by taking numbers off the END of the line until a
                      token is not a number, so the label keeps its parenthesised
                      specification and "Premium gasoline (unleaded 98)" cannot
                      lose its 98 to the value columns. The remaining label is
                      then matched against PRODUCT_LABELS exactly, after
                      whitespace is removed and case is folded.

A row whose label is not in PRODUCT_LABELS is NOT guessed at. It is recorded in
the reading as an unknown label and its numbers are thrown away. If that costs
the issue its gasoil or its gasoline row, the issue fails and writes nothing,
which is the SPEC.md section 13 rule that a column that moves must break loudly
rather than silently return the wrong product.

TWO SPECIFICATION BREAKS, IN THE DATA AND NOT ONLY IN A COMMENT
---------------------------------------------------------------
The gasoil row is "Gasoil (0.2% S)" in 2001, "Gasoil/Diesel (50 ppm)" in 2006 and
"Gasoil/Diesel (10 ppm)" from 2011. The gasoline row is "Premium gasoline
(unleaded)" to 2003, then "(unleaded 50 ppm)" and "(unleaded 95)" together, then
"(unleaded 10 ppm)" and "(unleaded 95)" together, then "(unleaded 98)" alone from
2015. Those are two structural breaks in a series that otherwise looks
continuous, and a chart that spans them must mark them.

So the specification travels WITH EVERY ROW, in gasoil_spec, gasoline_spec and
exactly as printed. The site reads the break off the data rather
than off a constant in a module it cannot see, and SPECIFICATION_BREAKS carries
the same fact in the manifest for the provenance panel.

TWO GASOLINE ROWS, AND WHY NEITHER IS DROPPED
----------------------------------------------
Between roughly 2004 and 2014 the Rotterdam block prints two premium gasoline
rows at once, a sulphur graded one and an octane graded one. Picking one of them
to be "the" gasoline series would be a judgement about product continuity made
silently inside a parser. Both are kept instead:

    premium_gasoline_usd_bbl      the leading premium grade of the issue,
                                  whatever its specification, with gasoline_spec
                                  saying which grade that is
    premium_gasoline_95_usd_bbl   the octane graded "unleaded 95" row, wherever
                                  the issue printed it

They are assigned by SPECIFICATION and never by printed position, because the
position moves: "unleaded 95" is the only gasoline row from August 2004 to May
2005 and the SECOND row from June 2005 to September 2013, under a sulphur graded
row that runs 50 ppm then 10 ppm. Reading by position would move the 95 line from
one column to the other in June 2005 with no symptom at all. In the ten issues
where 95 is the only row it lands in both columns, which is a duplication the
source forces and which gasoline_spec makes readable.

Which of the two continues the OPEC Annual Statistical Bulletin's own
"Gasoline - Premium unleaded 98" row is a measurable question, and the Gate 1
audit measured it. THE ANSWER IS THAT NEITHER COLUMN DOES, AND THAT IS A FINDING
THIS STUDY HAS TO PUBLISH RATHER THAN RESOLVE.

Against ASB table 7.6, Rotterdam block, 1980 to 2022 in $/b, downloaded to
data/private/probe/cracks/ASB_T76.xlsx, taking the 22 complete calendar years
this cache covers and comparing the ASB annual average with the mean of the
twelve monthly values:

    gasoil 10 ppm        mean error -0.09, mean absolute 0.17, worst 0.98
    fuel oil 3.5 percent mean error +0.32, mean absolute 0.48, worst 3.82 in 2020
    premium gasoline     mean error -0.40, mean absolute 1.79, worst 15.32

The gasoline errors are not spread out. Eighteen of the 22 years agree to 0.01 or
better and four do not, and in every one of those four the OTHER gasoline column
is the one that agrees exactly:

    year   ASB      premium_gasoline   premium_gasoline_95
    2005   62.58    68.90  (+6.32)     62.58  (-0.00)
    2006   72.90    81.73  (+8.83)     72.90  (-0.00)
    2012   127.29   111.97 (-15.32)    127.13 (-0.16)
    2013   122.57   115.22 (-7.35)     123.21 (+0.64)

and in 2007 to 2011, with no label change anywhere in between, it is the other
way round: premium_gasoline agrees to 0.01 to 1.31 and premium_gasoline_95 sits
2.73 to 9.98 below. So OPEC's own annual restatement onto a single "premium
unleaded 98" definition does not follow either printed row consistently, and no
rule keyed on the printed label reproduces it. A monthly premium gasoline series
spliced across 2004 to 2013 is therefore NOT one product, whichever column it is
built from, and the site must say so wherever it draws one.

Both columns stay as printed, gasoline_spec stays with every value, and the
choice is left to the reader rather than made here.

AND IN TWENTY MONTHS THE TWO ROWS EXCHANGE VALUES. That is the sharp end of the
same problem and it has its own record, GASOLINE_ROW_DISPUTE below: through 2012
and the first half of 2013 the headline column carries the LOWER of the two
readings and the crack it gives is negative in eight months, which is not a
market anybody traded. The months are found by rule rather than typed, the
evidence is recorded issue by issue, and the site draws both rows over them.

THE OVERLAP RULE
-----------------
Every issue prints two or three months, so most months are printed by two or
three different issues, and OPEC revises: the old layout carries a footnote
"R Revised since last issue". That overlap is free validation and it is used
rather than collapsed:

    THE RULE. For each month and each product the value written to the cache is
    the one printed by the LATEST issue that carries that month, because a later
    issue is the revision of an earlier one and never the other way round. Every
    issue that carried the month is still counted in n_issues, the largest
    absolute disagreement between any two issues on any product of that month is
    carried in max_disagreement_usd_bbl, the winning issue is named in
    source_issue and every issue that reported the month is named in issues.

A month with n_issues of 1 had no cross check. A month with a large
max_disagreement_usd_bbl is a revision or a parse problem and the site can show
which months those are. Nothing is averaged: averaging two vintages of one figure
would produce a number neither issue ever printed.

A REVISION AND A RESPECIFICATION ARE NOT THE SAME THING
--------------------------------------------------------
The overlap rule above was measured against the whole archive in the Gate 1
audit, and it conflated two facts that must be separated, because one is the
source correcting itself and the other is the source changing what it is
quoting.

    A REVISION is two issues printing different numbers on THE SAME printed row
    label, for example the November 2001 issue printing "29.01R" where the
    October issue printed 29.01 without the marker. Those are what
    max_disagreement_usd_bbl is for, and the old layout's own footnote,
    "R Revised since last issue", says so.

    A RESPECIFICATION is the row set itself changing between two issues, so the
    same slot holds a different product either side. In June 2005 the Rotterdam
    gasoil row goes from "Gasoil (0.2% S)" to "Gasoil/Diesel (50 ppm)", and the
    March 2005 gasoil printed by the May issue, 64.60, and by the June issue,
    69.30, are two different products, not one product revised by 4.70.

Before the Gate 1 audit both landed in max_disagreement_usd_bbl, which reported
a respecification as a 7 $/bbl disagreement and hid a genuine 21 $/bbl one among
them. They are now separated:

    max_disagreement_usd_bbl   the widest gap between issues that printed THE
                               SAME specification for that slot. A revision.
    max_respec_gap_usd_bbl     the widest gap between issues that printed
                               DIFFERENT specifications for the same slot. A
                               respecification, and not a disagreement at all.
    respecified                which slots, with both specifications, verbatim.

Neither reading is discarded and nothing is averaged: the cache still carries the
latest issue's value, and both numbers stay visible so a chart can draw the break
where the source put it.

LICENCE
--------
The MOMR disclaimer permits the information to be "used and/or reproduced for
educational and other non-commercial purposes without the OPEC Secretariat's
prior written permission, provided that it is fully acknowledged as the copyright
holder", and forbids full reproduction of the report itself. The table credits
Argus, and OPEC's own wording reserves third party copyright.

So the PARSED VALUES are cached and committed and the PDFs are NOT. They are kept
under data/private/momr/, which is gitignored, never committed and never
deployed. Credit "Argus, via the OPEC Monthly Oil Market Report" wherever these
numbers appear.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import unquote

import numpy as np
import pandas as pd

from ..config import BOUNDS_PRODUCT_USD_BBL
from ..config import source as registered_source
from .base import PRIVATE, Adapter, SourceError, http_get

__all__ = [
    "SERIES",
    "COLUMNS_BY_SLOT",
    "SLOTS",
    "PRODUCT_LABELS",
    "SPECIFICATION_BREAKS",
    "GASOLINE_ROW_DISPUTE",
    "gasoline_dispute_months",
    "CDX_URL",
    "WAYBACK_RAW",
    "PDF_DIR",
    "PROBE_DIR",
    "TABLE_TITLE",
    "BLOCK_LABEL",
    "IssueReading",
    "label_key",
    "is_number",
    "to_float",
    "split_label_and_numbers",
    "parse_header_columns",
    "page_is_table",
    "parse_table_page",
    "locate_table_page",
    "read_issue_pdf",
    "issue_month_of_filename",
    "parse_cdx",
    "fetch_issue_index",
    "issue_pdf_path",
    "download_issue",
    "collect_readings",
    "build_frame",
    "OpecRotterdamProductsMonthly",
    "main",
]


# --------------------------------------------------------------------------
# Names
# --------------------------------------------------------------------------

#: Cache stem and manifest series name. A key of crack.config.SOURCES, and
#: Adapter._check_declarations cross checks this module against that registry on
#: frequency, method and committable before anything is fetched.
SERIES = "opec_rotterdam_products_monthly"

#: The canonical product slots, and the cache column each one writes. The unit is
#: in every column name because the DGEC series next to it in data/cache is in
#: dollars per TONNE and the two must never be confused in a formula.
COLUMNS_BY_SLOT: Mapping[str, str] = {
    "naphtha": "naphtha_usd_bbl",
    "gasoline": "premium_gasoline_usd_bbl",
    "gasoline_95": "premium_gasoline_95_usd_bbl",
    "jet": "jet_usd_bbl",
    "gasoil": "gasoil_usd_bbl",
    "fuel_oil_1pct": "fuel_oil_1pct_usd_bbl",
    "fuel_oil_35pct": "fuel_oil_35pct_usd_bbl",
}

#: Value slots in cache column order.
SLOTS: tuple[str, ...] = tuple(COLUMNS_BY_SLOT)

#: The two slots without which an issue is a failed parse rather than a thin one.
#: They are the two the study is named after. Naphtha, jet and fuel oil 1.0
#: percent genuinely do not exist in the early layout, so their absence is a fact
#: about 2001 and not a parser failure.
REQUIRED_SLOTS: tuple[str, ...] = ("gasoil", "gasoline")

#: Product row labels, exactly as the report prints them, keyed by the label with
#: whitespace removed and case folded. Every variant here was read off a real
#: issue; recon 05 section 1.4 lists the eleven issues and the era each belongs
#: to. The value is (slot, specification as printed).
#:
#: A label that is not in this table is never guessed at. See _match_product.
PRODUCT_LABELS: Mapping[str, tuple[str, str]] = {
    "naphtha": ("naphtha", "Naphtha"),
    "naphtha*": ("naphtha", "Naphtha, barges"),
    # Gasoline. Two rows appear together in the middle eras, see the module
    # docstring, so the slot assigned here is always "gasoline" and the first and
    # second row of the block are separated by _assign_gasoline.
    "premiumgasoline(unleaded)": ("gasoline", "unleaded"),
    "premiumgasoline(unleaded50ppm)": ("gasoline", "unleaded 50 ppm"),
    # February to August 2008 footnote the specification with an asterisk. It is
    # the same row and the same product, and it is listed separately rather than
    # matched by stripping punctuation, because a rule that dropped characters
    # from a specification is a rule that could also drop the difference between
    # 50 ppm and 10 ppm.
    "premiumgasoline(unleaded50ppm*)": ("gasoline", "unleaded 50 ppm"),
    "premiumgasoline(unleaded10ppm)": ("gasoline", "unleaded 10 ppm"),
    "premiumgasoline(unleaded10ppm*)": ("gasoline", "unleaded 10 ppm"),
    "premiumgasoline(unleaded95)": ("gasoline", "unleaded 95"),
    "premiumgasoline(unleaded98)": ("gasoline", "unleaded 98"),
    "jet/kerosene": ("jet", "Jet/Kerosene"),
    # Gasoil, the other side of the specification break.
    "gasoil(0.2%s)": ("gasoil", "0.2% S"),
    "gasoil(0.2%)": ("gasoil", "0.2%"),
    "gasoil(0.05%s)": ("gasoil", "0.05% S"),
    "gasoil/diesel(0.2%s)": ("gasoil", "0.2% S"),
    "gasoil/diesel(50ppm)": ("gasoil", "50 ppm"),
    "gasoil/diesel(50ppm*)": ("gasoil", "50 ppm"),
    "gasoil/diesel(10ppm)": ("gasoil", "10 ppm"),
    "gasoil/diesel(10ppm*)": ("gasoil", "10 ppm"),
    "fueloil(1.0%s)": ("fuel_oil_1pct", "1.0% S"),
    "fueloil(1%s)": ("fuel_oil_1pct", "1% S"),
    "fueloil(3.5%s)": ("fuel_oil_35pct", "3.5% S"),
    "fueloil(3.5%)": ("fuel_oil_35pct", "3.5%"),
}

#: The specification of the octane graded gasoline row. Between August 2004 and
#: September 2013 the Rotterdam block prints this row alongside the sulphur
#: graded one, and it is the only row of the two whose definition never changes,
#: so it gets a column of its own and is always put in it. See _assign_gasoline.
GASOLINE_95 = "unleaded 95"

#: Labels this parser knows, has seen in a real Rotterdam block, and deliberately
#: does not carry, with the reason. They are recorded per issue in
#: IssueReading.ignored_labels and counted in the manifest, so "not carried" is a
#: visible decision rather than a silent drop.
#:
#: The distinction from an unknown label matters: an unknown label is a row
#: nobody has looked at and is a reason to go and read the document, and one of
#: these is a row somebody looked at and decided against.
IGNORED_LABELS: Mapping[str, str] = {
    "regulargasoline(unleaded)": (
        "The regular grade, printed in the Rotterdam block only from August 2004 "
        "to May 2005, ten issues in twenty five years. This study's gasoline "
        "crack is the premium grade, SPEC.md section 4.2, and a column that "
        "existed for twelve months would be more misleading on a chart than "
        "useful."
    ),
}

#: SPEC.md section 4.2 and section 6.5 want structural breaks marked on every
#: chart that spans them. These two are properties of the SOURCE, not of the
#: market, and they are carried here so the manifest and therefore the site can
#: read them. The same fact also travels per row in the gasoil_spec,
#: gasoline_spec columns, which is what a chart actually
#: needs in order to draw the break where it happened rather than where a
#: constant says it did.
#:
#: The dates are deliberately RANGES, not points. Recon 05 section 1.4 opened
#: eleven issues and bounded each transition between the two issues on either
#: side of it; the exact issue in which the label changed is narrowed by the
#: build itself, which reports first_month per specification in the manifest.
SPECIFICATION_BREAKS = (
    {
        "product": "gasoil",
        "column": "gasoil_usd_bbl",
        "spec_column": "gasoil_spec",
        "sequence": ["0.2% S", "50 ppm", "10 ppm"],
        "what": (
            "The Rotterdam gasoil row is a 0.2 percent sulphur gasoil in 2001 and "
            "2003, a 50 ppm gasoil/diesel in 2006 and a 10 ppm gasoil/diesel from "
            "2011. Sulphur specification drives the price, so the level before "
            "and after a change is not the same product and the series is not "
            "continuous across it."
        ),
        "source": "OPEC MOMR, refined product prices table, recon 05 section 1.4",
    },
    {
        "product": "gasoline",
        "column": "premium_gasoline_usd_bbl",
        "spec_column": "gasoline_spec",
        "sequence": [
            "unleaded",
            "unleaded 50 ppm",
            "unleaded 10 ppm",
            "unleaded 95",
            "unleaded 98",
        ],
        "what": (
            "The Rotterdam premium gasoline row is an unspecified unleaded grade "
            "to 2003, then a sulphur graded row and an octane graded row printed "
            "side by side through the middle of the sample, then premium unleaded "
            "98 alone from 2015. Octane and sulphur are both priced, so this is a "
            "break in the definition of the series and not a move in the market."
        ),
        "source": "OPEC MOMR, refined product prices table, recon 05 section 1.4",
    },
)


# --------------------------------------------------------------------------
# The gasoline row dispute
# --------------------------------------------------------------------------
#
# THE TWO GASOLINE ROWS EXCHANGE VALUES BETWEEN ISSUES, AND THE SITE SHOWS BOTH
# READINGS RATHER THAN PICKING ONE.
#
# The module docstring above already says that neither printed row continues
# OPEC's own annual restatement consistently. This is the sharper form of the
# same problem, and it is sharper because it is visible on a public chart:
# through 2012 and the first half of 2013 the HEADLINE column, the sulphur
# graded row, prints a Rotterdam premium gasoline BELOW dated Brent in eight
# months. A Rotterdam gasoline crack below zero for most of a year is not a
# market anybody traded, and drawing it as a single unannotated line would be
# this study publishing an artefact of a parsing convention as a market fact.
#
# The answer is NOT to switch to the row that looks right. That would be
# choosing a winner to make a chart behave, which SPEC.md section 2 rule 3
# forbids as plainly as it forbids inventing a number. The answer is to draw
# both printed rows over the months in question, say what the evidence is, and
# leave the choice open, which is what this record exists to let the site do.
#
# WHICH MONTHS, BY RULE AND NOT BY EYE. In every month of the two row overlap
# from March 2005 onward the octane graded row prints BELOW the sulphur graded
# one, by 0.89 to 16.63 $/bbl, which is the ordering an octane spread would
# give if the sulphur graded row were the higher specification. The months this
# record marks are the months where that ordering REVERSES. They are found by
# the rule below, applied to the committed cache, never by a typed list of
# dates, so a later issue that changes the picture changes the marked window
# with it.
GASOLINE_ROW_DISPUTE: Mapping[str, Any] = {
    "id": "opec_gasoline_two_rows",
    "column": "premium_gasoline_usd_bbl",
    "alternative_column": "premium_gasoline_95_usd_bbl",
    "rule": (
        "a month of the two row overlap in which the octane graded row, unleaded "
        "95, prints ABOVE the sulphur graded row that the headline column "
        "carries, reversing the ordering that holds in every other month of the "
        "overlap"
    ),
    "what": (
        "OPEC printed two Rotterdam premium gasoline rows at once from May 2004 "
        "to June 2013, a sulphur graded one and an octane graded one, and in "
        "these months the two exchange values between consecutive issues: the "
        "figure one issue prints on the sulphur graded row is the figure the "
        "next issue prints on the octane graded row. The headline column of this "
        "cache follows the sulphur graded label, so in these months it carries "
        "the lower of the two readings and the crack it gives falls below zero. "
        "Which row continues the series is NOT resolved here."
    ),
    "consequence": (
        "The gasoline crack in the marked months is drawn twice, once on each "
        "printed row, and the choice between them is left to the reader. "
        "Everything else on this site that reads OPEC gasoline is reported both "
        "ways wherever the two disagree."
    ),
    # THE SWAP, READ OFF FOUR ISSUES. Each pair is the SAME month printed by two
    # consecutive issues, both rows, verbatim. These are measurements taken from
    # the archived PDFs under data/private/momr, which the licence forbids
    # committing, so they are recorded here with the issue that carried them
    # rather than recomputed from a file a clean checkout does not have.
    "issue_evidence": (
        {
            "month": "2012-02",
            "headline_spec": "unleaded 10 ppm",
            "earlier_issue": "2012-04",
            "earlier_headline": 129.29,
            "earlier_alternative": 126.58,
            "later_issue": "2012-05",
            "later_headline": 115.76,
            "later_alternative": 129.34,
        },
        {
            "month": "2012-03",
            "headline_spec": "unleaded 10 ppm",
            "earlier_issue": "2012-04",
            "earlier_headline": 141.01,
            "earlier_alternative": 138.05,
            "later_issue": "2012-05",
            "later_headline": 119.73,
            "later_alternative": 140.30,
        },
    ),
    "issue_evidence_note": (
        "February 2012 as the April 2012 issue printed it, 129.29 on the sulphur "
        "graded row, is February 2012 as the May 2012 issue printed it on the "
        "octane graded row, 129.34, to within 0.05 $/bbl; March 2012 moves the "
        "same way, 141.01 to 140.30. The sulphur graded row falls 13.53 and 21.28 "
        "$/bbl in the same two issues while naphtha moves 0.05, jet 0.27 and both "
        "fuel oils 0.12 or less, and the Mediterranean block of the two issues "
        "prints February 2012 identically. The three months of 2010 this rule "
        "also marks carry the reversal with no restatement behind it: the May "
        "2010 issue prints April 2010 with the octane row 7.32 $/bbl below the "
        "sulphur graded one, the June 2010 issue prints May 2010 with it 4.31 "
        "$/bbl above, and the ordering goes back the other way after July 2010."
    ),
    # OPEC'S OWN ANNUAL RESTATEMENT, the one external check there is. Annual
    # Statistical Bulletin table 7.6, Rotterdam block, "Gasoline - Premium
    # unleaded 98", in $/b, against the mean of this cache's twelve monthly
    # values for the same year. "alternative" is the octane graded row where the
    # issues printed one and the headline row where they did not, which is the
    # only like for like comparison against a twelve month annual average: the
    # octane row stops in June 2013 and a six month mean is not an annual one.
    "annual_check": (
        {"year": 2005, "asb": 62.58, "headline": 68.90, "alternative": 62.58},
        {"year": 2006, "asb": 72.90, "headline": 81.73, "alternative": 72.90},
        {"year": 2007, "asb": 92.03, "headline": 92.02, "alternative": 82.05},
        {"year": 2008, "asb": 108.27, "headline": 108.16, "alternative": 98.46},
        {"year": 2009, "asb": 70.45, "headline": 70.51, "alternative": 65.57},
        {"year": 2010, "asb": 92.35, "headline": 91.04, "alternative": 88.70},
        {"year": 2011, "asb": 120.35, "headline": 120.42, "alternative": 117.62},
        {"year": 2012, "asb": 127.29, "headline": 111.97, "alternative": 127.14},
        {"year": 2013, "asb": 122.57, "headline": 115.22, "alternative": 122.64},
    ),
    "annual_check_note": (
        "The bulletin agrees with the octane graded reading to 0.16 $/b or better "
        "in 2005, 2006, 2012 and 2013 and with the headline reading to 1.31 $/b "
        "or better in 2007 to 2011, with no label change anywhere between 2006 "
        "and 2007. So OPEC's own annual restatement follows NEITHER printed row "
        "consistently and cannot settle the question either; what it does say is "
        "that in the two disputed years it agrees with the row this cache does "
        "not carry, and by 15.32 and 7.35 $/b."
    ),
    "unresolved": (
        "This is not resolvable from published documents. Both readings are "
        "printed by OPEC, both are carried in the cache, and the site says so "
        "wherever it draws a gasoline line across these months."
    ),
    "sources": (
        {
            "title": "OPEC Monthly Oil Market Report, refined product prices, Rotterdam barges FOB",
            "url": "https://www.opec.org/monthly-oil-market-report.html",
        },
        {
            "title": "OPEC Annual Statistical Bulletin, table 7.6, spot prices",
            "url": "https://www.opec.org/annual-statistical-bulletin.html",
        },
    ),
}


def gasoline_dispute_months(
    frame: pd.DataFrame,
    headline: str | None = None,
    alternative: str | None = None,
) -> pd.Series:
    """True for each row of the cache that GASOLINE_ROW_DISPUTE["rule"] marks.

    The rule and nothing else: both gasoline columns present and the octane
    graded one above the headline one. No date is typed anywhere, so the window
    the site draws is whatever the committed values say it is, and a later issue
    that moves a value moves the window with it.

    Subtracting Brent from both rows does not change which is larger, so this
    answers the same on the cache's two price columns and on the two cracks
    computed from them; the column names are arguments so that either pair can be
    passed without a second copy of the rule.

    Args:
        frame: any frame carrying the two gasoline columns.
        headline: the column of the row the cache leads with. Defaults to the
            cache's own name for it.
        alternative: the column of the octane graded row. Same default.

    Returns:
        A boolean Series on frame's own index.
    """
    first = pd.to_numeric(
        frame[headline or GASOLINE_ROW_DISPUTE["column"]], errors="coerce"
    )
    second = pd.to_numeric(
        frame[alternative or GASOLINE_ROW_DISPUTE["alternative_column"]],
        errors="coerce",
    )
    return (second > first).fillna(False)


# --------------------------------------------------------------------------
# Where the documents come from
# --------------------------------------------------------------------------

#: The Wayback CDX index. Restricted to opec.org, to PDFs, to responses that were
#: HTTP 200 and to URLs whose path contains "momr" in any case. collapse=urlkey
#: keeps one row per distinct URL rather than one per capture. The limit is well
#: above the 561 rows recon 05 section 1.2 measured, and a narrower query silently
#: truncates: recon's first attempt hit an unfiltered 3000 row limit and concluded
#: 2006 to 2009 were missing when they are not.
CDX_URL = (
    "http://web.archive.org/cdx/search/cdx"
    "?url=opec.org*"
    "&filter=original:.*[Mm][Oo][Mm][Rr].*\\.pdf"
    "&filter=mimetype:application/pdf"
    "&filter=statuscode:200"
    "&fl=timestamp,original,statuscode,mimetype,length"
    "&collapse=urlkey"
    "&limit=20000"
)

#: The raw replay form. The id_ suffix on the timestamp is what makes the archive
#: return the original bytes instead of a rewritten page with a banner.
WAYBACK_RAW = "https://web.archive.org/web/%sid_/%s"

#: Where the PDFs live. GITIGNORED. The licence permits reuse of the information
#: and forbids reproduction of the report, so the parsed values are committed and
#: the documents are not. See the module docstring.
PDF_DIR: Path = PRIVATE / "momr"

#: The eleven issues recon 05 downloaded, already on disk under their own names.
#: They are reused rather than fetched again, which is both polite and the only
#: way the first eleven parses can be checked against a report somebody wrote by
#: hand.
PROBE_DIR: Path = PRIVATE / "probe" / "cracks"

#: The index, cached next to the PDFs so a rebuild does not re query the CDX.
INDEX_FILE: Path = PDF_DIR / "issue_index.json"

#: How long the cached CDX index may be reused, in seconds. A week: the archive
#: gains at most one MOMR issue a month, and an index older than this is worth
#: refreshing before a run claims the last issue is the last issue.
INDEX_MAX_AGE_SECONDS = 7 * 24 * 3600

#: How many captures of one issue to keep, the chosen one included. Two is enough
#: for every issue in the archive today, and the cap exists so that a month with
#: forty captures does not turn one failed download into forty requests.
MAX_CANDIDATES = 3

#: The polite gap between two archive requests, in seconds. About 300 requests at
#: this rate is twenty five minutes of wall clock, which is the right price for
#: twenty five years of monthly data. SPEC.md section 5.4.
DEFAULT_DELAY = 3.0


# --------------------------------------------------------------------------
# Reading the table. No network anywhere below this line.
# --------------------------------------------------------------------------

#: The table's own title, as every era prints it. 2001 sets it on its own line
#: under "Table 2"; 2026 writes "Table 6 - 4: Refined product prices, US$/b". The
#: common substring is what is matched.
TABLE_TITLE = "refined product prices"

#: The block header. Matched as a prefix, case insensitively, because the wording
#: runs "Rotterdam", "Rotterdam (Barges FoB):" and "Rotterdam (Barges FOB)" across
#: the five eras and the capital B of FOB moved between 2019 and 2022.
BLOCK_LABEL = "rotterdam"

#: Prefixes that end the Rotterdam block. The other three regional blocks, the
#: table's own note and source lines, and the next table.
BLOCK_ENDERS = (
    "us gulf",
    "mediterranean",
    "singapore",
    "note:",
    "notes:",
    "sources:",
    "source:",
    "table ",
    "graph ",
    "n.a.",
    "*",
)

_MONTH_NAMES = (
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
)
_MONTH_NUMBER = {name: index + 1 for index, name in enumerate(_MONTH_NAMES)}

#: Full month names as the archived filenames spell them, plus the one
#: misspelling the archive actually contains. Recon 05 section 1.2: January 2008
#: is filed as momr-janaury-2008.pdf, and a parser that did not know that would
#: report a hole in the series that is not there.
_FILENAME_MONTHS = {
    "january": 1, "janaury": 1,
    "february": 2, "feburary": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9, "septmber": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

#: Every dash this source uses in a negative number. The 2001 and 2003 issues
#: write the minus of the change column as an en dash and one of them extracts as
#: a character that is neither ASCII nor a recognised dash, so the whole family is
#: listed and anything in it is read as a minus sign. The change column is not
#: used by this adapter, but a token it could not classify as a number would
#: throw the column count off and fail an issue that is perfectly readable.
#: written as codepoints, not as the characters themselves, because SPEC.md
#: section 0.1 forbids an em dash or an en dash anywhere in this repository and
#: tests/test_base.py enforces it over every .py file.
_DASH_CODEPOINTS = (
    0x002D,  # hyphen minus, the ordinary case
    0x2010,  # hyphen
    0x2011,  # non breaking hyphen
    0x2012,  # figure dash
    0x2013,  # en dash, what the 2001 and 2003 issues print
    0x2014,  # em dash
    0x2015,  # horizontal bar
    0x2212,  # minus sign
    0xFFFD,  # replacement character, what one 2001 glyph extracts as
)
_DASHES = "".join(chr(code) for code in _DASH_CODEPOINTS)

#: A number, with the report's own revision marker allowed on the end. The old
#: layout footnotes "R Revised since last issue" and writes the flag against the
#: figure, "23.50R". It is a fact about the figure and not part of it, so it is
#: accepted here and dropped by to_float. A parser that refused it would read
#: "Premium gasoline (unleaded) 23.50R 20.20 19.30 -0.90" as a two number row and
#: fail an issue that is perfectly readable, which is what the January 2002 issue
#: did before this was added.
_NUMBER = re.compile(r"^[+%s]?\d{1,4}(?:\.\d+)?R?$" % re.escape(_DASHES))

#: A month column header: a month abbreviation, possibly spelled out ("June",
#: "Sept"), an optional separator, an optional space, then an OPTIONAL two digit
#: year. Every one of these was counted in a real header line across the 303
#: archived issues:
#:
#:     "Oct.00"    "Mar 03"    "Jan 26"     the ordinary spellings
#:     "Dec,01"    a comma for a full stop, the January 2002 issue
#:     "Apr-05"    a hyphen, the 2005 issues
#:     "Sept. 08"  a space between the separator and the year
#:     "Nov"       no year at all, which is what the 2005 issues print for every
#:                 column but the last. parse_header_columns resolves those.
#:
#: The lookahead stops "2022-to-date" from being read as a month.
_HEADER_MONTH = re.compile(
    r"\b(%s)[a-z]*[.,-]?(?:\s?(\d{2})\b(?!\d))?" % "|".join(_MONTH_NAMES), re.IGNORECASE
)

#: A change column header, "May/Apr", "Dec./Nov." or "Sept/Aug".
_HEADER_CHANGE = re.compile(
    r"\b(%s)[a-z]*[.,-]?/(%s)[a-z]*[.,-]?"
    % ("|".join(_MONTH_NAMES), "|".join(_MONTH_NAMES)),
    re.IGNORECASE,
)

#: The issue's own month, as the page prints it in its running head or its
#: footer: "MOMR January 2001" in the early layout, "OPEC Monthly Oil Market
#: Report - March 2026" in the current one.
#:
#: THIS OVERRIDES THE FILENAME, and it has to. The archive holds
#: momr-april-2001.pdf, whose every page says May 2001 and whose price table
#: prints February, March and April 2001. It is the May issue filed under April.
#: Trusting the filename there would date the issue a month early, break the lag
#: check against the header months and lose a readable issue.
_ISSUE_LINE = re.compile(r"momr|monthly oil market report", re.IGNORECASE)
_ISSUE_MONTH = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\s+((?:19|20)\d{2})\b",
    re.IGNORECASE,
)


def printed_issue_month(text: str) -> str | None:
    """The issue month the page prints in its own running head, or None.

    Looked for only on a line that also names the report, so a month named in the
    narrative cannot be mistaken for the issue date.
    """
    for line in str(text).split("\n"):
        if not _ISSUE_LINE.search(line):
            continue
        match = _ISSUE_MONTH.search(line)
        if match:
            return "%s-%02d" % (
                match.group(2),
                _FILENAME_MONTHS[match.group(1).lower()],
            )
    return None

#: A year column header, "2023" or "2022-to-date".
_HEADER_YEAR = re.compile(r"\b((?:19|20)\d{2})(-to-date)?\b")


def label_key(label: str) -> str:
    """Fold a product row label to the form PRODUCT_LABELS is keyed by.

    Whitespace removed entirely and case folded, so that "Gasoil (0.2%S)",
    "Gasoil  (0.2% S)" and "GASOIL (0.2% S)" are one key and
    "Gasoil/Diesel (10 ppm)" is a different one. Nothing else is dropped: the
    parenthesised specification is the whole point of the label, and a match that
    ignored it would put a 50 ppm gasoil into a 10 ppm column.
    """
    return re.sub(r"\s+", "", str(label)).casefold()


def is_number(token: str) -> bool:
    """True when a token is one of this table's numbers, sign included."""
    return bool(_NUMBER.match(token))


def to_float(token: str) -> float:
    """One numeric token as a float. Any of the source's dashes is a minus."""
    text = token.strip()
    if text.endswith("R"):
        # "R Revised since last issue", the old layout's own footnote. The flag
        # is dropped here and the revision itself is what the overlap rule sees:
        # the same month printed again by a later issue, with n_issues and
        # max_disagreement_usd_bbl carrying the difference.
        text = text[:-1]
    sign = 1.0
    if text and text[0] in _DASHES:
        sign, text = -1.0, text[1:]
    elif text.startswith("+"):
        text = text[1:]
    try:
        return sign * float(text)
    except ValueError as exc:
        raise SourceError("opec: %r is not a number" % (token,)) from exc


def split_label_and_numbers(line: str) -> tuple[str, list[str]]:
    """Split one table row into its label and its numeric tokens.

    Numbers are taken off the END of the line until a token is not a number. That
    direction is the whole trick: a product label carries its specification in
    parentheses, and several of those specifications are numbers,
    "Premium gasoline (unleaded 98)" and "Fuel oil (380 cst 3.5% S)". Reading
    forward and stopping at the first digit would cut "98)" off the label and
    prepend it to the values. Reading backward, the closing parenthesis is what
    stops the scan, because "98)" is not a number.

    Returns:
        (label, numeric tokens in printed order). Either may be empty.
    """
    tokens = str(line).split()
    cut = len(tokens)
    while cut > 0 and is_number(tokens[cut - 1]):
        cut -= 1
    return " ".join(tokens[:cut]), tokens[cut:]


@dataclass(frozen=True)
class _Column:
    """One column of the price table, as its header describes it."""

    kind: str  # "month", "change" or "year"
    month: pd.Timestamp | None = None
    year: int | None = None
    to_date: bool = False


def _two_digit_year(value: int, issue_month: pd.Timestamp) -> int:
    """Expand a two digit header year against the issue it was printed in.

    The MOMR prints months from at most a year before the issue, so the century
    is decided by the issue rather than by a pivot rule: 00 in a January 2001
    issue is 2000, and 26 in a March 2026 issue is 2026.
    """
    for century in (issue_month.year // 100 * 100, issue_month.year // 100 * 100 - 100):
        candidate = century + value
        if issue_month.year - 1 <= candidate <= issue_month.year:
            return candidate
    return issue_month.year // 100 * 100 + value


def parse_header_columns(line: str, issue_month) -> list[_Column]:
    """Read the column layout off the price table's header line.

    The header is two or three month tokens, then exactly one change token, then
    zero or two year tokens. That shape is asserted rather than assumed, because
    it is the only thing that says which of a product row's numbers is a price and
    which is a month on month change.

    Args:
        line: the header line, for example "Jul 24 Aug 24 Aug/Jul  2023   2024".
        issue_month: the month of the issue, used to expand two digit years and
            to check that the months printed are months this issue could carry.

    Returns:
        The columns in printed order.

    Raises:
        SourceError: when the shape is not the one above, when the months are not
            consecutive and increasing, or when a month is more than six months
            before the issue. Each of those means the header is not the header
            this parser thinks it is, and guessing would put September's price on
            July's row.
    """
    issue = pd.Timestamp(issue_month).to_period("M").to_timestamp()
    text = str(line)

    found: list[tuple[int, _Column]] = []
    taken: list[tuple[int, int]] = []

    def overlaps(start: int, end: int) -> bool:
        return any(start < e and s < end for s, e in taken)

    # Change first: "Sep/Aug" must not be read as the month "Sep".
    for match in _HEADER_CHANGE.finditer(text):
        taken.append(match.span())
        found.append((match.start(), _Column(kind="change")))
    # Months, whose year may be missing. The 2005 issues print
    # "Nov    Dec   Jan 05 Jan/Dec", dating only the last column, so the number
    # is carried and the year is resolved below against whichever column does
    # carry one.
    raw_months: list[tuple[int, int, int | None]] = []
    for match in _HEADER_MONTH.finditer(text):
        if overlaps(*match.span()):
            continue
        taken.append(match.span())
        number = _MONTH_NUMBER[match.group(1)[:3].lower()]
        year = int(match.group(2)) if match.group(2) else None
        raw_months.append((match.start(), number, year))
        found.append((match.start(), _Column(kind="month")))
    for match in _HEADER_YEAR.finditer(text):
        if overlaps(*match.span()):
            continue
        taken.append(match.span())
        found.append(
            (
                match.start(),
                _Column(
                    kind="year", year=int(match.group(1)), to_date=bool(match.group(2))
                ),
            )
        )

    columns = [column for _start, column in sorted(found, key=lambda pair: pair[0])]
    kinds = [column.kind for column in columns]

    months = [column for column in columns if column.kind == "month"]
    if len(months) < 2:
        raise SourceError(
            "opec %s: the header line %r carries %d month column(s). Every layout "
            "of this table prints two or three months, so this is not the header"
            % (issue.strftime("%Y-%m"), text.strip(), len(months))
        )
    if kinds.count("change") != 1:
        raise SourceError(
            "opec %s: the header line %r carries %d change column(s), expected "
            "exactly one" % (issue.strftime("%Y-%m"), text.strip(), kinds.count("change"))
        )
    expected = ["month"] * len(months) + ["change"] + ["year"] * (len(columns) - len(months) - 1)
    if kinds != expected:
        raise SourceError(
            "opec %s: the header line %r reads as %s. Every layout of this table "
            "prints its months first, then one change column, then zero or two "
            "annual columns, and reading it in any other order would put a change "
            "where a price belongs"
            % (issue.strftime("%Y-%m"), text.strip(), ", ".join(kinds))
        )

    # RESOLVE THE YEARS. The 2005 issues date only their last month column,
    # "Nov    Dec   Jan 05 Jan/Dec", so the other two get their year from the one
    # that has one and from the fact that the columns are consecutive months. The
    # month NAMES are then checked against what that arithmetic produces, so a
    # header whose columns are not in fact consecutive fails here instead of
    # silently relabelling December as November.
    raw_months.sort(key=lambda triple: triple[0])
    anchor = next(
        (index for index, (_s, _m, year) in enumerate(raw_months) if year is not None),
        None,
    )
    if anchor is None:
        raise SourceError(
            "opec %s: no column on the header line %r carries a year, so the months "
            "it names cannot be dated. Every layout dates at least one column"
            % (issue.strftime("%Y-%m"), text.strip())
        )
    _start, number, year = raw_months[anchor]
    anchored = pd.Timestamp(year=_two_digit_year(year, issue), month=number, day=1)
    resolved: list[pd.Timestamp] = []
    for index, (_s, number, _y) in enumerate(raw_months):
        stamp = anchored + pd.offsets.MonthBegin(index - anchor) if index != anchor else anchored
        if stamp.month != number:
            raise SourceError(
                "opec %s: the header line %r dates column %d as %s but the column "
                "is labelled month %d. The columns are not the consecutive months "
                "this table always prints"
                % (issue.strftime("%Y-%m"), text.strip(), index + 1,
                   stamp.strftime("%Y-%m"), number)
            )
        resolved.append(stamp)

    dated = iter(resolved)
    columns = [
        _Column(kind="month", month=next(dated)) if column.kind == "month" else column
        for column in columns
    ]
    months = [column for column in columns if column.kind == "month"]

    for earlier, later in zip(months, months[1:]):
        if later.month != earlier.month + pd.offsets.MonthBegin(1):
            raise SourceError(
                "opec %s: the header months run %s then %s, which are not "
                "consecutive"
                % (
                    issue.strftime("%Y-%m"),
                    earlier.month.strftime("%Y-%m"),
                    later.month.strftime("%Y-%m"),
                )
            )
    for column in months:
        lag = (issue.year - column.month.year) * 12 + (issue.month - column.month.month)
        if not 1 <= lag <= 6:
            raise SourceError(
                "opec %s: the header carries %s, which is %d month(s) before the "
                "issue. An issue prints the one to three months just before it, so "
                "either the issue month is wrong or this is a different table"
                % (issue.strftime("%Y-%m"), column.month.strftime("%Y-%m"), lag)
            )

    # ONLY THE FIRST ANNUAL COLUMN IS AN ANNUAL AVERAGE. The layout prints the
    # previous calendar year's complete average and then the current year to
    # date, and only the 2022 issue writes "2022-to-date" so the label alone
    # cannot be trusted to tell them apart. Every year column after the first is
    # therefore marked to_date, because an unfinished year's running mean
    # compared against a completed one is a wrong number with no symptom.
    seen_year = False
    marked: list[_Column] = []
    for column in columns:
        if column.kind == "year":
            marked.append(
                _Column(
                    kind="year",
                    year=column.year,
                    to_date=column.to_date or seen_year,
                )
            )
            seen_year = True
        else:
            marked.append(column)
    return marked


def page_is_table(text: str) -> bool:
    """True when a page carries the refined product prices table.

    Both marks are required, the table's own title and a line that starts with
    the Rotterdam block header, because the report also carries a refining margins
    GRAPH and several narrative pages that name Rotterdam.
    """
    if not text:
        return False
    lowered = text.lower()
    if TABLE_TITLE not in lowered:
        return False
    return any(line.strip().lower().startswith(BLOCK_LABEL) for line in text.split("\n"))


@dataclass
class IssueReading:
    """What one issue of the report yielded, values and problems together."""

    issue: str
    page: int | None = None
    #: month first day -> slot -> price in $/bbl
    values: dict[pd.Timestamp, dict[str, float]] = field(default_factory=dict)
    #: slot -> the specification exactly as printed in this issue
    specs: dict[str, str] = field(default_factory=dict)
    #: complete calendar year -> slot -> the annual average this issue printed
    annual: dict[int, dict[str, float]] = field(default_factory=dict)
    #: labels inside the Rotterdam block that PRODUCT_LABELS does not know
    unknown_labels: list[str] = field(default_factory=list)
    #: the block header line, verbatim, so a wording change is visible
    block_header: str = ""
    #: the table title line, verbatim
    title: str = ""
    #: the issue month the FILENAME claimed, which is not always the issue month
    #: the document prints. See printed_issue_month.
    filename_issue: str = ""
    #: 0 when the page read at the default line tolerance, 1 when it needed the
    #: wider one. See read_issue_pdf.
    layout_attempt: int = 0
    #: labels inside the block that this parser knows and deliberately does not
    #: carry, with no column of their own. Recorded, never silently dropped.
    ignored_labels: list[str] = field(default_factory=list)
    #: None when the issue parsed, otherwise why it did not
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _match_product(label: str) -> tuple[str, str] | None:
    known = PRODUCT_LABELS.get(label_key(label))
    return known if known else None


def parse_table_page(text: str, *, issue: str, page: int | None = None) -> IssueReading:
    """Read the Rotterdam block out of one page of the refined product table.

    No network, no PDF library, no file. It takes the text of one page as
    pdfplumber lays it out and gives back everything that page said, including the
    labels it did not recognise.

    Args:
        text: the page, with its lines in reading order. Layout preserving
            extraction is required: the block header is a line of its own and its
            position relative to the product rows is what assigns them to
            Rotterdam rather than to Singapore.
        issue: the issue month as yyyy-mm.
        page: the page number, for the record.

    Returns:
        An IssueReading. A page this parser cannot read comes back with .error
        set and no values, never with a value it is unsure of.
    """
    issue_month = pd.Period(issue, freq="M").to_timestamp()
    reading = IssueReading(issue=issue, page=page)

    lines = str(text).split("\n")
    title_index = None
    for index, line in enumerate(lines):
        if TABLE_TITLE in line.lower():
            title_index = index
            reading.title = line.strip()
    if title_index is None:
        reading.error = "no line on the page reads %r" % TABLE_TITLE
        return reading

    # The header is the line carrying the change column, "May/Apr" or
    # "Dec./Nov.". That mark is used rather than the month tokens because the
    # 2005 issues leave the year off every column but the last, so counting
    # dated months finds nothing, while every layout without exception prints a
    # month over month change.
    header_line = None
    for line in lines[title_index : title_index + 8]:
        if _HEADER_CHANGE.search(line):
            header_line = line
            break
    if header_line is None:
        reading.error = (
            "no line in the eight after the title %r carries a month on month "
            "change column, so the header cannot be located" % reading.title
        )
        return reading

    try:
        columns = parse_header_columns(header_line, issue_month)
    except SourceError as exc:
        reading.error = str(exc)
        return reading

    block_index = None
    for index, line in enumerate(lines):
        if line.strip().lower().startswith(BLOCK_LABEL):
            block_index = index
            reading.block_header = line.strip()
            break
    if block_index is None:
        reading.error = "no line starts with %r" % BLOCK_LABEL
        return reading

    gasoline_rows: list[tuple[str, list[float]]] = []
    rows: dict[str, tuple[str, list[float]]] = {}

    for line in lines[block_index + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if any(lowered.startswith(end) for end in BLOCK_ENDERS):
            break
        label, tokens = split_label_and_numbers(stripped)
        if label.count("(") != label.count(")"):
            # A LABEL CLIPPED BY ITS OWN COLUMN. The July 2009 issue prints
            # "Premium gasoline (unleaded 10" and loses " ppm)" off the end, so
            # the 10 reads as a price. The specification is what identifies the
            # product, and half a specification identifies nothing, so the issue
            # fails here with the truth rather than with a column count that
            # would send the next reader looking in the wrong place.
            reading.error = (
                "the row %r carries an unclosed bracket, so its specification is "
                "clipped by the column width and the product cannot be "
                "identified. The number that looks like part of the label would "
                "otherwise be read as a price" % stripped
            )
            return reading
        if not label or not tokens:
            # A stray line inside the block with no numbers on it. It ends
            # nothing and carries nothing, so it is skipped rather than treated
            # as the end of the block, which is what the blank spacer line inside
            # the 2001 block requires.
            continue
        if len(tokens) != len(columns):
            reading.error = (
                "the row %r carries %d number(s) and the header describes %d "
                "column(s). A column has appeared or disappeared and matching "
                "them up would put one month's price under another month"
                % (stripped, len(tokens), len(columns))
            )
            return reading
        if label_key(label) in IGNORED_LABELS:
            reading.ignored_labels.append(label)
            continue
        known = _match_product(label)
        if known is None:
            reading.unknown_labels.append(label)
            continue
        slot, spec = known
        values = [to_float(token) for token in tokens]
        if slot == "gasoline":
            gasoline_rows.append((spec, values))
            continue
        if slot in rows:
            reading.error = (
                "two rows in the Rotterdam block both read as %s, %r and %r. "
                "Picking one would be a guess about which is the series"
                % (slot, rows[slot][0], spec)
            )
            return reading
        rows[slot] = (spec, values)

    # THE TWO GASOLINE ROWS, ASSIGNED BY SPECIFICATION AND NOT BY POSITION.
    #
    # From August 2004 to September 2013 the Rotterdam block prints two premium
    # gasoline rows, and which of them comes first changes: "unleaded 95" is the
    # only row for ten issues in 2004 and 2005, and is the SECOND row from June
    # 2005 to September 2013, under a sulphur graded row that runs 50 ppm then
    # 10 ppm. Assigning by printed position would move the 95 line from one
    # column to the other in June 2005 with no symptom at all.
    #
    # So "unleaded 95" always goes to its own column, wherever it is printed,
    # and the leading premium row of the issue, whatever its specification, goes
    # to the headline column with gasoline_spec saying what it is. In the ten
    # issues where 95 is the only row it lands in both, which is a duplication
    # the source forces and which the specification column makes readable.
    if len(gasoline_rows) > 2:
        reading.error = (
            "the Rotterdam block carries %d premium gasoline rows, %s. This parser "
            "knows how to carry two, the sulphur graded and the octane graded row "
            "the middle layout prints together, and will not choose among three"
            % (len(gasoline_rows), ", ".join(spec for spec, _v in gasoline_rows))
        )
        return reading
    if len(gasoline_rows) == 2 and not any(
        spec == GASOLINE_95 for spec, _values in gasoline_rows
    ):
        reading.error = (
            "the Rotterdam block carries two premium gasoline rows, %s, and "
            "neither is %r. The second column exists for that row and only for "
            "that row, so there is nowhere to put these two without guessing "
            "which continues which"
            % (", ".join(repr(spec) for spec, _v in gasoline_rows), GASOLINE_95)
        )
        return reading
    for spec, values in gasoline_rows:
        if spec == GASOLINE_95:
            rows["gasoline_95"] = (spec, values)
    if len(gasoline_rows) == 1:
        rows["gasoline"] = gasoline_rows[0]
    elif len(gasoline_rows) == 2:
        rows["gasoline"] = next(
            row for row in gasoline_rows if row[0] != GASOLINE_95
        )

    missing = [slot for slot in REQUIRED_SLOTS if slot not in rows]
    if missing:
        reading.error = (
            "the Rotterdam block yielded no %s row. Labels it did carry: %s. "
            "Unrecognised labels: %s"
            % (
                " and no ".join(missing),
                ", ".join(sorted(rows)) or "none",
                ", ".join(repr(u) for u in reading.unknown_labels) or "none",
            )
        )
        return reading

    for slot, (spec, values) in rows.items():
        reading.specs[slot] = spec
        for column, value in zip(columns, values):
            if column.kind == "month":
                reading.values.setdefault(column.month, {})[slot] = value
            elif column.kind == "year" and not column.to_date:
                # The first annual column is the previous calendar year's
                # complete average. The second is a year to date figure for an
                # unfinished year and is deliberately dropped: it is not an
                # annual average and would be compared against one.
                reading.annual.setdefault(column.year, {})[slot] = value
    return reading


# --------------------------------------------------------------------------
# Finding the table inside a PDF
# --------------------------------------------------------------------------

#: Where in the document the table sits, as a fraction of the page count. Measured
#: on the eleven issues recon 05 opened: 0.40 in 2001, 0.39 in 2003, 0.45 in 2006,
#: 0.64 in 2011 and 0.70 to 0.73 in every issue from 2015 on. The search starts
#: here and spirals outward, which finds the page in a handful of extractions
#: instead of opening ninety six.
SEARCH_START_FRACTION = 0.70


def _search_order(page_count: int, start_fraction: float = SEARCH_START_FRACTION):
    """Page indices to try, nearest first, starting at start_fraction."""
    if page_count <= 0:
        return []
    start = min(page_count - 1, max(0, int(round(start_fraction * page_count)) - 1))
    order = [start]
    for step in range(1, page_count):
        for index in (start + step, start - step):
            if 0 <= index < page_count and index not in order:
                order.append(index)
        if len(order) >= page_count:
            break
    return order


def locate_table_page(
    page_count: int,
    plain_text: Callable[[int], str],
    *,
    start_fraction: float = SEARCH_START_FRACTION,
) -> int:
    """Index of the page carrying the refined product prices table.

    Pure, so it can be tested without a PDF: it asks plain_text(index) for a
    page's text and decides with page_is_table.

    Raises:
        SourceError: when no page qualifies.
    """
    for index in _search_order(page_count, start_fraction):
        if page_is_table(plain_text(index)):
            return index
    raise SourceError(
        "opec: none of the %d pages carries both the title %r and a line starting "
        "with %r" % (page_count, TABLE_TITLE, BLOCK_LABEL)
    )


def read_issue_pdf(path, *, issue: str) -> IssueReading:
    """Open one issue, find the table and parse it. Reads a file, not the network.

    The page is located on plain text, which is cheap, and then extracted again
    with layout preserved, which is what the block structure needs. Any failure,
    a corrupt download, a missing page, an unreadable table, comes back as an
    IssueReading with .error set, because one bad issue out of three hundred must
    cost that issue and not the run.
    """
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover, an environment problem
        raise SourceError(
            "opec: pdfplumber is not installed and the MOMR is a PDF"
        ) from exc

    try:
        with pdfplumber.open(str(path)) as pdf:
            count = len(pdf.pages)

            def plain(index: int) -> str:
                return pdf.pages[index].extract_text() or ""

            index = locate_table_page(count, plain)
            page = pdf.pages[index]
            attempts = [
                page.extract_text(layout=True) or "",
                # THE SECOND ATTEMPT IS NOT A SECOND GUESS. A handful of the 2001
                # and 2002 issues set the product label a fraction lower on the
                # page than its own numbers, and at the default line tolerance
                # pdfplumber splits them into two lines: a row of numbers with no
                # label, then a label with no numbers. Both are then dropped, and
                # the issue fails with an empty Rotterdam block. Rejoining them at
                # a five point tolerance puts each label back on its own numbers
                # and changes nothing on a page that did not need it, because the
                # first attempt is used wherever it works.
                page.extract_text(layout=True, y_tolerance=5) or "",
            ]
    except SourceError as exc:
        return IssueReading(issue=issue, error=str(exc))
    except Exception as exc:  # noqa: BLE001, a PDF library raises many types
        return IssueReading(
            issue=issue,
            error="%s did not open or extract, %s: %s"
            % (Path(path).name, type(exc).__name__, exc),
        )

    reading = None
    for attempt, text in enumerate(attempts):
        # THE ISSUE MONTH COMES OFF THE PAGE, NOT OFF THE FILENAME. See
        # printed_issue_month: the archive holds one file whose name says April
        # 2001 and whose every page says May 2001.
        printed = printed_issue_month(text) or issue
        reading = parse_table_page(text, issue=printed, page=index + 1)
        reading.filename_issue = issue
        reading.layout_attempt = attempt
        if reading.ok:
            return reading
    return reading


# --------------------------------------------------------------------------
# The issue index
# --------------------------------------------------------------------------

_FILENAME_YEAR = re.compile(r"(19|20)\d{2}")


def issue_month_of_filename(url: str) -> str | None:
    """The issue month a MOMR filename names, as yyyy-mm, or None.

    Percent decoded first, because the archive holds "MOMR%20August%202015.pdf".
    The month is found by name and the year by pattern, so every shape the archive
    carries resolves without a per shape rule:

        momr-march-2026.pdf                 2026-03
        momr-april-2004-1.pdf               2004-04
        momr-janaury-2008.pdf               2008-01, the archive's own misspelling
        MOMR%20August%202015.pdf            2015-08
        OPEC_MOMR_November-2012.pdf         2012-11
    """
    name = unquote(str(url)).rsplit("/", 1)[-1].lower()
    stem = name[:-4] if name.endswith(".pdf") else name
    months = [
        (stem.index(spelling), number)
        for spelling, number in _FILENAME_MONTHS.items()
        if spelling in stem
    ]
    if not months:
        return None
    # The earliest spelling in the name wins, so "momr-march-2026" is not read as
    # some later substring, and a longer spelling wins over a shorter one at the
    # same position.
    months.sort(key=lambda pair: pair[0])
    month = months[0][1]
    years = [int(match.group(0)) for match in _FILENAME_YEAR.finditer(stem)]
    years = [year for year in years if 1999 <= year <= 2040]
    if not years:
        return None
    return "%04d-%02d" % (years[0], month)


def _is_canonical(url: str) -> bool:
    """True for the clean pattern OPEC serves today, /assets/assetdb/momr-<m>-<y>.pdf."""
    return "/assets/assetdb/momr-" in url.lower()


def parse_cdx(text: str) -> dict[str, dict]:
    """Turn a CDX response into one entry per issue month. No network.

    The CDX carries several captures of several URL shapes per issue. One is
    chosen per month, and the choice is stated rather than left to the order the
    archive happened to return:

        1. the canonical /assets/assetdb/momr-<month>-<year>.pdf shape, which is
           what OPEC serves today and what recon 05 section 1.2 verified across
           five layout eras,
        2. otherwise the largest capture, because the small ones in this listing
           are truncated or placeholder responses,
        3. and, between two otherwise equal candidates, the most recent capture.

    The captures that were not chosen are kept in "alternates", in the same
    order, because the first choice is not always readable: the archive's own
    copy of the December 2018 and March 2019 issues stops at exactly 5 MiB and
    will not open, while the older capture of the same issue, under a different
    filename and four times the size, opens fine. collect_readings falls back
    through this list rather than reporting an issue the archive actually holds
    as unobtainable.

    Returns:
        yyyy-mm -> {"timestamp", "original", "length", "candidates", "alternates"}.
    """
    grouped: dict[str, list[dict]] = {}
    for line in str(text).splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        timestamp, original = parts[0], parts[1]
        if not timestamp.isdigit():
            continue
        length = 0
        if len(parts) >= 5 and parts[4].isdigit():
            length = int(parts[4])
        month = issue_month_of_filename(original)
        if month is None:
            continue
        grouped.setdefault(month, []).append(
            {"timestamp": timestamp, "original": original, "length": length}
        )

    chosen: dict[str, dict] = {}
    for month, candidates in grouped.items():
        candidates.sort(
            key=lambda c: (_is_canonical(c["original"]), c["length"], c["timestamp"]),
            reverse=True,
        )
        best = dict(candidates[0])
        best["candidates"] = len(candidates)
        best["alternates"] = [dict(c) for c in candidates[1:MAX_CANDIDATES]]
        chosen[month] = best
    return dict(sorted(chosen.items()))


def fetch_issue_index(*, delay: float = DEFAULT_DELAY, max_age: float = INDEX_MAX_AGE_SECONDS) -> dict:
    """The issue index, from the cached copy when it is fresh, else from the CDX.

    Returns the mapping parse_cdx builds. The raw CDX response is saved next to
    the PDFs, so a later run can rebuild the index with no network and a reader
    can see exactly what the archive said.
    """
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    if INDEX_FILE.exists() and max_age > 0:
        age = time.time() - INDEX_FILE.stat().st_mtime
        if age < max_age:
            with open(INDEX_FILE, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if payload.get("issues"):
                return payload["issues"]

    response = http_get(CDX_URL, delay=delay, retries=4, timeout=120)
    body = response.text
    if not body.strip():
        raise SourceError(
            "opec: the Wayback CDX query returned nothing. Without an index there "
            "is no list of issues and this adapter will not guess one"
        )
    (PDF_DIR / "cdx_momr.txt").write_text(body, encoding="utf-8", newline="\n")
    issues = parse_cdx(body)
    if len(issues) < 200:
        raise SourceError(
            "opec: the CDX query resolved only %d issue month(s). Recon 05 section "
            "1.2 counted 303, and a short answer here is usually a truncated query "
            "rather than a shrunken archive: the first attempt recon made hit an "
            "unfiltered 3000 row limit and appeared to lose 2006 to 2009" % len(issues)
        )
    with open(INDEX_FILE, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(
            {"fetched_at": time.time(), "url": CDX_URL, "issues": issues},
            handle,
            indent=2,
            sort_keys=False,
        )
        handle.write("\n")
    return issues


# --------------------------------------------------------------------------
# Downloading, politely and resumably
# --------------------------------------------------------------------------

#: The names recon 05's eleven downloads already carry on this machine.
def _probe_path(issue: str) -> Path:
    return PROBE_DIR / ("MOMR_%s.pdf" % issue)


def issue_pdf_path(issue: str) -> Path | None:
    """The PDF already on disk for one issue, or None.

    Two directories, in order: the adapter's own cache, and the eleven files
    recon 05 downloaded. Reusing the second saves eleven requests and, more
    usefully, lets the eleven issues a human read by hand be the ones the parser
    is checked against.
    """
    mine = PDF_DIR / ("momr-%s.pdf" % issue)
    if mine.exists() and mine.stat().st_size > 0:
        return mine
    probe = _probe_path(issue)
    if probe.exists() and probe.stat().st_size > 0:
        return probe
    return None


def capture_of(entry: Mapping[str, Any], which: int = 0) -> Mapping[str, Any]:
    """One of an issue's captures, 0 being the chosen one. See parse_cdx."""
    if which == 0:
        return entry
    alternates = list(entry.get("alternates") or [])
    if which - 1 >= len(alternates):
        raise SourceError(
            "opec: no capture number %d for this issue, the archive holds %d"
            % (which + 1, len(alternates) + 1)
        )
    return alternates[which - 1]


def download_issue(
    issue: str,
    entry: Mapping[str, Any],
    *,
    delay: float = DEFAULT_DELAY,
    which: int = 0,
) -> Path:
    """Fetch one issue from the archive into PDF_DIR. One request, one file.

    The file is written to a temporary name and moved into place, so an
    interrupted run leaves no half PDF that a later run would take for a complete
    one and fail to parse.

    Args:
        which: 0 for the capture parse_cdx chose, 1 and up for its alternates.

    Raises:
        SourceError: on a failed request or a body that is not a PDF.
    """
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    capture = capture_of(entry, which)
    url = WAYBACK_RAW % (capture["timestamp"], capture["original"])
    response = http_get(
        url, headers={"Accept": "application/pdf,*/*;q=0.8"}, delay=delay, retries=3, timeout=180
    )
    body = response.content
    if not body.startswith(b"%PDF"):
        raise SourceError(
            "opec %s: %s returned %d byte(s) that do not begin with %%PDF, so the "
            "archive served something other than the issue" % (issue, url, len(body))
        )
    target = PDF_DIR / ("momr-%s.pdf" % issue)
    tmp = target.with_name(target.name + ".tmp.%d" % os.getpid())
    try:
        tmp.write_bytes(body)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return target


def collect_readings(
    index: Mapping[str, Mapping[str, str]],
    *,
    delay: float = DEFAULT_DELAY,
    download: bool = True,
    issues: Sequence[str] | None = None,
    progress: Callable[[str], None] | None = None,
) -> tuple[list[IssueReading], list[str]]:
    """Download what is missing, parse everything, and report both.

    ONE ISSUE CAN ARRIVE TWICE. The archive files the May 2001 issue under both
    momr-april-2001.pdf and momr-may-2001.pdf, and read_issue_pdf dates both from
    what the pages say rather than from the filename, so both come back as
    2001-05. The duplicate is dropped here, keeping the copy whose filename
    agreed with its contents, because leaving it in would count one issue twice in
    n_issues and turn a month with no cross check into a month that looks cross
    checked.

    Returns:
        (readings, not_downloaded). A reading is present for every issue that was
        opened, whether or not it parsed. not_downloaded names the issues whose
        PDF could not be obtained, which is a source failure and is recorded
        rather than treated as an absent month.
    """
    wanted = list(issues) if issues is not None else list(index)
    readings: list[IssueReading] = []
    missing: list[str] = []
    for issue in wanted:
        path = issue_pdf_path(issue)
        if path is None:
            if not download:
                missing.append(issue)
                continue
            try:
                path = download_issue(issue, index[issue], delay=delay)
            except Exception as exc:  # noqa: BLE001, one issue must not end the run
                missing.append(issue)
                if progress:
                    progress("%s download failed, %s: %s" % (issue, type(exc).__name__, exc))
                continue
        reading = read_issue_pdf(path, issue=issue)

        # A CAPTURE THAT WILL NOT OPEN IS NOT A MISSING ISSUE. The archive's own
        # copy of a few issues is truncated, at exactly 5 MiB in the two cases
        # this project met, and pdfminer stops at "Unexpected EOF". Another
        # capture of the same issue usually opens, so the alternates parse_cdx
        # kept are tried before the issue is given up on. Only an extraction
        # failure is retried: a table this parser cannot read is a parser problem
        # and refetching the same document would not change it.
        which = 0
        while (
            not reading.ok
            and download
            and "did not open or extract" in str(reading.error)
            and which + 1 < 1 + len(index.get(issue, {}).get("alternates") or [])
        ):
            which += 1
            if progress:
                progress(
                    "%s did not open, trying archive capture %d of %d"
                    % (issue, which + 1, 1 + len(index[issue]["alternates"]))
                )
            try:
                path.unlink()
            except OSError:
                pass
            try:
                path = download_issue(issue, index[issue], delay=delay, which=which)
            except Exception as exc:  # noqa: BLE001
                if progress:
                    progress("%s alternate download failed, %s" % (issue, exc))
                break
            reading = read_issue_pdf(path, issue=issue)

        readings.append(reading)
        if progress:
            progress(
                "%s %s page=%s months=%s%s"
                % (
                    issue,
                    "ok " if reading.ok else "FAIL",
                    reading.page,
                    ",".join(sorted(m.strftime("%Y-%m") for m in reading.values)),
                    "" if reading.ok else " " + str(reading.error)[:160],
                )
            )

    # Failures are never deduplicated: every file that could not be read has to
    # stay visible in the manifest under its own name.
    failures = [reading for reading in readings if not reading.ok]
    kept: dict[str, IssueReading] = {}
    duplicates: list[str] = []
    for reading in readings:
        if not reading.ok:
            continue
        existing = kept.get(reading.issue)
        if existing is None:
            kept[reading.issue] = reading
            continue
        # Prefer the copy whose filename agreed with the month printed inside it.
        if existing.filename_issue == existing.issue:
            duplicates.append(reading.filename_issue or reading.issue)
        else:
            duplicates.append(existing.filename_issue or existing.issue)
            kept[reading.issue] = reading
    if duplicates and progress:
        progress(
            "dropped %d duplicate file(s) of an issue already read: %s"
            % (len(duplicates), ", ".join(sorted(duplicates)))
        )
    return sorted(kept.values(), key=lambda r: r.issue) + failures, missing


# --------------------------------------------------------------------------
# Stitching the issues into one series
# --------------------------------------------------------------------------

COLUMN_N_ISSUES = "n_issues"
COLUMN_DISAGREEMENT = "max_disagreement_usd_bbl"
#: The respecification counterpart of COLUMN_DISAGREEMENT. See the module
#: docstring, "A REVISION AND A RESPECIFICATION ARE NOT THE SAME THING".
COLUMN_RESPEC_GAP = "max_respec_gap_usd_bbl"
#: Which slots the contributing issues specified differently, with both
#: specifications verbatim, as "slot:spec|spec", joined by ";". Empty when every
#: issue that printed the month agreed on what every row was.
COLUMN_RESPECIFIED = "respecified"
COLUMN_SOURCE_ISSUE = "source_issue"
COLUMN_ISSUES = "issues"
#: The slots whose printed specification changes over the sample and therefore
#: travels with every row. premium_gasoline_95_usd_bbl needs none: it is defined
#: by its specification, so its column carries "unleaded 95" or nothing.
SPEC_COLUMNS: Mapping[str, str] = {
    "gasoline": "gasoline_spec",
    "gasoil": "gasoil_spec",
}

CACHE_COLUMNS: tuple[str, ...] = (
    "date",
    *COLUMNS_BY_SLOT.values(),
    SPEC_COLUMNS["gasoline"],
    SPEC_COLUMNS["gasoil"],
    COLUMN_N_ISSUES,
    COLUMN_DISAGREEMENT,
    COLUMN_RESPEC_GAP,
    COLUMN_RESPECIFIED,
    COLUMN_SOURCE_ISSUE,
    COLUMN_ISSUES,
)


def _slot_readings(
    contributors: Sequence["IssueReading"], month: pd.Timestamp, slot: str
) -> dict[str, list[float]]:
    """What each issue printed for one slot of one month, grouped by specification.

    The grouping key is the specification the issue itself printed on that row,
    IssueReading.specs[slot], which is the row label verbatim and not a guess. It
    is what separates a revision from a respecification: two values under one key
    are two vintages of one product, and two keys are two products.

    A value that is not finite is dropped, because a NaN is the absence of a
    print and comparing it against a print would invent a disagreement.
    """
    by_spec: dict[str, list[float]] = {}
    for reading in contributors:
        printed = reading.values.get(month, {})
        if slot not in printed:
            continue
        value = printed[slot]
        if value is None or not np.isfinite(value):
            continue
        by_spec.setdefault(reading.specs.get(slot, ""), []).append(float(value))
    return by_spec


def build_frame(readings: Iterable[IssueReading]) -> pd.DataFrame:
    """Stitch every successful reading into one monthly frame.

    THE OVERLAP RULE, restated here because this is where it is applied. For each
    month and product the value kept is the one printed by the LATEST issue that
    carried that month, because a later issue is the revision of an earlier one.
    Every issue that carried the month is still counted, the largest absolute
    disagreement between any two of them on any product is kept, and both travel
    in the cache. Nothing is averaged: a mean of two vintages is a number neither
    issue ever printed.

    THE DISAGREEMENT IS MEASURED LIKE FOR LIKE. Two issues are compared on a slot
    only when they printed the same specification on it. Where they printed
    different specifications the gap goes to max_respec_gap_usd_bbl and the slot
    is named in respecified, because that gap is the source changing product and
    not the source changing its mind. See the module docstring.

    Returns:
        A frame with one row per calendar month between the first and the last
        observation, no month skipped. A month no issue reported appears with NaN
        prices and n_issues of zero rather than being dropped, which is what makes
        a hole visible to the manifest instead of invisible in a shorter frame.
    """
    good = [reading for reading in readings if reading.ok]
    per_month: dict[pd.Timestamp, list[IssueReading]] = {}
    for reading in good:
        for month in reading.values:
            per_month.setdefault(month, []).append(reading)
    if not per_month:
        raise SourceError(
            "opec: no issue yielded a single month. Nothing is written and the "
            "cache already on disk is kept"
        )

    span = pd.date_range(min(per_month), max(per_month), freq="MS")
    rows: list[dict] = []
    for month in span:
        contributors = sorted(per_month.get(month, []), key=lambda r: r.issue)
        row: dict = {"date": month}
        for slot, column in COLUMNS_BY_SLOT.items():
            row[column] = np.nan
        for spec_column in SPEC_COLUMNS.values():
            row[spec_column] = ""
        row[COLUMN_N_ISSUES] = len(contributors)
        row[COLUMN_DISAGREEMENT] = np.nan
        row[COLUMN_RESPEC_GAP] = np.nan
        row[COLUMN_RESPECIFIED] = ""
        row[COLUMN_SOURCE_ISSUE] = ""
        row[COLUMN_ISSUES] = ";".join(reading.issue for reading in contributors)

        if contributors:
            winner = contributors[-1]
            row[COLUMN_SOURCE_ISSUE] = winner.issue
            for slot, value in winner.values[month].items():
                row[COLUMNS_BY_SLOT[slot]] = value
            for slot, spec_column in SPEC_COLUMNS.items():
                row[spec_column] = winner.specs.get(slot, "")

            # A REVISION AND A RESPECIFICATION, MEASURED SEPARATELY. See the
            # module docstring. Within one specification the spread between
            # issues is OPEC revising its own assessment. Across two
            # specifications it is OPEC quoting a different product, and calling
            # that a disagreement of 7 $/bbl would be wrong in both directions:
            # it invents a disagreement where there is none, and it buries the
            # months where two issues really do disagree about one product.
            worst = 0.0
            seen_revision = False
            worst_respec = 0.0
            seen_respec = False
            respecified: list[str] = []
            for slot in COLUMNS_BY_SLOT:
                by_spec = _slot_readings(contributors, month, slot)
                if not by_spec:
                    continue
                for printed in by_spec.values():
                    if len(printed) > 1:
                        seen_revision = True
                        worst = max(worst, max(printed) - min(printed))
                if len(by_spec) > 1:
                    seen_respec = True
                    every = [v for printed in by_spec.values() for v in printed]
                    worst_respec = max(worst_respec, max(every) - min(every))
                    respecified.append(
                        "%s:%s" % (slot, "|".join(sorted(by_spec)))
                    )
            if seen_revision:
                row[COLUMN_DISAGREEMENT] = worst
            elif len(contributors) > 1:
                # More than one issue printed the month and every slot they share
                # was specified differently, so there was no like for like check.
                # That is not agreement and it is not zero disagreement, it is no
                # measurement, and it is recorded as one.
                row[COLUMN_DISAGREEMENT] = np.nan
            if seen_respec:
                row[COLUMN_RESPEC_GAP] = worst_respec
                row[COLUMN_RESPECIFIED] = ";".join(respecified)
        rows.append(row)

    frame = pd.DataFrame(rows, columns=list(CACHE_COLUMNS))
    frame[COLUMN_N_ISSUES] = frame[COLUMN_N_ISSUES].astype("int64")
    return frame.sort_values("date", kind="mergesort").reset_index(drop=True)


def specification_timeline(frame: pd.DataFrame) -> list[dict]:
    """Where each printed specification starts and ends, measured from the data.

    This is what turns SPECIFICATION_BREAKS from a claim into a record: the module
    says which breaks exist, and this says in which month each label first and
    last appeared in the issues actually parsed.
    """
    timeline: list[dict] = []
    for slot, column in SPEC_COLUMNS.items():
        if column not in frame.columns:
            continue
        block = frame[["date", column]].copy()
        block = block[block[column].astype(str).str.strip().ne("")]
        if block.empty:
            continue
        spec = block[column].astype(str)
        change = spec.ne(spec.shift())
        for _index, group in block.groupby(change.cumsum()):
            timeline.append(
                {
                    "product": slot,
                    "spec_column": column,
                    "specification": str(group[column].iloc[0]),
                    "first_month": group["date"].iloc[0].strftime("%Y-%m"),
                    "last_month": group["date"].iloc[-1].strftime("%Y-%m"),
                    "months": int(len(group)),
                }
            )
    return timeline


# --------------------------------------------------------------------------
# The adapter
# --------------------------------------------------------------------------

_registered = registered_source(SERIES)

#: Size floors. Recon 05 section 1.2 establishes the archive holds 303 issues,
#: 2001-01 to 2026-03, and that the January 2001 issue prints October to December
#: 2000, so the recoverable series is 2000-10 to 2026-02, 305 months. The build on
#: 2026-09-12 produced 305 rows.
#:
#: The per column floors are NOT one number, because these products do not all
#: start together and pretending they do would either pass an empty naphtha
#: column or fail a complete gasoil one. The first month each column carries, as
#: measured on that build, is in the comment next to it. Each floor sits about
#: ten rows under what was measured, which is enough room for the archive to lose
#: an issue and not enough for a column to quietly empty.
MIN_ROWS = 290
MIN_OBSERVATIONS = {
    # Measured: 305 of 305 months, 2000-10 to 2026-02, no hole.
    "gasoil_usd_bbl": 295,
    "premium_gasoline_usd_bbl": 295,
    "fuel_oil_35pct_usd_bbl": 295,
    # Measured: 262 months, 2004-05 to 2026-02. These three rows do not exist in
    # the early layout at all, which is a fact about 2001 and not a hole.
    "naphtha_usd_bbl": 250,
    "jet_usd_bbl": 250,
    "fuel_oil_1pct_usd_bbl": 250,
    # Measured: 110 months, 2004-05 to 2013-06. The octane graded row exists only
    # in the middle of the sample, so its floor is the length of that window and
    # not of the series.
    "premium_gasoline_95_usd_bbl": 100,
}


class OpecRotterdamProductsMonthly(Adapter):
    """Rotterdam barge product prices, monthly, $/bbl, from the OPEC MOMR.

    Everything this class does that is not shared with the other adapters is in
    the module docstring: the archive, the five layout eras, the two
    specification breaks and the overlap rule.
    """

    name = SERIES
    source = (
        "OPEC Monthly Oil Market Report, refined product prices table, Rotterdam "
        "barges FOB. Assessments credited to Argus. Retrieved from the Internet "
        "Archive"
    )
    url = CDX_URL
    page_url = _registered.page_url
    unit = "USD per barrel"
    frequency = "monthly"
    method = "parsed"
    committable = True
    licence_note = _registered.licence_note
    date_col = "date"
    required_cols = ("date", *COLUMNS_BY_SLOT.values())
    bounds = {column: BOUNDS_PRODUCT_USD_BBL for column in COLUMNS_BY_SLOT.values()}
    min_rows = MIN_ROWS
    min_observations = MIN_OBSERVATIONS
    observation_column = "gasoil_usd_bbl"

    def __init__(
        self,
        *,
        delay: float = DEFAULT_DELAY,
        download: bool = True,
        issues: Sequence[str] | None = None,
        progress: Callable[[str], None] | None = None,
    ):
        """
        Args:
            delay: polite pause before every archive request, seconds.
            download: False parses only what is already on disk and records every
                absent issue as not downloaded. Used by a rebuild.
            issues: a subset of issue months, for a partial run. None means every
                issue in the index.
            progress: called with one line per issue, for the CLI.
        """
        self.delay = float(delay)
        self.download = bool(download)
        self.issues = list(issues) if issues is not None else None
        self.progress = progress
        self.index: dict = {}
        self.readings: list[IssueReading] = []
        self.not_downloaded: list[str] = []
        self.failed_issues: list[dict] = []
        self.unknown_labels: dict[str, list[str]] = {}
        self.spec_timeline: list[dict] = []

    def fetch(self) -> pd.DataFrame:
        self.index = dict(fetch_issue_index(delay=self.delay))
        self.readings, self.not_downloaded = collect_readings(
            self.index,
            delay=self.delay,
            download=self.download,
            issues=self.issues,
            progress=self.progress,
        )
        self.failed_issues = [
            {"issue": reading.issue, "page": reading.page, "why": reading.error}
            for reading in self.readings
            if not reading.ok
        ]
        self.unknown_labels = {
            reading.issue: list(reading.unknown_labels)
            for reading in self.readings
            if reading.unknown_labels
        }
        frame = build_frame(self.readings)
        self.spec_timeline = specification_timeline(frame)

        parsed = sum(1 for reading in self.readings if reading.ok)
        last_indexed = max(self.index) if self.index else "none"
        self.vintage = "OPEC MOMR issues %s to %s, %d parsed" % (
            min((r.issue for r in self.readings), default="none"),
            max((r.issue for r in self.readings), default="none"),
            parsed,
        )
        self.note = (
            "Rotterdam barges FOB product prices in US dollars per barrel, read "
            "out of the 'Refined product prices, US$/b' table of the OPEC Monthly "
            "Oil Market Report. %d issue(s) in the Internet Archive index, %d "
            "opened, %d parsed, %d failed to parse, %d could not be downloaded. "
            "%d month(s), %s to %s. Every value is the figure printed by the "
            "latest issue that carried the month; n_issues counts how many issues "
            "printed it and max_disagreement_usd_bbl is the largest gap between "
            "any two of them on any product THEY SPECIFIED THE SAME WAY, so a "
            "revision is visible rather than averaged away. Where two issues "
            "specified a row differently the gap is a respecification and not a "
            "disagreement, and it travels in max_respec_gap_usd_bbl with the "
            "slots named in respecified. TWO SPECIFICATION BREAKS travel in the "
            "data: "
            "gasoil_spec runs 0.2 percent sulphur to 50 ppm to 10 ppm and "
            "gasoline_spec runs unleaded to 50 ppm and 10 ppm to 98, and any chart "
            "spanning one must mark it. The archive's last issue is %s, so the "
            "series ends where the archive ends; the issues after it are published "
            "but not archived and are listed in unarchived_issues. The PDFs are "
            "cached under data/private/momr/ and are never committed, only these "
            "parsed values are."
            % (
                len(self.index),
                len(self.readings),
                parsed,
                len(self.failed_issues),
                len(self.not_downloaded),
                len(frame),
                frame["date"].min().strftime("%Y-%m"),
                frame["date"].max().strftime("%Y-%m"),
                last_indexed,
            )
        )
        return frame

    def _entry(self, *, status: str, frame, note: str) -> dict:
        entry = super()._entry(status=status, frame=frame, note=note)
        entry["licence"] = (
            "OPEC copyright. Non commercial reuse of the information permitted "
            "with OPEC acknowledged. Full reproduction of the report is not"
        )
        entry["attribution"] = (
            "OPEC Monthly Oil Market Report, table 'Refined product prices, "
            "US$/b'. The assessments are Argus's: credit 'Argus, via the OPEC "
            "Monthly Oil Market Report' wherever these numbers appear. The PDFs "
            "themselves are not redistributable and are not committed."
        )
        entry["specification_breaks"] = [dict(b) for b in SPECIFICATION_BREAKS]
        entry["specification_timeline"] = list(self.spec_timeline)
        entry["overlap_rule"] = (
            "Each issue prints two or three months, so most months are printed by "
            "two or three issues. The value kept is the one from the LATEST issue "
            "that carried the month, because a later issue is the revision of an "
            "earlier one. n_issues counts the issues that printed the month, "
            "max_disagreement_usd_bbl is the largest gap between any two of them "
            "on a product THEY BOTH SPECIFIED THE SAME WAY, source_issue names "
            "the issue the value came from and issues names every issue that "
            "printed it. Nothing is averaged. A gap between two issues that "
            "specified a row differently is a respecification, not a "
            "disagreement: it is carried in max_respec_gap_usd_bbl with the "
            "slots and both specifications named in respecified, so the two "
            "cannot be read as one. max_disagreement_usd_bbl is NaN when more "
            "than one issue printed the month but no slot was specified the same "
            "way twice, because that is no cross check rather than a clean one."
        )
        entry["issues_indexed"] = len(self.index)
        entry["issues_opened"] = len(self.readings)
        entry["issues_parsed"] = sum(1 for reading in self.readings if reading.ok)
        entry["issues_failed"] = list(self.failed_issues)
        entry["issues_not_downloaded"] = list(self.not_downloaded)
        if self.unknown_labels:
            entry["unknown_labels"] = dict(self.unknown_labels)
        entry["unarchived_issues"] = (
            "Recon 05 section 1.2: the Internet Archive holds issues to 2026-03 "
            "and the six issues from 2026-04 to 2026-09 are published but not "
            "archived. opec.org answers HTTP 403 to every scripted request from "
            "this machine, so they cannot be fetched here. Closing that hole is a "
            "MANUAL step: the owner opens the MOMR download page in his own "
            "browser, saves the PDF into data/private/momr/ as "
            "momr-<yyyy>-<mm>.pdf, and reruns this adapter, which will pick the "
            "file up and extend the series. Until that happens the series ends "
            "where the archive ends and this field says so."
        )
        entry["pdf_cache"] = str(PDF_DIR)
        return entry


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: Iterable[str] | None = None) -> int:
    """Fetch, parse and cache the series. Returns an exit code."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="parse only the issues already in data/private/momr",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    adapter = OpecRotterdamProductsMonthly(
        delay=args.delay,
        download=not args.no_download,
        progress=None if args.quiet else (lambda line: print(line, flush=True)),
    )
    try:
        entry = adapter.run()
    except Exception as exc:  # noqa: BLE001, the CLI reports and exits non zero
        print("%s FAILED: %s: %s" % (adapter.name, type(exc).__name__, exc))
        return 1
    print(
        "%-34s rows=%-5d %s to %s gaps=%d status=%s"
        % (
            entry["series"],
            entry["rows"],
            entry["first_date"],
            entry["last_date"],
            len(entry["gaps"]),
            entry["status"],
        )
    )
    print("  issues indexed=%d opened=%d parsed=%d failed=%d not downloaded=%d"
          % (
              entry["issues_indexed"],
              entry["issues_opened"],
              entry["issues_parsed"],
              len(entry["issues_failed"]),
              len(entry["issues_not_downloaded"]),
          ))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
