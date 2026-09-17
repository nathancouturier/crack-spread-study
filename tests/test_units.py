"""The units gate. SPEC.md section 9, and its last line: write this test first.

This file was written before src/crack/engine.py existed, which is what SPEC.md
section 9 asks for, and it is the reason the engine has the shape it has rather
than the other way round.

What it guards
--------------
Two rows of the SPEC.md section 9 table live here, because both are statements
about units rather than about the margin model:

    Units      745 $/t of gasoil against Brent at 80 $/bbl is a crack of
               EXACTLY 20 $/bbl, and 833 $/t of gasoline against the same Brent
               is EXACTLY 20 too. SPEC.md calls a wrong conversion factor "the
               most common error in this study" and this is the test that
               catches it.
    Intensity  the derived gas intensity lands inside 0.12 to 0.30 MMBtu per
               barrel, SPEC.md section 4.4.

Exactly means exactly. Not pytest.approx. 745 / 7.45 is 100.0 to the last bit
in IEEE 754 double precision, and so is 833 / 8.33, so an equality assertion is
the right one here and a tolerance would let a factor drift into the fourth
decimal without anybody noticing. If a future change to the conversion path
makes this test need a tolerance, the change is the thing to look at.

The second half of the file is the units chain the margin depends on: euros per
megawatt hour to dollars per million Btu, and dollars per million Btu to dollars
per barrel of crude. SPEC.md section 9's Linearity row tests the derivative of
that chain inside the engine; here the chain itself is checked against a hand
computed value, so that a sign error and a factor error cannot cancel.
"""

from __future__ import annotations

import math

import pytest

from crack import config, engine


# ---------------------------------------------------------------------------
# SPEC.md section 9, the Units row
# ---------------------------------------------------------------------------


def test_gasoil_745_against_brent_80_is_exactly_20():
    """745 $/t over 7.45 bbl/t is 100 $/bbl, minus Brent 80, is exactly 20."""
    got = engine.crack_from_usd_t(
        745.0, config.BBL_PER_T_GASOIL, 80.0
    )
    assert got == 20.0


def test_gasoline_833_against_brent_80_is_exactly_20():
    """833 $/t over 8.33 bbl/t is 100 $/bbl, minus Brent 80, is exactly 20."""
    got = engine.crack_from_usd_t(
        833.0, config.BBL_PER_T_GASOLINE, 80.0
    )
    assert got == 20.0


def test_the_two_factors_are_the_ones_spec_section_4_1_fixes():
    """The constants themselves, so a change to them fails here by name.

    SPEC.md section 4.1 fixes both values and the Gate 2 brief repeats that
    neither may be tuned. The 44 month measurement behind each one is written
    out in config.py next to the constant.
    """
    assert config.BBL_PER_T_GASOIL == 7.45
    assert config.BBL_PER_T_GASOLINE == 8.33


def test_the_quote_path_gives_the_same_exact_answer_as_the_scalar_path():
    """The two spellings of the same arithmetic must not drift apart.

    engine.crack_from_usd_t takes three numbers. engine.crack takes two dated
    quotations and refuses to compute across a date or a window boundary,
    SPEC.md section 4.2. They have to agree bit for bit, or the alignment
    machinery would be buying safety with a different answer.
    """
    gasoil = engine.Quote(745.0, engine.USD_PER_T, "2026-07-01", engine.MONTHLY, "Gazole")
    brent = engine.Quote(80.0, engine.USD_PER_BBL, "2026-07-01", engine.MONTHLY, "Brent date")
    result = engine.crack(gasoil, brent, product_bbl_per_t=config.BBL_PER_T_GASOIL)
    assert result.value == 20.0
    assert result.value == engine.crack_from_usd_t(745.0, config.BBL_PER_T_GASOIL, 80.0)


