/* theme.js
 *
 * The portfolio's theme toggle, copied from nathancouturier.github.io
 * script.js section 2 and its keyboard shortcut in section 18, kept as close
 * to the original as the declared differences allow. docs/design.md Part 3
 * section 7.
 *
 * Kept from the portfolio: data-theme on <html>; the localStorage key
 * nc-theme, shared with the portfolio because both sites are on the same
 * origin; light unless the store says otherwise, with the system
 * prefers-color-scheme ignored as the portfolio ignores it; the glyph swapped to
 * U+2600 in dark and U+263E in light; meta theme-color rewritten to #17181C or
 * #FBFAF8; aria-label "Toggle theme" and title "Press T to toggle"; the key T
 * toggling unless the target is a field or a modifier is held.
 *
 * The four declared differences:
 *   1  the key listener also ignores select and [contenteditable], because the
 *      Model view will have selects
 *   2  every localStorage access sits inside try, so a blocked store falls back
 *      to light instead of throwing
 *   3  an inline script in index.html's head sets data-theme before the first
 *      paint; this module takes over after load
 *   4  the button also sets aria-pressed to whether dark is on
 * And one more, recorded as docs/design.md Part 7, C8: each glyph is followed
 * by U+FE0E, the text presentation selector, so no platform draws it as a
 * colour emoji.
 *
 * Numeric literals: none. The two hex colours are strings and the portfolio's.
 */

const STORAGE_KEY = "nc-theme";
const GLYPH_DARK = "\u2600\uFE0E";
const GLYPH_LIGHT = "\u263E\uFE0E";
const THEME_COLOR_DARK = "#17181C";
const THEME_COLOR_LIGHT = "#FBFAF8";

const root = document.documentElement;
const state = { theme: readStored() };

function readStored() {
  try {
    return localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light";
  } catch (error) {
    return "light";
  }
}

export function applyTheme(theme) {
  state.theme = theme;
  root.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch (error) {
    /* storage blocked: the choice lasts for this page only */
  }
  const icon = document.querySelector("#theme-icon");
  if (icon) icon.textContent = theme === "dark" ? GLYPH_DARK : GLYPH_LIGHT;
  const button = document.querySelector("#theme-toggle");
  if (button) button.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = theme === "dark" ? THEME_COLOR_DARK : THEME_COLOR_LIGHT;
}

export function toggleTheme() {
  applyTheme(state.theme === "dark" ? "light" : "dark");
}

export function currentTheme() {
  return state.theme;
}

/** Wire the button and the T key, and apply the stored theme once. */
export function initTheme() {
  const button = document.querySelector("#theme-toggle");
  if (button) button.addEventListener("click", toggleTheme);
  document.addEventListener("keydown", (ev) => {
    const target = ev.target;
    if (target && target.matches && target.matches("input, textarea, select, [contenteditable], [contenteditable] *")) return;
    if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
    if (ev.key === "t" || ev.key === "T") {
      ev.preventDefault();
      toggleTheme();
    }
  });
  applyTheme(state.theme);
}
