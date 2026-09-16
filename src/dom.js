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

/** A sentence element of segments: el(tag) with appendSegments. */
export function sentence(tag, segments, decimals, className) {
  return appendSegments(el(tag, { class: className }), segments, decimals);
}

/** A button that shows and hides a region under it, named for what the region
 *  holds (docs/design.md Part 3 section 9, S7). The region is built on first
 *  open by `build`, so a closed alternative costs nothing. Enter and Space work
 *  because it is a native button. */
export function disclosure(label, build) {
  const region = el("div", { class: "disclosure__region", id: uniqueId("alt") });
  region.hidden = true;
  const button = el("button", {
    class: "disclosure__button",
    text: label,
    attrs: { type: "button", "aria-expanded": "false", "aria-controls": region.id },
  });
  let built = false;
  button.addEventListener("click", () => {
    const open = button.getAttribute("aria-expanded") !== "true";
    if (open && !built) {
      region.appendChild(build());
      built = true;
    }
    button.setAttribute("aria-expanded", open ? "true" : "false");
    region.hidden = !open;
  });
  return el("div", { class: "disclosure" }, [button, region]);
}

let uniqueCounter = 0;
/** A document unique id. */
export function uniqueId(prefix) {
  uniqueCounter += 1;
  return prefix + "-" + String(uniqueCounter);
}

/** A wide table under its caption, docs/design.md Part 3 section 5 as corrected
 *  in Part 7, C13.
 *
 *  The caption is a paragraph ABOVE the scroll box, not a caption element inside
 *  it: inside, it takes the table's width and is clipped with the columns it is
 *  meant to announce. The table names the paragraph with aria-labelledby, so its
 *  accessible name is unchanged.
 *
 *  The paragraph ends with the columns that are off screen, measured, at every
 *  width and scroll position: "The vintage and source columns are to the right."
 *  Nothing is said when the table fits. A column's short name is its header's
 *  data-short attribute, or its header text.
 *
 *  While the table overflows, the box takes keyboard focus so it can be scrolled
 *  with the arrow keys in every engine, and a control that takes focus inside it
 *  is scrolled fully into view with its focus ring, which the browser's own
 *  scroll into view does not do for a control that is partly visible.
 *
 *  captionChildren  strings or nodes, the caption's own words
 *  table            the table element */
export function scrollTable(captionChildren, table) {
  const id = uniqueId("table-caption");
  const more = el("span", { class: "table-caption__more" });
  const caption = el("p", { class: "table-caption", id }, [...captionChildren, more]);
  table.setAttribute("aria-labelledby", id);
  const scroller = el("div", { class: "table-scroll", attrs: { role: "region", "aria-labelledby": id } }, [table]);

  const update = () => {
    if (scroller.clientWidth === 0) return; // inside a closed section, not laid out
    const overflows = scroller.scrollWidth > scroller.clientWidth;
    if (overflows) scroller.tabIndex = 0;
    else scroller.removeAttribute("tabindex");
    const words = overflows ? offScreenWords(scroller, table) : "";
    if (more.textContent !== words) more.textContent = words;
  };
  scroller.addEventListener("scroll", update, { passive: true });
  if (typeof ResizeObserver === "function") {
    const observer = new ResizeObserver(update);
    observer.observe(scroller);
    observer.observe(table);
  } else {
    window.addEventListener("resize", update, { passive: true });
  }

  const reveal = (target) => {
    if (!target || target === scroller || !scroller.contains(target)) return;
    const style = getComputedStyle(target);
    const ring = (parseFloat(style.outlineWidth) || 0) + (parseFloat(style.outlineOffset) || 0);
    const box = scroller.getBoundingClientRect();
    const rect = target.getBoundingClientRect();
    const row = target.closest("tr");
    const first = row ? row.firstElementChild : null;
    const sticky = first && !first.contains(target) && getComputedStyle(first).position === "sticky" ? first.getBoundingClientRect().width : 0;
    const overRight = rect.right + ring - box.right;
    const overLeft = box.left + sticky - (rect.left - ring);
    if (overRight > 0 && overLeft <= 0) scroller.scrollLeft += Math.min(overRight, -overLeft);
    else if (overLeft > 0) scroller.scrollLeft -= overLeft;
  };
  scroller.addEventListener("focusin", (event) => {
    reveal(event.target);
    requestAnimationFrame(() => reveal(event.target));
  });

  return el("div", { class: "table-block" }, [caption, scroller]);
}

/* The sentence naming the columns a scroll box cuts off, or "". */
function offScreenWords(scroller, table) {
  const heads = [...table.querySelectorAll("thead tr:last-child th")].filter((th) => th.getBoundingClientRect().width > 0);
  if (heads.length < 1 + 1) return "";
  const tableLeft = table.getBoundingClientRect().left + scroller.scrollLeft;
  const sticky = getComputedStyle(heads[0]).position === "sticky" ? heads[0].getBoundingClientRect().width : 0;
  const visibleLeft = scroller.scrollLeft + sticky;
  const visibleRight = scroller.scrollLeft + scroller.clientWidth;
  const right = [];
  const left = [];
  heads.slice(1).forEach((th) => {
    const rect = th.getBoundingClientRect();
    const start = rect.left + scroller.scrollLeft - tableLeft;
    const end = start + rect.width;
    if (end > visibleRight + 1) right.push(shortName(th));
    else if (start < visibleLeft - 1) left.push(shortName(th));
  });
  return columnsSentence(right, "to the right") + columnsSentence(left, "to the left");
}

function shortName(th) {
  const name = (th.dataset.short || th.textContent || "").trim();
  return /^[A-Z][a-z]/.test(name) ? name.charAt(0).toLowerCase() + name.slice(1) : name;
}

/* " The a, b and c columns are to the right." More than a handful of columns
 * are named by the first of them, so a year by year table does not list ten. */
const MOST_NAMED = 4;
function columnsSentence(names, where) {
  if (!names.length) return "";
  if (names.length > MOST_NAMED) return " The columns from " + names[0] + " on are " + where + ".";
  const list = names.length === 1 ? names[0] : names.slice(0, -1).join(", ") + " and " + names[names.length - 1];
  return " The " + list + (names.length === 1 ? " column is " : " columns are ") + where + ".";
}

/** A table cell holding a figure, or the words for a missing one. */
export function figureCell(text, field, className) {
  if (text === null) {
    return el("td", { class: "num is-missing", text: missingFigureText(field) });
  }
  return el("td", { class: className ? "num " + className : "num", text, attrs: { "data-field": field } });
}
