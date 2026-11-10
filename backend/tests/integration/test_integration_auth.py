from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import jwt

from tests.conftest import make_settings
from tests.integration.helpers import PASSWORD, sign_up, sign_up_with_profile


async def test_register_returns_the_account_without_secrets(client: httpx.AsyncClient):
    response = await client.post(
        "/api/v1/auth/register", json={"email": "Orest@Example.org", "password": PASSWORD}
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "email", "created_at", "email_verified"}
    assert body["email_verified"] is False
    assert body["email"] == "orest@example.org"
    assert PASSWORD not in response.text
    assert "argon2" not in response.text


async def test_duplicate_registration_conflicts_with_a_generic_message(client: httpx.AsyncClient):
    payload = {"email": "a@example.org", "password": PASSWORD}
    await client.post("/api/v1/auth/register", json=payload)

    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 409
    assert "a@example.org" not in response.text


async def test_registration_validation_errors_do_not_echo_input(client: httpx.AsyncClient):
    response = await client.post(
        "/api/v1/auth/register", json={"email": "not-an-email", "password": "short-secret"}
    )

    assert response.status_code == 422
    assert "not-an-email" not in response.text
    assert "short-secret" not in response.text
    for error in response.json()["detail"]:
        assert set(error) == {"type", "loc", "msg"}


async def test_unknown_body_keys_are_masked_in_the_error_location(client: httpx.AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.org", "password": PASSWORD, "canary-key-123": 1},
    )

    assert response.status_code == 422
    assert "canary-key-123" not in response.text
    assert ["body", "?"] in [error["loc"] for error in response.json()["detail"]]


async def test_profile_body_keys_are_masked_too(client: httpx.AsyncClient):
    actor = await sign_up(client)

    response = await client.put(
        "/api/v1/profiles/me",
        json={"canary-key-456": 1, "sports": [{"sport": "swimming", "canary-nested-789": 1}]},
        headers=actor.headers,
    )

    assert response.status_code == 422
    assert "canary-key-456" not in response.text
    assert "canary-nested-789" not in response.text


async def test_login_returns_a_bearer_token(client: httpx.AsyncClient):
    await client.post(
        "/api/v1/auth/register", json={"email": "a@example.org", "password": PASSWORD}
    )

    response = await client.post(
        "/api/v1/auth/login", json={"email": "A@Example.org", "password": PASSWORD}
    )

    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "token_type"}
    assert response.json()["token_type"] == "bearer"


async def test_wrong_password_and_unknown_email_get_the_same_answer(client: httpx.AsyncClient):
    await client.post(
        "/api/v1/auth/register", json={"email": "a@example.org", "password": PASSWORD}
    )

    wrong = await client.post(
        "/api/v1/auth/login", json={"email": "a@example.org", "password": "wrong-password"}
    )
    unknown = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.org", "password": "wrong-password"}
    )
    short = await client.post(
        "/api/v1/auth/login", json={"email": "a@example.org", "password": "x"}
    )

    assert wrong.status_code == unknown.status_code == short.status_code == 401
    assert wrong.json() == unknown.json() == short.json()
    assert wrong.headers["www-authenticate"] == "Bearer"


async def test_me_returns_the_own_account(client: httpx.AsyncClient):
    actor = await sign_up(client)

    response = await client.get("/api/v1/auth/me", headers=actor.headers)

    assert response.status_code == 200
    assert response.json()["id"] == actor.user_id
    assert response.json()["email"] == actor.email


async def test_missing_or_malformed_credentials_are_401_not_403(client: httpx.AsyncClient):
    for headers in ({}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer"}):
        response = await client.get("/api/v1/auth/me", headers=headers)

        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"


def forged(secret: str, **claims: object) -> dict[str, str]:
    settings = make_settings()
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": str(uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    payload.update(claims)
    return {"Authorization": f"Bearer {jwt.encode(payload, secret, algorithm='HS256')}"}


async def test_forged_expired_and_foreign_tokens_are_rejected(client: httpx.AsyncClient):
    actor = await sign_up(client)
    secret = make_settings().JWT_SECRET.get_secret_value()
    cases = [
        forged(secret, sub=actor.user_id, exp=datetime.now(UTC) - timedelta(minutes=1)),
        forged("another-secret-another-secret-another", sub=actor.user_id),
        forged(secret, sub=actor.user_id, aud="other"),
        forged(secret, sub=actor.user_id, iss="other"),
        forged(secret),  # valid signature, but the user does not exist
        {"Authorization": "Bearer " + jwt.encode({"sub": actor.user_id}, None, algorithm="none")},
    ]

    for headers in cases:
        assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401


async def test_deleting_the_account_removes_the_profile_and_kills_the_token(
    client: httpx.AsyncClient,
):
    actor, profile = await sign_up_with_profile(client)
    viewer = await sign_up(client)

    deleted = await client.delete("/api/v1/auth/me", headers=actor.headers)

    assert deleted.status_code == 204
    assert (await client.get("/api/v1/auth/me", headers=actor.headers)).status_code == 401
    assert (
        await client.get(f"/api/v1/profiles/{profile['id']}", headers=viewer.headers)
    ).status_code == 404
    relogin = await client.post(
        "/api/v1/auth/login", json={"email": actor.email, "password": PASSWORD}
    )
    assert relogin.status_code == 401
