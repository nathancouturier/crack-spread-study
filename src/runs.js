/* runs.js
 *
 * The Runs and crude demand view, docs/design.md Part 8.3, with Part 3 section 5.
 *
 * The lead answers the question the view is named for: the response of crude
 * runs to the margin on both equations with their intervals (the h1), whether
 * the margin beat the raw gasoil crack, said as the power allows, and the
 * unidentified paragraph where a headroom figure would sit. Then four parts
 * behind one choice row, each linkable (R8):
 *
 *   Response                    the Now section's strips and table, reused from
 *                               section-runs.js, the lower bound sentence where
 *                               the coefficients are, the reason the equations
 *                               differ, with and without the episodes, and
 *                               utilisation, the lagged margin and crude imports
 *                               month by month on separate plots (R1, R3)
 *   Run cut threshold           the scatter with both fits and the interval to
 *                               the edge of the search, no accent (R2)
 *   Horse race and instrument   A, B, C in a fixed order, the power beside each
 *                               pair, what the margin gives that the crack
 *                               cannot, and the instrument's control ladder
 *                               (R4, R5, R6)
 *   After the strikes on Iran   the residuals, 2022 and the months after the
 *                               break bracketed, never joined, no accent, and the
 *                               Now section's post break table (R7)
 *
 * STATE IS THE ADDRESS: #/runs?part=threshold. A button rewrites it with
 * router.replaceState and redraws; a pasted address arrives through update().
 *
 * Every figure is a field of data/runs.json or data/run-economics.json. The
 * page fits nothing: the fitted lines are vertices the export evaluated.
 *
 * Numeric literals: none. tools/check-literals.mjs.
 */

import { el, clear, sentence, disclosure, scrollTable, figureCell } from "./dom.js";
import { formatNumber, formatCell, segmentsText, UNITS } from "./format.js";
import * as charts from "./charts.js";
import * as router from "./router.js";
import * as runsSection from "./section-runs.js";

export const artifacts = Object.freeze(["runEconomics", "runs"]);

const VIEW = "runs";

const MONTH_FORMAT = new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
const monthWords = (iso) => MONTH_FORMAT.format(new Date(charts.timeOf(iso)));
const monthCell = (iso) => iso.slice(0, iso.lastIndexOf("-"));

let held = null;

/* ------------------------------------------------------------- state --- */

function partFrom(route, runs) {
  const asked = route && route.params ? route.params.part : "";
  return (runs.parts.find((p) => p.id === asked) || runs.parts[0]).id;
}

function write(part) {
  router.replaceState(VIEW, { part: part === held.runs.parts[0].id ? "" : part });
}

/* -------------------------------------------------------------- view --- */

export function render(root, data, route) {
  const runs = data.runs;
  const economics = data.runEconomics;
  held = { runs, economics, root, part: partFrom(route, runs) };
  const decimals = runs.conventions.decimals;

  const title = sentence("h1", runs.title_segments, decimals, "view-title runs-title");
  title.id = "view-title";
  title.setAttribute("tabindex", "-1");
  root.appendChild(title);
  root.appendChild(sentence("p", runs.race.margin_against_crack_segments, decimals, "lead runs-lead"));
  const headroom = runsSection.headroomBlock(economics);
  headroom.classList.add("runs-headroom");
  root.appendChild(headroom);

  const switcher = el("div", { class: "choice-row runs-parts", attrs: { role: "group", "aria-label": "Part of the view" } });
  for (const part of runs.parts) {
    const button = el("button", { class: "choice", text: part.label, attrs: { type: "button", "data-part": part.id, "aria-pressed": "false" } });
    button.addEventListener("click", () => {
      held.part = part.id;
      write(part.id);
      draw();
    });
    switcher.appendChild(button);
  }
  root.appendChild(switcher);
  root.appendChild(el("div", { class: "runs-body", id: "runs-body" }));
  draw();
  return title;
}

export function update(root, route) {
  if (!held) return;
  held.part = partFrom(route, held.runs);
  draw();
}

