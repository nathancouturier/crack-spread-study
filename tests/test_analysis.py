"""SPEC.md sections 6.1 and 6.2: does the estimator do what it claims.

The five tests the Gate 3 brief asks for by name are the five headings below.
Each one is written so that it fails for the reason it is named after and not for
some other reason, which means the synthetic tests use data this module made up
and the real data tests only check properties that cannot be tuned into
existence.

A NOTE ON WHAT THESE DO NOT TEST. No test here asserts that a coefficient on the
real data has a particular value or a particular sign. SPEC.md section 2 rule 3
says report the result whatever it is and rule 4 says the study is allowed to
find nothing. A test that pinned a coefficient would turn the next data refresh
into a failing build for the crime of the world having moved, and, worse, would
be the thing that makes somebody tune the estimator. The real data tests check
sample sizes, units, reproducibility and arithmetic.
"""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from crack import analysis

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Synthetic data with a known answer
# ---------------------------------------------------------------------------


def synthetic_response(
    nobs: int = 400,
    planted: tuple[float, float, float] = (0.30, 0.20, 0.10),
    seed: int = 7,
) -> pd.DataFrame:
    """A frame shaped like analysis_frame with a coefficient we chose ourselves.

    The margin is a persistent AR(1) so the regressor looks like the real one,
    the dependent is built from the planted lag coefficients plus a seasonal
    pattern plus noise, and nothing else is in it. If the estimator cannot find
    the number that was put in here, the number it reports on the real data means
    nothing.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2000-01-01", periods=nobs, freq="MS")
    margin = np.zeros(nobs)
    for t in range(1, nobs):
        margin[t] = 0.85 * margin[t - 1] + rng.normal(0.0, 2.0)
    margin = margin + 8.0

    seasonal = np.array([1.5 * math.sin(2 * math.pi * d.month / 12.0) for d in dates])
    y = np.full(nobs, 80.0) + seasonal + rng.normal(0.0, 0.5, nobs)
    for k, b in zip((1, 2, 3), planted):
        y[3:] += b * margin[3 - k : nobs - k]

    return pd.DataFrame(
        {
            "date": dates,
            "utilisation_pct": y,
            "intake_kb_d": 5000.0 + 10.0 * y,
            "imports_kb_d": 4800.0 + 9.0 * y,
            "capacity_kb_d": 6000.0,
            "capacity_assumed": False,
            "log_intake_pct": 100.0 * np.log(5000.0 + 10.0 * y),
            analysis.MARGIN_STUDY_INTENSITY: margin,
            "month": dates.month,
        }
    )


class TestPlantedCoefficient:
    """The regression reproduces a known answer on synthetic data."""

    def test_recovers_the_planted_lag_coefficients(self):
        planted = (0.30, 0.20, 0.10)
        frame = synthetic_response(nobs=600, planted=planted, seed=11)
        model = analysis.margin_response(
            frame=frame,
            label="synthetic",
            episode_dummies=False,
        )
        for k, expected in zip(analysis.MARGIN_LAGS, planted):
            got, se = model.regression.get(
                "%s_lag%d" % (analysis.MARGIN_STUDY_INTENSITY, k)
            )
            assert got == pytest.approx(expected, abs=0.02), (
                "lag %d came back at %.4f, not the planted %.2f" % (k, got, expected)
            )
            assert se > 0

    def test_the_sum_of_lags_and_its_standard_error_are_the_linear_combination(self):
        frame = synthetic_response(nobs=600, planted=(0.30, 0.20, 0.10), seed=12)
        model = analysis.margin_response(
            frame=frame, label="synthetic", episode_dummies=False
        )
        assert model.sum_b == pytest.approx(0.60, abs=0.05)

        # The sum is the sum, and its variance is 1' V 1 over those three rows
        # and columns of the same Newey-West covariance, not the sum of three
        # standard errors and not the root of the sum of three variances.
        fit = model.regression
        idx = [fit.index(name) for name in model.lag_terms]
        vector = np.zeros(fit.k)
        vector[idx] = 1.0
        assert model.sum_b == pytest.approx(float(vector @ fit.params), rel=1e-12)
        assert model.sum_b_se == pytest.approx(
            math.sqrt(float(vector @ fit.cov @ vector)), rel=1e-12
        )
        naive = float(np.sum(fit.se[idx]))
        assert model.sum_b_se != pytest.approx(naive, rel=1e-6)

    def test_a_zero_coefficient_comes_back_as_zero(self):
        """Planting nothing must not produce something. SPEC.md section 2 rule 4."""
        frame = synthetic_response(nobs=600, planted=(0.0, 0.0, 0.0), seed=13)
        model = analysis.margin_response(
            frame=frame, label="synthetic null", episode_dummies=False
        )
        assert abs(model.sum_b) < 2.0 * model.sum_b_se, (
            "the estimator found %.4f with se %.4f where nothing was planted"
            % (model.sum_b, model.sum_b_se)
        )


# ---------------------------------------------------------------------------
# The Newey-West lag is what it says it is
# ---------------------------------------------------------------------------


class TestNeweyWest:
    """The Newey-West lag is what this module claims, checked two ways."""

    def test_the_rule_of_thumb_and_the_floor_of_three(self):
        # SPEC.md section 6.1 says lag at least 3, so a short sample is floored.
        assert analysis.newey_west_lag(10) == 3
        assert analysis.newey_west_lag(50) == 3
        # floor(4 * (n / 100) ** (2 / 9)) for the real sample size.
        assert analysis.newey_west_lag(135) == 4
        for nobs in (135, 400, 1000, 5000):
            assert analysis.newey_west_lag(nobs) == int(
                math.floor(4.0 * (nobs / 100.0) ** (2.0 / 9.0))
            )
        for nobs in (10, 50, 135, 400, 1000):
            assert analysis.newey_west_lag(nobs) >= analysis.NEWEY_WEST_MIN_LAG

    def test_the_covariance_matches_statsmodels_at_the_same_lag(self):
        """An independent implementation, on the same data, at the claimed lag."""
        statsmodels_api = pytest.importorskip("statsmodels.api")
        rng = np.random.default_rng(99)
        nobs = 250
        X = np.column_stack(
            [np.ones(nobs), rng.normal(size=nobs), rng.normal(size=nobs)]
        )
        y = X @ np.array([1.0, 2.0, -0.5]) + rng.normal(size=nobs)
        for lag in (3, 4, 6):
            mine = analysis.ols_newey_west(y, X, ("const", "a", "b"), lag=lag)
            theirs = statsmodels_api.OLS(y, X).fit(
                cov_type="HAC",
                cov_kwds={"maxlags": lag, "use_correction": True},
            )
            assert mine.nw_lag == lag
            assert np.allclose(mine.params, theirs.params, rtol=1e-10)
            assert np.allclose(mine.cov, theirs.cov_params(), rtol=1e-8, atol=1e-12)

    def test_the_lag_actually_enters_the_covariance(self):
        """A different lag has to give a different covariance, or nothing is used."""
        # BOTH the regressor and the error have to be persistent. A HAC
        # covariance corrects the autocorrelation of the SCORES, x(t) e(t), so
        # an independent white noise regressor against an autocorrelated error
        # leaves the scores nearly uncorrelated and there is nothing to correct.
        # That is also the reason the real equation below needs it: utilisation
        # and the margin are both persistent month to month.
        rng = np.random.default_rng(5)
        nobs = 400
        x = np.zeros(nobs)
        e = np.zeros(nobs)
        for t in range(1, nobs):
            x[t] = 0.9 * x[t - 1] + rng.normal()
            e[t] = 0.8 * e[t - 1] + rng.normal()
        X = np.column_stack([np.ones(nobs), x])
        y = X @ np.array([0.5, 1.0]) + e
        zero = analysis.newey_west_cov(X, y - X @ np.linalg.lstsq(X, y, rcond=None)[0], 0)
        four = analysis.newey_west_cov(X, y - X @ np.linalg.lstsq(X, y, rcond=None)[0], 4)
        assert not np.allclose(zero, four)
        # With positively autocorrelated errors the HAC standard error is larger
        # than the one that ignores the autocorrelation. This is the whole point
        # of SPEC.md section 6.1 asking for it.
        assert np.sqrt(four[1, 1]) > np.sqrt(zero[1, 1])

    def test_the_lag_is_recorded_on_the_result(self):
        frame = synthetic_response(nobs=200, seed=31)
        model = analysis.margin_response(
            frame=frame, label="synthetic", episode_dummies=False, nw_lag=9
        )
        assert model.regression.nw_lag == 9
        default = analysis.margin_response(
            frame=frame, label="synthetic", episode_dummies=False
        )
        assert default.regression.nw_lag == analysis.newey_west_lag(
            default.regression.nobs
        )
        assert default.regression.nw_lag >= 3


# ---------------------------------------------------------------------------
# The bootstrap is reproducible from a fixed seed
# ---------------------------------------------------------------------------


def synthetic_kinked(
    nobs: int = 400,
    threshold: float = 6.0,
    slope_below: float = 2.0,
    seed: int = 3,
    noise: float = 0.6,
) -> pd.DataFrame:
    """A frame with a real kink at a threshold we chose.

    run_cut_threshold looks for the kink in the MEAN of lags 1, 2 and 3 of the
    margin column, so the kink is planted in exactly that variable and not in
    the raw column. Planting it in the raw column and hoping would test the
    search against data whose kink is somewhere else.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("1990-01-01", periods=nobs, freq="MS")
    margin = rng.uniform(-2.0, 20.0, nobs)
    lagged = pd.Series(margin)
    lagged_mean = ((lagged.shift(1) + lagged.shift(2) + lagged.shift(3)) / 3.0).to_numpy()
    y = 90.0 - slope_below * np.maximum(threshold - lagged_mean, 0.0) + rng.normal(
        0.0, noise, nobs
    )
    return pd.DataFrame(
        {
            "date": dates,
            "utilisation_pct": y,
            "intake_kb_d": 5000.0,
            "imports_kb_d": 4800.0,
            "capacity_kb_d": 6000.0,
            "capacity_assumed": False,
            "log_intake_pct": 100.0 * np.log(5000.0),
            analysis.MARGIN_STUDY_INTENSITY: margin,
            "month": dates.month,
        }
    )


