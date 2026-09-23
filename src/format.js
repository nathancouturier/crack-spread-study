/* format.js
 *
 * Turns a value from an artifact into the text a reader sees, and writes the
 * sentences for the three states a figure can be in when it is not there:
 * loading, failed to load, and present but empty. No DOM, so it runs under
 * plain node; tools/validate-format.mjs does exactly that.
 *
 * WHERE THE DECIMALS COME FROM. Not from here. Each artifact carries
 * conventions.decimals, a map from a format name such as usd_bbl to a count of
 * places, and every numeric segment names its format. A format the artifact
 * does not declare throws, naming it, rather than falling back to a guess:
 * docs/design.md Part 4 item 11, "decimals per unit, so formatting needs no
 * literal".
 *
 * SIGNS. A negative figure in prose carries U+2212, the minus sign, which all
 * three vendored faces draw at figure width. A negative figure in a table cell
 * carries the ASCII hyphen minus, so a copied cell pastes into a spreadsheet as
 * a number. docs/design.md Part 3 sections 4 and 6. A positive figure carries a
 * plus only when the artifact marks the value signed. A value that rounds to
 * zero at its decimals prints with no sign at all, so the page never says
 * "-0.00".
 *
 * MISSING. null, undefined, NaN and the infinities are missing, never zero.
 * The number formatters return null for them, and the caller must decide what
 * the gap says; SPEC.md section 2 rule 1 forbids printing a missing value as a
 * number of any kind.
 *
 * Numeric literals: none about the market. The unit words below are the unit
 * constants SPEC.md section 2 rule 2 allows, and they hold no digits.
 */

/** U+2212, the typographic minus, for prose. */
export const MINUS_PROSE = "\u2212";
/** U+002D, the hyphen minus, for table cells. */
export const MINUS_TABLE = "-";

/** The unit each format is read in, as a desk quotes it. Unit constants. An
 *  empty string is a dimensionless figure: a count, a year, a t statistic. */
export const UNITS = Object.freeze({
  usd_bbl: "$/bbl",
  usd_t: "$/t",
  usd_mmbtu: "$/MMBtu",
  eur_mwh: "EUR/MWh",
  mmbtu_per_bbl: "MMBtu/bbl",
  kb_d: "kb/d",
  t: "",
  r2: "",
  pp: "pp",
  pp_per_usd_bbl: "pp per $/bbl",
  percent: "percent",
  yield_percent: "percent",
  ratio: "times",
  bbl_per_t: "bbl/t",
  count: "",
  year: "",
});

/* A year is written 2026, never 2,026. Every other format groups thousands. */
const UNGROUPED = new Set(["year"]);

/** True for anything the page must show as a gap rather than a number. */
export function isMissing(value) {
  return value === null || value === undefined || typeof value !== "number" || !Number.isFinite(value);
}

/** The number of places the artifact declares for a format, or a thrown
 *  Error naming the format and the formats it does declare. */
export function decimalsFor(format, decimals) {
  if (!decimals || typeof decimals !== "object") {
    throw new Error("format.js was given no decimals table; pass the artifact's conventions.decimals");
  }
  const places = decimals[format];
  if (!Number.isInteger(places) || places < 0) {
    throw new Error(
      "the artifact declares no decimals for the format " + JSON.stringify(format) +
      "; it declares " + Object.keys(decimals).sort().join(", ")
    );
  }
  return places;
}

/** Format one number.
 *
 *    value     the number from the artifact
 *    format    its format name, for example "usd_bbl"
 *    decimals  the artifact's conventions.decimals
 *    options   { signed: boolean, context: "prose" | "table" }
 *
 *  Returns a string, or null when the value is missing. */
export function formatNumber(value, format, decimals, options) {
  const opts = options || {};
  const places = decimalsFor(format, decimals);
  if (isMissing(value)) return null;
  const body = new Intl.NumberFormat("en-US", {
    minimumFractionDigits: places,
    maximumFractionDigits: places,
    useGrouping: !UNGROUPED.has(format),
  }).format(Math.abs(value));
  const roundsToZero = !/[1-9]/.test(body);
  if (roundsToZero) return body;
  if (value < 0) return (opts.context === "table" ? MINUS_TABLE : MINUS_PROSE) + body;
  if (opts.signed) return "+" + body;
  return body;
}

