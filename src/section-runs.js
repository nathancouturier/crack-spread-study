/* section-runs.js
 *
 * "Run economics and crude demand", inside the Now view. docs/design.md Part 3
 * section 1, "Section contents", in the order S17 fixes:
 *
 *   1  the headroom paragraph, where a headroom figure would sit: the word
 *      unidentified in body type and weight 500, with the reason, then the
 *      percentile fallback, the only reading of today's level the study defends
 *   2  the response of crude runs to the margin on both equations: the interval
 *      strips with zero marked in the accent, and the table, planned model
 *      first, with each equation written out under its name
 *   3  why the two equations disagree
 *   4  the latest utilisation against what the margin implies, the post break
 *      months with each provisional month saying so, and why they are not a
 *      test
 *
 * The strips are drawn twice by the stylesheet's choice: as a column of the
 * table above 600px, and as one figure above the table at 600px and below, so
 * the one picture of the finding never sits behind a sideways scroll (S31).
 * The hidden one is display none, so neither is read twice.
 *
 * Not built here, and why: the link "Open Runs and crude demand". That view is
 * published at Gate 5, and a link to it today is an orphan UI state (Part 7,
 * C7).
 *
 * Numeric literals: none.
 */

import { el, sentence, figureCell, scrollTable } from "./dom.js";
import { formatNumber, formatCell, segmentsText, UNITS } from "./format.js";
import * as charts from "./charts.js";

export const artifact = "runEconomics";
export const loading = "the run cut threshold and the response of crude runs to the margin";

