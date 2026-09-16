/* state.js
 *
 * Loads the JSON artifacts, holds them, and holds the little view state the
 * address carries. That is the whole job.
 *
 * It touches no DOM, reads no hash and formats nothing. router.js owns the
 * hash, format.js turns values into text, dom.js builds elements, and each view
 * module renders what it is handed from here.
 *
 * A failure is kept, not thrown away. Every failed load is recorded with the
 * path, what went wrong in words, and the time the fetch failed, because
 * SPEC.md section 7.3 says an empty chart names the missing series and the time
 * of the failed fetch, and that time only exists if it is written down here at
 * the moment it happens.
 *
 * Numeric literals: none. tools/check-literals.mjs.
 */

/* Every artifact the site reads, by name, with what it holds in words for the
 * failure sentence. Paths are relative to index.html: a leading slash would
 * break the subpath deploy. */
const ARTIFACTS = Object.freeze({
  now: { path: "data/now.json", holds: "the landing sentence and the data dates" },
  cracks: { path: "data/cracks.json", holds: "the gasoil and gasoline cracks against the same week in earlier years" },
  marginStack: { path: "data/margin-stack.json", holds: "the waterfall from the cracks to the refining margin" },
  runEconomics: { path: "data/run-economics.json", holds: "the run cut threshold and the response of crude runs to the margin" },
  provenance: { path: "data/provenance.json", holds: "the manifest of every series, its source and its last fetch" },
});

const loaded = new Map();
const failures = new Map();
const pending = new Map();

function failureRecord(name, what, detail) {
  return {
    artifact: name,
    path: ARTIFACTS[name].path,
    holds: ARTIFACTS[name].holds,
    what,
    detail: detail || "",
    at: new Date().toISOString(),
  };
}

async function fetchArtifact(name) {
  const { path } = ARTIFACTS[name];
  let response;
  try {
    response = await fetch(path, { cache: "no-cache" });
  } catch (error) {
    throw failureRecord(name, "the request did not complete, so the network or the server is unreachable", String(error && error.message ? error.message : error));
  }
  if (!response.ok) {
    const statusText = response.statusText ? " " + response.statusText : "";
    throw failureRecord(name, "the server answered " + String(response.status) + statusText);
  }
  try {
    return await response.json();
  } catch (error) {
    throw failureRecord(name, "the file arrived but is not valid JSON", String(error && error.message ? error.message : error));
  }
}

/** Load one artifact, or hand back the copy already held. A second caller
 *  while the first request is still out shares that request. */
export function load(name) {
  if (!Object.prototype.hasOwnProperty.call(ARTIFACTS, name)) {
    return Promise.reject(new Error("state.js knows no artifact called " + name));
  }
  if (loaded.has(name)) return Promise.resolve(loaded.get(name));
  if (pending.has(name)) return pending.get(name);
  const request = fetchArtifact(name)
    .then((data) => {
      loaded.set(name, data);
      failures.delete(name);
      return data;
    })
    .catch((failure) => {
      failures.set(name, failure);
      throw failure;
    })
    .finally(() => pending.delete(name));
  pending.set(name, request);
  return request;
}

/** Load several. Resolves to { ok, data, failures }, reporting EVERY failure
 *  rather than the first, so the page can name each missing file. */
export async function loadAll(names) {
  const results = await Promise.allSettled(names.map((name) => load(name)));
  const data = {};
  const broken = [];
  results.forEach((result, index) => {
    const name = names[index];
    if (result.status === "fulfilled") data[name] = result.value;
    else if (result.reason && result.reason.artifact) broken.push(result.reason);
    else broken.push(failureRecord(name, "the load failed", String(result.reason)));
  });
  return { ok: broken.length === 0, data, failures: broken };
}

/** The artifact, or undefined if it never arrived. */
export function artifact(name) {
  return loaded.get(name);
}

/** What went wrong with one artifact, with the time the fetch failed. */
export function failure(name) {
  return failures.get(name);
}

/** Forget a failure so the next load tries again, for a retry control. */
export function forget(name) {
  failures.delete(name);
  loaded.delete(name);
}

/* ------------------------------------------------------ view state --- */

/* The only view state at Gate 4: which Now sections are open. It lives in the
 * address, #/now?open=cracks,runs, so this is a parser of that parameter and a
 * writer back to it, holding no copy that could drift from the hash. */

/** The open section ids from a route's params, in the order the caller's
 *  `known` list gives them, dropping anything that is not a section. */
export function openSections(params, known) {
  const asked = new Set(String((params && params.open) || "").split(",").filter((id) => id !== ""));
  return known.filter((id) => asked.has(id));
}

/** The params for a set of open sections, ready for router.href. */
export function openParams(openIds) {
  return openIds.length ? { open: openIds.join(",") } : {};
}