def synthetic_flat(nobs: int = 400, seed: int = 4) -> pd.DataFrame:
    """The same shape with NO kink: a straight line and noise."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("1990-01-01", periods=nobs, freq="MS")
    margin = rng.uniform(-2.0, 20.0, nobs)
    y = 85.0 + 0.05 * margin + rng.normal(0.0, 1.0, nobs)
    return pd.DataFrame(
        {
            "date": dates,
            "utilisation_pct": y,
            "intake_kb_d": 5000.0,
            "imports_kb_d": 4800.0,
            "capacity_kb_d": 6000.0,
            "capacity_assumed": False,
            "log_intake_pct": 100.0 * np.log(5000.0),
            analysis.MARGIN_STUDY_INTENSITY: margin,
            "month": dates.month,
        }
    )


class TestBootstrapReproducible:
    """The bootstrap is reproducible from a fixed seed."""

    def test_the_same_seed_gives_the_same_interval(self):
        frame = synthetic_kinked(seed=17)
        first = analysis.run_cut_threshold(frame=frame, replications=200, seed=62)
        second = analysis.run_cut_threshold(frame=frame, replications=200, seed=62)
        assert np.array_equal(first.draws, second.draws)
        assert first.ci_low == second.ci_low
        assert first.ci_high == second.ci_high
        assert first.identified == second.identified
        assert first.point.threshold == second.point.threshold

    def test_a_different_seed_gives_different_draws(self):
        frame = synthetic_kinked(seed=17)
        a = analysis.run_cut_threshold(frame=frame, replications=200, seed=62)
        b = analysis.run_cut_threshold(frame=frame, replications=200, seed=63)
        assert not np.array_equal(a.draws, b.draws)
        # The point estimate does not depend on the seed at all: only the
        # interval is bootstrapped.
        assert a.point.threshold == b.point.threshold

    def test_the_seed_and_the_replication_count_are_recorded(self):
        frame = synthetic_kinked(seed=17)
        result = analysis.run_cut_threshold(frame=frame, replications=123, seed=62)
        assert result.seed == 62
        assert result.replications == 123
        assert len(result.draws) == 123

    def test_the_block_length_comes_from_the_autocorrelation_and_is_stated(self):
        # White noise has nothing to carry, so the rule returns a very short
        # block and says which lag it read it off.
        rng = np.random.default_rng(1)
        block, how, acf = analysis.block_length_from_acf(rng.normal(size=500))
        assert 1 <= block <= 3
        assert "band" in how
        assert len(acf) >= 1
        # A persistent series must give a longer block than white noise does.
        x = np.zeros(500)
        for t in range(1, 500):
            x[t] = 0.9 * x[t - 1] + rng.normal()
        longer, _, _ = analysis.block_length_from_acf(x)
        assert longer > block

    def test_the_real_threshold_run_is_reproducible(self):
        """Twice on the committed data, with the module's own default seed."""
        a = analysis.run_cut_threshold(replications=100)
        b = analysis.run_cut_threshold(replications=100)
        assert np.array_equal(a.draws, b.draws)
        assert a.block_length == b.block_length
        assert a.point.threshold == b.point.threshold


# ---------------------------------------------------------------------------
# The threshold search returns unidentified when there is no kink
# ---------------------------------------------------------------------------


class TestThresholdIdentification:
    """Handed data with no kink, the search says unidentified."""

    def test_no_kink_is_unidentified(self):
        frame = synthetic_flat(nobs=400, seed=41)
        result = analysis.run_cut_threshold(frame=frame, replications=400, seed=62)
        assert not result.identified, (
            "a straight line with noise produced an identified threshold at "
            "%.2f, interval %.2f to %.2f"
            % (result.point.threshold, result.ci_low, result.ci_high)
        )
        assert result.verdict == "unidentified"
        assert result.headroom_usd_bbl is None
        assert result.reasons, "an unidentified verdict has to say why"

    def test_a_real_kink_is_found_and_the_verdict_is_identified(self):
        """The other half of the same test: the search is not always negative."""
        frame = synthetic_kinked(nobs=600, threshold=6.0, slope_below=2.0, seed=43)
        result = analysis.run_cut_threshold(frame=frame, replications=400, seed=62)
        assert result.point.threshold == pytest.approx(6.0, abs=0.75)
        assert result.identified, (
            "a planted kink at 6.00 came back %s, interval %.2f to %.2f"
            % (result.verdict, result.ci_low, result.ci_high)
        )
        assert result.ci_low <= 6.0 <= result.ci_high
        assert result.ci_width <= analysis.THRESHOLD_MAX_CI_WIDTH_USD_BBL
        assert result.headroom_usd_bbl == result.point.threshold
        assert result.point.slope_below > 0

    def test_a_wide_interval_is_unidentified_by_the_ten_dollar_rule(self):
        # The same planted kink buried in noise: the point estimate may still be
        # near 6 but the interval must widen, and SPEC.md section 6.2's bar is a
        # width bar, not a point estimate bar.
        frame = synthetic_kinked(nobs=150, threshold=6.0, slope_below=0.2, noise=4.0, seed=44)
        result = analysis.run_cut_threshold(frame=frame, replications=400, seed=62)
        assert not result.identified
        assert result.ci_width > analysis.THRESHOLD_MAX_CI_WIDTH_USD_BBL or any(
            "edge" in reason for reason in result.reasons
        )

    def test_the_longest_run_dates_are_the_longest_run_s_dates(self):
        """Gate 3 self audit, finding 4.3. THE STRETCH IS NOT GUESSED.

        report() used to print the stretch as the last `longest_run_below`
        entries of months_below, which is right only while the longest run
        happens to sit at the end of the list. Here the stray month is put AFTER
        the run, which is the arrangement that made the old code print a span
        that does not exist.
        """
        months = pd.date_range("2000-01-01", periods=60, freq="MS")
        margin = np.full(60, 10.0)
        # One long run early, a gap, then a single stray month at the end.
        margin[5:26] = 1.0
        margin[55] = 1.0
        frame = pd.DataFrame(
            {
                "date": months,
                "utilisation_pct": 85.0 - 5.0 * (margin < 5.0),
                analysis.MARGIN_STUDY_INTENSITY: np.concatenate(
                    [margin[3:], np.full(3, 10.0)]
                ),
            }
        )
        result = analysis.run_cut_threshold(frame=frame, replications=20)

        # Recount the runs here, independently of the module.
        runs, current = [], []
        previous = None
        for month in result.months_below:
            period = pd.Period(month, freq="M")
            if previous is not None and period == previous + 1:
                current.append(period)
            else:
                current = [period]
                runs.append(current)
            previous = period
        longest = max(runs, key=len)
        assert len(longest) > 5, "this fixture needs a long run to be worth testing"
        assert result.months_below[-1] > str(longest[-1]), (
            "this fixture is meant to put a stray month AFTER the run, which is "
            "the arrangement the old positional guess got wrong"
        )
        assert result.longest_run_below == len(longest)
        assert result.longest_run_first == str(longest[0])
        assert result.longest_run_last == str(longest[-1])
        # The old code would have printed the last `longest` entries of the list.
        assert result.months_below[-result.longest_run_below] != result.longest_run_first

    def test_the_months_below_the_threshold_are_reported(self):
        """The dates are the diagnostic that tells a kink from an episode."""
        result = analysis.run_cut_threshold(replications=20)
        assert len(result.months_below) == result.point.months_below
        assert result.longest_run_below >= 1
        assert result.longest_run_below <= len(result.months_below)
        first = pd.Period(result.longest_run_first, freq="M")
        last = pd.Period(result.longest_run_last, freq="M")
        assert (last - first).n + 1 == result.longest_run_below
        # Utilisation below the threshold has to be lower than above it, or the
        # fitted slope and the reported means are telling different stories.
        assert result.mean_utilisation_below < result.mean_utilisation_above
        for month in result.months_below:
            assert len(month) == 7 and month[4] == "-"

    def test_the_grid_sensitivity_is_a_check_and_changes_nothing(self):
        table = analysis.threshold_grid_sensitivity(replications=60)
        assert len(table) == 4
        assert set(table.columns) >= {"threshold", "ci_low", "ci_high", "identified"}
        # The headline grid is the first row and it is the module's own constant,
        # so this function cannot be the thing that chose it.
        assert table["quantiles"].iloc[0] == "%.2f to %.2f" % (
            analysis.THRESHOLD_GRID_QUANTILES
        )
        assert analysis.THRESHOLD_GRID_QUANTILES == (0.05, 0.95)
        # And it is reachable by nothing but the report: no default anywhere in
        # the module takes its answer.
        assert (
            analysis.run_cut_threshold(replications=20).grid_quantiles
            == analysis.THRESHOLD_GRID_QUANTILES
        )

    def test_the_threshold_can_be_run_without_the_episodes(self):
        """Gate 3 self audit, finding 4.2. SPEC.md section 6.1's with and without.

        margin_response and intake_trend_response both honoured it and the
        threshold, the one result the site's headroom figure depends on, did not.
        """
        import inspect

        parameters = inspect.signature(analysis.run_cut_threshold).parameters
        assert "drop_episode_months" in parameters
        assert "drop_months" in parameters
        assert parameters["drop_episode_months"].default is False
        assert parameters["drop_months"].default is None

        headline = analysis.run_cut_threshold(replications=20)
        without = analysis.run_cut_threshold(
            replications=20, drop_episode_months=True
        )
        assert without.nobs < headline.nobs
        assert without.dropped_months
        assert not headline.dropped_months
        # Every month removed is inside an episode window, and none of the kept
        # ones is.
        kept = set(headline.months_below) - set(without.dropped_months)
        assert kept
        for month in without.dropped_months:
            stamp = pd.Timestamp(month + "-01")
            mask = analysis.episode_mask([stamp])
            assert mask["any_episode"].iloc[0] == 1.0

    def test_removing_the_stretch_destroys_the_kink(self):
        """Gate 3 self audit, finding 4.1. The measurement the report rests on.

        This is a statement about the committed data and it is deliberately one
        of the few. If a future refresh makes the kink survive the removal of the
        stretch it is estimated from, the study's strongest reason for the
        unidentified verdict has changed and somebody has to read the report
        again rather than watch it go on saying the old thing.
        """
        headline = analysis.run_cut_threshold(replications=200)
        stretch = [
            month
            for month in headline.months_below
            if headline.longest_run_first <= month <= headline.longest_run_last
        ]
        assert len(stretch) == headline.longest_run_below
        without = analysis.run_cut_threshold(replications=200, drop_months=stretch)
        assert without.nobs == headline.nobs - len(stretch)
        assert headline.point.slope_below > 0
        assert without.point.slope_below < 0, (
            "the slope below the kink no longer reverses when the stretch it is "
            "estimated from is removed. It is now %+.4f against %+.4f"
            % (without.point.slope_below, headline.point.slope_below)
        )
        assert without.point.threshold > headline.point.threshold
        # And the kink stops buying anything over a straight line.
        assert headline.point.r2 - headline.linear_r2 > 0.2
        assert without.point.r2 - without.linear_r2 < 0.05
        assert not without.identified

    def test_the_fit_at_a_fixed_threshold_is_least_squares(self):
        # Built here rather than through the frame, because this test is about
        # fit_hockey_stick and search_threshold directly and must not depend on
        # what run_cut_threshold does to the regressor first.
        rng = np.random.default_rng(45)
        margin = rng.uniform(-2.0, 20.0, 300)
        y = (
            90.0
            - 2.0 * np.maximum(6.0 - margin, 0.0)
            + rng.normal(0.0, 0.6, 300)
        )
        fit = analysis.fit_hockey_stick(margin, y, 6.0)
        assert fit.slope_below == pytest.approx(2.0, abs=0.2)
        assert fit.level == pytest.approx(90.0, abs=0.3)
        # The grid search minimises the sum of squared residuals, so no candidate
        # on the grid may beat the one it chose.
        best, grid, ssr = analysis.search_threshold(margin, y)
        assert ssr.min() == pytest.approx(
            analysis.fit_hockey_stick(margin, y, best.threshold).ssr, rel=1e-12
        )
        assert best.threshold == grid[int(np.argmin(ssr))]


# ---------------------------------------------------------------------------
# The kb/d translation is arithmetically right
# ---------------------------------------------------------------------------


