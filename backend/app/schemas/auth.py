"""Request and response models of the authentication routes."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.domain.account import (
    EMAIL_MAX_LENGTH,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    Account,
    password_meets_policy,
)

# Deliberately simple: one "@", a dot in the domain, no whitespace. Full RFC validation needs a
# dependency and still cannot prove the address exists.
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=EMAIL_MAX_LENGTH, pattern=_EMAIL_PATTERN
    ),
]


class RegisterRequest(BaseModel):
    """Body of ``POST /auth/register``."""

    model_config = ConfigDict(extra="forbid")

    email: Email
    password: Annotated[
        str, Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH, repr=False)
    ]

    @field_validator("password")
    @classmethod
    def check_policy(cls, value: str) -> str:
        """Apply the shared password policy with a fixed message.

        :param value: Submitted password.
        :raises ValueError: If the policy is not met.
        :return: The password unchanged.
        """
        if not password_meets_policy(value):
            raise ValueError("Password does not meet the policy")
        return value


class LoginRequest(BaseModel):
    """Body of ``POST /auth/login``.

    The password length is only capped, never checked against the registration policy, so a
    short wrong password gets the same answer as any other wrong password.
    """

    model_config = ConfigDict(extra="forbid")

    email: Annotated[
        str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=EMAIL_MAX_LENGTH)
    ]
    password: Annotated[str, Field(min_length=1, max_length=PASSWORD_MAX_LENGTH, repr=False)]


class VerifyEmailRequest(BaseModel):
    """Body of ``POST /auth/verify-email``: the token from the link in the message."""

    model_config = ConfigDict(extra="forbid")

    token: Annotated[
        str, Field(min_length=20, max_length=200, pattern=r"^[A-Za-z0-9_-]+$", repr=False)
    ]


class ForgotPasswordRequest(BaseModel):
    """Body of ``POST /auth/forgot-password``: the address a reset link is asked for."""

    model_config = ConfigDict(extra="forbid")

    email: Email


class ResetPasswordRequest(BaseModel):
    """Body of ``POST /auth/reset-password``: the token from the link and the new password."""

    model_config = ConfigDict(extra="forbid")

    token: Annotated[
        str, Field(min_length=20, max_length=200, pattern=r"^[A-Za-z0-9_-]+$", repr=False)
    ]
    password: Annotated[
        str, Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH, repr=False)
    ]

    @field_validator("password")
    @classmethod
    def check_policy(cls, value: str) -> str:
        """Apply the shared password policy with a fixed message.

        :param value: Submitted password.
        :raises ValueError: If the policy is not met.
        :return: The password unchanged.
        """
        if not password_meets_policy(value):
            raise ValueError("Password does not meet the policy")
        return value


class TokenResponse(BaseModel):
    """Answer of a successful login."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105


class UserResponse(BaseModel):
    """The caller's own account; the e-mail is shown to its owner only."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    created_at: datetime
    # False until the owner follows the link from the message; such an account can browse and
    # edit its own profile but cannot invite, accept or be found by others.
    email_verified: bool

    @classmethod
    def from_domain(cls, account: Account) -> "UserResponse":
        """Build the response from an account record.

        :param account: The caller's account.
        :return: The response model.
        """
        return cls(
            id=account.id,
            email=account.email,
            created_at=account.created_at,
            email_verified=account.is_verified,
        )


class ErrorResponse(BaseModel):
    """Body of every domain error: a fixed message that never repeats the input."""

    detail: str
