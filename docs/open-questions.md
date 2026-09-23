# Open questions

Things this project has not settled, written down instead of decided quietly.
Every entry says what was measured, what is still unknown, and what would close
it. SPEC.md section 2 rule 8: an honest gap beats a plausible fabrication.

Started at Gate 1 with the market data layer. Later gates append.

**What "recon NN" means in this document.** The five source reconnaissance notes
written before Gate 1, `01-conventions`, `02-dgec`, `03-physical`, `04-market` and
`05-crack-sources`, are the working record of what was fetched, from where, with
what status and on what terms. THEY ARE NOT IN THE REPOSITORY: they live in
`data/private/recon/`, which `.gitignore` excludes, because recon 03
reproduces the Energy Institute capacity table that may not be redistributed,
and because they log an individual machine's requests. A citation to one is a
citation to that record, not to a public document, and nothing in this study
rests on a recon note alone: every figure a recon note is cited for is either
recomputed here from a committed cache, asserted in `tests/`, or carried in
`data/manifest.json` with its own source. Where the note and the data disagree,
the data wins and this document says so, as it does of recon 05 section 12 in
section 1.6. **`docs/sources.md` section 6 lists all five reports, what each
covers and the public primary source to fetch instead**, and a test fails if a
report is cited and not listed there.

---

## 1. Does FRED's no mirroring clause bite on a committed cache?

**Status: open. It needs the owner, not another measurement.**

FRED tags both series this project uses, `DCOILBRENTEU` and `DEXUSEU`, with its
most permissive tier, "public domain: citation requested". The same legal page,
under "II. Prohibited Use", applying to all use including non commercial and
educational, says verbatim:

> Engage, or otherwise participate, in the use of any data mining, mirroring,
> robots, scraping, or similar data-gathering or extraction methods except as
> expressly allowed by the terms of use applicable to the FRED API.

A scheduled job that downloads `fredgraph.csv` and commits the result into a
public repository is, read strictly, both a robot and a mirror. The expressly
allowed route is the FRED API, which is free but needs a key, which would then
live in a repository secret and would break the "no key" simplicity SPEC.md
section 5.1 assumes.

SPEC.md section 5.1 names FRED, so FRED is built and FRED is what the analysis
reads. Two things were done about the tension rather than around it:

* the clause travels with the data. It is in `crack.config`'s FRED licence note,
  which reaches `data/manifest.json` and therefore the provenance panel.
* **the escape route is built and tested.** `crack.sources.eia` fetches the same
  Brent numbers straight from EIA, whose reuse grant is explicit and carries no
  mirroring clause. Measured on 2026-09-12 against the committed caches: 9,973
  shared dates, maximum absolute difference **0.0**, no date in one file and not
  the other. Switching Brent from FRED to EIA costs one line.

What is not built is the EUR/USD half of the escape. The underlying publisher is
the Federal Reserve Board's H.10 release, a US federal government work, but no
Federal Reserve Board reuse statement was fetched and read, so nothing is
asserted about it.

**To close it:** the owner decides. Keep FRED and cite both publishers, or move
Brent to EIA and EUR/USD to H.10, or take a FRED API key.

Also on the same page, and the owner should see it because this repository was
written by an agent: FRED's prohibited use list includes using FRED content "in
connection with the development or training of any software program or system or
machine learning". That clause is about training on FRED content rather than
about using an agent to write a fetcher, and it is quoted here so the decision is
made with it in view.

## 2. SPEC.md section 5.4 says "a real user agent". For FRED that is wrong.

**Status: closed in code, recorded because the code disagrees with the spec.**

Recon 04 section 1.2 measured `fred.stlouisfed.org` five ways on the same URL in
the same minute, changing only the User-Agent header:

| User agent sent | Result |
|---|---|
| curl default | HTTP 200, 174,106 bytes, under a second |
| `crack-spread-study/1.0 (+...)` | HTTP 200 |
| `python-requests/2.32.3` | HTTP 200 |
| `Mozilla/5.0` | connection reset, 0 bytes |
| full Chrome 127 string | timed out after 40 s, 0 bytes |

The sibling repository `lme-comex-arbitrage-model` measured the same behaviour
independently on 2026-08-31 for the SOFR series. So the host to user agent map
lives in `crack.sources.base.USER_AGENT_BY_HOST` and FRED gets a named project
token. Every other host in the project gets the browser string.

**Still unknown:** whether the block is FRED policy or a middlebox on this
connection. Only the behaviour was observed, twice, from one machine. A CI runner
on different infrastructure may see something else, and the project token is not
guaranteed to keep working.

## 3. Brent has printed below SPEC.md section 5.4's lower bound. The bound moved.

**Status: deviation from the spec, deliberate, needs the owner's agreement.**

SPEC.md section 5.4 says Brent between 10 and 250 $/bbl. The first live fetch on
2026-09-12 carried **25 published prices below 10**, and every one is a real
print that EIA and FRED both still publish:

* 1998-11-30 to 1998-12-24, 17 days of the 1998 oil price collapse, low **9.10**
  on 1998-12-10
* 1999-02-08 to 1999-02-18, 7 days, low 9.77
* 2020-04-21, one day at **9.12**, the session WTI settled negative

The same 25 dates carry the same values in the EIA workbook, so it is not a FRED
artefact. With the bound at 10 the adapter refused the entire download, wrote no
cache and exited non zero.

`crack.config.BOUNDS_BRENT_USD_BBL` is now **(5.0, 250.0)**. The reasoning is in
the comment next to it: the bound is a units and parse check, not a view on the
market, and 5.0 still catches a file that arrived in cents or with a decimal
point in the wrong place. Deleting 1998 and 2020 from the history to fit a
printed number would be closer to inventing data than widening a check is.

**To close it:** the owner either accepts the wider bound or asks for the Brent
series to start in 2000, in which case the page has to say why it starts there.

## 4. May the Yahoo TTF cache be committed at all? Today it is not.

**Status: decided defensively, with a cost that has not been paid off.**

There is no public Yahoo Finance data licence. The applicable general term
forbids users to "reproduce, modify, rent, lease, sell, trade, distribute,
transmit, broadcast, publicly perform, create derivative works based on, or
exploit for any commercial purposes" any portion of the services, and `yfinance`
is an unofficial client for an undocumented endpoint with no grant of its own.
The sibling repository already treats Yahoo the same way.

So `ttf_daily` is marked not committable, `crack.sources.base.Adapter` writes it
to `data/private/`, and `data/private/` is gitignored.

**The cost, stated rather than hidden:** SPEC.md section 5.4 promises the site
builds and results reproduce with no network. That promise does not hold for
anything derived from the daily TTF layer on a fresh checkout, because the file
is not there. It holds for everything else in the market layer: the monthly gas
series the analysis actually runs on is the World Bank pink sheet, which is
CC BY 4.0, already in $/MMBtu, and committed.

The same collision exists for the Energy Institute capacity table, which is a
harder case because utilisation depends on it. Recon 03 section 2.5 sets out
three options there.

## 5. What does the leading asterisk mean on the pink sheet's gas description?

**Status: open, and it is probably harmless.**

The pink sheet's `Description` sheet prints the Natural Gas (Europe) description
in a row whose first cell is `*`, and row 107 of the same sheet says
`* denotes forecast series`. That reading does not obviously apply to a
historical monthly file. The likely meaning is that the World Bank publishes
price forecasts for that commodity in the Commodity Markets Outlook, not that the
history is forecast, but no sentence in the workbook settles it.

It is carried in the manifest entry for `worldbank_gas_europe_monthly` as
`open_question` so that it reaches the provenance panel rather than only this
file.

**To close it:** ask the World Bank commodity markets team, or find the sentence
in the Commodity Markets Outlook that defines the marker.

## 6. How much of the April 2015 break in the pink sheet is definition and how much is market?

**Status: unanswerable from free data, and the page must say so.**

The World Bank's Europe gas series changes definition inside itself. Verbatim
from the `Description` sheet:

> Natural Gas (Europe), from April 2015, Netherlands Title Transfer Facility
> (TTF); April 2010 to March 2015, average import border price and a spot price
> component, including UK; during June 2000 - March 2010 prices excludes UK.

Across that one month the level fell from 8.27 to 6.77 $/MMBtu, 18.1 percent.
Part of that is the definition and part is a real move in spring 2015. Recon 04
section 5.3 found no free overlap series that would separate them.

All three definition changes are carried in the manifest entry as
`structural_breaks`. SPEC.md section 4.3 requires the 2015-04 one marked on every
chart that spans it, and the pre 2015-04 segment must be labelled "European
import border price plus a spot component, including UK, World Bank definition",
never TTF.

**To close it:** it does not close. If the study's sample starts on or after
2015-04 the question disappears.

## 7. What roll convention does Yahoo use for TTF=F?

**Status: one roll observed, the rest inferred, nothing adjusted.**

`TTF=F` is a stitched continuous front month series carrying unadjusted price
jumps. Yahoo publishes no roll convention and no roll dates, and expired dated
contracts are delisted, so the splice points cannot be recovered from free data.

One roll was observed directly, recon 04 section 3.4: `TTF=F` matched
`TTFV26.NYM`, the October 2026 contract, on all ten sessions from 2026-08-28 to
2026-09-11 and never matched `TTFX26.NYM`. So the front month rolled into October
on 2026-08-28.

The adapter records `roll_jump_candidates`, the day on day close moves of 20
percent or more, with how many further sessions of the same month the series
holds after each. On the 2026-09-12 fetch there were **17** of them across 2,235
sessions. Two of the seventeen, 2019-09-30 at +37.3 percent and 2020-05-29 at
+24.9 percent, land on the last session of their month and have the shape a roll
would have. Others are plainly the market: 2022-02-24 at +51.1 percent is the
invasion of Ukraine and 2026-03-02 at +39.3 percent is the Hormuz episode.
**This series cannot tell them apart**,
so the list is labelled as candidates, no price is adjusted anywhere, and nothing
downstream may read it as a set of roll dates.

## 8. Does the site show a daily view at all, given the two FRED calendars?

**Status: open, and it is a design question for Gate 4.**

Brent follows a UK and European holiday calendar, EUR/USD follows the US federal
one. Measured on the committed caches on 2026-09-12, joined on the date:

| | |
|---|---|
| Joined rows | 7,220 |
| Both legs published | 6,847, 94.8 percent |
| Brent published, EUR/USD blank | 172 |
| EUR/USD published, Brent blank | 94 |
| Neither published | 107 |

About one business day in twenty carries one leg and not the other. Under SPEC.md
section 2 rule 1 that day is NaN, never filled from a neighbour, and it appears
in the manifest gaps.

On top of that, EUR/USD lags. H.10 goes out on Monday afternoons covering the
previous business week, so the FX series can sit five business days behind Brent:
on 2026-09-12 the Brent cache reached 2026-09-09 and the FX cache reached
2026-09-04.

So a daily gas cost in $/MMBtu built from TTF and EUR/USD inherits both the holes
and the lag. The monthly figure from the pink sheet has neither, needs no FX and
is already in the right unit.

**To close it:** Gate 4 decides whether the daily view exists and, if it does,
whether it shows the holes and the lag honestly or is simply dropped.

