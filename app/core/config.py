from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Basics
    APP_NAME: str = "CampusFind API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # PostgreSQL Database Connection
    DATABASE_URL: str
    SYNC_DATABASE_URL: str | None = None

    @computed_field  # type: ignore[misc]
    @property
    def sync_database_url(self) -> str:
        """Derive a synchronous database URL for Alembic if not explicitly configured."""
        if self.SYNC_DATABASE_URL:
            return self.SYNC_DATABASE_URL
        return self.DATABASE_URL.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        )

    # JWT Authentication
    JWT_SECRET_KEY: str

    # CORS Origins
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v: bool | str) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            val = v.strip().lower()
            if val in ("true", "1", "yes", "y", "t", "on", "dev", "development"):
                return True
            if val in (
                "false",
                "0",
                "no",
                "n",
                "f",
                "off",
                "release",
                "prod",
                "production",
            ):
                return False
            raise ValueError(f"DEBUG không hợp lệ: {v}")
        raise ValueError(f"DEBUG không hợp lệ: {v}")

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