class TestTranslation:
    """The kb/d translation is arithmetically right, by hand."""

    def test_the_arithmetic_by_hand(self):
        # 0.5 percentage points of capacity per $/bbl, a 10 $/bbl move, on a
        # 6,000 kb/d system: 0.5 * 10 = 5 percentage points of 6,000, which is
        # 300 kb/d. On 5,000 kb/d of runs that is 6 percent.
        t = analysis.translate_response(0.5, 0.1, 6000.0, 5000.0)
        assert t.kb_d == pytest.approx(300.0)
        assert t.share_of_runs == pytest.approx(0.06)

    def test_the_interval_is_the_same_map_applied_to_the_coefficient_interval(self):
        t = analysis.translate_response(0.5, 0.1, 6000.0, 5000.0)
        z = analysis.Z95
        assert t.kb_d_low == pytest.approx((0.5 - z * 0.1) / 100 * 10 * 6000.0)
        assert t.kb_d_high == pytest.approx((0.5 + z * 0.1) / 100 * 10 * 6000.0)
        # The map is linear, so the point estimate sits exactly in the middle.
        assert (t.kb_d_low + t.kb_d_high) / 2 == pytest.approx(t.kb_d)
        assert t.kb_d_high - t.kb_d == pytest.approx(t.kb_d - t.kb_d_low)

    def test_it_is_linear_in_the_move_and_in_the_base(self):
        one = analysis.translate_response(0.5, 0.1, 6000.0, 5000.0, move_usd_bbl=1.0)
        ten = analysis.translate_response(0.5, 0.1, 6000.0, 5000.0, move_usd_bbl=10.0)
        assert ten.kb_d == pytest.approx(10.0 * one.kb_d)
        doubled = analysis.translate_response(0.5, 0.1, 12000.0, 5000.0)
        assert doubled.kb_d == pytest.approx(
            2.0 * analysis.translate_response(0.5, 0.1, 6000.0, 5000.0).kb_d
        )

    def test_a_negative_response_translates_to_negative_barrels(self):
        t = analysis.translate_response(-0.5, 0.1, 6000.0, 5000.0)
        assert t.kb_d == pytest.approx(-300.0)
        assert t.share_of_runs == pytest.approx(-0.06)

    def test_a_zero_or_negative_base_is_refused(self):
        with pytest.raises(ValueError):
            analysis.translate_response(0.5, 0.1, 0.0, 5000.0)
        with pytest.raises(ValueError):
            analysis.translate_response(0.5, 0.1, 6000.0, -1.0)

    def test_the_model_carries_the_same_arithmetic(self):
        frame = synthetic_response(nobs=400, planted=(0.30, 0.20, 0.10), seed=51)
        model = analysis.margin_response(
            frame=frame, label="synthetic", episode_dummies=False
        )
        t = model.translation
        assert t.kb_d == pytest.approx(model.sum_b / 100.0 * 10.0 * t.base_kb_d)
        assert t.share_of_runs == pytest.approx(t.kb_d / t.runs_kb_d)


# ---------------------------------------------------------------------------
# Utilisation, on the committed data
# ---------------------------------------------------------------------------


class TestUtilisation:
    def test_it_reproduces_what_the_physical_recon_measured(self):
        """SPEC.md section 11 point 4 in spirit: an anchor, checked, not asserted.

        recon 03 section 2.3 divided each year's mean intake by that SAME year's
        capacity, so that is the column the anchor is checked against. The lagged
        column the regressions run on is a different number on purpose and the
        check prints it beside this one rather than instead of it.
        """
        check = analysis.utilisation_sanity_check()
        assert len(check) == len(analysis.RECON_ANNUAL_UTILISATION)
        failures = check[~check["agrees_to_3dp"]]
        assert failures.empty, (
            "utilisation disagrees with recon 03 section 2.3 in %s"
            % failures[["year", "utilisation_same_year", "recon"]].to_dict("records")
        )
        # The two columns are genuinely different, or the anchor would be
        # checking the lagged series by accident.
        assert check["study_less_same_year"].abs().max() > 0.01
        assert check["utilisation_study"].notna().all()

    def test_the_transcribed_figures_are_the_ones_that_were_transcribed(self):
        """Gate 5 finding 7. Eleven figures in analysis.py are transcribed from
        a document that is not in the repository and cannot be put in it: recon
        03 section 2.3 quotes the Energy Institute capacity sheet, which carries
        ICIS and S&P Global data and may not be redistributed (docs/sources.md
        section 2.7 and section 6). The test above checks the study against the
        transcription; this one checks the transcription itself, against a
        second reading of the same table recorded here, so that an edit to one
        of the eleven digits fails rather than moving the anchor the study is
        measured against.

        THE ONE DISAGREEMENT WITH THE DOCUMENT, recorded rather than smoothed.
        The report's own table prints 0.869 for 2015. Its own columns for that
        year, 5,936.5 kb/d of intake over 6,835.6 kb/d of capacity, divide to
        0.86844, which rounds to 0.868, and 0.868 is what is transcribed here
        and what this study reproduces (0.868469). The printed third decimal is
        a rounding slip in the report; the arithmetic is what was taken. See
        docs/open-questions.md, "The one figure recon 03 prints that its own
        columns do not give".
        """
        as_read = {
            2015: 0.868,  # the report prints 0.869; see the docstring
            2016: 0.889,
            2017: 0.895,
            2018: 0.857,
            2019: 0.851,
            2020: 0.724,
            2021: 0.742,
            2022: 0.798,
            2023: 0.791,
            2024: 0.794,
            2025: 0.831,
        }
        assert dict(analysis.RECON_ANNUAL_UTILISATION) == as_read
        # Every one is a utilisation: a ratio inside the unit interval, given to
        # exactly the three decimals the report gives, and one per year with no
        # year skipped.
        years = sorted(as_read)
        assert years == list(range(years[0], years[-1] + 1))
        for year, value in as_read.items():
            assert 0.0 < value < 1.0, year
            assert round(value, 3) == value, year

    def test_no_capacity_figure_is_applied_before_the_date_it_describes(self):
        """Gate 3 self audit, finding 1.1. THE LOOK AHEAD TEST.

        The Energy Institute figure for year Y is capacity at 31 December Y. Any
        month whose capacity comes from a stamp later than the first day of that
        month is reading a number that did not exist yet.
        """
        capacity = analysis.capacity_monthly()
        covered = capacity.dropna(subset=["capacity_source_year"])
        assert len(covered) > 600
        stamped = pd.to_datetime(
            {
                "year": covered["capacity_source_year"].astype(int),
                "month": 12,
                "day": 31,
            }
        )
        assert (stamped.to_numpy() <= covered["date"].to_numpy()).all(), (
            "a capacity figure is being applied to months before the 31 December "
            "it describes, which is the look ahead of finding 1.1"
        )
        # And it is the MOST RECENT such stamp, so the fix is an alignment and
        # not an arbitrary extra lag.
        assert (
            covered["date"].dt.year - covered["capacity_source_year"]
            == analysis.CAPACITY_SOURCE_LAG_YEARS
        ).all()
        assert analysis.CAPACITY_SOURCE_LAG_YEARS == 1

    def test_the_2025_step_lands_in_2026_and_not_in_2025(self):
        """The step the audit measured, in the one place it is easiest to read."""
        frame = analysis.utilisation_monthly().set_index("date")
        annual = analysis.capacity_annual().set_index("year")["capacity_kb_d"]
        assert annual[2025] < annual[2024], "2025 was the closure year, not 2024"
        for month in ("2025-01-01", "2025-06-01", "2025-12-01"):
            assert frame.loc[month, "capacity_kb_d"] == pytest.approx(annual[2024])
        for month in ("2026-01-01", "2026-06-01"):
            assert frame.loc[month, "capacity_kb_d"] == pytest.approx(annual[2025])

    def test_2026_needs_no_assumption_and_the_basis_still_guards_the_edge(self):
        default = analysis.utilisation_monthly()
        twenty_six = default[default["date"].dt.year == 2026]
        assert len(twenty_six) > 0
        # The 31 December 2025 stamp IS the right denominator for 2026, so no
        # month of it is an assumption under either basis.
        assert twenty_six["capacity_kb_d"].notna().all()
        assert not twenty_six["capacity_assumed"].any()
        capacity, year = analysis.latest_capacity_kb_d()
        assert year == 2025
        assert (twenty_six["capacity_kb_d"] == capacity).all()
        assert not default["capacity_assumed"].any()

        held = analysis.utilisation_monthly(analysis.CAPACITY_BEYOND_HELD_FLAT)
        assert np.allclose(
            held["capacity_kb_d"].to_numpy(),
            default["capacity_kb_d"].to_numpy(),
            equal_nan=True,
        ), "no month of this sample is past the file, so the bases must agree"

        # The guard still works where it bites: ask for a month the file cannot
        # reach and the two bases part company.
        beyond = pd.Timestamp(year=year + 2, month=6, day=1)
        nan_basis = analysis.capacity_monthly(through=beyond)
        flat_basis = analysis.capacity_monthly(
            analysis.CAPACITY_BEYOND_HELD_FLAT, through=beyond
        )
        tail = nan_basis[nan_basis["date"].dt.year > year + 1]
        assert len(tail) == 6
        assert tail["capacity_kb_d"].isna().all()
        assert tail["capacity_assumed"].all()
        flat_tail = flat_basis[flat_basis["date"].dt.year > year + 1]
        assert (flat_tail["capacity_kb_d"] == capacity).all()
        assert flat_tail["capacity_assumed"].all()

    def test_an_unknown_basis_is_refused_rather_than_defaulted(self):
        with pytest.raises(ValueError, match="basis_beyond"):
            analysis.capacity_monthly(basis_beyond="extrapolate")
        with pytest.raises(ValueError):
            analysis.capacity_monthly(interpolation="spline")

    def test_the_linear_basis_is_never_what_a_reported_number_runs_on(self):
        """CAPACITY_LINEAR carries look ahead by construction, so nothing uses it."""
        import inspect

        for function in (
            analysis.capacity_monthly,
            analysis.utilisation_monthly,
            analysis.utilisation_annual,
            analysis.analysis_frame,
        ):
            default = inspect.signature(function).parameters["interpolation"].default
            assert default == analysis.CAPACITY_STEP
        source = inspect.getsource(analysis.report)
        assert "CAPACITY_LINEAR" not in source

    def test_the_step_convention_is_a_step_and_not_a_ramp(self):
        step = analysis.capacity_monthly(interpolation=analysis.CAPACITY_STEP)
        year = step[step["date"].dt.year == 2020]
        assert year["capacity_kb_d"].nunique() == 1, (
            "a step carries one figure across a year. This one moved inside it, "
            "which is the smoothing SPEC.md section 6.1 asks not to do"
        )
        linear = analysis.capacity_monthly(interpolation=analysis.CAPACITY_LINEAR)
        linear_year = linear[linear["date"].dt.year == 2020]
        assert linear_year["capacity_kb_d"].nunique() > 1

    def test_the_closure_step_rule_is_the_stated_one(self):
        annual = analysis.capacity_annual().set_index("year")["capacity_kb_d"]
        change = annual.pct_change()
        expected = tuple(int(y) for y in change[change < -analysis.CLOSURE_STEP_MIN_FALL].index)
        assert analysis.capacity_step_years() == expected
        assert analysis.CLOSURE_STEP_MIN_FALL == 0.02
        # 2016 and 2025 are the two falls inside the regression sample.
        assert 2016 in expected and 2025 in expected

    def test_the_closure_step_turns_on_after_the_fall_is_recorded(self):
        """The same alignment rule as the denominator, finding 1.1 applied twice.

        A dummy that switched on in January of the fall year would assert in
        January that the region was going to lose a refinery before December, and
        unlike an episode dummy for an episode that has not happened it is NOT a
        column of zeros in the training rows of the expanding window.
        """
        model = analysis.intake_trend_response()
        names = [n for n in model.regression.names if n.startswith("closure_step_")]
        assert names, "the fallback carries closure steps or this test is vacuous"
        falls = set(analysis.capacity_step_years())
        for name in names:
            effective = int(name.rsplit("_", 1)[1])
            assert effective - analysis.CAPACITY_SOURCE_LAG_YEARS in falls
        assert names == ["closure_step_2017", "closure_step_2026"]

        design = model.regression.design
        dates = pd.DatetimeIndex(model.regression.dates)
        column = design[:, model.regression.names.index("closure_step_2017")]
        assert set(column[dates < pd.Timestamp("2017-01-01")]) == {0.0}
        assert set(column[dates >= pd.Timestamp("2017-01-01")]) == {1.0}

    def test_utilisation_pct_is_a_hundred_times_the_fraction(self):
        frame = analysis.utilisation_monthly(analysis.CAPACITY_BEYOND_HELD_FLAT)
        both = frame.dropna(subset=["utilisation"])
        assert np.allclose(both["utilisation_pct"], 100.0 * both["utilisation"])
        # And it is a plausible utilisation, not a ratio someone inverted.
        assert 0.4 < both["utilisation"].min() < both["utilisation"].max() < 1.1


