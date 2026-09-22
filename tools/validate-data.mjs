#!/usr/bin/env node
// Validate data/manifest.json against the files it describes.
//
//     node tools/validate-data.mjs
//     node tools/validate-data.mjs path/to/other-manifest.json
//
// Plain node, no npm install, no dependencies, runnable from anywhere. Exits 0
// when every check passes and 1 when any of them fails, so it can be the deploy
// gate SPEC.md non negotiable 7 asks for.
//
// THE POINT OF THIS FILE IS THAT IT IS NOT THE CODE THAT WROTE THE MANIFEST.
// scripts/refresh.py measures the caches in Python and records what it found.
// This reads the same files in JavaScript, measures them again, and compares. A
// number only one of the two produces is a claim. A number both produce
// independently is a fact. That is why the gap lists and the row counts are
// recomputed here rather than trusted, even though recomputing them is the
// slowest thing this tool does.
//
// What is checked, in order:
//
//    1  the manifest parses and declares the schema version this tool knows
//    2  the header fields are present and no series name appears twice
//    3  every entry carries the required keys, with a status, a method and a
//       frequency from the vocabulary
//    4  provenance is consistent: a file nothing fetched claims no fetch time,
//       and anything that may not be redistributed says in words what is
//       forbidden
//    5  every committable entry points at a file that exists
//    6  no orphans, in both directions: every committed data file has an entry
//       and every entry has a file
//    7  NOTHING MARKED committable false IS IN THE COMMITTED TREE. SPEC.md
//       section 2 rule 6. This is the check that keeps a licence promise rather
//       than a data promise, and it is the one whose failure cannot be undone by
//       a later commit
//    8  every committed CSV is LF, utf-8, with a header
//    9  dates are strictly increasing, unique and yyyy-mm-dd
//   10  declared rows, observations, file_rows, first_date and last_date match
//       what the file actually contains
//   11  no series measures zero observations and none is in a failed state
//   12  declared gaps match the file, recomputed at the declared frequency
//   13  values sit inside the bounds their declared unit implies
//   14  the three seed JSON files parse and agree with their manifest entries,
//       and every event and every anchor carries a source_url
//   15  the manual steps are present, well formed, and attached to the series
//       they name
//   16  NO COMMITTED FILE REPRODUCES THE ENERGY INSTITUTE CAPACITY TABLE, by
//       column name anywhere, and by value too on a machine that holds the
//       private table. Check 7's companion: 7 proves the private files are not
//       committed, 16 proves the table is not committed under another name
//
// NOTHING HERE IS ALLOWED TO SKIP. There is no third outcome between pass and
// fail. A check that reports "unrecognised unit, skipping" under a PASS line is
// a check a typo can switch off, and the sibling repository shipped exactly that
// bug: renaming a unit string disarmed its bounds check and every gate stayed
// green. An unrecognised unit is a failure here.

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");

// An optional argument names a manifest to validate instead of the committed
// one. Data files still resolve against the repository root, so this is not a
// way to point the tool at another checkout: it exists so a test can hand it a
// deliberately broken manifest and prove this tool fails on it.
const MANIFEST_PATH = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(ROOT, "data", "manifest.json");

const EXPECTED_SCHEMA_VERSION = 1;

const STATUS_VALUES = new Set(["ok", "stale", "failed"]);
const METHOD_VALUES = new Set(["published", "parsed", "reconstructed", "derived", "seed"]);
const FREQUENCY_VALUES = new Set(["daily", "weekly", "monthly", "annual"]);

const REQUIRED_ENTRY_KEYS = [
  "series", "source", "url", "page_url", "machine_fetched", "fetched_at",
  "checked_at", "rows", "observations", "file_rows", "first_date", "last_date",
  "frequency", "gaps", "provisional_from", "vintage", "method", "committable",
  "licence_note", "status", "note", "file", "unit",
];

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const ISO_STAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;

// The two manual steps scripts/refresh.py records. Named here rather than
// counted, because the failure this catches is one of them quietly disappearing
// from the manifest, and a count of two would not notice a substitution.
const REQUIRED_MANUAL_STEPS = ["momr_unarchived_2026", "dgec_weekly_note_collection"];

const SEED_FILES = {
  "data/seed/events.json": ["events"],
  "data/seed/anchors.json": ["anchors", "sp_global_reference"],
  "data/seed/eia_refinery_fuel_2023.json": ["eia_refinery_fuel_2023"],
};

