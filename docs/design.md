# Design: the chart, waterfall and table treatment

SPEC.md section 0.2: "Before writing CSS, write a short plan for the chart,
waterfall and table treatment and critique it against this brief. If any part of
it is what you would produce for any dashboard rather than this one, revise it
and say what you changed."

This file is that plan, in the order the work happened:

- **Part 0.** What the content is, measured on 2026-09-16 from the committed
  caches through `crack.series` and `crack.analysis`. Every decision below
  answers to one of these numbers.
- **Part 1.** The first pass, the ten items of the Gate 4 brief written straight
  through. It is left here with its mistakes, because the critique is the part
  SPEC.md section 0.2 asks for.
- **Part 2.** The critique, finding by finding, each with the revision it forced
  and why. Then the banned list, checked item by item.
- **Part 3.** The settled specification. **The builder implements Part 3 and
  nothing else.** Where Part 3 differs from Part 1, Part 2 says why.
- **Part 4.** What the JSON artifacts must carry for Part 3 to be buildable
  without a numeric literal in the frontend.
- **Part 5.** The checklist the shell has to fail against.
- **Part 7.** The Gate 4 build brief's corrections, C1 to C5, each already
  folded into Parts 0, 3, 4 and 5: August 2026 can be decomposed from the
  ministry's own prices, three data dates, the Provenance summary, sentences as
  segments, and what is not exported yet.
- **Part 6.** The second critique, by a reviewer who did not write Parts 1 to 3:
  the generic dashboard test item by item, the banned list read literally with
  its near relatives, every colour pairing measured in both themes, the honesty
  of the negative results, the CV line walked in ten seconds, and what fits at
  375 px. **Its revisions are already folded into Part 3, 4 and 5**, each edit
  tagged with its finding number (S1 and so on), so Part 3 is still the only
  part a builder reads.

No CSS here beyond token names. Sizes are stated so the builder implements a
decision rather than makes one.

---

## Part 0. The content, measured

**0.1 The landing month CAN be decomposed, from the ministry's own prices.**
Corrected at Gate 4 (Part 7, C1). The first version of this paragraph said the
landing month could not be decomposed because no product prices existed for it.
That premise was false. `data/cache/dgec_note_printed_monthly.csv` carries the
ministry's FINAL August 2026 monthly quotations, printed in the note of 4
September 2026 with provisional False: Eurosuper 1135, Gazole 1278, Fioul
domestique 1225, Jet 1284, Fioul lourd TBTS 528, Brent date 683 $/t, and
`data/cache/dgec_brent_monthly.csv` has August Brent at 91.076 $/bbl.
`series.latest_view()`, with the Gate 4 fields:

```
margin month                 2026-08   MBR 38.05 $/bbl, final
margin_carrier               gasoil, August's own, from the same ministry, month and basis as the MBR
runs month                   2026-06   JODI, provisional, lag 2.4 to 2.9 months
weekly crack date            2026-09-04 reconstructed from the ministry's chart, also printed in that note
percentile_10y               100.0 on 120 observations, i.e. the highest of 120 months
crack_month                  2026-02   the OPEC path, kept unchanged as history, not used on Now
```

**0.1b August 2026, decomposed** (`series.note_decomposition_for_month`, pinned in
`tests/test_note_decomposition.py`). Five products, each with a factor cited from
an ICE Futures Europe crack contract specification, because the DGEC methodology
note states no product factor (its only factor is Brent's 7.55 bbl/t):

```
                 $/t    bbl/t   crack $/bbl   volume yield   contribution
gasoil (Gazole)  1278   7.45      +80.47        0.3355          +27.00
jet              1284   7.88      +71.87        0.0866           +6.23
gasoline         1135   8.33      +45.18        0.1324           +5.98
  (Eurosuper priced on the method's EuroBOB yield)
heating oil      1225   7.45      +73.35        0.0809           +5.94
  (Fioul domestique, ICE gasoil 0.1 pct FOB ARA barges factor)
fuel oil 1 pct    528   6.35       -7.93        0.0740           -0.59
  (Fioul lourd TBTS, ICE fuel oil 1 pct FOB NWE cargoes factor)
residual                                                           -6.50
official MBR                                                       38.05
gas wedge at 21.11 $/MMBtu                                         -3.09
at this study's intensity                                          34.96
covered volume yield       0.709
unattributed               butane, export gasoline, naphtha, propane, sulphur (23.2 pct of the tonne),
                           plus the method's gas purchase, freight and insurance costs
```

On the ministry's final printed months (2025-11, 2026-02, 2026-03, 2026-08) the
residual is negative in all four and gasoil carries every one. Provisional
printed months (2025-12, 2026-04, 2026-09) are not decomposed and are listed as
such.

**0.2 February 2026 on the OPEC path, now history and not the Now view's.**
The paragraph below is the Gate 3 measurement on the OPEC MOMR cracks and it is
still true; it is no longer what the landing view draws.

```
gasoil contribution          +7.96 $/bbl
gasoline contribution        +2.22
residual                     -3.68      larger in size than the gasoline line
official MBR                  6.50
gas wedge at 11.24 $/MMBtu   -1.64      (0.21217 - 0.06590) MMBtu/bbl x gas
at this study's intensity     4.86
covered volume yield          0.468     the two priced products are under half the barrel
unattributed                  butane, jet, export gasoline, 1 pct fuel oil, heating oil, naphtha, propane, sulphur
```

August 2026 for the same lower half: MBR 38.05, wedge 3.09 at 21.11 $/MMBtu,
34.96 at this study's intensity.

Across 134 decomposable months the residual is negative in 132, median minus 54
percent of the official margin (Gate 2 self audit, unsure item 1). **A large
negative residual is the normal shape of this waterfall, not an exception.**

**0.3 The seasonal range has three or four years, and today is outside it.**
`analysis.seasonal_weekly`: weeks 1 to 26 have `n_years` 3 (2023 to 2025),
weeks 27 to 52 have 4 (2022 starts on 2022-07-01), week 53 has 0. Week 36 of
2026: gasoil 91.14 against a prior range of 15.44 to 58.21; gasoline 65.91
against 12.07 to 30.28. The current line sits a full range width above the band.

**0.4 The weekly evidence classes.** 221 weeks today: `cross_checked` 214,
`single_geometry_newest` 1 (2026-09-18, the end a reader looks at first),
`single_geometry_oldest` 6 (2022-07-01 to 2022-08-05, the least defended data in
the study). 20 weeks carry figures the ministry printed. Every one of these
counts moves when a note is collected, so the site counts them from
`data/cache/dgec_note_reconstructed_weekly.csv` at build time and never types
one into copy; at Gate 4 they read 219, 194, 19 and 18. `docs/methodology.md`
section 1.12.

**0.5 The response of runs, two models.**

```
                       kb/d per 10 $/bbl   95 pct interval       share of runs
capacity (SPEC 6.1)        +59.3           -290.1 to +408.8      +1.1 pct
intake with trend          +230.4          +5.1 to +455.6        +4.4 pct, +0.1 to +8.8
```

On a shared axis from -290 to +456 the fallback's lower end sits 0.7 percent of
the axis from zero: one or two pixels at any width a table cell will have. The
eye will read "touches". The printed figure has to say "does not, by 5.1".

**0.6 The horse race cannot separate the horses.** Power against the observed
effect 0.050 to 0.121 at a test size of 0.050. Four of six pairs at 0.050 to
0.072. The kindest pair needs 1,570 forecasts for 95 percent power.

**0.7 The threshold is unidentified**, point 2.28, interval 2.03 to 11.28
reaching the edge of the search. Remove 2020-07 to 2022-03 and the slope below
the kink flips from +3.88 to -0.50. `headroom` is None.

**0.8 The two cracks against the official margin:** R2 0.855 for gasoil, 0.551
for gasoline. Gasoline seasonality holds (+4.78 $/bbl May to September, t 4.64).
Gasoil winter does not (t -0.59); its strongest months are October (+3.00) and
November (+2.09).

**0.9 Breaks.** The MBR has none: the published file starts 2015-01, inside the
ministry's recomputed window (`config.DGEC_METHOD_*`). The breaks that do exist
are definitional: the pink sheet gas series becomes TTF from 2015-04; the
capacity denominator steps at 2017-01 and 2026-01; the OPEC premium gasoline
column is not one product across 2004 to 2013 (open question 11).

**0.10 The palette, measured, WCAG 2.1.**

| Token | Light, on `--bg` | Dark, on `--bg` |
|---|---|---|
| `--text` | 17.01 | 17.01 |
| `--text-muted` | 4.90 | 7.54 |
| `--text-dim` | **2.54** | 3.47 |
| `--accent` | 7.96 | **3.79** |
| `--accent-bright` | 6.51 | 5.15 |
| `--border` | 1.24 | 1.27 |
| `--border-strong` | 1.49 | 1.64 |

`--text-dim` fails as text in light and fails even the 3.0 graphics bar. Dark
`--accent` passes 3.0 for marks and fails 4.5 for text. This table covers each
token on `--bg` only; Part 6 section C measures every pairing Part 3 actually
draws, including marks on marks, and found three more failures.

**0.11 The portfolio is the identity and not the component library.** Its
stylesheet also carries a `backdrop-filter: blur(18px)` nav, a `body::after`
grain overlay driven by `--grain-opacity`, uppercase letter spaced `.eyebrow`
labels, scroll reveal staggers and `scroll-behavior: smooth`. Every one of those
is on SPEC.md section 0.2's banned list. The tokens are inherited; those rules
are not.

**0.12 What the siblings vendor.** `lme-comex-arbitrage-model` vendors three
fonts and no chart library, and draws SVG by hand (`src/charts.js`).
`baltic-freight-routes` vendors `d3.v7.9.0.min.js`, 279,706 bytes, and uses it
for `geoPath`, `geoNaturalEarth`, `zoom`, `select` and `symbol`: a map, not a
chart.

---

## Part 1. The first pass

Written straight through as a competent first attempt. Do not build from this
part.

**1. Now.** A header with the site name, six nav links and the theme toggle. The
latest official margin as a large Fraunces figure, "38.05 $/bbl", with the
verdict sentence under it. Under that a single line: "Margins Aug 2026 | Runs Jun
2026 (provisional) | Products Feb 2026". Then four section headers, each a row
with the section name, its headline value on the right and a chevron: Cracks
91.14, Margin stack 38.05, Runs unidentified, Provenance 20 series. A header opens
its section in place with a height transition.

**2. Time series.** Gasoil in the accent, gasoline in `--text-muted` and dashed,
both with end labels. Horizontal gridlines at every y tick, a month tick on the
x axis. Range buttons 1Y, 3Y, All above the chart. Events as numbered flags on
the top edge. A crosshair with a floating tooltip card listing both values. A
NaN breaks the line. A caption under the chart says the weekly series is
reconstructed, and a footnote says the six oldest weeks are least defended.

**3. Seasonal.** Per crack, a band from the prior five years' minimum to
maximum, a mean line, the current year in the accent. The band labelled "5 year
range". A toggle with three checkboxes: exclude 2020, 2022, 2026. `n_years` in
the tooltip.

**4. Waterfall.** Vertical, for the latest month, August 2026: gasoil, gasoline,
other, official MBR, gas, margin after gas. Positive steps green, negative red,
signed figures on top of each bar. The residual as "Other" in grey.

**5. Regression and horse race tables.** Coefficient, standard error, t with
significance stars, R2, OOS RMSE. The horse race sorted by RMSE with the lowest
in bold. The interval as a text column, "[5.1, 455.6]". The headroom cell prints
"n/a" in `--text-dim` with a tooltip saying unidentified. The response table
leads with the 230.4 kb/d model, since it is the one that clears zero.

**6. Typography.** As the LME sibling: JetBrains Mono for every figure, including
the figures inside the verdict sentence, and for column headers, nav and axis
labels; Figtree for prose; Fraunces for the verdict and view titles. Vendored
fonts copied from the sibling.

**7. Themes.** `styles/tokens.css` copies the portfolio `:root` and
`[data-theme="dark"]`. The portfolio's nav and body rules copied with them so the
site feels like the portfolio. The toggle copied from `portfolio_script.js`.

**8. Motion.** Section open 180ms. Bars tween. Charts draw in on first open, since
opening a section is an action. Figures crossfade when the Model recomputes. The
theme change crossfades over the portfolio's 380ms.

**9. Accessibility.** `aria-expanded` on section headers, a visible focus ring,
`title` and `desc` on every SVG, a data table behind each chart, contrast passes
AA.

**10. Charts.** SVG by hand, because the LME sibling did.

---

## Part 2. The critique

Each finding asks of the first pass: is this what I would produce for any
dashboard rather than this one? Tagged **generic**, **wrong for this content**,
or both. Each ends with the revision Part 3 implements.

### Now

**K1. The waterfall is drawn for a month that has nothing to decompose.** Wrong
for this content. Part 0.1: on August 2026 the product lines are empty and the
residual is the whole 38.05. A first pass that follows SPEC.md section 7.2 to the
letter produces one tall "Other" bar and two missing bars, which reads as a
broken chart.
*Revision:* two waterfalls side by side on one declared scale, February 2026 (the
latest month with product prices, full decomposition) and August 2026 (the
latest margin, official margin and the wedge only, product rows saying why they
are empty). Part 3 section 4.

**K2. The hero figure above the sentence is a metric with a label.** Generic.
SPEC.md section 7.3 forbids exactly this, and the figure it would crown is
38.05, a number with a percentile of 100 that a reader takes for a placeholder
(Gate 2 unsure item 3).
*Revision:* no hero figure. The verdict sentence is the `h1`. The percentile is
said as a rank, "the most in the 120 months to August 2026".

**K3. The pipe joined date line is a middle dot meta string in disguise, and it
merges three dates into one reading.** Both. SPEC.md section 13 says show the
runs date separately from the margin date; a single line with separators is the
visual form of merging them.
*Revision:* a definition list, three rows, each a full phrase with its status
word. Part 3 section 1.

**K4. Four section headers with a value each is a KPI row turned sideways.**
Generic. "Runs unidentified" puts the one negative finding in the slot where a
number is expected, so it reads as a missing value; "Provenance 20 series" is a
vanity count that hides the outstanding manual step (the OPEC archive hole).
*Revision:* each header carries one sentence. Figures appear inside sentences
with their dates, never alone on the right.

**K5. The chevron is an arrow appended to a button, and the obvious replacement,
a plus and minus, collides with sign.** Both. On a page where "+2.22" means a
positive contribution, a "+" beside "Margin stack" reads as a value.
*Revision:* the words "Show" and "Hide" at the right of the header row.

**K6. The weekly crack date is not on the landing view.** Wrong for this
content. SPEC.md section 1's "tracked" clause needs the weekly series' data
date, and the three data dates are all monthly. The first pass would have failed
the ten second test on its first clause.
*Revision:* the Cracks header sentence carries the week, "in the week to 4
September 2026". The three monthly dates stay three.

**K7. The verdict clause about runs would print a percentile and a headroom
label.** Wrong for this content. There is no headroom figure (Part 0.7).
*Revision:* the runs clause is a words only clause when the threshold is
unidentified. Template in Part 3 section 1.

### Time series

**K8. Gasoil in the accent spends the accent on identity and makes colour the
product carrier.** Generic and against the brief twice.
*Revision:* both products in ink roles, gasoil solid `--text`, gasoline dashed
`--text-muted`; the accent goes on the latest week only.

**K9. 1Y, 3Y, All range buttons.** Generic, imported from a price chart. This
sample has four named regimes and one reconstruction start date.
*Revision:* named ranges ("2020", "2022", "2023 embargo", "2026", "Weekly series
from July 2022", "All") plus the brush. They are content, not chrome.

**K10. The floating tooltip card is the only route to a value**, and a floating
card is a shadowed rounded box. Generic.
*Revision:* a fixed readout line above the plot, plain text, updated by pointer
or arrow keys. Every value also in the table.

**K11. Reconstructed and printed data told apart by a caption, least defended
weeks by a footnote.** Wrong for this content. The Gate 1 self audit's point was
that a weakness described only in prose is a weakness nobody meets.
*Revision:* printed weeks as square marks on the line; the six oldest weeks
under a hatch, the only hatch on the site; the newest weeks with no second
chart yet under an axis bracket. Part 3 section 2.

**K12. A structural break drawn on the MBR.** Wrong. There is none (Part 0.9).
The first pass would have invented one to satisfy SPEC.md section 4.3.
*Revision:* breaks only where they exist: gas 2015-04, capacity 2017-01 and
2026-01, OPEC gasoline 2004 to 2013. The Method view says why the MBR has none.

### Seasonal

**K13. "5 year range" labels a range that does not exist.** Wrong for this
content (Part 0.3). Tooltip `n_years` is the depth buried where nobody reads it.
*Revision:* no band at all. Three or four prior years are drawn as three or four
thin lines, each labelled with its year at its end. The depth is countable on the
chart: the 2022 line starts in July because the data does. The range figures are
said in the panel sentence. A min to max band over four points implies a
distribution, and a mean line over three is not a statistic worth a line.

**K14. The exclude toggle offers 2020 and 2026.** Wrong. 2020 is not in the
weekly range and 2026 is the current year; both checkboxes would do nothing.
*Revision:* the toggle lists only the episode years actually present in the
range, today "Leave out 2022". On the monthly OPEC seasonal view, which has 25
years, all three are offered.

**K15. The current line in the accent, again the whole series.** Generic.
*Revision:* current line in the product's ink style, accent on its latest point.

### Waterfall

**K16. Green and red.** Generic, the most dashboard thing in the plan. The
palette has no green, and the brique accent is a red, so a red negative bar would
read as the accent's "the one thing that matters".
*Revision:* positive steps solid ink, negative steps outlined ink with no fill,
the sign printed on every figure. No hue carries sign.

**K17. The residual as grey "Other".** Wrong for this content, and it is the
tidying the Gate 2 self audit predicted and said must not be allowed. Grey says
"less important"; the residual is larger than the gasoline line.
*Revision:* the residual is a full weight row named "Everything the two cracks do
not price", with its contents listed and the covered yield, 46.8 percent, said
beside it, plus the historical fact that it is negative in 132 of 134 months.

**K18. The gas step labelled "Gas".** Wrong, and dangerous: it re-states the
double count Gate 2 finding 1 removed from the engine. The MBR is already after
gas.
*Revision:* the step is "Extra gas at this study's intensity", with both
intensities printed. Part 3 section 4.

**K19. Vertical columns.** Generic. Labels under columns have to be abbreviated
or rotated, and at 375 px a six column waterfall has 50 px per bar.
*Revision:* horizontal, one row per line, which makes the waterfall a real table
with a bar cell. It then needs no separate table alternative.

### Tables

**K20. Significance stars.** Generic regression table habit, and here harmful:
t 2.00 gets a star and t 1.98 does not, when those are the same finding.
*Revision:* no stars. Intervals drawn.

**K21. Sorting the horse race by RMSE and bolding the lowest.** Wrong for this
content. It announces a winner the test cannot support (Part 0.6).
*Revision:* fixed order A, B, C as SPEC.md section 6.3 names them, no bold, no
accent on any row, and a power strip per pair. Part 3 section 5.

**K22. The interval as bracketed text.** Generic, and it buries the one visual
fact the Runs section exists for.
*Revision:* an interval strip in every response row, zero rule in the accent,
lower end printed beside it.

**K23. "n/a" in `--text-dim` for unidentified.** Wrong twice. "n/a" says the data
is missing when the finding is that the data does not identify a level; and
`--text-dim` is 2.54, unreadable.
*Revision:* the word "unidentified" in `--text`, followed by the reason sentence
and the percentile fallback.

**K24. Leading with the 230.4 model because it clears zero.** Wrong: that is
choosing the headline by its result, which SPEC.md section 6.6 forbids in
spirit. SPEC.md section 6.1's primary equation is the capacity one.
*Revision:* both rows, the SPEC 6.1 capacity model first, with the measured
reason they differ printed under the table.

### Typography, themes, motion, accessibility, charts

**K25. JetBrains Mono for column headers, nav, axis titles and verdict figures.**
Copied from the LME sibling, which is a sibling habit rather than this brief.
SPEC.md section 0.2 says mono is for figures in tables and on axes only, never
labels.
*Revision:* mono only for tabular figures and tick values. Headers, nav, axis
titles, end labels and figures inside sentences are Figtree or Fraunces with
`font-variant-numeric: tabular-nums lining-nums`. This is a declared departure
from the LME sibling.

**K26. Copying the portfolio's nav and body rules.** Imports glassmorphism
(`backdrop-filter`), a noise overlay (`body::after` grain), uppercase eyebrows and
reveal animations (Part 0.11).
*Revision:* copy the tokens verbatim, copy no rule except `:focus-visible` and the
reduced motion block. `--grain-opacity` and the three shadow tokens exist in
`tokens.css` and are referenced nowhere.

**K27. `--accent` as text in dark.** 3.79, fails.
*Revision:* an accent figure or label uses `--accent-bright` in dark (5.15);
marks keep `--accent`.

**K28. Chart draw in, figure crossfade.** Generic. Opening a section is an
action, but a line drawing itself shows nothing that changed. A crossfaded figure
shows intermediate values no artifact produced (SPEC.md section 2 rule 2).
*Revision:* deleted. Motion list in Part 3 section 8.

**K29. "Contrast passes AA", asserted.** Generic. Part 0.10 shows two tokens
failing.
*Revision:* the measured table, and `--text-dim` banned from anything carrying
meaning.

**K30. The portfolio toggle applies the theme on `DOMContentLoaded`**, so a
visitor who chose dark sees light first. `data-theme="light"` in `index.html`
removes the flash only for light visitors.
*Revision:* the same mechanism plus a four line inline script in `head`, before
the stylesheets, reading `nc-theme` inside `try`. A declared addition.

**K31. "SVG by hand, because the LME sibling did."** Not a justification, and
wrong on the facts: a sibling does vendor a library, d3 (Part 0.12). SPEC.md
section 8 says use what the siblings vendor first.
*Revision:* the decision is argued against d3 in Part 3 section 10.

### What survived

The item 6 decision to vendor the sibling's font files, the `aria-expanded`
pattern, the per chart table, a NaN breaking the line, and the density budget.
Thirty one findings, twenty one of them generic habits (K2, K3, K4, K5, K8, K9,
K10, K13, K15, K16, K19, K20, K21, K22, K25, K26, K28, K29, K31 and the parts of
K11 and K17 that were caption and colour reflexes). The rest were the plan not
knowing its own data.

### The banned list, checked against Part 3

Superseded by Part 6 section B, which reads the list literally and adds the near
relatives this table did not look for.

| Banned | Where it could have crept in | Part 3 |
|---|---|---|
| all caps labels | table headers, axis titles, portfolio `.eyebrow` | sentence case everywhere, no `text-transform`, no positive `letter-spacing` on any label |
| eyebrow labels above headings | "This month" over the verdict, "Section" over headers | none. The verdict is the `h1`; dates sit under it |
| meta strings joined with middle dots | the date line; the portfolio's own `<title>` uses them | dates are a `dl`; `<title>` joined with a comma |
| arrows appended to buttons or links | section chevrons, "Open in History" links, sort arrows | "Show" and "Hide" words; plain link text; no sorting UI. No U+2191 or U+2193 anywhere, which also avoids the Fraunces gap |
| glassmorphism | the sticky header | solid `--bg`, no `backdrop-filter` |
| noise overlays | portfolio `body::after` | not copied |
| gradient washes | band fills, header | no gradients; fills are one flat `color-mix` of a token |
| heavy shadows | tooltip card, open section | no `box-shadow` anywhere; shadow tokens unreferenced |
| the same rounded card for every block | sections, charts, tables | no cards. Blocks are separated by a hairline and space; no `border-radius` except the inherited focus ring's 2px |
| watermarks | "reconstructed" stamped across the weekly chart | reconstruction marked by marks and a sentence, never text over the plot |
| AI tags | "generated" badges, sparkle icons | none |

---

## Part 3. The settled specification

### 1. Now

**Layout, top to bottom.** Header; verdict `h1`; the data dates as a list of
sentences; four sections. Content column `--container` (1280px) with `--gutter`;
the verdict measure capped at 34em.

**Header**, 56px, solid `--bg`, hairline `--border` below, not sticky. Left: the
site name "NWE crack spread study", Figtree 600 `--fs-body-s`, a link to `#/now`.
Then the nav: Now, History, Model, Runs and crude demand, Events, Method, Figtree
500 `--fs-body-s` in `--text-muted`, current view in `--text` with
`aria-current="page"` and a 2px `--text` underline. Right: the theme toggle.
Below 768px the header is two rows: name and toggle, then the nav as a wrapping
row (`flex-wrap`, 16px column gap, 4px row gap). **The nav label keeps the full
words "Runs and crude demand" at every width** (S20): it is the only place
"crude demand" is on screen above the fold at 375 px before any scrolling, so
it is not shortened to "Runs". Estimated two nav lines at 375 px, header about
120px. No hamburger, no horizontally scrolling nav.

**The verdict** is one sentence, Fraunces 400, `--fs-display-s` (22px to 28px)
above 480px and `--fs-body-l` (17px to 19px) at 480px and below (S21), line
height 1.3, `--text`, figures tabular lining. It arrives from `now.json` as an
array of segments, text and value, each value naming its field, so a test can
assert every figure in the sentence came from one. Clauses, in order:

| Clause | Field(s) | Template when | Wording |
|---|---|---|---|
| margin | `margin_month`, `mbr_usd_bbl` | always | "On the ministry's Rotterdam measure, refiners' gross margin after the ministry's gas allowance was {mbr} $/bbl in {margin_month}," (Part 7, C10) |
| rank | `percentile_rank`, `percentile_observations` | rank equals n | "the most in {n} months;" |
| | | rank equals 1 | "the least in {n} months;" |
| | | otherwise | "more than in {rank minus 1} of {n} months;" |
| carrier | `carrier_name`, `carrier_contribution_usd_bbl`, `crack_month` | carrier present | "{carrier} carried {contribution} of it," (and "on the prices of {crack_month}" only if that month is not the margin month) |
| | | carrier absent | "no product split of that month says which crack carried it," |
| runs | `threshold_identified`, `headroom_usd_bbl` | unidentified | "and this sample cannot say whether runs have room to rise." |
| | | identified | "and runs sit {headroom} $/bbl above the level at which they get cut." |

Today it reads (Part 7, C1, C9 and C10, `data/now.json`): "On the ministry's
Rotterdam measure, refiners' gross margin after the ministry's gas allowance was
38.05 $/bbl in August 2026, the most in 120 months; gasoil carried 27.00 of it,
and this sample cannot say whether runs have room to rise." Forty words, four
clauses, the month once. The trailing window ends at the margin month, so "the most in
120 months" needs no second date, and the carrier is split on the same month's
printed prices, so it needs none either.

**Corrected at Gate 4, Part 7, C9.** The sentence first carried a fifth clause,
"or 34.96 at the average US refinery's gas use, 3.2 times the ministry's", and
said the month three times. It ran to about 65 words and nobody says it out
loud. The 34.96 figure and the ratio moved to the "Refining margin and gas"
section, where the wedge that produces them is drawn: `margin-stack.json`
`study_margin_segments`, "At the average US refinery's gas use, 3.2 times the
ministry's, the same barrel would have kept 34.96 $/bbl in August 2026 rather
than 38.05; the gap is the extra gas, −3.09 $/bbl", and the wedge row's second
line now carries the ratio too.

**Corrected at Gate 4, Part 7, C10.** The paragraph below defended "kept" and
"its own", and both were wrong: "kept" claims earnings on a margin that nets out
only energy, and "its" reads as the refiner's gas. It is kept for the record.

Why this wording (S13, C9): "Rotterdam refiners made" claimed realised earnings
for an indicator the ministry computes on a notional slate. "A refiner kept ...
after its own gas allowance" is what the MBR is, net of gas at the margin's own
0.0659 MMBtu/bbl, and "its own" is the fewest words that say the gas assumption
is the ministry's rather than a refinery's. The EIA's all US refinery average,
0.21217, and the ratio 3.22 (`docs/methodology.md`) that says how far it sits
from the ministry's assumption, are in the margin section. "The last month
with product prices" was also wrong on this page, because weekly product cracks
run to September.

**Data dates**, directly under the verdict: a `ul` of four sentences, one per
source date, never one line, never a `dl` (S5: a term and description pair
stacks into a label over a value below 600px, which is the metric with a label
above it that SPEC.md section 7.3 forbids). Figtree 400 `--fs-meta`, `--text`,
line height 1.45, 2px between items. Each sentence is assembled from the
manifest:

```
Margins run to August 2026 and are final; the monthly prices that split them are final in the ministry's note of 4 September 2026.
Weekly cracks run to the week of 4 September 2026, read off the ministry's weekly chart; last fetched on {fetched_at, date and UTC time}.
Refinery runs stop at June 2026 and are provisional; JODI revises recent months.
```

Three rows, not four (Part 7, C2). The fourth row, "Monthly product quotations
stop at February 2026", described the OPEC path, which the Now view no longer
uses; the OPEC hole stays in the Provenance summary and the manual steps. "The
scheduled job last fetched it" became "last fetched on", because no scheduled
job exists before Gate 5 and the fetch time is a manual run's.

The weekly date is its own row (S19). The brief says three data dates never
merged; the weekly reconstruction is a fourth date, and the "tracked" clause of
SPEC.md section 1 needs it and its fetch time on the landing view at every width,
not only inside a section header. The status words, final and provisional, come
from the manifest (`provisional_from`, manual step `outstanding`), never from
copy, and are set in Figtree 500, the same colour as the sentence. No pill, no
badge, no muted tone for the status.

**Four sections.** Each is an `h2` containing a full width `button` with
`aria-expanded` and `aria-controls`, min height 56px (44px touch minimum met),
hairline `--border` above. Inside the button: the name, Figtree 600
`--fs-body`; the summary sentence, Figtree 400 `--fs-body-s` `--text-muted`
(4.90 light, 7.54 dark), wrapping to a second line when it must; and at the
right edge the word "Show" or "Hide", Figtree 500 `--fs-meta`.

**Section names carry the words of the CV line** (S20). SPEC.md section 7.2 names
them Cracks, Margin stack, Runs and crude demand, Provenance. A sceptic scanning
for "run economics" finds none of those, and "margin stack" is a term of this
study, not of the desk. The names shipped, flagged for the owner as a deliberate
departure from the spec's working labels:

- **Gasoil and gasoline cracks.** "Gasoil {g} and gasoline {s} $/bbl in the
  week to {week}, read off the ministry's weekly chart; both above the same week
  in each of the {n_years} years the weekly series covers." Branches: "inside
  the range of the same week" and "below" when true, per product. Today n_years
  is four for week 36 (S14: "above every same week since 2022" hid how few years
  that is).
- **Refining margin and gas.** "How the cracks build the ministry's NWE
  refining margin in {margin_month}, on the ministry's own prices for that month,
  and what it is worth at the average US refinery's gas use." (Part 7, C1: one
  month, not two.) Inside, under the waterfall, the sentence the verdict gave
  up (C9): "At the average US refinery's gas use, {ratio} times the ministry's,
  the same barrel would have kept {study} $/bbl in {margin_month} rather than
  {mbr}; the gap is the extra gas, {wedge} $/bbl."
- **Run economics and crude demand.** "No level at which runs get cut can be
  identified. Crude runs move {capacity_kb_d} kb/d per 10 $/bbl of margin on
  the planned model, t {capacity_t}, and {fallback_kb_d} on a model with a trend,
  t {fallback_t}." The negative finding leads, the planned model comes before
  the one that clears zero (S16), and both t values are said so neither figure
  travels without its strength.
- **Provenance.** "None of the {n} series failed or went stale at the last
  fetch, {fetched_at}; {m} manual step is outstanding: the OPEC archive stops, so
  the monthly OPEC history of the cracks ends at February 2026." With failures it
  opens "{k} of {n} series failed or went stale". Part 7, C3: the OPEC gap no
  longer stops the Now view, so it is stated as what it costs now, the monthly
  history, and follows the failure count rather than leading. S2: the first
  version led with "20 series fetched", a count that is the provenance equivalent
  of a vanity metric and put the one real gap after it.

Sections open independently, in place, pushing what follows down. Open state is
in the hash, `#/now?open=cracks,runs`, so an open section is linkable. No
section is open on first load.

**Section contents.** Blocks inside an open section are separated by 24px of
space and their own sentence heading, never by a rule, a tint or a frame (S9):
the hairline belongs to the four section rows and to table headers only.

- Cracks: section 3's two seasonal panels.
- Refining margin and gas: section 4's waterfall and, under it, one sentence:
  "Month to month the gasoil crack tracks the official margin far more closely
  than gasoline does, R2 {g} against {s}."
- Run economics and crude demand, in this order (S17): **first** the headroom
  sentence of section 5, because SPEC.md section 1 puts "today's headroom" in the
  run economics clause and the word unidentified has to sit where that number
  would; then the response strip and table of section 5; then latest utilisation
  for {runs_month} against what the margin implies, as a four row table of the
  post break months with the sentence from `break_2026`, each provisional month's
  row ending in the word "provisional" (S18); then the link "Open Runs and crude
  demand".
- Provenance: the manifest table (section 5 table rules, column order in Part 6
  section F), the two manual steps verbatim, failed and stale rows first.
  **Corrected at Gate 4, Part 7, C12:** not verbatim. The page prints a reader
  layer the export writes, with a Provisional column (C13).

**First ten seconds, 1440 x 900** (about 780px of viewport). Header 56, verdict
three lines at 28px about 110, padding 56, dates four rows 80, four headers 4 x
64 = 256: about 560px. Everything in SPEC.md section 1's table is above the fold:

| Clause | Seen in |
|---|---|
| tracked | the dates list, "Weekly cracks run to the week of 4 September 2026 ... last fetched"; the cracks header |
| NWE refining margins | the verdict's first clause; the "Refining margin and gas" section name and its "NWE refining margin" summary |
| across gasoil and gasoline cracks | the "Gasoil and gasoline cracks" section name with both values; the verdict's carrier clause |
| run economics | the "Run economics and crude demand" section name; its first sentence "No level at which runs get cut can be identified"; "gross margin after the ministry's gas allowance" and "runs have room to rise" in the verdict (C10); the 34.96 at the US gas use in the margin section (C9) |
| linked to crude demand | the same section name; kb/d per 10 $/bbl for both models with t in its summary; the nav's "Runs and crude demand" |

**375 x 812** (about 700px of viewport), re-estimated (S21). At 480px and below
three settings change, all stated here: the verdict at `--fs-body-l`, the dates
list at line height 1.3, the section summaries at `--fs-meta`. Header two rows
120; verdict at 17px Fraunces, about 37 characters a line on 335px, nine lines
at 22px, about 200; gap 20; dates four sentences, about nine lines at 17px, 155;
gap 24; section rows about 76px each with a two line summary. Cracks row from
519, margin row from 595, the "Run economics and crude demand" name at about 671
to 693, **just inside the fold, with no margin to spare**. "Crude demand" is also
above the fold in the nav and "after gas" in the verdict. The summary of that
section, with the kb/d figures, needs a scroll. **This is an estimate and the
shell measures it** at 375 x 812 with the fonts loaded. If the section name falls
below the fold, the fix is shortening the Cracks and Margin summaries to one
line at that width by rewording their templates; never hiding a summary,
dropping a date or shrinking type below `--fs-meta`.

### 2. Time series (History)

**Plot surface.** No frame, no background fill. Height 360px desktop, 240px below
768px. Plot type sizes are CSS pixels at every width: redraw on width change (the
LME `onWidthChange` pattern), never scale a viewBox.

**Axes.** y ticks on the left, JetBrains Mono 400 `--fs-caption`, `--text-muted`,
right aligned, 4 to 6 ticks on a 1, 2, 5 ladder, unit said once in the axis title
above the ticks ("$/bbl", Figtree 500 `--fs-caption`, sentence case). x axis:
a label at each January, the year, Mono `--fs-caption`; below 768px every second
year when labels would sit closer than 48px. Unlabelled 4px ticks at each July on
weekly spans only.

**Gridlines.** Horizontal only, at y ticks, 1px `--border`, deliberately below
3.0 (1.24 light, 1.27 dark) because no value is read from a gridline alone. **The
zero line is 1px `--text-muted`** (4.90, 7.54), not `--border-strong` (S24: 1.49
and 1.64 fail 3.0, and zero is a value here, a negative margin being a real
state), drawn whenever zero is in the domain.

**Products without colour** (S10). Gasoil: solid, 1.75px, `--text`. Gasoline:
dashed 6 on 4, 1.75px, `--text`. **Both in the same ink.** The dash pattern and
the end label are the product's identity everywhere on the site; tone is not.
The first version set gasoline in `--text-muted`, the primary and secondary
series habit of every dashboard, which on this page also greyed out the weaker
leg as if it were the less important one. Gasoline's weakness is a finding (R2
0.551 against 0.855) and is said in a sentence and shown by the shared y domain,
not by a paler line. `--text-muted` is freed for context marks: prior years,
cursor, break rules.

