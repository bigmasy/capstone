"""Application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, invitations, matches, profiles, taxonomy, utils
from app.api.handlers import register_exception_handlers
from app.composition import build_ranker
from app.conf.config import Settings, get_settings
from app.core.logging import configure_logging, install_access_log
from app.database.db import DatabaseSessionManager

API_PREFIX = "/api/v1"

# Routers mounted under /api/v1, one per line to keep merges trivial. Liveness and readiness
# are mounted without a prefix because probes and the proxy health check use the bare paths.
V1_ROUTERS: list[APIRouter] = [
    auth.router,
    profiles.router,
    invitations.router,
    matches.router,
    taxonomy.router,
]

CORS_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_HEADERS = ["Authorization", "Content-Type"]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application.

    Nothing runs at import time; the database engine is created in the lifespan and disposed on
    shutdown. Tables are never created here, migrations are the only schema authority.

    :param settings: Settings to use; read from the environment when omitted.
    :return: The configured application.
    """
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Create the session manager on startup and dispose it on shutdown."""
        manager = DatabaseSessionManager(settings)
        app.state.db = manager
        try:
            yield
        finally:
            await manager.close()

    # The schema and the interactive docs are a map of the API for an attacker: served outside
    # prod only. The committed export is built from test settings, see app.tools.export_openapi.
    expose_docs = settings.ENV != "prod"
    app = FastAPI(
        title="Partner matching API for adaptive sport",
        version="0.1.0",
        openapi_url=f"{API_PREFIX}/openapi.json" if expose_docs else None,
        docs_url=f"{API_PREFIX}/docs" if expose_docs else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    # One scorer per process: loading a model is slow and the scorer is read-only
    app.state.scorer = build_ranker(settings)

    # Explicit origins and no credentials: the token travels in the Authorization header,
    # not in a cookie, so cross-site requests cannot ride on ambient credentials.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=CORS_METHODS,
        allow_headers=CORS_HEADERS,
    )
    install_access_log(app)
    register_exception_handlers(app)

    app.include_router(utils.router)
    for router in V1_ROUTERS:
        app.include_router(router, prefix=API_PREFIX)
    return app
