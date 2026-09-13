"""The committed seeds, and the SPEC.md section 9 intensity test.

This file is the one that stops crack.config.GAS_INTENSITY_MMBTU_PER_BBL from
becoming a number somebody typed. SPEC.md section 4.4 says "Gas intensity is
derived, not typed", and the only way to keep that true over time is to derive
it here, from the committed seed, and refuse to let the two drift apart. An edit
to the constant without an edit to the seed fails. An edit to the seed without
an edit to the constant fails. A figure whose citation has been dropped fails.

Nothing here touches the network. The seed is committed, which is the point: the
two figures it carries out of the EIA Refinery Capacity Report exist only inside
a PDF, so there is nothing to fetch and nothing to parse, and SPEC.md section
5.1 asks for exactly this, "Seed JSON with source URLs".

ONE PRACTICAL NOTE FOR WHOEVER WORKS ON THIS NEXT. On the machine this was
written on, the global Claude settings deny the file reading tools any path
containing the word "seed", a rule meant for wallet seed phrases. The pipeline
itself is unaffected, since it opens the file with ordinary Python, and so is
this test. Editing data/seed/*.json or this file with an editor tool will be
refused, and the fix is to narrow that rule rather than to move the file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crack import config
from crack.sources import eia
from crack.sources.base import SourceError


@pytest.fixture()
def seed() -> dict:
    return eia.load_refinery_fuel_seed()


# --------------------------------------------------------------------------
# SPEC.md section 9, the intensity row
# --------------------------------------------------------------------------

def test_the_seed_reproduces_the_configured_gas_intensity(seed):
    """Derived value against the constant the engine reads. The row SPEC.md 9 names."""
    derived = eia.gas_intensity_from_seed(seed)
    assert round(derived, 5) == config.GAS_INTENSITY_MMBTU_PER_BBL
    assert derived == pytest.approx(config.GAS_INTENSITY_MMBTU_PER_BBL, abs=5e-6)


def test_the_derived_intensity_is_inside_the_spec_band(seed):
    """SPEC.md section 4.4: outside 0.12 to 0.30, stop and show your working."""
    derived = eia.gas_intensity_from_seed(seed)
    low, high = config.GAS_INTENSITY_BAND
    assert low < derived < high
    assert derived == pytest.approx(0.2121741035, abs=1e-9)


def test_the_derivation_is_the_one_spec_4_4_describes(seed):
    """Written out here so the test fails on a changed method, not only a changed number.

    (fuel gas + hydrogen feedstock) in million cubic feet, to cubic feet, times
    the heat content in Btu per cubic foot, to MMBtu, over crude inputs in
    barrels.
    """
    figures = seed["_figures"]
    fuel = figures["refinery_fuel_gas_mmcf"]["value"]
    hydrogen = figures["hydrogen_feedstock_gas_mmcf"]["value"]
    heat = figures["gas_heat_content_btu_per_cf"]["value"]
    crude = figures["crude_inputs_thousand_bbl"]["value"]
    expected = (fuel + hydrogen) * 1e6 * heat / 1e6 / (crude * 1e3)
    assert eia.gas_intensity_from_seed(seed) == expected


def test_the_hydrogen_feedstock_gas_is_included(seed):
    """SPEC.md section 4.4 says to include it, and a European refiner buys it too.

    Dropping it moves the answer by about 15 percent, which is far more than the
    choice of denominator does, so it is the one decision in this derivation that
    could quietly change the study's answer.
    """
    figures = seed["_figures"]
    fuel_only = (
        figures["refinery_fuel_gas_mmcf"]["value"]
        * 1e6
        * figures["gas_heat_content_btu_per_cf"]["value"]
        / 1e6
        / (figures["crude_inputs_thousand_bbl"]["value"] * 1e3)
    )
    assert eia.gas_intensity_from_seed(seed) > fuel_only
    assert fuel_only == pytest.approx(
        config.GAS_INTENSITY_FUEL_ONLY_MMBTU_PER_BBL, abs=5e-5
    )


def test_the_sensitivities_in_the_seed_match_the_constants_in_config(seed):
    by_key = {item["key"]: item for item in seed["derived"]["sensitivities"]}
    assert by_key["fuel_gas_only"]["value"] == pytest.approx(
        config.GAS_INTENSITY_FUEL_ONLY_MMBTU_PER_BBL, abs=5e-5
    )
    assert by_key["gross_input_denominator"]["value"] == pytest.approx(
        config.GAS_INTENSITY_GROSS_INPUT_MMBTU_PER_BBL, abs=5e-5
    )
    # Neither is the study figure, and the seed says so in the file.
    assert all(item["used"] is False for item in seed["derived"]["sensitivities"])


# --------------------------------------------------------------------------
# The figures themselves
# --------------------------------------------------------------------------

def test_every_figure_the_config_carries_is_in_the_seed(seed):
    figures = seed["_figures"]
    assert (
        figures["refinery_fuel_gas_mmcf"]["value"]
        == config.EIA_REFINERY_FUEL_GAS_MMCF_2023
    )
    assert (
        figures["hydrogen_feedstock_gas_mmcf"]["value"]
        == config.EIA_HYDROGEN_FEEDSTOCK_GAS_MMCF_2023
    )
    assert (
        figures["gas_heat_content_btu_per_cf"]["value"]
        == config.EIA_GAS_HEAT_CONTENT_BTU_PER_CF_2023
    )
    assert (
        figures["crude_inputs_thousand_bbl"]["value"]
        == config.EIA_CRUDE_INPUTS_THOUSAND_BBL_2023
    )


def test_every_figure_carries_a_source_url_a_unit_and_a_printed_label(seed):
    """SPEC.md section 5.1 and non negotiable 8.

    An uncited number is indistinguishable from an invented one a year from now.
    """
    for key in eia.SEED_FIGURES:
        figure = seed["_figures"][key]
        assert figure["source_url"].startswith("https://www.eia.gov/")
        assert figure["unit"]
        assert figure["label_as_printed"]
        assert figure["period"] == "2023"
        assert figure["area"] == "United States"


def test_the_two_pdf_figures_quote_the_line_they_were_read_from(seed):
    """The two numbers that exist only inside a PDF carry the printed line."""
    for key in ("refinery_fuel_gas_mmcf", "hydrogen_feedstock_gas_mmcf"):
        figure = seed["_figures"][key]
        assert figure["source_url"].endswith("table10.pdf")
        assert str(int(figure["value"])) in figure["verified_line"].replace(",", "")


def test_the_seed_records_that_it_is_a_us_figure_and_an_upper_end_for_europe(seed):
    derived = seed["derived"]
    assert derived["is_an_upper_end_default_for_europe"] is True
    assert "still gas" in derived["upper_end_note"]


def test_the_licence_is_the_one_unambiguous_grant_in_the_project(seed):
    assert seed["licence"] == "US public domain"
    assert "public domain" in seed["licence_note"]
    assert seed["acknowledgment"].startswith(
        "Source: U.S. Energy Information Administration"
    )


def test_the_seed_warns_against_probing_eia_with_head(seed):
    """eia.gov answers 503 to HEAD and 200 to GET, which looks like an outage."""
    assert "HEAD" in seed["fetch_note"]


# --------------------------------------------------------------------------
# The loader refuses a seed that cannot be checked
# --------------------------------------------------------------------------

def broken_seed(tmp_path, mutate):
    payload = json.loads(eia.seed_path().read_text(encoding="utf-8"))
    mutate(payload)
    (tmp_path / eia.SEED_FILENAME).write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path


def test_a_figure_with_no_citation_is_refused(tmp_path):
    def drop_url(payload):
        for figure in payload["figures"]:
            if figure["key"] == "gas_heat_content_btu_per_cf":
                figure.pop("source_url")

    root = broken_seed(tmp_path, drop_url)
    with pytest.raises(SourceError, match="no source_url"):
        eia.load_refinery_fuel_seed(root)


def test_a_missing_figure_is_refused(tmp_path):
    def drop_figure(payload):
        payload["figures"] = [
            f for f in payload["figures"] if f["key"] != "crude_inputs_thousand_bbl"
        ]

    root = broken_seed(tmp_path, drop_figure)
    with pytest.raises(SourceError, match="no figure"):
        eia.load_refinery_fuel_seed(root)


def test_a_figure_with_no_number_is_refused(tmp_path):
    def blank_value(payload):
        for figure in payload["figures"]:
            if figure["key"] == "refinery_fuel_gas_mmcf":
                figure["value"] = "about a million"

    root = broken_seed(tmp_path, blank_value)
    with pytest.raises(SourceError, match="no numeric value"):
        eia.load_refinery_fuel_seed(root)


def test_an_absent_seed_file_is_refused(tmp_path):
    with pytest.raises(SourceError, match="not on disk"):
        eia.load_refinery_fuel_seed(tmp_path / "nothing")


# --------------------------------------------------------------------------
# The manifest entry
# --------------------------------------------------------------------------

def test_the_seed_is_recorded_in_the_manifest_as_a_seed(sandbox):
    # The sandbox repoints every data directory at a temporary one, so the
    # committed seed is copied in rather than read through the patched path.
    # The copy is what makes this a test of the manifest entry and not of the
    # sandbox.
    committed = eia.seed_path(Path(__file__).resolve().parents[1] / "data" / "seed")
    target = sandbox / "seed"
    target.mkdir(parents=True, exist_ok=True)
    (target / eia.SEED_FILENAME).write_text(
        committed.read_text(encoding="utf-8"), encoding="utf-8"
    )

    entry = eia.record_refinery_fuel_seed()
    assert entry["method"] == "seed"
    assert entry["machine_fetched"] is False
    # A file nothing fetched has no fetch time. It has a time this run looked.
    assert entry["fetched_at"] is None
    assert entry["checked_at"]
    assert entry["file"] == "data/seed/eia_refinery_fuel_2023.json"
    assert entry["committable"] is True
    assert entry["rows"] == 4

    manifest = json.loads((sandbox / "manifest.json").read_text(encoding="utf-8"))
    recorded = next(e for e in manifest["series"] if e["series"] == eia.SEED_SERIES)
    assert recorded["derived_gas_intensity_mmbtu_per_bbl"] == pytest.approx(
        config.GAS_INTENSITY_MMBTU_PER_BBL, abs=5e-6
    )
    assert set(recorded["figures"]) == set(eia.SEED_FIGURES)


# --------------------------------------------------------------------------
# SPEC.md section 4.4, the triangulation. Not a tuning.
# --------------------------------------------------------------------------
#
# "With that intensity, compute the October 2022 gas cost against a refinery
# fired on fuel oil and report it next to S&P's 7 $/bbl gap. The same order of
# magnitude is the expectation. Report whatever you get."
#
# What comes out, on the committed caches, is 6.23 $/bbl against S&P's about 7.
# That is close, and the closeness is not evidence of anything beyond the units
# being right: the two calculations share no inputs and do not use the same
# method. Nothing was tuned to land there, and SPEC.md section 6.6 forbids
# tuning toward it, so these assertions are deliberately loose about the level
# and tight about the arithmetic. A broken euro per megawatt hour to dollar per
# MMBtu chain, or a fuel oil price divided by the wrong heat content, moves the
# answer by a factor and fails here.
#
# It reads only committed caches. The private TTF export gives 39.12 $/MMBtu for
# the same month against the World Bank's 39.02, which is a second cross check
# and cannot be a test because data/private is not in the repository.

OCTOBER_2022 = "2022-10-01"


def cache(name: str):
    root = Path(__file__).resolve().parents[1] / "data" / "cache"
    import pandas as pd

    return pd.read_csv(root / ("%s.csv" % name), parse_dates=["date"])


@pytest.fixture()
def october_2022_gas_usd_mmbtu() -> float:
    gas = cache("worldbank_gas_europe_monthly")
    return float(gas.loc[gas["date"] == OCTOBER_2022, "gas_usd_mmbtu"].iloc[0])


@pytest.fixture()
def october_2022_fuel_oil_usd_bbl() -> float:
    """Rotterdam 3.5 percent fuel oil barges, the grade a refinery would burn."""
    products = cache("opec_rotterdam_products_monthly")
    row = products.loc[products["date"] == OCTOBER_2022].iloc[0]
    return float(row["fuel_oil_35pct_usd_bbl"])


def test_the_october_2022_gas_cost_is_what_the_intensity_and_the_gas_price_give(
    october_2022_gas_usd_mmbtu,
):
    cost = config.GAS_INTENSITY_MMBTU_PER_BBL * october_2022_gas_usd_mmbtu
    assert october_2022_gas_usd_mmbtu == pytest.approx(39.02, abs=0.01)
    assert cost == pytest.approx(8.279, abs=0.01)


def test_the_gas_versus_fuel_oil_gap_is_the_same_order_as_the_sp_figure(
    october_2022_gas_usd_mmbtu, october_2022_fuel_oil_usd_bbl
):
    """6.23 $/bbl computed here, about 7 $/bbl reported by S&P. Reported, not tuned."""
    intensity = config.GAS_INTENSITY_MMBTU_PER_BBL
    gas_cost = intensity * october_2022_gas_usd_mmbtu
    fuel_oil_usd_mmbtu = (
        october_2022_fuel_oil_usd_bbl / config.EIA_RESIDUAL_FUEL_OIL_MMBTU_PER_BBL
    )
    fuel_oil_cost = intensity * fuel_oil_usd_mmbtu
    gap = gas_cost - fuel_oil_cost

    assert gap == pytest.approx(6.23, abs=0.05)
    # Same order of magnitude as S&P, which is the whole expectation. The window
    # is wide on purpose: it must not become a target.
    reference = config.SP_GAS_VERSUS_FUEL_OIL_GAP_USD_BBL_2022_10
    assert reference / 3.0 < gap < reference * 3.0


def test_the_triangulation_uses_a_cited_heat_content_and_not_a_guess():
    """SPEC.md section 4.1: never guess a factor.

    6.287 million Btu per barrel is EIA's own published figure for residual fuel
    oil, Monthly Energy Review Table A1, read on 2026-09-13.
    """
    assert config.EIA_RESIDUAL_FUEL_OIL_MMBTU_PER_BBL == 6.287
