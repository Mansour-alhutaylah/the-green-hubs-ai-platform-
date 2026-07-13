"""add_document_chunk_char_offsets

Revision ID: 233e7656bf79
Revises: 81a7fdde2d19
Create Date: 2026-07-13 18:19:25.647530

Sprint 3.6A, Vector Retrieval Foundation. ``document_chunks.content`` has
always had a corresponding ``(char_start, char_end)`` slice available from
the chunker (``TextChunk.char_start``/``char_end``), but Sprint 3.5's
processing service never persisted it. Adding both as ``NOT NULL`` in a
single step (no nullable-then-backfill-then-constrain dance) is safe only
because ``document_chunks`` has no rows yet in any environment this
migration is expected to run against -- verified live immediately before
writing this migration (0 rows) and re-verified defensively at upgrade
time below, which aborts loudly rather than inventing placeholder offsets
for any row it did not expect to find.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '233e7656bf79'
down_revision: Union[str, None] = '81a7fdde2d19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    row_count = bind.execute(sa.text("SELECT COUNT(*) FROM document_chunks")).scalar()
    if row_count:
        raise RuntimeError(
            f"Refusing to add NOT NULL char_start/char_end to document_chunks: "
            f"the table contains {row_count} existing row(s) with no offset data "
            f"to backfill safely. This migration only supports the "
            f"currently-empty-table case; it will not invent zero or otherwise "
            f"placeholder offsets for pre-existing rows. If this table now has "
            f"real data, write a proper backfill migration instead of editing "
            f"this one."
        )

    op.add_column('document_chunks', sa.Column('char_start', sa.Integer(), nullable=False))
    op.add_column('document_chunks', sa.Column('char_end', sa.Integer(), nullable=False))
    op.create_check_constraint(
        'ck_document_chunks_char_start_non_negative', 'document_chunks', 'char_start >= 0'
    )
    op.create_check_constraint(
        'ck_document_chunks_char_end_after_start', 'document_chunks', 'char_end > char_start'
    )


def downgrade() -> None:
    op.drop_constraint(
        'ck_document_chunks_char_end_after_start', 'document_chunks', type_='check'
    )
    op.drop_constraint(
        'ck_document_chunks_char_start_non_negative', 'document_chunks', type_='check'
    )
    op.drop_column('document_chunks', 'char_end')
    op.drop_column('document_chunks', 'char_start')
