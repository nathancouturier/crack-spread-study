# Methodology

What this study computes, from what, and how far each number can be trusted.
Every figure below is a measurement made in this repository and reproducible from
it. Where a number is an expectation rather than a measurement, it says so.

---

## 1. The weekly crack layer, and the reconstruction it rests on

### 1.1 The problem

The site is named after cracks. A crack is a product price minus a crude price,
and there is no free, redistributable, weekly Northwest European product price
series published anywhere. Recon 05 probed Yahoo, stooq, the EU Weekly Oil
Bulletin, Eurostat, the Italian, German, Dutch and Belgian administrations, the
World Bank pink sheet, the IMF PCPS, the EIA and FRED. The complete result:

* Yahoo has no ICE Low Sulphur Gasoil and no Eurobob price in any spelling.
* stooq's robots.txt disallows every agent except Bingbot and Googlebot and its
  CSV endpoint now serves a proof of work bot check. Not used, on terms.
* The World Bank pink sheet carries no refined product at all, for Europe or
  anywhere.
* The IMF PCPS carries two refined products, both quoted in US cents per gallon.
* The EU Weekly Oil Bulletin is real, weekly, back to 2005 and CC BY 4.0, and it
  is a PUMP price. It is a refining plus distribution plus retail margin and it
  never enters a crack in this study.
* The OPEC Monthly Oil Market Report carries exactly the right thing, Rotterdam
  barges in dollars per barrel back to October 2000, and it is MONTHLY.

That leaves one weekly source: the DGEC weekly note.

### 1.2 What the ministry publishes, and what it deletes

DGEC publishes one "Note de conjoncture petroliere" at a time and deletes the
previous one. Page 3 of each note carries:

* a TABLE printing two weekly averages, and since December 2025 two monthly
  averages, for Eurosuper, Gazole, Fioul domestique, Jet, Fioul lourd TBTS and
  Brent date, in dollars per tonne;
* a CHART, drawn as vector polylines, of four of those six series over the
  preceding 105 weeks.

Ten notes survive: one live and nine from the Internet Archive. Recon 02 section
2.5 established there is no archive to crawl and no URL pattern to walk
backwards, because before mid 2024 the note lived at a single constant URL that
was overwritten every week.

So the printed tables across all ten notes amount to **18 distinct weekly
observations**, and the charts in the same ten documents are the ministry's own
record of **219**.

### 1.3 Four series, never merged

| Series | Method | Rows | Span | What it is |
|---|---|---|---|---|
| `dgec_note_printed_weekly` | `parsed` | 18 | 2024-06-21 to 2026-09-04 | the weekly figures DGEC set in type, read by row and column label |
| `dgec_note_printed_monthly` | `parsed` | 7 | 2025-11-01 to 2026-09-01 | the monthly columns of the same table, with the ministry's own provisional flag and every vintage of every month |
| `dgec_note_reconstructed_weekly` | `reconstructed` | 219 | 2022-07-01 to 2026-09-04 | the page 3 curves, decoded and calibrated against the printed figures on the same page |
| `dgec_note_reconstructed_cracks_weekly` | `derived` | 219 | 2022-07-01 to 2026-09-04 | cracks computed from the row above |

They are separate caches with separate manifest entries and different `method`
values. A reconstructed value is never written into a printed series, and no row
of either carries a value that came from the other.

**`dgec_note_printed_monthly` is new since the Gate 1 self audit** and exists
because of finding 1.1: the decoder had been reading the monthly columns and
their `(donnees provisoires)` markers correctly on every run and then discarding
them. SPEC.md non negotiable 5 says "Provisional is labelled provisional. The
current month in the ministry notes is provisional and gets revised. Keep every
vintage, show the flag", and this is the series that keeps that promise.

Each row carries the latest print of that month, a `provisional` flag, the
`vintage` of the note it was read from, the `first_vintage`, `n_prints`,
`revised`, `max_revision_usd_t` and a `revision_history` field holding every
earlier print with its own flag and all seven values. Two things in the corpus
justify the history field on their own:

* **March 2026 went provisional to final and moved while doing it.** 946 $/t
  Eurosuper on 20 March, 976 on 27 March, then 988 **final** on 3 April and
  unchanged on 24 April. Largest move of the six $/t columns: 56 $/t on Gazole.
* **April 2026 moved 180 $/t between two prints that were both provisional.**
  Jet 1,733 on 3 April, 1,553 on 24 April; Gazole 1,431 to 1,288.

`max_revision_usd_t` is empty, not zero, for a month printed only once, for the
same reason the spread columns are. It is also the only monthly home of Jet and
Fioul lourd TBTS **as DGEC $/t quotations**: the OPEC MOMR carries Argus jet and
1 percent fuel oil rows for the same hub in $/bbl on a different specification,
and JODI carries jetkero volumes, which are neighbours rather than substitutes.

### 1.4 How the chart is decoded

1. **Find the page by its title**, never by its index. The table is on page 3 in
   nine notes and page 4 in one, and the title wording itself changed between
   2024 and 2026.
2. **Take the four polylines** of equal length. The page also carries a fifth,
   shorter polyline, the monthly MBR chart, which is dropped and is redundant
   anyway because DGEC publishes the MBR as a workbook.
3. **Fit the value axis** by least squares on the y tick labels, using each
   label's glyph box centre. Worst single tick residual across the ten notes:
   0.588 $/t. That figure bounds axis nonlinearity and label centring error over
   the full height of the chart.
4. **Read the series identities off the legend**, matching each swatch's stroke
   colour to the text beside it, per note. Never from a colour constant: two of
   the ten notes round the same colour differently, `(1.0, 0.6, 0.0)` against
   `(1.0, 0.599609, 0.0)`.
5. **Date the points from the x axis labels.** The spacing is measured, not
   assumed: the point pitch divided by the label pitch implies 0.9986 to 1.0009
   weeks per point across the ten notes. The last point carries the last label's
   date, and that date is checked against the note's own latest printed weekly
   column.
6. **Fit one additive offset per note** on that note's eight printed anchors,
   four plotted products times the two printed weeks. The offset corrects the
   systematic difference between a digit's glyph box centre and its visual
   centre. It runs **-2.38 to +2.82 $/t across the ten notes and changes sign**,
   so it can never be a constant.
7. **Stitch** by taking the median across every note covering a week.

### 1.5 What it costs, measured

Two independent measurements. Read the first one's heading before its number.

**Leave one series out.** Fit the offset on three products' six anchors, predict
the held out product's two, rotate through all four, in all ten notes.

| | $/t |
|---|---|
| Mean absolute error, per note | **0.17 to 0.44** |
| Worst single anchor | **0.87** |

On gasoil at 7.45 barrels per tonne that is 0.02 to 0.06 $/bbl mean and 0.12
$/bbl worst, against cracks that run from 10 to 80 $/bbl in this sample.

**WHAT THAT FIGURE DOES NOT BOUND, AND IT IS MOST OF THE SERIES.** The 0.17 to
0.44 $/t error is a **leave one series out** figure. The offset is fitted on
three products' anchors and used to predict the fourth's, and **all eight
anchors of every note sit on the last two weeks of a 105 week chart**. So it is
**out of sample across products and in sample across time**, and it **does not
bound the other 103 weeks**. Anyone quoting 0.17 to 0.44 next to a week in the
middle of the series is quoting a number measured somewhere else.

The figure that does speak to time is the note pair overlap below, 0.30 $/t mean
absolute and 1.68 $/t worst single week, and that is the one to put next to the
series. This was the Gate 1 self audit's first "quietly unsure" item and it was
right: "out of sample" reads as "out of sample in time" and it is not.

**Agreement between overlapping notes.** 168 note pair by product comparisons,
every pair with at least five common weeks. This is the test that probes the LEFT
hand end of a chart, where no anchor sits, because the left end of a recent note
is the right end of an older one.

| | $/t |
|---|---|
| Mean of the per pair mean absolute differences | **0.30** |
| Worst single week across all 168 comparisons | **1.68**, on Brent |

Per week, the spread between the highest and lowest note is a column in the
cache, `spread_<product>_usd_t`, so the figure travels with every row rather than
living in this document alone. Where a week has only one geometry that column is
**NaN, an empty cell, not zero**: a spread over one reading is undefined, and a
zero there would state that two notes agreed when there was never a second note.
Anything rendering the column must print the empty cell as "no cross check".

### 1.6 Where it is weakest, stated rather than buried

**Twenty five of the 219 weeks have no cross check at all.** They are the six
oldest, 2022-07-01 to 2022-08-05, and the nineteen newest, 2026-05-01 to
2026-09-04. On those weeks the spread columns are empty rather than zero, the
`cross_checked` column is `false`, and `evidence_class` says which kind of
uncorroborated week it is. Nineteen of the twenty five are at the RECENT end,
which is the end a reader looks at first.

*(Recon 05 section 12 describes this split as "the 20 oldest and the 5 newest".
The count of twenty five is right and the split is not; recon 05's own
demonstration output disagrees with its own sentence. The corrected split is
above and is asserted in `tests/test_sources_dgec_note.py`.)*

**THE SIX OLDEST WEEKS ARE THE LEAST DEFENDED DATA IN THIS PROJECT, and they are
flagged as such in the data.** 2022-07-01 to 2022-08-05 carry two weaknesses at
once: they are covered by exactly one chart geometry, so nothing can contradict
them, **and** they sit at the far left of that one note's chart, 105 weeks from
its nearest calibration anchor, where the only evidence about the fit is the tick
residual. Every other uncorroborated week has at most one of the two problems:
the nineteen newest are uncorroborated but sit **on** the anchored end.

`evidence_class` carries this per row, with values `cross_checked` (194 weeks),
`single_geometry_newest` (19) and `single_geometry_oldest` (6), and it travels
into `dgec_note_reconstructed_cracks_weekly` as well, so the crack a reader plots
carries the flag rather than needing a join to find it. The Gate 1 self audit's
point was that a compounding weakness described only in prose is a weakness
nobody meets; this is the answer to it.

**The gates cannot see a smooth distortion anchored at the right hand end.** The
calibration fits one additive offset per note on eight anchors, and all eight sit
on the last two weeks. So any error that is small at the right and grows toward
the left is invisible to every gate in 1.7. The Gate 1 self audit measured it by
tilting a real note's chart, leaving the right end untouched:

