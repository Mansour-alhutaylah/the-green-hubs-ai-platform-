"""create_document_chunk_embeddings

Revision ID: 3f3acc7fc556
Revises: 233e7656bf79
Create Date: 2026-07-13 18:42:43.494237

Sprint 3.6A, Vector Retrieval Foundation.

Enables pgvector (verified available, version 0.8.2, in this Supabase
project's ``pg_available_extensions`` before writing this migration; not
previously installed) and creates ``document_chunk_embeddings``.

Fixed dimension: this sprint supports exactly one configured embedding
model/dimension (OpenAI ``text-embedding-3-small``, 1536), so the
column is ``vector(1536)`` and ``embedding_dimension`` is constrained to
equal 1536 -- not a generic "any dimension" design. A future
differently-sized model requires a new migration or a separate table,
not a change to this column.

Tenant-lineage integrity is enforced two ways, per the approved plan:
1. Application-side: the repository only ever populates
   document_id/engagement_id/organization_id via an ``INSERT ... SELECT``
   that derives them from ``chunk_id``'s real
   document_chunks -> documents -> engagements chain (see
   ``SQLAlchemyDocumentChunkEmbeddingRepository``) -- these three columns
   are never accepted as independent trusted parameters.
2. Declaratively: three composite foreign keys chain the same lineage at
   the database level --
   (chunk_id, document_id) -> document_chunks(id, document_id),
   (document_id, engagement_id) -> documents(id, engagement_id),
   (engagement_id, organization_id) -> engagements(id, organization_id).
   Each requires a supporting UNIQUE constraint on the referenced
   table's own (id, <lineage column>) pair -- harmless to add since
   ``id`` is already unique on each of those tables alone, so pairing it
   with one more column is trivially still unique. A plain
   single-column FK on ``chunk_id`` alone is intentionally omitted: the
   composite (chunk_id, document_id) FK already requires chunk_id to
   reference a real document_chunks row, so a separate FK would be
   redundant.
   No existing-schema limitation was found that would make this unsafe:
   ``engagements.organization_id`` is nullable, but since
   ``document_chunk_embeddings.organization_id`` is itself NOT NULL, a
   row can never reference an engagement whose organization is null --
   a correct failure mode, not a gap.

``embedding`` is nullable: populated only when ``status = 'COMPLETED'``.
A single combined CHECK constraint enforces the state/column
consistency invariant (PROCESSING/FAILED have no vector, PROCESSING
also carries no error, COMPLETED always has both a vector and no
error), so bad partial states cannot be written even by a
future/buggy caller bypassing the service layer.

``model_version`` is NOT NULL DEFAULT '' (not nullable) specifically so
the UNIQUE(chunk_id, provider, model, model_version) identity constraint
behaves correctly for providers with no version concept (Postgres
treats NULL <> NULL in uniqueness checks, which would otherwise let
duplicate rows through).

``ON DELETE NO ACTION`` throughout, matching every other foreign key in
this schema.

No ANN index (HNSW/IVFFlat) this sprint -- MVP data volume does not
justify it; a plain sequential distance scan combined with the B-tree
tenant-scope indexes below is sufficient. Downgrade drops this table and
its supporting unique constraints but deliberately does NOT drop the
``vector`` extension itself -- a shared, global object; leaving it
installed-but-unused is safer than a downgrade that could conflict with
anything else relying on it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = '3f3acc7fc556'
down_revision: Union[str, None] = '233e7656bf79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIMENSION = 1536


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Supporting UNIQUE constraints for the composite lineage foreign
    # keys created below -- see module docstring.
    op.create_unique_constraint(
        'uq_document_chunks_id_document_id', 'document_chunks', ['id', 'document_id']
    )
    op.create_unique_constraint(
        'uq_documents_id_engagement_id', 'documents', ['id', 'engagement_id']
    )
    op.create_unique_constraint(
        'uq_engagements_id_organization_id', 'engagements', ['id', 'organization_id']
    )

    op.create_table(
        'document_chunk_embeddings',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('chunk_id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('engagement_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('model_version', sa.String(), server_default='', nullable=False),
        sa.Column('embedding_dimension', sa.Integer(), nullable=False),
        sa.Column('embedding', Vector(EMBEDDING_DIMENSION), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(), server_default='PROCESSING', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column(
            'processing_started_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('attempt_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['chunk_id', 'document_id'],
            ['document_chunks.id', 'document_chunks.document_id'],
            name='fk_document_chunk_embeddings_chunk_lineage',
            ondelete='NO ACTION',
        ),
        sa.ForeignKeyConstraint(
            ['document_id', 'engagement_id'],
            ['documents.id', 'documents.engagement_id'],
            name='fk_document_chunk_embeddings_document_lineage',
            ondelete='NO ACTION',
        ),
        sa.ForeignKeyConstraint(
            ['engagement_id', 'organization_id'],
            ['engagements.id', 'engagements.organization_id'],
            name='fk_document_chunk_embeddings_engagement_lineage',
            ondelete='NO ACTION',
        ),
        sa.UniqueConstraint(
            'chunk_id',
            'provider',
            'model',
            'model_version',
            name='uq_document_chunk_embeddings_identity',
        ),
        sa.CheckConstraint(
            f'embedding_dimension = {EMBEDDING_DIMENSION}',
            name='ck_document_chunk_embeddings_dimension',
        ),
        sa.CheckConstraint(
            'attempt_count >= 1', name='ck_document_chunk_embeddings_attempt_count'
        ),
        sa.CheckConstraint(
            "status IN ('PROCESSING', 'COMPLETED', 'FAILED')",
            name='ck_document_chunk_embeddings_status',
        ),
        sa.CheckConstraint(
            "(status = 'PROCESSING' AND embedding IS NULL AND error_message IS NULL) OR "
            "(status = 'COMPLETED' AND embedding IS NOT NULL AND error_message IS NULL) OR "
            "(status = 'FAILED' AND embedding IS NULL)",
            name='ck_document_chunk_embeddings_status_consistency',
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name='ck_document_chunk_embeddings_content_hash_format',
        ),
    )

    op.create_index(
        'ix_document_chunk_embeddings_organization_id',
        'document_chunk_embeddings',
        ['organization_id'],
    )
    op.create_index(
        'ix_document_chunk_embeddings_org_provider_model_version_status',
        'document_chunk_embeddings',
        ['organization_id', 'provider', 'model', 'model_version', 'status'],
    )
    op.create_index(
        'ix_document_chunk_embeddings_org_engagement',
        'document_chunk_embeddings',
        ['organization_id', 'engagement_id'],
    )
    op.create_index(
        'ix_document_chunk_embeddings_org_document',
        'document_chunk_embeddings',
        ['organization_id', 'document_id'],
    )
    op.create_index(
        'ix_document_chunk_embeddings_chunk_id', 'document_chunk_embeddings', ['chunk_id']
    )


def downgrade() -> None:
    op.drop_table('document_chunk_embeddings')
    op.drop_constraint(
        'uq_engagements_id_organization_id', 'engagements', type_='unique'
    )
    op.drop_constraint('uq_documents_id_engagement_id', 'documents', type_='unique')
    op.drop_constraint(
        'uq_document_chunks_id_document_id', 'document_chunks', type_='unique'
    )
    # Deliberately not dropping the `vector` extension -- see module docstring.
