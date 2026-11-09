"""Small synthetic learning-to-rank data for the ranking tests."""

import numpy as np

from app.domain.matching.features import FEATURE_NAMES
from app.ranking.features import QueryData

_COLUMN = {name: i for i, name in enumerate(FEATURE_NAMES)}


def make_queries(seed: int, n_queries: int, rows: int = 12) -> list[QueryData]:
    """Queries whose labels depend on sport overlap, distance band and functional level."""
    rng = np.random.default_rng(seed)
    queries = []
    for _ in range(n_queries):
        x = np.zeros((rows, len(FEATURE_NAMES)))
        x[:, _COLUMN["n_shared_sports"]] = rng.integers(1, 4, rows)
        x[:, _COLUMN["sport_jaccard"]] = rng.random(rows)
        x[:, _COLUMN["min_skill_gap_shared"]] = rng.integers(0, 3, rows)
        x[:, _COLUMN["viewer_n_sports"]] = 2
        x[:, _COLUMN["cand_n_sports"]] = rng.integers(1, 4, rows)
        x[:, _COLUMN["distance_band"]] = rng.integers(0, 4, rows)
        x[:, _COLUMN["viewer_intensity"]] = 3
        x[:, _COLUMN["cand_intensity"]] = rng.integers(1, 6, rows)
        x[:, _COLUMN["intensity_diff_signed"]] = x[:, _COLUMN["cand_intensity"]] - 3
        x[:, _COLUMN["intensity_diff_abs"]] = np.abs(x[:, _COLUMN["intensity_diff_signed"]])
        x[:, _COLUMN["functional_level"]] = rng.integers(0, 3, rows)
        logit = (
            2.0 * x[:, _COLUMN["sport_jaccard"]]
            - 0.9 * x[:, _COLUMN["distance_band"]]
            + 0.8 * x[:, _COLUMN["functional_level"]]
            - 0.1
        )
        y = (rng.random(rows) < 1 / (1 + np.exp(-logit))).astype(float)
        queries.append(QueryData(x, y, propensity=rng.uniform(0.05, 1.0, rows)))
    return queries
