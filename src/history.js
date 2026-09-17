/* history.js
 *
 * The History view, docs/design.md Part 8.1, with Part 3 sections 2 and 3.
 *
 * Two sub views behind one pair of buttons, both linkable:
 *   Over time    three panels, never spliced: OPEC's monthly cracks from October
 *                2000, the ministry's margin from January 2015 with the extra gas
 *                in its own plot beside it, and this study's weekly reading from
 *                July 2022. Named ranges, product checkboxes, event markers in a
 *                lane above each plot, breaks split the one line they apply to.
 *   By season    Now's weekly seasonal panels, from data/cracks.json, and the long
 *                monthly profile of each crack from OPEC, with the textbook check
 *                said as measured.
 *
 * STATE IS THE ADDRESS. #/history?range=2022&products=gasoil&sub=season&leave=episodes.
 * A control rewrites the address with router.replaceState and redraws in place;
 * a pasted address arrives through update(). Nothing is kept that could drift
 * from the hash.
 *
 * Every figure is a field of data/history.json or data/cracks.json. The words
 * that label marks and controls are copy; every number in them is a field.
 *
 * Numeric literals: none. tools/check-literals.mjs.
 */

import { el, clear, sentence, disclosure, scrollTable, figureCell, uniqueId } from "./dom.js";
import { formatNumber, formatCell, segmentsText, UNITS } from "./format.js";
import * as charts from "./charts.js";
import * as router from "./router.js";
import * as cracksSection from "./section-cracks.js";

export const artifacts = Object.freeze(["history", "cracks"]);

const VIEW = "history";
const PRODUCTS = Object.freeze(["gasoil", "gasoline"]);
const SUBVIEWS = Object.freeze([
  { id: "time", label: "Over time" },
  { id: "season", label: "By season" },
]);
const LEAVE_EPISODES = "episodes";

/* How a week was read, for the readout and the tables. Keys are the artifact's
 * evidence classes, the same words as the Now view's cracks section. */
const EVIDENCE_WORDS = Object.freeze({
  cross_checked: "checked against a second chart",
  single_geometry_newest: "no second chart yet",
  single_geometry_oldest: "least defended week",
});

const MONTH_FORMAT = new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
const DAY_FORMAT = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const monthWords = (iso) => MONTH_FORMAT.format(new Date(charts.timeOf(iso)));
const dayWords = (iso) => DAY_FORMAT.format(new Date(charts.timeOf(iso)));

let held = null;

/* ------------------------------------------------------------- state --- */

function stateFrom(route, history) {
  const params = (route && route.params) || {};
  const sub = SUBVIEWS.some((s) => s.id === params.sub) ? params.sub : SUBVIEWS[0].id;
  const range = history.ranges.find((r) => r.id === params.range) || history.ranges[0];
  const asked = String(params.products || "").split(",").filter((p) => PRODUCTS.includes(p));
  const products = asked.length ? PRODUCTS.filter((p) => asked.includes(p)) : [...PRODUCTS];
  const leave = params.leave === LEAVE_EPISODES;
  return { sub, range, products, leave };
}

function paramsFor(state, history) {
  return {
    sub: state.sub === SUBVIEWS[0].id ? "" : state.sub,
    range: state.range.id === history.ranges[0].id ? "" : state.range.id,
    products: state.products.length === PRODUCTS.length ? "" : state.products.join(","),
    leave: state.leave ? LEAVE_EPISODES : "",
  };
}

function write(state) {
  router.replaceState(VIEW, paramsFor(state, held.history));
}

/* -------------------------------------------------------------- view --- */

export function render(root, data, route) {
  held = { history: data.history, cracks: data.cracks, root, state: stateFrom(route, data.history) };
  const history = data.history;
  const decimals = history.conventions.decimals;

  const title = sentence("h1", history.title_segments, decimals, "view-title");
  title.id = "view-title";
  title.setAttribute("tabindex", "-1");
  root.appendChild(title);
  root.appendChild(sentence("p", history.sample_segments, decimals, "lead history-lead"));

  const switcher = el("div", { class: "choice-row", attrs: { role: "group", "aria-label": "What the view shows" } });
  for (const sub of SUBVIEWS) {
    const button = el("button", { class: "choice", text: sub.label, attrs: { type: "button", "data-sub": sub.id, "aria-pressed": "false" } });
    button.addEventListener("click", () => {
      held.state = { ...held.state, sub: sub.id };
      write(held.state);
      draw();
    });
    switcher.appendChild(button);
  }
  root.appendChild(switcher);
  root.appendChild(el("div", { class: "history-body", id: "history-body" }));
  draw();
  return title;
}

export function update(root, route) {
  if (!held) return;
  held.state = stateFrom(route, held.history);
  draw();
}

function draw() {
  const body = held.root.querySelector("#history-body");
  if (!body) return;
  for (const button of held.root.querySelectorAll(".choice-row .choice[data-sub]")) {
    button.setAttribute("aria-pressed", button.getAttribute("data-sub") === held.state.sub ? "true" : "false");
  }
  clear(body);
  if (held.state.sub === "season") drawSeason(body);
  else drawTime(body);
}