## 9. A recon figure that did not reproduce, and the correction

**Status: closed, recorded so nobody trusts the wrong number.**

Recon 04 section 4.5 reports that the monthly mean of `TTF=F` converted with
`DEXUSEU` and `MMBTU_PER_MWH` reproduces the pink sheet's Europe gas series to a
"median of 0.02 percent" over 106 months. Recomputed on 2026-09-12 from the
committed caches, using `crack.config.monthly_mean`, every other statistic in
that section reproduces exactly:

| Statistic | Recon 04 | Measured here |
|---|---|---|
| Comparable months | 106 | 106 |
| Correlation | 0.999957 | 0.999957 |
| Mean difference | +0.0024 | +0.0024 |
| Median difference | -0.0019 | -0.0019 |
| Standard deviation of difference | 0.1120 | 0.1120 |
| Worst month | 2021-12, 1.99 percent | 2021-12, 1.99 percent |
| **Median absolute percentage difference** | **0.02 percent** | **0.157 percent** |

The median absolute difference in dollars is 0.0141 $/MMBtu, which on a level
around 9 $/MMBtu is 0.157 percent and not 0.02 percent. The recon figure looks
like the median signed difference in dollars, -0.0019, carried into the
percentage row by mistake. The conclusion it supports is unchanged and if
anything better tested: the unit chain in SPEC.md section 4.4 is confirmed by
construction. Use 0.157 percent when quoting the agreement, not 0.02 percent.

## 10. Two issues of the MOMR print different numbers for February and March 2012 under identical row labels

**Status: open. Measured, classified, not resolved, and it cannot be resolved
from inside this repository.**

The first build of `opec_rotterdam_products_monthly` reported 27 of 305 months
where the issues that printed a month disagreed, the worst 21.28 $/bbl. The
Gate 1 audit re-read the Rotterdam block of every issue involved by WORD
COORDINATES, clustering pdfplumber's words on their vertical centre and giving
each number to the label whose row it physically shares, instead of trusting
pdfplumber's assembled text lines. Over 289 issues and **4,125 label to number
cells, 312 of them inside a disputed month, the geometric reading and the parser
differ in zero cells.** None of the 27 is an extraction artifact.

Of the 27, eight were the Rotterdam row SET changing between two issues, so one
output slot held two different products either side, and `build_frame` reported
that as the source disagreeing with itself. Those are now separated into
`max_respec_gap_usd_bbl` and `respecified`, and four months fell out of the
disagreement count as a result. Eleven more, all in 2001 and 2002, are ordinary
revisions of 0.01 to 0.99 $/bbl, several of them carrying the old layout's own
printed revision marker, for example `29.01R`.

What is left, and what this entry is about:

| Month | Row | Earlier issues | May 2012 issue onward | Gap |
|---|---|---|---|---|
| 2012-02 | Premium gasoline (unleaded 10 ppm) | 129.29 | 115.76 | 13.53 |
| 2012-02 | Gasoil/Diesel (10 ppm) | 142.59 | 133.79 | 8.80 |
| 2012-03 | Premium gasoline (unleaded 10 ppm) | 141.01 | 119.73 | 21.28 |
| 2012-03 | Gasoil/Diesel (10 ppm) | 148.01 | 137.55 | 10.46 |

In the same block, on the same page, naphtha moves 0.05, jet 0.27 and both fuel
oils 0.12 or less, which is ordinary revision size. The row labels are byte for
byte identical in both issues. The column headers are correct in both, "Jan 12
Feb 12 Mar 12" in the April issue and "Feb 12 Mar 12 Apr 12" in the May one, so
it is not a column misalignment. The Mediterranean block of the two issues
prints February 2012 identically, 111.13, 128.88, 129.30, 120.31, 113.94,
107.60, so it is not a whole table restatement either. Only the Rotterdam
gasoline and gasoil rows moved.

The one external check available says the LATER reading is the better one for
gasoil: the OPEC Annual Statistical Bulletin table 7.6 puts Rotterdam gasoil
10 ppm at 129.18 $/b for 2012, and the cache's twelve monthly values average
129.84 on the later reading and 131.44 on the earlier one. That is evidence, not
proof, and it says nothing at all about which gasoline reading is right.

**Treatment now:** the overlap rule is unchanged, the later issue wins, and the
size of the disagreement travels in `max_disagreement_usd_bbl` so a chart can
mark these two months rather than draw them as if they were as firm as their
neighbours. Nothing is averaged and nothing is dropped.

**To close it:** open the June, July and August 2012 issues, which is already
done here and which only repeat the later reading, and then ask OPEC or Argus
directly. Failing that it stays open and the site says February and March 2012
carry a 13 to 21 $/bbl ambiguity on gasoline and 9 to 10 on gasoil.

## 11. The MOMR premium gasoline column is not one product across 2004 to 2013, and no label rule makes it one

**Status: open, and it is a limitation of the source rather than of the parser.**

Between August 2004 and September 2013 the Rotterdam block prints two premium
gasoline rows, a sulphur graded one and an octane graded one. This adapter keeps
both, `premium_gasoline_usd_bbl` for the leading row of the issue with
`gasoline_spec` saying what it is, and `premium_gasoline_95_usd_bbl` for the
"unleaded 95" row wherever it is printed. The module docstring deferred to Gate 1
the question of which of the two continues OPEC's own annual series. The Gate 1
audit measured it against ASB table 7.6, "Gasoline - Premium unleaded 98", over
the 22 complete calendar years the cache covers.

The answer is that **neither column does.** Eighteen of the 22 years agree with
the ASB to 0.01 $/b or better on `premium_gasoline_usd_bbl`, and in each of the
four that do not, the OTHER column is the one that agrees exactly:

| Year | ASB | premium_gasoline | premium_gasoline_95 |
|---|---|---|---|
| 2005 | 62.58 | 68.90 (+6.32) | 62.58 (-0.00) |
| 2006 | 72.90 | 81.73 (+8.83) | 72.90 (-0.00) |
| 2012 | 127.29 | 111.97 (-15.32) | 127.14 (-0.15) |
| 2013 | 122.57 | 115.22 (-7.35) | 122.64 (+0.07) |

**The 2013 line is corrected.** It read 123.21 (+0.64), which was the mean of the
**six** months the octane row was printed in 2013 compared against a twelve month
annual average. The like for like figure takes the octane row where the reports
printed one and the headline row where they did not, and it is 122.64, +0.07 from
the bulletin. The 2012 figure moves by a rounding place, 127.13 to 127.14 and
-0.16 to -0.15; the measured error is -0.155. Both are quoted in their corrected
form in `docs/methodology.md` section 2.1.1 and on the Method view.

and across 2007 to 2011, with no label change anywhere between 2006 and 2007, it
is the other way round: `premium_gasoline_usd_bbl` agrees to 0.01 to 1.31 and
`premium_gasoline_95_usd_bbl` sits 2.73 to 9.98 below. Gasoil over the same 22
years agrees to a mean absolute 0.17 $/b, worst 0.98, and fuel oil 3.5 percent
to 0.48, worst 3.82 in 2020.

**To close it:** it probably cannot be closed from published documents. The
treatment is to keep both columns as printed, keep `gasoline_spec` beside every
value, and have the site refuse to draw a single premium gasoline line across
2004 to 2013 without saying in words that it is not one product. The gasoil
series does not have this problem and is the one to lead with.

## 12. The spec's 8.33 barrels per tonne does not bridge DGEC Eurosuper and the MOMR gasoline row

**Status: open. The gasoil constant survives contact with the data, the gasoline
one does not, and what that means cannot be separated here.**

Measured over the 44 months from July 2022 to February 2026 where the recon 05
reconstruction of the DGEC page 3 chart and the MOMR both exist. The DGEC side is
a decoded reconstruction, not a published DGEC file, and carries its own error of
0.17 to 0.44 $/t, which is about 0.05 $/bbl and far too small to explain what
follows.

| Pair | Implied bbl per tonne | Spec constant | Verdict |
|---|---|---|---|
| DGEC Brent date $/t against DGEC Brent $/bbl, 140 months | **exactly 7.50000, zero variance** | `DGEC_BBL_PER_T_BRENT_NOTE` 7.5 | exact, not approximate |
| DGEC Gazole against MOMR Gasoil/Diesel 10 ppm, 44 months | mean 7.528, sd 0.107, 7.306 to 7.820 | `BBL_PER_T_GASOIL` 7.45 | survives, 1.1 percent high |
| DGEC Eurosuper against MOMR Premium gasoline 98, 44 months | mean 7.718, sd 0.448, 6.934 to 8.336 | `BBL_PER_T_GASOLINE` 8.33 | does not survive |

For gasoil the two sides are the same product, Rotterdam 10 ppm diesel, so the
implied figure really is a conversion factor. 7.528 corresponds to a density of
0.836 kg/l against 7.45's 0.845, and both sit inside EN590, so 7.45 stands and
the residual is product density plus decoding error. The cracks the two routes
produce agree to a mean absolute 1.58 $/bbl over 44 months, range -2.45 to +5.99,
which is wider than the 0.4 to 3.7 recon 05 measured on six months but the same
order.

For gasoline the two sides are NOT the same product, DGEC's Eurosuper being
finished premium at RON 95 and the MOMR row being premium unleaded 98 as assessed
by Argus, so the implied 7.718 is a conversion factor and an octane spread
tangled together and cannot condemn 8.33 on its own. What can be said is the
consequence: applying 8.33 leaves the MOMR row **8.82 $/bbl above** DGEC's
Eurosuper on average, up to 21.97, with a yearly mean gap of -12.17 in 2022,
-16.76 in 2023, -6.58 in 2024, -2.30 in 2025 and -3.65 in 2026. An 8.82 $/bbl
average premium of RON 98 over RON 95 is far larger than any plausible octane
spread, so either the two rows are further apart than their labels suggest or
8.33 is wrong for DGEC Eurosuper, and nothing in this repository separates them.

**To close it:** get one month of a published RON 95 Rotterdam barge quotation in
$/bbl from any third source and the two explanations come apart immediately.
Until then, **do not pick a factor that makes the two agree.** SPEC.md section
6.6 forbids exactly that, and a factor fitted to close an 8.82 $/bbl gap would be
the most invisible fabrication in the project.
---

## 13. The Energy Institute capacity table cannot be committed, and publishing only the ratio does not withhold it

**Status: open, and it is a decision for the owner at Gate 1, not a technical
question. The adapter keeps all three answers available and takes none.**

SPEC.md section 5.4 requires every cache committed so the site builds with no
network. SPEC.md non negotiable 6 requires anything that cannot be redistributed
to stay in `data/private/`. Both cannot hold for `ei_refinery_capacity_annual`,
because two separate prohibitions land on that one table. The Review, quoted:

> Publishers are welcome to quote from this Review provided that they attribute
> the source to Energy Institute Statistical Review of World Energy 2026.
> However, for extensive reproduction of tables and/or charts, permission must
> first be obtained from: EI Statistical Review of World Energy, 61 New Cavendish
> Street, London W1G 7AR, statisticalreview@energyinst.org

