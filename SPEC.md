# Build spec: NWE crack spread study and site

Build a public, reproducible study of Northwest European (NWE) refining margins: a Python pipeline that tracks the gasoil and gasoline cracks, the refining margin they add up to, what that margin is worth after gas costs, and how it feeds through to refinery runs and therefore to crude demand; plus a static site that lets a commodity trading professional interrogate it. It is a portfolio artifact and it must sit consistently alongside the repositories that already exist on the same GitHub profile.

Read this whole file before writing any code. Work through the phase gates in section 10 and stop at each one for approval.

---

## 0. Where this sits

- **Owner:** `nathancouturier` on GitHub
- **Repo name:** `crack-spread-study`, public
- **Live URL:** `https://nathancouturier.github.io/crack-spread-study/`
- **Sibling repos:** `nathancouturier.github.io` (the personal portfolio), the Baltic Exchange routes map, and `lme-comex-arbitrage-model` if it exists when you start. Open them before writing code and list the conventions they share. Where they disagree with this spec on structure or style, the repos win and you tell me. Where they disagree on data integrity, this spec wins.

### 0.1 Conventions to match

| Convention | Rule |
|---|---|
| Build step | **None.** Plain HTML, CSS and vanilla ES2020 modules. No bundler, no framework, no npm install to run the site |
| Data | All site data in `/data` as JSON loaded with `fetch`. Never hardcode data inside JS modules |
| Vendored libraries | Pinned files in `/vendor` with their licences. No CDN links |
| Pages serving | The site lives at a **subpath**, not the domain root. Every path relative. Verify it from the subpath, it is the most common way this deployment breaks |
| Jekyll | Ship a `.nojekyll` file |
| Validators | Standalone scripts in `/tools`, runnable with plain `node`, each documented in the README |
| Docs | A `/docs` folder with `sources.md`, `methodology.md`, `open-questions.md` |
| Private data | `data/private/` is gitignored, never committed, never deployed |
| Dashes | No em dashes or en dashes anywhere: code, comments, copy, README, commit messages. Use commas |

### 0.2 Design system, inherited deliberately

The portfolio sets the identity. Its `styles.css` is the single source of truth: copy its custom properties verbatim into `styles/tokens.css`, and load fonts exactly the way the portfolio does. Last known values, for reference only: paper `#FBFAF8`, ink `#17181C`, accent `#8E2B2B`, light theme by default with a complementary dark theme; **Fraunces** for display, **Satoshi** for body, **JetBrains Mono** for figures. If `styles.css` says otherwise, `styles.css` wins. If `lme-comex-arbitrage-model` uses a different palette, report the mismatch at Gate 1 instead of choosing silently. Support the theme toggle the way the portfolio does.

Do not redesign the identity. Your one judgement call is how to use it for dense time series, a waterfall and regression tables, which the portfolio does not contain. Constraints that come from the content rather than taste:

- Figures use lining tabular numerals so columns align. JetBrains Mono is for figures in tables and on axes only, never for labels, captions or prose.
- Density is correct here. This is an analytical screen, not a landing page. Whitespace that pushes the data below the fold makes it worse.
- Gasoil and gasoline must be distinguishable without colour: line style plus a direct label at the end of each line, no legend hunting. The accent marks the one thing that matters on each chart, such as the latest value or the threshold, never decoration.
- Positive and negative values are distinguishable without relying on colour alone.
- Motion only in answer to an action: a section opening, a number updating when an input moves. No entrance animations, no scroll reveals, no hover lifts.
- Banned: all-caps labels, eyebrow labels above headings, meta strings joined with middle dots, arrows appended to buttons or links, glassmorphism, noise overlays, gradient washes, heavy shadows, the same rounded card for every block, watermarks, AI tags.

Before writing CSS, write a short plan for the chart, waterfall and table treatment and critique it against this brief. If any part of it is what you would produce for any dashboard rather than this one, revise it and say what you changed.

---

## 1. The CV line this has to earn

> **Crack spread study:** tracked NWE refining margins across gasoil and gasoline cracks, and linked run economics to crude demand.

Somebody will read that line, open the repo and check it. Each clause must be visible within ten seconds of landing:

