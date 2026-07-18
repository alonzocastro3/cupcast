from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://cupcast:cupcast@localhost:5432/cupcast"
    redis_url: str = "redis://localhost:6379"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Football data provider
    football_api_key: str | None = None
    football_api_base_url: str = "https://api.football-data.org"
    football_tournament_id: str = "WC"
    football_api_timeout: float = 10.0
    football_api_max_retries: int = 3

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v  # type: ignore[return-value]


settings = Settings()