def test_a_product_already_in_dollars_per_barrel_is_not_converted_at_all():
    """The OPEC path. SPEC.md section 4.2, and the Gate 2 brief on it.

    The OPEC MOMR Rotterdam table is already in $/bbl. Dividing it by 7.45
    would be the same class of error the Units row exists to catch, one
    direction further on, so the two paths are separate functions and the
    result says which one produced it.
    """
    got = engine.crack_from_usd_bbl(100.0, 80.0)
    assert got == 20.0

    product = engine.Quote(100.0, engine.USD_PER_BBL, "2026-07-01", engine.MONTHLY, "Gasoil")
    brent = engine.Quote(80.0, engine.USD_PER_BBL, "2026-07-01", engine.MONTHLY, "Brent")
    result = engine.crack(product, brent)
    assert result.value == 20.0
    assert result.product_basis == engine.BASIS_DIRECT
    assert result.product_bbl_per_t is None


def test_converting_a_dollars_per_barrel_quote_again_is_refused():
    """A factor handed to a quote that needs none is an error, not a courtesy."""
    product = engine.Quote(100.0, engine.USD_PER_BBL, "2026-07-01", engine.MONTHLY)
    brent = engine.Quote(80.0, engine.USD_PER_BBL, "2026-07-01", engine.MONTHLY)
    with pytest.raises(engine.UnitError):
        engine.crack(product, brent, product_bbl_per_t=config.BBL_PER_T_GASOIL)


def test_a_dollars_per_tonne_quote_without_a_factor_is_refused():
    """And the reverse. Silence here would be a crack about 7.45 times too big."""
    product = engine.Quote(745.0, engine.USD_PER_T, "2026-07-01", engine.MONTHLY)
    brent = engine.Quote(80.0, engine.USD_PER_BBL, "2026-07-01", engine.MONTHLY)
    with pytest.raises(engine.UnitError):
        engine.crack(product, brent)


def test_the_dgec_brent_column_converts_with_the_note_factor_not_the_margin_one():
    """Two DGEC Brent factors exist and they are used in different places.

    recon 02 section 5.4. 7.5 converts the note's own $/t Brent column back to
    $/bbl; 7.55 is the factor inside the MBR method. Using one where the other
    belongs is about 0.56 $/bbl on the crude leg at a Brent of 84, and it would
    be silent. The July 2026 anchor of SPEC.md section 5.5 prints Brent date at
    628 $/t, which is 83.733 $/bbl on the note factor.
    """
    assert config.DGEC_BBL_PER_T_BRENT_NOTE == 7.5
    assert config.DGEC_BBL_PER_T_BRENT_MARGIN == 7.55
    assert config.DGEC_BBL_PER_T_BRENT_NOTE != config.DGEC_BBL_PER_T_BRENT_MARGIN

    brent = engine.Quote(628.0, engine.USD_PER_T, "2026-07-01", engine.MONTHLY, "Brent date")
    on_note_factor = engine.to_usd_bbl(brent, config.DGEC_BBL_PER_T_BRENT_NOTE)
    on_margin_factor = engine.to_usd_bbl(brent, config.DGEC_BBL_PER_T_BRENT_MARGIN)
    assert on_note_factor == pytest.approx(83.7333333, abs=1e-6)
    # The size of the mistake, stated rather than implied.
    assert abs(on_note_factor - on_margin_factor) == pytest.approx(0.5545, abs=1e-3)


# ---------------------------------------------------------------------------
# The units chain the margin depends on, SPEC.md section 4.4
# ---------------------------------------------------------------------------


def test_mmbtu_per_mwh_is_the_unit_definition():
    """1 MWh is 3.6e9 J and 1 MMBtu(IT) is 1.05505585262e9 J."""
    assert config.MMBTU_PER_MWH == 3.412142
    exact = 3.6e9 / 1.05505585262e9
    assert abs(config.MMBTU_PER_MWH - exact) < 1e-6


def test_the_gas_chain_reproduces_a_hand_computed_value():
    """TTF at 40 EUR/MWh with EURUSD at 1.10 is 12.8951 $/MMBtu.

    40 * 1.10 = 44 $/MWh, and 44 / 3.412142 = 12.8951257 $/MMBtu. Computed
    here by hand rather than by calling the engine twice, which would prove
    only that the engine agrees with itself.
    """
    gas = engine.gas_from_ttf(40.0, 1.10)
    assert gas.gas_usd_mmbtu == pytest.approx(44.0 / 3.412142, rel=0, abs=1e-12)
    assert gas.gas_usd_mmbtu == pytest.approx(12.8951257, abs=1e-6)
    assert gas.basis == engine.GAS_BASIS_TTF


