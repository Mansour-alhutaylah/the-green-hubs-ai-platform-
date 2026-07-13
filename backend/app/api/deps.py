"""Shared FastAPI dependency providers.

This is the single seam where concrete infrastructure gets bound to the
abstractions that routers/services depend on -- idiomatic FastAPI
``Depends``-based DI, chosen over a separate IoC container library since it
fully satisfies the project's Dependency Injection requirement without extra
machinery. Future tasks add further per-entity providers here following the
same shape as ``get_document_repository``.
"""

from functools import lru_cache
from typing import AsyncIterator
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, ProfileNotProvisionedError
from app.domain.entities.user import User
from app.domain.processing_unit_of_work import IProcessingUnitOfWork
from app.domain.repositories.document import IDocumentRepository
from app.domain.repositories.document_chunk import IDocumentChunkRepository
from app.domain.repositories.engagement import IEngagementRepository
from app.domain.repositories.extracted_text import IExtractedTextRepository
from app.domain.repositories.organization import IOrganizationRepository
from app.domain.repositories.user import IUserRepository
from app.domain.storage.document_storage import IDocumentStorage
from app.infrastructure.db.session import get_db as _get_db
from app.infrastructure.processing_unit_of_work import SQLAlchemyProcessingUnitOfWork
from app.infrastructure.repositories.document import SQLAlchemyDocumentRepository
from app.infrastructure.repositories.document_chunk import SQLAlchemyDocumentChunkRepository
from app.infrastructure.repositories.engagement import SQLAlchemyEngagementRepository
from app.infrastructure.repositories.extracted_text import SQLAlchemyExtractedTextRepository
from app.infrastructure.repositories.organization import SQLAlchemyOrganizationRepository
from app.infrastructure.repositories.user import SQLAlchemyUserRepository
from app.infrastructure.security.supabase_jwt import (
    SupabaseJWTVerifier,
    build_verifier_from_settings,
)
from app.infrastructure.storage.supabase_document_storage import SupabaseDocumentStorage
from app.services.document_processing import DocumentProcessingService
from app.services.document_upload import DocumentUploadService
from app.services.engagement import EngagementService
from app.services.organization import OrganizationService

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
