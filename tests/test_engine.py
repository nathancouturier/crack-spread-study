"""The engine gate. SPEC.md section 9, every row that is about the model.

tests/test_units.py holds the Units and Intensity rows, because both are
statements about conversion factors. This file holds the rest:

    Null         every crack zero, TTF zero, other cost zero, and the gross
                 margin, the margin after gas and the residual are all exactly
                 zero. It catches a term that should not exist. It does NOT
                 catch a sign error, whatever SPEC.md section 9's Catches column
                 says, because every input in it is zero and zero has no sign to
                 get wrong. Gate 2 self audit, finding 4. The signed null beside
                 it, and the Linearity and Round trip rows, are the sign tests,
                 and they are the ones that fired when the audit injected sign
                 errors.
    Linearity    the gross margin moves by yield[p] per $/bbl of crack[p], and
                 the margin after gas by -gas_intensity * eurusd / 3.412142 per
                 EUR/MWh of TTF. Catches a broken EUR/MWh to $/MMBtu chain.
    Round trip   breakeven_ttf plugged back in gives the threshold to 1e-9.
                 Catches the forward calculation and the inversion disagreeing.
    Alignment    no crack is ever computed from legs with different dates or
                 averaging windows. Catches silent misalignment.
    Replication  the MBR within 0.50 $/bbl, or a documented reason why not. It
                 is the second of those, and the reason is tested as carefully
                 as a pass would have been.

A word on the word "exactly"
----------------------------
SPEC.md section 9 says the Null row is exactly zero and the Linearity row moves
by exactly yield[p]. Those two exactlies are not the same kind of claim in
binary floating point, and this file does not pretend they are:

    Null       IS bit exact. Zero times anything is zero, and the sums are of
               zeros, so the assertions are == 0.0 with no tolerance.
    Linearity  is exact in arithmetic and not in IEEE 754 doubles, because
               0.34 * 21.0 - 0.34 * 20.0 is 0.3400000000000007 rather than
               0.34. The assertion is therefore to 1e-12, which is a thousand
               times tighter than the 1e-9 SPEC.md section 7.1 requires of the
               two engines and far below any number this study prints. A test
               that demanded bit equality here would be testing the rounding
               mode, not the model.

The real committed caches
-------------------------
The last section of this file runs the engine over data/cache through
crack.series. Those tests are the ones that would catch a model that is
internally consistent and wrong about Rotterdam, and they are why the
replication row can state a measured error rather than an expected one.
"""

from __future__ import annotations

import math

import pytest

from crack import config, engine


# ---------------------------------------------------------------------------
# A small, fully specified refinery, used by most of what follows
# ---------------------------------------------------------------------------


def make_inputs(**overrides):
    """A two product margin with every input named, easy to perturb.

    The yields are volumetric and deliberately do not sum to 1: the rest of the
    barrel is the residual line, which is the whole point of SPEC.md section 4.3
    layer 3 and is never spread across the two products here.
    """
    base = dict(
        yields={"gasoil": 0.34, "gasoline": 0.12},
        cracks={"gasoil": 20.0, "gasoline": 10.0},
        gas=engine.gas_from_ttf(40.0, 1.10),
        residual_usd_bbl=0.0,
        gas_intensity_mmbtu_per_bbl=config.GAS_INTENSITY_MMBTU_PER_BBL,
        other_variable_cost_usd_bbl=0.0,
        run_cut_threshold_usd_bbl=None,
    )
    base.update(overrides)
    return engine.MarginInputs(**base)


# ---------------------------------------------------------------------------
# SPEC.md section 9, the Null row
# ---------------------------------------------------------------------------


def test_null_case_is_exactly_zero_everywhere():
    """Every crack zero, TTF zero, other cost zero. Nothing may be non zero.

    THIS IS NOT THE SIGN ERROR TEST, and it said it was until the Gate 2 self
    audit, finding 4. The claim was that a margin which added the gas cost
    instead of subtracting it, or subtracted the residual instead of adding it,
    would fail here. It does not, and it cannot: every input in this case is
    zero, and zero plus zero, zero minus zero and minus zero minus zero are all
    zero. The audit injected both of those sign errors and all three Null tests
    stayed green through both.

    What this case IS worth keeping is an exactness check on the zero case. No
    tolerance, no approx: a model that returned 1e-17 here would be carrying a
    term that has no business existing, and SPEC.md section 9 asks for exactly
    zero.

    The sign tests are the one below, which is the same case with the zeros
    taken out, plus the Linearity and Round trip rows further down this file.
    Those are what fired on the audit's injections.
    """
    inputs = engine.MarginInputs(
        yields={"gasoil": 0.34, "gasoline": 0.12},
        cracks={"gasoil": 0.0, "gasoline": 0.0},
        gas=engine.gas_from_ttf(0.0, 1.10),
        residual_usd_bbl=0.0,
        other_variable_cost_usd_bbl=0.0,
    )
    result = engine.evaluate(inputs)

    assert result.attributed_usd_bbl == 0.0
    assert result.residual_usd_bbl == 0.0
    assert result.gross_margin_usd_bbl == 0.0
    assert result.gas_usd_mmbtu == 0.0
    assert result.gas_cost_usd_bbl == 0.0
    assert result.margin_after_gas_usd_bbl == 0.0
    for product in result.contributions:
        assert result.contributions[product] == 0.0


def test_a_signed_null_is_zero_only_because_every_sign_is_right():
    """The sign test the zero case cannot be: four non zero terms summing to zero.

    Gate 2 self audit, finding 4. Every line here is non zero and every line has
    a different magnitude, so no two sign errors can cancel and no single one
    can land back on zero:

        contributions   0.25 * 20.0 + 0.125 * 20.0   =  +7.5
        residual                                      =  -1.0
        gross margin                                  =  +6.5
        gas cost        0.5 MMBtu/bbl * 10.0 $/MMBtu  =  -5.0
        other variable cost                           =  -1.5
        margin after gas                              =   0.0

    Every one of those is exact in IEEE 754 double precision, so this is an
    equality assertion like the zero case above rather than a tolerance.

    What each injection does, computed by hand, which is why this test is
    written with these numbers and not prettier ones:

        residual added instead of subtracted    +2.0
        gas cost added instead of subtracted   +10.0
        other cost added instead of subtracted  +3.0
        contributions subtracted               -15.0

    None of them is zero and none of them is another, so the failure message
    says which sign moved.
    """
    inputs = engine.MarginInputs(
        yields={"gasoil": 0.25, "gasoline": 0.125},
        cracks={"gasoil": 20.0, "gasoline": 20.0},
        gas=engine.gas_from_usd_mmbtu(10.0),
        residual_usd_bbl=-1.0,
        gas_intensity_mmbtu_per_bbl=0.5,
        other_variable_cost_usd_bbl=1.5,
    )
    result = engine.evaluate(inputs)

    assert result.attributed_usd_bbl == 7.5
    assert result.residual_usd_bbl == -1.0
    assert result.gross_margin_usd_bbl == 6.5
    assert result.gas_cost_usd_bbl == 5.0
    assert result.other_variable_cost_usd_bbl == 1.5
    assert result.margin_after_gas_usd_bbl == 0.0

    # The decomposition's residual has the other sign convention, official minus
    # attributed, and it is solved rather than taken. A sign slip there returns
    # +7.5 instead of -1.0 on these numbers.
    decomposition = engine.decompose_official(
        6.5, inputs.yields, inputs.cracks
    )
    assert decomposition.attributed_usd_bbl == 7.5
    assert decomposition.residual_usd_bbl == -1.0


def test_null_case_on_the_published_gas_path_too():
    """The World Bank path has to be as null safe as the TTF path."""
    inputs = engine.MarginInputs(
        yields={"gasoil": 0.34},
        cracks={"gasoil": 0.0},
        gas=engine.gas_from_usd_mmbtu(0.0),
    )
    result = engine.evaluate(inputs)
    assert result.gross_margin_usd_bbl == 0.0
    assert result.margin_after_gas_usd_bbl == 0.0


def test_null_decomposition_residual_is_exactly_zero():
    """An official margin of zero, cracks of zero, and the residual is zero.

    The decomposition solves the residual rather than taking it, so this is the
    null test for the other half of SPEC.md section 4.3 layer 3.
    """
    decomposition = engine.decompose_official(
        0.0, {"gasoil": 0.34, "gasoline": 0.12}, {"gasoil": 0.0, "gasoline": 0.0}
    )
    assert decomposition.attributed_usd_bbl == 0.0
    assert decomposition.residual_usd_bbl == 0.0


# ---------------------------------------------------------------------------
# SPEC.md section 9, the Linearity row
# ---------------------------------------------------------------------------


