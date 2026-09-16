/* dom.js
 *
 * The few element helpers every view needs: build an element, empty one, set
 * a sentence of segments with each figure in its own span, and set the
 * loading, failure and empty sentences from format.js. Nothing here knows what
 * a crack or a margin is.
 *
 * Numeric literals: none. tools/check-literals.mjs.
 */

import { segmentText, missingFigureText, loadFailureSentences, loadingSentence, emptySeriesSentence } from "./format.js";

/** Build an element. `options.attrs` skips null and undefined, so a caller can
 *  pass a conditional attribute without a branch. Children may be strings,
 *  nodes, or null. */
export function el(tag, options, children) {
  const node = document.createElement(tag);
  const opts = options || {};
  if (opts.class) node.className = opts.class;
  if (opts.id) node.id = opts.id;
  if (opts.text !== undefined) node.textContent = opts.text;
  if (opts.attrs) {
    for (const [name, value] of Object.entries(opts.attrs)) {
      if (value === null || value === undefined) continue;
      node.setAttribute(name, String(value));
    }
  }
  for (const child of children || []) {
    if (child === null || child === undefined) continue;
    node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

/** Set a sentence the export wrote as segments into `parent`.
 *
 *  Words become text nodes. A number becomes span.fig with data-field naming
 *  where it came from, so a test in the browser can walk every figure on the
 *  page back to a field. A date or a word with a label becomes a span with its
 *  ISO value in data-value; a field ending in status_word is set in
 *  span.status-word, weight 500, Part 3 section 1. A missing number is not
 *  printed as a number: it becomes the words "no figure for {field}". */
export function appendSegments(parent, segments, decimals) {
  for (const segment of segments) {
    const piece = segmentText(segment, decimals);
    if (piece.kind === "text") {
      parent.appendChild(document.createTextNode(piece.text));
    } else if (piece.kind === "number") {
      parent.appendChild(el("span", {
        class: piece.missing ? "fig is-missing" : "fig",
        text: piece.missing ? missingFigureText(piece.field) : piece.text,
        attrs: { "data-field": piece.field },
      }));
    } else {
      const isStatus = /status_word$/.test(String(piece.field));
      parent.appendChild(el("span", {
        class: isStatus ? "status-word" : "fig",
        text: piece.text,
        attrs: { "data-field": piece.field, "data-value": segment.value },
      }));
    }
  }
  return parent;
}

/** A paragraph saying what is loading. */
export function loadingMessage(what) {
  return el("p", { class: "state-message", text: loadingSentence(what), attrs: { role: "status" } });
}

/** Paragraphs for every artifact that failed, each with its time and what to
 *  do. SPEC.md section 7.3. */
export function failureMessages(failures) {
  const nodes = [];
  for (const failure of failures) {
    for (const sentence of loadFailureSentences(failure)) {
      nodes.push(el("p", { class: "state-message", text: sentence }));
    }
  }
  if (nodes.length) nodes[0].setAttribute("role", "alert");
  return nodes;
}

/** The paragraph an empty chart shows in place of its marks. */
export function emptySeriesMessage(details) {
  return el("p", { class: "state-message", text: emptySeriesSentence(details) });
}