> The redistribution or reproduction of data whose source is S&P Global Energy or
> S&P Global Inc, is strictly prohibited without its prior authorisation.

and the capacity sheet carries, on the sheet, below the data:

> Source: Includes data from ICIS and S&P Global Energy

The footnote does not say which rows came from which supplier, so the S&P sourced
part cannot be separated out and kept. The cache therefore lives in
`data/private/`, is gitignored, and is never deployed. Recon 03 section 2.5 set
out three ways forward and recommended the second.

**What recon 03 did not say, and it changes the second option.** Option 2 is
"publish only the derived utilisation ratio". But utilisation is intake over
capacity, and the intake is itself committed, in
`data/cache/jodi_nwe_refinery_intake_monthly.csv`, because SPEC.md section 5.4
requires it. Anyone who divides the published intake by the published utilisation
recovers EI's capacity exactly, to the last decimal, for every month the ratio
appears. Rounding the ratio to three decimals still pins a capacity of the NWE
five country size to about plus or minus four thousand barrels a day in six
million. So option 2 as written does not withhold the table,
it publishes it in a form that takes one division to read. That may still be
acceptable to EI, and it may not, but the reasoning has to be checked rather than
assumed, because the licence text does not discuss derived values at all.

The honest version of option 2 publishes the regression outputs, the coefficient,
the interval and the chart, and not a full precision monthly ratio.

**To close it:** one email to `statisticalreview@energyinst.org` asking for
permission to publish five country rows of the capacity table, 1965 to 2025, in a
non commercial public portfolio repository with attribution, and a second sentence
asking whether a derived monthly utilisation ratio computed against a published
intake series counts as reproduction. Until there is an answer, SPEC.md section
6.1's own fallback stands available: "If the capacity table is unusable, use
intake with a trend and closure dummies instead, and say so."

---

## 14. energyinst.org now answers a bot challenge, so the capacity series cannot be machine refreshed

**Status: measured and closed as far as this repository is concerned. It is a
constraint, not a puzzle, and the constraint is recorded rather than worked
around.**

Recon 03 fetched the workbook on 2026-09-11 from this machine: HTTP 200,
3,973,716 bytes, from a plain `href` on the downloads page with no registration
and no click through. Measured again from the same machine on 2026-09-13, with
four different header sets, on the landing page as well as on the file itself:

```
HTTP 403, Server: cloudflare, Cf-Mitigated: challenge
body "Just a moment...", 5,976 bytes of Cloudflare interstitial
```

That is an interactive challenge covering the whole site. It is not a licence
refusal, not a rate limit, and not something a header fixes. `crack.sources.ei`
therefore parses a copy that is already stored and, when there is none, raises an
error telling the operator to download the file by hand and pointing at the page.
A person downloading a public workbook from a public page is the normal use of
that page. A script defeating a challenge is not, and a pipeline whose entire
claim is that it tells the truth about its sources cannot begin by pretending to
be a browser.

Two consequences, both already carried in the manifest entry:

- This series cannot be part of the weekly `refresh.yml` job in SPEC.md section
  8. It is annual and the edition changes once a year, so that costs nothing.
- `fetched_at` for this series means WHEN THE BYTES WERE OBTAINED, not when the
  program last ran, and `checked_at` carries the run. The base adapter stamps the
  moment of the run, which would have printed a fresh fetch time for a run that
  touched no network at all.

**To close it:** nothing to close. Revisit if EI publishes an API or the
challenge is lifted.

---

## 15. JODI's yield denominator. The physically right one is the one JODI has never assessed

**Status: open by design. It is a modelling choice SPEC.md has not made, it
belongs to Gate 3, and the adapter publishes both sides so it can be made in the
open.**

SPEC.md section 4.3 layer 4 says "Compute NWE yields from JODI refinery output by
product over refinery intake". Done literally, on the five country sums in kb/d,
the total does not come to 1:

| Month | `REFINOBS`/`CRUDEOIL` | `REFGROUT`/`TOTPRODS` | Ratio |
|---|---|---|---|
| 2019-06 | 5,276.7 | 6,103.0 | 1.1566 |
| 2022-10 | 4,995.8 | 5,761.0 | 1.1532 |
| 2025-06 | 5,111.3 | 5,789.0 | 1.1326 |
| 2026-06 | 5,147.1 | 5,867.0 | 1.1399 |

The numerator is gross output, including refinery fuel, from all refinery feed.
The denominator is crude alone. Using those ratios as `yield[p]` in
`contribution[p] = yield[p] * crack[p]` would inflate the decomposed margin by
about 15 percent. Switching the denominator to `REFINOBS`/`TOTCRUDE`, total
refinery feed, gives 1.0338, 1.0132, 1.0314 and 1.0241, which is volume gain and
is physically right, at the cost of seven years of history: `TOTCRUDE` starts
2009-01.

**One fact that bears on the choice and is not in recon 03.** JODI carries
assessment code 3, "Data has not been assessed", on EVERY total refinery feed
cell, in all five countries, for the whole life of the series: 1,050 of the 1,050
country cells in `jodi_nwe_refinery_intake_monthly`. Crude only intake is code 1
almost everywhere, 1,469 cells against one code 2 in the latest month. So the
physically better denominator is the one JODI has never checked, and the assessed
one is the one that gives a yield vector summing to 1.15.

Both are published, side by side, in the same cache, with their codes. Neither is
chosen in a data adapter, where the choice would be invisible to the Method view.

**To close it:** Gate 3 picks one, states it on the Method view with this table
next to it, and shows the decomposition both ways if the difference changes which
crack is said to be carrying the barrel.

---

## 16. JODI publishes no data licence, and its four missing value tokens are undefined

**Status: open, low risk, and worth one email before Gate 5.**

The JODI terms of use are website terms, not a data licence: "The Intellectual
Property rights in the JODI Website, and in the material published on it, are
protected by Intellectual Property laws and treaties around the world. All such
rights are reserved." The downloads page says the data can be downloaded for
free, which is a statement about access and not about republication. There is no
CC notice, no citation policy page, and no data licence page: the site map lists
one legal page. Committing a small derived extract with clear attribution is
normal practice among energy analysts and it is not covered by a grant, which
makes it materially weaker than FRED or EIA.

What this repository does: commits the parsed five country extract with
attribution, never mirrors the raw annual files, and records the position in the
manifest entry of all three JODI series.

Separately, and not verified: `OBS_VALUE` carries four non numeric tokens, `N/A`,
`x`, `-` and `..`, and neither the manual nor the item names guide defines them
apart from one another. All four are treated as missing and none is interpreted.
None appears in any series this study reads, so this is robustness rather than a
live problem, and a fifth token raises rather than becoming a number.

**To close it:** email `JODIinfo@ief.org` before Gate 5, asking whether a derived
monthly extract for five countries may be published with attribution, and what
the four tokens mean.

---

## 17. JODI's lag is 2.4 to 2.9 months, not the two SPEC.md assumes, and the capacity denominator stops in 2025

**Status: measured, not a question, recorded because two pieces of site copy
depend on it.**

Data ran to 2026-06 when the annual files were last written on 2026-08-20, and
the next release is the 22nd of the following month, so the gap widens to almost
three months just before each release. SPEC.md section 13 says "about two
months". SPEC.md section 7.2 already requires the runs data date shown separately
from the margin data date, which is the right answer, but the landing view's
sentence about "whether runs have room to rise" is necessarily about a quarter
old and the copy must not imply otherwise.

At the other end, there is no 2026 refinery capacity anywhere in the Energy
Institute workbook, and the 2026 edition stops at 2025. Every 2026 utilisation
figure therefore rests on an assumption about capacity that no source has
published. `crack.sources.ei.capacity_monthly` returns NaN past the last
published year end rather than carrying 2025 forward, so the assumption has to be
made in the analysis, where it can be labelled, rather than inside something that
looks like it read a number.

**To close it:** nothing to close before the 2027 edition. The Method view states
both dates and the assumption.

---

## 18. A workstation setting blocks the editor tools from every path containing the word "seed"

**Status: not a project question. Recorded here because it will confuse the next
person for twenty minutes.**

The global Claude settings on this machine carry `Read(**/*seed*)` in their deny
list, a rule plainly meant for wallet seed phrases. It also matches
`data/seed/`, so the file editing tools refuse to open
`data/seed/eia_refinery_fuel_2023.json`, `tests/test_seeds.py` and anything else
under that directory. The pipeline itself is unaffected, because it opens those
files with ordinary Python, and so is the test suite.

**To close it:** narrow the rule to something like `Read(**/*seed*phrase*)` or
`Read(**/.seed)`, in the user's own settings. Do not move the directory: SPEC.md
section 8 names `data/seed/` and the seeds belong there.

---

## 19. Does the owner accept the chart reconstruction as a published series

**Status: open, and it is the single biggest editorial decision in the project.**

`dgec_note_reconstructed_weekly` is 219 weekly observations recovered from the
vector polylines of a chart DGEC drew, calibrated against the printed figures on
the same page. It is the only weekly crack series available free anywhere recon
05 looked, and without it SPEC.md's CV line, "across gasoil and gasoline cracks",
cannot be honoured at weekly resolution.

The six conditions recon 05 section 14 sets are all implemented and tested:
separate series and manifest entry, the measured error carried in the data,
the 25 weeks with no cross check flagged, Brent flagged as the least accurate of
the four, the axis degeneracy disclosed, and a decode that fails loudly rather
than guessing. The error is 0.17 to 0.44 $/t out of sample, 0.87 $/t worst
anchor, 0.30 $/t agreement between overlapping notes. See `docs/methodology.md`
section 1.

**To close it:** the owner says yes or no. If yes, the framing on the Method view
has to be written once, carefully, and not hedged: the ministry prints two weeks
and deletes last week's note, so the printed numbers amount to eighteen
observations and the chart in the same document is its own record of 105 more.
If no, the site falls back to the OPEC monthly cracks and says at weekly
frequency that no free source exists.

---

## 20. Recon 05 section 12 names the wrong 25 weeks

**Status: measured and corrected in place. No action needed, recorded so the
next reader does not trust the sentence over the data.**

Recon 05 section 12 says the 25 weeks covered by a single note are "the 20
oldest, 2022-07-01 to 2022-11-11, and the 5 newest, 2026-08-07 to 2026-09-04".
The count is right. The split is not. They are the **six oldest, 2022-07-01 to
2022-08-05**, and the **nineteen newest, 2026-05-01 to 2026-09-04**.

Recon 05's own demonstration output contradicts its own sentence: it prints
`n_notes` of 1 for six rows and 2 from 2022-08-12 onward, which is what the note
coverage implies, since `wb_NPG-2024.06.21` reaches back to 2022-07-01 and
`wb_NPG-2024.07.12` only to 2022-08-12.

It matters because it moves nineteen of the twenty five uncorroborated weeks into
the RECENT end of the sample, which is the end a reader looks at first, rather
than leaving them safely in 2022. `tests/test_sources_dgec_note.py` asserts the
corrected split.

---

## 21. Two series were renamed against the names already in config.SOURCES

**Status: done, recorded because the old names appear in earlier reports.**

