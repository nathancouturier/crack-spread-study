#!/usr/bin/env node
// The python to javascript parity check SPEC.md section 7.1 asks for.
//
//     node tools/validate-engine.mjs
//     node tools/validate-engine.mjs path/to/engine-cases.json
//     node tools/validate-engine.mjs --verbose      print every case checked
//
// Plain node, no npm install, no dependencies. It reads what Python computed
// into data/fixtures/engine-cases.json, runs src/engine.js over the same inputs,
// and asserts agreement to 1e-9 on every line of every case: every product
// contribution, every subtotal, the gas chain, the margin after gas, the
// carrier, the residual, all three breakevens, the percentile and the two
// refusals. It exits 0 when they agree and 1 when they do not, so it can sit in
// the deploy gate beside the data validator.
//
// SPEC.md section 7.1: if they disagree, fix the JavaScript to match Python,
// never the reverse. That is why this tool never rounds, never coerces, and
// never treats an absent value as a zero.
//
// The one distinction it will not let slide
// -----------------------------------------
// NaN is a missing observation, SPEC.md section 2 rule 1. null is a question
// with no answer: no threshold was identified, or a breakeven has no leverage
// to exist on. A validator that compared them loosely would accept an engine
// that printed 0.0 for both, which is the failure mode this whole project is
// built to avoid. So null matches only null, NaN matches only NaN, and a number
// matches only a number.
//
// What is checked, in order:
//
//   1  the fixture parses, names itself, is not empty, and carries at least the
//      200 randomised cases SPEC.md section 7.1 asks for
//   2  the two engines agree about the vocabulary: units, windows, bases and
//      the three conversion constants
//   3  every crack case: the value, both legs in $/bbl, the basis, the date,
//      the window, the source's own product label and both factors, or the
//      exception class Python raised
//   4  every margin case: each contribution by name, the attributed total, the
//      residual, the gross margin, the gas price, the gas cost, the margin
//      after gas, the carrier and its value, the headroom, the threshold, the
//      margin basis, the three breakevens and the percentile with its window
//   5  every decomposition case, including the residual share and the covered
//      yield
//   6  every replication case, including the missing input list in order
//   7  every observed yield case on both bases and normalised, with the
//      denominator and the note the record carries
//   8  every percentile case
//
// And, since the Gate 2 self audit's findings 5 and 8, four kinds of case the
// fixture could not reach before. Every one of them was a measured divergence
// between the two engines, and two of them turned a missing value into a number
// in the browser:
//
//   9  quote cases: a price exactly as JSON carries it. null, an empty string,
//      a string of digits and a boolean are refused by both engines, because
//      Number(null) is 0 and a hole in an artifact must not become a price
//  10  raw crack cases: legs that never went through makeQuote, which is what a
//      Gate 4 module reading a JSON row actually holds. A leg with no window or
//      no date is refused, where before this engine cracked it and returned a
//      number
//  11  margin refusal cases: inputs both engines must refuse and with the same
//      exception class, including the gas cost on a margin that already
//      contains one, which is finding 1
//  12  gas wedge cases: the two intensities at one gas price that replaced that
//      subtraction, which neither the fixture nor this tool had ever compared
//
// On a disagreement it prints the case, the field, both values and the
// difference. A validator that says only "mismatch" costs an afternoon.
//
// Why bit exactness is NOT the bar, and what is printed instead
// -------------------------------------------------------------
// SPEC.md section 7.1 sets the bar at 1e-9 and that is the bar here. It is a
// hard assertion: one field past 1e-9 and this exits 1.
//
// An earlier version of this file also FAILED when any comparison was merely
// inside the tolerance rather than identical to the last bit. That check could
// only ever be red, for two reasons, and a permanently red gate teaches
// everybody to stop reading it.
//
//   The first reason is that IEEE 754 double arithmetic is not associative and
//   neither language promises an evaluation order for a sum written as a
//   sequence of additions. Both engines add over sorted keys, left to right, on
//   purpose, so they do agree today, but nothing in either language
//   specification obliges them to keep agreeing in the last bit. Demanding
//   bit equality is demanding a guarantee that does not exist.
//
//   The second reason is the one that was actually firing. The failure was at
//   "attributed plus residual" in a decomposition, and that comparison is not a
//   parity comparison at all. The residual is defined as official minus
//   attributed, so adding it back asks whether a + (b - a) == b in floating
//   point, and it does not, in ANY language. Python reproduces the same
//   3.331e-15 on the same numbers. It was measuring the arithmetic, not the
//   mirror.
//
// So the two are now measured on separate channels and neither is inflated by
// the other:
//
//   parity    a number Python recorded against the number engine.js produced
//             for the same field of the same case. This is drift between the
//             two engines and it is the thing SPEC.md section 7.1 is about.
//             It is reported on every run, with the largest value and where it
//             occurred, so that real drift is visible long before it reaches
//             1e-9. Today it is zero.
//
//   identity  an algebraic identity checked inside engine.js alone, such as
//             attributed plus residual returning the official margin, or a
//             breakeven plugged back in returning the threshold. Floating point
//             does not preserve these exactly and a single language cannot
//             either, so a small residue here is arithmetic and not drift.
//
// Both channels are still held to 1e-9 and both still fail the gate past it.
// What changed is that neither is asserted to be zero, and both are printed
// every run as a measurement. A number that has to be looked at beats a check
// that can only be ignored.

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import * as engine from "../src/engine.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");

