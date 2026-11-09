"""Immutable snapshot of a profile as the domain sees it, independent of storage."""

from dataclasses import dataclass, field
from uuid import UUID

from app.domain.privacy import GridCell
from app.domain.taxonomy import (
    EQUIPMENT_BY_CODE,
    MAX_CAPABILITY_LEVEL,
    MAX_INTENSITY,
    MIN_CAPABILITY_LEVEL,
    MIN_INTENSITY,
    CategoryCode,
    DistrictCode,
    EquipmentCode,
    SkillLevel,
    SportCode,
)


@dataclass(frozen=True, slots=True)
class SportEntry:
    """A sport a person practises and their self-declared skill in it."""

    sport: SportCode
    skill: SkillLevel = SkillLevel.BEGINNER


@dataclass(frozen=True, slots=True, repr=False)
class CapabilityEntry:
    """One declared capability: category, level 0-4 and the equipment used, if any.

    WARNING: the values are private data. The representation is masked so that an entry cannot
    leak through a log line, an error message or test output.

    :param category: Capability category.
    :param level: Ability to take part in training for the function, 0 (not possible) to 4.
    :param equipment: Equipment used for the function, or None.
    :raises ValueError: If the level is out of range or the equipment does not apply to the
        category.
    """

    category: CategoryCode
    level: int
    equipment: EquipmentCode | None = None

    def __repr__(self) -> str:
        """Mask the content so the private layer cannot leak through logs or test output."""
        return "CapabilityEntry(<private>)"

    def __post_init__(self) -> None:
        """Validate the level and the pairing of category and equipment."""
        if not MIN_CAPABILITY_LEVEL <= self.level <= MAX_CAPABILITY_LEVEL:
            raise ValueError("capability level is outside the allowed range")
        if (
            self.equipment is not None
            and self.category not in EQUIPMENT_BY_CODE[self.equipment].categories
        ):
            raise ValueError("equipment does not apply to the capability category")


@dataclass(frozen=True, slots=True, repr=False)
class FunctionalProfile:
    """Private layer: declared capabilities by category.

    WARNING: this data must never be serialised into a response, a log line, an error
    message or an exported feature. It may only be read by the functional-level function,
    which reduces it to a coarse level. For that reason the representation is masked.

    :param capabilities: Declared capabilities, at most one per category.
    :raises ValueError: If a category is declared twice.
    """

    capabilities: frozenset[CapabilityEntry]

    def __post_init__(self) -> None:
        """Reject two entries for one category."""
        categories = [entry.category for entry in self.capabilities]
        if len(categories) != len(set(categories)):
            raise ValueError("a category can be declared only once")

    def __repr__(self) -> str:
        """Mask the content so the private layer cannot leak through logs or test output."""
        return "FunctionalProfile(<private>)"

    @classmethod
    def empty(cls) -> "FunctionalProfile":
        """Return a profile that declares nothing."""
        return cls(capabilities=frozenset())

    def get(self, category: CategoryCode) -> CapabilityEntry | None:
        """Return the entry of a category, or None if it is not declared.

        :param category: Category to look up.
        :return: The declared entry or None.
        """
        for entry in self.capabilities:
            if entry.category == category:
                return entry
        return None


@dataclass(frozen=True, slots=True, kw_only=True)
class ProfileView:
    """Everything the matching needs to know about one profile.

    Holds the grid cell instead of coordinates and the district as a code. The functional
    layer is private (see FunctionalProfile); the cell is left out of ``repr`` because even a
    coarse location should not travel through log lines.

    :param id: Profile identifier.
    :param sports: Sports with skills, at most one entry per sport.
    :param intensity: Preferred training intensity, 1 (light) to 5 (hard).
    :param cell: Centre of the grid cell of the profile.
    :param district: Optional district, shown to the caller as a label only.
    :param functional: Private functional layer.
    :param is_visible: Whether the profile may appear in other people's feeds.
    :raises ValueError: If the intensity is out of range or a sport is listed twice.
    """

    id: UUID
    sports: frozenset[SportEntry]
    intensity: int
    cell: GridCell = field(repr=False)
    district: DistrictCode | None = None
    functional: FunctionalProfile = FunctionalProfile(capabilities=frozenset())
    is_visible: bool = True

    def __post_init__(self) -> None:
        """Validate the intensity and the uniqueness of sports."""
        if not MIN_INTENSITY <= self.intensity <= MAX_INTENSITY:
            raise ValueError("intensity is outside the allowed range")
        codes = [entry.sport for entry in self.sports]
        if len(codes) != len(set(codes)):
            raise ValueError("a sport can be listed only once")

    @property
    def sport_codes(self) -> frozenset[SportCode]:
        """Codes of all sports of the profile."""
        return frozenset(entry.sport for entry in self.sports)

    def skill_in(self, sport: SportCode) -> SkillLevel | None:
        """Return the skill in a sport, or None if the profile does not practise it.

        :param sport: Sport to look up.
        :return: The declared skill or None.
        """
        for entry in self.sports:
            if entry.sport == sport:
                return entry.skill
        return None