// --------------------------------------------------------------------------
// Bounds, by column
// --------------------------------------------------------------------------
//
// BY COLUMN, NOT BY THE ENTRY'S UNIT STRING. A cache file here is not one
// quantity: dgec_mbr_monthly.csv carries a margin in $/bbl next to the same
// margin in EUR/t, opec_rotterdam_products_monthly.csv carries seven price
// levels next to a disagreement in the same unit that is a difference rather
// than a level, and the JODI files carry flows next to counts of flagged cells.
// One band per file would be wrong for at least one column of most of them, and
// a band that is wrong is a band somebody eventually widens until it means
// nothing.
//
// The patterns are matched in order and the FIRST match wins, so the specific
// rules sit above the general ones. Every value column of every committed cache
// must match one of them. A numeric column that matches none is a FAILURE, not
// a skip: a new column nobody classified is exactly how an unbounded quantity
// gets into a published series.
//
// These numbers repeat crack/config.py on purpose. This tool exists to disagree
// with the Python when the Python is wrong, so importing them would defeat the
// exercise. When a bound moves in config.py it moves here too, and that pair of
// edits is the point.
//
// BRENT'S FLOOR IS 5.0, NOT THE SPEC'S 10. FRED and EIA both publish 25 real
// prints below 10 $/bbl, seventeen days of the 1998 collapse, seven in February
// 1999, and 2020-04-21 at 9.12. The deviation is argued in full next to the
// constant in src/crack/config.py and is a Gate 1 report item.
const COLUMN_BOUNDS = [
  {
    match: /^(spread_|max_disagreement_|max_respec_gap_|max_revision_)/,
    lo: 0.0, hi: 1000.0,
    what: "a difference between two readings of the same quantity, which has no level",
  },
  {
    match: /^(n_notes|n_issues|n_independent_geometries|n_prints|n_readings|cells|cells_code_\d+)$/,
    lo: 0.0, hi: 1000000.0,
    what: "a count of the documents or cells behind a row, provenance rather than a measurement",
  },
  {
    // The geometry of one note's page 3 chart, and the page the table sat on.
    // They are measurements of a PDF rather than of a market: the number of y
    // axis ticks, the distance between two plotted points in typographic
    // points, and a one based page number. The bands are what a page of A4 can
    // physically hold, so a decode that went wrong by an order of magnitude
    // fails here as well as at its own gates.
    match: /^(geometry_ticks|geometry_pitch_pt|note_page)$/,
    lo: 0.0, hi: 2000.0,
    what: "a measurement of the note PDF's own geometry, not of the market",
  },
  { match: /_kbd$/, lo: 0.0, hi: 100000.0, what: "a flow or a capacity, kb/d" },
  { match: /_capacity_kb_d$/, lo: 0.0, hi: 100000.0, what: "refinery capacity, kb/d" },
  { match: /_usd_mmbtu$/, lo: 0.0, hi: 150.0, what: "gas, $/MMBtu" },
  { match: /^eurusd$/, lo: 0.5, hi: 2.5, what: "US dollars per euro" },
  { match: /_eur_mwh$/, lo: 0.0, hi: 500.0, what: "TTF, EUR/MWh" },
  { match: /^mbr_usd_bbl$/, lo: -50.0, hi: 150.0, what: "a gross refining margin, $/bbl, which can be negative" },
  { match: /^mbr_eur_t$/, lo: -500.0, hi: 2000.0, what: "the same margin in EUR per tonne, which can be negative" },
  { match: /^crack_.*_usd_bbl$/, lo: -30.0, hi: 150.0, what: "a crack, $/bbl" },
  { match: /_usd_bbl$/, lo: 2.0, hi: 400.0, what: "a price level, $/bbl" },
  { match: /_(usd|eur)_t$/, lo: 100.0, hi: 3000.0, what: "a product quotation level, per tonne" },
];

function boundsForColumn(column) {
  for (const candidate of COLUMN_BOUNDS) {
    if (candidate.match.test(column)) return candidate;
  }
  return null;
}

// --------------------------------------------------------------------------
// Reading
// --------------------------------------------------------------------------

function parseCsv(text) {
  const lines = text.split("\n");
  if (lines.length && lines[lines.length - 1] === "") lines.pop();
  if (!lines.length) return { header: [], rows: [] };
  const split = (line) => {
    const cells = [];
    let cell = "";
    let quoted = false;
    for (let i = 0; i < line.length; i += 1) {
      const ch = line[i];
      if (quoted) {
        if (ch === '"') {
          if (line[i + 1] === '"') { cell += '"'; i += 1; } else quoted = false;
        } else cell += ch;
      } else if (ch === '"') quoted = true;
      else if (ch === ",") { cells.push(cell); cell = ""; }
      else cell += ch;
    }
    cells.push(cell);
    return cells;
  };
  const header = split(lines[0]);
  const rows = lines.slice(1).map(split);
  return { header, rows };
}

const fileCache = new Map();

function loadCsv(relative) {
  if (fileCache.has(relative)) return fileCache.get(relative);
  const full = path.join(ROOT, relative);
  let value = null;
  if (existsSync(full)) {
    const raw = readFileSync(full);
    const text = raw.toString("utf8");
    value = { ...parseCsv(text), raw, text };
  }
  fileCache.set(relative, value);
  return value;
}

