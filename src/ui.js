/* ui.js
 *
 * The entry module. It wires the theme, builds the nav from the route table,
 * starts the router, loads what a view needs, and renders the view or an
 * honest sentence saying why it cannot.
 *
 * THE ROUTE TABLE IS THE ONLY LIST OF VIEWS. The nav is built from it, the
 * router is told its names, and nothing else in the site names a view. At Gate
 * 5 it holds Now, History, Model, Runs and crude demand, Events and Method. A view that is not built is not linked, because a
 * link to a view with no data behind it is an orphan UI state, SPEC.md section
 * 11 point 8. A view is added by adding one entry below and one module;
 * router.js does not change.
 *
 * Numeric literals: none. tools/check-literals.mjs.
 */

import * as router from "./router.js";
import * as state from "./state.js";
import { initTheme } from "./theme.js";
import { el, clear, loadingMessage, failureMessages } from "./dom.js";
import * as now from "./now.js";
import * as historyView from "./history.js";
import * as modelView from "./model.js";
import * as runsView from "./runs.js";
import * as eventsView from "./events.js";
import * as methodView from "./method.js";

const SITE_NAME = "NWE crack spread study";
const DEFAULT_VIEW = "now";

/* name: the hash segment. label: the nav text and the document title.
 * module: exports `artifacts`, the state.js names it needs, and
 * render(root, data, route), which returns the element that takes focus. */
const ROUTES = [
  { name: "now", label: "Now", loading: "the landing sentence and its data dates", module: now },
  { name: "history", label: "History", loading: "the monthly and weekly cracks and the ministry's margin since the start of the data", module: historyView },
  { name: "model", label: "Model", loading: "the margin model's presets and the source of every input", module: modelView },
  { name: "runs", label: "Runs and crude demand", loading: "the response of crude runs to the margin, the run cut threshold, the horse race, the instrument and the residuals after the strikes on Iran", module: runsView },
  { name: "events", label: "Events", loading: "the thirteen months around each event", module: eventsView },
  { name: "method", label: "Method", loading: "the formulas, the assumptions and their sources, the cross checks and the limitations", module: methodView },
];

/* The views SPEC.md section 7.2 names, in nav order, for the unknown address
 * sentence: the ones not in ROUTES are said to be unpublished, by name, and
 * never linked. */
const PLANNED = Object.freeze(["Now", "History", "Model", "Runs and crude demand", "Events", "Method"]);

const byName = new Map(ROUTES.map((route) => [route.name, route]));
const viewRoot = document.querySelector("#view");
let renderToken = 0;

function buildNav() {
  const list = document.querySelector("#site-nav-list");
  if (!list) return;
  clear(list);
  for (const route of ROUTES) {
    list.appendChild(el("li", {}, [
      el("a", { class: "site-nav__link", text: route.label, attrs: { href: router.href(route.name), "data-view": route.name } }),
    ]));
  }
}

function markCurrent(viewName) {
  for (const link of document.querySelectorAll(".site-nav__link")) {
    if (link.getAttribute("data-view") === viewName) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}

function setTitle(label) {
  document.title = label + ", " + SITE_NAME;
}

/* Move focus to the new view's h1 on a route change, never on first load,
 * where it would scroll past the skip link. Part 3 section 9. */
function focusTitle(target, isFirstLoad) {
  if (isFirstLoad || !target) return;
  target.focus({ preventScroll: false });
}

function unpublishedSentence() {
  const missing = PLANNED.filter((label) => !ROUTES.some((route) => route.label === label));
  if (!missing.length) return "";
  const list = missing.length === 1 ? missing[0] : missing.slice(0, -1).join(", ") + " and " + missing[missing.length - 1];
  return list + (missing.length === 1 ? " is" : " are") + " not published yet, so a link to " + (missing.length === 1 ? "it" : "one of them") + " leads here.";
}

/* An address that names no view. It says what happened, which address, and
 * what to do, and links only to views that exist. */
function renderUnknown(route, isFirstLoad) {
  markCurrent(null);
  setTitle("No view at this address");
  clear(viewRoot);
  const title = el("h1", { class: "view-title", id: "view-title", text: "There is no view at this address.", attrs: { tabindex: "-1" } });
  const typed = route.view === null || route.view === undefined ? "" : String(route.view);
  const names = ROUTES.map((entry) => entry.label).join(", ");
  const said = el("p", { class: "state-message" }, [
    "The address ends in " + route.hash + ", and this study has no view called \u201C" + typed + "\u201D. ",
    "The views published so far are: " + names + ". ",
    unpublishedSentence(),
  ]);
  const todo = el("p", { class: "state-message" }, [
    "Check the address for a typing mistake, or ",
    el("a", { text: "open the Now view", attrs: { href: router.href(DEFAULT_VIEW) } }),
    ".",
  ]);
  viewRoot.appendChild(title);
  viewRoot.appendChild(said);
  viewRoot.appendChild(todo);
  focusTitle(title, isFirstLoad);
}

async function renderRoute(route, previous) {
  const isFirstLoad = previous === null;

  // A plain fragment, for example the skip link without script: keep the view.
  if (route.kind === "fragment") {
    if (previous === null) renderRoute(router.parse("", ROUTES.map((entry) => entry.name), DEFAULT_VIEW), null);
    return;
  }
  if (route.kind === "unknown") {
    renderToken += 1;
    renderUnknown(route, isFirstLoad);
    return;
  }

  const entry = byName.get(route.view);
  // Only the view state changed, for example a section opening: the view
  // handles that itself and the page is not rebuilt.
  if (previous && previous.kind === "route" && previous.view === route.view && viewRoot.childElementCount && entry.module.update) {
    entry.module.update(viewRoot, route);
    return;
  }

  renderToken += 1;
  const token = renderToken;
  markCurrent(entry.name);
  setTitle(entry.label);
  clear(viewRoot);
  viewRoot.appendChild(loadingMessage(entry.loading));

  const result = await state.loadAll(entry.module.artifacts);
  if (token !== renderToken) return; // a later route replaced this one

  clear(viewRoot);
  if (!result.ok) {
    const title = el("h1", { class: "view-title", id: "view-title", text: entry.label + " could not be shown.", attrs: { tabindex: "-1" } });
    viewRoot.appendChild(title);
    for (const node of failureMessages(result.failures)) viewRoot.appendChild(node);
    focusTitle(title, isFirstLoad);
    return;
  }
  const target = entry.module.render(viewRoot, result.data, route);
  focusTitle(target, isFirstLoad);
}

/* The skip link moves focus to the view's h1 without changing the address, so
 * the route and any open sections survive. Without script, the fragment does
 * the job and the router keeps the view. */
function wireSkipLink() {
  const link = document.querySelector("[data-skip]");
  if (!link) return;
  link.addEventListener("click", (ev) => {
    const target = document.querySelector("#view-title");
    if (!target) return;
    ev.preventDefault();
    target.focus();
  });
}

initTheme();
buildNav();
wireSkipLink();
router.start(ROUTES.map((route) => route.name), DEFAULT_VIEW, (route, previous) => {
  renderRoute(route, previous);
});
