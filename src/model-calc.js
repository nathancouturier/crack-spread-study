/* model-calc.js
 *
 * The one function the Model view computes through, docs/design.md Part 8.2,
 * "The parity". It calls src/engine.js and implements no formula of its own:
 * every figure it returns is a field of an engine record. It is the mirror of
 * scripts/gen_model_cases.py compute, line for line, and tools/validate-engine.mjs
 * runs it over data/fixtures/model-cases.json, which holds what crack.engine
 * computes in Python for every preset and every named edit, to 1e-9.
 *
 * WHAT IT DOES, in the order the Python does it
 *
 *   products     the model's products with both a crack and a yield; a product
 *                missing either is EXCLUDED, never priced at zero
 *   gross        engine.evaluate with no gas, read for its gross margin only
 *   after gas    engine.evaluate on MARGIN_GROSS_OF_GAS with gasFromTtf and no
 *                residual and no threshold, but only when every gas input is
 *                present; a missing one is named in blockedBy and everything
 *                after gas is null, never zero
 *   breakevens   breakevenTtf, breakevenGasUsdMmbtu and breakevenCrack on
 *                gasoil, each against the target the artifact carries, a
 *                margin of zero; never against a run cut threshold, which the
 *                study did not identify
 *   gap          engine.decomposeOfficial(mbr, yields, cracks): the ministry's
 *                MBR less this model's gross margin
 *
 * The margin here is GROSS of gas, so subtracting gas is correct. The
 * ministry's MBR is already net of its own gas allowance and is never handed to
 * evaluate: it enters only decomposeOfficial, which subtracts no gas.
 *
 * `values` is { cracks: {id: number|null}, yields: {id: number|null},
 * ttf_eur_mwh, eurusd, gas_intensity_mmbtu_per_bbl,
 * other_variable_cost_usd_bbl, mbr_usd_bbl }, the preset shape of
 * data/model.json with the preset's official MBR beside it. A value that is not
 * a finite number counts as missing.
 *
 * Numeric literals: none but 0. tools/check-literals.mjs.
 */

import * as engine from "./engine.js";

/** The gasoil key the crack breakeven is taken on, as in the Python. */
export const BREAKEVEN_PRODUCT = "gasoil";

/** The inputs without which nothing after gas can be computed, in the order
 *  the Python names them. */
export const GAS_INPUTS = Object.freeze([
  "ttf_eur_mwh",
  "eurusd",
  "gas_intensity_mmbtu_per_bbl",
  "other_variable_cost_usd_bbl",
]);

/** True for a value the model can use: a finite number. */
export function present(value) {
  return typeof value === "number" && Number.isFinite(value);
}

export function compute(values, target, productsOrder) {
  const cracksIn = values.cracks || {};
  const yieldsIn = values.yields || {};
  const included = productsOrder.filter((p) => present(cracksIn[p]) && present(yieldsIn[p]));
  const excluded = productsOrder.filter((p) => !included.includes(p));
  const yields = {};
  const cracks = {};
  for (const p of included) {
    yields[p] = yieldsIn[p];
    cracks[p] = cracksIn[p];
  }
  const blockedBy = GAS_INPUTS.filter((name) => !present(values[name]));

  const noGas = engine.evaluate(engine.marginInputs({
    yields,
    cracks,
    gas: engine.gasFromUsdMmbtu(0),
    gasIntensityMmbtuPerBbl: 0,
    otherVariableCostUsdBbl: 0,
    marginBasis: engine.MARGIN_GROSS_OF_GAS,
  }));
  const contributions = {};
  for (const p of included) contributions[p] = noGas.contributions[p];

  // The yields the reader has entered, summed over every product that has one,
  // for the sentence about a barrel holding more than a barrel. Not a margin.
  let yieldTotal = 0;
  for (const p of productsOrder) if (present(yieldsIn[p])) yieldTotal += yieldsIn[p];

  const out = {
    included,
    excluded,
    blockedBy,
    contributions,
    attributedUsdBbl: noGas.attributedUsdBbl,
    grossMarginUsdBbl: noGas.grossMarginUsdBbl,
    carrier: noGas.carrier,
    gasUsdMmbtu: null,
    gasCostUsdBbl: null,
    otherVariableCostUsdBbl: null,
    marginAfterGasUsdBbl: null,
    breakevenTtfEurMwh: null,
    breakevenGasUsdMmbtu: null,
    breakevenGasoilUsdBbl: null,
    thresholdIdentified: false,
    headroomUsdBbl: null,
    residualUsdBbl: null,
    coveredVolumeYield: null,
    yieldTotal,
  };

  if (!blockedBy.length) {
    const inputs = engine.marginInputs({
      yields,
      cracks,
      gas: engine.gasFromTtf(values.ttf_eur_mwh, values.eurusd),
      gasIntensityMmbtuPerBbl: values.gas_intensity_mmbtu_per_bbl,
      otherVariableCostUsdBbl: values.other_variable_cost_usd_bbl,
      marginBasis: engine.MARGIN_GROSS_OF_GAS,
    });
    const result = engine.evaluate(inputs);
    out.gasUsdMmbtu = result.gasUsdMmbtu;
    out.gasCostUsdBbl = result.gasCostUsdBbl;
    out.otherVariableCostUsdBbl = result.otherVariableCostUsdBbl;
    out.marginAfterGasUsdBbl = result.marginAfterGasUsdBbl;
    out.breakevenTtfEurMwh = engine.breakevenTtf(inputs, target);
    out.breakevenGasUsdMmbtu = engine.breakevenGasUsdMmbtu(inputs, target);
    out.breakevenGasoilUsdBbl = included.includes(BREAKEVEN_PRODUCT) ? engine.breakevenCrack(inputs, BREAKEVEN_PRODUCT, target) : null;
    out.thresholdIdentified = result.thresholdIdentified;
    out.headroomUsdBbl = result.headroomUsdBbl;
  }
  if (present(values.mbr_usd_bbl)) {
    const decomposition = engine.decomposeOfficial(values.mbr_usd_bbl, yields, cracks);
    out.residualUsdBbl = decomposition.residualUsdBbl;
    out.coveredVolumeYield = decomposition.coveredVolumeYield;
  }
  return out;
}

/** The field names of data/fixtures/model-cases.json, against this record's. */
export const FIXTURE_FIELDS = Object.freeze({
  included: "included",
  excluded: "excluded",
  blocked_by: "blockedBy",
  contributions: "contributions",
  attributed_usd_bbl: "attributedUsdBbl",
  gross_margin_usd_bbl: "grossMarginUsdBbl",
  carrier: "carrier",
  gas_usd_mmbtu: "gasUsdMmbtu",
  gas_cost_usd_bbl: "gasCostUsdBbl",
  other_variable_cost_usd_bbl: "otherVariableCostUsdBbl",
  margin_after_gas_usd_bbl: "marginAfterGasUsdBbl",
  breakeven_ttf_eur_mwh: "breakevenTtfEurMwh",
  breakeven_gas_usd_mmbtu: "breakevenGasUsdMmbtu",
  breakeven_gasoil_usd_bbl: "breakevenGasoilUsdBbl",
  threshold_identified: "thresholdIdentified",
  headroom_usd_bbl: "headroomUsdBbl",
  residual_usd_bbl: "residualUsdBbl",
  covered_volume_yield: "coveredVolumeYield",
});
