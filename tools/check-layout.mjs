#!/usr/bin/env node
// Measure the rendered Now view in a real browser, and fail on what no grep sees.
//
//     python scripts/serve.py --port 8126            in another shell
//     node tools/check-layout.mjs                    http://localhost:8126/crack-spread-study/
//     node tools/check-layout.mjs --base <url> --browser <path to a Chromium>
//     node tools/check-layout.mjs --only B1,S7       report some checks only
//     node tools/check-layout.mjs --widths 375 --themes light
//
// The Gate 4 audit (docs/self-audit.md, "Self audit, Gate 4") found failures that
// every static validator passed: a manifest table with a 44 px window at 375 px,
// captions clipped inside their own scroll containers, a Source column off screen
// with nothing saying so, focus rings clipped by the section body, an accent rule
// through a label, words set in the figure face. Each is a property of layout,
// so each is measured here, in headless Chromium, at the widths the audit used,
// with every section and both text alternatives open, in both themes.
//
// NOT IN `make gate`. It needs a browser and a running server, and the gate runs
// with neither. Run it by hand after a change to src/ or styles/, and Gate 5's
// workflow can run it against the Pages build. tools/browser.mjs says how the
// browser is found; every run uses a fresh profile, so no cached module is
// measured.
//
// THE CHECKS, named by the audit finding each one holds down
//   B1  a sticky first column takes at most half its scroll box, and none of
//       its cells is taller than about seven lines
//   B2  a table's caption is never clipped by the table's own scroll box
//   S1  every column cut off by a scroll box is named in the caption, and the
//       caption names none that is fully in view; focus on a control inside a
//       scroll box brings the whole focus ring into view
//   S3  the Provenance section holds no engineering log: no recon references,
//       no HTTP codes, no "this machine", no snake_case identifier, no word in
//       capitals that is not a name, no heading repeated as the next sentence,
//       no credit line said twice, French names with their accents
//   S6  no text in a strip figure is crossed by the accent zero rule
//   S7  no focus ring anywhere in an open section is clipped by an ancestor
//   S8  every series the manifest flags provisional says so in its row
//   M1  JetBrains Mono holds no letters
//   M2  a rail label either sits inside its bracket with 8px of line showing
//       at each end, or outside it, never over an end tick
//   M3  where the accent zero rule crosses an interval line, a --bg ring
//       separates them
//   M4  waterfall totals carry no plus sign; the scale sentence is not said to
//       the cent
//   H   History, docs/design.md Part 8.1, at #/history, the 2022 range and the
//       seasonal sub view: no two lane markers overlap or leave the page, no
//       end label runs past its chart or over another, at most one accent dot
//       per product line, every readout says something, no horse race word
//   MV  Model, docs/design.md Part 8.2, at #/model, the July 2026 and the 2019
//       presets: the accent on one figure and one bar, the MBR never a row of
//       the model's chain, "unidentified" where a run cut level would sit and
//       no headroom figure, no slider and no min or max, no field in JetBrains
//       Mono, missing products "Not priced", every bar inside its cell; then TTF
//       doubled in the field moves the margin after gas down with the same bar
//       node (in place) and the MBR unchanged, text in a field prints no NaN,
//       and "Put back" restores the preset
//   P   the page body never scrolls sideways, and the console logs no error
//       and throws no exception (messages from browser extensions excepted)
//   V   the deploy guard, docs: src/crack/versions.py. Every module, stylesheet
//       and artifact the page loaded carries the ?v= hash index.html names; and
//       with data/now.json served under a schema version the page does not read,
//       planted through the DevTools protocol, the view draws no verdict and says
//       which file it refused and to reload. Once, at 1280 px in light.

import { argValue, launch, openNow, openView } from "./browser.mjs";

const argv = process.argv;
const BASE = argValue(argv, "--base") || "http://localhost:8126/crack-spread-study/";
const ONLY = (argValue(argv, "--only") || "").split(",").filter(Boolean);
const WIDTHS = (argValue(argv, "--widths") || "375,768,1024,1280,1440").split(",").map(Number);
const THEMES = (argValue(argv, "--themes") || "light,dark").split(",");
const ALL = "cracks,margin,runs,provenance";
/* The History states measured at every width and theme, Part 8.1. */
const HISTORY = ["#/history", "#/history?range=2022", "#/history?sub=season"];
/* The Model states, Part 8.2. */
const MODEL = ["#/model", "#/model?preset=july_2026", "#/model?preset=average_2019"];
const VIEWS = (argValue(argv, "--views") || "now,history,model").split(",");