`dgec_npg_quotations` is now `dgec_note_printed_weekly` and `dgec_chart_weekly`
is now `dgec_note_reconstructed_weekly`. The registry entries were placeholders
written before either adapter existed. The new names are the ones the Gate 1
task specified, and they are better: they say which document the series comes
from and, in the second case, what was done to it. `tests/test_base.py` and
`tests/test_dgec_anchor.py` were updated in the same change. Nothing else
referenced the old names.

---

## 22. The reconstruction stops growing the week nobody runs the collector

**Status: open, and it is an operational question rather than a technical one.**

DGEC publishes one weekly note and deletes the previous one. The Internet Archive
holds nine and is not picking up new ones: the CDX for the host returns seventeen
rows covering nine distinct filenames, recon 02 section 2.5, and none of them is
recent. So the corpus grows only when someone runs

```
python scripts/note.py
```

which is two polite requests and adds the current note if it is not already held.
Every week that is not run is a week that is gone, permanently, for everybody.

Two further consequences the owner should decide about. First, the note PDFs are
not committed, so a fresh clone of this repository cannot rebuild either weekly
series: the caches are committed and the documents behind them are not. That is
the right call under the licence mitigation recorded in `config.SOURCES`, and it
means the committed CSV is the archive. Second, a scheduled job would close the
gap, and a scheduled job that commits its result is a mirror of a ministry
publication, which is permitted under Licence Ouverte 2.0 with attribution but is
worth the owner deciding deliberately rather than discovering.

**To close it:** either put the collector on a weekly schedule, or accept that
the series ends whenever collection stops and label the last date on the page.

---

## 23. The gasoline crack disagrees with OPEC by up to 22 $/bbl and neither cause can be separated

**Status: open, unresolvable with what this project holds, and published rather
than closed.**

Over the 44 months both sources cover, the reconstructed Eurosuper crack minus
the OPEC Rotterdam premium gasoline 98 crack has a mean of **-8.82 $/bbl** and a
range of **-21.97 to +0.07**, both legs taken against the same Brent. The gasoil
comparison over the same months is +1.10 mean and 1.58 mean absolute, so the
gasoline gap is not a general calibration problem, it is specific to that
product.

Two causes, and this project can separate neither:

* the implied barrels per tonne between the two sources runs **6.937 to 8.333
  over those same 44 months, mean 7.7185, median 7.8429**, against the ICE
  contract's 8.33 that `config.BBL_PER_T_GASOLINE` uses. The centre of that
  distribution is nowhere near 8.33: applying 8.33 leaves the MOMR row 8.82
  $/bbl above DGEC's Eurosuper on average. But the maximum, **8.3333 in February
  2025, is the contract factor to three decimals**;
* DGEC's Eurosuper is finished premium gasoline and the MOMR row is premium
  unleaded as assessed by Argus. They are different products.

**A CORRECTION, ON THE RECORD.** This section used to say the implied factor
runs "7.42 to 8.15, never the ICE contract's 8.33", which contradicted section
12 of this same document and was false by this project's own measurement: the
measured maximum is 8.333. The Gate 1 self audit found the contradiction,
finding 3.2. The six month sample it came from is real and every one of its
values reproduces; it was a subset presented as the whole overlap. The true
statement is stronger than the false one and it was already two sections
earlier, which is the uncomfortable part. `src/crack/config.py` carried the same
stale sentence and now carries the 44 month figures, because `config.py` is
where SPEC.md section 4.1 sends a reader to check a constant.

**To close it:** nothing in reach closes it. Deriving a factor from the DGEC
methodology note would at best replace one convention with another and would
still not make two different products the same product. The decision already
taken, and the one to keep unless the owner overrules it, is to hold 8.33, cite
the ICE contract, carry both series under their own labels and show the gap. A
factor chosen to close it would be the tuning SPEC.md section 6.6 forbids.

---

## 24. Offline byte idempotence is bought by not bumping `checked_at`

**Status: a deliberate trade, made once, and worth the owner seeing.**

`scripts/refresh.py --offline` is byte idempotent: run it twice on an unchanged
tree and `data/manifest.json` is byte for byte what it was. That property is what
makes `git diff --exit-code data/manifest.json` a meaningful CI check rather than
a timestamp generator, and the task that built the orchestrator required it.

It is bought with a small lie of omission. The manifest carries `generated_at`, a
`run` block, and a `checked_at` per entry. All three move on every run whether or
not anything about the data changed, so all three are excluded from the
comparison that decides whether to rewrite the file, and when nothing else has
changed the previous bytes are written back unchanged. **So a no change run does
not record that it happened.** `checked_at` says when the entry last changed, not
when it was last checked, and the console output is the only record that today's
run took place.

The alternatives are all worse. Rounding `checked_at` to the day still changes
daily. Writing the run into a separate file moves the problem. Dropping
idempotence makes the CI check worthless, which is the thing it was built for.

**To close it:** either accept it and make the provenance panel print
"last changed" rather than "last checked" against that field, or have CI record
its own run time somewhere outside the manifest.

---

## 25. Two S&P Global URLs and one Business Wire URL refuse automated access

**Status: measured on 2026-09-13, recorded in the data, not closeable from here.**

Of the twenty one entries in `data/seed/events.json`, every URL was requested once
with curl, following redirects. Seventeen answered HTTP 200. Three do not:

| URL | Result |
|---|---|
| the S&P Global article of 28 March 2022, SPEC.md section 5.6 | HTTP 403, 575 bytes, to a bot token user agent and to a browser user agent alike |
| the S&P Global article of 17 October 2022, SPEC.md section 5.6 | HTTP 403, 596 bytes, same both ways |
| the Business Wire copy of the ICE Russian free gasoil release, SPEC.md section 5.6 | curl could not complete the request at all with a bot token, and HTTP 403 with a browser string |
| `https://www.opec.org/monthly-oil-market-report.html` | HTTP 403, 5,749 bytes, which is the same Cloudflare refusal recon 05 measured |

The Business Wire one is already solved: ICE publishes the identical release on
its own investor relations site, which answers 200, and that is the URL in the
seed. Recon 04 section 6.6.

The two S&P articles are not solved. They open in a browser and they are the
source of five figures SPEC.md itself quotes. Those five figures are therefore
**transcribed from SPEC.md, which quotes the articles, rather than re read from
the source**, and `data/seed/anchors.json` says so in words next to each one.
That is the honest position and it is weaker than every other citation in this
project.

**To close it:** the owner opens both articles in a browser, checks the five
figures against what is printed, and either confirms them or corrects them. It is
five minutes of work that nothing automated can do.

---

## 26. `anchors.json` is one file with two manifest entries, because its two blocks are under different terms

**Status: a design decision, recorded because it looks odd until you know why.**

SPEC.md section 8 puts `anchors.json` in `data/seed` as one file. The file holds
two things under two different sets of terms: the DGEC anchors of SPEC.md section
5.5, which are Licence Ouverte 2.0 and freely republishable, and the S&P Global
order of magnitude figures, which are quoted from two news articles under
ordinary quotation and are not redistributable as a series.

SPEC.md non negotiable 6 records reuse terms **per source**, and the manifest is
where a reader looks them up. One entry would have had to carry one
`licence_note` for two sets of terms, and whichever one it carried would have
been wrong about half the file. So the file produces two entries, `anchors` and
`sp_global_reference`, both naming `data/seed/anchors.json`, and
`tests/test_events_anchors.py` asserts that they name the same file and that
their licence notes differ, because identical notes would mean the split was
pointless.

The alternative was two files, which would have put two hand written anchor files
in `data/seed` for no gain and would have disagreed with SPEC.md section 8's own
list.

**To close it:** nothing needs closing unless the owner would rather have two
files. Named here so that the next reader of the manifest does not file the
duplicate `file` field as a bug.

---

## 27. Five of the six July 2026 quotation anchors still cannot be checked, and now they are in the data saying so

**Status: unchanged since the DGEC batch, restated because it is now visible in a
committed artifact rather than only in a test skip message.**

SPEC.md section 5.5 prints six July 2026 monthly averages in $/t from the note of
28 August 2026. One of them, Brent date at 628, reproduces exactly. The other
five, Eurosuper 1,084, Gazole 1,160, Fioul domestique 1,127, Jet 1,204 and Fioul
lourd TBTS 507, cannot be checked at all, for two reasons that both have to go
before they can be:

* the August 2026 notes are deleted from the ministry site and were never
  archived, so the page those figures are printed on cannot be opened by anyone
  today. The SPEC.md section 5.6 URL for that note returns 404, checked
  2026-09-13;
* no series in this repository carries a July 2026 monthly average in $/t for
  those five products. `dgec_note_printed_monthly` holds the seven months the ten
  surviving notes print, 2025-11, 2025-12, 2026-02, 2026-03, 2026-04, 2026-08 and
  2026-09, and July 2026 is not among them.

**AMENDED AFTER THE GATE 1 SELF AUDIT, finding f.** There is now one reason
rather than two, and the test measures it instead of stating it.
`tests/test_dgec_anchor.py` used to call `pytest.skip` **unconditionally**, with
a message whose first stated reason was that
`data/cache/dgec_note_printed_weekly.csv` "does not exist, so no series in this
repository carries the Rotterdam quotations". That file exists, is committed, is
eighteen rows and carries those quotations. The sentence had been written before
the note adapter was built and was never updated, so the suite printed something
untrue five times on every run, and the only function that could ever have turned
the skip into an assertion, `build_printed_monthly()`, had zero callers.

Both halves are fixed. `build_printed_monthly()` is now the
`dgec_note_printed_monthly` adapter, so the monthly columns are a committed
series. The five tests open that cache, look for a 2026-07 row, and skip only if
it is absent, printing the months the cache does hold. **The day a note carrying a
July 2026 monthly column is collected, the row appears and the five tests become
assertions with no edit to any file.** A sixth test asserts that the skip
condition and the skip message describe the same file.

They are also in `data/seed/anchors.json` with `"status": "unverified"`, a
`status_note` saying all of the above, and the 404 recorded against the URL, and
`tests/test_cache_values.py` asserts that the seed file and the monthly cache
agree about what is missing, so the day one changes the other cannot stay behind.

**To close it:** nothing in reach. If a copy of NPG-2026.08.28 ever surfaces, the
five become checkable in one run. Otherwise they stay unverified, and the weekly
collector is what stops the same thing happening to every future month.

---

## 28. The 2026-03-11 IEA stock release date is pinned by a quotation, not by the `source_url`

**Status: open in a narrow and specific way. The date is supported; the field
that looks like it supports it does not.**

SPEC.md section 6.5 lists the IEA collective action as `2026-03` and says "Pin
the exact date from the source". `data/seed/events.json` pins it to 2026-03-11
with `date_precision: "day"`, and the entry carries a `source_quote` containing
the words "11 March" together with an `additional_sources` entry on `iea.org`;
`tests/test_events_anchors.py::test_the_iea_release_is_pinned_to_a_day` asserts
all three. So the day is not a guess.

What the Gate 1 self audit found, point 10 item 3, is narrower and is still true:
the entry's primary `source_url` is a report landing page rather than the
document that states the date, and the same is true of three other entries, the
two OPEC respecifications and the two World Bank definition changes. Those three
are corroborated inside the parsed data itself, which is why they are believed,
but **the `source_url` field does not carry the evidence it appears to carry**.
Offline there is no way to check any of them against the source.

