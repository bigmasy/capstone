import pytest

from app.privacy import LAT_STEP, LON_STEP, distance_band, distance_km, fuzz_location


def test_fuzz_returns_cell_center_not_input():
    lat, lon = 50.4501, 30.5234
    flat, flon = fuzz_location(lat, lon)
    assert (flat, flon) != (lat, lon)
    assert abs(flat - lat) <= LAT_STEP / 2
    assert abs(flon - lon) <= LON_STEP / 2


def test_fuzz_is_deterministic_and_groups_nearby_points():
    a = fuzz_location(50.4501, 30.5234)
    b = fuzz_location(50.4501, 30.5234)
    c = fuzz_location(50.4510, 30.5240)
    assert a == b == c


def test_fuzz_separates_distant_points():
    assert fuzz_location(50.45, 30.52) != fuzz_location(50.45, 30.70)


@pytest.mark.parametrize("latitude", [44.0, 50.0, 53.0])
def test_cell_size_is_a_few_kilometers(latitude):
    lat, lon = fuzz_location(latitude, 30.0)
    step_lat = distance_km(lat, lon, lat + LAT_STEP, lon)
    step_lon = distance_km(lat, lon, lat, lon + LON_STEP)
    assert 3 <= step_lat <= 5
    assert 3 <= step_lon <= 5


@pytest.mark.parametrize("latitude", [90.0, -90.0])
@pytest.mark.parametrize("longitude", [180.0, -180.0])
def test_fuzz_stays_within_valid_range_on_boundaries(latitude, longitude):
    lat, lon = fuzz_location(latitude, longitude)
    assert -90 <= lat <= 90
    assert -180 <= lon <= 180


@pytest.mark.parametrize("latitude", [90.0, -90.0])
@pytest.mark.parametrize("longitude", [180.0, -180.0])
def test_fuzz_location_at_bounds_returns_cell_center_inside_range(latitude, longitude):
    lat, lon = fuzz_location(latitude, longitude)
    assert (lat, lon) != (latitude, longitude)
    assert -90 < lat < 90
    assert -180 < lon < 180
    assert abs(lat - latitude) <= LAT_STEP / 2 + 1e-9
    assert abs(lon - longitude) <= LON_STEP / 2 + 1e-9


def test_distance_band_hides_exact_value():
    assert distance_band(1.2) == "under 5 km"
    assert distance_band(7.0) == "5–10 km"
    assert distance_band(12.0) == "10–25 km"
    assert distance_band(40.0) == "over 25 km"
