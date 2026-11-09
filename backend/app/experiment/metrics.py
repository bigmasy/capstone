"""Ranking metrics: tie-aware nDCG@k, computed analytically.

The reported values use this implementation; scikit-learn is only a reference in the tests.
"""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

_FloatArray = NDArray[np.float64]
# A list of numbers: a plain sequence or a numpy array
Values = Sequence[float] | NDArray[np.floating[Any]]


def _discounts(n: int) -> _FloatArray:
    """Cumulative discounts: entry i is the sum of 1/log2(p + 1) over positions p = 1..i."""
    positions = np.arange(1, n + 1, dtype=np.float64)
    return np.concatenate(([0.0], np.cumsum(1.0 / np.log2(positions + 1.0))))


def _check(scores: Values, gains: Values, k: int) -> tuple[_FloatArray, _FloatArray]:
    """Validate the input and return it as arrays."""
    if k < 1:
        raise ValueError("k must be at least 1")
    if len(scores) != len(gains):
        raise ValueError("scores and gains must have the same length")
    if len(scores) == 0:
        raise ValueError("the list must not be empty")
    s = np.asarray(scores, dtype=np.float64)
    g = np.asarray(gains, dtype=np.float64)
    if not np.all(np.isfinite(s)) or not np.all(np.isfinite(g)):
        raise ValueError("scores and gains must be finite")
    if np.any(g < 0):
        raise ValueError("gains must not be negative")
    return s, g


def ndcg_at_k(scores: Values, gains: Values, k: int) -> float | None:
    """Return the tie-aware nDCG@k of one ranked list.

    Items are ordered by score, best first, with gains discounted by 1/log2(position + 1).
    Items with equal scores form a tied group whose internal order is unknown; the result is
    the average over all uniform random orders of every group. By symmetry each item of a
    group occupies each of the group's positions with equal probability, so the expectation
    is the mean gain of the group times the sum of the discounts of its positions. This is
    exact, not sampled. The ideal DCG sorts the gains. A list whose gains are all zero has no
    defined nDCG.

    :param scores: Score of each item, higher is better; equal values are ties.
    :param gains: Real-valued gain of each item, not negative.
    :param k: Number of leading positions that count.
    :raises ValueError: If k is below 1, the lists differ in length or are empty, or a value
        is not finite or a gain is negative.
    :return: The value from 0 to 1, or None if the ideal DCG is zero.
    """
    s, g = _check(scores, gains, k)
    n = len(s)
    cumulative = _discounts(n)
    ideal = float(np.sort(g)[::-1][:k] @ (cumulative[1 : min(n, k) + 1] - cumulative[: min(n, k)]))
    if ideal <= 0.0:
        return None
    order = np.argsort(-s, kind="stable")
    ranked_scores, ranked_gains = s[order], g[order]
    starts = np.concatenate(([0], np.flatnonzero(np.diff(ranked_scores) != 0) + 1))
    ends = np.concatenate((starts[1:], [n]))
    group_sizes = ends - starts
    group_means = np.add.reduceat(ranked_gains, starts) / group_sizes
    cut = np.minimum(np.arange(n + 1), k)
    weights = cumulative[cut[ends]] - cumulative[cut[starts]]
    return float(group_means @ weights) / ideal


@dataclass(frozen=True, slots=True)
class MeanNdcg:
    """Mean nDCG over queries, with the number of queries that could not be scored.

    :param mean: Mean over the scored queries, or None if there are none.
    :param n_queries: Number of queries given.
    :param n_excluded: Number of queries left out because no item has a positive gain.
    """

    mean: float | None
    n_queries: int
    n_excluded: int


def mean_ndcg(queries: Iterable[tuple[Values, Values]], k: int) -> MeanNdcg:
    """Average nDCG@k over queries, leaving out queries with no positive gain.

    Leaving them out (instead of counting them as 0 or 1) keeps the mean from depending on
    how many empty queries a sample happens to contain; the count is reported next to it.

    :param queries: Pairs of (scores, gains), one pair per query.
    :param k: Number of leading positions that count.
    :return: The mean and the counts.
    """
    values: list[float] = []
    total = 0
    for scores, gains in queries:
        total += 1
        value = ndcg_at_k(scores, gains, k)
        if value is not None:
            values.append(value)
    mean = math.fsum(values) / len(values) if values else None
    return MeanNdcg(mean=mean, n_queries=total, n_excluded=total - len(values))