**To close it:** replace each of those `source_url` values with a deep link to
the page or PDF that states the date, and requote the sentence in
`source_quote`. SPEC.md section 6.5 also permits the honest alternative, which is
to carry the month with a `date_note` saying why no day could be pinned, the way
`ice_gasoil_10ppm_2015` and `ice_gasoil_russian_free_end_2022` already do.

**Why it was not done in this pass, and this is a workstation limit rather than a
judgement:** `data/seed/events.json` could not be opened or edited. The global
deny rule described in section 18 of this document, `Read(**/*seed*)`, matches
every path under `data/seed/`, and the editing tools refuse it. Nothing was
worked around to get past it. The one line change is the one described above and
it needs whoever can open the file.

---

## 29. A spread of zero used to mean two different things, and the reconstruction's error bar still measures the wrong axis

**Status: the first half is fixed in the data. The second half cannot be fixed
and is now labelled everywhere a reader will meet it.**

Two Gate 1 self audit findings, kept together because they are the same mistake
at two scales: a number that looks like evidence and is not.

**Fixed, finding e.1.** `dgec_note_reconstructed_weekly` wrote `0.0` into its four
`spread_*` columns on the 25 weeks covered by a single chart geometry, and
`dgec_note_printed_weekly` wrote `0` into `max_disagreement_usd_t` on the 16 of 18
weeks printed by a single note. A spread over one observation is undefined, not
zero, and a zero there reads as a positive claim that two readings agreed. The
module's own `DEGENERATE_PAIR` constant already said, about a different case, that
"a spread of zero between them is arithmetic, not agreement", and
`opec_rotterdam_products_monthly` had always written `NaN` in the identical
situation. Both files now write `NaN`, which `write_cache` renders as an empty
cell, `tools/validate-data.mjs` skips as unmeasured, and `UNDEFINED_SPREAD` in
`crack.sources.dgec_note` explains in the manifest. **Anything rendering these
columns must print the empty cell as "no cross check", never as "0.00".**

The new `dgec_note_printed_monthly` follows the same rule: `max_revision_usd_t` is
empty for a month printed once.

**Not fixable, finding c and point 10 item 1.** The reconstruction's declared 0.17
to 0.44 $/t error is a **leave one series out** figure and all eight anchors of
every note sit on the last two weeks of a 105 week chart. It is **out of sample
across products and in sample across time, and it does not bound the other 103
weeks.** No rearrangement of the existing evidence changes that, because there are
no anchors anywhere else on the chart and there never will be: the anchors are the
two weekly columns the note prints, and the note prints two.

The consequence is measurable and the audit measured it. A smooth distortion
anchored at the right hand end is invisible to every gate: bending the left end by
10 points moves the oldest week by **73.49 $/t**, about 10 $/bbl on the gasoil
crack, while the headline anchor residual gate reads **0.711 against its limit of
1.50** and everything else passes. A pure translation, by contrast, is absorbed
exactly, which is correct.

What defends the series is the overlap between notes, because a given week sits at
a different horizontal position in each note that draws it, and 194 of 219 weeks
have two or more independent geometries with a mean spread under 0.65 $/t. **The
25 that do not have no defence against it.**

*(Those two counts are the series as it stood when this question was written. The
note collected on 18 September 2026 reached back over the whole run: the figures
today are 214 of 221 cross checked and 7 uncorroborated, six of them the oldest.
`docs/methodology.md` sections 1.6 and 1.12. The count is read from
`data/cache/dgec_note_reconstructed_weekly.csv` everywhere it is published, and
`tests/test_sources_dgec_note.py` fails if a published copy of it goes stale.)*

**Labelled rather than closed, in four places:** `docs/methodology.md` sections 1.5
and 1.6 in those words; the `reconstruction` block of the manifest entry, under
`error_bar_axis`, `gates_are_blind_to` and `least_defended_weeks`; the series note
the provenance panel prints; and the new `evidence_class` column, which separates
the six weeks that are weak twice over from those that are weak once, nineteen of
them then and one of them now.

**Unchanged in kind at Gate 5, and not re-attacked.** More notes have been
collected since this was written, so the uncorroborated set has fallen from 25
weeks to 7, and every one of them is drawn hatched and named. That is a smaller
target, not a defended one: the six oldest weeks still have neither an
independent geometry nor an anchor near them, the 10 point bend still moves the
oldest week by 73.49 $/t, and nobody has tried a different attack on it since
Gate 1. The honest statement is that this is the reconstruction's one real
vulnerability, that it is labelled everywhere it is drawn, and that the only
thing that would close it is a second note plotting those six weeks at a
different place on its chart, which would have to be found rather than
computed.

---

## 30. Pixel quantisation in the reconstruction cannot be told apart from a flat week

**Status: open, unprovable case by case, recorded in the data's own documentation
rather than left for a reader to notice.**

Gate 1 self audit, point 10 item 2. A decoded value is the calibrated height of a
point on a vector curve, but the curve was drawn from rounded data onto a finite
grid, so two different weekly prices can land on the same height. Eurosuper reads
exactly **719.1192666134755 on 2024-09-20, 2024-09-27 and 2024-11-01**. Three
weeks at an identical price to thirteen decimal places is not what happened.
Nothing in the file distinguishes a genuinely flat week from a quantisation
collision, and no single case can be proved either way without the underlying
prices, which is the whole problem.

**To close it:** nothing closes it for the 219 reconstructed weeks. The printed
table is the cure and it covers 18 of them. The rule for anyone reading the file,
stated in `PIXEL_QUANTISATION` in `crack.sources.dgec_note`, in
`docs/methodology.md` section 1.6 and in the manifest: treat an exact repeat of a
reconstructed value at adjacent weeks as "indistinguishable at the resolution of
the chart", never as "the price did not move".

A per week quantisation flag was considered and not built. Marking every exact
repeat would flag the genuine flat weeks too, which would be a guess dressed as a
measurement, and this project does not put guesses in columns.

---

## 31. The Makefile described a CI that does not exist

**Status: the wording is fixed. The CI is still absent, deliberately, and that is
a real gap in SPEC.md non negotiable 7 until Gate 5.**

Gate 1 self audit, finding 6.1. `.github/workflows/` exists and is empty. There is
no `build.yml` and no `refresh.yml`. The `Makefile` nonetheless described its
`gate` target as running "the same commands in the same order as CI, so a green
run here is a green run there", and said "CI adds one step this target does not".
All of that described something that is not there.

SPEC.md non negotiable 7 says the CI gate IS the deploy gate, and SPEC.md section
10 puts both workflows at Gate 5. So the honest position, and the one the Makefile
now states, is that `make gate` is a **manual** step standing in for a workflow
that has not been written, and that one step belongs in the workflow when it is:
`git diff --exit-code data/manifest.json` after the offline refresh, which only
means anything on a clean checkout.

The workflows were not written in this pass on purpose. They are Gate 5 work and
writing them at Gate 1 would be building UI ahead of approval, which SPEC.md
section 10 forbids in the same sentence.

---

## 32. The new monthly quotation series is seven months long and cannot grow backwards

**Status: a limit of the source, not a gap in the work. Recorded so nobody plots
a trend on it.**

`dgec_note_printed_monthly` exists because the Gate 1 self audit, finding 1.1,
found the decoder reading the monthly columns and their `(donnees provisoires)`
markers correctly on every run and then throwing them away. It is the answer to
SPEC.md non negotiable 5 and it is **seven rows**: 2025-11, 2025-12, 2026-02,
2026-03, 2026-04, 2026-08 and 2026-09.

It is seven for a reason that will not change. The six column layout printing
monthly averages first appears in the December 2025 note, recon 02 section 3.3,
so no earlier note has the columns at all, and the ministry has deleted every
note the Internet Archive did not catch. Four months inside its own span, 2026-01
and 2026-05 to 2026-07, are missing because no preserved note prints them, and
those gaps are declared in the manifest rather than closed.

It grows only forward, two months at a time, and only if the weekly collector
runs. That is the same dependency as the weekly layer, manual step
`dgec_weekly_note_collection`.

**Do not build an analysis on it.** It is a provenance artifact and a vintage
record: it is the only place in this project where a DGEC figure is seen moving
from provisional to final, and the only monthly home of Jet and Fioul lourd TBTS
as DGEC $/t quotations. Seven months is not a series.

**To close it:** nothing closes the history. Running
`make note` every week is what stops it from
staying at seven.

---

## 33. Is DGEC's 1.0 percent gas line fuel only, or fuel plus hydrogen feedstock?

**Status: open, and it sets the size of the gas wedge. It does not affect the
margin, which is why the correction stands whatever the answer.**

The Gate 2 self audit, finding 1, established that DGEC's published MBR is
already net of purchased natural gas, so this study must not subtract its own gas
cost from it. That part is settled by the note's own words and nothing here
reopens it: `crack.engine.MARGIN_NET_OF_GAS` and `GasDoubleCountError` make the
double charge inexpressible, and `docs/methodology.md` section 2.3 carries the
reading.

What is not settled is the comparison that replaced the subtraction. The wedge
prices DGEC's embedded intensity and this study's EIA derived intensity at the
same gas price, and DGEC's embedded intensity is derived here from one line of
table 1, "Gaz naturel 1,0%", as 1.0 percent of a tonne of crude converted at the
method's own 7.55 bbl/t and at `config.GAS_MMBTU_PER_TONNE`, which is 49.757
MMBtu per tonne built from the Energy Institute's volumetric factor and EIA's
gross heat content. Both of those are cited and both are recomputed in a test.

The open part is what the 1.0 percent COVERS. The note says the refinery buys gas
"pour completer la couverture de ses besoins en combustible interne et en
hydrogene", which reads as fuel and feedstock together, but it does not say so in
the table and it does not split the line. EIA's US split is roughly 86 percent
fuel to 14 percent feedstock, so the reading is worth about a sixth of the
embedded intensity.

The consequences, bounded:

- If the 1.0 percent is fuel AND feedstock, the embedded intensity is 0.0659
  MMBtu/bbl as computed, and the wedge in August 2022 is 10.24 $/bbl.
- If it is fuel only, DGEC's model refinery buys more gas than 1.0 percent of the
  tonne in total, the embedded intensity is larger, and the wedge is smaller.
- Either way the deduction stays at zero. A wedge is a comparison between two
  assumptions; it is never a line of the margin, and no figure on the site moves
  with it except the wedge itself.

**To close it:** ask DGEC what the 1.0 percent line covers, or find a French
refining energy balance that splits purchased gas between fuel and hydrogen.
Until then the Method view says the embedded intensity is this project's reading
of one line of table 1 and not a figure DGEC publishes.

---

## 34. SPEC.md section 9's Catches column says the Null row catches sign errors. It cannot.

**Status: a wording problem in the brief, left in the brief. The tests say what
is true and this entry says why SPEC.md was not edited.**

