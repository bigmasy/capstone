"""Tests of the composition root: the choice of the process-wide scorer."""

import builtins
import sys

import pytest

from app.composition import build_ranker
from app.domain.matching.weighted import WeightedScorer
from tests.conftest import make_settings


def test_without_a_ranker_the_baseline_is_used():
    assert isinstance(build_ranker(make_settings()), WeightedScorer)


def test_a_missing_artifact_leaves_the_baseline_in_charge(tmp_path):
    settings = make_settings(RANKER_ENABLED=True, RANKER_ARTIFACT_DIR=tmp_path / "missing")

    assert isinstance(build_ranker(settings), WeightedScorer)


def test_an_unexpected_error_while_loading_never_stops_the_application(
    monkeypatch: pytest.MonkeyPatch, tmp_path, caplog: pytest.LogCaptureFixture
):
    def explode(*args, **kwargs):
        raise OSError("libomp.dylib not found at /secret/path")

    monkeypatch.setattr("app.ranking.factory.build_scorer", explode)
    settings = make_settings(RANKER_ENABLED=True, RANKER_ARTIFACT_DIR=tmp_path)

    assert isinstance(build_ranker(settings), WeightedScorer)
    assert "OSError" in caplog.text
    assert "/secret/path" not in caplog.text


def test_the_baseline_works_when_the_ranking_dependencies_are_not_installed(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    real_import = builtins.__import__

    def refuse_ranking(name, *args, **kwargs):
        if name.startswith("app.ranking"):
            raise ModuleNotFoundError("No module named 'numpy'")
        return real_import(name, *args, **kwargs)

    for module in [m for m in sys.modules if m.startswith("app.ranking")]:
        monkeypatch.delitem(sys.modules, module)
    monkeypatch.setattr(builtins, "__import__", refuse_ranking)
    settings = make_settings(RANKER_ENABLED=True, RANKER_ARTIFACT_DIR=tmp_path)

    assert isinstance(build_ranker(settings), WeightedScorer)
