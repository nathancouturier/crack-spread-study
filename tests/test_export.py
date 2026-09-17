"""The site facing artifacts, src/crack/export.py. Gate 4.

What these hold down:

  byte idempotence     two independent builds serialise to the same bytes, and
                       those bytes are the committed data/*.json
  build-check          a stale artifact is caught, by name, and nothing is written
  no NaN               a missing value is null; a NaN that reaches the
                       serialiser raises rather than writing a token no browser
                       parses
  agreement            the verdict fields are crack.series.latest_view's and
                       crack.analysis's numbers, not a second computation of them
  unidentified         an unidentified threshold exports the word, a null
                       headroom and no headroom figure in any sentence; an
                       identified one exports the headroom latest_view computes
  sentences            no text segment carries a digit, so every figure on the
                       page names the field it came from
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from crack import analysis, config, export, series

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA = REPO_ROOT / "data"


@pytest.fixture(scope="module")
def inputs():
    return export.Inputs()


@pytest.fixture(scope="module")
def built(inputs):
    return export.build(inputs)


def _segment_lists(value, where=""):
    if isinstance(value, list):
        for i, item in enumerate(value):
            yield from _segment_lists(item, "%s[%d]" % (where, i))
    elif isinstance(value, dict):
        for key, child in value.items():
            here = "%s.%s" % (where, key) if where else key
            if key.endswith("segments") and isinstance(child, list):
                yield here, child
            else:
                yield from _segment_lists(child, here)


# ---------------------------------------------------------------------------
# Byte idempotence and build-check
# ---------------------------------------------------------------------------


def test_the_artifact_set_is_the_five_the_now_view_reads_and_history(built):
    assert list(built) == ["now", "cracks", "margin-stack", "run-economics", "provenance", "history"]
    for name, payload in built.items():
        assert payload["schema_version"] == export.SCHEMA_VERSION
        assert payload["artifact"] == name
        assert payload["generated_by"] == "src/crack/export.py"
        assert len(payload["data_date"]) == 10
        assert "generated_at" not in payload


def test_two_independent_builds_are_byte_identical(built):
    again = export.build(export.Inputs())
    for name in built:
        assert export.serialise(built[name]) == export.serialise(again[name]), name


def test_the_committed_artifacts_are_what_the_build_produces(built):
    """build-check on the real tree. A cache or analysis change not rebuilt fails here."""
    assert export.stale_artifacts(built, DATA) == []


def test_serialised_text_is_ascii_lf_with_one_trailing_newline(built):
    for name, payload in built.items():
        text = export.serialise(payload)
        text.encode("ascii")
        assert "\r" not in text
        assert text.endswith("}\n") and not text.endswith("\n\n"), name


def test_build_check_catches_a_stale_artifact_and_writes_nothing(inputs, tmp_path, capsys):
    report = export.write_all(tmp_path, inputs)
    assert all(item["changed"] for item in report)
    assert export.check(tmp_path, inputs) == 0

    target = tmp_path / "margin-stack.json"
    text = target.read_text(encoding="ascii")
    stale = text.replace('"decomposed": true', '"decomposed": false', 1)
    assert stale != text
    target.write_bytes(stale.encode("ascii"))
    before = {p.name: p.read_bytes() for p in tmp_path.glob("*.json")}

    assert export.check(tmp_path, inputs) == 1
    out = capsys.readouterr().out
    assert "STALE    data/margin-stack.json" in out
    assert "now.json" not in out.split("checked", 1)[1].split("STALE", 1)[0]
    after = {p.name: p.read_bytes() for p in tmp_path.glob("*.json")}
    assert before == after, "check wrote to the directory it was checking"

    target.unlink()
    assert export.stale_artifacts(export.build(inputs), tmp_path) == ["margin-stack"]


def test_a_second_write_changes_nothing(inputs, tmp_path):
    export.write_all(tmp_path, inputs)
    stamps = {p.name: p.stat().st_mtime_ns for p in tmp_path.glob("*.json")}
    report = export.write_all(tmp_path, inputs)
    assert not any(item["changed"] for item in report)
    assert stamps == {p.name: p.stat().st_mtime_ns for p in tmp_path.glob("*.json")}


# ---------------------------------------------------------------------------
# Missing is null, never NaN
# ---------------------------------------------------------------------------


def test_no_nan_or_infinity_token_in_any_artifact(built):
    for name, payload in built.items():
        text = export.serialise(payload)
        # Strip string literals, then look for the bare tokens.
        import re

        bare = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
        assert "NaN" not in bare, name
        assert "Infinity" not in bare, name
        json.loads(text)


def test_a_nan_becomes_null_and_a_nan_that_slips_through_raises():
    assert export._num(math.nan) is None
    assert export._num(np.float64("nan")) is None
    assert export._num(math.inf) is None
    assert export._num(-0.0) == 0.0 and math.copysign(1.0, export._num(-0.0)) == 1.0
    with pytest.raises(ValueError):
        export.serialise({"value": math.nan})
    with pytest.raises(ValueError):
        export.serialise({"rows": [[1.0, math.inf]]})


def test_week_fifty_three_is_null_not_zero(built):
    weeks = built["cracks"]["panels"]["gasoil"]["weeks"]
    last = [row for row in weeks if row[0] == 53][0]
    assert last[1] == 0
    assert last[2] is None and last[3] is None
    assert all(v is None for v in last[4])


# ---------------------------------------------------------------------------
# The verdict agrees with crack.series and crack.analysis
# ---------------------------------------------------------------------------


def test_verdict_values_are_latest_views(built):
    view = series.latest_view()
    values = built["now"]["verdict"]["values"]
    assert values["margin_month"] == view.margin_month
    assert values["mbr_usd_bbl"] == pytest.approx(view.mbr_usd_bbl, abs=1e-6)
    assert values["margin_after_gas_usd_bbl"] == pytest.approx(view.margin_after_gas_usd_bbl, abs=1e-6)
    assert values["percentile_10y"] == pytest.approx(view.percentile_10y, abs=1e-6)
    assert values["percentile_observations"] == view.percentile_observations
    assert values["percentile_window_months"] == config.PERCENTILE_WINDOW_MONTHS
    assert values["percentile_rank"] * 100.0 / values["percentile_observations"] == pytest.approx(
        view.percentile_10y, abs=1e-9
    )
    assert values["gas_wedge_usd_bbl"] == pytest.approx(view.gas_wedge.wedge_usd_bbl, abs=1e-6)
    assert values["intensity_ratio"] == pytest.approx(view.gas_wedge.ratio, abs=1e-6)
    assert values["gas_usd_mmbtu"] == pytest.approx(view.gas_usd_mmbtu, abs=1e-6)
    # The carrier is the margin month's own, from the ministry's printed prices.
    assert values["carrier"] == view.margin_carrier == "gasoil"
    assert values["crack_month"] == view.margin_month
    assert values["carrier_contribution_usd_bbl"] == pytest.approx(
        view.margin_decomposition.carrier_contribution_usd_bbl, abs=1e-6
    )
    assert values["net_of"]["gas"] is True
    assert values["net_of"]["embedded_gas_intensity_mmbtu_per_bbl"] == pytest.approx(
        config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL, abs=1e-6
    )
    # Today's values, pinned, so a silent move shows up as a named failure.
    assert values["mbr_usd_bbl"] == pytest.approx(38.0505, abs=5e-5)
    assert values["percentile_rank"] == 120
    assert values["margin_study_intensity_usd_bbl"] == pytest.approx(34.9628, abs=5e-5)
    assert values["carrier_contribution_usd_bbl"] == pytest.approx(26.9966, abs=5e-4)


def test_margin_at_the_study_intensity_is_analysis_margin_frame(built):
    margin = analysis.margin_frame()
    values = built["now"]["verdict"]["values"]
    row = margin[margin["date"].dt.strftime("%Y-%m-%d") == values["margin_month"]].iloc[0]
    assert values["margin_study_intensity_usd_bbl"] == pytest.approx(
        float(row[analysis.MARGIN_STUDY_INTENSITY]), abs=1e-6
    )


def test_the_waterfall_is_the_note_decomposition(built):
    view = series.latest_view()
    rows = {row["id"]: row for row in built["margin-stack"]["rows"]}
    d = view.margin_decomposition
    for product, value in d.contributions.items():
        assert rows[product]["value_usd_bbl"] == pytest.approx(value, abs=1e-6)
        assert rows[product]["crack_usd_bbl"] == pytest.approx(view.margin_cracks[product].value, abs=1e-6)
        assert rows[product]["bbl_per_t"] == config.DGEC_NOTE_PRODUCT_BBL_PER_T[product]
    assert rows["residual"]["value_usd_bbl"] == pytest.approx(d.residual_usd_bbl, abs=1e-6)
    assert [x["slate_line"] for x in rows["residual"]["contains"]["slate_lines"]] == list(d.unattributed_products)
    assert rows["official_margin"]["value_usd_bbl"] == pytest.approx(view.mbr_usd_bbl, abs=1e-6)
    assert rows["gas_wedge"]["value_usd_bbl"] == pytest.approx(-view.gas_wedge.wedge_usd_bbl, abs=1e-6)
    assert rows["gas_wedge"]["embedded_intensity_mmbtu_per_bbl"] == pytest.approx(
        config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL, abs=1e-6
    )
    assert rows["gas_wedge"]["study_intensity_mmbtu_per_bbl"] == config.GAS_INTENSITY_MMBTU_PER_BBL
    # Every step starts where the last row ended, and the products plus the
    # residual land exactly on the official margin.
    running = 0.0
    for row in built["margin-stack"]["rows"]:
        if row["kind"] == "step":
            assert row["start_usd_bbl"] == pytest.approx(running, abs=1e-5)
        running = row["end_usd_bbl"]
    assert rows["residual"]["end_usd_bbl"] == pytest.approx(view.mbr_usd_bbl, abs=1e-5)
    scale = built["margin-stack"]["scale"]
    assert scale["low_usd_bbl"] <= 0.0 <= scale["high_usd_bbl"]
    assert scale["high_usd_bbl"] >= max(r["end_usd_bbl"] for r in rows.values())


def test_the_response_rows_are_analysis_and_the_planned_model_comes_first(built, inputs):
    models = built["run-economics"]["response"]["models"]
    assert [m["id"] for m in models] == ["capacity", "intake_trend"]
    for row, model in zip(models, (analysis.margin_response(frame=inputs.frame), analysis.intake_trend_response(frame=inputs.frame))):
        assert row["kb_d"] == pytest.approx(model.translation.kb_d, abs=1e-6)
        assert row["kb_d_low"] == pytest.approx(model.translation.kb_d_low, abs=1e-6)
        assert row["kb_d_high"] == pytest.approx(model.translation.kb_d_high, abs=1e-6)
        assert row["t"] == pytest.approx(model.sum_b_t, abs=1e-6)
        assert row["months"] == model.regression.nobs
    assert models[0]["interval_includes_zero"] is True and models[0]["lower_share"] is None
    assert models[1]["interval_includes_zero"] is False
    assert models[1]["lower_share"] == pytest.approx(
        models[1]["kb_d_low"] / (models[1]["kb_d_high"] - models[1]["kb_d_low"]), abs=1e-5
    )


def test_the_three_data_dates_stay_apart_each_with_its_own_flag(built):
    dates = built["now"]["data_dates"]
    assert [d["id"] for d in dates] == ["margins", "weekly_cracks", "runs"]
    by = {d["id"]: d for d in dates}
    assert by["margins"]["date"] == "2026-08-01" and by["margins"]["status_word"] == "final"
    assert by["margins"]["provisional"] is False
    # The note that last printed the margin month's prices, and the last week of
    # the reconstruction, both move with every weekly note collected, so both
    # are read from the committed caches rather than pinned.
    printed = series.load("dgec_note_printed_monthly")
    row = printed[pd.to_datetime(printed["date"]) == pd.Timestamp(by["margins"]["date"])]
    assert by["margins"]["quotations_vintage"] == str(row["vintage"].iloc[0])
    weekly = series.load("dgec_note_reconstructed_weekly")
    assert by["weekly_cracks"]["date"] == str(pd.to_datetime(weekly["date"]).max().date())
    assert by["weekly_cracks"]["status_word"] == "reconstructed"
    assert by["runs"]["date"] == "2026-06-01"
    assert by["runs"]["provisional"] is True and by["runs"]["status_word"] == "provisional"
    assert len({d["date"] for d in dates}) == 3


def test_the_cracks_latest_week_agrees_with_analysis_seasonal_weekly(built):
    latest = built["cracks"]["latest"]
    assert latest["date"] == series.latest_view().weekly_crack_data_date
    for product, column in (("gasoil", analysis.CRACK_GASOIL), ("gasoline", analysis.CRACK_GASOLINE)):
        table = analysis.seasonal_weekly(column)
        row = table[table["week"] == latest["iso_week"]].iloc[0]
        info = latest["products"][product]
        assert latest["n_years"] == int(row["n_years"])
        assert info["value_usd_bbl"] == pytest.approx(float(row["current"]), abs=1e-6)
        assert info["prior_minimum_usd_bbl"] == pytest.approx(float(row["minimum"]), abs=1e-6)
        assert info["prior_maximum_usd_bbl"] == pytest.approx(float(row["maximum"]), abs=1e-6)
        values = [p["value_usd_bbl"] for p in info["prior_years"]]
        assert len(values) == int(row["n_years"])
        assert min(values) == pytest.approx(float(row["minimum"]), abs=1e-6)
        assert max(values) == pytest.approx(float(row["maximum"]), abs=1e-6)
        for point in info["prior_years"] + [info["point"]]:
            assert point["evidence"] in ("printed", "reconstructed")
            assert point["least_defended"] == (point["evidence_class"] == "single_geometry_oldest")
        # Every panel row's n_years is seasonal_weekly's, week by week.
        panel = built["cracks"]["panels"][product]
        assert [r[1] for r in panel["weeks"]] == [int(x) for x in table["n_years"]]
    # The least defended weeks are carried, and there are six of them.
    assert built["cracks"]["series_note"]["evidence_class_counts"]["single_geometry_oldest"] == 6


# ---------------------------------------------------------------------------
# Unidentified means no headroom number, anywhere
# ---------------------------------------------------------------------------


def test_the_unidentified_threshold_exports_as_unidentified_with_no_headroom(built, inputs):
    threshold = inputs.threshold
    assert threshold.identified is False
    run = built["run-economics"]["threshold"]
    assert run["verdict"] == "unidentified"
    assert run["threshold_identified"] is False
    assert run["headroom_usd_bbl"] is None
    assert built["now"]["verdict"]["values"]["headroom_usd_bbl"] is None
    assert built["now"]["verdict"]["values"]["run_verdict"] == "unidentified"
    for name in ("now", "run-economics"):
        for where, segments in _segment_lists(built[name]):
            for segment in segments:
                assert segment.get("field") != "headroom_usd_bbl", (name, where)
    words = [s for s in run["segments"] if s.get("field") == "verdict"]
    assert words and words[0]["value"] == "unidentified"
    # The stronger evidence leads: the sign flip without the episode.
    assert run["slope_changes_sign_without_episode"] is True
    assert run["slope_below_usd_bbl"] > 0 > run["slope_below_without_episode"]
    assert run["fallback_segments"], "the percentile fallback is missing"


def test_an_identified_threshold_exports_latest_views_headroom(inputs):
    threshold = replace(inputs.threshold, identified=True, reasons=(), verdict="identified")
    view = inputs.view
    rank = export._trailing_rank(inputs)
    run = export.run_verdict(threshold, inputs.threshold_without_stretch, view, rank)
    expected = series.latest_view(threshold=threshold.point.threshold).headroom_usd_bbl
    assert run["threshold_identified"] is True
    assert run["headroom_usd_bbl"] == pytest.approx(expected, abs=1e-6)
    assert any(s.get("field") == "headroom_usd_bbl" for s in run["segments"])
    assert run["fallback_segments"] == []
    segments = export.verdict_segments({**export.verdict_values(inputs)}, run)
    assert any(s.get("field") == "headroom_usd_bbl" for s in segments)


# ---------------------------------------------------------------------------
# Sentences
# ---------------------------------------------------------------------------


def test_no_text_segment_carries_a_digit(built):
    found = 0
    for name, payload in built.items():
        for where, segments in _segment_lists(payload):
            for segment in segments:
                found += 1
                if "text" in segment:
                    assert set(segment) == {"text"}, (name, where)
                    assert not any(c.isdigit() for c in segment["text"]), (name, where, segment)
                else:
                    assert segment["field"], (name, where)
                    if "format" in segment:
                        assert segment["format"] in payload["conventions"]["decimals"]
                    else:
                        assert segment["label"], (name, where)
    assert found > 50


def test_the_verdict_reads_as_the_design_says(built):
    words = "".join(
        s["text"] if "text" in s else (s.get("label") or str(s["value"]))
        for s in built["now"]["verdict"]["segments"]
    )
    assert words == (
        "On the ministry's Rotterdam measure, refiners' gross margin after the ministry's gas allowance "
        "was 38.050505 $/bbl in August 2026, the most in 120 months; gasoil carried 26.996621 of it, "
        "and this sample cannot say whether runs have room to rise."
    )
    # SPEC.md section 7.2, said out loud: four clauses, the month once, and the
    # US intensity figure is not in it (docs/design.md Part 7, C9).
    assert words.count("August 2026") == 1
    fields = [s["field"] for s in built["now"]["verdict"]["segments"] if "field" in s]
    assert "margin_study_intensity_usd_bbl" not in fields
    assert "intensity_ratio" not in fields
    assert len(words.split()) <= 40
    # The figure moved to the section where the wedge is drawn.
    moved = {s["field"] for s in built["margin-stack"]["study_margin_segments"] if "field" in s}
    assert {"margin_study_intensity_usd_bbl", "intensity_ratio", "gas_wedge_usd_bbl"} <= moved
    for banned in ("clears zero", "a coin", "SPEC", "product prices", "Rotterdam refiners made", "winner"):
        for payload in built.values():
            for _, segments in _segment_lists(payload):
                for s in segments:
                    assert banned not in s.get("text", ""), banned


# ---------------------------------------------------------------------------
# The node validator, which is in make gate, fails on a broken artifact
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_validate_artifacts_passes_the_build_and_fails_a_tampered_one(inputs, tmp_path):
    export.write_all(tmp_path, inputs)
    tool = str(REPO_ROOT / "tools" / "validate-artifacts.mjs")
    ok = subprocess.run(["node", tool, str(tmp_path)], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout + ok.stderr

    now = json.loads((tmp_path / "now.json").read_text(encoding="ascii"))
    now["verdict"]["segments"].append({"text": "and 38 more"})
    del now["verdict"]["values"]["percentile_rank"]
    (tmp_path / "now.json").write_text(json.dumps(now), encoding="ascii")
    stack = (tmp_path / "margin-stack.json").read_text(encoding="ascii")
    (tmp_path / "margin-stack.json").write_text(stack.replace('"accent": true', '"accent": NaN', 1), encoding="ascii")
    bad = subprocess.run(["node", tool, str(tmp_path)], capture_output=True, text=True)
    assert bad.returncode == 1
    assert "percentile_rank is missing" in bad.stdout
    assert "has a digit in its words" in bad.stdout
    assert "bare NaN token" in bad.stdout


def test_every_sentence_the_now_sections_print_is_exported(built):
    """docs/design.md Part 7, C4: the sections' sentences travel as segments
    too, so the page composes none of them around a figure of its own."""
    cracks = built["cracks"]["latest"]["products"]
    for product in ("gasoil", "gasoline"):
        assert cracks[product]["heading_segments"] and cracks[product]["desc_segments"]
        words = "".join(s.get("text", "") for s in cracks[product]["heading_segments"])
        assert "read off the ministry's chart" in words
    stack = built["margin-stack"]
    assert stack["scale"]["segments"]
    for row in stack["rows"]:
        if row["id"] not in ("residual", "official_margin", "gas_wedge", "margin_study_intensity"):
            assert row["detail_segments"], row["id"]
    runs = built["run-economics"]
    zero = {m["id"]: m["zero_segments"] for m in runs["response"]["models"]}
    assert zero["capacity"] == [{"field": "interval_includes_zero", "value": "includes zero", "label": "includes zero"}]
    assert any(s.get("field") == "lower_share_percent" for s in zero["intake_trend"])
    assert runs["response"]["strip_desc_segments"]
    latest = runs["utilisation"]["latest_segments"]
    assert any(s.get("field") == "status_word" and s["value"] == "provisional" for s in latest)
    assert all(m["month_label"] for m in runs["utilisation"]["post_break_months"])


# ---------------------------------------------------------------------------
# Gate 4 audit fixes (docs/self-audit.md, Self audit, Gate 4; docs/design.md
# Part 7, C10 to C15)
# ---------------------------------------------------------------------------


def _words(segments):
    return "".join(s["text"] if "text" in s else (s.get("label") or str(s["value"])) for s in segments)


def test_no_sentence_claims_the_margin_was_kept_or_says_its_own_gas(built):
    """S4. "Kept" claims realised earnings for a margin that nets out only
    energy, and "its own gas allowance" reads as the refiner's gas. The verdict
    says gross margin and names the ministry as the owner of the allowance."""
    for name, payload in built.items():
        for where, segments in _segment_lists(payload):
            words = _words(segments)
            assert " kept " not in words, (name, where, words)
            assert "its own gas" not in words, (name, where, words)
    verdict = _words(built["now"]["verdict"]["segments"])
    assert "gross margin" in verdict and "the ministry's gas allowance" in verdict


def test_the_weekly_headline_leads_with_the_figure_the_ministry_printed(built):
    """S5. When the note printed the latest week, the summary and both panel
    headings lead with the printed figure and give the chart reading second."""
    latest = built["cracks"]["latest"]["products"]
    summary = next(s for s in built["now"]["sections"] if s["id"] == "cracks")["summary_segments"]
    numbers = [s["field"] for s in summary if "format" in s]
    printed = {p: latest[p]["point"]["printed_usd_bbl"] for p in ("gasoil", "gasoline")}
    assert all(v is not None for v in printed.values()), "today's latest week is printed; this test needs it"
    assert numbers[:2] == ["gasoil_printed_usd_bbl", "gasoline_printed_usd_bbl"], numbers
    assert numbers.index("gasoil_usd_bbl") > 1
    for product in ("gasoil", "gasoline"):
        heading = latest[product]["heading_segments"]
        fields = [s["field"] for s in heading if "format" in s]
        assert fields[0] == "%s_printed_usd_bbl" % product, fields
        assert "%s_usd_bbl" % product in fields[1:]
        assert "printed" in _words(heading)


def test_an_unprinted_latest_week_leads_with_the_chart_reading(inputs):
    info = dict(export.latest_week(inputs)["products"]["gasoil"])
    info["point"] = {**info["point"], "printed_usd_bbl": None, "evidence": "reconstructed"}
    heading = export._panel_heading("gasoil", info, "2026-09-04", 4)
    fields = [s["field"] for s in heading if "format" in s]
    assert fields[0] == "gasoil_usd_bbl"
    assert "printed" not in _words(heading)


def test_provenance_carries_a_reader_layer_for_every_series_and_step(built):
    """S3, S8, M6, M7. The manifest stays whole for the machine; the page
    reads labels, sources, provisional flags and manual steps written for a
    reader, and a series or a step with no reader text fails the build."""
    payload = built["provenance"]
    reader = payload["reader"]
    manifest = payload["manifest"]
    assert set(reader["series"]) == {e["series"] for e in manifest["series"]}
    labels = [r["label"] for r in reader["series"].values()]
    assert len(set(labels)) == len(labels), "two series share a label"
    engineering = ("recon", "HTTP", "this machine", "python", "--", "data/", "manual_step", " ,", "DELETES", "at any price")
    for series_id, row in reader["series"].items():
        assert "_" not in row["label"] and "_" not in row["source"], series_id
        assert row["label"][0].isupper(), series_id
        words = _words(row["provisional_segments"])
        entry = next(e for e in manifest["series"] if e["series"] == series_id)
        if entry["provisional_from"]:
            assert words.startswith("provisional"), (series_id, words)
        else:
            assert words == "none flagged", (series_id, words)
    steps = {s["id"]: s for s in reader["manual_steps"]}
    assert set(steps) == {s["id"] for s in manifest["manual_steps"]}
    for step in reader["manual_steps"]:
        for key in ("what", "why", "cost", "how"):
            text = step[key]
            for bad in engineering:
                assert bad not in text, (step["id"], key, bad)
            assert not any(w.isupper() and len(w) > 4 for w in text.replace(",", " ").replace(".", " ").split()), (step["id"], key)
    assert reader["manual_steps_heading"].rstrip(".").lower() not in reader["manual_steps_intro"].lower()
    # The DGEC printed monthly series names the months the ministry still marks provisional.
    printed = _words(reader["series"]["dgec_note_printed_monthly"]["provisional_segments"])
    assert "December 2025" in printed and "September 2026" in printed and "August 2026" not in printed
    # French names keep their accents on the page, escaped in the ASCII file.
    dgec = next(a for a in payload["attributions"] if a["id"] == "dgec")
    assert "é" in dgec["who"] and "ministère" in dgec["who"]
    # The two Brent rows say why both exist.
    assert reader["series"]["eia_brent_daily"]["label"] != reader["series"]["fred_brent_daily"]["label"]
    assert reader["series"]["eia_brent_daily"].get("gaps_reason")


def test_a_manifest_series_with_no_reader_label_fails_the_build(inputs):
    manifest = dict(inputs.manifest)
    manifest["series"] = list(manifest["series"]) + [{**manifest["series"][0], "series": "a_new_series"}]
    with pytest.raises(KeyError, match="a_new_series"):
        export.provenance_reader(manifest)


def test_the_waterfall_scale_is_said_in_whole_dollars_when_it_is_whole(built):
    """M4. The scale's ends are 1, 2, 5 ladder values; 0 to 50 is not said to the cent."""
    scale = built["margin-stack"]["scale"]
    formats = [s["format"] for s in scale["segments"] if "format" in s]
    assert formats == ["count", "count"]
    assert float(scale["low_usd_bbl"]).is_integer() and float(scale["high_usd_bbl"]).is_integer()