| Clause | Where the visitor finds it |
|---|---|
| tracked | Weekly series refreshed by a scheduled job, with the data date on screen |
| NWE refining margins | The official Rotterdam margin on Brent, plus this study's decomposition of it |
| across gasoil and gasoline cracks | Two named, first-class crack series, each with its seasonal view and its contribution to the margin |
| run economics | The margin after gas cost, the level at which runs get cut, and today's headroom to it |
| linked to crude demand | The refinery crude intake response to the margin, in kb/d per $/bbl, with its confidence interval |

- **Do not claim more than the line does.** No trading strategy, no signals, no Sharpe ratio, no price forecast, no backtest P&L.
- **Do not claim less.** If "run economics" or "crude demand" cannot be found as a first-class section within ten seconds, the site has failed its only job.
- The README opens by restating the bullet, then says what the study cannot do, then what it does.

---

## 2. Non-negotiables

These override any feature in this spec.

1. **Never invent market data.** A failed source or a missing date becomes `NaN`, is recorded in the manifest and is surfaced in the UI. No silent interpolation, no synthetic series, no filling from a neighbouring source without labelling it.
2. **Every number in the browser comes from a JSON artifact.** No numeric literals in the frontend except unit constants. Verify by grepping.
3. **Report results whatever they are.** If the raw gasoil crack explains runs as well as the margin after gas, the page says so in plain words.
4. **The study is allowed to find nothing.** If no stable run cut threshold exists in the sample, say so, and do not tune until one appears.
5. **Provisional is labelled provisional.** The current month in the ministry notes is provisional and gets revised. Keep every vintage, show the flag.
6. **Respect each source's terms.** Record reuse terms per source in `docs/sources.md`. Anything that cannot be redistributed stays in `data/private/`, and only the derived outputs its terms allow are published. Raise any doubt at Gate 1.
7. **Do not ship with failing tests or validators.** The CI gate is the deploy gate.
8. **Flag what you are unsure about.** An honest gap beats a plausible fabrication, because the audience will spot an invented number immediately.

---

## 3. The market, briefly

A refinery buys crude and sells products. A crack is one product's price minus the crude price, per barrel. NWE, around the Amsterdam, Rotterdam and Antwerp (ARA) hub, is where Europe's product benchmarks are set: ICE Low Sulphur Gasoil futures deliver diesel barges into ARA, and Eurobob barges are the gasoline reference. Refiners run harder when the margin pays and cut runs when it does not, and because refinery crude intake is crude demand, margins transmit into crude buying with a lag. European refiners also buy natural gas for fuel and for hydrogen, so the same crack is worth less to them when TTF is high.

The sample contains regimes the site must explain, not delete:

- **2020:** the pandemic demand collapse.
- **2022:** Russia's invasion of Ukraine, record diesel cracks and a gas price shock. S&P Global reported European diesel cracks averaging about 44 $/bbl in the week to 25 March 2022, ARA diesel cracks near 80 $/bbl on 13 October 2022 during French refinery strikes, and gas-fired refiners earning about 7 $/bbl less than fuel-oil-fired ones at that point.
- **2023:** the EU embargo on Russian refined products from 5 February 2023. ICE Gasoil delivery excludes Russian-origin barrels from the end of 2022.
- **2026:** US and Israeli strikes on Iran from 28 February 2026, tanker traffic through Hormuz essentially halted, the IEA's largest ever coordinated stock release (400 million barrels), a ceasefire agreed on 7 April, and Rotterdam margins at extreme levels through the summer.

---

## 4. Definitions and the engine

### 4.1 Constants

```
BBL_PER_T_GASOIL   = 7.45       # ICE Low Sulphur Gasoil vs Brent crack contracts
BBL_PER_T_GASOLINE = 8.33       # ICE Eurobob vs Brent crack contracts
MMBTU_PER_MWH      = 3.412142
```

Factors for any other product, and for converting DGEC's Brent from $/t to $/bbl, come from the DGEC methodology note (4.3) or from ICE contract specifications. Cite the page next to each constant in `config.py`. Never guess a factor.

### 4.2 Cracks

