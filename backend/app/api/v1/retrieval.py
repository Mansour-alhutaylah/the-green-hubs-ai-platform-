"""Tenant-safe vector retrieval endpoint.

``organization_id`` is never a request field -- the router passes only
``current_user`` to the service, which derives tenant scope from it. No
RAG, chat, or LLM completion here: this endpoint returns matched chunks
and similarity scores only.
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_vector_retrieval_service
from app.domain.entities.user import User
from app.schemas.retrieval import (
    RetrievalResultItem,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
)
from app.services.vector_retrieval import VectorRetrievalService

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post(
    "/search",
    response_model=RetrievalSearchResponse,
    responses={
        403: {"description": "User has no organization"},
        404: {"description": "Engagement or Document not found"},
        422: {"description": "Invalid query, top_k, or filter combination"},
    },
    summary="Search for semantically similar chunks within the caller's own organization",
)
async def search(
    payload: RetrievalSearchRequest,
    current_user: User = Depends(get_current_user),
    service: VectorRetrievalService = Depends(get_vector_retrieval_service),
) -> RetrievalSearchResponse:
    results = await service.search(
        current_user,
        query=payload.query,
        top_k=payload.top_k,
        engagement_id=payload.engagement_id,
        document_id=payload.document_id,
    )
    return RetrievalSearchResponse(
        items=[
            RetrievalResultItem(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                engagement_id=result.engagement_id,
                chunk_index=result.chunk_index,
                content=result.content,
                similarity_score=result.similarity_score,
                char_start=result.char_start,
                char_end=result.char_end,
            )
            for result in results
        ]
    )