function readJson(relative) {
  const full = path.join(ROOT, relative);
  if (!existsSync(full)) return null;
  return JSON.parse(readFileSync(full, "utf8"));
}

function listFiles(relativeDir, extension) {
  const full = path.join(ROOT, relativeDir);
  if (!existsSync(full)) return [];
  return readdirSync(full)
    .filter((name) => name.toLowerCase().endsWith(extension))
    .filter((name) => statSync(path.join(full, name)).isFile())
    .map((name) => relativeDir + "/" + name);
}

// --------------------------------------------------------------------------
// Dates and gaps, recomputed
// --------------------------------------------------------------------------

function toUtc(iso) {
  return Date.UTC(
    Number(iso.slice(0, 4)),
    Number(iso.slice(5, 7)) - 1,
    Number(iso.slice(8, 10))
  );
}

function fromUtc(ms) {
  return new Date(ms).toISOString().slice(0, 10);
}

const DAY = 86400000;

// Mirrors crack.sources.base.find_gaps, which documents the rule per frequency.
// daily: every business day in the span, holidays included, because no holiday
// calendar is bundled with this repository and inventing one would turn Good
// Friday into a silent pass. weekly, monthly and annual: every period in the
// span must carry at least one observation, reported at the start of the period.
function findGaps(dates, frequency) {
  if (dates.length < 2) return [];
  if (frequency === "daily") {
    const have = new Set(dates);
    const out = [];
    const last = toUtc(dates[dates.length - 1]);
    for (let ms = toUtc(dates[0]); ms <= last; ms += DAY) {
      const day = new Date(ms).getUTCDay();
      if (day === 0 || day === 6) continue;
      const iso = fromUtc(ms);
      if (!have.has(iso)) out.push(iso);
    }
    return out;
  }
  let anchorOf;
  let step;
  if (frequency === "weekly") {
    anchorOf = (iso) => {
      const ms = toUtc(iso);
      const weekday = (new Date(ms).getUTCDay() + 6) % 7; // Monday is 0
      return fromUtc(ms - weekday * DAY);
    };
    step = (iso) => fromUtc(toUtc(iso) + 7 * DAY);
  } else if (frequency === "monthly") {
    anchorOf = (iso) => iso.slice(0, 7) + "-01";
    step = (iso) => {
      let year = Number(iso.slice(0, 4));
      let month = Number(iso.slice(5, 7)) + 1;
      if (month > 12) { month = 1; year += 1; }
      return year + "-" + String(month).padStart(2, "0") + "-01";
    };
  } else {
    anchorOf = (iso) => iso.slice(0, 4) + "-01-01";
    step = (iso) => Number(iso.slice(0, 4)) + 1 + "-01-01";
  }
  const anchors = new Set(dates.map(anchorOf));
  const sorted = [...anchors].sort();
  const out = [];
  let cursor = sorted[0];
  const end = sorted[sorted.length - 1];
  while (cursor < end) {
    cursor = step(cursor);
    if (cursor <= end && !anchors.has(cursor)) out.push(cursor);
  }
  return out;
}

// The dates of the rows that carry an observation of THIS series, which is what
// the Python side counts and what the gap list is computed from. A row the
// source emitted for a day it published nothing is a row, not an observation.
function observationDates(entry, csv) {
  const dateAt = csv.header.indexOf("date");
  if (dateAt === -1) return null;
  const column = entry.observation_column;
  const valueAt = column ? csv.header.indexOf(column) : -1;
  if (column && valueAt === -1) return null;
  const dates = [];
  for (const row of csv.rows) {
    const iso = (row[dateAt] || "").trim();
    if (!iso) continue;
    if (column && !(row[valueAt] || "").trim()) continue;
    dates.push(iso);
  }
  return dates;
}

// --------------------------------------------------------------------------
// The run
// --------------------------------------------------------------------------

const results = [];

function check(name, fn) {
  let problems = [];
  try {
    problems = fn() || [];
  } catch (err) {
    problems = [err.name + ": " + err.message];
  }
  results.push({ name, problems });
}

if (!existsSync(MANIFEST_PATH)) {
  console.log("FAIL  data/manifest.json exists");
  console.log("      no manifest at " + MANIFEST_PATH);
  console.log("      run: python scripts/refresh.py --offline");
  process.exit(1);
}

let manifest = null;
let entries = [];

check("manifest parses and declares schema_version " + EXPECTED_SCHEMA_VERSION, () => {
  const problems = [];
  manifest = JSON.parse(readFileSync(MANIFEST_PATH, "utf8"));
  if (manifest.schema_version !== EXPECTED_SCHEMA_VERSION) {
    problems.push(
      "schema_version is " + JSON.stringify(manifest.schema_version) +
      ", this tool understands " + EXPECTED_SCHEMA_VERSION
    );
  }
  entries = Array.isArray(manifest.series) ? manifest.series : [];
  if (!Array.isArray(manifest.series)) problems.push("series is not an array");
  if (!entries.length) problems.push("the series list is empty");
  return problems;
});

