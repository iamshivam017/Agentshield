from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://agentshield:agentshield@localhost:5432/agentshield"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    transaction_limit_default: str = "10000.00"
    daily_limit_default: str = "50000.00"
    verification_threshold: str = "0.25"
    agent_api_key: str | None = None
    require_agent_auth: bool = False
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60


settings = Settings()
