from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.mail import MemoryMailSender
from app.core.security import PasswordHasher, TokenCodec
from app.domain.errors import AuthenticationError, ConflictError, NotFoundError
from app.domain.password_reset import InvalidResetError
from app.domain.verification import InvalidVerificationError, hash_token
from app.services.auth import AuthService, VerificationPolicy
from tests.conftest import make_settings
from tests.unit.services.fakes import (
    FakeResetRepository,
    FakeUserRepository,
    FakeVerificationRepository,
)

T0 = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
POLICY = VerificationPolicy(
    base_url="https://porych.life", ttl=timedelta(hours=24), resend_after=timedelta(seconds=60)
)


class Clock:
    def __init__(self) -> None:
        self.moment = T0

    def __call__(self) -> datetime:
        return self.moment


PASSWORD = "correct horse battery"


@pytest.fixture
def users() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def outbox() -> MemoryMailSender:
    return MemoryMailSender()


@pytest.fixture
def verifications(users: FakeUserRepository) -> FakeVerificationRepository:
    return FakeVerificationRepository(users)


@pytest.fixture
def service(
    users: FakeUserRepository,
    verifications: FakeVerificationRepository,
    outbox: MemoryMailSender,
    clock: Clock,
) -> AuthService:
    settings = make_settings()
    return AuthService(
        users,  # type: ignore[arg-type]
        PasswordHasher(settings),
        TokenCodec(settings),
        verifications,  # type: ignore[arg-type]
        outbox,
        POLICY,
        FakeResetRepository(users),  # type: ignore[arg-type]
        clock=clock,
    )


def token_of(outbox: MemoryMailSender) -> str:
    """Take the token out of the link in the latest message."""
    return outbox.sent[-1].text.split("#token=")[1].split()[0]


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
    service = AuthService(
        users,  # type: ignore[arg-type]
        PasswordHasher(strong_settings),
        TokenCodec(strong_settings),
        FakeVerificationRepository(users),  # type: ignore[arg-type]
        MemoryMailSender(),
        POLICY,
        FakeResetRepository(users),  # type: ignore[arg-type]
    )
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


async def test_registration_sends_a_link_and_stores_only_its_digest(
    service: AuthService,
    verifications: FakeVerificationRepository,
    outbox: MemoryMailSender,
):
    account = await service.register("a@example.org", PASSWORD)

    assert not account.is_verified
    assert len(outbox.sent) == 1
    mail = outbox.sent[0]
    assert mail.to == "a@example.org"
    token = token_of(outbox)
    # The link starts at the client and keeps the token in the fragment, out of any server log
    assert f"https://porych.life/verify-email#token={token}" in mail.text
    assert list(verifications.tokens) == [hash_token(token)]
    assert token not in verifications.tokens


async def test_registration_still_succeeds_when_the_mail_server_is_down(
    service: AuthService, users: FakeUserRepository, caplog: pytest.LogCaptureFixture
):
    class Broken:
        async def send(self, mail) -> None:
            raise OSError("connection refused for a@example.org")

    service.mail = Broken()  # type: ignore[assignment]

    account = await service.register("a@example.org", PASSWORD)

    assert account.id in users.accounts
    assert "OSError" in caplog.text
    assert "a@example.org" not in caplog.text


async def test_the_link_confirms_the_account_once(
    service: AuthService, users: FakeUserRepository, outbox: MemoryMailSender
):
    account = await service.register("a@example.org", PASSWORD)
    token = token_of(outbox)

    await service.confirm_email(token)

    assert users.accounts[account.id].is_verified
    with pytest.raises(InvalidVerificationError):
        await service.confirm_email(token)


async def test_an_expired_or_unknown_token_is_the_same_invalid_error(
    service: AuthService, clock: Clock, outbox: MemoryMailSender
):
    await service.register("a@example.org", PASSWORD)
    token = token_of(outbox)
    clock.moment = T0 + timedelta(hours=24, seconds=1)

    with pytest.raises(InvalidVerificationError) as expired:
        await service.confirm_email(token)
    with pytest.raises(InvalidVerificationError) as unknown:
        await service.confirm_email("x" * 43)

    assert expired.value.message == unknown.value.message


