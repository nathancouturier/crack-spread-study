/* now.js
 *
 * The Now view, as far as the shell goes at this commit: the verdict sentence
 * and the three data dates, both read from data/now.json as segments. The four
 * sections under them (Part 3 section 1) are the next step of Gate 4 and render
 * into the element this module leaves for them, id now-sections. They are not
 * drawn as closed rows yet, because a row that opens onto nothing is an orphan
 * UI state, SPEC.md section 11 point 8.
 *
 * Numeric literals: none. Every figure is a segment of now.json.
 */

import { el, appendSegments } from "./dom.js";

export const artifacts = Object.freeze(["now"]);

/** Render into `root`. `data` holds the loaded artifacts by name. Returns the
 *  element that takes focus on a route change: the verdict h1. */
export function render(root, data) {
  const now = data.now;
  const decimals = now.conventions.decimals;

  const verdict = el("h1", { class: "verdict", id: "view-title", attrs: { tabindex: "-1" } });
  appendSegments(verdict, now.verdict.segments, decimals);

  const dates = el("ul", { class: "data-dates", attrs: { "aria-label": "Data dates" } });
  for (const row of now.data_dates) {
    dates.appendChild(appendSegments(el("li", { attrs: { "data-date": row.id } }), row.segments, decimals));
  }

  root.appendChild(verdict);
  root.appendChild(dates);
  root.appendChild(el("div", { class: "sections", id: "now-sections" }));
  return verdict;
}
