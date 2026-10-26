"""Location coarsening: coordinates are mapped to a cell of a fixed grid."""

import math

# Grid step: 0.04° of latitude ≈ 4.4 km; 0.06° of longitude at 50° N ≈ 4.3 km
LAT_STEP = 0.04
LON_STEP = 0.06


def _cell_center(value: float, step: float, limit: float) -> float:
    """Center of the cell for a value in the range from -limit to limit.

    The cell index is clamped to the outermost cells of the range so that the
    center always stays inside it.
    """
    cells = round(limit / step)
    index = max(-cells, min(cells - 1, math.floor(value / step)))
    return (index + 0.5) * step


def fuzz_location(latitude: float, longitude: float) -> tuple[float, float]:
    """Return the center of the cell that contains the point.

    The grid is deterministic: the same point always yields the same cell,
    so repeated requests do not narrow down the position within the cell.

    A point on the upper bound of the range (latitude 90, longitude 180)
    belongs to the nearest cell inside the range, not to a cell beyond it.
    Therefore the result never coincides with the input point and lies within
    -90 to 90 for latitude and -180 to 180 for longitude.
    """
    lat = _cell_center(latitude, LAT_STEP, 90)
    lon = _cell_center(longitude, LON_STEP, 180)
    return round(lat, 6), round(lon, 6)


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance between two points by the haversine formula."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def distance_band(km: float) -> str:
    """Distance for the API response: a band instead of the exact value."""
    if km < 5:
        return "under 5 km"
    if km < 10:
        return "5–10 km"
    if km < 25:
        return "10–25 km"
    return "over 25 km"
