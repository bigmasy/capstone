"""Hypothesis strategies for domain objects."""

from hypothesis import strategies as st

from app.domain.privacy import GridCell
from app.domain.profile import CapabilityEntry, FunctionalProfile, ProfileView, SportEntry
from app.domain.taxonomy import CategoryCode, EquipmentCode, SkillLevel, SportCode
from tests.unit.domain.builders import make_id

# About 100 km around Kyiv: far enough to reach every distance band
cells = st.builds(
    GridCell,
    latitude=st.floats(min_value=49.5, max_value=51.4, allow_nan=False),
    longitude=st.floats(min_value=29.0, max_value=32.0, allow_nan=False),
)

sport_entries = st.dictionaries(
    st.sampled_from(list(SportCode)), st.sampled_from(list(SkillLevel)), max_size=6
).map(lambda raw: frozenset(SportEntry(sport, skill) for sport, skill in raw.items()))


@st.composite
def functional_profiles(draw: st.DrawFn) -> FunctionalProfile:
    """Draw a functional profile; equipment is the wheelchair on lower mobility only."""
    raw = draw(
        st.dictionaries(
            st.sampled_from(list(CategoryCode)),
            st.tuples(st.integers(0, 4), st.booleans()),
            max_size=7,
        )
    )
    return FunctionalProfile(
        capabilities=frozenset(
            CapabilityEntry(
                category,
                level,
                EquipmentCode.WHEELCHAIR_ACTIVE
                if with_equipment and category == CategoryCode.MOBILITY_LOWER
                else None,
            )
            for category, (level, with_equipment) in raw.items()
        )
    )


@st.composite
def profiles(draw: st.DrawFn, number: int | None = None) -> ProfileView:
    """Draw a profile; ``number`` fixes the id, otherwise it is drawn."""
    ident = draw(st.integers(1, 10_000)) if number is None else number
    return ProfileView(
        id=make_id(ident),
        sports=draw(sport_entries),
        intensity=draw(st.integers(1, 5)),
        cell=draw(cells),
        functional=draw(functional_profiles()),
        is_visible=draw(st.booleans()),
    )


@st.composite
def profile_pools(draw: st.DrawFn, max_size: int = 12) -> list[ProfileView]:
    """Draw profiles with distinct ids."""
    size = draw(st.integers(0, max_size))
    return [draw(profiles(number=i + 1)) for i in range(size)]