| left end bent by | worst anchor residual, limit 1.50 | oldest week moved | newest week moved |
|---|---|---|---|
| 1 point | 0.391 | 7.35 $/t | 0.04 $/t |
| 3 points | 0.462 | 22.05 $/t | 0.11 $/t |
| 10 points | **0.711** | **73.49 $/t** | 0.35 $/t |

A distortion moving the oldest week by 73 $/t, about 10 $/bbl on the gasoil
crack, passes with the headline gate reading 0.711 of its 1.50 limit. A pure
translation, by contrast, is absorbed exactly and moves nothing, which is correct
behaviour. What defends the series against the tilt is not the gates, it is the
overlap between notes, because a given week sits at a different horizontal
position in each note that plots it, and 194 of 219 weeks have two or more
independent geometries. **The 25 that do not have no defence against it, and the
six marked `single_geometry_oldest` sit exactly where such a distortion would be
largest.**

**Pixel quantisation is invisible in the file.** A decoded value is the
calibrated height of a point on a vector curve, but the curve was drawn from
rounded data onto a finite grid, so two different weekly prices can land on the
same height. Eurosuper reads exactly **719.1192666134755 on 2024-09-20,
2024-09-27 and 2024-11-01**. Those are almost certainly not three weeks at an
identical price to thirteen decimal places, and nothing in the file distinguishes
a genuinely flat week from a quantisation collision. No single case can be proved
either way without the underlying prices, which is the whole problem. Treat an
exact repeat of a reconstructed value at adjacent weeks as "indistinguishable at
the resolution of the chart", never as "the price did not move". The printed
table is the only cure and it covers 18 weeks.

**One note pair proves nothing.** `wb_NPG-2026.04.03` and `NPG-2026.09.04` draw
the same 400 to 1500 axis over 12 ticks at the same 4.3212 point pitch, so an
identical value lands on an identical pixel and the two decodes CANNOT disagree:
their standard deviation over 83 common weeks is exactly zero and their
difference a constant 0.18 $/t. That is determinism, not accuracy. The
`n_independent_geometries` column counts distinct chart geometries rather than
notes, so this pair contributes one piece of evidence to a week instead of two,
and `cross_checked` is driven by that column.

**Brent is the least accurate of the four.** It is the lowest line on a chart
scaled for the product lines, so the same pixel error is a larger relative error,
and on some notes it runs close to the bottom axis. The worst single week
disagreement in the whole overlap test is on Brent. Where a Brent figure matters,
`dgec_brent_monthly` is DGEC's own published workbook and should be preferred.

**Jet and Fioul lourd have no weekly series and will not get one.** They are not
plotted on the chart. They exist in `dgec_note_printed_weekly`, 18 and 16
observations respectively, and in `dgec_note_printed_monthly`, 7 months, and
nowhere else as DGEC quotations. Reconstructing them by regression on the three
products that are plotted would be a synthetic series, which SPEC.md section 2
rule 1 forbids outright.

**One note prints no Fioul lourd row at all.** `wb_NPG-2025.01.17` prints
Eurosuper, Gazole, Fioul domestique, Jet and Brent date and nothing else. Parsing
by label found the absence; parsing by position would have read Jet's numbers
into the fioul lourd column.

### 1.7 What happens when it goes wrong

Every one of the following makes the note contribute NOTHING. There is no
fallback, no partial decode, no borrowed calibration and no guess.

| Gate | Limit | Worst observed |
|---|---|---|
| polylines of equal length | exactly 4, at least 50 points | 4 of 105, all ten notes |
| y axis tick labels parsed | at least 4 | 7 |
| value axis fit against its own ticks | 2.0 $/t | 0.588 |
| printed anchors available | exactly 8 | 8, all ten notes |
| worst anchor after the per note offset | **1.5 $/t** | 0.738 |
| implied weeks per point | 0.98 to 1.02 | 0.9986 to 1.0009 |
| chart's last x label against the printed latest week | must be equal | equal, all ten |

A note tripping any gate raises, so `Adapter.run` keeps the previous cache
untouched, writes a manifest entry with `status: failed` carrying the reason, and
exits non zero. All ten notes pass today, which is why a failure is treated as a
layout change worth stopping for rather than as a note to drop quietly.

### 1.8 The cracks

```
crack_gasoil(t)   = gazole_usd_t(t)    / 7.45 - brent_date_usd_t(t) / 7.5
crack_gasoline(t) = eurosuper_usd_t(t) / 8.33 - brent_date_usd_t(t) / 7.5
```

Both legs come from the same chart, on the same page, of the same note, so they
share a date and an averaging window by construction. SPEC.md section 4.2
requires that and a weekly product against a monthly crude would break it.

7.45 and 8.33 are the ICE Low Sulphur Gasoil and Eurobob crack contract
divisors. 7.5 is DGEC's own Brent factor, recovered by recon 02 section 4.3 from
five month pairs against DGEC's published Brent workbook, exactly 7.5 each time,
and re-checked here against every non provisional monthly Brent column in the
corpus. The OTHER DGEC factor, 7.55, belongs to the CAF Brent inside the MBR
calculation; using it here would be a silent 0.67 percent error on the crude leg.

**The products are not the futures they are divided by.** Gazole is road diesel
quoted in Rotterdam and Eurosuper is finished premium gasoline, not Eurobob
blendstock. The divisors are contract conventions and the crack is quoted on that
convention.

### 1.9 Two external cross checks

**Against the OPEC monthly Rotterdam table**, 44 months, 2022-07 to 2026-02. A
French ministry chart decoded from vector curves against an Argus assessed table
printed in an OPEC PDF. Both cracks taken against the same Brent leg, so what is
measured is the product leg alone.

| Crack | Mean difference | Mean absolute | Range |
|---|---|---|---|
| Gasoil | **+1.10** $/bbl | 1.58 | -2.45 to +5.99 |
| Gasoline | **-8.82** $/bbl | 8.82 | -21.97 to +0.07 |

The gasoil agreement is the single best evidence that the reconstruction is real
rather than plausible: two entirely independent sources, one of them a decoded
picture, landing within about 1.6 $/bbl of each other on a quantity that ranges
over 70 $/bbl.

**The gasoline gap is not solved and is not going to be papered over.** Two
causes sit behind it and this project can separate neither. The implied barrels
per tonne between the two sources runs 7.42 to 8.15 across the months where both
exist, never the contract's 8.33; and the two sources quote different products,
DGEC's Eurosuper being finished premium gasoline while the MOMR row is premium
unleaded 98 as assessed by Argus. Picking a conversion factor that closed a
13 $/bbl gap between two differently defined products would be exactly the tuning
SPEC.md section 6.6 forbids. Both series are carried under their own labels and
the gap is shown.

**Against October 2022**, the crisis SPEC.md section 3 names, at weekly
resolution:

| Week ending | Gasoil crack, $/bbl |
|---|---|
| 2022-10-07 | 51.00 |
| 2022-10-14 | 62.01 |
| 2022-10-21 | **82.06** |
| 2022-10-28 | 74.37 |
| October mean | 67.36 |
| OPEC monthly, same month, same Brent leg | 69.50 |

The week ending 21 October straddles 13 October, the day S&P Global reported ARA
diesel cracks near 80 $/bbl. The reconstruction puts that week at 82, from a
French ministry chart, with no knowledge of the S&P figure. That is an
independent reproduction of a published number, and it is an order of magnitude
check, never a target: SPEC.md section 6.6 forbids tuning toward it.

### 1.10 Why not just use the numbers the ministry printed

Because the ministry prints two weeks and deletes last week's note, so the
printed numbers amount to eighteen observations, and the chart in the same
document is the ministry's own record of 105 more. Decoding it is a documented
extraction from a published source, the same category of act as parsing a table
out of a PDF, only harder. Every value is a measurement of a curve DGEC drew from
its own data. Nothing is interpolated between observations, nothing is modelled,
nothing is borrowed from a neighbouring source.

Stated the other way round, as "we estimated prices from a picture", it would be
a liability. Stated accurately, with the error measured and printed next to it,
it is the reason this study has a weekly crack at all.

### 1.11 Provenance and collection

The ten note PDFs are preserved under `data/private/dgec_notes/`. They are NOT
committed, because they are the ministry's own documents and the Licence Ouverte
mitigation recorded in `config.SOURCES` is to republish the parsed values rather
than the PDFs. They are irreplaceable.

On 2026-09-13 the live `NPG-2026.09.04.pdf` was re-fetched and found byte for
byte identical to the preserved copy, sha256
`a364a4fae11c95e9173f3314f2932077f67949cd9d8c3d05b8f8d29c042c13b9`, 2,406,779
bytes, which is the size recon 02 section 2.2 recorded.

`python -m crack.sources.dgec_note --collect` fetches the one note that is online
and adds it to the corpus if it is not already there, reading the href off the
landing page and never constructing it from a date. It never overwrites a file
already held. **Run it weekly.** Every week it is not run is a week that is gone:
the note is deleted when the next one appears and the Internet Archive is not
picking them up.

---

## 2. Definitions

These are SPEC.md section 4 written out, with the units stated, because every
argument later in this document is an argument about one of them.

### 2.1 A crack

```
crack_gasoil(t)   = p_gasoil_usd_t(t)   / BBL_PER_T_GASOIL   - brent_usd_bbl(t)
crack_gasoline(t) = p_gasoline_usd_t(t) / BBL_PER_T_GASOLINE - brent_usd_bbl(t)
```

A product price minus the crude price, per barrel. Two rules travel with it and
neither is optional.

**Both legs share the same date and the same averaging window.** Weekly with
weekly, monthly with monthly, never a weekly product against a monthly crude.
In `dgec_note_reconstructed_cracks_weekly` both legs come off the same chart on
the same page of the same note, so they cannot be misaligned. In the OPEC layer
both legs are monthly means over the same calendar month.

**Product definitions follow the source's own labels.** In the DGEC data
"Gazole" is road diesel quoted in Rotterdam and "Eurosuper" is finished premium
gasoline, not Eurobob blendstock. In the OPEC data the rows are "Gasoil/Diesel
(10 ppm)" and "Premium gasoline (unleaded 98)" assessed by Argus. They are not
relabelled as futures anywhere, and the difference between them is the subject of
open question 23.