function draw() {
  const body = held.root.querySelector("#runs-body");
  if (!body) return;
  for (const button of held.root.querySelectorAll(".runs-parts .choice")) {
    button.setAttribute("aria-pressed", button.getAttribute("data-part") === held.part ? "true" : "false");
  }
  clear(body);
  body.setAttribute("data-part", held.part);
  const builders = { response: drawResponse, threshold: drawThreshold, race: drawRace, break: drawBreak };
  (builders[held.part] || drawResponse)(body);
}

function part(headingText) {
  const section = el("section", { class: "runs-part" });
  if (headingText) section.appendChild(el("h2", { class: "runs-part__heading", text: headingText }));
  return section;
}

function plotHeight(width) {
  return width < charts.GEOMETRY.NARROW_WIDTH ? charts.GEOMETRY.TIME_HEIGHT_NARROW : charts.GEOMETRY.TIME_HEIGHT;
}

/* A y domain from the values drawn, on the tick ladder. `withZero` keeps zero
 * in view, which a residual or a margin needs and a utilisation rate does not. */
function domainOf(values, withZero) {
  const finite = values.filter((v) => charts.present(v));
  if (!finite.length) return null;
  const low = Math.min(...finite);
  const high = Math.max(...finite);
  return withZero ? charts.niceDomain(Math.min(low, 0), Math.max(high, 0), charts.GEOMETRY.Y_TICKS) : charts.niceDomain(low, high, charts.GEOMETRY.Y_TICKS);
}

function head(cells) {
  return el("thead", {}, [el("tr", {}, cells.map(([text, short, numeric]) => el("th", {
    class: numeric ? "col-num" : null,
    text,
    attrs: { scope: "col", "data-short": short },
  })))]);
}

/* ---------------------------------------------------------- response --- */

function drawResponse(body) {
  const { runs, economics } = held;
  const decimals = runs.conventions.decimals;
  const section = part("");
  section.appendChild(runsSection.responseBlock(economics, sentence("p", runs.endogeneity_segments, decimals, "note runs-lower-bound")));
  const reason = runsSection.disagreementBlock(economics);
  if (reason) section.appendChild(reason);
  section.appendChild(episodesBlock(decimals));
  body.appendChild(section);
  body.appendChild(seriesBlock(decimals));
}

function episodesBlock(decimals) {
  const { runs } = held;
  const block = el("div", { class: "block" });
  block.appendChild(el("h3", { class: "block__heading", text: "With and without the episodes" }));
  const tbody = el("tbody");
  for (const row of runs.episodes.rows) {
    const low = formatCell(row.kb_d_low, "kb_d", decimals, true);
    const high = formatCell(row.kb_d_high, "kb_d", decimals, true);
    tbody.appendChild(el("tr", { attrs: { "data-model": row.model, "data-variant": row.variant } }, [
      el("th", { class: "model-name", attrs: { scope: "row" } }, [
        el("span", { class: "model-name__label", text: row.model_label }),
        el("span", { class: "runs-variant", text: row.variant_label }),
      ]),
      figureCell(formatCell(row.kb_d, "kb_d", decimals, true), "kb_d"),
      low === null || high === null
        ? el("td", { class: "range", text: "no interval" })
        : el("td", { class: "range", attrs: { "data-field": "kb_d_low kb_d_high" } }, [el("span", { class: "num", text: low }), " to ", el("span", { class: "num", text: high })]),
      figureCell(formatCell(row.t, "t", decimals, true), "t"),
      figureCell(formatCell(row.months, "count", decimals), "months"),
    ]));
  }
  const table = el("table", { class: "table runs-episodes-table" }, [
    head([["Model and sample", "model", false], [UNITS.kb_d + " per " + (formatNumber(held.economics.response.models[0].move_usd_bbl, "count", decimals) || "no figure") + " " + UNITS.usd_bbl, UNITS.kb_d, true], ["Interval", "interval", true], ["t", "t", true], ["Months", "months", true]]),
    tbody,
  ]);
  block.appendChild(scrollTable(["The response on each equation with the episodes as terms, without the terms, and without the episode months."], table));
  block.appendChild(sentence("p", runs.episodes.segments, decimals, "note"));
  return block;
}

