/* charts.js
 *
 * SVG drawn by hand. docs/design.md Part 3 section 10: no chart library is
 * vendored, because every mark this study needs is unusual in a way no helper
 * covers, and a library's defaults (a legend, a tooltip card, colour cycling)
 * are each a banned or rejected item. The structure follows the LME sibling's
 * src/charts.js (lme-comex-arbitrage-model, by the same author): a namespace
 * helper, a path that breaks at a gap, a 1, 2, 5, 10 tick ladder and a redraw
 * on width change so type inside a plot stays the size the stylesheet says.
 * Its palette is not copied; marks here take colour from the role classes in
 * styles/components.css, never from a fill or stroke attribute holding a value,
 * so a theme change needs no redraw.
 *
 * What lives here: the helpers, and the three marks the Now sections draw.
 *   seasonalPanel    one crack by week of the year, each year its own line
 *   waterfallBar     one row's bar in the margin table
 *   liveWaterfallBar the same bar built once and moved in place, for the Model
 *                    view's recompute
 *   intervalStrip    one or more response intervals with zero marked
 * and, for the Runs view (docs/design.md Part 8.3):
 *   scatterPanel     the run cut threshold scatter, two fits and the interval
 *   powerCell        a horse race power strip in a table row, and powerFigure
 *                    the same strips as one figure at narrow widths
 *
 * Missing is never zero. A null ends the current subpath and the next value
 * starts a new one, a finite value with a gap on both sides is a small dot so it
 * cannot vanish, and a hole inside a line is marked on the baseline. SPEC.md
 * section 2 rule 1.
 *
 * NUMERIC LITERALS. GEOMETRY below is the drawing surface: heights, paddings, a
 * dot radius, a hatch pitch. They are coordinate system decisions, the same
 * class of decision as a pixel value in the stylesheet, and they carry no
 * observation. Each is declared with its value in tools/check-literals.mjs, so
 * a moved value fails the gate. Every quantity about the market arrives from a
 * JSON artifact through the caller. Stroke widths and dash patterns are in the
 * stylesheet, not here.
 */

import { formatNumber } from "./format.js";

export const GEOMETRY = Object.freeze({
  /* The seasonal panel plot, 220px tall, Part 3 section 3. */
  PANEL_HEIGHT: 220,
  /* A rail under the x axis: the depth rail and the two evidence lanes. */
  RAIL_HEIGHT: 14,
  /* Room above the plot for the unit title. */
  PAD_TOP: 28,
  /* Room left of the plot for the tick values. */
  PAD_LEFT: 44,
  /* Room right of the plot for the end labels. */
  PAD_RIGHT: 84,
  /* From the plot's bottom edge to the middle of the x tick values. */
  AXIS_GAP: 16,
  /* Room under the x tick values before the first rail. */
  AXIS_BELOW: 10,
  TICK_LENGTH: 4,
  /* Space between a mark and its label, 8px, Part 3 section 2. */
  LABEL_GAP: 8,
  /* Two end labels closer than this are pushed apart, with leaders. */
  LABEL_SPACING: 14,
  /* The accent dot, 4px radius, and its 2px --bg ring. */
  DOT_RADIUS: 4,
  RING_WIDTH: 2,
  /* A finite value with a gap on both sides. */
  ISOLATED_RADIUS: 1.5,
  /* A printed week, a 5px square. */
  SQUARE: 5,
  /* The least defended hatch: 45 degrees, 4px pitch, at least 6px wide. */
  HATCH_PITCH: 4,
  HATCH_ANGLE: 45,
  HATCH_MIN_WIDTH: 6,
  /* The end tick of a bracket in a rail. */
  BRACKET_TICK: 4,
  /* About this many tick intervals on each axis. */
  Y_TICKS: 5,
  X_TICKS: 5,
  /* Halving, for centring. */
  HALF: 0.5,
  /* Pixel coordinates are written to two places. */
  COORD_DECIMALS: 2,
  /* The waterfall bar inside a table row. A step narrower than SMALL_STEP px is
   * drawn as a 5px circle, Part 3 section 4. */
  BAR_THICKNESS: 14,
  SMALL_STEP: 4,
  SMALL_RADIUS: 2.5,
  /* The negative step's outline is 1.5px, inset by half of it. */
  OUTLINE_INSET: 0.75,
  /* The interval strip: a 28px row, 6px end ticks, 4px estimate dot. */
  STRIP_ROW: 28,
  STRIP_END_TICK: 6,
  STRIP_PAD: 8,
  /* The narrow strip figure's model labels sit above each row. */
  STRIP_LABEL: 16,
  /* A History time plot: 360px tall, 240px below 768px, Part 3 section 2. */
  TIME_HEIGHT: 360,
  TIME_HEIGHT_NARROW: 240,
  NARROW_WIDTH: 768,
  /* The gas wedge plot under the margin, Part 8.1 H2. */
  WEDGE_HEIGHT: 120,
  /* Room right of a time plot for a two line end label. */
  TIME_PAD_RIGHT: 64,
  /* Year labels closer than this take every second, fifth or tenth year. */
  YEAR_SPACING: 48,
  /* The monthly seasonal profile plot, Part 8.1 H8. */
  PROFILE_HEIGHT: 240,
  /* The run cut scatter, Part 8.3 R2: room right for two line fit labels, room
   * above for the unit title and the edge label on their own rows, and the
   * 6px square of a month in the stretch. */
  SCATTER_PAD_RIGHT: 24,
  SCATTER_PAD_TOP: 48,
  SCATTER_SQUARE: 6,
});

/* The mantissas of decimal notation. A fact about how numbers are written, not
 * about the market, so they may be literals. Declared in check-literals. */
const TICK_LADDER = Object.freeze([1, 2, 5, 10]);

/* The SVG namespace, read from an element the parser made, so this file holds
 * no URL (tools/check-paths.mjs) and no digit in a string. */
let svgNamespace = null;
function svgNs() {
  if (svgNamespace === null) {
    const holder = document.createElement("div");
    holder.innerHTML = "<svg></svg>";
    svgNamespace = holder.firstChild.namespaceURI;
  }
  return svgNamespace;
}

let idCounter = 0;
/** A document unique id for a title, desc, clip or pattern. */
export function uid(prefix) {
  idCounter += 1;
  return prefix + "-" + String(idCounter);
}

/** An SVG element with attributes. null and undefined attributes are skipped. */
export function svgEl(tag, attrs, text) {
  const node = document.createElementNS(svgNs(), tag);
  for (const [name, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined) continue;
    node.setAttribute(name, String(value));
  }
  if (text !== undefined) node.textContent = text;
  return node;
}

/** A coordinate as an attribute string. */
export function px(value) {
  return value.toFixed(GEOMETRY.COORD_DECIMALS);
}

/** Missing is null, undefined, NaN or an infinity, and never zero. */
export function present(value) {
  return typeof value === "number" && Number.isFinite(value);
}

/** A root svg that is an image with a title and a description, Part 3 section
 *  9: role img, aria-labelledby naming both. */
export function imageSvg({ width, height, title, desc, className }) {
  const titleId = uid("chart-title");
  const descId = uid("chart-desc");
  const svg = svgEl("svg", {
    class: className ? "chart " + className : "chart",
    width,
    height,
    viewBox: [0, 0, width, height].join(" "),
    role: "img",
    "aria-labelledby": titleId + " " + descId,
    focusable: "false",
  });
  svg.appendChild(svgEl("title", { id: titleId }, title));
  svg.appendChild(svgEl("desc", { id: descId }, desc));
  return svg;
}

/** A decorative svg whose values are all printed beside it. */
export function hiddenSvg({ width, height, className }) {
  return svgEl("svg", {
    class: className ? "chart " + className : "chart",
    width,
    height,
    viewBox: [0, 0, width, height].join(" "),
    "aria-hidden": "true",
    focusable: "false",
  });
}

/** A linear map from a domain that came from an artifact to pixels. */
export function linear(domainLow, domainHigh, rangeLow, rangeHigh) {
  const span = domainHigh - domainLow;
  const map = (value) => (span === 0 ? rangeLow : rangeLow + ((value - domainLow) / span) * (rangeHigh - rangeLow));
  map.domain = [domainLow, domainHigh];
  map.range = [rangeLow, rangeHigh];
  return map;
}

/** The power of ten at or below a positive value. */
function powerOfTenBelow(value) {
  return Math.pow(10, Math.floor(Math.log10(value)));
}

/** The round step for about `count` intervals across a span. */
export function tickStep(low, high, count) {
  if (!(high > low) || !(count > 0)) return 0;
  const rough = (high - low) / count;
  const magnitude = powerOfTenBelow(rough);
  for (const rung of TICK_LADDER) {
    if (magnitude * rung >= rough) return magnitude * rung;
  }
  return magnitude * TICK_LADDER[TICK_LADDER.length - 1];
}

