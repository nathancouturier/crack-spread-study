#!/usr/bin/env node
// Run the frontend's pure modules under plain node and check what they print.
//
//     node tools/validate-format.mjs
//
// src/format.js turns artifact values into text and writes the loading, error
// and empty sentences; src/router.js parses the address; src/state.js parses
// the open sections out of it. None of the three touches the DOM in the
// functions tested here, so they run in node exactly as in the browser. Plain
// node, no dependencies. In `make gate`.
//
// Two kinds of check:
//   1  cases written here, one behaviour each: signs, the two minus signs,
//      rounding to zero, grouping, a missing value, an undeclared format, the
//      failure and empty sentences, the router's shapes of hash
//   2  a cross check against data/now.json: every numeric segment formats with
//      the decimals the artifact declares, and every fetch time the export
//      labelled reads the same when format.js formats the ISO value itself. The
//      exporter is Python and this is JavaScript, so agreement is a fact about
//      both rather than a claim by one.
//
// The figures below are test inputs inside a tool, not frontend code;
// tools/check-literals.mjs scans src/ and index.html only.

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const load = (relative) => import(pathToFileURL(path.join(ROOT, relative)).href);

const format = await load("src/format.js");
const router = await load("src/router.js");
const state = await load("src/state.js");

let failed = 0;
let passed = 0;
function check(name, actual, expected) {
  const ok = Object.is(actual, expected) || JSON.stringify(actual) === JSON.stringify(expected);
  if (ok) passed += 1;
  else {
    failed += 1;
    console.log("  FAIL  " + name + ": expected " + JSON.stringify(expected) + ", got " + JSON.stringify(actual));
  }
}
function throws(name, fn, fragment) {
  try {
    fn();
    failed += 1;
    console.log("  FAIL  " + name + ": expected an error mentioning " + JSON.stringify(fragment));
  } catch (error) {
    check(name, String(error.message).includes(fragment), true);
  }
}

const MINUS = String.fromCodePoint(0x2212);
const dec = { usd_bbl: 2, kb_d: 1, count: 0, year: 0, ratio: 1 };

console.log("validate-format.mjs, repo " + ROOT);

// ------------------------------------------------------------ numbers ---
check("two places", format.formatNumber(38.050505, "usd_bbl", dec), "38.05");
check("negative in prose carries U+2212", format.formatNumber(-3.68, "usd_bbl", dec), MINUS + "3.68");
check("negative in a table carries the hyphen minus", format.formatNumber(-3.68, "usd_bbl", dec, { context: "table" }), "-3.68");
check("signed positive", format.formatNumber(59.338024, "kb_d", dec, { signed: true }), "+59.3");
check("unsigned positive has no plus", format.formatNumber(59.338024, "kb_d", dec), "59.3");
check("rounds to zero prints no sign", format.formatNumber(-0.004, "usd_bbl", dec, { signed: true }), "0.00");
check("positive rounding to zero prints no plus", format.formatNumber(0.004, "usd_bbl", dec, { signed: true }), "0.00");
check("a computed zero is a number, not a gap", format.formatNumber(0, "usd_bbl", dec), "0.00");
check("count groups thousands", format.formatNumber(2000, "count", dec), "2,000");
check("a year never groups", format.formatNumber(2026, "year", dec), "2026");
check("null is missing, not zero", format.formatNumber(null, "usd_bbl", dec), null);
check("NaN is missing", format.formatNumber(NaN, "usd_bbl", dec), null);
check("Infinity is missing", format.formatNumber(Infinity, "usd_bbl", dec), null);
check("a numeric string is missing, never coerced", format.formatNumber("38.05", "usd_bbl", dec), null);
check("quantity with unit", format.formatQuantity(38.050505, "usd_bbl", dec), "38.05 $/bbl");
check("quantity of a missing value", format.formatQuantity(null, "usd_bbl", dec), null);
throws("an undeclared format throws, naming it", () => format.formatNumber(1, "eur_mwh", dec), "eur_mwh");
throws("no decimals table throws", () => format.formatNumber(1, "usd_bbl", undefined), "conventions.decimals");

// ----------------------------------------------------------- segments ---
check("text segment", format.segmentText({ text: "a refiner kept " }, dec), { text: "a refiner kept ", kind: "text", field: null, missing: false });
check("label segment", format.segmentText({ field: "margin_month", value: "2026-08-01", label: "August 2026" }, dec), { text: "August 2026", kind: "label", field: "margin_month", missing: false });
check("signed number segment", format.segmentText({ field: "capacity_kb_d", value: -12.34, format: "kb_d", signed: true }, dec), { text: MINUS + "12.3", kind: "number", field: "capacity_kb_d", missing: false });
check("missing number segment keeps its field", format.segmentText({ field: "headroom_usd_bbl", value: null, format: "usd_bbl" }, dec), { text: null, kind: "number", field: "headroom_usd_bbl", missing: true });
check("missing figure words", format.missingFigureText("headroom_usd_bbl"), "no figure for headroom usd bbl");

