"""Choice of the scorer at start-up: the learned ranker if its artifact is usable, else baseline."""

import logging
from pathlib import Path

from app.domain.errors import DomainError
from app.domain.matching.scorer import Scorer
from app.domain.matching.weighted import WeightedScorer
from app.domain.matching.weights import DEFAULT_WEIGHTS
from app.ranking.lightgbm_scorer import LightGBMScorer

logger = logging.getLogger(__name__)


def build_scorer(settings: object, artifact_dir: Path | str | None) -> Scorer:
    """Return the learned scorer if its artifact loads, otherwise the weighted baseline.

    The fallback is deliberate: a missing or damaged artifact, a schema or taxonomy version
    mismatch, a missing LightGBM installation or a switched-off ranker must not stop the
    service from recommending. The reason is logged as a short code, never as a path or a
    value from the files.

    :param settings: Application settings; only an optional boolean ``RANKER_ENABLED`` is
        read (default True), so the factory does not depend on the configuration package.
    :param artifact_dir: Directory of the model artifact, or None for no learned model.
    :return: ``LightGBMScorer`` or ``WeightedScorer`` with the default weights.
    """
    baseline = WeightedScorer(DEFAULT_WEIGHTS)
    if artifact_dir is None:
        return baseline
    if getattr(settings, "RANKER_ENABLED", True) is False:
        logger.info("ranker disabled by settings, using the weighted baseline")
        return baseline
    try:
        return LightGBMScorer.from_directory(Path(artifact_dir))
    except DomainError:
        logger.warning("model artifact rejected, using the weighted baseline")
    except ImportError:
        logger.warning("lightgbm is not installed, using the weighted baseline")
    return baseline
