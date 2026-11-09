"""Guard against silently skipping the ranking and experiment tests in CI.

Those test modules call ``pytest.importorskip("lightgbm")``, so a missing library turns the
whole ranking suite into skips and the run stays green. In CI (``CI=true``) the library is
required, and this test fails when it cannot be imported.
"""

import importlib
import os

import pytest


def test_lightgbm_and_numpy_are_importable_in_ci():
    if os.environ.get("CI", "").lower() != "true":
        pytest.skip("only enforced when CI=true; a local run may omit the ML requirements")

    for name in ("lightgbm", "numpy", "scipy"):
        importlib.import_module(name)
