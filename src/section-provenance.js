/* section-provenance.js
 *
 * "Provenance", inside the Now view. docs/design.md Part 3 section 1 as
 * corrected in Part 7, C12 and C13: the manifest table, failed and stale rows
 * first, in the column order data/provenance.json lists (series, status, last
 * value, provisional, last fetch, missing dates, vintage, source); the work done
 * by hand; then who each source is credited to and on what terms, and the
 * typefaces with the Figtree for Satoshi disclosure.
 *
 * WHOSE WORDS. data/provenance.json carries the manifest whole, which is the
 * pipeline's record for whoever maintains it, and a reader layer written for
 * this page: a label and a source per series, whether any of it is provisional,
 * and the manual steps in sentences. Everything this module prints comes from
 * the reader layer or from a manifest field that is already a value (a status,
 * a date, a count); nothing prints a series id or a manual step verbatim.
 *
 * Nothing here is summarised into a count or a badge. A status is a word in a
 * cell at full ink. A gap is a count of missing dates with the first and last
 * named. A series no machine fetches says so instead of printing an empty
 * fetch time.
 *
 * Numeric literals: none.
 */

import { el, sentence, scrollTable } from "./dom.js";
import { formatCell, formatInstant } from "./format.js";
import { artifactUrl } from "./state.js";

export const artifact = "provenance";
export const loading = "the manifest of every series, its source and its last fetch";

/* Each column's header and the short name the caption uses when it is off
 * screen. */
const COLUMNS = Object.freeze({
  series: { head: "Series", short: "series" },
  status: { head: "Status", short: "status" },
  last_date: { head: "Last value", short: "last value" },
  provisional: { head: "Provisional", short: "provisional" },
  fetched_at: { head: "Last fetch", short: "last fetch" },
  gaps: { head: "Missing dates", short: "missing dates" },
  vintage: { head: "Vintage", short: "vintage" },
  source: { head: "Source", short: "source" },
});

/* Rows that did not come back cleanly lead the table. */
const TROUBLE = new Set(["failed", "stale"]);

export function render(inner, data) {
  const decimals = data.conventions.decimals;
  const manifest = data.manifest;
  const reader = data.reader || { series: {}, manual_steps: [] };
  const columns = data.manifest_columns;

  const series = [...manifest.series].sort((a, b) => Number(TROUBLE.has(b.status)) - Number(TROUBLE.has(a.status)));
  const head = el("tr", {}, columns.map((column) => el("th", {
    class: column === "last_date" ? "col-num" : "",
    text: COLUMNS[column] ? COLUMNS[column].head : column,
    attrs: { scope: "col", "data-short": COLUMNS[column] ? COLUMNS[column].short : null },
  })));
  const body = el("tbody");
  for (const entry of series) {
    const words = reader.series[entry.series] || {};
    body.appendChild(el("tr", { attrs: { "data-series": entry.series, "data-status": entry.status } }, columns.map((column) => cellFor(column, entry, words, decimals))));
  }
  const table = el("table", { class: "table manifest-table" }, [el("thead", {}, [head]), body]);
  /* GATE 5 FINDING 8. This caption and the summary sentence above it both said
   * "last", twenty nine minutes apart, and the later one belonged to a run that
   * opened no socket. The two are different things and the caption now says
   * which this one is: when the manifest was last written, and whether that run
   * fetched anything. The time of the last fetch of a series stays where it
   * belongs, in the summary sentence and in the Last fetch column. */
  const run = manifest.run || {};
  const wrote = run.mode === "offline"
    ? ", a run that reread the committed files and fetched nothing"
    : (run.mode ? ", a run that fetched from the sources" : "");
  inner.appendChild(el("div", { class: "block" }, [scrollTable([
    "Every series the study reads, as the manifest recorded it at " + (formatInstant(manifest.generated_at) || "a time it did not record") + wrote + "; failed and stale series first. Each series' own last fetch is in its row.",
  ], table)]));

  // The work done by hand, in the reader layer's words.
  const steps = reader.manual_steps || [];
  if (steps.length) {
    const block = el("div", { class: "block" }, [el("h3", { class: "block__heading", text: reader.manual_steps_heading })]);
    if (reader.manual_steps_intro) block.appendChild(el("p", { class: "prose", text: reader.manual_steps_intro }));
    for (const step of steps) {
      const item = el("div", { class: "manual-step", attrs: { "data-step": step.id, "data-status": step.status } });
      item.appendChild(el("p", { class: "prose" }, [
        el("span", { class: "manual-step__what", text: step.what }),
        document.createTextNode(" " + step.status_sentence),
      ]));
      item.appendChild(el("p", { class: "prose", text: "Why: " + step.why }));
      item.appendChild(el("p", { class: "prose", text: "What it costs while it is not done: " + step.cost }));
      item.appendChild(el("p", { class: "prose", text: "How: " + step.how }));
      block.appendChild(item);
    }
    inner.appendChild(block);
  }

  // Attributions and terms. A credit line that only repeats the name is said once.
  const credits = el("div", { class: "block" }, [el("h3", { class: "block__heading", text: "Who the figures are credited to, and on what terms" })]);
  const list = el("ul", { class: "credit-list" });
  for (const source of data.attributions || []) {
    let name = source.who;
    let credit = source.credit_line || "";
    if (credit === name || name.startsWith(credit)) credit = "";
    else if (credit.startsWith(name)) {
      name = credit;
      credit = "";
    }
    const item = el("li", { class: "prose", attrs: { "data-source": source.id } }, [el("span", { class: "credit__who", text: name }), document.createTextNode(".")]);
    if (credit) item.appendChild(document.createTextNode(" Credit line: \"" + credit + "\"."));
    item.appendChild(document.createTextNode(" Terms: " + source.licence + "."));
    if (source.third_party) item.appendChild(document.createTextNode(" " + source.third_party));
    list.appendChild(item);
  }
  credits.appendChild(list);
  inner.appendChild(credits);

  /* GATE 5 FINDING 6. data/manifest.json is deployed, versioned in the import
   * map and described in the README as the first class provenance artifact, and
   * before this line nothing on the site ever requested it: the page reads the
   * copy inside data/provenance.json. It is data present in the deployment and
   * unreachable in the UI, which is what SPEC.md section 11 point 8 calls an
   * orphan. The link makes it reachable, through the same content hashed URL
   * every other artifact is fetched at, and says what it is so that nobody
   * opens it expecting this table. */
  inner.appendChild(el("div", { class: "block" }, [
    el("p", { class: "prose" }, [
      "This table is the reader's view of the pipeline's own record. That record is published whole beside the site, as it was written, for anyone who wants to check it or to machine read it: ",
      el("a", { class: "text-link", text: "the manifest of every series, as JSON", attrs: { href: artifactUrl("data/manifest.json"), rel: "noopener" } }),
      ".",
    ]),
  ]));

  // Typefaces and the one substitution.
  if (data.fonts) {
    const faces = el("div", { class: "block" }, [el("h3", { class: "block__heading", text: "Typefaces" })]);
    const names = (data.fonts.faces || []).map((face) => face.family + " for " + face.use + ", " + face.licence);
    if (names.length) faces.appendChild(el("p", { class: "prose", text: names.join("; ") + "." }));
    if (data.fonts.substitution) faces.appendChild(el("p", { class: "prose", text: data.fonts.substitution }));
    inner.appendChild(faces);
  }
}

