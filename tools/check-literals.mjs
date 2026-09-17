#!/usr/bin/env node
// Fail if the frontend holds a number that did not come from a JSON artifact.
//
//     node tools/check-literals.mjs              self test, then scan
//     node tools/check-literals.mjs --verbose    also list every allowed literal
//
// SPEC.md section 2 rule 2: "Every number in the browser comes from a JSON
// artifact. No numeric literals in the frontend except unit constants. Verify by
// grepping." A grep for digits cannot tell a market value from a list index, or
// code from a comment, so this reads the source with a small JavaScript lexer
// instead and applies an explicit allowlist. Plain node, no dependencies. In
// `make gate`.
//
// WHAT IS SCANNED
//   src/**/*.js except src/crack/, which is the Python package
//   index.html: every inline script as JavaScript; the text between tags; and
//   every attribute value except href and src, which are paths and are guarded
//   by tools/check-paths.mjs
//
// WHAT COUNTS AS A LITERAL
//   In code, every numeric token: 38.05, 7, 1e-9, 0x1F, 10n.
//   In a string or template literal, every run of digits that stands alone,
//   because "kept 38.05 $/bbl" in a string is as much a hardcoded market value
//   as 38.05 in code. A run touching a letter, #, backslash or another digit on
//   its left is not standing alone: "v2", "#17181C" and "\u2212" are a version,
//   a colour and an escape. Comments are not scanned: a number in a comment
//   reaches no reader of the page.
//   Regex literal bodies are not scanned. A character class such as [1-9] is a
//   pattern, not a value; a market value hidden in a regex would still need a
//   literal elsewhere to reach the page.
//
// THE ALLOWLIST, and nothing else passes
//   1  the values 0 and 1 in code: index arithmetic, a length boundary, a step,
//      a count increment. Not 2, not 10: anything else has to be declared.
//   2  UNIT_CONSTANTS: a name and its exact value, per file, allowed only in the
//      declaration `const NAME = value`. Changing the value fails, and so does
//      using the same figure anywhere else in the file.
//   3  DECLARED: an exact source snippet containing a literal, per file, with
//      the number of times it may occur and the reason. Layout dimensions and
//      format facts live here, one per entry.
//   4  STRING_VOCABULARY: exact string literals that an API defines, such as
//      Intl's "2-digit". Exact match only.
//   5  CITATIONS: in a string, a number directly after "SPEC.md section",
//      "section", "sections", "rule", "Gate", "finding", "point", "item",
//      "question" or "Part", and the second end of "sections 4.2 to 4.5". These
//      cite a document and are never drawn as a figure.
//   6  HTML_ATTRIBUTES: an attribute name and exact value, for markup such as
//      tabindex="-1" and the viewport meta.
//   7  LAYOUT_CONSTANTS: a name and its exact value, per file, allowed only as
//      the property `NAME: value` alone on its line, the form of a frozen
//      geometry block such as GEOMETRY in src/charts.js. A drawing surface
//      decision (a height, a padding, a dot radius), never an observation.
//      Changing the value fails, and so does the same figure anywhere else.
//   8  CONTENT_HASH: in index.html only, a string that is exactly a relative
//      path followed by ?v= and twelve lower case hex digits, the form
//      src/crack/versions.py writes into the import map. A hash is an address,
//      not a figure, and one made of digits alone would otherwise fail by
//      chance. Any other digit in the import map is still reported.
//
// SELF TEST. Before scanning, the tool plants market values in synthetic files
// and asserts it reports each one, and asserts that the allowed forms pass. If
// the self test fails, the scan result means nothing and the tool exits 1.

import { readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");

// ------------------------------------------------------------ allowlist ---

// Rule 1. Index arithmetic.
const ALWAYS_ALLOWED_VALUES = new Set([0, 1]);

// Rule 2. Unit constants, by file. SPEC.md section 4.1 and src/crack/config.py.
const UNIT_CONSTANTS = {
  "src/engine.js": [
    // ICE Low Sulphur Gasoil futures, contract conversion, bbl per tonne.
    { name: "BBL_PER_T_GASOIL", value: "7.45" },
    // ICE Eurobob Oxy crack contract conversion, bbl per tonne.
    { name: "BBL_PER_T_GASOLINE", value: "8.33" },
    // MMBtu per MWh, a unit definition, SPEC.md section 4.1.
    { name: "MMBTU_PER_MWH", value: "3.412142" },
  ],
};

// Rule 7. Layout constants, by file, as `NAME: value` in a frozen block.
// docs/design.md Part 3 sections 2 to 5 give the sizes; each is in CSS pixels
// unless it says otherwise.
const LAYOUT_CONSTANTS = {
  "src/charts.js": [
    { name: "PANEL_HEIGHT", value: "220", why: "seasonal plot height, Part 3 section 3" },
    { name: "RAIL_HEIGHT", value: "14", why: "a rail under the axis, Part 3 section 3" },
    { name: "PAD_TOP", value: "28", why: "room for the unit title" },
    { name: "PAD_LEFT", value: "44", why: "room for tick values" },
    { name: "PAD_RIGHT", value: "84", why: "room for end labels" },
    { name: "AXIS_GAP", value: "16", why: "plot edge to x tick values" },
    { name: "AXIS_BELOW", value: "10", why: "x tick values to the first rail" },
    { name: "TICK_LENGTH", value: "4", why: "an axis tick" },
    { name: "LABEL_GAP", value: "8", why: "mark to label, Part 3 section 2" },
    { name: "LABEL_SPACING", value: "14", why: "end labels closer than this are spread" },
    { name: "DOT_RADIUS", value: "4", why: "the accent dot, Part 3 section 2" },
    { name: "RING_WIDTH", value: "2", why: "the --bg ring, S25" },
    { name: "ISOLATED_RADIUS", value: "1.5", why: "a value with gaps on both sides, Part 3 section 2" },
    { name: "SQUARE", value: "5", why: "a printed week, Part 3 section 2" },
    { name: "HATCH_PITCH", value: "4", why: "the least defended hatch, Part 3 section 2" },
    { name: "HATCH_ANGLE", value: "45", why: "the hatch angle in degrees" },
    { name: "HATCH_MIN_WIDTH", value: "6", why: "the hatch at any zoom" },
    { name: "BRACKET_TICK", value: "4", why: "a bracket's end tick" },
    { name: "Y_TICKS", value: "5", why: "4 to 6 ticks, Part 3 section 2" },
    { name: "X_TICKS", value: "5", why: "about five week labels" },
    { name: "HALF", value: "0.5", why: "halving, for centring" },
    { name: "COORD_DECIMALS", value: "2", why: "places in a pixel coordinate" },
    { name: "BAR_THICKNESS", value: "14", why: "a waterfall bar in a 32px row" },
    { name: "SMALL_STEP", value: "4", why: "steps narrower than this are circles, Part 3 section 4" },
    { name: "SMALL_RADIUS", value: "2.5", why: "the 5px circle, Part 3 section 4" },
    { name: "OUTLINE_INSET", value: "0.75", why: "half the 1.5px outline" },
    { name: "STRIP_ROW", value: "28", why: "an interval strip row, Part 3 section 5" },
    { name: "STRIP_END_TICK", value: "6", why: "interval end ticks, Part 3 section 5" },
    { name: "STRIP_PAD", value: "8", why: "space under the strip figure" },
    { name: "STRIP_LABEL", value: "16", why: "the model label above a narrow strip" },
    { name: "TIME_HEIGHT", value: "360", why: "a History time plot, Part 3 section 2" },
    { name: "TIME_HEIGHT_NARROW", value: "240", why: "a History time plot below 768px, Part 3 section 2" },
    { name: "NARROW_WIDTH", value: "768", why: "the width below which a time plot is shorter" },
    { name: "WEDGE_HEIGHT", value: "120", why: "the extra gas plot under the margin, Part 8.1 H2" },
    { name: "TIME_PAD_RIGHT", value: "64", why: "room for a two line end label" },
    { name: "YEAR_SPACING", value: "48", why: "year labels at least this far apart, Part 3 section 2" },
    { name: "PROFILE_HEIGHT", value: "240", why: "the monthly seasonal profile plot, Part 8.1 H8" },
  ],
};

// Rule 3. Declared snippets, by file. `count` is exact: a snippet counts once
// per literal inside it.
const DECLARED = {
  "src/charts.js": [
    // The mantissas of decimal notation, a fact about how numbers are written
    // and not about the market. Three literals: 2, 5 and 10.
    { snippet: "Object.freeze([1, 2, 5, 10])", count: 3, why: "the 1, 2, 5, 10 tick ladder" },
    { snippet: "Math.pow(10, Math.floor(Math.log10(value)))", count: 1, why: "the power of ten under a tick step" },
  ],
  "src/dom.js": [
    // How many cut off columns a table caption names one by one before it says
    // "the columns from X on". A wording decision about a list, not a value.
    { snippet: "const MOST_NAMED = 4;", count: 1, why: "columns named one by one in a caption, Part 7 C13" },
  ],
  "src/model.js": [
    // A share of one written as a percent, for the sentence saying how much of
    // the barrel the model margin covers. A unit conversion, docs/design.md Part 8.2.
    { snippet: "const PERCENT_PER_ONE = 100;", count: 1, why: "fraction to percent" },
  ],
  "src/engine.js": [
    // An ISO calendar date, YYYY-MM-DD, is ten characters. A format fact used
    // to reject a malformed date before any arithmetic, not a market value.
    { snippet: "date.length !== 10", count: 2, why: "ISO date string length" },
    // A share of one written as a percent. A unit conversion, the same kind of
    // constant as MMBTU_PER_MWH: percentile_rank returns 0 to 100.
    { snippet: "(100 * atOrBelow)", count: 1, why: "fraction to percent" },
  ],
};

// Rule 4. Strings an API defines.
const STRING_VOCABULARY = new Set([
  "2-digit", // Intl.DateTimeFormat option value for hour and minute
  "-1", // the tabindex value that makes an element focusable by script only
]);

// Rule 5. Citation words that may precede a number inside a string.
const CITATION_BEFORE = /(?:SPEC\.md section|sections?|rule|Gate|finding|point|item|question|Part)\s+(?:\d+(?:\.\d+)*\s+(?:to|and)\s+)?$/;

// Rule 6. Attribute values in index.html, exact.
const HTML_ATTRIBUTES = [
  { attr: "charset", value: "utf-8", why: "the character encoding" },
  { attr: "content", value: "width=device-width, initial-scale=1", why: "the viewport meta" },
  { attr: "tabindex", value: "-1", why: "focusable by script only" },
];

// Rule 8. A versioned path in the import map, exact form, index.html only.
const CONTENT_HASH = /^\.\/(?:src|data|styles)\/[\w.-]+\?v=[0-9a-f]{12}$/;

// ---------------------------------------------------------------- lexer ---

const REGEX_AFTER_WORDS = new Set(["return", "typeof", "case", "in", "of", "delete", "void", "throw", "new", "else", "do", "instanceof", "yield", "await"]);

/** Lex JavaScript into the pieces this check cares about: numeric tokens in
 *  code, and string and template text. Comments and regex bodies are skipped.
 *  Returns { numbers: [{ text, index }], strings: [{ text, index, raw }] }. */
export function lex(source) {
  const numbers = [];
  const strings = [];
  let i = 0;
  const n = source.length;
  let lastSignificant = ""; // the previous token class: "word", "num", "close", "punct"
  let lastWord = "";
  const templateStack = []; // brace depth at which each open template resumes

  let braceDepth = 0;

  const readTemplate = (start) => {
    // i points just after a backtick or a closing brace of ${ }
    let text = "";
    let textStart = i;
    while (i < n) {
      const c = source[i];
      if (c === "\\") { text += source.slice(i, i + 2); i += 2; continue; }
      if (c === "`") { strings.push({ text, index: textStart, raw: text }); i += 1; return "closed"; }
      if (c === "$" && source[i + 1] === "{") {
        strings.push({ text, index: textStart, raw: text });
        i += 2;
        templateStack.push(braceDepth);
        braceDepth += 1;
        return "expression";
      }
      text += c;
      i += 1;
    }
    strings.push({ text, index: textStart, raw: text });
    return "closed";
  };

  while (i < n) {
    const c = source[i];
    const next = source[i + 1];
    if (c === "/" && next === "/") { while (i < n && source[i] !== "\n") i += 1; continue; }
    if (c === "/" && next === "*") { const end = source.indexOf("*/", i + 2); i = end < 0 ? n : end + 2; continue; }
    if (/\s/.test(c)) { i += 1; continue; }
    if (c === "'" || c === '"') {
      const quote = c; const start = i; i += 1; let text = "";
      while (i < n && source[i] !== quote) {
        if (source[i] === "\\") { text += source.slice(i, i + 2); i += 2; continue; }
        if (source[i] === "\n") break;
        text += source[i]; i += 1;
      }
      i += 1;
      strings.push({ text, index: start, raw: text });
      lastSignificant = "close";
      continue;
    }
    if (c === "`") {
      i += 1;
      readTemplate(i);
      lastSignificant = "close";
      continue;
    }
    if (c === "{") { braceDepth += 1; i += 1; lastSignificant = "punct"; continue; }
    if (c === "}") {
      braceDepth -= 1;
      if (templateStack.length && templateStack[templateStack.length - 1] === braceDepth) {
        templateStack.pop();
        i += 1;
        readTemplate(i);
        lastSignificant = "close";
        continue;
      }
      i += 1; lastSignificant = "close"; continue;
    }
    if (c === "/") {
      const regexAllowed = lastSignificant === "" || lastSignificant === "punct" || (lastSignificant === "word" && REGEX_AFTER_WORDS.has(lastWord));
      if (regexAllowed) {
        i += 1; let inClass = false;
        while (i < n) {
          const r = source[i];
          if (r === "\\") { i += 2; continue; }
          if (r === "[") inClass = true;
          else if (r === "]") inClass = false;
          else if (r === "/" && !inClass) break;
          else if (r === "\n") break;
          i += 1;
        }
        i += 1;
        while (i < n && /[a-z]/i.test(source[i])) i += 1;
        lastSignificant = "close";
        continue;
      }
      i += 1; lastSignificant = "punct"; continue;
    }
    const numberMatch = /^(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|(?:\d[\d_]*(?:\.[\d_]*)?|\.\d[\d_]*)(?:[eE][+-]?\d+)?)n?/.exec(source.slice(i, i + 64));
    if (numberMatch && (/\d/.test(c) || (c === "." && /\d/.test(next || "")))) {
      numbers.push({ text: numberMatch[0], index: i });
      i += numberMatch[0].length;
      lastSignificant = "num";
      continue;
    }
    const wordMatch = /^[A-Za-z_$][\w$]*/.exec(source.slice(i, i + 256));
    if (wordMatch) {
      lastWord = wordMatch[0];
      lastSignificant = "word";
      i += wordMatch[0].length;
      continue;
    }
    lastSignificant = c === ")" || c === "]" ? "close" : "punct";
    i += 1;
  }
  return { numbers, strings };
}

function lineOf(source, index) {
  let line = 1;
  for (let k = 0; k < index && k < source.length; k += 1) if (source[k] === "\n") line += 1;
  return line;
}

function lineText(source, index) {
  const start = source.lastIndexOf("\n", index - 1) + 1;
  const end = source.indexOf("\n", index);
  return source.slice(start, end < 0 ? source.length : end);
}

/** Digit runs that stand alone inside a piece of text, with their offsets. */
function standaloneNumbers(text) {
  const out = [];
  const pattern = /(?<![\w#\\.])\d+(?:[.,]\d+)*(?![\w])/g;
  let match;
  while ((match = pattern.exec(text)) !== null) out.push({ text: match[0], offset: match.index });
  return out;
}

// ------------------------------------------------------------- checking ---

function numericValue(text) {
  const clean = text.replace(/_/g, "").replace(/n$/, "");
  return Number(clean);
}

/** Check one JavaScript source. Returns { violations, allowed }. */
export function checkScript(relative, source, baseIndex = 0, fullSource = source) {
  const violations = [];
  const allowed = [];
  const { numbers, strings } = lex(source);
  const units = UNIT_CONSTANTS[relative] || [];
  const declared = (DECLARED[relative] || []).map((entry) => ({ ...entry, seen: 0 }));

  for (const token of numbers) {
    const at = baseIndex + token.index;
    const where = { file: relative, line: lineOf(fullSource, at), text: lineText(fullSource, at).trim() };
    const value = numericValue(token.text);
    if (ALWAYS_ALLOWED_VALUES.has(value) && /^[01]$/.test(token.text)) {
      allowed.push({ ...where, literal: token.text, rule: "index arithmetic" });
      continue;
    }
    const before = source.slice(0, token.index);
    const unit = units.find((u) => new RegExp("(?:export\\s+)?const\\s+" + u.name + "\\s*=\\s*$").test(before.slice(-128)) && u.value === token.text);
    if (unit) {
      allowed.push({ ...where, literal: token.text, rule: "unit constant " + unit.name });
      continue;
    }
    const lineStart = source.lastIndexOf("\n", token.index - 1) + 1;
    const lineEnd = source.indexOf("\n", token.index);
    const localLine = source.slice(lineStart, lineEnd < 0 ? source.length : lineEnd);
    const layout = (LAYOUT_CONSTANTS[relative] || []).find((u) =>
      u.value === token.text &&
      new RegExp("^\\s*" + u.name + "\\s*:\\s*$").test(source.slice(lineStart, token.index)) &&
      /^\s*,?\s*$/.test(source.slice(token.index + token.text.length, lineEnd < 0 ? source.length : lineEnd)));
    if (layout) {
      allowed.push({ ...where, literal: token.text, rule: "layout constant " + layout.name });
      continue;
    }
    const entry = declared.find((d) => {
      const pos = localLine.indexOf(d.snippet);
      if (pos < 0) return false;
      const col = token.index - lineStart;
      return col >= pos && col < pos + d.snippet.length;
    });
    if (entry) {
      entry.seen += 1;
      allowed.push({ ...where, literal: token.text, rule: "declared: " + entry.why });
      continue;
    }
    violations.push({ ...where, literal: token.text, kind: "numeric literal in code" });
  }

  for (const entry of declared) {
    if (entry.seen !== entry.count) {
      violations.push({ file: relative, line: 0, text: entry.snippet, literal: entry.snippet, kind: "declared snippet expected " + entry.count + " time(s), found " + entry.seen + "; update the allowlist deliberately" });
    }
  }

  for (const piece of strings) {
    if (relative === "index.html" && CONTENT_HASH.test(piece.text)) {
      if (/\d/.test(piece.text)) allowed.push({ file: relative, line: lineOf(fullSource, baseIndex + piece.index), literal: JSON.stringify(piece.text), rule: "content hash", text: "" });
      continue;
    }
    if (STRING_VOCABULARY.has(piece.text)) {
      if (/\d/.test(piece.text)) allowed.push({ file: relative, line: lineOf(fullSource, baseIndex + piece.index), literal: JSON.stringify(piece.text), rule: "API vocabulary", text: "" });
      continue;
    }
    for (const hit of standaloneNumbers(piece.text)) {
      const at = baseIndex + piece.index;
      const where = { file: relative, line: lineOf(fullSource, at), text: lineText(fullSource, at).trim() };
      if (CITATION_BEFORE.test(piece.text.slice(0, hit.offset))) {
        allowed.push({ ...where, literal: hit.text, rule: "citation" });
        continue;
      }
      violations.push({ ...where, literal: hit.text, kind: "number inside a string" });
    }
  }
  return { violations, allowed };
}

/** Check index.html: inline scripts, text, attributes. */
export function checkHtml(relative, source) {
  const violations = [];
  const allowed = [];
  // Inline scripts, scanned as JavaScript, then blanked so the text scan below
  // does not read them again.
  let rest = source;
  const scriptPattern = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
  let match;
  while ((match = scriptPattern.exec(source)) !== null) {
    if (/\bsrc\s*=/.test(match[1])) continue;
    const bodyIndex = match.index + match[0].indexOf(">") + 1;
    const result = checkScript(relative, match[2], bodyIndex, source);
    violations.push(...result.violations);
    allowed.push(...result.allowed);
  }
  rest = rest.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, (m) => m.replace(/[^\n]/g, " "));
  rest = rest.replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, " "));
  rest = rest.replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, (m) => m.replace(/[^\n]/g, " "));
  // Character references such as &#x263E; are an encoding, not a figure.
  rest = rest.replace(/&#x?[0-9a-fA-F]+;/g, (m) => " ".repeat(m.length));

  // Attributes.
  // Opening tags carry attributes; closing tags and the doctype only bound text.
  rest = rest.replace(/<\/[a-zA-Z][\w-]*\s*>|<![^>]*>/g, (m) => "<" + " ".repeat(m.length - 2) + ">");
  const tagPattern = /<([a-zA-Z][\w-]*)((?:\s+[^\s=>]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*\/?>/g;
  const tagRanges = [];
  while ((match = tagPattern.exec(rest)) !== null) {
    tagRanges.push([match.index, match.index + match[0].length]);
    const attrPattern = /([^\s=>]+)(?:\s*=\s*("([^"]*)"|'([^']*)'|([^\s>]+)))?/g;
    let attr;
    const attrsText = match[2];
    const attrsStart = match.index + match[0].indexOf(attrsText);
    while ((attr = attrPattern.exec(attrsText)) !== null) {
      const name = attr[1].toLowerCase();
      const value = attr[3] ?? attr[4] ?? attr[5] ?? "";
      if (name === "href" || name === "src") continue;
      const hits = standaloneNumbers(value);
      if (!hits.length) continue;
      const at = attrsStart + attr.index;
      const where = { file: relative, line: lineOf(source, at), text: lineText(source, at).trim() };
      const declared = HTML_ATTRIBUTES.find((d) => d.attr === name && d.value === value);
      if (declared) {
        allowed.push({ ...where, literal: name + '="' + value + '"', rule: "attribute: " + declared.why });
        continue;
      }
      for (const hit of hits) violations.push({ ...where, literal: hit.text, kind: "number in the attribute " + name });
    }
  }
  // Text between tags.
  let cursor = 0;
  for (const [start, end] of tagRanges) {
    const text = rest.slice(cursor, start);
    for (const hit of standaloneNumbers(text)) {
      const at = cursor + hit.offset;
      violations.push({ file: relative, line: lineOf(source, at), text: lineText(source, at).trim(), literal: hit.text, kind: "number in page text" });
    }
    cursor = end;
  }
  const tail = rest.slice(cursor);
  for (const hit of standaloneNumbers(tail)) {
    const at = cursor + hit.offset;
    violations.push({ file: relative, line: lineOf(source, at), text: lineText(source, at).trim(), literal: hit.text, kind: "number in page text" });
  }
  return { violations, allowed };
}

// ------------------------------------------------------------ self test ---

function selfTest() {
  const ENGINE_DECLARED = (DECLARED["src/engine.js"] || [])
    .map((entry) => (entry.snippet + ";\n").repeat(entry.count))
    .join("");
  // The charts cases carry the declared snippets once each, as the real
  // charts.js does, so only the planted value can be reported.
  const CHARTS_DECLARED = (DECLARED["src/charts.js"] || []).map((entry) => entry.snippet + ";\n").join("");
  const cases = [
    { name: "a market value in code", file: "src/planted.js", kind: "js", source: "const margin = 38.05;\n", expect: ["38.05"] },
    { name: "a market value in a string", file: "src/planted.js", kind: "js", source: 'el("p", { text: "a refiner kept 38.05 $/bbl" });\n', expect: ["38.05"] },
    { name: "a market value in a template expression", file: "src/planted.js", kind: "js", source: "const s = `kept ${value + 38} and ${`${91.14}`}`;\n", expect: ["38", "91.14"] },
    { name: "a market value in template text", file: "src/planted.js", kind: "js", source: "const s = `kept 38.05 ${unit}`;\n", expect: ["38.05"] },
    { name: "a literal that is not 0 or 1", file: "src/planted.js", kind: "js", source: "const month = iso.slice(0, 7);\n", expect: ["7"] },
    { name: "a negative market value", file: "src/planted.js", kind: "js", source: "const residual = -3.68;\n", expect: ["3.68"] },
    // The two engine cases carry the declared snippets the real engine.js has,
    // at their declared counts, so only the planted value can be reported.
    { name: "a unit constant with a moved value", file: "src/engine.js", kind: "js", source: ENGINE_DECLARED + "export const BBL_PER_T_GASOIL = 7.46;\n", expect: ["7.46"] },
    { name: "a unit constant used outside its declaration", file: "src/engine.js", kind: "js", source: ENGINE_DECLARED + "export const BBL_PER_T_GASOIL = 7.45;\nconst x = price / 7.45;\n", expect: ["7.45"] },
    { name: "a declared snippet appearing more often than declared", file: "src/engine.js", kind: "js", source: ENGINE_DECLARED + "if (date.length !== 10) {}\n", expect: ["date.length !== 10"] },
    { name: "a layout constant with a moved value", file: "src/charts.js", kind: "js", source: CHARTS_DECLARED + "const GEOMETRY = Object.freeze({\n  PANEL_HEIGHT: 221,\n});\n", expect: ["221"] },
    { name: "a layout constant's figure used elsewhere", file: "src/charts.js", kind: "js", source: CHARTS_DECLARED + "const GEOMETRY = Object.freeze({\n  PANEL_HEIGHT: 220,\n});\nconst h = 220;\n", expect: ["220"] },
    { name: "a layout constant's name beside a market value", file: "src/charts.js", kind: "js", source: CHARTS_DECLARED + "const x = { PANEL_HEIGHT: 220 + 38.05 };\n", expect: ["220", "38.05"] },
    { name: "a value in page text", file: "index.html", kind: "html", source: "<p>Margin 38.05 $/bbl</p>\n", expect: ["38.05"] },
    { name: "a value in an inline script", file: "index.html", kind: "html", source: "<script>var m = 38.05;</script>\n", expect: ["38.05"] },
    { name: "a value in a data attribute", file: "index.html", kind: "html", source: '<span data-value="38.05">x</span>\n', expect: ["38.05"] },
    { name: "a value hidden in the import map", file: "index.html", kind: "html", source: '<script type="importmap">{"imports": {"./src/ui.js": "./src/ui.js?v=38.05", "./data/now.json": "./data/now.json?v=123456789012 91"}}</script>\n', expect: ["38.05", "123456789012", "91"] },
    { name: "a content hash outside index.html is not a hash", file: "src/planted.js", kind: "js", source: 'const url = "./src/ui.js?v=123456789012";\n', expect: ["123456789012"] },
    {
      name: "allowed forms",
      file: "src/planted.js",
      kind: "js",
      source: [
        "// 38.05 in a comment reaches no reader",
        "/* nor 91.14 in a block comment */",
        "const last = list[list.length - 1];",
        "for (let i = 0; i < n; i += 1) {}",
        'const minus = "\\u2212"; const ink = "#17181C"; const face = "figtree.v2.002";',
        'const opts = { hour: "2-digit" }; const focusable = { tabindex: "-1" };',
        "const zero = /[1-9]/.test(body);",
        'throw new Error("SPEC.md section 4.2 and sections 4.2 to 4.5, Gate 2");',
      ].join("\n"),
      expect: [],
    },
    {
      name: "allowed html",
      file: "index.html",
      kind: "html",
      source: '<script type="importmap">{"imports": {"./src/ui.js": "./src/ui.js?v=123456789012", "./data/now.json": "./data/now.json?v=0a1b2c3d4e5f"}}</script>\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<h1 tabindex="-1">x</h1><link href="vendor/figtree/figtree.v2.002.latin.woff2"><span>&#x263E;&#xFE0E;</span><!-- 38.05 -->\n',
      expect: [],
    },
  ];
  const failures = [];
  for (const test of cases) {
    const result = test.kind === "js" ? checkScript(test.file, test.source) : checkHtml(test.file, test.source);
    const found = result.violations.map((v) => v.literal).sort();
    const expected = [...test.expect].sort();
    const ok = found.length === expected.length && found.every((value, index) => value === expected[index]);
    console.log((ok ? "  ok    " : "  FAIL  ") + test.name + (ok ? "" : ": expected " + JSON.stringify(expected) + ", reported " + JSON.stringify(found)));
    if (!ok) failures.push(test.name);
  }
  return failures;
}

// ----------------------------------------------------------------- main ---

function listScripts(directory) {
  const out = [];
  const walk = (relative) => {
    for (const name of readdirSync(path.join(ROOT, relative))) {
      const rel = relative + "/" + name;
      if (rel === "src/crack") continue;
      const info = statSync(path.join(ROOT, rel));
      if (info.isDirectory()) walk(rel);
      else if (name.endsWith(".js") || name.endsWith(".mjs")) out.push(rel);
    }
  };
  if (existsSync(path.join(ROOT, directory))) walk(directory);
  return out.sort();
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const verbose = process.argv.includes("--verbose");
  console.log("check-literals.mjs, repo " + ROOT);
  console.log("self test: planted market values must be reported, allowed forms must pass");
  const testFailures = selfTest();
  if (testFailures.length) {
    console.log("FAIL  the self test failed, so a scan result would mean nothing");
    process.exit(1);
  }

  const files = listScripts("src");
  const violations = [];
  const allowed = [];
  for (const relative of files) {
    const result = checkScript(relative, readFileSync(path.join(ROOT, relative), "utf8"));
    violations.push(...result.violations);
    allowed.push(...result.allowed);
  }
  const htmlPath = path.join(ROOT, "index.html");
  let scanned = files.length;
  if (existsSync(htmlPath)) {
    const result = checkHtml("index.html", readFileSync(htmlPath, "utf8"));
    violations.push(...result.violations);
    allowed.push(...result.allowed);
    scanned += 1;
  }

  console.log("");
  console.log("scanned " + scanned + " file(s): " + [...files, "index.html"].join(", "));
  const byRule = new Map();
  for (const a of allowed) {
    const key = a.rule.startsWith("unit constant") || a.rule.startsWith("declared") || a.rule.startsWith("attribute") ? a.rule : a.rule;
    byRule.set(key, (byRule.get(key) || 0) + 1);
  }
  console.log("allowed: " + ([...byRule.entries()].map(([rule, count]) => count + " " + rule).join(", ") || "none"));
  if (verbose) for (const a of allowed) console.log("  " + a.file + ":" + a.line + "  " + a.literal + "  " + a.rule);

  if (violations.length) {
    console.log("");
    console.log("FAIL  a number in the frontend that no artifact supplied, SPEC.md section 2 rule 2");
    for (const v of violations) console.log("      " + v.file + ":" + v.line + "  " + v.literal + "  " + v.kind + "  | " + v.text.slice(0, 100));
    console.log("");
    console.log(violations.length + " literal(s). Read the figure from a JSON artifact, or, if it is a unit constant, a layout dimension or index arithmetic, add it to the commented allowlist at the top of this file with its reason.");
    process.exit(1);
  }
  console.log("PASS  no numeric literal outside the allowlist in src/ or index.html");
}