### 2.2 The margin, in four layers

SPEC.md section 4.3 asks for four, and Gate 1 delivers the data for all four and
computes none of them. What exists today is the input, and what each layer will
need is stated so the gap is visible:

| Layer | What it is | State at Gate 1 |
|---|---|---|
| 1, official margin | DGEC's own published MBR on Brent, monthly, $/bbl | **built.** `dgec_mbr_monthly`, 140 months, all nine SPEC.md section 5.5 anchors reproduce exactly |
| 2, replication | recompute the MBR from DGEC's published quotations | **cannot be completed, and the reason is published.** Five of the ten quotations the methodology note names are never published: EuroBOB, essence export, naphta, propane and butane, plus the PEG Nord gas price and the Aframax freight. SPEC.md section 4.3 says to name the missing input and fall back to the official series, which is what happens |
| 3, decomposition | `yield[p] * crack[p]` per product, with a residual line | the yields are in the methodology note and are recorded in `config`; the arithmetic is Gate 2. **Two Brents meet on this line**, see below |
| 4, observed yields | NWE yields from JODI output over intake | the three JODI caches are built; the ratio is Gate 2 |

**Layer 3 attributes a DGEC margin with cracks taken against a different Brent,
and the difference lands on the residual.** DGEC computed the MBR against its own
published monthly Brent date. The cracks come from the OPEC Rotterdam table
against the FRED DCOILBRENTEU monthly mean, because FRED is the only crude series
that spans the whole product table back to 2000. Both legs of every crack share a
date and an averaging window, so SPEC.md section 4.2 is satisfied, but the margin
and the cracks do not share a crude assessment. Measured over the 140 months
where both exist: the mean gap between the two Brents is 0.003 $/bbl, the worst
is 0.2649 $/bbl in August 2016, and at the 0.4679 volume yield the decomposition
covers, the worst effect on the attributed total is 0.1239 $/bbl and the mean
0.0014. It is small, it is silent, and it is said here rather than nowhere.
`series.brent_monthly("dgec")` is the other choice and taking it would shorten
the crack series to 2015.

### 2.3 Run economics

```
gas_usd_mmbtu    = ttf_eur_mwh * eurusd / MMBTU_PER_MWH
gas_cost         = gas_intensity_mmbtu_per_bbl * gas_usd_mmbtu
margin_after_gas = margin_gross - gas_cost - other_variable_cost
headroom         = margin_after_gas - run_cut_threshold
```

**That subtraction applies to a margin this study builds itself, and NOT to
DGEC's published MBR. The MBR is already net of purchased natural gas.** The
Gate 2 self audit, finding 1, found the monthly series applying it anyway and
charging the same barrel for gas twice. The evidence that the MBR is net of gas
is the note's own: section 3 takes off the revenues "les couts d'achat du Brent
date FAB et du gaz naturel CAF", table 1 carries "Gaz naturel 1,0%" as an INPUT
line, the note says the refinery buys gas for its internal fuel and its hydrogen
needs, it describes the figure as gross only of costs "autres que ceux
energetiques", and the indicator is named a margin "sur couts energetiques".

What the error was worth, measured on the committed caches:

| Month | Published MBR, and margin after gas | What the double charge printed | Overcharged by |
|---|---|---|---|
| 2026-08 | 38.05 $/bbl | 33.57 | 4.48 |
| 2022-10 | 24.78 $/bbl | 16.50 | 8.28 |
| 2022-08 | 11.17 $/bbl | **minus 3.69** | 14.86 |

Worst 14.86 $/bbl, mean 2.47 $/bbl over 140 months. August 2022, in the most
profitable stretch European refining has had in modern history, read as a loss.

Two things changed, and the second is the one that matters:

1. `crack.series.margin_after_gas_monthly` subtracts no gas. With
   `other_variable_cost` at its default of zero, the margin after gas IS the
   published margin, bit for bit, and a test asserts that equality on every
   month rather than to a tolerance.
2. A margin now carries its basis. `engine.MARGIN_NET_OF_GAS` says the gas
   purchase is already inside it, and `engine.MarginInputs` raises
   `GasDoubleCountError` for any non zero gas term on such a margin, in both
   engines. The mistake is no longer expressible rather than merely fixed.

**The gas story survives and is better told as a wedge.** Instead of a
deduction, the two intensities are priced at the same gas price and shown side
by side: DGEC's own embedded assumption, 1.0 percent of the tonne of crude at the
method's own 7.55 bbl/t, which is 0.0659 MMBtu/bbl, against this study's EIA
derived 0.21217, which is 3.22 times as much.

```
2026-08   gas 21.11 $/MMBtu   DGEC embedded 1.391   this study 4.479   wedge 3.088
2022-08   gas 70.04 $/MMBtu   DGEC embedded 4.616   this study 14.860  wedge 10.245
```

A positive wedge means a refinery buying gas at this study's intensity pays more
for it than DGEC's model refinery does, so the published margin flatters such a
refinery by the wedge. It is a comparison, never a line of the margin, and
nothing in the engine subtracts it.

One change to that chain has already been earned by the data and is recorded
here rather than left to be discovered. **The monthly gas series this study runs
on needs no conversion at all.** The World Bank pink sheet publishes "Natural
gas, Europe" already in $/MMBtu and, from April 2015, it is TTF by the
publisher's own definition. So for every month from 2015-04 the analysis reads
`gas_usd_mmbtu` directly, with no FX and no 3.412142, and the first line of the
chain above is used only on the optional daily TTF overlay. Two independent
computations of October 2022 agree to 0.26 percent: the pink sheet prints 39.02
$/MMBtu, and the TTF chain gives 135.48 EUR/MWh times 0.9853 divided by 3.412142,
which is 39.12.

`other_variable_cost` defaults to zero and is labelled. Carbon costs are out of
scope for this version and are a stated limitation, not folded silently into that
line.

---

## 3. Conversion factors, and why there are two for DGEC's Brent

Every constant, its source and what it may be used for sit in
`src/crack/config.py` next to the number itself. This section is about the four
that decide a crack.

### 3.1 The two contract factors

| Constant | Value | What it is | Source |
|---|---|---|---|
| `BBL_PER_T_GASOIL` | 7.45 | the divisor in the ICE Low Sulphur Gasoil vs Brent crack contract | ICE contract specification, `https://www.ice.com/products/6753331` |
| `BBL_PER_T_GASOLINE` | 8.33 | the divisor in the ICE Eurobob vs Brent crack contract | ICE contract specification, `https://www.ice.com/products/6753285` |

**They are conventions, not densities.** A tonne of any particular gasoil cargo
is not exactly 7.45 barrels. These are the numbers the crack contracts divide by,
so they are the numbers a crack quoted on that convention has to use, and every
crack this study prints is labelled as being on it.

7.45 survives an independent check. DGEC Gazole against the OPEC Rotterdam gasoil
row implies a mean of 7.528 barrels per tonne over the 44 months both cover,
which is a density of 0.836 against 7.45's 0.845, and both sit inside EN 590.

8.33 does not survive the same check, and it stays anyway. DGEC Eurosuper against
the OPEC premium gasoline 98 row implies a mean of **7.719** over the same 44
months, ranging 6.94 to 8.33, so 8.33 sits at the very top of the observed spread
rather than in the middle of it, where 7.45 sits for gasoil. The two sides
are different products, RON 95 finished gasoline against premium unleaded 98, so
the measurement mixes a conversion factor with an octane spread and cannot by
itself condemn 8.33. Picking a factor to close a 13 $/bbl gap between two
differently defined products is the tuning SPEC.md section 6.6 forbids. The gap
is published instead. Open question 12 and open question 23.

`MMBTU_PER_MWH = 3.412142` is a unit definition, not a measurement: 1 MWh is
3.6e9 J and 1 MMBtu(IT) is 1.05505585262e9 J, so the exact ratio is 3.41214163
and SPEC.md section 4.1 fixes the seven figure rounding.

### 3.2 The two DGEC Brent factors, and the 0.56 $/bbl error of using the wrong one

DGEC uses **two different** barrels per tonne figures for Brent, in two different
places, and neither is 7.45. Using one where the other belongs is a 0.67 percent
error on the crude leg, about 0.56 $/bbl at a Brent of 84, and it would be
silent.

| Constant | Value | Where DGEC uses it | Use it for |
|---|---|---|---|
| `DGEC_BBL_PER_T_BRENT_NOTE` | 7.5 | printing Brent date in the $/t quotation table on page 3 of the weekly note | converting that column back to $/bbl, which is what a crack needs when its product leg comes from the same table |
| `DGEC_BBL_PER_T_BRENT_MARGIN` | 7.55 | the CAF Brent price inside the MBR calculation | a replication of the MBR, and nothing else |

7.55 is **stated**, verbatim on page 4 of the methodology note: "Le prix du Brent
$/bbl (CAF) est calcule sur la base d'une equivalence de 7,55 bbl/t."

7.5 is **measured**, because the note never states it. Recon 02 section 4.3
recovered it by dividing the note's PRINTED $/t figure by the $/bbl figure DGEC
publishes for the same month in its own Brent workbook, on the five month pairs
where both a surviving note and the workbook cover the same month, and got 7.5
exactly on each of the five. Recon 04 section 7.4 reproduced it from a different
direction: the July 2026 anchor of 628 $/t divided by the FRED monthly mean of
83.7587 $/bbl is 7.4977.

**The committed cache is not evidence for it.** `dgec_brent_monthly.brent_usd_t`
is DERIVED from the published $/bbl at 7.5, so dividing one by the other in that
file returns 7.5 by construction and proves nothing. The claim rests on the five
printed month pairs and on the FRED cross check, and 628 is printed to the whole
dollar, so the measurement carries a small doubt that is stated rather than
rounded away.

The two constants are not allowed to become equal. `config.py` raises at import
time if they ever do, because collapsing them into one is exactly the error the
pair exists to prevent.

---

## 4. The gas intensity, derived rather than typed

SPEC.md section 4.4 says "gas intensity is derived, not typed". It is. The four
inputs are seeded by hand in `data/seed/eia_refinery_fuel_2023.json`, each with
the table it was read from, and `crack.sources.eia.gas_intensity_from_seed`
recomputes the intensity from them every time it is asked. The constant in
`config.py` is asserted against that recomputation by a test, so editing one
without the other fails the build.