check("header fields and unique series names", () => {
  const problems = [];
  if (!manifest) return ["manifest did not parse"];
  if (!ISO_STAMP.test(String(manifest.generated_at || ""))) {
    problems.push("generated_at is not yyyy-mm-ddThh:mm:ssZ: " + JSON.stringify(manifest.generated_at));
  }
  const run = manifest.run || {};
  if (!["offline", "online"].includes(run.mode)) {
    problems.push("run.mode is " + JSON.stringify(run.mode) + ", not offline or online");
  }
  for (const key of ["started_at", "finished_at"]) {
    if (!ISO_STAMP.test(String(run[key] || ""))) {
      problems.push("run." + key + " is not a timestamp: " + JSON.stringify(run[key]));
    }
  }
  const seen = new Set();
  for (const entry of entries) {
    if (seen.has(entry.series)) problems.push("series " + entry.series + " appears twice");
    seen.add(entry.series);
  }
  const sorted = entries.map((e) => String(e.series));
  if (sorted.join(" ") !== [...sorted].sort().join(" ")) {
    problems.push("the series list is not sorted by name, so its diff will be noisy");
  }
  return problems;
});

check("every entry carries the required keys and a known status, method and frequency", () => {
  const problems = [];
  for (const entry of entries) {
    const name = entry.series || "an entry with no name";
    for (const key of REQUIRED_ENTRY_KEYS) {
      if (!(key in entry)) problems.push(name + " has no " + key);
    }
    if (!STATUS_VALUES.has(entry.status)) {
      problems.push(name + " status " + JSON.stringify(entry.status) + " is not ok, stale or failed");
    }
    if (!METHOD_VALUES.has(entry.method)) {
      problems.push(name + " method " + JSON.stringify(entry.method) + " is not in the vocabulary");
    }
    if (!FREQUENCY_VALUES.has(entry.frequency)) {
      problems.push(name + " frequency " + JSON.stringify(entry.frequency) + " is not in the vocabulary");
    }
    if (typeof entry.committable !== "boolean") {
      problems.push(name + " committable is " + JSON.stringify(entry.committable) + ", not a boolean");
    }
    if (!Array.isArray(entry.gaps)) problems.push(name + " gaps is not an array");
    for (const key of ["first_date", "last_date"]) {
      if (entry[key] !== null && !ISO_DATE.test(String(entry[key]))) {
        problems.push(name + " " + key + " is not yyyy-mm-dd: " + JSON.stringify(entry[key]));
      }
    }
  }
  return problems;
});

check("provenance is consistent, and what may not be redistributed says so in words", () => {
  const problems = [];
  for (const entry of entries) {
    const name = entry.series;
    if (entry.machine_fetched === false && entry.fetched_at !== null) {
      problems.push(
        name + " declares machine_fetched false and a fetched_at of " +
        JSON.stringify(entry.fetched_at) + ". A file nothing fetched has no fetch time"
      );
    }
    if (entry.machine_fetched === false && !entry.checked_at) {
      problems.push(name + " was never fetched and records no checked_at either, so nothing says when it was last looked at");
    }
    for (const key of ["fetched_at", "checked_at"]) {
      if (entry[key] !== null && entry[key] !== undefined && !ISO_STAMP.test(String(entry[key]))) {
        problems.push(name + " " + key + " is not a timestamp: " + JSON.stringify(entry[key]));
      }
    }
    if (entry.committable === false && !String(entry.licence_note || "").trim()) {
      problems.push(name + " may not be redistributed and carries no licence_note saying what is forbidden");
    }
    if (entry.committable === false && !/not|prohibit|forbid/i.test(String(entry.licence_note || ""))) {
      problems.push(name + " is not committable but its licence_note never says what is not permitted");
    }
    if (!String(entry.page_url || "").startsWith("http")) {
      problems.push(name + " has no linkable page_url, so the provenance panel has nothing to link");
    }
  }
  return problems;
});

check("every committable entry points at a file that exists", () => {
  const problems = [];
  for (const entry of entries) {
    if (entry.committable === false) continue;
    const relative = String(entry.file || "");
    if (!relative) { problems.push(entry.series + " declares no file"); continue; }
    if (!/^data\/(cache|seed)\//.test(relative)) {
      problems.push(entry.series + " is committable but its file is " + relative + ", outside data/cache and data/seed");
    }
    if (!existsSync(path.join(ROOT, relative))) {
      problems.push(entry.series + " points at " + relative + ", which is not on disk");
    }
  }
  return problems;
});

