from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "notifications"
    redis_url: str = "redis://localhost:6379/0"

    max_retries: int = 5
    retry_base_seconds: int = 2  # backoff: 2s, 4s, 8s, 16s, 32s
    webhook_timeout_seconds: float = 5.0
    log_level: str = "INFO"


settings = Settings()