```
crack_gasoil(t)   = p_gasoil_usd_t(t)   / BBL_PER_T_GASOIL   - brent_usd_bbl(t)
crack_gasoline(t) = p_gasoline_usd_t(t) / BBL_PER_T_GASOLINE - brent_usd_bbl(t)
```

Both legs share the same date and the same averaging window: weekly with weekly, monthly with monthly. Never a weekly product against a monthly crude.

Product definitions follow the source's own labels, and the Method view says so. In the DGEC data, "Gazole" is road diesel quoted in Rotterdam and "Eurosuper" is finished premium gasoline, not Eurobob blendstock. Do not relabel them as futures.

### 4.3 The NWE refining margin

Four layers, each visible on the site:

1. **Official margin.** DGEC publishes a monthly gross refining margin on Brent (marge brute de raffinage sur Brent, MBR), with a methodology note linked from every weekly note. It is the headline NWE margin series. Read the note, record its product slate, yields and conversion factors in `config.py`, and find the date of the method change the notes refer to. That date is a structural break, marked on every chart that spans it.
2. **Replication.** Recompute the MBR from DGEC's own published quotations with that method. Where every input is published, agreement within 0.50 $/bbl in every complete month is the Gate 2 bar. If an input is not published, name it and fall back to the official series. Replication tests understanding; it never overwrites the official figure. If replication works, apply the same method to the weekly quotations to give a weekly margin, labelled as this study's computation, not DGEC's.
3. **Decomposition.** Attribute each month's margin to products, `yield[p] * crack[p]`, so the site can say which crack is carrying the barrel. Anything not attributable sits on a residual line, never silently spread across products.
4. **Observed yields.** Compute NWE yields from JODI refinery output by product over refinery intake (12-month rolling, BE, DE, FR, NL, UK) and show how the margin moves with observed NWE yields instead of the official fixed structure.

### 4.4 Run economics

```
gas_usd_mmbtu    = ttf_eur_mwh * eurusd / MMBTU_PER_MWH
gas_cost         = gas_intensity_mmbtu_per_bbl * gas_usd_mmbtu
margin_after_gas = margin_gross - gas_cost - other_variable_cost
headroom         = margin_after_gas - run_cut_threshold          # threshold from 6.2
```

- **Gas intensity is derived, not typed.** EIA's refinery fuel tables for 2023 give natural gas consumed as fuel at US refineries (1,021,246 MMcf) and natural gas used as hydrogen feedstock (172,313 MMcf). Convert with EIA's heat content and divide by EIA's 2023 refinery crude inputs. Expect about 0.2 MMBtu per barrel; outside 0.12 to 0.30, stop and show your working. It is a US figure and European refiners burn more of their own refinery gas, so present it as an upper-end default, editable and labelled.
- **Triangulate, do not tune.** With that intensity, compute the October 2022 gas cost against a refinery fired on fuel oil and report it next to S&P's 7 $/bbl gap. The same order of magnitude is the expectation. Report whatever you get.
- `other_variable_cost` defaults to zero, labelled. Carbon costs are out of scope for this version and listed as a limitation.

### 4.5 Outputs

```
contribution[p]  = yield[p] * crack[p]
carrier          = product with the largest contribution
breakeven_ttf    = TTF at which margin_after_gas == run_cut_threshold      (closed form, the model is linear)
breakeven_gasoil = gasoil crack at which margin_after_gas == run_cut_threshold
percentile_10y   = rank of margin_after_gas within its trailing ten years
```

The verdict sentence on the landing view is assembled from these values, never written by hand.

---

## 5. Data layer

Build this first and defensively. It is where the project fails.

### 5.1 Sources

