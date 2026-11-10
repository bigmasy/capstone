from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.database.models import Base, FunctionalCapability, Profile, ProfileSport, User
from app.domain.account import LocationRequiredError, ProfileRecord
from app.domain.privacy import GridCell
from app.domain.profile import CapabilityEntry, SportEntry
from app.domain.taxonomy import (
    CategoryCode,
    DistrictCode,
    EquipmentCode,
    SkillLevel,
    SportCode,
)
from app.repository import private_layer
from app.repository.profiles import ProfileRepository
from app.repository.users import UserRepository

CELL = GridCell(latitude=50.46, longitude=30.51)
NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        yield db


@pytest.fixture
def profiles(session: AsyncSession) -> ProfileRepository:
    return ProfileRepository(session)


async def make_user_id(session: AsyncSession, confirmed: bool = True) -> UUID:
    account = await UserRepository(session).create_user(
        f"{uuid4().hex}@example.org",
        "hash",
        verified_at=None if not confirmed else datetime.now(UTC),
    )
    return account.id


def make_record(**overrides: object) -> ProfileRecord:
    values: dict[str, object] = {
        "display_name": "Orest",
        "district": DistrictCode.KYIV_PODILSKYI,
        "intensity": 3,
        "is_visible": True,
        "cell": CELL,
        "sports": (
            SportEntry(SportCode.SWIMMING, SkillLevel.INTERMEDIATE),
            SportEntry(SportCode.ARCHERY, SkillLevel.BEGINNER),
        ),
        "capabilities": (
            CapabilityEntry(CategoryCode.MOBILITY_LOWER, 2, EquipmentCode.WHEELCHAIR_ACTIVE),
            CapabilityEntry(CategoryCode.VISION, 4),
        ),
        "functional_consent_at": NOW,
        "contact": "t.me/orest",
    }
    values.update(overrides)
    return ProfileRecord(**values)  # type: ignore[arg-type]


async def test_replace_profile_creates_everything_in_one_call(
    session: AsyncSession, profiles: ProfileRepository
):
    user_id = await make_user_id(session)

    owner = await profiles.replace_profile(user_id, make_record())

    assert owner.user_id == user_id
    assert owner.display_name == "Orest"
    assert owner.district is DistrictCode.KYIV_PODILSKYI
    assert [s.sport for s in owner.sports] == [SportCode.ARCHERY, SportCode.SWIMMING]
    assert [c.category for c in owner.capabilities] == [
        CategoryCode.MOBILITY_LOWER,
        CategoryCode.VISION,
    ]
    assert owner.functional_consent_at == NOW
    assert owner.contact == "t.me/orest"
    assert owner.created_at.tzinfo is not None


async def test_write_is_committed_before_the_method_returns(
    engine: AsyncEngine, session: AsyncSession, profiles: ProfileRepository
):
    user_id = await make_user_id(session)

    await profiles.replace_profile(user_id, make_record())

    async with async_sessionmaker(engine)() as other:
        assert await other.scalar(select(func.count()).select_from(Profile)) == 1


async def test_location_is_stored_as_the_cell_centre(
    session: AsyncSession, profiles: ProfileRepository
):
    user_id = await make_user_id(session)

    await profiles.replace_profile(user_id, make_record())

    row = (await session.execute(select(Profile))).scalar_one()
    assert (row.area_lat, row.area_lon) == (CELL.latitude, CELL.longitude)


async def test_replace_profile_overwrites_sports_and_capabilities(
    session: AsyncSession, profiles: ProfileRepository
):
    user_id = await make_user_id(session)
    first = await profiles.replace_profile(user_id, make_record())

    second = await profiles.replace_profile(
        user_id,
        make_record(
            display_name="Renamed",
            intensity=5,
            district=None,
            contact=None,
            sports=(SportEntry(SportCode.SWIMMING, SkillLevel.ADVANCED),),
            capabilities=(CapabilityEntry(CategoryCode.HEARING, 1, EquipmentCode.HEARING_AID),),
        ),
    )

    assert second.id == first.id
    assert second.display_name == "Renamed"
    assert second.district is None
    assert second.sports == (SportEntry(SportCode.SWIMMING, SkillLevel.ADVANCED),)
    assert second.capabilities == (
        CapabilityEntry(CategoryCode.HEARING, 1, EquipmentCode.HEARING_AID),
    )
    assert await session.scalar(select(func.count()).select_from(Profile)) == 1
    assert await session.scalar(select(func.count()).select_from(ProfileSport)) == 1
    assert await session.scalar(select(func.count()).select_from(FunctionalCapability)) == 1


