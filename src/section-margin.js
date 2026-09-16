/* section-margin.js
 *
 * "Refining margin and gas", inside the Now view. docs/design.md Part 3
 * section 4, one block for the margin month (Part 7, C1): a table, one row per
 * line, a bar in a cell. Products ordered by contribution, the residual at full
 * weight with what it holds, the official margin with the accent, the gas wedge
 * with both intensities, the total at the average US refinery's gas use. Under
 * it the residual's record and the sentence the verdict gave up (Part 7, C9).
 *
 * The table is the text alternative of its own bars: every bar's value is the
 * figure in its row, so the bars are aria-hidden. At 600px and below each row
 * becomes two lines by CSS grid on the tr, which is why the roles are written
 * into the markup: some engines drop table semantics when a table part changes
 * display.
 *
 * Positive and negative are told apart without colour: a filled bar against an
 * outlined one, the printed sign, and the direction from the connector.
 *
 * Numeric literals: none.
 */

import { el, sentence, figureCell } from "./dom.js";
import { formatCell, UNITS } from "./format.js";
import * as charts from "./charts.js";

export const artifact = "marginStack";
export const loading = "the waterfall from the cracks to the refining margin";

export function render(inner, data) {
  const decimals = data.conventions.decimals;
  const rows = data.rows;
  const scale = [data.scale.low_usd_bbl, data.scale.high_usd_bbl];

  inner.appendChild(sentence("p", data.scale.segments, decimals, "block scale-note"));

  const body = el("tbody", { attrs: { role: "rowgroup" } });
  const barCells = [];
  rows.forEach((row, index) => {
    const isTotal = row.kind === "total";
    const nameCell = el("th", { class: "waterfall__name", attrs: { scope: "row", role: "rowheader" } }, [
      el("span", { class: "waterfall__line", text: sentenceCase(row.name) }),
    ]);
    const detail = detailFor(row, data, decimals);
    if (detail) nameCell.appendChild(detail);

    const barCell = el("td", { class: "waterfall__bar", attrs: { role: "cell" } });
    barCells.push({ cell: barCell, row, previous: index > 0 ? rows[index - 1] : null, isLast: index === rows.length - 1 });

    // Steps signed, totals not, Part 3 section 4 and Part 7, C14; the accent's
    // figure in the text accent role, which is --accent-bright in dark.
    const figure = figureCell(formatCell(row.value_usd_bbl, "usd_bbl", decimals, !isTotal), "value_usd_bbl",
      [isTotal ? "num--total" : "", row.accent ? "text-accent" : ""].filter(Boolean).join(" "));
    figure.setAttribute("role", "cell");

    body.appendChild(el("tr", {
      class: isTotal ? "waterfall__row is-total" : "waterfall__row",
      attrs: { role: "row", "data-row": row.id },
    }, [nameCell, barCell, figure]));
  });

  const table = el("table", { class: "table waterfall", attrs: { role: "table" } }, [
    el("caption", { text: "How the ministry's refining margin for " + data.month_label + " is built, line by line, in " + UNITS.usd_bbl + ", then its gross margin at the average US refinery's gas use." }),
    el("thead", { attrs: { role: "rowgroup" } }, [
      el("tr", { attrs: { role: "row" } }, [
        el("th", { text: "Line", attrs: { scope: "col", role: "columnheader" } }),
        el("th", { class: "waterfall__bar-head", attrs: { scope: "col", role: "columnheader" } }, [el("span", { class: "visually-hidden", text: "Bar from the running total" })]),
        el("th", { class: "col-num", text: UNITS.usd_bbl, attrs: { scope: "col", role: "columnheader" } }),
      ]),
    ]),
    body,
  ]);
  inner.appendChild(el("div", { class: "block" }, [table]));

  // Every bar at the size of its cell. The bar is positioned absolutely inside
  // the cell, so it never sets the row's height; the table is watched for any
  // change of size, a narrower column or a line of text that rewrapped, and
  // the bars are drawn again at the new size.
  const draw = () => {
    for (const item of barCells) {
      const width = item.cell.clientWidth;
      const height = item.cell.clientHeight;
      if (width === 0 || height === 0) continue;
      item.cell.replaceChildren(charts.waterfallBar({ width, height, row: item.row, previous: item.previous, isLast: item.isLast, scale }));
    }
  };
  if (typeof ResizeObserver === "function") new ResizeObserver(draw).observe(table);
  else window.addEventListener("resize", draw, { passive: true });
  draw();

  inner.appendChild(sentence("p", data.residual_history.segments, decimals, "block"));
  if (data.study_margin_segments) inner.appendChild(sentence("p", data.study_margin_segments, decimals, "block"));
}

/* A row's second line: what the product line prices, what the residual holds,
 * what the wedge assumes. Totals have none. */
function detailFor(row, data, decimals) {
  if (row.detail_segments) return sentence("span", row.detail_segments.concat([{ text: "." }]), decimals, "waterfall__detail");
  if (row.id === "residual") {
    const node = el("span", { class: "waterfall__detail" });
    if (data.residual_segments && data.residual_segments.length) node.appendChild(sentence("span", data.residual_segments, decimals));
    const contains = row.contains || {};
    const products = (contains.slate_lines || []).map((line) => line.name);
    const costs = contains.method_costs || [];
    const parts = [];
    if (products.length) parts.push("the products " + listWords(products));
    if (costs.length) parts.push("the method's costs: " + listWords(costs, "; "));
    if (parts.length) node.appendChild(document.createTextNode(" It holds " + parts.join(", and ") + "."));
    if (contains.reason) node.appendChild(document.createTextNode(" " + contains.reason));
    return node;
  }
  if (row.id === "gas_wedge" && data.wedge_segments) return sentence("span", data.wedge_segments, decimals, "waterfall__detail");
  return null;
}

function listWords(words, separator) {
  const join = separator || ", ";
  if (words.length < 1 + 1) return words.join("");
  return words.slice(0, -1).join(join) + (separator ? join + "and " : " and ") + words[words.length - 1];
}

function sentenceCase(text) {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}
