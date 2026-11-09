"""Response model of the taxonomy route: codes only, labels belong to the client."""

from pydantic import BaseModel

from app.domain.taxonomy import (
    CATEGORIES,
    DISTRICTS,
    EQUIPMENT,
    MAX_CAPABILITY_LEVEL,
    MAX_INTENSITY,
    MIN_CAPABILITY_LEVEL,
    MIN_INTENSITY,
    SPORTS,
    TAXONOMY_VERSION,
    CategoryCode,
    DistrictCode,
    EquipmentCode,
    SkillLevel,
    SportCode,
)


class EquipmentRule(BaseModel):
    """An equipment code and the categories it may be attached to."""

    code: EquipmentCode
    categories: list[CategoryCode]


class TaxonomyResponse(BaseModel):
    """Versioned code lists used by profile input. Reference data, not personal data."""

    version: str
    sports: list[SportCode]
    categories: list[CategoryCode]
    equipment: list[EquipmentRule]
    districts: list[DistrictCode]
    skills: list[SkillLevel]
    capability_levels: list[int]
    intensities: list[int]

    @classmethod
    def current(cls) -> "TaxonomyResponse":
        """Build the response from the domain taxonomy.

        :return: The current code lists.
        """
        return cls(
            version=TAXONOMY_VERSION,
            sports=[item.code for item in SPORTS],
            categories=[item.code for item in CATEGORIES],
            equipment=[
                EquipmentRule(code=item.code, categories=list(item.categories))
                for item in EQUIPMENT
            ],
            districts=[item.code for item in DISTRICTS],
            skills=list(SkillLevel),
            capability_levels=list(range(MIN_CAPABILITY_LEVEL, MAX_CAPABILITY_LEVEL + 1)),
            intensities=list(range(MIN_INTENSITY, MAX_INTENSITY + 1)),
        )
