/**
 * The margin model, again, in JavaScript. SPEC.md sections 4.2 to 4.5 and 7.1.
 *
 * This file is a mirror of src/crack/engine.py and it is allowed to be nothing
 * else. Every function here has the same name, the same arguments in the same
 * order, the same guards and the same arithmetic in the same order as the
 * Python one, because tools/validate-engine.mjs runs both against
 * data/fixtures/engine-cases.json and asserts they agree to 1e-9 on every line.
 *
 * SPEC.md section 7.1 is explicit about which way the repair goes: "If they
 * disagree, fix the JavaScript to match Python, never the reverse." So when you
 * are tempted to improve something here, improve engine.py and then copy it.
 *
 * Why a mirror at all
 * -------------------
 * The Model view of SPEC.md section 7.2 lets a visitor move a crack, a yield,
 * the TTF price and the gas intensity and watch the margin recompute in place.
 * That has to happen in the browser, and a site that recomputed the margin with
 * arithmetic slightly different from the pipeline's would be quietly lying on
 * its most interactive screen.
 *
 * What is NOT in this file
 * ------------------------
 * Data. SPEC.md section 0.1 says all site data is JSON loaded with fetch and
 * never hardcoded in a JS module, and SPEC.md section 2 rule 2 allows unit
 * constants as the single exception. So the three conversion factors are here,
 * each with its citation, and everything else, the gas intensity, the yields,
 * the DGEC slate, the thresholds, arrives as an argument.
 *
 * Floating point
 * --------------
 * Sums run over sorted keys, left to right, exactly as the Python does.
 * Object.keys(...).sort() and Python's sorted() agree on ASCII keys, and
 * changing either order would move the last bits of a total.
 *
 * Missing data
 * ------------
 * NaN in, NaN out, SPEC.md section 2 rule 1. null is a different thing and
 * means the question has no answer: no threshold, no leverage, no history. The
 * two are never interchanged, here or in the fixture.
 */

// ---------------------------------------------------------------------------
// SPEC.md section 4.1, the unit constants. The only numbers in this file.
// ---------------------------------------------------------------------------

/**
 * Barrels per tonne of ICE Low Sulphur Gasoil, the divisor in the ICE gasoil
 * crack contract. https://www.ice.com/products/6753331 . It is a contract
 * convention and not a density, and src/crack/config.py carries the 44 month
 * measurement behind it.
 */
export const BBL_PER_T_GASOIL = 7.45;

/**
 * Barrels per tonne of Eurobob gasoline, ICE Eurobob vs Brent crack contract,
 * https://www.ice.com/products/6753285 . Same status, same caveat, and a much
 * larger measured spread against the physical assessments.
 */
export const BBL_PER_T_GASOLINE = 8.33;

/**
 * MMBtu per MWh. A unit definition: 1 MWh is 3.6e9 J, 1 MMBtu(IT) is
 * 1.05505585262e9 J, and SPEC.md section 4.1 fixes the seven figure rounding.
 */
export const MMBTU_PER_MWH = 3.412142;

// ---------------------------------------------------------------------------
// The vocabulary, mirroring crack.engine
// ---------------------------------------------------------------------------

export const USD_PER_BBL = 'usd_per_bbl';
export const USD_PER_T = 'usd_per_t';
export const UNITS = [USD_PER_BBL, USD_PER_T];

export const DAILY = 'daily';
export const WEEKLY = 'weekly';
export const MONTHLY = 'monthly';
export const WINDOWS = [DAILY, WEEKLY, MONTHLY];

export const BASIS_DIRECT = 'usd_per_bbl_direct';
export const BASIS_CONVERTED = 'usd_per_t_converted';

export const GAS_BASIS_TTF = 'ttf_eur_mwh';
export const GAS_BASIS_PUBLISHED = 'published_usd_mmbtu';

/**
 * The margin is gross of purchased natural gas, so SPEC.md section 4.4's
 * subtraction applies to it.
 */
export const MARGIN_GROSS_OF_GAS = 'gross_of_gas';

/**
 * The margin already contains the refinery's gas purchase and nothing may
 * subtract a gas cost from it again. DGEC's published MBR is this one: its
 * methodology note takes "les couts d'achat du Brent date FAB et du gaz naturel
 * CAF" off the product revenues before publishing the figure. Mirrors
 * crack.engine.MARGIN_NET_OF_GAS, which carries the whole reading.
 */
export const MARGIN_NET_OF_GAS = 'net_of_gas';

export const MARGIN_BASES = [MARGIN_GROSS_OF_GAS, MARGIN_NET_OF_GAS];

