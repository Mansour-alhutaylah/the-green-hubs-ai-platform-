"""Shared FastAPI dependency providers.

This is the single seam where concrete infrastructure gets bound to the
abstractions that routers/services depend on -- idiomatic FastAPI
``Depends``-based DI, chosen over a separate IoC container library since it
fully satisfies the project's Dependency Injection requirement without extra
machinery. Future tasks add further per-entity providers here following the
same shape as ``get_document_repository``.
"""

from decimal import Decimal
from functools import lru_cache
from typing import AsyncIterator
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, ProfileNotProvisionedError
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
from app.services.analysis.rag_analysis import RagAnalysisService
from app.services.document_processing import DocumentProcessingService
from app.services.document_read import DocumentReadService
from app.services.document_upload import DocumentUploadService
from app.services.embedding_generation import EmbeddingGenerationService
from app.services.engagement import EngagementService
from app.services.organization import OrganizationService
from app.services.vector_retrieval import VectorRetrievalService

_EMBEDDING_PROVIDER_NAME = "openai"
_EMBEDDING_MODEL_VERSION = ""
_LLM_PROVIDER_NAME = "openai"

_bearer_scheme = HTTPBearer(auto_error=False)


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
    user = await repository.get(identity)
    if user is None:
        raise ProfileNotProvisionedError("No application profile found for this account")
    return user


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
    engagement_repository: IEngagementRepository = Depends(get_engagement_repository),
    extracted_text_repository: IExtractedTextRepository = Depends(get_extracted_text_repository),
    chunk_repository: IDocumentChunkRepository = Depends(get_document_chunk_repository),
    storage: IDocumentStorage = Depends(get_document_storage),
    unit_of_work: IProcessingUnitOfWork = Depends(get_processing_unit_of_work),
) -> DocumentProcessingService:
    return DocumentProcessingService(
        document_repository,
        engagement_repository,
        extracted_text_repository,
        chunk_repository,
        storage,
        unit_of_work,
    )


def get_document_chunk_embedding_repository(
    session: AsyncSession = Depends(get_db),
) -> IDocumentChunkEmbeddingRepository:
    return SQLAlchemyDocumentChunkEmbeddingRepository(session)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    return OpenAIEmbeddingProvider(get_settings())


def get_embedding_generation_service(
    document_repository: IDocumentRepository = Depends(get_document_repository),
    engagement_repository: IEngagementRepository = Depends(get_engagement_repository),
    chunk_repository: IDocumentChunkRepository = Depends(get_document_chunk_repository),
    embedding_repository: IDocumentChunkEmbeddingRepository = Depends(
        get_document_chunk_embedding_repository
    ),
    provider: EmbeddingProvider = Depends(get_embedding_provider),
    settings: Settings = Depends(get_app_settings),
) -> EmbeddingGenerationService:
    return EmbeddingGenerationService(
        document_repository,
        engagement_repository,
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
