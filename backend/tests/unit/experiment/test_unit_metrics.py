import math
import random

import numpy as np
import pytest
from sklearn.metrics import ndcg_score

from app.experiment.metrics import mean_ndcg, ndcg_at_k


def test_hand_computed_case_without_ties():
    # DCG = 1/log2(2) + 0 + 2/log2(4) = 2; ideal order 2, 1, 0 gives 2 + 1/log2(3)
    value = ndcg_at_k([0.9, 0.5, 0.1], [1, 0, 2], k=3)

    assert value == pytest.approx(2 / (2 + 1 / math.log2(3)))


def test_hand_computed_case_with_one_tied_group():
    # All three tie: the relevant item is equally likely at every position
    value = ndcg_at_k([1.0, 1.0, 1.0], [1, 0, 0], k=3)

    assert value == pytest.approx((1 + 1 / math.log2(3) + 1 / 2) / 3)


def test_ties_are_cut_at_k_inside_the_group():
    # Only the first position counts, the item sits there with probability 1/3
    assert ndcg_at_k([1.0, 1.0, 1.0], [1, 0, 0], k=1) == pytest.approx(1 / 3)


def test_tied_group_after_a_distinct_leader():
    # Leader at position 1 (gain 0); the other two tie for positions 2 and 3 with gains 1 and 1
    value = ndcg_at_k([5.0, 1.0, 1.0], [0, 1, 1], k=3)

    dcg = 1 / math.log2(3) + 1 / 2
    ideal = 1 + 1 / math.log2(3)
    assert value == pytest.approx(dcg / ideal)


def test_real_valued_gains():
    value = ndcg_at_k([2.0, 1.0], [0.25, 0.75], k=2)

    assert value == pytest.approx((0.25 + 0.75 / math.log2(3)) / (0.75 + 0.25 / math.log2(3)))


def test_perfect_order_is_one_and_reversed_is_lower():
    gains = [3.0, 2.0, 1.0, 0.0]

    assert ndcg_at_k([4, 3, 2, 1], gains, k=4) == pytest.approx(1.0)
    assert ndcg_at_k([1, 2, 3, 4], gains, k=4) < 1.0


def test_query_without_positive_gain_has_no_value():
    assert ndcg_at_k([1.0, 2.0], [0.0, 0.0], k=2) is None


def test_k_larger_than_the_list_is_allowed():
    assert ndcg_at_k([2.0, 1.0], [1.0, 0.0], k=20) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("scores", "gains", "k"),
    [
        ([1.0], [1.0, 2.0], 1),
        ([1.0, 2.0], [1.0, -1.0], 2),
        ([1.0, float("nan")], [1.0, 1.0], 2),
        ([1.0, 2.0], [1.0, float("inf")], 2),
        ([1.0, 2.0], [1.0, 1.0], 0),
        ([], [], 1),
    ],
)
def test_invalid_input_is_rejected(scores, gains, k):
    with pytest.raises(ValueError):
        ndcg_at_k(scores, gains, k)


def test_value_does_not_depend_on_the_order_of_tied_items():
    rng = random.Random(5)
    scores = [2.0, 2.0, 2.0, 1.0, 1.0, 0.0]
    gains = [0.1, 0.9, 0.4, 0.0, 0.7, 0.3]
    expected = ndcg_at_k(scores, gains, k=4)
    for _ in range(20):
        order = list(range(len(scores)))
        rng.shuffle(order)
        shuffled = ndcg_at_k([scores[i] for i in order], [gains[i] for i in order], k=4)
        assert shuffled == pytest.approx(expected)


def test_value_does_not_depend_on_the_input_order_of_untied_items():
    scores, gains = [3.0, 1.0, 2.0], [0.2, 0.9, 0.5]

    assert ndcg_at_k(scores, gains, 3) == pytest.approx(ndcg_at_k(scores[::-1], gains[::-1], 3))


@pytest.mark.parametrize("seed", range(25))
def test_matches_scikit_learn_on_random_inputs_with_ties(seed):
    rng = np.random.default_rng(seed)
    n = int(rng.integers(2, 30))
    scores = rng.integers(0, 4, size=n).astype(float)  # few distinct values: many ties
    gains = rng.random(n) * (rng.random(n) < 0.6)
    k = int(rng.integers(1, n + 3))
    if gains.sum() == 0:
        gains[0] = 0.5

    ours = ndcg_at_k(scores.tolist(), gains.tolist(), k)

    reference = ndcg_score(gains[None, :], scores[None, :], k=k, ignore_ties=False)
    assert ours == pytest.approx(reference, abs=1e-12)


def test_mean_excludes_queries_without_positive_gain_and_counts_them():
    queries = [
        ([2.0, 1.0], [1.0, 0.0]),
        ([1.0, 2.0], [0.0, 0.0]),
        ([1.0, 2.0], [1.0, 0.0]),
    ]

    summary = mean_ndcg(queries, k=2)

    assert summary.n_queries == 3
    assert summary.n_excluded == 1
    assert summary.mean == pytest.approx((1.0 + ndcg_at_k([1.0, 2.0], [1.0, 0.0], 2)) / 2)


def test_mean_of_nothing_is_none():
    summary = mean_ndcg([([1.0, 2.0], [0.0, 0.0])], k=2)

    assert summary.mean is None
    assert (summary.n_queries, summary.n_excluded) == (1, 1)
