"""create_analysis_runs_and_source_references

Revision ID: da0298a9c722
Revises: 3f3acc7fc556
Create Date: 2026-07-14 09:25:46.188431

Sprint 3.6B, RAG + Structured Sustainability Analysis Foundation.

Creates ``analysis_runs`` (one row per RAG analysis request/result) and
``analysis_source_references`` (the citations grounding that result in
real, retrieved chunks). Does not touch ``ai_analysis_results`` -- that
table is a pre-existing, minimal, always-empty reconciliation table with
no tenant columns; it is deliberately left alone this sprint.

Tenant-safe idempotency (mandatory correction 1): ``UNIQUE
(organization_id, request_hash)``, not a bare globally-unique
``request_hash``. ``request_hash`` itself is computed application-side
over every behavior-changing input *including* ``organization_id`` (see
``app/services/rag_analysis.py``), so this constraint is a second,
declarative backstop on top of an already tenant-scoped hash -- the
same "derive and also declaratively enforce" pattern used for
``document_chunk_embeddings`` lineage in Sprint 3.6A.

Tenant lineage on ``analysis_source_references`` is enforced exactly as
it was for ``document_chunk_embeddings``: three composite foreign keys
chain ``document_chunks -> documents -> engagements`` along the real
ownership path, reusing the supporting ``UNIQUE(id, <column>)``
constraints already created on those three tables by migration
``3f3acc7fc556`` (no new supporting constraints needed there). A fourth
composite foreign key additionally ties each reference's
``organization_id`` to its own parent ``analysis_runs`` row's
``organization_id`` (via a new ``UNIQUE(id, organization_id)`` on
``analysis_runs`` added here) -- a citation cannot exist unless its
chunk's real tenant *and* its parent run's tenant agree, closing off
the very risk mandatory correction 2 is about: a citation's lineage
must be derivable from the real chunk, never from anything the caller
(or an LLM response) claims.

``analysis_source_references`` has exactly one row per (analysis_run_id,
chunk_id) -- one row per chunk that was actually assembled into the
LLM's context for that run, identified by ``citation_order`` (the
integer suffix of its temporary ``SOURCE_<n>`` key during context
assembly). Structured-output items reference these rows by id in a flat
list, not the other way around, so the same chunk can support multiple
findings without duplicate rows.

``ON DELETE NO ACTION`` throughout, matching every other foreign key in
this schema. No ANN index needed (no vector column in these two
tables). Downgrade drops both tables and the one new supporting unique
constraint on ``analysis_runs``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'da0298a9c722'
down_revision: Union[str, None] = '3f3acc7fc556'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'analysis_runs',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('engagement_id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=True),
        sa.Column('requested_by_user_id', sa.UUID(), nullable=False),
        sa.Column('analysis_type', sa.String(), nullable=False),
        sa.Column('query_text', sa.Text(), nullable=True),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('prompt_template_version', sa.String(), nullable=False),
        sa.Column('output_schema_version', sa.String(), nullable=False),
        sa.Column('temperature', sa.Numeric(3, 2), nullable=False),
        sa.Column('retrieval_top_k', sa.Integer(), nullable=False),
        sa.Column('embedding_provider', sa.String(), nullable=False),
        sa.Column('embedding_model', sa.String(), nullable=False),
        sa.Column('embedding_model_version', sa.String(), nullable=False),
        sa.Column('minimum_relevance_score', sa.Numeric(4, 3), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(), server_default='PROCESSING', nullable=False),
        sa.Column('structured_output', JSONB(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('insufficient_evidence_reason', sa.Text(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('estimated_cost', sa.Numeric(10, 4), nullable=True),
        sa.Column(
            'processing_started_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('attempt_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='NO ACTION'),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id'], ondelete='NO ACTION'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='NO ACTION'),
        sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id'], ondelete='NO ACTION'),
        sa.UniqueConstraint(
            'organization_id', 'request_hash', name='uq_analysis_runs_organization_request_hash'
        ),
        sa.CheckConstraint('attempt_count >= 1', name='ck_analysis_runs_attempt_count'),
        sa.CheckConstraint(
            "status IN ('PROCESSING', 'COMPLETED', 'FAILED', 'INSUFFICIENT_EVIDENCE')",
            name='ck_analysis_runs_status',
        ),
        sa.CheckConstraint(
            "(status = 'PROCESSING' AND structured_output IS NULL AND error_message IS NULL) OR "
            "(status = 'COMPLETED' AND structured_output IS NOT NULL AND error_message IS NULL) OR "
            "(status = 'FAILED' AND structured_output IS NULL) OR "
            "(status = 'INSUFFICIENT_EVIDENCE' AND structured_output IS NULL "
            "AND insufficient_evidence_reason IS NOT NULL)",
            name='ck_analysis_runs_status_consistency',
        ),
        sa.CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'", name='ck_analysis_runs_request_hash_format'
        ),
    )
    op.create_index(
        'ix_analysis_runs_organization_id', 'analysis_runs', ['organization_id']
    )
    op.create_index(
        'ix_analysis_runs_org_engagement', 'analysis_runs', ['organization_id', 'engagement_id']
    )
    op.create_index(
        'ix_analysis_runs_org_document', 'analysis_runs', ['organization_id', 'document_id']
    )
    # Supporting unique constraint enabling the composite lineage FK below.
    op.create_unique_constraint(
        'uq_analysis_runs_id_organization_id', 'analysis_runs', ['id', 'organization_id']
    )

    op.create_table(
        'analysis_source_references',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('analysis_run_id', sa.UUID(), nullable=False),
        sa.Column('chunk_id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('engagement_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('char_start', sa.Integer(), nullable=False),
        sa.Column('char_end', sa.Integer(), nullable=False),
        sa.Column('quoted_snippet', sa.Text(), nullable=False),
        sa.Column('citation_order', sa.Integer(), nullable=False),
        sa.Column('relevance_score', sa.Numeric(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['analysis_run_id', 'organization_id'],
            ['analysis_runs.id', 'analysis_runs.organization_id'],
            name='fk_analysis_source_references_run_lineage',
            ondelete='NO ACTION',
        ),
        sa.ForeignKeyConstraint(
            ['chunk_id', 'document_id'],
            ['document_chunks.id', 'document_chunks.document_id'],
            name='fk_analysis_source_references_chunk_lineage',
            ondelete='NO ACTION',
        ),
        sa.ForeignKeyConstraint(
            ['document_id', 'engagement_id'],
            ['documents.id', 'documents.engagement_id'],
            name='fk_analysis_source_references_document_lineage',
            ondelete='NO ACTION',
        ),
        sa.ForeignKeyConstraint(
            ['engagement_id', 'organization_id'],
            ['engagements.id', 'engagements.organization_id'],
            name='fk_analysis_source_references_engagement_lineage',
            ondelete='NO ACTION',
        ),
        sa.UniqueConstraint(
            'analysis_run_id', 'chunk_id', name='uq_analysis_source_references_run_chunk'
        ),
        sa.CheckConstraint(
            'char_end > char_start', name='ck_analysis_source_references_char_range'
        ),
        sa.CheckConstraint(
            'citation_order >= 1', name='ck_analysis_source_references_citation_order'
        ),
    )
    op.create_index(
        'ix_analysis_source_references_organization_id',
        'analysis_source_references',
        ['organization_id'],
    )
    op.create_index(
        'ix_analysis_source_references_analysis_run_id',
        'analysis_source_references',
        ['analysis_run_id'],
    )
    op.create_index(
        'ix_analysis_source_references_chunk_id', 'analysis_source_references', ['chunk_id']
    )


def downgrade() -> None:
    op.drop_table('analysis_source_references')
    op.drop_constraint(
        'uq_analysis_runs_id_organization_id', 'analysis_runs', type_='unique'
    )
    op.drop_table('analysis_runs')
