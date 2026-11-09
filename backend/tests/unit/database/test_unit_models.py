from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.database.models import Base, FunctionalCapability, Profile, ProfileSport, User


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        yield db


def make_user(**overrides: Any) -> User:
    values: dict[str, Any] = {"email": f"{uuid4().hex}@example.org", "password_hash": "hash"}
    values.update(overrides)
    return User(**values)


def make_profile(user: User, **overrides: Any) -> Profile:
    values: dict[str, Any] = {
        "user_id": user.id,
        "display_name": "Orest",
        "district_code": "kyiv_podilskyi",
        "intensity": 3,
        "is_visible": True,
        "area_lat": 50.45,
        "area_lon": 30.54,
    }
    values.update(overrides)
    return Profile(**values)


async def saved_user(db: AsyncSession) -> User:
    user = make_user()
    db.add(user)
    await db.commit()
    return user


async def test_user_gets_id_and_creation_time(session: AsyncSession):
    user = await saved_user(session)

    assert user.id is not None
    assert user.created_at is not None


async def test_email_must_be_unique(session: AsyncSession):
    session.add_all([make_user(email="a@example.org"), make_user(email="a@example.org")])

    with pytest.raises(IntegrityError):
        await session.commit()


async def test_email_must_be_lower_case(session: AsyncSession):
    session.add(make_user(email="Upper@example.org"))

    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.parametrize(
    "overrides",
    [
        {"intensity": 0},
        {"intensity": 6},
        {"area_lat": 90.5},
        {"area_lat": -90.5},
        {"area_lon": 180.5},
        {"area_lon": -180.5},
        {"district_code": "atlantis"},
        {"area_lat": None},
        {"area_lon": None},
    ],
)
async def test_profile_constraints_reject_bad_values(session: AsyncSession, overrides: dict):
    user = await saved_user(session)
    session.add(make_profile(user, **overrides))

    with pytest.raises(IntegrityError):
        await session.commit()


async def test_profile_boundaries_are_accepted(session: AsyncSession):
    user = await saved_user(session)
    session.add(make_profile(user, intensity=5, area_lat=90.0, area_lon=-180.0, contact="x" * 120))

    await session.commit()


async def test_one_profile_per_user(session: AsyncSession):
    user = await saved_user(session)
    session.add_all([make_profile(user), make_profile(user)])

    with pytest.raises(IntegrityError):
        await session.commit()


async def test_profile_needs_an_existing_user(session: AsyncSession):
    session.add(Profile(user_id=uuid4(), display_name="x", intensity=3, area_lat=1, area_lon=1))

    with pytest.raises(IntegrityError):
        await session.commit()


async def test_sport_rows_are_unique_per_profile_and_validated(session: AsyncSession):
    user = await saved_user(session)
    profile = make_profile(user)
    session.add(profile)
    await session.commit()
    session.add_all(
        [
            ProfileSport(profile_id=profile.id, sport="swimming", skill="beginner"),
            ProfileSport(profile_id=profile.id, sport="swimming", skill="advanced"),
        ]
    )

    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.parametrize(("sport", "skill"), [("chess", "beginner"), ("swimming", "expert")])
async def test_sport_and_skill_are_constrained(session: AsyncSession, sport: str, skill: str):
    user = await saved_user(session)
    profile = make_profile(user)
    session.add(profile)
    await session.commit()
    session.add(ProfileSport(profile_id=profile.id, sport=sport, skill=skill))

    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.parametrize(
    "overrides",
    [
        {"level": -1},
        {"level": 5},
        {"category": "telepathy"},
        {"equipment": "jetpack"},
    ],
)
async def test_capability_constraints(session: AsyncSession, overrides: dict):
    user = await saved_user(session)
    profile = make_profile(user)
    session.add(profile)
    await session.commit()
    values = {"profile_id": profile.id, "category": "vision", "level": 2, "equipment": None}
    values.update(overrides)
    session.add(FunctionalCapability(**values))

    with pytest.raises(IntegrityError):
        await session.commit()


async def test_deleting_a_user_cascades_to_everything_below(session: AsyncSession):
    user = await saved_user(session)
    profile = make_profile(user)
    session.add(profile)
    await session.commit()
    session.add_all(
        [
            ProfileSport(profile_id=profile.id, sport="swimming", skill="beginner"),
            FunctionalCapability(profile_id=profile.id, category="vision", level=2),
        ]
    )
    await session.commit()

    await session.delete(user)
    await session.commit()

    for model in (Profile, ProfileSport, FunctionalCapability):
        assert await session.scalar(select(func.count()).select_from(model)) == 0


def test_every_constraint_has_an_explicit_name():
    for table in Base.metadata.sorted_tables:
        for constraint in table.constraints:
            assert constraint.name, f"unnamed constraint on {table.name}: {constraint}"
        for index in table.indexes:
            assert index.name


def test_area_center_is_not_mapped():
    assert "area_center" not in Profile.__table__.c