export const YIELD_BASIS_CRUDE_INTAKE = 'crude_intake';
export const YIELD_BASIS_TOTAL_FEED = 'total_feed';
export const YIELD_BASIS_NORMALISED = 'normalised_share';

/** A price met a factor it should not have met, or one it needed and lacked. */
export class UnitError extends Error {
  constructor(message) {
    super(message);
    this.name = 'UnitError';
  }
}

/** Two legs of a crack did not share a date or an averaging window. */
export class AlignmentError extends Error {
  constructor(message) {
    super(message);
    this.name = 'AlignmentError';
  }
}

/**
 * A gas cost was about to be subtracted from a margin that already has one.
 * Mirrors crack.engine.GasDoubleCountError.
 */
export class GasDoubleCountError extends Error {
  constructor(message) {
    super(message);
    this.name = 'GasDoubleCountError';
  }
}

/**
 * Python raises ValueError and KeyError where JavaScript would reach for a
 * plain Error, and tools/validate-engine.mjs compares the CLASS a case refuses
 * with. Two divergent error names would either fail the validator or, worse,
 * not be compared at all, which is what the Gate 2 self audit found in section
 * (c). So this file names its refusals after Python's, because it is a mirror
 * and SPEC.md section 7.1 says which way the copying goes.
 */
export class ValueError extends Error {
  constructor(message) {
    super(message);
    this.name = 'ValueError';
  }
}

export class KeyError extends Error {
  constructor(message) {
    super(message);
    this.name = 'KeyError';
  }
}

function isMissing(x) {
  return Number.isNaN(x);
}

/**
 * An object with no prototype, used for every mapping this engine builds.
 *
 * Not decoration. A product key of "__proto__" assigned into a plain object
 * literal sets the prototype instead of creating an own property, so the key
 * silently disappears and its contribution is dropped from the margin, while
 * Python keeps it and attributes it. Gate 2 self audit, section (c) row 8.
 */
function emptyMapping() {
  return Object.create(null);
}

/**
 * Sorted keys of a plain object. The mirror of Python's sorted(mapping).
 * Every sum in this file runs in this order so that the two engines add the
 * same floats in the same sequence.
 */
function sortedKeys(mapping) {
  return Object.keys(mapping).sort();
}

// ---------------------------------------------------------------------------
// SPEC.md section 4.2, cracks
// ---------------------------------------------------------------------------

/**
 * One price observation with its date and averaging window.
 *
 * The mirror of crack.engine.Quote, including the validation, because a Quote
 * that accepted a window the Python refuses would let the browser compute a
 * crack the pipeline would not.
 */
export function makeQuote(value, unit, date, window, label = '') {
  if (!UNITS.includes(unit)) {
    throw new UnitError(
      `quote ${label || date} carries unit ${unit}, not one of ${UNITS.join(', ')}`
    );
  }
  if (!WINDOWS.includes(window)) {
    throw new AlignmentError(
      `quote ${label || date} carries window ${window}, not one of ${WINDOWS.join(', ')}`
    );
  }
  if (typeof date !== 'string' || date.length !== 10) {
    throw new AlignmentError(
      `quote ${label} carries date ${date}. Dates are ISO 'YYYY-MM-DD' strings here`
    );
  }
  // A price is a number or it is nothing. This used to be Number(value), and
  // Number(null) is 0 and Number('') is 0, so a JSON artifact with a hole in it
  // gave the browser a quote of 0 $/bbl where the pipeline raised. Gate 2 self
  // audit, finding 8, rows 1 to 3. NaN is a number and still passes: it is how
  // SPEC.md section 2 rule 1 carries a missing observation.
  if (typeof value !== 'number') {
    throw new UnitError(
      `quote ${label || date} carries value ${value}, which is not a number. A ` +
        'missing price is NaN, SPEC.md section 2 rule 1, and null, an empty ' +
        'string and a string of digits are all refused here so that this engine ' +
        'cannot read one of them as zero'
    );
  }
  return { value, unit, date, window, label };
}

function usdTToUsdBbl(priceUsdT, bblPerT) {
  if (bblPerT === 0) {
    throw new UnitError(
      'a barrels per tonne factor of zero has no meaning. Python would raise ' +
        'here and JavaScript would return Infinity, so both engines refuse it ' +
        'rather than disagree, SPEC.md section 7.1'
    );
  }
  return priceUsdT / bblPerT;
}

