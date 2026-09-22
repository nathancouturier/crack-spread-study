"""Shared plumbing for every data source adapter.

This module is the contract the rest of the data layer depends on. It owns five
things and nothing else:

    where files live          REPO_ROOT, DATA, CACHE, SEED, FIXTURES, PRIVATE,
                              MANIFEST
    how we talk to the web    USER_AGENT, user_agent_for, http_get, http_head,
                              SourceError
    how a frame is checked    validate_frame, observation_count, find_gaps
    how a result is recorded  read_cache, write_cache, manifest_read,
                              manifest_upsert
    what an adapter is        Adapter

The rules it enforces come from SPEC.md sections 2 and 5.4:

  * never invent a value. A failed fetch keeps the previous cache and is written
    into the manifest with status "failed". A missing observation stays NaN.
  * validate on write. Monotonic dates, no duplicates, the declared bounds, a
    row count that did not shrink against the cache already on disk, and a
    declared minimum number of real observations in every value column, so a
    source that starts printing a dash where it used to print a price fails
    loudly instead of caching a column of nothing.
  * be polite. A delay before every request, exponential backoff on 429, 5xx and
    connection errors, retries, one request per file.

Three things here are specific to this project and are not in the sibling repo
--------------------------------------------------------------------------------
1. THE USER AGENT IS NOT ONE STRING. SPEC.md section 5.4 says to send "a real
   user agent" and for one of this project's sources that instruction is simply
   wrong. Recon 04 section 1.2 measured fred.stlouisfed.org five ways in the same
   minute, changing only the User-Agent header: a named project token and
   python-requests both returned HTTP 200 in under a second, while "Mozilla/5.0"
   got a connection reset and a full Chrome string timed out after 40 seconds
   with zero bytes. The sibling repository reached the same conclusion
   independently on 2026-08-31 for the SOFR series. So the host to user agent map
   lives here, once, and no adapter has to rediscover it.

2. NEVER PROBE WITH HEAD. Recon 03 section 4 item 12 found eia.gov answers HTTP
   503 to a HEAD request and HTTP 200 to a GET of the same URL, on its navigator
   pages and on the directory that holds its data files. An adapter that checks
   liveness with HEAD before fetching will conclude the source is down when it is
   not. http_head below refuses those hosts rather than letting the mistake be
   made a second time.

3. GAP DETECTION TAKES A FREQUENCY. The sibling had only daily series, so a
   single missing_weekdays helper was enough. This project carries daily, weekly,
   monthly and annual series at once, and a missing weekday in a weekly series is
   not a gap while a missing week is. find_gaps asks which one it is looking at,
   and the Adapter declares it.

Nothing here fetches anything by itself. The adapters do that.
"""

from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit

import numpy as np
import pandas as pd
import requests

from .. import manual_steps
from ..config import (
    BOUNDS_BRENT_USD_BBL,
    BOUNDS_CRACK_USD_BBL,
    BOUNDS_INTAKE_KB_D,
    BOUNDS_PRODUCT_USD_T,
    FREQUENCIES,
    METHODS,
    SOURCES,
)

__all__ = [
    "REPO_ROOT",
    "DATA",
    "CACHE",
    "SEED",
    "FIXTURES",
    "PRIVATE",
    "MANIFEST",
    "USER_AGENT",
    "PROJECT_USER_AGENT",
    "USER_AGENT_BY_HOST",
    "HEAD_IS_BROKEN_ON",
    "user_agent_for",
    "SourceError",
    "http_get",
    "http_head",
    "utc_now_iso",
    "read_cache",
    "write_cache",
    "find_gaps",
    "missing_business_days",
    "observation_count",
    "validate_frame",
    "manifest_read",
    "manifest_upsert",
    "Adapter",
    "MANIFEST_SCHEMA_VERSION",
    "STATUS_VALUES",
    "ENTRY_KEYS",
    "SPEC_BOUNDS",
    "DIRECTORIES",
]


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

# This file is <repo>/src/crack/sources/base.py, so the repo root is four
# parents up: sources -> crack -> src -> repo root.
REPO_ROOT: Path = Path(__file__).resolve().parents[3]

DATA: Path = REPO_ROOT / "data"
CACHE: Path = DATA / "cache"
SEED: Path = DATA / "seed"
FIXTURES: Path = DATA / "fixtures"
#: Gitignored, never committed, never deployed. SPEC.md section 0.1 and section 2
#: rule 6. A cache whose terms forbid redistribution lives here.
PRIVATE: Path = DATA / "private"
MANIFEST: Path = DATA / "manifest.json"

#: The three places an adapter may write, and the meaning of each. They are kept
#: apart on purpose: data/cache is reserved for what a source actually served, so
#: a hand seeded file does not get to sit there and look like a record of the
#: market, and a file nobody is allowed to republish does not get to sit there
#: and be committed by accident.
DIRECTORIES = ("cache", "seed", "private")


def _verify_repo_root(root: Path) -> None:
    """Fail loudly if the four parents walk did not land on the repo root.

    A wrong root would silently write caches into some other directory, so this
    is checked at import time rather than left to be discovered later.

    The consequence is that this package expects to be run from a checkout, or
    from an editable install that still points at the checkout. A copy of the
    package sitting in site-packages on its own has no data directory to write
    to, and this raises rather than inventing one.
    """
    markers = ("pyproject.toml", "SPEC.md")
    missing = [m for m in markers if not (root / m).exists()]
    if missing:
        raise RuntimeError(
            "REPO_ROOT resolved to %s which does not look like the repository "
            "root, missing %s. base.py must stay at src/crack/sources/base.py."
            % (root, ", ".join(missing))
        )


