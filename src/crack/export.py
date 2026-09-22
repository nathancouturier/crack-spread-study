"""The site facing JSON artifacts. What `make build` writes and `make build-check` checks.

SPEC.md section 2 rule 2: every number in the browser comes from a JSON
artifact, and there are no numeric literals in the frontend except unit
constants. This module is the other side of that rule. It reads the committed
caches through crack.series and crack.analysis, never the network, and writes
one schema versioned file per concern into data/:

    data/now.json            the verdict, as segments, and the three data dates
    data/cracks.json         the latest weekly cracks against the same week of
                             every prior year, with the evidence per point
    data/margin-stack.json   the waterfall for the margin month, residual and
                             gas wedge included
    data/run-economics.json  utilisation against what the margin implies, the
                             response of both equations, the threshold verdict
    data/provenance.json     the manifest whole, plus attribution per source

WHAT A SENTENCE IS HERE. SPEC.md section 4.5 says the verdict is assembled from
values and never written by hand. Every sentence the Now view prints is exported
as a list of segments. A text segment carries words and nothing else, and
tests/test_export.py asserts it holds no digit. A value segment carries the
field it came from, the value, and the name of its format, and the decimals for
every format are in the artifact's conventions block, so the browser formats a
number without typing a literal. Dates travel as ISO strings with a display
label beside them.

MISSING IS null, NEVER ZERO. SPEC.md section 2 rule 1. A NaN reaching a payload
is converted to null by _num, and the serialiser runs with allow_nan=False on
every leaf, so a NaN that slipped past raises instead of writing the token NaN,
which is not JSON.

BYTE IDEMPOTENT. No artifact carries the time it was generated. Floats are
rounded to ROUND_DP places so the bytes do not depend on the last bit of a sum,
keys are written in insertion order, text is ASCII with LF endings and one
trailing newline. Building twice leaves the tree clean, and `build-check`
rebuilds in memory and compares bytes without writing.

THE CAPACITY CACHE, ANSWERED AT GATE 5. Utilisation used to need
data/private/ei_refinery_capacity_annual, which may not be committed
(docs/sources.md section 2.7), so a build on any machine without it, every
GitHub runner included, died on FileNotFoundError before it could write
run-economics.json. The five country total the analysis actually needs is now a
committed derived cache, nwe5_refinery_capacity_annual, and nothing in this
module or in crack.analysis reads data/private any more. The Energy Institute
table itself is still private and still never published. See crack.sources.ei's
docstring, "WHAT GATE 5 ADDED".
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from crack import analysis, config, engine, series, versions
from crack.sources import dgec_note, events_anchors, opec_momr

__all__ = [
    "SCHEMA_VERSION",
    "GENERATED_BY",
    "ARTIFACTS",
    "DECIMALS",
    "build",
    "serialise",
    "write_all",
    "check",
    "stale_artifacts",
    "now",
    "cracks",
    "margin_stack",
    "run_economics",
    "provenance",
    "runs",
    "events",
    "method",
    "run_verdict",
    "main",
]

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"

SCHEMA_VERSION = 1
GENERATED_BY = "src/crack/export.py"

#: Every float in every artifact is rounded to this many places. Six is far
#: below any decimals the page prints and far above the 1e-9 the parity check
#: works at, which does not read these files.
ROUND_DP = 6

#: Decimals per format, the one place the page's precision is decided. Part 3
#: section 5 of docs/design.md: $/bbl 2, kb/d 1, t 2, R2 3, power 3. pp is 1,
#: not 3 (Part 7, C14): the only pp figure on the page is the difference of two
#: utilisation figures printed to one place, and three places on it claimed a
#: precision neither figure has.
DECIMALS: Mapping[str, int] = {
    "usd_bbl": 2,
    "usd_t": 0,
    "usd_t_error": 2,
    "usd_mmbtu": 2,
    "eur_mwh": 2,
    "eurusd": 4,
    "mmbtu_per_mwh": 6,
    "mmbtu_per_bbl": 3,
    "kb_d": 1,
    "t": 2,
    "r2": 3,
    "pp": 1,
    "pp_per_usd_bbl": 3,
    "percent": 1,
    "ratio": 1,
    "yield_percent": 1,
    "bbl_per_t": 2,
    "count": 0,
    "year": 0,
    "coef": 5,
    "rmse": 3,
    "power": 3,
    "f_stat": 3,
    "gap_percent": 2,
    "slope": 2,
    "mmbtu_per_bbl_5": 5,
    "bbl_per_t_4": 4,
}

#: Formats whose values are whole numbers and are written as JSON integers.
INTEGER_FORMATS = ("count", "year")

MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
)

#: This study's name for each product, in the words a sentence uses, and the
#: source's own label beside it. SPEC.md section 4.2: the label travels.
PRODUCT_NAMES: Mapping[str, str] = {
    "gasoil": "gasoil",
    "gasoline": "gasoline",
    "jet": "jet",
    "heating_oil": "heating oil",
    "fuel_oil_1pct": "fuel oil",
}

#: The ICE contract each cited factor is read from. config.py carries the same
#: citation in its comments; this is the machine readable copy for the page.
FACTOR_CITATIONS: Mapping[str, Mapping[str, str]] = {
    "gasoil": {
        "contract": "ICE Gasoil Crack, Low Sulphur Gasoil 1st Line vs Brent 1st Line Future",
        "url": "https://www.ice.com/products/6753331",
    },
    "gasoline": {
        "contract": "ICE Gasoline Crack, Argus Eurobob Oxy FOB Rotterdam Barges vs Brent 1st Line Future",
        "url": "https://www.ice.com/products/6753285",
    },
    "jet": {
        "contract": "ICE Jet Fuel Crack, Jet CIF NWE Cargoes vs Brent 1st Line Future",
        "url": "https://www.ice.com/products/6753303",
    },
    "heating_oil": {
        "contract": "ICE Gasoil Crack, Gasoil 0.1% FOB ARA Barges (Platts) vs Brent 1st Line Future (in MTs)",
        "url": "https://www.ice.com/products/6753295",
    },
    "fuel_oil_1pct": {
        "contract": "ICE Fuel Oil Crack, Fuel Oil 1% FOB NWE Cargoes vs Brent 1st Line Future",
        "url": "https://www.ice.com/products/6753289",
    },
}

#: What each unattributed slate line is called in a sentence.
SLATE_LINE_NAMES: Mapping[str, str] = {
    "butane": "butane",
    "essence_export": "export gasoline",
    "naphta": "naphtha",
    "propane": "propane",
    "soufre": "sulphur",
}


# ---------------------------------------------------------------------------
# Leaves
# ---------------------------------------------------------------------------


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (float, np.floating)):
        return math.isnan(float(value)) or math.isinf(float(value))
    return False


def _num(value: Any) -> float | None:
    """A float for JSON, or None. Never NaN, never Infinity, never a numpy type."""
    if _is_missing(value):
        return None
    out = round(float(value), ROUND_DP)
    return 0.0 if out == 0.0 else out  # no negative zero in a file


def _int(value: Any) -> int | None:
    return None if _is_missing(value) else int(value)


def _iso(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def month_label(iso: str) -> str:
    stamp = pd.Timestamp(iso)
    return "%s %d" % (MONTH_NAMES[stamp.month - 1], stamp.year)


def day_label(iso: str) -> str:
    stamp = pd.Timestamp(iso)
    return "%d %s %d" % (stamp.day, MONTH_NAMES[stamp.month - 1], stamp.year)


def utc_label(timestamp: str) -> str:
    stamp = pd.Timestamp(timestamp)
    return "%s at %02d:%02d UTC" % (day_label(stamp.strftime("%Y-%m-%d")), stamp.hour, stamp.minute)


# Segments. A sentence is a list of these and nothing else.


def T(text: str) -> Mapping[str, Any]:
    """Words. Never a figure: tests/test_export.py asserts there is no digit."""
    return {"text": text}


def N(field: str, value: Any, fmt: str, signed: bool = False) -> Mapping[str, Any]:
    """A number, named by the field it came from, formatted by DECIMALS[fmt]."""
    if fmt not in DECIMALS:
        raise KeyError("no decimals declared for format %r" % fmt)
    number = _num(value)
    if fmt in INTEGER_FORMATS and number is not None:
        number = int(round(number))
    out = {"field": field, "value": number, "format": fmt}
    if signed:
        out["signed"] = True
    return out


def D(field: str, iso: str, kind: str = "month") -> Mapping[str, Any]:
    """A date, ISO for the machine and a label for the sentence."""
    label = month_label(iso) if kind == "month" else day_label(iso)
    return {"field": field, "value": iso, "label": label}


def W(field: str, word: str) -> Mapping[str, Any]:
    """A word that is data: a status, a verdict, a product name."""
    return {"field": field, "value": word, "label": word}


def _header(artifact: str, data_date: str, describes: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": artifact,
        "generated_by": GENERATED_BY,
        "data_date": data_date,
        "describes": describes,
        "source": "the committed caches in data/cache and data/seed and the manifest, nothing from data/private; no network",
    }


def _conventions() -> Mapping[str, Any]:
    return {
        "missing": "A missing value is JSON null. null never means zero and is never drawn as zero or bridged; the page shows a gap and says why.",
        "decimals": dict(DECIMALS),
        "rounding": "Floats are stored to %d places. The page prints the decimals of the format a value names." % ROUND_DP,
        "segments": "A sentence is a list of segments. A text segment holds words only. A value segment names its field and holds a value with a format, or an ISO date or a word with its label.",
    }


# ---------------------------------------------------------------------------
# The inputs, computed once per build
# ---------------------------------------------------------------------------


class Inputs:
    """Everything the five artifacts read, computed once, lazily."""

    def __init__(self, replications: int = analysis.BOOTSTRAP_REPLICATIONS):
        self.replications = replications
        self._cache: dict[str, Any] = {}

    def _get(self, key: str, make: Callable[[], Any]) -> Any:
        if key not in self._cache:
            self._cache[key] = make()
        return self._cache[key]

    @property
    def manifest(self) -> Mapping[str, Any]:
        def make():
            with (DATA / "manifest.json").open("r", encoding="utf-8") as handle:
                return json.load(handle)
        return self._get("manifest", make)

    def entry(self, name: str) -> Mapping[str, Any]:
        for item in self.manifest["series"]:
            if item["series"] == name:
                return item
        raise KeyError("no manifest entry for %r" % name)

    @property
    def view(self) -> series.LatestView:
        return self._get("view", series.latest_view)

    @property
    def margin(self) -> pd.DataFrame:
        return self._get("margin", analysis.margin_frame)

    @property
    def frame(self) -> pd.DataFrame:
        return self._get(
            "frame",
            lambda: analysis.analysis_frame(
                analysis.CAPACITY_BEYOND_HELD_FLAT, analysis.CAPACITY_STEP
            ),
        )

    @property
    def threshold(self) -> analysis.ThresholdResult:
        return self._get(
            "threshold",
            lambda: analysis.run_cut_threshold(
                frame=self.frame, replications=self.replications
            ),
        )

    @property
    def threshold_without_stretch(self) -> analysis.ThresholdResult:
        def make():
            th = self.threshold
            stretch = [
                m for m in th.months_below
                if th.longest_run_first <= m <= th.longest_run_last
            ]
            return analysis.run_cut_threshold(
                frame=self.frame,
                replications=self.replications,
                drop_months=stretch,
                dropped_label="the estimated stretch",
            )
        return self._get("threshold_without_stretch", make)

    @property
    def capacity_model(self) -> analysis.ResponseModel:
        return self._get(
            "capacity_model",
            lambda: analysis.margin_response(
                frame=self.frame, label="with episodes as regime dummies"
            ),
        )

    @property
    def fallback_model(self) -> analysis.ResponseModel:
        return self._get(
            "fallback_model",
            lambda: analysis.intake_trend_response(
                frame=self.frame, label="trend, month FE, closure steps"
            ),
        )

    @property
    def diagnostic_model(self) -> analysis.ResponseModel:
        return self._get(
            "diagnostic_model",
            lambda: analysis.margin_response(
                frame=self.frame,
                label="diagnostic, utilisation with a trend and closure steps",
                trend=True,
                closure_years=analysis.capacity_step_years(),
            ),
        )

    @property
    def break_result(self) -> analysis.BreakResult:
        return self._get(
            "break",
            lambda: analysis.break_2026(
                frame=analysis.horse_frame(), dependent=analysis.DEPENDENT_CAPACITY
            ),
        )

    @property
    def horse_frame(self) -> pd.DataFrame:
        return self._get("horse_frame", analysis.horse_frame)

    def horse_race(self, dependent: str) -> list[analysis.HorseResult]:
        return self._get("horse_race_" + dependent, lambda: analysis.horse_race(dependent, frame=self.horse_frame))

    @property
    def weekly(self) -> pd.DataFrame:
        def make():
            cracks_frame = series.dgec_weekly_cracks()
            cracks_frame["date"] = pd.to_datetime(cracks_frame["date"])
            quotes = series.load("dgec_note_reconstructed_weekly")
            quotes["date"] = pd.to_datetime(quotes["date"])
            merged = cracks_frame.merge(
                quotes[["date", "n_independent_geometries"]], on="date", how="left"
            )
            printed = printed_weekly_cracks()
            merged = merged.merge(printed, on="date", how="left")
            iso = merged["date"].dt.isocalendar()
            merged["iso_year"] = iso["year"].astype(int)
            merged["iso_week"] = iso["week"].astype(int)
            return merged
        return self._get("weekly", make)


def printed_weekly_cracks() -> pd.DataFrame:
    """The weeks the ministry printed, cracked through the engine like the line.

    Same factors as series.dgec_weekly_cracks: the ICE product factor and the
    note's own Brent factor, config.DGEC_BBL_PER_T_BRENT_NOTE.
    """
    printed = series.load("dgec_note_printed_weekly")
    rows = []
    for _, row in printed.iterrows():
        day = _iso(row["date"])
        crude = engine.Quote(
            float(row["brent_date_usd_t"]), engine.USD_PER_T, day, engine.WEEKLY,
            "Brent date, DGEC note table",
        )
        out = {"date": pd.Timestamp(day)}
        for product, (column, label) in series.DGEC_WEEKLY_COLUMNS.items():
            out["printed_%s_usd_bbl" % product] = engine.crack(
                engine.Quote(float(row[column]), engine.USD_PER_T, day, engine.WEEKLY, label),
                crude,
                product_bbl_per_t=config.PRODUCT_BBL_PER_T[product],
                brent_bbl_per_t=config.DGEC_BBL_PER_T_BRENT_NOTE,
            ).value
        out["printed_note"] = str(row["notes"])
        rows.append(out)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Shared pieces of sentences
# ---------------------------------------------------------------------------


def _trailing_rank(inputs: Inputs) -> Mapping[str, Any]:
    """The rank, not only the percentile. Same window and rule as the engine."""
    view = inputs.view
    margin = series.margin_after_gas_monthly()
    window = series.trailing_window(
        margin, "margin_after_gas_usd_bbl", pd.Timestamp(view.margin_month)
    )
    published = [x for x in window if not _is_missing(x)]
    value = view.margin_after_gas_usd_bbl
    rank = sum(1 for x in published if x <= value)
    start = pd.Timestamp(view.margin_month) - pd.DateOffset(
        months=config.PERCENTILE_WINDOW_MONTHS - 1
    )
    return {
        "percentile_10y": view.percentile_10y,
        "percentile_rank": rank,
        "percentile_months_below": rank - 1,
        "percentile_observations": len(published),
        "percentile_window_months": config.PERCENTILE_WINDOW_MONTHS,
        "percentile_window_first_month": _iso(start),
        "percentile_window_last_month": view.margin_month,
    }


def _rank_clause(rank: Mapping[str, Any], month: str) -> list[Mapping[str, Any]]:
    n = rank["percentile_observations"]
    if rank["percentile_rank"] == n:
        head = [T("the most in the ")]
    elif rank["percentile_rank"] == 1:
        head = [T("the least in the ")]
    else:
        head = [
            T("more than in "),
            N("percentile_months_below", rank["percentile_months_below"], "count"),
            T(" of the "),
        ]
    return head + [
        N("percentile_observations", n, "count"),
        T(" months to "),
        D("margin_month", month),
    ]


def run_verdict(
    threshold: analysis.ThresholdResult,
    without: analysis.ThresholdResult,
    view: series.LatestView,
    rank: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Headroom, or the word unidentified with its reason. Never both.

    SPEC.md section 6.2: when the threshold is unidentified the site shows no
    headroom figure and falls back to the ten year percentile. The headroom
    field is then null and no segment carries a headroom number.

    Identified, the headroom is the one latest_view computes with that
    threshold, so the page and crack.series cannot disagree.
    """
    grid = np.asarray(threshold.grid, dtype=float)
    step = float(grid[1] - grid[0]) if len(grid) > 1 else 0.0
    touches_low = bool(threshold.ci_low <= grid[0] + step)
    touches_high = bool(threshold.ci_high >= grid[-1] - step)
    too_wide = bool(threshold.ci_width > analysis.THRESHOLD_MAX_CI_WIDTH_USD_BBL)
    flips = bool(
        np.sign(threshold.point.slope_below) != np.sign(without.point.slope_below)
    )
    facts = {
        "threshold_identified": bool(threshold.identified),
        "verdict": "identified" if threshold.identified else "unidentified",
        "threshold_point_usd_bbl": _num(threshold.point.threshold),
        "threshold_ci_low_usd_bbl": _num(threshold.ci_low),
        "threshold_ci_high_usd_bbl": _num(threshold.ci_high),
        "threshold_ci_width_usd_bbl": _num(threshold.ci_width),
        "max_ci_width_usd_bbl": _num(analysis.THRESHOLD_MAX_CI_WIDTH_USD_BBL),
        "search_low_usd_bbl": _num(grid[0]),
        "search_high_usd_bbl": _num(grid[-1]),
        "interval_touches_lower_edge": touches_low,
        "interval_touches_upper_edge": touches_high,
        "interval_too_wide": too_wide,
        "slope_below_usd_bbl": _num(threshold.point.slope_below),
        "episode_first_month": threshold.longest_run_first + "-01",
        "episode_last_month": threshold.longest_run_last + "-01",
        "threshold_without_episode_usd_bbl": _num(without.point.threshold),
        "slope_below_without_episode": _num(without.point.slope_below),
        "slope_changes_sign_without_episode": flips,
        "months_below_every_month": len(threshold.months_below),
        "nobs_every_month": int(threshold.nobs),
        "months_below_without_episode": len(without.months_below),
        "nobs_without_episode": int(without.nobs),
        "bootstrap_replications": int(threshold.replications),
        "bootstrap_seed": int(threshold.seed),
        "regressor": "mean of the margin at the average US refinery's gas use over the three previous months",
        "reasons": list(threshold.reasons),
    }

    if threshold.identified:
        with_threshold = series.latest_view(threshold=threshold.point.threshold)
        headroom = with_threshold.headroom_usd_bbl
        facts["headroom_usd_bbl"] = _num(headroom)
        facts["segments"] = [
            T("Runs sit "),
            N("headroom_usd_bbl", headroom, "usd_bbl"),
            T(" $/bbl above the level at which they get cut, estimated at "),
            N("threshold_point_usd_bbl", threshold.point.threshold, "usd_bbl"),
            T(" $/bbl with an interval of "),
            N("threshold_ci_low_usd_bbl", threshold.ci_low, "usd_bbl"),
            T(" to "),
            N("threshold_ci_high_usd_bbl", threshold.ci_high, "usd_bbl"),
            T(" $/bbl."),
        ]
        facts["fallback_segments"] = []
        return facts

    facts["headroom_usd_bbl"] = None
    segments: list[Mapping[str, Any]] = [
        T("Headroom to the level at which runs get cut is "),
        W("verdict", "unidentified"),
        T(". "),
    ]
    interval = [
        N("threshold_ci_low_usd_bbl", threshold.ci_low, "usd_bbl"),
        T(" to "),
        N("threshold_ci_high_usd_bbl", threshold.ci_high, "usd_bbl"),
        T(" $/bbl"),
    ]
    if flips:
        segments += [
            T("Take out "),
            D("episode_first_month", facts["episode_first_month"]),
            T(" to "),
            D("episode_last_month", facts["episode_last_month"]),
            T(" and the estimated kink moves from "),
            N("threshold_point_usd_bbl", threshold.point.threshold, "usd_bbl"),
            T(" to "),
            N("threshold_without_episode_usd_bbl", without.point.threshold, "usd_bbl"),
            T(" $/bbl while the slope below it changes sign, so the kink describes one episode rather than a level; its interval, "),
            *interval,
        ]
        joiner = ", also"
    else:
        segments += [T("Its interval, "), *interval]
        joiner = ","
    tail = []
    if touches_low or touches_high:
        tail.append(T("%s runs to the edge of the range searched" % joiner))
        joiner = ", and"
    if too_wide:
        tail += [
            T("%s is wider than " % joiner),
            N("max_ci_width_usd_bbl", analysis.THRESHOLD_MAX_CI_WIDTH_USD_BBL, "usd_bbl"),
            T(" $/bbl"),
        ]
    segments += tail + [T(".")]
    facts["segments"] = segments
    facts["fallback_segments"] = [
        T("The only reading of today's level this study defends is its rank: "),
        N("mbr_usd_bbl", view.mbr_usd_bbl, "usd_bbl"),
        T(" is "),
        *_rank_clause(rank, view.margin_month),
        T("."),
    ]
    return facts


# ---------------------------------------------------------------------------
# now.json
# ---------------------------------------------------------------------------


def _status_word(entry: Mapping[str, Any], month: str | None = None) -> tuple[bool, str]:
    """Provisional or not, and the word, from the manifest rather than from copy."""
    provisional_from = entry.get("provisional_from")
    last = month or entry.get("last_date")
    provisional = bool(provisional_from) and str(last) >= str(provisional_from)
    if provisional:
        return True, "provisional"
    if entry.get("method") == "reconstructed":
        return False, "reconstructed"
    return False, "final"


def data_dates(inputs: Inputs) -> list[Mapping[str, Any]]:
    """Three dates, never merged: margins, weekly cracks, runs."""
    view = inputs.view
    mbr = inputs.entry("dgec_mbr_monthly")
    quotes = inputs.entry("dgec_note_printed_monthly")
    weekly = inputs.entry("dgec_note_reconstructed_weekly")
    runs = inputs.entry("jodi_nwe_refinery_intake_monthly")

    printed = series.load("dgec_note_printed_monthly")
    printed["date"] = pd.to_datetime(printed["date"])
    quote_row = printed[printed["date"] == pd.Timestamp(view.margin_month)]
    quotes_provisional = (
        None if quote_row.empty
        else str(quote_row["provisional"].iloc[0]).strip().lower() == "true"
    )
    quotes_vintage = None if quote_row.empty else str(quote_row["vintage"].iloc[0])

    mbr_provisional, mbr_word = _status_word(mbr, view.margin_month)
    margins_provisional = bool(mbr_provisional or quotes_provisional)
    margins_word = "provisional" if margins_provisional else mbr_word

    margins_segments = [
        T("Margins run to "),
        D("date", view.margin_month),
        T(" and are "),
        W("status_word", margins_word),
    ]
    if quotes_vintage is not None:
        margins_segments += [
            T("; the monthly prices that split them are "),
            W("quotations_status_word", "provisional" if quotes_provisional else "final"),
            T(" in the ministry's note of "),
            D("quotations_vintage", quotes_vintage, kind="day"),
            T("."),
        ]
    else:
        margins_segments += [T("; no note has printed the monthly prices that would split it.")]

    weekly_provisional, weekly_word = _status_word(weekly)
    weekly_date = view.weekly_crack_data_date
    runs_provisional, runs_word = _status_word(runs, view.runs_data_date)
    runs_segments = [
        T("Refinery runs stop at "),
        D("date", view.runs_data_date),
        T(" and are "),
        W("status_word", runs_word),
        T("; JODI revises recent months." if runs_provisional else "."),
    ]
    return [
        {
            "id": "margins",
            "date": view.margin_month,
            "label": month_label(view.margin_month),
            "provisional": margins_provisional,
            "status_word": margins_word,
            "fetch_status": mbr["status"],
            "vintage": mbr["vintage"],
            "quotations_vintage": quotes_vintage,
            "quotations_provisional": quotes_provisional,
            "fetched_at": mbr["fetched_at"],
            "series": ["dgec_mbr_monthly", "dgec_note_printed_monthly", "dgec_brent_monthly"],
            "segments": margins_segments,
        },
        {
            "id": "weekly_cracks",
            "date": weekly_date,
            "label": day_label(weekly_date),
            "provisional": weekly_provisional,
            "status_word": weekly_word,
            "fetch_status": weekly["status"],
            "vintage": weekly["vintage"],
            "fetched_at": weekly["fetched_at"],
            "series": ["dgec_note_reconstructed_weekly", "dgec_note_printed_weekly"],
            "segments": [
                T("Weekly cracks run to the week of "),
                D("date", weekly_date, kind="day"),
                T(", read off the ministry's weekly chart; last fetched on "),
                {"field": "fetched_at", "value": weekly["fetched_at"], "label": utc_label(weekly["fetched_at"])},
                T("."),
            ],
        },
        {
            "id": "runs",
            "date": view.runs_data_date,
            "label": month_label(view.runs_data_date),
            "provisional": runs_provisional,
            "status_word": runs_word,
            "fetch_status": runs["status"],
            "vintage": runs["vintage"],
            "fetched_at": runs["fetched_at"],
            "series": ["jodi_nwe_refinery_intake_monthly"],
            "segments": runs_segments,
        },
    ]


def verdict_values(inputs: Inputs) -> dict[str, Any]:
    view = inputs.view
    rank = _trailing_rank(inputs)
    margin = inputs.margin
    row = margin[margin["date"] == pd.Timestamp(view.margin_month)].iloc[0]
    decomposition = view.margin_decomposition
    carrier = view.margin_carrier
    values: dict[str, Any] = {
        "margin_month": view.margin_month,
        "mbr_usd_bbl": _num(view.mbr_usd_bbl),
        "margin_after_gas_usd_bbl": _num(view.margin_after_gas_usd_bbl),
        "margin_basis": engine.MARGIN_NET_OF_GAS,
        "net_of": {
            "gas": True,
            "embedded_gas_intensity_mmbtu_per_bbl": _num(config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL),
            "embedded_gas_mass_yield_percent": _num(100 * config.DGEC_MASS_YIELDS["gaz_naturel"]),
            "costs_subtracted": ["Brent date", "purchased natural gas", "crude freight", "insurance and losses"],
            "costs_not_subtracted": "every cost of refining other than energy, which the ministry's note says the profession does not value the same way",
            "other_variable_cost_usd_bbl": _num(config.OTHER_VARIABLE_COST_USD_BBL),
            "source": config.DGEC_METHOD_URL,
        },
        **{k: (_num(v) if isinstance(v, float) else v) for k, v in rank.items()},
        "gas_usd_mmbtu": _num(view.gas_usd_mmbtu),
        "study_gas_intensity_mmbtu_per_bbl": _num(config.GAS_INTENSITY_MMBTU_PER_BBL),
        "gas_wedge_usd_bbl": _num(view.gas_wedge.wedge_usd_bbl),
        "margin_study_intensity_usd_bbl": _num(row[analysis.MARGIN_STUDY_INTENSITY]),
        "intensity_ratio": _num(view.gas_wedge.ratio),
        "crack_month": view.margin_month if decomposition is not None else None,
        "carrier": carrier,
        "carrier_name": None if carrier is None else PRODUCT_NAMES[carrier],
        "carrier_label": None if carrier is None else series.DGEC_NOTE_MONTHLY_COLUMNS[carrier][1],
        "carrier_contribution_usd_bbl": None if decomposition is None else _num(decomposition.carrier_contribution_usd_bbl),
        "carrier_reason": view.margin_decomposition_reason or None,
    }
    return values