/** One quote in dollars per barrel, converting only if it has to. */
export function toUsdBbl(quote, bblPerT = null) {
  if (quote.unit === USD_PER_BBL) {
    if (bblPerT !== null && bblPerT !== undefined) {
      throw new UnitError(
        `quote ${quote.label || quote.date} is already in ${USD_PER_BBL} and was ` +
          `handed a barrels per tonne factor of ${bblPerT}`
      );
    }
    return quote.value;
  }
  if (bblPerT === null || bblPerT === undefined) {
    throw new UnitError(
      `quote ${quote.label || quote.date} is in ${USD_PER_T} and no barrels per ` +
        'tonne factor was given. SPEC.md section 4.1: never guess a factor'
    );
  }
  return usdTToUsdBbl(quote.value, bblPerT);
}

/**
 * One leg carries an averaging window and a date, or it is not a leg.
 *
 * THIS IS FINDING 5 OF THE GATE 2 SELF AUDIT. requireAligned compared
 * product.window with brent.window, and undefined !== undefined is false, so
 * crack() on two bare objects with no window and no date returned a number:
 * 71.97136465324384, window undefined, date undefined. makeQuote validates and
 * nothing forced a caller through it. SPEC.md section 4.2's alignment rule is
 * the one guarantee the Gate 2 brief singled out as needing to be structural,
 * and it cannot be structural in Python and duck typed in the browser, so both
 * engines check the leg itself before comparing two of them.
 */
function requireLeg(leg, role) {
  const window = leg === null || leg === undefined ? undefined : leg.window;
  const date = leg === null || leg === undefined ? undefined : leg.date;
  if (!WINDOWS.includes(window)) {
    throw new AlignmentError(
      `the ${role} leg carries window ${window}, not one of ${WINDOWS.join(', ')}. ` +
        'SPEC.md section 4.2 compares the two legs windows, and a leg with no ' +
        'window would compare equal to another leg with no window'
    );
  }
  if (typeof date !== 'string' || date.length !== 10) {
    throw new AlignmentError(
      `the ${role} leg carries date ${date}. SPEC.md section 4.2 compares the ` +
        "two legs dates and they are ISO 'YYYY-MM-DD' strings here"
    );
  }
}

/** Refuse two legs that do not share a date and an averaging window. */
export function requireAligned(product, brent) {
  requireLeg(product, 'product');
  requireLeg(brent, 'brent');
  if (product.window !== brent.window) {
    throw new AlignmentError(
      `cannot crack a ${product.window} product (${product.label || 'product'}, ` +
        `${product.date}) against a ${brent.window} crude (${brent.label || 'brent'}, ` +
        `${brent.date}). SPEC.md section 4.2`
    );
  }
  if (product.date !== brent.date) {
    throw new AlignmentError(
      `cannot crack ${product.label || 'product'} dated ${product.date} against ` +
        `${brent.label || 'brent'} dated ${brent.date}. SPEC.md section 4.2`
    );
  }
}

/** SPEC.md section 4.2, the $/t path. */
export function crackFromUsdT(priceUsdT, bblPerT, brentUsdBbl) {
  return usdTToUsdBbl(priceUsdT, bblPerT) - brentUsdBbl;
}

/** SPEC.md section 4.2, the $/bbl path. No conversion at all. */
export function crackFromUsdBbl(priceUsdBbl, brentUsdBbl) {
  return priceUsdBbl - brentUsdBbl;
}

/** The safe front door: both paths, the alignment check, the provenance. */
export function crack(product, brent, options = {}) {
  const productBblPerT =
    options.productBblPerT === undefined ? null : options.productBblPerT;
  const brentBblPerT =
    options.brentBblPerT === undefined ? null : options.brentBblPerT;
  requireAligned(product, brent);
  const productUsdBbl = toUsdBbl(product, productBblPerT);
  const brentUsdBbl = toUsdBbl(brent, brentBblPerT);
  return {
    value: productUsdBbl - brentUsdBbl,
    date: product.date,
    window: product.window,
    productLabel: product.label,
    productUsdBbl,
    brentUsdBbl,
    productBasis: product.unit === USD_PER_BBL ? BASIS_DIRECT : BASIS_CONVERTED,
    productBblPerT,
    brentBblPerT
  };
}

/** Strip a set of cracks to values, refusing a set that is misaligned. */
export function crackValues(cracks) {
  const names = sortedKeys(cracks);
  if (names.length === 0) {
    return emptyMapping();
  }
  const first = cracks[names[0]];
  for (let i = 1; i < names.length; i += 1) {
    const other = cracks[names[i]];
    if (other.window !== first.window || other.date !== first.date) {
      throw new AlignmentError(
        `cracks in one decomposition must share a date and a window: ` +
          `${names[0]} is ${first.window} ${first.date} but ${names[i]} is ` +
          `${other.window} ${other.date}`
      );
    }
  }
  const out = emptyMapping();
  names.forEach((name) => {
    out[name] = cracks[name].value;
  });
  return out;
}

