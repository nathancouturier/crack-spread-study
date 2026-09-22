// A headless Chromium driven through the DevTools protocol, with no npm install.
//
//     import { launch } from "./browser.mjs";
//     const browser = await launch();            // a fresh profile, a free port
//     const page = await browser.page();
//     await page.goto("http://localhost:8000/crack-spread-study/#/now");
//     ...
//     await browser.close();                     // kills it, deletes the profile
//
// Used by tools/check-layout.mjs and scripts/screenshots.mjs. Node 22 or later,
// for the global WebSocket and fetch. Plain node, no dependencies.
//
// WHICH BROWSER. The first of these that exists:
//   1  --browser <path> on the command line of the calling script
//   2  the CRACK_BROWSER environment variable
//   3  the usual install paths of Edge and Chrome on Windows, macOS and Linux
// CRACK_BROWSER_NO_SANDBOX=1 adds --no-sandbox, which a CI image whose AppArmor
// policy refuses unprivileged user namespaces needs and nothing else should.
// Any Chromium works: Edge, Chrome, Chromium. Firefox and Safari do not speak
// this protocol and are not supported.
//
// A FRESH PROFILE EVERY LAUNCH. ES modules are cached hard, and a profile reused
// from an earlier run can measure a module graph that is no longer on disk. So
// every launch makes its own --user-data-dir under the system temp directory and
// removes it on close. The debugging port is chosen by the browser
// (--remote-debugging-port=0) and read back from DevToolsActivePort, so two runs
// never collide and nothing else on the machine has to be stopped first.

import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const CANDIDATES = [
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
  "/usr/bin/microsoft-edge",
];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** The value after `--name` in argv, or null. */
export function argValue(argv, name) {
  const index = argv.indexOf(name);
  return index >= 0 && index + 1 < argv.length ? argv[index + 1] : null;
}

/** The browser executable, or a thrown Error saying how to name one. */
export function findBrowser(argv = process.argv) {
  const named = argValue(argv, "--browser") || process.env.CRACK_BROWSER;
  if (named) {
    if (!existsSync(named)) throw new Error("no browser at " + named);
    return named;
  }
  const found = CANDIDATES.find((candidate) => existsSync(candidate));
  if (!found) throw new Error("no Chromium browser found; pass --browser <path> or set CRACK_BROWSER");
  return found;
}

class Page {
  constructor(socket) {
    this.socket = socket;
    this.seq = 0;
    this.pending = new Map();
    this.listeners = new Map();
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const { resolve, reject } = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) reject(new Error(message.error.message));
        else resolve(message.result);
      } else if (message.method) {
        for (const listener of this.listeners.get(message.method) || []) listener(message.params);
      }
    });
  }

  send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++this.seq;
      this.pending.set(id, { resolve, reject });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  on(method, listener) {
    if (!this.listeners.has(method)) this.listeners.set(method, []);
    this.listeners.get(method).push(listener);
  }

  /** Evaluate an expression in the page and return its value. Promises are awaited. */
  async evaluate(expression) {
    const result = await this.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) {
      const detail = result.exceptionDetails.exception ? result.exceptionDetails.exception.description : result.exceptionDetails.text;
      throw new Error("in the page: " + detail);
    }
    return result.result.value;
  }

  async viewport(width, height) {
    await this.send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width < 768 });
  }

  /** Load a URL and wait for the load event. */
  async goto(url) {
    const loaded = new Promise((resolve) => this.on("Page.loadEventFired", resolve));
    await this.send("Page.navigate", { url });
    await Promise.race([loaded, sleep(15000)]);
  }

  async reload() {
    const loaded = new Promise((resolve) => this.on("Page.loadEventFired", resolve));
    await this.send("Page.reload", { ignoreCache: true });
    await Promise.race([loaded, sleep(15000)]);
  }

  /** Poll an expression until it is truthy, or throw after `timeout` ms. */
  async waitFor(expression, timeout = 15000) {
    const until = Date.now() + timeout;
    while (Date.now() < until) {
      if (await this.evaluate(expression)) return;
      await sleep(100);
    }
    throw new Error("timed out waiting for " + expression);
  }

  /** A PNG of the whole page, every pixel of its height, as a Buffer. */
  async screenshotFullPage(width) {
    const height = await this.evaluate("Math.ceil(document.documentElement.scrollHeight)");
    const shot = await this.send("Page.captureScreenshot", {
      format: "png",
      captureBeyondViewport: true,
      clip: { x: 0, y: 0, width, height, scale: 1 },
    });
    return { png: Buffer.from(shot.data, "base64"), height };
  }
}

