"""Functional compatibility of two profiles: similarity of declared ability per category.

Exact rational arithmetic keeps threshold comparisons platform-independent. The numeric
index never leaves the domain: the caller receives only a coarse level.
"""

from enum import StrEnum
from fractions import Fraction

from app.domain.profile import FunctionalProfile
from app.domain.taxonomy import MAX_CAPABILITY_LEVEL, CategoryCode

# Author's assumptions, not calibrated
EQUIPMENT_SHARE = Fraction(1, 4)
HIGH_THRESHOLD = Fraction(3, 4)
MEDIUM_THRESHOLD = Fraction(1, 2)
# Fewer shared categories than this and the functional level is not used at all
MIN_SHARED_CATEGORIES = 2


class FunctionalLevel(StrEnum):
    """Coarse functional compatibility; the only form of it that may be shown or learned."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def rank(self) -> int:
        """Position in the order low (0), medium (1), high (2)."""
        return _LEVEL_ORDER.index(self)


_LEVEL_ORDER = (FunctionalLevel.LOW, FunctionalLevel.MEDIUM, FunctionalLevel.HIGH)


def similarity_index(a: FunctionalProfile, b: FunctionalProfile) -> Fraction | None:
    """Return the mean similarity over the categories declared by both profiles.

    A category declared by only one profile is ignored: absence means "not declared", not
    "no limitation". The per-category similarity is one minus the level gap over the maximum
    level; when both sides name equipment, equal equipment is worth a quarter of it. The
    index is private: callers outside the domain use functional_level instead.

    :param a: First functional profile.
    :param b: Second functional profile.
    :return: The index from 0 to 1, or None if the profiles share no declared category.
    """
    own = {entry.category: entry for entry in a.capabilities}
    other = {entry.category: entry for entry in b.capabilities}
    common = sorted(own.keys() & other.keys())
    if not common:
        return None
    total = Fraction(0)
    for category in common:
        left, right = own[category], other[category]
        sim = Fraction(MAX_CAPABILITY_LEVEL - abs(left.level - right.level), MAX_CAPABILITY_LEVEL)
        if left.equipment is not None and right.equipment is not None:
            same = Fraction(int(left.equipment == right.equipment))
            sim = (1 - EQUIPMENT_SHARE) * sim + EQUIPMENT_SHARE * same
        total += sim
    return total / len(common)


def functional_level(a: FunctionalProfile, b: FunctionalProfile) -> FunctionalLevel:
    """Return the coarse level of the similarity index.

    Without comparable data the level is neutral (medium). The neutral value makes "no data"
    indistinguishable from a real medium result, so the level does not reveal which
    categories the other profile declared. Thresholds are inclusive: 3/4 is high, 1/2 is
    medium.

    :param a: First functional profile.
    :param b: Second functional profile.
    :return: Low, medium or high.
    """
    index = similarity_index(a, b)
    if index is None:
        return FunctionalLevel.MEDIUM
    if index >= HIGH_THRESHOLD:
        return FunctionalLevel.HIGH
    if index >= MEDIUM_THRESHOLD:
        return FunctionalLevel.MEDIUM
    return FunctionalLevel.LOW


def has_enough_shared_categories(
    viewer_categories: frozenset[CategoryCode],
    candidate_categories: frozenset[CategoryCode],
    minimum: int = MIN_SHARED_CATEGORIES,
) -> bool:
    """Tell whether two profiles declare enough common categories to compare them.

    With a single shared category the coarse level would reveal whether the candidate has that
    exact category and roughly how limited they are in it, so a viewer could probe for it by
    declaring just one. The rule makes a comparison possible only when at least ``minimum``
    categories are declared by both; otherwise the caller must treat the functional level as
    unavailable.

    :param viewer_categories: Categories declared by the viewer.
    :param candidate_categories: Categories declared by the candidate.
    :param minimum: Smallest number of shared categories that allows the comparison.
    :raises ValueError: If ``minimum`` is less than 1.
    :return: True if at least ``minimum`` categories are declared by both.
    """
    if minimum < 1:
        raise ValueError("minimum must be at least 1")
    return len(viewer_categories & candidate_categories) >= minimum


def shield_insufficient_overlap(
    viewer: FunctionalProfile, other: FunctionalProfile
) -> FunctionalProfile:
    """Return the functional profile of ``other`` that may be compared with the viewer's.

    With a single shared category the coarse level would reveal whether the other profile has
    that exact category and roughly how limited they are in it, so a viewer could probe for it
    by declaring just one. Unless at least ``MIN_SHARED_CATEGORIES`` categories are declared by
    both, the other profile is treated as declaring nothing; the level is then the neutral
    "medium" that "no data" always gives, so the two cases cannot be told apart.

    :param viewer: Functional profile of the viewer.
    :param other: Functional profile of the candidate.
    :return: ``other`` itself if the overlap is large enough, otherwise an empty profile.
    """
    mine = frozenset(entry.category for entry in viewer.capabilities)
    theirs = frozenset(entry.category for entry in other.capabilities)
    if has_enough_shared_categories(mine, theirs):
        return other
    return FunctionalProfile.empty()
