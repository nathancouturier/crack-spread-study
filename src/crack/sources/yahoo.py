"""Dutch TTF front month, daily, EUR/MWh, from Yahoo Finance as TTF=F.

    series      ttf_daily
    cache       data/private/ttf_daily.csv          NOT data/cache, see below
    columns     date, open, high, low, close, volume
    unit        EUR per MWh for the prices, lots for volume
    source      Yahoo Finance, symbol TTF=F
    page        https://finance.yahoo.com/quote/TTF%3DF/

THIS IS THE OPTIONAL DAILY LAYER. IT IS NOT THE GAS SERIES THE ANALYSIS RUNS ON.
The monthly gas series is crack.sources.worldbank, which is already in $/MMBtu,
is TTF by the publisher's own definition from April 2015, has no gaps and is
CC BY 4.0. Recon 04 section 5.2 is explicit that splicing this series onto that
one would lose more than it gains. The site is complete without this file.

Why the cache goes to data/private and is never committed
----------------------------------------------------------
There is no public Yahoo Finance data licence. Recon 04 section 3.9 read the
general Yahoo terms and found the applicable clause forbids users to "reproduce,
modify, rent, lease, sell, trade, distribute, transmit, broadcast, publicly
perform, create derivative works based on, or exploit for any commercial
purposes" any portion of the services, and yfinance is an unofficial client for
an undocumented endpoint carrying no grant of its own. Committing this file to a
public repository would be redistribution of Yahoo sourced data.

So committable is False, base.Adapter.directory() sends the file to
data/private/, and data/private is gitignored. SPEC.md section 2 rule 6 is a non
negotiable and SPEC.md section 5.4's promise that every cache is committed is
not, so rule 6 wins. The cost is real and is not hidden: anything derived from
this series cannot be rebuilt offline from a fresh checkout. It is spelled out
again in the manifest licence_note and belongs in the Gate 1 report.

The rolls are unadjusted and undocumented, and they are not adjusted here
-------------------------------------------------------------------------
TTF=F is a stitched continuous front month series. Yahoo publishes no roll
convention and no roll dates, and expired dated contracts are delisted, so the
splice points cannot be recovered from free data. Recon 04 section 3.4 observed
exactly one roll directly: TTF=F matched TTFV26.NYM, the October 2026 contract,
on all ten sessions from 2026-08-28 to 2026-09-11, and never matched TTFX26.NYM,
so the front month rolled into October on 2026-08-28 and the series carries the
price jump.

roll_jump_candidates() below lists the large day on day moves, and it is a
HEURISTIC for a human to read, nothing else. Recon 04 measured 17 moves above 20
percent in the series. Some are rolls, 2019-09-30 at +37.3 percent and 2020-08-28
at +25.9 percent both sit on a month end. Some are the market, 2022-02-24 at
+51.1 percent is the invasion of Ukraine and 2026-03-02 at +39.3 percent is the
Hormuz episode. Nothing in this series can tell the two apart. So:

  * the prices are written exactly as Yahoo serves them, unadjusted.
  * the candidate list is recorded in the manifest as an observation, under a
    name that says candidate.
  * no roll convention is invented, no back adjustment is applied, and nothing
    downstream may treat the candidate list as a set of roll dates.

Five more things measured about this series, recon 04 section 3
----------------------------------------------------------------
1. It starts 2017-10-23, which is 33 months into a sample beginning in 2015.
   Yahoo's own firstTradeDate agrees. It is not extended backwards.
2. 2,235 rows to 2026-09-11, 96.3 percent of business days. The missing 85 days
   are exchange holidays, in 83 runs of one day and one run of two, Good Friday
   and Easter Monday 2024.
3. Before 2018-03-14 the settlement is repeated into all four OHLC fields, and
   before 2018-02-27 the volume is zero. The first four months are usable as a
   price and useless as a liquidity signal. flat_bar_count() reports it.
4. Yahoo documents the unit nowhere. EUR per MWh was established NUMERICALLY, by
   reproducing the World Bank pink sheet to a median 0.02 percent over 106
   months, recon 04 section 4.5. That is a construction proof, not a citation,
   and the manifest says so.
5. yfinance returns an empty frame intermittently, SPEC.md section 13. An empty
   frame raises EmptyChartError, is retried, then falls through to the chart JSON
   endpoint, and if that is empty too the run fails. An empty frame is never
   written to the cache.

Do not use range=max on the chart endpoint
-------------------------------------------
It looks like the right parameter and it is a trap, inherited from the sibling
repository and confirmed for TTF by recon 04 section 3.8:

    ?interval=1d&period1=0&period2=9999999999   2,238 bars, granularity 1d
    ?interval=1d&range=max                        465 bars, granularity 1wk

range=max silently returns weekly bars. The explicit period form is what this
module uses and what yfinance uses internally, which is why the two paths agree.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import time
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

import pandas as pd

from ..config import BOUNDS_TTF_EUR_MWH
from ..config import source as registered_source
from .base import Adapter, SourceError, http_get

__all__ = [
    "TICKER",
    "SERIES",
    "CHART_URL",
    "QUOTE_PAGE",
    "EXCHANGE_TZ",
    "OUTPUT_COLUMNS",
    "PRICE_BOUNDS",
    "VOLUME_BOUNDS",
    "SERIES_START",
    "ROLL_JUMP_PERCENT",
    "OBSERVED_ROLL",
    "EmptyChartError",
    "frame_from_yfinance",
    "parse_chart_json",
    "normalise",
    "fetch_via_yfinance",
    "fetch_via_chart_json",
    "roll_jump_candidates",
    "flat_bar_count",
    "TtfFrontMonth",
    "main",
]


#: Yahoo's symbol for the continuous front month Dutch TTF calendar month future.
TICKER = "TTF=F"

#: Manifest and cache name, a key of crack.config.SOURCES.
SERIES = "ttf_daily"

#: The JSON endpoint yfinance wraps, used as the second path. period1=0 is the
#: epoch and period2 is a fixed far future bound, so the URL is stable and can be
#: pasted into a browser. Do NOT replace this with range=max, see the docstring.
CHART_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/TTF=F"
    "?period1=0&period2=9999999999&interval=1d"
)

#: The human readable page, for the provenance panel.
QUOTE_PAGE = "https://finance.yahoo.com/quote/TTF%3DF/"

#: Yahoo lists this contract on NYM and stamps each daily bar in New York time,
#: recon 04 section 3.8, meta timezone EDT. The zone is used for two things: to
#: turn a tz aware index into the session's own date, and to decide whether the
#: last bar belongs to a session that has not finished yet.
EXCHANGE_TZ = ZoneInfo("America/New_York")

#: The cache file layout, in order.
OUTPUT_COLUMNS = ("date", "open", "high", "low", "close", "volume")

#: Prices, EUR per MWh. crack.config's band, which sits above the August 2022
#: spike of 339.196 and at zero below, so only a units error or a parse failure
#: can trip it.
PRICE_BOUNDS = BOUNDS_TTF_EUR_MWH

#: Volume in lots. Zero is a real value on this contract, it is what the first
#: four months of the series carry, so the lower bound is zero and not one.
VOLUME_BOUNDS = (0.0, 5_000_000.0)

#: Yahoo's own firstTradeDate for TTF=F, 1508731200 seconds, recon 04 section
#: 3.1. A fetch that starts earlier is a source change and not a longer history.
SERIES_START = "2017-10-23"

#: 2,235 rows on 2026-09-11. The floors sit under that far enough that a normal
#: run of holidays cannot trip them and close enough that a truncated response
#: cannot replace a good file.
MIN_ROWS = 2_100
MIN_PUBLISHED = 2_100

#: A day on day close move at or above this, in percent, is listed as a candidate
#: for a roll artefact. It is a reporting threshold and nothing consumes it.
#: Recon 04 section 3.4 counted 17 moves above it in the whole series.
ROLL_JUMP_PERCENT = 20.0

#: The one roll this project has observed directly rather than inferred, recon 04
#: section 3.4. Carried into the manifest so the claim on the page has a date and
#: a method next to it.
OBSERVED_ROLL = {
    "date": "2026-08-28",
    "into": "TTFV26.NYM, the October 2026 contract",
    "evidence": (
        "TTF=F matched TTFV26.NYM exactly on all ten sessions from 2026-08-28 to "
        "2026-09-11 and never matched TTFX26.NYM, the November contract. One "
        "directly observed roll out of roughly a hundred in the series."
    ),
}

#: Retry budget for the yfinance path before the JSON endpoint is tried.
YFINANCE_ATTEMPTS = 3

#: Seconds between yfinance attempts.
YFINANCE_PAUSE = 2.0

#: Seconds to wait before the chart endpoint request.
POLITE_DELAY = 1.0


_registered = registered_source(SERIES)
if _registered.committable:
    raise RuntimeError(
        "crack.config.SOURCES has %s marked committable. This module writes "
        "Yahoo sourced data, which carries no redistribution grant, and the "
        "cache must stay in data/private" % SERIES
    )


#: A trailing UTC offset, "Z", "+01:00" or "-0500". Used to tell a zoned date
#: column from a naive one before parsing, see normalise().
_UTC_OFFSET = re.compile(r"(?:Z|[+-]\d{2}:?\d{2})$")


class EmptyChartError(SourceError):
    """Yahoo answered but the answer carries no rows.

    Kept apart from SourceError so the adapter can tell "yfinance did its
    intermittent empty frame thing, try the other path" from "the request
    failed", and so the test suite can assert on the case SPEC.md section 13
    calls out by name.
    """


# --------------------------------------------------------------------------
# Normalisation, shared by both paths
# --------------------------------------------------------------------------

def exchange_today(now: dt.datetime | None = None) -> pd.Timestamp:
    """Today's date on the exchange clock, as a midnight Timestamp.

    Args:
        now: an aware datetime to evaluate instead of the real clock. Tests pass
            it so they give the same answer in 2027.
    """
    moment = dt.datetime.now(tz=EXCHANGE_TZ) if now is None else now
    if moment.tzinfo is None:
        raise ValueError("exchange_today needs an aware datetime, got a naive one")
    return pd.Timestamp(moment.astimezone(EXCHANGE_TZ).date())


def normalise(
    frame: pd.DataFrame,
    *,
    now: dt.datetime | None = None,
    drop_unsettled: bool = True,
) -> pd.DataFrame:
    """Put a fetched frame into the cache layout and check it is well formed.

    Args:
        frame: a frame carrying date, open, high, low, close and volume in any
            order. The date may be tz aware, which is what yfinance hands back:
            recon 04 section 3.10 saw a -04:00 and -05:00 offset because Yahoo
            stamps the bar in the exchange's New York time. The session's own
            local date is taken, never a UTC date, or every bar would slide a day
            at the wrong hour of the year.
        now: aware datetime standing in for the clock, for tests.
        drop_unsettled: drop the bar for the current session. A bar for a session
            still trading is a snapshot and not a settlement, and writing it puts
            a number in the file that the next run quietly changes.

    Returns:
        A frame with exactly OUTPUT_COLUMNS, ascending by date, one row per
        session.

    Raises:
        EmptyChartError: if there are no rows, before or after the drop.
        SourceError: on a missing column, an unparseable date or a duplicate
            date. Nothing is repaired quietly.
    """
    missing = [c for c in OUTPUT_COLUMNS if c not in frame.columns]
    if missing:
        raise SourceError(
            "yahoo %s: the response is missing column(s) %s, got %s"
            % (TICKER, ", ".join(missing), ", ".join(map(str, frame.columns)))
        )

    out = frame.loc[:, list(OUTPUT_COLUMNS)].copy()

    # Whether the dates carry a zone is decided before parsing, not after. Live
    # yfinance hands back a single zone America/New_York index, but the same
    # frame saved to CSV and read back carries a text offset that switches
    # between -04:00 and -05:00 with daylight saving, and pandas parses a column
    # of MIXED offsets into an object column with no .dt accessor at all. So a
    # column that looks zoned is parsed through UTC and converted to the
    # exchange's own zone, and a naive column is left naive: passing utc=True to
    # a naive column would localise midnight local to midnight UTC and then slide
    # every session back a day on conversion.
    values = out["date"]
    zoned = isinstance(values.dtype, pd.DatetimeTZDtype)
    if not zoned and not pd.api.types.is_datetime64_any_dtype(values):
        sample = values.dropna().astype(str)
        zoned = bool(len(sample)) and bool(_UTC_OFFSET.search(sample.iloc[0].strip()))
    parsed = pd.to_datetime(values, errors="coerce", utc=True if zoned else False)
    if parsed.isna().any():
        bad = out.loc[parsed.isna(), "date"].astype(str).tolist()[:3]
        raise SourceError(
            "yahoo %s: %d date(s) do not parse, for example %s"
            % (TICKER, int(parsed.isna().sum()), ", ".join(bad))
        )
    if isinstance(parsed.dtype, pd.DatetimeTZDtype):
        parsed = parsed.dt.tz_convert(EXCHANGE_TZ).dt.tz_localize(None)
    out["date"] = parsed.dt.normalize()

    for column in ("open", "high", "low", "close", "volume"):
        out[column] = pd.to_numeric(out[column], errors="coerce")

    duplicates = out.loc[out["date"].duplicated(), "date"]
    if len(duplicates):
        raise SourceError(
            "yahoo %s: duplicate session date(s), first is %s"
            % (TICKER, duplicates.iloc[0].strftime("%Y-%m-%d"))
        )

    # A timestamp Yahoo published no open, high, low or close for is not an
    # observation, it is an empty slot the endpoint emitted for a non trading
    # day. It is not written as a row. A session with some prices and not others
    # is kept, NaN where the value is missing, because that is a real partial
    # observation. yfinance drops the same rows, which is what makes the two
    # paths agree.
    prices = out[["open", "high", "low", "close"]]
    out = out.loc[~prices.isna().all(axis=1)].reset_index(drop=True)
    out = out.sort_values("date", kind="mergesort").reset_index(drop=True)

    if out.empty:
        raise EmptyChartError("yahoo %s: the response carried no rows" % TICKER)

    if drop_unsettled:
        cutoff = exchange_today(now)
        out = out.loc[out["date"] < cutoff].reset_index(drop=True)
        if out.empty:
            raise EmptyChartError(
                "yahoo %s: every row was for the current session or later, so "
                "nothing settled was returned" % TICKER
            )
    return out


# --------------------------------------------------------------------------
# Path 1, yfinance
# --------------------------------------------------------------------------

def frame_from_yfinance(raw: Any) -> pd.DataFrame:
    """Turn a yfinance history frame into the cache layout. No network.

    Split out from fetch_via_yfinance so the shape handling is testable against
    a committed fixture rather than only against the live library.

    Raises:
        EmptyChartError: if the frame is empty. This is the intermittent
            behaviour SPEC.md section 13 warns about and it must never reach the
            cache, so it is a named exception and not a zero row frame that
            flows on to validation.
        SourceError: if the object is not a frame, or has lost a column.
    """
    if not isinstance(raw, pd.DataFrame):
        raise SourceError(
            "yfinance returned %s rather than a DataFrame for %s"
            % (type(raw).__name__, TICKER)
        )
    if raw.empty:
        raise EmptyChartError(
            "yfinance returned an empty frame for %s. SPEC.md section 13 says "
            "this happens intermittently, so it is retried and then the chart "
            "JSON endpoint is tried, and an empty frame is never cached" % TICKER
        )

    frame = raw.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        # yfinance uses a MultiIndex when more than one ticker is requested and,
        # depending on the version, sometimes for a single one too.
        wanted = {"open", "high", "low", "close", "volume"}
        frame.columns = [
            next((part for part in reversed(tup) if part), tup[0])
            if any(str(part).lower() in wanted for part in tup)
            else tup[0]
            for tup in frame.columns
        ]

    frame = frame.reset_index()
    lower = {str(c).strip().lower(): c for c in frame.columns}

    date_key = next(
        (lower[k] for k in ("date", "datetime", "index") if k in lower), None
    )
    if date_key is None:
        raise SourceError(
            "yfinance frame for %s has no date column, columns were %s"
            % (TICKER, ", ".join(map(str, frame.columns)))
        )

    picked: dict[str, Any] = {"date": frame[date_key]}
    for key in ("open", "high", "low", "close", "volume"):
        if key not in lower:
            raise SourceError(
                "yfinance frame for %s has no %r column, columns were %s"
                % (TICKER, key, ", ".join(map(str, frame.columns)))
            )
        picked[key] = frame[lower[key]]
    return pd.DataFrame(picked)


def fetch_via_yfinance(
    *, attempts: int = YFINANCE_ATTEMPTS, pause: float = YFINANCE_PAUSE
) -> pd.DataFrame:
    """Fetch the full history through yfinance. Network call.

    Retries on an empty frame and on a raising call, because both are the same
    intermittent problem seen from two sides.

    Raises:
        EmptyChartError: if every attempt came back empty.
        SourceError: if every attempt raised.
    """
    import yfinance  # imported here so this module can be tested without it

    last: Exception | None = None
    attempts = max(1, int(attempts))
    for attempt in range(1, attempts + 1):
        try:
            raw = yfinance.Ticker(TICKER).history(
                period="max", interval="1d", auto_adjust=False
            )
            return frame_from_yfinance(raw)
        except EmptyChartError as exc:
            last = exc
        except Exception as exc:  # noqa: BLE001, any library failure is a retry
            last = SourceError(
                "yfinance attempt %d for %s raised %s: %s"
                % (attempt, TICKER, type(exc).__name__, exc)
            )
        if attempt < attempts and pause > 0:
            time.sleep(pause)

    assert last is not None
    raise last


# --------------------------------------------------------------------------
# Path 2, the chart JSON endpoint
# --------------------------------------------------------------------------

def parse_chart_json(payload: Any) -> pd.DataFrame:
    """Parse a Yahoo v8 chart response into the cache layout. No network.

    Args:
        payload: the decoded JSON, or the raw text or bytes of the response.

    Returns:
        A frame with date, open, high, low, close and volume. A session Yahoo has
        no value for keeps NaN.

    Raises:
        EmptyChartError: if the response is well formed but carries no bars.
        SourceError: if the response is an error document, or its shape is not
            the documented one. The message names what was missing, so a change
            at Yahoo is diagnosable from the log alone.
    """
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8", errors="replace")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError as exc:
            raise SourceError(
                "yahoo %s: the chart endpoint did not return JSON, %s"
                % (TICKER, exc)
            ) from exc
    if not isinstance(payload, Mapping):
        raise SourceError(
            "yahoo %s: expected a JSON object from the chart endpoint, got %s"
            % (TICKER, type(payload).__name__)
        )

    chart = payload.get("chart")
    if not isinstance(chart, Mapping):
        raise SourceError(
            "yahoo %s: the response has no 'chart' object, keys were %s"
            % (TICKER, ", ".join(map(str, payload)))
        )
    if chart.get("error"):
        raise SourceError(
            "yahoo %s: the chart endpoint returned %r" % (TICKER, chart["error"])
        )

    results = chart.get("result")
    if not isinstance(results, Sequence) or not results:
        raise EmptyChartError(
            "yahoo %s: the chart endpoint returned no result block" % TICKER
        )
    result = results[0]
    if not isinstance(result, Mapping):
        raise SourceError(
            "yahoo %s: the result block is %s, not an object"
            % (TICKER, type(result).__name__)
        )

    meta = result.get("meta") if isinstance(result.get("meta"), Mapping) else {}
    granularity = str(meta.get("dataGranularity", "")).lower()
    if granularity and granularity != "1d":
        # The range=max trap, recon 04 section 3.8. Weekly bars in a file that
        # claims to be daily would silently thin the series, so it is refused.
        raise SourceError(
            "yahoo %s: the chart endpoint reports dataGranularity %r, not '1d'. "
            "That is the range=max behaviour and it returns weekly bars"
            % (TICKER, granularity)
        )

    stamps = result.get("timestamp")
    if not stamps:
        raise EmptyChartError(
            "yahoo %s: the chart endpoint returned a result with no timestamps"
            % TICKER
        )

    indicators = result.get("indicators")
    if not isinstance(indicators, Mapping):
        raise SourceError("yahoo %s: the result block has no 'indicators'" % TICKER)
    quotes = indicators.get("quote")
    if (
        not isinstance(quotes, Sequence)
        or not quotes
        or not isinstance(quotes[0], Mapping)
    ):
        raise SourceError(
            "yahoo %s: the result block has no 'indicators.quote' array" % TICKER
        )
    quote = quotes[0]

    try:
        offset = int(meta.get("gmtoffset", 0))
    except (TypeError, ValueError):
        offset = 0

    columns: dict[str, list] = {}
    for key in ("open", "high", "low", "close", "volume"):
        values = quote.get(key)
        if values is None:
            raise SourceError(
                "yahoo %s: 'indicators.quote[0]' has no %r array, keys were %s"
                % (TICKER, key, ", ".join(map(str, quote)))
            )
        if len(values) != len(stamps):
            raise SourceError(
                "yahoo %s: the %r array has %d entries but there are %d "
                "timestamps" % (TICKER, key, len(values), len(stamps))
            )
        columns[key] = [float("nan") if v is None else v for v in values]

    # Yahoo stamps a daily bar at the opening instant of the session in UTC.
    # Adding the exchange offset before taking the date gives the session date
    # the exchange itself prints, which is what the rest of this project keys on.
    dates = [
        pd.Timestamp(
            dt.datetime.fromtimestamp(int(ts) + offset, tz=dt.timezone.utc).date()
        )
        for ts in stamps
    ]
    return pd.DataFrame({"date": dates, **columns})


def fetch_via_chart_json(*, delay: float = POLITE_DELAY) -> pd.DataFrame:
    """Fetch the full history from the chart JSON endpoint. Network call.

    The chart endpoint accepts the project browser user agent, unlike FRED,
    recon 04 section 3.8, so base.http_get's default applies and nothing is
    overridden here.
    """
    response = http_get(CHART_URL, delay=delay, retries=2, timeout=60)
    return parse_chart_json(response.content)


# --------------------------------------------------------------------------
# Observations about the series, for the manifest and for a human
# --------------------------------------------------------------------------

def roll_jump_candidates(
    frame: pd.DataFrame, *, threshold_percent: float = ROLL_JUMP_PERCENT
) -> list[dict]:
    """Day on day close moves at or above a threshold. A HEURISTIC, not a fact.

    A continuous series that splices two contracts at different prices shows a
    jump. So does an invasion. Recon 04 section 3.4 found both inside this
    series and could not separate them: 2019-09-30 at +37.3 percent sits on a
    month end and looks like a roll, 2022-02-24 at +51.1 percent is the invasion
    of Ukraine, and nothing in TTF=F distinguishes them.

    So this returns CANDIDATES. Every entry carries the date, the move and one
    piece of circumstantial evidence, sessions_to_month_end: how many further
    sessions of the same calendar month this series holds after the jump date.
    Zero means the jump landed on the last session of its month, which is the
    shape a roll would take, because a TTF monthly contract expires at the end of
    the month before delivery. It is circumstantial and it is labelled as
    circumstantial: 2019-09-30 at +37.3 percent has a zero there and looks like a
    roll, 2022-02-24 at +51.1 percent has a large one and is the invasion.

    Nothing downstream may treat the list as a set of roll dates and no price is
    adjusted anywhere on the strength of it.

    Returns:
        Entries ordered by date, each with date, previous_date, close,
        previous_close, percent and sessions_to_month_end.
    """
    work = frame.loc[:, ["date", "close"]].copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["close"] = pd.to_numeric(work["close"], errors="coerce")
    work = work.dropna(subset=["date", "close"]).sort_values("date", kind="mergesort")

    previous_close = work["close"].shift(1)
    previous_date = work["date"].shift(1)
    percent = 100.0 * (work["close"] - previous_close) / previous_close

    # How many sessions of the same calendar month come after each one. Counted
    # from this series' own sessions, so an exchange holiday at the end of a
    # month does not turn a real last session into a non last one.
    months = work["date"].dt.to_period("M")
    remaining = months.groupby(months).cumcount(ascending=False)

    out: list[dict] = []
    for index in work.index[percent.abs() >= float(threshold_percent)]:
        prior = previous_date.loc[index]
        out.append(
            {
                "date": work.loc[index, "date"].strftime("%Y-%m-%d"),
                "previous_date": prior.strftime("%Y-%m-%d"),
                "close": float(work.loc[index, "close"]),
                "previous_close": float(previous_close.loc[index]),
                "percent": round(float(percent.loc[index]), 2),
                "sessions_to_month_end": int(remaining.loc[index]),
            }
        )
    return out


def flat_bar_count(frame: pd.DataFrame) -> dict:
    """How much of the frame is a settlement repeated into all four OHLC fields.

    Recon 04 section 3.3: 529 rows, the first four and a half months of the
    series, carry open equal to high equal to low equal to close, and 469 carry
    zero volume. Those rows are a usable price and a useless liquidity signal,
    and the difference belongs in the manifest rather than in a reader's
    surprise.
    """
    work = frame.loc[:, ["date", "open", "high", "low", "close", "volume"]].copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    prices = work[["open", "high", "low", "close"]].apply(
        pd.to_numeric, errors="coerce"
    )
    flat = (
        prices.notna().all(axis=1)
        & (prices.nunique(axis=1) == 1)
    )
    volume = pd.to_numeric(work["volume"], errors="coerce")
    zero_volume = volume.notna() & (volume == 0)

    first_shaped = work.loc[~flat, "date"]
    first_traded = work.loc[~zero_volume, "date"]
    return {
        "flat_bars": int(flat.sum()),
        "zero_volume_bars": int(zero_volume.sum()),
        "first_non_flat_bar": (
            first_shaped.min().strftime("%Y-%m-%d") if len(first_shaped) else None
        ),
        "first_bar_with_volume": (
            first_traded.min().strftime("%Y-%m-%d") if len(first_traded) else None
        ),
    }


# --------------------------------------------------------------------------
# The adapter
# --------------------------------------------------------------------------

class TtfFrontMonth(Adapter):
    """Yahoo TTF=F, the Dutch TTF continuous front month, written to data/private."""

    name = SERIES
    source = "Yahoo Finance, symbol TTF=F, CME listed calendar month future"
    url = CHART_URL
    page_url = QUOTE_PAGE
    unit = "EUR per MWh for the prices, lots for volume"
    frequency = "daily"
    method = "published"
    #: NOT COMMITTABLE. See the module docstring. base.Adapter.directory() reads
    #: this and sends the file to data/private, which is gitignored.
    committable = False
    licence_note = _registered.licence_note
    required_cols = OUTPUT_COLUMNS
    bounds = {
        "open": PRICE_BOUNDS,
        "high": PRICE_BOUNDS,
        "low": PRICE_BOUNDS,
        "close": PRICE_BOUNDS,
        "volume": VOLUME_BOUNDS,
    }
    date_col = "date"
    min_rows = MIN_ROWS
    min_observations = {
        "open": MIN_PUBLISHED,
        "high": MIN_PUBLISHED,
        "low": MIN_PUBLISHED,
        "close": MIN_PUBLISHED,
        "volume": MIN_PUBLISHED,
    }
    #: The close is what makes a session an observation of this series.
    observation_column = "close"

    def __init__(
        self,
        *,
        attempts: int = YFINANCE_ATTEMPTS,
        pause: float = YFINANCE_PAUSE,
        delay: float = POLITE_DELAY,
        allow_yfinance: bool = True,
        now: dt.datetime | None = None,
    ):
        """
        Args:
            attempts: yfinance tries before the JSON endpoint is used.
            pause: seconds between yfinance attempts.
            delay: polite pause before the JSON request.
            allow_yfinance: set False to go straight to the JSON endpoint, which
                is how the second path is proved to work on its own.
            now: aware datetime standing in for the clock, for tests.
        """
        self.attempts = int(attempts)
        self.pause = float(pause)
        self.delay = float(delay)
        self.allow_yfinance = bool(allow_yfinance)
        self.now = now
        #: "yfinance" or "chart json", set by fetch()
        self.path_used: str | None = None
        #: what went wrong on the first path, if the second was needed
        self.first_path_problem: str | None = None
        #: the bar dropped because its session had not settled, if any
        self.dropped_unsettled: str | None = None
        #: the roll candidates measured on this fetch
        self.roll_candidates: list[dict] = []
        #: the flat bar report measured on this fetch
        self.shape: dict = {}

    def fetch(self) -> pd.DataFrame:
        self.path_used = None
        self.first_path_problem = None

        raw: pd.DataFrame | None = None
        if self.allow_yfinance:
            try:
                raw = fetch_via_yfinance(attempts=self.attempts, pause=self.pause)
                self.path_used = "yfinance"
            except (EmptyChartError, SourceError) as exc:
                self.first_path_problem = "%s: %s" % (type(exc).__name__, exc)
        else:
            self.first_path_problem = "yfinance path disabled by the caller"

        if raw is None:
            raw = fetch_via_chart_json(delay=self.delay)
            self.path_used = "chart json"

        settled = normalise(raw, now=self.now, drop_unsettled=False)
        frame = normalise(raw, now=self.now, drop_unsettled=True)
        if len(frame) < len(settled):
            dropped = settled.loc[~settled["date"].isin(frame["date"]), "date"]
            self.dropped_unsettled = ", ".join(
                d.strftime("%Y-%m-%d") for d in dropped
            )
        else:
            self.dropped_unsettled = None

        first = frame["date"].min()
        if first < pd.Timestamp(SERIES_START):
            raise SourceError(
                "yahoo %s: the history starts %s, earlier than Yahoo's own "
                "firstTradeDate of %s. That is a source change and not a longer "
                "history" % (TICKER, first.strftime("%Y-%m-%d"), SERIES_START)
            )

        self.roll_candidates = roll_jump_candidates(frame)
        self.shape = flat_bar_count(frame)
        self.note = self._built_note(frame)
        return frame

    def _built_note(self, frame: pd.DataFrame) -> str:
        parts = [
            "Dutch TTF continuous front month, Yahoo Finance symbol TTF=F, one "
            "row per settled session, prices exactly as Yahoo serves them.",
            "Fetch path used: %s." % (self.path_used or "none"),
        ]
        if self.first_path_problem:
            parts.append("yfinance path not used because %s" % self.first_path_problem)
        if self.dropped_unsettled:
            parts.append(
                "Dropped the bar for %s because that session had not settled "
                "when the fetch ran. A live bar is not a settlement."
                % self.dropped_unsettled
            )
        parts.append(
            "UNIT: EUR per MWh. Yahoo documents the unit nowhere. It was "
            "established numerically, by reproducing the World Bank pink sheet's "
            "Natural gas, Europe series to a median 0.02 percent over 106 months "
            "after converting with DEXUSEU and MMBTU_PER_MWH, recon 04 section "
            "4.5. That is a construction proof, not a citation."
        )
        parts.append(
            "ROLLS ARE UNADJUSTED AND UNDOCUMENTED. Yahoo publishes no roll "
            "convention and no roll dates, and expired dated contracts are "
            "delisted, so the splice points cannot be recovered from free data. "
            "One roll was observed directly, %s into %s: %s. "
            "roll_jump_candidates lists %d day on day close move(s) of %g percent "
            "or more, and they are CANDIDATES a human reads, not roll dates: "
            "some are splices and some are the invasion of Ukraine and the "
            "Hormuz episode, and this series cannot tell them apart. No price is "
            "adjusted anywhere."
            % (
                OBSERVED_ROLL["date"],
                OBSERVED_ROLL["into"],
                OBSERVED_ROLL["evidence"],
                len(self.roll_candidates),
                ROLL_JUMP_PERCENT,
            )
        )
        if self.shape:
            parts.append(
                "%d row(s) carry a settlement repeated into all four OHLC fields "
                "and %d carry zero volume, all of them at the start of the "
                "series. The first bar with a real range is %s and the first with "
                "volume is %s. Those early rows are a usable price and a useless "
                "liquidity signal."
                % (
                    self.shape["flat_bars"],
                    self.shape["zero_volume_bars"],
                    self.shape["first_non_flat_bar"],
                    self.shape["first_bar_with_volume"],
                )
            )
        parts.append(
            "THIS CACHE IS NOT COMMITTED. It is written to data/private, which is "
            "gitignored, because Yahoo grants no redistribution right, recon 04 "
            "section 3.9. It is the optional daily display layer of SPEC.md "
            "section 5.1 and nothing the analysis depends on: the monthly gas "
            "series is worldbank_gas_europe_monthly, already in $/MMBtu and CC BY "
            "4.0. The consequence, stated rather than hidden, is that anything "
            "derived from this file cannot be rebuilt offline from a fresh "
            "checkout. The series starts %s, 33 months into a sample beginning in "
            "2015, and it is not extended backwards."
            % SERIES_START
        )
        return " ".join(parts)

    def _entry(self, *, status: str, frame, note: str) -> dict:
        entry = super()._entry(status=status, frame=frame, note=note)
        entry["fetch_path"] = self.path_used
        entry["roll_jump_candidates"] = list(self.roll_candidates)
        entry["roll_jump_threshold_percent"] = ROLL_JUMP_PERCENT
        entry["observed_roll"] = dict(OBSERVED_ROLL)
        if self.shape:
            entry["early_flat_bars"] = dict(self.shape)
        return entry


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> int:
    """Run the adapter and print an ASCII report. Returns an exit code."""
    adapter = TtfFrontMonth()
    try:
        entry = adapter.run()
    except Exception as exc:  # noqa: BLE001, the CLI reports and exits non zero
        print("%s FAILED: %s: %s" % (SERIES, type(exc).__name__, exc))
        return 1
    print(
        "%-20s rows=%-6d %s to %s gaps=%d status=%s path=%s roll_candidates=%d"
        % (
            entry["series"],
            entry["rows"],
            entry["first_date"],
            entry["last_date"],
            len(entry["gaps"]),
            entry["status"],
            entry["fetch_path"],
            len(entry["roll_jump_candidates"]),
        )
    )
    print("file: %s, NOT committed" % entry["file"])
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