def test_utilisation_differences_print_to_the_places_of_utilisation(built):
    """M4. A difference of two figures printed to one place is printed to one place."""
    assert export.DECIMALS["pp"] == export.DECIMALS["percent"] == 1


def test_the_unidentified_paragraph_names_both_kinks(built):
    """M5. The sentence says where the kink is with and without the episode."""
    fields = [s.get("field") for s in built["run-economics"]["threshold"]["segments"]]
    assert "threshold_point_usd_bbl" in fields and "threshold_without_episode_usd_bbl" in fields


# ---------------------------------------------------------------------------
# history.json, docs/design.md Part 8.1
# ---------------------------------------------------------------------------


def test_history_panels_are_three_and_never_spliced(built):
    h = built["history"]
    monthly, margin, weekly = h["monthly"], h["margin"], h["weekly"]
    assert monthly["first"] == str(series.opec_monthly_cracks()["date"].min().date())
    assert margin["first"] == "2015-01-01", "the official margin starts in 2015-01 and is never extended back"
    assert weekly["first"] == "2022-07-01"
    weekly_cache = series.load("dgec_note_reconstructed_weekly")
    assert weekly["last"] == str(pd.to_datetime(weekly_cache["date"]).max().date())
    assert len(weekly["rows"]) == len(weekly_cache)
    # The wedge sits beside the margin: no column with gas taken off it.
    assert margin["columns"] == ["date", "mbr_usd_bbl", "gas_usd_mmbtu", "gas_wedge_usd_bbl"]
    stack = series.margin_after_gas_monthly()
    for row, (_, ref) in zip(margin["rows"], stack.iterrows()):
        assert row[1] == pytest.approx(ref["mbr_usd_bbl"], abs=1e-6)
        assert row[3] == pytest.approx(ref["gas_wedge_usd_bbl"], abs=1e-6)