/** Tick values across a domain, on the step. */
export function tickValues(low, high, count) {
  const step = tickStep(low, high, count);
  if (step === 0) return [low];
  const places = stepPlaces(step);
  const out = [];
  for (let k = Math.ceil(low / step); k * step <= high; k += 1) {
    out.push(Number((k * step).toFixed(places)));
  }
  return out;
}

/** Widen [low, high] outward to the tick step, so the plot ends on a tick. */
export function niceDomain(low, high, count) {
  const step = tickStep(low, high, count);
  if (step === 0) return [low, high];
  return [Math.floor(low / step) * step, Math.ceil(high / step) * step];
}

/** A tick label with as many places as the step needs and no more. */
export function tickLabel(value, step) {
  return formatNumber(value, "tick", { tick: stepPlaces(step) }, { context: "table" });
}

/** The decimal places a tick step needs: none for a step of one or more. */
function stepPlaces(step) {
  return step > 0 && step < 1 ? Math.ceil(-Math.log10(step)) : 0;
}

/** Redraw on a width change, never scale a viewBox. Part 3 section 2, the LME
 *  onWidthChange pattern. A zero width means the node is not laid out yet, for
 *  example inside a section that is still closed; the observer fires again when
 *  it is. Returns a function that stops watching. */
export function onWidthChange(node, draw) {
  let last = 0;
  const run = () => {
    const width = node.clientWidth;
    if (width === 0 || width === last) return;
    last = width;
    draw(width);
  };
  if (typeof ResizeObserver === "function") {
    const observer = new ResizeObserver(run);
    observer.observe(node);
    run();
    return () => observer.disconnect();
  }
  window.addEventListener("resize", run, { passive: true });
  run();
  return () => window.removeEventListener("resize", run);
}

/** Runs of consecutive present values. `points` is [[x, y], ...] in order.
 *  Returns { runs: [[[x, y], ...], ...], holes: [[xBefore, xAfter], ...] }
 *  where a hole is a missing stretch with a present value on both sides. */
export function splitRuns(points) {
  const runs = [];
  const holes = [];
  let current = [];
  let lastPresentX = null;
  let sawGap = false;
  for (const [x, y] of points) {
    if (present(y)) {
      if (sawGap && lastPresentX !== null) holes.push([lastPresentX, x]);
      current.push([x, y]);
      lastPresentX = x;
      sawGap = false;
    } else {
      if (current.length) runs.push(current);
      current = [];
      if (lastPresentX !== null) sawGap = true;
    }
  }
  if (current.length) runs.push(current);
  return { runs, holes };
}

/** One path per run, never joined across a gap; a run of one point is a dot. */
function drawRuns(group, runs, xOf, yOf, lineClass, dotClass) {
  for (const run of runs) {
    if (run.length === 1) {
      group.appendChild(svgEl("circle", { class: dotClass, cx: px(xOf(run[0][0])), cy: px(yOf(run[0][1])), r: GEOMETRY.ISOLATED_RADIUS }));
      continue;
    }
    const d = run.map(([x, y], index) => (index === 0 ? "M" : "L") + px(xOf(x)) + " " + px(yOf(y))).join(" ");
    group.appendChild(svgEl("path", { class: lineClass, d }));
  }
}

/** The accent dot with its --bg ring, Part 3 section 2, S25. */
function accentDot(group, cx, cy) {
  group.appendChild(svgEl("circle", { class: "mark-ring-fill", cx: px(cx), cy: px(cy), r: GEOMETRY.DOT_RADIUS + GEOMETRY.RING_WIDTH }));
  group.appendChild(svgEl("circle", { class: "mark-accent-dot", cx: px(cx), cy: px(cy), r: GEOMETRY.DOT_RADIUS }));
}

/** Spread labels that want the same column apart, keeping their order. Each
 *  item has y (wanted) and gets y (placed). Symmetric around the group. */
function spreadLabels(items, low, high) {
  const sorted = [...items].sort((a, b) => a.want - b.want);
  for (const item of sorted) item.y = item.want;
  for (let pass = 0; pass < sorted.length; pass += 1) {
    let moved = false;
    for (let index = 1; index < sorted.length; index += 1) {
      const above = sorted[index - 1];
      const below = sorted[index];
      const gap = below.y - above.y;
      if (gap < GEOMETRY.LABEL_SPACING) {
        const push = (GEOMETRY.LABEL_SPACING - gap) * GEOMETRY.HALF;
        above.y -= push;
        below.y += push;
        moved = true;
      }
    }
    if (!moved) break;
  }
  const overflowTop = low - sorted[0].y;
  if (sorted.length && overflowTop > 0) for (const item of sorted) item.y += overflowTop;
  const overflowBottom = sorted.length ? sorted[sorted.length - 1].y - high : 0;
  if (overflowBottom > 0) for (const item of sorted) item.y -= overflowBottom;
  return sorted;
}

/** Runs of consecutive rows where key(row) is the same non null value. */
function runsOf(rows, key) {
  const out = [];
  let current = null;
  for (const row of rows) {
    const value = key(row);
    if (current && value === current.value) {
      current.last = row;
    } else {
      if (current && current.value !== null) out.push(current);
      current = { value, first: row, last: row };
    }
  }
  if (current && current.value !== null) out.push(current);
  return out;
}

/* A bracket in a rail: a line across the weeks, an end tick at each side, and
 * its label. Where the label fits inside the bracket it is centred on the line
 * over a --bg plate, so no text sits on a mark; plateRailLabels decides, once
 * the words can be measured. The bracket's ends travel on the label. */
function bracket(group, x0, x1, y, label) {
  const tick = GEOMETRY.BRACKET_TICK * GEOMETRY.HALF;
  group.appendChild(svgEl("path", {
    class: "mark-context",
    d: "M" + px(x0) + " " + px(y - tick) + " V" + px(y + tick) + " M" + px(x0) + " " + px(y) + " H" + px(x1) + " M" + px(x1) + " " + px(y - tick) + " V" + px(y + tick),
  }));
  // An empty label draws no text node at all. Two brackets on one rail that mean
  // the same thing are labelled once, and an empty <text> would still be placed
  // by plateRailLabels and would take a plate of its own.
  if (!label) return;
  group.appendChild(svgEl("text", {
    class: "chart-caption rail-label",
    x: px((x0 + x1) * GEOMETRY.HALF),
    y: px(y),
    "text-anchor": "middle",
    "dominant-baseline": "central",
    "data-x0": px(x0),
    "data-x1": px(x1),
    "data-y": px(y),
  }, label));
}

/** Place each rail label where it hides no part of its bracket. Text can only
 *  be measured once the svg is in the document, so the caller runs this after
 *  inserting it, and again when the fonts arrive; every run starts from the
 *  centred place, so it measures afresh.
 *
 *  In order of preference (Part 7, C15, M2 of the Gate 4 audit):
 *    1  inside the bracket, centred on a --bg plate the width of its words, when
 *       the plate leaves at least LABEL_GAP of line showing inside each end
 *       tick, so the bracket still reads as a span and not as two arrow heads
 *    2  just right of the bracket, when that stays inside the chart
 *    3  just left of it, likewise
 *    4  on a line of its own under the chart, starting under the bracket
 *  A plate wider than its bracket hid the end ticks, so "4 prior years" read as
 *  running into "none", and a narrow bracket kept only two stubs that looked
 *  like arrows. */
export function plateRailLabels(svg) {
  const g = GEOMETRY;
  for (const plate of svg.querySelectorAll(".rail-plate")) plate.remove();
  const width = Number(svg.getAttribute("width"));
  if (!svg.hasAttribute("data-base-height")) svg.setAttribute("data-base-height", svg.getAttribute("height"));
  const baseHeight = Number(svg.getAttribute("data-base-height"));
  let lines = 0;
  for (const label of svg.querySelectorAll(".rail-label")) {
    const x0 = Number(label.getAttribute("data-x0"));
    const x1 = Number(label.getAttribute("data-x1"));
    label.setAttribute("x", px((x0 + x1) * g.HALF));
    label.setAttribute("y", label.getAttribute("data-y"));
    label.setAttribute("text-anchor", "middle");
    let box;
    try {
      box = label.getBBox();
    } catch (error) {
      continue;
    }
    if (!box || box.width === 0) continue;
    const pad = g.TICK_LENGTH;
    if (box.x - pad > x0 + g.LABEL_GAP && box.x + box.width + pad < x1 - g.LABEL_GAP) {
      label.parentNode.insertBefore(svgEl("rect", {
        class: "mark-ring-fill rail-plate",
        x: px(box.x - pad),
        y: px(box.y),
        width: px(box.width + pad + pad),
        height: px(box.height),
      }), label);
    } else if (x1 + g.LABEL_GAP + box.width <= width) {
      label.setAttribute("x", px(x1 + g.LABEL_GAP));
      label.setAttribute("text-anchor", "start");
    } else if (x0 - g.LABEL_GAP - box.width >= 0) {
      label.setAttribute("x", px(x0 - g.LABEL_GAP));
      label.setAttribute("text-anchor", "end");
    } else {
      label.setAttribute("x", px(Math.max(0, Math.min(x0, width - box.width))));
      label.setAttribute("y", px(baseHeight + lines * g.RAIL_HEIGHT + g.RAIL_HEIGHT * g.HALF));
      label.setAttribute("text-anchor", "start");
      lines += 1;
    }
  }
  const height = baseHeight + lines * g.RAIL_HEIGHT;
  svg.setAttribute("height", String(height));
  svg.setAttribute("viewBox", [0, 0, width, height].join(" "));
}

