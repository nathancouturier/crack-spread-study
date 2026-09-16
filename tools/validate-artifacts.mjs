#!/usr/bin/env node
// Validate the site facing JSON artifacts that src/crack/export.py writes.
//
//     node tools/validate-artifacts.mjs
//     node tools/validate-artifacts.mjs path/to/other/data/dir
//
// Plain node, no npm install, no dependencies. Exits 0 when every check passes
// and 1 when any fails. It is in `make gate`.
//
// SPEC.md section 2 rule 2 says every number in the browser comes from a JSON
// artifact. That rule is only as good as the artifacts, so this reads them in a
// different language from the one that wrote them and checks, per artifact:
//
//    1  the file exists and parses as JSON
//    2  schema_version is the one this tool knows, generated_by names the
//       exporter, data_date is an ISO date, and there is no generated_at: a
//       generation timestamp would make `make build` not byte idempotent
//    3  no NaN and no Infinity token anywhere outside a string. JSON.parse
//       already refuses them, so this is also measured on the raw text, to
//       report WHERE rather than only that the parse failed
//    4  every field the Now view reads is present, and non null unless the
//       field is declared nullable below
//    5  every sentence is well formed: a text segment holds no digit, because a
//       figure in a sentence has to name the field it came from; a value
//       segment names its field; a numeric value segment names a format that
//       the artifact's conventions declare decimals for
//    6  the run verdict is coherent: an unidentified threshold carries a null
//       headroom and no sentence anywhere carries a headroom figure
//    7  the waterfall adds up: each step starts where the previous row ended,
//       the product rows and the residual end at the official margin, and the
//       wedge row ends at the margin at this study's gas intensity
//
// Nothing here is allowed to skip. A field this tool expects and cannot find is
// a failure, not a warning.

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const DATA = process.argv[2] ? path.resolve(process.argv[2]) : path.join(ROOT, "data");

const EXPECTED_SCHEMA_VERSION = 1;
const GENERATED_BY = "src/crack/export.py";
// The waterfall is stored to six places, so a sum of rounded rows can miss
// by a few millionths. This is a tolerance on stored rounding, not a unit.
const SUM_TOLERANCE = 1e-5;

