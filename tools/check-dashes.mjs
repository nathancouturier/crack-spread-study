#!/usr/bin/env node
// Fail if any tracked text file contains an em dash or an en dash.
//
//     node tools/check-dashes.mjs
//     node tools/check-dashes.mjs --list        print the files scanned
//
// SPEC.md section 0.1 bans both characters from this repository: code, comments,
// copy, README and commit messages. The rule exists because the sibling repos on
// the same GitHub profile follow it, and a project that keeps it in half its
// files reads as three projects rather than one body of work.
//
// The two characters are written here as escapes, never literally, because a
// checker that contained the thing it forbids would report itself. It scans
// itself like every other file, which is the point: this tool is inside the rule
// it enforces.
//
//   U+2014 em dash
//   U+2013 en dash
//
// ESCAPED DASHES COUNT. This project writes data/manifest.json with
// ensure_ascii=True, so an em dash inside a note reaches the file as the six
// characters backslash u 2 0 1 4 and a plain text scan would never see it. Every
// .json file is therefore also scanned with its \\uXXXX sequences decoded, and a
// hit reports the line of the raw file so it can be found. Without this, the one
// artifact the site renders most of could carry a banned character forever.
//
// Which files are scanned. Everything git would track: the index plus untracked
// files that are not ignored, so a file that has not been committed yet is still
// checked. If git is not available the scanner walks the tree instead and skips
// the usual build and cache directories. Binary files are skipped, and so is
// vendor/, which holds pinned third party libraries this project does not get to
// rewrite. data/private/ is gitignored and therefore never reached.
//
// The one exception the house rule allows is a dash that is genuinely part of a
// cited title, a source name, or a quoted line from a document. Changing one of
// those would be falsifying a citation, which is worse than breaking a style
// rule. Mark such a line by putting the token
//
//     dash-allowed
//
// in it, or on the line directly above it. Marked lines are listed separately
// under "quoted titles, not changed" and do not fail the run. There are none in
// the repository today, and every one that is ever added should be argued for in
// the pull request that adds it.

import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");

// Built from their code points, never typed and never written as a backslash u
// escape either. A backslash u escape for these two would be found by the
// escaped scan below and this file would fail itself, which is the one false
// positive a checker must not have.
const EM_DASH = String.fromCharCode(0x2014);
const EN_DASH = String.fromCharCode(0x2013);
const BANNED = [
  { name: "em dash", char: EM_DASH },
  { name: "en dash", char: EN_DASH },
];

// Built rather than written, so this line does not itself contain the token and
// exempt the whole file.
const ALLOW_TOKEN = "dash" + "-" + "allowed";

const SKIP_DIRS = new Set([
  ".git",
  "node_modules",
  "__pycache__",
  ".pytest_cache",
  ".ruff_cache",
  ".venv",
  "venv",
  "vendor",
  "dist",
  "build",
]);

const BINARY_EXTENSIONS = new Set([
  ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".svgz",
  ".woff", ".woff2", ".ttf", ".otf", ".eot",
  ".zip", ".gz", ".xz", ".7z", ".xls", ".xlsx", ".xlsm",
  ".pyc", ".so", ".dll", ".dylib", ".exe",
]);

function trackedFiles() {
  try {
    const out = execFileSync(
      "git",
      ["ls-files", "--cached", "--others", "--exclude-standard"],
      { cwd: ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }
    );
    const files = out.split("\n").map((line) => line.trim()).filter(Boolean);
    if (files.length) return { files, how: "git ls-files" };
  } catch {
    // fall through to the walk
  }
  const files = [];
  const walk = (relative) => {
    const dir = path.join(ROOT, relative);
    for (const name of readdirSync(dir)) {
      const rel = relative ? relative + "/" + name : name;
      const full = path.join(ROOT, rel);
      let info;
      try {
        info = statSync(full);
      } catch {
        continue;
      }
      if (info.isDirectory()) {
        // data/private is gitignored and holds sources this repository may not
        // redistribute. The walk must not read it, so that the two paths through
        // this tool scan the same set of files.
        if (!SKIP_DIRS.has(name) && rel !== "data/private") walk(rel);
      } else if (info.isFile()) {
        files.push(rel);
      }
    }
  };
  walk("");
  return { files, how: "directory walk, git was not available" };
}

