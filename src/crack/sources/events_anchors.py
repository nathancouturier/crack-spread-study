"""The two hand written, cited JSON files: the events and the anchors.

SPEC.md section 8 puts three files in data/seed. One of them,
eia_refinery_fuel_2023.json, is loaded by crack.sources.eia because the gas
intensity is derived from it. The other two are loaded here:

    events.json   SPEC.md section 6.5. Dated events and structural breaks, one
                  source_url per entry, "include only what you can cite".
    anchors.json  SPEC.md sections 5.5 and 8. The published DGEC figures the
                  pipeline must reproduce, plus the S&P Global order of
                  magnitude references, so that the tests and the site read them
                  from data rather than from literals.

Nothing here fetches anything. These are files a person wrote, and the only work
this module does is refuse to load one that cannot be checked and put an honest
entry in data/manifest.json for each.

WHY ONE FILE PRODUCES TWO MANIFEST ENTRIES
------------------------------------------
anchors.json holds two blocks under two different sets of terms. The DGEC
anchors are Licence Ouverte 2.0, which permits republication with attribution.
The S&P Global figures are quoted from two news articles under ordinary
quotation and are not redistributable as a series. SPEC.md non negotiable 6
records reuse terms per source, and the manifest is where a reader looks them
up, so the file gets two entries: "anchors" and "sp_global_reference". They name
the same file and say so. Splitting the file instead would have put two hand
written anchor files in data/seed for no gain.

WHAT IS REFUSED, AND WHY EACH REFUSAL EXISTS
--------------------------------------------
An event with no source_url, because SPEC.md section 6.5 says to include only
what can be cited and a seeded event with no citation is indistinguishable from
an invention a year from now. An event whose date does not parse as a day or a
month, because a date that the site cannot place on an axis is not an event. An
event whose date_precision disagrees with the shape of its date, because "day"
against a "2015-01" is exactly the invented day SPEC.md non negotiable 8 is
about. An anchor with no source_url, for the same reason as an event. And an
anchors file that claims a reproduction the committed caches do not support,
because that claim is the whole reason the file is worth reading.

THE CLAIM IS RE MEASURED, NOT RE READ
--------------------------------------
"mbr_anchors_reproduced": 9 in the manifest used to be a count of the
"reproduces": true flags in the seed file. The Gate 1 self audit, finding d.1,
set July 2026 in data/cache/dgec_mbr_monthly.csv to 99.99 and watched
`refresh.py --offline` report 19 of 19 ok while the manifest went on saying the
anchors reproduced, byte identically, because nothing in that run had opened the
cache the claim was about. measure_mbr_reproduction below opens it on every run,
online and offline. When an anchor does not reproduce the entry goes to status
"failed" with the disagreement in its note and record_anchors raises, so the run
exits non zero and the manifest says so. A manifest must not assert a check that
was not run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from ..config import source as registered_source
from .base import CACHE, SEED, SourceError, manifest_upsert, utc_now_iso

__all__ = [
    "EVENTS_SERIES",
    "EVENTS_FILENAME",
    "ANCHORS_SERIES",
    "SP_SERIES",
    "ANCHORS_FILENAME",
    "MBR_CACHE",
    "MBR_COLUMN",
    "events_path",
    "anchors_path",
    "load_events",
    "load_anchors",
    "measure_mbr_reproduction",
    "record_events",
    "record_anchors",
    "record_all",
]


EVENTS_SERIES = "events"
EVENTS_FILENAME = "events.json"

ANCHORS_SERIES = "anchors"
SP_SERIES = "sp_global_reference"
ANCHORS_FILENAME = "anchors.json"

#: The committed cache the MBR anchors are claimed to reproduce from, and the
#: column the claim is about. Named here rather than inline because the whole
#: point of measure_mbr_reproduction is that the manifest's claim and the file it
#: is a claim about cannot drift apart.
MBR_CACHE = "dgec_mbr_monthly.csv"
MBR_COLUMN = "mbr_usd_bbl"

#: A date is a day, yyyy-mm-dd, or a month, yyyy-mm. Nothing else. The precision
#: is declared in the entry as well, and the two must agree.
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH = re.compile(r"^\d{4}-\d{2}$")

#: Every event carries these. The list is short on purpose: it is the set a
#: reader needs to decide whether to believe the entry, not everything the site
#: might one day want to render.
EVENT_REQUIRED = (
    "id",
    "date",
    "date_precision",
    "label",
    "what",
    "kind",
    "layer",
    "source_url",
    "source_title",
    "source_publisher",
    "url_checked_at",
    "url_status",
)

EVENT_KINDS = (
    "market",
    "policy",
    "specification_break",
    "definition_change",
    "method_change",
    "reference",
)

EVENT_LAYERS = ("all", "daily", "weekly", "monthly")


def events_path(root: Path | str | None = None) -> Path:
    """Path of the committed events file."""
    return (Path(root) if root is not None else SEED) / EVENTS_FILENAME


def anchors_path(root: Path | str | None = None) -> Path:
    """Path of the committed anchors file."""
    return (Path(root) if root is not None else SEED) / ANCHORS_FILENAME


def _read(path: Path, what: str) -> dict:
    if not path.exists():
        raise SourceError(
            "%s: %s is not on disk. It is a committed seed file, not something a "
            "run creates" % (what, path)
        )
    with open(path, "r", encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except ValueError as exc:
            raise SourceError("%s: %s does not parse as JSON: %s" % (what, path, exc)) from None


def _date_problems(entry: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    date = entry.get("date")
    precision = entry.get("date_precision")
    if not isinstance(date, str):
        return ["date is %r, which is not a string" % (date,)]
    is_day = bool(_DAY.match(date))
    is_month = bool(_MONTH.match(date))
    if not (is_day or is_month):
        problems.append("date %r is neither yyyy-mm-dd nor yyyy-mm" % date)
        return problems
    if precision == "day" and not is_day:
        problems.append(
            "declares date_precision 'day' with the date %r, which names a month. "
            "A day nobody published is a day this project invented" % date
        )
    if precision == "month" and not is_month:
        problems.append(
            "declares date_precision 'month' with the date %r, which names a day" % date
        )
    if precision not in ("day", "month"):
        problems.append("date_precision is %r, not 'day' or 'month'" % (precision,))
    return problems


def _as_day(date: str) -> str:
    """A yyyy-mm becomes the first of that month. A yyyy-mm-dd is unchanged."""
    return date if _DAY.match(date) else "%s-01" % date


def load_events(root: Path | str | None = None) -> dict:
    """Read and check data/seed/events.json.

    Returns the payload with an added "_by_id" mapping and an "_events" list
    sorted by date then id, so callers never have to re sort and two callers
    cannot disagree about the order.

    Raises:
        SourceError: listing every problem it found rather than the first, so one
            run fixes the file rather than three.
    """
    path = events_path(root)
    payload = _read(path, "events")

    events = payload.get("events")
    if not isinstance(events, list) or not events:
        raise SourceError("events: %s carries no 'events' list" % path)

    problems: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(events):
        if not isinstance(entry, dict):
            problems.append("entry %d is not an object" % index)
            continue
        name = entry.get("id") or "entry %d" % index
        for key in EVENT_REQUIRED:
            if not entry.get(key):
                problems.append("%s has no %s" % (name, key))
        if entry.get("id") in seen:
            problems.append("%s appears twice, ids must be unique" % name)
        seen.add(entry.get("id"))
        for problem in _date_problems(entry):
            problems.append("%s %s" % (name, problem))
        if entry.get("kind") and entry["kind"] not in EVENT_KINDS:
            problems.append(
                "%s declares kind %r, not one of %s"
                % (name, entry["kind"], ", ".join(EVENT_KINDS))
            )
        if entry.get("layer") and entry["layer"] not in EVENT_LAYERS:
            problems.append(
                "%s declares layer %r, not one of %s"
                % (name, entry["layer"], ", ".join(EVENT_LAYERS))
            )
        for extra in entry.get("additional_sources") or []:
            if not extra.get("url"):
                problems.append("%s carries an additional source with no url" % name)

    if problems:
        raise SourceError(
            "events: %s is not usable, %d problem(s): %s. SPEC.md section 6.5 says "
            "to include only what you can cite"
            % (path, len(problems), "; ".join(problems))
        )

    ordered = sorted(events, key=lambda e: (e["date"], e["id"]))
    payload["_events"] = ordered
    payload["_by_id"] = {e["id"]: e for e in ordered}
    return payload


def load_anchors(root: Path | str | None = None) -> dict:
    """Read and check data/seed/anchors.json.

    Raises:
        SourceError: when a block is missing, when an anchor carries no
            source_url, or when the MBR block claims a reproduction it does not
            back up with a measured value. The last one matters: the file is only
            worth reading because it says what the committed caches actually do,
            and a "reproduces": true with no measured_value beside it would be a
            claim rather than a measurement.
    """
    path = anchors_path(root)
    payload = _read(path, "anchors")

    anchors = payload.get("anchors")
    if not isinstance(anchors, dict):
        raise SourceError("anchors: %s carries no 'anchors' object" % path)

    problems: list[str] = []

    mbr = anchors.get("mbr_monthly_usd_bbl", {}).get("values") or []
    if not mbr:
        problems.append("no MBR anchors, SPEC.md section 5.5 prints nine")
    for item in mbr:
        name = item.get("key", "an MBR anchor")
        if not item.get("source_url"):
            problems.append("%s has no source_url" % name)
        if "printed_value" not in item:
            problems.append("%s has no printed_value" % name)
        if item.get("reproduces") and "measured_value" not in item:
            problems.append(
                "%s claims it reproduces but carries no measured_value. A claim is "
                "not a measurement" % name
            )

    brent = anchors.get("brent_july_2026_usd_t")
    if not brent:
        problems.append("no brent_july_2026_usd_t anchor")
    elif not brent.get("source_url"):
        problems.append("brent_july_2026_usd_t has no source_url")

    products = anchors.get("july_2026_products_usd_t", {}).get("values") or []
    for item in products:
        if not item.get("source_url"):
            problems.append("%s has no source_url" % item.get("key", "a product anchor"))
        if not item.get("status"):
            problems.append(
                "%s does not say whether it is verified. The five July 2026 product "
                "anchors are not, and the file has to say so"
                % item.get("key", "a product anchor")
            )

    cross = anchors.get("brent_cross_check")
    if not cross:
        problems.append("no brent_cross_check block, SPEC.md section 5.5 requires it")
    elif "outliers" not in cross:
        problems.append(
            "brent_cross_check carries no outliers list. SPEC.md section 5.5 says "
            "list every outlier, and an empty list is an answer while a missing key "
            "is not"
        )

    references = payload.get("sp_global_reference", {}).get("references") or []
    if not references:
        problems.append("no sp_global_reference block")
    for item in references:
        if not item.get("source_url"):
            problems.append("%s has no source_url" % item.get("key", "an S&P reference"))

    if problems:
        raise SourceError(
            "anchors: %s is not usable, %d problem(s): %s"
            % (path, len(problems), "; ".join(problems))
        )

    payload["_mbr"] = {item["month"]: item for item in mbr}
    payload["_references"] = {item["key"]: item for item in references}
    return payload


def measure_mbr_reproduction(mbr: Mapping[str, Mapping[str, Any]]) -> dict:
    """Re derive, from the committed cache, whether each MBR anchor reproduces.

    THE MANIFEST MUST NOT ASSERT A CHECK THAT WAS NOT RUN. Gate 1 self audit,
    finding d.1: the audit set July 2026 in data/cache/dgec_mbr_monthly.csv to
    99.99, a 172 percent error on a published anchor and comfortably inside its
    bounds, and `refresh.py --offline` reported 19 of 19 ok while the manifest
    went on carrying "mbr_anchors_reproduced": 9 and a note saying the anchors
    reproduce. It went on carrying it BYTE IDENTICALLY, because the field was
    read out of data/seed/anchors.json rather than measured against the cache
    the claim is about.

    This function is that measurement. It opens the committed cache, rounds each
    month the way DGEC prints it, and compares. The caller writes what comes back
    into the manifest, and marks the entry failed when anything disagrees.

    Returns:
        A dict with "reproduced", "checked", "failures" (a list of human readable
        lines) and "cache", the repository relative path that was read.

    Raises:
        SourceError: when the cache is absent or unreadable. An anchor block that
            cannot be checked is not an anchor block that passed.
    """
    path = CACHE / MBR_CACHE
    relative = "data/cache/%s" % MBR_CACHE
    if not path.exists():
        raise SourceError(
            "anchors: %s is not on disk, so the claim that the MBR anchors "
            "reproduce from it cannot be measured. It is a committed cache, "
            "SPEC.md section 5.4" % path
        )

    values: dict[str, float] = {}
    with open(path, "r", encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split(",")
        if "date" not in header or MBR_COLUMN not in header:
            raise SourceError(
                "anchors: %s has columns %s, which do not include 'date' and %r"
                % (path, ", ".join(header), MBR_COLUMN)
            )
        date_at = header.index("date")
        value_at = header.index(MBR_COLUMN)
        for line in handle:
            cells = line.rstrip("\n").split(",")
            if len(cells) <= max(date_at, value_at):
                continue
            cell = cells[value_at].strip()
            if not cell:
                continue
            try:
                values[cells[date_at].strip()] = float(cell)
            except ValueError:
                raise SourceError(
                    "anchors: %s carries %r in %r on %s, which is not a number"
                    % (path, cell, MBR_COLUMN, cells[date_at])
                ) from None

    reproduced = 0
    failures: list[str] = []
    for month, item in sorted(mbr.items()):
        key = "%s-01" % month
        printed = item.get("printed_value")
        if key not in values:
            failures.append(
                "%s is not in %s at all, so its printed %s $/bbl reproduces from "
                "nothing" % (month, relative, printed)
            )
            continue
        measured = values[key]
        if round(measured, 2) == printed:
            reproduced += 1
        else:
            failures.append(
                "%s: the note printed %s $/bbl, %s holds %r, which rounds to %.2f"
                % (month, printed, relative, measured, round(measured, 2))
            )
    return {
        "reproduced": reproduced,
        "checked": len(mbr),
        "failures": failures,
        "cache": relative,
    }


def _seed_entry(series: str, filename: str, **extra) -> dict:
    """The fields every seed entry shares.

    machine_fetched is False and there is therefore no fetched_at, which is the
    rule crack.sources.base.manifest_upsert enforces: a file nothing fetched has
    no fetch time. checked_at is what the provenance panel prints instead.
    """
    registered = registered_source(series)
    entry = {
        "series": series,
        "source": registered.publisher,
        "url": None,
        "page_url": registered.page_url,
        "machine_fetched": False,
        "fetched_at": None,
        "checked_at": utc_now_iso(),
        "frequency": registered.frequency,
        "gaps": [],
        "provisional_from": None,
        "method": "seed",
        "committable": registered.committable,
        "licence_note": registered.licence_note,
        "status": "ok",
        "file": "data/seed/%s" % filename,
        "unit": registered.unit,
        "observation_column": None,
    }
    entry.update(extra)
    return entry


def record_events(root: Path | str | None = None) -> dict:
    """Put data/seed/events.json into data/manifest.json. Returns the entry."""
    payload = load_events(root)
    events = payload["_events"]
    cited = sum(1 for e in events if e.get("source_url"))
    refusing = [
        e["id"] for e in events if str(e.get("url_status", "")).startswith(("403", "curl"))
    ]
    breaks = [e["id"] for e in events if e["kind"] in ("specification_break", "definition_change", "method_change")]

    entry = _seed_entry(
        EVENTS_SERIES,
        EVENTS_FILENAME,
        rows=len(events),
        observations=len(events),
        file_rows=len(events),
        # The manifest keeps one date shape, yyyy-mm-dd, so every entry sorts and
        # renders the same way. An event whose own precision is a month is padded
        # to the first of that month HERE AND ONLY HERE, because these two fields
        # are the bounds of a coverage range rather than the date of an event.
        # The event's real precision stays in the file, in date_precision, and
        # nothing reads these two fields to place a marker.
        first_date=_as_day(events[0]["date"]),
        last_date=_as_day(events[-1]["date"]),
        date_padding_note=(
            "first_date and last_date are range bounds. An event that names only a "
            "month is padded to the first of that month for them. The event's own "
            "date and date_precision in data/seed/events.json are what a chart marker "
            "must read."
        ),
        vintage=payload.get("checked_at"),
        events=len(events),
        events_with_source_url=cited,
        structural_breaks=len(breaks),
        urls_that_refuse_automated_access=refusing,
        note=(
            "%d dated entries, every one with a source_url, SPEC.md section 6.5. "
            "%d of them are structural breaks the committed caches already carry: "
            "the OPEC Rotterdam specification changes, the two World Bank Europe "
            "gas definition changes, and the DGEC margin method. %d URLs refuse "
            "automated access and are named in "
            "urls_that_refuse_automated_access; each of those entries records what "
            "came back and where its figures were transcribed from. Dates carry a "
            "declared precision and no day is claimed that a source does not name."
            % (len(events), len(breaks), len(refusing))
        ),
    )
    manifest_upsert(entry)
    return entry


def record_anchors(root: Path | str | None = None) -> list[dict]:
    """Put data/seed/anchors.json into the manifest, as its two entries.

    Returns both entries, the DGEC anchors first.
    """
    payload = load_anchors(root)
    anchors = payload["anchors"]
    mbr = anchors["mbr_monthly_usd_bbl"]
    products = anchors["july_2026_products_usd_t"]
    cross = anchors["brent_cross_check"]
    brent = anchors["brent_july_2026_usd_t"]
    references = payload["sp_global_reference"]["references"]

    # MEASURED HERE, ON EVERY RUN, AGAINST THE FILE THE CLAIM IS ABOUT. Not read
    # out of the seed file's own "reproduces" flags, which is what let a
    # corrupted cache sit under a manifest saying the anchors reproduced. See
    # measure_mbr_reproduction.
    measured = measure_mbr_reproduction(payload["_mbr"])
    reproduced = measured["reproduced"]
    failures = measured["failures"]
    unverified = sum(1 for item in products["values"] if item.get("status") != "verified")

    # The seed file's own flags are still checked, against the measurement rather
    # than instead of it. A file claiming a reproduction the cache does not
    # support is exactly as wrong as a manifest doing it.
    claimed = sum(1 for item in mbr["values"] if item.get("reproduces"))
    if claimed != reproduced:
        failures.append(
            "data/seed/anchors.json flags %d of %d anchors as reproducing and the "
            "committed cache supports %d" % (claimed, len(mbr["values"]), reproduced)
        )

    good = not failures
    note = (
        "%d of %d published MBR anchors reproduce from %s to the two decimals "
        "DGEC prints, RE MEASURED BY THIS RUN rather than read out of the seed "
        "file, and Brent date at %d $/t for July 2026 reproduces from the "
        "published $/bbl at DGEC's own %s bbl/t. The SPEC.md section 5.5 Brent "
        "cross check passes on %d of %d months against a 95 percent bar, worst "
        "month %.4f $/bbl, no outliers. %d of the five July 2026 product anchors "
        "are UNVERIFIED and the file says why: the August 2026 notes are deleted "
        "from the ministry site and were never archived. "
        "tests/test_dgec_anchor.py checks those five against "
        "data/cache/dgec_note_printed_monthly.csv and skips only while that file "
        "carries no July 2026 row, which it does not today."
        % (
            reproduced,
            len(mbr["values"]),
            measured["cache"],
            brent.get("printed_value"),
            brent.get("conversion_factor_bbl_per_t"),
            cross.get("months_within_tolerance"),
            cross.get("months_compared"),
            cross.get("max_absolute_usd_bbl") or 0.0,
            unverified,
        )
    )
    if not good:
        note = (
            "AN MBR ANCHOR DOES NOT REPRODUCE FROM THE COMMITTED CACHE, so this "
            "entry claims nothing. %d of %d reproduce from %s. Disagreements: %s. "
            "SPEC.md section 5.5 says to stop and show the page rather than "
            "adjust anything."
            % (
                reproduced,
                len(mbr["values"]),
                measured["cache"],
                "; ".join(failures),
            )
        )

    anchors_entry = _seed_entry(
        ANCHORS_SERIES,
        ANCHORS_FILENAME,
        rows=len(mbr["values"]) + len(products["values"]) + 1,
        observations=len(mbr["values"]) + 1,
        file_rows=len(mbr["values"]) + len(products["values"]) + 1,
        first_date="2022-03-01",
        last_date="2026-08-01",
        vintage=payload.get("checked_at"),
        status="ok" if good else "failed",
        mbr_anchors=len(mbr["values"]),
        mbr_anchors_reproduced=reproduced,
        mbr_anchors_reproduced_against=measured["cache"],
        # No timestamp here on purpose. The manifest is byte idempotent, promise
        # 3 of scripts/refresh.py, and a field that moved on every run would
        # break that. checked_at already says when this run looked.
        mbr_anchors_that_do_not_reproduce=failures,
        product_anchors=len(products["values"]),
        product_anchors_unverified=unverified,
        brent_cross_check_months=cross.get("months_compared"),
        brent_cross_check_within_tolerance=cross.get("months_within_tolerance"),
        brent_cross_check_max_usd_bbl=cross.get("max_absolute_usd_bbl"),
        note=note,
    )

    sp_entry = _seed_entry(
        SP_SERIES,
        ANCHORS_FILENAME,
        rows=len(references),
        observations=len(references),
        file_rows=len(references),
        first_date="2022-03-25",
        last_date="2022-10-17",
        vintage=payload.get("checked_at"),
        references=len(references),
        shares_file_with="anchors",
        note=(
            "%d figures quoted from two dated S&P Global articles, SPEC.md "
            "sections 3, 4.4, 5.1 and 5.5. They live in the sp_global_reference "
            "block of data/seed/anchors.json and have their own manifest entry "
            "because their terms differ from the DGEC anchors in the same file. "
            "BOTH ARTICLE URLS ANSWER HTTP 403 to automated access, with a bot "
            "token user agent and with a browser user agent, so the figures are "
            "transcribed from SPEC.md, which quotes the articles, rather than re "
            "read from source. They are order of magnitude references and never a "
            "benchmark: SPEC.md section 6.6 forbids tuning toward them and nothing "
            "here is fitted to them." % len(references)
        ),
    )

    manifest_upsert(anchors_entry)
    manifest_upsert(sp_entry)
    if not good:
        # The failed entry is written FIRST, then this raises, so the run exits
        # non zero and the manifest on disk says the anchors did not reproduce
        # rather than silently keeping the last good sentence.
        raise SourceError(
            "anchors: %d of %d published MBR anchors reproduce from %s. %s"
            % (reproduced, len(mbr["values"]), measured["cache"], "; ".join(failures))
        )
    return [anchors_entry, sp_entry]


def record_all(root: Path | str | None = None) -> list[dict]:
    """Record both files. Returns every entry written, in manifest order."""
    entries = [record_events(root)]
    entries.extend(record_anchors(root))
    return entries
