"""Application settings read from the environment."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Used only when ENV=dev. Never accepted in prod, see Settings.check_prod_secrets.
_DEV_JWT_SECRET = "dev-only-secret-change-me-0123456789abcdef"  # noqa: S105
_DEV_DB_URL = "sqlite+aiosqlite:///./dev.db"
_MIN_JWT_SECRET_BYTES = 32
# Plain HTTP origins are accepted in prod only for the local machine (compose on a laptop).
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "[::1]"})


class Settings(BaseSettings):
    """Typed application settings.

    Values come from environment variables with the same names (and from ``.env`` for local
    development). The environment defaults to ``prod`` so a deployment that forgets to set it
    fails closed; outside ``ENV=dev`` the secrets must be supplied explicitly and the application
    refuses to start with an insecure default instead of running with it.
    """

    # hide_input_in_errors keeps JWT_SECRET and DB_URL out of validation error messages.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    ENV: Literal["dev", "test", "prod"] = "prod"
    # SecretStr keeps the connection password and the signing key out of repr, logs and tracebacks.
    DB_URL: SecretStr = SecretStr("")
    JWT_SECRET: SecretStr = SecretStr("")
    # Pinned to one algorithm so a token can never choose how it is verified.
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    JWT_EXPIRATION_SECONDS: int = Field(default=1800, gt=0)
    JWT_ISSUER: str = "adaptive-sport-api"
    JWT_AUDIENCE: str = "adaptive-sport-web"
    # Argon2id cost; the defaults are the argon2-cffi (RFC 9106 low-memory) profile. Tests lower
    # them through settings to keep the suite fast.
    ARGON2_TIME_COST: int = Field(default=3, ge=1)
    ARGON2_MEMORY_COST_KIB: int = Field(default=65536, ge=8)
    ARGON2_PARALLELISM: int = Field(default=4, ge=1)
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    MAX_MATCHES: int = Field(default=100, gt=0)
    CANDIDATE_RADIUS_KM: float = Field(default=100.0, gt=0)
    # How long an invitation can be answered; expiry is evaluated lazily from this stored instant.
    INVITATION_TTL_DAYS: int = Field(default=14, ge=1, le=90)
    # Retrieval cap of the matching feed: the ranker scores at most this many nearest candidates.
    CANDIDATE_LIMIT: int = Field(default=200, gt=0)
    # The learned ranker is opt-in: without an artifact the weighted baseline orders the feed.
    RANKER_ENABLED: bool = False
    RANKER_ARTIFACT_DIR: Path | None = None
    LOG_LEVEL: str = "INFO"

    @field_validator("RANKER_ARTIFACT_DIR", mode="before")
    @classmethod
    def blank_artifact_dir_is_unset(cls, value: object) -> object:
        """Treat an empty variable as "not set", which is how compose passes an unset path.

        :param value: Raw value from the environment.
        :return: None for a blank string, otherwise the value unchanged.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("LOG_LEVEL")
    @classmethod
    def normalise_log_level(cls, value: str) -> str:
        """Upper-case the level and reject names the logging module does not know.

        :param value: Raw level name.
        :raises ValueError: If the level is not a standard logging level.
        :return: Upper-case level name.
        """
        level = value.upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL")
        return level

    @field_validator("CORS_ORIGINS")
    @classmethod
    def check_origins(cls, value: list[str]) -> list[str]:
        """Require explicit origins: a scheme and a host, no wildcard, no path.

        :param value: Configured origins.
        :raises ValueError: If an origin is a wildcard or not of the form ``scheme://host[:port]``.
        :return: The origins unchanged.
        """
        for origin in value:
            if "*" in origin:
                raise ValueError("CORS_ORIGINS must list explicit origins, not wildcards")
            parts = urlsplit(origin)
            explicit = (
                parts.scheme in {"http", "https"}
                and bool(parts.hostname)
                and parts.path == ""
                and not (parts.query or parts.fragment or parts.username or parts.password)
            )
            if not explicit:
                raise ValueError(
                    "CORS_ORIGINS entries must look like https://host[:port] "
                    "(scheme and host, no path)"
                )
        return value

    @model_validator(mode="after")
    def check_environment(self) -> Self:
        """Fill dev defaults, or fail fast when a non-dev environment is not safe to run.

        :raises ValueError: If the learned ranker is enabled without an artifact directory, if
            DB_URL or JWT_SECRET is missing outside dev, the secret is shorter
            than 32 bytes or equals the dev default, or prod uses SQLite or a non-HTTPS origin.
        :return: The validated settings.
        """
        if self.RANKER_ENABLED and self.RANKER_ARTIFACT_DIR is None:
            raise ValueError("RANKER_ARTIFACT_DIR must be set when RANKER_ENABLED is true")
        if self.ENV == "dev":
            if not self.DB_URL.get_secret_value():
                self.DB_URL = SecretStr(_DEV_DB_URL)
            if not self.JWT_SECRET.get_secret_value():
                self.JWT_SECRET = SecretStr(_DEV_JWT_SECRET)
            return self
        database_url = self.DB_URL.get_secret_value()
        secret = self.JWT_SECRET.get_secret_value()
        if not database_url:
            raise ValueError(f"DB_URL must be set when ENV={self.ENV}")
        if not secret:
            raise ValueError(f"JWT_SECRET must be set when ENV={self.ENV}")
        if secret == _DEV_JWT_SECRET:
            raise ValueError(f"JWT_SECRET must not be the development default when ENV={self.ENV}")
        if len(secret.encode()) < _MIN_JWT_SECRET_BYTES:
            raise ValueError(f"JWT_SECRET must be at least 32 bytes when ENV={self.ENV}")
        if self.ENV == "prod":
            if database_url.startswith("sqlite"):
                raise ValueError("DB_URL must not point to SQLite when ENV=prod")
            for origin in self.CORS_ORIGINS:
                parts = urlsplit(origin)
                if parts.scheme != "https" and parts.hostname not in _LOOPBACK_HOSTS:
                    raise ValueError("CORS_ORIGINS must use https when ENV=prod")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, built on first use.

    The instance is cached; tests that change the environment call ``get_settings.cache_clear()``.

    :raises pydantic.ValidationError: If the environment holds invalid or insecure values.
    :return: Validated settings.
    """
    return Settings()