The Gate 2 self audit, finding 4, injected two sign errors of exactly the kind
the Null row claims to catch, adding the gas cost instead of subtracting it and
subtracting the residual instead of adding it, and all three Null tests passed
through both. They cannot do otherwise: every input in the Null case is zero, and
zero plus zero, zero minus zero and minus zero minus zero are all zero. Zero has
no sign to get wrong.

The rows that DID fire on those injections are Linearity and Round trip. So the
Catches column is attributing the work to the wrong row.

Three things were done and one was deliberately not:

1. `tests/test_engine.py` no longer claims it. The docstring of
   `test_null_case_is_exactly_zero_everywhere` says what the case is worth, an
   exactness check on the zero case, and says which rows are the sign tests.
2. A signed null was added,
   `test_a_signed_null_is_zero_only_because_every_sign_is_right`: four non zero
   terms of four different magnitudes that sum to exactly zero, so no single
   sign flip lands back on zero and no two cancel. It fires on both of the
   audit's injections.
3. The file header table carries the correction, because that table is what a
   reader of the tests sees first.
4. **SPEC.md was not edited.** It is the brief this work is measured against, not
   a document this build gets to rewrite to match what it did. The owner may want
   the Catches column to read "Linearity, Round trip: sign errors" and "Null: a
   term that should not exist", and that is a one line change, but it is the
   owner's line.

**To close it:** the owner decides whether SPEC.md section 9's Catches column
moves. Nothing in the code or the tests depends on the answer.

---

# Gate 3, the analysis

SPEC.md section 6. Nine entries. Several of them are the study finding nothing,
which SPEC.md section 2 rule 4 allows, and they are written as open questions
rather than as results because each one names something a later data date or an
owner decision could change.

---

## 35. This sample cannot tell the horses apart, and 132 months may never be able to

**Status: open. It is a question about power, not about these three regressors.**

*This question used to be headed "the horse race is a dead heat". The heading was
the claim the Gate 3 self audit, finding 2.1, took apart: a dead heat asserts
equality, and the measurement below supports only that this sample cannot
separate the three. The numbers in it have also moved, because finding 1.1's
capacity alignment changed the dependent.*

SPEC.md section 6.3 calls the horse race the point of the analysis and asks which
of the raw gasoil crack, the official margin and the margin after gas explains
NWE runs best. On the common sample the answer is **none of them is
distinguishable from another**. The expanding window out of sample RMSEs are
6.7601, 6.8159 and 6.7793 for A, B and C under the capacity dependent and 4.8911,
4.8070 and 4.7462 under the fallback, and **not one of the six pairwise squared
error differences is distinguishable from zero**, at t between 0.04 and 0.77.

**The measured power, which replaces an estimate that was too kind.** This
question used to say that calling a difference of that size on 72 forecasts would
need a squared error differential standard error "roughly an order of magnitude
smaller than the measured one". Measured properly it is a factor of 2.4 to 150 on
the effect, which is 19 to 100,000 times the number of forecasts. The table a
reader can check:

| Dependent | Pair | Observed RMSE gap | Smallest gap detectable | Power against the observed effect | Forecasts for 95 pct power |
|---|---|---|---|---|---|
| utilisation | A vs B | 0.819 pct | 7.42 pct | 0.054 | 24,575 |
| utilisation | A vs C | 0.284 pct | 12.28 pct | 0.050 | 670,408 |
| utilisation | B vs C | 0.536 pct | 8.31 pct | 0.051 | 74,845 |
| log intake | A vs B | 1.720 pct | 7.16 pct | 0.072 | 5,013 |
| log intake | A vs C | 2.963 pct | 7.05 pct | 0.121 | 1,570 |
| log intake | B vs C | 1.265 pct | 3.53 pct | 0.104 | 2,031 |

Read the power column against the size of the test, which is 0.050. **Four of the
six comparisons have power against their own observed effect of 0.05 to 0.07.** A
test whose power equals its size is a coin that always returns "not
distinguishable"; its failure to reject is arithmetic about the sample, not
evidence about the null. The kindest of the six needs about 1,570 monthly
forecasts, roughly 131 years of monthly data.

That is not a matter of a better estimator. The common sample is 132 months long
because DGEC's MBR file starts in 2015-01, and it grows by twelve months a year.

What was NOT done about it, deliberately: no third dependent was tried, no lag
structure was searched, no subsample was found on which one horse separates.
SPEC.md section 6.6 forbids all three and SPEC.md section 2 rule 3 says report
the result whatever it is. The module prints the ranking because the spec asks
for the numbers, and withholds the word "wins", and `horse_race_winner` assembles
that sentence from the measured loss differentials, so it will say something
different the moment the data does.

**To close it:** more months, or a reader who accepts that "these three are
indistinguishable on this evidence" is the finding. The site should say the
second thing, **and it now does**: `horse_race_winner` emits "this sample cannot
tell the horses apart" with the power beside it, `docs/methodology.md` section 4.6
prints the power table, and a test fails if the words "dead heat" come back.

---

## 36. Is the horse race still the spec's horse race once C is a substitution?

**Status: open. It needs the owner.**

Gate 2 established that DGEC's published MBR is already net of purchased gas at
DGEC's own embedded intensity, so SPEC.md section 6.3's horse B and horse C, read
literally, are **the same series**. Racing them would be two horses presented as
three.

What this gate did: horse C is the published MBR re-priced at this study's EIA
derived intensity, `MBR - (0.21217 - 0.06590) * gas price`, the substitution is
carried as a flag on the `Horse` record so no table can print it unlabelled, and
`analysis.report()` says so at the top of the section. The wedge ran 0.23 to
10.24 $/bbl over the sample, so the two columns are genuinely different and the
race is genuinely three horses.

What it is not: what SPEC.md section 6.3 wrote. Two other readings were available
and were not taken, because both are the owner's call and not a build decision.
The race could have been run as two horses with that said plainly. Or a fourth
runner could have been added, a margin this study builds itself out of cracks and
yields, which would be gross of gas and would let the spec's B and C be genuinely
distinct; that is a larger piece of work and it would need the product
quotations, which exist only from 2015 on the DGEC side and carry the
reconstruction error on the weekly side.

**To close it:** the owner says whether the substitution stands, whether the site
calls it horse C or something else, and whether a self built gross margin is
wanted as a fourth runner in a later gate.

---

## 37. The out of sample period is entirely the crisis period

**Status: open, and it is structural rather than fixable.**

The expanding window trains on 60 months before its first forecast. On a sample
that starts 2015-04 that puts the first forecast in **2020-04**, so all 72 out of
sample months fall between 2020-04 and 2026-03 and 25 of them sit inside one of
the three episode windows of SPEC.md section 6.1.

**The holdout is the pandemic, the invasion and the 2026 war.** Every out of
sample number in section 4 of `analysis.report()` should be read as "how these
three regressors did through three crises", not as "how they do".

The obvious fix is the wrong one. Shortening the training window to 36 months
would buy two quieter years of holdout and would be choosing a window after
seeing what it does to the answer, which SPEC.md section 6.6 forbids. The window
was set at 60 months, five years, on the reasoning that it is long enough to
identify eleven month dummies plus three lags, before any RMSE was computed, and
it has not moved.

Horse A's own longer sample gets 228 forecasts from 2007-04 and is a far more
varied test. That is one of the reasons it is reported beside the race rather
than in it.

**To close it:** nothing, until the sample carries a long quiet stretch after
2015. Worth restating on the site rather than closing.

---

## 38. The gas instrument is dead, and the reason is interesting enough to write down

**Status: closed as an instrument, open as a question about what else might work.**

SPEC.md section 6.3 suggests the gas cost as an instrument for the margin after
gas. The expectation, written down before running it, was that the first stage
would be **too** strong to be interesting: this study's margin contains the gas
price as an exact linear term with coefficient -0.14627, so relevance looked
mechanical.

**It came out at F = 0.215 with the controls the capacity equation carries and
F = 0.070 with the controls the fallback equation carries.** Those two were
described here as "on the capacity dependent" and "on the fallback" until the Gate
3 self audit, finding 3.1, pointed out that **the first stage contains no
dependent variable at all**: it regresses the endogenous margin on the controls
and the instrument. The two numbers are one control set with and without a single
column, the linear monthly trend, and the sign of the coefficient flips on it.

**The diagnosis given here was also wrong, by about two thirds.** This question
used to say the mechanical deduction of -0.14627 is roughly cancelled by the
margin's own co-movement with gas, and stopped there, as though the cancellation
explained the +0.043. Measured, the cancellation leaves **+0.10594**: the raw slope
of the MBR on gas is +0.23581, the mechanical term is -0.14627, the net raw slope
of the study margin on gas is +0.08954, and the first stage with a constant alone
is +0.10594, F 5.753. The collapse from there is the CONTROL SET:

| Controls | Coefficient | F |
|---|---|---|
| constant only | +0.10594 | 5.753 |
| plus month dummies | +0.10800 | 5.802 |
| plus episode dummies | +0.04306 | **0.215** |
| plus a linear trend | -0.02807 | **0.070** |

**And the episode dummies remove the instrument's own identifying variation.** The
instrument's standard deviation inside the three twelve month episode windows is
18.61 $/MMBtu against 5.31 outside them, and its maximum of 60.16 is 2022-10.
SPEC.md section 6.3 names exactly that variation as the reason to try the
instrument, "TTF was driven by pipeline cuts in 2022 and by LNG disruption in
2026", and SPEC.md section 6.1's equation then places a 0/1 step over each of
those windows and takes it out. **That is a more interesting result than "the
instrument is weak" and it says something real about why this identification is
hard:** gas does have purchase on the margin, the purchase is the crisis months,
and the equation's own regime terms remove the crisis months.

The exclusion restriction was also stated before the run and this study's view of
it is that it probably does not hold exactly: gas is a hydrogen feedstock as well
as a cost line, so a gas shock can change what a European refiner runs for
reasons the margin does not capture, and a gas shock arrives inside a wider
energy shock with its own routes to runs. So the instrument fails on relevance
and is doubtful on validity, and SPEC.md section 6.3's instruction is to say that
rather than force it. Nothing downstream reads the two stage estimates. **The
operational conclusion survives the corrected diagnosis without a scratch**: F is
below the rule of thumb bar of 10 under the spec's equation at 0.07 to 0.22, and
still below it at 5.80 on a constant and the month dummies with the 2022 shock
left in. What changed is the explanation, not the verdict. And to be explicit
about what was NOT done: the equation was not re-run without the episode dummies
in order to get a better F. That would be choosing a specification after seeing
what it does to a first stage, which SPEC.md section 6.6 forbids. The ladder is
reported as a diagnosis and the headline equation is unchanged.

**The endogeneity therefore remains unaddressed.** Runs move cracks, the bias is
toward zero, and every coefficient this study reports is a lower bound in
absolute value.

**To close it:** a candidate instrument that moves the NWE margin without
touching NWE runs through any other channel. Non European refinery outages and
Russian pipeline flow are the two that come to mind, and neither has a free,
redistributable monthly series this project has found. Not attempted, because
searching over candidate instruments until one has an F above 10 is a parameter
search wearing a different hat.

---

## 39. SPEC.md section 6.4 has no answer on this data date, and reopens in April 2027

**Status: open by arithmetic. Nothing to decide.**

