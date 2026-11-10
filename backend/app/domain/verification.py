"""E-mail verification: one-time tokens and the errors around them.

A token is a random URL-safe string that is e-mailed to the owner of the address and never
stored: only its SHA-256 digest is, so a copy of the database cannot be used to verify an
account. The functions here are pure and use only the standard library.
"""

import hashlib
import secrets

from app.domain.errors import AccessDeniedError, DomainError

TOKEN_BYTES = 32
# Stable machine code of the 403 answer; the client switches on it, the text may change.
EMAIL_NOT_VERIFIED_CODE = "email_not_verified"
EMAIL_NOT_VERIFIED_MESSAGE = "Confirm your e-mail address first"
INVALID_VERIFICATION_MESSAGE = "The confirmation link is invalid or has expired"


class EmailNotVerifiedError(AccessDeniedError):
    """The action needs an account whose e-mail address is confirmed (HTTP 403).

    :param code: Machine-readable code of the error.
    """

    code = EMAIL_NOT_VERIFIED_CODE

    def __init__(self) -> None:
        """Use the fixed message."""
        super().__init__(EMAIL_NOT_VERIFIED_MESSAGE)


class InvalidVerificationError(DomainError):
    """The confirmation token is unknown, used or expired (HTTP 400).

    The three cases are not told apart, so the answer reveals nothing about other tokens.
    """

    def __init__(self) -> None:
        """Use the fixed message."""
        super().__init__(INVALID_VERIFICATION_MESSAGE)


def generate_token() -> str:
    """Return a new random token (256 bits, URL-safe).

    :return: The token to put into the e-mailed link.
    """
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """Return the digest under which a token is stored and looked up.

    A fast hash is enough here: the token is random and long, so it cannot be guessed from
    its digest the way a password can.

    :param token: The token as it appears in the link.
    :return: Hexadecimal SHA-256 digest.
    """
    return hashlib.sha256(token.encode()).hexdigest()