/* A hatch pattern with a unique id, 45 degree strokes in the context role. */
function hatchPattern(defs) {
  const id = uid("hatch");
  const pattern = svgEl("pattern", {
    id,
    patternUnits: "userSpaceOnUse",
    width: GEOMETRY.HATCH_PITCH,
    height: GEOMETRY.HATCH_PITCH,
    patternTransform: "rotate(" + String(GEOMETRY.HATCH_ANGLE) + ")",
  });
  pattern.appendChild(svgEl("line", { class: "mark-hatch", x1: 0, y1: 0, x2: 0, y2: GEOMETRY.HATCH_PITCH }));
  defs.appendChild(pattern);
  return id;
}

/* ============================================================ seasonal === */

/** One seasonal panel, docs/design.md Part 3 section 3.
 *
 *  panel     cracks.json panels[product]: weeks rows, year_order, current_year,
 *            line_style
 *  yDomain   [low, high], shared by both panels so the weaker leg looks weaker
 *            by its level and not by a paler ink
 *  words     { title, desc, unit, weekAxis, priorYears(n), none, leastDefended,
 *              noSecondChart, currentLabel(value) } built by the caller from
 *              the artifact
 *  least     the evidence class the hatch marks, from series_note
 *  newest    the evidence class the bracket marks
 *  decimals  the artifact's conventions.decimals
 */
export function seasonalPanel({ width, panel, yDomain, words, least, newest, decimals }) {
  const g = GEOMETRY;
  const rows = panel.weeks;
  // Column positions come from the artifact's own column list.
  const WEEK = panel.columns.indexOf("week");
  const N_YEARS = panel.columns.indexOf("n_years");
  const VALUES = panel.columns.indexOf("values_by_year");
  const EVIDENCE = panel.columns.indexOf("evidence_class_by_year");
  const PRINTED = panel.columns.indexOf("printed_usd_bbl_by_year");
  const years = panel.year_order;
  const currentIndex = years.indexOf(panel.current_year);

  const leastRuns = years.map((year, index) => ({ year, runs: runsOf(rows, (row) => (row[EVIDENCE][index] === least ? least : null)) })).filter((lane) => lane.runs.length);
  const newestRuns = years.map((year, index) => ({ year, runs: runsOf(rows, (row) => (row[EVIDENCE][index] === newest ? newest : null)) })).filter((lane) => lane.runs.length);
  const rails = 1 + (leastRuns.length ? 1 : 0) + (newestRuns.length ? 1 : 0);

  const left = g.PAD_LEFT;
  const right = Math.max(width - g.PAD_RIGHT, left + g.PAD_RIGHT);
  const top = g.PAD_TOP;
  const bottom = top + g.PANEL_HEIGHT;
  const railTop = bottom + g.AXIS_GAP + g.AXIS_BELOW;
  const height = railTop + rails * g.RAIL_HEIGHT;

  const firstWeek = rows[0][WEEK];
  const lastWeek = rows[rows.length - 1][WEEK];
  const xOf = linear(firstWeek, lastWeek, left, right);
  const yOf = linear(yDomain[0], yDomain[1], bottom, top);
  const halfWeek = (right - left) / Math.max(lastWeek - firstWeek, 1) * g.HALF;

  const svg = imageSvg({ width, height, title: words.title, desc: words.desc, className: "chart--seasonal" });
  const defs = svgEl("defs");
  svg.appendChild(defs);
  const frame = svgEl("g", { "aria-hidden": "true" });
  const marks = svgEl("g", { "aria-hidden": "true" });
  const labels = svgEl("g", { "aria-hidden": "true" });
  svg.appendChild(frame);
  svg.appendChild(marks);
  svg.appendChild(labels);

  // Axes: horizontal gridlines at y ticks, the unit said once above them.
  const yStep = tickStep(yDomain[0], yDomain[1], g.Y_TICKS);
  for (const value of tickValues(yDomain[0], yDomain[1], g.Y_TICKS)) {
    const y = yOf(value);
    frame.appendChild(svgEl("line", { class: value === 0 ? "mark-context" : "mark-grid", x1: left, x2: right, y1: px(y), y2: px(y) }));
    frame.appendChild(svgEl("text", { class: "tick", x: left - g.LABEL_GAP, y: px(y), "text-anchor": "end", "dominant-baseline": "central" }, tickLabel(value, yStep)));
  }
  frame.appendChild(svgEl("text", { class: "chart-axis-title", x: left - g.LABEL_GAP, y: top - g.LABEL_GAP - g.TICK_LENGTH, "text-anchor": "end" }, words.unit));
  const xStep = tickStep(firstWeek, lastWeek, g.X_TICKS);
  const tickY = bottom + g.AXIS_GAP;
  for (const value of tickValues(firstWeek, lastWeek, g.X_TICKS)) {
    const x = xOf(value);
    frame.appendChild(svgEl("line", { class: "mark-context", x1: px(x), x2: px(x), y1: bottom, y2: bottom + g.TICK_LENGTH }));
    frame.appendChild(svgEl("text", { class: "tick", x: px(x), y: px(tickY), "text-anchor": "middle", "dominant-baseline": "central" }, tickLabel(value, xStep)));
  }
  frame.appendChild(svgEl("text", { class: "chart-axis-title", x: left - g.LABEL_GAP, y: px(tickY), "text-anchor": "end", "dominant-baseline": "central" }, words.weekAxis));
  frame.appendChild(svgEl("line", { class: "mark-context", x1: left, x2: right, y1: bottom, y2: bottom }));

  // Lines: prior years first, thin and muted; the current year last, in ink.
  const endLabels = [];
  years.forEach((year, index) => {
    const isCurrent = index === currentIndex;
    const points = rows.map((row) => [row[WEEK], row[VALUES][index]]);
    const { runs, holes } = splitRuns(points);
    if (!runs.length) return;
    const group = svgEl("g", { class: isCurrent ? "series-current series-" + panel.line_style : "series-prior" });
    drawRuns(group, runs, xOf, yOf, isCurrent ? "mark-series" : "mark-context", isCurrent ? "mark-series-fill" : "mark-context-fill");
    for (const [x0, x1] of holes) {
      group.appendChild(svgEl("line", { class: "mark-gap", x1: px(xOf(x0)), x2: px(xOf(x1)), y1: bottom, y2: bottom }));
    }
    marks.appendChild(group);
    const lastRun = runs[runs.length - 1];
    const [lx, ly] = lastRun[lastRun.length - 1];
    endLabels.push({
      x: xOf(lx),
      pointY: yOf(ly),
      want: yOf(ly),
      current: isCurrent,
      text: isCurrent ? words.currentLabel(year, ly) : formatNumber(year, "year", decimals),
    });
  });

  // Printed weeks: squares on top of the line at the printed value, never joined.
  const half = g.SQUARE * g.HALF;
  years.forEach((year, index) => {
    for (const row of rows) {
      const value = row[PRINTED][index];
      if (!present(value)) continue;
      marks.appendChild(svgEl("rect", { class: "mark-printed", x: px(xOf(row[WEEK]) - half), y: px(yOf(value) - half), width: g.SQUARE, height: g.SQUARE }));
    }
  });

  // The accent, once: the current year's latest week, with its ring.
  const current = endLabels.find((label) => label.current);
  if (current) accentDot(marks, current.x, current.pointY);

  // End labels. Labels that share a column are spread apart, with a leader to
  // each point that moved. All sit on a --bg halo where they cross a line.
  const columns = new Map();
  for (const label of endLabels) {
    const key = px(label.x);
    if (!columns.has(key)) columns.set(key, []);
    columns.get(key).push(label);
  }
  for (const group of columns.values()) {
    for (const label of spreadLabels(group, top, bottom)) {
      const tx = label.x + g.LABEL_GAP;
      if (Math.abs(label.y - label.pointY) >= 1) {
        labels.appendChild(svgEl("line", { class: "mark-context", x1: px(label.x), y1: px(label.pointY), x2: px(tx - g.TICK_LENGTH), y2: px(label.y) }));
      }
      labels.appendChild(svgEl("text", {
        class: label.current ? "chart-end-label halo" : "chart-caption halo",
        x: px(tx),
        y: px(label.y),
        "dominant-baseline": "central",
      }, label.text));
    }
  }

  // Rails, from fields and never from dates: depth, then the two evidence lanes.
  let railY = railTop + g.RAIL_HEIGHT * g.HALF;
  const railGroup = svgEl("g", { "aria-hidden": "true" });
  svg.appendChild(railGroup);
  for (const run of runsOf(rows, (row) => row[N_YEARS])) {
    const x0 = Math.max(xOf(run.first[WEEK]) - halfWeek, left);
    const x1 = Math.min(xOf(run.last[WEEK]) + halfWeek, right);
    bracket(railGroup, x0, x1, railY, run.value === 0 ? words.none : words.priorYears(run.value));
  }
  if (leastRuns.length) {
    railY += g.RAIL_HEIGHT;
    const patternId = hatchPattern(defs);
    for (const lane of leastRuns) {
      for (const run of lane.runs) {
        let x0 = xOf(run.first[WEEK]) - halfWeek;
        let x1 = xOf(run.last[WEEK]) + halfWeek;
        if (x1 - x0 < g.HATCH_MIN_WIDTH) {
          const mid = (x0 + x1) * g.HALF;
          x0 = mid - g.HATCH_MIN_WIDTH * g.HALF;
          x1 = mid + g.HATCH_MIN_WIDTH * g.HALF;
        }
        const railHalf = (g.RAIL_HEIGHT - g.TICK_LENGTH) * g.HALF;
        railGroup.appendChild(svgEl("rect", { class: "mark-hatch-area", x: px(x0), y: px(railY - railHalf), width: px(x1 - x0), height: px(railHalf + railHalf), fill: "url(#" + patternId + ")" }));
        railGroup.appendChild(svgEl("text", { class: "chart-caption", x: px(x1 + g.LABEL_GAP), y: px(railY), "dominant-baseline": "central" }, words.leastDefended(lane.year)));
      }
    }
  }
  if (newestRuns.length) {
    railY += g.RAIL_HEIGHT;
    for (const lane of newestRuns) {
      for (const run of lane.runs) {
        bracket(railGroup, xOf(run.first[WEEK]) - halfWeek, xOf(run.last[WEEK]) + halfWeek, railY, words.noSecondChart(lane.year));
      }
    }
  }
  return svg;
}