function seriesBlock(decimals) {
  const { runs } = held;
  const s = runs.series;
  const c = (name) => s.columns.indexOf(name);
  const rows = s.rows;
  const times = rows.map((row) => charts.timeOf(row[c("date")]));
  const xDomain = [times[0], times[times.length - 1]];
  const span = monthWords(s.first) + " to " + monthWords(s.last);
  const steps = s.capacity_steps.map((d) => charts.timeOf(d));
  const lastRow = rows[rows.length - 1];

  const section = part("Utilisation, the lagged margin and crude imports, month by month");
  section.appendChild(sentence("p", s.sample_segments, decimals, "note"));

  const plots = [
    {
      heading: "Utilisation, percent of NWE refinery capacity, " + span,
      unit: UNITS.percent,
      desc: "Monthly NWE crude intake over capacity, " + span + ", one solid line split where capacity falls by a step. The last months are provisional. Every value is in the table under the plots.",
      withZero: false,
      lines: [{ column: "utilisation_percent", name: "", style: "solid", format: "percent", breaks: steps }],
      breaks: steps,
    },
    {
      heading: "Margin at the average US refinery's gas use, mean of the three previous months, $/bbl",
      unit: UNITS.usd_bbl,
      desc: "The regressor of every equation on this page, the margin after gas at the average US refinery's use averaged over the three months before each month, " + span + ". It starts three months after the margin does. Every value is in the table under the plots.",
      withZero: true,
      lines: [{ column: "margin_lagged_usd_bbl", name: "", style: "solid", format: "usd_bbl", breaks: [] }],
      breaks: [],
    },
    {
      heading: "Crude intake and crude imports, kb/d, " + span,
      unit: UNITS.kb_d,
      desc: "NWE crude intake, solid, and NWE crude imports, dashed, " + span + ", on one kb/d scale. No model links them; the sentence under the plots gives their ratio. Every value is in the table under the plots.",
      withZero: false,
      lines: [
        { column: "intake_kb_d", name: "Intake", style: "solid", format: "kb_d", breaks: [] },
        { column: "imports_kb_d", name: "Imports", style: "dashed", format: "kb_d", breaks: [] },
      ],
      breaks: [],
    },
  ];
  for (const plot of plots) {
    const figure = el("figure", { class: "runs-plot" });
    figure.appendChild(el("h3", { class: "runs-plot__heading", text: plot.heading }));
    const frame = el("div", { class: "chart-frame" });
    figure.appendChild(frame);
    const yDomain = domainOf(rows.flatMap((row) => plot.lines.map((line) => row[c(line.column)])), plot.withZero);
    charts.onWidthChange(frame, (width) => {
      const panel = charts.timePanel({
        width,
        height: plotHeight(width),
        xDomain,
        yDomain,
        unit: plot.unit,
        title: plot.heading,
        desc: plot.desc,
        lines: plot.lines.map((line) => ({
          name: line.name,
          style: line.style,
          points: rows.map((row) => [charts.timeOf(row[c("date")]), row[c(line.column)]]),
          lastText: formatNumber(lastRow[c(line.column)], line.format, decimals) || "no value",
          breaks: line.breaks,
          accent: true,
        })),
        events: [],
        breaks: plot.breaks,
        rails: null,
        className: "chart--runs-series",
      });
      frame.replaceChildren(panel.svg);
    });
    section.appendChild(figure);
  }
  section.appendChild(sentence("p", s.capacity_segments, decimals, "note"));
  section.appendChild(sentence("p", s.imports.segments, decimals, "note"));
  section.appendChild(disclosure("Every month on these three plots, with its capacity and status", () => {
    const tbody = el("tbody");
    for (const row of rows) {
      tbody.appendChild(el("tr", {}, [
        el("th", { class: "num", text: monthCell(row[c("date")]), attrs: { scope: "row" } }),
        figureCell(formatCell(row[c("utilisation_percent")], "percent", decimals), "utilisation_percent"),
        figureCell(formatCell(row[c("margin_lagged_usd_bbl")], "usd_bbl", decimals), "margin_lagged_usd_bbl"),
        figureCell(formatCell(row[c("intake_kb_d")], "kb_d", decimals), "intake_kb_d"),
        figureCell(formatCell(row[c("imports_kb_d")], "kb_d", decimals), "imports_kb_d"),
        figureCell(formatCell(row[c("capacity_kb_d")], "kb_d", decimals), "capacity_kb_d"),
        figureCell(formatCell(row[c("capacity_source_year")], "year", decimals), "capacity_source_year"),
        el("td", { class: row[c("provisional")] ? "status-word" : "", text: row[c("provisional")] ? "provisional" : "final" }),
      ]));
    }
    const table = el("table", { class: "table runs-series-table" }, [
      head([["Month", "month", false], ["Utilisation, percent", "utilisation", true], ["Lagged margin, " + UNITS.usd_bbl, "lagged margin", true], ["Intake, " + UNITS.kb_d, "intake", true], ["Imports, " + UNITS.kb_d, "imports", true], ["Capacity, " + UNITS.kb_d, "capacity", true], ["Capacity of the year", "capacity year", true], ["Status", "status", false]]),
      tbody,
    ]);
    return scrollTable(["Utilisation, the lagged margin, crude intake and imports, " + span + ". A month with no lagged margin has fewer than three months of margin before it."], table);
  }));
  return section;
}

