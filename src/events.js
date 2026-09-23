/* events.js
 *
 * The Events view, docs/design.md Part 8.4, SPEC.md sections 6.5 and 7.2.
 *
 * The view opens on the list of events alone (E1, E10). Picking one, from the
 * list or from a marker on History, opens its panel under the list: the
 * thirteen months from six before the event's month to six after, as stacked
 * plots on their own scales and one shared axis of months from the event (E2,
 * E3): OPEC's monthly cracks, this study's weekly reading where the window
 * reaches it (never spliced onto the monthly line, E7), the ministry's margin
 * and the same margin at the average US refinery's gas use (E8), and
 * utilisation split at a capacity step (E9). Every window is the full thirteen
 * months; a month a series lacks is a gap with a sentence naming the series
 * and why (E6). The event is the one accent: a rule at its day, or, for an
 * event the source dates only to the month, a bracket over that month (E5).
 * No change figure, no index, nothing said about cause (E4).
 *
 * STATE IS THE ADDRESS: #/events?event={id}. A list link is an ordinary link to
 * that address; the router hands the change to update(), which draws the panel
 * and moves focus to its heading.
 *
 * Every figure is a field of data/events.json. Numeric literals: none.
 * tools/check-literals.mjs.
 */

import { el, clear, sentence, disclosure, scrollTable, figureCell } from "./dom.js";
import { formatNumber, formatCell, segmentsText, UNITS } from "./format.js";
import * as charts from "./charts.js";
import * as router from "./router.js";

export const artifacts = Object.freeze(["events"]);

const VIEW = "events";

const MONTH_FORMAT = new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
const DAY_FORMAT = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const monthWords = (iso) => MONTH_FORMAT.format(new Date(charts.timeOf(iso)));
const dayWords = (iso) => DAY_FORMAT.format(new Date(charts.timeOf(iso)));
const monthCell = (iso) => iso.slice(0, iso.lastIndexOf("-"));

/* Which series each figure column of the month table comes from, by the id the
 * artifact's own series list uses. A window is always the full thirteen months
 * (E2), so a month outside a series' span has no figure, and the cell has to
 * say which side of that span it fell on rather than print the column id:
 * Gate 5 finding 2. The sentence under the plot, from the artifact's `missing`
 * list, names the series and the reason in full. */
const CELL_SERIES = Object.freeze({
  gasoil_usd_bbl: "monthly_cracks",
  gasoline_usd_bbl: "monthly_cracks",
  mbr_usd_bbl: "margin",
  margin_us_gas_usd_bbl: "margin",
  utilisation_percent: "utilisation",
});

/* The words for one empty cell of the month table, from the series' own first
 * and last month. "" when the gap is inside the span, where the honest answer
 * is that the series simply has no value and the cell says only that. */
function outsideWords(column, month) {
  const series = held.events.series.find((s) => s.id === CELL_SERIES[column]);
  if (!series) return "";
  if (month > series.last) return "after this series ends";
  if (month < series.first) return "before this series starts";
  return "";
}

/* How a week was read, the words History and the Now view use. */
const EVIDENCE_WORDS = Object.freeze({
  cross_checked: "checked against a second chart",
  single_geometry_newest: "no second chart yet",
  single_geometry_oldest: "least defended week",
});

let held = null;

function chosen(route, data) {
  const asked = route && route.params ? route.params.event : "";
  return data.events.find((event) => event.id === asked) || null;
}

/* -------------------------------------------------------------- view --- */

