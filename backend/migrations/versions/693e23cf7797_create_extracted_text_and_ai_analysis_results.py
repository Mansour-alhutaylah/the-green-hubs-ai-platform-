"""create_extracted_text_and_ai_analysis_results

Revision ID: 693e23cf7797
Revises: 12c7b2051fc6
Create Date: 2026-07-11 00:00:01.000000

Retroactively brings ``extracted_text`` and ``ai_analysis_results``
under Alembic control -- same rationale as ``12c7b2051fc6``. Both FK to
``documents``, which already exists as of ``eeb31636c877`` (an ancestor
of this revision), so ordering is valid even though this migration is
chained after ``12c7b2051fc6`` rather than directly after
``eeb31636c877``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '693e23cf7797'
down_revision: Union[str, None] = '12c7b2051fc6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'extracted_text',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=True),
        sa.Column('extracted_content', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'ai_analysis_results',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('recommendations', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('ai_analysis_results')
    op.drop_table('extracted_text')
