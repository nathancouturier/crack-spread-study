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
//    8  per view: History, Model, Runs, Events and Method keep their findings
//    9  every exported field has a reader in src/, or a sentence that prints
//       it, or a declared reason it has none (docs/design.md Part 8.5, D9)
//
// Nothing here is allowed to skip. A field this tool expects and cannot find is
// a failure, not a warning.

import { existsSync, readdirSync, readFileSync } from "node:fs";
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
    "verdict.values.percentile_rank_study_intensity",
    "verdict.values.percentile_observations_study_intensity",
    "verdict.values.percentile_ranks_agree",
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
    "manifest_columns",
    "reader.series",
    "reader.manual_steps_heading",
    "reader.manual_steps_intro",
    "reader.manual_steps[].id",
    "reader.manual_steps[].status",
    "reader.manual_steps[].what",
    "reader.manual_steps[].why",
    "reader.manual_steps[].cost",
    "reader.manual_steps[].how",
  ],
  // docs/design.md Part 8.1, the History view.
  history: [
    "conventions.decimals",
    "title_segments",
    "sample_segments",
    "monthly.first",
    "monthly.last",
    "monthly.columns",
    "monthly.rows",
    "monthly.r2_segments",
    "margin.first",
    "margin.last",
    "margin.columns",
    "margin.rows",
    "margin.wedge_heading_segments",
    "margin.no_break_segments",
    "weekly.first",
    "weekly.last",
    "weekly.columns",
    "weekly.rows",
    "weekly.evidence_segments",
    "weekly.join_segments",
    "events[].id",
    "events[].date",
    "events[].short",
    "events[].source_url",
    "breaks[].id",
    "breaks[].date",
    "breaks[].drawn",
    "breaks[].panel?",
    "breaks[].line?",
    "breaks[].reason?",
    "breaks[].source_url",
    "ranges[].id",
    "ranges[].start",
    "ranges[].end",
    "seasonal_monthly.months",
    "seasonal_monthly.note_segments",
    "seasonal_monthly.panels.gasoil.lines",
    "seasonal_monthly.panels.gasoil.variants.all.sentence_segments",
    "seasonal_monthly.panels.gasoil.variants.without_episodes.sentence_segments",
    "seasonal_monthly.panels.gasoline.lines",
    "seasonal_monthly.panels.gasoline.variants.all.sentence_segments",
  ],
  // docs/design.md Part 8.2, the Model view.
  model: [
    "conventions.decimals",
    "title_segments",
    "lead_segments",
    "basis.margin_basis",
    "basis.official_margin_basis",
    "products[].id",
    "products[].name",
    "products[].ministry_label",
    "products[].volume_yield",
    "products[].yield_source_segments",
    "slate.covered_volume_yield",
    "slate.segments",
    "intensity.study_mmbtu_per_bbl",
    "intensity.source_segments",
    "other_cost.value_usd_bbl",
    "other_cost.source_segments",
    "breakeven_target.value_usd_bbl",
    "breakeven_target.segments",
    "run.threshold_identified",
    "run.verdict",
    "run.run_cut_threshold_usd_bbl?",
    "run.headroom_usd_bbl?",
    "run.segments",
    "presets[].id",
    "presets[].label",
    "presets[].months",
    "presets[].reconstructed",
    "presets[].reason_segments",
    "presets[].note_segments",
    "presets[].inputs.yields",
    "presets[].inputs.ttf_eur_mwh",
    "presets[].inputs.eurusd",
    "presets[].inputs.gas_intensity_mmbtu_per_bbl",
    "presets[].inputs.other_variable_cost_usd_bbl",
    "presets[].sources.ttf_segments",
    "presets[].sources.eurusd_segments",
    "presets[].official.mbr_usd_bbl?",
    "presets[].official.label_segments",
    "presets[].official.gap_segments",
    "presets[].scale.low_usd_bbl",
    "presets[].scale.high_usd_bbl",
  ],
  // docs/design.md Part 8.3, the Runs and crude demand view.
  runs: [
    "conventions.decimals",
    "title_segments",
    "parts[].id",
    "parts[].label",
    "series.first",
    "series.last",
    "series.columns",
    "series.rows",
    "series.capacity_steps",
    "series.sample_segments",
    "series.capacity_segments",
    "series.imports.mean_imports_over_intake",
    "series.imports.is_a_model",
    "series.imports.segments",
    "episodes.rows[].model",
    "episodes.rows[].variant",
    "episodes.rows[].kb_d",
    "episodes.rows[].kb_d_low",
    "episodes.rows[].kb_d_high",
    "episodes.rows[].t",
    "episodes.rows[].months",
    "episodes.segments",
    "endogeneity_segments",
    "threshold.columns",
    "threshold.rows",
    "threshold.fits[].id",
    "threshold.fits[].kink_usd_bbl",
    "threshold.fits[].slope_below",
    "threshold.fits[].line",
    "threshold.interval.low_usd_bbl",
    "threshold.interval.high_usd_bbl",
    "threshold.interval.search_low_usd_bbl",
    "threshold.interval.search_high_usd_bbl",
    "threshold.interval.reaches_search_edge",
    "threshold.stretch.months_in_stretch",
    "threshold.stretch.months_below",
    "threshold.heading_segments",
    "threshold.stretch_segments",
    "threshold.interval_segments",
    "threshold.desc_segments",
    "race.size",
    "race.power_domain",
    "race.any_distinguishable",
    "race.sentence_segments",
    "race.margin_against_crack_segments",
    "race.equations[].id",
    "race.equations[].label",
    "race.equations[].horses[].key",
    "race.equations[].horses[].coefficient",
    "race.equations[].horses[].se",
    "race.equations[].horses[].t",
    "race.equations[].horses[].r2",
    "race.equations[].horses[].oos_rmse",
    "race.equations[].long_sample.coefficient",
    "race.equations[].long_sample.in_the_race",
    "race.equations[].pairs[].first",
    "race.equations[].pairs[].second",
    "race.equations[].pairs[].observed_gap_percent",
    "race.equations[].pairs[].detectable_gap_percent",
    "race.equations[].pairs[].power",
    "race.equations[].pairs[].forecasts_for_target_power",
    "race.equations[].caption_segments",
    "race.gives",
    "instrument.f_bar",
    "instrument.ladder[].controls",
    "instrument.ladder[].f",
    "instrument.ladder[].used_by",
    "instrument.equations[].first_stage_f",
    "instrument.equations[].iv_used",
    "instrument.sentence_segments",
    "instrument.diagnosis_segments",
    "break.pre_rows",
    "break.post_rows",
    "break.tested",
    "break.brackets[].start",
    "break.brackets[].end",
    "break.brackets[].label_segments",
    "break.fit_segments",
    "break.explanations[].name",
    "break.events[].source_url",
    "break.desc_segments",
  ],
  // docs/design.md Part 8.4, the Events view.
  events: [
    "conventions.decimals",
    "title_segments",
    "lead_segments",
    "window.months_before",
    "window.months_after",
    "series[].id",
    "series[].first",
    "series[].last",
    "margin_segments",
    "monthly_columns",
    "weekly_columns",
    "events[].id",
    "events[].date",
    "events[].precision",
    "events[].label",
    "events[].name",
    "events[].source_url",
    "events[].precision_segments",
    "events[].window.first",
    "events[].window.last",
    "events[].window.event_month",
    "events[].rows",
    "events[].coverage_segments",
    "not_panels[].id",
    "not_panels_segments",
  ],
  // docs/design.md Part 8.5, the Method view.
  method: [
    "conventions.decimals",
    "title_segments",
    "lead_segments",
    "sections[].id",
    "sections[].title",
    "sections[].blocks",
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

if (loaded.provenance) {
  // docs/design.md Part 7, C12 and C13: the Provenance section prints a reader
  // label for every manifest series, and says whether any of it is provisional
  // (SPEC.md section 5.3). A series the page would print as a bare id, or a
  // flagged series whose row would not say provisional, fails here.
  check("provenance.json every manifest series has a reader label and its provisional words", () => {
    const problems = [];
    const reader = loaded.provenance.reader || {};
    const rows = reader.series || {};
    for (const entry of loaded.provenance.manifest.series) {
      const row = rows[entry.series];
      if (!row) {
        problems.push(entry.series + " has no reader row");
        continue;
      }
      if (typeof row.label !== "string" || !row.label || /_/.test(row.label)) problems.push(entry.series + " reader label is missing or has an underscore: " + JSON.stringify(row.label));
      if (typeof row.source !== "string" || !row.source) problems.push(entry.series + " reader source is missing");
      const words = (row.provisional_segments || []).map((segment) => segment.text !== undefined ? segment.text : segment.label).join("");
      if (entry.provisional_from && !/^provisional/.test(words)) problems.push(entry.series + " is provisional from " + entry.provisional_from + " and its reader words are " + JSON.stringify(words));
      if (!entry.provisional_from && words !== "none flagged") problems.push(entry.series + " is not flagged and its reader words are " + JSON.stringify(words));
    }
    const stepIds = new Set((reader.manual_steps || []).map((step) => step.id));
    for (const step of loaded.provenance.manifest.manual_steps || []) {
      if (!stepIds.has(step.id)) problems.push("the manual step " + step.id + " has no reader text");
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

if (loaded.now && loaded.history) {
  // GATE 5 FINDING 9. The landing sentence carries both gas figures, so the
  // rank clause that follows them has to be true of both. The two ranks are
  // recomputed here from the rows the History view draws, and the sentence may
  // only leave the measure unsaid while they agree.
  check("the verdict's rank clause holds on both gas measures", () => {
    const problems = [];
    const values = loaded.now.verdict.values;
    const margin = loaded.history.margin;
    const at = (name) => margin.columns.indexOf(name);
    const date = at("date");
    const mbr = at("mbr_usd_bbl");
    const wedge = at("gas_wedge_usd_bbl");
    if (date < 0 || mbr < 0 || wedge < 0) return ["history.json margin is missing a column this check reads"];
    const window = margin.rows.filter((row) => row[date] >= values.percentile_window_first_month && row[date] <= values.percentile_window_last_month);
    const official = window.filter((row) => row[mbr] !== null).map((row) => row[mbr]);
    const study = window.filter((row) => row[mbr] !== null && row[wedge] !== null).map((row) => row[mbr] - row[wedge]);
    const rankOf = (list, value) => list.filter((x) => x <= value + SUM_TOLERANCE).length;
    if (official.length !== values.percentile_observations) problems.push("the window holds " + official.length + " published months, the verdict says " + values.percentile_observations);
    if (rankOf(official, values.mbr_usd_bbl) !== values.percentile_rank) problems.push("the rank on the ministry's measure is not " + values.percentile_rank);
    if (rankOf(study, values.margin_study_intensity_usd_bbl) !== values.percentile_rank_study_intensity) problems.push("the rank on this study's measure is not " + values.percentile_rank_study_intensity);
    const agree = values.percentile_rank === values.percentile_rank_study_intensity && values.percentile_observations === values.percentile_observations_study_intensity;
    if (agree !== values.percentile_ranks_agree) problems.push("percentile_ranks_agree says " + values.percentile_ranks_agree + " and the two ranks say " + agree);
    const spoken = loaded.now.verdict.segments.map((s) => (s.text !== undefined ? s.text : String(s.label === undefined ? s.value : s.label))).join("");
    const names = spoken.includes("on the ministry's measure");
    if (!agree && !names) problems.push("the two measures rank the month differently and the verdict does not say whose rank it gives");
    if (agree && names) problems.push("the two measures agree and the verdict names one of them anyway");
    if (!spoken.includes("at this study's gas use")) problems.push("the verdict does not carry this study's gas figure");
    return problems;
  });
}

if (loaded.history) {
  // Part 8.1: three panels never spliced, breaks only where a line carries
  // them, never one on the margin, the wedge never subtracted, every range
  // inside the data, no gap bridged by a zero.
  check("history.json panels, breaks and ranges keep the findings", () => {
    const problems = [];
    const h = loaded.history;
    for (const key of ["monthly", "margin", "weekly"]) {
      const panel = h[key];
      const dates = panel.rows.map((row) => row[0]);
      for (let i = 1; i < dates.length; i += 1) if (!(dates[i] > dates[i - 1])) problems.push(key + " dates are not strictly increasing at " + dates[i]);
      if (dates[0] !== panel.first || dates[dates.length - 1] !== panel.last) problems.push(key + " first and last do not match its rows");
    }
    if (h.margin.columns.some((c) => /after_gas|net_margin/.test(c))) problems.push("the margin panel carries a margin with gas subtracted: " + h.margin.columns.join(", "));
    if (h.weekly.first <= h.monthly.first) problems.push("the weekly panel starts before the monthly one, so something was spliced");
    for (const brk of h.breaks) {
      if (brk.drawn) {
        const ok = (brk.panel === "monthly" && ["gasoil", "gasoline"].includes(brk.line)) || (brk.panel === "margin" && brk.line === "gas_wedge");
        if (!ok) problems.push(brk.id + " is drawn on " + brk.panel + " " + brk.line + ", which is not a line that carries a break");
      } else if (typeof brk.reason !== "string" || !brk.reason) {
        problems.push(brk.id + " is not drawn and says no reason");
      }
      if (brk.line === "mbr" || brk.line === "margin") problems.push(brk.id + " is drawn on the official margin, which has no break inside its published window");
    }
    const end = [h.monthly.last, h.margin.last, h.weekly.last].sort().pop();
    for (const range of h.ranges) {
      if (range.start < h.monthly.first || range.end > end || range.start > range.end) problems.push("range " + range.id + " runs outside the data, " + range.start + " to " + range.end);
    }
    const g = h.seasonal_monthly.panels;
    for (const product of ["gasoil", "gasoline"]) {
      for (const [year, values] of g[product].lines) if (values.length !== h.seasonal_monthly.months.length) problems.push(product + " " + year + " does not have one value per month");
    }
    return problems;
  });
}

if (loaded.model) {
  // Part 8.2: the model margin is gross of gas and the MBR is never a step of
  // it; no threshold, no headroom; every preset product either has a crack or
  // says why it has none, and never both.
  check("model.json keeps gross apart from net, invents no threshold and names every missing input", () => {
    const problems = [];
    const m = loaded.model;
    if (m.basis.margin_basis !== "gross_of_gas") problems.push("the model margin basis is " + m.basis.margin_basis);
    if (m.basis.official_is_a_step !== false) problems.push("the official margin is marked as a step of the model");
    if (m.run.threshold_identified !== false || m.run.run_cut_threshold_usd_bbl !== null || m.run.headroom_usd_bbl !== null) problems.push("model.json carries a threshold or a headroom");
    if (m.breakeven_target.value_usd_bbl !== 0) problems.push("the breakeven target is not a margin of zero");
    for (const [where, list] of segmentLists(m)) {
      list.forEach((segment, i) => {
        if (segment && segment.field === "headroom_usd_bbl") problems.push(where + "[" + i + "] prints a headroom");
      });
    }
    const ids = m.products.map((p) => p.id);
    for (const preset of m.presets) {
      for (const id of ids) {
        const value = preset.inputs.cracks[id];
        const source = preset.sources.cracks[id];
        if (!source) { problems.push(preset.id + " " + id + " has no source sentence"); continue; }
        if ((value === null) === source.available) problems.push(preset.id + " " + id + " crack and its availability disagree");
        if (value === null && !/^No figure/.test(source.segments.map((s) => s.text || s.label || "").join(""))) problems.push(preset.id + " " + id + " is missing and does not say so");
        if (typeof preset.inputs.yields[id] !== "number") problems.push(preset.id + " " + id + " has no yield");
      }
      const words = preset.note_segments.map((s) => s.text || s.label || "").join("");
      if (preset.reconstructed && !/^Reconstructed/.test(words)) problems.push(preset.id + " is reconstructed and its note does not open with the word");
      if (preset.scale.low_usd_bbl > 0 || preset.scale.high_usd_bbl < 0) problems.push(preset.id + " scale does not hold zero");
    }
    return problems;
  });
}

if (loaded.runs && loaded["run-economics"]) {
  // Part 8.3: nothing ranked, nothing identified, nothing trimmed, nothing
  // joined, and the view agrees with the Now section it shares a table with.
  check("runs.json ranks no horse, marks no threshold, trims no interval and joins no break", () => {
    const problems = [];
    const r = loaded.runs;
    const re = loaded["run-economics"];
    const text = JSON.stringify(r).toLowerCase();
    for (const word of ["winner", " wins", "best", " tie", "dead heat", "equivalent"]) if (text.includes(word)) problems.push("the banned word " + JSON.stringify(word.trim()));
    for (const eq of r.race.equations) {
      if (eq.horses.map((h) => h.key).join("") !== "ABC") problems.push(eq.id + " horses are not in the order A, B, C");
      if (eq.long_sample.in_the_race !== false) problems.push(eq.id + " puts horse A's long sample in the race");
      const c = eq.horses.find((h) => h.key === "C");
      if (!c || c.substitution !== true || !c.substitution_segments) problems.push(eq.id + " horse C is not labelled a substitution");
      for (const pair of eq.pairs) if (pair.distinguishable !== r.race.any_distinguishable && pair.distinguishable) problems.push(eq.id + " pair " + pair.first + pair.second + " is distinguishable and the race says none is");
    }
    if (re.threshold.threshold_identified === false) {
      const iv = r.threshold.interval;
      if (iv.reaches_search_edge && iv.high_usd_bbl !== iv.search_high_usd_bbl && iv.low_usd_bbl !== iv.search_low_usd_bbl) problems.push("the interval is said to reach the edge and stops short of both");
      if (iv.trimmed !== false) problems.push("the interval is trimmed");
      for (const [where, list] of segmentLists(r)) list.forEach((segment, i) => { if (segment && segment.field === "headroom_usd_bbl") problems.push(where + "[" + i + "] prints a headroom"); });
    }
    const cap = re.response.models.find((m) => m.id === "capacity");
    const title = Object.fromEntries(r.title_segments.filter((s) => "field" in s).map((s) => [s.field, s.value]));
    if (!cap || Math.abs(title.kb_d - cap.kb_d) > SUM_TOLERANCE) problems.push("the view's title and the Now section disagree on the planned model's kb/d");
    const pre = r.break.pre_rows;
    const post = r.break.post_rows;
    if (!pre.length || !post.length || !(post[0][0] > pre[pre.length - 1][0])) problems.push("the post break residuals do not start after the fitted months");
    if (r.break.tested !== re.utilisation.tested) problems.push("the view and the Now section disagree on whether 2026 is tested");
    for (const row of r.series.rows) if (row[1] === 0 && row[3] === null) problems.push("a missing month drawn as zero at " + row[0]);
    return problems;
  });
}

if (loaded.events) {
  // Part 8.4: every window is the full thirteen months, a missing month is
  // null and never zero, every missing series is named, the precision the
  // source gives is kept.
  check("events.json keeps every window whole, fills nothing and names every gap", () => {
    const problems = [];
    const e = loaded.events;
    const c = (name) => e.monthly_columns.indexOf(name);
    const span = e.window.months_before + e.window.months_after + 1;
    const series = Object.fromEntries(e.series.map((s) => [s.id, s]));
    const columns = { monthly_cracks: ["gasoil_usd_bbl", "gasoline_usd_bbl"], margin: ["mbr_usd_bbl"], utilisation: ["utilisation_percent"] };
    for (const ev of e.events) {
      if (ev.rows.length !== span) problems.push(ev.id + " has " + ev.rows.length + " months, not " + span);
      const offsets = ev.rows.map((row) => row[c("offset_months")]);
      if (offsets[0] !== -e.window.months_before || offsets[offsets.length - 1] !== e.window.months_after) problems.push(ev.id + " window does not run from minus to plus the declared months");
      if (!["day", "month"].includes(ev.precision)) problems.push(ev.id + " precision is " + ev.precision);
      for (const [id, cols] of Object.entries(columns)) {
        const empty = ev.rows.some((row) => cols.every((col) => row[c(col)] === null));
        const named = ev.missing.some((m) => m.series === id);
        if (empty && !named) problems.push(ev.id + " lacks months of " + id + " and does not say so");
        if (!empty && named) problems.push(ev.id + " names " + id + " as missing and it is not");
        for (const row of ev.rows) {
          for (const col of cols) {
            if (row[c(col)] !== null && (row[0] < series[id].first || row[0] > series[id].last)) problems.push(ev.id + " has a value for " + col + " at " + row[0] + ", outside the series");
          }
        }
      }
      if (!ev.weekly_rows.length && !ev.missing.some((m) => m.series === "weekly")) problems.push(ev.id + " has no weekly rows and does not say so");
      if (!/^https?:\/\//.test(ev.source_url)) problems.push(ev.id + " has no source link");
    }
    const words = JSON.stringify(e).toLowerCase();
    for (const word of ["impact", "caused by"]) if (words.includes(word)) problems.push("the word " + JSON.stringify(word) + ", which claims a cause");
    return problems;
  });
}

if (loaded.method) {
  // Part 8.5: every ref resolves to a sentence another artifact carries, every
  // reads block names a table the view builds, every table row has its columns.
  check("method.json refs resolve, tables are whole, the departures and the findings are there", () => {
    const problems = [];
    const READS = ["response_diagnostics", "margin_stack_prices", "breaks", "manual_steps", "reuse"];
    const resolveRef = (ref) => {
      let value = loaded[ref.artifact];
      for (const key of ref.path) value = value === undefined || value === null ? undefined : value[key];
      return Array.isArray(value) && value.length ? value : null;
    };
    const reads = new Set();
    for (const section of loaded.method.sections) {
      for (const block of section.blocks) {
        if (block.type === "ref" && !resolveRef(block)) problems.push(section.id + ": the ref " + block.artifact + " " + block.path.join(".") + " does not resolve to a sentence");
        if (block.type === "list") for (const item of block.items) if (!Array.isArray(item) && !resolveRef(item.ref)) problems.push(section.id + ": the list ref " + item.ref.artifact + " " + item.ref.path.join(".") + " does not resolve");
        if (block.type === "reads") {
          if (!READS.includes(block.what)) problems.push(section.id + ": unknown reads block " + block.what);
          reads.add(block.what);
        }
        if (block.type === "table") for (const row of block.rows) if (row.length !== block.columns.length) problems.push(section.id + ": a table row has " + row.length + " cells for " + block.columns.length + " columns");
      }
    }
    for (const what of READS) if (!reads.has(what)) problems.push("the Method view never reads " + what);
    const text = JSON.stringify(loaded.method);
    for (const needle of ["already net", "substitution", "leave one series out", "Eurosuper", "Gazole", "Carbon costs", "does not bound the oldest weeks"]) {
      if (!text.includes(needle)) problems.push("the Method view does not say " + JSON.stringify(needle));
    }
    return problems;
  });
}

// ORPHAN FIELDS, docs/design.md Part 8.5 D9. Every key of every artifact is
// read by some module in src/, or printed through a sentence segment that
// names it, or is declared below with the reason it is carried and not
// printed. The Gate 4 audit found four fields exported and never rendered;
// they may not be declared here, and a declared key that a module starts
// reading fails too, so the list cannot go stale.
const NEVER_SUPPORTING = ["factor_citation", "price_usd_t", "r2", "newey_west_lag"];
const WHY = {
  flag: "a flag or count the validators and tests assert on; the page prints the sentence it produced",
  copy: "a machine readable copy of a figure the page prints through a sentence under another field name",
  map: "a key of a map the page reads by iterating it, never by name",
  provenance: "provenance of a value for a reader of the file, not for the page",
  model: "read by the export or the parity fixture, not by the page",
};
const SUPPORTING = {
  cracks: { iso_year: WHY.provenance, iso_week: WHY.provenance, printed_usd_bbl: WHY.copy, n_independent_geometries: WHY.provenance, least_defended: WHY.flag, prior_years: WHY.copy, printed_weeks: WHY.flag, gasoil_bbl_per_t: WHY.provenance, gasoline_bbl_per_t: WHY.provenance, brent_bbl_per_t: WHY.provenance },
  events: { data_last: WHY.copy },
  history: { study_intensity_mmbtu_per_bbl: WHY.copy, ministry_intensity_mmbtu_per_bbl: WHY.copy, no_break_source_url: WHY.provenance, partial_years: WHY.flag },
  "margin-stack": { slate_line: WHY.provenance, volume_yield: WHY.model, unattributed_mass_yield_percent: WHY.copy, approximations: WHY.provenance, residual_share: WHY.copy, gas_source: WHY.provenance, embedded_cost_usd_bbl: WHY.copy, study_cost_usd_bbl: WHY.copy, includes_zero: WHY.flag, official_usd_bbl: WHY.copy, quotations_vintage: WHY.provenance, not_decomposed: WHY.flag },
  model: { margin_basis: WHY.flag, official_margin_basis: WHY.flag, official_is_a_step: WHY.flag, slate_line: WHY.provenance, volume_yield: WHY.model, unattributed_slate_lines: WHY.provenance, study_mmbtu_per_bbl: WHY.copy, embedded_mmbtu_per_bbl: WHY.copy, run_cut_threshold_usd_bbl: WHY.flag, crack_source: WHY.provenance, jet: WHY.map, heating_oil: WHY.map, fuel_oil_1pct: WHY.map, evidence_classes: WHY.provenance },
  now: { margin_basis: WHY.flag, net_of: WHY.provenance, embedded_gas_intensity_mmbtu_per_bbl: WHY.copy, embedded_gas_mass_yield_percent: WHY.copy, costs_subtracted: WHY.provenance, costs_not_subtracted: WHY.provenance, percentile_10y: WHY.copy, percentile_rank: WHY.copy, percentile_months_below: WHY.copy, percentile_window_months: WHY.copy, percentile_window_first_month: WHY.copy, percentile_window_last_month: WHY.copy, percentile_rank_study_intensity: WHY.flag, percentile_observations_study_intensity: WHY.flag, percentile_ranks_agree: WHY.flag, study_gas_intensity_mmbtu_per_bbl: WHY.copy, intensity_ratio: WHY.copy, crack_month: WHY.copy, carrier_label: WHY.copy, carrier_reason: WHY.provenance, run_verdict: WHY.flag, headroom_segments: WHY.copy, fetch_status: WHY.flag, quotations_provisional: WHY.flag },
  "run-economics": { threshold_ci_width_usd_bbl: WHY.copy, max_ci_width_usd_bbl: WHY.flag, interval_touches_lower_edge: WHY.flag, interval_touches_upper_edge: WHY.flag, interval_too_wide: WHY.flag, slope_below_usd_bbl: WHY.copy, slope_below_without_episode: WHY.copy, slope_changes_sign_without_episode: WHY.flag, months_below_every_month: WHY.copy, nobs_every_month: WHY.copy, months_below_without_episode: WHY.copy, nobs_without_episode: WHY.copy, bootstrap_replications: WHY.provenance, bootstrap_seed: WHY.provenance, reasons: WHY.flag, closure_step_years_in_sample: WHY.provenance, lower_share: WHY.copy, share_of_runs_low_percent: WHY.copy, share_of_runs_high_percent: WHY.copy, sum_of_lags_unit: WHY.provenance, capacity_step_years_in_sample: WHY.provenance, diagnostic_sum_of_lags: WHY.copy, diagnostic_is_reported_as_a_result: WHY.flag, latest_provisional: WHY.flag, first_month_not_fitted: WHY.copy },
  runs: { margin_regressor: WHY.provenance, mean_imports_over_intake: WHY.copy, min_imports_over_intake: WHY.copy, max_imports_over_intake: WHY.copy, is_a_model: WHY.flag, headline: WHY.flag, level_percent: WHY.copy, regressor_low_usd_bbl: WHY.copy, regressor_high_usd_bbl: WHY.copy, reaches_search_edge: WHY.flag, trimmed: WHY.flag, any_distinguishable: WHY.flag, in_the_race: WHY.flag, distinguishable: WHY.flag, wedge_before_2022_usd_bbl: WHY.copy, wedge_2022_usd_bbl: WHY.copy },
};
/* A key whose children are map keys is walked no further, and the provenance
 * manifest is skipped whole: it is shipped as SPEC.md section 5.3's first class
 * artifact, and the page prints its reader layer, checked above. */
const MAP_PARENTS = new Set(["date_of_last_update", "provenance.reader.series"]);
const HEADER = new Set(["schema_version", "artifact", "generated_by", "data_date", "describes", "source", "conventions"]);
{
  const srcDir = path.join(ROOT, "src");
  const source = readdirSync(srcDir).filter((f) => f.endsWith(".js")).map((f) => readFileSync(path.join(srcDir, f), "utf8")).join("\n");
  const readsKey = (key) => new RegExp("\\b" + key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b").test(source);
  check("every exported field has a reader, or a declared reason it has none", () => {
    const problems = [];
    for (const name of NEVER_SUPPORTING) for (const [artifact, list] of Object.entries(SUPPORTING)) if (name in list) problems.push(artifact + " declares " + name + " as supporting, and the Gate 4 audit requires it rendered");
    for (const [name, payload] of Object.entries(loaded)) {
      const keys = new Set();
      const said = new Set();
      const walk = (value, top, where) => {
        if (Array.isArray(value)) value.forEach((item) => walk(item, false, where));
        else if (value && typeof value === "object") {
          if (typeof value.field === "string") said.add(value.field);
          for (const [key, child] of Object.entries(value)) {
            if (top && HEADER.has(key)) continue;
            if (top && name === "provenance" && key === "manifest") continue;
            keys.add(key);
            const here = where + "." + key;
            if (!MAP_PARENTS.has(key) && !MAP_PARENTS.has(here)) walk(child, false, here);
          }
        }
      };
      walk(payload, true, name);
      const declared = SUPPORTING[name] || {};
      for (const key of keys) {
        const read = readsKey(key) || said.has(key);
        if (!read && !(key in declared)) problems.push(name + ".json exports " + key + ", which no module reads and no sentence prints");
      }
      for (const key of Object.keys(declared)) {
        if (!keys.has(key)) problems.push(name + ".json declares " + key + " as supporting and no longer exports it");
        else if (readsKey(key) || said.has(key)) problems.push(name + ".json declares " + key + " as supporting and it is now read or printed; take it off the list");
      }
    }
    return problems;
  });
}

console.log("");
console.log(passes + " passed, " + failures.length + " failed, artifacts in " + DATA);
process.exit(failures.length ? 1 : 0);