// ---------------------------------------------------------------------------
// Yields
// ---------------------------------------------------------------------------

/** Tonnes of product per tonne of crude into barrels per barrel. */
export function massYieldToVolumeYield(massYield, bblPerTProduct, bblPerTCrude) {
  if (bblPerTCrude === 0) {
    throw new UnitError('a crude barrels per tonne factor of zero has no meaning');
  }
  return (massYield * bblPerTProduct) / bblPerTCrude;
}

/**
 * SPEC.md section 4.3 layer 4. Output by product over a named denominator.
 *
 * The notes argument mirrors config.YIELD_BASIS_NOTES, which Python reads from
 * its own config and this module may not hold: SPEC.md section 0.1 keeps data
 * out of JS modules, and a paragraph of prose about a denominator is data. The
 * Python record's docstring says the note is carried with the data "so a JSON
 * artifact cannot lose it", and the mirror used to lose it, which is finding 11
 * of the Gate 2 self audit. So it arrives as an argument, the way the DGEC
 * method does in replicateMbr, and the parity fixture carries it.
 */
export function observedYields(outputKbd, denominatorKbd, basis, notes = {}) {
  if (basis !== YIELD_BASIS_CRUDE_INTAKE && basis !== YIELD_BASIS_TOTAL_FEED) {
    throw new ValueError(
      `observedYields builds on a JODI denominator, so basis must be ` +
        `${YIELD_BASIS_CRUDE_INTAKE} or ${YIELD_BASIS_TOTAL_FEED}`
    );
  }
  if (denominatorKbd === 0) {
    throw new ValueError(
      'a refinery denominator of zero kb/d is not a refinery. A month with no ' +
        'reported intake is NaN, not zero, SPEC.md section 2 rule 1'
    );
  }
  const names = sortedKeys(outputKbd);
  const yields = emptyMapping();
  let total = 0;
  names.forEach((name) => {
    yields[name] = outputKbd[name] / denominatorKbd;
  });
  names.forEach((name) => {
    total += yields[name];
  });
  return { yields, total, basis, denominatorKbd, note: noteFor(notes, basis) };
}

function noteFor(notes, basis) {
  const value = notes === null || notes === undefined ? undefined : notes[basis];
  return value === undefined ? '' : value;
}

/** The same vector scaled to sum to 1, relabelled as a share of output. */
export function normaliseYields(observed, notes = {}) {
  const names = sortedKeys(observed.yields);
  const scaled = emptyMapping();
  let total;
  if (observed.total === 0 || isMissing(observed.total)) {
    names.forEach((name) => {
      scaled[name] = NaN;
    });
    total = NaN;
  } else {
    names.forEach((name) => {
      scaled[name] = observed.yields[name] / observed.total;
    });
    total = 0;
    names.forEach((name) => {
      total += scaled[name];
    });
  }
  return {
    yields: scaled,
    total,
    basis: YIELD_BASIS_NORMALISED,
    denominatorKbd: observed.denominatorKbd,
    note: noteFor(notes, YIELD_BASIS_NORMALISED)
  };
}

// ---------------------------------------------------------------------------
// SPEC.md section 4.4, run economics
// ---------------------------------------------------------------------------

/** SPEC.md section 4.4: gas_usd_mmbtu = ttf_eur_mwh * eurusd / MMBTU_PER_MWH. */
export function gasFromTtf(ttfEurMwh, eurusd) {
  return {
    gasUsdMmbtu: (ttfEurMwh * eurusd) / MMBTU_PER_MWH,
    basis: GAS_BASIS_TTF,
    ttfEurMwh,
    eurusd
  };
}

/** The published path. The World Bank series is already $/MMBtu. */
export function gasFromUsdMmbtu(gasUsdMmbtu) {
  return {
    gasUsdMmbtu,
    basis: GAS_BASIS_PUBLISHED,
    ttfEurMwh: null,
    eurusd: null
  };
}

/** SPEC.md section 4.4: gas_cost = gas_intensity * gas_usd_mmbtu. */
export function gasCostUsdBbl(gasIntensityMmbtuPerBbl, gasUsdMmbtu) {
  return gasIntensityMmbtuPerBbl * gasUsdMmbtu;
}

/**
 * Two gas intensities priced at one gas price, next to each other.
 *
 * The mirror of crack.engine.gas_wedge, and the honest version of SPEC.md
 * section 4.4 for a margin that is already net of gas. It deducts nothing from
 * anything: it says what the margin's own embedded gas assumption costs at this
 * price and what this study's intensity would cost at the same price, and the
 * wedge is the difference. Read crack.engine.GasWedge before showing it.
 */
