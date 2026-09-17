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
 * Numeric literals: SCHEMA_ONE, the schema version this page reads, which is
 * 1 and passes tools/check-literals.mjs as a count. A version 2 would have to
 * be declared there with its reason.
 */

/* THE SCHEMA GUARD. Every artifact carries schema_version and its own name
 * (src/crack/export.py _header). This page was written against the layout of
 * one schema version per artifact, declared below, and refuses any other: an
 * artifact whose version or name it does not know is not drawn, and the page
 * says which file and what to do. That is the backstop for a mixed deploy, when
 * a cache hands an old copy of this module a new artifact or the other way
 * round (src/crack/versions.py): a layout read with the wrong expectations can
 * print a wrong number without any error, and a refusal cannot. A schema bump
 * in the export must change the number here in the same commit, and
 * tools/validate-format.mjs fails the gate on every committed artifact this
 * page would refuse. */
const SCHEMA_ONE = 1;

/* Every artifact the site reads, by name, with what it holds in words for the
 * failure sentence. Paths are relative to index.html: a leading slash would
 * break the subpath deploy. */
const ARTIFACTS = Object.freeze({
  now: { path: "data/now.json", artifact: "now", schema: SCHEMA_ONE, holds: "the landing sentence and the data dates" },
  cracks: { path: "data/cracks.json", artifact: "cracks", schema: SCHEMA_ONE, holds: "the gasoil and gasoline cracks against the same week in earlier years" },
  marginStack: { path: "data/margin-stack.json", artifact: "margin-stack", schema: SCHEMA_ONE, holds: "the waterfall from the cracks to the refining margin" },
  runEconomics: { path: "data/run-economics.json", artifact: "run-economics", schema: SCHEMA_ONE, holds: "the run cut threshold and the response of crude runs to the margin" },
  provenance: { path: "data/provenance.json", artifact: "provenance", schema: SCHEMA_ONE, holds: "the manifest of every series, its source and its last fetch" },
});

/** The artifact names this build of the page reads, for a validator. */
export function artifactNames() {
  return Object.keys(ARTIFACTS);
}

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

/* The URL to fetch: the path with its content hash, from the import map in
 * index.html, which import.meta.resolve applies (src/crack/versions.py). The
 * path is relative to index.html and this module sits one directory below it.
 * An engine without import.meta.resolve, or without import maps, gets the plain
 * path, which still loads the file and is still checked by the schema guard. */
export function artifactUrl(path) {
  try {
    if (typeof import.meta.resolve === "function") return import.meta.resolve("../" + path);
  } catch (error) {
    /* fall through to the plain path */
  }
  return path;
}

/* Why this page will not read a parsed artifact, or null when it will. */
export function refusal(name, data) {
  const expected = ARTIFACTS[name];
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return "the file holds no artifact header, so this page cannot tell what it is";
  }
  if (data.artifact !== expected.artifact) {
    return "the file names itself as a different artifact, so it is not the file this page asked for";
  }
  if (data.schema_version !== expected.schema) {
    return "the file declares a schema version this page does not read, so it was written for a different version of the site than the code now running";
  }
  return null;
}

/* What to do about a refusal: the likely cause is a deploy while the page was
 * open, and one reload fetches the code and the data together. */
const REFUSAL_TODO =
  "Reload the page: the site was probably updated while this copy was open, and a reload fetches the code and the data together. " +
  "Nothing from this file is shown, rather than read with the wrong layout.";

async function fetchArtifact(name) {
  const { path } = ARTIFACTS[name];
  let response;
  try {
    response = await fetch(artifactUrl(path), { cache: "no-cache" });
  } catch (error) {
    throw failureRecord(name, "the request did not complete, so the network or the server is unreachable", String(error && error.message ? error.message : error));
  }
  if (!response.ok) {
    const statusText = response.statusText ? " " + response.statusText : "";
    throw failureRecord(name, "the server answered " + String(response.status) + statusText);
  }
  let data;
  try {
    data = await response.json();
  } catch (error) {
    throw failureRecord(name, "the file arrived but is not valid JSON", String(error && error.message ? error.message : error));
  }
  const refused = refusal(name, data);
  if (refused) throw { ...failureRecord(name, refused), todo: REFUSAL_TODO };
  return data;
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