| Series | Source | Method | Notes |
|---|---|---|---|
| Rotterdam quotations, weekly and monthly averages: Eurosuper, Gazole, Fioul domestique, Jet, Fioul lourd TBTS below 1 percent, Brent daté, in $/t | DGEC, French Ministry for Ecological Transition, weekly price notes (NPG), data sourced DGEC-Reuters | Look first for a historical series file on the ministry's petroleum prices page. If only PDFs exist, parse the NPG archive by row and column labels, never by position | Current month provisional. Record how far back the archive goes |
| MBR, monthly, in $/bbl, €/t and c€/l | Same notes, plus the methodology note | Same | Record the method change date |
| Brent, daily | FRED `DCOILBRENTEU` (EIA Europe Brent spot) | `fredgraph.csv`, no key | Cross-check for DGEC Brent |
| EUR/USD, daily | FRED `DEXUSEU` | `fredgraph.csv`, no key | For TTF and €/t conversions |
| TTF front month, daily, €/MWh | Yahoo Finance `TTF=F` via `yfinance` | API | Record roll gaps. If history is short, extend monthly with the World Bank Pink Sheet European gas series and label the splice and its definition |
| Refinery crude intake, refinery output by product, crude imports, monthly, for BE, DE, FR, NL, UK | JODI-Oil World Database, free CSV, updated around the 20th of each month | CSV | Resolve product and flow codes from JODI's published short names list, never hardcode them. Carry JODI's assessment code (1, 2, 3) into the manifest |
| Refinery capacity by country, annual | Energy Institute Statistical Review of World Energy | xlsx | For utilisation. Confirm at Gate 1 that the table exists and covers all five countries |
| US refinery fuel use, 2023 | EIA Refinery Capacity Report, tables 10a and 10b, plus EIA crude inputs | Seed JSON with source URLs | For gas intensity |
| Events | Seed JSON, one `source_url` per entry | Manual | See 6.5 |
| Order of magnitude references | S&P Global articles of 28 March 2022 and 17 October 2022 | Seed JSON | Physical assessments. A sanity check on levels, not a benchmark |

### 5.2 Optional daily futures layer, off by default

There is no free, redistributable daily history for 1st line ICE Low Sulphur Gasoil, ICE Brent and Eurobob: ICE sells end-of-day CSV packages by subscription, and free web views cover only recent history. So:

- Build an importer for a CSV the owner exports himself into `data/private/`, with columns `date, series, value, unit, basis, source`. Never fetch it, never commit it.
- Eurobob trades on ICE on more than one assessment basis (Argus, and General Index contracts listed from December 2024). Record the basis per row and never splice bases silently.
- ICE Gasoil moved to a 10 ppm specification at the start of 2015, and Russian-origin barrels were excluded from delivery from the end of 2022. Both are breaks, marked.
- Use the 1st line versus 1st line convention of ICE's crack contracts, with its roll adjustment, and document that the two legs roll on different dates.
- The site must be complete without this layer. When present it adds a daily tab to History. Publish only what the export's terms allow, weekly averages by default.

### 5.3 Manifest

Every adapter writes `data/cache/<name>.csv` and appends to `data/manifest.json`:

```json
{
  "series": "dgec_gazole_rotterdam_weekly",
  "source": "DGEC via ecologie.gouv.fr",
  "url": "...",
  "fetched_at": "2026-09-12T08:04:11Z",
  "rows": 0,
  "first_date": "...",
  "last_date": "...",
  "gaps": [],
  "provisional_from": "...",
  "vintage": "NPG-2026.09.11",
  "licence_note": "...",
  "status": "ok | stale | failed",
  "note": "..."
}
```

The manifest is a first-class artifact, exported to the site and rendered on the provenance panel. Every chart can answer where its data came from, when it was pulled and whether any of it is provisional.

### 5.4 Rules

- Cache files are **committed**, so the site builds and results reproduce with no network. `make data` refreshes, `make build` never fetches.
- Validate on write: monotonic dates, no duplicate index, product prices between 100 and 3,000 $/t, Brent between 10 and 250 $/bbl, cracks between minus 30 and plus 150 $/bbl, intake non-negative, row count did not shrink. On failure keep the old cache, mark `failed`, exit non-zero.
- Retries with backoff, a real user agent, a polite delay between requests, one request per file.

### 5.5 Anchors the pipeline must reproduce

July 2026 monthly averages in $/t, as printed in the DGEC note of 28 August 2026:

```
Eurosuper                     1,084
Gazole                        1,160
Fioul domestique              1,127
Jet                           1,204
Fioul lourd TBTS (< 1%)         507
Brent daté                      628
```

Published MBR in $/bbl, as printed in the notes of the following month:

