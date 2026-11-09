import json
import logging

import httpx
import pytest
from fastapi import FastAPI

from app.core.logging import (
    ACCESS_LOGGER_NAME,
    REDACTED,
    AccessLogMiddleware,
    JsonFormatter,
    RedactionFilter,
    configure_logging,
    is_sensitive_key,
    redact,
)
from tests.conftest import make_settings


def make_record(**extra: object) -> logging.LogRecord:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "message", None, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_redact_masks_sensitive_keys_recursively():
    data = {
        "Password": "p",
        "profile": {"latitude": 50.4, "lon": 30.5, "name": "ok"},
        "items": [{"capabilities": ["x"], "token": "t"}],
    }

    result = redact(data)

    assert result["Password"] == REDACTED
    assert result["profile"] == {"latitude": REDACTED, "lon": REDACTED, "name": "ok"}
    assert result["items"] == [{"capabilities": REDACTED, "token": REDACTED}]


@pytest.mark.parametrize(
    "key",
    [
        "password",
        "token",
        "authorization",
        "email",
        "latitude",
        "longitude",
        "lat",
        "lon",
        "capabilities",
        "cookie",
        "contact",
        "secret",
        "jwt_secret",
        "refresh_token",
        "user_email",
        "Set-Cookie",
        "db_url",
        "new_password",
    ],
)
def test_filter_masks_sensitive_extra_fields(key: str):
    record = make_record(**{key: "secret-value"})

    RedactionFilter().filter(record)

    assert getattr(record, key) == REDACTED


def test_filter_masks_nested_extra_and_mapping_args():
    record = make_record(payload={"email": "a@b.c", "x": 1})
    record.args = {"password": "p"}

    RedactionFilter().filter(record)

    assert record.payload == {"email": REDACTED, "x": 1}  # type: ignore[attr-defined]
    assert record.args == {"password": REDACTED}


def test_formatter_emits_one_json_line_with_extras():
    record = make_record(route="/x", status=200)

    line = JsonFormatter().format(record)

    parsed = json.loads(line)
    assert "\n" not in line
    assert parsed["message"] == "message"
    assert parsed["route"] == "/x"
    assert parsed["status"] == 200


def test_formatter_keeps_only_the_exception_class():
    try:
        raise ValueError("user@example.com")
    except ValueError:
        import sys

        record = make_record()
        record.exc_info = sys.exc_info()

    parsed = json.loads(JsonFormatter().format(record))

    assert parsed["exception"] == "ValueError"
    assert "example.com" not in json.dumps(parsed)


def test_configure_logging_is_idempotent():
    root = logging.getLogger()
    before = len(root.handlers)

    configure_logging(make_settings())
    configure_logging(make_settings())

    assert len(root.handlers) <= before + 1


async def test_access_log_has_only_the_allowed_fields(
    app: FastAPI, client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
):
    canary = "canary-user@example.com"
    caplog.set_level(logging.INFO, logger=ACCESS_LOGGER_NAME)

    response = await client.post(
        f"/health?token={canary}",
        json={"password": canary, "latitude": 50.123456},
        headers={"Authorization": f"Bearer {canary}"},
    )

    assert response.status_code == 405
    records = [r for r in caplog.records if r.name == ACCESS_LOGGER_NAME]
    assert len(records) == 1
    formatter = JsonFormatter()
    line = formatter.format(records[0])
    assert canary not in line
    assert "50.123456" not in line
    payload = json.loads(line)
    assert {"method", "route", "status", "duration_ms", "request_id"} <= set(payload)
    assert payload["method"] == "POST"
    assert payload["status"] == 405
    assert payload["request_id"] == response.headers["x-request-id"]


async def test_access_log_uses_the_route_template(
    app: FastAPI, client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
):
    @app.get("/things/{thing_id}", response_model=None)
    async def thing(thing_id: str) -> None:
        return None

    caplog.set_level(logging.INFO, logger=ACCESS_LOGGER_NAME)

    await client.get("/things/personal-id-123")

    record = next(r for r in caplog.records if r.name == ACCESS_LOGGER_NAME)
    assert record.route == "/things/{thing_id}"  # type: ignore[attr-defined]
    assert "personal-id-123" not in JsonFormatter().format(record)


@pytest.mark.parametrize("name", ["aiosqlite", "sqlalchemy.engine", "asyncpg"])
def test_database_drivers_never_log_below_warning(name: str):
    # At DEBUG a driver prints bound parameters: e-mails, contacts, cell coordinates.
    configure_logging(make_settings(LOG_LEVEL="DEBUG"))

    assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING


