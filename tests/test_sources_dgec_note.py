"""The weekly crack layer: the printed table, the decoded chart, and the gates.

This file is the test recon 05 section 15 says was needed and had never been
built: "one test per note per product, 80 assertions". It is that, and five other
things.

WHAT IS ASSERTED HERE, AND WHY EACH ONE EARNS ITS PLACE
--------------------------------------------------------
1. Every one of the ten preserved notes decodes, and the page is found by title
   rather than by index, because in one of the ten the table is on page 4.
2. THE ANCHORS. For every note and every one of the four plotted products, the
   calibrated chart value on the two weeks that note PRINTS is compared against
   the printed figure. Ten notes times four products times two weeks is eighty
   assertions, and they are the whole reason the reconstruction is checkable at
   all.
3. The printed values reproduce recon 02 sections 3.2 and 4.4 verbatim, so a
   future edit to the table parser that silently swaps two rows fails here.
4. THE LINE NOT TO CROSS. Jet and Fioul lourd are printed and are NOT
   reconstructed, and a test says so, because the pressure to fill them in by
   regression on the three products that are plotted will exist as soon as
   someone wants a jet crack.
5. The six conditions of recon 05 section 14, each as its own test: the separate
   series, the error in the data, the 25 weeks with no cross check, Brent flagged
   as the worst, the axis degeneracy, and the gates.
6. The two external cross checks, against the OPEC monthly Rotterdam table over
   the 44 month overlap and against the October 2022 week that SPEC.md section 3
   names.

The note PDFs are not committed, so on a fresh checkout everything that needs
them skips rather than failing. The skip message says exactly what is missing.
"""

from __future__ import annotations

import statistics
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from crack import config
from crack.sources import base, dgec_note
from crack.sources.dgec_note import (
    CHART_COLUMNS,
    EVIDENCE_CLASSES,
    GATES,
    PRINTED_COLUMNS,
    PRINTED_MONTHLY_COLUMNS,
    DgecNotePrintedMonthly,
    DgecNotePrintedWeekly,
    DgecNoteReconstructedCracksWeekly,
    DgecNoteReconstructedWeekly,
    NoteDecodeError,
    build_printed_monthly,
    build_printed_weekly,
    build_reconstructed_weekly,
    parse_fr_date,
    parse_fr_month,
    weekly_cracks,
)

pytest.importorskip("pdfplumber", reason="the note decoder needs pdfplumber")

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = REPO_ROOT / "data" / "cache"


# ==========================================================================
# The corpus, decoded once
# ==========================================================================

def _paths() -> list[Path]:
    return dgec_note.note_paths()


@pytest.fixture(scope="module")
def corpus():
    """Every note, decoded once for the whole module. About four seconds."""
    paths = _paths()
    if not paths:
        pytest.skip(
            "no weekly note PDF under %s. The ten notes are irreplaceable, are "
            "not committed because they are the ministry's own documents, and "
            "cannot be downloaded again: DGEC publishes one note at a time and "
            "deletes the previous one. Everything in this file that reads them "
            "skips on a fresh checkout." % dgec_note.NOTE_DIR
        )
    return {n.file: n for n in dgec_note.load_corpus(strict=True)}


NOTE_FILES = sorted(p.name for p in _paths())

#: The ten notes recon 05 measured. The corpus GROWS by one note a week, and
#: every note collected after these ten changes the stitched series: one more
#: Friday, one more printed week, one more single geometry week at the newest
#: end. So the tests split in two, on purpose:
#:   * a test that reproduces a recon 05 MEASUREMENT (168 note pair comparisons,
#:     the 219 row demonstration output, the 25, 7 and 187 coverage table) runs
#:     on these ten notes only, because that measurement was made on them and a
#:     later note cannot make it truer or falser;
#:   * a test about the LIVE series (its length, its last Friday, how many of
#:     its newest weeks lack a second chart) reads its expectation from the
#:     corpus that is present, the latest vintage and the calendar, and never
#:     from a literal that the next note would make wrong.
RECON_05_NOTES = frozenset({
    "wb_NPG-2024.06.21.pdf",
    "wb_NPG-2024.07.12.pdf",
    "wb_NPG-2024.08.30.pdf",
    "wb_NPG-2025.01.17.pdf",
    "wb_NPG-2025.12.19.pdf",
    "wb_NPG-2026.03.20.pdf",
    "wb_NPG-2026.03.27.pdf",
    "wb_NPG-2026.04.03.pdf",
    "wb_NPG-2026.04.17.pdf",
    "NPG-2026.09.04.pdf",
})

#: The first Friday the chart reaches, and the first week of the newest run of
#: single geometry weeks. Both are facts of the notes actually collected: the
#: oldest chart starts on 2022-07-01, and the last note whose chart covers an
#: earlier week is the newest one held, so the run of single geometry weeks is
#: whatever the newest note does not reach back over.
#:
#: This constant MOVES every time a note is collected, and the two tests below
#: are built to fail when it does, which is the point: they report that a new
#: chart has given earlier weeks a second reading.
#:
#: 2026-05-01, when wb_NPG-2026.04.03 was the newest chart, 21 weeks stood on one
#:             geometry and 194 were cross checked.
#: 2026-09-18, after NPG-2026.09.11 and NPG-2026.09.18 were collected. Each note
#:             plots about 105 weeks, so the September charts reach back over
#:             every week of that run: 20 of those 21 weeks gained a second
#:             reading, 214 weeks are now cross checked, and only the newest
#:             week itself stands alone. The restitched median moved 104
#:             historical weeks by at most 0.39 $/t on a price column, inside
#:             the reconstruction's own measured error.
FIRST_FRIDAY = pd.Timestamp("2022-07-01")
NEWEST_RUN_START = pd.Timestamp("2026-09-18")