def test_gross_margin_moves_by_the_yield_per_dollar_of_crack():
    """One dollar on a crack is yield[p] dollars on the gross margin."""
    for product, expected in (("gasoil", 0.34), ("gasoline", 0.12)):
        base = make_inputs()
        bumped_cracks = dict(base.cracks)
        bumped_cracks[product] = bumped_cracks[product] + 1.0
        bumped = make_inputs(cracks=bumped_cracks)

        moved = (
            engine.evaluate(bumped).gross_margin_usd_bbl
            - engine.evaluate(base).gross_margin_usd_bbl
        )
        assert moved == pytest.approx(expected, abs=1e-12)


def test_margin_after_gas_moves_by_the_same_amount_on_a_crack():
    """The gas cost does not depend on the cracks, so the slope is unchanged."""
    base = make_inputs()
    bumped = make_inputs(cracks={"gasoil": 21.0, "gasoline": 10.0})
    moved = (
        engine.evaluate(bumped).margin_after_gas_usd_bbl
        - engine.evaluate(base).margin_after_gas_usd_bbl
    )
    assert moved == pytest.approx(0.34, abs=1e-12)


def test_margin_after_gas_moves_by_minus_intensity_times_eurusd_over_3_412142():
    """The EUR/MWh to $/MMBtu chain, tested as a derivative.

    SPEC.md section 9 writes the expected slope out in full:

        -gas_intensity * eurusd / 3.412142   per EUR/MWh of TTF

    A chain that multiplied by 3.412142 instead of dividing, or that forgot the
    exchange rate, or that dropped the minus sign, fails here, and each of those
    three is a plausible mistake that leaves the level looking reasonable.
    """
    eurusd = 1.10
    intensity = config.GAS_INTENSITY_MMBTU_PER_BBL
    expected = -intensity * eurusd / 3.412142

    base = make_inputs(gas=engine.gas_from_ttf(40.0, eurusd))
    bumped = make_inputs(gas=engine.gas_from_ttf(41.0, eurusd))
    moved = (
        engine.evaluate(bumped).margin_after_gas_usd_bbl
        - engine.evaluate(base).margin_after_gas_usd_bbl
    )
    assert moved == pytest.approx(expected, abs=1e-12)

    # And the slope has to be the same over a ten euro move, or the chain is
    # not linear and a closed form breakeven would be wrong.
    far = make_inputs(gas=engine.gas_from_ttf(50.0, eurusd))
    moved_far = (
        engine.evaluate(far).margin_after_gas_usd_bbl
        - engine.evaluate(base).margin_after_gas_usd_bbl
    )
    assert moved_far == pytest.approx(10.0 * expected, abs=1e-12)


def test_the_gas_slope_changes_with_the_exchange_rate():
    """A stronger euro makes the same TTF cost more dollars per barrel.

    Tested because an implementation that dropped eurusd would still pass the
    previous test if eurusd happened to be 1.0 in the fixture, and 1.0 is
    exactly the value somebody would reach for.
    """
    intensity = config.GAS_INTENSITY_MMBTU_PER_BBL
    for eurusd in (0.95, 1.00, 1.25):
        base = make_inputs(gas=engine.gas_from_ttf(40.0, eurusd))
        bumped = make_inputs(gas=engine.gas_from_ttf(41.0, eurusd))
        moved = (
            engine.evaluate(bumped).margin_after_gas_usd_bbl
            - engine.evaluate(base).margin_after_gas_usd_bbl
        )
        assert moved == pytest.approx(
            -intensity * eurusd / config.MMBTU_PER_MWH, abs=1e-12
        )


def test_other_variable_cost_enters_one_for_one_and_negatively():
    """SPEC.md section 4.4: margin_after_gas = gross - gas_cost - other."""
    base = make_inputs(other_variable_cost_usd_bbl=0.0)
    bumped = make_inputs(other_variable_cost_usd_bbl=1.0)
    moved = (
        engine.evaluate(bumped).margin_after_gas_usd_bbl
        - engine.evaluate(base).margin_after_gas_usd_bbl
    )
    assert moved == pytest.approx(-1.0, abs=1e-12)
    assert config.OTHER_VARIABLE_COST_USD_BBL == 0.0


# ---------------------------------------------------------------------------
# SPEC.md section 9, the Round trip row
# ---------------------------------------------------------------------------


def test_breakeven_ttf_plugged_back_in_gives_the_threshold():
    """SPEC.md section 9: agreement within 1e-9. The closed form, checked.

    The breakeven is computed in closed form because the model is linear,
    SPEC.md section 4.5, so this test is the only thing standing between a sign
    slip in the inversion and a site that quotes a confident wrong gas price.
    """
    for threshold in (-2.0, 0.0, 1.5, 4.25):
        inputs = make_inputs(run_cut_threshold_usd_bbl=threshold)
        ttf_star = engine.breakeven_ttf(inputs)
        assert ttf_star is not None

        replugged = make_inputs(
            gas=engine.gas_from_ttf(ttf_star, 1.10),
            run_cut_threshold_usd_bbl=threshold,
        )
        result = engine.evaluate(replugged)
        assert abs(result.margin_after_gas_usd_bbl - threshold) < 1e-9
        assert abs(result.headroom_usd_bbl) < 1e-9


def test_breakeven_gas_price_plugged_back_in_gives_the_threshold():
    """The same round trip on the published $/MMBtu path, which has no FX."""
    threshold = 2.0
    inputs = make_inputs(
        gas=engine.gas_from_usd_mmbtu(12.0), run_cut_threshold_usd_bbl=threshold
    )
    gas_star = engine.breakeven_gas_usd_mmbtu(inputs)
    assert gas_star is not None

    replugged = make_inputs(
        gas=engine.gas_from_usd_mmbtu(gas_star), run_cut_threshold_usd_bbl=threshold
    )
    assert (
        abs(engine.evaluate(replugged).margin_after_gas_usd_bbl - threshold) < 1e-9
    )


def test_breakeven_gasoil_crack_plugged_back_in_gives_the_threshold():
    """SPEC.md section 4.5 names breakeven_gasoil, so it gets its own round trip."""
    threshold = 1.0
    inputs = make_inputs(run_cut_threshold_usd_bbl=threshold)
    crack_star = engine.breakeven_crack(inputs, "gasoil")
    assert crack_star is not None

    replugged = make_inputs(
        cracks={"gasoil": crack_star, "gasoline": 10.0},
        run_cut_threshold_usd_bbl=threshold,
    )
    assert (
        abs(engine.evaluate(replugged).margin_after_gas_usd_bbl - threshold) < 1e-9
    )


def test_the_round_trip_holds_with_a_residual_and_an_other_cost_in_the_way():
    """The inversion has to carry every line, not only the ones in the fixture."""
    threshold = 3.0
    inputs = make_inputs(
        residual_usd_bbl=-1.75,
        other_variable_cost_usd_bbl=0.6,
        run_cut_threshold_usd_bbl=threshold,
    )
    ttf_star = engine.breakeven_ttf(inputs)
    gasoil_star = engine.breakeven_crack(inputs, "gasoil")

    by_ttf = make_inputs(
        gas=engine.gas_from_ttf(ttf_star, 1.10),
        residual_usd_bbl=-1.75,
        other_variable_cost_usd_bbl=0.6,
        run_cut_threshold_usd_bbl=threshold,
    )
    by_crack = make_inputs(
        cracks={"gasoil": gasoil_star, "gasoline": 10.0},
        residual_usd_bbl=-1.75,
        other_variable_cost_usd_bbl=0.6,
        run_cut_threshold_usd_bbl=threshold,
    )
    assert abs(engine.evaluate(by_ttf).margin_after_gas_usd_bbl - threshold) < 1e-9
    assert abs(engine.evaluate(by_crack).margin_after_gas_usd_bbl - threshold) < 1e-9


# ---------------------------------------------------------------------------
# No threshold is a first class answer. SPEC.md sections 4.4 and 6.2.
# ---------------------------------------------------------------------------


def test_without_a_threshold_there_is_no_headroom_and_no_breakeven():
    """SPEC.md section 6.2 allows the threshold to come out unidentified.

    The Gate 2 brief is explicit: do not invent a threshold at Gate 2. So the
    engine returns None, which the site turns into words, and it never returns
    a number computed against a placeholder.
    """
    inputs = make_inputs(run_cut_threshold_usd_bbl=None)
    result = engine.evaluate(inputs)

    assert result.threshold_identified is False
    assert result.headroom_usd_bbl is None
    assert engine.breakeven_ttf(inputs) is None
    assert engine.breakeven_gas_usd_mmbtu(inputs) is None
    assert engine.breakeven_crack(inputs, "gasoil") is None


def test_the_percentile_still_works_without_a_threshold():
    """Which is SPEC.md section 4.4's own fallback, so it has to be independent."""
    inputs = make_inputs(run_cut_threshold_usd_bbl=None)
    history = [0.0, 1.0, 2.0, 3.0, 4.0]
    bundle = engine.outputs(inputs, history)
    assert bundle.threshold_identified is False
    assert bundle.headroom_usd_bbl is None
    assert bundle.percentile_10y == 100.0


