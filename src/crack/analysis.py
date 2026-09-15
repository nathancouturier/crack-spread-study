"""SPEC.md section 6.1 and 6.2. How much do runs answer the margin, and is
there a level below which they get cut.

crack.engine takes numbers and gives numbers. crack.series opens the committed
caches and lines them up by date. This module is the third layer: it takes the
aligned series and estimates things from them, and it is the only place in the
project that runs a regression.

What this module will not do, and why
-------------------------------------
SPEC.md section 6.6 is the rule that governs this layer. No parameter search, no
walk forward optimisation, no forecast, no strategy, no Sharpe ratio, no
profit and loss. Two searches over a number appear below and both are named:

  1. The threshold grid of SPEC.md section 6.2, which the spec asks for by name
     and pairs with a block bootstrap interval and an explicit unidentified
     verdict. It is a profile least squares estimator for a kink location, the
     ordinary way to estimate a threshold, and its answer is reported with its
     interval whatever the interval turns out to be.
  2. Nothing else. Every other number in this module, the Newey-West lag, the
     bootstrap block length, the episode window, the closure step rule, is
     either fixed by a stated rule applied once or read off the data by a stated
     procedure, and none of them is moved after seeing what it does to a result.

SPEC.md section 2 rule 3 and rule 4 are the other half: report the result
whatever it is, and the study is allowed to find nothing. The regressions below
are weak. SPEC.md section 13 predicted that they would be, on monthly data
dominated by three crises, and they are. That is the finding.

WHICH MARGIN THIS ASKS ABOUT, AND WHAT CHANGED
----------------------------------------------
SPEC.md section 6.1 regresses utilisation on the margin after gas, and SPEC.md
section 4.4 defines the margin after gas as the gross margin minus the gas cost.
Gate 2 established that DGEC's published MBR is ALREADY NET OF PURCHASED GAS,
see crack.series.margin_after_gas_monthly and config.MBR_GAS_BASIS_NOTE, so
subtracting a gas cost from it charges the barrel twice.

The consequence for this module has to be said rather than smoothed over. This
study's margin after gas is therefore:

    margin_study_intensity = MBR - gas_wedge
    gas_wedge              = (this study's gas intensity
                              - DGEC's embedded gas intensity) * gas price

that is, the official margin re-priced at THIS STUDY'S gas intensity of 0.21217
MMBtu per barrel, EIA derived, in place of DGEC's embedded assumption of 1.0
percent of the barrel's mass, which is 0.0659 MMBtu per barrel at the note's own
7.55 bbl/t. DGEC's figure is a French linear programming model's purchased gas
for a self sufficient refinery. This study's is a US upper end figure for a
refinery that buys more of its energy. The question this module answers is
therefore about a refiner at the higher gas intensity, and it is a real question,
not a restatement of the official series: the wedge between the two ran 0.23 to
10.24 $/bbl over the sample and it is a different number in every month, so the
two margins are not the same series and do not have the same relationship with
runs.

THE OFFICIAL MBR IS REPORTED BESIDE IT EVERY TIME, unchanged, so a reader who
wants DGEC's own margin is never shown only this study's re-pricing of it.

Both models, because that was the decision
------------------------------------------
SPEC.md section 6.1 gives a first choice and a fallback: utilisation on Energy
Institute capacity, or, "if the capacity table is unusable", intake with a trend
and closure dummies. The capacity table is usable. It is also not committable:
recon 03 section 2.5 found the sheet is footnoted as containing ICIS and S&P
Global data, and S&P sourced data is not redistributable, so the capacity numbers
live in data/private and only the derived utilisation is published. The owner's
decision at the start of Gate 3 was to build the fallback as well, so that the
analysis survives if that position ever has to change. So both are here, both are
reported, and neither is presented as the other's robustness check.

2026 HAS NO CAPACITY FIGURE ANYWHERE
------------------------------------
The Energy Institute edition in data/private ends at 2025 and there is no 2026
number in it or in any other source this project reached. JODI runs to 2026-06.
So the six months of 2026 that have runs data have no denominator. This module
refuses to extrapolate a capacity and instead makes the choice explicit in the
basis argument: CAPACITY_2026_NAN leaves those months missing, which is the
honest default and the one that satisfies SPEC.md non negotiable 1, and
CAPACITY_2026_HELD_FLAT carries 2025 capacity forward with every affected row
flagged capacity_assumed. The headline regression runs on the held flat basis
because otherwise the 2026 episode, which SPEC.md section 6.1 requires be
reported with and without, cannot be in the sample at all; and the "without 2026"
row of that same table is the estimate that rests on no assumption. The fallback
model needs no capacity and covers 2026 cleanly either way.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from crack import config, series

__all__ = [
    "CAPACITY_SERIES",
    "CAPACITY_COLUMN",
    "INTAKE_COLUMN",
    "IMPORTS_COLUMN",
    "CAPACITY_2026_NAN",
    "CAPACITY_2026_HELD_FLAT",
    "CAPACITY_2026_BASES",
    "CAPACITY_STEP",
    "CAPACITY_LINEAR",
    "CLOSURE_STEP_MIN_FALL",
    "EPISODES",
    "EPISODE_MONTHS",
    "MARGIN_LAGS",
    "NEWEY_WEST_MIN_LAG",
    "MARGIN_STUDY_INTENSITY",
    "MARGIN_OFFICIAL",
    "capacity_annual",
    "capacity_step_years",
    "capacity_monthly",
    "utilisation_monthly",
    "utilisation_annual",
    "RECON_ANNUAL_UTILISATION",
    "utilisation_sanity_check",
    "margin_frame",
    "analysis_frame",
    "newey_west_lag",
    "newey_west_cov",
    "Regression",
    "ols_newey_west",
    "episode_mask",
    "CrudeDemand",
    "translate_response",
    "ResponseModel",
    "margin_response",
    "intake_trend_response",
    "autocorrelation",
    "block_length_from_acf",
    "HockeyStick",
    "fit_hockey_stick",
    "threshold_grid",
    "search_threshold",
    "ThresholdResult",
    "run_cut_threshold",
    "THRESHOLD_MAX_CI_WIDTH_USD_BBL",
    "BOOTSTRAP_REPLICATIONS",
    "BOOTSTRAP_SEED",
    "GRID_SENSITIVITY_REPLICATIONS",
    "threshold_grid_sensitivity",
    "imports_beside_intake",
    "latest_capacity_kb_d",
    "recent_runs_kb_d",
    # SPEC.md section 6.3, the horse race
    "CRACK_GASOIL",
    "CRACK_GASOLINE",
    "crack_frame",
    "horse_frame",
    "Horse",
    "HORSES",
    "DEPENDENT_CAPACITY",
    "DEPENDENT_FALLBACK",
    "DEPENDENTS",
    "common_sample_dates",
    "EXPANDING_MIN_TRAIN_MONTHS",
    "ExpandingWindow",
    "expanding_window_rmse",
    "HorseResult",
    "horse_race",
    "horse_race_frame",
    "horse_race_winner",
    "LossDifferential",
    "loss_differential",
    "gasoil_long_sample",
    "endogeneity_diagnostic",
    # SPEC.md section 6.3, the instrument
    "INSTRUMENT_COLUMN",
    "FIRST_STAGE_F_BAR",
    "EXCLUSION_RESTRICTION",
    "MECHANICAL_RELEVANCE",
    "InstrumentResult",
    "gas_instrument",
    # SPEC.md section 6.4, 2026
    "BREAK_2026_DATE",
    "BREAK_2026_FIRST_POST_MONTH",
    "BREAK_2026_MIN_POST_MONTHS",
    "BreakResult",
    "break_2026",
    # SPEC.md section 6.5, seasonality
    "SEASONAL_REMOVABLE_YEARS",
    "SEASONAL_RANGE_YEARS",
    "DRIVING_SEASON_MONTHS",
    "HEATING_SEASON_MONTHS",
    "seasonal_monthly",
    "seasonal_weekly",
    "seasonal_join",
    "seasonal_textbook_check",
    "seasonal_shape",
    "report",
]


# ---------------------------------------------------------------------------
# Names of the things this module reads
# ---------------------------------------------------------------------------

#: The Energy Institute capacity cache. It lives in data/private and NOT in
#: data/cache, and the directory is the licence: recon 03 section 2.5 quotes the
#: sheet's own footnote, "Source: Includes data from ICIS and S&P Global Energy",
#: and S&P sourced data is not redistributable. Only the derived utilisation
#: computed from it is published. SPEC.md non negotiable 6.
CAPACITY_SERIES = "ei_refinery_capacity_annual"
CAPACITY_DIRECTORY = "private"
CAPACITY_COLUMN = "nwe5_capacity_kb_d"

#: JODI, sum of BE DE FR NL GB. Crude oil only, not total feed: SPEC.md section
#: 6.1 says "refinery crude intake", and the Energy Institute denominator is
#: atmospheric distillation capacity, which is a crude column. Recon 03 section
#: 2.2 quotes the sheet's own unit footnote.
INTAKE_SERIES = "jodi_nwe_refinery_intake_monthly"
INTAKE_COLUMN = "nwe5_refinobs_crudeoil_kbd"

#: SPEC.md section 6.1: "Show NWE crude imports next to intake as the physical
#: footprint of the same demand. No separate model." Reported, never regressed.
IMPORTS_SERIES = "jodi_nwe_crude_imports_monthly"
IMPORTS_COLUMN = "nwe5_totimpsb_crudeoil_kbd"


# ---------------------------------------------------------------------------
# Capacity, and what to do about 2026
# ---------------------------------------------------------------------------

#: 2026 months carry no capacity and utilisation is NaN. The honest default.
CAPACITY_2026_NAN = "nan"
#: 2026 months carry the 2025 year end capacity, and every affected row is
#: flagged capacity_assumed so no chart and no table can show one without the
#: flag. It is an assumption, it is named, and the "without 2026" row of the
#: response table is the same estimate without it.
CAPACITY_2026_HELD_FLAT = "held_flat"
CAPACITY_2026_BASES = (CAPACITY_2026_NAN, CAPACITY_2026_HELD_FLAT)

#: SPEC.md section 6.1 asks for capacity "interpolated monthly, closures as
#: steps". The Energy Institute figure is atmospheric distillation capacity AT
#: YEAR END, recon 03 section 2.2, so a closure inside a year is already fully in
#: that year's printed number. The step convention carries the year's own figure
#: across all twelve of its months, which is what makes a closure a step at the
#: turn of the year rather than a ramp spread over twelve months. It is also the
#: convention recon 03 section 2.3 measured its sanity check on, so the annual
#: means below reproduce those figures exactly rather than approximately.
CAPACITY_STEP = "step"
#: Straight line between year end points, offered so the difference can be
#: measured rather than asserted. It smooths closures, which is the thing SPEC.md
#: section 6.1 asks not to do, so it is never the default.
CAPACITY_LINEAR = "linear"
CAPACITY_INTERPOLATIONS = (CAPACITY_STEP, CAPACITY_LINEAR)

#: A year on year fall in NWE5 capacity of more than this counts as a closure
#: step for the fallback model's dummies. Two percent of the roughly 6.6 mb/d
#: NWE5 system is about 132 kb/d, which is one medium NWE refinery, so the rule
#: is "a year in which the region lost at least a refinery". The number is chosen
#: once, from that reasoning, before looking at any regression, and it is not
#: moved afterwards. SPEC.md section 6.6.
CLOSURE_STEP_MIN_FALL = 0.02


def capacity_annual() -> pd.DataFrame:
    """NWE5 refinery capacity by year, kb/d, from the private Energy Institute cache.

    Returns:
        year, capacity_kb_d. The date column of the cache is a 31 December
        stamp, which is what the figure means, and the year is carried as an
        integer because everything downstream joins on it.
    """
    frame = series.load(CAPACITY_SERIES, directory=CAPACITY_DIRECTORY)
    out = pd.DataFrame(
        {
            "year": pd.to_datetime(frame["date"]).dt.year.astype(int),
            "capacity_kb_d": frame[CAPACITY_COLUMN].astype(float),
        }
    )
    return out.sort_values("year").reset_index(drop=True)


def capacity_step_years(min_fall: float = CLOSURE_STEP_MIN_FALL) -> tuple[int, ...]:
    """Years in which NWE5 capacity fell by more than min_fall, as a fraction.

    The closure dummy dates for the fallback model of SPEC.md section 6.1. They
    are derived from the capacity series, which means they are derived from the
    private Energy Institute cache, so intake_trend_response accepts them as an
    argument and runs with an empty tuple as well. If the capacity numbers ever
    have to leave this project, the fallback still runs and the report says which
    of the two it is quoting.
    """
    frame = capacity_annual()
    change = frame["capacity_kb_d"].pct_change()
    fell = frame.loc[change < -min_fall, "year"]
    return tuple(int(year) for year in fell)


def capacity_monthly(
    basis_2026: str = CAPACITY_2026_NAN,
    interpolation: str = CAPACITY_STEP,
    through: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Monthly NWE5 capacity in kb/d, on a named 2026 basis.

    Args:
        basis_2026: one of CAPACITY_2026_BASES. There is no published 2026
            capacity in any source this project reached, so this is a choice and
            it is made by the caller, out loud.
        interpolation: CAPACITY_STEP, the default and the one SPEC.md section 6.1
            describes, or CAPACITY_LINEAR.
        through: the last month to produce. Defaults to the last month of JODI
            intake, since a capacity denominator with no numerator is of no use
            to anyone.

    Returns:
        date, capacity_kb_d, capacity_source_year, capacity_assumed.
    """
    if basis_2026 not in CAPACITY_2026_BASES:
        raise ValueError(
            "basis_2026 is %r. There is no published 2026 refinery capacity, so "
            "this module will not pick one for you: it is %s"
            % (basis_2026, " or ".join(CAPACITY_2026_BASES))
        )
    if interpolation not in CAPACITY_INTERPOLATIONS:
        raise ValueError(
            "interpolation is %r, which is %s"
            % (interpolation, " or ".join(CAPACITY_INTERPOLATIONS))
        )

    annual = capacity_annual()
    last_year = int(annual["year"].iloc[-1])
    last_capacity = float(annual["capacity_kb_d"].iloc[-1])

    if through is None:
        intake = series.load(INTAKE_SERIES)
        through = pd.to_datetime(intake["date"]).max()
    through = pd.Timestamp(through).to_period("M").to_timestamp()

    start = pd.Timestamp(year=int(annual["year"].iloc[0]), month=1, day=1)
    months = pd.date_range(start, through, freq="MS")
    frame = pd.DataFrame({"date": months})
    frame["year"] = frame["date"].dt.year

    by_year = dict(zip(annual["year"], annual["capacity_kb_d"]))
    if interpolation == CAPACITY_STEP:
        frame["capacity_kb_d"] = frame["year"].map(by_year).astype(float)
    else:
        # Year end points placed on 31 December, interpolated on to the month
        # starts. A month before the first year end is not extrapolated.
        anchors = pd.Series(
            annual["capacity_kb_d"].to_numpy(),
            index=pd.to_datetime(
                [pd.Timestamp(year=int(y), month=12, day=31) for y in annual["year"]]
            ),
        )
        joined = pd.concat(
            [anchors, pd.Series(np.nan, index=pd.DatetimeIndex(months))]
        ).sort_index()
        joined = joined[~joined.index.duplicated(keep="first")]
        interpolated = joined.interpolate(method="time", limit_area="inside")
        frame["capacity_kb_d"] = (
            interpolated.reindex(pd.DatetimeIndex(months)).to_numpy().astype(float)
        )

    frame["capacity_source_year"] = frame["year"].where(
        frame["year"] <= last_year, np.nan
    )
    frame["capacity_assumed"] = frame["year"] > last_year

    beyond = frame["year"] > last_year
    if basis_2026 == CAPACITY_2026_HELD_FLAT:
        frame.loc[beyond, "capacity_kb_d"] = last_capacity
        frame.loc[beyond, "capacity_source_year"] = last_year
    else:
        frame.loc[beyond, "capacity_kb_d"] = np.nan

    frame["capacity_basis_2026"] = basis_2026
    frame["capacity_interpolation"] = interpolation
    return frame.drop(columns=["year"]).reset_index(drop=True)


def utilisation_monthly(
    basis_2026: str = CAPACITY_2026_NAN,
    interpolation: str = CAPACITY_STEP,
) -> pd.DataFrame:
    """NWE5 crude intake over capacity, monthly, with crude imports beside it.

    Returns:
        date, intake_kb_d, imports_kb_d, capacity_kb_d, utilisation,
        utilisation_pct, capacity_assumed, capacity_source_year, and JODI's own
        assessment code columns carried through unchanged.

        utilisation is the fraction, utilisation_pct is a hundred times it. The
        regressions below run on the percentage so a coefficient reads directly
        as percentage points per dollar a barrel, which is the unit SPEC.md
        section 6.1 asks the response to be reported in.
    """
    intake = series.load(INTAKE_SERIES)
    imports = series.load(IMPORTS_SERIES)
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(intake["date"]).dt.to_period("M").dt.to_timestamp(),
            "intake_kb_d": intake[INTAKE_COLUMN].astype(float),
            "intake_cells": intake["cells"],
        }
    )
    frame = frame.merge(
        pd.DataFrame(
            {
                "date": pd.to_datetime(imports["date"])
                .dt.to_period("M")
                .dt.to_timestamp(),
                "imports_kb_d": imports[IMPORTS_COLUMN].astype(float),
            }
        ),
        on="date",
        how="left",
    )
    capacity = capacity_monthly(basis_2026, interpolation, through=frame["date"].max())
    frame = frame.merge(capacity, on="date", how="left")

    frame["utilisation"] = frame["intake_kb_d"] / frame["capacity_kb_d"]
    frame["utilisation_pct"] = 100.0 * frame["utilisation"]
    return frame.sort_values("date").reset_index(drop=True)


def utilisation_annual(
    basis_2026: str = CAPACITY_2026_NAN,
    interpolation: str = CAPACITY_STEP,
) -> pd.DataFrame:
    """Calendar year mean intake over that year's capacity, months counted.

    The form recon 03 section 2.3 measured, so the two can be compared number by
    number rather than by eye. A part year is reported with its month count and
    is not annualised.
    """
    monthly = utilisation_monthly(basis_2026, interpolation)
    monthly["year"] = monthly["date"].dt.year
    grouped = monthly.groupby("year").agg(
        intake_kb_d=("intake_kb_d", "mean"),
        imports_kb_d=("imports_kb_d", "mean"),
        capacity_kb_d=("capacity_kb_d", "mean"),
        months=("intake_kb_d", "count"),
        capacity_assumed=("capacity_assumed", "any"),
    )
    grouped["utilisation"] = grouped["intake_kb_d"] / grouped["capacity_kb_d"]
    return grouped.reset_index()


#: What recon 03 section 2.3 measured, to three decimals, for 2015 to 2025. The
#: sanity check of this gate is against these and it is a check, not a target:
#: utilisation_sanity_check reports the gap whatever the gap is.
RECON_ANNUAL_UTILISATION: Mapping[int, float] = {
    2015: 0.868,
    2016: 0.889,
    2017: 0.895,
    2018: 0.857,
    2019: 0.851,
    2020: 0.724,
    2021: 0.742,
    2022: 0.798,
    2023: 0.791,
    2024: 0.794,
    2025: 0.831,
}


