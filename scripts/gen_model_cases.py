"""Write data/fixtures/model-cases.json, the Model view's parity fixture.

    python scripts/gen_model_cases.py            write the fixture
    python scripts/gen_model_cases.py --check    write nothing, exit 1 if it is stale

docs/design.md Part 8.2: the numbers the Model view prints for each preset must
be the numbers crack.engine computes for the same inputs, to 1e-9. The view
computes through one function, src/model-calc.js `compute`, and this script
records what crack.engine gives for the same inputs, in the same shape, so that
tools/validate-engine.mjs can run `compute` over them and compare every line.

WHAT IS IN IT. One case per preset in data/model.json, with the inputs exactly
as the artifact stores them, because those rounded values are what the page
reads. Then edits a reader can make, each built from a preset by a named rule,
because the page's branches are reached by edits and not by presets: TTF
doubled (SPEC.md section 12, raise TTF and watch the margin fall), a crack
cleared, a gas input cleared, yields that add up to more than a barrel, a
negative gas intensity, an exchange rate of zero, and gasoil cleared so the
gasoil breakeven has nothing to stand on. Synthetic edits of committed values,
labelled as edits; nothing here is market data.

THE COMPUTATION, in the order src/model-calc.js does it:

    products     the model's products with both a crack and a yield
    gross        engine.evaluate on those products; when a gas input is
                 missing, evaluate runs with no gas and ONLY its gross margin
                 is read, and everything after gas is None, never zero
    after gas    engine.evaluate with engine.gas_from_ttf, MARGIN_GROSS_OF_GAS,
                 no residual and no threshold
    breakevens   engine.breakeven_ttf, breakeven_gas_usd_mmbtu and
                 breakeven_crack on gasoil, each against model.json's
                 breakeven_target, a margin of zero
    gap          engine.decompose_official(mbr, yields, cracks): the residual
                 between the ministry's MBR and this model's gross margin

Floats are written with Python's repr, full precision; None is null. Built from
data/model.json, so `make build` runs before this, and tests/test_model.py
asserts the committed file is what a rebuild produces.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from crack import engine  # noqa: E402

MODEL = REPO_ROOT / "data" / "model.json"
FIXTURE = REPO_ROOT / "data" / "fixtures" / "model-cases.json"
TOLERANCE = 1e-9
GASOIL = "gasoil"

#: The edits, by name: what each does to a preset's inputs. Each is applied to
#: every preset, so every branch is reached from every source.
EDITS = (
    "ttf_doubled",
    "gasoline_crack_cleared",
    "ttf_cleared",
    "yields_above_one_barrel",
    "negative_gas_intensity",
    "eurusd_zero",
    "gasoil_crack_cleared",
)


def _edit(name: str, values: dict) -> dict:
    out = json.loads(json.dumps(values))
    if name == "ttf_doubled":
        out["ttf_eur_mwh"] = out["ttf_eur_mwh"] * 2
    elif name == "gasoline_crack_cleared":
        out["cracks"]["gasoline"] = None
    elif name == "ttf_cleared":
        out["ttf_eur_mwh"] = None
    elif name == "yields_above_one_barrel":
        out["yields"] = {p: y * 2 for p, y in out["yields"].items()}
    elif name == "negative_gas_intensity":
        out["gas_intensity_mmbtu_per_bbl"] = -out["gas_intensity_mmbtu_per_bbl"]
    elif name == "eurusd_zero":
        out["eurusd"] = 0.0
    elif name == "gasoil_crack_cleared":
        out["cracks"][GASOIL] = None
    else:
        raise KeyError(name)
    return out


def _present(value) -> bool:
    return value is not None


def compute(values: dict, target: float, products_order: list) -> dict:
    """What crack.engine gives for one set of model inputs. The mirror of
    src/model-calc.js compute, field for field."""
    included = [p for p in products_order if _present(values["cracks"].get(p)) and _present(values["yields"].get(p))]
    excluded = [p for p in products_order if p not in included]
    yields = {p: values["yields"][p] for p in included}
    cracks = {p: values["cracks"][p] for p in included}
    gas_inputs = ("ttf_eur_mwh", "eurusd", "gas_intensity_mmbtu_per_bbl", "other_variable_cost_usd_bbl")
    blocked_by = [name for name in gas_inputs if not _present(values.get(name))]

    no_gas = engine.evaluate(engine.MarginInputs(
        yields=yields, cracks=cracks, gas=engine.gas_from_usd_mmbtu(0.0),
        gas_intensity_mmbtu_per_bbl=0.0, other_variable_cost_usd_bbl=0.0,
        margin_basis=engine.MARGIN_GROSS_OF_GAS,
    ))
    out = {
        "included": included,
        "excluded": excluded,
        "blocked_by": blocked_by,
        "contributions": {p: no_gas.contributions[p] for p in included},
        "attributed_usd_bbl": no_gas.attributed_usd_bbl,
        "gross_margin_usd_bbl": no_gas.gross_margin_usd_bbl,
        "carrier": no_gas.carrier,
        "gas_usd_mmbtu": None,
        "gas_cost_usd_bbl": None,
        "other_variable_cost_usd_bbl": None,
        "margin_after_gas_usd_bbl": None,
        "breakeven_ttf_eur_mwh": None,
        "breakeven_gas_usd_mmbtu": None,
        "breakeven_gasoil_usd_bbl": None,
        "threshold_identified": False,
        "headroom_usd_bbl": None,
        "residual_usd_bbl": None,
        "covered_volume_yield": None,
    }
    if not blocked_by:
        inputs = engine.MarginInputs(
            yields=yields, cracks=cracks,
            gas=engine.gas_from_ttf(values["ttf_eur_mwh"], values["eurusd"]),
            gas_intensity_mmbtu_per_bbl=values["gas_intensity_mmbtu_per_bbl"],
            other_variable_cost_usd_bbl=values["other_variable_cost_usd_bbl"],
            margin_basis=engine.MARGIN_GROSS_OF_GAS,
        )
        result = engine.evaluate(inputs)
        out.update(
            gas_usd_mmbtu=result.gas_usd_mmbtu,
            gas_cost_usd_bbl=result.gas_cost_usd_bbl,
            other_variable_cost_usd_bbl=result.other_variable_cost_usd_bbl,
            margin_after_gas_usd_bbl=result.margin_after_gas_usd_bbl,
            breakeven_ttf_eur_mwh=engine.breakeven_ttf(inputs, target),
            breakeven_gas_usd_mmbtu=engine.breakeven_gas_usd_mmbtu(inputs, target),
            breakeven_gasoil_usd_bbl=engine.breakeven_crack(inputs, GASOIL, target) if GASOIL in included else None,
            threshold_identified=result.threshold_identified,
            headroom_usd_bbl=result.headroom_usd_bbl,
        )
    if _present(values.get("mbr_usd_bbl")):
        decomposition = engine.decompose_official(values["mbr_usd_bbl"], yields, cracks)
        out["residual_usd_bbl"] = decomposition.residual_usd_bbl
        out["covered_volume_yield"] = decomposition.covered_volume_yield
    return out


def build(model: dict | None = None) -> dict:
    if model is None:
        model = json.loads(MODEL.read_text(encoding="utf-8"))
    order = [p["id"] for p in model["products"]]
    target = model["breakeven_target"]["value_usd_bbl"]
    cases = []
    for preset in model["presets"]:
        values = dict(preset["inputs"])
        values["mbr_usd_bbl"] = preset["official"]["mbr_usd_bbl"]
        cases.append({"name": preset["id"], "preset": preset["id"], "edit": None, "inputs": values, "expected": compute(values, target, order)})
        for edit in EDITS:
            edited = _edit(edit, values)
            cases.append({"name": preset["id"] + " " + edit, "preset": preset["id"], "edit": edit, "inputs": edited, "expected": compute(edited, target, order)})
    return {
        "fixture": "model-cases",
        "python": "src/crack/engine.py, through scripts/gen_model_cases.py compute",
        "javascript": "src/model-calc.js compute, over src/engine.js",
        "tolerance": TOLERANCE,
        "model_artifact": "data/model.json",
        "products": order,
        "breakeven_target_usd_bbl": target,
        "cases": cases,
    }


def serialise(fixture: dict) -> str:
    return json.dumps(fixture, indent=1, ensure_ascii=True, allow_nan=False) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="write nothing, exit 1 if the committed fixture is stale")
    args = parser.parse_args(argv)
    text = serialise(build()).encode("ascii")
    if args.check:
        if not FIXTURE.exists() or FIXTURE.read_bytes() != text:
            print("STALE %s. Regenerate with: python scripts/gen_model_cases.py" % FIXTURE)
            return 1
        print("byte identical: %s matches a rebuild from data/model.json" % FIXTURE)
        return 0
    FIXTURE.write_bytes(text)
    print("wrote %s, %d bytes" % (FIXTURE, len(text)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
