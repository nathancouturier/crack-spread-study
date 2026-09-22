/* method.js
 *
 * The Method view, docs/design.md Part 8.5, SPEC.md section 7.2: formulas, the
 * departures from the specification with their evidence, the assumptions with
 * a source per row, the measured cross checks, the product definitions, the
 * weekly reconstruction and its error, structural breaks, limitations and
 * reuse terms. A readable document with a table of contents (D2), no callout,
 * no badge, no code block, formulas in the body face (D1, D3, D5).
 *
 * data/method.json is a list of sections of blocks. Three kinds of block read
 * other artifacts rather than copies of them, so the two views cannot drift:
 *   ref     a sentence another artifact carries, by path
 *   reads   a table this module builds from the artifact that owns the fields:
 *           the latest month's printed prices and ICE factor citations
 *           (margin-stack.json), R2 and the Newey-West lag of each response
 *           equation (run-economics.json), the breaks (history.json), the
 *           manual steps and the reuse terms (provenance.json). These are the
 *           fields the Gate 4 audit found exported and never rendered (D4).
 *
 * STATE IS THE ADDRESS: #/method?section=assumptions. A contents link is an
 * ordinary link to that address; update() scrolls to the section and moves
 * focus to its heading.
 *
 * Every figure is a field of an artifact. Numeric literals: none.
 * tools/check-literals.mjs.
 */

import { el, sentence, scrollTable, figureCell, appendSegments } from "./dom.js";
import { formatCell } from "./format.js";
import * as router from "./router.js";

export const artifacts = Object.freeze(["method", "marginStack", "runEconomics", "runs", "history", "provenance"]);

const VIEW = "method";

/* The artifact names a ref block uses, as state.js names them. */
const ARTIFACT_KEYS = Object.freeze({
  method: "method",
  "margin-stack": "marginStack",
  "run-economics": "runEconomics",
  runs: "runs",
  history: "history",
  provenance: "provenance",
});

const MONTH_FORMAT = new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
const monthWords = (iso) => {
  const [year, month] = String(iso).split("-").map(Number);
  return MONTH_FORMAT.format(new Date(Date.UTC(year, month - 1)));
};

let held = null;

/* -------------------------------------------------------------- view --- */

export function render(root, data, route) {
  held = { data, root };
  const method = data.method;
  const decimals = method.conventions.decimals;

  const title = sentence("h1", method.title_segments, decimals, "view-title");
  title.id = "view-title";
  title.setAttribute("tabindex", "-1");
  root.appendChild(title);
  root.appendChild(sentence("p", method.lead_segments, decimals, "lead method-lead"));

  const contents = el("nav", { class: "method-contents", attrs: { "aria-labelledby": "method-contents-heading" } }, [
    el("h2", { class: "method-contents__heading", id: "method-contents-heading", text: "Contents" }),
  ]);
  const list = el("ol", { class: "method-contents__list" });
  for (const section of method.sections) {
    list.appendChild(el("li", {}, [el("a", { class: "text-link", text: section.title, attrs: { href: router.href(VIEW, { section: section.id }), "data-section": section.id } })]));
  }
  contents.appendChild(list);
  root.appendChild(contents);

  for (const section of method.sections) {
    const node = el("section", { class: "method-section", id: "method-" + section.id, attrs: { "aria-labelledby": "method-heading-" + section.id } });
    node.appendChild(el("h2", { class: "method-section__heading", id: "method-heading-" + section.id, text: section.title, attrs: { tabindex: "-1" } }));
    for (const block of section.blocks) {
      const built = renderBlock(block, decimals);
      if (built) node.appendChild(built);
    }
    root.appendChild(node);
  }
  const asked = route && route.params ? route.params.section : "";
  if (asked) requestAnimationFrame(() => goTo(asked, false));
  return title;
}

export function update(root, route) {
  if (!held) return;
  const asked = route && route.params ? route.params.section : "";
  if (asked) goTo(asked, true);
}

function goTo(id, moveFocus) {
  const heading = held.root.querySelector("#method-heading-" + CSS.escape(id));
  if (!heading) return;
  heading.scrollIntoView({ block: "start" });
  if (moveFocus) heading.focus({ preventScroll: true });
}