_verify_repo_root(REPO_ROOT)


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

# A real, currently shipping desktop browser string. Several of this project's
# sources refuse an obvious script agent. Refresh the Chrome version from time to
# time, a very old string is itself a signal.
USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

#: A named bot token. This is the more correct thing to send to a public data
#: API than a browser string pretending to be a person, and for FRED it is the
#: only thing that works at all. See USER_AGENT_BY_HOST.
PROJECT_USER_AGENT: str = (
    "crack-spread-study/1.0 "
    "(+https://github.com/nathancouturier/crack-spread-study)"
)

# Hosts that need something other than the browser string, with the measurement
# that established it. Matched on the host and on any parent domain, so
# "fred.stlouisfed.org" covers "fred.stlouisfed.org" and nothing narrower is
# needed today.
#
# fred.stlouisfed.org RESETS THE CONNECTION when sent a browser user agent.
# Recon 04 section 1.2, same URL, same minute, only the header changed:
#
#     curl/8.x                       HTTP 200, 174,106 bytes, under a second
#     crack-spread-study/1.0 token   HTTP 200
#     python-requests/2.32.3         HTTP 200
#     Mozilla/5.0                    curl error 56, connection reset, 0 bytes
#     full Chrome 127 string         timed out after 40 s, 0 bytes received
#
# Whether the block is FRED policy or a middlebox on this connection is NOT
# established, only the behaviour was observed, and it was observed twice on two
# different days by two different agents. Either way the fix is the same. Note
# the direct conflict with SPEC.md section 5.4's "a real user agent": for this
# host that instruction is wrong, and the disagreement is recorded in
# docs/open-questions.md rather than resolved silently.
USER_AGENT_BY_HOST: Mapping[str, str] = {
    "fred.stlouisfed.org": PROJECT_USER_AGENT,
    "stlouisfed.org": PROJECT_USER_AGENT,
}

# Hosts that answer HTTP 503 to HEAD and HTTP 200 to GET on the same URL. Recon
# 03 section 4 item 12 measured this on eia.gov navigator pages and on the
# directory holding its data files. A liveness probe with HEAD against one of
# these reports the source as down when it is up, which is the most expensive
# kind of false alarm in a pipeline whose whole job is to tell the truth about
# whether a source answered. http_head refuses them.
HEAD_IS_BROKEN_ON: frozenset[str] = frozenset({"eia.gov", "www.eia.gov"})

DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Connection": "close",
}

# Retried: too many requests, request timeout, and anything the server side
# broke. Everything else in the 4xx range is a permanent answer, retrying a 403
# or a 404 only wastes the remote host's time.
RETRY_STATUS: frozenset[int] = frozenset(
    {408, 425, 429, 500, 502, 503, 504, 509, 520, 522, 524}
)


class SourceError(Exception):
    """A data source could not be read, or gave back something unusable."""


def _host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def _host_matches(host: str, registered: str) -> bool:
    """True when host is the registered host or a subdomain of it."""
    return host == registered or host.endswith("." + registered)


def user_agent_for(url: str) -> str:
    """The user agent this project sends to that URL's host.

    The browser string everywhere except the hosts in USER_AGENT_BY_HOST, which
    documents why each exception exists. Adapters do not need to call this, it is
    applied inside http_get, but it is exported so a test can assert on it
    without a network call.
    """
    host = _host_of(url)
    for registered, agent in USER_AGENT_BY_HOST.items():
        if _host_matches(host, registered):
            return agent
    return USER_AGENT


def http_get(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = 30,
    retries: int = 4,
    backoff: float = 1.7,
    delay: float = 1.0,
) -> requests.Response:
    """GET a URL politely, with retries, and return the response.

    The User-Agent is chosen by host through user_agent_for unless the caller
    passes one explicitly, so an adapter cannot accidentally send the browser
    string to FRED.

    Args:
        url: the absolute URL to fetch.
        headers: extra headers, merged over the defaults. A User-Agent given
            here wins over the per host choice, which is what a source specific
            probe wants and what ordinary adapters should not do.
        timeout: per attempt timeout in seconds.
        retries: number of retries after the first attempt, so retries=4 means
            up to five attempts in total.
        backoff: multiplier for the wait between attempts. Attempt n waits
            delay * backoff ** n seconds, honouring Retry-After when the server
            sends one.
        delay: the polite pause taken before every attempt, including the first.
            Scrapers must not hammer a host.

    Returns:
        The successful requests.Response, status 200 to 399.

    Raises:
        SourceError: after the final retry, or immediately on a status that will
            not change if we ask again. The message always carries the URL and
            the status or exception seen.
    """
    merged: dict[str, str] = dict(DEFAULT_HEADERS)
    merged["User-Agent"] = user_agent_for(url)
    if headers:
        merged.update(headers)

    attempts = max(1, int(retries) + 1)
    last_problem = "no attempt was made"

    for attempt in range(attempts):
        if delay > 0:
            time.sleep(delay)
        try:
            response = requests.get(url, headers=merged, timeout=timeout)
        except requests.RequestException as exc:
            last_problem = "%s: %s" % (type(exc).__name__, exc)
        else:
            if response.status_code < 400:
                return response
            last_problem = "HTTP %d" % response.status_code
            if response.status_code not in RETRY_STATUS:
                raise SourceError(
                    "GET %s failed with HTTP %d, not retryable"
                    % (url, response.status_code)
                )
            wait_hint = response.headers.get("Retry-After")
            if wait_hint:
                try:
                    time.sleep(min(60.0, float(wait_hint)))
                except (TypeError, ValueError):
                    pass

        if attempt < attempts - 1:
            time.sleep(max(0.0, delay) * (backoff ** (attempt + 1)))

    raise SourceError(
        "GET %s failed after %d attempts, last problem %s"
        % (url, attempts, last_problem)
    )


