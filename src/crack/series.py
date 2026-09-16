"""The plumbing. Committed caches in, aligned series out, engine does the maths.

crack.engine takes numbers and returns numbers and knows nothing about files.
This module is the other half: it opens data/cache, lines the series up, and
hands the engine dated observations. Everything with a date on it lives here,
and every arithmetic decision lives there.

The division is not tidiness. SPEC.md section 7.1 makes src/engine.js prove it
agrees with crack.engine to 1e-9, and a browser cannot open a CSV, so anything
the engine does has to be expressible without one. Whenever you are about to add
arithmetic here, check whether it belongs in engine.py instead. Resampling,
rolling windows, joining on dates and choosing which cache answers a question
belong here. Cracks, margins, breakevens and ranks do not.

What the sample is, and why
---------------------------
THE STUDY STARTS IN 2001, which is the owner's decision at the Gate 1 approval.
The OPEC MOMR Rotterdam product table runs from 2000-10 and covers the 2020
collapse, so the crack series uses the whole of it rather than starting in 2015
to match the official margin. The consequence has to be said rather than
smoothed over: DGEC's published MBR begins in 2015-01, so every series in this
module that involves the official margin, which includes the margin after gas
and the whole decomposition, begins in 2015-01 too. Before that date this study
has cracks and no margin. It says so, on the page and in the manifest, and it
does not extend the official series backwards.

The crude leg
-------------
The OPEC table is Rotterdam PRODUCTS only, so the crude leg comes from FRED
DCOILBRENTEU, monthly averaged under config.MONTHLY_MEAN_RULE. The two are
different assessments, Argus barges against EIA Europe Brent spot, and they are
averaged over the same calendar month, which is what SPEC.md section 4.2
requires: the same date and the same averaging window. It is not the same as
DGEC's own Brent date, and where DGEC's figure exists, 2015 onward,
brent_monthly can return that instead so the difference is visible rather than
assumed away.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from crack import config, engine
from crack.sources import base

__all__ = [
    "load",
    "brent_monthly",
    "eurusd_monthly",
    "gas_monthly",
    "opec_monthly_cracks",
    "dgec_weekly_cracks",
    "jodi_yields",
    "margin_after_gas_monthly",
    "net_of_gas_margin_inputs",
    "DGEC_VOLUME_YIELDS",
    "FUEL_OIL_TRIANGULATION_BASES",
    "cracks_for_month",
    "DGEC_UNATTRIBUTED_SLATE_LINES",
    "decomposition_for_month",
    "replication_attempts",
    "LatestView",
    "latest_view",
]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load(name: str, *, directory: str = "cache") -> pd.DataFrame:
    """One committed cache, by series name, or a loud failure.

    crack.sources.base.read_cache returns None for a file that is not there,
    which is right for a refresh that has to keep going. Here a missing cache
    means the analysis cannot run, so it raises and names the series.
    """
    frame = base.read_cache(name, directory=directory)
    if frame is None:
        raise FileNotFoundError(
            "no cache for %r. Run 'make data' to fetch it, or 'make data-offline' "
            "if you believe it is already committed" % (name,)
        )
    return frame


def _month_floor(dates: pd.Series) -> pd.Series:
    return pd.to_datetime(dates).dt.to_period("M").dt.to_timestamp()


def _iso(day: pd.Timestamp) -> str:
    return pd.Timestamp(day).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# The monthly inputs
# ---------------------------------------------------------------------------


def brent_monthly(source: str = "fred") -> pd.DataFrame:
    """Brent in $/bbl by month, under config.MONTHLY_MEAN_RULE.

    Args:
        source: "fred" for the monthly mean of FRED DCOILBRENTEU, which covers
            1987 onward and is the only crude series that spans the OPEC product
            table; "eia" for the same numbers taken straight from EIA, whose
            licence carries no doubt; "dgec" for DGEC's own published monthly
            Brent, which starts in 2015-01 and is the leg the MBR was computed
            against.

    Returns:
        date, brent_usd_bbl, observations. The observation count travels with
        the value so a thin month can be reported as thin, which is what
        config.monthly_mean exists for.
    """
    if source == "dgec":
        frame = load("dgec_brent_monthly")
        out = pd.DataFrame(
            {
                "date": _month_floor(frame["date"]),
                "brent_usd_bbl": frame["brent_usd_bbl"].astype(float),
                # DGEC publishes a monthly figure, not a set of days, so the
                # count is not available and is NOT invented as 30.
                "observations": np.nan,
            }
        )
        return out.sort_values("date").reset_index(drop=True)

    name = {"fred": "fred_brent_daily", "eia": "eia_brent_daily"}[source]
    daily = load(name)
    monthly = config.monthly_mean(daily["date"], daily["brent_usd_bbl"])
    return pd.DataFrame(
        {
            "date": monthly["month"],
            "brent_usd_bbl": monthly["value"],
            "observations": monthly["observations"],
        }
    )


def eurusd_monthly() -> pd.DataFrame:
    """US dollars per euro by month, same averaging rule as Brent.

    Needed only for the TTF path of SPEC.md section 4.4. The gas series this
    study runs on is already in $/MMBtu, so this is the exchange rate for the
    Model view's TTF slider and for the October 2022 triangulation, not a line
    in the published margin.
    """
    daily = load("fred_eurusd_daily")
    monthly = config.monthly_mean(daily["date"], daily["eurusd"])
    return pd.DataFrame(
        {
            "date": monthly["month"],
            "eurusd": monthly["value"],
            "observations": monthly["observations"],
        }
    )


def gas_monthly() -> pd.DataFrame:
    """European gas in $/MMBtu by month, World Bank pink sheet.

    ALREADY IN DOLLARS PER MILLION BTU. Recon 04 section 4.1: from 2015-04 the
    series is TTF by the publisher's own definition and is published in
    $/MMBtu, so nothing here multiplies by an exchange rate or divides by
    3.412142. The EUR/MWh chain of SPEC.md section 4.4 is the TTF path and it is
    reached through engine.gas_from_ttf, which the Model view uses and this
    function does not.
    """
    frame = load("worldbank_gas_europe_monthly")
    return pd.DataFrame(
        {
            "date": _month_floor(frame["date"]),
            "gas_usd_mmbtu": frame["gas_usd_mmbtu"].astype(float),
        }
    ).sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# SPEC.md section 4.2, the crack series
# ---------------------------------------------------------------------------

#: The OPEC MOMR Rotterdam columns this study cracks, and the label the source
#: itself uses for each. SPEC.md section 4.2: follow the source's own labels.
#: The gasoline column is premium unleaded assessed by Argus, which is not
#: Eurobob blendstock and is not DGEC's Eurosuper either, and the site says so
#: rather than calling any of them "gasoline" and hoping.
OPEC_PRODUCT_COLUMNS: Mapping[str, str] = {
    "gasoil": "gasoil_usd_bbl",
    "gasoline": "premium_gasoline_usd_bbl",
}


def opec_monthly_cracks(brent_source: str = "fred") -> pd.DataFrame:
    """Monthly Rotterdam cracks in $/bbl, 2000-10 onward. The headline series.

    THE OPEC TABLE IS ALREADY IN DOLLARS PER BARREL, so no conversion factor
    touches the product leg and engine.crack records that as BASIS_DIRECT. The
    same function handles the DGEC $/t path, where a factor is required, and the
    two are told apart by the unit on the quotation rather than by which call
    site built it.

    Every row goes through engine.crack with both legs as dated monthly
    quotations, so the alignment rule of SPEC.md section 4.2 is enforced per
    observation rather than assumed from the join. A month where Brent is
    missing gives a NaN crack and keeps its row.

    Returns:
        date, brent_usd_bbl, crack_gasoil_usd_bbl, crack_gasoline_usd_bbl,
        gasoil_usd_bbl, gasoline_usd_bbl, gasoline_spec, gasoil_spec,
        n_issues. The specification columns come from the cache and they matter:
        the OPEC gasoil row changes specification over the sample and the
        manifest carries the break.
    """
    products = load("opec_rotterdam_products_monthly")
    products["date"] = _month_floor(products["date"])
    brent = brent_monthly(brent_source)

    merged = products.merge(brent[["date", "brent_usd_bbl"]], on="date", how="left")

    rows = []
    for _, row in merged.iterrows():
        day = _iso(row["date"])
        crude = engine.Quote(
            float(row["brent_usd_bbl"]),
            engine.USD_PER_BBL,
            day,
            engine.MONTHLY,
            "Brent, FRED DCOILBRENTEU monthly mean"
            if brent_source == "fred"
            else "Brent",
        )
        values = {}
        for product, column in OPEC_PRODUCT_COLUMNS.items():
            quote = engine.Quote(
                float(row[column]),
                engine.USD_PER_BBL,
                day,
                engine.MONTHLY,
                "OPEC MOMR Rotterdam %s" % product,
            )
            values[product] = engine.crack(quote, crude).value
        rows.append(
            {
                "date": row["date"],
                "brent_usd_bbl": float(row["brent_usd_bbl"]),
                "gasoil_usd_bbl": float(row[OPEC_PRODUCT_COLUMNS["gasoil"]]),
                "gasoline_usd_bbl": float(row[OPEC_PRODUCT_COLUMNS["gasoline"]]),
                "crack_gasoil_usd_bbl": values["gasoil"],
                "crack_gasoline_usd_bbl": values["gasoline"],
                "gasoil_spec": row.get("gasoil_spec"),
                "gasoline_spec": row.get("gasoline_spec"),
                "n_issues": row.get("n_issues"),
            }
        )
    return pd.DataFrame(rows)


#: The reconstructed weekly quotation columns this study cracks, keyed by the
#: same product name as config.PRODUCT_BBL_PER_T, with the source's own label for
#: each. SPEC.md section 4.2: DGEC's "Eurosuper" is finished premium gasoline and
#: not Eurobob blendstock, so the label travels with the quote and the site
#: prints what the ministry called it.
DGEC_WEEKLY_COLUMNS: Mapping[str, tuple] = {
    "gasoil": ("gazole_usd_t", "Gazole"),
    "gasoline": ("eurosuper_usd_t", "Eurosuper"),
}


def dgec_weekly_cracks(recompute: bool = True) -> pd.DataFrame:
    """Weekly Rotterdam cracks in $/bbl from the reconstructed DGEC quotations.

    The weekly layer the owner accepted at Gate 1. Both legs come from the same
    chart on the same page of the same note, so they share a date and a window
    by construction, and engine.crack checks it anyway.

    THE $/t PATH, which is the other half of SPEC.md section 4.2. The product
    leg divides by the ICE contract factor and the crude leg divides by
    config.DGEC_BBL_PER_T_BRENT_NOTE, which is 7.5 and not 7.45 and not 7.55.

    Args:
        recompute: True recomputes the cracks from
            dgec_note_reconstructed_weekly through the engine, which is what
            tests/test_engine.py compares against the committed derived cache.
            False simply reads dgec_note_reconstructed_cracks_weekly. The two
            agree, and the comparison is how we know the engine and the Gate 1
            adapter implement the same definition.

    Every value inherits the reconstruction. The measured out of sample error is
    0.17 to 0.44 $/t mean absolute, about 0.02 to 0.06 $/bbl on the gasoil leg,
    and the series must never be presented as a DGEC publication.
    """
    if not recompute:
        frame = load("dgec_note_reconstructed_cracks_weekly")
        frame["date"] = pd.to_datetime(frame["date"])
        return frame

    quotes = load("dgec_note_reconstructed_weekly")
    rows = []
    for _, row in quotes.iterrows():
        day = _iso(row["date"])
        crude = engine.Quote(
            float(row["brent_date_usd_t"]),
            engine.USD_PER_T,
            day,
            engine.WEEKLY,
            "Brent date, DGEC note chart",
        )
        # One key per product picks the column, the source's own label and the
        # conversion factor together. Gate 2 self audit, finding 2: these were
        # three hand typed lookups per leg, and the audit put the gasoil factor
        # on the gasoline leg, worth 19 $/bbl on a week, with one test firing
        # and only by the accident of Gate 1 having committed a derived cache.
        cracks = {
            product: engine.crack(
                engine.Quote(
                    float(row[column]),
                    engine.USD_PER_T,
                    day,
                    engine.WEEKLY,
                    label,
                ),
                crude,
                product_bbl_per_t=config.PRODUCT_BBL_PER_T[product],
                brent_bbl_per_t=config.DGEC_BBL_PER_T_BRENT_NOTE,
            )
            for product, (column, label) in sorted(DGEC_WEEKLY_COLUMNS.items())
        }
        rows.append(
            {
                "date": row["date"],
                "brent_usd_bbl": cracks["gasoil"].brent_usd_bbl,
                "crack_gasoil_usd_bbl": cracks["gasoil"].value,
                "crack_gasoline_usd_bbl": cracks["gasoline"].value,
                "evidence_class": row.get("evidence_class"),
                "cross_checked": row.get("cross_checked"),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# SPEC.md section 4.3 layer 4, observed yields
# ---------------------------------------------------------------------------

#: JODI product columns for the five country aggregate, and the name each one
#: carries in this study. JETKERO is deliberately absent: recon 03 section 1.5
#: found TOTPRODS excludes it while KEROSENE contains it, so summing both double
#: counts jet. The five below are disjoint.
JODI_PRODUCT_COLUMNS: Mapping[str, str] = {
    "gasoline": "nwe5_refgrout_gasoline_kbd",
    "gasoil": "nwe5_refgrout_gasdies_kbd",
    "kerosene": "nwe5_refgrout_kerosene_kbd",
    "resfuel": "nwe5_refgrout_resfuel_kbd",
    "naphtha": "nwe5_refgrout_naphtha_kbd",
}

JODI_DENOMINATOR_COLUMNS: Mapping[str, str] = {
    config.YIELD_BASIS_CRUDE_INTAKE: "nwe5_refinobs_crudeoil_kbd",
    config.YIELD_BASIS_TOTAL_FEED: "nwe5_refinobs_totcrude_kbd",
}


def jodi_yields(
    basis: str = config.YIELD_BASIS_CRUDE_INTAKE,
    window: int = config.ROLLING_YIELD_WINDOW_MONTHS,
) -> pd.DataFrame:
    """NWE observed yields, twelve month rolling, on a named denominator.

    SPEC.md section 4.3 layer 4. The rolling window is applied to the numerator
    and the denominator separately and the yield is the ratio of the two rolling
    means, which is the volume weighted yield over the year rather than the mean
    of twelve monthly ratios. The two differ when intake moves, and the weighted
    one is the one that answers "what did this refinery system actually make per
    barrel it ran".

    BOTH BASES EXIST AND NEITHER IS THE DEFAULT IN DISGUISE. Recon 03 section
    1.8: output over crude intake sums to 1.13 to 1.16 because the numerator is
    gross output from all feed, and output over total feed sums to 1.01 to 1.03
    but starts only in 2009. The sum of the lines is returned as a column so the
    inflation is visible in the data rather than in a footnote.

    Returns:
        date, one column per product, total, denominator_kbd, basis.
    """
    if basis not in JODI_DENOMINATOR_COLUMNS:
        raise ValueError(
            "jodi_yields builds on a JODI denominator, so basis is %s. For %r, "
            "take the crude intake frame and normalise it, which relabels it as "
            "a share of output"
            % (
                " or ".join(sorted(JODI_DENOMINATOR_COLUMNS)),
                config.YIELD_BASIS_NORMALISED,
            )
        )

    output = load("jodi_nwe_refinery_output_monthly")
    intake = load("jodi_nwe_refinery_intake_monthly")
    output["date"] = _month_floor(output["date"])
    intake["date"] = _month_floor(intake["date"])

    denominator_column = JODI_DENOMINATOR_COLUMNS[basis]
    merged = output.merge(
        intake[["date", denominator_column]], on="date", how="inner"
    ).sort_values("date")

    rolled = {"date": merged["date"].to_numpy()}
    denominator = (
        merged[denominator_column]
        .astype(float)
        .rolling(window, min_periods=window)
        .mean()
    )
    total = pd.Series(0.0, index=merged.index)
    for product, column in sorted(JODI_PRODUCT_COLUMNS.items()):
        numerator = (
            merged[column].astype(float).rolling(window, min_periods=window).mean()
        )
        values = numerator / denominator
        rolled[product] = values.to_numpy()
        total = total + values
    rolled["total"] = total.to_numpy()
    rolled["denominator_kbd"] = denominator.to_numpy()

    # JODI's own total product output over the same denominator, reported
    # separately and deliberately NOT added into the yield vector. It is the
    # ratio recon 03 section 1.8 measured at 1.13 to 1.16 on crude intake and
    # 1.01 to 1.03 on total feed, and it is the number that says how much of the
    # inflation is the denominator rather than the product mix. TOTPRODS
    # excludes JETKERO, recon 03 section 1.5, so it is not the sum of the five
    # product lines above and the two are never compared as if it were.
    totprods = (
        merged["nwe5_refgrout_totprods_kbd"]
        .astype(float)
        .rolling(window, min_periods=window)
        .mean()
    )
    rolled["totprods_ratio"] = (totprods / denominator).to_numpy()

    frame = pd.DataFrame(rolled)
    frame["basis"] = basis
    return frame.reset_index(drop=True)


def latest_observed_yields(
    basis: str = config.YIELD_BASIS_CRUDE_INTAKE,
    window: int = config.ROLLING_YIELD_WINDOW_MONTHS,
) -> engine.ObservedYields:
    """The most recent complete twelve month yield vector, as an engine record."""
    frame = jodi_yields(basis, window)
    complete = frame[frame["total"].notna()]
    if complete.empty:
        raise ValueError("no complete %d month window in the JODI output" % window)
    row = complete.iloc[-1]
    return engine.observed_yields(
        {
            product: float(row[product]) * float(row["denominator_kbd"])
            for product in sorted(JODI_PRODUCT_COLUMNS)
        },
        float(row["denominator_kbd"]),
        basis,
    )


# ---------------------------------------------------------------------------
# SPEC.md section 4.4, the margin after gas
# ---------------------------------------------------------------------------


def margin_after_gas_monthly(
    gas_intensity_mmbtu_per_bbl: float = config.GAS_INTENSITY_MMBTU_PER_BBL,
    other_variable_cost_usd_bbl: float = config.OTHER_VARIABLE_COST_USD_BBL,
) -> pd.DataFrame:
    """The official margin, the gas wedge beside it, and what is left. 2015-01 on.

    NO GAS COST IS SUBTRACTED HERE, and that is the correction the Gate 2 self
    audit forced. DGEC's methodology note, section 3, computes the MBR by
    subtracting from revenues "les couts d'achat du Brent date FAB et du gaz
    naturel CAF". Its table 1 carries "Gaz naturel 1,0%" as an input yield, it
    says the refinery buys gas to cover its internal fuel and hydrogen needs, it
    is gross only of costs "autres que ceux energetiques", and the indicator is
    named a margin "sur couts energetiques". The published MBR is therefore
    ALREADY NET OF PURCHASED GAS.

    SPEC.md section 4.4 writes margin_after_gas = margin_gross - gas_cost -
    other_variable_cost. That formula is right for a margin this study builds
    itself out of cracks and yields, and wrong for this one. An earlier version
    of this function applied it here anyway and charged the barrel for gas
    twice, worth about 1.4 $/bbl in the latest month and over 4 $/bbl in 2022,
    at the exact number the landing view opens on. The margin now travels with
    its basis, engine.MARGIN_NET_OF_GAS, and engine.MarginInputs refuses a gas
    price on it, so the mistake is no longer expressible rather than merely
    fixed.

    The gas story survives, and is better. Instead of a deduction, the two
    intensities are priced at the same gas price and reported side by side:
    DGEC's own embedded assumption, 1.0 percent of the barrel's mass at the
    note's own 7.55 bbl/t, and this study's EIA derived intensity. The gap is
    the wedge. SPEC.md section 4.4's interest in "the gas wedge that opened in
    2022" is answered by that comparison, not by subtracting one from a figure
    that already contains the other.

    Layer 1 of SPEC.md section 4.3 is carried through untouched and never
    recomputed. The series starts in 2015-01 where DGEC's file starts, and the
    Gate 1 approval is explicit that where the official margin does not exist
    before 2015 this study says so rather than extending it.

    ONE IMPLEMENTATION, NOT TWO. The margin after gas used to be computed here
    in pandas and again in crack.engine.evaluate, the same three terms in two
    languages of the same language, with no test asking them to agree. That is
    the Gate 2 self audit's finding 3, and it was not hypothetical: a sign flip
    inside evaluate() moved the landing sentence's number by 76 $/bbl while this
    column carried on saying something else. So this function no longer does the
    arithmetic. It builds the same engine.MarginInputs the Model view and
    latest_view build, one per month, and takes margin_after_gas_usd_bbl off
    engine.evaluate. A margin that is wrong here is now wrong in the browser
    too, which is the only state worth having: one number, one place to fix.

    Returns:
        date, mbr_usd_bbl, gas_usd_mmbtu, embedded_gas_cost_usd_bbl,
        study_gas_cost_usd_bbl, gas_wedge_usd_bbl, margin_after_gas_usd_bbl,
        other_variable_cost_usd_bbl, margin_basis.

        There is deliberately no "gas_cost_usd_bbl" column any more. The name
        meant the thing that was being wrongly subtracted, and leaving it in
        place with a new meaning is how a corrected number goes back to being
        wrong. A caller that wants one must now choose which of the two it
        means.
    """
    mbr = load("dgec_mbr_monthly")
    mbr["date"] = _month_floor(mbr["date"])
    merged = mbr.merge(gas_monthly(), on="date", how="left").sort_values("date")

    gas_price = merged["gas_usd_mmbtu"].astype(float)
    embedded_cost = gas_price * config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL
    study_cost = gas_price * gas_intensity_mmbtu_per_bbl

    # The MBR arrives net of gas, so the only thing left to take off it is the
    # other variable cost, which SPEC.md section 4.4 defaults to zero and
    # labels. Carbon is out of scope and listed as a limitation, not folded in.
    # The whole published margin is the residual line, exactly as it is in
    # latest_view, because no product attribution exists without product
    # quotations and a residual is what SPEC.md section 4.3 layer 3 is for.
    after = [
        engine.evaluate(
            net_of_gas_margin_inputs(value, other_variable_cost_usd_bbl)
        ).margin_after_gas_usd_bbl
        for value in merged["mbr_usd_bbl"].astype(float)
    ]
    return pd.DataFrame(
        {
            "date": merged["date"].to_numpy(),
            "mbr_usd_bbl": merged["mbr_usd_bbl"].astype(float).to_numpy(),
            "gas_usd_mmbtu": gas_price.to_numpy(),
            "embedded_gas_cost_usd_bbl": embedded_cost.to_numpy(),
            "study_gas_cost_usd_bbl": study_cost.to_numpy(),
            "gas_wedge_usd_bbl": (study_cost - embedded_cost).to_numpy(),
            "margin_after_gas_usd_bbl": np.array(after, dtype=float),
            "other_variable_cost_usd_bbl": other_variable_cost_usd_bbl,
            "margin_basis": engine.MARGIN_NET_OF_GAS,
        }
    ).reset_index(drop=True)


def net_of_gas_margin_inputs(
    mbr_usd_bbl: float,
    other_variable_cost_usd_bbl: float = config.OTHER_VARIABLE_COST_USD_BBL,
    run_cut_threshold_usd_bbl: float | None = None,
) -> engine.MarginInputs:
    """DGEC's published MBR as engine inputs, on the basis that says it is net.

    One function, called from margin_after_gas_monthly and from latest_view, so
    that the monthly column and the landing sentence cannot be built two
    different ways. Gate 2 self audit, finding 3.

    No gas price and an intensity of exactly zero, both of which are the point:
    engine.MarginInputs raises GasDoubleCountError for any other combination on
    MARGIN_NET_OF_GAS, so the double charge this fixed is not expressible from
    here rather than merely absent.
    """
    return engine.MarginInputs(
        yields={},
        cracks={},
        residual_usd_bbl=mbr_usd_bbl,
        gas_intensity_mmbtu_per_bbl=0.0,
        other_variable_cost_usd_bbl=other_variable_cost_usd_bbl,
        run_cut_threshold_usd_bbl=run_cut_threshold_usd_bbl,
        margin_basis=engine.MARGIN_NET_OF_GAS,
    )


def trailing_window(
    frame: pd.DataFrame,
    column: str,
    upto: pd.Timestamp,
    months: int = config.PERCENTILE_WINDOW_MONTHS,
) -> Sequence[float]:
    """The trailing ten years of a monthly column, ending at and including upto.

    SPEC.md section 4.5's percentile_10y is "the rank of margin_after_gas within
    its trailing ten years", so the window is defined here, in months, and the
    ranking itself is engine.percentile_rank. A window that runs off the start
    of the data is shorter and says so through the observation count the engine
    returns, rather than being padded.
    """
    upto = pd.Timestamp(upto)
    start = upto - pd.DateOffset(months=months - 1)
    window = frame[(frame["date"] >= start) & (frame["date"] <= upto)]
    return [float(x) for x in window[column].to_numpy()]


# ---------------------------------------------------------------------------
# SPEC.md section 4.3 layer 3, the decomposition on real data
# ---------------------------------------------------------------------------

#: The two DGEC slate lines this study can put on a barrel basis, and nothing
#: else. A mass yield becomes a volumetric one only with a cited barrels per
#: tonne factor for the product, and this project holds exactly two: the ICE
#: gasoil factor and the ICE Eurobob factor. There is no cited factor here for
#: jet, for fioul domestique, for naphta, for propane or for butane, so those
#: lines are NOT converted, NOT estimated and NOT dropped quietly. They are
#: named in DGEC_UNATTRIBUTED_SLATE_LINES and their value lands on the residual,
#: which is what SPEC.md section 4.3 layer 3 requires.
#:
#: One approximation is taken and it is stated here rather than buried: the
#: EuroBOB mass yield of 12.0 percent is multiplied by a crack computed from a
#: DIFFERENT gasoline, the OPEC MOMR premium unleaded row or DGEC's Eurosuper,
#: because the EuroBOB quotation DGEC prices is not published anywhere this
#: project can reach. That mismatch is worth up to 13 $/bbl on the gasoline
#: crack alone, config.BBL_PER_T_GASOLINE records the measurement, and it is one
#: of the reasons the residual line is large.
#: ONE KEY PICKS BOTH THE MASS YIELD AND THE FACTOR. Gate 2 self audit, finding
#: 2: the two lines below used to name the DGEC slate line and the conversion
#: factor separately, by hand, and putting BBL_PER_T_GASOIL on the gasoline line
#: moved October 2022's gasoline contribution by 0.61 $/bbl with 756 tests and
#: the parity validator all green. config.PRODUCT_BBL_PER_T and
#: config.DGEC_SLATE_LINE are keyed on the same product name, so the factor and
#: the yield can no longer be taken from different products without renaming a
#: key in config, where the Units row of SPEC.md section 9 is looking.
#: tests/test_units.py checks the resulting numbers against the factors as well,
#: because a structure that makes an error unlikely is not a test that it did
#: not happen.
DGEC_VOLUME_YIELDS: Mapping[str, float] = {
    product: engine.mass_yield_to_volume_yield(
        config.DGEC_MASS_YIELDS[config.DGEC_SLATE_LINE[product]],
        config.PRODUCT_BBL_PER_T[product],
        config.DGEC_BBL_PER_T_BRENT_MARGIN,
    )
    for product in sorted(config.PRODUCT_BBL_PER_T)
}

#: Everything on DGEC's slate this decomposition cannot price, by the slate's
#: own names. Together they are 48.5 percent of the tonne, so the residual is
#: expected to be large and a small residual would be the surprising result.
DGEC_UNATTRIBUTED_SLATE_LINES: Sequence[str] = (
    "butane",
    "carbureacteur",
    "essence_export",
    "fioul_lourd_1pct",
    "fod",
    "naphta",
    "propane",
    "soufre",
)


def cracks_for_month(month: str) -> Mapping[str, float]:
    """The two priced Rotterdam cracks for one month, through engine.crack_values.

    Split out of decomposition_for_month so that a caller who needs the cracks
    themselves can have them instead of recovering them by dividing a
    contribution by the yield that produced it. Gate 2 self audit, finding 16:
    that recovery multiplied and then divided by the same number and would have
    divided by zero the day a slate line came out at a zero yield.

    Every crack goes through engine.crack_values, which is where SPEC.md section
    4.2's alignment rule is enforced ACROSS cracks rather than within one, so no
    caller reaches the decomposition on a set of cracks that do not share a date
    and a window.

    Raises:
        KeyError: when the month has no OPEC Rotterdam quotations. The MOMR
            issues for April to September 2026 are not in the Internet Archive
            and the manifest records the hole.
    """
    stamp = pd.Timestamp(month if len(month) > 7 else month + "-01").to_period("M")
    cracks = opec_monthly_cracks()
    cracks["period"] = cracks["date"].dt.to_period("M")
    crack_row = cracks[cracks["period"] == stamp]
    if crack_row.empty:
        raise KeyError("no OPEC Rotterdam quotations for %s" % stamp)

    day = _iso(crack_row["date"].iloc[0])
    crude = engine.Quote(
        float(crack_row["brent_usd_bbl"].iloc[0]),
        engine.USD_PER_BBL,
        day,
        engine.MONTHLY,
        "Brent",
    )
    return engine.crack_values(
        {
            "gasoil": engine.crack(
                engine.Quote(
                    float(crack_row["gasoil_usd_bbl"].iloc[0]),
                    engine.USD_PER_BBL,
                    day,
                    engine.MONTHLY,
                    "OPEC MOMR Rotterdam gasoil",
                ),
                crude,
            ),
            "gasoline": engine.crack(
                engine.Quote(
                    float(crack_row["gasoline_usd_bbl"].iloc[0]),
                    engine.USD_PER_BBL,
                    day,
                    engine.MONTHLY,
                    "OPEC MOMR Rotterdam premium gasoline",
                ),
                crude,
            ),
        }
    )


def decomposition_for_month(month: str) -> engine.Decomposition:
    """Take one month's published MBR apart into product contributions.

    TWO BRENTS MEET HERE AND THE DIFFERENCE LANDS ON THE RESIDUAL. The official
    margin was computed by DGEC against DGEC's own monthly Brent date, and the
    cracks come from the OPEC Rotterdam table against the FRED DCOILBRENTEU
    monthly mean, because that is the only crude series that spans the whole
    product table. Both legs of every crack share a date and a window, so
    SPEC.md section 4.2 is satisfied, but the margin and the cracks do not share
    a crude assessment. Gate 2 self audit, finding 15 measured what that is
    worth over the 140 months where both exist: the mean gap between the two
    Brents is 0.003 $/bbl, the worst is 0.2649 $/bbl in August 2016, and at the
    0.4679 volume yield this decomposition covers, the worst effect on the
    attributed total is 0.1239 $/bbl. It is small, it is silent, and it is on
    the Method view rather than nowhere. brent_monthly("dgec") is the other
    choice and it would shorten the crack series to 2015.

    Args:
        month: 'YYYY-MM' or 'YYYY-MM-DD'. Anything inside the month resolves to
            the month.

    Raises:
        KeyError: when the month has no published MBR, which is every month
            before 2015-01 and any month the file has not reached yet. The
            error says which, because "no margin before 2015" is a fact about
            the source and not a failure of this code.
    """
    stamp = pd.Timestamp(month if len(month) > 7 else month + "-01").to_period("M")
    margin = margin_after_gas_monthly()
    margin["period"] = margin["date"].dt.to_period("M")
    row = margin[margin["period"] == stamp]
    if row.empty:
        raise KeyError(
            "no published MBR for %s. DGEC's series starts 2015-01 and ends %s, "
            "and this study does not extend it in either direction"
            % (stamp, margin["date"].iloc[-1].date())
        )

    return engine.decompose_official(
        float(row["mbr_usd_bbl"].iloc[0]),
        DGEC_VOLUME_YIELDS,
        cracks_for_month(month),
        unattributed_products=DGEC_UNATTRIBUTED_SLATE_LINES,
    )


# ---------------------------------------------------------------------------
# SPEC.md section 4.3 layer 3 again, from the ministry's own monthly quotations
# ---------------------------------------------------------------------------
#
# GATE 4. The decomposition above prices the margin with OPEC MOMR cracks, which
# stop at 2026-02, so the landing month could not be split and the Gate 4 design
# plan built a waterfall for February beside an August block with its product
# rows empty. That premise was false. The ministry's weekly note of 4 September
# 2026 prints FINAL August 2026 monthly averages in $/t for Eurosuper, Gazole,
# Fioul domestique, Jet and Fioul lourd TBTS, and Brent date, and they are in
# data/cache/dgec_note_printed_monthly.csv with provisional False. That is the
# same ministry, the same month and the same Reuters basis as the MBR the
# decomposition explains, which is strictly better than a second publisher's
# February, and it removes the month mixing from the landing sentence.
#
# THE CRUDE LEG is DGEC's own published monthly Brent in $/bbl,
# data/cache/dgec_brent_monthly.csv, so no factor touches it. The note's own
# Brent date column in $/t is carried beside it, converted at
# config.DGEC_BBL_PER_T_BRENT_NOTE, as a diagnostic only.
#
# ADDITIVE. Nothing above changes: decomposition_for_month, DGEC_VOLUME_YIELDS
# and the parity fixture stay on the OPEC path, and the engine is generic over
# products, so five keys go through the same engine.decompose_official as two.

#: Printed monthly quotation column and the ministry's own label, per product.
#: The label is what the page prints, SPEC.md section 4.2.
DGEC_NOTE_MONTHLY_COLUMNS: Mapping[str, tuple] = {
    "gasoil": ("gazole_usd_t", "Gazole"),
    "gasoline": ("eurosuper_usd_t", "Eurosuper"),
    "jet": ("jet_usd_t", "Jet"),
    "heating_oil": ("fioul_domestique_usd_t", "Fioul domestique"),
    "fuel_oil_1pct": ("fioul_lourd_tbts_usd_t", "Fioul lourd TBTS (< 1%)"),
}

#: Volume yields for the five products, one key picking the mass yield and the
#: cited factor, exactly as DGEC_VOLUME_YIELDS does for two.
DGEC_NOTE_VOLUME_YIELDS: Mapping[str, float] = {
    product: engine.mass_yield_to_volume_yield(
        config.DGEC_MASS_YIELDS[config.DGEC_NOTE_SLATE_LINE[product]],
        config.DGEC_NOTE_PRODUCT_BBL_PER_T[product],
        config.DGEC_BBL_PER_T_BRENT_MARGIN,
    )
    for product in sorted(config.DGEC_NOTE_PRODUCT_BBL_PER_T)
}

#: What the note does not quote, by the slate's own names. 23.2 percent of the
#: tonne: propane 1.7, butane 1.2, naphta 8.2, essence export 11.9, sulphur 0.2.
#: Plus, and this is not a slate line, the method's gas purchase, freight and
#: insurance costs, which are inside the MBR and inside no crack.
DGEC_NOTE_UNATTRIBUTED_SLATE_LINES: Sequence[str] = (
    "butane",
    "essence_export",
    "naphta",
    "propane",
    "soufre",
)


def _note_month_row(month: str) -> pd.Series:
    stamp = pd.Timestamp(month if len(month) > 7 else month + "-01").to_period("M")
    printed = load("dgec_note_printed_monthly")
    printed["period"] = pd.to_datetime(printed["date"]).dt.to_period("M")
    row = printed[printed["period"] == stamp]
    if row.empty:
        raise KeyError("no monthly quotations printed by a DGEC note for %s" % stamp)
    row = row.iloc[0]
    provisional = str(row["provisional"]).strip().lower() == "true"
    if provisional:
        # A provisional quotation against a final margin mixes two vintages, and
        # SPEC.md section 13 says never to blend them silently. Refused, named.
        raise KeyError(
            "the monthly quotations for %s are provisional in the note of %s, "
            "and a provisional month is not decomposed" % (stamp, row["vintage"])
        )
    return row


def note_cracks_for_month(month: str) -> Mapping[str, engine.Crack]:
    """The five cracks from the ministry's final printed monthly averages.

    Every product leg is a monthly quotation in $/t with its cited factor, every
    crude leg is DGEC's published monthly Brent in $/bbl with the same date and
    window, and engine.crack checks the alignment per product.

    Raises:
        KeyError: when no note printed the month, when the printed month is
            still provisional, or when DGEC's Brent file has no value for it.
    """
    row = _note_month_row(month)
    day = _iso(pd.Timestamp(row["date"]))
    brent = brent_monthly("dgec")
    brent_row = brent[brent["date"] == pd.Timestamp(day)]
    if brent_row.empty or pd.isna(brent_row["brent_usd_bbl"].iloc[0]):
        raise KeyError("no DGEC monthly Brent for %s" % day[:7])
    crude = engine.Quote(
        float(brent_row["brent_usd_bbl"].iloc[0]),
        engine.USD_PER_BBL,
        day,
        engine.MONTHLY,
        "Brent date, DGEC monthly",
    )
    return {
        product: engine.crack(
            engine.Quote(
                float(row[column]), engine.USD_PER_T, day, engine.MONTHLY, label
            ),
            crude,
            product_bbl_per_t=config.DGEC_NOTE_PRODUCT_BBL_PER_T[product],
        )
        for product, (column, label) in sorted(DGEC_NOTE_MONTHLY_COLUMNS.items())
    }


def note_decomposition_for_month(month: str) -> engine.Decomposition:
    """One month's MBR taken apart with the ministry's own quotations.

    Raises:
        KeyError: no published MBR for the month, or no final printed
            quotations, or no DGEC Brent. Each says which.
    """
    stamp = pd.Timestamp(month if len(month) > 7 else month + "-01").to_period("M")
    mbr = load("dgec_mbr_monthly")
    mbr["period"] = pd.to_datetime(mbr["date"]).dt.to_period("M")
    row = mbr[mbr["period"] == stamp]
    if row.empty or pd.isna(row["mbr_usd_bbl"].iloc[0]):
        raise KeyError("no published MBR for %s" % stamp)
    cracks = note_cracks_for_month(month)
    return engine.decompose_official(
        float(row["mbr_usd_bbl"].iloc[0]),
        DGEC_NOTE_VOLUME_YIELDS,
        engine.crack_values(cracks),
        unattributed_products=DGEC_NOTE_UNATTRIBUTED_SLATE_LINES,
    )


def note_decomposition_history() -> pd.DataFrame:
    """Every month a note printed FINAL monthly quotations and DGEC has an MBR.

    Provisional months are listed with decomposed False and the reason, not
    dropped, so the count of months this decomposition covers is visible.

    Returns:
        date, vintage, provisional, decomposed, reason, official_usd_bbl,
        attributed_usd_bbl, residual_usd_bbl, carrier, and the note's own Brent
        date in $/bbl at DGEC_BBL_PER_T_BRENT_NOTE beside DGEC's published Brent.
    """
    printed = load("dgec_note_printed_monthly")
    brent = brent_monthly("dgec").set_index("date")["brent_usd_bbl"]
    rows = []
    for _, quoted in printed.iterrows():
        day = pd.Timestamp(quoted["date"])
        record = {
            "date": day,
            "vintage": str(quoted["vintage"]),
            "provisional": str(quoted["provisional"]).strip().lower() == "true",
            "note_brent_usd_bbl": float(quoted["brent_date_usd_t"])
            / config.DGEC_BBL_PER_T_BRENT_NOTE,
            "dgec_brent_usd_bbl": float(brent.get(day, math.nan)),
        }
        try:
            result = note_decomposition_for_month(_iso(day))
        except KeyError as error:
            record.update(
                decomposed=False,
                reason=str(error).strip("'\""),
                official_usd_bbl=math.nan,
                attributed_usd_bbl=math.nan,
                residual_usd_bbl=math.nan,
                carrier=None,
            )
        else:
            record.update(
                decomposed=True,
                reason="",
                official_usd_bbl=result.official_usd_bbl,
                attributed_usd_bbl=result.attributed_usd_bbl,
                residual_usd_bbl=result.residual_usd_bbl,
                carrier=result.carrier,
            )
        rows.append(record)
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# SPEC.md section 4.3 layer 2, the replication attempt on real months
# ---------------------------------------------------------------------------


def replication_attempts() -> pd.DataFrame:
    """Run the DGEC method on every month where DGEC printed its own quotations.

    The corpus is dgec_note_printed_monthly, which is seven months, because the
    six column layout that prints monthly averages first appears in the December
    2025 note and only ten notes survive. Those months carry Gazole, Fioul
    domestique, Jet and Fioul lourd TBTS in $/t, which map onto four of the
    method's ten product lines, plus Brent date.

    The result is the honest failure SPEC.md section 4.3 layer 2 anticipates:
    the full method is NaN because the gas and freight costs are unpublished,
    and the published only partial sits tens of dollars below the official
    figure. Nothing here is tuned toward the official number.

    Returns:
        One row per month, with the official MBR, the partial figure, the gap,
        and the count of missing inputs.
    """
    printed = load("dgec_note_printed_monthly")
    printed["date"] = _month_floor(printed["date"])
    mbr = load("dgec_mbr_monthly")
    mbr["date"] = _month_floor(mbr["date"])
    merged = printed.merge(mbr[["date", "mbr_usd_bbl"]], on="date", how="left")

    rows = []
    for _, row in merged.iterrows():
        quotations = {
            "gazole": float(row["gazole_usd_t"]),
            "fod": float(row["fioul_domestique_usd_t"]),
            "carbureacteur": float(row["jet_usd_t"]),
            "fioul_lourd_1pct": float(row["fioul_lourd_tbts_usd_t"]),
        }
        attempt = engine.replicate_mbr(
            quotations_usd_t=quotations,
            brent_usd_t=float(row["brent_date_usd_t"]),
            official_usd_bbl=float(row["mbr_usd_bbl"]),
        )
        rows.append(
            {
                "date": row["date"],
                "official_usd_bbl": attempt.official_usd_bbl,
                "margin_usd_bbl": attempt.margin_usd_bbl,
                "partial_usd_bbl": attempt.partial_usd_bbl,
                "error_usd_bbl": attempt.error_usd_bbl,
                "partial_error_usd_bbl": attempt.partial_error_usd_bbl,
                "covered_mass_yield": attempt.covered_mass_yield,
                "n_missing_inputs": len(attempt.missing_inputs),
                "within_bar": attempt.within_bar,
                "provisional": row.get("provisional"),
            }
        )
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# SPEC.md section 4.4, the October 2022 triangulation
# ---------------------------------------------------------------------------


#: The two fuel oil rows the OPEC Rotterdam table publishes, and what each one
#: means for a refinery that fires fuel oil instead of buying gas.
#:
#: THE HEADLINE IS THE 3.5 PERCENT ROW AND THE 1 PERCENT ROW IS THE VARIANT.
#: Gate 2 self audit, finding 7: this repository published both answers to the
#: same question, 6.23 $/bbl in docs/methodology.md and 5.51 $/bbl here, from
#: the same cache and the same month, because the two were computed on two
#: different fuel oil assessments. Both are defensible and that is exactly why
#: one of them has to be named. The choice, and the reason:
#:
#:   fuel_oil_35pct  the headline. SPEC.md section 4.4 asks for the gas cost
#:                   "against a refinery fired on fuel oil", and a refinery that
#:                   fires fuel oil burns its own heavy residue, which is high
#:                   sulphur. It is also the row on which the figure this repo
#:                   published first was computed, and a published number does
#:                   not move without a reason.
#:   fuel_oil_1pct   the variant, reported beside it and labelled. It is the row
#:                   the rest of this study prices, low sulphur barges, which is
#:                   what a refinery would BUY rather than what it would burn out
#:                   of its own tanks.
#:
#: Both are returned by every call, so nothing has to be recomputed to quote the
#: other, and the caller cannot get one without seeing that the other exists.
FUEL_OIL_TRIANGULATION_BASES: Mapping[str, str] = {
    "fuel_oil_35pct": "fuel_oil_35pct_usd_bbl",
    "fuel_oil_1pct": "fuel_oil_1pct_usd_bbl",
}

#: The basis the site quotes. See FUEL_OIL_TRIANGULATION_BASES for why.
FUEL_OIL_TRIANGULATION_HEADLINE = "fuel_oil_35pct"


def october_2022_triangulation(
    gas_intensity_mmbtu_per_bbl: float = config.GAS_INTENSITY_MMBTU_PER_BBL,
    month: str = "2022-10",
    fuel_oil_basis: str = FUEL_OIL_TRIANGULATION_HEADLINE,
) -> Mapping[str, float]:
    """This study's gas against fuel oil gap, next to S&P's 7 $/bbl.

    SPEC.md section 4.4: "With that intensity, compute the October 2022 gas cost
    against a refinery fired on fuel oil and report it next to S&P's 7 $/bbl
    gap. The same order of magnitude is the expectation. Report whatever you
    get." So this reports whatever it gets and nothing here is tuned toward 7.

    The arithmetic: both fuels are priced per million Btu and the refinery burns
    the same energy either way, so the gap is the intensity times the difference
    between the two fuel prices in $/MMBtu. The fuel oil price is an OPEC MOMR
    Rotterdam row, in $/bbl, divided by EIA's approximate heat content for
    residual fuel oil. That heat content is a US average for a heavy grade and
    the assessment is a Rotterdam barge, so this is an order of magnitude check
    and it is labelled as one.

    WHICH FUEL OIL, AND WHY IT IS A QUESTION. The table publishes a 3.5 percent
    sulphur row and a 1 percent row and they were 21 $/bbl apart in October
    2022, which is 0.7 $/bbl of gap. FUEL_OIL_TRIANGULATION_BASES carries the
    choice and the reason for it; the headline is the 3.5 percent row and the 1
    percent figure comes back in the same mapping under variant_, labelled,
    every time.

    Args:
        fuel_oil_basis: a key of FUEL_OIL_TRIANGULATION_BASES. Anything else is
            refused rather than defaulted, because silently picking one was how
            two answers got published.

    Returns a mapping rather than a record because it is a diagnostic quoted on
    the Method view, not a line of the model.
    """
    if fuel_oil_basis not in FUEL_OIL_TRIANGULATION_BASES:
        raise ValueError(
            "fuel_oil_basis is %r. The OPEC Rotterdam table publishes %s, and "
            "which one this question is asked on changes the answer by about "
            "0.7 $/bbl, so it is named rather than guessed"
            % (fuel_oil_basis, " and ".join(sorted(FUEL_OIL_TRIANGULATION_BASES)))
        )
    variant_basis = next(
        name for name in FUEL_OIL_TRIANGULATION_BASES if name != fuel_oil_basis
    )

    products = load("opec_rotterdam_products_monthly")
    products["date"] = _month_floor(products["date"])
    stamp = pd.Timestamp(month + "-01")
    row = products[products["date"] == stamp]
    if row.empty:
        raise KeyError("no OPEC Rotterdam quotations for %s" % month)

    gas = gas_monthly()
    gas_row = gas[gas["date"] == stamp]
    if gas_row.empty:
        raise KeyError("no gas price for %s" % month)

    gas_usd_mmbtu = float(gas_row["gas_usd_mmbtu"].iloc[0])
    gas_cost = engine.gas_cost_usd_bbl(gas_intensity_mmbtu_per_bbl, gas_usd_mmbtu)

    def fuel_oil_cost_of(basis: str) -> tuple[float, float, float]:
        usd_bbl = float(row[FUEL_OIL_TRIANGULATION_BASES[basis]].iloc[0])
        usd_mmbtu = usd_bbl / config.EIA_RESIDUAL_FUEL_OIL_MMBTU_PER_BBL
        return (
            usd_bbl,
            usd_mmbtu,
            engine.gas_cost_usd_bbl(gas_intensity_mmbtu_per_bbl, usd_mmbtu),
        )

    fuel_oil_usd_bbl, fuel_oil_usd_mmbtu, fuel_oil_cost = fuel_oil_cost_of(
        fuel_oil_basis
    )
    variant_usd_bbl, _, variant_cost = fuel_oil_cost_of(variant_basis)

    return {
        "month": stamp,
        "gas_usd_mmbtu": gas_usd_mmbtu,
        "fuel_oil_basis": fuel_oil_basis,
        "fuel_oil_usd_bbl": fuel_oil_usd_bbl,
        "fuel_oil_usd_mmbtu": fuel_oil_usd_mmbtu,
        "gas_cost_usd_bbl": gas_cost,
        "fuel_oil_cost_usd_bbl": fuel_oil_cost,
        "gap_usd_bbl": gas_cost - fuel_oil_cost,
        "variant_fuel_oil_basis": variant_basis,
        "variant_fuel_oil_usd_bbl": variant_usd_bbl,
        "variant_gap_usd_bbl": gas_cost - variant_cost,
        "sp_global_gap_usd_bbl": config.SP_GAS_VERSUS_FUEL_OIL_GAP_USD_BBL_2022_10,
    }


# ---------------------------------------------------------------------------
# The Now view, SPEC.md section 7.2, as values
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LatestView:
    """Everything the landing sentence is assembled from, plus its data dates.

    THREE DATES, NOT ONE, and they really are three different dates today:

        margin_month  the latest month with a published MBR and a gas price.
        crack_month   the latest month that also has Rotterdam product
                      quotations, which is where the decomposition and the
                      carrier come from. The OPEC MOMR issues for April to
                      September 2026 are not in the Internet Archive, a hole the
                      manifest records, so this month currently sits six months
                      behind the margin month.
        runs_data_date  the latest JODI month. JODI lags by about two months.

    SPEC.md section 7.2 asks for the margin date and the runs date to be shown
    separately for exactly this reason, and the crack date is a third because
    this study's crack source has its own hole. Nothing is carried forward to
    make the three agree: the landing sentence says "in the latest month with
    product quotations" and names it.
    """

    margin_month: str
    crack_month: str
    outputs: engine.Outputs
    margin_after_gas_usd_bbl: float
    mbr_usd_bbl: float
    gas_usd_mmbtu: float
    # No gas_cost_usd_bbl on this record. The MBR it describes is already net of
    # gas, so the only honest gas figures here are the two intensities priced at
    # this month's gas price and the gap between them. Gate 2 self audit,
    # finding 1. A single "the gas cost" on a net margin is the question that
    # produced the double charge.
    gas_wedge: engine.GasWedge
    decomposition: engine.Decomposition
    decomposition_outputs: engine.Outputs
    carrier: str | None
    percentile_10y: float | None
    headroom_usd_bbl: float | None
    margin_data_date: str
    runs_data_date: str
    crack_data_date: str
    weekly_crack_data_date: str
    # The number of PUBLISHED observations the rank was taken over, which today
    # is 120 and is not the same thing as the window's length. The field was
    # called percentile_months and held this count, so on the first month with a
    # hole in the ten year history the Gate 4 sentence would have said "120
    # months" over 119 observations. Gate 2 self audit, finding 14. The window
    # itself is outputs.percentile_window_months, config.PERCENTILE_WINDOW_MONTHS.
    percentile_observations: int
    threshold_identified: bool
    # GATE 4, ADDITIVE. The margin month itself taken apart with the ministry's
    # own final printed quotations, when a note printed them, and None when it
    # did not. The fields above keep their Gate 2 meaning: crack_month,
    # decomposition and carrier remain the OPEC path, which is history now. The
    # landing sentence's carrier is margin_carrier, from the same month as the
    # margin it explains. See note_decomposition_for_month.
    margin_decomposition: engine.Decomposition | None = None
    margin_cracks: Mapping[str, engine.Crack] | None = None
    margin_carrier: str | None = None
    margin_decomposition_reason: str = ""


def latest_view(
    threshold: float | None = None,
    gas_intensity_mmbtu_per_bbl: float = config.GAS_INTENSITY_MMBTU_PER_BBL,
) -> LatestView:
    """The latest complete month, end to end, through the engine.

    The margin after gas, the percentile and the gas breakevens come from the
    latest month that has a margin. The contributions, the carrier and the
    gasoil breakeven come from the latest month that also has cracks, and they
    carry that month's own date. Mixing the two would be exactly the
    misalignment SPEC.md section 4.2 forbids, one level up from a single crack.

    On the margin month the whole MBR sits on the residual line, because no
    product attribution is possible without product quotations. That is not a
    trick to make the numbers add up, it is what a residual line is for: the
    margin is real, this study cannot say which crack produced it that month,
    and the site shows the residual at full size rather than implying an
    attribution it does not have.

    Args:
        threshold: SPEC.md section 6.2's run cut threshold, which is Gate 3 work.
            None is the honest value at Gate 2 and it means the headroom and the
            breakevens come back None while the ten year percentile still works,
            which is exactly the fallback SPEC.md section 4.4 describes.
    """
    margin = margin_after_gas_monthly(gas_intensity_mmbtu_per_bbl)
    complete = margin[margin["margin_after_gas_usd_bbl"].notna()]
    if complete.empty:
        raise ValueError("no month has both a published MBR and a gas price")
    row = complete.iloc[-1]
    margin_month = _iso(row["date"])

    # The MBR is already net of gas, so this record carries no gas price and no
    # intensity. Handing it either would raise engine.GasDoubleCountError, which
    # is the guard doing its job rather than an inconvenience to route around.
    # The gas figures for this month are in the frame above, as a wedge.
    #
    # The same constructor the monthly column uses, so the landing sentence and
    # the series cannot be built two different ways. Gate 2 self audit, finding 3.
    margin_inputs = net_of_gas_margin_inputs(
        float(row["mbr_usd_bbl"]),
        float(row["other_variable_cost_usd_bbl"]),
        threshold,
    )
    wedge = engine.gas_wedge(
        float(row["gas_usd_mmbtu"]),
        config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL,
        gas_intensity_mmbtu_per_bbl,
    )
    history = trailing_window(margin, "margin_after_gas_usd_bbl", row["date"])
    bundle = engine.outputs(margin_inputs, history, threshold=threshold)

    # The latest month that has both a margin and product quotations.
    cracks = opec_monthly_cracks()
    cracks = cracks[cracks["crack_gasoil_usd_bbl"].notna()]
    shared = margin.merge(cracks[["date"]], on="date", how="inner")
    if shared.empty:
        raise ValueError("no month has both a published MBR and Rotterdam cracks")
    crack_row = shared.iloc[-1]
    crack_month = _iso(crack_row["date"])

    decomposition = decomposition_for_month(crack_month[:7])
    # The cracks themselves, from the one function that builds them through
    # engine.crack_values. They used to be recovered here as contribution over
    # yield, which multiplies and divides by the same number and divides by zero
    # on the day a slate line comes out at a zero yield. Gate 2 self audit,
    # finding 16.
    decomposition_inputs = engine.MarginInputs(
        yields=DGEC_VOLUME_YIELDS,
        cracks=cracks_for_month(crack_month[:7]),
        gas=engine.gas_from_usd_mmbtu(float(crack_row["gas_usd_mmbtu"])),
        residual_usd_bbl=decomposition.residual_usd_bbl,
        gas_intensity_mmbtu_per_bbl=gas_intensity_mmbtu_per_bbl,
        other_variable_cost_usd_bbl=float(crack_row["other_variable_cost_usd_bbl"]),
        run_cut_threshold_usd_bbl=threshold,
    )
    decomposition_bundle = engine.outputs(
        decomposition_inputs,
        trailing_window(margin, "margin_after_gas_usd_bbl", crack_row["date"]),
        gasoil_key="gasoil",
        threshold=threshold,
    )

    jodi = load("jodi_nwe_refinery_intake_monthly")
    opec = load("opec_rotterdam_products_monthly")
    weekly = load("dgec_note_reconstructed_weekly")

    try:
        margin_decomposition = note_decomposition_for_month(margin_month[:7])
        margin_cracks = note_cracks_for_month(margin_month[:7])
        margin_reason = ""
    except KeyError as error:
        margin_decomposition, margin_cracks = None, None
        margin_reason = str(error).strip("'\"")

    return LatestView(
        margin_month=margin_month,
        crack_month=crack_month,
        outputs=bundle,
        margin_after_gas_usd_bbl=bundle.margin.margin_after_gas_usd_bbl,
        mbr_usd_bbl=float(row["mbr_usd_bbl"]),
        gas_usd_mmbtu=float(row["gas_usd_mmbtu"]),
        gas_wedge=wedge,
        decomposition=decomposition,
        decomposition_outputs=decomposition_bundle,
        carrier=decomposition.carrier,
        percentile_10y=bundle.percentile_10y,
        headroom_usd_bbl=bundle.headroom_usd_bbl,
        margin_data_date=margin_month,
        runs_data_date=_iso(pd.to_datetime(jodi["date"]).max()),
        crack_data_date=_iso(pd.to_datetime(opec["date"]).max()),
        weekly_crack_data_date=_iso(pd.to_datetime(weekly["date"]).max()),
        percentile_observations=bundle.percentile_observations,
        threshold_identified=bundle.threshold_identified,
        margin_decomposition=margin_decomposition,
        margin_cracks=margin_cracks,
        margin_carrier=(
            None if margin_decomposition is None else margin_decomposition.carrier
        ),
        margin_decomposition_reason=margin_reason,
    )
