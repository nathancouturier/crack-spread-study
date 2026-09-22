"""Tests for crack.sources.base, the contract every adapter inherits.

No network is used anywhere in this file. Anything that would fetch is either
monkeypatched or replaced by a fake adapter.

The suite is arranged the way base.py is: paths, http, gaps, validation, cache,
manifest, Adapter. The Adapter section is the one that matters most, because it
is where SPEC.md section 5.4's promise lives: on failure keep the old cache, mark
the series failed, exit non zero.
"""

from __future__ import annotations

import json
import re

import pandas as pd
import pytest

from crack import config, manual_steps
from crack.sources import base
from crack.sources.base import (
    Adapter,
    SourceError,
    find_gaps,
    manifest_read,
    manifest_upsert,
    missing_business_days,
    read_cache,
    user_agent_for,
    utc_now_iso,
    validate_frame,
    write_cache,
)


def frame(dates, values, col="close"):
    return pd.DataFrame({"date": pd.to_datetime(list(dates)), col: list(values)})


# --------------------------------------------------------------------------
# paths
# --------------------------------------------------------------------------

def test_repo_root_points_at_the_repository():
    assert (base.REPO_ROOT / "pyproject.toml").exists()
    assert (base.REPO_ROOT / "SPEC.md").exists()
    assert base.CACHE == base.REPO_ROOT / "data" / "cache"
    assert base.SEED == base.REPO_ROOT / "data" / "seed"
    assert base.PRIVATE == base.REPO_ROOT / "data" / "private"
    assert base.MANIFEST == base.REPO_ROOT / "data" / "manifest.json"


def test_utc_now_iso_shape():
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", utc_now_iso())


# --------------------------------------------------------------------------
# validate_frame
# --------------------------------------------------------------------------

def test_valid_frame_has_no_problems():
    good = frame(["2026-08-24", "2026-08-25", "2026-08-27"], [700.0, 710.0, 720.0])
    assert (
        validate_frame(
            good,
            required_cols=("date", "close"),
            bounds={"close": config.BOUNDS_PRODUCT_USD_T},
            min_rows=3,
            min_observations={"close": 3},
            previous=3,
        )
        == []
    )


def test_duplicate_dates_are_caught():
    bad = frame(["2026-08-24", "2026-08-25", "2026-08-25"], [1.0, 2.0, 3.0])
    problems = validate_frame(bad, bounds={"close": (0.0, 10.0)})
    assert any("duplicate date" in p for p in problems)
    assert any("2026-08-25" in p for p in problems)


def test_non_monotonic_dates_are_caught():
    bad = frame(["2026-08-25", "2026-08-24", "2026-08-26"], [1.0, 2.0, 3.0])
    problems = validate_frame(bad)
    assert any("not increasing" in p for p in problems)
    assert any("2026-08-24 follows 2026-08-25" in p for p in problems)


def test_out_of_bounds_value_is_caught_and_nan_is_not():
    """NaN is exempt from bounds on purpose. SPEC.md section 2 rule 1 says a
    missing observation is written as NaN, so treating one as a bounds failure
    would punish the honest behaviour."""
    bad = frame(["2026-08-24", "2026-08-25"], [700.0, 91000.0])
    problems = validate_frame(bad, bounds={"close": config.BOUNDS_PRODUCT_USD_T})
    assert any("outside" in p and "close" in p for p in problems)

    with_nan = frame(["2026-08-24", "2026-08-25"], [700.0, float("nan")])
    assert validate_frame(with_nan, bounds={"close": config.BOUNDS_PRODUCT_USD_T}) == []


def test_the_spec_bounds_are_the_ones_the_spec_names():
    """SPEC.md section 5.4, read back off the constants rather than retyped."""
    assert base.SPEC_BOUNDS["product_usd_t"] == (100.0, 3000.0)
    # The Brent lower bound is 5.0 and the spec says 10. That is a deliberate
    # deviation, made after the first live fetch on 2026-09-12 returned 25
    # genuine published prices below 10: seventeen days of the 1998 collapse
    # with a low of 9.10, seven days in February 1999, and 2020-04-21 at 9.12.
    # The same 25 dates carry the same values in the EIA workbook, so it is not
    # a FRED artefact. See the comment on crack.config.BOUNDS_BRENT_USD_BBL and
    # docs/open-questions.md item 3. The upper bound is the spec's.
    assert base.SPEC_BOUNDS["brent_usd_bbl"] == (5.0, 250.0)
    assert base.SPEC_BOUNDS["crack_usd_bbl"] == (-30.0, 150.0)
    assert base.SPEC_BOUNDS["intake_kb_d"][0] == 0.0

    # A Brent print of 628, which is the July 2026 figure in dollars per TONNE,
    # is out of bounds in dollars per barrel. That is the unit error this band
    # exists to catch.
    problems = validate_frame(
        frame(["2026-07-01"], [628.0]),
        bounds={"close": config.BOUNDS_BRENT_USD_BBL},
    )
    assert any("outside" in p for p in problems)


