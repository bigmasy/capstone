from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.account import LOCATION_REQUIRED_MESSAGE, LocationRequiredError, ProfileDraft
from app.domain.errors import NotFoundError
from app.domain.privacy import coarsen
from app.domain.profile import CapabilityEntry, SportEntry
from app.domain.taxonomy import CategoryCode, DistrictCode, EquipmentCode, SkillLevel, SportCode
from app.services.profiles import ProfileService
from tests.unit.services.fakes import FakeProfileRepository

LAT, LON = 50.4501234, 30.5234567
T1 = datetime(2026, 11, 4, 10, 0, tzinfo=UTC)
T2 = datetime(2026, 11, 5, 10, 0, tzinfo=UTC)


def make_draft(**overrides: object) -> ProfileDraft:
    values: dict[str, object] = {
        "display_name": "Orest",
        "district": DistrictCode.KYIV_PODILSKYI,
        "intensity": 3,
        "is_visible": True,
        "latitude": LAT,
        "longitude": LON,
        "sports": (SportEntry(SportCode.SWIMMING, SkillLevel.BEGINNER),),
        "capabilities": (
            CapabilityEntry(CategoryCode.MOBILITY_LOWER, 2, EquipmentCode.WHEELCHAIR_ACTIVE),
        ),
        "functional_data_consent": True,
        "contact": None,
    }
    values.update(overrides)
    return ProfileDraft(**values)  # type: ignore[arg-type]


class Clock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def __call__(self) -> datetime:
        return self.moment


@pytest.fixture
def repo() -> FakeProfileRepository:
    return FakeProfileRepository()


@pytest.fixture
def clock() -> Clock:
    return Clock(T1)


@pytest.fixture
def service(repo: FakeProfileRepository, clock: Clock) -> ProfileService:
    return ProfileService(repo, clock)  # type: ignore[arg-type]


async def test_location_is_coarsened_before_it_reaches_the_repository(
    service: ProfileService, repo: FakeProfileRepository
):
    await service.put_profile(uuid4(), make_draft())

    stored = repo.records[0].cell
    assert stored == coarsen(LAT, LON)
    assert (stored.latitude, stored.longitude) != (LAT, LON)
    assert str(LAT) not in repr(repo.records[0])
    assert str(LON) not in repr(repo.records[0])


async def test_capabilities_are_stored_with_consent_and_stamp_the_time(
    service: ProfileService, repo: FakeProfileRepository
):
    owner = await service.put_profile(uuid4(), make_draft())

    assert len(owner.capabilities) == 1
    assert owner.functional_consent_at == T1
    assert repo.records[0].functional_consent_at == T1


async def test_capabilities_are_dropped_without_consent(
    service: ProfileService, repo: FakeProfileRepository
):
    owner = await service.put_profile(uuid4(), make_draft(functional_data_consent=False))

    assert owner.capabilities == ()
    assert owner.functional_consent_at is None
    assert repo.records[0].capabilities == ()


async def test_withdrawing_consent_deletes_capabilities_and_timestamp(service: ProfileService):
    user_id = uuid4()
    await service.put_profile(user_id, make_draft())

    owner = await service.put_profile(user_id, make_draft(functional_data_consent=False))

    assert owner.capabilities == ()
    assert owner.functional_consent_at is None


async def test_the_first_consent_time_is_kept_on_later_saves(service: ProfileService, clock: Clock):
    user_id = uuid4()
    await service.put_profile(user_id, make_draft())
    clock.moment = T2

    owner = await service.put_profile(user_id, make_draft(display_name="Renamed"))

    assert owner.functional_consent_at == T1
    assert owner.display_name == "Renamed"


async def test_consent_after_withdrawal_gets_a_new_timestamp(service: ProfileService, clock: Clock):
    user_id = uuid4()
    await service.put_profile(user_id, make_draft())
    await service.put_profile(user_id, make_draft(functional_data_consent=False))
    clock.moment = T2

    owner = await service.put_profile(user_id, make_draft())

    assert owner.functional_consent_at == T2


async def test_get_my_profile_and_missing_profile(service: ProfileService):
    user_id = uuid4()
    with pytest.raises(NotFoundError):
        await service.get_my_profile(user_id)

    created = await service.put_profile(user_id, make_draft())

    assert await service.get_my_profile(user_id) == created


async def test_public_profile_hides_private_fields(service: ProfileService):
    created = await service.put_profile(uuid4(), make_draft(contact="t.me/orest"))

    public = await service.get_public_profile(created.id)

    assert public.display_name == "Orest"
    assert not hasattr(public, "capabilities")
    assert not hasattr(public, "contact")


async def test_hidden_and_missing_public_profiles_are_not_found_alike(service: ProfileService):
    hidden = await service.put_profile(uuid4(), make_draft(is_visible=False))

    with pytest.raises(NotFoundError) as hidden_error:
        await service.get_public_profile(hidden.id)
    with pytest.raises(NotFoundError) as missing_error:
        await service.get_public_profile(uuid4())

    assert hidden_error.value.message == missing_error.value.message


async def test_delete_my_profile(service: ProfileService):
    user_id = uuid4()
    await service.put_profile(user_id, make_draft())

    await service.delete_my_profile(user_id)

    with pytest.raises(NotFoundError):
        await service.get_my_profile(user_id)
    with pytest.raises(NotFoundError):
        await service.delete_my_profile(user_id)


async def test_a_draft_without_location_keeps_the_stored_cell(
    service: ProfileService, repo: FakeProfileRepository
):
    user_id = uuid4()
    await service.put_profile(user_id, make_draft())

    owner = await service.put_profile(
        user_id, make_draft(latitude=None, longitude=None, contact="t.me/new")
    )

    assert repo.records[1].cell is None
    assert owner.contact == "t.me/new"


async def test_a_draft_with_a_location_replaces_the_stored_cell(
    service: ProfileService, repo: FakeProfileRepository
):
    user_id = uuid4()
    await service.put_profile(user_id, make_draft())

    await service.put_profile(user_id, make_draft(latitude=49.8397, longitude=24.0297))

    assert repo.records[1].cell == coarsen(49.8397, 24.0297)


async def test_a_first_save_without_location_is_refused_and_stores_nothing(
    service: ProfileService, repo: FakeProfileRepository
):
    with pytest.raises(LocationRequiredError) as caught:
        await service.put_profile(uuid4(), make_draft(latitude=None, longitude=None))

    assert caught.value.message == LOCATION_REQUIRED_MESSAGE
    assert repo.records == []
