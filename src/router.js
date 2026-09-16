/* router.js
 *
 * Owns location.hash and nothing else. It does not know what a view is, what a
 * crack is, or what any artifact holds. It parses the hash, tells its one
 * listener what the hash now says, and writes the hash when asked.
 *
 * Three shapes of hash, kept apart on purpose:
 *
 *   #/now                   a route: the view name is the first segment
 *   #/now?open=cracks,runs  a route carrying view state after the question
 *                           mark, parsed to a plain object of strings. Part 3
 *                           section 1: an open section is linkable
 *   #view-title             a document fragment, for example the skip link
 *                           without script. Not a route. Reported as such so
 *                           the caller keeps the view the visitor is reading
 *   (empty), #, #/          the default route
 *
 * WHICH VIEWS EXIST IS NOT DECIDED HERE. The caller passes the set of known view
 * names to start(). A route to a name outside that set is reported as
 * { kind: "unknown" } with the name the visitor typed, so the caller can say
 * what happened instead of silently landing on Now. Gate 5 adds a view by
 * adding a name to the caller's table; this file does not change.
 *
 * Numeric literals: none about the market. 0 appears as a string index and a
 * length boundary, which is index arithmetic. tools/check-literals.mjs.
 */

const ROUTE_PREFIX = "#/";

let knownViews = new Set();
let defaultView = null;
let listener = null;
let lastRoute = null;

/** Split "a=1&b=two" into { a: "1", b: "two" }. A repeated key keeps the last
 *  value; a key with no value is an empty string, so absent and empty differ. */
function parseQuery(text) {
  const out = {};
  for (const part of text.split("&")) {
    if (part === "") continue;
    const at = part.indexOf("=");
    const key = safeDecode(at < 0 ? part : part.slice(0, at));
    const value = at < 0 ? "" : safeDecode(part.slice(at + 1));
    if (key !== null && key !== "" && value !== null) out[key] = value;
  }
  return out;
}

/* A malformed percent escape in a hand typed address must not throw out of the
 * router and leave a blank page. It is reported as undecodable instead. */
function safeDecode(text) {
  try {
    return decodeURIComponent(text);
  } catch (error) {
    return null;
  }
}

/** Parse a hash string. Pure, so it can be tested without a window.
 *
 *  Returns one of
 *    { kind: "route",    view, params, hash }
 *    { kind: "unknown",  view, params, hash }   view is what the visitor typed
 *    { kind: "fragment", id, hash }
 */
export function parse(hash, views, fallback) {
  const known = views instanceof Set ? views : new Set(views);
  if (!hash || hash === "#" || hash === ROUTE_PREFIX) {
    return { kind: "route", view: fallback, params: {}, hash: ROUTE_PREFIX };
  }
  if (!hash.startsWith(ROUTE_PREFIX)) {
    return { kind: "fragment", id: safeDecode(hash.slice("#".length)), hash };
  }
  const mark = hash.indexOf("?");
  const path = mark < 0 ? hash.slice(ROUTE_PREFIX.length) : hash.slice(ROUTE_PREFIX.length, mark);
  const params = mark < 0 ? {} : parseQuery(hash.slice(mark + "?".length));
  const segments = path.split("/").map((part) => safeDecode(part));
  const name = segments.some((part) => part === null) ? null : segments.filter((part) => part !== "").join("/");
  if (name === "") {
    return { kind: "route", view: fallback, params, hash };
  }
  if (name !== null && known.has(name)) {
    return { kind: "route", view: name, params, hash };
  }
  return { kind: "unknown", view: name === null ? path : name, params, hash };
}

/** Build the hash for a view and its state. Keys with an empty value are left
 *  out, and the keys are written in sorted order, so one state has one address. */
export function href(view, params) {
  const pairs = Object.entries(params || {})
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([key, value]) => encodeURIComponent(key) + "=" + encodeURIComponent(value).replace(/%2C/g, ","));
  return ROUTE_PREFIX + encodeURIComponent(view) + (pairs.length ? "?" + pairs.join("&") : "");
}

/** The route the hash names now. */
export function current() {
  return parse(window.location.hash, knownViews, defaultView);
}

/** Navigate. Adds a history entry, so Back works. */
export function go(view, params) {
  const next = href(view, params);
  if (window.location.hash === next) {
    announce();
    return;
  }
  window.location.hash = next;
}

/** Rewrite the address for a change of view state, for example a section
 *  opening, WITHOUT a history entry and WITHOUT announcing it: the view already
 *  holds that state, and announcing would send it back into its own render. */
export function replaceState(view, params) {
  const next = href(view, params);
  if (window.location.hash === next) return;
  const url = window.location.pathname + window.location.search + next;
  window.history.replaceState(null, "", url);
  lastRoute = parse(next, knownViews, defaultView);
}

/** Start listening. `views` is the caller's list of view names that exist,
 *  `fallback` the one an empty hash means. The listener receives
 *  (route, previous), where previous is the last route announced or null on
 *  first load. A fragment hash is announced with the previous route, so the
 *  caller can keep it. */
export function start(views, fallback, onRoute) {
  knownViews = new Set(views);
  defaultView = fallback;
  listener = onRoute;
  window.addEventListener("hashchange", announce);
  announce();
}

function announce() {
  const route = current();
  const previous = lastRoute;
  if (route.kind !== "fragment") lastRoute = route;
  if (listener) listener(route, previous);
}