def test_a_breakeven_with_no_leverage_is_none_rather_than_infinity():
    """Zero gas intensity, zero exchange rate, zero yield. Three no answers.

    Python would raise ZeroDivisionError and JavaScript would return Infinity,
    and SPEC.md section 7.1 requires the two engines to agree, so both return
    None and the site says the question has no answer.
    """
    no_gas = make_inputs(
        gas_intensity_mmbtu_per_bbl=0.0, run_cut_threshold_usd_bbl=1.0
    )
    assert engine.breakeven_ttf(no_gas) is None
    assert engine.breakeven_gas_usd_mmbtu(no_gas) is None

    no_fx = make_inputs(
        gas=engine.gas_from_ttf(40.0, 0.0), run_cut_threshold_usd_bbl=1.0
    )
    assert engine.breakeven_ttf(no_fx) is None

    no_yield = make_inputs(
        yields={"gasoil": 0.0, "gasoline": 0.12}, run_cut_threshold_usd_bbl=1.0
    )
    assert engine.breakeven_crack(no_yield, "gasoil") is None


def test_a_ttf_breakeven_is_refused_on_the_published_gas_path():
    """The pink sheet series carries no exchange rate, so no TTF can be implied.

    Returning a number here would mean inventing an FX rate, which SPEC.md
    section 2 rule 1 forbids. The $/MMBtu breakeven is the one that exists on
    this path and it is returned.
    """
    inputs = make_inputs(
        gas=engine.gas_from_usd_mmbtu(12.0), run_cut_threshold_usd_bbl=1.0
    )
    assert engine.breakeven_ttf(inputs) is None
    assert engine.breakeven_gas_usd_mmbtu(inputs) is not None


# ---------------------------------------------------------------------------
# SPEC.md section 9, the Alignment row
# ---------------------------------------------------------------------------


def test_a_weekly_product_against_a_monthly_crude_is_refused():
    """The exact sentence SPEC.md section 4.2 forbids, as an exception."""
    product = engine.Quote(1160.0, engine.USD_PER_T, "2026-07-03", engine.WEEKLY, "Gazole")
    brent = engine.Quote(628.0, engine.USD_PER_T, "2026-07-03", engine.MONTHLY, "Brent date")
    with pytest.raises(engine.AlignmentError) as raised:
        engine.crack(
            product,
            brent,
            product_bbl_per_t=config.BBL_PER_T_GASOIL,
            brent_bbl_per_t=config.DGEC_BBL_PER_T_BRENT_NOTE,
        )
    assert "averaging window" in str(raised.value)


def test_two_different_dates_are_refused_even_at_the_same_frequency():
    """Same window, different days. The other half of the alignment rule."""
    product = engine.Quote(1160.0, engine.USD_PER_T, "2026-07-03", engine.WEEKLY)
    brent = engine.Quote(628.0, engine.USD_PER_T, "2026-06-26", engine.WEEKLY)
    with pytest.raises(engine.AlignmentError):
        engine.crack(
            product,
            brent,
            product_bbl_per_t=config.BBL_PER_T_GASOIL,
            brent_bbl_per_t=config.DGEC_BBL_PER_T_BRENT_NOTE,
        )


def test_aligned_legs_are_accepted_and_carry_their_date_and_window():
    """The positive case, so the guard is not passing by refusing everything."""
    product = engine.Quote(1160.0, engine.USD_PER_T, "2026-07-01", engine.MONTHLY, "Gazole")
    brent = engine.Quote(628.0, engine.USD_PER_T, "2026-07-01", engine.MONTHLY, "Brent date")
    result = engine.crack(
        product,
        brent,
        product_bbl_per_t=config.BBL_PER_T_GASOIL,
        brent_bbl_per_t=config.DGEC_BBL_PER_T_BRENT_NOTE,
    )
    assert result.date == "2026-07-01"
    assert result.window == engine.MONTHLY
    assert result.product_basis == engine.BASIS_CONVERTED
    assert result.value == pytest.approx(1160.0 / 7.45 - 628.0 / 7.5, abs=1e-12)


def test_a_decomposition_cannot_mix_windows_either():
    """One crack's legs are not the only thing that has to line up.

    A decomposition adds several cracks into one margin, so the cracks have to
    share a date and a window with each other. crack_values is where that is
    enforced and it is the only way cracks reach the decomposition.
    """
    brent_month = engine.Quote(80.0, engine.USD_PER_BBL, "2022-10-01", engine.MONTHLY)
    brent_week = engine.Quote(80.0, engine.USD_PER_BBL, "2022-10-07", engine.WEEKLY)
    monthly = engine.crack(
        engine.Quote(140.0, engine.USD_PER_BBL, "2022-10-01", engine.MONTHLY, "gasoil"),
        brent_month,
    )
    weekly = engine.crack(
        engine.Quote(110.0, engine.USD_PER_BBL, "2022-10-07", engine.WEEKLY, "gasoline"),
        brent_week,
    )
    with pytest.raises(engine.AlignmentError):
        engine.crack_values({"gasoil": monthly, "gasoline": weekly})

    # The aligned pair goes through and keeps its values.
    aligned = engine.crack(
        engine.Quote(110.0, engine.USD_PER_BBL, "2022-10-01", engine.MONTHLY, "gasoline"),
        brent_month,
    )
    values = engine.crack_values({"gasoil": monthly, "gasoline": aligned})
    assert values["gasoil"] == 60.0
    assert values["gasoline"] == 30.0


def test_a_quote_cannot_carry_a_window_the_project_does_not_average_on():
    """The alignment rule is only as good as the vocabulary it compares."""
    with pytest.raises(engine.AlignmentError):
        engine.Quote(80.0, engine.USD_PER_BBL, "2026-07-01", "quarterly")


# ---------------------------------------------------------------------------
# SPEC.md section 9, the Replication row. A documented failure.
# ---------------------------------------------------------------------------


def test_replication_does_not_reach_the_bar_and_says_why():
    """SPEC.md section 9: "MBR within 0.50 $/bbl, or a documented reason why not".

    It is the second one, and the reason is the deliverable. Recon 02 section
    5.6 crossed the methodology note's own input list against the weekly note
    and found seven inputs that nobody publishes. So the attempt runs on what
    IS published, the headline figure comes back NaN because two cost lines are
    missing, and the official series is what the site shows.

    This test asserts the failure is the RIGHT failure. A replication that
    started passing would mean either that DGEC began publishing five more
    quotations, in which case this test should fail and be rewritten, or that
    somebody filled a missing input with a plausible number, which is the thing
    SPEC.md section 2 rule 1 exists to stop.
    """
    # July 2026, the SPEC.md section 5.5 anchor month, with every published
    # quotation at its printed value and nothing else supplied.
    attempt = engine.replicate_mbr(
        quotations_usd_t={
            "gazole": 1160.0,
            "fod": 1127.0,
            "carbureacteur": 1204.0,
            "fioul_lourd_1pct": 507.0,
        },
        brent_usd_t=628.0,
        official_usd_bbl=36.69,
    )

    assert attempt.within_bar is False
    assert math.isnan(attempt.margin_usd_bbl)
    assert math.isnan(attempt.error_usd_bbl)
    assert attempt.bar_usd_bbl == 0.50

    # The five unpublished product quotations and the two unpublished costs,
    # each named. SPEC.md section 4.3 layer 2: "If an input is not published,
    # name it".
    for name in (
        "eurobob",
        "essence_export",
        "naphta",
        "propane",
        "butane",
        "peg_nord_gas_day_ahead",
        "aframax_freight_sullom_voe_le_havre",
    ):
        assert name in attempt.missing_inputs

    assert "EuroBOB" in attempt.reason
    assert "0.50 $/bbl" in attempt.reason
    assert attempt.reason == engine.REPLICATION_FAILURE_REASON


def test_the_published_only_partial_is_reported_and_is_not_a_margin():
    """The partial figure is a measurement of the gap, never a substitute.

    Four product lines and the sulphur line cover 59.5 percent of the mass
    yield, so the partial revenue pays for the crude and almost nothing else:
    for July 2026 it lands at 0.22 $/bbl against an official 36.69, a gap of
    36.47 $/bbl, which is seventy times the 0.50 $/bbl bar. Reporting that
    number honestly is the point. It is the size of what is missing, and anybody
    who reads it as an estimate of the margin has been told otherwise in the
    same record.
    """
    attempt = engine.replicate_mbr(
        quotations_usd_t={
            "gazole": 1160.0,
            "fod": 1127.0,
            "carbureacteur": 1204.0,
            "fioul_lourd_1pct": 507.0,
        },
        brent_usd_t=628.0,
        official_usd_bbl=36.69,
    )
    assert attempt.covered_mass_yield == pytest.approx(0.595, abs=1e-12)
    assert attempt.partial_usd_bbl == pytest.approx(0.222, abs=1e-3)
    assert attempt.partial_error_usd_bbl == pytest.approx(-36.468, abs=1e-3)
    assert abs(attempt.partial_error_usd_bbl) > 70 * attempt.bar_usd_bbl
    # The official figure is carried through untouched, SPEC.md section 4.3
    # layer 1. The replication never overwrites it.
    assert attempt.official_usd_bbl == 36.69


