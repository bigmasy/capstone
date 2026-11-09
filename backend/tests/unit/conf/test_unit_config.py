import importlib
import sys

import pytest
from pydantic import ValidationError

from app.conf.config import Settings, get_settings

STRONG_SECRET = "s" * 40
PROD_DB = "postgresql+asyncpg://user:pw@db:5432/app"


def build(**values: object) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def build_dev(**values: object) -> Settings:
    return build(ENV="dev", **values)


def test_environment_defaults_to_prod_and_fails_closed():
    with pytest.raises(ValidationError, match="DB_URL"):
        build()


def test_dev_defaults_are_usable():
    settings = build_dev()

    assert settings.ENV == "dev"
    assert settings.DB_URL.get_secret_value().startswith("sqlite+aiosqlite")
    assert len(settings.JWT_SECRET.get_secret_value().encode()) >= 32
    assert settings.JWT_ALGORITHM == "HS256"
    assert settings.JWT_EXPIRATION_SECONDS == 1800
    assert settings.CORS_ORIGINS == ["http://localhost:5173"]
    assert settings.MAX_MATCHES == 100
    assert settings.CANDIDATE_RADIUS_KM == 100.0


def test_invitation_ttl_defaults_to_two_weeks():
    assert build_dev().INVITATION_TTL_DAYS == 14


@pytest.mark.parametrize("days", [1, 14, 90])
def test_invitation_ttl_accepts_the_allowed_range(days: int):
    assert build_dev(INVITATION_TTL_DAYS=days).INVITATION_TTL_DAYS == days


@pytest.mark.parametrize("days", [0, -1, 91])
def test_invitation_ttl_outside_one_to_ninety_days_is_rejected(days: int):
    with pytest.raises(ValidationError):
        build_dev(INVITATION_TTL_DAYS=days)


def test_prod_requires_database_url():
    with pytest.raises(ValidationError, match="DB_URL"):
        build(ENV="prod", JWT_SECRET=STRONG_SECRET)


def test_prod_requires_jwt_secret():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        build(ENV="prod", DB_URL=PROD_DB)


def test_prod_rejects_short_secret():
    with pytest.raises(ValidationError, match="32 bytes"):
        build(ENV="prod", DB_URL=PROD_DB, JWT_SECRET="short")


def test_prod_rejects_the_development_secret():
    dev_secret = build_dev().JWT_SECRET.get_secret_value()

    with pytest.raises(ValidationError, match="development default"):
        build(ENV="prod", DB_URL=PROD_DB, JWT_SECRET=dev_secret)


def test_prod_accepts_strong_values():
    settings = build(ENV="prod", DB_URL=PROD_DB, JWT_SECRET=STRONG_SECRET)

    assert settings.ENV == "prod"


def test_validation_error_does_not_leak_the_secret():
    with pytest.raises(ValidationError) as caught:
        build(ENV="prod", DB_URL="postgresql+asyncpg://user:hunter2@db/app", JWT_SECRET="short")

    assert "hunter2" not in str(caught.value)
    assert "short'" not in str(caught.value)


def test_secrets_are_masked_in_repr_and_dump():
    settings = build(
        ENV="prod", DB_URL="postgresql+asyncpg://u:hunter2@db/app", JWT_SECRET=STRONG_SECRET
    )

    assert "hunter2" not in repr(settings)
    assert STRONG_SECRET not in repr(settings)
    assert STRONG_SECRET not in str(settings.model_dump())


def test_non_dev_environments_reject_the_development_secret_and_short_secrets():
    dev_secret = build_dev().JWT_SECRET.get_secret_value()

    with pytest.raises(ValidationError, match="development default"):
        build(ENV="test", DB_URL="sqlite+aiosqlite:///:memory:", JWT_SECRET=dev_secret)
    with pytest.raises(ValidationError, match="32 bytes"):
        build(ENV="test", DB_URL="sqlite+aiosqlite:///:memory:", JWT_SECRET="short")


def test_prod_rejects_sqlite():
    with pytest.raises(ValidationError, match="SQLite"):
        build(ENV="prod", DB_URL="sqlite+aiosqlite:///./app.db", JWT_SECRET=STRONG_SECRET)


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://*.example.com",
        "example.com",
        "ftp://example.com",
        "https://example.com/app",
        "https://example.com/",
        "https://user:pw@example.com",
        "https://example.com?x=1",
        "https://",
    ],
)
def test_malformed_or_wildcard_cors_origins_are_rejected(origin: str):
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        build_dev(CORS_ORIGINS=[origin])