def test_the_world_bank_path_does_no_conversion_at_all():
    """The pink sheet Europe gas series is ALREADY $/MMBtu, recon 04 section 4.1.

    Running it through the EUR/MWh chain would divide a dollar figure by 3.41
    for no reason. The two paths are separate constructors and the result says
    which one built it.
    """
    gas = engine.gas_from_usd_mmbtu(12.895203)
    assert gas.gas_usd_mmbtu == 12.895203
    assert gas.basis == engine.GAS_BASIS_PUBLISHED
    assert gas.ttf_eur_mwh is None
    assert gas.eurusd is None


def test_gas_cost_per_barrel_is_intensity_times_the_gas_price():
    """0.21217 MMBtu/bbl at 12.8951257 $/MMBtu is 2.7360 $/bbl."""
    got = engine.gas_cost_usd_bbl(config.GAS_INTENSITY_MMBTU_PER_BBL, 12.8951257)
    assert got == pytest.approx(0.21217 * 12.8951257, abs=1e-12)
    assert got == pytest.approx(2.73596, abs=1e-4)


# ---------------------------------------------------------------------------
# SPEC.md section 9, the Intensity row
# ---------------------------------------------------------------------------


def test_gas_intensity_is_inside_the_spec_band():
    """SPEC.md section 4.4: outside 0.12 to 0.30, stop and show your working."""
    low, high = config.GAS_INTENSITY_BAND
    assert low == 0.12 and high == 0.30
    assert low < config.GAS_INTENSITY_MMBTU_PER_BBL < high


def test_gas_intensity_is_derived_from_the_eia_numbers_not_typed():
    """Recompute it from the four EIA constants and check the stored value.

    SPEC.md section 4.4 says the intensity is derived, not typed. This is the
    derivation, done here from the cited inputs rather than trusted:

        (1,021,246 + 172,313) MMcf x 1e6 cf/MMcf x 1,036 Btu/cf / 1e6 Btu/MMBtu
        divided by 5,827,889 x 1e3 barrels
    """
    mmcf = (
        config.EIA_REFINERY_FUEL_GAS_MMCF_2023
        + config.EIA_HYDROGEN_FEEDSTOCK_GAS_MMCF_2023
    )
    mmbtu = mmcf * 1e6 * config.EIA_GAS_HEAT_CONTENT_BTU_PER_CF_2023 / 1e6
    barrels = config.EIA_CRUDE_INPUTS_THOUSAND_BBL_2023 * 1e3
    derived = mmbtu / barrels

    assert derived == pytest.approx(0.2121741, abs=1e-7)
    # The stored constant is that derivation rounded to five decimals, and it
    # must not have drifted from it by more than the rounding.
    assert abs(derived - config.GAS_INTENSITY_MMBTU_PER_BBL) < 5e-6
    low, high = config.GAS_INTENSITY_BAND
    assert low < derived < high


def test_the_two_neighbouring_intensities_are_reported_and_differ():
    """Recon 03 section 3.6 keeps both alternatives visible, never used.

    Fuel gas only drops about 15 percent; the gross input denominator moves it
    about 3 percent. Both are in config.py so that the choice is visible as a
    choice.
    """
    assert config.GAS_INTENSITY_FUEL_ONLY_MMBTU_PER_BBL < config.GAS_INTENSITY_MMBTU_PER_BBL
    assert config.GAS_INTENSITY_GROSS_INPUT_MMBTU_PER_BBL < config.GAS_INTENSITY_MMBTU_PER_BBL
    for alternative in (
        config.GAS_INTENSITY_FUEL_ONLY_MMBTU_PER_BBL,
        config.GAS_INTENSITY_GROSS_INPUT_MMBTU_PER_BBL,
    ):
        low, high = config.GAS_INTENSITY_BAND
        assert low < alternative < high


# ---------------------------------------------------------------------------
# Missing is missing, in the units layer too
# ---------------------------------------------------------------------------