def test_a_replication_with_every_input_supplied_does_close():
    """The arithmetic is right even though the data to run it does not exist.

    Constructed backwards from the method: pick a revenue and a cost stack, work
    out the margin by hand, and check the engine agrees. If DGEC ever publishes
    the five missing quotations, this is the test that says the method was
    implemented correctly all along, and until then it is the only thing
    separating "we cannot replicate" from "we cannot compute".
    """
    mass_yields = config.DGEC_MASS_YIELDS
    prices = {
        "propane": 500.0,
        "butane": 520.0,
        "naphta": 600.0,
        "eurobob": 750.0,
        "essence_export": 700.0,
        "carbureacteur": 800.0,
        "gazole": 780.0,
        "fod": 760.0,
        "fioul_lourd_1pct": 400.0,
    }
    brent_usd_t = 620.0
    freight = 12.0
    gas = 6.0

    revenue = sum(
        mass_yields[name] * price for name, price in sorted(prices.items())
    )
    revenue += mass_yields["soufre"] * config.DGEC_SULPHUR_PRICE_USD_T
    cost = (
        brent_usd_t
        + gas
        + freight
        + config.DGEC_INSURANCE_AND_LOSS_RATE * (brent_usd_t + freight)
    )
    expected = (revenue - cost) / config.DGEC_BBL_PER_T_BRENT_MARGIN

    attempt = engine.replicate_mbr(
        quotations_usd_t=prices,
        brent_usd_t=brent_usd_t,
        official_usd_bbl=expected,
        freight_usd_t=freight,
        gas_cost_usd_t=gas,
    )
    assert attempt.margin_usd_bbl == pytest.approx(expected, abs=1e-12)
    assert abs(attempt.error_usd_bbl) < 1e-12
    assert attempt.within_bar is True
    assert attempt.missing_inputs == ()
    assert attempt.covered_mass_yield == pytest.approx(0.945, abs=1e-12)


def test_the_replication_uses_the_margin_brent_factor_and_not_the_note_one():
    """7.55 inside the method, 7.5 in the note's display column.

    Recon 02 section 5.4. The two factors differ by 0.67 percent, so the whole
    margin differs by 0.67 percent and the Brent leg alone by about 0.55 $/bbl
    at the July 2026 anchor, which tests/test_units.py measures directly. Here
    the check is the ratio, because it holds at any level and it is what makes
    the swap detectable even on a month where the margin is small.
    """
    prices = {"gazole": 780.0}
    on_margin_factor = engine.replicate_mbr(
        prices, 620.0, 0.0, freight_usd_t=12.0, gas_cost_usd_t=6.0
    ).margin_usd_bbl
    on_note_factor = engine.replicate_mbr(
        prices,
        620.0,
        0.0,
        freight_usd_t=12.0,
        gas_cost_usd_t=6.0,
        bbl_per_t_brent=config.DGEC_BBL_PER_T_BRENT_NOTE,
    ).margin_usd_bbl
    assert on_margin_factor != on_note_factor
    ratio = (
        config.DGEC_BBL_PER_T_BRENT_MARGIN / config.DGEC_BBL_PER_T_BRENT_NOTE
    )
    assert on_note_factor == pytest.approx(on_margin_factor * ratio, abs=1e-9)
    assert ratio == pytest.approx(1.006667, abs=1e-6)


# ---------------------------------------------------------------------------
# SPEC.md section 4.3 layer 3, the decomposition and its residual
# ---------------------------------------------------------------------------


def test_the_residual_is_whatever_the_official_margin_has_left():
    """contribution[p] = yield[p] * crack[p], and the rest is one line."""
    decomposition = engine.decompose_official(
        20.0,
        {"gasoil": 0.34, "gasoline": 0.12},
        {"gasoil": 40.0, "gasoline": 20.0},
        unattributed_products=("naphta", "propane"),
    )
    assert decomposition.contributions["gasoil"] == pytest.approx(13.6, abs=1e-12)
    assert decomposition.contributions["gasoline"] == pytest.approx(2.4, abs=1e-12)
    assert decomposition.attributed_usd_bbl == pytest.approx(16.0, abs=1e-12)
    assert decomposition.residual_usd_bbl == pytest.approx(4.0, abs=1e-12)
    assert decomposition.residual_share == pytest.approx(0.2, abs=1e-12)
    assert decomposition.unattributed_products == ("naphta", "propane")
    assert decomposition.covered_volume_yield == pytest.approx(0.46, abs=1e-12)


def test_the_residual_is_never_spread_across_the_products():
    """SPEC.md section 4.3 layer 3, tested as an invariant rather than a promise.

    Move the official margin and nothing but the residual may move. A
    decomposition that quietly scaled the contributions to fit would fail here,
    and scaling to fit is the natural thing to write when the residual looks
    embarrassing.
    """
    yields = {"gasoil": 0.34, "gasoline": 0.12}
    cracks = {"gasoil": 40.0, "gasoline": 20.0}
    low = engine.decompose_official(10.0, yields, cracks)
    high = engine.decompose_official(30.0, yields, cracks)

    assert low.contributions == high.contributions
    assert low.attributed_usd_bbl == high.attributed_usd_bbl
    assert high.residual_usd_bbl - low.residual_usd_bbl == pytest.approx(20.0, abs=1e-12)


def test_the_carrier_is_the_largest_contribution_not_the_largest_crack():
    """SPEC.md section 4.5: carrier = product with the largest CONTRIBUTION.

    A gasoline crack of 30 beats a gasoil crack of 20, but 0.12 * 30 is 3.6 and
    0.34 * 20 is 6.8, so gasoil carries the barrel. This is the distinction the
    whole decomposition exists to make and it is easy to lose.
    """
    result = engine.evaluate(
        make_inputs(cracks={"gasoil": 20.0, "gasoline": 30.0})
    )
    assert result.carrier == "gasoil"
    assert result.carrier_contribution_usd_bbl == pytest.approx(6.8, abs=1e-12)


def test_a_missing_contribution_cannot_win_the_carrier_and_cannot_hide_it():
    """One missing minor product must not erase the answer for the whole barrel."""
    result = engine.evaluate(
        make_inputs(cracks={"gasoil": 20.0, "gasoline": math.nan})
    )
    assert result.carrier == "gasoil"
    assert math.isnan(result.gross_margin_usd_bbl)
    assert math.isnan(result.margin_after_gas_usd_bbl)


def test_every_product_needs_both_a_yield_and_a_crack():
    """A product with one and not the other is a margin that silently misses it."""
    with pytest.raises(ValueError):
        engine.MarginInputs(
            yields={"gasoil": 0.34, "gasoline": 0.12}, cracks={"gasoil": 20.0}
        )


# ---------------------------------------------------------------------------
# SPEC.md section 4.3 layer 4, observed yields on two denominators
# ---------------------------------------------------------------------------


def test_both_jodi_denominators_exist_and_disagree_the_way_recon_03_measured():
    """Recon 03 section 1.8: 1.13 to 1.16 on crude, 1.01 to 1.03 on total feed.

    October 2022, the real JODI numbers for the five countries, from recon 03
    section 1.8's own table: crude intake 4,995.8 kb/d and total product output
    5,761.0 kb/d, which is a ratio of 1.1532.
    """
    output = {"totprods": 5761.0}
    on_crude = engine.observed_yields(
        output, 4995.8, config.YIELD_BASIS_CRUDE_INTAKE
    )
    assert on_crude.total == pytest.approx(1.1532, abs=1e-4)
    assert on_crude.basis == config.YIELD_BASIS_CRUDE_INTAKE
    assert "1.13 to 1.16" in on_crude.note

    normalised = on_crude.normalised()
    assert normalised.total == pytest.approx(1.0, abs=1e-12)
    assert normalised.basis == config.YIELD_BASIS_NORMALISED
    assert "share of output" in normalised.note


def test_the_yield_basis_has_to_be_named_and_cannot_be_defaulted():
    """Recon 03 section 1.8: "Do not quietly pick one." So there is no default."""
    with pytest.raises(TypeError):
        engine.observed_yields({"totprods": 5761.0}, 4995.8)
    with pytest.raises(ValueError):
        engine.observed_yields(
            {"totprods": 5761.0}, 4995.8, config.YIELD_BASIS_NORMALISED
        )


def test_a_month_with_no_intake_is_missing_rather_than_a_division_by_zero():
    """SPEC.md section 2 rule 1: a hole is NaN, and never a zero denominator."""
    with pytest.raises(ValueError):
        engine.observed_yields({"totprods": 5761.0}, 0.0, config.YIELD_BASIS_CRUDE_INTAKE)


