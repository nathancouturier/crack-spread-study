#!/usr/bin/env node
// Fail on any path that would break the subpath deploy or reach off the site.
//
//     node tools/check-paths.mjs              self test, then scan
//
// The site is served from https://nathancouturier.github.io/crack-spread-study/,
// a subpath. SPEC.md section 0.1: "Every path relative. Verify it from the
// subpath, it is the most common way this deployment breaks." A root relative
// path, /styles/tokens.css, resolves to the domain root on Pages, which is the
// portfolio's repository and not this one, and it works on a plain local server
// run from the repository root, so nobody notices until it is live.
// scripts/serve.py reproduces the subpath to catch it at runtime; this catches
// it before anything runs. Plain node, no dependencies. In `make gate`.
//
// WHAT FAILS
//   a root relative path       starts with a single slash: /styles/x.css
//   a protocol relative URL    starts with two slashes: //cdn.example/x.js
//   an absolute URL            http:, https:, or any other scheme except the
//                              allowed ones below, because SPEC.md section 0.1
//                              forbids CDN links and the page makes no external
//                              request at all
//
// WHAT PASSES
//   relative paths             styles/tokens.css, ../vendor/x.woff2, ./format.js
//   fragments and hash routes  #view-title, #/now
//   data: URIs                 the empty favicon, data:,
//
// WHERE IT LOOKS
//   index.html          src, href, action, poster, srcset and data attributes on
//                       every tag; url() inside style attributes and <style>;
//                       every string in inline scripts
//   styles/*.css        every url() and @import, comments stripped
//   src/**/*.js         import and export specifiers, dynamic import(), and
//                       every string literal that looks like a path or a URL,
//                       comments stripped (src/crack/ is the Python package)
//
// A comment may name a URL: the documentation cites sources. Only code, markup
// and declarations are read.

import { readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { lex } from "./check-literals.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");

const ALLOWED_SCHEMES = new Set(["data"]);

/** Why a reference is bad, or null if it is fine. */
export function verdictFor(reference) {
  const value = reference.trim();
  if (value === "") return null;
  if (value.startsWith("//")) return "protocol relative URL, leaves the site";
  if (value.startsWith("/")) return "root relative path, breaks under the /crack-spread-study/ subpath";
  const scheme = /^([a-zA-Z][a-zA-Z0-9+.-]*):/.exec(value);
  if (scheme && !ALLOWED_SCHEMES.has(scheme[1].toLowerCase())) return "absolute URL with the scheme " + scheme[1] + ", no external requests and no CDN";
  return null;
}

function lineOf(source, index) {
  let line = 1;
  for (let k = 0; k < index && k < source.length; k += 1) if (source[k] === "\n") line += 1;
  return line;
}

function stripCssComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));
}

/** Every url() and @import target in a stylesheet. */
export function checkCss(relative, css, offset = 0, full = css) {
  const out = [];
  const clean = stripCssComments(css);
  const urlPattern = /url\(\s*(?:"([^"]*)"|'([^']*)'|([^)\s]*))\s*\)/gi;
  let match;
  while ((match = urlPattern.exec(clean)) !== null) {
    const value = match[1] ?? match[2] ?? match[3] ?? "";
    const why = verdictFor(value);
    if (why) out.push({ file: relative, line: lineOf(full, offset + match.index), value, why });
  }
  const importPattern = /@import\s+(?:"([^"]*)"|'([^']*)')/gi;
  while ((match = importPattern.exec(clean)) !== null) {
    const value = match[1] ?? match[2];
    const why = verdictFor(value);
    if (why) out.push({ file: relative, line: lineOf(full, offset + match.index), value, why });
  }
  return out;
}

/* A string in a script is read as a path when it looks like one: it starts
 * with a slash followed by a path character, or with two slashes, or with a
 * scheme. "/" alone, a separator for split(), and "#/" are not paths. */
function looksLikeReference(text) {
  return /^\/\/./.test(text) || /^\/[\w.~%-]/.test(text) || /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(text);
}

/** Import specifiers and path like strings in a script. */
export function checkScript(relative, source, offset = 0, full = source) {
  const out = [];
  for (const piece of lex(source).strings) {
    if (!looksLikeReference(piece.text)) continue;
    const why = verdictFor(piece.text);
    if (why) out.push({ file: relative, line: lineOf(full, offset + piece.index), value: piece.text, why });
  }
  return out;
}

