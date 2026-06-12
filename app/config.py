"""Application configuration using pydantic-settings (12-factor: config in env)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    app_name: str = "Day12 Production Agent"
    app_version: str = "1.0.0"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    redis_url: str = "redis://localhost:6379/0"
    agent_api_key: str = ""
    log_level: str = "INFO"
    rate_limit_per_minute: int = 10
    monthly_budget_usd: float = 10.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def ensure_production_config(self) -> None:
        """Fail fast on missing API key when running in production."""
        if self.environment == "production" and not self.agent_api_key:
            raise ValueError("AGENT_API_KEY must be set in production environment")


settings = Settings()
settings.ensure_production_config()
