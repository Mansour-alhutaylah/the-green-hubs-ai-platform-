"""Shared FastAPI dependency providers.

This is the single seam where concrete infrastructure gets bound to the
abstractions that routers/services depend on -- idiomatic FastAPI
``Depends``-based DI, chosen over a separate IoC container library since it
fully satisfies the project's Dependency Injection requirement without extra
machinery. Future tasks add further per-entity providers here following the
same shape as ``get_document_repository``.
"""

import logging
from decimal import Decimal
from functools import lru_cache
from typing import AsyncIterator, Awaitable, Callable
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    AIOSNotConfiguredError,
    AuthenticationError,
    AuthorizationError,
    PayloadTooLargeError,
    ProfileNotProvisionedError,
)
from app.core.request_context import enrich_request_context
from app.domain.aios.client import AIOSClient
from app.domain.aios.contracts import AIOSErrorCategory, safe_message_for
from app.domain.security import Permission, has_permission, resolve_trusted_role
from app.domain.embedding_provider import EmbeddingProvider
from app.domain.entities.user import User
from app.domain.llm_gateway import LLMGateway
from app.domain.processing_unit_of_work import IProcessingUnitOfWork
from app.domain.repositories.analysis_run import IAnalysisRunRepository
from app.domain.repositories.document import IDocumentRepository
from app.domain.repositories.document_chunk import IDocumentChunkRepository
from app.domain.repositories.document_chunk_embedding import IDocumentChunkEmbeddingRepository
from app.domain.repositories.engagement import IEngagementRepository
from app.domain.repositories.extracted_text import IExtractedTextRepository
from app.domain.repositories.organization import IOrganizationRepository
from app.domain.repositories.user import IUserRepository
from app.domain.storage.document_storage import IDocumentStorage
from app.infrastructure.ai.openai_embedding_provider import OpenAIEmbeddingProvider
from app.infrastructure.ai.openai_llm_gateway import OpenAILLMGateway
from app.infrastructure.aios.internal_signature import SigningKeyRing, build_key_ring
from app.infrastructure.aios.n8n_client import N8NAIOSClient
from app.infrastructure.aios.rate_limit import FixedWindowRateLimiter
from app.infrastructure.db.session import get_db as _get_db
from app.infrastructure.processing_unit_of_work import SQLAlchemyProcessingUnitOfWork
from app.infrastructure.repositories.analysis_run import SQLAlchemyAnalysisRunRepository
from app.infrastructure.repositories.document import SQLAlchemyDocumentRepository
from app.infrastructure.repositories.document_chunk import SQLAlchemyDocumentChunkRepository
from app.infrastructure.repositories.document_chunk_embedding import (
    SQLAlchemyDocumentChunkEmbeddingRepository,
)
from app.infrastructure.repositories.engagement import SQLAlchemyEngagementRepository
from app.infrastructure.repositories.extracted_text import SQLAlchemyExtractedTextRepository
from app.infrastructure.repositories.organization import SQLAlchemyOrganizationRepository
from app.infrastructure.repositories.user import SQLAlchemyUserRepository
from app.infrastructure.security.supabase_jwt import (
    SupabaseJWTVerifier,
    build_verifier_from_settings,
)
from app.infrastructure.storage.supabase_document_storage import SupabaseDocumentStorage
from app.services.aios.health_check import HealthCheckService
from app.services.aios.request_verification import RequestVerificationService
from app.services.analysis.rag_analysis import RagAnalysisService
from app.services.document_processing import DocumentProcessingService
from app.services.document_read import DocumentReadService
from app.services.document_upload import DocumentUploadService
from app.services.embedding_generation import EmbeddingGenerationService
from app.services.engagement import EngagementService
from app.services.evidence_review import EvidenceReviewService
from app.services.organization import OrganizationService
from app.services.vector_retrieval import VectorRetrievalService

_EMBEDDING_PROVIDER_NAME = "openai"
_EMBEDDING_MODEL_VERSION = ""
_LLM_PROVIDER_NAME = "openai"

_bearer_scheme = HTTPBearer(auto_error=False)

_authorization_logger = logging.getLogger("app.authorization")

# Deliberately generic: a denied caller learns that they may not perform the
# action, never which permission was required nor how roles map to it.
_PERMISSION_DENIED_DETAIL = "You do not have permission to perform this action."


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in _get_db():
        yield session


