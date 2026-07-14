"""Tenant-safe RAG + structured sustainability analysis use case.

Orchestrates, per request: tenant/document/engagement authorization
(mirroring ``VectorRetrievalService``'s own checks, duplicated here
because ``engagement_id`` must be known *before* the idempotency claim,
which happens before retrieval -- the same accepted duplication
``EmbeddingGenerationService`` already carries relative to
``DocumentProcessingService``), tenant-safe idempotent claim/retry/
reclaim (Mandatory Correction 1), tenant-scoped retrieval via the
existing ``VectorRetrievalService``, server-controlled source-key
mapping and citation persistence (Mandatory Correction 2), and final
response assembly.

Transaction/lifecycle boundary: ``claim_or_get``/``retry_failed``/
``reclaim_stale`` each commit immediately (see
``IAnalysisRunRepository``), so the claim is durable before any network
call is made. Retrieval and the external LLM call happen with no open
transaction. ``add_citations``/``mark_completed``/``mark_failed``/
``mark_insufficient_evidence`` are separate, immediately-committed
writes made only after the external call has already returned -- no
database transaction is ever held open across the LLM call.

No queue or worker exists yet (out of scope this sprint): every request
processes synchronously within the API call. Stale-reclaim exists for
the case where a *previous* request's process died mid-flight, leaving
a PROCESSING row a later, identically-hashed request can safely resume.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Sequence
from uuid import UUID

from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.domain.entities.analysis_run import AnalysisRun
from app.domain.entities.analysis_source_reference import AnalysisSourceReference
from app.domain.entities.user import User
from app.domain.entities.vector_search_result import VectorSearchResult
from app.domain.llm_gateway import LLMGateway, LLMGatewayError
from app.domain.repositories.analysis_run import IAnalysisRunRepository, NewCitation
from app.domain.repositories.document import IDocumentRepository
from app.domain.repositories.engagement import IEngagementRepository
from app.services.analysis.prompts import SYSTEM_PROMPT, build_user_prompt
from app.services.analysis.request_hash import compute_request_hash, normalize_query_text
from app.services.analysis.structured_output import StructuredAnalysisResult
from app.services.vector_retrieval import VectorRetrievalService

_ALLOWED_ANALYSIS_TYPES = frozenset({"sustainability_summary"})
_MAX_QUERY_TEXT_CHARS = 2000
_MAX_QUOTED_SNIPPET_CHARS = 2000
_EVIDENCE_FIELDS = ("reported_metrics", "key_findings", "recommendations")

_SAFE_LLM_ERROR_MESSAGES = {
    "LLMAuthenticationError": "Analysis provider authentication failed",
    "LLMProviderTimeoutError": "Analysis provider timed out",
    "LLMProviderUnavailableError": "Analysis provider unavailable",
    "LLMMalformedResponseError": "Analysis provider returned an unexpected response",
    "LLMValidationError": "Analysis request was invalid",
}


def _safe_llm_error_message(exc: LLMGatewayError) -> str:
    return _SAFE_LLM_ERROR_MESSAGES.get(type(exc).__name__, "Analysis generation failed")


def _remap_source_keys_to_citation_ids(
    structured_output: dict, citation_by_order: dict[int, AnalysisSourceReference]
) -> dict:
    result = dict(structured_output)
    for field_name in _EVIDENCE_FIELDS:
        items = result.get(field_name)
        if not isinstance(items, list):
            continue
        remapped: list[object] = []
        for item in items:
            if not isinstance(item, dict):
                remapped.append(item)
                continue
            new_item = dict(item)
            source_keys = new_item.pop("source_keys", [])
            citation_ids: list[str] = []
            for key in source_keys:
                try:
                    order = int(key.split("_")[1])
                except (IndexError, ValueError):
                    continue
                citation = citation_by_order.get(order)
                if citation is not None:
                    citation_ids.append(str(citation.id))
            new_item["citation_ids"] = citation_ids
            remapped.append(new_item)
        result[field_name] = remapped
    return result


@dataclass(frozen=True)
class CitationView:
    id: UUID
    document_id: UUID
    chunk_index: int
    char_start: int
    char_end: int
    quoted_snippet: str
    citation_order: int
    relevance_score: Decimal


@dataclass(frozen=True)
class AnalysisResultView:
    analysis_run_id: UUID
    organization_id: UUID
    engagement_id: UUID
    document_id: UUID | None
    status: str
    analysis_type: str
    structured_output: dict | None
    insufficient_evidence_reason: str | None
    error_message: str | None
    citations: Sequence[CitationView] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None


class RagAnalysisService:
    def __init__(
        self,
        analysis_run_repository: IAnalysisRunRepository,
        document_repository: IDocumentRepository,
        engagement_repository: IEngagementRepository,
        vector_retrieval_service: VectorRetrievalService,
        llm_gateway: LLMGateway,
        *,
        provider: str,
        model: str,
        prompt_template_version: str,
        output_schema_version: str,
        temperature: Decimal,
        retrieval_top_k: int,
        embedding_provider: str,
        embedding_model: str,
        embedding_model_version: str,
        minimum_relevance_score: Decimal,
        stale_after_seconds: int,
    ) -> None:
        self._analysis_run_repository = analysis_run_repository
        self._document_repository = document_repository
        self._engagement_repository = engagement_repository
        self._vector_retrieval_service = vector_retrieval_service
        self._llm_gateway = llm_gateway
        self._provider = provider
        self._model = model
        self._prompt_template_version = prompt_template_version
        self._output_schema_version = output_schema_version
        self._temperature = temperature
        self._retrieval_top_k = retrieval_top_k
        self._embedding_provider = embedding_provider
        self._embedding_model = embedding_model
        self._embedding_model_version = embedding_model_version
        self._minimum_relevance_score = minimum_relevance_score
        self._stale_after_seconds = stale_after_seconds

    async def analyze_document(
        self, current_user: User, document_id: UUID, *, analysis_type: str, query_text: str
    ) -> AnalysisResultView:
        if current_user.organization_id is None:
            raise AuthorizationError("User has no organization")
        organization_id = current_user.organization_id

        document = await self._document_repository.get(document_id)
        if document is None:
            raise NotFoundError(f"Document {document_id} not found")
        engagement = await self._engagement_repository.get(document.engagement_id)
        if engagement is None or engagement.organization_id != organization_id:
            raise NotFoundError(f"Document {document_id} not found")
        assert engagement.id is not None

        return await self._run(
            current_user,
            organization_id=organization_id,
            engagement_id=engagement.id,
            document_id=document_id,
            analysis_type=analysis_type,
            query_text=query_text,
        )

    async def analyze_engagement(
        self, current_user: User, engagement_id: UUID, *, analysis_type: str, query_text: str
    ) -> AnalysisResultView:
        if current_user.organization_id is None:
            raise AuthorizationError("User has no organization")
        organization_id = current_user.organization_id

        engagement = await self._engagement_repository.get(engagement_id)
        if engagement is None or engagement.organization_id != organization_id:
            raise NotFoundError(f"Engagement {engagement_id} not found")

        return await self._run(
            current_user,
            organization_id=organization_id,
            engagement_id=engagement_id,
            document_id=None,
            analysis_type=analysis_type,
            query_text=query_text,
        )

    async def get_run(self, current_user: User, analysis_run_id: UUID) -> AnalysisResultView:
        if current_user.organization_id is None:
            raise AuthorizationError("User has no organization")
        run = await self._analysis_run_repository.get_by_id(
            analysis_run_id, organization_id=current_user.organization_id
        )
        if run is None:
            raise NotFoundError(f"Analysis run {analysis_run_id} not found")
        return await self._to_view(run)

    async def _run(
        self,
        current_user: User,
        *,
        organization_id: UUID,
        engagement_id: UUID,
        document_id: UUID | None,
        analysis_type: str,
        query_text: str,
    ) -> AnalysisResultView:
        if analysis_type not in _ALLOWED_ANALYSIS_TYPES:
            raise ValidationError(
                f"analysis_type must be one of {sorted(_ALLOWED_ANALYSIS_TYPES)}"
            )
        normalized_query = normalize_query_text(query_text)
        if not normalized_query:
            raise ValidationError("query_text must not be empty")
        if len(normalized_query) > _MAX_QUERY_TEXT_CHARS:
            raise ValidationError(f"query_text must not exceed {_MAX_QUERY_TEXT_CHARS} characters")

        request_hash = compute_request_hash(
            organization_id=organization_id,
            engagement_id=engagement_id,
            document_id=document_id,
            analysis_type=analysis_type,
            query_text=normalized_query,
            provider=self._provider,
            model=self._model,
            prompt_template_version=self._prompt_template_version,
            output_schema_version=self._output_schema_version,
            temperature=self._temperature,
            retrieval_top_k=self._retrieval_top_k,
            embedding_provider=self._embedding_provider,
            embedding_model=self._embedding_model,
            embedding_model_version=self._embedding_model_version,
            minimum_relevance_score=self._minimum_relevance_score,
        )

        run, is_new = await self._analysis_run_repository.claim_or_get(
            organization_id=organization_id,
            engagement_id=engagement_id,
            document_id=document_id,
            requested_by_user_id=current_user.id,
            analysis_type=analysis_type,
            query_text=normalized_query,
            provider=self._provider,
            model=self._model,
            prompt_template_version=self._prompt_template_version,
            output_schema_version=self._output_schema_version,
            temperature=self._temperature,
            retrieval_top_k=self._retrieval_top_k,
            embedding_provider=self._embedding_provider,
            embedding_model=self._embedding_model,
            embedding_model_version=self._embedding_model_version,
            minimum_relevance_score=self._minimum_relevance_score,
            request_hash=request_hash,
        )

        if not is_new:
            assert run.id is not None
            claimed_id: UUID = run.id
            if run.status in ("COMPLETED", "INSUFFICIENT_EVIDENCE"):
                return await self._to_view(run)
            if run.status == "FAILED":
                retried = await self._analysis_run_repository.retry_failed(claimed_id)
                if retried is None:
                    return await self._to_view(await self._refetch(claimed_id, organization_id))
                run = retried
            elif run.status == "PROCESSING":
                reclaimed = await self._analysis_run_repository.reclaim_stale(
                    claimed_id, stale_after_seconds=self._stale_after_seconds
                )
                if reclaimed is None:
                    return await self._to_view(run)
                run = reclaimed

        return await self._process(
            current_user, run, organization_id=organization_id, query_text=normalized_query
        )

    async def _refetch(self, analysis_run_id: UUID, organization_id: UUID) -> AnalysisRun:
        refreshed = await self._analysis_run_repository.get_by_id(
            analysis_run_id, organization_id=organization_id
        )
        assert refreshed is not None
        return refreshed

    async def _process(
        self, current_user: User, run: AnalysisRun, *, organization_id: UUID, query_text: str
    ) -> AnalysisResultView:
        assert run.id is not None

        results = await self._vector_retrieval_service.search(
            current_user,
            query=query_text,
            top_k=self._retrieval_top_k,
            engagement_id=run.engagement_id,
            document_id=run.document_id,
        )
        relevant = [
            r for r in results if r.similarity_score >= float(self._minimum_relevance_score)
        ]

        if not relevant:
            await self._analysis_run_repository.mark_insufficient_evidence(
                run.id, reason="No sufficiently relevant content was found for this request."
            )
            return await self._to_view(await self._refetch(run.id, organization_id))

        source_map: dict[str, VectorSearchResult] = {
            f"SOURCE_{i}": result for i, result in enumerate(relevant, start=1)
        }

        user_prompt = build_user_prompt(
            analysis_type=run.analysis_type, query_text=query_text, source_map=source_map
        )

        def _validator(parsed: dict) -> bool:
            try:
                structured = StructuredAnalysisResult.model_validate(parsed)
            except PydanticValidationError:
                return False
            return structured.all_source_keys() <= source_map.keys()

        try:
            result = await self._llm_gateway.complete_structured(
                system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt, validator=_validator
            )
        except LLMGatewayError as exc:
            await self._analysis_run_repository.mark_failed(
                run.id, error_message=_safe_llm_error_message(exc)
            )
            return await self._to_view(await self._refetch(run.id, organization_id))

        try:
            structured = StructuredAnalysisResult.model_validate(result.parsed)
        except PydanticValidationError:
            await self._analysis_run_repository.mark_failed(
                run.id, error_message="Analysis provider returned a structurally invalid response"
            )
            return await self._to_view(await self._refetch(run.id, organization_id))

        referenced_keys = structured.all_source_keys()
        unknown_keys = referenced_keys - source_map.keys()
        if unknown_keys:
            await self._analysis_run_repository.mark_failed(
                run.id, error_message="Analysis provider cited sources outside the assembled context"
            )
            return await self._to_view(await self._refetch(run.id, organization_id))

        if structured.evidence_status == "insufficient":
            await self._analysis_run_repository.mark_insufficient_evidence(
                run.id,
                reason=structured.insufficient_evidence_reason
                or "The model determined available evidence was insufficient.",
            )
            return await self._to_view(await self._refetch(run.id, organization_id))

        new_citations = [
            NewCitation(
                chunk_id=source_map[key].chunk_id,
                citation_order=int(key.split("_")[1]),
                relevance_score=Decimal(str(source_map[key].similarity_score)),
                char_start=source_map[key].char_start,
                char_end=source_map[key].char_end,
                quoted_snippet=source_map[key].content[:_MAX_QUOTED_SNIPPET_CHARS],
            )
            for key in sorted(referenced_keys, key=lambda k: int(k.split("_")[1]))
        ]
        await self._analysis_run_repository.add_citations(
            run.id, organization_id=organization_id, citations=new_citations
        )
        await self._analysis_run_repository.mark_completed(
            run.id,
            structured_output=structured.model_dump(),
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            estimated_cost=None,
        )
        return await self._to_view(await self._refetch(run.id, organization_id))

    async def _to_view(self, run: AnalysisRun) -> AnalysisResultView:
        assert run.id is not None
        citations: Sequence[AnalysisSourceReference] = []
        if run.status == "COMPLETED":
            citations = await self._analysis_run_repository.get_citations(run.id)

        citation_by_order = {c.citation_order: c for c in citations}
        safe_structured = (
            _remap_source_keys_to_citation_ids(run.structured_output, citation_by_order)
            if run.structured_output is not None
            else None
        )

        return AnalysisResultView(
            analysis_run_id=run.id,
            organization_id=run.organization_id,
            engagement_id=run.engagement_id,
            document_id=run.document_id,
            status=run.status,
            analysis_type=run.analysis_type,
            structured_output=safe_structured,
            insufficient_evidence_reason=run.insufficient_evidence_reason,
            error_message=run.error_message,
            citations=[
                CitationView(
                    id=c.id,  # type: ignore[arg-type]
                    document_id=c.document_id,
                    chunk_index=c.chunk_index,
                    char_start=c.char_start,
                    char_end=c.char_end,
                    quoted_snippet=c.quoted_snippet,
                    citation_order=c.citation_order,
                    relevance_score=c.relevance_score,
                )
                for c in citations
            ],
            created_at=run.created_at,
            updated_at=run.updated_at,
            completed_at=run.completed_at,
        )