// --------------------------------------------------------------- time ---
check("instant", format.formatInstant("2026-09-13T18:11:38Z"), "13 September 2026 at 18:11 UTC");
check("instant before ten in the morning keeps two digits", format.formatInstant("2026-09-12T08:51:10Z"), "12 September 2026 at 08:51 UTC");
check("invalid instant", format.formatInstant("not a date"), null);
check("absent instant", format.formatInstant(null), null);

// --------------------------------------------- loading, error, empty ---
check("loading sentence", format.loadingSentence("the gasoil and gasoline cracks"), "Loading the gasoil and gasoline cracks.");
const failure = { path: "data/now.json", holds: "the landing sentence and the data dates", what: "the server answered 404 Not Found", at: "2026-09-16T12:04:05.000Z" };
const [happened, todo] = format.loadFailureSentences(failure);
check("failure names the file", happened.includes("data/now.json"), true);
check("failure says what went wrong", happened.includes("404 Not Found"), true);
check("failure carries the time of the failed fetch", happened.includes("16 September 2026 at 12:04 UTC"), true);
check("failure says what to do", /^Reload the page/.test(todo), true);
const empty = format.emptySeriesSentence({ series: "the DGEC weekly note", fetchedAt: "2026-09-13T18:11:38Z", status: "failed", reason: "The ministry deleted the note before it was collected" });
check("empty chart names the series", empty.includes("the DGEC weekly note"), true);
check("empty chart names the time of the failed fetch", empty.includes("its last fetch failed, at 13 September 2026 at 18:11 UTC"), true);
check("empty chart carries the reason", empty.includes("before it was collected."), true);
check("empty chart with no recorded time says so", format.emptySeriesSentence({ series: "x", fetchedAt: null, status: "failed", reason: null }).includes("not recorded"), true);
check("empty sentences hold no digit that did not come from the input", /\d/.test(format.emptySeriesSentence({ series: "x", fetchedAt: null, status: "stale", reason: null })), false);

// ------------------------------------------------------------- router ---
const views = ["now"];
check("empty hash is the default view", router.parse("", views, "now"), { kind: "route", view: "now", params: {}, hash: "#/" });
check("hash route", router.parse("#/now", views, "now").view, "now");
check("open sections in the hash", router.parse("#/now?open=cracks,runs", views, "now").params, { open: "cracks,runs" });
check("a view that does not exist is unknown, not Now", router.parse("#/history", views, "now"), { kind: "unknown", view: "history", params: {}, hash: "#/history" });
check("a fragment is not a route", router.parse("#view-title", views, "now").kind, "fragment");
check("a malformed escape does not throw", router.parse("#/%E0%A4%A", views, "now").kind, "unknown");
check("href sorts keys and keeps commas", router.href("now", { open: "cracks,runs", a: "" }), "#/now?open=cracks,runs");
check("href without state", router.href("now"), "#/now");
check("href round trips", router.parse(router.href("now", { open: "margin" }), views, "now").params, { open: "margin" });

// -------------------------------------------------------------- state ---
const sections = ["cracks", "margin", "runs", "provenance"];
check("open sections keep the page order", state.openSections({ open: "runs,cracks" }, sections), ["cracks", "runs"]);
check("unknown section ids are dropped", state.openSections({ open: "cracks,history" }, sections), ["cracks"]);
check("no open parameter", state.openSections({}, sections), []);
check("params for none open", state.openParams([]), {});

// ------------------------------------------------ cross check now.json ---
const now = JSON.parse(readFileSync(path.join(ROOT, "data/now.json"), "utf8"));
const decimals = now.conventions.decimals;
const sentences = [now.verdict.segments, ...now.data_dates.map((row) => row.segments), ...now.sections.map((s) => s.summary_segments)];
let numeric = 0;
let instants = 0;
for (const segments of sentences) {
  for (const segment of segments) {
    if (typeof segment.format === "string") {
      numeric += 1;
      const piece = format.segmentText(segment, decimals);
      check("now.json " + segment.field + " formats with declared decimals", typeof piece.text === "string" && piece.text.length > 0, true);
    }
    if (segment.field === "fetched_at") {
      instants += 1;
      check("now.json fetch time label agrees with format.js for " + segment.value, format.formatInstant(segment.value), segment.label);
    }
  }
}
check("now.json carries numeric segments to check", numeric > 0, true);
check("now.json carries fetch times to check", instants > 0, true);

console.log("  " + passed + " check(s) passed, " + failed + " failed; " + numeric + " numeric segment(s) and " + instants + " fetch time(s) of data/now.json cross checked");
if (failed) {
  console.log("FAIL  src/format.js, src/router.js or src/state.js does not do what the site relies on");
  process.exit(1);
}
console.log("PASS  formatting, sentences, routing and section state behave as specified");