/* ---------------------------------------------------------- over time --- */

function drawTime(body) {
  const { history, state } = held;
  const decimals = history.conventions.decimals;

  const controls = el("div", { class: "history-controls" });
  const ranges = el("div", { class: "choice-row", attrs: { role: "group", "aria-label": "Range" } });
  for (const range of history.ranges) {
    const button = el("button", { class: "choice", text: range.label, attrs: { type: "button", "aria-pressed": range.id === state.range.id ? "true" : "false" } });
    button.addEventListener("click", () => {
      held.state = { ...held.state, range };
      write(held.state);
      draw();
      const again = held.root.querySelectorAll(".history-controls .choice-row .choice")[history.ranges.indexOf(range)];
      if (again) again.focus();
    });
    ranges.appendChild(button);
  }
  controls.appendChild(ranges);

  const products = el("fieldset", { class: "product-toggle" }, [el("legend", { class: "product-toggle__legend", text: "Products on the crack panels" })]);
  for (const product of PRODUCTS) {
    const id = uniqueId("product");
    const box = el("input", { id, attrs: { type: "checkbox", value: product } });
    box.checked = state.products.includes(product);
    // At least one line stays: the last checked box cannot be cleared.
    box.disabled = box.checked && state.products.length === 1;
    box.addEventListener("change", () => {
      const next = PRODUCTS.filter((p) => (p === product ? box.checked : held.state.products.includes(p)));
      if (!next.length) return;
      held.state = { ...held.state, products: next };
      write(held.state);
      draw();
      const again = held.root.querySelector('.product-toggle input[value="' + product + '"]');
      if (again) again.focus();
    });
    products.appendChild(el("label", { class: "product-toggle__item", attrs: { for: id } }, [box, " " + product.charAt(0).toUpperCase() + product.slice(1)]));
  }
  controls.appendChild(products);
  body.appendChild(controls);

  body.appendChild(monthlyPanel(decimals));
  body.appendChild(marginPanel(decimals));
  body.appendChild(weeklyPanel(decimals));
  body.appendChild(breaksBlock());
}

/* The rows of a panel whose date falls inside the selected range. */
function rowsIn(rows, range) {
  return rows.filter((row) => row[0] >= range.start && row[0] <= range.end);
}

/* A y domain from the values drawn, on the tick ladder, zero kept in view. */
function domainOf(values) {
  const finite = values.filter((v) => charts.present(v));
  if (!finite.length) return null;
  return charts.niceDomain(Math.min(...finite, 0), Math.max(...finite, 0), charts.GEOMETRY.Y_TICKS);
}

function plotHeight(width) {
  return width < charts.GEOMETRY.NARROW_WIDTH ? charts.GEOMETRY.TIME_HEIGHT_NARROW : charts.GEOMETRY.TIME_HEIGHT;
}

/* The words a panel says when the range holds none of its data. */
function outOfRange(what, first, last, range, monthly) {
  const words = monthly ? monthWords : dayWords;
  return el("p", {
    class: "state-message",
    text: "Nothing of " + what + " falls in the range " + range.label + ": it runs from " + words(first) + " to " + words(last) + ", and nothing outside that is drawn or filled in.",
  });
}

/* Events and breaks for one panel inside the range, in date order, numbered. */
function markersFor(panelId, range, first, last) {
  const { history } = held;
  const inSpan = (date) => date >= range.start && date <= range.end && date >= first && date <= last;
  const items = [];
  for (const event of history.events) if (inSpan(event.date)) items.push({ kind: "event", item: event });
  for (const brk of history.breaks) if (brk.drawn && brk.panel === panelId && inSpan(brk.date)) items.push({ kind: "break", item: brk });
  items.sort((a, b) => (a.item.date < b.item.date ? -1 : a.item.date > b.item.date ? 1 : 0));
  return items;
}

/* The lane above a plot: a button per event, a plain label per break, placed at
 * their x. Short names while they fit, numbers for all of them when any two
 * collide, Part 3 section 2. A marker opens a sentence under the plot. */