/* =========================================================== waterfall === */

/** One waterfall row's bar, Part 3 section 4. The figure is printed in the
 *  row, so the bar is hidden from assistive technology.
 *
 *  row      a margin-stack.json row: kind, start_usd_bbl, end_usd_bbl, accent
 *  previous the row before it, or null, for the connector
 *  isLast   no connector below the last row
 *  scale    [low, high] from margin-stack.json scale
 */
export function waterfallBar({ width, height, row, previous, isLast, scale }) {
  const g = GEOMETRY;
  const svg = hiddenSvg({ width, height, className: "chart--bar" });
  const inset = g.SMALL_RADIUS + g.RING_WIDTH;
  const xOf = linear(scale[0], scale[1], inset, Math.max(width - inset, inset));
  const barTop = (height - g.BAR_THICKNESS) * g.HALF;
  const barBottom = barTop + g.BAR_THICKNESS;

  // The zero rule, the height of the row, so it runs the height of the block.
  const zero = xOf(0);
  svg.appendChild(svgEl("line", { class: "mark-context", x1: px(zero), x2: px(zero), y1: 0, y2: height }));

  // Connectors at the running total, decorative: where the last bar ended,
  // and where this one ends for the next.
  if (previous) {
    const x = xOf(previous.end_usd_bbl);
    svg.appendChild(svgEl("line", { class: "mark-connector", x1: px(x), x2: px(x), y1: 0, y2: px(barTop) }));
  }
  if (!isLast) {
    const x = xOf(row.end_usd_bbl);
    svg.appendChild(svgEl("line", { class: "mark-connector", x1: px(x), x2: px(x), y1: px(barBottom), y2: height }));
  }

  const from = xOf(Math.min(row.start_usd_bbl, row.end_usd_bbl));
  const to = xOf(Math.max(row.start_usd_bbl, row.end_usd_bbl));
  const negative = row.end_usd_bbl < row.start_usd_bbl;
  const middle = (barTop + barBottom) * g.HALF;

  if (row.kind === "total") {
    svg.appendChild(svgEl("rect", {
      class: row.accent ? "mark-accent-bar" : "mark-series-fill",
      x: px(from), y: px(barTop), width: px(Math.max(to - from, 0)), height: g.BAR_THICKNESS,
    }));
    return svg;
  }
  if (to - from < g.SMALL_STEP) {
    svg.appendChild(svgEl("circle", {
      class: negative ? "mark-negative" : "mark-series-fill",
      cx: px(xOf(row.end_usd_bbl)), cy: px(middle), r: g.SMALL_RADIUS,
    }));
    return svg;
  }
  if (negative) {
    svg.appendChild(svgEl("rect", {
      class: "mark-negative",
      x: px(from + g.OUTLINE_INSET), y: px(barTop + g.OUTLINE_INSET),
      width: px(to - from - g.OUTLINE_INSET - g.OUTLINE_INSET), height: px(g.BAR_THICKNESS - g.OUTLINE_INSET - g.OUTLINE_INSET),
    }));
  } else {
    svg.appendChild(svgEl("rect", { class: "mark-series-fill", x: px(from), y: px(barTop), width: px(to - from), height: g.BAR_THICKNESS }));
  }
  return svg;
}

/** The smallest value on the 1, 2, 5, 10 ladder at or above a positive value,
 *  for a scale that widens when an edit runs past it (docs/design.md Part 8.2,
 *  M10). Zero or less gives zero. */
export function ladderCeil(value) {
  if (!(value > 0)) return 0;
  const magnitude = powerOfTenBelow(value);
  for (const rung of TICK_LADDER) {
    if (magnitude * rung >= value) return magnitude * rung;
  }
  return magnitude * TICK_LADDER[TICK_LADDER.length - 1];
}

/** A waterfall bar that is built once and moved in place, for the Model view's
 *  live recompute (docs/design.md Part 8.2, M9). The same marks as waterfallBar,
 *  the same geometry, but every mark exists from the start and set() moves it:
 *  horizontal position through a CSS transform and width through the CSS width
 *  property, both of which styles/components.css tweens at --t-fast and the
 *  reduced motion block takes to nothing. A step narrower than SMALL_STEP
 *  swaps to its circle at once, because a rectangle cannot tween into a circle.
 *
 *  set({ width, height, row, previous, isLast, scale, still })
 *    row       { kind: "step" | "total", start_usd_bbl, end_usd_bbl, accent }
 *              or null for a row with nothing to draw, which hides every mark
 *    previous  the row above, for the connector, or null
 *    still     true to move without the tween, for a change of cell size */
export function liveWaterfallBar() {
  const g = GEOMETRY;
  const svg = hiddenSvg({ width: 0, height: 0, className: "chart--bar chart--live" });
  const zero = svg.appendChild(svgEl("line", { class: "mark-context live-mark", x1: 0, x2: 0, y1: 0 }));
  const above = svg.appendChild(svgEl("line", { class: "mark-connector live-mark", x1: 0, x2: 0, y1: 0 }));
  const below = svg.appendChild(svgEl("line", { class: "mark-connector live-mark", x1: 0, x2: 0 }));
  const fill = svg.appendChild(svgEl("rect", { class: "mark-series-fill live-mark", x: 0 }));
  const outline = svg.appendChild(svgEl("rect", { class: "mark-negative live-mark", x: 0 }));
  const dot = svg.appendChild(svgEl("circle", { class: "mark-series-fill live-mark", cx: 0, r: g.SMALL_RADIUS }));
  const show = (node, on) => node.setAttribute("display", on ? "inline" : "none");
  const at = (node, x) => { node.style.transform = "translate(" + px(x) + "px, 0px)"; };
  const wide = (node, w) => {
    node.setAttribute("width", px(w));
    node.style.width = px(w) + "px";
  };

  function set({ width, height, row, previous, isLast, scale, still }) {
    svg.classList.toggle("is-still", still === true);
    svg.setAttribute("width", width);
    svg.setAttribute("height", height);
    svg.setAttribute("viewBox", [0, 0, width, height].join(" "));
    const inset = g.SMALL_RADIUS + g.RING_WIDTH;
    const xOf = linear(scale[0], scale[1], inset, Math.max(width - inset, inset));
    const barTop = (height - g.BAR_THICKNESS) * g.HALF;
    const barBottom = barTop + g.BAR_THICKNESS;
    const drawable = row && present(row.start_usd_bbl) && present(row.end_usd_bbl);

    show(zero, drawable);
    zero.setAttribute("y2", height);
    at(zero, xOf(0));

    const hasAbove = drawable && previous && present(previous.end_usd_bbl);
    show(above, hasAbove);
    above.setAttribute("y2", px(barTop));
    if (hasAbove) at(above, xOf(previous.end_usd_bbl));

    show(below, drawable && !isLast);
    below.setAttribute("y1", px(barBottom));
    below.setAttribute("y2", height);
    if (drawable) at(below, xOf(row.end_usd_bbl));

    if (!drawable) {
      [fill, outline, dot].forEach((node) => show(node, false));
      return;
    }
    const from = xOf(Math.min(row.start_usd_bbl, row.end_usd_bbl));
    const to = xOf(Math.max(row.start_usd_bbl, row.end_usd_bbl));
    const negative = row.end_usd_bbl < row.start_usd_bbl;
    const isTotal = row.kind === "total";
    const small = !isTotal && to - from < g.SMALL_STEP;

    fill.setAttribute("class", (isTotal && row.accent ? "mark-accent-bar" : "mark-series-fill") + " live-mark");
    show(fill, !small && (isTotal || !negative));
    fill.setAttribute("y", px(barTop));
    fill.setAttribute("height", g.BAR_THICKNESS);
    at(fill, from);
    wide(fill, Math.max(to - from, 0));

    show(outline, !small && !isTotal && negative);
    outline.setAttribute("y", px(barTop + g.OUTLINE_INSET));
    outline.setAttribute("height", px(g.BAR_THICKNESS - g.OUTLINE_INSET - g.OUTLINE_INSET));
    at(outline, from + g.OUTLINE_INSET);
    wide(outline, Math.max(to - from - g.OUTLINE_INSET - g.OUTLINE_INSET, 0));

    show(dot, small);
    dot.setAttribute("class", (negative ? "mark-negative" : "mark-series-fill") + " live-mark");
    dot.setAttribute("cy", px((barTop + barBottom) * g.HALF));
    at(dot, xOf(row.end_usd_bbl));
  }
  return { svg, set };
}