async def test_resending_replaces_the_old_link(
    service: AuthService, clock: Clock, outbox: MemoryMailSender
):
    account = await service.register("a@example.org", PASSWORD)
    first = token_of(outbox)
    clock.moment = T0 + timedelta(minutes=5)

    await service.resend_confirmation(account)
    second = token_of(outbox)

    assert second != first
    with pytest.raises(InvalidVerificationError):
        await service.confirm_email(first)
    await service.confirm_email(second)


async def test_resending_is_throttled_and_never_reports_it(
    service: AuthService, clock: Clock, outbox: MemoryMailSender
):
    account = await service.register("a@example.org", PASSWORD)
    clock.moment = T0 + timedelta(seconds=30)

    await service.resend_confirmation(account)
    await service.resend_confirmation(account)

    assert len(outbox.sent) == 1


async def test_a_confirmed_account_is_sent_nothing(
    service: AuthService, users: FakeUserRepository, outbox: MemoryMailSender
):
    account = await service.register("a@example.org", PASSWORD)
    await service.confirm_email(token_of(outbox))
    outbox.sent.clear()

    await service.resend_confirmation(users.accounts[account.id])

    assert outbox.sent == []


async def test_a_confirmed_registration_sends_nothing_and_is_verified(
    service: AuthService, outbox: MemoryMailSender
):
    account = await service.register_confirmed("demo@example.invalid", PASSWORD)

    assert account.is_verified
    assert outbox.sent == []


# --- password reset ---------------------------------------------------------------------------


async def test_a_reset_link_is_mailed_and_only_its_digest_is_stored(
    service: AuthService, outbox: MemoryMailSender, users: FakeUserRepository
):
    account = await users.create_user("a@example.org", "hash")

    await service.request_password_reset("a@example.org")

    mail = outbox.sent[-1]
    token = token_of(outbox)
    assert mail.to == "a@example.org"
    assert "https://porych.life/reset-password#token=" in mail.text
    assert mail.html is not None and token in mail.html
    assert hash_token(token) in service.resets.tokens  # type: ignore[attr-defined]
    assert token not in service.resets.tokens  # type: ignore[attr-defined]
    assert account.id == service.resets.tokens[hash_token(token)][0]  # type: ignore[attr-defined]


async def test_an_unknown_address_gets_nothing_and_raises_nothing(
    service: AuthService, outbox: MemoryMailSender
):
    await service.request_password_reset("nobody@example.org")

    assert outbox.sent == []


async def test_a_second_request_inside_the_cooldown_is_silent(
    service: AuthService, outbox: MemoryMailSender, users: FakeUserRepository, clock: Clock
):
    await users.create_user("a@example.org", "hash")
    await service.request_password_reset("a@example.org")
    clock.moment = T0 + timedelta(seconds=30)
    await service.request_password_reset("a@example.org")
    assert len(outbox.sent) == 1

    clock.moment = T0 + timedelta(seconds=61)
    await service.request_password_reset("a@example.org")
    assert len(outbox.sent) == 2


async def test_the_reset_message_can_be_deferred_until_after_the_response(
    users: FakeUserRepository, outbox: MemoryMailSender, clock: Clock
):
    settings = make_settings()
    queued: list = []
    service = AuthService(
        users,  # type: ignore[arg-type]
        PasswordHasher(settings),
        TokenCodec(settings),
        FakeVerificationRepository(users),  # type: ignore[arg-type]
        outbox,
        POLICY,
        FakeResetRepository(users),  # type: ignore[arg-type]
        defer=lambda send, mail: queued.append((send, mail)),
        clock=clock,
    )
    await users.create_user("a@example.org", "hash")

    await service.request_password_reset("a@example.org")

    assert outbox.sent == []
    send, mail = queued[0]
    await send(mail)
    assert len(outbox.sent) == 1