async def test_replace_profile_can_drop_all_capabilities_and_consent(
    session: AsyncSession, profiles: ProfileRepository
):
    user_id = await make_user_id(session)
    await profiles.replace_profile(user_id, make_record())

    owner = await profiles.replace_profile(
        user_id, make_record(capabilities=(), functional_consent_at=None)
    )

    assert owner.capabilities == ()
    assert owner.functional_consent_at is None
    assert await session.scalar(select(func.count()).select_from(FunctionalCapability)) == 0


async def test_owner_lookups_are_scoped_to_the_owner(
    session: AsyncSession, profiles: ProfileRepository
):
    owner_id, other_id = await make_user_id(session), await make_user_id(session)
    created = await profiles.replace_profile(owner_id, make_record())

    assert await profiles.get_profile_by_user_id(owner_id) == created
    assert await profiles.get_profile_by_id(created.id, owner_id) == created
    assert await profiles.get_profile_by_id(created.id, other_id) is None
    assert await profiles.get_profile_by_user_id(other_id) is None
    assert await profiles.get_profile_by_id(uuid4(), owner_id) is None


async def test_public_lookup_returns_only_visible_profiles_without_private_fields(
    session: AsyncSession, profiles: ProfileRepository
):
    visible_id, hidden_id = await make_user_id(session), await make_user_id(session)
    visible = await profiles.replace_profile(visible_id, make_record())
    hidden = await profiles.replace_profile(hidden_id, make_record(is_visible=False))

    public = await profiles.get_public_profile_by_id(visible.id)

    assert public is not None
    assert public.display_name == "Orest"
    assert not hasattr(public, "capabilities")
    assert not hasattr(public, "contact")
    assert await profiles.get_public_profile_by_id(hidden.id) is None
    assert await profiles.get_public_profile_by_id(uuid4()) is None


async def test_remove_profile_deletes_children_and_keeps_the_user(
    session: AsyncSession, profiles: ProfileRepository
):
    user_id = await make_user_id(session)
    await profiles.replace_profile(user_id, make_record())

    assert await profiles.remove_profile(user_id) is True
    assert await profiles.remove_profile(user_id) is False

    for model in (Profile, ProfileSport, FunctionalCapability):
        assert await session.scalar(select(func.count()).select_from(model)) == 0
    assert await session.scalar(select(func.count()).select_from(User)) == 1


async def test_removing_the_user_removes_the_profile(
    session: AsyncSession, profiles: ProfileRepository
):
    user_id = await make_user_id(session)
    await profiles.replace_profile(user_id, make_record())

    await UserRepository(session).remove_user(user_id)

    for model in (Profile, ProfileSport, FunctionalCapability):
        assert await session.scalar(select(func.count()).select_from(model)) == 0


async def test_profile_view_carries_cell_sports_and_private_layer(
    session: AsyncSession, profiles: ProfileRepository
):
    user_id = await make_user_id(session)
    created = await profiles.replace_profile(user_id, make_record())

    view = await profiles.get_profile_view(user_id)

    assert view is not None
    assert view.id == created.id
    assert view.cell == CELL
    assert view.intensity == 3
    assert view.district is DistrictCode.KYIV_PODILSKYI
    assert view.sport_codes == {SportCode.SWIMMING, SportCode.ARCHERY}
    assert view.skill_in(SportCode.SWIMMING) is SkillLevel.INTERMEDIATE
    assert view.functional.get(CategoryCode.VISION) == CapabilityEntry(CategoryCode.VISION, 4)
    assert await profiles.get_profile_view(uuid4()) is None