export function render(root, data, route) {
  const events = data.events;
  held = { events, root, current: chosen(route, events) };
  const decimals = events.conventions.decimals;

  const title = sentence("h1", events.title_segments, decimals, "view-title");
  title.id = "view-title";
  title.setAttribute("tabindex", "-1");
  root.appendChild(title);
  root.appendChild(sentence("p", events.lead_segments, decimals, "lead events-lead"));

  const listSection = el("section", { class: "events-list-section", attrs: { "aria-labelledby": "events-list-heading" } });
  listSection.appendChild(el("h2", { class: "events-list__heading", id: "events-list-heading", text: "The events, in date order" }));
  // The list is a table, one row an event: denser than a list of blocks, and
  // the coverage column is read down, so a missing series stands out (E10).
  const tbody = el("tbody");
  for (const event of events.events) {
    const link = el("a", {
      class: "events-list__link",
      text: event.short,
      attrs: { href: router.href(VIEW, { event: event.id }), "data-event": event.id },
    });
    tbody.appendChild(el("tr", { class: "events-list__row", attrs: { "data-event": event.id } }, [
      el("th", { class: "events-list__date", text: event.label, attrs: { scope: "row" } }),
      el("td", { class: "events-list__event" }, [link, el("span", { class: "events-list__name", text: event.name + "." })]),
      sentence("td", event.coverage_segments, decimals, "events-list__coverage"),
    ]));
  }
  const table = el("table", { class: "table events-list" }, [
    el("thead", {}, [el("tr", {}, [
      el("th", { text: "Date, as the source gives it", attrs: { scope: "col" } }),
      el("th", { text: "Event", attrs: { scope: "col", "data-short": "event" } }),
      el("th", { text: "What its window lacks", attrs: { scope: "col", "data-short": "what its window lacks" } }),
    ])]),
    tbody,
  ]);
  listSection.appendChild(scrollTable(["Pick an event to open the thirteen months around it."], table));
  const others = sentence("p", events.not_panels_segments, decimals, "note events-others");
  others.appendChild(document.createTextNode(" "));
  others.appendChild(el("a", { class: "text-link", text: "Open the breaks in Method", attrs: { href: router.href("method", { section: "breaks" }) } }));
  others.appendChild(document.createTextNode("."));
  listSection.appendChild(others);
  root.appendChild(listSection);

  root.appendChild(el("div", { class: "events-body", id: "events-body" }));
  draw(false);
  return title;
}

export function update(root, route) {
  if (!held) return;
  held.current = chosen(route, held.events);
  draw(true);
}

function draw(moveFocus) {
  const body = held.root.querySelector("#events-body");
  if (!body) return;
  for (const link of held.root.querySelectorAll(".events-list__link")) {
    const current = held.current && link.getAttribute("data-event") === held.current.id;
    if (current) link.setAttribute("aria-current", "true");
    else link.removeAttribute("aria-current");
    link.closest("tr").classList.toggle("is-current", Boolean(current));
  }
  clear(body);
  if (!held.current) {
    body.appendChild(el("p", { class: "state-message events-empty", text: "Pick an event from the list, or a marker on History, to open the thirteen months around it." }));
    return;
  }
  const heading = panel(body, held.current);
  if (moveFocus && heading) heading.focus({ preventScroll: false });
}

/* ------------------------------------------------------------- panel --- */

function plotHeight(width) {
  return width < charts.GEOMETRY.NARROW_WIDTH ? charts.GEOMETRY.TIME_HEIGHT_NARROW : charts.GEOMETRY.TIME_HEIGHT;
}

function domainOf(values, withZero) {
  const finite = values.filter((v) => charts.present(v));
  if (!finite.length) return null;
  const low = Math.min(...finite);
  const high = Math.max(...finite);
  return withZero ? charts.niceDomain(Math.min(low, 0), Math.max(high, 0), charts.GEOMETRY.Y_TICKS) : charts.niceDomain(low, high, charts.GEOMETRY.Y_TICKS);
}

function lastPresent(rows, index) {
  for (let i = rows.length - 1; i >= 0; i -= 1) if (charts.present(rows[i][index])) return rows[i][index];
  return null;
}