/* --------------------------------------------------------- threshold --- */

function drawThreshold(body) {
  const { runs } = held;
  const decimals = runs.conventions.decimals;
  const t = runs.threshold;
  const c = (name) => t.columns.indexOf(name);
  const section = el("section", { class: "runs-part" });
  section.appendChild(sentence("h2", t.heading_segments, decimals, "runs-part__heading"));
  section.appendChild(sentence("p", t.stretch_segments, decimals, "lead"));

  const xs = t.rows.map((row) => row[c("margin_lagged_usd_bbl")]).concat([t.interval.search_low_usd_bbl, t.interval.search_high_usd_bbl]);
  const ys = t.rows.map((row) => row[c("utilisation_percent")]).concat(t.fits.flatMap((fit) => fit.line.map(([, y]) => y)));
  const xDomain = domainOf(xs, true);
  const yDomain = domainOf(ys, false);
  const edges = [];
  const iv = t.interval;
  if (iv.high_usd_bbl === iv.search_high_usd_bbl) edges.push({ x: iv.search_high_usd_bbl, label: "Edge of the range searched" });
  if (iv.low_usd_bbl === iv.search_low_usd_bbl) edges.push({ x: iv.search_low_usd_bbl, label: "Edge of the range searched" });
  const frame = el("div", { class: "chart-frame runs-scatter" });
  section.appendChild(frame);
  charts.onWidthChange(frame, (width) => {
    const panel = charts.scatterPanel({
      width,
      height: plotHeight(width),
      xDomain,
      yDomain,
      xUnit: UNITS.usd_bbl + ", mean of the three previous months",
      yUnit: "Utilisation, " + UNITS.percent,
      title: segmentsText(t.heading_segments, decimals),
      desc: segmentsText(t.desc_segments, decimals),
      points: t.rows.map((row) => ({ x: row[c("margin_lagged_usd_bbl")], y: row[c("utilisation_percent")], square: row[c("in_stretch")] === true })),
      fits: t.fits.map((fit) => ({ id: fit.id, line: fit.line, style: fit.style, name: fit.label, lastText: "kink at " + (formatNumber(fit.kink_usd_bbl, "usd_bbl", decimals) || "none") })),
      span: { low: iv.low_usd_bbl, high: iv.high_usd_bbl },
      edges,
    });
    frame.replaceChildren(panel.svg);
  });
  section.appendChild(sentence("p", t.interval_segments, decimals, "note"));

  const tbody = el("tbody");
  for (const fit of t.fits) {
    tbody.appendChild(el("tr", { attrs: { "data-fit": fit.id } }, [
      el("th", { text: fit.label, attrs: { scope: "row" } }),
      figureCell(formatCell(fit.months, "count", decimals), "months"),
      figureCell(formatCell(fit.kink_usd_bbl, "usd_bbl", decimals), "kink_usd_bbl"),
      figureCell(formatCell(fit.slope_below, "slope", decimals, true), "slope_below"),
      figureCell(formatCell(fit.months_below, "count", decimals), "months_below"),
      figureCell(formatCell(fit.kink_r2, "r2", decimals), "kink_r2"),
      figureCell(formatCell(fit.line_r2, "r2", decimals), "line_r2"),
    ]));
  }
  section.appendChild(scrollTable(["The kink fitted on every month and without the stretch. Slope below is the fall in utilisation, in percentage points, per $/bbl the margin sits below the kink; a negative slope means runs rise as the margin falls."], el("table", { class: "table runs-fits-table" }, [
    head([["Fit", "fit", false], ["Months", "months", true], ["Kink, " + UNITS.usd_bbl, "kink", true], ["Slope below", "slope below", true], ["Months below the kink", "months below", true], ["R2 with the kink", "R2 with the kink", true], ["R2 of a straight line", "R2 of a straight line", true]]),
    tbody,
  ])));

  section.appendChild(disclosure("Every month on the scatter", () => {
    const rows = el("tbody");
    for (const row of t.rows) {
      rows.appendChild(el("tr", {}, [
        el("th", { class: "num", text: monthCell(row[c("date")]), attrs: { scope: "row" } }),
        figureCell(formatCell(row[c("margin_lagged_usd_bbl")], "usd_bbl", decimals), "margin_lagged_usd_bbl"),
        figureCell(formatCell(row[c("utilisation_percent")], "percent", decimals), "utilisation_percent"),
        el("td", { text: row[c("in_stretch")] ? "in the stretch" : "outside it" }),
        el("td", { text: row[c("below_kink")] ? "below" : "above" }),
      ]));
    }
    return scrollTable(["Utilisation against the lagged margin, the months of the scatter."], el("table", { class: "table runs-points-table" }, [
      head([["Month", "month", false], ["Lagged margin, " + UNITS.usd_bbl, "lagged margin", true], ["Utilisation, percent", "utilisation", true], ["Stretch", "stretch", false], ["Against the kink on every month", "against the kink", false]]),
      rows,
    ]));
  }));
  body.appendChild(section);
}

