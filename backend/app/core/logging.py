"""JSON logging with redaction and a minimal access log."""

import json
import logging
import time
import uuid
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.conf.config import Settings

REDACTED = "[redacted]"

# Words that mark a log field as sensitive. A key is sensitive when it equals one of them or
# when one of its underscore-separated parts does (``user_email``, ``new-password``). Coordinates
# and functional capabilities are the core privacy claim of the platform; credentials, contact
# details and e-mails are personal data. Matching on whole parts keeps harmless names such as
# ``latency_ms`` readable.
SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "token",
        "authorization",
        "cookie",
        "secret",
        "credential",
        "credentials",
        "email",
        "contact",
        "latitude",
        "longitude",
        "lat",
        "lon",
        "lng",
        "coordinates",
        "location",
        "capabilities",
        "capability",
        "functional",
        "equipment",
        "category",
        "categories",
        "db_url",
        "dsn",
    }
)

# Attributes every LogRecord has; anything else was added through ``extra=``.
# ``color_message`` is the ANSI duplicate of the message that uvicorn adds to its own records.
_STANDARD_ATTRS = frozenset(vars(logging.makeLogRecord({}))) | {
    "message",
    "asctime",
    "taskName",
    "color_message",
}

ACCESS_LOGGER_NAME = "app.access"

# Database drivers print bound parameters at DEBUG and INFO: e-mails, contacts and coordinates
# would end up in the log whatever the redaction filter does with structured fields.
_QUIET_LOGGERS = ("aiosqlite", "sqlalchemy.engine", "asyncpg")

# The server installs its own plain-text handlers on these loggers. They are removed so that
# every line, including start-up messages and tracebacks of unhandled exceptions, goes through
# the JSON formatter and the redaction filter of the root logger.
_SERVER_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.asgi")


def is_sensitive_key(key: object) -> bool:
    """Tell whether a field name marks a value that must not be logged.

    :param key: Field name; compared case-insensitively, hyphens count as underscores.
    :return: True if the name or one of its parts is in :data:`SENSITIVE_KEYS`.
    """
    name = str(key).lower().replace("-", "_")
    return name in SENSITIVE_KEYS or any(part in SENSITIVE_KEYS for part in name.split("_"))


def redact(value: Any) -> Any:
    """Return a copy of ``value`` with the values of sensitive keys replaced.

    :param value: A mapping, a list or tuple, or a scalar.
    :return: The same structure with sensitive values masked.
    """
    if isinstance(value, Mapping):
        return {
            key: REDACTED if is_sensitive_key(key) else redact(item) for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact(item) for item in value]
    return value


class RedactionFilter(logging.Filter):
    """Mask sensitive values in structured ``extra`` fields and in mapping log arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact the record in place; never drops it.

        :param record: Record about to be emitted.
        :return: Always ``True``.
        """
        for key in list(vars(record)):
            if key in _STANDARD_ATTRS:
                continue
            if is_sensitive_key(key):
                setattr(record, key, REDACTED)
            else:
                setattr(record, key, redact(getattr(record, key)))
        if isinstance(record.args, Mapping):
            record.args = redact(record.args)
        return True


class JsonFormatter(logging.Formatter):
    """Format records as one JSON object per line.

    Structured fields are redacted here as well, so a handler that was installed without the
    :class:`RedactionFilter` still cannot print a sensitive field.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Serialise the record.

        :param record: Record to format.
        :return: A single-line JSON document.
        """
        payload: dict[str, Any] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, item in vars(record).items():
            if key not in _STANDARD_ATTRS:
                payload[key] = REDACTED if is_sensitive_key(key) else redact(item)
        if record.exc_info:
            # Only the exception class: its message may hold user data.
            payload["exception"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(settings: Settings) -> None:
    """Install the JSON handler with the redaction filter on the root logger.

    The server loggers lose their own handlers and propagate to the root, and the server's access
    log is switched off in favour of :class:`AccessLogMiddleware`. Safe to call repeatedly:
    earlier handlers installed by this function are replaced.

    :param settings: Application settings; ``LOG_LEVEL`` selects the level.
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_app_handler", False):
            root.removeHandler(handler)
    handler = logging.StreamHandler()
    handler._app_handler = True  # type: ignore[attr-defined]
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())
    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL)
    for name in _SERVER_LOGGERS:
        server_logger = logging.getLogger(name)
        for server_handler in list(server_logger.handlers):
            server_logger.removeHandler(server_handler)
        server_logger.propagate = True
    # The server's own access log would print the raw path and query string.
    access = logging.getLogger("uvicorn.access")
    for access_handler in list(access.handlers):
        access.removeHandler(access_handler)
    access.disabled = True
    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(max(root.level, logging.WARNING))


def _route_template(scope: Scope) -> str:
    """Return the matched route path, never the concrete URL with ids or query."""
    route = scope.get("route")
    return str(getattr(route, "path", "unmatched"))


class AccessLogMiddleware:
    """Pure ASGI middleware that logs method, route template, status and duration.

    Bodies, headers, query strings and concrete paths are never read or logged. A random request
    id is generated here and returned in ``X-Request-ID``. Being pure ASGI (no
    ``BaseHTTPMiddleware``) it adds no request/response wrapping and cannot buffer bodies.

    :param app: The wrapped ASGI application.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Keep the wrapped application and the logger."""
        self.app = app
        self.logger = logging.getLogger(ACCESS_LOGGER_NAME)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle one connection; only HTTP requests are logged.

        :param scope: ASGI scope.
        :param receive: ASGI receive channel.
        :param send: ASGI send channel.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex
        started = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            """Remember the status and add the request id header to the response start."""
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            # Only the class is logged: the message can hold request data.
            self.logger.error(
                "unhandled exception",
                extra={
                    "route": _route_template(scope),
                    "error": type(exc).__name__,
                    "request_id": request_id,
                },
            )
            raise
        finally:
            self.logger.info(
                "request",
                extra={
                    "method": scope["method"],
                    "route": _route_template(scope),
                    "status": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "request_id": request_id,
                },
            )


def install_access_log(app: FastAPI) -> None:
    """Add :class:`AccessLogMiddleware` as the outermost middleware.

    :param app: Application to extend.
    """
    app.add_middleware(AccessLogMiddleware)
