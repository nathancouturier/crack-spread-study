"""Constants, conversion factors, averaging rules and the source registry.

SPEC.md section 4.1: "Cite the page next to each constant in config.py. Never
guess a factor." This module is where that promise is kept. Nothing here fetches
anything and almost nothing here computes anything. It holds the numbers and,
next to every one of them, where the number came from and what it may and may
not be used for.

Read this before you believe any output of this project
-------------------------------------------------------
Three of the numbers below are conventions, three are measurements, and the
difference matters more in this study than in most:

    BBL_PER_T_GASOIL, BBL_PER_T_GASOLINE   contract conventions. They are the
                                           divisors ICE uses in its crack
                                           contracts. They are not measurements
                                           of the density of any particular
                                           barrel, and the study says so.
    MMBTU_PER_MWH                          a unit definition, exact to the
                                           digits given.
    DGEC_BBL_PER_T_BRENT_NOTE,             two factors, both DGEC's, used in two
    DGEC_BBL_PER_T_BRENT_MARGIN            different places. Using one where the
                                           other belongs is a silent error of
                                           about 0.7 percent on the Brent leg.
    GAS_INTENSITY_MMBTU_PER_BBL            a derived US figure, reported with
                                           its whole derivation and its two
                                           neighbours, and presented as an upper
                                           end default for Europe.
    MONTHLY_MEAN_*                         an averaging rule, fixed here because
                                           leaving it to a library default moves
                                           the answer by up to 1.10 $/bbl.

Where the recon reports are cited
----------------------------------
Citations of the form "recon 02 section 5.4" point at the Gate 1 research
reports under data/private/recon/, which are gitignored and are not part of the
published repository. Every one of them also names the primary document it read,
and the primary document is the citation that matters. The recon reference is
there so the next person can find the working rather than repeat it.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

__all__ = [
    "BBL_PER_T_GASOIL",
    "BBL_PER_T_GASOLINE",
    "PRODUCT_BBL_PER_T",
    "DGEC_SLATE_LINE",
    "ICE_SPEC_RETRIEVED",
    "BBL_PER_T_JET",
    "BBL_PER_T_HEATING_OIL",
    "BBL_PER_T_FUEL_OIL_1PCT",
    "DGEC_NOTE_PRODUCT_BBL_PER_T",
    "DGEC_NOTE_SLATE_LINE",
    "MMBTU_PER_MWH",
    "DGEC_BBL_PER_T_BRENT_NOTE",
    "DGEC_BBL_PER_T_BRENT_MARGIN",
    "DGEC_MASS_YIELDS",
    "DGEC_METHOD_EDITION",
    "DGEC_METHOD_URL",
    "DGEC_METHOD_REVISED_YEAR",
    "DGEC_METHOD_ANNEX_IN_FORCE_FROM",
    "DGEC_SULPHUR_PRICE_USD_T",
    "DGEC_INSURANCE_AND_LOSS_RATE",
    "DGEC_PUBLISHED_METHOD_INPUTS",
    "DGEC_UNPUBLISHED_METHOD_INPUTS",
    "REPLICATION_BAR_USD_BBL",
    "PERCENTILE_WINDOW_YEARS",
    "PERCENTILE_WINDOW_MONTHS",
    "ROLLING_YIELD_WINDOW_MONTHS",
    "YIELD_BASIS_CRUDE_INTAKE",
    "YIELD_BASIS_TOTAL_FEED",
    "YIELD_BASIS_NORMALISED",
    "YIELD_BASES",
    "YIELD_BASIS_NOTES",
    "GAS_INTENSITY_MMBTU_PER_BBL",
    "GAS_INTENSITY_FUEL_ONLY_MMBTU_PER_BBL",
    "GAS_INTENSITY_GROSS_INPUT_MMBTU_PER_BBL",
    "GAS_INTENSITY_BAND",
    "EI_BCF_NG_PER_MILLION_TONNES_LNG",
    "GAS_MMBTU_PER_TONNE",
    "DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL",
    "MBR_IS_NET_OF_GAS",
    "MBR_GAS_BASIS_NOTE",
    "YIELD_WINDOW_MONTHS",
    "OTHER_VARIABLE_COST_USD_BBL",
    "EIA_REFINERY_FUEL_GAS_MMCF_2023",
    "EIA_HYDROGEN_FEEDSTOCK_GAS_MMCF_2023",
    "EIA_GAS_HEAT_CONTENT_BTU_PER_CF_2023",
    "EIA_CRUDE_INPUTS_THOUSAND_BBL_2023",
    "EIA_RESIDUAL_FUEL_OIL_MMBTU_PER_BBL",
    "SP_GAS_VERSUS_FUEL_OIL_GAP_USD_BBL_2022_10",
    "MONTHLY_MEAN_RULE",
    "MONTHLY_MEAN_MIN_OBSERVATIONS",
    "BRENT_CROSS_CHECK_TOLERANCE_USD_BBL",
    "BRENT_CROSS_CHECK_MIN_PASS_SHARE",
    "monthly_mean",
    "BOUNDS_PRODUCT_USD_T",
    "BOUNDS_PRODUCT_USD_BBL",
    "BOUNDS_BRENT_USD_BBL",
    "BOUNDS_CRACK_USD_BBL",
    "BOUNDS_INTAKE_KB_D",
    "BOUNDS_MARGIN_USD_BBL",
    "BOUNDS_EURUSD",
    "BOUNDS_TTF_EUR_MWH",
    "BOUNDS_GAS_USD_MMBTU",
    "FREQUENCIES",
    "METHODS",
    "Source",
    "SOURCES",
    "source",
    "committable_series",
    "uncommittable_series",
]


# ---------------------------------------------------------------------------
# SPEC.md section 4.1, conversion factors
# ---------------------------------------------------------------------------

# Barrels per tonne of ICE Low Sulphur Gasoil, the divisor in the ICE gasoil
# crack contract.
#
# Source: ICE Low Sulphur Gasoil Futures vs Brent Crude Futures crack contract
# specification, https://www.ice.com/products/6753331, listed in SPEC.md
# section 5.6. SPEC.md section 4.1 fixes the same value.
#
# What it is not: a density. A tonne of any particular gasoil cargo is not
# exactly 7.45 barrels. This is the number the crack contract divides by, so it
# is the number a crack quoted against that contract has to use, and every crack
# this study prints is quoted on that convention and labelled as such.
#
# Corroboration, over the WHOLE overlap rather than a sample of it. The DGEC
# weekly Gazole quotations, monthly averaged, against the OPEC MOMR Rotterdam
# gasoil row, two independent sources, for all 44 months where both exist,
# 2022-07 to 2026-02:
#
#     n = 44 months   implied bbl/t   min 7.3080 in 2023-07   max 7.8191 in 2022-12
#                                     mean 7.5285             median 7.5313
#
# 7.45 sits inside that spread and close to the middle of it, which is the
# expected result and is not evidence for changing it. The spread itself is
# real: a tonne of gasoil is not a fixed number of barrels and the two sources
# assess different specifications at the same hub.
#
# THIS COMMENT USED TO DESCRIBE SIX MONTHS AND A RANGE OF 7.31 TO 7.65. Those
# six values are all real and all reproduce, but they were a subset presented as
# the whole overlap, and the Gate 1 self audit, finding 3.1, recomputed the full
# 44 months from the committed caches. docs/open-questions.md section 12 already
# carried the correct table. config.py is where SPEC.md section 4.1 sends a
# reader to check a constant, so it carries the full sample now.
BBL_PER_T_GASOIL = 7.45

# Barrels per tonne of Eurobob gasoline, the divisor in the ICE Eurobob crack
# contract.
#
# Source: ICE Eurobob vs Brent Crude Futures crack contract specification,
# https://www.ice.com/products/6753285, listed in SPEC.md section 5.6. SPEC.md
# section 4.1 fixes the same value.
#
# THE GAP, AND WHY IT IS NOT TUNED AWAY. The reconstructed DGEC Eurosuper
# quotations in $/t, monthly averaged, against the OPEC MOMR premium gasoline
# quotations in $/bbl, over ALL 44 months where both exist, 2022-07 to 2026-02,
# recomputed from the committed caches:
#
#     n = 44 months   implied bbl/t   min 6.9370 in 2023-07   max 8.3333 in 2025-02
#                                     mean 7.7185             median 7.8429
#
# Read that carefully, because it says two things at once and only one of them
# is comfortable. The CENTRE of the distribution is nowhere near 8.33: applying
# 8.33 leaves the MOMR row 8.82 $/bbl above DGEC's Eurosuper on average, far
# larger than any plausible RON 95 to RON 98 spread, and the gasoline crack
# disagreement between the two sources reaches 13 $/bbl. The MAXIMUM, however,
# is 8.3333 in February 2025, which is the ICE contract factor to three
# decimals, so the earlier claim that the implied factor is "never 8.33" was
# false by this project's own measurement and has been removed here and from
# docs/open-questions.md section 23.
#
# Two causes sit behind the spread and this project can separate neither. The
# two sources quote different products, DGEC's Eurosuper being finished premium
# gasoline while the MOMR row is premium unleaded assessed by Argus, and the
# real density of a gasoline cargo moves with its blend and with the season.
#
# 8.33 stays, because it is the contract factor and because picking a factor
# that closes an 8.82 $/bbl mean gap between two differently defined products is
# exactly the tuning SPEC.md section 6.6 forbids. The gap is carried as a stated
# limitation on the Method view, with both series shown side by side under their
# own labels, which is SPEC.md section 4.2's instruction not to relabel DGEC's
# products as futures.
#
# THIS COMMENT USED TO DESCRIBE SIX MONTHS AND A RANGE OF 7.42 TO 8.15. Those
# six values are real and reproduce individually, but they were a subset
# presented as the whole overlap and they hid both of the findings above. Gate 1
# self audit, finding 3.1.
BBL_PER_T_GASOLINE = 8.33

# The one table where a product name meets its barrels per tonne factor.
#
# THIS EXISTS BECAUSE OF THE GATE 2 SELF AUDIT, FINDING 2. The two constants
# above were guarded by tests and their USE was not: the audit put
# BBL_PER_T_GASOIL on the gasoline leg of the decomposition yield and all 756
# tests and the parity validator stayed green while the October 2022 gasoline
# contribution moved by 0.61 $/bbl. SPEC.md section 9's Units row calls a wrong
# conversion factor "the most common error in this study", and a constant that
# is right in config.py and wrong at the call site is exactly that error.
#
# So no call site types a factor any more. Every one of them looks the factor up
# by the SAME key that names the product it is converting, here, and a wrong
# factor now requires editing this mapping, which
# tests/test_units.py::test_every_product_factor_is_the_one_spec_section_4_1_fixes
# asserts line by line.
PRODUCT_BBL_PER_T: Mapping[str, float] = MappingProxyType(
    {
        "gasoil": BBL_PER_T_GASOIL,
        "gasoline": BBL_PER_T_GASOLINE,
    }
)

# Which line of DGEC's own slate each of this study's two products is, so that
# the mass yield and the conversion factor are picked up by one key rather than
# by two hand typed lookups that can disagree. DGEC's "gazole" is road diesel
# and its "eurobob" is the blendstock the method prices, SPEC.md section 4.2.
DGEC_SLATE_LINE: Mapping[str, str] = MappingProxyType(
    {
        "gasoil": "gazole",
        "gasoline": "eurobob",
    }
)

# ---------------------------------------------------------------------------
# Three more barrels per tonne factors, cited, for the ministry's own monthly
# quotations. Gate 4.
# ---------------------------------------------------------------------------
#
# WHY THESE EXIST NOW. Until Gate 4 the only month the margin could be split by
# product was a month in the OPEC MOMR table, which stops at 2026-02, and this
# file held no factor for any product but gasoil and gasoline. The Gate 4 brief
# found that DGEC's weekly note of 4 September 2026 prints FINAL August 2026
# monthly averages for five products and Brent date, in $/t
# (data/cache/dgec_note_printed_monthly.csv), so the latest margin month can be
# split from the same ministry, the same month and the same basis as the
# official margin. Three of those five products need a factor, and SPEC.md
# section 4.1 allows one only from the DGEC methodology note or an ICE contract
# specification.
#
# THE METHODOLOGY NOTE WAS READ FIRST AND HOLDS NONE. Its only conversion factor
# is the Brent equivalence of 7.55 bbl/t on page 4, DGEC_BBL_PER_T_BRENT_MARGIN
# below. Its table 1 is mass yields and its product quotations are in $/t, and
# it never states a factor for a product. Read in full on 2026-09-16 from
# data/private/dgec_notes/mbr_method.pdf.
#
# SO ALL THREE ARE ICE CONTRACT CONVERSION FACTORS, the same kind of citation as
# BBL_PER_T_GASOIL and BBL_PER_T_GASOLINE, each the "Conversion factor: 1 metric
# tonne = N barrels" line of the ICE Futures Europe contract specification,
# downloaded as the product guide PDF (https://www.ice.com/api/productguide/spec/
# <id>/pdf) on 2026-09-16. The same download of 6753331 and 6753285 prints 7.45
# and 8.33, which is the check that the page being read is the page SPEC.md
# section 5.6 cites.
#
# WHAT A CONTRACT FACTOR IS AND IS NOT, said once for all three. It is the
# convention an exchange settles a crack on, not a measured density of the
# cargo the ministry quotes. DGEC's "Carbureacteur", "Fioul domestique" and
# "Fioul lourd TBTS" are Reuters Rotterdam assessments, and the ICE contracts
# settle on Platts assessments of the nearest product: jet CIF NWE cargoes,
# gasoil 0.1 percent FOB ARA barges, fuel oil 1 percent FOB NWE cargoes. The
# product label on the page stays the ministry's, SPEC.md section 4.2.
#
# ICE_SPEC_RETRIEVED records the date the three PDFs were read.
ICE_SPEC_RETRIEVED = "2026-09-16"

#: Jet. ICE Futures Europe, "Jet Fuel Crack, Jet CIF NWE Cargoes vs Brent 1st
#: Line Future", contract symbol JNB, https://www.ice.com/products/6753303,
#: "Conversion factor: 1 metric tonne = 7.88 barrels".
BBL_PER_T_JET = 7.88

#: Fioul domestique, heating oil at 0.1 percent sulphur. ICE Futures Europe,
#: "Gasoil Crack, Gasoil 0.1% FOB ARA Barges (Platts) vs Brent 1st Line Future
#: (in MTs)", https://www.ice.com/products/6753295, "conversion factor: 1 metric
#: tonne = 7.45 barrels". The same number as BBL_PER_T_GASOIL and a separate
#: constant, because it is cited from a different contract and would have to
#: move on its own if ICE ever changed one of the two.
BBL_PER_T_HEATING_OIL = 7.45

#: Fioul lourd, the method's "Fioul lourd 1% S" and the note's "Fioul lourd TBTS
#: (< 1%)". ICE Futures Europe, "Fuel Oil Crack, Fuel Oil 1% FOB NWE Cargoes vs
#: Brent 1st Line Future", https://www.ice.com/products/6753289, "Conversion
#: factor: 1 metric tonne = 6.35 barrels". Fuel oil is dense, so fewer barrels
#: to the tonne than crude, and its crack against Brent is normally negative.
BBL_PER_T_FUEL_OIL_1PCT = 6.35

#: Every product the ministry's printed monthly quotations let this study crack,
#: keyed by this study's product name, with its cited factor. A SEPARATE MAPPING
#: FROM PRODUCT_BBL_PER_T ON PURPOSE: that one drives the OPEC decomposition and
#: the engine parity fixture, which cover two products and must not move because
#: a third source arrived. The gasoil and gasoline lines are the same constants.
DGEC_NOTE_PRODUCT_BBL_PER_T: Mapping[str, float] = MappingProxyType(
    {
        "gasoil": BBL_PER_T_GASOIL,
        "gasoline": BBL_PER_T_GASOLINE,
        "jet": BBL_PER_T_JET,
        "heating_oil": BBL_PER_T_HEATING_OIL,
        "fuel_oil_1pct": BBL_PER_T_FUEL_OIL_1PCT,
    }
)

#: The DGEC slate line each of those products is priced against, by one key, for
#: the same reason as DGEC_SLATE_LINE. The gasoline line carries the approximation
#: DGEC_SLATE_LINE already states: the method prices EuroBOB and the note prints
#: Eurosuper.
DGEC_NOTE_SLATE_LINE: Mapping[str, str] = MappingProxyType(
    {
        "gasoil": "gazole",
        "gasoline": "eurobob",
        "jet": "carbureacteur",
        "heating_oil": "fod",
        "fuel_oil_1pct": "fioul_lourd_1pct",
    }
)

# MMBtu per MWh. A unit definition, SPEC.md section 4.1, used in the gas chain
# of SPEC.md section 4.4: gas_usd_mmbtu = ttf_eur_mwh * eurusd / MMBTU_PER_MWH.
# 1 MWh = 3.6e9 J and 1 MMBtu(IT) = 1.05505585262e9 J, so the exact ratio is
# 3.41214163... and the value below is that rounded to seven figures, which is
# what SPEC.md fixes.
MMBTU_PER_MWH = 3.412142

# ---------------------------------------------------------------------------
# The two DGEC Brent factors. Both of them, because there are two.
# ---------------------------------------------------------------------------
#
# Recon 02 section 5.4 found that DGEC uses two different barrels per tonne
# figures for Brent, in two different places, and that neither is 7.45. Using
# one where the other belongs is a 0.67 percent error on the crude leg, which is
# about 0.56 $/bbl at a Brent of 84, and it would be silent.

# The factor the weekly note uses to print Brent date in its $/t quotation
# table. It is not stated in the note. Recon 02 section 4.3 recovered it by
# dividing the note's printed $/t figure by the $/bbl figure DGEC publishes for
# the same month in its own Brent history workbook, on five month pairs, and got
# 7.5 exactly each time. Recon 04 section 7.4 reproduced it independently from
# the July 2026 anchor in SPEC.md section 5.5: 628 $/t divided by the FRED
# monthly mean of 83.7587 $/bbl gives 7.4977.
#
# USE IT FOR: converting the note's Brent date $/t column back to $/bbl, which
# is what crack_gasoil and crack_gasoline need when their product leg comes from
# the same table. Any other use is wrong.
#
# It is a measurement of DGEC's own arithmetic, not a published factor, so it
# carries a small doubt: 628 is printed to the whole dollar. Recon 04 section 7.4
# is explicit that this is a sanity check on the reading and not a substitute for
# a published number.
DGEC_BBL_PER_T_BRENT_NOTE = 7.5

# The factor stated inside the MBR methodology note, page 4, verbatim:
# "Le prix du Brent $/bbl (CAF) est calcule sur la base d'une equivalence de
# 7,55 bbl/t."
#
# Source: Mode de calcul de la marge brute de raffinage sur brent,
# https://www.ecologie.gouv.fr/sites/default/files/documents/Mode%20de%20calcul%20de%20la%20marge%20brute%20de%20raffinage%20sur%20brent.pdf
# edition of 1 August 2019, 4 pages. Recon 02 section 5.4.
#
# USE IT FOR: the CAF Brent price inside a replication of the MBR, SPEC.md
# section 4.3 layer 2, and nothing else. Note that recon 02 section 5.6 found
# the replication cannot in fact be completed from published data, because five
# of the ten product quotations plus the gas cost and the freight cost are not
# published, so this factor may end up used only in the partial attribution.
DGEC_BBL_PER_T_BRENT_MARGIN = 7.55


# ---------------------------------------------------------------------------
# The MBR method itself. SPEC.md section 4.3 layer 1: "Read the note, record its
# product slate, yields and conversion factors in config.py".
# ---------------------------------------------------------------------------
#
# Source for everything in this block: "Mode de calcul de la marge brute de
# raffinage sur brent", DGEC, PDF metadata title "2019.08.01 Mode de calcul de
# la marge brute de raffinage sur brent-1", 4 pages, read in full at recon 02
# section 5. SPEC.md section 5.6 links it.

#: The edition of the methodology note these constants were read from.
DGEC_METHOD_EDITION = "2019-08-01"

DGEC_METHOD_URL = (
    "https://www.ecologie.gouv.fr/sites/default/files/documents/"
    "Mode%20de%20calcul%20de%20la%20marge%20brute%20de%20raffinage%20sur%20brent.pdf"
)

#: The note says the method was revised with IFPEN in 2014 and that the annex
#: method applies from 1 January 2016, with 2014 and 2015 recomputed
#: retroactively for continuity. Recon 02 section 5.1 quotes all three
#: sentences.
#:
#: THE CONSEQUENCE SPEC.md SECTION 4.3 DOES NOT ANTICIPATE, and it is a relief
#: rather than a problem: the published MBR file starts in January 2015, which
#: is inside the recomputed window, so the ENTIRE series this project can reach
#: is on one method and contains no structural break. There is no break date to
#: mark on a chart because no chart drawn from public data spans it. The Method
#: view says so instead, and records that the pre 2014 method is not comparable
#: and its data is not published anyway.
DGEC_METHOD_REVISED_YEAR = 2014
DGEC_METHOD_ANNEX_IN_FORCE_FROM = "2016-01-01"

#: Table 1 of the methodology note, "Rendements massiques", verbatim and
#: complete, as MASS yields: tonnes of each line per tonne of Brent.
#:
#: READ THE UNITS TWICE. These are mass yields on a tonne of crude. SPEC.md
#: section 4.5 writes contribution[p] = yield[p] * crack[p] with the crack in
#: $/bbl, which needs a VOLUMETRIC yield, barrels of product per barrel of
#: crude. The two differ by the ratio of the two conversion factors, and for
#: gasoil that is 7.45 / 7.55, about 1.3 percent. crack.engine.
#: mass_yield_to_volume_yield does that conversion and demands both factors, so
#: a mass yield can never be multiplied by a $/bbl crack by accident. Where this
#: project holds no cited factor for a product, that product is not converted
#: and its yield stays on the residual line with its name attached, which is
#: SPEC.md section 4.3 layer 3's instruction.
#:
#: Brent at 100 percent and natural gas at 1.0 percent are INPUTS, not outputs,
#: and they are kept in the mapping because dropping them would hide two of the
#: method's own lines. Outputs sum to 94.5 percent, plus 6.6 percent internal
#: fuel and losses is 101.1 percent, less the 1.0 percent of purchased gas is
#: 100.1 percent, the residual being the note's own rounding. Recon 02 section
#: 5.2 reproduces the table.
DGEC_MASS_YIELDS: Mapping[str, float] = MappingProxyType(
    {
        "brent": 1.000,  # input
        "gaz_naturel": 0.010,  # input, purchased
        "propane": 0.017,
        "butane": 0.012,
        "naphta": 0.082,
        "eurobob": 0.120,
        "essence_export": 0.119,
        "carbureacteur": 0.083,
        "gazole": 0.340,
        "fod": 0.082,
        "fioul_lourd_1pct": 0.088,
        "soufre": 0.002,
        "combustible_interne_et_pertes": 0.066,
    }
)

#: The note fixes the sulphur price rather than quoting it: "Soufre (estime a
#: 100 $/t)". Recon 02 section 5.3. It is the one unpublished input the method
#: itself supplies, and 0.2 percent of a tonne at 100 $/t is 0.20 $/t of crude,
#: about 0.026 $/bbl, so it changes nothing and is carried for completeness.
DGEC_SULPHUR_PRICE_USD_T = 100.0

#: "les couts d'assurance et les pertes (evalues forfaitairement a 0,3% du cours
#: du Brent date et du cout du fret)". Recon 02 section 5.5, page 4 verbatim.
DGEC_INSURANCE_AND_LOSS_RATE = 0.003

#: The method inputs that ARE published, so a replication may use them.
#: Recon 02 section 5.6 crossed the note's input list against what the weekly
#: note actually prints.
DGEC_PUBLISHED_METHOD_INPUTS: Sequence[str] = (
    "brent_date",
    "gazole",
    "fod",
    "carbureacteur",
    "fioul_lourd_1pct",
    "soufre",
    "eur_usd",
)

#: The method inputs that are NOT published anywhere this project can reach, and
#: therefore the reason SPEC.md section 4.3 layer 2's 0.50 $/bbl bar cannot be
#: met. Recon 02 section 5.6, each line checked against the note's own tables.
#:
#: Every one of these is named on the page rather than summarised, because
#: SPEC.md section 4.3 layer 2 says "If an input is not published, name it and
#: fall back to the official series", and an unnamed gap is indistinguishable
#: from a modelling failure.
DGEC_UNPUBLISHED_METHOD_INPUTS: Sequence[str] = (
    "eurobob",  # the note prints Eurosuper, finished gasoline, a different product
    "essence_export",  # defined as 50 percent naphta CAF plus 50 percent eurosuper FAB
    "naphta",
    "propane",
    "butane",
    "peg_nord_gas_day_ahead",  # the gas purchase price, EUR/MWh
    "grtgaz_transport_tariff",  # published as a tariff, not in these documents
    "aframax_freight_sullom_voe_le_havre",  # Reuters commercial data
)

#: SPEC.md section 4.3 layer 2 and section 9: "agreement within 0.50 $/bbl in
#: every complete month is the Gate 2 bar".
REPLICATION_BAR_USD_BBL = 0.50


# ---------------------------------------------------------------------------
# SPEC.md section 4.5, the ten year percentile
# ---------------------------------------------------------------------------

#: "percentile_10y = rank of margin_after_gas within its trailing ten years".
#: Ten years of monthly observations is 120 months, and the window is defined in
#: months rather than by a date offset so that the rank does not quietly change
#: length in a leap year.
PERCENTILE_WINDOW_YEARS = 10
PERCENTILE_WINDOW_MONTHS = 120

#: SPEC.md section 4.3 layer 4's other window: "Compute NWE yields from JODI
#: refinery output by product over refinery intake (12-month rolling, BE, DE,
#: FR, NL, UK)". In months, for the same reason as the one above, and a constant
#: for a duller reason: it was a bare 12 in two signatures in crack.series while
#: its sibling, the ten year percentile window, was a named constant with a
#: docstring. Gate 2 self audit, finding 13. The spec fixes both windows and
#: both should be the same kind of thing.
#:
#: It is a rolling mean of the numerator and of the denominator separately, not
#: the mean of twelve monthly ratios. crack.series.jodi_yields says why.
ROLLING_YIELD_WINDOW_MONTHS = 12


# ---------------------------------------------------------------------------
# SPEC.md section 4.3 layer 4, the observed yield denominator. A real choice.
# ---------------------------------------------------------------------------
#
# Recon 03 section 1.8 measured it and refused to pick: "Do not quietly pick
# one. This is a real modelling choice and the spec has not made it." So both
# bases exist here, both are computed, and the site shows both.

#: JODI REFINOBS on CRUDEOIL. Crude only in the denominator, gross output from
#: all feed in the numerator, so the ratio is 1.13 to 1.16 and the product
#: yields do not sum to 1. Starts 2002-01.
YIELD_BASIS_CRUDE_INTAKE = "crude_intake"

#: JODI REFINOBS on TOTCRUDE. Total refinery feed in the denominator, so the
#: ratio is 1.01 to 1.03, which is volume gain and is physically right. Starts
#: 2009-01, which is the cost.
YIELD_BASIS_TOTAL_FEED = "total_feed"

#: Crude intake in the denominator, then the yield vector scaled to sum to 1.
#: Labelled a share of output rather than a yield on crude, because that is what
#: it is.
YIELD_BASIS_NORMALISED = "normalised_share"

YIELD_BASES = (
    YIELD_BASIS_CRUDE_INTAKE,
    YIELD_BASIS_TOTAL_FEED,
    YIELD_BASIS_NORMALISED,
)

#: What each basis means, in the words the Method view uses. Kept next to the
#: names so the label and the arithmetic cannot drift apart.
YIELD_BASIS_NOTES: Mapping[str, str] = MappingProxyType(
    {
        YIELD_BASIS_CRUDE_INTAKE: (
            "JODI refinery gross output by product over JODI refinery crude "
            "intake, REFGROUT over REFINOBS CRUDEOIL. The numerator is output "
            "from all refinery feed including NGL, other feedstocks and "
            "backflows, and the denominator is crude alone, so the lines sum to "
            "about 1.13 to 1.16 rather than to 1. Using these directly as "
            "yield[p] inflates a decomposed margin by about 15 percent, which is "
            "why the number is shown next to the sum that gives it away. Covers "
            "2002-01 onward. Recon 03 section 1.8."
        ),
        YIELD_BASIS_TOTAL_FEED: (
            "The same output over JODI total refinery feed, REFINOBS TOTCRUDE. "
            "The lines sum to about 1.01 to 1.03, which is volume gain and is "
            "physically right. Covers 2009-01 onward only, which is the whole "
            "cost of this basis and the reason it is not simply the default. "
            "Recon 03 section 1.8."
        ),
        YIELD_BASIS_NORMALISED: (
            "Crude intake in the denominator, then every line divided by the sum "
            "so the vector adds to 1. It is a share of output, not a yield on "
            "crude, and it must be labelled that way wherever it appears. It "
            "keeps the 2002 start and loses the volume gain."
        ),
    }
)


# ---------------------------------------------------------------------------
# SPEC.md section 4.4, gas intensity. Derived, not typed.
# ---------------------------------------------------------------------------
#
# Every input below is an EIA figure for the United States in 2023, and every
# one of them is quoted with the table it came from. The derivation is one pass
# with these numbers and nothing in it was chosen to land anywhere. Recon 03
# section 3.6 shows every step.

#: Natural gas consumed as fuel at US refineries, 2023, million cubic feet.
#: EIA Refinery Capacity Report, table 10a, https://www.eia.gov/petroleum/refinerycapacity/
EIA_REFINERY_FUEL_GAS_MMCF_2023 = 1_021_246.0

#: Natural gas used as hydrogen feedstock at US refineries, 2023, million cubic
#: feet. EIA Refinery Capacity Report, table 10b, same report.
EIA_HYDROGEN_FEEDSTOCK_GAS_MMCF_2023 = 172_313.0

#: Heat content of natural gas consumed, US, 2023, Btu per cubic foot. EIA
#: Natural Gas Navigator, series NG.NG_CONS_HEAT_A_EPG0_VGTH_BTUCF_A.A.
EIA_GAS_HEAT_CONTENT_BTU_PER_CF_2023 = 1_036.0

#: Refinery and blender net input of crude oil, US, 2023, thousand barrels. EIA
#: series MCRRIUS1, https://www.eia.gov/dnav/pet/pet_pnp_inpt_dc_nus_mbbl_a.htm
EIA_CRUDE_INPUTS_THOUSAND_BBL_2023 = 5_827_889.0

# The derivation, recon 03 section 3.6, written out so nobody has to trust the
# constant below:
#
#   fuel gas plus hydrogen feedstock   1,021,246 + 172,313 = 1,193,559 MMcf
#   as cubic feet                      1,193,559 x 1e6     = 1.193559e12 cf
#   times the heat content             x 1,036 Btu/cf      = 1.236527124e15 Btu
#   as MMBtu                           / 1e6               = 1,236,527,124 MMBtu
#   crude inputs as barrels            5,827,889 x 1e3     = 5,827,889,000 bbl
#   intensity                          = 0.2121741035... MMBtu per barrel
#
# SPEC.md section 4.4 expects about 0.2 and says to stop and show the working
# outside 0.12 to 0.30. 0.21217 is comfortably inside, so there is no stop
# condition and nothing to tune.
#
# IT IS A US FIGURE AND THEREFORE AN UPPER END DEFAULT FOR EUROPE. European
# refiners burn proportionally more of their own still gas and buy proportionally
# less pipeline gas, so a European refinery's purchased gas intensity is more
# likely below this than above it. SPEC.md section 4.4 requires it to be
# presented as an upper end default, editable in the Model view and labelled.
GAS_INTENSITY_MMBTU_PER_BBL = 0.21217

#: The same derivation with the hydrogen feedstock dropped, fuel gas only.
#: Reported for honesty, never used. Recon 03 section 3.6. Including hydrogen
#: feedstock moves the answer by about 15 percent and SPEC.md section 4.4 says to
#: include it, which is right, because European refiners buy that gas too.
GAS_INTENSITY_FUEL_ONLY_MMBTU_PER_BBL = 0.1815

#: The same derivation with the denominator switched to gross input to
#: atmospheric distillation units, 16,502 kb/d times 365 = 6,023,230,000 barrels.
#: Reported for honesty, never used. Recon 03 section 3.6. The denominator choice
#: moves the answer by about 3 percent.
GAS_INTENSITY_GROSS_INPUT_MMBTU_PER_BBL = 0.2053

#: SPEC.md section 4.4 and section 9: the derived intensity must land inside
#: this band or the pipeline stops and shows its working. tests/test_units.py
#: asserts it at Gate 2.
GAS_INTENSITY_BAND = (0.12, 0.30)

#: Approximate heat content of residual fuel oil, million Btu per barrel, gross.
#: EIA Monthly Energy Review, Table A1 "Approximate Heat Content of Petroleum and
#: Biofuels", "(Million Btu per Barrel, Except as Noted)", row "Residual Fuel Oil
#: 6.287", read from https://www.eia.gov/totalenergy/data/monthly/pdf/sec12_2.pdf
#: on 2026-09-13. The table's own note says the values are GROSS heat contents.
#:
#: USE IT FOR: the SPEC.md section 4.4 triangulation, and nothing else. That
#: paragraph asks for the October 2022 gas cost computed "against a refinery
#: fired on fuel oil", which needs the fuel oil price in the same energy units as
#: the gas price, and this is the only factor that converts one to the other.
#: It is a US average for a heavy residual grade, so it is approximate for a
#: Rotterdam barge, and the triangulation is a sanity check on an order of
#: magnitude rather than a number the study depends on. Nothing in the margin
#: engine reads it.
EIA_RESIDUAL_FUEL_OIL_MMBTU_PER_BBL = 6.287

#: S&P Global reported that gas fired refiners were earning about 7 $/bbl less
#: than fuel oil fired ones in mid October 2022, in the refinery margin tracker of
#: 17 October 2022, which SPEC.md section 5.6 links. SPEC.md section 4.4 asks for
#: this study's own figure to be reported NEXT TO it, expecting the same order of
#: magnitude, and says to report whatever comes out. It is an order of magnitude
#: reference and never a target: SPEC.md section 6.6 forbids tuning toward it.
SP_GAS_VERSUS_FUEL_OIL_GAP_USD_BBL_2022_10 = 7.0

# ---------------------------------------------------------------------------
# THE MBR IS ALREADY NET OF PURCHASED NATURAL GAS. The Gate 2 self audit,
# finding 1, and the primary source settles it.
# ---------------------------------------------------------------------------
#
# "Mode de calcul de la marge brute de raffinage sur Brent", DGEC, section 3
# "Mode de calcul de la marge", verbatim:
#
#     "Pour calculer la marge de raffinage sur Brent, on soustrait aux
#      recettes : les couts d'achat du Brent date FAB et du gaz naturel CAF ;
#      le cout du fret petrolier ; les couts d'assurance et les pertes"
#
# The same note's table 1 carries "Gaz naturel 1,0%" as an INPUT beside
# "Combustible interne et pertes 6,6%", and says the refinery "procede a des
# achats de gaz naturel pour completer la couverture de ses besoins en
# combustible interne et en hydrogene". Its point 4 says the margin is gross of
# fixed and variable costs "autres que ceux energetiques", that is, gross of
# everything EXCEPT energy, and the indicator's own name is "marge de raffinage
# sur couts energetiques".
#
# SO THE PUBLISHED MBR IS ALREADY A MARGIN AFTER GAS. SPEC.md section 4.4's
# margin_after_gas = margin_gross - gas_cost - other_variable_cost assumes a
# margin_gross that is gross of gas. That assumption is true of a margin this
# study builds from cracks and yields and FALSE of DGEC's MBR, and subtracting
# a gas cost from the MBR charges the same barrel for gas twice. Until Gate 2 it
# did: the correction is worth 0.34 to 14.86 $/bbl by month, 4.48 $/bbl in the
# latest month and 8.28 $/bbl in October 2022.
#
# crack.engine carries the basis on the margin itself, so the wrong combination
# raises instead of returning a number. docs/methodology.md section 2.3 writes
# the reading and the size of the correction down, section 4.2 derives DGEC's own
# embedded intensity, and docs/open-questions.md section 33 carries what is still
# open about it.
MBR_IS_NET_OF_GAS = True

MBR_GAS_BASIS_NOTE = (
    "DGEC's published MBR is already net of the natural gas the method assumes "
    "the refinery buys: section 3 of the methodology note subtracts 'les couts "
    "d'achat du Brent date FAB et du gaz naturel CAF' from the product "
    "revenues, and table 1 carries natural gas at 1.0 percent of the tonne as "
    "an input. The indicator is named 'marge de raffinage sur couts "
    "energetiques' and its own note says it is gross of costs 'autres que ceux "
    "energetiques'. This study therefore does NOT subtract a gas cost from it. "
    "What it shows instead is the comparison: what DGEC's own embedded gas "
    "assumption costs at the month's gas price against what this study's EIA "
    "derived intensity would cost at the same price. SPEC.md section 4.4's "
    "subtraction applies to a gross margin this study builds itself, not to "
    "this one."
)

#: Billion cubic feet of natural gas per million tonnes of LNG. A volumetric
#: conversion, quoted with attribution from the Energy Institute Statistical
#: Review of World Energy 2026, sheet "Approximate conversion factors", the
#: natural gas and LNG table, row "1 million tonnes LNG", column "billion cubic
#: feet NG": 48.027940960947284.
#:
#: Quotation of one factor with attribution is what the review permits; see the
#: ei_refinery_capacity_annual licence note below for what it does not permit.
#: Nothing in the margin engine reads it. It exists for one purpose, sizing
#: DGEC's own gas assumption in the same units as this study's intensity, and
#: docs/methodology.md section 4.2 shows the arithmetic.
EI_BCF_NG_PER_MILLION_TONNES_LNG = 48.027940960947284

#: MMBtu per tonne of natural gas, GROSS, derived rather than typed:
#:
#:     48.027940960947284 bcf per Mt  x 1e9 cf per bcf / 1e6 t per Mt
#:         = 48,027.94 cubic feet per tonne
#:     x EIA_GAS_HEAT_CONTENT_BTU_PER_CF_2023 (1,036 Btu/cf, gross)
#:         = 49,756,947 Btu per tonne
#:     / 1e6 = 49.7569 MMBtu per tonne
#:
#: The EI table's own energy columns are NET heating values and this study's gas
#: intensity is built on EIA's GROSS heat content, so the EI energy column is
#: deliberately not used: the volume column is taken from EI and the heat
#: content from EIA, which keeps both sides of the comparison on one basis. The
#: two bases differ by about 10 percent and mixing them would put that 10
#: percent into the comparison.
GAS_MMBTU_PER_TONNE = (
    EI_BCF_NG_PER_MILLION_TONNES_LNG
    * 1_000.0
    * EIA_GAS_HEAT_CONTENT_BTU_PER_CF_2023
    / 1_000_000.0
)

#: The gas intensity DGEC's method already embeds in the published MBR, in this
#: study's units, so the two can be put next to each other:
#:
#:     0.010 tonnes of gas per tonne of crude      table 1 of the method note
#:     / 7.55 barrels per tonne of crude           the note's own factor
#:     x 49.7569 MMBtu per tonne of gas            above
#:     = 0.06590 MMBtu per barrel
#:
#: Against this study's 0.21217 MMBtu per barrel that is 31 percent. The two are
#: not the same measurement: DGEC's is a French linear programming model's
#: PURCHASED gas for a self sufficient refinery, and this study's is US refinery
#: purchased fuel gas plus hydrogen feedstock over crude inputs. The comparison
#: is reported as information, never subtracted from the other, and the Model
#: view of SPEC.md section 7.2 is where a reader moves the intensity and watches
#: the wedge move.
DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL = (
    DGEC_MASS_YIELDS["gaz_naturel"] * GAS_MMBTU_PER_TONNE / DGEC_BBL_PER_T_BRENT_MARGIN
)

#: SPEC.md section 4.3 layer 4's rolling window, in months. It was a bare 12 in
#: two signatures in crack.series while its sibling, the ten year percentile
#: window, was PERCENTILE_WINDOW_MONTHS with a docstring. Gate 2 self audit,
#: finding 13: one of the two spec windows was a config constant and the other a
#: literal, and they should be the same kind of thing.
YIELD_WINDOW_MONTHS = 12

#: SPEC.md section 4.4: other_variable_cost defaults to zero and is labelled.
#: Carbon costs are out of scope for this version and are listed as a limitation,
#: not folded silently into this line.
OTHER_VARIABLE_COST_USD_BBL = 0.0


# ---------------------------------------------------------------------------
# The monthly averaging rule. Fixed here, not left to a library default.
# ---------------------------------------------------------------------------
#
# SPEC.md section 5.5 asks for DGEC's Brent, converted with DGEC's own factor, to
# sit within 1.5 $/bbl of the monthly mean of FRED DCOILBRENTEU in at least 95
# percent of months. That test is only meaningful once "the monthly mean" is
# pinned down, and recon 04 section 7.2 measured three defensible readings of it
# over 2015-01 to 2026-08:
#
#   A  mean of the days FRED actually published a price
#   B  reindex to every business day, carry the last price forward, then mean
#   C  reindex to every calendar day, carry forward, then mean
#
#   A against B   max 1.0995 $/bbl, mean 0.0634, 29 of 140 months apart by 0.10
#   A against C   max 1.1533 $/bbl, mean 0.1699, 82 of 140 months apart by 0.10
#
# The choice alone moves the monthly mean by up to 1.10 $/bbl, which is 73 percent
# of the whole tolerance. In December 2018 or April 2026 it could by itself decide
# whether a month passes. That makes it a modelling decision, so it is made here
# once, in the open, rather than inherited from whatever a resample call happens
# to do.
#
# Method A is the rule, for two reasons. Filling a UK bank holiday with Friday's
# Brent invents a price on a day nobody traded, which SPEC.md section 2 rule 1
# forbids outright. And A is the closest honest match to what DGEC itself is
# doing, which is averaging its own daily quotations over the month. The two can
# never agree perfectly, because Brent date as assessed by Reuters is a different
# assessment from EIA Europe Brent spot and DGEC uses its own quotation days, so a
# residual of a few tens of cents is expected and is not a bug.
MONTHLY_MEAN_RULE = (
    "Arithmetic mean of the days the source actually published a price. "
    "Weekends do not appear in the source. A blank day is not an observation of "
    "a price, so it is excluded from the mean, never filled and never carried "
    "forward. A month with fewer than the declared minimum of published days is "
    "NaN rather than a thin mean, and the observation count travels with every "
    "monthly value so an outlier can be reported as 'this month failed on 17 "
    "days of data'."
)

#: The fewest published days a month must carry before its mean is usable.
#: Recon 04 section 7.3 recommends 15: it excludes nothing in the 2015 onward
#: sample, whose thinnest month is 2018-12 with 17 days, and it correctly
#: excludes the partial current month, which had 7 days when the recon ran.
MONTHLY_MEAN_MIN_OBSERVATIONS = 15

#: SPEC.md section 5.5, the cross check tolerance and the share of months that
#: must pass it.
BRENT_CROSS_CHECK_TOLERANCE_USD_BBL = 1.5
BRENT_CROSS_CHECK_MIN_PASS_SHARE = 0.95


def monthly_mean(
    dates,
    values,
    *,
    min_observations: int = MONTHLY_MEAN_MIN_OBSERVATIONS,
) -> pd.DataFrame:
    """Monthly means of a daily series under MONTHLY_MEAN_RULE.

    THE ONE PLACE A DAILY SERIES BECOMES A MONTHLY ONE. Recon 04 section 7.2
    measured that the averaging choice moves the answer by up to 1.10 $/bbl out
    of a 1.5 $/bbl tolerance, so a second copy of this arithmetic elsewhere in
    the project would be a second chance to disagree with this one.

    Args:
        dates: the observation dates, anything pandas can parse.
        values: the observed prices, NaN where the source published none.
        min_observations: months carrying fewer published days than this get a
            NaN value. The count is still reported, so the month is visible as
            thin rather than absent.

    Returns:
        A frame with one row per calendar month between the first and the last
        observation, no month skipped, and three columns:

            month         first day of the month, datetime64
            value         the mean of the published days, or NaN
            observations  how many days actually carried a price

        A month the source covered but published nothing in appears with a NaN
        value and an observation count of zero rather than being dropped, which
        is what makes a hole in the data visible to the manifest instead of
        invisible in a shorter frame.
    """
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(pd.Series(list(dates)), errors="coerce"),
            "value": pd.to_numeric(pd.Series(list(values)), errors="coerce"),
        }
    )
    frame = frame[frame["date"].notna()]
    if frame.empty:
        return pd.DataFrame(
            {
                "month": pd.Series([], dtype="datetime64[ns]"),
                "value": pd.Series([], dtype="float64"),
                "observations": pd.Series([], dtype="int64"),
            }
        )

    frame["month"] = frame["date"].dt.to_period("M").dt.to_timestamp()
    published = frame[frame["value"].notna()]

    grouped = published.groupby("month")["value"]
    means = grouped.mean()
    counts = grouped.size()

    span = pd.date_range(
        frame["month"].min(), frame["month"].max(), freq="MS"
    )
    means = means.reindex(span)
    counts = counts.reindex(span).fillna(0).astype("int64")

    out = pd.DataFrame(
        {
            "month": span,
            "value": means.to_numpy(dtype="float64"),
            "observations": counts.to_numpy(dtype="int64"),
        }
    )
    # A thin month is reported as thin, not as a mean of four days. The count
    # stays so the outlier list required by SPEC.md section 5.5 can say why.
    thin = out["observations"] < int(min_observations)
    out.loc[thin, "value"] = np.nan
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------------
# SPEC.md section 5.4, validation bounds
# ---------------------------------------------------------------------------
#
# These are units checks, not views on the market. Each is set wide enough that
# only a wrong unit, a wrong sign or a parse failure can trip it. They live here
# rather than in sources/base.py so that every number in the project has one
# home, and crack.sources.base imports them.
#
# The four SPEC.md section 5.4 names them:

#: Rotterdam product quotations, $/t. SPEC.md section 5.4.
#: For scale, the July 2026 anchors in SPEC.md section 5.5 run from 507 for
#: fioul lourd to 1,204 for jet, and the 2022 peak in the recon data is about
#: 1,700 for gazole, so this band is roughly three times the observed range.
BOUNDS_PRODUCT_USD_T = (100.0, 3000.0)

#: Rotterdam product quotations, $/bbl. SPEC.md section 5.4 names a bound for
#: product prices in dollars per TONNE only, because when it was written the only
#: product source in view was DGEC, which quotes in $/t. The OPEC MOMR quotes the
#: same hub in dollars per BARREL, so it needs its own band rather than the $/t
#: one divided by a factor this project would then have had to choose.
#:
#: Like every other bound here it is a units and parse check, not a view on the
#: market. The observed range of the parsed MOMR Rotterdam table over 2000-10 to
#: 2026-02 is 10.85 $/bbl, fuel oil 3.5 percent in November 2001, to 143.25
#: $/bbl, gasoil 10 ppm in the 2022 crisis, so the band below is roughly four
#: times the observed range at the top and half the observed minimum at the
#: bottom. What it still catches is the failure that matters: a table misread as
#: dollars per tonne reads 500 to 1,500 and trips the upper bound at once, and a
#: cents file or a tenfold decimal slip trips one end or the other.
BOUNDS_PRODUCT_USD_BBL = (2.0, 400.0)

#: Brent, $/bbl.
#:
#: THIS ONE DISAGREES WITH SPEC.md SECTION 5.4, WHICH SAYS 10 TO 250, AND THE
#: DISAGREEMENT IS MEASURED RATHER THAN ARGUED. The first live fetch of FRED
#: DCOILBRENTEU on 2026-09-12 carried 25 published prices below 10 $/bbl, and
#: every one of them is a real print that EIA and FRED both still publish:
#:
#:     1998-11-30 to 1998-12-24   17 days, the 1998 oil price collapse,
#:                                low 9.10 on 1998-12-10
#:     1999-02-08 to 1999-02-18    7 days, low 9.77
#:     2020-04-21                  1 day at 9.12, the session WTI settled
#:                                negative
#:
#: The same 25 dates appear in the EIA workbook with identical values, so this is
#: not a FRED artefact. With the bound at 10 the adapter refused the whole
#: download, kept no cache and exited non zero, which is correct behaviour for a
#: bound that has been violated and the wrong answer to a bound that is wrong.
#:
#: The bound is a units and parse check, not a view on the market: it exists to
#: catch a file that arrived in cents, or in euros, or with a decimal point in
#: the wrong place. 5.0 still does that, since a cents file would read 910 and a
#: tenfold slip would read 0.91. Cutting 1998 and 2020 out of the history to fit
#: the printed number would be closer to inventing data than widening the bound
#: is, and SPEC.md section 2 rule 1 is the rule that outranks section 5.4 here.
#:
#: This is a deliberate deviation from the spec and it is a Gate 1 report item.
#: If the owner would rather hold the spec's number, the only honest way to do it
#: is to start the Brent series in 2000 and say so on the page.
BOUNDS_BRENT_USD_BBL = (5.0, 250.0)

#: Cracks, $/bbl. SPEC.md section 5.4. ARA diesel cracks reached about 80 $/bbl
#: on 13 October 2022, SPEC.md section 3, so the upper bound leaves room for a
#: worse crisis than the worst in the sample.
BOUNDS_CRACK_USD_BBL = (-30.0, 150.0)

#: Refinery crude intake, kb/d. SPEC.md section 5.4 says non negative. The upper
#: bound is a units check: the five NWE countries together run under 6,000 kb/d,
#: so a value above 100,000 means barrels per day arrived where thousands were
#: expected.
BOUNDS_INTAKE_KB_D = (0.0, 100000.0)

# Three more the project needs and SPEC.md section 5.4 does not name. Same kind
# of check, stated rather than assumed.

#: The gross refining margin, $/bbl. DGEC's published MBR runs from about 1 to
#: about 37 over 2015 to 2026, recon 02 section 7.1, and a margin can be negative
#: in a bad month, so this band is a sign and units check only.
BOUNDS_MARGIN_USD_BBL = (-50.0, 150.0)

#: US dollars per euro, FRED DEXUSEU. The euro has traded between about 0.82 and
#: 1.60 since 1999.
BOUNDS_EURUSD = (0.5, 2.5)

#: TTF, EUR per MWh. Yahoo TTF=F has printed 3.51 to 339.196, recon 04 section
#: 3.1, so the upper bound sits above the August 2022 spike.
BOUNDS_TTF_EUR_MWH = (0.0, 500.0)

#: European gas, $ per MMBtu, the World Bank pink sheet unit.
BOUNDS_GAS_USD_MMBTU = (0.0, 150.0)


# ---------------------------------------------------------------------------
# The source registry
# ---------------------------------------------------------------------------

#: The frequencies this project handles. Gap detection needs to know which one a
#: series is, because a missing weekday in a weekly series is not a gap and a
#: missing week in a monthly series is not either. See
#: crack.sources.base.find_gaps.
FREQUENCIES = ("daily", "weekly", "monthly", "annual")

#: How a series came to exist. This is a first class field because one series in
#: this study is reconstructed from the curves of a published chart, and SPEC.md
#: section 2 rule 1 means that fact has to be declared in the manifest rather
#: than mentioned in a docstring.
#:
#:     published      the source published exactly this series, machine readable
#:     parsed         extracted from a document the source published, a PDF table
#:     reconstructed  recovered from a published chart, with a measured error
#:     derived        computed by this project from other series
#:     seed           committed by hand from a cited document, never fetched
METHODS = ("published", "parsed", "reconstructed", "derived", "seed")


@dataclass(frozen=True)
class Source:
    """One series this project builds, and everything provenance needs about it.

    Frozen, because the registry is read by the refresh script, by the adapters
    and by the export that feeds the provenance panel, and none of those three
    has any business editing it.

    machine_url is None when the URL cannot be hardcoded. That is not a gap in
    the research, it is a property of the source: the World Bank rewrites the
    document id in its path, JODI renames the in progress year's file every
    January, and the ministry's own page links files whose visible label and href
    disagree about a numeric suffix. For those, url_note says what to scrape and
    the adapter must fail loudly when it cannot find the link rather than
    guessing at a pattern.
    """

    #: cache file stem and the series name in the manifest
    series: str
    #: one sentence a human reads on the provenance panel
    label: str
    #: who published it
    publisher: str
    #: the human readable page, always present, always linkable
    page_url: str
    #: the machine readable file, or None when it has to be discovered
    machine_url: str | None
    #: what to do when machine_url is None, or what is odd about it when it is not
    url_note: str
    #: one of FREQUENCIES
    frequency: str
    #: the unit of the value columns
    unit: str
    #: one of METHODS
    method: str
    #: the licence, named
    licence: str
    #: what the licence actually permits, and what it does not, in plain words
    licence_note: str
    #: whether the cache may be committed to a public repository. False sends the
    #: cache to data/private/ and keeps it out of the deploy, SPEC.md section 2
    #: rule 6.
    committable: bool

    def __post_init__(self) -> None:
        if self.frequency not in FREQUENCIES:
            raise ValueError(
                "source %r declares frequency %r, not one of %s"
                % (self.series, self.frequency, ", ".join(FREQUENCIES))
            )
        if self.method not in METHODS:
            raise ValueError(
                "source %r declares method %r, not one of %s"
                % (self.series, self.method, ", ".join(METHODS))
            )
        if not self.licence_note:
            raise ValueError(
                "source %r carries no licence_note. Every source states what its "
                "terms permit, SPEC.md section 2 rule 6" % (self.series,)
            )
        if not self.committable and "not" not in self.licence_note.lower():
            # A cache that may not be redistributed must say so in words, not
            # only in a boolean, because the boolean is what the code reads and
            # the words are what a human reads on the provenance panel.
            raise ValueError(
                "source %r is not committable but its licence_note does not say "
                "what is forbidden" % (self.series,)
            )


def _registry(*sources: Source) -> Mapping[str, Source]:
    seen: dict[str, Source] = {}
    for item in sources:
        if item.series in seen:
            raise ValueError("two sources both claim the series name %r" % item.series)
        seen[item.series] = item
    return MappingProxyType(seen)


# Licence notes are quoted from the primary document wherever they are quoted at
# all. The recon reports hold the full text and the URL each was read from.

_ETALAB = "Licence Ouverte 2.0 (Etalab)"
_ETALAB_NOTE = (
    "Licence Ouverte 2.0 expressly permits extraction, transformation, "
    "redistribution and publication, including commercially, on condition of "
    "attribution to the concedant and a statement of the date of last update. "
    "Attribute to DGEC, Direction generale de l'energie et du climat, ministere "
    "de la Transition ecologique, with the URL and the note date. One doubt, "
    "raised at recon 02 section 6.4 rather than hidden: every DGEC price table "
    "carries 'Source : DGEC-REUTERS' and the underlying assessments are a "
    "commercial vendor's. The ministry's carve out is for an explicit reservation "
    "of third party rights and a source credit is not one, so on the face of the "
    "documents reuse is permitted. Mitigation: republish the parsed values with "
    "attribution, never the NPG PDFs themselves."
)

_FRED_NOTE = (
    "FRED tags both series 'public domain: citation requested' and asks that the "
    "data source be cited and FRED acknowledged. One real tension, recorded at "
    "recon 04 section 1.8 rather than paraphrased away: the same legal page "
    "prohibits 'data mining, mirroring, robots, scraping, or similar "
    "data-gathering or extraction methods except as expressly allowed by the "
    "terms of use applicable to the FRED API', and a scheduled job that commits "
    "fredgraph.csv into a public repository is arguably a mirror. The clean way "
    "out is to take Brent from EIA directly and EUR/USD from the Federal Reserve "
    "Board H.10, both US federal publishers with no mirroring clause. See "
    "docs/open-questions.md."
)

_OPEC_NOTE = (
    "OPEC permits the information in the MOMR to be 'used and/or reproduced for "
    "educational and other non-commercial purposes without the OPEC "
    "Secretariat's prior written permission, provided that it is fully "
    "acknowledged as the copyright holder'. Full reproduction of the report "
    "itself is not permitted, so the parsed values may be cached and the PDFs "
    "may not. The table credits Argus, and OPEC's own wording says third party "
    "copyright must be acknowledged by obtaining authorisation from the owner, "
    "so credit 'Argus, via the OPEC Monthly Oil Market Report' on every chart "
    "and do not offer the product price series as a bulk download."
)

_JODI_URL_NOTE = (
    "Base "
    "https://www.jodidata.org/_resources/files/downloads/oil-data/annual-csv "
    "with primary/{YYYY}.csv and secondary/{YYYY}.csv for closed years, but the "
    "IN PROGRESS year breaks the pattern: it is primaryyear2026.csv, not "
    "2026.csv, recon 03 section 1.2. Read the hrefs off the downloads page "
    "rather than constructing them or the adapter silently loses the latest "
    "year every January. A full refresh is 933 MB across 50 files, so stream "
    "each one and filter to the five REF_AREAs and the handful of flows and "
    "products before anything is kept. Never commit the raw annual files. "
    "Resolve product and flow codes from JODI's published short names list, "
    "never hardcode them, and carry the assessment code 1, 2 or 3 into the "
    "manifest. JODI revises history: the 2002 file was rewritten in October "
    "2025. THE UK IS GB: the database has 118 REF_AREA values, GB is one of "
    "them and UK is not, so SPEC.md's spelling returns an empty series rather "
    "than an error."
)

_JODI_NOTE = (
    "The JODI terms of use are website terms, not a data licence: 'The "
    "Intellectual Property rights in the JODI Website, and in the material "
    "published on it, are protected by Intellectual Property laws and treaties "
    "around the world. All such rights are reserved.' The downloads page says "
    "the data can be downloaded for free, which is a statement about access and "
    "not about republication. There is no explicit permission to redistribute. "
    "Recon 03 section 1.9 reads this as: committing a small derived extract with "
    "clear attribution is normal practice and is what every energy analyst does, "
    "but it is not covered by a grant and is materially weaker than FRED or EIA. "
    "Use with attribution, do not mirror the raw annual files, and ask "
    "JODIinfo@ief.org before Gate 5."
)

_EIA_NOTE = (
    "US government publications are in the public domain. EIA states 'You may "
    "use and/or distribute any of our data, files, databases, reports, graphs, "
    "charts, and other information products', asking for an acknowledgment that "
    "includes the publication date. The only unambiguous grant in this project."
)


SOURCES: Mapping[str, Source] = _registry(
    # -- DGEC, the ministry ------------------------------------------------
    Source(
        series="dgec_mbr_monthly",
        label="Gross refining margin on Brent, monthly, DGEC's own published figure",
        publisher="DGEC, ministere de la Transition ecologique",
        page_url="https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers",
        machine_url=None,
        url_note=(
            "The workbook is 'Historique de la marge brute de raffinage sur "
            "Brent depuis 2015 (moyennes mensuelles).xlsx', linked from the "
            "landing page. The href and the visible label disagree about a "
            "numeric suffix in both directions and the suffix has changed over "
            "time, recon 02 section 1.2: the label claimed '_1' while the "
            "working href had none, and the '_1' URL returns 404. Scrape the "
            "href off the landing page, never construct it, and fail loudly if "
            "no link matching the title is found. Sheet 'Marge brute raffinage "
            "sur Brent', 139 monthly rows 2015-01 to 2026-07 when read, plus an "
            "annual block below keyed by a text year, so the parser must not "
            "assume column A is always a date. The weekly note leads this file "
            "by at least one month."
        ),
        frequency="monthly",
        unit="USD per barrel and EUR per tonne",
        method="published",
        licence=_ETALAB,
        licence_note=_ETALAB_NOTE,
        committable=True,
    ),
    Source(
        series="dgec_brent_monthly",
        label="Brent date monthly averages as DGEC publishes them, in $/bbl",
        publisher="DGEC, ministere de la Transition ecologique",
        page_url="https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers",
        machine_url=None,
        url_note=(
            "'Historique du cours du Brent depuis 2015 (moyennes mensuelles).xlsx', "
            "same landing page, same unstable suffix, same rule: read the href. "
            "Sheet 'Cours du Brent', 140 monthly rows 2015-01 to 2026-08 when "
            "read, full float precision. The page states these are means of the "
            "daily Brent date London close, which is the series the SPEC.md "
            "section 5.5 cross check compares against FRED."
        ),
        frequency="monthly",
        unit="USD per barrel",
        method="published",
        licence=_ETALAB,
        licence_note=_ETALAB_NOTE,
        committable=True,
    ),
    Source(
        series="dgec_note_printed_weekly",
        label="Rotterdam quotations printed in the weekly notes, $/t",
        publisher="DGEC, ministere de la Transition ecologique",
        page_url="https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers",
        machine_url=None,
        url_note=(
            "The weekly notes are PDFs named NPG-YYYY.MM.DD.pdf under "
            "https://www.ecologie.gouv.fr/sites/default/files/documents/ , "
            "sometimes with a '_0' suffix, and recon 02 section 2.4 found the "
            "filename date does not reliably match the note's content date. Only "
            "the current note is linked from the landing page, so history comes "
            "from the Wayback Machine. Parse table 1 by row and column labels, "
            "never by position: recon 02 section 3.3 documents three layout "
            "breaks. SPEC.md section 5.5 anchors these values. Every preserved "
            "note prints two weekly columns, some of which repeat a week an "
            "adjacent note already printed, so this series is a little shorter "
            "than twice the number of notes, its row count is in the manifest "
            "entry, and it is the whole published weekly record. It is the GROUND TRUTH "
            "and the calibration anchor set for dgec_note_reconstructed_weekly, "
            "and it is the only place Jet and Fioul lourd exist at weekly "
            "frequency, because neither is plotted on the chart."
        ),
        frequency="weekly",
        unit="USD per tonne",
        method="parsed",
        licence=_ETALAB,
        licence_note=_ETALAB_NOTE,
        committable=True,
    ),
    Source(
        series="dgec_note_printed_monthly",
        label=(
            "Monthly Rotterdam quotations printed in the weekly notes, $/t, with "
            "the ministry's own provisional flag and every vintage of every month"
        ),
        publisher="DGEC, ministere de la Transition ecologique",
        page_url="https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers",
        machine_url=None,
        url_note=(
            "The same note PDFs as dgec_note_printed_weekly, and the MONTHLY "
            "columns of the same table on the same page. The six column layout "
            "that prints monthly averages first appears in the December 2025 "
            "note, recon 02 section 3.3, so this series is 7 months from 6 of "
            "the 10 preserved notes and cannot be made longer without collecting "
            "more notes. DGEC publishes monthly workbooks for Brent and for the "
            "MBR and NO monthly product history at all, so this is the only "
            "monthly record of these six DGEC quotations anywhere, and the only "
            "monthly home of Jet and Fioul lourd TBTS as DGEC $/t figures. The "
            "OPEC MOMR carries Argus jet and 1 percent fuel oil rows for the same "
            "hub in $/bbl on a different specification, and JODI carries jetkero "
            "volumes: neighbours, not substitutes. SPEC.md "
            "section 2 rule 5 is the reason it exists as a series rather than as "
            "a diagnostic: the current month is provisional and gets revised, so "
            "each row carries the provisional marker DGEC printed, the vintage "
            "of the note it was read from, and a revision_history field holding "
            "every earlier print of that month with its own flag and values. The "
            "corpus contains an observed provisional to final transition, March "
            "2026 across four notes, and a 143 $/t revision between two "
            "provisional prints of April 2026. The gaps are real: a month no "
            "preserved note happened to print has no row."
        ),
        frequency="monthly",
        unit="USD per tonne",
        method="parsed",
        licence=_ETALAB,
        licence_note=_ETALAB_NOTE,
        committable=True,
    ),
    Source(
        series="dgec_note_reconstructed_weekly",
        label=(
            "Weekly Rotterdam quotations recovered from the curves of the chart "
            "on page 3 of the weekly note, this study's reconstruction"
        ),
        publisher="DGEC, ministere de la Transition ecologique, decoded by this study",
        page_url="https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers",
        machine_url=None,
        url_note=(
            "Same PDFs as dgec_note_printed_weekly. The chart is vector, so the "
            "curves carry more history than the printed table does. Recon 05 part "
            "two decoded ten notes into 219 consecutive weekly observations from "
            "2022-07-01 to 2026-09-04 with no holes, calibrated each note against "
            "its own printed figures, and measured an out of sample error of 0.17 "
            "to 0.44 $/t mean absolute, worst single point 0.87 $/t, which is 0.02 "
            "to 0.12 $/bbl on gasoil. FOUR SERIES ONLY, Eurosuper, Gazole, Fioul "
            "domestique and Brent date. Jet and Fioul lourd are not on the chart "
            "and are therefore deliberately absent: reconstructing them by "
            "regression on the three that are plotted would be the synthetic "
            "series SPEC.md section 2 rule 1 forbids. Six conditions from recon 05 "
            "section 14 are implemented in crack.sources.dgec_note and each one is "
            "cited there: separate series and manifest entry, the measured error "
            "carried in the data, the 25 weeks with no cross check flagged, Brent "
            "flagged as the least accurate of the four, the wb_NPG-2026.04.03 "
            "against NPG-2026.09.04 axis degeneracy disclosed, and a decode that "
            "fails loudly rather than guessing."
        ),
        frequency="weekly",
        unit="USD per tonne",
        # THIS is why the manifest carries a method field. A number recovered
        # from the geometry of a chart is not the same kind of object as a number
        # a ministry printed, and SPEC.md section 2 rule 1 means the difference
        # has to be declared where the data is, not only in prose.
        method="reconstructed",
        licence=_ETALAB,
        licence_note=(
            _ETALAB_NOTE
            + " This series is additionally a reconstruction by this study, not "
            "a DGEC publication. It must be labelled as such everywhere it "
            "appears, with its measured error next to it, and it must never be "
            "presented as a DGEC figure."
        ),
        committable=True,
    ),
    Source(
        series="dgec_note_reconstructed_cracks_weekly",
        label=(
            "Weekly Rotterdam gasoil and gasoline cracks against Brent, $/bbl, "
            "computed from the reconstructed weekly quotations"
        ),
        publisher="this study, from DGEC quotations decoded by this study",
        page_url="https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers",
        machine_url=None,
        url_note=(
            "Computed, not fetched. crack = product $/t over the ICE contract "
            "factor minus Brent date $/t over DGEC_BBL_PER_T_BRENT_NOTE, SPEC.md "
            "section 4.2. Both legs come from the same chart on the same page of "
            "the same note, so they share a date and an averaging window, which is "
            "what SPEC.md section 4.2 requires and what a weekly product against a "
            "monthly crude would break. EVERY VALUE INHERITS THE RECONSTRUCTION: "
            "this series is exactly as trustworthy as dgec_note_reconstructed_"
            "weekly and no more, and the 0.17 to 0.44 $/t measured error is about "
            "0.02 to 0.06 $/bbl on the gasoil leg. The gasoline leg disagrees with "
            "the OPEC Rotterdam premium gasoline 98 crack by up to 13 $/bbl, for "
            "the reasons set out next to BBL_PER_T_GASOLINE above, and that gap is "
            "published rather than closed."
        ),
        frequency="weekly",
        unit="USD per barrel",
        method="derived",
        licence=_ETALAB,
        licence_note=(
            _ETALAB_NOTE
            + " This series is additionally computed by this study from a "
            "reconstruction by this study. It is not a DGEC figure and must never "
            "be presented as one."
        ),
        committable=True,
    ),
    # -- The committed decode of the weekly notes --------------------------
    #
    # SPEC.md section 5.4 says the caches are committed so the site builds and
    # results reproduce with no network. The three series above could not honour
    # that: they are built by decoding note PDFs that are gitignored and cannot
    # be downloaded again, so a fresh clone could not rebuild any of them and the
    # weekly refresh job of SPEC.md section 8 could not restitch after collecting
    # a note. These four caches are the decode itself, committed, so the stitch
    # is a pure function of committed data. The PDFs stay private. See
    # crack.sources.dgec_note, "The committed decode".
    Source(
        series="dgec_note_decoded_index",
        label=(
            "One row per preserved weekly note: the week it prints, its file, its "
            "quotation page and its chart geometry"
        ),
        publisher="DGEC, ministere de la Transition ecologique, recorded by this study",
        page_url="https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers",
        machine_url=None,
        url_note=(
            "Not fetched. Written from the corpus of preserved note PDFs, which "
            "are gitignored and irreplaceable. The date is the note's CONTENT "
            "date, the latest week printed inside it, never the date in its file "
            "name: four of the notes carry a content date later than their name "
            "because the ministry sometimes replaces the contents of an existing "
            "URL. The geometry is the signature that tells two notes which cannot "
            "disagree from two which agree."
        ),
        frequency="weekly",
        unit="USD per tonne for the axis values, points for the pitch, a count for the ticks",
        method="parsed",
        licence=_ETALAB,
        licence_note=_ETALAB_NOTE,
        committable=True,
    ),
    Source(
        series="dgec_note_decoded_weekly",
        label=(
            "The page 3 chart of every preserved note, decoded, one reading per "
            "note per week per product, $/t"
        ),
        publisher="DGEC weekly note chart, decoded by this study",
        page_url="https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers",
        machine_url=None,
        url_note=(
            "Not fetched. The readings themselves, before the stitch. "
            "dgec_note_reconstructed_weekly is the median across them per week "
            "with its spread and its evidence class; this is what each note drew. "
            "One row per week and one reading slot per note that covers it, with "
            "the note's file name beside its values, because a cache here is a "
            "time series and a long table would not have a unique date."
        ),
        frequency="weekly",
        unit="USD per tonne",
        method="reconstructed",
        licence=_ETALAB,
        licence_note=(
            _ETALAB_NOTE
            + " This series is additionally a reconstruction by this study, not a "
            "DGEC publication. It must be labelled as such everywhere it appears, "
            "with its measured error next to it, and never presented as a DGEC "
            "figure."
        ),
        committable=True,
    ),
    Source(
        series="dgec_note_decoded_printed",
        label=(
            "The printed weekly columns of every preserved note, one reading per "
            "note per week per product"
        ),
        publisher="DGEC, ministere de la Transition ecologique, weekly note",
        page_url="https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers",
        machine_url=None,
        url_note=(
            "Not fetched. Parsed out of each note's own table by row and column "
            "label. dgec_note_printed_weekly is the stitch of these, one row per "
            "distinct week with the disagreement between notes carried rather than "
            "averaged; this is what each note printed. A blank is a row that "
            "note's layout does not print, never a zero."
        ),
        frequency="weekly",
        unit="USD per tonne, except fioul_lourd_tbts_eur_t which is EUR per tonne",
        method="parsed",
        licence=_ETALAB,
        licence_note=_ETALAB_NOTE,
        committable=True,
    ),
    Source(
        series="dgec_note_decoded_monthly",
        label=(
            "The printed monthly columns of every preserved note, one reading per "
            "note per month per product, with that note's provisional marker"
        ),
        publisher="DGEC, ministere de la Transition ecologique, weekly note",
        page_url="https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers",
        machine_url=None,
        url_note=(
            "Not fetched. The monthly columns the six column layout has printed "
            "since December 2025, with the provisional marker each note set "
            "against each month. SPEC.md section 2 rule 5 asks for every vintage "
            "to be kept and the flag shown; this file is where the vintages are. "
            "dgec_note_printed_monthly is the stitch of these."
        ),
        frequency="monthly",
        unit="USD per tonne, except fioul_lourd_tbts_eur_t which is EUR per tonne",
        method="parsed",
        licence=_ETALAB,
        licence_note=_ETALAB_NOTE,
        committable=True,
    ),
    # -- OPEC ---------------------------------------------------------------
    Source(
        series="opec_rotterdam_products_monthly",
        label=(
            "Rotterdam barge product prices, monthly, $/bbl, read out of the "
            "'Refined product prices, US$/b' table of the OPEC Monthly Oil Market "
            "Report. The headline crack source of this study"
        ),
        publisher="OPEC Secretariat, assessments credited to Argus",
        page_url="https://www.opec.org/monthly-oil-market-report.html",
        machine_url=None,
        url_note=(
            "Live opec.org returns 403 to every scripted request from this "
            "machine, recon 05 section 1.1, so nothing is fetched from opec.org. "
            "The issues resolve from the Internet Archive instead, through "
            "https://web.archive.org/web/<timestamp>id_/<original url> , where "
            "the original is "
            "https://www.opec.org/assets/assetdb/momr-<month>-<year>.pdf . The "
            "index is DISCOVERED with a Wayback CDX query and never hardcoded, "
            "because the timestamp differs per issue and the 2004 to 2008 "
            "filenames carry extra suffixes and one misspelling, "
            "momr-janaury-2008.pdf. Recon 05 section 1.2 counted 303 distinct "
            "issues, 2001-01 to 2026-03, verified across five layout eras. April "
            "to September 2026 are not archived, which is a hole the manifest "
            "records rather than papers over. The PDFs are cached under "
            "data/private/momr/ and are NEVER committed; only the parsed values "
            "are."
        ),
        frequency="monthly",
        unit="USD per barrel",
        method="parsed",
        licence="OPEC copyright, non commercial reuse of the information permitted",
        licence_note=_OPEC_NOTE,
        committable=True,
    ),
    # -- FRED ---------------------------------------------------------------
    Source(
        series="fred_brent_daily",
        label="Europe Brent spot, daily, $/bbl, EIA series published through FRED",
        publisher="US Energy Information Administration, retrieved from FRED",
        page_url="https://fred.stlouisfed.org/series/DCOILBRENTEU",
        machine_url="https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU",
        url_note=(
            "No key. Header is 'observation_date,DCOILBRENTEU', LF endings, "
            "us-ascii, no byte order mark. A day with no published price is an "
            "EMPTY field, not the '.' older FRED downloads used, so accept both "
            "and map both to NaN, never to zero. One row per business day, no "
            "weekend rows, so a gap is a blank value rather than an absent row. "
            "MUST be fetched with the project token user agent, see "
            "crack.sources.base.USER_AGENT_BY_HOST."
        ),
        frequency="daily",
        unit="USD per barrel",
        method="published",
        licence="public domain, citation requested",
        licence_note=_FRED_NOTE,
        committable=True,
    ),
    Source(
        series="fred_eurusd_daily",
        label="US dollars to one euro, daily noon buying rate, FRED DEXUSEU",
        publisher="Board of Governors of the Federal Reserve System, retrieved from FRED",
        page_url="https://fred.stlouisfed.org/series/DEXUSEU",
        machine_url="https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXUSEU",
        url_note=(
            "Same endpoint shape and the same user agent rule as Brent. The "
            "holiday calendar is the US federal one, which is a DIFFERENT "
            "calendar from the Brent series, recon 04 section 2.5, so a date "
            "present in one is not necessarily present in the other and the two "
            "must be joined on the date, never zipped by position. The "
            "publication lag is worse than Brent's."
        ),
        frequency="daily",
        unit="US dollars per euro",
        method="published",
        licence="public domain, citation requested",
        licence_note=_FRED_NOTE,
        committable=True,
    ),
    Source(
        series="eia_brent_daily",
        label=(
            "Europe Brent spot FOB, daily, $/bbl, taken straight from EIA. The "
            "same numbers as fred_brent_daily, under a licence with no doubt in it"
        ),
        publisher="US Energy Information Administration",
        page_url="https://www.eia.gov/dnav/pet/hist/RBRTEd.htm",
        machine_url="https://www.eia.gov/dnav/pet/hist_xls/RBRTEd.xls",
        url_note=(
            "A legacy .xls, not .xlsx, so it is read with xlrd and not openpyxl. "
            "Two sheets, 'Contents' and 'Data 1'. On 'Data 1' row 1 is a link "
            "back, row 2 is 'Sourcekey' and 'RBRTE', row 3 is the header 'Date' "
            "and 'Europe Brent Spot Price FOB (Dollars per Barrel)', and the data "
            "starts at row 4 with Excel serial dates. 9,973 rows, 1987-05-20 to "
            "2026-09-09 when read, recon 04 section 1.7. EIA OMITS a holiday "
            "entirely rather than emitting a blank row, which is the one "
            "structural difference from the FRED copy of the same series. "
            "NEVER probe eia.gov with HEAD, it answers 503 to HEAD and 200 to GET "
            "on the same URL, recon 03 section 4 item 12, and "
            "crack.sources.base.http_head refuses the host for that reason."
        ),
        frequency="daily",
        unit="USD per barrel",
        method="published",
        licence="US public domain",
        licence_note=_EIA_NOTE,
        committable=True,
    ),
    # -- Gas ----------------------------------------------------------------
    Source(
        series="worldbank_gas_europe_monthly",
        label="Natural gas, Europe, monthly, $/MMBtu, World Bank pink sheet",
        publisher="World Bank Commodity Price Data (The Pink Sheet)",
        page_url="https://www.worldbank.org/en/research/commodity-markets",
        machine_url=None,
        url_note=(
            "CMO-Historical-Data-Monthly.xlsx sits under a thedocs.worldbank.org "
            "path whose document id segment changes, and the old stable "
            "pubdocs.worldbank.org URL now 404s, recon 04 section 4.1. Scrape the "
            "landing page for the link whose filename is "
            "CMO-Historical-Data-Monthly.xlsx and fail loudly if it is absent. "
            "Sheet 'Monthly Prices'. From 2015-04 the Europe gas series is TTF by "
            "the publisher's own definition and already in $/MMBtu, so the "
            "analysis reads gas_usd_mmbtu rather than computing it, with no FX "
            "and no conversion factor. Before 2015-04 the definition changes "
            "twice and those breaks must be labelled."
        ),
        frequency="monthly",
        unit="USD per MMBtu",
        method="published",
        licence="CC BY 4.0",
        licence_note=(
            "World Bank data is licensed CC BY 4.0 with an added mediation and "
            "arbitration clause for disputes, which is not a use restriction. "
            "Attribute as 'World Bank Commodity Price Data (The Pink Sheet)'. "
            "Two caveats recorded at recon 04 section 4.7: the general datasets "
            "page carries a narrower clause scoped to material outside the open "
            "data licence, and the Europe gas series itself credits Bloomberg "
            "Finance L.P. and World Gas Intelligence, so do not strip the "
            "attribution and do not present it as this project's own assessment."
        ),
        committable=True,
    ),
    Source(
        series="ttf_daily",
        label="Dutch TTF front month settlement, daily, EUR/MWh, optional display layer",
        publisher="Yahoo Finance, symbol TTF=F, CME listed calendar month future",
        page_url="https://finance.yahoo.com/quote/TTF%3DF/",
        machine_url=None,
        url_note=(
            "Fetched through yfinance, an unofficial client for an undocumented "
            "endpoint. History starts 2017-10-23, 2,235 rows to 2026-09-11, 96.3 "
            "percent of business days, the missing days being exchange holidays. "
            "Rolls are unadjusted and visible. Before 2018-03-14 the settlement "
            "is repeated into all four OHLC fields. Yahoo does not document the "
            "unit anywhere: EUR per MWh was established numerically by "
            "reproducing the pink sheet series to a median 0.02 percent over 106 "
            "months, recon 04 section 3.1, which is a construction proof and must "
            "be labelled as one. yfinance returns an empty frame intermittently, "
            "SPEC.md section 13: retry, then fail rather than caching an empty "
            "file."
        ),
        frequency="daily",
        unit="EUR per MWh",
        method="published",
        licence="none found",
        # NOT COMMITTABLE. The cache goes to data/private/ and never leaves this
        # machine.
        licence_note=(
            "There is no public Yahoo Finance data licence. The applicable "
            "general term forbids users to 'reproduce, modify, rent, lease, "
            "sell, trade, distribute, transmit, broadcast, publicly perform, "
            "create derivative works based on, or exploit for any commercial "
            "purposes' any portion of the services, and yfinance carries no "
            "redistribution grant of its own. Committing this cache to a public "
            "repository would be redistribution of Yahoo sourced data, so it is "
            "NOT committed. The site is complete without it: the monthly gas "
            "series the analysis runs on comes from the World Bank pink sheet, "
            "which is CC BY 4.0 and already in $/MMBtu."
        ),
        committable=False,
    ),
    # -- Physical -----------------------------------------------------------
    #
    # THREE JODI SERIES, NOT ONE. SPEC.md section 5.1 writes them as a single
    # row, "Refinery crude intake, refinery output by product, crude imports".
    # They are three caches here for a reason that is mechanical rather than
    # aesthetic: a cache file is one row per date, and a single tidy table of
    # five countries by ten measures would repeat every month forty times, which
    # crack.sources.base.validate_frame refuses as duplicate dates and rightly
    # so. Splitting on the spec's own three nouns keeps each file one row per
    # month with the countries across the columns.
    Source(
        series="jodi_nwe_refinery_intake_monthly",
        label=(
            "Refinery crude intake and total refinery feed for BE, DE, FR, NL "
            "and GB, monthly, thousand barrels per day"
        ),
        publisher="JODI-Oil World Database",
        page_url="https://www.jodidata.org/oil/database/data-downloads.aspx",
        machine_url=None,
        url_note=_JODI_URL_NOTE,
        frequency="monthly",
        unit="thousand barrels per day",
        method="published",
        licence="no explicit licence, all rights reserved",
        licence_note=_JODI_NOTE,
        committable=True,
    ),
    Source(
        series="jodi_nwe_refinery_output_monthly",
        label=(
            "Refinery gross output by product for BE, DE, FR, NL and GB, "
            "monthly, thousand barrels per day"
        ),
        publisher="JODI-Oil World Database",
        page_url="https://www.jodidata.org/oil/database/data-downloads.aspx",
        machine_url=None,
        url_note=_JODI_URL_NOTE,
        frequency="monthly",
        unit="thousand barrels per day",
        method="published",
        licence="no explicit licence, all rights reserved",
        licence_note=_JODI_NOTE,
        committable=True,
    ),
    Source(
        series="jodi_nwe_crude_imports_monthly",
        label=(
            "Crude oil imports for BE, DE, FR, NL and GB, monthly, thousand "
            "barrels per day"
        ),
        publisher="JODI-Oil World Database",
        page_url="https://www.jodidata.org/oil/database/data-downloads.aspx",
        machine_url=None,
        url_note=_JODI_URL_NOTE,
        frequency="monthly",
        unit="thousand barrels per day",
        method="published",
        licence="no explicit licence, all rights reserved",
        licence_note=_JODI_NOTE,
        committable=True,
    ),
    Source(
        series="ei_refinery_capacity_annual",
        label="Refinery capacity by country, annual, thousand barrels daily",
        publisher="Energy Institute Statistical Review of World Energy 2026",
        page_url="https://www.energyinst.org/statistical-review/resources-and-data-downloads",
        machine_url="https://www.energyinst.org/__data/assets/file/0008/1827620/EI-Stats-Review-ALL-data.xlsx",
        url_note=(
            "Plain href, no click through and no registration. Sheet 'Oil "
            "refinery - capacity', units 'Thousand barrels daily'. The asset id "
            "in the path is edition specific and will move with the 2027 edition, "
            "so check the landing page when it does. EI revises history between "
            "editions, which is a reproducibility hazard worth recording in the "
            "manifest vintage field."
        ),
        frequency="annual",
        unit="thousand barrels daily",
        method="published",
        licence="Energy Institute copyright, quotation permitted, reproduction not",
        # NOT COMMITTABLE. The cache goes to data/private/ and only the derived
        # utilisation ratio is published.
        licence_note=(
            "The review permits quotation with attribution but says that 'for "
            "extensive reproduction of tables and/or charts, permission must "
            "first be obtained'. Committing the capacity table, even five country "
            "rows, is extensive reproduction of a table and is NOT permitted "
            "without written permission from statisticalreview@energyinst.org. "
            "Worse, the capacity sheet is footnoted as including data from ICIS "
            "and S&P Global Energy, and 'The redistribution or reproduction of "
            "data whose source is S&P Global Energy or S&P Global Inc, is "
            "strictly prohibited without its prior authorisation'. The footnote "
            "does not say which rows came from which supplier, so the S&P part "
            "cannot be stripped out. The raw capacity therefore stays in "
            "data/private/ and only utilisation, the ratio of a JODI series to an "
            "EI series, is published. SPEC.md section 6.1 already provides the "
            "fallback if even that is refused: use intake with a trend and "
            "closure dummies, and say so."
        ),
        committable=False,
    ),
    Source(
        series="nwe5_refinery_capacity_annual",
        label="NWE five country refinery capacity total, annual, thousand barrels daily",
        publisher="this study, from the Energy Institute Statistical Review of World Energy 2026",
        page_url="https://www.energyinst.org/statistical-review/resources-and-data-downloads",
        machine_url=None,
        url_note=(
            "Not fetched. Derived by this study from the row above, by summing "
            "the five country capacities at each year end. Only the owner can "
            "rebuild it, because only the owner has the private table; everyone "
            "else, CI included, reads the committed cache. The Review's own "
            "download page is linked because that is where the underlying figures "
            "come from and where a reader goes to check them."
        ),
        frequency="annual",
        unit="thousand barrels daily",
        # Not "published". EI publishes country rows; this total is arithmetic
        # over five of them and the provenance panel says so.
        method="derived",
        licence="Energy Institute copyright on the underlying table, this total derived and attributed",
        licence_note=(
            "ONE NUMBER PER YEAR, the five country total, and NOT any of the "
            "country rows it was summed from. Reproducing the Review's table is "
            "not permitted without written permission and redistributing its S&P "
            "Global sourced data is prohibited outright, which is why the table "
            "itself stays in data/private/ under the entry above and is never "
            "committed. This total is a derived aggregate rather than a row of "
            "that table, it is attributed to the Energy Institute Statistical "
            "Review of World Energy 2026 wherever it appears, and it is already "
            "recoverable from what SPEC.md section 6.1 requires the site to "
            "publish, since utilisation times the committed JODI intake returns "
            "it to the decimal. It is committed because SPEC.md section 5.4 "
            "requires the study to rebuild with no network and a GitHub runner "
            "has nothing from data/private. If the Energy Institute reads this "
            "differently, the remedy is one email to "
            "statisticalreview@energyinst.org and the fallback of SPEC.md section "
            "6.1, intake with a trend and closure dummies, which is already built "
            "and reported beside the utilisation model."
        ),
        committable=True,
    ),
    # -- Seeds --------------------------------------------------------------
    Source(
        series="eia_refinery_fuel_2023",
        label="US refinery natural gas use and crude inputs for 2023, the gas intensity inputs",
        publisher="US Energy Information Administration",
        page_url="https://www.eia.gov/petroleum/refinerycapacity/",
        machine_url=None,
        url_note=(
            "Seeded by hand from the cited tables rather than fetched, because it "
            "is four numbers that change once a year and each one needs its table "
            "named next to it. Tables 10a and 10b of the Refinery Capacity Report "
            "edition covering 2023, the heat content from the Natural Gas "
            "Navigator series NG_CONS_HEAT_A_EPG0_VGTH_BTUCF_A, and crude inputs "
            "from MCRRIUS1. NEVER probe eia.gov with HEAD: it answers 503 to HEAD "
            "and 200 to GET on the same URL, recon 03 section 1171, which looks "
            "exactly like the source being down."
        ),
        frequency="annual",
        unit="million cubic feet, Btu per cubic foot, thousand barrels",
        method="seed",
        licence="US public domain",
        licence_note=_EIA_NOTE,
        committable=True,
    ),
    Source(
        series="events",
        label="Dated events marked on every chart, one source_url per entry",
        publisher="this study, every entry cited",
        page_url="https://nathancouturier.github.io/crack-spread-study/",
        machine_url=None,
        url_note=(
            "data/seed/events.json, written by hand under SPEC.md section 6.5. An "
            "entry with no source_url does not go in."
        ),
        frequency="daily",
        unit="none",
        method="seed",
        licence="this study, MIT",
        licence_note=(
            "The list is this project's own. Each entry links the source that "
            "establishes the event, and the linked sources carry their own terms."
        ),
        committable=True,
    ),
    Source(
        series="anchors",
        label=(
            "The published DGEC figures the pipeline must reproduce, SPEC.md "
            "section 5.5, held as data rather than as literals in a test"
        ),
        publisher="DGEC, ministere de la Transition ecologique, transcribed by this study",
        page_url="https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers",
        machine_url=None,
        url_note=(
            "data/seed/anchors.json, written by hand under SPEC.md sections 5.5 "
            "and 8. The printed values are transcribed from SPEC.md section 5.5, "
            "which prints them from the DGEC notes named against each one; every "
            "measured_ field in the file is recomputed from the committed caches "
            "so the file cannot claim a reproduction the data does not support. "
            "The file also carries the sp_global_reference block, which is under "
            "different terms and therefore has its own manifest entry pointing at "
            "the same file."
        ),
        frequency="monthly",
        unit="USD per barrel and USD per tonne",
        method="seed",
        licence=_ETALAB,
        licence_note=_ETALAB_NOTE,
        committable=True,
    ),
    Source(
        series="sp_global_reference",
        label="S&P Global margin and crack levels quoted as order of magnitude checks",
        publisher="S&P Global Commodity Insights",
        page_url="https://www.spglobal.com/energy/en/news-research/latest-news/crude-oil/032822-refinery-margin-tracker-record-high-global-diesel-cracks-propel-margins-upward",
        machine_url=None,
        url_note=(
            "Five figures from two dated articles, SPEC.md sections 3, 4.4, 5.1 "
            "and 5.5, seeded by hand with their URLs in the sp_global_reference "
            "block of data/seed/anchors.json. They are physical assessments on a "
            "different method and they are a sanity check on levels, never a "
            "benchmark to fit to. Both article URLs answer HTTP 403 to automated "
            "access, with a bot token user agent and with a browser user agent, "
            "so the figures are transcribed from SPEC.md, which quotes the "
            "articles, and the file says so."
        ),
        frequency="monthly",
        unit="USD per barrel",
        method="seed",
        licence="S&P Global copyright",
        licence_note=(
            "Two individual figures quoted from two news articles with "
            "attribution and a link, which is ordinary quotation. The underlying "
            "assessments are S&P's and are NOT redistributable as a series. Do "
            "not build a chart out of them, do not extend them, and do not "
            "present them as a comparable series."
        ),
        committable=True,
    ),
)


def source(series: str) -> Source:
    """The registry entry for one series, by name.

    Raises:
        KeyError: naming every series that does exist, because a typo in an
            adapter's name attribute would otherwise show up much later as a
            manifest entry nobody can trace.
    """
    try:
        return SOURCES[series]
    except KeyError:
        raise KeyError(
            "no source registered as %r. Registered: %s"
            % (series, ", ".join(sorted(SOURCES)))
        ) from None


def committable_series() -> Sequence[str]:
    """Series whose cache may be committed to the public repository."""
    return tuple(sorted(name for name, s in SOURCES.items() if s.committable))


def uncommittable_series() -> Sequence[str]:
    """Series whose cache may not be redistributed, and therefore stays private.

    Two today, for two different reasons, and both reasons are in the licence
    note next to them: the Energy Institute capacity table, which may not be
    reproduced extensively and carries S&P sourced rows that cannot be separated
    out, and the Yahoo TTF series, which has no redistribution grant at all.
    """
    return tuple(sorted(name for name, s in SOURCES.items() if not s.committable))


# ---------------------------------------------------------------------------
# Import time checks
# ---------------------------------------------------------------------------
#
# The two facts this module would be worst at losing quietly.

if not (GAS_INTENSITY_BAND[0] < GAS_INTENSITY_MMBTU_PER_BBL < GAS_INTENSITY_BAND[1]):
    raise RuntimeError(
        "GAS_INTENSITY_MMBTU_PER_BBL is %r, outside the SPEC.md section 4.4 band "
        "%r. The spec says stop and show your working rather than proceed."
        % (GAS_INTENSITY_MMBTU_PER_BBL, GAS_INTENSITY_BAND)
    )

if DGEC_BBL_PER_T_BRENT_NOTE == DGEC_BBL_PER_T_BRENT_MARGIN:
    raise RuntimeError(
        "The two DGEC Brent factors have become equal. They are 7.5 and 7.55, "
        "they are used in different places, and collapsing them into one is the "
        "error this pair of constants exists to prevent. See recon 02 section 5.4."
    )
