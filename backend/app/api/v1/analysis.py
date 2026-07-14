"""Tenant-safe RAG + structured sustainability analysis endpoints.

Exactly three endpoints, matching this sprint's approved scope: analyze
a single document, analyze an entire engagement, and poll a run's
current state by id. ``organization_id`` is never a request field --
always derived from ``current_user`` inside ``RagAnalysisService``. An
inaccessible or foreign-tenant resource raises ``NotFoundError`` from
the service, which the global ``AppError`` handler turns into an
indistinguishable 404 -- the same convention every other tenant-scoped
endpoint in this codebase follows.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_rag_analysis_service
from app.domain.entities.user import User
from app.schemas.analysis import AnalysisRunResponse, AnalyzeRequest, CitationOut
from app.services.analysis.rag_analysis import AnalysisResultView, RagAnalysisService

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _to_response(view: AnalysisResultView) -> AnalysisRunResponse:
    return AnalysisRunResponse(
        analysis_run_id=view.analysis_run_id,
        engagement_id=view.engagement_id,
        document_id=view.document_id,
        status=view.status,
        analysis_type=view.analysis_type,
        structured_output=view.structured_output,  # type: ignore[arg-type]
        insufficient_evidence_reason=view.insufficient_evidence_reason,
        error_message=view.error_message,
        citations=[
            CitationOut(
                id=c.id,
                document_id=c.document_id,
                chunk_index=c.chunk_index,
                char_start=c.char_start,
                char_end=c.char_end,
                quoted_snippet=c.quoted_snippet,
                citation_order=c.citation_order,
                relevance_score=float(c.relevance_score),
            )
            for c in view.citations
        ],
        created_at=view.created_at,
        updated_at=view.updated_at,
        completed_at=view.completed_at,
    )


@router.post(
    "/documents/{document_id}/analyze",
    response_model=AnalysisRunResponse,
    responses={
        403: {"description": "User has no organization"},
        404: {"description": "Document not found"},
        422: {"description": "Invalid analysis_type or query_text"},
    },
    summary="Run (or idempotently re-fetch) a tenant-safe RAG analysis scoped to one document",
)
async def analyze_document(
    document_id: UUID,
    payload: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    service: RagAnalysisService = Depends(get_rag_analysis_service),
) -> AnalysisRunResponse:
    view = await service.analyze_document(
        current_user,
        document_id,
        analysis_type=payload.analysis_type,
        query_text=payload.query_text,
    )
    return _to_response(view)


@router.post(
    "/engagements/{engagement_id}/analyze",
    response_model=AnalysisRunResponse,
    responses={
        403: {"description": "User has no organization"},
        404: {"description": "Engagement not found"},
        422: {"description": "Invalid analysis_type or query_text"},
    },
    summary="Run (or idempotently re-fetch) a tenant-safe RAG analysis scoped to one engagement",
)
async def analyze_engagement(
    engagement_id: UUID,
    payload: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    service: RagAnalysisService = Depends(get_rag_analysis_service),
) -> AnalysisRunResponse:
    view = await service.analyze_engagement(
        current_user,
        engagement_id,
        analysis_type=payload.analysis_type,
        query_text=payload.query_text,
    )
    return _to_response(view)


@router.get(
    "/runs/{analysis_run_id}",
    response_model=AnalysisRunResponse,
    responses={
        403: {"description": "User has no organization"},
        404: {"description": "Analysis run not found"},
    },
    summary="Fetch the current state of a previously requested analysis run",
)
async def get_analysis_run(
    analysis_run_id: UUID,
    current_user: User = Depends(get_current_user),
    service: RagAnalysisService = Depends(get_rag_analysis_service),
) -> AnalysisRunResponse:
    view = await service.get_run(current_user, analysis_run_id)
    return _to_response(view)