def test_mass_yields_become_volume_yields_only_with_both_factors():
    """The unit trap inside SPEC.md section 4.5, guarded.

    DGEC's 34.0 percent gazole is a MASS yield. On a barrel basis it is
    0.34 * 7.45 / 7.55 = 0.33550, and multiplying the mass figure by a $/bbl
    crack overstates the gasoil contribution by 1.3 percent.
    """
    volume = engine.mass_yield_to_volume_yield(
        config.DGEC_MASS_YIELDS["gazole"],
        config.BBL_PER_T_GASOIL,
        config.DGEC_BBL_PER_T_BRENT_MARGIN,
    )
    assert volume == pytest.approx(0.335497, abs=1e-6)
    assert volume < config.DGEC_MASS_YIELDS["gazole"]
    with pytest.raises(engine.UnitError):
        engine.mass_yield_to_volume_yield(0.34, 7.45, 0.0)


def test_the_dgec_slate_is_the_one_the_methodology_note_prints():
    """Recon 02 section 5.2, table 1, Rendements massiques, checked line by line."""
    assert config.DGEC_MASS_YIELDS["gazole"] == 0.340
    assert config.DGEC_MASS_YIELDS["eurobob"] == 0.120
    assert config.DGEC_MASS_YIELDS["essence_export"] == 0.119
    assert config.DGEC_MASS_YIELDS["carbureacteur"] == 0.083
    assert config.DGEC_MASS_YIELDS["fod"] == 0.082
    assert config.DGEC_MASS_YIELDS["fioul_lourd_1pct"] == 0.088
    assert config.DGEC_MASS_YIELDS["naphta"] == 0.082
    assert config.DGEC_MASS_YIELDS["gaz_naturel"] == 0.010

    outputs_only = sum(
        value
        for name, value in config.DGEC_MASS_YIELDS.items()
        if name not in ("brent", "gaz_naturel", "combustible_interne_et_pertes")
    )
    # The note's own products sum to 94.5 percent of the tonne.
    assert outputs_only == pytest.approx(0.945, abs=1e-12)


# ---------------------------------------------------------------------------
# SPEC.md section 4.5, the ten year percentile
# ---------------------------------------------------------------------------


def test_the_percentile_is_the_share_at_or_below():
    """The definition the site quotes in a sentence, pinned down."""
    history = [0.0, 1.0, 2.0, 3.0, 4.0]
    assert engine.percentile_rank(2.0, history) == 60.0
    assert engine.percentile_rank(4.0, history) == 100.0
    assert engine.percentile_rank(-1.0, history) == 0.0
    assert engine.percentile_rank(10.0, history) == 100.0


def test_the_percentile_skips_missing_months_and_never_counts_them_as_low():
    """A hole in the history is not a bad month. SPEC.md section 2 rule 1."""
    history = [0.0, math.nan, 2.0, math.nan, 4.0]
    assert engine.percentile_rank(2.0, history) == pytest.approx(66.6667, abs=1e-4)


def test_the_percentile_is_none_when_it_cannot_be_answered():
    """Not 50, not zero. None, and the site says so in words."""
    assert engine.percentile_rank(1.0, []) is None
    assert engine.percentile_rank(1.0, [math.nan, math.nan]) is None
    assert engine.percentile_rank(math.nan, [1.0, 2.0]) is None


def test_the_percentile_window_is_ten_years_of_months():
    assert config.PERCENTILE_WINDOW_YEARS == 10
    assert config.PERCENTILE_WINDOW_MONTHS == 120


# ---------------------------------------------------------------------------
# SPEC.md section 4.5, the outputs bundle the verdict sentence is built from
# ---------------------------------------------------------------------------


def test_outputs_returns_values_and_not_a_sentence():
    """SPEC.md section 4.5: the verdict is assembled from these, never written.

    So the bundle holds numbers and names, and there is no string anywhere in it
    that a designer would be tempted to edit.
    """
    inputs = make_inputs(run_cut_threshold_usd_bbl=2.0)
    history = [1.0, 2.0, 3.0, 4.0, 5.0, math.nan]
    bundle = engine.outputs(inputs, history)

    assert bundle.carrier == "gasoil"
    assert bundle.contributions["gasoil"] == pytest.approx(6.8, abs=1e-12)
    assert bundle.breakeven_ttf_eur_mwh is not None
    assert bundle.breakeven_gasoil_usd_bbl is not None
    assert bundle.percentile_10y == 100.0
    assert bundle.percentile_observations == 5
    assert bundle.headroom_usd_bbl == pytest.approx(
        engine.evaluate(inputs).margin_after_gas_usd_bbl - 2.0, abs=1e-12
    )
    assert bundle.threshold_identified is True


def test_a_threshold_passed_to_outputs_reaches_every_line_of_it():
    """The Model view edits the threshold, so it has to be an argument."""
    inputs = make_inputs(run_cut_threshold_usd_bbl=None)
    bundle = engine.outputs(inputs, [], threshold=1.0)
    assert bundle.threshold_identified is True
    assert bundle.headroom_usd_bbl is not None
    assert bundle.breakeven_ttf_eur_mwh is not None


# ---------------------------------------------------------------------------
# Missing data, once more, at the margin level
# ---------------------------------------------------------------------------


def test_a_missing_gas_price_gives_a_missing_margin_after_gas_and_a_real_gross():
    """The gross margin survives a gas hole, and the site can still show it."""
    inputs = make_inputs(gas=engine.gas_from_ttf(math.nan, 1.10))
    result = engine.evaluate(inputs)
    assert result.gross_margin_usd_bbl == pytest.approx(8.0, abs=1e-12)
    assert math.isnan(result.gas_cost_usd_bbl)
    assert math.isnan(result.margin_after_gas_usd_bbl)


def test_nothing_is_ever_filled_to_keep_a_number_on_the_screen():
    """Every missing input reaches the output as missing. No defaults, anywhere."""
    inputs = make_inputs(residual_usd_bbl=math.nan)
    result = engine.evaluate(inputs)
    assert math.isnan(result.gross_margin_usd_bbl)
    assert math.isnan(result.margin_after_gas_usd_bbl)
    # And a NaN residual does not quietly become a NaN contribution.
    assert result.contributions["gasoil"] == pytest.approx(6.8, abs=1e-12)


# ---------------------------------------------------------------------------
# The engine over the real committed caches, through crack.series
# ---------------------------------------------------------------------------
#
# Everything above this line would pass on an engine that was internally
# consistent and wrong about Rotterdam. These are the ones that would not.


def test_the_engine_reproduces_the_gate_1_weekly_crack_cache_exactly():
    """Two implementations of SPEC.md section 4.2, asked to agree.

    data/cache/dgec_note_reconstructed_cracks_weekly.csv was computed by the
    Gate 1 adapter. crack.series.dgec_weekly_cracks recomputes it from the
    quotation cache through crack.engine. Agreement to 1e-9 over all 219 weeks
    says the engine implements the same definition the committed data was built
    on, including the 7.5 Brent factor, and disagreement would mean one of the
    two has drifted.
    """
    from crack import series

    recomputed = series.dgec_weekly_cracks(recompute=True)
    committed = series.dgec_weekly_cracks(recompute=False)
    assert len(recomputed) == len(committed) == 219

    merged = recomputed.merge(
        committed, on="date", suffixes=("_engine", "_cache")
    )
    assert len(merged) == 219
    for column in ("crack_gasoil_usd_bbl", "crack_gasoline_usd_bbl", "brent_usd_bbl"):
        difference = (
            merged["%s_engine" % column] - merged["%s_cache" % column]
        ).abs().max()
        assert difference < 1e-9, "%s differs by %r" % (column, difference)


def test_the_monthly_crack_series_covers_the_sample_the_owner_chose():
    """2001 onward, which is the Gate 1 decision, and 2020 is in it.

    The OPEC MOMR Rotterdam table starts 2000-10. The owner chose the full
    window over matching the official margin's 2015 start, so the crack series
    has to carry the pandemic year and the test says so rather than assuming it.
    """
    from crack import series

    cracks = series.opec_monthly_cracks()
    assert str(cracks["date"].min().date()) == "2000-10-01"
    assert cracks["date"].max().year >= 2026
    covid = cracks[cracks["date"].dt.strftime("%Y-%m") == "2020-04"]
    assert len(covid) == 1
    assert covid["crack_gasoil_usd_bbl"].notna().all()


def test_every_computed_crack_sits_inside_the_spec_section_5_4_bounds():
    """A units check on 305 months of real data, not a view on the market.

    SPEC.md section 5.4 puts cracks between minus 30 and plus 150 $/bbl. A
    conversion applied where none was needed, or a leg subtracted the wrong way
    round, leaves that band immediately.
    """
    from crack import series

    low, high = config.BOUNDS_CRACK_USD_BBL
    cracks = series.opec_monthly_cracks()
    for column in ("crack_gasoil_usd_bbl", "crack_gasoline_usd_bbl"):
        values = cracks[column].dropna()
        assert len(values) > 250
        assert values.min() > low
        assert values.max() < high