const argv = process.argv.slice(2);
const VERBOSE = argv.includes("--verbose");
const positional = argv.filter((arg) => !arg.startsWith("--"));
const FIXTURE = positional.length
  ? path.resolve(positional[0])
  : path.join(ROOT, "data", "fixtures", "engine-cases.json");

const checks = [];
const failures = [];

// The two measurement channels described in the header. PARITY is python
// against javascript on the same field. IDENTITY is an algebraic identity
// checked inside engine.js alone, which floating point does not preserve in any
// language and which therefore measures arithmetic rather than drift.
const PARITY = "parity";
const IDENTITY = "identity";

const measured = {
  [PARITY]: { comparisons: 0, exact: 0, worst: 0, where: "" },
  [IDENTITY]: { comparisons: 0, exact: 0, worst: 0, where: "" }
};

let TOLERANCE = 1e-9;

function check(name, fn) {
  let problems;
  try {
    problems = fn() || [];
  } catch (err) {
    problems = ["threw: " + (err && err.message ? err.message : String(err))];
  }
  checks.push({ name, problems });
}

/* --------------------------------------------------------------- decoding --- */

// The fixture writes a missing number as the string "NaN" because JSON has no
// NaN token. null stays null and means something different.
function decodeNumber(value) {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === "string") {
    if (value === "NaN") return NaN;
    if (value === "Infinity") return Infinity;
    if (value === "-Infinity") return -Infinity;
    throw new Error("cannot decode number from string " + value);
  }
  return value;
}

function decodeMapping(mapping) {
  const out = {};
  Object.keys(mapping).forEach((key) => {
    out[key] = decodeNumber(mapping[key]);
  });
  return out;
}

function decodeList(list) {
  return list.map((item) => decodeNumber(item));
}

function show(value) {
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  if (typeof value === "number") {
    if (Number.isNaN(value)) return "NaN";
    return String(value);
  }
  if (Array.isArray(value)) return "[" + value.map(show).join(", ") + "]";
  return String(value);
}

/* ------------------------------------------------------------ comparison --- */

function compare(where, field, expected, actual, channel = PARITY) {
  const track = measured[channel];
  track.comparisons += 1;
  const wanted = typeof expected === "string" && ["NaN", "Infinity", "-Infinity"].includes(expected)
    ? decodeNumber(expected)
    : expected;

  if (wanted === null || wanted === undefined) {
    if (actual === null || actual === undefined) {
      track.exact += 1;
      return;
    }
    failures.push({
      where,
      what: field,
      expected: "null, the question has no answer",
      actual: show(actual),
      difference: "a number where there should be none"
    });
    return;
  }

  if (typeof wanted === "boolean" || typeof wanted === "string") {
    if (wanted === actual) {
      track.exact += 1;
      return;
    }
    failures.push({
      where,
      what: field,
      expected: show(wanted),
      actual: show(actual),
      difference: "not equal"
    });
    return;
  }

  if (typeof actual !== "number") {
    failures.push({
      where,
      what: field,
      expected: show(wanted),
      actual: show(actual),
      difference: "javascript did not produce a number"
    });
    return;
  }

  if (Number.isNaN(wanted)) {
    if (Number.isNaN(actual)) {
      track.exact += 1;
      return;
    }
    failures.push({
      where,
      what: field,
      expected: "NaN, the observation is missing",
      actual: show(actual),
      difference: "a number where the data is missing"
    });
    return;
  }
  if (Number.isNaN(actual)) {
    failures.push({
      where,
      what: field,
      expected: show(wanted),
      actual: "NaN",
      difference: "javascript lost the value"
    });
    return;
  }

  const difference = Math.abs(wanted - actual);
  if (difference === 0) {
    track.exact += 1;
  }
  if (difference > track.worst) {
    track.worst = difference;
    track.where = where + " " + field;
  }
  if (difference > TOLERANCE) {
    failures.push({
      where,
      what: field,
      channel,
      expected: String(wanted),
      actual: String(actual),
      difference: difference.toExponential(3)
    });
  }
}

function compareMapping(where, field, expected, actual) {
  const wantedKeys = Object.keys(expected).sort();
  const gotKeys = Object.keys(actual).sort();
  if (wantedKeys.join("|") !== gotKeys.join("|")) {
    failures.push({
      where,
      what: field + " keys",
      expected: wantedKeys.join(",") || "(none)",
      actual: gotKeys.join(",") || "(none)",
      difference: "different products"
    });
    return;
  }
  wantedKeys.forEach((key) => {
    compare(where, field + "." + key, expected[key], actual[key]);
  });
}

/* ---------------------------------------------------------------- fixture --- */

let fixture = null;