SPEC.md section 6.4 asks whether the relation held after 2026-02-28. JODI
refinery intake, the dependent, ends 2026-06, so there are **four** post break
months with a dependent and all three margin lags. The bar set before looking was
twelve, one full seasonal cycle, because the equation carries eleven month
dummies.

**Four months cannot say whether a relation held**, so no verdict was returned
and no test was run that would have produced a number looking like one.

What is reported instead: the equation fitted on months to 2026-02 and each post
break month predicted out of sample, with the episode dummies deliberately off,
since a 2026 dummy would absorb exactly the deviation being looked for. Runs came
in below what the margin implies in four of four months on the capacity model and
three of four on the fallback, the largest gap 1.79 in sample residual standard
deviations. Three explanations are set out and cited, feedstock availability,
unplanned outages and maintenance timing, and **none is chosen**, because four
monthly observations cannot separate three explanations and JODI publishes no
outage or turnaround series that would let them be separated.

**To close it:** the JODI release covering 2027-02, around April 2027. Then the
same function returns a verdict instead of a count.

---

## 40. The gasoil seasonal window everybody quotes is not the one in the data

**Status: open. It is a question about what the site should draw.**

SPEC.md section 6.5 asks for the textbook pattern to be checked rather than
asserted. Checked, on 25 complete years of OPEC Rotterdam quotations, each year
demeaned by its own mean so the level swings between years do not drown the
shape:

* **Gasoline into the driving season holds and is not close.** May to September
  sits +4.78 $/bbl above the rest of the year, t +4.64, positive in 22 of 25
  years, and it survives removing 2020, 2022 and 2026 (+4.31, t +5.07).
* **Gasoil into the heating season does not hold.** The contiguous winter,
  November and December of one year with January to March of the next, sits -0.44
  $/bbl from the rest of the two years it spans with a standard error of 0.75,
  t -0.59, on 24 winters. It is nothing under every window tried: t -0.59 on the
  contiguous winter, -0.35 on a calendar year November to March window, -0.18 and
  +0.35 on the same two with the crisis years removed.

**Two sentences this question used to carry were artefacts and are gone.** Gate 3
self audit, findings 5.2 and 5.3.

* It said the gasoil window is "positive in only 16 of 25 years". That count comes
  from applying November to March **inside one calendar year**, which averages the
  head of one winter with the tail of the one before it. Under a contiguous winter
  it is **positive in 10 of 24**, a minority, and the reassuring reading that the
  sign was usually right and the mean was dragged down does not survive.
* It quoted -0.37 as the estimate. That sign rests on two observations out of
  twenty five, 2022 at -18.81 and 2008 at -10.74 against a next most negative year
  of -6.39, and under the calendar window the mean and the median have opposite
  signs, -0.37 against +0.36. The honest statement is that the gasoil winter
  effect is indistinguishable from zero under every definition tried, and that a
  signed point estimate gives it more standing than the data supports.

The conclusion is unchanged and it is the one SPEC.md section 6.5 asked to have
checked rather than asserted: **on this sample the textbook gasoil pattern does
not hold**. Only the sentences supporting it have been replaced by ones that are
true. The study now reports the contiguous winter as its window, because that is
the season a cold week falls in, and prints the calendar year window beside it so
the size of the artefact is visible.

The month by month shape says why. The gasoil crack's strongest months are
**October** at +3.00 and November at +2.09, and December, January and February
are all negative. Such strength as there is arrives in the autumn build and has
faded by the middle of the winter it was built for.

**A window drawn around that October peak would fit, and it is not tested and no
number for it is reported.** A window chosen after seeing the table is a
parameter search and SPEC.md section 6.6 forbids it. Writing one down now for a
later gate to test on later data would be legitimate; testing it on the same 25
years would not.

**To close it:** the owner decides whether the Cracks view draws the desk's
November to March window and reports that it fails, draws the measured shape and
lets the reader see the October peak, or both. This study's recommendation is
both, with the failed test printed, because the failure is the more useful fact.

---

## 41. The five year weekly seasonal range SPEC.md section 6.5 asks for does not exist

**Status: open. It needs the owner.**

SPEC.md section 6.5 asks for each crack by week of year with the prior five years
as a range. The weekly layer is this study's reconstruction of the DGEC note
chart and it begins **2022-07-01**, so at most four calendar years are available,
and weeks in the first half of the year have only three. No arrangement of the
data produces five.

What was done: `seasonal_weekly` carries an `n_years` count on every week so a
chart prints the depth beside the band instead of drawing four years and calling
them five, and the long history is served from the monthly OPEC series, which
does carry five years for every month and is where the textbook check above is
run.

**The two layers are not spliced and must not be.** They quote different
products, DGEC's Gazole and Eurosuper against OPEC's gasoil and premium gasoline.
Over the 44 overlapping months the weekly series averaged to months sits +0.92
$/bbl from the monthly one on gasoil, mean absolute gap 1.24, correlation 0.9935;
and **-9.01 $/bbl** on gasoline, mean absolute gap 9.02, correlation 0.8861. The
gasoline figure is the size of a different product, not an error.

**To close it:** the owner decides whether the weekly seasonal view ships with a
three to four year band labelled with its depth, or whether the seasonal view is
monthly only until the reconstruction has five years, which is 2027-07.

---

## 42. The two dependents disagree about whether there is a response at all

**Status: open, and it is the first half of this gate's finding carried forward.**

*The numbers below moved when the Gate 3 self audit's finding 1.1 was actioned
and the capacity denominator was lagged by a year. The disagreement did not.*

Under the capacity dependent, utilisation over Energy Institute capacity, **none
of the three horses has a coefficient distinguishable from zero**: A at -0.115
with a Newey-West standard error of 0.106, B at -0.107 with 0.276, C at +0.093
with 0.307. Under the fallback dependent, the log of NWE5 crude intake with a
trend and closure steps, **all three are positive and none of them quite clears a
t of 2**: A at +0.166 with 0.102, B at +0.400 with 0.240, C at +0.466 with 0.236,
so t of +1.64, +1.67 and +1.98.

The first half of this gate established the mechanism, as a labelled diagnostic
and not as a reported result: the capacity denominator is a step function that
fell 3.0 percent in the 2016 figure and 5.3 percent in the 2025 one, which under
the alignment rule of `docs/methodology.md` section 4.4 land in the dependent at
2017-01 and 2026-01, both inside the sample. SPEC.md section 6.1's capacity
equation carries neither a trend nor a closure step, so those jumps sit in its
dependent as noise, and adding both moves its coefficient 89 percent of the way to
the fallback's.

Neither model was declared the winner, because SPEC.md section 6.1 asks for the
capacity model and names the fallback as what to use "if the capacity table is
unusable", and the capacity table is usable. So both are reported with their own
standard errors.

**This matters for the site**, which has to put one number in the Runs and crude
demand view. Taking the SPEC.md section 6.1 equation under each dependent, the two
disagree about whether a 10 $/bbl move is worth **+59 kb/d** with an interval
spanning zero, or **+230 kb/d** with an interval that just does not.

**To close it:** the owner chooses which is the headline and which is the check,
or the view shows both side by side. This study's recommendation is both, since
the disagreement is a real feature of the data and hiding it would be the one
choice that is definitely wrong.

---

## 43. Nothing in this gate has been checked against a second implementation end to end

**Status: open. Flagged under SPEC.md section 11 point 10.**

Pieces of `analysis.py` are checked against independent implementations. The
Newey-West covariance is compared with statsmodels at three truncation lags on
the same data. The first stage F is compared with statsmodels on the same
regression, and separately rebuilt by hand in the test from the raw frame. Every
estimator is run against synthetic data with a planted answer: the lag
coefficients, the null, the kink, the absence of a kink, the two stage estimate
against a planted coefficient with a planted confound, and the seasonal
difference against a planted 5 $/bbl season.

What has **not** happened is anybody re-deriving the horse race, the expanding
window or the 2026 residuals from the committed caches in a different language or
a different library and getting the same numbers. SPEC.md section 7.1 requires
exactly that for the engine, Python against JavaScript, because the engine exists
twice. The analysis layer exists once, so there is nothing to compare it with,
and the tests above are the whole of the defence.

The specific things a second implementation would most likely catch, listed so
that a reader can weigh them: an off by one in the lag construction that the
planted coefficient tests would not see because they plant into the same
construction; a sample that is one month different from the one reported, which
the sample tests check the size of but not the membership of against an external
source; and an expanding window whose first origin is one row out.

**To close it:** somebody reruns the headline table from the caches without
reading `analysis.py` first. Worth doing before Gate 4 wires these numbers into a
site.

---

## 44. The capacity denominator's reference date is now honest and its publication date is not

**Status: open. It is the residual the Gate 3 self audit's finding 1.1 did not close.**

Finding 1.1 found this study dividing January of year Y by the Energy Institute
capacity figure stamped 31 December of year Y, a number describing a date eleven
months in the future. That is fixed: `CAPACITY_SOURCE_LAG_YEARS` is 1, month m of
year Y now carries the 31 December Y-1 figure, and a test fails if any month is
ever divided by a stamp later than its own first day. See `docs/methodology.md`
section 4.4.

**What is not fixed is the publication lag.** The Energy Institute volume carrying
the 31 December Y figure appears around the middle of year Y+1. So the denominator
for January 2025 describes 31 December 2024 correctly, and it was still not in
anybody's hands in January 2025. A strict real time reconstruction would lag by a
further year, dividing the months of year Y by the 31 December Y-2 stamp.

**That was not done, and here is the reasoning rather than a decision hidden in a
default.** A second year of lag would put a two year old capacity into every
month of the sample, which on a system that lost 5.3 percent of its capacity in
one year is a large and permanent error in the level of the dependent, in exchange
for a correction that matters only to a reader who wants the 72 out of sample
forecasts read as a real time simulation. The study's out of sample claim is about
the ESTIMATION, which the poison test in the audit proved clean to the bit, and
this question is the place where the remaining gap is recorded rather than
smoothed over.

**It would be a parameter choice to search over, and it is not being searched
over.** Choosing between one year and two years of lag by looking at which gives a
better R2 or a lower out of sample RMSE is exactly what SPEC.md section 6.6
forbids. One year is the lag the figure's own reference date implies, it was
chosen from that reasoning and not from a result, and it has not been moved.

**To close it:** the owner says whether the study wants a second, strictly real
time, utilisation series reported beside the headline one, with the difference
measured. That is a reporting decision and not a modelling one, and it costs one
more column rather than a different answer.


---

## 45. The run cut threshold is one episode, and no open question said so until now

**Status: open, and it is the single most important caveat on the headline the
site would most like to print.**

SPEC.md section 6.2 asks for a hockey stick, a grid search and a block bootstrap
interval, and says that if the interval is wider than 10 $/bbl or touches the edge
of the sample the threshold is unidentified and the site shows no headroom figure.
It came back **unidentified** on the edge rule: threshold 2.28 $/bbl, interval 2.03
to 11.28, which reaches the top of the searchable range. That much was in
`docs/methodology.md` section 7 in one line, and the Gate 3 self audit, finding
4.2, pointed out that questions 35 to 43 covered the race, the window, the
instrument, 2026, seasonality, the two dependents and cross checking, and **none
of them covered the threshold**, which is the one result the site's headroom
figure depends on.

