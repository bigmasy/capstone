"""Liveness and readiness routes."""

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import HealthServiceDep

router = APIRouter(tags=["utils"])


class HealthResponse(BaseModel):
    """Liveness answer."""

    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    """Readiness answer."""

    status: Literal["ready"] = "ready"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report that the process is alive; does not touch the database.

    :return: Static ``ok`` status.
    """
    return HealthResponse()


@router.get("/ready", response_model=ReadyResponse)
async def ready(service: HealthServiceDep) -> ReadyResponse:
    """Report that the database answers.

    :param service: Readiness service.
    :raises HTTPException: 503 when the database is unreachable. This module is the API layer,
        which is the only place allowed to raise HTTP errors.
    :return: Static ``ready`` status.
    """
    if not await service.is_ready():
        # Never forward the cause: a driver message can contain the connection URL.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable"
        )
    return ReadyResponse()
