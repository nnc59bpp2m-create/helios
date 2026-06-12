from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List, Optional
import secrets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # App
    app_name: str = "helios"
    app_env: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "sqlite+apsw:///./helios.db"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Security
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # CORS
    cors_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "capacitor://localhost",
            "http://localhost",
            "https://localhost"
        ]
    )

    # Huami/Zepp API
    huami_app_id: str = ""
    huami_app_secret: str = ""

    # Google Calendar
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/calendar/callback/google"
    google_scopes: str = "https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/userinfo.email"

    # Microsoft Graph (Outlook/Graph)
    ms_graph_client_id: str = ""
    ms_graph_client_secret: str = ""
    ms_graph_redirect_uri: str = "http://localhost:8000/api/v1/calendar/callback/outlook"
    ms_graph_scopes: str = "https://graph.microsoft.com/Calendars.Read https://graph.microsoft.com/User.Read https://graph.microsoft.com/People.Read"

    # Ollama/Local LLM
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "nemotron3-ultra:latest"
    ollama_timeout: int = 120

    # Redis/Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # Encryption
    encryption_key: str = ""

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"


settings = Settings()