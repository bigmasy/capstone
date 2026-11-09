"""The matching feed of the signed-in user."""

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, MatchingServiceDep
from app.domain.taxonomy import SportCode
from app.schemas.auth import ErrorResponse
from app.schemas.matches import MatchFeed, SearchRadius

router = APIRouter(prefix="/matches", tags=["matches"])

_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
}

MAX_PAGE_SIZE = 50


@router.get("", response_model=MatchFeed, responses=_RESPONSES)
async def get_matches(
    current: CurrentUser,
    service: MatchingServiceDep,
    skip: Annotated[int, Query(ge=0, le=1000, description="Entries to skip")] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE, description="Page size")] = 20,
    radius_km: Annotated[
        SearchRadius | None,
        Query(description="Narrow the search to one distance band; default is the full radius"),
    ] = None,
    sport: Annotated[
        SportCode | None, Query(description="Only candidates who practise this sport")
    ] = None,
) -> MatchFeed:
    """Return a page of potential training partners for the caller, best first.

    The feed is always built for the caller's own profile. Each entry shows the public profile
    fields, the distance as a band, the points of the baseline formula by criterion and the
    functional criterion as a level only. When a learned ranker orders the feed, ``rank_source``
    says so and ``rank_influence`` tells, per criterion, whether it raised or lowered the
    position; the raw model score is never returned.

    :param current: The authenticated caller.
    :param service: Matching service.
    :param skip: Number of entries to skip.
    :param limit: Page size, at most 50.
    :param radius_km: Optional narrower search radius, one of 5, 10 or 25.
    :param sport: Optional sport filter.
    :raises NotFoundError: If the caller has no profile yet (answered with 404).
    :return: The page with the total length of the feed.
    """
    page = await service.get_matches(
        current.id,
        skip=skip,
        limit=limit,
        radius_km=None if radius_km is None else float(radius_km),
        sport=sport,
    )
    return MatchFeed.from_page(page)