/* -------------------------------------------------------------- race --- */

function drawRace(body) {
  const { runs } = held;
  const decimals = runs.conventions.decimals;
  const race = runs.race;
  const section = part("The horse race");
  section.appendChild(sentence("p", race.sentence_segments, decimals, "lead"));
  for (const eq of race.equations) section.appendChild(equationBlock(eq, decimals));
  const gives = el("div", { class: "block runs-gives" });
  gives.appendChild(el("h3", { class: "block__heading", text: "What the margin gives that the raw crack cannot" }));
  for (const paragraph of race.gives) gives.appendChild(sentence("p", paragraph, decimals, "prose"));
  section.appendChild(gives);
  body.appendChild(section);
  body.appendChild(instrumentBlock(decimals));
}

function equationBlock(eq, decimals) {
  const { runs } = held;
  const race = runs.race;
  const block = el("div", { class: "block runs-equation", attrs: { "data-equation": eq.id } });
  block.appendChild(el("h3", { class: "block__heading", text: eq.label }));

  const tbody = el("tbody");
  for (const horse of eq.horses) {
    const name = el("th", { class: "model-name", attrs: { scope: "row" } }, [el("span", { class: "model-name__label", text: horse.key + ", " + horse.name })]);
    if (horse.substitution_segments) name.appendChild(el("span", { class: "runs-variant", text: "a substitution, said under the table" }));
    tbody.appendChild(el("tr", { class: "runs-horse", attrs: { "data-horse": horse.key } }, [
      name,
      figureCell(formatCell(horse.coefficient, "coef", decimals, true), "coefficient"),
      figureCell(formatCell(horse.se, "coef", decimals), "se"),
      figureCell(formatCell(horse.t, "t", decimals, true), "t"),
      figureCell(formatCell(horse.r2, "r2", decimals), "r2"),
      figureCell(formatCell(horse.oos_rmse, "rmse", decimals), "oos_rmse"),
    ]));
  }
  const empty = () => el("td", { class: "num" });
  tbody.appendChild(el("tr", { class: "is-note" }, [
    el("th", { text: "A forecast of the training mean alone", attrs: { scope: "row" } }),
    empty(), empty(), empty(), empty(),
    figureCell(formatCell(eq.mean_benchmark_rmse, "rmse", decimals), "mean_benchmark_rmse"),
  ]));
  const long = eq.long_sample;
  tbody.appendChild(el("tr", { class: "is-note runs-long-sample" }, [
    el("th", { class: "model-name", attrs: { scope: "row" } }, [
      el("span", { class: "model-name__label", text: "A on its own longer sample, not in the race" }),
      el("span", { class: "runs-variant", text: monthWords(long.first_month) + " to " + monthWords(long.last_month) + ", " + formatNumber(long.months, "count", decimals) + " months" }),
    ]),
    figureCell(formatCell(long.coefficient, "coef", decimals, true), "coefficient"),
    figureCell(formatCell(long.se, "coef", decimals), "se"),
    figureCell(formatCell(long.t, "t", decimals, true), "t"),
    figureCell(formatCell(long.r2, "r2", decimals), "r2"),
    figureCell(formatCell(long.oos_rmse, "rmse", decimals), "oos_rmse"),
  ]));
  const caption = sentence("span", eq.caption_segments, decimals);
  block.appendChild(scrollTable([caption], el("table", { class: "table runs-race-table" }, [
    head([["Horse", "horse", false], ["Coefficient", "coefficient", true], ["Newey-West se", "Newey-West se", true], ["t", "t", true], ["R2", "R2", true], ["Out of sample RMSE", "out of sample RMSE", true]]),
    tbody,
  ])));
  const substituted = eq.horses.find((horse) => horse.substitution_segments);
  if (substituted) {
    const note = el("p", { class: "note runs-substitution" }, [substituted.key + ", the substitution. "]);
    for (const node of sentence("span", substituted.substitution_segments, decimals).childNodes) note.appendChild(node.cloneNode(true));
    block.appendChild(note);
  }
  block.appendChild(sentence("p", eq.oos_segments, decimals, "note"));

  // The power of each pairwise test, beside the gap it could have seen.
  const size = race.size;
  const domain = race.power_domain;
  const items = eq.pairs.map((pair) => ({ label: pair.first + " and " + pair.second, power: pair.power }));
  const sizeText = formatNumber(size, "power", decimals);
  const figure = el("div", { class: "strip-figure chart-frame" });
  charts.onWidthChange(figure, (width) => {
    figure.replaceChildren(charts.powerFigure({
      width,
      items,
      domain,
      size,
      title: "Power of each pairwise test on " + eq.label.toLowerCase() + ", against a size of " + sizeText,
      desc: "One row per pair of horses on a scale from " + formatNumber(domain[0], "count", decimals) + " to " + formatNumber(domain[domain.length - 1], "count", decimals) + ", the size " + sizeText + " marked by a rule and the power by a dot: " + items.map((item) => item.label + " " + formatNumber(item.power, "power", decimals)).join(", ") + ". Every dot sits on or beside the rule.",
    }));
  });
  const ptbody = el("tbody");
  const cells = [];
  eq.pairs.forEach((pair, index) => {
    const cell = el("td", { class: "strip-col strip-cell" });
    cells.push({ cell, item: items[index] });
    ptbody.appendChild(el("tr", { attrs: { "data-pair": pair.first + pair.second } }, [
      el("th", { text: items[index].label, attrs: { scope: "row" } }),
      figureCell(formatCell(pair.observed_gap_percent, "gap_percent", decimals), "observed_gap_percent"),
      figureCell(formatCell(pair.detectable_gap_percent, "gap_percent", decimals), "detectable_gap_percent"),
      figureCell(formatCell(pair.power, "power", decimals), "power"),
      cell,
      figureCell(formatCell(pair.forecasts_for_target_power, "count", decimals), "forecasts_for_target_power"),
    ]));
  });
  const powerBlock = el("div", { class: "runs-power" });
  powerBlock.appendChild(figure);
  powerBlock.appendChild(scrollTable([
    "Could the test have told each pair apart? The observed gap in out of sample RMSE beside the smallest gap the test could have detected, both in percent of the larger RMSE; the power against the observed gap, where the size " + sizeText + " is marked; and the forecasts " + formatNumber(race.power_target_percent, "count", decimals) + " percent power would need.",
  ], el("table", { class: "table runs-power-table" }, [
    el("thead", {}, [el("tr", {}, [
      el("th", { text: "Pair", attrs: { scope: "col", "data-short": "pair" } }),
      el("th", { class: "col-num", text: "Observed gap, percent", attrs: { scope: "col", "data-short": "observed gap" } }),
      el("th", { class: "col-num", text: "Smallest detectable gap, percent", attrs: { scope: "col", "data-short": "smallest detectable gap" } }),
      el("th", { class: "col-num", text: "Power", attrs: { scope: "col", "data-short": "power" } }),
      el("th", { class: "strip-col", attrs: { scope: "col", "data-short": "power drawing" } }, [el("span", { class: "visually-hidden", text: "Power drawn with the size marked" })]),
      el("th", { class: "col-num", text: "Forecasts needed", attrs: { scope: "col", "data-short": "forecasts needed" } }),
    ])]),
    ptbody,
  ])));
  if (cells.length) {
    charts.onWidthChange(cells[0].cell, () => {
      for (const { cell, item } of cells) {
        const width = cell.clientWidth;
        const height = cell.clientHeight;
        if (width === 0 || height === 0) continue;
        cell.replaceChildren(charts.powerCell({ width, height, item, domain, size }));
      }
    });
  }
  block.appendChild(powerBlock);
  return block;
}