The four inputs, all EIA, all United States, all 2023:

| Input | Value | Source |
|---|---|---|
| natural gas consumed as fuel at refineries | 1,021,246 MMcf | Refinery Capacity Report, table 10a |
| natural gas used as hydrogen feedstock | 172,313 MMcf | Refinery Capacity Report, table 10b |
| heat content of natural gas consumed | 1,036 Btu/cf | Natural Gas Navigator, `NG_CONS_HEAT_A_EPG0_VGTH_BTUCF_A` |
| refinery and blender net input of crude oil | 5,827,889 thousand bbl | Petroleum and Other Liquids, `MCRRIUS1` |

One pass, nothing chosen to land anywhere:

```
(1,021,246 + 172,313) MMcf            = 1,193,559 MMcf
x 1e6 cubic feet per MMcf             = 1.193559e12 cf
x 1,036 Btu per cubic foot            = 1.236527124e15 Btu
/ 1e6 Btu per MMBtu                   = 1,236,527,124 MMBtu
/ (5,827,889 x 1e3) barrels           = 0.2121741 MMBtu per barrel
```

SPEC.md section 4.4 expects about 0.2 and says to stop and show the working
outside 0.12 to 0.30. **0.21217 is inside**, so there is no stop condition and
nothing to tune.

Two sensitivities are carried in the seed and neither is used. Dropping the
hydrogen feedstock gas gives 0.1815, about 15 percent lower; SPEC.md section 4.4
says to include it and that is right, because a European refiner buys that gas
too. Switching the denominator to gross input to atmospheric distillation units
gives 0.2053, about 3 percent lower.

**It is a US figure and therefore an upper end default for Europe.** European
refiners burn proportionally more of their own still gas and buy proportionally
less pipeline gas, so a European refinery's purchased gas intensity is more
likely below this than above it. The Model view will make it editable and label
it as an upper end default.

### 4.1 The triangulation SPEC.md section 4.4 asks for

Compute the October 2022 gas cost against a refinery fired on fuel oil, and
report it next to S&P Global's about 7 $/bbl. Reported whatever it came out at:

```
gas fired      0.21217 x 39.02 $/MMBtu                  = 8.279 $/bbl
fuel oil fired 0.21217 x (60.75 $/bbl / 6.287 MMBtu/bbl) = 2.050 $/bbl
difference                                               = 6.23 $/bbl
```

against S&P's about 7 $/bbl. Four independent committed sources, nothing tuned,
same order of magnitude. The residual fuel oil heat content of 6.287 MMBtu per
barrel comes from the EIA Monthly Energy Review table A1 and is used for this
triangulation and nothing else; no part of the margin engine reads it.

**Which fuel oil, and why it is a question.** The OPEC Rotterdam table publishes
two fuel oil rows and in October 2022 they were 21 $/bbl apart: 60.75 $/bbl at
3.5 percent sulphur and 82.06 at 1 percent. That is 0.7 $/bbl of answer. The
Gate 2 self audit, finding 7, found this repository publishing both, 6.23 here
and 5.51 from `crack.series.october_2022_triangulation`, from the same cache and
the same month, with nothing saying which was the answer.

The headline is the 3.5 percent row, for two reasons. SPEC.md section 4.4 asks
for the gas cost "against a refinery fired on fuel oil", and a refinery that
fires fuel oil burns its own heavy residue, which is high sulphur rather than
the low sulphur barge it would have to buy. And it is the figure this repository
published first; a published number does not move without a reason, and "the
other row is the one we crack elsewhere" is a reason to report the variant, not
to replace the headline with it.

The variant comes back from the same call, labelled, every time:

```
fuel oil fired, 1 percent sulphur   0.21217 x (82.06 / 6.287) = 2.769 $/bbl
difference                                                    = 5.51 $/bbl
```

So the gap is 6.23 $/bbl on the row a fuel oil fired refinery actually burns,
0.77 below S&P's figure, and 5.51 $/bbl on the low sulphur row, 1.49 below.
`series.october_2022_triangulation` refuses a fuel oil basis it does not
recognise rather than defaulting to one, which is how two answers got published
in the first place.

### 4.2 DGEC's own embedded gas intensity, and the wedge against this one

The published MBR already contains a gas purchase, section 2.3 above, so the
question this study can ask of it is not "what does gas cost" but "how does
DGEC's assumption compare with mine". Sizing that needs DGEC's 1.0 percent line
in this study's units, MMBtu per barrel of crude. Derived, not typed, from four
cited numbers:

| Input | Value | Source |
|---|---|---|
| natural gas as a share of the tonne of crude | 1.0 percent | DGEC methodology note, table 1, "Gaz naturel" |
| barrels per tonne of crude | 7.55 | the same note's own margin factor |
| natural gas per million tonnes of LNG | 48.0279 bcf | Energy Institute Statistical Review 2026, approximate conversion factors |
| heat content of natural gas | 1,036 Btu/cf, gross | EIA, as in the intensity above |

```
48.027940960947284 bcf per Mt x 1e9 cf per bcf / 1e6 t per Mt = 48,027.94 cf per tonne
x 1,036 Btu per cf                                            = 49,756,947 Btu per tonne
/ 1e6                                                         = 49.7569 MMBtu per tonne

0.010 tonnes of gas per tonne of crude / 7.55 bbl per tonne
    x 49.7569 MMBtu per tonne                                 = 0.06590 MMBtu per barrel
```

The Energy Institute table's own energy columns are NET heating values and this
study's intensity is built on EIA's GROSS heat content, which differ by about 10
percent, so the volume column is taken from EI and the heat content from EIA and
both sides of the comparison stay on one basis.

**0.0659 against 0.21217 is a ratio of 3.22.** Priced at one month's gas price
that gives the wedge in section 2.3: 3.09 $/bbl in August 2026 and 10.24 $/bbl in
August 2022. What the 1.0 percent line actually covers, fuel only or fuel plus
hydrogen feedstock, is `docs/open-questions.md` section 33; it moves the wedge and
it does not move the margin.

---

### 4.3 The margin the Gate 3 regressions ask about, and what changed

**Read this before reading any number out of `src/crack/analysis.py`.** SPEC.md
section 6.3 sets up a three horse race: (A) the raw gasoil crack, (B) the
official margin, (C) the margin after gas, where SPEC.md section 4.4 defines the
margin after gas as the gross margin minus a gas cost. Gate 2 established that
DGEC's published MBR is **already net of purchased gas**, section 2.3 and section
4.2 above. On the spec's own arithmetic B and C would therefore be the same
series and the race would be a two horse race still being described as three.

The third horse in this repository is therefore **the margin after gas at this
study's own gas intensity**:

```
margin_study_intensity(t) = MBR(t) - gas_wedge(t)
gas_wedge(t)              = (0.21217 - 0.0659) MMBtu/bbl x gas price(t) in $/MMBtu
```

that is, DGEC's published margin with DGEC's embedded gas assumption taken out
and this study's put in. It is not the spec's original C and it is not presented
as it. What it answers is a real and separate question: DGEC's 1.0 percent of the
tonne is a French linear programming model's purchased gas for a largely self
sufficient refinery, and 0.21217 MMBtu per barrel is EIA's US figure for a
refinery that buys more of its energy, so the horse race asks whether a refiner
at the higher gas intensity shows a different relationship with runs than the
official margin does.

The two are not the same series. Over the 140 published months the wedge runs
from 0.231 to 10.245 $/bbl, mean 1.704, so it moves month by month rather than
shifting the level. Measured over the same months:

| Series | mean | min | max |
|---|---|---|---|
| MBR as DGEC publishes it | 6.992 | -0.271 | 38.051 |
| gas wedge | 1.704 | 0.231 | 10.245 |
| margin at this study's intensity | 5.288 | -1.818 | 34.963 |

**DGEC's own MBR is reported beside it in every table `analysis.report()`
prints**, unchanged, so a reader who wants the official margin never sees only
this study's re-pricing of it.

### 4.4 Utilisation, and the date a capacity figure is allowed to describe

`utilisation = NWE5 crude intake (JODI, BE DE FR NL GB) / capacity (Energy
Institute)`. Four decisions, all visible in the code and none of them silent.

**The denominator is lagged one year, and this is a correction.** The Energy
Institute figure for year Y is atmospheric distillation capacity **at 31 December
of year Y**. Until the Gate 3 self audit this module divided January of year Y by
that figure, which is a number describing a date eleven months in the future and
published in the middle of the year after it. Finding 1.1 measured what that was
worth: capacity fell 5.3 percent between the 2024 and 2025 stamps, all of it
landing on 1 January 2025, so intake barely moved from December to January,
5,428.0 to 5,403.5 kb/d, and the forecast target jumped 4.20 percentage points.
Fifteen of the 72 out of sample targets of section 4.6 were built that way.

The rule now, applied once and everywhere: **a capacity figure is only ever
applied to months at or after the date it describes.** The first month at or
after 31 December Y is January of year Y+1, so month m of year Y carries the
figure stamped 31 December Y-1, the capacity the region was known to have when
the month began. `CAPACITY_SOURCE_LAG_YEARS` is that rule and it is 1.

What the fix costs, because it is not free: a denominator that is never from the
future is a denominator that is **up to twelve months stale**. The 2025 closures
are where that bites hardest, and every month of 2025 is now divided by a
capacity the region no longer had by December. The study prefers a stale number it
can date to a fresh one it could not have had. What the fix does **not** buy is a
real time series: the reference date is no longer in the future but the
publication date still is, since the Energy Institute volume carrying the
31 December Y figure appears around the middle of year Y+1. That residual is
`docs/open-questions.md` question 44.

**Capacity is a step, not a ramp.** A closure inside a year is already fully
inside that year's printed number, so one year end figure is carried across the
twelve months that follow it, which makes a closure a step at the turn of the year
rather than a slope spread over twelve. `CAPACITY_LINEAR` exists so the difference
can be measured. It is never the default and no reported number in the module runs
on it, for two reasons now rather than one: it smooths closures, which SPEC.md
section 6.1 asks not to do, and a straight line between the 31 December Y-1 and
31 December Y figures reads the later of the two into every month of year Y, which
is exactly the look ahead the alignment rule exists to stop.