function fillLane(lane, markers, panel, detail) {
  clear(lane);
  lane.style.width = String(panel.svg.getAttribute("width")) + "px";
  const nodes = markers.map((marker, index) => {
    const x = panel.xOf(charts.timeOf(marker.item.date));
    const number = String(index + 1);
    const node = marker.kind === "event"
      ? el("button", { class: "lane__marker", text: marker.item.short, attrs: { type: "button", "data-number": number, "aria-label": number + ", " + marker.item.name + ", " + marker.item.label } })
      : el("span", { class: "lane__break", text: marker.item.short, attrs: { "data-number": number } });
    node.style.left = charts.px(x) + "px";
    if (marker.kind === "event") {
      node.addEventListener("click", () => showDetail(detail, marker, number));
    }
    lane.appendChild(node);
    return node;
  });
  const collide = () => {
    const boxes = nodes.map((node) => node.getBoundingClientRect());
    const laneBox = lane.getBoundingClientRect();
    for (let i = 0; i < boxes.length; i += 1) {
      if (boxes[i].left < laneBox.left - charts.GEOMETRY.LABEL_GAP || boxes[i].right > laneBox.right + charts.GEOMETRY.TIME_PAD_RIGHT) return true;
      if (i > 0 && boxes[i].left < boxes[i - 1].right + charts.GEOMETRY.TICK_LENGTH) return true;
    }
    return false;
  };
  if (nodes.length && collide()) {
    for (const node of nodes) {
      node.textContent = node.getAttribute("data-number");
      node.classList.add("is-numbered");
    }
    // Numbers that still touch take a second row, then a third, so no two
    // markers overlap and each stays a separate target.
    const rowsRight = [];
    for (const node of nodes) {
      const box = node.getBoundingClientRect();
      let row = rowsRight.findIndex((right) => box.left >= right + charts.GEOMETRY.TICK_LENGTH);
      if (row < 0) {
        row = rowsRight.length;
        rowsRight.push(box.right);
      } else {
        rowsRight[row] = box.right;
      }
      node.setAttribute("data-row", String(row));
      node.style.setProperty("--row", String(row));
    }
    lane.setAttribute("data-rows", String(rowsRight.length));
    lane.style.setProperty("--rows", String(rowsRight.length));
  }
}

function showDetail(detail, marker, number) {
  clear(detail);
  const event = marker.item;
  detail.appendChild(el("p", { class: "event-detail" }, [
    number + ". " + event.label + ": " + event.name + ". Source: ",
    el("a", { class: "text-link", text: event.source_title || event.source_publisher || "the source", attrs: { href: event.source_url, rel: "noopener" } }),
    ".",
  ]));
}

/* The numbered list under a plot: every marker drawn, with its source. */
function markerList(markers) {
  if (!markers.length) return null;
  const list = el("ol", { class: "marker-list" });
  markers.forEach((marker, index) => {
    const item = marker.item;
    const what = marker.kind === "event" ? item.name : item.name + ", a break: the line is split here";
    list.appendChild(el("li", {}, [
      el("span", { class: "marker-list__number", text: String(index + 1) + ". " }),
      item.label + ", " + what + ". ",
      el("a", { class: "text-link", text: item.source_title || "Source", attrs: { href: item.source_url, rel: "noopener" } }),
    ]));
  });
  return list;
}

/* One interactive plot: the lane, the chart group with its readout and cursor,
 * the detail sentence and the marker list. `build(width)` returns the time
 * panel; `readout(index)` the sentence for the observation at index. */
function interactivePlot({ heading, headingSegments, decimals, rows, times, build, readout, markers, className }) {
  const section = el("section", { class: "history-panel " + (className || "") });
  section.appendChild(sentence("h2", headingSegments, decimals, "history-panel__heading"));
  const readoutId = uniqueId("readout");
  const said = el("p", { class: "readout", id: readoutId, attrs: { "aria-live": "polite" } });
  const lane = el("div", { class: "lane", attrs: { "aria-label": "Events and breaks on " + heading } });
  const frame = el("div", { class: "chart-frame history-chart", attrs: { role: "group", "aria-describedby": readoutId, "aria-label": heading + ". Left and right arrow keys step through the observations." } });
  frame.tabIndex = 0; // the plot group takes focus for the arrow keys, Part 3 section 9
  const detail = el("div", { class: "event-detail-region", attrs: { "aria-live": "polite" } });
  section.appendChild(said);
  section.appendChild(lane);
  section.appendChild(frame);
  section.appendChild(detail);
  const list = markerList(markers);

  let index = rows.length - 1;
  let panel = null;
  let cursor = null;
  const show = (at) => {
    index = Math.max(0, Math.min(rows.length - 1, at));
    said.textContent = readout(index);
    if (panel && cursor) charts.moveCursor(cursor, panel.xOf(times[index]));
  };
  charts.onWidthChange(frame, (width) => {
    panel = build(width);
    frame.replaceChildren(panel.svg);
    charts.plateRailLabels(panel.svg);
    cursor = charts.cursorLine(panel);
    fillLane(lane, markers, panel, detail);
    said.textContent = readout(index);
  });
  frame.addEventListener("pointermove", (ev) => {
    if (!panel) return;
    const box = panel.svg.getBoundingClientRect();
    const x = ev.clientX - box.left;
    let best = 0;
    let bestGap = Infinity;
    times.forEach((t, i) => {
      const gap = Math.abs(panel.xOf(t) - x);
      if (gap < bestGap) {
        bestGap = gap;
        best = i;
      }
    });
    show(best);
  });
  frame.addEventListener("keydown", (ev) => {
    const moves = { ArrowLeft: index - 1, ArrowRight: index + 1, Home: 0, End: rows.length - 1 };
    if (!Object.prototype.hasOwnProperty.call(moves, ev.key)) return;
    ev.preventDefault();
    show(moves[ev.key]);
  });
  said.textContent = readout(index);
  return { section, list };
}

function finishPanel(section, list, notes, alternative) {
  if (list) section.appendChild(list);
  for (const note of notes) if (note) section.appendChild(note);
  section.appendChild(alternative);
  return section;
}

