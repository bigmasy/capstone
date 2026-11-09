"""Dependencies shared by the routers: settings, services and the current user."""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.composition import (
    build_auth_service,
    build_health_service,
    build_invitation_service,
    build_matching_service,
    build_profile_service,
)
from app.conf.config import Settings
from app.database.db import DbSession
from app.domain.account import Account
from app.domain.errors import AuthenticationError
from app.domain.matching.scorer import Scorer
from app.services.auth import AuthService
from app.services.health import HealthService
from app.services.invitations import InvitationService
from app.services.matching import MatchingService
from app.services.profiles import ProfileService

# auto_error is off so a missing header raises the domain AuthenticationError and is answered
# with 401 and a Bearer challenge like every other authentication failure (FastAPI would
# answer 403 on its own).
bearer_scheme = HTTPBearer(auto_error=False, description="Access token from POST /auth/login")


def get_app_settings(request: Request) -> Settings:
    """Return the settings the running application was built with.

    :param request: Current request.
    :return: The settings stored by ``create_app``.
    """
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def get_auth_service(db: DbSession, settings: SettingsDep) -> AuthService:
    """Build the authentication service for one request.

    :param db: Database session of the request.
    :param settings: Application settings.
    :return: The service.
    """
    return build_auth_service(db, settings)


def get_profile_service(db: DbSession) -> ProfileService:
    """Build the profile service for one request.

    :param db: Database session of the request.
    :return: The service.
    """
    return build_profile_service(db)


def get_invitation_service(db: DbSession, settings: SettingsDep) -> InvitationService:
    """Build the invitation service for one request.

    :param db: Database session of the request.
    :param settings: Application settings.
    :return: The service.
    """
    return build_invitation_service(db, settings)


def get_health_service(db: DbSession) -> HealthService:
    """Build the readiness service for one request.

    :param db: Database session of the request.
    :return: The service.
    """
    return build_health_service(db)


def get_scorer(request: Request) -> Scorer:
    """Return the scorer the running application was built with.

    :param request: Current request.
    :return: The process-wide scorer stored by ``create_app``.
    """
    scorer: Scorer = request.app.state.scorer
    return scorer


ScorerDep = Annotated[Scorer, Depends(get_scorer)]


def get_matching_service(
    db: DbSession, settings: SettingsDep, scorer: ScorerDep
) -> MatchingService:
    """Build the matching service for one request.

    :param db: Database session of the request.
    :param settings: Application settings.
    :param scorer: The process-wide scorer.
    :return: The service.
    """
    return build_matching_service(db, settings, scorer)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]
InvitationServiceDep = Annotated[InvitationService, Depends(get_invitation_service)]
HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
MatchingServiceDep = Annotated[MatchingService, Depends(get_matching_service)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    service: AuthServiceDep,
) -> Account:
    """Resolve the bearer token to the current account, reloading it from the database.

    :param credentials: Parsed ``Authorization: Bearer`` header, if present.
    :param service: Authentication service.
    :raises AuthenticationError: If the header is missing, the token is invalid or expired, or
        the user no longer exists.
    :return: The account of the caller.
    """
    if credentials is None:
        raise AuthenticationError("Not authenticated")
    return await service.authenticate(credentials.credentials)


CurrentUser = Annotated[Account, Depends(get_current_user)]