check("the fixture parses and names itself", () => {
  const problems = [];
  const text = readFileSync(FIXTURE, "utf8");
  fixture = JSON.parse(text);
  if (fixture.schema_version !== 2) {
    problems.push("schema_version is " + fixture.schema_version + ", this tool reads 2");
  }
  if (!Array.isArray(fixture.cases) || fixture.cases.length === 0) {
    problems.push("no cases in the fixture");
  }
  if (typeof fixture.tolerance !== "number") {
    problems.push("the fixture carries no tolerance");
  } else {
    TOLERANCE = fixture.tolerance;
  }
  if (fixture.mirror !== "src/engine.js") {
    problems.push("the fixture names " + fixture.mirror + " as the mirror");
  }
  if ((fixture.counts && fixture.counts.randomised) < 200) {
    problems.push(
      "SPEC.md section 7.1 asks for at least 200 randomised input sets, the " +
        "fixture has " + (fixture.counts && fixture.counts.randomised)
    );
  }
  return problems;
});

check("the two engines agree about the vocabulary and the unit constants", () => {
  const problems = [];
  if (engine.BBL_PER_T_GASOIL !== 7.45) {
    problems.push("BBL_PER_T_GASOIL is " + engine.BBL_PER_T_GASOIL + ", not 7.45");
  }
  if (engine.BBL_PER_T_GASOLINE !== 8.33) {
    problems.push("BBL_PER_T_GASOLINE is " + engine.BBL_PER_T_GASOLINE + ", not 8.33");
  }
  if (engine.MMBTU_PER_MWH !== 3.412142) {
    problems.push("MMBTU_PER_MWH is " + engine.MMBTU_PER_MWH + ", not 3.412142");
  }
  // The Units row of SPEC.md section 9, asserted here as well as in Python,
  // because this is the copy of the engine the browser runs.
  if (engine.crackFromUsdT(745, engine.BBL_PER_T_GASOIL, 80) !== 20) {
    problems.push("745 $/t of gasoil against Brent 80 is not exactly 20 in engine.js");
  }
  if (engine.crackFromUsdT(833, engine.BBL_PER_T_GASOLINE, 80) !== 20) {
    problems.push("833 $/t of gasoline against Brent 80 is not exactly 20 in engine.js");
  }
  const vocabulary = [
    ["USD_PER_BBL", "usd_per_bbl"],
    ["USD_PER_T", "usd_per_t"],
    ["MONTHLY", "monthly"],
    ["WEEKLY", "weekly"],
    ["DAILY", "daily"],
    ["BASIS_DIRECT", "usd_per_bbl_direct"],
    ["BASIS_CONVERTED", "usd_per_t_converted"],
    ["GAS_BASIS_TTF", "ttf_eur_mwh"],
    ["GAS_BASIS_PUBLISHED", "published_usd_mmbtu"],
    ["YIELD_BASIS_CRUDE_INTAKE", "crude_intake"],
    ["YIELD_BASIS_TOTAL_FEED", "total_feed"],
    ["YIELD_BASIS_NORMALISED", "normalised_share"]
  ];
  vocabulary.forEach(([name, value]) => {
    if (engine[name] !== value) {
      problems.push(name + " is " + engine[name] + ", python says " + value);
    }
  });
  return problems;
});

/* ------------------------------------------------------------ the runners --- */

function buildQuote(payload) {
  return engine.makeQuote(
    decodeNumber(payload.value),
    payload.unit,
    payload.date,
    payload.window,
    payload.label
  );
}

// A gas record from the fixture, or nothing at all.
//
// null in the payload means the case passed NO gas record, which Python
// defaults to gas_from_usd_mmbtu(0.0) and which used to be a TypeError here.
// Gate 2 self audit, finding 8 row 4. It is not a gas price of zero: the case
// that means zero carries a record whose price is 0.
//
// A TTF record with no exchange rate is built literally rather than through
// gasFromTtf, because there is no rate to multiply by. Python holds exactly
// that record, GasCost(basis=ttf, eurusd=None), and answers None for the TTF
// breakeven; the mirror used to answer NaN. Finding 8 row 5.
// eurusdAbsent asks for the record to carry no eurusd KEY at all rather than an
// eurusd of null. Python has one word for both and JavaScript has two, and
// undefined === null is false, so a guard written against one of them passes
// while the other is live. The fixture carries both spellings.
function buildGas(gas, eurusdAbsent) {
  if (gas === null || gas === undefined) {
    return undefined;
  }
  if (gas.basis === engine.GAS_BASIS_TTF) {
    const eurusd = decodeNumber(gas.eurusd);
    if (eurusd === null) {
      const record = {
        gasUsdMmbtu: decodeNumber(gas.gas_usd_mmbtu),
        basis: engine.GAS_BASIS_TTF,
        ttfEurMwh: decodeNumber(gas.ttf_eur_mwh)
      };
      if (!eurusdAbsent) {
        record.eurusd = null;
      }
      return record;
    }
    return engine.gasFromTtf(decodeNumber(gas.ttf_eur_mwh), eurusd);
  }
  return engine.gasFromUsdMmbtu(decodeNumber(gas.gas_usd_mmbtu));
}