function productName(product) {
  return product.charAt(0).toUpperCase() + product.slice(1);
}

/* The monthly OPEC cracks. */
function monthlyPanel(decimals) {
  const { history, state } = held;
  const monthly = history.monthly;
  const c = (name) => monthly.columns.indexOf(name);
  const rows = rowsIn(monthly.rows, state.range);
  if (!rows.length) {
    const section = el("section", { class: "history-panel" }, [sentence("h2", monthly.heading_segments, decimals, "history-panel__heading")]);
    section.appendChild(outOfRange("OPEC's monthly cracks", monthly.first, monthly.last, state.range, true));
    return section;
  }
  const times = rows.map((row) => charts.timeOf(row[0]));
  const xDomain = [times[0], times[times.length - 1]];
  const shown = state.products;
  const yDomain = domainOf(rows.flatMap((row) => shown.map((p) => row[c(p + "_usd_bbl")])));
  const isLast = rows[rows.length - 1][0] === monthly.last;
  const breaksFor = (product) => history.breaks.filter((b) => b.drawn && b.panel === "monthly" && b.line === product).map((b) => charts.timeOf(b.date));
  const markers = markersFor("monthly", state.range, monthly.first, monthly.last);
  const heading = segmentsText(monthly.heading_segments, decimals);

  const { section, list } = interactivePlot({
    heading,
    headingSegments: monthly.heading_segments,
    decimals,
    rows,
    times,
    markers,
    build: (width) => charts.timePanel({
      width,
      height: plotHeight(width),
      xDomain,
      yDomain,
      unit: UNITS.usd_bbl,
      title: heading,
      desc: "Monthly cracks, one line per product, gasoil solid and gasoline dashed, " + monthWords(rows[0][0]) + " to " + monthWords(rows[rows.length - 1][0]) + ". A dashed rule and a split line mark each change in OPEC's product specification; thin rules mark events. Every value is in the table under the chart.",
      lines: shown.map((product) => ({
        name: productName(product),
        style: product === "gasoil" ? "solid" : "dashed",
        points: rows.map((row) => [charts.timeOf(row[0]), row[c(product + "_usd_bbl")]]),
        lastText: formatNumber(rows[rows.length - 1][c(product + "_usd_bbl")], "usd_bbl", decimals) || "no value",
        breaks: breaksFor(product),
        accent: isLast,
      })),
      events: markers.filter((m) => m.kind === "event").map((m) => charts.timeOf(m.item.date)),
      breaks: markers.filter((m) => m.kind === "break" && shown.includes(m.item.line)).map((m) => charts.timeOf(m.item.date)),
      rails: null,
    }),
    readout: (i) => {
      const row = rows[i];
      const parts = shown.map((p) => p + " " + (formatNumber(row[c(p + "_usd_bbl")], "usd_bbl", decimals) || "no value"));
      const specs = shown.map((p) => p + " " + (row[c(p + "_spec")] || "no label"));
      return monthWords(row[0]) + ": " + parts.join(", ") + " $/bbl. OPEC's labels that month: " + specs.join(", ") + ".";
    },
  });

  const alternative = disclosure("Every month on this panel, with OPEC's product labels", () => {
    const head = el("tr", {}, [
      el("th", { text: "Month", attrs: { scope: "col" } }),
      el("th", { class: "col-num", text: "Gasoil, $/bbl", attrs: { scope: "col", "data-short": "gasoil" } }),
      el("th", { class: "col-num", text: "Gasoline, $/bbl", attrs: { scope: "col", "data-short": "gasoline" } }),
      el("th", { text: "Gasoil label", attrs: { scope: "col", "data-short": "gasoil label" } }),
      el("th", { text: "Gasoline label", attrs: { scope: "col", "data-short": "gasoline label" } }),
    ]);
    const tbody = el("tbody");
    for (const row of rows) {
      tbody.appendChild(el("tr", {}, [
        el("th", { class: "num", text: row[0].slice(0, row[0].lastIndexOf("-")), attrs: { scope: "row" } }),
        figureCell(formatCell(row[c("gasoil_usd_bbl")], "usd_bbl", decimals), "gasoil_usd_bbl"),
        figureCell(formatCell(row[c("gasoline_usd_bbl")], "usd_bbl", decimals), "gasoline_usd_bbl"),
        el("td", { text: row[c("gasoil_spec")] || "no label" }),
        el("td", { text: row[c("gasoline_spec")] || "no label" }),
      ]));
    }
    return scrollTable(["OPEC's monthly Rotterdam cracks, " + monthWords(rows[0][0]) + " to " + monthWords(rows[rows.length - 1][0]) + "."], el("table", { class: "table history-table" }, [el("thead", {}, [head]), tbody]));
  });
  const notes = [sentence("p", monthly.r2_segments, decimals, "note")];
  if (isLast) notes.push(sentence("p", monthly.end_segments, decimals, "note"));
  return finishPanel(section, list, notes, alternative);
}