**Only the ratio is published.** The capacity numbers stay in `data/private`,
`docs/sources.md` section 4.4 and `docs/open-questions.md` section 13 say why.

**2026 needs no assumption, and the basis argument is still there for when the
file runs out.** The Energy Institute edition ends at 2025 and JODI runs to
2026-06. Under the alignment above the 31 December 2025 stamp is exactly the right
denominator for every month of 2026, so the six months that used to have a
numerator and no denominator now have both and **nothing is extrapolated and
nothing is flagged `capacity_assumed`**. The argument survives under a year
agnostic name because the file runs out again every year, as soon as JODI reaches
the January after the last year end stamp: `CAPACITY_BEYOND_NAN` leaves those
months missing, which is SPEC.md non negotiable 1, and
`CAPACITY_BEYOND_HELD_FLAT` carries the last figure forward with every affected
row flagged. On today's data the two bases produce an identical series, and
`tests/test_analysis.py` asserts both that and that the guard still parts them for
a month past the file's reach.

**The annual sanity check is against the same-year figure, on purpose.** recon 03
section 2.3 divided each year's mean intake by that same year's capacity, so that
is the number `utilisation_sanity_check` compares with, and it still agrees to
three decimals in 11 of 11 years. The lagged annual mean that the regressions
actually run on is printed in the column beside it, along with the difference,
which reaches -0.044 in 2025. Neither can be quietly substituted for the other.

**The fallback is built too, and it is not a robustness check.** SPEC.md section
6.1 offers intake with a trend and closure dummies "if the capacity table is
unusable". The table is usable and not committable, so the owner's decision at
Gate 3 was to build both. The fallback regresses 100 times the log of NWE5 crude
intake on a linear monthly trend, month fixed effects, closure step dummies, and
the same margin lags. A closure step is a year in which NWE5 capacity fell by more
than 2 percent; two percent of a roughly 6.6 mb/d system is about 132 kb/d, one
medium NWE refinery, and the threshold was chosen from that reasoning before any
regression was run and has not been moved. **The step turns on in the January
after the fall is recorded**, by the same alignment rule as the denominator: the
2016 fall enters at 2017-01 and the 2025 fall at 2026-01, and the dummies are
named `closure_step_2017` and `closure_step_2026` after the month they turn on.
A dummy starting in January of the fall year would assert in January that the
region was going to lose a refinery before December, and unlike an episode dummy
for an episode that has not happened yet it is **not** a column of zeros in the
training rows of the expanding window, so it was a live look ahead in the out of
sample exercise rather than an inert one. `intake_trend_response` also runs with
`closure_years=()`, which needs no capacity data at all, and both are reported.

### 4.5 Two estimator choices that could look like tuning, and are not

SPEC.md section 6.6 forbids parameter search. Two numbers in `analysis.py` are
read off the data rather than fixed, so both are written down here.

**The Newey-West truncation lag** is `max(3, floor(4 * (n / 100) ** (2 / 9)))`,
the usual automatic rule with SPEC.md section 6.1's floor of 3 on top. At n = 135
it gives 4. It is a function of the sample size and of nothing else, and
`tests/test_analysis.py` checks both the rule and that the covariance actually
uses that many lags, against statsmodels on the same data.

**The bootstrap block length** is the shortest lag at which the dependent's own
sample autocorrelation first falls inside the two over root n band. On the real
sample that is **20 months**, because utilisation is very persistent: the
autocorrelations run 0.855, 0.736, 0.672 and are still near 0.5 at a year. A
shorter block would narrow the threshold interval and it would be the wrong
answer, so the block was not shortened. The rule, the band and the
autocorrelations it was read off are all printed by `analysis.report()` so the
reading can be checked rather than taken.

### 4.6 The horse race, and the substitution inside it

SPEC.md section 6.3 calls the horse race the point of the analysis and names
three runners: **(A)** the raw gasoil crack, the number on every screen, **(B)**
the official margin, **(C)** the margin after gas.

**Horse C in this study is a substitution, and it is labelled one everywhere.**
Gate 2 established that DGEC's published MBR is already net of purchased gas at
DGEC's own embedded intensity of 0.06590 MMBtu/bbl, section 4.2 above. Read
literally, the spec's B and C are therefore the same series, and a race between
them would be two horses presented as three. So horse C is the published MBR
re-priced at this study's EIA derived intensity of 0.21217 MMBtu/bbl:

```
horse C = MBR - gas wedge
gas wedge = (0.21217 - 0.06590) * gas price in $/MMBtu
```

That is a real and different question, about a refiner who buys more of his
energy than DGEC's model refinery does, and the wedge ran 0.23 to 10.24 $/bbl
over the sample, so the two are not the same column. **It is not the spec's
original horse C**, the substitution is carried on the `Horse` record as a flag
rather than in prose, and `tests/test_analysis.py` asserts that the flag reaches
every table the race is printed in.

**The sample trap, and what was done about it.** The OPEC Rotterdam quotations
start 2000-10 and DGEC's MBR file starts 2015-01. Horse A therefore has 288
usable months and horses B and C have 132. Racing each on its own sample would
hand A twenty extra years of quieter data and the comparison would be worthless.
**The race runs on the common sample, 2015-04 to 2026-03, n = 132 for every
horse, at the same Newey-West lag**, and horse A's longer sample is reported
separately and labelled as not being the race. `common_sample_dates` computes the
intersection, the restriction is applied to the rows **after** the lags are built
from the full frame, and a test checks that a restricted horse's lag 1 column is
still the value one calendar month earlier and not the previous surviving row.

The race is run **on both dependents**, utilisation over Energy Institute
capacity and the log intake fallback, because the first half of this gate found
that the two disagree about the response and a race that held under only one of
them would be a weaker result than one that held under both.

**The out of sample RMSE.** SPEC.md section 6.3 asks for an expanding window one,
and it is the honest discriminator: in sample R squared rewards a regressor for
fitting 2020 and 2022 after the fact. The window trains on the first 60 months,
forecasts month 61, adds it and refits, and so on to the end of the sample, 72
forecasts in all. Every coefficient is estimated on the training rows only. The
specification, meaning which columns exist, is fixed by SPEC.md section 6.1
before any data is seen and is the same at every origin; an episode dummy for an
episode that has not happened yet is a column of zeros in the training rows and
gets a zero coefficient, so the first month of an episode is forecast as though
the episode were not there. The design comes off the fitted regression rather
than being rebuilt, so the out of sample equation cannot drift away from the in
sample one printed beside it. The test that carries the claim poisons the
dependent from some month onward with an absurd value and asserts that every
forecast made before that month is bit for bit unchanged.

Beside each horse's RMSE is the same exercise for a model that predicts the
training mean and nothing else. A regressor that cannot beat the mean has not
earned the word "explains".

**The largest caveat on that whole column, said plainly.** A 60 month training
window on a 132 month sample puts the first forecast in 2020-04. **All 72 out of
sample months therefore fall between 2020-04 and 2026-03, and 25 of them sit
inside one of the three episode windows.** The out of sample period *is* the
crisis period. It is not a quiet holdout, and no choice of training window makes
it one on a sample that starts in 2015: shortening the window to gain quieter
months would be choosing the window after seeing what it does, which SPEC.md
section 6.6 forbids. Horse A's own longer sample gets 228 forecasts from 2007-04,
which is a far more varied period, and that is one more reason its numbers are
reported separately rather than dropped into the race table.

**What the race found, and it is not what the spec expected.** Under the capacity
dependent the lowest out of sample RMSE belongs to **horse A, the raw gasoil
crack**, at 6.7601 against 6.7793 for C and 6.8159 for B. Under the fallback it
belongs to horse C, at 4.7462 against 4.8070 for B and 4.8911 for A. The two
dependents do not agree on the ordering, and **not one of the six pairwise
squared error differences, three under each dependent, is distinguishable from
zero**, at t between 0.04 and 0.77.

SPEC.md section 6.3 says that if A wins we say so on the page. A has the lowest
number under one of the two dependents and it is said, here and in
`analysis.report()`, and nothing was changed to stop it. What is **not** said is
that A won, because the difference is not distinguishable from noise, and what is
also not said is that the three are equal.

**This sample cannot tell the horses apart, which is not a finding that they are
equal.** The module used to print "the race is a dead heat" and this document
used to print it in bold. A dead heat asserts equality, which is a finding, and
the Gate 3 self audit, finding 2.1, measured how little support there is for it.
Against the effects actually observed, the power of these six 5 percent tests runs
**0.050 to 0.121, against a test size of 0.050**. A test whose power equals its
size is a coin that always returns "not distinguishable"; its failure to reject is
arithmetic about the sample, not evidence about the null. The smallest RMSE gap
any of the six could have called distinguishable runs **3.53 to 12.28 percent**,
against observed gaps of 0.28 to 2.96 percent, and reaching 95 percent power
against the gaps actually measured would take **1,570 to 670,408 one step ahead
forecasts**, the kindest pair about 131 years of monthly data.

So the honest sentence, and the one the module now emits, is that **this sample
cannot separate the three horses**, with the power printed beside it so a reader
can see why. `horse_race_winner` assembles every clause of that from the numbers,
including the identity of the horse with the lowest RMSE, so it will say something
different if the data ever does.

**What separates them is in sample, not out of it.** Under the capacity
dependent none of the three coefficients is distinguishable from zero at all,
at t of A -1.09, B -0.39 and C +0.30. Under the fallback all three are positive,
A at +0.166 with a Newey-West standard error of 0.102, B at +0.400 with 0.240 and
C at +0.466 with 0.236, so t of +1.64, +1.67 and +1.98.

**What B and C give that A cannot**, which is the honest statement of this
study's value once the race has come back undecided, and which is the second half
of what SPEC.md section 6.3 asks for when A is not beaten:

- **A level.** A crack of 25 $/bbl is a number; a margin of 6 $/bbl is a
  decision. Only the margin is denominated in what the barrel earns after the
  crude and the energy are paid for, so only the margin can be set beside a cash
  cost, and only the margin has a sign that means something.
