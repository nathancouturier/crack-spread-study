"""Gate 4. The landing month taken apart with the ministry's own quotations.

The Gate 4 design plan said August 2026 could not be decomposed because no
product prices existed for it. They do: the DGEC note of 4 September 2026 prints
FINAL August monthly averages, data/cache/dgec_note_printed_monthly.csv. These
tests pin what that decomposition gives, the cited factors it runs on, and the
things it refuses to do.
"""

from __future__ import annotations

import math

import pytest

from crack import config, engine, series

AUGUST = "2026-08"


def test_the_three_new_factors_are_the_ice_contract_figures_and_nothing_else():
    # ICE Futures Europe contract specifications, read 2026-09-16:
    #   6753303 Jet CIF NWE Cargoes vs Brent        1 metric tonne = 7.88 barrels
    #   6753295 Gasoil 0.1% FOB ARA Barges vs Brent 1 metric tonne = 7.45 barrels
    #   6753289 Fuel Oil 1% FOB NWE Cargoes vs Brent 1 metric tonne = 6.35 barrels
    assert config.BBL_PER_T_JET == 7.88
    assert config.BBL_PER_T_HEATING_OIL == 7.45
    assert config.BBL_PER_T_FUEL_OIL_1PCT == 6.35
    assert dict(config.DGEC_NOTE_PRODUCT_BBL_PER_T) == {
        "gasoil": 7.45,
        "gasoline": 8.33,
        "jet": 7.88,
        "heating_oil": 7.45,
        "fuel_oil_1pct": 6.35,
    }
    assert dict(config.DGEC_NOTE_SLATE_LINE) == {
        "gasoil": "gazole",
        "gasoline": "eurobob",
        "jet": "carbureacteur",
        "heating_oil": "fod",
        "fuel_oil_1pct": "fioul_lourd_1pct",
    }


def test_the_opec_path_did_not_move():
    """Additive. The two product mapping that feeds the parity fixture is untouched."""
    assert dict(config.PRODUCT_BBL_PER_T) == {"gasoil": 7.45, "gasoline": 8.33}
    assert set(series.DGEC_VOLUME_YIELDS) == {"gasoil", "gasoline"}


def test_august_2026_cracks_from_the_printed_quotations():
    cracks = series.note_cracks_for_month(AUGUST)
    # Brent is DGEC's own published monthly figure, 91.076 $/bbl, on every leg.
    for crack in cracks.values():
        assert crack.brent_usd_bbl == 91.076
        assert crack.date == "2026-08-01"
        assert crack.window == engine.MONTHLY
        assert crack.product_basis == engine.BASIS_CONVERTED
    # Printed $/t over the cited factor, minus Brent. Exact arithmetic restated.
    assert cracks["gasoil"].value == pytest.approx(1278 / 7.45 - 91.076, abs=1e-12)
    assert cracks["gasoline"].value == pytest.approx(1135 / 8.33 - 91.076, abs=1e-12)
    assert cracks["jet"].value == pytest.approx(1284 / 7.88 - 91.076, abs=1e-12)
    assert cracks["heating_oil"].value == pytest.approx(1225 / 7.45 - 91.076, abs=1e-12)
    assert cracks["fuel_oil_1pct"].value == pytest.approx(528 / 6.35 - 91.076, abs=1e-12)
    # And the pinned values, so a cache edit shows up here.
    assert cracks["gasoil"].value == pytest.approx(80.4676, abs=5e-5)
    assert cracks["gasoline"].value == pytest.approx(45.1785, abs=5e-5)
    assert cracks["jet"].value == pytest.approx(71.8682, abs=5e-5)
    assert cracks["heating_oil"].value == pytest.approx(73.3535, abs=5e-5)
    assert cracks["fuel_oil_1pct"].value == pytest.approx(-7.9264, abs=5e-5)
    assert cracks["gasoil"].product_label == "Gazole"
    assert cracks["gasoline"].product_label == "Eurosuper"


