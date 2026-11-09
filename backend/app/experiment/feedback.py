"""Simulated feedback: logged feeds, invitations and answers drawn from the world.

For every viewer the logging policy shows a feed produced by the default weighted baseline
with epsilon-greedy exploration. Who gets invited depends on the position (the first slots
are looked at more), and the answer of an invited candidate is drawn from the acceptance
probability of the world. Only invited pairs get a label (accepted or declined); pairs that
were not invited are missing, not negative.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from app.domain.matching.feed import eligible_candidates, rank, shield_functional
from app.domain.matching.scorer import Candidate, Scorer
from app.domain.matching.weighted import WeightedScorer
from app.domain.matching.weights import DEFAULT_WEIGHTS
from app.domain.profile import ProfileView
from app.experiment.world import World, stream

# Retrieval cap of the architecture decisions: the ranker sees at most this many candidates
DEFAULT_MAX_CANDIDATES = 200


@dataclass(frozen=True, slots=True)
class FeedbackParams:
    """Parameters of the logging policy and of the invitation behaviour.

    :param epsilon: Probability that a feed slot is filled by a uniformly random remaining
        candidate instead of the best remaining one.
    :param feed_size: Number of slots of a feed.
    :param invite_rate: Scale of the position bias; the chance to invite the candidate in
        slot r is min(1, invite_rate / log2(r + 1)).
    :param max_candidates: Retrieval cap, nearest candidates first.
    :raises ValueError: If a value is out of range.
    """

    epsilon: float = 0.3
    feed_size: int = 20
    invite_rate: float = 0.5
    max_candidates: int = DEFAULT_MAX_CANDIDATES

    def __post_init__(self) -> None:
        """Validate the parameters."""
        if not (math.isfinite(self.epsilon) and 0.0 <= self.epsilon <= 1.0):
            raise ValueError("epsilon must be between 0 and 1")
        if self.feed_size < 1 or self.max_candidates < 1:
            raise ValueError("feed_size and max_candidates must be at least 1")
        if not (math.isfinite(self.invite_rate) and self.invite_rate > 0):
            raise ValueError("invite_rate must be positive")


@dataclass(frozen=True, slots=True)
class Impression:
    """One slot of a logged feed.

    :param viewer_id: Who saw the feed.
    :param candidate_id: Who was shown in the slot.
    :param rank: Slot number, starting at 1.
    :param selection_propensity: Probability that the logging policy put this candidate in
        this slot given the slots before it.
    :param invite_probability: Probability that the viewer invites the candidate in this slot.
    :param invited: Whether the viewer invited the candidate.
    :param accepted: The answer if invited, otherwise None (missing, not negative).
    """

    viewer_id: UUID
    candidate_id: UUID
    rank: int
    selection_propensity: float
    invite_probability: float
    invited: bool
    accepted: bool | None

    @property
    def propensity(self) -> float:
        """Probability of the row being logged as an invitation, given the earlier slots."""
        return self.selection_propensity * self.invite_probability


@dataclass(frozen=True, slots=True)
class FeedbackLog:
    """All impressions of a simulation, grouped by viewer in the order given.

    :param impressions: Logged slots.
    """

    impressions: tuple[Impression, ...]

    def invited_rows(self) -> list[Impression]:
        """Return the labelled rows: impressions that led to an invitation.

        :return: Invited impressions in log order.
        """
        return [i for i in self.impressions if i.invited]


def selection_propensities(n_remaining: int, epsilon: float) -> list[float]:
    """Return the probability of every remaining candidate being chosen for the next slot.

    With probability 1 - epsilon the best remaining candidate (index 0) is chosen, with
    probability epsilon one is chosen uniformly. The values add up to 1.

    :param n_remaining: Number of candidates still available, at least 1.
    :param epsilon: Exploration probability.
    :return: One probability per remaining candidate, in baseline order.
    """
    uniform = epsilon / n_remaining
    return [(1.0 - epsilon) + uniform] + [uniform] * (n_remaining - 1)


def candidate_pool(
    viewer: ProfileView, profiles: Sequence[ProfileView], max_candidates: int
) -> list[Candidate]:
    """Return the retrieved candidates of a viewer: the feed rule, nearest first, capped.

    The functional data of a candidate who shares too few categories with the viewer is
    withheld, exactly as the matching service does before scoring (``shield_functional``), so
    the baselines and the ranker see what they see in the product. The candidates stay in the
    list; only their profile copy is masked, so the ground truth must be asked about the
    original profile (see ``simulate_feedback`` and ``evaluation_lists``).

    :param viewer: The viewer.
    :param profiles: Population to choose from.
    :param max_candidates: Retrieval cap.
    :return: Shielded eligible candidates ordered by distance and id, at most
        ``max_candidates``.
    """
    eligible = eligible_candidates(viewer, profiles)
    eligible.sort(key=lambda c: (c.distance_km, c.profile.id))
    return [shield_functional(viewer, c) for c in eligible[:max_candidates]]


def _viewer_feed(
    viewer: ProfileView,
    pool: list[Candidate],
    truth: Mapping[UUID, ProfileView],
    world: World,
    params: FeedbackParams,
    seed: int,
    scorer: Scorer,
) -> list[Impression]:
    """Simulate the feed, invitations and answers of one viewer.

    The pool holds shielded candidates; the answer is drawn from the original profile.
    """
    rng = stream(seed, "feedback", viewer.id)
    ranked = rank(scorer.score(viewer, pool), len(pool), scorer.keeps)
    remaining = [e.candidate for e in ranked]
    impressions: list[Impression] = []
    for slot in range(1, min(params.feed_size, len(remaining)) + 1):
        # All four draws are taken in every slot so the stream stays aligned
        explore, pick, invite, answer = rng.random(), rng.random(), rng.random(), rng.random()
        index = int(pick * len(remaining)) if explore < params.epsilon else 0
        propensities = selection_propensities(len(remaining), params.epsilon)
        chosen = remaining.pop(index)
        invite_probability = min(1.0, params.invite_rate / math.log2(slot + 1))
        invited = invite < invite_probability
        accepted = None
        if invited:
            accepted = answer < world.acceptance_probability(viewer, truth[chosen.profile.id])
        impressions.append(
            Impression(
                viewer_id=viewer.id,
                candidate_id=chosen.profile.id,
                rank=slot,
                selection_propensity=propensities[index],
                invite_probability=invite_probability,
                invited=invited,
                accepted=accepted,
            )
        )
    return impressions


def simulate_feedback(
    viewers: Sequence[ProfileView],
    profiles: Sequence[ProfileView],
    world: World,
    params: FeedbackParams,
    seed: int,
    scorer: Scorer | None = None,
) -> FeedbackLog:
    """Simulate logged feeds, invitations and answers for the viewers.

    Every viewer has an independent random stream derived from the seed and the viewer id,
    so the result for a viewer does not depend on the other viewers or on their order.

    :param viewers: Viewers whose feeds are logged.
    :param profiles: Population the candidates come from.
    :param world: Ground truth that answers the invitations.
    :param params: Logging policy and invitation behaviour.
    :param seed: Seed of the feedback streams.
    :param scorer: Logging policy; defaults to the weighted baseline with default weights.
    :return: The log of all impressions.
    """
    policy = scorer or WeightedScorer(DEFAULT_WEIGHTS)
    truth = {profile.id: profile for profile in profiles}
    impressions: list[Impression] = []
    for viewer in viewers:
        pool = candidate_pool(viewer, profiles, params.max_candidates)
        impressions.extend(_viewer_feed(viewer, pool, truth, world, params, seed, policy))
    return FeedbackLog(impressions=tuple(impressions))