function cellFor(column, entry, words, decimals) {
  switch (column) {
    case "series":
      return el("th", { class: "manifest__series", text: words.label || entry.series, attrs: { scope: "row" } });
    case "status":
      return el("td", { class: "status-word", text: entry.status, attrs: { "data-field": "status" } });
    case "last_date":
      return entry.last_date
        ? el("td", { class: "num", text: entry.last_date, attrs: { "data-field": "last_date" } })
        : el("td", { class: "manifest__words", text: "none", attrs: { "data-field": "last_date" } });
    case "provisional":
      return sentence("td", words.provisional_segments || [], decimals, "manifest__words manifest__provisional");
    case "fetched_at": {
      if (words.fetch_words) return el("td", { class: "manifest__fetch", text: words.fetch_words, attrs: { "data-field": "fetched_at" } });
      if (!entry.fetched_at) return el("td", { class: "manifest__fetch", text: "no fetch recorded", attrs: { "data-field": "fetched_at" } });
      return el("td", { class: "manifest__fetch", text: formatInstant(entry.fetched_at) || entry.fetched_at, attrs: { "data-field": "fetched_at" } });
    }
    case "gaps": {
      const gaps = entry.gaps || [];
      if (!gaps.length) return el("td", { class: "manifest__words manifest__gaps", text: "none", attrs: { "data-field": "gaps" } });
      const first = gapDate(gaps[0], true);
      const last = gapDate(gaps[gaps.length - 1], false);
      const count = formatCell(gaps.length, "count", decimals);
      let text = count + (gaps.length === 1 ? " date, " + first : " dates, " + first + " to " + last);
      if (words.gaps_reason) text += "; " + words.gaps_reason;
      return el("td", { class: "manifest__words manifest__gaps", text, attrs: { "data-field": "gaps" } });
    }
    case "vintage":
      return el("td", { class: "manifest__vintage", text: entry.vintage === null || entry.vintage === undefined ? "none recorded" : String(entry.vintage) });
    case "source": {
      const href = entry.page_url || entry.url;
      const name = words.source || entry.source;
      const cell = el("td", { class: "manifest__source" });
      if (href) cell.appendChild(el("a", { class: "text-link", text: name, attrs: { href, rel: "noopener" } }));
      else cell.appendChild(document.createTextNode(name));
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