def test_shrinking_row_count_is_caught():
    previous = frame(["2026-08-24", "2026-08-25", "2026-08-26"], [1.0, 2.0, 3.0])
    shrunk = frame(["2026-08-24", "2026-08-25"], [1.0, 2.0])
    problems = validate_frame(shrunk, previous=previous)
    assert any("shrank from 3 to 2" in p for p in problems)
    # The same check accepts a plain row count, which is what the manifest holds.
    assert any("shrank" in p for p in validate_frame(shrunk, previous=3))
    # Growing is fine.
    assert validate_frame(previous, previous=shrunk) == []


def test_missing_columns_and_min_rows_are_caught():
    bad = pd.DataFrame({"day": ["2026-08-24"], "close": [1.0]})
    problems = validate_frame(bad, required_cols=("date", "close"), min_rows=5)
    assert any("missing required column 'date'" in p for p in problems)
    assert any("missing date column 'date'" in p for p in problems)
    assert any("below the minimum" in p for p in problems)


def test_unparseable_date_is_caught():
    bad = pd.DataFrame({"date": ["2026-08-24", "not a date"], "close": [1.0, 2.0]})
    problems = validate_frame(bad)
    assert any("do not parse as a date" in p for p in problems)


def test_validate_frame_rejects_non_frames():
    assert validate_frame(None) == ["expected a DataFrame, got NoneType"]


def test_an_all_nan_column_is_refused_and_an_eroding_one_too():
    """The dash case. SPEC.md section 5.4 and the task brief both name it.

    A source that starts printing a dash where it used to print a price keeps the
    row count and loses the data, so row count alone cannot see it. Two checks
    catch it: a declared floor, and a comparison against what is already on disk.
    """
    good = pd.DataFrame(
        {
            "date": pd.bdate_range("2026-01-01", periods=40),
            "close": [700.0 + i for i in range(40)],
        }
    )
    blanked = good.copy()
    blanked["close"] = float("nan")
    problems = validate_frame(blanked, min_observations={"close": 20})
    assert any("0 observation(s)" in p for p in problems)

    eroded = good.copy()
    eroded.loc[eroded.index[:10], "close"] = float("nan")
    # 30 observations is still above the floor of 20, so only the comparison with
    # the previous cache catches this one.
    problems = validate_frame(
        eroded, min_observations={"close": 20}, previous=good
    )
    assert any("shrank from 40 to 30" in p for p in problems)


def test_a_genuinely_sparse_column_may_declare_a_floor_of_one():
    """The floor is per adapter and declared, not one global number.

    data/seed/eia_refinery_fuel_2023 is four cited numbers. A global floor would
    reject an honest series.
    """
    sparse = pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-01-01", "2024-01-01", "2025-01-01"]),
            "gas_mmcf": [1021246.0, float("nan"), float("nan")],
        }
    )
    assert validate_frame(sparse, min_observations={"gas_mmcf": 1}) == []


def test_a_blank_text_cell_is_not_an_observation():
    assert base.observation_count(pd.Series(["a", "", "  ", None, "b"])) == 2
    assert base.observation_count(pd.Series([1.0, float("nan"), 3.0])) == 2
    assert base.observation_count(None) == 0


# --------------------------------------------------------------------------
# find_gaps, one case per frequency
# --------------------------------------------------------------------------

def test_daily_gaps_find_the_hole_and_ignore_the_weekend():
    # Monday 24 August 2026 to Monday 31 August 2026, with Wednesday 26 absent.
    dates = ["2026-08-24", "2026-08-25", "2026-08-27", "2026-08-28", "2026-08-31"]
    assert find_gaps(dates, "daily") == ["2026-08-26"]
    assert missing_business_days(dates) == ["2026-08-26"]


def test_daily_gaps_on_a_complete_run_are_empty():
    dates = [
        "2026-08-24",
        "2026-08-25",
        "2026-08-26",
        "2026-08-27",
        "2026-08-28",
        "2026-08-31",
    ]
    assert find_gaps(dates, "daily") == []


def test_weekly_gaps_are_reported_as_the_monday_of_the_missing_week():
    # Four Friday notes with the week of Monday 12 January 2026 missing.
    dates = ["2026-01-02", "2026-01-09", "2026-01-23", "2026-01-30"]
    assert find_gaps(dates, "weekly") == ["2026-01-12"]


def test_a_weekly_note_published_a_day_early_is_not_a_gap():
    """The ministry notes are dated by publication and slip by a day or two.

    The weekly rule asks whether the WEEK carries an observation, never whether
    it landed on the usual weekday, because the alternative reports a Thursday
    note as a missing Friday and a missing Thursday at the same time.
    """
    dates = ["2026-01-02", "2026-01-09", "2026-01-15", "2026-01-23", "2026-01-30"]
    assert find_gaps(dates, "weekly") == []


def test_the_daily_rule_would_be_wrong_for_a_weekly_series():
    """Why the frequency argument exists at all.

    The same five complete weekly observations produce twenty phantom gaps under
    the daily rule and none under the weekly one.
    """
    dates = ["2026-01-02", "2026-01-09", "2026-01-16", "2026-01-23", "2026-01-30"]
    assert find_gaps(dates, "weekly") == []
    assert len(find_gaps(dates, "daily")) == 16


