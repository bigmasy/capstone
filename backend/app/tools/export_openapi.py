"""Write the OpenAPI document of the application to a file.

Usage, from ``backend/``: ``python -m app.tools.export_openapi [path]``. Without a path the
file ``docs/api/openapi.json`` at the repository root is written. The output is deterministic
(sorted keys, two-space indent, trailing newline) so the committed copy can be compared with a
freshly generated one.
"""

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.conf.config import Settings
from app.main import create_app

# backend/app/tools/export_openapi.py -> repository root
DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "docs" / "api" / "openapi.json"


def build_spec() -> dict[str, Any]:
    """Generate the OpenAPI document from the routes.

    The application is built with fixed test settings and no ``.env``, so the result does not
    depend on the machine; no database connection is opened.

    :return: The OpenAPI document.
    """
    settings = Settings(
        _env_file=None,
        ENV="test",
        DB_URL="sqlite+aiosqlite:///:memory:",
        JWT_SECRET="x" * 32,
    )
    return create_app(settings).openapi()


def render_spec(spec: dict[str, Any]) -> str:
    """Serialise a document in the canonical form.

    :param spec: The OpenAPI document.
    :return: JSON text with sorted keys, two-space indent and a trailing newline.
    """
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """Write the document to the path given on the command line.

    :param argv: Arguments; the first one, if any, is the output path.
    :return: Process exit code.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    target = Path(args[0]) if args else DEFAULT_OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_spec(build_spec()), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