- **The gas wedge.** It ran 1.02 $/bbl on average before 2022 and 5.90 $/bbl
  through 2022, peaking at 10.24. A gasoil crack cannot show that the same crack
  was worth several dollars a barrel less to a gas fired refinery that year.
- **A threshold in dollars.** "How far is today from the level where runs get
  cut" is a question that can only be asked in margin space. This study did not
  find that level, **section 4.10 below**, but the question is askable of B and C
  and is not askable of A. This cross reference used to point at section 4.7,
  which is endogeneity, and the section it should have pointed at did not exist.

### 4.7 Endogeneity, which is not fixed and is not hidden

**Runs move cracks.** More runs mean more product on the water and a weaker
crack, so the regressor this equation treats as a cause is partly an effect of
the thing it is explaining. The bias that puts in the estimated response is
**toward zero**. Every coefficient reported by this module should be read as a
lower bound in absolute value, and the honest reading of a coefficient
indistinguishable from zero is "this sample cannot see the response", not "there
is no response".

Lagging the regressor one to three months, which SPEC.md section 6.1 does, helps
only partly: it removes the same month simultaneity and not the rest, because a
shock that raises runs depresses cracks for months afterwards and because both
series are persistent. `analysis.endogeneity_diagnostic` prints the correlation
of runs with each regressor at lags 0 to 3 so the shape of the problem is
visible. **It identifies nothing** and the report says so: simultaneity is not
visible in a correlation.

**The instrument was the attempt to fix it, and it failed.** SPEC.md section 6.3
suggests the gas cost as an instrument for the margin after gas, on the ground
that TTF was driven by pipeline cuts in 2022 and LNG disruption in 2026 rather
than by NWE runs.

*The exclusion restriction, stated before the instrument was run.* It is that the
European gas price affects NWE refinery runs **only** through the refining
margin. It is arguable and it is not obvious, and this study's view is that it
probably does not hold exactly. Gas is not only a cost line: it is a hydrogen
feedstock for hydrotreating and hydrocracking, so a gas shock can change what a
European refiner runs and how hard for reasons the margin does not capture. A gas
shock also arrives inside a wider energy shock that moves product demand,
industrial activity and crude at once, and those channels reach runs without
passing through the margin.

*What was expected of the first stage, also written down first.* That it would be
relevant by construction and that a large F would therefore be partly arithmetic:
this study's margin contains the gas price as an exact linear term with
coefficient -0.14627, and DGEC's MBR is itself net of gas.

*What actually happened.* **The first stage F is 0.215 with the controls the
capacity equation carries and 0.070 with the controls the fallback equation
carries.** That sentence used to read "0.215 on the capacity dependent and 0.070
on the fallback", which is a misdescription: **the first stage contains no
dependent variable at all.** It regresses the endogenous margin on the controls
and the instrument. The two numbers are one control set with and without a single
column, the linear monthly trend the fallback equation carries, and the sign of
the first stage coefficient flips on that one column, +0.043 to -0.028. Gate 3
self audit, finding 3.1.

*Where the F actually goes, measured rather than asserted.* The controls are put
in one at a time, on the same sample and the same Newey-West lag:

| Controls | Coefficient | HAC se | F | Partial R2 |
|---|---|---|---|---|
| constant only | +0.10594 | 0.04417 | **5.753** | 0.0984 |
| plus month dummies | +0.10800 | 0.04484 | **5.802** | 0.1027 |
| plus episode dummies, the capacity equation | +0.04306 | 0.09277 | **0.215** | 0.0059 |
| plus a linear trend, the fallback equation | -0.02807 | 0.10609 | **0.070** | 0.0020 |

**The episode dummies do the killing.** And that matters, because the
instrument's variation **is** the episodes: its standard deviation inside the
three twelve month episode windows is 18.61 $/MMBtu against 5.31 outside them,
and its largest value, 60.16, is 2022-10. SPEC.md section 6.3 names exactly that
variation as the reason to try this instrument, "TTF was driven by pipeline cuts
in 2022 and by LNG disruption in 2026", and the equation SPEC.md section 6.1
specifies then places a 0/1 step over each of those windows and takes it out. The
specification is controlling away the instrument's own identifying variation.

*So the diagnosis this document used to give was wrong by about two thirds.* It
said the mechanical deduction of -0.14627 is roughly cancelled by the margin's own
co-movement with gas, leaving +0.043. Measured, **the cancellation leaves
+0.10594**: the raw slope of MBR on gas is +0.23581, the mechanical term is
-0.14627, the net raw slope of the study margin on gas is +0.08954, and the first
stage with a constant alone is +0.10594. The step from +0.106 down to +0.043 and
then to -0.028 is the episode dummies and the trend, not the cancellation. The
honest statement is not that gas has no purchase on the margin. It is that **gas
has purchase on the margin, that the purchase is the crisis months, and that this
equation's own regime terms remove the crisis months.**

The two stage estimates that follow, -9.44 with a standard error of 20.40 and
+4.98 with 17.58, are not usable and are printed only because the spec asks for
the exercise.

**So the instrument is weak and this study says so rather than forcing it.** The
operational conclusion survives the corrected diagnosis without a scratch: F of
0.07 to 0.22 under the spec's own equation, and still only 5.80 on a constant and
the month dummies with the 2022 shock left in, below the rule of thumb bar of 10
either way. Nothing downstream reads it. The headline response is ordinary least
squares, the endogeneity is unaddressed, and that is reported as a limitation and
not as a solved problem.

### 4.8 Did the link hold in 2026: count the months first

SPEC.md section 6.4 asks whether the relation held after 2026-02-28. Before
running anything, the months were counted.

| Series | Last month |
|---|---|
| JODI NWE5 refinery crude intake, the dependent | 2026-06 |
| OPEC Rotterdam quotations, horse A | 2026-02 |
| DGEC MBR, horses B and C | 2026-08 |

The OPEC series stops in 2026-02 for a collection reason and not a publication
one: the six Monthly Oil Market Report issues from April to September 2026 are
not in the Internet Archive and this pipeline cannot fetch them. That is recorded
as a manual step in `data/manifest.json` and it is why the horse race ends in
2026-03 while the section 6.1 response reaches 2026-06.

The dependent ends 2026-06, so there are **four** months after the break with a
dependent and all three margin lags. The bar this study set before looking, and
did not move afterwards, is **twelve** post break months, one full seasonal
cycle, because the equation carries eleven month dummies and a verdict drawn from
fewer months than it has seasonal terms is a verdict about which months happened
to fall after the break.

**Four months cannot say whether a relation held, so this study returns no
verdict.** That is the answer to SPEC.md section 6.4 on this data date, and it is
one sentence rather than a Chow test that would produce a number looking like an
answer. The question reopens with the JODI release for 2027-02, around April 2027.

What can be done honestly is done: the equation is fitted on the months up to and
including 2026-02 and each post break month is predicted out of sample, with the
episode dummies deliberately **off**, since a 2026 dummy would absorb exactly the
deviation being looked for. The residuals are a description of four months and
the module does not call them a test.

| Month | Capacity model, kb/d | Fallback, kb/d |
|---|---|---|
| 2026-03 | +25 | +141 |
| 2026-04 | -144 | -187 |
| 2026-05 | +18 | +23 |
| 2026-06 | -166 | -307 |

Runs came in below what the margin implies in two of four months on each model,
the largest gap 1.12 in sample residual standard deviations. **These residuals
moved when finding 1.1's capacity alignment was fixed**, section 4.4: on the old
denominator the capacity model was below in four of four and the fallback in three
of four, with the largest gap 1.79 standard deviations. That is a reminder of how
little four months carry, and it is one more reason the verdict is "ask again in
April 2027" rather than a number. **No month here carries an assumed capacity any
more**: the 31 December 2025 figure is the right denominator for every month of
2026. What all of them do carry is a denominator up to twelve months stale, which
is the price of the alignment and which every other month of the sample pays too.

**The competing explanations, none of which this data can separate.** Three
events fall inside these four months, each cited from `data/seed/events.json`
with its source URL: the strikes on Iran and the halt to Hormuz traffic on
2026-02-28, the IEA coordinated release of 400 million barrels on 2026-03-11, and
the US and Iran ceasefire on 2026-04-07. At least three mechanisms would put runs
below what the margin implies, and all three are consistent with this table:
**feedstock availability**, with Hormuz halted a refiner can face a good margin
and have no suitable crude on the quay, which is what the IEA reported for
refiners outside the Gulf; **unplanned outages**, since one large NWE unit down
for a month is worth about a hundred kb/d, the size of these residuals; and
**maintenance**, since the NWE spring turnaround season is March to May and its
timing moves year to year while the month dummies carry only the average season.

**This study does not pick one.** Four monthly observations cannot separate three
explanations, and JODI publishes no outage or turnaround series that would let
them be separated. SPEC.md section 6.4 says to set them out and not to choose.

### 4.9 Seasonality, checked rather than asserted

**Which series, and where the join is.** Two layers, two panels, **never one
line**:

- **Monthly, the long history.** OPEC MOMR Rotterdam quotations, 2000-10 to
  2026-02, 305 months. This is the only series in the project deep enough to give
  the five year range SPEC.md section 6.5 asks for.
- **Weekly, where it reaches.** This study's reconstruction of the DGEC note
  chart, 2022-07-01 to 2026-09-04, 219 Fridays. It is not a DGEC publication and
  it carries the reconstruction error measured in section 6 below.

They quote different products: DGEC's Gazole and Eurosuper against OPEC's gasoil
and premium gasoline. Over the 44 overlapping months the weekly series averaged
to months sits **+0.92 $/bbl** from the monthly one on gasoil, mean absolute gap
1.24, correlation 0.9935; and **-9.01 $/bbl** on gasoline, mean absolute gap 9.02,
correlation 0.8861. The gasoline gap is the size of a different product, not an
error, and it is the reason the two layers are shown side by side and never
spliced.

**The five year weekly range SPEC.md section 6.5 asks for does not exist.** The
weekly reconstruction begins 2022-07-01, so at most four calendar years are
available and the first half of the year has only three. Every week carries an
`n_years` count so a chart prints the depth beside the band rather than drawing
four years and calling them five.