def test_replication_fails_on_every_real_month_and_the_gap_is_reported():
    """SPEC.md section 9's Replication row, measured rather than asserted.

    Six months have both a printed DGEC quotation table and a published MBR.
    On every one of them the full method is NaN, because the PEG Nord gas cost
    and the Aframax freight are not published, and the published only partial
    sits 22 to 40 $/bbl below the official figure. The bar is 0.50.

    This test exists to keep the failure honest. If somebody later fills the
    freight with an estimate, within_bar might start coming back True on some
    month, and this assertion is what says that happened.
    """
    from crack import series

    attempts = series.replication_attempts()
    scored = attempts[attempts["official_usd_bbl"].notna()]
    assert len(scored) >= 6

    assert not scored["within_bar"].any()
    assert scored["margin_usd_bbl"].isna().all()
    assert scored["n_missing_inputs"].min() == 8
    assert (scored["covered_mass_yield"] - 0.595).abs().max() < 1e-9

    worst = scored["partial_error_usd_bbl"].abs().max()
    best = scored["partial_error_usd_bbl"].abs().min()
    assert best > 20.0
    assert worst < 60.0
    # And the official series is untouched by any of it.
    assert scored["official_usd_bbl"].min() > 0.0


def test_the_decomposition_of_october_2022_leaves_a_large_honest_residual():
    """The month SPEC.md section 3 names, taken apart.

    Two priced products out of DGEC's thirteen slate lines cannot explain a
    whole margin, so the residual is large, and it is shown at full size. A
    decomposition that came out neat here would mean something had been fitted.
    """
    from crack import series

    decomposition = series.decomposition_for_month("2022-10")
    assert decomposition.official_usd_bbl > 20.0
    assert set(decomposition.contributions) == {"gasoil", "gasoline"}
    assert decomposition.contributions["gasoil"] > 10.0
    assert (
        decomposition.attributed_usd_bbl + decomposition.residual_usd_bbl
        == pytest.approx(decomposition.official_usd_bbl, abs=1e-12)
    )
    assert decomposition.unattributed_products == series.DGEC_UNATTRIBUTED_SLATE_LINES
    assert decomposition.covered_volume_yield < 0.5


def test_the_decomposition_never_moves_the_official_margin():
    """SPEC.md section 4.3 layer 1, checked against the cache it came from."""
    from crack import series

    margin = series.margin_after_gas_monthly()
    for month in ("2019-06", "2022-10", "2025-06"):
        published = margin[margin["date"].dt.strftime("%Y-%m") == month]
        decomposition = series.decomposition_for_month(month)
        assert decomposition.official_usd_bbl == pytest.approx(
            float(published["mbr_usd_bbl"].iloc[0]), abs=1e-12
        )


def test_the_margin_after_gas_starts_where_the_official_margin_starts():
    """No margin before 2015, and this study does not invent one.

    The Gate 1 decision is explicit: the sample starts in 2001 for the cracks,
    and where the official MBR does not exist before 2015 the study says so
    rather than extending it. This is that sentence as a test.
    """
    from crack import series

    margin = series.margin_after_gas_monthly()
    assert str(margin["date"].min().date()) == "2015-01-01"
    assert margin["mbr_usd_bbl"].notna().all()


def test_both_observed_yield_bases_reproduce_recon_03_on_the_real_caches():
    """Recon 03 section 1.8's two ratios, recomputed from the committed JODI.

    The twelve month rolling figures are not the single month ones recon 03
    printed, so the test checks the bands rather than the four numbers: JODI's
    total product output over crude intake gives about 1.13 to 1.16, and over
    total refinery feed about 1.01 to 1.03. Recon 03's own instruction was not
    to pick one quietly, so both are computed and both are asserted.

    The five named product lines sum to less than either ratio, at about 0.97 on
    crude intake, because they are five of JODI's products and not all of them.
    That is a different number from TOTPRODS and the two are kept in separate
    columns so nobody reads one as the other.
    """
    from crack import series

    on_crude = series.jodi_yields(config.YIELD_BASIS_CRUDE_INTAKE)
    on_feed = series.jodi_yields(config.YIELD_BASIS_TOTAL_FEED)

    crude_ratio = on_crude["totprods_ratio"].dropna()
    feed_ratio = on_feed["totprods_ratio"].dropna()
    assert 1.13 < crude_ratio.median() < 1.16
    assert 1.01 < feed_ratio.median() < 1.03
    assert crude_ratio.median() > feed_ratio.median()

    named = on_crude["total"].dropna()
    assert 0.90 < named.median() < 1.05
    assert named.median() < crude_ratio.median()

    # The cost of the physically right denominator is seven years of history:
    # the gasoil yield on crude intake starts 2002-12 and on total feed 2009-12,
    # because JODI's TOTCRUDE series itself starts in 2009. Measured here rather
    # than quoted, since it is the whole argument against the better
    # denominator.
    first_on_crude = on_crude.loc[on_crude["gasoil"].first_valid_index(), "date"]
    first_on_feed = on_feed.loc[on_feed["gasoil"].first_valid_index(), "date"]
    assert first_on_feed > first_on_crude
    assert str(first_on_crude.date()) == "2002-12-01"
    assert str(first_on_feed.date()) == "2009-12-01"
    # And a third fact neither basis fixes: JODI's naphtha line only starts in
    # 2009, so the five product vector is short on BOTH bases and the four
    # product one is not. The site says which products a yield vector contains.
    assert (
        str(on_crude.loc[on_crude["naphtha"].first_valid_index(), "date"].date())
        == "2009-12-01"
    )


def test_the_latest_view_keeps_its_three_data_dates_apart():
    """SPEC.md section 7.2: the margin date and the runs date are shown separately.

    Today there are three, because the OPEC MOMR issues for April to September
    2026 are not in the Internet Archive, so the crack month sits behind the
    margin month. Nothing is carried forward to hide that.
    """
    from crack import series

    view = series.latest_view()
    assert view.margin_month > view.crack_month
    assert view.runs_data_date < view.margin_month
    assert view.threshold_identified is False
    assert view.headroom_usd_bbl is None
    assert view.percentile_10y is not None
    assert view.carrier in ("gasoil", "gasoline")
    # The whole published margin sits on the residual in a month with no
    # product quotations, rather than being attributed to a product.
    assert view.outputs.contributions == {}
    assert view.outputs.margin.residual_usd_bbl == pytest.approx(
        view.mbr_usd_bbl, abs=1e-12
    )


def test_the_october_2022_triangulation_is_the_same_order_as_s_and_p():
    """SPEC.md section 4.4: report whatever you get, next to S&P's 7 $/bbl.

    What comes out is 6.23 $/bbl, against S&P's roughly 7, on a US average heat
    content for residual fuel oil and a Rotterdam barge assessment. The same
    order of magnitude is the expectation and that is what happened. Nothing was
    moved to land closer.

    ONE ANSWER, WITH THE OTHER ONE LABELLED. Gate 2 self audit, finding 7: this
    repository published 6.23 in docs/methodology.md and 5.51 here, from the same
    cache and the same month, because one was computed on the 3.5 percent
    sulphur fuel oil row and the other on the 1 percent row. The headline is now
    the 3.5 percent row, because a refinery that fires fuel oil burns its own
    heavy residue and because that is the figure this repo published first, and
    the 1 percent figure comes back from the same call as the variant. Both are
    asserted here so neither can move without the other being looked at.
    """
    from crack import series

    triangulation = series.october_2022_triangulation()
    assert triangulation["fuel_oil_basis"] == "fuel_oil_35pct"
    assert triangulation["fuel_oil_usd_bbl"] == pytest.approx(60.75, abs=0.005)
    assert triangulation["gap_usd_bbl"] == pytest.approx(6.23, abs=0.005)
    assert triangulation["sp_global_gap_usd_bbl"] == 7.0
    ratio = triangulation["gap_usd_bbl"] / triangulation["sp_global_gap_usd_bbl"]
    assert 0.5 < ratio < 2.0

    # The variant, in the same mapping, on the low sulphur row the rest of the
    # study cracks. 1.49 below S&P rather than 0.77 below, and the site says
    # which one it is quoting.
    assert triangulation["variant_fuel_oil_basis"] == "fuel_oil_1pct"
    assert triangulation["variant_fuel_oil_usd_bbl"] == pytest.approx(82.06, abs=0.005)
    assert triangulation["variant_gap_usd_bbl"] == pytest.approx(5.51, abs=0.005)