function instrumentBlock(decimals) {
  const { runs } = held;
  const inst = runs.instrument;
  const section = part("The instrument");
  section.appendChild(sentence("p", inst.sentence_segments, decimals, "lead"));
  const tbody = el("tbody");
  for (const rung of inst.ladder) {
    tbody.appendChild(el("tr", {}, [
      el("th", { text: rung.controls, attrs: { scope: "row" } }),
      figureCell(formatCell(rung.coefficient, "coef", decimals, true), "coefficient"),
      figureCell(formatCell(rung.se, "coef", decimals), "se"),
      figureCell(formatCell(rung.f, "f_stat", decimals), "f"),
      figureCell(formatCell(rung.partial_r2, "r2", decimals), "partial_r2"),
      el("td", { class: "runs-used-by", text: rung.used_by.length ? rung.used_by.join("; ") : "neither equation" }),
    ]));
  }
  section.appendChild(scrollTable(["The first stage of the gas price as an instrument for the margin, as the controls go in one at a time. It holds no dependent, so both equations share it; the last column says whose controls each row is."], el("table", { class: "table runs-ladder-table" }, [
    head([["Controls", "controls", false], ["Coefficient on gas", "coefficient", true], ["Newey-West se", "Newey-West se", true], ["First stage F", "F", true], ["Partial R2", "partial R2", true], ["The controls of", "whose controls", false]]),
    tbody,
  ])));
  section.appendChild(sentence("p", inst.diagnosis_segments, decimals, "prose"));
  const etbody = el("tbody");
  for (const eq of inst.equations) {
    etbody.appendChild(el("tr", {}, [
      el("th", { class: "model-name", attrs: { scope: "row" } }, [
        el("span", { class: "model-name__label", text: eq.label }),
        el("span", { class: "runs-variant", text: eq.coefficient_unit }),
      ]),
      figureCell(formatCell(eq.first_stage_f, "f_stat", decimals), "first_stage_f"),
      figureCell(formatCell(eq.ols_coefficient, "coef", decimals, true), "ols_coefficient"),
      figureCell(formatCell(eq.ols_se, "coef", decimals), "ols_se"),
      figureCell(formatCell(eq.iv_coefficient, "coef", decimals, true), "iv_coefficient"),
      figureCell(formatCell(eq.iv_se, "coef", decimals), "iv_se"),
      el("td", { text: eq.iv_used ? "used" : "not used, the instrument is weak" }),
    ]));
  }
  section.appendChild(scrollTable(["Ordinary least squares and two stage estimates of the response to the three month mean margin, on each equation's own controls."], el("table", { class: "table runs-iv-table" }, [
    head([["Equation", "equation", false], ["First stage F", "F", true], ["Least squares", "least squares", true], ["se", "least squares se", true], ["Two stage", "two stage", true], ["se", "two stage se", true], ["Two stage estimate", "two stage estimate", false]]),
    etbody,
  ])));
  section.appendChild(sentence("p", inst.exclusion_segments, decimals, "note"));
  return section;
}