def _verdict_rank_clause(rank: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """The rank clause of the verdict, without the month: the verdict says the
    month once, in its first clause, and the trailing window ends there. The
    fallback paragraph keeps _rank_clause, which names the month."""
    n = rank["percentile_observations"]
    if rank["percentile_rank"] == n:
        head = [T("the most in ")]
    elif rank["percentile_rank"] == 1:
        head = [T("the least in ")]
    else:
        head = [
            T("more than in "),
            N("percentile_months_below", rank["percentile_months_below"], "count"),
            T(" of "),
        ]
    return head + [N("percentile_observations", n, "count"), T(" months")]


def verdict_segments(values: Mapping[str, Any], run: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """One sentence a trader would say out loud, SPEC.md section 7.2, in four
    clauses: refiners' gross margin after gas this month, where that sits in
    ten years, which crack carried it, and whether runs have room to rise.

    The month is said once. "Gross margin" and not "kept": the MBR nets out
    crude, the gas the method buys, freight and insurance, and no other cost of
    refining, so it is not what a refiner keeps. "The ministry's gas allowance"
    and not "its own": the gas is the method's embedded intensity, and "its"
    read as the refiner's. The same barrel at the average US refinery's gas
    use, and the ratio of the two intensities, are said in the "Refining margin
    and gas" section, where the wedge is drawn (margin-stack.json
    study_margin_segments). docs/design.md Part 7, C9 and C10."""
    month = values["margin_month"]
    out: list[Mapping[str, Any]] = [
        T("On the ministry's Rotterdam measure, refiners' gross margin after the ministry's gas allowance was "),
        N("mbr_usd_bbl", values["mbr_usd_bbl"], "usd_bbl"),
        T(" $/bbl in "),
        D("margin_month", month),
        T(", "),
        *_verdict_rank_clause(values),
        T("; "),
    ]
    if values["carrier"] is not None:
        out += [
            W("carrier_name", values["carrier_name"]),
            T(" carried "),
            N("carrier_contribution_usd_bbl", values["carrier_contribution_usd_bbl"], "usd_bbl"),
            T(" of it"),
        ]
        if values["crack_month"] != month:
            # Never today (Part 7, C1), but a split from another month is named.
            out += [T(" on the prices of "), D("crack_month", values["crack_month"])]
        out += [T(", ")]
    else:
        out += [T("no product split of that month says which crack carried it, ")]
    if run["threshold_identified"]:
        out += [
            T("and runs sit "),
            N("headroom_usd_bbl", run["headroom_usd_bbl"], "usd_bbl"),
            T(" $/bbl above the level at which they get cut."),
        ]
    else:
        out += [T("and this sample cannot say whether runs have room to rise.")]
    return out


def now(inputs: Inputs) -> Mapping[str, Any]:
    view = inputs.view
    values = verdict_values(inputs)
    run = run_verdict(inputs.threshold, inputs.threshold_without_stretch, view, values)
    values["threshold_identified"] = run["threshold_identified"]
    values["headroom_usd_bbl"] = run["headroom_usd_bbl"]
    values["run_verdict"] = run["verdict"]
    payload = _header("now", view.margin_month, "the landing sentence and the three data dates")
    payload["conventions"] = _conventions()
    payload["verdict"] = {
        "values": values,
        "segments": verdict_segments(values, run),
        "headroom_segments": run["segments"],
        "fallback_segments": run["fallback_segments"],
    }
    payload["data_dates"] = data_dates(inputs)
    payload["sections"] = section_summaries(inputs, values, run)
    return payload


def section_summaries(inputs: Inputs, values: Mapping[str, Any], run: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    latest = latest_week(inputs)
    # When the ministry printed the latest week, the sentence leads with the
    # printed figures and gives the chart reading second, because a reader
    # holding the note sees the printed ones. The comparison with earlier years
    # stays the chart reading's, because the earlier years are chart readings
    # too. docs/design.md Part 7, C11.
    printed = [latest["products"][p]["point"]["printed_usd_bbl"] for p in ("gasoil", "gasoline")]
    crack_segments: list[Mapping[str, Any]] = []
    if all(x is not None for x in printed):
        crack_segments += [
            T("Gasoil "),
            N("gasoil_printed_usd_bbl", printed[0], "usd_bbl"),
            T(" and gasoline "),
            N("gasoline_printed_usd_bbl", printed[1], "usd_bbl"),
            T(" $/bbl in the week to "),
            D("weekly_date", latest["date"], kind="day"),
            T(" as the ministry's note printed them, and "),
            N("gasoil_usd_bbl", latest["products"]["gasoil"]["value_usd_bbl"], "usd_bbl"),
            T(" and "),
            N("gasoline_usd_bbl", latest["products"]["gasoline"]["value_usd_bbl"], "usd_bbl"),
            T(" read off its weekly chart; "),
        ]
    else:
        for i, product in enumerate(("gasoil", "gasoline")):
            info = latest["products"][product]
            crack_segments += [
                T("Gasoil " if i == 0 else " and gasoline "),
                N("%s_usd_bbl" % product, info["value_usd_bbl"], "usd_bbl"),
            ]
        crack_segments += [
            T(" $/bbl in the week to "),
            D("weekly_date", latest["date"], kind="day"),
            T(", read off the ministry's weekly chart; "),
        ]
    positions = {p: latest["products"][p]["position"] for p in ("gasoil", "gasoline")}
    words = {"above": "above", "inside": "inside the range of", "below": "below", "none": "with nothing to compare against in"}
    if positions["gasoil"] == positions["gasoline"]:
        crack_segments += [T("both " + words[positions["gasoil"]] + " the same week in each of the ")]
    else:
        crack_segments += [
            T("gasoil " + words[positions["gasoil"]] + " and gasoline " + words[positions["gasoline"]] + " the same week in each of the "),
        ]
    crack_segments += [
        N("n_years", latest["n_years"], "count"),
        T(" years the weekly series covers."),
    ]

    margin_segments = [
        T("How the cracks build the ministry's NWE refining margin in "),
        D("margin_month", values["margin_month"]),
    ]
    if values["carrier"] is not None:
        margin_segments += [T(", on the ministry's own prices for that month, and what it is worth at the average US refinery's gas use.")]
    else:
        margin_segments += [T(", and what it is worth at the average US refinery's gas use.")]

    cap, fall = inputs.capacity_model, inputs.fallback_model
    run_segments: list[Mapping[str, Any]] = []
    if run["threshold_identified"]:
        run_segments += [T("Runs sit "), N("headroom_usd_bbl", run["headroom_usd_bbl"], "usd_bbl"), T(" $/bbl above the level at which they get cut. ")]
    else:
        run_segments += [T("No level at which runs get cut can be identified. ")]
    run_segments += [
        T("Crude runs move "),
        N("capacity_kb_d", cap.translation.kb_d, "kb_d", signed=True),
        T(" kb/d per "),
        N("move_usd_bbl", cap.translation.move_usd_bbl, "count"),
        T(" $/bbl of margin on the planned model, t "),
        N("capacity_t", cap.sum_b_t, "t", signed=True),
        T(", and "),
        N("fallback_kb_d", fall.translation.kb_d, "kb_d", signed=True),
        T(" on a model with a trend, t "),
        N("fallback_t", fall.sum_b_t, "t", signed=True),
        T("."),
    ]

    manifest = inputs.manifest
    entries = manifest["series"]
    bad = [e for e in entries if e["status"] in ("failed", "stale")]
    fetched = sorted(e["fetched_at"] for e in entries if e.get("fetched_at") and e.get("machine_fetched"))
    last_fetch = fetched[-1]
    outstanding = [s for s in manifest["manual_steps"] if s.get("status") == "outstanding"]
    provenance_segments: list[Mapping[str, Any]] = []
    if bad:
        provenance_segments += [N("series_failed_or_stale", len(bad), "count"), T(" of "), N("series_count", len(entries), "count"), T(" series failed or went stale")]
    else:
        provenance_segments += [T("None of the "), N("series_count", len(entries), "count"), T(" series failed or went stale")]
    provenance_segments += [
        T(" at the last fetch, "),
        {"field": "last_fetched_at", "value": last_fetch, "label": utc_label(last_fetch)},
    ]
    if outstanding:
        provenance_segments += [
            T("; "),
            N("manual_steps_outstanding", len(outstanding), "count"),
            T(" manual step is outstanding: the OPEC archive stops, so the monthly OPEC history of the cracks ends at "
              if len(outstanding) == 1 and outstanding[0]["id"] == "momr_unarchived_2026"
              else " manual steps are outstanding, listed below."),
        ]
        if len(outstanding) == 1 and outstanding[0]["id"] == "momr_unarchived_2026":
            opec = inputs.entry("opec_rotterdam_products_monthly")
            provenance_segments += [D("opec_last_date", opec["last_date"]), T(".")]
    else:
        provenance_segments += [T("; no manual step is outstanding.")]

    return [
        {"id": "cracks", "name": "Gasoil and gasoline cracks", "artifact": "data/cracks.json", "summary_segments": crack_segments},
        {"id": "margin", "name": "Refining margin and gas", "artifact": "data/margin-stack.json", "summary_segments": margin_segments},
        {"id": "runs", "name": "Run economics and crude demand", "artifact": "data/run-economics.json", "summary_segments": run_segments},
        {"id": "provenance", "name": "Provenance", "artifact": "data/provenance.json", "summary_segments": provenance_segments},
    ]


# ---------------------------------------------------------------------------
# cracks.json
# ---------------------------------------------------------------------------

WEEKLY_COLUMNS = {"gasoil": analysis.CRACK_GASOIL, "gasoline": analysis.CRACK_GASOLINE}


def latest_week(inputs: Inputs) -> Mapping[str, Any]:
    weekly = inputs.weekly
    last = weekly.iloc[-1]
    year, week = int(last["iso_year"]), int(last["iso_week"])
    products = {}
    n_years = None
    for product, column in WEEKLY_COLUMNS.items():
        table = analysis.seasonal_weekly(column)
        row = table[table["week"] == week].iloc[0]
        prior = weekly[(weekly["iso_week"] == week) & (weekly["iso_year"].isin(table.attrs["years_used"]))]
        prior = prior.dropna(subset=[column])
        points = [_point(r, column, product) for _, r in prior.iterrows()]
        value = float(last[column])
        if int(row["n_years"]) == 0:
            position = "none"
        elif value > float(row["maximum"]):
            position = "above"
        elif value < float(row["minimum"]):
            position = "below"
        else:
            position = "inside"
        n_years = int(row["n_years"])
        products[product] = {
            "value_usd_bbl": _num(value),
            "label": series.DGEC_WEEKLY_COLUMNS[product][1],
            "point": _point(last, column, product),
            "prior_minimum_usd_bbl": _num(row["minimum"]),
            "prior_maximum_usd_bbl": _num(row["maximum"]),
            "above_prior_maximum_usd_bbl": _num(value - float(row["maximum"])) if n_years else None,
            "position": position,
            "prior_years": points,
        }
    date = _iso(last["date"])
    for product, info in products.items():
        info["heading_segments"] = _panel_heading(product, info, date, n_years)
        info["desc_segments"] = _panel_desc(product, info, date, year)
    return {"date": date, "iso_year": year, "iso_week": week, "n_years": n_years, "products": products}


def _panel_heading(product: str, info: Mapping[str, Any], date: str, n_years: int | None) -> list[Mapping[str, Any]]:
    """The seasonal panel's sentence heading, docs/design.md Part 3 section 3:
    the figure, that it is read off the chart, and how far it sits from the
    range of the prior years, with how many years that range holds."""
    name = PRODUCT_NAMES[product]
    printed = info["point"]["printed_usd_bbl"]
    if printed is not None:
        # The printed figure first, the chart reading second (Part 7, C11).
        out = [
            T(name[:1].upper() + name[1:] + ", "),
            N("%s_printed_usd_bbl" % product, printed, "usd_bbl"),
            T(" $/bbl in the week to "),
            D("weekly_date", date, kind="day"),
            T(" as the ministry's note printed it; read off the ministry's chart, "),
            N("%s_usd_bbl" % product, info["value_usd_bbl"], "usd_bbl"),
            T(", "),
        ]
    else:
        out = [
            T(name[:1].upper() + name[1:] + ", "),
            N("%s_usd_bbl" % product, info["value_usd_bbl"], "usd_bbl"),
            T(" $/bbl in the week to "),
            D("weekly_date", date, kind="day"),
            T(", read off the ministry's chart, "),
        ]
    position = info["position"]
    if position == "above":
        out += [N("above_prior_maximum_usd_bbl", info["above_prior_maximum_usd_bbl"], "usd_bbl"), T(" above the highest same week of the ")]
    elif position == "below":
        out += [N("below_prior_minimum_usd_bbl", info["prior_minimum_usd_bbl"] - info["value_usd_bbl"], "usd_bbl"), T(" below the lowest same week of the ")]
    elif position == "inside":
        out += [T("inside the range of the same week in the ")]
    else:
        return out + [T("with no earlier year to set it against.")]
    return out + [N("n_years", n_years, "count"), T(" years before it.")]


def _panel_desc(product: str, info: Mapping[str, Any], date: str, year: int) -> list[Mapping[str, Any]]:
    """The seasonal panel's SVG description, docs/design.md Part 3 section 9."""
    points = info["prior_years"]
    out = [
        T(PRODUCT_NAMES[product][:1].upper() + PRODUCT_NAMES[product][1:] + " crack by week of the year, "),
        N("current_year", year, "year"),
    ]
    if points:
        out += [T(" against "), N("first_prior_year", points[0]["year"], "year"), T(" to "), N("last_prior_year", points[-1]["year"], "year")]
    out += [
        T(", one line per year. Latest "),
        N("%s_usd_bbl" % product, info["value_usd_bbl"], "usd_bbl"),
        T(" $/bbl in the week to "),
        D("weekly_date", date, kind="day"),
    ]
    if info["position"] in ("above", "below", "inside"):
        out += [
            T(", against a range for that week of "),
            N("prior_minimum_usd_bbl", info["prior_minimum_usd_bbl"], "usd_bbl"),
            T(" to "),
            N("prior_maximum_usd_bbl", info["prior_maximum_usd_bbl"], "usd_bbl"),
        ]
    return out + [T(". Squares are figures the ministry printed; a hatch under the axis marks the least defended weeks, a bracket the weeks with no second chart yet.")]


def _point(row: pd.Series, column: str, product: str) -> Mapping[str, Any]:
    printed = row.get("printed_%s_usd_bbl" % product)
    evidence = row.get("evidence_class")
    return {
        "date": _iso(row["date"]),
        "year": int(row["iso_year"]),
        "week": int(row["iso_week"]),
        "value_usd_bbl": _num(row[column]),
        "evidence": "printed" if not _is_missing(printed) else "reconstructed",
        "printed_usd_bbl": _num(printed),
        "evidence_class": None if _is_missing(evidence) else str(evidence),
        "cross_checked": bool(row.get("cross_checked")) if not _is_missing(row.get("cross_checked")) else None,
        "n_independent_geometries": _int(row.get("n_independent_geometries")),
        "least_defended": str(evidence) == "single_geometry_oldest",
    }


def cracks(inputs: Inputs) -> Mapping[str, Any]:
    weekly = inputs.weekly
    latest = latest_week(inputs)
    payload = _header("cracks", latest["date"], "the latest weekly gasoil and gasoline cracks against the same week of every prior year the weekly series holds")
    payload["conventions"] = _conventions()
    payload["latest"] = latest
    panels = {}
    for product, column in WEEKLY_COLUMNS.items():
        table = analysis.seasonal_weekly(column)
        years = list(table.attrs["years_used"])
        current_year = int(table.attrs["current_year"])
        by = weekly.set_index(["iso_year", "iso_week"])
        rows = []
        for _, r in table.iterrows():
            week = int(r["week"])
            values, evidence, printed = [], [], []
            for year in years + [current_year]:
                key = (year, week)
                if key in by.index and not _is_missing(by.loc[key, column]):
                    cell = by.loc[key]
                    values.append(_num(cell[column]))
                    evidence.append(str(cell["evidence_class"]))
                    printed.append(_num(cell.get("printed_%s_usd_bbl" % product)))
                else:
                    values.append(None)
                    evidence.append(None)
                    printed.append(None)
            rows.append([week, int(r["n_years"]), _num(r["minimum"]), _num(r["maximum"]), values, evidence, printed])
        panels[product] = {
            "label": series.DGEC_WEEKLY_COLUMNS[product][1],
            "name": PRODUCT_NAMES[product],
            "unit": "USD per barrel",
            "line_style": "solid" if product == "gasoil" else "dashed",
            "prior_years": years,
            "current_year": current_year,
            "episode_years_in_range": [y for y in analysis.SEASONAL_REMOVABLE_YEARS if y in years],
            "columns": ["week", "n_years", "prior_minimum_usd_bbl", "prior_maximum_usd_bbl", "values_by_year", "evidence_class_by_year", "printed_usd_bbl_by_year"],
            "year_order": years + [current_year],
            "weeks": rows,
        }
    payload["panels"] = panels
    first = _iso(weekly["date"].min())
    payload["series_note"] = {
        "first_week": first,
        "weeks": int(len(weekly)),
        "printed_weeks": int(weekly["printed_gasoil_usd_bbl"].notna().sum()),
        "evidence_class_counts": {k: int(v) for k, v in sorted(weekly["evidence_class"].value_counts().items())},
        "least_defended_class": "single_geometry_oldest",
        "factors": {
            "gasoil_bbl_per_t": config.BBL_PER_T_GASOIL,
            "gasoline_bbl_per_t": config.BBL_PER_T_GASOLINE,
            "brent_bbl_per_t": config.DGEC_BBL_PER_T_BRENT_NOTE,
        },
        "segments": [
            T("Lines are read off the ministry's weekly chart from "),
            D("first_week", first, kind="day"),
            T(", so only "),
            N("n_years", latest["n_years"], "count"),
            T(" prior years exist for this week and this is not a five year range; squares are figures the ministry printed."),
        ],
    }
    return payload


# ---------------------------------------------------------------------------
# margin-stack.json
# ---------------------------------------------------------------------------


def _ladder_ceiling(x: float) -> float:
    """The next 1, 2, 5 step at or beyond |x|, signed. For the shared scale."""
    if x == 0.0:
        return 0.0
    magnitude = 10 ** math.floor(math.log10(abs(x)))
    for step in (1, 2, 5, 10):
        if step * magnitude >= abs(x) - 1e-12:
            return math.copysign(step * magnitude, x)
    return math.copysign(10 * magnitude, x)


def margin_stack(inputs: Inputs) -> Mapping[str, Any]:
    view = inputs.view
    month = view.margin_month
    payload = _header("margin-stack", month, "the waterfall from product contributions to the ministry's margin, then the gas wedge to the margin at this study's gas intensity")
    payload["conventions"] = _conventions()
    decomposition = view.margin_decomposition
    wedge = view.gas_wedge
    rows: list[Mapping[str, Any]] = []
    running = 0.0

    def step(row_id, kind, value, **extra):
        nonlocal running
        start = running
        running = start + value
        rows.append({"id": row_id, "kind": kind, "value_usd_bbl": _num(value), "start_usd_bbl": _num(start), "end_usd_bbl": _num(running), **extra})

    if decomposition is not None:
        printed = series.load("dgec_note_printed_monthly")
        printed["date"] = pd.to_datetime(printed["date"])
        quote = printed[printed["date"] == pd.Timestamp(month)].iloc[0]
        order = sorted(decomposition.contributions, key=lambda p: -decomposition.contributions[p])
        for product in order:
            crack = view.margin_cracks[product]
            column, label = series.DGEC_NOTE_MONTHLY_COLUMNS[product]
            step(
                product, "step", decomposition.contributions[product],
                name=PRODUCT_NAMES[product],
                label=label,
                price_usd_t=_num(quote[column]),
                bbl_per_t=config.DGEC_NOTE_PRODUCT_BBL_PER_T[product],
                factor_citation=dict(FACTOR_CITATIONS[product]),
                product_usd_bbl=_num(crack.product_usd_bbl),
                brent_usd_bbl=_num(crack.brent_usd_bbl),
                crack_usd_bbl=_num(crack.value),
                slate_line=config.DGEC_NOTE_SLATE_LINE[product],
                mass_yield_percent=_num(100 * config.DGEC_MASS_YIELDS[config.DGEC_NOTE_SLATE_LINE[product]]),
                volume_yield=_num(series.DGEC_NOTE_VOLUME_YIELDS[product]),
                carrier=product == decomposition.carrier,
                detail_segments=[
                    T("The "),
                    W("label", label),
                    T(" quotation less Brent, "),
                    N("crack_usd_bbl", crack.value, "usd_bbl", signed=True),
                    T(" $/bbl, on "),
                    N("volume_yield_percent", 100 * series.DGEC_NOTE_VOLUME_YIELDS[product], "percent"),
                    T(" percent of the barrel by volume"),
                ],
            )
        unattributed = [
            {"slate_line": line, "name": SLATE_LINE_NAMES[line], "mass_yield_percent": _num(100 * config.DGEC_MASS_YIELDS[line])}
            for line in decomposition.unattributed_products
        ]
        step(
            "residual", "step", decomposition.residual_usd_bbl,
            name="everything the cracks do not price",
            contains={
                "slate_lines": unattributed,
                "unattributed_mass_yield_percent": _num(sum(100 * config.DGEC_MASS_YIELDS[l] for l in decomposition.unattributed_products)),
                "method_costs": ["purchased natural gas", "crude freight, Sullom Voe to Le Havre", "insurance and losses"],
                "approximations": [
                    "the gasoline line prices the method's EuroBOB yield with the ministry's Eurosuper quotation, a finished gasoline and a different product",
                    "each product converts to barrels at an ICE contract factor, a settlement convention and not the density of the cargo the ministry quotes",
                ],
            },
            covered_volume_yield=_num(decomposition.covered_volume_yield),
            residual_share=_num(decomposition.residual_share),
        )
    else:
        step("residual", "step", view.mbr_usd_bbl, name="everything the cracks do not price", contains={"reason": view.margin_decomposition_reason})

    rows.append({"id": "official_margin", "kind": "total", "value_usd_bbl": _num(view.mbr_usd_bbl), "start_usd_bbl": 0.0, "end_usd_bbl": _num(view.mbr_usd_bbl), "name": "official margin, the ministry's MBR", "accent": True})
    running = view.mbr_usd_bbl
    step(
        "gas_wedge", "step", -wedge.wedge_usd_bbl,
        name="extra gas at the average US refinery's use",
        gas_usd_mmbtu=_num(wedge.gas_usd_mmbtu),
        gas_source="World Bank Commodity Price Data (The Pink Sheet), natural gas, Europe",
        embedded_intensity_mmbtu_per_bbl=_num(wedge.embedded_intensity_mmbtu_per_bbl),
        study_intensity_mmbtu_per_bbl=_num(wedge.study_intensity_mmbtu_per_bbl),
        embedded_cost_usd_bbl=_num(wedge.embedded_cost_usd_bbl),
        study_cost_usd_bbl=_num(wedge.study_cost_usd_bbl),
        intensity_ratio=_num(wedge.ratio),
    )
    rows.append({"id": "margin_study_intensity", "kind": "total", "value_usd_bbl": _num(running), "start_usd_bbl": 0.0, "end_usd_bbl": _num(running), "name": "at that gas use", "accent": False})

    ends = [0.0] + [r["start_usd_bbl"] for r in rows] + [r["end_usd_bbl"] for r in rows]
    low, high = min(ends), max(ends)
    scale_low = min(0.0, _ladder_ceiling(low))
    scale_high = max(0.0, _ladder_ceiling(high))
    # Ladder values are said as whole dollars when they are whole: "0 to 50",
    # not "0.00 to 50.00", a scale said to the cent (Part 7, C14).
    scale_format = "count" if float(scale_low).is_integer() and float(scale_high).is_integer() else "usd_bbl"
    payload["month"] = month
    payload["month_label"] = month_label(month)
    payload["decomposed"] = decomposition is not None
    payload["rows"] = rows
    payload["scale"] = {
        "low_usd_bbl": _num(scale_low),
        "high_usd_bbl": _num(scale_high),
        "includes_zero": True,
        "segments": [
            T("On one scale, "),
            N("low_usd_bbl", scale_low, scale_format),
            T(" to "),
            N("high_usd_bbl", scale_high, scale_format),
            T(" $/bbl, "),
            D("margin_month", month),
            T("."),
        ],
    }

    history = series.note_decomposition_history()
    done = history[history["decomposed"]]
    payload["residual_history"] = {
        "months": [
            {"month": _iso(r["date"]), "residual_usd_bbl": _num(r["residual_usd_bbl"]), "official_usd_bbl": _num(r["official_usd_bbl"]), "carrier": r["carrier"], "quotations_vintage": r["vintage"]}
            for _, r in done.iterrows()
        ],
        "not_decomposed": [
            {"month": _iso(r["date"]), "reason": r["reason"]}
            for _, r in history[~history["decomposed"]].iterrows()
        ],
        "negative": int((done["residual_usd_bbl"] < 0).sum()),
        "decomposed": int(len(done)),
        "segments": [
            T("On the ministry's own monthly prices this line has been negative in "),
            N("negative", int((done["residual_usd_bbl"] < 0).sum()), "count"),
            T(" of the "),
            N("decomposed", int(len(done)), "count"),
            T(" months a note printed final prices for."),
        ],
    }
    payload["residual_segments"] = [] if decomposition is None else [
        T("The cracks cover "),
        N("covered_volume_yield_percent", 100 * decomposition.covered_volume_yield, "percent"),
        T(" percent of the barrel; everything else, and the ministry's gas, freight and insurance costs, adds up to this line."),
    ]
    payload["wedge_segments"] = [
        N("study_intensity_mmbtu_per_bbl", wedge.study_intensity_mmbtu_per_bbl, "mmbtu_per_bbl"),
        T(" MMBtu/bbl here against the ministry's "),
        N("embedded_intensity_mmbtu_per_bbl", wedge.embedded_intensity_mmbtu_per_bbl, "mmbtu_per_bbl"),
        T(", "),
        N("intensity_ratio", wedge.ratio, "ratio"),
        T(" times as much, at "),
        N("gas_usd_mmbtu", wedge.gas_usd_mmbtu, "usd_mmbtu"),
        T(" $/MMBtu."),
    ]
    # The figure the verdict used to carry, docs/design.md Part 7, C9: the same
    # barrel at the average US refinery's gas use, said where the wedge is drawn.
    payload["study_margin_segments"] = [
        T("At the average US refinery's gas use, "),
        N("intensity_ratio", wedge.ratio, "ratio"),
        T(" times the ministry's, the same barrel's gross margin would have been "),
        N("margin_study_intensity_usd_bbl", running, "usd_bbl"),
        T(" $/bbl in "),
        D("margin_month", month),
        T(" rather than "),
        N("mbr_usd_bbl", view.mbr_usd_bbl, "usd_bbl"),
        T("; the gap is the extra gas, "),
        N("gas_wedge_usd_bbl", -wedge.wedge_usd_bbl, "usd_bbl", signed=True),
        T(" $/bbl."),
    ]
    return payload


# ---------------------------------------------------------------------------
# run-economics.json
# ---------------------------------------------------------------------------


def _model_row(model: analysis.ResponseModel, model_id: str, label: str, equation: str, step_years: Sequence[int] = ()) -> Mapping[str, Any]:
    t = model.translation
    low, high = t.kb_d_low, t.kb_d_high
    width = high - low
    return {
        "id": model_id,
        "label": label,
        "equation": equation,
        "closure_step_years_in_sample": list(step_years),
        "dependent": model.dependent,
        "regressor": model.regressor,
        "kb_d": _num(t.kb_d),
        "kb_d_low": _num(low),
        "kb_d_high": _num(high),
        "move_usd_bbl": _num(t.move_usd_bbl),
        "interval_includes_zero": bool(low <= 0.0 <= high),
        "lower_share": _num(low / width) if low > 0.0 and width > 0 else None,
        "share_of_runs_percent": _num(100 * t.share_of_runs),
        "share_of_runs_low_percent": _num(100 * t.share_of_runs_low),
        "share_of_runs_high_percent": _num(100 * t.share_of_runs_high),
        "sum_of_lags": _num(model.sum_b),
        "sum_of_lags_unit": t.per_usd_unit,
        "sum_of_lags_se": _num(model.sum_b_se),
        "t": _num(model.sum_b_t),
        "r2": _num(model.regression.r2),
        "months": int(model.regression.nobs),
        "first_month": model.first_month,
        "last_month": model.last_month,
        "newey_west_lag": int(model.regression.nw_lag),
        "zero_segments": _zero_segments(low, high),
    }


def _zero_segments(low: float, high: float) -> list[Mapping[str, Any]]:
    """The Zero column, docs/design.md Part 3 section 5, S27: the distance from
    zero as a share of the interval's width, never a pass word."""
    width = high - low
    if low <= 0.0 <= high:
        return [W("interval_includes_zero", "includes zero")]
    if low > 0.0:
        return [
            T("lower end "),
            N("kb_d_low", low, "kb_d", signed=True),
            T(", "),
            N("lower_share_percent", 100 * low / width, "percent"),
            T(" percent of the interval's width above zero"),
        ]
    return [
        T("upper end "),
        N("kb_d_high", high, "kb_d", signed=True),
        T(", "),
        N("upper_share_percent", 100 * -high / width, "percent"),
        T(" percent of the interval's width below zero"),
    ]


def run_economics(inputs: Inputs) -> Mapping[str, Any]:
    view = inputs.view
    runs = inputs.entry("jodi_nwe_refinery_intake_monthly")
    payload = _header("run-economics", view.runs_data_date, "utilisation against what the margin implies, the crude demand response on both equations, and the run cut threshold verdict")
    payload["conventions"] = _conventions()
    rank = _trailing_rank(inputs)
    run = run_verdict(inputs.threshold, inputs.threshold_without_stretch, view, rank)
    payload["threshold"] = run

    cap, fall, diag = inputs.capacity_model, inputs.fallback_model, inputs.diagnostic_model
    first, last = pd.Timestamp(cap.first_month), pd.Timestamp(cap.last_month)
    steps_in_sample = [y + analysis.CAPACITY_SOURCE_LAG_YEARS for y in analysis.capacity_step_years()
                       if first <= pd.Timestamp(year=y + analysis.CAPACITY_SOURCE_LAG_YEARS, month=1, day=1) <= last]
    payload["response"] = {
        "order": ["capacity", "intake_trend"],
        "models": [
            _model_row(
                cap, "capacity", "Utilisation of capacity, the planned model",
                "NWE crude intake over capacity, on the margin at the average US refinery's gas use over the three previous months, with month fixed effects and a term for each episode",
            ),
            _model_row(
                fall, "intake_trend", "Crude intake with a trend",
                "the log of NWE crude intake, on the same margin terms, with a linear trend, month fixed effects, a term for each episode and a step from the January after each year capacity fell by a refinery or more",
                steps_in_sample,
            ),
        ],
        "interval_level_percent": 95,
    }
    strip = [T("Crude runs per "), N("move_usd_bbl", cap.translation.move_usd_bbl, "count"), T(" $/bbl of margin, each with its "),
             N("interval_level_percent", 95, "count"), T(" percent interval, on one scale with zero marked: ")]
    for i, model in enumerate(payload["response"]["models"]):
        strip += [
            T("" if i == 0 else "; "),
            W("label", model["label"]),
            T(", "),
            N("kb_d", model["kb_d"], "kb_d", signed=True),
            T(" kb/d, "),
            N("kb_d_low", model["kb_d_low"], "kb_d", signed=True),
            T(" to "),
            N("kb_d_high", model["kb_d_high"], "kb_d", signed=True),
        ]
    payload["response"]["strip_desc_segments"] = [x for x in strip if x.get("text") != ""] + [T(".")]
    gap = fall.sum_b - cap.sum_b
    moved = (diag.sum_b - cap.sum_b) / gap if gap else math.nan
    reason = [T("The capacity figure falls by a step in ")]
    for i, year in enumerate(steps_in_sample):
        if i:
            reason.append(T(" and " if i == len(steps_in_sample) - 1 else ", "))
        reason.append(N("capacity_step_year", year, "year"))
    reason += [
        T(", and the planned model has no trend or closure step to absorb it; adding both moves its estimate "),
        N("diagnostic_share_moved_percent", 100 * moved, "percent"),
        T(" percent of the way to the second."),
    ]
    payload["response"]["disagreement"] = {
        "capacity_step_years_in_sample": steps_in_sample,
        "diagnostic_sum_of_lags": _num(diag.sum_b),
        "diagnostic_share_moved_percent": _num(100 * moved),
        "diagnostic_is_reported_as_a_result": False,
        "segments": reason,
    }

    br = inputs.break_result
    frame = analysis.horse_frame()
    frame = frame.dropna(subset=["intake_kb_d"])
    latest = frame.iloc[-1]
    months = []
    for _, r in br.residuals.iterrows():
        month = str(r["date"])
        provisional, word = _status_word(runs, month)
        months.append({
            "month": month,
            "month_label": month_label(month),
            "utilisation_percent": _num(r["actual"]),
            "implied_percent": _num(r["predicted"]),
            "residual_pp": _num(r["residual"]),
            "residual_kb_d": _num(r["residual_kb_d"]),
            "intake_kb_d": _num(r["intake_kb_d"]),
            "provisional": provisional,
            "status_word": word,
        })
    payload["utilisation"] = {
        "runs_month": view.runs_data_date,
        "latest_utilisation_percent": _num(latest["utilisation_pct"]),
        "latest_provisional": _status_word(runs, view.runs_data_date)[0],
        "implied_by": {
            "equation": "utilisation of capacity on the margin at the average US refinery's gas use, lagged one to three months, with month fixed effects and no episode terms, fitted only on months before March 2026",
            "dependent": br.dependent,
            "regressor": br.regressor,
            "first_month_not_fitted": analysis.BREAK_2026_FIRST_POST_MONTH,
        },
        "post_break_months": months,
        "n_post": int(br.n_post),
        "min_post_months": int(br.min_post_months),
        "tested": not br.too_short,
        "segments": [
            T("Whether the relation held after "),
            D("break_date", analysis.BREAK_2026_DATE, kind="day"),
            T(" is not tested: "),
            N("n_post", br.n_post, "count"),
            T(" months have runs data, against a bar of "),
            N("min_post_months", br.min_post_months, "count"),
            T(" set before looking. The rows describe those months and are not a test."),
        ] if br.too_short else [
            T("The months after "),
            D("break_date", analysis.BREAK_2026_DATE, kind="day"),
            T(" clear the bar set before looking."),
        ],
    }
    last_row = next((m for m in months if m["month"] == view.runs_data_date), None)
    latest_words = [
        T("Utilisation in "),
        D("runs_month", view.runs_data_date),
        T(" was "),
        N("latest_utilisation_percent", latest["utilisation_pct"], "percent"),
        T(" percent of capacity"),
    ]
    if last_row is not None:
        latest_words += [
            T(" against "),
            N("implied_percent", last_row["implied_percent"], "percent"),
            T(" percent that the margin implies, and the month is "),
            W("status_word", last_row["status_word"]),
            T("."),
        ]
    else:
        latest_words += [T("; no implied figure exists for that month.")]
    payload["utilisation"]["latest_segments"] = latest_words
    return payload


# ---------------------------------------------------------------------------
# provenance.json
# ---------------------------------------------------------------------------

ATTRIBUTIONS: Sequence[Mapping[str, Any]] = (
    {
        "id": "dgec",
        # Accented, as the ministry writes its name; escaped so this file and the
        # artifact stay ASCII. The rest of the repository writes these names
        # without accents, in code and docs a reader of the page never sees.
        "who": "DGEC, Direction g\u00e9n\u00e9rale de l'\u00e9nergie et du climat, minist\u00e8re de la Transition \u00e9cologique",
        "credit_line": "Source: DGEC, prices credited DGEC-Reuters",
        "third_party": "Every DGEC price table carries 'Source : DGEC-REUTERS'; the assessments are Reuters'. Parsed values are republished with attribution and the note PDFs are not.",
        "licence": "Licence Ouverte 2.0, attribution and the date of last update",
        "series": ["dgec_mbr_monthly", "dgec_brent_monthly", "dgec_note_printed_monthly", "dgec_note_printed_weekly", "dgec_note_reconstructed_weekly", "dgec_note_reconstructed_cracks_weekly", "dgec_note_decoded_index", "dgec_note_decoded_weekly", "dgec_note_decoded_printed", "dgec_note_decoded_monthly", "anchors"],
    },
    {
        "id": "opec_argus",
        "who": "OPEC Monthly Oil Market Report, Rotterdam product assessments by Argus",
        "credit_line": "Argus, via the OPEC Monthly Oil Market Report",
        "third_party": "The table credits Argus. OPEC is acknowledged as copyright holder, for non commercial use.",
        "licence": "OPEC permits non commercial reproduction with full acknowledgement",
        "series": ["opec_rotterdam_products_monthly"],
    },
    {
        "id": "world_bank",
        "who": "World Bank Commodity Price Data (The Pink Sheet)",
        "credit_line": "World Bank Commodity Price Data (The Pink Sheet)",
        "third_party": "The Europe gas series is credited in the workbook to Bloomberg Finance L.P. and World Gas Intelligence.",
        "licence": "CC BY 4.0",
        "series": ["worldbank_gas_europe_monthly"],
    },
    {
        "id": "jodi",
        "who": "JODI-Oil World Database, International Energy Forum",
        "credit_line": "JODI-Oil World Database",
        "third_party": "",
        "licence": "Website terms with all rights reserved and no data licence; a small filtered extract is committed with attribution, a weaker position than any other source here",
        "series": ["jodi_nwe_refinery_intake_monthly", "jodi_nwe_refinery_output_monthly", "jodi_nwe_crude_imports_monthly"],
    },
    {
        "id": "energy_institute",
        "who": "Energy Institute Statistical Review of World Energy 2026",
        "credit_line": "Energy Institute Statistical Review of World Energy 2026",
        "third_party": "The capacity sheet includes ICIS and S&P Global Energy data, so the table is not published. Only the five country total derived from it is, and the utilisation computed with it.",
        "licence": "Quotation with attribution; extensive reproduction needs permission",
        "series": ["ei_refinery_capacity_annual", "nwe5_refinery_capacity_annual"],
    },
    {
        "id": "fred_eia",
        "who": "U.S. Energy Information Administration, retrieved from FRED, Federal Reserve Bank of St. Louis",
        "credit_line": "U.S. Energy Information Administration, Crude Oil Prices: Brent - Europe [DCOILBRENTEU], retrieved from FRED",
        "third_party": "",
        "licence": "EIA data is US public domain with an acknowledgment; FRED asks for citation",
        "series": ["fred_brent_daily", "fred_eurusd_daily", "eia_brent_daily", "eia_refinery_fuel_2023"],
    },
    {
        "id": "sp_global",
        "who": "S&P Global Commodity Insights",
        "credit_line": "S&P Global Commodity Insights, articles of 28 March 2022 and 17 October 2022",
        "third_party": "",
        "licence": "Ordinary quotation of individual figures with a link; never charted as a series",
        "series": ["sp_global_reference"],
    },
    {
        "id": "ice",
        "who": "ICE Futures Europe contract specifications",
        "credit_line": "Conversion factors from ICE Futures Europe crack contract specifications",
        "third_party": "",
        "licence": "Cited, no ICE data is used",
        "series": [],
    },
)

# ---------------------------------------------------------------------------
# The reader layer of provenance.json
# ---------------------------------------------------------------------------
#
# The manifest is the pipeline's own record, written for whoever maintains the
# adapters: series ids, recon references, command lines, a note in capitals
# where something is urgent. It is exported whole, because SPEC.md section 5.3
# makes it a first class artifact. What the Provenance section PRINTS is this
# layer, written for a reader of the page: a plain label and source per series,
# whether any of it is provisional, and the manual steps in sentences. A series
# or a manual step the manifest gains without a reader entry fails the build
# (provenance_reader raises), so nothing reaches the page in the pipeline's
# words and nothing is silently left off it. docs/design.md Part 7, C12.

SERIES_READER: Mapping[str, Mapping[str, str]] = {
    "anchors": {
        "label": "Published margin and price anchors, typed from the ministry's notes",
        "source": "DGEC, checked by hand",
    },
    "dgec_brent_monthly": {
        "label": "Brent, monthly average, from the ministry's history file",
        "source": "DGEC, prices from Reuters",
    },
    "dgec_mbr_monthly": {
        "label": "Gross refining margin on Brent, monthly, the official margin",
        "source": "DGEC, prices from Reuters",
    },
    "dgec_note_printed_monthly": {
        "label": "Rotterdam product prices, monthly, as the weekly note prints them",
        "source": "DGEC weekly note, prices from Reuters",
    },
    "dgec_note_printed_weekly": {
        "label": "Rotterdam product prices, weekly, as the weekly note prints them",
        "source": "DGEC weekly note, prices from Reuters",
    },
    "dgec_note_reconstructed_weekly": {
        "label": "Rotterdam product prices, weekly, read off the weekly note's chart",
        "source": "DGEC weekly note, chart read by this study",
    },
    "dgec_note_reconstructed_cracks_weekly": {
        "label": "Gasoil and gasoline cracks, weekly, from the chart reading",
        "source": "Computed by this study",
    },
    "dgec_note_decoded_index": {
        "label": "The register of the weekly notes this study preserved, one row each",
        "source": "DGEC weekly note, recorded by this study",
    },
    "dgec_note_decoded_weekly": {
        "label": "Every note's chart reading, week by week, before they are stitched together",
        "source": "DGEC weekly note, chart read by this study",
    },
    "dgec_note_decoded_printed": {
        "label": "Every note's printed weekly table, before they are stitched together",
        "source": "DGEC weekly note",
        "gaps_reason": "the weeks no preserved note printed, not lost data",
    },
    "dgec_note_decoded_monthly": {
        "label": "Every note's printed monthly table, with the provisional marker it carried",
        "source": "DGEC weekly note",
        "gaps_reason": "the months no preserved note printed, not lost data",
    },
    "ei_refinery_capacity_annual": {
        "label": "Refinery capacity, annual, five northwest European countries",
        "source": "Energy Institute Statistical Review",
    },
    "nwe5_refinery_capacity_annual": {
        "label": "Refinery capacity, annual, the five country total, which is what the analysis divides by",
        "source": "Derived by this study from the Energy Institute Statistical Review",
    },
    "eia_brent_daily": {
        "label": "Brent spot, daily, from the EIA",
        "source": "US Energy Information Administration",
        "gaps_reason": "holidays with no published price, not lost data",
    },
    "eia_refinery_fuel_2023": {
        "label": "US refinery gas use in one year, typed from EIA tables",
        "source": "US Energy Information Administration",
    },
    "events": {
        "label": "Dated events, each with its source",
        "source": "This study, every entry cited",
    },
    "fred_brent_daily": {
        "label": "Brent spot, daily, the same EIA series through FRED, which the analysis reads",
        "source": "US Energy Information Administration, through FRED",
        "gaps_reason": "holidays with no published price, not lost data",
    },
    "fred_eurusd_daily": {
        "label": "Euro in US dollars, daily",
        "source": "Federal Reserve Board, through FRED",
    },
    "jodi_nwe_crude_imports_monthly": {
        "label": "Crude imports, monthly, five northwest European countries",
        "source": "JODI-Oil World Database",
    },
    "jodi_nwe_refinery_intake_monthly": {
        "label": "Refinery crude intake, monthly, five northwest European countries",
        "source": "JODI-Oil World Database",
    },
    "jodi_nwe_refinery_output_monthly": {
        "label": "Refinery output by product, monthly, five northwest European countries",
        "source": "JODI-Oil World Database",
    },
    "opec_rotterdam_products_monthly": {
        "label": "Rotterdam product prices, monthly, from OPEC's monthly report",
        "source": "OPEC Monthly Oil Market Report, prices from Argus",
    },
    "sp_global_reference": {
        "label": "Reference figures quoted from two S&P Global articles",
        "source": "S&P Global Commodity Insights",
    },
    "ttf_daily": {
        "label": "Dutch TTF gas, front month, daily",
        "source": "Yahoo Finance, symbol TTF=F",
    },
    "worldbank_gas_europe_monthly": {
        "label": "Natural gas in Europe, monthly",
        "source": "World Bank Pink Sheet",
    },
}

#: What the Last fetch column says for a series no machine fetches.
NOT_FETCHED_WORDS = "typed from cited documents, not fetched"

MANUAL_STEPS_HEADING = "Work done by hand"
MANUAL_STEPS_INTRO = (
    "Two gaps no scheduled fetch can close on its own. Each says what it is, why, "
    "what it costs while it is not done, and how it is done."
)

MANUAL_STEPS_READER: Mapping[str, Mapping[str, str]] = {
    "momr_unarchived_2026": {
        "what": "Six issues of OPEC's Monthly Oil Market Report, April to September 2026, have to be saved by hand.",
        "why": "OPEC's website refuses automated downloads, so the study reads past issues from the Internet Archive, which holds every issue from January 2001 to March 2026 and none after.",
        "cost": "Until they are saved, the monthly OPEC crack series ends at February 2026 and misses the whole of the 2026 episode. The ministry's weekly cracks and its monthly margin both cover 2026, so the study still sees it; its longest crack series does not.",
        "how": "Each issue is opened in a browser and saved, and the parser reads the saved copies. The reports themselves are not published here, only the prices read from them.",
    },
    "dgec_weekly_note_collection": {
        "what": "The ministry's weekly note has to be saved in the week it appears. It is the only source of the weekly Rotterdam prices.",
        "why": "The ministry keeps only the latest note online and removes each one when the next is published, and the Internet Archive holds only ten of them. A week that is not saved cannot be recovered.",
        "cost": "A permanent gap in the weekly series. The chart reading is calibrated on the figures each note prints, so a missed note also takes away that week's calibration.",
        "how": "Once a week the note that is online is downloaded and the weekly series are rebuilt from it. The notes themselves are not published here, only the prices read from them.",
    },
}


#: What a manual step's status means, said to a reader.
MANUAL_STEP_STATUS_WORDS: Mapping[str, str] = {
    "outstanding": "It has not been done yet.",
    "standing": "It is never finished: it has to be done every time.",
    "done": "It has been done.",
}


def _provisional_segments(entry: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Whether any of a series is provisional, SPEC.md section 5.3, in words.

    A cache that carries the source's own flag per row (the ministry's printed
    monthly prices) is read row by row, because a month goes final while a later
    one is still provisional and the flags are not contiguous. Otherwise the
    manifest's provisional_from bounds a trailing run to the last date."""
    start = entry.get("provisional_from")
    if not start:
        return [T("none flagged")]
    months: list[str] = []
    try:
        frame = series.load(entry["series"])
    except Exception:  # a seed or a cache with no frame: the manifest bound stands
        frame = None
    if frame is not None and "provisional" in frame.columns:
        flagged = frame[frame["provisional"].astype(str).str.strip().str.lower() == "true"]
        months = sorted(_iso(d) for d in flagged["date"])
    if months:
        out: list[Mapping[str, Any]] = [T("provisional: ")]
        for i, month in enumerate(months):
            if i:
                out.append(T(" and " if i == len(months) - 1 else ", "))
            out.append(D("provisional_month", month))
        return out
    last = entry.get("last_date")
    if last and str(last)[:7] == str(start)[:7]:
        return [T("provisional: "), D("provisional_from", start)]
    return [T("provisional from "), D("provisional_from", start), T(" to "), D("last_date", last)]


def provenance_reader(manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    """The words the Provenance section prints. Raises KeyError, naming it, for a
    manifest series or manual step with no reader entry."""
    rows = {}
    for entry in manifest["series"]:
        name = entry["series"]
        if name not in SERIES_READER:
            raise KeyError("no reader label in export.SERIES_READER for the manifest series %s" % name)
        row = dict(SERIES_READER[name])
        if not entry.get("machine_fetched", True) or not entry.get("fetched_at"):
            row["fetch_words"] = NOT_FETCHED_WORDS
        row["provisional_segments"] = _provisional_segments(entry)
        rows[name] = row
    steps = []
    for step in manifest.get("manual_steps", []):
        if step["id"] not in MANUAL_STEPS_READER:
            raise KeyError("no reader text in export.MANUAL_STEPS_READER for the manual step %s" % step["id"])
        if step["status"] not in MANUAL_STEP_STATUS_WORDS:
            raise KeyError("no reader words in export.MANUAL_STEP_STATUS_WORDS for the status %s" % step["status"])
        steps.append({
            "id": step["id"],
            "status": step["status"],
            "status_sentence": MANUAL_STEP_STATUS_WORDS[step["status"]],
            **MANUAL_STEPS_READER[step["id"]],
        })
    return {
        "series": rows,
        "manual_steps_heading": MANUAL_STEPS_HEADING,
        "manual_steps_intro": MANUAL_STEPS_INTRO,
        "manual_steps": steps,
    }


FONTS: Mapping[str, Any] = {
    "faces": [
        {"family": "Fraunces", "use": "the verdict and view titles", "licence": "SIL Open Font License 1.1"},
        {"family": "Figtree", "use": "body text", "licence": "SIL Open Font License 1.1"},
        {"family": "JetBrains Mono", "use": "figures in tables and on axes", "licence": "SIL Open Font License 1.1"},
    ],
    "substitution": "Body text is set in Figtree, an open licensed stand in for Satoshi, the portfolio's face, whose licence does not allow a copy in a public repository.",
}


def provenance(inputs: Inputs) -> Mapping[str, Any]:
    manifest = inputs.manifest
    last = sorted(e["fetched_at"] for e in manifest["series"] if e.get("fetched_at"))[-1]
    payload = _header("provenance", last[:10], "the manifest whole, the words the Provenance section prints for each series and manual step, and the attribution and licence line for every source")
    payload["conventions"] = _conventions()
    names = {e["series"] for e in manifest["series"]}
    attributions = []
    for item in ATTRIBUTIONS:
        missing = [s for s in item["series"] if s not in names]
        if missing:
            raise KeyError("attribution %s names series with no manifest entry: %s" % (item["id"], missing))
        record = dict(item)
        record["series"] = list(item["series"])
        record["date_of_last_update"] = {
            s: next(e["last_date"] for e in manifest["series"] if e["series"] == s)
            for s in item["series"]
        }
        attributions.append(record)
    ice = next(a for a in attributions if a["id"] == "ice")
    ice["factors"] = [
        {"product": p, "label": series.DGEC_NOTE_MONTHLY_COLUMNS[p][1], "bbl_per_t": config.DGEC_NOTE_PRODUCT_BBL_PER_T[p], **FACTOR_CITATIONS[p]}
        for p in sorted(config.DGEC_NOTE_PRODUCT_BBL_PER_T)
    ]
    ice["retrieved"] = config.ICE_SPEC_RETRIEVED
    payload["attributions"] = attributions
    payload["fonts"] = FONTS
    payload["manifest_columns"] = ["series", "status", "last_date", "provisional", "fetched_at", "gaps", "vintage", "source"]
    payload["reader"] = provenance_reader(manifest)
    payload["manifest"] = manifest
    return payload


# ---------------------------------------------------------------------------
# history.json, docs/design.md Part 8.1
# ---------------------------------------------------------------------------

#: The words a lane button uses for an event, Part 3 section 2. Words only, and
#: one for every event the History view marks; an event of a marked kind with no
#: short name raises in the build instead of reaching the page as an id.
EVENT_SHORT_NAMES: Mapping[str, str] = {
    "imo_2020_sulphur_cap": "Ship fuel sulphur cap",
    "covid_pandemic_and_european_lockdowns_2020_03": "Lockdowns",
    "russia_invades_ukraine_2022_02_24": "Invasion",
    "sp_record_diesel_cracks_week_to_2022_03_25": "Diesel record",
    "sp_ara_diesel_cracks_2022_10_13": "Refinery strikes",
    "eu_embargo_russian_seaborne_crude_2022_12_05": "Crude embargo",
    "eu_embargo_russian_refined_products_2023_02_05": "Product embargo",
    "strikes_on_iran_hormuz_2026_02_28": "Strikes on Iran",
    "iea_collective_action_400_mb_2026_03_11": "Stock release",
    "us_iran_ceasefire_2026_04_07": "Ceasefire",
}

#: The kinds of events.json entry the History view marks as events. The other
#: kinds are breaks and are placed by HISTORY_BREAK_LINES, never as events.
HISTORY_EVENT_KINDS = ("market", "policy", "reference")
HISTORY_BREAK_KINDS = ("specification_break", "definition_change", "method_change")

#: Which line a break splits, from the event's own series_column. A break whose
#: column is not here has no line on this view and is listed, not drawn.
HISTORY_BREAK_LINES: Mapping[str, tuple[str, str]] = {
    "gasoil_usd_bbl": ("monthly", "gasoil"),
    "premium_gasoline_usd_bbl": ("monthly", "gasoline"),
}
#: The gas definition changes carry no series_column; they split the wedge line.
HISTORY_GAS_SERIES = "worldbank_gas_europe_monthly"

BREAK_SHORT_NAMES: Mapping[str, str] = {
    "specification_break": "respecified",
    "definition_change": "Gas series redefined",
    "method_change": "Method in force",
}

#: The named ranges of Part 8.1 H4, each opened by one event of events.json. ONE
#: RULE for all four: from RANGE_LEAD_MONTHS before the event's month to
#: analysis.EPISODE_MONTHS after it, the episode length the regressions use, and
#: the six months before are SPEC.md section 6.5's minus six. Clipped to the data.
RANGE_LEAD_MONTHS = 6
HISTORY_RANGES: tuple[tuple[str, str, str], ...] = (
    ("2020", "2020", "covid_pandemic_and_european_lockdowns_2020_03"),
    ("2022", "2022", "russia_invades_ukraine_2022_02_24"),
    ("embargo_2023", "2023 embargo", "eu_embargo_russian_refined_products_2023_02_05"),
    ("2026", "2026", "strikes_on_iran_hormuz_2026_02_28"),
)

MONTH_SHORT = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _event_day(event: Mapping[str, Any]) -> str:
    """An event's date as an ISO day: a month precision entry is its first day."""
    text = str(event["date"])
    return text if len(text.split("-")) == 3 else text + "-01"


def _month_span_label(first: str, last: str) -> str:
    return "%s to %s" % (month_label(first), month_label(last))


def _history_ranges(first: str, last: str, weekly_first: str, by_id: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    out = [
        {"id": "all", "label": "All", "start": first, "end": last, "event": None},
        {"id": "weekly", "label": "Weekly series from %s" % MONTH_NAMES[pd.Timestamp(weekly_first).month - 1] + " " + str(pd.Timestamp(weekly_first).year), "start": weekly_first, "end": last, "event": None},
    ]
    for range_id, label, event_id in HISTORY_RANGES:
        month = pd.Timestamp(_event_day(by_id[event_id])).to_period("M").to_timestamp()
        start = max(month - pd.DateOffset(months=RANGE_LEAD_MONTHS), pd.Timestamp(first))
        end = min(month + pd.DateOffset(months=analysis.EPISODE_MONTHS) - pd.DateOffset(days=1), pd.Timestamp(last))
        out.append({"id": range_id, "label": label, "start": _iso(start), "end": _iso(end), "event": event_id})
    return out


def _season_sentence(row: Mapping[str, Any], product: str, shape: pd.DataFrame, column: str) -> list[Mapping[str, Any]]:
    """The textbook check said as measured, Part 8.1 H8: the season, the
    difference, its t, the count of seasons, and whether it holds."""
    diff = float(row["difference_usd_bbl"])
    unit = "winters" if int(row["season_spans_years"]) > 1 else "years"
    if product == "gasoline":
        out = [T("May to September sits "), N("gasoline_season_difference_usd_bbl", diff, "usd_bbl", signed=True), T(" $/bbl against the rest of the year, t "), N("gasoline_season_t", row["t"], "t", signed=True)]
    else:
        out = [T("November to March, the winter window desks quote, sits "), N("gasoil_season_difference_usd_bbl", diff, "usd_bbl", signed=True), T(" $/bbl against the rest of the two years each winter spans, t "), N("gasoil_season_t", row["t"], "t", signed=True)]
    out += [T(", higher in "), N("%s_seasons_positive" % product, row["seasons_positive"], "count"), T(" of "), N("%s_seasons" % product, row["seasons"], "count"), T(" %s: " % unit)]
    if bool(row["holds"]):
        out.append(T("%s firms into %s in this sample." % (product, "the driving season" if product == "gasoline" else "winter")))
    else:
        out.append(T("%s does not firm into %s in this sample." % (product, "the driving season" if product == "gasoline" else "winter")))
        ranked = shape.sort_values("%s_mean" % column, ascending=False).head(2)
        months = [int(m) for m in ranked["month"]]
        values = [float(v) for v in ranked["%s_mean" % column]]
        out += [
            T(" Its strongest months are "),
            W("%s_strongest_month" % product, MONTH_NAMES[months[0] - 1]),
            T(", "),
            N("%s_strongest_usd_bbl" % product, values[0], "usd_bbl", signed=True),
            T(", and "),
            W("%s_second_month" % product, MONTH_NAMES[months[1] - 1]),
            T(", "),
            N("%s_second_usd_bbl" % product, values[1], "usd_bbl", signed=True),
            T("."),
        ]
    return out


def _gasoline_row_sensitivity() -> Mapping[str, Any]:
    """The driving season premium computed on each of OPEC's two gasoline rows.

    SPEC.md section 2 rule 3 again: where the source prints two readings, the
    published figure is reported on both rather than on the one the study
    prefers. The two are within a tenth of a dollar here, which is worth saying
    out loud, because a sensitivity is only reassuring once it is measured.
    """
    s = analysis.gasoline_row_sensitivity()
    head, other = s["headline"], s["alternative"]
    return {
        "substituted_months": int(len(s["substituted_months"])),
        "first_month": s["first_month"],
        "last_month": s["last_month"],
        "drawn_row": {
            "difference_usd_bbl": _num(head["difference_usd_bbl"]),
            "t": _num(head["t"]),
            "seasons_positive": head["seasons_positive"],
            "seasons": head["seasons"],
        },
        "other_row": {
            "difference_usd_bbl": _num(other["difference_usd_bbl"]),
            "t": _num(other["t"]),
            "seasons_positive": other["seasons_positive"],
            "seasons": other["seasons"],
        },
        "segments": [
            T("OPEC printed two gasoline rows between "),
            D("dispute_first", s["first_month"]), T(" and "), D("dispute_last", s["last_month"]),
            T(" and in "), N("substituted_months", len(s["substituted_months"]), "count"),
            T(" months they swap values, so this premium is computed on both. On the row drawn here it is "),
            N("headline_difference", head["difference_usd_bbl"], "usd_bbl", signed=True),
            T(" $/bbl, t "), N("headline_t", head["t"], "t", signed=True),
            T(", positive in "), N("headline_positive", head["seasons_positive"], "count"),
            T(" of "), N("headline_seasons", head["seasons"], "count"),
            T(" seasons; on the other row "),
            N("alternative_difference", other["difference_usd_bbl"], "usd_bbl", signed=True),
            T(" $/bbl, t "), N("alternative_t", other["t"], "t", signed=True),
            T(", positive in "), N("alternative_positive", other["seasons_positive"], "count"),
            T(" of "), N("alternative_seasons", other["seasons"], "count"),
            T(". The claim does not turn on which row is the series."),
        ],
    }


def _seasonal_monthly_layer(frame: pd.DataFrame) -> Mapping[str, Any]:
    """The long monthly seasonality, OPEC, each complete year demeaned."""
    out: dict[str, Any] = {"panels": {}}
    complete_years: list[int] = []
    for product, column in WEEKLY_COLUMNS.items():
        work = frame.dropna(subset=[column])[["date", column]].copy()
        work["year"] = work["date"].dt.year
        work["month"] = work["date"].dt.month
        counts = work.groupby("year")["month"].count()
        years = [int(y) for y in counts[counts == 12].index]
        partial = [int(y) for y in counts[counts < 12].index]
        complete_years = years
        full = work[work["year"].isin(years)].copy()
        full["demeaned"] = full[column] - full.groupby("year")[column].transform("mean")
        lines = []
        for year in years:
            block = full[full["year"] == year].set_index("month")["demeaned"]
            lines.append([year, [_num(block.get(m)) for m in range(1, 13)]])
        episode_years = [y for y in analysis.SEASONAL_REMOVABLE_YEARS if y in years]
        variants = {}
        for variant, excluded in (("all", ()), ("without_episodes", tuple(episode_years))):
            shape = analysis.seasonal_shape(exclude_years=excluded, frame=frame)
            check = analysis.seasonal_textbook_check(exclude_years=excluded, frame=frame)
            row = check[check["crack"] == column].iloc[0]
            kept = [y for y in years if y not in excluded]
            variants[variant] = {
                "excluded_years": list(excluded),
                "years": len(kept),
                "mean_usd_bbl": [_num(v) for v in shape["%s_mean" % column]],
                "difference_usd_bbl": _num(row["difference_usd_bbl"]),
                "t": _num(row["t"]),
                "seasons_positive": int(row["seasons_positive"]),
                "seasons": int(row["seasons"]),
                "holds": bool(row["holds"]),
                "sentence_segments": _season_sentence(row, product, shape, column),
                "mean_label_segments": [T("Mean of "), N("years", len(kept), "count"), T(" years")],
            }
        season = analysis.DRIVING_SEASON_MONTHS if product == "gasoline" else analysis.HEATING_SEASON_MONTHS
        out["panels"][product] = {
            "name": PRODUCT_NAMES[product],
            "line_style": "solid" if product == "gasoil" else "dashed",
            "years": years,
            "partial_years": partial,
            "columns": ["year", "demeaned_usd_bbl_by_month"],
            "lines": lines,
            "episode_years_in_range": episode_years,
            "season_months": list(season),
            "season_label": "May to September, the driving season" if product == "gasoline" else "November to March, the window desks quote",
            "variants": variants,
        }
        if product == "gasoline":
            # The driving season premium is the one published result that reads
            # OPEC gasoline over the months where the source printed two rows
            # that disagree, so it is reported on both of them. See
            # crack.sources.opec_momr.GASOLINE_ROW_DISPUTE.
            out["panels"][product]["row_sensitivity"] = _gasoline_row_sensitivity()
    last_partial = [y for y in out["panels"]["gasoil"]["partial_years"] if y > max(complete_years)]
    out["months"] = list(MONTH_SHORT)
    out["first_year"] = min(complete_years)
    out["last_year"] = max(complete_years)
    note = [T("Each line is one calendar year of OPEC's Rotterdam quotations less that year's own mean, "), N("first_year", min(complete_years), "year"), T(" to "), N("last_year", max(complete_years), "year"), T(".")]
    if last_partial:
        last_month = frame["date"].max()
        note += [T(" "), N("partial_year", last_partial[0], "year"), T(" is not drawn: OPEC's quotations for it stop at "), D("monthly_last", _iso(last_month)), T(", and a year's shape needs its own twelve month mean.")]
    out["note_segments"] = note
    return out


def _runs_of(flags: Sequence[bool], dates: Sequence[str]) -> list[dict]:
    """Contiguous runs of True, as {first, last, months}. Used for the disputed
    window, which is a property of the values and not a typed pair of dates."""
    out: list[dict] = []
    start: int | None = None
    for index, flag in enumerate(list(flags) + [False]):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            out.append(
                {
                    "first": dates[start],
                    "last": dates[index - 1],
                    "months": index - start,
                }
            )
            start = None
    return out


def gasoline_dispute(monthly: pd.DataFrame) -> Mapping[str, Any]:
    """The two gasoline rows OPEC printed, and the months where they swap.

    SPEC.md section 2 rule 3: a source that contradicts itself is reported, not
    resolved. The record in crack.sources.opec_momr says what the dispute is and
    carries the evidence that cannot be recomputed here, the readings of four
    archived issues and OPEC's own annual bulletin, neither of which is a
    committed file. Everything else is measured from the committed cache: which
    months the rule marks, both cracks in each of them, and how many of them the
    headline row puts below zero.
    """
    record = opec_momr.GASOLINE_ROW_DISPUTE
    frame = monthly.dropna(subset=["gasoline_95_usd_bbl"]).copy()
    swapped = opec_momr.gasoline_dispute_months(
        frame, headline="gasoline_usd_bbl", alternative="gasoline_95_usd_bbl"
    )
    dates = [_iso(d) for d in frame["date"]]
    windows = _runs_of(list(swapped), dates)
    marked = frame[swapped.to_numpy()]
    negative = marked[marked[analysis.CRACK_GASOLINE] < 0]
    longest = max(windows, key=lambda w: w["months"]) if windows else None
    sensitivity = analysis.gasoline_row_sensitivity()
    head, other = sensitivity["headline"], sensitivity["alternative"]
    # The years of the annual check where the bulletin is closer to the headline
    # row than to the other one. Measured off the record, not typed, so the
    # sentence cannot drift from the table under it.
    agreeing = [
        a["year"]
        for a in record["annual_check"]
        if abs(a["headline"] - a["asb"]) < abs(a["alternative"] - a["asb"])
    ]
    annual_agree_first = min(agreeing) if agreeing else None
    annual_agree_last = max(agreeing) if agreeing else None

    payload: dict[str, Any] = {
        "id": record["id"],
        "overlap_first": dates[0],
        "overlap_last": dates[-1],
        "windows": windows,
        "months": int(swapped.sum()),
        "negative_months": int(len(negative)),
        "headline_spec": str(marked["gasoline_spec"].iloc[0]) if len(marked) else None,
        "alternative_spec": opec_momr.GASOLINE_95,
        "columns": [
            "date",
            "headline_usd_bbl",
            "alternative_usd_bbl",
            "headline_price_usd_bbl",
            "alternative_price_usd_bbl",
        ],
        "rows": [
            [
                _iso(r["date"]),
                _num(r[analysis.CRACK_GASOLINE]),
                _num(r[analysis.CRACK_GASOLINE_95]),
                _num(r["gasoline_usd_bbl"]),
                _num(r["gasoline_95_usd_bbl"]),
            ]
            for _, r in marked.iterrows()
        ],
        # The evidence that cannot be recomputed from a committed file, as rows
        # rather than as prose, because a sentence carrying a figure is a figure
        # the reader cannot check against a column. tests/test_export.py forbids
        # a digit in a words segment for the same reason.
        "issue_columns": [
            "month", "earlier_issue", "earlier_headline_usd_bbl", "earlier_alternative_usd_bbl",
            "later_issue", "later_headline_usd_bbl", "later_alternative_usd_bbl",
        ],
        "issue_rows": [
            [
                _iso("%s-01" % e["month"]),
                _iso("%s-01" % e["earlier_issue"]),
                _num(e["earlier_headline"]),
                _num(e["earlier_alternative"]),
                _iso("%s-01" % e["later_issue"]),
                _num(e["later_headline"]),
                _num(e["later_alternative"]),
            ]
            for e in record["issue_evidence"]
        ],
        "annual_columns": ["year", "asb_usd_bbl", "headline_usd_bbl", "alternative_usd_bbl"],
        "annual_rows": [
            [int(a["year"]), _num(a["asb"]), _num(a["headline"]), _num(a["alternative"])]
            for a in record["annual_check"]
        ],
        "annual_source": "OPEC Annual Statistical Bulletin, table 7.6, spot prices, Rotterdam",
        "sources": [dict(s) for s in record["sources"]],
        "bracket_label": "The two printed rows swap here",
        "heading_segments": [
            T("In "), N("dispute_months", int(swapped.sum()), "count"),
            T(" months OPEC printed two gasoline rows whose values swap between issues, and this panel draws both."),
        ],
        "what_segments": [
            T("From "), D("overlap_first", dates[0]), T(" to "), D("overlap_last", dates[-1]),
            T(" the Rotterdam block printed a sulphur graded premium gasoline row and an octane graded one side by side. The line above follows the sulphur graded label. In "),
            N("dispute_months", int(swapped.sum()), "count"),
            T(" of those months the two rows exchange values between consecutive issues, and the sulphur graded row is left carrying the lower of the two readings: "),
            N("negative_months", int(len(negative)), "count"),
            T(" of them then price Rotterdam gasoline below dated Brent, a negative crack on a barrel nobody would have run. The dotted line is the other row OPEC printed in the same table of the same issues."),
        ],
        "evidence_segments": [
            T("The swap is visible issue by issue. The month of "),
            D("swap_month", _iso("%s-01" % record["issue_evidence"][0]["month"])),
            T(" as the issue of "),
            D("swap_earlier_issue", _iso("%s-01" % record["issue_evidence"][0]["earlier_issue"])),
            T(" printed it on the sulphur graded row, "),
            N("swap_earlier_headline", record["issue_evidence"][0]["earlier_headline"], "usd_bbl"),
            T(" $/bbl, is the same month as the issue of "),
            D("swap_later_issue", _iso("%s-01" % record["issue_evidence"][0]["later_issue"])),
            T(" printed it on the octane graded row, "),
            N("swap_later_alternative", record["issue_evidence"][0]["later_alternative"], "usd_bbl"),
            T(" $/bbl, while the sulphur graded row fell to "),
            N("swap_later_headline", record["issue_evidence"][0]["later_headline"], "usd_bbl"),
            T(". In the same block of the same two issues naphtha, jet and both fuel oils move by ordinary revision size, and the Mediterranean block prints the month identically, so this is the two gasoline rows and not a restatement of the table."),
        ],
        "annual_segments": [
            T("OPEC's own Annual Statistical Bulletin restates these years onto one premium unleaded definition, and in "),
            N("annual_year_a", record["annual_check"][-2]["year"], "year"), T(" and "),
            N("annual_year_b", record["annual_check"][-1]["year"], "year"),
            T(" it agrees with the dotted row, not this panel's line: it misses the line by "),
            N("annual_gap_a", record["annual_check"][-2]["headline"] - record["annual_check"][-2]["asb"], "usd_bbl", signed=True),
            T(" and "),
            N("annual_gap_b", record["annual_check"][-1]["headline"] - record["annual_check"][-1]["asb"], "usd_bbl", signed=True),
            T(" $/bbl and the other row by "),
            N("annual_alt_gap_a", record["annual_check"][-2]["alternative"] - record["annual_check"][-2]["asb"], "usd_bbl", signed=True),
            T(" and "),
            N("annual_alt_gap_b", record["annual_check"][-1]["alternative"] - record["annual_check"][-1]["asb"], "usd_bbl", signed=True),
            T(". From "), N("annual_agree_first", annual_agree_first, "year"),
            T(" to "), N("annual_agree_last", annual_agree_last, "year"),
            T(" the bulletin agrees with this panel's line instead, with no label change between, so it follows neither row consistently and settles nothing."),
        ],
        "unresolved_segments": [
            T("So the study does not choose. Both readings are OPEC's, both are in the data, and the only published result that reads gasoline across these months, the driving season premium, is reported on both rows below: "),
            N("headline_difference", head["difference_usd_bbl"], "usd_bbl", signed=True),
            T(" $/bbl on the line, "),
            N("alternative_difference", other["difference_usd_bbl"], "usd_bbl", signed=True),
            T(" $/bbl on the dotted row. The seasonal claim does not turn on the choice."),
        ],
    }
    if longest is not None:
        payload["longest_window"] = longest
    return payload


def history(inputs: Inputs) -> Mapping[str, Any]:
    """The History view: three time panels, their events and breaks, the named
    ranges, and the seasonal sub view's monthly layer. The weekly seasonal layer
    is data/cracks.json, which the view also reads."""
    events_file = events_anchors.load_events()
    by_id = {e["id"]: e for e in events_file["events"]}

    monthly = series.opec_monthly_cracks().sort_values("date").reset_index(drop=True)
    monthly["date"] = pd.to_datetime(monthly["date"])
    margin = series.margin_after_gas_monthly().sort_values("date").reset_index(drop=True)
    margin["date"] = pd.to_datetime(margin["date"])
    weekly = inputs.weekly.sort_values("date").reset_index(drop=True)

    m_first, m_last = _iso(monthly["date"].min()), _iso(monthly["date"].max())
    g_first, g_last = _iso(margin["date"].min()), _iso(margin["date"].max())
    w_first, w_last = _iso(weekly["date"].min()), _iso(weekly["date"].max())
    data_end = max(m_last, g_last, w_last)

    payload = _header("history", w_last, "the monthly OPEC cracks, the ministry's margin with the gas wedge beside it, the weekly reconstruction, their events and breaks, the named ranges, and the monthly seasonality")
    payload["conventions"] = _conventions()

    first_complete = int(monthly["date"].dt.year.value_counts().sort_index().loc[lambda s: s == 12].index.min())
    payload["title_segments"] = [
        T("Rotterdam cracks month by month since "), D("monthly_first", m_first),
        T(", the ministry's margin since "), D("margin_first", g_first),
        T(", and this study's weekly reading since "), D("weekly_first", w_first, kind="day"),
        T(", each on its own panel."),
    ]
    payload["sample_segments"] = [
        T("The sample starts in "), N("sample_first_year", first_complete, "year"),
        T(", the owner's choice of the full OPEC record, so the cracks reach back to "), D("monthly_first", m_first),
        T(" while the official margin exists only from "), D("margin_first", g_first),
        T("; nothing here extends the margin back before its first published month."),
    ]

    # The monthly cracks panel, and the two gasoline rows under it.
    dispute = gasoline_dispute(monthly)
    disputed_months = {row[0]: True for row in dispute["rows"]}
    joined = monthly.merge(margin[["date", "mbr_usd_bbl"]], on="date", how="inner").dropna(subset=[analysis.CRACK_GASOIL, analysis.CRACK_GASOLINE, "mbr_usd_bbl"])
    r2 = {p: float(np.corrcoef(joined[c], joined["mbr_usd_bbl"])[0, 1] ** 2) for p, c in WEEKLY_COLUMNS.items()}
    payload["monthly"] = {
        "heading_segments": [T("Monthly gasoil and gasoline cracks on OPEC's Rotterdam barge quotations, "), D("first", m_first), T(" to "), D("last", m_last), T(".")],
        "source": "OPEC Monthly Oil Market Report, Rotterdam barges FOB, assessments credited to Argus, less FRED Brent",
        "first": m_first,
        "last": m_last,
        "columns": ["date", "gasoil_usd_bbl", "gasoline_usd_bbl", "gasoil_spec", "gasoline_spec", "gasoline_95_usd_bbl", "gasoline_disputed"],
        "rows": [
            [_iso(r["date"]), _num(r[analysis.CRACK_GASOIL]), _num(r[analysis.CRACK_GASOLINE]), None if _is_missing(r.get("gasoil_spec")) else str(r["gasoil_spec"]), None if _is_missing(r.get("gasoline_spec")) else str(r["gasoline_spec"]), _num(r[analysis.CRACK_GASOLINE_95]), bool(disputed_months.get(_iso(r["date"]), False))]
            for _, r in monthly.iterrows()
        ],
        "r2_months": int(len(joined)),
        "r2": {p: _num(v) for p, v in r2.items()},
        "r2_segments": [
            T("Month to month the gasoil crack tracks the official margin far more closely than gasoline does: R squared "),
            N("gasoil_r2", r2["gasoil"], "r2"), T(" against "), N("gasoline_r2", r2["gasoline"], "r2"),
            T(" over the "), N("r2_months", len(joined), "count"), T(" months both exist. Gasoline is the weaker leg."),
        ],
        "end_segments": [T("OPEC's product quotations stop at "), D("last", m_last), T(": the archive holds no later issue, so the line ends there rather than being carried forward.")],
        "dispute": dispute,
    }

    # The margin panel and the wedge beside it.
    ministry = float(config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL)
    study = float(config.GAS_INTENSITY_MMBTU_PER_BBL)
    payload["margin"] = {
        "heading_segments": [T("The ministry's gross refining margin on Brent, "), D("first", g_first), T(" to "), D("last", g_last), T(", already net of the ministry's own gas allowance.")],
        "wedge_heading_segments": [T("Beside it, not subtracted from it: the extra gas at the average US refinery's use, "), N("study_intensity", study, "mmbtu_per_bbl"), T(" MMBtu/bbl against the ministry's "), N("ministry_intensity", ministry, "mmbtu_per_bbl"), T(", at each month's European gas price.")],
        "first": g_first,
        "last": g_last,
        "columns": ["date", "mbr_usd_bbl", "gas_usd_mmbtu", "gas_wedge_usd_bbl"],
        "rows": [[_iso(r["date"]), _num(r["mbr_usd_bbl"]), _num(r["gas_usd_mmbtu"]), _num(r["gas_wedge_usd_bbl"])] for _, r in margin.iterrows()],
        "study_intensity_mmbtu_per_bbl": study,
        "ministry_intensity_mmbtu_per_bbl": ministry,
        "no_break_segments": [
            T("No break is drawn on the margin because none exists in it: the method in force from "),
            D("method_in_force", _event_day(by_id["dgec_mbr_method_in_force_2016_01_01"]), kind="day"),
            T(" was recomputed back over the two years before it, and the published series starts in "),
            D("first", g_first), T("."),
        ],
        "no_break_source_url": by_id["dgec_mbr_method_in_force_2016_01_01"]["source_url"],
    }

    # The weekly panel.
    join = analysis.seasonal_join()
    error = dgec_note.RECONSTRUCTION_ERROR
    oldest = weekly[weekly["evidence_class"] == "single_geometry_oldest"]
    newest = weekly[weekly["evidence_class"] == "single_geometry_newest"]
    payload["weekly"] = {
        "heading_segments": [T("Weekly gasoil and gasoline cracks read off the ministry's weekly chart, from the week to "), D("first", w_first, kind="day"), T(" to the week to "), D("last", w_last, kind="day"), T(".")],
        "first": w_first,
        "last": w_last,
        "columns": ["date", "gasoil_usd_bbl", "gasoline_usd_bbl", "brent_usd_bbl", "printed_gasoil_usd_bbl", "printed_gasoline_usd_bbl", "evidence_class", "n_independent_geometries"],
        "rows": [
            [_iso(r["date"]), _num(r[analysis.CRACK_GASOIL]), _num(r[analysis.CRACK_GASOLINE]), _num(r["brent_usd_bbl"]), _num(r["printed_gasoil_usd_bbl"]), _num(r["printed_gasoline_usd_bbl"]), None if _is_missing(r["evidence_class"]) else str(r["evidence_class"]), _int(r["n_independent_geometries"])]
            for _, r in weekly.iterrows()
        ],
        "least_defended_class": "single_geometry_oldest",
        "newest_class": "single_geometry_newest",
        "evidence_segments": [
            T("Lines are this study's reading of the ministry's chart; squares are the "),
            N("printed_weeks", int(weekly["printed_gasoil_usd_bbl"].notna().sum()), "count"),
            T(" weeks the ministry printed. Refitted on three products and tested on the fourth, a note's reading misses its printed figures by "),
            N("error_low_usd_t", error["out_of_sample_mae_usd_t"][0], "usd_t_error"), T(" to "), N("error_high_usd_t", error["out_of_sample_mae_usd_t"][1], "usd_t_error"),
            T(" $/t on average, but that test sits where the notes print figures and does not bound the oldest weeks: the "),
            N("oldest_weeks", len(oldest), "count"), T(" weeks from "), D("oldest_first", _iso(oldest["date"].min()), kind="day"),
            T(", hatched under the axis, are the least defended data in the study, and the "),
            N("newest_weeks", len(newest), "count"), T(" weeks from "), D("newest_first", _iso(newest["date"].min()), kind="day"),
            T(" have no second chart yet."),
        ],
        "join": {
            "overlap_months": int(join["overlap_months"]),
            "gasoil_mean_gap_usd_bbl": _num(join["%s_mean_gap" % analysis.CRACK_GASOIL]),
            "gasoline_mean_gap_usd_bbl": _num(join["%s_mean_gap" % analysis.CRACK_GASOLINE]),
        },
        "join_segments": [
            T("This panel is never joined to the monthly one. Over the "), N("overlap_months", join["overlap_months"], "count"),
            T(" months both cover, the weekly crack less OPEC's monthly one averages "), N("gasoil_mean_gap_usd_bbl", join["%s_mean_gap" % analysis.CRACK_GASOIL], "usd_bbl", signed=True),
            T(" $/bbl for gasoil and "), N("gasoline_mean_gap_usd_bbl", join["%s_mean_gap" % analysis.CRACK_GASOLINE], "usd_bbl", signed=True),
            T(" $/bbl for gasoline: the ministry's gasoline is Eurosuper, a finished premium grade, and OPEC's is a different product, so a spliced line would jump by a product and not by a market."),
        ],
    }

    # Events, from the seed, by kind, only those this view can place.
    events = []
    for event in events_file["events"]:
        if event["kind"] not in HISTORY_EVENT_KINDS or event.get("layer") == "daily":
            continue
        if event["id"] not in EVENT_SHORT_NAMES:
            raise KeyError("events.json entry %s has no short name for the History lane" % event["id"])
        day = _event_day(event)
        events.append({
            "id": event["id"],
            "date": day,
            "precision": event.get("date_precision"),
            "label": D("date", day, kind="day" if event.get("date_precision") == "day" else "month")["label"],
            "short": EVENT_SHORT_NAMES[event["id"]],
            "name": event["label"],
            "kind": event["kind"],
            "source_url": event["source_url"],
            "source_title": event.get("source_title"),
            "source_publisher": event.get("source_publisher"),
        })
    events.sort(key=lambda e: e["date"])
    payload["events"] = events

    # Breaks: drawn where a line of this view carries them, listed otherwise.
    breaks = []
    for event in events_file["events"]:
        if event["kind"] not in HISTORY_BREAK_KINDS:
            continue
        day = _event_day(event)
        panel, line, reason = None, None, None
        column = event.get("series_column")
        if event["kind"] == "method_change":
            reason = "not a break in the data this view draws: the ministry recomputed the margin before this date on the new method, and its published series starts after the recomputed window begins"
        elif event.get("layer") == "daily":
            reason = "a break in the ICE daily futures layer, which this study does not publish"
        elif column in HISTORY_BREAK_LINES:
            panel, line = HISTORY_BREAK_LINES[column]
        elif HISTORY_GAS_SERIES in event.get("applies_to", ()):
            if day >= g_first:
                panel, line = "margin", "gas_wedge"
            else:
                reason = "before the first month of the margin, so before anything this view prices gas for"
        else:
            reason = "no line on this view carries the series it applies to"
        short = BREAK_SHORT_NAMES[event["kind"]]
        if event["kind"] == "specification_break" and line:
            short = PRODUCT_NAMES[line][:1].upper() + PRODUCT_NAMES[line][1:] + " " + short
        elif event["kind"] == "specification_break":
            short = "Specification changed"
        breaks.append({
            "id": event["id"], "date": day, "label": D("date", day, kind="day" if event.get("date_precision") == "day" else "month")["label"],
            "name": event["label"], "short": short, "kind": event["kind"],
            "panel": panel, "line": line, "drawn": panel is not None, "reason": reason,
            "source_url": event["source_url"], "source_title": event.get("source_title"),
        })
    # The capacity steps inside the months the run regressions use, the same
    # list run-economics.json names, so the two views never disagree on them.
    capacity = inputs.entry(analysis.CAPACITY_SERIES)
    cap_first, cap_last = pd.Timestamp(inputs.capacity_model.first_month), pd.Timestamp(inputs.capacity_model.last_month)
    for year in sorted(y + analysis.CAPACITY_SOURCE_LAG_YEARS for y in analysis.capacity_step_years()):
        day = "%d-01-01" % year
        if not (cap_first <= pd.Timestamp(day) <= cap_last):
            continue
        breaks.append({
            "id": "capacity_step_%d" % year, "date": day, "label": month_label(day),
            "name": "Refinery capacity figure steps down", "short": "Capacity figure steps", "kind": "capacity_step",
            "panel": None, "line": None, "drawn": False,
            "reason": "a step in the capacity that divides refinery intake, so a break in utilisation, which this view does not draw",
            "source_url": capacity.get("page_url") or capacity.get("url"), "source_title": "Energy Institute, Statistical Review of World Energy, refinery capacity by country",
        })
    breaks.sort(key=lambda b: (b["date"], b["id"]))
    payload["breaks"] = breaks
    payload["ranges"] = _history_ranges(m_first, data_end, w_first, by_id)
    payload["seasonal_monthly"] = _seasonal_monthly_layer(analysis.crack_frame())
    return payload


# ---------------------------------------------------------------------------
# model.json, docs/design.md Part 8.2
# ---------------------------------------------------------------------------
#
# The calculator's presets. The model margin is the ministry's slate yields
# times the cracks, on engine.MARGIN_GROSS_OF_GAS with no residual, so gas is
# subtracted from it; the ministry's MBR, already net of its own gas, travels
# beside each preset for comparison and is never a step of the model. Every
# input of every preset carries the sentence saying where it came from, and a
# product a source does not quote for the month is null with its reason.
#
# The breakevens are computed against breakeven_target, a margin of zero,
# because the run cut threshold is unidentified (Gate 3): no threshold, no
# headroom figure, anywhere in this file.

#: The presets SPEC.md section 7.2 names, in its order. `months` None means the
#: latest margin month, resolved at build time.
MODEL_PRESETS: tuple[tuple[str, str], ...] = (
    ("latest", "note"),
    ("average_2019", "opec"),
    ("october_2022", "opec"),
    ("july_2026", "reconstructed"),
)
MODEL_PRESET_MONTHS: Mapping[str, Sequence[str] | None] = {
    "latest": None,
    "average_2019": tuple("2019-%02d-01" % m for m in range(1, 13)),
    "october_2022": ("2022-10-01",),
    "july_2026": ("2026-07-01",),
}
MODEL_BREAKEVEN_TARGET_USD_BBL = 0.0
MODEL_PANDEMIC_EVENT = "covid_pandemic_and_european_lockdowns_2020_03"
MODEL_STRIKES_EVENT = "sp_ara_diesel_cracks_2022_10_13"
MODEL_IRAN_EVENT = "strikes_on_iran_hormuz_2026_02_28"
MODEL_GAS_BECOMES_TTF_EVENT = "worldbank_europe_gas_definition_2015_04"

#: How a reconstructed week's evidence class is said in a preset note.
MODEL_EVIDENCE_WORDS: Mapping[str, tuple[str, str]] = {
    "cross_checked": ("Every one of them is checked against a second chart.", "checked against a second chart"),
    "single_geometry_newest": ("No second chart has checked any of them yet.", "not yet checked by a second chart"),
    "single_geometry_oldest": ("Every one of them is among the least defended weeks of the reconstruction.", "among the least defended weeks"),
}


def _and_list(words: Sequence[str]) -> str:
    words = list(words)
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def _period_segments(field: str, months: Sequence[str]) -> list[Mapping[str, Any]]:
    """A month said by name, or a calendar year said as its number."""
    if len(months) == 1:
        return [D(field, months[0])]
    return [N(field, pd.Timestamp(months[0]).year, "year")]


def _model_margin(cracks: Mapping[str, float | None], ttf: float, eurusd: float) -> engine.MarginResult:
    products = [p for p in series.MODEL_PRODUCTS if cracks.get(p) is not None]
    return engine.evaluate(engine.MarginInputs(
        yields={p: _num(series.DGEC_NOTE_VOLUME_YIELDS[p]) for p in products},
        cracks={p: cracks[p] for p in products},
        gas=engine.gas_from_ttf(ttf, eurusd),
        gas_intensity_mmbtu_per_bbl=config.GAS_INTENSITY_MMBTU_PER_BBL,
        other_variable_cost_usd_bbl=config.OTHER_VARIABLE_COST_USD_BBL,
        margin_basis=engine.MARGIN_GROSS_OF_GAS,
    ))


def _model_scale(cracks: Mapping[str, float | None], ttf: float, eurusd: float, mbr: float | None) -> Mapping[str, Any]:
    """The preset's shared scale: every running total of both blocks, on the
    1, 2, 5 ladder, zero inside. The page widens it only when an edit runs past."""
    result = _model_margin(cracks, ttf, eurusd)
    ends, running = [0.0], 0.0
    for product in series.MODEL_PRODUCTS:
        if product in result.contributions:
            running += result.contributions[product]
            ends.append(running)
    ends += [result.gross_margin_usd_bbl, result.gross_margin_usd_bbl - result.gas_cost_usd_bbl, result.margin_after_gas_usd_bbl]
    if mbr is not None:
        ends.append(mbr)
    low = min(0.0, _ladder_ceiling(min(ends)))
    high = max(0.0, _ladder_ceiling(max(ends)))
    return {"low_usd_bbl": _num(low), "high_usd_bbl": _num(high)}


def _model_product_rows() -> list[Mapping[str, Any]]:
    rows = []
    for product in series.MODEL_PRODUCTS:
        line = config.DGEC_NOTE_SLATE_LINE[product]
        volume = series.DGEC_NOTE_VOLUME_YIELDS[product]
        mass = 100 * config.DGEC_MASS_YIELDS[line]
        segments = [
            T("The ministry's slate: "),
            N("mass_yield_percent", mass, "percent"),
            T(" percent of the tonne, "),
            N("volume_yield_percent", 100 * volume, "percent"),
            T(" percent of the barrel at ICE's "),
            N("bbl_per_t", config.DGEC_NOTE_PRODUCT_BBL_PER_T[product], "bbl_per_t"),
            T(" bbl/t for the product and the method's "),
            N("brent_bbl_per_t", config.DGEC_BBL_PER_T_BRENT_MARGIN, "bbl_per_t"),
            T(" bbl/t for Brent."),
        ]
        if product == "gasoline":
            segments.append(T(" The method's line is EuroBOB, a blendstock; every price here is a finished gasoline."))
        rows.append({
            "id": product,
            "name": PRODUCT_NAMES[product],
            "ministry_label": series.DGEC_NOTE_MONTHLY_COLUMNS[product][1],
            "slate_line": line,
            "volume_yield": _num(volume),
            "mass_yield_percent": _num(mass),
            "bbl_per_t": config.DGEC_NOTE_PRODUCT_BBL_PER_T[product],
            "factor_citation": dict(FACTOR_CITATIONS[product]),
            "yield_source_segments": segments,
        })
    return rows


def _model_note_preset(inputs: Inputs, month: str) -> Mapping[str, Any]:
    """The latest month, on the ministry's own final monthly prices."""
    printed = series.load("dgec_note_printed_monthly")
    printed["date"] = pd.to_datetime(printed["date"])
    row = printed[printed["date"] == pd.Timestamp(month)]
    vintage = None if row.empty else str(row["vintage"].iloc[0])
    try:
        cracks = series.note_cracks_for_month(month)
        refusal = None
    except KeyError as error:
        cracks, refusal = {}, str(error).strip("'\"")
    values: dict[str, float | None] = {}
    sources: dict[str, Any] = {}
    for product in series.MODEL_PRODUCTS:
        column, label = series.DGEC_NOTE_MONTHLY_COLUMNS[product]
        if product not in cracks:
            values[product] = None
            sources[product] = {"available": False, "segments": [T("No figure for "), D("month", month), T(": " + (refusal or "no note printed it") + ". Left out of the margin, not borrowed from another month.")]}
            continue
        crack = cracks[product]
        values[product] = _num(crack.value)
        sources[product] = {"available": True, "segments": [
            T("The ministry's monthly average for "), D("month", month),
            T(", final in its note of "), D("quotations_vintage", vintage, kind="day"),
            T(": "), W("label", label), T(" at "), N("price_usd_t", row[column].iloc[0], "usd_t"),
            T(" $/t, at ICE's "), N("bbl_per_t", config.DGEC_NOTE_PRODUCT_BBL_PER_T[product], "bbl_per_t"),
            T(" bbl/t, less the ministry's Brent, "), N("brent_usd_bbl", crack.brent_usd_bbl, "usd_bbl"), T(" $/bbl."),
        ]}
    note = [
        T("Cracks from the ministry's final monthly prices for "), D("month", month),
        T(", printed in its note of "), D("quotations_vintage", vintage, kind="day"),
        T(", against the ministry's own Brent; gas and the exchange rate for the same month."),
    ] if vintage else [T("No note printed the ministry's monthly prices for "), D("month", month), T(".")]
    return {
        "crack_source": "dgec_note_printed_monthly",
        "reconstructed": False,
        "cracks": values,
        "crack_sources": sources,
        "note_segments": note,
        "reason_segments": [T("The latest month with both the ministry's margin and its final monthly prices.")],
        "reason_source_url": None,
        "gap_holds": "the part of the barrel the five products do not price and the ministry's gas, freight and insurance costs; the prices are the ministry's own",
    }


def _model_opec_preset(months: Sequence[str], by_id: Mapping[str, Any]) -> Mapping[str, Any]:
    opec = series.model_opec_cracks(months)
    printed = series.load("dgec_note_printed_monthly")
    first_printed = _iso(pd.to_datetime(printed["date"]).min())
    period = _period_segments("period", months)
    values: dict[str, float | None] = {}
    sources: dict[str, Any] = {}
    missing = []
    for product in series.MODEL_PRODUCTS:
        item = opec[product]
        if item["value"] is None:
            values[product] = None
            missing.append(PRODUCT_NAMES[product])
            if item["reason"] == "opec_has_no_column":
                why = [T("No figure for "), *period, T(": OPEC's Rotterdam table quotes no " + PRODUCT_NAMES[product] + ", and no note this study holds prints the ministry's monthly prices before "), D("first_printed_month", first_printed), T(". Left out of the margin, not borrowed from gasoil.")]
            else:
                why = [T("No figure for "), *period, T(": OPEC's Rotterdam table has no " + PRODUCT_NAMES[product] + " quotation in " + _and_list([month_label(m) for m in item["missing_months"]]) + ". Left out of the margin rather than averaged over fewer months.")]
            sources[product] = {"available": False, "segments": why}
            continue
        values[product] = _num(item["value"])
        quoted = [T("OPEC's Rotterdam "), W("label", item["label"]), T(" quotation")]
        spec = [T(", specified as "), W("specification", " then ".join(item["specifications"]))] if item["specifications"] else []
        if len(months) == 1:
            segments = quoted + [T(" for "), D("month", months[0])] + spec + [T(", less FRED's Brent monthly mean for the same month.")]
        else:
            segments = [T("The mean of "), N("months_used", item["months_used"], "count"), T(" monthly cracks of "), *period, T(": ")] + quoted + spec + [T(", less FRED's Brent monthly mean, month by month.")]
        sources[product] = {"available": True, "segments": segments}
    if len(months) == 1:
        event = by_id[MODEL_STRIKES_EVENT]
        figure = next(f for f in event["figures"] if f["key"] == "ara_diesel_crack_usd_bbl")
        reason = [T("The month of the French refinery strikes, when S&P Global reported ARA diesel cracks near "), N("ara_diesel_crack_usd_bbl", figure["value"], "count"), T(" $/bbl on "), D("event_date", event["date"], kind="day"), T(".")]
        note = [T("Cracks from OPEC's Rotterdam monthly quotations for "), D("month", months[0]), T(", each less FRED's Brent for the month; gas and the exchange rate for the same month. No note this study holds prints the ministry's monthly prices before "), D("first_printed_month", first_printed), T(".")]
    else:
        event = by_id[MODEL_PANDEMIC_EVENT]
        reason = [T("The last full year before the pandemic lockdowns of "), D("event_month", _event_day(event)), T(".")]
        note = [T("An average of "), N("months", len(months), "count"), T(" months, not one: OPEC's Rotterdam monthly quotations less FRED's Brent for each month of "), *period, T(", and the gas price and exchange rate averaged the same way. No note this study holds prints the ministry's monthly prices before "), D("first_printed_month", first_printed), T(".")]
    holds = "the part of the barrel the products do not price, the ministry's gas, freight and insurance costs, and the difference between OPEC's quotations and the Reuters prices the ministry uses"
    if missing:
        holds += ", and " + _and_list(missing) + ", which has no price here"
    return {
        "crack_source": "opec_rotterdam_products_monthly",
        "reconstructed": False,
        "cracks": values,
        "crack_sources": sources,
        "note_segments": note,
        "reason_segments": reason,
        "reason_source_url": event["source_url"],
        "gap_holds": holds,
    }


def _model_reconstructed_preset(month: str, by_id: Mapping[str, Any]) -> Mapping[str, Any]:
    recon = series.model_reconstructed_cracks(month)
    weeks = recon["weeks"]
    values: dict[str, float | None] = {}
    sources: dict[str, Any] = {}
    missing = []
    for product in series.MODEL_PRODUCTS:
        item = recon["products"][product]
        if item["value"] is None:
            values[product] = None
            missing.append(PRODUCT_NAMES[product])
            sources[product] = {"available": False, "segments": [
                T("No figure for "), D("month", month),
                T(": the ministry's weekly chart plots Gazole, Eurosuper and Fioul domestique only, and its monthly prices for the month are not in this study's data. Left out of the margin, not borrowed from another month."),
            ]}
            continue
        values[product] = _num(item["value"])
        sources[product] = {"available": True, "segments": [
            T("Reconstructed, read off the ministry's weekly chart and not printed: "), W("label", item["label"]),
            T(" less the chart's Brent, the mean of "), N("weeks", len(item["weekly"]), "count"),
            T(" weeks ending in "), D("month", month), T("."),
        ]}
    first, last = weeks[0], weeks[-1]
    note = [
        T("Reconstructed, not printed: each crack is the mean of "), N("weeks", len(weeks), "count"),
        T(" weekly readings of the ministry's chart, for the weeks ending on the Fridays from "), D("first_week", first, kind="day"),
        T(" to "), D("last_week", last, kind="day"),
    ]
    if recon["printed_weeks"] == 0:
        note += [T(", and the ministry printed none of those weeks.")]
    else:
        note += [T(", "), N("printed_weeks", recon["printed_weeks"], "count"), T(" of them also printed by the ministry.")]
    if pd.Timestamp(first).day < 7:
        before = pd.Timestamp(first).replace(day=1) - pd.offsets.MonthBegin(1)
        note += [T(" The first of those weeks starts in "), D("previous_month", _iso(before)), T(".")]
    for evidence, count in recon["evidence_classes"].items():
        if count == len(weeks):
            note += [T(" " + MODEL_EVIDENCE_WORDS[evidence][0])]
        else:
            note += [T(" "), N("weeks_" + evidence, count, "count"), T(" of them " + ("is" if count == 1 else "are") + " " + MODEL_EVIDENCE_WORDS[evidence][1] + ".")]
    note += [T(" The ministry printed its monthly prices for the month only in a note of the following month, which it deleted and nobody archived, so none is used here; and the chart plots " + _and_list(["no " + name for name in missing]) + ".")]
    event = by_id[MODEL_IRAN_EVENT]
    return {
        "crack_source": "dgec_note_reconstructed_weekly",
        "reconstructed": True,
        "cracks": values,
        "crack_sources": sources,
        "note_segments": note,
        "reason_segments": [T("The month before the latest, in the regime that followed the strikes on Iran of "), D("event_date", event["date"], kind="day"), T(".")],
        "reason_source_url": event["source_url"],
        "gap_holds": "the part of the barrel the products do not price, the ministry's gas, freight and insurance costs, the difference between this study's reading of the weekly chart and the prices the ministry used, and " + _and_list(missing) + ", which have no price here",
        "weeks": {"fridays": weeks, "printed": recon["printed_weeks"], "evidence_classes": recon["evidence_classes"]},
    }


def model(inputs: Inputs) -> Mapping[str, Any]:
    view = inputs.view
    latest = view.margin_month
    payload = _header("model", latest, "the margin model's presets, each input with the sentence saying where it came from, the ministry's slate yields, and the target the breakevens are computed against")
    payload["conventions"] = _conventions()
    events_file = events_anchors.load_events()
    by_id = {e["id"]: e for e in events_file["events"]}
    embedded = config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL
    run = run_verdict(inputs.threshold, inputs.threshold_without_stretch, view, _trailing_rank(inputs))

    payload["title_segments"] = [T("The margin model: cracks times the ministry's yields, less gas")]
    payload["lead_segments"] = [
        T("This page builds a margin of its own: each crack times the ministry's yield for that product. That margin is gross of gas, so gas is subtracted from it here. It is not the ministry's MBR, which is already net of the ministry's own gas at "),
        N("embedded_intensity_mmbtu_per_bbl", embedded, "mmbtu_per_bbl"),
        T(" MMBtu/bbl; the MBR for each preset's month is set under the model with the gap between the two, and nothing is subtracted from it."),
    ]
    payload["basis"] = {
        "margin_basis": engine.MARGIN_GROSS_OF_GAS,
        "residual_usd_bbl": 0.0,
        "official_margin_basis": engine.MARGIN_NET_OF_GAS,
        "official_is_a_step": False,
    }
    products = _model_product_rows()
    covered = sum(series.DGEC_NOTE_VOLUME_YIELDS.values())
    payload["products"] = products
    payload["slate"] = {
        "covered_volume_yield": _num(covered),
        "unattributed_slate_lines": [SLATE_LINE_NAMES[l] for l in series.DGEC_NOTE_UNATTRIBUTED_SLATE_LINES],
        "segments": [
            T("The five products cover "), N("covered_volume_yield_percent", 100 * covered, "percent"),
            T(" percent of the barrel; " + _and_list([SLATE_LINE_NAMES[l] for l in series.DGEC_NOTE_UNATTRIBUTED_SLATE_LINES]) + " have no price here and are not in the model margin."),
        ],
    }
    payload["intensity"] = {
        "study_mmbtu_per_bbl": _num(config.GAS_INTENSITY_MMBTU_PER_BBL),
        "embedded_mmbtu_per_bbl": _num(embedded),
        "source_segments": [
            T("Derived from the EIA's US refinery tables for "),
            N("eia_year", pd.Timestamp(inputs.entry("eia_refinery_fuel_2023")["first_date"]).year, "year"),
            T(", gas burned as fuel and used for hydrogen over crude inputs. A US figure, so an upper end for Europe, where refiners burn more of their own gas; the ministry's margin assumes "),
            N("embedded_intensity_mmbtu_per_bbl", embedded, "mmbtu_per_bbl"), T(" MMBtu/bbl."),
        ],
    }
    payload["other_cost"] = {
        "value_usd_bbl": _num(config.OTHER_VARIABLE_COST_USD_BBL),
        "source_segments": [T("Zero by default, and labelled so: carbon and every cost other than energy are out of scope for this version.")],
    }
    payload["breakeven_target"] = {
        "value_usd_bbl": _num(MODEL_BREAKEVEN_TARGET_USD_BBL),
        "words": "a margin of zero, not a level at which runs get cut",
        "segments": [T("Each breakeven is the input at which the model's margin after gas is zero, every other input held: a margin of zero, not a level at which runs get cut.")],
    }
    payload["run"] = {
        "threshold_identified": run["threshold_identified"],
        "verdict": run["verdict"],
        "run_cut_threshold_usd_bbl": None,
        "headroom_usd_bbl": run["headroom_usd_bbl"],
        "segments": run["segments"],
    }
    if run["threshold_identified"]:
        # The model has no identified level to pass the engine, and inventing
        # one is what this file must never do; a threshold identified later
        # needs its own design pass before it reaches the calculator.
        raise ValueError("model.json is written for an unidentified run cut threshold; revisit docs/design.md Part 8.2 M4 before exporting an identified one")

    mbr_entry = inputs.entry("dgec_mbr_monthly")
    ttf_event = by_id[MODEL_GAS_BECOMES_TTF_EVENT]
    presets = []
    for preset_id, source in MODEL_PRESETS:
        months = MODEL_PRESET_MONTHS[preset_id] or (latest,)
        months = tuple(months)
        if source == "note":
            body = _model_note_preset(inputs, months[0])
        elif source == "opec":
            body = _model_opec_preset(months, by_id)
        else:
            body = _model_reconstructed_preset(months[0], by_id)
        gas = series.model_gas_and_fx(months)
        official = series.model_official_margin(months)
        period = _period_segments("period", months)
        if gas["ttf_eur_mwh"] is None:
            raise KeyError("no World Bank gas price or FRED EUR/USD for every month of preset %s" % preset_id)
        single = len(months) == 1
        ttf_segments = [
            T("Derived, not quoted: the World Bank's European gas price for " if single else "Derived, not quoted: the mean of the World Bank's monthly European gas prices for "),
            *period, T(", "), N("gas_usd_mmbtu", gas["gas_usd_mmbtu"], "usd_mmbtu"),
            T(" $/MMBtu, TTF by the World Bank's own definition since "), D("ttf_definition_month", _event_day(ttf_event)),
            T(", at FRED's exchange rate for the same period and "), N("mmbtu_per_mwh", config.MMBTU_PER_MWH, "mmbtu_per_mwh"),
            T(" MMBtu per MWh. The daily TTF series is not used, because its terms keep it out of this repository."),
        ]
        fx_segments = (
            [T("FRED's US dollars per euro, the mean of the daily rates in "), D("month", months[0]), T(".")]
            if single else
            [T("FRED's US dollars per euro, the mean of the "), N("months", len(months), "count"), T(" monthly means of "), *period, T(".")]
        )
        status_provisional = any(_status_word(mbr_entry, m)[0] for m in months)
        if official["mbr_usd_bbl"] is None:
            official_label = [T("No ministry MBR for "), *period, T(": the published series starts in "), D("mbr_first_month", mbr_entry["first_date"]), T(" and is not extended.")]
        elif single:
            official_label = [T("The ministry's MBR for "), *period, T(", "), W("status_word", "provisional" if status_provisional else "final"), T(", already net of the ministry's own gas allowance")]
        else:
            official_label = [T("The ministry's MBR for "), *period, T(", the mean of the "), N("months_published", official["months_published"], "count"), T(" months it published, already net of the ministry's own gas allowance")]
        ttf = _num(gas["ttf_eur_mwh"])
        eurusd = _num(gas["eurusd"])
        mbr = _num(official["mbr_usd_bbl"])
        preset = {
            "id": preset_id,
            "label": month_label(months[0]) if single else str(pd.Timestamp(months[0]).year) + " average",
            "months": list(months),
            "kind": "month" if single else "year_average",
            **{k: v for k, v in body.items() if k not in ("cracks", "crack_sources", "gap_holds")},
            "inputs": {
                "cracks": body["cracks"],
                "yields": {p["id"]: p["volume_yield"] for p in products},
                "ttf_eur_mwh": ttf,
                "eurusd": eurusd,
                "gas_intensity_mmbtu_per_bbl": _num(config.GAS_INTENSITY_MMBTU_PER_BBL),
                "other_variable_cost_usd_bbl": _num(config.OTHER_VARIABLE_COST_USD_BBL),
            },
            "sources": {
                "cracks": body["crack_sources"],
                "ttf_segments": ttf_segments,
                "eurusd_segments": fx_segments,
            },
            "gas_usd_mmbtu": _num(gas["gas_usd_mmbtu"]),
            "official": {
                "mbr_usd_bbl": mbr,
                "months": len(months),
                "months_published": official["months_published"],
                "provisional": status_provisional,
                "label_segments": official_label,
                "gap_segments": [T("It holds " + body["gap_holds"] + ".")],
            },
            "scale": _model_scale(body["cracks"], ttf, eurusd, mbr),
        }
        presets.append(preset)
    payload["presets"] = presets
    return payload


# ---------------------------------------------------------------------------
# runs.json, docs/design.md Part 8.3
# ---------------------------------------------------------------------------
#
# The Runs and crude demand view. Everything here is crack.analysis as audited
# at Gate 3, written out: the page fits nothing. The response table, the
# threshold verdict and the post break table the view shares with the Now
# section stay in run-economics.json, so the two pages read one copy.

#: The equations of the horse race and the instrument, in SPEC.md section 6.1's
#: order: the planned model first (K24), then the fallback.
RUNS_EQUATIONS: Sequence[tuple[str, str, str]] = (
    ("capacity", analysis.DEPENDENT_CAPACITY, "Utilisation of capacity, the planned model"),
    ("intake_trend", analysis.DEPENDENT_FALLBACK, "Crude intake with a trend"),
)

#: What a coefficient and a forecast error are measured in, per dependent.
RUNS_UNITS: Mapping[str, Mapping[str, str]] = {
    analysis.DEPENDENT_CAPACITY: {
        "coefficient": "percentage points of capacity per $/bbl",
        "rmse": "percentage points of capacity",
    },
    analysis.DEPENDENT_FALLBACK: {
        "coefficient": "percent of runs per $/bbl",
        "rmse": "percent of runs",
    },
}

RUNS_PARTS: Sequence[Mapping[str, str]] = (
    {"id": "response", "label": "Response"},
    {"id": "threshold", "label": "Run cut threshold"},
    {"id": "race", "label": "Horse race and instrument"},
    {"id": "break", "label": "After the strikes on Iran"},
)

#: The competing explanations SPEC.md section 6.4 asks to be set out and not
#: chosen between. Words, no figure.
RUNS_EXPLANATIONS: Sequence[Mapping[str, str]] = (
    {"id": "feedstock", "name": "Feedstock availability", "what": "with Hormuz traffic halted a refiner can face a good margin and still have no suitable crude; the IEA reported refiners outside the Gulf curtailing runs over feedstock availability"},
    {"id": "outages", "name": "Unplanned outages", "what": "one large unit down for a month is worth on the order of the residuals in the table"},
    {"id": "maintenance", "name": "Maintenance", "what": "spring turnarounds move from year to year, and the month terms carry the average season rather than this year's"},
)


def _stamp(value: Any) -> str:
    return str(pd.Timestamp(value).date())


def _runs_series(inputs: Inputs) -> Mapping[str, Any]:
    frame = inputs.frame
    sample = analysis.threshold_sample(frame)[["date", "margin_mean_lagged"]]
    joined = frame.merge(sample, on="date", how="left")
    entry = inputs.entry(analysis.INTAKE_SERIES)
    rows = []
    for _, r in joined.iterrows():
        month = _stamp(r["date"])
        rows.append([
            month,
            _num(r["utilisation_pct"]),
            _num(r["margin_mean_lagged"]),
            _num(r["intake_kb_d"]),
            _num(r["imports_kb_d"]),
            _num(r["capacity_kb_d"]),
            _int(r["capacity_source_year"]),
            bool(r["capacity_assumed"]),
            _status_word(entry, month)[0],
        ])
    first, last = rows[0][0], rows[-1][0]
    steps = [
        "%d-01-01" % (y + analysis.CAPACITY_SOURCE_LAG_YEARS)
        for y in analysis.capacity_step_years()
        if first < "%d-01-01" % (y + analysis.CAPACITY_SOURCE_LAG_YEARS) <= last
    ]
    latest = joined.iloc[-1]
    capacity_year = int(latest["capacity_source_year"])
    assumed = int(joined["capacity_assumed"].sum())
    provisional_from = entry.get("provisional_from")
    stats = analysis.imports_beside_intake(frame)
    cap, fall = inputs.capacity_model, inputs.fallback_model
    ratio = stats["mean_imports_over_intake"]
    opec = series.opec_monthly_cracks()

    sample_segments = [
        T("The sample starts in "),
        N("sample_first_year", int(opec["date"].dt.year.value_counts().sort_index().loc[lambda c: c == 12].index.min()), "year"),
        T(", the owner's choice of the full OPEC record, so the gasoil crack reaches back to "),
        D("crack_first_month", _stamp(opec["date"].min())),
        T(" and JODI's crude intake to "),
        D("jodi_first_month", _stamp(entry["first_date"])),
        T(", while the ministry's margin exists only from "),
        D("margin_first_month", first),
        T(". Every plot and equation on this page that uses the margin therefore starts there, and nothing extends the margin back. JODI runs to "),
        D("jodi_last_month", _stamp(entry["last_date"])),
    ]
    if provisional_from:
        sample_segments += [T(", and the months from "), D("provisional_from", _stamp(provisional_from)), T(" are provisional and may be revised.")]
    else:
        sample_segments += [T(".")]

    capacity_segments = [
        T("Utilisation divides each month's intake by the capacity published for the end of the year before, so every month of "),
        N("latest_year", pd.Timestamp(last).year, "year"),
        T(" uses the "),
        N("capacity_source_year", capacity_year, "year"),
        T(" figure of "),
        N("capacity_kb_d", latest["capacity_kb_d"], "kb_d"),
        T(" kb/d, a published figure and not an assumption: the number of months in this sample with an assumed capacity is "),
        N("capacity_assumed_months", assumed, "count"),
        T(". Capacity falls by a step in "),
    ]
    for i, step in enumerate(steps):
        if i:
            capacity_segments.append(T(" and " if i == len(steps) - 1 else ", "))
        capacity_segments.append(D("capacity_step_month", step))
    capacity_segments.append(T(", and the utilisation line is split there."))

    imports_segments = [
        T("Crude imports averaged "),
        N("mean_imports_over_intake_percent", 100 * ratio, "percent"),
        T(" percent of crude intake over "),
        N("months", stats["months"], "count"),
        T(" months, between "),
        N("min_imports_over_intake_percent", 100 * stats["min_imports_over_intake"], "percent"),
        T(" and "),
        N("max_imports_over_intake_percent", 100 * stats["max_imports_over_intake"], "percent"),
        T(", and the two move together, a correlation of "),
        N("correlation_levels", stats["correlation_levels"], "r2"),
        T(" in levels and "),
        N("correlation_12m_differences", stats["correlation_12m_differences"], "r2"),
        T(" in twelve month changes. So the planned model's "),
        N("kb_d", cap.translation.kb_d, "kb_d", signed=True),
        T(" kb/d of runs reads across to about "),
        N("imports_kb_d", cap.translation.kb_d * ratio, "kb_d", signed=True),
        T(" kb/d of imports, and the trend model's "),
        N("fallback_kb_d", fall.translation.kb_d, "kb_d", signed=True),
        T(" to about "),
        N("fallback_imports_kb_d", fall.translation.kb_d * ratio, "kb_d", signed=True),
        T(". That is arithmetic on the ratio, not a second model, and not evidence that imports respond."),
    ]
    return {
        "first": first,
        "last": last,
        "columns": ["date", "utilisation_percent", "margin_lagged_usd_bbl", "intake_kb_d", "imports_kb_d", "capacity_kb_d", "capacity_source_year", "capacity_assumed", "provisional"],
        "rows": rows,
        "capacity_steps": steps,
        "provisional_from": provisional_from,
        "margin_regressor": "mean of the margin at the average US refinery's gas use over the three previous months",
        "sample_segments": sample_segments,
        "capacity_segments": capacity_segments,
        "imports": {
            "months": int(stats["months"]),
            "mean_imports_over_intake": _num(ratio),
            "min_imports_over_intake": _num(stats["min_imports_over_intake"]),
            "max_imports_over_intake": _num(stats["max_imports_over_intake"]),
            "correlation_levels": _num(stats["correlation_levels"]),
            "correlation_12m_differences": _num(stats["correlation_12m_differences"]),
            "is_a_model": False,
            "segments": imports_segments,
        },
    }


def _episode_rows(inputs: Inputs) -> Mapping[str, Any]:
    """SPEC.md section 6.1: with and without the episodes. The variants are the
    ones analysis.report() ran at Gate 3, nothing else."""
    frame = inputs.frame
    variants = [
        ("capacity", "Utilisation of capacity, the planned model", "episodes", "A term for each episode, the headline", inputs.capacity_model),
        ("capacity", "Utilisation of capacity, the planned model", "no_terms", "No episode terms", analysis.margin_response(frame=frame, label="no regime dummies, full sample", episode_dummies=False)),
        ("capacity", "Utilisation of capacity, the planned model", "dropped", "Episode months left out", analysis.margin_response(frame=frame, label="episode months dropped from the sample", episode_dummies=False, drop_episode_months=True)),
        ("intake_trend", "Crude intake with a trend", "episodes", "A term for each episode, the headline", inputs.fallback_model),
        ("intake_trend", "Crude intake with a trend", "dropped", "Episode months left out", analysis.intake_trend_response(frame=frame, label="episode months dropped from the sample", episode_dummies=False, drop_episode_months=True)),
    ]
    rows = []
    for model_id, model_label, variant, variant_label, model in variants:
        t = model.translation
        rows.append({
            "model": model_id,
            "model_label": model_label,
            "variant": variant,
            "variant_label": variant_label,
            "headline": variant == "episodes",
            "kb_d": _num(t.kb_d),
            "kb_d_low": _num(t.kb_d_low),
            "kb_d_high": _num(t.kb_d_high),
            "t": _num(model.sum_b_t),
            "months": int(model.regression.nobs),
        })
    return {
        "rows": rows,
        "episode_months": analysis.EPISODE_MONTHS,
        "segments": [
            T("Each episode is the "),
            N("episode_months", analysis.EPISODE_MONTHS, "count"),
            T(" months from the pandemic lockdowns of March "),
            N("episode_2020_year", pd.Timestamp(analysis.EPISODES["episode_2020"]).year, "year"),
            T(", Russia's invasion of Ukraine in February "),
            N("episode_2022_year", pd.Timestamp(analysis.EPISODES["episode_2022"]).year, "year"),
            T(" and the strikes on Iran in February "),
            N("episode_2026_year", pd.Timestamp(analysis.EPISODES["episode_2026"]).year, "year"),
            T(". The headline keeps every month and gives each episode its own term; the other rows are the same equations without those terms and without those months, as the analysis ran them. Nothing is chosen from among them."),
        ],
    }


def _endogeneity_segments() -> list[Mapping[str, Any]]:
    return [
        T("Runs move cracks: more runs put more product on the water and weaken the crack, so the margin these equations treat as a cause is partly an effect of runs. That biases every response on this page toward zero, and lagging the margin by one to three months removes only the same month part of it. Read each coefficient as a lower bound in absolute value: an interval that includes zero says this sample cannot see the response, not that there is none."),
    ]


def _fit_line(fit: analysis.HockeyStick, low: float, high: float) -> list[list[float | None]]:
    xs = sorted({float(low), float(min(max(fit.threshold, low), high)), float(high)})
    ys = analysis._kink_design(np.asarray(xs), fit.threshold) @ np.array([fit.level, -fit.slope_below])
    return [[_num(x), _num(y)] for x, y in zip(xs, ys)]


def _runs_threshold(inputs: Inputs) -> Mapping[str, Any]:
    th, wo = inputs.threshold, inputs.threshold_without_stretch
    sample = analysis.threshold_sample(inputs.frame)
    stretch = {m for m in th.months_below if th.longest_run_first <= m <= th.longest_run_last}
    below = set(th.months_below)
    rows = []
    for _, r in sample.iterrows():
        month = _stamp(r["date"])
        rows.append([month, _num(r["margin_mean_lagged"]), _num(r["utilisation_pct"]), month[:7] in stretch, month[:7] in below])
    first_stretch = th.longest_run_first + "-01"
    last_stretch = th.longest_run_last + "-01"

    def fit_row(fit_id: str, label: str, result: analysis.ThresholdResult) -> Mapping[str, Any]:
        return {
            "id": fit_id,
            "label": label,
            "style": "dashed" if fit_id == "every_month" else "dotted",
            "kink_usd_bbl": _num(result.point.threshold),
            "level_percent": _num(result.point.level),
            "slope_below": _num(result.point.slope_below),
            "months": int(result.nobs),
            "months_below": len(result.months_below),
            "kink_r2": _num(result.point.r2),
            "line_r2": _num(result.linear_r2),
            "regressor_low_usd_bbl": _num(result.regressor_min),
            "regressor_high_usd_bbl": _num(result.regressor_max),
            "ci_low_usd_bbl": _num(result.ci_low),
            "ci_high_usd_bbl": _num(result.ci_high),
            "identified": bool(result.identified),
            "line": _fit_line(result.point, result.regressor_min, result.regressor_max),
        }

    grid = np.asarray(th.grid, dtype=float)
    return {
        "columns": ["date", "margin_lagged_usd_bbl", "utilisation_percent", "in_stretch", "below_kink"],
        "rows": rows,
        "fits": [
            fit_row("every_month", "Every month", th),
            fit_row("without_stretch", "Without that stretch", wo),
        ],
        "interval": {
            "low_usd_bbl": _num(th.ci_low),
            "high_usd_bbl": _num(th.ci_high),
            "search_low_usd_bbl": _num(grid[0]),
            "search_high_usd_bbl": _num(grid[-1]),
            "reaches_search_edge": bool(th.ci_high >= grid[-1] - float(grid[1] - grid[0]) or th.ci_low <= grid[0] + float(grid[1] - grid[0])),
            "trimmed": False,
        },
        "stretch": {
            "first_month": first_stretch,
            "last_month": last_stretch,
            "months_in_stretch": int(th.longest_run_below),
            "months_below": len(th.months_below),
        },
        "heading_segments": [T("No run cut level is marked, because none is identified.")],
        "stretch_segments": [
            N("months_below", len(th.months_below), "count"),
            T(" of the "),
            N("months", th.nobs, "count"),
            T(" months sit below the kink fitted on every month, at "),
            N("kink_usd_bbl", th.point.threshold, "usd_bbl"),
            T(" $/bbl, and "),
            N("months_in_stretch", th.longest_run_below, "count"),
            T(" of those "),
            N("months_below", len(th.months_below), "count"),
            T(" are one unbroken stretch, "),
            D("stretch_first_month", first_stretch),
            T(" to "),
            D("stretch_last_month", last_stretch),
            T(", drawn as squares. So the kink is estimated from one episode. Fitted again without that stretch, the kink moves to "),
            N("kink_without_usd_bbl", wo.point.threshold, "usd_bbl"),
            T(" $/bbl and the slope below it goes from "),
            N("slope_below", th.point.slope_below, "slope", signed=True),
            T(" to "),
            N("slope_below_without", wo.point.slope_below, "slope", signed=True),
            T(" percentage points per $/bbl: below the kink, runs rise as the margin falls, the opposite of a run cut."),
        ],
        "interval_segments": [
            T("The shaded span is the "),
            N("interval_level_percent", 95, "count"),
            T(" percent block bootstrap interval of the kink fitted on every month, "),
            N("ci_low_usd_bbl", th.ci_low, "usd_bbl"),
            T(" to "),
            N("ci_high_usd_bbl", th.ci_high, "usd_bbl"),
            T(" $/bbl, from "),
            N("bootstrap_replications", th.replications, "count"),
            T(" replications. The search ran from "),
            N("search_low_usd_bbl", grid[0], "usd_bbl"),
            T(" to "),
            N("search_high_usd_bbl", grid[-1], "usd_bbl"),
            T(" $/bbl, and the interval runs to that edge, so the span is drawn to the edge and not trimmed: the sample cannot see where the interval ends."),
        ],
        "desc_segments": [
            T("Scatter of utilisation, in percent of capacity, against the margin at the average US refinery's gas use averaged over the three previous months, "),
            N("months", th.nobs, "count"),
            T(" months. Hollow circles are months outside "),
            D("stretch_first_month", first_stretch),
            T(" to "),
            D("stretch_last_month", last_stretch),
            T(", filled squares the "),
            N("months_in_stretch", th.longest_run_below, "count"),
            T(" months inside it. A dashed line is the kink fitted on every month, at "),
            N("kink_usd_bbl", th.point.threshold, "usd_bbl"),
            T(" $/bbl; a dotted line the kink fitted without the stretch, at "),
            N("kink_without_usd_bbl", wo.point.threshold, "usd_bbl"),
            T(" $/bbl, sloping the other way below it. A span marks the interval "),
            N("ci_low_usd_bbl", th.ci_low, "usd_bbl"),
            T(" to "),
            N("ci_high_usd_bbl", th.ci_high, "usd_bbl"),
            T(" $/bbl, reaching the edge of the range searched. Every point is in the table under the chart."),
        ],
    }


def _runs_race(inputs: Inputs) -> Mapping[str, Any]:
    hf = inputs.horse_frame
    equations = []
    all_pairs: list[analysis.LossDifferential] = []
    gasoil_vs_margin: list[analysis.LossDifferential] = []
    for eq_id, dependent, label in RUNS_EQUATIONS:
        results = inputs.horse_race(dependent)
        pairs = [analysis.loss_differential(results[i], results[j]) for i in range(len(results)) for j in range(i + 1, len(results))]
        all_pairs += pairs
        gasoil_vs_margin += [p for p in pairs if p.first == "horse A"]
        long_run = analysis.gasoil_long_sample(dependent, frame=hf)
        first = results[0]
        episodes_out = analysis.episode_mask(pd.DatetimeIndex(first.oos.dates))
        horses = []
        for r in results:
            horse = {
                "key": r.horse.key,
                "name": r.horse.name,
                "substitution": bool(r.horse.substitution),
                "coefficient": _num(r.model.sum_b),
                "se": _num(r.model.sum_b_se),
                "t": _num(r.model.sum_b_t),
                "r2": _num(r.model.regression.r2),
                "oos_rmse": _num(r.oos.rmse),
            }
            if r.horse.substitution:
                horse["substitution_segments"] = [
                    T("The ministry's margin is already net of the ministry's gas, so a margin after that gas would be horse B again; this is that margin re-priced at the average US refinery's gas use of "),
                    N("study_intensity_mmbtu_per_bbl", config.GAS_INTENSITY_MMBTU_PER_BBL, "mmbtu_per_bbl"),
                    T(" MMBtu/bbl instead of the ministry's "),
                    N("ministry_intensity_mmbtu_per_bbl", config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL, "mmbtu_per_bbl"),
                    T(" MMBtu/bbl."),
                ]
            horses.append(horse)
        equations.append({
            "id": eq_id,
            "label": label,
            "dependent": dependent,
            "coefficient_unit": RUNS_UNITS[dependent]["coefficient"],
            "rmse_unit": RUNS_UNITS[dependent]["rmse"],
            "first_month": first.model.first_month,
            "last_month": first.model.last_month,
            "months": int(first.model.regression.nobs),
            "newey_west_lag": int(first.model.regression.nw_lag),
            "forecasts": int(first.oos.n_forecasts),
            "first_forecast": first.oos.first_forecast,
            "last_forecast": first.oos.last_forecast,
            "mean_benchmark_rmse": _num(first.oos.mean_benchmark_rmse),
            "horses": horses,
            "long_sample": {
                "first_month": long_run.model.first_month,
                "last_month": long_run.model.last_month,
                "months": int(long_run.model.regression.nobs),
                "coefficient": _num(long_run.model.sum_b),
                "se": _num(long_run.model.sum_b_se),
                "t": _num(long_run.model.sum_b_t),
                "r2": _num(long_run.model.regression.r2),
                "oos_rmse": _num(long_run.oos.rmse),
                "in_the_race": False,
            },
            "pairs": [
                {
                    "first": p.first[-1],
                    "second": p.second[-1],
                    "observed_gap_percent": _num(p.observed_gap_pct),
                    "detectable_gap_percent": _num(p.detectable_gap_pct),
                    "power": _num(p.power_at_observed),
                    "forecasts_for_target_power": _num(p.forecasts_for_target_power),
                    "t": _num(p.t),
                    "distinguishable": bool(p.distinguishable),
                }
                for p in pairs
            ],
            "caption_segments": [
                T("On "),
                W("label", label.lower()),
                T(", "),
                D("first_month", first.model.first_month),
                T(" to "),
                D("last_month", first.model.last_month),
                T(", the same "),
                N("months", first.model.regression.nobs, "count"),
                T(" months for every horse. Coefficients are the sum of the three lags in "),
                W("coefficient_unit", RUNS_UNITS[dependent]["coefficient"]),
                T("; errors in "),
                W("rmse_unit", RUNS_UNITS[dependent]["rmse"]),
                T(", over "),
                N("forecasts", first.oos.n_forecasts, "count"),
                T(" one month ahead forecasts from "),
                D("first_forecast", first.oos.first_forecast),
                T(" to "),
                D("last_forecast", first.oos.last_forecast),
                T(". The rows keep the order A, B, C and are not ranked by any column."),
            ],
            "oos_segments": [
                T("Every one of those "),
                N("forecasts", first.oos.n_forecasts, "count"),
                T(" forecast months falls in or after the pandemic, and "),
                N("forecasts_in_episodes", int(episodes_out["any_episode"].sum()), "count"),
                T(" of them inside an episode: the out of sample period is the crisis period, not a quiet holdout."),
            ],
        })

    size = 0.05
    powers = [p.power_at_observed for p in all_pairs]
    distinguishable = any(p.distinguishable for p in all_pairs)
    needed = [p.forecasts_for_target_power for p in all_pairs if math.isfinite(p.forecasts_for_target_power)]
    sentence = [
        T("This sample cannot tell the horses apart. None of the "),
        N("pairs", len(all_pairs), "count"),
        T(" comparisons of forecast errors, three on each equation, is distinguishable from zero, and against the gaps they found those tests have power of "),
        N("power_low", min(powers), "power"),
        T(" to "),
        N("power_high", max(powers), "power"),
        T(", where a test's size of "),
        N("size", size, "power"),
        T(" is the rate at which it reports a difference that does not exist. Reaching "),
        N("power_target_percent", 100 * analysis.POWER_TARGET, "count"),
        T(" percent power would take "),
        N("forecasts_needed_low", min(needed), "count"),
        T(" to "),
        N("forecasts_needed_high", max(needed), "count"),
        T(" monthly forecasts, against the "),
        N("forecasts", equations[0]["forecasts"], "count"),
        T(" this sample has. That is not a finding that the three are equal."),
    ] if not distinguishable else [
        T("At least one of the "),
        N("pairs", len(all_pairs), "count"),
        T(" comparisons of forecast errors is distinguishable from zero; the power table says which."),
    ]
    a_pairs_distinguishable = any(p.distinguishable for p in gasoil_vs_margin)
    a_powers = [p.power_at_observed for p in gasoil_vs_margin]
    honest = [
        T("Did the margin beat the raw gasoil crack? It did not beat it and was not beaten by it: on both equations neither margin's forecast errors differ distinguishably from the crack's, and those "),
        N("gasoil_pairs", len(gasoil_vs_margin), "count"),
        T(" tests had power of only "),
        N("gasoil_power_low", min(a_powers), "power"),
        T(" to "),
        N("gasoil_power_high", max(a_powers), "power"),
        T(". The reason is power, not equality."),
    ] if not a_pairs_distinguishable else [
        T("On at least one equation the margin and the raw gasoil crack forecast runs distinguishably differently; the power table says which pair."),
    ]

    margin = analysis.margin_frame()
    before = margin.loc[margin["date"] < "2022-01-01", "gas_wedge_usd_bbl"].mean()
    during = margin.loc[(margin["date"] >= "2022-01-01") & (margin["date"] < "2023-01-01"), "gas_wedge_usd_bbl"].mean()
    th = inputs.threshold
    gives = [
        [
            T("What the margin gives that the raw crack cannot, none of it a claim about forecasting. A level with a sign: a crack is one product against crude, while the margin is what the whole barrel earns after crude and the ministry's gas, so only the margin can be set against a cash cost and only its sign means a refinery loses on the barrel."),
        ],
        [
            T("The gas wedge: the extra gas a refinery pays at the average US refinery's use, over the ministry's own allowance, averaged "),
            N("wedge_before_usd_bbl", before, "usd_bbl"),
            T(" $/bbl before "),
            N("wedge_year", 2022, "year"),
            T(" and "),
            N("wedge_during_usd_bbl", during, "usd_bbl"),
            T(" $/bbl during "),
            N("wedge_year", 2022, "year"),
            T(". The same gasoil crack was worth that much less to a refinery that buys its gas, and no crack shows it."),
        ],
        [
            T("A threshold in dollars: the question of how far today is from the level at which runs get cut can only be asked of a margin. On this sample that level is "),
            W("verdict", "unidentified" if not th.identified else "identified"),
            T(", so the page asks it and prints no answer."),
        ],
    ]
    return {
        "size": size,
        "power_domain": [0, 1],
        "power_target_percent": int(round(100 * analysis.POWER_TARGET)),
        "any_distinguishable": bool(distinguishable),
        "sentence_segments": sentence,
        "margin_against_crack_segments": honest,
        "equations": equations,
        "gives": gives,
        "wedge_before_2022_usd_bbl": _num(before),
        "wedge_2022_usd_bbl": _num(during),
    }


def _runs_instrument(inputs: Inputs) -> Mapping[str, Any]:
    hf = inputs.horse_frame
    results = [(eq_id, label, analysis.gas_instrument(frame=hf, dependent=dependent)) for eq_id, dependent, label in RUNS_EQUATIONS]
    ladder = []
    for i, rung in enumerate(results[0][2].control_ladder):
        for _, _, iv in results[1:]:
            other = iv.control_ladder[i]
            if abs(float(other["f"]) - float(rung["f"])) > 1e-9:
                raise ValueError("the first stage differs between equations at %r, and it contains no dependent" % rung["controls"])
        ladder.append({
            "controls": str(rung["controls"]),
            "coefficient": _num(rung["coefficient"]),
            "se": _num(rung["se"]),
            "f": _num(rung["f"]),
            "partial_r2": _num(rung["partial_r2"]),
            "used_by": [label for _, label, iv in results if iv.control_ladder[i]["is_the_spec_equation"]],
        })
    iv0 = results[0][2]
    by_label = {r["controls"]: r for r in ladder}
    spec_f = [iv.first_stage_f for _, _, iv in results]
    equations = [
        {
            "id": eq_id,
            "label": label,
            "coefficient_unit": RUNS_UNITS[iv.dependent]["coefficient"],
            "months": int(iv.nobs),
            "first_stage_f": _num(iv.first_stage_f),
            "weak": bool(iv.weak),
            "ols_coefficient": _num(iv.ols_coefficient),
            "ols_se": _num(iv.ols_se),
            "iv_coefficient": _num(iv.iv_coefficient),
            "iv_se": _num(iv.iv_se),
            "iv_used": False,
        }
        for eq_id, label, iv in results
    ]
    constant = ladder[0]
    months_rung = ladder[1]
    episodes_rung = ladder[2]
    trend_rung = ladder[3]
    return {
        "f_bar": _num(analysis.FIRST_STAGE_F_BAR),
        "ladder": ladder,
        "equations": equations,
        "sentence_segments": [
            T("The gas price was tried as an instrument for the margin, because gas moved on pipeline cuts in "),
            N("year_2022", 2022, "year"),
            T(" and LNG disruption in "),
            N("year_2026", 2026, "year"),
            T(" rather than on NWE runs. Its first stage F is a property of the control set, not of the instrument: "),
            N("f_constant", constant["f"], "f_stat"),
            T(" with a constant alone, "),
            N("f_months", months_rung["f"], "f_stat"),
            T(" with the month terms, "),
            N("f_episodes", episodes_rung["f"], "f_stat"),
            T(" once the episode terms go in, and "),
            N("f_trend", trend_rung["f"], "f_stat"),
            T(" with a trend as well."),
        ],
        "diagnosis_segments": [
            T("The episode terms take the F down because the instrument's variation is the "),
            N("year_2022", 2022, "year"),
            T(" shock they remove: the gas price's standard deviation is "),
            N("sd_in_episodes", iv0.instrument_sd_in_episodes, "usd_mmbtu"),
            T(" $/MMBtu inside the "),
            N("months_in_episodes", iv0.instrument_months_in_episodes, "count"),
            T(" episode months against "),
            N("sd_outside_episodes", iv0.instrument_sd_outside_episodes, "usd_mmbtu"),
            T(" outside them, and its highest three month mean, "),
            N("instrument_max", iv0.instrument_max, "usd_mmbtu"),
            T(" $/MMBtu, is the one that ends before "),
            D("instrument_max_month", iv0.instrument_max_month + "-01"),
            T(". Under each equation's own controls the F is "),
            N("f_spec_low", min(spec_f), "f_stat"),
            T(" or "),
            N("f_spec_high", max(spec_f), "f_stat"),
            T(", below the bar of "),
            N("f_bar", analysis.FIRST_STAGE_F_BAR, "count"),
            T(", and it is below it on a constant and the month terms too. The instrument is weak, the two stage estimates are printed and not used, and the headline stays ordinary least squares with the bias toward zero unremoved."),
        ],
        "exclusion_segments": [
            T("It would also need gas to reach runs only through the margin, which this study doubts: gas is a hydrogen feedstock as well as a fuel, and a gas shock arrives inside a wider energy shock that moves product demand at the same time."),
        ],
    }


def _runs_break(inputs: Inputs) -> Mapping[str, Any]:
    br = inputs.break_result
    entry = inputs.entry(analysis.INTAKE_SERIES)
    pre = [[r["date"], _num(r["residual"])] for _, r in br.pre_fit.iterrows()]
    post = []
    for _, r in br.residuals.iterrows():
        provisional, word = _status_word(entry, str(r["date"]))
        post.append([str(r["date"]), _num(r["residual"]), provisional])
    start_2022 = pd.Timestamp(analysis.EPISODES["episode_2022"])
    end_2022 = start_2022 + pd.DateOffset(months=analysis.EPISODE_MONTHS - 1)
    below = int((br.residuals["residual"] < 0).sum())
    return {
        "columns_pre": ["date", "residual_pp"],
        "columns_post": ["date", "residual_pp", "provisional"],
        "pre_rows": pre,
        "post_rows": post,
        "pre_residual_sd_pp": _num(br.pre_residual_sd),
        "n_pre": int(br.n_pre),
        "n_post": int(br.n_post),
        "min_post_months": int(br.min_post_months),
        "tested": not br.too_short,
        "brackets": [
            {
                "id": "episode_2022",
                "start": _stamp(start_2022),
                "end": _stamp(end_2022),
                "label_segments": [T("The "), N("year_2022", 2022, "year"), T(" episode")],
            },
            {
                "id": "after_break",
                "start": str(br.residuals["date"].iloc[0]),
                "end": str(br.residuals["date"].iloc[-1]),
                "label_segments": [T("After the break, not a test")],
            },
        ],
        "heading_segments": [
            T("Runs against what the margin implies, fitted on the months before March "),
            N("year_2026", 2026, "year"),
            T(", with no episode terms"),
        ],
        "fit_segments": [
            T("The equation is the planned model without its episode terms, fitted on the "),
            N("n_pre", br.n_pre, "count"),
            T(" months to February "),
            N("year_2026", 2026, "year"),
            T(" only; a term for the episode after the strikes would absorb exactly the gap this looks for. Its in sample residuals have a standard deviation of "),
            N("pre_residual_sd_pp", br.pre_residual_sd, "pp"),
            T(" percentage points. The "),
            N("n_post", br.n_post, "count"),
            T(" months after the break are predicted out of sample, and runs sat below the prediction in "),
            N("months_below", below, "count"),
            T(" of them."),
        ],
        "explanations_segments": [
            T("Three explanations could put runs below what the margin implies after the strikes, and "),
            N("n_post", br.n_post, "count"),
            T(" months cannot separate them, so this study sets them out and does not choose."),
        ],
        "explanations": [dict(x) for x in RUNS_EXPLANATIONS],
        "events": [dict(e) for e in br.explanations],
        "reopens_segments": [
            T("The question can be asked when "),
            N("min_post_months", br.min_post_months, "count"),
            T(" months after the break have runs data."),
        ],
        "desc_segments": [
            T("Residuals of utilisation against the margin, in percentage points of capacity, monthly from "),
            D("first_month", pre[0][0]),
            T(". A solid line for the "),
            N("n_pre", br.n_pre, "count"),
            T(" months the equation was fitted on, a separate dashed line with squares for the "),
            N("n_post", br.n_post, "count"),
            T(" months after the break, never joined. Brackets under the axis mark the "),
            N("year_2022", 2022, "year"),
            T(" episode and the months after the break. No mark is highlighted, because no verdict exists. Every value is in the table under the chart."),
        ],
    }


def runs(inputs: Inputs) -> Mapping[str, Any]:
    view = inputs.view
    payload = _header("runs", view.runs_data_date, "the Runs and crude demand view: runs and imports against the lagged margin, the run cut threshold scatter, the response with and without the episodes, the horse race with its power, the instrument, and the 2026 residuals")
    payload["conventions"] = _conventions()
    cap, fall = inputs.capacity_model, inputs.fallback_model
    payload["parts"] = [dict(p) for p in RUNS_PARTS]
    payload["title_segments"] = [
        T("A "),
        N("move_usd_bbl", cap.translation.move_usd_bbl, "count"),
        T(" $/bbl rise in the margin after gas is worth "),
        N("kb_d", cap.translation.kb_d, "kb_d", signed=True),
        T(" kb/d of NWE crude runs on the planned model, interval "),
        N("kb_d_low", cap.translation.kb_d_low, "kb_d", signed=True),
        T(" to "),
        N("kb_d_high", cap.translation.kb_d_high, "kb_d", signed=True),
        T(", and "),
        N("fallback_kb_d", fall.translation.kb_d, "kb_d", signed=True),
        T(" kb/d on crude intake with a trend, interval "),
        N("fallback_kb_d_low", fall.translation.kb_d_low, "kb_d", signed=True),
        T(" to "),
        N("fallback_kb_d_high", fall.translation.kb_d_high, "kb_d", signed=True),
        T("."),
    ]
    payload["series"] = _runs_series(inputs)
    payload["episodes"] = _episode_rows(inputs)
    payload["endogeneity_segments"] = _endogeneity_segments()
    payload["threshold"] = _runs_threshold(inputs)
    payload["race"] = _runs_race(inputs)
    payload["instrument"] = _runs_instrument(inputs)
    payload["break"] = _runs_break(inputs)
    return payload


# ---------------------------------------------------------------------------
# events.json, docs/design.md Part 8.4
# ---------------------------------------------------------------------------
#
# One panel per event of data/seed/events.json whose kind is an event rather
# than a break: the cracks, the margin after gas and utilisation from
# EVENT_MONTHS_BEFORE months before the event's month to EVENT_MONTHS_AFTER
# after it, SPEC.md section 6.5. EVERY WINDOW IS THE FULL THIRTEEN MONTHS. A
# month a series does not cover is null, never zero and never filled, and the
# panel carries a sentence per series naming what is missing and why (E6).

EVENT_MONTHS_BEFORE = 6
EVENT_MONTHS_AFTER = 6

#: Why a series has nothing after its last month, in words, per series id.
EVENT_SERIES_STOPS: Mapping[str, str] = {
    "monthly_cracks": "the OPEC archive holds no later issue",
    "margin": "the ministry has published no later month",
    "utilisation": "JODI has published no later month",
    "weekly": "no later note has been collected",
}


def _event_month_span(first: pd.Timestamp, last: pd.Timestamp) -> int:
    return (last.year - first.year) * 12 + last.month - first.month + 1


def _event_missing_segments(
    name: str, series_id: str, months: Sequence[pd.Timestamp], present: Sequence[bool],
    first: str, last: str, data_last: pd.Timestamp,
) -> list[Mapping[str, Any]] | None:
    """The sentence naming what a monthly series lacks inside one window, or
    None when every month has a value. Before the series, after it inside the
    data, and after the latest month the study holds, each said separately."""
    if all(present):
        return None
    s_first, s_last = pd.Timestamp(first), pd.Timestamp(last)
    before = [m for m, ok in zip(months, present) if not ok and m < s_first]
    after = [m for m, ok in zip(months, present) if not ok and s_last < m <= data_last]
    future = [m for m, ok in zip(months, present) if not ok and m > data_last and m > s_last]
    inside = [m for m, ok in zip(months, present) if not ok and s_first <= m <= s_last]
    out: list[Mapping[str, Any]] = [T(name[:1].upper() + name[1:] + ": ")]
    clauses: list[list[Mapping[str, Any]]] = []
    if len(before) == len(months):
        clauses.append([T("the series starts in "), D("series_first", first), T(", after this window ends")])
    elif len(before) == 1:
        clauses.append([T("the series starts in "), D("series_first", first), T(", so "), D("missing_first", _iso(before[0])), T(" has none")])
    elif before:
        clauses.append([T("the series starts in "), D("series_first", first), T(", so the "), N("months_before_series", len(before), "count"), T(" months of this window before it have none")])
    if len(after) == 1:
        clauses.append([T("the series stops at "), D("series_last", last), T(", so "), D("missing_first", _iso(after[0])), T(" has none, because %s" % EVENT_SERIES_STOPS[series_id])])
    elif after:
        clauses.append([T("the series stops at "), D("series_last", last), T(", so the "), N("months_after_series", len(after), "count"), T(" months from "), D("missing_first", _iso(after[0])), T(" to "), D("missing_last", _iso(after[-1])), T(" have none, because %s" % EVENT_SERIES_STOPS[series_id])])
    if inside:
        clauses.append([T("the series has no value in "), N("months_missing_inside", len(inside), "count"), T(" months inside its own span")])
    if len(future) == 1:
        clauses.append([D("future_month", _iso(future[0])), T(" is after the latest data this study holds")])
    elif future:
        clauses.append([T("the "), N("months_after_data", len(future), "count"), T(" months after "), D("data_last_month", _iso(data_last)), T(" are after the latest data this study holds")])
    for i, clause in enumerate(clauses):
        if i:
            out.append(T("; and "))
        out += clause
    out.append(T(". Nothing fills them."))
    return out


def events(inputs: Inputs) -> Mapping[str, Any]:
    """The Events view: one thirteen month panel per event, Part 8.4."""
    events_file = events_anchors.load_events()
    monthly = series.opec_monthly_cracks().sort_values("date").reset_index(drop=True)
    monthly["date"] = pd.to_datetime(monthly["date"])
    monthly = monthly.dropna(subset=[analysis.CRACK_GASOIL, analysis.CRACK_GASOLINE], how="all")
    margin = inputs.margin.sort_values("date").reset_index(drop=True)
    margin["date"] = pd.to_datetime(margin["date"])
    margin = margin.dropna(subset=["mbr_usd_bbl"])
    frame = inputs.frame.sort_values("date").reset_index(drop=True)
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.dropna(subset=["utilisation_pct"])
    weekly = inputs.weekly.sort_values("date").reset_index(drop=True)
    intake_entry = inputs.entry(analysis.INTAKE_SERIES)

    spans = {
        "monthly_cracks": (_iso(monthly["date"].min()), _iso(monthly["date"].max())),
        "margin": (_iso(margin["date"].min()), _iso(margin["date"].max())),
        "utilisation": (_iso(frame["date"].min()), _iso(frame["date"].max())),
        "weekly": (_iso(weekly["date"].min()), _iso(weekly["date"].max())),
    }
    data_last = max(pd.Timestamp(last) for _, last in spans.values())
    data_last_month = data_last.to_period("M").to_timestamp()
    names = {
        "monthly_cracks": "OPEC's monthly gasoil and gasoline cracks",
        "margin": "the ministry's margin",
        "utilisation": "utilisation",
        "weekly": "this study's weekly reading of the ministry's chart",
    }
    steps = sorted(
        "%d-01-01" % (y + analysis.CAPACITY_SOURCE_LAG_YEARS)
        for y in analysis.capacity_step_years()
        if spans["utilisation"][0] < "%d-01-01" % (y + analysis.CAPACITY_SOURCE_LAG_YEARS) <= spans["utilisation"][1]
    )
    by_month = {
        "monthly": monthly.set_index("date"),
        "margin": margin.set_index("date"),
        "frame": frame.set_index("date"),
    }

    payload = _header("events", _iso(data_last), "the Events view: for each event of data/seed/events.json, the cracks, the margin after gas and utilisation from six months before its month to six months after, with every missing month named")
    payload["conventions"] = _conventions()
    payload["title_segments"] = [
        T("What the cracks, the margin after gas and utilisation did from "),
        N("months_before", EVENT_MONTHS_BEFORE, "count"), T(" months before to "),
        N("months_after", EVENT_MONTHS_AFTER, "count"), T(" months after each event."),
    ]
    payload["lead_segments"] = [
        T("Each panel shows levels around a dated event, in the source's own units: what moved around the date, never an estimate of the event's effect, because other things happened in the same months. Every window runs the full "),
        N("window_months", EVENT_MONTHS_BEFORE + EVENT_MONTHS_AFTER + 1, "count"),
        T(" months; a month a series does not cover is left empty and named, never filled."),
    ]
    payload["window"] = {"months_before": EVENT_MONTHS_BEFORE, "months_after": EVENT_MONTHS_AFTER}
    payload["series"] = [
        {"id": sid, "name": names[sid], "first": first, "last": last}
        for sid, (first, last) in spans.items()
    ]
    payload["data_last"] = _iso(data_last)
    payload["capacity_steps"] = steps
    payload["margin_segments"] = [
        T("Both lines are after gas and nothing is subtracted twice: the ministry's margin is already net of its own "),
        N("ministry_intensity", config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL, "mmbtu_per_bbl"),
        T(" MMBtu/bbl of gas, and the dotted line is the same margin at the average US refinery's "),
        N("study_intensity", config.GAS_INTENSITY_MMBTU_PER_BBL, "mmbtu_per_bbl"),
        T(" MMBtu/bbl, the extra gas priced at each month's European gas price."),
    ]
    payload["monthly_columns"] = [
        "date", "offset_months", "gasoil_usd_bbl", "gasoline_usd_bbl", "mbr_usd_bbl",
        "margin_us_gas_usd_bbl", "utilisation_percent", "utilisation_provisional",
    ]
    payload["weekly_columns"] = [
        "date", "gasoil_usd_bbl", "gasoline_usd_bbl", "printed_gasoil_usd_bbl",
        "printed_gasoline_usd_bbl", "evidence_class",
    ]
    payload["least_defended_class"] = "single_geometry_oldest"
    payload["newest_class"] = "single_geometry_newest"

    out_events = []
    for event in events_file["events"]:
        if event["kind"] not in HISTORY_EVENT_KINDS or event.get("layer") == "daily":
            continue
        day = _event_day(event)
        precision = event.get("date_precision")
        month = pd.Timestamp(day).to_period("M").to_timestamp()
        months = [month + pd.DateOffset(months=k) for k in range(-EVENT_MONTHS_BEFORE, EVENT_MONTHS_AFTER + 1)]
        window_first, window_last_month = months[0], months[-1]
        window_end = window_last_month + pd.DateOffset(months=1) - pd.DateOffset(days=1)

        def value(table: str, stamp: pd.Timestamp, column: str) -> float | None:
            frame_ = by_month[table]
            return _num(frame_.at[stamp, column]) if stamp in frame_.index else None

        rows = []
        for k, stamp in zip(range(-EVENT_MONTHS_BEFORE, EVENT_MONTHS_AFTER + 1), months):
            iso = _iso(stamp)
            util = value("frame", stamp, "utilisation_pct")
            rows.append([
                iso, k,
                value("monthly", stamp, analysis.CRACK_GASOIL),
                value("monthly", stamp, analysis.CRACK_GASOLINE),
                value("margin", stamp, "mbr_usd_bbl"),
                value("margin", stamp, "margin_study_intensity_usd_bbl"),
                util,
                None if util is None else _status_word(intake_entry, iso)[0],
            ])
        in_window = weekly[(weekly["date"] >= window_first) & (weekly["date"] <= window_end)]
        weekly_rows = [
            [_iso(r["date"]), _num(r[analysis.CRACK_GASOIL]), _num(r[analysis.CRACK_GASOLINE]),
             _num(r["printed_gasoil_usd_bbl"]), _num(r["printed_gasoline_usd_bbl"]),
             None if _is_missing(r["evidence_class"]) else str(r["evidence_class"])]
            for _, r in in_window.iterrows()
        ]

        missing = []
        for sid, columns in (("monthly_cracks", (2, 3)), ("margin", (4,)), ("utilisation", (6,))):
            present = [any(row[c] is not None for c in columns) for row in rows]
            segments = _event_missing_segments(names[sid], sid, months, present, spans[sid][0], spans[sid][1], data_last_month)
            if segments:
                missing.append({"series": sid, "segments": segments})
        w_first, w_last = spans["weekly"]
        if not weekly_rows:
            if window_end < pd.Timestamp(w_first):
                w_segments = [T("This study's weekly reading of the ministry's chart starts on "), D("series_first", w_first, kind="day"), T(", after this window ends, so this window has no weekly cracks.")]
            else:
                w_segments = [T("This study's weekly reading of the ministry's chart ends on "), D("series_last", w_last, kind="day"), T(", before this window starts.")]
            missing.append({"series": "weekly", "segments": w_segments})
        else:
            parts = []
            if window_first < pd.Timestamp(w_first):
                parts.append([T(" starts on "), D("series_first", w_first, kind="day"), T(", so the weeks of this window before it have none")])
            if window_end > pd.Timestamp(w_last):
                parts.append([T(" ends on "), D("series_last", w_last, kind="day"), T(", so the weeks after it have none: %s" % EVENT_SERIES_STOPS["weekly"])])
            if parts:
                w_segments = [T("This study's weekly reading of the ministry's chart")]
                for i, part in enumerate(parts):
                    if i:
                        w_segments.append(T(", and"))
                    w_segments += part
                w_segments.append(T(". Nothing fills them."))
                missing.append({"series": "weekly", "segments": w_segments})

        if missing:
            listed = [m["series"] for m in missing]
            coverage = [T("Missing in part or in whole: ")]
            for i, sid in enumerate(listed):
                if i:
                    coverage.append(T(" and " if i == len(listed) - 1 else ", "))
                coverage.append(W("series_name", names[sid]))
            coverage.append(T("."))
        else:
            coverage = [T("Every series has a value in every month of this window.")]

        if precision == "day":
            precision_segments = [T("Dated to the day by the source, "), D("date", day, kind="day"), T(", and drawn as a rule at that day.")]
        else:
            precision_segments = [T("Dated to the month, "), D("date", day), T(": the source gives no single day, so the whole month is bracketed under the axis rather than a day being invented.")]

        out_events.append({
            "id": event["id"],
            "date": day,
            "precision": precision,
            "label": D("date", day, kind="day" if precision == "day" else "month")["label"],
            "short": EVENT_SHORT_NAMES[event["id"]],
            "name": event["label"],
            "kind": event["kind"],
            "what": event.get("what"),
            "precision_segments": precision_segments,
            "source_url": event["source_url"],
            "source_title": event.get("source_title"),
            "source_publisher": event.get("source_publisher"),
            "additional_sources": [
                {"url": a["url"], "title": a.get("title"), "publisher": a.get("publisher"), "why": a.get("why")}
                for a in (event.get("additional_sources") or [])
            ],
            "window": {
                "first": _iso(window_first),
                "last": _iso(window_last_month),
                "end": _iso(window_end),
                "event_month": _iso(month),
                "label_segments": [D("window_first", _iso(window_first)), T(" to "), D("window_last", _iso(window_last_month))],
            },
            "capacity_steps": [s for s in steps if _iso(window_first) <= s <= _iso(window_end)],
            "rows": rows,
            "weekly_rows": weekly_rows,
            "missing": missing,
            "coverage_segments": coverage,
        })
    out_events.sort(key=lambda e: e["date"])
    payload["events"] = out_events

    # The entries of events.json that are breaks, not events: no panel, and the
    # page says where they are instead of leaving them out silently.
    payload["not_panels"] = [
        {"id": e["id"], "date": _event_day(e), "label": D("date", _event_day(e), kind="day" if e.get("date_precision") == "day" else "month")["label"], "name": e["label"], "kind": e["kind"]}
        for e in events_file["events"]
        if e["kind"] not in HISTORY_EVENT_KINDS or e.get("layer") == "daily"
    ]
    payload["not_panels_segments"] = [
        T("The other "), N("not_panels", len(payload["not_panels"]), "count"),
        T(" entries of the events file are breaks in a series, not events in the market: specification changes, gas definition changes, the margin's method date and the two changes to the ICE gasoil contract. They have no window here; the Method view lists each with where it is drawn."),
    ]
    return payload


# ---------------------------------------------------------------------------
# method.json, docs/design.md Part 8.5
# ---------------------------------------------------------------------------
#
# The Method view as a document: sections of blocks, every figure a value
# segment or a value cell computed here from config, series, analysis or the
# manifest, never typed. A block of type "ref" names a list of segments another
# artifact already carries, so the Method view prints the sentence the view
# that owns it prints and the two cannot drift. The fields the Gate 4 audit
# found orphaned (the ICE factor citations and the printed $/t prices in
# margin-stack.json, R2 and the Newey-West lag in run-economics.json) are read
# by the Method view from those artifacts, blocks of type "reads", not copied.


def _P(*segments: Mapping[str, Any]) -> Mapping[str, Any]:
    return {"type": "p", "segments": list(segments)}


def _ref(artifact: str, *path: Any) -> Mapping[str, Any]:
    return {"type": "ref", "artifact": artifact, "path": list(path)}


def _cell_text(text: str) -> Mapping[str, Any]:
    return {"text": text}


def _cell_value(field: str, value: Any, fmt: str, signed: bool = False) -> Mapping[str, Any]:
    return dict(N(field, value, fmt, signed=signed))


def _cell_link(text: str, url: str) -> Mapping[str, Any]:
    return {"text": text, "url": url}


def _cell_segments(*segments: Mapping[str, Any]) -> Mapping[str, Any]:
    return {"segments": list(segments)}


def _table(caption: str, columns: Sequence[tuple[str, str, bool]], rows: Sequence[Sequence[Mapping[str, Any]]]) -> Mapping[str, Any]:
    return {
        "type": "table",
        "caption": caption,
        "columns": [{"label": label, "short": short, "numeric": numeric} for label, short, numeric in columns],
        "rows": [list(r) for r in rows],
    }


#: The inputs the ministry's method names and never publishes, in words.
METHOD_UNPUBLISHED_WORDS: Mapping[str, tuple[str, str]] = {
    "eurobob": ("quotation", "EuroBOB, the gasoline blendstock the method prices; the note prints Eurosuper, a finished grade"),
    "essence_export": ("quotation", "export gasoline, which the method defines as half naphtha and half Eurosuper"),
    "naphta": ("quotation", "naphtha"),
    "propane": ("quotation", "propane"),
    "butane": ("quotation", "butane"),
    "peg_nord_gas_day_ahead": ("cost", "the PEG Nord day ahead gas price the refinery pays"),
    "grtgaz_transport_tariff": ("cost", "the GRTgaz transport tariff on that gas"),
    "aframax_freight_sullom_voe_le_havre": ("cost", "Aframax crude freight from Sullom Voe to Le Havre"),
}

#: SPEC.md section 5.4's Brent bound, the one this study widened; config holds
#: the bound in force, and this is the specification's figure it departs from.
METHOD_SPEC_BRENT_LOW_USD_BBL = 10.0

#: The slate lines of the method's table 1 that are inputs or losses, not
#: products, so the count of product quotations can be taken from the table.
METHOD_NOT_PRODUCTS = ("brent", "gaz_naturel", "combustible_interne_et_pertes")

METHOD_SECTIONS: Sequence[tuple[str, str]] = (
    ("formulas", "Formulas"),
    ("departures", "Where this study departs from its specification, and why"),
    ("assumptions", "Assumptions, each with its source"),
    ("checks", "Cross checks, measured"),
    ("products", "What each product is"),
    ("gasoline_rows", "The two gasoline rows OPEC printed, and the months they swap"),
    ("reconstruction", "The weekly series, and its measured error"),
    ("breaks", "Structural breaks"),
    ("limitations", "Limitations"),
    ("reuse", "Reuse terms, per source"),
)


def _implied_factors() -> Mapping[str, Mapping[str, Any]]:
    """Barrels per tonne implied by the weekly reconstruction's calendar month
    mean in $/t over OPEC's monthly $/bbl, over every month both hold."""
    quotes = series.load("dgec_note_reconstructed_weekly")
    quotes["date"] = pd.to_datetime(quotes["date"])
    quotes["month"] = quotes["date"].dt.to_period("M").dt.to_timestamp()
    monthly = quotes.groupby("month")[["gazole_usd_t", "eurosuper_usd_t"]].mean().reset_index()
    opec = series.load("opec_rotterdam_products_monthly")
    opec["date"] = pd.to_datetime(opec["date"])
    joined = monthly.merge(opec, left_on="month", right_on="date")
    out = {}
    for product, (usd_t, usd_bbl) in {"gasoil": ("gazole_usd_t", "gasoil_usd_bbl"), "gasoline": ("eurosuper_usd_t", "premium_gasoline_usd_bbl")}.items():
        ratio = (joined[usd_t] / joined[usd_bbl]).dropna()
        months = joined.loc[ratio.index, "month"]
        out[product] = {
            "months": int(len(ratio)),
            "first": _iso(months.min()),
            "last": _iso(months.max()),
            "mean": float(ratio.mean()),
            "min": float(ratio.min()),
            "max": float(ratio.max()),
        }
    return out


def _brent_low_prints(bound: float) -> list[Mapping[str, Any]]:
    """The FRED Brent prints below `bound`, grouped by year."""
    fred = series.load("fred_brent_daily")
    fred["date"] = pd.to_datetime(fred["date"])
    values = pd.to_numeric(fred["brent_usd_bbl"], errors="coerce")
    low = fred[values < bound].assign(value=values[values < bound])
    out = []
    for year, block in low.groupby(low["date"].dt.year):
        out.append({"year": int(year), "days": int(len(block)), "first": _iso(block["date"].min()), "last": _iso(block["date"].max()), "low": float(block["value"].min())})
    return out


def method(inputs: Inputs) -> Mapping[str, Any]:
    """The Method view, Part 8.5."""
    payload = _header("method", _iso(inputs.margin["date"].max()), "the Method view: the formulas, the departures from the specification with their evidence, the assumptions with a source per row, the measured cross checks, the product definitions, the weekly reconstruction and its error, the limitations and the reuse terms")
    payload["conventions"] = _conventions()
    payload["title_segments"] = [T("How every figure on this site is computed, what it rests on, and what it cannot show.")]
    payload["lead_segments"] = [
        T("This is where the study shows its work: the formulas, the places it departs from its own specification and the evidence for each, the constants with a source per row, the checks against independent data, and the limits of what the data can say. Every figure here is computed from the committed data by the same code that builds the other views."),
    ]
    payload["sections"] = [{"id": sid, "title": title} for sid, title in METHOD_SECTIONS]
    blocks: dict[str, list[Mapping[str, Any]]] = {sid: [] for sid, _ in METHOD_SECTIONS}

    gasoil_f, gasoline_f = config.BBL_PER_T_GASOIL, config.BBL_PER_T_GASOLINE
    ministry = float(config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL)
    study = float(config.GAS_INTENSITY_MMBTU_PER_BBL)
    threshold = inputs.threshold

    # 1. Formulas, SPEC.md sections 4.1 to 4.5.
    f = blocks["formulas"]
    f.append({"type": "h", "text": "Cracks"})
    f.append({"type": "formula", "segments": [T("gasoil crack = gasoil price in $/t / "), N("bbl_per_t_gasoil", gasoil_f, "bbl_per_t"), T(" minus Brent in $/bbl")]})
    f.append({"type": "formula", "segments": [T("gasoline crack = gasoline price in $/t / "), N("bbl_per_t_gasoline", gasoline_f, "bbl_per_t"), T(" minus Brent in $/bbl")]})
    f.append(_P(T("The divisors are the barrels per tonne the ICE crack contracts settle on, conventions and not densities. Both legs of a crack always share a date and an averaging window: weekly with weekly, a calendar month with the same calendar month, never a weekly product against a monthly crude.")))
    f.append({"type": "h", "text": "The margin, in four layers"})
    f.append(_P(T("The official margin is the ministry's monthly gross refining margin on Brent, published from "), D("margin_first", _iso(inputs.margin["date"].min())), T(". The replication recomputes it from the ministry's own quotations with its method, and cannot close, as the departures below say. The decomposition splits a month's margin by product:")))
    f.append({"type": "formula", "segments": [T("contribution of a product = its volume yield x its crack")]})
    f.append({"type": "formula", "segments": [T("residual = official margin minus the sum of the contributions")]})
    f.append(_P(T("The residual carries every product the study cannot price and the ministry's own cost lines, and is always shown. The observed yields are JODI refinery output by product over refinery intake for Belgium, Germany, France, the Netherlands and the United Kingdom, rolling over "), N("rolling_yield_months", config.ROLLING_YIELD_WINDOW_MONTHS, "count"), T(" months.")))
    f.append({"type": "h", "text": "Run economics"})
    f.append({"type": "formula", "segments": [T("gas in $/MMBtu = TTF in EUR/MWh x EUR/USD / "), N("mmbtu_per_mwh", config.MMBTU_PER_MWH, "mmbtu_per_mwh")]})
    f.append({"type": "formula", "segments": [T("gas cost = gas intensity in MMBtu/bbl x gas in $/MMBtu")]})
    f.append({"type": "formula", "segments": [T("margin after gas = a margin gross of gas minus the gas cost minus other variable cost")]})
    f.append({"type": "formula", "segments": [T("headroom = margin after gas minus the level at which runs get cut")]})
    f.append(_P(T("The subtraction applies only to a margin built from cracks and yields, which is gross of gas. The ministry's margin is already net of the gas its method assumes, so on the ministry's margin the gas step is the wedge between two intensities, never a second subtraction. Headroom is not computed anywhere on this site, because the level at which runs get cut is unidentified; see the limitations.")))
    f.append({"type": "h", "text": "Outputs"})
    f.append({"type": "formula", "segments": [T("carrier = the product with the largest contribution")]})
    f.append({"type": "formula", "segments": [T("breakeven TTF = the TTF at which the margin after gas equals the target, solved in closed form because the model is linear")]})
    f.append({"type": "formula", "segments": [T("ten year rank = the rank of the month's margin among the trailing "), N("percentile_window_months", config.PERCENTILE_WINDOW_MONTHS, "count"), T(" months")]})
    f.append(_P(T("The Model view solves its breakevens against a margin of zero, not against a run cut level, for the same reason headroom is not computed.")))
    f.append({"type": "h", "text": "The response of runs to the margin"})
    f.append({"type": "formula", "segments": [T("utilisation = a + the sum over one to three months back of b x the margin after gas + month terms + episode terms + error")]})
    f.append(_P(T("Utilisation is NWE crude intake over refinery capacity. The response is the sum of the three lagged coefficients, with Newey-West standard errors; the lag of each equation, its R squared and its sample are in the table below, read from the run economics artifact the Now view uses.")))
    f.append({"type": "reads", "what": "response_diagnostics"})

    # 2. Departures.
    d = blocks["departures"]
    d.append({"type": "h", "text": "The ministry's margin is already net of gas, so the gas step is a wedge"})
    d.append(_P(T("The specification writes the margin after gas as a gross margin less a gas cost. The ministry's own method note says its margin already has the purchased gas taken off:")))
    d.append({"type": "quote", "lang": "fr", "text": "Pour calculer la marge de raffinage sur Brent, on soustrait aux recettes : les couts d'achat du Brent date FAB et du gaz naturel CAF ; le cout du fret petrolier ; les couts d'assurance et les pertes", "source_title": "Mode de calcul de la marge brute de raffinage sur Brent, DGEC", "source_url": config.DGEC_METHOD_URL})
    d.append(_P(T("Its table of yields carries natural gas at "), N("ministry_gas_share_percent", 100 * config.DGEC_MASS_YIELDS["gaz_naturel"], "percent"), T(" percent of the tonne of crude as an input. In this study's units that is "), N("ministry_intensity", ministry, "mmbtu_per_bbl_5"), T(" MMBtu/bbl, against the "), N("study_intensity", study, "mmbtu_per_bbl_5"), T(" MMBtu/bbl this study derives for the average US refinery, "), N("intensity_ratio", study / ministry, "ratio"), T(" times as much. Subtracting a gas cost from the ministry's margin would charge the same barrel twice, so the engine refuses it, and what the site shows instead is the extra gas at the higher intensity, beside the margin and never taken from it.")))
    d.append({"type": "h", "text": "The ministry's margin cannot be replicated within the bar"})
    unpublished = list(config.DGEC_UNPUBLISHED_METHOD_INPUTS)
    products = [k for k in config.DGEC_MASS_YIELDS if k not in METHOD_NOT_PRODUCTS]
    quotes = [k for k in unpublished if METHOD_UNPUBLISHED_WORDS[k][0] == "quotation"]
    d.append(_P(T("The specification's bar is agreement within "), N("replication_bar_usd_bbl", config.REPLICATION_BAR_USD_BBL, "usd_bbl"), T(" $/bbl in every complete month. It cannot be met, because "), N("unpublished_quotations", len(quotes), "count"), T(" of the "), N("method_products", len(products), "count"), T(" product quotations the method prices are never published, and neither are "), N("unpublished_costs", len(unpublished) - len(quotes), "count"), T(" of its cost inputs. Named, as the specification asks:")))
    d.append({"type": "list", "items": [[T(METHOD_UNPUBLISHED_WORDS[k][1] + ".")] for k in unpublished]})
    attempts = series.replication_attempts()
    d.append(_P(T("So the site falls back to the official series and never overwrites it. The months where the ministry printed its own monthly prices, priced on the published lines alone, show how far short that falls:")))
    d.append(_table(
        "The method run on the published lines only, against the ministry's margin, $/bbl.",
        [("Month", "month", False), ("Ministry's margin", "ministry's margin", True), ("Published lines only", "published lines only", True), ("Published lines less the margin", "published lines less the margin", True), ("Prices", "prices", False)],
        [[_cell_text(month_label(_iso(r["date"]))), _cell_value("official_usd_bbl", r["official_usd_bbl"], "usd_bbl"), _cell_value("partial_usd_bbl", r["partial_usd_bbl"], "usd_bbl"), _cell_value("partial_error_usd_bbl", r["partial_error_usd_bbl"], "usd_bbl", signed=True), _cell_text("provisional" if bool(r["provisional"]) else "final")] for _, r in attempts.iterrows()],
    ))
    d.append({"type": "h", "text": "The third horse of the race is a substitution"})
    d.append(_P(T("The specification races the raw gasoil crack, the official margin and the margin after gas. Once the official margin is known to be net of gas, the second and third are the same series, so the third horse is replaced and labelled wherever it appears:")))
    d.append(_ref("runs", "race", "equations", 0, "horses", 2, "substitution_segments"))
    d.append({"type": "h", "text": "The Brent validation bound is 5 $/bbl, not 10"})
    lows = _brent_low_prints(METHOD_SPEC_BRENT_LOW_USD_BBL)
    low_segments: list[Mapping[str, Any]] = [T("The specification bounds Brent at "), N("spec_brent_low", METHOD_SPEC_BRENT_LOW_USD_BBL, "count"), T(" to "), N("spec_brent_high", config.BOUNDS_BRENT_USD_BBL[1], "count"), T(" $/bbl. FRED publishes "), N("brent_prints_below_ten", sum(r["days"] for r in lows), "count"), T(" real daily prints below "), N("spec_brent_low", METHOD_SPEC_BRENT_LOW_USD_BBL, "count"), T(": ")]
    for i, r in enumerate(lows):
        if i:
            low_segments.append(T(", and " if i == len(lows) - 1 else ", "))
        low_segments += [N("days", r["days"], "count"), T(" in " if r["days"] > 1 else " day in "), N("year", r["year"], "year"), T(" with a low of "), N("low_usd_bbl", r["low"], "usd_bbl")]
    low_segments += [T(". With the bound at "), N("spec_brent_low", METHOD_SPEC_BRENT_LOW_USD_BBL, "count"), T(" the whole download was refused. The bound exists to catch a file in cents or a slipped decimal point, which "), N("bound_brent_low", config.BOUNDS_BRENT_USD_BBL[0], "count"), T(" still catches, and cutting real prints to fit it would come closer to inventing data than widening it does.")]
    d.append(_P(*low_segments))
    d.append({"type": "h", "text": "History has named ranges, not a brush"})
    d.append(_P(T("The specification asks for a range brush on History. The view offers the windows the analysis uses instead, each from six months before the event that opens it, so a reader cannot cut a window no finding refers to.")))
    d.append({"type": "h", "text": "The stock release is dated to the day"})
    iea = {e["id"]: e for e in events_anchors.load_events()["events"]}["iea_collective_action_400_mb_2026_03_11"]
    d.append(_P(T("The specification lists the IEA release by its month alone, "), D("iea_release_month", _event_day(iea)), T(", and asks for the exact date from the source. Two IEA publications give it: "), D("iea_release_date", _event_day(iea), kind="day"), T(", and the Events view draws it at that day.")))

    # 3. Assumptions.
    a = blocks["assumptions"]
    cite = FACTOR_CITATIONS
    rows = [
        [_cell_text("Barrels per tonne, gasoil"), _cell_value("bbl_per_t_gasoil", gasoil_f, "bbl_per_t"), _cell_text("every gasoil crack"), _cell_link(cite["gasoil"]["contract"], cite["gasoil"]["url"])],
        [_cell_text("Barrels per tonne, gasoline"), _cell_value("bbl_per_t_gasoline", gasoline_f, "bbl_per_t"), _cell_text("every gasoline crack"), _cell_link(cite["gasoline"]["contract"], cite["gasoline"]["url"])],
        [_cell_text("Barrels per tonne, jet"), _cell_value("bbl_per_t_jet", config.BBL_PER_T_JET, "bbl_per_t"), _cell_text("the jet line of the monthly decomposition"), _cell_link(cite["jet"]["contract"], cite["jet"]["url"])],
        [_cell_text("Barrels per tonne, heating oil"), _cell_value("bbl_per_t_heating_oil", config.BBL_PER_T_HEATING_OIL, "bbl_per_t"), _cell_text("the heating oil line of the decomposition"), _cell_link(cite["heating_oil"]["contract"], cite["heating_oil"]["url"])],
        [_cell_text("Barrels per tonne, fuel oil"), _cell_value("bbl_per_t_fuel_oil", config.BBL_PER_T_FUEL_OIL_1PCT, "bbl_per_t"), _cell_text("the fuel oil line of the decomposition"), _cell_link(cite["fuel_oil_1pct"]["contract"], cite["fuel_oil_1pct"]["url"])],
        [_cell_text("Barrels per tonne of Brent, the ministry's weekly note"), _cell_value("bbl_per_t_brent_note", config.DGEC_BBL_PER_T_BRENT_NOTE, "bbl_per_t"), _cell_text("turning the note's Brent in $/t back into $/bbl, for the weekly cracks; measured on the ministry's own printed pairs, not stated"), _cell_link("DGEC weekly note of 28 August 2026", "https://www.ecologie.gouv.fr/sites/default/files/documents/NPG-2026.08.28_0.pdf")],
        [_cell_text("Barrels per tonne of Brent, the ministry's margin"), _cell_value("bbl_per_t_brent_margin", config.DGEC_BBL_PER_T_BRENT_MARGIN, "bbl_per_t"), _cell_text("the replication and the ministry's embedded gas, nothing else; stated on page four of the method note"), _cell_link("Mode de calcul de la marge brute de raffinage sur Brent", config.DGEC_METHOD_URL)],
        [_cell_text("MMBtu per MWh"), _cell_value("mmbtu_per_mwh", config.MMBTU_PER_MWH, "mmbtu_per_mwh"), _cell_text("TTF in EUR/MWh to $/MMBtu, on the daily TTF only"), _cell_text("a unit definition, a megawatt hour over a million British thermal units")],
        [_cell_text("Gas intensity, the average US refinery"), _cell_value("study_intensity", study, "mmbtu_per_bbl_5"), _cell_text("the margin at the US gas use, the Model's default, horse C"), _cell_link("EIA Refinery Capacity Report, tables 10a and 10b", "https://www.eia.gov/petroleum/refinerycapacity/")],
        [_cell_text("Gas intensity the ministry's margin embeds"), _cell_value("ministry_intensity", ministry, "mmbtu_per_bbl_5"), _cell_text("sizing the wedge; never subtracted"), _cell_link("Mode de calcul de la marge brute de raffinage sur Brent, table 1", config.DGEC_METHOD_URL)],
        [_cell_text("Other variable cost"), _cell_value("other_variable_cost_usd_bbl", config.OTHER_VARIABLE_COST_USD_BBL, "usd_bbl"), _cell_text("the margin after gas; a labelled default, carbon costs out of scope"), _cell_text("the specification's default")],
    ]
    a.append(_table("The constants, each with where it is used and its source.", [("Constant", "constant", False), ("Value", "value", True), ("Used for", "used for", False), ("Source", "source", False)], rows))
    a.append({"type": "h", "text": "The US gas intensity, derived rather than typed"})
    a.append(_table("Four EIA figures for the United States in 2023.", [("Input", "input", False), ("Value", "value", True), ("Unit", "unit", False), ("Source", "source", False)], [
        [_cell_text("Natural gas burned as refinery fuel"), _cell_value("eia_fuel_gas_mmcf", config.EIA_REFINERY_FUEL_GAS_MMCF_2023, "count"), _cell_text("million cubic feet"), _cell_link("EIA Refinery Capacity Report, table 10a", "https://www.eia.gov/petroleum/refinerycapacity/")],
        [_cell_text("Natural gas used as hydrogen feedstock"), _cell_value("eia_hydrogen_gas_mmcf", config.EIA_HYDROGEN_FEEDSTOCK_GAS_MMCF_2023, "count"), _cell_text("million cubic feet"), _cell_link("EIA Refinery Capacity Report, table 10b", "https://www.eia.gov/petroleum/refinerycapacity/")],
        [_cell_text("Heat content of natural gas consumed"), _cell_value("eia_heat_content_btu_cf", config.EIA_GAS_HEAT_CONTENT_BTU_PER_CF_2023, "count"), _cell_text("Btu per cubic foot, gross"), _cell_text("EIA Natural Gas Navigator, heat content of natural gas consumed, annual")],
        [_cell_text("Refinery and blender net input of crude oil"), _cell_value("eia_crude_inputs_kbbl", config.EIA_CRUDE_INPUTS_THOUSAND_BBL_2023, "count"), _cell_text("thousand barrels"), _cell_link("EIA, refinery and blender net input", "https://www.eia.gov/dnav/pet/pet_pnp_inpt_dc_nus_mbbl_a.htm")],
    ]))
    a.append({"type": "formula", "segments": [T("intensity = (fuel gas + hydrogen gas) x heat content / crude input = "), N("study_intensity", study, "mmbtu_per_bbl_5"), T(" MMBtu/bbl")]})
    a.append(_P(T("Inside the specification's band of "), N("band_low", config.GAS_INTENSITY_BAND[0], "mmbtu_per_bbl"), T(" to "), N("band_high", config.GAS_INTENSITY_BAND[1], "mmbtu_per_bbl"), T(". It is a US figure: European refiners burn more of their own still gas and buy less, so it is an upper end default, editable in the Model view. Fuel gas alone would give "), N("fuel_only_intensity", config.GAS_INTENSITY_FUEL_ONLY_MMBTU_PER_BBL, "mmbtu_per_bbl"), T(", and a denominator of distillation input "), N("gross_input_intensity", config.GAS_INTENSITY_GROSS_INPUT_MMBTU_PER_BBL, "mmbtu_per_bbl"), T("; neither is used.")))
    a.append({"type": "h", "text": "The gas the ministry's margin already embeds"})
    a.append({"type": "formula", "segments": [T("embedded intensity = "), N("ministry_gas_share_percent", 100 * config.DGEC_MASS_YIELDS["gaz_naturel"], "percent"), T(" percent of a tonne of crude / "), N("bbl_per_t_brent_margin", config.DGEC_BBL_PER_T_BRENT_MARGIN, "bbl_per_t"), T(" barrels per tonne x "), N("gas_mmbtu_per_tonne", config.GAS_MMBTU_PER_TONNE, "coef"), T(" MMBtu per tonne of gas = "), N("ministry_intensity", ministry, "mmbtu_per_bbl_5"), T(" MMBtu/bbl")]})
    a.append(_P(T("The MMBtu per tonne of gas takes the volume from the Energy Institute's conversion table, "), N("ei_bcf_per_mt_lng", config.EI_BCF_NG_PER_MILLION_TONNES_LNG, "coef"), T(" billion cubic feet per million tonnes, and the heat content from the EIA figure above, so both intensities sit on the same gross basis.")))
    a.append({"type": "h", "text": "The prices behind the latest month's split"})
    a.append({"type": "reads", "what": "margin_stack_prices"})
    a.append({"type": "h", "text": "Rules"})
    a.append({"type": "list", "items": [
        [T("A monthly mean is the mean of the days the source published a price: no day is filled or carried forward, and a month with fewer than "), N("monthly_mean_min_days", config.MONTHLY_MEAN_MIN_OBSERVATIONS, "count"), T(" published days has no mean.")],
        [T("The ten year rank uses the trailing "), N("percentile_window_months", config.PERCENTILE_WINDOW_MONTHS, "count"), T(" months, counted in months so a leap year does not change its length.")],
        [T("Newey-West standard errors use a lag of at least "), N("newey_west_min_lag", analysis.NEWEY_WEST_MIN_LAG, "count"), T(", as the specification asks; the lag each equation used is in the table under the formulas.")],
        [T("Validation bounds are units checks, not views on the market: product prices "), N("bound_product_low", config.BOUNDS_PRODUCT_USD_T[0], "count"), T(" to "), N("bound_product_high", config.BOUNDS_PRODUCT_USD_T[1], "count"), T(" $/t, Brent "), N("bound_brent_low", config.BOUNDS_BRENT_USD_BBL[0], "count"), T(" to "), N("bound_brent_high", config.BOUNDS_BRENT_USD_BBL[1], "count"), T(" $/bbl, cracks "), N("bound_crack_low", config.BOUNDS_CRACK_USD_BBL[0], "count"), T(" to "), N("bound_crack_high", config.BOUNDS_CRACK_USD_BBL[1], "count"), T(" $/bbl. A failed check keeps the old cache and marks the series failed.")],
        [T("A missing value is null in every artifact, never zero, never bridged by a line, and the page says why it is missing.")],
    ]})

    # 4. Cross checks.
    c = blocks["checks"]
    anchors = inputs.entry("anchors")
    tri = series.october_2022_triangulation()
    implied = _implied_factors()
    join = analysis.seasonal_join()
    c.append({**_table("Each check against data this study did not fit to, with what it shows.", [("Check", "check", False), ("Result", "result", False), ("What it means", "what it means", False)], [
        [_cell_text("The ministry's Brent, converted with its own factor, against FRED's monthly mean"), _cell_segments(N("brent_months_within", anchors["brent_cross_check_within_tolerance"], "count"), T(" of "), N("brent_months", anchors["brent_cross_check_months"], "count"), T(" months within "), N("brent_tolerance_usd_bbl", config.BRENT_CROSS_CHECK_TOLERANCE_USD_BBL, "usd_bbl"), T(" $/bbl, worst "), N("brent_worst_usd_bbl", anchors["brent_cross_check_max_usd_bbl"], "usd_bbl"), T(" $/bbl")), _cell_text("the specification asks for 95 percent of months; every month passes")],
        [_cell_text("The ministry's printed margins parsed from its notes"), _cell_segments(N("mbr_anchors_reproduced", anchors["mbr_anchors_reproduced"], "count"), T(" of "), N("mbr_anchors", anchors["mbr_anchors"], "count"), T(" reproduce exactly")), _cell_text("the specification's eight months and the final August 2026 figure")],
        [_cell_text("October 2022 gas cost against a refinery fired on fuel oil, at this study's intensity"), _cell_segments(N("triangulation_gap_usd_bbl", tri["gap_usd_bbl"], "usd_bbl"), T(" $/bbl on the high sulphur fuel oil row, "), N("triangulation_variant_usd_bbl", tri["variant_gap_usd_bbl"], "usd_bbl"), T(" on the low sulphur row, against S&P Global's about "), N("sp_global_gap_usd_bbl", tri["sp_global_gap_usd_bbl"], "usd_bbl")), _cell_text("the same order of magnitude, which is all an order of magnitude check can say; nothing was tuned toward it")],
        [_cell_text("Barrels per tonne implied by the ministry's Gazole against OPEC's gasoil"), _cell_segments(T("mean "), N("implied_gasoil_mean", implied["gasoil"]["mean"], "bbl_per_t_4"), T(", from "), N("implied_gasoil_min", implied["gasoil"]["min"], "bbl_per_t_4"), T(" to "), N("implied_gasoil_max", implied["gasoil"]["max"], "bbl_per_t_4"), T(", over "), N("implied_months", implied["gasoil"]["months"], "count"), T(" months")), _cell_segments(T("the contract's "), N("bbl_per_t_gasoil", gasoil_f, "bbl_per_t"), T(" sits inside the spread, near its middle"))],
        [_cell_text("Barrels per tonne implied by the ministry's Eurosuper against OPEC's premium gasoline"), _cell_segments(T("mean "), N("implied_gasoline_mean", implied["gasoline"]["mean"], "bbl_per_t_4"), T(", from "), N("implied_gasoline_min", implied["gasoline"]["min"], "bbl_per_t_4"), T(" to "), N("implied_gasoline_max", implied["gasoline"]["max"], "bbl_per_t_4"), T(", over "), N("implied_months", implied["gasoline"]["months"], "count"), T(" months")), _cell_segments(T("the contract's "), N("bbl_per_t_gasoline", gasoline_f, "bbl_per_t"), T(" sits at the top of the spread, not the middle. It is kept: the two sources quote different grades, a finished premium gasoline against OPEC's premium unleaded, so the gap mixes a density with an octane spread, and choosing a factor to close it would be tuning"))],
        [_cell_text("This study's weekly cracks, averaged by month, against OPEC's monthly ones"), _cell_segments(T("gasoil "), N("gasoil_mean_gap_usd_bbl", join["%s_mean_gap" % analysis.CRACK_GASOIL], "usd_bbl", signed=True), T(", gasoline "), N("gasoline_mean_gap_usd_bbl", join["%s_mean_gap" % analysis.CRACK_GASOLINE], "usd_bbl", signed=True), T(" $/bbl on average over "), N("overlap_months", join["overlap_months"], "count"), T(" months")), _cell_text("gasoil agrees across two independent sources; gasoline differs by a product, so the two series are never joined")],
    ]), "prose": True})
    c.append(_P(T("The implied factors are recomputed here from the committed data, calendar month means of the weekly reconstruction over OPEC's monthly $/bbl, "), D("implied_first", implied["gasoil"]["first"]), T(" to "), D("implied_last", implied["gasoil"]["last"]), T(".")))

    # 5. Products.
    p = blocks["products"]
    p.append(_P(T("Every product keeps its source's own label. None of them is a futures contract, and none is relabelled as one: the ICE contracts supply only the barrels per tonne a crack is quoted on.")))
    p.append(_table("The products, as each source names them.", [("Label", "label", False), ("Source", "source", False), ("What it is", "what it is", False)], [
        [_cell_text("Gazole"), _cell_text("the ministry, Rotterdam, credited DGEC-Reuters"), _cell_text("road diesel quoted in Rotterdam; this study's gasoil in the weekly series and the latest month's split")],
        [_cell_text("Eurosuper"), _cell_text("the ministry"), _cell_text("finished premium gasoline, not Eurobob blendstock; this study's gasoline in the weekly series")],
        [_cell_text("Fioul domestique"), _cell_text("the ministry"), _cell_text("heating oil")],
        [_cell_text("Jet"), _cell_text("the ministry"), _cell_text("jet fuel; printed in the monthly table, not on the weekly chart")],
        [_cell_text("Fioul lourd TBTS (< 1%)"), _cell_text("the ministry"), _cell_text("low sulphur fuel oil; printed in the monthly table, not on the weekly chart")],
        [_cell_text("Brent date"), _cell_text("the ministry"), _cell_text("dated Brent, in $/t in the note's table, converted with the note's own factor")],
        [_cell_text("Gasoil 10 ppm"), _cell_text("OPEC Monthly Oil Market Report, Rotterdam barges, assessed by Argus"), _cell_text("this study's gasoil in the monthly series from 2000; its label changed with the specification, see the breaks")],
        [_cell_text("Premium gasoline, unleaded 98"), _cell_text("OPEC Monthly Oil Market Report, assessed by Argus"), _cell_text("this study's gasoline in the monthly series; a different product from Eurosuper, relabelled four times since 2000")],
    ]))

    # 6. The two gasoline rows. SPEC.md section 2 rule 3: a source that
    # contradicts itself is reported, not resolved. The words come from the
    # History artifact that draws both rows, so the two views cannot drift.
    g = blocks["gasoline_rows"]
    record = opec_momr.GASOLINE_ROW_DISPUTE
    g.append(_ref("history", "monthly", "dispute", "what_segments"))
    g.append(_P(T("Which months those are is found by a rule and not by a list of dates: they are the months of the overlap where the octane graded row prints above the sulphur graded one, reversing the ordering that holds in every other month of it. A later issue that moved a value would move the window with it.")))
    g.append({"type": "h", "text": "The same month, printed by two consecutive issues"})
    g.append(_ref("history", "monthly", "dispute", "evidence_segments"))
    g.append(_table(
        "Two months of the Rotterdam block as the issue before and the issue after printed them, both gasoline rows, in $/bbl. Read from the archived reports, which their licence does not allow this repository to commit.",
        [("Month", "month", False), ("Earlier issue", "earlier issue", False), ("Sulphur graded", "sulphur graded", True), ("Octane graded", "octane graded", True), ("Later issue", "later issue", False), ("Sulphur graded", "sulphur graded, later", True), ("Octane graded", "octane graded, later", True)],
        [
            [
                _cell_text(month_label("%s-01" % e["month"])),
                _cell_text(month_label("%s-01" % e["earlier_issue"])),
                _cell_value("earlier_headline", e["earlier_headline"], "usd_bbl"),
                _cell_value("earlier_alternative", e["earlier_alternative"], "usd_bbl"),
                _cell_text(month_label("%s-01" % e["later_issue"])),
                _cell_value("later_headline", e["later_headline"], "usd_bbl"),
                _cell_value("later_alternative", e["later_alternative"], "usd_bbl"),
            ]
            for e in record["issue_evidence"]
        ],
    ))
    g.append({"type": "h", "text": "OPEC's own annual restatement, which settles nothing"})
    g.append(_ref("history", "monthly", "dispute", "annual_segments"))
    g.append(_table(
        "The Annual Statistical Bulletin's Rotterdam premium gasoline against the calendar year mean of each printed row, $/bbl. The octane graded column is the octane row where the reports printed one and the headline row where they did not, because a six month mean is not an annual average.",
        [("Year", "year", False), ("Bulletin", "bulletin", True), ("Sulphur graded row", "sulphur graded row", True), ("Octane graded row", "octane graded row", True)],
        [
            [
                _cell_text(str(a["year"])),
                _cell_value("asb_usd_bbl", a["asb"], "usd_bbl"),
                _cell_value("headline_usd_bbl", a["headline"], "usd_bbl"),
                _cell_value("alternative_usd_bbl", a["alternative"], "usd_bbl"),
            ]
            for a in record["annual_check"]
        ],
    ))
    g.append({"type": "h", "text": "What the choice changes, measured"})
    g.append(_ref("history", "seasonal_monthly", "panels", "gasoline", "row_sensitivity", "segments"))
    g.append(_P(T("Nothing else on this site reads OPEC gasoline across these months. The ministry's margin, which the monthly R squared is measured against, begins after them; this study's weekly layer begins long after them; every dated event on the Events view is later; and no Model preset sits inside them. Those are sample start dates, checked against the window rather than asserted.")))
    g.append(_ref("history", "monthly", "dispute", "unresolved_segments"))
    g.append(_P(T(record["unresolved"])))

    # 7. The weekly reconstruction.
    r = blocks["reconstruction"]
    weekly = inputs.weekly
    error = dgec_note.RECONSTRUCTION_ERROR
    import re as _re
    tilt = _re.search(r"a (\d+) point tilt moved the oldest week by ([0-9.]+)", dgec_note.SMOOTH_TILT_IS_INVISIBLE)
    oldest = weekly[weekly["evidence_class"] == "single_geometry_oldest"]
    r.append(_P(T("The ministry prints two weeks of prices in each weekly note and deletes the note a week later, but each note also carries a chart of about two years of weekly prices. This study reads those charts: the curves are decoded from the vector drawing, calibrated against the figures the same note prints, and combined across every note collected. "), N("weeks", len(weekly), "count"), T(" weeks run from "), D("weekly_first", _iso(weekly["date"].min()), kind="day"), T(" to "), D("weekly_last", _iso(weekly["date"].max()), kind="day"), T("; "), N("printed_weeks", int(weekly["printed_gasoil_usd_bbl"].notna().sum()), "count"), T(" of them the ministry printed, and "), N("cross_checked_weeks", int((weekly["n_independent_geometries"] >= 2).sum()), "count"), T(" are read from two or more independent chart geometries. Nothing is interpolated between weeks and nothing is borrowed from another source.")))
    r.append(_P(T("The measured error: refitted on three products and tested on the fourth, a note's reading misses its printed figures by "), N("error_low_usd_t", error["out_of_sample_mae_usd_t"][0], "usd_t_error"), T(" to "), N("error_high_usd_t", error["out_of_sample_mae_usd_t"][1], "usd_t_error"), T(" $/t on average, worst "), N("error_worst_usd_t", error["out_of_sample_worst_usd_t"], "usd_t_error"), T(" $/t. Where two notes plot the same week they agree to "), N("pair_mean_usd_t", error["note_pair_mean_absolute_usd_t"], "usd_t_error"), T(" $/t on average and "), N("pair_worst_usd_t", error["note_pair_worst_week_usd_t"], "usd_t_error"), T(" $/t at worst.")))
    restitch = dgec_note.COLLECTION_RESTITCHES_HISTORY
    r.append({"type": "h", "text": "Collecting a note changes the weeks already published"})
    r.append(_P(T("Each note plots about "), N("chart_weeks", dgec_note.CHART_WEEKS, "count"), T(" weeks, so most weeks are drawn by several notes, and the value here is the median across the chart geometries that cover the week. One more note therefore does not only add a week at the right hand end: it restitches the series behind it. Collecting the note of "), D("restitch_note", _iso(inputs.weekly["date"].max()), kind="day"), T(" moved "), N("weeks_moved", restitch["weeks_moved"], "count"), T(" of the "), N("weeks_before", restitch["weeks_before"], "count"), T(" weeks already in the series, by at most "), N("worst_price_move_usd_t", restitch["worst_price_move_usd_t"], "usd_t_error"), T(" $/t on a price column, "), N("worst_spread_move_usd_t", restitch["worst_spread_move_usd_t"], "usd_t_error"), T(" $/t on a spread column and "), N("worst_crack_move_usd_bbl", restitch["worst_crack_move_usd_bbl"], "usd_bbl"), T(" $/bbl on a crack.")))
    r.append(_P(T("Those moves sit inside the reading's own measured error, and the same collection took the weeks read from two or more independent chart geometries from "), N("cross_checked_before", restitch["cross_checked_before"], "count"), T(" to "), N("cross_checked_after", restitch["cross_checked_after"], "count"), T(". So this is the method working, more evidence giving a better estimate, and not a correction of a mistake. It is also a reproducibility fact worth stating plainly: a weekly figure quoted from this site today can differ slightly from the same figure next month, and anyone checking the study against an earlier reading of it should expect that on every week rather than on the newest one.")))
    r.append(_P(T("The comparison above is between two vintages of the committed file, so it cannot be recomputed from the file as it stands; it is recorded in the collector with the collection it was measured on.")))
    r.append(_P(T("That first error is leave one series out, not out of sample in time. Every calibration anchor sits in the last two weeks of a note's chart, so it measures the reading where the anchors are and does not bound the oldest weeks. A smooth bend in a chart anchored at its right hand end passes every check: bending one note's chart by "), N("tilt_points", int(tilt.group(1)) if tilt else None, "count"), T(" points moved its oldest week by "), N("tilt_usd_t", float(tilt.group(2)) if tilt else None, "usd_t_error"), T(" $/t. What defends a week against that is a second note plotting it at a different place on its chart. The "), N("oldest_weeks", len(oldest), "count"), T(" weeks from "), D("oldest_first", _iso(oldest["date"].min()), kind="day"), T(" have no second chart and sit where such a bend does most harm: they are the least defended data in the study, and every chart that draws them hatches them.")))

    # 7. Breaks.
    b = blocks["breaks"]
    b.append(_P(T("A break is a change in what a series measures. It splits the line it applies to and no other; an event never splits a line. The list is the one History draws from.")))
    b.append({"type": "reads", "what": "breaks"})
    b.append(_ref("history", "margin", "no_break_segments"))
    b.append(_ref("runs", "series", "capacity_segments"))

    # 8. Limitations, the weakest first.
    lim = blocks["limitations"]
    lim.append({"type": "list", "items": [
        {"ref": {"artifact": "run-economics", "path": ["threshold", "segments"]}},
        {"ref": {"artifact": "runs", "path": ["race", "sentence_segments"]}},
        {"ref": {"artifact": "runs", "path": ["endogeneity_segments"]}},
        {"ref": {"artifact": "runs", "path": ["instrument", "diagnosis_segments"]}},
        {"ref": {"artifact": "history", "path": ["monthly", "r2_segments"]}},
        {"ref": {"artifact": "history", "path": ["seasonal_monthly", "panels", "gasoil", "variants", "all", "sentence_segments"]}},
        {"ref": {"artifact": "run-economics", "path": ["utilisation", "segments"]}},
        [T("Carbon costs are out of scope: other variable cost is zero and labelled, and no emissions price is in any margin.")],
        [T("The gas intensity is a US average and an upper end for Europe; the ministry's own is "), N("ministry_intensity", ministry, "mmbtu_per_bbl"), T(" MMBtu/bbl, and the truth for a given refinery is somewhere this study cannot see.")],
        {"ref": {"artifact": "history", "path": ["monthly", "end_segments"]}},
        [T("The ministry printed monthly prices only for "), N("printed_months", len(attempts), "count"), T(" months (")] + [seg for i, x in enumerate(attempts["date"]) for seg in ([T(", ")] if i else []) + [D("printed_month", _iso(x))]] + [T("), so the margin can be split by the ministry's own prices only in those months.")],
        {"ref": {"artifact": "runs", "path": ["series", "sample_segments"]}},
        {"ref": {"artifact": "history", "path": ["weekly", "evidence_segments"]}},
    ]})
    lim.append({"type": "h", "text": "Two steps done by hand"})
    lim.append({"type": "reads", "what": "manual_steps"})

    # 9. Reuse.
    blocks["reuse"].append({"type": "reads", "what": "reuse"})

    for section in payload["sections"]:
        section["blocks"] = blocks[section["id"]]
    return payload


# ---------------------------------------------------------------------------
# Build, serialise, write, check
# ---------------------------------------------------------------------------

ARTIFACTS: Mapping[str, Callable[[Inputs], Mapping[str, Any]]] = {
    "now": now,
    "cracks": cracks,
    "margin-stack": margin_stack,
    "run-economics": run_economics,
    "provenance": provenance,
    "history": history,
    "model": model,
    "runs": runs,
    "events": events,
    "method": method,
}


def build(inputs: Inputs | None = None) -> dict[str, Mapping[str, Any]]:
    inputs = Inputs() if inputs is None else inputs
    return {name: make(inputs) for name, make in ARTIFACTS.items()}


def _is_row(items: Sequence[Any]) -> bool:
    return all(not isinstance(x, (dict, list, tuple)) for x in items)


def _pretty(value: Any, indent: int = 0) -> str:
    """JSON with structure indented and rows of scalars on one line.

    allow_nan=False on every leaf, so a NaN that reached a payload raises here
    instead of writing a token no browser parses.
    """
    pad = " " * indent
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = [
            "%s  %s: %s" % (pad, json.dumps(str(k)), _pretty(v, indent + 2))
            for k, v in value.items()
        ]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(value, (list, tuple)):
        items = list(value)
        if not items:
            return "[]"
        if _is_row(items):
            return json.dumps(items, ensure_ascii=True, allow_nan=False)
        if all(isinstance(i, (list, tuple)) and all(not isinstance(x, dict) and (not isinstance(x, (list, tuple)) or _is_row(x)) for x in i) for i in items):
            body = [pad + "  " + json.dumps(i, ensure_ascii=True, allow_nan=False) for i in items]
            return "[\n" + ",\n".join(body) + "\n" + pad + "]"
        if all(isinstance(i, dict) and _is_row(list(i.values())) for i in items):
            body = [pad + "  " + json.dumps(i, ensure_ascii=True, allow_nan=False) for i in items]
            return "[\n" + ",\n".join(body) + "\n" + pad + "]"
        body = [pad + "  " + _pretty(i, indent + 2) for i in items]
        return "[\n" + ",\n".join(body) + "\n" + pad + "]"
    if isinstance(value, (np.bool_,)):
        value = bool(value)
    elif isinstance(value, np.integer):
        value = int(value)
    elif isinstance(value, np.floating):
        value = float(value)
    return json.dumps(value, ensure_ascii=True, allow_nan=False)


def serialise(payload: Mapping[str, Any]) -> str:
    """One artifact as text: ASCII, LF, one trailing newline."""
    return _pretty(payload) + "\n"


def stale_artifacts(built: Mapping[str, Mapping[str, Any]], directory: Path = DATA) -> list[str]:
    """Names whose committed file is missing or not byte identical to a rebuild."""
    out = []
    for name, payload in built.items():
        path = Path(directory) / ("%s.json" % name)
        if not path.exists() or path.read_bytes() != serialise(payload).encode("ascii"):
            out.append(name)
    return out


def write_all(directory: Path = DATA, inputs: Inputs | None = None) -> list[Mapping[str, Any]]:
    """Write every artifact whose bytes changed and report each one."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    report = []
    for name, payload in build(inputs).items():
        text = serialise(payload).encode("ascii")
        path = directory / ("%s.json" % name)
        changed = not path.exists() or path.read_bytes() != text
        if changed:
            path.write_bytes(text)
        report.append({"artifact": name, "bytes": len(text), "changed": changed})
    return report


def check(directory: Path = DATA, inputs: Inputs | None = None) -> int:
    """Rebuild in memory, write nothing, return 1 when anything is stale.

    For the committed data/ directory this also checks the content hashes in
    index.html (src/crack/versions.py): a module, stylesheet or artifact whose
    bytes changed while index.html still names the old hash is stale too,
    because a deploy of it would keep yesterday's URL."""
    stale = stale_artifacts(build(inputs), directory)
    print("checked %d artifacts in %s" % (len(ARTIFACTS), directory))
    for name in stale:
        print("  STALE    data/%s.json" % name)
    stale_versions: list[str] = []
    crlf: list[str] = []
    if Path(directory).resolve() == DATA.resolve():
        stale_versions = versions.stale_entries(REPO_ROOT)
        print("checked the content hashes in index.html")
        for entry in stale_versions:
            print("  STALE    index.html version of %s" % entry)
        # A versioned file with CRLF on disk hashes to something a checkout of
        # the same commit cannot reproduce, because .gitattributes stores it with
        # LF. See crack.versions.crlf_entries.
        crlf = versions.crlf_entries(REPO_ROOT)
        print("checked the line endings of the versioned files")
        for entry in crlf:
            print("  CRLF     %s" % entry)
    if stale:
        print("The committed artifacts do not match the caches and the analysis. Run: make build")
    if stale_versions:
        print("index.html names a hash that is not the file's. Run: make build")
    if crlf:
        print(
            "A versioned file carries CRLF. .gitattributes stores it with LF, so the "
            "hash in index.html is of bytes only this machine has and CI will fail. "
            "Rewrite the file with LF, then run: make build"
        )
    if stale or stale_versions or crlf:
        return 1
    print("every artifact matches a rebuild from the committed caches, byte for byte")
    if Path(directory).resolve() == DATA.resolve():
        print("every module, stylesheet and artifact URL in index.html carries its current hash")
        print("every versioned file on disk is LF, so a clean checkout hashes the same bytes")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the site facing JSON artifacts into data/.")
    parser.add_argument("--check", action="store_true", help="write nothing, exit 1 if a committed artifact is stale")
    parser.add_argument("--out", default=None, help="write into this directory instead of data/")
    args = parser.parse_args(argv)
    directory = DATA if args.out is None else Path(args.out)
    if args.check:
        return check(directory)
    report = write_all(directory)
    print("export, from the committed caches, no network")
    for item in report:
        print("  %-16s %8d bytes   %s" % (item["artifact"], item["bytes"], "written" if item["changed"] else "unchanged"))
    if directory.resolve() == DATA.resolve():
        # After the artifacts, so their hashes are the bytes just written.
        written = versions.write(REPO_ROOT)
        print("  %-16s %s" % ("index.html", "versions written" if written else "versions unchanged"))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