check("no orphans, every committed data file has an entry and every entry a file", () => {
  const problems = [];
  const declared = new Set(entries.map((e) => String(e.file || "")));
  for (const relative of listFiles("data/cache", ".csv")) {
    if (!declared.has(relative)) {
      problems.push(relative + " is committed but no manifest entry claims it");
    }
  }
  for (const relative of listFiles("data/seed", ".json")) {
    if (!declared.has(relative)) {
      problems.push(relative + " is committed but no manifest entry claims it");
    }
  }
  for (const [relative, owners] of Object.entries(SEED_FILES)) {
    for (const owner of owners) {
      if (!entries.some((e) => e.series === owner)) {
        problems.push(relative + " has no manifest entry named " + owner);
      }
    }
  }
  // The registry and the manifest must name the same series. A registered
  // series with no entry is a source somebody wrote down and never built.
  const inManifest = new Set(entries.map((e) => e.series));
  for (const entry of entries) {
    if (!entry.file) problems.push(entry.series + " has no file");
  }
  if (inManifest.size !== entries.length) problems.push("duplicate series names");
  return problems;
});

check("nothing marked committable false is in the committed tree, SPEC.md section 2 rule 6", () => {
  const problems = [];
  const priv = entries.filter((e) => e.committable === false);
  if (!priv.length) {
    problems.push(
      "no entry is marked committable false. Two should be, the Energy Institute " +
      "capacity table and the Yahoo TTF series, so either the manifest is wrong or " +
      "a licence promise was dropped"
    );
  }
  let tracked = null;
  try {
    tracked = new Set(
      execFileSync("git", ["ls-files", "--cached", "--others", "--exclude-standard"], {
        cwd: ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"],
      })
        .split("\n").map((line) => line.trim()).filter(Boolean)
    );
  } catch {
    tracked = null;
  }
  for (const entry of priv) {
    const relative = String(entry.file || "");
    if (!relative.startsWith("data/private/")) {
      problems.push(
        entry.series + " may not be redistributed but its file is " + relative +
        ", which is not under data/private/"
      );
    }
    if (tracked && tracked.has(relative)) {
      problems.push(
        "THE LICENCE PROMISE IS BROKEN: " + relative + " is not redistributable and git " +
        "would commit it. " + entry.licence_note.slice(0, 160)
      );
    }
  }
  if (tracked) {
    for (const relative of tracked) {
      if (relative.startsWith("data/private/")) {
        problems.push("data/private/ must never be committed, and git would commit " + relative);
      }
    }
  } else {
    problems.push(
      "git is not available here, so this tool could not prove the private files are " +
      "outside the commit. That is the one check this repository cannot afford to " +
      "assume, so it fails rather than passes quietly"
    );
  }
  return problems;
});

// SPEC.md non negotiable 6, the other half of check 7. Check 7 proves the
// private FILES are not committed. This proves the private TABLE is not
// committed under another name: the Energy Institute capacity sheet may not be
// reproduced and its S&P sourced rows may not be redistributed, and since Gate 5
// one number derived from it, the five country total, IS committed so that a
// fresh clone can rebuild the study. That is the whole of the permitted
// disclosure and this is where it is held to. See crack.sources.ei's docstring.
check("no committed file reproduces the Energy Institute capacity table", () => {
  const problems = [];
  const WITHHELD = ["be", "de", "fr", "nl", "gb"].map((c) => c + "_capacity_kb_d");
  const PUBLISHED = "nwe5_capacity_kb_d";

  const committedFiles = [];
  const walk = (dir) => {
    for (const name of readdirSync(dir)) {
      if (name === "private") continue;
      const full = path.join(dir, name);
      if (statSync(full).isDirectory()) walk(full);
      else committedFiles.push(full);
    }
  };
  walk(path.join(ROOT, "data"));

  // 1. By name. A per country capacity column is a row of the Review's table and
  //    may not appear in a committed CSV header or a committed JSON key.
  for (const full of committedFiles) {
    const relative = path.relative(ROOT, full).split(path.sep).join("/");
    const text = readFileSync(full, "utf8");
    for (const column of WITHHELD) {
      if (text.includes(column)) {
        problems.push(
          "THE LICENCE PROMISE IS BROKEN: " + relative + " carries " + column +
          ", which is a row of the Energy Institute capacity table. Only " +
          PUBLISHED + ", the five country total, may be published"
        );
      }
    }
  }

  // 2. By value, and only on a machine that has the private table, so this half
  //    is stronger for the owner and absent in CI rather than pretending. Every
  //    per country figure the Review prints, in the spelling the caches write
  //    floats in, must appear in no committed file.
  const privateTable = path.join(ROOT, "data", "private", "ei_refinery_capacity_annual.csv");
  if (existsSync(privateTable)) {
    const lines = readFileSync(privateTable, "utf8").trim().split("\n");
    const header = lines[0].split(",").map((h) => h.trim());
    const withheldIndexes = header
      .map((h, i) => (WITHHELD.includes(h) ? i : -1))
      .filter((i) => i >= 0);
    if (withheldIndexes.length !== WITHHELD.length) {
      problems.push(
        "data/private/ei_refinery_capacity_annual.csv no longer carries all five " +
        "country columns, so this check cannot prove they are withheld"
      );
    }
    // A short integer such as 757 occurs by chance in a file of prices, so only
    // the figures long enough to be a fingerprint are searched for. The rounded
    // ones are covered by the column name half above and by the fact that a
    // reader cannot tell which country a bare 757 belongs to.
    const fingerprints = new Set();
    for (const line of lines.slice(1)) {
      const cells = line.split(",");
      for (const index of withheldIndexes) {
        const cell = (cells[index] || "").trim();
        if (cell.length >= 8) fingerprints.add(cell);
      }
    }
    for (const full of committedFiles) {
      const relative = path.relative(ROOT, full).split(path.sep).join("/");
      const text = readFileSync(full, "utf8");
      for (const value of fingerprints) {
        if (text.includes(value)) {
          problems.push(
            "THE LICENCE PROMISE IS BROKEN: " + relative + " carries " + value +
            ", which is a per country figure from the Energy Institute capacity table"
          );
        }
      }
    }
  }
  return problems;
});

