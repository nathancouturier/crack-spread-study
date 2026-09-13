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
| 3, decomposition | `yield[p] * crack[p]` per product, with a residual line | the yields are in the methodology note and are recorded in `config`; the arithmetic is Gate 2 |
| 4, observed yields | NWE yields from JODI output over intake | the three JODI caches are built; the ratio is Gate 2 |

### 2.3 Run economics

```
gas_usd_mmbtu    = ttf_eur_mwh * eurusd / MMBTU_PER_MWH
gas_cost         = gas_intensity_mmbtu_per_bbl * gas_usd_mmbtu
margin_after_gas = margin_gross - gas_cost - other_variable_cost
headroom         = margin_after_gas - run_cut_threshold
```

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

**Gate 3, the analysis.** No regression has been run. There is no utilisation
response, no run cut threshold, no horse race between the raw gasoil crack, the
official margin and the margin after gas, no instrument, and no 2026 residual
test. Any number in those categories that appears anywhere before Gate 3 is a
bug.

**Gate 4 and Gate 5, the site.** There is no `index.html`, no CSS and no
JavaScript, and there should not be: SPEC.md section 10 forbids UI work before
the data and the engine are approved.

---

## 8. Deviations from SPEC.md, on the record

Two, both measured rather than argued, both flagged for the owner.

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
