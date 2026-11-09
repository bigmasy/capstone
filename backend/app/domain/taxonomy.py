"""Closed dictionaries for profile input: sports, functional categories, equipment, districts.

The lists describe what a person can do and which equipment they use, never a condition.
Codes are stable identifiers: lowercase snake_case, at most 50 characters (the column size),
never renamed or reused within a major version.
"""

from dataclasses import dataclass
from enum import StrEnum

# Minor: codes added; major: codes removed or renamed
TAXONOMY_VERSION = "1.0.0"

MIN_CAPABILITY_LEVEL = 0
MAX_CAPABILITY_LEVEL = 4
MIN_INTENSITY = 1
MAX_INTENSITY = 5


class SportCode(StrEnum):
    """Code of an adaptive sport."""

    SWIMMING = "swimming"
    ARCHERY = "archery"
    TABLE_TENNIS = "table_tennis"
    SITTING_VOLLEYBALL = "sitting_volleyball"
    WHEELCHAIR_BASKETBALL = "wheelchair_basketball"
    CYCLING = "cycling"
    HANDCYCLING = "handcycling"
    ROWING = "rowing"
    ATHLETICS = "athletics"
    GYM_FITNESS = "gym_fitness"
    POWERLIFTING = "powerlifting"
    YOGA_STRETCHING = "yoga_stretching"
    BADMINTON = "badminton"
    NORDIC_WALKING = "nordic_walking"


class CategoryCode(StrEnum):
    """Code of a capability category (what a person can do, not a condition)."""

    MOBILITY_LOWER = "mobility_lower"
    MOBILITY_UPPER = "mobility_upper"
    BALANCE_POSTURE = "balance_posture"
    ENDURANCE = "endurance"
    DEXTERITY = "dexterity"
    VISION = "vision"
    HEARING = "hearing"


class EquipmentCode(StrEnum):
    """Code of a piece of equipment a person uses."""

    WHEELCHAIR_ACTIVE = "wheelchair_active"
    HANDCYCLE = "handcycle"
    CRUTCHES_OR_CANE = "crutches_or_cane"
    PROSTHESIS_LOWER_LIMB = "prosthesis_lower_limb"
    RUNNING_BLADE = "running_blade"
    PROSTHESIS_UPPER_LIMB = "prosthesis_upper_limb"
    GUIDE_SUPPORT = "guide_support"
    HEARING_AID = "hearing_aid"


class DistrictCode(StrEnum):
    """Code of an administrative district; the prefix keeps codes unique across cities."""

    KYIV_HOLOSIIVSKYI = "kyiv_holosiivskyi"
    KYIV_DARNYTSKYI = "kyiv_darnytskyi"
    KYIV_DESNIANSKYI = "kyiv_desnianskyi"
    KYIV_DNIPROVSKYI = "kyiv_dniprovskyi"
    KYIV_OBOLONSKYI = "kyiv_obolonskyi"
    KYIV_PECHERSKYI = "kyiv_pecherskyi"
    KYIV_PODILSKYI = "kyiv_podilskyi"
    KYIV_SVIATOSHYNSKYI = "kyiv_sviatoshynskyi"
    KYIV_SOLOMIANSKYI = "kyiv_solomianskyi"
    KYIV_SHEVCHENKIVSKYI = "kyiv_shevchenkivskyi"


