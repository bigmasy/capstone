"""Password hashing (Argon2id) and access tokens (JWT, HS256)."""

import secrets
from datetime import UTC, datetime, timedelta
from functools import cached_property
from uuid import UUID

import jwt
from argon2 import PasswordHasher as _Argon2
from argon2 import Type
from argon2.exceptions import InvalidHashError, VerificationError

from app.conf.config import Settings
from app.domain.account import password_meets_policy
from app.domain.errors import AuthenticationError

# One message for every token failure: the reason (expired, forged, wrong audience) is of use
# to an attacker and of none to an honest client, which simply signs in again.
_INVALID_TOKEN = "Could not validate credentials"  # noqa: S105
_REQUIRED_CLAIMS = ["sub", "iat", "exp", "iss", "aud"]


class PasswordHasher:
    """Argon2id hashing with the cost taken from settings.

    :param settings: Application settings; the ``ARGON2_*`` values set the cost.
    """

    def __init__(self, settings: Settings) -> None:
        """Build the underlying Argon2id hasher."""
        self._argon2 = _Argon2(
            time_cost=settings.ARGON2_TIME_COST,
            memory_cost=settings.ARGON2_MEMORY_COST_KIB,
            parallelism=settings.ARGON2_PARALLELISM,
            type=Type.ID,
        )

    def hash(self, password: str) -> str:
        """Hash a password with a fresh random salt.

        :param password: Plain password.
        :raises ValueError: If the password breaks the password policy.
        :return: Encoded Argon2id hash.
        """
        if not password_meets_policy(password):
            raise ValueError("password policy violated")
        return self._argon2.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        """Check a password against a stored hash.

        :param password_hash: Stored hash.
        :param password: Plain password.
        :return: True if they match; False for a mismatch and for an unreadable hash.
        """
        try:
            return self._argon2.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        """Tell whether a stored hash was made with weaker parameters than the current ones.

        :param password_hash: Stored hash.
        :return: True when the hash should be recomputed after a successful login.
        """
        return self._argon2.check_needs_rehash(password_hash)

    @cached_property
    def dummy_hash(self) -> str:
        """A hash of a random password nobody knows, made with the current parameters.

        Login verifies against it when the e-mail is unknown, so that the work done (and the
        response) is the same as for a wrong password.
        """
        return self._argon2.hash(secrets.token_urlsafe(32))


class TokenCodec:
    """Issues and validates access tokens.

    :param settings: Application settings: secret, algorithm, lifetime, issuer and audience.
    """

    def __init__(self, settings: Settings) -> None:
        """Keep the settings the codec needs."""
        self._secret = settings.JWT_SECRET.get_secret_value()
        self._algorithm = settings.JWT_ALGORITHM
        self._lifetime = timedelta(seconds=settings.JWT_EXPIRATION_SECONDS)
        self._issuer = settings.JWT_ISSUER
        self._audience = settings.JWT_AUDIENCE

    def issue(self, user_id: UUID, now: datetime | None = None) -> str:
        """Create a signed access token.

        :param user_id: Subject of the token.
        :param now: Issue time; the current time when omitted.
        :return: Encoded JWT.
        """
        issued = now or datetime.now(UTC)
        claims = {
            "sub": str(user_id),
            "iat": issued,
            "exp": issued + self._lifetime,
            "iss": self._issuer,
            "aud": self._audience,
        }
        return jwt.encode(claims, self._secret, algorithm=self._algorithm)

    def decode(self, token: str) -> UUID:
        """Validate a token and return its subject.

        The accepted algorithm is pinned, so ``alg=none`` and key-confusion tokens fail.

        :param token: Encoded JWT.
        :raises AuthenticationError: If the token is malformed, expired, forged, issued for
            another audience or issuer, lacks a required claim, or has no UUID subject.
        :return: The user identifier.
        """
        return self.decode_with_issue_time(token)[0]

    def decode_with_issue_time(self, token: str) -> tuple[UUID, datetime]:
        """Validate a token and return its subject together with the time it was issued.

        :param token: Encoded JWT.
        :raises AuthenticationError: As for :meth:`decode`.
        :return: The user identifier and the issue time (UTC, whole seconds).
        """
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": _REQUIRED_CLAIMS},
            )
            return UUID(str(claims["sub"])), datetime.fromtimestamp(int(claims["iat"]), UTC)
        except (jwt.PyJWTError, ValueError, TypeError, OverflowError, OSError) as exc:
            raise AuthenticationError(_INVALID_TOKEN) from exc
