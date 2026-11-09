"""Pure generation of synthetic profiles: no database, no I/O.

Determinism: a local Random(seed) is used, and only its random() and getrandbits() methods,
because the other helpers of the module changed between Python releases. All choices are made
from ordered tuples, so the result does not depend on hash randomization. Locations are
coarsened to grid cells right after they are drawn, so exact points never leave this module.
"""

import math
import uuid
from collections.abc import Sequence
from random import Random
from typing import TypeVar

from app.domain.privacy import coarsen
from app.domain.profile import (
    CapabilityEntry,
    FunctionalProfile,
    ProfileView,
    SportEntry,
)
from app.domain.taxonomy import (
    EQUIPMENT,
    CategoryCode,
    DistrictCode,
    EquipmentCode,
    SkillLevel,
    SportCode,
)
from app.synthetic.params import GeneratorParams

_T = TypeVar("_T")

KM_PER_DEGREE = 111.195
# Coordinates are rounded so that platform differences in math functions do not show up
COORD_DIGITS = 5

# Categories affected by each latent pattern; "multiple" picks them at random
PATTERN_CATEGORIES: dict[str, tuple[CategoryCode, ...]] = {
    "undeclared": (),
    "lower_mobility": (CategoryCode.MOBILITY_LOWER,),
    "upper_mobility": (CategoryCode.MOBILITY_UPPER,),
    "vision": (CategoryCode.VISION,),
    "hearing": (CategoryCode.HEARING,),
    "endurance_balance": (CategoryCode.ENDURANCE, CategoryCode.BALANCE_POSTURE),
}

_SKILLS = tuple(SkillLevel)
_CATEGORIES = tuple(CategoryCode)
_SPORTS = tuple(SportCode)


def _pick(rng: Random, weights: Sequence[float]) -> int:
    """Index chosen with the given weights."""
    point = rng.random() * sum(weights)
    for index, weight in enumerate(weights):
        point -= weight
        if point < 0:
            return index
    return len(weights) - 1


def _pick_distinct(
    rng: Random, items: Sequence[_T], weights: Sequence[float], count: int
) -> list[_T]:
    """Items chosen one by one without replacement, in the order they were drawn."""
    pool, remaining = list(items), list(weights)
    chosen: list[_T] = []
    for _ in range(count):
        index = _pick(rng, remaining)
        chosen.append(pool.pop(index))
        remaining.pop(index)
    return chosen


def _normal_pair(rng: Random) -> tuple[float, float]:
    """Two independent standard normal values (Box-Muller)."""
    radius = math.sqrt(-2 * math.log(1 - rng.random()))
    angle = 2 * math.pi * rng.random()
    return radius * math.cos(angle), radius * math.sin(angle)


def _location(rng: Random, params: GeneratorParams) -> tuple[float, float, DistrictCode | None]:
    """Exact point and district of one profile (the point is coarsened by the caller)."""
    district: DistrictCode | None
    if rng.random() < params.scatter_share:
        radius = params.scatter_radius_km * math.sqrt(rng.random())
        angle = 2 * math.pi * rng.random()
        east, north = radius * math.cos(angle), radius * math.sin(angle)
        district = None
    else:
        cluster = _pick(rng, params.cluster_weights)
        dx, dy = _normal_pair(rng)
        east = params.cluster_offsets_km[cluster][0] + dx * params.cluster_sigma_km
        north = params.cluster_offsets_km[cluster][1] + dy * params.cluster_sigma_km
        district = DistrictCode(params.cluster_districts[cluster])
        if rng.random() < params.district_omitted_share:
            district = None
    lat0, lon0 = params.anchor
    lat = lat0 + north / KM_PER_DEGREE
    lon = lon0 + east / (KM_PER_DEGREE * math.cos(math.radians(lat0)))
    return round(lat, COORD_DIGITS), round(lon, COORD_DIGITS), district


def _sports(rng: Random, params: GeneratorParams) -> frozenset[SportEntry]:
    """Sports with skills; at most one entry per sport."""
    counts = [c for c, _ in params.sports_count_weights]
    count = counts[_pick(rng, [w for _, w in params.sports_count_weights])]
    popularity = dict(params.sport_weights)
    weights = [popularity.get(code.value, params.default_sport_weight) for code in _SPORTS]
    return frozenset(
        SportEntry(sport=code, skill=_SKILLS[int(rng.random() * len(_SKILLS))])
        for code in _pick_distinct(rng, _SPORTS, weights, count)
    )


def _equipment_options(category: CategoryCode) -> list[EquipmentCode]:
    """Equipment that can be attached to the category, in taxonomy order."""
    return [e.code for e in EQUIPMENT if category in e.categories]


def _capabilities(rng: Random, params: GeneratorParams) -> FunctionalProfile:
    """Capability entries drawn from the latent pattern."""
    pattern = params.pattern_weights[_pick(rng, [w for _, w in params.pattern_weights])][0]
    if pattern == "multiple":
        count = 2 + int(rng.random() * 2)
        affected = _pick_distinct(rng, _CATEGORIES, [1] * len(_CATEGORIES), count)
    else:
        affected = list(PATTERN_CATEGORIES[pattern])
    entries: list[CapabilityEntry] = []
    if pattern != "undeclared":
        for category in _CATEGORIES:
            if category in affected:
                level = _pick(rng, params.affected_level_weights)
                options = _equipment_options(category)
                equipment = None
                if rng.random() < params.equipment_share and options:
                    equipment = options[int(rng.random() * len(options))]
                entries.append(CapabilityEntry(category=category, level=level, equipment=equipment))
            elif rng.random() < params.extra_declared_share:
                weights = [w for _, w in params.extra_level_weights]
                level = params.extra_level_weights[_pick(rng, weights)][0]
                entries.append(CapabilityEntry(category=category, level=level))
    return FunctionalProfile(capabilities=frozenset(entries))


def generate_profiles(params: GeneratorParams, seed: int) -> list[ProfileView]:
    """Generate ``params.count`` profiles; the same arguments give the same result.

    The profile at position i does not depend on the count, so a smaller population is a
    prefix of a larger one for the same seed (nested subsets for density sweeps).

    :param params: Distribution parameters, including the number of profiles.
    :param seed: Seed of the local random generator.
    :return: Profiles in generation order, with cell centres instead of exact points.
    """
    rng = Random(seed)  # noqa: S311 - simulation, not security
    result: list[ProfileView] = []
    for _ in range(params.count):
        profile_id = uuid.UUID(int=rng.getrandbits(128), version=4)
        lat, lon, district = _location(rng, params)
        sports = _sports(rng, params)
        intensity = 1 + _pick(rng, params.intensity_weights)
        visible = rng.random() < params.visible_share
        functional = _capabilities(rng, params)
        result.append(
            ProfileView(
                id=profile_id,
                sports=sports,
                intensity=intensity,
                cell=coarsen(lat, lon),
                district=district,
                functional=functional,
                is_visible=visible,
            )
        )
    return result
