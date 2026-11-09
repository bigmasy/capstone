import math

import numpy as np
import pytest
from scipy import stats as scipy_stats

from app.experiment.stats import decide, paired_summary

DIFFS = [0.02, 0.03, -0.01, 0.04, 0.015, 0.025, 0.0, 0.035, 0.01, 0.02]


def test_summary_matches_independent_calculations():
    summary = paired_summary(DIFFS, resamples=2000, seed=1)

    arr = np.array(DIFFS)
    assert summary.n == 10
    assert summary.mean == pytest.approx(arr.mean())
    assert summary.cohen_dz == pytest.approx(arr.mean() / arr.std(ddof=1))
    assert summary.prob_superiority == pytest.approx((8 + 0.5 * 1) / 10)
    assert summary.wilcoxon_p == pytest.approx(scipy_stats.wilcoxon(arr).pvalue)


def test_bootstrap_interval_is_reproducible_and_brackets_the_mean():
    a = paired_summary(DIFFS, resamples=2000, seed=7)
    b = paired_summary(DIFFS, resamples=2000, seed=7)
    c = paired_summary(DIFFS, resamples=2000, seed=8)

    assert (a.ci_low, a.ci_high) == (b.ci_low, b.ci_high)
    assert (a.ci_low, a.ci_high) != (c.ci_low, c.ci_high)
    assert a.ci_low < a.mean < a.ci_high
    assert min(DIFFS) <= a.ci_low and a.ci_high <= max(DIFFS)


def test_bootstrap_interval_is_the_percentile_interval_of_resampled_means():
    summary = paired_summary(DIFFS, resamples=4000, seed=3, confidence=0.9)

    rng = np.random.default_rng(3)
    arr = np.array(DIFFS)
    means = arr[rng.integers(0, len(arr), size=(4000, len(arr)))].mean(axis=1)
    assert summary.ci_low == pytest.approx(np.quantile(means, 0.05))
    assert summary.ci_high == pytest.approx(np.quantile(means, 0.95))


def test_constant_differences_have_a_degenerate_interval_and_no_effect_size():
    summary = paired_summary([0.02] * 6, resamples=500, seed=1)

    assert summary.ci_low == pytest.approx(0.02) == pytest.approx(summary.ci_high)
    assert summary.cohen_dz is None
    assert summary.prob_superiority == 1.0


def test_all_zero_differences_give_p_one_and_no_effect():
    summary = paired_summary([0.0] * 5, resamples=100, seed=1)

    assert summary.wilcoxon_p == 1.0
    assert summary.mean == 0.0
    assert summary.prob_superiority == 0.5


def test_at_least_two_generations_are_needed():
    with pytest.raises(ValueError):
        paired_summary([0.1], resamples=100, seed=1)
    with pytest.raises(ValueError):
        paired_summary([0.1, float("nan")], resamples=100, seed=1)
    with pytest.raises(ValueError):
        paired_summary([0.1, 0.2], resamples=0, seed=1)


def test_decision_rule_needs_a_positive_lower_bound_and_a_large_enough_mean():
    strong = paired_summary([0.03, 0.04, 0.05, 0.035, 0.045, 0.04], resamples=1000, seed=1)
    tiny = paired_summary([0.001, 0.002, 0.0015, 0.0012, 0.0018, 0.001], resamples=1000, seed=1)
    noisy = paired_summary([0.05, -0.04, 0.06, -0.05, 0.04, -0.03], resamples=1000, seed=1)

    assert decide(strong, min_delta=0.01) is True
    assert decide(tiny, min_delta=0.01) is False  # lower bound > 0 but the effect is too small
    assert decide(noisy, min_delta=0.01) is False


def test_summary_serialises_to_plain_numbers():
    data = paired_summary(DIFFS, resamples=200, seed=1).as_dict()

    assert set(data) == {
        "n",
        "mean",
        "ci_low",
        "ci_high",
        "wilcoxon_p",
        "cohen_dz",
        "prob_superiority",
    }
    assert all(v is None or math.isfinite(v) for v in data.values())
