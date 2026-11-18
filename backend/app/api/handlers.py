"""Exception handlers: map domain errors and validation errors to HTTP responses."""

import types
import typing
from collections.abc import Iterable
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.dependencies.models import Dependant
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel

from app.domain.account import (
    LOCATION_INCOMPLETE_MESSAGE,
    LOCATION_REQUIRED_MESSAGE,
    LocationRequiredError,
)
from app.domain.errors import (
    AccessDeniedError,
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
)
from app.domain.invitations import ContactRequiredError
from app.domain.password_reset import InvalidResetError
from app.domain.photo import PHOTO_INVALID_CODE, PhotoRejectedError
from app.domain.verification import EmailNotVerifiedError, InvalidVerificationError

_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    AccessDeniedError: status.HTTP_403_FORBIDDEN,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    InvalidVerificationError: status.HTTP_400_BAD_REQUEST,
    InvalidResetError: status.HTTP_400_BAD_REQUEST,
}

# Fixed text per pydantic error type. The message pydantic produces can quote the input (UUID
# and URL parsing, regular expressions, custom validators), and an error may carry ``input``,
# ``ctx`` and ``url``; none of them is ever returned. A type outside this table is reported as
# a generic ``invalid`` error.
_MESSAGES: dict[str, str] = {
    "missing": "Field required",
    "extra_forbidden": "Unexpected field",
    "json_invalid": "Malformed JSON",
    "model_attributes_type": "Invalid object",
    "dict_type": "Invalid object",
    "list_type": "Invalid list",
    "string_type": "Invalid text",
    "string_too_short": "Text is too short",
    "string_too_long": "Text is too long",
    "string_pattern_mismatch": "Text has an invalid format",
    "int_type": "Invalid integer",
    "int_parsing": "Invalid integer",
    "float_type": "Invalid number",
    "float_parsing": "Invalid number",
    "bool_type": "Invalid boolean",
    "bool_parsing": "Invalid boolean",
    "uuid_type": "Invalid identifier",
    "uuid_parsing": "Invalid identifier",
    "datetime_type": "Invalid date and time",
    "datetime_parsing": "Invalid date and time",
    "enum": "Value is not allowed",
    "literal_error": "Value is not allowed",
    "greater_than": "Value is too small",
    "greater_than_equal": "Value is too small",
    "less_than": "Value is too large",
    "less_than_equal": "Value is too large",
    "too_short": "Too few items",
    "too_long": "Too many items",
    "value_error": "Invalid value",
    "location_incomplete": LOCATION_INCOMPLETE_MESSAGE,
    "assertion_error": "Invalid value",
}
_GENERIC_TYPE = "invalid"
_GENERIC_MESSAGE = "Invalid value"

# Parts of a location that FastAPI itself puts first; they are not user-controlled.
_LOC_SOURCES = frozenset({"body", "query", "path", "header", "cookie"})


