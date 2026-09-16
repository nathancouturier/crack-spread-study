/* section-cracks.js
 *
 * "Gasoil and gasoline cracks", inside the Now view. docs/design.md Part 3
 * section 3: two seasonal panels, gasoil then gasoline, side by side above
 * 768px and stacked below, on one shared y domain. Each has its sentence
 * heading, the chart, and a button under it that opens the same figures as a
 * table. Under both, the sentence that says how few prior years there are and
 * that this is not a five year range.
 *
 * Every figure is from data/cracks.json. The words that label marks (the year
 * of a line, "prior years", "least defended weeks") are copy; the numbers in
 * them are fields.
 *
 * Not built here, and why: the "Leave out 2022" toggle of Part 3 section 3.
 * Pressing it has to change the heading, the depth rail and the range sentence,
 * and those sentences are exported for the full range only. Drawing a toggled
 * state would mean composing new figures in the page. It waits for the export
 * to carry the sentences for the range without each episode year.
 *
 * Numeric literals: none.
 */

import { el, sentence, disclosure, figureCell, scrollTable } from "./dom.js";
import { formatNumber, formatCell, segmentsText, UNITS } from "./format.js";
import * as charts from "./charts.js";

export const artifact = "cracks";
export const loading = "the gasoil and gasoline cracks against the same week in earlier years";

const PRODUCTS = Object.freeze(["gasoil", "gasoline"]);

/* How a week was read, for the table and nowhere else. The keys are the
 * artifact's evidence classes. */
const EVIDENCE_WORDS = Object.freeze({
  cross_checked: "checked against a second chart",
  single_geometry_newest: "no second chart yet",
  single_geometry_oldest: "least defended week",
});

export function render(inner, data) {
  const decimals = data.conventions.decimals;
  const columns = data.panels[PRODUCTS[0]].columns;
  const at = (name) => columns.indexOf(name);

  // One y domain for both panels, from every value and printed figure drawn.
  let low = Infinity;
  let high = -Infinity;
  for (const product of PRODUCTS) {
    for (const row of data.panels[product].weeks) {
      for (const value of [...row[at("values_by_year")], ...row[at("printed_usd_bbl_by_year")]]) {
        if (!charts.present(value)) continue;
        low = Math.min(low, value);
        high = Math.max(high, value);
      }
    }
  }
  const panels = el("div", { class: "panels" });
  const haveValues = low <= high;
  const domain = haveValues ? charts.niceDomain(Math.min(low, 0), high, charts.GEOMETRY.Y_TICKS) : null;

  for (const product of PRODUCTS) {
    const panel = data.panels[product];
    const latest = data.latest.products[product];
    const heading = sentence("h3", latest.heading_segments, decimals, "panel__heading");
    const chart = el("div", { class: "chart-frame" });
    const figure = el("figure", { class: "panel" }, [heading, chart]);

    if (!haveValues) {
      chart.appendChild(el("p", { class: "state-message", text: "No weekly crack values arrived in data/cracks.json, so nothing is drawn. Reload the page, or open the Provenance section for the last fetch of the weekly series." }));
    } else {
      const words = panelWords(panel, latest, decimals);
      charts.onWidthChange(chart, (width) => {
        const svg = charts.seasonalPanel({
          width,
          panel,
          yDomain: domain,
          words,
          least: data.series_note.least_defended_class,
          newest: newestClass(data),
          decimals,
        });
        chart.replaceChildren(svg);
        charts.plateRailLabels(svg);
      });
      // The plates are measured in the loaded face, so measure again once the
      // fonts arrive if they had not when the panel was first drawn.
      if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(() => {
          const svg = chart.querySelector("svg");
          if (svg) charts.plateRailLabels(svg);
        });
      }
    }
    figure.appendChild(disclosure(
      "The same week in each year for " + panel.name + ", with how each week was read",
      () => weeksTable(panel, decimals, at),
    ));
    panels.appendChild(figure);
  }

  inner.appendChild(panels);
  inner.appendChild(sentence("p", data.series_note.segments, decimals, "block note"));
}

/* The evidence class the bracket marks: the one that is neither cross checked
 * nor the least defended class, read from the artifact's counts. */
function newestClass(data) {
  const counts = data.series_note.evidence_class_counts;
  return Object.keys(counts).find((name) => name !== "cross_checked" && name !== data.series_note.least_defended_class) || null;
}

function panelWords(panel, latest, decimals) {
  const year = (value) => formatNumber(value, "year", decimals);
  return {
    title: segmentsText(latest.heading_segments, decimals),
    desc: segmentsText(latest.desc_segments, decimals),
    unit: UNITS.usd_bbl,
    weekAxis: "Week",
    currentLabel: (value, last) => year(value) + ", " + formatNumber(last, "usd_bbl", decimals),
    priorYears: (count) => formatNumber(count, "count", decimals) + (count === 1 ? " prior year" : " prior years"),
    none: "none",
    leastDefended: (value) => year(value) + ", least defended weeks",
    noSecondChart: (value) => year(value) + ", no second chart yet",
  };
}

/* The text alternative: every week, every year, with how it was read and how
 * many prior years the week has. Wide, so it scrolls in its own container with
 * the week column sticky; the caption names the years that are off screen. */
function weeksTable(panel, decimals, at) {
  const years = panel.year_order;
  const headRow = el("tr", {}, [
    el("th", { text: "Week", attrs: { scope: "col" } }),
    el("th", { text: "Prior years", attrs: { scope: "col", "data-short": "prior years" } }),
  ]);
  for (const year of years) {
    const label = formatNumber(year, "year", decimals);
    headRow.appendChild(el("th", { text: label + ", " + UNITS.usd_bbl, attrs: { scope: "col", "data-short": label } }));
    headRow.appendChild(el("th", { text: label + ", how read", attrs: { scope: "col", "data-short": label + ", how read" } }));
  }
  const body = el("tbody");
  for (const row of panel.weeks) {
    const tr = el("tr", {}, [
      el("th", { class: "num", text: formatCell(row[at("week")], "count", decimals), attrs: { scope: "row" } }),
      figureCell(formatCell(row[at("n_years")], "count", decimals), "n_years"),
    ]);
    years.forEach((year, index) => {
      const value = row[at("values_by_year")][index];
      const printed = row[at("printed_usd_bbl_by_year")][index];
      const evidence = row[at("evidence_class_by_year")][index];
      if (!charts.present(value)) {
        tr.appendChild(el("td", { text: "no value" }));
        tr.appendChild(el("td", { text: "" }));
        return;
      }
      tr.appendChild(figureCell(formatCell(value, "usd_bbl", decimals), "values_by_year"));
      const how = [EVIDENCE_WORDS[evidence] || evidence];
      if (charts.present(printed)) how.push("printed by the ministry at " + formatNumber(printed, "usd_bbl", decimals));
      tr.appendChild(el("td", { text: how.join("; ") }));
    });
    body.appendChild(tr);
  }
  const table = el("table", { class: "table weeks-table" }, [el("thead", {}, [headRow]), body]);
  return scrollTable(["The " + panel.name + " crack by week of the year, one pair of columns per year."], table);
}
