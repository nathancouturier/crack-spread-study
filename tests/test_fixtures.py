"""The parity fixture is what the CURRENT engine.py produces, byte for byte.

SPEC.md section 7.1 asks for two things: a fixture of at least 200 randomised
input sets carrying full Python output, and a validator that runs src/engine.js
against it under plain node. tools/validate-engine.mjs is the node half. This is
the Python half, and it exists because the node half cannot do this job.

The failure this file is here to catch
--------------------------------------
data/fixtures/engine-cases.json is COMMITTED rather than generated at gate time,
which is the right choice: it makes an engine change show up as a diff in the
cases it moved, which a reviewer can read. It has one failure mode, and it is
silent:

    somebody edits src/crack/engine.py, does not re-export the fixture, and the
    parity validator goes on comparing src/engine.js against a Python that no
    longer exists. Both sides pass. The gate is green over a check that stopped
    checking.

That is the same shape as every other thing this project keeps finding, and node
cannot see it: tools/validate-engine.mjs reads the fixture and engine.js and has
no way to ask engine.py anything. Only Python can. So these tests rebuild the
fixture from the seed the file itself records and compare bytes, and a Python
engine change that was never re-exported fails HERE, in the Python suite, before
it fails in node.

Byte idempotence, which is the other half of the same argument
--------------------------------------------------------------
"Regenerate and nothing changes" is only a real check if the generator is a
deterministic function of the engine and the seed. A wall clock timestamp, an
iteration over a set, an unseeded random draw, a locale dependent float repr,
any of those would make the file churn and the byte comparison above would
become noise everybody learns to rerun until it passes.

So the tests below regenerate the file three ways, in process, twice in a row,
and through the command line the way a person would run it, and assert the bytes
are identical every time. The command line run writes into a temporary
directory: it is the same code path with a different --out, and pointing it at
the repository to prove it would not damage the repository is not a trade this
file is willing to make. `--check` is the mode that makes the claim directly, it
exits 0 only when a rebuild matches the committed bytes, and it is asserted
rather than assumed.

What is NOT asserted here
-------------------------
Agreement with engine.js. That is node's job and this file must not duplicate
it, because a Python test that checked Python against Python would pass in
exactly the case SPEC.md section 7.1 cares about.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "data" / "fixtures" / "engine-cases.json"
GENERATOR = REPO_ROOT / "scripts" / "gen_fixtures.py"


def _load_generator():
    """Import scripts/gen_fixtures.py, which is a script rather than a module.

    It is not importable as crack.something and it should not be: it is a build
    step. Loading it by path keeps it where SPEC.md section 8 puts it and still
    lets these tests call build() and serialise() directly, which is what makes
    the byte comparison possible without shelling out for every assertion.
    """
    spec = importlib.util.spec_from_file_location("crack_gen_fixtures", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules["crack_gen_fixtures"] = module
    spec.loader.exec_module(module)
    return module


gen_fixtures = _load_generator()

from crack import config, engine  # noqa: E402


@pytest.fixture(scope="module")
def committed_bytes() -> bytes:
    if not FIXTURE.exists():
        pytest.fail(
            "data/fixtures/engine-cases.json is missing. It is a committed "
            "artifact, not a build output. Write it with: "
            "python scripts/gen_fixtures.py"
        )
    return FIXTURE.read_bytes()


@pytest.fixture(scope="module")
def committed_text(committed_bytes) -> str:
    return committed_bytes.decode("ascii")


@pytest.fixture(scope="module")
def committed(committed_text) -> dict:
    return json.loads(committed_text)


@pytest.fixture(scope="module")
def rebuilt_text() -> str:
    """The fixture rebuilt right now, from the engine that is on disk."""
    return gen_fixtures.serialise(gen_fixtures.build())


# ---------------------------------------------------------------------------
# The committed file is the current engine's output
# ---------------------------------------------------------------------------


def test_the_committed_fixture_is_what_the_current_engine_produces(
    committed_text, rebuilt_text
):
    """The whole point of this file.

    If this fails, either src/crack/engine.py moved and the fixture was not
    re-exported, or the fixture was hand edited. Both are the same repair:
    regenerate and read the diff.

    The message names the first line that differs and the case it belongs to,
    because "the bytes differ" on a file of this size is not something anybody
    can act on.
    """
    if committed_text == rebuilt_text:
        return

    committed_lines = committed_text.splitlines()
    rebuilt_lines = rebuilt_text.splitlines()
    first = None
    for index, (left, right) in enumerate(zip(committed_lines, rebuilt_lines)):
        if left != right:
            first = index
            break
    if first is None:
        pytest.fail(
            "the committed fixture has %d lines and a rebuild from the current "
            "src/crack/engine.py has %d. Regenerate and read the diff: "
            "python scripts/gen_fixtures.py"
            % (len(committed_lines), len(rebuilt_lines))
        )

    # Walk back to the nearest "name" key, which is how a case identifies itself
    # in this fixture's layout.
    name = "the header"
    for line in reversed(committed_lines[: first + 1]):
        stripped = line.strip()
        if stripped.startswith('"name":'):
            name = stripped.split(":", 1)[1].strip().strip(',').strip('"')
            break

    pytest.fail(
        "the committed fixture is NOT what src/crack/engine.py produces today. "
        "The first line that differs is line %d, in case %s.\n"
        "  committed  %s\n"
        "  rebuilt    %s\n"
        "If the engine changed on purpose, regenerate the fixture and read the "
        "diff: python scripts/gen_fixtures.py. If it did not, the fixture was "
        "edited by hand and the parity validator has been comparing "
        "src/engine.js against a Python that no longer exists."
        % (
            first + 1,
            name,
            committed_lines[first].strip()[:160],
            rebuilt_lines[first].strip()[:160],
        )
    )


def test_the_recorded_seed_is_the_one_the_generator_ships_with(committed):
    """A file built under some other seed is not reproducible from this repo."""
    assert committed["seed"] == gen_fixtures.SEED


def test_the_fixture_names_the_engine_and_the_mirror_it_stands_between(committed):
    """Both paths are asserted rather than trusted, and both must exist.

    tools/validate-engine.mjs refuses a fixture whose "mirror" is not
    src/engine.js. This is the other end of that: the file also has to name the
    Python it was built from, and that file has to be there.
    """
    assert committed["engine"] == "src/crack/engine.py"
    assert committed["mirror"] == "src/engine.js"
    assert committed["generator"] == "scripts/gen_fixtures.py"
    assert (REPO_ROOT / committed["engine"]).exists()
    assert (REPO_ROOT / committed["mirror"]).exists()
    assert (REPO_ROOT / committed["generator"]).exists()


def test_the_fixture_carries_the_tolerance_spec_7_1_sets(committed):
    """1e-9. The validator reads the bar out of the file rather than typing it,
    so the file is where it has to be correct."""
    assert committed["tolerance"] == 1e-9


# ---------------------------------------------------------------------------
# Byte idempotence
# ---------------------------------------------------------------------------


def test_two_rebuilds_in_one_process_are_byte_identical():
    """Nothing unseeded leaks in.

    A wall clock timestamp, an iteration over a set, or an unseeded random draw
    would fail here and nowhere else, because the comparison above would still
    pass on the run that wrote the file.
    """
    first = gen_fixtures.serialise(gen_fixtures.build())
    second = gen_fixtures.serialise(gen_fixtures.build())
    assert first == second


def test_a_fresh_interpreter_rebuilds_the_same_bytes(tmp_path, committed_bytes):
    """The command line path, run the way a person runs it, into a temp dir.

    A separate process is not redundant with the in process rebuild above. Hash
    randomisation, import order and the working directory are all per process,
    and any of them leaking into the output would show up here first.

    It writes to --out rather than to data/fixtures. The claim being tested is
    "regenerating an unchanged engine leaves the working tree clean", and
    writing into the working tree to prove that is the one experiment whose
    failure mode is the thing it is trying to rule out.
    """
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--out", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    written = (tmp_path / gen_fixtures.FILENAME).read_bytes()
    assert written == committed_bytes, (
        "a fresh interpreter rebuilt different bytes from the committed "
        "fixture. Regenerate with: python scripts/gen_fixtures.py"
    )


def test_check_mode_says_the_working_tree_would_stay_clean(capsys):
    """`gen_fixtures.py --check` is the assertion in one command.

    It rebuilds, compares against the committed bytes and exits 0 only when they
    match, which is exactly "regenerating would change nothing". It is the form
    the Makefile and, at Gate 5, the workflow will run, so it is tested here
    rather than assumed to work.
    """
    assert gen_fixtures.main(["--check"]) == 0
    assert "byte identical" in capsys.readouterr().out


def test_a_different_seed_produces_a_different_file():
    """The seed drives the randomised block rather than decorating it.

    Without this, a generator that recorded the seed and ignored it would pass
    every other test in this file.
    """
    original = gen_fixtures.SEED
    try:
        gen_fixtures.SEED = original + 1
        other = gen_fixtures.serialise(gen_fixtures.build())
    finally:
        gen_fixtures.SEED = original
    assert other != gen_fixtures.serialise(gen_fixtures.build())


# ---------------------------------------------------------------------------
# The file itself, as node has to read it
# ---------------------------------------------------------------------------


def test_the_fixture_is_ascii_lf_and_ends_with_exactly_one_newline(committed_bytes):
    """.gitattributes normalises to LF, so the committed file has to be LF.

    A CRLF fixture parses fine in node and is a different file on every
    checkout, which would make the byte comparison above fail on one platform
    and pass on another.
    """
    assert b"\r\n" not in committed_bytes, "the fixture has CRLF line endings"
    assert committed_bytes.endswith(b"\n")
    assert not committed_bytes.endswith(b"\n\n")
    committed_bytes.decode("ascii")


def test_the_fixture_carries_no_bare_nan_token(committed_text):
    """JSON has no NaN and JSON.parse refuses the token json.dump writes.

    A fixture with a bare NaN parses in Python, fails in node, and the parity
    validator then reports that it cannot read the file rather than that the
    engines disagree. The encoding is asserted here, on the side that writes it.
    """

    def refuse(constant):
        raise AssertionError(
            "the fixture contains the bare JSON token %s, which node cannot "
            "parse. A missing number is written as the string \"NaN\"" % constant
        )

    json.loads(committed_text, parse_constant=refuse)


def test_a_missing_number_and_an_absent_value_are_written_differently(committed):
    """SPEC.md section 2 rule 1. NaN is not null and null is not zero.

    This is the distinction the whole fixture format exists to preserve, and a
    generator that collapsed the two would still pass every byte comparison in
    this file. So both have to be present, and present for the right reasons: a
    "NaN" somewhere a measurement is missing, and a null somewhere a question
    has no answer.
    """
    saw_nan = False
    saw_null = False
    for case in committed["cases"]:
        expected = case["expected"]
        for value in expected.values():
            if value == "NaN":
                saw_nan = True
            if value is None:
                saw_null = True
        for name in ("contributions", "yields"):
            if isinstance(expected.get(name), dict):
                if any(v == "NaN" for v in expected[name].values()):
                    saw_nan = True
    assert saw_nan, "no case in the fixture carries a missing observation"
    assert saw_null, "no case in the fixture carries a question with no answer"


# ---------------------------------------------------------------------------
# Coverage, so a fixture cannot quietly stop testing a branch
# ---------------------------------------------------------------------------


def test_the_fixture_has_the_cases_spec_7_1_asks_for(committed):
    """At least 200 randomised input sets. The validator checks this too, and it
    is checked here as well because a fixture that fell short would otherwise
    only be caught by the tool it was supposed to feed."""
    assert committed["counts"]["randomised"] >= 200
    assert committed["counts"]["total"] == len(committed["cases"])
    randomised = [c for c in committed["cases"] if c["name"].startswith("random_")]
    assert len(randomised) == committed["counts"]["randomised"]


def test_every_case_kind_the_validator_runs_is_present(committed):
    """tools/validate-engine.mjs has a runner per kind and fails when a kind is
    absent. The same list, asserted from Python, so the two tools cannot drift
    into testing different halves of the engine."""
    kinds = {case["kind"] for case in committed["cases"]}
    assert kinds == {
        "crack",
        # The four kinds the Gate 2 self audit's findings 5 and 8 added, each
        # one reaching a divergence the 380 case fixture could not: a quote
        # value as JSON carries it, a crack leg that never went through
        # makeQuote, a set of margin inputs both engines must refuse, and the
        # gas wedge that replaced the gas subtraction finding 1 removed.
        "quote",
        "raw_crack",
        "margin",
        "margin_refusal",
        "gas_wedge",
        "decomposition",
        "replication",
        "yields",
        "percentile",
    }


def test_the_fixture_reaches_every_branch_the_generator_requires(committed):
    """gen_fixtures.build() refuses to write a fixture that lost a branch.

    That refusal runs at write time. This asserts the same thing about the file
    that is actually committed, which is what the validator will read, so a
    fixture written before a branch was added is caught too.
    """
    coverage = committed["coverage"]
    for name in gen_fixtures.REQUIRED_COVERAGE:
        assert coverage.get(name, 0) > 0, (
            "the committed fixture reaches no %s case, so nothing tests that "
            "branch in either engine" % name
        )


def test_every_margin_case_carries_every_line_of_the_margin(committed):
    """SPEC.md section 7.1: "full Python output, every contribution line
    included". A fixture that dropped a field would make the validator silently
    stop comparing it."""
    required = {
        "contributions",
        "attributed_usd_bbl",
        "residual_usd_bbl",
        "gross_margin_usd_bbl",
        "gas_usd_mmbtu",
        "gas_cost_usd_bbl",
        "other_variable_cost_usd_bbl",
        "margin_after_gas_usd_bbl",
        "carrier",
        "carrier_contribution_usd_bbl",
        "threshold_identified",
        "headroom_usd_bbl",
        "gas_basis",
        "breakeven_ttf_eur_mwh",
        "breakeven_gas_usd_mmbtu",
        "breakeven_gasoil_usd_bbl",
        "percentile_10y",
        "percentile_observations",
        # Added with schema 2. The margin basis says whether the gas purchase is
        # already inside the margin, and the window says what the percentile was
        # ranked over. Gate 2 self audit, findings 1 and 11.
        "margin_basis",
        "gas_already_in_margin",
        "run_cut_threshold_usd_bbl",
        "percentile_window_months",
    }
    for case in committed["cases"]:
        if case["kind"] != "margin":
            continue
        missing = required - set(case["expected"])
        assert not missing, (case["name"], sorted(missing))
        assert set(case["expected"]["contributions"]) == set(case["inputs"]["yields"])
        assert case["inputs"]["margin_basis"] in ("gross_of_gas", "net_of_gas")


def test_the_fixture_carries_the_values_json_puts_where_a_price_should_be(committed):
    """Gate 2 self audit, finding 8 rows 1 to 3, as a property of the file.

    null, an empty string and a string of digits are what a JSON artifact
    actually carries when a price is missing or was written by something that
    stringified it. Number(null) is 0, so before this the browser cracked a
    0 $/bbl price where the pipeline refused. These cases only test anything if
    the raw value survives into the file undecoded, so that is what is asserted:
    the value_json field holds the JSON value itself, not an encoding of it.
    """
    quotes = {case["name"]: case for case in committed["cases"] if case["kind"] == "quote"}
    assert quotes, "the fixture reaches no quote case at all"

    refused = {
        "quote_value_null_is_refused": None,
        "quote_value_empty_string_is_refused": "",
        "quote_value_string_of_digits_is_refused": "83.73",
        "quote_value_boolean_is_refused": True,
    }
    for name, raw in refused.items():
        case = quotes[name]
        assert case["value_json"] == raw and type(case["value_json"]) is type(raw)
        assert case["expected"]["error"] == "UnitError"

    accepted = quotes["quote_value_number_is_accepted"]
    assert accepted["value_json"] == 94.62
    assert accepted["expected"]["error"] is None
    assert accepted["expected"]["value"] == 94.62


def test_the_fixture_reaches_a_crack_leg_that_never_went_through_a_quote(committed):
    """Gate 2 self audit, finding 5. A leg with no window is refused by both.

    The legs in these cases are bare objects carrying only the fields named, so
    a leg with no window really has none, which is what a row read out of a JSON
    artifact looks like. undefined !== undefined is false, so before this the
    browser cracked them and returned 71.97.
    """
    raw = {case["name"]: case for case in committed["cases"] if case["kind"] == "raw_crack"}
    assert raw["raw_legs_with_no_window"]["expected"]["error"] == "AlignmentError"
    assert "window" not in raw["raw_legs_with_no_window"]["product"]
    assert raw["raw_legs_with_no_date_and_no_window"]["expected"]["error"] == (
        "AlignmentError"
    )
    assert raw["raw_product_leg_with_no_date"]["expected"]["error"] == "AlignmentError"
    # And a bare leg that carries everything is still a crack, in both engines.
    complete = raw["raw_legs_that_carry_everything"]
    assert complete["expected"]["error"] is None
    # 94.62 minus 80.0, which is 14.620000000000005 in doubles and is written to
    # the file as that rather than rounded. Nothing in this repository rounds a
    # number to make a comparison look tidier.
    assert complete["expected"]["value"] == pytest.approx(14.62, abs=1e-12)


def test_the_fixture_makes_the_gas_double_count_a_refusal_in_both_engines(committed):
    """Finding 1, mirrored. A gas price on a net of gas margin is refused.

    The margin the site opens on is DGEC's published MBR, which is already net
    of the gas the method assumes the refinery buys. The fixture carried no such
    margin at all until schema 2, so the browser's copy of the rule was never
    checked against Python's.
    """
    refusals = {
        case["name"]: case
        for case in committed["cases"]
        if case["kind"] == "margin_refusal"
    }
    double_count = refusals["a_gas_price_on_a_margin_that_already_contains_one"]
    assert double_count["expected"]["error"] == "GasDoubleCountError"
    assert double_count["inputs"]["margin_basis"] == "net_of_gas"

    net = [
        case
        for case in committed["cases"]
        if case["kind"] == "margin"
        and case["expected"]["margin_basis"] == "net_of_gas"
    ]
    assert net, "no net of gas margin in the fixture"
    for case in net:
        # The gas line is zero and the margin is the margin, not the margin
        # minus a gas cost.
        assert case["expected"]["gas_cost_usd_bbl"] == 0.0
        assert case["expected"]["gas_already_in_margin"] is True


def test_every_decomposition_case_carries_the_residual_line(committed):
    """SPEC.md section 4.3 layer 3: the residual is always shown and never
    spread across products. Every case in the fixture carries it, including the
    ones where it is zero, so the validator compares it every time."""
    for case in committed["cases"]:
        if case["kind"] != "decomposition":
            continue
        assert "residual_usd_bbl" in case["expected"], case["name"]
        assert "attributed_usd_bbl" in case["expected"], case["name"]
        assert "residual_share" in case["expected"], case["name"]


def test_the_unit_constants_in_the_fixture_are_the_configured_ones(committed):
    """The Units row of SPEC.md section 9, reached through the fixture.

    745 $/t of gasoil against Brent 80 is exactly 20 and 833 $/t of gasoline
    against the same Brent is exactly 20. tests/test_units.py asserts that of
    engine.py and the validator asserts it of engine.js. This asserts the
    fixture's converted crack cases were built with the same two factors, so a
    changed factor cannot pass through the file unnoticed.
    """
    assert config.BBL_PER_T_GASOIL == 7.45
    assert config.BBL_PER_T_GASOLINE == 8.33
    assert engine.crack_from_usd_t(745.0, config.BBL_PER_T_GASOIL, 80.0) == 20.0
    assert engine.crack_from_usd_t(833.0, config.BBL_PER_T_GASOLINE, 80.0) == 20.0

    seen = set()
    for case in committed["cases"]:
        if case["kind"] != "crack":
            continue
        factor = case.get("product_bbl_per_t")
        if isinstance(factor, (int, float)):
            seen.add(float(factor))
    assert config.BBL_PER_T_GASOIL in seen
    assert config.BBL_PER_T_GASOLINE in seen