def test_a_missing_price_gives_a_missing_crack_and_never_a_zero():
    """SPEC.md section 2 rule 1. NaN in, NaN out, no exception, no fill."""
    assert math.isnan(engine.crack_from_usd_t(math.nan, config.BBL_PER_T_GASOIL, 80.0))
    assert math.isnan(engine.crack_from_usd_t(745.0, config.BBL_PER_T_GASOIL, math.nan))
    assert math.isnan(engine.crack_from_usd_bbl(math.nan, 80.0))
    assert math.isnan(engine.gas_from_ttf(math.nan, 1.10).gas_usd_mmbtu)
    assert math.isnan(engine.gas_cost_usd_bbl(config.GAS_INTENSITY_MMBTU_PER_BBL, math.nan))


def test_a_zero_conversion_factor_is_an_error_rather_than_an_infinity():
    """Python would raise and JavaScript would return Infinity.

    SPEC.md section 7.1 makes the two engines agree to 1e-9, and Infinity is
    not a number either of them should produce from a factor, so the guard is
    explicit and both sides carry it.
    """
    with pytest.raises(engine.UnitError):
        engine.crack_from_usd_t(745.0, 0.0, 80.0)


# ---------------------------------------------------------------------------
# The Units row at the CALL SITES, which is where the error is actually made
# ---------------------------------------------------------------------------
#
# Gate 2 self audit, finding 2. Everything above this line guards the CONSTANTS:
# change 7.45 to 7.55 and six tests fail by name. That is the version of the
# mistake nobody makes. The version people make is using the right constant in
# the wrong place, and the audit proved that one was invisible: building
# series.DGEC_VOLUME_YIELDS["gasoline"] on BBL_PER_T_GASOIL instead of
# BBL_PER_T_GASOLINE moved October 2022's gasoline contribution by 0.61 $/bbl,
# moved the residual on the one month the site exists to explain by the same
# amount, and 756 tests and the parity validator all stayed green.
#
# SPEC.md section 9's Units row says it catches "a wrong conversion factor, the
# most common error in this study". These are the tests that make that true of
# the places the factors are used, not only of the places they are defined.
#
# Every one of them recomputes the number from the cited factor by hand and
# compares. None of them asks the engine to agree with itself.


def test_every_dgec_volume_yield_is_built_on_its_own_products_factor():
    """The gasoline yield uses 8.33, the gasoil yield uses 7.45, and they differ.

    A volumetric yield is mass_yield * bbl_per_t_product / bbl_per_t_crude, so
    the product factor is a multiplier on a number that multiplies a crack in
    every month of the decomposition. Swapping the two is an 11 percent error on
    the gasoline line and it does not raise, does not go out of range and does
    not look wrong.
    """
    from crack import series

    gasoil = config.DGEC_MASS_YIELDS["gazole"] * config.BBL_PER_T_GASOIL / 7.55
    gasoline = config.DGEC_MASS_YIELDS["eurobob"] * config.BBL_PER_T_GASOLINE / 7.55
    assert config.DGEC_BBL_PER_T_BRENT_MARGIN == 7.55

    assert series.DGEC_VOLUME_YIELDS["gasoil"] == pytest.approx(gasoil, abs=1e-15)
    assert series.DGEC_VOLUME_YIELDS["gasoline"] == pytest.approx(gasoline, abs=1e-15)
    assert series.DGEC_VOLUME_YIELDS["gasoil"] == pytest.approx(0.3354967, abs=1e-7)
    assert series.DGEC_VOLUME_YIELDS["gasoline"] == pytest.approx(0.1323974, abs=1e-7)

    # And the wrong factor, stated as a number so this test says what it is
    # defending against. On the gasoil factor the gasoline yield would be
    # 0.1184, which is 0.014 of a barrel and about 11 percent low.
    on_the_wrong_factor = (
        config.DGEC_MASS_YIELDS["eurobob"] * config.BBL_PER_T_GASOIL / 7.55
    )
    assert on_the_wrong_factor == pytest.approx(0.1184106, abs=1e-7)
    assert abs(series.DGEC_VOLUME_YIELDS["gasoline"] - on_the_wrong_factor) > 0.013