def get_app_settings() -> Settings:
    return get_settings()


def get_document_repository(
    session: AsyncSession = Depends(get_db),
) -> IDocumentRepository:
    return SQLAlchemyDocumentRepository(session)


def get_organization_repository(
    session: AsyncSession = Depends(get_db),
) -> IOrganizationRepository:
    return SQLAlchemyOrganizationRepository(session)


def get_organization_service(
    repository: IOrganizationRepository = Depends(get_organization_repository),
) -> OrganizationService:
    return OrganizationService(repository)


def get_engagement_repository(
    session: AsyncSession = Depends(get_db),
) -> IEngagementRepository:
    return SQLAlchemyEngagementRepository(session)


def get_engagement_service(
    repository: IEngagementRepository = Depends(get_engagement_repository),
    organization_repository: IOrganizationRepository = Depends(get_organization_repository),
) -> EngagementService:
    return EngagementService(repository, organization_repository)


@lru_cache
def get_supabase_jwt_verifier() -> SupabaseJWTVerifier:
    return build_verifier_from_settings(get_settings())


def get_user_repository(
    session: AsyncSession = Depends(get_db),
) -> IUserRepository:
    return SQLAlchemyUserRepository(session)


def get_current_auth_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    verifier: SupabaseJWTVerifier = Depends(get_supabase_jwt_verifier),
) -> UUID:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise AuthenticationError("Invalid authentication credentials")
    return verifier.verify(credentials.credentials)


async def get_current_user(
    identity: UUID = Depends(get_current_auth_identity),
    repository: IUserRepository = Depends(get_user_repository),
) -> User:
    # The authentication bootstrap, and the only unscoped tenant-owned read
    # in the application. `identity` is the `sub` of a JWT whose signature,
    # issuer and audience were already verified, so this can only return the
    # caller's own profile -- which is what establishes organization_id in
    # the first place. See IUserRepository for the full justification; the
    # architecture guard allows this one call site and no other.
    user = await repository.get_by_authenticated_id(identity)
    if user is None:
        raise ProfileNotProvisionedError("No application profile found for this account")
    enrich_request_context(user_id=user.id, organization_id=user.organization_id)
    return user


def require_permission(
    permission: Permission,
) -> Callable[[User], Awaitable[User]]:
    """Build a dependency that admits only callers holding ``permission``.

    Layers on top of ``get_current_user``, so authentication still runs
    first and still produces 401 on its own terms; this adds the separate
    authorization decision and produces 403. The authenticated ``User`` is
    returned unchanged, letting a route swap
    ``Depends(get_current_user)`` for ``Depends(require_permission(...))``
    without any other signature change -- existing tenant checks inside the
    services keep receiving the same ``current_user``.

    The decision reads only the server-resolved profile. Nothing from the
    request body, query string or headers participates, so no client value
    -- and no LLM output, document text or filename that later reaches a
    service -- can influence it.
    """

    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        role = resolve_trusted_role(current_user)
        if not has_permission(role, permission):
            # correlation_id/user_id/organization_id are attached to every
            # record by the logging factory; only safe fields are added here.
            _authorization_logger.warning(
                "Authorization denied permission=%s role=%s",
                permission.value,
                role.value if role is not None else "-",
            )
            raise AuthorizationError(_PERMISSION_DENIED_DETAIL)
        return current_user

    return dependency


@lru_cache
def get_document_storage() -> IDocumentStorage:
    return SupabaseDocumentStorage(get_settings())


def get_document_upload_service(
    document_repository: IDocumentRepository = Depends(get_document_repository),
    engagement_repository: IEngagementRepository = Depends(get_engagement_repository),
    storage: IDocumentStorage = Depends(get_document_storage),
    settings: Settings = Depends(get_app_settings),
) -> DocumentUploadService:
    return DocumentUploadService(
        document_repository,
        engagement_repository,
        storage,
        max_upload_size_bytes=settings.max_upload_size_bytes,
    )


def get_document_read_service(
    document_repository: IDocumentRepository = Depends(get_document_repository),
    engagement_repository: IEngagementRepository = Depends(get_engagement_repository),
    settings: Settings = Depends(get_app_settings),
) -> DocumentReadService:
    return DocumentReadService(
        document_repository,
        engagement_repository,
        embedding_provider=_EMBEDDING_PROVIDER_NAME,
        embedding_model=settings.embedding_model,
        embedding_model_version=_EMBEDDING_MODEL_VERSION,
    )