**End labels.** At the right end of each line, 8px after its last point: the
product name, Figtree 500 `--fs-meta` `--text`, then its last value, Figtree 400
tabular. If the two labels would overlap vertically (less than 18px apart), push
them apart symmetrically and draw a 1px `--text-muted` leader to each point.
Labels carry a 3px `--bg` halo (`paint-order: stroke`) where they cross a line.
Where a line ends before the plot does (the monthly OPEC cracks stop at 2026-02
while the margin runs to 2026-08), the label sits at the line's own end and names
the month: "Gasoil, Feb 2026, 7.96". No legend anywhere.

**Accent.** One per chart. Weekly cracks: a filled 4px radius dot on each line at
the latest week, with a **2px `--bg` ring** around it, and a 1px `--accent` rule
from the lower dot to the x axis. The ring is not decoration (S25): in light the
accent against the ink line it sits on measures 2.14, so without the ring the dot
reads as a blob at the end of the line rather than a mark; the ring separates it
by the paper's 17.01 on both sides. Monthly margin: the August 2026 point, same
ring, and its end label figure. Accent text uses `--accent` in light (7.96) and
`--accent-bright` in dark (5.15), never `--accent` as dark text (3.79).

**Events.** A 1px solid `--border-strong` hairline across the plot height, with a
4px `--text-muted` tick at its top edge, so the position is findable at 4.90
while the full height line stays quiet. Its label is a real `button` in an HTML
lane 20px tall above the plot, Figtree 500 `--fs-caption`, short names from
`events.json` ("Invasion", "Diesel record", "Refinery strikes", "Crude embargo",
"Product embargo", "Strikes on Iran", "Stock release", "Ceasefire"). Colliding
labels (2022 has four inside eight months, 2026 three inside six weeks) drop to
numbers in the lane and are listed by number under the chart. Activating one
opens `#/events/{id}`.

**Structural breaks.** Drawn where they exist (Part 0.9). The series path is
split at the break into two paths that never join, and a 1px dashed
`--text-muted` rule crosses the plot with its label in the lane: "Gas series
becomes TTF", "Capacity figure steps". A break differs from an event by the split
line and the dashed rule; an event never splits a line. The OPEC gasoline column
caveat is a span, not a date: a bracket in the evidence rail over 2004 to 2013,
"Not one product across these years".

**NaN.** The path is built from runs of finite values, one `path` per run. A
finite point with NaN on both sides is drawn as a 1.5px radius dot so it cannot
vanish. Under each gap, on the x axis baseline, a 1px dotted `--text-muted`
segment spanning the gap. The readout for a week in a gap says "No value for
{date}: {reason from manifest gaps}". Never a line across a gap, never a zero.

**Reconstructed against printed.** The reconstructed series is the line. The 18
printed weeks are 5px squares, filled `--bg`, 1.5px `--text` stroke, on top of
the line at their printed value, never joined. One sentence under the chart,
Figtree `--fs-meta`, `--text`: "Lines are read off the ministry's weekly chart.
Where two notes plot the same week they agree to {pair_mean_usd_bbl} $/bbl on
average and {pair_worst_usd_bbl} at worst; squares are figures the ministry
printed." S29: the first version quoted 0.30 and 1.68 in $/t beside a chart in
$/bbl, which a reader cannot put against the line. The export converts per
product with the config factors (gasoil 7.45 bbl/t) and names the unit.