/** Launch a headless browser on a fresh profile. */
export async function launch(argv = process.argv) {
  const executable = findBrowser(argv);
  const profile = mkdtempSync(path.join(tmpdir(), "crack-browser-"));
  // CRACK_BROWSER_NO_SANDBOX, for a CI container and for nothing else.
  //
  // Chrome's own sandbox needs unprivileged user namespaces, and several CI
  // images, GitHub's ubuntu-24.04 among them, restrict those through AppArmor.
  // Chrome then exits immediately and this launch times out waiting for
  // DevToolsActivePort, which reads as "the browser is broken" rather than as
  // "the sandbox was refused". Turning the sandbox off is safe where the thing
  // being loaded is the repository's own localhost server and the machine is
  // destroyed at the end of the job, and is NOT safe anywhere else, so it is
  // opt in by environment variable, off by default, and never a flag a local
  // run reaches for.
  const sandbox = process.env.CRACK_BROWSER_NO_SANDBOX === "1"
    ? ["--no-sandbox", "--disable-dev-shm-usage"]
    : [];
  const child = spawn(executable, [
    "--headless=new",
    "--remote-debugging-port=0",
    "--user-data-dir=" + profile,
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--hide-scrollbars",
    ...sandbox,
    "about:blank",
  ], { stdio: "ignore" });

  const portFile = path.join(profile, "DevToolsActivePort");
  let port = null;
  for (let attempt = 0; attempt < 100 && port === null; attempt += 1) {
    if (existsSync(portFile)) {
      const first = readFileSync(portFile, "utf8").split("\n")[0].trim();
      if (first) port = Number(first);
    }
    if (port === null) await sleep(100);
  }
  if (port === null) {
    child.kill();
    throw new Error("the browser at " + executable + " did not open a debugging port");
  }

  const close = async () => {
    child.kill();
    await sleep(500);
    try {
      rmSync(profile, { recursive: true, force: true });
    } catch {
      // The browser may still hold a file for a moment; the directory is in temp.
    }
  };

  return {
    executable,
    profile,
    close,
    async page() {
      let targets = [];
      for (let attempt = 0; attempt < 50; attempt += 1) {
        try {
          targets = await (await fetch("http://127.0.0.1:" + port + "/json")).json();
        } catch {
          targets = [];
        }
        if (targets.some((t) => t.type === "page")) break;
        await sleep(100);
      }
      const target = targets.find((t) => t.type === "page");
      if (!target) throw new Error("no page target on port " + port);
      const socket = new WebSocket(target.webSocketDebuggerUrl);
      await new Promise((resolve, reject) => {
        socket.addEventListener("open", resolve, { once: true });
        socket.addEventListener("error", reject, { once: true });
      });
      const page = new Page(socket);
      await page.send("Page.enable");
      await page.send("Runtime.enable");
      await page.send("Log.enable");
      page.errors = [];
      page.on("Runtime.exceptionThrown", (p) => page.errors.push("exception: " + (p.exceptionDetails.exception ? p.exceptionDetails.exception.description : p.exceptionDetails.text)));
      page.on("Runtime.consoleAPICalled", (p) => {
        if (p.type === "error" || p.type === "warning") page.errors.push("console " + p.type + ": " + p.args.map((a) => a.value !== undefined ? a.value : a.description).join(" "));
      });
      page.on("Log.entryAdded", (p) => {
        if (p.entry.level === "error" || p.entry.level === "warning") page.errors.push("log " + p.entry.level + ": " + p.entry.text + (p.entry.url ? " " + p.entry.url : ""));
      });
      return page;
    },
  };
}

/** Open the Now view at `base` in `theme` with `open` sections, and wait until
 *  every open section has rendered and the fonts are in. */
export async function openNow(page, base, { theme = "light", open = "", width = 1440, height = 900 } = {}) {
  await page.viewport(width, height);
  await page.goto(base);
  // goto resolves on the first load event it sees, and on a fresh target that
  // can be the initial about:blank rather than the site, where localStorage is
  // denied. So wait until the document really is the site before touching
  // storage, rather than trusting the load event.
  await page.waitFor("location.href.startsWith(" + JSON.stringify(base) + ") && document.readyState !== 'loading'");
  await page.evaluate("localStorage.setItem('nc-theme', " + JSON.stringify(theme) + "), true");
  await page.goto(base + (open ? "#/now?open=" + open : "#/now"));
  await page.reload();
  await page.waitFor("document.querySelectorAll('.section').length > 0");
  await page.waitFor(
    "document.fonts.status === 'loaded' && [...document.querySelectorAll('.section__body[data-open=\"true\"] .section__inner')]" +
    ".every((inner) => inner.children.length > 0 && !inner.querySelector('.state-message[role=\"status\"]'))"
  );
  // Width observers and the rail plates run after layout; give them two frames.
  await page.evaluate("new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r, 400))))");
}

/** Open any view by its hash at `base` in `theme`, and wait until the view's
 *  title is drawn, the fonts are in and the width observers have run. */
export async function openView(page, base, { theme = "light", hash = "#/now", width = 1440, height = 900 } = {}) {
  await page.viewport(width, height);
  await page.goto(base);
  await page.waitFor("location.href.startsWith(" + JSON.stringify(base) + ") && document.readyState !== 'loading'");
  await page.evaluate("localStorage.setItem('nc-theme', " + JSON.stringify(theme) + "), true");
  // Set the hash in the page rather than through navigation: a same document
  // navigation fires no load event to wait for.
  await page.evaluate("location.hash = " + JSON.stringify(hash) + ", true");
  await page.reload();
  await page.waitFor("document.querySelector('#view-title') && !document.querySelector('#view .state-message[role=\"status\"]')");
  await page.waitFor("document.fonts.status === 'loaded'");
  await page.evaluate("new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r, 400))))");
}
