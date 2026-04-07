import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    app_name: str = "Multi-Agent Productivity Assistant"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/productivity_assistant"

    # OpenAI / LLM
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Google Calendar OAuth 2.0
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/callback"
    google_token_file: str = "token.json"
    google_credentials_file: str = "credentials.json"

    # Security
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
