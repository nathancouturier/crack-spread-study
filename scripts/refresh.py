#!/usr/bin/env python
"""Refresh every source, or revalidate the committed caches with no network.

    python scripts/refresh.py                 fetch everything, politely
    python scripts/refresh.py --offline       fetch nothing, revalidate what is committed
    python scripts/refresh.py --list          print the jobs and exit
    python scripts/refresh.py --only fred     run one or more jobs by name
    python scripts/refresh.py --offline --strict-private
                                              also revalidate the two private caches

This is the only script that writes data/manifest.json, and the manifest is a
first class artifact, SPEC.md section 5.3. Everything below exists to make it
true rather than merely present.

THE FOUR PROMISES
-----------------
1. NOTHING IS INVENTED. SPEC.md section 2 rule 1. A source that fails leaves the
   cache on disk exactly as it was, gets status "failed" with the error text in
   its note, and makes this script exit non zero. No partial write, no fallback
   to a neighbouring source, no silent interpolation. The Adapter base class
   already guarantees the cache half of that; this script guarantees the exit
   code and the reporting half.

2. OFFLINE MEANS OFFLINE. --offline opens no socket. It reads the committed
   caches, measures them with the same code the online path uses, and rewrites
   the manifest from what it measured rather than from what the last fetch
   claimed. That is the run CI should make, and it is what turns "the manifest
   says 9,973 rows" into "the file on disk has 9,973 rows".

3. OFFLINE IS BYTE IDEMPOTENT. Running it twice on an unchanged tree leaves
   data/manifest.json byte identical, so `git diff --exit-code data/` after it is
   a meaningful CI check rather than a timestamp generator. The mechanism is in
   manifest_is_unchanged below: when nothing but the clock has moved, the
   previous bytes are written back unchanged. The price is that a no change run
   does not bump checked_at, and that price is paid deliberately. The manifest
   describes the data, not the runs.

4. THE MANUAL STEPS ARE IN THE MANIFEST, NOT IN SOMEBODY'S HEAD. This project has
   two pieces of work a machine cannot do, and both of them silently degrade the
   data if they are forgotten. They are written into the manifest on every run,
   at the top level and against the series they affect, so a reader of the
   provenance panel sees them without reading the README. See MANUAL_STEPS.

WHAT OFFLINE DOES WITH THE TWO PRIVATE CACHES
---------------------------------------------
ttf_daily and ei_refinery_capacity_annual may not be redistributed, SPEC.md
section 2 rule 6, so their files live in data/private and are not in the
repository. A clean CI checkout does not have them. If offline revalidated them
it would produce one manifest on the owner's machine and a different one in CI,
and promise 3 would be worthless. So offline CARRIES THOSE TWO ENTRIES THROUGH
VERBATIM from the committed manifest and says so on the console. When the file
does happen to be present it is still checked, and its MEASUREMENTS still do not
change the manifest: the place to update a private entry is a real run,
`python scripts/refresh.py`. --strict-private overrides this and makes a missing
or invalid private cache a failure, for use on the owner's own machine.

ONE THING A PRESENT PRIVATE CACHE DOES CHANGE. If it is present and fails
validation, the run prints it, exits non zero AND sets that entry's status to
"failed" with the reason in its note, leaving every count and date as the last
real run measured them. It used to exit non zero and leave the entry reading
"ok", so the committed manifest described a file the tool had just declared bad.
Gate 1 self audit, finding d.2.

Modelled on scripts/refresh.py in the sibling repository
lme-comex-arbitrage-model, which had the same job and none of this project's
weekly, monthly, annual and reconstructed frequencies.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd  # noqa: E402

from crack import config  # noqa: E402
from crack.sources import base  # noqa: E402
from crack.sources import events_anchors  # noqa: E402
from crack.sources.base import Adapter, MANIFEST, read_cache, utc_now_iso, validate_frame  # noqa: E402
from crack.sources.dgec import DgecBrentMonthly, DgecMbrMonthly  # noqa: E402
from crack.sources.dgec_note import (  # noqa: E402
    DgecNotePrintedMonthly,
    DgecNotePrintedWeekly,
    DgecNoteReconstructedCracksWeekly,
    DgecNoteReconstructedWeekly,
    load_corpus,
)
from crack.sources.ei import EiRefineryCapacity  # noqa: E402
from crack.sources.eia import EiaBrent, record_refinery_fuel_seed  # noqa: E402
from crack.sources.fred import FredBrent, FredEurUsd  # noqa: E402
from crack.sources.jodi import (  # noqa: E402
    JodiCrudeImports,
    JodiRefineryIntake,
    JodiRefineryOutput,
)
from crack.sources.opec_momr import OpecRotterdamProductsMonthly  # noqa: E402
from crack.sources.worldbank import WorldBankGasEurope  # noqa: E402
from crack.sources.yahoo import TtfFrontMonth  # noqa: E402

# Windows consoles default to cp1252 and several notes in this project quote
# French. Printing must never be the thing that fails a refresh.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover, old interpreters
        pass


# --------------------------------------------------------------------------
# The manual steps
# --------------------------------------------------------------------------
#
# Two of them, both real, both discovered rather than assumed, and both with a
# cost stated in words. They go into the manifest on every run.

MANUAL_STEPS: tuple[dict[str, Any], ...] = (
    {
        "id": "momr_unarchived_2026",
        "series": ["opec_rotterdam_products_monthly"],
        "what": (
            "Six OPEC Monthly Oil Market Report issues, April to September 2026, are not in "
            "the Internet Archive and cannot be fetched by this pipeline."
        ),
        "why": (
            "opec.org answers HTTP 403 to every scripted request from this machine, recon 05 "
            "section 1.1, so the adapter resolves issues through the Wayback Machine instead. "
            "The archive holds every issue from January 2001 to March 2026 and stops there. "
            "Nothing in this repository can close that gap on its own."
        ),
        "cost_if_skipped": (
            "The headline monthly crack series ends at 2026-02 and the whole 2026 episode, "
            "which is the most interesting period in the sample, is missing from it. The "
            "weekly DGEC reconstruction covers 2026 and the official monthly MBR covers it, "
            "so the study is not blind, but its longest crack series is."
        ),
        "how": (
            "Open each issue in a browser from https://www.opec.org/monthly-oil-market-report.html "
            ", save the PDF into data/private/momr/ under the name the index expects, then run "
            "python -m crack.sources.opec_momr to reparse. The PDFs are never committed, only "
            "the parsed values are."
        ),
        "cadence": "monthly, or once when the archive catches up",
        "status": "outstanding",
    },
    {
        "id": "dgec_weekly_note_collection",
        "series": [
            "dgec_note_printed_weekly",
            "dgec_note_printed_monthly",
            "dgec_note_reconstructed_weekly",
            "dgec_note_reconstructed_cracks_weekly",
        ],
        "what": (
            "The DGEC weekly note has to be downloaded in the week it is published. It is the "
            "only source of the weekly Rotterdam quotations."
        ),
        "why": (
            "The ministry publishes one note at a time and DELETES the previous one when the "
            "next appears, recon 02 section 2.3. There is no archive on the ministry site and "
            "the Internet Archive caught only ten of them. A note that is missed is gone: the "
            "week it prints cannot be recovered from anywhere, at any price, ever."
        ),
        "cost_if_skipped": (
            "A permanent hole in the weekly layer. Every week missed also removes two "
            "calibration anchors from the chart reconstruction, because the reconstruction is "
            "fitted on the printed figures of the same note."
        ),
        "how": (
            "make note, or python scripts/note.py, two requests, which saves the note "
            "that is online now into data/private/dgec_notes and then rebuilds the three "
            "weekly series. Put it on a weekly schedule and check it ran."
        ),
        "cadence": "weekly, every week, without exception",
        "status": "standing",
    },
)


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Job:
    """One unit of work, named so --only can address it.

    adapters builds the Adapter instances the job owns. Offline uses it to
    revalidate, and never calls fetch(). online is what a real run calls; it
    returns the manifest entries it wrote and raises nothing, recording its own
    failures, because one dead source must not stop the other fourteen.
    """

    name: str
    what: str
    series: tuple[str, ...]
    adapters: Callable[[], list[Adapter]] | None = None
    online: Callable[["argparse.Namespace"], list[dict]] | None = None
    seed: Callable[[], list[dict]] | None = None
    network: bool = True


def _run_adapters(adapters: Sequence[Adapter], failures: list[dict]) -> list[dict]:
    entries: list[dict] = []
    for adapter in adapters:
        try:
            entries.append(adapter.run())
        except Exception as exc:  # noqa: BLE001, one dead source is not fifteen
            failures.append(
                {
                    "series": adapter.name,
                    "error": "%s: %s" % (type(exc).__name__, exc),
                    "traceback": traceback.format_exc(),
                }
            )
    return entries


def _simple(factory: Callable[[], list[Adapter]]) -> Callable[[Any], list[dict]]:
    def run(args) -> list[dict]:
        failures: list[dict] = []
        entries = _run_adapters(factory(), failures)
        args.failures.extend(failures)
        return entries

    return run


def _notes_online(args) -> list[dict]:
    """The three note series share one decode of one corpus.

    load_corpus is strict: if any note trips a gate it raises rather than
    dropping that note and shipping a shorter series. A shorter series would hide
    a layout change, which is the thing this decode is most likely to meet.
    """
    adapters = [
        DgecNotePrintedWeekly(),
        DgecNotePrintedMonthly(),
        DgecNoteReconstructedWeekly(),
        DgecNoteReconstructedCracksWeekly(),
    ]
    try:
        notes = load_corpus(None, strict=True)
    except Exception as exc:  # noqa: BLE001
        args.failures.append(
            {
                "series": "dgec_note_*",
                "error": "corpus decode failed, no note series was touched: %s: %s"
                % (type(exc).__name__, exc),
                "traceback": traceback.format_exc(),
            }
        )
        return []
    for adapter in adapters:
        adapter.notes = notes
    failures: list[dict] = []
    entries = _run_adapters(adapters, failures)
    args.failures.extend(failures)
    return entries


JOBS: tuple[Job, ...] = (
    Job(
        name="fred",
        what="FRED Brent and EUR/USD, daily",
        series=("fred_brent_daily", "fred_eurusd_daily"),
        adapters=lambda: [FredBrent(), FredEurUsd()],
        online=_simple(lambda: [FredBrent(), FredEurUsd()]),
    ),
    Job(
        name="eia",
        what="EIA Europe Brent spot, daily, the licence clean copy of the FRED series",
        series=("eia_brent_daily",),
        adapters=lambda: [EiaBrent()],
        online=_simple(lambda: [EiaBrent()]),
    ),
    Job(
        name="worldbank",
        what="World Bank pink sheet European gas, monthly, $/MMBtu",
        series=("worldbank_gas_europe_monthly",),
        adapters=lambda: [WorldBankGasEurope()],
        online=_simple(lambda: [WorldBankGasEurope()]),
    ),
    Job(
        name="yahoo",
        what="Yahoo TTF front month, daily, EUR/MWh, NOT committable",
        series=("ttf_daily",),
        adapters=lambda: [TtfFrontMonth()],
        online=_simple(lambda: [TtfFrontMonth()]),
    ),
    Job(
        name="dgec",
        what="DGEC monthly Brent and the official gross refining margin",
        series=("dgec_brent_monthly", "dgec_mbr_monthly"),
        adapters=lambda: [DgecBrentMonthly(), DgecMbrMonthly()],
        online=_simple(lambda: [DgecBrentMonthly(), DgecMbrMonthly()]),
    ),
    Job(
        name="dgec-note",
        what=(
            "The weekly note: the printed weekly table, the printed monthly "
            "table with its provisional flags, the chart reconstruction and its "
            "cracks"
        ),
        series=(
            "dgec_note_printed_weekly",
            "dgec_note_printed_monthly",
            "dgec_note_reconstructed_weekly",
            "dgec_note_reconstructed_cracks_weekly",
        ),
        adapters=lambda: [
            DgecNotePrintedWeekly(),
            DgecNotePrintedMonthly(),
            DgecNoteReconstructedWeekly(),
            DgecNoteReconstructedCracksWeekly(),
        ],
        online=_notes_online,
    ),
    Job(
        name="opec",
        what="OPEC MOMR Rotterdam barge product prices, monthly, $/bbl",
        series=("opec_rotterdam_products_monthly",),
        adapters=lambda: [OpecRotterdamProductsMonthly()],
        online=_simple(lambda: [OpecRotterdamProductsMonthly()]),
    ),
    Job(
        name="jodi",
        what="JODI NWE refinery intake, output by product and crude imports, monthly",
        series=(
            "jodi_nwe_refinery_intake_monthly",
            "jodi_nwe_refinery_output_monthly",
            "jodi_nwe_crude_imports_monthly",
        ),
        adapters=lambda: [JodiRefineryIntake(), JodiRefineryOutput(), JodiCrudeImports()],
        online=_simple(
            lambda: [JodiRefineryIntake(), JodiRefineryOutput(), JodiCrudeImports()]
        ),
    ),
    Job(
        name="ei",
        what="Energy Institute refinery capacity, annual, NOT committable",
        series=("ei_refinery_capacity_annual",),
        adapters=lambda: [EiRefineryCapacity()],
        online=_simple(lambda: [EiRefineryCapacity()]),
    ),
    Job(
        name="seeds",
        what="The three committed seed files: refinery fuel, events, anchors",
        series=("eia_refinery_fuel_2023", "events", "anchors", "sp_global_reference"),
        seed=lambda: [record_refinery_fuel_seed()] + events_anchors.record_all(),
        network=False,
    ),
)

JOBS_BY_NAME: Mapping[str, Job] = {job.name: job for job in JOBS}


def resolve_only(values: Sequence[str]) -> list[Job]:
    """Jobs named on the command line, or every job. Raises on an unknown name."""
    if not values:
        return list(JOBS)
    chosen: list[Job] = []
    for value in values:
        job = JOBS_BY_NAME.get(value)
        if job is None:
            raise SystemExit(
                "no job named %r. Jobs: %s" % (value, ", ".join(sorted(JOBS_BY_NAME)))
            )
        if job not in chosen:
            chosen.append(job)
    return chosen


# --------------------------------------------------------------------------
# The manifest, and its idempotence
# --------------------------------------------------------------------------

#: Fields that move on every run whether or not anything about the data changed.
#: They are excluded from the comparison that decides whether to rewrite the
#: file. See promise 3 in the module docstring.
VOLATILE_TOP = ("generated_at", "run")
VOLATILE_ENTRY = ("checked_at",)


def _without_volatile(payload: Mapping[str, Any]) -> dict:
    stripped = {k: v for k, v in payload.items() if k not in VOLATILE_TOP}
    stripped["series"] = [
        {k: v for k, v in entry.items() if k not in VOLATILE_ENTRY}
        for entry in payload.get("series", [])
    ]
    return stripped


def manifest_is_unchanged(before: bytes | None, payload: Mapping[str, Any]) -> bool:
    """True when the only difference from the committed manifest is the clock."""
    if before is None:
        return False
    try:
        previous = json.loads(before.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return False
    return _without_volatile(previous) == _without_volatile(payload)


def _write_manifest_bytes(raw: bytes) -> None:
    tmp = MANIFEST.with_name(MANIFEST.name + ".tmp.%d" % os.getpid())
    try:
        with open(tmp, "wb") as handle:
            handle.write(raw)
        os.replace(tmp, MANIFEST)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def _serialise(payload: Mapping[str, Any]) -> bytes:
    text = json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=False) + "\n"
    return text.encode("utf-8")


def existing_entries() -> dict[str, dict]:
    """The committed manifest, keyed by series name. Empty when there is none."""
    if not MANIFEST.exists():
        return {}
    try:
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return {e.get("series"): e for e in payload.get("series", []) if e.get("series")}


def finalise_manifest(mode: str, before: bytes | None, started: str) -> tuple[dict, bool]:
    """Attach the manual steps and the run block, then write, or restore.

    Returns the payload and whether the file on disk changed.
    """
    payload = base.manifest_read()

    by_series: dict[str, list[dict]] = {}
    for step in MANUAL_STEPS:
        for name in step["series"]:
            by_series.setdefault(name, []).append(
                {k: v for k, v in step.items() if k != "series"}
            )

    for entry in payload.get("series", []):
        steps = by_series.get(entry.get("series"))
        if steps:
            entry["manual_step"] = steps
        else:
            entry.pop("manual_step", None)

    payload["manual_steps"] = [dict(step) for step in MANUAL_STEPS]
    payload["manual_steps_note"] = (
        "Work this pipeline cannot do for itself. Each entry says what it is, why it exists, "
        "what it costs to skip it and how to do it. They are repeated against the series they "
        "affect in the manual_step field of those entries."
    )
    payload["generated_at"] = utc_now_iso()
    payload["run"] = {
        "mode": mode,
        "started_at": started,
        "finished_at": utc_now_iso(),
        "script": "scripts/refresh.py",
    }

    raw = _serialise(payload)
    if manifest_is_unchanged(before, payload):
        # Byte for byte what was committed. Promise 3.
        _write_manifest_bytes(before)
        return payload, False
    _write_manifest_bytes(raw)
    return payload, True


# --------------------------------------------------------------------------
# Offline revalidation
# --------------------------------------------------------------------------

def _base_entry(adapter: Adapter, *, status: str, frame, note: str) -> dict:
    """The base class entry, deliberately NOT the subclass override.

    Several adapters extend _entry with provenance that only a fetch can know:
    which Wayback issues were read, which JODI cells carried assessment code 2,
    which path yfinance took. Offline knows none of that, and calling the
    override would write an empty version of it over the real one. So the base
    fields are recomputed here from the file, and the subclass extras are carried
    forward from the committed entry by carry_forward below.
    """
    return Adapter._entry(adapter, status=status, frame=frame, note=note)


#: Keys the base entry owns. Anything else in a committed entry was put there by
#: an adapter that fetched, and offline carries it through untouched.
_BASE_KEYS = frozenset(base.ENTRY_KEYS) | {"observation_column", "manual_step"}


def carry_forward(entry: dict, previous: Mapping[str, Any] | None) -> dict:
    """Put back everything offline cannot know, from the committed entry."""
    if not previous:
        entry.setdefault("vintage", None)
        return entry
    for key, value in previous.items():
        if key not in _BASE_KEYS:
            entry.setdefault(key, value)
    # A run that fetched nothing must not stamp a fresh fetch time on the
    # provenance panel. checked_at is what this run did.
    if entry.get("machine_fetched"):
        entry["fetched_at"] = previous.get("fetched_at")
    if entry.get("vintage") is None:
        entry["vintage"] = previous.get("vintage")
    if entry.get("provisional_from") is None:
        entry["provisional_from"] = previous.get("provisional_from")
    return entry


def revalidate(adapter: Adapter, previous: Mapping[str, Any] | None) -> dict:
    """Measure one committed cache and return its manifest entry. Fetches nothing.

    The measurement is the same code the online path uses, so the two cannot
    drift: the same validate_frame with the same declared bounds and floors, and
    the same Adapter._entry with the same gap rule at the same frequency.
    """
    # read_cache resolves the directory through crack.sources.base, which is the
    # one place the data paths live, so this follows a test that redirects them
    # instead of reaching past it to REPO_ROOT.
    frame = read_cache(
        adapter.name, date_col=adapter.date_col, directory=adapter.directory()
    )
    if frame is None:
        entry = _base_entry(
            adapter,
            status="failed",
            frame=None,
            note="%s is not on disk. Nothing was written and nothing was removed."
            % adapter.cache_file(),
        )
        return carry_forward(entry, previous)

    problems = validate_frame(
        frame,
        date_col=adapter.date_col,
        required_cols=adapter.required_cols,
        bounds=adapter.bounds,
        min_rows=adapter.min_rows,
        min_observations=adapter.min_observations,
        previous=None,
    )
    if problems:
        entry = _base_entry(
            adapter,
            status="failed",
            frame=frame,
            note="the committed cache does not validate: %s. The file was NOT "
            "changed." % "; ".join(problems),
        )
        return carry_forward(entry, previous)

    # Nothing was learned that the last real run did not already know, so the
    # note it wrote is still the true one. Replacing it with "revalidated" would
    # throw away the only sentence explaining the series.
    note = (previous or {}).get("note") or ""
    if not note or (previous or {}).get("status") != "ok":
        note = (
            "revalidated offline from the committed cache on %s. No fetch, no "
            "network." % utc_now_iso()[:10]
        )
    else:
        # ONE EXCEPTION, AND IT IS NARROW. An adapter may declare offline_note to
        # restate the part of its note that depends only on the committed cache
        # and the calendar, never on the fetch. Without it a correction to that
        # wording would sit in the source and never reach the manifest until
        # somebody happened to run an online fetch, and the manifest is what the
        # provenance panel prints. The only adapters with one today are the two
        # DGEC workbooks, whose provisional sentence is derivable offline.
        restate = getattr(adapter, "offline_note", None)
        if callable(restate):
            note = restate(note, frame)
    entry = _base_entry(adapter, status="ok", frame=frame, note=note)
    return carry_forward(entry, previous)


def _private_check(adapter: Adapter) -> tuple[bool, str]:
    """A one line report on a private cache. Returns (valid, report).

    valid is False ONLY when the file is present and fails validation. A file
    that is simply absent is the normal CI case, not a fault: the two private
    caches are not in the repository, SPEC.md section 2 rule 6, and their entries
    are carried through from the committed manifest so that offline produces the
    same manifest here and in CI.
    """
    frame = read_cache(
        adapter.name, date_col=adapter.date_col, directory=adapter.directory()
    )
    if frame is None:
        return (
            True,
            "not on this machine, entry carried through from the committed manifest",
        )
    problems = validate_frame(
        frame,
        date_col=adapter.date_col,
        required_cols=adapter.required_cols,
        bounds=adapter.bounds,
        min_rows=adapter.min_rows,
        min_observations=adapter.min_observations,
        previous=None,
    )
    if problems:
        return (
            False,
            "PRESENT AND INVALID: %s. Run a real refresh." % "; ".join(problems),
        )
    return (
        True,
        "present and valid, %d rows, entry carried through unchanged" % len(frame),
    )


def mark_private_failed(
    adapter: Adapter, previous: Mapping[str, Any] | None, report: str
) -> None:
    """Write status failed for a private cache this run has just called invalid.

    Gate 1 self audit, finding d.2. The default offline mode does not revalidate
    a private entry into the manifest, for the reason in the module docstring,
    and it used to leave the entry reading "ok" while the same run printed that
    the file was invalid and exited non zero. A manifest that describes a file
    the tool knows is bad is worse than no manifest. The measurements are left
    exactly as the last real run wrote them, because this run measured nothing it
    trusts; only the status and the note change, and the note says what failed.
    """
    if not previous:
        return
    entry = dict(previous)
    entry["status"] = "failed"
    entry["note"] = (
        "OFFLINE REVALIDATION FOUND THIS CACHE INVALID ON %s: %s The file was NOT "
        "changed and the counts and dates below are still the last real run's. "
        "Fix the file and run python scripts/refresh.py."
        % (utc_now_iso()[:10], report)
    )
    base.manifest_upsert(entry)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return "%.4f" % value
    return str(value)


def print_summary(payload: Mapping[str, Any], touched: Sequence[str]) -> list[str]:
    """One row per series. Returns the lines, so a caller can also log them."""
    rows = [
        (
            entry.get("series", ""),
            entry.get("status", ""),
            entry.get("method", ""),
            entry.get("frequency", ""),
            _cell(entry.get("rows")),
            _cell(entry.get("first_date")),
            _cell(entry.get("last_date")),
            _cell(len(entry.get("gaps") or [])),
            "yes" if entry.get("committable") else "NO",
            "yes" if entry.get("series") in touched else "",
        )
        for entry in payload.get("series", [])
    ]
    header = (
        "series", "status", "method", "freq", "rows", "first", "last", "gaps",
        "commit", "run",
    )
    widths = [
        max(len(header[i]), max((len(row[i]) for row in rows), default=0))
        for i in range(len(header))
    ]

    def line(cells: Sequence[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells)).rstrip()

    lines = [line(header), line(["-" * w for w in widths])]
    lines.extend(line(row) for row in rows)
    return lines


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresh the data layer, or revalidate it with no network.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="fetch nothing. Revalidate the committed caches and rewrite the manifest",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="JOB",
        help="run one job by name, repeatable. See --list",
    )
    parser.add_argument("--list", action="store_true", help="print the jobs and exit")
    parser.add_argument(
        "--strict-private",
        action="store_true",
        help=(
            "offline only: revalidate the two private caches as well, and fail if one "
            "is missing. For the owner's machine, never for CI"
        ),
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="polite pause between jobs on an online run, seconds, default 1.0",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    args.failures = []

    if args.list:
        print("jobs, in run order")
        for job in JOBS:
            print("  %-11s %s" % (job.name, job.what))
            for name in job.series:
                registered = config.SOURCES.get(name)
                flag = "" if registered is None or registered.committable else "  NOT committable"
                print("      %s%s" % (name, flag))
        return 0

    jobs = resolve_only(args.only)
    mode = "offline" if args.offline else "online"
    started = utc_now_iso()
    before = MANIFEST.read_bytes() if MANIFEST.exists() else None
    previous = existing_entries()

    print("scripts/refresh.py, %s, %d job(s), started %s" % (mode, len(jobs), started))
    print("repository %s" % REPO_ROOT)
    print("")

    touched: list[str] = []
    private_notes: list[str] = []

    for index, job in enumerate(jobs):
        print("[%d/%d] %s, %s" % (index + 1, len(jobs), job.name, job.what))

        if job.seed is not None:
            try:
                for entry in job.seed():
                    touched.append(entry["series"])
                    print("        %-40s ok" % entry["series"])
            except Exception as exc:  # noqa: BLE001
                args.failures.append(
                    {
                        "series": job.name,
                        "error": "%s: %s" % (type(exc).__name__, exc),
                        "traceback": traceback.format_exc(),
                    }
                )
                print("        FAILED %s" % exc)
            continue

        if args.offline:
            for adapter in job.adapters():
                if not adapter.committable and not args.strict_private:
                    valid, note = _private_check(adapter)
                    private_notes.append("%s: %s" % (adapter.name, note))
                    print("        %-40s private, %s" % (adapter.name, note))
                    if not valid:
                        # The entry does not stay "ok" while this run says the
                        # file is bad. Gate 1 self audit, finding d.2.
                        mark_private_failed(adapter, previous.get(adapter.name), note)
                        args.failures.append(
                            {"series": adapter.name, "error": note, "traceback": ""}
                        )
                    continue
                entry = revalidate(adapter, previous.get(adapter.name))
                base.manifest_upsert(entry)
                touched.append(adapter.name)
                if entry["status"] != "ok":
                    args.failures.append(
                        {"series": adapter.name, "error": entry["note"], "traceback": ""}
                    )
                print(
                    "        %-40s %s, %s rows"
                    % (adapter.name, entry["status"], entry["rows"])
                )
            continue

        if job.online is None:  # pragma: no cover, every job has one of the two
            raise SystemExit("job %r has neither an online runner nor a seed" % job.name)
        entries = job.online(args)
        for entry in entries:
            touched.append(entry["series"])
            print(
                "        %-40s %s, %s rows"
                % (entry["series"], entry["status"], entry["rows"])
            )
        if job.network and index + 1 < len(jobs) and args.delay > 0:
            time.sleep(args.delay)

    payload, changed = finalise_manifest(mode, before, started)

    print("")
    for line in print_summary(payload, touched):
        print(line)

    print("")
    print("manual steps recorded in the manifest, %d:" % len(MANUAL_STEPS))
    for step in MANUAL_STEPS:
        print("  %-30s %s" % (step["id"], step["cadence"]))
        print("      %s" % step["what"])

    if private_notes:
        print("")
        print("private caches, not revalidated into the manifest offline:")
        for note in private_notes:
            print("  %s" % note)

    print("")
    print(
        "data/manifest.json %s"
        % ("REWRITTEN" if changed else "unchanged, byte identical to what was committed")
    )

    if args.failures:
        print("")
        print("FAILED, %d series:" % len(args.failures))
        for failure in args.failures:
            print("  %s: %s" % (failure["series"], failure["error"]))
        print("")
        print(
            "Every cache on disk was left exactly as it was. SPEC.md section 5.4: on "
            "failure keep the old cache, mark failed, exit non zero."
        )
        return 1

    ok = sum(1 for e in payload.get("series", []) if e.get("status") == "ok")
    print("%d of %d series ok" % (ok, len(payload.get("series", []))))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
