from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EXPENSES_", extra="ignore")

    app_name: str = "Expense Tracker"
    database_url: str = "sqlite:///./expenses.db"

    # Dev-only fallback. Always set EXPENSES_JWT_SECRET outside local development.
    jwt_secret: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60

    # A budget is flagged as "warning" once this share of it has been spent.
    budget_warning_ratio: float = 0.8


@lru_cache
def get_settings() -> Settings:
    return Settings()