export function gasWedge(
  gasUsdMmbtu,
  embeddedIntensityMmbtuPerBbl,
  studyIntensityMmbtuPerBbl
) {
  const embeddedCost = gasCostUsdBbl(embeddedIntensityMmbtuPerBbl, gasUsdMmbtu);
  const studyCost = gasCostUsdBbl(studyIntensityMmbtuPerBbl, gasUsdMmbtu);
  const ratio =
    embeddedIntensityMmbtuPerBbl === 0
      ? NaN
      : studyIntensityMmbtuPerBbl / embeddedIntensityMmbtuPerBbl;
  return {
    gasUsdMmbtu,
    embeddedIntensityMmbtuPerBbl,
    studyIntensityMmbtuPerBbl,
    embeddedCostUsdBbl: embeddedCost,
    studyCostUsdBbl: studyCost,
    wedgeUsdBbl: studyCost - embeddedCost,
    ratio
  };
}

/**
 * Normalise a margin input object, mirroring crack.engine.MarginInputs.
 *
 * Every field is required except the ones SPEC.md gives a default: the residual
 * and the other variable cost are zero, which is what makes the SPEC.md section
 * 9 Null row exact, and the threshold is null, which is SPEC.md section 6.2's
 * unidentified case. The gas intensity has NO default here, because it is a
 * derived figure rather than a unit constant and SPEC.md section 0.1 keeps
 * derived figures out of JS modules.
 */
export function marginInputs(raw) {
  const yields = raw.yields || {};
  const cracks = raw.cracks || {};
  const yieldNames = sortedKeys(yields);
  const crackNames = sortedKeys(cracks);
  // Element by element, not yieldNames.join('|') against crackNames.join('|').
  // The joined form cannot tell one product called "a|b" from two called "a"
  // and "b", and Python compares sets, which can. Gate 2 self audit, finding 10.
  const sameKeys =
    yieldNames.length === crackNames.length &&
    yieldNames.every((name, index) => name === crackNames[index]);
  if (!sameKeys) {
    throw new ValueError(
      'every product needs both a yield and a crack. Yields: ' +
        `${yieldNames.join(', ') || 'none'}. Cracks: ${crackNames.join(', ') || 'none'}`
    );
  }
  if (raw.gasIntensityMmbtuPerBbl === undefined) {
    throw new ValueError(
      'gasIntensityMmbtuPerBbl is required. It is a derived figure, not a unit ' +
        'constant, so it arrives from JSON and is never defaulted in this module'
    );
  }
  // Python defaults the gas record to gas_from_usd_mmbtu(0.0) and this module
  // used to have no default at all, so a margin with no gas came back as 3.0
  // $/bbl in the pipeline and a TypeError in the browser. Gate 2 self audit,
  // finding 8 row 4.
  const gas = raw.gas === undefined || raw.gas === null ? gasFromUsdMmbtu(0) : raw.gas;
  const marginBasis =
    raw.marginBasis === undefined ? MARGIN_GROSS_OF_GAS : raw.marginBasis;
  if (!MARGIN_BASES.includes(marginBasis)) {
    throw new ValueError(
      `marginBasis is ${marginBasis}, not one of ${MARGIN_BASES.join(', ')}. A ` +
        'margin has to say whether the gas purchase is already inside it'
    );
  }
  if (marginBasis === MARGIN_NET_OF_GAS) {
    const term = raw.gasIntensityMmbtuPerBbl * gas.gasUsdMmbtu;
    if (!(term === 0)) {
      throw new GasDoubleCountError(
        `this margin is ${MARGIN_NET_OF_GAS}, so it already contains the ` +
          `refinery's gas purchase, and it was handed ` +
          `${raw.gasIntensityMmbtuPerBbl} MMBtu per barrel at ${gas.gasUsdMmbtu} ` +
          '$/MMBtu. Subtracting that would charge the same barrel for gas twice. ' +
          'Put the gas price through gasWedge() instead, which compares the two ' +
          'intensities at one price without deducting either'
      );
    }
  }
  return {
    yields,
    cracks,
    products: yieldNames,
    gas,
    residualUsdBbl: raw.residualUsdBbl === undefined ? 0 : raw.residualUsdBbl,
    gasIntensityMmbtuPerBbl: raw.gasIntensityMmbtuPerBbl,
    otherVariableCostUsdBbl:
      raw.otherVariableCostUsdBbl === undefined ? 0 : raw.otherVariableCostUsdBbl,
    runCutThresholdUsdBbl:
      raw.runCutThresholdUsdBbl === undefined ? null : raw.runCutThresholdUsdBbl,
    marginBasis
  };
}

