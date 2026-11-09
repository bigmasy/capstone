"""Tests of the weights and the share tables of the weighted scorer."""

import dataclasses
from fractions import Fraction

import pytest

from app.domain.functional import FunctionalLevel
from app.domain.matching.weights import (
    DEFAULT_TABLES,
    DEFAULT_WEIGHTS,
    ScoringTables,
    Weights,
)
from app.domain.privacy import DistanceBand


def test_default_weights_are_30_30_25_15():
    # Golden: initial weights of the reference implementation, not calibrated
    assert (
        DEFAULT_WEIGHTS.sport,
        DEFAULT_WEIGHTS.distance,
        DEFAULT_WEIGHTS.functional,
        DEFAULT_WEIGHTS.intensity,
    ) == (30, 30, 25, 15)


def test_weights_must_sum_to_one_hundred():
    with pytest.raises(ValueError, match="100"):
        Weights(sport=30, distance=30, functional=25, intensity=10)


def test_weights_must_not_be_negative():
    with pytest.raises(ValueError, match="negative"):
        Weights(sport=-10, distance=60, functional=25, intensity=25)


def test_weights_must_be_integers():
    with pytest.raises(TypeError, match="integer"):
        Weights(sport=30.0, distance=30, functional=25, intensity=15)  # type: ignore[arg-type]


def test_custom_weights_that_sum_to_one_hundred_are_accepted():
    weights = Weights(sport=50, distance=10, functional=20, intensity=20)
    assert weights.sport == 50


def test_weights_are_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        DEFAULT_WEIGHTS.sport = 40  # type: ignore[misc]


def test_default_distance_shares_fall_from_one_to_zero():
    # Golden: author's assumption of the reference implementation
    assert [DEFAULT_TABLES.distance_share[band] for band in DistanceBand] == [
        Fraction(1),
        Fraction(2, 3),
        Fraction(1, 3),
        Fraction(0),
    ]


def test_default_functional_shares_are_zero_half_one():
    assert DEFAULT_TABLES.functional_share == {
        FunctionalLevel.LOW: Fraction(0),
        FunctionalLevel.MEDIUM: Fraction(1, 2),
        FunctionalLevel.HIGH: Fraction(1),
    }


def test_tables_must_cover_every_band_and_level():
    with pytest.raises(ValueError, match="distance"):
        ScoringTables(
            distance_share={DistanceBand.UNDER_5_KM: Fraction(1)},
            functional_share=dict(DEFAULT_TABLES.functional_share),
        )
    with pytest.raises(ValueError, match="functional"):
        ScoringTables(
            distance_share=dict(DEFAULT_TABLES.distance_share),
            functional_share={FunctionalLevel.LOW: Fraction(0)},
        )


@pytest.mark.parametrize("bad", [Fraction(-1, 10), Fraction(11, 10)])
def test_shares_must_stay_between_zero_and_one(bad):
    shares = dict(DEFAULT_TABLES.distance_share)
    shares[DistanceBand.FROM_5_TO_10_KM] = bad
    with pytest.raises(ValueError, match="between 0 and 1"):
        ScoringTables(distance_share=shares, functional_share=dict(DEFAULT_TABLES.functional_share))


def test_tables_do_not_alias_the_input_mapping():
    shares = dict(DEFAULT_TABLES.distance_share)
    tables = ScoringTables(
        distance_share=shares, functional_share=dict(DEFAULT_TABLES.functional_share)
    )
    shares[DistanceBand.UNDER_5_KM] = Fraction(0)
    assert tables.distance_share[DistanceBand.UNDER_5_KM] == 1
    with pytest.raises(TypeError):
        tables.distance_share[DistanceBand.UNDER_5_KM] = Fraction(0)  # type: ignore[index]