/* Everything below PROBE runs inside the page. It returns
 * [{ check, width, theme, problem }]. */
const PROBE = String.raw`(async () => {
  const problems = [];
  const add = (check, problem) => problems.push({ check, problem });
  const frame = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  const RING = 6; // outline 2px at offset 4px, styles/layout.css
  const text = (node) => (node.textContent || "").replace(/\s+/g, " ").trim();

  // Open every text alternative, then let the width observers draw.
  for (const button of document.querySelectorAll('.disclosure__button[aria-expanded="false"]')) button.click();
  await frame();
  await new Promise((r) => setTimeout(r, 300));

  const scrollers = [...document.querySelectorAll(".table-scroll")];
  for (const scroller of scrollers) {
    const table = scroller.querySelector("table");
    if (!table) continue;
    const name = table.className + " " + (text(table.querySelector("th")) || "");
    const box = scroller.getBoundingClientRect();
    scroller.scrollLeft = 0;
    await frame();

    // The caption the reader sees: a caption element, or what aria-labelledby names.
    const labelId = table.getAttribute("aria-labelledby");
    const caption = table.querySelector("caption") || (labelId ? document.getElementById(labelId) : null);
    if (!caption) add("B2", name + ": no caption");
    else {
      const c = caption.getBoundingClientRect();
      if (c.right > box.right + 1 && scroller.contains(caption)) add("B2", name + ": the caption is " + Math.round(c.width) + " px wide inside a " + Math.round(box.width) + " px scroll box, clipped");
      if (c.right > document.documentElement.clientWidth + 1) add("B2", name + ": the caption runs off the page");
    }

    const overflows = scroller.scrollWidth > scroller.clientWidth + 1;
    const firstCells = [...table.querySelectorAll("tr > :first-child")];
    const sticky = firstCells.length && getComputedStyle(firstCells[0]).position === "sticky"
      ? Math.max(...firstCells.map((cell) => cell.getBoundingClientRect().width)) : 0;
    if (overflows && sticky > scroller.clientWidth / 2) {
      add("B1", name + ": sticky first column " + Math.round(sticky) + " px of a " + scroller.clientWidth + " px box");
    }
    // A narrow sticky column must not turn a row into a column of words: no
    // sticky cell taller than 160px, about seven lines.
    if (overflows && sticky) {
      const tallest = Math.max(...firstCells.map((cell) => cell.getBoundingClientRect().height));
      if (tallest > 160) add("B1", name + ": a sticky first column cell is " + Math.round(tallest) + " px tall");
    }

    // S1: which header cells are cut on the right at scrollLeft 0, and does the caption name them.
    const heads = [...table.querySelectorAll("thead tr:last-child th")].filter((th) => th.getBoundingClientRect().width > 0);
    const words = caption ? text(caption).toLowerCase() : "";
    const shortName = (th) => (th.dataset.short || text(th)).toLowerCase();
    const cutRight = heads.filter((th, i) => i > 0 && th.getBoundingClientRect().right > box.right + 1);
    if (cutRight.length) {
      if (!/to the right/.test(words)) add("S1", name + ": " + cutRight.length + " column(s) off screen to the right and the caption does not say so");
      else if (cutRight.length <= 4) {
        for (const th of cutRight) if (!words.includes(shortName(th))) add("S1", name + ": the caption does not name the cut column " + JSON.stringify(shortName(th)));
      }
    } else if (/to the right/.test(words)) {
      add("S1", name + ": the caption says columns are to the right and none is");
    }
    if (overflows) {
      scroller.scrollLeft = scroller.scrollWidth;
      scroller.dispatchEvent(new Event("scroll"));
      await frame();
      await new Promise((r) => setTimeout(r, 50));
      const after = caption ? text(caption).toLowerCase() : "";
      if (/to the right/.test(after)) add("S1", name + ": scrolled to the end, the caption still says columns are to the right");
      scroller.scrollLeft = 0;
      scroller.dispatchEvent(new Event("scroll"));
      await frame();
    }

    // S1: focus inside a scroll box brings the ring into view.
    for (const control of scroller.querySelectorAll("a[href], button")) {
      scroller.scrollLeft = 0;
      await frame();
      control.focus();
      await frame();
      const r = control.getBoundingClientRect();
      const b = scroller.getBoundingClientRect();
      const stickyCell = control.closest("tr") ? control.closest("tr").firstElementChild : null;
      const leftEdge = b.left + (stickyCell && stickyCell !== control.closest("td,th") && getComputedStyle(stickyCell).position === "sticky" ? stickyCell.getBoundingClientRect().width : 0);
      const over = Math.max(r.right + RING - b.right, leftEdge - (r.left - RING), 0);
      if (over > 1) add("S1", name + ": focus on " + JSON.stringify(text(control).slice(0, 40)) + " leaves its ring " + Math.round(over) + " px outside the scroll box");
      control.blur();
    }
    scroller.scrollLeft = 0;
  }

  // S7: focus rings clipped by any ancestor, everywhere in the open sections.
  const focusables = document.querySelector(".sections")
    ? '.section__body[data-open="true"] a[href], .section__body[data-open="true"] button, .section__body[data-open="true"] [tabindex="0"], .section__button'
    : '#view a[href], #view button, #view input, #view [tabindex="0"]';
  for (const control of document.querySelectorAll(focusables)) {
    if (control.disabled) continue;
    if (control.closest(".table-scroll") && control !== control.closest(".table-scroll")) continue; // measured above, after scrolling
    control.scrollIntoView({ block: "center" });
    control.focus();
    await frame();
    const r = control.getBoundingClientRect();
    const ring = { left: r.left - RING, right: r.right + RING, top: r.top - RING, bottom: r.bottom + RING };
    for (let node = control.parentElement; node && node !== document.body; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (style.overflowX === "visible" && style.overflowY === "visible") continue;
      const c = node.getBoundingClientRect();
      const clip = Math.max(c.left - ring.left, ring.right - c.right, c.top - ring.top, ring.bottom - c.bottom);
      if (clip > 0.5) {
        add("S7", "the focus ring of " + JSON.stringify(text(control).slice(0, 40) || control.className) + " is clipped " + clip.toFixed(1) + " px by ." + String(node.className).split(" ")[0]);
        break;
      }
    }
    control.blur();
  }
  window.scrollTo(0, 0);

  // S3: the Provenance prose.
  const provenance = document.querySelector("#section-body-provenance .section__inner");
  if (provenance) {
    const prose = [...provenance.querySelectorAll("p, li, h3, th, td, caption")].map(text).join("\n");
    const bad = [
      [/\brecon \d/i, "an internal recon reference"],
      [/\bHTTP \d{3}\b/, "an HTTP status code"],
      [/this machine/i, "\"this machine\""],
      [/\b[a-z]+_[a-z0-9_]+\b/, "a snake_case identifier"],
      [/ ,/, "a space before a comma"],
      [/python -m|--collect/, "a command line"],
      [/\bat any price, ever\b/, "\"at any price, ever\""],
      [/most interesting period/, "\"the most interesting period\""],
      [/generale de l'energie|ministere|Transition ecologique/, "a French name without its accents"],
    ];
    for (const [pattern, why] of bad) {
      const m = pattern.exec(prose);
      if (m) add("S3", why + ": " + JSON.stringify(prose.slice(Math.max(0, m.index - 30), m.index + 40)));
    }
    const NAMES = new Set(["JODI", "OPEC", "DGEC", "FRED", "MOMR", "NWE", "MBR", "EIA", "ICE", "TTF", "RBRTE", "REUTERS", "DCOILBRENTEU", "DEXUSEU", "USD", "EUR", "CC", "BY", "SIL", "OFL", "UTC", "US", "UK", "BE", "DE", "FR", "NL", "PDF", "PDFS", "MMBTU", "L.P", "IEA", "ARA", "CIF", "FOB", "TBTS", "LOCF", "ISO", "ICIS"]);
    for (const m of prose.matchAll(/\b[A-Z][A-Z]{3,}\b/g)) if (!NAMES.has(m[0])) add("S3", "a word in capitals: " + m[0]);
    for (const heading of provenance.querySelectorAll("h3")) {
      const next = heading.nextElementSibling;
      if (next && text(next).toLowerCase().startsWith(text(heading).toLowerCase().replace(/[.]$/, ""))) add("S3", "the heading " + JSON.stringify(text(heading)) + " is repeated as the next sentence");
    }
    for (const item of provenance.querySelectorAll("li")) {
      const sentences = text(item).split(/(?<=\.)\s+/).map((s) => s.replace(/[.]$/, ""));
      const seen = new Set();
      for (const s of sentences) {
        if (s.length > 12 && seen.has(s)) add("S3", "a credit says the same thing twice: " + JSON.stringify(s));
        seen.add(s);
      }
    }
  }

  // S8: provisional flags in the manifest table, where the Provenance section is.
  if (document.querySelector("#section-body-provenance")) try {
    const manifest = (await (await fetch("data/provenance.json", { cache: "no-cache" })).json()).manifest;
    for (const entry of manifest.series) {
      if (!entry.provisional_from) continue;
      const row = document.querySelector('tr[data-series="' + entry.series + '"]');
      if (!row) add("S8", entry.series + ": no row");
      else if (!/provisional/i.test(text(row))) add("S8", entry.series + " is flagged provisional from " + entry.provisional_from + " and its row does not say so");
    }
  } catch (error) {
    add("S8", "could not read data/provenance.json: " + error.message);
  }

  // S6 and M3: the interval strips.
  const parseInterval = (d) => {
    const m = /M([\d.]+) [\d.]+ V[\d.]+ M[\d.]+ ([\d.]+) H([\d.]+)/.exec(d || "");
    return m ? { x0: +m[1], y: +m[2], x1: +m[3] } : null;
  };
  for (const svg of document.querySelectorAll("svg.chart--strip-figure, svg.chart--strip")) {
    if (!svg.getBoundingClientRect().width) continue;
    const rules = [...svg.querySelectorAll("line.mark-accent-rule")].map((l) => ({ x: +l.getAttribute("x1"), y1: +l.getAttribute("y1"), y2: +l.getAttribute("y2") }));
    for (const label of svg.querySelectorAll("text")) {
      const b = label.getBBox();
      for (const rule of rules) {
        if (rule.x >= b.x && rule.x <= b.x + b.width && Math.max(rule.y1, rule.y2) > b.y && Math.min(rule.y1, rule.y2) < b.y + b.height) {
          add("S6", "the accent zero rule at x " + rule.x.toFixed(1) + " crosses the label " + JSON.stringify(text(label)));
        }
      }
    }
    const rings = [...svg.querySelectorAll(".mark-accent-rule-ring")].map((l) => ({ x: +l.getAttribute("x1"), y1: +l.getAttribute("y1"), y2: +l.getAttribute("y2") }));
    for (const path of svg.querySelectorAll("path.mark-interval")) {
      const iv = parseInterval(path.getAttribute("d"));
      if (!iv) continue;
      for (const rule of rules) {
        if (rule.x > iv.x0 && rule.x < iv.x1 && rule.y1 <= iv.y && rule.y2 >= iv.y) {
          const ringed = rings.some((ring) => Math.abs(ring.x - rule.x) < 0.5 && ring.y1 < iv.y && ring.y2 > iv.y);
          if (!ringed) add("M3", "the accent zero rule crosses an ink interval line at y " + iv.y.toFixed(1) + " with no --bg ring");
        }
      }
    }
  }

  // M1: no letters in JetBrains Mono.
  const walker = document.createTreeWalker(document.getElementById("view"), NodeFilter.SHOW_TEXT);
  const monoWords = new Map();
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const value = node.nodeValue.trim();
    if (!value || !node.parentElement) continue;
    const parent = node.parentElement;
    if (parent.closest("[hidden], .visually-hidden")) continue;
    if (!/JetBrains/.test(getComputedStyle(parent).fontFamily)) continue;
    if (/[A-Za-z]/.test(value)) monoWords.set(value, (monoWords.get(value) || 0) + 1);
  }
  for (const [value, count] of monoWords) add("M1", "words in JetBrains Mono, " + count + " time(s): " + JSON.stringify(value.slice(0, 50)));

  // M2: rail labels against their brackets.
  for (const label of document.querySelectorAll("svg .rail-label")) {
    let bracket = label.previousElementSibling;
    while (bracket && bracket.classList.contains("rail-plate")) bracket = bracket.previousElementSibling;
    if (!bracket || bracket.tagName !== "path") continue;
    const m = /M([\d.]+) ([\d.]+) V([\d.]+) M[\d.]+ [\d.]+ H([\d.]+)/.exec(bracket.getAttribute("d"));
    if (!m) continue;
    const x0 = +m[1];
    const x1 = +m[4];
    const tickTop = +m[2];
    const tickBottom = +m[3];
    const plate = label.previousElementSibling && label.previousElementSibling.classList.contains("rail-plate") ? label.previousElementSibling.getBBox() : null;
    const b = plate || label.getBBox();
    // Inside means at least 8px of bracket line shows between the plate and each
    // end tick: less, and the stubs read as arrow heads (audit point d).
    const inside = b.x > x0 + 8 && b.x + b.width < x1 - 8;
    const outside = b.x + b.width < x0 || b.x > x1 || b.y >= tickBottom || b.y + b.height <= tickTop;
    const clipped = b.x < 0 || b.x + b.width > +label.ownerSVGElement.getAttribute("width") + 0.5 || b.y + b.height > +label.ownerSVGElement.getAttribute("height") + 0.5;
    if (clipped) add("M2", "the rail label " + JSON.stringify(text(label)) + " runs outside its chart");
    if (!inside && !outside) add("M2", "the rail label " + JSON.stringify(text(label)) + " covers an end tick of its bracket (" + x0.toFixed(0) + " to " + x1.toFixed(0) + ", label " + b.x.toFixed(0) + " to " + (b.x + b.width).toFixed(0) + ")");
  }

  // M4: signs and precision in the margin section.
  for (const cell of document.querySelectorAll("#section-body-margin tr.is-total td.num")) if (/^\+/.test(text(cell))) add("M4", "a waterfall total prints a plus sign: " + text(cell));
  const scale = document.querySelector("#section-body-margin .scale-note");
  if (scale && /\.00 to /.test(text(scale))) add("M4", "the scale is said to the cent: " + JSON.stringify(text(scale)));

  // H: the History view, docs/design.md Part 8.1.
  if (document.querySelector(".history-body")) {
    for (const lane of document.querySelectorAll(".lane")) {
      const boxes = [...lane.children].map((node) => ({ text: text(node), box: node.getBoundingClientRect(), row: node.getAttribute("data-row") || "0" }));
      for (let i = 0; i < boxes.length; i += 1) {
        for (let j = i + 1; j < boxes.length; j += 1) {
          const a = boxes[i].box;
          const b = boxes[j].box;
          if (a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom) add("H", "two lane markers overlap: " + JSON.stringify(boxes[i].text) + " and " + JSON.stringify(boxes[j].text));
        }
        if (boxes[i].box.right > document.documentElement.clientWidth + 1 || boxes[i].box.left < -1) add("H", "a lane marker runs off the page: " + JSON.stringify(boxes[i].text));
      }
    }
    for (const svg of document.querySelectorAll("svg.chart--time, svg.chart--profile")) {
      const width = +svg.getAttribute("width");
      for (const label of svg.querySelectorAll(".chart-end-label")) {
        const b = label.getBBox();
        if (b.x + b.width > width + 0.5) add("H", "the end label " + JSON.stringify(text(label)) + " runs past its chart by " + (b.x + b.width - width).toFixed(1) + " px");
      }
      const ends = [...svg.querySelectorAll(".chart-end-label")].map((l) => l.getBBox());
      for (let i = 1; i < ends.length; i += 1) {
        const a = ends[i - 1];
        const b = ends[i];
        if (a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height) add("H", "two end labels overlap");
      }
      if (svg.querySelectorAll(".mark-accent-dot").length > 2) add("H", "more than one accent mark per product on a chart");
    }
    for (const panel of document.querySelectorAll(".history-panel")) {
      const readout = panel.querySelector(".readout");
      if (readout && !text(readout)) add("H", "a readout is empty");
    }
    if (/winner|dead heat|tie/i.test(text(document.getElementById("view")))) add("H", "a banned word about the horse race");
  }

  // MV: the Model view, docs/design.md Part 8.2.
  if (document.querySelector(".calc-layout")) {
    const view = document.getElementById("view");
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    const accents = [...view.querySelectorAll(".text-accent")];
    if (accents.length !== 1) add("MV", accents.length + " accent figures, not one");
    if (view.querySelectorAll('rect.mark-accent-bar:not([display="none"])').length !== 1) add("MV", "not exactly one accent bar");
    if (view.querySelector(".calc-model tr[data-row=official-mbr]")) add("MV", "the ministry's MBR is a row of the model's chain");
    const run = view.querySelector('tr[data-breakeven="run-cut"]');
    if (!run || !/unidentified/.test(text(run))) add("MV", "the run cut row does not say unidentified");
    if (/headroom[^.]*?\d/i.test(text(view))) add("MV", "a figure follows the word headroom");
    if (view.querySelector('input[type=range], input[min], input[max]')) add("MV", "a slider or a min or max attribute");
    for (const input of view.querySelectorAll(".calc-field__input")) {
      if (/JetBrains/.test(getComputedStyle(input).fontFamily)) { add("MV", "a field is set in JetBrains Mono"); break; }
    }
    for (const svg of view.querySelectorAll("svg.chart--live")) {
      const box = svg.getBoundingClientRect();
      for (const mark of svg.querySelectorAll('rect.live-mark:not([display="none"]), circle.live-mark:not([display="none"])')) {
        const b = mark.getBoundingClientRect();
        if (b.left < box.left - 1 || b.right > box.right + 1) add("MV", "a bar runs outside its cell in the row " + svg.closest("tr").getAttribute("data-row"));
      }
    }
    if (/preset=july_2026/.test(location.hash)) {
      for (const id of ["jet", "fuel_oil_1pct"]) {
        const row = view.querySelector('tr[data-row="product:' + id + '"]');
        if (!row || !/Not priced/.test(text(row))) add("MV", "July 2026: " + id + " is not said to be Not priced");
      }
      if (!/reconstructed/.test(text(view.querySelector('.calc-preset[data-preset="july_2026"]')))) add("MV", "the July 2026 preset is not labelled reconstructed");
    }
    const set = (id, value) => {
      const input = document.getElementById(id);
      input.value = value;
      input.dispatchEvent(new Event("input", { bubbles: true }));
    };
    const figure = (row) => text(view.querySelector('tr[data-row="' + row + '"] td.num'));
    const ttf = document.getElementById("calc-ttf_eur_mwh");
    const before = parseFloat(figure("after-gas"));
    const mbr = figure("official-mbr");
    const bar = view.querySelector('tr[data-row="after-gas"] rect.mark-accent-bar');
    set("calc-ttf_eur_mwh", String(parseFloat(ttf.value) * 2));
    await sleep(350);
    const after = parseFloat(figure("after-gas"));
    if (!(after < before)) add("MV", "doubling TTF did not lower the margin after gas: " + before + " then " + after);
    if (view.querySelector('tr[data-row="after-gas"] rect.mark-accent-bar') !== bar) add("MV", "the accent bar was redrawn, not moved in place");
    if (figure("official-mbr") !== mbr) add("MV", "the ministry's MBR moved with TTF");
    set("calc-crack-gasoil", "abc");
    await sleep(50);
    if (/NaN|Infinity|undefined/.test(text(view))) add("MV", "a field holding text printed NaN, Infinity or undefined");
    view.querySelector(".calc-put-back").click();
    await sleep(350);
    if (parseFloat(figure("after-gas")) !== before) add("MV", "Put back did not restore the preset's margin after gas");
  }

  // P: the body never scrolls sideways.
  if (document.documentElement.scrollWidth > document.documentElement.clientWidth) add("P", "the page scrolls sideways, " + document.documentElement.scrollWidth + " in " + document.documentElement.clientWidth);
  return problems;
})()`;