def _fridays(first: pd.Timestamp, last: pd.Timestamp) -> int:
    """How many Fridays from first to last inclusive, both Fridays."""
    return int((last - first).days // 7) + 1


@pytest.fixture(scope="module")
def recon_corpus(corpus):
    """The ten notes recon 05 measured, and nothing collected since."""
    missing = sorted(RECON_05_NOTES - set(corpus))
    if missing:
        pytest.skip("recon 05's notes are not all present: %s" % ", ".join(missing))
    return {name: note for name, note in corpus.items() if name in RECON_05_NOTES}


@pytest.fixture(scope="module")
def latest_vintage(corpus):
    """The newest note's printed date, the last Friday the series can reach."""
    return pd.Timestamp(max(note.vintage for note in corpus.values()))

#: Ten notes when the corpus is present, so the per note parametrisations below
#: produce ten cases each. Empty on a fresh checkout, where a parametrised test
#: with an empty argument list is collected as a single skip.
_PARAMS = NOTE_FILES or ["<no note PDF present>"]


# ==========================================================================
# Date parsing
# ==========================================================================

def test_french_short_dates_parse_in_every_spelling_the_notes_use():
    assert parse_fr_date("4-sept.-26") == date(2026, 9, 4)
    assert parse_fr_date("28-août-26") == date(2026, 8, 28)
    assert parse_fr_date("28-aout-26") == date(2026, 8, 28)
    assert parse_fr_date("21-juin-24") == date(2024, 6, 21)
    assert parse_fr_date("19-déc.-25") == date(2025, 12, 19)
    # A monthly column header is not a weekly one. Telling them apart is what
    # stops a monthly average being written into the weekly series.
    assert parse_fr_date("sept.-26") is None
    assert parse_fr_month("sept.-26") == (2026, 9)
    assert parse_fr_month("4-sept.-26") is None
    assert parse_fr_date("variation") is None
    assert parse_fr_date("31-brumaire-26") is None


# ==========================================================================
# Every note decodes
# ==========================================================================

@pytest.mark.parametrize("file_name", _PARAMS)
def test_every_note_decodes_and_passes_every_gate(corpus, file_name):
    """Ten for ten. A gate firing here means a layout changed, not a flaky test."""
    note = corpus[file_name]
    d = note.diagnostics
    assert d["n_points"] >= GATES["min_points"]
    assert len(note.chart) == GATES["chart_series"]
    assert d["n_y_ticks"] >= GATES["min_y_ticks"]
    assert d["max_tick_residual_usd_t"] <= GATES["max_tick_residual_usd_t"]
    assert d["anchor_worst_usd_t"] <= GATES["max_anchor_residual_usd_t"]
    low, high = GATES["weeks_per_point"]
    assert low <= d["weeks_per_point"] <= high


def test_the_page_is_found_by_title_not_by_index(corpus):
    """One of the ten notes carries the table on page 4, not page 3.

    Recon 02 section 3.1. An adapter that indexed page 3 would read the wrong
    page of NPG-2024.07.12 and would find no chart at all, and the title wording
    itself changed between the 2024 and the 2026 notes, from "Cours hebdomadaire
    du Brent date ..." to "Cours du Brent date ...", so the title match has to be
    on the fragments common to both.
    """
    pages = {name: note.page for name, note in corpus.items()}
    assert pages["wb_NPG-2024.07.12.pdf"] == 4
    assert set(pages.values()) == {3, 4}


def test_the_vintage_is_the_printed_date_not_the_file_name(corpus):
    """Four of the ten notes carry a content date later than their file name.

    Recon 02 section 2.4: the ministry sometimes replaces the CONTENTS of an
    existing URL with the following week's note rather than uploading a new file,
    so the file name is not evidence of anything. wb_NPG-2026.04.17 is the worst,
    one week out, and wb_NPG-2024.07.12 is four weeks out.
    """
    expected = {
        "wb_NPG-2024.06.21.pdf": date(2024, 6, 28),
        "wb_NPG-2024.07.12.pdf": date(2024, 8, 9),
        "wb_NPG-2024.08.30.pdf": date(2024, 9, 6),
        "wb_NPG-2025.01.17.pdf": date(2025, 1, 17),
        "wb_NPG-2025.12.19.pdf": date(2025, 12, 19),
        "wb_NPG-2026.03.20.pdf": date(2026, 3, 20),
        "wb_NPG-2026.03.27.pdf": date(2026, 3, 27),
        "wb_NPG-2026.04.03.pdf": date(2026, 4, 3),
        "wb_NPG-2026.04.17.pdf": date(2026, 4, 24),
        "NPG-2026.09.04.pdf": date(2026, 9, 4),
        "NPG-2026.09.11.pdf": date(2026, 9, 11),
    }
    for name, note in corpus.items():
        # A note collected after this table was written is checked by its file
        # name, which for a note collected in its own week is its printed date;
        # the table holds the ones where the two were measured to differ.
        if name not in expected:
            stamp = name.replace("wb_", "").replace("NPG-", "").replace(".pdf", "")
            want = date(*(int(part) for part in stamp.split(".")))
            assert note.vintage == want, (
                "%s prints %s, not the date in its name. Add it to the table above "
                "with the printed date, as recon 02 section 2.4 did for four notes"
                % (name, note.vintage)
            )
        else:
            assert note.vintage == expected[name], name
        assert note.vintage.weekday() == 4, "%s is not dated a Friday" % name


# ==========================================================================
# THE ANCHORS. Ten notes, four plotted products, two printed weeks each.
# ==========================================================================

@pytest.mark.parametrize("file_name", _PARAMS)
@pytest.mark.parametrize("column", CHART_COLUMNS)
def test_chart_anchor_against_the_printed_value(corpus, file_name, column):
    """The decoded curve, on the two weeks the same page PRINTS.

    This is the test recon 05 section 15 says was needed and was never built.
    Forty cases, eighty assertions, one per note per product per printed week.

    The tolerance is the gate, 1.5 $/t, which is what recon 05 section 14
    condition 6 names. The worst anchor in the whole corpus today is 0.738 $/t,
    so this has room, and it is a CEILING on how wrong a value may be, not a
    target to tune toward: SPEC.md section 6.6 forbids adjusting the parser to
    hit a number.
    """
    note = corpus[file_name]
    printed_weeks = sorted(note.printed_weekly)
    assert len(printed_weeks) == 2
    for week in printed_weeks:
        printed = note.printed_weekly[week].get(column)
        assert printed is not None, "%s prints no %s for %s" % (file_name, column, week)
        decoded = note.chart[column][week]
        assert abs(decoded - printed) <= GATES["max_anchor_residual_usd_t"], (
            "%s %s on %s: decoded %.2f against a printed %.0f, %.3f $/t out, the "
            "limit is %.2f"
            % (file_name, column, week, decoded, printed, abs(decoded - printed),
               GATES["max_anchor_residual_usd_t"])
        )


@pytest.mark.parametrize("file_name", _PARAMS)
def test_leave_one_series_out_error_is_within_what_recon_05_measured(corpus, file_name):
    """The honest, out of sample figure: 0.17 to 0.44 $/t, worst 0.87.

    The anchor test above is IN SAMPLE, because the offset it checks was fitted
    on those same eight points. This is the out of sample version: the offset is
    refitted on three products' six anchors and used to predict the fourth
    product's two. Recon 05 section 11 measured 0.17 to 0.44 $/t mean absolute
    and 0.87 $/t worst across the corpus, and RECONSTRUCTION_ERROR carries those
    numbers into the manifest and onto the Method view.
    """
    d = corpus[file_name].diagnostics
    low, high = dgec_note.RECONSTRUCTION_ERROR["out_of_sample_mae_usd_t"]
    worst = dgec_note.RECONSTRUCTION_ERROR["out_of_sample_worst_usd_t"]
    assert d["leave_one_series_out_mae_usd_t"] is not None
    assert low - 0.01 <= d["leave_one_series_out_mae_usd_t"] <= high + 0.01, (
        "%s out of sample MAE is %.3f $/t, outside the %.2f to %.2f band recon 05 "
        "section 11 measured. Report the new number, do not widen the band "
        "quietly" % (file_name, d["leave_one_series_out_mae_usd_t"], low, high)
    )
    assert d["leave_one_series_out_worst_usd_t"] <= worst + 0.01


def test_the_per_note_offset_changes_sign_so_it_can_never_be_a_constant(corpus):
    """Recon 05 section 11, and the reason calibration is per note.

    The bias between a tick label's glyph box centre and its visual centre runs
    -2.38 to +2.82 $/t across the ten notes and CHANGES SIGN. Recon 02 spot
    checked one note and saw about -2.7; that figure is right for that note and
    wrong as a constant. If this test ever fails because every offset has the
    same sign, the fitting is still correct and the comment is what needs
    changing.
    """
    offsets = [n.diagnostics["offset_usd_t"] for n in corpus.values()]
    assert min(offsets) < 0 < max(offsets)
    assert -3.0 < min(offsets) and max(offsets) < 3.5


# ==========================================================================
# The printed table, verbatim against recon 02
# ==========================================================================

#: Verbatim from recon 02 section 3.2, the full printed weekly column of the
#: reference note, and from section 4.4, the values hand read out of the others.
#: These are transcriptions of what is set in type on the page. If the parser
#: ever disagrees with one of them, the parser is wrong until proved otherwise,
#: and it is NOT adjusted to hit the number: the disagreement gets reported.
PRINTED_ANCHORS = {
    (date(2026, 9, 4)): {
        "eurosuper_usd_t": 1349,
        "gazole_usd_t": 1394,
        "fioul_domestique_usd_t": 1359,
        "jet_usd_t": 1430,
        "fioul_lourd_tbts_usd_t": 548,
        "fioul_lourd_tbts_eur_t": 472,
        "brent_date_usd_t": 720,
    },
    (date(2026, 8, 28)): {
        "eurosuper_usd_t": 1201,
        "gazole_usd_t": 1249,
        "fioul_domestique_usd_t": 1218,
        "jet_usd_t": 1278,
        "fioul_lourd_tbts_usd_t": 533,
        "fioul_lourd_tbts_eur_t": 457,
        "brent_date_usd_t": 684,
    },
    (date(2024, 6, 28)): {
        "eurosuper_usd_t": 877,
        "fioul_domestique_usd_t": 803,
        "jet_usd_t": 840,
        "fioul_lourd_tbts_usd_t": 514,
        "brent_date_usd_t": 651,
    },
    (date(2024, 9, 6)): {
        "eurosuper_usd_t": 740,
        "fioul_domestique_usd_t": 664,
        "jet_usd_t": 720,
        "fioul_lourd_tbts_usd_t": 474,
        "brent_date_usd_t": 575,
    },
    (date(2025, 1, 17)): {
        "eurosuper_usd_t": 766,
        "gazole_usd_t": 764,
        "brent_date_usd_t": 616,
    },
    (date(2025, 12, 19)): {
        "eurosuper_usd_t": 646,
        "gazole_usd_t": 632,
        "fioul_domestique_usd_t": 615,
        "jet_usd_t": 690,
        "fioul_lourd_tbts_usd_t": 371,
        "brent_date_usd_t": 457,
    },
    (date(2026, 4, 3)): {
        "eurosuper_usd_t": 1099,
        "gazole_usd_t": 1415,
        "fioul_domestique_usd_t": 1391,
        "jet_usd_t": 1669,
        "fioul_lourd_tbts_usd_t": 647,
        "brent_date_usd_t": 926,
    },
}


def test_printed_weekly_reproduces_every_value_recon_02_read_by_hand(corpus):
    frame = build_printed_weekly(list(corpus.values())).set_index("date")
    for when, expected in PRINTED_ANCHORS.items():
        stamp = pd.Timestamp(when)
        assert stamp in frame.index, "%s is missing from the printed series" % when
        for column, value in expected.items():
            got = frame.loc[stamp, column]
            assert got == pytest.approx(float(value)), (
                "printed %s on %s: parsed %r, recon 02 read %d off the page"
                % (column, when, got, value)
            )


def test_the_printed_series_is_eighteen_weeks_and_says_so(recon_corpus):
    """Twenty printed columns, three of them reprints, so eighteen weeks.

    That was the entire published weekly record in the ten notes recon 05 read,
    and it is the honest number. The reconstruction exists because eighteen
    observations is not a series. Pinned to those ten notes: each note collected
    since prints two more weeks, one of them a reprint.
    """
    frame = build_printed_weekly(list(recon_corpus.values()))
    assert len(frame) == 18
    assert frame["date"].min() == pd.Timestamp("2024-06-21")
    assert frame["date"].max() == pd.Timestamp("2026-09-04")
    assert frame["date"].is_monotonic_increasing
    assert not frame["date"].duplicated().any()
    assert set(frame.loc[frame["n_notes"] > 1, "date"]) == {
        pd.Timestamp("2026-03-20"),
        pd.Timestamp("2026-03-27"),
    }


def test_the_printed_series_grows_by_the_notes_collected_since(corpus, recon_corpus, latest_vintage):
    """Every note prints its own week and the week before. A note collected in
    the week after the last one reprints one week and adds one, so the printed
    record ends on the latest note's date and never skips a note's own week."""
    frame = build_printed_weekly(list(corpus.values()))
    assert frame["date"].max() == latest_vintage
    assert frame["date"].is_monotonic_increasing
    assert not frame["date"].duplicated().any()
    printed = set(frame["date"])
    for note in corpus.values():
        assert pd.Timestamp(note.vintage) in printed, note.file
    assert len(frame) >= len(build_printed_weekly(list(recon_corpus.values())))


def test_where_two_notes_print_the_same_week_they_agree(corpus):
    """A free revision check, and it passes: no reprint moved by a dollar.

    Adjacent notes overlap on one printed week each. A disagreement would be a
    fact about the source worth reporting, not noise to average away, which is
    why max_disagreement_usd_t is a column rather than a silent mean.

    ONLY THE WEEKS THAT WERE ACTUALLY PRINTED TWICE CARRY A NUMBER. The others
    carry NaN, because a disagreement between one reading and nothing is
    undefined and a 0 there would have said the notes agreed. Gate 1 self audit,
    finding e.1. The counts are read from the corpus present, because each note
    collected turns one single print into a reprint.
    """
    frame = build_printed_weekly(list(corpus.values()))
    compared = frame[frame["n_notes"] > 1]
    assert len(compared) >= 2
    assert compared["max_disagreement_usd_t"].notna().all()
    assert compared["max_disagreement_usd_t"].max() == 0.0
    alone = frame[frame["n_notes"] == 1]
    assert len(alone) + len(compared) == len(frame)
    assert alone["max_disagreement_usd_t"].isna().all(), (
        "a week printed by one note carries a disagreement of %r. A spread over "
        "one reading is undefined, not zero"
        % alone["max_disagreement_usd_t"].tolist()
    )


def test_one_note_prints_no_fioul_lourd_row_at_all(corpus):
    """wb_NPG-2025.01.17 omits it, and parsing by label is what found that.

    Recon 02 section 3.3 lists that note among the ones printing Fioul lourd
    before Jet. It does not print the row: its table is Eurosuper, Gazole, Fioul
    domestique, Jet, Brent date and nothing else. A positional parser would have
    read Jet's numbers into the fioul lourd column and nobody would have seen it.
    This is why the declared observation floor for that column is 16 and not 18.
    """
    note = corpus["wb_NPG-2025.01.17.pdf"]
    for values in note.printed_weekly.values():
        assert "fioul_lourd_tbts_usd_t" not in values
        assert "jet_usd_t" in values
    frame = build_printed_weekly(list(corpus.values()))
    missing = frame.loc[frame["fioul_lourd_tbts_usd_t"].isna(), "date"]
    assert set(missing) == {pd.Timestamp("2025-01-10"), pd.Timestamp("2025-01-17")}


def test_the_row_order_break_does_not_swap_jet_and_fioul_lourd(corpus):
    """Recon 02 section 3.3 break (b), the SPEC.md section 13 failure mode.

    2024 notes print Fioul lourd before Jet, December 2025 onward print Jet
    first. Jet is always the more expensive of the two by a wide margin, so a
    swap would be visible as an inversion. It is not there on either side of the
    break.
    """
    for name in ("wb_NPG-2024.06.21.pdf", "NPG-2026.09.04.pdf"):
        for values in corpus[name].printed_weekly.values():
            assert values["jet_usd_t"] > values["fioul_lourd_tbts_usd_t"]


def test_the_monthly_columns_appear_only_in_the_later_layout(corpus):
    """Recon 02 section 3.3 break (a), and the reason there is a monthly series.

    The monthly columns do not exist before the December 2025 layout, so they
    amount to seven months from six notes. They used to be parsed on every run
    and then thrown away, which the Gate 1 self audit called finding 1.1: SPEC.md
    section 2 rule 5 asks for provisional to be labelled and every vintage kept,
    and the decoder already had both. They are now dgec_note_printed_monthly.
    """
    assert corpus["wb_NPG-2024.06.21.pdf"].printed_monthly == {}
    assert corpus["wb_NPG-2025.01.17.pdf"].printed_monthly == {}
    later = corpus["NPG-2026.09.04.pdf"]
    assert set(later.printed_monthly) == {(2026, 8), (2026, 9)}
    # Recon 02 section 3.5: provisionality is a COLUMN property, marked by
    # "(donnees provisoires)" under the header, and the current month carries it
    # while the last complete month does not.
    assert later.printed_monthly_provisional[(2026, 9)] is True
    assert later.printed_monthly_provisional[(2026, 8)] is False
    # Recon 02 section 4.4, the August 2026 monthly column, verbatim.
    assert later.printed_monthly[(2026, 8)]["brent_date_usd_t"] == 683
    assert later.printed_monthly[(2026, 8)]["gazole_usd_t"] == 1278


# ==========================================================================
# dgec_note_printed_monthly, the series the audit found being thrown away
# ==========================================================================

@pytest.fixture(scope="module")
def printed_monthly(corpus):
    """The monthly frame, built from the decoded corpus."""
    return build_printed_monthly(list(corpus.values()))


def test_the_monthly_series_is_seven_months_and_says_which(printed_monthly):
    """Seven months, from the six notes printing a six column table.

    Gate 1 self audit, finding 1.1: this used to be decoded correctly on every
    run and then discarded, which is precisely what SPEC.md section 2 rule 5
    forbids losing.
    """
    frame = printed_monthly
    assert len(frame) == 7
    assert [pd.Timestamp(d).strftime("%Y-%m") for d in frame["date"]] == [
        "2025-11",
        "2025-12",
        "2026-02",
        "2026-03",
        "2026-04",
        "2026-08",
        "2026-09",
    ]
    for column in PRINTED_COLUMNS:
        assert frame[column].notna().all(), "%s carries a hole" % column
    for column in PRINTED_MONTHLY_COLUMNS:
        assert column in frame.columns


def test_every_month_carries_the_ministrys_own_provisional_flag(printed_monthly):
    """SPEC.md section 2 rule 5, as data rather than as a sentence.

    The flags are the ones DGEC printed, read from the "(donnees provisoires)"
    marker under the column header. They are NOT contiguous: February 2026 is
    final while March 2026 was still provisional in the same note, and August
    2026 is final while September 2026 is provisional. That is why the flag is
    per row and provisional_from is only a range bound.
    """
    flags = {
        pd.Timestamp(d).strftime("%Y-%m"): bool(p)
        for d, p in zip(printed_monthly["date"], printed_monthly["provisional"])
    }
    assert flags == {
        "2025-11": False,
        "2025-12": True,
        "2026-02": False,
        "2026-03": False,
        "2026-04": True,
        "2026-08": False,
        "2026-09": True,
    }


def test_march_2026_is_an_observed_provisional_to_final_transition(printed_monthly):
    """The one thing in this project where a DGEC figure is seen moving.

    Four notes print March 2026. Two print it provisional, at 946 then 976 $/t
    Eurosuper, and two print it final at 988. The file keeps the final figure,
    flags the row final, and carries all four prints in revision_history, so the
    revision is readable out of the committed data rather than only out of the
    PDFs. SPEC.md section 2 rule 5: keep every vintage, show the flag.
    """
    row = printed_monthly[printed_monthly["date"] == pd.Timestamp("2026-03-01")].iloc[0]
    assert row["provisional"] is False or row["provisional"] == False  # noqa: E712
    assert row["n_prints"] == 4
    assert row["eurosuper_usd_t"] == 988
    assert row["gazole_usd_t"] == 1219
    assert row["vintage"] == "2026-04-24"
    assert row["first_vintage"] == "2026-03-20"
    assert bool(row["revised"]) is True
    # Gazole moved 1163 to 1219 between the first print and the final one, the
    # largest move of the six $/t columns.
    assert row["max_revision_usd_t"] == pytest.approx(56.0)

    history = row["revision_history"].split(";")
    assert len(history) == 4
    assert history[0].startswith("2026-03-20|provisional|")
    assert "eurosuper_usd_t=946" in history[0]
    assert history[1].startswith("2026-03-27|provisional|")
    assert "eurosuper_usd_t=976" in history[1]
    assert history[2].startswith("2026-04-03|final|")
    assert "eurosuper_usd_t=988" in history[2]
    assert history[3].startswith("2026-04-24|final|")
    # No comma anywhere, so the field never needs CSV quoting.
    assert "," not in row["revision_history"]


def test_april_2026_moved_between_two_provisional_prints(printed_monthly):
    """Revisions of 143 and 180 $/t while the month was still provisional.

    Gazole went 1,431 to 1,288 and Jet went 1,733 to 1,553 between two notes
    three weeks apart, both prints carrying the provisional marker. This is the
    size of the thing SPEC.md section 2 rule 5 warns about, and it would have
    been invisible if the file kept only the latest print with no history beside
    it.
    """
    row = printed_monthly[printed_monthly["date"] == pd.Timestamp("2026-04-01")].iloc[0]
    assert bool(row["provisional"]) is True
    assert row["n_prints"] == 2
    assert bool(row["revised"]) is True
    assert row["gazole_usd_t"] == 1288, "the LATEST provisional print is kept"
    assert row["jet_usd_t"] == 1553
    # The largest move of the six $/t columns is Jet's 180, not Gazole's 143.
    assert row["max_revision_usd_t"] == pytest.approx(180.0)
    history = row["revision_history"].split(";")
    assert "gazole_usd_t=1431" in history[0]
    assert "gazole_usd_t=1288" in history[1]
    assert "jet_usd_t=1733" in history[0]
    assert "jet_usd_t=1553" in history[1]
    assert all("|provisional|" in part for part in history)


def test_a_month_printed_once_has_no_revision_rather_than_a_zero(printed_monthly):
    """Undefined, not zero. The same rule as the spread columns.

    A revision measured against no earlier print is not a revision of zero, and
    writing 0 would say the ministry printed it twice and did not change it.
    """
    # How many months were printed once falls as notes are collected, since each
    # note reprints the months the one before it printed, so it is not pinned.
    once = printed_monthly[printed_monthly["n_prints"] == 1]
    assert len(once) >= 1
    assert once["max_revision_usd_t"].isna().all()
    assert (~once["revised"].astype(bool)).all()
    more = printed_monthly[printed_monthly["n_prints"] > 1]
    assert more["max_revision_usd_t"].notna().all()


def test_the_monthly_series_is_the_only_monthly_home_of_the_dgec_jet_quotation():
    """Stated in the adapter, and stated narrowly enough to be true.

    Jet and Fioul lourd TBTS are not on the page 3 chart, so they have no weekly
    reconstruction, and DGEC publishes no monthly product workbook, so this is
    the only place either appears at monthly frequency AS A DGEC $/t QUOTATION.

    They are not the only jet and fuel oil rows in the project and the claim is
    not that they are. opec_rotterdam_products_monthly carries jet_usd_bbl and
    fuel_oil_1pct_usd_bbl, which are Argus assessments of the same hub on a
    different specification in a different unit, and jodi_nwe_refinery_output_
    monthly carries jetkero volumes, which are not a price at all. Those are
    neighbours, not substitutes, and this test names them so that the adapter
    note cannot quietly become an overclaim.
    """
    path = CACHE / "dgec_note_printed_monthly.csv"
    if not path.exists():
        pytest.skip("%s is not built" % path)
    monthly = pd.read_csv(path)
    assert "jet_usd_t" in monthly.columns
    assert "fioul_lourd_tbts_usd_t" in monthly.columns

    expected_neighbours = {
        "jodi_nwe_refinery_output_monthly.csv",
        "opec_rotterdam_products_monthly.csv",
    }
    found = set()
    for other in sorted(CACHE.glob("*.csv")):
        if other.name in (
            "dgec_note_printed_monthly.csv",
            "dgec_note_printed_weekly.csv",
        ):
            continue
        header = pd.read_csv(other, nrows=0).columns
        if any(("jet" in c or "fioul_lourd" in c or "fuel_oil" in c) for c in header):
            found.add(other.name)
    assert found == expected_neighbours, (
        "a jet or heavy fuel oil column now appears in %s. If that is a real new "
        "source, the adapter note and this test both need rewriting rather than "
        "widening" % ", ".join(sorted(found - expected_neighbours)) or "nothing"
    )
    # And none of the neighbours is a DGEC $/t quotation.
    for name in expected_neighbours:
        header = pd.read_csv(CACHE / name, nrows=0).columns
        assert not any(c.endswith("_usd_t") for c in header), name


def test_the_monthly_adapter_declares_a_real_provisional_from(corpus):
    """SPEC.md section 5.3's provisional_from, derived rather than typed.

    Every DGEC entry in the manifest used to carry null here while the decoder
    held the flags, which was the visible half of finding 1.1.
    """
    adapter = DgecNotePrintedMonthly()
    adapter.notes = list(corpus.values())
    frame = adapter.fetch()
    assert adapter.provisional_from == "2025-12-01"
    assert pd.Timestamp(adapter.provisional_from) in set(
        frame.loc[frame["provisional"].astype(bool), "date"]
    )
    assert "provisional" in adapter.note.lower()


def test_brent_date_printed_in_usd_t_recovers_the_published_usd_bbl(corpus):
    """The 7.5 factor, checked against DGEC's own Brent workbook, per note.

    Recon 02 section 4.3 recovered the factor from five month pairs. This checks
    it the other way round, on the printed MONTHLY Brent column of every note
    that prints one, against the committed dgec_brent_monthly cache. It is the
    one place the note and the workbook can be compared directly, and it is what
    justifies dividing the weekly Brent leg of every crack by 7.5.
    """
    path = CACHE / "dgec_brent_monthly.csv"
    if not path.exists():
        pytest.skip("dgec_brent_monthly.csv is not built")
    published = pd.read_csv(path, parse_dates=["date"]).set_index("date")[
        "brent_usd_bbl"
    ]
    checked = 0
    for name, note in corpus.items():
        for (year, month), values in note.printed_monthly.items():
            if note.printed_monthly_provisional.get((year, month)):
                continue  # a provisional month is revised, recon 02 section 3.5
            printed = values.get("brent_date_usd_t")
            stamp = pd.Timestamp(year, month, 1)
            if printed is None or stamp not in published.index:
                continue
            expected = published.loc[stamp] * config.DGEC_BBL_PER_T_BRENT_NOTE
            assert round(expected) == printed, (
                "%s prints Brent date at %d $/t for %04d-%02d; the workbook gives "
                "%.4f $/bbl which is %.2f $/t at %g bbl/t"
                % (name, printed, year, month, published.loc[stamp], expected,
                   config.DGEC_BBL_PER_T_BRENT_NOTE)
            )
            # The other DGEC factor is shown to be the wrong one here, so that an
            # edit swapping the two constants fails with the reason attached.
            wrong = published.loc[stamp] * config.DGEC_BBL_PER_T_BRENT_MARGIN
            assert round(wrong) != printed
            checked += 1
    assert checked >= 3, "only %d monthly Brent column(s) could be checked" % checked


# ==========================================================================
# THE LINE NOT TO CROSS
# ==========================================================================

def test_jet_and_fioul_lourd_are_printed_and_never_reconstructed(corpus):
    """Recon 05 section 14, the line: do not reconstruct what the chart does not plot.

    Jet and Fioul lourd TBTS are in the printed table and are NOT on the page 3
    chart. They therefore do not exist as a weekly series, and filling them in by
    regression on the three products that are plotted would be exactly the
    synthetic series SPEC.md section 2 rule 1 forbids. It would also be obvious
    to any reader who knows the products.

    If a future note adds them to the chart, the legend match will find them and
    this test is the thing that has to be changed deliberately.
    """
    reconstructed = set(CHART_COLUMNS)
    for forbidden in ("jet_usd_t", "fioul_lourd_tbts_usd_t", "fioul_lourd_tbts_eur_t"):
        assert forbidden in PRINTED_COLUMNS
        assert forbidden not in reconstructed
    for note in corpus.values():
        assert set(note.chart) == reconstructed, note.file
    frame = build_reconstructed_weekly(list(corpus.values()))
    assert "jet_usd_t" not in frame.columns
    assert "fioul_lourd_tbts_usd_t" not in frame.columns


# ==========================================================================
# The stitched reconstruction
# ==========================================================================

@pytest.fixture(scope="module")
def reconstructed(corpus):
    return build_reconstructed_weekly(list(corpus.values()))


@pytest.fixture(scope="module")
def recon_reconstructed(recon_corpus):
    """The stitched series from recon 05's ten notes alone."""
    return build_reconstructed_weekly(list(recon_corpus.values()))


def test_the_stitched_series_is_219_consecutive_fridays_with_no_holes(recon_reconstructed):
    """Recon 05 section 12: union 2022-07-01 to 2026-09-04, 219 weeks, zero holes."""
    frame = recon_reconstructed
    assert len(frame) == 219
    assert frame["date"].min() == FIRST_FRIDAY
    assert frame["date"].max() == pd.Timestamp("2026-09-04")


def test_the_live_series_runs_every_friday_to_the_latest_note(reconstructed, latest_vintage):
    """The same shape on every note collected: consecutive Fridays from the
    oldest chart's first week to the newest note's own date, no holes."""
    frame = reconstructed
    assert frame["date"].min() == FIRST_FRIDAY
    assert frame["date"].max() == latest_vintage
    assert len(frame) == _fridays(FIRST_FRIDAY, latest_vintage)
    assert (frame["date"].dt.dayofweek == 4).all(), "every week ends on a Friday"
    gaps = frame["date"].diff().dropna().unique()
    assert list(gaps) == [pd.Timedelta(days=7)]
    for column in CHART_COLUMNS:
        assert frame[column].notna().all(), "%s carries a hole" % column


def test_twenty_five_weeks_have_no_cross_check_and_they_are_the_ends(recon_reconstructed):
    """Recon 05 section 14 condition 5, carried in the data and not in prose.

    Twenty five of the 219 weeks are covered by one chart geometry only, and on
    those weeks the spread columns are NaN, because a spread between one reading
    and nothing is undefined. They used to be 0.0, which reads as a positive
    claim that two notes agreed, and the Gate 1 self audit, finding e.1, called
    that out: opec_rotterdam_products_monthly had always written NaN in the
    identical situation and these two files now match it.

    A CORRECTION TO RECON 05 SECTION 12, ON THE RECORD. That section says the
    twenty five are "the 20 oldest, 2022-07-01 to 2022-11-11, and the 5 newest,
    2026-08-07 to 2026-09-04". The count of twenty five is right and the split is
    not: they are the SIX oldest, 2022-07-01 to 2022-08-05, and the NINETEEN
    newest, 2026-05-01 to 2026-09-04. Recon 05's own demonstration output
    disagrees with its own sentence, printing n_notes of 1 for six rows and then
    2 from 2022-08-12, which is what the note coverage implies: wb_NPG-2024.06.21
    reaches back to 2022-07-01 and wb_NPG-2024.07.12 to 2022-08-12, so the first
    six weeks have one covering note and the seventh has two. The corrected split
    matters because it moves nineteen of the twenty five uncorroborated weeks
    into the RECENT end of the sample, which is the end a reader looks at.

    On recon 05's ten notes. Every note collected since with the same geometry as
    NPG-2026.09.04 adds one week to the newest run; see the live test below.
    """
    frame = recon_reconstructed
    single = frame[~frame["cross_checked"]]
    assert len(single) == 25
    assert list(single["date"].head(6)) == list(frame["date"].head(6))
    assert list(single["date"].tail(19)) == list(frame["date"].tail(19))
    assert single["date"].head(6).max() == pd.Timestamp("2022-08-05")
    assert single["date"].tail(19).min() == pd.Timestamp("2026-05-01")
    spreads = ["spread_%s" % c for c in CHART_COLUMNS]
    assert single[spreads].isna().all().all(), (
        "an uncorroborated week carries a spread. There was never a second "
        "geometry to spread against, so the only honest value is NaN"
    )
    covered = frame[frame["cross_checked"]]
    assert len(covered) == 194
    assert (covered["n_independent_geometries"] >= 2).all()
    assert covered[spreads].notna().all().all(), (
        "a cross checked week carries no spread, so the cross check is not in "
        "the data"
    )
    # Recon 05 section 12's own coverage table, which is right: 25 weeks with one
    # covering note, 7 with two, 187 with three or more.
    counts = frame["n_notes"].value_counts()
    assert int(counts.get(1, 0)) == 25
    assert int(counts.get(2, 0)) == 7
    assert int(frame["n_notes"].ge(3).sum()) == 187
    assert int(frame["n_notes"].max()) == 9


def test_the_newest_single_geometry_run_starts_where_the_last_second_chart_ends(reconstructed, latest_vintage):
    """On the live corpus: the six oldest weeks, and every week from 2026-05-01 to
    the latest note, have one geometry. The newest run grows by a week with each
    note that shares NPG-2026.09.04's geometry, and it shrinks only when a note
    with a different geometry is collected, which this test would then report."""
    frame = reconstructed
    single = frame[~frame["cross_checked"]]
    newest = _fridays(NEWEST_RUN_START, latest_vintage)
    assert len(single) == 6 + newest
    assert list(single["date"].head(6)) == list(frame["date"].head(6))
    assert list(single["date"].tail(newest)) == list(frame["date"].tail(newest))
    assert single["date"].tail(newest).min() == NEWEST_RUN_START
    assert len(frame[frame["cross_checked"]]) == len(frame) - 6 - newest


def test_the_six_oldest_weeks_are_flagged_as_weak_twice_over(reconstructed, latest_vintage):
    """Gate 1 self audit, point 10 item 6, answered in the data.

    The audit's point was not that the six oldest weeks were undocumented. It
    was that cross_checked is a boolean and the 25 weeks it marks False are not
    equally weak: nineteen of them are uncorroborated but sit ON the anchored
    right hand end of their note's chart, and six are uncorroborated AND 105
    weeks from the nearest anchor at the far left of the only note that draws
    them. Both weaknesses at once, and only for those six. evidence_class is
    where that compounding becomes a value rather than a sentence.
    """
    frame = reconstructed
    assert set(frame["evidence_class"]) <= set(EVIDENCE_CLASSES)
    counts = frame["evidence_class"].value_counts().to_dict()
    newest = _fridays(NEWEST_RUN_START, latest_vintage)
    assert counts == {
        "cross_checked": len(frame) - 6 - newest,
        "single_geometry_newest": newest,
        "single_geometry_oldest": 6,
    }
    oldest = frame[frame["evidence_class"] == "single_geometry_oldest"]
    assert [pd.Timestamp(d).strftime("%Y-%m-%d") for d in oldest["date"]] == [
        "2022-07-01",
        "2022-07-08",
        "2022-07-15",
        "2022-07-22",
        "2022-07-29",
        "2022-08-05",
    ]
    # They are the very start of the series, which is what "far left of the
    # chart" means, and they have exactly one note and one geometry.
    assert list(oldest.index) == list(range(6))
    assert (oldest["n_notes"] == 1).all()
    assert (oldest["n_independent_geometries"] == 1).all()
    # Every uncorroborated week is classified as one kind or the other, and no
    # corroborated week is.
    single = frame[~frame["cross_checked"]]
    assert set(single["evidence_class"]) == {
        "single_geometry_oldest",
        "single_geometry_newest",
    }
    assert set(frame[frame["cross_checked"]]["evidence_class"]) == {"cross_checked"}


def test_the_evidence_class_travels_with_the_cracks(reconstructed):
    """A crack is exactly as defended as the two quotations it came from.

    The cracks file is what a reader of the site will actually plot, so the
    provenance has to be on its rows and not one join away.
    """
    cracks = weekly_cracks(reconstructed)
    assert "evidence_class" in cracks.columns
    assert list(cracks["evidence_class"]) == list(reconstructed["evidence_class"])
    path = CACHE / "dgec_note_reconstructed_cracks_weekly.csv"
    if path.exists():
        committed = pd.read_csv(path)
        assert "evidence_class" in committed.columns
        assert int((committed["evidence_class"] == "single_geometry_oldest").sum()) == 6


def test_the_degenerate_pair_counts_once(corpus, reconstructed):
    """Recon 05 section 12, disclosed rather than enjoyed.

    wb_NPG-2026.04.03 and NPG-2026.09.04 draw the same 400 to 1500 axis over 12
    ticks at the same point pitch, so an identical value lands on an identical
    pixel and the two decodes CANNOT disagree. Their standard deviation over the
    83 common weeks is exactly zero. That is determinism, not accuracy, so
    n_independent_geometries counts distinct geometries rather than notes and the
    pair contributes one piece of evidence, not two.
    """
    a = corpus["wb_NPG-2026.04.03.pdf"]
    b = corpus["NPG-2026.09.04.pdf"]
    assert a.geometry == b.geometry, (
        "the two notes recon 05 section 12 found degenerate no longer share a "
        "geometry. Re-measure before relaxing anything: %r against %r"
        % (a.geometry, b.geometry)
    )
    common = sorted(set(a.weeks) & set(b.weeks))
    assert len(common) == 83
    differences = [
        a.chart["gazole_usd_t"][w] - b.chart["gazole_usd_t"][w] for w in common
    ]
    assert statistics.pstdev(differences) == pytest.approx(0.0, abs=1e-9), (
        "the pair is supposed to be degenerate: a non zero standard deviation "
        "means the geometry changed and DEGENERATE_PAIR needs rewriting"
    )
    # And the data says so: on those weeks more notes cover the week than there
    # are independent geometries.
    frame = reconstructed.set_index("date")
    stamps = [pd.Timestamp(w) for w in common]
    assert (
        frame.loc[stamps, "n_notes"] > frame.loc[stamps, "n_independent_geometries"]
    ).any()


def test_overlapping_notes_agree_to_what_recon_05_measured(recon_corpus):
    """Recon 05 section 12: mean absolute 0.30 $/t, worst single week 1.68.

    This is the genuinely out of sample evidence, because the left hand end of a
    recent note is the right hand end of an older one and no anchor sits there.
    Pairs are compared only where they share at least five weeks. On the ten
    notes recon 05 measured: a later note adds pairs, and a later note with the
    degenerate geometry adds pairs that cannot disagree, which would flatter the
    mean rather than test it.
    """
    notes = list(recon_corpus.values())
    per_pair = []
    worst = 0.0
    worst_where = None
    for i, first in enumerate(notes):
        for second in notes[i + 1:]:
            common = sorted(set(first.weeks) & set(second.weeks))
            if len(common) < 5:
                continue
            for column in CHART_COLUMNS:
                differences = [
                    abs(first.chart[column][w] - second.chart[column][w]) for w in common
                ]
                per_pair.append(statistics.mean(differences))
                if max(differences) > worst:
                    worst = max(differences)
                    worst_where = (first.file, second.file, column)
    assert len(per_pair) == 168, "recon 05 section 12 ran 168 comparisons"
    mean_absolute = statistics.mean(per_pair)
    assert mean_absolute == pytest.approx(
        dgec_note.RECONSTRUCTION_ERROR["note_pair_mean_absolute_usd_t"], abs=0.05
    ), "mean pairwise agreement is %.3f $/t" % mean_absolute
    assert worst == pytest.approx(
        dgec_note.RECONSTRUCTION_ERROR["note_pair_worst_week_usd_t"], abs=0.05
    ), "worst single week is %.3f $/t at %r" % (worst, worst_where)
    # Recon 05 section 12 found the worst week is on Brent, which is the evidence
    # behind BRENT_IS_WORST.
    assert worst_where[2] == "brent_date_usd_t"


def test_brent_is_the_least_accurate_of_the_four(reconstructed):
    """Recon 05 section 14 condition 5, and BRENT_IS_WORST is the words for it.

    Brent is the lowest line on a chart scaled for the product lines, so the same
    pixel error is a larger relative error. The widest single week disagreement
    between notes, across all four series, is on Brent.
    """
    covered = reconstructed[reconstructed["cross_checked"]]
    worst = {c: covered["spread_%s" % c].max() for c in CHART_COLUMNS}
    assert max(worst, key=worst.get) == "brent_date_usd_t", worst
    assert "least accurately decoded" in dgec_note.BRENT_IS_WORST
    assert "dgec_brent_monthly" in dgec_note.BRENT_IS_WORST


def test_the_reconstruction_reproduces_the_recon_05_demonstration(recon_reconstructed):
    """Against recon 05's own 219 row output, which was built independently.

    The demonstration csv is rounded to one decimal, so the tolerance is the
    rounding and nothing else. This is the test that says the production adapter
    and the measurement harness are the same arithmetic rather than two
    plausible ones. It runs on recon 05's ten notes, because the stitched value
    of a week is a mean over the notes that draw it and a later note moves it.
    """
    demo = base.PRIVATE / "probe" / "cracks" / "reconstructed_weekly_DEMO.csv"
    if not demo.exists():
        pytest.skip("recon 05's demonstration output is not present at %s" % demo)
    expected = pd.read_csv(demo, parse_dates=["week_ending"])
    joined = recon_reconstructed.merge(expected, left_on="date", right_on="week_ending")
    assert len(joined) == 219
    for mine, theirs in (
        ("eurosuper_usd_t", "Eurosuper_usd_t"),
        ("gazole_usd_t", "Gazole_usd_t"),
        ("fioul_domestique_usd_t", "Fioul domestique_usd_t"),
        ("brent_date_usd_t", "Brent_usd_t"),
    ):
        worst = (joined[mine] - joined[theirs]).abs().max()
        assert worst <= 0.06, "%s differs from recon 05 by %.4f $/t" % (mine, worst)


# ==========================================================================
# The gates. Every one of them, fired on purpose.
# ==========================================================================

class _Page:
    """The smallest thing the geometry helpers will accept."""

    def __init__(self, curves=(), chars=(), lines=()):
        self.curves = list(curves)
        self.chars = list(chars)
        self.lines = list(lines)


def _polyline(n, colour="(0.0, 0.0, 1.0)"):
    return {"pts": [(float(i), 100.0 + i) for i in range(n)], "stroking_color": colour}


def test_a_chart_without_four_equal_polylines_fails_loudly():
    with pytest.raises(NoteDecodeError) as caught:
        dgec_note._chart_polylines(_Page(curves=[_polyline(105) for _ in range(3)]))
    assert "expected exactly 4" in str(caught.value)

    with pytest.raises(NoteDecodeError) as caught:
        dgec_note._chart_polylines(_Page(curves=[_polyline(10)]))
    assert "no polyline" in str(caught.value)


def test_fewer_than_four_y_ticks_fails_loudly():
    chars = []
    for index, (top, text) in enumerate([(10.0, "500"), (30.0, "600"), (50.0, "700")]):
        for offset, glyph in enumerate(text):
            chars.append(
                {
                    "x0": 10.0 + offset,
                    "x1": 15.0 + offset,
                    "top": top,
                    "bottom": top + 5,
                    "text": glyph,
                }
            )
    with pytest.raises(NoteDecodeError) as caught:
        dgec_note._value_axis(_Page(chars=chars), (100.0, 400.0, 5.0, 60.0))
    assert "tick label" in str(caught.value)


def test_an_anchor_residual_over_the_gate_fails_loudly():
    """The headline gate, recon 05 section 14 condition 6.

    One product is moved 6 $/t off its printed value. The fitted offset absorbs a
    quarter of it, leaving well over the 1.5 $/t limit, and the decode refuses
    rather than shipping a note whose axis fit is wrong.
    """
    weeks = [date(2026, 8, 28), date(2026, 9, 4)]
    printed = {
        weeks[0]: {c: 1000.0 for c in CHART_COLUMNS},
        weeks[1]: {c: 1010.0 for c in CHART_COLUMNS},
    }
    good = {c: [1000.0, 1010.0] for c in CHART_COLUMNS}
    offset, anchors, diagnostics = dgec_note._calibrate(good, printed, weeks)
    assert offset == pytest.approx(0.0)
    assert diagnostics["anchor_worst_usd_t"] == pytest.approx(0.0)

    bad = dict(good)
    bad["brent_date_usd_t"] = [994.0, 1004.0]
    with pytest.raises(NoteDecodeError) as caught:
        dgec_note._calibrate(bad, printed, weeks)
    message = str(caught.value)
    assert "worst anchor" in message
    assert "brent_date_usd_t" in message
    assert "nothing from it is used" in message


def test_a_missing_printed_anchor_fails_rather_than_calibrating_on_fewer():
    weeks = [date(2026, 8, 28), date(2026, 9, 4)]
    printed = {
        weeks[0]: {c: 1000.0 for c in CHART_COLUMNS if c != "gazole_usd_t"},
        weeks[1]: {c: 1010.0 for c in CHART_COLUMNS},
    }
    raw = {c: [1000.0, 1010.0] for c in CHART_COLUMNS}
    with pytest.raises(NoteDecodeError) as caught:
        dgec_note._calibrate(raw, printed, weeks)
    assert "expected 8" in str(caught.value)


def test_a_note_that_fails_a_gate_stops_the_whole_build(monkeypatch, tmp_path):
    """Strict by default, and deliberately so.

    All ten notes decode today, so a gate firing means the layout changed or a
    file is damaged. Dropping the note and shipping a shorter series would hide
    that, so load_corpus raises and Adapter.run keeps the previous cache.
    """
    real = dgec_note.decode_note

    def explode(path):
        if Path(path).name.startswith("NPG-"):
            raise NoteDecodeError("synthetic gate failure")
        return real(path)

    if not _paths():
        pytest.skip("no note PDF present")
    monkeypatch.setattr(dgec_note, "decode_note", explode)
    with pytest.raises(NoteDecodeError) as caught:
        dgec_note.load_corpus(strict=True)
    assert "synthetic gate failure" in str(caught.value)
    assert "is not rebuilt" in str(caught.value)


def test_an_empty_corpus_directory_fails_rather_than_writing_nothing(tmp_path):
    with pytest.raises(NoteDecodeError) as caught:
        dgec_note.load_corpus(tmp_path, strict=True)
    assert "irreplaceable" in str(caught.value)


def test_a_failing_fetch_keeps_the_cache_and_marks_the_entry_failed(sandbox, monkeypatch):
    """SPEC.md section 5.4, exercised on this adapter rather than assumed.

    The previous cache must survive a failed rebuild untouched, and the manifest
    must say the series failed rather than quietly keeping an "ok" from the last
    good run.
    """
    adapter = DgecNoteReconstructedWeekly()
    existing = pd.DataFrame(
        {
            "date": pd.to_datetime(["2022-07-01"]),
            **{c: [1000.0] for c in CHART_COLUMNS},
        }
    )
    base.write_cache(adapter.name, existing, directory="cache")
    monkeypatch.setattr(
        dgec_note,
        "load_corpus",
        lambda *a, **k: (_ for _ in ()).throw(NoteDecodeError("the chart moved")),
    )
    with pytest.raises(NoteDecodeError):
        adapter.run()
    kept = base.read_cache(adapter.name, directory="cache")
    assert len(kept) == 1
    entry = [
        e
        for e in base.manifest_read()["series"]
        if e["series"] == "dgec_note_reconstructed_weekly"
    ][0]
    assert entry["status"] == "failed"
    assert "the chart moved" in entry["note"]
    assert entry["method"] == "reconstructed"


# ==========================================================================
# The cracks, and the two external cross checks
# ==========================================================================

def test_the_crack_formula_is_the_spec_formula(reconstructed):
    """SPEC.md section 4.2, with config's constants and no others."""
    cracks = weekly_cracks(reconstructed)
    row = reconstructed.iloc[100]
    out = cracks.iloc[100]
    brent = row["brent_date_usd_t"] / config.DGEC_BBL_PER_T_BRENT_NOTE
    assert out["brent_usd_bbl"] == pytest.approx(brent)
    assert out["crack_gasoil_usd_bbl"] == pytest.approx(
        row["gazole_usd_t"] / config.BBL_PER_T_GASOIL - brent
    )
    assert out["crack_gasoline_usd_bbl"] == pytest.approx(
        row["eurosuper_usd_t"] / config.BBL_PER_T_GASOLINE - brent
    )
    # The margin factor is NOT the note factor. Using 7.55 here would be a silent
    # 0.67 percent error on the crude leg, about 0.56 $/bbl at a Brent of 84.
    assert config.DGEC_BBL_PER_T_BRENT_MARGIN != config.DGEC_BBL_PER_T_BRENT_NOTE
    assert out["crack_gasoil_usd_bbl"] != pytest.approx(
        row["gazole_usd_t"] / config.BBL_PER_T_GASOIL
        - row["brent_date_usd_t"] / config.DGEC_BBL_PER_T_BRENT_MARGIN
    )
    # Both legs share a date by construction, SPEC.md section 4.2. There is no
    # join here to get wrong, and that is the point.
    assert list(cracks["date"]) == list(reconstructed["date"])


def test_october_2022_weekly_gasoil_cracks(reconstructed):
    """SPEC.md section 3's crisis, at weekly resolution, from this study's data.

    The week ending 21 October 2022 straddles 13 October, the day S&P Global
    reported ARA diesel cracks near 80 $/bbl. The reconstruction puts that week
    at about 82, from a French ministry chart, with no knowledge of the S&P
    figure. That is an independent reproduction of a published number and it is
    the single most persuasive thing in this layer.

    The expected values below are the previous agent's measurement, kept as
    written so that a change in the decoder shows up as a disagreement with a
    recorded figure rather than being absorbed.
    """
    cracks = weekly_cracks(reconstructed).set_index("date")
    expected = {
        "2022-10-07": 50.99,
        "2022-10-14": 61.97,
        "2022-10-21": 82.12,
        "2022-10-28": 74.37,
    }
    got = {}
    for when, previous in expected.items():
        value = float(cracks.loc[pd.Timestamp(when), "crack_gasoil_usd_bbl"])
        got[when] = value
        assert value == pytest.approx(previous, abs=0.10), (
            "week ending %s: this build gives %.3f $/bbl, the previously recorded "
            "measurement is %.2f" % (when, value, previous)
        )
    october = statistics.mean(got.values())
    assert october == pytest.approx(67.36, abs=0.05)
    # And the week straddling 13 October is the peak, near the 80 $/bbl S&P
    # reported. Order of magnitude, never a target: SPEC.md section 6.6.
    assert max(got, key=got.get) == "2022-10-21"
    assert 78.0 < got["2022-10-21"] < 86.0


def test_against_the_opec_monthly_rotterdam_table(reconstructed):
    """Two independent sources meeting. Recon 05 section 13.4, at full length.

    A French ministry chart decoded from vector curves, and an Argus assessed
    table printed in an OPEC PDF, over the 44 months both cover. The gasoil
    cracks agree to a mean absolute of about 1.6 $/bbl. The gasoline cracks do
    not, by about 9 $/bbl on average, and that disagreement is ASSERTED HERE
    rather than hidden, because the two sources quote different products and
    imply 7.42 to 8.15 barrels per tonne rather than the contract's 8.33. Picking
    a factor that closed the gap would be the tuning SPEC.md section 6.6 forbids.

    Both cracks are taken against the SAME Brent leg, the note's own Brent date
    divided by 7.5, so the difference measured here is the product leg alone.
    """
    path = CACHE / "opec_rotterdam_products_monthly.csv"
    if not path.exists():
        pytest.skip("opec_rotterdam_products_monthly.csv is not built")
    opec = pd.read_csv(path, parse_dates=["date"])
    opec["month"] = opec["date"].dt.to_period("M")
    opec = opec.set_index("month")

    cracks = weekly_cracks(reconstructed)
    cracks["month"] = cracks["date"].dt.to_period("M")
    monthly = cracks.groupby("month").agg(
        gasoil=("crack_gasoil_usd_bbl", "mean"),
        gasoline=("crack_gasoline_usd_bbl", "mean"),
        brent=("brent_usd_bbl", "mean"),
        weeks=("crack_gasoil_usd_bbl", "size"),
    )
    joined = monthly.join(
        opec[["gasoil_usd_bbl", "premium_gasoline_usd_bbl"]], how="inner"
    ).dropna(subset=["gasoil_usd_bbl"])
    assert len(joined) == 44, "the overlap is 44 months, got %d" % len(joined)
    assert str(joined.index.min()) == "2022-07"
    assert str(joined.index.max()) == "2026-02"

    gasoil = joined["gasoil"] - (joined["gasoil_usd_bbl"] - joined["brent"])
    gasoline = joined["gasoline"] - (joined["premium_gasoline_usd_bbl"] - joined["brent"])

    assert gasoil.mean() == pytest.approx(1.10, abs=0.10), (
        "gasoil crack, reconstruction minus OPEC: mean %+.2f, mean absolute %.2f, "
        "range %+.2f to %+.2f"
        % (gasoil.mean(), gasoil.abs().mean(), gasoil.min(), gasoil.max())
    )
    assert gasoil.abs().mean() == pytest.approx(1.58, abs=0.10)
    assert gasoil.min() == pytest.approx(-2.45, abs=0.15)
    assert gasoil.max() == pytest.approx(5.99, abs=0.15)

    # THE GAP THAT IS NOT SOLVED, asserted so it cannot be quietly closed.
    assert gasoline.mean() == pytest.approx(-8.82, abs=0.15), (
        "gasoline crack, reconstruction minus OPEC: mean %+.2f, range %+.2f to "
        "%+.2f" % (gasoline.mean(), gasoline.min(), gasoline.max())
    )
    assert gasoline.min() == pytest.approx(-21.97, abs=0.20)
    assert gasoline.max() == pytest.approx(0.07, abs=0.20)
    assert abs(gasoline.mean()) > abs(gasoil.mean()) * 3, (
        "the gasoline disagreement is meant to be much the larger of the two. If "
        "it has closed, find out why before celebrating"
    )


# ==========================================================================
# Declarations, the registry and the manifest
# ==========================================================================

def test_the_two_series_are_separate_and_declare_different_methods():
    """Recon 05 section 14 condition 2, and the reason the method field exists."""
    printed = config.source("dgec_note_printed_weekly")
    rebuilt = config.source("dgec_note_reconstructed_weekly")
    assert printed.series != rebuilt.series
    assert printed.method == "parsed"
    assert rebuilt.method == "reconstructed"
    assert DgecNotePrintedWeekly.method == "parsed"
    assert DgecNoteReconstructedWeekly.method == "reconstructed"
    assert DgecNoteReconstructedCracksWeekly.method == "derived"
    assert DgecNotePrintedWeekly.name != DgecNoteReconstructedWeekly.name
    for adapter in (
        DgecNotePrintedWeekly,
        DgecNoteReconstructedWeekly,
        DgecNoteReconstructedCracksWeekly,
    ):
        registered = config.source(adapter.name)
        assert adapter.frequency == registered.frequency == "weekly"
        assert adapter.committable == registered.committable is True
        assert adapter.method == registered.method


def test_the_reconstructed_series_carries_its_method_and_its_error_in_the_manifest(
    sandbox, corpus, latest_vintage
):
    """Recon 05 section 14 conditions 2 and 3, checked where they have to be true.

    The required sentence is checked word for word. The measured error, the
    degeneracy and the products that are deliberately absent all travel in the
    manifest entry, not in a docstring somewhere the site cannot read.
    """
    adapter = DgecNoteReconstructedWeekly()
    adapter.notes = list(corpus.values())
    entry = adapter.run()
    assert entry["status"] == "ok"
    assert entry["method"] == "reconstructed"
    assert entry["rows"] == _fridays(FIRST_FRIDAY, latest_vintage)
    assert entry["gaps"] == []
    required = (
        "reconstructed from the vector polyline on page 3 of the DGEC weekly "
        "note, calibrated against the printed weekly averages on the same page"
    )
    assert entry["reconstruction"]["method"] == required
    assert required.upper() in entry["note"].upper()
    assert entry["reconstruction"]["error_usd_t"]["out_of_sample_worst_usd_t"] == 0.87
    assert "degeneracy" in entry["reconstruction"]
    assert "wb_NPG-2026.04.03" in entry["reconstruction"]["degeneracy"]
    assert "Jet" in entry["reconstruction"]["not_reconstructed"]
    assert entry["reconstruction"]["gates"]["max_anchor_residual_usd_t"] == 1.5
    assert latest_vintage.strftime("%Y-%m-%d") in str(entry["vintage"])

    stored = base.manifest_read()["series"]
    names = [e["series"] for e in stored]
    assert "dgec_note_reconstructed_weekly" in names
    assert "dgec_note_printed_weekly" not in names, (
        "the two series are written by two adapters and must never share an entry"
    )


def test_the_printed_adapter_declares_an_honest_floor_per_column():
    """Two columns have a lower floor and both reasons are facts about the source."""
    floors = DgecNotePrintedWeekly.min_observations
    assert set(floors) == set(PRINTED_COLUMNS)
    assert floors["brent_date_usd_t"] == 18
    assert floors["fioul_lourd_tbts_usd_t"] == 16
    assert floors["fioul_lourd_tbts_eur_t"] == 10
    assert set(DgecNotePrintedWeekly.bounds) == set(PRINTED_COLUMNS)
    assert set(DgecNoteReconstructedWeekly.bounds) == set(CHART_COLUMNS)


def test_the_committed_caches_are_what_the_adapters_built():
    """The three files in data/cache, checked as committed artefacts.

    Runs on a fresh checkout, with no note PDF, so the expected lengths come from
    the committed files themselves: the reconstruction is every Friday from the
    oldest chart's first week to its own last date, the cracks file has one row
    per reconstructed week, and the printed series ends on that same Friday,
    because the note that drew the newest week also printed it.
    """
    frames = {}
    for name in (
        "dgec_note_printed_weekly.csv",
        "dgec_note_reconstructed_weekly.csv",
        "dgec_note_reconstructed_cracks_weekly.csv",
    ):
        path = CACHE / name
        if not path.exists():
            pytest.skip("%s is not built yet" % name)
        frames[name] = pd.read_csv(path, parse_dates=["date"])
        raw = path.read_bytes()
        assert b"\r\n" not in raw, "%s must be LF, not CRLF" % name
    quotes = frames["dgec_note_reconstructed_weekly.csv"]
    last = quotes["date"].max()
    assert quotes["date"].min() == FIRST_FRIDAY
    assert len(quotes) == _fridays(FIRST_FRIDAY, last)
    assert list(frames["dgec_note_reconstructed_cracks_weekly.csv"]["date"]) == list(quotes["date"])
    assert frames["dgec_note_printed_weekly.csv"]["date"].max() == last
    assert len(frames["dgec_note_printed_weekly.csv"]) >= 18
