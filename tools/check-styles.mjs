#!/usr/bin/env node
// Fail on the CSS the design bans, read from declarations with comments removed.
//
//     node tools/check-styles.mjs              self test, then scan styles/
//
// docs/design.md Part 5 items 15 and 25 are written as greps over styles/ that
// "must return nothing". A literal grep also reads comments, so a stylesheet
// that explains why it has no shadow would fail it. This strips comments first,
// then checks the declarations, and adds the two rules Part 3 section 6 states
// that a grep cannot see. Plain node, no dependencies. In `make gate`.
//
// BANNED, Part 5 items 15 and 25, SPEC.md section 0.2
//   backdrop-filter          glassmorphism
//   box-shadow               heavy shadows, and the sticky column edge shadow
//   text-transform           all caps labels
//   any gradient             gradient washes, and the fade on a scroll container
//   mask-image               the same fade by another name
//   var(--grain-opacity)     the noise overlay
//   var(--text-dim)          fails contrast, Part 6 section C
//   var(--accent-deep)       2.14 on --bg in dark
//   var(--bg-card), var(--bg-tint)   a tinted block is the rounded card's relative
//   font-variant-caps, smcp, c2sc    small capitals are all caps
//   font-variation-settings  overrides font-weight, Part 3 section 6
//   a positive letter-spacing        S32; the display -0.025em is the one value
//   overflow-x: hidden, or overflow: hidden, on body or html   S22
//
// RULES A GREP CANNOT SEE, Part 3 section 6
//   every rule that names Fraunces or var(--ff-display) in a font or
//   font-family declaration also sets font-weight: its default is Black
//   JetBrains Mono, var(--ff-mono), appears only in rules whose selectors are
//   all in MONO_SELECTORS: table figures and axis ticks

import { readdirSync, readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");

// The only selectors allowed to set JetBrains Mono. Part 3 section 6: figures
// in table cells and tick values on axes, nothing else.
const MONO_SELECTORS = new Set([".num", ".tick"]);

const BANNED = [
  { pattern: /backdrop-filter\s*:/i, why: "backdrop-filter, glassmorphism" },
  { pattern: /box-shadow\s*:/i, why: "box-shadow" },
  { pattern: /text-transform\s*:/i, why: "text-transform, all caps" },
  { pattern: /gradient\s*\(/i, why: "a gradient" },
  { pattern: /mask-image\s*:/i, why: "mask-image, a fade" },
  { pattern: /var\(\s*--grain-opacity\s*\)/i, why: "var(--grain-opacity), a noise overlay" },
  { pattern: /var\(\s*--text-dim\s*\)/i, why: "var(--text-dim), fails contrast" },
  { pattern: /var\(\s*--accent-deep\s*\)/i, why: "var(--accent-deep), fails contrast in dark" },
  { pattern: /var\(\s*--bg-card\s*\)/i, why: "var(--bg-card), a tinted block" },
  { pattern: /var\(\s*--bg-tint\s*\)/i, why: "var(--bg-tint), a tinted block" },
  { pattern: /font-variant-caps\s*:/i, why: "font-variant-caps, small capitals" },
  { pattern: /\b(?:smcp|c2sc)\b/i, why: "a small capitals feature" },
  { pattern: /font-variation-settings\s*:/i, why: "font-variation-settings overrides font-weight" },
];

function stripComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));
}

function lineOf(source, index) {
  let line = 1;
  for (let k = 0; k < index && k < source.length; k += 1) if (source[k] === "\n") line += 1;
  return line;
}

/** Rules as { selector, body, index }, flattening @media and skipping
 *  @font-face, whose font-weight is a range and whose family is a name. */