/* The official margin, and the extra gas beside it in its own plot. */
function marginPanel(decimals) {
  const { history, state } = held;
  const margin = history.margin;
  const c = (name) => margin.columns.indexOf(name);
  const rows = rowsIn(margin.rows, state.range);
  if (!rows.length) {
    const section = el("section", { class: "history-panel" }, [sentence("h2", margin.heading_segments, decimals, "history-panel__heading")]);
    section.appendChild(outOfRange("the ministry's margin", margin.first, margin.last, state.range, true));
    section.appendChild(sentence("p", margin.no_break_segments, decimals, "note"));
    return section;
  }
  const times = rows.map((row) => charts.timeOf(row[0]));
  const xDomain = [times[0], times[times.length - 1]];
  const isLast = rows[rows.length - 1][0] === margin.last;
  const markers = markersFor("margin", state.range, margin.first, margin.last);
  const heading = segmentsText(margin.heading_segments, decimals);
  const mbrDomain = domainOf(rows.map((row) => row[c("mbr_usd_bbl")]));

  const { section, list } = interactivePlot({
    heading,
    headingSegments: margin.heading_segments,
    decimals,
    rows,
    times,
    markers: markers.filter((m) => m.kind === "event"),
    build: (width) => charts.timePanel({
      width,
      height: plotHeight(width),
      xDomain,
      yDomain: mbrDomain,
      unit: UNITS.usd_bbl,
      title: heading,
      desc: "The ministry's monthly gross refining margin on Brent, " + monthWords(rows[0][0]) + " to " + monthWords(rows[rows.length - 1][0]) + ", one line with no break, because the method was recomputed over the whole published window. Thin rules mark events. Every value is in the table under the charts.",
      lines: [{
        name: "Margin",
        style: "solid",
        points: rows.map((row) => [charts.timeOf(row[0]), row[c("mbr_usd_bbl")]]),
        lastText: formatNumber(rows[rows.length - 1][c("mbr_usd_bbl")], "usd_bbl", decimals) || "no value",
        breaks: [],
        accent: isLast,
      }],
      events: markers.filter((m) => m.kind === "event").map((m) => charts.timeOf(m.item.date)),
      breaks: [],
      rails: null,
    }),
    readout: (i) => {
      const row = rows[i];
      return monthWords(row[0]) + ": the ministry's margin " + (formatNumber(row[c("mbr_usd_bbl")], "usd_bbl", decimals) || "no value") + " $/bbl; beside it, extra gas at the US refinery average " + (formatNumber(row[c("gas_wedge_usd_bbl")], "usd_bbl", decimals) || "no value") + " $/bbl at " + (formatNumber(row[c("gas_usd_mmbtu")], "usd_mmbtu", decimals) || "no value") + " $/MMBtu.";
    },
  });

  // The wedge, its own small plot on the same axis units, never under the line.
  section.appendChild(sentence("h3", margin.wedge_heading_segments, decimals, "history-panel__subheading"));
  const wedgeFrame = el("div", { class: "chart-frame history-chart history-chart--wedge" });
  section.appendChild(wedgeFrame);
  const gasBreaks = history.breaks.filter((b) => b.drawn && b.panel === "margin" && b.line === "gas_wedge");
  const wedgeDomain = domainOf(rows.map((row) => row[c("gas_wedge_usd_bbl")]));
  charts.onWidthChange(wedgeFrame, (width) => {
    const panel = charts.timePanel({
      width,
      height: charts.GEOMETRY.WEDGE_HEIGHT,
      xDomain,
      yDomain: wedgeDomain,
      unit: UNITS.usd_bbl,
      title: segmentsText(margin.wedge_heading_segments, decimals),
      desc: "The extra gas cost per barrel at the average US refinery's gas use over the ministry's own allowance, " + monthWords(rows[0][0]) + " to " + monthWords(rows[rows.length - 1][0]) + ". A dashed rule and a split line mark where the European gas series changes definition. It is drawn beside the margin and never subtracted from it.",
      lines: [{
        name: "Extra gas",
        style: "solid",
        points: rows.map((row) => [charts.timeOf(row[0]), row[c("gas_wedge_usd_bbl")]]),
        lastText: formatNumber(rows[rows.length - 1][c("gas_wedge_usd_bbl")], "usd_bbl", decimals) || "no value",
        breaks: gasBreaks.map((b) => charts.timeOf(b.date)),
        accent: false,
      }],
      events: [],
      breaks: gasBreaks.map((b) => charts.timeOf(b.date)).filter((t) => t >= xDomain[0] && t <= xDomain[1]),
      rails: null,
      className: "chart--wedge",
    });
    wedgeFrame.replaceChildren(panel.svg);
  });
  const gasNotes = gasBreaks
    .filter((b) => b.date >= rows[0][0] && b.date <= rows[rows.length - 1][0])
    .map((b) => el("p", { class: "note" }, [b.label + ": " + b.name + ". The wedge line is split there. ", el("a", { class: "text-link", text: b.source_title || "Source", attrs: { href: b.source_url, rel: "noopener" } })]));

  const alternative = disclosure("Every month of the margin and the extra gas beside it", () => {
    const head = el("tr", {}, [
      el("th", { text: "Month", attrs: { scope: "col" } }),
      el("th", { class: "col-num", text: "Official margin, $/bbl", attrs: { scope: "col", "data-short": "official margin" } }),
      el("th", { class: "col-num", text: "Extra gas, $/bbl", attrs: { scope: "col", "data-short": "extra gas" } }),
      el("th", { class: "col-num", text: "Gas, $/MMBtu", attrs: { scope: "col", "data-short": "gas" } }),
    ]);
    const tbody = el("tbody");
    for (const row of rows) {
      tbody.appendChild(el("tr", {}, [
        el("th", { class: "num", text: row[0].slice(0, row[0].lastIndexOf("-")), attrs: { scope: "row" } }),
        figureCell(formatCell(row[c("mbr_usd_bbl")], "usd_bbl", decimals), "mbr_usd_bbl"),
        figureCell(formatCell(row[c("gas_wedge_usd_bbl")], "usd_bbl", decimals), "gas_wedge_usd_bbl"),
        figureCell(formatCell(row[c("gas_usd_mmbtu")], "usd_mmbtu", decimals), "gas_usd_mmbtu"),
      ]));
    }
    return scrollTable(["The ministry's margin and, beside it, the extra gas at the US refinery average, " + monthWords(rows[0][0]) + " to " + monthWords(rows[rows.length - 1][0]) + "."], el("table", { class: "table history-table" }, [el("thead", {}, [head]), tbody]));
  });
  return finishPanel(section, list, [sentence("p", margin.no_break_segments, decimals, "note"), ...gasNotes], alternative);
}