def _model_types(annotation: Any) -> Iterable[type[BaseModel]]:
    """Yield every pydantic model reachable from an annotation (unions, lists, dicts)."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation
        return
    for arg in typing.get_args(annotation):
        if isinstance(arg, type | types.GenericAlias | types.UnionType) or typing.get_origin(arg):
            yield from _model_types(arg)


def _model_names(model: type[BaseModel], seen: set[type[BaseModel]]) -> Iterable[str]:
    """Yield field names and aliases of a model and of the models nested in it."""
    if model in seen:
        return
    seen.add(model)
    for name, info in model.model_fields.items():
        yield name
        if info.alias:
            yield info.alias
        for nested in _model_types(info.annotation):
            yield from _model_names(nested, seen)


def _dependant_names(dependant: Dependant, seen: set[type[BaseModel]]) -> Iterable[str]:
    """Yield parameter and model field names used by a dependant and its sub-dependencies."""
    fields = [
        *dependant.path_params,
        *dependant.query_params,
        *dependant.header_params,
        *dependant.cookie_params,
        *dependant.body_params,
    ]
    for field in fields:
        yield field.name
        yield field.alias
        for model in _model_types(field.field_info.annotation):
            yield from _model_names(model, seen)
    for sub in dependant.dependencies:
        yield from _dependant_names(sub, seen)


def known_loc_names(app: FastAPI) -> frozenset[str]:
    """Collect the names that may appear in a validation error location.

    The names derive from the request parameters and request models of the routes actually
    registered on the application, so a new model is covered without touching this module.

    :param app: Application whose routes are inspected.
    :return: Allowed location keys.
    """
    names: set[str] = set(_LOC_SOURCES)
    seen: set[type[BaseModel]] = set()
    for route in app.routes:
        if isinstance(route, APIRoute):
            names.update(_dependant_names(route.dependant, seen))
    return frozenset(names)


def safe_loc(loc: Iterable[str | int], known: frozenset[str]) -> list[str | int]:
    """Mask the parts of a location that are not known field names.

    Unknown keys may be client-controlled (for example an unexpected property name in a JSON
    body, which can carry a value or a secret), so they are replaced with ``"?"``.

    :param loc: Location from a pydantic error.
    :param known: Allowed names, see :func:`known_loc_names`.
    :return: Location with unknown string keys masked; list indexes are kept.
    """
    return [part if isinstance(part, int) or part in known else "?" for part in loc]


def safe_error(error_type: str, loc: Iterable[str | int], known: frozenset[str]) -> dict[str, Any]:
    """Build the public form of one validation error from its type and location only.

    :param error_type: Error type reported by pydantic.
    :param loc: Location from the pydantic error.
    :param known: Allowed location names, see :func:`known_loc_names`.
    :return: Dictionary with ``type``, masked ``loc`` and a fixed ``msg``.
    """
    message = _MESSAGES.get(error_type)
    return {
        "type": error_type if message else _GENERIC_TYPE,
        "loc": safe_loc(loc, known),
        "msg": message or _GENERIC_MESSAGE,
    }


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Answer 422 with only ``type``, ``loc`` and a fixed ``msg`` for each error.

    The default FastAPI response echoes the input, which may include exact coordinates and
    functional capabilities; those must never be returned. Neither is the pydantic message
    forwarded, because it can quote the input; see :func:`safe_error`.

    :param request: Failing request, used to reach the application routes.
    :param exc: Validation error raised by FastAPI.
    :return: JSON response with status 422.
    """
    known = known_loc_names(request.app)
    detail = [safe_error(err["type"], err["loc"], known) for err in exc.errors()]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": detail}
    )


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map a domain error to its HTTP status with body ``{"detail": message}``.

    :param request: Failing request (unused).
    :param exc: A :class:`DomainError` subclass instance.
    :return: JSON response; 401, 403, 404 or 409 depending on the error class.
    """
    code = status.HTTP_400_BAD_REQUEST
    for error_type, mapped in _STATUS_BY_ERROR.items():
        if isinstance(exc, error_type):
            code = mapped
            break
    message = exc.message if isinstance(exc, DomainError) else "Request failed"
    headers = {"WWW-Authenticate": "Bearer"} if code == status.HTTP_401_UNAUTHORIZED else None
    return JSONResponse(status_code=code, content={"detail": message}, headers=headers)


async def contact_required_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answer 409 with the usual body plus a stable machine code.

    The client switches on ``code`` to point the user to the profile; the text may change, the
    code does not.

    :param request: Failing request (unused).
    :param exc: A :class:`ContactRequiredError`.
    :return: JSON response with status 409 and ``{"detail": ..., "code": "contact_required"}``.
    """
    if not isinstance(exc, ContactRequiredError):
        return await domain_error_handler(request, exc)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT, content={"detail": exc.message, "code": exc.code}
    )


async def email_not_verified_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answer 403 with the usual body plus a stable machine code.

    The client switches on ``code`` to ask the person to confirm the address.

    :param request: Failing request (unused).
    :param exc: An :class:`EmailNotVerifiedError`.
    :return: JSON response with status 403 and ``{"detail": ..., "code": "email_not_verified"}``.
    """
    if not isinstance(exc, EmailNotVerifiedError):
        return await domain_error_handler(request, exc)
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN, content={"detail": exc.message, "code": exc.code}
    )


async def location_required_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answer a profile save that has no location to store with a 422 in the validation shape.

    The two location fields are named so a client can show the message next to them, exactly
    as for any other field error. The message is fixed and repeats no submitted value.

    :param request: Failing request (unused).
    :param exc: A :class:`LocationRequiredError` (its message is fixed, so a constant is used).
    :return: JSON response with status 422.
    """
    errors = [
        {"type": "location_required", "loc": ["body", field], "msg": LOCATION_REQUIRED_MESSAGE}
        for field in ("latitude", "longitude")
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": errors}
    )


async def photo_rejected_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answer an upload that cannot be used as a photograph with a 422 and a reason code.

    :param request: Failing request (unused).
    :param exc: A :class:`PhotoRejectedError`; its message is fixed and repeats no input.
    :return: JSON response with status 422 and ``{"detail": ..., "code": ...}``.
    """
    code = exc.code if isinstance(exc, PhotoRejectedError) else PHOTO_INVALID_CODE
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": str(exc), "code": code},
    )


def describe_validation_errors_truthfully(app: FastAPI) -> None:
    """Make the published schema of a validation error match what the handler returns.

    Recent FastAPI versions describe ``input`` and ``ctx`` on each error; the handler never
    returns them, and the contract must not suggest that it does.

    :param app: Application whose ``openapi`` method is wrapped.
    """
    build_schema = app.openapi

    def openapi() -> dict[str, Any]:
        """Return the cached schema without the fields the handler drops."""
        schema = build_schema()
        error = schema.get("components", {}).get("schemas", {}).get("ValidationError", {})
        for name in ("input", "ctx"):
            error.get("properties", {}).pop(name, None)
        return schema

    app.openapi = openapi  # type: ignore[method-assign]


def register_exception_handlers(app: FastAPI) -> None:
    """Install all handlers on the application.

    :param app: Application to extend.
    """
    describe_validation_errors_truthfully(app)
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    for error_type in _STATUS_BY_ERROR:
        app.add_exception_handler(error_type, domain_error_handler)
    app.add_exception_handler(LocationRequiredError, location_required_handler)
    app.add_exception_handler(PhotoRejectedError, photo_rejected_handler)
    app.add_exception_handler(ContactRequiredError, contact_required_handler)
    app.add_exception_handler(EmailNotVerifiedError, email_not_verified_handler)