/* ------------------------------------------------------------ blocks --- */

function resolve(ref) {
  let value = held.data[ARTIFACT_KEYS[ref.artifact]];
  for (const key of ref.path) value = value === undefined || value === null ? undefined : value[key];
  return Array.isArray(value) ? value : null;
}

function renderBlock(block, decimals) {
  switch (block.type) {
    case "h":
      return el("h3", { class: "method-subheading", text: block.text });
    case "p":
      return sentence("p", block.segments, decimals, "prose method-p");
    case "formula":
      return sentence("p", block.segments, decimals, "method-formula");
    case "quote":
      return el("figure", { class: "method-quote" }, [
        el("blockquote", { attrs: { lang: block.lang } }, [el("p", { text: block.text })]),
        el("figcaption", { class: "note" }, [el("a", { class: "text-link", text: block.source_title, attrs: { href: block.source_url, rel: "noopener" } })]),
      ]);
    case "list": {
      const list = el("ul", { class: "method-list" });
      for (const item of block.items) {
        const segments = Array.isArray(item) ? item : resolve(item.ref);
        if (segments) list.appendChild(appendSegments(el("li"), segments, decimals));
      }
      return list;
    }
    case "ref": {
      const segments = resolve(block);
      return segments ? appendSegments(el("p", { class: "prose method-p" }), segments, decimals) : null;
    }
    case "table":
      return documentTable(block, decimals);
    case "reads":
      return READS[block.what] ? READS[block.what](decimals) : null;
    default:
      return null;
  }
}

/* A ref is formatted with the method artifact's decimals: every artifact
 * carries the same conventions block, written from one table in the export. */

function cellFor(cell, decimals) {
  if (cell.url) return el("td", { class: "method-cell" }, [el("a", { class: "text-link", text: cell.text, attrs: { href: cell.url, rel: "noopener" } })]);
  if (cell.segments) return appendSegments(el("td", { class: "method-cell" }), cell.segments, decimals);
  if (cell.format) return figureCell(formatCell(cell.value, cell.format, decimals, cell.signed === true), cell.field);
  return el("td", { class: "method-cell", text: cell.text });
}

function documentTable(block, decimals) {
  const head = el("tr", {}, block.columns.map((column) => el("th", { class: column.numeric ? "col-num" : null, text: column.label, attrs: { scope: "col", "data-short": column.short } })));
  const tbody = el("tbody");
  for (const row of block.rows) {
    const [first, ...rest] = row;
    const th = cellFor(first, decimals);
    const header = el("th", { class: "method-rowhead", attrs: { scope: "row" } }, [...th.childNodes]);
    tbody.appendChild(el("tr", {}, [header, ...rest.map((cell) => cellFor(cell, decimals))]));
  }
  return scrollTable([block.caption], el("table", { class: block.prose ? "table method-table method-table--prose" : "table method-table" }, [el("thead", {}, [head]), tbody]));
}

/* ------------------------------------------------------------- reads --- */

const DAY_FORMAT = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const dayWords = (iso) => {
  const [year, month, day] = String(iso).split("-").map(Number);
  return DAY_FORMAT.format(new Date(Date.UTC(year, month - 1, day)));
};

/* The Licence Ouverte asks for the date of last update beside the credit: the
 * latest date of the data each source supplies, or the day a document was read. */
function lastUpdate(item) {
  const dates = Object.values(item.date_of_last_update || {}).sort();
  if (dates.length) return "data to " + dayWords(dates[dates.length - 1]);
  if (item.retrieved) return "read on " + dayWords(item.retrieved);
  return "not recorded";
}