/* This study's weekly reading of the ministry's chart. */
function weeklyPanel(decimals) {
  const { history, state } = held;
  const weekly = history.weekly;
  const c = (name) => weekly.columns.indexOf(name);
  const rows = rowsIn(weekly.rows, state.range);
  const joinNote = sentence("p", weekly.join_segments, decimals, "note");
  if (!rows.length) {
    const section = el("section", { class: "history-panel" }, [sentence("h2", weekly.heading_segments, decimals, "history-panel__heading")]);
    section.appendChild(outOfRange("this study's weekly reading", weekly.first, weekly.last, state.range, false));
    section.appendChild(joinNote);
    return section;
  }
  const times = rows.map((row) => charts.timeOf(row[0]));
  const xDomain = [times[0], times[times.length - 1]];
  const shown = state.products;
  const yDomain = domainOf(rows.flatMap((row) => shown.flatMap((p) => [row[c(p + "_usd_bbl")], row[c("printed_" + p + "_usd_bbl")]])));
  const isLast = rows[rows.length - 1][0] === weekly.last;
  const markers = markersFor("weekly", state.range, weekly.first, weekly.last);
  const heading = segmentsText(weekly.heading_segments, decimals);

  // Evidence spans from the class column, never from dates: runs of a class.
  const spans = (cls) => {
    const out = [];
    let start = null;
    let prev = null;
    for (const row of weekly.rows) {
      if (row[c("evidence_class")] === cls) {
        if (start === null) start = row[0];
        prev = row[0];
      } else if (start !== null) {
        out.push([charts.timeOf(start), charts.timeOf(prev)]);
        start = null;
      }
    }
    if (start !== null) out.push([charts.timeOf(start), charts.timeOf(prev)]);
    return out;
  };

  const { section, list } = interactivePlot({
    heading,
    headingSegments: weekly.heading_segments,
    decimals,
    rows,
    times,
    markers: markers.filter((m) => m.kind === "event"),
    build: (width) => charts.timePanel({
      width,
      height: plotHeight(width),
      xDomain,
      yDomain,
      unit: UNITS.usd_bbl,
      title: heading,
      desc: "Weekly cracks read off the ministry's chart, gasoil solid and gasoline dashed, " + dayWords(rows[0][0]) + " to " + dayWords(rows[rows.length - 1][0]) + ". Squares are weeks the ministry printed. Under the axis a hatch marks the least defended weeks and a bracket the weeks with no second chart yet. Every value is in the table under the chart.",
      lines: shown.map((product) => ({
        name: productName(product),
        style: product === "gasoil" ? "solid" : "dashed",
        points: rows.map((row) => [charts.timeOf(row[0]), row[c(product + "_usd_bbl")]]),
        lastText: formatNumber(rows[rows.length - 1][c(product + "_usd_bbl")], "usd_bbl", decimals) || "no value",
        breaks: [],
        accent: isLast,
      })),
      squares: rows.flatMap((row) => shown.map((p) => [charts.timeOf(row[0]), row[c("printed_" + p + "_usd_bbl")]])),
      events: markers.filter((m) => m.kind === "event").map((m) => charts.timeOf(m.item.date)),
      breaks: [],
      rails: {
        least: spans(weekly.least_defended_class),
        newest: spans(weekly.newest_class),
        leastLabel: "Least defended weeks",
        newestLabel: "No second chart yet",
      },
    }),
    readout: (i) => {
      const row = rows[i];
      const parts = shown.map((p) => p + " " + (formatNumber(row[c(p + "_usd_bbl")], "usd_bbl", decimals) || "no value"));
      const brent = formatNumber(row[c("brent_usd_bbl")], "usd_bbl", decimals);
      const printed = shown.map((p) => formatNumber(row[c("printed_" + p + "_usd_bbl")], "usd_bbl", decimals)).filter((v) => v !== null);
      const how = [EVIDENCE_WORDS[row[c("evidence_class")]] || "evidence not recorded"];
      if (printed.length) how.unshift("printed by the ministry at " + printed.join(" and "));
      return "Week to " + dayWords(row[0]) + ": " + parts.join(", ") + (brent ? ", Brent " + brent : "") + " $/bbl, read off the chart; " + how.join("; ") + ".";
    },
  });

  const alternative = disclosure("Every week on this panel, with how each was read", () => {
    const head = el("tr", {}, [
      el("th", { text: "Week to", attrs: { scope: "col" } }),
      el("th", { class: "col-num", text: "Gasoil, $/bbl", attrs: { scope: "col", "data-short": "gasoil" } }),
      el("th", { class: "col-num", text: "Gasoline, $/bbl", attrs: { scope: "col", "data-short": "gasoline" } }),
      el("th", { class: "col-num", text: "Brent, $/bbl", attrs: { scope: "col", "data-short": "Brent" } }),
      el("th", { class: "col-num", text: "Printed gasoil", attrs: { scope: "col", "data-short": "printed gasoil" } }),
      el("th", { class: "col-num", text: "Printed gasoline", attrs: { scope: "col", "data-short": "printed gasoline" } }),
      el("th", { text: "How read", attrs: { scope: "col", "data-short": "how read" } }),
    ]);
    const tbody = el("tbody");
    for (const row of rows) {
      const printedGasoil = formatCell(row[c("printed_gasoil_usd_bbl")], "usd_bbl", decimals);
      const printedGasoline = formatCell(row[c("printed_gasoline_usd_bbl")], "usd_bbl", decimals);
      tbody.appendChild(el("tr", {}, [
        el("th", { class: "num", text: row[0], attrs: { scope: "row" } }),
        figureCell(formatCell(row[c("gasoil_usd_bbl")], "usd_bbl", decimals), "gasoil_usd_bbl"),
        figureCell(formatCell(row[c("gasoline_usd_bbl")], "usd_bbl", decimals), "gasoline_usd_bbl"),
        figureCell(formatCell(row[c("brent_usd_bbl")], "usd_bbl", decimals), "brent_usd_bbl"),
        printedGasoil === null ? el("td", { class: "is-missing", text: "not printed" }) : figureCell(printedGasoil, "printed_gasoil_usd_bbl"),
        printedGasoline === null ? el("td", { class: "is-missing", text: "not printed" }) : figureCell(printedGasoline, "printed_gasoline_usd_bbl"),
        el("td", { text: EVIDENCE_WORDS[row[c("evidence_class")]] || "not recorded" }),
      ]));
    }
    return scrollTable(["This study's weekly reading of the ministry's chart, " + dayWords(rows[0][0]) + " to " + dayWords(rows[rows.length - 1][0]) + "."], el("table", { class: "table history-table weeks-table" }, [el("thead", {}, [head]), tbody]));
  });
  return finishPanel(section, list, [sentence("p", weekly.evidence_segments, decimals, "note"), joinNote], alternative);
}

