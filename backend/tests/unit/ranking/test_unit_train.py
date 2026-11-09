from dataclasses import replace

import numpy as np
import pytest

from app.experiment.metrics import mean_ndcg
from app.ranking.features import QueryData
from tests.unit.ranking.data import make_queries

pytest.importorskip("lightgbm")
pytestmark = pytest.mark.ml

from app.ranking.train import (  # noqa: E402
    TrainConfig,
    filter_trainable,
    ipw_weights,
    predict_scores,
    train_ranker,
)

FAST = TrainConfig(
    seed=1, n_estimators=40, num_leaves=7, min_child_samples=5, early_stopping_rounds=10
)


def test_training_is_deterministic_for_one_seed():
    train, valid = make_queries(1, 60), make_queries(2, 20)

    a = train_ranker(train, valid, FAST)
    b = train_ranker(train, valid, FAST)

    assert a.model_text == b.model_text
    assert a.best_iteration == b.best_iteration


def test_another_seed_changes_the_model():
    train, valid = make_queries(1, 60), make_queries(2, 20)

    a = train_ranker(train, valid, FAST)
    other = train_ranker(train, valid, replace(FAST, seed=2))

    assert a.model_text != other.model_text


def test_model_ranks_better_than_chance_on_held_out_queries():
    model = train_ranker(make_queries(1, 80), make_queries(2, 20), FAST)
    test = make_queries(3, 60)

    learned = mean_ndcg([(predict_scores(model.model_text, q.X), q.y) for q in test], 10).mean
    constant = mean_ndcg([(np.zeros(len(q.y)), q.y) for q in test], 10).mean

    assert learned is not None and constant is not None
    assert learned > constant + 0.03


def test_degenerate_queries_are_dropped_from_training_and_validation():
    good = make_queries(1, 30)
    x = np.ones((1, good[0].X.shape[1]))
    single = QueryData(x, np.array([1.0]))
    all_declined = QueryData(np.vstack([x, x]), np.array([0.0, 0.0]))
    all_accepted = QueryData(np.vstack([x, x]), np.array([1.0, 1.0]))

    kept, dropped = filter_trainable([*good, single, all_declined, all_accepted])
    model = train_ranker(
        [*good, single, all_declined, all_accepted], make_queries(2, 10) + [single], FAST
    )

    assert len(kept) == 30 and dropped == 3
    assert model.n_train_queries == 30
    assert model.n_dropped_train_queries == 3
    assert model.n_valid_queries == 10
    assert model.n_dropped_valid_queries == 1
    assert model.n_train_rows == 30 * 12


def test_training_without_any_usable_query_is_an_error():
    x = np.ones((1, 11))

    with pytest.raises(ValueError):
        train_ranker([QueryData(x, np.array([1.0]))], make_queries(2, 5), FAST)


def test_training_works_without_validation_queries():
    model = train_ranker(make_queries(1, 30), [], FAST)

    assert model.n_valid_queries == 0
    assert model.validation_ndcg == {}


def test_early_stopping_uses_ndcg_at_10_and_reports_all_cut_offs():
    model = train_ranker(make_queries(1, 60), make_queries(2, 20), FAST)

    assert set(model.validation_ndcg) == {"ndcg@10", "ndcg@5", "ndcg@20"}
    assert 1 <= model.best_iteration <= FAST.n_estimators


def test_hyperparameters_record_the_deterministic_settings_and_truncation_level():
    config = TrainConfig(seed=7, truncation_level=5)

    params = config.hyperparameters()

    assert params["lambdarank_truncation_level"] == 5
    assert params["deterministic"] is True
    assert params["force_row_wise"] is True
    assert params["n_jobs"] == 1
    assert params["random_state"] == 7
    assert params["objective"] == "lambdarank"
    assert params["eval_at"] == [10, 5, 20]


def test_truncation_level_reaches_the_model_file():
    model = train_ranker(
        make_queries(1, 30), make_queries(2, 10), replace(FAST, truncation_level=4)
    )

    assert "[lambdarank_truncation_level: 4]" in model.model_text


def test_ipw_weights_are_clipped_and_normalised_to_mean_one():
    weights = ipw_weights(np.array([0.5, 0.1, 0.01]), clip=10.0)

    assert weights.mean() == pytest.approx(1.0)
    assert weights[2] == pytest.approx(weights[1])  # both hit the clip
    assert weights[1] / weights[0] == pytest.approx(5.0)


@pytest.mark.parametrize("bad", [[0.0, 0.5], [-0.1, 0.5], [1.5, 0.5], [float("nan"), 0.5]])
def test_ipw_rejects_impossible_propensities(bad):
    with pytest.raises(ValueError):
        ipw_weights(np.array(bad), clip=10.0)


def test_ipw_training_changes_the_model_and_needs_propensities():
    train, valid = make_queries(1, 60), make_queries(2, 20)
    plain = train_ranker(train, valid, FAST)

    weighted = train_ranker(train, valid, replace(FAST, use_ipw=True))

    assert weighted.model_text != plain.model_text
    no_p = [QueryData(q.X, q.y) for q in train]
    with pytest.raises(ValueError):
        train_ranker(no_p, valid, replace(FAST, use_ipw=True))


def test_invalid_config_is_rejected():
    for changes in (
        {"n_estimators": 0},
        {"learning_rate": 0.0},
        {"truncation_level": 0},
        {"ipw_clip": 0.5},
    ):
        with pytest.raises(ValueError):
            TrainConfig(**changes)
