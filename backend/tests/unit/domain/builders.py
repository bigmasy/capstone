"""Small data builders for the domain tests."""

from collections.abc import Iterable
from uuid import UUID

from app.domain.privacy import GridCell
from app.domain.profile import CapabilityEntry, FunctionalProfile, ProfileView, SportEntry
from app.domain.taxonomy import (
    CategoryCode,
    DistrictCode,
    EquipmentCode,
    SkillLevel,
    SportCode,
)

# A cell centre in central Kyiv; builders place profiles on cell centres directly
CENTER_LAT = 50.45
CENTER_LON = 30.52

SportSpec = SportCode | str | tuple[SportCode | str, SkillLevel | str]
CapabilitySpec = tuple[CategoryCode | str, int, EquipmentCode | str | None]


def make_id(number: int) -> UUID:
    """Return a readable, ordered UUID: make_id(1) < make_id(2)."""
    return UUID(int=number)


def make_functional(*capabilities: CapabilitySpec) -> FunctionalProfile:
    """Build a functional profile from (category, level, equipment) tuples."""
    return FunctionalProfile(
        capabilities=frozenset(
            CapabilityEntry(
                category=CategoryCode(category),
                level=level,
                equipment=None if equipment is None else EquipmentCode(equipment),
            )
            for category, level, equipment in capabilities
        )
    )


def make_sports(specs: Iterable[SportSpec]) -> frozenset[SportEntry]:
    """Build sport entries from codes or (code, skill) tuples."""
    entries = []
    for spec in specs:
        if isinstance(spec, tuple):
            sport, skill = spec
        else:
            sport, skill = spec, SkillLevel.BEGINNER
        entries.append(SportEntry(sport=SportCode(sport), skill=SkillLevel(skill)))
    return frozenset(entries)


def make_profile(
    number: int = 1,
    sports: Iterable[SportSpec] = (SportCode.SWIMMING,),
    lat: float = CENTER_LAT,
    lon: float = CENTER_LON,
    intensity: int = 3,
    visible: bool = True,
    caps: Iterable[CapabilitySpec] = (),
    district: DistrictCode | None = None,
) -> ProfileView:
    """Build a profile view; ``number`` makes the id, ``lat``/``lon`` are the cell centre."""
    return ProfileView(
        id=make_id(number),
        sports=make_sports(sports),
        intensity=intensity,
        cell=GridCell(latitude=lat, longitude=lon),
        district=district,
        functional=make_functional(*caps),
        is_visible=visible,
    )