# ---------------------------------------------------------------------------
# The sample, the margin and the episodes, on the committed data
# ---------------------------------------------------------------------------


class TestSampleAndMargin:
    def test_the_margin_starts_in_2015_and_is_not_extended_backwards(self):
        margin = analysis.margin_frame()
        assert str(margin["date"].iloc[0].date()) == "2015-01-01"
        assert margin[analysis.MARGIN_STUDY_INTENSITY].notna().all()

    def test_the_study_margin_is_the_mbr_less_the_gas_wedge(self):
        """The Gate 3 substitution, checked, so it cannot drift into being the MBR."""
        margin = analysis.margin_frame()
        assert np.allclose(
            margin[analysis.MARGIN_STUDY_INTENSITY],
            margin["margin_after_gas_usd_bbl"] - margin["gas_wedge_usd_bbl"],
        )
        # It is a different series from the official one in every month, because
        # the wedge is never zero: this study's intensity is strictly above
        # DGEC's embedded one and the gas price is strictly positive.
        assert (margin["gas_wedge_usd_bbl"] > 0).all()
        assert not np.allclose(
            margin[analysis.MARGIN_STUDY_INTENSITY], margin[analysis.MARGIN_OFFICIAL]
        )

    def test_the_regression_sample_is_the_one_reported(self):
        model = analysis.margin_response()
        assert model.first_month == "2015-04-01", (
            "the sample starts three months after the margin does, because the "
            "equation uses lags 1 to 3"
        )
        assert model.regression.nobs == 135
        assert model.regression.nw_lag == 4

    def test_dropping_the_episodes_removes_exactly_those_months(self):
        full = analysis.margin_response()
        without = analysis.margin_response(
            episode_dummies=False, drop_episode_months=True
        )
        assert without.regression.nobs < full.regression.nobs
        assert without.episodes_in_sample == ()
        dropped = full.regression.nobs - without.regression.nobs
        # Three windows of twelve months, minus the ones the sample does not
        # reach: 2026's window runs past the end of the JODI data.
        assert dropped == 29

    def test_the_episode_windows_are_one_rule_applied_three_times(self):
        dates = pd.date_range("2019-01-01", "2027-01-01", freq="MS")
        mask = analysis.episode_mask(dates)
        for name in analysis.EPISODES:
            assert mask[name].sum() == analysis.EPISODE_MONTHS
        # The three windows do not overlap in this sample, so any_episode is
        # exactly their sum.
        assert mask["any_episode"].sum() == 3 * analysis.EPISODE_MONTHS

    def test_the_threshold_uses_the_same_months_as_the_response(self):
        model = analysis.margin_response()
        threshold = analysis.run_cut_threshold(replications=20)
        assert threshold.nobs == model.regression.nobs
        assert threshold.first_month == model.first_month
        assert threshold.last_month == model.last_month

    def test_imports_are_reported_and_never_modelled(self):
        stats = analysis.imports_beside_intake()
        assert 0.5 < stats["mean_imports_over_intake"] < 1.5
        assert stats["months"] > 100
        # SPEC.md section 6.1: no separate model. The module offers no function
        # that regresses on imports, and this test is what keeps it that way.
        assert not any(
            "imports" in name and "response" in name for name in dir(analysis)
        )


class TestTheTrendIsTime:
    """The fallback's "linear monthly trend" is a trend in months, not in rows.

    On a contiguous sample the two are the same variable, so only the sample
    with episode months dropped can tell them apart. That sample has a 29 month
    hole in the middle of it, and a row counter closes the hole and bends the
    trend. These tests fail on a row counter and pass on elapsed months.
    """

    def _trend_column(self, model):
        fit = model.regression
        return np.asarray(fit.dates), fit

    def test_the_trend_spans_calendar_months_not_row_numbers(self):
        dropped = analysis.intake_trend_response(
            episode_dummies=False, drop_episode_months=True
        )
        assert "trend_months" in dropped.regression.names

        dates = pd.PeriodIndex(pd.DatetimeIndex(dropped.regression.dates), freq="M")
        elapsed_span = (dates[-1] - dates[0]).n
        rows = dropped.regression.nobs
        # The sample really does have a hole in it, or this test proves nothing.
        assert elapsed_span > rows - 1, (
            "the dropped sample is contiguous, so this test cannot distinguish "
            "elapsed months from row numbers"
        )

        # Rebuild the design the module must have used and check the trend term
        # against BOTH candidates. Elapsed months has to win outright.
        elapsed = np.array([(p - dates[0]).n for p in dates], dtype=float)
        counter = np.arange(rows, dtype=float)
        assert not np.allclose(elapsed, counter)

        full = analysis.intake_trend_response(
            frame=analysis.analysis_frame(
                analysis.CAPACITY_BEYOND_HELD_FLAT, analysis.CAPACITY_STEP
            )
        )
        # On the full, contiguous sample the two coincide, which is why the
        # headline fallback row is unaffected by this correction.
        full_dates = pd.PeriodIndex(pd.DatetimeIndex(full.regression.dates), freq="M")
        full_elapsed = np.array([(p - full_dates[0]).n for p in full_dates], dtype=float)
        assert np.allclose(full_elapsed, np.arange(full.regression.nobs, dtype=float))

    def test_the_trend_coefficient_is_per_month_of_calendar_time(self):
        """A planted trend in time comes back per month, with a gap in the sample.

        Built here rather than on the real data: a synthetic series with a known
        slope per calendar month, cut in half by a hole, is the only way to check
        the units of the term without asserting a number about the world.
        """
        months = pd.date_range("2000-01-01", periods=240, freq="MS")
        slope_per_month = 0.05
        elapsed = np.arange(240, dtype=float)
        y = 100.0 + slope_per_month * elapsed
        frame = pd.DataFrame(
            {
                "date": months,
                "utilisation_pct": y,
                "log_intake_pct": y,
                "intake_kb_d": 5000.0,
                "imports_kb_d": 4800.0,
                "capacity_kb_d": 6000.0,
                "capacity_assumed": False,
                analysis.MARGIN_STUDY_INTENSITY: 0.0,
                "month": months.month,
            }
        )
        # Cut a 40 month hole out of the middle. A row counter would read the
        # slope as 0.05 * 240 / 200, which is 0.06 per row.
        keep = ~((months >= "2010-01-01") & (months < "2013-05-01"))
        frame = frame[keep].reset_index(drop=True)

        model = analysis.intake_trend_response(
            frame=frame, episode_dummies=False, closure_years=()
        )
        got, _ = model.regression.get("trend_months")
        assert got == pytest.approx(slope_per_month, abs=1e-6), (
            "the trend came back at %.6f per unit. A row counter on this sample "
            "would give about %.6f" % (got, slope_per_month * 240 / 200)
        )


class TestTheCapacityEquationIsTheSpecs:
    """margin_response defaults to SPEC.md section 6.1's equation and nothing more.

    The trend and closure step arguments exist for one labelled diagnostic in
    report(). If a default ever turned them on, the headline response would
    quietly stop being the equation the spec writes.
    """

    def test_the_default_has_no_trend_and_no_closure_steps(self):
        model = analysis.margin_response()
        assert "trend_months" not in model.regression.names
        assert not [n for n in model.regression.names if n.startswith("closure_step_")]
        # What it does have: a constant, eleven month dummies, the regime terms
        # and the three margin lags.
        assert "const" in model.regression.names
        assert sum(n.startswith("month_") for n in model.regression.names) == 11
        assert len(model.lag_terms) == 3

    def test_the_diagnostic_is_reachable_only_by_asking_for_it(self):
        plain = analysis.margin_response()
        diagnostic = analysis.margin_response(
            trend=True, closure_years=analysis.capacity_step_years()
        )
        assert "trend_months" in diagnostic.regression.names
        assert [n for n in diagnostic.regression.names if n.startswith("closure_step_")]
        # A different equation, so a different answer. If these two agreed, the
        # diagnostic in the report would be measuring nothing.
        assert diagnostic.sum_b != plain.sum_b


class TestReport:
    def test_the_report_runs_and_says_the_things_it_has_to_say(self):
        text = analysis.report(replications=50)
        for phrase in (
            "margin_study_intensity = MBR - gas wedge",
            "THE DENOMINATOR IS LAGGED ONE YEAR",
            "VERDICT",
            "10 $/bbl is worth",
            # The four descriptions the Gate 3 self audit asked to have
            # corrected. Each of these is a sentence a reader meets, and this is
            # what stops one of them drifting back.
            "THIS SAMPLE CANNOT TELL THE THREE HORSES APART",
            "THE F IS A PROPERTY OF THE CONTROL SET",
            "TAKE THE EPISODE OUT AND THE ESTIMATE DOES NOT WIDEN, IT REVERSES",
            "INDISTINGUISHABLE FROM ZERO UNDER EVERY DEFINITION",
        ):
            assert phrase in text, "the report no longer says %r" % phrase
        for banned_claim in ("DEAD HEAT", "dead heat"):
            assert banned_claim not in text, (
                "the report asserts %r again. The measurement supports only that "
                "this sample cannot separate the horses, Gate 3 self audit "
                "finding 2.1" % banned_claim
            )
        # SPEC.md section 0.1: no em dashes and no en dashes anywhere. Written
        # as code points so that this file can assert the rule without breaking
        # it, which is what tests/test_base.py checks across the sources.
        for banned in (chr(0x2014), chr(0x2013)):
            assert banned not in text


# ---------------------------------------------------------------------------
# SPEC.md section 6.3: the three horses run on an identical sample
# ---------------------------------------------------------------------------


