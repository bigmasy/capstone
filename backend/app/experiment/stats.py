"""Paired statistics over independent generations.

Every generation gives one number per method (the mean nDCG over its test viewers); the
methods are compared through the per-generation differences. The decision rule is fixed in
advance: supported when the lower bound of the bootstrap interval is above zero and the mean
difference is at least ``min_delta``.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats as scipy_stats

DEFAULT_RESAMPLES = 10_000
DEFAULT_CONFIDENCE = 0.95


@dataclass(frozen=True, slots=True)
class PairedSummary:
    """Summary of paired per-generation differences.

    :param n: Number of generations.
    :param mean: Mean difference.
    :param ci_low: Lower bound of the percentile bootstrap interval of the mean.
    :param ci_high: Upper bound of the interval.
    :param wilcoxon_p: Two-sided p-value of the Wilcoxon signed-rank test (1.0 if all
        differences are zero).
    :param cohen_dz: Mean divided by the sample standard deviation (ddof=1), or None if the
        differences do not vary.
    :param prob_superiority: Share of generations with a positive difference, ties counting
        one half.
    """

    n: int
    mean: float
    ci_low: float
    ci_high: float
    wilcoxon_p: float
    cohen_dz: float | None
    prob_superiority: float

    def as_dict(self) -> dict[str, float | int | None]:
        """Return the summary as a plain dict for JSON.

        :return: Field names mapped to numbers.
        """
        return {
            "n": self.n,
            "mean": self.mean,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "wilcoxon_p": self.wilcoxon_p,
            "cohen_dz": self.cohen_dz,
            "prob_superiority": self.prob_superiority,
        }


def paired_summary(
    differences: Sequence[float],
    *,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int,
    confidence: float = DEFAULT_CONFIDENCE,
) -> PairedSummary:
    """Summarise paired differences with a bootstrap interval and rank-based tests.

    :param differences: One difference per generation (method A minus method B).
    :param resamples: Number of bootstrap resamples.
    :param seed: Seed of the bootstrap, fixed in the configuration for reproducibility.
    :param confidence: Level of the percentile interval.
    :raises ValueError: If there are fewer than two finite differences, or the resample count
        or the confidence level is invalid.
    :return: The summary.
    """
    values = np.asarray(differences, dtype=np.float64)
    if len(values) < 2 or not np.all(np.isfinite(values)):
        raise ValueError("at least two finite differences are needed")
    if resamples < 1 or not 0 < confidence < 1:
        raise ValueError("resamples must be positive and confidence between 0 and 1")
    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, len(values), size=(resamples, len(values)))].mean(axis=1)
    tail = (1 - confidence) / 2
    low, high = np.quantile(means, [tail, 1 - tail])
    std = float(values.std(ddof=1))
    positive = float(np.sum(values > 0)) + 0.5 * float(np.sum(values == 0))
    return PairedSummary(
        n=len(values),
        mean=float(values.mean()),
        ci_low=float(low),
        ci_high=float(high),
        wilcoxon_p=_wilcoxon_p(values),
        cohen_dz=float(values.mean()) / std if std > 0 and math.isfinite(std) else None,
        prob_superiority=positive / len(values),
    )


def _wilcoxon_p(values: np.ndarray) -> float:
    """Two-sided Wilcoxon signed-rank p-value; 1.0 when every difference is zero."""
    if not np.any(values != 0):
        return 1.0
    return float(scipy_stats.wilcoxon(values).pvalue)


def decide(summary: PairedSummary, *, min_delta: float) -> bool:
    """Apply the pre-registered decision rule.

    :param summary: Summary of method A minus method B.
    :param min_delta: Smallest mean difference worth reporting (0.01 in the protocol).
    :return: True if the lower bound of the interval is above zero and the mean is at least
        ``min_delta``.
    """
    return summary.ci_low > 0 and summary.mean >= min_delta
