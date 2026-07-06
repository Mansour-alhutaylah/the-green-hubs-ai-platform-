"""Application configuration.

Settings are loaded lazily via ``get_settings()`` rather than at import time,
so importing this module never raises even when ``.env`` is missing or
incomplete. This is a deliberate fix for a flaw found in the Hemaya reference
project's ``ai_config.py``, which raised at import time if ``OPENAI_API_KEY``
was absent -- that made the module impossible to import in tests without a
fully configured environment.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "development"
    debug: bool = True
    app_name: str = "the-green-hubs-ai-platform"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # Explicit allow-list, never "*" (Hemaya's main.py used allow_origins=["*"]).
    backend_cors_origins: list[str] = ["http://localhost:5173"]

    # Database (Supabase Postgres, pgvector-enabled). Required to boot the
    # DB-dependent parts of the app, but the app itself must still import
    # and start without it -- only /api/v1/health/db and Alembic need it set.
    database_url: Optional[str] = None

    # Supabase project details. Not consumed by any code yet (auth lands in
    # a later sprint) -- present now so the shape of configuration is settled.
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    supabase_jwt_secret: Optional[str] = None

    jwt_algorithm: str = "HS256"

    # AI/embeddings. Not consumed by any code yet -- infrastructure/ai/ is a
    # placeholder this sprint. No LangChain dependency is introduced yet.
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"


@lru_cache
def get_settings() -> Settings:
    return Settings()