class TestTheHorsesShareOneSample:
    """The sample trap of SPEC.md section 6.3, closed and kept closed.

    Horse A exists from 2000-10 and horses B and C from 2015-01. If the race
    ever ran on each horse's own sample, A would be scored on twenty extra years
    of quiet data and the comparison would be worthless. These tests fail if the
    three samples ever diverge by a single month.
    """

    def test_every_horse_runs_on_exactly_the_same_months(self):
        frame = analysis.horse_frame()
        for dependent in analysis.DEPENDENTS:
            results = analysis.horse_race(dependent, frame=frame)
            assert len(results) == 3
            first = results[0].model.regression
            for result in results[1:]:
                fit = result.model.regression
                assert fit.nobs == first.nobs
                assert fit.dates == first.dates, (
                    "horse %s ran on different months from horse %s"
                    % (result.horse.key, results[0].horse.key)
                )
                assert result.model.first_month == results[0].model.first_month
                assert result.model.last_month == results[0].model.last_month
                # And on the same Newey-West truncation lag, or one horse could
                # look sharper than another for a reason that is not its data.
                assert fit.nw_lag == first.nw_lag

    def test_the_common_sample_is_the_intersection_and_not_one_horse_s_own(self):
        frame = analysis.horse_frame()
        for dependent in analysis.DEPENDENTS:
            common = analysis.common_sample_dates(
                frame, [h.column for h in analysis.HORSES], dependent
            )
            gasoil_only = analysis.common_sample_dates(
                frame, [analysis.CRACK_GASOIL], dependent
            )
            margin_only = analysis.common_sample_dates(
                frame, [analysis.MARGIN_OFFICIAL], dependent
            )
            # The gasoil crack really does reach much further back, so the
            # restriction is doing work rather than being a formality.
            assert len(gasoil_only) > len(common) + 100
            assert set(common) <= set(gasoil_only)
            assert set(common) <= set(margin_only)
            assert set(common) == set(gasoil_only) & set(margin_only)

    def test_the_lags_are_built_before_the_sample_is_cut_not_after(self):
        """A horse restricted to later months must not get a lag from a later row.

        The restriction is applied to the ROWS after the lags exist. If it were
        applied first, the lag of the first surviving month would silently be the
        month before it in the restricted frame, which on a frame with a hole is
        the wrong month entirely.
        """
        frame = analysis.horse_frame()
        dates = analysis.common_sample_dates(
            frame, [analysis.MARGIN_STUDY_INTENSITY], analysis.DEPENDENT_CAPACITY
        )
        # Cut a hole: keep only every other month of the sample.
        every_other = pd.DatetimeIndex(sorted(dates)[::2])
        model = analysis.margin_response(frame=frame, sample_dates=every_other)
        assert model.regression.nobs == len(every_other)
        # The lag column of the fitted design has to equal the margin at t-1 in
        # CALENDAR time, taken from the full frame, and not the previous row of
        # the restricted one.
        by_date = frame.set_index("date")[analysis.MARGIN_STUDY_INTENSITY]
        column = model.regression.names.index(
            "%s_lag1" % analysis.MARGIN_STUDY_INTENSITY
        )
        for i, stamp in enumerate(model.regression.dates):
            expected = by_date[pd.Timestamp(stamp) - pd.DateOffset(months=1)]
            assert model.regression.design[i, column] == pytest.approx(expected)

    def test_horse_c_is_labelled_a_substitution_everywhere_it_appears(self):
        """Gate 2 made the spec's B and C the same series. That has to be visible."""
        substitutions = [h for h in analysis.HORSES if h.substitution]
        assert len(substitutions) == 1
        horse_c = substitutions[0]
        assert horse_c.key == "C"
        assert horse_c.column == analysis.MARGIN_STUDY_INTENSITY
        assert "SUBSTITUTION" in horse_c.substitution_note
        # The flag reaches the table, so no row of it can be printed unlabelled.
        results = analysis.horse_race()
        table = analysis.horse_race_frame(results)
        assert table["substitution"].sum() == 1
        assert table.loc[table["horse"] == "C", "substitution"].all()
        assert not table.loc[table["horse"] != "C", "substitution"].any()

    def test_a_common_sample_shorter_than_the_training_window_is_refused(self):
        """horse_race must not quietly race on fewer months than it can score."""
        frame = analysis.horse_frame()
        common = analysis.common_sample_dates(
            frame,
            [h.column for h in analysis.HORSES],
            analysis.DEPENDENT_CAPACITY,
        )
        with pytest.raises(ValueError, match="common sample"):
            analysis.horse_race(
                analysis.DEPENDENT_CAPACITY, frame=frame, min_train=len(common)
            )


# ---------------------------------------------------------------------------
# The expanding window never peeks at the future
# ---------------------------------------------------------------------------


class TestExpandingWindowDoesNotPeek:
    """SPEC.md section 6.3's out of sample RMSE is actually out of sample."""

    def _fitted(self, nobs=200, seed=71):
        rng = np.random.default_rng(seed)
        x = rng.normal(size=nobs)
        design = np.column_stack([np.ones(nobs), x])
        y = design @ np.array([2.0, 0.5]) + rng.normal(0.0, 0.5, nobs)
        dates = pd.date_range("2000-01-01", periods=nobs, freq="MS")
        return y, design, dates

    def test_poisoning_the_future_cannot_change_an_earlier_forecast(self):
        """The test the whole claim rests on.

        Replace the dependent from some month onward with an absurd number. Every
        forecast made BEFORE that month trains only on rows before it and scores
        a month before it, so those errors must be bit for bit identical. If any
        of them moves, the window is reading the future.
        """
        y, design, dates = self._fitted()
        clean = analysis.ols_newey_west(y, design, ("const", "x"), dates=dates)
        min_train = 60
        poison_at = min_train + 5

        poisoned_y = y.copy()
        poisoned_y[poison_at:] = 1.0e6
        poisoned = analysis.ols_newey_west(
            poisoned_y, design, ("const", "x"), dates=dates
        )

        a = analysis.expanding_window_rmse(clean, min_train=min_train)
        b = analysis.expanding_window_rmse(poisoned, min_train=min_train)
        untouched = poison_at - min_train
        assert untouched == 5
        assert np.array_equal(a.errors[:untouched], b.errors[:untouched]), (
            "a forecast made before the poisoned month moved when the future "
            "changed, so the window is peeking"
        )
        assert np.array_equal(
            a.benchmark_errors[:untouched], b.benchmark_errors[:untouched]
        )
        # And the poison did land, or the test above proves nothing.
        assert not np.array_equal(a.errors, b.errors)

    def test_each_forecast_is_the_training_prefix_refitted_by_hand(self):
        """Recompute three of the forecasts independently and compare."""
        y, design, dates = self._fitted(nobs=120, seed=72)
        fit = analysis.ols_newey_west(y, design, ("const", "x"), dates=dates)
        window = analysis.expanding_window_rmse(fit, min_train=60)
        for offset in (0, 7, len(window.errors) - 1):
            t = 60 + offset
            params, *_ = np.linalg.lstsq(design[:t], y[:t], rcond=None)
            assert window.errors[offset] == pytest.approx(
                y[t] - design[t] @ params, rel=1e-12
            )
            assert window.benchmark_errors[offset] == pytest.approx(
                y[t] - y[:t].mean(), rel=1e-12
            )

    def test_the_counts_and_the_dates_are_what_they_claim(self):
        y, design, dates = self._fitted(nobs=150, seed=73)
        fit = analysis.ols_newey_west(y, design, ("const", "x"), dates=dates)
        window = analysis.expanding_window_rmse(fit, min_train=60)
        assert window.n_forecasts == 150 - 60
        assert window.min_train == 60
        assert window.first_forecast == str(dates[60].date())
        assert window.last_forecast == str(dates[-1].date())
        assert len(window.dates) == window.n_forecasts
        assert window.rmse == pytest.approx(
            math.sqrt(float(np.mean(window.errors**2)))
        )

    def test_a_sample_too_short_for_the_window_is_refused(self):
        y, design, dates = self._fitted(nobs=50, seed=74)
        fit = analysis.ols_newey_west(y, design, ("const", "x"), dates=dates)
        with pytest.raises(ValueError, match="min_train"):
            analysis.expanding_window_rmse(fit, min_train=60)

    def test_a_useful_regressor_beats_the_mean_and_a_useless_one_does_not(self):
        """The benchmark has to be able to lose and to win, or it says nothing."""
        rng = np.random.default_rng(75)
        nobs = 200
        x = rng.normal(size=nobs)
        design = np.column_stack([np.ones(nobs), x])
        dates = pd.date_range("2000-01-01", periods=nobs, freq="MS")

        signal = design @ np.array([2.0, 3.0]) + rng.normal(0.0, 0.3, nobs)
        strong = analysis.expanding_window_rmse(
            analysis.ols_newey_west(signal, design, ("const", "x"), dates=dates),
            min_train=60,
        )
        assert strong.beats_the_mean
        assert strong.ratio_to_mean < 0.5

        noise = 2.0 + rng.normal(0.0, 1.0, nobs)
        useless = analysis.expanding_window_rmse(
            analysis.ols_newey_west(noise, design, ("const", "x"), dates=dates),
            min_train=60,
        )
        assert useless.ratio_to_mean > 0.9

    def test_the_race_scores_every_horse_on_the_same_forecast_months(self):
        results = analysis.horse_race()
        for result in results[1:]:
            assert result.oos.dates == results[0].oos.dates
            assert result.oos.n_forecasts == results[0].oos.n_forecasts
            # The mean only benchmark depends on the dependent alone, so it must
            # be identical across horses. If it is not, they are not racing on
            # the same dependent.
            assert result.oos.mean_benchmark_rmse == pytest.approx(
                results[0].oos.mean_benchmark_rmse
            )

    def test_two_horses_scored_on_different_months_cannot_be_compared(self):
        capacity = analysis.horse_race(analysis.DEPENDENT_CAPACITY)
        analysis.loss_differential(capacity[0], capacity[1])
        short = analysis.horse_race(
            analysis.DEPENDENT_CAPACITY,
            min_train=analysis.EXPANDING_MIN_TRAIN_MONTHS + 6,
        )
        with pytest.raises(ValueError, match="different forecast months"):
            analysis.loss_differential(capacity[0], short[1])


# ---------------------------------------------------------------------------
# The first stage F is what this module claims it is
# ---------------------------------------------------------------------------


