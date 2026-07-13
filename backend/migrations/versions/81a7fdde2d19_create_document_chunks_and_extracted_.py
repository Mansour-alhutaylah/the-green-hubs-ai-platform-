"""create_document_chunks_and_extracted_text_unique

Revision ID: 81a7fdde2d19
Revises: 73688728b480
Create Date: 2026-07-13 12:23:43.595597

Sprint 3.5, Document Processing Foundation.

``document_chunks`` is a brand-new table (no historical/reconciled data
to preserve), so it is designed cleanly rather than mirroring an
already-live schema: ``document_id`` is ``NOT NULL`` (a chunk with no
document is meaningless, unlike ``extracted_text.document_id``'s
historically nullable column, which this migration does not touch), and
``created_at`` is ``TIMESTAMP WITH TIME ZONE`` -- matching ``documents``
(its direct parent table, already timezone-aware since Sprint 1), not
``extracted_text``'s older naive-timestamp convention. ``ON DELETE NO
ACTION`` matches every other foreign key in this schema (see
``73688728b480``'s documented rationale).

``UNIQUE(extracted_text.document_id)`` encodes the "one extracted-text
record per Document" contract at the database level. Verified safe to
add during Sprint 3.5 planning by querying the live table directly:
0 rows, 0 duplicate ``document_id`` values, 0 null ``document_id``
values. No nullability change to any existing ``extracted_text`` column,
and no other historical schema is touched.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '81a7fdde2d19'
down_revision: Union[str, None] = '73688728b480'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='NO ACTION'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_document_chunks_document_id'), 'document_chunks', ['document_id'], unique=False
    )
    op.create_unique_constraint(
        'uq_document_chunks_document_id_chunk_index',
        'document_chunks',
        ['document_id', 'chunk_index'],
    )
    op.create_unique_constraint(
        'uq_extracted_text_document_id', 'extracted_text', ['document_id']
    )


def downgrade() -> None:
    op.drop_constraint('uq_extracted_text_document_id', 'extracted_text', type_='unique')
    op.drop_constraint(
        'uq_document_chunks_document_id_chunk_index', 'document_chunks', type_='unique'
    )
    op.drop_index(op.f('ix_document_chunks_document_id'), table_name='document_chunks')
    op.drop_table('document_chunks')