function buildInputs(payload, eurusdAbsent = false) {
  const raw = {
    yields: decodeMapping(payload.yields),
    cracks: decodeMapping(payload.cracks),
    residualUsdBbl: decodeNumber(payload.residual_usd_bbl),
    gasIntensityMmbtuPerBbl: decodeNumber(payload.gas_intensity_mmbtu_per_bbl),
    otherVariableCostUsdBbl: decodeNumber(payload.other_variable_cost_usd_bbl),
    runCutThresholdUsdBbl: decodeNumber(payload.run_cut_threshold_usd_bbl),
    marginBasis: payload.margin_basis
  };
  const gas = buildGas(payload.gas, eurusdAbsent);
  if (gas !== undefined) {
    raw.gas = gas;
  }
  return engine.marginInputs(raw);
}

function runCrackCase(testCase) {
  const where = "crack " + testCase.name;
  const expected = testCase.expected;
  let result = null;
  let thrown = null;
  try {
    result = engine.crack(buildQuote(testCase.product), buildQuote(testCase.brent), {
      productBblPerT: decodeNumber(testCase.product_bbl_per_t),
      brentBblPerT: decodeNumber(testCase.brent_bbl_per_t)
    });
  } catch (err) {
    thrown = err;
  }

  if (expected.error) {
    if (!thrown) {
      failures.push({
        where,
        what: "refusal",
        expected: "python raised " + expected.error,
        actual: "engine.js returned " + show(result && result.value),
        difference: "the javascript accepted an input python refuses"
      });
      return;
    }
    compare(where, "error class", expected.error, thrown.name);
    return;
  }
  if (thrown) {
    failures.push({
      where,
      what: "refusal",
      expected: "a value",
      actual: "engine.js threw " + thrown.name + ": " + thrown.message,
      difference: "the javascript refused an input python accepts"
    });
    return;
  }
  compare(where, "value", expected.value, result.value);
  compare(where, "product_usd_bbl", expected.product_usd_bbl, result.productUsdBbl);
  compare(where, "brent_usd_bbl", expected.brent_usd_bbl, result.brentUsdBbl);
  compare(where, "product_basis", expected.product_basis, result.productBasis);
  compare(where, "date", expected.date, result.date);
  compare(where, "window", expected.window, result.window);
  // The label and the factors. SPEC.md section 4.2 keeps the source's own name
  // for a product, and a mirror that dropped it would have passed until now.
  compare(where, "product_label", expected.product_label, result.productLabel);
  compare(where, "product_bbl_per_t", expected.product_bbl_per_t, result.productBblPerT);
  compare(where, "brent_bbl_per_t", expected.brent_bbl_per_t, result.brentBblPerT);
}

// A quote built from a value exactly as JSON carries it. Gate 2 self audit,
// finding 8 rows 1 to 3: makeQuote used to run Number(value), and Number(null)
// and Number("") are both 0, so a JSON artifact with a hole in it produced a
// price of 0 $/bbl in the browser and a refusal in the pipeline.
//
// value_json is passed through with NO decoding at all. That is the whole
// point: the case is about what JSON.parse hands the engine.
function runQuoteCase(testCase) {
  const where = "quote " + testCase.name;
  const expected = testCase.expected;
  let result = null;
  let thrown = null;
  try {
    result = engine.makeQuote(
      testCase.value_json,
      testCase.unit,
      testCase.date,
      testCase.window,
      testCase.label
    );
  } catch (err) {
    thrown = err;
  }
  if (expected.error) {
    if (!thrown) {
      failures.push({
        where,
        what: "refusal",
        expected: "python raised " + expected.error,
        actual: "engine.js returned a quote of " + show(result && result.value),
        difference: "the javascript accepted a value python refuses"
      });
      return;
    }
    compare(where, "error class", expected.error, thrown.name);
    return;
  }
  if (thrown) {
    failures.push({
      where,
      what: "refusal",
      expected: "a quote",
      actual: "engine.js threw " + thrown.name + ": " + thrown.message,
      difference: "the javascript refused a value python accepts"
    });
    return;
  }
  compare(where, "value", expected.value, result.value);
  compare(where, "unit", expected.unit, result.unit);
  compare(where, "date", expected.date, result.date);
  compare(where, "window", expected.window, result.window);
  compare(where, "label", expected.label, result.label);
}

// crack() on legs that never went through makeQuote. Gate 2 self audit, finding
// 5: this engine accepted two bare objects with no window and no date and
// returned a number, because undefined !== undefined is false. SPEC.md section
// 4.2's alignment rule is the one the Gate 2 brief asked to be structural, and
// it cannot be structural in Python and duck typed in the browser.
//
// The legs are built as plain objects carrying only the fields the case names,
// which is what a row read out of a JSON artifact looks like.
function buildBareLeg(payload) {
  const leg = {};
  Object.keys(payload).forEach((key) => {
    // Only the price is a number. The date, the window, the unit and the label
    // are strings and go through untouched, so a leg that carries a date really
    // carries the date and not a decoding of it.
    leg[key] = key === "value" ? decodeNumber(payload[key]) : payload[key];
  });
  return leg;
}