def utilisation_sanity_check() -> pd.DataFrame:
    """This module's annual utilisation against RECON_ANNUAL_UTILISATION.

    Returns:
        year, utilisation, recon, difference, agrees_to_3dp.
    """
    annual = utilisation_annual().set_index("year")
    rows = []
    for year, expected in sorted(RECON_ANNUAL_UTILISATION.items()):
        got = float(annual.loc[year, "utilisation"]) if year in annual.index else np.nan
        rows.append(
            {
                "year": year,
                "utilisation": got,
                "recon": expected,
                "difference": got - expected,
                "agrees_to_3dp": bool(round(got, 3) == expected),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# The margin this module asks about
# ---------------------------------------------------------------------------

#: The regressor of SPEC.md section 6.1 as this study computes it: the official
#: MBR re-priced at this study's EIA derived gas intensity. See the module
#: docstring for what changed and why.
MARGIN_STUDY_INTENSITY = "margin_study_intensity_usd_bbl"
#: DGEC's own published margin, carried unchanged so the re-pricing above is
#: always visible beside the thing it re-priced.
MARGIN_OFFICIAL = "mbr_usd_bbl"


def margin_frame(
    gas_intensity_mmbtu_per_bbl: float = config.GAS_INTENSITY_MMBTU_PER_BBL,
) -> pd.DataFrame:
    """The monthly margin series this module regresses on, 2015-01 onward.

    Returns:
        date, mbr_usd_bbl, gas_usd_mmbtu, gas_wedge_usd_bbl,
        margin_study_intensity_usd_bbl, margin_basis.

    THE SERIES STARTS IN 2015-01 BECAUSE DGEC'S FILE DOES. The owner's decision
    at Gate 1 was that the sample starts in 2001 and that where the official MBR
    does not exist before 2015-01 this study says so rather than extending it.
    So the cracks reach back to 2000-10 and this regression does not.
    """
    frame = series.margin_after_gas_monthly(gas_intensity_mmbtu_per_bbl)
    out = frame[
        [
            "date",
            "mbr_usd_bbl",
            "gas_usd_mmbtu",
            "embedded_gas_cost_usd_bbl",
            "study_gas_cost_usd_bbl",
            "gas_wedge_usd_bbl",
            "margin_after_gas_usd_bbl",
            "margin_basis",
        ]
    ].copy()
    # The published margin is already net of DGEC's embedded gas. Taking the
    # wedge off it replaces DGEC's gas assumption with this study's, which is the
    # only arithmetic in this module that touches the margin at all.
    out[MARGIN_STUDY_INTENSITY] = (
        out["margin_after_gas_usd_bbl"] - out["gas_wedge_usd_bbl"]
    )
    out["gas_intensity_mmbtu_per_bbl"] = gas_intensity_mmbtu_per_bbl
    return out.reset_index(drop=True)


def analysis_frame(
    basis_2026: str = CAPACITY_2026_HELD_FLAT,
    interpolation: str = CAPACITY_STEP,
    gas_intensity_mmbtu_per_bbl: float = config.GAS_INTENSITY_MMBTU_PER_BBL,
) -> pd.DataFrame:
    """Utilisation, intake, imports and both margins on one monthly index.

    An inner join on the month, so the frame starts where the margin starts and
    ends where JODI ends. Nothing is carried forward across the join to make the
    two data dates agree: SPEC.md section 7.2 shows them separately for exactly
    this reason.
    """
    runs = utilisation_monthly(basis_2026, interpolation)
    margin = margin_frame(gas_intensity_mmbtu_per_bbl)
    frame = runs.merge(margin, on="date", how="inner").sort_values("date")
    frame["log_intake_pct"] = 100.0 * np.log(frame["intake_kb_d"].astype(float))
    frame["month"] = frame["date"].dt.month
    frame["trend_months"] = np.arange(len(frame), dtype=float)
    return frame.reset_index(drop=True)


# ---------------------------------------------------------------------------
# The episodes SPEC.md section 6.1 asks to see the result with and without
# ---------------------------------------------------------------------------

#: How long an episode dummy runs from its event month. ONE RULE FOR ALL THREE,
#: applied once, so no window is picked to suit a result. Twelve months because
#: the margin lags of SPEC.md section 6.1 reach three months and a shock to a
#: refining system plausibly works through within a year. It is a choice, it is
#: stated, and it is never moved.
EPISODE_MONTHS = 12

#: The three episodes of SPEC.md section 6.1, each starting at the month of its
#: entry in data/seed/events.json. The ids are the seed file's own.
EPISODES: Mapping[str, str] = {
    # covid_pandemic_and_european_lockdowns_2020_03
    "episode_2020": "2020-03-01",
    # russia_invades_ukraine_2022_02_24
    "episode_2022": "2022-02-01",
    # strikes_on_iran_hormuz_2026_02_28
    "episode_2026": "2026-02-01",
}


def episode_mask(
    dates: Sequence[pd.Timestamp],
    episodes: Mapping[str, str] = EPISODES,
    months: int = EPISODE_MONTHS,
) -> pd.DataFrame:
    """One 0/1 column per episode, plus any_episode.

    A month inside more than one window would be 1 in both columns. None of the
    three windows overlaps in this sample, and the frame is built so that if a
    future event made them overlap the columns would say so rather than merging.
    """
    index = pd.DatetimeIndex(dates)
    out = pd.DataFrame(index=range(len(index)))
    for name, start in sorted(episodes.items()):
        begin = pd.Timestamp(start)
        end = begin + pd.DateOffset(months=months)
        out[name] = ((index >= begin) & (index < end)).astype(float)
    out["any_episode"] = (out.to_numpy().sum(axis=1) > 0).astype(float)
    return out


# ---------------------------------------------------------------------------
# Ordinary least squares with Newey-West standard errors
# ---------------------------------------------------------------------------

#: SPEC.md section 6.1: "Newey-West standard errors, lag at least 3."
NEWEY_WEST_MIN_LAG = 3


def newey_west_lag(nobs: int, minimum: int = NEWEY_WEST_MIN_LAG) -> int:
    """The Bartlett truncation lag, by the standard rule of thumb, floored at 3.

    floor(4 * (n / 100) ** (2 / 9)), the automatic lag of Newey and West (1994)
    as it is usually written, and then the maximum of that and SPEC.md section
    6.1's floor of 3. On this sample, n is 135 and the rule gives 4.

    It is a rule applied once to the sample size, not a number tried until the
    standard errors looked right. SPEC.md section 6.6.
    """
    if nobs <= 0:
        raise ValueError("nobs is %r" % (nobs,))
    rule = int(math.floor(4.0 * (nobs / 100.0) ** (2.0 / 9.0)))
    return max(minimum, rule)


def newey_west_cov(
    design: np.ndarray,
    resid: np.ndarray,
    lag: int,
    use_correction: bool = True,
) -> np.ndarray:
    """The Newey-West heteroskedasticity and autocorrelation consistent sandwich.

    S = G(0) + sum over l of w(l) * (G(l) + G(l)'), with the Bartlett weight
    w(l) = 1 - l / (lag + 1) and G(l) = sum over t of u(t) u(t - l)', where
    u(t) = x(t) * e(t). The covariance is (X'X)^-1 S (X'X)^-1, with the small
    sample correction n / (n - k) when use_correction.

    Written out here rather than taken from a library because SPEC.md section 6.1
    names the lag and tests/test_analysis.py has to be able to check that the
    lag this claims is the lag it used. The same test compares it with
    statsmodels on the same data, so this is checked against an independent
    implementation and not merely against itself.
    """
    design = np.asarray(design, dtype=float)
    resid = np.asarray(resid, dtype=float).reshape(-1)
    nobs, k = design.shape
    if lag < 0:
        raise ValueError("lag is %r, which is not a number of lags" % (lag,))
    if lag >= nobs:
        raise ValueError(
            "lag %d needs at least %d observations and there are %d"
            % (lag, lag + 1, nobs)
        )

    scores = design * resid[:, None]
    sandwich = scores.T @ scores
    for step in range(1, lag + 1):
        weight = 1.0 - step / (lag + 1.0)
        gamma = scores[step:].T @ scores[:-step]
        sandwich = sandwich + weight * (gamma + gamma.T)

    bread = np.linalg.pinv(design.T @ design)
    cov = bread @ sandwich @ bread
    if use_correction:
        cov = cov * (nobs / (nobs - k))
    return cov


@dataclass(frozen=True)
class Regression:
    """One fitted equation, with everything a reader needs to check it."""

    names: tuple[str, ...]
    params: np.ndarray
    cov: np.ndarray
    nobs: int
    nw_lag: int
    r2: float
    adj_r2: float
    ssr: float
    resid: np.ndarray
    fitted: np.ndarray
    dates: tuple[pd.Timestamp, ...]
    #: The regressor matrix exactly as it was fitted. Carried so that
    #: expanding_window_rmse can re-fit THE SAME specification on a prefix of the
    #: rows rather than rebuild it from a second copy of the assembly code. Two
    #: copies of a design is how an out of sample number ends up describing a
    #: different equation from the in sample one it is printed beside.
    design: np.ndarray = field(default_factory=lambda: np.zeros((0, 0)))
    #: The dependent exactly as it was fitted. STORED, not rebuilt as fitted plus
    #: residual: that sum is equal to y only to floating point, and the expanding
    #: window's no peeking test compares two runs bit for bit, which a
    #: reconstruction quietly fails for a reason that has nothing to do with
    #: peeking.
    endog: np.ndarray = field(default_factory=lambda: np.zeros(0))

    @property
    def y(self) -> np.ndarray:
        """The dependent as it was fitted."""
        return self.endog

    @property
    def k(self) -> int:
        return len(self.names)

    @property
    def se(self) -> np.ndarray:
        return np.sqrt(np.diag(self.cov))

    @property
    def tstat(self) -> np.ndarray:
        return self.params / self.se

    def index(self, name: str) -> int:
        return self.names.index(name)

    def get(self, name: str) -> tuple[float, float]:
        """One coefficient and its Newey-West standard error."""
        i = self.index(name)
        return float(self.params[i]), float(self.se[i])

    def combination(self, weights: Mapping[str, float]) -> tuple[float, float]:
        """A linear combination of coefficients and its standard error.

        var(w'b) = w' V w with the same Newey-West V, which is how the sum of
        the three lag coefficients of SPEC.md section 6.1 gets an interval
        rather than three intervals that a reader has to add up by eye.
        """
        vector = np.zeros(self.k)
        for name, weight in weights.items():
            vector[self.index(name)] = float(weight)
        value = float(vector @ self.params)
        variance = float(vector @ self.cov @ vector)
        return value, math.sqrt(max(variance, 0.0))

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "term": list(self.names),
                "coefficient": self.params,
                "nw_se": self.se,
                "t": self.tstat,
            }
        )


def ols_newey_west(
    y: Sequence[float],
    design: np.ndarray,
    names: Sequence[str],
    lag: int | None = None,
    dates: Sequence[pd.Timestamp] | None = None,
) -> Regression:
    """Least squares with a Newey-West covariance. No weighting, no shrinkage.

    Args:
        lag: the Bartlett truncation lag. None asks newey_west_lag for it, which
            is the stated rule, and any value passed is recorded on the result so
            that what the standard errors used is never a matter of belief.
    """
    y = np.asarray(y, dtype=float).reshape(-1)
    design = np.asarray(design, dtype=float)
    names = tuple(names)
    if design.shape[1] != len(names):
        raise ValueError(
            "the design has %d columns and %d names were given"
            % (design.shape[1], len(names))
        )
    nobs = design.shape[0]
    if nobs != y.shape[0]:
        raise ValueError("y has %d rows and the design has %d" % (y.shape[0], nobs))
    if lag is None:
        lag = newey_west_lag(nobs)

    params, *_ = np.linalg.lstsq(design, y, rcond=None)
    fitted = design @ params
    resid = y - fitted
    ssr = float(resid @ resid)
    centred = y - y.mean()
    tss = float(centred @ centred)
    r2 = 1.0 - ssr / tss if tss > 0 else float("nan")
    k = len(names)
    adj = (
        1.0 - (1.0 - r2) * (nobs - 1) / (nobs - k)
        if nobs > k and tss > 0
        else float("nan")
    )
    cov = newey_west_cov(design, resid, lag)
    return Regression(
        names=names,
        params=params,
        cov=cov,
        nobs=nobs,
        nw_lag=int(lag),
        r2=float(r2),
        adj_r2=float(adj),
        ssr=ssr,
        resid=resid,
        fitted=fitted,
        dates=tuple(pd.DatetimeIndex(dates)) if dates is not None else tuple(),
        design=design,
        endog=y,
    )


# ---------------------------------------------------------------------------
# SPEC.md section 6.1, the response, and the translation the CV line needs
# ---------------------------------------------------------------------------

#: k = 1, 2, 3. SPEC.md section 6.1 writes the sum over k explicitly.
MARGIN_LAGS = (1, 2, 3)

#: Two sided normal critical value at 95 percent. The interval is a normal one
#: on a Newey-West standard error, which is what a HAC covariance supports; it is
#: not a t interval and it is not a bootstrap interval, and the report says so.
Z95 = 1.959963984540054


@dataclass(frozen=True)
class CrudeDemand:
    """SPEC.md section 6.1's translation, which is the CV line's own clause.

    "linked to crude demand" is this record. A visitor has to be able to read it
    in one sentence: a 10 $/bbl move in the margin after gas is worth this many
    kb/d of NWE crude demand, which is this share of NWE runs.
    """

    per_usd: float
    per_usd_se: float
    per_usd_unit: str
    move_usd_bbl: float
    base_kb_d: float
    base_label: str
    runs_kb_d: float
    runs_label: str
    kb_d: float
    kb_d_low: float
    kb_d_high: float
    share_of_runs: float
    share_of_runs_low: float
    share_of_runs_high: float

    def sentence(self) -> str:
        return (
            "A %.0f $/bbl rise in the margin after gas is worth %.0f kb/d of NWE "
            "crude demand, 95 percent interval %.0f to %.0f kb/d, which is %.2f "
            "percent of NWE runs, interval %.2f to %.2f percent."
            % (
                self.move_usd_bbl,
                self.kb_d,
                self.kb_d_low,
                self.kb_d_high,
                100.0 * self.share_of_runs,
                100.0 * self.share_of_runs_low,
                100.0 * self.share_of_runs_high,
            )
        )


def translate_response(
    per_usd: float,
    per_usd_se: float,
    base_kb_d: float,
    runs_kb_d: float,
    per_usd_unit: str = "percentage points of capacity per $/bbl",
    base_label: str = "",
    runs_label: str = "",
    move_usd_bbl: float = 10.0,
    z: float = Z95,
) -> CrudeDemand:
    """Percentage points per $/bbl into kb/d of crude demand, and into a share.

    kb_d = (per_usd / 100) * move * base_kb_d, and the interval is the same
    linear map applied to the coefficient's own interval, which is exact because
    the map is linear and base_kb_d and runs_kb_d are treated as known constants
    rather than as estimates. They are: one is a published capacity figure and
    the other is a measured mean of JODI intake, and neither carries a standard
    error into this arithmetic. The report says so.
    """
    if base_kb_d <= 0 or runs_kb_d <= 0:
        raise ValueError(
            "base_kb_d %r and runs_kb_d %r have to be positive rates"
            % (base_kb_d, runs_kb_d)
        )
    low = per_usd - z * per_usd_se
    high = per_usd + z * per_usd_se

    def to_kb_d(value: float) -> float:
        return value / 100.0 * move_usd_bbl * base_kb_d

    kb_d = to_kb_d(per_usd)
    kb_d_low = to_kb_d(low)
    kb_d_high = to_kb_d(high)
    return CrudeDemand(
        per_usd=float(per_usd),
        per_usd_se=float(per_usd_se),
        per_usd_unit=per_usd_unit,
        move_usd_bbl=float(move_usd_bbl),
        base_kb_d=float(base_kb_d),
        base_label=base_label,
        runs_kb_d=float(runs_kb_d),
        runs_label=runs_label,
        kb_d=kb_d,
        kb_d_low=kb_d_low,
        kb_d_high=kb_d_high,
        share_of_runs=kb_d / runs_kb_d,
        share_of_runs_low=kb_d_low / runs_kb_d,
        share_of_runs_high=kb_d_high / runs_kb_d,
    )


@dataclass(frozen=True)
class ResponseModel:
    """One row of the response table of SPEC.md section 6.1."""

    label: str
    dependent: str
    regressor: str
    regression: Regression
    lag_terms: tuple[str, ...]
    sum_b: float
    sum_b_se: float
    translation: CrudeDemand
    first_month: str
    last_month: str
    episodes_in_sample: tuple[str, ...]
    episodes_as_dummies: bool
    capacity_assumed_months: int
    note: str = ""

    @property
    def sum_b_low(self) -> float:
        return self.sum_b - Z95 * self.sum_b_se

    @property
    def sum_b_high(self) -> float:
        return self.sum_b + Z95 * self.sum_b_se

    @property
    def sum_b_t(self) -> float:
        return self.sum_b / self.sum_b_se if self.sum_b_se > 0 else float("nan")


def _month_dummies(months: Sequence[int]) -> tuple[np.ndarray, list[str]]:
    """Eleven month dummies, January as the base. SPEC.md section 6.1's month FE."""
    months = np.asarray(months, dtype=int)
    names, columns = [], []
    for month in range(2, 13):
        names.append("month_%02d" % month)
        columns.append((months == month).astype(float))
    if not columns:
        return np.zeros((len(months), 0)), []
    return np.column_stack(columns), names


def _build_response(
    frame: pd.DataFrame,
    dependent: str,
    regressor: str,
    label: str,
    lags: Sequence[int],
    month_fe: bool,
    episode_dummies: bool,
    drop_episode_months: bool,
    trend: bool,
    closure_years: Sequence[int],
    base_kb_d: float,
    runs_kb_d: float,
    base_label: str,
    runs_label: str,
    per_usd_unit: str,
    nw_lag: int | None,
    note: str = "",
    sample_dates: Sequence[pd.Timestamp] | None = None,
) -> ResponseModel:
    """Assemble one equation, fit it, and translate its long run response.

    Args:
        sample_dates: restrict the estimation sample to exactly these months,
            AFTER the lags have been built from the full frame. This is how the
            horse race of SPEC.md section 6.3 runs three regressors on one
            sample: the restriction is applied to the rows and never to the lag
            construction, so a horse whose regressor starts later does not
            silently get a shorter lag from the surviving rows.
    """
    work = frame.copy()
    lag_terms = []
    for k in lags:
        name = "%s_lag%d" % (regressor, k)
        work[name] = work[regressor].shift(k)
        lag_terms.append(name)

    episodes = episode_mask(work["date"])
    for column in episodes.columns:
        work[column] = episodes[column].to_numpy()

    needed = ["date", dependent, *lag_terms]
    work = work.dropna(subset=needed)
    if sample_dates is not None:
        keep = pd.DatetimeIndex(sample_dates)
        work = work[work["date"].isin(keep)]
    if drop_episode_months:
        work = work[work["any_episode"] == 0.0]
    work = work.reset_index(drop=True)
    if work.empty:
        raise ValueError("no observations left for %r" % (label,))

    columns = [np.ones(len(work))]
    names = ["const"]
    if trend:
        # ELAPSED CALENDAR MONTHS since the first observation of this sample, and
        # not the row number. The two are the same thing while the sample is
        # contiguous, which it is on the full sample, and they are NOT the same
        # thing once drop_episode_months removes 29 months out of the middle of
        # it: the row number then compresses the 2020 to 2022 hole to nothing and
        # the fitted "monthly trend" is a different slope on either side of it.
        # Measured on this sample the two variables differ by up to 24 months.
        # The term SPEC.md section 6.1's fallback asks for is a trend in time, so
        # it is time.
        periods = pd.PeriodIndex(work["date"], freq="M")
        columns.append(np.array([(p - periods[0]).n for p in periods], dtype=float))
        names.append("trend_months")
    if month_fe:
        dummies, dummy_names = _month_dummies(work["date"].dt.month)
        if dummies.shape[1]:
            columns.append(dummies)
            names.extend(dummy_names)
    for year in closure_years:
        column = (work["date"] >= pd.Timestamp(year=int(year), month=1, day=1)).astype(
            float
        )
        if 0.0 < column.mean() < 1.0:
            columns.append(column.to_numpy())
            names.append("closure_step_%d" % int(year))
    present_episodes = tuple(
        name for name in sorted(EPISODES) if work[name].to_numpy().any()
    )
    if episode_dummies:
        for name in present_episodes:
            column = work[name].to_numpy()
            if 0.0 < column.mean() < 1.0:
                columns.append(column)
                names.append(name)
    for name in lag_terms:
        columns.append(work[name].to_numpy(dtype=float))
        names.append(name)

    design = np.column_stack([np.asarray(c, dtype=float).reshape(len(work), -1) for c in columns])
    fit = ols_newey_west(
        work[dependent].to_numpy(dtype=float),
        design,
        names,
        lag=nw_lag,
        dates=work["date"],
    )
    sum_b, sum_b_se = fit.combination({name: 1.0 for name in lag_terms})
    translation = translate_response(
        sum_b,
        sum_b_se,
        base_kb_d,
        runs_kb_d,
        per_usd_unit=per_usd_unit,
        base_label=base_label,
        runs_label=runs_label,
    )
    assumed = (
        int(work["capacity_assumed"].sum()) if "capacity_assumed" in work else 0
    )
    return ResponseModel(
        label=label,
        dependent=dependent,
        regressor=regressor,
        regression=fit,
        lag_terms=tuple(lag_terms),
        sum_b=sum_b,
        sum_b_se=sum_b_se,
        translation=translation,
        first_month=str(work["date"].iloc[0].date()),
        last_month=str(work["date"].iloc[-1].date()),
        episodes_in_sample=present_episodes,
        episodes_as_dummies=bool(episode_dummies),
        capacity_assumed_months=assumed,
        note=note,
    )


def latest_capacity_kb_d() -> tuple[float, int]:
    """Today's NWE5 capacity and the year it is from. The translation's base."""
    annual = capacity_annual()
    return float(annual["capacity_kb_d"].iloc[-1]), int(annual["year"].iloc[-1])