function isSkippedPath(relative) {
  const parts = relative.split("/");
  if (parts.some((part) => SKIP_DIRS.has(part))) return true;
  if (relative.startsWith("data/private/")) return true;
  return BINARY_EXTENSIONS.has(path.extname(relative).toLowerCase());
}

function looksBinary(buffer) {
  const limit = Math.min(buffer.length, 8000);
  for (let i = 0; i < limit; i += 1) {
    if (buffer[i] === 0) return true;
  }
  return false;
}

// A JSON file written with ensure_ascii hides its dashes behind \\uXXXX. This
// turns those six characters into the character they name so the same scan
// finds them, and reports them as escaped so the reader knows what to search
// for.
// The patterns are assembled from pieces for the same reason the two characters
// above are: written out in full, this file would match itself.
const ESCAPED = [
  { name: "escaped em dash", pattern: new RegExp("\\\\u" + "2014", "gi") },
  { name: "escaped en dash", pattern: new RegExp("\\\\u" + "2013", "gi") },
];

const args = new Set(process.argv.slice(2));
const { files, how } = trackedFiles();

const hits = [];
const allowed = [];
let scanned = 0;
let skipped = 0;

for (const relative of files) {
  if (isSkippedPath(relative)) {
    skipped += 1;
    continue;
  }
  const full = path.join(ROOT, relative);
  if (!existsSync(full)) continue;
  let buffer;
  try {
    buffer = readFileSync(full);
  } catch {
    skipped += 1;
    continue;
  }
  if (looksBinary(buffer)) {
    skipped += 1;
    continue;
  }
  scanned += 1;
  const text = buffer.toString("utf8");
  const lines = text.split("\n");

  const record = (index, column, kind, line) => {
    const previous = index > 0 ? lines[index - 1] : "";
    const exempt = line.includes(ALLOW_TOKEN) || previous.includes(ALLOW_TOKEN);
    const hit = {
      file: relative,
      line: index + 1,
      column: column + 1,
      kind,
      text: line.trim().slice(0, 120),
    };
    if (exempt) allowed.push(hit);
    else hits.push(hit);
  };

  lines.forEach((line, index) => {
    for (const dash of BANNED) {
      let at = line.indexOf(dash.char);
      while (at !== -1) {
        record(index, at, dash.name, line);
        at = line.indexOf(dash.char, at + 1);
      }
    }
    for (const escaped of ESCAPED) {
      escaped.pattern.lastIndex = 0;
      let match = escaped.pattern.exec(line);
      while (match !== null) {
        record(index, match.index, escaped.name, line);
        match = escaped.pattern.exec(line);
      }
    }
  });
}

console.log("check-dashes.mjs, repo " + ROOT);
console.log("file list from " + how);
console.log(
  "scanned " + scanned + " text file(s), skipped " + skipped + " binary, vendored or private file(s)"
);
if (args.has("--list")) {
  for (const relative of files) {
    if (!isSkippedPath(relative)) console.log("  " + relative);
  }
}
console.log("");

if (allowed.length) {
  console.log("quoted titles, not changed, " + allowed.length + " occurrence(s):");
  for (const hit of allowed) {
    console.log("  " + hit.file + ":" + hit.line + ":" + hit.column + "  " + hit.kind + "  " + hit.text);
  }
  console.log("");
}

if (hits.length) {
  console.log("FAIL  no em dash or en dash in tracked text files");
  for (const hit of hits.slice(0, 40)) {
    console.log("      " + hit.file + ":" + hit.line + ":" + hit.column + "  " + hit.kind + "  " + hit.text);
  }
  if (hits.length > 40) console.log("      and " + (hits.length - 40) + " more");
  console.log("");
  console.log(
    hits.length + " banned dash(es) in " + new Set(hits.map((h) => h.file)).size +
    " file(s). Replace each with a comma or an ASCII hyphen."
  );
  console.log(
    "If a dash is genuinely part of a cited title, put the token " + ALLOW_TOKEN +
    " on that line and say why in the pull request."
  );
  process.exit(1);
}

console.log("PASS  no em dash or en dash in tracked text files, escaped ones included");
process.exit(0);