const READS = {
  /* R2 and the Newey-West lag of each response equation, from the artifact the
   * Now view's run economics section reads. */
  response_diagnostics(decimals) {
    const response = held.data.runEconomics.response;
    const d = held.data.runEconomics.conventions.decimals;
    const head = el("tr", {}, [
      el("th", { text: "Equation", attrs: { scope: "col" } }),
      el("th", { text: "Sample", attrs: { scope: "col", "data-short": "sample" } }),
      el("th", { class: "col-num", text: "Months", attrs: { scope: "col", "data-short": "months" } }),
      el("th", { class: "col-num", text: "Sum of the lags, pp per $/bbl", attrs: { scope: "col", "data-short": "sum of the lags" } }),
      el("th", { class: "col-num", text: "Newey-West SE", attrs: { scope: "col", "data-short": "Newey-West SE" } }),
      el("th", { class: "col-num", text: "t", attrs: { scope: "col", "data-short": "t" } }),
      el("th", { class: "col-num", text: "R squared", attrs: { scope: "col", "data-short": "R squared" } }),
      el("th", { class: "col-num", text: "Newey-West lag", attrs: { scope: "col", "data-short": "Newey-West lag" } }),
    ]);
    const tbody = el("tbody");
    for (const model of response.models) {
      tbody.appendChild(el("tr", { attrs: { "data-model": model.id } }, [
        el("th", { class: "method-rowhead", text: model.label, attrs: { scope: "row" } }),
        el("td", { class: "method-cell", text: monthWords(model.first_month) + " to " + monthWords(model.last_month) }),
        figureCell(formatCell(model.months, "count", d), "months"),
        figureCell(formatCell(model.sum_of_lags, "pp_per_usd_bbl", d, true), "sum_of_lags"),
        figureCell(formatCell(model.sum_of_lags_se, "pp_per_usd_bbl", d), "sum_of_lags_se"),
        figureCell(formatCell(model.t, "t", d, true), "t"),
        figureCell(formatCell(model.r2, "r2", d), "r2"),
        figureCell(formatCell(model.newey_west_lag, "count", d), "newey_west_lag"),
      ]));
    }
    return scrollTable(["Each response equation's sample, sum of the lagged coefficients with its Newey-West standard error, fit and lag. The planned model comes first."], el("table", { class: "table method-table" }, [el("thead", {}, [head]), tbody]));
  },

  /* The latest month's split: the printed $/t price of each product, the ICE
   * factor it is divided by, with the contract cited, and the crack it gives. */
  margin_stack_prices() {
    const stack = held.data.marginStack;
    const d = stack.conventions.decimals;
    const head = el("tr", {}, [
      el("th", { text: "Product, as printed", attrs: { scope: "col" } }),
      el("th", { class: "col-num", text: "Printed price, $/t", attrs: { scope: "col", "data-short": "printed price" } }),
      el("th", { class: "col-num", text: "Barrels per tonne", attrs: { scope: "col", "data-short": "barrels per tonne" } }),
      el("th", { class: "col-num", text: "Price, $/bbl", attrs: { scope: "col", "data-short": "price" } }),
      el("th", { class: "col-num", text: "Brent, $/bbl", attrs: { scope: "col", "data-short": "Brent" } }),
      el("th", { class: "col-num", text: "Crack, $/bbl", attrs: { scope: "col", "data-short": "crack" } }),
      el("th", { class: "col-num", text: "Mass yield, percent", attrs: { scope: "col", "data-short": "mass yield" } }),
      el("th", { text: "Factor from", attrs: { scope: "col", "data-short": "factor from" } }),
    ]);
    const tbody = el("tbody");
    for (const row of stack.rows.filter((r) => r.price_usd_t !== undefined)) {
      tbody.appendChild(el("tr", { attrs: { "data-row": row.id } }, [
        el("th", { class: "method-rowhead", text: row.label, attrs: { scope: "row" } }),
        figureCell(formatCell(row.price_usd_t, "usd_t", d), "price_usd_t"),
        figureCell(formatCell(row.bbl_per_t, "bbl_per_t", d), "bbl_per_t"),
        figureCell(formatCell(row.product_usd_bbl, "usd_bbl", d), "product_usd_bbl"),
        figureCell(formatCell(row.brent_usd_bbl, "usd_bbl", d), "brent_usd_bbl"),
        figureCell(formatCell(row.crack_usd_bbl, "usd_bbl", d, true), "crack_usd_bbl"),
        figureCell(formatCell(row.mass_yield_percent, "yield_percent", d), "mass_yield_percent"),
        el("td", { class: "method-cell" }, row.factor_citation ? [el("a", { class: "text-link", text: row.factor_citation.contract, attrs: { href: row.factor_citation.url, rel: "noopener" } })] : ["no factor"]),
      ]));
    }
    return scrollTable(["The ministry's printed prices for " + stack.month_label + ", each divided by its ICE contract factor and less Brent, the split the Now view draws."], el("table", { class: "table method-table" }, [el("thead", {}, [head]), tbody]));
  },

  /* Every break in the series the site reads, the list History draws from. */
  breaks() {
    const history = held.data.history;
    const head = el("tr", {}, [
      el("th", { text: "Date", attrs: { scope: "col" } }),
      el("th", { text: "Break", attrs: { scope: "col", "data-short": "break" } }),
      el("th", { text: "Where it is drawn", attrs: { scope: "col", "data-short": "where it is drawn" } }),
      el("th", { text: "Source", attrs: { scope: "col", "data-short": "source" } }),
    ]);
    const where = { monthly: "splits the monthly ", margin: "splits the extra gas line under the margin" };
    const tbody = el("tbody");
    for (const brk of history.breaks) {
      const drawn = brk.drawn ? (brk.panel === "monthly" ? where.monthly + brk.line + " line" : where.margin) : "not drawn: " + brk.reason;
      tbody.appendChild(el("tr", {}, [
        el("th", { class: "method-rowhead", text: brk.label, attrs: { scope: "row" } }),
        el("td", { class: "method-cell", text: brk.name }),
        el("td", { class: "method-cell", text: drawn }),
        el("td", { class: "method-cell" }, [el("a", { class: "text-link", text: brk.source_title || "Source", attrs: { href: brk.source_url, rel: "noopener" } })]),
      ]));
    }
    return scrollTable(["Every break in the series the site reads, in date order."], el("table", { class: "table method-table" }, [el("thead", {}, [head]), tbody]));
  },

  /* The two steps a machine cannot do, in the words the Provenance section uses. */
  manual_steps() {
    const reader = held.data.provenance.reader;
    const list = el("ul", { class: "method-list" });
    for (const step of reader.manual_steps) {
      list.appendChild(el("li", {}, [
        el("span", { class: "method-step__what", text: step.what + " " }),
        step.why + " " + step.cost + " " + step.status_sentence,
      ]));
    }
    return list;
  },

  /* Reuse terms per source, and the font disclosure. */
  reuse() {
    const provenance = held.data.provenance;
    const wrap = el("div", { class: "method-reuse" });
    const head = el("tr", {}, [
      el("th", { text: "Source", attrs: { scope: "col" } }),
      el("th", { text: "Credit line", attrs: { scope: "col", "data-short": "credit line" } }),
      el("th", { text: "Terms", attrs: { scope: "col", "data-short": "terms" } }),
      el("th", { text: "Third party", attrs: { scope: "col", "data-short": "third party" } }),
      el("th", { text: "Date of last update", attrs: { scope: "col", "data-short": "date of last update" } }),
    ]);
    const tbody = el("tbody");
    for (const item of provenance.attributions) {
      tbody.appendChild(el("tr", { attrs: { "data-source": item.id } }, [
        el("th", { class: "method-rowhead", text: item.who, attrs: { scope: "row" } }),
        el("td", { class: "method-cell", text: item.credit_line }),
        el("td", { class: "method-cell", text: item.licence }),
        el("td", { class: "method-cell", text: item.third_party || "none recorded" }),
        el("td", { class: "method-cell", text: lastUpdate(item) }),
      ]));
    }
    wrap.appendChild(scrollTable(["What each source allows, and the line that credits it wherever its data appear."], el("table", { class: "table method-table method-table--prose" }, [el("thead", {}, [head]), tbody])));
    wrap.appendChild(el("p", { class: "prose method-p", text: provenance.fonts.substitution }));
    const faces = el("ul", { class: "method-list" });
    for (const face of provenance.fonts.faces) faces.appendChild(el("li", { text: face.family + ", for " + face.use + ", " + face.licence + "." }));
    wrap.appendChild(faces);
    return wrap;
  },
};