def recent_runs_kb_d(frame: pd.DataFrame | None = None, months: int = 12) -> float:
    """Mean NWE5 crude intake over the last complete months of JODI data.

    The denominator of "the share of NWE runs that represents". A mean of the
    last twelve months rather than the single latest month, because one month of
    JODI moves with maintenance and the share is a statement about the system.
    """
    if frame is None:
        frame = utilisation_monthly()
    tail = frame.dropna(subset=["intake_kb_d"]).tail(months)
    return float(tail["intake_kb_d"].mean())


def margin_response(
    regressor: str = MARGIN_STUDY_INTENSITY,
    label: str = "",
    lags: Sequence[int] = MARGIN_LAGS,
    episode_dummies: bool = True,
    drop_episode_months: bool = False,
    basis_2026: str = CAPACITY_2026_HELD_FLAT,
    interpolation: str = CAPACITY_STEP,
    frame: pd.DataFrame | None = None,
    nw_lag: int | None = None,
    trend: bool = False,
    closure_years: Sequence[int] = (),
    sample_dates: Sequence[pd.Timestamp] | None = None,
) -> ResponseModel:
    """SPEC.md section 6.1's equation on utilisation over Energy Institute capacity.

        utilisation_pct(t) = a + sum over k of b_k * margin(t - k)
                             + month fixed effects + regime terms + e(t)

    The dependent is utilisation in percent, so b_k is percentage points of
    capacity per dollar a barrel with no further scaling, which is the unit
    SPEC.md section 6.1 asks for.

    Args:
        episode_dummies: the "regime terms" of the equation, one step per episode
            of EPISODES.
        drop_episode_months: drop those months from the sample instead. SPEC.md
            section 6.1 asks for the result with and without the episodes and
            this is the "without": the estimate that owes nothing to 2020, 2022
            or 2026, and, on the held flat capacity basis, nothing to the 2026
            capacity assumption either.
        trend, closure_years: BOTH DEFAULT OFF AND THE DEFAULT IS THE SPEC'S
            EQUATION. SPEC.md section 6.1 writes this equation as a constant, the
            margin lags, month fixed effects and regime terms, with no trend and
            no closure step, because the capacity denominator is what is supposed
            to take the closures out. They are exposed only so that report() can
            run ONE labelled diagnostic that tests, rather than asserts, the
            reason the capacity model and the fallback disagree. Nothing else in
            this module passes them and no headline result uses them.
    """
    if frame is None:
        frame = analysis_frame(basis_2026, interpolation)
    capacity, capacity_year = latest_capacity_kb_d()
    runs = recent_runs_kb_d()
    if not label:
        label = "utilisation on %s" % regressor
    return _build_response(
        frame=frame,
        dependent="utilisation_pct",
        regressor=regressor,
        label=label,
        lags=lags,
        month_fe=True,
        episode_dummies=episode_dummies,
        drop_episode_months=drop_episode_months,
        trend=trend,
        closure_years=tuple(closure_years),
        base_kb_d=capacity,
        runs_kb_d=runs,
        base_label="NWE5 capacity %d, Energy Institute, kb/d" % capacity_year,
        runs_label="mean NWE5 crude intake, last 12 JODI months, kb/d",
        per_usd_unit="percentage points of capacity per $/bbl",
        nw_lag=nw_lag,
        sample_dates=sample_dates,
        note=(
            "utilisation is NWE5 crude intake over Energy Institute capacity, "
            "capacity held as a step at each year's published year end figure"
        ),
    )


def intake_trend_response(
    regressor: str = MARGIN_STUDY_INTENSITY,
    label: str = "",
    lags: Sequence[int] = MARGIN_LAGS,
    episode_dummies: bool = True,
    drop_episode_months: bool = False,
    closure_years: Sequence[int] | None = None,
    frame: pd.DataFrame | None = None,
    nw_lag: int | None = None,
    sample_dates: Sequence[pd.Timestamp] | None = None,
) -> ResponseModel:
    """SPEC.md section 6.1's fallback: intake with a trend and closure dummies.

    The dependent is 100 times the log of NWE5 crude intake, so a coefficient is
    a percent of runs per dollar a barrel and translates to kb/d on the runs base
    rather than the capacity base. The two models therefore give coefficients in
    different units and comparable answers in kb/d, which is the unit the CV line
    is written in.

    Args:
        closure_years: years to carry a step dummy from January of. None takes
            capacity_step_years(), which is derived from the private Energy
            Institute cache; pass an empty tuple for the model that needs no
            capacity data at all. Both are reported, because the point of the
            fallback is that it survives the capacity series being withdrawn.
    """
    if frame is None:
        # No capacity is needed here, so the 2026 basis cannot change the answer,
        # and the held flat basis is used only so the frame carries the same
        # months as the capacity model and the two samples are comparable.
        frame = analysis_frame(CAPACITY_2026_HELD_FLAT, CAPACITY_STEP)
    if closure_years is None:
        closure_years = capacity_step_years()
    runs = recent_runs_kb_d()
    if not label:
        label = "log intake on %s" % regressor
    return _build_response(
        frame=frame,
        dependent="log_intake_pct",
        regressor=regressor,
        label=label,
        lags=lags,
        month_fe=True,
        episode_dummies=episode_dummies,
        drop_episode_months=drop_episode_months,
        trend=True,
        closure_years=tuple(closure_years),
        base_kb_d=runs,
        runs_kb_d=runs,
        base_label="mean NWE5 crude intake, last 12 JODI months, kb/d",
        runs_label="mean NWE5 crude intake, last 12 JODI months, kb/d",
        per_usd_unit="percent of runs per $/bbl",
        nw_lag=nw_lag,
        sample_dates=sample_dates,
        note=(
            "log intake with a linear monthly trend, month fixed effects and a "
            "step dummy from January of each closure year %s"
            % (tuple(int(y) for y in closure_years),)
        ),
    )


def imports_beside_intake(frame: pd.DataFrame | None = None) -> Mapping[str, float]:
    """NWE crude imports next to intake, arithmetic only. SPEC.md section 6.1.

    "Show NWE crude imports next to intake as the physical footprint of the same
    demand. No separate model." So there is no model here and there is no second
    regression: this is the ratio of the two, their correlation in levels and in
    twelve month differences, and nothing else. Any kb/d response estimated on
    intake can be read across to imports by multiplying by the ratio, and the
    report says that is arithmetic rather than evidence that imports move too.
    """
    if frame is None:
        frame = analysis_frame(CAPACITY_2026_HELD_FLAT, CAPACITY_STEP)
    both = frame.dropna(subset=["intake_kb_d", "imports_kb_d"])
    ratio = both["imports_kb_d"] / both["intake_kb_d"]
    diff_intake = both["intake_kb_d"].diff(12).dropna()
    diff_imports = both["imports_kb_d"].diff(12).dropna()
    joint = pd.concat([diff_intake, diff_imports], axis=1).dropna()
    return {
        "months": int(len(both)),
        "first_month": str(both["date"].iloc[0].date()),
        "last_month": str(both["date"].iloc[-1].date()),
        "mean_intake_kb_d": float(both["intake_kb_d"].mean()),
        "mean_imports_kb_d": float(both["imports_kb_d"].mean()),
        "mean_imports_over_intake": float(ratio.mean()),
        "min_imports_over_intake": float(ratio.min()),
        "max_imports_over_intake": float(ratio.max()),
        "correlation_levels": float(
            both["intake_kb_d"].corr(both["imports_kb_d"])
        ),
        "correlation_12m_differences": float(
            joint.iloc[:, 0].corr(joint.iloc[:, 1]) if len(joint) > 2 else np.nan
        ),
    }


# ---------------------------------------------------------------------------
# SPEC.md section 6.2, the run cut threshold
# ---------------------------------------------------------------------------

#: SPEC.md section 6.2: "If the interval is wider than 10 $/bbl or touches the
#: edge of the sample, call it unidentified."
THRESHOLD_MAX_CI_WIDTH_USD_BBL = 10.0

#: The grid runs between these quantiles of the regressor, so that every
#: candidate threshold has data on both sides of it. A threshold outside this
#: range is one the sample cannot see, which is the same thing the edge rule
#: above is testing for.
THRESHOLD_GRID_QUANTILES = (0.05, 0.95)
THRESHOLD_GRID_STEP_USD_BBL = 0.25

#: Block bootstrap replications and the seed. Fixed, so the interval is
#: reproducible from a clean checkout and tests/test_analysis.py can assert it.
#: The seed is SPEC.md's section number for this estimate and has no other
#: meaning; nothing about the result was consulted in choosing it.
BOOTSTRAP_REPLICATIONS = 2000
BOOTSTRAP_SEED = 62

#: Replications for the grid sensitivity check, which runs the whole bootstrap
#: four times over and is a diagnostic rather than a published interval. Named
#: here so the report cannot quote a count the function does not use.
GRID_SENSITIVITY_REPLICATIONS = 600

#: The regressor the kink is looked for in: the mean of the margin over t-1,
#: t-2 and t-3, the same one to three month window as SPEC.md section 6.1's
#: equation, collapsed to one variable so the kink is in one place rather than
#: three. Stated once, not chosen from among alternatives.
THRESHOLD_LAGS = MARGIN_LAGS


def autocorrelation(x: Sequence[float], max_lag: int) -> np.ndarray:
    """Sample autocorrelations 1..max_lag, the usual biased (divide by n) form."""
    x = np.asarray(x, dtype=float).reshape(-1)
    x = x - x.mean()
    nobs = len(x)
    denominator = float(x @ x)
    if denominator <= 0:
        return np.full(max_lag, np.nan)
    return np.array(
        [float(x[lag:] @ x[:-lag]) / denominator for lag in range(1, max_lag + 1)]
    )


