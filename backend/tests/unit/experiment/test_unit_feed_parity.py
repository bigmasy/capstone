"""The experiment sees a candidate exactly as the matching service shows it to the scorer."""

import numpy as np
import pytest

from app.experiment.dataset import evaluation_lists, logged_queries
from app.experiment.feedback import FeedbackLog, Impression, candidate_pool
from app.experiment.world import World, get_world_spec
from app.ranking.features import feature_matrix
from tests.unit.domain.builders import make_profile
from tests.unit.services.test_unit_matching import VIEWER_USER, service

VIEWER = make_profile(1, caps=[("vision", 4, None), ("hearing", 4, None)])
# One shared category: masked
ONE_SHARED = make_profile(2, caps=[("vision", 0, None), ("endurance", 0, None)])
# Two shared categories: compared
TWO_SHARED = make_profile(3, caps=[("vision", 4, None), ("hearing", 2, None)])
# No shared category and no capabilities at all
NONE_SHARED = make_profile(4, caps=[("endurance", 1, None)])
EMPTY = make_profile(5)
POPULATION = [VIEWER, ONE_SHARED, TWO_SHARED, NONE_SHARED, EMPTY]


async def _service_candidates():
    matching, _ = service(VIEWER, POPULATION)
    page = await matching.get_matches(VIEWER_USER)
    return {entry.scored.candidate.profile.id: entry.scored.candidate for entry in page.entries}


async def test_the_experiment_and_the_service_mask_the_same_candidates_identically():
    from_service = await _service_candidates()

    from_experiment = {c.profile.id: c for c in candidate_pool(VIEWER, POPULATION, 200)}

    assert from_service.keys() == from_experiment.keys() == {p.id for p in POPULATION[1:]}
    for profile_id, candidate in from_experiment.items():
        assert candidate.profile.functional == from_service[profile_id].profile.functional
        assert candidate.distance_km == from_service[profile_id].distance_km
    assert from_experiment[ONE_SHARED.id].profile.functional.capabilities == frozenset()
    assert from_experiment[TWO_SHARED.id].profile.functional == TWO_SHARED.functional


async def test_the_experiment_features_equal_the_features_the_service_scores():
    from_service = await _service_candidates()
    pool = candidate_pool(VIEWER, POPULATION, 200)

    expected = feature_matrix(VIEWER, [from_service[c.profile.id] for c in pool])

    assert np.array_equal(feature_matrix(VIEWER, pool), expected)


def _impressions(candidates):
    return FeedbackLog(
        impressions=tuple(
            Impression(
                viewer_id=VIEWER.id,
                candidate_id=c.id,
                rank=i + 1,
                selection_propensity=0.5,
                invite_probability=0.5,
                invited=True,
                accepted=bool(i % 2),
            )
            for i, c in enumerate(candidates)
        )
    )


async def test_logged_training_rows_use_the_masked_features():
    from_service = await _service_candidates()
    chosen = [ONE_SHARED, TWO_SHARED, NONE_SHARED]
    by_id = {p.id: p for p in POPULATION}

    (query,) = logged_queries(_impressions(chosen), [VIEWER], by_id)

    assert np.array_equal(query.X, feature_matrix(VIEWER, [from_service[p.id] for p in chosen]))


@pytest.mark.parametrize("world_name", ["additive", "interactions"])
def test_the_ground_truth_is_asked_about_the_original_profiles(world_name):
    world = World(get_world_spec(world_name), seed=3)
    by_id = {p.id: p for p in POPULATION}

    ((_, gains),) = evaluation_lists([VIEWER], POPULATION, world, 200)

    pool = candidate_pool(VIEWER, POPULATION, 200)
    assert list(gains) == [world.acceptance_probability(VIEWER, by_id[c.profile.id]) for c in pool]
    # The mask changes what the world would answer, so asking the masked copy would be wrong
    masked = next(c.profile for c in pool if c.profile.id == ONE_SHARED.id)
    assert world.acceptance_probability(VIEWER, masked) != world.acceptance_probability(
        VIEWER, ONE_SHARED
    )