function runRawCrackCase(testCase) {
  const where = "raw crack " + testCase.name;
  const expected = testCase.expected;
  let result = null;
  let thrown = null;
  try {
    result = engine.crack(
      buildBareLeg(testCase.product),
      buildBareLeg(testCase.brent),
      {
        productBblPerT: decodeNumber(testCase.product_bbl_per_t),
        brentBblPerT: decodeNumber(testCase.brent_bbl_per_t)
      }
    );
  } catch (err) {
    thrown = err;
  }
  if (expected.error) {
    if (!thrown) {
      failures.push({
        where,
        what: "refusal",
        expected: "python raised " + expected.error,
        actual:
          "engine.js returned " +
          show(result && result.value) +
          " with window " +
          show(result && result.window) +
          " and date " +
          show(result && result.date),
        difference: "the javascript cracked legs python refuses to crack"
      });
      return;
    }
    compare(where, "error class", expected.error, thrown.name);
    return;
  }
  if (thrown) {
    failures.push({
      where,
      what: "refusal",
      expected: "a crack",
      actual: "engine.js threw " + thrown.name + ": " + thrown.message,
      difference: "the javascript refused legs python accepts"
    });
    return;
  }
  compare(where, "value", expected.value, result.value);
  compare(where, "date", expected.date, result.date);
  compare(where, "window", expected.window, result.window);
}

// A set of margin inputs both engines have to refuse, and with the same class.
// One of these is the gas double count of finding 1, which is now a refusal in
// both engines rather than a wrong number in one of them.
function runMarginRefusalCase(testCase) {
  const where = "margin refusal " + testCase.name;
  let thrown = null;
  let result = null;
  try {
    result = buildInputs(testCase.inputs);
  } catch (err) {
    thrown = err;
  }
  if (!thrown) {
    failures.push({
      where,
      what: "refusal",
      expected: "python raised " + testCase.expected.error,
      actual: "engine.js built a margin with products " + show(result.products),
      difference: "the javascript accepted inputs python refuses"
    });
    return;
  }
  compare(where, "error class", testCase.expected.error, thrown.name);
}

// Two gas intensities at one gas price. The gas story on a margin that is
// already net of gas, and the thing that replaced the subtraction finding 1
// found, so a browser that got it wrong would be wrong about the correction
// itself.
function runGasWedgeCase(testCase) {
  const where = "gas wedge " + testCase.name;
  const expected = testCase.expected;
  const result = engine.gasWedge(
    decodeNumber(testCase.gas_usd_mmbtu),
    decodeNumber(testCase.embedded_intensity_mmbtu_per_bbl),
    decodeNumber(testCase.study_intensity_mmbtu_per_bbl)
  );
  compare(where, "gas_usd_mmbtu", expected.gas_usd_mmbtu, result.gasUsdMmbtu);
  compare(
    where,
    "embedded_intensity_mmbtu_per_bbl",
    expected.embedded_intensity_mmbtu_per_bbl,
    result.embeddedIntensityMmbtuPerBbl
  );
  compare(
    where,
    "study_intensity_mmbtu_per_bbl",
    expected.study_intensity_mmbtu_per_bbl,
    result.studyIntensityMmbtuPerBbl
  );
  compare(
    where,
    "embedded_cost_usd_bbl",
    expected.embedded_cost_usd_bbl,
    result.embeddedCostUsdBbl
  );
  compare(where, "study_cost_usd_bbl", expected.study_cost_usd_bbl, result.studyCostUsdBbl);
  compare(where, "wedge_usd_bbl", expected.wedge_usd_bbl, result.wedgeUsdBbl);
  compare(where, "ratio", expected.ratio, result.ratio);
  // The wedge is a difference and nothing else. IDENTITY, because it is
  // engine.js checked against itself.
  if (!Number.isNaN(result.wedgeUsdBbl)) {
    compare(
      where,
      "study minus embedded",
      result.studyCostUsdBbl - result.embeddedCostUsdBbl,
      result.wedgeUsdBbl,
      IDENTITY
    );
  }
}

