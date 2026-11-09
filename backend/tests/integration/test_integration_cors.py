import httpx
import pytest
from fastapi import FastAPI

from app.main import create_app
from tests.conftest import make_settings

ALLOWED = "http://localhost:5173"
OTHER = "https://evil.example"


async def test_allowed_origin_is_echoed(client: httpx.AsyncClient):
    response = await client.get("/health", headers={"Origin": ALLOWED})

    assert response.headers["access-control-allow-origin"] == ALLOWED
    assert "access-control-allow-credentials" not in response.headers


async def test_other_origin_gets_no_cors_headers(client: httpx.AsyncClient):
    response = await client.get("/health", headers={"Origin": OTHER})

    assert "access-control-allow-origin" not in response.headers


async def test_preflight_from_allowed_origin(client: httpx.AsyncClient):
    response = await client.options(
        "/health",
        headers={
            "Origin": ALLOWED,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers
    assert "*" not in allowed_headers
    assert "*" not in response.headers["access-control-allow-methods"]


async def test_preflight_from_other_origin_is_rejected(client: httpx.AsyncClient):
    response = await client.options(
        "/health",
        headers={"Origin": OTHER, "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


async def test_preflight_with_unlisted_header_is_rejected(client: httpx.AsyncClient):
    response = await client.options(
        "/health",
        headers={
            "Origin": ALLOWED,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-custom-secret",
        },
    )

    assert response.status_code == 400


@pytest.mark.parametrize("origin", [ALLOWED, OTHER])
async def test_never_a_wildcard(client: httpx.AsyncClient, origin: str):
    response = await client.get("/health", headers={"Origin": origin})

    assert response.headers.get("access-control-allow-origin") != "*"


async def test_origins_come_from_settings():
    app: FastAPI = create_app(make_settings(CORS_ORIGINS=[OTHER]))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        accepted = await http.get("/health", headers={"Origin": OTHER})
        refused = await http.get("/health", headers={"Origin": ALLOWED})

    assert accepted.headers["access-control-allow-origin"] == OTHER
    assert "access-control-allow-origin" not in refused.headers
