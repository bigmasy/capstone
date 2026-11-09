"""Parameters of the synthetic profile generator."""

import math
from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.taxonomy import (
    MAX_CAPABILITY_LEVEL,
    MAX_INTENSITY,
    MIN_INTENSITY,
    DistrictCode,
    SportCode,
)

# Latent functional patterns the generator knows; "multiple" picks the categories at random
PATTERNS = (
    "undeclared",
    "lower_mobility",
    "upper_mobility",
    "vision",
    "hearing",
    "endurance_balance",
    "multiple",
)

_MAX_LATITUDE = 90.0
_MAX_LONGITUDE = 180.0


def _check_weights(name: str, weights: Iterable[float]) -> None:
    """Raise unless the weights are finite, non-negative and not all zero."""
    values = list(weights)
    if not all(math.isfinite(w) and w >= 0 for w in values):
        raise ValueError(f"{name} must be finite and non-negative")
    if sum(values) <= 0:
        raise ValueError(f"{name} must not be all zero")


def _check_share(name: str, value: float) -> None:
    """Raise unless the value is a number between 0 and 1."""
    if not (math.isfinite(value) and 0 <= value <= 1):
        raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class GeneratorParams:
    """Distribution parameters of the generated population.

    All values are the author's assumptions, not calibrated and not taken from sources.
    They describe a simulated world; results obtained on it say nothing about a real
    community.

    | Parameter | Meaning |
    |---|---|
    | count | number of profiles |
    | anchor | center of the simulated area (central Kyiv); synthetic geometry only |
    | cluster_* | dense areas: weights, offsets (km east, north), Gaussian spread (sigma, km) |
    | cluster_districts | district label of each cluster; not tied to real district borders |
    | scatter_share, scatter_radius_km | sparse periphery: uniform in a disc, no district |
    | district_omitted_share | clustered profiles that leave the optional district empty |
    | sports_count_weights | number of sports per profile |
    | sport_weights, default_sport_weight | popularity of sports, skewed on purpose |
    | intensity_weights | intensity 1..5 |
    | visible_share | share of profiles visible in the feed |
    | pattern_weights | latent functional pattern (generator-internal, never stored) |
    | affected_level_weights | level (0..) of the categories the pattern affects |
    | extra_declared_share, extra_level_weights | other categories declared at a high level |
    | equipment_share | chance of equipment on an affected category |

    Sports, patterns and levels are drawn independently of location and of each other.

    :raises ValueError: If a count, share, weight table or code is invalid.
    """

    count: int = 60
    anchor: tuple[float, float] = (50.45, 30.52)
    cluster_weights: tuple[float, ...] = (0.40, 0.30, 0.20, 0.10)
    cluster_offsets_km: tuple[tuple[float, float], ...] = ((0, 0), (6, 4), (-10, 5), (3, -12))
    cluster_sigma_km: float = 2.5
    cluster_districts: tuple[str, ...] = (
        "kyiv_shevchenkivskyi",
        "kyiv_podilskyi",
        "kyiv_obolonskyi",
        "kyiv_darnytskyi",
    )
    scatter_share: float = 0.10
    scatter_radius_km: float = 60.0
    district_omitted_share: float = 0.15
    sports_count_weights: tuple[tuple[int, float], ...] = ((1, 0.50), (2, 0.35), (3, 0.15))
    sport_weights: tuple[tuple[str, float], ...] = (
        ("swimming", 5),
        ("gym_fitness", 4),
        ("table_tennis", 3),
        ("cycling", 3),
        ("archery", 2),
        ("wheelchair_basketball", 2),
        ("sitting_volleyball", 2),
        ("athletics", 2),
    )
    default_sport_weight: float = 1
    intensity_weights: tuple[float, ...] = (0.10, 0.25, 0.35, 0.20, 0.10)
    visible_share: float = 0.95
    pattern_weights: tuple[tuple[str, float], ...] = (
        ("undeclared", 0.20),
        ("lower_mobility", 0.25),
        ("upper_mobility", 0.15),
        ("vision", 0.08),
        ("hearing", 0.07),
        ("endurance_balance", 0.10),
        ("multiple", 0.15),
    )
    affected_level_weights: tuple[float, ...] = (0.10, 0.30, 0.40, 0.20)
    extra_declared_share: float = 0.5
    extra_level_weights: tuple[tuple[int, float], ...] = ((3, 0.4), (4, 0.6))
    equipment_share: float = 0.6

    def __post_init__(self) -> None:
        """Validate every field; the generator relies on these checks."""
        self._check_size_and_geometry()
        self._check_tables()

    def _check_size_and_geometry(self) -> None:
        """Validate the count, the anchor and the cluster layout."""
        if self.count < 1:
            raise ValueError("count must be at least 1")
        lat, lon = self.anchor
        if not (math.isfinite(lat) and math.isfinite(lon)):
            raise ValueError("anchor must be finite")
        if abs(lat) > _MAX_LATITUDE or abs(lon) > _MAX_LONGITUDE:
            raise ValueError("anchor is outside the valid range")
        clusters = len(self.cluster_weights)
        _check_weights("cluster_weights", self.cluster_weights)
        if not clusters == len(self.cluster_offsets_km) == len(self.cluster_districts):
            raise ValueError("clusters need one weight, offset and district each")
        offsets = [v for pair in self.cluster_offsets_km for v in pair]
        if not all(math.isfinite(v) for v in offsets):
            raise ValueError("cluster_offsets_km must be finite")
        for name in ("cluster_sigma_km", "scatter_radius_km"):
            value = getattr(self, name)
            if not (math.isfinite(value) and value >= 0):
                raise ValueError(f"{name} must be a non-negative number")
        valid_districts = {d.value for d in DistrictCode}
        if not set(self.cluster_districts) <= valid_districts:
            raise ValueError("cluster_districts holds an unknown district code")
        for name in (
            "scatter_share",
            "district_omitted_share",
            "visible_share",
            "extra_declared_share",
            "equipment_share",
        ):
            _check_share(name, getattr(self, name))

    def _check_tables(self) -> None:
        """Validate the sport, intensity, pattern and level tables."""
        _check_weights("sports_count_weights", (w for _, w in self.sports_count_weights))
        if not all(1 <= n <= len(SportCode) for n, _ in self.sports_count_weights):
            raise ValueError("sports_count_weights holds an impossible number of sports")
        valid_sports = {s.value for s in SportCode}
        if not {code for code, _ in self.sport_weights} <= valid_sports:
            raise ValueError("sport_weights holds an unknown sport code")
        _check_weights("sport_weights", (w for _, w in self.sport_weights))
        if not (math.isfinite(self.default_sport_weight) and self.default_sport_weight >= 0):
            raise ValueError("default_sport_weight must be a non-negative number")
        if len(self.intensity_weights) != MAX_INTENSITY - MIN_INTENSITY + 1:
            raise ValueError("intensity_weights needs one weight per intensity")
        _check_weights("intensity_weights", self.intensity_weights)
        if not {name for name, _ in self.pattern_weights} <= set(PATTERNS):
            raise ValueError("pattern_weights holds an unknown pattern")
        _check_weights("pattern_weights", (w for _, w in self.pattern_weights))
        if len(self.affected_level_weights) > MAX_CAPABILITY_LEVEL + 1:
            raise ValueError("affected_level_weights has more entries than levels")
        _check_weights("affected_level_weights", self.affected_level_weights)
        if not all(0 <= level <= MAX_CAPABILITY_LEVEL for level, _ in self.extra_level_weights):
            raise ValueError("extra_level_weights holds a level outside the range")
        _check_weights("extra_level_weights", (w for _, w in self.extra_level_weights))