function carrierOf(contributions, products) {
  let bestName = null;
  let bestValue = NaN;
  products.forEach((name) => {
    const value = contributions[name];
    if (isMissing(value)) {
      return;
    }
    if (bestName === null || value > bestValue) {
      bestName = name;
      bestValue = value;
    }
  });
  return { carrier: bestName, carrierContributionUsdBbl: bestValue };
}

/** The margin, line by line. SPEC.md sections 4.3 layer 3, 4.4 and 4.5. */
export function evaluate(inputs) {
  const contributions = emptyMapping();
  inputs.products.forEach((name) => {
    contributions[name] = inputs.yields[name] * inputs.cracks[name];
  });
  let attributed = 0;
  inputs.products.forEach((name) => {
    attributed += contributions[name];
  });

  const gross = attributed + inputs.residualUsdBbl;
  // On a net of gas margin the gas cost line is zero, because the purchase is
  // already inside the margin that arrived. marginInputs refuses to hold a gas
  // price on that basis, so nothing is being skipped quietly here.
  const alreadyNet = inputs.marginBasis === MARGIN_NET_OF_GAS;
  const gasCost = alreadyNet
    ? 0
    : gasCostUsdBbl(inputs.gasIntensityMmbtuPerBbl, inputs.gas.gasUsdMmbtu);
  const afterGas = gross - gasCost - inputs.otherVariableCostUsdBbl;
  const { carrier, carrierContributionUsdBbl } = carrierOf(
    contributions,
    inputs.products
  );
  const threshold = inputs.runCutThresholdUsdBbl;
  const identified = threshold !== null && threshold !== undefined;

  return {
    contributions,
    attributedUsdBbl: attributed,
    residualUsdBbl: inputs.residualUsdBbl,
    grossMarginUsdBbl: gross,
    gasUsdMmbtu: inputs.gas.gasUsdMmbtu,
    gasCostUsdBbl: gasCost,
    otherVariableCostUsdBbl: inputs.otherVariableCostUsdBbl,
    marginAfterGasUsdBbl: afterGas,
    carrier,
    carrierContributionUsdBbl,
    runCutThresholdUsdBbl: identified ? threshold : null,
    thresholdIdentified: identified,
    headroomUsdBbl: identified ? afterGas - threshold : null,
    gasBasis: inputs.gas.basis,
    marginBasis: inputs.marginBasis,
    gasAlreadyInMargin: alreadyNet
  };
}

// ---------------------------------------------------------------------------
// SPEC.md section 4.3 layer 3, the decomposition
// ---------------------------------------------------------------------------

/** Attribute a published margin to products and put the rest on one line. */
export function decomposeOfficial(
  officialUsdBbl,
  yields,
  cracks,
  unattributedProducts = []
) {
  const inputs = marginInputs({
    yields,
    cracks,
    gas: gasFromUsdMmbtu(0),
    gasIntensityMmbtuPerBbl: 0
  });
  const contributions = emptyMapping();
  inputs.products.forEach((name) => {
    contributions[name] = inputs.yields[name] * inputs.cracks[name];
  });
  let attributed = 0;
  let covered = 0;
  inputs.products.forEach((name) => {
    attributed += contributions[name];
    covered += inputs.yields[name];
  });
  const residual = officialUsdBbl - attributed;
  const share = officialUsdBbl === 0 ? NaN : residual / officialUsdBbl;
  const { carrier, carrierContributionUsdBbl } = carrierOf(
    contributions,
    inputs.products
  );
  return {
    officialUsdBbl,
    contributions,
    attributedUsdBbl: attributed,
    residualUsdBbl: residual,
    residualShare: share,
    carrier,
    carrierContributionUsdBbl,
    unattributedProducts: unattributedProducts.slice().sort(),
    coveredVolumeYield: covered
  };
}

// ---------------------------------------------------------------------------
// SPEC.md section 4.3 layer 2, the replication attempt
// ---------------------------------------------------------------------------

/**
 * Recompute the MBR from DGEC's method with whatever is published.
 *
 * The mass yields, the sulphur price, the insurance rate, the Brent factor and
 * the list of unpublished inputs all arrive as arguments, because they are
 * DGEC's published method and therefore data, not unit constants. The Python
 * defaults them from crack.config; the fixture supplies the same values here.
 */
