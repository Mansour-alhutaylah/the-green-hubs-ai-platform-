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

    # Verified 2026-07-12 against the live JWKS + OIDC discovery endpoints
    # (see app/infrastructure/security/supabase_jwt.py's module docstring):
    # this project signs access tokens asymmetrically (ES256), so
    # `supabase_jwt_secret` above is not used for verification.
    # `"authenticated"` is Supabase's documented default audience for
    # signed-in user sessions; no evidence in this project contradicts it.
    supabase_jwt_audience: str = "authenticated"

    jwt_algorithm: str = "HS256"

    # Document Upload Foundation (app/services/document_upload.py). A
    # configurable default, not hardcoded domain policy -- see the Sprint
    # 3.4 plan's file-validation section.
    max_upload_size_bytes: int = 25 * 1024 * 1024  # 25 MB

    # Explicit, pre-provisioned bucket name. SupabaseDocumentStorage never
    # creates or alters it -- that is an infrastructure setup step outside
    # this codebase. Left unset by default (rather than defaulted to a real
    # name) so a missing configuration fails clearly, not silently.
    supabase_storage_bucket: Optional[str] = None

    # AI. `openai_model` is reserved for a future chat/completion use --
    # never read by embedding code, which uses its own dedicated settings
    # below so the two concerns can never be ambiguously conflated. No
    # LangChain dependency is introduced yet.
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"

    # Embeddings (Sprint 3.6A, Vector Retrieval Foundation). Dedicated
    # configuration, deliberately separate from `openai_model` above.
    # `embedding_dimension` must equal 1536 this sprint -- the
    # `document_chunk_embeddings.embedding` column is a fixed `vector(1536)`
    # (migration `3f3acc7fc556`); OpenAIEmbeddingProvider refuses to
    # construct with any other value. A future differently-sized model
    # requires a new migration or a separate table, not a config change.
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    embedding_provider_timeout_seconds: float = 30.0
    embedding_max_batch_size: int = 100
    embedding_max_input_characters: int = 8000
    embedding_processing_stale_after_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