def test_the_triangulation_will_not_pick_a_fuel_oil_row_on_its_own():
    """Asking it on the other row is allowed. Asking it on nothing is not.

    The two rows are 21 $/bbl apart in October 2022 and that is 0.7 $/bbl of
    answer, which is how the repository came to publish two figures for one
    question. A basis it does not recognise is refused rather than defaulted.
    """
    from crack import series

    swapped = series.october_2022_triangulation(fuel_oil_basis="fuel_oil_1pct")
    assert swapped["gap_usd_bbl"] == pytest.approx(5.51, abs=0.005)
    assert swapped["variant_gap_usd_bbl"] == pytest.approx(6.23, abs=0.005)
    assert set(series.FUEL_OIL_TRIANGULATION_BASES) == {
        "fuel_oil_1pct",
        "fuel_oil_35pct",
    }
    with pytest.raises(ValueError):
        series.october_2022_triangulation(fuel_oil_basis="fuel_oil")


# ---------------------------------------------------------------------------
# The headline number itself, pinned to the committed caches
# ---------------------------------------------------------------------------
#
# WHY THIS SECTION EXISTS. The Gate 2 self audit found that the margin after gas
# charged DGEC's published MBR for natural gas a second time, because the MBR is
# already net of the gas the method assumes the refinery buys. The error was
# worth 4.48 $/bbl in the latest month and 14.86 $/bbl in August 2022, and it
# turned the most profitable refining month of a generation into a printed loss
# of 3.69 $/bbl.
#
# All 756 tests passed through it, and so did the parity validator, because not
# one of them asserted the VALUE of the number the whole site is built to print.
# tests asserted that the dates were kept apart, that the residual carried the
# margin, that the threshold was absent. Every number on the landing view was
# unasserted.
#
# So these are the value assertions. They are deliberately tight, they are
# computed from the committed caches, and each one says what it would have
# caught. The next piece of wrong arithmetic in this file's subject is caught
# here or nowhere.

#: The three months the audit measured, with what the double charge did to each:
#: the correct margin after gas, and the figure the old subtraction printed.
PINNED_MARGIN_MONTHS = (
    # month, mbr and margin after gas, the old wrong figure, the overcharge
    ("2026-08", 38.0505, 33.5716, 4.4789),
    ("2022-10", 24.7830, 16.5041, 8.2789),
    ("2022-08", 11.1690, -3.6914, 14.8604),
)


def test_the_margin_after_gas_is_pinned_for_three_real_months():
    """The headline number, to four decimals, on three months of committed cache.

    Gate 2 self audit, finding 1. Each row carries the figure the old, wrong
    subtraction printed as well, and the assertion that the two are far apart,
    so that a re-introduced gas deduction fails here with the size of the error
    in the failure message rather than as a bare inequality.
    """
    from crack import series

    margin = series.margin_after_gas_monthly()
    for month, expected, old_wrong, overcharge in PINNED_MARGIN_MONTHS:
        row = margin[margin["date"].dt.strftime("%Y-%m") == month]
        assert len(row) == 1, month
        row = row.iloc[0]
        assert row["mbr_usd_bbl"] == pytest.approx(expected, abs=5e-5), month
        assert row["margin_after_gas_usd_bbl"] == pytest.approx(
            expected, abs=5e-5
        ), month
        assert row["study_gas_cost_usd_bbl"] == pytest.approx(
            overcharge, abs=5e-5
        ), month
        # The distance from the wrong answer, which is 900 to 300,000 times the
        # tolerance above. Nothing can drift quietly between the two.
        assert abs(row["margin_after_gas_usd_bbl"] - old_wrong) == pytest.approx(
            overcharge, abs=5e-5
        ), month


def test_august_2022_is_a_profit_and_the_old_arithmetic_said_it_was_a_loss():
    """This assertion exists because the bug printed minus 3.69 for this month.

    August 2022 was the most profitable stretch European refining has had in
    modern history: diesel cracks had been at records since the invasion, and
    DGEC's own published margin for the month is plus 11.17 $/bbl. The double
    charged version of this series printed minus 3.69, a loss, and no test
    objected because no test looked at the number.

    A sign of a margin is the cheapest sanity check a refining series has and it
    is the one a reader applies first. If this ever fails, the margin has been
    charged for something twice again, and that is what to look for.
    """
    from crack import series

    margin = series.margin_after_gas_monthly()
    august = margin[margin["date"].dt.strftime("%Y-%m") == "2022-08"].iloc[0]
    assert august["margin_after_gas_usd_bbl"] > 0.0
    assert august["margin_after_gas_usd_bbl"] == pytest.approx(11.1690, abs=5e-5)
    # The whole of 2022 was positive on the official series. A month of 2022
    # coming back negative is the fingerprint of the bug that was fixed.
    year = margin[margin["date"].dt.year == 2022]
    assert len(year) == 12
    assert (year["margin_after_gas_usd_bbl"] > 0.0).all()


def test_the_margin_after_gas_is_the_mbr_exactly_when_nothing_else_is_charged():
    """The property that makes a re-introduced gas subtraction impossible to miss.

    SPEC.md section 4.4's other_variable_cost defaults to zero, and DGEC's MBR
    is already net of gas, so with nothing else charged the margin after gas IS
    the published margin, bit for bit, in every month of the series. Not close:
    equal. Any deduction of any size, on any month, breaks this.

    The second half is the same statement with a cost put back on: charge 1.25
    $/bbl and every month moves by exactly 1.25 and by nothing else, so the
    property survives being used rather than only holding at the default.
    """
    from crack import series

    margin = series.margin_after_gas_monthly()
    assert len(margin) > 130
    assert (margin["other_variable_cost_usd_bbl"] == 0.0).all()
    assert (margin["margin_basis"] == engine.MARGIN_NET_OF_GAS).all()
    assert (margin["margin_after_gas_usd_bbl"] == margin["mbr_usd_bbl"]).all()

    charged = series.margin_after_gas_monthly(other_variable_cost_usd_bbl=1.25)
    difference = charged["mbr_usd_bbl"] - charged["margin_after_gas_usd_bbl"]
    assert (difference == 1.25).all()
    # And the gas price still moves nothing, which is the point of the basis.
    assert (charged["gas_usd_mmbtu"] == margin["gas_usd_mmbtu"]).all()


def test_the_monthly_column_and_the_engine_cannot_disagree_about_the_margin():
    """One implementation, checked month by month. Gate 2 self audit, finding 3.

    The series column used to be computed in pandas and the landing sentence in
    crack.engine, the same three terms twice, with nothing comparing them. The
    audit flipped a sign inside engine.evaluate and watched the two disagree by
    76 $/bbl with four tests failing, three of which were a byte comparison that
    fires for any edit at all.

    The column is now taken off engine.evaluate, so this test is a guard on that
    staying true rather than a comparison of two implementations: it rebuilds
    every month independently, through the public engine entry point, and asks
    for bit equality.
    """
    from crack import series

    margin = series.margin_after_gas_monthly()
    for _, row in margin.iterrows():
        inputs = series.net_of_gas_margin_inputs(
            float(row["mbr_usd_bbl"]), float(row["other_variable_cost_usd_bbl"])
        )
        assert engine.evaluate(inputs).margin_after_gas_usd_bbl == float(
            row["margin_after_gas_usd_bbl"]
        ), str(row["date"])


def test_the_margin_series_has_no_column_called_gas_cost():
    """The name meant the thing that was wrong. It is not reused for a new thing.

    Gate 2 self audit, finding 1. The column named gas_cost_usd_bbl carried the
    deduction that should never have been made. Redefining the name to mean one
    of the two honest figures would leave every caller, every chart label and
    every future reader believing the old thing. So it was deleted, and a caller
    has to say which of the two intensities it means: what DGEC's method has
    inside it, or what this study's EIA derived intensity would cost.
    """
    from crack import series

    margin = series.margin_after_gas_monthly()
    assert "gas_cost_usd_bbl" not in margin.columns
    assert set(margin.columns) == {
        "date",
        "mbr_usd_bbl",
        "gas_usd_mmbtu",
        "embedded_gas_cost_usd_bbl",
        "study_gas_cost_usd_bbl",
        "gas_wedge_usd_bbl",
        "margin_after_gas_usd_bbl",
        "other_variable_cost_usd_bbl",
        "margin_basis",
    }
    view = series.latest_view()
    assert not hasattr(view, "gas_cost_usd_bbl")
    assert isinstance(view.gas_wedge, engine.GasWedge)