def http_head(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = 30,
    delay: float = 1.0,
) -> requests.Response:
    """HEAD a URL, for a size or a last modified date. One attempt, no retries.

    Refuses the hosts in HEAD_IS_BROKEN_ON rather than returning their 503,
    because a 503 from those hosts means nothing at all and an adapter that
    believed it would report a live source as dead. Use http_get there and read
    the headers off the real response.

    Raises:
        SourceError: on a refused host, on a status of 400 or more, or on a
            connection failure. A HEAD is a convenience, so it does not retry:
            if it matters enough to retry, fetch the thing.
    """
    host = _host_of(url)
    for registered in HEAD_IS_BROKEN_ON:
        if _host_matches(host, registered):
            raise SourceError(
                "refusing to HEAD %s. %s answers HTTP 503 to HEAD and HTTP 200 "
                "to GET on the same URL, so a HEAD probe reports the source as "
                "down when it is up. See recon 03 and the module docstring. Use "
                "http_get." % (url, registered)
            )

    merged: dict[str, str] = dict(DEFAULT_HEADERS)
    merged["User-Agent"] = user_agent_for(url)
    if headers:
        merged.update(headers)

    if delay > 0:
        time.sleep(delay)
    try:
        response = requests.head(url, headers=merged, timeout=timeout, allow_redirects=True)
    except requests.RequestException as exc:
        raise SourceError(
            "HEAD %s failed, %s: %s" % (url, type(exc).__name__, exc)
        ) from exc
    if response.status_code >= 400:
        raise SourceError("HEAD %s returned HTTP %d" % (url, response.status_code))
    return response


def utc_now_iso() -> str:
    """Current UTC time as 2026-09-12T08:04:11Z, second precision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Cache read and write
# --------------------------------------------------------------------------

def _cache_path(name: str, *, directory: str = "cache") -> Path:
    """Path of a data file, by series name and directory.

    directory is one of DIRECTORIES. See the comment on DIRECTORIES for what
    each one means and why they are not interchangeable.
    """
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise ValueError("cache name %r is not a plain series name" % (name,))
    if directory not in DIRECTORIES:
        raise ValueError(
            "directory %r is not one of %s" % (directory, ", ".join(DIRECTORIES))
        )
    root = {"cache": CACHE, "seed": SEED, "private": PRIVATE}[directory]
    return root / ("%s.csv" % name)


def read_cache(
    name: str, *, date_col: str = "date", directory: str = "cache"
) -> pd.DataFrame | None:
    """Read data/<directory>/<name>.csv, or return None if it is not there.

    The date column is parsed to datetime64. Everything else is left as pandas
    read it, so a column that failed to fetch stays NaN rather than becoming a
    zero.

    float_precision="round_trip" IS NOT OPTIONAL AND IT IS NOT A STYLE CHOICE.
    pandas' default C parser is fast and is not round trip exact: it reads
    1201.7159025169021, which is what write_cache wrote, back as
    1201.715902516902, which is the adjacent double. Everything downstream then
    computes on a number that is not the number in the file, and a rebuild of a
    cache from a cache is not byte idempotent. That is how it was found: a clean
    checkout rebuilt the committed decode of the DGEC notes from the committed
    decode of the DGEC notes and produced a 212 line diff of last digits. The
    parser this asks for is slower and is exactly the one whose output equals
    what write_cache wrote.
    """
    path = _cache_path(name, directory=directory)
    if not path.exists():
        return None
    frame = pd.read_csv(path, encoding="utf-8", float_precision="round_trip")
    if date_col in frame.columns:
        frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
    return frame


def _format_float(value: float) -> str:
    """Decimal text for a float, never scientific notation, round trip exact."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, float) and math.isinf(value):
        return "inf" if value > 0 else "-inf"
    return np.format_float_positional(value, unique=True, trim="-")