def get_extracted_text_repository(
    session: AsyncSession = Depends(get_db),
) -> IExtractedTextRepository:
    return SQLAlchemyExtractedTextRepository(session)


def get_document_chunk_repository(
    session: AsyncSession = Depends(get_db),
) -> IDocumentChunkRepository:
    return SQLAlchemyDocumentChunkRepository(session)


def get_processing_unit_of_work(
    session: AsyncSession = Depends(get_db),
) -> IProcessingUnitOfWork:
    return SQLAlchemyProcessingUnitOfWork(session)


def get_document_processing_service(
    document_repository: IDocumentRepository = Depends(get_document_repository),
    extracted_text_repository: IExtractedTextRepository = Depends(get_extracted_text_repository),
    chunk_repository: IDocumentChunkRepository = Depends(get_document_chunk_repository),
    storage: IDocumentStorage = Depends(get_document_storage),
    unit_of_work: IProcessingUnitOfWork = Depends(get_processing_unit_of_work),
) -> DocumentProcessingService:
    # No IEngagementRepository: MVP Slice 3 moved the document ->
    # engagement -> organization ownership chain into the document
    # repository's own tenant-scoped SQL.
    return DocumentProcessingService(
        document_repository,
        extracted_text_repository,
        chunk_repository,
        storage,
        unit_of_work,
    )


def get_evidence_review_service(
    document_repository: IDocumentRepository = Depends(get_document_repository),
) -> EvidenceReviewService:
    # One dependency only. The evidence commands need no storage, no
    # provider and no engagement repository: the document -> engagement
    # -> organization ownership chain, the expected-state guard and the
    # successor's tenancy all live inside the repository's own SQL.
    return EvidenceReviewService(document_repository)


def get_document_chunk_embedding_repository(
    session: AsyncSession = Depends(get_db),
) -> IDocumentChunkEmbeddingRepository:
    return SQLAlchemyDocumentChunkEmbeddingRepository(session)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    return OpenAIEmbeddingProvider(get_settings())


def get_embedding_generation_service(
    document_repository: IDocumentRepository = Depends(get_document_repository),
    chunk_repository: IDocumentChunkRepository = Depends(get_document_chunk_repository),
    embedding_repository: IDocumentChunkEmbeddingRepository = Depends(
        get_document_chunk_embedding_repository
    ),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
    settings: Settings = Depends(get_app_settings),
) -> EmbeddingGenerationService:
    # No IEngagementRepository -- see get_document_processing_service.
    return EmbeddingGenerationService(
        document_repository,
        chunk_repository,
        embedding_repository,
        provider,
        provider_name=_EMBEDDING_PROVIDER_NAME,
        model=settings.embedding_model,
        model_version=_EMBEDDING_MODEL_VERSION,
        embedding_dimension=settings.embedding_dimension,
        max_batch_size=settings.embedding_max_batch_size,
        stale_after_seconds=settings.embedding_processing_stale_after_seconds,
    )


def get_vector_retrieval_service(
    embedding_repository: IDocumentChunkEmbeddingRepository = Depends(
        get_document_chunk_embedding_repository
    ),
    engagement_repository: IEngagementRepository = Depends(get_engagement_repository),
    document_repository: IDocumentRepository = Depends(get_document_repository),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
    settings: Settings = Depends(get_app_settings),
) -> VectorRetrievalService:
    return VectorRetrievalService(
        embedding_repository,
        engagement_repository,
        document_repository,
        provider,
        provider_name=_EMBEDDING_PROVIDER_NAME,
        model=settings.embedding_model,
        model_version=_EMBEDDING_MODEL_VERSION,
    )


def get_analysis_run_repository(
    session: AsyncSession = Depends(get_db),
) -> IAnalysisRunRepository:
    return SQLAlchemyAnalysisRunRepository(session)


@lru_cache
def get_llm_gateway() -> LLMGateway:
    return OpenAILLMGateway(get_settings())