def test_a_net_of_gas_margin_refuses_a_gas_price_and_a_gross_one_takes_it():
    """The refusal that makes the double charge inexpressible, and its opposite.

    engine.MarginInputs raises GasDoubleCountError for a gas term on a margin
    that already contains one. It has to raise on exactly that and on nothing
    else: a margin this study builds itself out of cracks and yields is gross of
    gas, SPEC.md section 4.4's subtraction is right for it, and a guard that
    refused both would have deleted the model rather than fixed it.
    """
    with pytest.raises(engine.GasDoubleCountError):
        engine.MarginInputs(
            yields={},
            cracks={},
            gas=engine.gas_from_usd_mmbtu(21.11),
            residual_usd_bbl=38.0505047,
            gas_intensity_mmbtu_per_bbl=config.GAS_INTENSITY_MMBTU_PER_BBL,
            margin_basis=engine.MARGIN_NET_OF_GAS,
        )
    # A NaN gas price is refused too. NaN times the intensity is not zero, and a
    # margin that is in fact complete must not come back NaN.
    with pytest.raises(engine.GasDoubleCountError):
        engine.MarginInputs(
            yields={},
            cracks={},
            gas=engine.gas_from_usd_mmbtu(math.nan),
            residual_usd_bbl=38.0505047,
            gas_intensity_mmbtu_per_bbl=config.GAS_INTENSITY_MMBTU_PER_BBL,
            margin_basis=engine.MARGIN_NET_OF_GAS,
        )

    # The same price and the same intensity on a gross margin: accepted, and the
    # gas is subtracted, because on that basis it has not been subtracted yet.
    gross = engine.MarginInputs(
        yields={"gasoil": 0.3355},
        cracks={"gasoil": 22.0},
        gas=engine.gas_from_usd_mmbtu(21.11),
        gas_intensity_mmbtu_per_bbl=config.GAS_INTENSITY_MMBTU_PER_BBL,
        margin_basis=engine.MARGIN_GROSS_OF_GAS,
    )
    result = engine.evaluate(gross)
    assert result.gas_cost_usd_bbl == pytest.approx(
        config.GAS_INTENSITY_MMBTU_PER_BBL * 21.11, abs=1e-12
    )
    assert result.gas_cost_usd_bbl > 4.0
    assert result.margin_after_gas_usd_bbl == pytest.approx(
        result.gross_margin_usd_bbl - result.gas_cost_usd_bbl, abs=1e-12
    )
    # And the default basis is the gross one, so nothing had to opt in to the
    # ordinary case.
    assert engine.MarginInputs(yields={}, cracks={}).margin_basis == (
        engine.MARGIN_GROSS_OF_GAS
    )


def test_the_gas_wedge_is_pinned_on_the_two_months_the_audit_measured():
    """The honest gas story, as numbers, on the committed caches.

    Two intensities at one gas price. DGEC's embedded assumption is 1.0 percent
    of the tonne of crude at the method's own 7.55 bbl/t, which is 0.0659
    MMBtu/bbl; this study's EIA derived figure is 0.21217, about 3.2 times as
    much. The wedge is what a refinery buying gas at this study's intensity pays
    over DGEC's model refinery, and it is a comparison, never a line of the
    margin.

    August 2022 is in here because it is the month that matters: gas at 70.04
    $/MMBtu, DGEC's own assumption already costing 4.62 $/bbl inside the
    published margin, and this study's intensity costing 14.86.
    """
    from crack import series

    margin = series.margin_after_gas_monthly()
    expected = {
        # month: gas price, embedded cost, study cost, wedge
        "2026-08": (21.11, 1.391, 4.479, 3.088),
        "2022-08": (70.04, 4.616, 14.860, 10.245),
    }
    for month, (gas, embedded, study, wedge) in expected.items():
        row = margin[margin["date"].dt.strftime("%Y-%m") == month].iloc[0]
        assert row["gas_usd_mmbtu"] == pytest.approx(gas, abs=5e-3), month
        assert row["embedded_gas_cost_usd_bbl"] == pytest.approx(
            embedded, abs=5e-4
        ), month
        assert row["study_gas_cost_usd_bbl"] == pytest.approx(study, abs=5e-4), month
        assert row["gas_wedge_usd_bbl"] == pytest.approx(wedge, abs=5e-4), month
        # The wedge is the difference of the two costs. Checked against the two
        # figures above rather than against the column's own arithmetic, so the
        # tolerance carries the rounding of both of them.
        assert row["gas_wedge_usd_bbl"] == pytest.approx(
            study - embedded, abs=2e-3
        ), month

    assert config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL == pytest.approx(
        0.06590, abs=5e-6
    )
    # The same figures through the engine record the landing view carries.
    wedge = engine.gas_wedge(
        70.04,
        config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL,
        config.GAS_INTENSITY_MMBTU_PER_BBL,
    )
    assert wedge.embedded_cost_usd_bbl == pytest.approx(4.616, abs=5e-4)
    assert wedge.study_cost_usd_bbl == pytest.approx(14.860, abs=5e-4)
    assert wedge.wedge_usd_bbl == pytest.approx(10.245, abs=5e-4)
    assert wedge.ratio == pytest.approx(3.2194, abs=5e-4)


def test_what_the_old_subtraction_was_worth_across_the_whole_sample():
    """The size of the correction, measured, so it cannot be called cosmetic.

    The deduction that used to be applied was this study's intensity times the
    gas price, month by month. At its worst it was 14.86 $/bbl, in August 2022,
    and on average across 140 months it was 2.47 $/bbl. The mean is more than a
    tenth of the mean margin, and the worst is larger than most months' margin.
    """
    from crack import series

    margin = series.margin_after_gas_monthly()
    overcharge = margin["study_gas_cost_usd_bbl"]
    assert overcharge.max() == pytest.approx(14.8604, abs=5e-5)
    assert margin.loc[overcharge.idxmax(), "date"].strftime("%Y-%m") == "2022-08"
    assert overcharge.mean() == pytest.approx(2.4713, abs=5e-5)
    assert overcharge.min() > 0.0


def test_the_landing_view_numbers_are_asserted_and_not_only_its_dates():
    """Every number the landing sentence is built from, pinned.

    Gate 2 self audit, finding 3, root cause: the only test of latest_view
    asserted the three data dates, the carrier, the absent threshold and the
    empty contributions, and never once a value. The 14.86 $/bbl error went
    through this function into the headline sentence with the suite green.
    """
    from crack import series

    view = series.latest_view()
    assert view.margin_month == "2026-08-01"
    assert view.mbr_usd_bbl == pytest.approx(38.0505, abs=5e-5)
    assert view.margin_after_gas_usd_bbl == pytest.approx(38.0505, abs=5e-5)
    assert view.margin_after_gas_usd_bbl == view.mbr_usd_bbl
    assert view.gas_usd_mmbtu == pytest.approx(21.11, abs=5e-3)
    assert view.gas_wedge.wedge_usd_bbl == pytest.approx(3.0877, abs=5e-4)
    assert view.percentile_10y == pytest.approx(100.0, abs=1e-9)
    assert view.percentile_observations == 120
    assert view.outputs.percentile_window_months == config.PERCENTILE_WINDOW_MONTHS

    # The same number as the series column for the same month, which is the
    # comparison that was missing.
    margin = series.margin_after_gas_monthly()
    row = margin[margin["date"].dt.strftime("%Y-%m-%d") == view.margin_month].iloc[0]
    assert view.margin_after_gas_usd_bbl == float(row["margin_after_gas_usd_bbl"])
    assert view.gas_wedge.wedge_usd_bbl == pytest.approx(
        float(row["gas_wedge_usd_bbl"]), abs=1e-12
    )

    # And the crack month's decomposition, which is the other half of the
    # sentence: which crack is carrying the barrel, and by how much.
    assert view.crack_month == "2026-02-01"
    assert view.carrier == "gasoil"
    assert view.decomposition.contributions["gasoil"] == pytest.approx(
        7.9623, abs=5e-4
    )
    assert view.decomposition.contributions["gasoline"] == pytest.approx(
        2.2207, abs=5e-4
    )
    assert view.decomposition.official_usd_bbl == pytest.approx(6.5015, abs=5e-4)
    # Two priced lines out of thirteen already outweigh the whole margin, so the
    # residual is large and negative and is shown at full size. SPEC.md section
    # 4.3 layer 3, and the audit's own point about not tidying it away.
    assert view.decomposition.residual_usd_bbl == pytest.approx(-3.6815, abs=5e-4)


def test_the_latest_view_cracks_are_the_cracks_and_not_a_recovered_ratio():
    """Gate 2 self audit, finding 16, as a value test.

    latest_view used to rebuild its cracks as contribution divided by yield,
    which is the yield multiplied and then divided again, and a division by zero
    on the day a slate line comes out at zero. They now come from the same
    function the decomposition uses. The two agree today; this asserts they are
    the same numbers rather than nearly the same numbers.
    """
    from crack import series

    view = series.latest_view()
    cracks = series.cracks_for_month(view.crack_month[:7])
    assert set(cracks) == {"gasoil", "gasoline"}
    for name, value in cracks.items():
        # The contribution is the yield times the crack, and the crack the view
        # carries is the crack itself rather than the contribution divided back.
        assert view.decomposition.contributions[name] == (
            series.DGEC_VOLUME_YIELDS[name] * value
        )
        assert view.decomposition_outputs.margin.contributions[name] == (
            series.DGEC_VOLUME_YIELDS[name] * value
        )

    # The case the old recovery could not survive, stated as arithmetic: a
    # product with a zero yield contributes zero, and dividing that back by the
    # yield to recover its crack is a division by zero.
    zero_yield_contribution = 0.0 * 22.0
    with pytest.raises(ZeroDivisionError):
        zero_yield_contribution / 0.0
