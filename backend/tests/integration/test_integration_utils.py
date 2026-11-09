from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db


async def test_health_answers_without_database(app: FastAPI, client: httpx.AsyncClient):
    async def broken() -> AsyncIterator[AsyncSession]:
        raise AssertionError("health must not open a session")
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = broken

    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_runs_select_one(client: httpx.AsyncClient):
    response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.parametrize(
    "failure",
    [
        OperationalError("SELECT 1", {}, Exception("postgresql://user:pw@host/db")),
        ConnectionRefusedError("connect to postgresql://user:pw@host/db failed"),
        OSError("postgresql://user:pw@host/db unreachable"),
        TimeoutError("postgresql://user:pw@host/db"),
    ],
    ids=["sqlalchemy", "refused", "oserror", "timeout"],
)
async def test_ready_reports_unavailable_database_without_details(
    app: FastAPI, client: httpx.AsyncClient, failure: Exception
):
    class BrokenSession:
        async def execute(self, *args: object, **kwargs: object) -> None:
            raise failure

    async def broken() -> AsyncIterator[BrokenSession]:
        yield BrokenSession()

    app.dependency_overrides[get_db] = broken

    response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "pw" not in response.text


async def test_openapi_is_served_under_api_v1(client: httpx.AsyncClient):
    response = await client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    assert {"/health", "/ready"} <= set(response.json()["paths"])
