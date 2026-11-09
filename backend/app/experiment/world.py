"""Ground-truth acceptance model of the simulated world.

The world decides how likely a candidate is to accept an invitation. It is deliberately
independent of the weighted baseline: it has its own functional form, uses exact cell-centre
distances and latent traits the ranker never sees, and it must not import the baseline
weights (a test checks this). Everything here is an assumption of the simulation, not a
claim about real people.

The decision is taken from the candidate's side: the viewer invites, the candidate accepts
or declines. All random inputs are derived from hashes of the seed and the identifiers, so
the result of one pair does not depend on the order in which pairs are evaluated.
"""

import hashlib
import math
from dataclasses import dataclass, fields, replace
from enum import IntEnum
from random import Random
from statistics import NormalDist
from uuid import UUID

from app.domain.privacy import haversine_km
from app.domain.profile import ProfileView
from app.domain.taxonomy import MAX_CAPABILITY_LEVEL, CategoryCode

_NORMAL = NormalDist()
_UNIT_RESOLUTION = 2**64


def stream(seed: int, *parts: object) -> Random:
    """Return a random generator whose state depends only on the seed and the parts.

    Separate streams keep the experiment independent of the generator: drawing from one
    never shifts the draws of another.

    :param seed: Experiment seed.
    :param parts: Labels and identifiers that name the stream.
    :return: A new generator.
    """
    text = "|".join([str(seed), *(str(part) for part in parts)])
    return Random(int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:16], "big"))  # noqa: S311


def _unit(seed: int, *parts: object) -> float:
    """Return a hash-derived number strictly between 0 and 1."""
    text = "|".join([str(seed), *(str(part) for part in parts)])
    value = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    return (value + 0.5) / _UNIT_RESOLUTION


class Goal(IntEnum):
    """Latent training goal, ordered from relaxed to competitive."""

    RECREATION = 0
    FITNESS = 1
    COMPETITION = 2


# Goal shares per preferred intensity 1..5: harder training tends to go with competition
_GOAL_WEIGHTS = (
    (0.70, 0.25, 0.05),
    (0.55, 0.35, 0.10),
    (0.30, 0.45, 0.25),
    (0.15, 0.40, 0.45),
    (0.05, 0.30, 0.65),
)
_MAX_INTENSITY_GAP = 4.0


@dataclass(frozen=True, slots=True)
class WorldSpec:
    """Coefficients of one world; the logit is a sum of the terms described below.

    :param name: Name of the world.
    :param intercept: Base log-odds of acceptance.
    :param sport_weight: Weight of the saturating sport overlap.
    :param sport_saturation: Rate at which the overlap saturates.
    :param skill_gap_penalty: Loss of a shared sport's overlap per level of skill gap.
    :param distance_weight: Weight of the distance term exp(-km / distance_scale_km).
    :param distance_scale_km: Length scale of the distance decay.
    :param mobility_interaction: Extra weight of distance per unit of the candidate's
        lower-limb mobility deficit (0 switches the interaction off).
    :param functional_weight: Weight of the functional compatibility.
    :param functional_bottleneck: Mix of the worst category (1) and the mean (0).
    :param functional_default: Compatibility when no category is declared by both.
    :param equipment_bonus: Bonus when both name the same equipment in a shared category.
    :param intensity_up_penalty: Penalty when the viewer wants harder training than the
        candidate, per full intensity range.
    :param intensity_down_penalty: Penalty when the viewer wants easier training.
    :param goal_weight: Weight of the match of the latent goals.
    :param responsiveness_sd: Spread of the latent readiness of a candidate to accept.
    :param noise_sd: Spread of the noise of each ordered pair.
    :raises ValueError: If a coefficient is not finite or a scale is not positive.
    """

    name: str
    intercept: float
    sport_weight: float
    sport_saturation: float
    skill_gap_penalty: float
    distance_weight: float
    distance_scale_km: float
    mobility_interaction: float
    functional_weight: float
    functional_bottleneck: float
    functional_default: float
    equipment_bonus: float
    intensity_up_penalty: float
    intensity_down_penalty: float
    goal_weight: float
    responsiveness_sd: float
    noise_sd: float

    def __post_init__(self) -> None:
        """Validate the coefficients."""
        values = [getattr(self, f.name) for f in fields(self) if f.name != "name"]
        if not all(math.isfinite(v) for v in values):
            raise ValueError("world coefficients must be finite")
        if self.distance_scale_km <= 0 or self.sport_saturation <= 0:
            raise ValueError("scales must be positive")
        if not 0 <= self.functional_bottleneck <= 1:
            raise ValueError("functional_bottleneck must be between 0 and 1")
        if self.responsiveness_sd < 0 or self.noise_sd < 0:
            raise ValueError("spreads must not be negative")


