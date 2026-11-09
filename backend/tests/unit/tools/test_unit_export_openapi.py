import json
from pathlib import Path

from app.tools.export_openapi import build_spec, main, render_spec


def test_rendering_is_deterministic_sorted_and_indented():
    first = render_spec(build_spec())
    second = render_spec(build_spec())

    assert first == second
    assert first.endswith("}\n")
    document = json.loads(first)
    assert list(document) == sorted(document)
    assert first.startswith('{\n  "')


def test_spec_does_not_depend_on_the_environment(monkeypatch):
    monkeypatch.setenv("DB_URL", "sqlite+aiosqlite:///./other.db")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    assert render_spec(build_spec()) == render_spec(build_spec())


def test_main_writes_the_file(tmp_path: Path):
    target = tmp_path / "nested" / "openapi.json"

    assert main([str(target)]) == 0

    assert json.loads(target.read_text())["openapi"].startswith("3.")