class SkillLevel(StrEnum):
    """Self-declared skill in one sport, ordered from beginner to advanced."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

    @property
    def rank(self) -> int:
        """Position in the order beginner (0), intermediate (1), advanced (2)."""
        return _SKILL_ORDER.index(self)


_SKILL_ORDER = (SkillLevel.BEGINNER, SkillLevel.INTERMEDIATE, SkillLevel.ADVANCED)


@dataclass(frozen=True, slots=True)
class Sport:
    """A sport with its display name."""

    code: SportCode
    name: str


@dataclass(frozen=True, slots=True)
class CapabilityCategory:
    """A capability category with its display name and a neutral description."""

    code: CategoryCode
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class Equipment:
    """A piece of equipment and the categories it can be attached to."""

    code: EquipmentCode
    name: str
    categories: tuple[CategoryCode, ...]


@dataclass(frozen=True, slots=True)
class District:
    """A district with its display name."""

    code: DistrictCode
    name: str


@dataclass(frozen=True, slots=True)
class CapabilityLevelInfo:
    """A capability level (0-4) with its wording (a working draft)."""

    value: int
    label: str


SPORTS = (
    Sport(SportCode.SWIMMING, "Swimming"),
    Sport(SportCode.ARCHERY, "Archery"),
    Sport(SportCode.TABLE_TENNIS, "Table tennis"),
    Sport(SportCode.SITTING_VOLLEYBALL, "Sitting volleyball"),
    Sport(SportCode.WHEELCHAIR_BASKETBALL, "Wheelchair basketball"),
    Sport(SportCode.CYCLING, "Cycling"),
    Sport(SportCode.HANDCYCLING, "Handcycling"),
    Sport(SportCode.ROWING, "Rowing"),
    Sport(SportCode.ATHLETICS, "Athletics"),
    Sport(SportCode.GYM_FITNESS, "Gym and fitness"),
    Sport(SportCode.POWERLIFTING, "Powerlifting"),
    Sport(SportCode.YOGA_STRETCHING, "Yoga and stretching"),
    Sport(SportCode.BADMINTON, "Badminton"),
    Sport(SportCode.NORDIC_WALKING, "Nordic walking"),
)

CATEGORIES = (
    CapabilityCategory(
        CategoryCode.MOBILITY_LOWER,
        "Moving on foot",
        "standing, walking, climbing steps, running",
    ),
    CapabilityCategory(
        CategoryCode.MOBILITY_UPPER,
        "Using arms for movement and load",
        "reaching, pushing, pulling, carrying",
    ),
    CapabilityCategory(
        CategoryCode.BALANCE_POSTURE,
        "Balance and posture",
        "keeping balance and a stable position while sitting or standing",
    ),
    CapabilityCategory(
        CategoryCode.ENDURANCE,
        "Sustaining effort",
        "keeping up physical effort over time",
    ),
    CapabilityCategory(
        CategoryCode.DEXTERITY,
        "Fine hand movements",
        "gripping, throwing, handling small equipment",
    ),
    CapabilityCategory(
        CategoryCode.VISION,
        "Seeing and orienting",
        "following a course, seeing equipment and markings",
    ),
    CapabilityCategory(
        CategoryCode.HEARING,
        "Hearing instructions",
        "following spoken instructions and signals in a training setting",
    ),
)

EQUIPMENT = (
    Equipment(
        EquipmentCode.WHEELCHAIR_ACTIVE,
        "Active (sports) wheelchair",
        (CategoryCode.MOBILITY_LOWER,),
    ),
    Equipment(EquipmentCode.HANDCYCLE, "Handcycle", (CategoryCode.MOBILITY_LOWER,)),
    Equipment(
        EquipmentCode.CRUTCHES_OR_CANE,
        "Crutches or cane",
        (CategoryCode.MOBILITY_LOWER, CategoryCode.BALANCE_POSTURE),
    ),
    Equipment(
        EquipmentCode.PROSTHESIS_LOWER_LIMB,
        "Lower-limb prosthesis",
        (CategoryCode.MOBILITY_LOWER,),
    ),
    Equipment(
        EquipmentCode.RUNNING_BLADE,
        "Running prosthesis",
        (CategoryCode.MOBILITY_LOWER,),
    ),
    Equipment(
        EquipmentCode.PROSTHESIS_UPPER_LIMB,
        "Upper-limb prosthesis",
        (CategoryCode.MOBILITY_UPPER, CategoryCode.DEXTERITY),
    ),
    Equipment(EquipmentCode.GUIDE_SUPPORT, "Sighted guide or tether", (CategoryCode.VISION,)),
    Equipment(EquipmentCode.HEARING_AID, "Hearing aid", (CategoryCode.HEARING,)),
)

DISTRICTS = (
    District(DistrictCode.KYIV_HOLOSIIVSKYI, "Kyiv, Holosiivskyi"),
    District(DistrictCode.KYIV_DARNYTSKYI, "Kyiv, Darnytskyi"),
    District(DistrictCode.KYIV_DESNIANSKYI, "Kyiv, Desnianskyi"),
    District(DistrictCode.KYIV_DNIPROVSKYI, "Kyiv, Dniprovskyi"),
    District(DistrictCode.KYIV_OBOLONSKYI, "Kyiv, Obolonskyi"),
    District(DistrictCode.KYIV_PECHERSKYI, "Kyiv, Pecherskyi"),
    District(DistrictCode.KYIV_PODILSKYI, "Kyiv, Podilskyi"),
    District(DistrictCode.KYIV_SVIATOSHYNSKYI, "Kyiv, Sviatoshynskyi"),
    District(DistrictCode.KYIV_SOLOMIANSKYI, "Kyiv, Solomianskyi"),
    District(DistrictCode.KYIV_SHEVCHENKIVSKYI, "Kyiv, Shevchenkivskyi"),
)

# Level of a capability: the ability to take part in training for the function
# (higher means more capable). The wording is a working draft.
LEVELS = (
    CapabilityLevelInfo(0, "not possible"),
    CapabilityLevelInfo(1, "only with substantial help or adaptation"),
    CapabilityLevelInfo(2, "with adaptation or equipment"),
    CapabilityLevelInfo(3, "mostly independent"),
    CapabilityLevelInfo(4, "fully independent"),
)

EQUIPMENT_BY_CODE = {e.code: e for e in EQUIPMENT}
