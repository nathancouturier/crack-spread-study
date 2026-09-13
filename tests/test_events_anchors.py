"""The two cited JSON files, and the orchestrator that records them.

Three things are asserted here and they are different in kind.

WHAT THE FILES CLAIM. events.json and anchors.json are written by hand, so the
loader in crack.sources.events_anchors refuses a file that cannot be checked and
these tests prove that it does, by handing it broken files rather than by
trusting the docstring.

THAT THE FILES AND THE CODE AGREE. tests/test_dgec_anchor.py holds the SPEC.md
section 5.5 numbers as literals, because it was written before anchors.json
existed and because an anchor test that read its expectations from a file the
same pipeline writes would be circular. Both are now true at once: the literals
stay where they are, and the tests below assert that anchors.json says exactly
the same thing. If somebody edits one, this fails. That is the only way to have
the numbers in data without losing the independence of the test.

THAT THE ORCHESTRATOR KEEPS ITS PROMISES. scripts/refresh.py promises that
offline is byte idempotent and that it never writes a fetch time onto a file
nothing fetched. Both are asserted against a real temporary tree.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED = REPO_ROOT / "data" / "seed"

from crack.sources import events_anchors as ea  # noqa: E402
from crack.sources.base import SourceError  # noqa: E402

from test_dgec_anchor import (  # noqa: E402
    BRENT_ANCHOR_JULY_2026_USD_T,
    MBR_ANCHORS,
    PRODUCT_ANCHORS_JULY_2026,
)


def _load_refresh():
    """Import scripts/refresh.py, which is a script rather than a package."""
    path = REPO_ROOT / "scripts" / "refresh.py"
    spec = importlib.util.spec_from_file_location("crack_refresh_under_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


refresh = _load_refresh()


@pytest.fixture(scope="module")
def events():
    return ea.load_events()


@pytest.fixture(scope="module")
def anchors():
    return ea.load_anchors()


# --------------------------------------------------------------------------
# events.json
# --------------------------------------------------------------------------

def test_every_event_carries_a_source_url(events):
    """SPEC.md section 6.5: include only what you can cite."""
    missing = [e["id"] for e in events["_events"] if not e.get("source_url")]
    assert not missing, (
        "these events carry no source_url and must not be in the file: %s" % missing
    )


def test_every_event_records_what_its_url_answered(events):
    """A URL nobody checked is a citation nobody can rely on.

    Two of these URLs refuse automated access, the S&P Global articles, and one
    is a ministry note that has since been deleted. Recording the HTTP result
    next to each URL is what turns "cited" into "cited, and here is the state of
    that citation on the day it was written down".
    """
    missing = [e["id"] for e in events["_events"] if not e.get("url_status")]
    assert not missing, "these events do not say what their URL answered: %s" % missing


def test_no_event_claims_a_day_its_source_does_not_name(events):
    """SPEC.md non negotiable 8. The ICE and lockdown entries are months."""
    for event in events["_events"]:
        if event["date_precision"] == "day":
            assert re.match(r"^\d{4}-\d{2}-\d{2}$", event["date"]), event["id"]
        else:
            assert re.match(r"^\d{4}-\d{2}$", event["date"]), event["id"]


def test_the_two_entries_that_could_not_be_pinned_say_so(events):
    """The ICE 10 ppm transition and the Russian free gasoil change.

    Both sources say "at the start of 2015" and "at the end of 2022" and neither
    prints a day. Both entries therefore carry a month AND a date_note that says
    why, which is the difference between an honest gap and a silent one.
    """
    for name in ("ice_gasoil_10ppm_2015", "ice_gasoil_russian_free_end_2022"):
        event = events["_by_id"][name]
        assert event["date_precision"] == "month"
        assert event.get("date_note"), "%s does not say why it carries no day" % name


def test_the_iea_release_is_pinned_to_a_day(events):
    """SPEC.md section 6.5 writes 2026-03 and says to pin the exact date.

    It is pinned. Two IEA publications state 11 March 2026 outright, and the
    entry quotes one of them and links the other.
    """
    event = events["_by_id"]["iea_collective_action_400_mb_2026_03_11"]
    assert event["date"] == "2026-03-11"
    assert event["date_precision"] == "day"
    assert "11 March" in event["source_quote"]
    assert any("iea.org" in s["url"] for s in event["additional_sources"])


def test_the_spec_65_table_is_all_there(events):
    """Every row of the SPEC.md section 6.5 table has an entry."""
    wanted = {
        "2015-01": "ice_gasoil_10ppm_2015",
        "2020-03": "covid_pandemic_and_european_lockdowns_2020_03",
        "2022-02-24": "russia_invades_ukraine_2022_02_24",
        "2022-03-25": "sp_record_diesel_cracks_week_to_2022_03_25",
        "2022-10-13": "sp_ara_diesel_cracks_2022_10_13",
        "2022-12-05": "eu_embargo_russian_seaborne_crude_2022_12_05",
        "2023-02-05": "eu_embargo_russian_refined_products_2023_02_05",
        "2026-02-28": "strikes_on_iran_hormuz_2026_02_28",
        "2026-04-07": "us_iran_ceasefire_2026_04_07",
    }
    for date, name in wanted.items():
        assert name in events["_by_id"], "SPEC.md section 6.5 row %s is missing" % date
        assert events["_by_id"][name]["date"] == date


def test_the_structural_breaks_the_caches_know_about_are_all_there(events):
    """The breaks measured from the committed data, not read from a report."""
    for name in (
        "opec_gasoil_spec_2005_03",
        "opec_gasoil_spec_2008_06",
        "opec_gasoline_spec_2013_07",
        "worldbank_europe_gas_definition_2015_04",
        "dgec_mbr_method_in_force_2016_01_01",
        "imo_2020_sulphur_cap",
    ):
        assert name in events["_by_id"], "%s is missing from events.json" % name


def test_the_opec_specification_breaks_match_the_committed_cache():
    """MEASURED, NOT TYPED. The event dates come out of the file itself.

    The cache carries the label OPEC printed on each row, per month. The first
    month a new label appears is the break, and this recomputes that from the
    CSV so the seed file cannot drift from the data it describes.
    """
    frame = pd.read_csv(REPO_ROOT / "data" / "cache" / "opec_rotterdam_products_monthly.csv")
    payload = ea.load_events()
    for product in ("gasoil", "gasoline"):
        column = "%s_spec" % product
        seen = frame[["date", column]].dropna()
        first_month = {}
        for _, row in seen.iterrows():
            first_month.setdefault(row[column], row["date"][:7])
        # every label except the first one is a break
        labels = list(first_month)
        for label in labels[1:]:
            month = first_month[label]
            name = "opec_%s_spec_%s" % (product, month.replace("-", "_"))
            assert name in payload["_by_id"], (
                "the cache says the %s row became %r in %s and events.json has no "
                "entry for it" % (product, label, month)
            )
            assert payload["_by_id"][name]["date"] == month


def test_a_bad_events_file_is_refused(tmp_path):
    """Four ways to break it, four refusals. The docstring is not the test."""
    good = json.loads((SEED / "events.json").read_text(encoding="utf-8"))

    def write(payload):
        (tmp_path / "events.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    no_url = json.loads(json.dumps(good))
    no_url["events"][0].pop("source_url")
    write(no_url)
    with pytest.raises(SourceError, match="source_url"):
        ea.load_events(tmp_path)

    invented_day = json.loads(json.dumps(good))
    for event in invented_day["events"]:
        if event["date_precision"] == "month":
            event["date_precision"] = "day"
            break
    write(invented_day)
    with pytest.raises(SourceError, match="invented"):
        ea.load_events(tmp_path)

    duplicated = json.loads(json.dumps(good))
    duplicated["events"].append(dict(duplicated["events"][0]))
    write(duplicated)
    with pytest.raises(SourceError, match="twice"):
        ea.load_events(tmp_path)

    wrong_kind = json.loads(json.dumps(good))
    wrong_kind["events"][0]["kind"] = "vibes"
    write(wrong_kind)
    with pytest.raises(SourceError, match="kind"):
        ea.load_events(tmp_path)


# --------------------------------------------------------------------------
# anchors.json
# --------------------------------------------------------------------------

def test_anchors_agree_with_the_literals_in_test_dgec_anchor(anchors):
    """THE TWO COPIES OF SPEC.md SECTION 5.5 MUST SAY THE SAME THING.

    test_dgec_anchor.py asserts the cache against literals. anchors.json holds
    the same numbers as data so the site can print them. Neither is allowed to
    drift from the other, and this is the assertion that stops it.
    """
    assert len(anchors["_mbr"]) == len(MBR_ANCHORS)
    for month_key, (printed, _printed_in) in MBR_ANCHORS.items():
        month = month_key[:7]
        assert month in anchors["_mbr"], "anchors.json has no MBR anchor for %s" % month
        assert anchors["_mbr"][month]["printed_value"] == printed, (
            "anchors.json says %s for %s, test_dgec_anchor.py says %s"
            % (anchors["_mbr"][month]["printed_value"], month, printed)
        )

    brent = anchors["anchors"]["brent_july_2026_usd_t"]
    assert brent["printed_value"] == BRENT_ANCHOR_JULY_2026_USD_T

    products = {
        item["label_as_printed"]: item["printed_value"]
        for item in anchors["anchors"]["july_2026_products_usd_t"]["values"]
    }
    assert products == PRODUCT_ANCHORS_JULY_2026


def test_every_mbr_anchor_reproduces_from_the_committed_cache(anchors):
    """Recomputed here, not read. SPEC.md section 10 gates Gate 2 on this."""
    frame = pd.read_csv(REPO_ROOT / "data" / "cache" / "dgec_mbr_monthly.csv")
    series = frame.set_index("date")["mbr_usd_bbl"]
    for month, item in anchors["_mbr"].items():
        measured = float(series.loc["%s-01" % month])
        assert round(measured, 2) == item["printed_value"], (
            "%s: the cache holds %r, the note printed %r"
            % (month, measured, item["printed_value"])
        )
        assert item["reproduces"] is True
        assert item["measured_value"] == pytest.approx(measured)


def test_the_five_product_anchors_are_labelled_unverified(anchors):
    """They cannot be checked and the file says so rather than implying they can.

    The August 2026 notes are deleted from the ministry site and were never
    archived, and no series in this repository carries a July 2026 monthly
    average in $/t. SPEC.md non negotiable 8: an honest gap beats a plausible
    fabrication.
    """
    for item in anchors["anchors"]["july_2026_products_usd_t"]["values"]:
        assert item["status"] == "unverified", item["key"]
        assert item["status_note"], item["key"]
        assert item["url_status"].startswith("404"), item["key"]


def test_the_brent_cross_check_in_the_file_matches_a_fresh_computation(anchors):
    """SPEC.md section 5.5, recomputed from the two committed caches."""
    from crack import config

    cross = anchors["anchors"]["brent_cross_check"]
    dgec = pd.read_csv(REPO_ROOT / "data" / "cache" / "dgec_brent_monthly.csv").set_index("date")
    fred = pd.read_csv(REPO_ROOT / "data" / "cache" / "fred_brent_daily.csv")
    means = config.monthly_mean(fred["date"], fred["brent_usd_bbl"])
    means["month"] = means["month"].dt.strftime("%Y-%m-%d")
    joined = dgec.join(means.set_index("month"), how="inner")
    residual = (joined["brent_usd_bbl"] - joined["value"]).abs().dropna()

    assert cross["months_compared"] == len(residual)
    assert cross["months_within_tolerance"] == int(
        (residual <= config.BRENT_CROSS_CHECK_TOLERANCE_USD_BBL).sum()
    )
    assert cross["max_absolute_usd_bbl"] == pytest.approx(float(residual.max()))
    assert cross["pass_share"] >= config.BRENT_CROSS_CHECK_MIN_PASS_SHARE
    assert cross["outliers"] == []


def test_every_sp_reference_carries_its_url_and_its_refusal(anchors):
    """Both S&P URLs answer 403 to a script. The file records that."""
    assert len(anchors["_references"]) == 5
    for key, item in anchors["_references"].items():
        assert item["source_url"].startswith("https://www.spglobal.com/"), key
        assert item["url_status"].startswith("403"), key


def test_the_sp_references_are_not_presented_as_a_series(anchors):
    """SPEC.md section 5.1 and section 6.6. The terms and the discipline."""
    block = anchors["sp_global_reference"]
    assert "not redistributable" in block["licence_note"].lower()
    assert "forbids tuning" in block["not_a_benchmark"]


def test_a_bad_anchors_file_is_refused(tmp_path):
    good = json.loads((SEED / "anchors.json").read_text(encoding="utf-8"))

    def write(payload):
        (tmp_path / "anchors.json").write_text(json.dumps(payload), encoding="utf-8")

    no_url = json.loads(json.dumps(good))
    no_url["anchors"]["mbr_monthly_usd_bbl"]["values"][0].pop("source_url")
    write(no_url)
    with pytest.raises(SourceError, match="source_url"):
        ea.load_anchors(tmp_path)

    claim_only = json.loads(json.dumps(good))
    claim_only["anchors"]["mbr_monthly_usd_bbl"]["values"][0].pop("measured_value")
    write(claim_only)
    with pytest.raises(SourceError, match="not a measurement"):
        ea.load_anchors(tmp_path)

    no_outliers = json.loads(json.dumps(good))
    no_outliers["anchors"]["brent_cross_check"].pop("outliers")
    write(no_outliers)
    with pytest.raises(SourceError, match="outliers"):
        ea.load_anchors(tmp_path)


# --------------------------------------------------------------------------
# The manifest entries the two files produce
# --------------------------------------------------------------------------

def test_recording_the_seeds_writes_three_entries(sandbox):
    """events, anchors and sp_global_reference, into a sandboxed manifest."""
    import shutil

    from crack.sources import base

    seed_dir = sandbox / "seed"
    seed_dir.mkdir(parents=True, exist_ok=True)
    for name in ("events.json", "anchors.json"):
        shutil.copy(SEED / name, seed_dir / name)

    entries = ea.record_all(seed_dir)
    assert [e["series"] for e in entries] == ["events", "anchors", "sp_global_reference"]

    payload = base.manifest_read()
    written = {e["series"]: e for e in payload["series"]}
    for name in ("events", "anchors", "sp_global_reference"):
        entry = written[name]
        # A file nothing fetched has no fetch time. base.manifest_upsert refuses
        # an entry that breaks this, so reaching here already proves it, but the
        # provenance panel prints both fields and a reader should see the rule.
        assert entry["machine_fetched"] is False
        assert entry["fetched_at"] is None
        assert entry["checked_at"]
        assert entry["method"] == "seed"
        assert entry["status"] == "ok"
        assert entry["observations"] > 0

    assert written["anchors"]["file"] == written["sp_global_reference"]["file"], (
        "the two entries describe two blocks of one file and must name the same file"
    )
    assert written["anchors"]["licence_note"] != written["sp_global_reference"]["licence_note"], (
        "the two entries exist BECAUSE their terms differ. Identical licence notes "
        "would mean one file with one set of terms, and then one entry would do"
    )


def test_the_manifest_dates_are_days_even_when_an_event_is_a_month(sandbox):
    """first_date and last_date are range bounds, in one shape, always.

    The earliest event names a month. The manifest pads it to the first of that
    month for the range bound and says so, and the event's own precision stays
    in the file where a chart marker reads it.
    """
    import shutil

    seed_dir = sandbox / "seed"
    seed_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(SEED / "events.json", seed_dir / "events.json")

    entry = ea.record_events(seed_dir)
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", entry["first_date"])
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", entry["last_date"])
    assert entry["date_padding_note"]


# --------------------------------------------------------------------------
# scripts/refresh.py
# --------------------------------------------------------------------------

def test_every_job_names_only_registered_series():
    """A job that names an unregistered series would write an untraceable entry."""
    from crack.config import SOURCES

    for job in refresh.JOBS:
        for name in job.series:
            assert name in SOURCES, "job %r names the unregistered series %r" % (
                job.name,
                name,
            )


def test_every_registered_series_is_owned_by_exactly_one_job():
    """No series can be missed by a full run, and none can be run twice."""
    from crack.config import SOURCES

    owned = [name for job in refresh.JOBS for name in job.series]
    assert len(owned) == len(set(owned)), "a series is claimed by two jobs"
    missing = sorted(set(SOURCES) - set(owned))
    assert not missing, "no job builds these registered series: %s" % missing


def test_the_manual_steps_are_complete_and_attached():
    """Two of them, each saying what, why, what it costs and how.

    Both are ways this project loses data permanently if somebody forgets, so
    "it is in the README" is not good enough and they go in the manifest.
    """
    ids = [step["id"] for step in refresh.MANUAL_STEPS]
    assert ids == ["momr_unarchived_2026", "dgec_weekly_note_collection"]
    for step in refresh.MANUAL_STEPS:
        for key in ("what", "why", "cost_if_skipped", "how", "cadence", "series", "status"):
            assert step.get(key), "manual step %s has no %s" % (step["id"], key)
        assert step["series"], step["id"]


def test_the_committed_manifest_carries_the_manual_steps():
    payload = json.loads((REPO_ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    recorded = {step["id"] for step in payload.get("manual_steps", [])}
    assert recorded == {step["id"] for step in refresh.MANUAL_STEPS}

    by_series = {e["series"]: e for e in payload["series"]}
    for step in refresh.MANUAL_STEPS:
        for name in step["series"]:
            attached = by_series[name].get("manual_step") or []
            assert any(s["id"] == step["id"] for s in attached), (
                "%s does not carry the manual step %s, so nobody reading the "
                "provenance panel for that series would learn about it"
                % (name, step["id"])
            )


def test_manifest_is_unchanged_ignores_only_the_clock():
    """The mechanism behind byte idempotence, tested directly."""
    before = {
        "schema_version": 1,
        "generated_at": "2026-09-13T00:00:00Z",
        "run": {"mode": "offline"},
        "series": [{"series": "a", "rows": 3, "checked_at": "2026-09-13T00:00:00Z"}],
    }
    raw = json.dumps(before).encode("utf-8")

    later = json.loads(json.dumps(before))
    later["generated_at"] = "2026-09-14T09:00:00Z"
    later["run"] = {"mode": "offline", "started_at": "later"}
    later["series"][0]["checked_at"] = "2026-09-14T09:00:00Z"
    assert refresh.manifest_is_unchanged(raw, later) is True

    changed = json.loads(json.dumps(later))
    changed["series"][0]["rows"] = 4
    assert refresh.manifest_is_unchanged(raw, changed) is False


def test_carry_forward_keeps_what_offline_cannot_know():
    """An offline run must not overwrite provenance only a fetch could produce."""
    entry = {
        "series": "x",
        "machine_fetched": True,
        "fetched_at": "2026-09-13T12:00:00Z",
        "vintage": None,
        "provisional_from": None,
    }
    previous = {
        "series": "x",
        "machine_fetched": True,
        "fetched_at": "2026-09-01T08:00:00Z",
        "vintage": "NPG-2026.09.04",
        "provisional_from": "2026-08-01",
        "specification_timeline": [{"month": "2013-07"}],
        "attribution": "Argus, via the OPEC Monthly Oil Market Report",
    }
    out = refresh.carry_forward(dict(entry), previous)
    assert out["fetched_at"] == "2026-09-01T08:00:00Z", (
        "an offline run fetched nothing and must not stamp a fresh fetch time"
    )
    assert out["vintage"] == "NPG-2026.09.04"
    assert out["provisional_from"] == "2026-08-01"
    assert out["specification_timeline"] == [{"month": "2013-07"}]
    assert out["attribution"].startswith("Argus")


def test_revalidate_fails_loudly_on_a_missing_cache(sandbox):
    """A cache that is not there is a failure, never an empty series."""
    from crack.sources.fred import FredBrent

    entry = refresh.revalidate(FredBrent(), None)
    assert entry["status"] == "failed"
    assert "not on disk" in entry["note"]
    assert entry["rows"] == 0


def test_the_offline_run_leaves_the_committed_manifest_byte_identical(tmp_path):
    """PROMISE 3, end to end, against the real repository.

    The run is made in a copy of the working tree so this test cannot damage the
    committed data, and the assertion is on the bytes rather than on the parsed
    object, because the CI check this protects is git diff.
    """
    import shutil
    import subprocess

    work = tmp_path / "repo"
    work.mkdir()
    for name in ("pyproject.toml", "SPEC.md"):
        shutil.copy(REPO_ROOT / name, work / name)
    shutil.copytree(REPO_ROOT / "src", work / "src")
    shutil.copytree(REPO_ROOT / "scripts", work / "scripts")
    shutil.copytree(REPO_ROOT / "data" / "cache", work / "data" / "cache")
    shutil.copytree(REPO_ROOT / "data" / "seed", work / "data" / "seed")
    shutil.copy(REPO_ROOT / "data" / "manifest.json", work / "data" / "manifest.json")

    before = (work / "data" / "manifest.json").read_bytes()
    result = subprocess.run(
        [sys.executable, "scripts/refresh.py", "--offline"],
        cwd=work,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    after = (work / "data" / "manifest.json").read_bytes()
    assert after == before, (
        "an offline refresh on an unchanged tree rewrote data/manifest.json. "
        "That makes the CI check git diff --exit-code meaningless"
    )
    assert "byte identical" in result.stdout


# --------------------------------------------------------------------------
# The manifest must not assert a check that was not run
# --------------------------------------------------------------------------

def test_the_mbr_reproduction_is_measured_against_the_cache_not_read_from_the_seed():
    """Gate 1 self audit, finding d.1, closed and tested.

    measure_mbr_reproduction opens data/cache/dgec_mbr_monthly.csv and compares.
    It does not look at the seed file's own "reproduces" flags at all, which is
    the whole point: those flags were what the manifest used to be counting, and
    a flag is a claim rather than a measurement.
    """
    payload = ea.load_anchors()
    measured = ea.measure_mbr_reproduction(payload["_mbr"])
    assert measured["checked"] == 9
    assert measured["reproduced"] == 9
    assert measured["failures"] == []
    assert measured["cache"] == "data/cache/dgec_mbr_monthly.csv"


def test_a_value_corrupted_inside_its_bounds_is_caught_by_the_anchor_measurement(
    sandbox, tmp_path, monkeypatch
):
    """The audit's own fault injection, as a test that runs on every gate.

    The audit set July 2026 to 99.99, which is a 172 percent error on a figure
    SPEC.md section 5.5 prints and comfortably inside BOUNDS_MARGIN_USD_BBL, and
    the offline refresh reported 19 of 19 ok while the manifest went on saying
    the anchors reproduced. Now the measurement is taken against the cache on
    every run, the entry goes to status failed with the disagreement in its note,
    and record_anchors raises so the run exits non zero.

    The corruption happens to a COPY. The committed cache is never written to by
    a test, which is why crack.sources.events_anchors.CACHE is redirected rather
    than the real file being edited and put back: a test that edits a committed
    file and restores it afterwards leaves the file damaged whenever it fails.
    """
    import shutil

    from crack.sources import base

    fake_cache = tmp_path / "fake_cache"
    fake_cache.mkdir()
    seed_dir = tmp_path / "fake_seed"
    seed_dir.mkdir()
    for name in ("events.json", "anchors.json"):
        shutil.copy(SEED / name, seed_dir / name)

    cache = fake_cache / ea.MBR_CACHE
    original = (REPO_ROOT / "data" / "cache" / ea.MBR_CACHE).read_text(encoding="utf-8")
    lines = original.split("\n")
    header = lines[0].split(",")
    value_at = header.index(ea.MBR_COLUMN)
    date_at = header.index("date")
    hit = None
    for index, line in enumerate(lines[1:], start=1):
        cells = line.split(",")
        if len(cells) > value_at and cells[date_at] == "2026-07-01":
            cells[value_at] = "99.99"
            lines[index] = ",".join(cells)
            hit = index
            break
    assert hit is not None, "2026-07-01 is not in the committed MBR cache"
    cache.write_text("\n".join(lines), encoding="utf-8", newline="")
    monkeypatch.setattr(ea, "CACHE", fake_cache)

    payload = ea.load_anchors(seed_dir)
    measured = ea.measure_mbr_reproduction(payload["_mbr"])
    assert measured["reproduced"] == 8
    assert len(measured["failures"]) == 1
    assert "2026-07" in measured["failures"][0]
    assert "99.99" in measured["failures"][0]

    with pytest.raises(SourceError, match="reproduce"):
        ea.record_anchors(seed_dir)

    # AND THE MANIFEST SAYS SO. It does not keep the last good sentence.
    entry = None
    for candidate in base.manifest_read()["series"]:
        if candidate.get("series") == "anchors":
            entry = candidate
    assert entry is not None
    assert entry["status"] == "failed"
    assert entry["mbr_anchors_reproduced"] == 8
    assert entry["mbr_anchors_that_do_not_reproduce"]
    assert "DOES NOT REPRODUCE" in entry["note"]

    # The committed cache was never touched.
    assert (REPO_ROOT / "data" / "cache" / ea.MBR_CACHE).read_text(
        encoding="utf-8"
    ) == original


def test_an_invalid_private_cache_does_not_leave_its_entry_reading_ok(sandbox):
    """Gate 1 self audit, finding d.2.

    The default offline mode does not revalidate a private entry into the
    manifest, for a good reason: the two private caches are not in the
    repository, so revalidating them would produce one manifest on the owner's
    machine and another in CI. But it used to exit non zero on an invalid private
    cache while leaving that entry reading status "ok", so the committed manifest
    described a file the tool had just declared bad.
    """
    from crack.sources import base
    from crack.sources.yahoo import TtfFrontMonth

    adapter = TtfFrontMonth()
    private = base.PRIVATE / "ttf_daily.csv"
    private.parent.mkdir(parents=True, exist_ok=True)
    private.write_text(
        "date,open,high,low,close,volume\n"
        "2026-09-10,30,31,29,30,1\n"
        "2026-09-11,30,31,29,99999,1\n",
        encoding="utf-8",
        newline="",
    )

    valid, report = refresh._private_check(adapter)
    assert valid is False
    assert report.startswith("PRESENT AND INVALID")

    previous = {
        "series": "ttf_daily",
        "status": "ok",
        "method": "published",
        "committable": False,
        "licence_note": "NOT committable, there is no Yahoo redistribution grant",
        "rows": 2235,
        "note": "the last real run's note",
    }
    refresh.mark_private_failed(adapter, previous, report)

    entry = None
    for candidate in base.manifest_read()["series"]:
        if candidate.get("series") == "ttf_daily":
            entry = candidate
    assert entry is not None
    assert entry["status"] == "failed"
    assert "OFFLINE REVALIDATION FOUND THIS CACHE INVALID" in entry["note"]
    assert "99999" in entry["note"]
    # The measurements are left alone, because this run measured nothing it
    # trusts. Only the status and the note move.
    assert entry["rows"] == 2235


def test_a_valid_or_absent_private_cache_still_carries_through(sandbox):
    """The normal cases must not become failures. CI has neither file."""
    from crack.sources import base
    from crack.sources.yahoo import TtfFrontMonth

    adapter = TtfFrontMonth()
    private = base.PRIVATE / "ttf_daily.csv"
    if private.exists():
        private.unlink()
    valid, report = refresh._private_check(adapter)
    assert valid is True
    assert "not on this machine" in report


def test_offline_restates_the_dgec_provisional_sentence_without_a_fetch():
    """Gate 1 self audit, finding 1.2, and how the correction reaches the manifest.

    An offline run keeps the note the last real run wrote, because that note
    names a discovered URL and a fetch's own measurements. The provisional
    sentence is the one part of it that depends only on the committed cache and
    the calendar, so the adapter may restate it. Without that hook, a correction
    to its wording would sit in the source until somebody happened to fetch.
    """
    from crack.sources.dgec import DgecMbrMonthly

    adapter = DgecMbrMonthly(today=pd.Timestamp("2026-09-13"))
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-07-01", "2026-08-01"]),
            "mbr_usd_bbl": [36.69, 38.05],
            "mbr_eur_t": [230.0, 240.0],
        }
    )
    stale = (
        "Gross refining margin, read from the workbook, this run used http://x. "
        "No provisional month. This workbook publishes complete months only and "
        "its last is 2026-08, which is already over."
    )
    restated = adapter.offline_note(stale, frame)
    assert restated.startswith("Gross refining margin, read from the workbook")
    assert "which is already over" not in restated
    assert "A month being over does NOT make its figure final" in restated
    assert "WHAT REMAINS UNCERTAIN" in restated
    assert adapter.provisional_from is None

    # A note with no provisional sentence in it is returned untouched, so this
    # can never invent one.
    assert adapter.offline_note("a note about something else", frame) == (
        "a note about something else"
    )
    assert adapter.offline_note("", frame) == ""


def test_the_committed_manifest_no_longer_argues_from_the_calendar():
    """The corrected reasoning is in the artifact, not only in the source."""
    payload = json.loads(
        (REPO_ROOT / "data" / "manifest.json").read_text(encoding="utf-8")
    )
    entry = next(e for e in payload["series"] if e["series"] == "dgec_mbr_monthly")
    assert "which is already over" not in entry["note"]
    assert "A month being over does NOT make its figure final" in entry["note"]
    assert "WHAT REMAINS UNCERTAIN" in entry["note"]
