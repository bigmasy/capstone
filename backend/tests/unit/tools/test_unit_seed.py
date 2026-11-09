import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.conf.config import get_settings
from app.database.db import DatabaseSessionManager
from app.database.models import Base, FunctionalCapability, Profile, User
from app.domain.privacy import coarsen
from app.tools import seed
from app.tools.seed import SeedResult, demo_email, seed_demo
from tests.conftest import make_settings

PASSWORD = "demo-password-for-tests"


@pytest.fixture
async def manager() -> AsyncIterator[DatabaseSessionManager]:
    db = DatabaseSessionManager(make_settings())
    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield db
    await db.close()


async def count_rows(db: DatabaseSessionManager, model: type) -> int:
    async with db.session() as session:
        return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def run_seed(db: DatabaseSessionManager, count: int = 12) -> SeedResult:
    return await seed_demo(db, make_settings(), count=count, seed=7, password=PASSWORD)


def test_demo_email_is_on_a_reserved_domain():
    assert demo_email(0) == "demo-0001@example.invalid"
    assert demo_email(199) == "demo-0200@example.invalid"


async def test_creates_an_account_and_a_profile_per_generated_profile(manager):
    result = await run_seed(manager, 12)

    assert result == SeedResult(created=12, skipped=0)
    assert await count_rows(manager, User) == 12
    assert await count_rows(manager, Profile) == 12


async def test_second_run_adds_nothing(manager):
    await run_seed(manager, 12)

    result = await run_seed(manager, 12)

    assert result == SeedResult(created=0, skipped=12)
    assert await count_rows(manager, User) == 12
    assert await count_rows(manager, Profile) == 12


async def test_larger_second_run_only_adds_the_new_accounts(manager):
    await run_seed(manager, 5)

    result = await run_seed(manager, 8)

    assert result == SeedResult(created=3, skipped=5)


async def test_account_without_profile_gets_its_profile(manager):
    await run_seed(manager, 3)
    async with manager.session() as session:
        await session.execute(Profile.__table__.delete())
        await session.commit()

    result = await run_seed(manager, 3)

    assert result == SeedResult(created=0, skipped=3)
    assert await count_rows(manager, Profile) == 3


async def test_nothing_in_the_data_looks_real(manager):
    await run_seed(manager, 12)

    async with manager.session() as session:
        users = (await session.execute(select(User))).scalars().all()
        profiles = (await session.execute(select(Profile))).scalars().all()
    assert all(user.email.endswith("@example.invalid") for user in users)
    assert all(user.email.startswith("demo-") for user in users)
    assert all(PASSWORD not in user.password_hash for user in users)
    assert all(user.password_hash.startswith("$argon2id$") for user in users)
    assert all(profile.display_name.startswith("Demo participant ") for profile in profiles)
    assert all(profile.contact is None for profile in profiles)


async def test_stored_location_is_a_cell_centre(manager):
    await run_seed(manager, 12)

    async with manager.session() as session:
        profiles = (await session.execute(select(Profile))).scalars().all()
    for profile in profiles:
        cell = coarsen(profile.area_lat, profile.area_lon)
        assert (profile.area_lat, profile.area_lon) == (cell.latitude, cell.longitude)


async def test_capabilities_are_stored_only_with_consent(manager):
    await run_seed(manager, 40)

    async with manager.session() as session:
        profiles = (await session.execute(select(Profile))).scalars().all()
        with_capabilities = {
            row.profile_id
            for row in (await session.execute(select(FunctionalCapability))).scalars()
        }
    assert with_capabilities, "the generated population should contain functional data"
    for profile in profiles:
        assert (profile.functional_consent_at is not None) == (profile.id in with_capabilities)


async def test_same_seed_gives_the_same_population():
    snapshots = []
    for _ in range(2):
        db = DatabaseSessionManager(make_settings())
        async with db.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await run_seed(db, 10)
        async with db.session() as session:
            rows = (await session.execute(select(Profile))).scalars().all()
        snapshots.append(
            sorted((p.display_name, p.intensity, p.area_lat, p.area_lon) for p in rows)
        )
        await db.close()

    assert snapshots[0] == snapshots[1]


def prod_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("DB_URL", "postgresql+asyncpg://unused:unused@db.invalid/unused")
    monkeypatch.setenv("JWT_SECRET", "p" * 40)
    monkeypatch.setenv("CORS_ORIGINS", '["https://localhost"]')
    monkeypatch.setenv("SEED_PASSWORD", PASSWORD)


def test_refuses_to_run_in_prod(monkeypatch, capsys):
    prod_environment(monkeypatch)

    async def forbidden(*args: object) -> SeedResult:
        raise AssertionError("the database must not be opened")

    monkeypatch.setattr(seed, "_run", forbidden)

    assert seed.main(["--count", "3"]) == seed.EXIT_REFUSED
    assert "ENV=prod" in capsys.readouterr().err


def test_force_demo_allows_prod(monkeypatch, capsys):
    prod_environment(monkeypatch)
    calls: list[tuple[object, ...]] = []

    async def fake_run(*args: object) -> SeedResult:
        calls.append(args)
        return SeedResult(created=3, skipped=0)

    monkeypatch.setattr(seed, "_run", fake_run)

    assert seed.main(["--count", "3", "--force-demo"]) == 0
    assert len(calls) == 1
    assert "3 created" in capsys.readouterr().out


def dev_environment(monkeypatch: pytest.MonkeyPatch, database: Path) -> None:
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("DB_URL", f"sqlite+aiosqlite:///{database}")
    monkeypatch.setenv("ARGON2_TIME_COST", "1")
    monkeypatch.setenv("ARGON2_MEMORY_COST_KIB", "8")
    monkeypatch.setenv("ARGON2_PARALLELISM", "1")
    get_settings.cache_clear()


def test_password_is_required_and_there_is_no_default(monkeypatch, tmp_path, capsys):
    dev_environment(monkeypatch, tmp_path / "seed.db")
    monkeypatch.delenv("SEED_PASSWORD", raising=False)

    assert seed.main(["--count", "2"]) == seed.EXIT_REFUSED
    assert "SEED_PASSWORD" in capsys.readouterr().err


def test_weak_password_is_rejected_without_echoing_it(monkeypatch, tmp_path, capsys):
    dev_environment(monkeypatch, tmp_path / "seed.db")

    assert seed.main(["--count", "2", "--password", "short"]) == seed.EXIT_REFUSED
    captured = capsys.readouterr()
    assert "short" not in captured.err + captured.out


def test_command_line_seeds_a_database_and_is_idempotent(monkeypatch, tmp_path, capsys):
    database = tmp_path / "seed.db"
    dev_environment(monkeypatch, database)
    monkeypatch.setenv("SEED_PASSWORD", PASSWORD)

    async def create_schema() -> None:
        engine: AsyncEngine = create_async_engine(f"sqlite+aiosqlite:///{database}")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(create_schema())

    assert seed.main(["--count", "4"]) == 0
    assert "4 created, 0 skipped" in capsys.readouterr().out
    assert seed.main(["--count", "4"]) == 0
    output = capsys.readouterr().out
    assert "0 created, 4 skipped" in output
    assert "example.invalid" not in output
    assert PASSWORD not in output