function panel(body, event) {
  const data = held.events;
  const decimals = data.conventions.decimals;
  const c = (name) => data.monthly_columns.indexOf(name);
  const w = (name) => data.weekly_columns.indexOf(name);
  const rows = event.rows;
  const missingFor = (series) => event.missing.find((m) => m.series === series) || null;

  const section = el("section", { class: "events-panel", attrs: { "data-event": event.id, "aria-labelledby": "event-title" } });
  const heading = el("h2", { class: "events-panel__heading", id: "event-title", text: event.label + ": " + event.name + ".", attrs: { tabindex: "-1" } });
  section.appendChild(heading);
  if (event.what) section.appendChild(el("p", { class: "lead events-panel__what", text: event.what }));
  section.appendChild(sentence("p", event.precision_segments, decimals, "note"));
  const source = el("p", { class: "note events-source" }, [
    "Source: ",
    el("a", { class: "text-link", text: event.source_title || event.source_publisher || "the source", attrs: { href: event.source_url, rel: "noopener" } }),
    event.source_publisher ? ", " + event.source_publisher + "." : ".",
  ]);
  section.appendChild(source);
  if (event.additional_sources.length) {
    const more = el("ul", { class: "events-sources" });
    for (const item of event.additional_sources) {
      more.appendChild(el("li", {}, [
        el("a", { class: "text-link", text: item.title || item.publisher || "a further source", attrs: { href: item.url, rel: "noopener" } }),
        item.publisher ? ", " + item.publisher : "",
        item.why ? ". " + item.why.trim().replace(/\.?$/, ".") : ".",
      ]));
    }
    section.appendChild(el("p", { class: "note events-sources__intro", text: "Further sources for the same event:" }));
    section.appendChild(more);
  }
  const windowLine = el("p", { class: "note events-window" }, ["The window runs from "]);
  for (const segment of event.window.label_segments) windowLine.appendChild(document.createTextNode(segment.text !== undefined ? segment.text : segment.label));
  windowLine.appendChild(document.createTextNode(", months from the event on the axis."));
  section.appendChild(windowLine);

  // The shared axis: the full thirteen months, whatever the data cover.
  const xDomain = [charts.timeOf(event.window.first), charts.timeOf(event.window.end)];
  const xTicks = rows.map((row) => ({
    t: charts.timeOf(row[c("date")]),
    label: formatNumber(row[c("offset_months")], "count", decimals, { signed: true }),
    key: row[c("offset_months")],
  }));
  const isDay = event.precision === "day";
  const eventMonthIndex = rows.findIndex((row) => row[c("date")] === event.window.event_month);
  const monthBracket = !isDay && eventMonthIndex >= 0 && eventMonthIndex + 1 < rows.length
    ? [{ start: charts.timeOf(rows[eventMonthIndex][c("date")]), end: charts.timeOf(rows[eventMonthIndex + 1][c("date")]), label: event.label }]
    : [];
  const rails = (extra) => ({ least: [], newest: [], leastLabel: "", newestLabel: "", ...(extra || {}), brackets: monthBracket });
  const when = monthWords(event.window.first) + " to " + monthWords(event.window.last);
  const eventWords = isDay ? "An accent rule marks " + event.label + "." : "A bracket under the axis marks " + event.label + ", the month the source gives.";

  const plots = [
    {
      id: "cracks",
      heading: "OPEC's monthly gasoil and gasoline cracks, $/bbl",
      unit: UNITS.usd_bbl,
      withZero: true,
      desc: "Monthly Rotterdam cracks, gasoil solid and gasoline dashed, " + when + ". " + eventWords + " Months without a value are left empty. Every value is in the table under the plots.",
      lines: [
        { column: "gasoil_usd_bbl", name: "Gasoil", style: "solid" },
        { column: "gasoline_usd_bbl", name: "Gasoline", style: "dashed" },
      ],
      missing: missingFor("monthly_cracks"),
      breaks: [],
    },
    {
      id: "margin",
      heading: "The ministry's margin, and the same margin at the average US refinery's gas use, $/bbl",
      unit: UNITS.usd_bbl,
      withZero: true,
      desc: "The ministry's monthly gross refining margin on Brent, already net of its own gas allowance, solid, and the same margin at the average US refinery's gas use, dotted, " + when + ". " + eventWords + " Every value is in the table under the plots.",
      lines: [
        { column: "mbr_usd_bbl", name: "Ministry", style: "solid" },
        { column: "margin_us_gas_usd_bbl", name: "US gas", style: "dotted" },
      ],
      missing: missingFor("margin"),
      note: data.margin_segments,
      breaks: [],
    },
    {
      id: "utilisation",
      heading: "Utilisation, percent of NWE refinery capacity",
      unit: UNITS.percent,
      withZero: false,
      desc: "Monthly NWE crude intake over capacity, " + when + ", one solid line split where capacity falls by a step. " + eventWords + " Every value is in the table under the plots.",
      lines: [{ column: "utilisation_percent", name: "", style: "solid" }],
      missing: missingFor("utilisation"),
      breaks: event.capacity_steps.map((d) => charts.timeOf(d)),
    },
  ];

  const drawPlot = (plot, points, yDomain, extraRails, squares) => {
    const figure = el("figure", { class: "events-plot", attrs: { "data-plot": plot.id } });
    figure.appendChild(el("h3", { class: "events-plot__heading", text: plot.heading }));
    const frame = el("div", { class: "chart-frame events-chart", attrs: { role: "group", "aria-label": plot.heading + ". The tables under the plots hold every value." } });
    frame.tabIndex = 0;
    figure.appendChild(frame);
    charts.onWidthChange(frame, (width) => {
      const built = charts.timePanel({
        width,
        height: plotHeight(width),
        xDomain,
        yDomain,
        unit: plot.unit,
        title: plot.heading,
        desc: plot.desc,
        lines: points,
        squares: squares || [],
        events: [],
        breaks: plot.breaks,
        rails: rails(extraRails),
        className: "chart--event",
        xTicks,
        marker: isDay ? charts.timeOf(event.date) : null,
        labelAtEnd: true,
      });
      frame.replaceChildren(built.svg);
      charts.plateRailLabels(built.svg);
    });
    return figure;
  };

  const monthlyPlot = (plot) => {
    const values = rows.flatMap((row) => plot.lines.map((line) => row[c(line.column)]));
    const yDomain = domainOf(values, plot.withZero);
    const block = el("div", { class: "events-block", attrs: { "data-series": plot.id } });
    if (!yDomain) {
      block.appendChild(el("h3", { class: "events-plot__heading", text: plot.heading }));
    } else {
      block.appendChild(drawPlot(plot, plot.lines.map((line) => ({
        name: line.name,
        style: line.style,
        points: rows.map((row) => [charts.timeOf(row[c("date")]), row[c(line.column)]]),
        lastText: formatNumber(lastPresent(rows, c(line.column)), line.column === "utilisation_percent" ? "percent" : "usd_bbl", decimals) || "no value",
        breaks: plot.breaks,
        accent: false,
      })), yDomain, null, null));
    }
    if (plot.missing) block.appendChild(sentence("p", plot.missing.segments, decimals, "note events-missing"));
    if (plot.note) block.appendChild(sentence("p", plot.note, decimals, "note"));
    return block;
  };

  const [cracksPlot, marginPlot, utilisationPlot] = plots;
  section.appendChild(monthlyPlot(cracksPlot));

  // This study's weekly reading: its own plot, never joined to the monthly one.
  const weekly = event.weekly_rows;
  const weeklyBlock = el("div", { class: "events-block", attrs: { "data-series": "weekly" } });
  const weeklyHeading = "This study's weekly reading of the ministry's chart, gasoil and gasoline cracks, $/bbl";
  const weeklyMissing = missingFor("weekly");
  if (weekly.length) {
    const yDomain = domainOf(weekly.flatMap((row) => [row[w("gasoil_usd_bbl")], row[w("gasoline_usd_bbl")], row[w("printed_gasoil_usd_bbl")], row[w("printed_gasoline_usd_bbl")]]), true);
    const spans = (cls) => {
      const out = [];
      let start = null;
      let prev = null;
      for (const row of weekly) {
        if (row[w("evidence_class")] === cls) {
          if (start === null) start = row[w("date")];
          prev = row[w("date")];
        } else if (start !== null) {
          out.push([charts.timeOf(start), charts.timeOf(prev)]);
          start = null;
        }
      }
      if (start !== null) out.push([charts.timeOf(start), charts.timeOf(prev)]);
      return out;
    };
    const plot = {
      id: "weekly",
      heading: weeklyHeading,
      unit: UNITS.usd_bbl,
      desc: "Weekly cracks read off the ministry's chart, gasoil solid and gasoline dashed, " + dayWords(weekly[0][w("date")]) + " to " + dayWords(weekly[weekly.length - 1][w("date")]) + ", on the same months from the event as the plots above. Squares are weeks the ministry printed. Under the axis a hatch marks the least defended weeks and a bracket the weeks with no second chart yet. " + eventWords + " Every value is in the table under the plots.",
      breaks: [],
    };
    const lines = [["gasoil_usd_bbl", "Gasoil", "solid"], ["gasoline_usd_bbl", "Gasoline", "dashed"]].map(([column, name, style]) => ({
      name,
      style,
      points: weekly.map((row) => [charts.timeOf(row[w("date")]), row[w(column)]]),
      lastText: formatNumber(lastPresent(weekly, w(column)), "usd_bbl", decimals) || "no value",
      breaks: [],
      accent: false,
    }));
    const squares = weekly.flatMap((row) => [[charts.timeOf(row[w("date")]), row[w("printed_gasoil_usd_bbl")]], [charts.timeOf(row[w("date")]), row[w("printed_gasoline_usd_bbl")]]]);
    weeklyBlock.appendChild(drawPlot(plot, lines, yDomain, {
      least: spans(data.least_defended_class),
      newest: spans(data.newest_class),
      leastLabel: "Least defended weeks",
      newestLabel: "No second chart yet",
    }, squares));
  } else {
    weeklyBlock.appendChild(el("h3", { class: "events-plot__heading", text: weeklyHeading }));
  }
  if (weeklyMissing) weeklyBlock.appendChild(sentence("p", weeklyMissing.segments, decimals, "note events-missing"));
  section.appendChild(weeklyBlock);

  section.appendChild(monthlyPlot(marginPlot));
  section.appendChild(monthlyPlot(utilisationPlot));

  section.appendChild(disclosure("Every month of this window", () => monthTable(event, decimals)));
  if (weekly.length) section.appendChild(disclosure("Every week of this window, with how each was read", () => weekTable(event, decimals)));
  body.appendChild(section);
  return heading;
}

