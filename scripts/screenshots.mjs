#!/usr/bin/env node
// Full page screenshots of the site, from its subpath, in headless Chromium.
//
//     python scripts/serve.py --port 8126                          in another shell
//     node scripts/screenshots.mjs
//     node scripts/screenshots.mjs --base https://nathancouturier.github.io/crack-spread-study/
//     node scripts/screenshots.mjs --out assets --browser "C:/Program Files/Google/Chrome/Application/chrome.exe"
//     node scripts/screenshots.mjs --only runs,model   shots whose names start so
//
// SPEC.md section 10: Gate 4 asks for screenshots at desktop and mobile widths
// in both themes, and Gate 5 for screenshots of every view taken from the live
// subpath. This writes one PNG per entry in SHOTS into --out (default assets/),
// each the WHOLE page, every pixel of its height, and prints each file's size in
// pixels and every console error or uncaught exception the page raised, with
// messages from browser extensions left out.
//
// Plain node 22 or later, no npm install. The browser is any Chromium, found by
// tools/browser.mjs: --browser <path>, else the CRACK_BROWSER environment
// variable, else the usual Edge and Chrome install paths. Every run uses a fresh
// profile in the system temp directory, removed at the end, because ES modules
// are cached hard and a reused profile can photograph a module graph that is no
// longer on disk. The theme is set the way a visitor's choice is, through the
// nc-theme key in localStorage, before the page loads.
//
// Exit status 1 if any shot fails or the page logged an error, so a run that
// photographed a broken page does not look like a good one.
//
// TO ADD A VIEW at Gate 5, add an entry to SHOTS: a file name, the hash route,
// the viewport, the theme. `open` is the Now view's open sections; `hash`
// opens any other view by its address.

import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { argValue, launch, openNow, openView } from "../tools/browser.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const argv = process.argv;
const BASE = argValue(argv, "--base") || "http://localhost:8126/crack-spread-study/";
const OUT = path.resolve(ROOT, argValue(argv, "--out") || "assets");

const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 375, height: 812 };
const ALL = "cracks,margin,runs,provenance";

