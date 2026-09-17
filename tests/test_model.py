"""data/model.json and its parity fixture, docs/design.md Part 8.2.

The Model view's presets must carry the findings the calculator could quietly
lose: the model margin is gross of gas and the ministry's MBR is not, the run cut
threshold is unidentified so no breakeven is taken against it, and a preset whose
data do not exist as SPEC.md section 7.2 names them says so product by product
instead of borrowing a neighbour. And the numbers the view prints for each preset
are crack.engine's, which tools/validate-engine.mjs checks against
data/fixtures/model-cases.json, a file this suite asserts is current.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pandas as pd
import pytest

from crack import engine, export, series

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA = REPO_ROOT / "data"


@pytest.fixture(scope="module")
def model():
    return json.loads((DATA / "model.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def presets(model):
    return {p["id"]: p for p in model["presets"]}


def _words(segments):
    out = []
    for s in segments:
        if "text" in s:
            out.append(s["text"])
        elif "label" in s:
            out.append(str(s["label"]))
        else:
            out.append("{%s}" % s["field"])
    return "".join(out)


def _gen_model_cases():
    spec = importlib.util.spec_from_file_location("gen_model_cases", REPO_ROOT / "scripts" / "gen_model_cases.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_four_presets_spec_7_2_names_in_its_order(model):
    assert [p["id"] for p in model["presets"]] == ["latest", "average_2019", "october_2022", "july_2026"]


def test_the_model_margin_is_gross_of_gas_and_the_mbr_is_never_a_step(model):
    assert model["basis"]["margin_basis"] == engine.MARGIN_GROSS_OF_GAS
    assert model["basis"]["residual_usd_bbl"] == 0.0
    assert model["basis"]["official_margin_basis"] == engine.MARGIN_NET_OF_GAS
    assert model["basis"]["official_is_a_step"] is False
    lead = _words(model["lead_segments"])
    assert "gross of gas" in lead and "not the ministry's MBR" in lead and "already net" in lead
    assert "nothing is subtracted from it" in lead


def test_every_preset_prices_the_ministrys_slate_yields(model):
    for preset in model["presets"]:
        for product, value in preset["inputs"]["yields"].items():
            assert value == pytest.approx(series.DGEC_NOTE_VOLUME_YIELDS[product], abs=1e-6)
    assert [p["id"] for p in model["products"]] == list(series.MODEL_PRODUCTS)


def test_no_threshold_no_headroom_and_breakevens_against_a_margin_of_zero(model):
    assert model["run"]["threshold_identified"] is False
    assert model["run"]["verdict"] == "unidentified"
    assert model["run"]["run_cut_threshold_usd_bbl"] is None
    assert model["run"]["headroom_usd_bbl"] is None
    assert "unidentified" in _words(model["run"]["segments"])
    assert model["breakeven_target"]["value_usd_bbl"] == 0.0
    assert "not a level at which runs get cut" in _words(model["breakeven_target"]["segments"])
    text = json.dumps(model)
    assert '"field": "headroom_usd_bbl"' not in text
    for word in ("winner", "dead heat", " tie "):
        assert word not in text


def test_latest_is_the_margin_month_on_the_waterfalls_own_cracks(presets):
    now = json.loads((DATA / "now.json").read_text(encoding="utf-8"))
    stack = json.loads((DATA / "margin-stack.json").read_text(encoding="utf-8"))
    latest = presets["latest"]
    assert latest["months"] == [now["verdict"]["values"]["margin_month"]]
    by_id = {row["id"]: row for row in stack["rows"]}
    for product, value in latest["inputs"]["cracks"].items():
        assert value == pytest.approx(by_id[product]["crack_usd_bbl"], abs=1e-6)
    assert latest["official"]["mbr_usd_bbl"] == pytest.approx(now["verdict"]["values"]["mbr_usd_bbl"], abs=1e-6)
    assert latest["reconstructed"] is False


def test_july_2026_is_the_reconstruction_labelled_with_jet_and_fuel_oil_missing(presets):
    july = presets["july_2026"]
    assert july["reconstructed"] is True
    assert july["crack_source"] == "dgec_note_reconstructed_weekly"
    cracks = july["inputs"]["cracks"]
    assert cracks["jet"] is None and cracks["fuel_oil_1pct"] is None
    for product in ("jet", "fuel_oil_1pct"):
        said = _words(july["sources"]["cracks"][product]["segments"])
        assert july["sources"]["cracks"][product]["available"] is False
        assert said.startswith("No figure for July 2026") and "not borrowed" in said
    weekly = series.load("dgec_note_reconstructed_cracks_weekly")
    weekly["date"] = pd.to_datetime(weekly["date"]).dt.strftime("%Y-%m-%d")
    weekly = weekly[weekly["date"].str.startswith("2026-07")]
    assert july["weeks"]["fridays"] == list(weekly["date"])
    assert len(weekly) == 5
    for product, column in (("gasoil", "crack_gasoil_usd_bbl"), ("gasoline", "crack_gasoline_usd_bbl"), ("heating_oil", "crack_fioul_domestique_usd_bbl")):
        assert cracks[product] == pytest.approx(float(weekly[column].mean()), abs=1e-6)
        assert "Reconstructed" in _words(july["sources"]["cracks"][product]["segments"])
    note = _words(july["note_segments"])
    assert note.startswith("Reconstructed, not printed") and "{weeks}" in note
    assert "printed none" in note and "deleted and nobody archived" in note
    assert "no jet and no fuel oil" in note


def test_2019_ttf_is_derived_from_committed_world_bank_and_fred_and_says_so(presets):
    y2019 = presets["average_2019"]
    months = [m[:7] for m in y2019["months"]]
    assert len(months) == 12
    gas = series.gas_monthly()
    gas = gas[gas["date"].dt.year == 2019]["gas_usd_mmbtu"].mean()
    fx = series.eurusd_monthly()
    fx = fx[fx["date"].dt.year == 2019]["eurusd"].mean()
    inputs = y2019["inputs"]
    assert inputs["eurusd"] == pytest.approx(fx, abs=1e-6)
    assert engine.gas_from_ttf(inputs["ttf_eur_mwh"], inputs["eurusd"]).gas_usd_mmbtu == pytest.approx(gas, abs=1e-5)
    said = _words(y2019["sources"]["ttf_segments"])
    assert said.startswith("Derived, not quoted") and "World Bank" in said and "FRED" in said
    assert "not used" in said
    assert inputs["cracks"]["heating_oil"] is None
    assert "not borrowed from gasoil" in _words(y2019["sources"]["cracks"]["heating_oil"]["segments"])
    assert "An average of {months} months" in _words(y2019["note_segments"])


def test_2019_mbr_is_the_mean_of_twelve_published_months_and_says_so(presets):
    y2019 = presets["average_2019"]
    mbr = series.load("dgec_mbr_monthly")
    mbr = mbr[pd.to_datetime(mbr["date"]).dt.year == 2019]
    assert len(mbr) == 12
    assert y2019["official"]["mbr_usd_bbl"] == pytest.approx(float(mbr["mbr_usd_bbl"].mean()), abs=1e-6)
    assert y2019["official"]["months_published"] == 12
    assert "the mean of the {months_published} months it published" in _words(y2019["official"]["label_segments"])


def test_october_2022_names_every_source_and_its_reason(presets):
    october = presets["october_2022"]
    assert october["crack_source"] == "opec_rotterdam_products_monthly"
    for product, source in october["sources"]["cracks"].items():
        said = _words(source["segments"])
        if october["inputs"]["cracks"][product] is None:
            assert said.startswith("No figure")
        else:
            assert "OPEC" in said and "FRED" in said
    assert "refinery strikes" in _words(october["reason_segments"])
    assert october["reason_source_url"].startswith("https://")


def test_the_ttf_inverse_round_trips_through_the_engine():
    for gas, fx in ((21.11, 1.1593619), (4.8033, 1.1196), (39.02, 0.985295)):
        ttf = series.ttf_eur_mwh_from_usd_mmbtu(gas, fx)
        assert engine.gas_from_ttf(ttf, fx).gas_usd_mmbtu == pytest.approx(gas, abs=1e-12)


def test_every_preset_scale_holds_its_own_running_totals(model):
    module = _gen_model_cases()
    order = [p["id"] for p in model["products"]]
    for preset in model["presets"]:
        values = dict(preset["inputs"], mbr_usd_bbl=preset["official"]["mbr_usd_bbl"])
        result = module.compute(values, 0.0, order)
        low, high = preset["scale"]["low_usd_bbl"], preset["scale"]["high_usd_bbl"]
        for value in (result["gross_margin_usd_bbl"], result["margin_after_gas_usd_bbl"], values["mbr_usd_bbl"]):
            assert low <= value <= high


def test_the_parity_fixture_is_what_a_rebuild_from_model_json_produces():
    module = _gen_model_cases()
    committed = (DATA / "fixtures" / "model-cases.json").read_bytes()
    assert committed == module.serialise(module.build()).encode("ascii"), "Run: python scripts/gen_model_cases.py"


def test_the_parity_fixture_reaches_every_branch_the_view_has():
    fixture = json.loads((DATA / "fixtures" / "model-cases.json").read_text(encoding="utf-8"))
    expected = [case["expected"] for case in fixture["cases"]]
    assert any(e["blocked_by"] for e in expected)
    assert any(e["excluded"] for e in expected)
    assert any(e["breakeven_ttf_eur_mwh"] is None and not e["blocked_by"] for e in expected)
    assert any(e["breakeven_gasoil_usd_bbl"] is None and not e["blocked_by"] for e in expected)
    assert any(e["covered_volume_yield"] > 1 for e in expected if e["covered_volume_yield"] is not None)
    assert all(e["headroom_usd_bbl"] is None and e["threshold_identified"] is False for e in expected)
    for case in fixture["cases"]:
        e = case["expected"]
        if e["margin_after_gas_usd_bbl"] is not None:
            assert math.isclose(e["margin_after_gas_usd_bbl"], e["gross_margin_usd_bbl"] - e["gas_cost_usd_bbl"] - e["other_variable_cost_usd_bbl"], abs_tol=1e-9)


def test_an_identified_threshold_is_refused_rather_than_exported(monkeypatch):
    inputs = export.Inputs(replications=50)
    real = export.run_verdict

    def identified(*args, **kwargs):
        out = dict(real(*args, **kwargs))
        out["threshold_identified"] = True
        return out

    monkeypatch.setattr(export, "run_verdict", identified)
    with pytest.raises(ValueError, match="unidentified"):
        export.model(inputs)