def synthetic_instrument(
    nobs: int = 240,
    relevance: float = 1.0,
    seed: int = 81,
) -> pd.DataFrame:
    """A frame where the instrument's pull on the margin is a number we chose.

    Dated from 2005, and none of the three episode windows of EPISODES falls
    inside 2005 to 2019, so with episode_dummies off the control set is a
    constant and eleven month dummies and the first stage can be rebuilt by hand
    in the test below.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2005-01-01", periods=nobs, freq="MS")
    gas = 6.0 + np.abs(rng.normal(0.0, 2.0, nobs))
    margin = 5.0 + relevance * gas + rng.normal(0.0, 1.0, nobs)
    y = 85.0 + 0.2 * np.roll(margin, 1) + rng.normal(0.0, 0.5, nobs)
    return pd.DataFrame(
        {
            "date": dates,
            "utilisation_pct": y,
            "log_intake_pct": y,
            "intake_kb_d": 5000.0,
            "imports_kb_d": 4800.0,
            "capacity_kb_d": 6000.0,
            "capacity_assumed": False,
            analysis.MARGIN_STUDY_INTENSITY: margin,
            analysis.INSTRUMENT_COLUMN: gas,
            "month": dates.month,
        }
    )


class TestFirstStageF:
    """The reported first stage F is the statistic it is described as."""

    def _by_hand(self, frame):
        """Rebuild the first stage independently: the three month means and OLS."""
        work = frame.copy()
        endo = pd.concat(
            [work[analysis.MARGIN_STUDY_INTENSITY].shift(k) for k in (1, 2, 3)],
            axis=1,
        )
        inst = pd.concat(
            [work[analysis.INSTRUMENT_COLUMN].shift(k) for k in (1, 2, 3)], axis=1
        )
        work["endo_mean"] = endo.mean(axis=1).where(endo.notna().all(axis=1))
        work["inst_mean"] = inst.mean(axis=1).where(inst.notna().all(axis=1))
        work = work.dropna(
            subset=["utilisation_pct", "endo_mean", "inst_mean"]
        ).reset_index(drop=True)
        columns = [np.ones(len(work))]
        names = ["const"]
        for month in range(2, 13):
            columns.append((work["date"].dt.month == month).to_numpy(dtype=float))
            names.append("month_%02d" % month)
        columns.append(work["inst_mean"].to_numpy(dtype=float))
        names.append("instrument")
        return work, np.column_stack(columns), names

    def test_the_f_is_measured_as_a_property_of_the_control_set(self):
        """Gate 3 self audit, finding 3.1. The F belongs to the controls.

        Two things are asserted here and neither is a number about the world:
        that the ladder's last rung reproduces the headline F exactly, so it is
        the same regression and not a lookalike, and that the first stage of the
        two dependents differs by ONE column, which is what makes "the F under
        two models" a misdescription.
        """
        capacity = analysis.gas_instrument(dependent=analysis.DEPENDENT_CAPACITY)
        fallback = analysis.gas_instrument(dependent=analysis.DEPENDENT_FALLBACK)
        assert [rung["controls"] for rung in capacity.control_ladder] == [
            "constant only",
            "plus month dummies",
            "plus episode dummies",
            "plus a linear trend",
        ]
        for result, rung in ((capacity, 2), (fallback, 3)):
            spec = result.control_ladder[rung]
            assert spec["is_the_spec_equation"]
            assert spec["f"] == pytest.approx(result.first_stage_f, rel=1e-10)
            assert spec["coefficient"] == pytest.approx(
                result.first_stage_coefficient, rel=1e-10
            )
            assert sum(
                bool(r["is_the_spec_equation"]) for r in result.control_ladder
            ) == 1

        # ONE COLUMN APART. The first stage contains no dependent at all.
        assert set(fallback.control_set) - set(capacity.control_set) == {
            "trend_months"
        }
        assert set(capacity.control_set) - set(fallback.control_set) == set()
        for name in (analysis.DEPENDENT_CAPACITY, analysis.DEPENDENT_FALLBACK):
            assert name not in capacity.control_set
            assert name not in fallback.control_set
        assert capacity.control_ladder[0] == fallback.control_ladder[0]

    def test_the_instruments_variation_is_the_episodes_the_controls_remove(self):
        """The other half of finding 3.1, and the reason the diagnosis changed."""
        result = analysis.gas_instrument(dependent=analysis.DEPENDENT_CAPACITY)
        assert result.instrument_months_in_episodes > 0
        assert result.instrument_sd_in_episodes > (
            2.0 * result.instrument_sd_outside_episodes
        ), (
            "the instrument's variation is no longer concentrated in the episode "
            "windows, sd %.2f inside against %.2f outside, so the diagnosis in "
            "the report needs rereading"
            % (
                result.instrument_sd_in_episodes,
                result.instrument_sd_outside_episodes,
            )
        )
        peak = pd.Timestamp(result.instrument_max_month + "-01")
        assert analysis.episode_mask([peak])["any_episode"].iloc[0] == 1.0
        # The episode rung is where the F goes, and the report says so from this
        # measurement rather than from a typed sentence.
        drops = [
            result.control_ladder[i - 1]["f"] - result.control_ladder[i]["f"]
            for i in range(1, len(result.control_ladder))
        ]
        assert drops.index(max(drops)) == 1, (
            "the biggest fall in the first stage F is no longer the episode "
            "dummies, so the diagnosis in the report needs rereading"
        )
        assert "PROPERTY OF THE CONTROL SET" in result.diagnosis
        assert "%.3f" % result.control_ladder[0]["f"] in result.diagnosis

    def test_the_f_is_the_square_of_the_newey_west_t_on_the_excluded_instrument(self):
        frame = synthetic_instrument(relevance=1.0)
        result = analysis.gas_instrument(
            frame=frame, dependent=analysis.DEPENDENT_CAPACITY, episode_dummies=False
        )
        assert result.first_stage_f == pytest.approx(
            (result.first_stage_coefficient / result.first_stage_se) ** 2, rel=1e-12
        )

    def test_the_first_stage_matches_an_independent_refit(self):
        frame = synthetic_instrument(relevance=1.0)
        result = analysis.gas_instrument(
            frame=frame, dependent=analysis.DEPENDENT_CAPACITY, episode_dummies=False
        )
        work, design, names = self._by_hand(frame)
        assert len(work) == result.nobs
        mine = analysis.ols_newey_west(
            work["endo_mean"].to_numpy(dtype=float),
            design,
            names,
            lag=result.nw_lag,
        )
        coefficient, se = mine.get("instrument")
        assert result.first_stage_coefficient == pytest.approx(coefficient, rel=1e-10)
        assert result.first_stage_se == pytest.approx(se, rel=1e-10)
        assert result.first_stage_f == pytest.approx((coefficient / se) ** 2, rel=1e-10)

    def test_it_matches_statsmodels_on_the_same_regression(self):
        """A second, independent implementation of the same standard error."""
        statsmodels_api = pytest.importorskip("statsmodels.api")
        frame = synthetic_instrument(relevance=1.0, seed=82)
        result = analysis.gas_instrument(
            frame=frame, dependent=analysis.DEPENDENT_CAPACITY, episode_dummies=False
        )
        work, design, names = self._by_hand(frame)
        theirs = statsmodels_api.OLS(
            work["endo_mean"].to_numpy(dtype=float), design
        ).fit(
            cov_type="HAC",
            cov_kwds={"maxlags": result.nw_lag, "use_correction": True},
        )
        index = names.index("instrument")
        assert result.first_stage_coefficient == pytest.approx(
            theirs.params[index], rel=1e-9
        )
        assert result.first_stage_se == pytest.approx(theirs.bse[index], rel=1e-8)
        assert result.first_stage_f == pytest.approx(theirs.tvalues[index] ** 2, rel=1e-8)

    def test_a_relevant_instrument_is_strong_and_an_irrelevant_one_is_weak(self):
        """The statistic has to be able to come out both ways."""
        strong = analysis.gas_instrument(
            frame=synthetic_instrument(relevance=1.0, seed=83),
            dependent=analysis.DEPENDENT_CAPACITY,
            episode_dummies=False,
        )
        assert strong.first_stage_f > analysis.FIRST_STAGE_F_BAR
        assert not strong.weak
        assert not strong.verdict.startswith("WEAK")

        weak = analysis.gas_instrument(
            frame=synthetic_instrument(relevance=0.0, seed=84),
            dependent=analysis.DEPENDENT_CAPACITY,
            episode_dummies=False,
        )
        assert weak.first_stage_f < analysis.FIRST_STAGE_F_BAR
        assert weak.weak
        assert weak.verdict.startswith("WEAK")

    def test_two_stage_least_squares_recovers_a_planted_coefficient(self):
        """If the estimator could not find a known answer, its F would not matter."""
        rng = np.random.default_rng(85)
        nobs = 480
        dates = pd.date_range("2005-01-01", periods=nobs, freq="MS")
        gas = 6.0 + np.abs(rng.normal(0.0, 2.0, nobs))
        confound = rng.normal(0.0, 1.0, nobs)
        margin = 5.0 + 1.5 * gas + 3.0 * confound + rng.normal(0.0, 0.5, nobs)
        planted = 0.40
        def three_month_mean(values):
            lagged = pd.Series(values)
            return (
                (lagged.shift(1) + lagged.shift(2) + lagged.shift(3)) / 3.0
            ).to_numpy()

        margin_mean = three_month_mean(margin)
        # The confound enters the dependent at the SAME one to three month window
        # as the margin does, which is what makes ordinary least squares biased
        # here and the instrument worth something. A contemporaneous confound
        # would leave least squares consistent and the test would prove nothing.
        y = (
            85.0
            + planted * margin_mean
            + 2.0 * three_month_mean(confound)
            + rng.normal(0.0, 0.5, nobs)
        )
        frame = pd.DataFrame(
            {
                "date": dates,
                "utilisation_pct": y,
                "log_intake_pct": y,
                "intake_kb_d": 5000.0,
                "imports_kb_d": 4800.0,
                "capacity_kb_d": 6000.0,
                "capacity_assumed": False,
                analysis.MARGIN_STUDY_INTENSITY: margin,
                analysis.INSTRUMENT_COLUMN: gas,
                "month": dates.month,
            }
        )
        result = analysis.gas_instrument(
            frame=frame, dependent=analysis.DEPENDENT_CAPACITY, episode_dummies=False
        )
        assert result.first_stage_f > analysis.FIRST_STAGE_F_BAR
        # Within three of its OWN standard errors of the planted value. An
        # absolute tolerance here would be a claim about how precise two stage
        # least squares is on 480 months, which is not what this test is for:
        # the estimator is consistent, not exact, and its own standard error is
        # the right yardstick for how close it should come.
        assert abs(result.iv_coefficient - planted) < 3.0 * result.iv_se, (
            "the instrument recovered %.4f where %.2f was planted, se %.4f"
            % (result.iv_coefficient, planted, result.iv_se)
        )
        # And the ordinary least squares estimate is biased upward by the
        # confound, which is the whole reason for running the instrument.
        assert result.ols_coefficient > result.iv_coefficient + 0.05

    def test_the_real_instrument_is_reported_weak_rather_than_forced(self):
        """SPEC.md section 6.3: if the instrument is weak, say so."""
        for dependent in analysis.DEPENDENTS:
            result = analysis.gas_instrument(dependent=dependent)
            assert result.instrument == analysis.INSTRUMENT_COLUMN
            assert result.weak == (result.first_stage_f <= analysis.FIRST_STAGE_F_BAR)
            if result.weak:
                assert result.verdict.startswith("WEAK")
        # The exclusion restriction is stated, not assumed away, and it says out
        # loud that it is arguable.
        assert "hydrogen" in analysis.EXCLUSION_RESTRICTION
        assert "probably does not hold" in analysis.EXCLUSION_RESTRICTION

    def test_the_mechanical_coefficient_is_the_gap_between_the_two_intensities(self):
        from crack import config

        result = analysis.gas_instrument()
        assert result.mechanical_coefficient == pytest.approx(
            -(
                config.GAS_INTENSITY_MMBTU_PER_BBL
                - config.DGEC_EMBEDDED_GAS_INTENSITY_MMBTU_PER_BBL
            )
        )


# ---------------------------------------------------------------------------
# SPEC.md section 6.4: count the months before running a test
# ---------------------------------------------------------------------------


class TestTheBreakIn2026:
    def test_the_post_break_months_are_counted_and_the_verdict_follows_the_count(self):
        result = analysis.break_2026()
        assert result.break_date == "2026-02-28"
        assert result.n_post == len(result.residuals)
        assert result.too_short == (result.n_post < result.min_post_months)
        assert result.min_post_months == analysis.BREAK_2026_MIN_POST_MONTHS == 12
        if result.too_short:
            assert str(result.n_post) in result.verdict
            assert "WILL NOT RETURN A VERDICT" in result.verdict

    def test_every_post_break_month_is_after_the_break(self):
        result = analysis.break_2026()
        for stamp in result.residuals["date"]:
            assert pd.Timestamp(stamp) >= pd.Timestamp(
                analysis.BREAK_2026_FIRST_POST_MONTH
            )
        assert result.n_pre > 100

    def _pre_break_dates(self, frame):
        return pd.DatetimeIndex(
            [
                d
                for d in analysis.common_sample_dates(
                    frame,
                    [analysis.MARGIN_STUDY_INTENSITY],
                    analysis.DEPENDENT_CAPACITY,
                )
                if d < pd.Timestamp(analysis.BREAK_2026_FIRST_POST_MONTH)
            ]
        )

    def test_the_prediction_is_out_of_sample_by_construction(self):
        """The fit sees no post break month, so the residuals are real errors."""
        frame = analysis.horse_frame()
        result = analysis.break_2026(frame=frame)
        model = analysis.margin_response(
            frame=frame,
            episode_dummies=False,
            sample_dates=self._pre_break_dates(frame),
        )
        assert model.regression.nobs == result.n_pre
        for stamp in model.regression.dates:
            assert pd.Timestamp(stamp) < pd.Timestamp(
                analysis.BREAK_2026_FIRST_POST_MONTH
            )
        assert np.allclose(
            result.residuals["residual"],
            result.residuals["actual"] - result.residuals["predicted"],
        )

    def test_the_episode_dummies_are_off_so_2026_is_not_absorbed(self):
        """With the dummy on, the deviation would be fitted away by construction."""
        frame = analysis.horse_frame()
        result = analysis.break_2026(frame=frame, episode_dummies=False)
        assert result.n_post >= 1
        model = analysis.margin_response(
            frame=frame,
            episode_dummies=False,
            sample_dates=self._pre_break_dates(frame),
        )
        assert not [n for n in model.regression.names if n.startswith("episode_")]

    def test_the_explanations_are_cited_and_not_chosen(self):
        result = analysis.break_2026()
        assert len(result.explanations) == 3
        for event in result.explanations:
            assert event["source_url"].startswith("http")
            assert event["date"] >= "2026-02-28"
        # No field on the result names a winning explanation, because SPEC.md
        # section 6.4 says not to pick one the data cannot separate.
        assert not hasattr(result, "explanation")
        assert not hasattr(result, "cause")

    def test_the_data_dates_are_reported_separately(self):
        """SPEC.md section 7.2: the runs date and the margin date are not one date."""
        result = analysis.break_2026()
        assert result.jodi_last_month != result.margin_last_month
        assert result.crack_last_month < result.jodi_last_month


# ---------------------------------------------------------------------------
# SPEC.md section 6.5: the seasonal aggregation excludes what it says it excludes
# ---------------------------------------------------------------------------


def synthetic_cracks(seed: int = 91) -> pd.DataFrame:
    """Monthly cracks 2001 to 2025 with a planted seasonal shape and no surprises."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2001-01-01", "2025-12-01", freq="MS")
    month = dates.month.to_numpy()
    gasoline = (
        15.0
        + 5.0 * np.isin(month, analysis.DRIVING_SEASON_MONTHS)
        + rng.normal(0.0, 0.5, len(dates))
    )
    gasoil = (
        15.0
        + 5.0 * np.isin(month, analysis.HEATING_SEASON_MONTHS)
        + rng.normal(0.0, 0.5, len(dates))
    )
    return pd.DataFrame(
        {
            "date": dates,
            analysis.CRACK_GASOIL: gasoil,
            analysis.CRACK_GASOLINE: gasoline,
            "brent_usd_bbl": 70.0,
        }
    )