const SHOTS = [
  { name: "now-desktop-light", ...DESKTOP, theme: "light", open: "" },
  { name: "now-desktop-light-open", ...DESKTOP, theme: "light", open: ALL },
  { name: "now-desktop-dark-open", ...DESKTOP, theme: "dark", open: ALL },
  { name: "now-mobile-light", ...MOBILE, theme: "light", open: "" },
  { name: "now-mobile-light-open", ...MOBILE, theme: "light", open: ALL },
  { name: "now-mobile-dark-open", ...MOBILE, theme: "dark", open: ALL },
  // History, docs/design.md Part 8.1: the whole sample, the 2022 range, and the
  // seasonal sub view, at both widths in both themes.
  { name: "history-desktop-light", ...DESKTOP, theme: "light", hash: "#/history" },
  { name: "history-desktop-dark-2022", ...DESKTOP, theme: "dark", hash: "#/history?range=2022" },
  { name: "history-desktop-light-season", ...DESKTOP, theme: "light", hash: "#/history?sub=season" },
  { name: "history-mobile-light", ...MOBILE, theme: "light", hash: "#/history" },
  { name: "history-mobile-dark-season", ...MOBILE, theme: "dark", hash: "#/history?sub=season" },
  // Model, docs/design.md Part 8.2: the latest month, the reconstructed July
  // 2026 and the 2019 average, at both widths in both themes.
  { name: "model-desktop-light", ...DESKTOP, theme: "light", hash: "#/model" },
  { name: "model-desktop-dark-july-2026", ...DESKTOP, theme: "dark", hash: "#/model?preset=july_2026" },
  { name: "model-desktop-light-2019", ...DESKTOP, theme: "light", hash: "#/model?preset=average_2019" },
  { name: "model-mobile-light", ...MOBILE, theme: "light", hash: "#/model" },
  { name: "model-mobile-dark-july-2026", ...MOBILE, theme: "dark", hash: "#/model?preset=july_2026" },
  // Runs and crude demand, docs/design.md Part 8.3: each of the four parts at
  // desktop, two of them at mobile, both themes.
  { name: "runs-desktop-light", ...DESKTOP, theme: "light", hash: "#/runs" },
  { name: "runs-desktop-light-threshold", ...DESKTOP, theme: "light", hash: "#/runs?part=threshold" },
  { name: "runs-desktop-dark-race", ...DESKTOP, theme: "dark", hash: "#/runs?part=race" },
  { name: "runs-desktop-light-break", ...DESKTOP, theme: "light", hash: "#/runs?part=break" },
  { name: "runs-mobile-light-threshold", ...MOBILE, theme: "light", hash: "#/runs?part=threshold" },
  { name: "runs-mobile-dark-race", ...MOBILE, theme: "dark", hash: "#/runs?part=race" },
  // Events, docs/design.md Part 8.4: the list alone, a day dated event with the
  // weekly series and the OPEC gap, the month dated lockdowns, and two at mobile.
  { name: "events-desktop-light", ...DESKTOP, theme: "light", hash: "#/events" },
  { name: "events-desktop-light-strikes-on-iran", ...DESKTOP, theme: "light", hash: "#/events?event=strikes_on_iran_hormuz_2026_02_28" },
  { name: "events-desktop-dark-lockdowns", ...DESKTOP, theme: "dark", hash: "#/events?event=covid_pandemic_and_european_lockdowns_2020_03" },
  { name: "events-mobile-light-invasion", ...MOBILE, theme: "light", hash: "#/events?event=russia_invades_ukraine_2022_02_24" },
  { name: "events-mobile-dark-stock-release", ...MOBILE, theme: "dark", hash: "#/events?event=iea_collective_action_400_mb_2026_03_11" },
  // Method, docs/design.md Part 8.5: the whole document at both widths in both
  // themes, and opened at a section by its address.
  { name: "method-desktop-light", ...DESKTOP, theme: "light", hash: "#/method" },
  { name: "method-desktop-dark", ...DESKTOP, theme: "dark", hash: "#/method" },
  { name: "method-mobile-light-assumptions", ...MOBILE, theme: "light", hash: "#/method?section=assumptions" },
];
const ONLY = (argValue(argv, "--only") || "").split(",").filter(Boolean);

/** Width and height from a PNG's IHDR chunk, to report what was written. */
function pngSize(buffer) {
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) };
}

mkdirSync(OUT, { recursive: true });
const browser = await launch(argv);
console.log("screenshots.mjs, " + BASE + " into " + path.relative(ROOT, OUT) + ", " + browser.executable);
let failed = false;
try {
  const page = await browser.page();
  for (const shot of SHOTS.filter((s) => !ONLY.length || ONLY.some((prefix) => s.name.startsWith(prefix)))) {
    page.errors.length = 0;
    try {
      if (shot.hash) await openView(page, BASE, shot);
      else await openNow(page, BASE, shot);
      const theme = await page.evaluate("document.documentElement.dataset.theme");
      if (theme !== shot.theme) throw new Error("the page is in " + theme + ", not " + shot.theme);
      const { png, height } = await page.screenshotFullPage(shot.width);
      const file = path.join(OUT, shot.name + ".png");
      writeFileSync(file, png);
      const size = pngSize(png);
      const errors = page.errors.filter((m) => !/chrome-extension:\/\//.test(m) && /^(exception|console error|log error)/.test(m));
      console.log("  " + path.relative(ROOT, file) + "  " + size.width + " x " + size.height + " px" + (size.height !== height ? ", PAGE IS " + height + " px TALL" : "") + ", console errors: " + (errors.length ? errors.length : "none"));
      for (const error of errors) console.log("      " + error);
      if (errors.length || size.height !== height) failed = true;
    } catch (error) {
      failed = true;
      console.log("  FAIL  " + shot.name + ": " + error.message);
    }
  }
} finally {
  await browser.close();
}
process.exit(failed ? 1 : 0);