function rules(css) {
  const out = [];
  const pattern = /([^{}]+)\{([^{}]*)\}/g;
  let match;
  while ((match = pattern.exec(css)) !== null) {
    const selector = match[1].replace(/^[\s\S]*\{/, "").trim();
    out.push({ selector, body: match[2], index: match.index });
  }
  return out;
}

export function checkCss(relative, source) {
  const findings = [];
  const css = stripComments(source);
  for (const banned of BANNED) {
    const global = new RegExp(banned.pattern.source, banned.pattern.flags.includes("g") ? banned.pattern.flags : banned.pattern.flags + "g");
    let match;
    while ((match = global.exec(css)) !== null) {
      findings.push({ file: relative, line: lineOf(css, match.index), why: banned.why });
    }
  }
  for (const rule of rules(css)) {
    const line = lineOf(css, rule.index);
    const selectors = rule.selector.split(",").map((s) => s.trim());
    if (/@font-face/.test(rule.selector)) continue;
    const spacing = /letter-spacing\s*:\s*([^;]+)/i.exec(rule.body);
    if (spacing && !/^\s*(?:-|0(?:\.0+)?(?:em|px|rem)?\s*$|normal\s*$)/.test(spacing[1])) {
      findings.push({ file: relative, line, why: "a positive letter-spacing, " + spacing[1].trim() });
    }
    const overflow = /overflow(?:-x)?\s*:\s*hidden/i.test(rule.body);
    if (overflow && selectors.some((s) => s === "body" || s === "html")) {
      findings.push({ file: relative, line, why: "overflow hidden on " + rule.selector + ", S22" });
    }
    const family = /(?:^|;)\s*font(?:-family)?\s*:\s*([^;]+)/i.exec(rule.body);
    const familyValue = family ? family[1] : "";
    if (/Fraunces|--ff-display/.test(familyValue) && !/font-weight\s*:/.test(rule.body)) {
      findings.push({ file: relative, line, why: "Fraunces without font-weight in " + rule.selector + ", its default is Black" });
    }
    if (/JetBrains Mono|--ff-mono/.test(familyValue) && !selectors.every((s) => MONO_SELECTORS.has(s))) {
      findings.push({ file: relative, line, why: "JetBrains Mono on " + rule.selector + ", only table figures and axis ticks may use it" });
    }
  }
  return findings;
}

function selfTest() {
  const cases = [
    { name: "a shadow", source: ".card { box-shadow: 0 8px 24px black; }", bad: 1 },
    { name: "an uppercase label", source: ".eyebrow { text-transform: uppercase; }", bad: 1 },
    { name: "a gradient wash", source: "body::before { background-image: linear-gradient(red, blue); }", bad: 1 },
    { name: "glass", source: ".nav { backdrop-filter: blur(12px); }", bad: 1 },
    { name: "the dim token", source: ".caption { color: var(--text-dim); }", bad: 1 },
    { name: "positive tracking", source: ".mono { letter-spacing: 0.02em; }", bad: 1 },
    { name: "body overflow", source: "body { position: relative; overflow-x: hidden; }", bad: 1 },
    { name: "Fraunces without a weight", source: "h1 { font-family: var(--ff-display); }", bad: 1 },
    { name: "mono on a label", source: ".label { font-family: var(--ff-mono); }", bad: 1 },
    { name: "small capitals", source: ".x { font-feature-settings: \"smcp\"; }", bad: 1 },
    {
      name: "allowed forms",
      source: [
        "/* no box-shadow, no text-transform: uppercase, no linear-gradient(), no var(--text-dim) */",
        "@font-face { font-family: \"Fraunces\"; src: url(\"../vendor/f.woff2\"); font-weight: 100 900; }",
        ".verdict { font-family: var(--ff-display); font-weight: 400; letter-spacing: -0.025em; }",
        ".num { font-family: var(--ff-mono); font-weight: 400; }",
        "@media (max-width: 480px) { .tick { font-family: var(--ff-mono); } }",
        ".section__inner { overflow: hidden; }",
        "--shadow-sm: 0 1px 2px rgba(0,0,0,0.4);",
      ].join("\n"),
      bad: 0,
    },
  ];
  const failures = [];
  for (const test of cases) {
    const found = checkCss("planted.css", test.source);
    const ok = found.length === test.bad;
    console.log((ok ? "  ok    " : "  FAIL  ") + test.name + (ok ? "" : ": expected " + test.bad + ", got " + JSON.stringify(found.map((f) => f.why))));
    if (!ok) failures.push(test.name);
  }
  return failures;
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  console.log("check-styles.mjs, repo " + ROOT);
  console.log("self test: planted banned CSS must be reported, allowed forms must pass");
  if (selfTest().length) {
    console.log("FAIL  the self test failed, so a scan result would mean nothing");
    process.exit(1);
  }
  const dir = path.join(ROOT, "styles");
  const files = existsSync(dir) ? readdirSync(dir).filter((name) => name.endsWith(".css")).sort() : [];
  const findings = [];
  for (const name of files) findings.push(...checkCss("styles/" + name, readFileSync(path.join(dir, name), "utf8")));
  console.log("");
  console.log("scanned " + files.length + " stylesheet(s): " + files.map((f) => "styles/" + f).join(", "));
  if (findings.length) {
    console.log("FAIL  CSS that docs/design.md Part 5 bans");
    for (const f of findings) console.log("      " + f.file + ":" + f.line + "  " + f.why);
    process.exit(1);
  }
  console.log("PASS  no banned property, token, tracking or overflow; Fraunces always weighted; mono only on figures and ticks");
}