class TestSeasonalExclusions:
    """A toggle that says it removes 2020, 2022 and 2026 has to remove them."""

    def test_excluding_a_year_gives_the_answer_that_year_never_existed(self):
        """The strongest form of the test: exclusion equals deletion.

        Poison the excluded years with absurd values. If the exclusion works, the
        result is the result on a frame that never had those years at all, and it
        is unchanged from the clean frame's answer.
        """
        clean = synthetic_cracks()
        poisoned = clean.copy()
        mask = poisoned["date"].dt.year.isin(analysis.SEASONAL_REMOVABLE_YEARS)
        poisoned.loc[mask, analysis.CRACK_GASOIL] = -900.0
        poisoned.loc[mask, analysis.CRACK_GASOLINE] = 900.0
        deleted = clean[~mask].reset_index(drop=True)

        a = analysis.seasonal_textbook_check(
            exclude_years=analysis.SEASONAL_REMOVABLE_YEARS, frame=poisoned
        )
        b = analysis.seasonal_textbook_check(
            exclude_years=analysis.SEASONAL_REMOVABLE_YEARS, frame=deleted
        )
        c = analysis.seasonal_textbook_check(
            exclude_years=analysis.SEASONAL_REMOVABLE_YEARS, frame=clean
        )
        for column in ("difference_usd_bbl", "se", "t", "complete_years"):
            assert np.allclose(a[column].to_numpy(), b[column].to_numpy())
            assert np.allclose(a[column].to_numpy(), c[column].to_numpy())
        # And the poison is genuinely destructive if it is NOT excluded, or the
        # test above would pass on a function that did nothing.
        unfiltered = analysis.seasonal_textbook_check(frame=poisoned)
        assert not np.allclose(
            unfiltered["difference_usd_bbl"].to_numpy(),
            a["difference_usd_bbl"].to_numpy(),
        )

    def test_the_shape_table_excludes_them_too(self):
        clean = synthetic_cracks()
        poisoned = clean.copy()
        mask = poisoned["date"].dt.year.isin(analysis.SEASONAL_REMOVABLE_YEARS)
        poisoned.loc[mask, analysis.CRACK_GASOIL] = -900.0
        a = analysis.seasonal_shape(
            exclude_years=analysis.SEASONAL_REMOVABLE_YEARS, frame=poisoned
        )
        b = analysis.seasonal_shape(
            exclude_years=analysis.SEASONAL_REMOVABLE_YEARS, frame=clean
        )
        assert np.allclose(
            a["%s_mean" % analysis.CRACK_GASOIL].to_numpy(),
            b["%s_mean" % analysis.CRACK_GASOIL].to_numpy(),
        )
        assert a.attrs["excluded_years"] == tuple(
            sorted(analysis.SEASONAL_REMOVABLE_YEARS)
        )

    def test_the_excluded_years_are_recorded_on_the_result(self):
        check = analysis.seasonal_textbook_check(
            exclude_years=analysis.SEASONAL_REMOVABLE_YEARS
        )
        for _, row in check.iterrows():
            assert row["excluded_years"] == tuple(
                sorted(analysis.SEASONAL_REMOVABLE_YEARS)
            )
        full = analysis.seasonal_textbook_check()
        # 2020 and 2022 are complete years in this sample and 2026 is not, so the
        # count has to fall by exactly two.
        assert (
            int(full["complete_years"].iloc[0]) - int(check["complete_years"].iloc[0])
            == 2
        )

    def test_the_monthly_range_never_draws_on_an_excluded_year(self):
        band = analysis.seasonal_monthly(
            exclude_years=analysis.SEASONAL_REMOVABLE_YEARS
        )
        used = band.attrs["years_used"]
        for year in analysis.SEASONAL_REMOVABLE_YEARS:
            assert year not in used
        assert band.attrs["excluded_years"] == tuple(
            sorted(analysis.SEASONAL_REMOVABLE_YEARS)
        )
        # The range is still the stated number of years deep: removing a year
        # reaches further back instead of quietly shrinking the band.
        assert len(used) == analysis.SEASONAL_RANGE_YEARS
        assert int(band["n_years"].max()) == analysis.SEASONAL_RANGE_YEARS

    def test_the_weekly_range_says_how_many_years_it_really_has(self):
        """The five year weekly range does not exist and the count has to admit it."""
        band = analysis.seasonal_weekly()
        assert int(band["n_years"].max()) < analysis.SEASONAL_RANGE_YEARS, (
            "the weekly reconstruction now reaches five years, so the report's "
            "statement that it cannot is out of date"
        )
        assert (band["n_years"] >= 0).all()
        populated = band[band["n_years"] > 0]
        assert len(populated) >= 50
        drawn = populated.dropna(subset=["median"])
        assert (drawn["minimum"] <= drawn["median"]).all()
        assert (drawn["median"] <= drawn["maximum"]).all()

    def test_the_current_year_line_is_the_current_year_and_not_the_band(self):
        band = analysis.seasonal_monthly()
        current = band.attrs["current_year"]
        assert current not in band.attrs["years_used"]
        assert current > max(band.attrs["years_used"])

    def test_the_textbook_check_can_return_does_not_hold(self):
        """SPEC.md section 6.5 says check, do not assert. So it must be able to fail."""
        flat = synthetic_cracks()
        flat[analysis.CRACK_GASOIL] = 15.0
        flat[analysis.CRACK_GASOLINE] = 15.0
        check = analysis.seasonal_textbook_check(frame=flat).set_index("crack")
        assert not check.loc[analysis.CRACK_GASOIL, "holds"]
        assert not check.loc[analysis.CRACK_GASOLINE, "holds"]

        planted = analysis.seasonal_textbook_check(frame=synthetic_cracks()).set_index(
            "crack"
        )
        assert planted.loc[analysis.CRACK_GASOIL, "holds"]
        assert planted.loc[analysis.CRACK_GASOLINE, "holds"]
        # The planted difference is 5 $/bbl in season against out of season, and
        # demeaning a year does not change a difference of two means inside it.
        assert planted.loc[
            analysis.CRACK_GASOLINE, "difference_usd_bbl"
        ] == pytest.approx(5.0, abs=0.1)

    def test_a_winter_is_contiguous_and_a_calendar_year_window_is_not_one(self):
        """Gate 3 self audit, finding 5.2. THE WINTER IS THE THING BEING MEASURED.

        Planted data settles this without appealing to the real series. ONE cold
        winter is put into an otherwise flat series, running November and
        December of 2010 into January, February and March of 2011. The contiguous
        window sees it for what it is: one anomalous winter out of twenty four.
        The calendar year window splits it in half and books the halves to two
        different years, which is exactly how "positive in 16 of 25" was
        manufactured.
        """
        months = pd.date_range("2000-01-01", periods=12 * 26, freq="MS")
        frame = pd.DataFrame({"date": months})
        stamp = frame["date"].dt.year * 12 + frame["date"].dt.month
        lift = np.zeros(len(frame))
        for year, month in ((2010, 11), (2010, 12), (2011, 1), (2011, 2), (2011, 3)):
            lift[(stamp == year * 12 + month).to_numpy()] = 12.0
        frame[analysis.CRACK_GASOIL] = 20.0 + lift
        frame[analysis.CRACK_GASOLINE] = 20.0

        contiguous = analysis.seasonal_textbook_check(
            frame=frame, window=analysis.SEASON_WINDOW_CONTIGUOUS
        ).set_index("crack")
        calendar = analysis.seasonal_textbook_check(
            frame=frame, window=analysis.SEASON_WINDOW_CALENDAR
        ).set_index("crack")
        assert contiguous.loc[analysis.CRACK_GASOIL, "seasons_positive"] == 1, (
            "one planted winter has to show up as one positive season"
        )
        assert calendar.loc[analysis.CRACK_GASOIL, "seasons_positive"] == 2, (
            "the calendar year window has to split that one winter across the "
            "two years it spans, which is the artefact of finding 5.2"
        )
        # The contiguous winter spans two calendar years and the driving season
        # does not, which is the whole of the difference.
        assert contiguous.loc[analysis.CRACK_GASOIL, "season_spans_years"] == 2
        assert contiguous.loc[analysis.CRACK_GASOLINE, "season_spans_years"] == 1
        assert calendar.loc[analysis.CRACK_GASOIL, "season_spans_years"] == 1
        # A contiguous winter needs both its years complete, so it has one fewer
        # season than there are complete years.
        assert (
            contiguous.loc[analysis.CRACK_GASOIL, "seasons"]
            == calendar.loc[analysis.CRACK_GASOIL, "seasons"] - 1
        )

    def test_the_gasoil_winter_sign_is_reported_with_what_it_rests_on(self):
        """Findings 5.2 and 5.3, on the committed data.

        Not a test that the number is a number. A test that the two things the
        audit found the published sentences hiding, a median of the opposite sign
        and a mean carried by two observations, are both on the result where the
        report can read them.
        """
        calendar = analysis.seasonal_textbook_check(
            window=analysis.SEASON_WINDOW_CALENDAR
        ).set_index("crack")
        row = calendar.loc[analysis.CRACK_GASOIL]
        assert row["difference_usd_bbl"] < 0 < row["median_usd_bbl"], (
            "the calendar year gasoil mean and median no longer disagree in "
            "sign, so the paragraph explaining why they did needs rereading"
        )
        assert len(row["two_most_negative"]) == 2
        contiguous = analysis.seasonal_textbook_check().set_index("crack")
        assert not contiguous.loc[analysis.CRACK_GASOIL, "holds"]
        assert not calendar.loc[analysis.CRACK_GASOIL, "holds"]
        # The textbook failure is the finding and it survives every window, which
        # is what SPEC.md section 6.5 asked to have checked.
        for window in analysis.SEASON_WINDOWS:
            for exclusions in ((), analysis.SEASONAL_REMOVABLE_YEARS):
                check = analysis.seasonal_textbook_check(
                    exclude_years=exclusions, window=window
                ).set_index("crack")
                assert not check.loc[analysis.CRACK_GASOIL, "holds"]
                assert abs(check.loc[analysis.CRACK_GASOIL, "t"]) < 1.0
                assert check.loc[analysis.CRACK_GASOLINE, "holds"]

    def test_the_holds_flag_uses_the_module_s_own_critical_value(self):
        """The one number the Gate 3 self audit could not trace, now traceable."""
        import inspect

        source = inspect.getsource(analysis.seasonal_textbook_check)
        assert "mean / se > Z95" in source
        assert "> 2.0" not in source

    def test_the_season_windows_are_fixed_and_not_searched(self):
        assert analysis.DRIVING_SEASON_MONTHS == (5, 6, 7, 8, 9)
        assert analysis.HEATING_SEASON_MONTHS == (11, 12, 1, 2, 3)
        assert analysis.SEASONAL_REMOVABLE_YEARS == (2020, 2022, 2026)
        # No function in this module takes a season as something to optimise
        # over: the windows are module constants and the only arguments are the
        # years to exclude and the frame. SPEC.md section 6.6.
        import inspect

        signature = inspect.signature(analysis.seasonal_textbook_check)
        # `window` names one of two FIXED definitions of a season, both of which
        # are reported. It is not a knob to search over: the month sets are the
        # module constants above and neither window can be handed a new one.
        assert set(signature.parameters) == {"exclude_years", "frame", "window"}
        assert signature.parameters["window"].default == (
            analysis.SEASON_WINDOW_CONTIGUOUS
        )
        assert analysis.SEASON_WINDOWS == ("contiguous", "calendar_year")
        with pytest.raises(ValueError):
            analysis.seasonal_textbook_check(window="october_to_february")

    def test_the_weekly_and_monthly_layers_are_two_panels_and_not_one_line(self):
        join = analysis.seasonal_join()
        assert join["overlap_months"] > 0
        # The gasoline quotations are different products and the gap is large.
        assert abs(join["%s_mean_gap" % analysis.CRACK_GASOLINE]) > 1.0
        assert join["%s_correlation" % analysis.CRACK_GASOIL] > 0.9
        # No function in this module returns the two layers joined into one
        # series, and that is deliberate.
        assert not any("splice" in name or "stitch" in name for name in dir(analysis))