# Shared scales; the worlds differ in the terms they switch on
_BASE = WorldSpec(
    name="base",
    intercept=-3.8,
    sport_weight=2.6,
    sport_saturation=0.8,
    skill_gap_penalty=0.0,
    distance_weight=2.8,
    distance_scale_km=10.0,
    mobility_interaction=0.0,
    functional_weight=2.2,
    functional_bottleneck=0.0,
    functional_default=0.6,
    equipment_bonus=0.0,
    intensity_up_penalty=0.9,
    intensity_down_penalty=0.9,
    goal_weight=0.0,
    responsiveness_sd=0.0,
    noise_sd=0.3,
)
# Null control: additive, symmetric, no latent traits, mean functional compatibility
_BASELINE_LIKE = replace(_BASE, name="baseline_like")
# Adds skill match, bottleneck functional form, equipment, asymmetric intensity, goal, readiness
_ADDITIVE = replace(
    _BASE,
    name="additive",
    skill_gap_penalty=0.35,
    functional_bottleneck=1.0,
    equipment_bonus=0.4,
    intensity_up_penalty=1.4,
    intensity_down_penalty=0.5,
    goal_weight=0.8,
    responsiveness_sd=0.5,
    noise_sd=0.5,
)
# Adds the distance by mobility interaction on top of the additive world
_INTERACTIONS = replace(_ADDITIVE, name="interactions", mobility_interaction=1.5)

_SPECS = {spec.name: spec for spec in (_BASELINE_LIKE, _ADDITIVE, _INTERACTIONS)}
WORLD_NAMES = tuple(_SPECS)


def get_world_spec(name: str) -> WorldSpec:
    """Return the coefficients of a named world.

    :param name: One of WORLD_NAMES.
    :raises ValueError: If the name is unknown.
    :return: The spec.
    """
    try:
        return _SPECS[name]
    except KeyError:
        raise ValueError(f"unknown world: {name}") from None