/* ============================================================== strips === */

/** The shared domain of a set of intervals, zero always inside. */
export function stripDomain(intervals) {
  let low = 0;
  let high = 0;
  for (const item of intervals) {
    if (present(item.low)) low = Math.min(low, item.low);
    if (present(item.high)) high = Math.max(high, item.high);
  }
  return [low, high];
}

/* One interval row: the interval as a line with end ticks, the estimate as a
 * dot with a --bg ring. The accent zero rule is drawn once by the caller. */
function intervalRow(group, xOf, y, item) {
  const g = GEOMETRY;
  if (!present(item.low) || !present(item.high) || !present(item.estimate)) return;
  const tick = g.STRIP_END_TICK * g.HALF;
  const x0 = xOf(item.low);
  const x1 = xOf(item.high);
  group.appendChild(svgEl("path", {
    class: "mark-interval",
    d: "M" + px(x0) + " " + px(y - tick) + " V" + px(y + tick) + " M" + px(x0) + " " + px(y) + " H" + px(x1) + " M" + px(x1) + " " + px(y - tick) + " V" + px(y + tick),
  }));
  const cx = xOf(item.estimate);
  group.appendChild(svgEl("circle", { class: "mark-ring-fill", cx: px(cx), cy: px(y), r: g.DOT_RADIUS + g.RING_WIDTH }));
  group.appendChild(svgEl("circle", { class: "mark-series-fill", cx: px(cx), cy: px(y), r: g.DOT_RADIUS }));
}

/* The accent zero rule over one interval row, from y1 to y2. Where the rule
 * crosses the ink interval line, a --bg ring under it separates the two: accent
 * against ink is 2.14 in light (S25, Part 7 C15). The ring is drawn only where
 * the line actually crosses zero, so an interval that stops short of zero keeps
 * its end tick whole, however close to the rule it sits. */
function zeroRule(group, x, y1, y2, rowY, item) {
  const g = GEOMETRY;
  if (present(item.low) && present(item.high) && item.low < 0 && item.high > 0) {
    const reach = g.STRIP_END_TICK * g.HALF;
    group.appendChild(svgEl("line", { class: "mark-accent-rule-ring", x1: px(x), x2: px(x), y1: px(rowY - reach), y2: px(rowY + reach) }));
  }
  group.appendChild(svgEl("line", { class: "mark-accent-rule", x1: px(x), x2: px(x), y1: px(y1), y2: px(y2) }));
}

/** An interval strip for one table row, hidden, Part 3 section 5. */
export function intervalCell({ width, height, item, domain }) {
  const g = GEOMETRY;
  const svg = hiddenSvg({ width, height, className: "chart--strip" });
  const inset = g.DOT_RADIUS + g.RING_WIDTH;
  const xOf = linear(domain[0], domain[1], inset, Math.max(width - inset, inset));
  intervalRow(svg, xOf, height * g.HALF, item);
  zeroRule(svg, xOf(0), 0, height, height * g.HALF, item);
  return svg;
}

/** The interval strips as one figure above the table at narrow widths, an
 *  image with a title and description. Each row labelled at its left end.
 *
 *  The accent zero rule runs through each interval row and stops at the label
 *  line above the next, so it never crosses a label: S6 of the Gate 4 audit
 *  measured it through "Crude intake with a trend" at 375 px. Part 7, C15. */
export function intervalFigure({ width, items, domain, title, desc }) {
  const g = GEOMETRY;
  const rowHeight = g.STRIP_LABEL + g.STRIP_ROW;
  const height = items.length * rowHeight + g.STRIP_PAD;
  const svg = imageSvg({ width, height, title, desc, className: "chart--strip-figure" });
  const inset = g.DOT_RADIUS + g.RING_WIDTH;
  const xOf = linear(domain[0], domain[1], inset, Math.max(width - inset, inset));
  const zero = xOf(0);
  const group = svgEl("g", { "aria-hidden": "true" });
  items.forEach((item, index) => {
    const top = index * rowHeight;
    const rowTop = top + g.STRIP_LABEL;
    const rowY = rowTop + g.STRIP_ROW * g.HALF;
    group.appendChild(svgEl("text", { class: "chart-caption-strong", x: 0, y: px(top + g.STRIP_LABEL * g.HALF), "dominant-baseline": "central" }, item.label));
    intervalRow(group, xOf, rowY, item);
    zeroRule(group, zero, rowTop, rowTop + g.STRIP_ROW, rowY, item);
  });
  svg.appendChild(group);
  return svg;
}

/* ============================================================= history === */

/** Milliseconds for an ISO date, at UTC midnight, or NaN. */
export function timeOf(iso) {
  const [year, month, day] = String(iso).split("-").map(Number);
  return Date.UTC(year, month - 1, day);
}

/* Year boundaries across a time domain, every `step` years, as [ms, year]. */
function yearTicks(t0, t1, step) {
  const first = new Date(t0).getUTCFullYear();
  const last = new Date(t1).getUTCFullYear();
  const out = [];
  for (let year = first; year <= last; year += 1) {
    if (year % step !== 0) continue;
    const t = Date.UTC(year, 0, 1);
    if (t >= t0 && t <= t1) out.push([t, year]);
  }
  return out;
}

/* Split a line's points at its breaks: a break at time b ends the path before
 * the first point at or after b. Nothing marks the baseline, because a break is
 * not missing data; a gap inside a piece is still marked by splitRuns. */
function splitAtBreaks(points, breaks) {
  const pieces = [];
  let current = [];
  const sorted = [...breaks].sort((a, b) => a - b);
  let next = 0;
  for (const point of points) {
    let crossed = false;
    while (next < sorted.length && point[0] >= sorted[next]) {
      crossed = true;
      next += 1;
    }
    if (crossed && current.length) {
      pieces.push(current);
      current = [];
    }
    current.push(point);
  }
  if (current.length) pieces.push(current);
  return pieces;
}

/** A History time plot, docs/design.md Part 3 section 2 and Part 8.1.
 *
 *  width, height      the svg's width and the plot's height, in CSS px
 *  xDomain, yDomain   [low, high]: ms for x, the unit for y
 *  unit               the axis title, for example "$/bbl"
 *  title, desc        the chart's accessible name and description
 *  lines              [{ points: [[ms, value]], style: "solid" | "dashed",
 *                        name, lastText, breaks: [ms], accent }]
 *  squares            [[ms, value]] printed figures, 5px squares, never joined
 *  events, breaks     [ms] for the event hairlines and the dashed break rules
 *  rails              { least: [[ms, ms]], newest: [[ms, ms]], leastLabel,
 *                       newestLabel, brackets: [{ start, end, label }] }, the
 *                       evidence rail under the axis, or null; brackets are
 *                       named spans on a rail of their own
 *  xTicks             optional [{ t, label, key }]: numeric x labels the caller
 *                       names, in place of the Januaries, thinned on the 1, 2,
 *                       5, 10 ladder by the integer key, so key 0 is always
 *                       kept. The Events view's months from the event, Part 8.4
 *  marker             optional ms: the one accent rule on the plot, the event
 *                       the plot exists for, Part 8.4 E5
 *  labelAtEnd         optional: an end label sits just after its line's own
 *                       last point, with no leader, rather than at the right
 *                       edge, so a line that stops early is not drawn on to
 *                       the edge by its leader, Part 8.4 E6
 *  Returns { svg, xOf, yOf, left, right, top, bottom }. */
