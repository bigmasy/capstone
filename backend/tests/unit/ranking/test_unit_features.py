import numpy as np
import pytest

from app.domain.matching.features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION
from app.domain.matching.scorer import Candidate
from app.domain.taxonomy import DistrictCode, SkillLevel, SportCode
from app.ranking.features import QueryData, feature_matrix, stack_queries
from tests.unit.domain.builders import make_profile

# The whitelist of the design: coarse, public or already shown. Changing it is a schema change
EXPECTED_FEATURES = (
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


def test_feature_names_are_exactly_the_whitelist_and_the_version_is_pinned():
    assert FEATURE_NAMES == EXPECTED_FEATURES
    assert FEATURE_SCHEMA_VERSION == 1


def test_no_feature_name_hints_at_a_coordinate_identifier_or_private_value():
    for name in FEATURE_NAMES:
        parts = name.split("_")
        assert not any(token in parts for token in ("lat", "lon", "id", "district", "name"))
        assert "coord" not in name and "capab" not in name


def test_matrix_columns_follow_the_feature_names_and_rows_follow_the_candidates():
    viewer = make_profile(1, sports=[SportCode.SWIMMING, SportCode.CYCLING], intensity=2)
    near = make_profile(2, sports=[SportCode.SWIMMING], intensity=5)
    far = make_profile(3, sports=[SportCode.CYCLING], intensity=1, lon=31.5)

    matrix = feature_matrix(
        viewer, [Candidate.between(viewer, near), Candidate.between(viewer, far)]
    )

    assert matrix.shape == (2, len(FEATURE_NAMES))
    column = {name: i for i, name in enumerate(FEATURE_NAMES)}
    assert matrix[0, column["n_shared_sports"]] == 1
    assert matrix[0, column["cand_intensity"]] == 5
    assert matrix[0, column["intensity_diff_signed"]] == 3
    assert matrix[1, column["distance_band"]] == 3
    assert matrix[1, column["cand_intensity"]] == 1


def test_empty_candidate_list_gives_an_empty_matrix():
    matrix = feature_matrix(make_profile(1), [])

    assert matrix.shape == (0, len(FEATURE_NAMES))


def test_features_ignore_everything_that_is_not_on_the_whitelist():
    viewer = make_profile(1, sports=[(SportCode.SWIMMING, SkillLevel.BEGINNER)], lat=50.45)
    base = make_profile(
        2,
        sports=[(SportCode.SWIMMING, SkillLevel.BEGINNER)],
        lat=50.45,
        caps=[("mobility_lower", 3, "handcycle"), ("vision", 4, None)],
    )
    # Other id, other district, other cell inside the same band, other private values that
    # keep the same coarse functional level
    twin = make_profile(
        99,
        sports=[(SportCode.SWIMMING, SkillLevel.BEGINNER)],
        lat=50.46,
        caps=[("mobility_lower", 3, "handcycle"), ("vision", 4, None)],
        district=DistrictCode.KYIV_PODILSKYI,
    )

    a = feature_matrix(viewer, [Candidate.between(viewer, base)])
    b = feature_matrix(viewer, [Candidate.between(viewer, twin)])

    assert np.array_equal(a, b)


def test_functional_values_reach_the_model_only_as_a_level():
    viewer = make_profile(1, caps=[("mobility_lower", 4, None)])
    levels = {
        feature_matrix(
            viewer,
            [Candidate.between(viewer, make_profile(2, caps=[("mobility_lower", lvl, None)]))],
        )[0, FEATURE_NAMES.index("functional_level")]
        for lvl in range(5)
    }

    assert levels <= {0.0, 1.0, 2.0}


def test_stack_queries_builds_matrix_labels_and_group_sizes():
    q1 = QueryData(np.ones((3, 2)), np.array([1.0, 0.0, 0.0]))
    q2 = QueryData(np.zeros((2, 2)), np.array([0.0, 1.0]))

    data = stack_queries([q1, q2])

    assert data.X.shape == (5, 2)
    assert data.y.tolist() == [1, 0, 0, 0, 1]
    assert data.group.tolist() == [3, 2]
    assert data.propensity is None


def test_stack_queries_keeps_propensities_only_when_all_queries_have_them():
    with_p = QueryData(np.ones((2, 2)), np.array([1.0, 0.0]), np.array([0.5, 0.25]))
    without = QueryData(np.ones((2, 2)), np.array([1.0, 0.0]))

    assert stack_queries([with_p, with_p]).propensity.tolist() == [0.5, 0.25, 0.5, 0.25]
    with pytest.raises(ValueError):
        stack_queries([with_p, without])


def test_query_data_rejects_mismatched_shapes():
    with pytest.raises(ValueError):
        QueryData(np.ones((3, 2)), np.array([1.0, 0.0]))
    with pytest.raises(ValueError):
        QueryData(np.ones((2, 2)), np.array([1.0, 0.0]), np.array([0.5]))