/* Every break in the series this view reads: drawn, or why not. */
function breaksBlock() {
  const { history } = held;
  const section = el("section", { class: "history-panel history-breaks" });
  section.appendChild(el("h2", { class: "history-panel__heading", text: "Breaks in these series, and where each is drawn" }));
  const head = el("tr", {}, [
    el("th", { text: "Date", attrs: { scope: "col" } }),
    el("th", { text: "Break", attrs: { scope: "col", "data-short": "break" } }),
    el("th", { text: "On this view", attrs: { scope: "col", "data-short": "on this view" } }),
    el("th", { text: "Source", attrs: { scope: "col", "data-short": "source" } }),
  ]);
  const where = { monthly: "splits the monthly ", margin: "splits the extra gas line under the margin" };
  const tbody = el("tbody");
  for (const brk of history.breaks) {
    const drawn = brk.drawn
      ? (brk.panel === "monthly" ? where.monthly + brk.line + " line" : where.margin)
      : "not drawn: " + brk.reason;
    tbody.appendChild(el("tr", {}, [
      el("th", { class: "history-breaks__date", text: brk.label, attrs: { scope: "row" } }),
      el("td", { class: "history-breaks__name", text: brk.name }),
      el("td", { class: "history-breaks__where", text: drawn }),
      el("td", { class: "history-breaks__source" }, [el("a", { class: "text-link", text: brk.source_title || "Source", attrs: { href: brk.source_url, rel: "noopener" } })]),
    ]));
  }
  section.appendChild(scrollTable(["Every break in the series this view reads, in date order. The ministry's margin has none inside its published window."], el("table", { class: "table history-breaks__table" }, [el("thead", {}, [head]), tbody])));
  return section;
}