async def test_a_delivery_failure_never_breaks_a_reset_request(
    users: FakeUserRepository, clock: Clock, caplog: pytest.LogCaptureFixture
):
    class Broken:
        async def send(self, mail) -> None:
            raise OSError("smtp down: a@example.org")

    settings = make_settings()
    service = AuthService(
        users,  # type: ignore[arg-type]
        PasswordHasher(settings),
        TokenCodec(settings),
        FakeVerificationRepository(users),  # type: ignore[arg-type]
        Broken(),
        POLICY,
        FakeResetRepository(users),  # type: ignore[arg-type]
        clock=clock,
    )
    await users.create_user("a@example.org", "hash")

    await service.request_password_reset("a@example.org")

    assert "OSError" in caplog.text
    assert "a@example.org" not in caplog.text


async def test_the_link_sets_a_new_password_once(
    service: AuthService, outbox: MemoryMailSender, users: FakeUserRepository
):
    await service.register("a@example.org", PASSWORD)
    await service.request_password_reset("a@example.org")
    token = token_of(outbox)

    await service.reset_password(token, "another long passphrase")

    assert await service.login("a@example.org", "another long passphrase")
    with pytest.raises(AuthenticationError):
        await service.login("a@example.org", PASSWORD)
    with pytest.raises(InvalidResetError):
        await service.reset_password(token, "yet another passphrase")
    # The mailbox is proved by the link, so the account counts as confirmed now
    assert (await users.get_user_by_email("a@example.org")).is_verified  # type: ignore[union-attr]


async def test_an_expired_or_unknown_reset_token_is_the_same_invalid_error(
    service: AuthService, outbox: MemoryMailSender, users: FakeUserRepository, clock: Clock
):
    await users.create_user("a@example.org", "hash")
    await service.request_password_reset("a@example.org")
    token = token_of(outbox)
    clock.moment = T0 + timedelta(hours=1, seconds=1)

    with pytest.raises(InvalidResetError) as expired:
        await service.reset_password(token, "another long passphrase")
    with pytest.raises(InvalidResetError) as unknown:
        await service.reset_password("x" * 43, "another long passphrase")

    assert expired.value.message == unknown.value.message


async def test_a_new_request_replaces_the_old_link(
    service: AuthService, outbox: MemoryMailSender, users: FakeUserRepository, clock: Clock
):
    await users.create_user("a@example.org", "hash")
    await service.request_password_reset("a@example.org")
    first = token_of(outbox)
    clock.moment = T0 + timedelta(minutes=5)
    await service.request_password_reset("a@example.org")
    second = token_of(outbox)

    assert first != second
    with pytest.raises(InvalidResetError):
        await service.reset_password(first, "another long passphrase")
    await service.reset_password(second, "another long passphrase")


async def test_a_token_issued_before_the_reset_stops_working(
    service: AuthService, outbox: MemoryMailSender, clock: Clock
):
    # Tokens are checked against the real clock, so the reset happens a few seconds ago
    reset_time = datetime.now(UTC).replace(microsecond=0) - timedelta(seconds=10)
    account = await service.register("a@example.org", PASSWORD)
    before = service.tokens.issue(account.id, now=reset_time - timedelta(minutes=5))
    clock.moment = reset_time
    await service.request_password_reset("a@example.org")
    await service.reset_password(token_of(outbox), "another long passphrase")
    after = service.tokens.issue(account.id, now=reset_time + timedelta(seconds=2))

    with pytest.raises(AuthenticationError):
        await service.authenticate(before)
    assert (await service.authenticate(after)).id == account.id


async def test_a_token_issued_in_the_same_second_as_the_reset_still_works(
    service: AuthService, outbox: MemoryMailSender, clock: Clock
):
    reset_time = datetime.now(UTC).replace(microsecond=900_000) - timedelta(seconds=10)
    account = await service.register("a@example.org", PASSWORD)
    clock.moment = reset_time
    await service.request_password_reset("a@example.org")
    await service.reset_password(token_of(outbox), "another long passphrase")
    same_second = service.tokens.issue(account.id, now=reset_time.replace(microsecond=0))

    assert (await service.authenticate(same_second)).id == account.id
