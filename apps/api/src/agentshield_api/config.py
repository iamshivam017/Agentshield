from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://agentshield:agentshield@localhost:5432/agentshield"
    db_pool_size: int = 5
    db_max_overflow: int = 10


settings = Settings()
