"""Password reset by e-mail: the error around the one-time token.

The token itself is made, hashed and stored exactly like the e-mail confirmation token (see
:mod:`app.domain.verification`); only the meaning and the lifetime differ.
"""

from app.domain.errors import DomainError

INVALID_RESET_MESSAGE = "The reset link is invalid or has expired"


class InvalidResetError(DomainError):
    """The reset token is unknown, used or expired (HTTP 400).

    The three cases are not told apart, so the answer reveals nothing about other tokens.
    """

    def __init__(self) -> None:
        """Use the fixed message."""
        super().__init__(INVALID_RESET_MESSAGE)