```
Oct 2025   11.45    (note of 28 Nov 2025)
Nov 2025   16.47    (note of 12 Dec 2025)
Feb 2026    6.50    (note of 13 Mar 2026)
Mar 2026   24.72    (notes of 3 and 17 Apr 2026)
Apr 2026   18.68    (notes of 8 and 15 May 2026)
May 2026   21.26    (note of 19 Jun 2026)
Jun 2026   20.30    (notes of 10 and 17 Jul 2026)
Jul 2026   36.69    (notes of 14 and 28 Aug 2026)
```

August 2026 stood at 38.05 provisional on 28 August; take the final figure from the September notes. Write all of this as `tests/test_dgec_anchor.py`. If your reading of the table layout disagrees with any value, stop and show me the page. Do not adjust the parser until it hits the number.

Cross-check: DGEC Brent, converted with DGEC's own factor, against the monthly mean of FRED `DCOILBRENTEU`, within 1.5 $/bbl in at least 95 percent of months. List every outlier.

Order of magnitude: S&P reported NWE cracking margins of 15.35 $/bbl on Forties for the week to 25 March 2022 and 23.11 $/bbl on Dated Brent for the week to 14 October 2022. Put the MBR for March and October 2022 next to them in the Gate 1 report. Different methods, so a gap is expected; a gap of a different order is a bug.

### 5.6 Reference links

```
DGEC weekly note (example)   https://www.ecologie.gouv.fr/sites/default/files/documents/NPG-2026.08.28_0.pdf
Ministry petroleum prices    http://www.developpement-durable.gouv.fr/prix-des-produits-petroliers-1
MBR methodology note         http://www.developpement-durable.gouv.fr/sites/default/files/Mode%20de%20calcul%20de%20la%20marge%20brute%20de%20raffinage%20sur%20brent.pdf
JODI downloads               https://jodidata.org/oil/database/data-downloads.aspx
EIA refinery capacity        https://www.eia.gov/petroleum/refinerycapacity/
ICE gasoil crack spec        https://www.ice.com/products/6753331
ICE Eurobob crack spec       https://www.ice.com/products/6753285
ICE 10 ppm transition        https://s2.q4cdn.com/154085107/files/doc_news/archive/c79af05e-53b8-4422-ab87-42fd967ced10.pdf
ICE Russian-free gasoil      https://www.businesswire.com/news/home/20230207005713/en/ICE-Announces-Successful-First-Delivery-of-Russian-Free-Barrels-of-ICE-Gasoil
S&P, March 2022              https://www.spglobal.com/energy/en/news-research/latest-news/crude-oil/032822-refinery-margin-tracker-record-high-global-diesel-cracks-propel-margins-upward
S&P, October 2022            https://www.spglobal.com/energy/en/news-research/latest-news/crude-oil/101722-refinery-margin-tracker-atlantic-basin-margins-soar-on-refinery-outages-tight-diesel-supply
IEA OMR, March 2026          https://www.iea.org/reports/oil-market-report-march-2026
IEA OMR, April 2026          https://iea.blob.core.windows.net/assets/515f3128-df1a-4d6c-beb4-fd91d2434bef/-14APR2026_OilMarketReport_Free_version1.pdf
IEA, Middle East and markets https://www.iea.org/topics/the-middle-east-and-global-energy-markets
IEA stock release coverage   https://www.cnbc.com/2026/03/14/iran-war-iea-oil-stockpile-spr-strait-hormuz.html
```

---

## 6. Analysis: linking run economics to crude demand

### 6.1 The claim

When the margin after gas is high, NWE refiners run harder and buy more crude, one to three months later. When it falls below the level at which marginal refineries lose cash, runs are cut.

```
utilisation(t) = a + sum over k of b_k * margin_after_gas(t - k) + month fixed effects + regime terms + e(t),   k = 1, 2, 3
```

- Utilisation is NWE refinery crude intake (JODI, sum of BE, DE, FR, NL, UK) over capacity (Energy Institute, interpolated monthly, closures as steps). If the capacity table is unusable, use intake with a trend and closure dummies instead, and say so.
- Report the response in percentage points per $/bbl, then translate it into crude demand at today's NWE capacity: kb/d for a 10 $/bbl move, and the share of NWE runs that represents.
- Show NWE crude imports next to intake as the physical footprint of the same demand. No separate model.
- Newey-West standard errors, lag at least 3.
- Show results with and without the 2020, 2022 and 2026 episodes.

