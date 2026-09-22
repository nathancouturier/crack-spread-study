"""The DGEC weekly note, read twice: what it prints, and what it draws.

This is the weekly product price layer, and it is the most delicate thing in this
project. Read this docstring before you use either series.

THE SITUATION
-------------
DGEC publishes one "Note de conjoncture petroliere" at a time and DELETES the
previous one. The Internet Archive holds nine, the live site holds one, and that
is the whole population: recon 02 section 2.5 established there is no archive to
crawl. Ten note PDFs are preserved under data/private/dgec_notes/ and they cannot
be downloaded again. Never modify or delete them.

Each note carries, on the same page:

    a TABLE printing two weekly averages and, since December 2025, two monthly
    averages, for Eurosuper, Gazole, Fioul domestique, Jet, Fioul lourd TBTS and
    Brent date, in $/t.

    a CHART, drawn as vector polylines, of four of those six series over the
    preceding 105 weeks.

So the printed tables across the ten notes recon 05 read amounted to 18 distinct
weekly observations and 7 distinct monthly ones, and the charts in the same ten
documents were the ministry's own record of 219 weeks. Every note collected since
adds two printed weeks, one of them usually a reprint, and about 105 charted ones
of which one is new. The counts in the manifest are the counts of the committed
cache and this paragraph is the shape of the source, not a row count.

THREE SERIES, AND THEY ARE NOT THE SAME KIND OF OBJECT
-------------------------------------------------------
    dgec_note_printed_weekly        method "parsed". The numbers DGEC printed,
                                    read by label. Ground truth, and the
                                    calibration anchor set for the other series.
                                    A couple of dozen weeks, two more with every
                                    note collected. It is small and that is
                                    honest.

    dgec_note_printed_monthly       method "parsed". The MONTHLY columns of the
                                    same table, which the six column layout has
                                    printed since December 2025. 7 months, each
                                    carrying the ministry's own provisional flag
                                    and the vintage of the note it was read from,
                                    and each carrying every earlier print of the
                                    same month in revision_history. SPEC.md
                                    section 2 rule 5 asks for exactly this:
                                    provisional is labelled provisional, every
                                    vintage is kept and the flag is shown. It is
                                    also the only monthly home of Jet and Fioul
                                    lourd TBTS as DGEC $/t quotations: neither is
                                    plotted on the chart, so outside this series
                                    they exist only in the printed weeks.

    dgec_note_reconstructed_weekly  method "reconstructed". The page 3 curves,
                                    decoded and calibrated against the printed
                                    figures on the same page. Four years of
                                    weeks, no holes, four products only, and a
                                    collection restitches the whole of it:
                                    COLLECTION_RESTITCHES_HISTORY.

They are never merged. Recon 05 section 14 sets six conditions on the second
series and every one of them is implemented here:

  1. Nothing is invented. Every value is a measurement of a curve the ministry
     drew from its own data. Nothing is interpolated, modelled or borrowed.
  2. Nothing is silent. Separate name, separate cache, separate manifest entry,
     and a method field that says in words what was done.
  3. The error is measured, not asserted, and it travels in the data:
     RECONSTRUCTION_ERROR below, the per week spread columns, and
     docs/methodology.md.
  4. It is validated against something it did not see: the overlap between notes,
     and the OPEC monthly table.
  5. The weak spots are in the data, not only in prose. cross_checked is False on
     every week only one note covers, and evidence_class goes further and says
     WHICH kind of uncorroborated week each one is, because the six oldest are
     weak twice over. n_independent_geometries counts distinct chart geometries
     rather than notes, so the degenerate pair recon 05 section 12 found,
     wb_NPG-2026.04.03 against NPG-2026.09.04, which share an axis scale and a
     point pitch and therefore CANNOT disagree, counts once rather than twice.
     Brent is the least accurate of the four and BRENT_IS_WORST says so. A spread
     computed over a single observation is NaN, never zero: see UNDEFINED_SPREAD.
  6. It fails loudly. Every gate in GATES below writes no value at all rather
     than a guess, and a note that trips one stops the adapter.

THE LINE THIS MODULE DOES NOT CROSS
------------------------------------
Jet and Fioul lourd are NOT on the chart. They therefore do not exist as a weekly
series and this module does not produce one for them. Regressing them on the
three products that are plotted would be exactly the synthetic series SPEC.md
section 2 rule 1 forbids. They appear in dgec_note_printed_weekly, a
couple of dozen observations, and nowhere else.

WHY NOT JUST USE THE PRINTED NUMBERS
-------------------------------------
Because the ministry prints two weeks and deletes last week's note, so the
printed numbers amount to two dozen observations, while the chart in the same
document is its own record of 105 more. Decoding it is a documented extraction from a
published source, the same category of act as parsing a table out of a PDF, only
harder. It is labelled as a reconstruction everywhere it appears.
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from ..config import (
    SOURCES,
    BBL_PER_T_GASOIL,
    BBL_PER_T_GASOLINE,
    BOUNDS_CRACK_USD_BBL,
    BOUNDS_PRODUCT_USD_T,
    DGEC_BBL_PER_T_BRENT_NOTE,
)
from .base import (
    PRIVATE,
    Adapter,
    SourceError,
)

__all__ = [
    "NOTE_DIR",
    "NOTE_GLOB",
    "TABLE_TITLE_MARKERS",
    "PRINTED_ROWS",
    "CHART_PRODUCTS",
    "GATES",
    "RECONSTRUCTION_ERROR",
    "BRENT_IS_WORST",
    "DEGENERATE_PAIR",
    "UNDEFINED_SPREAD",
    "EVIDENCE_CLASSES",
    "OLDEST_WEEKS_ARE_WEAK_TWICE",
    "ERROR_BAR_AXIS",
    "SMOOTH_TILT_IS_INVISIBLE",
    "PIXEL_QUANTISATION",
    "CHART_WEEKS",
    "COLLECTION_RESTITCHES_HISTORY",
    "NoteDecodeError",
    "NoteDecode",
    "parse_fr_date",
    "decode_note",
    "load_corpus",
    "build_printed_weekly",
    "build_printed_monthly",
    "build_reconstructed_weekly",
    "weekly_cracks",
    "DgecNotePrintedWeekly",
    "DgecNotePrintedMonthly",
    "DgecNoteReconstructedWeekly",
    "DgecNoteReconstructedCracksWeekly",
    "main",
]


# ---------------------------------------------------------------------------
# Where the notes are
# ---------------------------------------------------------------------------

#: The preserved corpus. Gitignored, and IRREPLACEABLE: the ministry deletes each
#: note when the next one appears and the Internet Archive holds nine in total.
#: Nothing in this module writes into this directory except collect_current_note,
#: which only ever adds a file it has just downloaded.
NOTE_DIR: Path = PRIVATE / "dgec_notes"

#: Both spellings in the corpus: NPG-YYYY.MM.DD.pdf fetched live, and
#: wb_NPG-YYYY.MM.DD.pdf recovered from the Wayback Machine. The other PDFs in
#: the same directory are the methodology notes and are not weekly notes.
NOTE_GLOB = "*NPG-*.pdf"

#: The quotation page is found by its TITLE, never by its index. Recon 02 section
#: 3.1: it is page 3 in nine of the ten notes and page 4 in NPG-2024.07.12, and
#: the title wording itself changed, from "Cours hebdomadaire du Brent date et
#: cotations des produits petroliers (en $/t)" in the 2024 notes to "Cours du
#: Brent date et cotations des produits petroliers (en $/t)" in 2026. These are
#: the two fragments common to every spelling seen, matched on accent stripped,
#: case folded, whitespace collapsed text.
TABLE_TITLE_MARKERS = ("brent date", "cotations des produits petroliers")


# ---------------------------------------------------------------------------
# The rows of the printed table, by label
# ---------------------------------------------------------------------------
#
# PARSED BY LABEL, NEVER BY POSITION. Recon 02 section 3.3 documents three layout
# breaks inside this ten note sample:
#
#   (a) the monthly columns are recent. The 2024 and January 2025 notes print
#       three columns, two weekly dates and a variation. The six column form with
#       "Moyennes hebdomadaires" and "Moyennes mensuelles" first appears in the
#       December 2025 note.
#   (b) THE ROW ORDER CHANGED. 2024 and January 2025 print Fioul lourd before
#       Jet, December 2025 onward print Jet before Fioul lourd and add the EUR/t
#       fioul lourd row. Positional parsing would silently swap two products
#       across that break, which is the SPEC.md section 13 failure mode made
#       real.
#   (c) the x geometry drifts. NPG-2026.04.17 has the same logical table shifted
#       about 23 points right of NPG-2026.04.03, one week apart, with different
#       font sizes. Any parser keyed on an absolute x breaks. Columns are
#       recovered here by clustering the value positions and naming each cluster
#       from the nearest header, recomputed per file.
#
# The key is the label as printed, accent stripped and case folded; the value is
# the column name in the cache. Longest match wins, so "fioul lourd tbts (< 1%)
# (en EUR/t)" cannot be swallowed by "fioul lourd tbts (< 1%)".
PRINTED_ROWS: Mapping[str, str] = {
    "eurosuper": "eurosuper_usd_t",
    "gazole": "gazole_usd_t",
    "fioul domestique": "fioul_domestique_usd_t",
    "jet": "jet_usd_t",
    "fioul lourd tbts (< 1%)": "fioul_lourd_tbts_usd_t",
    "fioul lourd tbts (< 1%) (en eur/t)": "fioul_lourd_tbts_eur_t",
    "brent date": "brent_date_usd_t",
}

#: The single row of the table that is not quoted in dollars per tonne. The table
#: title carries the unit for every other row, and this one names its own.
PRINTED_EUR_COLUMN = "fioul_lourd_tbts_eur_t"

#: The four series the chart plots, by the legend text they carry, longest label
#: first so that a future note which adds Fioul lourd to the chart cannot have it
#: read as Fioul domestique. Recon 05 section 10: series identification comes
#: from the legend, matching each swatch's stroke colour to the text beside it,
#: and NEVER from the colour value, because two of the ten notes round the same
#: colour differently, (1.0, 0.6, 0.0) against (1.0, 0.599609, 0.0).
CHART_PRODUCTS: Mapping[str, str] = {
    "fioul domestique": "fioul_domestique_usd_t",
    "eurosuper": "eurosuper_usd_t",
    "gazole": "gazole_usd_t",
    "brent": "brent_date_usd_t",
}

#: Products on the chart, in the order the site should show them, with Brent last
#: because it is the crude leg and the least accurately decoded of the four.
CHART_COLUMNS = (
    "eurosuper_usd_t",
    "gazole_usd_t",
    "fioul_domestique_usd_t",
    "brent_date_usd_t",
)

PRINTED_COLUMNS = tuple(PRINTED_ROWS.values())


# ---------------------------------------------------------------------------
# The gates. Recon 05 section 14 condition 6.
# ---------------------------------------------------------------------------
#
# Each of these is a way the decode could be wrong, with the number that says so,
# and tripping any one of them means the note contributes NOTHING. There is no
# fallback, no partial decode and no guess. The values are set from what recon 05
# measured across all ten notes, with room above the worst observation, so that a
# gate firing means something really changed rather than that a threshold was
# drawn too tight.
GATES: Mapping[str, Any] = {
    # Four polylines, of equal length, and long enough to be a weekly history
    # rather than an axis or a legend rule. All ten notes give exactly 4 of
    # exactly 105.
    "chart_series": 4,
    "min_points": 50,
    # The value axis is fitted by least squares on the y tick labels, so fewer
    # than four ticks is not a fit worth trusting.
    "min_y_ticks": 4,
    # Worst single tick residual across the ten notes is 0.588 $/t. This bounds
    # axis nonlinearity and label centring error over the full height of the
    # chart and is the only evidence available about the left hand end, where no
    # anchor sits.
    "max_tick_residual_usd_t": 2.0,
    # Two printed weeks times four plotted products.
    "anchors": 8,
    # THE HEADLINE GATE, and the one recon 05 section 14 names: after the per
    # note offset is fitted on the anchors, no anchor may be more than this far
    # from the printed figure. Worst across the ten notes is 0.738 $/t.
    "max_anchor_residual_usd_t": 1.5,
    # The point pitch divided by the x label pitch, which is what establishes the
    # spacing as weekly rather than assuming it. Measured 0.9986 to 1.0009.
    "weeks_per_point": (0.98, 1.02),
}

#: What the reconstruction costs, measured rather than asserted, recon 05
#: sections 11 and 12. These numbers go in the manifest, in docs/methodology.md
#: and on the Method view, next to the series and not in a footnote.
RECONSTRUCTION_ERROR: Mapping[str, Any] = {
    "out_of_sample_mae_usd_t": (0.17, 0.44),
    "out_of_sample_worst_usd_t": 0.87,
    "note_pair_mean_absolute_usd_t": 0.30,
    "note_pair_worst_week_usd_t": 1.68,
    "method": (
        "leave one series out: the per note offset is fitted on three products' "
        "six printed anchors and used to predict the fourth product's two, "
        "rotating through all four products in all ten notes"
    ),
}

#: Recon 05 section 12: Brent is consistently the worst decoded of the four. It
#: is the lowest line on a chart scaled for the product lines, so the same pixel
#: error is a larger relative error, and on some notes it runs close to the
#: bottom axis. The largest single week disagreement between any two notes in the
#: whole overlap test, 1.68 $/t, is on Brent.
BRENT_IS_WORST = (
    "brent_date_usd_t is the least accurately decoded of the four plotted "
    "series. It is the lowest line on a chart scaled for the product lines, so "
    "the same pixel error is a larger relative error, and the worst single week "
    "disagreement between two notes in the whole overlap test, 1.68 $/t, is on "
    "Brent. Where a Brent figure matters, prefer dgec_brent_monthly, which DGEC "
    "publishes as a workbook."
)

#: Recon 05 section 12, disclosed because it is the one place the cross check
#: proves less than it appears to. Two notes whose charts share a y scale and a
#: point pitch map an identical value onto an identical pixel, so they cannot
#: disagree: a spread of zero between them is arithmetic, not agreement. The
#: n_independent_geometries column exists to carry this into the data.
DEGENERATE_PAIR = (
    "wb_NPG-2026.04.03 and NPG-2026.09.04 both draw a 400 to 1500 axis over 12 "
    "ticks at the same 4.3212 point pitch, so over their 83 common weeks the "
    "decoder cannot disagree with itself: their standard deviation is exactly "
    "0.00 and their difference a constant 0.18 $/t. That pair proves the decoder "
    "is deterministic and proves the two notes carry the same underlying values. "
    "It proves nothing about accuracy. The independent evidence comes from the "
    "pairs with different axis scales, which is most of them, and they give the "
    "0.30 $/t figure. n_independent_geometries counts distinct chart geometries "
    "rather than notes so that this is visible per week."
)

#: The same reasoning as DEGENERATE_PAIR, taken one step further and applied to
#: the arithmetic rather than to a pair of notes. A spread over ONE observation
#: is not zero, it is undefined, and writing zero there states agreement where
#: there was never a second reading to agree with. Both note series therefore
#: write NaN, which write_cache renders as an empty cell, and the columns that
#: say how many readings there were, n_notes and n_independent_geometries, are
#: what a reader consults to know why. opec_rotterdam_products_monthly has
#: always done this correctly and these two now match it.
UNDEFINED_SPREAD = (
    "A spread, a disagreement or a revision computed over a single reading is "
    "NaN in these files and never 0. Zero is a measurement meaning two or more "
    "readings agreed; an empty cell means there was only ever one reading and "
    "the quantity is undefined. Which weeks are in the second case is what "
    "n_notes and n_independent_geometries say, and how many there are is counted "
    "in each series' own note above, because a collection changes it. Anything "
    "rendering these columns must print the empty cell as 'no cross check', "
    "never as '0.00'."
)

#: The values of the evidence_class column, in decreasing order of how well
#: defended the week is. This exists because cross_checked is a boolean and the
#: 25 weeks it marks False are NOT equally weak: six of them are weak twice over.
EVIDENCE_CLASSES = (
    "cross_checked",
    "single_geometry_interior",
    "single_geometry_newest",
    "single_geometry_oldest",
    "no_coverage",
)

#: Recon 05 section 12 and the Gate 1 self audit, trouble (c). The six weeks the
#: audit named as the least defended data in the project, and why naming them in
#: prose was not enough.
OLDEST_WEEKS_ARE_WEAK_TWICE = (
    "THE SIX OLDEST RECONSTRUCTED WEEKS, 2022-07-01 to 2022-08-05, carry two "
    "weaknesses at once and are the least defended data in this project. They "
    "are covered by exactly ONE chart geometry, so cross_checked is False and "
    "no second note can contradict them, AND they sit at the far left of that "
    "one note's chart, 105 weeks from its nearest calibration anchor, where the "
    "only evidence about the fit is the tick residual. Every other "
    "uncorroborated week has at most one of the two problems: a newest single "
    "geometry week is uncorroborated but sits ON the anchored end, and a "
    "collection usually gives it a second geometry. evidence_class marks these "
    "six 'single_geometry_oldest' so the compounding is a value in the data and "
    "not a sentence in a document."
)

#: WHAT A COLLECTION DOES TO THE WEEKS ALREADY IN THE SERIES, measured.
#:
#: Each note plots about 105 weeks and the stitch takes a median across every
#: note that covers a week, so collecting one note does not only add a week at
#: the right hand end: it revises about half the series behind it, by a little.
#: That is the method working, more evidence giving a better estimate, and it is
#: also a reproducibility fact a reader is entitled to before he quotes a weekly
#: figure. Nothing in a single vintage of the cache can show it, because it is a
#: difference between two vintages, so it is recorded here with the collection it
#: was measured on.
#: How many weeks a note's page 3 chart plots. Recon 05 measured it on every
#: note of the corpus and it is the same in all of them. It is named here because
#: three sentences quote it and the site prints it.
CHART_WEEKS = 105

COLLECTION_RESTITCHES_HISTORY: Mapping[str, object] = {
    "what": (
        "COLLECTING A NOTE RESTITCHES THE WHOLE RECONSTRUCTION, NOT ONLY ITS "
        "NEWEST WEEK. Each note plots about 105 weeks, so most weeks are covered "
        "by several notes, and the value written here is the median across the "
        "geometries that cover the week. One more note therefore moves weeks that "
        "were already published. A figure read off this site today can differ "
        "from the same figure next month, and the reason is more evidence rather "
        "than a correction."
    ),
    "measured_on": "NPG-2026.09.18",
    "measured_note": (
        "Measured on the collection of the note of 18 September 2026, by "
        "comparing the committed cache before and after it. That comparison lives "
        "in the repository's history, not in the data, so it is recorded here "
        "rather than recomputed."
    ),
    "weeks_before": 220,
    "weeks_after": 221,
    "weeks_moved": 104,
    "worst_price_move_usd_t": 0.39,
    "worst_price_column": "gazole_usd_t",
    "worst_spread_move_usd_t": 0.62,
    "worst_spread_column": "spread_fioul_domestique_usd_t",
    "worst_crack_move_usd_bbl": 0.06,
    "worst_crack_column": "crack_gasoil_usd_bbl",
    "cross_checked_before": 194,
    "cross_checked_after": 214,
    "direction": (
        "The moves are inside the reconstruction's own measured error, 0.17 to "
        "0.44 $/t, and the collection took the weeks read from two or more "
        "independent chart geometries from 194 to 214, so the series after the "
        "collection is better defended than the series before it."
    ),
}

#: Gate 1 self audit, point 10 item 1. The words matter: "out of sample" will be
#: read as "out of sample in time" and it is not.
ERROR_BAR_AXIS = (
    "THE 0.17 TO 0.44 $/t ERROR IS A LEAVE ONE SERIES OUT FIGURE. The per note "
    "offset is fitted on three products' anchors and used to predict the "
    "fourth's, and all eight anchors of every note sit on the LAST TWO WEEKS of "
    "a 105 week chart. It is therefore out of sample across products and in "
    "sample across time, and it does NOT bound the other 103 weeks. The figure "
    "that does speak to time is the note pair overlap, 0.30 $/t mean absolute "
    "and 1.68 $/t worst single week, and that is the one to quote next to a week "
    "in the middle of the series."
)

#: Gate 1 self audit, trouble (c), the one attack that works. Recorded next to
#: the gates rather than in a document, because it is a property of the gates.
SMOOTH_TILT_IS_INVISIBLE = (
    "The gates are blind to a smooth distortion anchored at the right hand end. "
    "The audit tilted a real note's chart, leaving the anchored right end "
    "untouched and bending the left: a 10 point tilt moved the oldest week by "
    "73.49 $/t, about 10 $/bbl on the gasoil crack, while the headline anchor "
    "residual gate read 0.711 against its limit of 1.50 and every other gate "
    "passed. A 1 point tilt moved it 7.35 $/t at a gate reading of 0.391. What "
    "defends the series against this is not the gates, it is the overlap between "
    "notes, because a given week sits at a different horizontal position in each "
    "note that plots it. The weeks with only one geometry, counted above, have no "
    "defence against it, and those marked single_geometry_oldest have none and "
    "sit where the distortion is largest."
)

#: Gate 1 self audit, point 10 item 2. Recorded because nothing in the file can
#: distinguish the two cases and a reader would otherwise assume the first.
PIXEL_QUANTISATION = (
    "A decoded value is the calibrated height of a point on a raster free vector "
    "curve, but the curve itself was drawn from rounded data onto a finite grid, "
    "so two different weekly prices can land on the same point height. Eurosuper "
    "reads exactly 719.1192666134755 on 2024-09-20, 2024-09-27 and 2024-11-01, "
    "and nothing in this file distinguishes a genuinely flat week from two "
    "different prices quantised onto one height. The printed table is the only "
    "cure and it covers the weeks dgec_note_printed_weekly holds, which is a "
    "small fraction of these. Treat an exact repeat of a reconstructed value "
    "at adjacent weeks as 'indistinguishable at the resolution of the chart', "
    "never as 'the price did not move'."
)


# ---------------------------------------------------------------------------
# Small text helpers
# ---------------------------------------------------------------------------

#: The month abbreviations DGEC prints, including both the accented and the
#: unaccented spellings, because pdfplumber's decoding of the embedded font is
#: not identical across the ten notes.
_MONTHS: Mapping[str, int] = {
    "janv": 1,
    "fevr": 2,
    "mars": 3,
    "avr": 4,
    "mai": 5,
    "juin": 6,
    "juil": 7,
    "aout": 8,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

#: Every flavour of space DGEC's PDFs use, including the narrow no break space it
#: uses as a thousands separator.
_SPACES = "\\s\u00a0\u202f\u2009"


def strip_accents(text: str) -> str:
    """Accent stripped, case folded text, for label matching only.

    Never used to produce output. The PDFs decode "aout" and "aout" with an
    accent inconsistently between notes and "degrees" of accent are not a
    property of the data.
    """
    decomposed = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _squash(text: str) -> str:
    """Accent stripped, lower case, single spaced, currency symbols spelled out.

    The euro sign survives accent stripping unchanged, so the one row of the
    table that names its own unit, "Fioul lourd TBTS (< 1%) (en EUR/t)", would
    otherwise never match a plain ASCII label written in source.
    """
    squashed = strip_accents(text).replace("€", "eur").replace("$", "usd")
    return re.sub(r"\s+", " ", squashed).strip()


def parse_fr_date(text: str) -> date | None:
    """Parse a French short date as DGEC prints it, for example 4-sept.-26.

    Returns None rather than raising, because this is used to ASK whether a word
    is a date. The two digit year is 2000 plus, which is right for a publication
    that started in its current form in 2011 and would be wrong only for a note
    from before 2000, of which none exists.
    """
    squashed = re.sub("[%s]" % _SPACES, "", strip_accents(text))
    match = re.match(r"^(\d{1,2})-([a-z.]+)-(\d{2})$", squashed)
    if not match:
        return None
    month = match.group(2).strip(".")
    if month not in _MONTHS:
        return None
    try:
        return date(2000 + int(match.group(3)), _MONTHS[month], int(match.group(1)))
    except ValueError:
        return None


def parse_fr_month(text: str) -> tuple[int, int] | None:
    """Parse a French short month as DGEC prints a monthly column, sept.-26."""
    squashed = re.sub("[%s]" % _SPACES, "", strip_accents(text))
    match = re.match(r"^([a-z.]+)-(\d{2})$", squashed)
    if not match:
        return None
    month = match.group(1).strip(".")
    if month not in _MONTHS:
        return None
    return (2000 + int(match.group(2)), _MONTHS[month])


def _least_squares(pairs: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """Fit value = a + b * position over (position, value) pairs.

    Raises:
        NoteDecodeError: when every position is identical, which would be a
            degenerate axis rather than a chart.
    """
    n = len(pairs)
    sx = sum(p[0] for p in pairs)
    sy = sum(p[1] for p in pairs)
    sxx = sum(p[0] * p[0] for p in pairs)
    sxy = sum(p[0] * p[1] for p in pairs)
    denominator = n * sxx - sx * sx
    if abs(denominator) < 1e-9:
        raise NoteDecodeError("the y axis tick labels all sit at the same height")
    slope = (n * sxy - sx * sy) / denominator
    return (sy - slope * sx) / n, slope


# ---------------------------------------------------------------------------
# The result of reading one note
# ---------------------------------------------------------------------------

class NoteDecodeError(SourceError):
    """One note could not be read, or failed one of the GATES.

    A note that raises this contributes nothing at all. There is no partial
    decode, because a partially decoded chart is a guess with a plausible shape.
    """


@dataclass
class NoteDecode:
    """Everything one weekly note yields, and the diagnostics that earned it."""

    #: file name as it sits in data/private/dgec_notes
    file: str
    #: 1 based page the quotation table and its chart were found on
    page: int
    #: THE VINTAGE, which is the latest weekly date PRINTED INSIDE the note, not
    #: the date in its filename. Recon 02 section 2.4: four of the ten notes
    #: carry a content date later than their filename, by one to four weeks,
    #: because the ministry sometimes replaces the contents of an existing URL
    #: rather than uploading a new file.
    vintage: date
    #: week ending date -> column -> value, $/t, exactly as printed
    printed_weekly: dict[date, dict[str, float]]
    #: (year, month) -> column -> value, $/t, exactly as printed. Empty for the
    #: 2024 and January 2025 notes, which print no monthly columns.
    printed_monthly: dict[tuple[int, int], dict[str, float]]
    #: whether each printed monthly column carried "(donnees provisoires)"
    printed_monthly_provisional: dict[tuple[int, int], bool]
    #: column -> {week ending date -> calibrated $/t}, the four plotted series
    chart: dict[str, dict[date, float]]
    #: the geometry signature, used to tell two notes that CANNOT disagree from
    #: two that agree. See DEGENERATE_PAIR.
    geometry: tuple
    #: every number the gates were checked against
    diagnostics: dict = field(default_factory=dict)

    @property
    def weeks(self) -> list[date]:
        any_series = next(iter(self.chart.values()))
        return sorted(any_series)


# ---------------------------------------------------------------------------
# Finding the page
# ---------------------------------------------------------------------------

def find_quotation_page(pdf) -> tuple[int, Any]:
    """The page carrying the quotation table, found by its title.

    Returns (one based page number, the pdfplumber page).

    Raises:
        NoteDecodeError: when no page carries the title. Falling back to page 3
            would be wrong for NPG-2024.07.12, where the table is on page 4, and
            silently wrong for whatever the next layout change does.
    """
    for index, page in enumerate(pdf.pages):
        text = _squash(page.extract_text() or "")
        if all(marker in text for marker in TABLE_TITLE_MARKERS):
            return index + 1, page
    raise NoteDecodeError(
        "no page carries the quotation table title. Looked for %s in every page's "
        "text, accent stripped and case folded" % (", ".join(map(repr, TABLE_TITLE_MARKERS)))
    )


# ---------------------------------------------------------------------------
# The printed table
# ---------------------------------------------------------------------------

def _rows_by_band(words: Sequence[Mapping], tolerance: float = 3.0) -> list[list[Mapping]]:
    """Cluster words into rows on their vertical centre.

    A fixed rounding is not enough. In NPG-2026.09.04 the label "Eurosuper" sits
    at a centre of 148.0 and its own values at 147.0, so rounding to the nearest
    point puts a row's label and its numbers in different rows. The clustering is
    on the gap between consecutive centres instead.
    """
    ordered = sorted(words, key=lambda w: ((w["top"] + w["bottom"]) / 2.0, w["x0"]))
    rows: list[list[Mapping]] = []
    current: list[Mapping] = []
    last = None
    for word in ordered:
        centre = (word["top"] + word["bottom"]) / 2.0
        if last is not None and centre - last > tolerance:
            rows.append(sorted(current, key=lambda w: w["x0"]))
            current = []
        current.append(word)
        last = centre
    if current:
        rows.append(sorted(current, key=lambda w: w["x0"]))
    return rows


_NUMBER = re.compile(r"^-?\d{1,4}$")


def _merge_numbers(row: Sequence[Mapping]) -> list[tuple[float, float, float]]:
    """Numbers in one row as (value, centre x, right edge).

    DGEC separates thousands with a narrow no break space, so 1 349 extracts as
    the two words "1" and "349". They are rejoined when the left token is a
    single digit and the gap to the next token is under three points, which is
    tighter than the gap between two columns by an order of magnitude.
    """
    out: list[tuple[float, float, float]] = []
    current: tuple[str, float, float] | None = None  # text, left x, right x
    for word in row:
        text = re.sub("[%s]" % _SPACES, "", str(word["text"]))
        if _NUMBER.match(text):
            if (
                current is not None
                and (word["x0"] - current[2]) < 3.0
                and len(current[0].lstrip("-")) == 1
            ):
                current = (current[0] + text, current[1], word["x1"])
            else:
                if current is not None:
                    out.append((float(current[0]), (current[1] + current[2]) / 2.0, current[2]))
                current = (text, word["x0"], word["x1"])
        else:
            if current is not None:
                out.append((float(current[0]), (current[1] + current[2]) / 2.0, current[2]))
            current = None
    if current is not None:
        out.append((float(current[0]), (current[1] + current[2]) / 2.0, current[2]))
    return out


def _label_of(row: Sequence[Mapping], first_value_x: float) -> str:
    """The row label: every word left of the first value column, joined."""
    words = [w for w in row if w["x1"] <= first_value_x]
    return _squash(" ".join(str(w["text"]) for w in words))


def _match_label(label: str) -> str | None:
    """The cache column for a printed row label, longest match first."""
    for printed in sorted(PRINTED_ROWS, key=len, reverse=True):
        if label.startswith(printed):
            return PRINTED_ROWS[printed]
    return None


def _cluster_centres(values: Iterable[float], tolerance: float = 9.0) -> list[float]:
    """Group x centres that belong to the same column, return the group means."""
    ordered = sorted(values)
    groups: list[list[float]] = []
    for value in ordered:
        if groups and value - groups[-1][-1] <= tolerance:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [sum(g) / len(g) for g in groups]


def parse_printed_table(page) -> dict:
    """Read the quotation table off one page, by label, never by position.

    Returns a dict with keys "weekly", "monthly", "monthly_provisional" and
    "diagnostics".

    The column identities are recovered in three steps, none of which uses an
    absolute coordinate:

      1. find the product rows by label, and merge their thousands separated
         numbers.
      2. cluster every value's centre x across all those rows. Each cluster is
         one column of the table, whatever the layout era and wherever the table
         has drifted to.
      3. name each cluster from the nearest header token. A header that parses as
         a full date, 4-sept.-26, names a weekly column. One that parses as a
         month, sept.-26, names a monthly column. "variation" names a column this
         module never reads, and naming it is what stops a variation value being
         mistaken for a price.

    Raises:
        NoteDecodeError: when the table does not yield two weekly columns, or
            when a required row is missing.
    """
    words = page.extract_words(use_text_flow=False)
    rows = _rows_by_band(words)

    # Step 1. The rows, by label. The label is everything left of the leftmost
    # number on the row, so it is found before the columns are.
    labelled: list[tuple[str, list[tuple[float, float, float]]]] = []
    top_of_table = None
    for row in rows:
        numbers = _merge_numbers(row)
        if not numbers:
            continue
        leftmost = min(n[1] for n in numbers)
        label = _label_of(row, leftmost - 1.0)
        if not label:
            continue
        column = _match_label(label)
        if column is None:
            continue
        labelled.append((column, numbers))
        row_top = min(w["top"] for w in row)
        top_of_table = row_top if top_of_table is None else min(top_of_table, row_top)

    if not labelled:
        raise NoteDecodeError(
            "no row of the quotation table matched a known label. Expected one "
            "of %s" % ", ".join(sorted(PRINTED_ROWS))
        )

    seen = [c for c, _ in labelled]
    duplicates = sorted({c for c in seen if seen.count(c) > 1})
    if duplicates:
        raise NoteDecodeError(
            "the quotation table carries two rows for %s, so a label matched "
            "twice and the parse cannot be trusted" % ", ".join(duplicates)
        )

    # Step 2. The columns, from where the values actually are.
    centres = _cluster_centres(n[1] for _, numbers in labelled for n in numbers)
    if len(centres) < 3:
        raise NoteDecodeError(
            "the quotation table yielded %d value column(s), expected 3 in the "
            "2024 layout or 6 from December 2025" % len(centres)
        )

    # Step 3. Name each column from the nearest header. Headers sit above the
    # first labelled row; the provisional marker sits below its own header, so
    # the band searched is generous upward and tight downward.
    header_words = [w for w in words if w["bottom"] <= float(top_of_table) + 1.0]

    weekly_columns: dict[float, date] = {}
    monthly_columns: dict[float, tuple[int, int]] = {}
    named: set[float] = set()
    provisional_x: list[float] = []

    for word in header_words:
        text = str(word["text"])
        centre = (word["x0"] + word["x1"]) / 2.0
        nearest = min(centres, key=lambda c: abs(c - centre))
        if abs(nearest - centre) > 30.0:
            continue
        parsed_date = parse_fr_date(text)
        if parsed_date is not None:
            weekly_columns[nearest] = parsed_date
            named.add(nearest)
            continue
        parsed_month = parse_fr_month(text)
        if parsed_month is not None:
            monthly_columns[nearest] = parsed_month
            named.add(nearest)
            continue
        squashed = _squash(text)
        if squashed.startswith("variation"):
            named.add(nearest)
        if "provisoire" in squashed:
            provisional_x.append(centre)

    if len(weekly_columns) != 2:
        raise NoteDecodeError(
            "the quotation table yielded %d weekly column(s), expected exactly 2. "
            "Found headers naming %s"
            % (
                len(weekly_columns),
                ", ".join(str(d) for d in sorted(weekly_columns.values())) or "none",
            )
        )

    weekly: dict[date, dict[str, float]] = {d: {} for d in weekly_columns.values()}
    monthly: dict[tuple[int, int], dict[str, float]] = {m: {} for m in monthly_columns.values()}

    for column, numbers in labelled:
        for value, centre, _ in numbers:
            nearest = min(centres, key=lambda c: abs(c - centre))
            if nearest in weekly_columns:
                weekly[weekly_columns[nearest]][column] = value
            elif nearest in monthly_columns:
                monthly[monthly_columns[nearest]][column] = value

    provisional: dict[tuple[int, int], bool] = {}
    for centre, month in monthly_columns.items():
        provisional[month] = any(abs(x - centre) <= 30.0 for x in provisional_x)

    return {
        "weekly": weekly,
        "monthly": monthly,
        "monthly_provisional": provisional,
        "diagnostics": {
            "value_columns": len(centres),
            "rows_matched": sorted(c for c, _ in labelled),
            "weekly_dates": sorted(str(d) for d in weekly_columns.values()),
            "monthly_columns": sorted("%04d-%02d" % m for m in monthly_columns.values()),
        },
    }


# ---------------------------------------------------------------------------
# The chart
# ---------------------------------------------------------------------------

def _chart_polylines(page) -> tuple[list, int]:
    """The four long polylines of the price chart, and their common length.

    The page carries a fifth, shorter polyline of 61 points, which is the monthly
    MBR chart below. It is dropped by taking the modal length among the long
    curves, and it is redundant anyway because DGEC publishes the MBR as a
    workbook back to 2015.
    """
    long_curves = [c for c in page.curves if len(c.get("pts", ())) >= GATES["min_points"]]
    if not long_curves:
        raise NoteDecodeError(
            "the quotation page carries no polyline of %d points or more, so "
            "there is no chart to decode" % GATES["min_points"]
        )
    lengths = [len(c["pts"]) for c in long_curves]
    modal = max(set(lengths), key=lengths.count)
    series = [c for c in long_curves if len(c["pts"]) == modal]
    if len(series) != GATES["chart_series"]:
        raise NoteDecodeError(
            "the chart yielded %d polyline(s) of %d points, expected exactly %d "
            "of equal length. Lengths seen: %s"
            % (len(series), modal, GATES["chart_series"], sorted(lengths))
        )
    return series, modal


def _value_axis(page, box: tuple[float, float, float, float]) -> tuple[float, float, list, float]:
    """Fit $/t against page y from the tick labels left of the plot area.

    Returns (intercept, slope, ticks, worst residual).
    """
    x0, x1, y0, y1 = box
    bands: dict[float, list] = defaultdict(list)
    for char in page.chars:
        if char["x1"] < x0 - 1 and char["x0"] > x0 - 50 and y0 - 70 < char["top"] < y1 + 70:
            bands[round(char["top"], 1)].append(char)

    ticks: list[tuple[float, float]] = []
    for top, chars in bands.items():
        chars.sort(key=lambda c: c["x0"])
        text = re.sub("[%s]" % _SPACES, "", "".join(c["text"] for c in chars))
        if re.fullmatch(r"\d{2,5}", text):
            # The label's vertical centre, taken as the midpoint of its own
            # glyph box. This carries a systematic bias, because a digit's
            # visual centre is not the centre of its font bounding box, and that
            # bias is what the per note offset in calibrate() removes.
            ticks.append(((top + chars[0]["bottom"]) / 2.0, float(text)))
    ticks.sort()

    if len(ticks) < GATES["min_y_ticks"]:
        raise NoteDecodeError(
            "only %d y axis tick label(s) parsed, the minimum is %d. The value "
            "axis cannot be fitted" % (len(ticks), GATES["min_y_ticks"])
        )

    intercept, slope = _least_squares(ticks)
    worst = max(abs(intercept + slope * position - value) for position, value in ticks)
    if worst > GATES["max_tick_residual_usd_t"]:
        raise NoteDecodeError(
            "the value axis does not fit its own tick labels: worst residual "
            "%.3f $/t against a limit of %.2f. The axis may not be linear or a "
            "tick label was misread" % (worst, GATES["max_tick_residual_usd_t"])
        )
    return intercept, slope, ticks, worst


def _x_axis_dates(page, box: tuple[float, float, float, float]) -> list[tuple[float, date]]:
    """The dated x axis labels under the plot area, left to right."""
    x0, x1, y0, y1 = box
    bands: dict[float, list] = defaultdict(list)
    for char in page.chars:
        if y1 + 1 < char["top"] < y1 + 95 and x0 - 12 < char["x0"] < x1 + 12:
            bands[round((char["x0"] + char["x1"]) / 2.0, 0)].append(char)
    dates: list[tuple[float, date]] = []
    for centre, chars in bands.items():
        # The labels are rotated, so the characters read bottom to top.
        chars.sort(key=lambda c: -c["y0"])
        parsed = parse_fr_date("".join(c["text"] for c in chars))
        if parsed is not None:
            dates.append((centre, parsed))
    dates.sort()
    if len(dates) < 2:
        raise NoteDecodeError(
            "the chart's x axis yielded %d dated label(s), at least 2 are needed "
            "to establish the spacing" % len(dates)
        )
    return dates


def _legend(page, box: tuple[float, float, float, float]) -> dict[str, str]:
    """Stroke colour to cache column, read off the legend of this note only.

    Never compare colours across notes. Recon 05 section 10: two of the ten
    notes round the same colour differently, (1.0, 0.6, 0.0) against
    (1.0, 0.599609, 0.0), so a parser keyed on a colour constant would find
    nothing in those two.
    """
    x0, x1, y0, y1 = box
    mapping: dict[str, str] = {}
    words = page.extract_words()
    for shape in list(page.curves) + list(page.lines):
        points = shape.get("pts") or [
            (shape["x0"], shape["top"]),
            (shape["x1"], shape["bottom"]),
        ]
        if len(points) > 6 or not shape.get("stroking_color"):
            continue
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        if max(xs) - min(xs) >= 40 or min(ys) <= y1:
            continue
        centre_y = sum(ys) / len(ys)
        right = max(xs)
        beside = sorted(
            (
                w
                for w in words
                if abs((w["top"] + w["bottom"]) / 2.0 - centre_y) < 6
                and 0 < w["x0"] - right < 90
            ),
            key=lambda w: w["x0"],
        )
        if not beside:
            continue
        text = _squash(" ".join(str(w["text"]) for w in beside[:3]))
        for legend_label in sorted(CHART_PRODUCTS, key=len, reverse=True):
            if text.startswith(legend_label):
                mapping.setdefault(str(shape["stroking_color"]), CHART_PRODUCTS[legend_label])
                break
    return mapping


def _calibrate(
    raw: Mapping[str, list[float]],
    printed: Mapping[str, dict[str, float]],
    weekly_dates: Sequence[date],
) -> tuple[float, list[tuple[str, str, float, float]], dict]:
    """Fit one additive offset per note on the printed anchors, and check it.

    The two anchors per series are the note's own printed latest and previous
    weekly averages, which are by construction the last two chart points. Four
    series times two weeks is eight anchors.

    THE OFFSET CANNOT BE HARDCODED. Recon 05 section 11 measured it across the
    ten notes at -2.38 to +2.82 $/t, and it CHANGES SIGN between notes, so a
    constant would be right for one note and wrong for the rest. It is fitted per
    note, on that note's own printed figures, which is the whole reason the
    reconstruction is calibratable at all.

    Returns (offset, anchors, diagnostics).
    """
    latest, previous = weekly_dates[-1], weekly_dates[-2]
    anchors: list[tuple[str, str, float, float]] = []
    for column, values in raw.items():
        for when, decoded in ((latest, values[-1]), (previous, values[-2])):
            printed_value = printed.get(when, {}).get(column)
            if printed_value is None:
                continue
            anchors.append((column, str(when), decoded, float(printed_value)))

    if len(anchors) != GATES["anchors"]:
        raise NoteDecodeError(
            "the chart could be anchored on %d printed value(s), expected %d, "
            "four plotted series times the two printed weeks"
            % (len(anchors), GATES["anchors"])
        )

    residuals = [printed - decoded for _, _, decoded, printed in anchors]
    offset = statistics.mean(residuals)
    after = [abs(decoded + offset - printed) for _, _, decoded, printed in anchors]
    worst = max(after)

    if worst > GATES["max_anchor_residual_usd_t"]:
        worst_anchor = max(
            zip(anchors, after), key=lambda pair: pair[1]
        )[0]
        raise NoteDecodeError(
            "after fitting the per note offset of %+.3f $/t the worst anchor is "
            "still %.3f $/t out, against a limit of %.2f. The worst is %s on %s, "
            "decoded %.2f against a printed %.0f. The chart decode is not "
            "trustworthy for this note and nothing from it is used"
            % (
                offset,
                worst,
                GATES["max_anchor_residual_usd_t"],
                worst_anchor[0],
                worst_anchor[1],
                worst_anchor[2] + offset,
                worst_anchor[3],
            )
        )

    # Leave one series out, the out of sample figure. Reported, never gated: it
    # is a property of the note worth carrying into the manifest, and recon 05
    # measured 0.17 to 0.44 $/t across the corpus.
    out_of_sample: list[float] = []
    for held_out in sorted({a[0] for a in anchors}):
        train = [a for a in anchors if a[0] != held_out]
        test = [a for a in anchors if a[0] == held_out]
        if not train or not test:
            continue
        fitted = statistics.mean(printed - decoded for _, _, decoded, printed in train)
        out_of_sample += [abs(decoded + fitted - printed) for _, _, decoded, printed in test]

    diagnostics = {
        "offset_usd_t": round(offset, 4),
        "offset_sd_usd_t": round(statistics.pstdev(residuals), 4),
        "anchor_mae_usd_t": round(statistics.mean(after), 4),
        "anchor_worst_usd_t": round(worst, 4),
        "leave_one_series_out_mae_usd_t": (
            round(statistics.mean(out_of_sample), 4) if out_of_sample else None
        ),
        "leave_one_series_out_worst_usd_t": (
            round(max(out_of_sample), 4) if out_of_sample else None
        ),
    }
    return offset, anchors, diagnostics


def decode_note(path: str | Path) -> NoteDecode:
    """Read one weekly note: its printed table and its decoded chart.

    Every gate in GATES is applied here, and any one of them raises. A note that
    raises contributes NOTHING to either series: no partial values, no fallback
    to a neighbouring note's calibration, no guess.

    Raises:
        NoteDecodeError: on any gate. The message always names the measurement
            that failed and the limit it failed against.
    """
    import pdfplumber  # imported here so the module imports without it installed

    path = Path(path)
    with pdfplumber.open(str(path)) as pdf:
        page_number, page = find_quotation_page(pdf)

        table = parse_printed_table(page)
        weekly_dates = sorted(table["weekly"])

        series, n_points = _chart_polylines(page)
        xs = [p[0] for c in series for p in c["pts"]]
        ys = [p[1] for c in series for p in c["pts"]]
        box = (min(xs), max(xs), min(ys), max(ys))

        intercept, slope, ticks, tick_residual = _value_axis(page, box)
        x_dates = _x_axis_dates(page, box)
        legend = _legend(page, box)

        # pdfplumber's curve points are already in TOP DOWN page coordinates,
        # identical to char["top"], not in PDF bottom up space. Recon 05 section
        # 10 flags this because getting it wrong produces plausible looking
        # garbage rather than an error.
        raw: dict[str, list[float]] = {}
        for curve in series:
            colour = str(curve["stroking_color"])
            column = legend.get(colour)
            if column is None:
                continue
            points = sorted(curve["pts"], key=lambda p: p[0])
            raw[column] = [intercept + slope * p[1] for p in points]

        missing = [c for c in CHART_COLUMNS if c not in raw]
        if missing:
            raise NoteDecodeError(
                "the legend did not identify %s. Colours on the chart: %s, "
                "colours named in the legend: %s"
                % (
                    ", ".join(missing),
                    ", ".join(sorted(str(c["stroking_color"]) for c in series)),
                    ", ".join(sorted(legend)) or "none",
                )
            )

    # The spacing is MEASURED, not assumed. The point pitch divided by the x
    # label pitch, scaled by the weeks between the first and last label, is the
    # implied number of weeks per point.
    label_span_weeks = (x_dates[-1][1] - x_dates[0][1]).days / 7.0 / (len(x_dates) - 1)
    label_pitch = (x_dates[-1][0] - x_dates[0][0]) / (len(x_dates) - 1)
    point_pitch = (box[1] - box[0]) / (n_points - 1)
    weeks_per_point = point_pitch / (label_pitch / label_span_weeks)
    low, high = GATES["weeks_per_point"]
    if not (low <= weeks_per_point <= high):
        raise NoteDecodeError(
            "the chart's points are %.4f weeks apart, outside [%.2f, %.2f], so "
            "the spacing is not weekly and the dates cannot be assigned"
            % (weeks_per_point, low, high)
        )

    # The last point carries the last x axis label's date, and the label must
    # agree with the note's own printed latest week. This is what ties the chart
    # to the table and it is what makes NPG-2026.04.17's filename versus content
    # mismatch harmless: the date comes from the document, never from the name.
    last_week = x_dates[-1][1]
    if last_week != weekly_dates[-1]:
        raise NoteDecodeError(
            "the chart's last x axis label is %s but the table's latest printed "
            "weekly column is %s. The two must be the same week or the chart "
            "cannot be dated" % (last_week, weekly_dates[-1])
        )

    point_dates = [last_week - timedelta(weeks=(n_points - 1 - k)) for k in range(n_points)]
    offset, anchors, calibration = _calibrate(raw, table["weekly"], weekly_dates)

    chart = {
        column: {point_dates[k]: values[k] + offset for k in range(n_points)}
        for column, values in raw.items()
    }

    diagnostics = {
        "page": page_number,
        "n_points": n_points,
        "n_y_ticks": len(ticks),
        "y_tick_range": [ticks[-1][1], ticks[0][1]],
        "max_tick_residual_usd_t": round(tick_residual, 4),
        "n_x_labels": len(x_dates),
        "weeks_per_point": round(weeks_per_point, 4),
        "point_pitch_pt": round(point_pitch, 4),
        "first_week": str(point_dates[0]),
        "last_week": str(point_dates[-1]),
        "anchors": [(c, w, round(d + offset, 2), p) for c, w, d, p in anchors],
    }
    diagnostics.update(calibration)
    diagnostics.update(table["diagnostics"])

    # The geometry signature. Two notes that share it map an identical value onto
    # an identical pixel and therefore CANNOT disagree, so counting them as two
    # independent observations of a week would overstate the cross check. See
    # DEGENERATE_PAIR.
    geometry = (
        len(ticks),
        round(ticks[0][1], 3),
        round(ticks[-1][1], 3),
        round(point_pitch, 3),
    )

    return NoteDecode(
        file=path.name,
        page=page_number,
        vintage=weekly_dates[-1],
        printed_weekly=table["weekly"],
        printed_monthly=table["monthly"],
        printed_monthly_provisional=table["monthly_provisional"],
        chart=chart,
        geometry=geometry,
        diagnostics=diagnostics,
    )


# ---------------------------------------------------------------------------
# The corpus
# ---------------------------------------------------------------------------

def note_paths(directory: Path | None = None) -> list[Path]:
    """Every weekly note PDF in the corpus, sorted by file name.

    The methodology PDFs that live in the same directory, mbr_method.pdf,
    methodo_prix.pdf and tuto.pdf, do not match NOTE_GLOB and are not notes.
    """
    directory = Path(directory) if directory is not None else NOTE_DIR
    return sorted(directory.glob(NOTE_GLOB))


#: The landing page that links the ONE note that is online. Recon 02 section 2.3:
#: never construct the PDF URL from a date. Drupal appends a duplicate counter,
#: "_0", "_1", at upload time, the label and the href disagree about it in both
#: directions, and every constructed spelling of a note that has been replaced
#: returns 404. Read the href.
LANDING_PAGE = "https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers"

_NPG_HREF = re.compile(r'href="([^"]*/NPG-[^"]*\.pdf)"', re.IGNORECASE)


def collect_current_note(
    directory: Path | None = None, *, delay: float = 3.0
) -> tuple[Path, bool]:
    """Fetch the one note that is online and preserve it. Two requests.

    THIS IS THE ONLY WAY THE SERIES GROWS. The ministry publishes one note at a
    time and deletes the previous one, and the Internet Archive holds nine in
    total, so every week this is not run is a week that is gone. Recon 02 section
    2.5: there is no archive to crawl and no URL pattern to walk backwards.

    Returns (path, downloaded). downloaded is False when the note already sits in
    the corpus, which is the ordinary case between publications.

    It NEVER overwrites a file already in the corpus. Those PDFs are
    irreplaceable and a re-download that differed would be a finding, not a
    correction. Verified on 2026-09-13: the live NPG-2026.09.04.pdf is byte for
    byte identical to the preserved copy, sha256
    a364a4fae11c95e9173f3314f2932077f67949cd9d8c3d05b8f8d29c042c13b9, 2,406,779
    bytes.

    Raises:
        NoteDecodeError: when the landing page carries no NPG link. Guessing a
            URL from today's date is exactly what recon 02 section 2.3 says not
            to do.
    """
    from .base import http_get

    directory = Path(directory) if directory is not None else NOTE_DIR
    page = http_get(LANDING_PAGE, delay=delay)
    hrefs = sorted(set(_NPG_HREF.findall(page.text)))
    if not hrefs:
        raise NoteDecodeError(
            "the DGEC landing page at %s carries no link to an NPG pdf. The page "
            "layout changed, or the ministry has taken the note down. Do NOT "
            "construct the URL from a date: recon 02 section 2.2 probed fourteen "
            "constructed spellings and every one of them returned 404"
            % LANDING_PAGE
        )
    if len(hrefs) > 1:
        raise NoteDecodeError(
            "the landing page links %d NPG pdfs, %s. Exactly one note is online "
            "at a time, so this is a layout change worth looking at before "
            "anything is downloaded" % (len(hrefs), ", ".join(hrefs))
        )
    url = hrefs[0]
    target = directory / url.rsplit("/", 1)[-1]
    if target.exists():
        return target, False

    response = http_get(url, delay=delay, timeout=90)
    content_type = (response.headers.get("content-type") or "").lower()
    if "pdf" not in content_type:
        raise NoteDecodeError(
            "%s answered %s, not a pdf" % (url, content_type or "no content type")
        )
    directory.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)
    return target, True


def load_corpus(directory: Path | None = None, *, strict: bool = True) -> list[NoteDecode]:
    """Decode every note in the corpus.

    Args:
        strict: the default, and what the adapters use. Any note that trips a
            gate raises, so the adapter keeps its previous cache and records a
            failed manifest entry. This is deliberately louder than dropping the
            note: all ten notes in the corpus decode today, so a gate firing
            means the layout changed or a file is damaged, and quietly shipping a
            shorter series would hide that. Pass False only in a diagnostic.

    Raises:
        NoteDecodeError: when strict and any note fails, or when the corpus is
            empty.
    """
    paths = note_paths(directory)
    if not paths:
        raise NoteDecodeError(
            "no weekly note matching %s under %s. The notes are irreplaceable and "
            "are not committed, so this directory is empty on a fresh checkout"
            % (NOTE_GLOB, directory or NOTE_DIR)
        )
    decoded: list[NoteDecode] = []
    failures: list[str] = []
    for path in paths:
        try:
            decoded.append(decode_note(path))
        except NoteDecodeError as exc:
            failures.append("%s: %s" % (path.name, exc))
            if strict:
                raise NoteDecodeError(
                    "%s failed a decode gate, so nothing from it is used and the "
                    "series is not rebuilt. %s" % (path.name, exc)
                ) from exc
    if failures:
        # Only reachable with strict False, which is a diagnostic path. The
        # failures are surfaced rather than swallowed even there.
        print(
            "dgec_note: %d note(s) failed to decode and contributed nothing: %s"
            % (len(failures), "; ".join(failures)),
            file=sys.stderr,
        )
    return decoded


# ---------------------------------------------------------------------------
# The printed series
# ---------------------------------------------------------------------------

def build_printed_weekly(notes: Sequence[NoteDecode]) -> pd.DataFrame:
    """The values DGEC printed, one row per distinct printed week.

    Every note prints two weekly columns and some of them reprint a week an
    adjacent note already printed, so the series is shorter than twice the number
    of notes. That is the whole published weekly record and it is not padded.

    Where two notes print the same week, the values are checked against each
    other and any disagreement is carried in max_disagreement_usd_t rather than
    averaged away. A revision is a fact about the source, not noise.

    WHERE ONLY ONE NOTE PRINTS THE WEEK, max_disagreement_usd_t IS NaN. It used
    to be 0, which read as "the notes agreed" on most of the weeks, where there
    was never a second note to agree with. See UNDEFINED_SPREAD.
    """
    per_week: dict[date, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    sources: dict[date, list[str]] = defaultdict(list)
    for note in notes:
        for when, values in note.printed_weekly.items():
            sources[when].append(note.file)
            for column, value in values.items():
                per_week[when][column].append(float(value))

    rows = []
    for when in sorted(per_week):
        row: dict[str, Any] = {"date": pd.Timestamp(when)}
        worst = 0.0
        compared = False
        for column in PRINTED_COLUMNS:
            seen = per_week[when].get(column, [])
            if not seen:
                # The row is not printed in that layout era. NaN, never filled.
                row[column] = float("nan")
                continue
            row[column] = seen[0]
            if len(seen) > 1:
                compared = True
                worst = max(worst, max(seen) - min(seen))
        row["n_notes"] = len(sources[when])
        # Undefined, not zero, when no column of this week was ever printed
        # twice. UNDEFINED_SPREAD.
        row["max_disagreement_usd_t"] = worst if compared else float("nan")
        row["notes"] = ";".join(sorted(sources[when]))
        rows.append(row)

    frame = pd.DataFrame(rows)
    ordered = ["date"] + list(PRINTED_COLUMNS) + ["n_notes", "max_disagreement_usd_t", "notes"]
    return frame[ordered].sort_values("date").reset_index(drop=True)


#: The columns of dgec_note_printed_monthly, after the seven value columns.
PRINTED_MONTHLY_COLUMNS = (
    "provisional",
    "vintage",
    "first_vintage",
    "n_prints",
    "revised",
    "max_revision_usd_t",
    "notes",
    "revision_history",
)


def _print_signature(values: Mapping[str, float]) -> tuple:
    """One print of one month, as a comparable tuple over the seven columns."""
    return tuple(values.get(column) for column in PRINTED_COLUMNS)


def _format_print(vintage: date, provisional: bool, values: Mapping[str, float]) -> str:
    """One vintage of one month as a single field of revision_history.

    Pipe separated and equals separated, with NO comma anywhere, so the field
    never needs CSV quoting and a reader can split it with two string splits.
    """
    parts = [
        vintage.isoformat(),
        "provisional" if provisional else "final",
    ]
    for column in PRINTED_COLUMNS:
        value = values.get(column)
        if value is None:
            continue
        parts.append("%s=%s" % (column, ("%g" % float(value))))
    return "|".join(parts)


def build_printed_monthly(notes: Sequence[NoteDecode]) -> pd.DataFrame:
    """The MONTHLY columns the notes print, with every vintage of every month.

    SPEC.md section 2 rule 5: "Provisional is labelled provisional. The current
    month in the ministry notes is provisional and gets revised. Keep every
    vintage, show the flag." This is the series that keeps that promise, and it
    is the only place in the project where a DGEC figure is seen moving.

    The monthly columns only exist from the December 2025 six column layout
    onward, recon 02 section 3.3, so this is 7 months from 6 of the 10 notes, and
    DGEC publishes no monthly product history anywhere else at all. It is also
    the only monthly home of Jet and Fioul lourd TBTS.

    ONE ROW PER MONTH, CARRYING THE LATEST PRINT
    ---------------------------------------------
    A cache file is one row per date, so the seven value columns carry the LATEST
    print of that month: the final figure when one has been printed, otherwise
    the most recent provisional one. A final figure replaces a provisional one
    and never the other way round. Recon 02 section 3.5 measured a 2 $/bbl swing
    between the two on the MBR, so blending them would be a real error.

    EVERY EARLIER PRINT IS STILL IN THE ROW
    ----------------------------------------
    revision_history carries every vintage of the month, in order, with its
    provisional flag and all seven values, so nothing is discarded and the
    revision can be read out of the committed file rather than out of the PDFs.
    Two things the corpus shows, and neither is small:

        March 2026 went 946 / 1163 Eurosuper / Gazole provisional on 20 March,
        976 / 1202 provisional on 27 March, then 988 / 1219 FINAL on 3 April and
        unchanged on 24 April. A provisional to final transition, observed.

        April 2026 went 1088 / 1431 provisional on 3 April and 1067 / 1288
        provisional on 24 April. A revision of 143 $/t on Gazole between two
        provisional prints of the same month, which is the size of the thing
        SPEC.md section 2 rule 5 is warning about.

    max_revision_usd_t is the largest absolute move between the first print and
    the kept one, across the six $/t columns, and it is NaN where the month has
    been printed only once, because a revision over one print is undefined rather
    than zero. UNDEFINED_SPREAD.
    """
    per_month: dict[tuple[int, int], list[tuple[date, str, bool, dict[str, float]]]] = (
        defaultdict(list)
    )
    for note in notes:
        for month, values in note.printed_monthly.items():
            per_month[month].append(
                (
                    note.vintage,
                    note.file,
                    bool(note.printed_monthly_provisional.get(month, False)),
                    {c: float(v) for c, v in values.items()},
                )
            )

    ordered_columns = ["date"] + list(PRINTED_COLUMNS) + list(PRINTED_MONTHLY_COLUMNS)
    if not per_month:
        return pd.DataFrame(columns=ordered_columns)

    rows = []
    for month in sorted(per_month):
        prints = sorted(per_month[month], key=lambda item: (item[0], item[1]))
        finals = [p for p in prints if not p[2]]
        kept = finals[-1] if finals else prints[-1]
        first = prints[0]

        row: dict[str, Any] = {"date": pd.Timestamp(month[0], month[1], 1)}
        for column in PRINTED_COLUMNS:
            value = kept[3].get(column)
            row[column] = float("nan") if value is None else float(value)

        row["provisional"] = bool(kept[2])
        row["vintage"] = kept[0].isoformat()
        row["first_vintage"] = first[0].isoformat()
        row["n_prints"] = len(prints)
        row["revised"] = bool(
            len(prints) > 1 and _print_signature(first[3]) != _print_signature(kept[3])
        )
        if len(prints) > 1:
            # The six $/t columns only. The seventh is the same fioul lourd row
            # in EUR/t and a move measured in euros does not belong in a column
            # named usd_t.
            moves = [
                abs(float(kept[3][c]) - float(first[3][c]))
                for c in PRINTED_COLUMNS
                if c != PRINTED_EUR_COLUMN and c in kept[3] and c in first[3]
            ]
            row["max_revision_usd_t"] = max(moves) if moves else float("nan")
        else:
            # Undefined, not zero. There is no earlier print to differ from.
            row["max_revision_usd_t"] = float("nan")
        row["notes"] = ";".join(sorted({p[1] for p in prints}))
        row["revision_history"] = ";".join(
            _format_print(p[0], p[2], p[3]) for p in prints
        )
        rows.append(row)

    frame = pd.DataFrame(rows)
    return frame[ordered_columns].sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# The reconstructed series
# ---------------------------------------------------------------------------

def _evidence_class(
    when: date,
    n_notes: int,
    n_geometries: int,
    first_corroborated: date | None,
    last_corroborated: date | None,
) -> str:
    """How well defended one reconstructed week is. One of EVIDENCE_CLASSES.

    cross_checked answers "is there a second independent reading", which is the
    first question. This answers the second one, "and if not, where does this
    week sit on the chart that is its only source", because the calibration
    anchors are all at the right hand end and an uncorroborated week at the left
    end is a different object from an uncorroborated week at the right end.
    OLDEST_WEEKS_ARE_WEAK_TWICE sets out why the distinction earns a column.
    """
    if n_notes == 0:
        return "no_coverage"
    if n_geometries > 1:
        return "cross_checked"
    if first_corroborated is not None and when < first_corroborated:
        return "single_geometry_oldest"
    if last_corroborated is not None and when > last_corroborated:
        return "single_geometry_newest"
    return "single_geometry_interior"


def build_reconstructed_weekly(notes: Sequence[NoteDecode]) -> pd.DataFrame:
    """Stitch the decoded charts of every note into one weekly series.

    The central value of each week is the MEDIAN across the notes that cover it,
    not the mean, because a median is unmoved by one note whose axis fit is
    slightly off, and not the latest note, because the latest note has no claim
    to be the best on a week five hundred days behind its right hand edge.

    Four columns carry the honesty of the thing, and recon 05 section 14
    conditions 3 and 5 require all four:

        n_notes                     how many notes cover this week
        n_independent_geometries    how many DISTINCT chart geometries cover it.
                                    Two notes with the same axis scale and point
                                    pitch cannot disagree, so they are one piece
                                    of evidence, not two. See DEGENERATE_PAIR.
        cross_checked               False where n_independent_geometries is 1.
                                    Those weeks have NO cross check at all, and
                                    how many there are is counted into the
                                    manifest note rather than written here: a
                                    collection moves it, usually downward.
                                    COLLECTION_RESTITCHES_HISTORY.
        evidence_class              WHICH kind of week this is, one of
                                    EVIDENCE_CLASSES. cross_checked is a boolean
                                    and the weeks it marks False are not equally
                                    weak, so this column separates them.
                                    single_geometry_oldest is the six weeks of
                                    July and early August 2022 that are BOTH
                                    uncorroborated AND at the extreme unanchored
                                    left of the only note that draws them. See
                                    OLDEST_WEEKS_ARE_WEAK_TWICE.
        spread_<product>_usd_t      the highest minus the lowest note on that
                                    week, per product. NaN, not zero, where only
                                    one geometry covers it: a spread over one
                                    reading is undefined, and a zero there would
                                    read as agreement. See UNDEFINED_SPREAD.

    A week inside the span that no note covers gets a row of NaN with n_notes
    zero rather than being dropped, so a hole is visible in the file and in the
    manifest instead of being invisible in a shorter frame. There are none today.
    """
    per_week: dict[date, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    coverage: dict[date, list[str]] = defaultdict(list)
    geometries: dict[date, set] = defaultdict(set)

    for note in notes:
        for column, values in note.chart.items():
            for when, value in values.items():
                per_week[when][column].append(value)
        for when in note.weeks:
            coverage[when].append(note.file)
            geometries[when].add(note.geometry)

    if not per_week:
        raise NoteDecodeError("no note yielded a decoded chart")

    first, last = min(per_week), max(per_week)
    span = [first + timedelta(weeks=k) for k in range(((last - first).days // 7) + 1)]

    # Which weeks have real, independent, time domain evidence. The boundary of
    # that block is what tells an uncorroborated week at the unanchored left end
    # apart from one sitting on the anchored right end, and it is measured here
    # rather than hardcoded as a pair of dates, so the day a new note arrives the
    # classification moves with it.
    corroborated = [w for w in span if len(geometries.get(w, set())) > 1]
    first_corroborated = min(corroborated) if corroborated else None
    last_corroborated = max(corroborated) if corroborated else None

    rows = []
    for when in span:
        row: dict[str, Any] = {"date": pd.Timestamp(when)}
        for column in CHART_COLUMNS:
            seen = per_week.get(when, {}).get(column, [])
            if len(seen) > 1:
                row[column] = float(statistics.median(seen))
                row["spread_%s" % column] = float(max(seen) - min(seen))
            elif seen:
                row[column] = float(seen[0])
                # One reading. The spread is UNDEFINED, not zero. Writing zero
                # here would state that two notes agreed when there was never a
                # second note. UNDEFINED_SPREAD.
                row["spread_%s" % column] = float("nan")
            else:
                row[column] = float("nan")
                row["spread_%s" % column] = float("nan")
        row["n_notes"] = len(coverage.get(when, []))
        row["n_independent_geometries"] = len(geometries.get(when, set()))
        row["cross_checked"] = bool(row["n_independent_geometries"] > 1)
        row["evidence_class"] = _evidence_class(
            when,
            row["n_notes"],
            row["n_independent_geometries"],
            first_corroborated,
            last_corroborated,
        )
        rows.append(row)

    frame = pd.DataFrame(rows)
    ordered = (
        ["date"]
        + list(CHART_COLUMNS)
        + ["n_notes", "n_independent_geometries", "cross_checked", "evidence_class"]
        + ["spread_%s" % c for c in CHART_COLUMNS]
    )
    return frame[ordered].sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# The cracks
# ---------------------------------------------------------------------------

def weekly_cracks(frame: pd.DataFrame) -> pd.DataFrame:
    """Weekly gasoil and gasoline cracks from a weekly $/t frame. SPEC.md 4.2.

        crack_gasoil   = gazole_usd_t     / BBL_PER_T_GASOIL   - brent_usd_bbl
        crack_gasoline = eurosuper_usd_t  / BBL_PER_T_GASOLINE - brent_usd_bbl

    Both legs come from the SAME table on the SAME page of the SAME note, so they
    share a date and an averaging window by construction, which is what SPEC.md
    section 4.2 demands and what a weekly product against a monthly crude would
    break.

    THE BRENT LEG. The note prints Brent date in $/t and this converts it back
    with DGEC_BBL_PER_T_BRENT_NOTE, 7.5, which recon 02 section 4.3 recovered
    from five month pairs against DGEC's own published Brent workbook, exactly
    7.5 every time. The other DGEC factor, 7.55, belongs to the CAF Brent inside
    the MBR calculation and using it here would be a silent 0.67 percent error on
    the crude leg.

    THE PRODUCT LEGS ARE NOT THE FUTURES THEY ARE DIVIDED BY. SPEC.md section 4.2
    is explicit: Gazole is road diesel quoted in Rotterdam and Eurosuper is
    finished premium gasoline, not Eurobob blendstock. The divisors are the ICE
    contract conventions, so the crack is quoted on that convention, and the
    Method view says so. The gasoline leg in particular disagrees with the OPEC
    Rotterdam premium gasoline 98 crack by up to 13 $/bbl and that gap is
    reported, never tuned away. See config.BBL_PER_T_GASOLINE.
    """
    out = pd.DataFrame({"date": pd.to_datetime(frame["date"])})
    brent_usd_bbl = pd.to_numeric(frame["brent_date_usd_t"], errors="coerce") / (
        DGEC_BBL_PER_T_BRENT_NOTE
    )
    out["brent_usd_bbl"] = brent_usd_bbl
    out["crack_gasoil_usd_bbl"] = (
        pd.to_numeric(frame["gazole_usd_t"], errors="coerce") / BBL_PER_T_GASOIL
        - brent_usd_bbl
    )
    out["crack_gasoline_usd_bbl"] = (
        pd.to_numeric(frame["eurosuper_usd_t"], errors="coerce") / BBL_PER_T_GASOLINE
        - brent_usd_bbl
    )
    if "fioul_domestique_usd_t" in frame.columns:
        # Fioul domestique is a heating gasoil of the same family as Gazole, so
        # the gasoil divisor is the closest published convention. It is a
        # DIFFERENT product from road diesel and it is labelled as one: this
        # column exists because the chart plots it, not because ICE lists it.
        out["crack_fioul_domestique_usd_bbl"] = (
            pd.to_numeric(frame["fioul_domestique_usd_t"], errors="coerce")
            / BBL_PER_T_GASOIL
            - brent_usd_bbl
        )
    # The provenance columns travel with the cracks, because a crack is exactly
    # as defended as the two quotations it was computed from and a reader of this
    # file must not have to join back to find that out. evidence_class in
    # particular: the six weeks marked single_geometry_oldest carry a crack whose
    # only evidence is one unanchored end of one chart.
    for carried in (
        "n_notes",
        "n_independent_geometries",
        "cross_checked",
        "evidence_class",
    ):
        if carried in frame.columns:
            out[carried] = frame[carried]
    return out


# ---------------------------------------------------------------------------
# The adapters
# ---------------------------------------------------------------------------

_CORPUS_NOTE = (
    "Built from the %d weekly note PDFs preserved under data/private/dgec_notes/, "
    "which were machine fetched from ecologie.gouv.fr and the Internet Archive. "
    "The PDFs are not committed. The ministry publishes one note at a time and "
    "deletes the previous one, so this corpus cannot be rebuilt from the web and "
    "the only way the series grows is prospective collection: run "
    "'python scripts/note.py' (make note) weekly. READ fetched_at "
    "CAREFULLY: it is when this run read the preserved documents, not when the "
    "documents were downloaded, and last_date is the honest end of the data."
)


#: The last words of _CORPUS_NOTE. Everything after it in a manifest note is
#: derived from the committed cache alone, so offline can restate it; everything
#: before it counts PDFs a clean checkout does not have. See _restate_note.
_CORPUS_NOTE_END = "last_date is the honest end of the data."


def _restate_note(previous: str, body: str) -> str:
    """The committed note's corpus sentence, then a freshly measured body.

    scripts/refresh.py --offline keeps the note the last real fetch wrote,
    because offline knows nothing a fetch knew. That is right for the corpus
    sentence, which counts PDFs that are not in the repository, and wrong for
    every count after it, which comes from the committed cache: those went stale
    the moment a collection restitched the series, and the provenance panel
    printed the stale ones. This rebuilds the second half and leaves the first
    alone.

    A previous note that does not carry the marker is returned untouched. Guessing
    where a sentence ends is not worth a wrong manifest.
    """
    head, marker, _tail = str(previous).partition(_CORPUS_NOTE_END)
    if not marker:
        return str(previous)
    return head + marker + " " + body


class _NoteAdapter(Adapter):
    """Shared plumbing: decode the corpus once, then build one frame from it."""

    #: injected by a test or by main() so the corpus is decoded once per run
    notes: Sequence[NoteDecode] | None = None
    #: where the note PDFs are. NOT named "directory": Adapter.directory() is a
    #: METHOD on the base class, the one that decides between data/cache,
    #: data/seed and data/private, and shadowing it with a path would silently
    #: break every adapter's read and write path.
    note_directory: Path | None = None

    def corpus(self) -> Sequence[NoteDecode]:
        if self.notes is None:
            self.notes = load_corpus(self.note_directory, strict=True)
        return self.notes

    def _vintage(self, notes: Sequence[NoteDecode]) -> str:
        latest = max(n.vintage for n in notes)
        return "latest note prints the week ending %s" % latest


class DgecNotePrintedWeekly(_NoteAdapter):
    """What the ministry PRINTED. Ground truth, and the calibration anchors.

    Eighteen weeks, and that number is the honest one. It is not padded, not
    extended and not interpolated. Every value here is a figure DGEC set in type.
    """

    name = "dgec_note_printed_weekly"
    source = "DGEC, ministere de la Transition ecologique, weekly note, printed table"
    url = "https://www.ecologie.gouv.fr/sites/default/files/documents/"
    page_url = "https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers"
    unit = "USD per tonne, except fioul_lourd_tbts_eur_t which is EUR per tonne"
    frequency = "weekly"
    method = "parsed"
    committable = True
    date_col = "date"
    required_cols = ("date",) + PRINTED_COLUMNS
    observation_column = "brent_date_usd_t"
    bounds = {c: BOUNDS_PRODUCT_USD_T for c in PRINTED_COLUMNS}
    # Floors, per column, from what the corpus actually holds. They are NOT one
    # global number, and the two that are lower than the rest are lower for two
    # different reasons, both of which are facts about the source:
    #
    #   fioul_lourd_tbts_eur_t   the EUR/t row only exists from the December 2025
    #                            layout onward, recon 02 section 3.3, so it is
    #                            printed on ten of the eighteen weeks.
    #   fioul_lourd_tbts_usd_t   wb_NPG-2025.01.17 PRINTS NO FIOUL LOURD ROW AT
    #                            ALL. Recon 02 section 3.3 lists it among the
    #                            notes that print Fioul lourd before Jet; it does
    #                            not print the row. Parsing by label found the
    #                            absence, parsing by position would have read
    #                            Jet's numbers into it.
    min_observations = {
        "eurosuper_usd_t": 18,
        "gazole_usd_t": 18,
        "fioul_domestique_usd_t": 18,
        "jet_usd_t": 18,
        "fioul_lourd_tbts_usd_t": 16,
        "fioul_lourd_tbts_eur_t": 10,
        "brent_date_usd_t": 18,
    }
    min_rows = 18

    @staticmethod
    def _body(frame: pd.DataFrame) -> str:
        """Everything in the note that the committed cache alone decides."""
        single = int((pd.to_numeric(frame["n_notes"], errors="coerce") < 2).sum())
        return (
            "These are the figures printed in the tables, parsed by row and "
            "column label. Two weekly columns per note, some of them reprints of "
            "a week an adjacent note already printed, so %d distinct weeks, of "
            "which %d were printed by one note only and therefore have no "
            "max_disagreement_usd_t. Jet and Fioul lourd appear HERE and in "
            "dgec_note_printed_monthly and nowhere else: they are not on the "
            "page 3 chart and therefore have no weekly reconstruction. %s"
            % (len(frame), single, UNDEFINED_SPREAD)
        )

    def fetch(self) -> pd.DataFrame:
        notes = self.corpus()
        self.vintage = self._vintage(notes)
        frame = build_printed_weekly(notes)
        self.note = _CORPUS_NOTE % len(notes) + " " + self._body(frame)
        return frame

    def offline_note(self, note: str, frame: pd.DataFrame) -> str:
        return _restate_note(note, self._body(frame))


class DgecNotePrintedMonthly(_NoteAdapter):
    """The MONTHLY columns of the same printed table, with their vintages.

    SPEC.md section 2 rule 5 in full: provisional is labelled provisional, every
    vintage is kept and the flag is shown. This series exists because the note
    decoder had been reading the monthly columns and their provisional markers
    correctly on every run and then discarding them, which the Gate 1 self audit
    found and called finding 1.1.

    It is small, 7 months, and it is the only monthly record of these six
    quotations anywhere: DGEC publishes a monthly Brent workbook and a monthly
    MBR workbook and no monthly product history at all.
    """

    name = "dgec_note_printed_monthly"
    source = (
        "DGEC, ministere de la Transition ecologique, weekly note, printed table, "
        "monthly columns"
    )
    url = "https://www.ecologie.gouv.fr/sites/default/files/documents/"
    page_url = "https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers"
    unit = "USD per tonne, except fioul_lourd_tbts_eur_t which is EUR per tonne"
    frequency = "monthly"
    method = "parsed"
    committable = True
    date_col = "date"
    required_cols = ("date",) + PRINTED_COLUMNS + ("provisional", "vintage")
    observation_column = "brent_date_usd_t"
    bounds = {c: BOUNDS_PRODUCT_USD_T for c in PRINTED_COLUMNS}
    # Every month printed in the six column layout prints all seven rows, so the
    # floors are the row count. They are floors, not expectations: the series
    # grows by two months every time a note is collected in a new month.
    min_observations = {c: 7 for c in PRINTED_COLUMNS}
    min_rows = 7

    def fetch(self) -> pd.DataFrame:
        notes = self.corpus()
        self.vintage = self._vintage(notes)
        frame = build_printed_monthly(notes)

        # A REAL provisional_from, derived from the flags DGEC itself printed
        # rather than declared. It is the earliest month in this file that is
        # still carrying the ministry's "(donnees provisoires)" marker. The flags
        # are NOT contiguous, because a month goes final while a later one is
        # still provisional, so the per row provisional column is the
        # authoritative one and this field is the range bound SPEC.md section 5.3
        # asks for.
        provisional = frame.loc[frame["provisional"].astype(bool), "date"]
        self.provisional_from = (
            pd.Timestamp(provisional.min()).strftime("%Y-%m-%d")
            if len(provisional)
            else None
        )

        still_provisional = [
            pd.Timestamp(d).strftime("%Y-%m") for d in sorted(provisional)
        ]
        revised = frame[frame["revised"].astype(bool)]
        self.note = (
            _CORPUS_NOTE % len(notes)
            + " THE MONTHLY COLUMNS OF THE PRINTED QUOTATION TABLE, WITH THE "
            "MINISTRY'S OWN PROVISIONAL MARKER CARRIED PER ROW. SPEC.md section "
            "2 rule 5. The six column layout that prints monthly averages first "
            "appears in the December 2025 note, recon 02 section 3.3, so this "
            "series is %d months from %d of the %d preserved notes and there is "
            "no earlier monthly product history to be had: DGEC publishes "
            "monthly workbooks for Brent and for the MBR and none for the "
            "products. %d month(s) are still flagged provisional by the "
            "ministry, %s, and the flag is per row because a month goes final "
            "while a later one is still provisional. %d month(s) have been "
            "revised since their first print and revision_history carries every "
            "vintage of every month with its flag and its seven values, so the "
            "revision is readable out of this file and not only out of the PDFs. "
            "The two that matter: March 2026 was printed provisional at 946 $/t "
            "Eurosuper on 20 March and 976 on 27 March, then FINAL at 988 on 3 "
            "April, and April 2026 moved from 1,431 $/t Gazole to 1,288 between "
            "two PROVISIONAL prints three weeks apart, a 143 $/t revision. "
            "max_revision_usd_t is NaN where a month has been printed once, "
            "because a revision over one print is undefined rather than zero. "
            "THIS IS THE ONLY MONTHLY SERIES IN THE PROJECT CARRYING JET AND "
            "FIOUL LOURD TBTS AS DGEC $/t QUOTATIONS: neither is plotted on the "
            "page 3 chart, so neither has a weekly reconstruction, and DGEC "
            "publishes no monthly product workbook. The neighbours are not "
            "substitutes and are named rather than ignored: "
            "opec_rotterdam_products_monthly carries Argus assessments of jet and "
            "of 1 percent fuel oil at the same hub, on a different specification "
            "and in $/bbl, and jodi_nwe_refinery_output_monthly carries jetkero "
            "volumes, which are not a price. The gaps are real: the notes print "
            "no monthly column for a month no preserved note happened to cover."
            % (
                len(frame),
                int(sum(1 for n in notes if n.printed_monthly)),
                len(notes),
                len(still_provisional),
                ", ".join(still_provisional) or "none",
                len(revised),
            )
        )
        return frame


class DgecNoteReconstructedWeekly(_NoteAdapter):
    """The page 3 curves, decoded. THIS IS NOT A DGEC PUBLICATION.

    It is this study's reconstruction of a chart DGEC drew from its own data, and
    it is labelled as one everywhere. Read RECONSTRUCTION_ERROR, BRENT_IS_WORST
    and DEGENERATE_PAIR before using it, and read the module docstring before
    putting it on a page.
    """

    name = "dgec_note_reconstructed_weekly"
    source = (
        "DGEC, ministere de la Transition ecologique, weekly note, page 3 chart, "
        "decoded by this study"
    )
    url = "https://www.ecologie.gouv.fr/sites/default/files/documents/"
    page_url = "https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers"
    unit = "USD per tonne"
    frequency = "weekly"
    # NOT "parsed". A number recovered from the geometry of a curve is not the
    # same kind of object as a number a ministry printed, and SPEC.md section 2
    # rule 1 means the difference is declared where the data is.
    method = "reconstructed"
    committable = True
    date_col = "date"
    required_cols = ("date",) + CHART_COLUMNS
    observation_column = "gazole_usd_t"
    bounds = {c: BOUNDS_PRODUCT_USD_T for c in CHART_COLUMNS}
    min_observations = {c: 200 for c in CHART_COLUMNS}
    min_rows = 200

    @staticmethod
    def _body(frame: pd.DataFrame) -> str:
        """Everything in the note that the committed cache alone decides.

        EVERY COUNT IN HERE IS COUNTED, none is typed, because a collection moves
        all of them at once: see COLLECTION_RESTITCHES_HISTORY. Before this was
        so, the provenance panel published "19 newest single geometry weeks" and
        "194 of 219 weeks" for a fortnight after the collection that made them 1
        and 214.
        """
        single = int((~frame["cross_checked"].astype(bool)).sum())
        checked = len(frame) - single
        newest = frame[frame["evidence_class"] == "single_geometry_newest"]
        oldest = frame[frame["evidence_class"] == "single_geometry_oldest"]
        if len(oldest):
            oldest_range = "%s to %s" % (
                pd.Timestamp(oldest["date"].min()).strftime("%Y-%m-%d"),
                pd.Timestamp(oldest["date"].max()).strftime("%Y-%m-%d"),
            )
        else:
            oldest_range = "none"
        return (
            "RECONSTRUCTED FROM THE VECTOR POLYLINE ON PAGE 3 OF THE DGEC "
            "WEEKLY NOTE, CALIBRATED AGAINST THE PRINTED WEEKLY AVERAGES ON THE "
            "SAME PAGE. Measured error, recon 05 sections 11 and 12: %.2f to "
            "%.2f $/t mean absolute out of sample by leave one series out, worst "
            "single anchor %.2f $/t, mean absolute agreement between overlapping "
            "notes %.2f $/t, worst single week %.2f $/t. %s %d of the %d weeks "
            "are read from two or more independent chart geometries; the other "
            "%d are covered by a single geometry and therefore have NO cross "
            "check, flagged as cross_checked false, and evidence_class splits "
            "them by kind: %d of them, %s, are marked single_geometry_oldest and "
            "%d are the newest weeks, which the next collection will usually "
            "cross check. %s %s %s %s %s %s %s %s Jet and Fioul lourd are NOT "
            "plotted on this chart and are deliberately absent: reconstructing "
            "them would be a synthetic series."
            % (
                RECONSTRUCTION_ERROR["out_of_sample_mae_usd_t"][0],
                RECONSTRUCTION_ERROR["out_of_sample_mae_usd_t"][1],
                RECONSTRUCTION_ERROR["out_of_sample_worst_usd_t"],
                RECONSTRUCTION_ERROR["note_pair_mean_absolute_usd_t"],
                RECONSTRUCTION_ERROR["note_pair_worst_week_usd_t"],
                ERROR_BAR_AXIS,
                checked,
                len(frame),
                single,
                len(oldest),
                oldest_range,
                len(newest),
                OLDEST_WEEKS_ARE_WEAK_TWICE,
                COLLECTION_RESTITCHES_HISTORY["what"],
                COLLECTION_RESTITCHES_HISTORY["direction"],
                SMOOTH_TILT_IS_INVISIBLE,
                PIXEL_QUANTISATION,
                UNDEFINED_SPREAD,
                BRENT_IS_WORST,
                DEGENERATE_PAIR,
            )
        )

    def fetch(self) -> pd.DataFrame:
        notes = self.corpus()
        self.vintage = self._vintage(notes)
        frame = build_reconstructed_weekly(notes)
        self.note = _CORPUS_NOTE % len(notes) + " " + self._body(frame)
        return frame

    def offline_note(self, note: str, frame: pd.DataFrame) -> str:
        return _restate_note(note, self._body(frame))

    def _entry(self, **kwargs) -> dict:
        entry = super()._entry(**kwargs)
        # The measured error travels IN THE MANIFEST, not only in prose. Recon 05
        # section 14 condition 3.
        entry["reconstruction"] = {
            "method": (
                "reconstructed from the vector polyline on page 3 of the DGEC "
                "weekly note, calibrated against the printed weekly averages on "
                "the same page"
            ),
            "calibration": (
                "one additive offset per note, fitted by least squares on that "
                "note's own eight printed anchors, four plotted series times the "
                "two printed weeks. The offset runs -2.38 to +2.82 $/t across the "
                "corpus and changes sign between notes, so it can never be a "
                "constant"
            ),
            "error_usd_t": dict(RECONSTRUCTION_ERROR),
            # WHAT THE ERROR BAR DOES NOT COVER, in the manifest rather than only
            # in docs/methodology.md, because the manifest is what the provenance
            # panel renders next to the number.
            "error_bar_axis": ERROR_BAR_AXIS,
            "gates_are_blind_to": SMOOTH_TILT_IS_INVISIBLE,
            "least_defended_weeks": OLDEST_WEEKS_ARE_WEAK_TWICE,
            "quantisation": PIXEL_QUANTISATION,
            "undefined_spread": UNDEFINED_SPREAD,
            "evidence_classes": list(EVIDENCE_CLASSES),
            "least_accurate_series": BRENT_IS_WORST,
            "degeneracy": DEGENERATE_PAIR,
            "not_reconstructed": (
                "Jet and Fioul lourd TBTS are not plotted on the chart and are "
                "therefore absent from this series. They exist only in "
                "dgec_note_printed_weekly, whose row count that entry carries"
            ),
            # What a collection does to the weeks already published. Measured
            # across two vintages of this cache, which one vintage cannot show.
            "restitching": dict(COLLECTION_RESTITCHES_HISTORY),
            "gates": {k: v for k, v in GATES.items()},
        }
        return entry


class DgecNoteReconstructedCracksWeekly(_NoteAdapter):
    """Weekly cracks computed from the reconstructed layer. SPEC.md section 4.2.

    Derived, not observed. It inherits every limitation of the series underneath
    it, and the manifest says so.
    """

    name = "dgec_note_reconstructed_cracks_weekly"
    source = "computed by this study from dgec_note_reconstructed_weekly"
    url = ""
    page_url = "https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers"
    unit = "USD per barrel"
    frequency = "weekly"
    method = "derived"
    committable = True
    date_col = "date"
    required_cols = ("date", "crack_gasoil_usd_bbl", "crack_gasoline_usd_bbl")
    observation_column = "crack_gasoil_usd_bbl"
    bounds = {
        "crack_gasoil_usd_bbl": BOUNDS_CRACK_USD_BBL,
        "crack_gasoline_usd_bbl": BOUNDS_CRACK_USD_BBL,
        "crack_fioul_domestique_usd_bbl": BOUNDS_CRACK_USD_BBL,
    }
    min_observations = {
        "crack_gasoil_usd_bbl": 200,
        "crack_gasoline_usd_bbl": 200,
        "crack_fioul_domestique_usd_bbl": 200,
    }
    min_rows = 200

    def fetch(self) -> pd.DataFrame:
        notes = self.corpus()
        self.vintage = self._vintage(notes)
        frame = weekly_cracks(build_reconstructed_weekly(notes))
        self.note = (
            "crack = product $/t divided by the ICE contract factor, minus Brent "
            "date $/t divided by %g, SPEC.md section 4.2 with "
            "config.DGEC_BBL_PER_T_BRENT_NOTE. Both legs come from the same chart "
            "on the same page of the same note, so they share a date and an "
            "averaging window. EVERY VALUE HERE INHERITS THE RECONSTRUCTION: see "
            "dgec_note_reconstructed_weekly, whose measured error is 0.17 to 0.44 "
            "$/t, about 0.02 to 0.06 $/bbl on gasoil. %s The gasoline crack "
            "disagrees with the OPEC Rotterdam premium gasoline 98 crack by up to "
            "13 $/bbl because the two sources quote different products and imply "
            "6.937 to 8.333 barrels per tonne, mean 7.7185, over the 44 months "
            "2022-07 to 2026-02 where both exist, rather than the contract's "
            "8.33. That gap is reported, not tuned away. The provenance columns "
            "of dgec_note_reconstructed_weekly travel with every row here, "
            "evidence_class included."
            % (DGEC_BBL_PER_T_BRENT_NOTE, ERROR_BAR_AXIS)
        )
        return frame


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

# The licence note is the registry's, set once here rather than retyped, so the
# provenance panel prints the same words the registry holds. The reconstruction
# adds a sentence of its own, because a reconstruction is not a DGEC publication
# and the licence note is where a reader is told so.
DgecNotePrintedWeekly.licence_note = SOURCES["dgec_note_printed_weekly"].licence_note
DgecNotePrintedMonthly.licence_note = SOURCES["dgec_note_printed_monthly"].licence_note
DgecNoteReconstructedWeekly.licence_note = SOURCES[
    "dgec_note_reconstructed_weekly"
].licence_note
DgecNoteReconstructedCracksWeekly.licence_note = SOURCES[
    "dgec_note_reconstructed_cracks_weekly"
].licence_note


def _report(entry: Mapping[str, Any]) -> None:
    print(
        "%-40s %-8s rows=%-5s %s to %s  gaps=%d"
        % (
            entry.get("series"),
            entry.get("status"),
            entry.get("observations"),
            entry.get("first_date"),
            entry.get("last_date"),
            len(entry.get("gaps") or []),
        )
    )


def main(argv: Iterable[str] | None = None) -> int:
    """Build the weekly crack layer. Exits non zero on any failure."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--directory",
        default=None,
        help="where the note PDFs are, default data/private/dgec_notes",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="print the per note decode diagnostics and build nothing",
    )
    parser.add_argument(
        "--collect",
        action="store_true",
        help=(
            "fetch the one note that is online first, two requests. Run this "
            "weekly: the ministry deletes each note when the next appears"
        ),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    directory = Path(args.directory) if args.directory else None

    if args.collect:
        try:
            path, downloaded = collect_current_note(directory)
        except Exception as exc:  # noqa: BLE001
            print("COLLECTION FAILED: %s" % exc, file=sys.stderr)
            return 1
        print(
            "%s %s" % ("collected" if downloaded else "already held", path.name)
        )

    try:
        notes = load_corpus(directory, strict=True)
    except NoteDecodeError as exc:
        print("FAILED: %s" % exc, file=sys.stderr)
        return 1

    if args.diagnostics:
        import json

        for note in notes:
            print(json.dumps({"file": note.file, **note.diagnostics}, default=str))
        return 0

    status = 0
    for adapter_class in (
        DgecNotePrintedWeekly,
        DgecNotePrintedMonthly,
        DgecNoteReconstructedWeekly,
        DgecNoteReconstructedCracksWeekly,
    ):
        adapter = adapter_class()
        adapter.notes = notes
        adapter.note_directory = directory
        try:
            _report(adapter.run())
        except Exception as exc:  # noqa: BLE001
            print("FAILED %s: %s" % (adapter_class.name, exc), file=sys.stderr)
            status = 1
    return status


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