/** Attributes, style and inline scripts of an HTML page. */
export function checkHtml(relative, html) {
  const out = [];
  const withoutComments = html.replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, " "));
  let match;
  const scriptPattern = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
  while ((match = scriptPattern.exec(withoutComments)) !== null) {
    const bodyIndex = match.index + match[0].indexOf(">") + 1;
    out.push(...checkScript(relative, match[2], bodyIndex, html));
  }
  const stylePattern = /<style\b[^>]*>([\s\S]*?)<\/style>/gi;
  while ((match = stylePattern.exec(withoutComments)) !== null) {
    const bodyIndex = match.index + match[0].indexOf(">") + 1;
    out.push(...checkCss(relative, match[1], bodyIndex, html));
  }
  const markup = withoutComments
    .replace(/<script\b([^>]*)>[\s\S]*?<\/script>/gi, (m, attrs) => "<script" + attrs + ">" + " ".repeat(Math.max(0, m.length - attrs.length - "<script></script>".length)) + "</script>")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, (m) => m.replace(/[^\n]/g, " "));
  const tagPattern = /<[a-zA-Z][\w-]*((?:\s+[^\s=>]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*\/?>/g;
  while ((match = tagPattern.exec(markup)) !== null) {
    const attrPattern = /([^\s=>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g;
    let attr;
    while ((attr = attrPattern.exec(match[1])) !== null) {
      const name = attr[1].toLowerCase();
      const value = attr[2] ?? attr[3] ?? attr[4] ?? "";
      const line = lineOf(html, match.index);
      if (["src", "href", "action", "poster", "data", "formaction", "xlink:href"].includes(name)) {
        const why = verdictFor(value);
        if (why) out.push({ file: relative, line, value, why });
      } else if (name === "srcset") {
        for (const candidate of value.split(",")) {
          const url = candidate.trim().split(/\s+/)[0] || "";
          const why = verdictFor(url);
          if (why) out.push({ file: relative, line, value: url, why });
        }
      } else if (name === "style") {
        for (const hit of checkCss(relative, value)) out.push({ ...hit, line });
      }
    }
  }
  return out;
}

// ------------------------------------------------------------ self test ---

function selfTest() {
  const cases = [
    { name: "a root relative stylesheet", kind: "html", source: '<link rel="stylesheet" href="/styles/tokens.css">', bad: 1 },
    { name: "a root relative module", kind: "html", source: '<script type="module" src="/src/ui.js"></script>', bad: 1 },
    { name: "a CDN script", kind: "html", source: '<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>', bad: 1 },
    { name: "a protocol relative font", kind: "css", source: '@font-face { src: url(//fonts.gstatic.com/x.woff2); }', bad: 1 },
    { name: "a root relative font", kind: "css", source: '@font-face { src: url("/vendor/figtree/figtree.v2.002.latin.woff2"); }', bad: 1 },
    { name: "a root relative import in css", kind: "css", source: '@import "/styles/layout.css";', bad: 1 },
    { name: "a root relative fetch", kind: "js", source: 'fetch("/data/now.json");', bad: 1 },
    { name: "a root relative module import", kind: "js", source: 'import { el } from "/src/dom.js";', bad: 1 },
    { name: "an external fetch in a template", kind: "js", source: "fetch(`https://example.org/${name}.json`);", bad: 1 },
    { name: "a root relative url in a style attribute", kind: "html", source: '<div style="background: url(/assets/x.png)"></div>', bad: 1 },
    { name: "a root relative path in an inline script", kind: "html", source: '<script>fetch("/data/now.json")</script>', bad: 1 },
    {
      name: "relative forms pass",
      kind: "html",
      source: [
        '<link rel="icon" href="data:,">',
        '<link rel="stylesheet" href="styles/tokens.css">',
        '<a href="#/now">Now</a><a href="#view-title">skip</a>',
        '<script type="module" src="src/ui.js"></script>',
        "<!-- https://nathancouturier.github.io/crack-spread-study/ in a comment -->",
        '<script>var parts = hash.split("/"); var route = "#/";</script>',
      ].join("\n"),
      bad: 0,
    },
    { name: "relative css passes", kind: "css", source: '/* url(/in/a/comment) */ @font-face { src: url("../vendor/fraunces/fraunces.v1.000.latin.woff2") format("woff2"); }', bad: 0 },
    { name: "relative js passes", kind: "js", source: 'import * as r from "./router.js"; fetch("data/now.json"); // fetch("/data/x.json")\nconst sep = "/";', bad: 0 },
  ];
  const failures = [];
  for (const test of cases) {
    const found = test.kind === "html" ? checkHtml("planted.html", test.source) : test.kind === "css" ? checkCss("planted.css", test.source) : checkScript("planted.js", test.source);
    const ok = found.length === test.bad;
    console.log((ok ? "  ok    " : "  FAIL  ") + test.name + (ok ? "" : ": expected " + test.bad + " finding(s), got " + found.length + " " + JSON.stringify(found.map((f) => f.value))));
    if (!ok) failures.push(test.name);
  }
  return failures;
}

// ----------------------------------------------------------------- main ---

function walk(directory, extensions, skip) {
  const out = [];
  const go = (relative) => {
    const full = path.join(ROOT, relative);
    if (!existsSync(full)) return;
    for (const name of readdirSync(full)) {
      const rel = relative + "/" + name;
      if (skip.has(rel)) continue;
      const info = statSync(path.join(ROOT, rel));
      if (info.isDirectory()) go(rel);
      else if (extensions.some((ext) => name.endsWith(ext))) out.push(rel);
    }
  };
  go(directory);
  return out.sort();
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  console.log("check-paths.mjs, repo " + ROOT);
  console.log("self test: planted root relative and external paths must be reported, relative ones must pass");
  const testFailures = selfTest();
  if (testFailures.length) {
    console.log("FAIL  the self test failed, so a scan result would mean nothing");
    process.exit(1);
  }
  const findings = [];
  const scanned = [];
  if (existsSync(path.join(ROOT, "index.html"))) {
    findings.push(...checkHtml("index.html", readFileSync(path.join(ROOT, "index.html"), "utf8")));
    scanned.push("index.html");
  }
  for (const rel of walk("styles", [".css"], new Set())) {
    findings.push(...checkCss(rel, readFileSync(path.join(ROOT, rel), "utf8")));
    scanned.push(rel);
  }
  for (const rel of walk("src", [".js", ".mjs"], new Set(["src/crack"]))) {
    findings.push(...checkScript(rel, readFileSync(path.join(ROOT, rel), "utf8")));
    scanned.push(rel);
  }
  console.log("");
  console.log("scanned " + scanned.length + " file(s): " + scanned.join(", "));
  if (findings.length) {
    console.log("FAIL  a path that breaks under /crack-spread-study/ or leaves the site");
    for (const f of findings) console.log("      " + f.file + ":" + f.line + "  " + f.value + "  " + f.why);
    process.exit(1);
  }
  console.log("PASS  every src, href, url(), import and fetch path is relative, and nothing is fetched from another host");
}
