"""The margin model. SPEC.md sections 4.2 to 4.5, and nothing else.

This module takes numbers and returns numbers. It reads no file, fetches
nothing, holds no series and imports no pandas. There are two reasons for that
and both are load bearing.

The first is SPEC.md section 7.1: this engine exists twice, here and in
src/engine.js, and tools/validate-engine.mjs has to prove the two agree to 1e-9
on every line of every case. A function that reached for a data frame could not
be mirrored in a browser, and a function that reached for a file could not be
mirrored at all. Everything here is arithmetic on floats and small frozen
records, in an order that is written down, so the JavaScript can do the same
arithmetic in the same order.

The second is that a pure engine can be argued with. Every number the site
prints comes out of one of these functions with its inputs visible next to it,
so a reader who disagrees with a yield or a factor can see exactly which line it
enters and what it moves.

Where the series live
---------------------
crack.series is the plumbing: it opens the committed caches, aligns them, and
calls these functions. If you are looking for the code that knows what
data/cache/opec_rotterdam_products_monthly.csv is, it is there, not here.

The four layers of SPEC.md section 4.3, and where each one is
------------------------------------------------------------
    1  official margin       not computed at all. DGEC's published MBR is
                             carried through untouched. Nothing in this module
                             overwrites it, and decompose_official takes it as
                             an input precisely so that the decomposition
                             cannot change it.
    2  replication           replicate_mbr. It does not reach the 0.50 $/bbl
                             bar and it is not supposed to pretend otherwise.
                             Read its docstring before reading its output.
    3  decomposition         decompose_official, contribution[p] = yield[p] *
                             crack[p], with everything unattributable on a
                             residual line that is always returned.
    4  observed yields       observed_yields, on either JODI denominator, with
                             the sum of the vector returned next to it so that
                             the 1.15 problem cannot hide.

Three things this module refuses to do
--------------------------------------
It will not compute a crack from legs that do not share a date and an averaging
window, SPEC.md section 4.2. That is a raised AlignmentError, not a warning.

It will not subtract a gas cost from a margin that already contains one. Every
margin carries a basis, MARGIN_GROSS_OF_GAS or MARGIN_NET_OF_GAS, and DGEC's
published MBR is the second: its methodology note subtracts the cost of the
purchased natural gas before publishing the figure. SPEC.md section 4.4's
margin_after_gas = margin_gross - gas_cost applies to the first kind and not to
the second, so the combination that would charge the barrel twice raises
GasDoubleCountError. The gas story on a net margin is gas_wedge, which compares
the two intensities at one price and deducts neither.

It will not invent a run cut threshold. SPEC.md section 6.2 puts the threshold
behind Gate 3 and allows it to come out unidentified, so the threshold is an
argument here, it is allowed to be None, and when it is None the headroom and
the breakevens are None as well rather than being computed against a guess.
SPEC.md section 6.2's own fallback, the ten year percentile, is percentile_rank
and needs no threshold at all.

Missing data
------------
NaN in, NaN out, everywhere, with no exception raised and nothing filled.
SPEC.md section 2 rule 1. The exceptions this module does raise are all about
units, alignment and arithmetic that has no answer, never about a missing
observation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence

from crack import config

__all__ = [
    # units and windows
    "USD_PER_BBL",
    "USD_PER_T",
    "UNITS",
    "DAILY",
    "WEEKLY",
    "MONTHLY",
    "WINDOWS",
    "BASIS_DIRECT",
    "BASIS_CONVERTED",
    "GAS_BASIS_TTF",
    "GAS_BASIS_PUBLISHED",
    "MARGIN_GROSS_OF_GAS",
    "MARGIN_NET_OF_GAS",
    "MARGIN_BASES",
    # errors
    "UnitError",
    "AlignmentError",
    "GasDoubleCountError",
    # cracks, SPEC.md section 4.2
    "Quote",
    "Crack",
    "to_usd_bbl",
    "require_aligned",
    "crack_from_usd_t",
    "crack_from_usd_bbl",
    "crack",
    "crack_values",
    # yields
    "mass_yield_to_volume_yield",
    "ObservedYields",
    "observed_yields",
    # gas and the margin, SPEC.md section 4.4
    "GasCost",
    "gas_from_ttf",
    "gas_from_usd_mmbtu",
    "gas_cost_usd_bbl",
    "GasWedge",
    "gas_wedge",
    "MarginInputs",
    "MarginResult",
    "evaluate",
    # decomposition, SPEC.md section 4.3 layer 3
    "Decomposition",
    "decompose_official",
    # replication, SPEC.md section 4.3 layer 2
    "ReplicationAttempt",
    "replicate_mbr",
    # outputs, SPEC.md section 4.5
    "breakeven_ttf",
    "breakeven_gas_usd_mmbtu",
    "breakeven_crack",
    "percentile_rank",
    "Outputs",
    "outputs",
]


# ---------------------------------------------------------------------------
# The vocabulary. Units, windows and bases, named once.
# ---------------------------------------------------------------------------

#: A price in dollars per barrel. The OPEC MOMR Rotterdam table is already this,
#: so it needs no conversion, SPEC.md section 4.2.
USD_PER_BBL = "usd_per_bbl"

#: A price in dollars per tonne. Every DGEC quotation is this, so it needs a
#: cited barrels per tonne factor before it can meet a $/bbl crude price.
USD_PER_T = "usd_per_t"

UNITS = (USD_PER_BBL, USD_PER_T)

DAILY = "daily"
WEEKLY = "weekly"
MONTHLY = "monthly"

#: The averaging windows a crack leg can carry. SPEC.md section 4.2 requires
#: both legs of a crack to share one, so the window is part of an observation
#: rather than a property of the file it came from.
WINDOWS = (DAILY, WEEKLY, MONTHLY)

#: The product leg arrived in $/bbl and was used as it stands.
BASIS_DIRECT = "usd_per_bbl_direct"

#: The product leg arrived in $/t and was divided by a cited factor.
BASIS_CONVERTED = "usd_per_t_converted"

#: The gas price was built from TTF in EUR/MWh through the SPEC.md section 4.4
#: chain, which needs EUR/USD.
GAS_BASIS_TTF = "ttf_eur_mwh"

#: The gas price arrived already in $/MMBtu, which is what the World Bank pink
#: sheet Europe series publishes, so no chain runs at all.
GAS_BASIS_PUBLISHED = "published_usd_mmbtu"

#: The margin is gross of purchased natural gas, so SPEC.md section 4.4's
#: subtraction applies to it. This is a margin built here, from cracks and
#: yields, with no energy cost inside it yet.
MARGIN_GROSS_OF_GAS = "gross_of_gas"

#: The margin ALREADY has the gas purchase inside it and nothing may subtract a
#: gas cost from it again.
#:
#: DGEC's published MBR is this one. Section 3 of its methodology note
#: subtracts "les couts d'achat du Brent date FAB et du gaz naturel CAF" from
#: the product revenues, table 1 carries natural gas at 1.0 percent of the tonne
#: as an INPUT, and the indicator is called "marge de raffinage sur couts
#: energetiques". config.MBR_GAS_BASIS_NOTE carries the whole reading.
#:
#: SPEC.md section 4.4 writes margin_after_gas = margin_gross - gas_cost -
#: other_variable_cost and SPEC.md section 4.3 layer 1 calls the MBR a gross
#: margin. Both are true of a margin this study builds itself and only the
#: second is true of the MBR, so the basis travels ON the margin rather than in
#: a comment, and evaluate() refuses the combination that would charge the same
#: barrel twice.
MARGIN_NET_OF_GAS = "net_of_gas"

MARGIN_BASES = (MARGIN_GROSS_OF_GAS, MARGIN_NET_OF_GAS)


class UnitError(ValueError):
    """A price met a factor it should not have met, or one it needed and lacked.

    Raised rather than absorbed, because every case it covers is a coding error
    in the caller and every one of them would otherwise produce a plausible
    number about seven times too large or too small.
    """


class AlignmentError(ValueError):
    """Two legs of a crack did not share a date or an averaging window.

    SPEC.md section 4.2: "Never a weekly product against a monthly crude." The
    Gate 2 brief asks for that to be structurally impossible rather than a
    convention, so it is this exception rather than a docstring.
    """


class GasDoubleCountError(ValueError):
    """A gas cost was about to be subtracted from a margin that already has one.

    The Gate 2 self audit, finding 1: series.margin_after_gas_monthly took
    DGEC's published MBR, which is already net of the natural gas the method
    assumes the refinery buys, and subtracted this study's own gas cost from it
    again. The fix is not a comment. A margin carries its basis, MARGIN_NET_OF_GAS
    or MARGIN_GROSS_OF_GAS, and this exception is what a caller gets for the
    combination that would charge the barrel twice.

    It is a refusal rather than a silent zero on purpose. Returning the margin
    unchanged would let a caller believe a deduction had happened, and printing
    a number nobody asked a question about is how the first version of this got
    into the repository.
    """


def _is_missing(x: float) -> bool:
    """NaN, and nothing else. None is not a number and never reaches here."""
    return x != x


# ---------------------------------------------------------------------------
# SPEC.md section 4.2, cracks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Quote:
    """One price observation, with everything needed to use it safely.

    The date and the window travel WITH the price rather than alongside it,
    which is what makes SPEC.md section 4.2's alignment rule enforceable: a
    function that takes two Quotes can check them, a function that takes two
    floats cannot.

    Attributes:
        value: the price. NaN when the source published none.
        unit: one of UNITS.
        date: the observation label, ISO 'YYYY-MM-DD'. For a monthly average it
            is the first day of the month, for a weekly average the Friday the
            source itself labels the week with. It is a label, not a timestamp,
            and it is compared as a string.
        window: one of WINDOWS, the averaging window the value represents.
        label: the source's own name for the product, kept verbatim. SPEC.md
            section 4.2: "Product definitions follow the source's own labels".
            DGEC's Gazole is road diesel and its Eurosuper is finished premium
            gasoline, and neither is a futures contract, so this field carries
            what the source called it and the site prints that.
    """

    value: float
    unit: str
    date: str
    window: str
    label: str = ""

    def __post_init__(self) -> None:
        if self.unit not in UNITS:
            raise UnitError(
                "quote %r carries unit %r, not one of %s"
                % (self.label or self.date, self.unit, ", ".join(UNITS))
            )
        if self.window not in WINDOWS:
            raise AlignmentError(
                "quote %r carries window %r, not one of %s"
                % (self.label or self.date, self.window, ", ".join(WINDOWS))
            )
        if not isinstance(self.date, str) or len(self.date) != 10:
            raise AlignmentError(
                "quote %r carries date %r. Dates are ISO 'YYYY-MM-DD' strings "
                "here, because they are compared for equality and a datetime "
                "that differs by a timezone would compare unequal to an "
                "identical day" % (self.label, self.date)
            )
        # A price is a number or it is nothing. Gate 2 self audit, finding 8,
        # rows 1 to 3: JSON writes a missing price as null, and Number(null) is
        # 0 in JavaScript, so a browser handed an artifact with a hole in it was
        # cracking a 0 $/bbl price while the pipeline raised. Both engines now
        # refuse anything that is not a number, and NaN, which IS a number and
        # is how SPEC.md section 2 rule 1 carries a missing observation, still
        # goes through untouched.
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise UnitError(
                "quote %r carries value %r, which is not a number. A missing "
                "price is NaN, SPEC.md section 2 rule 1, and null, an empty "
                "string and a string of digits are all refused here so that "
                "src/engine.js cannot read one of them as zero"
                % (self.label or self.date, self.value)
            )
        object.__setattr__(self, "value", float(self.value))


def to_usd_bbl(quote: Quote, bbl_per_t: float | None = None) -> float:
    """One quote in dollars per barrel, converting only if it has to.

    Args:
        quote: the observation.
        bbl_per_t: the cited barrels per tonne factor. REQUIRED when the quote
            is in $/t and REFUSED when it is already in $/bbl. Both halves of
            that rule raise, because both mistakes are silent and both are worth
            several dollars a barrel.

    Raises:
        UnitError: on a missing factor, an unwanted factor, or a factor of zero.
    """
    if quote.unit == USD_PER_BBL:
        if bbl_per_t is not None:
            raise UnitError(
                "quote %r is already in %s and was handed a barrels per tonne "
                "factor of %r. The OPEC Rotterdam table is quoted in dollars "
                "per barrel and dividing it again is exactly the error SPEC.md "
                "section 9's Units row exists to catch"
                % (quote.label or quote.date, USD_PER_BBL, bbl_per_t)
            )
        return quote.value
    if bbl_per_t is None:
        raise UnitError(
            "quote %r is in %s and no barrels per tonne factor was given. "
            "SPEC.md section 4.1: never guess a factor"
            % (quote.label or quote.date, USD_PER_T)
        )
    return _usd_t_to_usd_bbl(quote.value, bbl_per_t)


def _usd_t_to_usd_bbl(price_usd_t: float, bbl_per_t: float) -> float:
    if bbl_per_t == 0.0:
        raise UnitError(
            "a barrels per tonne factor of zero has no meaning. Python would "
            "raise here and JavaScript would return Infinity, so both engines "
            "refuse it rather than disagree, SPEC.md section 7.1"
        )
    return price_usd_t / bbl_per_t


def _require_leg(leg: Quote, role: str) -> None:
    """One leg carries an averaging window and a date, or it is not a leg.

    getattr rather than attribute access, so an object that simply has no window
    is refused with the same AlignmentError in both engines rather than an
    AttributeError here and a silent number in the browser.
    """
    window = getattr(leg, "window", None)
    date = getattr(leg, "date", None)
    if window not in WINDOWS:
        raise AlignmentError(
            "the %s leg carries window %r, not one of %s. SPEC.md section 4.2 "
            "compares the two legs' windows, and a leg with no window would "
            "compare equal to another leg with no window"
            % (role, window, ", ".join(WINDOWS))
        )
    if not isinstance(date, str) or len(date) != 10:
        raise AlignmentError(
            "the %s leg carries date %r. SPEC.md section 4.2 compares the two "
            "legs' dates and they are ISO 'YYYY-MM-DD' strings here"
            % (role, date)
        )


def require_aligned(product: Quote, brent: Quote) -> None:
    """Refuse two legs that do not share a date and an averaging window.

    SPEC.md section 4.2 and the Gate 2 brief. This is the whole of the
    Alignment row of SPEC.md section 9 and it is one function so that there is
    exactly one place where the rule can be weakened.

    Both legs are checked for a window and a date BEFORE they are compared. A
    Quote cannot be built without them, so for a Quote this is a no op. It is
    here for the leg that is not a Quote: src/engine.js accepts any object, and
    before Gate 2 it cracked two objects with no window and no date at all,
    because undefined !== undefined is false. That is the Gate 2 self audit's
    finding 5, and the guarantee SPEC.md section 4.2 asks to be structural
    cannot be structural in one engine and duck typed in the other, so the check
    lives in the one function both engines route through.

    Raises:
        AlignmentError: naming both legs, both dates and both windows, because
            the interesting question when this fires is which series was
            resampled by mistake.
    """
    _require_leg(product, "product")
    _require_leg(brent, "brent")
    if product.window != brent.window:
        raise AlignmentError(
            "cannot crack a %s product (%s, %s) against a %s crude (%s, %s). "
            "SPEC.md section 4.2: both legs share the same averaging window, "
            "weekly with weekly, monthly with monthly"
            % (
                product.window,
                product.label or "product",
                product.date,
                brent.window,
                brent.label or "brent",
                brent.date,
            )
        )
    if product.date != brent.date:
        raise AlignmentError(
            "cannot crack %s dated %s against %s dated %s. SPEC.md section 4.2: "
            "both legs share the same date"
            % (
                product.label or "product",
                product.date,
                brent.label or "brent",
                brent.date,
            )
        )


def crack_from_usd_t(
    price_usd_t: float, bbl_per_t: float, brent_usd_bbl: float
) -> float:
    """SPEC.md section 4.2, the $/t path: p / bbl_per_t minus Brent.

    745 $/t of gasoil at 7.45 bbl/t against Brent at 80 $/bbl is exactly 20, and
    833 $/t of gasoline at 8.33 against the same Brent is exactly 20 too. Both
    are exact in IEEE 754 double precision and tests/test_units.py asserts them
    with equality rather than a tolerance.
    """
    return _usd_t_to_usd_bbl(price_usd_t, bbl_per_t) - brent_usd_bbl


def crack_from_usd_bbl(price_usd_bbl: float, brent_usd_bbl: float) -> float:
    """SPEC.md section 4.2, the $/bbl path: no conversion at all.

    The OPEC MOMR Rotterdam table, which is this study's crack source back to
    2000, is published in dollars per barrel. This function exists separately
    from crack_from_usd_t so that a caller has to say which kind of price it
    holds, and so that the result can record which path produced it.
    """
    return price_usd_bbl - brent_usd_bbl


@dataclass(frozen=True)
class Crack:
    """One crack, with its date, its window and the path that produced it.

    The provenance fields are not decoration. A gasoil crack computed from an
    OPEC $/bbl row and one computed from a DGEC $/t row are different numbers
    on different specifications, and the site has to be able to say which it is
    showing without asking the caller to remember.
    """

    value: float
    date: str
    window: str
    product_label: str
    product_usd_bbl: float
    brent_usd_bbl: float
    product_basis: str
    product_bbl_per_t: float | None
    brent_bbl_per_t: float | None


def crack(
    product: Quote,
    brent: Quote,
    *,
    product_bbl_per_t: float | None = None,
    brent_bbl_per_t: float | None = None,
) -> Crack:
    """The safe front door. Both paths, the alignment check, and the provenance.

    Args:
        product: the product leg, in either unit.
        brent: the crude leg, in either unit. The DGEC weekly note prints Brent
            date in $/t, so this leg needs a factor as often as the product one
            does, and it is a DIFFERENT factor: config.DGEC_BBL_PER_T_BRENT_NOTE
            is 7.5 for the note's own column and never 7.45.
        product_bbl_per_t: cited factor for the product leg, required only when
            the product is in $/t.
        brent_bbl_per_t: cited factor for the crude leg, same rule.

    Returns:
        A Crack carrying the value, both legs in $/bbl, the date, the window and
        which path each leg took.

    Raises:
        AlignmentError: if the two legs disagree about the date or the window.
        UnitError: if either leg met the wrong factor, or none.
    """
    require_aligned(product, brent)
    product_usd_bbl = to_usd_bbl(product, product_bbl_per_t)
    brent_usd_bbl = to_usd_bbl(brent, brent_bbl_per_t)
    return Crack(
        value=product_usd_bbl - brent_usd_bbl,
        date=product.date,
        window=product.window,
        product_label=product.label,
        product_usd_bbl=product_usd_bbl,
        brent_usd_bbl=brent_usd_bbl,
        product_basis=(
            BASIS_DIRECT if product.unit == USD_PER_BBL else BASIS_CONVERTED
        ),
        product_bbl_per_t=product_bbl_per_t,
        brent_bbl_per_t=brent_bbl_per_t,
    )


def crack_values(cracks: Mapping[str, Crack]) -> Mapping[str, float]:
    """Strip a set of Cracks down to floats, refusing a set that is misaligned.

    The alignment rule of SPEC.md section 4.2 is about one crack's two legs, but
    a decomposition multiplies several cracks by several yields and adds them
    into one margin, so those cracks have to share a date and a window with each
    other as well. This is where that is checked, and it is the reason the
    decomposition takes its cracks through a function rather than as a bare
    mapping.

    Raises:
        AlignmentError: naming the two products that disagree.
    """
    items = sorted(cracks.items())
    if not items:
        return MappingProxyType({})
    first_name, first = items[0]
    for name, other in items[1:]:
        if other.window != first.window or other.date != first.date:
            raise AlignmentError(
                "cracks in one decomposition must share a date and a window: "
                "%s is %s %s but %s is %s %s"
                % (
                    first_name,
                    first.window,
                    first.date,
                    name,
                    other.window,
                    other.date,
                )
            )
    return MappingProxyType({name: c.value for name, c in items})


# ---------------------------------------------------------------------------
# Yields
# ---------------------------------------------------------------------------


def mass_yield_to_volume_yield(
    mass_yield: float, bbl_per_t_product: float, bbl_per_t_crude: float
) -> float:
    """Tonnes of product per tonne of crude into barrels per barrel.

    THE QUIET UNIT ERROR IN SPEC.md SECTION 4.5. It writes contribution[p] =
    yield[p] * crack[p] with the crack in $/bbl of crude, which needs a
    volumetric yield. DGEC's table 1, the only published slate this project has,
    is MASS yields. The two differ by the ratio of the two conversion factors:

        volume yield = mass yield * bbl_per_t_product / bbl_per_t_crude

    For gasoil that ratio is 7.45 / 7.55, so a 34.0 percent mass yield is a
    33.55 percent volumetric one, about 1.3 percent smaller. On a 20 $/bbl crack
    that is 0.09 $/bbl, which is small, and it is exactly the kind of small that
    accumulates silently across five products and then gets blamed on the
    residual.

    Both factors are required arguments with no defaults, because a product
    whose factor this project cannot cite must not be converted at all: it stays
    out of the decomposition and lands on the residual line with its name
    attached, which is what SPEC.md section 4.3 layer 3 asks for.
    """
    if bbl_per_t_crude == 0.0:
        raise UnitError("a crude barrels per tonne factor of zero has no meaning")
    return mass_yield * bbl_per_t_product / bbl_per_t_crude


@dataclass(frozen=True)
class ObservedYields:
    """JODI yields on one stated denominator, with the sum that gives it away.

    SPEC.md section 4.3 layer 4 asks for yields from JODI refinery output over
    refinery intake. Recon 03 section 1.8 measured that this sums to 1.13 to
    1.16 rather than to 1, because JODI's numerator is gross output from all
    refinery feed while its denominator is crude alone, and it refused to pick a
    fix. So this record carries the basis it was built on and the sum of its own
    lines, and the site shows both bases rather than choosing one quietly.

    Attributes:
        yields: product to yield, on the stated basis.
        total: the sum of the lines. On YIELD_BASIS_CRUDE_INTAKE expect about
            1.13 to 1.16, on YIELD_BASIS_TOTAL_FEED about 1.01 to 1.03, and on
            YIELD_BASIS_NORMALISED exactly 1 up to floating point.
        basis: one of config.YIELD_BASES.
        denominator_kbd: the denominator actually used, in kb/d, so that a
            reader can recompute any line.
        note: config.YIELD_BASIS_NOTES for this basis, carried with the data so
            a JSON artifact cannot lose it.
    """

    yields: Mapping[str, float]
    total: float
    basis: str
    denominator_kbd: float
    note: str

    def normalised(self) -> "ObservedYields":
        """The same vector scaled to sum to 1, relabelled as a share of output.

        Returns a new record on YIELD_BASIS_NORMALISED. It is a share of output,
        not a yield on crude, and the basis field is what says so.
        """
        if self.total == 0.0 or _is_missing(self.total):
            scaled = {name: math.nan for name in self.yields}
            total = math.nan
        else:
            scaled = {name: v / self.total for name, v in self.yields.items()}
            total = sum(scaled[name] for name in sorted(scaled))
        return ObservedYields(
            yields=MappingProxyType(dict(sorted(scaled.items()))),
            total=total,
            basis=config.YIELD_BASIS_NORMALISED,
            denominator_kbd=self.denominator_kbd,
            note=config.YIELD_BASIS_NOTES[config.YIELD_BASIS_NORMALISED],
        )


def observed_yields(
    output_kbd: Mapping[str, float],
    denominator_kbd: float,
    basis: str,
) -> ObservedYields:
    """SPEC.md section 4.3 layer 4. Output by product over a named denominator.

    Args:
        output_kbd: JODI REFGROUT by product, kb/d, summed over BE, DE, FR, NL
            and GB by the caller. The twelve month rolling average SPEC.md
            section 4.3 layer 4 asks for is applied to the inputs before they
            arrive here, in crack.series, because a rolling window is series
            plumbing and this module holds no series.
        denominator_kbd: crude intake for YIELD_BASIS_CRUDE_INTAKE, total
            refinery feed for YIELD_BASIS_TOTAL_FEED.
        basis: one of config.YIELD_BASES. YIELD_BASIS_NORMALISED is reached by
            building on crude intake and calling normalised(), so passing it
            here is refused rather than silently accepted.

    Beware JETKERO. Recon 03 section 1.5: JODI's TOTPRODS excludes JETKERO,
    which sits inside KEROSENE, so summing product lines that include both
    double counts jet. That is a question about which keys the caller passes,
    and it is stated here because this is where somebody will be looking when
    the sum comes out wrong.
    """
    if basis not in (config.YIELD_BASIS_CRUDE_INTAKE, config.YIELD_BASIS_TOTAL_FEED):
        raise ValueError(
            "observed_yields builds on a JODI denominator, so basis must be %r "
            "or %r. %r is reached by calling normalised() on one of those, which "
            "keeps the relabelling and the arithmetic together"
            % (
                config.YIELD_BASIS_CRUDE_INTAKE,
                config.YIELD_BASIS_TOTAL_FEED,
                basis,
            )
        )
    if denominator_kbd == 0.0:
        raise ValueError(
            "a refinery denominator of zero kb/d is not a refinery. A month with "
            "no reported intake is NaN, not zero, SPEC.md section 2 rule 1"
        )
    names = sorted(output_kbd)
    values = {name: output_kbd[name] / denominator_kbd for name in names}
    total = 0.0
    for name in names:
        total += values[name]
    return ObservedYields(
        yields=MappingProxyType(values),
        total=total,
        basis=basis,
        denominator_kbd=denominator_kbd,
        note=config.YIELD_BASIS_NOTES[basis],
    )


# ---------------------------------------------------------------------------
# SPEC.md section 4.4, run economics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GasCost:
    """A gas price in $/MMBtu and the path it arrived by.

    Two paths reach the same unit and they are not interchangeable:

        GAS_BASIS_TTF        ttf_eur_mwh * eurusd / MMBTU_PER_MWH, the SPEC.md
                             section 4.4 chain. Only this path supports
                             breakeven_ttf, because only this path knows what a
                             euro is worth.
        GAS_BASIS_PUBLISHED  the World Bank pink sheet Europe series, which is
                             ALREADY $/MMBtu, recon 04 section 4.1. Running it
                             through the chain would divide a dollar figure by
                             3.41 for no reason.
    """

    gas_usd_mmbtu: float
    basis: str
    ttf_eur_mwh: float | None = None
    eurusd: float | None = None


def gas_from_ttf(ttf_eur_mwh: float, eurusd: float) -> GasCost:
    """SPEC.md section 4.4: gas_usd_mmbtu = ttf_eur_mwh * eurusd / MMBTU_PER_MWH."""
    return GasCost(
        gas_usd_mmbtu=ttf_eur_mwh * eurusd / config.MMBTU_PER_MWH,
        basis=GAS_BASIS_TTF,
        ttf_eur_mwh=ttf_eur_mwh,
        eurusd=eurusd,
    )


def gas_from_usd_mmbtu(gas_usd_mmbtu: float) -> GasCost:
    """The published path. No FX, no factor, nothing to get wrong."""
    return GasCost(
        gas_usd_mmbtu=gas_usd_mmbtu,
        basis=GAS_BASIS_PUBLISHED,
        ttf_eur_mwh=None,
        eurusd=None,
    )


def gas_cost_usd_bbl(
    gas_intensity_mmbtu_per_bbl: float, gas_usd_mmbtu: float
) -> float:
    """SPEC.md section 4.4: gas_cost = gas_intensity * gas_usd_mmbtu."""
    return gas_intensity_mmbtu_per_bbl * gas_usd_mmbtu


@dataclass(frozen=True)
class GasWedge:
    """Two gas intensities priced at one gas price, next to each other.

    THIS IS THE HONEST VERSION OF SPEC.md SECTION 4.4 FOR DGEC'S MBR, and it is
    what replaced a subtraction that was wrong on this series. The MBR already
    contains DGEC's own gas purchase, one percent of the tonne of crude bought
    at PEG Nord day ahead plus a GRTgaz transport tariff, so this study cannot
    deduct its own gas cost from it. What it can do, and what a refining analyst
    actually wants, is say how big DGEC's embedded assumption is and how it
    compares with the intensity this study derived from EIA:

        embedded_cost_usd_bbl = embedded_intensity * gas_usd_mmbtu
        study_cost_usd_bbl    = study_intensity    * gas_usd_mmbtu
        wedge_usd_bbl         = study_cost - embedded_cost

    A positive wedge means a refinery buying gas at this study's intensity pays
    more for it than DGEC's model refinery does, so the published margin
    flatters such a refinery by the wedge. It is a comparison, never a line of
    the margin, and nothing in evaluate() reads it.

    Attributes:
        gas_usd_mmbtu: the one gas price both sides are priced at.
        embedded_intensity_mmbtu_per_bbl: the margin's own assumption. For the
            MBR, config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL, 0.0659.
        study_intensity_mmbtu_per_bbl: this study's derived figure, 0.21217.
        embedded_cost_usd_bbl, study_cost_usd_bbl: each intensity at that price.
        wedge_usd_bbl: study minus embedded.
        ratio: study over embedded, or NaN when the embedded intensity is zero.
            A pure number, so it does not move with the gas price.
    """

    gas_usd_mmbtu: float
    embedded_intensity_mmbtu_per_bbl: float
    study_intensity_mmbtu_per_bbl: float
    embedded_cost_usd_bbl: float
    study_cost_usd_bbl: float
    wedge_usd_bbl: float
    ratio: float


def gas_wedge(
    gas_usd_mmbtu: float,
    embedded_intensity_mmbtu_per_bbl: float,
    study_intensity_mmbtu_per_bbl: float = config.GAS_INTENSITY_MMBTU_PER_BBL,
) -> GasWedge:
    """Price two gas intensities at one gas price and report both, plus the gap.

    No subtraction from any margin happens here. That is the whole point: this
    function exists so that the gas story can be told about a margin that is
    already net of gas, without the deduction the Gate 2 self audit found.
    """
    embedded_cost = gas_cost_usd_bbl(embedded_intensity_mmbtu_per_bbl, gas_usd_mmbtu)
    study_cost = gas_cost_usd_bbl(study_intensity_mmbtu_per_bbl, gas_usd_mmbtu)
    ratio = (
        math.nan
        if embedded_intensity_mmbtu_per_bbl == 0.0
        else study_intensity_mmbtu_per_bbl / embedded_intensity_mmbtu_per_bbl
    )
    return GasWedge(
        gas_usd_mmbtu=gas_usd_mmbtu,
        embedded_intensity_mmbtu_per_bbl=embedded_intensity_mmbtu_per_bbl,
        study_intensity_mmbtu_per_bbl=study_intensity_mmbtu_per_bbl,
        embedded_cost_usd_bbl=embedded_cost,
        study_cost_usd_bbl=study_cost,
        wedge_usd_bbl=study_cost - embedded_cost,
        ratio=ratio,
    )


@dataclass(frozen=True)
class MarginInputs:
    """Everything the margin is computed from, in one record.

    Attributes:
        yields: product to VOLUMETRIC yield, barrels of product per barrel of
            crude. Mass yields must go through mass_yield_to_volume_yield first.
        cracks: product to crack in $/bbl. The keys must match yields exactly,
            because a product with a yield and no crack, or the reverse, is a
            decomposition that silently does not add up.
        residual_usd_bbl: the part of the margin no product line explains.
            SPEC.md section 4.3 layer 3: it is always shown and never spread
            across products. It defaults to zero, which is what makes the
            SPEC.md section 9 Null row exact.
        gas: a GasCost.
        gas_intensity_mmbtu_per_bbl: MMBtu of purchased gas per barrel of crude.
            Derived in config.py from EIA tables and editable on the Model view,
            SPEC.md section 4.4.
        other_variable_cost_usd_bbl: defaults to zero and is labelled. Carbon is
            out of scope for this version and is a stated limitation rather than
            a number quietly folded into this line, SPEC.md section 4.4.
        run_cut_threshold_usd_bbl: SPEC.md section 6.2's threshold, which is
            Gate 3 work and is allowed to come out unidentified. None here means
            unidentified, and None propagates into the headroom and the
            breakevens rather than being replaced by a plausible number.
        margin_basis: MARGIN_GROSS_OF_GAS or MARGIN_NET_OF_GAS. It says whether
            the margin these lines add up to already has the refinery's gas
            purchase inside it. MARGIN_GROSS_OF_GAS is the default because a
            margin assembled here out of cracks and yields is gross of
            everything. A margin that arrived already net of gas, which is what
            DGEC publishes, must say so, and then no gas cost may be subtracted
            from it: a gas price on a net margin raises GasDoubleCountError
            rather than quietly costing the barrel twice.
    """

    yields: Mapping[str, float]
    cracks: Mapping[str, float]
    gas: GasCost = field(default_factory=lambda: gas_from_usd_mmbtu(0.0))
    residual_usd_bbl: float = 0.0
    gas_intensity_mmbtu_per_bbl: float = config.GAS_INTENSITY_MMBTU_PER_BBL
    other_variable_cost_usd_bbl: float = config.OTHER_VARIABLE_COST_USD_BBL
    run_cut_threshold_usd_bbl: float | None = None
    margin_basis: str = MARGIN_GROSS_OF_GAS

    def __post_init__(self) -> None:
        if self.margin_basis not in MARGIN_BASES:
            raise ValueError(
                "margin_basis is %r, not one of %s. A margin has to say whether "
                "the gas purchase is already inside it"
                % (self.margin_basis, ", ".join(MARGIN_BASES))
            )
        if self.margin_basis == MARGIN_NET_OF_GAS:
            # Not "is it small", and not "is it finite". The gas term on a
            # margin that already contains one has to be EXACTLY zero, so a NaN
            # gas price piped in from a series fails here too: a NaN would
            # otherwise propagate into a margin that is in fact complete.
            term = self.gas_intensity_mmbtu_per_bbl * self.gas.gas_usd_mmbtu
            if not (term == 0.0):
                raise GasDoubleCountError(
                    "this margin is %s, so it already contains the refinery's "
                    "gas purchase, and it was handed %r MMBtu per barrel at "
                    "%r $/MMBtu. Subtracting that would charge the same barrel "
                    "for gas twice. Put the gas price through gas_wedge() "
                    "instead, which compares the two intensities at one price "
                    "without deducting either"
                    % (
                        MARGIN_NET_OF_GAS,
                        self.gas_intensity_mmbtu_per_bbl,
                        self.gas.gas_usd_mmbtu,
                    )
                )
        yields = dict(self.yields)
        cracks = dict(self.cracks)
        if set(yields) != set(cracks):
            missing_crack = sorted(set(yields) - set(cracks))
            missing_yield = sorted(set(cracks) - set(yields))
            raise ValueError(
                "every product needs both a yield and a crack. Yields with no "
                "crack: %s. Cracks with no yield: %s"
                % (missing_crack or "none", missing_yield or "none")
            )
        object.__setattr__(self, "yields", MappingProxyType(dict(sorted(yields.items()))))
        object.__setattr__(self, "cracks", MappingProxyType(dict(sorted(cracks.items()))))

    @property
    def products(self) -> Sequence[str]:
        """The product keys in the order every sum in this module uses them.

        Sorted, and sorted for a reason that is about SPEC.md section 7.1 rather
        than about tidiness: floating point addition is not associative, so the
        Python and the JavaScript engines have to add the contributions in the
        same order or they will disagree in the last bits. Sorted ASCII keys
        give the same order in both languages, and Object.keys(...).sort() in
        src/engine.js is the mirror of this line.
        """
        return tuple(self.yields)


@dataclass(frozen=True)
class MarginResult:
    """Every line of SPEC.md section 4.4, separately, plus the total.

    No function in this module returns a margin without the lines that made it.
    The first thing a refining analyst does with a margin is disagree with one
    line of it, and a total they cannot take apart is a number they have to
    take on trust.
    """

    contributions: Mapping[str, float]
    attributed_usd_bbl: float
    residual_usd_bbl: float
    gross_margin_usd_bbl: float
    gas_usd_mmbtu: float
    gas_cost_usd_bbl: float
    other_variable_cost_usd_bbl: float
    margin_after_gas_usd_bbl: float
    carrier: str | None
    carrier_contribution_usd_bbl: float
    run_cut_threshold_usd_bbl: float | None
    threshold_identified: bool
    headroom_usd_bbl: float | None
    gas_basis: str
    margin_basis: str
    gas_already_in_margin: bool


def evaluate(inputs: MarginInputs) -> MarginResult:
    """The margin, line by line. SPEC.md sections 4.3 layer 3, 4.4 and 4.5.

        contribution[p]  = yield[p] * crack[p]
        gross_margin     = sum of the contributions + residual
        gas_cost         = gas_intensity * gas_usd_mmbtu
        margin_after_gas = gross_margin - gas_cost - other_variable_cost
        headroom         = margin_after_gas - run_cut_threshold

    ON A MARGIN_NET_OF_GAS MARGIN THE GAS COST LINE IS ZERO, because the gas
    purchase is already inside the margin that arrived. It is not skipped
    quietly: MarginInputs refuses to hold a gas price on that basis at all, so
    by the time evaluate sees one the deduction has already been argued about.
    The margin after gas is then the margin itself less the other variable cost,
    which for DGEC's MBR is the right answer and is what the ministry means by
    "marge de raffinage sur couts energetiques".

    The sum runs over sorted product keys, left to right, so src/engine.js can
    reproduce it bit for bit.

    Missing data propagates: one NaN crack makes the attributed total, the gross
    margin and the margin after gas NaN, and the site shows a hole rather than a
    number that quietly dropped a product. The carrier is chosen among the
    contributions that are finite, so a missing minor product does not erase the
    answer to "which crack is carrying the barrel".

    The headroom is None, not NaN, when no threshold was given. The difference
    matters: NaN means the data is missing, None means SPEC.md section 6.2 found
    no threshold in the sample and the site falls back to the ten year
    percentile, which is a finding rather than a gap.
    """
    contributions = {
        name: inputs.yields[name] * inputs.cracks[name] for name in inputs.products
    }
    attributed = 0.0
    for name in inputs.products:
        attributed += contributions[name]

    gross = attributed + inputs.residual_usd_bbl
    already_net = inputs.margin_basis == MARGIN_NET_OF_GAS
    gas_cost = (
        0.0
        if already_net
        else gas_cost_usd_bbl(
            inputs.gas_intensity_mmbtu_per_bbl, inputs.gas.gas_usd_mmbtu
        )
    )
    after_gas = gross - gas_cost - inputs.other_variable_cost_usd_bbl

    carrier, carrier_value = _carrier(contributions, inputs.products)

    threshold = inputs.run_cut_threshold_usd_bbl
    identified = threshold is not None
    headroom = after_gas - threshold if identified else None

    return MarginResult(
        contributions=MappingProxyType(contributions),
        attributed_usd_bbl=attributed,
        residual_usd_bbl=inputs.residual_usd_bbl,
        gross_margin_usd_bbl=gross,
        gas_usd_mmbtu=inputs.gas.gas_usd_mmbtu,
        gas_cost_usd_bbl=gas_cost,
        other_variable_cost_usd_bbl=inputs.other_variable_cost_usd_bbl,
        margin_after_gas_usd_bbl=after_gas,
        carrier=carrier,
        carrier_contribution_usd_bbl=carrier_value,
        run_cut_threshold_usd_bbl=threshold,
        threshold_identified=identified,
        headroom_usd_bbl=headroom,
        gas_basis=inputs.gas.basis,
        margin_basis=inputs.margin_basis,
        gas_already_in_margin=already_net,
    )


def _carrier(
    contributions: Mapping[str, float], products: Sequence[str]
) -> tuple[str | None, float]:
    """The product with the largest contribution, SPEC.md section 4.5.

    Ties go to the first key in sorted order, which is arbitrary but identical
    in both engines. A NaN contribution cannot win, and when every contribution
    is NaN the carrier is None and its value NaN, because "which crack is
    carrying the barrel" has no answer that month and the site says so.
    """
    best_name: str | None = None
    best_value = math.nan
    for name in products:
        value = contributions[name]
        if _is_missing(value):
            continue
        if best_name is None or value > best_value:
            best_name = name
            best_value = value
    return best_name, best_value


# ---------------------------------------------------------------------------
# SPEC.md section 4.3 layer 3, the decomposition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Decomposition:
    """The official margin taken apart, with the residual always present.

    SPEC.md section 4.3 layer 3: "Anything not attributable sits on a residual
    line, never silently spread across products." The residual here is solved,
    not fitted: it is whatever the official margin has left after the product
    lines, and it carries the sign it comes out with.

    Attributes:
        official_usd_bbl: DGEC's published MBR, untouched. Layer 1 of SPEC.md
            section 4.3 is never overwritten and this field is the proof.
        contributions: yield[p] * crack[p] per product.
        attributed_usd_bbl: their sum.
        residual_usd_bbl: official minus attributed.
        residual_share: the residual over the official margin, or NaN when the
            official margin is zero. A diagnostic, not a line of the model.
        unattributed_products: products the slate contains and this
            decomposition could not price, named. Recon 02 section 5.6 lists
            five of DGEC's ten product quotations as unpublished, so this
            tuple is normally not empty, and an empty one would be the
            surprising case.
        covered_volume_yield: the yield mass the priced products account for,
            so the reader can see how much of the barrel the attributed figure
            speaks for.
    """

    official_usd_bbl: float
    contributions: Mapping[str, float]
    attributed_usd_bbl: float
    residual_usd_bbl: float
    residual_share: float
    carrier: str | None
    carrier_contribution_usd_bbl: float
    unattributed_products: Sequence[str]
    covered_volume_yield: float


def decompose_official(
    official_usd_bbl: float,
    yields: Mapping[str, float],
    cracks: Mapping[str, float],
    *,
    unattributed_products: Iterable[str] = (),
) -> Decomposition:
    """Attribute a published margin to products and put the rest on one line.

    Args:
        official_usd_bbl: the published MBR for the month, in $/bbl. Carried
            through untouched.
        yields: volumetric yields for the products that CAN be priced.
        cracks: their cracks, in $/bbl, all sharing a date and a window. Use
            crack_values to get this mapping out of a set of Cracks, which is
            where that is enforced.
        unattributed_products: the names of slate lines this decomposition could
            not price, so the residual can be reported with the reason rather
            than as a mystery.
    """
    inputs = MarginInputs(yields=yields, cracks=cracks)
    contributions = {
        name: inputs.yields[name] * inputs.cracks[name] for name in inputs.products
    }
    attributed = 0.0
    covered = 0.0
    for name in inputs.products:
        attributed += contributions[name]
        covered += inputs.yields[name]

    residual = official_usd_bbl - attributed
    share = math.nan if official_usd_bbl == 0.0 else residual / official_usd_bbl
    carrier, carrier_value = _carrier(contributions, inputs.products)

    return Decomposition(
        official_usd_bbl=official_usd_bbl,
        contributions=MappingProxyType(contributions),
        attributed_usd_bbl=attributed,
        residual_usd_bbl=residual,
        residual_share=share,
        carrier=carrier,
        carrier_contribution_usd_bbl=carrier_value,
        unattributed_products=tuple(sorted(unattributed_products)),
        covered_volume_yield=covered,
    )


# ---------------------------------------------------------------------------
# SPEC.md section 4.3 layer 2, the replication attempt
# ---------------------------------------------------------------------------

#: Why the replication cannot reach the SPEC.md section 4.3 bar. Written here,
#: once, as data, because it is published on the Method view and quoted in
#: tests/test_engine.py, and a reason that lived in two places would eventually
#: disagree with itself.
REPLICATION_FAILURE_REASON = (
    "The DGEC method needs ten product quotations, a gas purchase cost and a "
    "freight cost. Five of the product quotations are never published: EuroBOB, "
    "essence export, naphta, propane and butane. The note prints Eurosuper, "
    "which is finished premium gasoline and a different product from the EuroBOB "
    "blendstock the method prices, so it is not a substitute. The PEG Nord day "
    "ahead gas price, the GRTgaz transport tariff and the Sullom Voe to Le Havre "
    "Aframax freight are not published in these documents either. Together the "
    "five missing product lines are 35.0 percent of the mass yield and the two "
    "missing costs are unbounded, so the 0.50 $/bbl bar of SPEC.md section 4.3 "
    "layer 2 cannot be met from published data. What is published covers 59.3 "
    "percent of the mass yield in four product lines, gazole, fioul domestique, "
    "fioul lourd 1 percent and carbureacteur, plus the sulphur line the method "
    "fixes at 100 $/t. SPEC.md section 4.3 layer 2 provides the fallback and "
    "this study takes it: name the missing inputs and use the official series. "
    "Nothing is tuned to close the gap. Recon 02 section 5.6."
)
# The 35.0 is propane 1.7 plus butane 1.2 plus naphta 8.2 plus EuroBOB 12.0 plus
# essence export 11.9, read off table 1 of the methodology note and carried in
# config.DGEC_MASS_YIELDS. This string said 33.0 until the Gate 2 self audit,
# finding 6, and 33.0 was impossible on the note's own arithmetic: the four
# published lines are 59.3 percent, the sulphur line is 0.2, and the note's
# products sum to 94.5. The note prints "Gazole 34,0%" and "FOD 8,2%" as
# separate lines, which is where a 33 could have come from and did not.


@dataclass(frozen=True)
class ReplicationAttempt:
    """What happened when the MBR was recomputed from published data.

    THIS IS A DELIBERATE, DOCUMENTED FAILURE AND IT IS A DELIVERABLE. SPEC.md
    section 4.3 layer 2 sets a 0.50 $/bbl bar and says that where an input is
    not published, name it and fall back to the official series. Recon 02
    section 5.6 established, from the method note's own input list, that seven
    inputs are unpublished. So the attempt runs, the error is reported as it
    comes, and the official series is what the site shows.

    Attributes:
        margin_usd_bbl: the full method with every input it names. NaN whenever
            an unpublished input is missing, which is every month, and that NaN
            is the honest answer rather than a failure of the code.
        partial_usd_bbl: the same arithmetic over the published inputs only,
            with the unpublished revenue and cost lines simply absent. It is
            NOT an estimate of the MBR and must never be shown as one. It is
            reported so the size and the sign of the gap are visible.
        covered_mass_yield: the mass yield the priced product lines cover.
        missing_inputs: every input the method needs and nobody publishes.
        official_usd_bbl: DGEC's figure, untouched.
        error_usd_bbl: margin_usd_bbl minus official. NaN by construction.
        partial_error_usd_bbl: partial_usd_bbl minus official. A real number,
            and a large one.
        within_bar: whether the method ran complete AND abs(error) is under the
            bar. False here, and it is False because the error is NaN rather
            than because it is large, which is a different and more honest kind
            of failure. It cannot be True while missing_inputs is non empty.
        reason: REPLICATION_FAILURE_REASON.
    """

    margin_usd_bbl: float
    partial_usd_bbl: float
    revenue_published_usd_t: float
    covered_mass_yield: float
    missing_inputs: Sequence[str]
    official_usd_bbl: float
    error_usd_bbl: float
    partial_error_usd_bbl: float
    bar_usd_bbl: float
    within_bar: bool
    reason: str


def replicate_mbr(
    quotations_usd_t: Mapping[str, float],
    brent_usd_t: float,
    official_usd_bbl: float,
    *,
    mass_yields: Mapping[str, float] = config.DGEC_MASS_YIELDS,
    bbl_per_t_brent: float = config.DGEC_BBL_PER_T_BRENT_MARGIN,
    freight_usd_t: float = math.nan,
    gas_cost_usd_t: float = math.nan,
    sulphur_usd_t: float = config.DGEC_SULPHUR_PRICE_USD_T,
) -> ReplicationAttempt:
    """Recompute the MBR from DGEC's own method, with what is published.

    The method, from the note, page 4, recon 02 section 5.5, verbatim in
    structure: from the product revenues subtract the cost of the Brent date
    FOB and of the CIF natural gas, the oil freight, and insurance and losses
    assessed at 0.3 percent of the Brent price and the freight together. The
    result is per tonne of crude and becomes $/bbl at 7.55 bbl/t, which is the
    factor the method itself states and is NOT the 7.5 the weekly note uses for
    its own Brent column.

        revenue_usd_t   = sum over products of mass_yield[p] * price[p]
        cost_usd_t      = brent + gas + freight + 0.003 * (brent + freight)
        margin_usd_bbl  = (revenue - cost) / 7.55

    Args:
        quotations_usd_t: whatever product prices the caller holds, in $/t, keyed
            by the method's own line names. Lines that are absent are absent:
            nothing is substituted, interpolated or proxied.
        brent_usd_t: Brent date in $/t.
        official_usd_bbl: DGEC's published figure for the same month.
        freight_usd_t: the Aframax freight. NaN by default because it is not
            published, and NaN is what carries that fact into the answer.
        gas_cost_usd_t: the gas purchase and transport cost per tonne of crude.
            NaN by default, same reason.
        sulphur_usd_t: the method fixes it at 100 $/t, so this one unpublished
            input is available and is used.

    Returns:
        A ReplicationAttempt. Read its docstring: the headline number is NaN on
        purpose.
    """
    priced = {}
    for name in sorted(mass_yields):
        if name in ("brent", "gaz_naturel", "combustible_interne_et_pertes"):
            # Inputs and losses, not revenue lines.
            continue
        if name == "soufre":
            priced[name] = sulphur_usd_t
            continue
        if name in quotations_usd_t:
            priced[name] = quotations_usd_t[name]

    revenue = 0.0
    covered = 0.0
    for name in sorted(priced):
        revenue += mass_yields[name] * priced[name]
        covered += mass_yields[name]

    insurance_and_loss = config.DGEC_INSURANCE_AND_LOSS_RATE * (
        brent_usd_t + freight_usd_t
    )
    cost_full = brent_usd_t + gas_cost_usd_t + freight_usd_t + insurance_and_loss
    margin_usd_bbl = _usd_t_to_usd_bbl(revenue - cost_full, bbl_per_t_brent)

    # The published only figure. The unpublished revenue lines and the two
    # unpublished costs are ABSENT rather than zero, and the insurance line is
    # taken on the Brent price alone because the freight it would otherwise
    # include is one of the missing inputs.
    cost_partial = brent_usd_t + config.DGEC_INSURANCE_AND_LOSS_RATE * brent_usd_t
    partial_usd_bbl = _usd_t_to_usd_bbl(revenue - cost_partial, bbl_per_t_brent)

    error = margin_usd_bbl - official_usd_bbl
    partial_error = partial_usd_bbl - official_usd_bbl

    # What is missing is measured from the call, not asserted from the registry.
    # A product line is missing when no price arrived for it; the two cost lines
    # are missing when the number that carries them is NaN. config.
    # DGEC_UNPUBLISHED_METHOD_INPUTS says which lines nobody publishes, and this
    # loop says which ones this particular call did without, so the day DGEC
    # starts publishing EuroBOB the tuple gets shorter by itself.
    missing = tuple(
        name
        for name in config.DGEC_UNPUBLISHED_METHOD_INPUTS
        if name in mass_yields and name not in quotations_usd_t
    )
    if _is_missing(freight_usd_t):
        missing = missing + ("aframax_freight_sullom_voe_le_havre",)
    if _is_missing(gas_cost_usd_t):
        missing = missing + ("peg_nord_gas_day_ahead", "grtgaz_transport_tariff")

    # A replication cannot pass while an input is missing. Gate 2 self audit,
    # finding 12: supply the two costs, price one product line out of ten, and
    # the old rule would have come back True with five products unpriced, on any
    # official figure that happened to be near the wrong answer. within_bar is
    # the pass flag of SPEC.md section 9's Replication row, so it now asserts
    # both halves: the arithmetic agreed AND it ran on the whole method.
    within = (
        not missing
        and (not _is_missing(error))
        and abs(error) <= config.REPLICATION_BAR_USD_BBL
    )

    return ReplicationAttempt(
        margin_usd_bbl=margin_usd_bbl,
        partial_usd_bbl=partial_usd_bbl,
        revenue_published_usd_t=revenue,
        covered_mass_yield=covered,
        missing_inputs=missing,
        official_usd_bbl=official_usd_bbl,
        error_usd_bbl=error,
        partial_error_usd_bbl=partial_error,
        bar_usd_bbl=config.REPLICATION_BAR_USD_BBL,
        within_bar=within,
        reason=REPLICATION_FAILURE_REASON,
    )


# ---------------------------------------------------------------------------
# SPEC.md section 4.5, the outputs
# ---------------------------------------------------------------------------


def breakeven_gas_usd_mmbtu(
    inputs: MarginInputs, threshold: float | None = None
) -> float | None:
    """The gas price at which margin_after_gas equals the threshold.

    CLOSED FORM, because the model is linear in the gas price, SPEC.md section
    4.5. Nothing here is solved numerically and nothing iterates:

        margin_after_gas = gross - intensity * gas - other
        threshold        = gross - intensity * gas* - other
        gas*             = (gross - other - threshold) / intensity

    Returns None when there is no threshold, which is SPEC.md section 6.2's
    unidentified case, and None when the intensity is zero, which is a refinery
    that buys no gas and therefore has no gas breakeven at all. None is not a
    failure and it is not NaN: it means the question has no answer, and the site
    prints words rather than a number.

    None as well on a MARGIN_NET_OF_GAS margin, and that one is a statement
    about the data rather than about the arithmetic: a margin that already
    contains its own gas purchase does not move when this study's gas price
    moves, so there is no gas price at which it reaches the threshold. The Model
    view's gas slider belongs on a margin this study builds itself, and on
    DGEC's series the question to ask instead is gas_wedge().
    """
    level = _threshold_or_none(inputs, threshold)
    if level is None:
        return None
    if inputs.margin_basis == MARGIN_NET_OF_GAS:
        return None
    if inputs.gas_intensity_mmbtu_per_bbl == 0.0:
        return None
    result = evaluate(inputs)
    return (
        result.gross_margin_usd_bbl
        - result.other_variable_cost_usd_bbl
        - level
    ) / inputs.gas_intensity_mmbtu_per_bbl


def breakeven_ttf(
    inputs: MarginInputs, threshold: float | None = None
) -> float | None:
    """The TTF price in EUR/MWh at which margin_after_gas equals the threshold.

    Closed form again, one step further down the SPEC.md section 4.4 chain:

        gas    = ttf * eurusd / MMBTU_PER_MWH
        ttf*   = (gross - other - threshold) * MMBTU_PER_MWH
                 / (intensity * eurusd)

    Returns None when the gas price did not come through the TTF path. The World
    Bank pink sheet Europe series is already in $/MMBtu and carries no exchange
    rate, so a TTF breakeven computed from it would need an FX rate this record
    does not hold, and inventing one is not on the table. Use
    breakeven_gas_usd_mmbtu on that path.

    tests/test_engine.py plugs the answer back in and asserts the margin after
    gas equals the threshold to 1e-9, which is the Round trip row of SPEC.md
    section 9.
    """
    level = _threshold_or_none(inputs, threshold)
    if level is None:
        return None
    if inputs.margin_basis == MARGIN_NET_OF_GAS:
        # Same reason as breakeven_gas_usd_mmbtu: the margin does not move with
        # the gas price, because the gas is already inside it.
        return None
    if inputs.gas.basis != GAS_BASIS_TTF or inputs.gas.eurusd is None:
        return None
    denominator = inputs.gas_intensity_mmbtu_per_bbl * inputs.gas.eurusd
    if denominator == 0.0:
        return None
    result = evaluate(inputs)
    return (
        (result.gross_margin_usd_bbl - result.other_variable_cost_usd_bbl - level)
        * config.MMBTU_PER_MWH
        / denominator
    )


def breakeven_crack(
    inputs: MarginInputs, product: str, threshold: float | None = None
) -> float | None:
    """The crack of one product at which margin_after_gas equals the threshold.

    Closed form, because the margin is linear in every crack:

        margin_after_gas = y[p] * c[p] + rest + residual - gas_cost - other
        c*[p]            = (threshold + gas_cost + other - residual - rest)
                           / y[p]

    where rest is the sum of the other products' contributions. SPEC.md section
    4.5 names breakeven_gasoil; this is the same function with the product as an
    argument, so the Model view can quote a gasoline breakeven too without a
    second copy of the arithmetic.

    Returns None when there is no threshold, and None when the product's yield
    is zero, because a product the refinery does not make cannot move the margin
    at any price.
    """
    if product not in inputs.yields:
        raise KeyError(
            "no product %r in this margin. Products: %s"
            % (product, ", ".join(inputs.products))
        )
    level = _threshold_or_none(inputs, threshold)
    if level is None:
        return None
    own_yield = inputs.yields[product]
    if own_yield == 0.0:
        return None

    rest = 0.0
    for name in inputs.products:
        if name == product:
            continue
        rest += inputs.yields[name] * inputs.cracks[name]

    # On a MARGIN_NET_OF_GAS margin this term is exactly zero already, because
    # MarginInputs refuses any other gas price on that basis. The crack
    # breakeven is still a real question there: the margin is linear in every
    # crack whether or not the gas is inside it.
    gas_cost = gas_cost_usd_bbl(
        inputs.gas_intensity_mmbtu_per_bbl, inputs.gas.gas_usd_mmbtu
    )
    return (
        level
        + gas_cost
        + inputs.other_variable_cost_usd_bbl
        - inputs.residual_usd_bbl
        - rest
    ) / own_yield


def _threshold_or_none(
    inputs: MarginInputs, threshold: float | None
) -> float | None:
    """The explicit threshold, else the one on the inputs, else None.

    SPEC.md section 6.2 allows the threshold to be unidentified and SPEC.md
    section 4.4 says the site then shows no headroom and falls back to the ten
    year percentile. None is therefore a first class value here and never a
    reason to substitute a default.
    """
    if threshold is not None:
        return threshold
    return inputs.run_cut_threshold_usd_bbl


def percentile_rank(
    value: float, history: Iterable[float]
) -> float | None:
    """Where a value sits inside a history, 0 to 100. SPEC.md section 4.5.

    The rule, stated because a percentile has several defensible definitions and
    the site quotes this one in a sentence a trader reads:

        the share of the history's published observations that are at or below
        the value, times 100

    So a value equal to the worst month in ten years does not score 0, it scores
    whatever share of months were that bad or worse, and a value above every
    month scores exactly 100.

    Args:
        value: the margin after gas for the month in question. It does NOT have
            to be a member of the history, and on the site it usually is,
            because the trailing ten years include the current month.
        history: the trailing window, normally 120 monthly values,
            config.PERCENTILE_WINDOW_MONTHS. Windowing is series work and lives
            in crack.series; this function ranks whatever it is given.

    Returns:
        The percentile, or None when the value is missing or the window holds no
        published observation. None means the question cannot be answered, which
        the site says in words. It is never 50 by default.
    """
    if _is_missing(value):
        return None
    published = [x for x in history if not _is_missing(x)]
    if not published:
        return None
    at_or_below = 0
    for x in published:
        if x <= value:
            at_or_below += 1
    return 100.0 * at_or_below / len(published)


@dataclass(frozen=True)
class Outputs:
    """The five things SPEC.md section 4.5 names, in one record.

    SPEC.md section 4.5 ends: "The verdict sentence on the landing view is
    assembled from these values, never written by hand." So this record holds
    values and no sentence. The wording lives in the interface, at Gate 4, and
    it is built from these fields.
    """

    margin: MarginResult
    contributions: Mapping[str, float]
    carrier: str | None
    carrier_contribution_usd_bbl: float
    breakeven_ttf_eur_mwh: float | None
    breakeven_gas_usd_mmbtu: float | None
    breakeven_gasoil_usd_bbl: float | None
    percentile_10y: float | None
    percentile_window_months: int
    percentile_observations: int
    headroom_usd_bbl: float | None
    threshold_identified: bool


def outputs(
    inputs: MarginInputs,
    history: Sequence[float] = (),
    *,
    gasoil_key: str = "gasoil",
    threshold: float | None = None,
) -> Outputs:
    """Everything SPEC.md section 4.5 asks for, computed once.

    Args:
        inputs: the margin inputs.
        history: the trailing ten years of margin after gas, monthly. Empty is
            allowed and gives percentile_10y of None, which the site reports as
            not enough history rather than as a middling month.
        gasoil_key: the product key the gasoil breakeven is quoted on. Named
            rather than assumed, because the OPEC slate calls it "gasoil" and
            DGEC calls it "gazole" and this study carries both.
        threshold: SPEC.md section 6.2's run cut threshold, or None for
            unidentified.
    """
    result = evaluate(
        inputs
        if threshold is None
        else MarginInputs(
            yields=inputs.yields,
            cracks=inputs.cracks,
            gas=inputs.gas,
            residual_usd_bbl=inputs.residual_usd_bbl,
            gas_intensity_mmbtu_per_bbl=inputs.gas_intensity_mmbtu_per_bbl,
            other_variable_cost_usd_bbl=inputs.other_variable_cost_usd_bbl,
            run_cut_threshold_usd_bbl=threshold,
            margin_basis=inputs.margin_basis,
        )
    )
    level = _threshold_or_none(inputs, threshold)
    published = [x for x in history if not _is_missing(x)]
    gasoil_breakeven = (
        breakeven_crack(inputs, gasoil_key, level)
        if gasoil_key in inputs.yields
        else None
    )
    return Outputs(
        margin=result,
        contributions=result.contributions,
        carrier=result.carrier,
        carrier_contribution_usd_bbl=result.carrier_contribution_usd_bbl,
        breakeven_ttf_eur_mwh=breakeven_ttf(inputs, level),
        breakeven_gas_usd_mmbtu=breakeven_gas_usd_mmbtu(inputs, level),
        breakeven_gasoil_usd_bbl=gasoil_breakeven,
        percentile_10y=percentile_rank(result.margin_after_gas_usd_bbl, history),
        percentile_window_months=config.PERCENTILE_WINDOW_MONTHS,
        percentile_observations=len(published),
        headroom_usd_bbl=result.headroom_usd_bbl,
        threshold_identified=level is not None,
    )