function runMarginCase(testCase) {
  const where = "margin " + testCase.name;
  const expected = testCase.expected;
  const inputs = buildInputs(testCase.inputs, testCase.gas_eurusd_absent === true);
  const history = decodeList(testCase.history);
  const result = engine.evaluate(inputs);
  const bundle = engine.outputs(inputs, history, {
    gasoilKey: testCase.gasoil_key,
    threshold: decodeNumber(testCase.threshold),
    percentileWindowMonths: testCase.percentile_window_months
  });

  compareMapping(where, "contributions", expected.contributions, result.contributions);
  compare(where, "attributed_usd_bbl", expected.attributed_usd_bbl, result.attributedUsdBbl);
  compare(where, "residual_usd_bbl", expected.residual_usd_bbl, result.residualUsdBbl);
  compare(where, "gross_margin_usd_bbl", expected.gross_margin_usd_bbl, result.grossMarginUsdBbl);
  compare(where, "gas_usd_mmbtu", expected.gas_usd_mmbtu, result.gasUsdMmbtu);
  compare(where, "gas_cost_usd_bbl", expected.gas_cost_usd_bbl, result.gasCostUsdBbl);
  compare(
    where,
    "other_variable_cost_usd_bbl",
    expected.other_variable_cost_usd_bbl,
    result.otherVariableCostUsdBbl
  );
  compare(
    where,
    "margin_after_gas_usd_bbl",
    expected.margin_after_gas_usd_bbl,
    result.marginAfterGasUsdBbl
  );
  compare(where, "carrier", expected.carrier, result.carrier);
  compare(
    where,
    "carrier_contribution_usd_bbl",
    expected.carrier_contribution_usd_bbl,
    result.carrierContributionUsdBbl
  );
  compare(where, "threshold_identified", expected.threshold_identified, result.thresholdIdentified);
  compare(where, "headroom_usd_bbl", expected.headroom_usd_bbl, result.headroomUsdBbl);
  // The threshold the result carries, which the validator never compared: a
  // mirror that returned the wrong one would still have matched the headroom,
  // because the headroom was computed from it.
  compare(
    where,
    "run_cut_threshold_usd_bbl",
    expected.run_cut_threshold_usd_bbl,
    result.runCutThresholdUsdBbl
  );
  compare(where, "gas_basis", expected.gas_basis, result.gasBasis);
  // Which side of the gas purchase this margin sits on, and whether the engine
  // agrees that the gas is already inside it. Finding 1, mirrored.
  compare(where, "margin_basis", expected.margin_basis, result.marginBasis);
  compare(
    where,
    "gas_already_in_margin",
    expected.gas_already_in_margin,
    result.gasAlreadyInMargin
  );

  compare(where, "breakeven_ttf_eur_mwh", expected.breakeven_ttf_eur_mwh, bundle.breakevenTtfEurMwh);
  compare(
    where,
    "breakeven_gas_usd_mmbtu",
    expected.breakeven_gas_usd_mmbtu,
    bundle.breakevenGasUsdMmbtu
  );
  compare(
    where,
    "breakeven_gasoil_usd_bbl",
    expected.breakeven_gasoil_usd_bbl,
    bundle.breakevenGasoilUsdBbl
  );
  compare(where, "percentile_10y", expected.percentile_10y, bundle.percentile10y);
  compare(
    where,
    "percentile_observations",
    expected.percentile_observations,
    bundle.percentileObservations
  );
  // The window the rank was taken over, which Python carries on the record and
  // the mirror used to drop entirely. Gate 2 self audit, finding 11.
  compare(
    where,
    "percentile_window_months",
    expected.percentile_window_months,
    bundle.percentileWindowMonths
  );
  compare(where, "outputs.headroom_usd_bbl", expected.outputs_headroom_usd_bbl, bundle.headroomUsdBbl);
  compare(
    where,
    "outputs.threshold_identified",
    expected.outputs_threshold_identified,
    bundle.thresholdIdentified
  );

  // The round trip of SPEC.md section 9, run in the browser's engine rather
  // than only in Python: plug the breakeven back in and the margin after gas
  // has to be the threshold. IDENTITY channel: it is engine.js inverting its own
  // arithmetic, so the residue it leaves is rounding rather than drift.
  if (bundle.breakevenTtfEurMwh !== null && inputs.gas.basis === engine.GAS_BASIS_TTF) {
    const threshold =
      decodeNumber(testCase.threshold) === null
        ? inputs.runCutThresholdUsdBbl
        : decodeNumber(testCase.threshold);
    const replugged = engine.marginInputs({
      yields: inputs.yields,
      cracks: inputs.cracks,
      gas: engine.gasFromTtf(bundle.breakevenTtfEurMwh, inputs.gas.eurusd),
      residualUsdBbl: inputs.residualUsdBbl,
      gasIntensityMmbtuPerBbl: inputs.gasIntensityMmbtuPerBbl,
      otherVariableCostUsdBbl: inputs.otherVariableCostUsdBbl,
      runCutThresholdUsdBbl: threshold
    });
    const back = engine.evaluate(replugged).marginAfterGasUsdBbl;
    if (!Number.isNaN(back)) {
      compare(where, "breakeven_ttf round trip", threshold, back, IDENTITY);
    }
  }
}

function runDecompositionCase(testCase) {
  const where = "decomposition " + testCase.name;
  const expected = testCase.expected;
  const result = engine.decomposeOfficial(
    decodeNumber(testCase.official_usd_bbl),
    decodeMapping(testCase.yields),
    decodeMapping(testCase.cracks),
    testCase.unattributed_products
  );
  compareMapping(where, "contributions", expected.contributions, result.contributions);
  compare(where, "attributed_usd_bbl", expected.attributed_usd_bbl, result.attributedUsdBbl);
  compare(where, "residual_usd_bbl", expected.residual_usd_bbl, result.residualUsdBbl);
  compare(where, "residual_share", expected.residual_share, result.residualShare);
  compare(where, "carrier", expected.carrier, result.carrier);
  compare(
    where,
    "carrier_contribution_usd_bbl",
    expected.carrier_contribution_usd_bbl,
    result.carrierContributionUsdBbl
  );
  compare(
    where,
    "covered_volume_yield",
    expected.covered_volume_yield,
    result.coveredVolumeYield
  );
  compare(
    where,
    "unattributed_products",
    expected.unattributed_products.join(","),
    result.unattributedProducts.join(",")
  );
  // The invariant SPEC.md section 4.3 layer 3 is really about: the residual
  // plus the attributed lines are the official margin, in the browser too.
  //
  // IDENTITY channel, not parity. The residual is official minus attributed, so
  // this asks whether a + (b - a) == b in doubles, and it does not: Python
  // returns the same 3.331e-15 on the same three numbers. Held to 1e-9 like
  // everything else, reported separately, and never asserted to be zero.
  const rebuilt = result.attributedUsdBbl + result.residualUsdBbl;
  if (!Number.isNaN(rebuilt)) {
    compare(
      where,
      "attributed plus residual",
      decodeNumber(testCase.official_usd_bbl),
      rebuilt,
      IDENTITY
    );
  }
}

