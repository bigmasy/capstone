"""Baselines of the comparison: B0 (default weights) and B1 (weights fitted on the same labels).

The weighted scorer is recomputed here from the feature matrix instead of being called once
per candidate and weight vector: the grid has 1771 vectors, so the per-criterion shares are
computed once and every vector is a matrix product plus a rounding to tenths. A test checks
that the results equal ``WeightedScorer`` exactly.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import product

import numpy as np
from numpy.typing import NDArray

from app.domain.functional import FunctionalLevel
from app.domain.matching.features import FEATURE_NAMES
from app.domain.matching.weights import DEFAULT_TABLES, WEIGHT_TOTAL, Weights
from app.domain.privacy import DistanceBand
from app.domain.taxonomy import MAX_INTENSITY, MIN_INTENSITY
from app.experiment.metrics import mean_ndcg
from app.ranking.features import QueryData

_Float = NDArray[np.float64]
_COLUMN = {name: index for index, name in enumerate(FEATURE_NAMES)}
_INTENSITY_RANGE = MAX_INTENSITY - MIN_INTENSITY
# Share tables in the order of the integer ranks the features carry
_DISTANCE_SHARE = np.array([float(DEFAULT_TABLES.distance_share[b]) for b in DistanceBand])
_FUNCTIONAL_SHARE = np.array([float(DEFAULT_TABLES.functional_share[f]) for f in FunctionalLevel])


def weight_grid(step: int) -> list[Weights]:
    """Return every weight vector of non-negative multiples of ``step`` that adds up to 100.

    :param step: Grid step; it must divide 100.
    :raises ValueError: If the step does not divide 100.
    :return: Weight vectors in lexicographic order of (sport, distance, functional).
    """
    if step < 1 or WEIGHT_TOTAL % step:
        raise ValueError("step must divide the weight total")
    units = WEIGHT_TOTAL // step
    return [
        Weights(sport=s * step, distance=d * step, functional=f * step, intensity=i * step)
        for s, d, f in product(range(units + 1), repeat=3)
        if (i := units - s - d - f) >= 0
    ]


def baseline_shares(matrix: _Float) -> _Float:
    """Return the share of each criterion earned by every row of a feature matrix.

    :param matrix: Feature matrix with the columns of FEATURE_NAMES.
    :return: Array of shape (rows, 4) with the columns sport, distance, intensity,
        functional, each from 0 to 1.
    """
    sport = matrix[:, _COLUMN["sport_jaccard"]]
    distance = _DISTANCE_SHARE[matrix[:, _COLUMN["distance_band"]].astype(int)]
    intensity = 1.0 - matrix[:, _COLUMN["intensity_diff_abs"]] / _INTENSITY_RANGE
    functional = _FUNCTIONAL_SHARE[matrix[:, _COLUMN["functional_level"]].astype(int)]
    return np.column_stack([sport, distance, intensity, functional])


def _tenths(shares: _Float, weights: Weights) -> _Float:
    """Points per criterion in integer tenths, rounded half to even like the scorer."""
    vector = np.array([weights.sport, weights.distance, weights.intensity, weights.functional])
    return np.rint(shares * vector * 10.0)  # type: ignore[no-any-return]


def baseline_scores(matrix: _Float, weights: Weights) -> _Float:
    """Return the weighted baseline score (0 to 100) of every row of a feature matrix.

    :param matrix: Feature matrix with the columns of FEATURE_NAMES.
    :param weights: Weights of the criteria.
    :return: One score per row, equal to ``WeightedScorer`` on the same pair.
    """
    return _tenths(baseline_shares(matrix), weights).sum(axis=1) / 10.0  # type: ignore[no-any-return]


@dataclass(frozen=True, slots=True)
class FittedBaseline:
    """Result of the grid search.

    :param weights: Best weights; the first of equal ones in grid order.
    :param validation_ndcg: Mean nDCG@k of the weights on the selection queries.
    """

    weights: Weights
    validation_ndcg: float


def select_b1(queries: Sequence[QueryData], k: int, grid: Sequence[Weights]) -> FittedBaseline:
    """Pick the weights with the highest mean nDCG@k on labelled queries.

    The shares are computed once per query; ties between weight vectors go to the one that
    comes first in the grid, so the result does not depend on floating-point noise.

    :param queries: Validation queries with binary labels.
    :param k: Cut-off of the nDCG.
    :param grid: Candidate weight vectors.
    :raises ValueError: If there are no queries, or none has a positive label.
    :return: The best weights and their score.
    """
    if not queries or not grid:
        raise ValueError("selection needs queries and a grid")
    shares = [baseline_shares(q.X) for q in queries]
    best: FittedBaseline | None = None
    for weights in grid:
        scored = [
            (_tenths(s, weights).sum(axis=1), q.y) for s, q in zip(shares, queries, strict=True)
        ]
        value = mean_ndcg(scored, k).mean
        if value is None:
            raise ValueError("no selection query has a positive label")
        if best is None or value > best.validation_ndcg + 1e-12:
            best = FittedBaseline(weights=weights, validation_ndcg=value)
    if best is None:
        raise ValueError("selection needs queries and a grid")
    return best