**The evidence rail** (S12). A 14px rail directly under the x axis, the one place
on a chart where the weight of evidence is drawn. Rows come from the
`evidence_class` column, never from dates in the frontend:

- `single_geometry_oldest`, the six weeks from 2022-07-01: a 45 degree hatch,
  1px `--text-muted` strokes at 4px pitch, minimum 6px wide at any zoom, labelled
  in the event lane "Least defended weeks". **This is the only hatch on the
  site, and wherever it appears it means these six weeks.** Its sentence, under
  the chart, only when the six weeks are in view: "The six oldest weeks sit where
  a slow bend in the ministry's chart would do most harm and no second chart
  checks them; a bend the checks cannot see would move them by about
  {oldest_tilt_usd_bbl} $/bbl." Today about 10 (`docs/methodology.md`, the tilt
  test at 10 points).
- `single_geometry_newest`, the weeks with no second chart yet, one of them
  today, from 2026-09-18: a 1px
  `--text-muted` bracket, "No second chart yet". The newest end is where the
  calibration anchors sit, so it is marked but not hatched: hatching it would
  make the best anchored weeks look like the worst.
- `cross_checked`: nothing drawn. Absence of a mark means two or more charts
  agree.

The first version drew the hatch behind the lines (S12). A shaded zone behind a
series is the "forecast region" of any dashboard, it muddies a dashed gasoline
line at 1.49 contrast, and at `--text-muted` strength it would bury the line.
Under the axis it passes 3.0 and touches nothing.

**Readout.** A single line above the plot, Figtree `--fs-meta`, tabular figures:
"Week to 4 September 2026: gasoil 91.14, gasoline 65.91, Brent 96.01 $/bbl.
Read off the chart, no second chart yet." The evidence clause comes from the
row's class and printed flag ("printed by the ministry", "checked against a
second chart", "least defended week"), which is what makes this readout belong
to this series rather than to any crosshair. Pointer moves it; when the plot
group has focus, left and right arrow keys step by one observation, Home and End
jump. A 1px `--text-muted` vertical cursor. No floating card.

**Ranges.** Above the plot, a row of text buttons: "All", "Weekly series from
July 2022", "2020", "2022", "2023 embargo", "2026". Their windows come from
`events.json` episode spans. The pressed range is `aria-pressed` and shown by a
2px `--text` underline plus weight 600, never by a fill.

**The brush sits on a coverage strip, not on a miniature of the chart** (S1).
The 48px overview strip with a thumbnail of the series under a draggable window
is the stock chart widget every finance dashboard ships. Here the strip under the
plot draws what the three data dates and the weekly date mean: four 1px lanes,
one per source, each a solid 3px bar where that source has data and nothing where
it does not, end labelled like a series ("Official margin, to Aug 2026", "Monthly
product quotations, to Feb 2026", "Weekly cracks, from Jul 2022 to 4 Sep 2026",
"Refinery runs, to Jun 2026"). A provisional tail is a 1px line after the 3px bar
with the word "provisional" at its end. Gaps are breaks in the bar. The brush
window is a 1px `--text` outline over all four lanes with 44px tall invisible
handles. Dragging it changes the plot; two native `input type="range"` controls
are its keyboard equivalent. Lanes are 12px apart, so the strip is about 64px:
16px more than the thumbnail it replaces, and it answers "why does this line stop
here" before anyone asks.

**Empty chart** (S34). The plot area holds one sentence, Figtree `--fs-body-s`,
`--text`: "No gasoline crack to draw. {series} failed on {fetched_at, date and
UTC time}; the last good copy ends {last_date}. Reload after the next scheduled
fetch, or read the Provenance section." From the manifest. The first version
said what failed and not what to do, half of what SPEC.md section 7.3 asks.

**Product toggle** (S4). Two native checkboxes with visible labels, "Gasoil" and
"Gasoline", both checked by default, the second disabled while the first is
unchecked and the other way round, so at least one line stays. The first version
used `aria-pressed` chips whose state was a fill, the filter pill of every
dashboard; a checkbox shows its state by shape, which the brief's "without colour"
asks for anyway.

### 3. Seasonal

**Now, Cracks section.** Two panels, gasoil then gasoline, side by side above
768px and stacked below, sharing one y domain so the weaker gasoline leg looks
weaker by its level, not by a paler ink. 220px tall each plus two 14px rails.

Each panel:

- A sentence heading, Figtree 500 `--fs-body-s` `--text`: "Gasoil, 91.14 $/bbl
  in the week to 4 September 2026, read off the ministry's chart, 32.93 above
  the highest same week of the {n_years} years before it." (S14, S15: the heading
  carries the depth and the reconstruction, because it is the sentence people
  read and the rails are the marks they may not.)
- **Prior years as lines, not a band.** One line per prior year present in
  `seasonal_weekly`, **1px solid `--text-muted`** (S24: the first version used
  `--border-strong`, 1.49 light and 1.64 dark, for lines that are now the whole
  comparison, since there is no band; they carry data and must pass 3.0), each
  labelled with its year at its right end in Figtree `--fs-caption`
  `--text-muted`, with a `--text-muted` leader when crowded. The 2022 line starts
  in July because the data does, so the depth is countable on the chart itself.
- **Current year** 2px `--text` in the product's dash pattern (gasoil solid,
  gasoline dashed 6 on 4). It is told from the prior years by width, by ink
  (17.01 against 4.90 in light) and by its end label "2026, 91.14"; for gasoline
  also by the dash. Accent dot, 4px radius with a 2px `--bg` ring, on its latest
  week.
- **Depth rail.** A 14px rail under the x axis with brackets over runs of equal
  `n_years`: "3 prior years" over weeks 1 to 26, "4 prior years" over 27 to 52,
  "none" over week 53. From the field per week, never computed from dates.
- **Evidence rail**, under the depth rail, the same marks as History: the hatch
  under weeks 27 to 32 labelled "2022, least defended weeks", because those
  weeks of the 2022 prior line are the six `single_geometry_oldest` rows; the
  bracket "2026, no second chart yet" under the current year's newest weeks.
- **The range said plainly** under the panel, Figtree `--fs-meta` `--text`:
  "The same week ranged from 15.44 to 58.21 in 2022 to 2025. Only three or four
  prior years exist, because the weekly series starts in July 2022, so this is
  not a five year range." The words "five year" appear once on the site, here,
  in a negative sentence, because a desk reader will look for that range and
  should be told it is absent rather than left to wonder (S15). No band, no
  apology word.
- **Toggle** (S4): episode years that are actually present in the prior lines,
  from the field, today one button. It reads "Leave out 2022"; pressed, its text
  becomes "Put 2022 back", with `aria-pressed` alongside. The state is in the
  words, not in a fill. Pressing it removes the line and its hatch, updates the
  depth rail ("2 prior years", "3 prior years") and the range sentence.

**History, seasonal sub-view.** The monthly OPEC profile, 25 years, each year
demeaned: month on x, $/bbl on y. Prior years as 1px `--border-strong`
hairlines: at 25 lines they are a mass, not a set of readable series, and no
value is read from one, so they are exempt from 3.0 the way gridlines are and
say so in the chart's `desc`. The median as a 1.5px `--text` line, end labelled
"Median of 25 years"; the current year in the product's dash at 2px `--text`.
Under gasoline: "May to September sits 4.78 $/bbl above the rest of the year,
t 4.64, positive in 22 of 25 years." (verified in `docs/methodology.md`, the
seasonality table). Under gasoil, the desk's November to March window as a
bracket under the axis labelled "The winter window desks quote", and the
sentence: "It does not hold here, t -0.59 on 24 winters. The strongest months are
October, +3.00, and November, +2.09." Open question 40 recommends both the failed
window and the measured shape; this draws both, the failed window in the same
ink and size as the measured one. Here the toggle offers the episode years
present among the 25 prior years, from the field (S33): today expected to be
2020, 2022 and 2023. The first version listed 2026, the current year on that
panel, a button that would remove nothing.

The weekly and monthly layers are never on one panel (open question 41: they
quote different products).

### 4. The waterfall

**CORRECTED AT GATE 4, Part 7, C1. ONE BLOCK, AUGUST 2026, not two.** The two
block form below was the answer to a landing month that could not be decomposed,
and the landing month can be. The Now view draws one block for the margin month,
from `data/margin-stack.json`: five product rows ordered by contribution, the
residual, the official margin total with the accent, the wedge, the total at this
study's gas use. The February block, its rows and "Not split, monthly product
quotations stop at February 2026" are gone from Now; February on the OPEC path
may return on History. Everything else in this section (columns, marks, small
steps, the residual's weight, the wedge row, 600px and below) applies to the one
block. The scale sentence reads "On one scale, {low} to {high} $/bbl", with
`scale.low_usd_bbl` and `scale.high_usd_bbl` from the artifact. The residual's
history sentence is now "On the ministry's own monthly prices this line has been
negative in {negative} of the {decomposed} months a note printed final prices
for", today 4 of 4; the OPEC "132 of 134" belongs to History with the OPEC path.
The residual's second line: "The cracks cover {covered} percent of the barrel;
everything else, and the ministry's gas, freight and insurance costs, adds up to
this line", today 70.9 percent, and its list names butane, export gasoline,
naphtha, propane and sulphur. The text of the superseded form follows, kept for
the record.

**Form, as first specified.** A `table`, one row per line, horizontal bars in a cell. Two month
blocks side by side at 1024px and above, stacked below, **on one shared x scale**
declared in a sentence over them: "Both months on one scale, 0 to 40 $/bbl." The
domain comes from the data (the largest running total and the lowest, widened to
the 1, 2, 5 ladder, zero always inside), not from a literal. A zero rule, 1px
`--text-muted`, runs the height of each block.

**Columns.** Line name (Figtree 400 `--fs-body-s`, left, with an optional second
line in `--fs-meta` `--text-muted`), bar (flexible, min 160px), figure (JetBrains
Mono 400 `--fs-meta`, right, `9ch`, sign always printed on steps, hyphen minus in
mono so a copied value pastes into a spreadsheet). Rows 32px.

**February 2026 block**, heading "February 2026, the last month the margin can be
split by product":

| Row | Kind | Figure |
|---|---|---|
| Gasoil crack times its yield | step | +7.96 |
| Gasoline crack times its yield | step | +2.22 |
| Everything the two cracks do not price | step, the residual | -3.68 |
| Official margin, the ministry's MBR | total | 6.50 |
| Extra gas at the average US refinery's use | step | -1.64 |
| At that gas use | total | 4.86 |

**August 2026 block**, heading "August 2026, the latest margin": the gasoil and
gasoline rows are present, their bar cells hold the text "Not split, monthly
product quotations stop at February 2026", Figtree `--fs-meta` `--text`, figure
cell empty with that text as its accessible name; the residual row reads "Cannot
be separated from the products this month"; then official margin 38.05, extra
gas -3.09, at that gas use 34.96. At 1024px and above rows align across the two
blocks so each line reads across.

**Marks.** Step bars float from the running total. Positive step: solid fill
`--text`. Negative step: no fill, 1.5px `--text` stroke inset. Totals: solid fill
`--text` from zero, row set in Figtree 600 and figure in Mono 600, a 1px
`--border-strong` rule above. **The accent goes on one total only, the August 2026
official margin** (S3): fill `--accent` (7.96 light, 3.79 dark, both above 3.0 as
a mark) and its figure in `--accent` in light, `--accent-bright` in dark. The
first version put the accent on both official margin totals, two accents in one
figure, which is the accent as a style for "total" rather than the one thing.
The one thing is the latest published margin; February's total is ink. No text
is ever set on a filled bar, so no pairing of text on `--text` or `--accent`
exists. Between consecutive bars a 1px dotted `--border-strong` connector at the
running total, decorative, because the running total is also given by where the
next bar starts. Positive and negative are told apart by fill against outline,
by the printed sign, and by direction from the connector, with colour playing no
part.

**Small steps.** A step narrower than 4px at the current width is drawn as a
5px circle at its running total end, filled `--text` for positive and hollow with
a 1.5px `--text` stroke for negative, the same fill against outline rule as the
bars, and its figure carries the size. A step is
never dropped for being small; on the shared scale at 375 px one dollar is about
6.4px, so a move under 0.60 $/bbl takes this form.

**The residual, larger than a product line, without looking like a mistake.**
Same weight, same ink, same row height as the products; no grey, no italic, no
"other". Its second line (S30): "Eight products the study cannot price, from
fuel oil to naphtha, and the ministry's cost lines. The two cracks cover {covered
yield} percent of the barrel; everything else adds up to this line." The first
version said the cracks "add up to more than the margin" because they price 46.8
percent of the barrel, a causal "so" the data does not show; coverage and sign
are two facts and are now said as two. Under the table, one sentence from the
decomposition history: "This line has been negative in 132 of 134 months." The
row name is a button that opens the list of `unattributed_products` in place.

**The wedge row's second line:** "0.212 MMBtu/bbl here against the ministry's
0.066, at {gas} $/MMBtu." The Method view carries the derivation. The word "minus
gas" appears nowhere, and no row is labelled "gas" alone: the MBR is already
after gas.

**At 600px and below** (S31). Three columns cannot fit 335px: the name column
would be about 95px and "Everything the two cracks do not price" with its second
line would run to seven lines. Each row becomes two lines inside the same `tr`:
the name, and its second line, across the full width; under it the bar track,
335px less the figure, about 255px, and the figure at its right. This is CSS grid
on the `tr` with `role="table"`, `row`, `rowheader` and `cell` set explicitly in
the markup, because some engines drop table semantics when a table part changes
`display`. The two blocks stack, February first, then August, still on one scale,
with the scale sentence above the first. The table never scrolls sideways and
never becomes a card.

**On the Model view** the same table recomputes live; bar geometry tweens
(section 8), figures swap instantly, and the August block is replaced by the
preset month. On the Model view the accent goes on the preset month's official
margin total.

### 5. Regression and horse race tables

**Table rules, site wide.** Figures JetBrains Mono 400 `--fs-meta`, right
aligned, sign always printed, fixed decimals per unit from the artifact ($/bbl 2,
kb/d 1, t 2, R2 3, power 3, pp 1 (Part 7, C14; it was 3)). Labels Figtree 400 `--fs-body-s`, left. Column
headers Figtree 500 `--fs-meta` `--text-muted`, sentence case, units in the
header ("kb/d per 10 $/bbl"), no `letter-spacing`. Hairline `--border-strong`
under the header row, `--border` above a total or a note row, none between rows.
No zebra. Rows 32px desktop, 40px below 768px.

**Wide tables** sit in an `overflow-x: auto` container, `max-width: 100%`, with
the first column `position: sticky`, background solid `--bg`, and a 1px
`--border-strong` rule on its right edge. Nothing else signals that a table
scrolls (S6): no shadow on the sticky edge, no fade mask on the container, both of
which are the scroll affordances of every dashboard kit and both of which are on
the banned list in all but name (a heavy shadow, a gradient wash). Instead, below
600px, the table's `caption` ends with the columns that start off screen: "t, R2
and the number of months are to the right." They never become cards.
**Corrected at Gate 4, Part 7, C13:** the caption sits above the scroll box, not
inside it, and names what is off screen at every width, measured.

**Response table** (Now, run economics section; Runs view in full):

| Model | kb/d per 10 $/bbl | Interval | Zero | Share of runs | t | Months |
|---|---|---|---|---|---|---|
| Utilisation of capacity, the planned model | +59.3 | -290.1 to +408.8 | includes zero | +1.1 pct | +0.33 | {nobs} |
| Crude intake with a trend | +230.4 | +5.1 to +455.6 | lower end +5.1, {lower_share} of the interval's width above zero | +4.4 pct | +2.00 | {nobs} |

Order fixed, the planned model first (S16). The interval column prints both
ends. Row labels say what the model is, not "SPEC 6.1", which means nothing on a
public page.

**The interval strip** (min 200px, 24px tall, `aria-hidden`, the columns carry
the values) sits in a column between Interval and Zero at 600px and above. One
shared domain across all rows, from the lowest low to the highest high. A 1.5px
`--accent` zero rule the full row height, the one thing on this chart. The
interval a 2px `--text` line with 6px end ticks; the estimate a filled 4px `--text`
dot with a 2px `--bg` ring where it crosses the zero rule (accent against ink is
2.14 in light). The domain is drawn at its true extent even though it puts the
fallback's lower tick one or two pixels from the rule: that closeness is the
finding, and a domain chosen to separate them would flatter it.

**The Zero column** (S27) replaces "clears zero by 5.1". "Clears" is a pass word;
a reader skims it as "significant". The text now reports the distance and its
size against the interval, `lower_share` exported (today 1.1 percent: 5.1 over
the width 450.5). Nothing decides from a threshold whether that is "nearly";
the figure says it. Figtree 400 `--fs-meta` `--text`, the same weight in both
rows, so "includes zero" is not quieter than the row that does not.

**At 600px and below** (S31) the strips leave the table: a figure directly above
it, the full 335px, one 28px row per model, each labelled at its left end in Figtree
`--fs-meta` ("Planned model", "With a trend"), the accent zero rule through both
rows and stopping at each label line (Part 7, C15).
The strip is the only picture of the run economics finding and it must not sit
behind a sideways scroll. The table under it scrolls with the model name sticky.

Under the table, the measured reason, from `docs/open-questions.md` question 42,
Figtree `--fs-body-s` `--text`: "The capacity figure falls by a step in 2017 and
2026, and the planned model has no trend or closure step to absorb it; adding both
moves its estimate 89 percent of the way to the second."

**Horse race table** (Runs view): rows A, B, C in that order, as SPEC.md section
6.3 names them. Row C's second line: "The official margin re-priced at the
average US refinery's gas use, a substitution explained in Method." Columns:
coefficient (pp per $/bbl), Newey-West SE, t, R2, out of sample RMSE, forecasts.
Horse A's longer sample is a separate row under a note row, never in the race.
No bold, no accent, no ordering by any column, no sort control.

**The power table**, directly under it, one row per pair: pair, observed RMSE gap,
smallest detectable gap, power, a power strip, forecasts needed for 95 percent
power. The observed gap and the smallest detectable gap sit side by side so the
reader sees the first is a fraction of the second. The power strip: 120px, domain
0 to 1, a 1.5px `--accent` tick at the test size (0.050, from the artifact), a
filled 4px `--text` dot with a 2px `--bg` ring at the power. Every dot sits on or
beside the accent tick; that is the picture of a test that cannot tell anything
apart. At 600px and below the power strips move above the table as the interval
strips do.

**"Cannot separate", as a sentence and never as a result.** Above both tables, the
sentence `horse_race_winner` emits, in Figtree `--fs-body` `--text`, the same size
as the section's other lead sentences: "This sample cannot tell the three apart:
power against the gaps it found is 0.050 to 0.121, and 0.050 is the rate at which
the test would report a difference that does not exist." (S26: the first version
said "0.050 is what a coin would give", which is wrong, a coin gives 0.5, and a
wrong analogy on the page's most negative finding is worse than none.) Banned
words in this view, asserted by a test: winner, wins, best, tie, dead heat,
equivalent. Nothing is ranked, so nothing looks like a winner; nothing is marked
equal, so nothing looks like a tie.

**"Unidentified", where a number would sit** (S17, S28). In the run economics
section on Now and at the top of the Runs view, the headroom slot is a paragraph,
not a label and value pair, Figtree `--fs-body` `--text`, with "unidentified" in
500: "Headroom to the level at which runs get cut is unidentified. Take out July
2020 to March 2022 and the slope below the estimated kink changes sign, so the
kink describes one episode rather than a level; its interval, 2.03 to 11.28
$/bbl, also runs to the edge of the range searched." The sign flip leads because
`docs/methodology.md` names it the stronger evidence; an interval alone "sounds
like a wide estimate of something real". Then the fallback, the next paragraph,
same type: "The only reading of today's level this study defends is its rank:
38.05 is the most in the 120 months to August 2026." Same size, weight and colour
as any figure sentence on the page. Never "n/a", never an empty cell, never a
dimmed cell, never smaller than the response figures beside it.