export function replicateMbr(options) {
  const {
    quotationsUsdT,
    brentUsdT,
    officialUsdBbl,
    massYields,
    bblPerTBrent,
    sulphurUsdT,
    insuranceAndLossRate,
    barUsdBbl,
    unpublishedInputs,
    reason
  } = options;
  const freightUsdT = options.freightUsdT === undefined ? NaN : options.freightUsdT;
  const gasCostUsdT = options.gasCostUsdT === undefined ? NaN : options.gasCostUsdT;

  const skipped = ['brent', 'gaz_naturel', 'combustible_interne_et_pertes'];
  const priced = emptyMapping();
  sortedKeys(massYields).forEach((name) => {
    if (skipped.includes(name)) {
      return;
    }
    if (name === 'soufre') {
      priced[name] = sulphurUsdT;
      return;
    }
    if (Object.prototype.hasOwnProperty.call(quotationsUsdT, name)) {
      priced[name] = quotationsUsdT[name];
    }
  });

  let revenue = 0;
  let covered = 0;
  sortedKeys(priced).forEach((name) => {
    revenue += massYields[name] * priced[name];
    covered += massYields[name];
  });

  const insuranceAndLoss = insuranceAndLossRate * (brentUsdT + freightUsdT);
  const costFull = brentUsdT + gasCostUsdT + freightUsdT + insuranceAndLoss;
  const marginUsdBbl = usdTToUsdBbl(revenue - costFull, bblPerTBrent);

  const costPartial = brentUsdT + insuranceAndLossRate * brentUsdT;
  const partialUsdBbl = usdTToUsdBbl(revenue - costPartial, bblPerTBrent);

  const error = marginUsdBbl - officialUsdBbl;
  const partialError = partialUsdBbl - officialUsdBbl;

  const missing = unpublishedInputs.filter(
    (name) =>
      Object.prototype.hasOwnProperty.call(massYields, name) &&
      !Object.prototype.hasOwnProperty.call(quotationsUsdT, name)
  );
  if (isMissing(freightUsdT)) {
    missing.push('aframax_freight_sullom_voe_le_havre');
  }
  if (isMissing(gasCostUsdT)) {
    missing.push('peg_nord_gas_day_ahead');
    missing.push('grtgaz_transport_tariff');
  }

  // A replication cannot pass while an input is missing, mirroring Python.
  // Gate 2 self audit, finding 12.
  const within =
    missing.length === 0 && !isMissing(error) && Math.abs(error) <= barUsdBbl;

  return {
    marginUsdBbl,
    partialUsdBbl,
    revenuePublishedUsdT: revenue,
    coveredMassYield: covered,
    missingInputs: missing,
    officialUsdBbl,
    errorUsdBbl: error,
    partialErrorUsdBbl: partialError,
    barUsdBbl,
    withinBar: within,
    reason
  };
}

// ---------------------------------------------------------------------------
// SPEC.md section 4.5, the outputs
// ---------------------------------------------------------------------------

function thresholdOrNull(inputs, threshold) {
  if (threshold !== null && threshold !== undefined) {
    return threshold;
  }
  return inputs.runCutThresholdUsdBbl === undefined
    ? null
    : inputs.runCutThresholdUsdBbl;
}

/** The gas price at which margin_after_gas equals the threshold. Closed form. */
export function breakevenGasUsdMmbtu(inputs, threshold = null) {
  const level = thresholdOrNull(inputs, threshold);
  if (level === null) {
    return null;
  }
  // A margin that already contains its own gas purchase does not move when the
  // gas price moves, so there is no gas price at which it reaches a threshold.
  if (inputs.marginBasis === MARGIN_NET_OF_GAS) {
    return null;
  }
  if (inputs.gasIntensityMmbtuPerBbl === 0) {
    return null;
  }
  const result = evaluate(inputs);
  return (
    (result.grossMarginUsdBbl - result.otherVariableCostUsdBbl - level) /
    inputs.gasIntensityMmbtuPerBbl
  );
}

/** The TTF price at which margin_after_gas equals the threshold. Closed form. */
export function breakevenTtf(inputs, threshold = null) {
  const level = thresholdOrNull(inputs, threshold);
  if (level === null) {
    return null;
  }
  if (inputs.marginBasis === MARGIN_NET_OF_GAS) {
    return null;
  }
  // undefined as well as null. Python returns None for a gas record with no
  // exchange rate and this returned NaN, because undefined === null is false.
  // Gate 2 self audit, finding 8 row 5.
  if (
    inputs.gas.basis !== GAS_BASIS_TTF ||
    inputs.gas.eurusd === null ||
    inputs.gas.eurusd === undefined
  ) {
    return null;
  }
  const denominator = inputs.gasIntensityMmbtuPerBbl * inputs.gas.eurusd;
  if (denominator === 0) {
    return null;
  }
  const result = evaluate(inputs);
  return (
    ((result.grossMarginUsdBbl - result.otherVariableCostUsdBbl - level) *
      MMBTU_PER_MWH) /
    denominator
  );
}