export function timePanel({ width, height, xDomain, yDomain, unit, title, desc, lines, squares, events, breaks, rails, className, xTicks, marker, labelAtEnd }) {
  const g = GEOMETRY;
  const least = rails ? rails.least.filter(([t0, t1]) => t1 >= xDomain[0] && t0 <= xDomain[1]) : [];
  const newest = rails ? rails.newest.filter(([t0, t1]) => t1 >= xDomain[0] && t0 <= xDomain[1]) : [];
  const brackets = rails && rails.brackets ? rails.brackets.filter((b) => b.end >= xDomain[0] && b.start <= xDomain[1]) : [];
  const railCount = (least.length ? 1 : 0) + (newest.length ? 1 : 0) + (brackets.length ? 1 : 0);
  const left = g.PAD_LEFT;
  const right = Math.max(width - g.TIME_PAD_RIGHT, left + g.TIME_PAD_RIGHT);
  const top = g.PAD_TOP;
  const bottom = top + height;
  const railTop = bottom + g.AXIS_GAP + g.AXIS_BELOW;
  const total = railTop + railCount * g.RAIL_HEIGHT;
  const xOf = linear(xDomain[0], xDomain[1], left, right);
  const yOf = linear(yDomain[0], yDomain[1], bottom, top);

  const svg = imageSvg({ width, height: total, title, desc, className: className ? "chart--time " + className : "chart--time" });
  const defs = svgEl("defs");
  svg.appendChild(defs);
  const frame = svgEl("g", { "aria-hidden": "true" });
  const rules = svgEl("g", { "aria-hidden": "true" });
  const marks = svgEl("g", { "aria-hidden": "true" });
  const labels = svgEl("g", { "aria-hidden": "true" });
  svg.appendChild(frame);
  svg.appendChild(rules);
  svg.appendChild(marks);
  svg.appendChild(labels);

  // y: gridlines at ticks, zero in the context role, the unit said once.
  const yStep = tickStep(yDomain[0], yDomain[1], g.Y_TICKS);
  for (const value of tickValues(yDomain[0], yDomain[1], g.Y_TICKS)) {
    const y = yOf(value);
    frame.appendChild(svgEl("line", { class: value === 0 ? "mark-context" : "mark-grid", x1: left, x2: right, y1: px(y), y2: px(y) }));
    frame.appendChild(svgEl("text", { class: "tick", x: left - g.LABEL_GAP, y: px(y), "text-anchor": "end", "dominant-baseline": "central" }, tickLabel(value, yStep)));
  }
  frame.appendChild(svgEl("text", { class: "chart-axis-title", x: left - g.LABEL_GAP, y: top - g.LABEL_GAP - g.TICK_LENGTH, "text-anchor": "end" }, unit));

  // x: a label at each January, on the smallest 1, 2, 5 or 10 year step that
  // keeps two labels YEAR_SPACING apart; or the caller's own ticks, thinned
  // the same way by their integer key.
  const candidates = xTicks
    ? xTicks.filter((tick) => tick.t >= xDomain[0] && tick.t <= xDomain[1])
    : yearTicks(xDomain[0], xDomain[1], TICK_LADDER[0]).map(([t, year]) => ({ t, label: String(year), key: year }));
  let step = TICK_LADDER[TICK_LADDER.length - 1];
  for (const rung of TICK_LADDER) {
    if ((right - left) / Math.max(candidates.length / rung, TICK_LADDER[0]) >= g.YEAR_SPACING) {
      step = rung;
      break;
    }
  }
  const tickY = bottom + g.AXIS_GAP;
  for (const tick of candidates) {
    if (tick.key % step !== 0) continue;
    const x = xOf(tick.t);
    frame.appendChild(svgEl("line", { class: "mark-context", x1: px(x), x2: px(x), y1: bottom, y2: bottom + g.TICK_LENGTH }));
    frame.appendChild(svgEl("text", { class: "tick", x: px(x), y: px(tickY), "text-anchor": "middle", "dominant-baseline": "central" }, tick.label));
  }
  frame.appendChild(svgEl("line", { class: "mark-context", x1: left, x2: right, y1: bottom, y2: bottom }));

  // Events: a quiet full height hairline and a findable tick at the top edge.
  for (const t of events || []) {
    if (t < xDomain[0] || t > xDomain[1]) continue;
    const x = px(xOf(t));
    rules.appendChild(svgEl("line", { class: "mark-decor", x1: x, x2: x, y1: top, y2: bottom }));
    rules.appendChild(svgEl("line", { class: "mark-context", x1: x, x2: x, y1: top - g.TICK_LENGTH, y2: top }));
  }
  // Breaks: a dashed rule in the context role; the line itself is split below.
  for (const t of breaks || []) {
    if (t < xDomain[0] || t > xDomain[1]) continue;
    const x = px(xOf(t));
    rules.appendChild(svgEl("line", { class: "mark-break", x1: x, x2: x, y1: top - g.TICK_LENGTH, y2: bottom }));
  }

  // The event the plot exists for: one accent rule, the height of the plot.
  if (marker !== undefined && marker !== null && marker >= xDomain[0] && marker <= xDomain[1]) {
    const x = px(xOf(marker));
    rules.appendChild(svgEl("line", { class: "mark-event", x1: x, x2: x, y1: top - g.TICK_LENGTH, y2: bottom }));
  }

  // Lines, each split at its own breaks and at every gap, never joined.
  const ends = [];
  for (const line of lines) {
    const inRange = line.points.filter(([t]) => t >= xDomain[0] && t <= xDomain[1]);
    if (!inRange.length) continue;
    const group = svgEl("g", { class: "series-current series-" + line.style });
    for (const piece of splitAtBreaks(inRange, line.breaks || [])) {
      const split = splitRuns(piece);
      drawRuns(group, split.runs, xOf, yOf, "mark-series", "mark-series-fill");
      for (const [x0, x1] of split.holes) {
        group.appendChild(svgEl("line", { class: "mark-gap", x1: px(xOf(x0)), x2: px(xOf(x1)), y1: bottom, y2: bottom }));
      }
    }
    marks.appendChild(group);
    const last = [...inRange].reverse().find(([, v]) => present(v));
    if (last) ends.push({ x: xOf(last[0]), pointY: yOf(last[1]), want: yOf(last[1]), line, accent: line.accent === true });
  }

  const half = g.SQUARE * g.HALF;
  for (const [t, value] of squares || []) {
    if (t < xDomain[0] || t > xDomain[1] || !present(value)) continue;
    marks.appendChild(svgEl("rect", { class: "mark-printed", x: px(xOf(t) - half), y: px(yOf(value) - half), width: g.SQUARE, height: g.SQUARE }));
  }
  for (const end of ends) if (end.accent) accentDot(marks, end.x, end.pointY);

  // End labels: the product name, and its last value on a second line, spread
  // apart with a leader where they crowd, on a --bg halo.
  const lineHeight = g.LABEL_SPACING;
  const wanted = spreadPairs(ends.map((end) => ({ end, y: end.pointY })), lineHeight, top + lineHeight * g.HALF, bottom);
  for (const label of wanted) {
    const end = label.end;
    const tx = (labelAtEnd ? end.x : right) + g.LABEL_GAP;
    if (Math.abs(label.y - end.pointY) >= 1 || (!labelAtEnd && Math.abs(end.x - right) >= 1)) {
      labels.appendChild(svgEl("line", { class: "mark-context", x1: px(end.x), y1: px(end.pointY), x2: px(tx - g.TICK_LENGTH), y2: px(label.y) }));
    }
    const text = svgEl("text", { class: "chart-end-label halo", x: px(tx), y: px(label.y - lineHeight * g.HALF), "dominant-baseline": "central" });
    text.appendChild(svgEl("tspan", { x: px(tx) }, end.line.name));
    text.appendChild(svgEl("tspan", { x: px(tx), dy: lineHeight, class: "chart-end-value" }, end.line.lastText));
    labels.appendChild(text);
  }

  // The evidence rail, from the classes the artifact carries, never from dates.
  if (railCount) {
    const railGroup = svgEl("g", { "aria-hidden": "true" });
    svg.appendChild(railGroup);
    let railY = railTop + g.RAIL_HEIGHT * g.HALF;
    const clip = (t0, t1) => [Math.max(xOf(Math.max(t0, xDomain[0])), left), Math.min(xOf(Math.min(t1, xDomain[1])), right)];
    if (least.length) {
      const patternId = hatchPattern(defs);
      for (const [t0, t1] of least) {
        let [x0, x1] = clip(t0, t1);
        if (x1 - x0 < g.HATCH_MIN_WIDTH) {
          const mid = (x0 + x1) * g.HALF;
          x0 = mid - g.HATCH_MIN_WIDTH * g.HALF;
          x1 = mid + g.HATCH_MIN_WIDTH * g.HALF;
        }
        const railHalf = (g.RAIL_HEIGHT - g.TICK_LENGTH) * g.HALF;
        railGroup.appendChild(svgEl("rect", { class: "mark-hatch-area", x: px(x0), y: px(railY - railHalf), width: px(x1 - x0), height: px(railHalf + railHalf), fill: "url(#" + patternId + ")" }));
        railGroup.appendChild(svgEl("text", { class: "chart-caption", x: px(x1 + g.LABEL_GAP), y: px(railY), "dominant-baseline": "central" }, rails.leastLabel));
      }
      railY += g.RAIL_HEIGHT;
    }
    for (const [t0, t1] of newest) {
      const [x0, x1] = clip(t0, t1);
      bracket(railGroup, x0, x1, railY, rails.newestLabel);
    }
    if (newest.length) railY += g.RAIL_HEIGHT;
    // Named spans, each with its own words: the Runs view's 2022 episode and
    // the months after the 2026 break, Part 8.3 R7.
    for (const item of brackets) {
      const [x0, x1] = clip(item.start, item.end);
      bracket(railGroup, x0, x1, railY, item.label);
    }
  }
  return { svg, xOf, yOf, left, right, top, bottom };
}