/* ---------------------------------------------------------- by season --- */

function drawSeason(body) {
  const { history, cracks, state } = held;
  const decimals = history.conventions.decimals;

  const weekly = el("section", { class: "history-panel" });
  weekly.appendChild(el("h2", { class: "history-panel__heading", text: "Week by week, this study's weekly reading against the same week of each earlier year" }));
  cracksSection.render(weekly, cracks);
  body.appendChild(weekly);

  const layer = history.seasonal_monthly;
  const monthly = el("section", { class: "history-panel" });
  monthly.appendChild(el("h2", { class: "history-panel__heading", text: "Month by month, the shape of each year of OPEC's quotations" }));
  monthly.appendChild(sentence("p", layer.note_segments, decimals, "note"));

  const episodeYears = [...new Set(PRODUCTS.flatMap((p) => layer.panels[p].episode_years_in_range))].sort();
  if (episodeYears.length) {
    const years = episodeYears.map((y) => formatNumber(y, "year", decimals));
    const joined = years.length > 1 ? years.slice(0, -1).join(", ") + " and " + years[years.length - 1] : years[0];
    const toggle = el("button", {
      class: "choice choice--toggle",
      text: state.leave ? "Put " + joined + " back" : "Leave out " + joined,
      attrs: { type: "button", "aria-pressed": state.leave ? "true" : "false" },
    });
    toggle.addEventListener("click", () => {
      held.state = { ...held.state, leave: !held.state.leave };
      write(held.state);
      draw();
      const again = held.root.querySelector(".choice--toggle");
      if (again) again.focus();
    });
    monthly.appendChild(el("div", { class: "choice-row" }, [toggle]));
  }

  const variant = state.leave ? "without_episodes" : "all";
  const panels = el("div", { class: "panels" });
  let low = Infinity;
  let high = -Infinity;
  for (const product of PRODUCTS) {
    const panel = layer.panels[product];
    const excluded = panel.variants[variant].excluded_years;
    for (const [year, values] of panel.lines) {
      if (excluded.includes(year)) continue;
      for (const v of values) if (charts.present(v)) { low = Math.min(low, v); high = Math.max(high, v); }
    }
  }
  const yDomain = charts.niceDomain(Math.min(low, 0), Math.max(high, 0), charts.GEOMETRY.Y_TICKS);
  for (const product of PRODUCTS) {
    const panel = layer.panels[product];
    const chosen = panel.variants[variant];
    const lines = panel.lines.filter(([year]) => !chosen.excluded_years.includes(year));
    const figure = el("figure", { class: "panel" });
    figure.appendChild(sentence("h3", chosen.sentence_segments, decimals, "panel__heading"));
    const frame = el("div", { class: "chart-frame" });
    figure.appendChild(frame);
    const meanLabel = segmentsText(chosen.mean_label_segments, decimals);
    charts.onWidthChange(frame, (width) => {
      const svg = charts.profilePanel({
        width,
        years: lines,
        mean: chosen.mean_usd_bbl,
        months: layer.months,
        season: panel.season_months,
        style: panel.line_style,
        yDomain,
        words: {
          title: productName(product) + " crack by calendar month, each year less its own mean",
          desc: segmentsText(chosen.sentence_segments, decimals) + " One thin decorative line per year, exempt from contrast rules because no value is read from it alone; the ink line is the mean of the years drawn, and every value is in the table under the chart.",
          unit: UNITS.usd_bbl,
          meanLabel,
          seasonLabel: panel.season_label,
        },
      });
      frame.replaceChildren(svg);
      charts.plateRailLabels(svg);
    });
    figure.appendChild(disclosure("The " + panel.name + " shape by month, the mean and every year", () => {
      const head = el("tr", {}, [el("th", { text: "Year", attrs: { scope: "col" } })]);
      layer.months.forEach((name) => head.appendChild(el("th", { class: "col-num", text: name, attrs: { scope: "col" } })));
      const tbody = el("tbody");
      const meanRow = el("tr", { class: "is-total" }, [el("th", { text: meanLabel, attrs: { scope: "row" } })]);
      chosen.mean_usd_bbl.forEach((v) => meanRow.appendChild(figureCell(formatCell(v, "usd_bbl", decimals, true), "mean_usd_bbl", "num--total")));
      tbody.appendChild(meanRow);
      for (const [year, values] of lines) {
        const tr = el("tr", {}, [el("th", { class: "num", text: formatNumber(year, "year", decimals), attrs: { scope: "row" } })]);
        values.forEach((v) => tr.appendChild(figureCell(formatCell(v, "usd_bbl", decimals, true), "demeaned_usd_bbl")));
        tbody.appendChild(tr);
      }
      return scrollTable(["The " + panel.name + " crack by month less each year's own mean, $/bbl."], el("table", { class: "table history-table" }, [el("thead", {}, [head]), tbody]));
    }));
    panels.appendChild(figure);
  }
  monthly.appendChild(panels);
  body.appendChild(monthly);
}