function runReplicationCase(testCase) {
  const where = "replication " + testCase.name;
  const expected = testCase.expected;
  const method = testCase.method;
  const result = engine.replicateMbr({
    quotationsUsdT: decodeMapping(testCase.quotations_usd_t),
    brentUsdT: decodeNumber(testCase.brent_usd_t),
    officialUsdBbl: decodeNumber(testCase.official_usd_bbl),
    freightUsdT: decodeNumber(testCase.freight_usd_t),
    gasCostUsdT: decodeNumber(testCase.gas_cost_usd_t),
    massYields: decodeMapping(method.mass_yields),
    bblPerTBrent: method.bbl_per_t_brent,
    sulphurUsdT: method.sulphur_usd_t,
    insuranceAndLossRate: method.insurance_and_loss_rate,
    barUsdBbl: method.bar_usd_bbl,
    unpublishedInputs: method.unpublished_inputs,
    reason: "carried in the fixture"
  });
  compare(where, "margin_usd_bbl", expected.margin_usd_bbl, result.marginUsdBbl);
  compare(where, "partial_usd_bbl", expected.partial_usd_bbl, result.partialUsdBbl);
  compare(
    where,
    "revenue_published_usd_t",
    expected.revenue_published_usd_t,
    result.revenuePublishedUsdT
  );
  compare(where, "covered_mass_yield", expected.covered_mass_yield, result.coveredMassYield);
  compare(where, "error_usd_bbl", expected.error_usd_bbl, result.errorUsdBbl);
  compare(
    where,
    "partial_error_usd_bbl",
    expected.partial_error_usd_bbl,
    result.partialErrorUsdBbl
  );
  compare(where, "within_bar", expected.within_bar, result.withinBar);
  compare(
    where,
    "missing_inputs",
    expected.missing_inputs.join(","),
    result.missingInputs.join(",")
  );
}

function runYieldsCase(testCase) {
  const where = "yields " + testCase.name;
  const expected = testCase.expected;
  let result = engine.observedYields(
    decodeMapping(testCase.output_kbd),
    decodeNumber(testCase.denominator_kbd),
    testCase.basis,
    testCase.notes
  );
  if (testCase.normalise) {
    result = engine.normaliseYields(result, testCase.notes);
  }
  compareMapping(where, "yields", expected.yields, result.yields);
  compare(where, "total", expected.total, result.total);
  compare(where, "basis", expected.basis, result.basis);
  // The denominator and the note. Python's record carries the note "so a JSON
  // artifact cannot lose it" and the mirror lost it while this validator
  // compared neither field. Gate 2 self audit, finding 11.
  compare(where, "denominator_kbd", expected.denominator_kbd, result.denominatorKbd);
  compare(where, "note", expected.note, result.note);
}

function runPercentileCase(testCase) {
  const where = "percentile " + testCase.name;
  // history_shape "mapping" passes an empty object rather than an array, which
  // is what a caller with no history at all reaches for. Python iterates it and
  // answers null; this engine threw a TypeError until the Gate 2 self audit,
  // section (c) row 7.
  //
  // "null" passes nothing, and both engines must REFUSE it. null is not an
  // empty history, and an engine that answered "no percentile" here would be
  // more forgiving than Python, which SPEC.md section 7.1 forbids.
  const shapes = { mapping: {}, null: null };
  const history = Object.prototype.hasOwnProperty.call(
    shapes,
    testCase.history_shape
  )
    ? shapes[testCase.history_shape]
    : decodeList(testCase.history);

  let result = null;
  let thrown = null;
  try {
    result = engine.percentileRank(decodeNumber(testCase.value), history);
  } catch (err) {
    thrown = err;
  }
  if (testCase.expected.error) {
    if (!thrown) {
      failures.push({
        where,
        what: "refusal",
        expected: "python raised " + testCase.expected.error,
        actual: "engine.js returned " + show(result),
        difference: "the javascript ranked against a history python refuses"
      });
      return;
    }
    compare(where, "error class", testCase.expected.error, thrown.name);
    return;
  }
  if (thrown) {
    failures.push({
      where,
      what: "refusal",
      expected: "a percentile",
      actual: "engine.js threw " + thrown.name + ": " + thrown.message,
      difference: "the javascript refused a history python accepts"
    });
    return;
  }
  compare(where, "percentile", testCase.expected.percentile, result);
}

