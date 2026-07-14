"""Integration tests for ``SQLAlchemyAnalysisRunRepository`` against a
real database (migration ``da0298a9c722``).

Every row a test creates is tracked and deleted, via an independent
session, in ``cleanup_ids``'s teardown -- regardless of test outcome, in
dependency-safe order: analysis_source_references, then analysis_runs,
then document_chunks, then documents, then users, then engagements, then
organizations.

Marked ``integration`` module-wide, mirroring
``test_document_chunk_embedding_repository.py``.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncIterator, Awaitable, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.repositories.analysis_run import NewCitation
from app.infrastructure.db.models.analysis_run import AnalysisRunModel
from app.infrastructure.db.models.analysis_source_reference import AnalysisSourceReferenceModel
from app.infrastructure.db.models.document import DocumentModel
from app.infrastructure.db.models.document_chunk import DocumentChunkModel
from app.infrastructure.db.models.engagement import Engagement as EngagementModel
from app.infrastructure.db.models.organization import Organization as OrganizationModel
from app.infrastructure.db.models.user import User as UserModel
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.repositories.analysis_run import SQLAlchemyAnalysisRunRepository

pytestmark = pytest.mark.integration

PROVIDER = "openai"
MODEL = "gpt-4o-mini"
EMBEDDING_PROVIDER = "openai"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_MODEL_VERSION = ""


def _hash() -> str:
    return (uuid.uuid4().hex + uuid.uuid4().hex)  # 64 hex chars


def _claim_kwargs(**overrides: object) -> dict:
    kwargs: dict = dict(
        analysis_type="sustainability_summary",
        query_text="scope 1 emissions",
        provider=PROVIDER,
        model=MODEL,
        prompt_template_version="v1",
        output_schema_version="v1",
        temperature=Decimal("0.10"),
        retrieval_top_k=5,
        embedding_provider=EMBEDDING_PROVIDER,
        embedding_model=EMBEDDING_MODEL,
        embedding_model_version=EMBEDDING_MODEL_VERSION,
        minimum_relevance_score=Decimal("0.500"),
    )
    kwargs.update(overrides)
    return kwargs


@pytest.fixture(autouse=True)
def _require_database_url() -> None:
    if not get_settings().database_url:
        pytest.skip("integration tests require DATABASE_URL to be set")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def cleanup_ids() -> AsyncIterator[dict[str, list[uuid.UUID]]]:
    ids: dict[str, list[uuid.UUID]] = {
        "citations": [], "runs": [], "chunks": [], "documents": [], "users": [],
        "engagements": [], "organizations": [],
    }
    yield ids
    async with AsyncSessionLocal() as cleanup_session:
        for citation_id in ids["citations"]:
            model = await cleanup_session.get(AnalysisSourceReferenceModel, citation_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for run_id in ids["runs"]:
            model = await cleanup_session.get(AnalysisRunModel, run_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for chunk_id in ids["chunks"]:
            model = await cleanup_session.get(DocumentChunkModel, chunk_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for document_id in ids["documents"]:
            model = await cleanup_session.get(DocumentModel, document_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for user_id in ids["users"]:
            model = await cleanup_session.get(UserModel, user_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for engagement_id in ids["engagements"]:
            model = await cleanup_session.get(EngagementModel, engagement_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()
        for organization_id in ids["organizations"]:
            model = await cleanup_session.get(OrganizationModel, organization_id)
            if model is not None:
                await cleanup_session.delete(model)
        await cleanup_session.commit()


@pytest.fixture
def make_context(cleanup_ids: dict[str, list[uuid.UUID]]) -> Callable[..., Awaitable[dict]]:
    """Factory: creates a real Organization + Engagement + Document +
    DocumentChunk + User. Returns a dict of ids."""

    async def _make(content: str = "Scope 1 emissions decreased.") -> dict:
        async with AsyncSessionLocal() as session:
            organization = OrganizationModel(name="Analysis Repo Test Org")
            session.add(organization)
            await session.flush()
            engagement = EngagementModel(
                organization_id=organization.id, title="Analysis Repo Test Engagement"
            )
            session.add(engagement)
            await session.flush()
            document = DocumentModel(
                filename="report.pdf", storage_path=f"test/{uuid.uuid4()}.pdf",
                processing_status="PROCESSED", engagement_id=engagement.id,
            )
            session.add(document)
            await session.flush()
            chunk = DocumentChunkModel(
                document_id=document.id, chunk_index=0, content=content,
                char_start=0, char_end=len(content),
            )
            session.add(chunk)
            await session.flush()
            user_id = uuid.uuid4()
            session.add(
                UserModel(
                    id=user_id, organization_id=organization.id, full_name="Test User",
                    email=f"analysis-repo-{user_id}@example.com", role=None,
                )
            )
            await session.commit()
        cleanup_ids["organizations"].append(organization.id)
        cleanup_ids["engagements"].append(engagement.id)
        cleanup_ids["documents"].append(document.id)
        cleanup_ids["chunks"].append(chunk.id)
        cleanup_ids["users"].append(user_id)
        return {
            "organization_id": organization.id,
            "engagement_id": engagement.id,
            "document_id": document.id,
            "chunk_id": chunk.id,
            "user_id": user_id,
        }

    return _make


@pytest.fixture
async def ctx(make_context: Callable[..., Awaitable[dict]]) -> dict:
    return await make_context()


def _track_run(cleanup_ids: dict[str, list[uuid.UUID]], run) -> None:
    if run.id is not None:
        cleanup_ids["runs"].append(run.id)


def _track_citations(cleanup_ids: dict[str, list[uuid.UUID]], citations) -> None:
    cleanup_ids["citations"].extend(c.id for c in citations if c.id is not None)


# ---------------------------------------------------------------------------
# Tenant-safe idempotency (Mandatory Correction 1)
# ---------------------------------------------------------------------------


async def test_claim_or_get_creates_new_run_on_first_call(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], ctx: dict
) -> None:
    repository = SQLAlchemyAnalysisRunRepository(session)

    run, is_new = await repository.claim_or_get(
        organization_id=ctx["organization_id"], engagement_id=ctx["engagement_id"],
        document_id=ctx["document_id"], requested_by_user_id=ctx["user_id"],
        request_hash=_hash(), **_claim_kwargs(),
    )
    _track_run(cleanup_ids, run)

    assert is_new is True
    assert run.status == "PROCESSING"
    assert run.organization_id == ctx["organization_id"]


async def test_claim_or_get_is_idempotent_within_same_organization(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], ctx: dict
) -> None:
    repository = SQLAlchemyAnalysisRunRepository(session)
    request_hash = _hash()

    first, first_is_new = await repository.claim_or_get(
        organization_id=ctx["organization_id"], engagement_id=ctx["engagement_id"],
        document_id=ctx["document_id"], requested_by_user_id=ctx["user_id"],
        request_hash=request_hash, **_claim_kwargs(),
    )
    _track_run(cleanup_ids, first)
    second, second_is_new = await repository.claim_or_get(
        organization_id=ctx["organization_id"], engagement_id=ctx["engagement_id"],
        document_id=ctx["document_id"], requested_by_user_id=ctx["user_id"],
        request_hash=request_hash, **_claim_kwargs(),
    )

    assert first_is_new is True
    assert second_is_new is False
    assert second.id == first.id


async def test_claim_or_get_different_organization_same_hash_creates_separate_run(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]],
    make_context: Callable[..., Awaitable[dict]],
) -> None:
    ctx_a = await make_context("Org A content.")
    ctx_b = await make_context("Org B content.")
    repository = SQLAlchemyAnalysisRunRepository(session)
    shared_hash = _hash()

    run_a, is_new_a = await repository.claim_or_get(
        organization_id=ctx_a["organization_id"], engagement_id=ctx_a["engagement_id"],
        document_id=ctx_a["document_id"], requested_by_user_id=ctx_a["user_id"],
        request_hash=shared_hash, **_claim_kwargs(),
    )
    run_b, is_new_b = await repository.claim_or_get(
        organization_id=ctx_b["organization_id"], engagement_id=ctx_b["engagement_id"],
        document_id=ctx_b["document_id"], requested_by_user_id=ctx_b["user_id"],
        request_hash=shared_hash, **_claim_kwargs(),
    )
    _track_run(cleanup_ids, run_a)
    _track_run(cleanup_ids, run_b)

    assert is_new_a is True
    assert is_new_b is True  # never collides across organizations
    assert run_a.id != run_b.id


async def test_foreign_organization_hash_lookup_never_returns_another_tenants_run(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]],
    make_context: Callable[..., Awaitable[dict]],
) -> None:
    ctx_a = await make_context("Org A content.")
    ctx_b = await make_context("Org B content.")
    repository = SQLAlchemyAnalysisRunRepository(session)
    shared_hash = _hash()

    run_a, _is_new = await repository.claim_or_get(
        organization_id=ctx_a["organization_id"], engagement_id=ctx_a["engagement_id"],
        document_id=ctx_a["document_id"], requested_by_user_id=ctx_a["user_id"],
        request_hash=shared_hash, **_claim_kwargs(),
    )
    _track_run(cleanup_ids, run_a)

    fetched_by_b = await repository.get_by_id(run_a.id, organization_id=ctx_b["organization_id"])

    assert fetched_by_b is None  # org B's request_hash cannot retrieve org A's run


async def test_two_concurrent_first_claims_only_one_wins(
    cleanup_ids: dict[str, list[uuid.UUID]], ctx: dict
) -> None:
    request_hash = _hash()

    async def _attempt() -> bool:
        async with AsyncSessionLocal() as claim_session:
            repository = SQLAlchemyAnalysisRunRepository(claim_session)
            _run, is_new = await repository.claim_or_get(
                organization_id=ctx["organization_id"], engagement_id=ctx["engagement_id"],
                document_id=ctx["document_id"], requested_by_user_id=ctx["user_id"],
                request_hash=request_hash, **_claim_kwargs(),
            )
            return is_new

    results = await asyncio.gather(_attempt(), _attempt())

    assert sorted(results) == [False, True]  # exactly one winner

    async with AsyncSessionLocal() as verify_session:
        from sqlalchemy import select

        result = await verify_session.execute(
            select(AnalysisRunModel).where(AnalysisRunModel.request_hash == request_hash)
        )
        rows = result.scalars().all()
        assert len(rows) == 1  # never duplicated
        cleanup_ids["runs"].append(rows[0].id)


async def test_get_by_id_returns_none_for_foreign_organization(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], ctx: dict
) -> None:
    repository = SQLAlchemyAnalysisRunRepository(session)
    run, _is_new = await repository.claim_or_get(
        organization_id=ctx["organization_id"], engagement_id=ctx["engagement_id"],
        document_id=ctx["document_id"], requested_by_user_id=ctx["user_id"],
        request_hash=_hash(), **_claim_kwargs(),
    )
    _track_run(cleanup_ids, run)

    result = await repository.get_by_id(run.id, organization_id=uuid.uuid4())

    assert result is None


# ---------------------------------------------------------------------------
# FAILED retry
# ---------------------------------------------------------------------------


async def test_retry_failed_transitions_and_increments_attempt_count(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], ctx: dict
) -> None:
    repository = SQLAlchemyAnalysisRunRepository(session)
    run, _is_new = await repository.claim_or_get(
        organization_id=ctx["organization_id"], engagement_id=ctx["engagement_id"],
        document_id=ctx["document_id"], requested_by_user_id=ctx["user_id"],
        request_hash=_hash(), **_claim_kwargs(),
    )
    _track_run(cleanup_ids, run)
    await repository.mark_failed(run.id, error_message="Analysis provider unavailable")

    retried = await repository.retry_failed(run.id)

    assert retried is not None
    assert retried.status == "PROCESSING"
    assert retried.attempt_count == 2
    assert retried.error_message is None
    assert retried.updated_at > run.updated_at


async def test_retry_failed_does_not_touch_non_failed_rows(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], ctx: dict
) -> None:
    repository = SQLAlchemyAnalysisRunRepository(session)
    run, _is_new = await repository.claim_or_get(
        organization_id=ctx["organization_id"], engagement_id=ctx["engagement_id"],
        document_id=ctx["document_id"], requested_by_user_id=ctx["user_id"],
        request_hash=_hash(), **_claim_kwargs(),
    )
    _track_run(cleanup_ids, run)  # still PROCESSING, not FAILED

    retried = await repository.retry_failed(run.id)

    assert retried is None


# ---------------------------------------------------------------------------
# Stale reclaim
# ---------------------------------------------------------------------------


async def test_non_stale_processing_row_cannot_be_reclaimed(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], ctx: dict
) -> None:
    repository = SQLAlchemyAnalysisRunRepository(session)
    run, _is_new = await repository.claim_or_get(
        organization_id=ctx["organization_id"], engagement_id=ctx["engagement_id"],
        document_id=ctx["document_id"], requested_by_user_id=ctx["user_id"],
        request_hash=_hash(), **_claim_kwargs(),
    )
    _track_run(cleanup_ids, run)  # processing_started_at = now(), not stale

    reclaimed = await repository.reclaim_stale(run.id, stale_after_seconds=300)

    assert reclaimed is None


async def test_stale_processing_row_can_be_reclaimed_exactly_once(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], ctx: dict
) -> None:
    repository = SQLAlchemyAnalysisRunRepository(session)
    run, _is_new = await repository.claim_or_get(
        organization_id=ctx["organization_id"], engagement_id=ctx["engagement_id"],
        document_id=ctx["document_id"], requested_by_user_id=ctx["user_id"],
        request_hash=_hash(), **_claim_kwargs(),
    )
    _track_run(cleanup_ids, run)

    stale_time = datetime.now(timezone.utc) - timedelta(seconds=999)
    await session.execute(
        text("UPDATE analysis_runs SET processing_started_at = :t WHERE id = :id"),
        {"t": stale_time, "id": run.id},
    )
    await session.commit()

    first_reclaim = await repository.reclaim_stale(run.id, stale_after_seconds=300)
    second_reclaim = await repository.reclaim_stale(run.id, stale_after_seconds=300)

    assert first_reclaim is not None
    assert first_reclaim.attempt_count == 2
    assert second_reclaim is None  # no longer stale immediately after reclaim


async def test_two_concurrent_stale_reclaim_attempts_only_one_wins(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], ctx: dict
) -> None:
    repository = SQLAlchemyAnalysisRunRepository(session)
    run, _is_new = await repository.claim_or_get(
        organization_id=ctx["organization_id"], engagement_id=ctx["engagement_id"],
        document_id=ctx["document_id"], requested_by_user_id=ctx["user_id"],
        request_hash=_hash(), **_claim_kwargs(),
    )
    _track_run(cleanup_ids, run)

    stale_time = datetime.now(timezone.utc) - timedelta(seconds=999)
    await session.execute(
        text("UPDATE analysis_runs SET processing_started_at = :t WHERE id = :id"),
        {"t": stale_time, "id": run.id},
    )
    await session.commit()

    async def _attempt() -> bool:
        async with AsyncSessionLocal() as reclaim_session:
            reclaim_repository = SQLAlchemyAnalysisRunRepository(reclaim_session)
            reclaimed = await reclaim_repository.reclaim_stale(run.id, stale_after_seconds=300)
            return reclaimed is not None

    results = await asyncio.gather(_attempt(), _attempt())

    assert sorted(results) == [False, True]


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


async def test_mark_completed_persists_structured_output(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], ctx: dict
) -> None:
    repository = SQLAlchemyAnalysisRunRepository(session)
    run, _is_new = await repository.claim_or_get(
        organization_id=ctx["organization_id"], engagement_id=ctx["engagement_id"],
        document_id=ctx["document_id"], requested_by_user_id=ctx["user_id"],
        request_hash=_hash(), **_claim_kwargs(),
    )
    _track_run(cleanup_ids, run)

    await repository.mark_completed(
        run.id, structured_output={"executive_summary": "ok", "overall_confidence": 0.8},
        prompt_tokens=10, completion_tokens=20, total_tokens=30, estimated_cost=None,
    )

    fetched = await repository.get_by_id(run.id, organization_id=ctx["organization_id"])
    assert fetched is not None
    assert fetched.status == "COMPLETED"
    assert fetched.structured_output["executive_summary"] == "ok"
    assert fetched.completed_at is not None


async def test_mark_failed_clears_structured_output(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], ctx: dict
) -> None:
    repository = SQLAlchemyAnalysisRunRepository(session)
    run, _is_new = await repository.claim_or_get(
        organization_id=ctx["organization_id"], engagement_id=ctx["engagement_id"],
        document_id=ctx["document_id"], requested_by_user_id=ctx["user_id"],
        request_hash=_hash(), **_claim_kwargs(),
    )
    _track_run(cleanup_ids, run)

    await repository.mark_failed(run.id, error_message="Analysis provider unavailable")

    fetched = await repository.get_by_id(run.id, organization_id=ctx["organization_id"])
    assert fetched is not None
    assert fetched.status == "FAILED"
    assert fetched.structured_output is None
    assert fetched.error_message == "Analysis provider unavailable"


async def test_mark_insufficient_evidence_persists_reason(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], ctx: dict
) -> None:
    repository = SQLAlchemyAnalysisRunRepository(session)
    run, _is_new = await repository.claim_or_get(
        organization_id=ctx["organization_id"], engagement_id=ctx["engagement_id"],
        document_id=ctx["document_id"], requested_by_user_id=ctx["user_id"],
        request_hash=_hash(), **_claim_kwargs(),
    )
    _track_run(cleanup_ids, run)

    await repository.mark_insufficient_evidence(run.id, reason="No relevant content found.")

    fetched = await repository.get_by_id(run.id, organization_id=ctx["organization_id"])
    assert fetched is not None
    assert fetched.status == "INSUFFICIENT_EVIDENCE"
    assert fetched.insufficient_evidence_reason == "No relevant content found."
    assert fetched.structured_output is None


# ---------------------------------------------------------------------------
# Server-controlled citations (Mandatory Correction 2)
# ---------------------------------------------------------------------------


async def test_add_citations_derives_lineage_from_real_chunk(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], ctx: dict
) -> None:
    repository = SQLAlchemyAnalysisRunRepository(session)
    run, _is_new = await repository.claim_or_get(
        organization_id=ctx["organization_id"], engagement_id=ctx["engagement_id"],
        document_id=ctx["document_id"], requested_by_user_id=ctx["user_id"],
        request_hash=_hash(), **_claim_kwargs(),
    )
    _track_run(cleanup_ids, run)

    citations = await repository.add_citations(
        run.id, organization_id=ctx["organization_id"],
        citations=[
            NewCitation(
                chunk_id=ctx["chunk_id"], citation_order=1, relevance_score=Decimal("0.93"),
                char_start=0, char_end=28, quoted_snippet="Scope 1 emissions decreased.",
            )
        ],
    )
    _track_citations(cleanup_ids, citations)

    assert len(citations) == 1
    citation = citations[0]
    assert citation.document_id == ctx["document_id"]
    assert citation.engagement_id == ctx["engagement_id"]
    assert citation.organization_id == ctx["organization_id"]
    assert citation.citation_order == 1


async def test_add_citations_excludes_citation_whose_chunk_belongs_to_a_different_organization(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], ctx: dict,
    make_context: Callable[..., Awaitable[dict]],
) -> None:
    """Defense in depth: a chunk_id that genuinely belongs to a different
    organization than the owning run's organization_id must never produce
    a citation row, even if a caller (or a future bug) tried to pass it."""
    other_ctx = await make_context("Foreign tenant content.")
    repository = SQLAlchemyAnalysisRunRepository(session)
    run, _is_new = await repository.claim_or_get(
        organization_id=ctx["organization_id"], engagement_id=ctx["engagement_id"],
        document_id=ctx["document_id"], requested_by_user_id=ctx["user_id"],
        request_hash=_hash(), **_claim_kwargs(),
    )
    _track_run(cleanup_ids, run)

    citations = await repository.add_citations(
        run.id, organization_id=ctx["organization_id"],
        citations=[
            NewCitation(
                chunk_id=other_ctx["chunk_id"], citation_order=1, relevance_score=Decimal("0.93"),
                char_start=0, char_end=28, quoted_snippet="Foreign tenant content.",
            )
        ],
    )
    _track_citations(cleanup_ids, citations)

    assert citations == []


async def test_composite_lineage_fk_rejects_raw_insert_with_mismatched_run_organization(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], ctx: dict,
    make_context: Callable[..., Awaitable[dict]],
) -> None:
    """Declarative backstop: even a raw INSERT that bypasses the
    repository's derived lineage cannot attach a chunk/run pair whose
    organizations disagree."""
    other_ctx = await make_context("Foreign tenant content.")
    repository = SQLAlchemyAnalysisRunRepository(session)
    run, _is_new = await repository.claim_or_get(
        organization_id=ctx["organization_id"], engagement_id=ctx["engagement_id"],
        document_id=ctx["document_id"], requested_by_user_id=ctx["user_id"],
        request_hash=_hash(), **_claim_kwargs(),
    )
    _track_run(cleanup_ids, run)

    with pytest.raises(IntegrityError):
        await session.execute(
            text(
                """
                INSERT INTO analysis_source_references
                  (analysis_run_id, chunk_id, document_id, engagement_id, organization_id,
                   chunk_index, char_start, char_end, quoted_snippet, citation_order,
                   relevance_score)
                VALUES (:run_id, :chunk_id, :document_id, :engagement_id, :organization_id,
                        0, 0, 10, 'x', 1, 0.9)
                """
            ),
            {
                "run_id": run.id,  # belongs to ctx["organization_id"]
                "chunk_id": other_ctx["chunk_id"],
                "document_id": other_ctx["document_id"],
                "engagement_id": other_ctx["engagement_id"],
                "organization_id": other_ctx["organization_id"],  # mismatched vs run's own org
            },
        )
    await session.rollback()


async def test_get_citations_ordered_by_citation_order(
    session: AsyncSession, cleanup_ids: dict[str, list[uuid.UUID]], ctx: dict,
    make_context: Callable[..., Awaitable[dict]],
) -> None:
    repository = SQLAlchemyAnalysisRunRepository(session)
    run, _is_new = await repository.claim_or_get(
        organization_id=ctx["organization_id"], engagement_id=ctx["engagement_id"],
        document_id=ctx["document_id"], requested_by_user_id=ctx["user_id"],
        request_hash=_hash(), **_claim_kwargs(),
    )
    _track_run(cleanup_ids, run)

    async with AsyncSessionLocal() as second_session:
        second_chunk = DocumentChunkModel(
            document_id=ctx["document_id"], chunk_index=1, content="Second chunk.",
            char_start=0, char_end=13,
        )
        second_session.add(second_chunk)
        await second_session.commit()
        await second_session.refresh(second_chunk)
    cleanup_ids["chunks"].append(second_chunk.id)

    citations = await repository.add_citations(
        run.id, organization_id=ctx["organization_id"],
        citations=[
            NewCitation(
                chunk_id=second_chunk.id, citation_order=2, relevance_score=Decimal("0.80"),
                char_start=0, char_end=13, quoted_snippet="Second chunk.",
            ),
            NewCitation(
                chunk_id=ctx["chunk_id"], citation_order=1, relevance_score=Decimal("0.93"),
                char_start=0, char_end=28, quoted_snippet="Scope 1 emissions decreased.",
            ),
        ],
    )
    _track_citations(cleanup_ids, citations)

    fetched = await repository.get_citations(run.id)

    assert [c.citation_order for c in fetched] == [1, 2]
