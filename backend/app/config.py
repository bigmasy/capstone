from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dev.db"
    max_matches: int = 100

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