def write_cache(
    name: str, df: pd.DataFrame, *, date_col: str = "date", directory: str = "cache"
) -> None:
    """Write a frame to data/<directory>/<name>.csv atomically.

    utf-8, LF line endings, no index column, dates as yyyy-mm-dd, floats in plain
    decimal so a diff of the committed cache stays readable and so the same frame
    always produces the same bytes. The file is written to a temporary name in
    the same directory and then moved into place with os.replace, so a crash
    midway cannot leave a half written cache.

    The LF ending needs saying twice, because opening the handle with
    newline="\\n" is not enough on Windows. pandas.to_csv defaults its
    lineterminator to os.linesep, which is written straight through a handle that
    has already disabled translation, so the file comes out CRLF while the
    docstring says LF. lineterminator is passed explicitly below and a test
    asserts on the bytes. The sibling repository shipped five CRLF caches before
    noticing.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("write_cache expects a DataFrame, got %r" % (type(df),))

    path = _cache_path(name, directory=directory)
    path.parent.mkdir(parents=True, exist_ok=True)

    out = df.copy()
    if date_col in out.columns:
        out[date_col] = pd.to_datetime(out[date_col], errors="coerce").dt.strftime(
            "%Y-%m-%d"
        )
    for col in out.columns:
        if col == date_col:
            continue
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")

    tmp = path.with_name(path.name + ".tmp.%d" % os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            out.to_csv(
                handle,
                index=False,
                float_format=_format_float,
                na_rep="",
                lineterminator="\n",
            )
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


# --------------------------------------------------------------------------
# Gaps
# --------------------------------------------------------------------------

def missing_business_days(dates: Iterable[Any]) -> list[str]:
    """Weekdays between the first and last observation with no observation.

    Returns ISO yyyy-mm-dd strings, sorted ascending.

    This counts exchange and bank holidays as gaps. No holiday calendar is
    bundled with this repository, and the three daily series in this project keep
    three different ones, FRED's Brent following a UK and European calendar,
    FRED's EUR/USD following the US federal calendar and TTF following the
    exchange calendar, so Christmas Day and Good Friday appear in this list
    exactly like a genuine failed fetch. Read the output as "weekdays with no
    observation", not as "days the source lost". Recon 04 measured eight or nine
    a year for Brent, so a list of that size is normal and expected.
    """
    index = _clean_dates(dates)
    if len(index) < 2:
        return []
    expected = pd.bdate_range(index.min(), index.max(), freq="B")
    return _format_dates(expected.difference(index))


def _clean_dates(dates: Iterable[Any]) -> pd.DatetimeIndex:
    parsed = pd.to_datetime(pd.Series(list(dates)), errors="coerce").dropna()
    if parsed.empty:
        return pd.DatetimeIndex([])
    return pd.DatetimeIndex(parsed.dt.normalize().unique()).sort_values()


def _format_dates(index: pd.DatetimeIndex) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in index]


def find_gaps(dates: Iterable[Any], frequency: str) -> list[str]:
    """Periods between the first and last observation that carry no observation.

    THE FREQUENCY IS NOT OPTIONAL. The sibling repository had only daily series
    and one missing_weekdays helper was enough for it. This project carries daily
    quotations, weekly ministry notes, monthly margins and annual capacity at the
    same time, and running the daily rule over a monthly series would report
    about twenty gaps a month for a series with none.

    Args:
        dates: the dates that carry an observation. Dates with no observation
            must not be passed in, or a hole becomes invisible: the Adapter
            filters on its observation_column before calling this.
        frequency: one of crack.config.FREQUENCIES.

            daily     every business day in the span must appear. Weekends are
                      not gaps, holidays are reported as gaps because no holiday
                      calendar is bundled.
            weekly    every ISO week in the span must carry at least one
                      observation. A gap is reported as the Monday of the missing
                      week. The weekday is deliberately not checked: the ministry
                      notes are dated by publication and slip by a day or two,
                      and a note published on a Thursday instead of a Friday is
                      not a missing week.
            monthly   every calendar month in the span must carry at least one
                      observation. A gap is reported as the first of the month.
            annual    every year in the span must carry at least one
                      observation. A gap is reported as the first of January.

    Returns:
        ISO yyyy-mm-dd strings, sorted ascending. Empty when there is nothing
        between the first and last observation, which includes the case of a
        single observation.

    Raises:
        ValueError: on an unknown frequency. Guessing would produce a gap list
            that looks authoritative and means nothing.
    """
    if frequency not in FREQUENCIES:
        raise ValueError(
            "frequency %r is not one of %s" % (frequency, ", ".join(FREQUENCIES))
        )
    if frequency == "daily":
        return missing_business_days(dates)

    index = _clean_dates(dates)
    if len(index) < 2:
        return []

    if frequency == "weekly":
        # Monday of each observation's ISO week.
        anchors = pd.DatetimeIndex(
            index - pd.to_timedelta(index.dayofweek, unit="D")
        ).unique()
        expected = pd.date_range(anchors.min(), anchors.max(), freq="W-MON")
    elif frequency == "monthly":
        anchors = pd.DatetimeIndex(index.to_period("M").to_timestamp()).unique()
        expected = pd.date_range(anchors.min(), anchors.max(), freq="MS")
    else:  # annual
        anchors = pd.DatetimeIndex(index.to_period("Y").to_timestamp()).unique()
        expected = pd.date_range(anchors.min(), anchors.max(), freq="YS")

    return _format_dates(expected.difference(anchors))


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

#: The bounds SPEC.md section 5.4 names, gathered under the names the spec uses
#: so an adapter can reach for one by meaning rather than retype a pair of
#: numbers. The numbers themselves live in crack.config with their reasoning.
SPEC_BOUNDS: Mapping[str, tuple[float, float]] = {
    "product_usd_t": BOUNDS_PRODUCT_USD_T,
    "brent_usd_bbl": BOUNDS_BRENT_USD_BBL,
    "crack_usd_bbl": BOUNDS_CRACK_USD_BBL,
    "intake_kb_d": BOUNDS_INTAKE_KB_D,
}


def observation_count(values: Any) -> int:
    """How many cells of a column are real observations.

    A cell is an observation when it is not NaN, not None and, for a text column,
    not blank once stripped. This is the counterpart of the NaN rule: a missing
    observation is written as nothing, so anything that reads back as nothing is
    not an observation and must not be counted as one.
    """
    if values is None:
        return 0
    series = values if isinstance(values, pd.Series) else pd.Series(values)
    filled = series.notna()
    if not pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_datetime64_any_dtype(
        series
    ):
        filled = filled & series.astype(str).str.strip().ne("")
    return int(filled.sum())


def validate_frame(
    df: Any,
    *,
    date_col: str = "date",
    required_cols: Sequence[str] = (),
    bounds: Mapping[str, tuple[float, float]] | None = None,
    min_rows: int = 1,
    min_observations: Mapping[str, int] | None = None,
    previous: Any = None,
) -> list[str]:
    """Check a frame before it is allowed to become the cache. SPEC.md 5.4.

    Args:
        df: the candidate frame.
        date_col: name of the date column.
        required_cols: columns that must exist.
        bounds: col -> (lo, hi), inclusive, NaN ignored. A NaN is a declared
            missing observation and is never a bounds failure, that is the whole
            point of writing NaN rather than a guess.
        min_rows: the frame must have at least this many rows.
        min_observations: col -> the fewest real observations that column is
            allowed to carry, where an observation is a cell that is not NaN and
            not blank. This is the check that stops an all NaN frame with the
            right dates replacing a good cache, because row count alone cannot
            see the difference. Declare it per adapter and never as one global
            constant: the seeded EIA figures are four numbers and their honest
            floor is four, while the Brent column's floor is thousands. When
            previous carries the same column, the count must also not have shrunk
            against it, so a source that silently blanks half a column fails even
            while it stays above the floor.
        previous: the frame currently on disk, or an integer row count. If it is
            given, the new frame must not have fewer rows.

    Returns:
        A list of human readable problems. An empty list means the frame is
        valid. Nothing is raised, the caller decides what a problem costs.
    """
    problems: list[str] = []

    if not isinstance(df, pd.DataFrame):
        return ["expected a DataFrame, got %s" % type(df).__name__]

    for col in required_cols:
        if col not in df.columns:
            problems.append("missing required column %r" % col)

    if len(df) < min_rows:
        problems.append("row count %d is below the minimum of %d" % (len(df), min_rows))

    if date_col not in df.columns:
        problems.append("missing date column %r" % date_col)
    else:
        raw = df[date_col]
        parsed = pd.to_datetime(raw, errors="coerce")
        bad = int(parsed.isna().sum()) - int(pd.isna(raw).sum())
        if bad > 0:
            examples = raw[parsed.isna() & raw.notna()].astype(str).tolist()[:3]
            problems.append(
                "%d value(s) in %r do not parse as a date, for example %s"
                % (bad, date_col, ", ".join(examples))
            )
        if parsed.isna().any():
            problems.append(
                "%d empty date(s) in %r" % (int(parsed.isna().sum()), date_col)
            )

        clean = parsed.dropna()
        duplicates = clean[clean.duplicated()].dt.strftime("%Y-%m-%d").unique().tolist()
        if duplicates:
            problems.append(
                "duplicate date(s): %s%s"
                % (", ".join(duplicates[:5]), " and more" if len(duplicates) > 5 else "")
            )
        if len(clean) > 1 and not clean.is_monotonic_increasing:
            first_break = next(
                (i for i in range(1, len(clean)) if clean.iloc[i] < clean.iloc[i - 1]),
                None,
            )
            where = (
                " first at row %d, %s follows %s"
                % (
                    first_break,
                    clean.iloc[first_break].strftime("%Y-%m-%d"),
                    clean.iloc[first_break - 1].strftime("%Y-%m-%d"),
                )
                if first_break is not None
                else ""
            )
            problems.append("dates are not increasing,%s" % where)

    for col, pair in (bounds or {}).items():
        if col not in df.columns:
            problems.append("bounds given for missing column %r" % col)
            continue
        lo, hi = pair
        values = pd.to_numeric(df[col], errors="coerce")
        unparsed = int(values.isna().sum()) - int(pd.isna(df[col]).sum())
        if unparsed > 0:
            problems.append("%d non numeric value(s) in %r" % (unparsed, col))
        outside = values.notna() & ((values < lo) | (values > hi))
        count = int(outside.sum())
        if count:
            worst = values[outside]
            problems.append(
                "%d value(s) in %r outside [%g, %g], for example %s"
                % (count, col, lo, hi, _format_float(float(worst.iloc[0])))
            )

    for col, floor in (min_observations or {}).items():
        if col not in df.columns:
            problems.append(
                "a minimum observation count was given for missing column %r" % col
            )
            continue
        count = observation_count(df[col])
        if count < int(floor):
            problems.append(
                "column %r holds %d observation(s), below the declared minimum of "
                "%d. A column with no values in it is not a cheaper version of "
                "the same series, it is a different series" % (col, count, int(floor))
            )
            continue
        if isinstance(previous, pd.DataFrame) and col in previous.columns:
            before = observation_count(previous[col])
            if count < before:
                problems.append(
                    "observation count in %r shrank from %d to %d against the "
                    "cache already on disk" % (col, before, count)
                )

    if previous is not None:
        if isinstance(previous, pd.DataFrame):
            previous_rows = len(previous)
        elif isinstance(previous, (int, np.integer)):
            previous_rows = int(previous)
        else:
            problems.append(
                "previous must be a DataFrame or a row count, got %s"
                % type(previous).__name__
            )
            previous_rows = None
        if previous_rows is not None and len(df) < previous_rows:
            problems.append("row count shrank from %d to %d" % (previous_rows, len(df)))

    return problems


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------

MANIFEST_SCHEMA_VERSION = 1

STATUS_VALUES = ("ok", "stale", "failed")

# SPEC.md section 5.3 is the floor, not the ceiling. Five fields are added to it
# and each one exists because this project has a series the sibling did not:
#
#   method        one series is RECONSTRUCTED from the curves of a published
#                 chart. SPEC.md section 2 rule 1 means that has to be declared
#                 where the data is, not mentioned in prose somewhere else.
#   committable   two caches may not be redistributed, the Energy Institute
#                 capacity table and the Yahoo TTF series. The flag is what keeps
#                 them out of data/cache and therefore out of the commit.
#   frequency     gap lists mean nothing without it, see find_gaps.
#   page_url      the machine URL of several sources rots or has to be scraped,
#                 so the human page is the stable thing to link on the provenance
#                 panel.
#   observations  rows counts the lines in the file, observations counts the ones
#                 that carry a value for this series. They differ whenever the
#                 source emits a row for a day it published nothing, which FRED
#                 does about eight times a year.
#
# provisional_from and vintage come straight from SPEC.md section 5.3 and matter
# here more than anywhere: the current month in the ministry notes is provisional
# and gets revised, SPEC.md section 2 rule 5.
ENTRY_KEYS = (
    "series",
    "source",
    "url",
    "page_url",
    "machine_fetched",
    "fetched_at",
    "checked_at",
    "rows",
    "observations",
    "file_rows",
    "first_date",
    "last_date",
    "frequency",
    "gaps",
    "provisional_from",
    "vintage",
    "method",
    "committable",
    "licence_note",
    "status",
    "note",
    "file",
    "unit",
)


def manifest_read() -> dict:
    """Read data/manifest.json, returning an empty manifest if it is absent.

    A manifest that exists but does not parse is an error worth surfacing, not
    something to silently replace, so the JSON error propagates.
    """
    if not MANIFEST.exists():
        return {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "generated_at": utc_now_iso(),
            "series": [],
        }
    with open(MANIFEST, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    payload.setdefault("schema_version", MANIFEST_SCHEMA_VERSION)
    payload.setdefault("generated_at", utc_now_iso())
    payload.setdefault("series", [])
    if not isinstance(payload["series"], list):
        raise ValueError(
            "manifest 'series' must be a list, found %s"
            % type(payload["series"]).__name__
        )
    return payload


def manifest_upsert(entry: Mapping[str, Any]) -> None:
    """Insert or replace one series entry in data/manifest.json.

    The entry is matched on its "series" key, so running an adapter twice updates
    the record rather than appending a second one. The list is kept sorted by
    series name and the file is written atomically as utf-8 with LF endings,
    which keeps the committed diff to the lines that actually changed.

    Five things are refused here rather than left to a convention, and each is a
    way the manifest could otherwise tell a lie:

        a status outside the vocabulary
        a method outside the vocabulary, or absent. The manifest is where a
            reconstructed series declares itself, so "not stated" is not an
            option.
        a committable flag that is not a boolean. It decides where bytes land.
        a series that declares machine_fetched false while carrying a fetch time.
            A hand seeded file was never fetched, so it must not carry a
            fetched_at for the provenance panel to print. Record checked_at.
        a series marked not committable with nothing in licence_note. The boolean
            is what the code reads, the sentence is what a human reads, and the
            sentence is the part that can be checked.
    """
    if "series" not in entry:
        raise ValueError(
            "a manifest entry needs a 'series' key, got keys %s" % sorted(entry)
        )
    status = entry.get("status")
    if status not in STATUS_VALUES:
        raise ValueError("status %r is not one of %s" % (status, ", ".join(STATUS_VALUES)))
    method = entry.get("method")
    if method not in METHODS:
        raise ValueError(
            "series %r declares method %r, which is not one of %s. Every series "
            "states how it came to exist, because one of them is reconstructed "
            "from a chart" % (entry.get("series"), method, ", ".join(METHODS))
        )
    committable = entry.get("committable")
    if not isinstance(committable, bool):
        raise ValueError(
            "series %r declares committable %r. It must be True or False, it "
            "decides whether the cache may be published"
            % (entry.get("series"), committable)
        )
    if entry.get("machine_fetched") is False and entry.get("fetched_at") is not None:
        raise ValueError(
            "series %r declares machine_fetched false and a fetched_at of %r. A "
            "file nothing fetched has no fetch time, record checked_at instead"
            % (entry.get("series"), entry.get("fetched_at"))
        )
    if committable is False and not entry.get("licence_note"):
        raise ValueError(
            "series %r is not committable and carries no licence_note saying "
            "what is forbidden" % (entry.get("series"),)
        )

    record = {key: entry.get(key) for key in ENTRY_KEYS}
    extra = {k: v for k, v in entry.items() if k not in ENTRY_KEYS}
    record.update(extra)

    payload = manifest_read()
    kept = [e for e in payload["series"] if e.get("series") != record["series"]]
    kept.append(record)
    kept.sort(key=lambda e: str(e.get("series")))
    payload["series"] = kept
    payload["schema_version"] = MANIFEST_SCHEMA_VERSION
    payload["generated_at"] = utc_now_iso()
    # THE MANUAL STEPS ARE REATTACHED ON EVERY WRITE, not only by
    # scripts/refresh.py. The entry built above is a fresh dict and carries no
    # manual_step, so an adapter run that wrote one directly used to strip the
    # field and leave a tree that tools/validate-data.mjs rejects. `make note` is
    # such a run and the scheduled workflow runs it unattended. apply is pure and
    # idempotent, so this costs a refresh nothing. See crack.manual_steps.
    manual_steps.apply(payload)

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_name(MANIFEST.name + ".tmp.%d" % os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=True, sort_keys=False)
            handle.write("\n")
        os.replace(tmp, MANIFEST)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


# --------------------------------------------------------------------------
# Adapter
# --------------------------------------------------------------------------

class Adapter:
    """Base class for a single data source.

    A subclass sets the class attributes and implements fetch(). It gets
    validation, atomic cache writing, gap detection at the right frequency and
    manifest bookkeeping for free, and it cannot accidentally overwrite a good
    cache with a bad frame or publish a cache it is not allowed to publish.

        class FredBrent(Adapter):
            name = "fred_brent_daily"
            source = "US EIA, retrieved from FRED"
            url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU"
            page_url = "https://fred.stlouisfed.org/series/DCOILBRENTEU"
            unit = "USD per barrel"
            frequency = "daily"
            method = "published"
            required_cols = ("date", "brent_usd_bbl")
            bounds = {"brent_usd_bbl": SPEC_BOUNDS["brent_usd_bbl"]}
            min_observations = {"brent_usd_bbl": 9000}
            observation_column = "brent_usd_bbl"

            def fetch(self):
                ...
                return frame

        entry = FredBrent().run()
    """

    #: cache file stem, and the series name in the manifest. When it matches a
    #: key of crack.config.SOURCES, run() checks that this class and the registry
    #: agree about frequency, method and committable.
    name: str = ""
    #: human readable source, for example "DGEC via ecologie.gouv.fr"
    source: str = ""
    #: the exact URL the data came from
    url: str = ""
    #: the human readable page, for the provenance panel. Several of this
    #: project's machine URLs have to be scraped or rot, so this is the link the
    #: site shows.
    page_url: str = ""
    #: unit of the value columns, for example "USD per tonne"
    unit: str = ""
    #: one of crack.config.FREQUENCIES. Gap detection needs it.
    frequency: str = "daily"
    #: one of crack.config.METHODS. "reconstructed" is not a shameful label, it
    #: is a true one, and the site prints it.
    method: str = "published"
    #: False when the cache may not be redistributed. It sends the file to
    #: data/private/ instead of data/cache/, SPEC.md section 2 rule 6.
    committable: bool = True
    #: what the terms permit and forbid, in words. Required when committable is
    #: False.
    licence_note: str = ""
    #: col -> (lo, hi), inclusive, checked before the cache is replaced
    bounds: Mapping[str, tuple[float, float]] = {}
    #: columns fetch() must return
    required_cols: Sequence[str] = ("date",)
    #: the date column
    date_col: str = "date"
    #: refuse a frame smaller than this
    min_rows: int = 1
    #: col -> fewest real observations that column may carry. Every adapter
    #: declares this for every value column it writes. See validate_frame.
    min_observations: Mapping[str, int] = {}
    #: the column whose non blank cells define an observation of this series.
    #: None means every dated row counts, which is right only for a file where
    #: the row itself is the observation, such as a calendar of dates.
    observation_column: str | None = None
    #: whether this is machine fetched. False forbids a fetched_at, see
    #: manifest_upsert, and sends the file to data/seed.
    machine_fetched: bool = True
    #: the first date from which the source calls its own figures provisional,
    #: SPEC.md section 2 rule 5. The current month in the ministry notes is
    #: provisional and gets revised, and the site shows the flag.
    provisional_from: str | None = None
    #: which edition of the source this came from, for example "NPG-2026.09.04"
    #: or "EI Statistical Review 2026". Set by fetch() when it can only be known
    #: after the fetch.
    vintage: str | None = None
    #: free text carried into the manifest on success
    note: str = ""

    def fetch(self) -> pd.DataFrame:
        """Return a frame with a date column and the series columns.

        Subclasses implement this. It may raise, run() will record the failure.
        Missing observations must be NaN. Do not interpolate, do not substitute a
        neighbouring source without saying so in the note, SPEC.md section 2
        rule 1.
        """
        raise NotImplementedError("%s must implement fetch()" % type(self).__name__)

    # -- internals ---------------------------------------------------------

    def directory(self) -> str:
        """Which data directory this adapter reads and writes.

        Three outcomes and one rule each:

            private   the terms forbid redistribution, so the bytes never reach
                      a commit. SPEC.md section 2 rule 6. Today this is the
                      Energy Institute capacity table, which may not be
                      reproduced extensively and carries S&P sourced rows, and
                      the Yahoo TTF series, which has no grant at all.
            seed      nothing fetched it. data/cache is reserved for what a
                      source actually served, so a hand seeded file does not get
                      to sit there and look like a record of the market.
            cache     machine fetched and publishable.

        run() uses this for the read and the write, and cache_file() uses it for
        the manifest, so the declared path and the real one cannot disagree.
        """
        if not self.committable:
            return "private"
        return "cache" if self.machine_fetched else "seed"

    def cache_file(self) -> str:
        """Repo relative path of the file this adapter owns."""
        return "data/%s/%s.csv" % (self.directory(), self.name)

    def _check_declarations(self) -> None:
        """Refuse an adapter whose declarations cannot be trusted, before fetching.

        Each of these is a hole that would otherwise open quietly at some later
        gate, so they are closed by construction here rather than by a test over
        a hardcoded list of adapters that a new adapter would not be in.
        """
        if not self.name:
            raise ValueError("%s has no name" % type(self).__name__)
        if self.frequency not in FREQUENCIES:
            raise SourceError(
                "%s declares frequency %r, not one of %s. Gap detection cannot "
                "guess" % (self.name, self.frequency, ", ".join(FREQUENCIES))
            )
        if self.method not in METHODS:
            raise SourceError(
                "%s declares method %r, not one of %s"
                % (self.name, self.method, ", ".join(METHODS))
            )
        if not isinstance(self.committable, bool):
            raise SourceError(
                "%s declares committable %r, which must be True or False"
                % (self.name, self.committable)
            )
        if not self.committable and not self.licence_note:
            raise SourceError(
                "%s is not committable and carries no licence_note. The flag "
                "keeps the bytes out of the repository, the sentence is what "
                "tells a reader why" % (self.name,)
            )

        # Fail closed, not opt in. A column this adapter bounds is a value
        # column, and a value column with no floor can be emptied to all NaN
        # without validate_frame noticing, because NaN is exempt from bounds by
        # design. The sibling repository found this the hard way: two probe cases
        # each replaced a good 40 row cache with an all NaN one and every gate
        # stayed green.
        unfloored = sorted(set(self.bounds) - set(self.min_observations))
        if unfloored:
            raise SourceError(
                "%s bounds %s but declares no min_observations floor for %s, so "
                "an all NaN column would be accepted. Declare a floor per value "
                "column."
                % (self.name, ", ".join(sorted(self.bounds)), ", ".join(unfloored))
            )

        # A registered series and its adapter must agree. The registry is what
        # the provenance panel and docs/sources.md are built from, so a class
        # that quietly disagreed with it would publish one story and act on
        # another.
        registered = SOURCES.get(self.name)
        if registered is None:
            return
        for field in ("frequency", "method", "committable"):
            mine = getattr(self, field)
            theirs = getattr(registered, field)
            if mine != theirs:
                raise SourceError(
                    "%s declares %s=%r but crack.config.SOURCES declares %r. The "
                    "registry is what the provenance panel prints, so the two "
                    "cannot disagree" % (self.name, field, mine, theirs)
                )

    def _entry(self, *, status: str, frame: pd.DataFrame | None, note: str) -> dict:
        # Two counts, and they mean different things on purpose. file_rows is how
        # many data lines the file has. observations is how many of them carry a
        # value for THIS series, which is the only one of the two that is
        # comparable across series and the only one gaps are computed from. rows
        # is kept as the SPEC.md section 5.3 name for observations.
        observations = 0
        file_rows = 0
        first_date = None
        last_date = None
        gaps: list[str] = []
        if frame is not None and len(frame) and self.date_col in frame.columns:
            file_rows = len(frame)
            dates = pd.to_datetime(frame[self.date_col], errors="coerce")
            present = dates.notna()
            column = self.observation_column
            if column and column in frame.columns:
                values = frame[column]
                filled = values.notna()
                if not pd.api.types.is_numeric_dtype(values):
                    filled = filled & values.astype(str).str.strip().ne("")
                present = present & filled
            have = dates[present]
            observations = int(len(have))
            if observations:
                first_date = have.min().strftime("%Y-%m-%d")
                last_date = have.max().strftime("%Y-%m-%d")
                gaps = find_gaps(have, self.frequency)
        return {
            "series": self.name,
            "source": self.source,
            "url": self.url,
            "page_url": self.page_url,
            "machine_fetched": bool(self.machine_fetched),
            "fetched_at": utc_now_iso() if self.machine_fetched else None,
            # A file nothing fetched has no fetch time but it does have a moment
            # when this run last looked at it and found it unchanged, which is
            # what the provenance panel should print in its place. This is the
            # field manifest_upsert's error message points at.
            "checked_at": None if self.machine_fetched else utc_now_iso(),
            "rows": observations,
            "observations": observations,
            "file_rows": file_rows,
            "first_date": first_date,
            "last_date": last_date,
            "frequency": self.frequency,
            "gaps": gaps,
            "provisional_from": self.provisional_from,
            "vintage": self.vintage,
            "method": self.method,
            "committable": bool(self.committable),
            "licence_note": self.licence_note,
            "status": status,
            "note": note,
            "file": self.cache_file(),
            "unit": self.unit,
            # Declared, never inferred. tools/validate-data.mjs recounts the
            # observations from the file and needs to know which column defines
            # one, and a missing declaration there is a failure rather than a
            # silent fallback.
            "observation_column": self.observation_column,
        }

    def run(self) -> dict:
        """Fetch, validate, write, and record. Returns the manifest entry.

        On success the cache is replaced and an "ok" entry is written. On any
        failure, a raising fetch() or a frame that does not validate, the cache
        already on disk is left exactly as it was, a "failed" entry carrying the
        error text in "note" is written, and the exception is re raised so the
        caller can exit non zero. SPEC.md section 5.4.
        """
        self._check_declarations()

        existing = read_cache(
            self.name, date_col=self.date_col, directory=self.directory()
        )

        try:
            frame = self.fetch()
            problems = validate_frame(
                frame,
                date_col=self.date_col,
                required_cols=self.required_cols,
                bounds=self.bounds,
                min_rows=self.min_rows,
                min_observations=self.min_observations,
                previous=existing,
            )
            if problems:
                raise SourceError(
                    "%s did not validate: %s" % (self.name, "; ".join(problems))
                )
        except Exception as exc:
            entry = self._entry(
                status="failed",
                frame=existing,
                note="fetch failed, previous cache kept unchanged. %s: %s"
                % (type(exc).__name__, exc),
            )
            manifest_upsert(entry)
            raise

        write_cache(self.name, frame, date_col=self.date_col, directory=self.directory())
        entry = self._entry(status="ok", frame=frame, note=self.note)
        manifest_upsert(entry)
        return entry