**Threshold scatter** (Runs view): utilisation against the margin series the
threshold search ran on, named from the artifact. Months outside 2020-07 to
2022-03 as hollow 5px circles, 1.5px `--text`; months inside it as filled 6px
squares `--text`, labelled once "July 2020 to March 2022". **Two fits, not one**
(S28): the kink fitted on every month, 1.5px dashed `--text`, end labelled "Every
month, kink at 2.28"; the kink fitted without July 2020 to March 2022, 1.5px
dotted `--text`, end labelled "Without that episode, kink at 9.87". Below their
kinks the two lines slope opposite ways, which is the picture of "unidentified"
that a single dashed fit with an interval never gives. The headline interval 2.03
to 11.28 as a vertical span, flat fill `color-mix(in srgb, var(--text) 6%,
var(--bg))`, **with no text inside it** (S23: `--text-muted` on that fill is 4.34
in light, below 4.5), its right edge a 1px `--text-muted` rule whose label "Edge
of the range searched" sits above the plot in the lane, on `--bg`. **No accent on
this chart**, because the thing the accent would mark does not exist; the chart's
sentence heading says so: "No run cut level is marked, because none is
identified." Episode counts such as "months below the kink" are printed only if
the export carries them (S29: the first version printed "21 of the 24 months",
which no Gate 3 output contains; methodology gives 24 of 135 below the kink with
every month and 101 of 114 without the episode).

### 6. Typography

| Face | Used for | Weights | Sizes (tokens) |
|---|---|---|---|
| Fraunces | the verdict `h1`; view titles `h1` on other views | 400 verdict, 500 view titles | `--fs-display-s` |
| Figtree | everything written: nav, section names and summaries, headings, table headers and row labels, axis titles, end labels, event labels, readouts, captions, prose, figures inside any sentence | 400, 500, 600 | `--fs-body`, `--fs-body-s`, `--fs-meta`, `--fs-caption` |
| JetBrains Mono | figures in table cells; tick values on axes. Nothing else | 400, 600 for totals | `--fs-meta` in tables, `--fs-caption` on axes |

- **Every rule that names Fraunces sets `font-weight`.** Its default instance is
  Black at optical size 9. `font-optical-sizing` stays `auto`;
  `font-variation-settings` is never used, which also means the portfolio's
  `h1, h2, h3, h4` rule (`"opsz" 144, "SOFT" 30`) is not copied.
