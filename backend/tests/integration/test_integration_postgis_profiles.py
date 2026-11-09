"""Profiles on a real PostgreSQL/PostGIS database, created by the migrations."""

import os
from collections.abc import AsyncIterator, Iterator
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.conf.config import get_settings
from app.database.db import get_db
from app.database.models import FunctionalCapability, Profile
from app.domain.account import ProfileRecord
from app.domain.privacy import coarsen
from app.domain.profile import CapabilityEntry, SportEntry
from app.domain.taxonomy import CategoryCode, SkillLevel, SportCode
from app.main import create_app
from app.repository.profiles import ProfileRepository
from app.repository.users import UserRepository
from tests.conftest import make_settings
from tests.integration.helpers import make_profile_body, sign_up

pytestmark = pytest.mark.postgis

BACKEND_DIR = Path(__file__).resolve().parents[2]


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


async def make_user_id(session: AsyncSession) -> UUID:
    return (await UserRepository(session).create_user(f"{uuid4().hex}@example.org", "hash")).id


def record(lat: float, lon: float) -> ProfileRecord:
    return ProfileRecord(
        display_name="Orest",
        district=None,
        intensity=3,
        is_visible=True,
        cell=coarsen(lat, lon),
        sports=(SportEntry(SportCode.SWIMMING, SkillLevel.BEGINNER),),
        capabilities=(CapabilityEntry(CategoryCode.VISION, 4),),
        functional_consent_at=None,
        contact=None,
    )


async def test_generated_geography_follows_the_stored_cell(pg_engine: AsyncEngine):
    async with async_sessionmaker(pg_engine, expire_on_commit=False)() as session:
        user_id = await make_user_id(session)
        await ProfileRepository(session).replace_profile(user_id, record(50.4501, 30.5234))
        row = (await session.execute(select(Profile))).scalar_one()
        coordinates = (
            await session.execute(
                text(
                    "SELECT ST_Y(area_center::geometry), ST_X(area_center::geometry) FROM profiles"
                )
            )
        ).one()

    assert coordinates == pytest.approx((row.area_lat, row.area_lon))


async def test_spatial_index_supports_distance_queries(pg_engine: AsyncEngine):
    async with async_sessionmaker(pg_engine, expire_on_commit=False)() as session:
        for lat in (50.4501, 50.4901):
            user_id = await make_user_id(session)
            await ProfileRepository(session).replace_profile(user_id, record(lat, 30.5234))
        metres = (
            await session.execute(
                text(
                    "SELECT max(ST_Distance(a.area_center, b.area_center, false)) "
                    "FROM profiles a, profiles b"
                )
            )
        ).scalar_one()

    assert 3_000 < metres < 6_000


async def test_cascade_delete_and_replace_on_postgresql(pg_engine: AsyncEngine):
    async with async_sessionmaker(pg_engine, expire_on_commit=False)() as session:
        user_id = await make_user_id(session)
        repository = ProfileRepository(session)
        first = await repository.replace_profile(user_id, record(50.45, 30.52))
        second = await repository.replace_profile(user_id, record(50.46, 30.53))
        assert second.id == first.id

        await UserRepository(session).remove_user(user_id)

        assert await session.scalar(select(func.count()).select_from(Profile)) == 0
        assert await session.scalar(select(func.count()).select_from(FunctionalCapability)) == 0


async def test_full_http_flow_on_postgresql(pg_engine: AsyncEngine):
    app: FastAPI = create_app(make_settings(DB_URL=os.environ["TEST_DATABASE_URL"]))
    maker = async_sessionmaker(pg_engine, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        owner = await sign_up(client)
        other = await sign_up(client)
        put = await client.put(
            "/api/v1/profiles/me", json=make_profile_body(), headers=owner.headers
        )
        public = await client.get(f"/api/v1/profiles/{put.json()['id']}", headers=other.headers)
        deleted = await client.delete("/api/v1/auth/me", headers=owner.headers)
        gone = await client.get(f"/api/v1/profiles/{put.json()['id']}", headers=other.headers)

    assert put.status_code == 200
    assert public.status_code == 200 and "capabilities" not in public.json()
    assert deleted.status_code == 204
    assert gone.status_code == 404


async def test_keeping_the_cell_keeps_the_generated_geography(pg_engine: AsyncEngine):
    async with async_sessionmaker(pg_engine, expire_on_commit=False)() as session:
        user_id = await make_user_id(session)
        repository = ProfileRepository(session)
        await repository.replace_profile(user_id, record(50.4501, 30.5234))
        keep = replace(record(0.0, 0.0), cell=None, contact="t.me/new")
        await repository.replace_profile(user_id, keep)
        row = (await session.execute(select(Profile))).scalar_one()
        coordinates = (
            await session.execute(
                text(
                    "SELECT ST_Y(area_center::geometry), ST_X(area_center::geometry) FROM profiles"
                )
            )
        ).one()

    expected = coarsen(50.4501, 30.5234)
    assert (row.area_lat, row.area_lon) == (expected.latitude, expected.longitude)
    assert coordinates == pytest.approx((expected.latitude, expected.longitude))
    assert row.contact == "t.me/new"


async def test_invitations_need_a_contact_on_postgresql(pg_engine: AsyncEngine):
    app: FastAPI = create_app(make_settings(DB_URL=os.environ["TEST_DATABASE_URL"]))
    maker = async_sessionmaker(pg_engine, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        with_contact, without_contact = await sign_up(client), await sign_up(client)
        target = await client.put(
            "/api/v1/profiles/me", json=make_profile_body(), headers=with_contact.headers
        )
        await client.put(
            "/api/v1/profiles/me",
            json=make_profile_body(contact=None),
            headers=without_contact.headers,
        )
        refused = await client.post(
            "/api/v1/invitations",
            json={"recipient_profile_id": target.json()["id"]},
            headers=without_contact.headers,
        )
        third = await sign_up(client)
        await client.put("/api/v1/profiles/me", json=make_profile_body(), headers=third.headers)
        invited = await client.post(
            "/api/v1/invitations",
            json={"recipient_profile_id": target.json()["id"]},
            headers=third.headers,
        )

    assert refused.status_code == 409
    assert refused.json()["code"] == "contact_required"
    assert invited.status_code == 201