/** A number and its unit, "38.05 $/bbl", or null when the value is missing. */
export function formatQuantity(value, format, decimals, options) {
  const text = formatNumber(value, format, decimals, options);
  if (text === null) return null;
  const unit = Object.prototype.hasOwnProperty.call(UNITS, format) ? UNITS[format] : "";
  return unit ? text + " " + unit : text;
}

/** The text of one sentence segment, as the export writes them
 *  (docs/design.md Part 7, C4):
 *    { text }                                  words, no digit
 *    { field, value, format, signed? }         a number
 *    { field, value, label }                   a date or a word, with its label
 *  Returns { text, kind, field, missing } where kind is "text", "number" or
 *  "label". A missing number keeps its field so the caller can name the gap. */
export function segmentText(segment, decimals) {
  if (Object.prototype.hasOwnProperty.call(segment, "text")) {
    return { text: segment.text, kind: "text", field: null, missing: false };
  }
  if (typeof segment.label === "string") {
    return { text: segment.label, kind: "label", field: segment.field, missing: false };
  }
  const text = formatNumber(segment.value, segment.format, decimals, {
    signed: segment.signed === true,
    context: "prose",
  });
  return { text, kind: "number", field: segment.field, missing: text === null };
}

/** A whole sentence of segments as plain text, for an SVG title or desc,
 *  where no span can carry the field. A missing number reads as the segment's
 *  own `missing` words when the export wrote any, and as "no figure" when it
 *  did not. The field identifier is never read out: Gate 5 finding 2 heard
 *  "no figure for margin us gas usd bbl" inside a chart's description. */
export function segmentsText(segments, decimals) {
  return segments
    .map((segment) => {
      const piece = segmentText(segment, decimals);
      return piece.missing ? missingFigureText(segment.missing) : piece.text;
    })
    .join("");
}

/** A figure for a table cell: hyphen minus, sign when asked, or null. */
export function formatCell(value, format, decimals, signed) {
  return formatNumber(value, format, decimals, { signed: signed === true, context: "table" });
}

/* ------------------------------------------------------------- time --- */

/* The parts Intl is asked for. "2-digit" is Intl's own option vocabulary, a
 * string the API defines, not a figure; it is the one string with a digit that
 * tools/check-literals.mjs allows, by exact value. */
const INSTANT_PARTS = Object.freeze({
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "UTC",
});

/** "13 September 2026 at 18:11 UTC", the form the export writes for a fetch
 *  time. Returns null for anything that is not a valid instant. */
export function formatInstant(iso) {
  const date = typeof iso === "string" ? new Date(iso) : iso;
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return null;
  const parts = {};
  for (const part of new Intl.DateTimeFormat("en-GB", INSTANT_PARTS).formatToParts(date)) {
    parts[part.type] = part.value;
  }
  return parts.day + " " + parts.month + " " + parts.year + " at " + parts.hour + ":" + parts.minute + " UTC";
}

/* ------------------------------------------ loading, empty and error --- */

/* SPEC.md section 7.3: errors say what happened and what to do; an empty chart
 * names the missing series and the time of the failed fetch. docs/design.md
 * Part 3 section 8: a loading state is the sentence "Loading {series}", no
 * shimmer. Each function returns plain sentences; dom.js sets them. */

/** "Loading the gasoil and gasoline cracks." */
export function loadingSentence(what) {
  return "Loading " + what + ".";
}

/** Two sentences for an artifact that did not load: what happened, then what
 *  to do. `failure` is the record state.js keeps, with its time, and its own
 *  `todo` when the cause calls for different advice, as a refused schema does. */
