"""Structural guarantees of the domain package: imports and access to the private layer."""

import ast
import sys
from pathlib import Path

import pytest

import app.domain

DOMAIN_DIR = Path(app.domain.__file__).resolve().parent
MODULES = sorted(DOMAIN_DIR.rglob("*.py"))
# Only these modules may read the private capability entries
PRIVATE_LAYER_READERS = {"functional.py", "profile.py"}


def imported_modules(path: Path) -> set[str]:
    """Return the top-level and full names of all modules imported by a file."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"relative import in {path.name}"
            assert node.module is not None
            names.add(node.module)
    return names


def test_the_domain_package_has_the_expected_modules():
    found = {path.relative_to(DOMAIN_DIR).as_posix() for path in MODULES}
    assert {
        "errors.py",
        "taxonomy.py",
        "privacy.py",
        "profile.py",
        "functional.py",
        "invitations.py",
        "matching/weights.py",
        "matching/scorer.py",
        "matching/weighted.py",
        "matching/feed.py",
        "matching/features.py",
    } <= found


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.relative_to(DOMAIN_DIR).as_posix())
def test_domain_modules_import_only_the_standard_library_and_the_domain(path):
    # Arrange / Act
    modules = imported_modules(path)

    # Assert
    for module in modules:
        top = module.split(".")[0]
        assert top in sys.stdlib_module_names or module.startswith("app.domain"), (
            path.name,
            module,
        )


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.relative_to(DOMAIN_DIR).as_posix())
def test_domain_modules_are_free_of_async_code(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert not any(isinstance(n, ast.AsyncFunctionDef | ast.Await) for n in ast.walk(tree))


@pytest.mark.parametrize(
    "path",
    [p for p in MODULES if p.name not in PRIVATE_LAYER_READERS],
    ids=lambda p: p.relative_to(DOMAIN_DIR).as_posix(),
)
def test_only_the_functional_module_reads_private_capabilities(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    attributes = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert "capabilities" not in attributes
    assert "equipment" not in attributes
