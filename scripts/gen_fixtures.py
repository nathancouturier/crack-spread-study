"""Write data/fixtures/engine-cases.json, the parity fixture SPEC.md 7.1 asks for.

    python scripts/gen_fixtures.py             write the fixture
    python scripts/gen_fixtures.py --check     write nothing, exit 1 if it is stale
    python scripts/gen_fixtures.py --out DIR   write somewhere else, for a diff

SPEC.md section 7.1 asks for "at least 200 randomised input sets with full
Python output, every contribution line included", so that tools/validate-engine.mjs
can run src/engine.js against them and prove the two engines agree to 1e-9. This
writes that file. It is the Python side of the proof, so it computes with
crack.engine and records what came back without touching it.

What is in it, and why it is more than 200 random draws
------------------------------------------------------
A random sweep of plausible inputs proves the two engines agree in the middle,
which is where they were never going to disagree. The interesting inputs are the
ones a language difference can actually reach:

    a missing observation      NaN in, NaN out, and a carrier that survives it
    a zero conversion factor   Python raises, JavaScript would return Infinity
    a zero denominator         same shape, different function
    a misaligned pair          the AlignmentError both engines must raise
    no threshold               None in Python, null in JavaScript, and neither
                               of them zero
    no leverage                a breakeven that does not exist, which is null
                               and is NOT the same as a breakeven of zero
    an empty product set       sum of nothing is zero, in both languages
    a tie in the carrier       two identical contributions, broken by sorted
                               key order in both engines

The Gate 2 self audit measured nine more divergences that this file could not
reach, because every case in it was built from a validated Python object. Four
case kinds were added for them, and each one is named after what it catches:

    quote            a price exactly as JSON carries it: null, "", "83.73",
                     true. Number(null) is 0, so a hole in an artifact used to
                     become a price of 0 $/bbl in the browser and a refusal in
                     the pipeline. Findings 8 rows 1 to 3
    raw_crack        a crack leg that never went through makeQuote, which is
                     what a module reading a JSON row holds. undefined !==
                     undefined is false, so two legs with no window at all used
                     to crack to 71.97. Finding 5
    margin_refusal   inputs both engines must refuse, with the same exception
                     class: a product called "a|b" against two called "a" and
                     "b", and a gas price on a margin that already contains one,
                     which is finding 1 itself
    gas_wedge        the two intensities at one gas price that replaced that
                     subtraction, which nothing compared at all

So the file is built in three parts: written cases that name a branch each, a
large randomised block, and the awkward edges. "coverage" at the top counts what
was actually reached and build() refuses to write a fixture that misses any of
it, so an edit that quietly stops exercising a branch fails here rather than
passing a validator that no longer tests anything.

No committed cache is read
--------------------------
Deliberately. A fixture built from data/cache would change every time a source
publishes another month, and the byte comparison in tests/test_fixtures.py would
then be a data check wearing a parity check's clothes. Every number below is
synthetic and the file changes only when the engine does.

Reproducibility
---------------
The seed is recorded in the file and every draw comes from random.Random(seed)
in a fixed order, so regenerating gives byte identical output.

Encoding, because JSON has no NaN
---------------------------------
JSON cannot carry NaN and json.dump writes a bare NaN token that JSON.parse
refuses. Nothing here is filled or rounded to get around that, so:

    a missing number    the string "NaN", or "Infinity", or "-Infinity"
    an absent value     null, which is Python None and never a number

The two are different on purpose and SPEC.md section 2 rule 1 is why. A
breakeven that was not found carries null, and a margin computed from a missing
crack carries "NaN". A validator that read both as zero would agree with
anything.

Print policy: ASCII only. The console this project is developed on is cp1252.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from crack import config, engine  # noqa: E402

#: Where the fixture lives. SPEC.md section 8 fixes the path.
FIXTURES = REPO_ROOT / "data" / "fixtures"
FILENAME = "engine-cases.json"

#: Bumped when the SHAPE of a case changes, so a stale validator says so instead
#: of reading a field that is no longer there.
#:
#: 2, at the Gate 2 self audit's findings 5 and 8. The fixture reached only
#: inputs both engines were always going to agree on: every quote value was a
#: number, every leg was a validated Quote, every margin carried a gas record,
#: every slate was keyed "gasoil" and every margin was gross of gas. The nine
#: divergences the audit measured were all outside it, and two of them turned a
#: missing value into a number in the browser. Four case kinds were added, each
#: named after the divergence it closes: quote, raw_crack, margin_refusal and
#: gas_wedge.
SCHEMA_VERSION = 2

SEED = 20260913

#: Every branch the fixture has to reach. build() refuses to write without them.
REQUIRED_COVERAGE = (
    "crack_direct",
    "crack_converted",
    "crack_missing_value",
    "crack_unit_error",
    "crack_alignment_error",
    "margin_with_threshold",
    "margin_without_threshold",
    "margin_missing_crack",
    "margin_empty_products",
    "margin_carrier_tie",
    "margin_ttf_gas",
    "margin_published_gas",
    "margin_no_leverage",
    "margin_negative",
    "decomposition_positive_residual",
    "decomposition_negative_residual",
    "decomposition_zero_official",
    "replication_missing_inputs",
    "replication_complete",
    "yields_crude_intake",
    "yields_total_feed",
    "yields_normalised",
    "percentile_full",
    "percentile_with_holes",
    "percentile_empty",
    # Gate 2 self audit, findings 5 and 8. Everything below this line is a case
    # the 380 case fixture could not reach, and the audit measured each one
    # disagreeing between the two engines before it was closed.
    "quote_refused_value",  # null, "", "83.73", true: Number(null) was 0
    "quote_accepted",
    "raw_leg_refused",  # a bare object with no window or no date
    "raw_leg_accepted",
    "margin_refusal_keys",  # {"a|b"} against {"a","b"}
    "margin_refusal_gas_double_count",
    "margin_net_of_gas",
    "margin_gas_defaulted",  # no gas record at all
    "margin_ttf_without_eurusd",
    "margin_ttf_eurusd_absent",
    "margin_threshold_override",  # outputs(threshold=X) with X not on the inputs
    "margin_gasoil_key_not_gasoil",
    "percentile_empty_mapping",
    "percentile_refuses_a_null_history",
    "gas_wedge",
)


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------


def encode(value):
    """Python value to something JSON can carry without losing what it means."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value
    if isinstance(value, (int, str)):
        return value
    if isinstance(value, dict):
        return {key: encode(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    raise TypeError("cannot encode %r of type %s" % (value, type(value).__name__))


def quote_payload(quote: engine.Quote) -> dict:
    return {
        "value": encode(quote.value),
        "unit": quote.unit,
        "date": quote.date,
        "window": quote.window,
        "label": quote.label,
    }


def gas_payload(gas: engine.GasCost | None) -> dict | None:
    """A gas record, or null for a margin that was handed none at all.

    null is not a gas price of zero. It means the caller passed no gas record,
    which Python defaults to gas_from_usd_mmbtu(0.0) and src/engine.js used to
    answer with a TypeError. Gate 2 self audit, finding 8 row 4.
    """
    if gas is None:
        return None
    return {
        "gas_usd_mmbtu": encode(gas.gas_usd_mmbtu),
        "basis": gas.basis,
        "ttf_eur_mwh": encode(gas.ttf_eur_mwh),
        "eurusd": encode(gas.eurusd),
    }


def inputs_payload(inputs: engine.MarginInputs, gas: engine.GasCost | None) -> dict:
    """The margin inputs as JSON.

    Args:
        gas: the record the case actually passed, or None when it passed none.
            Taken separately from inputs.gas because MarginInputs has already
            substituted its default by the time it is built, and the point of
            the case is that the default was substituted.
    """
    return {
        "yields": encode(dict(inputs.yields)),
        "cracks": encode(dict(inputs.cracks)),
        "gas": gas_payload(gas),
        "residual_usd_bbl": encode(inputs.residual_usd_bbl),
        "gas_intensity_mmbtu_per_bbl": encode(inputs.gas_intensity_mmbtu_per_bbl),
        "other_variable_cost_usd_bbl": encode(inputs.other_variable_cost_usd_bbl),
        "run_cut_threshold_usd_bbl": encode(inputs.run_cut_threshold_usd_bbl),
        # Which side of the gas purchase this margin sits on. A margin that is
        # already net of gas may not have one subtracted from it again, and the
        # fixture carried no such case at all until the Gate 2 self audit.
        "margin_basis": inputs.margin_basis,
    }


# ---------------------------------------------------------------------------
# Case builders. Each one computes with crack.engine and records the answer.
# ---------------------------------------------------------------------------


def crack_case(
    name: str,
    product: engine.Quote,
    brent: engine.Quote,
    product_bbl_per_t=None,
    brent_bbl_per_t=None,
) -> dict:
    case = {
        "kind": "crack",
        "name": name,
        "product": quote_payload(product),
        "brent": quote_payload(brent),
        "product_bbl_per_t": encode(product_bbl_per_t),
        "brent_bbl_per_t": encode(brent_bbl_per_t),
    }
    try:
        result = engine.crack(
            product,
            brent,
            product_bbl_per_t=product_bbl_per_t,
            brent_bbl_per_t=brent_bbl_per_t,
        )
    except (engine.UnitError, engine.AlignmentError) as error:
        case["expected"] = {"error": type(error).__name__}
        return case
    case["expected"] = {
        "error": None,
        "value": encode(result.value),
        "date": result.date,
        "window": result.window,
        "product_usd_bbl": encode(result.product_usd_bbl),
        "brent_usd_bbl": encode(result.brent_usd_bbl),
        "product_basis": result.product_basis,
        # The label and the two factors the Crack record carries. The mirror
        # returns them and the validator never compared them, so a browser that
        # lost the source's own product name, which SPEC.md section 4.2 insists
        # on, would have passed. Gate 2 self audit, section (c).
        "product_label": result.product_label,
        "product_bbl_per_t": encode(result.product_bbl_per_t),
        "brent_bbl_per_t": encode(result.brent_bbl_per_t),
    }
    return case


def quote_case(name: str, value_json, unit, date, window, label="") -> dict:
    """One quote built from a value exactly as JSON would carry it.

    GATE 2 SELF AUDIT, FINDING 8, ROWS 1 TO 3, AND THE REASON THIS KIND EXISTS.
    Every quote in the fixture used to be built from a Python float, so no case
    ever put a JSON null through the browser's makeQuote. Number(null) is 0, so
    a Gate 4 artifact with a hole in it gave the browser a price of 0 $/bbl and
    the pipeline a refusal, on a project whose first non negotiable is that a
    missing observation stays missing.

    value_json is written into the file VERBATIM and neither engine decodes it:
    null stays null, "" stays "", "83.73" stays a string. NaN is not one of the
    values here because JSON has no NaN token at all; the crack cases carry the
    missing observation, through the string "NaN" that encode() writes and both
    sides decode to a real NaN before the quote is built.
    """
    case = {
        "kind": "quote",
        "name": name,
        "value_json": value_json,
        "unit": unit,
        "date": date,
        "window": window,
        "label": label,
    }
    try:
        quote = engine.Quote(value_json, unit, date, window, label)
    except (engine.UnitError, engine.AlignmentError) as error:
        case["expected"] = {"error": type(error).__name__}
        return case
    case["expected"] = {
        "error": None,
        "value": encode(quote.value),
        "unit": quote.unit,
        "date": quote.date,
        "window": quote.window,
        "label": quote.label,
    }
    return case


class _BareLeg:
    """A crack leg that is not a Quote, which is what a JSON row deserialises to.

    src/engine.js takes plain objects and has no Quote class to insist on, so
    the Python side of this case has to be equally unvalidated or the two
    engines would not be answering the same question. Gate 2 self audit,
    finding 5: crack() in the browser accepted two objects with no window and no
    date and returned 71.97136465324384, because undefined !== undefined is
    false.
    """

    def __init__(self, **fields):
        for key, value in fields.items():
            setattr(self, key, value)


def raw_crack_case(name: str, product: dict, brent: dict, **factors) -> dict:
    """crack() on two bare objects, with only the fields the case names.

    A field that is absent from the dict is absent from the object, so a leg
    with no window really has no window in either language.
    """
    case = {
        "kind": "raw_crack",
        "name": name,
        "product": {key: encode(value) for key, value in sorted(product.items())},
        "brent": {key: encode(value) for key, value in sorted(brent.items())},
        "product_bbl_per_t": encode(factors.get("product_bbl_per_t")),
        "brent_bbl_per_t": encode(factors.get("brent_bbl_per_t")),
    }
    try:
        result = engine.crack(
            _BareLeg(**product),
            _BareLeg(**brent),
            product_bbl_per_t=factors.get("product_bbl_per_t"),
            brent_bbl_per_t=factors.get("brent_bbl_per_t"),
        )
    except (engine.UnitError, engine.AlignmentError) as error:
        case["expected"] = {"error": type(error).__name__}
        return case
    case["expected"] = {
        "error": None,
        "value": encode(result.value),
        "date": result.date,
        "window": result.window,
    }
    return case


def margin_refusal_case(name: str, payload: dict, build) -> dict:
    """A set of margin inputs both engines have to refuse, and with which class.

    build() is the Python call. The payload is what the JavaScript is handed,
    field for field, so that the two are refusing the same thing rather than two
    similar things.
    """
    case = {"kind": "margin_refusal", "name": name, "inputs": payload}
    try:
        build()
    except Exception as error:  # noqa: BLE001 - the class is the assertion
        case["expected"] = {"error": type(error).__name__}
        return case
    raise SystemExit(
        "margin refusal case %r did not refuse anything. A case that records no "
        "exception would assert that both engines accept it, which is the "
        "opposite of what it is for" % name
    )


def gas_wedge_case(
    name: str, gas_usd_mmbtu: float, embedded: float, study: float
) -> dict:
    """Two intensities at one gas price, in both engines.

    The wedge replaced a subtraction that was wrong on DGEC's margin, so it is
    now the gas story the site tells and the mirror was never compared on it at
    all.
    """
    wedge = engine.gas_wedge(gas_usd_mmbtu, embedded, study)
    return {
        "kind": "gas_wedge",
        "name": name,
        "gas_usd_mmbtu": encode(gas_usd_mmbtu),
        "embedded_intensity_mmbtu_per_bbl": encode(embedded),
        "study_intensity_mmbtu_per_bbl": encode(study),
        "expected": {
            "gas_usd_mmbtu": encode(wedge.gas_usd_mmbtu),
            "embedded_intensity_mmbtu_per_bbl": encode(
                wedge.embedded_intensity_mmbtu_per_bbl
            ),
            "study_intensity_mmbtu_per_bbl": encode(
                wedge.study_intensity_mmbtu_per_bbl
            ),
            "embedded_cost_usd_bbl": encode(wedge.embedded_cost_usd_bbl),
            "study_cost_usd_bbl": encode(wedge.study_cost_usd_bbl),
            "wedge_usd_bbl": encode(wedge.wedge_usd_bbl),
            "ratio": encode(wedge.ratio),
        },
    }


#: "the case passed whatever is on the inputs", which is the ordinary thing and
#: is not the same as "the case passed nothing", which is finding 8 row 4.
GAS_FROM_INPUTS = "gas_from_inputs"


def margin_case(
    name: str,
    inputs: engine.MarginInputs,
    history=(),
    gasoil_key: str = "gasoil",
    threshold=None,
    gas=GAS_FROM_INPUTS,
    gas_eurusd_absent: bool = False,
) -> dict:
    """One margin, evaluated and put through outputs(), with every line recorded.

    Args:
        gas: the gas record the case passed, or None when it passed NONE and let
            the engine's own default stand. inputs.gas is the record after that
            default has been substituted, so it cannot answer the question by
            itself, and the question is the whole of finding 8 row 4.
        gas_eurusd_absent: hand the JavaScript a gas record with no eurusd KEY
            rather than one whose eurusd is null. Python has one word for both,
            None, and JavaScript has two, and undefined === null is false, so
            the mirror answered NaN for the absent one where Python answers
            None. Finding 8 row 5. Both spellings are in the fixture because a
            guard written against one of them passes while the other is live.
    """
    if gas is GAS_FROM_INPUTS:
        gas = inputs.gas
    result = engine.evaluate(inputs)
    bundle = engine.outputs(
        inputs, list(history), gasoil_key=gasoil_key, threshold=threshold
    )
    return {
        "kind": "margin",
        "name": name,
        "inputs": inputs_payload(inputs, gas),
        "history": [encode(x) for x in history],
        "gasoil_key": gasoil_key,
        "threshold": encode(threshold),
        "gas_eurusd_absent": gas_eurusd_absent,
        # config.PERCENTILE_WINDOW_MONTHS. Python carries it on the Outputs
        # record and the mirror dropped the field, so it travels as an input
        # here and is compared below. Gate 2 self audit, finding 11.
        "percentile_window_months": config.PERCENTILE_WINDOW_MONTHS,
        "expected": {
            "contributions": encode(dict(result.contributions)),
            "attributed_usd_bbl": encode(result.attributed_usd_bbl),
            "residual_usd_bbl": encode(result.residual_usd_bbl),
            "gross_margin_usd_bbl": encode(result.gross_margin_usd_bbl),
            "gas_usd_mmbtu": encode(result.gas_usd_mmbtu),
            "gas_cost_usd_bbl": encode(result.gas_cost_usd_bbl),
            "other_variable_cost_usd_bbl": encode(
                result.other_variable_cost_usd_bbl
            ),
            "margin_after_gas_usd_bbl": encode(result.margin_after_gas_usd_bbl),
            "carrier": result.carrier,
            "carrier_contribution_usd_bbl": encode(
                result.carrier_contribution_usd_bbl
            ),
            "threshold_identified": result.threshold_identified,
            "headroom_usd_bbl": encode(result.headroom_usd_bbl),
            "run_cut_threshold_usd_bbl": encode(result.run_cut_threshold_usd_bbl),
            "gas_basis": result.gas_basis,
            "margin_basis": result.margin_basis,
            "gas_already_in_margin": result.gas_already_in_margin,
            "breakeven_ttf_eur_mwh": encode(bundle.breakeven_ttf_eur_mwh),
            "breakeven_gas_usd_mmbtu": encode(bundle.breakeven_gas_usd_mmbtu),
            "breakeven_gasoil_usd_bbl": encode(bundle.breakeven_gasoil_usd_bbl),
            "percentile_10y": encode(bundle.percentile_10y),
            "percentile_observations": bundle.percentile_observations,
            "percentile_window_months": bundle.percentile_window_months,
            "outputs_headroom_usd_bbl": encode(bundle.headroom_usd_bbl),
            "outputs_threshold_identified": bundle.threshold_identified,
        },
    }


def decomposition_case(
    name: str, official: float, yields: dict, cracks: dict, unattributed=()
) -> dict:
    result = engine.decompose_official(
        official, yields, cracks, unattributed_products=unattributed
    )
    return {
        "kind": "decomposition",
        "name": name,
        "official_usd_bbl": encode(official),
        "yields": encode(yields),
        "cracks": encode(cracks),
        "unattributed_products": list(unattributed),
        "expected": {
            "contributions": encode(dict(result.contributions)),
            "attributed_usd_bbl": encode(result.attributed_usd_bbl),
            "residual_usd_bbl": encode(result.residual_usd_bbl),
            "residual_share": encode(result.residual_share),
            "carrier": result.carrier,
            "carrier_contribution_usd_bbl": encode(
                result.carrier_contribution_usd_bbl
            ),
            "unattributed_products": list(result.unattributed_products),
            "covered_volume_yield": encode(result.covered_volume_yield),
        },
    }


def replication_case(
    name: str,
    quotations: dict,
    brent_usd_t: float,
    official: float,
    freight=math.nan,
    gas_cost=math.nan,
) -> dict:
    attempt = engine.replicate_mbr(
        quotations_usd_t=quotations,
        brent_usd_t=brent_usd_t,
        official_usd_bbl=official,
        freight_usd_t=freight,
        gas_cost_usd_t=gas_cost,
    )
    return {
        "kind": "replication",
        "name": name,
        "quotations_usd_t": encode(quotations),
        "brent_usd_t": encode(brent_usd_t),
        "official_usd_bbl": encode(official),
        "freight_usd_t": encode(freight),
        "gas_cost_usd_t": encode(gas_cost),
        # The method itself travels with the case, because src/engine.js may not
        # hold it: SPEC.md section 0.1 keeps data out of JS modules and DGEC's
        # slate is data.
        "method": {
            "mass_yields": encode(dict(config.DGEC_MASS_YIELDS)),
            "bbl_per_t_brent": config.DGEC_BBL_PER_T_BRENT_MARGIN,
            "sulphur_usd_t": config.DGEC_SULPHUR_PRICE_USD_T,
            "insurance_and_loss_rate": config.DGEC_INSURANCE_AND_LOSS_RATE,
            "bar_usd_bbl": config.REPLICATION_BAR_USD_BBL,
            "unpublished_inputs": list(config.DGEC_UNPUBLISHED_METHOD_INPUTS),
        },
        "expected": {
            "margin_usd_bbl": encode(attempt.margin_usd_bbl),
            "partial_usd_bbl": encode(attempt.partial_usd_bbl),
            "revenue_published_usd_t": encode(attempt.revenue_published_usd_t),
            "covered_mass_yield": encode(attempt.covered_mass_yield),
            "missing_inputs": list(attempt.missing_inputs),
            "error_usd_bbl": encode(attempt.error_usd_bbl),
            "partial_error_usd_bbl": encode(attempt.partial_error_usd_bbl),
            "within_bar": attempt.within_bar,
        },
    }


def yields_case(
    name: str, output_kbd: dict, denominator: float, basis: str, normalise: bool
) -> dict:
    observed = engine.observed_yields(output_kbd, denominator, basis)
    if normalise:
        observed = observed.normalised()
    return {
        "kind": "yields",
        "name": name,
        "output_kbd": encode(output_kbd),
        "denominator_kbd": encode(denominator),
        "basis": basis,
        "normalise": normalise,
        # config.YIELD_BASIS_NOTES. Python reads it from config and the mirror
        # may not hold it, SPEC.md section 0.1, so it travels with the case.
        # ObservedYields.note says it exists "so a JSON artifact cannot lose it"
        # and the mirror lost it. Gate 2 self audit, finding 11.
        "notes": {key: config.YIELD_BASIS_NOTES[key] for key in sorted(config.YIELD_BASIS_NOTES)},
        "expected": {
            "yields": encode(dict(observed.yields)),
            "total": encode(observed.total),
            "basis": observed.basis,
            "denominator_kbd": encode(observed.denominator_kbd),
            "note": observed.note,
        },
    }


def percentile_case(name: str, value: float, history, history_shape="list") -> dict:
    """One rank, over a history of the shape the case names.

    "mapping" passes an empty mapping instead of a list. Gate 2 self audit,
    section (c) row 7: percentile_rank(2.0, {}) returned None in Python and threw
    a TypeError in the browser, because the mirror called history.filter on
    something that has no filter. Python iterates whatever it is given, so the
    mirror has to as well.

    "null" passes nothing at all, and BOTH engines must refuse it. This is the
    other side of the same repair and it is the one that keeps the repair
    honest: a mirror written as Array.from(history || []) answers "no history"
    where Python raises, which makes the browser the more forgiving of the two
    engines, and SPEC.md section 7.1 forbids that direction. null is not an
    empty history: an empty history is [].
    """
    shapes = {"mapping": {}, "null": None}
    passed = shapes.get(history_shape, history)
    case = {
        "kind": "percentile",
        "name": name,
        "value": encode(value),
        "history": [encode(x) for x in history],
        "history_shape": history_shape,
    }
    try:
        case["expected"] = {
            "error": None,
            "percentile": encode(engine.percentile_rank(value, passed)),
        }
    except TypeError as error:
        case["expected"] = {"error": type(error).__name__, "percentile": None}
    return case


# ---------------------------------------------------------------------------
# The three blocks
# ---------------------------------------------------------------------------


def written_cases() -> list:
    """One case per branch, each named after the thing it is there to catch."""
    cases = []
    monthly_brent = engine.Quote(80.0, engine.USD_PER_BBL, "2026-02-01", engine.MONTHLY, "Brent")
    monthly_brent_t = engine.Quote(628.0, engine.USD_PER_T, "2026-07-01", engine.MONTHLY, "Brent date")

    cases.append(
        crack_case(
            "units_row_gasoil_745",
            engine.Quote(745.0, engine.USD_PER_T, "2026-07-01", engine.MONTHLY, "Gazole"),
            engine.Quote(80.0, engine.USD_PER_BBL, "2026-07-01", engine.MONTHLY, "Brent"),
            product_bbl_per_t=config.BBL_PER_T_GASOIL,
        )
    )
    cases.append(
        crack_case(
            "units_row_gasoline_833",
            engine.Quote(833.0, engine.USD_PER_T, "2026-07-01", engine.MONTHLY, "Eurosuper"),
            engine.Quote(80.0, engine.USD_PER_BBL, "2026-07-01", engine.MONTHLY, "Brent"),
            product_bbl_per_t=config.BBL_PER_T_GASOLINE,
        )
    )
    cases.append(
        crack_case(
            "opec_direct_dollars_per_barrel",
            engine.Quote(94.62, engine.USD_PER_BBL, "2026-02-01", engine.MONTHLY, "gasoil"),
            monthly_brent,
        )
    )
    cases.append(
        crack_case(
            "dgec_both_legs_in_dollars_per_tonne",
            engine.Quote(1160.0, engine.USD_PER_T, "2026-07-01", engine.MONTHLY, "Gazole"),
            monthly_brent_t,
            product_bbl_per_t=config.BBL_PER_T_GASOIL,
            brent_bbl_per_t=config.DGEC_BBL_PER_T_BRENT_NOTE,
        )
    )
    cases.append(
        crack_case(
            "missing_product_price",
            engine.Quote(math.nan, engine.USD_PER_BBL, "2026-02-01", engine.MONTHLY, "gasoil"),
            monthly_brent,
        )
    )
    cases.append(
        crack_case(
            "missing_crude_price",
            engine.Quote(94.62, engine.USD_PER_BBL, "2026-02-01", engine.MONTHLY, "gasoil"),
            engine.Quote(math.nan, engine.USD_PER_BBL, "2026-02-01", engine.MONTHLY, "Brent"),
        )
    )
    cases.append(
        crack_case(
            "unit_error_factor_on_a_barrel_price",
            engine.Quote(94.62, engine.USD_PER_BBL, "2026-02-01", engine.MONTHLY, "gasoil"),
            monthly_brent,
            product_bbl_per_t=config.BBL_PER_T_GASOIL,
        )
    )
    cases.append(
        crack_case(
            "unit_error_no_factor_on_a_tonne_price",
            engine.Quote(1160.0, engine.USD_PER_T, "2026-02-01", engine.MONTHLY, "Gazole"),
            monthly_brent,
        )
    )
    cases.append(
        crack_case(
            "unit_error_zero_factor",
            engine.Quote(1160.0, engine.USD_PER_T, "2026-02-01", engine.MONTHLY, "Gazole"),
            monthly_brent,
            product_bbl_per_t=0.0,
        )
    )
    cases.append(
        crack_case(
            "alignment_error_weekly_against_monthly",
            engine.Quote(1160.0, engine.USD_PER_T, "2026-02-06", engine.WEEKLY, "Gazole"),
            engine.Quote(80.0, engine.USD_PER_BBL, "2026-02-06", engine.MONTHLY, "Brent"),
            product_bbl_per_t=config.BBL_PER_T_GASOIL,
        )
    )
    cases.append(
        crack_case(
            "alignment_error_two_dates",
            engine.Quote(94.62, engine.USD_PER_BBL, "2026-02-06", engine.WEEKLY, "gasoil"),
            engine.Quote(80.0, engine.USD_PER_BBL, "2026-01-30", engine.WEEKLY, "Brent"),
        )
    )

    intensity = config.GAS_INTENSITY_MMBTU_PER_BBL
    base_yields = {"gasoil": 0.3355, "gasoline": 0.1324}

    cases.append(
        margin_case(
            "null_row_everything_zero",
            engine.MarginInputs(
                yields=base_yields,
                cracks={"gasoil": 0.0, "gasoline": 0.0},
                gas=engine.gas_from_ttf(0.0, 1.10),
                gas_intensity_mmbtu_per_bbl=intensity,
            ),
        )
    )
    cases.append(
        margin_case(
            "typical_month_with_threshold",
            engine.MarginInputs(
                yields=base_yields,
                cracks={"gasoil": 22.0, "gasoline": 12.0},
                gas=engine.gas_from_ttf(38.0, 1.08),
                residual_usd_bbl=-2.5,
                gas_intensity_mmbtu_per_bbl=intensity,
                other_variable_cost_usd_bbl=0.4,
                run_cut_threshold_usd_bbl=2.0,
            ),
            history=[1.0, 2.0, 3.0, 4.0, 5.0],
            threshold=2.0,
        )
    )
    cases.append(
        margin_case(
            "typical_month_without_threshold",
            engine.MarginInputs(
                yields=base_yields,
                cracks={"gasoil": 22.0, "gasoline": 12.0},
                gas=engine.gas_from_usd_mmbtu(12.5),
                gas_intensity_mmbtu_per_bbl=intensity,
            ),
            history=[1.0, 2.0, math.nan, 4.0],
        )
    )
    cases.append(
        margin_case(
            "missing_crack_propagates",
            engine.MarginInputs(
                yields=base_yields,
                cracks={"gasoil": 22.0, "gasoline": math.nan},
                gas=engine.gas_from_ttf(38.0, 1.08),
                gas_intensity_mmbtu_per_bbl=intensity,
                run_cut_threshold_usd_bbl=1.0,
            ),
            history=[1.0, 2.0],
        )
    )
    cases.append(
        margin_case(
            "no_products_at_all_margin_on_the_residual",
            engine.MarginInputs(
                yields={},
                cracks={},
                gas=engine.gas_from_usd_mmbtu(21.11),
                residual_usd_bbl=38.050505,
                gas_intensity_mmbtu_per_bbl=intensity,
            ),
            history=[10.0, 20.0, 30.0],
        )
    )
    cases.append(
        margin_case(
            "carrier_tie_broken_by_sorted_key_order",
            engine.MarginInputs(
                yields={"gasoil": 0.25, "gasoline": 0.25},
                cracks={"gasoil": 10.0, "gasoline": 10.0},
                gas=engine.gas_from_usd_mmbtu(10.0),
                gas_intensity_mmbtu_per_bbl=intensity,
            ),
        )
    )
    cases.append(
        margin_case(
            "no_leverage_zero_intensity",
            engine.MarginInputs(
                yields=base_yields,
                cracks={"gasoil": 22.0, "gasoline": 12.0},
                gas=engine.gas_from_ttf(38.0, 1.08),
                gas_intensity_mmbtu_per_bbl=0.0,
                run_cut_threshold_usd_bbl=1.0,
            ),
        )
    )
    cases.append(
        margin_case(
            "no_leverage_zero_yield_on_gasoil",
            engine.MarginInputs(
                yields={"gasoil": 0.0, "gasoline": 0.1324},
                cracks={"gasoil": 22.0, "gasoline": 12.0},
                gas=engine.gas_from_ttf(38.0, 1.08),
                gas_intensity_mmbtu_per_bbl=intensity,
                run_cut_threshold_usd_bbl=1.0,
            ),
        )
    )
    cases.append(
        margin_case(
            "negative_margin_bad_month",
            engine.MarginInputs(
                yields=base_yields,
                cracks={"gasoil": 2.0, "gasoline": -1.0},
                gas=engine.gas_from_ttf(90.0, 1.02),
                residual_usd_bbl=-1.0,
                gas_intensity_mmbtu_per_bbl=intensity,
                run_cut_threshold_usd_bbl=0.0,
            ),
            history=[-5.0, -1.0, 0.5, 3.0],
            threshold=0.0,
        )
    )
    cases.append(
        margin_case(
            "gasoil_key_absent_from_the_slate",
            engine.MarginInputs(
                yields={"gazole": 0.3355},
                cracks={"gazole": 22.0},
                gas=engine.gas_from_ttf(38.0, 1.08),
                gas_intensity_mmbtu_per_bbl=intensity,
                run_cut_threshold_usd_bbl=1.0,
            ),
            gasoil_key="gasoil",
        )
    )

    cases.append(
        decomposition_case(
            "residual_positive",
            20.0,
            base_yields,
            {"gasoil": 30.0, "gasoline": 15.0},
            unattributed=("naphta", "propane"),
        )
    )
    cases.append(
        decomposition_case(
            "residual_negative",
            6.5,
            base_yields,
            {"gasoil": 23.7, "gasoline": 16.8},
            unattributed=("butane", "carbureacteur", "fod"),
        )
    )
    cases.append(
        decomposition_case(
            "official_margin_of_zero",
            0.0,
            base_yields,
            {"gasoil": 10.0, "gasoline": 5.0},
        )
    )
    cases.append(
        decomposition_case(
            "missing_crack_in_the_decomposition",
            20.0,
            base_yields,
            {"gasoil": 30.0, "gasoline": math.nan},
        )
    )

    published = {
        "gazole": 1160.0,
        "fod": 1127.0,
        "carbureacteur": 1204.0,
        "fioul_lourd_1pct": 507.0,
    }
    cases.append(
        replication_case("published_only_july_2026", published, 628.0, 36.69)
    )
    complete = dict(published)
    complete.update(
        {
            "propane": 500.0,
            "butane": 520.0,
            "naphta": 600.0,
            "eurobob": 750.0,
            "essence_export": 700.0,
        }
    )
    cases.append(
        replication_case(
            "every_input_supplied",
            complete,
            620.0,
            5.0,
            freight=12.0,
            gas_cost=6.0,
        )
    )
    cases.append(
        replication_case(
            "freight_supplied_gas_missing",
            complete,
            620.0,
            5.0,
            freight=12.0,
        )
    )

    jodi = {
        "gasoline": 1180.0,
        "gasoil": 2140.0,
        "kerosene": 460.0,
        "resfuel": 540.0,
        "naphtha": 580.0,
    }
    cases.append(
        yields_case(
            "crude_intake_basis", jodi, 4995.8, config.YIELD_BASIS_CRUDE_INTAKE, False
        )
    )
    cases.append(
        yields_case(
            "total_feed_basis", jodi, 5690.0, config.YIELD_BASIS_TOTAL_FEED, False
        )
    )
    cases.append(
        yields_case(
            "normalised_share", jodi, 4995.8, config.YIELD_BASIS_CRUDE_INTAKE, True
        )
    )
    missing_line = dict(jodi)
    missing_line["naphtha"] = math.nan
    cases.append(
        yields_case(
            "missing_product_line",
            missing_line,
            4995.8,
            config.YIELD_BASIS_CRUDE_INTAKE,
            False,
        )
    )

    # -----------------------------------------------------------------------
    # The cases the 380 case fixture could not reach. Gate 2 self audit,
    # findings 5 and 8, one case per row of the divergence table in section (c).
    # -----------------------------------------------------------------------

    # Rows 1 to 3: what a JSON artifact carries where a price should be.
    for suffix, raw in (
        ("null", None),
        ("empty_string", ""),
        ("string_of_digits", "83.73"),
        ("boolean", True),
    ):
        cases.append(
            quote_case(
                "quote_value_%s_is_refused" % suffix,
                raw,
                engine.USD_PER_BBL,
                "2026-02-01",
                engine.MONTHLY,
                "gasoil",
            )
        )
    cases.append(
        quote_case(
            "quote_value_number_is_accepted",
            94.62,
            engine.USD_PER_BBL,
            "2026-02-01",
            engine.MONTHLY,
            "gasoil",
        )
    )
    cases.append(
        quote_case(
            "quote_window_is_not_one_of_three",
            94.62,
            engine.USD_PER_BBL,
            "2026-02-01",
            "fortnightly",
            "gasoil",
        )
    )
    cases.append(
        quote_case(
            "quote_date_is_not_an_iso_day",
            94.62,
            engine.USD_PER_BBL,
            "2026-02",
            engine.MONTHLY,
            "gasoil",
        )
    )

    # Finding 5: a leg that never went through makeQuote at all.
    aligned_leg = {
        "value": 94.62,
        "unit": engine.USD_PER_BBL,
        "date": "2026-02-01",
        "window": engine.MONTHLY,
        "label": "gasoil",
    }
    brent_leg = dict(aligned_leg, value=80.0, label="Brent")
    cases.append(
        raw_crack_case("raw_legs_that_carry_everything", aligned_leg, brent_leg)
    )
    cases.append(
        raw_crack_case(
            "raw_legs_with_no_window",
            {key: value for key, value in aligned_leg.items() if key != "window"},
            {key: value for key, value in brent_leg.items() if key != "window"},
        )
    )
    cases.append(
        raw_crack_case(
            "raw_legs_with_no_date_and_no_window",
            {"value": 94.62, "unit": engine.USD_PER_BBL, "label": "gasoil"},
            {"value": 80.0, "unit": engine.USD_PER_BBL, "label": "Brent"},
        )
    )
    cases.append(
        raw_crack_case(
            "raw_product_leg_with_no_date",
            {key: value for key, value in aligned_leg.items() if key != "date"},
            brent_leg,
        )
    )

    # Finding 8 row 6, and finding 1 mirrored into the fixture at last.
    cases.append(
        margin_refusal_case(
            "one_product_called_a_pipe_b_against_two_called_a_and_b",
            {
                "yields": {"a|b": 0.3},
                "cracks": {"a": 0.1, "b": 0.2},
                "gas": gas_payload(engine.gas_from_usd_mmbtu(10.0)),
                "residual_usd_bbl": 0.0,
                "gas_intensity_mmbtu_per_bbl": intensity,
                "other_variable_cost_usd_bbl": 0.0,
                "run_cut_threshold_usd_bbl": None,
                "margin_basis": engine.MARGIN_GROSS_OF_GAS,
            },
            lambda: engine.MarginInputs(
                yields={"a|b": 0.3},
                cracks={"a": 0.1, "b": 0.2},
                gas=engine.gas_from_usd_mmbtu(10.0),
                gas_intensity_mmbtu_per_bbl=intensity,
            ),
        )
    )
    cases.append(
        margin_refusal_case(
            "a_gas_price_on_a_margin_that_already_contains_one",
            {
                "yields": {},
                "cracks": {},
                "gas": gas_payload(engine.gas_from_usd_mmbtu(21.11)),
                "residual_usd_bbl": 38.050505,
                "gas_intensity_mmbtu_per_bbl": intensity,
                "other_variable_cost_usd_bbl": 0.0,
                "run_cut_threshold_usd_bbl": None,
                "margin_basis": engine.MARGIN_NET_OF_GAS,
            },
            lambda: engine.MarginInputs(
                yields={},
                cracks={},
                gas=engine.gas_from_usd_mmbtu(21.11),
                residual_usd_bbl=38.050505,
                gas_intensity_mmbtu_per_bbl=intensity,
                margin_basis=engine.MARGIN_NET_OF_GAS,
            ),
        )
    )
    cases.append(
        margin_refusal_case(
            "a_margin_basis_neither_engine_knows",
            {
                "yields": {"gasoil": 0.3355},
                "cracks": {"gasoil": 22.0},
                "gas": gas_payload(engine.gas_from_usd_mmbtu(10.0)),
                "residual_usd_bbl": 0.0,
                "gas_intensity_mmbtu_per_bbl": intensity,
                "other_variable_cost_usd_bbl": 0.0,
                "run_cut_threshold_usd_bbl": None,
                "margin_basis": "gross",
            },
            lambda: engine.MarginInputs(
                yields={"gasoil": 0.3355},
                cracks={"gasoil": 22.0},
                gas=engine.gas_from_usd_mmbtu(10.0),
                gas_intensity_mmbtu_per_bbl=intensity,
                margin_basis="gross",
            ),
        )
    )

    # The DGEC shape itself: a published margin that is already net of gas,
    # carried on the residual line, with no gas price and no intensity. This is
    # what crack.series.latest_view hands the engine every time the site loads.
    cases.append(
        margin_case(
            "dgec_mbr_already_net_of_gas",
            engine.MarginInputs(
                yields={},
                cracks={},
                residual_usd_bbl=38.050505,
                gas_intensity_mmbtu_per_bbl=0.0,
                other_variable_cost_usd_bbl=0.0,
                margin_basis=engine.MARGIN_NET_OF_GAS,
            ),
            history=[3.0, 11.168954, 24.782993, 38.050505],
            gas=engine.gas_from_usd_mmbtu(0.0),
        )
    )
    cases.append(
        margin_case(
            "net_of_gas_with_an_other_variable_cost_and_a_threshold",
            engine.MarginInputs(
                yields={},
                cracks={},
                residual_usd_bbl=24.782993,
                gas_intensity_mmbtu_per_bbl=0.0,
                other_variable_cost_usd_bbl=1.25,
                run_cut_threshold_usd_bbl=2.0,
                margin_basis=engine.MARGIN_NET_OF_GAS,
            ),
            history=[3.0, 11.168954, 24.782993],
            gas=engine.gas_from_usd_mmbtu(0.0),
        )
    )

    # Finding 8 row 4: no gas record at all. Python defaults it, the mirror used
    # to die. The margin is 3.0 on these numbers either way, and 3.0 is not the
    # answer to a TypeError.
    cases.append(
        margin_case(
            "no_gas_record_at_all",
            engine.MarginInputs(
                yields={"gasoil": 0.25},
                cracks={"gasoil": 12.0},
                gas_intensity_mmbtu_per_bbl=intensity,
            ),
            history=[1.0, 2.0, 3.0],
            gas=None,
        )
    )

    # Finding 8 row 5: the TTF path with no exchange rate. Python returns None
    # for the TTF breakeven and the mirror returned NaN, because undefined ===
    # null is false.
    ttf_without_fx = engine.GasCost(
        gas_usd_mmbtu=12.5,
        basis=engine.GAS_BASIS_TTF,
        ttf_eur_mwh=38.0,
        eurusd=None,
    )
    cases.append(
        margin_case(
            "ttf_gas_with_no_exchange_rate",
            engine.MarginInputs(
                yields=base_yields,
                cracks={"gasoil": 22.0, "gasoline": 12.0},
                gas=ttf_without_fx,
                gas_intensity_mmbtu_per_bbl=intensity,
                run_cut_threshold_usd_bbl=1.0,
            ),
            history=[1.0, 2.0, 3.0],
            gas=ttf_without_fx,
        )
    )
    cases.append(
        margin_case(
            "ttf_gas_with_an_absent_exchange_rate",
            engine.MarginInputs(
                yields=base_yields,
                cracks={"gasoil": 22.0, "gasoline": 12.0},
                gas=ttf_without_fx,
                gas_intensity_mmbtu_per_bbl=intensity,
                run_cut_threshold_usd_bbl=1.0,
            ),
            history=[1.0, 2.0, 3.0],
            gas=ttf_without_fx,
            gas_eurusd_absent=True,
        )
    )

    # The outputs(threshold=X) override, with X DIFFERENT from the threshold on
    # the inputs. Two fixture cases exercised the branch and in both of them the
    # two numbers were equal, so a mirror that ignored the argument passed.
    override_gas = engine.gas_from_ttf(38.0, 1.08)
    cases.append(
        margin_case(
            "a_threshold_argument_that_overrides_the_one_on_the_inputs",
            engine.MarginInputs(
                yields=base_yields,
                cracks={"gasoil": 22.0, "gasoline": 12.0},
                gas=override_gas,
                gas_intensity_mmbtu_per_bbl=intensity,
                other_variable_cost_usd_bbl=0.4,
                run_cut_threshold_usd_bbl=1.0,
            ),
            history=[1.0, 2.0, 3.0],
            threshold=4.0,
            gas=override_gas,
        )
    )

    # gasoil_key, on the slate that is the reason the parameter exists. DGEC
    # calls it gazole and every margin case in the fixture said gasoil.
    gazole_gas = engine.gas_from_ttf(38.0, 1.08)
    cases.append(
        margin_case(
            "the_dgec_slate_where_gasoil_is_called_gazole",
            engine.MarginInputs(
                yields={"gazole": 0.3355, "eurobob": 0.1324},
                cracks={"gazole": 22.0, "eurobob": 12.0},
                gas=gazole_gas,
                gas_intensity_mmbtu_per_bbl=intensity,
                run_cut_threshold_usd_bbl=1.0,
            ),
            history=[1.0, 2.0, 3.0],
            gasoil_key="gazole",
            gas=gazole_gas,
        )
    )

    # The gas wedge, which is now the gas story on the official margin and was
    # in neither the fixture nor the validator.
    for name, price in (
        ("august_2022", 70.04),
        ("august_2026", 21.11),
        ("a_zero_gas_price", 0.0),
    ):
        cases.append(
            gas_wedge_case(
                "gas_wedge_%s" % name,
                price,
                config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL,
                intensity,
            )
        )
    cases.append(
        gas_wedge_case("gas_wedge_with_no_embedded_intensity", 21.11, 0.0, intensity)
    )
    cases.append(
        gas_wedge_case("gas_wedge_on_a_missing_gas_price", math.nan, 0.0659, intensity)
    )

    cases.append(percentile_case("full_history", 2.0, [0.0, 1.0, 2.0, 3.0, 4.0]))
    cases.append(
        percentile_case("empty_mapping_history", 2.0, [], history_shape="mapping")
    )
    cases.append(percentile_case("null_history", 2.0, [], history_shape="null"))
    cases.append(
        percentile_case("history_with_holes", 2.0, [0.0, math.nan, 2.0, math.nan, 4.0])
    )
    cases.append(percentile_case("empty_history", 2.0, []))
    cases.append(percentile_case("all_missing_history", 2.0, [math.nan, math.nan]))
    cases.append(percentile_case("missing_value", math.nan, [0.0, 1.0]))
    cases.append(percentile_case("above_everything", 99.0, [0.0, 1.0, 2.0]))
    return cases


def random_cases(rng: random.Random, count: int = 240) -> list:
    """The randomised block SPEC.md section 7.1 asks for, at least 200 of them.

    Drawn over ranges the market has actually visited: cracks from minus 10 to
    plus 90 $/bbl, TTF from 3 to 340 EUR/MWh, which is the whole observed range
    of the Yahoo series, and gas intensities across the SPEC.md section 4.4
    band. Every fifth case carries a missing value somewhere, because a fixture
    without holes would only prove the two engines agree on complete data.
    """
    cases = []
    for index in range(count):
        products = ["gasoil", "gasoline"]
        if index % 3 == 0:
            products.append("jet")
        if index % 7 == 0:
            products.append("fuel_oil")

        yields = {name: round(rng.uniform(0.02, 0.45), 6) for name in products}
        cracks = {name: round(rng.uniform(-10.0, 90.0), 6) for name in products}
        if index % 5 == 0:
            cracks[products[index % len(products)]] = math.nan

        if index % 2 == 0:
            gas = engine.gas_from_ttf(
                round(rng.uniform(3.0, 340.0), 4), round(rng.uniform(0.85, 1.6), 4)
            )
        else:
            gas = engine.gas_from_usd_mmbtu(round(rng.uniform(1.5, 70.0), 4))

        threshold = None if index % 4 == 0 else round(rng.uniform(-3.0, 8.0), 4)
        inputs = engine.MarginInputs(
            yields=yields,
            cracks=cracks,
            gas=gas,
            residual_usd_bbl=round(rng.uniform(-8.0, 8.0), 6),
            gas_intensity_mmbtu_per_bbl=round(rng.uniform(0.12, 0.30), 6),
            other_variable_cost_usd_bbl=round(rng.uniform(0.0, 2.0), 6),
            run_cut_threshold_usd_bbl=threshold,
        )
        history = [round(rng.uniform(-6.0, 40.0), 4) for _ in range(rng.randint(0, 24))]
        if index % 6 == 0 and history:
            history[0] = math.nan
        cases.append(
            margin_case("random_margin_%03d" % index, inputs, history, threshold=None)
        )

        if index % 4 == 0:
            official = round(rng.uniform(-2.0, 40.0), 6)
            cases.append(
                decomposition_case(
                    "random_decomposition_%03d" % index, official, yields, cracks
                )
            )
        if index % 8 == 0:
            unit = engine.USD_PER_T if index % 16 == 0 else engine.USD_PER_BBL
            day = "2026-%02d-01" % (1 + index % 12)
            if unit == engine.USD_PER_T:
                product = engine.Quote(
                    round(rng.uniform(150.0, 2000.0), 4), unit, day, engine.MONTHLY, "p"
                )
                brent = engine.Quote(
                    round(rng.uniform(100.0, 1200.0), 4), unit, day, engine.MONTHLY, "b"
                )
                cases.append(
                    crack_case(
                        "random_crack_%03d" % index,
                        product,
                        brent,
                        product_bbl_per_t=config.BBL_PER_T_GASOIL,
                        brent_bbl_per_t=config.DGEC_BBL_PER_T_BRENT_NOTE,
                    )
                )
            else:
                product = engine.Quote(
                    round(rng.uniform(10.0, 200.0), 4), unit, day, engine.MONTHLY, "p"
                )
                brent = engine.Quote(
                    round(rng.uniform(10.0, 150.0), 4), unit, day, engine.MONTHLY, "b"
                )
                cases.append(
                    crack_case("random_crack_%03d" % index, product, brent)
                )
        if index % 20 == 0:
            cases.append(
                percentile_case(
                    "random_percentile_%03d" % index,
                    round(rng.uniform(-6.0, 40.0), 4),
                    [round(rng.uniform(-6.0, 40.0), 4) for _ in range(rng.randint(1, 30))],
                )
            )
    return cases


def coverage_of(cases) -> dict:
    """Count the branches the fixture actually reached, by inspection.

    Counted from the recorded RESULTS rather than from the builder, so a case
    that was meant to hit a branch and did not is visible here.
    """
    counts = {name: 0 for name in REQUIRED_COVERAGE}
    for case in cases:
        kind = case["kind"]
        expected = case["expected"]
        if kind == "crack":
            if expected.get("error") == "UnitError":
                counts["crack_unit_error"] += 1
            elif expected.get("error") == "AlignmentError":
                counts["crack_alignment_error"] += 1
            else:
                if expected["product_basis"] == engine.BASIS_DIRECT:
                    counts["crack_direct"] += 1
                else:
                    counts["crack_converted"] += 1
                if expected["value"] == "NaN":
                    counts["crack_missing_value"] += 1
        elif kind == "margin":
            if expected["threshold_identified"]:
                counts["margin_with_threshold"] += 1
            else:
                counts["margin_without_threshold"] += 1
            if any(v == "NaN" for v in expected["contributions"].values()):
                counts["margin_missing_crack"] += 1
            if not expected["contributions"]:
                counts["margin_empty_products"] += 1
            if case["name"] == "carrier_tie_broken_by_sorted_key_order":
                counts["margin_carrier_tie"] += 1
            if expected["gas_basis"] == engine.GAS_BASIS_TTF:
                counts["margin_ttf_gas"] += 1
            else:
                counts["margin_published_gas"] += 1
            if (
                expected["breakeven_ttf_eur_mwh"] is None
                and expected["threshold_identified"]
            ):
                counts["margin_no_leverage"] += 1
            if (
                isinstance(expected["margin_after_gas_usd_bbl"], float)
                and expected["margin_after_gas_usd_bbl"] < 0
            ):
                counts["margin_negative"] += 1
            if expected["margin_basis"] == engine.MARGIN_NET_OF_GAS:
                counts["margin_net_of_gas"] += 1
            if case["inputs"]["gas"] is None:
                counts["margin_gas_defaulted"] += 1
            if (
                case["inputs"]["gas"] is not None
                and case["inputs"]["gas"]["basis"] == engine.GAS_BASIS_TTF
                and case["inputs"]["gas"]["eurusd"] is None
            ):
                counts["margin_ttf_without_eurusd"] += 1
                if case["gas_eurusd_absent"]:
                    counts["margin_ttf_eurusd_absent"] += 1
            if (
                case["threshold"] is not None
                and case["inputs"]["run_cut_threshold_usd_bbl"] is not None
                and case["threshold"] != case["inputs"]["run_cut_threshold_usd_bbl"]
            ):
                counts["margin_threshold_override"] += 1
            if case["gasoil_key"] != "gasoil":
                counts["margin_gasoil_key_not_gasoil"] += 1
        elif kind == "quote":
            if expected["error"]:
                counts["quote_refused_value"] += 1
            else:
                counts["quote_accepted"] += 1
        elif kind == "raw_crack":
            if expected["error"]:
                counts["raw_leg_refused"] += 1
            else:
                counts["raw_leg_accepted"] += 1
        elif kind == "margin_refusal":
            if expected["error"] == "GasDoubleCountError":
                counts["margin_refusal_gas_double_count"] += 1
            elif case["name"].startswith("one_product_called"):
                counts["margin_refusal_keys"] += 1
        elif kind == "gas_wedge":
            counts["gas_wedge"] += 1
        elif kind == "decomposition":
            residual = expected["residual_usd_bbl"]
            if isinstance(residual, float) and residual > 0:
                counts["decomposition_positive_residual"] += 1
            if isinstance(residual, float) and residual < 0:
                counts["decomposition_negative_residual"] += 1
            if expected["residual_share"] == "NaN":
                counts["decomposition_zero_official"] += 1
        elif kind == "replication":
            if expected["missing_inputs"]:
                counts["replication_missing_inputs"] += 1
            else:
                counts["replication_complete"] += 1
        elif kind == "yields":
            counts["yields_%s" % {
                config.YIELD_BASIS_CRUDE_INTAKE: "crude_intake",
                config.YIELD_BASIS_TOTAL_FEED: "total_feed",
                config.YIELD_BASIS_NORMALISED: "normalised",
            }[expected["basis"]]] += 1
        elif kind == "percentile":
            if case.get("history_shape") == "mapping":
                counts["percentile_empty_mapping"] += 1
            if case.get("history_shape") == "null":
                counts["percentile_refuses_a_null_history"] += 1
                continue
            if expected["percentile"] is None:
                counts["percentile_empty"] += 1
            elif any(x == "NaN" for x in case["history"]):
                counts["percentile_with_holes"] += 1
            else:
                counts["percentile_full"] += 1
    return counts


def build() -> dict:
    rng = random.Random(SEED)
    cases = written_cases() + random_cases(rng)
    counts = coverage_of(cases)
    missing = sorted(name for name, count in counts.items() if count == 0)
    if missing:
        raise SystemExit(
            "the fixture reaches no case for: %s. A parity fixture that stopped "
            "exercising a branch would pass a validator that no longer tests it"
            % ", ".join(missing)
        )
    randomised = sum(1 for case in cases if case["name"].startswith("random_"))
    if randomised < 200:
        raise SystemExit(
            "SPEC.md section 7.1 asks for at least 200 randomised input sets and "
            "this fixture has %d" % randomised
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "seed": SEED,
        "generator": "scripts/gen_fixtures.py",
        "engine": "src/crack/engine.py",
        "mirror": "src/engine.js",
        "tolerance": 1e-9,
        "note": (
            "Python output for every case, produced by crack.engine. "
            "tools/validate-engine.mjs runs src/engine.js against it and asserts "
            "agreement to the tolerance above on every line. SPEC.md section 7.1: "
            "if they disagree, fix the JavaScript to match Python, never the "
            "reverse. Missing numbers are the string NaN; a value that does not "
            "exist is null, and the two are not the same thing."
        ),
        "counts": {
            "total": len(cases),
            "randomised": randomised,
            "written": len(cases) - randomised,
        },
        "coverage": counts,
        "cases": cases,
    }


def serialise(fixture: dict) -> str:
    return json.dumps(fixture, indent=2, sort_keys=False, ensure_ascii=True) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="write nothing, exit 1 if the committed fixture is stale",
    )
    parser.add_argument("--out", default=None, help="write to another directory")
    args = parser.parse_args(argv)

    fixture = build()
    text = serialise(fixture)
    directory = Path(args.out) if args.out else FIXTURES
    path = directory / FILENAME

    if args.check:
        if not path.exists():
            print("MISSING %s" % path)
            return 1
        # Bytes, not text. path.read_text() applies universal newlines, so a
        # CRLF file on Windows would read back as LF and --check would say a
        # fixture that is not byte identical is byte identical. The whole
        # claim this mode makes is about bytes, so it compares bytes.
        current = path.read_bytes()
        if current != text.encode("ascii"):
            print(
                "STALE %s. The engine has changed since the fixture was written. "
                "Regenerate with: python scripts/gen_fixtures.py" % path
            )
            return 1
        print(
            "byte identical: %s matches a rebuild at seed %d, %d cases. "
            "Regenerating would leave the working tree clean"
            % (path, fixture["seed"], fixture["counts"]["total"])
        )
        return 0

    directory.mkdir(parents=True, exist_ok=True)
    # newline="\n", explicitly. The default would translate every \n to \r\n on
    # Windows, which .gitattributes then normalises back to LF on commit, so the
    # committed file and the working tree file would differ by 20,000 bytes and
    # "regenerate and nothing changes" would be true on Linux and false here.
    # ASCII because serialise() writes ensure_ascii=True and node reads this.
    path.write_bytes(text.encode("ascii"))
    print(
        "wrote %s: %d cases, %d randomised, %d written"
        % (
            path,
            fixture["counts"]["total"],
            fixture["counts"]["randomised"],
            fixture["counts"]["written"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