/* ------------------------------------------------------------- break --- */

function drawBreak(body) {
  const { runs, economics } = held;
  const decimals = runs.conventions.decimals;
  const b = runs.break;
  const cPre = (name) => b.columns_pre.indexOf(name);
  const cPost = (name) => b.columns_post.indexOf(name);
  const section = el("section", { class: "runs-part" });
  section.appendChild(sentence("h2", b.heading_segments, decimals, "runs-part__heading"));
  section.appendChild(sentence("p", b.fit_segments, decimals, "lead"));

  const pre = b.pre_rows.map((row) => [charts.timeOf(row[cPre("date")]), row[cPre("residual_pp")]]);
  const post = b.post_rows.map((row) => [charts.timeOf(row[cPost("date")]), row[cPost("residual_pp")]]);
  const xDomain = [pre[0][0], post.length ? post[post.length - 1][0] : pre[pre.length - 1][0]];
  const yDomain = domainOf(pre.concat(post).map(([, v]) => v), true);
  const title = segmentsText(b.heading_segments, decimals);
  const frame = el("div", { class: "chart-frame runs-residuals" });
  section.appendChild(frame);
  charts.onWidthChange(frame, (width) => {
    const panel = charts.timePanel({
      width,
      height: plotHeight(width),
      xDomain,
      yDomain,
      unit: UNITS.pp,
      title,
      desc: segmentsText(b.desc_segments, decimals),
      lines: [
        { name: "Fitted", style: "solid", points: pre, lastText: formatNumber(pre[pre.length - 1][1], "pp", decimals) || "no value", breaks: [], accent: false },
        { name: "After", style: "dashed", points: post, lastText: post.length ? formatNumber(post[post.length - 1][1], "pp", decimals) || "no value" : "none", breaks: [], accent: false },
      ],
      squares: post,
      events: [],
      breaks: [],
      rails: {
        least: [],
        newest: [],
        brackets: b.brackets.map((item) => ({ start: charts.timeOf(item.start), end: charts.timeOf(item.end), label: segmentsText(item.label_segments, decimals) })),
      },
      className: "chart--residuals",
    });
    frame.replaceChildren(panel.svg);
    charts.plateRailLabels(panel.svg);
  });
  section.appendChild(disclosure("Every residual on this plot", () => {
    const tbody = el("tbody");
    for (const row of b.pre_rows) {
      tbody.appendChild(el("tr", {}, [
        el("th", { class: "num", text: monthCell(row[cPre("date")]), attrs: { scope: "row" } }),
        figureCell(formatCell(row[cPre("residual_pp")], "pp", decimals, true), "residual_pp"),
        el("td", { text: "fitted" }),
      ]));
    }
    for (const row of b.post_rows) {
      tbody.appendChild(el("tr", {}, [
        el("th", { class: "num", text: monthCell(row[cPost("date")]), attrs: { scope: "row" } }),
        figureCell(formatCell(row[cPost("residual_pp")], "pp", decimals, true), "residual_pp"),
        el("td", { class: row[cPost("provisional")] ? "status-word" : "", text: row[cPost("provisional")] ? "after the break, provisional" : "after the break" }),
      ]));
    }
    return scrollTable(["Utilisation less what the margin implies, in percentage points of capacity."], el("table", { class: "table runs-residuals-table" }, [
      head([["Month", "month", false], ["Residual, " + UNITS.pp, "residual", true], ["Month kind", "month kind", false]]),
      tbody,
    ]));
  }));
  section.appendChild(runsSection.utilisationBlock(economics));

  const why = el("div", { class: "block" });
  why.appendChild(el("h3", { class: "block__heading", text: "What could explain runs below what the margin implies" }));
  why.appendChild(sentence("p", b.explanations_segments, decimals, "prose"));
  why.appendChild(el("ul", { class: "runs-explanations" }, b.explanations.map((item) => el("li", {}, [
    el("span", { class: "runs-explanations__name", text: item.name + ": " }),
    item.what + ".",
  ]))));
  why.appendChild(el("ul", { class: "marker-list" }, b.events.map((event) => el("li", {}, [
    event.label + ". ",
    el("a", { class: "text-link", text: event.source_title || "Source", attrs: { href: event.source_url, rel: "noopener" } }),
  ]))));
  why.appendChild(sentence("p", b.reopens_segments, decimals, "note"));
  section.appendChild(why);
  body.appendChild(section);
}