def test_august_2026_decomposition_pinned():
    d = series.note_decomposition_for_month(AUGUST)
    assert d.official_usd_bbl == pytest.approx(38.0505, abs=5e-5)
    assert d.contributions["gasoil"] == pytest.approx(26.9966, abs=5e-4)
    assert d.contributions["gasoline"] == pytest.approx(5.9815, abs=5e-4)
    assert d.contributions["jet"] == pytest.approx(6.2258, abs=5e-4)
    assert d.contributions["heating_oil"] == pytest.approx(5.9353, abs=5e-4)
    assert d.contributions["fuel_oil_1pct"] == pytest.approx(-0.5867, abs=5e-4)
    assert d.attributed_usd_bbl == pytest.approx(44.5526, abs=5e-4)
    assert d.residual_usd_bbl == pytest.approx(-6.5021, abs=5e-4)
    assert d.covered_volume_yield == pytest.approx(0.70945, abs=5e-6)
    assert d.carrier == "gasoil"
    assert d.unattributed_products == (
        "butane",
        "essence_export",
        "naphta",
        "propane",
        "soufre",
    )
    # The residual is solved, never spread: official equals attributed plus it.
    assert d.attributed_usd_bbl + d.residual_usd_bbl == pytest.approx(
        d.official_usd_bbl, abs=1e-12
    )


def test_every_contribution_is_mass_yield_times_price_less_factor_times_brent():
    """The volume yield identity, per product, so a swapped key cannot hide."""
    d = series.note_decomposition_for_month(AUGUST)
    printed = {"gasoil": 1278, "gasoline": 1135, "jet": 1284, "heating_oil": 1225,
               "fuel_oil_1pct": 528}
    for product, price in printed.items():
        mass = config.DGEC_MASS_YIELDS[config.DGEC_NOTE_SLATE_LINE[product]]
        factor = config.DGEC_NOTE_PRODUCT_BBL_PER_T[product]
        expected = mass * (price - factor * 91.076) / config.DGEC_BBL_PER_T_BRENT_MARGIN
        assert d.contributions[product] == pytest.approx(expected, abs=1e-12)


def test_a_provisional_month_is_refused_by_name():
    with pytest.raises(KeyError, match="provisional"):
        series.note_decomposition_for_month("2025-12")
    with pytest.raises(KeyError, match="provisional"):
        series.note_cracks_for_month("2026-04")


def test_a_month_no_note_printed_is_refused():
    with pytest.raises(KeyError, match="no monthly quotations"):
        series.note_decomposition_for_month("2026-06")


def test_the_history_lists_provisional_months_rather_than_dropping_them():
    history = series.note_decomposition_history()
    months = [d.strftime("%Y-%m") for d in history["date"]]
    assert months == ["2025-11", "2025-12", "2026-02", "2026-03", "2026-04",
                      "2026-08", "2026-09"]
    decomposed = history[history["decomposed"]]
    assert [d.strftime("%Y-%m") for d in decomposed["date"]] == [
        "2025-11", "2026-02", "2026-03", "2026-08"
    ]
    assert (decomposed["residual_usd_bbl"] < 0).all()
    assert set(decomposed["carrier"]) == {"gasoil"}
    refused = history[~history["decomposed"]]
    assert all(math.isnan(x) for x in refused["residual_usd_bbl"])
    assert all(reason for reason in refused["reason"])


def test_latest_view_carries_the_margin_month_decomposition_beside_the_old_one():
    view = series.latest_view()
    assert view.margin_month == "2026-08-01"
    assert view.margin_carrier == "gasoil"
    assert view.margin_decomposition_reason == ""
    assert view.margin_decomposition == series.note_decomposition_for_month(AUGUST)
    assert set(view.margin_cracks) == set(config.DGEC_NOTE_PRODUCT_BBL_PER_T)
    # The Gate 2 fields keep their meaning.
    assert view.crack_month == "2026-02-01"
