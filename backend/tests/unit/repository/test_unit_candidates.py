"""Tests of candidate retrieval on SQLite: the portable source and the choice of the source."""

import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.database.models import Base
from app.domain.account import ProfileRecord
from app.domain.matching.feed import eligible_candidates
from app.domain.privacy import coarsen
from app.domain.profile import CapabilityEntry, ProfileView, SportEntry
from app.domain.taxonomy import CategoryCode, SkillLevel, SportCode
from app.repository.candidates import (
    HaversineCandidateSource,
    build_candidate_source,
)
from app.repository.profiles import ProfileRepository
from app.repository.users import UserRepository

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)
SWIM = SportEntry(SportCode.SWIMMING, SkillLevel.BEGINNER)
ARCHERY = SportEntry(SportCode.ARCHERY, SkillLevel.BEGINNER)


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        yield db


async def add_profile(
    session: AsyncSession,
    *,
    lat: float = 50.45,
    lon: float = 30.52,
    sports: tuple[SportEntry, ...] = (SWIM,),
    visible: bool = True,
    capabilities: tuple[CapabilityEntry, ...] = (),
    consent: bool = True,
    name: str = "Orest",
) -> ProfileView:
    """Store a profile and return the snapshot matching would build for its owner."""
    user = await UserRepository(session).create_user(f"{uuid4().hex}@example.org", "hash")
    repository = ProfileRepository(session)
    await repository.replace_profile(
        user.id,
        ProfileRecord(
            display_name=name,
            district=None,
            intensity=3,
            is_visible=visible,
            cell=coarsen(lat, lon),
            sports=sports,
            capabilities=capabilities,
            functional_consent_at=NOW if consent else None,
            contact=None,
        ),
    )
    view = await repository.get_profile_view(user.id)
    assert view is not None
    return view


def ids(found) -> list[UUID]:
    return [item.view.id for item in found]


async def test_candidates_are_visible_other_profiles_sharing_a_sport(session: AsyncSession):
    viewer = await add_profile(session, sports=(SWIM, ARCHERY))
    near = await add_profile(session, lat=50.46, sports=(SWIM,))
    await add_profile(session, lat=50.46, sports=(SportEntry(SportCode.CYCLING),))
    await add_profile(session, lat=50.46, visible=False)

    found = await HaversineCandidateSource(session).search_candidates(viewer, 100.0, 50)

    assert ids(found) == [near.id]
    assert viewer.id not in ids(found)


async def test_candidates_carry_the_public_name_and_the_snapshot(session: AsyncSession):
    viewer = await add_profile(session)
    other = await add_profile(session, lat=50.46, name="Maryna", sports=(SWIM, ARCHERY))

    [item] = await HaversineCandidateSource(session).search_candidates(viewer, 100.0, 50)

    assert item.display_name == "Maryna"
    assert item.view.id == other.id
    assert item.view.sports == other.sports
    assert item.view.cell == other.cell


async def test_the_radius_cuts_by_distance_between_cell_centres(session: AsyncSession):
    viewer = await add_profile(session, lat=50.45)
    near = await add_profile(session, lat=50.49)  # one cell north, about 4.4 km
    await add_profile(session, lat=50.61)  # about 18 km

    within_five = await HaversineCandidateSource(session).search_candidates(viewer, 5.0, 50)
    within_ten = await HaversineCandidateSource(session).search_candidates(viewer, 10.0, 50)
    within_thirty = await HaversineCandidateSource(session).search_candidates(viewer, 30.0, 50)

    assert ids(within_five) == ids(within_ten) == [near.id]
    assert len(within_thirty) == 2


async def test_candidates_are_ordered_by_distance_then_id_and_cut_by_the_limit(
    session: AsyncSession,
):
    viewer = await add_profile(session, lat=50.45)
    far = await add_profile(session, lat=50.57)
    nearest = await add_profile(session, lat=50.49)
    twins = [await add_profile(session, lat=50.53) for _ in range(2)]

    found = await HaversineCandidateSource(session).search_candidates(viewer, 100.0, 50)
    cut = await HaversineCandidateSource(session).search_candidates(viewer, 100.0, 2)

    assert ids(found) == [nearest.id, *sorted(t.id for t in twins), far.id]
    assert ids(cut) == ids(found)[:2]


async def test_a_zero_limit_or_a_viewer_without_sports_finds_nothing(session: AsyncSession):
    viewer = await add_profile(session)
    await add_profile(session, lat=50.46)

    assert await HaversineCandidateSource(session).search_candidates(viewer, 100.0, 0) == []


async def test_capabilities_are_loaded_only_for_profiles_with_consent(session: AsyncSession):
    vision = (CapabilityEntry(CategoryCode.VISION, 4),)
    viewer = await add_profile(session)
    consenting = await add_profile(session, lat=50.46, capabilities=vision)
    # Rows left behind without consent must not take part in anybody's comparison
    await add_profile(session, lat=50.47, capabilities=vision, consent=False)

    found = await HaversineCandidateSource(session).search_candidates(viewer, 100.0, 50)

    by_id = {item.view.id: item.view for item in found}
    assert len(by_id) == 2
    assert by_id[consenting.id].functional.capabilities == frozenset(vision)
    assert [v for v in by_id.values() if v.id != consenting.id][
        0
    ].functional.capabilities == frozenset()


async def test_the_viewer_snapshot_has_no_functional_data_without_consent(session: AsyncSession):
    viewer = await add_profile(
        session, capabilities=(CapabilityEntry(CategoryCode.VISION, 4),), consent=False
    )

    assert viewer.functional.capabilities == frozenset()


async def test_the_portable_source_agrees_with_the_domain_rules(session: AsyncSession):
    rng = random.Random(11)
    population = [
        await add_profile(
            session,
            lat=50.45 + rng.uniform(-0.6, 0.6),
            lon=30.52 + rng.uniform(-0.9, 0.9),
            sports=tuple(
                SportEntry(sport) for sport in rng.sample(list(SportCode)[:5], rng.randint(1, 3))
            ),
            visible=rng.random() > 0.2,
        )
        for _ in range(40)
    ]
    viewer = population[0]
    source = HaversineCandidateSource(session)

    for radius in (5.0, 25.0, 100.0):
        found = await source.search_candidates(viewer, radius, 200)

        expected = [
            c.profile.id
            for c in sorted(
                eligible_candidates(viewer, population),
                key=lambda c: (c.distance_km, c.profile.id),
            )
            if c.distance_km <= radius
        ]
        assert ids(found) == expected


async def test_sqlite_gets_the_portable_source(session: AsyncSession):
    assert isinstance(build_candidate_source(session), HaversineCandidateSource)
