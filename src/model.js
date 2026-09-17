/* model.js
 *
 * The Model view, docs/design.md Part 8.2: the calculator. Four presets, every
 * input editable, a live recompute with the waterfall moving in place, the
 * breakevens in the units a desk quotes.
 *
 * WHAT IT COMPUTES WITH. Nothing of its own. Every figure it prints is a field
 * of src/model-calc.js compute, which calls src/engine.js, the mirror proven to
 * 1e-9, and tools/validate-engine.mjs holds compute to crack.engine for every
 * preset and every named edit. The only arithmetic here is drawing: where a bar
 * starts and ends on the scale, the running position of each step.
 *
 * THE FOUR THINGS THIS VIEW MUST NOT DO, Part 8.2
 *   M1 and M2  subtract gas from the ministry's MBR. The model margin is cracks
 *              times the ministry's yields, GROSS of gas, and gas is subtracted
 *              from that. The MBR, already net of the ministry's own gas, sits in
 *              a separate comparison block and is never a step of the model.
 *   M4         print a headroom. The run cut threshold is unidentified; the
 *              breakevens are taken against a margin of zero, the target the
 *              artifact carries, and the row where a run cut level would sit
 *              says "unidentified".
 *   M6         borrow a neighbour. A product a preset has no price for is an
 *              empty field that says why, a row that says "Not priced", and a
 *              margin that says it covers less of the barrel.
 *   M7         clamp quietly. A field takes any text; what the engine does with
 *              what was typed is said under the form, one sentence a condition.
 *
 * STATE. The preset is in the address, #/model?preset=october_2022. Edits are
 * not: they belong to this reading of the page, and "Put back the preset's
 * figures" returns to the address's state. A field that still shows the text
 * the preset put there computes with the preset's stored value, not with the
 * rounded text, so an untouched preset is exactly the fixture's case.
 *
 * Numeric literals: PERCENT_PER_ONE, declared in tools/check-literals.mjs.
 */

import { el, clear, sentence, appendSegments } from "./dom.js";
import { formatNumber, formatCell, formatQuantity, UNITS } from "./format.js";
import * as charts from "./charts.js";
import * as router from "./router.js";
import { compute, present } from "./model-calc.js";

export const artifacts = Object.freeze(["model"]);

const VIEW = "model";
/* A share of one written as a percent: a unit conversion, for the sentence
 * saying how much of the barrel the margin covers. */
const PERCENT_PER_ONE = 100;

/* The scalar inputs, in the order the form shows them: gas first, so the TTF
 * field sits beside the top of the waterfall. `format` names the artifact's
 * decimals for the text a preset puts in the field. */
const SCALARS = Object.freeze([
  { key: "ttf_eur_mwh", label: "TTF, EUR/MWh", words: "TTF", format: "eur_mwh" },
  { key: "eurusd", label: "EUR/USD, dollars per euro", words: "EUR/USD", format: "eurusd" },
  { key: "gas_intensity_mmbtu_per_bbl", label: "Gas intensity, MMBtu/bbl", words: "gas intensity", format: "mmbtu_per_bbl" },
  { key: "other_variable_cost_usd_bbl", label: "Other variable cost, $/bbl", words: "other variable cost", format: "usd_bbl" },
]);

/* What a field accepts as a number: an optional sign, digits with a point for
 * decimals, an optional exponent. A comma is not a decimal mark here. */
const NUMBER_TEXT = /^[+\-−]?(\d+\.?\d*|\.\d+)([eE][+\-]?\d+)?$/;

let held = null;

/* ------------------------------------------------------------ helpers --- */