/* Two line end labels, each two lines tall, need two line heights between
 * their centres. Pushed apart symmetrically, then kept inside [low, high]. */
function spreadPairs(items, lineHeight, low, high) {
  const sorted = [...items].sort((a, b) => a.y - b.y);
  const need = lineHeight + lineHeight + GEOMETRY.TICK_LENGTH;
  for (let pass = 0; pass < sorted.length; pass += 1) {
    for (let index = 1; index < sorted.length; index += 1) {
      const gap = sorted[index].y - sorted[index - 1].y;
      if (gap < need) {
        const push = (need - gap) * GEOMETRY.HALF;
        sorted[index - 1].y -= push;
        sorted[index].y += push;
      }
    }
  }
  if (sorted.length) {
    const over = low - sorted[0].y;
    if (over > 0) for (const item of sorted) item.y += over;
    const under = sorted[sorted.length - 1].y - high;
    if (under > 0) for (const item of sorted) item.y -= under;
  }
  return sorted;
}

/** A vertical cursor for a readout, drawn into a time panel's svg and moved by
 *  the caller. Returns the line element. */
export function cursorLine(panel) {
  const line = svgEl("line", { class: "mark-cursor", x1: 0, x2: 0, y1: panel.top, y2: panel.bottom, visibility: "hidden", "aria-hidden": "true" });
  panel.svg.appendChild(line);
  return line;
}

export function moveCursor(line, x) {
  line.setAttribute("x1", px(x));
  line.setAttribute("x2", px(x));
  line.setAttribute("visibility", "visible");
}

/** The monthly seasonal profile, Part 8.1 H8: every complete year demeaned as
 *  a decorative hairline, the mean of those years in ink, and the season the
 *  sentence tests as a bracket under the axis.
 *
 *  years       [[year, [twelve values]]]
 *  mean        [twelve values]
 *  months      the short month names, from the artifact
 *  season      the month numbers of the tested season, in order
 *  words       { title, desc, unit, meanLabel, seasonLabel } */
export function profilePanel({ width, years, mean, months, season, style, yDomain, words }) {
  const g = GEOMETRY;
  const left = g.PAD_LEFT;
  const right = Math.max(width - g.PAD_RIGHT, left + g.PAD_RIGHT);
  const top = g.PAD_TOP;
  const bottom = top + g.PROFILE_HEIGHT;
  const railTop = bottom + g.AXIS_GAP + g.AXIS_BELOW;
  const height = railTop + g.RAIL_HEIGHT;
  const first = TICK_LADDER[0];
  const last = months.length;
  const xOf = linear(first, last, left, right);
  const yOf = linear(yDomain[0], yDomain[1], bottom, top);
  const halfMonth = (right - left) / Math.max(last - first, first) * g.HALF;

  const svg = imageSvg({ width, height, title: words.title, desc: words.desc, className: "chart--profile" });
  const frame = svgEl("g", { "aria-hidden": "true" });
  const marks = svgEl("g", { "aria-hidden": "true" });
  svg.appendChild(frame);
  svg.appendChild(marks);

  const yStep = tickStep(yDomain[0], yDomain[1], g.Y_TICKS);
  for (const value of tickValues(yDomain[0], yDomain[1], g.Y_TICKS)) {
    const y = yOf(value);
    frame.appendChild(svgEl("line", { class: value === 0 ? "mark-context" : "mark-grid", x1: left, x2: right, y1: px(y), y2: px(y) }));
    frame.appendChild(svgEl("text", { class: "tick", x: left - g.LABEL_GAP, y: px(y), "text-anchor": "end", "dominant-baseline": "central" }, tickLabel(value, yStep)));
  }
  frame.appendChild(svgEl("text", { class: "chart-axis-title", x: left - g.LABEL_GAP, y: top - g.LABEL_GAP - g.TICK_LENGTH, "text-anchor": "end" }, words.unit));
  // Month names are words, so they are Figtree captions, not mono ticks. Every
  // second month is named when the months are closer than half YEAR_SPACING.
  const tickY = bottom + g.AXIS_GAP;
  const every = (right - left) / Math.max(last - first, first) < g.YEAR_SPACING * g.HALF ? TICK_LADDER[1] : TICK_LADDER[0];
  months.forEach((name, index) => {
    const x = xOf(index + first);
    frame.appendChild(svgEl("line", { class: "mark-context", x1: px(x), x2: px(x), y1: bottom, y2: bottom + g.TICK_LENGTH }));
    if (index % every === 0) frame.appendChild(svgEl("text", { class: "chart-caption", x: px(x), y: px(tickY), "text-anchor": "middle", "dominant-baseline": "central" }, name));
  });
  frame.appendChild(svgEl("line", { class: "mark-context", x1: left, x2: right, y1: bottom, y2: bottom }));

  for (const [, values] of years) {
    const { runs } = splitRuns(values.map((v, index) => [index + first, v]));
    drawRuns(marks, runs, xOf, yOf, "mark-hairline", "mark-hairline-fill");
  }
  const group = svgEl("g", { class: "series-mean series-" + style });
  const meanRuns = splitRuns(mean.map((v, index) => [index + first, v])).runs;
  drawRuns(group, meanRuns, xOf, yOf, "mark-series", "mark-series-fill");
  marks.appendChild(group);
  const lastIndex = mean.map((v) => present(v)).lastIndexOf(true);
  if (lastIndex >= 0) {
    // Inside the plot, right aligned just above the line's end on a --bg halo,
    // because the words are wider than the room right of a narrow plot.
    const x = xOf(lastIndex + first);
    marks.appendChild(svgEl("text", { class: "chart-end-label halo", x: px(x), y: px(yOf(mean[lastIndex]) - g.LABEL_SPACING), "text-anchor": "end", "dominant-baseline": "central" }, words.meanLabel));
  }

  // The season bracket. A season that wraps the year end is two brackets, the
  // label on the longer piece and a bare bracket on the other.
  const railY = railTop + g.RAIL_HEIGHT * g.HALF;
  const pieces = [];
  let piece = [];
  for (const month of season) {
    if (piece.length && month !== piece[piece.length - 1] + first) {
      pieces.push(piece);
      piece = [];
    }
    piece.push(month);
  }
  if (piece.length) pieces.push(piece);
  const longest = pieces.reduce((best, p) => (p.length > best.length ? p : best), pieces[0] || []);
  const railGroup = svgEl("g", { "aria-hidden": "true" });
  svg.appendChild(railGroup);
  const tick = g.BRACKET_TICK * g.HALF;
  for (const p of pieces) {
    const x0 = Math.max(xOf(p[0]) - halfMonth, left);
    const x1 = Math.min(xOf(p[p.length - 1]) + halfMonth, right);
    if (p === longest) {
      bracket(railGroup, x0, x1, railY, words.seasonLabel);
    } else {
      railGroup.appendChild(svgEl("path", { class: "mark-context", d: "M" + px(x0) + " " + px(railY - tick) + " V" + px(railY + tick) + " M" + px(x0) + " " + px(railY) + " H" + px(x1) + " M" + px(x1) + " " + px(railY - tick) + " V" + px(railY + tick) }));
    }
  }
  return svg;
}

/* ================================================================ runs === */

/** The run cut threshold scatter, docs/design.md Part 3 section 5 and Part
 *  8.3, R2.
 *
 *  width, height      the svg's width and the plot's height, in CSS px
 *  xDomain, yDomain   [low, high] in the artifact's units
 *  xUnit, yUnit       the axis titles
 *  title, desc        the accessible name and description
 *  points             [{ x, y, square }]: square for a month of the stretch the
 *                     kink is estimated from, a hollow circle otherwise
 *  fits               [{ line: [[x, y]], style: "dashed" | "dotted", name,
 *                        lastText }], each end labelled, none in the accent
 *  span               { low, high } or null: the interval, a flat span with no
 *                     text on it, drawn to its true ends
 *  edges              [{ x, label }]: an edge of the search, a rule the height
 *                     of the plot with its label above the plot
 *  Returns { svg, xOf, yOf }. No accent: the thing it would mark is not
 *  identified. */