def test_prod_requires_https_origins_except_for_loopback():
    with pytest.raises(ValidationError, match="https"):
        build(
            ENV="prod", DB_URL=PROD_DB, JWT_SECRET=STRONG_SECRET, CORS_ORIGINS=["http://a.example"]
        )

    settings = build(
        ENV="prod",
        DB_URL=PROD_DB,
        JWT_SECRET=STRONG_SECRET,
        CORS_ORIGINS=["https://a.example:8443", "http://localhost:5173"],
    )

    assert len(settings.CORS_ORIGINS) == 2


def test_environment_variables_are_read(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAX_MATCHES", "7")
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.example","https://b.example"]')

    settings = build_dev()

    assert settings.MAX_MATCHES == 7
    assert settings.CORS_ORIGINS == ["https://a.example", "https://b.example"]


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENV", "dev")
    first = get_settings()
    second = get_settings()

    assert first is second


def test_get_settings_cache_can_be_cleared(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENV", "dev")
    first = get_settings()
    monkeypatch.setenv("MAX_MATCHES", "5")
    get_settings.cache_clear()

    assert get_settings() is not first
    assert get_settings().MAX_MATCHES == 5


def test_importing_the_module_creates_no_settings(monkeypatch: pytest.MonkeyPatch):
    # A prod environment without secrets would raise if an instance were built at import time.
    monkeypatch.setenv("ENV", "prod")
    # monkeypatch restores the original module object afterwards.
    monkeypatch.delitem(sys.modules, "app.conf.config")

    module = importlib.import_module("app.conf.config")

    assert module.get_settings.cache_info().currsize == 0
    with pytest.raises(ValidationError):
        module.get_settings()


def test_token_and_hashing_defaults():
    settings = build_dev()

    assert settings.JWT_ISSUER
    assert settings.JWT_AUDIENCE
    assert settings.ARGON2_TIME_COST >= 2
    assert settings.ARGON2_MEMORY_COST_KIB >= 19456
    assert settings.ARGON2_PARALLELISM >= 1


def test_only_hs256_is_accepted():
    with pytest.raises(ValidationError, match="JWT_ALGORITHM"):
        build_dev(JWT_ALGORITHM="none")


def test_the_learned_ranker_is_off_by_default():
    settings = build_dev()

    assert settings.RANKER_ENABLED is False
    assert settings.RANKER_ARTIFACT_DIR is None
    assert settings.CANDIDATE_LIMIT == 200


def test_enabling_the_ranker_requires_an_artifact_directory():
    with pytest.raises(ValidationError, match="RANKER_ARTIFACT_DIR"):
        build_dev(RANKER_ENABLED=True)


def test_an_artifact_directory_is_accepted_as_a_path(tmp_path):
    settings = build_dev(RANKER_ENABLED=True, RANKER_ARTIFACT_DIR=str(tmp_path))

    assert settings.RANKER_ARTIFACT_DIR == tmp_path


def test_a_blank_artifact_directory_counts_as_unset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RANKER_ARTIFACT_DIR", "  ")

    assert build_dev().RANKER_ARTIFACT_DIR is None


def test_the_candidate_limit_must_be_positive():
    with pytest.raises(ValidationError, match="CANDIDATE_LIMIT"):
        build_dev(CANDIDATE_LIMIT=0)


def test_the_compose_ranker_variables_are_valid_for_prod(monkeypatch: pytest.MonkeyPatch):
    # The values are strings, as the compose file passes them to the api container
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("DB_URL", PROD_DB)
    monkeypatch.setenv("JWT_SECRET", STRONG_SECRET)
    monkeypatch.setenv("RANKER_ENABLED", "true")
    monkeypatch.setenv("RANKER_ARTIFACT_DIR", "/var/lib/ranker")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.RANKER_ENABLED is True
    assert str(settings.RANKER_ARTIFACT_DIR) == "/var/lib/ranker"


def test_an_enabled_ranker_with_a_blank_directory_is_refused(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RANKER_ENABLED", "true")
    monkeypatch.setenv("RANKER_ARTIFACT_DIR", "")

    with pytest.raises(ValidationError, match="RANKER_ARTIFACT_DIR"):
        build_dev()
