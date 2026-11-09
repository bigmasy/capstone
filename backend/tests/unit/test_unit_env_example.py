"""The template of the compose variables stays in step with docker-compose.yml."""

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "docker-compose.yml"
TEMPLATE = ROOT / ".env.example"

pytestmark = pytest.mark.skipif(
    not (COMPOSE.is_file() and TEMPLATE.is_file()), reason="needs the repository root"
)


def _assignments() -> dict[str, str]:
    values = {}
    for line in TEMPLATE.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([A-Z][A-Z0-9_]*)=(.*)", line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def test_every_variable_that_compose_requires_is_listed_and_left_empty():
    required = set(re.findall(r"\$\{([A-Z_]+):\?", COMPOSE.read_text(encoding="utf-8")))
    listed = _assignments()

    assert required
    assert required <= listed.keys()
    assert {listed[name] for name in required} == {""}
    # The demo password is required only with the demo profile, but it is part of the template
    assert {"SEED_PASSWORD", "SEED_COUNT"} <= listed.keys()


def test_the_template_holds_no_value_at_all():
    assert set(_assignments().values()) == {""}


def test_the_template_is_tracked_and_the_real_file_is_ignored():
    def ignored(name: str) -> bool:
        result = subprocess.run(  # noqa: S603
            ["git", "check-ignore", "--quiet", name],  # noqa: S607
            cwd=ROOT,
            check=False,
        )
        return result.returncode == 0

    if subprocess.run(["git", "rev-parse"], cwd=ROOT, check=False).returncode != 0:  # noqa: S607
        pytest.skip("not a git checkout")

    assert ignored(".env")
    assert not ignored(".env.example")