function sentenceCase(text) {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

function listWords(words) {
  if (words.length < 1 + 1) return words.join("");
  return words.slice(0, -1).join(", ") + " and " + words[words.length - 1];
}

function presetFrom(route, model) {
  const asked = route && route.params ? route.params.preset : "";
  return model.presets.find((p) => p.id === asked) || model.presets[0];
}

/* The text a preset puts in a field: its stored value at the artifact's
 * decimals, without grouping so it reads back as a number; a yield, which has
 * no declared format, as stored. Empty for a missing value. */
function fieldText(value, format, decimals) {
  if (!present(value)) return "";
  if (!format) return String(value);
  return formatNumber(value, format, decimals, { context: "table" }).replace(/,/g, "");
}

/* What a field holds: { state: "preset" | "number" | "empty" | "text", value }. */
function readField(field) {
  const text = field.input.value.trim();
  if (field.input.value === field.presetText) {
    return { state: "preset", value: present(field.stored) ? field.stored : null };
  }
  if (text === "") return { state: "empty", value: null };
  if (!NUMBER_TEXT.test(text)) return { state: "text", value: null };
  return { state: "number", value: Number(text.replace("−", "-")) };
}

/* ---------------------------------------------------------------- view --- */

export function render(root, data, route) {
  const model = data.model;
  const decimals = model.conventions.decimals;
  held = { model, decimals, root, preset: presetFrom(route, model), fields: new Map(), rows: new Map(), scale: null };

  const title = sentence("h1", model.title_segments, decimals, "view-title");
  title.id = "view-title";
  title.setAttribute("tabindex", "-1");
  root.appendChild(title);
  root.appendChild(sentence("p", model.lead_segments, decimals, "lead calc-lead"));

  const presets = el("div", { class: "choice-row calc-presets", attrs: { role: "group", "aria-label": "Presets" } });
  for (const preset of model.presets) {
    const button = el("button", { class: "choice calc-preset", attrs: { type: "button", "data-preset": preset.id, "aria-pressed": "false" } }, [
      el("span", { class: "calc-preset__label", text: preset.label }),
      preset.reconstructed ? el("span", { class: "calc-preset__status", text: "reconstructed, " + String(preset.weeks.fridays.length) + " weeks, " + (preset.weeks.printed ? String(preset.weeks.printed) : "none") + " printed" }) : null,
    ]);
    button.addEventListener("click", () => {
      router.replaceState(VIEW, { preset: preset.id === model.presets[0].id ? "" : preset.id });
      applyPreset(preset);
    });
    presets.appendChild(button);
  }
  root.appendChild(presets);
  root.appendChild(el("div", { class: "calc-preset-notes", id: "calc-preset-notes" }));

  const layout = el("div", { class: "calc-layout" });
  layout.appendChild(buildForm());
  layout.appendChild(buildResults());
  root.appendChild(layout);

  applyPreset(held.preset);
  return title;
}

export function update(root, route) {
  if (!held) return;
  const preset = presetFrom(route, held.model);
  if (preset.id !== held.preset.id) applyPreset(preset);
}

/* ---------------------------------------------------------------- form --- */

function buildForm() {
  const { model, decimals } = held;
  const form = el("form", { class: "calc-form", attrs: { "aria-label": "The model's inputs", novalidate: "" } });
  form.addEventListener("submit", (event) => event.preventDefault());

  const gas = group("Gas and other costs", "The gas cost is this study's intensity times the gas price in dollars; TTF is converted at the exchange rate.");
  for (const scalar of SCALARS) gas.appendChild(field({ id: scalar.key, label: scalar.label, words: scalar.words, format: scalar.format }));
  // Below 1024px the waterfall is under the whole form, so the result the gas
  // fields move is repeated under them; hidden from assistive technology,
  // which hears the live sentence above the waterfall.
  gas.appendChild(el("p", { class: "calc-summary calc-summary--near", id: "calc-summary-near", attrs: { "aria-hidden": "true" } }));
  form.appendChild(gas);

  const cracks = group("Cracks, $/bbl", "Each crack is the product's price less Brent, in dollars a barrel.");
  for (const product of model.products) {
    cracks.appendChild(field({ id: "crack:" + product.id, label: sentenceCase(product.name) + " crack, $/bbl", words: "the " + product.name + " crack", format: "usd_bbl", product }));
  }
  form.appendChild(cracks);

  const yields = group("Yields, barrels of product per barrel of crude", null);
  yields.appendChild(sentence("p", model.slate.segments, decimals, "calc-group__intro"));
  for (const product of model.products) {
    yields.appendChild(field({ id: "yield:" + product.id, label: sentenceCase(product.name) + " yield, share of the barrel", words: "the " + product.name + " yield", format: null, product }));
  }
  form.appendChild(yields);

  const putBack = el("button", { class: "disclosure__button calc-put-back", text: "Put back the preset's figures", attrs: { type: "button" } });
  putBack.addEventListener("click", () => applyPreset(held.preset));
  form.appendChild(el("div", { class: "calc-put-back-row" }, [putBack]));
  return form;
}

function group(heading, intro) {
  const node = el("fieldset", { class: "calc-group" }, [el("legend", { class: "calc-group__heading", text: heading })]);
  if (intro) node.appendChild(el("p", { class: "calc-group__intro", text: intro }));
  return node;
}

function field({ id, label, words, format, product }) {
  const inputId = "calc-" + id.replace(":", "-");
  const input = el("input", {
    class: "calc-field__input",
    id: inputId,
    attrs: { type: "text", inputmode: "decimal", autocomplete: "off", spellcheck: "false", "aria-describedby": inputId + "-source " + inputId + "-note" },
  });
  const source = el("p", { class: "calc-field__source", id: inputId + "-source" });
  const note = el("p", { class: "calc-field__note", id: inputId + "-note" });
  const record = { id, label, words, format, product, input, source, note, stored: null, presetText: "" };
  input.addEventListener("input", () => recompute(false));
  held.fields.set(id, record);
  return el("div", { class: "calc-field" }, [el("label", { class: "calc-field__label", text: label, attrs: { for: inputId } }), input, source, note]);
}

function applyPreset(preset) {
  const { model, decimals } = held;
  held.preset = preset;
  held.scale = [preset.scale.low_usd_bbl, preset.scale.high_usd_bbl];

  for (const button of held.root.querySelectorAll(".calc-preset")) {
    button.setAttribute("aria-pressed", button.getAttribute("data-preset") === preset.id ? "true" : "false");
  }

  const notes = held.root.querySelector("#calc-preset-notes");
  clear(notes);
  const reason = sentence("p", preset.reason_segments, decimals, "calc-reason");
  if (preset.reason_source_url) {
    reason.appendChild(document.createTextNode(" "));
    reason.appendChild(el("a", { class: "text-link", text: "Source", attrs: { href: preset.reason_source_url, rel: "noopener" } }));
  }
  notes.appendChild(reason);
  notes.appendChild(sentence("p", preset.note_segments, decimals, "calc-note"));

  const inputs = preset.inputs;
  for (const scalar of SCALARS) {
    const f = held.fields.get(scalar.key);
    setStored(f, inputs[scalar.key]);
    clear(f.source);
    const segments = {
      ttf_eur_mwh: preset.sources.ttf_segments,
      eurusd: preset.sources.eurusd_segments,
      gas_intensity_mmbtu_per_bbl: model.intensity.source_segments,
      other_variable_cost_usd_bbl: model.other_cost.source_segments,
    }[scalar.key];
    appendSegments(f.source, segments, decimals);
  }
  for (const product of model.products) {
    const c = held.fields.get("crack:" + product.id);
    setStored(c, inputs.cracks[product.id]);
    clear(c.source);
    const crackSource = preset.sources.cracks[product.id];
    appendSegments(c.source, crackSource.segments, decimals);
    c.source.classList.toggle("is-unavailable", crackSource.available === false);

    const y = held.fields.get("yield:" + product.id);
    setStored(y, inputs.yields[product.id]);
    clear(y.source);
    appendSegments(y.source, product.yield_source_segments, decimals);
  }

  const official = held.rows.get("official-mbr");
  clear(official.line);
  appendSegments(official.line, preset.official.label_segments, decimals);
  const gap = held.rows.get("official-gap");
  clear(gap.detail);
  appendSegments(gap.detail, preset.official.gap_segments, decimals);

  recompute(true);
}

function setStored(f, value) {
  f.stored = present(value) ? value : null;
  f.presetText = fieldText(value, f.format, held.decimals);
  f.input.value = f.presetText;
}

/* ------------------------------------------------------------- results --- */

function buildResults() {
  const results = el("div", { class: "calc-results" });

  results.appendChild(el("p", { class: "calc-summary", id: "calc-summary", attrs: { "aria-live": "polite" } }));
  results.appendChild(el("div", { class: "calc-conditions", id: "calc-conditions" }));
  results.appendChild(el("p", { class: "scale-note calc-scale", id: "calc-scale" }));

  const chain = [];
  for (const product of held.model.products) chain.push({ id: "product:" + product.id, kind: "step", name: sentenceCase(product.name) });
  chain.push({ id: "gross", kind: "total", name: "Gross margin of this model, before gas" });
  chain.push({ id: "gas", kind: "step", name: "Gas at this study's intensity" });
  chain.push({ id: "other", kind: "step", name: "Other variable cost" });
  chain.push({ id: "after-gas", kind: "total", name: "Margin after gas of this model", accent: true });
  results.appendChild(waterfall("calc-model", "The model's margin, line by line, in " + UNITS.usd_bbl + ": each crack times the ministry's yield, the gross margin they add up to, less gas and other variable cost. Gross of gas until the gas line, so the gas line is subtracted once.", chain));

  results.appendChild(el("h2", { class: "calc-heading", text: "Beside the model, not part of it: the ministry's MBR" }));
  results.appendChild(el("p", { class: "calc-intro", text: "The MBR is already net of the ministry's own gas allowance, so nothing is subtracted from it here. The line between the two is the gap, recomputed as the cracks and yields change." }));
  results.appendChild(waterfall("calc-official", "The ministry's MBR for the preset's period against this model's gross margin, in " + UNITS.usd_bbl + ". A comparison, not a step of the model.", [
    { id: "official-gross", kind: "total", name: "Gross margin of this model, before gas" },
    { id: "official-gap", kind: "step", name: "The ministry's MBR less this gross margin" },
    { id: "official-mbr", kind: "total", name: "" },
  ]));

  results.appendChild(el("h2", { class: "calc-heading", text: "Breakevens, against a margin of zero" }));
  results.appendChild(sentence("p", held.model.breakeven_target.segments, held.decimals, "calc-intro"));
  results.appendChild(breakevenTable());
  results.appendChild(sentence("p", held.model.run.segments, held.decimals, "calc-intro calc-run"));
  return results;
}

function waterfall(className, caption, chain) {
  const body = el("tbody", { attrs: { role: "rowgroup" } });
  const table = el("table", { class: "table waterfall calc-waterfall " + className, attrs: { role: "table" } }, [
    el("caption", { text: caption }),
    el("thead", { attrs: { role: "rowgroup" } }, [
      el("tr", { attrs: { role: "row" } }, [
        el("th", { text: "Line", attrs: { scope: "col", role: "columnheader" } }),
        el("th", { class: "waterfall__bar-head", attrs: { scope: "col", role: "columnheader" } }, [el("span", { class: "visually-hidden", text: "Bar from the running total" })]),
        el("th", { class: "col-num", text: UNITS.usd_bbl, attrs: { scope: "col", role: "columnheader" } }),
      ]),
    ]),
    body,
  ]);
  chain.forEach((item, index) => {
    const line = el("span", { class: "waterfall__line", text: item.name });
    const detail = el("span", { class: "waterfall__detail" });
    const nameCell = el("th", { class: "waterfall__name", attrs: { scope: "row", role: "rowheader" } }, [line, detail]);
    const bar = charts.liveWaterfallBar();
    const word = el("span", { class: "calc-bar-word" });
    const barCell = el("td", { class: "waterfall__bar", attrs: { role: "cell" } }, [bar.svg, word]);
    const figure = el("td", { class: "num", attrs: { role: "cell" } });
    const tr = el("tr", { class: item.kind === "total" ? "waterfall__row is-total" : "waterfall__row", attrs: { role: "row", "data-row": item.id } }, [nameCell, barCell, figure]);
    body.appendChild(tr);
    held.rows.set(item.id, { ...item, line, detail, bar, barCell, word, figure, chain: className, index, isLast: index === chain.length - 1, geometry: null });
  });
  const redraw = () => drawBars(true);
  if (typeof ResizeObserver === "function") new ResizeObserver(redraw).observe(table);
  else window.addEventListener("resize", redraw, { passive: true });
  return el("div", { class: "block calc-block" }, [table]);
}

function breakevenTable() {
  const rows = [
    { id: "ttf", name: "TTF", unit: UNITS.eur_mwh },
    { id: "gas", name: "Gas price", unit: UNITS.usd_mmbtu },
    { id: "gasoil", name: "Gasoil crack", unit: UNITS.usd_bbl },
    { id: "run-cut", name: "The level at which runs get cut", unit: "" },
  ];
  const body = el("tbody");
  for (const row of rows) {
    const detail = el("span", { class: "calc-breakeven__detail" });
    const figure = el("td", { class: "num" });
    body.appendChild(el("tr", { attrs: { "data-breakeven": row.id } }, [
      el("th", { class: "calc-breakeven__name", attrs: { scope: "row" } }, [el("span", { class: "calc-breakeven__line", text: row.name }), detail]),
      figure,
      el("td", { class: "calc-breakeven__unit", text: row.unit }),
    ]));
    held.rows.set("breakeven:" + row.id, { detail, figure });
  }
  const table = el("table", { class: "table calc-breakevens" }, [
    el("caption", { text: "The breakevens, in the units a desk quotes them in." }),
    el("thead", {}, [el("tr", {}, [
      el("th", { text: "Input", attrs: { scope: "col" } }),
      el("th", { class: "col-num", text: "At a margin of zero", attrs: { scope: "col" } }),
      el("th", { text: "Unit", attrs: { scope: "col" } }),
    ])]),
    body,
  ]);
  return el("div", { class: "block calc-block" }, [table]);
}

/* ----------------------------------------------------------- recompute --- */

function recompute(fromPreset) {
  const { model, preset, decimals } = held;
  const order = model.products.map((p) => p.id);
  const reads = new Map();
  for (const [id, f] of held.fields) reads.set(id, readField(f));

  const values = { cracks: {}, yields: {}, mbr_usd_bbl: preset.official.mbr_usd_bbl };
  for (const scalar of SCALARS) values[scalar.key] = reads.get(scalar.key).value;
  for (const id of order) {
    values.cracks[id] = reads.get("crack:" + id).value;
    values.yields[id] = reads.get("yield:" + id).value;
  }
  const result = compute(values, model.breakeven_target.value_usd_bbl, order);
  held.result = result;

  fieldNotes(reads);
  conditions(reads, values, result);
  modelRows(values, result);
  officialRows(result);
  breakevens(values, result);
  summary(result);
  widenScale(fromPreset);
  drawBars(fromPreset);
}

function fieldNotes(reads) {
  const { decimals } = held;
  for (const [id, f] of held.fields) {
    const read = reads.get(id);
    let words = "";
    if (read.state !== "preset") {
      const was = f.stored === null ? "no figure" : fieldText(f.stored, f.format, decimals);
      if (read.state === "text") words = "Not a number, so treated as missing, not as zero. The preset holds " + was + ".";
      else if (read.state === "empty") words = "Empty, so treated as missing, not as zero. The preset holds " + was + ".";
      else words = "Edited here. The preset holds " + was + ".";
    }
    if (f.note.textContent !== words) f.note.textContent = words;
    f.input.setAttribute("aria-invalid", read.state === "text" ? "true" : "false");
    f.input.classList.toggle("is-edited", read.state !== "preset");
  }
}

/* What the engine did with what was typed, one sentence a condition. M7. */
function conditions(reads, values, result) {
  const { model, decimals } = held;
  const box = held.root.querySelector("#calc-conditions");
  const lines = [];
  const labelOf = (id) => held.fields.get(id).label;

  const notNumbers = [...reads.entries()].filter(([, r]) => r.state === "text").map(([id]) => labelOf(id));
  if (notNumbers.length) lines.push(["The " + listWords(notNumbers) + (notNumbers.length === 1 ? " field holds" : " fields hold") + " text that is not a number, so the engine is given nothing there, never a zero. Use a point for decimals."]);

  if (result.excluded.length) {
    const names = result.excluded.map((id) => model.products.find((p) => p.id === id).name);
    const covered = present(result.coveredVolumeYield)
      ? ["; the margin prices ", figure(result.coveredVolumeYield * PERCENT_PER_ONE, "percent", "covered_volume_yield_percent"), " percent of the barrel, against ", figure(model.slate.covered_volume_yield * PERCENT_PER_ONE, "percent", "slate_covered_volume_yield_percent"), " percent for all five products"]
      : [];
    lines.push([sentenceCase(listWords(names)) + (names.length === 1 ? " has" : " have") + " no crack or no yield, so " + (names.length === 1 ? "it is" : "they are") + " left out of the margin rather than priced at zero", ...covered, "."]);
  }
  if (result.blockedBy.length) {
    const words = result.blockedBy.map((key) => SCALARS.find((s) => s.key === key).words);
    lines.push(["The margin after gas and the breakevens are not computed: " + listWords(words) + (words.length === 1 ? " is" : " are") + " missing, and a missing input is never taken as zero."]);
  }
  if (present(result.yieldTotal) && result.yieldTotal > 1) {
    lines.push(["The yields add up to ", figure(result.yieldTotal * PERCENT_PER_ONE, "yield_percent", "yield_total_percent"), " percent of the barrel, more than a barrel holds. The engine multiplies each crack by its yield as entered and rescales nothing, so the margin is bigger than any barrel could give."]);
  }
  const negativeYields = model.products.filter((p) => present(values.yields[p.id]) && values.yields[p.id] < 0).map((p) => p.name);
  if (negativeYields.length) lines.push(["A negative yield for " + listWords(negativeYields) + " is taken as entered: that crack is subtracted from the margin instead of added."]);
  const intensity = values.gas_intensity_mmbtu_per_bbl;
  if (present(intensity) && intensity < 0) lines.push(["The gas intensity is negative, so the engine adds the gas cost to the margin instead of subtracting it, and a higher TTF raises the margin."]);
  if (present(intensity) && intensity === 0) lines.push(["At a gas intensity of zero no gas price moves this margin, so neither gas breakeven exists."]);
  if (present(values.ttf_eur_mwh) && values.ttf_eur_mwh < 0) lines.push(["TTF is negative, and the engine prices gas below zero as entered."]);
  if (present(values.eurusd) && values.eurusd <= 0) lines.push([values.eurusd === 0 ? "At an exchange rate of zero TTF converts to gas that costs nothing, and no TTF breakeven exists." : "The exchange rate is negative, so TTF converts to a negative gas price, as entered."]);
  if (present(values.other_variable_cost_usd_bbl) && values.other_variable_cost_usd_bbl < 0) lines.push(["Other variable cost is negative, so the engine adds it to the margin."]);

  const edited = [...reads.values()].filter((r) => r.state !== "preset").length;
  if (edited) lines.push([String(edited) + (edited === 1 ? " input differs" : " inputs differ") + " from the preset " + held.preset.label + "; each says what the preset holds."]);

  clear(box);
  if (!lines.length) {
    box.appendChild(el("p", { class: "calc-condition", text: "Every input is the preset's, as the artifact holds it." }));
    return;
  }
  for (const parts of lines) box.appendChild(el("p", { class: "calc-condition" }, parts));
}

/* A figure in a sentence, as a span with its field, or the words for a gap. */
function figure(value, format, field) {
  const text = formatNumber(value, format, held.decimals, { context: "prose" });
  return el("span", { class: text === null ? "fig is-missing" : "fig", text: text === null ? "no figure" : text, attrs: { "data-field": field } });
}

function setFigure(cell, value, field, options) {
  const opts = options || {};
  const text = formatCell(value, "usd_bbl", held.decimals, opts.signed === true);
  const missing = text === null;
  cell.textContent = missing ? opts.missingWord || "no figure" : text;
  cell.className = ["num", missing ? "is-missing" : "", opts.total ? "num--total" : "", !missing && opts.accent ? "text-accent" : ""].filter(Boolean).join(" ");
  if (missing) cell.removeAttribute("data-field");
  else cell.setAttribute("data-field", field);
}

function setWord(row, words) {
  if (row.word.textContent !== words) row.word.textContent = words;
  row.barCell.classList.toggle("has-word", words !== "");
}

function setDetail(row, parts) {
  clear(row.detail);
  for (const part of parts) row.detail.appendChild(typeof part === "string" ? document.createTextNode(part) : part);
}

function modelRows(values, result) {
  const { model } = held;
  let running = 0;
  let previous = null;
  for (const product of model.products) {
    const row = held.rows.get("product:" + product.id);
    const included = result.included.includes(product.id);
    if (included) {
      const value = result.contributions[product.id];
      row.geometry = { kind: "step", start_usd_bbl: running, end_usd_bbl: running + value };
      running += value;
      setFigure(row.figure, value, "contribution_" + product.id, { signed: true });
      setWord(row, "");
      setDetail(row, [product.ministry_label + ": the crack times the ministry's yield."]);
    } else {
      row.geometry = null;
      setFigure(row.figure, null, "", { missingWord: "no figure" });
      setWord(row, "Not priced");
      const why = !present(values.cracks[product.id]) ? "no crack" : "no yield";
      setDetail(row, [product.ministry_label + ": " + why + ", so left out of the margin, not priced at zero."]);
    }
    row.previous = previous;
    if (row.geometry) previous = row.geometry;
  }

  const gross = held.rows.get("gross");
  gross.geometry = { kind: "total", start_usd_bbl: 0, end_usd_bbl: result.grossMarginUsdBbl };
  gross.previous = previous;
  setFigure(gross.figure, result.grossMarginUsdBbl, "gross_margin_usd_bbl", { total: true });
  setDetail(gross, [String(result.included.length) + " of " + String(model.products.length) + " products priced; gross of gas, not the ministry's MBR."]);

  const gas = held.rows.get("gas");
  const other = held.rows.get("other");
  const after = held.rows.get("after-gas");
  const blocked = result.blockedBy.length > 0;
  if (blocked) {
    const words = listWords(result.blockedBy.map((key) => SCALARS.find((s) => s.key === key).words));
    for (const row of [gas, other, after]) {
      row.geometry = null;
      row.previous = null;
      setWord(row, "Not computed");
      setFigure(row.figure, null, "", { total: row.kind === "total" });
      setDetail(row, ["Not computed: " + words + " missing."]);
    }
    return;
  }
  // Where the gas bar ends on the scale, for drawing only; the figures printed
  // are the engine's gas cost and margin after gas.
  const afterGasCost = result.grossMarginUsdBbl - result.gasCostUsdBbl;
  gas.geometry = { kind: "step", start_usd_bbl: result.grossMarginUsdBbl, end_usd_bbl: afterGasCost };
  gas.previous = gross.geometry;
  setWord(gas, "");
  setFigure(gas.figure, negate(result.gasCostUsdBbl), "gas_cost_usd_bbl", { signed: true });
  setDetail(gas, [
    figure(values.gas_intensity_mmbtu_per_bbl, "mmbtu_per_bbl", "gas_intensity_mmbtu_per_bbl"), " MMBtu/bbl at ",
    figure(result.gasUsdMmbtu, "usd_mmbtu", "gas_usd_mmbtu"), " $/MMBtu, which is TTF at ",
    figure(values.ttf_eur_mwh, "eur_mwh", "ttf_eur_mwh"), " EUR/MWh and ",
    figure(values.eurusd, "eurusd", "eurusd"), " dollars per euro. Subtracted once, from a margin that holds no gas.",
  ]);

  other.geometry = { kind: "step", start_usd_bbl: afterGasCost, end_usd_bbl: result.marginAfterGasUsdBbl };
  other.previous = gas.geometry;
  setWord(other, "");
  setFigure(other.figure, negate(result.otherVariableCostUsdBbl), "other_variable_cost_usd_bbl", { signed: true });
  setDetail(other, [held.fields.get("other_variable_cost_usd_bbl").input.value === held.fields.get("other_variable_cost_usd_bbl").presetText ? "As the preset holds it: carbon and costs other than energy are out of scope." : "As entered."]);

  after.geometry = { kind: "total", start_usd_bbl: 0, end_usd_bbl: result.marginAfterGasUsdBbl, accent: true };
  after.previous = other.geometry;
  setWord(after, "");
  setFigure(after.figure, result.marginAfterGasUsdBbl, "margin_after_gas_usd_bbl", { total: true, accent: true });
  setDetail(after, ["This model's margin, not the ministry's; its distance to a margin of zero is this figure."]);
}

/* A deduction printed as the signed step it is. Presentation, not a formula:
 * the engine's gas cost is a cost, and a waterfall prints it below zero. */
function negate(value) {
  return present(value) ? -value : value;
}

function officialRows(result) {
  const mbr = held.preset.official.mbr_usd_bbl;
  const gross = held.rows.get("official-gross");
  gross.geometry = { kind: "total", start_usd_bbl: 0, end_usd_bbl: result.grossMarginUsdBbl };
  gross.previous = null;
  setFigure(gross.figure, result.grossMarginUsdBbl, "gross_margin_usd_bbl", { total: true });
  setDetail(gross, ["The same line as above, the start of the comparison."]);

  const gap = held.rows.get("official-gap");
  const official = held.rows.get("official-mbr");
  if (!present(mbr)) {
    for (const row of [gap, official]) {
      row.geometry = null;
      setWord(row, "No MBR");
      setFigure(row.figure, null, "");
    }
    return;
  }
  gap.geometry = present(result.residualUsdBbl) ? { kind: "step", start_usd_bbl: result.grossMarginUsdBbl, end_usd_bbl: mbr } : null;
  gap.previous = gross.geometry;
  setWord(gap, "");
  setFigure(gap.figure, result.residualUsdBbl, "residual_usd_bbl", { signed: true });

  official.geometry = { kind: "total", start_usd_bbl: 0, end_usd_bbl: mbr };
  official.previous = gap.geometry;
  setWord(official, "");
  setFigure(official.figure, mbr, "mbr_usd_bbl", { total: true });
}

function breakevens(values, result) {
  const blocked = result.blockedBy.length > 0;
  const blockedWords = "Not computed: " + listWords(result.blockedBy.map((key) => SCALARS.find((s) => s.key === key).words)) + " missing.";
  const intensityZero = present(values.gas_intensity_mmbtu_per_bbl) && values.gas_intensity_mmbtu_per_bbl === 0;

  const put = (id, value, format, field, why) => {
    const row = held.rows.get("breakeven:" + id);
    const text = formatCell(value, format, held.decimals, false);
    row.figure.textContent = text === null ? "no figure" : text;
    row.figure.className = text === null ? "num is-missing" : "num";
    if (text === null) row.figure.removeAttribute("data-field");
    else row.figure.setAttribute("data-field", field);
    row.detail.textContent = text === null ? why : "";
  };

  const ttfWhy = blocked ? blockedWords
    : intensityZero ? "None: at a gas intensity of zero no gas price moves this margin."
    : "None: at an exchange rate of zero no TTF moves this margin.";
  put("ttf", result.breakevenTtfEurMwh, "eur_mwh", "breakeven_ttf_eur_mwh", ttfWhy);
  put("gas", result.breakevenGasUsdMmbtu, "usd_mmbtu", "breakeven_gas_usd_mmbtu", blocked ? blockedWords : "None: at a gas intensity of zero no gas price moves this margin.");
  const gasoilWhy = blocked ? blockedWords
    : !result.included.includes("gasoil") ? "None: gasoil is not in this margin."
    : "None: at a gasoil yield of zero no gasoil crack moves this margin.";
  put("gasoil", result.breakevenGasoilUsdBbl, "usd_bbl", "breakeven_gasoil_usd_bbl", gasoilWhy);

  const run = held.rows.get("breakeven:run-cut");
  run.figure.textContent = held.model.run.verdict;
  run.figure.className = "calc-verdict";
  run.detail.textContent = "No breakeven is taken against it, and no headroom is printed.";
}

function summary(result) {
  const near = held.root.querySelector("#calc-summary-near");
  summaryInto(held.root.querySelector("#calc-summary"), result);
  if (near) summaryInto(near, result);
}

function summaryInto(box, result) {
  clear(box);
  if (!present(result.marginAfterGasUsdBbl)) {
    box.appendChild(document.createTextNode("Margin after gas of this model: not computed, because an input it needs is missing. Headroom to a run cut level: unidentified."));
    return;
  }
  const value = result.marginAfterGasUsdBbl;
  const where = value > 0 ? "above" : value < 0 ? "below" : "at";
  box.appendChild(document.createTextNode("Margin after gas of this model: "));
  box.appendChild(el("span", { class: "fig calc-summary__figure", text: formatQuantity(value, "usd_bbl", held.decimals, { context: "prose" }), attrs: { "data-field": "margin_after_gas_usd_bbl" } }));
  box.appendChild(document.createTextNode(", " + (where === "at" ? "at" : "that far " + where) + " a margin of zero. Headroom to a run cut level: unidentified."));
}

/* M10: the preset's scale, widened to the next round figure when an edit runs
 * past it, and never narrowed while editing. */
function widenScale(fromPreset) {
  const ends = [];
  for (const row of held.rows.values()) {
    if (!row.geometry) continue;
    ends.push(row.geometry.start_usd_bbl, row.geometry.end_usd_bbl);
  }
  let [low, high] = held.scale;
  for (const value of ends.filter(present)) {
    if (value > high) high = charts.ladderCeil(value);
    if (value < low) low = negate(charts.ladderCeil(negate(value)));
  }
  held.scale = [low, high];
  const note = held.root.querySelector("#calc-scale");
  const lowText = formatNumber(low, "count", held.decimals, { context: "prose" });
  const highText = formatNumber(high, "count", held.decimals, { context: "prose" });
  const preset = held.preset.scale;
  const widened = low !== preset.low_usd_bbl || high !== preset.high_usd_bbl;
  note.textContent = "Bars on a scale from " + lowText + " to " + highText + " " + UNITS.usd_bbl + (widened
    ? ", widened past the preset's because an edit ran beyond it; it is not narrowed again until a preset is chosen."
    : ", the preset's; it widens if an edit runs past it.");
}

function drawBars(still) {
  if (!held) return;
  for (const row of held.rows.values()) {
    if (!row.bar) continue;
    const width = row.barCell.clientWidth;
    const height = row.barCell.clientHeight;
    if (width === 0 || height === 0) continue;
    row.bar.set({ width, height, row: row.geometry, previous: row.previous || null, isLast: row.isLast, scale: held.scale, still: still === true });
  }
}
