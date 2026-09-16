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
 *   intervalStrip    one or more response intervals with zero marked
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

/** The round step for about `count` intervals across a span. */
export function tickStep(low, high, count) {
  if (!(high > low) || !(count > 0)) return 0;
  const rough = (high - low) / count;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rough)));
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
 * its label centred on the line over a --bg halo, so no text sits on a mark. */
function bracket(group, x0, x1, y, label) {
  const tick = GEOMETRY.BRACKET_TICK * GEOMETRY.HALF;
  group.appendChild(svgEl("path", {
    class: "mark-context",
    d: "M" + px(x0) + " " + px(y - tick) + " V" + px(y + tick) + " M" + px(x0) + " " + px(y) + " H" + px(x1) + " M" + px(x1) + " " + px(y - tick) + " V" + px(y + tick),
  }));
  group.appendChild(svgEl("text", { class: "chart-caption rail-label", x: px((x0 + x1) * GEOMETRY.HALF), y: px(y), "text-anchor": "middle", "dominant-baseline": "central" }, label));
}

/** Give each rail label a --bg plate the width of its words, so the bracket
 *  line stops at the label instead of showing between the words. Text can only
 *  be measured once the svg is in the document, so the caller runs this after
 *  inserting it. */
export function plateRailLabels(svg) {
  for (const plate of svg.querySelectorAll(".rail-plate")) plate.remove();
  for (const label of svg.querySelectorAll(".rail-label")) {
    let box;
    try {
      box = label.getBBox();
    } catch (error) {
      continue;
    }
    if (!box || box.width === 0) continue;
    const pad = GEOMETRY.TICK_LENGTH;
    label.parentNode.insertBefore(svgEl("rect", {
      class: "mark-ring-fill rail-plate",
      x: px(box.x - pad),
      y: px(box.y),
      width: px(box.width + pad + pad),
      height: px(box.height),
    }), label);
  }
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

/** An interval strip for one table row, hidden, Part 3 section 5. */
export function intervalCell({ width, height, item, domain }) {
  const g = GEOMETRY;
  const svg = hiddenSvg({ width, height, className: "chart--strip" });
  const inset = g.DOT_RADIUS + g.RING_WIDTH;
  const xOf = linear(domain[0], domain[1], inset, Math.max(width - inset, inset));
  intervalRow(svg, xOf, height * g.HALF, item);
  const zero = xOf(0);
  svg.appendChild(svgEl("line", { class: "mark-accent-rule", x1: px(zero), x2: px(zero), y1: 0, y2: height }));
  return svg;
}

/** The interval strips as one figure above the table at narrow widths, an
 *  image with a title and description. Each row labelled at its left end. */
export function intervalFigure({ width, items, domain, title, desc }) {
  const g = GEOMETRY;
  const rowHeight = g.STRIP_LABEL + g.STRIP_ROW;
  const height = items.length * rowHeight + g.STRIP_PAD;
  const svg = imageSvg({ width, height, title, desc, className: "chart--strip-figure" });
  const inset = g.DOT_RADIUS + g.RING_WIDTH;
  const xOf = linear(domain[0], domain[1], inset, Math.max(width - inset, inset));
  const group = svgEl("g", { "aria-hidden": "true" });
  items.forEach((item, index) => {
    const labelY = index * rowHeight + g.STRIP_LABEL * g.HALF;
    group.appendChild(svgEl("text", { class: "chart-caption-strong", x: 0, y: px(labelY), "dominant-baseline": "central" }, item.label));
    intervalRow(group, xOf, index * rowHeight + g.STRIP_LABEL + g.STRIP_ROW * g.HALF, item);
  });
  const zero = xOf(0);
  group.appendChild(svgEl("line", { class: "mark-accent-rule", x1: px(zero), x2: px(zero), y1: g.STRIP_LABEL, y2: height }));
  svg.appendChild(group);
  return svg;
}