### 6.2 Run cut threshold

Fit a hockey stick: utilisation roughly flat near its ceiling above a threshold, falling below it. Find the threshold by grid search, with a block bootstrap confidence interval. If the interval is wider than 10 $/bbl or touches the edge of the sample, call it unidentified. The site then shows no headroom figure and falls back to the ten-year percentile.

### 6.3 The horse race, which is the point

Run the same regression three ways: (A) the raw gasoil crack, the number on every screen; (B) the official margin; (C) the margin after gas. Report coefficients, R squared, Newey-West standard errors and an expanding-window out-of-sample RMSE for each.

If A wins, say so on the page, then say what B and C still give that A cannot: a margin level, the gas wedge that opened in 2022, and a threshold in dollars.

Flag endogeneity honestly. Runs move cracks, since more runs mean more product and weaker cracks, which biases the response toward zero. Lags help only partly. Try the gas cost as an instrument for the margin after gas: TTF was driven by pipeline cuts in 2022 and by LNG disruption in 2026, not by NWE runs. Report the first-stage F. If the instrument is weak, say that rather than forcing it.

### 6.4 Did the link hold in 2026

Test whether the relation held after 28 February 2026. If runs sit below what margins imply, show the residuals and set out the competing explanations: feedstock availability, outages, maintenance. The IEA noted that refiners outside the Gulf were curtailing runs over feedstock availability; cite it, but do not pick an explanation the data cannot separate.

### 6.5 Seasonality and events

Seasonality: each crack by week of year, the prior five years as a range, the current year as a line, with a toggle that removes 2020, 2022 and 2026 from the range. Check, do not assert, the textbook pattern of gasoline firming into the driving season and gasoil into winter.

Seed `data/seed/events.json`, each entry with a `source_url`. Include only what you can cite:

| Date | Event |
|---|---|
| 2015-01 | ICE Gasoil moves to a 10 ppm specification (daily layer only) |
| 2020-03 | Pandemic lockdowns across Europe |
| 2022-02-24 | Russia invades Ukraine |
| 2022-03-25 | Week of record European diesel cracks, about 44 $/bbl (S&P Global) |
| 2022-10-13 | ARA diesel cracks near 80 $/bbl during French refinery strikes (S&P Global) |
| 2022-12-05 | EU embargo on Russian seaborne crude and G7 price cap |
| 2023-02-05 | EU embargo on Russian refined products |
| 2026-02-28 | US and Israeli strikes on Iran, Hormuz tanker traffic halts (IEA Oil Market Report, March 2026) |
| 2026-03 | IEA coordinated release of 400 million barrels, the largest in its history. Pin the exact date from the source |
| 2026-04-07 | Two-week US and Iran ceasefire (IEA Oil Market Report, April 2026) |

Add later 2026 developments only with a source. Around each event, show cracks, margin after gas and utilisation from minus 6 to plus 6 months.

### 6.6 Do not

No parameter search, no walk-forward optimisation, no forecasts, no strategy, no Sharpe ratio. Presenting this as a trading system is the fastest way to lose the audience.

---

## 7. Site

### 7.1 The engine exists twice, so prove they agree

`src/crack/engine.py` drives the pipeline. `src/engine.js` drives the interactive margin model. They will drift.

- `scripts/gen_fixtures.py` emits `data/fixtures/engine-cases.json`: at least 200 randomised input sets with full Python output, every contribution line included.
- `tools/validate-engine.mjs` runs `engine.js` against that file with plain `node` and asserts agreement to 1e-9 on every line.
- It runs in CI and in `make test`. If they disagree, fix the JavaScript to match Python, never the reverse.

### 7.2 Views and progressive disclosure

Not one long page of stacked cards. The landing view is small and answers one question. Everything else sits behind a control the visitor chooses to operate, reached by button, with a hash router so every view is linkable.

