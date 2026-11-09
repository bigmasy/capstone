"""Coarse features of a viewer-candidate pair for the learned ranker.

The set is deliberately small and coarse. Every feature is either public (sports, skill,
intensity) or already shown to the caller (distance band, functional level). No coordinate,
identifier, name, district or private capability value enters it, so a model trained on
these features cannot leak what the API does not already reveal.
"""

from dataclasses import dataclass, fields
from fractions import Fraction

from app.domain.functional import functional_level
from app.domain.matching.scorer import Candidate
from app.domain.profile import ProfileView

# Bump when a feature is added, removed, reordered or redefined; a model artifact records
# the version it was trained on
FEATURE_SCHEMA_VERSION = 1

FEATURE_NAMES = (
    "n_shared_sports",
    "sport_jaccard",
    "min_skill_gap_shared",
    "viewer_n_sports",
    "cand_n_sports",
    "distance_band",
    "viewer_intensity",
    "cand_intensity",
    "intensity_diff_signed",
    "intensity_diff_abs",
    "functional_level",
)


@dataclass(frozen=True, slots=True)
class PairFeatures:
    """Features of one viewer-candidate pair, in the order of FEATURE_NAMES.

    :param n_shared_sports: Number of sports both practise.
    :param sport_jaccard: Shared sports over all sports of the two, 0 to 1.
    :param min_skill_gap_shared: Smallest skill gap (0 to 2) over shared sports; 0 if none.
    :param viewer_n_sports: Number of sports of the viewer.
    :param cand_n_sports: Number of sports of the candidate.
    :param distance_band: Distance band from 0 (nearest) to 3.
    :param viewer_intensity: Intensity of the viewer, 1 to 5.
    :param cand_intensity: Intensity of the candidate, 1 to 5.
    :param intensity_diff_signed: Candidate intensity minus viewer intensity.
    :param intensity_diff_abs: Absolute intensity difference.
    :param functional_level: Coarse functional level: 0 low, 1 medium, 2 high.
    """

    n_shared_sports: int
    sport_jaccard: float
    min_skill_gap_shared: int
    viewer_n_sports: int
    cand_n_sports: int
    distance_band: int
    viewer_intensity: int
    cand_intensity: int
    intensity_diff_signed: int
    intensity_diff_abs: int
    functional_level: int

    def as_vector(self) -> tuple[float, ...]:
        """Return the values as numbers in the order of FEATURE_NAMES.

        :return: One float per feature.
        """
        return tuple(float(getattr(self, f.name)) for f in fields(self))


def pair_features(viewer: ProfileView, candidate: Candidate) -> PairFeatures:
    """Compute the coarse features of a pair.

    :param viewer: The viewer.
    :param candidate: The candidate with its distance from the viewer.
    :return: The features of the pair.
    """
    other = candidate.profile
    mine, theirs = viewer.sport_codes, other.sport_codes
    shared = mine & theirs
    my_skill = {entry.sport: entry.skill.rank for entry in viewer.sports}
    their_skill = {entry.sport: entry.skill.rank for entry in other.sports}
    gaps = [abs(my_skill[sport] - their_skill[sport]) for sport in shared]
    union = len(mine | theirs)
    jaccard = float(Fraction(len(shared), union)) if union else 0.0
    signed = other.intensity - viewer.intensity
    return PairFeatures(
        n_shared_sports=len(shared),
        sport_jaccard=jaccard,
        min_skill_gap_shared=min(gaps, default=0),
        viewer_n_sports=len(mine),
        cand_n_sports=len(theirs),
        distance_band=candidate.distance_band.rank,
        viewer_intensity=viewer.intensity,
        cand_intensity=other.intensity,
        intensity_diff_signed=signed,
        intensity_diff_abs=abs(signed),
        functional_level=functional_level(viewer.functional, other.functional).rank,
    )
