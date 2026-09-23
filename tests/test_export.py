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

import ast
import json
import math
import re
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
    assert list(built) == ["now", "cracks", "margin-stack", "run-economics", "provenance", "history", "model", "runs", "events", "method"]
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
        "was 38.050505 $/bbl in August 2026, or 34.962813 at this study's gas use, "
        "the most in 120 months; gasoil carried 26.996621 of it, "
        "and this sample cannot say whether runs have room to rise."
    )
    # SPEC.md section 7.2, said out loud: the month once, and still short enough
    # to say. Gate 5 finding 9: both gas figures, the ministry's allowance and
    # this study's intensity, are in the sentence a trader reads out loud, and
    # the ratio between them is not (docs/design.md Part 7, C9 and C16).
    assert words.count("August 2026") == 1
    fields = [s["field"] for s in built["now"]["verdict"]["segments"] if "field" in s]
    assert "margin_study_intensity_usd_bbl" in fields
    assert "intensity_ratio" not in fields
    assert len(words.split()) <= 47
    # The ratio and the wedge stay in the section where the wedge is drawn.
    moved = {s["field"] for s in built["margin-stack"]["study_margin_segments"] if "field" in s}
    assert {"margin_study_intensity_usd_bbl", "intensity_ratio", "gas_wedge_usd_bbl"} <= moved
    for banned in ("clears zero", "a coin", "SPEC", "product prices", "Rotterdam refiners made", "winner"):
        for payload in built.values():
            for _, segments in _segment_lists(payload):
                for s in segments:
                    assert banned not in s.get("text", ""), banned


# ---------------------------------------------------------------------------
# Gate 5 finding 4, generalised: a count and the noun after it
# ---------------------------------------------------------------------------

#: Words that end in "s" and are not plural nouns, so a count may sit in front
#: of them. Verbs agree with the count through their own {singular|plural}
#: alternative where they need to; these are the ones that never move.
_NOT_A_PLURAL_NOUN = frozenset(
    """is was has as less plus minus across this its thus always perhaps
    uses sits runs says holds does goes stops reads carries means gives
    leaves falls leads""".split()
)
#: "Series" is the same word in both numbers, so "1 series" is already right.
_INVARIANT_NOUNS = frozenset({"series"})
#: "1 weeks", "1 months", "1 years", "1 notes" and their kin.
_COUNT_THEN_PLURAL = re.compile(r"\b1 ([a-z]+s)\b")


def _looks_plural(word: str) -> bool:
    word = word.lower()
    return word.endswith("s") and word not in _NOT_A_PLURAL_NOUN and word not in _INVARIANT_NOUNS


def test_plural_puts_the_words_after_a_count_in_the_count_s_number():
    assert export._plural(1, " {week|weeks} from ") == " week from "
    assert export._plural(2, " {week|weeks} from ") == " weeks from "
    assert export._plural(0, " {week|weeks} from ") == " weeks from "
    assert export._plural(1, " {month has|months have} runs data") == " month has runs data"
    assert export._plural(7, " {month has|months have} runs data") == " months have runs data"
    assert export._plural(1, " no alternative here") == " no alternative here"


def test_no_exported_sentence_reads_one_of_a_plural(built):
    """Gate 5 finding 4. The weekly caption read "the 1 weeks from 18 September
    2026". This fails on that and on "1 months", "1 years", "1 notes" and their
    kin, wherever a sentence in any artifact is assembled."""
    problems = []
    for name, payload in built.items():
        for where, segments in _segment_lists(payload):
            words = _words(segments)
            for match in _COUNT_THEN_PLURAL.finditer(words):
                if _looks_plural(match.group(1)):
                    problems.append((name, where, match.group(0)))
    assert problems == []