**Now, the landing view.** One sentence a trader would say out loud: what a Rotterdam refiner earns per barrel after gas this month, where that sits in ten years of history, which crack is carrying the barrel, and whether runs have room to rise. Under it, the data date for margins and the data date for runs, shown separately, with any provisional flag. Then four closed sections that open on click:

- **Cracks.** Gasoil and gasoline, latest weekly values against their five-year range for the same week.
- **Margin stack.** A waterfall from product contributions to the gross margin, minus gas, to the margin after gas. The residual line is shown, never hidden.
- **Runs and crude demand.** Latest NWE utilisation against what the margin implies, the response in kb/d per $/bbl with its interval, and headroom to the threshold or the word unidentified.
- **Provenance.** The manifest: every series, source, last fetch, gaps, vintage, status.

**History.** Weekly cracks and the monthly margin from the start of the data, event markers, a range brush, a product toggle and a seasonal sub-view. Structural breaks marked.

**Model.** The calculator. Presets: latest month, 2019 average, October 2022, July 2026. Every input editable: cracks, yields, TTF, EUR/USD, gas intensity, other variable cost. Live recompute, the waterfall updating in place, breakevens in the units a desk quotes: $/bbl for cracks and margins, €/MWh for gas. This view proves the model is real rather than a screenshot.

**Runs and crude demand.** Utilisation and crude imports against lagged margin after gas, the scatter with the hockey stick fit and its interval, the response table, the horse race, the instrument result, and residuals with 2022 and 2026 highlighted.

**Events.** The minus 6 to plus 6 month panels, one per event, opened by clicking a marker in History or picking from a list.

**Method.** Formulas, the assumptions table with a source per row, product definitions, structural breaks, limitations, reuse terms.

### 7.3 Copy

Write it yourself, in English, plain sentences, sentence case. The verdict is a sentence, not a metric with a label above it. Errors say what happened and what to do. An empty chart names the missing series and the time of the failed fetch.

---

## 8. Repo layout

```
crack-spread-study/
  index.html
  .nojekyll
  .gitignore                    data/private/
  README.md
  SPEC.md
  Makefile                      data | build | test | serve
  pyproject.toml
  src/
    engine.js                   mirror of engine.py, ES module
    ui.js  state.js  router.js  charts.js  format.js
    crack/                      python package
      config.py  engine.py  series.py  analysis.py  export.py
      sources/  base.py dgec.py fred.py yahoo.py jodi.py ei.py eia.py user_csv.py
  styles/                       tokens.css  layout.css  components.css
  data/
    seed/                       committed and cited: events.json, anchors.json, eia_refinery_fuel_2023.json
    cache/                      committed, machine fetched
    private/                    gitignored, optional daily futures export
    fixtures/                   engine-cases.json, text fixtures of DGEC notes for parser tests
    manifest.json
    *.json                      site-facing artifacts written by export.py, schema versioned
  vendor/                       pinned libraries plus licences
  tools/
    validate-engine.mjs         python to javascript parity
    validate-data.mjs           schema, date monotonicity, no orphan series
  tests/                        test_units.py test_engine.py test_dgec_anchor.py test_analysis.py test_sources.py
  scripts/                      refresh.py gen_fixtures.py
  docs/                         sources.md methodology.md open-questions.md
  .github/workflows/
    build.yml                   test, validate, deploy to Pages
    refresh.yml                 weekly, public sources only: commit if validators pass, open an issue if not
```

`README.md` must contain: the CV bullet, what the study cannot do, what it does, a screenshot, local run instructions, the data refresh procedure, a provenance table, and the known limitations.

Charting: use what the sibling repos already vendor. If they vendor nothing suitable, vendor one small library or draw SVG by hand, and justify the choice at Gate 4.

---

## 9. Tests