const RUNNERS = {
  crack: runCrackCase,
  quote: runQuoteCase,
  raw_crack: runRawCrackCase,
  margin: runMarginCase,
  margin_refusal: runMarginRefusalCase,
  gas_wedge: runGasWedgeCase,
  decomposition: runDecompositionCase,
  replication: runReplicationCase,
  yields: runYieldsCase,
  percentile: runPercentileCase
};

check("every case agrees, line by line", () => {
  const problems = [];
  const seen = {};
  fixture.cases.forEach((testCase) => {
    const runner = RUNNERS[testCase.kind];
    if (!runner) {
      problems.push("no runner for case kind " + testCase.kind);
      return;
    }
    seen[testCase.kind] = (seen[testCase.kind] || 0) + 1;
    const before = failures.length;
    runner(testCase);
    if (VERBOSE) {
      const mark = failures.length === before ? "ok  " : "FAIL";
      console.log("    " + mark + " " + testCase.kind + " " + testCase.name);
    }
  });
  Object.keys(RUNNERS).forEach((kind) => {
    if (!seen[kind]) {
      problems.push("the fixture contains no " + kind + " case");
    }
  });
  return problems;
});

/* ------------------------------------------------------- the measurement --- */

// Printed on every run, pass or fail. This is the drift monitor that replaced
// the old bit exactness check, and it is deliberately not a check: it asserts
// nothing on its own and it cannot turn the gate red by itself. Its job is to
// put a number on screen that somebody can watch move.
//
// What to do with it. The parity line should read zero. It reads zero today
// because both engines sum over sorted keys left to right and do the same
// divisions in the same order. If it stops reading zero, something in one
// engine was reordered or rewritten, and that is worth understanding even at
// 1e-16, long before it reaches the 1e-9 that fails the gate. The identity line
// will never read zero and is not supposed to: it is the rounding left by
// engine.js inverting its own arithmetic. Watch it for a sudden jump in order
// of magnitude rather than for a zero.
function measurementReport() {
  const lines = [];
  const describe = (channel, what) => {
    const track = measured[channel];
    if (track.comparisons === 0) {
      lines.push("  " + channel.padEnd(9) + " no comparison made. " + what);
      return;
    }
    const inexact = track.comparisons - track.exact;
    lines.push(
      "  " + channel.padEnd(9) +
        "largest " + track.worst.toExponential(3) +
        (track.where ? " at " + track.where : "") +
        ", " + inexact + " of " + track.comparisons + " comparisons inexact"
    );
    lines.push("            " + what);
  };
  describe(PARITY, "python against javascript on the same field. Expect zero.");
  describe(
    IDENTITY,
    "javascript inverting its own arithmetic. A residue here is rounding, " +
      "not drift, and a single language shows the same one."
  );
  lines.push("  bar       " + TOLERANCE + ", SPEC.md section 7.1, hard on both channels");
  return lines;
}

/* ------------------------------------------------------------------ report --- */

function report() {
  const passed = checks.filter((entry) => entry.problems.length === 0).length;
  console.log("python to javascript parity, SPEC.md section 7.1");
  console.log("  fixture     " + path.relative(ROOT, FIXTURE).split(path.sep).join("/"));
  if (fixture && fixture.cases) {
    console.log("  cases       " + fixture.cases.length);
    console.log("  seed        " + fixture.seed);
  }
  const comparisons = measured[PARITY].comparisons + measured[IDENTITY].comparisons;
  const exactComparisons = measured[PARITY].exact + measured[IDENTITY].exact;
  console.log("  comparisons " + comparisons);
  console.log("  exact       " + exactComparisons);
  console.log("  tolerance   " + TOLERANCE);
  console.log("");
  for (const entry of checks) {
    const mark = entry.problems.length === 0 ? "ok  " : "FAIL";
    console.log("  " + mark + "  " + entry.name);
    for (const problem of entry.problems.slice(0, 20)) {
      console.log("        " + problem);
    }
    if (entry.problems.length > 20) {
      console.log("        ... and " + (entry.problems.length - 20) + " more");
    }
  }

  if (failures.length) {
    console.log("");
    console.log("  " + failures.length + " field level disagreement(s) past " + TOLERANCE + ":");
    for (const entry of failures.slice(0, 25)) {
      console.log(
        "    " + entry.where + "  " + entry.what +
          (entry.channel ? "  [" + entry.channel + "]" : "")
      );
      console.log("      python     " + entry.expected);
      console.log("      javascript " + entry.actual);
      console.log("      difference " + entry.difference);
    }
    if (failures.length > 25) {
      console.log("    ... and " + (failures.length - 25) + " more");
    }
  }

  console.log("");
  console.log("  measured difference, reported every run, asserted by nobody");
  for (const line of measurementReport()) {
    console.log(line);
  }
  console.log("");
  console.log("  " + passed + " of " + checks.length + " checks passed");
  // The exit code answers to one thing, SPEC.md section 7.1's 1e-9, plus the
  // structural checks above. Bit exactness is measured and printed, never
  // asserted: see the header for why it is not a bar anything could meet.
  const failed = checks.filter((entry) => entry.problems.length > 0);
  return failed.length === 0 && failures.length === 0;
}

const ok = report();
process.exit(ok ? 0 : 1);