@pytest.mark.parametrize("key", ["latency_ms", "duration_ms", "route", "status", "request_id"])
def test_harmless_field_names_stay_readable(key: str):
    assert not is_sensitive_key(key)


def test_formatter_redacts_even_without_the_filter():
    record = make_record(email="a@b.c", detail={"token": "t", "n": 1})

    parsed = json.loads(JsonFormatter().format(record))

    assert parsed["email"] == REDACTED
    assert parsed["detail"] == {"token": REDACTED, "n": 1}


def test_server_loggers_go_through_the_root_json_handler():
    server_handler = logging.StreamHandler()
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).addHandler(server_handler)
        logging.getLogger(name).propagate = False
    logging.getLogger("uvicorn.access").addHandler(server_handler)

    configure_logging(make_settings())

    for name in ("uvicorn", "uvicorn.error", "uvicorn.asgi"):
        server_logger = logging.getLogger(name)
        assert server_logger.handlers == []
        assert server_logger.propagate is True
    access = logging.getLogger("uvicorn.access")
    assert access.handlers == []
    assert access.disabled is True


def test_unhandled_exception_logs_of_the_server_are_redacted(
    capsys: pytest.CaptureFixture[str],
):
    configure_logging(make_settings())

    try:
        raise ValueError("user@example.com 50.123456")
    except ValueError:
        logging.getLogger("uvicorn.error").exception("Exception in ASGI application")

    line = capsys.readouterr().err.strip()
    parsed = json.loads(line)
    assert parsed["logger"] == "uvicorn.error"
    assert parsed["exception"] == "ValueError"
    assert "example.com" not in line
    assert "50.123456" not in line


async def run_asgi(
    app: AccessLogMiddleware, path: str, query: bytes = b"", method: str = "GET"
) -> list[dict[str, object]]:
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query,
        "headers": [(b"authorization", b"Bearer canary-token")],
    }
    await app(scope, receive, send)  # type: ignore[arg-type]
    return sent


async def test_middleware_logs_only_the_allowed_fields_and_sets_the_request_id(
    caplog: pytest.LogCaptureFixture,
):
    async def inner(scope, receive, send):  # type: ignore[no-untyped-def]
        scope["route"] = type("Route", (), {"path": "/users/{user_id}"})()
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    caplog.set_level(logging.INFO, logger=ACCESS_LOGGER_NAME)

    sent = await run_asgi(AccessLogMiddleware(inner), "/users/42", b"email=a@b.c&lat=50.1")

    (record,) = [r for r in caplog.records if r.name == ACCESS_LOGGER_NAME]
    extras = {
        k: v
        for k, v in vars(record).items()
        if k in {"method", "route", "status", "duration_ms", "request_id"}
    }
    assert extras["route"] == "/users/{user_id}"
    assert extras["status"] == 204
    line = JsonFormatter().format(record)
    for forbidden in ("a@b.c", "50.1", "/users/42", "canary-token"):
        assert forbidden not in line
    headers = dict(sent[0]["headers"])  # type: ignore[arg-type]
    assert headers[b"x-request-id"].decode() == extras["request_id"]


async def test_middleware_logs_the_class_of_an_unhandled_exception_and_reraises(
    caplog: pytest.LogCaptureFixture,
):
    async def inner(scope, receive, send):  # type: ignore[no-untyped-def]
        raise RuntimeError("user@example.com")

    caplog.set_level(logging.INFO, logger=ACCESS_LOGGER_NAME)

    with pytest.raises(RuntimeError):
        await run_asgi(AccessLogMiddleware(inner), "/boom")

    records = [r for r in caplog.records if r.name == ACCESS_LOGGER_NAME]
    assert [r.getMessage() for r in records] == ["unhandled exception", "request"]
    assert records[0].error == "RuntimeError"  # type: ignore[attr-defined]
    assert records[1].status == 500  # type: ignore[attr-defined]
    assert "example.com" not in " ".join(JsonFormatter().format(r) for r in records)


async def test_middleware_ignores_non_http_scopes():
    seen: list[str] = []

    async def inner(scope, receive, send):  # type: ignore[no-untyped-def]
        seen.append(scope["type"])

    await AccessLogMiddleware(inner)({"type": "lifespan"}, None, None)  # type: ignore[arg-type]

    assert seen == ["lifespan"]


def test_formatter_drops_the_ansi_duplicate_of_the_message():
    record = make_record(color_message="\x1b[1mtext\x1b[0m")

    parsed = json.loads(JsonFormatter().format(record))

    assert "color_message" not in parsed