# ---------------------------------------------------------------------------
# The race is reported honestly, whatever it says
# ---------------------------------------------------------------------------


class TestTheRaceIsReportedHonestly:
    def test_the_winner_sentence_is_read_off_the_numbers(self):
        results = analysis.horse_race()
        key, sentence = analysis.horse_race_winner(results)
        best = min(results, key=lambda r: r.oos.rmse)
        assert key == best.horse.key
        assert ("%.4f" % best.oos.rmse) in sentence

    def test_an_undecided_race_is_not_called_a_dead_heat(self):
        """Gate 3 self audit, finding 2.1. SPEC.md section 2 rules 3 and 4 on the prose.

        A dead heat asserts that the horses are equal, which is a finding. The
        measurement supports only that this sample cannot separate them. The two
        are different claims and this test keeps the second one.
        """
        results = analysis.horse_race()
        pairs = [
            analysis.loss_differential(results[i], results[j])
            for i in range(len(results))
            for j in range(i + 1, len(results))
        ]
        _, sentence = analysis.horse_race_winner(results)
        if not any(p.distinguishable for p in pairs):
            assert "THIS SAMPLE CANNOT TELL THE HORSES APART" in sentence
            assert "NOT THE SAME AS SAYING THEY ARE EQUAL" in sentence
            assert "withheld" in sentence
            # The power is printed beside the claim, because "could not
            # separate" is only meaningful next to "could not have separated".
            assert "power" in sentence
            for banned in ("DEAD HEAT", "dead heat"):
                assert banned not in sentence
        else:
            assert "carries information" in sentence

    def test_the_power_of_each_comparison_travels_with_it(self):
        """Finding 2.1 again, on the arithmetic rather than the prose."""
        results = analysis.horse_race()
        pair = analysis.loss_differential(results[0], results[1])
        better = min(r.oos.rmse for r in results[:2])
        worse = max(r.oos.rmse for r in results[:2])
        assert pair.better_rmse == pytest.approx(better)
        assert pair.worse_rmse == pytest.approx(worse)
        assert pair.observed_gap_pct == pytest.approx(
            100.0 * (worse - better) / worse
        )
        # The smallest detectable gap, rebuilt here from the definition.
        detectable = math.sqrt(better**2 + analysis.Z95 * pair.nw_se)
        assert pair.detectable_gap_pct == pytest.approx(
            100.0 * (detectable - better) / detectable
        )
        # A test cannot have less power than its own size.
        assert 0.05 <= pair.power_at_observed <= 1.0
        # Power rises with the effect and falls with the noise, or the formula
        # is upside down.
        loud = dataclasses.replace(pair, mean_difference=pair.nw_se * 5.0)
        quiet = dataclasses.replace(pair, mean_difference=pair.nw_se * 0.01)
        assert loud.power_at_observed > 0.99
        assert quiet.power_at_observed == pytest.approx(0.05, abs=0.002)
        assert loud.forecasts_for_target_power < quiet.forecasts_for_target_power

    def test_this_sample_could_not_have_separated_the_horses(self):
        """The measurement the sentence rests on, asserted so it cannot rot.

        If a future data refresh makes these tests powerful, the report's own
        wording changes with them, because every clause of it is computed. This
        test records what is true today: the comparisons cannot see the gaps they
        are being asked about.
        """
        for dependent in analysis.DEPENDENTS:
            results = analysis.horse_race(dependent=dependent)
            for i in range(len(results)):
                for j in range(i + 1, len(results)):
                    pair = analysis.loss_differential(results[i], results[j])
                    assert not pair.distinguishable
                    assert pair.observed_gap_pct < pair.detectable_gap_pct, (
                        "%s %s: the observed gap is now larger than the smallest "
                        "detectable one, so the report's power paragraph needs "
                        "rereading" % (dependent, pair.sentence)
                    )
                    assert pair.power_at_observed < 0.5
                    assert pair.forecasts_for_target_power > 10 * pair.nobs

    def test_the_loss_differential_is_the_paired_squared_error_difference(self):
        results = analysis.horse_race()
        pair = analysis.loss_differential(results[0], results[1])
        expected = float(np.mean(results[0].oos.errors**2 - results[1].oos.errors**2))
        assert pair.mean_difference == pytest.approx(expected, rel=1e-12)
        assert pair.nobs == results[0].oos.n_forecasts
        # It is antisymmetric, which a mean of a difference has to be.
        reverse = analysis.loss_differential(results[1], results[0])
        assert reverse.mean_difference == pytest.approx(-pair.mean_difference)
        assert reverse.nw_se == pytest.approx(pair.nw_se)

    def test_the_long_sample_row_is_labelled_and_is_not_in_the_race(self):
        long_run = analysis.gasoil_long_sample()
        race = analysis.horse_race()
        in_race = next(r for r in race if r.horse.column == analysis.CRACK_GASOIL)
        assert long_run.model.regression.nobs > in_race.model.regression.nobs
        assert "NOT the race" in long_run.model.label
        assert long_run.model.first_month < in_race.model.first_month


class TestGateThreeReport:
    def test_the_report_says_the_second_half_s_things(self):
        text = analysis.report(replications=20)
        for phrase in (
            "THE SAMPLE TRAP",
            "SUBSTITUTION",
            "OOS RMSE",
            "RUNS MOVE CRACKS",
            "THE EXCLUSION RESTRICTION",
            "first stage",
            "COUNT THE MONTHS FIRST",
            "THIS STUDY DOES NOT PICK ONE",
            "CHECKED AND NOT ASSERTED",
            "WHAT B AND C GIVE THAT A CANNOT",
        ):
            assert phrase in text, "the report no longer says %r" % phrase
        for banned in (chr(0x2014), chr(0x2013)):
            assert banned not in text


# ---------------------------------------------------------------------------
# The analysis must run on a checkout that has no data/private
# ---------------------------------------------------------------------------
#
# Gate 5, and it is the regression these tests exist for rather than a nicety.
# The Energy Institute capacity table may not be redistributed, so it lives in
# data/private, which is gitignored; a GitHub runner clones the repository and
# has none of it. This module used to read that file directly, and on a clean
# checkout 98 tests and python scripts/export.py --check died on
# FileNotFoundError, which means the study could not be rebuilt by anybody but
# its author whatever the README claimed. The five country total is now a
# committed derived cache. These two tests prove it stayed that way.


def test_the_capacity_series_is_a_committed_cache_and_not_the_private_table():
    assert analysis.CAPACITY_DIRECTORY == "cache"
    assert analysis.CAPACITY_SERIES == "nwe5_refinery_capacity_annual"
    assert analysis.CAPACITY_SOURCE_SERIES == "ei_refinery_capacity_annual"
    assert (REPO_ROOT / "data" / "cache" / "nwe5_refinery_capacity_annual.csv").exists()


def test_every_capacity_path_runs_with_data_private_taken_away(tmp_path, monkeypatch):
    """The clean checkout, simulated: data/private points at an empty directory.

    Nothing here is allowed to fall back to a private file, so if any of these
    four paths still reached for one it would raise FileNotFoundError here
    exactly as it did in CI.
    """
    from crack.sources import base as sources_base

    monkeypatch.setattr(sources_base, "PRIVATE", tmp_path / "no-private")

    annual = analysis.capacity_annual()
    assert len(annual) > 50
    assert list(annual.columns) == ["year", "capacity_kb_d"]

    monthly = analysis.utilisation_monthly()
    assert monthly["utilisation"].notna().any()

    capacity, year = analysis.latest_capacity_kb_d()
    assert capacity > 0 and year >= 2020
    assert analysis.capacity_step_years()