export function scatterPanel({ width, height, xDomain, yDomain, xUnit, yUnit, title, desc, points, fits, span, edges }) {
  const g = GEOMETRY;
  const left = g.PAD_LEFT;
  const right = Math.max(width - g.SCATTER_PAD_RIGHT, left + g.SCATTER_PAD_RIGHT);
  const top = g.SCATTER_PAD_TOP;
  const bottom = top + height;
  const total = bottom + g.AXIS_GAP + g.LABEL_SPACING + g.AXIS_BELOW;
  const xOf = linear(xDomain[0], xDomain[1], left, right);
  const yOf = linear(yDomain[0], yDomain[1], bottom, top);

  const svg = imageSvg({ width, height: total, title, desc, className: "chart--scatter" });
  const frame = svgEl("g", { "aria-hidden": "true" });
  const marks = svgEl("g", { "aria-hidden": "true" });
  const labels = svgEl("g", { "aria-hidden": "true" });
  svg.appendChild(frame);
  svg.appendChild(marks);
  svg.appendChild(labels);

  // The span first, so every mark sits over it.
  if (span && present(span.low) && present(span.high)) {
    const x0 = Math.max(xOf(span.low), left);
    const x1 = Math.min(xOf(span.high), right);
    frame.appendChild(svgEl("rect", { class: "mark-span", x: px(x0), y: px(top), width: px(Math.max(x1 - x0, 0)), height: px(bottom - top) }));
  }

  const yStep = tickStep(yDomain[0], yDomain[1], g.Y_TICKS);
  for (const value of tickValues(yDomain[0], yDomain[1], g.Y_TICKS)) {
    const y = yOf(value);
    frame.appendChild(svgEl("line", { class: "mark-grid", x1: left, x2: right, y1: px(y), y2: px(y) }));
    frame.appendChild(svgEl("text", { class: "tick", x: left - g.LABEL_GAP, y: px(y), "text-anchor": "end", "dominant-baseline": "central" }, tickLabel(value, yStep)));
  }
  frame.appendChild(svgEl("text", { class: "chart-axis-title", x: 0, y: g.LABEL_SPACING }, yUnit));
  const xStep = tickStep(xDomain[0], xDomain[1], g.X_TICKS);
  const tickY = bottom + g.AXIS_GAP;
  for (const value of tickValues(xDomain[0], xDomain[1], g.X_TICKS)) {
    const x = xOf(value);
    frame.appendChild(svgEl("line", { class: value === 0 ? "mark-context" : "mark-grid", x1: px(x), x2: px(x), y1: top, y2: bottom }));
    frame.appendChild(svgEl("text", { class: "tick", x: px(x), y: px(tickY), "text-anchor": "middle", "dominant-baseline": "central" }, tickLabel(value, xStep)));
  }
  frame.appendChild(svgEl("line", { class: "mark-context", x1: left, x2: right, y1: bottom, y2: bottom }));
  frame.appendChild(svgEl("text", { class: "chart-axis-title", x: right, y: px(tickY + g.LABEL_SPACING), "text-anchor": "end", "dominant-baseline": "central" }, xUnit));

  // Edges of the search: a rule, and its words above the plot on --bg.
  for (const edge of edges || []) {
    if (!present(edge.x)) continue;
    const x = xOf(edge.x);
    frame.appendChild(svgEl("line", { class: "mark-context", x1: px(x), x2: px(x), y1: px(top - g.TICK_LENGTH), y2: px(bottom) }));
    labels.appendChild(svgEl("text", { class: "chart-caption scatter-edge-label", x: px(x), y: px(top - g.LABEL_GAP - g.TICK_LENGTH), "text-anchor": "end" }, edge.label));
  }

  const half = g.SCATTER_SQUARE * g.HALF;
  for (const point of points) {
    if (!present(point.x) || !present(point.y)) continue;
    const cx = xOf(point.x);
    const cy = yOf(point.y);
    if (point.square) marks.appendChild(svgEl("rect", { class: "mark-series-fill scatter-square", x: px(cx - half), y: px(cy - half), width: g.SCATTER_SQUARE, height: g.SCATTER_SQUARE }));
    else marks.appendChild(svgEl("circle", { class: "mark-point", cx: px(cx), cy: px(cy), r: g.SMALL_RADIUS }));
  }

  const ends = [];
  for (const fit of fits) {
    const line = fit.line.filter(([x, y]) => present(x) && present(y));
    if (line.length < 1 + 1) continue;
    const d = line.map(([x, y], index) => (index === 0 ? "M" : "L") + px(xOf(x)) + " " + px(yOf(y))).join(" ");
    marks.appendChild(svgEl("path", { class: "mark-fit mark-fit--" + fit.style, d, "data-fit": fit.id }));
    const [lx, ly] = line[line.length - 1];
    ends.push({ end: { x: xOf(lx), pointY: yOf(ly), fit }, y: yOf(ly) });
  }
  // Fit labels in the top right corner of the plot, one row each in the order
  // the lines end from the top, right aligned on a --bg halo, each joined to
  // its line's end by a context leader. The top of the scatter is where no
  // month sits, so no word covers a point, and at 375 px the plot keeps its
  // width.
  const sorted = [...ends].sort((a, b) => a.y - b.y);
  sorted.forEach((item, index) => {
    const end = item.end;
    const y = top + g.LABEL_SPACING * (index + g.HALF) + g.TICK_LENGTH;
    labels.appendChild(svgEl("line", { class: "mark-context", x1: px(end.x), x2: px(end.x), y1: px(y + g.LABEL_SPACING * g.HALF), y2: px(end.pointY) }));
    labels.appendChild(svgEl("text", { class: "chart-end-label halo scatter-fit-label", x: px(end.x), y: px(y), "text-anchor": "end", "dominant-baseline": "central" }, end.fit.name + ", " + end.fit.lastText));
  });
  return { svg, xOf, yOf };
}

/* The power row: a hairline across the domain, the accent tick at the test's
 * size the height of the row, and the power as an ink dot with a --bg ring. */
function powerRow(group, xOf, y, rowTop, rowBottom, item, size) {
  const g = GEOMETRY;
  const domain = xOf.domain;
  group.appendChild(svgEl("line", { class: "mark-context", x1: px(xOf(domain[0])), x2: px(xOf(domain[1])), y1: px(y), y2: px(y) }));
  if (present(size)) {
    group.appendChild(svgEl("line", { class: "mark-accent-rule power-size", x1: px(xOf(size)), x2: px(xOf(size)), y1: px(rowTop), y2: px(rowBottom) }));
  }
  if (!present(item.power)) return;
  const cx = xOf(item.power);
  group.appendChild(svgEl("circle", { class: "mark-ring-fill", cx: px(cx), cy: px(y), r: g.DOT_RADIUS + g.RING_WIDTH }));
  group.appendChild(svgEl("circle", { class: "mark-series-fill power-dot", cx: px(cx), cy: px(y), r: g.DOT_RADIUS }));
}

/** A power strip for one table row, hidden, Part 3 section 5: domain from the
 *  artifact, the size as the accent tick, the power as a dot. */
export function powerCell({ width, height, item, domain, size }) {
  const g = GEOMETRY;
  const svg = hiddenSvg({ width, height, className: "chart--strip chart--power" });
  const inset = g.DOT_RADIUS + g.RING_WIDTH;
  const xOf = linear(domain[0], domain[1], inset, Math.max(width - inset, inset));
  powerRow(svg, xOf, height * g.HALF, 0, height, item, size);
  return svg;
}

/** The power strips as one figure at narrow widths, each row labelled above,
 *  the accent tick stopping at the label line so it crosses no words. */
export function powerFigure({ width, items, domain, size, title, desc }) {
  const g = GEOMETRY;
  const rowHeight = g.STRIP_LABEL + g.STRIP_ROW;
  const height = items.length * rowHeight + g.STRIP_PAD;
  const svg = imageSvg({ width, height, title, desc, className: "chart--strip-figure chart--power" });
  const inset = g.DOT_RADIUS + g.RING_WIDTH;
  const xOf = linear(domain[0], domain[1], inset, Math.max(width - inset, inset));
  const group = svgEl("g", { "aria-hidden": "true" });
  items.forEach((item, index) => {
    const rowTop = index * rowHeight + g.STRIP_LABEL;
    group.appendChild(svgEl("text", { class: "chart-caption-strong", x: 0, y: px(index * rowHeight + g.STRIP_LABEL * g.HALF), "dominant-baseline": "central" }, item.label));
    powerRow(group, xOf, rowTop + g.STRIP_ROW * g.HALF, rowTop, rowTop + g.STRIP_ROW, item, size);
  });
  svg.appendChild(group);
  return svg;
}