// Field paths the Now view reads. "a.b" walks objects, "a[].b" walks every
// element of an array. A trailing "?" means the value may be null.
const REQUIRED = {
  now: [
    "conventions.decimals",
    "verdict.values.margin_month",
    "verdict.values.mbr_usd_bbl",
    "verdict.values.margin_basis",
    "verdict.values.net_of.gas",
    "verdict.values.net_of.embedded_gas_intensity_mmbtu_per_bbl",
    "verdict.values.net_of.costs_subtracted",
    "verdict.values.percentile_10y",
    "verdict.values.percentile_rank",
    "verdict.values.percentile_observations",
    "verdict.values.percentile_window_months",
    "verdict.values.percentile_window_first_month",
    "verdict.values.percentile_window_last_month",
    "verdict.values.margin_study_intensity_usd_bbl",
    "verdict.values.intensity_ratio",
    "verdict.values.gas_usd_mmbtu",
    "verdict.values.crack_month?",
    "verdict.values.carrier?",
    "verdict.values.carrier_contribution_usd_bbl?",
    "verdict.values.threshold_identified",
    "verdict.values.headroom_usd_bbl?",
    "verdict.values.run_verdict",
    "verdict.segments",
    "verdict.headroom_segments",
    "verdict.fallback_segments",
    "data_dates[].id",
    "data_dates[].date",
    "data_dates[].label",
    "data_dates[].provisional",
    "data_dates[].status_word",
    "data_dates[].fetch_status",
    "data_dates[].vintage",
    "data_dates[].fetched_at",
    "data_dates[].segments",
    "sections[].id",
    "sections[].name",
    "sections[].artifact",
    "sections[].summary_segments",
  ],
  cracks: [
    "conventions.decimals",
    "latest.date",
    "latest.n_years",
    "latest.products.gasoil.value_usd_bbl",
    "latest.products.gasoil.point.evidence",
    "latest.products.gasoil.point.evidence_class",
    "latest.products.gasoil.point.least_defended",
    "latest.products.gasoil.prior_minimum_usd_bbl",
    "latest.products.gasoil.prior_maximum_usd_bbl",
    "latest.products.gasoil.position",
    "latest.products.gasoil.prior_years[].year",
    "latest.products.gasoil.prior_years[].value_usd_bbl",
    "latest.products.gasoil.prior_years[].evidence",
    "latest.products.gasoil.prior_years[].evidence_class",
    "latest.products.gasoil.prior_years[].least_defended",
    "latest.products.gasoline.value_usd_bbl",
    "latest.products.gasoline.point.evidence",
    "latest.products.gasoline.point.least_defended",
    "latest.products.gasoline.position",
    "latest.products.gasoline.prior_years[].value_usd_bbl",
    "latest.products.gasoline.prior_years[].evidence",
    "latest.products.gasoline.prior_years[].least_defended",
    "panels.gasoil.prior_years",
    "panels.gasoil.current_year",
    "panels.gasoil.episode_years_in_range",
    "panels.gasoil.year_order",
    "panels.gasoil.weeks",
    "panels.gasoline.prior_years",
    "panels.gasoline.weeks",
    "series_note.segments",
  ],
  "margin-stack": [
    "conventions.decimals",
    "month",
    "decomposed",
    "rows[].id",
    "rows[].kind",
    "rows[].value_usd_bbl",
    "rows[].start_usd_bbl",
    "rows[].end_usd_bbl",
    "rows[].name",
    "scale.low_usd_bbl",
    "scale.high_usd_bbl",
    "residual_history.segments",
    "residual_segments",
    "wedge_segments",
  ],
  "run-economics": [
    "conventions.decimals",
    "threshold.threshold_identified",
    "threshold.verdict",
    "threshold.headroom_usd_bbl?",
    "threshold.threshold_ci_low_usd_bbl",
    "threshold.threshold_ci_high_usd_bbl",
    "threshold.segments",
    "threshold.fallback_segments",
    "response.order",
    "response.models[].id",
    "response.models[].label",
    "response.models[].equation",
    "response.models[].kb_d",
    "response.models[].kb_d_low",
    "response.models[].kb_d_high",
    "response.models[].interval_includes_zero",
    "response.models[].lower_share?",
    "response.models[].share_of_runs_percent",
    "response.models[].t",
    "response.models[].months",
    "response.disagreement.segments",
    "utilisation.runs_month",
    "utilisation.latest_utilisation_percent",
    "utilisation.latest_provisional",
    "utilisation.implied_by.equation",
    "utilisation.post_break_months[].month",
    "utilisation.post_break_months[].utilisation_percent",
    "utilisation.post_break_months[].implied_percent",
    "utilisation.post_break_months[].provisional",
    "utilisation.post_break_months[].status_word",
    "utilisation.segments",
  ],
  provenance: [
    "conventions.decimals",
    "attributions[].id",
    "attributions[].credit_line",
    "attributions[].licence",
    "fonts.substitution",
    "manifest.schema_version",
    "manifest.series[].series",
    "manifest.series[].status",
    "manifest.series[].fetched_at?",
    "manifest.series[].gaps",
    "manifest.series[].vintage?",
    "manifest.series[].licence_note",
    "manifest.manual_steps[].id",
    "manifest.manual_steps[].status",
  ],
};

const failures = [];
let passes = 0;

function check(name, fn) {
  let problems;
  try {
    problems = fn();
  } catch (error) {
    problems = [String(error && error.message ? error.message : error)];
  }
  if (problems.length) {
    failures.push(name);
    console.log("FAIL  " + name);
    for (const p of problems.slice(0, 20)) console.log("        " + p);
    if (problems.length > 20) console.log("        and " + (problems.length - 20) + " more");
  } else {
    passes += 1;
    console.log("PASS  " + name);
  }
}

// Walk a path, returning every [where, value] it reaches, or a problem.
function resolve(root, spec) {
  const nullable = spec.endsWith("?");
  const parts = (nullable ? spec.slice(0, -1) : spec).split(".");
  let frontier = [["", root]];
  for (const part of parts) {
    const each = part.endsWith("[]");
    const key = each ? part.slice(0, -2) : part;
    const next = [];
    for (const [where, value] of frontier) {
      const here = where ? where + "." + key : key;
      if (value === null || typeof value !== "object" || !(key in value)) {
        return { problem: here + " is missing" };
      }
      const child = value[key];
      if (each) {
        if (!Array.isArray(child)) return { problem: here + " is not an array" };
        if (!child.length) return { problem: here + " is an empty array" };
        child.forEach((item, i) => next.push([here + "[" + i + "]", item]));
      } else {
        next.push([here, child]);
      }
    }
    frontier = next;
  }
  return { nullable, reached: frontier };
}

