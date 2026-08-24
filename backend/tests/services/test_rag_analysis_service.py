"""Unit tests for ``RagAnalysisService`` -- business logic exercised
against in-memory fakes. No database, no network, no ``integration``
mark. Covers both mandatory corrections: tenant-safe idempotency
(Correction 1) and server-controlled citation source-key mapping
(Correction 2).
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence

import pytest

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.domain.embedding_provider import EmbeddingProvider, EmbeddingResult
from app.domain.entities.analysis_run import AnalysisRun
from app.domain.entities.analysis_source_reference import AnalysisSourceReference
from app.domain.entities.document import Document
from app.domain.entities.engagement import Engagement
from app.domain.entities.user import User
from app.domain.entities.vector_search_result import VectorSearchResult
from app.domain.llm_gateway import LLMGateway, LLMProviderUnavailableError, LLMStructuredResult
from app.domain.repositories.analysis_run import IAnalysisRunRepository, NewCitation
from app.domain.repositories.document import IDocumentRepository
from app.domain.repositories.document_chunk_embedding import IDocumentChunkEmbeddingRepository
from app.domain.repositories.engagement import IEngagementRepository
from app.services.analysis.rag_analysis import RagAnalysisService
from app.services.vector_retrieval import VectorRetrievalService

PROVIDER_NAME = "openai"
MODEL = "gpt-4o-mini"
EMBEDDING_PROVIDER_NAME = "openai"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_MODEL_VERSION = ""
DIMENSION = 8
MIN_RELEVANCE = Decimal("0.500")
STALE_AFTER_SECONDS = 300

VALID_STRUCTURED_OUTPUT = {
    "analysis_type": "sustainability_summary",
    "evidence_status": "sufficient",
    "insufficient_evidence_reason": None,
    "executive_summary": "Scope 1 emissions decreased year over year.",
    "reporting_period": "FY2025",
    "detected_topics": ["emissions"],
    "reported_metrics": [
        {
            "name": "Scope 1 emissions",
            "status": "stated",
            "value": "1000",
            "unit": "tCO2e",
            "period": "FY2025",
            "source_keys": ["SOURCE_1"],
        }
    ],
    "key_findings": [{"statement": "Emissions decreased.", "source_keys": ["SOURCE_1"]}],
    "recommendations": [{"statement": "Continue trend.", "source_keys": ["SOURCE_1"]}],
    "overall_confidence": 0.8,
}


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeDocumentRepository(IDocumentRepository):
    """Models the real ``documents -> engagements`` ownership join, so a
    foreign ``document_id`` genuinely resolves to nothing here too."""

    def __init__(self, engagements: "FakeEngagementRepository") -> None:
        self.rows: dict[uuid.UUID, Document] = {}
        self._engagements = engagements

    def seed(self, document: Document) -> None:
        self.rows[document.id] = document



    async def create(self, entity: Document) -> Document:
        raise NotImplementedError

    async def update(self, entity: Document) -> Document:
        raise NotImplementedError

    async def delete(self, entity: Document) -> None:
        raise NotImplementedError

    async def get_for_organization(
        self, document_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Document | None:
        document = self.rows.get(document_id)
        if document is None:
            return None
        engagement = self._engagements.rows.get(document.engagement_id)
        if engagement is None or engagement.organization_id != organization_id:
            return None
        return document

    async def get_by_engagement(
        self, engagement_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Sequence[Document]:
        return [d for d in self.rows.values() if d.engagement_id == engagement_id]

    async def update_status(
        self, document_id: uuid.UUID, status: str, *, organization_id: uuid.UUID
    ) -> Document:
        raise NotImplementedError

    async def begin_processing(
        self, document_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Document:
        raise NotImplementedError

    async def complete_processing(
        self, document_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Document:
        raise NotImplementedError

    async def get_read_model_for_organization(self, document_id: uuid.UUID, *, organization_id: uuid.UUID):
        raise NotImplementedError

    async def list_read_models_for_organization(self, *, organization_id: uuid.UUID, engagement_id=None, processing_status=None, limit: int, offset: int):
        raise NotImplementedError

    async def count_for_organization(self, *, organization_id: uuid.UUID, engagement_id=None, processing_status=None) -> int:
        raise NotImplementedError

    async def get_evidence_for_organization(self, document_id: uuid.UUID, *, organization_id: uuid.UUID):
        raise NotImplementedError

    async def transition_evidence(self, document_id: uuid.UUID, **kwargs):
        raise NotImplementedError


class FakeEngagementRepository(IEngagementRepository):
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, Engagement] = {}

    def seed(self, engagement: Engagement) -> None:
        assert engagement.id is not None
        self.rows[engagement.id] = engagement


    async def list(
        self, *, limit: int = 100, offset: int = 0, organization_id: uuid.UUID | None = None
    ) -> Sequence[Engagement]:
        return list(self.rows.values())

    async def count(self, *, organization_id: uuid.UUID) -> int:
        return len(self.rows)

    async def get_for_organization(
        self, entity_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Engagement | None:
        row = self.rows.get(entity_id)
        return row if row is not None and row.organization_id == organization_id else None

    async def update_for_organization(
        self, entity: Engagement, *, organization_id: uuid.UUID
    ) -> Engagement:
        raise NotImplementedError

    async def create(self, entity: Engagement) -> Engagement:
        raise NotImplementedError

    async def update(self, entity: Engagement) -> Engagement:
        raise NotImplementedError

    async def delete(self, entity: Engagement) -> None:
        raise NotImplementedError


class FakeDocumentChunkEmbeddingRepository(IDocumentChunkEmbeddingRepository):
    def __init__(self) -> None:
        self.results: list[VectorSearchResult] = []

    async def claim_new(self, *args: object, **kwargs: object) -> Sequence:  # type: ignore[type-arg]
        raise NotImplementedError

    async def get_existing(self, *args: object, **kwargs: object) -> Sequence:  # type: ignore[type-arg]
        raise NotImplementedError

    async def retry_failed(self, *args: object, **kwargs: object) -> Sequence:  # type: ignore[type-arg]
        raise NotImplementedError

    async def reclaim_stale(self, *args: object, **kwargs: object) -> Sequence:  # type: ignore[type-arg]
        raise NotImplementedError

    async def mark_completed(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError

    async def mark_failed(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError

    async def search(
        self,
        *,
        organization_id: uuid.UUID,
        provider: str,
        model: str,
        model_version: str,
        query_vector: Sequence[float],
        top_k: int,
        engagement_id: uuid.UUID | None = None,
        document_id: uuid.UUID | None = None,
    ) -> Sequence[VectorSearchResult]:
        return self.results

    async def delete(self, entity: object) -> None:
        raise NotImplementedError


class FakeEmbeddingProvider(EmbeddingProvider):
    async def embed_texts(self, texts: Sequence[str]) -> Sequence[EmbeddingResult]:
        return [EmbeddingResult(text=t, vector=[0.1] * DIMENSION, dimension=DIMENSION) for t in texts]


class FakeAnalysisRunRepository(IAnalysisRunRepository):
    def __init__(self) -> None:
        self.runs: dict[uuid.UUID, AnalysisRun] = {}
        self.citations: dict[uuid.UUID, list[AnalysisSourceReference]] = {}
        self.chunk_lineage: dict[uuid.UUID, tuple[uuid.UUID, uuid.UUID, uuid.UUID, int]] = {}

    def register_chunk(
        self,
        chunk_id: uuid.UUID,
        *,
        document_id: uuid.UUID,
        engagement_id: uuid.UUID,
        organization_id: uuid.UUID,
        chunk_index: int = 0,
    ) -> None:
        self.chunk_lineage[chunk_id] = (document_id, engagement_id, organization_id, chunk_index)

    def force_processing_started_at(self, analysis_run_id: uuid.UUID, when: datetime) -> None:
        self.runs[analysis_run_id].processing_started_at = when

    async def claim_or_get(
        self,
        *,
        organization_id: uuid.UUID,
        engagement_id: uuid.UUID,
        document_id: uuid.UUID | None,
        requested_by_user_id: uuid.UUID,
        analysis_type: str,
        query_text: str | None,
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
        request_hash: str,
    ) -> tuple[AnalysisRun, bool]:
        for run in self.runs.values():
            if run.organization_id == organization_id and run.request_hash == request_hash:
                return run, False
        now = datetime.now(timezone.utc)
        run_id = uuid.uuid4()
        run = AnalysisRun(
            id=run_id,
            organization_id=organization_id,
            engagement_id=engagement_id,
            document_id=document_id,
            requested_by_user_id=requested_by_user_id,
            analysis_type=analysis_type,
            query_text=query_text,
            provider=provider,
            model=model,
            prompt_template_version=prompt_template_version,
            output_schema_version=output_schema_version,
            temperature=temperature,
            retrieval_top_k=retrieval_top_k,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            embedding_model_version=embedding_model_version,
            minimum_relevance_score=minimum_relevance_score,
            request_hash=request_hash,
            status="PROCESSING",
            structured_output=None,
            error_message=None,
            insufficient_evidence_reason=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            estimated_cost=None,
            processing_started_at=now,
            attempt_count=1,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
        self.runs[run_id] = run
        self.citations[run_id] = []
        return run, True

    async def get_by_id(
        self, analysis_run_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> AnalysisRun | None:
        run = self.runs.get(analysis_run_id)
        if run is None or run.organization_id != organization_id:
            return None
        return run

    async def retry_failed(
        self, analysis_run_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> AnalysisRun | None:
        run = self.runs.get(analysis_run_id)
        if run is None or run.organization_id != organization_id or run.status != "FAILED":
            return None
        run.status = "PROCESSING"
        run.processing_started_at = datetime.now(timezone.utc)
        run.attempt_count += 1
        run.error_message = None
        run.insufficient_evidence_reason = None
        run.updated_at = datetime.now(timezone.utc)
        return run

    async def reclaim_stale(
        self, analysis_run_id: uuid.UUID, *, organization_id: uuid.UUID, stale_after_seconds: int
    ) -> AnalysisRun | None:
        run = self.runs.get(analysis_run_id)
        if run is None or run.organization_id != organization_id or run.status != "PROCESSING":
            return None
        assert run.processing_started_at is not None
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
        if run.processing_started_at >= cutoff:
            return None
        run.processing_started_at = datetime.now(timezone.utc)
        run.attempt_count += 1
        run.updated_at = datetime.now(timezone.utc)
        return run

    async def mark_completed(
        self,
        analysis_run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        structured_output: dict,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        total_tokens: int | None,
        estimated_cost: Decimal | None,
    ) -> None:
        run = self.runs[analysis_run_id]
        if run.organization_id != organization_id or run.status != "PROCESSING":
            return
        run.status = "COMPLETED"
        run.structured_output = structured_output
        run.error_message = None
        run.prompt_tokens = prompt_tokens
        run.completion_tokens = completion_tokens
        run.total_tokens = total_tokens
        run.estimated_cost = estimated_cost
        run.completed_at = datetime.now(timezone.utc)
        run.updated_at = datetime.now(timezone.utc)

    async def mark_failed(
        self, analysis_run_id: uuid.UUID, *, organization_id: uuid.UUID, error_message: str
    ) -> None:
        run = self.runs[analysis_run_id]
        if run.organization_id != organization_id or run.status != "PROCESSING":
            return
        run.status = "FAILED"
        run.error_message = error_message
        run.structured_output = None
        run.updated_at = datetime.now(timezone.utc)

    async def mark_insufficient_evidence(
        self, analysis_run_id: uuid.UUID, *, organization_id: uuid.UUID, reason: str
    ) -> None:
        run = self.runs[analysis_run_id]
        if run.organization_id != organization_id or run.status != "PROCESSING":
            return
        run.status = "INSUFFICIENT_EVIDENCE"
        run.insufficient_evidence_reason = reason
        run.structured_output = None
        run.error_message = None
        run.completed_at = datetime.now(timezone.utc)
        run.updated_at = datetime.now(timezone.utc)

    async def add_citations(
        self,
        analysis_run_id: uuid.UUID,
        *,
        organization_id: uuid.UUID,
        citations: Sequence[NewCitation],
    ) -> Sequence[AnalysisSourceReference]:
        inserted: list[AnalysisSourceReference] = []
        for c in citations:
            document_id, engagement_id, chunk_org_id, chunk_index = self.chunk_lineage[c.chunk_id]
            if chunk_org_id != organization_id:
                continue
            ref = AnalysisSourceReference(
                id=uuid.uuid4(),
                analysis_run_id=analysis_run_id,
                chunk_id=c.chunk_id,
                document_id=document_id,
                engagement_id=engagement_id,
                organization_id=organization_id,
                chunk_index=chunk_index,
                char_start=c.char_start,
                char_end=c.char_end,
                quoted_snippet=c.quoted_snippet,
                citation_order=c.citation_order,
                relevance_score=c.relevance_score,
                created_at=datetime.now(timezone.utc),
            )
            self.citations.setdefault(analysis_run_id, []).append(ref)
            inserted.append(ref)
        return inserted

    async def get_citations(
        self, analysis_run_id: uuid.UUID, *, organization_id: uuid.UUID
    ) -> Sequence[AnalysisSourceReference]:
        return sorted(
            [
                c
                for c in self.citations.get(analysis_run_id, [])
                if c.organization_id == organization_id
            ],
            key=lambda c: c.citation_order,
        )

    async def delete(self, entity: AnalysisRun) -> None:
        if entity.id in self.runs:
            del self.runs[entity.id]


class FakeLLMGateway(LLMGateway):
    def __init__(self, responses: Sequence[dict | Exception]) -> None:
        self._responses = list(responses)
        self.call_count = 0
        self.captured_user_prompts: list[str] = []

    async def complete_structured(
        self, *, system_prompt: str, user_prompt: str, validator=None
    ) -> LLMStructuredResult:
        self.call_count += 1
        self.captured_user_prompts.append(user_prompt)
        if not self._responses:
            raise AssertionError("FakeLLMGateway ran out of queued responses")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMStructuredResult(
            raw_text=json.dumps(item),
            parsed=item,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            model=MODEL,
            finish_reason="stop",
        )


def _user(organization_id: uuid.UUID | None) -> User:
    return User(
        id=uuid.uuid4(),
        organization_id=organization_id,
        full_name="Test User",
        email="test@example.com",
        role=None,
        created_at=datetime.now(timezone.utc),
    )


def _search_result(
    *, chunk_id: uuid.UUID, document_id: uuid.UUID, engagement_id: uuid.UUID, score: float = 0.9
) -> VectorSearchResult:
    return VectorSearchResult(
        chunk_id=chunk_id,
        document_id=document_id,
        engagement_id=engagement_id,
        chunk_index=0,
        content="Scope 1 emissions decreased.",
        char_start=0,
        char_end=28,
        similarity_score=score,
    )


class Harness:
    def __init__(self) -> None:
        self.engagement_repository = FakeEngagementRepository()
        self.document_repository = FakeDocumentRepository(self.engagement_repository)
        self.embedding_repository = FakeDocumentChunkEmbeddingRepository()
        self.embedding_provider = FakeEmbeddingProvider()
        self.vector_retrieval_service = VectorRetrievalService(
            self.embedding_repository,
            self.engagement_repository,
            self.document_repository,
            self.embedding_provider,
            provider_name=EMBEDDING_PROVIDER_NAME,
            model=EMBEDDING_MODEL,
            model_version=EMBEDDING_MODEL_VERSION,
        )
        self.analysis_run_repository = FakeAnalysisRunRepository()
        self.llm_gateway_responses: list[dict | Exception] = []

    def build_service(self) -> tuple[RagAnalysisService, FakeLLMGateway]:
        gateway = FakeLLMGateway(self.llm_gateway_responses)
        service = RagAnalysisService(
            self.analysis_run_repository,
            self.document_repository,
            self.engagement_repository,
            self.vector_retrieval_service,
            gateway,
            provider=PROVIDER_NAME,
            model=MODEL,
            prompt_template_version="v1",
            output_schema_version="v1",
            temperature=Decimal("0.10"),
            retrieval_top_k=5,
            embedding_provider=EMBEDDING_PROVIDER_NAME,
            embedding_model=EMBEDDING_MODEL,
            embedding_model_version=EMBEDDING_MODEL_VERSION,
            minimum_relevance_score=MIN_RELEVANCE,
            stale_after_seconds=STALE_AFTER_SECONDS,
        )
        return service, gateway

    def seed_org(self) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
        """Seeds one organization/engagement/document/chunk. Returns
        (organization_id, engagement_id, document_id, chunk_id)."""
        organization_id = uuid.uuid4()
        engagement_id = uuid.uuid4()
        document_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        self.engagement_repository.seed(
            Engagement(
                id=engagement_id, organization_id=organization_id, title="Eng",
                status="planning", created_at=now,
            )
        )
        self.document_repository.seed(
            Document(
                id=document_id, filename="r.pdf", storage_path="x", processing_status="PROCESSED",
                engagement_id=engagement_id, created_at=now, updated_at=now,
            )
        )
        self.analysis_run_repository.register_chunk(
            chunk_id, document_id=document_id, engagement_id=engagement_id,
            organization_id=organization_id,
        )
        return organization_id, engagement_id, document_id, chunk_id


@pytest.fixture
def harness() -> Harness:
    return Harness()


# ---------------------------------------------------------------------------
# Tenant / request validation
# ---------------------------------------------------------------------------


async def test_null_organization_rejected_with_403(harness: Harness) -> None:
    service, _gateway = harness.build_service()
    user = _user(None)
    with pytest.raises(AuthorizationError):
        await service.analyze_document(
            user, uuid.uuid4(), analysis_type="sustainability_summary", query_text="q"
        )


async def test_missing_document_returns_404(harness: Harness) -> None:
    service, _gateway = harness.build_service()
    user = _user(uuid.uuid4())
    with pytest.raises(NotFoundError):
        await service.analyze_document(
            user, uuid.uuid4(), analysis_type="sustainability_summary", query_text="q"
        )


async def test_foreign_tenant_document_returns_404(harness: Harness) -> None:
    _org, _eng, document_id, _chunk = harness.seed_org()
    service, _gateway = harness.build_service()
    other_user = _user(uuid.uuid4())
    with pytest.raises(NotFoundError):
        await service.analyze_document(
            other_user, document_id, analysis_type="sustainability_summary", query_text="q"
        )


async def test_missing_engagement_returns_404(harness: Harness) -> None:
    service, _gateway = harness.build_service()
    user = _user(uuid.uuid4())
    with pytest.raises(NotFoundError):
        await service.analyze_engagement(
            user, uuid.uuid4(), analysis_type="sustainability_summary", query_text="q"
        )


async def test_foreign_tenant_engagement_returns_404(harness: Harness) -> None:
    organization_id, engagement_id, _doc, _chunk = harness.seed_org()
    service, _gateway = harness.build_service()
    other_user = _user(uuid.uuid4())
    with pytest.raises(NotFoundError):
        await service.analyze_engagement(
            other_user, engagement_id, analysis_type="sustainability_summary", query_text="q"
        )


async def test_invalid_analysis_type_rejected_with_422(harness: Harness) -> None:
    organization_id, engagement_id, _doc, _chunk = harness.seed_org()
    service, _gateway = harness.build_service()
    user = _user(organization_id)
    with pytest.raises(ValidationError):
        await service.analyze_engagement(
            user, engagement_id, analysis_type="not_a_real_type", query_text="q"
        )


async def test_blank_query_text_rejected_with_422(harness: Harness) -> None:
    organization_id, engagement_id, _doc, _chunk = harness.seed_org()
    service, _gateway = harness.build_service()
    user = _user(organization_id)
    with pytest.raises(ValidationError):
        await service.analyze_engagement(
            user, engagement_id, analysis_type="sustainability_summary", query_text="   "
        )


async def test_get_run_for_foreign_organization_returns_404(harness: Harness) -> None:
    organization_id, engagement_id, _doc, chunk_id = harness.seed_org()
    harness.embedding_repository.results = [
        _search_result(chunk_id=chunk_id, document_id=_doc, engagement_id=engagement_id)
    ]
    harness.llm_gateway_responses = [VALID_STRUCTURED_OUTPUT]
    service, _gateway = harness.build_service()
    user = _user(organization_id)
    view = await service.analyze_engagement(
        user, engagement_id, analysis_type="sustainability_summary", query_text="q"
    )

    other_user = _user(uuid.uuid4())
    with pytest.raises(NotFoundError):
        await service.get_run(other_user, view.analysis_run_id)


# ---------------------------------------------------------------------------
# No-evidence path -- never calls the LLM
# ---------------------------------------------------------------------------


async def test_no_retrieved_chunks_marks_insufficient_evidence_without_calling_llm(
    harness: Harness,
) -> None:
    organization_id, engagement_id, _doc, _chunk = harness.seed_org()
    harness.embedding_repository.results = []
    service, gateway = harness.build_service()
    user = _user(organization_id)

    view = await service.analyze_engagement(
        user, engagement_id, analysis_type="sustainability_summary", query_text="q"
    )

    assert view.status == "INSUFFICIENT_EVIDENCE"
    assert gateway.call_count == 0
    assert view.citations == []


async def test_below_threshold_chunks_marks_insufficient_evidence_without_calling_llm(
    harness: Harness,
) -> None:
    organization_id, engagement_id, document_id, chunk_id = harness.seed_org()
    harness.embedding_repository.results = [
        _search_result(
            chunk_id=chunk_id, document_id=document_id, engagement_id=engagement_id, score=0.1
        )
    ]
    service, gateway = harness.build_service()
    user = _user(organization_id)

    view = await service.analyze_engagement(
        user, engagement_id, analysis_type="sustainability_summary", query_text="q"
    )

    assert view.status == "INSUFFICIENT_EVIDENCE"
    assert gateway.call_count == 0


# ---------------------------------------------------------------------------
# Successful completion + citation persistence
# ---------------------------------------------------------------------------


async def test_successful_analysis_completes_and_persists_citation(harness: Harness) -> None:
    organization_id, engagement_id, document_id, chunk_id = harness.seed_org()
    harness.embedding_repository.results = [
        _search_result(chunk_id=chunk_id, document_id=document_id, engagement_id=engagement_id)
    ]
    harness.llm_gateway_responses = [VALID_STRUCTURED_OUTPUT]
    service, gateway = harness.build_service()
    user = _user(organization_id)

    view = await service.analyze_engagement(
        user, engagement_id, analysis_type="sustainability_summary", query_text="q"
    )

    assert view.status == "COMPLETED"
    assert gateway.call_count == 1
    assert len(view.citations) == 1
    assert view.citations[0].chunk_index == 0
    finding = view.structured_output["key_findings"][0]
    assert finding["citation_ids"] == [str(view.citations[0].id)]
    assert "source_keys" not in finding  # temporary key never leaks into the client response


async def test_duplicate_source_keys_normalized_to_single_citation(harness: Harness) -> None:
    organization_id, engagement_id, document_id, chunk_id = harness.seed_org()
    harness.embedding_repository.results = [
        _search_result(chunk_id=chunk_id, document_id=document_id, engagement_id=engagement_id)
    ]
    payload = dict(VALID_STRUCTURED_OUTPUT)
    payload["key_findings"] = [
        {"statement": "A", "source_keys": ["SOURCE_1"]},
        {"statement": "B", "source_keys": ["SOURCE_1"]},
    ]
    harness.llm_gateway_responses = [payload]
    service, _gateway = harness.build_service()
    user = _user(organization_id)

    view = await service.analyze_engagement(
        user, engagement_id, analysis_type="sustainability_summary", query_text="q"
    )

    assert view.status == "COMPLETED"
    assert len(view.citations) == 1


# ---------------------------------------------------------------------------
# Server-controlled citations (Mandatory Correction 2)
# ---------------------------------------------------------------------------


async def test_hallucinated_source_key_marks_run_failed(harness: Harness) -> None:
    organization_id, engagement_id, document_id, chunk_id = harness.seed_org()
    harness.embedding_repository.results = [
        _search_result(chunk_id=chunk_id, document_id=document_id, engagement_id=engagement_id)
    ]
    payload = dict(VALID_STRUCTURED_OUTPUT)
    payload["key_findings"] = [{"statement": "A", "source_keys": ["SOURCE_999"]}]
    harness.llm_gateway_responses = [payload]
    service, _gateway = harness.build_service()
    user = _user(organization_id)

    view = await service.analyze_engagement(
        user, engagement_id, analysis_type="sustainability_summary", query_text="q"
    )

    assert view.status == "FAILED"
    assert view.citations == []


async def test_source_key_outside_assembled_context_marks_run_failed(harness: Harness) -> None:
    organization_id, engagement_id, document_id, chunk_id = harness.seed_org()
    harness.embedding_repository.results = [
        _search_result(chunk_id=chunk_id, document_id=document_id, engagement_id=engagement_id)
    ]  # only SOURCE_1 is ever assembled
    payload = dict(VALID_STRUCTURED_OUTPUT)
    payload["key_findings"] = [{"statement": "A", "source_keys": ["SOURCE_2"]}]
    harness.llm_gateway_responses = [payload]
    service, _gateway = harness.build_service()
    user = _user(organization_id)

    view = await service.analyze_engagement(
        user, engagement_id, analysis_type="sustainability_summary", query_text="q"
    )

    assert view.status == "FAILED"
    assert view.citations == []


async def test_llm_evidence_status_insufficient_marks_run_insufficient_evidence(
    harness: Harness,
) -> None:
    organization_id, engagement_id, document_id, chunk_id = harness.seed_org()
    harness.embedding_repository.results = [
        _search_result(chunk_id=chunk_id, document_id=document_id, engagement_id=engagement_id)
    ]
    payload = dict(VALID_STRUCTURED_OUTPUT)
    payload["evidence_status"] = "insufficient"
    payload["insufficient_evidence_reason"] = "Not enough detail."
    payload["key_findings"] = []
    payload["reported_metrics"] = []
    payload["recommendations"] = []
    harness.llm_gateway_responses = [payload]
    service, gateway = harness.build_service()
    user = _user(organization_id)

    view = await service.analyze_engagement(
        user, engagement_id, analysis_type="sustainability_summary", query_text="q"
    )

    assert view.status == "INSUFFICIENT_EVIDENCE"
    assert view.insufficient_evidence_reason == "Not enough detail."
    assert gateway.call_count == 1
    assert view.citations == []


async def test_malformed_structured_output_marks_run_failed(harness: Harness) -> None:
    organization_id, engagement_id, document_id, chunk_id = harness.seed_org()
    harness.embedding_repository.results = [
        _search_result(chunk_id=chunk_id, document_id=document_id, engagement_id=engagement_id)
    ]
    harness.llm_gateway_responses = [{"not": "a valid structured analysis result"}]
    service, _gateway = harness.build_service()
    user = _user(organization_id)

    view = await service.analyze_engagement(
        user, engagement_id, analysis_type="sustainability_summary", query_text="q"
    )

    assert view.status == "FAILED"


async def test_llm_gateway_error_marks_run_failed_with_sanitized_message(
    harness: Harness,
) -> None:
    organization_id, engagement_id, document_id, chunk_id = harness.seed_org()
    harness.embedding_repository.results = [
        _search_result(chunk_id=chunk_id, document_id=document_id, engagement_id=engagement_id)
    ]
    harness.llm_gateway_responses = [LLMProviderUnavailableError("upstream said 503: <secret>")]
    service, _gateway = harness.build_service()
    user = _user(organization_id)

    view = await service.analyze_engagement(
        user, engagement_id, analysis_type="sustainability_summary", query_text="q"
    )

    assert view.status == "FAILED"
    assert view.error_message == "Analysis provider unavailable"
    assert "<secret>" not in (view.error_message or "")


# ---------------------------------------------------------------------------
# Mandatory Correction 1 -- tenant-safe idempotency
# ---------------------------------------------------------------------------


async def test_identical_request_in_same_organization_is_idempotent(harness: Harness) -> None:
    organization_id, engagement_id, document_id, chunk_id = harness.seed_org()
    harness.embedding_repository.results = [
        _search_result(chunk_id=chunk_id, document_id=document_id, engagement_id=engagement_id)
    ]
    harness.llm_gateway_responses = [VALID_STRUCTURED_OUTPUT]
    service, gateway = harness.build_service()
    user = _user(organization_id)

    first = await service.analyze_engagement(
        user, engagement_id, analysis_type="sustainability_summary", query_text="q"
    )
    second = await service.analyze_engagement(
        user, engagement_id, analysis_type="sustainability_summary", query_text="q"
    )

    assert first.analysis_run_id == second.analysis_run_id
    assert gateway.call_count == 1  # the LLM is never called twice for the same request


async def test_unchanged_document_revision_reuses_same_run(harness: Harness) -> None:
    organization_id, engagement_id, document_id, chunk_id = harness.seed_org()
    harness.embedding_repository.results = [
        _search_result(chunk_id=chunk_id, document_id=document_id, engagement_id=engagement_id)
    ]
    harness.llm_gateway_responses = [VALID_STRUCTURED_OUTPUT]
    service, gateway = harness.build_service()
    user = _user(organization_id)

    first = await service.analyze_document(
        user, document_id, analysis_type="sustainability_summary", query_text="q"
    )
    second = await service.analyze_document(
        user, document_id, analysis_type="sustainability_summary", query_text="q"
    )

    assert first.analysis_run_id == second.analysis_run_id
    assert len(harness.analysis_run_repository.runs) == 1
    assert gateway.call_count == 1


async def test_verified_document_revision_creates_run_after_insufficient_evidence(
    harness: Harness,
) -> None:
    organization_id, engagement_id, document_id, chunk_id = harness.seed_org()
    harness.llm_gateway_responses = [VALID_STRUCTURED_OUTPUT]
    service, gateway = harness.build_service()
    user = _user(organization_id)

    before_verification = await service.analyze_document(
        user, document_id, analysis_type="sustainability_summary", query_text="q"
    )
    assert before_verification.status == "INSUFFICIENT_EVIDENCE"

    document = harness.document_repository.rows[document_id]
    document.updated_at = document.updated_at + timedelta(seconds=1)
    harness.embedding_repository.results = [
        _search_result(chunk_id=chunk_id, document_id=document_id, engagement_id=engagement_id)
    ]
    after_verification = await service.analyze_document(
        user, document_id, analysis_type="sustainability_summary", query_text="q"
    )

    assert after_verification.status == "COMPLETED"
    assert after_verification.analysis_run_id != before_verification.analysis_run_id
    assert harness.analysis_run_repository.runs[before_verification.analysis_run_id].status == (
        "INSUFFICIENT_EVIDENCE"
    )
    assert len(harness.analysis_run_repository.runs) == 2
    assert gateway.call_count == 1


async def test_identical_request_in_different_organizations_creates_separate_runs() -> None:
    harness_a = Harness()
    org_a, eng_a, doc_a, chunk_a = harness_a.seed_org()
    harness_a.embedding_repository.results = [
        _search_result(chunk_id=chunk_a, document_id=doc_a, engagement_id=eng_a)
    ]
    harness_a.llm_gateway_responses = [VALID_STRUCTURED_OUTPUT]
    service_a, _gateway_a = harness_a.build_service()

    # A second, independent tenant issuing the byte-identical request (same
    # analysis_type/query_text/config) must never collide with tenant A.
    harness_b = Harness()
    org_b, eng_b, doc_b, chunk_b = harness_b.seed_org()
    harness_b.embedding_repository.results = [
        _search_result(chunk_id=chunk_b, document_id=doc_b, engagement_id=eng_b)
    ]
    harness_b.llm_gateway_responses = [VALID_STRUCTURED_OUTPUT]
    service_b, _gateway_b = harness_b.build_service()

    view_a = await service_a.analyze_engagement(
        _user(org_a), eng_a, analysis_type="sustainability_summary", query_text="identical query"
    )
    view_b = await service_b.analyze_engagement(
        _user(org_b), eng_b, analysis_type="sustainability_summary", query_text="identical query"
    )

    assert view_a.analysis_run_id != view_b.analysis_run_id


async def test_failed_run_is_retried_on_next_identical_request(harness: Harness) -> None:
    organization_id, engagement_id, document_id, chunk_id = harness.seed_org()
    harness.embedding_repository.results = [
        _search_result(chunk_id=chunk_id, document_id=document_id, engagement_id=engagement_id)
    ]
    harness.llm_gateway_responses = [
        LLMProviderUnavailableError("temporary failure"),
        VALID_STRUCTURED_OUTPUT,
    ]
    service, gateway = harness.build_service()
    user = _user(organization_id)

    first = await service.analyze_engagement(
        user, engagement_id, analysis_type="sustainability_summary", query_text="q"
    )
    assert first.status == "FAILED"

    second = await service.analyze_engagement(
        user, engagement_id, analysis_type="sustainability_summary", query_text="q"
    )

    assert second.status == "COMPLETED"
    assert second.analysis_run_id == first.analysis_run_id
    assert gateway.call_count == 2


async def test_stale_processing_run_is_reclaimed_and_reprocessed(harness: Harness) -> None:
    organization_id, engagement_id, document_id, chunk_id = harness.seed_org()
    harness.embedding_repository.results = [
        _search_result(chunk_id=chunk_id, document_id=document_id, engagement_id=engagement_id)
    ]
    user = _user(organization_id)

    # Simulate a first request whose process died mid-flight, leaving a
    # PROCESSING row well past the staleness threshold: seed the repository
    # directly via claim_or_get, using the same hash computation the service
    # itself will use for the real request below.
    from app.services.analysis.request_hash import compute_request_hash

    request_hash = compute_request_hash(
        organization_id=organization_id,
        engagement_id=engagement_id,
        document_id=None,
        evidence_revision=(
            f"{document_id}:{harness.document_repository.rows[document_id].updated_at.isoformat()}"
        ),
        analysis_type="sustainability_summary",
        query_text="q",
        provider=PROVIDER_NAME,
        model=MODEL,
        prompt_template_version="v1",
        output_schema_version="v1",
        temperature=Decimal("0.10"),
        retrieval_top_k=5,
        embedding_provider=EMBEDDING_PROVIDER_NAME,
        embedding_model=EMBEDDING_MODEL,
        embedding_model_version=EMBEDDING_MODEL_VERSION,
        minimum_relevance_score=MIN_RELEVANCE,
    )
    stale_run, _is_new = await harness.analysis_run_repository.claim_or_get(
        organization_id=organization_id,
        engagement_id=engagement_id,
        document_id=None,
        requested_by_user_id=user.id,
        analysis_type="sustainability_summary",
        query_text="q",
        provider=PROVIDER_NAME,
        model=MODEL,
        prompt_template_version="v1",
        output_schema_version="v1",
        temperature=Decimal("0.10"),
        retrieval_top_k=5,
        embedding_provider=EMBEDDING_PROVIDER_NAME,
        embedding_model=EMBEDDING_MODEL,
        embedding_model_version=EMBEDDING_MODEL_VERSION,
        minimum_relevance_score=MIN_RELEVANCE,
        request_hash=request_hash,
    )
    assert stale_run.id is not None
    harness.analysis_run_repository.force_processing_started_at(
        stale_run.id, datetime.now(timezone.utc) - timedelta(seconds=STALE_AFTER_SECONDS + 60)
    )

    harness.llm_gateway_responses = [VALID_STRUCTURED_OUTPUT]
    service, gateway = harness.build_service()
    view = await service.analyze_engagement(
        user, engagement_id, analysis_type="sustainability_summary", query_text="q"
    )

    assert view.analysis_run_id == stale_run.id
    assert view.status == "COMPLETED"
    assert gateway.call_count == 1


async def test_non_stale_processing_run_is_not_reprocessed(harness: Harness) -> None:
    organization_id, engagement_id, document_id, chunk_id = harness.seed_org()
    harness.embedding_repository.results = [
        _search_result(chunk_id=chunk_id, document_id=document_id, engagement_id=engagement_id)
    ]
    service, gateway = harness.build_service()
    user = _user(organization_id)

    from app.services.analysis.request_hash import compute_request_hash

    request_hash = compute_request_hash(
        organization_id=organization_id,
        engagement_id=engagement_id,
        document_id=None,
        evidence_revision=(
            f"{document_id}:{harness.document_repository.rows[document_id].updated_at.isoformat()}"
        ),
        analysis_type="sustainability_summary",
        query_text="q",
        provider=PROVIDER_NAME,
        model=MODEL,
        prompt_template_version="v1",
        output_schema_version="v1",
        temperature=Decimal("0.10"),
        retrieval_top_k=5,
        embedding_provider=EMBEDDING_PROVIDER_NAME,
        embedding_model=EMBEDDING_MODEL,
        embedding_model_version=EMBEDDING_MODEL_VERSION,
        minimum_relevance_score=MIN_RELEVANCE,
    )
    in_flight_run, _is_new = await harness.analysis_run_repository.claim_or_get(
        organization_id=organization_id,
        engagement_id=engagement_id,
        document_id=None,
        requested_by_user_id=user.id,
        analysis_type="sustainability_summary",
        query_text="q",
        provider=PROVIDER_NAME,
        model=MODEL,
        prompt_template_version="v1",
        output_schema_version="v1",
        temperature=Decimal("0.10"),
        retrieval_top_k=5,
        embedding_provider=EMBEDDING_PROVIDER_NAME,
        embedding_model=EMBEDDING_MODEL,
        embedding_model_version=EMBEDDING_MODEL_VERSION,
        minimum_relevance_score=MIN_RELEVANCE,
        request_hash=request_hash,
    )
    # processing_started_at defaults to "now" -- not stale.

    view = await service.analyze_engagement(
        user, engagement_id, analysis_type="sustainability_summary", query_text="q"
    )

    assert view.analysis_run_id == in_flight_run.id
    assert view.status == "PROCESSING"
    assert gateway.call_count == 0  # never touched -- still genuinely in flight
