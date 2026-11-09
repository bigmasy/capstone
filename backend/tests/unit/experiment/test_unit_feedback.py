import math

import pytest

from app.domain.matching.feed import eligible_candidates, rank
from app.domain.matching.weighted import WeightedScorer
from app.domain.matching.weights import DEFAULT_WEIGHTS
from app.experiment.feedback import (
    FeedbackParams,
    candidate_pool,
    selection_propensities,
    simulate_feedback,
)
from app.experiment.world import World, get_world_spec
from app.synthetic import GeneratorParams, generate_profiles


@pytest.fixture(scope="module")
def population():
    return generate_profiles(GeneratorParams(count=120), 11)


@pytest.fixture(scope="module")
def world():
    return World(get_world_spec("additive"), seed=11)


def test_selection_propensities_sum_to_one_for_every_state():
    for n in (1, 2, 5, 40):
        for epsilon in (0.0, 0.3, 1.0):
            assert sum(selection_propensities(n, epsilon)) == pytest.approx(1.0)


def test_selection_propensities_mix_greedy_and_uniform():
    values = selection_propensities(4, 0.3)

    assert values[0] == pytest.approx(0.7 + 0.3 / 4)
    assert values[1:] == [pytest.approx(0.3 / 4)] * 3


def test_feedback_is_deterministic(population, world):
    viewers = population[:20]

    a = simulate_feedback(viewers, population, world, FeedbackParams(), seed=4)
    b = simulate_feedback(viewers, population, world, FeedbackParams(), seed=4)
    c = simulate_feedback(viewers, population, world, FeedbackParams(), seed=5)

    assert a == b
    assert a != c


def test_a_viewer_feed_does_not_depend_on_the_other_viewers(population, world):
    alone = simulate_feedback(population[3:4], population, world, FeedbackParams(), seed=4)
    together = simulate_feedback(population[:10], population, world, FeedbackParams(), seed=4)

    mine = [i for i in together.impressions if i.viewer_id == population[3].id]
    assert list(alone.impressions) == mine


def test_without_exploration_the_feed_is_the_baseline_order(population, world):
    viewer = population[0]
    params = FeedbackParams(epsilon=0.0, feed_size=15)
    pool = [c.profile for c in candidate_pool(viewer, population, params.max_candidates)]

    log = simulate_feedback([viewer], population, world, params, seed=1)

    scorer = WeightedScorer(DEFAULT_WEIGHTS)
    expected = rank(scorer.score(viewer, eligible_candidates(viewer, pool)), 15, scorer.keeps)
    shown = [i.candidate_id for i in sorted(log.impressions, key=lambda i: i.rank)]
    assert shown == [e.candidate.profile.id for e in expected][: len(shown)]
    assert all(i.selection_propensity == 1.0 for i in log.impressions)


def test_with_full_exploration_every_selection_propensity_is_uniform(population, world):
    viewer = population[0]
    params = FeedbackParams(epsilon=1.0, feed_size=5, invite_rate=1.0)

    log = simulate_feedback([viewer], population, world, params, seed=1)

    n = len(candidate_pool(viewer, population, params.max_candidates))
    by_rank = {i.rank: i for i in log.impressions}
    for r, impression in by_rank.items():
        assert impression.selection_propensity == pytest.approx(1 / (n - r + 1))


def test_propensity_is_selection_times_position_biased_invitation(population, world):
    log = simulate_feedback(population[:30], population, world, FeedbackParams(), seed=2)

    assert log.impressions
    for i in log.impressions:
        assert 0 < i.selection_propensity <= 1
        assert i.invite_probability == pytest.approx(min(1.0, 0.5 / math.log2(i.rank + 1)))
        assert i.propensity == pytest.approx(i.selection_propensity * i.invite_probability)


def test_only_invited_rows_have_a_label(population, world):
    log = simulate_feedback(population[:40], population, world, FeedbackParams(), seed=2)

    assert any(i.invited for i in log.impressions)
    assert any(not i.invited for i in log.impressions)
    for i in log.impressions:
        assert (i.accepted is None) == (not i.invited)
    assert {i.accepted for i in log.invited_rows()} == {True, False}


def test_feed_size_and_ranks_are_respected(population, world):
    params = FeedbackParams(feed_size=7)

    log = simulate_feedback(population[:10], population, world, params, seed=2)

    for viewer in population[:10]:
        ranks = [i.rank for i in log.impressions if i.viewer_id == viewer.id]
        assert ranks == list(range(1, len(ranks) + 1))
        assert len(ranks) <= 7


def test_higher_ranks_are_invited_more_often(population, world):
    params = FeedbackParams(epsilon=0.3, feed_size=20, invite_rate=1.0)
    log = simulate_feedback(population, population, world, params, seed=3)

    def rate(lo, hi):
        rows = [i for i in log.impressions if lo <= i.rank <= hi]
        return sum(i.invited for i in rows) / len(rows)

    assert rate(1, 2) > rate(15, 20)


def test_observed_acceptance_matches_the_world_probability(population, world):
    log = simulate_feedback(population, population, world, FeedbackParams(), seed=3)
    by_id = {p.id: p for p in population}
    rows = log.invited_rows()

    expected = sum(
        world.acceptance_probability(by_id[i.viewer_id], by_id[i.candidate_id]) for i in rows
    )
    observed = sum(bool(i.accepted) for i in rows)

    assert len(rows) > 200
    assert abs(observed - expected) < 4 * math.sqrt(len(rows) * 0.25)


def test_candidate_pool_follows_the_retrieval_rule_and_cap(population):
    viewer = population[0]

    pool = candidate_pool(viewer, population, max_candidates=5)

    assert len(pool) <= 5
    for c in pool:
        assert c.profile.id != viewer.id and c.profile.is_visible
        assert viewer.sport_codes & c.profile.sport_codes
    assert [c.distance_km for c in pool] == sorted(c.distance_km for c in pool)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"epsilon": -0.1},
        {"epsilon": 1.5},
        {"feed_size": 0},
        {"invite_rate": 0.0},
        {"max_candidates": 0},
    ],
)
def test_invalid_parameters_are_rejected(kwargs):
    with pytest.raises(ValueError):
        FeedbackParams(**kwargs)
