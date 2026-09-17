#!/usr/bin/env node
// Full page screenshots of the site, from its subpath, in headless Chromium.
//
//     python scripts/serve.py --port 8126                          in another shell
//     node scripts/screenshots.mjs
//     node scripts/screenshots.mjs --base https://nathancouturier.github.io/crack-spread-study/
//     node scripts/screenshots.mjs --out assets --browser "C:/Program Files/Google/Chrome/Application/chrome.exe"
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
];

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
  for (const shot of SHOTS) {
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
