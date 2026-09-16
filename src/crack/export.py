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

THE CAPACITY CACHE. Utilisation needs data/private/ei_refinery_capacity_annual,
which may not be committed (docs/sources.md section 2.7). A build on a machine
without it cannot produce run-economics.json, and this module lets
FileNotFoundError propagate rather than export a page without the run economics
section. Gate 5's workflow has to answer that before it can run build-check.
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

from crack import analysis, config, engine, series

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
#: section 5 of docs/design.md: $/bbl 2, kb/d 1, t 2, R2 3, power 3, pp 3.
DECIMALS: Mapping[str, int] = {
    "usd_bbl": 2,
    "usd_t": 0,
    "usd_mmbtu": 2,
    "mmbtu_per_bbl": 3,
    "kb_d": 1,
    "t": 2,
    "r2": 3,
    "pp": 3,
    "pp_per_usd_bbl": 3,
    "percent": 1,
    "ratio": 1,
    "yield_percent": 1,
    "bbl_per_t": 2,
    "count": 0,
    "year": 0,
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
        "source": "the committed caches in data/cache and data/seed, the manifest, and data/private/ei_refinery_capacity_annual for utilisation only; no network",
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
            T(" and the slope below the estimated kink changes sign, so the kink describes one episode rather than a level; its interval, "),
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
    clauses: what the barrel kept after gas this month, where that sits in ten
    years, which crack carried it, and whether runs have room to rise.

    The month is said once. "After its own gas allowance" says whose gas: the
    MBR is net of gas at the ministry's embedded intensity, so the figure is the
    ministry's and not a refinery's. The same barrel at the average US
    refinery's gas use, and the ratio of the two intensities, are said in the
    "Refining margin and gas" section, where the wedge is drawn
    (margin-stack.json study_margin_segments). docs/design.md Part 7, C9."""
    month = values["margin_month"]
    out: list[Mapping[str, Any]] = [
        T("On the ministry's Rotterdam margin, a refiner kept "),
        N("mbr_usd_bbl", values["mbr_usd_bbl"], "usd_bbl"),
        T(" $/bbl after its own gas allowance in "),
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
    crack_segments: list[Mapping[str, Any]] = []
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
        T(" years the weekly series covers"),
    ]
    printed = [latest["products"][p]["point"]["printed_usd_bbl"] for p in ("gasoil", "gasoline")]
    if all(x is not None for x in printed):
        crack_segments += [
            T("; the note printed "),
            N("gasoil_printed_usd_bbl", printed[0], "usd_bbl"),
            T(" and "),
            N("gasoline_printed_usd_bbl", printed[1], "usd_bbl"),
            T("."),
        ]
    else:
        crack_segments += [T(".")]

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
        N("move_usd_bbl", cap.translation.move_usd_bbl, "usd_bbl"),
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
    return {"date": _iso(last["date"]), "iso_year": year, "iso_week": week, "n_years": n_years, "products": products}


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
    payload["month"] = month
    payload["month_label"] = month_label(month)
    payload["decomposed"] = decomposition is not None
    payload["rows"] = rows
    payload["scale"] = {"low_usd_bbl": _num(scale_low), "high_usd_bbl": _num(scale_high), "includes_zero": True}

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
        T(" times the ministry's, the same barrel would have kept "),
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
    }


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
    return payload


# ---------------------------------------------------------------------------
# provenance.json
# ---------------------------------------------------------------------------

ATTRIBUTIONS: Sequence[Mapping[str, Any]] = (
    {
        "id": "dgec",
        "who": "DGEC, Direction generale de l'energie et du climat, ministere de la Transition ecologique",
        "credit_line": "Source: DGEC, prices credited DGEC-Reuters",
        "third_party": "Every DGEC price table carries 'Source : DGEC-REUTERS'; the assessments are Reuters'. Parsed values are republished with attribution and the note PDFs are not.",
        "licence": "Licence Ouverte 2.0, attribution and the date of last update",
        "series": ["dgec_mbr_monthly", "dgec_brent_monthly", "dgec_note_printed_monthly", "dgec_note_printed_weekly", "dgec_note_reconstructed_weekly", "dgec_note_reconstructed_cracks_weekly", "anchors"],
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
        "third_party": "The capacity sheet includes ICIS and S&P Global Energy data, so the table is not published; only the derived utilisation is.",
        "licence": "Quotation with attribution; extensive reproduction needs permission",
        "series": ["ei_refinery_capacity_annual"],
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
    payload = _header("provenance", last[:10], "the manifest whole, and the attribution and licence line for every source")
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
    payload["manifest_columns"] = ["series", "status", "last_date", "fetched_at", "gaps", "vintage", "source"]
    payload["manifest"] = manifest
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
    """Rebuild in memory, write nothing, return 1 when anything is stale."""
    stale = stale_artifacts(build(inputs), directory)
    print("checked %d artifacts in %s" % (len(ARTIFACTS), directory))
    for name in stale:
        print("  STALE    data/%s.json" % name)
    if stale:
        print("The committed artifacts do not match the caches and the analysis. Run: make build")
        return 1
    print("every artifact matches a rebuild from the committed caches, byte for byte")
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
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
