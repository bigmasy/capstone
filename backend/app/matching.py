"""Initial matching: a simple compatibility score from 0 to 100."""

from dataclasses import dataclass

from app.models import Profile
from app.privacy import distance_km

# Initial weights, not calibrated; calibration is done in later iterations.
# The weights sum to 100.
W_SPORT = 40
W_DISTANCE = 40
W_INTENSITY = 20
# Distance at which the proximity contribution drops to zero
MAX_DISTANCE_KM = 30.0


@dataclass(frozen=True)
class Match:
    profile: Profile
    score: float
    distance_km: float


def shared_sports(a: Profile, b: Profile) -> set[str]:
    return {s.sport for s in a.sports} & {s.sport for s in b.sports}


def score_pair(a: Profile, b: Profile) -> tuple[float, float]:
    """Return (score 0–100, distance in km). Without a shared sport the score is 0."""
    km = distance_km(a.area_lat, a.area_lon, b.area_lat, b.area_lon)
    shared = shared_sports(a, b)
    if not shared:
        return 0.0, km
    union = {s.sport for s in a.sports} | {s.sport for s in b.sports}
    sport_part = W_SPORT * len(shared) / len(union)
    distance_part = W_DISTANCE * max(0.0, 1 - km / MAX_DISTANCE_KM)
    intensity_part = W_INTENSITY * (1 - abs(a.intensity - b.intensity) / 4)
    return round(sport_part + distance_part + intensity_part, 1), km


def find_matches(me: Profile, candidates: list[Profile], limit: int) -> list[Match]:
    result = []
    for other in candidates:
        if other.id == me.id or not other.is_visible:
            continue
        score, km = score_pair(me, other)
        if score > 0:
            result.append(Match(other, score, km))
    # Equal scores are ordered by id so that the order is reproducible
    result.sort(key=lambda m: (-m.score, m.profile.id))
    return result[:limit]
