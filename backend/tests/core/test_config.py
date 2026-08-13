"""Unit tests for ``resolve_ai_credentials`` -- the shared logic that
decides whether ``OpenAIEmbeddingProvider`` and ``OpenAILLMGateway`` talk
to direct OpenAI or an OpenAI-compatible gateway such as OpenRouter.

Every ``Settings(...)`` call below pins every field ``resolve_ai_credentials``
reads (``openai_api_key``, ``openai_base_url``, ``openrouter_api_key``),
even where a default would otherwise apply -- ``Settings`` loads a real
local ``.env`` by default, and this developer's has live
``OPENROUTER_API_KEY``/``OPENAI_BASE_URL`` values that must never leak into
these results.
"""

from app.core.config import Settings, resolve_ai_credentials

_DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


def test_direct_openai_key_resolves_to_openai_default_base_url() -> None:
    settings = Settings(
        openai_api_key="direct-key",
        openai_base_url=_DEFAULT_OPENAI_BASE_URL,
        openrouter_api_key=None,
    )

    api_key, base_url = resolve_ai_credentials(settings)

    assert api_key == "direct-key"
    assert base_url == _DEFAULT_OPENAI_BASE_URL


def test_openrouter_key_resolves_when_openai_key_absent() -> None:
    settings = Settings(
        openai_api_key=None, openai_base_url=_DEFAULT_OPENAI_BASE_URL, openrouter_api_key="or-key"
    )

    api_key, base_url = resolve_ai_credentials(settings)

    assert api_key == "or-key"
    assert base_url == "https://openrouter.ai/api/v1"


def test_direct_openai_key_takes_precedence_when_both_are_set() -> None:
    settings = Settings(
        openai_api_key="direct-key",
        openai_base_url=_DEFAULT_OPENAI_BASE_URL,
        openrouter_api_key="or-key",
    )

    api_key, base_url = resolve_ai_credentials(settings)

    assert api_key == "direct-key"
    assert base_url == _DEFAULT_OPENAI_BASE_URL


def test_explicit_base_url_override_is_respected_for_direct_openai() -> None:
    settings = Settings(
        openai_api_key="direct-key",
        openai_base_url="https://custom.example.com/v1",
        openrouter_api_key=None,
    )

    api_key, base_url = resolve_ai_credentials(settings)

    assert api_key == "direct-key"
    assert base_url == "https://custom.example.com/v1"


def test_no_credentials_returns_none_api_key_and_default_base_url() -> None:
    settings = Settings(
        openai_api_key=None, openai_base_url=_DEFAULT_OPENAI_BASE_URL, openrouter_api_key=None
    )

    api_key, base_url = resolve_ai_credentials(settings)

    assert api_key is None
    assert base_url == _DEFAULT_OPENAI_BASE_URL


def test_embedding_dimension_default_is_1536() -> None:
    # Inspects the declared field default directly (not an instantiated
    # Settings()) so this assertion can't be masked by a real .env file
    # setting EMBEDDING_DIMENSION during a local test run.
    assert Settings.model_fields["embedding_dimension"].default == 1536


# ---------------------------------------------------------------------------
# AIOS orchestration settings (Gate 3)
# ---------------------------------------------------------------------------


def test_aios_is_disabled_by_default() -> None:
    """A deployment that has not been configured for orchestration must
    not attempt to dispatch. Inspects the declared default so a local
    .env cannot mask it."""

    assert Settings.model_fields["aios_enabled"].default is False


def test_the_aios_base_url_has_no_default() -> None:
    """Left unset so a missing configuration fails clearly, rather than
    silently targeting somewhere plausible."""

    assert Settings.model_fields["aios_n8n_base_url"].default is None


def test_the_aios_clock_skew_default_is_the_specified_five_minutes() -> None:
    assert Settings.model_fields["aios_max_clock_skew_seconds"].default == 300


def test_the_aios_payload_ceiling_is_bounded() -> None:
    assert Settings.model_fields["aios_max_payload_bytes"].default == 64 * 1024


def test_the_aios_timeouts_are_bounded_and_connect_is_shorter() -> None:
    connect = Settings.model_fields["aios_connect_timeout_seconds"].default
    total = Settings.model_fields["aios_request_timeout_seconds"].default
    assert 0 < connect <= total <= 30


def test_no_signing_key_is_configured_by_default() -> None:
    """Secrets are supplied by the platform secret store, never by a
    default in source."""

    assert Settings.model_fields["aios_signing_keys"].default == {}
    assert Settings.model_fields["aios_active_key_id"].default is None