def test_monthly_gaps_are_reported_as_the_first_of_the_missing_month():
    # A month is missing whatever day of the month the observations sit on.
    dates = ["2026-01-15", "2026-02-20", "2026-04-03", "2026-05-11"]
    assert find_gaps(dates, "monthly") == ["2026-03-01"]

    dates = ["2026-01-01", "2026-02-01", "2026-03-01"]
    assert find_gaps(dates, "monthly") == []


def test_annual_gaps_are_reported_as_the_first_of_january():
    dates = ["2020-06-30", "2021-06-30", "2023-06-30"]
    assert find_gaps(dates, "annual") == ["2022-01-01"]


def test_gaps_of_a_short_or_empty_series_are_empty():
    for frequency in config.FREQUENCIES:
        assert find_gaps([], frequency) == []
        assert find_gaps(["2026-01-02"], frequency) == []


def test_an_unknown_frequency_raises_rather_than_guessing():
    with pytest.raises(ValueError) as caught:
        find_gaps(["2026-01-02", "2026-01-09"], "fortnightly")
    assert "fortnightly" in str(caught.value)


# --------------------------------------------------------------------------
# cache round trip
# --------------------------------------------------------------------------

def test_write_then_read_cache_round_trips_including_nan(sandbox):
    original = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-08-24", "2026-08-25", "2026-08-26"]),
            "gazole_usd_t": [1160.5, float("nan"), 1162.25],
            "intake_kb_d": [5100, 5120, 5090],
        }
    )
    write_cache("demo", original)

    path = base.CACHE / "demo.csv"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert text.startswith("date,gazole_usd_t,intake_kb_d\n")
    assert "2026-08-24" in text
    assert "\r\n" not in text

    back = read_cache("demo")
    assert list(back.columns) == ["date", "gazole_usd_t", "intake_kb_d"]
    assert back["date"].tolist() == original["date"].tolist()
    assert back["gazole_usd_t"].isna().tolist() == [False, True, False]
    assert back["gazole_usd_t"].dropna().tolist() == [1160.5, 1162.25]


def test_read_cache_returns_none_when_absent(sandbox):
    assert read_cache("never_fetched") is None


def test_write_cache_avoids_scientific_notation(sandbox):
    tiny = pd.DataFrame({"date": pd.to_datetime(["2026-08-24"]), "rate": [0.0000123456]})
    write_cache("tiny", tiny)
    text = (base.CACHE / "tiny.csv").read_text(encoding="utf-8")
    assert "e-" not in text.lower()
    assert "0.0000123456" in text
    assert read_cache("tiny")["rate"].iloc[0] == pytest.approx(0.0000123456)


def test_write_cache_writes_lf_and_leaves_no_temporary_file(sandbox):
    """pandas.to_csv defaults its lineterminator to os.linesep.

    Opening the handle with a newline of "\\n" only disables translation, it does
    not change what pandas writes into the handle, so on Windows the file comes
    out CRLF while the docstring says LF. The sibling repository shipped five
    CRLF caches before noticing.
    """
    write_cache("lf_probe", frame(["2026-08-24", "2026-08-25"], [700.0, 710.0]))
    raw = (base.CACHE / "lf_probe.csv").read_bytes()
    assert b"\r" not in raw
    assert raw.count(b"\n") == 3  # header plus two rows
    assert raw.endswith(b"\n")
    assert [p.name for p in base.CACHE.iterdir() if ".tmp." in p.name] == []


def test_write_cache_is_byte_stable(sandbox):
    """The same frame twice gives the same bytes, so a refresh that changed
    nothing produces an empty diff."""
    payload = frame(["2026-08-24", "2026-08-25"], [700.125, float("nan")])
    write_cache("stable", payload)
    first = (base.CACHE / "stable.csv").read_bytes()
    write_cache("stable", payload)
    assert (base.CACHE / "stable.csv").read_bytes() == first


# --------------------------------------------------------------------------
# manifest
# --------------------------------------------------------------------------

def entry(series="dgec_mbr_monthly", status="ok", rows=10, note="", **extra):
    record = {
        "series": series,
        "source": "DGEC via ecologie.gouv.fr",
        "url": "https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers",
        "page_url": "https://www.ecologie.gouv.fr/politiques-publiques/prix-produits-petroliers",
        "fetched_at": utc_now_iso(),
        "rows": rows,
        "first_date": "2015-01-01",
        "last_date": "2026-07-01",
        "frequency": "monthly",
        "gaps": [],
        "provisional_from": None,
        "vintage": None,
        "method": "published",
        "committable": True,
        "licence_note": "Licence Ouverte 2.0",
        "status": status,
        "note": note,
        "file": "data/cache/%s.csv" % series,
        "unit": "USD per barrel",
    }
    record.update(extra)
    return record


def test_manifest_read_on_a_missing_file_is_empty(sandbox):
    payload = manifest_read()
    assert payload["schema_version"] == 1
    assert payload["series"] == []