def test_the_october_2022_gasoline_contribution_is_pinned_to_the_cent():
    """The month SPEC.md section 3 names, on the line the wrong factor moves.

    5.7842 $/bbl of gasoline and a residual of minus 4.3411 $/bbl. The audit
    measured that the gasoil factor on the gasoline yield gives 5.1731 and
    minus 3.7300 instead, 0.61 $/bbl on both, with every other check in this
    repository still passing. This assertion is the one that would have caught
    it, and it is tight enough that a factor error cannot hide inside it.
    """
    from crack import series

    decomposition = series.decomposition_for_month("2022-10")
    assert decomposition.contributions["gasoline"] == pytest.approx(5.7842, abs=5e-4)
    assert decomposition.contributions["gasoil"] == pytest.approx(23.3399, abs=5e-4)
    assert decomposition.residual_usd_bbl == pytest.approx(-4.3411, abs=5e-4)
    # The distance to the wrong factor's answer, so the tolerance above is
    # visibly smaller than the error it has to catch: 0.61 against 0.0005.
    assert abs(decomposition.contributions["gasoline"] - 5.1731) > 0.6


def test_the_weekly_crack_call_sites_use_three_different_factors_correctly():
    """Three factors meet in one row of the weekly series and none is the others.

    crack.series.dgec_weekly_cracks divides Gazole by 7.45, Eurosuper by 8.33
    and the same Brent column by 7.5, the note's own factor. The audit put the
    gasoil factor on the gasoline leg and exactly one test fired, and it fired
    by the accident of Gate 1 having committed a derived cache to compare
    against. This one recomputes the latest week from the quotation cache by
    hand, with the factors written out as literals, so it fires on its own.
    """
    from crack import series

    quotes = series.load("dgec_note_reconstructed_weekly")
    computed = series.dgec_weekly_cracks(recompute=True)
    row = quotes.iloc[-1]
    got = computed.iloc[-1]
    assert got["date"] == row["date"]

    brent_usd_bbl = float(row["brent_date_usd_t"]) / 7.5
    gasoil = float(row["gazole_usd_t"]) / 7.45 - brent_usd_bbl
    gasoline = float(row["eurosuper_usd_t"]) / 8.33 - brent_usd_bbl

    assert got["brent_usd_bbl"] == pytest.approx(brent_usd_bbl, abs=1e-12)
    assert got["crack_gasoil_usd_bbl"] == pytest.approx(gasoil, abs=1e-12)
    assert got["crack_gasoline_usd_bbl"] == pytest.approx(gasoline, abs=1e-12)

    # The gasoil factor on the gasoline leg is worth Eurosuper times
    # (1/7.45 - 1/8.33), about 0.014 $/bbl per 1 $/t, so over 18 $/bbl on a week
    # near 1,300 $/t, and it would still be inside the SPEC.md section 5.4
    # bounds. The size is computed for the week at hand, because the latest week
    # changes with every note collected.
    on_the_wrong_factor = float(row["eurosuper_usd_t"]) / 7.45 - brent_usd_bbl
    size = float(row["eurosuper_usd_t"]) * (1 / 7.45 - 1 / 8.33)
    assert abs(gasoline - on_the_wrong_factor) == pytest.approx(size, abs=1e-9)
    assert size > 5.0, "the wrong factor must move the crack by far more than rounding"


def test_the_opec_call_site_converts_nothing_at_all():
    """The other half of the same error: converting a price that is already right.

    The OPEC MOMR Rotterdam table is in $/bbl. crack.series.opec_monthly_cracks
    must hand engine.crack no factor at all, and the recomputed crack must be
    the plain difference of the two published columns. A stray 7.45 here would
    divide a 90 $/bbl gasoil price into 12 and nothing else in the suite would
    mind.
    """
    from crack import series

    cracks = series.opec_monthly_cracks()
    row = cracks[cracks["date"].dt.strftime("%Y-%m") == "2022-10"].iloc[0]
    assert row["crack_gasoil_usd_bbl"] == pytest.approx(
        float(row["gasoil_usd_bbl"]) - float(row["brent_usd_bbl"]), abs=1e-12
    )
    assert row["crack_gasoline_usd_bbl"] == pytest.approx(
        float(row["gasoline_usd_bbl"]) - float(row["brent_usd_bbl"]), abs=1e-12
    )
    assert row["crack_gasoil_usd_bbl"] > 50.0
