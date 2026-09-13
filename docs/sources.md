# Sources

Every source this study reads, what it is, where it was read from, what its terms
permit **in the source's own words**, whether its cache may be committed, how
often it moves, and the traps somebody rebuilding this will otherwise fall into.

SPEC.md non negotiable 6 requires reuse terms per source. Quoting them rather
than summarising them is deliberate: a paraphrase of a licence is a claim about a
licence, and the reader of a portfolio repository should be able to check it in
one click. Every quotation below was read from the URL printed next to it. Where
this project disagrees with itself about what a clause means, the disagreement is
in section 4 rather than resolved silently.

Nothing in this file is legal advice and nobody here is a lawyer. It is a record
of what was read, when, and what was decided on the strength of it.

---

## 1. The table

| Series | What it is | Machine URL | Page | Cadence | Cache committed | Licence |
|---|---|---|---|---|---|---|
| `dgec_mbr_monthly` | DGEC gross refining margin on Brent, monthly, $/bbl and EUR/t | scraped from the page, the suffix is unstable | [prix des produits petroliers](https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers) | monthly, about six weeks after month end | **yes** | Licence Ouverte 2.0 |
| `dgec_brent_monthly` | Brent date monthly means as DGEC publishes them, $/bbl | same, scraped | same | monthly | **yes** | Licence Ouverte 2.0 |
| `dgec_note_printed_weekly` | the quotation table printed on page 3 of the weekly note, $/t | none, the PDFs are collected by hand | same | weekly, and **deleted** when the next note appears | **yes**, the parsed values only | Licence Ouverte 2.0 |
| `dgec_note_printed_monthly` | the monthly columns of the same page 3 table, $/t, with the ministry's provisional flag and every vintage of each month | none, the same PDFs | same | monthly, from the December 2025 layout onward only | **yes**, the parsed values only | Licence Ouverte 2.0 |
| `dgec_note_reconstructed_weekly` | the page 3 chart curves, decoded and calibrated, $/t | none | same | weekly | **yes** | Licence Ouverte 2.0, plus this study's own reconstruction |
| `dgec_note_reconstructed_cracks_weekly` | cracks computed from the row above, $/bbl | none, computed | same | weekly | **yes** | as above, plus derived by this study |
| `opec_rotterdam_products_monthly` | Rotterdam barge product prices, monthly, $/bbl | resolved per issue through the Wayback CDX index | [Monthly Oil Market Report](https://www.opec.org/monthly-oil-market-report.html) | monthly, around the middle of the month | **yes**, the parsed values only. The PDFs never | OPEC copyright, non commercial reuse |
| `fred_brent_daily` | Europe Brent spot, daily, $/bbl, the EIA series through FRED | [fredgraph.csv](https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU) | [DCOILBRENTEU](https://fred.stlouisfed.org/series/DCOILBRENTEU) | daily, a few days of lag | **yes**, with the doubt in section 4.1 | public domain, citation requested |
| `fred_eurusd_daily` | US dollars per euro, daily noon rate | [fredgraph.csv](https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXUSEU) | [DEXUSEU](https://fred.stlouisfed.org/series/DEXUSEU) | daily, a longer lag than Brent | **yes**, same doubt | public domain, citation requested |
| `eia_brent_daily` | the same Brent series taken straight from EIA | [RBRTEd.xls](https://www.eia.gov/dnav/pet/hist_xls/RBRTEd.xls) | [RBRTEd](https://www.eia.gov/dnav/pet/hist/RBRTEd.htm) | daily | **yes** | US public domain |
| `worldbank_gas_europe_monthly` | European gas, monthly, already in $/MMBtu, TTF from April 2015 | scraped, the document id in the path changes | [Commodity Markets](https://www.worldbank.org/en/research/commodity-markets) | monthly, early in the month | **yes** | CC BY 4.0 |
| `ttf_daily` | Dutch TTF front month, daily, EUR/MWh, optional overlay | yfinance, an unofficial client | [TTF=F](https://finance.yahoo.com/quote/TTF%3DF/) | daily | **NO**, `data/private/` | none found |
| `jodi_nwe_refinery_intake_monthly` | refinery crude intake and total feed, BE DE FR NL GB, kb/d | hrefs read off the downloads page | [JODI downloads](https://www.jodidata.org/oil/database/data-downloads.aspx) | monthly, around the 20th, 2.4 to 2.9 months of lag | **yes**, a filtered extract | no explicit licence |
| `jodi_nwe_refinery_output_monthly` | refinery gross output by product, same five countries | same | same | same | **yes** | no explicit licence |
| `jodi_nwe_crude_imports_monthly` | crude oil imports, same five countries | same | same | same | **yes** | no explicit licence |
| `ei_refinery_capacity_annual` | refinery capacity by country, annual, kb/d | [EI-Stats-Review-ALL-data.xlsx](https://www.energyinst.org/__data/assets/file/0008/1827620/EI-Stats-Review-ALL-data.xlsx) | [Statistical Review](https://www.energyinst.org/statistical-review/resources-and-data-downloads) | annual, June | **NO**, `data/private/` | EI copyright, reproduction not permitted |
| `eia_refinery_fuel_2023` | US refinery gas use and crude inputs, the gas intensity inputs | none, seeded by hand | [Refinery Capacity Report](https://www.eia.gov/petroleum/refinerycapacity/) | annual, June | **yes** | US public domain |
| `events` | dated events and structural breaks, one `source_url` each | none, written by hand | this repository | when something happens | **yes** | this study, MIT, the cited sources keep their own terms |
| `anchors` | the SPEC.md section 5.5 figures the pipeline must reproduce | none, written by hand | DGEC, as above | when the spec's anchors change | **yes** | Licence Ouverte 2.0 |
| `sp_global_reference` | five order of magnitude figures quoted from two S&P articles | none | [S&P, March 2022](https://www.spglobal.com/energy/en/news-research/latest-news/crude-oil/032822-refinery-margin-tracker-record-high-global-diesel-cracks-propel-margins-upward) | fixed, two dated articles | **yes**, five individual figures | S&P Global copyright |

---

## 2. Reuse terms, in each source's own words

### 2.1 DGEC, Licence Ouverte 2.0

Read at `https://www.ecologie.gouv.fr/mentions-legales`, section "Reutilisation
des contenus et liens", and at
`https://github.com/etalab/licence-ouverte/blob/master/LO.md`.

The ministry's own statement, verbatim:

> "Sauf mention explicite de propriete intellectuelle detenue par des tiers, les
> contenus de ce site sont proposes sous licence ouverte Etalab 2.0. Vous etes
> notamment libres de les reproduire, copier, modifier, extraire, transformer,
> communiquer diffuser, redistribuer, publier, transmettre et exploiter sous
> reserve de mentionner leur source, leur date de derniere mise a jour et ne pas
> induire en erreur des tiers quant aux informations qui y figurent."

The licence itself, verbatim:

> "Le Reutilisateur est libre de reutiliser l'Information : de la communiquer, la
> reproduire, la copier ; de l'adapter, la modifier, l'extraire et la
> transformer, notamment pour creer des Informations derivees ; de la diffuser,
> la redistribuer, la publier et la transmettre, de l'exploiter a titre
> commercial [...]"

> "Sous reserve de : mentionner la paternite de l'Information : sa source (a
> minima le nom du Concedant) et la date de la derniere mise a jour de
> l'Information reutilisee."

Accents are stripped in the two quotations above to keep this file in the ASCII
the repository uses everywhere else; the wording is otherwise untouched and the
URLs are there to check it against.

**Redistributable: yes**, including commercially, on condition of attribution and
a statement of the date of last update.

**Attribution this project uses:** DGEC, Direction generale de l'energie et du
climat, ministere de la Transition ecologique, with the URL and, as the date of
last update, the printed date of the note or the last month present in the
workbook.

**Mitigation applied anyway:** the parsed values are republished, the note PDFs
are not. See section 4.3 for why.

### 2.2 FRED, public domain with citation requested

Read at `https://fred.stlouisfed.org/legal`. Both series carry the schema.org
licence `https://fred.stlouisfed.org/legal/#copyright-public-domain` and the
keyword "public domain: citation requested", which is FRED's most permissive
tier. Verbatim:

> "These series may be under copyright or in the public domain and may be used
> without permission, provided you do not engage in any prohibited use. When
> using, please cite the data source and acknowledge that you obtained the data
> from FRED (example, "Source: BLS via FRED") when displaying or publishing it."

The suggested citation printed on the series page, verbatim:

> "U.S. Energy Information Administration, Crude Oil Prices: Brent - Europe
> [DCOILBRENTEU], retrieved from FRED, Federal Reserve Bank of St. Louis;
> https://fred.stlouisfed.org/series/DCOILBRENTEU"

**And, on the same page, under "II. Prohibited Use", applying to all use
including non commercial and educational, verbatim:**

> "Engage, or otherwise participate, in the use of any data mining, mirroring,
> robots, scraping, or similar data-gathering or extraction methods except as
> expressly allowed by the terms of use applicable to the FRED API."

That clause is a position the owner has to take, not a detail. Section 4.1.

### 2.3 EIA, US public domain

Read at `https://www.eia.gov/about/copyrights_reuse.php`. Verbatim:

> "U.S. government publications are in the public domain and are not subject to
> copyright protection. You may use and/or distribute any of our data, files,
> databases, reports, graphs, charts, and other information products that are on
> our website or that you receive through our email distribution service.
> However, if you use or reproduce any of our information products, you should
> use an acknowledgment, which includes the publication date, such as: "Source:
> U.S. Energy Information Administration (Oct 2008).""

**Redistributable: yes, freely, with an acknowledgment carrying the publication
date.** This is the only unambiguous grant in the project, which is why
`eia_brent_daily` exists alongside `fred_brent_daily` carrying the same numbers.

### 2.4 OPEC, non commercial reuse with acknowledgement

Read from the disclaimer page of the Monthly Oil Market Report itself, page 2 of
the September 2024 issue. Verbatim:

> "The data, analysis and any other information contained in the Monthly Oil
> Market Report (the "MOMR") and/or any of the material contained therein may be
> used and/or reproduced for educational and other non-commercial purposes
> without the OPEC Secretariat's prior written permission, provided that it is
> fully acknowledged as the copyright holder. [...] third party material's
> copyright must be acknowledged by obtaining necessary authorization from the
> copyright owner(s)."

**Redistributable: the parsed values, for non commercial purposes, with OPEC
acknowledged. The report itself, no.** So the 294 PDFs sit in `data/private/` and
only `data/cache/opec_rotterdam_products_monthly.csv` is committed.

**The table credits Argus.** The source line under it reads, verbatim,
`Sources: Argus and OPEC.` OPEC's own wording says third party copyright must be
acknowledged by obtaining authorisation from the owner. Section 4.2.

**Attribution this project uses:** "Argus, via the OPEC Monthly Oil Market
Report", on every chart drawn from this series.

### 2.5 World Bank, CC BY 4.0

Read at `https://data.worldbank.org/summary-terms-of-use` and at
`https://datacatalog.worldbank.org/public-licenses#cc-by`.

Summary terms of use, verbatim:

> "Unless indicated otherwise in the data or indicator metadata, you are free to
> copy, distribute, adapt, display or include the data in other products for
> commercial or noncommercial purposes at no cost under a Creative Commons
> Attribution 4.0 International License, with the additional terms below."

Data Access and Licensing, verbatim:

> "The World Bank Group makes data publicly available according to open data
> standards and licenses datasets under the Creative Commons Attribution 4.0
> International license (CC-BY 4.0)."

The "additional terms" in both places are a mandatory mediation and then UNCITRAL
arbitration clause for disputes, which is not a use restriction.

**Redistributable: yes, CC BY 4.0 with attribution.**

**Attribution this project uses:** "World Bank Commodity Price Data (The Pink
Sheet)". The Europe gas series is additionally credited in the workbook to
Bloomberg Finance L.P. and World Gas Intelligence, so the attribution is not
stripped and the series is never presented as this project's own assessment.

**One tension, recorded not resolved:** the general "Terms of use for Datasets"
page at `https://www.worldbank.org/en/about/legal/terms-of-use-for-datasets`
carries a narrower paragraph, verbatim: "For the remainder of the Materials, you
may make non-commercial uses thereof, but you may not make any derivative work or
commercial use ... without the prior written consent of the relevant member
institution(s)." That clause is scoped to material **not** covered by the open
data licence, and the pink sheet is linked from the Commodity Markets page under
the CC BY heading, so it is read as CC BY 4.0 here.

### 2.6 JODI, no data licence at all

Read at `https://www.jodidata.org/terms-of-use.aspx`. This is a website terms of
use, not a data licence. The only clause bearing on reuse, quoted in full:

> "**Intellectual Property**
> The Intellectual Property rights in the JODI Website, and in the material
> published on it, are protected by Intellectual Property laws and treaties
> around the world. All such rights are reserved."

Governing law is stated as "the law of the Kingdom of Saudi Arabia".

The downloads page says the data "can be downloaded, for free", which is a
statement about access rather than about republication. **There is no explicit
permission to redistribute and no open licence.**

**What this project does, and how weak it is.** It commits a small filtered
extract, five countries and a handful of flows and products, with clear
attribution, and it never mirrors the raw annual files, which are 933 MB across
50 files. That is normal practice among energy analysts and it is what every
public JODI chart does. It is **not** covered by a grant, and it is materially
weaker than FRED, EIA or the World Bank. Write to `JODIinfo@ief.org` before
Gate 5.

### 2.7 Energy Institute, reproduction not permitted

Read from the Statistical Review of World Energy 2026 itself. Verbatim:

> "Publishers are welcome to quote from this Review provided that they attribute
> the source to Energy Institute Statistical Review of World Energy 2026.
> However, for extensive reproduction of tables and/or charts, permission must
> first be obtained from: EI Statistical Review of World Energy, 61 New Cavendish
> Street, London W1G 7AR, statisticalreview@energyinst.org"

And, separately:

> "The redistribution or reproduction of data whose source is S&P Global Energy or
> S&P Global Inc, is strictly prohibited without its prior authorisation."

> "**Using S&P Global Energy data**
> The redistribution or reproduction of data whose sources is S&P Global Energy is
> strictly prohibited without prior authorisation from S&P Global.
> Email: ci.support@spglobal.com"

The capacity sheet itself is footnoted `Source: Includes data from ICIS and S&P
Global Energy`, and the footnote does not say which rows came from which
supplier, so the S&P part cannot be stripped out.

**Redistributable: no.** Committing the capacity table, even five country rows
for 61 years, is extensive reproduction of a table. The cache is therefore in
`data/private/`, it is not in the repository, and only the derived utilisation
ratio is intended for publication. Section 4.4.

Also worth knowing, verbatim: "Each year revisions are made to historical data
when updated or where more reliable data sources have become available." The
edition is a reproducibility hazard and is recorded in the manifest `vintage`.

### 2.8 Yahoo Finance, no grant

There is no public Yahoo Finance data licence. The applicable general clause is
section 2(e) of the Yahoo Terms of Service at
`https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html`, which says users must
not

> "reproduce, modify, rent, lease, sell, trade, distribute, transmit, broadcast,
> publicly perform, create derivative works based on, or exploit for any
> commercial purposes, any portion or use of, or access to, the Services".

`yfinance` is an unofficial client for an undocumented endpoint and carries no
redistribution grant of its own.

**Redistributable: no, or at best unclear.** The cache is in `data/private/` and
never leaves the owner's machine. **The site is complete without it**, because
the monthly gas series the analysis runs on is the World Bank pink sheet, which
is CC BY 4.0 and already in $/MMBtu.

### 2.9 S&P Global, ordinary quotation only

Five individual figures are quoted from two dated articles, with attribution and
a link, in `data/seed/anchors.json`. That is ordinary quotation. The underlying
assessments are S&P's and are **not redistributable as a series**: they are never
charted, never extended and never presented as comparable to anything this study
computes.

Both article URLs answer **HTTP 403 to automated access**, with a bot token user
agent and with a browser user agent, checked on 2026-09-13. The pages open in a
browser. The figures in the seed are therefore transcribed from SPEC.md sections
3, 4.4, 5.1 and 5.5, which quote the articles, and the file says so rather than
implying they were re read.

### 2.10 ICE, cited but never fetched

No ICE data is used. The two conversion factors come from published contract
specifications and two press releases date the two specification breaks. Recorded
because SPEC.md section 5.2 contemplates a daily futures layer and its terms
explain why that layer cannot be built from free sources. Verbatim, from the ICE
terms of use:

> "Copyright License. Under this Agreement, we hereby grant you a limited license
> to [...] and only if you do not remove, modify or obscure any copyright,
> trademark, or other [...] license does not include use of any data mining,
> robots or similar data gathering or extraction methods."

Personal, non commercial use only, robots excluded. SPEC.md section 5.2 is right
that the only lawful route is an export the owner makes himself into
`data/private/`.

---

## 3. Known traps, one row per source

These cost real time to find. Each is a fact measured on this machine, not a
guess.

### 3.1 DGEC

* **The ministry deletes each weekly note when the next appears.** There is no
  archive on the site and no URL pattern to walk backwards: before mid 2024 the
  note lived at one constant URL that was overwritten weekly. Ten survive, one
  live and nine from the Internet Archive. `python -m crack.sources.dgec_note
  --collect` must run **every week**. A week missed is gone.
* The SPEC.md section 5.6 URL
  `https://www.ecologie.gouv.fr/sites/default/files/documents/NPG-2026.08.28_0.pdf`
  **404s today**, for exactly that reason. It is not rot, it is the deletion.
* **The historical workbook hrefs carry an unstable numeric suffix** and the
  visible label and the href disagree about it, in both directions. Read the
  href off the landing page, never construct it. The `_1` URL returns 404.
* Both workbooks carry an **annual block below the monthly block, keyed by a text
  year**, so column A is not always a date.
* The filename date of a note does not reliably match the note's content date.
* The old `developpement-durable.gouv.fr` URL in SPEC.md section 5.6 is a 404.
  The live landing page is `ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers`.
* **Two different Brent factors**, 7.5 in the note and 7.55 in the margin
  methodology. See `docs/methodology.md` section 3.2.

### 3.2 FRED

* **FRED resets the connection on a browser user agent.** Same URL, same minute,
  only the header changed: `curl/8.x` gets 200, the project bot token gets 200,
  `python-requests` gets 200, `Mozilla/5.0` gets curl error 56, a full Chrome
  string times out. Observed twice on two days by two agents. This directly
  contradicts SPEC.md section 5.4's "a real user agent", and the contradiction is
  recorded in `docs/open-questions.md` rather than resolved silently.
* The header is `observation_date`, not `DATE`.
* **A day with no published price is an EMPTY field**, not the `.` older FRED
  downloads used. Accept both, map both to NaN, never to zero.
* **Brent and EUR/USD keep different holiday calendars**, a UK and European one
  against the US federal one. Join on the date, never zip by position.

### 3.3 EIA

* **Never probe `eia.gov` with HEAD.** It answers HTTP 503 to a HEAD and HTTP 200
  to a GET of the same URL, on navigator pages and on the archive directory
  index. A liveness probe with HEAD reports the source as down when it is up.
  `crack.sources.base.http_head` refuses the host outright.
* `RBRTEd.xls` is a legacy `.xls`, so it needs `xlrd` and not `openpyxl`, and its
  dates are Excel serials.
* **EIA omits a holiday entirely** rather than emitting a blank row, which is the
  one structural difference from the FRED copy of the same series.
* Tables 10a and 10b of the Refinery Capacity Report exist **only as a PDF**. The
  workbook that accompanies the report carries one sheet and it is the per
  refinery capacity file. There is nothing to parse, which is why those four
  figures are a seed.

### 3.4 OPEC

* **`opec.org` answers HTTP 403 to every scripted request from this machine.**
  Nothing is fetched from it. Issues resolve through the Internet Archive
  instead, and the index is discovered with a Wayback CDX query and never
  hardcoded.
* The 2004 to 2008 filenames carry extra suffixes and **one misspelling**,
  `momr-janaury-2008.pdf`.
* **April to September 2026 are not archived.** Six issues, by hand. It is
  recorded as a `manual_step` in the manifest.
* **The Rotterdam row labels change**: gasoil from `0.2% S` to `50 ppm` to
  `10 ppm`, gasoline from `unleaded` through three intermediate labels to
  `unleaded 98`. The cache carries the label per row so no chart has to guess,
  and each transition is an entry in `data/seed/events.json`.
* Each issue prints two or three months, so most months are printed by more than
  one issue. A gap between two issues that specified a row **differently** is a
  respecification, not a disagreement, and the two are carried in separate
  columns.

### 3.5 World Bank

* **The workbook URL contains a document id that changes**, and the old stable
  `pubdocs.worldbank.org` URL now 404s. Scrape the landing page for the filename
  and fail loudly if it is absent.
* **The Europe gas series is TTF only from April 2015.** Before that it is an
  import border price, and before June 2000 the workbook states no definition at
  all. Two labelled breaks, both in `data/seed/events.json`.
* Parse by matching the series name row text, never by column position. The pink
  sheet has added and removed series before.

### 3.6 JODI

* **The UK is `GB`.** The database has 118 `REF_AREA` values, `GB` is one of them
  and `UK` is not, so SPEC.md's spelling returns an empty series rather than an
  error.
* It is **not one CSV**: 50 annual files, 933 MB in total, and the **in progress
  year breaks the naming pattern**, `primaryyear2026.csv` rather than `2026.csv`.
  Read the hrefs off the downloads page or the adapter silently loses the latest
  year every January.
* **JODI revises history.** The 2002 file was rewritten in October 2025.
* The lag is **2.4 to 2.9 months**, not the two SPEC.md assumes.
* `TOTCRUDE`, `JETKERO` and `NAPHTHA` start only in 2009-01.
* `TOTPRODS` excludes `JETKERO`, and output over crude intake runs 1.13 to 1.16
  rather than 1, so the yield denominator is a real modelling choice.
* Carry the assessment code 1, 2 or 3 per cell. Code 2 appears only on 2026-06 in
  the current data, which confirms it is the provisional marker.

### 3.7 Energy Institute

* **`energyinst.org` now answers a Cloudflare bot challenge**, so the capacity
  series cannot be machine refreshed at all. The adapter parses a stored
  workbook and records when and where those bytes were obtained rather than
  stamping a fresh fetch time.
* The asset id in the download path is **edition specific** and will move with
  the 2027 edition.
* **No 2026 capacity exists anywhere yet.**

### 3.8 Yahoo

* `yfinance` returns an **empty frame intermittently**. Retry, then fail rather
  than caching an empty file.
* History starts 2017-10-23. Before 2018-03-14 the settlement is repeated into
  all four OHLC fields.
* Rolls are **unadjusted and undocumented**, and they are visible in the series.
* **Yahoo documents the unit nowhere.** EUR per MWh was established numerically,
  by reproducing the World Bank pink sheet series to a median of 0.02 percent
  over 106 months. That is a construction proof and is labelled as one.

---

## 4. Four positions that need the owner's decision

Each of these is a place where the honest reading of a clause is not the only
reading, or where a licence blocks something the spec assumes. None is decided
here. All four are also in `docs/open-questions.md` with more detail.

### 4.1 FRED's no mirroring clause against a committed cache

The clause is quoted in full in section 2.2. A scheduled job that fetches
`fredgraph.csv` and commits the result into a public repository is, on a strict
reading, both a robot and a mirror. The expressly allowed route is the FRED API,
which is free but needs a key, which would then live in a GitHub secret and would
break the "no key" simplicity SPEC.md section 5.1 assumes.

**The clean way out costs nothing.** Brent is already available from EIA
directly, under the only unambiguous grant in this project, and the committed
`eia_brent_daily` cache is **identical to `fred_brent_daily` to 0.0 maximum
absolute difference over all 9,973 rows**. EUR/USD could come from the Federal
Reserve Board's own H.10 rather than from FRED. Both underlying publishers are US
federal agencies and neither has a mirroring prohibition.

**The decision:** keep FRED as SPEC.md section 5.1 names it and cite both FRED
and the original agency, or move Brent to the EIA file and EUR/USD to H.10 and
drop FRED entirely. The data layer already supports the second choice.

### 4.2 OPEC's non commercial grant, and the Argus third party clause

OPEC's grant is for "educational and other non-commercial purposes". A public
portfolio repository with no advertising, no paywall and no product is
non commercial on any ordinary reading, and this project is one. But a portfolio
exists to get its author hired, which is a commercial purpose in the loosest
sense, and the loosest sense is the one a rights holder would argue.

Separately, the table credits Argus, and OPEC's own wording says third party
copyright "must be acknowledged by obtaining necessary authorization from the
copyright owner(s)". Read strictly, that asks this project to obtain
authorisation from Argus for a series it parsed out of an OPEC report.

**The decision:** rely on the ordinary reading, credit "Argus, via the OPEC
Monthly Oil Market Report" on every chart and offer no bulk download of the
product price series, or write to `dataqueries@opec.org` first.

### 4.3 DGEC's Reuters credit

Every DGEC price table carries `Source : DGEC-REUTERS`, and the methodology note
names Reuters as the source of the crude price, the product quotations, the gas
quotation and the freight cost. The underlying assessments are a commercial
vendor's.

Two facts sit against each other. The ministry's carve out is "Sauf mention
explicite de propriete intellectuelle detenue par des tiers", and a source credit
is not an explicit reservation of third party intellectual property; no Reuters
copyright statement appears anywhere in the note or on the page. And Licence
Ouverte 2.0 has the concedant warrant that the Information carries no third party
rights that would obstruct reuse.

On the face of the documents, reuse is permitted. **The mitigation already
applied** is to republish the parsed values with attribution and never the NPG
PDFs themselves, which is also why a fresh clone of this repository cannot
rebuild the weekly series from source.

**The decision:** accept the ordinary reading with that mitigation, or ask the
ministry.

### 4.4 The Energy Institute prohibition, which keeps capacity out of the repository

This is the one hard licence blocker. The clauses are in section 2.7 and they are
not ambiguous: extensive reproduction of a table needs written permission, and
the capacity sheet includes S&P Global sourced data whose redistribution is
"strictly prohibited".

It collides directly with SPEC.md section 5.4, "cache files are committed, so the
site builds and results reproduce with no network", and SPEC.md non negotiable 6,
"anything that cannot be redistributed stays in `data/private/`". The two rules
point in opposite directions and non negotiable 6 wins, so the capacity cache is
private and a fresh clone cannot compute utilisation.

Three options, and SPEC.md already wrote the third:

1. **Ask EI.** One email to `statisticalreview@energyinst.org` asking to publish
   five country rows in a non commercial public portfolio repository with
   attribution. The clean path. It takes days, not minutes.
2. **Publish only the ratio.** Keep capacity in `data/private/` and publish
   `utilisation = intake / capacity` and the regression outputs. A ratio of a
   JODI series to an EI series is arguably a derived output rather than a
   reproduction of a table. Weaker on reproducibility, honest about it, and the
   site keeps working. **This is what the code does today.** Note the honest
   objection recorded in open question 13: publishing the ratio next to the JODI
   numerator does not in fact withhold the denominator from anybody who can
   divide.
3. **Take SPEC.md section 6.1's own fallback**: "If the capacity table is
   unusable, use intake with a trend and closure dummies instead, and say so."
   That fallback was written for a usability failure and it applies just as well
   to a licence failure.

---

## 5. How to check any of this

```
python scripts/refresh.py --list        the jobs, the series each owns, and which are private
node tools/validate-data.mjs            proves nothing marked committable false is in the tree
```

The manifest at `data/manifest.json` carries `licence_note` and `committable` on
every entry, and the validator fails the build if a non committable file ever
appears in what git would commit. The words in this document are for a reader;
the boolean in the manifest is what the code acts on; and the validator is what
makes sure the two agree.