/* V: versioned URLs, then a planted schema mismatch. */
async function deployGuard(page) {
  const problems = [];
  await openNow(page, BASE, { theme: "light", width: 1280, height: 900 });
  const loaded = await page.evaluate("performance.getEntriesByType('resource').map((e) => e.name)");
  const html = await page.evaluate("fetch(location.href.split('#')[0], { cache: 'no-store' }).then((r) => r.text())");
  const own = loaded.filter((url) => /\/(src|styles|data)\/[\w.-]+\.(js|css|json)(\?|$)/.test(url));
  if (!own.some((url) => /\/data\//.test(url))) problems.push("no artifact was loaded, so nothing was measured");
  for (const url of own) {
    const match = /\/((?:src|styles|data)\/[\w.-]+\.(?:js|css|json))(?:\?v=([0-9a-f]+))?$/.exec(url);
    if (!match || !match[2]) problems.push("loaded without a content hash: " + url);
    else if (!html.includes(match[1] + "?v=" + match[2])) problems.push("loaded under a hash index.html does not name: " + url);
  }
  await page.send("Fetch.enable", { patterns: [{ urlPattern: "*data/now.json*" }] });
  page.on("Fetch.requestPaused", async (paused) => {
    const original = await fetch(paused.request.url);
    const body = (await original.text()).replace('"schema_version": 1', '"schema_version": 2');
    await page.send("Fetch.fulfillRequest", {
      requestId: paused.requestId,
      responseCode: 200,
      responseHeaders: [{ name: "Content-Type", value: "application/json; charset=utf-8" }],
      body: Buffer.from(body).toString("base64"),
    });
  });
  await page.reload();
  await page.waitFor("document.querySelector('#view [role=\"alert\"]') || document.querySelector('.verdict')");
  const shown = await page.evaluate("({ verdict: !!document.querySelector('.verdict'), text: document.querySelector('#view').innerText })");
  if (shown.verdict) problems.push("with now.json under an unknown schema version the verdict was still drawn");
  if (!/data\/now\.json/.test(shown.text)) problems.push("the refusal does not name data/now.json: " + JSON.stringify(shown.text.slice(0, 120)));
  if (!/Reload the page/.test(shown.text)) problems.push("the refusal does not say to reload");
  await page.send("Fetch.disable");
  return problems;
}

const browser = await launch(argv);
console.log("check-layout.mjs, " + BASE + ", " + browser.executable);
const found = [];
try {
  const page = await browser.page();
  for (const theme of THEMES) {
    for (const width of WIDTHS) {
      page.errors.length = 0;
      const states = [...(VIEWS.includes("now") ? [null] : []), ...(VIEWS.includes("history") ? HISTORY : []), ...(VIEWS.includes("model") ? MODEL : [])];
      for (const hash of states) {
        page.errors.length = 0;
        if (hash === null) await openNow(page, BASE, { theme, open: ALL, width, height: width < 768 ? 812 : 900 });
        else await openView(page, BASE, { theme, hash, width, height: width < 768 ? 812 : 900 });
        const problems = await page.evaluate(PROBE);
        const where = hash === null ? "" : hash + ": ";
        for (const problem of problems) found.push({ ...problem, problem: where + problem.problem, width, theme });
        for (const message of page.errors) {
          if (/chrome-extension:\/\//.test(message) || !/^(exception|console error|log error)/.test(message)) continue;
          found.push({ check: "P", problem: where + message, width, theme });
        }
      }
    }
  }
  if (!ONLY.length || ONLY.includes("V")) {
    for (const problem of await deployGuard(page)) found.push({ check: "V", problem, width: 1280, theme: "light" });
  }
} finally {
  await browser.close();
}

const selected = ONLY.length ? found.filter((f) => ONLY.includes(f.check)) : found;
const byCheck = new Map();
for (const f of selected) {
  const key = f.check + "  " + f.problem;
  if (!byCheck.has(key)) byCheck.set(key, []);
  byCheck.get(key).push(f.theme + " " + f.width);
}
const checks = ["B1", "B2", "S1", "S3", "S6", "S7", "S8", "M1", "M2", "M3", "M4", "H", "MV", "P", "V"].filter((c) => !ONLY.length || ONLY.includes(c));
for (const check of checks) {
  const lines = [...byCheck.entries()].filter(([key]) => key.startsWith(check + "  "));
  if (!lines.length) {
    console.log("PASS  " + check);
    continue;
  }
  console.log("FAIL  " + check + ", " + lines.length + " distinct problem(s)");
  for (const [key, where] of lines.slice(0, 12)) console.log("        " + key.slice(check.length + 2) + "  [" + where.join(", ") + "]");
  if (lines.length > 12) console.log("        and " + (lines.length - 12) + " more");
}
const failedChecks = checks.filter((c) => [...byCheck.keys()].some((k) => k.startsWith(c + "  ")));
if (failedChecks.length) {
  console.log("FAIL  " + failedChecks.join(", "));
  process.exit(1);
}
console.log("PASS  every layout check, " + WIDTHS.join(", ") + " px, " + THEMES.join(" and "));
