"""Composition root: wires services to repositories for one request.

The API layer must not know about sessions, queries or repositories, and services must not know
about the session type either, so the assembly lives here, the only module that sees both.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.conf.config import Settings
from app.core.security import PasswordHasher, TokenCodec
from app.domain.matching.scorer import Scorer
from app.domain.matching.weighted import WeightedScorer
from app.domain.matching.weights import DEFAULT_WEIGHTS
from app.repository.candidates import build_candidate_source
from app.repository.health import HealthRepository
from app.repository.invitations import InvitationRepository
from app.repository.profiles import ProfileRepository
from app.repository.users import UserRepository
from app.services.auth import AuthService
from app.services.health import HealthService
from app.services.invitations import InvitationService
from app.services.matching import MatchingService
from app.services.profiles import ProfileService

logger = logging.getLogger(__name__)


def build_auth_service(session: AsyncSession, settings: Settings) -> AuthService:
    """Build the authentication service for one request.

    :param session: Database session of the request, handed to the repository only.
    :param settings: Application settings.
    :return: A ready service.
    """
    return AuthService(UserRepository(session), PasswordHasher(settings), TokenCodec(settings))


def build_profile_service(session: AsyncSession) -> ProfileService:
    """Build the profile service for one request.

    :param session: Database session of the request, handed to the repository only.
    :return: A ready service.
    """
    return ProfileService(ProfileRepository(session))


def build_invitation_service(session: AsyncSession, settings: Settings) -> InvitationService:
    """Build the invitation service for one request.

    :param session: Database session of the request, handed to the repositories only.
    :param settings: Application settings; the invitation lifetime comes from here.
    :return: A ready service.
    """
    return InvitationService(
        InvitationRepository(session), ProfileRepository(session), settings.INVITATION_TTL_DAYS
    )


def build_health_service(session: AsyncSession) -> HealthService:
    """Build the readiness service for one request.

    :param session: Database session of the request, handed to the repository only.
    :return: A ready service.
    """
    return HealthService(HealthRepository(session))


def build_ranker(settings: Settings) -> Scorer:
    """Choose the scorer for the whole process: the learned ranker if it can be loaded.

    Called once when the application is built, because loading a model is slow and the scorer
    is shared by all requests. Any problem with the model, whatever its kind, leaves the weighted
    baseline in charge: recommending must not depend on an optional artifact. Only the class of
    the error is logged, never a path or a value from the files.

    :param settings: Application settings; ``RANKER_ENABLED`` and ``RANKER_ARTIFACT_DIR`` decide.
    :return: The learned scorer or the weighted baseline.
    """
    try:
        # Imported here because the ranking package needs numpy, which the runtime image may
        # not contain; the baseline must work without it
        from app.ranking.factory import build_scorer  # noqa: PLC0415

        return build_scorer(settings, settings.RANKER_ARTIFACT_DIR)
    except Exception as error:
        logger.warning("ranker could not be started (%s), using the baseline", type(error).__name__)
        return WeightedScorer(DEFAULT_WEIGHTS)


def build_matching_service(
    session: AsyncSession, settings: Settings, scorer: Scorer
) -> MatchingService:
    """Build the matching service for one request.

    :param session: Database session of the request, handed to the repositories only.
    :param settings: Application settings (radius and size limits).
    :param scorer: The process-wide scorer built by :func:`build_ranker`.
    :return: A ready service; the weighted baseline is its fallback if the scorer fails.
    """
    return MatchingService(
        ProfileRepository(session),
        build_candidate_source(session),
        scorer,
        fallback=WeightedScorer(DEFAULT_WEIGHTS),
        default_radius_km=settings.CANDIDATE_RADIUS_KM,
        candidate_limit=settings.CANDIDATE_LIMIT,
        max_matches=settings.MAX_MATCHES,
    )