def test_history_breaks_are_drawn_only_where_they_exist(built):
    breaks = built["history"]["breaks"]
    drawn = {(b["date"], b["line"]) for b in breaks if b["drawn"]}
    assert ("2015-04-01", "gas_wedge") in drawn
    assert ("2013-07-01", "gasoline") in drawn and ("2008-06-01", "gasoil") in drawn
    assert not any(b["line"] in ("mbr", "margin") for b in breaks)
    method = next(b for b in breaks if b["kind"] == "method_change")
    assert method["drawn"] is False and method["reason"]
    capacity = [b["date"] for b in breaks if b["kind"] == "capacity_step"]
    assert capacity == ["2017-01-01", "2026-01-01"]
    assert all(not b["drawn"] and "utilisation" in b["reason"] for b in breaks if b["kind"] == "capacity_step")
    assert "No break is drawn on the margin" in _words(built["history"]["margin"]["no_break_segments"])


def test_history_says_the_measured_findings(built):
    h = built["history"]
    join = h["weekly"]["join"]
    assert join["gasoil_mean_gap_usd_bbl"] == pytest.approx(0.92, abs=0.005)
    assert join["gasoline_mean_gap_usd_bbl"] == pytest.approx(-9.01, abs=0.005)
    assert h["monthly"]["r2"]["gasoil"] == pytest.approx(0.855, abs=5e-4)
    assert h["monthly"]["r2"]["gasoline"] == pytest.approx(0.551, abs=5e-4)
    panels = h["seasonal_monthly"]["panels"]
    gasoline = panels["gasoline"]["variants"]["all"]
    gasoil = panels["gasoil"]["variants"]["all"]
    assert gasoline["holds"] is True and gasoline["t"] == pytest.approx(4.64, abs=0.005)
    assert gasoil["holds"] is False and gasoil["t"] == pytest.approx(-0.59, abs=0.005)
    assert (gasoil["seasons_positive"], gasoil["seasons"]) == (10, 24)
    said = _words(gasoil["sentence_segments"])
    assert "does not firm into winter" in said and "October" in said and "November" in said
    assert panels["gasoil"]["episode_years_in_range"] == [2020, 2022]
    evidence = _words(h["weekly"]["evidence_segments"])
    assert "does not bound the oldest weeks" in evidence and "least defended" in evidence
    assert "starts in" in _words(h["sample_segments"])


def test_history_ranges_follow_one_rule(built):
    ranges = {r["id"]: r for r in built["history"]["ranges"]}
    assert list(ranges) == ["all", "weekly", "2020", "2022", "embargo_2023", "2026"]
    assert ranges["2022"]["start"] == "2021-08-01" and ranges["2022"]["end"] == "2023-01-31"
    assert ranges["weekly"]["start"] == "2022-07-01"
    for words in ("winner", "dead heat", " tie "):
        assert words not in export.serialise(built["history"]).lower()