/** The crack of one product at which margin_after_gas equals the threshold. */
export function breakevenCrack(inputs, product, threshold = null) {
  if (!Object.prototype.hasOwnProperty.call(inputs.yields, product)) {
    throw new KeyError(
      `no product ${product} in this margin. Products: ${inputs.products.join(', ')}`
    );
  }
  const level = thresholdOrNull(inputs, threshold);
  if (level === null) {
    return null;
  }
  const ownYield = inputs.yields[product];
  if (ownYield === 0) {
    return null;
  }
  let rest = 0;
  inputs.products.forEach((name) => {
    if (name === product) {
      return;
    }
    rest += inputs.yields[name] * inputs.cracks[name];
  });
  const gasCost = gasCostUsdBbl(
    inputs.gasIntensityMmbtuPerBbl,
    inputs.gas.gasUsdMmbtu
  );
  return (
    (level + gasCost + inputs.otherVariableCostUsdBbl - inputs.residualUsdBbl - rest) /
    ownYield
  );
}

/**
 * Where a value sits inside a history, 0 to 100. SPEC.md section 4.5.
 *
 * The share of the history's published observations that are at or below the
 * value, times 100. null when the value is missing or the window holds nothing,
 * and never 50 by default.
 */
export function percentileRank(value, history) {
  if (isMissing(value)) {
    return null;
  }
  // Array.from rather than history.filter, so anything ITERABLE answers the way
  // Python's "for x in history" does instead of throwing: an empty mapping
  // ranks against nothing in both engines rather than returning null in one and
  // a TypeError in the other. Gate 2 self audit, section (c) row 7.
  //
  // And Array.from(history), not Array.from(history || []). null is not an
  // empty history: Python raises TypeError on it, because None is not iterable,
  // and a mirror that quietly answered null would be the more forgiving of the
  // two engines, which is the direction SPEC.md section 7.1 forbids.
  const published = Array.from(history).filter((x) => !isMissing(x));
  if (published.length === 0) {
    return null;
  }
  let atOrBelow = 0;
  published.forEach((x) => {
    if (x <= value) {
      atOrBelow += 1;
    }
  });
  return (100 * atOrBelow) / published.length;
}

/** Everything SPEC.md section 4.5 asks for, computed once. Values, no sentence. */
export function outputs(inputs, history = [], options = {}) {
  const gasoilKey = options.gasoilKey === undefined ? 'gasoil' : options.gasoilKey;
  const threshold = options.threshold === undefined ? null : options.threshold;
  // The window length is config.PERCENTILE_WINDOW_MONTHS in Python and data
  // rather than a unit constant here, so it arrives as an option and is carried
  // on the record. The mirror used to drop the field entirely, which is finding
  // 11 of the Gate 2 self audit.
  const percentileWindowMonths =
    options.percentileWindowMonths === undefined
      ? null
      : options.percentileWindowMonths;
  const level = thresholdOrNull(inputs, threshold);
  const withThreshold =
    threshold === null
      ? inputs
      : marginInputs({
          yields: inputs.yields,
          cracks: inputs.cracks,
          gas: inputs.gas,
          residualUsdBbl: inputs.residualUsdBbl,
          gasIntensityMmbtuPerBbl: inputs.gasIntensityMmbtuPerBbl,
          otherVariableCostUsdBbl: inputs.otherVariableCostUsdBbl,
          runCutThresholdUsdBbl: threshold,
          marginBasis: inputs.marginBasis
        });
  const result = evaluate(withThreshold);
  // Array.from(history), for the reason percentileRank gives: null is not an
  // empty history in Python and must not become one here.
  const published = Array.from(history).filter((x) => !isMissing(x));
  const gasoilBreakeven = Object.prototype.hasOwnProperty.call(
    inputs.yields,
    gasoilKey
  )
    ? breakevenCrack(inputs, gasoilKey, level)
    : null;

  return {
    margin: result,
    contributions: result.contributions,
    carrier: result.carrier,
    carrierContributionUsdBbl: result.carrierContributionUsdBbl,
    breakevenTtfEurMwh: breakevenTtf(inputs, level),
    breakevenGasUsdMmbtu: breakevenGasUsdMmbtu(inputs, level),
    breakevenGasoilUsdBbl: gasoilBreakeven,
    percentile10y: percentileRank(result.marginAfterGasUsdBbl, history),
    percentileWindowMonths,
    percentileObservations: published.length,
    headroomUsdBbl: result.headroomUsdBbl,
    thresholdIdentified: level !== null
  };
}