export function render(inner, data) {
  const decimals = data.conventions.decimals;
  const threshold = data.threshold;
  const response = data.response;
  const utilisation = data.utilisation;

  // 1. Headroom, or the word unidentified where the number would sit.
  const headroom = sentence("p", threshold.segments, decimals, "lead");
  for (const word of headroom.querySelectorAll('[data-field="verdict"]')) word.classList.add("verdict-word");
  const first = el("div", { class: "block" }, [headroom]);
  if (threshold.fallback_segments && threshold.fallback_segments.length) {
    first.appendChild(sentence("p", threshold.fallback_segments, decimals, "lead"));
  }
  inner.appendChild(first);

  // 2. The response, strips then table.
  const models = response.order.map((id) => response.models.find((model) => model.id === id)).filter(Boolean);
  const items = models.map((model) => ({ label: model.label, estimate: model.kb_d, low: model.kb_d_low, high: model.kb_d_high }));
  const domain = charts.stripDomain(items);
  const move = formatNumber(models.length ? models[0].move_usd_bbl : null, "count", decimals);
  const perMove = UNITS.kb_d + " per " + (move === null ? "no figure" : move) + " " + UNITS.usd_bbl;
  const level = formatNumber(response.interval_level_percent, "count", decimals);

  const block = el("div", { class: "block" });
  block.appendChild(el("h3", { class: "block__heading", text: "How far crude runs move with the margin, on both equations" }));

  const stripFigure = el("div", { class: "strip-figure chart-frame" });
  const stripTitle = "Crude runs per " + move + " " + UNITS.usd_bbl + " of margin, " + perModelWords(models.length);
  const stripDesc = segmentsText(response.strip_desc_segments, decimals);
  charts.onWidthChange(stripFigure, (width) => {
    stripFigure.replaceChildren(charts.intervalFigure({ width, items, domain, title: stripTitle, desc: stripDesc }));
  });
  block.appendChild(stripFigure);

  const head = el("tr", {}, [
    el("th", { text: "Model", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: perMove, attrs: { scope: "col", "data-short": UNITS.kb_d } }),
    el("th", { class: "col-num", text: "Interval, " + level + " percent", attrs: { scope: "col", "data-short": "interval" } }),
    el("th", { class: "strip-col", attrs: { scope: "col", "data-short": "interval drawing" } }, [el("span", { class: "visually-hidden", text: "Interval drawn on one scale with zero marked" })]),
    el("th", { text: "Zero", attrs: { scope: "col", "data-short": "zero" } }),
    el("th", { class: "col-num", text: "Share of runs, percent", attrs: { scope: "col", "data-short": "share of runs" } }),
    el("th", { class: "col-num", text: "t", attrs: { scope: "col", "data-short": "t" } }),
    el("th", { class: "col-num", text: "Months", attrs: { scope: "col", "data-short": "months" } }),
  ]);
  const body = el("tbody");
  const stripCells = [];
  models.forEach((model, index) => {
    const low = formatCell(model.kb_d_low, "kb_d", decimals, true);
    const high = formatCell(model.kb_d_high, "kb_d", decimals, true);
    const stripCell = el("td", { class: "strip-col strip-cell" });
    stripCells.push({ cell: stripCell, item: items[index] });
    body.appendChild(el("tr", { attrs: { "data-model": model.id } }, [
      el("th", { class: "model-name", attrs: { scope: "row" } }, [
        el("span", { class: "model-name__label", text: model.label }),
        el("span", { class: "model-name__equation", text: sentenceCase(model.equation) + "." }),
      ]),
      figureCell(formatCell(model.kb_d, "kb_d", decimals, true), "kb_d"),
      // The two ends in the figure face, the word between them in the text face.
      low === null || high === null
        ? el("td", { class: "range", text: "no interval", attrs: { "data-field": "kb_d_low kb_d_high" } })
        : el("td", { class: "range", attrs: { "data-field": "kb_d_low kb_d_high" } }, [el("span", { class: "num", text: low }), " to ", el("span", { class: "num", text: high })]),
      stripCell,
      sentence("td", model.zero_segments, decimals, "zero-cell"),
      figureCell(formatCell(model.share_of_runs_percent, "percent", decimals, true), "share_of_runs_percent"),
      figureCell(formatCell(model.t, "t", decimals, true), "t"),
      figureCell(formatCell(model.months, "count", decimals), "months"),
    ]));
  });
  const table = el("table", { class: "table response-table" }, [el("thead", {}, [head]), body]);
  block.appendChild(scrollTable([
    "Crude runs per " + move + " " + UNITS.usd_bbl + " of margin after gas at the average US refinery's use, the planned model first.",
  ], table));
  // At 600px and below each equation is said under the table instead of inside
  // the sticky model column, where it made every row a dozen lines tall
  // (Part 7, C13). The stylesheet shows one of the two, never both.
  block.appendChild(el("ul", { class: "model-equations" }, models.map((model) => el("li", {}, [
    el("span", { class: "model-equations__label", text: model.label + ": " }),
    sentenceCase(model.equation) + ".",
  ]))));
  if (stripCells.length) {
    charts.onWidthChange(stripCells[0].cell, () => {
      for (const { cell, item } of stripCells) {
        const width = cell.clientWidth;
        const height = cell.clientHeight;
        if (width === 0 || height === 0) continue;
        cell.replaceChildren(charts.intervalCell({ width, height, item, domain }));
      }
    });
  }
  inner.appendChild(block);

  // 3. Why the two disagree.
  if (response.disagreement && response.disagreement.segments) {
    inner.appendChild(sentence("p", response.disagreement.segments, decimals, "block"));
  }

  // 4. Utilisation against what the margin implies.
  const util = el("div", { class: "block" });
  util.appendChild(el("h3", { class: "block__heading", text: "Latest utilisation against what the margin implies" }));
  util.appendChild(sentence("p", utilisation.latest_segments, decimals, "lead"));
  const uhead = el("tr", {}, [
    el("th", { text: "Month", attrs: { scope: "col" } }),
    el("th", { class: "col-num", text: "Utilisation, percent of capacity", attrs: { scope: "col", "data-short": "utilisation" } }),
    el("th", { class: "col-num", text: "Implied by the margin, percent", attrs: { scope: "col", "data-short": "implied" } }),
    el("th", { class: "col-num", text: "Difference, " + UNITS.pp, attrs: { scope: "col", "data-short": "difference in " + UNITS.pp } }),
    el("th", { class: "col-num", text: "Difference, " + UNITS.kb_d, attrs: { scope: "col", "data-short": "difference in " + UNITS.kb_d } }),
    el("th", { text: "Status", attrs: { scope: "col", "data-short": "status" } }),
  ]);
  const ubody = el("tbody");
  for (const month of utilisation.post_break_months) {
    ubody.appendChild(el("tr", { attrs: { "data-month": month.month } }, [
      el("th", { text: month.month_label, attrs: { scope: "row", "data-value": month.month } }),
      figureCell(formatCell(month.utilisation_percent, "percent", decimals), "utilisation_percent"),
      figureCell(formatCell(month.implied_percent, "percent", decimals), "implied_percent"),
      figureCell(formatCell(month.residual_pp, "pp", decimals, true), "residual_pp"),
      figureCell(formatCell(month.residual_kb_d, "kb_d", decimals, true), "residual_kb_d"),
      el("td", { class: month.provisional ? "status-word" : "", text: month.status_word, attrs: { "data-field": "status_word" } }),
    ]));
  }
  util.appendChild(scrollTable([
    "The months after the break, each against " + utilisation.implied_by.equation + ".",
  ], el("table", { class: "table utilisation-table" }, [el("thead", {}, [uhead]), ubody])));
  util.appendChild(sentence("p", utilisation.segments, decimals));
  inner.appendChild(util);
}

function perModelWords(count) {
  return count === 1 ? "one model, with its interval and zero marked" : "each model with its interval, zero marked";
}

function sentenceCase(text) {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}
