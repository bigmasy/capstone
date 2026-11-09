"""Building the data of one generation: viewer splits, labelled queries and test lists."""

from collections.abc import Mapping, Sequence
from uuid import UUID

import numpy as np

from app.domain.matching.feed import shield_functional
from app.domain.matching.scorer import Candidate
from app.domain.profile import ProfileView
from app.experiment.feedback import FeedbackLog, candidate_pool
from app.experiment.world import World, stream
from app.ranking.features import QueryData, feature_matrix


def split_viewers(
    profiles: Sequence[ProfileView], shares: tuple[float, float, float], seed: int
) -> tuple[list[ProfileView], list[ProfileView], list[ProfileView]]:
    """Split viewers into train, validation and test, by viewer and not by row.

    Every viewer lands in exactly one part, so no list of a test viewer is seen in training.
    The order is a random key per profile, drawn from a stream of its own.

    :param profiles: All profiles of the generation, in generation order.
    :param shares: Shares of train, validation and test; they add up to 1.
    :param seed: Seed of the split.
    :return: The three parts.
    """
    rng = stream(seed, "split")
    keyed = sorted((rng.random(), index) for index in range(len(profiles)))
    ordered = [profiles[index] for _, index in keyed]
    n_train = round(shares[0] * len(ordered))
    n_valid = round(shares[1] * len(ordered))
    return ordered[:n_train], ordered[n_train : n_train + n_valid], ordered[n_train + n_valid :]


def logged_queries(
    log: FeedbackLog, viewers: Sequence[ProfileView], profiles: Mapping[UUID, ProfileView]
) -> list[QueryData]:
    """Return one labelled query per viewer from the invited rows of the log.

    Rows that were not invited are missing, not negative, so they do not appear. Viewers
    without any invited row yield no query.

    :param log: Logged impressions.
    :param viewers: Viewers whose queries are wanted, in the order of the result.
    :param profiles: All profiles by id.
    :return: The queries, with labels (1 accepted, 0 declined) and logging propensities.
    """
    rows_by_viewer: dict[UUID, list[tuple[UUID, bool, float]]] = {}
    for impression in log.invited_rows():
        rows_by_viewer.setdefault(impression.viewer_id, []).append(
            (impression.candidate_id, bool(impression.accepted), impression.propensity)
        )
    queries: list[QueryData] = []
    for viewer in viewers:
        rows = rows_by_viewer.get(viewer.id)
        if not rows:
            continue
        # The features are built from what the feed shows, so the overlap rule applies here too
        candidates = [
            shield_functional(viewer, Candidate.between(viewer, profiles[cid]))
            for cid, _, _ in rows
        ]
        queries.append(
            QueryData(
                X=feature_matrix(viewer, candidates),
                y=np.array([float(label) for _, label, _ in rows]),
                propensity=np.array([p for _, _, p in rows]),
            )
        )
    return queries


def evaluation_lists(
    viewers: Sequence[ProfileView],
    profiles: Sequence[ProfileView],
    world: World,
    max_candidates: int,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Return the evaluation lists: features and true acceptance probabilities per viewer.

    The list of a viewer is the full retrieved candidate list, with no dependence on who was
    shown or invited in the log. The features are those of the shielded candidates (the
    product's overlap rule); the gains come from the original profiles. Viewers without
    candidates are left out.

    :param viewers: Test viewers.
    :param profiles: Population the candidates come from.
    :param world: Ground truth giving the gains.
    :param max_candidates: Retrieval cap.
    :return: One (feature matrix, gains) pair per viewer that has candidates.
    """
    truth = {profile.id: profile for profile in profiles}
    lists = []
    for viewer in viewers:
        pool = candidate_pool(viewer, profiles, max_candidates)
        if not pool:
            continue
        gains = np.array([world.acceptance_probability(viewer, truth[c.profile.id]) for c in pool])
        lists.append((feature_matrix(viewer, pool), gains))
    return lists