**The textbook check.** Each crack is demeaned within its own calendar year, so
what is left is the shape of the year and not its level, which otherwise swings
by tens of dollars between years for reasons that are not seasonal. For each
season, the season's months less every other month of the calendar years that
season spans is one number. The mean of those numbers is reported with its
standard error **across seasons**, because a year is plausibly independent of the
next for this purpose and a month is not. The month sets were written down before
the test: driving season May to September, heating season November to March. The
removable years of SPEC.md section 6.5 are 2020, 2022 and 2026, and a test poisons
those years with absurd values and asserts that excluding them gives the same
answer as deleting them.

**Which winter, and why this has to be said.** A driving season fits inside one
calendar year. **A winter does not.** Until the Gate 3 self audit this module
applied November to March *inside one calendar year*, which averages November and
December of year Y with January, February and March of the **same** year Y: the
head of one winter and the tail of the one before it. The heating season quoted
here is now the contiguous one, November and December of year Y with January,
February and March of year Y+1, compared with the other nineteen months of the two
calendar years it spans. Both windows are computed and both are printed, so the
size of the difference is visible rather than quietly corrected. There are 25
complete years and therefore 24 contiguous winters, because a winter needs both of
its years complete.

| Claim | Window | Seasons | In | Out | Difference | Median | se | t | Positive | |
|---|---|---|---|---|---|---|---|---|---|---|
| gasoline into the driving season | contiguous | 25 | +2.79 | -1.99 | **+4.78** | +4.01 | 1.03 | +4.64 | 22 of 25 | holds |
| gasoil into the heating season | contiguous | 24 | -0.35 | +0.09 | -0.44 | -0.56 | 0.75 | -0.59 | **10 of 24** | does not hold |
| gasoil into the heating season | calendar year | 25 | -0.21 | +0.15 | -0.37 | +0.36 | 1.04 | -0.35 | 16 of 25 | does not hold |
| gasoline, crisis years removed | contiguous | 23 | +2.51 | -1.80 | **+4.31** | +4.01 | 0.85 | +5.07 | 21 of 23 | holds |
| gasoil, crisis years removed | contiguous | 20 | -0.09 | +0.02 | -0.11 | -0.56 | 0.62 | -0.18 | 8 of 20 | does not hold |
| gasoil, crisis years removed | calendar year | 23 | +0.15 | -0.11 | +0.26 | +0.36 | 0.76 | +0.35 | 15 of 23 | does not hold |

The driving season is identical under both windows, which is why the gasoline
rows are printed once. "Crisis years removed" takes out **two** complete years and
not three: 2026 has two months in the cache, so it was never one of the 25 and
cannot be taken out of them.

**Gasoline: the textbook holds and it is not close.** The driving season months
sit 4.78 $/bbl above the rest of the year, positive in 22 of 25 seasons, and the
difference survives removing the crisis years. Peak month June, trough December.

**Gasoil: the textbook does not hold as it is usually stated.** The contiguous
winter is 0.44 $/bbl from the rest of the two years it spans with a standard error
of 0.75, t -0.59, which is nothing; and it is nothing under every window tried,
t -0.59, -0.35, -0.18 and +0.35. **That conclusion is the finding SPEC.md section
6.5 asked to have checked rather than asserted, and it survives.**

**Two sentences that used to support it did not, and have been replaced.** Gate 3
self audit, findings 5.2 and 5.3.

- "Positive in only 16 of 25 years" reads as "the sign was usually right and the
  mean was dragged down". That count is an artefact of splitting winters at the
  year boundary. Under the contiguous winter it is **positive in 10 of 24**, a
  minority.
- Quoting -0.37 as the estimate gives it more standing than the data supports.
  Its sign rests on two observations out of twenty five, 2022 at -18.81 and 2008
  at -10.74 against a next most negative year of -6.39, and it does not survive
  them: -0.37 on all years under the calendar window, +0.26 with the crisis years
  out, -0.44 on contiguous winters, -0.11 on contiguous winters with the crisis
  years out. Note also that under the calendar window the mean and the median have
  **opposite signs**, -0.37 against +0.36, which is exactly why 16 of 25 years came
  out positive under a negative mean. Under the contiguous winter they agree,
  -0.44 and -0.56, which is a further reason to prefer that window. The honest
  statement is that the gasoil winter effect is **indistinguishable from zero
  under every definition tried**.

The within year shape says where such strength as there is lives: the gasoil
crack's strongest month is **October** at +3.00 and its second strongest November
at +2.09, while December, January and February are all negative. **Such strength
as there is arrives in the autumn build and has faded by the middle of the winter
it was built for.**

A window drawn around that October peak would fit better. **It is not tested here
and no number for it is reported**, because a window chosen after seeing the
table is a parameter search and SPEC.md section 6.6 forbids it. The honest
statement is the one above: on this sample, in the windows a desk would name out
loud, gasoline is seasonal and gasoil is not.

### 4.10 The run cut threshold, which is one episode

This section did not exist until the Gate 3 self audit asked for it, finding 4.2.
The threshold is the one result the site's headroom figure depends on and it was
documented in one line in section 7 and nowhere else.

**What is fitted.** SPEC.md section 6.2's hockey stick and nothing else: a level,
flat above a threshold, one slope below it, on utilisation against the mean of
this study's margin at lags 1, 2 and 3. No month fixed effects and no episode
dummies, because the episodes are where the margin fell and where runs fell, and a
dummy on them would remove the variation the threshold is estimated from. The
threshold is found by profile least squares over a grid from the 5th to the 95th
percentile of the regressor in 0.25 $/bbl steps, and the interval is a moving
block bootstrap percentile interval, 2,000 replications, seed 62, block length
read off the dependent's own autocorrelation.

**What came back.** Threshold **2.28 $/bbl**, level 82.78 percent, slope below
+3.88 percentage points per $/bbl with a Newey-West standard error of 0.75, on
135 months. The 95 percent interval is 2.03 to 11.28, which **reaches the top of
the searchable range**, so by SPEC.md section 6.2's own edge rule the verdict is
**unidentified**, the site shows no headroom figure and falls back to the ten year
percentile.

**The verdict does not turn on where the grid was cut.** Four quantile grids were
run, 0.05 to 0.95, 0.02 to 0.98, 0.00 to 1.00 and 0.10 to 0.90. All four come back
unidentified and the point estimate moves between 2.27 and 2.76 $/bbl. The headline
grid is the module constant and did not move; nothing downstream reads the other
three.

**The concentration, which is the thing to read.** 24 months sit below the
estimated threshold and **21 of them are one unbroken stretch, 2020-07 to
2022-03**. That is computed by `report()` rather than typed, and so are its dates:
they used to be recovered as the last 21 entries of the list of months below,
which is correct only while the longest run happens to sit at the end of it, and
finding 4.3 showed the same code printing a 59 month span that does not exist when
a stray month falls after the run.

**Take that stretch out and the estimate does not widen, it reverses.** This is
the check SPEC.md section 6.1 asks for by name and that `run_cut_threshold` could
not perform until now:

| | With every month | Without 2020-07 to 2022-03 | Without the three episode windows |
|---|---|---|---|
| n | 135 | 114 | 106 |
| Threshold | **2.28** $/bbl | **9.87** $/bbl | 1.99 $/bbl |
| Slope below | **+3.8786** | **-0.4958** | +4.0244 |
| Months below | 24 of 135 | **101 of 114** | 11 of 106 |
| Kink R2 | 0.2971 | **0.0559** | 0.2299 |
| Straight line R2, same sample | 0.0309 | 0.0455 | 0.0000 |
| Mean utilisation below | 74.84 | **83.17** | 75.17 |
| Mean utilisation above | 82.76 | **80.40** | 83.77 |
| Verdict | unidentified | unidentified | unidentified |

**The slope flips sign.** Without the episode, runs rise as the margin falls below
the estimated kink, which is the opposite of the hockey stick SPEC.md section 6.2
describes. The threshold walks from near the bottom of the sample to near the top,
101 of 114 months sit below it, the mean utilisation below and above swap places,
and the kink buys 1.0 points of R2 over a straight line against 26.6 points with
the episode in. The bottom of the regressor's range goes with the stretch too:
everything from -0.743 up to +2.021 $/bbl, which is every month in which the
lagged margin was negative, is inside it.

**A kink whose slope reverses when one episode is removed is not a kink.** That is
the strongest available statement of why the verdict is unidentified, and it is
better evidence than the width of the interval: an unidentified interval sounds
like a wide estimate of something real, and this is a description of one episode.

**Nothing is selected on either variant.** The headline threshold, its interval
and its verdict are the ones computed with every month in. The stretch removed in
the middle column is read off the headline result rather than chosen, which makes
it a destruction test and not a search, and the right hand column is the rule
SPEC.md section 6.1 fixed before any of this was run. SPEC.md section 6.6.

---

## 5. The monthly averaging rule, fixed once and in the open

A daily series becomes a monthly one in exactly one place,
`crack.config.monthly_mean`. It is not left to a library default because the
choice moves the answer by more than two thirds of the tolerance it is tested
against.

Three defensible readings of "the monthly mean" were measured over 2015-01 to
2026-08:

| | |
|---|---|
| A | mean of the days the source actually published a price |
| B | reindex to every business day, carry the last price forward, then mean |
| C | reindex to every calendar day, carry forward, then mean |

| Comparison | Worst month | Mean | Months apart by more than 0.10 $/bbl |
|---|---|---|---|
| A against B | 1.0995 $/bbl | 0.0634 | 29 of 140 |
| A against C | 1.1533 $/bbl | 0.1699 | 82 of 140 |

The SPEC.md section 5.5 Brent cross check allows 1.5 $/bbl. The averaging choice
alone can move a month by 1.10 of that, so in December 2018 or April 2026 it
could by itself decide whether a month passes.

**Method A is the rule.** Two reasons. Filling a UK bank holiday with Friday's
Brent invents a price on a day nobody traded, which SPEC.md non negotiable 1
forbids outright. And A is the closest honest match to what DGEC is doing, which
is averaging its own daily quotations over the month.

Three consequences are built into the function rather than left to the caller.
Every calendar month between the first and the last observation appears, so a
month the source covered but published nothing in is a NaN with an observation
count of zero rather than an absent row. The observation count travels with every
monthly value, so an outlier can be reported as "this month failed on 17 days of
data". And a month carrying fewer than 15 published days is NaN rather than a
thin mean; 15 excludes nothing in the 2015 onward sample, whose thinnest month is
December 2018 with 17 days, and it correctly excludes a partial current month.