// Every segment list anywhere in a payload, found by key name.
function segmentLists(value, where = "", out = []) {
  if (Array.isArray(value)) {
    value.forEach((item, i) => segmentLists(item, where + "[" + i + "]", out));
  } else if (value && typeof value === "object") {
    for (const [key, child] of Object.entries(value)) {
      const here = where ? where + "." + key : key;
      if (key.endsWith("segments") && Array.isArray(child)) out.push([here, child]);
      else segmentLists(child, here, out);
    }
  }
  return out;
}

// Strip JSON string literals so a token check does not trip on prose.
function withoutStrings(text) {
  return text.replace(/"(?:[^"\\]|\\.)*"/g, '""');
}

const loaded = {};
for (const name of Object.keys(REQUIRED)) {
  const file = path.join(DATA, name + ".json");
  check(name + ".json exists and parses", () => {
    if (!existsSync(file)) return [file + " does not exist. Run: make build"];
    const text = readFileSync(file, "utf8");
    const problems = [];
    const bare = withoutStrings(text);
    for (const token of ["NaN", "Infinity"]) {
      const at = bare.indexOf(token);
      if (at >= 0) problems.push("bare " + token + " token near: " + bare.slice(Math.max(0, at - 40), at + 20));
    }
    if (!text.endsWith("\n") || text.includes("\r")) problems.push("not LF with one trailing newline");
    try {
      loaded[name] = JSON.parse(text);
    } catch (error) {
      problems.push("does not parse: " + error.message);
    }
    return problems;
  });
}

for (const [name, specs] of Object.entries(REQUIRED)) {
  const payload = loaded[name];
  if (!payload) continue;

  check(name + ".json header: schema version, exporter, data date, no timestamp", () => {
    const problems = [];
    if (payload.schema_version !== EXPECTED_SCHEMA_VERSION) {
      problems.push("schema_version is " + JSON.stringify(payload.schema_version) + ", this tool knows " + EXPECTED_SCHEMA_VERSION);
    }
    if (payload.artifact !== name) problems.push("artifact is " + JSON.stringify(payload.artifact));
    if (payload.generated_by !== GENERATED_BY) problems.push("generated_by is " + JSON.stringify(payload.generated_by));
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(payload.data_date))) problems.push("data_date is not an ISO date: " + JSON.stringify(payload.data_date));
    if ("generated_at" in payload) problems.push("carries generated_at, which breaks byte idempotence");
    return problems;
  });

  check(name + ".json every field the Now view reads is present", () => {
    const problems = [];
    for (const spec of specs) {
      const result = resolve(payload, spec);
      if (result.problem) {
        problems.push(result.problem);
        continue;
      }
      for (const [where, value] of result.reached) {
        if (value === null && !result.nullable) problems.push(where + " is null and is not declared nullable");
        if (typeof value === "number" && !Number.isFinite(value)) problems.push(where + " is not finite");
      }
    }
    return problems;
  });

  check(name + ".json sentences: no digit in words, every figure names its field and format", () => {
    const problems = [];
    const decimals = (payload.conventions && payload.conventions.decimals) || {};
    const lists = segmentLists(payload);
    for (const [where, list] of lists) {
      list.forEach((segment, i) => {
        const at = where + "[" + i + "]";
        if (segment === null || typeof segment !== "object") {
          problems.push(at + " is not an object");
          return;
        }
        if ("text" in segment) {
          if (Object.keys(segment).length !== 1) problems.push(at + " mixes text with other keys");
          if (/[0-9]/.test(segment.text)) problems.push(at + " has a digit in its words: " + JSON.stringify(segment.text));
          return;
        }
        if (typeof segment.field !== "string" || !segment.field) problems.push(at + " names no field");
        if (!("value" in segment)) problems.push(at + " has no value");
        if (typeof segment.value === "number" || "format" in segment) {
          if (!(segment.format in decimals)) problems.push(at + " format " + JSON.stringify(segment.format) + " has no declared decimals");
          if (segment.value !== null && !Number.isFinite(segment.value)) problems.push(at + " value is not finite");
        } else if (typeof segment.label !== "string" || !segment.label) {
          problems.push(at + " is a date or word segment with no label");
        }
      });
    }
    return problems;
  });
}