**The reason it is unidentified is stronger than the interval.** 24 months sit
below the estimated threshold and 21 of them are one unbroken stretch, 2020-07 to
2022-03. Remove that stretch and rerun the whole search and bootstrap on the
remaining 114 months and the estimate does not merely widen:

| | With every month | Without 2020-07 to 2022-03 |
|---|---|---|
| Threshold | 2.28 $/bbl | **9.87** $/bbl |
| Slope below | **+3.8786** | **-0.4958** |
| Months below | 24 of 135 | **101 of 114** |
| Kink R2 less straight line R2 | 26.6 points | **1.0 point** |

**The slope flips sign.** Without the episode, runs rise as the margin falls below
the estimated kink, which is the opposite of the hockey stick SPEC.md section 6.2
describes. A kink whose slope reverses when one episode is removed is not a kink,
and the estimate, its sign included, **is** 2020-07 to 2022-03.

That check did not exist in the code either: `run_cut_threshold` had no way to
leave months out, while `margin_response` and `intake_trend_response` both
honoured SPEC.md section 6.1's "with and without the episodes". It does now, by
two arguments, and `analysis.report()` and `docs/methodology.md` section 4.10 both
print the result.

**To close it:** a second episode. The sample holds one stretch in which this
study's margin went negative and runs fell with it, and no behavioural level can
be estimated from one. It closes when Europe has another one, which is not
something to wish for, or when a longer margin series reaches back to 2008 and
1998, which needs a margin before DGEC's file starts in 2015-01 and is open
question 32's problem in a different form.

---

## 46. The two MOMR gasoline rows exchange values in twenty months, and the study cannot say which is the series

**Status: open, and probably not closable from published documents. The site now
draws both rows and says so.**

Open question 11 says the MOMR premium gasoline column is not one product across
2004 to 2013. This is the part of that which reaches a public chart.

**What was found.** Eight months of the History gasoline line sat below zero, all
of them on the sulphur graded row the cache leads with: 2012-02 -3.57, 2012-03
-5.72, 2012-05 -2.63, 2012-10 -0.36, 2012-11 -5.38, 2012-12 -3.92, 2013-01 -3.07
and 2013-03 -0.70. The octane graded row printed in the same table of the same
issues gives +10.01, +14.85, +15.88, +14.89, +8.83, +10.54, +11.99 and +14.07. A
Rotterdam gasoline crack below dated Brent for most of a year is not a market
anybody traded, and the view drew it as one unannotated dashed line.

**Which months.** In every month of the overlap from March 2005 on, the octane
graded row prints below the sulphur graded one, by 0.89 to 16.63 $/bbl. Twenty
months reverse that ordering, in two runs, 2010-05 to 2010-07 and 2012-02 to
2013-06. They are found by applying that rule to the committed cache rather than
by a typed list of dates. **The three months of 2010 had not been noticed before**
and they matter, because they carry the reversal with no restatement behind them:
the ordering simply flips for three months and flips back.

**The evidence that it is a swap.** February 2012 as the April 2012 issue printed
it is 129.29 on the sulphur graded row and 126.58 on the octane graded one; as
the May 2012 issue printed it, 115.76 and 129.34. The figure moved from one row
to the other to within 0.05 $/bbl. March 2012 moves the same way, 141.01 to
140.30. Open question 10 recorded the 13.53 and 21.28 $/bbl falls on the sulphur
graded row as an unexplained disagreement between issues; this is what they are.
Open question 10 stays open on the gasoil rows of the same two months, which move
8.80 and 10.46 and have no second row to move to.

**Why the study does not pick one.** OPEC's Annual Statistical Bulletin agrees
with the octane graded reading in 2005, 2006, 2012 and 2013 and with the sulphur
graded one in 2007 to 2011, with no label change anywhere between 2006 and 2007.
It follows neither row consistently, so it cannot arbitrate, and picking the row
that makes the chart behave is exactly what SPEC.md section 2 rule 3 forbids.

**What the choice changes.** Measured, in `analysis.gasoline_row_sensitivity`:
the driving season premium is +4.78 $/bbl, t +4.64, positive in 22 of 25 seasons
on the row drawn and +4.87, t +4.77, positive in 23 of 25 on the other, with June
the peak and December the trough either way. **No published figure changes.**
Nothing else reaches the window, and the sample start of everything that could is
checked against it rather than asserted.

**Treatment now:** both rows are drawn on the History gasoline panel over the
whole overlap, distinguishable without colour, the disputed months are bracketed
under the axis and listed with both readings in the panel's table, and the Method
view carries the issue evidence and the bulletin comparison.

**To close it:** ask OPEC or Argus which row the published series is, or find one
month of an independent Rotterdam premium gasoline quotation in $/bbl from a
third source inside the window. Until then it stays open and the site shows both.

---

## 47. The one figure recon 03 prints that its own columns do not give

**Status: settled as arithmetic, recorded because that figure is an anchor this
study is measured against.**

`src/crack/analysis.py` carries eleven annual NWE utilisation figures transcribed
from recon 03 section 2.3, and `utilisation_sanity_check` measures this study's
own annual utilisation against them. The Gate 5 audit is right that a
transcription from a document nobody else can open deserves more than a comment,
and checking it turned one thing up.

**The report's table prints 0.869 for 2015. Its own columns for that year do not
give 0.869.** The same row carries 5,936.5 kb/d of crude intake and 6,835.6 kb/d
of capacity, and 5,936.5 / 6,835.6 = 0.86844, which rounds to 0.868. This study
computes 0.868469 on its own committed caches. So the transcription in
`analysis.py` is 0.868: the report's arithmetic, not the report's third decimal.
The other ten years agree with both.

**What follows.** The anchor is the division, not the printed digit, and one cell
of a working note has a rounding slip in it. Nothing downstream moves: 0.868 is
what was always transcribed and what the study always reproduced, and the
difference the check reports for 2015, 0.000469, is the largest of the eleven
precisely because the printed digit was rounded the other way.

**What holds it now.** `tests/test_analysis.py`
`TestUtilisation::test_it_reproduces_what_the_physical_recon_measured` fails the
gate if this study stops reproducing one of the eleven to three decimals, and
`::test_the_transcribed_figures_are_the_ones_that_were_transcribed` fails if one
of the transcribed digits is edited. Before Gate 5 only the first existed, so the
study was checked against the transcription and the transcription against
nothing.

**To close it:** open the two primary sources for 2015, JODI's monthly crude
intake for the five countries and the Energy Institute capacity sheet, and
recompute. Nobody on this project has opened either, which is question 50.

---

## 48. Everything rendered has been measured in one browser engine, and never by a screen reader

**Status: open, and it cannot be closed by anything in this repository.**

Every layout, focus and contrast measurement in this project, at Gate 4 and at
Gate 5, was made in headless Edge 153, which is Chromium. `tools/check-layout.mjs`
runs there, `tools/browser.mjs` launches it, and the twenty checks at five widths
in both themes are all Chromium measurements. **No Firefox. No Safari. No screen
reader.**

**What was measured, so the gap is the right size.** Roles, accessible names,
descriptions, `aria-expanded`, `inert`, focus order, visible focus and its
contrast, reduced motion, and the rendered text of thirty view states. That is
the structure a screen reader reads from, and it is checked; what is not checked
is how any of it sounds. The Gate 5 audit says this of itself in its own words:
"I did not run a screen reader ... I am inferring that rather than having heard
it."

**Where the risk is concentrated.** The 375 px fold, measured at 1029 px of
content against an 812 px viewport, which depends on font metrics and wrapping;
scroll-into-view inside the horizontally scrolling tables, which is where Gate 4
found clipped focus rings; and `inert` on a closed section, which is the newest
of the three platform features the page relies on.

**Why it is not simply fixed.** Installing a second engine and a screen reader is
not a change to this repository, and a green check written by somebody who has
run neither would be worse than the sentence. So it is a sentence, and it is on
the Method view where a visitor meets it, not only here.

**To close it:** run `tools/check-layout.mjs` against a Firefox and a WebKit
build, and one keyboard pass of each view with NVDA or VoiceOver, and write down
what was heard.

---

## 49. `.github/workflows/refresh.yml` has never fired on its schedule

**Status: open until a Friday passes.**

The weekly collection job was committed on 2026-09-22, in `7eabe41`. Its cron is
`10 7 * * 5`, 07:10 UTC on Fridays, so **its first scheduled Friday is 25
September 2026 and it has not arrived.** `gh run list` shows no run of it at all:
every run in this repository's history is `build.yml` on a push.

**What has been exercised and what has not.** The work the job does is exercised
on every gate: `python scripts/refresh.py --offline` reads the committed caches
and rewrites a byte identical manifest, and the same script with the network is
how every cache in the tree was fetched. What has never been exercised is the
trigger, the runner's network reaching the ministry, the `contents: write` commit
of a refreshed cache and the `issues: write` path that is supposed to open an
issue when a validator fails.

**The failure modes worth naming.** GitHub disables scheduled workflows in a
repository with no pushes for sixty days, and this repository will go quiet.
A scheduled run can be delayed or dropped under load, which is why the job
collects first and publishes second. And the note the job is for is deleted from
the ministry's site a week after it appears, so a missed Friday is a week of
weekly prices that no later run can recover.

**What the site already says.** The README's refresh procedure says a missed week
can be collected by hand the moment somebody notices, and the workflow carries
`workflow_dispatch` for exactly that. That is the repair, and it is the only one
available.

**To close it:** read the run of 25 September 2026. Dispatching it by hand before
then would test everything except the thing in question.

---

## 50. No primary source was opened at any gate of this project

**Status: open, oldest in the project, and said by every audit of itself.**

Gate 1 said it: no DGEC note, no EIA table, no OPEC issue, no IEA report was
opened by the person writing the adapters. Gate 5 said it again, in the same
words, of itself. Between them the project has grown eleven transcribed
utilisation figures, four transcribed EIA figures, a set of quoted licences and a
publication date for the IEA stock release, **and every one of them is still a
figure somebody wrote down from a document, checked against other figures written
down from the same kind of document.**

**What that does and does not mean.** It does not mean nothing is checked: the
EIA seed was re-read from the source PDF's text layer on 2026-09-13 rather than
copied from the recon report, the eleven utilisation figures are reproduced to
three decimals from JODI and capacity data fetched by machine, the eight MBR
anchors of SPEC.md section 5.5 reproduce exactly from the committed workbook, and
the ministry's own printed weekly figures are what the reconstruction is
calibrated against. It means that if a transcription is wrong at the root,
everything downstream is consistently wrong and no check in this repository would
notice.

**Where it bites hardest.** The 11 March 2026 date for the IEA stock release,
which is one sentence in one event and is carried by a quotation rather than by a
`source_url` (question 28); the quoted reuse terms in `docs/sources.md`, which are
the basis of every committable decision in `data/manifest.json`; and the eleven
figures of question 47.

**To close it:** open them. One afternoon with the five documents named in
`docs/sources.md` section 6 closes more of this project's remaining doubt than
any further code.