check("every committed CSV is utf-8, LF, with a header", () => {
  const problems = [];
  for (const entry of entries) {
    if (entry.committable === false) continue;
    const relative = String(entry.file || "");
    if (!relative.endsWith(".csv")) continue;
    const csv = loadCsv(relative);
    if (!csv) { problems.push(relative + " is missing"); continue; }
    if (csv.text.includes("\r")) problems.push(relative + " contains a carriage return, it must be LF only");
    if (!csv.header.length || csv.header[0] !== "date") {
      problems.push(relative + " first header cell is " + JSON.stringify(csv.header[0]) + ", expected date");
    }
    if (!csv.rows.length) problems.push(relative + " has a header and no rows");
  }
  return problems;
});

check("dates are yyyy-mm-dd, unique and strictly increasing", () => {
  const problems = [];
  for (const entry of entries) {
    if (entry.committable === false) continue;
    const relative = String(entry.file || "");
    if (!relative.endsWith(".csv")) continue;
    const csv = loadCsv(relative);
    if (!csv) continue;
    const dateAt = csv.header.indexOf("date");
    if (dateAt === -1) { problems.push(relative + " has no date column"); continue; }
    let previous = null;
    const seen = new Set();
    for (let i = 0; i < csv.rows.length; i += 1) {
      const iso = (csv.rows[i][dateAt] || "").trim();
      if (!ISO_DATE.test(iso)) {
        problems.push(relative + " row " + (i + 2) + " date " + JSON.stringify(iso) + " is not yyyy-mm-dd");
        continue;
      }
      if (seen.has(iso)) problems.push(relative + " date " + iso + " appears twice");
      seen.add(iso);
      if (previous !== null && iso <= previous) {
        problems.push(relative + " row " + (i + 2) + ", " + iso + " does not follow " + previous);
      }
      previous = iso;
    }
  }
  return problems;
});

check("declared counts and date ranges match the file", () => {
  const problems = [];
  for (const entry of entries) {
    if (entry.committable === false) continue;
    const relative = String(entry.file || "");
    if (!relative.endsWith(".csv")) continue;
    const csv = loadCsv(relative);
    if (!csv) continue;
    if (csv.rows.length !== entry.file_rows) {
      problems.push(
        entry.series + " declares file_rows " + entry.file_rows + ", the file has " + csv.rows.length
      );
    }
    const dates = observationDates(entry, csv);
    if (dates === null) {
      problems.push(
        entry.series + " declares observation_column " + JSON.stringify(entry.observation_column) +
        ", which is not a column of " + relative
      );
      continue;
    }
    if (dates.length !== entry.observations) {
      problems.push(
        entry.series + " declares " + entry.observations + " observations, the file carries " + dates.length
      );
    }
    if (entry.rows !== entry.observations) {
      problems.push(entry.series + " rows " + entry.rows + " and observations " + entry.observations + " disagree");
    }
    if (dates.length) {
      const first = dates[0];
      const last = dates[dates.length - 1];
      if (first !== entry.first_date) {
        problems.push(entry.series + " declares first_date " + entry.first_date + ", the file starts " + first);
      }
      if (last !== entry.last_date) {
        problems.push(entry.series + " declares last_date " + entry.last_date + ", the file ends " + last);
      }
    }
  }
  return problems;
});

check("no series measures zero observations, and none is failed", () => {
  const problems = [];
  for (const entry of entries) {
    if (!(entry.observations > 0)) {
      problems.push(entry.series + " carries " + entry.observations + " observations");
    }
    if (entry.status === "failed") {
      problems.push(entry.series + " is failed: " + String(entry.note || "").slice(0, 200));
    }
  }
  return problems;
});