async def test_private_layer_reads_only_what_was_stored(
    session: AsyncSession, profiles: ProfileRepository
):
    user_id = await make_user_id(session)
    created = await profiles.replace_profile(user_id, make_record(capabilities=()))

    functional = await private_layer.load_functional_profile(session, created.id)

    assert functional.capabilities == frozenset()


def test_only_the_private_layer_touches_the_capability_table():
    package = Path(__file__).resolve().parents[3] / "app" / "repository"
    offenders = [
        path.name
        for path in package.glob("*.py")
        if path.name != "private_layer.py" and "FunctionalCapability" in path.read_text()
    ]

    assert offenders == []


async def test_visible_owner_id_is_resolved_only_for_visible_profiles(
    session: AsyncSession, profiles: ProfileRepository
):
    visible_user, hidden_user = await make_user_id(session), await make_user_id(session)
    visible = await profiles.replace_profile(visible_user, make_record())
    hidden = await profiles.replace_profile(hidden_user, make_record(is_visible=False))

    assert await profiles.get_visible_owner_id(visible.id) == visible_user
    assert await profiles.get_visible_owner_id(hidden.id) is None
    assert await profiles.get_visible_owner_id(uuid4()) is None


async def test_profile_exists_ignores_visibility(
    session: AsyncSession, profiles: ProfileRepository
):
    hidden_user, without_profile = await make_user_id(session), await make_user_id(session)
    await profiles.replace_profile(hidden_user, make_record(is_visible=False))

    assert await profiles.profile_exists(hidden_user) is True
    assert await profiles.profile_exists(without_profile) is False


async def test_has_contact_is_true_only_for_a_profile_with_a_contact(
    session: AsyncSession, profiles: ProfileRepository
):
    with_contact, without_contact, no_profile = (
        await make_user_id(session),
        await make_user_id(session),
        await make_user_id(session),
    )
    await profiles.replace_profile(with_contact, make_record(contact="t.me/orest"))
    await profiles.replace_profile(without_contact, make_record(contact=None))

    assert await profiles.has_contact(with_contact) is True
    assert await profiles.has_contact(without_contact) is False
    assert await profiles.has_contact(no_profile) is False


async def test_has_contact_follows_a_later_change_of_the_contact(
    session: AsyncSession, profiles: ProfileRepository
):
    user_id = await make_user_id(session)
    await profiles.replace_profile(user_id, make_record(contact=None))
    before = await profiles.has_contact(user_id)

    await profiles.replace_profile(user_id, make_record(contact="t.me/orest"))

    assert before is False
    assert await profiles.has_contact(user_id) is True


async def test_a_record_without_a_cell_keeps_the_stored_cell_and_updates_the_rest(
    session: AsyncSession, profiles: ProfileRepository
):
    user_id = await make_user_id(session)
    await profiles.replace_profile(user_id, make_record())

    owner = await profiles.replace_profile(
        user_id, make_record(cell=None, contact="t.me/new", display_name="Renamed")
    )

    row = (await session.execute(select(Profile))).scalar_one()
    assert (row.area_lat, row.area_lon) == (CELL.latitude, CELL.longitude)
    assert owner.contact == "t.me/new" and owner.display_name == "Renamed"


async def test_a_record_without_a_cell_and_without_a_profile_is_refused_and_writes_nothing(
    session: AsyncSession, profiles: ProfileRepository
):
    user_id = await make_user_id(session)

    with pytest.raises(LocationRequiredError):
        await profiles.replace_profile(user_id, make_record(cell=None))

    assert await session.scalar(select(func.count()).select_from(Profile)) == 0
    assert await session.scalar(select(func.count()).select_from(ProfileSport)) == 0


async def test_a_profile_of_an_unconfirmed_account_looks_hidden_to_other_people(
    session: AsyncSession, profiles: ProfileRepository
):
    owner = await make_user_id(session, confirmed=False)
    stored = await profiles.replace_profile(owner, make_record())

    assert await profiles.get_public_profile_by_id(stored.id) is None
    assert await profiles.get_visible_owner_id(stored.id) is None
    # The owner still sees and edits their own profile
    assert await profiles.get_profile_by_user_id(owner) is not None
