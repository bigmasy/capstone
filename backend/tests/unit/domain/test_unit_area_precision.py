"""The nested grids behind the owner's choice of area precision."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.privacy import (
    DEFAULT_PRECISION,
    GRID_STEPS,
    LAT_STEP,
    LON_STEP,
    AreaPrecision,
    coarsen,
)

LATITUDES = st.floats(min_value=-89.9, max_value=89.9, allow_nan=False)
LONGITUDES = st.floats(min_value=-179.9, max_value=179.9, allow_nan=False)
ORDER = [AreaPrecision.KM_1, AreaPrecision.KM_2, AreaPrecision.KM_4, AreaPrecision.PLACE]


def test_the_default_grid_is_the_one_stored_before_the_choice_existed():
    assert DEFAULT_PRECISION is AreaPrecision.KM_4
    assert GRID_STEPS[DEFAULT_PRECISION] == (LAT_STEP, LON_STEP)
    assert coarsen(50.4501, 30.5234) == coarsen(50.4501, 30.5234, AreaPrecision.KM_4)


def test_every_grid_is_twice_as_coarse_as_the_previous_one():
    for finer, coarser in zip(ORDER, ORDER[1:], strict=False):
        assert coarser.is_coarser_than(finer) and not finer.is_coarser_than(coarser)
        assert GRID_STEPS[coarser][0] == pytest.approx(2 * GRID_STEPS[finer][0])
        assert GRID_STEPS[coarser][1] == pytest.approx(2 * GRID_STEPS[finer][1])
    assert not AreaPrecision.KM_2.is_coarser_than(AreaPrecision.KM_2)


@pytest.mark.parametrize("precision", ORDER)
@given(latitude=LATITUDES, longitude=LONGITUDES)
def test_the_centre_is_never_farther_than_half_a_step(
    precision: AreaPrecision, latitude: float, longitude: float
):
    lat_step, lon_step = GRID_STEPS[precision]

    cell = coarsen(latitude, longitude, precision)

    assert abs(cell.latitude - latitude) <= lat_step / 2 + 1e-9
    assert abs(cell.longitude - longitude) <= lon_step / 2 + 1e-9


@given(latitude=LATITUDES, longitude=LONGITUDES)
def test_coarsening_a_stored_cell_gives_the_coarse_cell_of_the_point(
    latitude: float, longitude: float
):
    for index, finer in enumerate(ORDER):
        stored = coarsen(latitude, longitude, finer)
        for coarser in ORDER[index + 1 :]:
            assert coarsen(stored.latitude, stored.longitude, coarser) == coarsen(
                latitude, longitude, coarser
            )


@given(latitude=LATITUDES, longitude=LONGITUDES)
def test_coarsening_is_idempotent_on_every_grid(latitude: float, longitude: float):
    for precision in ORDER:
        cell = coarsen(latitude, longitude, precision)
        assert coarsen(cell.latitude, cell.longitude, precision) == cell
