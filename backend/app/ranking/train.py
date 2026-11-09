"""Training of the LightGBM ranker (lambdarank) on invited-only labels.

Used by the offline experiment and by whoever exports an artifact; the API never trains.
LightGBM is imported inside the functions that need it, so importing this module is cheap
and works without the library.

Settings that make a run reproducible on one machine: ``deterministic=True``,
``force_row_wise=True``, ``n_jobs=1`` and ``random_state=seed``. Byte-identical model files
are expected for identical data, configuration and library build, not across platforms.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.ranking.artifact import ArtifactManifest, write_artifact
from app.ranking.features import QueryData, RankingData, stack_queries

# Positions at which LightGBM reports ndcg during training; the first one drives early stopping
DEFAULT_EVAL_AT = (10, 5, 20)
_MIN_ROWS_PER_QUERY = 2


@dataclass(frozen=True)
class TrainConfig:
    """Hyperparameters and options of one training run.

    :param seed: Seed of LightGBM (``random_state``).
    :param n_estimators: Maximum number of trees.
    :param learning_rate: Shrinkage per tree.
    :param num_leaves: Leaves per tree.
    :param min_child_samples: Minimum rows in a leaf.
    :param subsample: Share of rows sampled for every tree.
    :param colsample_bytree: Share of features sampled for every tree.
    :param truncation_level: ``lambdarank_truncation_level``: how many top positions of a list
        take part in the pair gradients; this, not ``eval_at``, shapes the training.
    :param early_stopping_rounds: Rounds without improvement of ndcg@eval_at[0] that stop it.
    :param eval_at: Positions monitored on the validation queries; the first one is used for
        early stopping. Monitoring only; reported metrics are computed by the experiment code.
    :param use_ipw: Weight rows by clipped inverse logging propensity.
    :param ipw_clip: Upper bound of the inverse propensity before normalisation.
    :raises ValueError: If a value is out of range.
    """

    seed: int = 0
    n_estimators: int = 300
    learning_rate: float = 0.05
    num_leaves: int = 15
    min_child_samples: int = 20
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    truncation_level: int = 10
    early_stopping_rounds: int = 30
    eval_at: tuple[int, ...] = DEFAULT_EVAL_AT
    use_ipw: bool = False
    ipw_clip: float = 10.0

    def __post_init__(self) -> None:
        """Validate the configuration."""
        if self.n_estimators < 1 or self.num_leaves < 2 or self.min_child_samples < 1:
            raise ValueError("tree counts and sizes are out of range")
        if not (math.isfinite(self.learning_rate) and self.learning_rate > 0):
            raise ValueError("learning_rate must be positive")
        if not (0 < self.subsample <= 1 and 0 < self.colsample_bytree <= 1):
            raise ValueError("sampling shares must be in (0, 1]")
        if self.truncation_level < 1 or self.early_stopping_rounds < 1:
            raise ValueError("truncation_level and early_stopping_rounds must be at least 1")
        if not self.eval_at or any(k < 1 for k in self.eval_at):
            raise ValueError("eval_at needs positive positions")
        if not (math.isfinite(self.ipw_clip) and self.ipw_clip >= 1):
            raise ValueError("ipw_clip must be at least 1")

    def hyperparameters(self) -> dict[str, Any]:
        """Return the parameters as recorded in the manifest and passed to LightGBM.

        :return: Plain dict of JSON-serialisable values.
        """
        return {
            "objective": "lambdarank",
            "n_estimators": self.n_estimators,
            "learning_rate": self.learning_rate,
            "num_leaves": self.num_leaves,
            "min_child_samples": self.min_child_samples,
            "subsample": self.subsample,
            "subsample_freq": 1,
            "colsample_bytree": self.colsample_bytree,
            "lambdarank_truncation_level": self.truncation_level,
            "early_stopping_rounds": self.early_stopping_rounds,
            "eval_at": list(self.eval_at),
            "use_ipw": self.use_ipw,
            "ipw_clip": self.ipw_clip,
            "deterministic": True,
            "force_row_wise": True,
            "n_jobs": 1,
            "random_state": self.seed,
        }


@dataclass(frozen=True, slots=True)
class TrainedModel:
    """Result of a training run.

    :param model_text: The model in LightGBM text format (trees up to the best iteration).
    :param best_iteration: Number of trees kept.
    :param n_train_rows: Rows used for training.
    :param n_train_queries: Queries used for training.
    :param n_dropped_train_queries: Training queries dropped as degenerate.
    :param n_valid_rows: Rows used for validation.
    :param n_valid_queries: Queries used for validation.
    :param n_dropped_valid_queries: Validation queries dropped as degenerate.
    :param validation_ndcg: LightGBM's own ndcg at the best iteration, keyed like "ndcg@10";
        empty without validation. LightGBM scores a list without positives as 1, so this is
        for monitoring only.
    :param lightgbm_version: Version of the library.
    :param config: The configuration used.
    """

    model_text: str
    best_iteration: int
    n_train_rows: int
    n_train_queries: int
    n_dropped_train_queries: int
    n_valid_rows: int
    n_valid_queries: int
    n_dropped_valid_queries: int
    validation_ndcg: dict[str, float]
    lightgbm_version: str
    config: TrainConfig


def filter_trainable(queries: Sequence[QueryData]) -> tuple[list[QueryData], int]:
    """Drop queries that carry no ranking signal: under two rows, or a single class.

    :param queries: Queries of labelled rows.
    :return: The kept queries and the number of dropped ones.
    """
    kept = [
        q
        for q in queries
        if len(q.y) >= _MIN_ROWS_PER_QUERY and 0.0 < float(np.sum(q.y > 0)) < len(q.y)
    ]
    return kept, len(queries) - len(kept)


def ipw_weights(propensity: NDArray[np.float64], clip: float) -> NDArray[np.float64]:
    """Return clipped inverse-propensity weights normalised to mean 1.

    :param propensity: Logging propensity of every row, in (0, 1].
    :param clip: Upper bound of 1 / propensity before normalising.
    :raises ValueError: If a propensity is not in (0, 1].
    :return: One weight per row.
    """
    if not np.all(np.isfinite(propensity)) or np.any(propensity <= 0) or np.any(propensity > 1):
        raise ValueError("propensities must lie in (0, 1]")
    raw = np.minimum(1.0 / propensity, clip)
    return raw / raw.mean()  # type: ignore[no-any-return]


def _weights(data: RankingData, config: TrainConfig) -> NDArray[np.float64] | None:
    """Sample weights for the run, or None when IPW is off."""
    if not config.use_ipw:
        return None
    if data.propensity is None:
        raise ValueError("IPW needs the logging propensity of every row")
    return ipw_weights(data.propensity, config.ipw_clip)


def train_ranker(
    train: Sequence[QueryData], valid: Sequence[QueryData], config: TrainConfig
) -> TrainedModel:
    """Train a LightGBM lambdarank model on binary labels, one group per viewer.

    Degenerate queries are dropped from both sets. Without usable validation queries the
    model is trained for the full number of trees.

    :param train: Training queries.
    :param valid: Validation queries used for early stopping.
    :param config: Hyperparameters and options.
    :raises ValueError: If no training query is usable or IPW lacks propensities.
    :return: The trained model as text with counts and monitoring values.
    """
    import lightgbm as lgb  # noqa: PLC0415 - loaded lazily so the API starts without it

    kept_train, dropped_train = filter_trainable(train)
    kept_valid, dropped_valid = filter_trainable(valid)
    if not kept_train:
        raise ValueError("no usable training queries")
    data = stack_queries(kept_train)
    # The native API is used on purpose: the sklearn wrapper would add scikit-learn (and its
    # dependencies) to the runtime image for no gain.
    params: dict[str, Any] = {
        "objective": "lambdarank",
        "learning_rate": config.learning_rate,
        "num_leaves": config.num_leaves,
        "min_data_in_leaf": config.min_child_samples,
        "bagging_fraction": config.subsample,
        "bagging_freq": 1,
        "feature_fraction": config.colsample_bytree,
        "lambdarank_truncation_level": config.truncation_level,
        "deterministic": True,
        "force_row_wise": True,
        "num_threads": 1,
        "seed": config.seed,
        "verbosity": -1,
    }
    train_set = lgb.Dataset(
        data.X, label=data.y, group=data.group, weight=_weights(data, config), params=params
    )
    valid_sets: list[Any] = []
    callbacks: list[Any] = []
    if kept_valid:
        valid_data = stack_queries(kept_valid)
        params["eval_at"] = list(config.eval_at)
        valid_sets.append(
            lgb.Dataset(
                valid_data.X,
                label=valid_data.y,
                group=valid_data.group,
                reference=train_set,
                params=params,
            )
        )
        callbacks.append(
            lgb.early_stopping(config.early_stopping_rounds, first_metric_only=True, verbose=False)
        )
    booster = lgb.train(
        params,
        train_set,
        num_boost_round=config.n_estimators,
        valid_sets=valid_sets or None,
        callbacks=callbacks,
    )
    best = (
        booster.best_iteration
        if kept_valid and booster.best_iteration > 0
        else booster.current_iteration()
    )
    scores: dict[str, float] = {}
    if kept_valid:
        for key, value in booster.best_score["valid_0"].items():
            scores[str(key)] = float(value)
    return TrainedModel(
        model_text=booster.model_to_string(num_iteration=best),
        best_iteration=int(best),
        n_train_rows=len(data.y),
        n_train_queries=len(kept_train),
        n_dropped_train_queries=dropped_train,
        n_valid_rows=sum(len(q.y) for q in kept_valid),
        n_valid_queries=len(kept_valid),
        n_dropped_valid_queries=dropped_valid,
        validation_ndcg=scores,
        lightgbm_version=lgb.__version__,
        config=config,
    )


def load_booster(model_text: str) -> Any:
    """Parse a text model once, for repeated scoring.

    :param model_text: Model in LightGBM text format.
    :return: A LightGBM booster.
    """
    import lightgbm as lgb  # noqa: PLC0415

    return lgb.Booster(model_str=model_text)


def booster_scores(booster: Any, X: NDArray[np.float64]) -> NDArray[np.float64]:
    """Return the raw rank scores of a booster for a feature matrix.

    :param booster: Booster from ``load_booster``.
    :param X: Feature matrix.
    :return: One raw score per row (not calibrated).
    """
    if len(X) == 0:
        return np.zeros(0)
    return np.asarray(booster.predict(X, raw_score=True, num_threads=1), dtype=np.float64)


def predict_scores(model_text: str, X: NDArray[np.float64]) -> NDArray[np.float64]:
    """Return the raw rank scores of a text model for a feature matrix.

    :param model_text: Model in LightGBM text format.
    :param X: Feature matrix.
    :return: One raw score per row (not calibrated).
    """
    return booster_scores(load_booster(model_text), X)


def export_artifact(
    model: TrainedModel,
    directory: Path,
    *,
    seeds: dict[str, int],
    n_events: int,
    metrics: dict[str, dict[str, float]],
) -> ArtifactManifest:
    """Write a trained model as an artifact directory.

    :param model: The trained model.
    :param directory: Target directory.
    :param seeds: Seeds of data generation, splits and training.
    :param n_events: Number of logged events (impressions) behind the training rows.
    :param metrics: Validation metrics of the baseline and of the model.
    :return: The manifest that was written.
    """
    return write_artifact(
        directory,
        model.model_text,
        hyperparameters=model.config.hyperparameters(),
        seeds=seeds,
        counts={
            "rows": model.n_train_rows,
            "queries": model.n_train_queries,
            "events": n_events,
        },
        metrics=metrics,
        lightgbm_version=model.lightgbm_version,
    )
