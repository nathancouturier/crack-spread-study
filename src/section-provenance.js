/* section-provenance.js
 *
 * "Provenance", inside the Now view. docs/design.md Part 3 section 1: the
 * manifest table, failed and stale rows first, in the column order of Part 6
 * section F (series, status, last value date, last fetch, gaps, vintage,
 * source) as data/provenance.json lists it; the manual steps verbatim; then who
 * each source is credited to and on what terms, and the typefaces with the
 * Figtree for Satoshi disclosure.
 *
 * Nothing here is summarised into a count or a badge. A status is a word in a
 * cell at full ink. A gap is a count of missing dates with the first and last
 * named. A series no machine fetches says so instead of printing an empty
 * fetch time.
 *
 * Numeric literals: none.
 */

import { el, figureCell } from "./dom.js";
import { formatCell, formatInstant } from "./format.js";

export const artifact = "provenance";
export const loading = "the manifest of every series, its source and its last fetch";

const COLUMN_HEADS = Object.freeze({
  series: "Series",
  status: "Status",
  last_date: "Last value",
  fetched_at: "Last fetch",
  gaps: "Missing dates",
  vintage: "Vintage",
  source: "Source",
});

/* Rows that did not come back cleanly lead the table. */
const TROUBLE = new Set(["failed", "stale"]);

export function render(inner, data) {
  const decimals = data.conventions.decimals;
  const manifest = data.manifest;
  const columns = data.manifest_columns;

  const series = [...manifest.series].sort((a, b) => Number(TROUBLE.has(b.status)) - Number(TROUBLE.has(a.status)));
  const head = el("tr", {}, columns.map((column) => el("th", { class: column === "last_date" || column === "gaps" ? "col-num" : "", text: COLUMN_HEADS[column] || column, attrs: { scope: "col" } })));
  const body = el("tbody");
  for (const entry of series) {
    body.appendChild(el("tr", { attrs: { "data-series": entry.series, "data-status": entry.status } }, columns.map((column) => cellFor(column, entry, decimals))));
  }
  const table = el("table", { class: "table manifest-table" }, [
    el("caption", {}, [
      document.createTextNode("Every series the study reads, as the manifest recorded it at " + (formatInstant(manifest.generated_at) || "a time it did not record") + "; failed and stale series first."),
      el("span", { class: "caption-narrow", text: " The fetch, gaps, vintage and source columns are to the right." }),
    ]),
    el("thead", {}, [head]),
    body,
  ]);
  inner.appendChild(el("div", { class: "block" }, [el("div", { class: "table-scroll" }, [table])]));

  // The manual steps, verbatim.
  const steps = manifest.manual_steps || [];
  if (steps.length) {
    const block = el("div", { class: "block" }, [el("h3", { class: "block__heading", text: "Work this pipeline cannot do for itself" })]);
    if (manifest.manual_steps_note) block.appendChild(el("p", { class: "prose", text: manifest.manual_steps_note }));
    for (const step of steps) {
      const item = el("div", { class: "manual-step", attrs: { "data-step": step.id } });
      item.appendChild(el("p", { class: "prose" }, [
        el("span", { class: "manual-step__what", text: step.what }),
        document.createTextNode(" This step is "),
        el("span", { class: "status-word", text: step.status, attrs: { "data-field": "status" } }),
        document.createTextNode("."),
      ]));
      item.appendChild(el("p", { class: "prose", text: "Why: " + step.why }));
      item.appendChild(el("p", { class: "prose", text: "What skipping it costs: " + step.cost_if_skipped }));
      item.appendChild(el("p", { class: "prose", text: "How: " + step.how }));
      if (step.cadence) item.appendChild(el("p", { class: "prose", text: "How often: " + step.cadence + "." }));
      block.appendChild(item);
    }
    inner.appendChild(block);
  }

  // Attributions and terms.
  const credits = el("div", { class: "block" }, [el("h3", { class: "block__heading", text: "Who the figures are credited to, and on what terms" })]);
  const list = el("ul", { class: "credit-list" });
  for (const source of data.attributions || []) {
    const item = el("li", { class: "prose", attrs: { "data-source": source.id } }, [
      el("span", { class: "credit__who", text: source.who }),
      document.createTextNode(". " + source.credit_line + ". Terms: " + source.licence + "."),
    ]);
    if (source.third_party) item.appendChild(document.createTextNode(" " + source.third_party));
    list.appendChild(item);
  }
  credits.appendChild(list);
  inner.appendChild(credits);

  // Typefaces and the one substitution.
  if (data.fonts) {
    const faces = el("div", { class: "block" }, [el("h3", { class: "block__heading", text: "Typefaces" })]);
    const names = (data.fonts.faces || []).map((face) => face.family + " for " + face.use + ", " + face.licence);
    if (names.length) faces.appendChild(el("p", { class: "prose", text: names.join("; ") + "." }));
    if (data.fonts.substitution) faces.appendChild(el("p", { class: "prose", text: data.fonts.substitution }));
    inner.appendChild(faces);
  }
}

function cellFor(column, entry, decimals) {
  switch (column) {
    case "series":
      return el("th", { class: "manifest__series", text: entry.series, attrs: { scope: "row" } });
    case "status":
      return el("td", { class: "status-word", text: entry.status, attrs: { "data-field": "status" } });
    case "last_date":
      return el("td", { class: "num", text: entry.last_date || "none", attrs: { "data-field": "last_date" } });
    case "fetched_at": {
      if (!entry.fetched_at) {
        return el("td", { class: "manifest__fetch", text: entry.machine_fetched === false ? "not fetched by a machine, " + entry.method : "no fetch recorded", attrs: { "data-field": "fetched_at" } });
      }
      return el("td", { class: "manifest__fetch", text: formatInstant(entry.fetched_at) || entry.fetched_at, attrs: { "data-field": "fetched_at" } });
    }
    case "gaps": {
      const gaps = entry.gaps || [];
      if (!gaps.length) return el("td", { class: "num", text: "none", attrs: { "data-field": "gaps" } });
      const first = gapDate(gaps[0], true);
      const last = gapDate(gaps[gaps.length - 1], false);
      const cell = figureCell(formatCell(gaps.length, "count", decimals), "gaps");
      cell.textContent += gaps.length === 1 ? " date, " + first : " dates, " + first + " to " + last;
      return cell;
    }
    case "vintage":
      return el("td", { class: "manifest__vintage", text: entry.vintage === null || entry.vintage === undefined ? "none recorded" : String(entry.vintage) });
    case "source": {
      const href = entry.page_url || entry.url;
      const cell = el("td", { class: "manifest__source" });
      if (href) cell.appendChild(el("a", { class: "text-link", text: entry.source, attrs: { href, rel: "noopener" } }));
      else cell.appendChild(document.createTextNode(entry.source));
      return cell;
    }
    default:
      return el("td", { text: entry[column] === null || entry[column] === undefined ? "" : String(entry[column]) });
  }
}

/* A gap is a date, or an object naming a span; either way the page prints what
 * the manifest wrote and never fills it. */
function gapDate(gap, first) {
  if (typeof gap === "string") return gap;
  if (gap && typeof gap === "object") return String(first ? gap.start || gap.date || gap.first || "" : gap.end || gap.date || gap.last || "");
  return String(gap);
}