def test_every_count_in_the_export_is_followed_by_a_noun_that_can_be_singular():
    """The same finding held at the cause rather than at today's data.

    A count is data: it moves, and a sentence written while it was nineteen
    reads "the 1 weeks" the week it becomes one. This reads the syntax tree of
    src/crack/export.py and fails when a count segment is followed by a literal
    text segment whose first word is a plural noun, whether or not today's
    build happens to make that count one. The fix is _plural, whose
    {singular|plural} alternatives are not literals and so pass here.
    """
    source = (REPO_ROOT / "src" / "crack" / "export.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    def called(node):
        return node.func.id if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else None

    problems = []
    for node in ast.walk(tree):
        sequences = []
        if isinstance(node, (ast.List, ast.Tuple)):
            sequences.append(node.elts)
        if isinstance(node, ast.Call):
            sequences.append(node.args)
        for sequence in sequences:
            for first, second in zip(sequence, sequence[1:]):
                if called(first) != "N" or len(first.args) < 3:
                    continue
                fmt = first.args[2]
                if not (isinstance(fmt, ast.Constant) and fmt.value in export.INTEGER_FORMATS):
                    continue
                if called(second) != "T" or len(second.args) != 1:
                    continue
                text = second.args[0]
                if not (isinstance(text, ast.Constant) and isinstance(text.value, str)):
                    continue  # _plural, or anything else computed: not a literal
                word = re.match(r"\s*([A-Za-z]+)", text.value)
                if word and _looks_plural(word.group(1)):
                    problems.append("line %d: %r" % (text.lineno, text.value[:60]))
    assert problems == [], (
        "a count is pasted in front of a plural noun; wrap the words in "
        "_plural(count, \" {singular|plural} ...\"):\n" + "\n".join(problems)
    )


def test_the_verdict_carries_both_gas_figures_and_a_rank_true_of_both(built):
    """Gate 5 finding 9. The landing sentence used to answer "after gas" on the
    ministry's 0.0659 MMBtu/bbl allowance only, which is 3.09 $/bbl more
    favourable than the figure every equation on the Runs view uses. Both are
    now in the sentence, and the rank clause that follows them is true of both
    or says whose measure it ranks."""
    values = built["now"]["verdict"]["values"]
    segments = built["now"]["verdict"]["segments"]
    spoken = _words(segments)

    # The two figures in the sentence are the two the study defines, and the
    # study's is the lower one: it buys more gas per barrel.
    assert values["margin_study_intensity_usd_bbl"] < values["mbr_usd_bbl"]
    assert values["study_gas_intensity_mmbtu_per_bbl"] > values["net_of"]["embedded_gas_intensity_mmbtu_per_bbl"]
    numbers = [s for s in segments if s.get("format") == "usd_bbl"]
    assert [s["field"] for s in numbers][:2] == ["mbr_usd_bbl", "margin_study_intensity_usd_bbl"]
    assert "at this study's gas use" in spoken
    # The gap between them is the wedge, and it is said where the wedge is drawn.
    gap = values["mbr_usd_bbl"] - values["margin_study_intensity_usd_bbl"]
    # Both sides are stored to six places, so the tolerance is on that rounding.
    assert abs(gap - values["gas_wedge_usd_bbl"]) < 1e-5

    # The rank clause sits after both figures, so it has to hold on both.
    assert values["percentile_rank_study_intensity"] == values["percentile_rank"], (
        "the two measures rank the latest month differently, so the verdict's "
        "rank clause must name whose measure it ranks"
    )
    assert values["percentile_observations_study_intensity"] == values["percentile_observations"]
    assert values["percentile_ranks_agree"] is True
    assert "on the ministry's measure" not in spoken

    # And the rank is what it claims to be, recomputed here from the rows the
    # History view draws rather than from the exporter's own helper.
    margin = built["history"]["margin"]
    columns = margin["columns"]
    rows = [dict(zip(columns, row)) for row in margin["rows"]]
    window = [
        row for row in rows
        if values["percentile_window_first_month"] <= row["date"] <= values["percentile_window_last_month"]
    ]
    official = [row["mbr_usd_bbl"] for row in window if row["mbr_usd_bbl"] is not None]
    study = [
        row["mbr_usd_bbl"] - row["gas_wedge_usd_bbl"]
        for row in window
        if row["mbr_usd_bbl"] is not None and row["gas_wedge_usd_bbl"] is not None
    ]
    assert len(official) == values["percentile_observations"]
    assert len(study) == values["percentile_observations_study_intensity"]
    assert sum(1 for x in official if x <= values["mbr_usd_bbl"]) == values["percentile_rank"]
    # The study's measure is a difference of two rows each stored to six places,
    # so the comparison carries that rounding.
    assert sum(
        1 for x in study if x <= values["margin_study_intensity_usd_bbl"] + 1e-5
    ) == values["percentile_rank_study_intensity"]


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


# ---------------------------------------------------------------------------
# runs.json, docs/design.md Part 8.3
# ---------------------------------------------------------------------------

BANNED_RACE_WORDS = ("winner", " wins", "best", " tie", "dead heat", "equivalent")


def test_runs_title_is_the_response_on_both_equations_planned_first(built, inputs):
    r = built["runs"]
    fields = [s.get("field") for s in r["title_segments"] if "field" in s]
    assert fields.index("kb_d") < fields.index("fallback_kb_d")
    values = {s["field"]: s["value"] for s in r["title_segments"] if "field" in s}
    assert values["kb_d"] == pytest.approx(59.3, abs=0.05)
    assert values["kb_d_low"] == pytest.approx(-290.1, abs=0.05) and values["kb_d_high"] == pytest.approx(408.8, abs=0.05)
    assert values["fallback_kb_d"] == pytest.approx(230.4, abs=0.05)
    assert values["fallback_kb_d_low"] == pytest.approx(5.1, abs=0.05) and values["fallback_kb_d_high"] == pytest.approx(455.6, abs=0.05)


def test_runs_scatter_is_the_threshold_sample_and_both_fits(built, inputs):
    t = built["runs"]["threshold"]
    th, wo = inputs.threshold, inputs.threshold_without_stretch
    assert len(t["rows"]) == th.nobs
    assert sum(1 for row in t["rows"] if row[4]) == len(th.months_below) == 24
    assert sum(1 for row in t["rows"] if row[3]) == th.longest_run_below == 21
    stretch = [row[0] for row in t["rows"] if row[3]]
    assert stretch[0] == "2020-07-01" and stretch[-1] == "2022-03-01"
    every, without = t["fits"]
    assert every["kink_usd_bbl"] == pytest.approx(2.28, abs=0.005)
    assert every["slope_below"] == pytest.approx(3.88, abs=0.005)
    assert without["kink_usd_bbl"] == pytest.approx(9.87, abs=0.005)
    assert without["slope_below"] == pytest.approx(-0.50, abs=0.005)
    assert without["months"] == wo.nobs == 114
    # The line is the fitted kink evaluated at its own vertices.
    for fit, result in ((every, th), (without, wo)):
        for x, y in fit["line"]:
            expected = result.point.level - result.point.slope_below * max(result.point.threshold - x, 0.0)
            assert y == pytest.approx(expected, abs=1e-5)
    interval = t["interval"]
    assert interval["high_usd_bbl"] == interval["search_high_usd_bbl"], "the interval reaches the edge and is not trimmed"
    assert interval["reaches_search_edge"] is True and interval["trimmed"] is False


def test_threshold_sample_is_what_the_threshold_searched(inputs):
    sample = analysis.threshold_sample(inputs.frame)
    th = inputs.threshold
    assert len(sample) == th.nobs
    assert sample["margin_mean_lagged"].min() == pytest.approx(th.regressor_min)
    assert sample["margin_mean_lagged"].max() == pytest.approx(th.regressor_max)


def test_runs_race_cannot_tell_the_horses_apart_and_ranks_nothing(built):
    race = built["runs"]["race"]
    assert race["any_distinguishable"] is False
    powers = [p["power"] for eq in race["equations"] for p in eq["pairs"]]
    assert len(powers) == 6
    assert min(powers) == pytest.approx(0.050, abs=5e-4) and max(powers) == pytest.approx(0.121, abs=5e-4)
    assert race["size"] == 0.05
    for eq in race["equations"]:
        assert [h["key"] for h in eq["horses"]] == ["A", "B", "C"], "fixed order, never sorted"
        assert [h["substitution"] for h in eq["horses"]] == [False, False, True]
        assert eq["long_sample"]["in_the_race"] is False and eq["long_sample"]["months"] == 288
        assert all(not p["distinguishable"] for p in eq["pairs"])
    said = _words(race["sentence_segments"]).lower()
    assert "cannot tell the horses apart" in said
    honest = _words(race["margin_against_crack_segments"])
    assert "did not beat it and was not beaten by it" in honest and "power, not equality" in honest
    text = export.serialise(built["runs"]).lower()
    for word in BANNED_RACE_WORDS:
        assert word not in text, word


def test_runs_instrument_ladder_is_a_property_of_the_control_set(built):
    inst = built["runs"]["instrument"]
    fs = [rung["f"] for rung in inst["ladder"]]
    assert fs == pytest.approx([5.753, 5.802, 0.215, 0.070], abs=5e-4)
    assert inst["ladder"][2]["used_by"] == ["Utilisation of capacity, the planned model"]
    assert inst["ladder"][3]["used_by"] == ["Crude intake with a trend"]
    assert all(eq["weak"] and eq["iv_used"] is False for eq in inst["equations"])
    assert "shock they remove" in _words(inst["diagnosis_segments"])


def test_runs_response_is_a_lower_bound_and_imports_are_arithmetic(built):
    r = built["runs"]
    assert "lower bound in absolute value" in _words(r["endogeneity_segments"])
    imports = r["series"]["imports"]
    assert imports["is_a_model"] is False
    assert imports["mean_imports_over_intake"] == pytest.approx(0.954, abs=5e-4)
    assert "not a second model" in _words(imports["segments"])
    variants = [(row["model"], row["variant"]) for row in r["episodes"]["rows"]]
    assert variants[0] == ("capacity", "episodes") and ("intake_trend", "dropped") in variants


def test_runs_series_starts_with_the_margin_and_says_so(built):
    s = built["runs"]["series"]
    assert s["first"] == "2015-01-01" and s["last"] == "2026-06-01"
    assert s["capacity_steps"] == ["2017-01-01", "2026-01-01"]
    assert s["rows"][-1][-1] is True, "June 2026 is provisional"
    last_year = [row for row in s["rows"] if row[0].startswith("2026")]
    assert all(row[6] == 2025 and row[7] is False for row in last_year), "2026 uses the 2025 year end capacity, no assumption"
    words = _words(s["sample_segments"])
    assert "starts in" in words and "nothing extends the margin back" in words


def test_runs_break_is_not_tested_and_never_joined(built, inputs):
    b = built["runs"]["break"]
    assert b["tested"] is False and b["n_post"] == 4 and b["min_post_months"] == 12
    assert b["pre_rows"][-1][0] == "2026-02-01" and b["post_rows"][0][0] == "2026-03-01"
    assert len(b["pre_rows"]) == inputs.break_result.n_pre
    assert [x["id"] for x in b["brackets"]] == ["episode_2022", "after_break"]
    assert b["brackets"][0]["start"] == "2022-02-01" and b["brackets"][0]["end"] == "2023-01-01"


# ---------------------------------------------------------------------------
# events.json, docs/design.md Part 8.4
# ---------------------------------------------------------------------------


def test_events_are_the_market_policy_and_reference_entries_each_with_a_source(built):
    e = built["events"]
    ids = [ev["id"] for ev in e["events"]]
    assert len(ids) == 10
    assert ids == sorted(ids, key=lambda i: next(ev["date"] for ev in e["events"] if ev["id"] == i))
    for ev in e["events"]:
        assert ev["kind"] in ("market", "policy", "reference")
        assert ev["source_url"].startswith("https://")
    assert len(e["not_panels"]) == 11


def test_the_stock_release_keeps_the_day_the_source_pins(built):
    ev = next(ev for ev in built["events"]["events"] if ev["id"] == "iea_collective_action_400_mb_2026_03_11")
    assert ev["date"] == "2026-03-11" and ev["precision"] == "day" and ev["label"] == "11 March 2026"
    lock = next(ev for ev in built["events"]["events"] if ev["id"].startswith("covid"))
    assert lock["precision"] == "month" and lock["label"] == "March 2020"


def test_every_window_is_thirteen_months_and_never_filled(built, inputs):
    e = built["events"]
    cols = e["monthly_columns"]
    margin = inputs.margin.set_index("date")
    for ev in e["events"]:
        assert [row[cols.index("offset_months")] for row in ev["rows"]] == list(range(-6, 7))
        for row in ev["rows"]:
            stamp = pd.Timestamp(row[0])
            mbr = row[cols.index("mbr_usd_bbl")]
            if stamp in margin.index:
                assert mbr == pytest.approx(margin.at[stamp, "mbr_usd_bbl"], abs=1e-6)
            else:
                assert mbr is None
            if row[cols.index("utilisation_percent")] is None:
                assert row[cols.index("utilisation_provisional")] is None


def test_a_window_past_the_data_names_every_missing_series(built):
    ev = next(ev for ev in built["events"]["events"] if ev["id"] == "us_iran_ceasefire_2026_04_07")
    missing = {m["series"]: "".join(s.get("text", s.get("label", "")) for s in m["segments"]) for m in ev["missing"]}
    assert set(missing) == {"monthly_cracks", "margin", "utilisation", "weekly"}
    assert "stops at February 2026" in missing["monthly_cracks"]
    assert "after the latest data" in missing["margin"]
    lock = next(ev for ev in built["events"]["events"] if ev["id"].startswith("covid"))
    assert [m["series"] for m in lock["missing"]] == ["weekly"] and lock["weekly_rows"] == []


def test_events_margin_is_never_net_of_gas_twice(built, inputs):
    e = built["events"]
    cols = e["monthly_columns"]
    frame = inputs.margin.set_index("date")
    ev = next(ev for ev in e["events"] if ev["id"].startswith("strikes_on_iran"))
    for row in ev["rows"]:
        stamp = pd.Timestamp(row[0])
        if stamp in frame.index:
            assert row[cols.index("margin_us_gas_usd_bbl")] == pytest.approx(frame.at[stamp, "mbr_usd_bbl"] - frame.at[stamp, "gas_wedge_usd_bbl"], abs=1e-5)
    assert ev["capacity_steps"] == ["2026-01-01"]


# ---------------------------------------------------------------------------
# method.json, docs/design.md Part 8.5
# ---------------------------------------------------------------------------


def _method_values(built):
    out = {}
    def walk(value):
        if isinstance(value, dict):
            if "field" in value and "value" in value:
                out.setdefault(value["field"], value["value"])
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(built["method"])
    return out


def test_method_carries_the_measured_cross_checks(built):
    v = _method_values(built)
    assert v["brent_months_within"] == v["brent_months"] == 140
    assert v["mbr_anchors_reproduced"] == v["mbr_anchors"] == 9
    assert v["triangulation_gap_usd_bbl"] == pytest.approx(6.23, abs=0.005)
    assert v["triangulation_variant_usd_bbl"] == pytest.approx(5.51, abs=0.005)
    assert v["implied_gasoil_mean"] == pytest.approx(7.528, abs=0.001)
    assert v["implied_gasoline_mean"] == pytest.approx(7.718, abs=0.001)
    assert v["implied_months"] == 44
    assert v["brent_prints_below_ten"] == 25
    assert v["study_intensity"] == config.GAS_INTENSITY_MMBTU_PER_BBL
    assert v["ministry_intensity"] == pytest.approx(0.0659, abs=5e-5)


def test_method_names_every_unpublished_input(built):
    text = json.dumps(built["method"])
    for key in config.DGEC_UNPUBLISHED_METHOD_INPUTS:
        assert export.METHOD_UNPUBLISHED_WORDS[key][1] in text
    v = _method_values(built)
    assert v["unpublished_quotations"] == 5 and v["method_products"] == 10


def test_method_cites_every_factor_and_reads_the_orphans(built):
    assumptions = next(s for s in built["method"]["sections"] if s["id"] == "assumptions")
    table = assumptions["blocks"][0]
    urls = {cell["url"] for row in table["rows"] for cell in row if "url" in cell}
    for citation in export.FACTOR_CITATIONS.values():
        assert citation["url"] in urls
    reads = {b["what"] for s in built["method"]["sections"] for b in s["blocks"] if b["type"] == "reads"}
    assert {"margin_stack_prices", "response_diagnostics", "reuse"} <= reads
    for row in built["margin-stack"]["rows"]:
        if "price_usd_t" in row:
            assert row["factor_citation"]["url"].startswith("https://www.ice.com/")
    for model in built["run-economics"]["response"]["models"]:
        assert model["newey_west_lag"] >= analysis.NEWEY_WEST_MIN_LAG and 0 <= model["r2"] <= 1


# ---------------------------------------------------------------------------
# SPEC.md section 4.3 layer 4, observed yields. Gate 5 finding 3.
# ---------------------------------------------------------------------------
#
# The layer was computed in crack.engine and crack.series, defined in words on
# the Method view, exported by no artifact and drawn by no view: a layer the
# specification requires "visible on the site" and that a reader could not
# reach. These three tests hold the arithmetic, the artifact and the view, and
# the third is the one that would have caught the finding.


def test_the_observed_yield_margins_are_the_same_cracks_weighted_twice():
    """Layer 4 against layer 3: only the yields differ between the columns.

    Recomputed here from the cracks and the yields by hand, so the test fails
    if crack.series stops using the yields it says it uses, or weights a crack
    from another month.
    """
    frame = series.observed_yield_margins()
    fixed = series.DGEC_VOLUME_YIELDS
    row = frame[frame["crude_intake_usd_bbl"].notna()].iloc[-1]
    by_hand = (
        fixed["gasoil"] * row["crack_gasoil_usd_bbl"]
        + fixed["gasoline"] * row["crack_gasoline_usd_bbl"]
    )
    assert row["fixed_usd_bbl"] == pytest.approx(by_hand, abs=1e-9)
    for basis in (config.YIELD_BASIS_CRUDE_INTAKE, config.YIELD_BASIS_TOTAL_FEED):
        observed = (
            row["%s_gasoil" % basis] * row["crack_gasoil_usd_bbl"]
            + row["%s_gasoline" % basis] * row["crack_gasoline_usd_bbl"]
        )
        assert row["%s_usd_bbl" % basis] == pytest.approx(observed, abs=1e-9)
        # The yields are the ones crack.series.jodi_yields publishes for that
        # month, not a second rolling window computed here.
        published = series.jodi_yields(basis)
        published = published[published["date"] == row["date"]].iloc[0]
        assert row["%s_gasoil" % basis] == pytest.approx(published["gasoil"], abs=1e-12)
        assert row["%s_gasoline" % basis] == pytest.approx(published["gasoline"], abs=1e-12)
    # The denominator is a choice and both answers exist, with the coverage
    # each one costs: crude intake reaches back further, total feed starts
    # where JODI's TOTCRUDE does.
    crude = frame[frame["crude_intake_usd_bbl"].notna()]["date"]
    feed = frame[frame["total_feed_usd_bbl"].notna()]["date"]
    assert crude.min() < feed.min()
    assert str(feed.min().date()) == "2009-12-01"


def test_the_observed_yield_layer_is_exported_with_both_denominators(built):
    """The artifact carries the layer, and says which barrel each yield is of.

    SPEC.md section 4.3 layer 4 names both the computation and the comparison,
    so the block has to hold the fixed slate, both observed bases and a row per
    month; and config says both bases are shown rather than one chosen.
    """
    block = built["history"]["yields"]
    frame = series.observed_yield_margins()
    assert [b["id"] for b in block["bases"]] == [
        config.YIELD_BASIS_CRUDE_INTAKE,
        config.YIELD_BASIS_TOTAL_FEED,
    ]
    assert block["fixed"]["fixed_gasoil_percent"] == pytest.approx(
        100 * series.DGEC_VOLUME_YIELDS["gasoil"], abs=1e-6
    )
    assert len(block["rows"]) == len(frame)
    column = block["columns"].index
    for row, (_, ref) in zip(block["rows"], frame.iterrows()):
        assert row[column("fixed_usd_bbl")] == pytest.approx(ref["fixed_usd_bbl"], abs=1e-6)
        for basis in (config.YIELD_BASIS_CRUDE_INTAKE, config.YIELD_BASIS_TOTAL_FEED):
            exported = row[column("%s_usd_bbl" % basis)]
            reference = ref["%s_usd_bbl" % basis]
            if exported is None:
                assert math.isnan(reference)
            else:
                assert exported == pytest.approx(reference, abs=1e-6)
    # The observed yields are higher than the slate's on both bases, which is
    # the finding this panel reports, and it is reported whatever it is.
    for basis in block["bases"]:
        assert basis["gasoil_low_percent"] > block["fixed"]["fixed_gasoil_percent"]
        assert basis["mean_gap_usd_bbl"] > 0


def test_every_layer_of_section_4_3_reaches_a_view(built):
    """The Gate 5 finding, as a test: computed is not the same as shown.

    Each of the four layers has to be reachable by a reader, so each is checked
    the way a reader meets it: a figure in an artifact AND a module that reads
    the block it sits in. The fourth failed both halves until Gate 5.
    """
    src = REPO_ROOT / "src"
    modules = {path.name: path.read_text(encoding="utf-8") for path in src.glob("*.js")}
    layers = {
        "1 official margin": ("history", "margin", "history.js"),
        "2 replication": ("method", "sections", "method.js"),
        "3 decomposition": ("margin-stack", "rows", "section-margin.js"),
        "4 observed yields": ("history", "yields", "history.js"),
    }
    for layer, (artifact, key, module) in layers.items():
        assert key in built[artifact], "%s is in no artifact" % layer
        assert key in modules[module], "%s is in no view: %s never reads it" % (layer, module)
    # And the fourth layer's own comparison, which is what SPEC.md asks for:
    # the margin at observed yields beside the margin at the fixed slate.
    yields = built["history"]["yields"]
    assert "fixed_usd_bbl" in yields["columns"]
    assert any(b["id"] + "_usd_bbl" in yields["columns"] for b in yields["bases"])
