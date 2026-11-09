"""Location privacy: coordinates are coarsened to a grid cell, distances are shown as bands.

Only the centre of a grid cell is ever stored or compared, never the exact position.
"""

import math
from dataclasses import dataclass
from enum import StrEnum

# Grid step: 0.04 degrees of latitude is about 4.4 km; 0.06 degrees of longitude at 50 N is
# about 4.3 km
LAT_STEP = 0.04
LON_STEP = 0.06

_MAX_LATITUDE = 90.0
_MAX_LONGITUDE = 180.0
EARTH_RADIUS_KM = 6371.0

# Upper limits of the distance bands; the last band has no upper limit
BAND_LIMITS_KM = (5.0, 10.0, 25.0)


@dataclass(frozen=True, slots=True)
class GridCell:
    """Centre of a grid cell, in degrees; the only form of location the domain keeps.

    :param latitude: Latitude of the cell centre, from -90 to 90.
    :param longitude: Longitude of the cell centre, from -180 to 180.
    :raises ValueError: If a value is not finite or lies outside its range.
    """

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        """Reject values that are not a point on the globe, without echoing them."""
        if not (math.isfinite(self.latitude) and math.isfinite(self.longitude)):
            raise ValueError("coordinates must be finite numbers")
        if abs(self.latitude) > _MAX_LATITUDE or abs(self.longitude) > _MAX_LONGITUDE:
            raise ValueError("coordinates are outside the valid range")


class DistanceBand(StrEnum):
    """Distance shown to the caller instead of the exact value.

    The value is the display label of the reference implementation, kept so the wire format
    does not change.
    """

    UNDER_5_KM = "under 5 km"
    FROM_5_TO_10_KM = "5–10 km"
    FROM_10_TO_25_KM = "10–25 km"
    OVER_25_KM = "over 25 km"

    @property
    def rank(self) -> int:
        """Position of the band from the nearest (0) to the farthest (3)."""
        return _BAND_ORDER.index(self)


_BAND_ORDER = (
    DistanceBand.UNDER_5_KM,
    DistanceBand.FROM_5_TO_10_KM,
    DistanceBand.FROM_10_TO_25_KM,
    DistanceBand.OVER_25_KM,
)


def _cell_center(value: float, step: float, limit: float) -> float:
    """Return the centre of the cell of a value in the range from -limit to limit.

    The cell index is clamped to the outermost cells of the range so that the centre always
    stays inside it.
    """
    cells = round(limit / step)
    index = max(-cells, min(cells - 1, math.floor(value / step)))
    return (index + 0.5) * step


def coarsen(latitude: float, longitude: float) -> GridCell:
    """Return the centre of the grid cell that contains the point.

    The grid is deterministic: the same point always yields the same cell, so repeated
    requests do not narrow down the position within the cell. A point on the upper bound of
    the range (latitude 90, longitude 180) belongs to the nearest cell inside the range, so
    the result always lies strictly inside it. Values outside the range are clamped to the
    outermost cells.

    :param latitude: Exact latitude in degrees.
    :param longitude: Exact longitude in degrees.
    :raises ValueError: If a value is not finite.
    :return: The cell centre, rounded to 6 decimals.
    """
    if not (math.isfinite(latitude) and math.isfinite(longitude)):
        raise ValueError("coordinates must be finite numbers")
    lat = _cell_center(latitude, LAT_STEP, _MAX_LATITUDE)
    lon = _cell_center(longitude, LON_STEP, _MAX_LONGITUDE)
    return GridCell(latitude=round(lat, 6), longitude=round(lon, 6))


def haversine_km(a: GridCell, b: GridCell) -> float:
    """Return the great-circle distance between two cell centres in kilometres.

    The result is exactly symmetric: swapping the arguments flips the sign of the angle
    differences, and every term of the formula is even in them.

    :param a: First cell.
    :param b: Second cell.
    :return: Distance in kilometres, not less than 0.
    """
    p1, p2 = math.radians(a.latitude), math.radians(b.latitude)
    dphi = p2 - p1
    dlmb = math.radians(b.longitude - a.longitude)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    # Rounding can push h a hair above 1 for antipodal points
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, h)))


def band_for(distance_km: float) -> DistanceBand:
    """Return the band of a distance, the only form in which a distance leaves the domain.

    A distance equal to a limit belongs to the farther band (5.0 km is "5-10 km"). The
    comparison is exact, with no tolerance: distances are computed between cell centres, so
    an exact hit on 5, 10 or 25 km is practically unreachable, and a tolerance would make
    the band depend on a tuning constant instead of on the value. The result is stable
    because the haversine distance is symmetric bit for bit.

    :param distance_km: Distance in kilometres.
    :raises ValueError: If the distance is negative or not a number.
    :return: The band that contains the distance.
    """
    if math.isnan(distance_km) or distance_km < 0:
        raise ValueError("distance must be a non-negative number")
    return _BAND_ORDER[sum(distance_km >= limit for limit in BAND_LIMITS_KM)]
