from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.core.security import PasswordHasher, TokenCodec
from app.domain.errors import AuthenticationError
from tests.conftest import make_settings

PASSWORD = "correct horse battery"


@pytest.fixture
def hasher() -> PasswordHasher:
    return PasswordHasher(make_settings())


@pytest.fixture
def codec() -> TokenCodec:
    return TokenCodec(make_settings())


def test_hash_is_argon2id_and_salted(hasher: PasswordHasher):
    first, second = hasher.hash(PASSWORD), hasher.hash(PASSWORD)

    assert first.startswith("$argon2id$")
    assert first != second
    assert PASSWORD not in first


def test_verify_accepts_right_and_rejects_wrong_password(hasher: PasswordHasher):
    stored = hasher.hash(PASSWORD)

    assert hasher.verify(stored, PASSWORD) is True
    assert hasher.verify(stored, PASSWORD + "x") is False


def test_verify_rejects_garbage_hash_without_raising(hasher: PasswordHasher):
    assert hasher.verify("not-a-hash", PASSWORD) is False


@pytest.mark.parametrize("password", ["short", "x" * 9, "x" * 129, ""])
def test_hash_enforces_password_policy(hasher: PasswordHasher, password: str):
    with pytest.raises(ValueError, match="password policy"):
        hasher.hash(password)


@pytest.mark.parametrize("length", [10, 128])
def test_policy_bounds_are_inclusive(hasher: PasswordHasher, length: int):
    assert hasher.hash("x" * length)


def test_needs_rehash_when_cost_parameters_change():
    old = PasswordHasher(make_settings(ARGON2_TIME_COST=1))
    new = PasswordHasher(make_settings(ARGON2_TIME_COST=2))
    stored = old.hash(PASSWORD)

    assert old.needs_rehash(stored) is False
    assert new.needs_rehash(stored) is True


def test_dummy_hash_is_valid_and_never_matches(hasher: PasswordHasher):
    dummy = hasher.dummy_hash

    assert dummy.startswith("$argon2id$")
    assert hasher.verify(dummy, PASSWORD) is False


def test_token_roundtrip_returns_subject(codec: TokenCodec):
    user_id = uuid4()

    assert codec.decode(codec.issue(user_id)) == user_id


def test_token_carries_the_required_claims(codec: TokenCodec):
    token = codec.issue(uuid4(), now=datetime(2026, 1, 1, tzinfo=UTC))

    claims = jwt.decode(token, options={"verify_signature": False})

    assert set(claims) == {"sub", "iat", "exp", "iss", "aud"}
    assert claims["exp"] - claims["iat"] == 1800


def test_expired_token_is_rejected(codec: TokenCodec):
    token = codec.issue(uuid4(), now=datetime.now(UTC) - timedelta(hours=2))

    with pytest.raises(AuthenticationError):
        codec.decode(token)


def test_token_signed_with_another_secret_is_rejected(codec: TokenCodec):
    other = TokenCodec(make_settings(JWT_SECRET="o" * 40))

    with pytest.raises(AuthenticationError):
        codec.decode(other.issue(uuid4()))


def _claims(**overrides: object) -> dict[str, object]:
    now = datetime.now(UTC)
    settings = make_settings()
    claims: dict[str, object] = {
        "sub": str(uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    claims.update(overrides)
    return claims


def _forge(**overrides: object) -> str:
    return jwt.encode(
        _claims(**overrides), make_settings().JWT_SECRET.get_secret_value(), algorithm="HS256"
    )


def test_forging_helper_produces_an_accepted_token(codec: TokenCodec):
    assert codec.decode(_forge())


def test_alg_none_token_is_rejected(codec: TokenCodec):
    token = jwt.encode(_claims(), None, algorithm="none")

    with pytest.raises(AuthenticationError):
        codec.decode(token)


@pytest.mark.parametrize("claim", ["iss", "aud"])
def test_wrong_issuer_or_audience_is_rejected(codec: TokenCodec, claim: str):
    with pytest.raises(AuthenticationError):
        codec.decode(_forge(**{claim: "someone-else"}))


@pytest.mark.parametrize("claim", ["sub", "exp", "iat", "iss", "aud"])
def test_missing_claim_is_rejected(codec: TokenCodec, claim: str):
    claims = _claims()
    del claims[claim]
    token = jwt.encode(claims, make_settings().JWT_SECRET.get_secret_value(), algorithm="HS256")

    with pytest.raises(AuthenticationError):
        codec.decode(token)


def test_subject_must_be_a_uuid(codec: TokenCodec):
    with pytest.raises(AuthenticationError):
        codec.decode(_forge(sub="not-a-uuid"))


@pytest.mark.parametrize("token", ["", "abc", "a.b.c", "x" * 5000])
def test_garbage_token_is_rejected(codec: TokenCodec, token: str):
    with pytest.raises(AuthenticationError):
        codec.decode(token)


def test_error_message_does_not_reveal_the_reason(codec: TokenCodec):
    messages = set()
    for token in ["abc", _forge(aud="x"), _forge(sub="bad")]:
        with pytest.raises(AuthenticationError) as caught:
            codec.decode(token)
        messages.add(caught.value.message)

    assert len(messages) == 1


def test_decode_with_issue_time_returns_the_subject_and_whole_seconds():
    codec = TokenCodec(make_settings())
    now = datetime.now(UTC).replace(microsecond=0) - timedelta(seconds=30)
    user_id = uuid4()

    subject, issued = codec.decode_with_issue_time(codec.issue(user_id, now=now))

    assert subject == user_id
    assert issued == now


def test_decode_with_issue_time_rejects_a_forged_token():
    codec = TokenCodec(make_settings())

    with pytest.raises(AuthenticationError):
        codec.decode_with_issue_time("not.a.token")
