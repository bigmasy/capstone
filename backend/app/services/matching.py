"""The matching feed: retrieve candidates, score them, order them and cut a page."""

import asyncio
import logging
from collections.abc import Sequence
from uuid import UUID

from app.domain.errors import NotFoundError
from app.domain.matching.feed import eligible_candidates, rank, shield_functional
from app.domain.matching.scorer import Candidate, Scored, Scorer
from app.domain.matching.source import CandidateSource, MatchEntry, MatchPage
from app.domain.profile import ProfileView
from app.domain.taxonomy import SportCode
from app.repository.profiles import ProfileRepository

logger = logging.getLogger(__name__)

_NOT_FOUND = "Profile not found"


class MatchingService:
    """Builds the feed of a viewer.

    The scenario is: load the viewer's snapshot, fetch nearby candidates, apply the
    minimum-shared-categories rule, score, order, and cut a page. Scoring is CPU-bound (a
    learned model runs tree ensembles), so it runs in a worker thread and does not block the
    event loop. If the learned scorer fails at run time the feed is built again with the
    fallback scorer instead of failing the request.

    :param profiles: Repository of profiles, used to load the viewer's snapshot.
    :param candidates: Source of candidate profiles.
    :param scorer: Strategy that scores and orders candidates.
    :param fallback: Scorer to use if ``scorer`` raises, normally the weighted baseline.
    :param default_radius_km: Search radius used when the caller gives none; also its upper bound.
    :param candidate_limit: Maximum number of candidates retrieved and scored per request.
    :param max_matches: Maximum length of the ranked feed; later pages beyond it are empty.
    """

    def __init__(
        self,
        profiles: ProfileRepository,
        candidates: CandidateSource,
        scorer: Scorer,
        *,
        fallback: Scorer | None = None,
        default_radius_km: float = 100.0,
        candidate_limit: int = 200,
        max_matches: int = 100,
    ) -> None:
        """Keep the collaborators and limits."""
        self.profiles = profiles
        self.candidates = candidates
        self.scorer = scorer
        self.fallback = fallback
        self.default_radius_km = default_radius_km
        self.candidate_limit = candidate_limit
        self.max_matches = max_matches

    async def get_matches(
        self,
        user_id: UUID,
        *,
        skip: int = 0,
        limit: int = 20,
        radius_km: float | None = None,
        sport: SportCode | None = None,
    ) -> MatchPage:
        """Return one page of the caller's feed.

        The caller is identified by the account, never by a profile id from the request, so a
        feed can only be built for one's own profile. Hidden profiles, the caller's own profile
        and profiles without a shared sport never appear. Functional data of a candidate is used
        only if its owner consented and the two share enough categories.

        :param user_id: The authenticated caller.
        :param skip: Number of entries to skip.
        :param limit: Maximum number of entries on the page.
        :param radius_km: Search radius; defaults to the configured radius and cannot exceed it.
        :param sport: If given, only candidates who practise this sport.
        :raises NotFoundError: If the caller has not created a profile yet.
        :raises ValueError: If ``skip`` is negative, ``limit`` is negative, or the radius is not
            positive.
        :return: The page with the total length of the ranked feed.
        """
        if skip < 0 or limit < 0:
            raise ValueError("skip and limit must not be negative")
        radius = self.default_radius_km if radius_km is None else radius_km
        if not 0 < radius <= self.default_radius_km:
            raise ValueError("radius is outside the allowed range")
        viewer = await self.profiles.get_profile_view(user_id)
        if viewer is None:
            raise NotFoundError(_NOT_FOUND)

        found = await self.candidates.search_candidates(viewer, radius, self.candidate_limit)
        names = {item.view.id: item.display_name for item in found}
        eligible = eligible_candidates(viewer, [item.view for item in found])
        if sport is not None:
            eligible = [c for c in eligible if sport in c.profile.sport_codes]
        shielded = [shield_functional(viewer, candidate) for candidate in eligible]

        scorer, scored = await self._score(viewer, shielded)
        ranked = rank(scored, self.max_matches, scorer.keeps)
        page = ranked[skip : skip + limit]
        return MatchPage(
            entries=[
                MatchEntry(display_name=names[item.candidate.profile.id], scored=item)
                for item in page
            ],
            skip=skip,
            limit=limit,
            total=len(ranked),
            rank_source=scorer.rank_source,
        )

    async def _score(
        self, viewer: ProfileView, candidates: Sequence[Candidate]
    ) -> tuple[Scorer, list[Scored]]:
        """Score in a worker thread; on failure of the learned scorer use the fallback."""
        try:
            return self.scorer, await asyncio.to_thread(self.scorer.score, viewer, candidates)
        except Exception as error:
            if self.fallback is None:
                raise
            # Only the class name is logged: the message of a model error may quote features
            logger.warning("scorer failed (%s), using the fallback", type(error).__name__)
            return self.fallback, await asyncio.to_thread(self.fallback.score, viewer, candidates)
