import random

import numpy as np
import pytest

from app.domain.matching.feed import eligible_candidates
from app.domain.matching.weighted import WeightedScorer
from app.domain.matching.weights import DEFAULT_WEIGHTS, Weights
from app.experiment.baselines import (
    baseline_scores,
    baseline_shares,
    select_b1,
    weight_grid,
)
from app.experiment.metrics import mean_ndcg
from app.ranking.features import QueryData, feature_matrix
from app.synthetic import GeneratorParams, generate_profiles


@pytest.fixture(scope="module")
def pairs():
    population = generate_profiles(GeneratorParams(count=60), 4)
    out = []
    for viewer in population[:15]:
        candidates = eligible_candidates(viewer, population)
        out.append((viewer, candidates, feature_matrix(viewer, candidates)))
    return out


def test_grid_holds_every_integer_weight_vector_in_steps_of_five():
    grid = weight_grid(5)

    assert len(grid) == 1771  # compositions of 20 into 4 non-negative parts
    assert len(set(grid)) == len(grid)
    assert all(
        sum((w.sport, w.distance, w.functional, w.intensity)) == 100
        and all(part % 5 == 0 for part in (w.sport, w.distance, w.functional, w.intensity))
        for w in grid
    )
    assert DEFAULT_WEIGHTS in grid


def test_grid_step_must_divide_one_hundred():
    with pytest.raises(ValueError):
        weight_grid(7)
    assert len(weight_grid(50)) == 10


def test_vectorised_scores_equal_the_weighted_scorer_for_random_weights(pairs):
    rng = random.Random(2)
    grid = weight_grid(5)
    for _ in range(25):
        weights = grid[rng.randrange(len(grid))]
        scorer = WeightedScorer(weights)
        for viewer, candidates, matrix in pairs:
            expected = [s.score for s in scorer.score(viewer, candidates)]
            assert baseline_scores(matrix, weights).tolist() == pytest.approx(expected, abs=1e-9)


def test_default_weights_reproduce_the_default_scores(pairs):
    viewer, candidates, matrix = pairs[0]

    expected = [s.score for s in WeightedScorer(DEFAULT_WEIGHTS).score(viewer, candidates)]

    assert baseline_scores(matrix, DEFAULT_WEIGHTS).tolist() == pytest.approx(expected)


def test_shares_are_between_zero_and_one(pairs):
    for _, _, matrix in pairs:
        shares = baseline_shares(matrix)
        assert shares.shape == (len(matrix), 4)
        assert shares.min() >= 0.0 and shares.max() <= 1.0


def _queries_where_only_distance_matters(pairs):
    queries = []
    for _, _, matrix in pairs:
        y = (matrix[:, 5] == 0).astype(float)
        if 0 < y.sum() < len(y):
            queries.append(QueryData(matrix, y))
    return queries


def test_b1_beats_or_equals_the_default_on_the_selection_queries_and_favours_distance(pairs):
    queries = _queries_where_only_distance_matters(pairs)
    assert len(queries) >= 5

    chosen = select_b1(queries, k=10, grid=weight_grid(5))

    def value(weights: Weights) -> float:
        return mean_ndcg([(baseline_scores(q.X, weights), q.y) for q in queries], 10).mean

    assert chosen.validation_ndcg == pytest.approx(value(chosen.weights))
    assert chosen.validation_ndcg >= value(DEFAULT_WEIGHTS) - 1e-12
    assert chosen.weights.distance >= 30


def test_b1_selection_is_deterministic_and_breaks_ties_by_grid_order(pairs):
    queries = _queries_where_only_distance_matters(pairs)

    first = select_b1(queries, k=10, grid=weight_grid(5))
    second = select_b1(queries, k=10, grid=weight_grid(5))

    assert first == second
    best = first.validation_ndcg
    earlier = [
        w
        for w in weight_grid(5)
        if w == first.weights
        or np.isclose(mean_ndcg([(baseline_scores(q.X, w), q.y) for q in queries], 10).mean, best)
    ]
    assert earlier[0] == first.weights


def test_b1_needs_queries():
    with pytest.raises(ValueError):
        select_b1([], k=10, grid=weight_grid(50))