class World:
    """Ground truth of the simulation: the probability that a candidate accepts a viewer.

    :param spec: Coefficients of the world.
    :param seed: Seed of the latent traits and the pair noise.
    """

    def __init__(self, spec: WorldSpec, seed: int) -> None:
        """Create the world; no state is drawn until it is asked for."""
        self.spec = spec
        self.seed = seed

    def goal_of(self, profile: ProfileView) -> Goal:
        """Return the latent goal of a profile, drawn from its intensity and the seed.

        :param profile: The profile.
        :return: The goal.
        """
        weights = _GOAL_WEIGHTS[profile.intensity - 1]
        point = _unit(self.seed, "goal", profile.id)
        for goal, weight in zip(Goal, weights, strict=True):
            point -= weight
            if point < 0:
                return goal
        return Goal.COMPETITION

    def responsiveness_of(self, profile: ProfileView) -> float:
        """Return the latent readiness of a profile to accept invitations (log-odds).

        :param profile: The profile.
        :return: A draw from a normal distribution with the spread of the world.
        """
        z = _NORMAL.inv_cdf(_unit(self.seed, "responsiveness", profile.id))
        return self.spec.responsiveness_sd * z

    def pair_noise(self, viewer_id: UUID, candidate_id: UUID) -> float:
        """Return the noise of an ordered pair, derived from a hash of the seed and both ids.

        :param viewer_id: Identifier of the viewer.
        :param candidate_id: Identifier of the candidate.
        :return: A draw from a normal distribution with the spread of the world.
        """
        z = _NORMAL.inv_cdf(_unit(self.seed, "pair", viewer_id, candidate_id))
        return self.spec.noise_sd * z

    def logit(self, viewer: ProfileView, candidate: ProfileView) -> float:
        """Return the log-odds that the candidate accepts an invitation of the viewer.

        :param viewer: The viewer who invites.
        :param candidate: The candidate who decides.
        :return: The log-odds including latent traits and noise.
        """
        spec = self.spec
        total = spec.intercept
        total += spec.sport_weight * self._sport_term(viewer, candidate)
        total += self._distance_term(viewer, candidate)
        functional, equipment = self._functional_terms(viewer, candidate)
        total += spec.functional_weight * functional + spec.equipment_bonus * equipment
        total -= self._intensity_penalty(viewer, candidate)
        total += spec.goal_weight * self._goal_match(viewer, candidate)
        total += self.responsiveness_of(candidate)
        total += self.pair_noise(viewer.id, candidate.id)
        return total

    def acceptance_probability(self, viewer: ProfileView, candidate: ProfileView) -> float:
        """Return the probability that the candidate accepts an invitation of the viewer.

        :param viewer: The viewer who invites.
        :param candidate: The candidate who decides.
        :return: A probability strictly between 0 and 1.
        """
        x = self.logit(viewer, candidate)
        # Split by sign so exp never overflows
        if x >= 0:
            return 1.0 / (1.0 + math.exp(-x))
        e = math.exp(x)
        return e / (1.0 + e)

    def _sport_term(self, viewer: ProfileView, candidate: ProfileView) -> float:
        """Saturating overlap of shared sports, each weighted by the match of skills."""
        spec = self.spec
        mine = {entry.sport: entry.skill.rank for entry in viewer.sports}
        # Sorted so the float sum does not depend on the hash order of the set
        shared = sorted((e for e in candidate.sports if e.sport in mine), key=lambda e: e.sport)
        overlap = math.fsum(
            max(0.0, 1.0 - spec.skill_gap_penalty * abs(mine[e.sport] - e.skill.rank))
            for e in shared
        )
        return 1.0 - math.exp(-spec.sport_saturation * overlap)

    def _distance_term(self, viewer: ProfileView, candidate: ProfileView) -> float:
        """Exponential decay of the exact cell-centre distance, steeper for low mobility."""
        spec = self.spec
        km = haversine_km(viewer.cell, candidate.cell)
        decay = math.exp(-km / spec.distance_scale_km)
        entry = candidate.functional.get(CategoryCode.MOBILITY_LOWER)
        deficit = (
            0.0 if entry is None else (MAX_CAPABILITY_LEVEL - entry.level) / MAX_CAPABILITY_LEVEL
        )
        return spec.distance_weight * decay * (1.0 + spec.mobility_interaction * deficit)

    def _functional_terms(self, viewer: ProfileView, candidate: ProfileView) -> tuple[float, float]:
        """Compatibility over shared categories (mean/minimum mix) and the equipment match."""
        spec = self.spec
        compat: list[float] = []
        same_equipment = False
        for category in CategoryCode:
            mine, theirs = viewer.functional.get(category), candidate.functional.get(category)
            if mine is None or theirs is None:
                continue
            compat.append(1.0 - abs(mine.level - theirs.level) / MAX_CAPABILITY_LEVEL)
            if mine.equipment is not None and mine.equipment == theirs.equipment:
                same_equipment = True
        if not compat:
            return spec.functional_default, 0.0
        mean = math.fsum(compat) / len(compat)
        mixed = (1.0 - spec.functional_bottleneck) * mean + spec.functional_bottleneck * min(compat)
        return mixed, 1.0 if same_equipment else 0.0

    def _intensity_penalty(self, viewer: ProfileView, candidate: ProfileView) -> float:
        """Penalty for an intensity mismatch, larger when the viewer asks for more."""
        spec = self.spec
        gap = viewer.intensity - candidate.intensity
        if gap > 0:
            return spec.intensity_up_penalty * gap / _MAX_INTENSITY_GAP
        return spec.intensity_down_penalty * -gap / _MAX_INTENSITY_GAP

    def _goal_match(self, viewer: ProfileView, candidate: ProfileView) -> float:
        """1 for equal goals, one half for neighbouring goals, 0 otherwise."""
        distance = abs(int(self.goal_of(viewer)) - int(self.goal_of(candidate)))
        return {0: 1.0, 1: 0.5}.get(distance, 0.0)