check("declared gaps match the file, recomputed at the declared frequency", () => {
  const problems = [];
  for (const entry of entries) {
    if (entry.committable === false) continue;
    const relative = String(entry.file || "");
    if (!relative.endsWith(".csv")) continue;
    const csv = loadCsv(relative);
    if (!csv) continue;
    const dates = observationDates(entry, csv);
    if (!dates) continue;
    const measured = findGaps(dates, entry.frequency);
    const declared = entry.gaps || [];
    if (measured.length !== declared.length) {
      problems.push(
        entry.series + " declares " + declared.length + " gap(s), this tool measured " +
        measured.length + " at frequency " + entry.frequency
      );
      continue;
    }
    for (let i = 0; i < measured.length; i += 1) {
      if (measured[i] !== declared[i]) {
        problems.push(entry.series + " gap " + i + " is " + declared[i] + ", measured " + measured[i]);
        break;
      }
    }
  }
  return problems;
});

check("every numeric column is classified, and its values sit inside its bounds", () => {
  const problems = [];
  for (const entry of entries) {
    if (entry.committable === false) continue;
    const relative = String(entry.file || "");
    if (!relative.endsWith(".csv")) continue;
    const csv = loadCsv(relative);
    if (!csv) continue;
    for (let c = 0; c < csv.header.length; c += 1) {
      const column = csv.header[c];
      if (column === "date") continue;

      // Is this column a measurement at all? A column whose filled cells are
      // all text is provenance, such as a specification label, a list of issue
      // names or a True/False cross check flag, and there is nothing to bound.
      // One numeric cell is enough to make it a measurement, so a mostly text
      // column with a stray number is checked rather than waved through.
      const values = [];
      let textCells = 0;
      for (let r = 0; r < csv.rows.length; r += 1) {
        const cell = (csv.rows[r][c] || "").trim();
        if (!cell) continue;
        const value = Number(cell);
        if (Number.isFinite(value)) values.push({ row: r + 2, cell, value });
        else textCells += 1;
      }
      if (!values.length) continue;
      if (textCells) {
        problems.push(
          relative + " column " + column + " mixes " + values.length + " numeric cell(s) with " +
          textCells + " text cell(s). A column is a measurement or it is provenance, not both"
        );
        continue;
      }

      const bounds = boundsForColumn(column);
      if (bounds === null) {
        problems.push(
          relative + " column " + column + " is numeric and matches no bound in COLUMN_BOUNDS. " +
          "An unclassified numeric column is a failure, not a skip: a validator a new column " +
          "name can switch off is not a validator"
        );
        continue;
      }
      const breaches = values.filter((v) => v.value < bounds.lo || v.value > bounds.hi);
      for (const breach of breaches.slice(0, 3)) {
        problems.push(
          relative + " " + column + " row " + breach.row + " is " + breach.cell + ", outside " +
          bounds.lo + " to " + bounds.hi + " for " + bounds.what
        );
      }
      if (breaches.length > 3) {
        problems.push(relative + " " + column + " has " + breaches.length + " values outside its bounds");
      }
    }
  }
  return problems;
});