async def read_bounded_body(request: Request, *, max_bytes: int) -> bytes:
    """Read a request body, refusing anything over ``max_bytes``.

    Shared by both AIOS routes so the ceiling is enforced identically on
    the product-facing route and on the internal verification endpoint.

    The declared ``Content-Length`` is checked *first*, so an oversized
    body is refused before it is materialised in memory. That header is
    client-supplied and therefore not trusted on its own -- the actual
    length is re-checked after reading, which is what a chunked request
    with no ``Content-Length`` falls through to. Neither check alone is
    sufficient: the first bounds the common case cheaply, the second is
    the one that cannot be lied to.
    """

    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > max_bytes:
                raise PayloadTooLargeError(
                    safe_message_for(AIOSErrorCategory.PAYLOAD_TOO_LARGE)
                )
        except ValueError:
            # A malformed Content-Length is not a size decision; fall
            # through to the authoritative post-read check.
            pass

    body = await request.body()
    if len(body) > max_bytes:
        raise PayloadTooLargeError(safe_message_for(AIOSErrorCategory.PAYLOAD_TOO_LARGE))
    return body


@lru_cache
def get_aios_key_ring() -> SigningKeyRing:
    """The configured signing key ring, or a clear failure.

    ``build_key_ring`` returns ``None`` when nothing is configured, so
    importing and booting the app without AIOS credentials stays possible
    -- the same deliberate choice ``get_settings()`` makes about a
    missing ``.env``. Reaching *this* provider means a route actually
    needs to sign or verify, and at that point an absent key ring is a
    real misconfiguration rather than a tolerable one.
    """

    settings = get_settings()
    key_ring = build_key_ring(settings.aios_signing_keys, settings.aios_active_key_id)
    if key_ring is None:
        raise AIOSNotConfiguredError(
            "The orchestration service is not configured on this deployment."
        )
    return key_ring


@lru_cache
def get_aios_client() -> AIOSClient:
    return N8NAIOSClient(get_settings(), get_aios_key_ring())


def get_health_check_service(
    settings: Settings = Depends(get_app_settings),
) -> HealthCheckService:
    # The kill switch is checked here rather than inside the service, so
    # a disabled deployment never constructs a client and never resolves
    # a key ring -- one of the four documented rollback steps.
    if not settings.aios_enabled:
        raise AIOSNotConfiguredError(
            "The orchestration service is not enabled on this deployment."
        )
    return HealthCheckService(get_aios_client())


def get_request_verification_service(
    settings: Settings = Depends(get_app_settings),
) -> RequestVerificationService:
    if not settings.aios_enabled:
        raise AIOSNotConfiguredError(
            "The orchestration service is not enabled on this deployment."
        )
    return RequestVerificationService(
        get_aios_key_ring(),
        max_clock_skew_seconds=settings.aios_max_clock_skew_seconds,
        max_body_bytes=settings.aios_max_payload_bytes,
    )


@lru_cache
def get_aios_verification_rate_limiter() -> FixedWindowRateLimiter:
    settings = get_settings()
    return FixedWindowRateLimiter(
        limit=settings.aios_verification_rate_limit,
        window_seconds=settings.aios_verification_rate_window_seconds,
    )


def get_rag_analysis_service(
    analysis_run_repository: IAnalysisRunRepository = Depends(get_analysis_run_repository),
    document_repository: IDocumentRepository = Depends(get_document_repository),
    engagement_repository: IEngagementRepository = Depends(get_engagement_repository),
    vector_retrieval_service: VectorRetrievalService = Depends(get_vector_retrieval_service),
    llm_gateway: LLMGateway = Depends(get_llm_gateway),
    settings: Settings = Depends(get_app_settings),
) -> RagAnalysisService:
    return RagAnalysisService(
        analysis_run_repository,
        document_repository,
        engagement_repository,
        vector_retrieval_service,
        llm_gateway,
        provider=_LLM_PROVIDER_NAME,
        model=settings.openai_model,
        prompt_template_version=settings.rag_prompt_template_version,
        output_schema_version=settings.rag_output_schema_version,
        temperature=Decimal(str(settings.llm_temperature)),
        retrieval_top_k=settings.rag_retrieval_top_k,
        embedding_provider=_EMBEDDING_PROVIDER_NAME,
        embedding_model=settings.embedding_model,
        embedding_model_version=_EMBEDDING_MODEL_VERSION,
        minimum_relevance_score=Decimal(str(settings.rag_minimum_relevance_score)),
        stale_after_seconds=settings.rag_processing_stale_after_seconds,
    )