def test_manifest_upsert_round_trips_and_preserves_other_entries(sandbox):
    manifest_upsert(entry(rows=10))
    manifest_upsert(entry(series="fred_brent_daily", rows=9973, frequency="daily"))
    manifest_upsert(entry(rows=139, status="stale", note="second pull"))

    payload = manifest_read()
    names = [e["series"] for e in payload["series"]]
    assert names == ["dgec_mbr_monthly", "fred_brent_daily"], (
        "one entry per series, sorted by name, and the other entry survived"
    )

    dgec = payload["series"][0]
    assert dgec["rows"] == 139
    assert dgec["status"] == "stale"
    assert dgec["note"] == "second pull"

    # The untouched entry is byte for byte what it was.
    brent = payload["series"][1]
    assert brent["rows"] == 9973
    assert brent["frequency"] == "daily"

    on_disk = json.loads((sandbox / "manifest.json").read_text(encoding="utf-8"))
    assert on_disk["series"] == payload["series"]
    assert sorted(dgec) == sorted(base.ENTRY_KEYS)


def test_every_manifest_write_reattaches_the_manual_steps(sandbox):
    """A collector must not leave a tree its own validator rejects.

    scripts/refresh.py used to own the manual steps and attach them at the end of
    a run. Every other writer of the manifest therefore replaced an entry WITHOUT
    the manual_step field, and `make note` is such a writer: between it and the
    next offline refresh, tools/validate-data.mjs failed with "manual step
    dgec_weekly_note_collection names dgec_note_printed_weekly but that entry
    does not carry it". The attachment moved into manifest_upsert, so the field
    survives whichever command wrote the entry.
    """
    affected = manual_steps.steps_by_series()
    name = "dgec_note_reconstructed_weekly"
    assert name in affected, "the weekly collection duty names this series"

    manifest_upsert(entry(series=name, method="reconstructed"))
    payload = manifest_read()
    written = payload["series"][0]
    assert written["series"] == name
    assert written["manual_step"] == affected[name], (
        "the entry carries the steps that affect it, with no second run needed"
    )
    assert [s["id"] for s in payload["manual_steps"]] == [
        s["id"] for s in manual_steps.MANUAL_STEPS
    ]
    assert payload["manual_steps_note"]

    # A series no step names carries none, and a stale one does not linger.
    manifest_upsert(entry(series="fred_brent_daily", frequency="daily"))
    fred = [e for e in manifest_read()["series"] if e["series"] == "fred_brent_daily"][0]
    assert "manual_step" not in fred


def test_attaching_the_manual_steps_twice_changes_nothing(sandbox):
    """scripts/refresh.py's offline byte idempotence rests on this."""
    manifest_upsert(entry(series="dgec_note_printed_weekly"))
    first = (sandbox / "manifest.json").read_bytes()
    once = manual_steps.apply(json.loads(first.decode("utf-8")))
    twice = manual_steps.apply(json.loads(json.dumps(once)))
    assert twice == once


def test_the_manifest_carries_every_field_this_project_added(sandbox):
    """SPEC.md section 5.3 is the floor. Five fields sit on top of it."""
    for key in (
        "series",
        "source",
        "url",
        "fetched_at",
        "rows",
        "first_date",
        "last_date",
        "gaps",
        "provisional_from",
        "vintage",
        "licence_note",
        "status",
        "note",
    ):
        assert key in base.ENTRY_KEYS, "SPEC.md section 5.3 names %r" % key
    for key in ("method", "committable", "frequency", "page_url", "observations"):
        assert key in base.ENTRY_KEYS


def test_manifest_upsert_rejects_a_bad_status(sandbox):
    with pytest.raises(ValueError):
        manifest_upsert(entry(status="fine"))
    with pytest.raises(ValueError):
        manifest_upsert({"status": "ok"})


def test_manifest_upsert_demands_a_declared_method(sandbox):
    """The reconstructed series is the reason this field is not optional."""
    with pytest.raises(ValueError) as caught:
        manifest_upsert(entry(method=None))
    assert "method" in str(caught.value)

    with pytest.raises(ValueError):
        manifest_upsert(entry(method="decoded from a chart, roughly"))

    manifest_upsert(entry(series="dgec_note_reconstructed_weekly", method="reconstructed"))
    assert manifest_read()["series"][0]["method"] == "reconstructed"


def test_manifest_upsert_demands_a_boolean_committable(sandbox):
    with pytest.raises(ValueError) as caught:
        manifest_upsert(entry(committable=None))
    assert "committable" in str(caught.value)
    with pytest.raises(ValueError):
        manifest_upsert(entry(committable="yes"))


def test_a_series_that_may_not_be_published_must_say_why(sandbox):
    with pytest.raises(ValueError) as caught:
        manifest_upsert(entry(series="ttf_daily", committable=False, licence_note=""))
    assert "licence_note" in str(caught.value)

    manifest_upsert(
        entry(
            series="ttf_daily",
            committable=False,
            licence_note="Yahoo grants no redistribution right, so this cache is not committed",
            file="data/private/ttf_daily.csv",
        )
    )
    assert manifest_read()["series"][0]["committable"] is False


