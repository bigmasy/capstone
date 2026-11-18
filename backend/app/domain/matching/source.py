"""The candidate source port and the result types of a feed."""

from collections.abc import Awaitable, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.domain.matching.scorer import RankSource, Scored
from app.domain.profile import ProfileView


@dataclass(frozen=True, slots=True)
class CandidateProfile:
    """A stored profile found near a viewer: the matching snapshot plus its public name.

    The snapshot has no display name because scoring does not need one; the name travels beside
    it so that the feed can show it without a second query.

    :param view: Snapshot of the profile. Its functional layer is filled only if the owner gave
        consent.
    :param display_name: Name the owner chose to show to other people.
    :param has_photo: Whether the owner uploaded a photograph.
    """

    view: ProfileView
    display_name: str
    has_photo: bool = False


class CandidateSource(Protocol):
    """Port of candidate retrieval: the stage before scoring.

    An implementation returns only visible profiles other than the viewer's that practise at
    least one of the viewer's sports and lie within the radius, nearest first and then by
    profile id, at most ``limit`` of them. The distance is measured between grid cell centres.
    Implementations may be backed by PostGIS or by plain code; both must give the same set.
    The method returns an awaitable so that the domain stays free of ``async`` syntax.
    """

    def search_candidates(
        self, viewer: ProfileView, radius_km: float, limit: int
    ) -> Awaitable[list[CandidateProfile]]:
        """Find the profiles that may be offered to the viewer.

        :param viewer: The viewer; their own profile is never returned.
        :param radius_km: Search radius around the viewer's cell centre, in kilometres.
        :param limit: Maximum number of profiles to return.
        :return: Candidate profiles, nearest first, ties broken by profile id.
        """
        ...


@dataclass(frozen=True, slots=True)
class MatchEntry:
    """One entry of a feed: the scored candidate and the name to show.

    :param display_name: Public name of the candidate.
    :param scored: The candidate with its score, breakdown and rank influence.
    :param has_photo: Whether the candidate uploaded a photograph.
    """

    display_name: str
    scored: Scored
    has_photo: bool = False


@dataclass(frozen=True, slots=True)
class MatchPage:
    """One page of a viewer's feed.

    :param entries: The entries of the page, best first.
    :param skip: Number of entries skipped before the page.
    :param limit: Maximum size of the page that was requested.
    :param total: Number of entries in the whole ranked feed, before paging.
    :param rank_source: Strategy that ordered the feed.
    """

    entries: Sequence[MatchEntry]
    skip: int
    limit: int
    total: int
    rank_source: RankSource