| Test | Construction | Catches |
|---|---|---|
| Units | Gasoil 745 $/t with Brent 80 $/bbl gives a crack of exactly 20. Gasoline 833 $/t with Brent 80 gives exactly 20 | A wrong conversion factor, the most common error in this study |
| Null | Every crack zero, TTF zero, other cost zero: gross margin, margin after gas and the residual all exactly zero | Sign errors |
| Linearity | The gross margin moves by exactly `yield[p]` per $/bbl of `crack[p]`. The margin after gas moves by exactly `-gas_intensity * eurusd / 3.412142` per €/MWh of TTF | A broken €/MWh to $/MMBtu chain |
| Round trip | Plug `breakeven_ttf` back in: the margin after gas equals the threshold within 1e-9 | Forward calculation and inversion disagreeing |
| Alignment | No crack is ever computed from legs with different dates or averaging windows | Silent misalignment |
| Anchors | The values in 5.5 parse exactly | Parser drift |
| Replication | MBR within 0.50 $/bbl, or a documented reason why not | A misread method |
| Intensity | Derived value inside 0.12 to 0.30 MMBtu/bbl | Wrong heat content or units |

Plus the parity validator in 7.1, the data validator, and source adapter tests against committed fixtures, so parsers are tested without network access.

Write the units test first.

---

## 10. Phase gates

Stop at each. Show the output. Wait for approval. Do not write UI code before the data and the engine are approved.

**Gate 1, data.** Adapters, cache, manifest, validation, `make data`. Show the manifest, every series' date range, row count and gaps, and the reuse terms you found. Tell me how far back the DGEC data go, whether a historical file exists, which sources are weaker than this spec assumes, the order of magnitude comparison in 5.5, and whether the sibling repos agree on the palette.

**Gate 2, engine.** `config.py`, `engine.py`, the tests in section 9, the anchors, the replication attempt and the intensity derivation, with the test output. Do not proceed if an anchor fails.

**Gate 3, analysis.** The utilisation regression, the threshold, the horse race, the instrument, the 2026 residuals, the seasonality. Say plainly what held and what did not. If the margin after gas lost the horse race, change nothing to make it win.

**Gate 4, design and shell.** The treatment plan with your own critique, then the shell with the Now view working end to end, including its four sections. Screenshots at desktop and mobile widths, in both themes.

**Gate 5, full build.** All views, self audit, README, both workflows, deployment. Screenshots of everything, taken from the live subpath.

---

## 11. Self audit, run before every gate and paste the result

1. Series fetched successfully, stale or failed, with vintages and provisional ranges
2. Date ranges and gaps per series
3. Any number in the codebase without a matching source or config entry
4. Anchor results against 5.5
5. Test and validator output
6. Python to JavaScript parity result
7. Relative path check: does every asset load from the `/crack-spread-study/` subpath
8. Orphan data (present in JSON, unreachable in the UI) and orphan UI states (reachable, no data)
9. Accessibility: keyboard navigation, visible focus, contrast in both themes, reduced motion
10. Anything you are quietly unsure about but have not otherwise flagged

Point 10 is not optional. I would rather read an uncomfortable list than ship a confident error.

---

## 12. Definition of done

I open `https://nathancouturier.github.io/crack-spread-study/` and land on one sentence telling me what a Rotterdam refiner earns per barrel after gas, how that compares with ten years of history, which crack is carrying it, and whether runs have room to move. I open Cracks and see gasoil and gasoline against their seasonal range. I open the Model, raise TTF, and watch the margin after gas and the headroom fall in place. I open Runs and crude demand and read, with an interval, how many kb/d of crude demand a 10 $/bbl margin move is worth, and an honest sentence on whether the margin beat the raw gasoil crack. I open History and see 2022 and 2026 for what they were. Nothing on screen I did not ask for. Every number traceable to a source.

---

## 13. What will go wrong

- **The DGEC notes change layout, or a PDF extracts columns out of order.** Parse by labels, check the unit rows, fail loudly.
- **Provisional figures move.** Expected. Keep vintages, show the flag, never blend a provisional month into a final one silently.
- **The MBR method changed.** Find the date, mark the break, do not stitch two methods into one line without saying so.
- **JODI revises history and lags by about two months.** Show the runs data date separately from the margin data date. Carry the assessment codes.
- **`yfinance` returns an empty frame for TTF.** It does this intermittently. Retry, then fail rather than caching an empty file.
- **The regressions are weak.** Likely, on monthly data dominated by three crises. Report it, state the limitation, do not fish.
- **Paths break on Pages.** The subpath is the classic failure. Test from the subpath before calling Gate 5 done.
- **The site drifts toward a generic dashboard.** Go back to section 0.2 and cut something.