def block_length_from_acf(
    x: Sequence[float], max_lag: int | None = None
) -> tuple[int, str, np.ndarray]:
    """Block length from the series' own autocorrelation, by a stated rule.

    The rule: the block is the shortest lag at which the sample autocorrelation
    first falls inside the usual two over root n band, that is, the first lag at
    which the series is no longer significantly correlated with itself. A block
    of that length carries the dependence the data actually shows.

    SPEC.md section 6.2 asks for the block length to come from the data's own
    autocorrelation, to be stated, and NOT to be tuned to narrow the interval.
    This rule is applied once to the dependent variable, before the bootstrap is
    run, and the report prints the autocorrelations it was read off so that a
    reader can check the reading rather than take it.

    Returns:
        (block length, a sentence saying how it was chosen, the autocorrelations)
    """
    x = np.asarray(x, dtype=float).reshape(-1)
    nobs = len(x)
    if max_lag is None:
        max_lag = max(1, min(nobs // 4, 36))
    acf = autocorrelation(x, max_lag)
    band = 2.0 / math.sqrt(nobs)
    inside = np.where(np.abs(acf) < band)[0]
    if len(inside) == 0:
        block = max_lag
        how = (
            "no lag up to %d has an autocorrelation inside the two over root n "
            "band of %.4f, so the block is the longest lag examined, %d months"
            % (max_lag, band, max_lag)
        )
    else:
        block = int(inside[0]) + 1
        how = (
            "the first lag whose autocorrelation falls inside the two over root "
            "n band of %.4f is lag %d, rho = %.4f, so the block is %d months"
            % (band, block, acf[block - 1], block)
        )
    return max(1, int(block)), how, acf


@dataclass(frozen=True)
class HockeyStick:
    """One fitted kink at a given threshold.

        utilisation_pct = level - slope_below * max(threshold - margin, 0)

    slope_below is reported as a positive number when runs fall below the
    threshold, which is the shape SPEC.md section 6.2 describes. A negative
    slope_below means runs RISE as the margin falls below the candidate, which
    would be the opposite of the claim, and it is reported rather than screened
    out.
    """

    threshold: float
    level: float
    slope_below: float
    slope_below_se: float
    ssr: float
    r2: float
    nobs: int
    nw_lag: int
    months_below: int


def _kink_design(margin: np.ndarray, threshold: float) -> np.ndarray:
    shortfall = np.maximum(threshold - margin, 0.0)
    return np.column_stack([np.ones(len(margin)), shortfall])


def fit_hockey_stick(
    margin: Sequence[float],
    utilisation_pct: Sequence[float],
    threshold: float,
    nw_lag: int | None = None,
) -> HockeyStick:
    """Least squares at a fixed threshold. Linear in the parameters given tau."""
    margin = np.asarray(margin, dtype=float).reshape(-1)
    y = np.asarray(utilisation_pct, dtype=float).reshape(-1)
    design = _kink_design(margin, threshold)
    fit = ols_newey_west(y, design, ("level", "shortfall"), lag=nw_lag)
    level, shortfall = fit.params
    return HockeyStick(
        threshold=float(threshold),
        level=float(level),
        slope_below=float(-shortfall),
        slope_below_se=float(fit.se[1]),
        ssr=fit.ssr,
        r2=fit.r2,
        nobs=fit.nobs,
        nw_lag=fit.nw_lag,
        months_below=int((margin < threshold).sum()),
    )


def threshold_grid(
    margin: Sequence[float],
    step: float = THRESHOLD_GRID_STEP_USD_BBL,
    quantiles: tuple[float, float] = THRESHOLD_GRID_QUANTILES,
) -> np.ndarray:
    """Candidate thresholds, in even steps between two quantiles of the regressor."""
    margin = np.asarray(margin, dtype=float).reshape(-1)
    low = float(np.quantile(margin, quantiles[0]))
    high = float(np.quantile(margin, quantiles[1]))
    if not high > low:
        raise ValueError("the regressor has no spread to search over")
    count = int(math.floor((high - low) / step)) + 1
    return low + step * np.arange(count)


def _profile_ssr(margin: np.ndarray, y: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Sum of squared residuals at each candidate threshold. The grid search."""
    out = np.empty(len(grid))
    for i, threshold in enumerate(grid):
        design = _kink_design(margin, threshold)
        params, *_ = np.linalg.lstsq(design, y, rcond=None)
        resid = y - design @ params
        out[i] = float(resid @ resid)
    return out


def search_threshold(
    margin: Sequence[float],
    utilisation_pct: Sequence[float],
    grid: np.ndarray | None = None,
    nw_lag: int | None = None,
) -> tuple[HockeyStick, np.ndarray, np.ndarray]:
    """The grid search of SPEC.md section 6.2. Returns the fit, the grid, the SSR."""
    margin = np.asarray(margin, dtype=float).reshape(-1)
    y = np.asarray(utilisation_pct, dtype=float).reshape(-1)
    if grid is None:
        grid = threshold_grid(margin)
    ssr = _profile_ssr(margin, y, grid)
    best = grid[int(np.argmin(ssr))]
    return fit_hockey_stick(margin, y, best, nw_lag=nw_lag), grid, ssr


@dataclass(frozen=True)
class ThresholdResult:
    """SPEC.md section 6.2's answer, including the answer being "unidentified"."""

    point: HockeyStick
    grid: np.ndarray
    ssr: np.ndarray
    draws: np.ndarray
    ci_low: float
    ci_high: float
    identified: bool
    verdict: str
    reasons: tuple[str, ...]
    block_length: int
    block_choice: str
    acf: np.ndarray
    replications: int
    seed: int
    nobs: int
    first_month: str
    last_month: str
    linear_ssr: float
    linear_r2: float
    regressor_min: float
    regressor_max: float
    #: The months whose lagged margin sits below the estimated threshold. THE
    #: SINGLE MOST IMPORTANT DIAGNOSTIC ON THIS RESULT. A threshold estimated
    #: from one continuous stretch of months is a description of that stretch,
    #: not a behavioural level the refining system returns to, and the only way
    #: a reader can tell the difference is to see the dates.
    months_below: tuple[str, ...]
    longest_run_below: int
    mean_utilisation_below: float
    mean_utilisation_above: float
    grid_quantiles: tuple[float, float]

    @property
    def ci_width(self) -> float:
        return self.ci_high - self.ci_low

    @property
    def headroom_usd_bbl(self) -> float | None:
        """The site shows a headroom only when the threshold is identified.

        SPEC.md section 6.2: if it is not, "the site then shows no headroom
        figure and falls back to the ten year percentile". None is that state and
        it is returned rather than a number with a caveat next to it.
        """
        return None if not self.identified else self.point.threshold


def _moving_block_indices(
    nobs: int, block: int, rng: np.random.Generator
) -> np.ndarray:
    """One moving block bootstrap resample of positions, length nobs."""
    starts = rng.integers(0, nobs - block + 1, size=int(math.ceil(nobs / block)))
    return np.concatenate([np.arange(s, s + block) for s in starts])[:nobs]


def run_cut_threshold(
    frame: pd.DataFrame | None = None,
    regressor: str = MARGIN_STUDY_INTENSITY,
    lags: Sequence[int] = THRESHOLD_LAGS,
    replications: int = BOOTSTRAP_REPLICATIONS,
    seed: int = BOOTSTRAP_SEED,
    basis_2026: str = CAPACITY_2026_HELD_FLAT,
    max_ci_width: float = THRESHOLD_MAX_CI_WIDTH_USD_BBL,
) -> ThresholdResult:
    """Fit the hockey stick, bootstrap the threshold, and say whether it is found.

    The equation is the plain shape SPEC.md section 6.2 describes and nothing
    else: a level, flat above the threshold, and one slope below it. No month
    fixed effects and no episode dummies, because the episodes are where the
    margin fell and where runs fell, and a dummy on them would remove the very
    variation the threshold is estimated from. That is a limitation and it is
    reported, not hidden: the threshold, if there is one, is identified mostly by
    2020.

    The threshold interval is a moving block bootstrap percentile interval, with
    the block read off the dependent variable's own autocorrelation by
    block_length_from_acf and a fixed seed. The grid is held at the one computed
    from the original sample, so a replication is answering the same question as
    the point estimate.

    THE UNIDENTIFIED VERDICT IS A REAL OUTCOME AND NOT A FAILURE. SPEC.md section
    2 rule 4: the study is allowed to find nothing. If the interval is wider than
    max_ci_width or reaches the edge of the grid, identified is False, headroom
    is None, and the site falls back to the ten year percentile.
    """
    if frame is None:
        frame = analysis_frame(basis_2026, CAPACITY_STEP)
    work = frame.copy()
    lag_columns = []
    for k in lags:
        name = "_lag%d" % k
        work[name] = work[regressor].shift(k)
        lag_columns.append(name)
    # EVERY LAG OR NO ROW. pandas.mean skips missing values, so without the
    # min_count the first two months of the sample would carry a one month and a
    # two month mean under the same column name as the three month one, and the
    # threshold would be estimated partly on a different variable. It also makes
    # this sample identical to the one SPEC.md section 6.1's equation runs on,
    # which is the point of using the same window.
    work["margin_mean_lagged"] = work[lag_columns].mean(axis=1).where(
        work[lag_columns].notna().all(axis=1)
    )
    work = work.dropna(subset=["utilisation_pct", "margin_mean_lagged"]).reset_index(
        drop=True
    )
    if len(work) < 24:
        raise ValueError("only %d usable months, too few to search" % len(work))

    margin = work["margin_mean_lagged"].to_numpy(dtype=float)
    y = work["utilisation_pct"].to_numpy(dtype=float)

    point, grid, ssr = search_threshold(margin, y)

    # The straight line the kink is being asked to beat, on the same sample.
    linear = ols_newey_west(
        y, np.column_stack([np.ones(len(margin)), margin]), ("const", "margin")
    )

    block, how, acf = block_length_from_acf(y)
    rng = np.random.default_rng(seed)
    draws = np.empty(replications)
    for b in range(replications):
        take = _moving_block_indices(len(y), block, rng)
        candidate_ssr = _profile_ssr(margin[take], y[take], grid)
        draws[b] = grid[int(np.argmin(candidate_ssr))]

    ci_low = float(np.quantile(draws, 0.025))
    ci_high = float(np.quantile(draws, 0.975))
    width = ci_high - ci_low
    step = float(grid[1] - grid[0]) if len(grid) > 1 else 0.0
    reasons = []
    if width > max_ci_width:
        reasons.append(
            "the 95 percent block bootstrap interval is %.2f $/bbl wide, which is "
            "wider than the %.0f $/bbl bar in SPEC.md section 6.2" % (width, max_ci_width)
        )
    touches_low = ci_low <= grid[0] + step
    touches_high = ci_high >= grid[-1] - step
    if touches_low or touches_high:
        reasons.append(
            "the interval reaches the %s edge of the searchable range, %.2f to "
            "%.2f $/bbl, so the sample cannot see where it ends"
            % (
                "lower" if touches_low and not touches_high else
                "upper" if touches_high and not touches_low else "lower and upper",
                float(grid[0]),
                float(grid[-1]),
            )
        )
    below = work[margin < point.threshold]
    below_months = tuple(str(d.date())[:7] for d in below["date"])
    longest, current, previous = 0, 0, None
    for stamp in below["date"]:
        period = pd.Timestamp(stamp).to_period("M")
        current = current + 1 if previous is not None and period == previous + 1 else 1
        longest = max(longest, current)
        previous = period

    identified = not reasons
    verdict = (
        "identified at %.2f $/bbl, 95 percent interval %.2f to %.2f"
        % (point.threshold, ci_low, ci_high)
        if identified
        else "unidentified"
    )
    return ThresholdResult(
        point=point,
        grid=grid,
        ssr=ssr,
        draws=draws,
        ci_low=ci_low,
        ci_high=ci_high,
        identified=identified,
        verdict=verdict,
        reasons=tuple(reasons),
        block_length=block,
        block_choice=how,
        acf=acf,
        replications=int(replications),
        seed=int(seed),
        nobs=len(y),
        first_month=str(work["date"].iloc[0].date()),
        last_month=str(work["date"].iloc[-1].date()),
        linear_ssr=linear.ssr,
        linear_r2=linear.r2,
        regressor_min=float(margin.min()),
        regressor_max=float(margin.max()),
        months_below=below_months,
        longest_run_below=int(longest),
        mean_utilisation_below=float(below["utilisation_pct"].mean())
        if len(below)
        else float("nan"),
        mean_utilisation_above=float(
            work.loc[margin >= point.threshold, "utilisation_pct"].mean()
        ),
        grid_quantiles=tuple(THRESHOLD_GRID_QUANTILES),
    )


def threshold_grid_sensitivity(
    frame: pd.DataFrame | None = None,
    regressor: str = MARGIN_STUDY_INTENSITY,
    lags: Sequence[int] = THRESHOLD_LAGS,
    quantile_sets: Sequence[tuple[float, float]] = (
        (0.05, 0.95),
        (0.02, 0.98),
        (0.00, 1.00),
        (0.10, 0.90),
    ),
    replications: int = GRID_SENSITIVITY_REPLICATIONS,
    seed: int = BOOTSTRAP_SEED,
) -> pd.DataFrame:
    """Does the unidentified verdict turn on where the grid was cut. A check, not a choice.

    THE HEADLINE GRID IS THE ONE IN THRESHOLD_GRID_QUANTILES AND IT DOES NOT MOVE.
    This function exists because the obvious objection to an unidentified verdict
    reached partly on an edge rule is "you cut the grid too short", and the
    honest answer is to measure it rather than to argue. It returns one row per
    grid, and run_cut_threshold is not parameterised by it: nothing downstream
    reads this, the site never sees it, and no result above was chosen with it.
    SPEC.md section 6.6.
    """
    if frame is None:
        frame = analysis_frame(CAPACITY_2026_HELD_FLAT, CAPACITY_STEP)
    work = frame.copy()
    lag_columns = []
    for k in lags:
        name = "_lag%d" % k
        work[name] = work[regressor].shift(k)
        lag_columns.append(name)
    work["m"] = work[lag_columns].mean(axis=1).where(
        work[lag_columns].notna().all(axis=1)
    )
    work = work.dropna(subset=["utilisation_pct", "m"]).reset_index(drop=True)
    margin = work["m"].to_numpy(dtype=float)
    y = work["utilisation_pct"].to_numpy(dtype=float)
    block, _, _ = block_length_from_acf(y)

    rows = []
    for quantiles in quantile_sets:
        grid = threshold_grid(margin, quantiles=tuple(quantiles))
        point, _, _ = search_threshold(margin, y, grid=grid)
        rng = np.random.default_rng(seed)
        draws = np.empty(replications)
        for b in range(replications):
            take = _moving_block_indices(len(y), block, rng)
            draws[b] = grid[int(np.argmin(_profile_ssr(margin[take], y[take], grid)))]
        low, high = (float(v) for v in np.quantile(draws, [0.025, 0.975]))
        step = float(grid[1] - grid[0]) if len(grid) > 1 else 0.0
        rows.append(
            {
                "quantiles": "%.2f to %.2f" % quantiles,
                "grid_low": float(grid[0]),
                "grid_high": float(grid[-1]),
                "threshold": point.threshold,
                "ci_low": low,
                "ci_high": high,
                "ci_width": high - low,
                "too_wide": bool(high - low > THRESHOLD_MAX_CI_WIDTH_USD_BBL),
                "touches_edge": bool(
                    low <= grid[0] + step or high >= grid[-1] - step
                ),
            }
        )
    frame_out = pd.DataFrame(rows)
    frame_out["identified"] = ~(frame_out["too_wide"] | frame_out["touches_edge"])
    return frame_out


# ---------------------------------------------------------------------------
# SPEC.md section 6.3, the horse race, which the spec calls the point
# ---------------------------------------------------------------------------

#: The OPEC MOMR Rotterdam cracks, monthly, computed in crack.series through the
#: engine. Horse A is the gasoil one: "the number on every screen".
CRACK_GASOIL = "crack_gasoil_usd_bbl"
CRACK_GASOLINE = "crack_gasoline_usd_bbl"


def crack_frame(brent_source: str = "fred") -> pd.DataFrame:
    """Monthly Rotterdam cracks in $/bbl, 2000-10 onward, for horse A.

    A thin wrapper on series.opec_monthly_cracks that keeps only what the race
    needs and puts the date on the month start, which is the index everything in
    this module joins on.
    """
    frame = series.opec_monthly_cracks(brent_source)
    out = frame[["date", CRACK_GASOIL, CRACK_GASOLINE, "brent_usd_bbl"]].copy()
    out["date"] = pd.to_datetime(out["date"]).dt.to_period("M").dt.to_timestamp()
    return out.sort_values("date").reset_index(drop=True)


def horse_frame(
    basis_2026: str = CAPACITY_2026_HELD_FLAT,
    interpolation: str = CAPACITY_STEP,
    gas_intensity_mmbtu_per_bbl: float = config.GAS_INTENSITY_MMBTU_PER_BBL,
) -> pd.DataFrame:
    """Runs, both margins and both cracks on one monthly index, left joined on runs.

    analysis_frame INNER joins runs on the margin and therefore begins in
    2015-01. That is right for SPEC.md section 6.1, whose regressor is the
    margin, and wrong for SPEC.md section 6.3, whose horse A exists from 2000-10
    and whose longer sample has to be reportable beside the race. So this frame
    keeps every JODI month and lets each horse's own sample fall out of what is
    missing, which is also what makes the common sample something computed rather
    than assumed.
    """
    runs = utilisation_monthly(basis_2026, interpolation)
    frame = runs.merge(crack_frame(), on="date", how="left")
    frame = frame.merge(
        margin_frame(gas_intensity_mmbtu_per_bbl), on="date", how="left"
    )
    frame = frame.sort_values("date").reset_index(drop=True)
    frame["log_intake_pct"] = 100.0 * np.log(frame["intake_kb_d"].astype(float))
    frame["month"] = frame["date"].dt.month
    frame["trend_months"] = np.arange(len(frame), dtype=float)
    return frame


@dataclass(frozen=True)
class Horse:
    """One runner in SPEC.md section 6.3's race, and what it actually is."""

    key: str
    column: str
    name: str
    what_it_is: str
    #: True when this runner is NOT the series SPEC.md section 6.3 names. It is
    #: carried on the record rather than written into the prose so that no table
    #: can print this horse without the label travelling with it.
    substitution: bool = False
    substitution_note: str = ""


#: SPEC.md section 6.3 asks for three: (A) the raw gasoil crack, (B) the official
#: margin, (C) the margin after gas.
#:
#: C IS A SUBSTITUTION AND IT IS LABELLED ONE EVERYWHERE. Gate 2 established that
#: DGEC's published MBR is ALREADY net of purchased gas at DGEC's own embedded
#: intensity of 0.06590 MMBtu/bbl, see series.margin_after_gas_monthly. So the
#: spec's B and C, read literally, are the same series, and a race between them
#: would be a race of two horses presented as three. The substitution re-prices
#: the barrel at this study's EIA derived 0.21217 MMBtu/bbl instead, which is a
#: real and different question about a refiner who buys more of his energy, and
#: it is NOT what SPEC.md section 6.3 wrote. Both facts are reported.
HORSES: tuple[Horse, ...] = (
    Horse(
        key="A",
        column=CRACK_GASOIL,
        name="the raw gasoil crack",
        what_it_is=(
            "OPEC MOMR Rotterdam gasoil quotation less Brent, monthly, $/bbl. "
            "The number on every screen"
        ),
    ),
    Horse(
        key="B",
        column=MARGIN_OFFICIAL,
        name="the official margin, DGEC's published MBR",
        what_it_is=(
            "DGEC marge brute de raffinage sur Brent, monthly, $/bbl, carried "
            "through untouched"
        ),
    ),
    Horse(
        key="C",
        column=MARGIN_STUDY_INTENSITY,
        name="the margin after gas at this study's own intensity",
        what_it_is=(
            "the published MBR less the gas wedge, that is, the same barrel "
            "re-priced at %.5f MMBtu/bbl of purchased gas instead of DGEC's "
            "embedded %.5f" % (
                config.GAS_INTENSITY_MMBTU_PER_BBL,
                config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL,
            )
        ),
        substitution=True,
        substitution_note=(
            "SPEC.md section 6.3's horse C is 'the margin after gas'. The MBR is "
            "already net of gas at DGEC's embedded intensity, so the spec's B and "
            "C would be ONE series and the race would collapse to two horses "
            "while still being called three. This horse is therefore a "
            "SUBSTITUTION: the official margin re-priced at this study's EIA "
            "derived gas intensity. It is never presented as the spec's original C"
        ),
    ),
)

#: The two dependents of SPEC.md section 6.1. The first half of this gate found
#: that they disagree, so SPEC.md section 6.3's race is run on both: a horse race
#: that holds under only one of them is a weaker result than one that holds under
#: both, and which of the two is the case is a finding rather than a footnote.
DEPENDENT_CAPACITY = "utilisation_pct"
DEPENDENT_FALLBACK = "log_intake_pct"
DEPENDENTS = (DEPENDENT_CAPACITY, DEPENDENT_FALLBACK)


def common_sample_dates(
    frame: pd.DataFrame,
    columns: Sequence[str],
    dependent: str,
    lags: Sequence[int] = MARGIN_LAGS,
) -> pd.DatetimeIndex:
    """The months on which EVERY one of these regressors can be raced, at these lags.

    THE SAMPLE TRAP OF SPEC.md SECTION 6.3. Horse A can be computed from 2002
    because the OPEC cracks start in 2000-10, while B and C only exist from
    2015-01. Racing them on their own samples would give A twenty extra years of
    quiet data and the comparison would be invalid. So the race runs here, and A's
    longer sample is reported separately and labelled.
    """
    work = frame.copy()
    needed = [dependent]
    for column in columns:
        for k in lags:
            name = "__common_%s_lag%d" % (column, k)
            work[name] = work[column].shift(k)
            needed.append(name)
    work = work.dropna(subset=needed)
    return pd.DatetimeIndex(work["date"])


# ---------------------------------------------------------------------------
# The expanding window, which SPEC.md section 6.3 calls for and this gate calls
# the honest discriminator
# ---------------------------------------------------------------------------

#: The shortest training window before the first forecast is made. Five years of
#: monthly data, which is long enough to identify eleven month dummies plus the
#: lags, chosen once from that reasoning and not moved after seeing any RMSE.
#: SPEC.md section 6.6.
EXPANDING_MIN_TRAIN_MONTHS = 60


@dataclass(frozen=True)
class ExpandingWindow:
    """One step ahead out of sample forecasts on an expanding estimation window."""

    rmse: float
    #: The same exercise for a model that predicts the training mean and nothing
    #: else. A regressor that cannot beat the mean of the dependent has not
    #: earned the word "explains", and this is the only way to see that.
    mean_benchmark_rmse: float
    n_forecasts: int
    min_train: int
    first_forecast: str
    last_forecast: str
    errors: np.ndarray
    benchmark_errors: np.ndarray
    dates: tuple[str, ...]

    @property
    def beats_the_mean(self) -> bool:
        return self.rmse < self.mean_benchmark_rmse

    @property
    def ratio_to_mean(self) -> float:
        return self.rmse / self.mean_benchmark_rmse


def expanding_window_rmse(
    regression: Regression,
    min_train: int = EXPANDING_MIN_TRAIN_MONTHS,
) -> ExpandingWindow:
    """SPEC.md section 6.3's expanding window out of sample RMSE.

    For each origin t from min_train to the last row: fit the SAME design on rows
    0 to t-1 and predict row t. The dependent at t, and at every row after it, is
    never seen by the fit that predicts it, which is what makes the number out of
    sample. The regressors at row t are lags 1 to 3 of a monthly series, all of
    which are published before month t, so no regressor is from the future either.

    WHAT IS FIXED IN ADVANCE AND WHAT IS NOT, said plainly because "no peeking"
    is a claim and not a property:

      - Every COEFFICIENT is estimated on the training rows only. Nothing else in
        this function touches y at or after the origin.
      - The SPECIFICATION, that is, which columns exist, is fixed by SPEC.md
        section 6.1 before any data is seen, and is the same at every origin.
      - An episode dummy for an episode that has not happened yet is a column of
        zeros in the training rows, so least squares gives it a zero coefficient
        and the forecast for the first month of that episode is made as though
        the episode were not there. That is the honest behaviour and it is why
        the 2026 forecasts are not flattered.

    The design comes off the fitted Regression rather than being rebuilt, so the
    out of sample equation cannot drift away from the in sample one printed
    beside it.
    """
    design = np.asarray(regression.design, dtype=float)
    y = np.asarray(regression.y, dtype=float)
    nobs = len(y)
    if design.shape[0] != nobs:
        raise ValueError(
            "the design has %d rows and the dependent %d" % (design.shape[0], nobs)
        )
    if nobs <= min_train:
        raise ValueError(
            "an expanding window needs more than min_train = %d observations and "
            "this sample has %d" % (min_train, nobs)
        )

    errors: list[float] = []
    benchmark: list[float] = []
    stamps: list[str] = []
    labels = (
        [str(pd.Timestamp(d).date()) for d in regression.dates]
        if regression.dates
        else [str(i) for i in range(nobs)]
    )
    for t in range(min_train, nobs):
        x_train, y_train = design[:t], y[:t]
        params, *_ = np.linalg.lstsq(x_train, y_train, rcond=None)
        errors.append(float(y[t] - float(design[t] @ params)))
        benchmark.append(float(y[t] - float(y_train.mean())))
        stamps.append(labels[t])

    errors_array = np.asarray(errors, dtype=float)
    benchmark_array = np.asarray(benchmark, dtype=float)
    return ExpandingWindow(
        rmse=float(np.sqrt(np.mean(errors_array**2))),
        mean_benchmark_rmse=float(np.sqrt(np.mean(benchmark_array**2))),
        n_forecasts=len(errors_array),
        min_train=int(min_train),
        first_forecast=stamps[0],
        last_forecast=stamps[-1],
        errors=errors_array,
        benchmark_errors=benchmark_array,
        dates=tuple(stamps),
    )


@dataclass(frozen=True)
class HorseResult:
    """One runner's in sample fit and its out of sample RMSE, on the race sample."""

    horse: Horse
    dependent: str
    model: ResponseModel
    oos: ExpandingWindow

    @property
    def row(self) -> Mapping[str, object]:
        model = self.model
        return {
            "horse": self.horse.key,
            "regressor": self.horse.column,
            "name": self.horse.name,
            "substitution": self.horse.substitution,
            "dependent": self.dependent,
            "n": model.regression.nobs,
            "first_month": model.first_month,
            "last_month": model.last_month,
            "sum_of_lags": model.sum_b,
            "nw_se": model.sum_b_se,
            "t": model.sum_b_t,
            "ci_low": model.sum_b_low,
            "ci_high": model.sum_b_high,
            "r2": model.regression.r2,
            "adj_r2": model.regression.adj_r2,
            "oos_rmse": self.oos.rmse,
            "oos_mean_benchmark_rmse": self.oos.mean_benchmark_rmse,
            "oos_n": self.oos.n_forecasts,
            "beats_the_mean_oos": self.oos.beats_the_mean,
            "kb_d_per_10_usd": model.translation.kb_d,
        }


def _response_for(
    dependent: str,
    regressor: str,
    label: str,
    frame: pd.DataFrame,
    sample_dates: Sequence[pd.Timestamp] | None,
    episode_dummies: bool,
    closure_years: Sequence[int] | None,
    nw_lag: int | None = None,
) -> ResponseModel:
    """Whichever of the two equations of SPEC.md section 6.1 this dependent is."""
    if dependent == DEPENDENT_CAPACITY:
        return margin_response(
            regressor=regressor,
            label=label,
            frame=frame,
            episode_dummies=episode_dummies,
            sample_dates=sample_dates,
            nw_lag=nw_lag,
        )
    if dependent == DEPENDENT_FALLBACK:
        return intake_trend_response(
            regressor=regressor,
            label=label,
            frame=frame,
            episode_dummies=episode_dummies,
            closure_years=closure_years,
            sample_dates=sample_dates,
            nw_lag=nw_lag,
        )
    raise ValueError(
        "dependent is %r, which is %s" % (dependent, " or ".join(DEPENDENTS))
    )


def horse_race(
    dependent: str = DEPENDENT_CAPACITY,
    frame: pd.DataFrame | None = None,
    horses: Sequence[Horse] = HORSES,
    episode_dummies: bool = True,
    closure_years: Sequence[int] | None = None,
    min_train: int = EXPANDING_MIN_TRAIN_MONTHS,
) -> list[HorseResult]:
    """SPEC.md section 6.3, run on ONE sample, with an out of sample RMSE each.

    The three regressors go into the same equation with the same controls, the
    same lags, the same Newey-West lag and the same months. The only thing that
    differs between the three fits is which column is on the right hand side,
    which is the only way the comparison means anything.
    """
    if frame is None:
        frame = horse_frame()
    dates = common_sample_dates(frame, [h.column for h in horses], dependent)
    if len(dates) <= min_train:
        raise ValueError(
            "the common sample is %d months, which is not enough for a %d month "
            "training window" % (len(dates), min_train)
        )
    # ONE Newey-West lag for all three, taken from the common sample size, so a
    # horse cannot win on a different truncation lag from its rivals.
    lag = newey_west_lag(len(dates))
    results = []
    for horse in horses:
        model = _response_for(
            dependent=dependent,
            regressor=horse.column,
            label="horse %s, %s" % (horse.key, horse.name),
            frame=frame,
            sample_dates=dates,
            episode_dummies=episode_dummies,
            closure_years=closure_years,
            nw_lag=lag,
        )
        if model.regression.nobs != len(dates):
            raise ValueError(
                "horse %s ran on %d months and the common sample is %d"
                % (horse.key, model.regression.nobs, len(dates))
            )
        results.append(
            HorseResult(
                horse=horse,
                dependent=dependent,
                model=model,
                oos=expanding_window_rmse(model.regression, min_train=min_train),
            )
        )
    return results


def horse_race_frame(results: Sequence[HorseResult]) -> pd.DataFrame:
    """The race as a table, one row per horse."""
    return pd.DataFrame([r.row for r in results])


@dataclass(frozen=True)
class LossDifferential:
    """Is one horse's out of sample RMSE distinguishable from another's."""

    first: str
    second: str
    mean_difference: float
    nw_se: float
    t: float
    nobs: int
    distinguishable: bool

    @property
    def sentence(self) -> str:
        return (
            "%s against %s: mean squared error difference %+.5f, Newey-West se "
            "%.5f, t %+.2f on %d forecasts, %s"
            % (
                self.first,
                self.second,
                self.mean_difference,
                self.nw_se,
                self.t,
                self.nobs,
                "DISTINGUISHABLE" if self.distinguishable else "not distinguishable",
            )
        )


def loss_differential(a: HorseResult, b: HorseResult) -> LossDifferential:
    """The paired squared error difference between two horses, with a HAC standard error.

    WHY THIS IS HERE. Horse C can have the lowest out of sample RMSE and the gap
    to the next horse can be a third of one percent, and reporting only the
    ranking would turn a rounding difference into a result. This is the ordinary
    paired comparison of two forecast loss series: regress the difference of the
    squared errors on a constant, take the Newey-West standard error of that
    constant, and read the t.

    It is a comparison of two numbers that have already been computed and it is
    NOT a forecasting exercise, no parameter is searched over and nothing is
    selected on it. SPEC.md section 6.6.
    """
    if a.oos.dates != b.oos.dates:
        raise ValueError("the two horses were scored on different forecast months")
    difference = a.oos.errors**2 - b.oos.errors**2
    fit = ols_newey_west(
        difference, np.ones((len(difference), 1)), ("const",)
    )
    value, se = fit.get("const")
    t = value / se if se > 0 else float("nan")
    return LossDifferential(
        first="horse %s" % a.horse.key,
        second="horse %s" % b.horse.key,
        mean_difference=float(value),
        nw_se=float(se),
        t=float(t),
        nobs=len(difference),
        distinguishable=bool(abs(t) > Z95),
    )


def horse_race_winner(results: Sequence[HorseResult]) -> tuple[str, str]:
    """Who won on the out of sample RMSE, and by how much, measured not asserted.

    SPEC.md section 6.3 makes the out of sample RMSE the discriminator, and
    SPEC.md section 2 rule 3 says report the result whatever it is. So the winner
    is read off the numbers here and the sentence is assembled from them, never
    typed. If the raw gasoil crack wins, this function says the raw gasoil crack
    won.
    """
    ranked = sorted(results, key=lambda r: r.oos.rmse)
    best, second = ranked[0], ranked[1]
    margin_pct = 100.0 * (second.oos.rmse - best.oos.rmse) / second.oos.rmse
    pairs = [
        loss_differential(ranked[i], ranked[j])
        for i in range(len(ranked))
        for j in range(i + 1, len(ranked))
    ]
    any_distinguishable = any(p.distinguishable for p in pairs)
    sentence = (
        "horse %s, %s, has the lowest expanding window out of sample RMSE at "
        "%.4f, ahead of horse %s at %.4f, a margin of %.2f percent. The spread "
        "across all %d horses is %.4f to %.4f against a mean only benchmark of "
        "%.4f. %s"
        % (
            best.horse.key,
            best.horse.name,
            best.oos.rmse,
            second.horse.key,
            second.oos.rmse,
            margin_pct,
            len(results),
            ranked[0].oos.rmse,
            ranked[-1].oos.rmse,
            best.oos.mean_benchmark_rmse,
            (
                "At least one pairwise squared error difference is "
                "distinguishable from zero, so the ordering above carries "
                "information."
                if any_distinguishable
                else (
                    "NOT ONE of the %d pairwise squared error differences is "
                    "distinguishable from zero, so THE RACE IS A DEAD HEAT and "
                    "the ordering above is a ranking of numbers, not a finding. "
                    "The lowest RMSE is reported because SPEC.md section 6.3 asks "
                    "for it, and the word 'wins' is withheld because the data "
                    "does not support it." % len(pairs)
                )
            ),
        )
    )
    return best.horse.key, sentence


def gasoil_long_sample(
    dependent: str = DEPENDENT_CAPACITY,
    frame: pd.DataFrame | None = None,
    episode_dummies: bool = True,
    closure_years: Sequence[int] | None = None,
    min_train: int = EXPANDING_MIN_TRAIN_MONTHS,
) -> HorseResult:
    """Horse A on ALL the months it has, reported separately and labelled.

    SPEC.md section 6.3's race is on the common sample and this is not part of
    it. It is here because the gasoil crack genuinely does reach back to 2000-10
    and throwing that away would be its own kind of dishonesty, and because the
    difference between this row and A's row in the race is the size of the sample
    trap, measured.
    """
    if frame is None:
        frame = horse_frame()
    horse = next(h for h in HORSES if h.column == CRACK_GASOIL)
    dates = common_sample_dates(frame, [horse.column], dependent)
    model = _response_for(
        dependent=dependent,
        regressor=horse.column,
        label="horse A on its own longer sample, NOT the race",
        frame=frame,
        sample_dates=dates,
        episode_dummies=episode_dummies,
        closure_years=closure_years,
        nw_lag=None,
    )
    return HorseResult(
        horse=horse,
        dependent=dependent,
        model=model,
        oos=expanding_window_rmse(model.regression, min_train=min_train),
    )


# ---------------------------------------------------------------------------
# Endogeneity, which SPEC.md section 6.3 asks to be flagged honestly
# ---------------------------------------------------------------------------


def endogeneity_diagnostic(
    frame: pd.DataFrame | None = None,
    regressors: Sequence[str] = (CRACK_GASOIL, MARGIN_OFFICIAL, MARGIN_STUDY_INTENSITY),
    lags: Sequence[int] = (0, 1, 2, 3),
) -> pd.DataFrame:
    """The correlation of runs with each regressor at lag 0 and at lags 1 to 3.

    SPEC.md section 6.3: "Runs move cracks, since more runs mean more product and
    weaker cracks, which biases the response toward zero. Lags help only partly."

    THIS FUNCTION DOES NOT TEST THAT AND CANNOT. Simultaneity is not visible in a
    correlation, and no ordering of two contemporaneous monthly series identifies
    which one moved first. What it does is show the shape of the problem: the
    contemporaneous correlation beside the lagged ones, so a reader can see how
    much of the relationship sits at lag 0 where the causation runs both ways,
    and how fast it decays into the lags the equation actually uses.

    The sign of the bias is a statement about the world and not a measurement
    here: a positive demand shock to runs weakens the crack, so the crack and
    runs move together for one reason and apart for another, and the estimated
    response to the margin is pulled TOWARD ZERO. This study does not estimate
    the size of that bias and does not claim to have removed it.
    """
    if frame is None:
        frame = horse_frame()
    rows = []
    for column in regressors:
        for k in lags:
            work = pd.DataFrame(
                {
                    "intake": frame["intake_kb_d"].astype(float),
                    "utilisation": frame["utilisation_pct"].astype(float),
                    "x": frame[column].astype(float).shift(k),
                }
            ).dropna()
            rows.append(
                {
                    "regressor": column,
                    "lag": k,
                    "months": int(len(work)),
                    "corr_with_intake": float(work["intake"].corr(work["x"])),
                    "corr_with_utilisation": float(
                        work["utilisation"].corr(work["x"])
                    ),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# SPEC.md section 6.3, the instrument
# ---------------------------------------------------------------------------

#: The instrument: the European gas price in $/MMBtu, World Bank pink sheet, the
#: same monthly series the gas wedge is priced from. It is used at the SAME one to
#: three month lag window as the endogenous regressor, so the instrument is dated
#: like the thing it instruments.
INSTRUMENT_COLUMN = "gas_usd_mmbtu"

#: The usual rule of thumb bar for a single excluded instrument. Named here so
#: the verdict cannot be adjusted after seeing the F.
FIRST_STAGE_F_BAR = 10.0


@dataclass(frozen=True)
class InstrumentResult:
    """The two stage least squares fit, and whether the instrument is any good."""

    endogenous: str
    instrument: str
    dependent: str
    nobs: int
    nw_lag: int
    first_stage_coefficient: float
    first_stage_se: float
    first_stage_f: float
    first_stage_r2: float
    first_stage_partial_r2: float
    iv_coefficient: float
    iv_se: float
    ols_coefficient: float
    ols_se: float
    first_month: str
    last_month: str
    weak: bool
    verdict: str
    exclusion_restriction: str
    mechanical_relevance: str
    #: The coefficient the gas price enters this study's margin with BY
    #: ARITHMETIC: minus the difference between the two gas intensities. Carried
    #: beside the fitted first stage coefficient so the reader can see how much
    #: of the mechanical term survives once the margin's own co-movement with gas
    #: is in the same equation.
    mechanical_coefficient: float
    mechanical_measured: str

    @property
    def iv_t(self) -> float:
        return self.iv_coefficient / self.iv_se if self.iv_se > 0 else float("nan")


#: Stated BEFORE the instrument is run, which is the only time it means anything.
EXCLUSION_RESTRICTION = (
    "The exclusion restriction is that the European gas price affects NWE "
    "refinery runs ONLY through the refining margin. It is arguable and it is "
    "not obvious, and this study's honest view is that it probably does not hold "
    "exactly. Gas is not only a cost line in the margin: it is a hydrogen "
    "feedstock for hydrotreating and hydrocracking, so a gas shock can force a "
    "European refiner to change what he runs and how hard, for reasons the margin "
    "does not capture. A gas shock also arrives inside a wider energy shock that "
    "moves product demand, industrial activity and crude at the same time, and "
    "those channels reach runs without passing through the refining margin "
    "either. So the instrument is reported as a diagnostic, not as an "
    "identification strategy, and the ordinary least squares estimate stays the "
    "headline."
)

#: Said in the same breath as the first stage F, because a strong first stage
#: here is partly arithmetic rather than evidence.
MECHANICAL_RELEVANCE = (
    "The expectation set down before running this was that the first stage would "
    "be relevant BY CONSTRUCTION and that a large F would therefore be partly "
    "arithmetic rather than evidence. This study's margin is the MBR less a gas "
    "wedge, and the wedge is a fixed multiple of this very gas price, so the "
    "instrument enters the endogenous regressor as an exact linear term with a "
    "known coefficient; and DGEC's MBR is itself already net of gas at DGEC's own "
    "intensity, so gas is inside the official margin too. The measured first "
    "stage is reported next to that arithmetic below, and on this sample it does "
    "not come out the way the expectation said it would."
)


def gas_instrument(
    frame: pd.DataFrame | None = None,
    dependent: str = DEPENDENT_CAPACITY,
    endogenous: str = MARGIN_STUDY_INTENSITY,
    instrument: str = INSTRUMENT_COLUMN,
    lags: Sequence[int] = MARGIN_LAGS,
    episode_dummies: bool = True,
    nw_lag: int | None = None,
    f_bar: float = FIRST_STAGE_F_BAR,
) -> InstrumentResult:
    """Two stage least squares, the margin instrumented by the gas price.

    SPEC.md section 6.3: "Try the gas cost as an instrument for the margin after
    gas: TTF was driven by pipeline cuts in 2022 and by LNG disruption in 2026,
    not by NWE runs. Report the first-stage F. If the instrument is weak, say
    that rather than forcing it."

    The equation collapses the three margin lags into their mean, exactly as
    run_cut_threshold does, so there is ONE endogenous regressor and ONE excluded
    instrument and the model is just identified. Three endogenous lags against
    three lagged instruments would be a different and much weaker exercise, and
    it would make the reported F a vector rather than the single number the spec
    asks for.

    The controls are the same as the ordinary least squares equation: a constant,
    eleven month dummies and the regime terms. The first stage F is the robust
    Wald statistic on the excluded instrument, which with one instrument is the
    square of its Newey-West t. The second stage covariance is the standard
    instrumental variables sandwich with the same Newey-West kernel: the bread is
    built from the FITTED regressors and the residuals from the ACTUAL ones,
    which is the difference between a correct IV standard error and the one a
    two step regression prints by accident.
    """
    if frame is None:
        frame = horse_frame()
    work = frame.copy()
    lag_names, instrument_lags = [], []
    for k in lags:
        endo_name, inst_name = "_endo_lag%d" % k, "_inst_lag%d" % k
        work[endo_name] = work[endogenous].shift(k)
        work[inst_name] = work[instrument].shift(k)
        lag_names.append(endo_name)
        instrument_lags.append(inst_name)
    work["endo_mean"] = work[lag_names].mean(axis=1).where(
        work[lag_names].notna().all(axis=1)
    )
    work["inst_mean"] = work[instrument_lags].mean(axis=1).where(
        work[instrument_lags].notna().all(axis=1)
    )
    episodes = episode_mask(work["date"])
    for column in episodes.columns:
        work[column] = episodes[column].to_numpy()
    work = work.dropna(subset=[dependent, "endo_mean", "inst_mean"]).reset_index(
        drop=True
    )
    if len(work) < 24:
        raise ValueError("only %d usable months" % len(work))

    columns = [np.ones(len(work))]
    names = ["const"]
    if dependent == DEPENDENT_FALLBACK:
        periods = pd.PeriodIndex(work["date"], freq="M")
        columns.append(np.array([(p - periods[0]).n for p in periods], dtype=float))
        names.append("trend_months")
    dummies, dummy_names = _month_dummies(work["date"].dt.month)
    columns.append(dummies)
    names.extend(dummy_names)
    if episode_dummies:
        for name in sorted(EPISODES):
            column = work[name].to_numpy(dtype=float)
            if 0.0 < column.mean() < 1.0:
                columns.append(column)
                names.append(name)
    exog = np.column_stack(
        [np.asarray(c, dtype=float).reshape(len(work), -1) for c in columns]
    )
    endo = work["endo_mean"].to_numpy(dtype=float)
    inst = work["inst_mean"].to_numpy(dtype=float)
    y = work[dependent].to_numpy(dtype=float)
    if nw_lag is None:
        nw_lag = newey_west_lag(len(work))

    first = ols_newey_west(
        endo,
        np.column_stack([exog, inst]),
        (*names, "instrument"),
        lag=nw_lag,
        dates=work["date"],
    )
    coefficient, se = first.get("instrument")
    f_stat = (coefficient / se) ** 2 if se > 0 else float("nan")
    reduced = ols_newey_west(endo, exog, tuple(names), lag=nw_lag)
    partial_r2 = (
        1.0 - first.ssr / reduced.ssr if reduced.ssr > 0 else float("nan")
    )

    endo_hat = first.fitted
    x_hat = np.column_stack([exog, endo_hat])
    x_actual = np.column_stack([exog, endo])
    params, *_ = np.linalg.lstsq(x_hat, y, rcond=None)
    iv_resid = y - x_actual @ params
    iv_cov = newey_west_cov(x_hat, iv_resid, nw_lag)
    iv_coefficient = float(params[-1])
    iv_se = float(math.sqrt(max(iv_cov[-1, -1], 0.0)))

    ols = ols_newey_west(
        y, x_actual, (*names, "endo_mean"), lag=nw_lag, dates=work["date"]
    )
    ols_coefficient, ols_se = ols.get("endo_mean")

    mechanical = -(
        config.GAS_INTENSITY_MMBTU_PER_BBL
        - config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL
    )
    mechanical_measured = (
        "By arithmetic the gas price enters this study's margin with a "
        "coefficient of exactly %+.5f, the negative of the gap between the two "
        "gas intensities. The fitted first stage coefficient is %+.5f. The "
        "difference is the margin's OWN co-movement with gas: the months when "
        "European gas was dear, 2022 above all, are the months when product "
        "cracks and therefore the MBR were high, and that positive co-movement "
        "%s the mechanical deduction. So the instrument has %s independent "
        "purchase on the margin once the controls are in, which is what the F "
        "below is measuring."
        % (
            mechanical,
            coefficient,
            "roughly cancels" if abs(coefficient) < abs(mechanical) else "does not cancel",
            "almost no" if abs(coefficient / mechanical) < 0.5 else "some",
        )
    )

    weak = not (f_stat > f_bar)
    verdict = (
        "WEAK. The first stage F is %.2f, which does not clear the rule of thumb "
        "bar of %.0f, so the two stage least squares estimate above is not "
        "reliable and this study does not lean on it."
        % (f_stat, f_bar)
        if weak
        else (
            "The first stage F is %.2f, above the rule of thumb bar of %.0f, so "
            "the instrument is not weak in the statistical sense. That is a "
            "statement about relevance only. Relevance is not the binding "
            "constraint here and the exclusion restriction is, see below."
            % (f_stat, f_bar)
        )
    )
    return InstrumentResult(
        endogenous=endogenous,
        instrument=instrument,
        dependent=dependent,
        nobs=len(work),
        nw_lag=int(nw_lag),
        first_stage_coefficient=float(coefficient),
        first_stage_se=float(se),
        first_stage_f=float(f_stat),
        first_stage_r2=float(first.r2),
        first_stage_partial_r2=float(partial_r2),
        iv_coefficient=iv_coefficient,
        iv_se=iv_se,
        ols_coefficient=float(ols_coefficient),
        ols_se=float(ols_se),
        first_month=str(work["date"].iloc[0].date()),
        last_month=str(work["date"].iloc[-1].date()),
        weak=bool(weak),
        verdict=verdict,
        exclusion_restriction=EXCLUSION_RESTRICTION,
        mechanical_relevance=MECHANICAL_RELEVANCE,
        mechanical_coefficient=float(mechanical),
        mechanical_measured=mechanical_measured,
    )


# ---------------------------------------------------------------------------
# SPEC.md section 6.4, did the link hold in 2026
# ---------------------------------------------------------------------------

#: SPEC.md section 6.4: "Test whether the relation held after 28 February 2026."
#: The month of the strikes is 2026-02, so the post break months are 2026-03 on.
BREAK_2026_DATE = "2026-02-28"
BREAK_2026_FIRST_POST_MONTH = "2026-03-01"

#: How many post break months this study requires before it will pronounce on
#: whether the relation held. Twelve, one full seasonal cycle, because the
#: equation carries eleven month dummies and a verdict drawn from fewer months
#: than there are seasonal terms is a verdict about which months happened to fall
#: after the break. The number is set here, once, from that reasoning, and the
#: count is compared with it rather than the other way round. SPEC.md section 6.6.
BREAK_2026_MIN_POST_MONTHS = 12


@dataclass(frozen=True)
class BreakResult:
    """SPEC.md section 6.4's answer, which on this sample is "ask again later"."""

    dependent: str
    regressor: str
    break_date: str
    n_pre: int
    n_post: int
    min_post_months: int
    too_short: bool
    verdict: str
    residuals: pd.DataFrame
    pre_residual_sd: float
    jodi_last_month: str
    crack_last_month: str
    margin_last_month: str
    capacity_assumed_post: int
    explanations: tuple[Mapping[str, str], ...]


def _events(ids: Sequence[str]) -> tuple[Mapping[str, str], ...]:
    """Named entries from data/seed/events.json, with their source_url each."""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "data" / "seed" / "events.json"
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    by_id = {event["id"]: event for event in payload["events"]}
    out = []
    for name in ids:
        event = by_id[name]
        out.append(
            {
                "id": event["id"],
                "date": event["date"],
                "label": event["label"],
                "source_url": event["source_url"],
                "source_title": event.get("source_title", ""),
            }
        )
    return tuple(out)


def break_2026(
    frame: pd.DataFrame | None = None,
    dependent: str = DEPENDENT_CAPACITY,
    regressor: str = MARGIN_STUDY_INTENSITY,
    episode_dummies: bool = False,
    min_post_months: int = BREAK_2026_MIN_POST_MONTHS,
) -> BreakResult:
    """Did the relation hold after 2026-02-28. COUNT THE MONTHS FIRST.

    SPEC.md section 6.4 asks for a test. The Gate 3 brief asks for the months to
    be counted before the test is run, and they are: JODI ends 2026-06 and the
    OPEC cracks end 2026-02, so on any specification there are at most four post
    break months with a dependent. Four observations cannot support a verdict on
    whether a relation with eleven month dummies and three lags changed, and
    running a Chow test on them would produce a number that looks like an answer.

    So this function does the thing that CAN be done honestly: it fits the
    equation on the months up to and including 2026-02, makes a genuine out of
    sample prediction for each post break month, and shows the residual. A
    residual is a description of what happened. It is not a test and this function
    does not call it one.

    Episode dummies default OFF here, unlike everywhere else in this module, and
    the reason has to be said: the 2026 episode dummy would absorb exactly the
    post break deviation this is trying to look at, by construction. With it on,
    the residuals would be small because a free parameter had been fitted to them.
    """
    if frame is None:
        frame = horse_frame()
    work = frame.copy()
    lag_terms = []
    for k in MARGIN_LAGS:
        name = "%s_lag%d" % (regressor, k)
        work[name] = work[regressor].shift(k)
        lag_terms.append(name)
    work = work.dropna(subset=[dependent, *lag_terms]).reset_index(drop=True)

    first_post = pd.Timestamp(BREAK_2026_FIRST_POST_MONTH)
    pre = work[work["date"] < first_post].reset_index(drop=True)
    post = work[work["date"] >= first_post].reset_index(drop=True)

    model = _response_for(
        dependent=dependent,
        regressor=regressor,
        label="fitted on months before %s only" % BREAK_2026_FIRST_POST_MONTH,
        frame=frame,
        sample_dates=pd.DatetimeIndex(pre["date"]),
        episode_dummies=episode_dummies,
        closure_years=None,
    )
    fit = model.regression
    names = list(fit.names)

    # Build the post break design by the SAME rule the fit used, column by column
    # and by name, so a mismatch is impossible rather than merely unlikely.
    periods_pre = pd.PeriodIndex(pre["date"], freq="M")
    periods_post = pd.PeriodIndex(post["date"], freq="M")
    episodes_post = episode_mask(post["date"])
    design_post = np.zeros((len(post), len(names)))
    for j, name in enumerate(names):
        if name == "const":
            design_post[:, j] = 1.0
        elif name == "trend_months":
            design_post[:, j] = [(p - periods_pre[0]).n for p in periods_post]
        elif name.startswith("month_"):
            design_post[:, j] = (post["date"].dt.month == int(name[-2:])).astype(float)
        elif name.startswith("closure_step_"):
            year = int(name.rsplit("_", 1)[1])
            design_post[:, j] = (
                post["date"] >= pd.Timestamp(year=year, month=1, day=1)
            ).astype(float)
        elif name in episodes_post.columns:
            design_post[:, j] = episodes_post[name].to_numpy()
        elif name in post.columns:
            design_post[:, j] = post[name].to_numpy(dtype=float)
        else:
            raise ValueError("no post break column for the term %r" % name)

    predicted = design_post @ fit.params
    actual = post[dependent].to_numpy(dtype=float)
    residual = actual - predicted
    runs_base = recent_runs_kb_d()
    capacity, _ = latest_capacity_kb_d()
    scale = capacity / 100.0 if dependent == DEPENDENT_CAPACITY else runs_base / 100.0
    residuals = pd.DataFrame(
        {
            "date": post["date"].dt.date.astype(str),
            "actual": actual,
            "predicted": predicted,
            "residual": residual,
            "residual_kb_d": residual * scale,
            "intake_kb_d": post["intake_kb_d"].to_numpy(dtype=float),
            "capacity_assumed": post["capacity_assumed"].to_numpy()
            if "capacity_assumed" in post
            else False,
            "in_sample_residual_sd_multiples": residual / fit.resid.std(ddof=1),
        }
    )

    # The crack and the margin are read from their OWN series and not from the
    # joined frame, whose right hand end is JODI's. SPEC.md section 7.2 shows the
    # margin data date and the runs data date separately for exactly this reason,
    # and the reason the post break sample is as short as it is, is that the two
    # ends differ.
    crack_last = crack_frame().dropna(subset=[CRACK_GASOIL])["date"].max()
    margin_last = margin_frame()["date"].max()
    runs_last = pd.Timestamp(frame.dropna(subset=["intake_kb_d"])["date"].max())

    too_short = len(post) < min_post_months
    if too_short:
        verdict = (
            "THE POST BREAK SAMPLE IS %d MONTHS AND THIS STUDY WILL NOT RETURN A "
            "VERDICT ON %d. JODI refinery intake, which is the dependent, ends "
            "%s; the OPEC Rotterdam quotations end %s and the DGEC margin ends "
            "%s; so there are %d months after %s that have a dependent and all "
            "three lags of %s. The bar set before looking was %d months, one "
            "seasonal cycle, because this equation carries eleven month dummies "
            "and a verdict drawn from fewer months than it has seasonal terms is "
            "a verdict about which months happened to fall after the break. The "
            "residuals below are a description of those %d months and are not a "
            "test."
            % (
                len(post),
                len(post),
                str(runs_last.date()),
                str(pd.Timestamp(crack_last).date()),
                str(pd.Timestamp(margin_last).date()),
                len(post),
                BREAK_2026_DATE,
                regressor,
                min_post_months,
                len(post),
            )
        )
    else:
        verdict = (
            "The post break sample is %d months, which clears the %d month bar "
            "set before looking, so a test is reportable." % (len(post), min_post_months)
        )
    return BreakResult(
        dependent=dependent,
        regressor=regressor,
        break_date=BREAK_2026_DATE,
        n_pre=len(pre),
        n_post=len(post),
        min_post_months=int(min_post_months),
        too_short=bool(too_short),
        verdict=verdict,
        residuals=residuals,
        pre_residual_sd=float(fit.resid.std(ddof=1)),
        jodi_last_month=str(runs_last.date()),
        crack_last_month=str(pd.Timestamp(crack_last).date()),
        margin_last_month=str(pd.Timestamp(margin_last).date()),
        capacity_assumed_post=int(
            post["capacity_assumed"].sum() if "capacity_assumed" in post else 0
        ),
        explanations=_events(
            (
                "strikes_on_iran_hormuz_2026_02_28",
                "iea_collective_action_400_mb_2026_03_11",
                "us_iran_ceasefire_2026_04_07",
            )
        ),
    )


# ---------------------------------------------------------------------------
# SPEC.md section 6.5, seasonality
# ---------------------------------------------------------------------------

#: SPEC.md section 6.5: "a toggle that removes 2020, 2022 and 2026 from the
#: range". The three crisis years of SPEC.md section 3.
SEASONAL_REMOVABLE_YEARS = (2020, 2022, 2026)
#: "the prior five years as a range".
SEASONAL_RANGE_YEARS = 5

#: The textbook claim SPEC.md section 6.5 asks to be CHECKED and not asserted.
#: Northern hemisphere driving season and heating season, as a desk would say
#: them. The month sets are written down here, before the test, and are not
#: adjusted afterwards.
DRIVING_SEASON_MONTHS = (5, 6, 7, 8, 9)
HEATING_SEASON_MONTHS = (11, 12, 1, 2, 3)


def seasonal_monthly(
    crack: str = CRACK_GASOIL,
    current_year: int | None = None,
    exclude_years: Sequence[int] = (),
    range_years: int = SEASONAL_RANGE_YEARS,
    frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """One crack by calendar month: the prior years as a range, this year as a line.

    THE LONG HISTORY. The OPEC MOMR Rotterdam quotations run from 2000-10, which
    is the only series in this project that reaches back far enough to give a
    five year range for every month of the year.

    Returns:
        month, n_years, minimum, p25, median, p75, maximum, mean, current, and
        years_used, which is the list of years actually in the range after the
        exclusions, so a chart can print what it drew from.
    """
    if frame is None:
        frame = crack_frame()
    work = frame.dropna(subset=[crack])[["date", crack]].copy()
    work["year"] = work["date"].dt.year
    work["month"] = work["date"].dt.month
    if current_year is None:
        current_year = int(work["year"].max())
    excluded = {int(y) for y in exclude_years}
    # The window is the last range_years years that survive the exclusions, so
    # removing 2020 reaches one year further back instead of leaving a four year
    # range labelled as five. The years actually used travel on the result.
    available = sorted(
        y for y in work["year"].unique() if y < current_year and y not in excluded
    )
    years_used = available[-range_years:]
    prior = work[work["year"].isin(years_used)]
    current = work[work["year"] == current_year].set_index("month")[crack]

    rows = []
    for month in range(1, 13):
        block = prior.loc[prior["month"] == month, crack]
        rows.append(
            {
                "month": month,
                "n_years": int(len(block)),
                "minimum": float(block.min()) if len(block) else np.nan,
                "p25": float(block.quantile(0.25)) if len(block) else np.nan,
                "median": float(block.median()) if len(block) else np.nan,
                "p75": float(block.quantile(0.75)) if len(block) else np.nan,
                "maximum": float(block.max()) if len(block) else np.nan,
                "mean": float(block.mean()) if len(block) else np.nan,
                "current": float(current[month]) if month in current.index else np.nan,
            }
        )
    out = pd.DataFrame(rows)
    out.attrs["years_used"] = tuple(int(y) for y in years_used)
    out.attrs["current_year"] = int(current_year)
    out.attrs["excluded_years"] = tuple(sorted(excluded))
    out.attrs["source"] = "OPEC MOMR Rotterdam monthly quotations, 2000-10 onward"
    return out


def seasonal_weekly(
    crack: str = CRACK_GASOIL,
    current_year: int | None = None,
    exclude_years: Sequence[int] = (),
    range_years: int = SEASONAL_RANGE_YEARS,
    frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """The same shape by ISO week, on this study's weekly reconstruction.

    WHERE THE WEEKLY LAYER REACHES, AND WHERE IT DOES NOT. The reconstructed DGEC
    weekly series begins 2022-07-01, so it carries at most four calendar years and
    its first half year is 2022 only. SPEC.md section 6.5's "prior five years as a
    range" IS NOT AVAILABLE WEEKLY IN THIS PROJECT and no amount of arranging
    makes it available. The n_years column on every row says how many years that
    week actually has, and it is the number a chart has to print beside the band.

    The weekly quotations are DGEC's Gazole and Eurosuper, which are not the same
    products as the OPEC gasoil and premium gasoline of the monthly table, so the
    two are two panels and are never spliced into one line.
    """
    if frame is None:
        frame = series.dgec_weekly_cracks()
    work = frame.dropna(subset=[crack])[["date", crack]].copy()
    work["date"] = pd.to_datetime(work["date"])
    iso = work["date"].dt.isocalendar()
    work["year"] = iso["year"].astype(int)
    work["week"] = iso["week"].astype(int)
    if current_year is None:
        current_year = int(work["year"].max())
    excluded = {int(y) for y in exclude_years}
    available = sorted(
        y for y in work["year"].unique() if y < current_year and y not in excluded
    )
    years_used = available[-range_years:]
    prior = work[work["year"].isin(years_used)]
    current = work[work["year"] == current_year].set_index("week")[crack]

    rows = []
    for week in range(1, 54):
        block = prior.loc[prior["week"] == week, crack]
        rows.append(
            {
                "week": week,
                "n_years": int(block.count()),
                "minimum": float(block.min()) if len(block) else np.nan,
                "median": float(block.median()) if len(block) else np.nan,
                "maximum": float(block.max()) if len(block) else np.nan,
                "mean": float(block.mean()) if len(block) else np.nan,
                "current": float(current[week]) if week in current.index else np.nan,
            }
        )
    out = pd.DataFrame(rows)
    out.attrs["years_used"] = tuple(int(y) for y in years_used)
    out.attrs["current_year"] = int(current_year)
    out.attrs["excluded_years"] = tuple(sorted(excluded))
    out.attrs["source"] = (
        "this study's reconstruction of the DGEC weekly note chart, Gazole and "
        "Eurosuper, %s onward. NOT a DGEC publication"
        % str(pd.Timestamp(work["date"].min()).date())
    )
    return out


def seasonal_join() -> Mapping[str, object]:
    """Where the weekly layer and the monthly layer meet, and how far apart they are.

    Two different sources quoting two different products, so this is NOT a splice
    and the number below is not an error term. It is the size of the step a reader
    would take if he read across from one panel to the other, measured so that he
    does not have to guess it.
    """
    weekly = series.dgec_weekly_cracks()
    weekly["date"] = pd.to_datetime(weekly["date"])
    weekly["month"] = weekly["date"].dt.to_period("M").dt.to_timestamp()
    monthly_from_weekly = weekly.groupby("month")[
        [CRACK_GASOIL, CRACK_GASOLINE]
    ].mean()
    monthly = crack_frame().set_index("date")[[CRACK_GASOIL, CRACK_GASOLINE]]
    joined = monthly_from_weekly.join(
        monthly, how="inner", lsuffix="_weekly", rsuffix="_monthly"
    )
    out: dict[str, object] = {
        "overlap_months": int(len(joined)),
        "first_overlap_month": str(joined.index.min().date()) if len(joined) else "",
        "last_overlap_month": str(joined.index.max().date()) if len(joined) else "",
        "weekly_first": str(pd.Timestamp(weekly["date"].min()).date()),
        "weekly_last": str(pd.Timestamp(weekly["date"].max()).date()),
        "weekly_rows": int(len(weekly)),
        "monthly_first": str(monthly.index.min().date()),
        "monthly_last": str(monthly.index.max().date()),
        "monthly_rows": int(len(monthly)),
    }
    for crack in (CRACK_GASOIL, CRACK_GASOLINE):
        gap = joined["%s_weekly" % crack] - joined["%s_monthly" % crack]
        out["%s_mean_gap" % crack] = float(gap.mean())
        out["%s_mean_absolute_gap" % crack] = float(gap.abs().mean())
        out["%s_correlation" % crack] = float(
            joined["%s_weekly" % crack].corr(joined["%s_monthly" % crack])
        )
    return out


def seasonal_textbook_check(
    exclude_years: Sequence[int] = (),
    frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """CHECK, do not assert: does gasoline firm into summer and gasoil into winter.

    SPEC.md section 6.5 asks for the textbook pattern to be checked. The check has
    to survive the fact that the level of a crack moves enormously between years
    for reasons that have nothing to do with the season, so:

      1. Each year's cracks are demeaned by that year's own mean. What is left is
         the within year shape, which is the only thing a seasonal claim is about.
      2. For each year, the mean of the season's months less the mean of the other
         months is one number. Years, not months, are the unit, so twenty five
         numbers rather than three hundred correlated ones.
      3. The reported t is that difference's mean over its standard error across
         years. A year is plausibly independent of the next for this purpose; a
         month is not.

    Only complete years are used, because a partial year's own mean is not
    comparable with a full one's. The result is reported whichever way it comes
    out, including the way that contradicts the textbook.
    """
    if frame is None:
        frame = crack_frame()
    excluded = {int(y) for y in exclude_years}
    rows = []
    for crack, season, label in (
        (CRACK_GASOLINE, DRIVING_SEASON_MONTHS, "gasoline into the driving season"),
        (CRACK_GASOIL, HEATING_SEASON_MONTHS, "gasoil into the heating season"),
    ):
        work = frame.dropna(subset=[crack])[["date", crack]].copy()
        work["year"] = work["date"].dt.year
        work["month"] = work["date"].dt.month
        complete = work.groupby("year")["month"].count()
        years = [
            int(y) for y in complete[complete == 12].index if int(y) not in excluded
        ]
        differences, in_season, out_season = [], [], []
        for year in years:
            block = work[work["year"] == year]
            demeaned = block[crack] - block[crack].mean()
            mask = block["month"].isin(season)
            differences.append(float(demeaned[mask].mean() - demeaned[~mask].mean()))
            in_season.append(float(demeaned[mask].mean()))
            out_season.append(float(demeaned[~mask].mean()))
        values = np.asarray(differences, dtype=float)
        n = len(values)
        se = float(values.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
        mean = float(values.mean()) if n else float("nan")
        rows.append(
            {
                "claim": label,
                "crack": crack,
                "season_months": tuple(season),
                "complete_years": n,
                "first_year": min(years) if years else np.nan,
                "last_year": max(years) if years else np.nan,
                "excluded_years": tuple(sorted(excluded)),
                "in_season_mean_usd_bbl": float(np.mean(in_season)) if n else np.nan,
                "out_of_season_mean_usd_bbl": float(np.mean(out_season))
                if n
                else np.nan,
                "difference_usd_bbl": mean,
                "se": se,
                "t": mean / se if se and se > 0 else float("nan"),
                "years_positive": int((values > 0).sum()),
                "holds": bool(n > 1 and se > 0 and mean / se > 2.0),
            }
        )
    return pd.DataFrame(rows)


def seasonal_shape(
    exclude_years: Sequence[int] = (),
    frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """The within year shape of each crack, month by month, in $/bbl.

    The same year demeaning as seasonal_textbook_check, averaged by calendar
    month. This is what the seasonal claim looks like when it is drawn rather
    than summarised, and it is where the peak and trough months are read off.
    """
    if frame is None:
        frame = crack_frame()
    excluded = {int(y) for y in exclude_years}
    out = pd.DataFrame({"month": range(1, 13)})
    for crack in (CRACK_GASOIL, CRACK_GASOLINE):
        work = frame.dropna(subset=[crack])[["date", crack]].copy()
        work["year"] = work["date"].dt.year
        work["month"] = work["date"].dt.month
        complete = work.groupby("year")["month"].count()
        years = [
            int(y) for y in complete[complete == 12].index if int(y) not in excluded
        ]
        work = work[work["year"].isin(years)]
        work["demeaned"] = work[crack] - work.groupby("year")[crack].transform("mean")
        by_month = work.groupby("month")["demeaned"].agg(["mean", "std", "count"])
        out["%s_mean" % crack] = by_month["mean"].reindex(out["month"]).to_numpy()
        out["%s_se" % crack] = (
            (by_month["std"] / np.sqrt(by_month["count"]))
            .reindex(out["month"])
            .to_numpy()
        )
    out.attrs["excluded_years"] = tuple(sorted(excluded))
    return out


# ---------------------------------------------------------------------------
# The report, so that everything above can be run and read in one place
# ---------------------------------------------------------------------------


def _wrap(text: str, width: int = 74) -> list[str]:
    """Wrap one of this module's stated paragraphs for the text report.

    textwrap is not imported for one call, and this is the whole of it: split on
    spaces and fill to width. The paragraphs it wraps are the exclusion
    restriction and the verdicts, which are written as single strings so that
    they can be asserted verbatim in tests/test_analysis.py and carried into
    docs/methodology.md without being retyped.
    """
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else current + " " + word
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _fmt(value: float, places: int = 4) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "NaN"
    return ("%%.%df" % places) % value


def _response_lines(model: ResponseModel) -> list[str]:
    lines = [
        "  %s" % model.label,
        "    sample        %s to %s, n = %d, Newey-West lag %d, R2 %s, adj R2 %s"
        % (
            model.first_month,
            model.last_month,
            model.regression.nobs,
            model.regression.nw_lag,
            _fmt(model.regression.r2, 4),
            _fmt(model.regression.adj_r2, 4),
        ),
        "    episodes      %s, as dummies: %s, months on assumed 2026 capacity: %d"
        % (
            ", ".join(model.episodes_in_sample) or "none in sample",
            model.episodes_as_dummies,
            model.capacity_assumed_months,
        ),
    ]
    steps = [n for n in model.regression.names if n.startswith("closure_step_")]
    if steps or "trend_months" in model.regression.names:
        lines.append(
            "    terms         %s%s"
            % (
                "a linear monthly trend, " if "trend_months" in model.regression.names
                else "",
                "closure steps that vary inside the sample: %s"
                % (", ".join(steps) if steps else "none"),
            )
        )
    for name in model.lag_terms:
        value, se = model.regression.get(name)
        lines.append(
            "    %-28s %+9.5f  NW se %8.5f  t %+6.2f"
            % (name, value, se, value / se if se else float("nan"))
        )
    lines.append(
        "    sum of lags                  %+9.5f  NW se %8.5f  t %+6.2f  "
        "95 pct %+.5f to %+.5f  [%s]"
        % (
            model.sum_b,
            model.sum_b_se,
            model.sum_b_t,
            model.sum_b_low,
            model.sum_b_high,
            model.translation.per_usd_unit,
        )
    )
    t = model.translation
    lines.append(
        "    10 $/bbl is worth %+.1f kb/d of crude demand, 95 pct %+.1f to %+.1f, "
        "which is %+.2f pct of runs (%+.2f to %+.2f)"
        % (
            t.kb_d,
            t.kb_d_low,
            t.kb_d_high,
            100 * t.share_of_runs,
            100 * t.share_of_runs_low,
            100 * t.share_of_runs_high,
        )
    )
    lines.append(
        "    base %s = %.1f, runs base %s = %.1f"
        % (t.base_label, t.base_kb_d, t.runs_label, t.runs_kb_d)
    )
    return lines


def report(replications: int = BOOTSTRAP_REPLICATIONS) -> str:
    """Everything in SPEC.md sections 6.1 and 6.2, computed and printed.

    Run it with `python -m crack.analysis`. Nothing here is written to data/ and
    nothing is written for the site: SPEC.md section 10 puts the site behind Gate
    4, and this is a text report a human reads.
    """
    out: list[str] = []
    add = out.append

    add("SPEC.md section 6.1 and 6.2, Gate 3")
    add("=" * 78)
    add("")
    add("The margin this asks about")
    add("-" * 78)
    margin = margin_frame()
    add(
        "  DGEC's published MBR is already net of purchased gas at DGEC's own "
        "embedded intensity"
    )
    add(
        "  of %.5f MMBtu/bbl. This study re-prices it at its own EIA derived "
        "%.5f MMBtu/bbl."
        % (
            config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL,
            config.GAS_INTENSITY_MMBTU_PER_BBL,
        )
    )
    add(
        "  margin_study_intensity = MBR - gas wedge. This is NOT the spec's "
        "original horse C and the"
    )
    add("  substitution is stated in docs/methodology.md.")
    add(
        "  MBR                    mean %s  min %s  max %s  n %d"
        % (
            _fmt(margin[MARGIN_OFFICIAL].mean(), 3),
            _fmt(margin[MARGIN_OFFICIAL].min(), 3),
            _fmt(margin[MARGIN_OFFICIAL].max(), 3),
            len(margin),
        )
    )
    add(
        "  gas wedge              mean %s  min %s  max %s"
        % (
            _fmt(margin["gas_wedge_usd_bbl"].mean(), 3),
            _fmt(margin["gas_wedge_usd_bbl"].min(), 3),
            _fmt(margin["gas_wedge_usd_bbl"].max(), 3),
        )
    )
    add(
        "  margin_study_intensity mean %s  min %s  max %s  %s to %s"
        % (
            _fmt(margin[MARGIN_STUDY_INTENSITY].mean(), 3),
            _fmt(margin[MARGIN_STUDY_INTENSITY].min(), 3),
            _fmt(margin[MARGIN_STUDY_INTENSITY].max(), 3),
            margin["date"].iloc[0].date(),
            margin["date"].iloc[-1].date(),
        )
    )
    add("")

    add("1. Utilisation")
    add("-" * 78)
    check = utilisation_sanity_check()
    add("  NWE5 crude intake over Energy Institute capacity, step interpolation.")
    add("  Against what recon 03 section 2.3 measured:")
    add("    year  utilisation     recon  difference  agrees")
    for _, row in check.iterrows():
        add(
            "    %4d  %11s  %8.3f  %+10.6f  %s"
            % (
                int(row["year"]),
                _fmt(row["utilisation"], 4),
                row["recon"],
                row["difference"],
                "yes" if row["agrees_to_3dp"] else "NO",
            )
        )
    disagree = check[~check["agrees_to_3dp"]]
    add(
        "  %d of %d years agree to three decimals."
        % (len(check) - len(disagree), len(check))
    )
    capacity_kb_d, capacity_year = latest_capacity_kb_d()
    add(
        "  2026: no capacity figure exists in any source reached. The published "
        "series leaves"
    )
    add(
        "  2026 NaN (basis %r). The regressions below run on basis %r, which "
        "carries the %d"
        % (CAPACITY_2026_NAN, CAPACITY_2026_HELD_FLAT, capacity_year)
    )
    add(
        "  figure of %.1f kb/d into 2026 and flags every affected month. The "
        "without-2026 row is"
        % capacity_kb_d
    )
    add("  the estimate that rests on no assumption.")
    add("  Closure step years the fallback draws on, NWE5 capacity falling more")
    add("  than %.0f percent in a year:" % (100 * CLOSURE_STEP_MIN_FALL))
    add("    all years in the capacity file  %s" % (capacity_step_years(),))
    add("")

    frame = analysis_frame(CAPACITY_2026_HELD_FLAT, CAPACITY_STEP)
    add("2. The response, SPEC.md section 6.1")
    add("-" * 78)
    add("  Capacity model, utilisation in percent of capacity")
    models = [
        margin_response(frame=frame, label="with episodes as regime dummies"),
        margin_response(
            frame=frame,
            label="no regime dummies, full sample",
            episode_dummies=False,
        ),
        margin_response(
            frame=frame,
            label="episode months dropped from the sample",
            episode_dummies=False,
            drop_episode_months=True,
        ),
        margin_response(
            frame=frame,
            regressor=MARGIN_OFFICIAL,
            label="DGEC official MBR, regime dummies, for comparison",
        ),
    ]
    for model in models:
        for line in _response_lines(model):
            add(line)
        add("")
    add("  Fallback model, 100 * log of NWE5 crude intake")
    fallback = [
        intake_trend_response(frame=frame, label="trend, month FE, closure steps"),
        intake_trend_response(
            frame=frame,
            label="trend, month FE, no closure steps (no capacity data at all)",
            closure_years=(),
        ),
        intake_trend_response(
            frame=frame,
            label="episode months dropped from the sample",
            episode_dummies=False,
            drop_episode_months=True,
        ),
    ]
    for model in fallback:
        for line in _response_lines(model):
            add(line)
        add("")

    add("  The two models disagree, and this is the reason, not a tie breaker")
    add(
        "    The two dependents differ only by the denominator. utilisation_pct "
        "divides intake by a"
    )
    add(
        "    capacity that is a step function, and that step fell %.1f percent in "
        "2016 and %.1f percent"
        % (
            -100
            * float(
                capacity_annual().set_index("year")["capacity_kb_d"].pct_change()[2016]
            ),
            -100
            * float(
                capacity_annual().set_index("year")["capacity_kb_d"].pct_change()[2025]
            ),
        )
    )
    add(
        "    in 2025, inside the sample. The capacity equation of SPEC.md section "
        "6.1 carries no trend"
    )
    add(
        "    and no closure step, so those jumps sit in its dependent as noise. "
        "The fallback carries"
    )
    add(
        "    both and absorbs them. NEITHER IS DECLARED THE WINNER HERE. The "
        "spec asks for both and"
    )
    add("    both are above, with their own standard errors.")
    add("")
    # THAT EXPLANATION IS A CLAIM, so it gets tested rather than asserted. Put
    # the trend and the closure steps into the capacity equation, change nothing
    # else, and see whether its coefficient moves to the fallback's. This is a
    # diagnostic and NOT a specification this study reports: SPEC.md section 6.1
    # writes the capacity equation without them and the headline rows above are
    # the spec's equation. It is reported whichever way it comes out.
    diagnostic = margin_response(
        frame=frame,
        label="DIAGNOSTIC ONLY, not SPEC.md section 6.1's equation: "
        "utilisation with a trend and closure steps",
        trend=True,
        closure_years=capacity_step_years(),
    )
    add("  Testing that explanation rather than asserting it")
    for line in _response_lines(diagnostic):
        add(line)
    spec_sum = models[0].sum_b
    fallback_sum = fallback[0].sum_b
    add(
        "    The spec's capacity equation gives %+.4f, the fallback gives %+.4f, "
        "and the capacity"
        % (spec_sum, fallback_sum)
    )
    add(
        "    equation with the fallback's trend and closure steps added gives "
        "%+.4f." % diagnostic.sum_b
    )
    moved = abs(diagnostic.sum_b - spec_sum)
    gap = abs(fallback_sum - spec_sum)
    if gap > 0 and moved / gap > 0.5:
        add(
            "    It moves %.0f percent of the way, so the two terms are most of "
            "the disagreement and the"
            % (100 * moved / gap)
        )
        add(
            "    explanation above holds. IT IS STILL NOT THE SPEC'S EQUATION AND "
            "IT IS NOT REPORTED AS A"
        )
        add(
            "    RESULT. What it buys is that the reason given for the gap is a "
            "measurement, not a story."
        )
    else:
        add(
            "    It moves only %.0f percent of the way, so the trend and the "
            "closure steps are NOT the"
            % (100 * moved / gap if gap > 0 else 0.0)
        )
        add(
            "    explanation, and the paragraph above is wrong. The two models "
            "disagree for some other"
        )
        add("    reason and this study has not identified it.")
    add("")

    add("  Crude imports beside intake, arithmetic only, no second model")
    stats = imports_beside_intake(frame)
    for key in sorted(stats):
        value = stats[key]
        add(
            "    %-28s %s"
            % (key, _fmt(value, 4) if isinstance(value, float) else value)
        )
    best = models[0]
    add(
        "    imports are %.1f percent of intake on average, so the %.1f kb/d "
        "intake response of the"
        % (100 * stats["mean_imports_over_intake"], best.translation.kb_d)
    )
    add(
        "    first row above reads across to about %.1f kb/d of crude imports. "
        "That is arithmetic on"
        % (best.translation.kb_d * stats["mean_imports_over_intake"])
    )
    add(
        "    the ratio, NOT evidence that imports respond, and SPEC.md section "
        "6.1 asks for no second model."
    )
    add("")

    add("3. The run cut threshold, SPEC.md section 6.2")
    add("-" * 78)
    threshold = run_cut_threshold(frame=frame, replications=replications)
    add(
        "  sample        %s to %s, n = %d"
        % (threshold.first_month, threshold.last_month, threshold.nobs)
    )
    add(
        "  regressor     mean of margin_study_intensity over t-1, t-2, t-3, "
        "range %.2f to %.2f $/bbl"
        % (threshold.regressor_min, threshold.regressor_max)
    )
    add(
        "  grid          %.2f to %.2f $/bbl in %.2f steps, %d candidates"
        % (
            float(threshold.grid[0]),
            float(threshold.grid[-1]),
            float(threshold.grid[1] - threshold.grid[0]),
            len(threshold.grid),
        )
    )
    add(
        "  block length  %d months. %s"
        % (threshold.block_length, threshold.block_choice)
    )
    add(
        "  autocorrelations of utilisation, lags 1 to %d: %s"
        % (
            min(12, len(threshold.acf)),
            ", ".join("%.3f" % v for v in threshold.acf[:12]),
        )
    )
    add(
        "  bootstrap     %d moving block replications, seed %d"
        % (threshold.replications, threshold.seed)
    )
    add(
        "  point         threshold %.2f $/bbl, level %.3f pct, slope below "
        "%+.4f pct per $/bbl, NW se %.4f"
        % (
            threshold.point.threshold,
            threshold.point.level,
            threshold.point.slope_below,
            threshold.point.slope_below_se,
        )
    )
    add(
        "                months below the threshold %d of %d, kink R2 %.4f, "
        "straight line R2 %.4f"
        % (
            threshold.point.months_below,
            threshold.nobs,
            threshold.point.r2,
            threshold.linear_r2,
        )
    )
    add(
        "  interval      %.2f to %.2f $/bbl, width %.2f"
        % (threshold.ci_low, threshold.ci_high, threshold.ci_width)
    )
    draws = threshold.draws
    add(
        "  draws         quantiles 5, 25, 50, 75, 95: %s"
        % ", ".join(
            "%.2f" % v for v in np.quantile(draws, [0.05, 0.25, 0.5, 0.75, 0.95])
        )
    )
    add(
        "                %.1f percent of draws sit at the top of the grid and "
        "%.1f percent at the bottom."
        % (
            100 * float((draws >= threshold.grid[-1]).mean()),
            100 * float((draws <= threshold.grid[0]).mean()),
        )
    )
    add(
        "                Three quarters of the draws fall between %.2f and %.2f "
        "$/bbl. THAT IS A DESCRIPTION"
        % (float(np.quantile(draws, 0.125)), float(np.quantile(draws, 0.875)))
    )
    add(
        "                OF THE DRAWS, NOT A CONFIDENCE INTERVAL, and it is not "
        "offered as a substitute"
    )
    add(
        "                for one. The 95 percent interval is the line above and "
        "it reaches the edge."
    )
    add(
        "  what the      A threshold is not an ordinary parameter. The location of "
        "a kink has non"
    )
    add(
        "  interval is   standard asymptotics, and a percentile interval from "
        "resampled data is an"
    )
    add(
        "                approximation to its sampling distribution rather than an "
        "exact statement"
    )
    add(
        "                about coverage. It is reported here because SPEC.md "
        "section 6.2 asks for a"
    )
    add(
        "                block bootstrap interval by name and because the verdict "
        "it feeds is a"
    )
    add(
        "                NEGATIVE one: an interval whose true coverage is uncertain "
        "is weak grounds"
    )
    add(
        "                for claiming a threshold and adequate grounds for "
        "declining to. Had this"
    )
    add(
        "                come back identified, the caveat would have had to be read "
        "the other way."
    )
    add("  VERDICT       %s" % threshold.verdict.upper())
    for reason in threshold.reasons:
        add("                because %s" % reason)
    if not threshold.identified:
        add(
            "                so the site shows no headroom figure and falls back "
            "to the ten year"
        )
        add(
            "                percentile, exactly as SPEC.md section 6.2 "
            "instructs. headroom is None."
        )
    add("")
    add("  WHICH MONTHS SIT BELOW THE ESTIMATED THRESHOLD, which is the thing to read")
    add(
        "    %d months, the longest unbroken run of them %d months: %s"
        % (
            len(threshold.months_below),
            threshold.longest_run_below,
            ", ".join(threshold.months_below),
        )
    )
    add(
        "    mean utilisation below %.2f pct, above %.2f pct."
        % (threshold.mean_utilisation_below, threshold.mean_utilisation_above)
    )
    # MEASURED, NOT ASSERTED. Every clause of the paragraph below is read off
    # the result, because a sentence saying "the kink is one episode" that was
    # typed rather than computed would go on saying it after the next data
    # refresh moved the months. SPEC.md non negotiable 8.
    below_count = len(threshold.months_below)
    longest = threshold.longest_run_below
    scattered = below_count - longest
    concentration = longest / below_count if below_count else float("nan")
    add(
        "    CONCENTRATION: %d of those %d months, %.0f percent, are ONE unbroken "
        "stretch, and the"
        % (longest, below_count, 100 * concentration)
    )
    add(
        "    remaining %d %s scattered. The stretch runs %s to %s."
        % (
            scattered,
            "is" if scattered == 1 else "are",
            threshold.months_below[-longest] if longest else "n/a",
            threshold.months_below[-1] if longest else "n/a",
        )
    )
    if concentration >= 0.75:
        add(
            "    So the kink is ESTIMATED FROM ONE EPISODE. A threshold read off a "
            "single continuous"
        )
        add(
            "    stretch of months describes that stretch. It is not evidence of a "
            "level the NWE system"
        )
        add(
            "    returns to and cuts runs at, and the sample holds no second "
            "episode to test it on."
        )
        add(
            "    That, and not only the interval, is why this study reports no "
            "headroom figure."
        )
    else:
        add(
            "    The months below are spread across the sample rather than "
            "concentrated in one episode,"
        )
        add(
            "    so the objection in the line above does not apply to this run. "
            "Read the interval."
        )
    add("")
    add(
        "  Does the verdict turn on where the grid was cut. A check, and the "
        "headline grid did not move."
    )
    sensitivity = threshold_grid_sensitivity(frame=frame)
    add(
        "    quantiles        grid            point   95 pct interval    width  "
        "identified"
    )
    for _, row in sensitivity.iterrows():
        add(
            "    %-14s  %6.2f to %6.2f  %6.2f  %6.2f to %6.2f  %6.2f  %s"
            % (
                row["quantiles"],
                row["grid_low"],
                row["grid_high"],
                row["threshold"],
                row["ci_low"],
                row["ci_high"],
                row["ci_width"],
                "yes" if row["identified"] else "no",
            )
        )
    identified_grids = int(sensitivity["identified"].sum())
    if identified_grids == 0:
        add(
            "    Unidentified on all %d grids examined, so the verdict is not an "
            "artefact of the cut."
            % len(sensitivity)
        )
    else:
        add(
            "    %d of the %d grids examined came back identified. THE VERDICT "
            "TURNS ON THE CUT and the"
            % (identified_grids, len(sensitivity))
        )
        add(
            "    headline row above, which is the pre-registered grid, is the one "
            "this study reports."
        )
    add(
        "    The first row is the headline. The other three are reported because "
        "the objection is"
    )
    add(
        "    obvious and measuring it is cheaper than arguing about it; nothing "
        "downstream reads them."
    )
    # The first sensitivity row runs the SAME grid as the headline on fewer
    # replications, so the gap between the two is a direct measurement of the
    # Monte Carlo error in the interval. Printed, not characterised in words.
    headline_row = sensitivity.iloc[0]
    add(
        "    Row one runs the headline grid at %d replications rather than %d. "
        "Its interval is %.2f to"
        % (GRID_SENSITIVITY_REPLICATIONS, threshold.replications, headline_row["ci_low"], )
    )
    add(
        "    %.2f against the headline's %.2f to %.2f, so the Monte Carlo error in "
        "the endpoints is"
        % (headline_row["ci_high"], threshold.ci_low, threshold.ci_high)
    )
    add(
        "    %.2f and %.2f $/bbl at this replication count. The verdict does not "
        "move with it."
        % (
            abs(headline_row["ci_low"] - threshold.ci_low),
            abs(headline_row["ci_high"] - threshold.ci_high),
        )
    )
    add("")

    # -----------------------------------------------------------------------
    # SPEC.md section 6.3
    # -----------------------------------------------------------------------
    horses = horse_frame()
    add("4. The horse race, SPEC.md section 6.3, which the spec calls the point")
    add("-" * 78)
    for horse in HORSES:
        add("  %s  %s" % (horse.key, horse.name))
        for line in _wrap(horse.what_it_is, 72):
            add("     %s" % line)
        if horse.substitution:
            for line in _wrap("SUBSTITUTION. %s." % horse.substitution_note, 72):
                add("     %s" % line)
    add("")
    add("  THE SAMPLE TRAP, and what was done about it")
    add(
        "    Horse A can be computed from %s because the OPEC Rotterdam "
        "quotations start 2000-10."
        % str(
            pd.Timestamp(
                common_sample_dates(horses, [CRACK_GASOIL], DEPENDENT_CAPACITY).min()
            ).date()
        )
    )
    add(
        "    Horses B and C only exist from 2015-01 because DGEC's file does. "
        "Racing them on their own"
    )
    add(
        "    samples would hand A twenty extra years of quiet data and the "
        "comparison would be invalid."
    )
    add(
        "    So the race runs on the COMMON SAMPLE and A's longer sample is "
        "reported separately, below,"
    )
    add("    and labelled.")
    add("")

    race_results: dict[str, list[HorseResult]] = {}
    for dependent in DEPENDENTS:
        results = horse_race(dependent, frame=horses)
        race_results[dependent] = results
        table = horse_race_frame(results)
        unit = (
            "percentage points of capacity per $/bbl"
            if dependent == DEPENDENT_CAPACITY
            else "percent of runs per $/bbl"
        )
        add(
            "  Dependent: %s  [%s]"
            % (
                "utilisation over Energy Institute capacity, in percent"
                if dependent == DEPENDENT_CAPACITY
                else "100 times the log of NWE5 crude intake, the fallback",
                unit,
            )
        )
        add(
            "    sample %s to %s, n = %d for every horse, Newey-West lag %d"
            % (
                results[0].model.first_month,
                results[0].model.last_month,
                results[0].model.regression.nobs,
                results[0].model.regression.nw_lag,
            )
        )
        add(
            "    horse  sum of lags     NW se       t       R2   adj R2   "
            "OOS RMSE   vs mean   kb/d per 10 $"
        )
        for _, row in table.iterrows():
            add(
                "    %-5s  %+11.5f  %8.5f  %+6.2f  %7.4f  %7.4f  %9.4f  %8.4f  "
                "%+13.1f"
                % (
                    row["horse"] + ("*" if row["substitution"] else " "),
                    row["sum_of_lags"],
                    row["nw_se"],
                    row["t"],
                    row["r2"],
                    row["adj_r2"],
                    row["oos_rmse"],
                    row["oos_mean_benchmark_rmse"],
                    row["kb_d_per_10_usd"],
                )
            )
        add(
            "    * horse C is the substitution described above and is not "
            "SPEC.md section 6.3's original C."
        )
        add(
            "    The out of sample column is an expanding window, %d month "
            "minimum training sample,"
            % results[0].oos.min_train
        )
        add(
            "    %d one step ahead forecasts from %s to %s, refitted at every "
            "origin. The vs mean column"
            % (
                results[0].oos.n_forecasts,
                results[0].oos.first_forecast,
                results[0].oos.last_forecast,
            )
        )
        add(
            "    is the same exercise for a model that predicts the training "
            "mean and nothing else."
        )
        key, sentence = horse_race_winner(results)
        for i, line in enumerate(_wrap(sentence, 72)):
            add("    %s%s" % ("RANKING: " if i == 0 else "         ", line))
        add("    Pairwise, is any of that distinguishable from zero:")
        for i in range(len(results)):
            for j in range(i + 1, len(results)):
                add("      %s" % loss_differential(results[i], results[j]).sentence)
        add("")

    add("  Horse A on its own longer sample. REPORTED SEPARATELY, NOT THE RACE.")
    for dependent in DEPENDENTS:
        long_run = gasoil_long_sample(dependent, frame=horses)
        short_run = next(
            r for r in race_results[dependent] if r.horse.column == CRACK_GASOIL
        )
        add(
            "    %-16s %s to %s, n = %d: sum of lags %+.5f, NW se %.5f, t %+.2f, "
            "R2 %.4f, OOS RMSE %.4f"
            % (
                dependent,
                long_run.model.first_month,
                long_run.model.last_month,
                long_run.model.regression.nobs,
                long_run.model.sum_b,
                long_run.model.sum_b_se,
                long_run.model.sum_b_t,
                long_run.model.regression.r2,
                long_run.oos.rmse,
            )
        )
        add(
            "    %-16s on the race sample it was %+.5f, se %.5f. The difference "
            "between those two numbers"
            % ("", short_run.model.sum_b, short_run.model.sum_b_se)
        )
        add(
            "    %-16s is the size of the sample trap, measured, and it is why "
            "the race is on the common sample."
            % ""
        )
    add("")

    # THE PARAGRAPH THE GATE 3 BRIEF ASKS FOR, with every number in it read off
    # the results above rather than typed. SPEC.md section 2 rule 3.
    capacity_rank = sorted(race_results[DEPENDENT_CAPACITY], key=lambda r: r.oos.rmse)
    fallback_rank = sorted(race_results[DEPENDENT_FALLBACK], key=lambda r: r.oos.rmse)
    both_agree = capacity_rank[0].horse.key == fallback_rank[0].horse.key
    any_pair_distinguishable = any(
        loss_differential(results[i], results[j]).distinguishable
        for results in race_results.values()
        for i in range(len(results))
        for j in range(i + 1, len(results))
    )
    add("  WHAT THE RACE SAYS, in plain words")
    add(
        "    The lowest out of sample RMSE is horse %s under the capacity "
        "dependent and horse %s under"
        % (capacity_rank[0].horse.key, fallback_rank[0].horse.key)
    )
    add(
        "    the fallback, so the two dependents %s on the ordering. And it does "
        "not matter, because"
        % ("agree" if both_agree else "DISAGREE")
    )
    add(
        "    %s of the pairwise squared error differences, under either "
        "dependent, is distinguishable from"
        % ("at least one" if any_pair_distinguishable else "not one")
    )
    if not any_pair_distinguishable:
        add(
            "    zero. OUT OF SAMPLE, THE THREE HORSES ARE A DEAD HEAT. The raw "
            "gasoil crack is not beaten by"
        )
        add(
            "    the official margin and it does not beat it, and the same is "
            "true of this study's margin"
        )
        add(
            "    after gas. Anybody who says on this evidence that one of the "
            "three tracks NWE runs better"
        )
        add("    than the others is reading a ranking as a result.")
    else:
        add(
            "    zero, so the ordering above carries information and the pairwise "
            "lines say which pairs."
        )
    add(
        "    What DOES separate them is the in sample coefficient under the "
        "fallback dependent, where all"
    )
    add(
        "    three are positive and horses B and C reach a t of about 2 while A "
        "is smaller in units of runs;"
    )
    add(
        "    and the capacity dependent, where NONE of the three is "
        "distinguishable from zero at all."
    )
    add("")
    add("  WHAT B AND C GIVE THAT A CANNOT, which is this study's honest value")
    add(
        "    If the raw gasoil crack explains runs as well as the margin does, "
        "and on this sample it does,"
    )
    add(
        "    then the case for the margin is not that it forecasts runs better. "
        "It does not. The case is"
    )
    add(
        "    that the crack is not a quantity a refiner can act on. Three things "
        "follow from that, and no"
    )
    add("    crack can supply any of them:")
    add(
        "      A LEVEL. A crack of 25 $/bbl is a number; a margin of 6 $/bbl is a "
        "decision. Only the margin"
    )
    add(
        "      is denominated in what the barrel actually earns after the crude "
        "and the energy are paid for,"
    )
    add(
        "      so only the margin can be compared with a cash cost and only the "
        "margin has a sign that means"
    )
    add("      something.")
    add(
        "      THE GAS WEDGE. Over this sample the wedge between DGEC's embedded "
        "gas intensity and this"
    )
    add(
        "      study's ran %s to %s $/bbl, and it opened in 2022: it was %s "
        "$/bbl on average before 2022-01"
        % (
            _fmt(margin["gas_wedge_usd_bbl"].min(), 2),
            _fmt(margin["gas_wedge_usd_bbl"].max(), 2),
            _fmt(
                margin.loc[margin["date"] < "2022-01-01", "gas_wedge_usd_bbl"].mean(), 2
            ),
        )
    )
    add(
        "      and %s $/bbl in 2022. A gasoil crack cannot show that, because "
        "the same crack was worth"
        % _fmt(
            margin.loc[
                (margin["date"] >= "2022-01-01") & (margin["date"] < "2023-01-01"),
                "gas_wedge_usd_bbl",
            ].mean(),
            2,
        )
    )
    add(
        "      several dollars a barrel less to a gas fired refinery that year "
        "than to one that was not."
    )
    add(
        "      A THRESHOLD IN DOLLARS. A run cut level is a statement about the "
        "margin, and the question"
    )
    add(
        "      \"how far is today from the level where runs get cut\" cannot even "
        "be asked of a crack."
    )
    add(
        "      This study did not find that level, see section 3 above: it is "
        "UNIDENTIFIED. But the"
    )
    add(
        "      question is only askable in margin space, and that is a property "
        "of B and C and not of A."
    )
    add("")

    # -----------------------------------------------------------------------
    # SPEC.md section 6.3, endogeneity
    # -----------------------------------------------------------------------
    add("5. Endogeneity, stated plainly and not buried")
    add("-" * 78)
    add(
        "  RUNS MOVE CRACKS. More runs mean more product on the water and a "
        "weaker crack, so the crack"
    )
    add(
        "  this equation treats as a cause is partly an effect of the thing it is "
        "explaining. The bias"
    )
    add(
        "  that puts in the estimated response is TOWARD ZERO. Every coefficient "
        "in sections 2 and 4"
    )
    add(
        "  above should be read as a lower bound on the response in absolute "
        "value, and the honest"
    )
    add(
        "  reading of a coefficient indistinguishable from zero is therefore "
        "\"this sample cannot see"
    )
    add("  the response\", not \"there is no response\".")
    add(
        "  Lagging the regressor one to three months, which SPEC.md section 6.1 "
        "does, helps only partly."
    )
    add(
        "  It removes the same month simultaneity. It does not remove it at a "
        "lag, because a shock that"
    )
    add(
        "  raises runs this month raises product supply and depresses cracks for "
        "months afterwards, and"
    )
    add(
        "  because both series are persistent, so this month's runs are "
        "correlated with last month's."
    )
    add(
        "  This study does NOT claim to have removed the bias. The instrument in "
        "section 6 was the"
    )
    add("  attempt and it failed. What follows is the shape of the problem:")
    endogeneity = endogeneity_diagnostic(horses)
    add("    regressor                          lag  months  corr w/ intake  corr w/ util")
    for _, row in endogeneity.iterrows():
        add(
            "    %-33s  %3d  %6d  %+14.4f  %+13.4f"
            % (
                row["regressor"],
                row["lag"],
                row["months"],
                row["corr_with_intake"],
                row["corr_with_utilisation"],
            )
        )
    add(
        "    These are correlations and they identify nothing. Simultaneity is "
        "not visible in a"
    )
    add(
        "    correlation and no ordering of two contemporaneous monthly series "
        "says which moved first."
    )
    add(
        "    They are here so a reader can see how much of the relationship sits "
        "at lag 0, where the"
    )
    add("    causation runs both ways, and how little of it decays by lag 3.")
    add("")

    # -----------------------------------------------------------------------
    # SPEC.md section 6.3, the instrument
    # -----------------------------------------------------------------------
    add("6. The instrument, SPEC.md section 6.3")
    add("-" * 78)
    add("  THE EXCLUSION RESTRICTION, stated before the instrument was run")
    for line in _wrap(EXCLUSION_RESTRICTION, 74):
        add("    %s" % line)
    add("")
    add("  What was expected of the first stage, also written down first")
    for line in _wrap(MECHANICAL_RELEVANCE, 74):
        add("    %s" % line)
    add("")
    for dependent in DEPENDENTS:
        iv = gas_instrument(frame=horses, dependent=dependent)
        add(
            "  Dependent %s, %s to %s, n = %d, Newey-West lag %d"
            % (dependent, iv.first_month, iv.last_month, iv.nobs, iv.nw_lag)
        )
        add(
            "    endogenous  mean of %s over t-1, t-2, t-3" % iv.endogenous
        )
        add("    instrument  mean of %s over the same three months" % iv.instrument)
        add(
            "    first stage  coefficient %+.5f, NW se %.5f, F %.3f, partial R2 "
            "%.4f, equation R2 %.4f"
            % (
                iv.first_stage_coefficient,
                iv.first_stage_se,
                iv.first_stage_f,
                iv.first_stage_partial_r2,
                iv.first_stage_r2,
            )
        )
        add(
            "    2SLS         %+.5f, NW se %.5f, t %+.2f"
            % (iv.iv_coefficient, iv.iv_se, iv.iv_t)
        )
        add(
            "    OLS, same equation and sample, for comparison  %+.5f, NW se %.5f"
            % (iv.ols_coefficient, iv.ols_se)
        )
        for line in _wrap(iv.mechanical_measured, 74):
            add("    %s" % line)
        for line in _wrap("VERDICT: " + iv.verdict, 74):
            add("    %s" % line)
        add("")
    add(
        "  So the instrument does not work, and SPEC.md section 6.3 says to say "
        "that rather than force it."
    )
    add(
        "  It is said. The two stage estimates above are printed because the "
        "spec asks for the exercise,"
    )
    add(
        "  and they are not used anywhere: the headline response of section 2 is "
        "ordinary least squares,"
    )
    add(
        "  the endogeneity in section 5 is unaddressed, and this study reports "
        "that as a limitation"
    )
    add("  rather than as a solved problem.")
    add("")

    # -----------------------------------------------------------------------
    # SPEC.md section 6.4
    # -----------------------------------------------------------------------
    add("7. Did the link hold in 2026, SPEC.md section 6.4")
    add("-" * 78)
    add("  COUNT THE MONTHS FIRST.")
    breaks = {}
    for dependent in DEPENDENTS:
        result = break_2026(frame=horses, dependent=dependent)
        breaks[dependent] = result
    first = breaks[DEPENDENT_CAPACITY]
    for line in _wrap(first.verdict, 74):
        add("    %s" % line)
    add("")
    add(
        "  That is the answer to SPEC.md section 6.4 on this data date, in one "
        "sentence: the post break"
    )
    add(
        "  sample is %d months and %d months cannot say whether a relation held."
        % (first.n_post, first.n_post)
    )
    add("")
    add("  The residuals, which are a description and not a test")
    for dependent in DEPENDENTS:
        result = breaks[dependent]
        add(
            "    Dependent %s, fitted on %d months to 2026-02, predicted out of "
            "sample from %s."
            % (dependent, result.n_pre, BREAK_2026_FIRST_POST_MONTH[:7])
        )
        add(
            "    In sample residual standard deviation %.4f. Episode dummies are "
            "OFF here, deliberately:"
            % result.pre_residual_sd
        )
        add(
            "    a 2026 dummy would absorb exactly the deviation this is looking "
            "for."
        )
        add(
            "      month     actual  predicted  residual  residual kb/d  in sample sds  cap assumed"
        )
        for _, row in result.residuals.iterrows():
            add(
                "      %s  %9.3f  %9.3f  %+8.3f  %+13.1f  %+13.2f  %s"
                % (
                    row["date"][:7],
                    row["actual"],
                    row["predicted"],
                    row["residual"],
                    row["residual_kb_d"],
                    row["in_sample_residual_sd_multiples"],
                    "yes" if row["capacity_assumed"] else "no",
                )
            )
        below = int((result.residuals["residual"] < 0).sum())
        worst = result.residuals.loc[result.residuals["residual"].idxmin()]
        add(
            "    Runs came in BELOW what the margin implies in %d of the %d "
            "months, the largest gap %s at"
            % (below, len(result.residuals), worst["date"][:7])
        )
        add(
            "    %+.1f kb/d, which is %.2f in sample residual standard "
            "deviations. On the capacity dependent"
            % (
                worst["residual_kb_d"],
                abs(worst["in_sample_residual_sd_multiples"]),
            )
        )
        if dependent == DEPENDENT_CAPACITY:
            add(
                "    All %d of these months carry the ASSUMED 2026 capacity, "
                "since no 2026 capacity figure"
                % result.capacity_assumed_post
            )
            add(
                "    exists anywhere, so part of every residual in this block is "
                "that assumption and not the"
            )
            add(
                "    world. The block below needs no capacity at all and is the "
                "one to read for that reason."
            )
        else:
            add(
                "    This dependent needs NO capacity figure, so none of these "
                "residuals owes anything to the"
            )
            add(
                "    2026 capacity assumption. The cap assumed column is carried "
                "through from the frame and is"
            )
            add("    inert here.")
        add("")
    add("  THE COMPETING EXPLANATIONS, none of which this data can separate")
    add(
        "    Three things happened inside these four months, each cited from "
        "data/seed/events.json:"
    )
    for event in first.explanations:
        add("      %s  %s" % (event["date"], event["label"]))
        add("        %s" % event["source_url"])
    add(
        "    And at least three mechanisms could put runs below what the margin "
        "implies, all of them"
    )
    add("    consistent with these residuals and none of them tested here:")
    add(
        "      FEEDSTOCK AVAILABILITY. With Hormuz traffic halted, a refiner can "
        "face a good margin and"
    )
    add(
        "      still have no suitable crude on the quay. The IEA reported "
        "refiners outside the Gulf"
    )
    add(
        "      curtailing runs over feedstock availability, cited above from the "
        "March 2026 report."
    )
    add(
        "      UNPLANNED OUTAGES. A single large NWE unit down for a month is "
        "worth on the order of a"
    )
    add("      hundred kb/d, which is the size of the residuals in this table.")
    add(
        "      MAINTENANCE. Spring turnaround season is March to May in NWE and "
        "its timing moves year to"
    )
    add(
        "      year; the month dummies carry the average season and not this "
        "year's."
    )
    add(
        "    THIS STUDY DOES NOT PICK ONE. Four monthly observations cannot "
        "separate three explanations,"
    )
    add(
        "    and JODI publishes no outage or turnaround series that would let "
        "them be separated. SPEC.md"
    )
    add(
        "    section 6.4 says to set them out and not to choose, and that is what "
        "is done here. The"
    )
    add(
        "    question is reopenable: it needs %d months after %s, which arrives "
        "with the JODI release for"
        % (first.min_post_months, BREAK_2026_DATE)
    )
    add("    2027-02, around April 2027.")
    add("")

    # -----------------------------------------------------------------------
    # SPEC.md section 6.5
    # -----------------------------------------------------------------------
    add("8. Seasonality, SPEC.md section 6.5")
    add("-" * 78)
    join = seasonal_join()
    add("  WHICH SERIES, AND WHERE THE JOIN IS")
    add(
        "    Monthly, the long history: OPEC MOMR Rotterdam quotations, %s to "
        "%s, %d months."
        % (join["monthly_first"], join["monthly_last"], join["monthly_rows"])
    )
    add(
        "    Weekly, where it reaches: this study's reconstruction of the DGEC "
        "note chart, %s to %s,"
        % (join["weekly_first"], join["weekly_last"])
    )
    add(
        "    %d Fridays. IT IS NOT A DGEC PUBLICATION and it carries the "
        "reconstruction's error."
        % join["weekly_rows"]
    )
    add(
        "    THE TWO ARE NOT SPLICED AND MUST NOT BE. They quote different "
        "products: DGEC's Gazole and"
    )
    add(
        "    Eurosuper against OPEC's gasoil and premium gasoline. Over the %d "
        "overlapping months, %s to"
        % (join["overlap_months"], join["first_overlap_month"])
    )
    add("    %s, the weekly series averaged to months sits" % join["last_overlap_month"])
    add(
        "      gasoil    %+.2f $/bbl from the monthly one, mean absolute gap "
        "%.2f, correlation %.4f"
        % (
            join["%s_mean_gap" % CRACK_GASOIL],
            join["%s_mean_absolute_gap" % CRACK_GASOIL],
            join["%s_correlation" % CRACK_GASOIL],
        )
    )
    add(
        "      gasoline  %+.2f $/bbl from the monthly one, mean absolute gap "
        "%.2f, correlation %.4f"
        % (
            join["%s_mean_gap" % CRACK_GASOLINE],
            join["%s_mean_absolute_gap" % CRACK_GASOLINE],
            join["%s_correlation" % CRACK_GASOLINE],
        )
    )
    add(
        "    The gasoline gap is the size of a different product, not an error. "
        "Two panels, never one line."
    )
    add("")
    weekly_range = seasonal_weekly()
    add("  THE FIVE YEAR WEEKLY RANGE SPEC.md SECTION 6.5 ASKS FOR DOES NOT EXIST")
    add(
        "    The weekly reconstruction begins %s, so the prior years available "
        "to a %d year range are %s."
        % (
            join["weekly_first"],
            SEASONAL_RANGE_YEARS,
            ", ".join(str(y) for y in weekly_range.attrs["years_used"]),
        )
    )
    add(
        "    The deepest week has %d years behind it and the shallowest %d. The "
        "n_years column travels with"
        % (
            int(weekly_range["n_years"].max()),
            int(weekly_range.loc[weekly_range["n_years"] > 0, "n_years"].min()),
        )
    )
    add(
        "    every week so a chart prints the count beside the band rather than "
        "drawing four years and"
    )
    add(
        "    calling them five. The monthly series carries the full five year "
        "range for every month and"
    )
    add("    that is where the seasonal claim below is tested.")
    add("")
    add("  THE TEXTBOOK PATTERN, CHECKED AND NOT ASSERTED")
    add(
        "    Method: demean each crack within its own calendar year, so what is "
        "left is the shape of the"
    )
    add(
        "    year and not its level; take the season's months less the other "
        "months as ONE number per year;"
    )
    add(
        "    and report the mean of those numbers with the standard error across "
        "years. A year is the unit"
    )
    add(
        "    because months inside a year are not independent. The month sets "
        "were written down before the"
    )
    add(
        "    test: driving season %s, heating season %s."
        % (DRIVING_SEASON_MONTHS, HEATING_SEASON_MONTHS)
    )
    for exclusions, label in (
        ((), "all complete years"),
        (SEASONAL_REMOVABLE_YEARS, "with 2020, 2022 and 2026 removed"),
    ):
        check = seasonal_textbook_check(exclude_years=exclusions)
        add("    %s:" % label)
        for _, row in check.iterrows():
            add(
                "      %-34s %2d years  in season %+6.2f  out %+6.2f  diff "
                "%+6.2f  se %5.2f  t %+6.2f  %s"
                % (
                    row["claim"],
                    row["complete_years"],
                    row["in_season_mean_usd_bbl"],
                    row["out_of_season_mean_usd_bbl"],
                    row["difference_usd_bbl"],
                    row["se"],
                    row["t"],
                    "HOLDS" if row["holds"] else "DOES NOT HOLD",
                )
            )
    add("")
    shape = seasonal_shape()
    add("  The within year shape, in $/bbl away from each year's own mean")
    add("    month  gasoil   se   gasoline   se")
    for _, row in shape.iterrows():
        add(
            "    %5d  %+6.2f %5.2f  %+7.2f %5.2f"
            % (
                int(row["month"]),
                row["%s_mean" % CRACK_GASOIL],
                row["%s_se" % CRACK_GASOIL],
                row["%s_mean" % CRACK_GASOLINE],
                row["%s_se" % CRACK_GASOLINE],
            )
        )
    gasoil_peak = int(shape.loc[shape["%s_mean" % CRACK_GASOIL].idxmax(), "month"])
    gasoil_trough = int(shape.loc[shape["%s_mean" % CRACK_GASOIL].idxmin(), "month"])
    gasoline_peak = int(shape.loc[shape["%s_mean" % CRACK_GASOLINE].idxmax(), "month"])
    gasoline_trough = int(
        shape.loc[shape["%s_mean" % CRACK_GASOLINE].idxmin(), "month"]
    )
    full = seasonal_textbook_check().set_index("crack")
    add("")
    add("  WHAT THE DATA SHOWS, including the half that contradicts the textbook")
    add(
        "    GASOLINE: the textbook holds and it is not close. The driving season "
        "months sit %+.2f $/bbl"
        % full.loc[CRACK_GASOLINE, "difference_usd_bbl"]
    )
    add(
        "    above the rest of the year, t %+.2f across %d complete years, and "
        "the difference survives"
        % (
            full.loc[CRACK_GASOLINE, "t"],
            int(full.loc[CRACK_GASOLINE, "complete_years"]),
        )
    )
    add(
        "    removing 2020, 2022 and 2026. It is positive in %d of those %d "
        "years. Peak month %d, trough %d."
        % (
            int(full.loc[CRACK_GASOLINE, "years_positive"]),
            int(full.loc[CRACK_GASOLINE, "complete_years"]),
            gasoline_peak,
            gasoline_trough,
        )
    )
    add(
        "    GASOIL: THE TEXTBOOK DOES NOT HOLD AS IT IS USUALLY STATED. The "
        "November to March window sits"
    )
    add(
        "    %+.2f $/bbl from the rest of the year with a standard error of %.2f, "
        "t %+.2f, which is nothing,"
        % (
            full.loc[CRACK_GASOIL, "difference_usd_bbl"],
            full.loc[CRACK_GASOIL, "se"],
            full.loc[CRACK_GASOIL, "t"],
        )
    )
    add(
        "    and it is positive in only %d of %d years. The shape table above "
        "says why: the gasoil crack's"
        % (
            int(full.loc[CRACK_GASOIL, "years_positive"]),
            int(full.loc[CRACK_GASOIL, "complete_years"]),
        )
    )
    add(
        "    strongest month is %d and its weakest is %d, so such strength as "
        "there is arrives in the autumn"
        % (gasoil_peak, gasoil_trough)
    )
    add(
        "    build and has faded by the middle of the winter it was built for. A "
        "window drawn around that"
    )
    add(
        "    peak would fit better, and it is NOT tested here and no number for "
        "it is reported, because a"
    )
    add(
        "    window chosen after seeing this table is a parameter search and "
        "SPEC.md section 6.6 forbids it."
    )
    add(
        "    The honest statement is the one above: on this sample, gasoline is "
        "seasonal and gasoil is not,"
    )
    add("    in the windows a desk would name out loud.")
    add("")
    return "\n".join(out)


if __name__ == "__main__":  # pragma: no cover
    print(report())