if (loaded.now && loaded["run-economics"]) {
  check("the run verdict is coherent across now.json and run-economics.json", () => {
    const problems = [];
    const values = loaded.now.verdict.values;
    const threshold = loaded["run-economics"].threshold;
    if (values.threshold_identified !== threshold.threshold_identified) problems.push("threshold_identified differs between the two artifacts");
    if (values.headroom_usd_bbl !== threshold.headroom_usd_bbl) problems.push("headroom_usd_bbl differs between the two artifacts");
    if (!threshold.threshold_identified) {
      if (threshold.headroom_usd_bbl !== null || values.headroom_usd_bbl !== null) problems.push("unidentified but a headroom number is exported");
      if (threshold.verdict !== "unidentified") problems.push("unidentified but verdict reads " + JSON.stringify(threshold.verdict));
      for (const payload of [loaded.now, loaded["run-economics"]]) {
        for (const [where, list] of segmentLists(payload)) {
          list.forEach((segment, i) => {
            if (segment && segment.field === "headroom_usd_bbl") problems.push(payload.artifact + " " + where + "[" + i + "] prints a headroom while the threshold is unidentified");
          });
        }
      }
    } else if (typeof threshold.headroom_usd_bbl !== "number") {
      problems.push("identified but no headroom number");
    }
    return problems;
  });
}

if (loaded["margin-stack"] && loaded.now) {
  check("the waterfall adds up and ends where the verdict says", () => {
    const problems = [];
    const stack = loaded["margin-stack"];
    const rows = stack.rows;
    const byId = Object.fromEntries(rows.map((r) => [r.id, r]));
    const official = byId.official_margin;
    const study = byId.margin_study_intensity;
    if (!official || !study || !byId.residual || !byId.gas_wedge) return ["missing one of official_margin, margin_study_intensity, residual, gas_wedge"];
    let running = 0;
    for (const row of rows) {
      if (row.kind === "step") {
        if (Math.abs(row.start_usd_bbl - running) > SUM_TOLERANCE) problems.push(row.id + " starts at " + row.start_usd_bbl + ", the previous row ended at " + running);
        if (Math.abs(row.start_usd_bbl + row.value_usd_bbl - row.end_usd_bbl) > SUM_TOLERANCE) problems.push(row.id + " start plus value is not its end");
        running = row.end_usd_bbl;
      } else if (row.kind === "total") {
        if (Math.abs(row.value_usd_bbl - running) > SUM_TOLERANCE) problems.push(row.id + " total " + row.value_usd_bbl + " is not the running total " + running);
        running = row.value_usd_bbl;
      } else {
        problems.push(row.id + " has kind " + JSON.stringify(row.kind));
      }
    }
    const values = loaded.now.verdict.values;
    if (Math.abs(official.value_usd_bbl - values.mbr_usd_bbl) > SUM_TOLERANCE) problems.push("official margin row differs from the verdict");
    if (Math.abs(study.value_usd_bbl - values.margin_study_intensity_usd_bbl) > SUM_TOLERANCE) problems.push("margin at this study's gas use differs from the verdict");
    if (stack.month !== values.margin_month) problems.push("the waterfall month " + stack.month + " is not the margin month " + values.margin_month);
    if (values.carrier !== null && !(byId[values.carrier] && byId[values.carrier].carrier === true)) problems.push("the verdict's carrier is not the waterfall's carrier");
    const lo = stack.scale.low_usd_bbl;
    const hi = stack.scale.high_usd_bbl;
    for (const row of rows) {
      for (const v of [row.start_usd_bbl, row.end_usd_bbl]) {
        if (v < lo - SUM_TOLERANCE || v > hi + SUM_TOLERANCE) problems.push(row.id + " runs outside the declared scale");
      }
    }
    return problems;
  });
}

console.log("");
console.log(passes + " passed, " + failures.length + " failed, artifacts in " + DATA);
process.exit(failures.length ? 1 : 0);