function monthTable(event, decimals) {
  const data = held.events;
  const c = (name) => data.monthly_columns.indexOf(name);
  const head = el("tr", {}, [
    el("th", { text: "Month", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "From the event", attrs: { scope: "col", "data-short": "from the event" } }),
    el("th", { class: "col-num", text: "Gasoil, $/bbl", attrs: { scope: "col", "data-short": "gasoil" } }),
    el("th", { class: "col-num", text: "Gasoline, $/bbl", attrs: { scope: "col", "data-short": "gasoline" } }),
    el("th", { class: "col-num", text: "Ministry's margin, $/bbl", attrs: { scope: "col", "data-short": "ministry's margin" } }),
    el("th", { class: "col-num", text: "At US gas use, $/bbl", attrs: { scope: "col", "data-short": "at US gas use" } }),
    el("th", { class: "col-num", text: "Utilisation, percent", attrs: { scope: "col", "data-short": "utilisation" } }),
    el("th", { text: "Runs data", attrs: { scope: "col", "data-short": "runs data" } }),
  ]);
  const tbody = el("tbody");
  for (const row of event.rows) {
    const provisional = row[c("utilisation_provisional")];
    const month = row[c("date")];
    const gap = (column) => ({ missing: outsideWords(column, month) });
    tbody.appendChild(el("tr", { attrs: { "data-month": month } }, [
      el("th", { class: "num", text: monthCell(month), attrs: { scope: "row" } }),
      figureCell(formatCell(row[c("offset_months")], "count", decimals, true) || formatCell(row[c("offset_months")], "count", decimals), "offset_months"),
      figureCell(formatCell(row[c("gasoil_usd_bbl")], "usd_bbl", decimals), "gasoil_usd_bbl", gap("gasoil_usd_bbl")),
      figureCell(formatCell(row[c("gasoline_usd_bbl")], "usd_bbl", decimals), "gasoline_usd_bbl", gap("gasoline_usd_bbl")),
      figureCell(formatCell(row[c("mbr_usd_bbl")], "usd_bbl", decimals), "mbr_usd_bbl", gap("mbr_usd_bbl")),
      figureCell(formatCell(row[c("margin_us_gas_usd_bbl")], "usd_bbl", decimals), "margin_us_gas_usd_bbl", gap("margin_us_gas_usd_bbl")),
      figureCell(formatCell(row[c("utilisation_percent")], "percent", decimals), "utilisation_percent", gap("utilisation_percent")),
      el("td", { text: provisional === null ? "none published" : provisional ? "provisional" : "final" }),
    ]));
  }
  return scrollTable(["The thirteen months around " + event.label + ", " + event.short + ". A month a series does not reach says so in its own cell, in words, and is never a zero; the sentence under each plot names the series and why it stops where it does."], el("table", { class: "table events-table" }, [el("thead", {}, [head]), tbody]));
}

