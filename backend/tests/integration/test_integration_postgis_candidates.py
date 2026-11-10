"""Candidate retrieval on PostgreSQL/PostGIS: parity with the portable haversine source."""

import os
import random
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.conf.config import get_settings
from app.domain.account import ProfileRecord
from app.domain.matching.source import CandidateProfile
from app.domain.privacy import coarsen, haversine_km
from app.domain.profile import CapabilityEntry, ProfileView, SportEntry
from app.domain.taxonomy import CategoryCode, SkillLevel, SportCode
from app.repository.candidates import (
    HaversineCandidateSource,
    PostgisCandidateSource,
    build_candidate_source,
)
from app.repository.profiles import ProfileRepository
from app.repository.users import UserRepository

pytestmark = pytest.mark.postgis

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)
BACKEND_DIR = Path(__file__).resolve().parents[2]
# PostGIS measures on a sphere of mean radius 6371.0088 km, the haversine function on 6371.0 km:
# a profile whose cell centre lies within this distance of the radius may be on either side
BOUNDARY_TOLERANCE_KM = 0.001


@pytest.fixture
def migrated_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Rebuild the schema from the migrations on the test database."""
    url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("JWT_SECRET", "m" * 40)
    monkeypatch.setenv("DB_URL", url)
    get_settings.cache_clear()
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield url
    command.downgrade(config, "base")


@pytest.fixture
async def pg_engine(migrated_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(migrated_url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(pg_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with async_sessionmaker(pg_engine, expire_on_commit=False)() as db:
        yield db


async def add_profile(
    session: AsyncSession,
    *,
    lat: float,
    lon: float,
    sports: tuple[SportEntry, ...],
    visible: bool = True,
    capabilities: tuple[CapabilityEntry, ...] = (),
    consent: bool = True,
    confirmed: bool = True,
) -> ProfileView:
    user = await UserRepository(session).create_user(
        f"{uuid4().hex}@example.org",
        "hash",
        verified_at=datetime.now(UTC) if confirmed else None,
    )
    repository = ProfileRepository(session)
    await repository.replace_profile(
        user.id,
        ProfileRecord(
            display_name="Orest",
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


async def populate(session: AsyncSession, seed: int, size: int) -> list[ProfileView]:
    rng = random.Random(seed)
    sports = list(SportCode)[:5]
    population = []
    for _ in range(size):
        picked = rng.sample(sports, rng.randint(1, 3))
        population.append(
            await add_profile(
                session,
                lat=50.45 + rng.uniform(-0.7, 0.7),
                lon=30.52 + rng.uniform(-1.0, 1.0),
                sports=tuple(SportEntry(s, SkillLevel.BEGINNER) for s in picked),
                visible=rng.random() > 0.2,
                capabilities=(CapabilityEntry(CategoryCode.VISION, rng.randint(0, 4)),),
                consent=rng.random() > 0.3,
            )
        )
    return population


def distance_to(viewer: ProfileView, item: CandidateProfile) -> float:
    return haversine_km(viewer.cell, item.view.cell)


async def test_postgis_and_haversine_return_the_same_candidates(session: AsyncSession):
    population = await populate(session, seed=5, size=70)
    postgis = PostgisCandidateSource(session)
    portable = HaversineCandidateSource(session)
    compared = 0

    for viewer in population[:6]:
        for radius in (5.0, 10.0, 25.0, 60.0, 100.0):
            expected = await portable.search_candidates(viewer, radius, 200)
            actual = await postgis.search_candidates(viewer, radius, 200)
            compared += len(expected)

            only_one_side = {i.view.id for i in expected} ^ {i.view.id for i in actual}
            by_id = {i.view.id: i for i in [*expected, *actual]}
            for profile_id in only_one_side:
                gap = abs(distance_to(viewer, by_id[profile_id]) - radius)
                assert gap <= BOUNDARY_TOLERANCE_KM, (radius, gap)
            if not only_one_side:
                assert [i.view.id for i in actual] == [i.view.id for i in expected]

    # The comparison must not be vacuous: radii from 5 to 100 km over a 100 km wide population
    assert compared > 100


async def test_both_sources_apply_the_same_limit_in_the_same_order(session: AsyncSession):
    population = await populate(session, seed=8, size=60)
    viewer = population[0]

    expected = await HaversineCandidateSource(session).search_candidates(viewer, 100.0, 7)
    actual = await PostgisCandidateSource(session).search_candidates(viewer, 100.0, 7)

    assert [i.view.id for i in actual] == [i.view.id for i in expected]
    distances = [distance_to(viewer, i) for i in actual]
    assert distances == sorted(distances)


async def test_snapshots_from_both_sources_are_identical(session: AsyncSession):
    population = await populate(session, seed=3, size=40)
    viewer = population[0]

    expected = await HaversineCandidateSource(session).search_candidates(viewer, 100.0, 200)
    actual = await PostgisCandidateSource(session).search_candidates(viewer, 100.0, 200)

    assert {i.view.id: i for i in actual} == {i.view.id: i for i in expected}


async def test_postgis_never_returns_hidden_profiles_the_viewer_or_unrelated_sports(
    session: AsyncSession,
):
    swim = (SportEntry(SportCode.SWIMMING),)
    viewer = await add_profile(session, lat=50.45, lon=30.52, sports=swim)
    near = await add_profile(session, lat=50.49, lon=30.52, sports=swim)
    await add_profile(session, lat=50.49, lon=30.52, sports=swim, visible=False)
    await add_profile(session, lat=50.49, lon=30.52, sports=(SportEntry(SportCode.ARCHERY),))

    found = await PostgisCandidateSource(session).search_candidates(viewer, 100.0, 50)

    assert [i.view.id for i in found] == [near.id]


async def test_capabilities_without_consent_are_not_loaded_on_postgis(session: AsyncSession):
    swim = (SportEntry(SportCode.SWIMMING),)
    vision = (CapabilityEntry(CategoryCode.VISION, 3),)
    viewer = await add_profile(session, lat=50.45, lon=30.52, sports=swim)
    await add_profile(session, lat=50.49, lon=30.52, sports=swim, capabilities=vision)
    await add_profile(
        session, lat=50.53, lon=30.52, sports=swim, capabilities=vision, consent=False
    )

    found = await PostgisCandidateSource(session).search_candidates(viewer, 100.0, 50)

    assert [bool(i.view.functional.capabilities) for i in found] == [True, False]


async def test_the_spatial_filter_uses_the_gist_index(session: AsyncSession):
    await populate(session, seed=1, size=30)
    await session.execute(text("SET LOCAL enable_seqscan = off"))

    plan = (
        await session.execute(
            text(
                "EXPLAIN SELECT id FROM profiles WHERE ST_DWithin(area_center, "
                "ST_GeogFromText('SRID=4326;POINT(30.52 50.45)'), 10000, false)"
            )
        )
    ).scalars()

    assert "ix_profiles_area_center" in "\n".join(plan)


async def test_postgis_and_haversine_distances_agree_within_the_documented_tolerance(
    session: AsyncSession,
):
    population = await populate(session, seed=2, size=25)
    viewer = population[0]

    rows = (
        await session.execute(
            text(
                "SELECT id, ST_Distance(area_center, "
                "ST_GeogFromText(:point), false) / 1000.0 FROM profiles"
            ),
            {"point": f"SRID=4326;POINT({viewer.cell.longitude:.6f} {viewer.cell.latitude:.6f})"},
        )
    ).all()

    by_id: dict[UUID, ProfileView] = {p.id: p for p in population}
    for profile_id, kilometres in rows:
        expected = haversine_km(viewer.cell, by_id[profile_id].cell)
        assert kilometres == pytest.approx(expected, rel=1e-5, abs=1e-6)


async def test_the_factory_picks_the_postgis_source_on_postgresql(session: AsyncSession):
    assert isinstance(build_candidate_source(session), PostgisCandidateSource)


async def test_postgis_leaves_out_profiles_of_unconfirmed_accounts(session: AsyncSession):
    swim = (SportEntry(SportCode.SWIMMING),)
    viewer = await add_profile(session, lat=50.45, lon=30.52, sports=swim)
    confirmed = await add_profile(session, lat=50.46, lon=30.53, sports=swim)
    await add_profile(session, lat=50.46, lon=30.54, sports=swim, confirmed=False)

    for source in (PostgisCandidateSource(session), HaversineCandidateSource(session)):
        found = await source.search_candidates(viewer, 100.0, 10)
        assert [item.view.id for item in found] == [confirmed.id]