- **Figtree has the same trap the other way** (S8). The vendored file's default
  instance is weight 300, Light (`vendor/README.md` of the LME sibling, "Name ID
  1 reads Figtree Light"). The portfolio sets 400 on `html, body`, a rule this
  site does not copy wholesale, so `styles/base.css` writes `body { font-weight:
  400 }` itself and every Figtree rule that means 500 or 600 says so. A missed
  weight renders the whole page in Light, and 13px Light `--text-muted` is
  thinner than the 4.90 ratio suggests.
- **Numerals.** Mono is tabular by construction. Every Figtree or Fraunces
  element that can contain a figure sets `font-variant-numeric: tabular-nums
  lining-nums`: Figtree's digits are proportional by default. Negative figures in
  prose use U+2212, which all three faces carry; in mono tables the hyphen minus.
- **Fraunces and `tnum`.** The LME sibling's README verifies `tnum` in Figtree
  and not in Fraunces. The verdict's figures never change in place, so
  proportional digits there are harmless; the shell checks the feature list once
  and records it in `vendor/README.md`, and nothing that updates live is set in
  Fraunces.
- **No glyph outside the shipped latin cuts**: no arrows, no check marks, no
  middle dot, no bullet. The theme toggle's glyph is the one exception, inherited
  (U+263E and U+2600), and it sits in a button with an `aria-label`. Neither is in
  the vendored cuts, so it falls back to a system face; each is followed by
  U+FE0E, the text presentation selector, so no platform draws it as a colour
  emoji (S11).
- **Case.** Sentence case everywhere. No `text-transform`, no positive
  `letter-spacing` on anything, labels or figures: the portfolio's `.mono` rule
  adds 0.02em and is not copied (S32). No `font-variant-caps`, no
  `font-feature-settings` naming `smcp`, `c2sc` or `case`: small capitals are all
  caps at a smaller size and are banned with them. The display letter spacing the
  portfolio uses on Fraunces, -0.025em, is kept for the verdict, the one negative
  value.
- **Fonts, vendored.** Copy the LME sibling's three files and licences byte for
  byte and check the sha256 of each copy, re-measured on the sibling's files on
  2026-09-16 and matching its `vendor/README.md`:

  ```
  fraunces/fraunces.v1.000.latin.woff2              7234ed860a9cc83045413c4faee63c960a8f2d1917adcf728119307d56e0d783
  jetbrains-mono/jetbrains-mono.v2.211.latin.woff2  18be452724bfdc236c074ca94a249a7f41a86752c7d04ab258ce9ed5651f6a7e
  figtree/figtree.v2.002.latin.woff2                4ba7d3d096695818fe0686be4f1e82c6b05134e18a22260336130335027462dd
  ```

  Each with its `LICENSE` (SIL OFL 1.1). `@font-face` URLs `../vendor/...` from `styles/tokens.css`,
  `format("woff2")`, no `local()`, `font-display: swap`. Preload Figtree then
  JetBrains Mono, with `crossorigin`.
- **Figtree for Satoshi.** The portfolio's body face is Satoshi, whose ITF Free
  Font License forbids a copy in a public repository, and SPEC.md section 0.1
  forbids the Fontshare CDN. Figtree is the substitute the LME sibling measured as
  closest. Disclosed in three places and no others: `vendor/README.md` (the full
  argument, pointing to the sibling's), `README.md` known limitations, and one
  sentence in the Method view under "Typefaces": "Body text is set in Figtree, an
  open licensed stand in for Satoshi, the portfolio's face, whose licence does not
  allow a copy in a public repository." `--ff-body` is redefined once, after the
  verbatim token block, as `"Figtree", system-ui, -apple-system, Helvetica,
  sans-serif`, with a comment naming the substitution. No footer badge.

### 7. Themes and the toggle

**Tokens.** `styles/tokens.css` holds the portfolio's `:root` and
`[data-theme="dark"]` blocks verbatim, byte for byte from
`portfolio_styles_pages.css` lines 21 to 87, followed by the `@font-face` blocks
and the single `--ff-body` override. `--shadow-sm`, `--shadow`, `--shadow-lg` and
`--grain-opacity` are present and referenced by no rule.

**Chart roles**, defined once in `styles/components.css` as aliases, so no chart
code names a raw token:

| Role | Light | Dark | Measured |
|---|---|---|---|
| series (gasoil and gasoline, every current year, fits, interval lines, bars) | `--text` | `--text` | 17.01 / 17.01 |
| context marks that carry data (weekly prior years, zero lines, leaders, cursor, break rules, event top ticks, evidence rail) | `--text-muted` | `--text-muted` | 4.90 / 7.54 |
| decorative marks, never read alone (gridlines) | `--border` | `--border` | 1.24 / 1.27 |
| decorative marks, never read alone (waterfall connectors, event full height hairlines, the 25 monthly prior years, rules under table headers) | `--border-strong` | `--border-strong` | 1.49 / 1.64 |
| mark accent (dots, rules, the one bar) | `--accent` | `--accent` | 7.96 / 3.79 on `--bg`; a `--bg` ring wherever it touches `--text` |
| text accent (figures, labels) | `--accent` | `--accent-bright` | 7.96 / 5.15 |
| ring and halo | `--bg` | `--bg` | separates accent from ink |
| flat span fill | `color-mix` of `--text` at 6 percent into `--bg` | same | no text inside it |

Changed by Part 6 (S10, S24, S25, S23): gasoline moved from `--text-muted` to
`--text`; prior year lines, zero lines and leaders moved from `--border-strong`
to `--text-muted` because they carry data; the ring role is new; the span may
hold no text. The full measured table is Part 6 section C.

`--text-dim` is used for nothing. It fails 3.0 in light. `--accent-deep` is used
for nothing: 2.14 in dark. `--bg-card`, `--bg-tint` and `--bg-elev` are used for
nothing except `--bg-elev` as the field background of Model inputs, where
`--text` measures 17.74 light and 15.40 dark and `--text-muted` 5.12 and 6.83. A
tinted block is the rounded card's near relative and is banned with it.

**Page overflow** (S22). The portfolio sets `body { overflow-x: hidden }`. It is
not copied: on this site it would hide the exact failure the 375 px check exists
to catch, a table or chart pushing the page wider. The body is allowed to
overflow so that the check can see it.

SVG marks take colour from classes that read these roles, never from `fill` or
`stroke` attributes holding a value, so a theme change needs no redraw.

**The toggle, copied from `portfolio_script.js`.** `data-theme` on `<html>`;
`index.html` ships `data-theme="light"` and `<meta name="theme-color"
content="#FBFAF8">`; `applyTheme` sets the attribute, writes `localStorage`
`nc-theme`, swaps the button glyph and rewrites `theme-color` to `#17181C` or
`#FBFAF8`; the button carries `aria-label="Toggle theme"` and `title="Press T to
toggle"`; the `keydown` listener toggles on `t` or `T` unless the target is an
input or textarea or a modifier is held. Four declared differences:

1. The listener also ignores `select` and `[contenteditable]`, because the Model
   view has selects.
2. Every `localStorage` access is inside `try`, so a blocked store falls back to
   light instead of throwing.
3. An inline script in `head`, before the stylesheets, reads `nc-theme` and sets
   `data-theme` before first paint (K30).
4. The button also sets `aria-pressed` to whether dark is on.

Because the study is served from `nathancouturier.github.io/crack-spread-study/`,
the same origin as the portfolio, `nc-theme` is shared: a visitor who chose dark
on the portfolio arrives in dark. System `prefers-color-scheme` is ignored, as the
portfolio ignores it.

### 8. Motion

The whole list. Anything not in this table does not move.

| What | Trigger | How | Duration |
|---|---|---|---|
| Section body height | a section button is activated | `grid-template-rows` from `0fr` to `1fr`, `--ease-out` | `--t-fast`, 200ms |
| Bar geometry in the Model waterfall | a Model input changes | the bar's `x` and `width`, `--ease-out` | `--t-fast` |
| Page background and text colour | the theme toggle | the portfolio's `background-color` and `color` transition, `--ease-out` | `--t-base`, 380ms |

Explicitly not animated: figures (they swap instantly, because an animated figure
shows values no artifact produced); chart first render; route changes; the
seasonal "Leave out 2022" toggle (the line is removed at once); the History
cursor and brush (they follow the pointer with no easing); hover of any kind; no
loading shimmer, a loading state is the sentence "Loading {series}".
`scroll-behavior` is `auto`.

`prefers-reduced-motion: reduce`: the portfolio's block copied verbatim
(durations 0.01ms, `scroll-behavior: auto`), minus its hero and reveal selectors
which do not exist here.

### 9. Accessibility

**Keyboard order on Now.** Skip link ("Skip to the verdict"); site name; six nav
links; theme toggle; the verdict `h1` (not focusable, reached by the skip link
with `tabindex="-1"`); the four section buttons; inside an open section, in
reading order: the chart group, the text alternative button named for its content, any
control, the link to the full view. On a hash route change, focus moves to the new view's `h1`
(`tabindex="-1"`) and `document.title` becomes "{view}, NWE crack spread study".

**Focus.** The portfolio's rule verbatim: `outline: 2px solid var(--accent);
outline-offset: 4px; border-radius: 2px`. Contrast 7.96 light, 3.79 dark on
`--bg`, 8.30 and 3.43 on a Model input's `--bg-elev`, all above 3.0 for non text.
The 4px offset keeps the ring on the page ground, never on a filled bar. Never
removed, never replaced by a colour change.

**Charts.** Every SVG: `role="img"`, `aria-labelledby` pointing to a `title` (the
chart's sentence heading) and a `desc` assembled from the artifact, for example
"Gasoil crack by week of the year, 2026 against 2022 to 2025. Latest 91.14 $/bbl
on 4 September 2026, above the highest same week, 58.21." Decorative children
`aria-hidden`. Interactive plots (History) are a `role="group"` with
`tabindex="0"` and an `aria-describedby` to the readout, which is
`aria-live="polite"`. Event labels are HTML buttons, not SVG elements.

**Text alternative for every chart.** A button under each chart, named for its
content (see below), reveals a real `table` with a `caption`, `th scope`, the same figures and
the evidence class and depth columns (`evidence_class`, `n_years`,
`cross_checked` as "yes" or "no second chart"). The waterfall, the response
table and the power table are already tables; their strips and bars are
`aria-hidden`.

**Contrast.** Part 6 section C, measured for every pairing in both themes.
Everything carrying meaning uses `--text`, `--text-muted`, the text accent role
or the mark accent on marks. Nothing uses `--text-dim` or `--accent-deep`. Only
the marks listed as decorative in section 7 sit below 3.0, and each is backed by
a label, a position or a table. No text sits on the span fill, on a filled bar or
on a hatch.

**Text alternative buttons name their content** (S7). Not "Show the numbers"
under every chart, which is any dashboard's data table toggle, but what the
table holds for this chart: "Every week, with how each was read", "The same
week in each prior year", "Every month on the scatter, with its episode".

**Other.** `lang="en"`. Touch targets 44px minimum. Brush has range input
equivalents. Model inputs are labelled `input` elements with units in the label.

### 10. The charting decision: SVG by hand

SPEC.md section 8: "use what the sibling repos already vendor. If they vendor
nothing suitable, vendor one small library or draw SVG by hand, and justify the
choice at Gate 4."

**What the siblings vendor.** The Baltic routes map vendors d3 7.9.0, 279,706
bytes. The LME model vendors no chart code.

**Why not d3, although it is vendored.**

- The Baltic map uses d3 for projections, zoom and selection. What this site
  would use is `scaleLinear`, `ticks`, `line().defined()` and `brush`: about 150
  lines of plain code, already written once in the LME sibling's
  `src/charts.js` (`tickValues` on a 1, 2, 5, 10 ladder, `onWidthChange`, a path
  that breaks at a gap). 280 KB for that is the wrong trade on a site that must
  load its data over the same connection.
- `d3-brush` has no keyboard model. The brush needs native range inputs anyway.
- Every mark in Part 3 is unusual in a way no helper covers: the evidence hatch
  from a per row column, printed squares over a reconstructed line, the depth
  strip from `n_years`, the waterfall inside table rows, the interval strip with
  an accent zero rule, the power strip. The code that decides those is the same
  size with or without d3.

**Why not a small chart library** (uPlot, Chart.js, Frappe). They render to
canvas or to their own SVG with their own defaults: a legend, a tooltip card,
axis styling, colour cycling. Each default is a banned or rejected item above,
and canvas output has no per chart `title` and `desc`, and needs a redraw on
theme change.

**Therefore:** `src/charts.js` draws SVG by hand, starting from the LME sibling's
helpers copied with attribution in a comment, and adding the marks in sections 2
to 5. `/vendor` holds fonts and licences only. This matches the sibling whose
content (time series, bars, intervals) is closest, and it departs from the one
that vendors d3 for a different job. **Open for the owner:** if one d3 across
the portfolio matters more than 280 KB, `d3-scale` and `d3-shape` alone could be
vendored instead; nothing in Part 3 changes.

**Other views, briefly, so nothing is invented later.** Events: one panel per
event, cracks, the margin at this study's intensity and utilisation from minus 6
to plus 6 months on three stacked 140px plots sharing x, the event month as a
`--accent` rule (the one thing). Model: the waterfall of section 4 with inputs in
a labelled form beside it (stacked below 768px), presets as four `aria-pressed`
buttons named with the reason for each month, taken from `events.json`, pressed
shown by a 2px `--text` underline and weight 600, breakevens in a two row table, $/bbl and EUR/MWh.

---

## Part 4. What the artifacts must carry

Written as requirements on the export step, so SPEC.md section 2 rule 2 holds:

1. `now.json`: the verdict as segments with field names; `margin_month`,
   `crack_month`, `runs_month`, `weekly_date`; each date's status and vintage from
   the manifest; `percentile_rank` and `percentile_observations` (the rank, not
   only the percentile); `mbr_usd_bbl`, `margin_study_intensity_usd_bbl`,
   `carrier`, `threshold_identified`, `headroom_usd_bbl` (null today).
2. The decomposition for `margin_month` (Part 7, C1: one month, from the
   ministry's printed quotations; `crack_month` equals it), with contributions,
   each product's printed price, cited factor and crack, residual,
   `unattributed_products`, `covered_volume_yield`, the gas price, both
   intensities, the wedge; plus the residual sign counts over the months a note
   printed final prices for.
3. Weekly cracks with `evidence_class`, `cross_checked`, `n_independent_geometries`
   per row, and the printed weekly figures as their own series.
4. `seasonal_weekly` per crack with `n_years` per week and the prior years as
   separate columns (the lines need the years, not only min and max); the episode
   years present in the range.
5. The monthly seasonal profile, the textbook check results and the month means.
6. Response models with `kb_d`, `kb_d_low`, `kb_d_high`, shares, t, months and
   the label; the question 42 reason sentence.
7. The horse race rows, the loss differential table with power, size and
   forecasts needed, and the `horse_race_winner` sentence.
8. The threshold result with its interval, the edge flag, the reason, the episode
   removed comparison, and the scatter points with their episode membership.
9. `events.json` with short labels and episode spans; a breaks list with dates or
   spans and labels (Part 0.9).
10. The manifest whole, including `manual_steps`, `gaps` with reasons, and
    `fetched_at`.
11. Decimals per unit, so formatting needs no literal.

Added by Part 6:

12. `intensity_ratio` (3.22) for the verdict's wedge clause; `capacity_t` and
    `fallback_t` beside the two kb/d figures for the run economics summary (S13,
    S16).
13. The note pair agreement converted per product to $/bbl with the config
    factor, `pair_mean_usd_bbl` and `pair_worst_usd_bbl`, and the tilt test's
    oldest week move in $/bbl, `oldest_tilt_usd_bbl` (S29, S12).
14. For each response model, `lower_share`: the lower end over the interval
    width when the lower end is above zero, null otherwise (S27).
15. The threshold refit without July 2020 to March 2022: its kink, slope below,
    and the fitted line's points, so the scatter draws both fits (S28). Months
    below the kink for both fits; nothing else is printed about counts.
16. Per source, the coverage spans the brush strip draws: first and last date,
    gap spans, `provisional_from`, and the scheduled job's last `fetched_at`
    (S1, S19).
17. `evidence_class` per (year, week) in `seasonal_weekly`, so the seasonal
    evidence rail needs no date logic in the frontend (S15).
18. The episode years present among the prior years of each seasonal layer,
    weekly and monthly, computed by the export (S33).

---

## Part 5. The checklist the shell has to fail against

1. Is there a figure on Now larger than the verdict text, or a figure alone on
   the right of a section header? K2, K4.
2. Are the three data dates on one line, or joined by any separator? K3.
3. Does any button or link end in an arrow, chevron, plus or minus? K5.
4. Does the Cracks header show the weekly date? K6.
5. Is the waterfall in "Refining margin and gas" drawn for any month other than
   the margin month, or with any product row whose figure is not in
   `data/margin-stack.json`? K1, as corrected by Part 7, C1: August 2026 alone
   is now the right answer, because August can be decomposed.
6. Is any bar or line green or red, or is the accent on a whole series? K8, K16.
7. Is the residual row lighter, greyer or smaller than a product row? K17.
8. Does the word "gas" alone label a waterfall step? K18.
9. Is there a band on the weekly seasonal panel, or the words "five year"? K13.
10. Does any toggle offer a year that is not in its range? K14.
11. Is the horse race sortable, bold anywhere, or does it contain "winner",
    "tie" or "dead heat"? K21.
12. Does any cell print "n/a" where "unidentified" belongs? K23.
13. Is the 230.4 row above the 59.3 row? K24.
14. Is JetBrains Mono computed on any element that is not a table figure or an
    axis tick? K25.
15. Grep `styles/` for `backdrop-filter`, `box-shadow`, `text-transform`,
    `gradient`, `var(--grain-opacity)`, `var(--text-dim)`. Each must return
    nothing. K26, K29.
16. Does any figure change through intermediate values, or does anything move
    that is not in the motion table? K28.
17. With a stored dark theme, is there a light frame on reload? K30.
18. Is there any U+2013, U+2014, U+00B7, U+2191 or U+2193 in `index.html`,
    `src/`, `styles/` or `data/*.json`?
19. Force the stylesheet to one foreground colour. Can gasoil be told from
    gasoline, and a positive step from a negative one?
20. Tab from the top of Now with the keyboard alone: open all four sections, reach
    the text alternative button in the cracks section, and see the focus ring at every stop, in both
    themes.
21. Does every asset path resolve from `/crack-spread-study/`, with no leading
    slash?

Added by Part 6:

22. At 375 x 812 with the fonts loaded, is the "Run economics and crude demand"
    section name inside the first viewport? Measure, do not estimate. S21.
23. At 375 px, on every view, with every Now section open: is
    `document.documentElement.scrollWidth` greater than `clientWidth`? Must be no.
    S22, S31.
24. At 375 px, is any interval strip or power strip inside a horizontally
    scrolling container? Must be no. Does the waterfall scroll sideways? Must be
    no. S31.
25. Grep `styles/` for `font-variant-caps`, `smcp`, `c2sc`, `mask-image`,
    `overflow-x: hidden` on `body`, `var(--bg-card)`, `var(--bg-tint)`,
    `var(--accent-deep)`, and any positive `letter-spacing`. Each must return
    nothing. S6, S32, section 7.
26. Grep `index.html`, `src/` and `data/*.json` for U+2192, U+2197, U+203A, U+00BB,
    U+2022, U+2027 and U+22C5, and for " | " inside any visible string. None. The
    theme glyphs U+263E and U+2600 appear only followed by U+FE0E. S11.
27. Is there more than one element in the accent colour on any chart, counting a
    dot and its drop rule as one mark? S3.
28. Does any text sit on the span fill, on a filled bar or on a hatch? S23.
29. Is gasoline drawn in any colour other than `--text`, or is a data carrying
    line (prior year, zero, leader) drawn in `--border-strong`? S10, S24.
30. Do the words "clears zero", "a coin", "SPEC 6.1", "product prices" or
    "Rotterdam refiners made" appear on any view? S26, S27, S13.
31. Does any weekly crack figure on Now appear without "read off the ministry's
    chart" in the same sentence or heading? S14, S15.
32. On the Runs view and in the run economics section, does "unidentified" come
    before the response table, in the same size as its figures? S17.

---

## Part 6. The second critique

Written on 2026-09-16 by a reviewer who did not write Parts 1 to 3, against
SPEC.md sections 0, 1, 2, 7 and 10 and the Gate 2 and 3 results. Part 2 was a
good self critique; this part looks for what a self critique does not find: the
habits the author still shares with the first pass, colour pairings nobody
measured because they are marks on marks, and places where the page's wording
is kinder to a result than the result is. Every revision below is already in
Part 3, 4 or 5 with its S number.

### A. The generic dashboard test, item by item

The question for each treatment: would it appear unchanged on any analytics
dashboard? A convention the reader already knows how to read (a y axis, a
right aligned figure column) is not the failure the brief means; chrome that
carries no content of this study is. Verdicts: **kept** (specific already, or a
convention worth keeping), **replaced**.

| Treatment in Part 3 as received | Any dashboard? | Verdict |
|---|---|---|
| Header, name, nav, toggle | yes, and inherited from the portfolio | kept; no sidebar, no avatar, no search. Nav label "Runs and crude demand" kept whole at 375 px (S20) |
| Verdict `h1` from field segments | no | kept; wording corrected (S13) |
| Data dates as a `dl` | the key and value pair is | replaced by four sentences (S5), with the weekly date and its fetch time as the fourth (S19) |
| Four accordion rows with a summary | the accordion is | kept because SPEC.md section 7.2 requires closed sections; made specific by names that carry the CV line's words (S20) and summaries that lead with the gap, not a count (S2, S17) |
| Section names Cracks, Margin stack, Runs, Provenance | "Margin stack" is this study's jargon, the rest could label any energy dashboard | replaced by "Gasoil and gasoline cracks", "Refining margin and gas", "Run economics and crude demand", "Provenance" (S20) |
| Provenance summary "20 series fetched, none failed" | yes, a status count | replaced by the outstanding OPEC gap first (S2) |
| Axes, 1, 2, 5 ticks, horizontal gridlines | yes, a convention | kept; zero line promoted to `--text-muted` (S24) |
| Gasoil in ink, gasoline in muted grey | yes, primary and secondary series | replaced: both in `--text`, dash and end label as identity (S10) |
| End labels, no legend | no, the brief's own rule | kept |
| Accent dots on the latest week | the brief's rule | kept; `--bg` ring added (S25) |
| Event lane with buttons | annotations are common; these labels are not | kept; 4px `--text-muted` top tick added |
| Split paths at breaks, dotted gap marks | no | kept |
| Printed weeks as squares | no | kept |
| Least defended weeks hatched behind the lines | yes, the shaded "forecast zone" | replaced by the evidence rail under the axis (S12) |
| Readout line and vertical cursor | yes | kept, because the evidence clause in the readout ("read off the chart, no second chart yet") is what a generic crosshair never says |
| Named range buttons | no | kept; pressed state as underline and weight, not fill |
| Brush over a thumbnail of the series | yes, the stock chart widget | replaced by a coverage strip of the four data dates (S1) |
| Empty chart sentence | half generic, it said what failed but not what to do | completed (S34) |
| Product toggle as pressed chips | yes, the filter pill | replaced by native checkboxes (S4) |
| Weekly seasonal prior years as labelled lines | no, it follows from the missing five year range | kept; recoloured to pass 3.0 (S24); evidence rail added (S15) |
| Depth rail from `n_years` | no | kept |
| "Leave out 2022" pressed chip | the chip is | state now in the words, "Put 2022 back" (S4) |
| Monthly seasonal, median over 25 hairlines | a climatology plot, common | kept; the failed winter window bracket is the part that belongs here; toggle list fixed (S33) |
| Waterfall as a table with bars | no | kept; one accent (S3), residual copy (S30), small steps drawn, layout at 375 px (S31) |
| Accent on both official margin totals | yes, accent as the style of "total" | replaced: one accent, August 2026 (S3) |
| Table rules: mono, right aligned, hairlines, no zebra | yes, good practice | kept; fixed order and units in headers are the specific part |
| Scroll shadow or fade mask on wide tables | not written, but the default any builder adds | forbidden in words (S6) |
| Sticky first column | yes | kept, it is needed at 375 px |
| Interval strip with accent zero rule | no, a forest plot | kept; "clears zero" replaced (S27); pulled out of the scroll at 375 px (S31) |
| Horse race and power strips | no | kept; wrong analogy removed (S26) |
| Threshold scatter, one fit and a shaded interval | yes, the default regression figure | replaced by two fits that slope opposite ways (S28) |
| "Show the numbers" under every chart | yes | replaced by buttons named for their table (S7) |
| Motion: height, bar tween, theme fade | the accordion height is | kept, three items, all answers to an action |
| SVG by hand | no | kept; the argument in section 10 holds |

Of the thirty four rows, twenty one are kept, several with a correction, and
thirteen are replaced, completed or forbidden in words. The replacements cluster in the same
places Part 2's did not look: state shown by fill (chips, pressed buttons), tone
used as hierarchy (gasoline, grey prior years), and the three widgets every
finance chart ships with (thumbnail brush, forecast shading, single fit scatter).

### B. The banned list, read literally, with near relatives

| Banned | Literal check of Part 3 | Near relative looked for | Result |
|---|---|---|---|
| all caps labels | none; acronyms (MBR, JODI, OPEC, TTF, NWE, R2, RMSE) are names, not a label style | small caps via `font-variant-caps`, `smcp`, `c2sc`; letter spaced sentence case labels; the portfolio's `.mono` 0.02em | small caps and every positive `letter-spacing` now banned in section 6 and grepped (Part 5 item 25) (S32) |
| eyebrow labels above headings | none above headings | a `dl` term that stacks above its value on a phone; "Headroom to the run cut level" above "unidentified"; lane names above strip lanes | `dl` removed from the dates and the headroom (S5, S17); coverage lanes end labelled, not titled |
| meta strings joined with middle dots | `<title>` joined by a comma | pipes, slashes, bullets U+2022, U+2027, U+22C5 as separators | grepped (Part 5 item 26) |
| arrows appended to buttons or links | "Show" and "Hide"; plain links | breadcrumb chevrons U+203A and U+00BB, the external link arrow U+2197 on source links in Provenance, CSS `::after` content arrows | grepped; source links in the manifest table are the plain source name |
| glassmorphism | none | a sticky table column with a translucent background | sticky column is solid `--bg` |
| noise overlays | not copied | the hatch used as texture | the hatch has one meaning and one place (section 2) |
| gradient washes | none | fade masks on scroll containers; a `color-mix` span that fades | `mask-image` grepped; span is one flat mix |
| heavy shadows | none | scroll shadows on the sticky edge | forbidden (S6) |
| the same rounded card for every block | no cards, no radius | a tinted block (`--bg-card`, `--bg-tint`) for every section; every inner block framed by the same hairline and padding | tints unused (section 7); hairlines only on the four section rows and table headers (S9) |
| watermarks | none | "reconstructed" or "provisional" stamped over a plot or as a pill | status words inline in sentences; no text over a plot |
| AI tags | none | a "generated" note on the verdict because it is templated | none; the template is a code fact, not a page fact |

One inherited glyph is outside the rule set's spirit: the theme toggle's moon and
sun. Kept because the portfolio has them, with U+FE0E so they do not render as
emoji (S11).

### C. Contrast, measured

WCAG 2 relative luminance from the token hex values in
`portfolio_styles_pages.css`, ratio (L1 + 0.05) / (L2 + 0.05). Requirements:
4.5 for text at the sizes used here (nothing on the site is 24px regular or
18.66px bold except the desktop verdict, and it is set in `--text`), 3.0 for a
graphical object that carries meaning (WCAG 1.4.11), 3.0 between two adjacent
marks when one must be told from the other by colour. The span fill is
`color-mix(in srgb, var(--text) 6%, var(--bg))`: `#EDECEB` light, `#252629`
dark.

| Foreground | Background | Use in Part 3 | Needs | Light | Dark | Outcome |
|---|---|---|---|---|---|---|
| `--text` | `--bg` | all prose, figures, series, bars | 4.5 | 17.01 | 17.01 | pass |
| `--text-muted` | `--bg` | nav, summaries, headers, tick values, prior years, zero lines, leaders, evidence rail | 4.5 | 4.90 | 7.54 | pass; light has 0.40 to spare, so 13px Figtree must be weight 400, never Light 300 (S8) |
| `--text-dim` | `--bg` | nothing | 4.5 or 3.0 | 2.54 | 3.47 | fails text in both, fails 3.0 in light; **removed from the plan** |
| `--accent` | `--bg` | light text accent; marks in both | 4.5 text, 3.0 mark | 7.96 | 3.79 | light pass; dark passes as a mark only; **restricted: never text in dark** |
| `--accent-bright` | `--bg` | dark text accent | 4.5 | 6.51 | 5.15 | pass, used in dark only |
| `--accent-deep` | `--bg` | nothing | 3.0 | 10.87 | 2.14 | fails in dark; **removed** |
| `--border` | `--bg` | gridlines, section hairlines | decorative | 1.24 | 1.27 | below 3.0; **restricted to marks no value is read from** |
| `--border-strong` | `--bg` | first version: prior years, zero line, leaders, hatch; now: connectors, event full height lines, 25 monthly hairlines, table header rules | 3.0 if it carries data | 1.49 | 1.64 | fails; **removed from every data carrying mark** (S24) |
| `--text` | `--bg-elev` | Model input values | 4.5 | 17.74 | 15.40 | pass |
| `--text-muted` | `--bg-elev` | Model input units | 4.5 | 5.12 | 6.83 | pass |
| `--accent` | `--bg-elev` | focus ring on an input | 3.0 | 8.30 | 3.43 | pass |
| `--accent-bright` | `--bg-elev` | an accent figure inside an input | 4.5 | 6.79 | 4.67 | pass; dark with 0.17 to spare |
| `--text` | `--bg-card` | nothing | 4.5 | 15.99 | 15.77 | unused, tints banned |
| `--text-muted` | `--bg-card` | nothing | 4.5 | 4.61 | 6.99 | unused |
| `--text` | span fill | scatter points inside the interval span | 3.0 | 15.03 | 14.50 | pass |
| `--text-muted` | span fill | first version: the "Edge of the range searched" label | 4.5 | 4.34 | 6.43 | **fails as text in light**; label moved above the plot onto `--bg`, no text inside the span (S23); the 1px edge rule passes as a mark |
| `--accent` | span fill | nothing, no accent on the scatter | 3.0 | 7.03 | 3.23 | would pass; unused |
| `--accent` | `--text` | accent dot on an ink line; accent zero rule crossing an ink interval; accent tick under an ink power dot | 3.0 adjacent | 2.14 | 4.49 | **fails in light**; every accent mark touching ink gets a 2px `--bg` ring (S25) |
| `--accent-bright` | `--text` | dark accent label near an ink line | 3.0 adjacent | 2.61 | 3.30 | labels carry a `--bg` halo, so the pair never touches |
| `--accent` | `--text-muted` | accent dot on a prior year line or the cursor | 3.0 adjacent | 1.62 | 1.99 | **fails in both**; ring (S25) |
| `--text-muted` | `--text` | current year crossing a prior year line | not relied on | 3.47 | 2.26 | told apart by width (2px against 1px), dash, and end label, never by tone alone |
| `--bg` | `--text` | the ring and halo against ink | 3.0 | 17.01 | 17.01 | pass |
| `--text-muted` | `--bg` | hatch strokes, evidence rail | 3.0 | 4.90 | 7.54 | pass (was `--border-strong`, 1.49 and 1.64) |

Three failures Part 0.10 could not show, because it measured tokens on `--bg`
only: muted text on the span in light, accent against ink in light, and accent
against muted in both. And one that Part 3 had carried into the data: the weekly
prior year lines at `--border-strong`, which became the whole comparison once the
band was removed.

### D. The honesty of the negative results

The test: does the page make "unidentified", "cannot separate", an interval
that nearly touches zero, the missing five year range and the reconstructed
weeks look like what they are, with the same type as the positive numbers?

What Part 3 already did right, kept: the runs clause of the verdict is in the
same `h1` as 38.05; the horse race has no order, no bold, no accent; the
scatter carries no accent because nothing is identified; no band pretends to be
a range; the residual row is full weight.

What it did not, and the revision:

- **S13, the verdict overstated what the MBR is.** "Rotterdam refiners made"
  claims earnings; the MBR is the ministry's notional margin, net of gas at
  0.0659. "The last month with product prices" was false on a page that shows
  weekly product cracks to September.
- **S14, S15, the most visible weekly figure hid how it was made.** The Cracks
  header and the seasonal heading put 91.14 in front of every visitor with no
  word that it is read off a chart, and "above every same week since 2022" read
  like a long record when it is four years. Both sentences now carry the
  reconstruction and the depth; the evidence rail puts the least defended weeks
  of the 2022 prior line on the seasonal panel, where they sit inside the range
  the headline is measured against.
- **S16, the run economics summary led with the bigger number.** Part 2 fixed
  the table order (K24) and left the header summary saying "230.4 kb/d on one
  model and 59.3 on the other", with "is worth" as the verb. It now leads with
  the unidentified threshold, then the planned model, each figure with its t.
- **S17, "unidentified" sat below the response table, as a label and value
  pair.** On a phone the pair stacks into a label above a word, the metric with a
  label above it, and a reader who stops at the table never reaches it. It is now
  the first paragraph of the section, in body size, with "unidentified" in 500.
- **S18, the June runs figure was not marked provisional** inside the section,
  only in the dates list. Each provisional row now says so.
- **S26, a wrong analogy on the weakest result.** "0.050 is what a coin would
  give" is false (a coin gives 0.5) and makes the horse race sound like a
  literal coin toss. Replaced by what size means.
- **S27, "clears zero by 5.1" is a pass word.** The distance is still printed, now
  as a share of the interval width, 1.1 percent. The strip keeps its true domain,
  so the lower tick sits a pixel or two from the zero rule: the interval that
  nearly touches zero looks like one because it is drawn to scale, not because a
  word says "nearly".
- **S28, the reason for "unidentified" led with the weaker evidence.** An interval
  reaching the search edge "sounds like a wide estimate of something real"
  (`docs/methodology.md`); the sign flip without July 2020 to March 2022 is the
  stronger fact. It leads the sentence, and the scatter draws both fits so the
  flip is seen.
- **S29, figures without a source, and a unit mismatch.** "21 of the 24 months
  below the kink" is in no Gate 3 output; removed unless exported. The note pair
  agreement was quoted in $/t beside a $/bbl chart. "22 of 25 years" and 0.30 and
  1.68 were checked and are in `docs/methodology.md`.
- **S30, a causal "so" the data does not carry.** Coverage of 46.8 percent and a
  negative residual are two facts; the residual row now says them as two.

Type parity, checked after the revision: every negative finding on Now is set in
the same face, size and colour as the positive figure next to it. The only
display type on the page is the verdict, and it contains both 38.05 and "cannot
say whether runs have room to rise". Nothing negative is in `--text-muted` that
its positive neighbour is not.

### E. The CV line, walked in ten seconds

A commodity professional who read "tracked NWE refining margins across gasoil
and gasoline cracks, and linked run economics to crude demand" lands on
`#/now` at 1440 x 900.

- **Seconds 0 to 3.** The verdict: a margin, after gas, August 2026, the most in
  120 months, a second figure at a heavier gas use, gasoil carrying the barrel,
  runs with no identified room. "NWE refining margins" is found. "Run economics"
  is half found, as "after gas" and "runs have room", but not by name.
- **Seconds 3 to 5.** Four dated sentences. "Tracked" is found: a weekly date and
  when the job fetched it. Before S19 the only weekly date on Now was inside a
  section summary.
- **Seconds 5 to 10.** Four section names. Before S20 they read Cracks, Margin
  stack, Runs and crude demand, Provenance: "run economics" appeared nowhere, the
  one clause SPEC.md section 1 says the site fails on. Now "Gasoil and gasoline
  cracks", "Refining margin and gas", "Run economics and crude demand", with a
  summary under the third giving kb/d per 10 $/bbl for both models. Every clause
  is found by its own words.

At 375 x 812: nav with "Runs and crude demand" (crude demand, second 1); verdict
(margins, second 2 to 5); four dated sentences (tracked); the cracks and margin
rows; and the run economics name estimated at 671 to 693 of 700. **Just inside,
by an estimate.** Part 5 item 22 makes the shell measure it. The kb/d figures
need a short scroll at that width; "crude demand" does not.

Flagged for the owner: the four section names depart from SPEC.md section 7.2's
labels, and the dates list has four entries where the brief says three. Both
changes exist only to pass SPEC.md section 1.

### F. Feasibility at 375 px

Content width at 375 px: `--gutter` is `clamp(1.25rem, 4vw, 2.75rem)`, which
resolves to 20px, so 335px. The shell measures.

| Element | Fits? | Treatment at 375 px | Scrolls sideways inside its own container? |
|---|---|---|---|
| Header and nav | yes, two rows plus a wrapped nav line, about 120px | flex wrap, full "Runs and crude demand" | no |
| Verdict and dates | yes | `--fs-body-l` verdict, dates at line height 1.3 | no |
| Section rows | yes | summary at `--fs-meta`, "Show" at the right, 44px minimum target | no |
| Seasonal panels | yes, stacked, about 250px plot width after ticks and year labels | year labels with leaders; two 14px rails | no |
| Waterfall | not as three columns (name column about 100px, residual row seven lines) | each row two lines, name then bar and figure, grid on `tr` with explicit ARIA roles; blocks stacked on one scale; bar track about 255px, 6.4px per $/bbl; steps under 4px as circles | **never** |
| Response interval strips | not inside the table | pulled out above the table, full width, one 28px row per model | never |
| Response table | no, seven columns | `overflow-x: auto`, model name sticky, caption names the off screen columns | yes, the numbers only |
| Horse race and power tables | no | as the response table; power strips pulled out above | yes, the numbers only |
| Manifest table | no | columns ordered series, status, last value date, last fetch, gaps, vintage, source, so a failed or stale row is visible before scrolling; series name sticky | yes |
| History chart | yes, 240px tall | every second year label; colliding event labels become numbers; hatch at least 6px wide | no |
| Coverage strip and brush | yes, about 64px | end labels move above each lane's right end when the bar reaches the edge; range inputs as the keyboard route | no |
| Threshold scatter | yes, 240px tall | fit end labels inside the plot on a `--bg` halo; edge label in the lane | no |
| Model form and waterfall | yes, stacked | inputs full width, 44px tall | no |

**What must never make the page scroll.** The body. `overflow-x: hidden` is not
copied from the portfolio because it would hide the failure instead of
preventing it (S22), and Part 5 item 23 checks `scrollWidth` against
`clientWidth` on every view with every section open. The only horizontal
scrolling on the site is inside a table's own container, and no picture that
carries a finding (interval strip, power strip, waterfall bars) is ever inside
one (S31).

### G. Every change, and why

| | Change | Why |
|---|---|---|
| S1 | Brush over a coverage strip of the four data dates, not a thumbnail of the series | the thumbnail brush is the stock chart widget; the coverage strip shows why lines stop where they do |
| S2 | Provenance summary leads with the OPEC gap | "20 series fetched" was a count that buried the one outstanding manual step |
| S3 | One accent in the waterfall, the August official margin | two accents made the accent mean "total" |
| S4 | Checkboxes for products, word flip for "Leave out 2022", underline and weight for pressed ranges and presets | state shown by fill is the filter chip of any dashboard and relies on tone |
| S5 | Dates as four sentences, not a `dl` | a stacked term and description is a label above a value |
| S6 | No scroll shadow, no fade mask, caption names off screen columns | the default scroll affordances are a heavy shadow and a gradient wash |
| S7 | Text alternative buttons named for their table | "Show the numbers" is generic |
| S8 | `font-weight: 400` on body, every Figtree weight explicit | the vendored Figtree defaults to 300 |
| S9 | Inner blocks separated by space and a sentence, hairlines only on section rows and table headers | the same hairline frame on every block is the card in disguise |
| S10 | Gasoline in `--text`, dashed | tone hierarchy is generic and greyed the weaker leg as if unimportant |
| S11 | U+FE0E after the toggle glyphs | the glyphs fall back to system fonts and can render as emoji |
| S12 | Hatch moved from behind the lines to an evidence rail under the axis | a shaded zone behind a series is the dashboard forecast region and muddies the dashed line |
| S13 | Verdict: "on the ministry's Rotterdam margin, a refiner kept", "the average US refinery's gas use, 3.2 times the ministry's", "the last month the margin can be split by product" | the first wording claimed realised earnings, was vague on the intensity and false about product prices |
| S14 | Cracks summary says "read off the ministry's weekly chart" and the number of years | the headline weekly figure hid its reconstruction and its depth |
| S15 | Seasonal heading carries both; evidence rail on the seasonal panel; "not a five year range" said once | the least defended weeks sit inside the range the headline is compared with |
| S16 | Run economics summary: unidentified first, planned model first, t beside each kb/d | the summary led with 230.4 and "is worth" |
| S17 | Headroom paragraph first in the section and the view, body size, not a label pair | "unidentified" was below the table and stacked as a label on phones |
| S18 | Provisional months say "provisional" in the runs table | the flag lived only in the dates list |
| S19 | Weekly date and fetch time as a fourth dated sentence | "tracked" needs it on the landing view at every width |
| S20 | Section names carry the CV line's words; nav keeps "Runs and crude demand" whole | "run economics" was not on the page by name |
| S21 | Verdict at `--fs-body-l`, dates at line height 1.3, summaries at `--fs-meta`, at 480px and below; fold re-estimated | at 22px the verdict ran ten lines and pushed the run economics row below the fold |
| S22 | `body { overflow-x: hidden }` not copied | it hides the overflow the 375 px check must find |
| S23 | No text on the span fill; the edge label moved to the lane | `--text-muted` on the span is 4.34 in light |
| S24 | Prior year lines, zero lines, leaders, hatch in `--text-muted` | at `--border-strong` they measure 1.49 and 1.64 while carrying data |
| S25 | 2px `--bg` ring on every accent mark that touches ink or muted | accent against ink is 2.14 in light, against muted 1.62 and 1.99 |
| S26 | "0.050 is the rate at which the test would report a difference that does not exist" | "what a coin would give" is wrong |
| S27 | "Clears zero by 5.1" replaced by a Zero column with the lower end as a share of the interval | "clears" reads as a pass |
| S28 | The sign flip leads the unidentified paragraph; the scatter draws both fits | the methodology names the flip the stronger evidence |
| S29 | Unsourced "21 of the 24 months" removed; agreement converted to $/bbl | a figure no artifact holds breaks SPEC.md section 2 rule 2; $/t beside a $/bbl chart cannot be read |
| S30 | Residual second line states coverage and sign as two facts | the causal "so" was not measured |
| S31 | Waterfall rows in two lines, strips pulled out of scrolling tables, manifest columns reordered | three columns and seven column tables do not fit 335px, and a finding must not sit behind a sideways scroll |
| S32 | No positive letter spacing anywhere, no small caps, portfolio `.mono` and heading rules not copied | small caps are the near relative of all caps; `.mono` adds 0.02em |
| S33 | Episode toggles listed from a field; monthly list no longer offers 2026 | 2026 is the current year on that panel |
| S34 | Empty chart sentence says what to do | SPEC.md section 7.3 asks for both halves |

### H. What this critique did not change, and why

- **SVG by hand over the vendored d3.** Section 10's argument holds on the
  measured sizes and on the keyboard gap in `d3-brush`, which S1 makes more
  relevant, not less.
- **"Show" and "Hide".** Plain, not generic in any harmful way, and the
  alternatives are all arrows or signs.
- **Two month blocks in the waterfall.** The right answer to a landing month that
  cannot be decomposed; S3 only moves the accent.
- **The motion table.** Three entries, each an answer to an action.
- **Horizontal gridlines and a 1, 2, 5 tick ladder.** Conventions, kept on
  purpose; replacing them would be novelty, not specificity.

---

## Part 7. Gate 4 corrections, from the build brief

The Gate 4 brief overrides Part 3 where they disagree and asks for each change to
be recorded here. Every one of these is already folded into Parts 0, 3, 4 and 5,
tagged with its C number. C10 to C15 answer the adversarial Gate 4 audit
(`docs/self-audit.md`, "Self audit, Gate 4"), whose finding numbers they cite.

### C1. August 2026 can be decomposed, so the Now view does not mix months

**What the plan said.** Part 0.1 said the landing month could not be decomposed
because no product prices existed for August 2026, so Part 3 section 4 built two
waterfall blocks, February 2026 from the OPEC MOMR cracks and August with its
product rows empty, and the verdict's carrier clause named February.

**Why that was wrong.** Verified by the main session from the committed cache:
`data/cache/dgec_note_printed_monthly.csv` carries the ministry's FINAL August
2026 monthly quotations, printed in the note of 4 September 2026 with provisional
False, and `data/cache/dgec_brent_monthly.csv` has August Brent at 91.076 $/bbl.
So the latest month can be decomposed from the same ministry, the same month and
the same basis as the official margin it explains, which is strictly better than
OPEC's February and removes the month mixing from the verdict.

**What was built.** `crack.series.note_decomposition_for_month`, additive: the
OPEC path, `DGEC_VOLUME_YIELDS`, the engine and the parity fixture are unchanged,
and `scripts/gen_fixtures.py --check` still reports the fixture byte identical.
`latest_view` gains `margin_decomposition`, `margin_cracks` and `margin_carrier`
beside its Gate 2 fields. A provisional printed month is refused by name, never
decomposed against a final margin.

**Which products joined, and on what citation.** SPEC.md section 4.1 allows a
factor only from the DGEC methodology note or an ICE contract specification.
The note (`data/private/dgec_notes/mbr_method.pdf`, read in full) states one
factor, Brent at 7.55 bbl/t, and none for any product. All three extra products
have an ICE Futures Europe crack contract whose specification prints a conversion
factor, read from the product guide PDFs on 2026-09-16:

| Product, the ministry's label | Factor | ICE contract |
|---|---|---|
| Jet | 7.88 | Jet Fuel Crack, Jet CIF NWE Cargoes vs Brent 1st Line Future, 6753303 |
| Fioul domestique | 7.45 | Gasoil Crack, Gasoil 0.1% FOB ARA Barges (Platts) vs Brent 1st Line Future, 6753295 |
| Fioul lourd TBTS (< 1%) | 6.35 | Fuel Oil Crack, Fuel Oil 1% FOB NWE Cargoes vs Brent 1st Line Future, 6753289 |

The same download of 6753331 and 6753285 prints 7.45 and 8.33, the two factors
SPEC.md already fixes. So no product stays in the residual for want of a factor.
What the residual still holds, named on the page: butane, export gasoline,
naphtha, propane and sulphur, which the note does not quote, 23.2 percent of the
tonne, plus the method's gas purchase, freight and insurance costs. A contract
factor is a settlement convention, not the density of the Reuters cargo the
ministry quotes; that is stated in the residual row's `approximations`.

**What changed on the page.** The verdict's carrier clause (Part 3 section 1),
the "Refining margin and gas" summary, the waterfall's form (Part 3 section 4,
one block), Part 4 item 2 and Part 5 item 5. February 2026 on the OPEC path is
not the Now view's and may appear as history later.

### C2. Three data dates, not four

The brief asks for "the three data dates, each with its own provisional flag and
status word, never merged". The fourth sentence, "Monthly product quotations stop
at February 2026", described the OPEC path and C1 took the OPEC path off the Now
view. The three are margins (with the note that printed the prices that split
them), weekly cracks (S19 keeps it on Now), and runs. The status word comes from
the manifest (`provisional_from`, `method`) and, for the margin month's
quotations, from the printed row's own provisional flag: final, provisional, or
reconstructed for the weekly chart reading.

### C3. The Provenance summary no longer leads with the OPEC gap

S2 put the OPEC gap first because it stopped the Now view's decomposition. It no
longer does, so the summary states the failure count first and then the one
outstanding manual step with what it now costs: the monthly OPEC history of the
cracks ends at February 2026.

### C4. Sentences travel as segments, and the export writes them

Part 3 section 1 said the verdict arrives as segments naming their fields. The
export does that for every sentence the Now view prints: the verdict, the
headroom or unidentified paragraph and its percentile fallback, the three data
dates, the four section summaries, the residual and wedge second lines, the
response disagreement sentence and the 2026 utilisation sentence. A text segment
holds no digit; `tools/validate-artifacts.mjs` and `tests/test_export.py` both
assert it, so every figure on Now names the field it came from.

### C5. What Part 4 asked for that the Now view does not read, and is not exported yet

The sentence under the waterfall comparing the two cracks' R2 against the
official margin (Part 3 section 1, "Section contents"), which no Gate 3 function
returns as a value today; the monthly seasonal profile (item 5), the horse race and power tables (item 7),
the threshold scatter points and both fitted lines (items 8, 15), `events.json`
short labels and the breaks list (item 9), the note pair agreement in $/bbl and
the tilt measurement (item 13), and the coverage spans for the History brush
(item 16). They belong to History and the Runs view at Gate 5. The pair agreement
and the tilt figure in particular exist today only as measurements quoted in
`docs/methodology.md`, not as a function's output, so exporting them first needs
a function that computes them; typing 0.30, 1.68 or 10 into the exporter would
break SPEC.md section 2 rule 2 from the other side.

### C6. Two comments in the verbatim token block lost a middle dot and an em dash

`styles/tokens.css` copies the portfolio's custom properties byte for byte. Two
comments inside that block carried a middle dot and an em dash, which SPEC.md
section 0.1 and Part 5 item 18 ban from every file, so those two characters
became commas. No declaration was touched.

### C7. The nav links only the views that exist

At Gate 4 only Now has data behind it. A nav link to History, Model, Runs and
crude demand, Events or Method would open onto nothing, an orphan UI state
(SPEC.md section 11 point 8), so `src/ui.js` builds the nav from its route table
and Gate 5 adds each view with its link. The "Runs and crude demand" words above
the fold at 375 px therefore come from the section name "Run economics and
crude demand" until the Runs view is published.

### C8. The theme glyphs carry U+FE0E

Recorded in Part 3 section 6 as S11 and implemented in `src/theme.js` and
`index.html`: each glyph is followed by the text presentation selector.

### C9. The verdict is said out loud: four clauses, the month once

**What the plan said.** Part 3 section 1 gave the verdict five clauses, the
fifth "or {study} at the average US refinery's gas use, {ratio} times the
ministry's", and named the margin month in the margin clause, the rank clause
and the carrier clause. Built from `data/now.json` it read at about 65 words.

**Why that was wrong.** SPEC.md section 7.2 asks for one sentence a trader would
say out loud with four things in it: what a Rotterdam refiner earns per barrel
after gas this month, where that sits in ten years, which crack carries the
barrel, and whether runs have room to rise. A second margin at a second gas
intensity, and the same month three times, is a paragraph read off a table.

**What was built.** `crack.export.verdict_segments` writes four clauses with the
month once: the rank clause drops "to {month}" because the trailing window ends
at the margin month, and the carrier clause drops "at the ministry's own prices
for {month}" unless the split month ever differs from the margin month, in
which case it names it. "After gas" became "after its own gas allowance", which
says whose gas assumption the figure is net of. The US intensity figure and the
ratio moved to `margin-stack.json`: `study_margin_segments`, printed under the
waterfall, and the ratio in `wedge_segments`, the wedge row's second line.
`tests/test_export.py` pins the new sentence whole, the single month and the
moved fields; `tools/validate-format.mjs` checks the same through `format.js`.

### C10. The verdict says gross margin, and whose gas allowance

**What the plan said.** C9's wording, "a refiner kept 38.05 $/bbl after its own
gas allowance", and the argument that "its own" is the fewest words that say
the gas assumption is the ministry's.

**Why that was wrong.** The Gate 4 audit, S4. `now.json`
`net_of.costs_not_subtracted` reads "every cost of refining other than energy",
so a refiner does not keep this margin: "kept" is the "made" of S13 in another
verb. And the nearest owner for "its" is "a refiner", so a desk reader takes
"its own gas allowance" as the refinery's gas, the reading the words were meant
to exclude, and then finds the US gas use 3.2 times higher two sections down.

**What was built.** `crack.export.verdict_segments`: "On the ministry's
Rotterdam measure, refiners' gross margin after the ministry's gas allowance was
38.05 $/bbl in August 2026, the most in 120 months; gasoil carried 27.00 of it,
and this sample cannot say whether runs have room to rise." Forty words, within
the 40 `tests/test_export.py` allows; "a refiner's" became "refiners'" to stay
inside it. `study_margin_segments` says "the same barrel's gross margin would
have been 34.96" instead of "would have kept", and the waterfall caption says
"its gross margin at the average US refinery's gas use". `tests/test_export.py`
fails on " kept " or "its own gas" in any exported sentence;
`tools/validate-format.mjs` reads the verdict for the same through `format.js`.

### C11. The weekly headline leads with the printed figure

**Why.** Audit S5. The latest week, 4 September 2026, was printed by the
ministry: gasoil 91.11, gasoline 65.94. The page led with its own chart reading,
91.14 and 65.91, and put the printed figures last. A reader holding the note
asks why the site prefers its reading of a chart to the number printed beside
it.

**What was built.** When both products are printed for the latest week, the
Cracks summary reads "Gasoil 91.11 and gasoline 65.94 $/bbl in the week to
4 September 2026 as the ministry's note printed them, and 91.14 and 65.91 read
off its weekly chart; both above the same week in each of the 4 years the
weekly series covers." Each panel heading leads the same way. The comparison
with earlier years stays the chart reading's, because the earlier years are
chart readings too, and the margin by which it is above (32.93) is still said
against the chart reading. A week the note did not print keeps Part 3's form.
The panel's current year line and its end label are the reconstruction, as
before; the printed square is on it.

### C12. Provenance prints words written for a reader, not the manifest's

**What the plan said.** Part 3 section 1: "the two manual steps verbatim", and
the manifest's series ids as row labels.

**Why that was wrong.** Audit S3. The manifest is the pipeline's record for its
maintainer, and printed verbatim it put "recon 05 section 1.1", "HTTP 403 ...
from this machine", a command line with a space before its comma, "DELETES" in
capitals and snake_case ids on a public page, with the heading repeated as the
first sentence and four credits naming their source twice. It read as an
engineering log, the one thing the owner asked the page not to be. The row
labels were also the width problem of B1.

**What was built.** `provenance.json` keeps the manifest whole (SPEC.md section
5.3) and gains `reader`: `export.SERIES_READER` gives every series a label and a
source in plain words, including why two Brent rows exist and that the 283
missing Brent dates are holidays with no published price (audit M6, M7);
`export.MANUAL_STEPS_READER` says each manual step as what, why, what it costs
while not done, and how, with no internal reference; a heading and an intro
that do not repeat each other. A manifest series or step with no reader entry
raises `KeyError` in the build, so nothing new reaches the page in the
pipeline's words and nothing is silently dropped. The page prints a credit line
only when it adds to the name. The DGEC name keeps its French accents on the
page, escaped as `\u00e9` so the artifact stays ASCII; code and docs keep
writing it without them, which a reader of the page never sees.

### C13. Wide tables: caption above, off screen columns named at every width, a Provisional column

**What the plan said.** Part 3 section 5 (S6): the table's `caption` is the only
scroll affordance, ending below 600px with the columns that start off screen,
written by hand per table. Part 6 section F: the manifest's series column sticky.

**Why that was wrong.** Audit B1, B2, S1, S2, S8, all measured:
- a `caption` inside the scroll box takes the table's width, so at 375 px the
  response caption was 777px wide in a 335px box and the words naming the off
  screen columns were themselves off screen;
- above 600px nothing was said, while the manifest's Source column was off
  screen at 1440, 1280, 1024 and 768, and the response table hid Zero, Share, t
  and Months between 601 and about 1100px, where "includes zero" is the finding;
- the manifest's sticky column was a 291px unbreakable id in a 335px box, a 44px
  window; the response table's 14rem model column left 111px;
- a Tab onto a partly visible Source link did not scroll it into view, leaving
  its ring outside the box;
- no column said which months are provisional (SPEC.md section 5.3).

**What was built.** `src/dom.js` `scrollTable`. The caption is a paragraph above
the scroll box; the table names it with `aria-labelledby`. The paragraph ends
with a sentence measured from the header cells at every width and scroll
position, "The vintage and source columns are to the right.", "The columns from
2024 on are to the right." past four columns, a matching sentence for columns
scrolled off to the left, and nothing when the table fits. While the table
overflows, the box is a focusable region, so the keyboard can scroll it in
engines that do not make an overflowing box focusable; the keyboard order of
Part 3 section 9 gains that stop inside an open section, before the controls
the table holds. A control that takes focus inside the box is scrolled until its
whole ring shows. No shadow, no fade, no arrow: the affordance is still words.

At 600px and below the manifest's series label and the response table's model
name wrap inside a 9.5rem sticky column, under half of the 335px box, and the
two model equations leave that column for a list under the table, where they had
made each model row about twelve lines tall. The week by week text alternative of
a seasonal panel keeps each row on one line and scrolls. Above 600px
the manifest columns are narrowed so that at 1280px and wider the whole table
fits (1192px in a 1192px box, measured). The manifest gains a Provisional column
after Last value, from `reader.series[].provisional_segments`: "provisional:
December 2025, April 2026 and September 2026" for the printed monthly prices,
read from the ministry's own per row flag because the flags are not contiguous;
"provisional: June 2026" for the three JODI series; "none flagged" otherwise.
`tools/validate-artifacts.mjs` fails a flagged series whose words do not say
provisional.

### C14. Precision and signs

Audit M4 and M5. The waterfall scale is said in whole dollars when its ladder
ends are whole ("0 to 50 $/bbl", format `count`), not to the cent. Waterfall
totals print unsigned; steps keep their sign. `pp` prints to one place, not
three, because the one pp figure on the page is the difference of two
utilisation figures printed to one place: "+0.401" beside 78.7 and 78.3 claimed
a precision neither has. The unidentified paragraph names both kinks, "the
estimated kink moves from 2.28 to 9.87 $/bbl while the slope below it changes
sign", from `threshold_point_usd_bbl` and `threshold_without_episode_usd_bbl`.

### C15. Marks and rings that no validator measured

Audit S6, S7, M1, M2, M3.
- **The strip figure's zero rule** runs through each interval row and stops at
  the label line above the next, so it never crosses "Crude intake with a
  trend". It was one rule from the first label to the bottom.
- **Where the zero rule crosses an ink interval line** a 2px `--bg` ring sits
  under it (`.mark-accent-rule-ring`, 5.5px), the S25 rule for accent on ink.
  It is drawn only where the interval actually spans zero, so the fallback's
  lower tick, a pixel or two from the rule, is never covered.
- **Focus rings.** `.section__inner` must clip for the height motion, and it
  clipped the left 6px of every ring flush with the column. It now reaches 8px
  past the column on both sides and is padded back by 8px, so nothing moves and
  every ring is inside. The seasonal panel's grid column is `minmax(0, 1fr)`,
  because an open week table had widened the right panel past the section and
  cut its ring and its caption. A scroll box keeps 8px under its last row.
- **Words out of the figure face.** The interval cell sets its two ends in
  `span.num` and "to" in Figtree; "none", the missing dates and the provisional
  words are Figtree with tabular figures. Dates in Last value stay in mono, as
  figures.
- **Rail labels.** A label sits centred on its bracket over a plate only when
  the plate leaves 8px of line inside each end tick, so the bracket still reads
  as a span; otherwise it moves just right of the
  bracket, else just left, else onto its own line under the chart. "none" now
  sits beside week 53 instead of over the end tick of "4 prior years", and at
  375 px "2026, no second chart yet" takes a line under the rails instead of
  leaving two stubs that read as arrows.

**How all of it is held.** `tools/check-layout.mjs` measures each of these in
headless Chromium at 375, 768, 1024, 1280 and 1440 px in both themes, with every
section and text alternative open, and fails naming the finding. It is not in
`make gate`, because the gate runs without a browser or a server; `make layout`
runs it.

---

## Part 8. Gate 5 views

Part 3 section 2 settled the time series treatment and section 3 the seasonal
one, both written before any view but Now existed. Each Gate 5 view gets a
section here before it is built: what it draws, the first plan, the SPEC.md
section 0.2 test ("is this what I would produce for any dashboard rather than
this one?") applied item by item, and what changed. Parts 3, 6 and 7 still hold
wherever this part does not say otherwise.

### 8.1 History

**What the view has to show** (SPEC.md section 7.2, the Gate 5 brief). Weekly
cracks and the monthly margin from the start of the data, event markers, a range
control, a product toggle, a seasonal sub-view, structural breaks. Measured on
2026-09-17 through `crack.series` and `crack.analysis`:

```
OPEC monthly cracks, gasoil and gasoline   2000-10 to 2026-02   305 months, no gap
official MBR                               2015-01 to 2026-08   140 months
gas wedge at this study's intensity        2015-01 to 2026-08   pink sheet gas, TTF from 2015-04
weekly reconstruction                      2022-07-01 to 2026-09-11   220 weeks, 19 printed
weekly minus monthly, 44 common months     gasoil +0.92 $/bbl, gasoline -9.01 $/bbl
crack against the MBR, 134 common months   R2 gasoil 0.855, gasoline 0.551
textbook seasons, contiguous windows       gasoline May to September +4.78, t 4.64, 22 of 25
                                           gasoil November to March -0.44, t -0.59, 10 of 24
strongest gasoil months, demeaned          October +3.00, November +2.09
```

Breaks that really exist in what this view draws: OPEC's gasoline column
respecified 2004-05, 2005-03, 2008-06 and 2013-07; its gasoil column 2005-03 and
2008-06; the pink sheet gas series becoming TTF in 2015-04, which splits the gas
wedge. None on the MBR: the method in force from 2016-01-01 was recomputed back
over 2014 and 2015, and the published file starts in 2015-01. The capacity steps
of 2017-01 and 2026-01 are breaks in utilisation, which this view does not draw;
the ICE 10 ppm and Russian free changes belong to the daily layer, which is not
published. All of them come from `data/seed/events.json`, by kind.

**The first plan.** One tall chart with three stacked panels sharing a time
axis: monthly cracks, the MBR, the weekly cracks. Range buttons All, 2020, 2022,
2023 embargo, 2026, Weekly series. Event markers as numbered flags. A crosshair
readout per panel. The gas wedge as a shaded band under the MBR. Breaks as dashed
vertical rules through all three panels. The seasonal sub-view as Now's two
weekly panels plus two monthly climatology panels with the median of 25 years and
a p25 to p75 band. Events listed under the chart with their sources.

**The critique.**

- **H1. Breaks through all three panels.** Wrong for this content, the K12
  mistake in another place: a gasoline respecification in 2013 is not a break in
  the MBR, and a rule through the margin panel says it is. *Revision:* a break is
  drawn only on the panel and the line it applies to, from the event's
  `series_column`: a gasoline respecification splits the dashed gasoline line and
  its rule crosses the monthly panel only, the gas definition change splits the
  wedge line only. Breaks this view has no line for are listed under the charts
  with the reason, never drawn on a neighbour.
- **H2. The wedge as a shaded band under the MBR.** Wrong, and the most
  dangerous item in the plan: a band hanging below the margin line reads as the
  margin minus gas, which is the double count Gate 2 removed from the engine, and
  a filled area is the gradient wash's near relative. *Revision:* the wedge is its
  own small plot directly under the MBR, on the same time axis and the same $/bbl
  scale, drawn as a line of the extra gas cost, labelled "Extra gas at the
  average US refinery's use", with the sentence that the MBR is already net of
  the ministry's own 0.066 MMBtu/bbl and nothing is subtracted from it here. The
  two share x and y units so a reader can hold one against the other, and no mark
  connects them.
- **H3. Three panels on one shared time axis.** Half generic, half wrong.
  Stacked panels with a shared axis are the stock dashboard layout, and here
  they invite reading the weekly panel as the continuation of the monthly one,
  which open question 41 forbids: gasoline differs by 9.01 $/bbl because it is a
  different product. *Revision:* kept stacked, because the eye has to go from 2022
  on one to 2022 on the other; each panel has its own x domain clipped to its own
  data under the selected range, its own heading naming source and span, and the
  weekly panel carries the measured gap sentence. The panels are never drawn
  touching, and there is no shared crosshair.
- **H4. Range buttons.** Kept from K9 as named ranges, never a 1Y, 3Y, All row.
  Each window is one rule applied once, written in the export: from six months
  before the event that names the regime to twelve months after it
  (`analysis.EPISODE_MONTHS`, the episode length the regressions use), clipped to
  the data. "Weekly series from July 2022" runs from the first weekly Friday.
  **No continuous brush.** The coverage strip of S1 was designed to answer why a
  line stops; here each panel heading says its own span and an empty panel says
  why it is empty, so the strip would repeat those sentences as marks. A brush
  would let a reader cut windows no finding refers to; the named ranges are the
  windows the analysis actually uses. SPEC.md section 7.2 names "a range brush";
  this is a declared departure for the owner.
- **H5. A panel with nothing in the range.** The first plan drew an empty frame.
  *Revision:* the panel keeps its heading and says, from the artifact, what it
  does not hold: "The official margin starts in January 2015, so nothing of it
  falls in 2001 to 2002." Never a neighbour's data, never an empty axis.
- **H6. Numbered event flags always.** Generic, and a flag is decoration.
  *Revision:* Part 3 section 2's lane: the short name as a button when the names
  fit, numbers only when they collide, with a numbered list under the panel. A
  marker opens a sentence under its panel with the date, what happened and the
  source link. Until the Events view exists it says nothing about a panel there,
  and the list names no view that is not published.
- **H7. Accent.** The first plan put the accent on each panel's latest point and
  on the selected event. Two accents on the weekly panel. *Revision:* one mark
  per panel, the latest observation of the ink series the panel exists for: on
  the monthly and weekly panels a dot per product line at its last value, which
  Part 3 section 2 counts as the one latest mark; on the MBR its last month; the
  wedge plot and the event rules take none.
- **H8. The monthly seasonal band from p25 to p75 and a median.** Generic
  climatology. The textbook check is on the mean of demeaned seasons, so a
  median line would draw a statistic the sentence under it does not test.
  *Revision:* 25 complete years as `--border-strong` hairlines (decorative,
  exempt from 3.0 and said so in the chart's description), the mean of those
  years at 1.5px `--text`, end labelled "Mean of 25 years", and the season the
  sentence tests as a bracket under the axis: "May to September" under gasoline,
  "November to March, the window desks quote" under gasoil. The results are said
  as measured, the failed one in the same type as the one that holds. 2026 is not
  drawn: two months cannot be demeaned by a year's mean, and the panel says so.
  This replaces Part 3 section 3's median line.
- **H9. The seasonal toggle.** The episode years among the 25 complete years
  are 2020 and 2022; 2026 is not complete and 2023 is not an episode year in
  `analysis.SEASONAL_REMOVABLE_YEARS`. *Revision:* one toggle, "Leave out 2020
  and 2022", its text flipping to "Put 2020 and 2022 back", and the export
  carries the mean line and both test results for both states, so the page
  composes no figure. The weekly seasonal panels keep Now's treatment and the
  artifact Now reads, with Now's own restriction: no toggle until the export
  carries the sentences without 2022.
- **H10. The crosshair readout.** Kept from Part 3 section 2 because its
  evidence clause is specific to this series; on the monthly panels the clause
  is the source's own specification label for that month ("gasoil 10 ppm,
  gasoline unleaded 98"), which only this data can say.
- **H11. What the view opens on.** The first plan opened on All. Kept: the
  whole sample is the claim ("from the start of the data"), and the sample
  start is said in the lead sentence: the owner chose 2001, so the cracks run
  from October 2000 while the margin runs from January 2015, and nothing extends
  the margin back.

**What survived.** Stacked panels (with H3's limits), end labels, the readout,
the printed squares and evidence rail on the weekly panel, named ranges,
checkboxes for products, the list of events with sources.

**The banned list, for this view.** No legend (end labels), no tooltip card (a
readout line), no fill under any line, no hue for a product, no arrow on a range
button or event marker, no pressed fill (underline and weight, S4), no text on a
hatch or a plot area, no month name in JetBrains Mono (month and year labels
that are words are Figtree; only numeric ticks are mono).

**As built, and measured.** Three things moved during the build, each found by
`tools/check-layout.mjs` check H or by looking at the page. Numbered lane markers
that still touch (2022 has four events inside eight months) stack in a second or
third row rather than overlapping, the lane growing to hold them. The "Mean of 25
years" label sits inside the plot, right aligned above the line's end on a `--bg`
halo, because at 375 px it ran 26 px past the chart. The least defended hatch is
labelled in the rail beside it, as on the Now seasonal panels, not in the event
lane. The view is in the nav and the router; `tools/check-layout.mjs` measures
`#/history`, `#/history?range=2022` and `#/history?sub=season` at 375, 768, 1024,
1280 and 1440 px in both themes, and `scripts/screenshots.mjs` photographs five
History states.

### 8.2 Model

**What the view has to show** (SPEC.md section 7.2 and section 12). The
calculator: four presets, latest month, 2019 average, October 2022 and July
2026; every input editable, cracks, yields, TTF, EUR/USD, gas intensity and
other variable cost; a live recompute with the waterfall updating in place; the
breakevens in the units a desk quotes, $/bbl for cracks and margins, EUR/MWh for
gas. SPEC.md section 12: "I open the Model, raise TTF, and watch the margin after
gas and the headroom fall in place." The arithmetic is `src/engine.js`, the
mirror proven to 1e-9; the view calls it and implements no formula of its own.

What the committed data allow, measured on 2026-09-17 from the caches:

```
ministry's final printed monthly prices   2025-11, 2026-02, 2026-03, 2026-08, five products
                                          (2025-12, 2026-04, 2026-09 provisional; no July 2026)
OPEC Rotterdam monthly, $/bbl             to 2026-02; gasoil, premium gasoline, jet, fuel oil 1%,
                                          no heating oil column
weekly reconstruction, July 2026          five weeks to 3, 10, 17, 24 and 31 July, none printed,
                                          every one "no second chart yet"; Gazole, Eurosuper and
                                          Fioul domestique only
World Bank European gas, $/MMBtu          to 2026-08, TTF by the publisher's definition from 2015-04
FRED EUR/USD daily                        to 2026-09-04
the ministry's MBR                        2015-01 to 2026-08, net of its own gas at 0.066 MMBtu/bbl
```

**The first plan.** The Now waterfall with inputs beside it. The product rows,
the residual, the official margin with the accent, the gas wedge, the total at
the study's intensity, every row recomputed live. A TTF slider and a gasoil
slider over a range from the sample. Four preset buttons. A breakeven table:
breakeven TTF and breakeven gasoil against the run cut threshold, and the
headroom. Inputs as number fields with min and max.

**The critique.**

- **M1. The Now waterfall is the wrong chain for a calculator, and dangerous.**
  Its total is the ministry's MBR, which is already net of the ministry's gas,
  and its residual is the MBR less the products. Feed a TTF into that chain and
  the page subtracts gas from a margin that contains gas, the double count Gate
  2 removed from the engine (`GasDoubleCountError`). *Revision:* the model
  builds its own margin, the ministry's slate yields times the cracks, and
  nothing else, on `MARGIN_GROSS_OF_GAS` with no residual. That margin is gross
  of gas, so subtracting gas from it is correct. The chain is: the product
  steps, "Gross margin of this model, before gas", the gas step, the other
  variable cost step, "Margin after gas of this model". The view says in its
  lead, before any input, that this is a model margin and not the ministry's
  MBR.
- **M2. The official margin in the chain.** Drawn as a total inside the model
  chain, the MBR reads as the model's answer. *Revision:* a second block under
  the first, on the same scale, labelled as a comparison and never a step of the
  model: the model's gross margin, then "The ministry's MBR less this gross
  margin", then the MBR for the preset month, "already net of the ministry's own
  gas". The gap is `decomposeOfficial(mbr, yields, cracks).residualUsdBbl` from
  the engine, the same residual the Now view prints, so it moves when a crack is
  edited, and its second line says what it holds: the unpriced part of the
  barrel, the ministry's gas, freight and insurance, and, where the preset's
  prices are not the ministry's, the difference between sources.
- **M3. The accent.** Part 3 section 4 put the accent on the preset month's
  official margin. Wrong once M2 moves the MBR out of the chain: the one thing
  this view exists for is the number that falls when TTF rises. *Revision:* the
  accent is on "Margin after gas of this model" and nowhere else; the MBR total
  is ink.
- **M4. Headroom against a run cut threshold.** The threshold is unidentified
  (Gate 3), so a breakeven against it, a headroom figure, or a slider "to the
  run cut level" would print a number the study does not have. *Revision:* the
  breakevens are computed against a margin of zero, which the artifact carries
  as `breakeven_target` with the words "a margin of zero, not a level at which
  runs get cut"; the engine is called with that target and never with an
  invented one. In the breakeven table the row where the run cut level would sit
  says "unidentified", in the same size as the figures beside it, followed by
  the Now view's unidentified paragraph, from the same export function. What
  falls in place when TTF rises is the margin after gas and its distance to
  zero; the page says so rather than promising headroom.
- **M5. Sliders.** A slider over the sample's range is the what if widget of
  every dashboard, needs a min and max the page would have to type, and moves a
  figure through values nobody chose. *Revision:* labelled text fields with
  `inputmode="decimal"`, the unit in the label, one per input, the preset value
  in each. No slider, no spinner, no min or max attribute.
- **M6. Presets whose data do not exist as SPEC.md names them.** A preset button
  that loads "July 2026" and quietly fills jet from another month is exactly the
  neighbour substitution SPEC.md section 2 forbids. *Revision:* every preset
  records, per input, where the value came from, and the page prints that
  source line under its field. Missing products are empty fields that say why
  ("No figure for July 2026: the weekly reconstruction reads Gazole, Eurosuper
  and Fioul domestique only"), their waterfall row says "Not priced" in the bar
  cell, and they are left out of the margin, which then covers less of the
  barrel and says how much less. July 2026 is labelled reconstructed on the
  preset itself, with its weeks counted and the printed ones among them
  counted. 2019 is an average of twelve OPEC months and says so; its TTF is
  derived from the World Bank's $/MMBtu and FRED's EUR/USD, never the Yahoo
  daily series, and says so; its MBR is the mean of the twelve published months
  and says that too.
- **M7. Nonsense inputs.** min and max attributes would clamp or block quietly,
  and would need figures typed into the page. *Revision:* the engine computes
  whatever it is given, and the page says what the engine did with it, under
  the form, in a sentence per condition: yields above one barrel, a negative
  yield, a negative gas intensity, TTF or EUR/USD below zero, a field that is
  not a number. An empty or unreadable field is a missing input, never a zero: a
  missing crack or yield leaves that product out and says so; a missing TTF,
  EUR/USD, intensity or other cost leaves the margin after gas uncomputed and
  says which input stopped it.
- **M8. Preset buttons named by a date alone.** "Oct 2022" is a date picker.
  *Revision:* each button is the month, and the reason it is on the list sits
  under the row for the pressed preset, from the artifact: October 2022 with the
  French refinery strikes, the S&P Global reference in `events.json`; 2019 as
  the last full year before the pandemic lockdowns; July 2026 after the strikes
  on Iran; the latest month as the latest month with the ministry's margin and
  its final monthly prices. Pressed state as Part 6 S4: underline and weight,
  `aria-pressed`, never a fill.
- **M9. Motion.** The recompute is the second item of the motion table: bar
  geometry tweens at `--t-fast`, figures swap at once. The bars are updated in
  place, not redrawn, so the tween has something to move, and the portfolio's
  reduced motion block already takes the duration to 0.01ms. A bar that becomes
  narrower than 4px changes to the small step circle at once, because a
  rectangle cannot tween into a circle.
- **M10. The scale.** A live recompute on a fixed scale runs off the table; a
  scale refitted on every keystroke moves every bar at once, which reads as a
  change in every line. *Revision:* the preset's scale, widened on the 1, 2, 5
  ladder only when an edit runs past it, and never narrowed during edits. The
  scale sentence says the current scale.

**What survived.** The waterfall as a table with bars in a cell, its marks,
small steps and 600px layout from Part 3 section 4; four presets; a short
breakeven table.

**The banned list, for this view.** No slider, no card around the form, no
fieldset frame (groups are separated by space and a sentence heading, S9), no
tinted input group (the one allowed use of `--bg-elev` is the field background,
Part 3 section 7), no pressed fill, no arrow on "Put back" or a preset, no
figure animated through values, no JetBrains Mono in a field (a field is not a
table figure; Figtree with tabular figures).

**The parity.** The numbers the page prints for each preset are the numbers
crack.engine computes for the same inputs, to 1e-9: `src/model-calc.js` is the
one function the view calls, `scripts/gen_model_cases.py` records what Python
computes for each preset in `data/model.json` into
`data/fixtures/model-cases.json`, and `tools/validate-engine.mjs` runs
`src/model-calc.js` over it.

**As built, and measured.** `src/model.js` on `data/model.json`, computing only
through `src/model-calc.js`, which `tools/validate-engine.mjs` holds to the 32
cases of `data/fixtures/model-cases.json` (four presets, seven named edits each)
at a largest parity difference of zero. Five things moved during the build.
The bars are `charts.liveWaterfallBar`, built once per row and moved by a CSS
transform and the CSS width property, because `x1` and `x2` on a line are not
properties a transition can tween; a change of cell size moves them with the
tween off. A field still showing the text the preset put there computes with the
stored value, not the rounded text, so an untouched preset is exactly its case.
The July 2026 button says "reconstructed, 5 weeks, none printed" under the month,
counted from the artifact. Below 1024 px the waterfall sits under the whole form,
so the margin after gas sentence is repeated under the gas fields (hidden from
assistive technology, which hears the live one); that is SPEC.md section 12's
"watch it fall in place" at phone width, where the bars themselves are a scroll
away. The run cut row's "unidentified" is a right aligned word at the figures'
size, never mono. `tools/check-layout.mjs` check MV measures `#/model`, July 2026
and 2019 at 375, 768, 1024, 1280 and 1440 px in both themes: one accent figure
and one accent bar, no MBR row in the model chain, "unidentified" and no figure
after the word headroom, no slider and no min or max, no mono field, "Not priced"
for July's jet and fuel oil, every bar inside its cell, then TTF doubled lowers
the margin after gas on the same bar node with the MBR unchanged, text in a field
prints no NaN, and "Put back" restores the preset. It was checked to fail when a
figure was planted after "Headroom". `scripts/screenshots.mjs` photographs five
Model states.

### 8.3 Runs and crude demand

**What the view has to show** (SPEC.md section 7.2 and section 12).
Utilisation and crude imports against the lagged margin after gas, the scatter
with the hockey stick fit and its interval, the response table, the horse race,
the instrument result, and residuals with 2022 and 2026 highlighted. SPEC.md
section 12: "read, with an interval, how many kb/d of crude demand a 10 $/bbl
margin move is worth, and an honest sentence on whether the margin beat the raw
gasoil crack." Everything is `crack.analysis` as audited at Gate 3; the export
writes it and the page fits nothing. Measured on 2026-09-17:

```
response, 135 months 2015-04 to 2026-06   planned model +0.09512 se 0.28582 t 0.33, +59.3 kb/d, -290.1 to +408.8
                                          intake with a trend +0.44391 se 0.22147 t 2.00, +230.4 kb/d, +5.1 to +455.6
                                          capacity steps 2017-01 and 2026-01, 88.9 percent of the gap
threshold, 135 months                     kink 2.28, interval 2.03 to 11.28, search -0.22 to 11.28, slope below +3.88
                                          24 months below the kink, 21 of them one stretch, 2020-07 to 2022-03
without that stretch, 114 months          kink 9.87, slope below -0.50, 101 months below
horse race, 132 common months             72 forecasts 2020-04 to 2026-03, all in or after the pandemic
                                          power 0.050 to 0.121 against a size of 0.050, 6 pairs on two equations
                                          forecasts for 95 percent power 1,570 to 670,408
horse A alone, 288 months from 2002-04    reported beside the race, never in it
instrument, first stage F by control set  5.75 constant, 5.80 month dummies, 0.215 episode dummies, 0.070 trend
                                          sd in episode months 18.61 $/MMBtu, outside 5.31, peak 60.16 in 2022-10
2026                                      4 post break months against a bar of 12, not tested
imports over intake, 138 months           95.4 percent on average, 86.4 to 103.9
JODI                                      2002-01 to 2026-06, June 2026 provisional; the margin from 2015-01
```

**The first plan.** One long page: the Now section's four blocks at the top,
then a dual axis chart of utilisation and the lagged margin, the scatter with
the fitted kink as an accent line and its interval as a shaded band, a
regression table per equation with stars, the horse race table sorted by out of
sample RMSE, a first stage F badge coloured by the bar of 10, and a residual
bar chart with 2022 and 2026 bars in the accent.

**The critique.**

- **R1. A dual axis chart of utilisation and the margin.** The stock move of
  every macro dashboard, and wrong here: two y scales make any two series look
  related by choosing the ranges, which is the claim this view exists to test.
  *Revision:* separate plots on their own scales, as History does (H3):
  utilisation with the capacity steps it carries drawn as breaks, the lagged
  margin, and crude intake with crude imports on one kb/d scale, solid and
  dashed, end labelled. The plots start in January 2015, where the margin
  starts; the lead says JODI reaches back to 2002 and that nothing extends the
  margin.
- **R2. The kink as an accent line with a shaded interval band.** A fitted line
  in the accent says "here is the level", which is the one thing Gate 3 did not
  find, and a single fit hides why. *Revision:* Part 3 section 5's scatter as
  written: two fits in ink, every month dashed and the months without the
  stretch dotted, end labelled with their kinks; the 21 months of the stretch as
  filled squares and the rest as hollow circles; the interval as a flat span
  with no text on it that runs to the right edge of the search because the
  interval does, with that edge a rule labelled above the plot. No accent,
  because the thing it would mark does not exist, and the heading says so. The
  counts 24 and 21 are printed, because the export now carries them (S29).
- **R3. A regression table per equation, with stars.** K20: stars make t 2.00 a
  finding and t 1.98 not. *Revision:* the Now view's strip and table, reused
  from `src/section-runs.js` so the two pages cannot disagree, the planned model
  first (K24), then the reason they differ. Added here: SPEC.md section 6.1's
  "with and without the episodes" as one table, and under the coefficients the
  sentence that endogeneity biases toward zero, so each is a lower bound in
  absolute value. It sits where the coefficients are, not in a limitations list
  at the end.
- **R4. The horse race sorted by RMSE.** K21, and worse here: the lowest RMSE is
  a different horse on each equation. *Revision:* rows A, B, C in SPEC.md's
  order under each equation, no bold, no accent, no sort; the lowest RMSE is not
  marked. The sentence above the tables is "this sample cannot tell the horses
  apart" with the power range and the size beside it; the power table puts the
  observed gap beside the smallest detectable gap, a strip per pair with the
  size as the accent tick, and the forecasts that 95 percent power would need.
  Horse C's second line says it is a substitution and why. Horse A on its own
  longer sample is a row under a note row, outside the race.
- **R5. "Did the margin beat the crack" as a verdict word.** A badge, a tick or
  the word "no" in display type turns an underpowered test into a result.
  *Revision:* SPEC.md section 12's honest sentence assembled from fields: the
  margin did not beat the raw gasoil crack and was not beaten by it, and the
  reason is power, not equality. Then SPEC.md section 6.3's paragraph, in body
  type: what the margin gives that the crack cannot, a level with a sign, the gas
  wedge (measured before and during 2022) and a threshold in dollars if one is
  ever identified, which on this sample it is not.
- **R6. An F badge coloured against the bar.** A traffic light, and it states
  the F as a property of the instrument. Gate 3 measured it as a property of the
  control set. *Revision:* the control ladder as a table, four rows in the order
  the controls go in, each row saying which equation uses it; then the sentence
  that the episode dummies remove the 2022 shock that is the instrument's
  variation, with the standard deviations in and out of the episode months. The
  two stage estimates are printed as not used, beside the ordinary least
  squares ones.
- **R7. Residual bars with 2022 and 2026 in the accent.** Colour as the only
  highlight, and the accent on 2026 says something happened there when the
  study returns no verdict. *Revision:* the residuals of the equation fitted on
  months before March 2026 with no episode terms, the in sample months a solid
  line and the four months after the break a separate dashed line with squares,
  never joined; 2022 and 2026 as labelled brackets in the rail under the axis,
  the bracket the seasonal panels use. No accent. The table of the four months,
  reused from the Now section with the provisional word, and the sentence "not
  tested, 4 months against a bar of 12".
- **R8. Everything open on one page.** Nothing on screen the visitor did not ask
  for (SPEC.md section 12). *Revision:* the lead answers the question the view
  is named for (the response on both equations with intervals, the honest horse
  race sentence, the unidentified paragraph), then four parts behind a choice
  row, each linkable: Response, Run cut threshold, Horse race and instrument,
  2026. The Now section's link "Open Runs and crude demand" opens the first.

**What survived.** The Now section's strips, table and post break table, reused
and not copied; the scatter treatment of Part 3 section 5; the horse race and
power tables of Part 3 section 5; the choice row and sub view pattern of History.

**The banned list, for this view.** No dual axis, no significance stars, no
sort control, no bold or accent on a horse, no badge, no traffic light, no
shaded band with text on it, no accent on the scatter or the residuals, no
legend (end labels), and none of the words winner, wins, best, tie, dead heat or
equivalent on the page.

### 8.4 Events

**What the view has to show** (SPEC.md sections 6.5 and 7.2). "The minus 6 to
plus 6 month panels, one per event, opened by clicking a marker in History or
picking from a list." Around each event, the cracks, the margin after gas and
utilisation, from six months before to six months after. Every panel links its
source. Measured on 2026-09-18 from `data/seed/events.json` through
`crack.sources.events_anchors`, and from the caches the other views read:

```
events with a panel         10: kinds market, policy and reference, in date order,
                            2020-01-01 to 2026-04-07; nine dated to the day, the
                            lockdowns to the month (the seed's date_note says why)
entries without a panel     the specification breaks, the gas definition changes, the
                            MBR method date and the two ICE daily layer changes;
                            they are breaks, listed in Method with where each is drawn
the stock release           11 March 2026, precision day, pinned from two IEA pages
                            (SPEC.md wrote 2026-03 and asked for the day)
OPEC monthly cracks         2000-10 to 2026-02: the three 2026 windows lose their
                            last months
official MBR                2015-01 to 2026-08: every window here is inside its start
utilisation, JODI over EI   2015-01 to 2026-06, June provisional; the analysis frame
                            the Runs view reads, capacity steps 2017-01 and 2026-01
weekly reconstruction       2022-07-01 to 2026-09-11: the 2020 and three 2022 windows
                            hold none or part of it, the six oldest weeks hatched
```

**The first plan.** A grid of ten small multiples, one card per event, each with
the three series on one chart and a left and a right axis, the event at zero,
every series indexed to 100 in the event month, a "change from minus one to plus
one" figure under each card, and a dropdown to pick an event.

**The critique.**

- **E1. Ten cards in a grid.** The rounded card for every block, the first item
  of the banned list, and ten charts on screen that nobody asked for (SPEC.md
  section 12). *Revision:* one event open at a time. The view opens on the list
  alone; a list item or a History marker opens that event's panel under it, and
  the address says which, `#/events?event={id}`, so a panel is linkable. No
  frame, no tint: a panel is a heading, a sentence, its plots and a table.
- **E2. Three series on one chart with two axes.** The dual axis that R1 threw
  out of the Runs view, for the same reason: two scales make any two lines look
  related by the choice of ranges. *Revision:* the plots are stacked, each on its
  own scale and unit, on one shared x axis of the thirteen months, the way
  History stacks its panels (H3): cracks in $/bbl, the margin after gas in
  $/bbl, utilisation in percent.
- **E3. Indexed to 100 at the event.** The event study chart of every research
  deck, and wrong here twice: it hides the level, which is what a desk reads (a
  crack at 44 is a different market from a crack at 14 even when both rose by
  half), and an index is a number the data does not contain. *Revision:*
  levels, in the source's units. The x axis is labelled in months from the
  event, numeric ticks in JetBrains Mono (minus six to plus six, thinned on the
  1, 2, 5 ladder so zero is always labelled), and the calendar month of every
  point is in the table and in the plot's description.
- **E4. "Change from minus one to plus one" under each panel.** It reads as the
  event's effect, which the window cannot identify: other things happened in the
  same months (2022 has four events in eight months) and SPEC.md section 6.6
  forbids anything that looks like a signal. *Revision:* no computed change, no
  before and after mean. One sentence under the heading: the panel shows what
  moved around the date, not what the event caused.
- **E5. The event at zero as an ordinary gridline.** A day precision event and a
  month precision one would be drawn the same, which claims a precision the
  lockdowns do not have. *Revision:* the event is the one thing each plot is
  for, so it takes the accent: a 1px accent rule at the day for an event the
  source dates to the day; for one dated to the month, no rule, a bracket in the
  rail under the axis spanning that month and labelled with the month. The
  seed's own date note is printed under the heading, so the IEA release says it
  is pinned to 11 March from two IEA pages.
- **E6. A window shortened to the data.** The easy failure: the 2026 windows lose
  their monthly cracks after February 2026 and a chart that starts and stops
  where the data do would look complete. *Revision:* the x axis always runs the
  full thirteen months. Missing months are null in the artifact and drawn as the
  site draws every gap (no line, a dotted segment on the baseline, Part 3
  section 2), and a sentence under the plot names the series and why: "OPEC's
  monthly cracks stop at February 2026, so the 6 months from March 2026 to
  August 2026 in this window have none; nothing fills them." A series with
  nothing in the window keeps its heading and says so instead of an empty
  frame (H5). Months after the latest data the study holds are "not in the data
  yet", said once, not a series failure.
- **E7. The weekly cracks spliced onto the monthly line where both exist.**
  Forbidden by open question 41 and by H3. *Revision:* the cracks plot draws
  OPEC's monthly cracks only, gasoil solid and gasoline dashed as everywhere;
  the weekly reconstruction is its own plot under it, on the same x axis, drawn
  only in windows that reach July 2022, with the evidence rail (the six oldest
  weeks hatched, the newest bracketed) and the printed weeks as squares. The
  2020 windows say, by name, that the weekly series starts on 1 July 2022.
- **E8. The margin after gas as one line.** Two figures are "after gas" on this
  site and one line would have to pick: the ministry's MBR, already net of its
  own 0.066 MMBtu/bbl, and the same margin at the average US refinery's 0.212.
  Subtracting gas from the MBR is the double count Gate 2 removed. *Revision:*
  both, end labelled, the ministry's solid and the US gas use dotted (the dash
  is gasoline's, so it is not reused for a margin), and the sentence under the
  plot says both are after gas and nothing is subtracted twice.
- **E9. Utilisation as one continuous line.** Two capacity steps sit inside the
  sample, one in January 2026, inside the three 2026 windows. *Revision:* the
  line splits at the step with the dashed break rule, as on the Runs view, and
  provisional months carry the word in the table.
- **E10. A dropdown to pick the event.** A select hides nine of ten choices and
  says nothing about each. *Revision:* the list is the picker: ten links in date
  order, each with its date at the precision the source gives, its short name,
  and a coverage clause from the artifact that names every series missing from
  its window, so a reader sees before opening that the lockdown window has no
  weekly series. The open event is `aria-current`, underline and weight, never
  a fill (S4).
- **E11. History's markers.** Until now a marker opened a sentence under its
  panel (H6). *Revision:* a marker now opens its event's panel here, and the
  numbered list under each History panel links it too.

**The banned list, for this view.** No card, no dual axis, no index to 100, no
change figure, no fill under a line, no legend (end labels), no dropdown, no
arrow on a list link, no text on the plot area, no month name in JetBrains Mono,
and nothing reading as cause: the words "impact" and "caused" do not appear on
the page, and "effect" only in the sentence that denies it.

### 8.5 Method

**What the view has to show** (SPEC.md section 7.2, the Gate 5 brief).
"Formulas, the assumptions table with a source per row, product definitions,
structural breaks, limitations, reuse terms." It is also where the study shows
its work: the departures from SPEC.md with their evidence, the measured cross
checks, the weekly reconstruction and its error, the two manual steps, and the
fields the Gate 4 audit found exported and never rendered (section 8 of the
Gate 4 self audit: the ICE factor citations, the printed $/t prices, R2 and the
Newey-West lag). Measured on 2026-09-18 through `crack.config`, `crack.series`,
`crack.analysis` and the manifest:

```
factors            gasoil 7.45, gasoline 8.33, jet 7.88, heating oil 7.45, fuel oil 6.35,
                   each an ICE contract conversion factor read on 2026-09-16
DGEC Brent         7.5 in the weekly note's $/t table (measured), 7.55 in the MBR (stated)
gas                3.412142 MMBtu/MWh; 0.21217 MMBtu/bbl from four EIA 2023 figures;
                   the ministry's embedded 0.06590; ratio 3.22
Brent check        140 of 140 months within 1.5 $/bbl, worst 0.26
MBR anchors        9 of 9 reproduce (SPEC.md's eight and August 2026 final)
triangulation      October 2022, 6.23 $/bbl on the 3.5 percent fuel oil row, 5.51 on
                   the 1 percent row, against S&P's about 7
implied bbl/t      44 months 2022-07 to 2026-02: gasoil mean 7.5283 (7.3080 to 7.8191),
                   gasoline mean 7.7184 (6.9370 to 8.3334) against 8.33
replication        7 months of printed prices, 8 inputs unpublished, never within 0.50
Brent bound        25 FRED prints below 10 $/bbl, 1998, 1999 and 2020, so 5 and not 10
reconstruction     leave one series out 0.17 to 0.44 $/t; note pairs 0.30 mean, 1.68 worst;
                   a 10 point tilt moves the oldest week 73.49 $/t
Newey-West         lag 4 on 135 months, at least 3 by SPEC.md section 6.1
```

The implied factors recomputed here from the committed caches, by the calendar
month mean of the weekly reconstruction over OPEC's monthly $/bbl, give 7.5283
and 7.7184; `config.py` quotes 7.5285 and 7.7185 from the Gate 1 computation.
The page prints what the export computes, never the comment.

**The first plan.** One long page of headed sections with every formula in a
code block in JetBrains Mono, a sticky table of contents in a left sidebar, a
big assumptions table, "Tip" and "Warning" callout boxes for the departures, and
each source's licence as a badge.

**The critique.**

- **D1. Formulas in a code block in the mono face.** The mono face is for
  figures in tables and on axis ticks only (SPEC.md section 0.2), and a code
  block turns a definition into something to copy into a terminal. *Revision:*
  each formula is a line in Figtree with tabular figures and plain operators,
  "gasoil crack = gasoil price in $/t / 7.45 minus Brent in $/bbl", every
  constant a value from the artifact, and under it one sentence on what it is
  and is not.
- **D2. A sticky sidebar table of contents.** The documentation site layout;
  at 375 px it either disappears or eats the column. *Revision:* an ordered list
  of links at the top of the view, in the text column, each one an address,
  `#/method?section=assumptions`, so a section is linkable the way every other
  view's state is and the router is not fooled by a bare fragment. Opening one
  scrolls to its heading and moves focus there.
- **D3. Callout boxes for the departures.** Tinted boxes with an icon are the
  "same rounded card" and a coloured alarm. The departures are the most
  important part of the page and must not look like asides. *Revision:* a
  section of their own, second after the formulas, each departure a sentence
  heading and a paragraph in body type: what SPEC.md says, what this study did,
  and the evidence, with the primary source quoted where one exists (the MBR's
  own method note, in French, with its URL).
- **D4. One assumptions table with everything.** Mixing contract factors, unit
  definitions, derived intensities and rules in one table puts "3.412142" next
  to "the monthly averaging rule" and makes the source column a mix of links and
  essays. *Revision:* one table of constants, each row the name in words, the
  value, where it is used and the source as a link; then the two derivations
  that need their working, the gas intensity and the ministry's embedded gas, as
  small tables of inputs with their sources; then the rules (monthly averaging,
  the percentile window, the Newey-West lag, the validation bounds) as a list of
  sentences. The August 2026 decomposition prices, per product the printed $/t,
  the factor, its ICE citation and the crack it gives, are read from
  `data/margin-stack.json` itself, and R2 and the Newey-West lag of each
  response equation from `data/run-economics.json`, so the fields the audit
  found orphaned are rendered from the artifacts that own them rather than
  copied.
- **D5. Licences as badges.** A badge per source is decoration and cannot hold a
  third party caveat. *Revision:* a table, source, credit line, terms, and the
  third party note in words, read from `data/provenance.json`, plus the font
  disclosure as a sentence: Figtree stands in for Satoshi because Satoshi's
  licence does not allow a copy in a public repository.
- **D6. Cross checks as green ticks.** A tick says "passed" and invites no
  reading of the size. *Revision:* a table, check, what was compared, the result
  in figures and what it means, with the one that is not comfortable (gasoline's
  implied 7.72 against 8.33) in the same weight as the ones that are, and why
  8.33 was kept said beside it.
- **D7. Limitations as a bullet list at the end.** Kept as a list, because each
  is a separate statement, but written as sentences with their figures, and the
  weakest results lead: the unidentified threshold, the race this sample cannot
  decide, endogeneity, the weaker gasoline leg, the heating season that does not
  hold, the 2026 months too few to test, then scope (carbon costs, the US gas
  intensity as an upper end, the unpublished inputs) and the two manual steps.
- **D8. Structural breaks restated in prose.** *Revision:* the same break list
  History draws, read from `data/history.json`, with where each is drawn or why
  it is not, plus the capacity steps, so the two views cannot disagree.
- **D9. Nothing makes an unread field fail.** The audit found orphans by hand.
  *Revision:* `tools/validate-artifacts.mjs` walks every key of every artifact
  and fails when a key is read by no module in `src/`, unless it is on a short
  declared list of supporting fields with the reason each is not printed; the
  four the audit named are not allowed on that list, and a listed key that a
  module starts reading fails too, so the list cannot go stale.

**The banned list, for this view.** No callout box, no icon, no badge, no code
block, no sidebar, no mono outside table figures, no "note:" or "warning:" label
above a paragraph, no all caps.