export function loadFailureSentences(failure) {
  const when = formatInstant(failure.at);
  const happened =
    "The page could not load " + failure.path + ", which holds " + failure.holds +
    ": " + failure.what + (when ? ", at " + when : "") + ".";
  const todo = failure.todo ||
    "Reload the page to try again. If it fails again the file is missing or damaged in this copy of the site, " +
    "and nothing it holds is shown, rather than shown from a guess.";
  return [happened, todo];
}

/** The sentence an empty chart shows in place of its marks.
 *
 *    series      the series name, in words, as the manifest gives it
 *    fetchedAt   the ISO time of the last fetch attempt, or null
 *    status      the manifest's status word for the series: "failed",
 *                "stale", "ok" or anything else it records
 *    reason      the manifest's reason for the gap, a sentence, or null
 */
export function emptySeriesSentence({ series, fetchedAt, status, reason }) {
  const when = formatInstant(fetchedAt);
  let fetch;
  if (status === "failed") {
    fetch = when ? "its last fetch failed, at " + when : "its last fetch failed, and the time of that fetch is not recorded";
  } else if (status === "stale") {
    fetch = when ? "its last successful fetch, at " + when + ", is stale" : "it is stale, and the time of its last fetch is not recorded";
  } else {
    fetch = when ? "it was last fetched at " + when + " and holds no values for this range" : "it holds no values for this range, and the time of its last fetch is not recorded";
  }
  const because = reason ? " " + reason.trim().replace(/\.?$/, ".") : "";
  return "Nothing is drawn for " + series + ": " + fetch + "." + because + " The gap is left empty rather than filled.";
}

/* The words for one missing figure, and the one rule they obey.
 *
 * THE GATE 5 FINDING. This function used to take the artifact's column
 * identifier and print it: `String(field).replace(/_/g, " ")`, which put "no
 * figure for margin us gas usd bbl" into 110 table cells on a live view, and
 * into the `desc` of a chart, where a screen reader read it aloud. An
 * identifier is what the code calls a column; it is not what the thing is
 * called, and a reader has no way to turn one back into the other.
 *
 * So the words a cell shows are now the caller's, taken from the artifact being
 * rendered, which is where the series and the reason for the gap are named. The
 * caller that has nothing to say gets the plain true sentence and nothing else,
 * and an identifier handed to this function is DROPPED rather than printed:
 * silence about the series beats machine language about it, and a cell that
 * only says "no figure" is still true.
 *
 * Every empty cell's reason is also said once, in words, in the caption or the
 * note beside its table, which is where there is room for it. */

/** What a cell with no figure says when nothing else can be said about it. */
export const NO_FIGURE = "no figure";

/* The shape of an artifact column id. Two tests, because the string arrives
 * both ways: `margin_us_gas_usd_bbl` as it is written in the artifact, and
 * "margin us gas usd bbl" once something has swapped the underscores for
 * spaces, which is the form that got past check-literals, check-styles and
 * validate-format and onto the page. The second test is the unit tail every
 * field in this project ends with. */
const HAS_UNDERSCORE = /_/;
const ENDS_LIKE_A_FIELD = /\b(usd\s+(bbl|t|mmbtu)|kb\s+d|eur\s+mwh|mmbtu\s+per\s+bbl|pp\s+per\s+usd\s+bbl|percent|count|year|months|r2|se|t)$/i;
/* One word is a name for a thing, not something said to a reader. Every field
 * in every artifact is either one word or underscored, and every phrase this
 * function is meant to print is at least two: "no figure yet", "after this
 * series ends". tools/validate-format.mjs tries all 328 field names. */
const IS_ONE_WORD = /^\S+$/;

/** The words for a figure that is missing, given what the caller can name.
 *
 *    words   the plain English name of what is missing, or of why it is, as the
 *            artifact gives it. Absent, empty, or shaped like an identifier:
 *            the cell says "no figure" and claims nothing more.
 */
export function missingFigureText(words) {
  const name = typeof words === "string" ? words.trim() : "";
  if (!name) return NO_FIGURE;
  if (HAS_UNDERSCORE.test(name) || IS_ONE_WORD.test(name) || ENDS_LIKE_A_FIELD.test(name)) return NO_FIGURE;
  return name;
}