### 5.1 What the rule buys, measured

The SPEC.md section 5.5 cross check, computed from the two committed caches:

| | |
|---|---|
| months compared | 140 |
| within 1.5 $/bbl | **140**, which is 100 percent against a 95 percent bar |
| mean absolute | 0.0136 $/bbl |
| worst month | 0.2649 $/bbl |
| outliers | **none** |

That single number validates three things at once that could each have been
wrong on their own: the DGEC workbook parser, the FRED parser, and the 7.5 bbl/t
factor of section 3.2. It is recorded as data in `data/seed/anchors.json` and
recomputed by `tests/test_events_anchors.py` rather than copied.

---

## 6. The measured error of the weekly reconstruction

Section 1 is the full account. The summary a reader needs before trusting a
weekly crack:

| | |
|---|---|
| What it is | four series decoded from the vector polylines on page 3 of ten DGEC weekly notes |
| Span | 219 consecutive weeks, 2022-07-01 to 2026-09-04, no holes |
| Calibration | one additive offset per note, fitted by least squares on that note's own eight printed anchors |
| Out of sample error, **across products only** | **0.17 to 0.44 $/t mean absolute**, worst single point 0.87 $/t |
| In $/bbl on the gasoil leg | about 0.02 to 0.12 |
| Agreement between overlapping notes, **the figure that speaks to time** | 0.30 $/t mean absolute, 1.68 $/t worst single week |
| Weeks with no independent cross check | 25 of 219, flagged in the data itself, split by kind in `evidence_class` |
| Least defended weeks | the six of 2022-07-01 to 2022-08-05, uncorroborated **and** 105 weeks from the nearest anchor, flagged `single_geometry_oldest` |
| Least accurate of the four | Brent date, flagged in the manifest |
| Not reconstructed | Jet and Fioul lourd TBTS are not plotted on the chart and are therefore absent. Regressing them on the three that are plotted would be the synthetic series SPEC.md non negotiable 1 forbids |

**The 0.17 to 0.44 figure is a leave one series out number and all eight anchors
of every note sit on the last two weeks of a 105 week chart. It is out of sample
across products and in sample across time, and it does not bound the other 103
weeks.** Section 1.5 sets this out in full and section 1.6 shows what the gates
cannot see. Quote 0.30 and 1.68 next to a week in the middle of the series.

The error, that caveat, the tilt measurement, the quantisation caveat and the
list of least defended weeks are all carried in the manifest entry under
`reconstruction`, not only in this document, and the series declares
`method: reconstructed` so that no chart can present it as a figure DGEC
published.

---

## 7. What does not exist yet, and which gate builds it

This document covers Gate 1, the data layer, and nothing else. Saying so is
cheaper than letting a reader assume.

**Gate 2, the engine.** `src/crack/engine.py` and its JavaScript mirror do not
exist. Nothing in this repository yet computes a margin, a decomposition, a
contribution, a breakeven or a ten year percentile. The four layers of section
2.2 are inputs today and arithmetic tomorrow. The units, null, linearity, round
trip, alignment and replication tests of SPEC.md section 9 are Gate 2 tests; the
anchor and intensity tests of that section already run.

**Gate 3, the analysis, is now complete.** `src/crack/analysis.py` covers SPEC.md
section 6 end to end: the utilisation series and its fallback and the response
regression with Newey-West standard errors and the kb/d translation (6.1), the
run cut threshold with its block bootstrap (6.2), the three horse race with an
expanding window out of sample RMSE on both dependents, the endogeneity statement
and the gas instrument with its first stage F (6.3), the 2026 residuals (6.4) and
the seasonal check (6.5). Sections 4.3 to 4.10 above document every choice those
make. `analysis.report()` prints the whole of it and is the Gate 3 output.

**Two of section 6's questions came back negative and stay negative.** The run
cut threshold is **unidentified**, so `headroom` is None and SPEC.md section
6.2's fallback applies: the site shows the ten year percentile and no headroom
figure. And the 2026 question has **no verdict**, because the post break sample
is four months against a bar of twelve set before looking. Both are results
rather than unfinished work, and SPEC.md section 2 rule 4 allows them.

**What still does not exist in the analysis layer, and should not.** Nothing
writes a site facing JSON artifact: SPEC.md section 10 puts that behind Gate 4,
and `analysis.report()` deliberately writes nothing to `data/`. There is no
strategy, no Sharpe ratio and no profit and loss anywhere, by SPEC.md section 6.6.
Any number in those categories appearing anywhere is a bug.

**One conflict inside SPEC.md, resolved rather than denied.** This paragraph used
to say "there is no forecast" as well, and that was not true. SPEC.md section 6.3
asks for an expanding window out of sample RMSE **by name**, and the horse race
computes 72 one step ahead forecasts per horse per dependent, 432 in all. SPEC.md
section 6.6 says "no forecasts". The conflict is resolved in favour of 6.3, which
is the specific instruction, and the resolution is this: **the only forecasts in
this project are the one step ahead ones SPEC.md section 6.3 requires in order to
score a regressor out of sample.** None of them is shown as a prediction of
anything, none is about the future, no parameter is chosen using them, and nothing
is optimised on them. Saying "no forecast" while computing 432 of them was the
part that read badly. Gate 3 self audit.

**Gate 4 and Gate 5, the site.** There is no `index.html`, no CSS and no
JavaScript, and there should not be: SPEC.md section 10 forbids UI work before
the data and the engine are approved.

---

## 8. Deviations from SPEC.md, on the record

Three, all measured rather than argued, all flagged for the owner. This line used
to say two and list three.

**`BOUNDS_BRENT_USD_BBL` is (5.0, 250.0), not SPEC.md section 5.4's (10, 250).**
FRED and EIA both publish 25 real Brent prints below 10 $/bbl: seventeen days of
the 1998 price collapse, low 9.10 on 10 December 1998, seven days in February
1999, low 9.77, and 21 April 2020 at 9.12. The same 25 dates carry the same
values in both sources, so this is not a FRED artefact. With the bound at 10 the
adapter refused the whole download, kept no cache and exited non zero, which is
correct behaviour for a bound that has been violated and the wrong answer to a
bound that is wrong. The bound is a units and parse check, not a view on the
market, and 5.0 still catches a file that arrived in cents or with a decimal
point in the wrong place. Cutting 1998 and 2020 out of the history to fit a
printed number would be closer to inventing data than widening the bound is. The
only honest alternative is to start the Brent series in 2000 and say so on the
page. Open question 3.

**SPEC.md section 5.4 asks for "a real user agent". For fred.stlouisfed.org that
instruction is wrong**, measured twice on two days: a browser string gets the
connection reset or times out, and a named bot token gets HTTP 200. The project
sends `crack-spread-study/1.0` to that host and a browser string everywhere else.
Open question 2.

**SPEC.md non negotiable 7 says the CI gate is the deploy gate, and there is no
CI.** `.github/workflows/` is empty. SPEC.md section 10 puts both workflows at
Gate 5, so writing them now would be building ahead of an approval the spec
requires. Until then `make gate` is what stands in their place and it is a
manual step: `python scripts/refresh.py --offline`, `python -m pytest tests`,
`node tools/validate-data.mjs`, `node tools/check-dashes.mjs`. The Makefile used
to describe those four as "the same commands in the same order as CI"; it now
says what is actually true. One step belongs in the workflow when it is written
and is deliberately not in the target: `git diff --exit-code data/manifest.json`
after the offline refresh, which only means anything on a clean checkout. Open
question 31.

---

## 9. What the gate can and cannot see

Written down because the Gate 1 self audit measured it rather than assumed it,
and because a reader deciding how much to trust a committed number should know
which checks stand behind it.

`make gate` is four commands and they see different things.

| | refresh --offline | validate-data.mjs | pytest | check-dashes.mjs |
|---|---|---|---|---|
| a cache missing or unreadable | yes | yes | yes | |
| a value outside its declared bounds | yes | yes | yes | |
| a duplicate, out of order or missing date | yes | yes | yes | |
| a column emptied to all NaN | yes | yes | yes | |
| a manifest that disagrees with the file | yes | yes | | |
| a numeric column nobody classified | | yes | | |
| **a value changed INSIDE its bounds** | no | no | **yes** | |
| a published anchor that stopped reproducing | **yes** | | yes | |
| an em dash or en dash | | | | yes |

The bold row is the one that used to be a hole. The audit put 99.99 into one
cell of `data/cache/dgec_mbr_monthly.csv`, a 172 percent error on a figure
SPEC.md section 5.5 prints, and watched the offline refresh report 19 of 19 ok
and the validator pass 15 of 15. Only pytest caught it, and only because the MBR
was one of exactly two series with value level assertions.

Two things closed it.

**`tests/cache_digests.json`**, a committed record of every committed cache: its
sha256, its row count, its column list, and the first and last published value of
every value column with its date. `write_cache` is deterministic, so a clean
rebuild of unchanged data reproduces the bytes exactly and **any** edit anywhere
in any committed cache fails `tests/test_cache_values.py`. The per column anchors
exist so that the failure names a file, a column, a date and two numbers rather
than two hex strings. A digest failure is never a reason to regenerate the
digest: find out what the source served, then `python tests/cache_digests.py
--write` and read the diff.

**The anchor claim is re measured rather than re read.** `data/manifest.json`
carried `"mbr_anchors_reproduced": 9` and a note saying the anchors reproduce,
counted from the `"reproduces": true` flags in `data/seed/anchors.json`. With a
corrupted cache in place it went on saying so, byte identically, because nothing
in that run had opened the file the claim was about.
`crack.sources.events_anchors.measure_mbr_reproduction` now opens
`data/cache/dgec_mbr_monthly.csv` on every run, online and offline; a
disagreement sets the entry to `status: failed`, puts the disagreement in its
note and raises, so the run exits non zero. **A manifest must not assert a check
that was not run.**

The two private caches are outside all of this, because they are outside the
repository. An invalid private cache now marks its manifest entry `failed`
instead of leaving it reading `ok`, which is the most a run can honestly say
about a file it will not revalidate into the manifest.
