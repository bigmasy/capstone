"""Base exceptions of the domain layer; the API layer maps them to HTTP statuses."""


class DomainError(Exception):
    """Base class of all domain errors.

    :param message: Description that is safe to return to the client.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class AuthenticationError(DomainError):
    """The caller could not be authenticated (HTTP 401)."""


class AccessDeniedError(DomainError):
    """The caller is known but not allowed to perform the action (HTTP 403)."""


class NotFoundError(DomainError):
    """The object does not exist or is not visible to the caller (HTTP 404)."""


class ConflictError(DomainError):
    """The action conflicts with the current state of the object (HTTP 409)."""
