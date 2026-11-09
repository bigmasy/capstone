"""Tests of location coarsening, haversine distance and distance bands."""

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.privacy import (
    BAND_LIMITS_KM,
    LAT_STEP,
    LON_STEP,
    DistanceBand,
    GridCell,
    band_for,
    coarsen,
    haversine_km,
)

latitudes = st.floats(min_value=-90, max_value=90, allow_nan=False)
longitudes = st.floats(min_value=-180, max_value=180, allow_nan=False)


def test_coarsen_returns_cell_center_not_input():
    # Arrange
    lat, lon = 50.4501, 30.5234

    # Act
    cell = coarsen(lat, lon)

    # Assert
    assert (cell.latitude, cell.longitude) != (lat, lon)
    assert abs(cell.latitude - lat) <= LAT_STEP / 2
    assert abs(cell.longitude - lon) <= LON_STEP / 2


def test_coarsen_is_deterministic_and_groups_nearby_points():
    a = coarsen(50.4501, 30.5234)
    b = coarsen(50.4501, 30.5234)
    c = coarsen(50.4510, 30.5240)
    assert a == b == c


def test_coarsen_separates_distant_points():
    assert coarsen(50.45, 30.52) != coarsen(50.45, 30.70)


def test_coarsen_golden_cell_of_central_kyiv():
    # Golden: the grid is part of the privacy contract; changing it moves every stored cell
    assert coarsen(50.4501, 30.5234) == GridCell(latitude=50.46, longitude=30.51)


@pytest.mark.parametrize("latitude", [44.0, 50.0, 53.0])
def test_cell_size_is_a_few_kilometers(latitude):
    cell = coarsen(latitude, 30.0)
    north = GridCell(cell.latitude + LAT_STEP, cell.longitude)
    east = GridCell(cell.latitude, cell.longitude + LON_STEP)
    assert 3 <= haversine_km(cell, north) <= 5
    assert 3 <= haversine_km(cell, east) <= 5


@pytest.mark.parametrize("latitude", [90.0, -90.0])
@pytest.mark.parametrize("longitude", [180.0, -180.0])
def test_coarsen_at_bounds_returns_cell_center_inside_range(latitude, longitude):
    cell = coarsen(latitude, longitude)
    assert (cell.latitude, cell.longitude) != (latitude, longitude)
    assert -90 < cell.latitude < 90
    assert -180 < cell.longitude < 180
    assert abs(cell.latitude - latitude) <= LAT_STEP / 2 + 1e-9
    assert abs(cell.longitude - longitude) <= LON_STEP / 2 + 1e-9


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_coarsen_rejects_non_finite_values_without_echoing_them(bad):
    with pytest.raises(ValueError, match="finite") as info:
        coarsen(bad, 30.0)
    assert "nan" not in str(info.value).lower().replace("finite", "")


@pytest.mark.parametrize("bad", [math.nan, math.inf])
def test_grid_cell_rejects_non_finite_or_out_of_range_values(bad):
    with pytest.raises(ValueError):
        GridCell(bad, 0.0)
    with pytest.raises(ValueError):
        GridCell(0.0, bad)
    with pytest.raises(ValueError):
        GridCell(90.5, 0.0)
    with pytest.raises(ValueError):
        GridCell(0.0, -180.5)


@given(latitudes, longitudes)
def test_coarsen_is_idempotent(latitude, longitude):
    # Arrange
    cell = coarsen(latitude, longitude)

    # Act
    again = coarsen(cell.latitude, cell.longitude)

    # Assert
    assert again == cell


@given(latitudes, longitudes)
def test_coarsen_always_returns_a_cell_centre_inside_the_range(latitude, longitude):
    # Arrange / Act
    cell = coarsen(latitude, longitude)

    # Assert: the offset from the cell origin is half a step, and the point stays in range
    assert math.isclose(cell.latitude / LAT_STEP % 1, 0.5, abs_tol=1e-4)
    assert math.isclose(cell.longitude / LON_STEP % 1, 0.5, abs_tol=1e-4)
    assert -90 < cell.latitude < 90
    assert -180 < cell.longitude < 180


@given(latitudes, longitudes)
def test_coarsen_moves_a_point_by_at_most_half_a_cell(latitude, longitude):
    cell = coarsen(latitude, longitude)
    assert abs(cell.latitude - latitude) <= LAT_STEP / 2 + 1e-9
    assert abs(cell.longitude - longitude) <= LON_STEP / 2 + 1e-9


def test_haversine_of_a_point_with_itself_is_zero():
    cell = GridCell(50.45, 30.52)
    assert haversine_km(cell, cell) == 0


def test_haversine_one_degree_of_latitude_is_about_111_km():
    km = haversine_km(GridCell(50.0, 30.0), GridCell(51.0, 30.0))
    assert km == pytest.approx(111.19, abs=0.05)


@given(latitudes, longitudes, latitudes, longitudes)
def test_haversine_is_symmetric_and_non_negative(lat1, lon1, lat2, lon2):
    a, b = GridCell(lat1, lon1), GridCell(lat2, lon2)
    assert haversine_km(a, b) == haversine_km(b, a)
    assert haversine_km(a, b) >= 0


def test_band_limits_are_five_ten_and_twenty_five_km():
    assert BAND_LIMITS_KM == (5.0, 10.0, 25.0)


@pytest.mark.parametrize(
    "km,band",
    [
        (0.0, DistanceBand.UNDER_5_KM),
        (1.2, DistanceBand.UNDER_5_KM),
        (4.999999, DistanceBand.UNDER_5_KM),
        (5.0, DistanceBand.FROM_5_TO_10_KM),
        (7.0, DistanceBand.FROM_5_TO_10_KM),
        (9.999999, DistanceBand.FROM_5_TO_10_KM),
        (10.0, DistanceBand.FROM_10_TO_25_KM),
        (12.0, DistanceBand.FROM_10_TO_25_KM),
        (24.999999, DistanceBand.FROM_10_TO_25_KM),
        (25.0, DistanceBand.OVER_25_KM),
        (40.0, DistanceBand.OVER_25_KM),
        (20000.0, DistanceBand.OVER_25_KM),
    ],
)
def test_band_for_boundaries_belong_to_the_farther_band(km, band):
    assert band_for(km) is band


@pytest.mark.parametrize("limit", BAND_LIMITS_KM)
def test_band_boundary_float_noise_is_not_smoothed(limit):
    # The comparison is exact (>=). The values just below and above the limit, one float step
    # apart, land in different bands, which keeps the function a pure threshold.
    below = math.nextafter(limit, 0.0)
    above = math.nextafter(limit, math.inf)
    assert band_for(below).rank + 1 == band_for(limit).rank == band_for(above).rank


def test_band_labels_keep_the_wire_format_of_the_reference_implementation():
    assert [band.value for band in DistanceBand] == [
        "under 5 km",
        "5–10 km",
        "10–25 km",
        "over 25 km",
    ]


def test_band_rank_runs_from_zero_to_three():
    assert [band.rank for band in DistanceBand] == [0, 1, 2, 3]


@pytest.mark.parametrize("bad", [-0.1, math.nan])
def test_band_for_rejects_negative_and_nan_distances(bad):
    with pytest.raises(ValueError):
        band_for(bad)


@given(
    st.floats(min_value=0, max_value=30000, allow_nan=False),
    st.floats(min_value=0, max_value=30000, allow_nan=False),
)
def test_band_is_monotone_in_distance(x, y):
    low, high = sorted((x, y))
    assert band_for(low).rank <= band_for(high).rank