function weekTable(event, decimals) {
  const data = held.events;
  const w = (name) => data.weekly_columns.indexOf(name);
  const head = el("tr", {}, [
    el("th", { text: "Week to", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Gasoil, $/bbl", attrs: { scope: "col", "data-short": "gasoil" } }),
    el("th", { class: "col-num", text: "Gasoline, $/bbl", attrs: { scope: "col", "data-short": "gasoline" } }),
    el("th", { class: "col-num", text: "Printed gasoil", attrs: { scope: "col", "data-short": "printed gasoil" } }),
    el("th", { class: "col-num", text: "Printed gasoline", attrs: { scope: "col", "data-short": "printed gasoline" } }),
    el("th", { text: "How read", attrs: { scope: "col", "data-short": "how read" } }),
  ]);
  const tbody = el("tbody");
  for (const row of event.weekly_rows) {
    const printedGasoil = formatCell(row[w("printed_gasoil_usd_bbl")], "usd_bbl", decimals);
    const printedGasoline = formatCell(row[w("printed_gasoline_usd_bbl")], "usd_bbl", decimals);
    tbody.appendChild(el("tr", {}, [
      el("th", { class: "num", text: row[w("date")], attrs: { scope: "row" } }),
      figureCell(formatCell(row[w("gasoil_usd_bbl")], "usd_bbl", decimals), "gasoil_usd_bbl"),
      figureCell(formatCell(row[w("gasoline_usd_bbl")], "usd_bbl", decimals), "gasoline_usd_bbl"),
      printedGasoil === null ? el("td", { class: "is-missing", text: "not printed" }) : figureCell(printedGasoil, "printed_gasoil_usd_bbl"),
      printedGasoline === null ? el("td", { class: "is-missing", text: "not printed" }) : figureCell(printedGasoline, "printed_gasoline_usd_bbl"),
      el("td", { text: EVIDENCE_WORDS[row[w("evidence_class")]] || "not recorded" }),
    ]));
  }
  const words = segmentsText(event.window.label_segments, decimals);
  return scrollTable(["This study's weekly reading of the ministry's chart inside the window, " + words + "."], el("table", { class: "table events-table weeks-table" }, [el("thead", {}, [head]), tbody]));
}