check("the seed files parse and agree with their manifest entries", () => {
  const problems = [];

  const events = readJson("data/seed/events.json");
  if (!events) problems.push("data/seed/events.json is missing");
  else {
    const list = events.events || [];
    if (!list.length) problems.push("events.json carries no events");
    const ids = new Set();
    for (const item of list) {
      const name = item.id || "an event with no id";
      if (ids.has(item.id)) problems.push("event " + name + " appears twice");
      ids.add(item.id);
      if (!item.source_url) {
        problems.push("event " + name + " has no source_url. SPEC.md section 6.5: include only what you can cite");
      }
      if (!/^\d{4}-\d{2}(-\d{2})?$/.test(String(item.date))) {
        problems.push("event " + name + " date " + JSON.stringify(item.date) + " is neither yyyy-mm-dd nor yyyy-mm");
      }
      const isDay = /^\d{4}-\d{2}-\d{2}$/.test(String(item.date));
      if (item.date_precision === "day" && !isDay) {
        problems.push("event " + name + " claims day precision on the month " + item.date);
      }
      if (item.date_precision === "month" && isDay) {
        problems.push("event " + name + " claims month precision on the day " + item.date);
      }
      if (!item.url_status) problems.push("event " + name + " does not record what its URL answered");
    }
    const entry = entries.find((e) => e.series === "events");
    if (entry && entry.observations !== list.length) {
      problems.push(
        "the events manifest entry declares " + entry.observations + " observations, the file has " + list.length
      );
    }
  }

  const anchors = readJson("data/seed/anchors.json");
  if (!anchors) problems.push("data/seed/anchors.json is missing");
  else {
    const mbr = ((anchors.anchors || {}).mbr_monthly_usd_bbl || {}).values || [];
    if (mbr.length !== 9) {
      problems.push("anchors.json carries " + mbr.length + " MBR anchors, SPEC.md section 5.5 prints nine");
    }
    for (const item of mbr) {
      if (!item.source_url) problems.push("MBR anchor " + item.key + " has no source_url");
      if (item.reproduces !== true) {
        problems.push(
          "MBR anchor " + item.key + " does not reproduce: printed " + item.printed_value +
          ", measured " + item.measured_rounded_2dp + ". SPEC.md section 10 says Gate 2 must not proceed"
        );
      }
    }
    const products = ((anchors.anchors || {}).july_2026_products_usd_t || {}).values || [];
    for (const item of products) {
      if (!item.source_url) problems.push("product anchor " + item.key + " has no source_url");
      if (!item.status) problems.push("product anchor " + item.key + " does not say whether it is verified");
    }
    const cross = (anchors.anchors || {}).brent_cross_check;
    if (!cross) problems.push("anchors.json carries no brent_cross_check block");
    else {
      if (!Array.isArray(cross.outliers)) problems.push("brent_cross_check.outliers is not a list");
      const share = cross.months_within_tolerance / cross.months_compared;
      if (!(share >= cross.min_pass_share)) {
        problems.push(
          "the Brent cross check passes on " + cross.months_within_tolerance + " of " +
          cross.months_compared + ", under the " + cross.min_pass_share + " bar of SPEC.md section 5.5"
        );
      }
    }
    const references = (anchors.sp_global_reference || {}).references || [];
    if (!references.length) problems.push("anchors.json carries no sp_global_reference block");
    for (const item of references) {
      if (!item.source_url) problems.push("S&P reference " + item.key + " has no source_url");
      if (!item.url_status) problems.push("S&P reference " + item.key + " does not record what its URL answered");
    }
  }

  const fuel = readJson("data/seed/eia_refinery_fuel_2023.json");
  if (!fuel) problems.push("data/seed/eia_refinery_fuel_2023.json is missing");
  else {
    for (const figure of fuel.figures || []) {
      if (!figure.source_url) problems.push("refinery fuel figure " + figure.key + " has no source_url");
      if (typeof figure.value !== "number") problems.push("refinery fuel figure " + figure.key + " has no numeric value");
    }
    const derived = (fuel.derived || {}).gas_intensity_mmbtu_per_bbl;
    if (!(derived > 0.12 && derived < 0.3)) {
      problems.push(
        "the derived gas intensity is " + derived + ", outside the SPEC.md section 4.4 band of 0.12 to 0.30"
      );
    }
  }

  return problems;
});

check("the manual steps are recorded and attached to the series they affect", () => {
  const problems = [];
  const steps = (manifest && manifest.manual_steps) || [];
  if (!Array.isArray(steps) || !steps.length) {
    return ["the manifest records no manual_steps. This project has two and forgetting either one loses data permanently"];
  }
  const byId = new Map(steps.map((s) => [s.id, s]));
  for (const id of REQUIRED_MANUAL_STEPS) {
    if (!byId.has(id)) problems.push("the manual step " + id + " is missing from the manifest");
  }
  for (const step of steps) {
    for (const key of ["id", "what", "why", "cost_if_skipped", "how", "cadence", "series", "status"]) {
      if (!step[key]) problems.push("manual step " + step.id + " has no " + key);
    }
    for (const name of step.series || []) {
      const entry = entries.find((e) => e.series === name);
      if (!entry) { problems.push("manual step " + step.id + " names the unknown series " + name); continue; }
      const attached = entry.manual_step || [];
      if (!attached.some((s) => s.id === step.id)) {
        problems.push(
          "manual step " + step.id + " names " + name + " but that entry does not carry it, " +
          "so a reader of the provenance panel would never see it"
        );
      }
    }
  }
  return problems;
});

// --------------------------------------------------------------------------
// Report
// --------------------------------------------------------------------------

console.log("validate-data.mjs, repo " + ROOT);
console.log("manifest " + path.relative(ROOT, MANIFEST_PATH).split(path.sep).join("/"));
console.log("");

let failed = 0;
for (const result of results) {
  if (result.problems.length) {
    failed += 1;
    console.log("FAIL  " + result.name);
    for (const problem of result.problems.slice(0, 8)) console.log("      " + problem);
    if (result.problems.length > 8) {
      console.log("      and " + (result.problems.length - 8) + " more");
    }
  } else {
    console.log("PASS  " + result.name);
  }
}

console.log("");
if (failed) {
  console.log(
    failed + " of " + results.length + " checks failed. The manifest and the committed data do not agree."
  );
  console.log("Fix the DATA first. Find out what the source actually served and why the file changed.");
  console.log("Only once the file is right, re-record it: python scripts/refresh.py --offline");
  console.log("The offline refresh rewrites the manifest to match the file. It never repairs the file.");
  process.exit(1);
}
console.log(results.length + " of " + results.length + " checks passed, " + entries.length + " series.");
process.exit(0);