def test_a_series_that_was_never_fetched_cannot_claim_a_fetch_time(sandbox):
    with pytest.raises(ValueError) as caught:
        manifest_upsert(
            entry(
                series="events",
                method="seed",
                machine_fetched=False,
                fetched_at="2026-09-01T10:00:00Z",
            )
        )
    assert "has no fetch time" in str(caught.value)
    assert "checked_at" in str(caught.value)

    manifest_upsert(
        entry(
            series="events",
            method="seed",
            machine_fetched=False,
            fetched_at=None,
            checked_at=utc_now_iso(),
        )
    )
    recorded = manifest_read()["series"][0]
    assert recorded["machine_fetched"] is False
    assert recorded["fetched_at"] is None
    assert recorded["checked_at"]


def test_manifest_is_written_lf(sandbox):
    manifest_upsert(entry())
    raw = base.MANIFEST.read_bytes()
    assert b"\r" not in raw


# --------------------------------------------------------------------------
# Adapter
# --------------------------------------------------------------------------

class FakeAdapter(Adapter):
    """A publishable, machine fetched, weekly series. Not in the registry."""

    name = "fake_gazole"
    source = "test fixture"
    url = "https://example.invalid/fixture"
    page_url = "https://example.invalid/"
    unit = "USD per tonne"
    frequency = "weekly"
    method = "parsed"
    required_cols = ("date", "close")
    bounds = {"close": config.BOUNDS_PRODUCT_USD_T}
    min_observations = {"close": 1}
    observation_column = "close"
    note = "synthetic frame built inside the test suite"

    def __init__(self, payload):
        self.payload = payload

    def fetch(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def test_adapter_run_writes_cache_and_an_ok_entry(sandbox):
    good = frame(["2026-01-02", "2026-01-09", "2026-01-23"], [1160.0, 1155.0, 1162.0])
    result = FakeAdapter(good).run()

    assert result["status"] == "ok"
    assert result["rows"] == 3
    assert result["observations"] == 3
    assert result["file_rows"] == 3
    assert result["first_date"] == "2026-01-02"
    assert result["last_date"] == "2026-01-23"
    assert result["frequency"] == "weekly"
    # Gaps are computed at the declared frequency, so the missing week shows and
    # the four missing weekdays either side of each note do not.
    assert result["gaps"] == ["2026-01-12"]
    assert result["method"] == "parsed"
    assert result["committable"] is True
    assert result["file"] == "data/cache/fake_gazole.csv"
    assert result["unit"] == "USD per tonne"
    assert (base.CACHE / "fake_gazole.csv").exists()
    assert manifest_read()["series"][0]["series"] == "fake_gazole"


def test_a_failed_fetch_leaves_the_previous_cache_untouched(sandbox):
    """SPEC.md section 5.4, the whole promise of this layer in one test."""
    good = frame(["2026-01-02", "2026-01-09"], [1160.0, 1155.0])
    FakeAdapter(good).run()
    before = (base.CACHE / "fake_gazole.csv").read_bytes()

    with pytest.raises(SourceError):
        FakeAdapter(SourceError("ecologie.gouv.fr returned HTTP 503")).run()

    assert (base.CACHE / "fake_gazole.csv").read_bytes() == before
    recorded = manifest_read()["series"][0]
    assert recorded["status"] == "failed"
    assert "503" in recorded["note"]
    assert "previous cache kept unchanged" in recorded["note"]
    assert recorded["rows"] == 2, "the manifest describes what is actually on disk"
    assert recorded["last_date"] == "2026-01-09"


def test_adapter_run_refuses_a_frame_that_shrank(sandbox):
    FakeAdapter(frame(["2026-01-02", "2026-01-09"], [1160.0, 1155.0])).run()
    before = (base.CACHE / "fake_gazole.csv").read_bytes()

    with pytest.raises(SourceError) as caught:
        FakeAdapter(frame(["2026-01-02"], [1160.0])).run()

    assert "shrank" in str(caught.value)
    assert (base.CACHE / "fake_gazole.csv").read_bytes() == before
    assert manifest_read()["series"][0]["status"] == "failed"


def test_adapter_run_refuses_an_out_of_bounds_frame(sandbox):
    with pytest.raises(SourceError) as caught:
        FakeAdapter(frame(["2026-01-02", "2026-01-09"], [1160.0, 91000.0])).run()
    assert "outside" in str(caught.value)
    assert not (base.CACHE / "fake_gazole.csv").exists()
    assert manifest_read()["series"][0]["status"] == "failed"


def test_adapter_run_refuses_an_all_nan_frame(sandbox):
    FakeAdapter(frame(["2026-01-02", "2026-01-09"], [1160.0, 1155.0])).run()
    before = (base.CACHE / "fake_gazole.csv").read_bytes()

    blanked = frame(["2026-01-02", "2026-01-09", "2026-01-16"], [float("nan")] * 3)
    with pytest.raises(SourceError) as caught:
        FakeAdapter(blanked).run()
    assert "0 observation(s)" in str(caught.value)
    assert (base.CACHE / "fake_gazole.csv").read_bytes() == before


def test_adapter_without_fetch_raises_not_implemented():
    class Empty(Adapter):
        name = "empty"

    with pytest.raises(NotImplementedError):
        Empty().fetch()


def test_an_adapter_that_bounds_a_column_without_flooring_it_is_refused(sandbox):
    class Unfloored(Adapter):
        name = "unfloored_thing"
        observation_column = "value"
        bounds = {"value": (0.0, 10.0)}

        def fetch(self):  # pragma: no cover, run() raises before this is reached
            raise AssertionError("fetch() must not be reached")

    with pytest.raises(SourceError) as caught:
        Unfloored().run()
    assert "min_observations" in str(caught.value)
    assert "value" in str(caught.value)


def test_an_adapter_must_declare_a_known_frequency(sandbox):
    class Odd(Adapter):
        name = "odd_thing"
        frequency = "fortnightly"

        def fetch(self):  # pragma: no cover
            raise AssertionError("fetch() must not be reached")

    with pytest.raises(SourceError) as caught:
        Odd().run()
    assert "fortnightly" in str(caught.value)


def test_where_the_bytes_land_follows_the_declarations(sandbox):
    """Three directories, three meanings, and the declared path matches the real one.

    data/cache is for what a source actually served. data/seed is for a file
    nothing fetched. data/private is for a file the terms forbid republishing,
    SPEC.md section 2 rule 6, and it is gitignored, so putting the Energy
    Institute capacity table anywhere else would commit it.
    """
    payload = pd.DataFrame(
        {"date": pd.to_datetime(["2026-01-02", "2026-01-09"]), "value": [1.0, 2.0]}
    )

    class Fetched(Adapter):
        name = "fetched_thing"
        frequency = "weekly"
        observation_column = "value"
        min_observations = {"value": 1}
        bounds = {"value": (0.0, 10.0)}

        def fetch(self):
            return payload.copy()

    class Seeded(Adapter):
        name = "seeded_thing"
        frequency = "weekly"
        machine_fetched = False
        method = "seed"
        observation_column = "value"
        min_observations = {"value": 1}
        bounds = {"value": (0.0, 10.0)}

        def fetch(self):
            return payload.copy()

    class Restricted(Adapter):
        name = "restricted_thing"
        frequency = "weekly"
        committable = False
        licence_note = "the publisher does not permit reproduction of this table"
        observation_column = "value"
        min_observations = {"value": 1}
        bounds = {"value": (0.0, 10.0)}

        def fetch(self):
            return payload.copy()

    assert Fetched().run()["file"] == "data/cache/fetched_thing.csv"
    assert Seeded().run()["file"] == "data/seed/seeded_thing.csv"
    assert Restricted().run()["file"] == "data/private/restricted_thing.csv"

    assert (sandbox / "cache" / "fetched_thing.csv").exists()
    assert (sandbox / "seed" / "seeded_thing.csv").exists()
    assert (sandbox / "private" / "restricted_thing.csv").exists()
    assert not (sandbox / "cache" / "restricted_thing.csv").exists()
    assert not (sandbox / "cache" / "seeded_thing.csv").exists()

    # And a seeded file carries no fetch time, which manifest_upsert enforces,
    # but it does carry the moment this run last looked at it.
    seeded = [e for e in manifest_read()["series"] if e["series"] == "seeded_thing"][0]
    assert seeded["fetched_at"] is None
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", seeded["checked_at"])

    fetched = [e for e in manifest_read()["series"] if e["series"] == "fetched_thing"][0]
    assert fetched["checked_at"] is None
    assert fetched["fetched_at"]


def test_a_restricted_adapter_without_a_licence_note_is_refused(sandbox):
    class Silent(Adapter):
        name = "silent_thing"
        committable = False

        def fetch(self):  # pragma: no cover
            raise AssertionError("fetch() must not be reached")

    with pytest.raises(SourceError) as caught:
        Silent().run()
    assert "licence_note" in str(caught.value)


def test_an_adapter_may_not_disagree_with_the_source_registry(sandbox):
    """The registry is what the provenance panel prints."""

    class Wrong(Adapter):
        name = "ttf_daily"  # registered as committable False
        frequency = "daily"
        committable = True

        def fetch(self):  # pragma: no cover
            raise AssertionError("fetch() must not be reached")

    with pytest.raises(SourceError) as caught:
        Wrong().run()
    assert "SOURCES" in str(caught.value)
    assert "committable" in str(caught.value)


# --------------------------------------------------------------------------
# http, no network
# --------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code
        self.headers = {}
        self.text = "body"


def test_http_get_retries_a_503_then_succeeds(monkeypatch):
    seen = []

    def fake_get(url, headers=None, timeout=None):
        seen.append(url)
        return FakeResponse(503 if len(seen) < 3 else 200)

    monkeypatch.setattr(base.requests, "get", fake_get)
    monkeypatch.setattr(base.time, "sleep", lambda _s: None)

    response = base.http_get("https://example.invalid/x", delay=0)
    assert response.status_code == 200
    assert len(seen) == 3


def test_http_get_gives_up_and_names_the_url_and_status(monkeypatch):
    monkeypatch.setattr(base.requests, "get", lambda *a, **k: FakeResponse(500))
    monkeypatch.setattr(base.time, "sleep", lambda _s: None)

    with pytest.raises(SourceError) as caught:
        base.http_get("https://example.invalid/down", retries=2, delay=0)
    message = str(caught.value)
    assert "https://example.invalid/down" in message
    assert "500" in message
    assert "3 attempts" in message


def test_http_get_does_not_retry_a_403(monkeypatch):
    """opec.org answers 403 to every scripted request from this machine.

    Asking again would not change the answer and would only waste the host's
    time, so a 403 fails at once and names itself.
    """
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append(url)
        return FakeResponse(403)

    monkeypatch.setattr(base.requests, "get", fake_get)
    monkeypatch.setattr(base.time, "sleep", lambda _s: None)

    with pytest.raises(SourceError) as caught:
        base.http_get("https://www.opec.org/blocked", delay=0)
    assert len(calls) == 1
    assert "not retryable" in str(caught.value)


def test_fred_gets_the_project_token_and_everything_else_gets_the_browser_string():
    """Recon 04 section 1.2. The browser string RESETS THE CONNECTION at FRED.

    Measured five ways in the same minute on the same URL: a named project token
    and python-requests both returned HTTP 200 in under a second, Mozilla/5.0 got
    a connection reset and a full Chrome string timed out with zero bytes. The
    sibling repository measured the same thing independently on 2026-08-31. This
    is the one place in the project that knows it.
    """
    fred = user_agent_for("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU")
    assert fred == base.PROJECT_USER_AGENT
    assert "Mozilla" not in fred
    assert "crack-spread-study" in fred

    assert user_agent_for("https://www.ecologie.gouv.fr/x.pdf") == base.USER_AGENT
    assert "Mozilla/5.0" in user_agent_for("https://www.energyinst.org/x.xlsx")


def test_http_get_applies_the_per_host_user_agent(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured.update(headers or {})
        return FakeResponse(200)

    monkeypatch.setattr(base.requests, "get", fake_get)
    monkeypatch.setattr(base.time, "sleep", lambda _s: None)

    base.http_get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXUSEU", delay=0)
    assert captured["User-Agent"] == base.PROJECT_USER_AGENT

    captured.clear()
    base.http_get("https://example.invalid/ok", headers={"Accept": "text/csv"}, delay=0)
    assert "Mozilla/5.0" in captured["User-Agent"]
    assert captured["Accept"] == "text/csv"


def test_an_explicit_user_agent_from_the_caller_wins(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured.update(headers or {})
        return FakeResponse(200)

    monkeypatch.setattr(base.requests, "get", fake_get)
    monkeypatch.setattr(base.time, "sleep", lambda _s: None)

    base.http_get(
        "https://fred.stlouisfed.org/x", headers={"User-Agent": "probe/1"}, delay=0
    )
    assert captured["User-Agent"] == "probe/1"


def test_head_is_refused_for_eia_because_it_answers_503_to_head():
    """Recon 03. eia.gov answers 503 to HEAD and 200 to GET on the same URL.

    A liveness probe with HEAD reports a live source as dead, which is the most
    expensive kind of false alarm in a pipeline whose job is to say honestly
    whether a source answered.
    """
    with pytest.raises(SourceError) as caught:
        base.http_head("https://www.eia.gov/dnav/pet/pet_pnp_inpt_dc_nus_mbbl_a.htm")
    message = str(caught.value)
    assert "503" in message
    assert "http_get" in message


def test_head_is_allowed_elsewhere(monkeypatch):
    monkeypatch.setattr(
        base.requests, "head", lambda *a, **k: FakeResponse(200)
    )
    monkeypatch.setattr(base.time, "sleep", lambda _s: None)
    assert base.http_head("https://www.energyinst.org/x.xlsx", delay=0).status_code == 200


# --------------------------------------------------------------------------
# config, the parts base.py depends on
# --------------------------------------------------------------------------

def test_the_two_dgec_brent_factors_are_both_present_and_different():
    """Recon 02 section 5.4 found two, used in two places."""
    assert config.DGEC_BBL_PER_T_BRENT_NOTE == 7.5
    assert config.DGEC_BBL_PER_T_BRENT_MARGIN == 7.55
    assert config.DGEC_BBL_PER_T_BRENT_NOTE != config.DGEC_BBL_PER_T_BRENT_MARGIN


def test_the_contract_factors_are_the_contract_factors():
    assert config.BBL_PER_T_GASOIL == 7.45
    assert config.BBL_PER_T_GASOLINE == 8.33
    assert config.MMBTU_PER_MWH == 3.412142


def test_the_gas_intensity_matches_its_own_derivation():
    """SPEC.md section 4.4: derived, not typed. Recomputed from the cited inputs.

    If somebody edits the constant without editing the EIA figures above it, or
    the other way round, this fails.
    """
    total_mmcf = (
        config.EIA_REFINERY_FUEL_GAS_MMCF_2023
        + config.EIA_HYDROGEN_FEEDSTOCK_GAS_MMCF_2023
    )
    mmbtu = total_mmcf * 1e6 * config.EIA_GAS_HEAT_CONTENT_BTU_PER_CF_2023 / 1e6
    barrels = config.EIA_CRUDE_INPUTS_THOUSAND_BBL_2023 * 1e3
    derived = mmbtu / barrels

    assert derived == pytest.approx(0.2121741035, abs=1e-9)
    assert config.GAS_INTENSITY_MMBTU_PER_BBL == pytest.approx(derived, abs=5e-6)
    lo, hi = config.GAS_INTENSITY_BAND
    assert lo < config.GAS_INTENSITY_MMBTU_PER_BBL < hi


def test_the_monthly_mean_rule_excludes_blank_days_rather_than_filling_them():
    """Recon 04 section 7.2 measured that filling moves the answer by 1.10 $/bbl
    out of a 1.5 $/bbl tolerance, so the rule is fixed rather than inherited."""
    dates = pd.bdate_range("2026-01-01", "2026-02-27")
    values = [100.0] * len(dates)
    frame_in = pd.DataFrame({"date": dates, "value": values})
    # Blank the last three business days of January, as a holiday run would be.
    january = frame_in["date"].dt.month == 1
    frame_in.loc[frame_in[january].index[-3:], "value"] = float("nan")

    out = config.monthly_mean(
        frame_in["date"], frame_in["value"], min_observations=1
    )
    assert list(out["month"].dt.strftime("%Y-%m")) == ["2026-01", "2026-02"]
    # The blank days are excluded from the mean, not carried forward into it.
    assert out.loc[0, "observations"] == int(january.sum()) - 3
    assert out.loc[0, "value"] == pytest.approx(100.0)


def test_a_thin_month_is_nan_and_still_reports_its_count():
    dates = ["2026-01-05", "2026-01-06", "2026-02-02", "2026-02-03", "2026-02-04"]
    values = [100.0, 102.0, 90.0, 92.0, 94.0]
    out = config.monthly_mean(dates, values, min_observations=3)
    assert pd.isna(out.loc[0, "value"]), "two days is below the declared minimum"
    assert out.loc[0, "observations"] == 2
    assert out.loc[1, "value"] == pytest.approx(92.0)
    assert out.loc[1, "observations"] == 3


def test_a_month_the_source_covered_but_published_nothing_in_is_visible():
    """A hole must be a NaN row, not a shorter frame. SPEC.md section 2 rule 1."""
    dates = ["2026-01-15", "2026-03-15"]
    values = [100.0, 110.0]
    out = config.monthly_mean(dates, values, min_observations=1)
    assert list(out["month"].dt.strftime("%Y-%m")) == ["2026-01", "2026-02", "2026-03"]
    assert out.loc[1, "observations"] == 0
    assert pd.isna(out.loc[1, "value"])


def test_the_registry_marks_the_two_sources_that_may_not_be_republished():
    assert set(config.uncommittable_series()) == {
        "ei_refinery_capacity_annual",
        "ttf_daily",
    }
    for name in config.uncommittable_series():
        note = config.source(name).licence_note
        assert "not" in note.lower(), "%s must say what is forbidden" % name
    assert "dgec_note_reconstructed_weekly" in config.committable_series()


def test_the_reconstructed_series_declares_itself_as_one():
    assert config.source("dgec_note_reconstructed_weekly").method == "reconstructed"
    assert all(
        config.source(name).method in config.METHODS for name in config.SOURCES
    )


def test_a_source_that_has_to_be_scraped_says_so_instead_of_carrying_a_url():
    """The World Bank rewrites the document id in its path and JODI renames the
    in progress year every January, so those URLs cannot be hardcoded."""
    for name in (
        "worldbank_gas_europe_monthly",
        "jodi_nwe_refinery_intake_monthly",
        "jodi_nwe_refinery_output_monthly",
        "jodi_nwe_crude_imports_monthly",
    ):
        entry = config.source(name)
        assert entry.machine_url is None
        assert len(entry.url_note) > 100
        assert entry.page_url.startswith("https://")


def test_an_unregistered_series_name_raises_with_the_list():
    with pytest.raises(KeyError) as caught:
        config.source("dgec_mbr_montly")
    assert "dgec_mbr_monthly" in str(caught.value)


# --------------------------------------------------------------------------
# The repository rule that is easiest to break by accident
# --------------------------------------------------------------------------

def test_no_dashes_in_the_python_sources():
    """SPEC.md section 0.1, no em dashes and no en dashes anywhere in the repo.

    The two characters are written as chr() calls so that this file, which is
    part of the repository, does not itself contain them.
    """
    banned = (chr(0x2014), chr(0x2013))
    offenders = []
    for folder in ("src", "tests", "scripts", "tools"):
        root = base.REPO_ROOT / folder
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            if any(ch in text for ch in banned):
                offenders.append(str(path.relative_to(base.REPO_ROOT)))
    assert offenders == []
