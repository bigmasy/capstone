"""Feature matrix and group array of the learned ranker.

The columns are exactly the coarse features of the domain (FEATURE_NAMES); nothing else is
added here, so what the model sees stays public or already shown to the caller.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from app.domain.matching.features import FEATURE_NAMES, pair_features
from app.domain.matching.scorer import Candidate
from app.domain.profile import ProfileView

_Float = NDArray[np.float64]


def feature_matrix(viewer: ProfileView, candidates: Sequence[Candidate]) -> _Float:
    """Return the features of the viewer-candidate pairs, one row per candidate.

    :param viewer: The viewer.
    :param candidates: Candidates in the order of the rows.
    :return: Array of shape (number of candidates, number of features), columns in the order
        of FEATURE_NAMES.
    """
    rows = [pair_features(viewer, candidate).as_vector() for candidate in candidates]
    return np.asarray(rows, dtype=np.float64).reshape(len(rows), len(FEATURE_NAMES))


@dataclass(frozen=True, slots=True)
class QueryData:
    """Rows of one query (one viewer): features, labels and, optionally, propensities.

    :param X: Feature matrix, one row per labelled candidate.
    :param y: Binary labels, 1 for accepted and 0 for declined.
    :param propensity: Logging propensity of each row, or None if unknown.
    :raises ValueError: If the shapes do not agree.
    """

    X: _Float
    y: _Float
    propensity: _Float | None = None

    def __post_init__(self) -> None:
        """Check that matrix, labels and propensities describe the same rows."""
        if self.X.ndim != 2 or self.y.ndim != 1 or len(self.X) != len(self.y):
            raise ValueError("features and labels must describe the same rows")
        if self.propensity is not None and self.propensity.shape != self.y.shape:
            raise ValueError("propensities and labels must describe the same rows")


@dataclass(frozen=True, slots=True)
class RankingData:
    """Stacked queries in the layout LightGBM expects.

    :param X: Feature matrix of all rows.
    :param y: Labels of all rows.
    :param group: Number of rows of each query, in order.
    :param propensity: Logging propensity of every row, or None.
    """

    X: _Float
    y: _Float
    group: NDArray[np.int32]
    propensity: _Float | None


def stack_queries(queries: Sequence[QueryData]) -> RankingData:
    """Stack queries into one matrix with a group array.

    :param queries: Queries in the order of the groups.
    :raises ValueError: If only some of the queries carry propensities.
    :return: The stacked data.
    """
    if not queries:
        raise ValueError("no queries to stack")
    has_p = [q.propensity is not None for q in queries]
    if any(has_p) and not all(has_p):
        raise ValueError("propensities must be given for all queries or for none")
    propensity = (
        np.concatenate([q.propensity for q in queries if q.propensity is not None])
        if all(has_p)
        else None
    )
    return RankingData(
        X=np.vstack([q.X for q in queries]),
        y=np.concatenate([q.y for q in queries]),
        group=np.asarray([len(q.y) for q in queries], dtype=np.int32),
        propensity=propensity,
    )
