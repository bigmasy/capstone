from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.security import PasswordHasher, TokenCodec
from app.domain.errors import AuthenticationError, ConflictError, NotFoundError
from app.services.auth import AuthService
from tests.conftest import make_settings
from tests.unit.services.fakes import FakeUserRepository

PASSWORD = "correct horse battery"


@pytest.fixture
def users() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def service(users: FakeUserRepository) -> AuthService:
    settings = make_settings()
    return AuthService(users, PasswordHasher(settings), TokenCodec(settings))  # type: ignore[arg-type]


async def test_register_stores_a_hash_not_the_password(
    service: AuthService, users: FakeUserRepository
):
    account = await service.register("Orest@Example.org", PASSWORD)

    assert account.email == "orest@example.org"
    assert account.password_hash.startswith("$argon2id$")
    assert PASSWORD not in account.password_hash
    assert len(users.accounts) == 1


async def test_duplicate_registration_is_a_generic_conflict(service: AuthService):
    await service.register("a@example.org", PASSWORD)

    with pytest.raises(ConflictError) as caught:
        await service.register("A@example.org", PASSWORD)

    assert "a@example.org" not in caught.value.message.lower()


async def test_login_returns_a_token_for_the_account(service: AuthService):
    account = await service.register("a@example.org", PASSWORD)

    token = await service.login("A@example.org", PASSWORD)

    assert (await service.authenticate(token)).id == account.id


async def test_unknown_email_and_wrong_password_look_identical(service: AuthService):
    await service.register("a@example.org", PASSWORD)

    with pytest.raises(AuthenticationError) as unknown:
        await service.login("nobody@example.org", PASSWORD)
    with pytest.raises(AuthenticationError) as wrong:
        await service.login("a@example.org", PASSWORD + "x")

    assert unknown.value.message == wrong.value.message
    assert type(unknown.value) is type(wrong.value)


async def test_unknown_email_still_does_a_password_verification(
    service: AuthService, monkeypatch: pytest.MonkeyPatch
):
    calls: list[str] = []
    original = service.hasher.verify

    def spy(password_hash: str, password: str) -> bool:
        calls.append(password_hash)
        return original(password_hash, password)

    monkeypatch.setattr(service.hasher, "verify", spy)

    with pytest.raises(AuthenticationError):
        await service.login("nobody@example.org", PASSWORD)

    assert calls == [service.hasher.dummy_hash]


async def test_login_upgrades_a_weak_hash(users: FakeUserRepository):
    weak = PasswordHasher(make_settings(ARGON2_TIME_COST=1))
    strong_settings = make_settings(ARGON2_TIME_COST=2)
    service = AuthService(users, PasswordHasher(strong_settings), TokenCodec(strong_settings))  # type: ignore[arg-type]
    account = await users.create_user("a@example.org", weak.hash(PASSWORD))

    await service.login("a@example.org", PASSWORD)

    upgraded = users.accounts[account.id].password_hash
    assert upgraded != account.password_hash
    assert not service.hasher.needs_rehash(upgraded)


async def test_authenticate_rejects_a_token_of_a_deleted_user(service: AuthService):
    account = await service.register("a@example.org", PASSWORD)
    token = await service.login("a@example.org", PASSWORD)

    await service.delete_account(account.id)

    with pytest.raises(AuthenticationError):
        await service.authenticate(token)


async def test_authenticate_rejects_garbage_and_expired_tokens(service: AuthService):
    account = await service.register("a@example.org", PASSWORD)
    expired = service.tokens.issue(account.id, now=datetime.now(UTC) - timedelta(hours=1))

    for token in ("garbage", expired):
        with pytest.raises(AuthenticationError):
            await service.authenticate(token)


async def test_token_for_an_unknown_user_is_rejected(service: AuthService):
    with pytest.raises(AuthenticationError):
        await service.authenticate(service.tokens.issue(uuid4()))


async def test_delete_account_removes_it_and_reports_missing(
    service: AuthService, users: FakeUserRepository
):
    account = await service.register("a@example.org", PASSWORD)

    await service.delete_account(account.id)

    assert users.removed == [account.id]
    with pytest.raises(NotFoundError):
        await service.delete_account(account.id)
